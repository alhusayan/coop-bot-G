"""Bounded structured product prices. No app startup, URL fetching or secret logs.

The caller owns the per-search budget. One selected listing = at most one API
request, with no automatic retry/fallback after an attempted request. Prices
remain provider-observed, never labelled merchant-page verified.
"""
import copy
import json
import os
import re
import threading
import time
from concurrent.futures import Future, TimeoutError
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit, parse_qsl

import requests
from findzia_cache import provider_cacheable

SHEIN_CURRENCIES = {
    'us.shein.com': 'USD', 'roe.shein.com': 'EUR', 'eur.shein.com': 'EUR',
    'de.shein.com': 'EUR', 'fr.shein.com': 'EUR', 'it.shein.com': 'EUR',
    'ch.shein.com': 'CHF', 'pl.shein.com': 'PLN', 'pt.shein.com': 'EUR',
    'es.shein.com': 'EUR', 'www.shein.se': 'SEK', 'www.shein.co.uk': 'GBP',
}
_TRACKING = {'srsltid', 'gclid', 'fbclid', 'msclkid'}


def _url(value):
    try:
        parsed = urlsplit(value if isinstance(value, str) else '')
        return parsed if (parsed.scheme in ('https', 'http') and parsed.hostname
                          and not parsed.username and not parsed.password
                          and parsed.port in (None, 80, 443)) else None
    except ValueError:
        return None


def shein_params(row):
    parsed = _url(row.get('url'))
    if not parsed or parsed.hostname not in SHEIN_CURRENCIES:
        return None  # No substitution of US/Europe for m/ar/jo or Gulf URLs.
    match = re.fullmatch(r'/[^/]*-p-(\d{6,})\.html', parsed.path, re.I)
    if not match or parsed.fragment or any(k not in _TRACKING and not k.startswith('utm_')
                        for k, _ in parse_qsl(parsed.query, keep_blank_values=True)):
        return None  # The API cannot bind an arbitrary selected SKU/seller.
    return {'engine': 'shein_product', 'product_id': match.group(1),
            'shein_domain': parsed.hostname, 'currency': SHEIN_CURRENCIES[parsed.hostname]}


def shopping_params(card, country, language):
    if not re.fullmatch(r'[a-z]{2}', str(country)) or not re.fullmatch(r'[a-zA-Z-]{2,10}', str(language)):
        return None
    params = {'engine': 'google_product_page', 'gl': country, 'hl': language, 'link': 'resolved'}
    token = card.get('product_token')
    product_id = card.get('product_id') or card.get('productId')
    if isinstance(token, str) and 10 <= len(token) <= 16000:
        params['product_token'] = token
    elif re.fullmatch(r'\d{6,30}', str(product_id or '')):
        params['product_id'] = str(product_id)
    else:
        return None
    return params


def _amount(label, currency):
    """Only the explicit current label; never extracted/USD/member fallback."""
    if not isinstance(label, str) or len(label) > 60:
        return None
    symbol = {'USD': r'US\$|\$', 'EUR': '€', 'GBP': '£', 'CHF': 'CHF',
              'PLN': 'zł', 'SEK': 'kr'}[currency]
    pattern = r'(?:' + currency + '|' + symbol + ')'
    if not re.search(pattern, label, re.I):
        return None
    digits = re.sub(pattern, '', label, flags=re.I).replace('\xa0', '').replace(' ', '')
    if not re.fullmatch(r'\d+(?:[.,]\d{1,2})?', digits):
        return None
    try:
        value = Decimal(digits.replace(',', '.'))
        return value if value.is_finite() and value > 0 else None
    except InvalidOperation:
        return None


def _shein_records(data, params):
    product = data.get('product')
    if not isinstance(product, dict) or str(product.get('product_id')) != params['product_id']:
        return []
    actual = (data.get('search_metadata') or {}).get('request_url')
    bound = shein_params({'url': actual})
    if not bound or any(bound[k] != params[k] for k in ('product_id', 'shein_domain', 'currency')):
        return []
    echoed = data.get('search_parameters') or {}
    if (echoed.get('shein_domain', params['shein_domain']) != params['shein_domain']
            or echoed.get('currency', params['currency']) != params['currency']):
        return []
    if product.get('is_in_stock') is False or product.get('stock') == 0 or not product.get('title'):
        return []
    currency = params['currency']
    if product.get('currency') and product['currency'] != currency:
        return []
    base = _amount(product.get('price'), currency)
    if base is None:
        return []
    variants = product.get('variants') or {}
    sizes = variants.get('size') or []
    amounts = [] if sizes else [base]
    # Product ID binds a colour, not a size. Preserve a size price range instead
    # of turning the cheapest size or member discount into one universal price.
    for variant in sizes:
        if not isinstance(variant, dict):
            return []
        if variant.get('stock') == 0 or variant.get('is_in_stock') is False:
            continue
        amount = _amount(variant.get('price'), currency)
        if amount is None:
            return []
        amounts.append(amount)
    if not amounts:
        return []
    low, high = min(amounts), max(amounts)
    price = f'{low} {currency}' if low == high else f'{low}-{high} {currency}'
    return [{'link': actual, 'title': product['title'], 'price': price,
             'currency': currency, 'image': product.get('main_image') or '',
             '_structured_price_source': 'searchapi_shein_product'}]


