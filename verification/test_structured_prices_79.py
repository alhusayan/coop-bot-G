"""Synthetic provider fixtures; no credentials or network needed."""
import copy
import io
import json
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from functools import lru_cache
from types import SimpleNamespace

from findzia_prices import StructuredPrices, shein_params, shopping_params, _shein_records, _google_records
import test_audit_prices as support

SHEIN = 'https://us.shein.com/Blue-Candle-p-1234567.html'
CARD = {'title': 'Acme Blue Candle', 'source': 'Shop', 'product_id': '123456789',
        'price': '$99', 'thumbnail': 'https://images.example.com/candle.jpg'}


def shein_data():
    return {'search_metadata': {'status': 'Success', 'request_url': SHEIN},
            'search_parameters': {'shein_domain': 'us.shein.com', 'currency': 'USD'},
            'product': {'product_id': '1234567', 'title': 'Blue Candle', 'price': '$8.95',
                        'stock': 8, 'is_in_stock': True, 'main_image': 'https://images.example.com/candle.jpg',
                        'original_price': '$15', 'shein_club_membership': {'price': '$7'},
                        'variants': {'size': [{'price': '$8.95', 'stock': 5}, {'price': '$12.95', 'stock': 3}]}}}


def google_data():
    return {'product': {'product_id': CARD['product_id'], 'price': '$1'},
            'offers': [{'link': 'https://shop.example.com/candle?sku=blue',
                        'title': 'Acme Blue Candle', 'price': '$8.95',
                        'merchant': {'name': 'Shop'}, 'original_price': '$20'},
                       {'link': 'https://other.example.com/candle?sku=blue',
                        'title': 'Acme Blue Candle', 'price': '$12.95',
                        'merchant': {'name': 'Other'}}],
            'typical_prices': {'low_price': '$2'}}


class BindingTests(unittest.TestCase):
    def shein(self, data=None, url=SHEIN):
        return _shein_records(shein_data() if data is None else data, shein_params({'url': url}))

    def test_observed_domain_id_and_currency_are_explicit(self):
        self.assertEqual(shein_params({'url': SHEIN}), {'engine':'shein_product', 'product_id':'1234567',
                          'shein_domain':'us.shein.com', 'currency':'USD'})

    def test_gulf_mobile_unknown_and_spoofed_hosts_are_not_replaced(self):
        for host in ('m.shein.com', 'jo.shein.com', 'ar.shein.com', 'us.shein.com.evil.test'):
            self.assertIsNone(shein_params({'url': SHEIN.replace('us.shein.com', host)}))

    def test_selected_variant_currency_and_unknown_queries_use_existing_index(self):
        for query in ('sku=12', 'currency=KWD', 'size=L', 'seller=2', 'mallCode=2', 'unknown='):
            self.assertIsNone(shein_params({'url': SHEIN + '?' + query}))
        self.assertIsNotNone(shein_params({'url': SHEIN + '?utm_source=test&srsltid=abc'}))

    def test_non_product_paths_credentials_and_ports_rejected(self):
        for url in (SHEIN.replace('/Blue-', '/ar/Blue-'), SHEIN.replace('https://', 'https://name:pass@'),
                    SHEIN.replace('.com/', '.com:8443/'), 'https://us.shein.com/pdsearch/candle/'):
            self.assertIsNone(shein_params({'url': url}))

    def test_variants_form_range_and_old_member_prices_do_not_enter_it(self):
        row = self.shein()[0]
        self.assertEqual(row['price'], '8.95-12.95 USD')
        self.assertNotIn('price_verified', row)

    def test_out_of_stock_size_is_not_a_cheapest_price(self):
        data = shein_data()
        data['product']['variants']['size'].append({'price': '$1', 'stock': 0})
        self.assertEqual(self.shein(data)[0]['price'], '8.95-12.95 USD')
        data['product']['variants']['size'][0]['stock'] = 0
        self.assertEqual(self.shein(data)[0]['price'], '12.95 USD')
        data['product']['variants']['size'][1]['stock'] = 0
        self.assertEqual(self.shein(data), [])

    def test_other_colour_price_is_not_in_range(self):
        data = shein_data()
        data['product']['variants']['colors'] = [{'product_id':'9999999', 'price':'$1'}]
        self.assertEqual(self.shein(data)[0]['price'], '8.95-12.95 USD')

    def test_missing_live_variant_price_fails_closed(self):
        data = shein_data()
        data['product']['variants']['size'][0].pop('price')
        self.assertEqual(self.shein(data), [])

    def test_no_current_price_does_not_use_original_or_usd_extraction(self):
        for value in ('', '8.95', '$1/month', 'from $5', '$0', '€8.95'):
            data = shein_data(); data['product']['price'] = value
            data['product'].update(price_usd='$8.95', extracted_price=8.95)
            self.assertEqual(self.shein(data), [])

    def test_product_market_response_and_currency_must_match(self):
        for edit in ('id', 'url', 'domain', 'currency', 'stock'):
            data = shein_data()
            if edit == 'id': data['product']['product_id'] = '9999999'
            if edit == 'url': data['search_metadata']['request_url'] = SHEIN.replace('us.', 'de.')
            if edit == 'domain': data['search_parameters']['shein_domain'] = 'de.shein.com'
            if edit == 'currency': data['search_parameters']['currency'] = 'CAD'
            if edit == 'stock': data['product']['is_in_stock'] = False
            self.assertEqual(self.shein(data), [])

    def test_europe_price_keeps_eur(self):
        data = shein_data(); url = SHEIN.replace('us.', 'de.')
        data['search_metadata']['request_url'] = url
        data['search_parameters'] = {'shein_domain':'de.shein.com', 'currency':'EUR'}
        data['product'].update(price='€8,95', variants={})
        self.assertEqual(self.shein(data,url)[0]['price'], '8.95 EUR')

    def test_each_google_offer_keeps_own_money_url_and_seller(self):
        rows = _google_records(google_data(), shopping_params(CARD,'sa','ar'))
        self.assertEqual([r['price'] for r in rows], ['$8.95','$12.95'])
        self.assertEqual([r['source'] for r in rows], ['Shop','Other'])
        self.assertTrue(all(r['_shopping_gl'] == 'sa' for r in rows))
        self.assertEqual(rows[0]['old_price'], '$20')

    def test_google_does_not_borrow_aggregate_price_for_missing_offer(self):
        data = google_data(); data['offers'][0].pop('price')
        self.assertEqual(len(_google_records(data, shopping_params(CARD,'us','en'))),1)

    def test_google_rejects_wrong_catalog_id_unresolved_redirect_and_oos(self):
        params = shopping_params(CARD,'us','en')
        data = google_data(); data['product']['product_id'] = '9999999'
        self.assertEqual(_google_records(data,params),[])
        data = google_data(); data['offers'][0]['link'] = 'https://www.google.com/goto?url=abc'
        data['offers'][1]['stock_information'] = 'Out of stock online'
        self.assertEqual(_google_records(data,params),[])

    def test_google_identifier_and_explicit_language_not_title_guess(self):
        params = shopping_params(CARD,'de','de')
        self.assertEqual(params, {'engine':'google_product_page','gl':'de','hl':'de',
                                 'link':'resolved','product_id':'123456789'})
        self.assertIsNone(shopping_params({'title':'candle'}, 'de','de'))
        self.assertIsNone(shopping_params(CARD, '', 'en'))

    def test_native_product_token_is_preserved(self):
        card = dict(CARD, product_token='observed-product-token')
        self.assertEqual(shopping_params(card,'gb','en')['product_token'],'observed-product-token')


