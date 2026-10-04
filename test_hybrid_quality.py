"""Offline regressions for the three searches in the 2026-10-04 production log.

Fixtures are synthetic examples of the observed failures, not captured provider
responses. Network is blocked; these tests cannot measure live result quality.
"""
import contextlib
import importlib
import io
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.parse

import requests


class QualityRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='findzia-quality-')
        cls.env = patch.dict(os.environ, {'SEARCHAPI_API_KEY': 'test', 'SERPAPI_API_KEY': 'test',
            'SERPER_API_KEY': 'test', 'CACHE_DB_PATH': cls.temp.name+'/test.sqlite'}, clear=True)
        cls.env.start()
        cls.http = patch.object(requests.sessions.Session, 'request', side_effect=AssertionError('Unexpected live HTTP'))
        cls.net = patch.object(socket.socket, 'connect', side_effect=AssertionError('Unexpected live network'))
        cls.http.start(); cls.net.start()
        with contextlib.redirect_stdout(io.StringIO()):
            cls.m = importlib.import_module('main')

    @classmethod
    def tearDownClass(cls):
        cls.net.stop(); cls.http.stop(); cls.env.stop(); cls.temp.cleanup()

    def test_ds2b_title_does_not_invent_a_model_or_variant(self):
        ref = {'brand': 'Casio', 'model': 'DS-2B', 'identifiers': ['DS-2B']}
        for title in ('CASIO Calculator DS-2B', 'Casio DS2B Calculator', 'CASIO DS 2B calculator'):
            with self.subTest(title=title):
                candidate = self.m._web_enrich_candidate_profile_from_text(dict(ref), title)
                axes = self.m._web_visual_profile_states(ref, candidate)
                self.assertEqual(axes['model'], 'same')
                self.assertEqual(axes['alphanumeric_identity'], 'same')
                self.assertNotIn('variant', candidate)
                self.assertEqual(candidate['model'], 'ds2b')

    def test_actual_changed_models_stay_different(self):
        ref = {'brand': 'Casio', 'model': 'DS-2B', 'identifiers': ['DS-2B']}
        for title in ('CASIO JS-40B calculator', 'CASIO DS-1B calculator', 'CASIO DS-2B-GD-W-DH calculator'):
            with self.subTest(title=title):
                candidate = self.m._web_enrich_candidate_profile_from_text(dict(ref), title)
                axes = self.m._web_visual_profile_states(ref, candidate)
                self.assertEqual(axes['model'], 'different')
        self.assertEqual(self.m._web_profile_model_state('iPhone 16', 'iPhone 17'), 'different')
        self.assertNotEqual(self.m._web_profile_model_state('Galaxy S24', 'Galaxy S24 Ultra'), 'same')

    def test_complete_multiple_codes_and_namespaces_remain_distinct(self):
        self.assertEqual(self.m._web_identity_model_codes('DS-2B / JS-40B'), {'ds2b', 'js40b'})
        self.assertEqual(self.m._web_identity_model_codes('DS-2B-GD-W-DH'), {'ds2bgdwdh'})
        self.assertEqual(self.m._web_identity_model_codes('DS-2B / 2B'), {'ds2b', '2b'})
        axes = self.m._web_visual_profile_states(
            {'model': 'DS-2B', 'identifiers': ['EAN: 1234567890123']},
            {'model': 'DS2B', 'identifiers': ['EAN: 1234567890124']})
        self.assertEqual(axes['alphanumeric_identity'], 'different')

    def test_logi_brand_and_generic_description_do_not_empty_lens(self):
        ref = {'brand': 'Logi', 'product_name': 'Logi wireless mouse', 'product_type': 'computer mouse',
               'named': True, 'query': 'logi wireless mouse'}
        rows = [{'title': title, 'link': 'https://www.ebay.co.uk/itm/'+str(123456789012+i),
                 'thumbnail': 'https://images.example/mouse.jpg'} for i, title in enumerate(
                    ['Logitech M185 Wireless Mouse', 'Logitech MX Anywhere 2S Bluetooth Mouse'])]
        result = self.m._lens_reference_rows(rows, ref)
        self.assertEqual(len(result), 2)
        self.assertFalse(any(row.get('exact') for row in result))
        axes = self.m._web_visual_profile_states({'brand': 'Logi'}, {'brand': 'Logitech'})
        self.assertEqual(axes['brand'], 'same')
        self.assertEqual(self.m._web_visual_profile_states({'brand': 'Logi'}, {'brand': 'Microsoft'})['brand'], 'different')

    def test_uncertain_lens_rows_reach_review_even_with_named_candidates(self):
        ref = {'brand': 'Casio', 'model': 'DS-2B', 'product_name': '', 'product_type': 'calculator',
               'named': True, 'query': 'Casio DS-2B calculator'}
        rows = [{'title': title, 'link': 'https://www.ebay.co.uk/itm/'+str(123456789012+i),
                 'thumbnail': 'https://images.example/calculator.jpg'} for i, title in enumerate(
                    ['Casio DS-2B Calculator', 'Desktop calculator', 'Computer keyboard'])]
        result = self.m._lens_reference_rows(rows, ref)
        self.assertEqual(len(result), 2)
        self.assertTrue(result[1]['_reference_fallback'])
        self.assertFalse(result[1].get('exact'))
        self.assertFalse(self.m._lens_reference_fallback_eligible(rows[2], ref))

    def test_different_named_product_line_is_still_guarded(self):
        ref = {'brand': 'Rolex', 'product_name': 'Daytona', 'product_type': 'watch', 'named': True}
        row = {'title': 'Rolex Submariner watch', 'thumbnail': 'https://images.example/watch.jpg'}
        self.assertLess(self.m._lens_reference_priority(row, ref), 0)
        self.assertFalse(self.m._lens_reference_fallback_eligible(row, ref))

    def test_serper_shopping_preserves_product_and_merchant_evidence(self):
        row = self.m._serper_to_serpapi('shopping', {'shopping': [{
            'title': 'CASIO DS-2B Calculator', 'link': 'https://www.google.com/search?ibp=oshop',
            'productId': '123456789', 'source': 'eBay UK', 'price': '£12.50',
            'imageUrl': 'https://images.example/calculator.jpg', 'ratingCount': 12, 'rating': 4.5,
            'merchant_link': 'https://www.ebay.co.uk/itm/123456789012'}]})['shopping_results'][0]
        self.assertEqual(row['product_id'], '123456789')
        self.assertEqual(row['reviews'], 12)
        self.assertEqual(self.m._local_discovery_direct_link(row), row['merchant_link'])
        self.assertEqual(row['extracted_price'], 12.5)

    def test_observed_tracking_targets_unwrap_without_network(self):
        merchant = 'https://www.ebay.co.uk/itm/123456789012'
        for base in ('https://www.google.com/search', 'https://www.googleadservices.com/pagead/aclk'):
            wrapped = base+'?'+urllib.parse.urlencode({'adurl': merchant})
            self.assertEqual(self.m._local_discovery_direct_link({'link': wrapped}), merchant)
        for target in ('http://127.0.0.1/product/12345', 'http://internal.local/product/12345',
                       'https://user:pass@www.ebay.co.uk/itm/123456789012'):
            wrapped = 'https://www.google.com/search?'+urllib.parse.urlencode({'url': target})
            self.assertEqual(self.m._local_discovery_direct_link({'link': wrapped}), '')
        self.assertEqual(self.m._local_discovery_direct_link({'link': 'https://www.google.com/search?q=calculator'}), '')

    def test_same_merchant_reordered_title_recovers_price_and_picture(self):
        card = {'title': 'CASIO DS-2B Calculator', 'source': 'eBay UK', 'price': '£12.50',
                'old_price': '£16.00', 'thumbnail': 'https://images.example/calculator.jpg'}
        data = {'organic_results': [{'title': 'Calculator CASIO DS2B - eBay UK',
                                     'link': 'https://www.ebay.co.uk/itm/123456789012'}]}
        with patch.object(self.m, '_fast_provider_search', return_value=data) as search:
            result = self.m._web_text_shopping_lookup(card, {'country': 'gb', 'hl': 'en'}, time.monotonic()+4, threading.Event())
        self.assertEqual(search.call_count, 1)
        row = result['organic_results'][0]
        self.assertEqual(row['price'], '£12.50')
        self.assertEqual(row['old_price'], '£16.00')
        self.assertEqual(row['image_candidates'][0], card['thumbnail'])

    def test_money_never_moves_to_another_model_variant_or_merchant(self):
        card = {'title': 'CASIO DS-2B black Calculator', 'source': 'eBay UK', 'price': '£12.50',
                'thumbnail': 'https://images.example/a.jpg'}
        for title in ('CASIO JS-40B black Calculator', 'CASIO DS2B white Calculator',
                      'CASIO DS2B black Calculator 2 pack', 'Replacement battery for CASIO DS2B black Calculator'):
            self.assertFalse(self.m._shopping_same_product(card, {'title': title}), title)
        with patch.object(self.m, '_fast_provider_search', return_value={'organic_results': [
            {'title': card['title'], 'link': 'https://www.amazon.co.uk/dp/B012345678'}]}):
            result = self.m._web_text_shopping_lookup(card, {'country': 'gb', 'hl': 'en'}, time.monotonic()+4, threading.Event())
        self.assertEqual(result['organic_results'], [])

    def test_ledger_deduplicates_and_binds_generic_reordered_title(self):
        market = {'country': 'gb'}
        card = {'source': 'eBay UK', 'title': 'Gold Tone Green Stone Necklace',
                'price': '£24.00', 'link': 'https://www.google.com/search?ibp=oshop'}
        self.m._shopping_unit_ledger_add(market, [card, card], 'serper_shopping')
        self.m._shopping_unit_ledger_add(market, [card], 'google_shopping')
        self.assertEqual(len(market['_shopping_units']), 1)
        row = {'title': 'Green Stone Gold Tone Necklace', 'url': 'https://www.ebay.co.uk/itm/123456789012'}
        self.assertEqual(self.m._shopping_unit_price_for(row, market), '£24.00')
        self.assertEqual(self.m._shopping_unit_price_for(dict(row, title='Red Stone Gold Tone Necklace'), market), '')
        market['_shopping_units'] = [{'merchant': 'eBay UK', 'title': 'Casio DS-2B Black Calculator', 'price': '£12.50'}]
        self.assertEqual(self.m._shopping_unit_price_for(dict(row, title='Casio DS-2B White Calculator'), market), '')

    def test_catalog_click_resolves_through_serper_without_buying_another_shopping_query(self):
        payload = {'id': '123456789', 'title': 'CASIO DS-2B Calculator', 'source': 'eBay UK',
                   'country': 'gb', 'lang': 'en', 'price': '£12.50'}
        link = 'https://www.ebay.co.uk/itm/123456789012'
        with patch.object(self.m, '_fast_provider_search', return_value={'organic_results': [
                {'title': 'Calculator CASIO DS2B - eBay UK', 'link': link}]}), \
             patch.object(self.m, '_serpapi_cached_json', side_effect=AssertionError('No extra paid provider')):
            self.assertEqual(self.m._shopping_resolve_merchant(payload, time.monotonic()+5), link)

    def test_individual_price_recovery_keeps_exact_url_binding(self):
        entries = {str(i): {'url': 'https://www.ebay.co.uk/itm/'+str(123456789012+i),
                           'title': 'Casio DS-2B Calculator', 'country': 'gb'} for i in range(2)}
        def search(engine, query, *a, **kw):
            hits = [{'title': 'Casio DS-2B Calculator', 'link': row['url'], 'snippet': 'Price £12.50',
                     'thumbnail': 'https://images.example/calculator.jpg'}
                    for row in entries.values() if row['url'].rsplit('/', 1)[-1] in query]
            hits.append({'title': 'Casio DS-2B Calculator', 'link': 'https://www.ebay.co.uk/itm/999999999999', 'price': '£1.00'})
            return {'organic_results': hits}
        with patch.object(self.m, '_fast_provider_search', side_effect=search) as call:
            result = self.m._web_targeted_price_updates(entries, 'en', {'country': 'gb'})
        self.assertEqual(call.call_count, 2)
        self.assertFalse(any(' OR ' in call.args[1] for call in call.call_args_list))
        self.assertEqual(set(result), {'0', '1'})
        self.assertTrue(all(row.get('page_image') for row in result.values()))
        self.assertTrue(all(row.get('price') and '1.00' not in row['price'] for row in result.values()))

    def test_image_budget_is_eight_seconds_but_never_exceeds_parent_deadline(self):
        self.assertEqual(sum(self.m._fast_provider_timeouts('serper_images', 12)), 8)
        self.assertEqual(sum(self.m._fast_provider_timeouts('serper_images', 2)), 2)
        self.assertLess(sum(self.m._fast_provider_timeouts('serper_search', 12)), 8)
        self.assertEqual(self.m._SEARCHAPI_ROUTER.threshold, 8)
        self.assertFalse(self.m.FINDZIA_GROUPED_RECOVERY_ENABLED)

    def test_serper_image_read_gets_full_window_without_a_second_call(self):
        from findzia_searchapi import SerperTransport
        transport = SerperTransport(cache_get=lambda key: None, cache_put=lambda *a, **kw: None, cost=lambda *a: None)
        self.addCleanup(transport.pool.pool.shutdown)
        calls = []
        def fetch(kind, body, timeout):
            calls.append(timeout)
            return {'images': []}
        transport.search('images', {'q': 'mouse'}, (1.5, 6.5), fetch, self.m._serper_to_serpapi)
        self.assertEqual(calls, [(1.5, 8)])


if __name__ == '__main__':
    unittest.main(verbosity=2)
