"""Real cache persistence and provider adapters; fake clock/HTTP only."""
import copy
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from collections import Counter

from findzia_cache import cache_ttl, provider_cacheable
from findzia_searchapi import SerperTransport, SearchApiRouter
from findzia_independent_search import SearchClient
from test_audit_prices import scope, Clock

GOOD = {'organic_results': [{'title': 'Blue candle', 'link': 'https://shop.example/candle', 'price':'$5'}]}
BAD = ({}, {'organic_results': []}, {'organic_results': [{}]},
       {'organic_results': ['bad']}, {'organic_results':[{'unknown':True}]},
       dict(GOOD, error='timeout'), dict(GOOD, partial=True), dict(GOOD, ok=False),
       dict(GOOD, search_metadata={'status':'Error'}), dict(GOOD, _findzia_lookup_failed=True))


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.clock = Clock(); self.clock.now = 1_000_000
        self.path = str(Path(self.temp.name)/'cache.sqlite')
        self.market = {'country':'kw'}
        roots = ['_serpapi_cache_db_init','_serpapi_cache_get','_serpapi_cache_put',
                 '_web_ai_classifier_cache_db_init','_web_ai_classifier_cache_get',
                 '_web_ai_classifier_cache_put','_cache_db_init','cache_get','cache_put','_text_lens_cache']
        self.ns = scope(roots, {'sqlite3':sqlite3, 'time':self.clock, 'CACHE_DB_PATH':self.path,
            'CACHE_DB_LOCK':threading.Lock(), 'SERPAPI_RESULT_CACHE_ENABLED':True,
            'SERPAPI_RESULT_CACHE_TTL_SECONDS':3600, 'WEB_AI_CLASSIFIER_CACHE_TTL_SECONDS':86400,
            'current_market':lambda:self.market, 'normalize_ar':lambda s:s.lower(),
            'norm_tokens':lambda s:set(s.split()), 'cache_ttl_for':lambda *a:7*86400,
            'SEARCH_CACHE':{}, '_TEXT_LENS_REFERENCES':{}, '_TEXT_LENS_LOCK':threading.Lock()})
        self.ns['_serpapi_cache_db_init']()
        self.ns['_cache_db_init']()
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE ai_result_classification_cache(cache_key TEXT PRIMARY KEY,response_json TEXT,created_at REAL,expires_at REAL)')

    def test_no_empty_failure_partial_or_malformed_provider_entry(self):
        for data in BAD:
            self.ns['_serpapi_cache_put']('bad','google',data)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM serpapi_response_cache').fetchone()[0],0)

    def test_failed_refresh_does_not_overwrite_good_evidence(self):
        self.ns['_serpapi_cache_put']('a','google',GOOD)
        self.ns['_serpapi_cache_put']('a','google',{'error':'timeout'})
        self.assertEqual(self.ns['_serpapi_cache_get']('a'),GOOD)

    def test_hard_day_boundary_and_hits_do_not_extend_it(self):
        self.ns['_serpapi_cache_put']('a','google',GOOD,7*86400)
        self.clock.now += 86399
        self.assertEqual(self.ns['_serpapi_cache_get']('a'),GOOD)
        self.clock.now += 1
        self.assertIsNone(self.ns['_serpapi_cache_get']('a'))

    def test_prices_shorter_ttl_is_preserved_and_zero_disables_write(self):
        self.ns['_serpapi_cache_put']('a','google',GOOD,300)
        self.ns['_serpapi_cache_put']('zero','google',GOOD,0)
        self.clock.now += 300
        self.assertIsNone(self.ns['_serpapi_cache_get']('a'))
        self.assertIsNone(self.ns['_serpapi_cache_get']('zero'))
        self.assertEqual(cache_ttl(float('inf')),0)

    def test_legacy_poisoned_and_old_rows_are_deleted(self):
        for i,(raw,created) in enumerate([
            ('not json',self.clock.now), (json.dumps({'organic_results':[]}),self.clock.now),
            (json.dumps(GOOD),self.clock.now-86401), (json.dumps(GOOD),self.clock.now+10)]):
            with sqlite3.connect(self.path) as db:
                db.execute('INSERT INTO serpapi_response_cache VALUES (?,?,?,?,?)',
                           (str(i),'google',raw,created,self.clock.now+7*86400))
            self.assertIsNone(self.ns['_serpapi_cache_get'](str(i)))
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM serpapi_response_cache').fetchone()[0],0)

    def test_photo_identity_and_offer_proof_expire_after_one_day(self):
        for value in ({'query':'blue candle'}, {'item':{'id':1,'match':'mismatch'}},
                      {'items':[{'id':1,'match':'exact'}]}):
            self.ns['_web_ai_classifier_cache_put']('proof',value,7*86400)
            self.assertEqual(self.ns['_web_ai_classifier_cache_get']('proof'),value)
            self.clock.now += 86400
            self.assertIsNone(self.ns['_web_ai_classifier_cache_get']('proof'))

    def test_failed_or_empty_audit_is_not_persisted(self):
        for value in ({'items':[]},{'items':[None]}, {'items':[{'id':1}], 'review_error':'partial_offer_review'}):
            self.ns['_web_ai_classifier_cache_put']('bad',value)
        self.assertIsNone(self.ns['_web_ai_classifier_cache_get']('bad'))

    def test_legacy_week_old_identity_not_reused(self):
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT INTO ai_result_classification_cache VALUES (?,?,?,?)',
                       ('old',json.dumps({'query':'candle'}),self.clock.now-90000,self.clock.now+7*86400))
        self.assertIsNone(self.ns['_web_ai_classifier_cache_get']('old'))

    def test_final_search_no_fuzzy_cross_market_or_empty_result(self):
        self.ns['cache_put']('Acme X100 blue','en','Product',{'1':'https://shop.example/1'})
        self.assertIsNotNone(self.ns['cache_get']('Acme X100 blue','en'))
        self.assertIsNone(self.ns['cache_get']('Acme X100 blue new','en'))
        self.market['country']='sa'
        self.assertIsNone(self.ns['cache_get']('Acme X100 blue','en'))
        self.ns['cache_put']('empty','en','No results',{})
        self.assertIsNone(self.ns['cache_get']('empty','en'))
        self.market['country']='kw'; self.clock.now += 86400
        self.assertIsNone(self.ns['cache_get']('Acme X100 blue','en'))

    def test_text_image_reference_day_limit_survives_restart(self):
        ref = dict(query_key='q', reference='token', image_base64='image', ok=True,
                   expires_at=self.clock.now+7*86400)
        self.ns['_text_lens_cache'](save=ref)
        self.ns['_TEXT_LENS_REFERENCES'].clear()
        self.assertEqual(self.ns['_text_lens_cache'](query_key='q')['expires_at'], self.clock.now+86400)
        self.clock.now += 86400
        self.assertIsNone(self.ns['_text_lens_cache'](query_key='q'))

    def test_legacy_reference_without_creation_time_is_invalidated(self):
        self.ns['_text_lens_cache']()
        ref=dict(query_key='q',reference='old',expires_at=self.clock.now+86400)
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT INTO text_lens_references VALUES (?,?,?,?)',('q','old',json.dumps(ref),ref['expires_at']))
        self.assertIsNone(self.ns['_text_lens_cache'](query_key='q'))

    def test_failed_reference_is_never_saved(self):
        self.ns['_text_lens_cache'](save=dict(query_key='q',reference='bad',ok=False,
                                            error='timeout',expires_at=self.clock.now+86400))
        self.assertFalse(self.ns['_TEXT_LENS_REFERENCES'])
        self.assertIsNone(self.ns['_text_lens_cache'](query_key='q'))

    def test_malformed_legacy_final_urls_are_discarded(self):
        key=self.ns['cache_key']('candle','en')
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT INTO search_cache VALUES (?,?,?,?,?,?,?)',
                (key,'candle','en','Product',json.dumps('malformed'),self.clock.now,self.clock.now+3600))
        self.assertIsNone(self.ns['cache_get']('candle','en'))