class Response:
    def __init__(self,data=None,status=200):
        self.data = google_data() if data is None else data
        self.status_code, self.closed = status, False
    def iter_content(self,size): yield json.dumps(self.data).encode()
    def close(self): self.closed = True


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.calls, self.responses = [], []
        self.reply = Response()
        def get(*args,**kwargs):
            self.calls.append((args,kwargs)); return self.reply
        self.client = StructuredPrices(key='private-test-secret', enabled=True, get=get)
    def request(self,card=None):
        with redirect_stdout(io.StringIO()):
            return self.client.shopping(card or CARD,'us','en',2)

    def test_auth_header_fixed_endpoint_no_redirects_and_response_closed(self):
        self.request()
        args,kwargs = self.calls[0]
        self.assertEqual(args,('https://www.searchapi.io/api/v1/search',))
        self.assertEqual(kwargs['headers']['Authorization'],'Bearer private-test-secret')
        self.assertNotIn('api_key',kwargs['params'])
        self.assertFalse(kwargs['allow_redirects']); self.assertTrue(self.reply.closed)

    def test_cache_isolated_by_market_language_and_immutable(self):
        first = self.request(); first['organic_results'][0]['price'] = '$999'
        self.assertEqual(self.request()['organic_results'][0]['price'],'$8.95')
        with redirect_stdout(io.StringIO()): self.client.shopping(CARD,'sa','ar',2)
        self.assertEqual(len(self.calls),2)

    def test_failures_make_one_call_per_request_and_are_not_cached(self):
        self.reply = Response({'error':'upstream private-test-secret'},500)
        with redirect_stdout(io.StringIO()) as out:
            first = self.client.shopping(CARD,'us','en',2)
            second = self.client.shopping(CARD,'us','en',2)
        self.assertEqual(first,second)
        self.assertTrue(first['_findzia_lookup_failed']); self.assertEqual(len(self.calls),2)
        self.assertFalse(self.client.cache)
        self.assertNotIn('private-test-secret',out.getvalue())

    def test_account_or_rate_failure_opens_circuit(self):
        for status in (401,402,403,429):
            calls = []
            client = StructuredPrices(key='test', enabled=True,
                get=lambda *a,**k:calls.append(k) or Response({},status))
            with redirect_stdout(io.StringIO()):
                result = client.shopping(CARD,'us','en',2)
                skipped = client.shopping(dict(CARD,product_id='99999999'),'us','en',2)
            self.assertTrue(result['_findzia_lookup_failed'])
            self.assertIsNone(skipped); self.assertEqual(len(calls),1)

    def test_no_key_disabled_and_unsupported_do_not_call(self):
        self.client.key = ''
        self.assertIsNone(self.request())
        self.client.key = 'test'; self.client.enabled = False
        self.assertIsNone(self.request())
        self.client.enabled = True
        self.assertIsNone(self.client.shein({'url':SHEIN.replace('us.','jo.')},2))
        self.assertEqual(self.calls,[])

    def test_malformed_oversized_and_unknown_status_fail_without_leaking(self):
        for data in ([], {'search_metadata':{'status':'Processing'}}, {'padding':'x'*2000001}):
            self.client.cache.clear(); self.reply = Response(data)
            self.assertTrue(self.request()['_findzia_lookup_failed'])
            self.assertTrue(self.reply.closed)

    def test_concurrent_identical_requests_are_coalesced(self):
        entered,release = threading.Event(),threading.Event()
        def get(*a,**k):
            self.calls.append(k); entered.set(); release.wait(1); return Response()
        self.client.get = get
        with redirect_stdout(io.StringIO()), ThreadPoolExecutor(max_workers=2) as pool:
            one = pool.submit(self.client.shopping,CARD,'us','en',2)
            self.assertTrue(entered.wait(1))
            two = pool.submit(self.client.shopping,CARD,'us','en',2)
            release.set()
            self.assertEqual(one.result(),two.result())
        self.assertEqual(len(self.calls),1)

    def test_global_parallelism_is_bounded(self):
        for _ in range(4): self.assertTrue(self.client.slots.acquire(False))
        self.assertIsNone(self.request()); self.assertEqual(self.calls,[])
        for _ in range(4): self.client.slots.release()


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.PriceTests(); self.fixture.setUp()
        self.ns = self.fixture.ns

    def test_shein_structured_request_replaces_index_request_and_passes_price_guard(self):
        calls = []
        client = StructuredPrices(key='test', enabled=True, get=lambda *a,**k:calls.append(k) or Response(shein_data()))
        self.ns['_STRUCTURED_PRICES'] = client
        real = support.scope(['_web_live_quote_fields'], {
            '_web_live_money_fields':lambda amount,currency,market: {
                'price_amount':amount, 'currency':currency}})
        self.ns['_web_live_quote_fields'] = real['_web_live_quote_fields']
        row = {'url':SHEIN,'title':'Blue Candle','country':'us'}
        with redirect_stdout(io.StringIO()):
            update = self.ns['_web_targeted_price_updates']({'one':row},'ar',{'country':'kw'})['one']
        self.assertEqual(self.fixture.calls,[]); self.assertEqual(len(calls),1)
        self.assertEqual(update['price_source'],'searchapi_shein_product')
        self.assertEqual(update['price_kind'],'range')
        self.assertEqual((update['price_min'],update['price_max']),(8.95,12.95))
        self.assertFalse(update['price_verified'])
        self.assertTrue(self.ns['_web_confirmable_price'](dict(row,**update)))
        self.assertFalse(self.ns['_web_confirmable_price'](dict(row,**dict(update,price_source_url=SHEIN.replace('us.','de.')))))

    def test_unsupported_shein_retains_exact_listing_index(self):
        self.ns['_STRUCTURED_PRICES'] = StructuredPrices(key='test',enabled=True,
            get=lambda *a,**k:self.fail('unsupported storefront requested'))
        with redirect_stdout(io.StringIO()):
            self.ns['_web_targeted_price_updates']({'one':{'url':SHEIN.replace('us.','jo.'),'title':'Blue Candle'}},'ar',{'country':'kw'})
        self.assertEqual(len(self.fixture.calls),1)

    def test_structured_failure_consumes_one_slot_without_extra_paid_fallback(self):
        self.ns['_STRUCTURED_PRICES'] = StructuredPrices(key='test',enabled=True,get=lambda *a,**k:Response({},402))
        with redirect_stdout(io.StringIO()):
            updates=self.ns['_web_targeted_price_updates']({'one':{'url':SHEIN,'title':'Blue Candle'}},'ar',{'country':'kw'})
        self.assertEqual(updates,{}); self.assertEqual(self.fixture.calls,[])

    def test_request_market_beats_wrong_ambient_market_and_one_earlier_local_attempt(self):
        self.ns['WEB_ASYNC_PRICE_SHARED_MARKETS'] = 2
        self.ns['current_market'] = lambda:{'country':'kw'}
        self.ns['_web_offer_image_candidates'] = lambda r:['image']
        local = {'url':'https://local.example.com/dress','country':'sa','title':'dress'}
        overseas = {'url':SHEIN,'country':'us','title':'dress'}
        batches = self.ns['_web_automatic_price_batches']({'global':overseas,'local':local},
                    {'earlier':local}, {'country':'sa'})
        self.assertEqual(list(batches[0]),['local'])
        self.assertEqual(list(batches[1]),['global'])

    def test_ounass_alias_is_exact_and_conflicting_path_is_rejected(self):
        ns = support.scope(['_merchant_url_market'], {'lru_cache':lru_cache})
        self.assertEqual(ns['_merchant_url_market']('https://saudi.ounass.com/p')['country'],'sa')
        self.assertNotEqual(ns['_merchant_url_market']('https://saudi.ounass.com.evil.test/p').get('country'),'sa')

    def lookup_scope(self, result, cancel=None):
        return support.scope(['_web_text_shopping_lookup'], {
            '_STRUCTURED_PRICES':SimpleNamespace(shopping=lambda *a:result),
            '_local_discovery_direct_link':lambda row:row.get('link',''),
            '_shopping_same_product':lambda card,row:card['title'] == row['title'],
            '_web_offer_image_candidates':lambda r:[r['thumbnail']] if r.get('thumbnail') else [],
            '_fast_provider_search':lambda *a,**k:self.fail('extra index request')})

    def test_google_lookup_preserves_offer_price_instead_of_card_price(self):
        result = {'organic_results':_google_records(google_data(),shopping_params(CARD,'us','en'))}
        ns = self.lookup_scope(result)
        rows = ns['_web_text_shopping_lookup'](CARD,{'country':'us','hl':'en'},time.monotonic()+3,threading.Event())['organic_results']
        self.assertEqual([r['price'] for r in rows],['$8.95','$12.95'])
        self.assertTrue(all(r['image_candidates'] == [CARD['thumbnail']] for r in rows))

    def test_google_wrong_product_and_cancelled_reply_never_publish(self):
        data=google_data(); data['offers'][0]['title']='Different product'; data['offers']=data['offers'][:1]
        ns=self.lookup_scope({'organic_results':_google_records(data,shopping_params(CARD,'us','en'))})
        self.assertEqual(ns['_web_text_shopping_lookup'](CARD,{'country':'us','hl':'en'},time.monotonic()+3,threading.Event()),{'organic_results':[]})
        cancel=threading.Event(); cancel.set()
        self.assertIsNone(ns['_web_text_shopping_lookup'](CARD,{'country':'us','hl':'en'},time.monotonic()+3,cancel))

    def test_google_attempted_failure_does_not_trigger_index_fallback(self):
        ns=self.lookup_scope({'organic_results':[],'_findzia_lookup_failed':True})
        self.assertEqual(ns['_web_text_shopping_lookup'](CARD,{'country':'us','hl':'en'},time.monotonic()+3,threading.Event()),{'organic_results':[]})

    def test_google_native_reply_after_deadline_is_not_published(self):
        ns=self.lookup_scope({'organic_results':google_data()['offers']})
        times=iter([0,5])
        ns['time']=SimpleNamespace(monotonic=lambda:next(times))
        self.assertEqual(ns['_web_text_shopping_lookup'](CARD,{'country':'us','hl':'en'},3,threading.Event()),{'organic_results':[]})

    def test_shein_uk_slug_alias_is_bound_but_different_country_is_not(self):
        same=self.ns['_web_same_index_listing']
        first=SHEIN.replace('us.shein.com','www.shein.co.uk')
        self.assertTrue(same(first,first.replace('Blue-Candle','Blaue-Kerze')))
        self.assertFalse(same(first,SHEIN))

    def test_serper_adapter_keeps_observed_native_identifiers(self):
        ns=support.scope(['_serper_to_serpapi'])
        card=dict(CARD,link='https://www.google.com/shopping/product/123456789',
                  productId='123456789',product_token='observed-product-token')
        rows=ns['_serper_to_serpapi']('shopping',{'shopping':[card]})['shopping_results']
        self.assertEqual(rows[0]['product_token'],card['product_token'])
        self.assertEqual(rows[0]['product_id'],card['productId'])


if __name__ == '__main__': unittest.main()
