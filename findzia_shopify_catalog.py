"""Live Shopify Global Catalog supplement; no catalog/image cache or indexing.

Runs inside the admitted search request, outside price scraping, image proxies,
AI verification and persistent search history. Merchant origin is not inferred
from the buyer's destination or from a price currency.
"""
import asyncio
from contextlib import suppress
from decimal import Decimal, InvalidOperation
import html
import json
import os
import re
import time
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import httpx
from fastapi.responses import JSONResponse
from findzia_market_evidence import MerchantMarkets

ENDPOINT = 'https://catalog.shopify.com/api/ucp/mcp'
VERSION = '2026-08-25'
ZERO_DECIMAL = frozenset('BIF CLP DJF GNF ISK JPY KMF KRW PYG RWF UGX VND VUV XAF XOF XPF'.split())
THREE_DECIMAL = frozenset('BHD IQD JOD KWD LYD OMR TND'.split())
FOUR_DECIMAL = frozenset(('CLF', 'UYW'))


def agent_profile():
    capabilities = {}
    for operation in ('search', 'lookup'):
        capabilities['dev.ucp.shopping.catalog.' + operation] = [{
            'version': VERSION,
            'spec': f'https://ucp.dev/{VERSION}/specification/catalog/{operation}',
            'schema': f'https://ucp.dev/{VERSION}/schemas/shopping/catalog_{operation}.json',
        }]
    capabilities['dev.shopify.catalog.global'] = [{
        'version': VERSION,
        'spec': 'https://shopify.dev/docs/agents/catalog/global-catalog',
        'schema': f'https://shopify.dev/ucp/schemas/{VERSION}/shopify_catalog_global.json',
        'extends': list(capabilities),
    }]
    return {'ucp': {'version': VERSION, 'capabilities': capabilities, 'payment_handlers': {}, 'services': {
        'dev.ucp.shopping': [{'version': VERSION, 'transport': 'mcp',
                             'spec': f'https://ucp.dev/{VERSION}/specification/overview',
                             'schema': f'https://ucp.dev/{VERSION}/services/shopping/mcp.openrpc.json'}]}}}


def safe_url(value):
    if not isinstance(value, str) or len(value) > 4096 or re.search(r'[\s\x00-\x1f]', value):
        return ''
    try:
        parsed = urlsplit(value)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            return ''
        return value
    except ValueError:
        return ''


def url_key(value):
    try:
        p = urlsplit(value)
        query = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith('utm_')
                 and k.lower() not in ('gclid', 'fbclid', 'srsltid', '_gsid')]
        return urlunsplit(('https', p.netloc.lower().removeprefix('www.'), p.path.rstrip('/'),
                           urlencode(sorted(query)), ''))
    except (TypeError, ValueError):
        return ''


def plain(value, limit=300):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', '', str(value or '')))).strip()[:limit]


def money(value):
    """UCP amounts are ISO currency minor units, never always divide by 100."""
    if not isinstance(value, dict):
        return None
    amount, currency = value.get('amount'), value.get('currency', '')
    if type(amount) is not int or amount < 0 or not re.fullmatch(r'[A-Z]{3}', str(currency)):
        return None
    digits = 0 if currency in ZERO_DECIMAL else 3 if currency in THREE_DECIMAL else 4 if currency in FOUR_DECIMAL else 2
    try:
        display = format(Decimal(amount).scaleb(-digits), f'.{digits}f')
    except (InvalidOperation, ValueError):
        return None
    return {'amount_minor': amount, 'currency': currency, 'value': display,
            'text': f'{display} {currency}'}


def normalize_products(products, country, visual=False, origin_country=''):
    rows, seen = [], set()
    for product in products[:50]:
        if not isinstance(product, dict):
            continue
        variants = product.get('variants')
        if not isinstance(variants, list):
            continue
        for variant in variants[:50]:
            if not isinstance(variant, dict) or (variant.get('availability') or {}).get('available') is not True:
                continue
            shipping = (variant.get('requires') or {}).get('shipping')
            # Shopify documents that digital products can bypass ships_from.
            # Only a physically shipped variant can supply local-origin proof.
            if visual and shipping is False:
                continue
            proven_origin = origin_country if shipping is True else ''
            url = safe_url(variant.get('url') or product.get('url'))
            price = money(variant.get('price'))
            title = plain(product.get('title'))
            seller = variant.get('seller') or {}
            if not url or not price or not title or not isinstance(seller, dict):
                continue
            key = url_key(url)
            if key in seen:
                continue
            media = (variant.get('media') or []) + (product.get('media') or [])
            image = next((safe_url(m.get('url')) for m in media if isinstance(m, dict)
                          and m.get('type') == 'image' and safe_url(m.get('url'))), '')
            if not image:
                continue
            seen.add(key)
            rows.append({'url': url, 'title': title, 'image': image,
                         'store': plain(seller.get('name') or urlsplit(url).hostname, 120),
                         'price': price['text'], 'money': price,
                         'product_id': plain(product.get('id'), 200),
                         'variant_id': plain(variant.get('id'), 200),
                         'source': 'shopify_catalog', 'cacheable': False,
                         'market_scope': 'local' if proven_origin else 'unknown',
                         'merchant_country': proven_origin.upper() or None,
                         'merchant_country_evidence': 'shopify_origin_filter' if proven_origin else '',
                         'seller_id': plain(seller.get('id'), 200),
                         'destination_country': country.upper(),
                         'shipping_evidence': 'catalog_filter', 'shipping_cost_verified': False,
                         'match_type': 'visual_similarity' if visual else 'catalog_search'})
            # One representative available variant per product; no misleading
            # cheapest-price comparison across sizes, conditions or currencies.
            break
    return rows


