"""Unlisted discovery trial: live catalog previews, never a catalog cache.

Ten-minute editions rotate our own queries and presentation recipe. Product
data is fetched only for the requesting visitor and is never retained here.
"""
import asyncio
import hashlib
import random
import re
import time
from collections import OrderedDict
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse
from findzia_shopify_catalog import ShopifyCatalog, url_key

EDITION_SECONDS = 600
CATEGORIES = (
    ('beauty', 'Beauty', 'الجمال', ('skin care', 'hair care', 'perfume')),
    ('women', 'Women', 'النساء', ('women handbags', 'women dresses', 'women shoes')),
    ('men', 'Men', 'الرجال', ('men sneakers', 'men shirts', 'men watches')),
    ('home', 'Home', 'المنزل', ('home decor', 'table lamps', 'ceramic dinnerware')),
    ('tech', 'Tech', 'التقنية', ('wireless headphones', 'phone accessories', 'portable speakers')),
    ('active', 'Active', 'الرياضة', ('fitness accessories', 'running shoes', 'yoga accessories')),
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


def select_rows(rows, seed, seen):
    candidates = [row for row in rows if row.get('url') and row.get('image')
                  and row.get('title') and row.get('money')]
    random.Random(seed).shuffle(candidates)
    chosen, stores = [], {}
    for row in candidates:
        key = url_key(row['url'])
        store = urlsplit(row['url']).hostname
        if not store or key in seen or stores.get(store, 0) >= 2:
            continue
        seen.add(key)
        stores[store] = stores.get(store, 0) + 1
        chosen.append(row)
        if len(chosen) == 8:
            break
    return chosen


class Discovery:
    def __init__(self, catalog, countries, clock=time.time):
        self.catalog, self.countries, self.clock = catalog, countries, clock
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

    async def feed(self, country, lang, query=''):
        plan = recipe(self.clock())
        categories = ([{'id': 'search', 'en': query, 'ar': query, 'query': query}]
                      if query else plan['categories'])

        async def search(category):
            async with self.slots:
                try:
                    return await self.catalog._search(category['query'], country, lang)
                except Exception:
                    return {'status': 'provider_error', 'items': []}

        self.inflight += 1
        tasks = [asyncio.create_task(search(category)) for category in categories]
        try:
            # Bound the whole request, including waiting behind another visitor.
            done, pending = await asyncio.wait(tasks, timeout=16)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            seen, groups = set(), []
            for category, task in zip(categories, tasks):
                result = task.result() if task in done and not task.cancelled() else {'status': 'timeout', 'items': []}
                rows = select_rows(result['items'], plan['edition'] + country + category['id'], seen)
                groups.append({**{k: category[k] for k in ('id', 'en', 'ar')},
                               'status': result['status'], 'items': rows})
            return {**{k: plan[k] for k in ('edition', 'interval_seconds', 'theme')},
                    'country': country, 'generated_at': int(self.clock()),
                    'delivery': 'live', 'cacheable': False, 'groups': groups}
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self.inflight -= 1


def install_discover(app, countries):
    # Separate admission/concurrency from the primary text and Lens pipelines.
    discovery = Discovery(ShopifyCatalog(countries), countries)

    @app.get('/api/discover/config')
    async def config():
        return JSONResponse({'countries': {str(k).upper(): v for k, v in countries.items()},
                             'interval_seconds': EDITION_SECONDS}, headers=HEADERS)

    @app.get('/api/discover/trial')
    async def trial(request: Request):
        country = str(request.query_params.get('country', 'KW')).upper()
        lang = 'ar' if request.query_params.get('lang') == 'ar' else 'en'
        query = re.sub(r'[\x00-\x1f]', '', request.query_params.get('q', '')).strip()[:120]
        if country not in discovery.catalog.countries:
            return JSONResponse({'error': 'unsupported_country'}, status_code=400, headers=HEADERS)
        # ASGI's trusted proxy configuration owns client identity; never trust a
        # client-supplied forwarding header here.
        client = request.client.host if request.client else 'unknown'
        if not discovery.admit(client):
            return JSONResponse({'error': 'busy'}, status_code=429,
                                headers={**HEADERS, 'Retry-After': '60'})
        result = await discovery.feed(country, lang, query)
        return JSONResponse(result, headers=HEADERS)

    return discovery
