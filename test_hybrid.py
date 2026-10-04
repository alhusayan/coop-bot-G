"""Offline hybrid routing and billed-work regressions; all HTTP is mocked."""
import ast
import copy
import os
from pathlib import Path
import re
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.parse

import requests
from findzia_searchapi import SearchApiRouter, SerperTransport
from test_searchapi import Response

TREE = ast.parse(Path(__file__).with_name('main.py').read_text())


def actual(names, **context):
    selected = []
    for node in TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            selected.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in node.targets):
            selected.append(node)
    assert len(selected) == len(names), names
    exec(compile(ast.Module(body=selected, type_ignores=[]), '<actual main>', 'exec'), context)
    return context


class HybridTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {'SEARCHAPI_API_KEY': 'primary-test',
            'SERPAPI_API_KEY': 'backup-test', 'SERPER_API_KEY': 'serper-test'}, clear=True)
        env.start(); self.addCleanup(env.stop)
        self.calls, self.events, self.cache, self.ttls = [], Counter(), {}, []
        def put(key, engine, data, ttl_seconds=None):
            self.cache[key] = copy.deepcopy(data); self.ttls.append(ttl_seconds)
        def cost(event, count=1):
            self.events[event] += count
        self.transport = SerperTransport(cache_get=self.cache.get, cache_put=put, cost=cost)
        self.addCleanup(self.transport.pool.pool.shutdown)
        def get(url, **kw):
            self.calls.append(('searchapi', kw['params']))
            return Response(data={'visual_matches': []})
        self.router = SearchApiRouter(cache_get=self.cache.get, cache_put=put,
            cost=cost, http_get=get, log=lambda *a: None)
        self.addCleanup(self.router.primary_pool.pool.shutdown)
        self.addCleanup(self.router.backup_pool.pool.shutdown)
        def fetch(kind, body, timeout):
            self.calls.append(('serper', kind, body))
            return {dict(search='organic', images='images', shopping='shopping')[kind]: []}
        def backup(params, timeout, **kw):
            self.calls.append(('serpapi', params))
            return {'visual_matches': [], 'search_metadata': {'provider': 'serpapi'}}
        self.ns = actual({'_HYBRID_SERPER_ENGINES', '_hybrid_serper_request', '_serpapi_cached_json',
            '_fast_provider_search', '_fast_provider_supports_operators', '_serper_to_serpapi'},
            _HYBRID_SEARCH=True, _HYBRID_SERPER=self.transport, _SEARCHAPI_ROUTER=self.router,
            SERPER_API_KEY='serper-test', SERPAPI_API_KEY='backup-test', FAST_PROVIDER_NUM=20,
            COUNTRY_NAMES={'kw': 'Kuwait', 'us': 'United States', 'cn': 'China'},
            _FAST_PROVIDER_FLAGS={}, _web_model_tokens_from_listing=lambda q: ['M3'] if 'M3' in q else [],
            _serper_json=fetch, _serpapi_only_cached_json=backup, _api_cost_record=cost,
            print=lambda *a: None, re=re, urllib=urllib)

    def request(self, engine='google', **params):
        return self.ns['_serpapi_cached_json'](dict(engine=engine, q='vase', gl='kw', hl='ar', **params), 10)

    def test_all_index_aliases_share_serper_with_no_expensive_calls(self):
        for kind, engines in (('search', ('google', 'google_light', 'serper_search')),
                             ('images', ('google_images', 'google_images_light', 'serper_images')),
                             ('shopping', ('google_shopping', 'google_shopping_light', 'serper_shopping'))):
            for engine in engines:
                result = self.request(engine)
                self.assertEqual(result['search_metadata']['provider'], 'serper')
                self.assertIn(dict(search='organic_results', images='images_results', shopping='shopping_results')[kind], result)
        self.assertEqual([c[0] for c in self.calls], ['serper']*3)
        self.assertEqual(self.events['serper_cache_hits'], 6)
        self.assertEqual(self.ttls, [120]*3)

    def test_fast_lane_and_google_lane_share_same_body(self):
        self.ns['_fast_provider_search']('serper_search', 'vase', 'kw', 'ar', 6)
        self.request('google')
        self.assertEqual(len(self.calls), 1)

    def test_lens_primary_and_single_backup_on_failure(self):
        result = self.request('google_lens', url='https://images.example/a.jpg')
        self.assertEqual(result['search_metadata']['provider'], 'searchapi')
        self.assertEqual(self.router.threshold, 8)
        self.assertEqual(self.router.total, 18)
        def down(url, **kw):
            self.calls.append(('searchapi', kw['params'])); return Response(503)
        self.router.get = down
        result = self.request('google_lens', url='https://images.example/b.jpg')
        self.assertEqual(result['search_metadata']['provider'], 'serpapi')
        self.assertEqual([c[0] for c in self.calls], ['searchapi', 'searchapi', 'serpapi'])

    def test_specialist_tokens_and_native_baidu_keep_owner(self):
        for engine in ('baidu', 'google_immersive_product'):
            self.request(engine, page_token='opaque-owned-token')
        self.assertEqual([c[0] for c in self.calls], ['serpapi', 'serpapi'])

    def test_missing_key_operator_rejection_and_empty_query_do_not_buy_fallback(self):
        self.ns['SERPER_API_KEY'] = ''
        self.assertIsNone(self.request())
        self.ns['SERPER_API_KEY'] = 'serper-test'
        self.ns['_FAST_PROVIDER_FLAGS']['serper_no_operators'] = True
        for q in ('vase site:shop.example', ''):
            result = self.ns['_serpapi_cached_json']({'engine': 'google', 'q': q}, 8, return_error=True)
            self.assertIn('_serpapi_failure', result)
        self.assertEqual(self.calls, [])

    def test_serper_error_does_not_trigger_searchapi_or_serpapi(self):
        self.ns['_serper_json'] = lambda *a: {'error': 'unavailable'}
        self.assertIsNone(self.request())
        self.assertEqual(self.calls, [])
        self.assertEqual(self.cache, {})

    def test_request_mapping_keeps_language_page_location_and_model(self):
        self.ns['_serpapi_cached_json']({'engine': 'google_light', 'q': 'حاسب M3', 'gl': 'kw', 'hl': 'ar',
            'start': 10, 'num': 10, 'nfpr': 1, 'api_key': 'never-forward', 'json_restrictor': 'never-forward'}, 8)
        body = self.calls[0][2]
        self.assertEqual(body, {'q': 'حاسب M3', 'gl': 'kw', 'hl': 'ar', 'page': 2,
            'num': 10, 'location': 'Kuwait', 'autocorrect': False})
        self.request('google_images')
        self.assertNotIn('location', self.calls[-1][2])

    def test_distinct_market_language_page_and_num_are_not_coalesced(self):
        base = dict(engine='google', q='vase', gl='kw', hl='ar')
        for extra in ({}, {'gl': 'us'}, {'hl': 'en'}, {'page': 2}, {'num': 10}):
            self.ns['_serpapi_cached_json'](dict(base, **extra), 8)
        self.assertEqual(len(self.calls), 5)

    def test_parallel_aliases_share_one_physical_request(self):
        entered, release = threading.Event(), threading.Event()
        def slow(kind, body, timeout):
            self.calls.append(('serper', kind, body)); entered.set(); release.wait(2)
            return {'organic': [{'title': 'Vase', 'link': 'https://shop.example/vase'}]}
        self.ns['_serper_json'] = slow
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(self.request, ('google', 'google_light', 'serper_search')[i%3]) for i in range(8)]
            self.assertTrue(entered.wait(1))
            deadline = time.monotonic()+1
            while self.events['serper_shared_responses'] < 7 and time.monotonic() < deadline:
                time.sleep(.005)
            release.set()
            results = [f.result() for f in futures]
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.events['serper_shared_responses'], 7)
        results[0]['organic_results'].clear()
        self.assertEqual(len(results[1]['organic_results']), 1)

    def test_timeout_retains_paid_work_for_next_caller(self):
        release = threading.Event()
        def slow(kind, body, timeout):
            self.calls.append(('serper', kind, body)); release.wait(1); return {'organic': []}
        self.ns['_serper_json'] = slow
        params = dict(engine='google', q='vase')
        self.assertIsNone(self.ns['_serpapi_cached_json'](params, .04))
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(self.ns['_serpapi_cached_json'], params, 1)
            release.set()
            self.assertIsInstance(pending.result(), dict)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.events['serper_wait_timeouts'], 1)

    def test_no_cache_really_bypasses_cache(self):
        self.request(); self.request(no_cache=True); self.request(no_cache='true')
        self.assertEqual(len(self.calls), 3)

    def test_rollback_restores_previous_routing(self):
        self.ns['_HYBRID_SEARCH'] = False
        self.router.get = lambda *a, **kw: Response(data={'organic_results': []})
        self.assertEqual(self.request()['search_metadata']['provider'], 'searchapi')
        self.router.enabled = False
        self.assertEqual(self.request()['search_metadata']['provider'], 'serpapi')

    def test_serper_price_and_image_fields_survive_adapter(self):
        self.ns['_fast_price_number'] = lambda value, currency: 12.5
        self.ns['_serper_json'] = lambda kind, *a: {'shopping': [{'title': 'Tap',
            'link': 'https://shop.example/tap', 'source': 'Shop', 'imageUrl': 'https://shop.example/tap.jpg',
            'price': 'KWD 12.500', 'currency': 'KWD', 'old_price': 'KWD 15.000', 'in_stock': True}]}
        row = self.request('google_shopping')['shopping_results'][0]
        self.assertEqual((row['extracted_price'], row['currency'], row['old_price']), (12.5, 'KWD', 'KWD 15.000'))
        self.assertEqual(row['thumbnail'], 'https://shop.example/tap.jpg')
        self.assertTrue(row['in_stock'])
        self.ns['_serper_json'] = lambda *a: {'images': [{'title': 'Tap', 'link': 'https://shop.example/tap',
            'imageUrl': 'https://shop.example/tap.jpg', 'thumbnailUrl': 'https://shop.example/small.jpg'}]}
        row = self.request('google_images')['images_results'][0]
        self.assertEqual(row['original'], 'https://shop.example/tap.jpg')
        self.assertEqual(row['thumbnail'], 'https://shop.example/small.jpg')