class LocalEvidenceTests(unittest.TestCase):
    def test_store_discovery_failure_not_cached_and_success_expires(self):
        clock=Clock();calls=[]
        replies=iter([('',{}),('shop.example',{}),('shop.example',{})])
        def discover(*a,**k):calls.append(a);return next(replies)
        ns=scope(['resolve_store_homepage'],{'time':clock,'text77_store_domain':lambda s:'',
            'normalize_name':lambda s:s,'normalize_ar':lambda s:s,
            'current_market':lambda:{'country':'kw'},'text77_call_gemini':discover,
            'url_is_alive':lambda u:True,'_STORE_HOME_CACHE':{},'_STORE_HOME_LOCK':threading.Lock()})
        self.assertEqual(ns['resolve_store_homepage']('Shop'),'')
        self.assertFalse(ns['_STORE_HOME_CACHE'])
        self.assertEqual(ns['resolve_store_homepage']('Shop'),'https://shop.example')
        ns['resolve_store_homepage']('Shop');self.assertEqual(len(calls),2)
        clock.now=86400;ns['resolve_store_homepage']('Shop');self.assertEqual(len(calls),3)

    def test_failed_redirect_resolution_is_retried(self):
        from types import SimpleNamespace
        replies=iter([SimpleNamespace(status_code=429,url='https://shop.example/p'),
                      SimpleNamespace(status_code=200,url='https://shop.example/p')])
        calls=[]
        def fetch(*a,**k):calls.append(a);return next(replies)
        ns=scope(['get_final_url'],{'_web_validated_outbound_url':lambda u:True,
            '_web_safe_get':fetch,'_web_safe_response_close':lambda r:None,
            'FINAL_URL_CACHE':{},'FINAL_URL_CACHE_LOCK':threading.Lock(),'HEADERS':{}})
        for _ in range(3):ns['get_final_url']('https://shop.example/p')
        self.assertEqual(len(calls),2)

    def test_empty_collection_retry_starts_new_fetch(self):
        calls=[]
        def submit(fn,url):
            calls.append(url);f=Future();f.set_result([]);return f
        from types import SimpleNamespace
        from concurrent.futures import wait
        ns=scope(['_web_expand_collection_rows'], {'wait':wait,'_COLLECTION_JOBS':{},
            '_COLLECTION_LOCK':threading.Lock(),'_COLLECTION_POOL':SimpleNamespace(submit=submit),
            '_web_fetch_collection':lambda u:[], '_web_collection_url':lambda u:True,
            '_web_price_url_key':lambda u:u,'COLLECTION_PAGES_MAX':2,'COLLECTION_WAIT_SECONDS':1})
        for _ in range(2):self.assertEqual(ns['_web_expand_collection_rows']([{'url':'https://shop.example/collection'}]),[])
        self.assertEqual(len(calls),2)

    def test_empty_filter_evidence_is_not_cached(self):
        ns=scope(['_refine_live_evidence'],{'CLASSIC_FILTER_CATALOG_ENABLED':False,
            '_refine_catalog_key':lambda *a:'key','_CLASSIC_EVIDENCE_CACHE':{},
            '_refine_catalog_fetch':lambda *a:[], '_REFINE_CATALOG_POOL':None,
            '_CLASSIC_EVIDENCE_LOCK':threading.Lock()})
        self.assertEqual(ns['_refine_live_evidence']('candle','kw')['records'],[])
        self.assertFalse(ns['_CLASSIC_EVIDENCE_CACHE'])

    def test_failed_page_is_retried_then_success_cached_shortly(self):
        clock=Clock(); calls=[]
        replies=iter([{'ok':False,'page_fetch_reason':'timeout'},
            {'ok':True,'is_product':True,'price':5,'currency':'KWD','url':'https://shop.example/p'}])
        def fetch(*args): calls.append(args);return next(replies)
        ns=scope(['_web_verified_page_snapshot'], {'time':clock,
            'current_market':lambda:{'country':'kw'},'_web_market_currency':lambda m:'KWD',
            '_web_price_url_key':lambda u:u,'_web_fetch_page_snapshot':fetch,
            'WEB_PRODUCT_VERIFY_CACHE':{},'WEB_PRODUCT_VERIFY_LOCK':threading.Lock(),
            '_WEB_PAGE_FLIGHTS':{},'WEB_LIVE_PRICE_CACHE_TTL':300,'WEB_STOCK_CACHE_TTL':120})
        self.assertFalse(ns['_web_verified_page_snapshot']('https://shop.example/p')['ok'])
        self.assertFalse(ns['WEB_PRODUCT_VERIFY_CACHE'])
        self.assertTrue(ns['_web_verified_page_snapshot']('https://shop.example/p')['ok'])
        self.assertTrue(ns['_web_verified_page_snapshot']('https://shop.example/p')['ok'])
        self.assertEqual(len(calls),2)

    def test_transient_image_failures_are_not_reused(self):
        clock=Clock()
        ns=scope(['_web_image_cache_get','_web_image_cache_set','_web_visual_cache_get','_web_visual_cache_set'],
                 {'time':clock,'WEB_IMAGE_CACHE_TTL_SECONDS':7*86400,
                  'WEB_IMAGE_CACHE':{},'WEB_IMAGE_CACHE_LOCK':threading.Lock(),
                  'WEB_VISUAL_IMAGE_CACHE':{},'WEB_VISUAL_IMAGE_CACHE_LOCK':threading.Lock()})
        ns['_web_image_cache_set']('a','0');ns['_web_visual_cache_set']('a',None)
        self.assertFalse(ns['WEB_IMAGE_CACHE']);self.assertFalse(ns['WEB_VISUAL_IMAGE_CACHE'])
        ns['_web_image_cache_set']('a','https://image.example/p.jpg')
        ns['_web_visual_cache_set']('a',b'pixels')
        clock.now=86400
        self.assertEqual(ns['_web_image_cache_get']('a'),'')
        self.assertEqual(ns['_web_visual_cache_get']('a'),(False,None))

    def test_liveness_network_failure_does_not_hide_next_attempt(self):
        from types import SimpleNamespace
        replies=iter([SimpleNamespace(status_code=429),SimpleNamespace(status_code=200)])
        ns=scope(['url_is_alive'], {'_URL_ALIVE_CACHE':{},'_URL_ALIVE_LOCK':threading.Lock(),
            '_web_validated_outbound_url':lambda u:True,'_web_safe_get':lambda *a,**k:next(replies),
            '_web_safe_response_close':lambda r:None,'HEADERS':{}})
        self.assertFalse(ns['url_is_alive']('https://shop.example/p'))
        self.assertTrue(ns['url_is_alive']('https://shop.example/p'))
        self.assertTrue(ns['url_is_alive']('https://shop.example/p'))


