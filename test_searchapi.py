import ast
import copy
import os
from pathlib import Path
import threading
import time
import re
import urllib.parse
from types import SimpleNamespace
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
        self.assertEqual(self.router.threshold, 8)
        self.assertGreaterEqual(args['timeout'][1], 8)
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
        self.assertEqual(self.search()['organic_results'][0]['title'], 'LATE')
        self.assertIn('searchapi_late_cached', self.events)

    def test_total_deadline_bounds_stalled_backup(self):
        self.router.threshold, self.router.total, self.router.backup_min = .02, .12, .01
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


    def test_eight_seconds_is_configurable_above_old_cap(self):
        with patch.dict(os.environ, {'SEARCHAPI_FALLBACK_AFTER_SECONDS': '9'}):
            router = SearchApiRouter(cache_get=self.cache.get, cache_put=lambda *a, **k: None,
                                     cost=self.events.append, log=self.logs.append)
        self.addCleanup(router.primary_pool.pool.shutdown)
        self.addCleanup(router.backup_pool.pool.shutdown)
        self.assertEqual(router.threshold, 9)

    def test_short_tasks_keep_primary_time_and_do_not_damage_health(self):
        waits = []
        def primary(params, seconds):
            waits.append(seconds)
            return None, 'timeout', 0
        self.router._primary = primary
        for _ in range(4):
            self.assertIsNone(self.router.search(self.params, 2, self.fallback))
        self.assertTrue(all(1.9 < seconds <= 2 for seconds in waits))
        self.assertFalse(self.backups)
        self.assertFalse(self.router.snapshot()['open_circuits'])

    def test_invalid_request_does_not_buy_backup_or_open_circuit(self):
        for _ in range(4):
            self.responses.append(Response(400))
            self.assertIsNone(self.search())
        self.assertFalse(self.backups)
        self.assertFalse(self.router.snapshot()['open_circuits'])

    def test_late_primary_reused_without_another_http_request(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        calls = []
        def get(*args, **kwargs):
            calls.append(1); entered.set(); release.wait(1)
            return Response()
        self.router.get = get
        self.router.threshold = .03
        self.assertIsNone(self.router.search(self.params, .04, self.fallback))
        self.router.threshold = .3
        with ThreadPoolExecutor(max_workers=1) as pool:
            second = pool.submit(self.search)
            limit = time.monotonic()+1
            while 'searchapi_late_reused' not in self.events and time.monotonic()<limit:
                threading.Event().wait(.002)
            release.set()
            self.assertEqual(second.result()['search_metadata']['provider'], 'searchapi')
        self.assertEqual(len(calls), 1)
        self.assertFalse(self.backups)
        self.assertEqual(self.events.count('searchapi_http_200'), 1)

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
        context.setdefault('_HYBRID_SEARCH', False)  # Legacy all-SearchApi mode coverage.
        context.setdefault('time', time)
        context.setdefault('_fast_provider_timeouts', lambda engine, remaining: (1, max(.01, remaining-1)))
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
            _web_model_tokens_from_listing=lambda q: ['M3'], _shopping_gl_supported=lambda cc: True)
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


    def test_unsupported_shopping_is_skipped_before_paid_transport(self):
        ns = self.functions('_fast_provider_search',
            _SEARCHAPI_ROUTER=SimpleNamespace(enabled=True),
            _shopping_gl_supported=lambda cc: cc != 'kw',
            _log_unsupported_shopping_gl=lambda cc: None)
        result = ns['_fast_provider_search']('serper_shopping', 'vase', 'kw', 'ar', 10)
        self.assertEqual(result['shopping_results'], [])
        self.assertEqual(result['search_metadata']['skipped'], 'unsupported_market')

    def test_china_plan_keeps_two_languages_and_shein_images(self):
        router = SimpleNamespace(enabled=True, economy=True)
        ns = self.functions('_searchapi_global_catalog_kinds', _SEARCHAPI_ROUTER=router)
        kinds = ns['_searchapi_global_catalog_kinds']('cn')
        self.assertEqual(len(kinds), 4)
        self.assertIn('global_fast::en', kinds)
        self.assertIn('global_fast::zh-cn', kinds)
        self.assertIn('global_fast_images:shein.com:en', kinds)
        self.assertIn('global_fast_images:shein.com:zh-cn', kinds)
        self.assertIsNone(ns['_searchapi_global_catalog_kinds']('us'))
        router.economy = False
        self.assertIsNone(ns['_searchapi_global_catalog_kinds']('cn'))

    def test_china_grouped_query_keeps_all_approved_stores(self):
        calls = []
        stores = (('AliExpress','aliexpress.com'),('Temu','temu.com'),('SHEIN','shein.com'),('Alibaba','alibaba.com'))
        def fast(*args):
            calls.append(args)
            return {'organic_results': []}
        ns = self.functions('_global_discovery_request', GLOBAL_MARKET_STORES={'cn': stores},
            FAST_PROVIDERS=['serper'], _fast_provider_supports_operators=lambda p: True,
            _web_market=lambda cc: {'country':cc}, _web_catalog_scope=lambda d: 'site:'+d,
            _market_query_wait=lambda *a: None, _market_query_cached=lambda *a: None,
            _market_query_static=lambda q, hl: {'query': '花瓶' if hl=='zh-cn' else 'vase'},
            _fast_provider_search=fast, TEXT_DIRECT_TRANSLATION_WAIT=1,
            FAST_PROVIDER_TIMEOUT_SECONDS=8, _local_discovery_rows=lambda *a: [])
        for hl in ('en', 'zh-cn'):
            ns['_global_discovery_request']('vase', 'cn', 'global_fast::'+hl, 12)
        self.assertEqual(len(calls), 2)
        for call in calls:
            for _, domain in stores:
                self.assertIn('site:'+domain, call[1])
        self.assertEqual(calls[0][3], 'en')
        self.assertEqual(calls[1][3], 'zh-cn')
        self.assertIn('花瓶', calls[1][1])

    def test_recovery_batches_four_listings_into_one_paid_query(self):
        calls=[]
        router=SimpleNamespace(enabled=True,economy=True)
        ns = self.functions('_web_targeted_price_updates', re=re, urllib=urllib,
            ThreadPoolExecutor=ThreadPoolExecutor, MARKET_CTX=SimpleNamespace(),
            _SEARCHAPI_ROUTER=router, FINDZIA_GROUPED_RECOVERY_ENABLED=True, _indexed_recovery_allowed=lambda: True,
            _web_price_url_key=lambda url:url, _web_shein_product_id=lambda url:'',
            _global_store_match=lambda *a:False, _web_row_has_numeric_price=lambda row:False,
            country_search_hl=lambda cc:'ar', SERPAPI_API_KEY='fake', WEB_LIVE_PRICE_WAIT=10,
            FAST_PROVIDERS=['serper'], _fast_provider_supports_operators=lambda p:True,
            _fast_provider_search=lambda *a: calls.append(a) or {},
            _web_indexed_media_records=lambda d:[])
        entries={str(i):{'url':f'https://shop.example/product/{123456+i}',
                 'title':f'Vase {i}', 'country':'kw'} for i in range(4)}
        self.assertEqual(ns['_web_targeted_price_updates'](entries,'ar',{'country':'kw'}),{})
        self.assertEqual(len(calls),1)
        self.assertTrue(all(str(123456+i) in calls[0][1] for i in range(4)))
        self.assertIn(' OR ',calls[0][1])
        router.economy=False;calls.clear()
        ns['_web_targeted_price_updates'](entries,'ar',{'country':'kw'})
        self.assertEqual(len(calls),4)

if __name__ == '__main__':
    unittest.main(verbosity=2)
