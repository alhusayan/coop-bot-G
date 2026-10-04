"""Offline cost regressions: provider requests are mocked, never charged."""
import contextlib
import copy
import importlib
import io
import json
import os
import socket
import tempfile
import threading
import time
import unittest
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, Mock

import requests
from findzia_searchapi import SerperTransport


class ProviderResponse:
    status_code = 200
    def __init__(self, events=(), error=None, data=None):
        self.events, self.error, self.data = events, error, data
        self.closed = False
    def iter_lines(self, **kwargs):
        for event in self.events:
            yield 'data: ' + json.dumps(event)
            yield ''
        if self.error:
            raise self.error
    def json(self):
        return self.data
    def close(self):
        self.closed = True


class CostOptimizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.env = patch.dict(os.environ, {'SEARCHAPI_API_KEY': 'test',
            'SERPER_API_KEY': 'serper-secret', 'SERPAPI_API_KEY': 'test',
            'GEMINI_API_KEY': 'gemini-secret', 'CACHE_DB_PATH': cls.temp.name+'/test.sqlite',
            'FINDZIA_SOCIAL_ENABLED': 'false'}, clear=True)
        cls.env.start()
        cls.network = patch.object(socket.socket, 'connect', side_effect=AssertionError('Live network forbidden'))
        cls.http = patch.object(requests.sessions.Session, 'request', side_effect=AssertionError('Live HTTP forbidden'))
        cls.network.start(); cls.http.start()
        with contextlib.redirect_stdout(io.StringIO()):
            cls.m = importlib.import_module('main')

    @classmethod
    def tearDownClass(cls):
        cls.http.stop(); cls.network.stop(); cls.env.stop(); cls.temp.cleanup()

    def setUp(self):
        self.counts = Counter()
        def cost(k, n=1):
            self.counts[k] += n
        self.cost = patch.object(self.m, '_api_cost_record', cost)
        self.cost.start(); self.addCleanup(self.cost.stop)
        self.logs = io.StringIO()
        self.output = contextlib.redirect_stdout(self.logs)
        self.output.__enter__(); self.addCleanup(self.output.__exit__, None, None, None)

    def media(self, snap, *, failed=(), index_images=None, page_error=None):
        row = {'url': 'https://merchant.example/product/123456', 'country': 'sa',
               'title': 'Product 123456', '_failed_images': list(failed)}
        snap = dict({'url': row['url'], 'title': row['title'], 'is_product': True,
                     'page_fetch_status': 'ok'}, **snap)
        lookup = Mock(return_value={'media': {'page_image': (index_images or [''])[0],
                                            'image_candidates': index_images or []}})
        with patch.object(self.m, '_web_verified_page_snapshot', return_value=snap, side_effect=page_error), \
             patch.object(self.m, '_web_targeted_price_updates', lookup), \
             patch.object(self.m, '_web_public_image_url', lambda u: u):
            result = self.m._fz_recover_media(row)
        return result, lookup

    def test_fast_verified_page_avoids_all_paid_work(self):
        url = 'https://images.example/product123456-main.jpg'
        result, lookup = self.media({'product_image': url})
        self.assertIn(url, result['images'])
        lookup.assert_not_called()
        self.assertEqual(self.counts['media_index_avoided'], 1)

    def test_failed_primary_can_use_validated_page_alternate(self):
        old = 'https://images.example/product123456-old.jpg'
        alt = 'https://images.example/product123456-alt.jpg'
        result, lookup = self.media({'product_image': old, 'image_candidates': [old, alt]}, failed=[old])
        self.assertEqual(result['images'], [alt])
        lookup.assert_not_called()

    def test_all_page_images_failed_still_recovers_with_index(self):
        old = 'https://images.example/product123456-old.jpg'
        new = 'https://images.example/product123456-new.jpg'
        result, lookup = self.media({'product_image': old}, failed=[old], index_images=[new])
        self.assertEqual(result['images'], [new])
        self.assertEqual(lookup.call_count, 1)
        self.assertTrue(lookup.call_args.kwargs['image_only'])

    def test_unverified_page_cannot_supply_images(self):
        bad = 'https://images.example/unrelated-product.jpg'
        new = 'https://images.example/product123456-new.jpg'
        result, lookup = self.media({'is_product': False, 'product_image': bad,
                                    'image_candidates': [bad]}, index_images=[new])
        self.assertEqual(result['images'], [new])
        self.assertEqual(lookup.call_count, 1)

    def test_page_error_still_uses_one_index_fallback(self):
        new = 'https://images.example/product123456-new.jpg'
        result, lookup = self.media({}, page_error=RuntimeError('blocked'), index_images=[new])
        self.assertEqual(result['images'], [new])
        self.assertEqual(lookup.call_count, 1)

    def test_slow_page_does_not_block_index_recovery(self):
        gate = threading.Event()
        row = {'url': 'https://merchant.example/product/123456', 'country': 'sa', 'title': '123456'}
        new = 'https://images.example/product123456-new.jpg'
        def page(*a):
            gate.wait(1)
            return {}
        try:
            with patch.object(self.m, '_FZ_MEDIA_PAGE_GRACE', .01), \
                 patch.object(self.m, '_web_verified_page_snapshot', page), \
                 patch.object(self.m, '_web_targeted_price_updates', return_value={'media': {'page_image': new}}):
                began = time.monotonic()
                result = self.m._fz_recover_media(row)
                self.assertLess(time.monotonic()-began, .7)
                self.assertEqual(result['images'], [new])
        finally:
            gate.set()

    def test_recovery_cache_normalizes_exclusions_but_keeps_identity(self):
        row = {'url': 'https://merchant.example/product/123456?sku=red', 'title': 'Red',
               'country': 'sa', '_failed_images': ['https://i.example/a.jpg', 'https://i.example/b.jpg']}
        one = self.m._fz_media_cache_key(row)
        self.assertEqual(one, self.m._fz_media_cache_key(dict(row, _failed_images=[
            'https://i.example/b.jpg', 'https://i.example/a.jpg', 'https://i.example/a.jpg'])))
        for changes in ({'country': 'kw'}, {'title': 'Blue'},
                        {'url': 'https://merchant.example/product/123456?sku=blue'}):
            self.assertNotEqual(one, self.m._fz_media_cache_key(dict(row, **changes)))

    def test_requested_size_reaches_transport_and_general_search_stays_twenty(self):
        bodies = []
        def search(kind, body, timeout, fetch, normalize, **kw):
            bodies.append(body)
            return {'organic_results': []}
        with patch.object(self.m._HYBRID_SERPER, 'search', search):
            self.m._fast_provider_search('serper_search', 'model X123 store', 'sa', 'ar', 4,
                                         num=10, purpose='shopping_link')
            self.m._fast_provider_search('serper_search', 'model X123', 'sa', 'ar', 4)
        self.assertEqual([b['num'] for b in bodies], [10, 20])
        self.assertTrue(all(b['gl'] == 'sa' and b['hl'] == 'ar' for b in bodies))
        self.assertTrue(all('_purpose' not in b for b in bodies))

    def test_shopping_link_lookup_uses_ten_and_preserves_matching_evidence(self):
        card = {'title': 'Product 123456', 'source': 'Merchant', 'price': 'SAR 100', 'currency': 'SAR'}
        raw = {'title': card['title'], 'link': 'https://merchant.example/product/123456'}
        with patch.object(self.m, '_fast_provider_search', return_value={'organic_results': [raw]}) as fetch, \
             patch.object(self.m, '_shopping_unit_merchant_matches', return_value=True), \
             patch.object(self.m, '_shopping_same_product', return_value=True):
            result = self.m._web_text_shopping_lookup(card, {'country': 'sa', 'hl': 'ar'},
                    time.monotonic()+4, threading.Event())
        self.assertEqual(fetch.call_args.kwargs, {'num': 10, 'purpose': 'shopping_link'})
        self.assertEqual(result['organic_results'][0]['price'], 'SAR 100')

    def test_serper_counts_reported_credits_by_phase_and_engine(self):
        response = ProviderResponse(data={'organic': [], 'credits': 2})
        with patch.object(requests, 'post', return_value=response) as post:
            self.m._serper_json('search', {'q': 'private product', 'num': 10, 'gl': 'sa', 'hl': 'ar'},
                                3, purpose='listing_price')
        self.assertEqual(self.counts['serper_listing_price_credits'], 2)
        self.assertEqual(self.counts['serper_search_credits'], 2)
        self.assertEqual(self.counts['serper_reported_credits'], 2)
        self.assertTrue(response.closed)
        self.assertNotIn('private product', self.logs.getvalue())
        self.assertNotIn('serper-secret', self.logs.getvalue())
        self.assertNotIn('purpose', post.call_args.kwargs['json'])

    def test_sse_cumulative_metadata_is_counted_once_even_without_candidates(self):
        response = ProviderResponse(events=[
            {'candidates': [{'content': {'parts': [{'text': '{}'}]}}],
             'usageMetadata': {'promptTokenCount': 1000, 'candidatesTokenCount': 1}},
            {'candidates': [{'finishReason': 'STOP'}], 'usageMetadata': {'promptTokenCount': 1000}},
            {'usageMetadata': {'promptTokenCount': 1000, 'candidatesTokenCount': 5,
              'thoughtsTokenCount': 2, 'cachedContentTokenCount': 200, 'totalTokenCount': 1007}}
        ])
        with patch.object(requests, 'post', return_value=response):
            data, error = self.m._web_identity_stream_response(
                'https://example.invalid/models/gemini-3.5-flash-lite:generateContent', {}, 3,
                lambda _: None, purpose='visual_audit')
        self.assertFalse(error)
        self.assertEqual(data['usageMetadata']['totalTokenCount'], 1007)
        self.assertEqual(self.counts['gemini_visual_audit_usage_reports'], 1)
        self.assertEqual(self.counts['gemini_visual_audit_reported_prompt_tokens'], 1000)
        self.assertEqual(self.counts['gemini_visual_audit_reported_output_tokens'], 5)
        self.assertEqual(self.counts['gemini_visual_audit_reported_thoughts_tokens'], 2)
        self.assertEqual(self.counts['gemini_visual_audit_reported_cached_tokens'], 200)
        self.assertEqual(self.counts['gemini_visual_audit_reported_total_tokens'], 1007)
        self.assertTrue(response.closed)

    def test_interrupted_sse_is_marked_incomplete_and_closed(self):
        response = ProviderResponse(events=[{'usageMetadata': {'promptTokenCount': 321}}],
                                    error=requests.Timeout('interrupted'))
        with patch.object(requests, 'post', return_value=response), self.assertRaises(requests.Timeout):
            self.m._web_identity_stream_response('https://example.invalid/models/test:generateContent',
                                                 {}, 3, lambda _: None, purpose='photo_identity')
        self.assertEqual(self.counts['gemini_photo_identity_usage_incomplete'], 1)
        self.assertEqual(self.counts['gemini_photo_identity_reported_prompt_tokens'], 321)
        self.assertTrue(response.closed)

    def test_missing_usage_and_invalid_values_are_not_zero_bills(self):
        self.m._gemini_usage_record({}, 'refinement', 'test')
        self.m._gemini_usage_record({'usageMetadata': {'promptTokenCount': True,
            'candidatesTokenCount': -10, 'totalTokenCount': '100'}}, 'refinement', 'test')
        self.assertEqual(self.counts['gemini_refinement_usage_missing'], 2)
        self.assertNotIn('gemini_refinement_reported_total_tokens', self.counts)
        self.assertNotIn('gemini_refinement_reported_output_tokens', self.counts)