def event_line(event):
    return (json.dumps(event, ensure_ascii=False, separators=(',', ':')) + '\n').encode()


class ShopifyCatalog:
    def __init__(self, countries, *, transport=None, markets=None):
        self.countries = frozenset(c.upper() for c in countries)
        self.transport = transport
        self.markets = markets or MerchantMarkets(countries)
        self.inflight = 0
        self.retry_after = 0.0

    def enabled(self, preview=False):
        mode = os.environ.get('FINDZIA_SHOPIFY_CATALOG_ENABLED', 'false').lower()
        return mode in ('true', '1', 'yes') or (mode == 'preview' and preview)

    async def search(self, query, country, lang='en', *, image_b64='', mime='image/jpeg'):
        # Concurrent local discovery gives positive origin evidence. Absence from
        # a limited local result page never proves that another store is foreign.
        calls = [asyncio.create_task(self._search(query, country, lang, image_b64=image_b64,
                    mime=mime, origin_country=origin)) for origin in (str(country).upper(), '')]
        try:
            local, general = await asyncio.gather(*calls)
            rows, seen = [], set()
            for result in (local, general):
                for row in result['items']:
                    key = url_key(row['url'])
                    if key not in seen:
                        rows.append(self.markets.classify(row, country)); seen.add(key)
            return {'status': 'ok' if rows or any(r['status'] == 'ok' for r in (local, general)) else general['status'],
                    'items': rows[:18]}
        finally:
            for call in calls:
                if not call.done(): call.cancel()
            await asyncio.gather(*calls, return_exceptions=True)

    async def _search(self, query, country, lang='en', *, image_b64='', mime='image/jpeg', origin_country=''):
        country = str(country).upper()
        if country not in self.countries:
            return {'status': 'unsupported_country', 'items': []}
        if self.inflight >= 8 or time.monotonic() < self.retry_after:
            return {'status': 'busy', 'items': []}
        profile = os.environ.get('FINDZIA_SHOPIFY_PROFILE_URL', 'https://api.findzia.com/.well-known/ucp')
        if not safe_url(profile):
            return {'status': 'unconfigured', 'items': []}
        catalog = {'context': {'address_country': country, 'language': lang},
                   'filters': {'ships_to': {'country': country}, 'available': True},
                   'pagination': {'limit': 6 if origin_country else 12}}
        if origin_country:
            catalog['filters']['ships_from'] = [{'country': origin_country}]
        if query:
            catalog['query'] = str(query)[:1000]
        if image_b64:
            if mime not in ('image/jpeg', 'image/png', 'image/webp') or len(image_b64) > 12000000:
                return {'status': 'unsupported_image', 'items': []}
            catalog['like'] = [{'image': {'content_type': mime, 'data': image_b64}}]
        if not query and not image_b64:
            return {'status': 'empty_query', 'items': []}
        payload = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {
            'name': 'search_catalog', 'arguments': {
                'meta': {'ucp-agent': {'profile': profile}}, 'catalog': catalog}}}
        self.inflight += 1
        try:
            # The absolute deadline also covers trickling bodies and connection
            # acquisition. No automatic retries and no persistence of content.
            async with asyncio.timeout(12):
                async with httpx.AsyncClient(transport=self.transport, timeout=httpx.Timeout(10, connect=3),
                                             follow_redirects=False) as client:
                    async with client.stream('POST', ENDPOINT, json=payload,
                            headers={'Accept': 'application/json, text/event-stream'}) as response:
                        if response.status_code == 429:
                            self.retry_after = time.monotonic() + 60
                            return {'status': 'rate_limited', 'items': []}
                        response.raise_for_status()
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > 2000000:
                                return {'status': 'invalid_response', 'items': []}
                        if 'text/event-stream' in response.headers.get('content-type', ''):
                            records = [line[5:].strip() for line in body.decode().splitlines() if line.startswith('data:')]
                            data = next((json.loads(r) for r in records if r and r != '[DONE]'), {})
                        else:
                            data = json.loads(body)
            result = data.get('result') or {}
            structured = result.get('structuredContent') or {}
            products = structured.get('products')
            if data.get('error') or result.get('isError') or structured.get('status') not in (None, 'success') or not isinstance(products, list):
                return {'status': 'provider_error', 'items': []}
            # Fail closed if requested shipping/availability filters were ignored.
            if any(isinstance(m, dict) and 'unsupported' in str(m.get('code', '')).lower()
                   for m in structured.get('messages', [])):
                return {'status': 'unsupported_filter', 'items': []}
            return {'status': 'ok', 'items': normalize_products(products, country, bool(image_b64), origin_country)}
        except (TimeoutError, httpx.TimeoutException):
            return {'status': 'timeout', 'items': []}
        except (httpx.HTTPError, ValueError, TypeError, AttributeError, ImportError):
            return {'status': 'provider_error', 'items': []}
        finally:
            self.inflight -= 1

    def wrap_response(self, response, *, opted_in, query, country, lang, image_b64='', mime='image/jpeg', preview=False):
        if not opted_in or not self.enabled(preview) or response.status_code != 200:
            return response
        response.body_iterator = self.supplement(response.body_iterator, query, country, lang,
                                                 image_b64=image_b64, mime=mime)
        response.headers['Cache-Control'] = 'no-store, no-transform'
        return response

    async def supplement(self, source, query, country, lang, *, image_b64='', mime='image/jpeg'):
        """Interleave a separate ephemeral event, outside all existing caches.

        The original events flow immediately. Only its terminal done waits for
        the bounded supplement. Closing the consumer cancels both async tasks.
        """
        task = asyncio.create_task(self.search(query, country, lang, image_b64=image_b64, mime=mime))
        iterator, pending, buffer = source.__aiter__(), None, b''
        sent, catalog_rows, primary_urls = False, [], set()
        final = None
        try:
            pending = asyncio.create_task(anext(iterator))
            while pending is not None or not sent:
                waiters = {pending} if pending is not None else set()
                if not sent:
                    waiters.add(task)
                ready, _ = await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
                # Forward primary results before the supplemental batch when
                # both are ready; never add latency to the first existing card.
                if pending in ready:
                    try:
                        chunk = pending.result()
                    except StopAsyncIteration:
                        pending = None
                    else:
                        buffer += chunk.encode() if isinstance(chunk, str) else chunk
                        lines = buffer.split(b'\n')
                        buffer = lines.pop()
                        for line in lines:
                            if not line.strip():
                                continue
                            data = self.markets.event(json.loads(line), country)
                            if data.get('event') in ('result', 'upsert'):
                                primary_urls.add(url_key((data.get('item') or {}).get('url', '')))
                            if data.get('event') == 'remove':
                                primary_urls.discard(url_key(data.get('url', '')))
                            for row in data.get('results', data.get('all_results', [])) or []:
                                primary_urls.add(url_key(row.get('url', '')))
                            if data.get('event') == 'done':
                                final = data
                            else:
                                yield event_line(data)
                            if data.get('event') == 'error' and not data.get('recoverable'):
                                return
                            if data.get('event') == 'recommendations':
                                task.cancel()
                                sent, catalog_rows = True, []
                        pending = asyncio.create_task(anext(iterator)) if final is None else None
                if task in ready and not sent:
                    try:
                        result = task.result()
                    except Exception:
                        # A supplemental provider may never break the admitted
                        # primary search, even for an unexpected client failure.
                        result = {'status': 'provider_error', 'items': []}
                    catalog_rows = result['items']  # UI combines duplicates and retains positive merchant-origin proof.
                    yield event_line({'event': 'catalog', 'source': 'shopify_catalog',
                                      'status': result['status'], 'items': catalog_rows,
                                      'destination_country': str(country).upper(), 'cacheable': False})
                    sent = True
            if final is not None:
                # Existing credit settlement sees the same single search and
                # must not clear valid catalog evidence on primary count=0.
                if catalog_rows:
                    final = dict(final, count=max(int(final.get('count') or 0), len(primary_urls - {''})) +
                                 sum(url_key(r['url']) not in primary_urls for r in catalog_rows))
                yield event_line(final)
            elif buffer:
                yield buffer
        finally:
            for work in (pending, task):
                if work is not None:
                    work.cancel()
            await asyncio.gather(*(work for work in (pending, task) if work is not None), return_exceptions=True)
            if hasattr(iterator, 'aclose'):
                with suppress(Exception):
                    await iterator.aclose()


def install_catalog(app, countries, stores=None):
    catalog = ShopifyCatalog(countries, markets=MerchantMarkets(countries, stores))

    @app.get('/.well-known/ucp')
    async def profile():
        return JSONResponse(agent_profile(), headers={'Cache-Control': 'public, max-age=300'})

    return catalog