def _google_records(data, params):
    product = data.get('product') or {}
    if (params.get('product_id') and product.get('product_id')
            and str(product['product_id']) != params['product_id']):
        return []
    rows = []
    for offer in (data.get('offers') or [])[:40]:
        if not isinstance(offer, dict):
            continue
        parsed = _url(offer.get('link'))
        if (not parsed or not offer.get('title') or not offer.get('price')
                or re.search(r'(^|\.)google\.', parsed.hostname)
                or 'out of stock' in str(offer.get('stock_information') or '').lower()):
            continue
        row = {k: copy.deepcopy(offer[k]) for k in ('link', 'title', 'price', 'currency',
                   'extracted_price', 'image', 'thumbnail', 'installments_description',
                   'monthly_payment_duration', 'down_payment') if offer.get(k) is not None}
        merchant = offer.get('merchant') or {}
        row.update(source=merchant.get('name', '') if isinstance(merchant, dict) else '',
                   _structured_price_source='searchapi_google_product_page',
                   _shopping_gl=params['gl'])
        if offer.get('installment'):
            row['installments_description'] = 'installment'
        if offer.get('original_price'):
            row['old_price'] = offer['original_price']
        rows.append(row)  # Price and URL always come from this same offer.
    return rows


class StructuredPrices:
    def __init__(self, cost=None, *, key=None, enabled=None, get=None, clock=None):
        self.key = (os.environ.get('SEARCHAPI_API_KEY', '') if key is None else key).strip()
        # Live cross-provider ID compatibility/latency must pass the standalone
        # probe before this route replaces any current production lookup.
        self.enabled = (os.environ.get('FINDZIA_STRUCTURED_PRICES_ENABLED', 'false').lower()
                        not in ('0', 'false', 'off')) if enabled is None else enabled
        self.cost = cost or (lambda *a: None)
        self.get = get or requests.get
        self.clock = clock or time.monotonic
        self.lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(4)
        self.cache = {}
        self.inflight = {}
        self.cooldown = 0.

    def shein(self, row, timeout):
        params = shein_params(row)
        return self.fetch(params, timeout) if params else None

    def shopping(self, card, country, language, timeout):
        params = shopping_params(card, country, language)
        return self.fetch(params, timeout) if params else None

    def fetch(self, params, timeout):
        """None means no request started; a dict consumes this lookup's budget."""
        if not self.enabled or not self.key or timeout < .4:
            return None
        key = json.dumps(params, sort_keys=True)
        began = self.clock()
        with self.lock:
            cached = self.cache.get(key)
            if cached and cached[0] > began and provider_cacheable(cached[1]):
                self.cost('structured_price_cache_hits')
                return copy.deepcopy(cached[1])
            pending = self.inflight.get(key)
            if pending is None:
                if began < self.cooldown or not self.slots.acquire(blocking=False):
                    return None
                self.inflight[key] = Future()
        if pending is not None:
            try:
                return copy.deepcopy(pending.result(timeout=max(.01, timeout)))
            except TimeoutError:
                return {'organic_results': [], '_findzia_lookup_failed': True}
        result = {'organic_results': [], '_findzia_lookup_failed': True}
        response, status, ttl = None, 'unavailable', 20.
        try:
            timeout = min(10., float(timeout))
            connect = min(1., timeout * .15)
            self.cost('structured_price_http_requests')
            self.cost('structured_price_' + params['engine'] + '_requests')
            response = self.get('https://www.searchapi.io/api/v1/search', params=params,
                headers={'Authorization': 'Bearer ' + self.key},
                timeout=(connect, timeout-connect), allow_redirects=False, stream=True)
            code = response.status_code
            status = 'http_' + str(code)
            if code in (401, 402, 403, 429):
                with self.lock:
                    self.cooldown = max(self.cooldown, self.clock() + (60 if code == 429 else 300))
            if code == 200:
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > 2000000 or self.clock() - began > timeout:
                        raise ValueError('response_limit')
                    chunks.append(chunk)
                data = json.loads(b''.join(chunks))
                if (not isinstance(data, dict) or data.get('error') or data.get('errors')
                        or str((data.get('search_metadata') or {}).get('status', 'success')).lower()
                        not in ('success', 'completed')):
                    raise ValueError('provider_failure')
                normalize = _shein_records if params['engine'] == 'shein_product' else _google_records
                rows = normalize(data, params)
                for row in rows:
                    row['_structured_observed_at'] = time.time()
                result = {'organic_results': rows}
                status, ttl = ('accepted' if rows else 'no_bound_offers'), (120. if rows else 30.)
        except Exception as exc:
            status = type(exc).__name__  # Never print provider body, URLs or keys.
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
            with self.lock:
                now = self.clock()
                self.cache = {k: v for k, v in self.cache.items() if v[0] > now}
                if len(self.cache) >= 512:
                    self.cache.pop(next(iter(self.cache)))
                if provider_cacheable(result):
                    self.cache[key] = (now + ttl, copy.deepcopy(result))
                future = self.inflight.pop(key)
                future.set_result(copy.deepcopy(result))
            self.slots.release()
            print('STRUCTURED PRICE ' + json.dumps({'engine': params['engine'], 'status': status,
                'rows': len(result['organic_results']), 'elapsed_ms': int((self.clock()-began)*1000)}))
        return result