class Response:
    status_code=200
    def __init__(self,data):self.data=data
    def json(self):return copy.deepcopy(self.data)
    def close(self):pass
    def iter_content(self,*args):yield json.dumps(self.data).encode()


class ProviderTests(unittest.TestCase):
    def setUp(self): self.cache={};self.costs=Counter();self.calls=[]
    def put(self,key,engine,data,**kwargs): self.cache[key]=copy.deepcopy(data)
    def cost(self,key):self.costs[key]+=1

    def test_serper_empty_then_fresh_success_then_reuse(self):
        client=SerperTransport(cache_get=self.cache.get,cache_put=self.put,cost=self.cost)
        replies=iter([{'organic':[]},{'organic':GOOD['organic_results']}])
        def fetch(*a):self.calls.append(a);return next(replies)
        def search():return client.search('search',{'q':'candle','gl':'kw'},1,fetch,
                                          lambda k,d:{'organic_results':d['organic']})
        self.assertEqual(search()['organic_results'],[]);self.assertFalse(self.cache)
        self.assertTrue(search()['organic_results']);self.assertTrue(search()['organic_results'])
        self.assertEqual(len(self.calls),2)

    def test_serper_simultaneous_empty_is_shared_but_next_wave_is_fresh(self):
        entered,release,shared=threading.Event(),threading.Event(),threading.Event()
        def cost(k):
            if k=='serper_shared_responses':shared.set()
        client=SerperTransport(cache_get=self.cache.get,cache_put=self.put,cost=cost)
        def fetch(*a):self.calls.append(a);entered.set();release.wait(2);return {'organic':[]}
        def search():return client.search('search',{'q':'candle'},2,fetch,lambda k,d:{'organic_results':[]})
        with ThreadPoolExecutor(2) as pool:
            first=pool.submit(search);self.assertTrue(entered.wait(1))
            second=pool.submit(search);self.assertTrue(shared.wait(1));release.set()
            self.assertEqual(first.result(),second.result())
        self.assertEqual(len(self.calls),1);self.assertFalse(self.cache)
        search();self.assertEqual(len(self.calls),2)

    def test_searchapi_empty_does_not_buy_rescue_or_cache(self):
        replies=iter([{'visual_matches':[]},{'visual_matches':GOOD['organic_results']}])
        def get(*a,**k):self.calls.append(k);return Response(next(replies))
        with patch.dict('os.environ',{'SEARCHAPI_API_KEY':'test','SERPAPI_API_KEY':'test'}):
            client=SearchApiRouter(cache_get=self.cache.get,cache_put=self.put,cost=self.cost,http_get=get,log=lambda s:None)
        def rescue(*a,**k):self.fail('empty success must not buy fallback')
        def search():return client.search({'engine':'google_lens','url':'https://image.example/p.jpg'},2,rescue)
        self.assertEqual(search()['visual_matches'],[]);self.assertFalse(self.cache)
        self.assertTrue(search()['visual_matches']);self.assertTrue(search()['visual_matches'])
        self.assertEqual(len(self.calls),2)

    def test_late_provider_failure_not_cached_and_valid_late_evidence_retained(self):
        client=SearchApiRouter(cache_get=self.cache.get,cache_put=self.put,cost=self.cost,log=lambda s:None)
        for key,value in [('empty',{'visual_matches':[]}),('good',GOOD)]:
            future=Future();client._retain_late(key,'google_lens',future,False)
            future.set_result((value,'',200))
        self.assertNotIn('empty',self.cache);self.assertIn('good',self.cache)

    def test_independent_empty_is_not_cached_and_market_stays_separate(self):
        data={'web':{'results':[]}}
        def get(*a,**k):self.calls.append(k);return Response(data)
        client=SearchClient(env={'BRAVE_SEARCH_API_KEY':'test'},get=get,log=lambda s:None)
        def search(country='kw'):return client.search('brave_search','candle',country,'en',time.monotonic()+4,threading.Event())
        self.assertEqual(search()['organic_results'],[]);self.assertFalse(client.cache)
        data['web']['results']=[{'title':'Candle','url':'https://shop.example/p'}]
        self.assertTrue(search()['organic_results']);self.assertTrue(search()['organic_results'])
        search('sa');self.assertEqual(len(self.calls),3)


if __name__=='__main__':unittest.main()