class HttpAccountingTests(unittest.TestCase):
    def test_actual_http_records_provider_credits_and_closes_bad_json(self):
        events, logs = Counter(), []
        def cost(k, n=1): events[k] += n
        ns = actual({'_serper_json'}, time=time, re=re, requests=requests,
            SERPER_API_KEY='serper-test', _FAST_PROVIDER_FLAGS={}, _api_cost_record=cost, print=logs.append)
        good = Response(data={'organic': [], 'credits': 2})
        bad = Response(data=ValueError('bad json'))
        denied = Response(400, {'message': 'pattern not allowed serper-test https://secret.example'})
        with patch.object(requests, 'post', side_effect=[good, bad, denied]) as post:
            self.assertEqual(ns['_serper_json']('search', {'q': 'vase'}, 6)['credits'], 2)
            self.assertIsNone(ns['_serper_json']('images', {'q': 'vase'}, 6))
            self.assertIsNone(ns['_serper_json']('search', {'q': 'site:shop.example vase'}, 6))
        self.assertEqual(post.call_count, 3)
        self.assertEqual(events['serper_http_requests'], 3)
        self.assertEqual(events['serper_http_200'], 1)
        self.assertEqual(events['serper_reported_credits'], 2)
        self.assertTrue(all(r.closed for r in (good, bad, denied)))
        self.assertTrue(ns['_FAST_PROVIDER_FLAGS']['serper_no_operators'])
        self.assertNotIn('serper-test', str(logs))
        self.assertNotIn('secret.example', str(logs))


