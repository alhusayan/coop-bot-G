"""Production functions loaded by AST; transport/provider calls are simulated.

No imports of the application's startup hooks and no paid/network requests.
Price parsers, URL binding and the functions under test run unchanged.
"""
import ast
import copy
import hashlib
import io
import json
import math
import os
import re
import threading
import time
import unittest
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from contextlib import redirect_stdout
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import SimpleNamespace

SOURCE = Path(os.environ.get('FINDZIA_TEST_MAIN', Path(__file__).parents[1] / 'main.py'))
TREE = ast.parse(SOURCE.read_text())
NODES = {}
for node in TREE.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        NODES[node.name] = node
    elif isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                NODES[target.id] = node

def scope(roots, overrides=None):
    ns = dict(re=re, json=json, urllib=urllib, time=time, copy=copy, os=os, math=math, hashlib=hashlib, Counter=Counter,
              threading=threading, Decimal=Decimal, InvalidOperation=InvalidOperation,
              ThreadPoolExecutor=ThreadPoolExecutor, __name__='findzia_test')
    ns.update(overrides or {})
    loading = set()
    def load(name):
        if name in ns or name in loading or name not in NODES:
            return
        loading.add(name)
        node = copy.deepcopy(NODES[name])
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                load(child.id)
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), 'exec'), ns)
        loading.remove(name)
    for root in roots:
        load(root)
    return ns

class Clock:
    def __init__(self): self.now = 0.0
    def monotonic(self): return self.now
    def time(self): return self.now

class Event:
    def __init__(self, clock, ready_at=float('inf'), on_wait=None):
        self.clock, self.ready_at, self.on_wait = clock, ready_at, on_wait
    def is_set(self): return self.clock.now >= self.ready_at
    def set(self): self.ready_at = self.clock.now
    def wait(self, seconds):
        self.clock.now += min(seconds, max(0, self.ready_at - self.clock.now))
        if self.on_wait: self.on_wait()
        return self.is_set()

class StreamTests(unittest.TestCase):
    def run_stream(self, events, *, trailing_failure=True):
        class Timeout(Exception): pass
        response = SimpleNamespace(status_code=200, closed=False)
        def lines(**kwargs):
            for event in events:
                yield 'data: ' + json.dumps(event)
                yield ''
            if trailing_failure: raise Timeout('connection did not close')
        response.iter_lines = lines
        def close(r): r.closed = True
        updates, usage = [], []
        ns = scope(['_web_identity_stream_response'], {
            'requests': SimpleNamespace(post=lambda *a, **k: response, Timeout=Timeout),
            'GEMINI_API_KEY': 'test', '_api_cost_record': lambda *a: None,
            '_web_safe_response_close': close, '_web_identity_http_error': lambda r: '',
            '_gemini_usage_record': lambda *a, **k: usage.append((a,k)),
            'GEMINI_STATS_LOCK': threading.Lock(), 'GEMINI_STATS': {'plain_calls': 0}})
        try:
            result = ns['_web_identity_stream_response']('https://test/models/model:generateContent', {}, 35, updates.append)
            return result, updates, usage, response
        except Timeout:
            self.assertTrue(response.closed)
            raise

    def test_terminal_answer_does_not_wait_for_connection_close(self):
        result, updates, usage, response = self.run_stream([
            {'candidates':[{'content':{'parts':[{'text':'{"items":'}]}}]},
            {'candidates':[{'content':{'parts':[{'text':'[]}'},{'text':'hidden','thought':True}]},'finishReason':'STOP'}],
             'usageMetadata':{'totalTokenCount':17}}])
        self.assertEqual(result[1], '')
        self.assertEqual(updates[-1], '{"items":[]}')
        self.assertEqual(result[0]['usageMetadata']['totalTokenCount'],17)
        self.assertTrue(usage[0][1]['complete'] and response.closed)

    def test_truncation_is_preserved_for_existing_validator(self):
        result, _, _, _ = self.run_stream([{'candidates':[{'content':{'parts':[{'text':'{"items":['}]},'finishReason':'MAX_TOKENS'}]}])
        self.assertEqual(result[0]['candidates'][0]['finishReason'],'MAX_TOKENS')
        self.assertEqual(result[0]['candidates'][0]['content']['parts'][0]['text'],'{"items":[')

    def test_nonterminal_stream_still_times_out(self):
        with self.assertRaisesRegex(Exception, 'connection did not close'):
            self.run_stream([{'candidates':[{'content':{'parts':[{'text':'{"items":['}]}}]}])

    def test_unspecified_finish_is_not_completion(self):
        result, _, _, _ = self.run_stream([
            {'candidates':[{'content':{'parts':[{'text':'abc'}]},'finishReason':'FINISH_REASON_UNSPECIFIED'}]},
            {'candidates':[{'content':{'parts':[{'text':'def'}]},'finishReason':'STOP'}]}])
        self.assertEqual(result[0]['candidates'][0]['content']['parts'][0]['text'],'abcdef')

