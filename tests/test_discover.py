import asyncio
import unittest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from findzia_discover import Discovery, recipe, select_rows, install_discover


def row(i, store='shop.test'):
    return {'url': f'https://{store}/products/{i}', 'image': f'https://{store}/{i}.jpg',
            'title': f'Product {i}', 'store': store, 'money': {'value': '12.500', 'currency': 'KWD'},
            'source': 'shopify_catalog', 'cacheable': False}


class FakeCatalog:
    countries = frozenset(('KW', 'JP'))

    def __init__(self):
        self.calls = []

    async def _search(self, query, country, lang):
        self.calls.append((query, country, lang))
        await asyncio.sleep(0)
        return {'status': 'ok', 'items': [row(query + str(i), f'store{i % 4}.test') for i in range(12)]}


class DiscoveryTests(unittest.IsolatedAsyncioTestCase):
    def test_editions_are_stable_until_ten_minute_boundary(self):
        self.assertEqual(recipe(601), recipe(1199))
        a, b = recipe(1199), recipe(1200)
        self.assertNotEqual(a['edition'], b['edition'])
        self.assertTrue(all(x['query'] != y['query'] for x, y in zip(a['categories'], b['categories'])))

    def test_diversity_dedup_and_prices(self):
        items = [row(i) for i in range(8)] + [row(1, 'other.test')]
        seen = set()
        chosen = select_rows(items, 'seed', seen)
        self.assertEqual(len(chosen), 3)
        self.assertTrue(set(r['url'] for r in chosen).isdisjoint(r['url'] for r in select_rows(items, 'seed', seen)))
        self.assertTrue(all(r['money']['value'] == '12.500' for r in chosen))

    async def test_every_visit_is_live_no_retained_product_snapshot(self):
        catalog = FakeCatalog()
        discovery = Discovery(catalog, {'KW': 'Kuwait'}, clock=lambda: 1200)
        first = await discovery.feed('KW', 'en')
        second = await discovery.feed('KW', 'en')
        self.assertEqual(len(catalog.calls), 12)
        self.assertEqual(first['edition'], second['edition'])
        self.assertEqual(len(first['groups']), 6)
        urls = [r['url'] for g in first['groups'] for r in g['items']]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertFalse(first['cacheable'])
        self.assertEqual(discovery.inflight, 0)
        self.assertFalse(any('groups' in k or 'cache' in k or 'items' in k for k in vars(discovery)))

    async def test_one_category_failure_keeps_other_collections(self):
        catalog = FakeCatalog()
        search = catalog._search
        async def fail(query, country, lang):
            if query == recipe(1200)['categories'][0]['query']:
                raise ValueError('provider unavailable')
            return await search(query, country, lang)
        catalog._search = fail
        feed = await Discovery(catalog, {}, clock=lambda: 1200).feed('KW', 'ar')
        self.assertEqual(feed['groups'][0]['status'], 'provider_error')
        self.assertEqual(sum(bool(g['items']) for g in feed['groups']), 5)

    async def test_routes_validate_country_no_store_and_limit_requests(self):
        app = FastAPI()
        discovery = install_discover(app, {'kw': 'Kuwait', 'jp': 'Japan'})
        discovery.catalog = FakeCatalog()
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
            config = await client.get('/api/discover/config')
            self.assertEqual(config.json()['countries'], {'KW': 'Kuwait', 'JP': 'Japan'})
            response = await client.get('/api/discover/trial?country=ZZ')
            self.assertEqual(response.status_code, 400)
            for i in range(8):
                response = await client.get('/api/discover/trial?country=JP&q=headphones')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['country'], 'JP')
                self.assertEqual(len(response.json()['groups']), 1)
                self.assertIn('no-store', response.headers['cache-control'])
            self.assertEqual(len(discovery.catalog.calls), 8)
            self.assertEqual((await client.get('/api/discover/trial')).status_code, 429)

    async def test_cancellation_releases_admission_and_tasks(self):
        catalog = FakeCatalog()
        stopped = []
        async def slow(*args):
            try:
                await asyncio.sleep(60)
            finally:
                stopped.append(True)
        catalog._search = slow
        discovery = Discovery(catalog, {})
        task = asyncio.create_task(discovery.feed('KW', 'en'))
        await asyncio.sleep(.01)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(discovery.inflight, 0)
        self.assertEqual(len(stopped), 6)


if __name__ == '__main__':
    unittest.main()
