"""Small discovery lanes using the application's existing retrieval policies.

Only indexed web offers are cached here. Shopify catalog rows never enter this
adapter, its cache, product-page enrichment or background work.
"""
import asyncio
import copy
import threading
import time
from collections import OrderedDict, Counter
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, InvalidOperation
from functools import partial
from urllib.parse import urlsplit

from findzia_shopify_catalog import safe_url, plain, url_key


class MarketSources:
    def __init__(self, services, markets=None):
        self.s = services
        self.markets = markets
        self.pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix='discover-market')
        self.page_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='discover-page')
        self.cache = OrderedDict()
        self.inflight = {}
        self.pages = OrderedDict()
        self.page_inflight = {}
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

    @staticmethod
    def money(quote):
        if not quote:
            return None
        low, high = quote.get('min'), quote.get('max')
        value = low if low is not None else high
        if value is None or value <= 0:
            return None
        return {'value': str(value), 'currency': quote['currency'], 'kind': quote['kind'],
                'min': str(low) if low is not None else None,
                'max': str(high) if high is not None else None, 'unit': quote.get('unit', '')}

    def normalize(self, rows, channel, *, incomplete=False):
        out = []
        for raw in rows or []:
            url = safe_url(raw.get('url') or raw.get('link'))
            images = self.s['_web_offer_image_candidates'](raw)
            image = next((safe_url(x) for x in images if safe_url(x)), '')
            quote = self.s['_web_indexed_offer_quote'](raw)
            if not url or not raw.get('title') or raw.get('in_stock') is False:
                continue
            if self.s['_web_collection_url'](url):
                continue
            money = self.money(quote)
            if not incomplete and (not image or not money):
                continue
            store = self.s['_ui_plain_store_name'](raw.get('store') or raw.get('source') or '', url)
            out.append({'url': url, 'title': plain(raw.get('title'), 240), 'image': image,
                        'store': plain(store, 120), 'source': channel, 'discovery_source': channel,
                        'retrieval_sources': list(raw.get('retrieval_sources') or []),
                        'price_source': raw.get('price_source') or 'indexed_offer',
                        'money': money,
                        'cacheable': True})
        return out

    def _run(self, query, spec):
        role, cc, kind = spec
        market = dict(self.s['_web_market'](cc), _collection_deadline=time.monotonic() + 8,
                      _text_serper_passthrough=True)
        if role == 'global':
            fn = partial(self.s['_global_discovery_request'], query, cc, kind, 8)
            channel = 'web_search'
        else:
            fn = partial(self.s['_local_discovery_request'], query, market, kind, 8, threading.Event())
            channel = 'shopping_search' if 'shopping' in kind else 'web_search'
        rows = self.s['_run_with_market'](market, fn)
        return self.normalize(rows, channel, incomplete=True)

    def _page(self, row, country):
        """Read one observed web listing. Catalog rows never enter this method."""
        market = self.s['_web_market'](country.lower())
        snap = self.s['_run_with_market'](market, partial(
            self.s['_web_verified_page_snapshot'], row['url'], row['merchant_country'].lower())) or {}
        # Keep variants, currency selectors and country routes bound to the URL.
        if (not snap.get('is_product') or not snap.get('ok')
                or url_key(snap.get('url')) != url_key(row['url'])
                or snap.get('page_fetch_status') == 'blocked'):
            return {}
        if self.s['_findzia_hard_product_mismatch'](row['title'], snap.get('title') or ''):
            return {}
        availability = str(snap.get('availability') or '').lower()
        if any(word in availability for word in ('outofstock', 'soldout', 'discontinued')):
            return {'unavailable': True}
        patch = {}
        if not row.get('money'):
            money = self.money(self.s['_web_quote_from_fields'](snap))
            if money:
                patch.update(money=money, price_source=snap.get('price_source') or 'product_page')
        if not row.get('image'):
            picture = safe_url(snap.get('product_image') or snap.get('image'))
            if picture:
                patch['image'] = picture
        return patch

    async def recover(self, rows, country, scope):
        if not self.markets or '_web_verified_page_snapshot' not in self.s:
            return rows
        candidates, seen, stores = [], set(), Counter()
        for raw in rows:
            if raw.get('money') and raw.get('image'):
                continue
            # Both an observed URL and positive merchant-country proof are needed.
            if raw.get('discovery_source') not in ('web_search', 'shopping_search'):
                continue
            row = self.markets.classify(raw, country)
            if row['market_scope'] != scope or not row['merchant_country']:
                continue
            key, host = url_key(row['url']), urlsplit(row['url']).hostname
            if key in seen:
                continue
            seen.add(key)
            candidates.append((0 if row.get('money') or row.get('image') else 1, host, row))
        # Prefer a nearly complete offer, with one recovery per merchant/category.
        selected = []
        for _, host, row in sorted(candidates, key=lambda x: x[0]):
            if stores[host]:
                continue
            stores[host] += 1
            selected.append(row)
            if len(selected) == 2:
                break

        async def read(row):
            key = (country, scope, url_key(row['url']), bool(row.get('money')), bool(row.get('image')))
            with self.lock:
                hit = self.pages.get(key)
                if hit and time.monotonic() - hit[0] < 600:
                    return row['url'], dict(hit[1])
                future = self.page_inflight.get(key)
                created = future is None
                if created:
                    if len(self.page_inflight) >= 12:
                        return row['url'], {}
                    future = self.page_pool.submit(self._page, row, country)
                    self.page_inflight[key] = future
            def finish(done):
                try:
                    patch = done.result()
                except Exception:
                    patch = {}
                with self.lock:
                    self.page_inflight.pop(key, None)
                    self.pages[key] = (time.monotonic(), patch)
                    while len(self.pages) > 256:
                        self.pages.popitem(last=False)
            if created:
                future.add_done_callback(finish)
            try:
                patch = await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(future)), 4)
            except Exception:
                patch = {}
            return row['url'], patch
        patches = dict(await asyncio.gather(*(read(row) for row in selected)))
        return [dict(row, **patches.get(row['url'], {})) for row in rows
                if not patches.get(row['url'], {}).get('unavailable')]

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
                return await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(future)), 14)
            except (Exception, asyncio.CancelledError):
                if asyncio.current_task().cancelling():
                    raise
                return []
        batches = await asyncio.gather(*(collect(*pair) for pair in pending))
        rows = [row for batch in batches for row in batch]
        ready_before = sum(bool(row.get('money') and row.get('image')) for row in rows)
        recovered = await self.recover(rows, country, scope)
        ready = [row for row in recovered if row.get('money') and row.get('image')]
        print(f'DISCOVER WEB country={country} scope={scope} query={query[:80]!r} '
              f'candidates={len(rows)} priced={sum(bool(r.get("money")) for r in rows)} '
              f'imaged={sum(bool(r.get("image")) for r in rows)} ready={len(ready)} recovered={len(ready)-ready_before}')
        return {'status': 'ok' if ready else 'empty', 'items': ready}

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
