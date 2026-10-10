"""Unlisted discovery trial: live catalog previews, never a catalog cache.

Country evidence and a single display currency are applied before admission.
Shopify stays live; indexed web lanes use the existing bounded search policies.
"""
import asyncio
import hashlib
import random
import re
import time
from collections import OrderedDict, Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse
from findzia_shopify_catalog import ShopifyCatalog, url_key, ZERO_DECIMAL, THREE_DECIMAL, FOUR_DECIMAL
from findzia_market_evidence import MerchantMarkets
from findzia_discover_sources import MarketSources

EDITION_SECONDS = 600
CATEGORIES = (
    ('beauty', 'Beauty', 'الجمال', ('moisturizer', 'shampoo', 'perfume')),
    ('women', 'Women', 'النساء', ('women handbags', 'women dresses', 'women shoes')),
    ('men', 'Men', 'الرجال', ('men sneakers', 'men shirts', 'men watches')),
    ('home', 'Home', 'المنزل', ('vase', 'table lamp', 'dinner set')),
    ('tech', 'Tech', 'التقنية', ('wireless headphones', 'phone case', 'bluetooth speaker')),
    ('active', 'Active', 'الرياضة', ('dumbbell', 'running shoes', 'yoga mat')),
)
HEADERS = {'Cache-Control': 'no-store, no-transform', 'X-Robots-Tag': 'noindex, nofollow'}


def recipe(now=None):
    edition = int((time.time() if now is None else now) // EDITION_SECONDS)
    # Adjacent editions always change the queries; no random refresh timer in UI.
    return {'edition': str(edition), 'interval_seconds': EDITION_SECONDS,
            'theme': edition % 3,
            'categories': [{'id': key, 'en': en, 'ar': ar,
                            'query': queries[(edition + i) % len(queries)]}
                           for i, (key, en, ar, queries) in enumerate(CATEGORIES)]}


def display_money(money, currency, rates):
    """Rates are quoted against the display currency; never relabel raw money."""
    source = str(money.get('currency') or '').upper()
    if not currency or not source:
        return None
    try:
        divisor = Decimal(1) if source == currency else Decimal(str(rates.get(source, 0)))
        if not divisor.is_finite() or divisor <= 0:
            return None
        digits = 0 if currency in ZERO_DECIMAL else 3 if currency in THREE_DECIMAL else 4 if currency in FOUR_DECIMAL else 2
        quantum = Decimal(1).scaleb(-digits)
        def convert(value):
            amount = Decimal(str(value))
            if not amount.is_finite() or amount <= 0:
                raise ValueError('invalid amount')
            return format((amount / divisor).quantize(quantum, rounding=ROUND_HALF_UP), f'.{digits}f')
        value = convert(money['value'])
        if Decimal(value) <= 0:
            return None
        result = {'value': value, 'currency': currency, 'converted': source != currency,
                  'kind': money.get('kind', 'exact'), 'unit': money.get('unit', '')}
        for bound in ('min', 'max'):
            if money.get(bound) is not None:
                result[bound] = convert(money[bound])
        return result
    except (InvalidOperation, ValueError, TypeError, KeyError):
        return None


def select_rows(rows, seed, seen):
    # Preserve provenance on duplicate listings, then alternate source channels.
    unique = OrderedDict()
    for row in rows:
        if not all(row.get(k) for k in ('url', 'image', 'title', 'money', 'display_money')):
            continue
        key = url_key(row['url'])
        channel = row.get('discovery_source') or row.get('source') or 'web_search'
        if key in unique:
            unique[key]['discovery_sources'] = sorted(set(unique[key]['discovery_sources']) | {channel})
        else:
            unique[key] = dict(row, discovery_source=channel, discovery_sources=[channel])
    buckets = {}
    for row in unique.values():
        buckets.setdefault(row['discovery_source'], []).append(row)
    rng = random.Random(seed)
    for values in buckets.values():
        rng.shuffle(values)
    ordered, keys = [], sorted(buckets, key=lambda key: (key == 'shopify_catalog', key))
    while any(buckets.values()):
        for key in keys:
            if buckets[key]:
                ordered.append(buckets[key].pop())
    chosen, stores = [], {}
    # First give different merchants their slots, then fill sparse sections
    # from the available stores without allowing one merchant to take all eight.
    for limit in (2, 4):
        for row in ordered:
            key = url_key(row['url'])
            store = urlsplit(row['url']).hostname
            if not store or key in seen or stores.get(store, 0) >= limit:
                continue
            seen.add(key)
            stores[store] = stores.get(store, 0) + 1
            chosen.append(row)
            if len(chosen) == 8:
                return chosen
    return chosen


class Discovery:
    def __init__(self, catalog, countries, clock=time.time, *, sources=None, currencies=None, markets=None, cross_border_domains=()):
        self.catalog, self.countries, self.clock = catalog, countries, clock
        self.sources = sources
        self.currencies = {k.upper(): v for k, v in (currencies or {}).items()}
        self.markets = markets or MerchantMarkets(countries)
        self.cross_border_domains = frozenset(cross_border_domains)
        self.inflight = 0
        self.clients = OrderedDict()
        self.slots = asyncio.Semaphore(6)

    def admit(self, client):
        now = self.clock()
        key = hashlib.sha256(client.encode()).hexdigest()
        start, count = self.clients.pop(key, (now, 0))
        if now - start >= 60:
            start, count = now, 0
        self.clients[key] = (start, count + 1)
        while len(self.clients) > 2048:
            self.clients.popitem(last=False)
        return count < 8 and self.inflight < 2

    async def feed(self, country, lang, query='', scope='local'):
        plan = recipe(self.clock())
        currency = self.currencies.get(country, '')
        categories = ([{'id': 'search', 'en': query, 'ar': query, 'query': query}]
                      if query else plan['categories'])

        async def search(category):
            async def catalog():
                async with self.slots:
                    try:
                        result = await self.catalog._search(category['query'], country, lang,
                            origin_country=country if scope == 'local' else '')
                        result['items'] = [dict(row, discovery_source='shopify_catalog') for row in result['items']]
                        return result
                    except Exception:
                        return {'status': 'provider_error', 'items': []}
            async def web():
                if not self.sources:
                    return {'status': 'unavailable', 'items': []}
                try:
                    return await self.sources.search(category['query'], country, scope)
                except Exception:
                    return {'status': 'provider_error', 'items': []}
            indexed, live = await asyncio.gather(web(), catalog())
            return {'status': 'ok' if indexed['items'] or live['items'] else 'empty',
                    'items': indexed['items'] + live['items'],
                    'source_status': {'web': indexed['status'], 'catalog': live['status']}}

        self.inflight += 1
        tasks = [asyncio.create_task(search(category)) for category in categories]
        fx_task = asyncio.create_task(self.sources.fx(currency)) if self.sources and currency else None
        try:
            done, pending = await asyncio.wait(tasks, timeout=21)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            rates = await fx_task if fx_task else {}
            seen, groups = set(), []
            excluded = Counter()
            for category, task in zip(categories, tasks):
                result = task.result() if task in done and not task.cancelled() else {'status': 'timeout', 'items': []}
                admitted = []
                for raw in result['items']:
                    row = self.markets.classify(raw, country)
                    host = urlsplit(row.get('url') or '').hostname or ''
                    if scope == 'global' and row['market_scope'] == 'unknown' and any(
                            host == domain or host.endswith('.' + domain) for domain in self.cross_border_domains):
                        row.update(market_scope='global', merchant_country=None, flag='',
                                   merchant_country_evidence='approved_cross_border_catalog')
                    if row['market_scope'] != scope:
                        excluded['market'] += 1
                        continue
                    shown = display_money(row.get('money') or {}, currency, rates)
                    if shown is None:
                        excluded['currency'] += 1
                        continue
                    row['display_money'] = shown
                    admitted.append(row)
                rows = select_rows(admitted, plan['edition'] + country + scope + category['id'], seen)
                groups.append({**{k: category[k] for k in ('id', 'en', 'ar')},
                               'status': result['status'], 'source_status': result.get('source_status', {}), 'items': rows})
            all_rows = [r for g in groups for r in g['items']]
            counts = Counter(source for r in all_rows for source in r['discovery_sources'])
            return {**{k: plan[k] for k in ('edition', 'interval_seconds', 'theme')},
                    'country': country, 'currency': currency, 'scope': scope,
                    'generated_at': int(self.clock()), 'delivery': 'mixed_sources', 'cacheable': False,
                    'source_counts': dict(counts), 'store_count': len({urlsplit(r['url']).hostname for r in all_rows}),
                    'excluded': dict(excluded), 'groups': groups}
        finally:
            for task in tasks + ([fx_task] if fx_task else []):
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, *([fx_task] if fx_task else []), return_exceptions=True)
            self.inflight -= 1