class PlannerTests(unittest.TestCase):
    def test_bilingual_local_and_global_coverage_without_duplicate_shopping(self):
        ns = actual({'_web_text_direct_specs', '_web_preferred_text_specs', '_searchapi_global_catalog_kinds'},
            _HYBRID_SEARCH=True, _SEARCHAPI_ROUTER=SimpleNamespace(enabled=True, economy=True),
            _market_query_languages=lambda cc, q: ['en', {'kw': 'ar', 'cn': 'zh-cn', 'us': 'en'}[cc]],
            serpapi_provider_degraded=lambda: False, current_market=lambda: {}, serper_primary=lambda: True,
            FAST_PROVIDERS=['serper'], SEARCH_PROVIDER_PRIMARY='serper', FAST_PROVIDER_IMAGES=True,
            FAST_PROVIDER_SHOPPING=True, SERPAPI_API_KEY='test', LOCAL_DISCOVERY_BAIDU=True,
            _fast_provider_supports_operators=lambda p: True, _fz_local_store_lanes=lambda *a: [],
            _fz_search_variants=lambda q: [], TEXT_DIRECT_IMAGES_ENGINE='google_images_light',
            DEFAULT_GLOBAL_COUNTRIES=['us', 'cn'], GLOBAL_MARKET_STORES={
                'us': [('Amazon', 'amazon.com')], 'cn': [('AliExpress', 'aliexpress.com'),
                ('Temu', 'temu.com'), ('SHEIN', 'shein.com'), ('Alibaba', 'alibaba.com')]})
        for fn in ('_web_text_direct_specs', '_web_preferred_text_specs'):
            specs = ns[fn]('vase', 'kw')
            local = [s for s in specs if s['role'] == 'local']
            for kind in ('serper_search', 'serper_images'):
                self.assertEqual({s['hl'] for s in local if s['engine'] == kind}, {'en', 'ar'})
            self.assertIn('serper_shopping', [s['engine'] for s in local])
            self.assertEqual({s['country'] for s in specs if s['role'] == 'global'}, {'us', 'cn'})
            specs = ns[fn]('vase', 'us')
            self.assertNotIn('google_shopping', [s['engine'] for s in specs])
        self.assertEqual(len(ns['_searchapi_global_catalog_kinds']('cn')), 4)


if __name__ == '__main__':
    unittest.main(verbosity=2)