class AuditWaitTests(unittest.TestCase):
    def make(self, shared_ready=float('inf')):
        clock = Clock()
        shared = Event(clock, shared_ready)
        shared._findzia_proof = {'item':{'id':1,'match':'exact'}, 'reference_profile':{'kind':'test'}}
        rows = [{'_classification_id':i,'image':'https://test/image'} for i in range(2)]
        def live(*args, **kwargs):
            clock.now += 35
            return {'items':[{'id':0,'match':'exact'}], 'reference_profile':{'kind':'test'}}
        overrides = {
            'time':clock, 'WEB_IDENTITY_OFFER_CACHE_ENABLED':True,
            'WEB_VISUAL_CLASSIFIER_ENABLED':True, 'WEB_AI_CLASSIFIER_MAX_RESULTS':8,
            'WEB_VISUAL_CLASSIFIER_MAX_RESULTS':8, 'WEB_VISUAL_CLASSIFIER_TIMEOUT_SECONDS':35,
            'WEB_IDENTITY_CONTENT_CACHE_TTL':60,
            'WEB_IDENTITY_OFFER_INFLIGHT_LOCK':threading.Lock(), 'WEB_IDENTITY_OFFER_INFLIGHT':{'1':shared},
            '_web_photo_match_context':lambda x:x,
            '_web_visual_collect_evidence':lambda *a:('reference',{0:'image0',1:'image1'}),
            '_web_identity_candidates':lambda r:[{'id':x['_classification_id']} for x in r],
            '_web_identity_offer_content_key':lambda candidate,*a:str(candidate['id']),
            '_web_identity_offer_proof':lambda value:value if value and value.get('item') else None,
            '_web_ai_classifier_cache_get':lambda k:None,
            '_web_ai_classifier_cache_put':lambda *a:None,
            '_web_identity_offer_cache_trim':lambda:None,
            '_web_share_media_audit':lambda *a:None,
            '_api_cost_record':lambda *a:None,
            '_web_ai_classifier_request_live':live,
            '_web_is_http_url':lambda s:s.startswith('https://'), '_web_unproxy_image_url':lambda s:s,
            '_web_identity_review_failure':lambda err,*a:{'review_error':err},
        }
        return clock, rows, scope(['_web_ai_classifier_request'], overrides)

    def test_overlap_has_one_wait_window_not_two(self):
        clock, rows, ns = self.make()
        with redirect_stdout(io.StringIO()):
            result = ns['_web_ai_classifier_request']('',rows,{}, {'image_b64':'test'})
        self.assertLessEqual(clock.now,41.00001)
        self.assertEqual([x['id'] for x in result['items']],[0])
        self.assertEqual(result['review_error'],'partial_offer_review')
        self.assertNotIn('0',ns['WEB_IDENTITY_OFFER_INFLIGHT'])

    def test_other_owner_finishing_within_window_is_preserved(self):
        clock, rows, ns = self.make(40)
        with redirect_stdout(io.StringIO()):
            result = ns['_web_ai_classifier_request']('',rows,{}, {'image_b64':'test'})
        self.assertEqual([x['id'] for x in result['items']],[0,1])
        self.assertNotIn('review_error',result)
        self.assertAlmostEqual(clock.now,40)

    def test_cancel_duplicate_batch_stops_wait_without_cancelling_owner(self):
        clock, cancel = Clock(), threading.Event()
        owner = Event(clock, on_wait=cancel.set)
        ns = scope(['_web_ai_classify_captured_batch'], {
            'time':clock,'WEB_AI_CLASSIFIER_ENABLED':True, 'GEMINI_API_KEY':'test',
            'WEB_VISUAL_CLASSIFIER_TIMEOUT_SECONDS':35,'WEB_AI_CLASSIFIER_TIMEOUT_SECONDS':35,
            'WEB_VISUAL_CLASSIFIER_FETCH_TIMEOUT_SECONDS':4,
            'WEB_AI_CLASSIFIER_INFLIGHT_LOCK':threading.Lock(),'WEB_AI_CLASSIFIER_INFLIGHT':{'key':owner},
            '_web_photo_match_context':lambda x:x, '_web_ai_classifier_cache_key':lambda *a:'key',
            '_web_ai_classifier_cache_get':lambda *a:None, '_web_ai_classifier_cache_put':lambda *a:None,
            '_web_ai_classifier_request':lambda *a,**k:self.fail('unexpected duplicate request'),
            '_web_identity_review_failure':lambda err,*a:{'review_error':err}})
        result = ns['_web_ai_classify_captured_batch']('',[{}],{}, {'image_b64':'test'},cancel)
        self.assertEqual(result[1],'cancelled')
        self.assertLessEqual(clock.now,.11)
        self.assertFalse(owner.is_set())

class PriceTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.responses = {}
        def search(engine, term, cc, hl, timeout, **kw):
            self.calls.append((term,cc,hl))
            return {'organic_results':self.responses.get(cc,[])}
        def host_match(url, cc):
            host = urllib.parse.urlsplit(url or '').hostname or ''
            return host.endswith('.shein.com') or host in ('shein.com','www.aliexpress.com')
        overrides = {
            'current_market':lambda:{'country':'kw','currency':'KWD'},
            '_global_store_match':host_match, '_web_collection_url':lambda url:False,
            '_fz_social_row':lambda row:False, '_fz_regional_price_store':lambda url:False,
            '_fz_regional_index_quote':lambda *a:None,
            '_indexed_recovery_allowed':lambda:True, 'MARKET_CTX':threading.local(),
            'SERPAPI_API_KEY':'test','WEB_LIVE_PRICE_WAIT':10,
            'FAST_PROVIDERS':['test'],'_fast_provider_supports_operators':lambda p:True,
            '_fast_provider_search':search,'_web_shein_product_id':lambda url:'1234567' if 'shein.com' in url else '',
            '_web_shein_index_fetch':lambda *a:self.fail('unexpected image request'),
            '_serpapi_cached_json':lambda *a,**k:self.fail('unexpected fallback'),
            '_SEARCHAPI_ROUTER':SimpleNamespace(enabled=False,economy=False),
            'FINDZIA_GROUPED_RECOVERY_ENABLED':False,'WEB_ASYNC_PRICE_SHARED_MARKETS':4,
            '_web_indexed_media_records':lambda data:data.get('organic_results',[]),
            '_local_discovery_direct_link':lambda row:row.get('link',''),
            '_local_discovery_title':lambda row:row.get('title',''),
            '_findzia_hard_product_mismatch':lambda a,b: a=='DIFFERENT',
            '_web_offer_image_candidates':lambda row:[], '_fz_same_image_listing':lambda *a:False,
            '_web_live_quote_fields':lambda q,m:{'price':str(q['min'])+' '+q['currency'],'currency':q['currency']},
        }
        self.ns = scope(['_web_listing_price_country','_web_automatic_price_batches',
                         '_web_targeted_price_updates','_web_confirmable_price'], overrides)

    def recover(self, entries):
        with redirect_stdout(io.StringIO()):
            return self.ns['_web_targeted_price_updates'](entries,'ar',{'country':'kw','currency':'KWD'})

    def test_french_shein_euro_snippet_survives_recovery_and_final_gate(self):
        row = {'url':'https://fr.shein.com/Old-Name-p-1234567.html','title':'necklace','country':'cn','export_store':True}
        link = 'https://fr.shein.com/New-Name-p-1234567.html'
        self.responses['fr'] = [{'link':link,'title':'necklace','snippet':'Prix 12,50 €.'}]
        changes = self.recover({'offer':row})
        self.assertEqual(self.calls[0][1:3],('fr','fr'))
        self.assertEqual(changes['offer']['currency'],'EUR')
        self.assertEqual(changes['offer']['price_source_url'],link)
        self.assertFalse(changes['offer']['price_verified'])
        self.assertTrue(self.ns['_web_confirmable_price'](dict(row,**changes['offer'])))

    def test_mixed_markets_use_independent_retrieval_and_currency_context(self):
        entries = {cc:{'url':f'https://{cc}.shein.com/Necklace-p-1234567.html','country':'cn','export_store':True}
                   for cc in ('de','us','ca')}
        for cc, price in [('de','12,50 €'),('us','$14.50'),('ca','$19.50')]:
            self.responses[cc] = [{'link':entries[cc]['url'],'snippet':price}]
        changes = self.recover(entries)
        self.assertEqual({c[1] for c in self.calls},{'de','us','ca'})
        self.assertEqual({cc:v['currency'] for cc,v in changes.items()},{'de':'EUR','us':'USD','ca':'CAD'})

    def test_slug_change_still_requires_same_product_market_and_variant(self):
        match = self.ns['_web_same_index_listing']
        original = 'https://fr.shein.com/A-p-1234567.html?sku=red&currency=EUR'
        self.assertTrue(match(original,original.replace('/A-','/B-')))
        for url in [original.replace('1234567','7654321'),original.replace('fr.shein','de.shein'),
                    original.replace('sku=red','sku=blue'),original.replace('EUR','USD'),
                    original.replace('/A-','/en/A-')]:
            self.assertFalse(match(original,url))

    def test_indexed_price_cannot_lose_binding_or_gain_verification(self):
        row = {'url':'https://fr.shein.com/A-p-1234567.html','price':'12 EUR','currency':'EUR',
               'price_source':'exact_listing_index','price_verified':False}
        self.assertFalse(self.ns['_web_confirmable_price'](row))
        self.assertFalse(self.ns['_web_confirmable_price'](dict(row,price_source_url=row['url'].replace('fr.shein','de.shein'))))

    def test_no_price_borrowed_from_another_storefront_or_variant(self):
        row = {'url':'https://de.shein.com/A-p-1234567.html?sku=red','export_store':True}
        self.responses['de'] = [
            {'link':row['url'].replace('de.shein','us.shein'),'price':'10 USD'},
            {'link':row['url'].replace('sku=red','sku=blue'),'price':'9 EUR'}]
        self.assertEqual(self.recover({'offer':row}),{})

    def test_missing_ambiguous_or_discount_price_stays_missing(self):
        row = {'url':'https://de.shein.com/A-p-1234567.html','export_store':True}
        for snippet in ['', 'Was 20 EUR now 10 EUR','Save 10 EUR','12 EUR or 15 EUR']:
            with self.subTest(snippet=snippet):
                self.responses['de']=[{'link':row['url'],'snippet':snippet}]
                self.assertEqual(self.recover({'offer':row}),{})

    def test_arabic_host_is_not_argentina_and_other_export_behavior_is_preserved(self):
        cc = self.ns['_web_listing_price_country']
        self.assertEqual(cc({'url':'https://ar.shein.com/A-p-1234567.html','export_store':True},{'country':'kw'}),'us')
        self.assertEqual(cc({'url':'https://uk.shein.com/A-p-1234567.html','export_store':True},{}),'gb')
        self.assertEqual(cc({'url':'https://www.aliexpress.com/item/1234567.html','export_store':True},{}),'us')

    def test_batches_and_optional_grouping_never_merge_storefront_countries(self):
        entries = {cc:{'url':f'https://{cc}.shein.com/A-p-1234567.html','export_store':True} for cc in ('de','fr','us')}
        batches = self.ns['_web_automatic_price_batches'](entries)
        self.assertEqual(len(batches),3)
        self.ns['_SEARCHAPI_ROUTER'].enabled = self.ns['_SEARCHAPI_ROUTER'].economy = True
        self.ns['FINDZIA_GROUPED_RECOVERY_ENABLED'] = True
        self.recover(entries)
        self.assertEqual({call[1] for call in self.calls},{'de','fr','us'})

    def test_fallback_provider_receives_per_listing_country_and_query(self):
        calls = []
        self.ns['FAST_PROVIDERS'] = []
        self.ns['_serpapi_cached_json'] = lambda request,**kw: calls.append(request) or {}
        self.recover({'offer':{'url':'https://fr.shein.com/A-p-1234567.html','export_store':True}})
        self.assertEqual((calls[0]['gl'],calls[0]['hl'],calls[0]['engine']),('fr','fr','google'))
        self.assertIn('1234567',calls[0]['q'])

    def test_image_only_shein_recovery_keeps_image_engine_without_price_update(self):
        calls = []
        self.ns['_web_shein_index_fetch'] = lambda request,budget: calls.append(request) or {}
        with redirect_stdout(io.StringIO()):
            result = self.ns['_web_targeted_price_updates'](
                {'offer':{'url':'https://de.shein.com/A-p-1234567.html','export_store':True}},
                'ar',{'country':'kw'},image_only=True)
        self.assertEqual((calls[0]['gl'],calls[0]['hl'],calls[0]['engine']),('de','de','test_images'))
        self.assertNotIn('num',calls[0])
        self.assertEqual(result,{})

if __name__ == '__main__': unittest.main(verbosity=2)
