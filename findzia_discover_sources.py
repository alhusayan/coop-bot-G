"""Small discovery lanes using the application's existing retrieval policies.

Only indexed web offers are cached here. Shopify catalog rows never enter this
adapter, its cache, product-page enrichment or background work.
"""
import asyncio
import copy
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, InvalidOperation
from functools import partial

from findzia_shopify_catalog import safe_url, plain


class MarketSources:
    def __init__(self, services):
        self.s = services
        self.pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix='discover-market')
        self.cache = OrderedDict()
        self.inflight = {}
        self.lock = threading.Lock()

    def specs(self, query, country, scope):
        cc = country.lower()
        if scope == 'global':
            fast = bool(self.s.get('FAST_PROVIDERS'))
            return [('global', target, 'global_fast' if fast else 'global')
                    for target in self.s.get('DEFAULT_GLOBAL_COUNTRIES', ('us', 'cn'))
                    if target != cc]
        kinds = self.s['_local_fast_discovery_kinds'](cc, query)
        if kinds:
            search = next((k for k in kinds if '_search:en' in k), kinds[0])
            second = next((k for k in kinds if '_shopping:' in k), '')
            if second and not self.s.get('_shopping_gl_supported', lambda _: True)(cc):
                second = ''
            # Some markets have no Shopping feed. Spend the same second lane
            # on their existing merchant scopes rather than an empty request.
            provider = search.split('_', 1)[0]
            if not second and self.s.get('_fast_provider_supports_operators', lambda _: False)(provider):
                second = search + ':scoped'
            if not second:
                second = next((k for k in kinds if '_images:en' in k), '')
            return [('local', cc, k) for k in dict.fromkeys((search, second)) if k]
        return [('local', cc, k) for k in self.s['_local_primary_discovery_kinds'](cc)[:2]]

    def normalize(self, rows, channel):
        out = []
        for raw in rows or []:
            url = safe_url(raw.get('url') or raw.get('link'))
            images = self.s['_web_offer_image_candidates'](raw)
            image = next((safe_url(x) for x in images if safe_url(x)), '')
            quote = self.s['_web_indexed_offer_quote'](raw)
            if not url or not image or not quote or raw.get('in_stock') is False:
                continue
            if self.s['_web_collection_url'](url):
                continue
            low, high = quote.get('min'), quote.get('max')
            value = low if low is not None else high
            if value is None or value <= 0:
                continue
            store = self.s['_ui_plain_store_name'](raw.get('store') or raw.get('source') or '', url)
            out.append({'url': url, 'title': plain(raw.get('title'), 240), 'image': image,
                        'store': plain(store, 120), 'source': channel, 'discovery_source': channel,
                        'retrieval_sources': list(raw.get('retrieval_sources') or []),
                        'price_source': raw.get('price_source') or 'indexed_offer',
                        'money': {'value': str(value), 'currency': quote['currency'],
                                  'kind': quote['kind'], 'min': str(low) if low is not None else None,
                                  'max': str(high) if high is not None else None, 'unit': quote.get('unit', '')},
                        'cacheable': True})
        return out

    def _run(self, query, spec):
        role, cc, kind = spec
        market = dict(self.s['_web_market'](cc), _collection_deadline=time.monotonic() + 8)
        if role == 'global':
            fn = partial(self.s['_global_discovery_request'], query, cc, kind, 8)
            channel = 'web_search'
        else:
            fn = partial(self.s['_local_discovery_request'], query, market, kind, 8, threading.Event())
            channel = 'shopping_search' if 'shopping' in kind else 'web_search'
        rows = self.s['_run_with_market'](market, fn)
        return self.normalize(rows, channel)

    async def search(self, query, country, scope):
        specs = self.specs(query, country, scope)
        pending = []
        for spec in specs:
            key = (query, country.upper(), scope, spec)
            with self.lock:
                hit = self.cache.get(key)
                if hit and time.monotonic() - hit[0] < 600:
                    pending.append((None, copy.deepcopy(hit[1])))
                    continue
                future = self.inflight.get(key)
                created = future is None
                if created:
                    if len(self.inflight) >= 24:
                        pending.append((None, []))
                        continue
                    future = self.pool.submit(self._run, query, spec)
                    self.inflight[key] = future
            # Attach outside the lock: an already-finished Future calls back inline.
            def finish(done, key=key):
                try:
                    rows = done.result()
                except Exception:
                    rows = []
                with self.lock:
                    self.inflight.pop(key, None)
                    if rows:
                        self.cache[key] = (time.monotonic(), copy.deepcopy(rows))
                        self.cache.move_to_end(key)
                        while len(self.cache) > 128:
                            self.cache.popitem(last=False)
            if created:
                future.add_done_callback(finish)
            pending.append((future, None))
        async def collect(future, cached):
            if future is None:
                return cached
            try:
                return await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(future)), 18)
            except (Exception, asyncio.CancelledError):
                if asyncio.current_task().cancelling():
                    raise
                return []
        batches = await asyncio.gather(*(collect(*pair) for pair in pending))
        rows = [row for batch in batches for row in batch]
        return {'status': 'ok' if rows else 'empty', 'items': rows}

    async def fx(self, currency):
        def load():
            rates = self.s['get_fx_rates'](currency)
            # The legacy converter can return an old quote after an outage.
            # Discovery must not silently use that unbounded stale fallback.
            with self.s['FX_CACHE_LOCK']:
                record = self.s['FX_CACHE'].get(currency) or {}
                stamp = record.get('ts', 0)
            if not 0 <= time.time() - stamp <= 86400:
                return {}
            clean = {}
            for key, value in rates.items():
                try:
                    rate = Decimal(str(value))
                    if rate.is_finite() and rate > 0:
                        clean[str(key).upper()] = str(rate)
                except (InvalidOperation, ValueError):
                    pass
            return clean
        try:
            return await asyncio.wait_for(asyncio.get_running_loop().run_in_executor(self.pool, load), 12)
        except Exception:
            return {}
