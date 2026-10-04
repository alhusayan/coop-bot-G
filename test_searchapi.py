import ast
import copy
import os
from pathlib import Path
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import requests
from findzia_searchapi import SearchApiRouter, normalize, searchapi_params

GOOD = {'organic_results': [{'title': 'Product', 'link': 'https://shop.example/product'}]}


class Response:
    def __init__(self, status=200, data=None):
        self.status_code, self.data, self.closed = status, data if data is not None else GOOD, False
    def json(self):
        if isinstance(self.data, Exception):
            raise self.data
        return copy.deepcopy(self.data)
    def close(self):
        self.closed = True


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'SEARCHAPI_API_KEY': 'primary-secret',
            'SERPAPI_API_KEY': 'backup-secret', 'SEARCHAPI_PRIMARY_ENABLED': 'true'}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.http, self.backups, self.events, self.logs = [], [], [], []
        self.cache = {}
        self.responses = []
        def get(url, **kwargs):
            self.http.append((url, kwargs))
            return self.responses.pop(0) if self.responses else Response()
        def put(key, engine, data, ttl_seconds=None):
            self.cache[key] = copy.deepcopy(data)
        self.router = SearchApiRouter(cache_get=self.cache.get, cache_put=put,
            cost=self.events.append, http_get=get, log=self.logs.append)
        self.addCleanup(self.router.primary_pool.pool.shutdown)
        self.addCleanup(self.router.backup_pool.pool.shutdown)
        self.params = {'engine': 'google', 'q': 'macbook', 'gl': 'kw', 'hl': 'ar', 'api_key': 'backup-secret'}

    def fallback(self, params, timeout, **kwargs):
        self.backups.append((params, timeout, kwargs))
        return GOOD

    def search(self, **kwargs):
        return self.router.search(self.params, 10, self.fallback, **kwargs)

    def test_primary_success_cache_credentials_and_no_backup(self):
        result = self.search()
        self.assertEqual(result['search_metadata']['provider'], 'searchapi')
        result['organic_results'].clear()
        self.assertEqual(len(self.search()['organic_results']), 1)
        self.assertEqual(len(self.http), 1)
        self.assertEqual(self.backups, [])
        args = self.http[0][1]
        self.assertEqual(args['headers'], {'Authorization': 'Bearer primary-secret'})
        self.assertNotIn('api_key', args['params'])
        self.assertFalse(args['allow_redirects'])
        self.assertGreaterEqual(args['timeout'][1], 6)
        self.assertEqual((args['params']['gl'], args['params']['hl']), ('kw', 'ar'))

    def test_errors_switch_once_without_retry(self):
        for status in (401, 402, 403, 429, 500, 502, 503, 504):
            with self.subTest(status=status):
                self.cache.clear(); self.router.circuits.clear()
                response = Response(status, {'error': 'primary-secret private-message'})
                self.responses.append(response)
                before = len(self.backups)
                result = self.search()
                self.assertEqual(len(self.backups), before+1)
                self.assertFalse(self.backups[-1][2]['retry_connect'])
                self.assertEqual(self.backups[-1][0]['api_key'], 'backup-secret')
                self.assertEqual(result['search_metadata']['provider'], 'serpapi')
                self.assertTrue(response.closed)
        self.assertNotIn('secret', ' '.join(self.logs))
        self.assertNotIn('private-message', ' '.join(self.logs))

    def test_malformed_and_body_error_switch(self):
        for data in (ValueError('invalid JSON'), [], {}, {'error': 'bad'}, {'search_metadata': {'status': 'Processing'}}):
            self.cache.clear(); self.router.circuits.clear()
            self.responses.append(Response(data=data))
            self.assertEqual(self.search()['search_metadata']['provider'], 'serpapi')

    def test_explicit_empty_is_not_outage(self):
        self.responses.append(Response(data={'organic_results': []}))
        self.assertEqual(self.search()['organic_results'], [])
        self.assertFalse(self.backups)

    def test_read_timeout_uses_rescue(self):
        self.router.get = lambda *a, **k: (_ for _ in ()).throw(requests.ReadTimeout())
        self.assertEqual(self.search()['search_metadata']['provider'], 'serpapi')
        self.assertEqual(len(self.backups), 1)

    def test_wall_deadline_does_not_wait_for_late_primary(self):
        self.router.threshold = .04
        release = threading.Event()
        self.addCleanup(release.set)
        def blocked(*a, **kw):
            release.wait(1)
            return Response(data={'organic_results': [{'title': 'LATE'}]})
        self.router.get = blocked
        started = time.monotonic()
        result = self.search()
        self.assertLess(time.monotonic()-started, .3)
        self.assertEqual(result['search_metadata']['provider'], 'serpapi')
        release.set()
        self.router.primary_pool.pool.shutdown(wait=True)
        self.assertEqual(self.search()['organic_results'][0]['title'], 'Product')

    def test_total_deadline_bounds_stalled_backup(self):
        self.router.threshold, self.router.total = .02, .12
        self.responses.append(Response(503))
        release = threading.Event()
        self.addCleanup(release.set)
        def fallback(*a, **kw):
            release.wait(1)
            return GOOD
        started = time.monotonic()
        self.assertIsNone(self.router.search(self.params, .12, fallback))
        self.assertLess(time.monotonic()-started, .3)
        release.set()

    def test_concurrent_identical_requests_share_primary_and_backup(self):
        entered, release = threading.Event(), threading.Event()
        def delayed(*a, **kw):
            entered.set(); release.wait(1)
            return Response(503)
        self.router.get = delayed
        with ThreadPoolExecutor(max_workers=8) as pool:
            leader = pool.submit(self.search)
            self.assertTrue(entered.wait(1))
            followers = [pool.submit(self.search) for _ in range(7)]
            deadline = time.monotonic()+1
            while self.events.count('searchapi_shared_responses') < 7 and time.monotonic()<deadline:
                threading.Event().wait(.002)
            release.set()
            for future in [leader]+followers:
                self.assertEqual(future.result()['search_metadata']['provider'], 'serpapi')
        self.assertEqual(self.events.count('searchapi_http_requests'), 1)
        self.assertEqual(len(self.backups), 1)

    def test_circuit_skips_primary_and_recovers(self):
        self.responses.append(Response(429))
        self.search()
        self.cache.clear()
        self.search()
        self.assertEqual(len(self.http), 1)
        self.assertIn('google', self.router.snapshot()['open_circuits'])
        self.cache.clear()
        self.router.circuits['google'] = (3, time.monotonic()-1)
        self.assertEqual(self.search()['search_metadata']['provider'], 'searchapi')

    def test_provider_tokens_stay_with_owner_and_rollback(self):
        params = {'engine': 'google_immersive_product', 'page_token': 'serp-owned'}
        self.router.search(params, 2, self.fallback)
        self.assertFalse(self.http)
        self.assertEqual(self.backups[-1][0], params)
        self.router.enabled = False
        self.search()
        self.assertFalse(self.http)

    def test_both_fail_returns_failure_only_when_requested(self):
        self.responses.append(Response(503))
        result = self.router.search(self.params, 2, lambda *a, **kw: {'error': 'failed'}, return_error=True)
        self.assertEqual(result['error'], 'search_providers_unavailable')
        self.assertEqual(self.cache, {})

    def test_no_cache_bypasses_saved_result(self):
        self.search()
        self.params['no_cache'] = True
        self.search()
        self.assertEqual(len(self.http), 2)