def install_discover(app, countries, services=None):
    # Separate admission/concurrency from the primary text and Lens pipelines.
    services = services or {}
    markets = MerchantMarkets(countries, services.get('COUNTRY_MAJOR_STORE_DOMAINS'))
    sources = MarketSources(services, markets) if services else None
    discovery = Discovery(ShopifyCatalog(countries, markets=markets), countries, sources=sources,
                          currencies=services.get('COUNTRY_CURRENCIES'), markets=markets,
                          cross_border_domains=[domain for _, domain in services.get('GLOBAL_MARKET_STORES', {}).get('cn', ())])

    @app.get('/api/discover/config')
    async def config():
        return JSONResponse({'countries': {str(k).upper(): v for k, v in countries.items()},
                             'currencies': discovery.currencies, 'interval_seconds': EDITION_SECONDS}, headers=HEADERS)

    @app.get('/api/discover/trial')
    async def trial(request: Request):
        country = str(request.query_params.get('country', 'KW')).upper()
        lang = 'ar' if request.query_params.get('lang') == 'ar' else 'en'
        scope = request.query_params.get('scope', 'local')
        if scope not in ('local', 'global'):
            return JSONResponse({'error': 'invalid_scope'}, status_code=400, headers=HEADERS)
        query = re.sub(r'[\x00-\x1f]', '', request.query_params.get('q', '')).strip()[:120]
        if country not in discovery.catalog.countries:
            return JSONResponse({'error': 'unsupported_country'}, status_code=400, headers=HEADERS)
        # ASGI's trusted proxy configuration owns client identity; never trust a
        # client-supplied forwarding header here.
        client = request.client.host if request.client else 'unknown'
        if not discovery.admit(client):
            return JSONResponse({'error': 'busy'}, status_code=429,
                                headers={**HEADERS, 'Retry-After': '60'})
        result = await discovery.feed(country, lang, query, scope)
        return JSONResponse(result, headers=HEADERS)

    return discovery