class WiderCacheTests(unittest.TestCase):
    def setUp(self):
        self.cache, self.calls, self.counts = {}, [], Counter()
        def put(key, engine, data, **kw):
            self.cache[key] = copy.deepcopy(data)
        def cost(key, n=1):
            self.counts[key] += n
        self.transport = SerperTransport(cache_get=self.cache.get, cache_put=put, cost=cost)
        self.addCleanup(self.transport.pool.pool.shutdown)
        self.base = {'q': 'product 123456 merchant', 'gl': 'sa', 'hl': 'ar', 'num': 20}

    def fetch(self, kind, body, timeout):
        self.calls.append(dict(body))
        return {'organic': [{'title': str(i)} for i in range(body['num'])]}

    def search(self, body, fetch=None, bypass=False):
        return self.transport.search('search', body, 2, fetch or self.fetch,
            lambda kind, raw: {'organic_results': raw['organic']}, bypass=bypass)

    def test_narrow_lookup_reuses_paid_twenty_without_truncating_evidence(self):
        original = self.search(self.base)
        narrow = self.search(dict(self.base, num=10))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(narrow, original)
        self.assertEqual(self.counts['serper_wider_cache_hits'], 1)
        narrow['organic_results'].clear()
        self.assertEqual(len(self.search(self.base)['organic_results']), 20)

    def test_narrow_inflight_shares_broader_paid_work(self):
        entered, release = threading.Event(), threading.Event()
        def slow(kind, body, timeout):
            entered.set()
            release.wait(1)
            return self.fetch(kind, body, timeout)
        with ThreadPoolExecutor(max_workers=2) as pool:
            wide = pool.submit(self.search, self.base, slow)
            self.assertTrue(entered.wait(1))
            narrow = pool.submit(self.search, dict(self.base, num=10), slow)
            until = time.monotonic()+1
            while not self.counts['serper_wider_shared_responses'] and time.monotonic() < until:
                time.sleep(.001)
            release.set()
            self.assertEqual(wide.result(), narrow.result())
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.counts['serper_wider_shared_responses'], 1)

    def test_different_market_language_variant_and_page_are_separate(self):
        self.search(self.base)
        variants = [{'gl': 'kw'}, {'hl': 'en'}, {'q': 'product 654321 merchant'},
                    {'page': 2}, {'autocorrect': False}, {'location': 'Riyadh'}]
        for change in variants:
            self.search(dict(self.base, num=10, **change))
        self.assertEqual(len(self.calls), 1+len(variants))

    def test_ten_never_satisfies_twenty_and_bypass_still_fetches(self):
        self.search(dict(self.base, num=10))
        twenty = self.search(self.base)
        self.assertEqual(len(twenty['organic_results']), 20)
        self.assertEqual(len(self.calls), 2)
        self.search(dict(self.base, num=10), bypass=True)
        self.assertEqual(len(self.calls), 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