class SchemaTests(unittest.TestCase):
    def test_baidu_language_codes_and_shopping_light(self):
        out = searchapi_params({'engine': 'baidu', 'q': '手机', 'ct': 2, 'pn': 20, 'rn': 10})
        self.assertEqual(out['ct'], 1)
        self.assertEqual(out['page'], 3)
        self.assertEqual(searchapi_params({'engine': 'google_shopping_light', 'q': 'phone'})['engine'], 'google_shopping')

    def test_lens_mapping_and_currency(self):
        params = searchapi_params({'engine': 'google_lens', 'url': 'https://example.com/photo.jpg',
            'type': 'products', 'country': 'kw', 'hl': 'ar', 'q': 'black', 'auto_crop': True, 'api_key': 'secret'})
        self.assertEqual(params['search_type'], 'products')
        self.assertEqual(params['country'], 'kw')
        self.assertNotIn('api_key', params)
        self.assertNotIn('auto_crop', params)
        normalized = normalize({'visual_matches': [{'title': 'Tap', 'link': 'https://store.example/tap',
            'source': 'Store', 'image': {'link': 'https://store.example/tap.jpg'},
            'price': 'KWD 12.500', 'extracted_price': 12.5, 'currency': 'KWD', 'stock_information': 'In stock'}]}, 'google_lens')
        row = normalized['visual_matches'][0]
        self.assertEqual(row['image'], 'https://store.example/tap.jpg')
        self.assertEqual(row['price']['currency'], 'KWD')
        self.assertEqual(row['price']['extracted_value'], 12.5)
        self.assertTrue(row['in_stock'])

    def test_image_schema_matches_existing_parser(self):
        out = normalize({'images': [{'title': 'Shoe', 'source': {'name': 'Store', 'link': 'https://shop.example/shoe'},
            'original': {'link': 'https://shop.example/full.jpg', 'width': 1200}, 'thumbnail': 'https://shop.example/thumb.jpg'}]}, 'google_images')
        row = out['images_results'][0]
        self.assertEqual(row['link'], 'https://shop.example/shoe')
        self.assertEqual(row['original'], 'https://shop.example/full.jpg')
        self.assertEqual(row['source'], 'Store')

    def test_shopping_sale_installment_ads_and_group_fields(self):
        item = {'title': 'Phone', 'seller': 'Store', 'price': '$399 now', 'extracted_price': 399,
                'original_price': '$999', 'extracted_original_price': 999,
                'installment': {'cost_per_month': '$50/mo'}, 'product_token': 'searchapi-owned',
                'product_link': 'https://www.google.com/shopping/product/123'}
        data = normalize({'shopping_results': [item], 'shopping_ads': [dict(item, title='Ad')],
            'categorized_shopping_results': [{'shopping_results': [item]}]}, 'google_shopping')
        self.assertEqual(len(data['shopping_results']), 2)
        row = data['shopping_results'][0]
        self.assertEqual(row['price'], '$399 now')
        self.assertEqual(row['old_price'], '$999')
        self.assertNotIn('original_price', row)
        self.assertTrue(row['installments_description'])
        self.assertNotIn('immersive_product_page_token', row)
        self.assertEqual(row['source'], 'Store')
        self.assertEqual(data['categorized_shopping_results'][0]['shopping_results'][0]['source'], 'Store')

    def test_native_query_page_and_nfpr_preserved(self):
        out = searchapi_params({'engine': 'google', 'q': '黑色水龙头 site:taobao.com',
             'gl': 'cn', 'hl': 'zh-cn', 'start': 10, 'nfpr': 1, 'json_restrictor': 'x'})
        self.assertEqual(out['page'], 2)
        self.assertEqual(out['hl'], 'zh-cn')
        self.assertEqual(out['nfpr'], 1)
        self.assertNotIn('json_restrictor', out)


class MainIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(Path(__file__).with_name('main.py').read_text())
    def functions(self, *names, **context):
        nodes = [n for n in self.tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        self.assertEqual(len(nodes), len(names))
        exec(compile(ast.Module(body=nodes, type_ignores=[]), '<actual main functions>', 'exec'), context)
        return context

    def test_actual_fast_route_uses_primary_adapter(self):
        router = type('Router', (), {'enabled': True})()
        calls = []
        def request(params, timeout, **kw):
            calls.append(params)
            return {'search_metadata': {'provider': 'searchapi'}, 'organic_results': []}
        ns = self.functions('_fast_provider_search', _SEARCHAPI_ROUTER=router,
            _serpapi_cached_json=request, SERPAPI_API_KEY='backup', COUNTRY_NAMES={'kw': 'Kuwait'},
            _web_model_tokens_from_listing=lambda q: ['M3'])
        for kind, expected in [('search', 'google'), ('images', 'google_images'), ('shopping', 'google_shopping')]:
            data = ns['_fast_provider_search']('serper_'+kind, 'MacBook M3', 'kw', 'ar', 8, page=2)
            self.assertEqual(calls[-1]['engine'], expected)
            self.assertEqual(data['search_metadata']['provider'], 'searchapi')
        self.assertEqual(calls[0]['start'], 10)

    def test_actual_lens_collector_accepts_searchapi(self):
        ns = self.functions('_collect_lens_items', is_blocked_store=lambda *a: False,
            _web_offer_image_candidates=lambda row: [row['image']],
            _web_capture_listing_evidence=lambda *a: {})
        data = normalize({'visual_matches': [{'title': 'Tap', 'link': 'https://shop.example/tap',
            'source': 'Store', 'image': {'link': 'https://shop.example/tap.jpg'},
            'price': 'KWD 12.500', 'extracted_price': 12.5, 'currency': 'KWD'}]}, 'google_lens')
        rows = ns['_collect_lens_items'](data, [], set())
        self.assertEqual(rows[0]['currency'], 'KWD')
        self.assertEqual(rows[0]['price_value'], 12.5)
        self.assertEqual(rows[0]['image'], 'https://shop.example/tap.jpg')

    def test_shein_does_not_shorten_or_duplicate_primary(self):
        calls = []
        def fast(*args, **kw):
            calls.append(args)
            return {'organic_results': []}
        ns = self.functions('_web_shein_index_fetch', time=time,
            _SEARCHAPI_ROUTER=type('Router', (), {'enabled': True})(),
            _fast_provider_search=fast, _web_shein_product_id=lambda value: '')
        result = ns['_web_shein_index_fetch']({'engine': 'serper_search', 'q': 'dress site:shein.com',
                                              'gl': 'us', 'hl': 'en'}, 12)
        self.assertEqual(result['organic_results'], [])
        self.assertEqual(len(calls), 1)
        self.assertGreater(sum(calls[0][-1]), 11)


if __name__ == '__main__':
    unittest.main(verbosity=2)
