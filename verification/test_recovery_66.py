"""Regression scenarios for v66; no network, paid model or payment calls."""
import copy
import io
import json
import threading
import unittest
from collections import Counter
from concurrent.futures import Future
from contextlib import redirect_stdout
from types import SimpleNamespace
from test_audit_prices import scope, Clock
import test_audit_prices as audit_support
from test_media_backend import Inspector, ns as media_ns

INLINE = {'data':'YQ==','mime_type':'image/png'}

class AuditRecoveryTests(unittest.TestCase):
    def setup_request(self, replies, elapsed=None, kind='product', attached=True):
        self.clock, self.calls, self.seeds, self.progress = Clock(), [], [], []
        self.replies, self.elapsed = list(replies), list(elapsed or [1]*len(replies))
        candidate = {'id':0, 'title':'necklace','image_attached':attached}
        def stream(url,payload,timeout,on_text,*a,**kw):
            self.calls.append({'payload':copy.deepcopy(payload),'timeout':timeout,'at':self.clock.now})
            self.clock.now += self.elapsed.pop(0)
            answer = self.replies.pop(0)
            if isinstance(answer,Exception): raise answer
            finish, text = answer
            return {'candidates':[{'content':{'parts':[{'text':text}]},'finishReason':finish}]}, ''
        overrides = {
            'time':self.clock, 'DEFAULT_COUNTRY':'kw','COUNTRY_NAMES':{'kw':'Kuwait'},
            '_web_photo_match_context':lambda x:x, '_web_clean_classification_identity':lambda x:x or '',
            '_web_identity_candidates':lambda rows:[dict(candidate)],
            'WEB_VISUAL_CLASSIFIER_ENABLED':True,'WEB_VISUAL_CLASSIFIER_MAX_RESULTS':8,
            '_web_is_http_url':lambda x:bool(x),'_web_unproxy_image_url':lambda x:x,
            '_web_identity_content_key':lambda *a:'key', '_web_ai_classifier_cache_get':lambda *a:None,
            '_web_ai_classifier_cache_put':lambda *a:None,
            '_FINDZIA_MEDIA_PIXEL_POLICY':media_ns['PIXEL_POLICY'],
            '_WEB_VISUAL_PROFILE_TEXT_FIELDS':('category','brand','model'),
            '_WEB_VISUAL_PROFILE_LIST_FIELDS':('components','visible_text'),
            '_WEB_VISUAL_HARD_DIFFERENCE_AXES':{'model'},
            '_web_ai_reference_context':lambda *a:{'reference_source':'reference_image_only'},
            'GEMINI_FAST_MODEL':'test','GEMINI_BASE_URL':'https://invalid.test',
            'WEB_VISUAL_CLASSIFIER_TIMEOUT_SECONDS':35,'WEB_AI_CLASSIFIER_TIMEOUT_SECONDS':20,
            '_web_visual_normalize_profile':lambda x:x or {},
            '_web_photo_confirm_reference':lambda x,y:(x,[]),
            '_web_visual_item_axes':lambda item:{'category':'same'},
            '_web_enrich_candidate_profile_from_text':lambda profile,title:profile,
            '_web_result_classification_title':lambda row:row.get('title',''),
            '_web_visual_profile_states':lambda *a:{}, '_web_semantic_match_guard':lambda *a:None,
            '_web_match_guard_is_anchor_independent':lambda *a:False,
            '_web_match_guard_conflict_axis':lambda *a:None,
            '_web_identity_percentage_from_evidence':lambda *a:0,
            'WEB_VISUAL_CLASSIFIER_EXACT_SCORE':92,
            '_web_visual_exact_proof_failure':lambda *a:('insufficient_evidence',[]),
            'GEMINI_STATS_LOCK':threading.Lock(),'GEMINI_STATS':{'plain_calls':0},
            '_web_identity_stream_response':stream,'_web_identity_post_response':lambda *a:self.fail('unexpected nonstream'),
            '_gemini_usage_record':lambda *a,**k:None,'_web_identity_http_error':lambda *a:'http_402',
            '_api_cost_record':lambda *a:None,'WEB_IDENTITY_CONTENT_CACHE_TTL':60,
            'requests':SimpleNamespace(Timeout=TimeoutError),
            'app':SimpleNamespace(state=SimpleNamespace(product_media_inspector=SimpleNamespace(
                remember_audit=lambda inline,decision:self.seeds.append((inline,decision))))),
            '_web_visual_collect_evidence':lambda *a:self.fail('images were downloaded twice')}
        self.ns = scope(['_web_ai_classifier_request_live'],overrides)
        self.evidence = (INLINE,{0:INLINE} if attached else {})

    @staticmethod
    def answer(kind='product'):
        return json.dumps({'reference_profile':[{'field':'category','values':['necklace']}], 'items':[{
            'id':0,'match':'similar','market':'global','confidence':80,'identity_score':0,'observation_quality':80,
            'candidate_profile':[{'field':'category','values':['necklace']}], 'same_axes':['category'],
            'different_axes':[],'differences':[],'match_reason':'uncertain','market_reason':'foreign_storefront',
            'image_kind':kind}]})

    def invoke(self, streaming=True):
        with redirect_stdout(io.StringIO()):
            return self.ns['_web_ai_classifier_request_live']('necklace',[{'image':'https://test/image'}],
                {'country':'kw'}, {'image_b64':'reference'}, _prepared_evidence=self.evidence,
                progress_callback=self.progress.append if streaming else None)

    def test_truncation_retries_once_with_same_pixels_inside_original_deadline(self):
        self.setup_request([('MAX_TOKENS','{"reference_profile":['),('STOP',self.answer())],[8,2])
        result=self.invoke()
        self.assertEqual(len(self.calls),2)
        self.assertLessEqual(self.calls[1]['timeout'],27)
        self.assertEqual(self.calls[0]['payload']['contents'],self.calls[1]['payload']['contents'])
        self.assertGreater(self.calls[1]['payload']['generationConfig']['maxOutputTokens'],self.calls[0]['payload']['generationConfig']['maxOutputTokens'])
        self.assertEqual(result['items'][0]['match'],'similar')
        self.assertEqual(self.seeds,[(INLINE,'product')])

    def test_second_truncation_does_not_retry_or_seed_half_response(self):
        self.setup_request([('MAX_TOKENS','{"items":['),('MAX_TOKENS','{"items":[')])
        result=self.invoke()
        self.assertEqual(len(self.calls),2)
        self.assertEqual(result['review_error'],'output_truncated')
        self.assertEqual(self.seeds,[])

    def test_no_retry_when_original_deadline_has_less_than_four_seconds(self):
        self.setup_request([('MAX_TOKENS','{"items":[')],[32])
        self.assertEqual(self.invoke()['review_error'],'output_truncated')
        self.assertEqual(len(self.calls),1)

    def test_malformed_stop_is_rejected_without_blind_paid_retry(self):
        self.setup_request([('STOP','{"items":[')])
        self.assertEqual(self.invoke()['review_error'],'malformed_json')
        self.assertEqual(len(self.calls),1); self.assertEqual(self.seeds,[])

    def test_duplicate_keys_or_ids_never_seed_or_pass(self):
        for raw in [self.answer().replace('"id": 0','"id": 0, "id": 0'),
                    json.dumps(dict(json.loads(self.answer()), items=json.loads(self.answer())['items']*2))]:
            self.setup_request([('STOP',raw)])
            self.assertIn('review_error',self.invoke()); self.assertEqual(self.seeds,[])

    def test_uncertain_or_unattached_image_never_seeds_cache(self):
        for kind, attached in [('uncertain',True),('product',False)]:
            self.setup_request([('STOP',self.answer(kind))],attached=attached)
            self.invoke(); self.assertEqual(self.seeds,[])

    def test_timeout_is_not_retried(self):
        self.setup_request([TimeoutError('read timed out')])
        self.assertEqual(self.invoke()['review_error'],'timeout')
        self.assertEqual(len(self.calls),1)

    def test_payload_has_bounded_item_count_and_shared_image_policy(self):
        self.setup_request([('STOP',self.answer())]);self.invoke()
        p=self.calls[0]['payload']; items=p['generationConfig']['responseSchema']['properties']['items']
        self.assertEqual((items['minItems'],items['maxItems']),(1,1))
        self.assertIn(media_ns['PIXEL_POLICY'],p['systemInstruction']['parts'][0]['text'])

    def test_nonstream_duplicate_ids_cannot_seed_a_media_decision(self):
        raw=json.loads(self.answer());raw['items']*=2
        self.setup_request([])
        self.ns['_web_identity_post_response']=lambda *a:SimpleNamespace(status_code=200,json=lambda:{
            'candidates':[{'content':{'parts':[{'text':json.dumps(raw)}]},'finishReason':'STOP'}]})
        self.assertEqual(self.invoke(streaming=False)['review_error'],'duplicate_or_invalid_ids')
        self.assertEqual(self.seeds,[])

    def test_media_cache_failure_does_not_discard_completed_identity_audit(self):
        self.setup_request([('STOP',self.answer())])
        def unavailable(*a): raise RuntimeError('cache unavailable')
        self.ns['app'].state.product_media_inspector.remember_audit=unavailable
        self.assertEqual(len(self.invoke()['items']),1)

class PriceRecoveryTests(unittest.TestCase):
    setUp=audit_support.PriceTests.setUp
    recover=audit_support.PriceTests.recover

    def test_fourth_provider_response_is_not_discarded_after_30_rows(self):
        def records(data): return data.get('organic_results',[])[:30]
        self.ns['_web_indexed_media_records']=records
        entries={str(i):{'url':f'https://shop{i}.test/product/{1000000+i}'} for i in range(4)}
        def search(engine,term,*a,**kw):
            i=next(i for i in range(4) if f'shop{i}.test' in term)
            rows=[{'link':f'https://unrelated.test/{i}/{k}','title':'item'} for k in range(10)]
            if i==3: rows[9]={'link':entries['3']['url'],'price':'12 USD'}
            return {'organic_results':rows}
        self.ns['_fast_provider_search']=search
        result=self.recover(entries)
        self.assertIn('3',result);self.assertEqual(result['3']['price'],'12.0 USD')

    def test_rich_price_is_not_overwritten_by_unrelated_snippet_price(self):
        row={'url':'https://us.shein.com/A-p-1234567.html','export_store':True}
        self.responses['us']=[{'link':row['url'],'snippet':'Shipping $2.99.',
                              'rich_snippet':{'top':{'extensions':['$12.00']}}}]
        self.assertEqual(self.recover({'a':row})['a']['price'],'12.0 USD')

    def test_shipping_only_snippet_is_not_a_product_price(self):
        parser=self.ns['_local_discovery_plain_snippet_price']
        for snippet in ['Shipping $2.99.', '$2.99 shipping.', 'Free shipping on orders over $29.', 'Versand: 12 EUR']:
            self.assertEqual(parser({'snippet':snippet},'de' if 'EUR' in snippet else 'us'),'')
        self.assertEqual(parser({'snippet':'Price $12.00. Free shipping.'},'us'),'$12.00')

    def test_provider_unavailable_trace_is_distinct_from_empty_results(self):
        self.ns['_fast_provider_search']=lambda *a,**k:None
        with redirect_stdout(io.StringIO()) as out:
            self.ns['_web_targeted_price_updates']({'a':{'url':'https://de.shein.com/A-p-1234567.html'}},'ar',{'country':'kw'})
        self.assertIn('"reason": "provider_unavailable"',out.getvalue())

    def test_organic_adapter_preserves_structured_price_and_installment_context(self):
        ns=scope(['_serper_to_serpapi','_web_indexed_offer_quote'],{
            'current_market':lambda:{'country':'us'},'_fast_rich_snippet':lambda *a:None})
        rows=[{'link':'https://shop.test/product/1234567','title':'necklace',
               'price':{'value':'12.50','currency':'EUR'}}]
        data=ns['_serper_to_serpapi']('search',{'organic':rows})
        self.assertEqual(ns['_web_indexed_offer_quote'](data['organic_results'][0])['currency'],'EUR')
        rows[0]['installments_description']='monthly payment'
        data=ns['_serper_to_serpapi']('search',{'organic':rows})
        self.assertIsNone(ns['_web_indexed_offer_quote'](data['organic_results'][0]))

    def test_trace_distinguishes_absent_rejected_and_other_market_without_private_data(self):
        row={'url':'https://de.shein.com/A-p-1234567.html?sku=SECRET-SKU','export_store':True,'title':'PRIVATE TITLE'}
        samples=[([], 'empty_index'),
            ([{'link':row['url'],'snippet':'No price in index'}],'price_absent'),
            ([{'link':row['url'],'price':'Save 10 EUR'}],'price_rejected'),
            ([{'link':row['url'].replace('de.shein','fr.shein'),'price':'10 EUR'}],'other_storefront_only'),
            ([{'link':row['url'].replace('SECRET-SKU','other'),'price':'10 EUR'}],'variant_or_query_mismatch')]
        for records,reason in samples:
            self.responses['de']=records
            with redirect_stdout(io.StringIO()) as out:
                self.ns['_web_targeted_price_updates']({'a':row},'ar',{'country':'kw'})
            text=out.getvalue()
            self.assertIn('"reason": "'+reason+'"',text)
            for secret in ('SECRET-SKU','PRIVATE TITLE','Save 10 EUR',row['url']): self.assertNotIn(secret,text)

class MediaReuseTests(unittest.TestCase):
    def make(self,fetch=lambda url:INLINE,judge=None):
        self.calls=[]
        def classify(*a,**k):
            self.calls.append(k)
            return {'images':[{'id':i,'kind':'product'} for i,_ in enumerate(k['images'])]}
        inspector=Inspector(fetch,judge or classify);self.addCleanup(inspector.shutdown);return inspector

    def test_completed_audit_reused_for_identical_bytes_on_different_url(self):
        ins=self.make();self.assertTrue(ins.remember_audit(INLINE,'product'))
        self.assertEqual(ins.inspect('https://different.test/a').result(2),'product')
        self.assertEqual(self.calls,[]);self.assertEqual(ins.stats['audit_reused'],1)

    def test_known_logo_stays_rejected(self):
        ins=self.make();ins.remember_audit(INLINE,'logo')
        self.assertEqual(ins.inspect('https://test/a').result(2),'logo');self.assertEqual(self.calls,[])

    def test_changed_bytes_and_uncertain_audits_require_independent_check(self):
        ins=self.make(fetch=lambda url:dict(INLINE,data='Yg=='))
        ins.remember_audit(INLINE,'product')
        self.assertFalse(ins.remember_audit(dict(INLINE,data='Yg=='),'uncertain'))
        self.assertEqual(ins.inspect('https://test/a').result(2),'product');self.assertEqual(len(self.calls),1)

    def test_seed_does_not_override_active_or_existing_independent_check(self):
        began,release=threading.Event(),threading.Event()
        def judge(*a,**k):
            began.set();release.wait(2)
            return {'images':[{'id':0,'kind':'logo'}]}
        ins=self.make(judge=judge)
        f=ins.inspect('https://test/a');self.assertTrue(began.wait(2))
        self.assertFalse(ins.remember_audit(INLINE,'product'));release.set()
        self.assertEqual(f.result(2),'logo')
        self.assertFalse(ins.remember_audit(INLINE,'product'))

    def test_busy_workers_batch_backlog_and_complete_all_images(self):
        gate,started=threading.Event(),threading.Event();sizes=[];lock=threading.Lock()
        def judge(*a,**k):
            with lock:
                sizes.append(len(k['images']))
                if len(sizes)>=2:started.set()
            gate.wait(3)
            return {'images':[{'id':i,'kind':'product'} for i in range(len(k['images']))]}
        ins=self.make(fetch=lambda url:dict(INLINE,data=url.encode().hex()),judge=judge)
        futures=[]
        for i in range(2):
            f=Future();futures.append(f);ins.load('image'+str(i),f);ins.flush()
        self.assertTrue(started.wait(2))
        for i in range(2,22):
            f=Future();futures.append(f);ins.load('image'+str(i),f);ins.flush()
        self.assertEqual(len(sizes),2)
        gate.set()
        self.assertEqual([f.result(3) for f in futures],['product']*22)
        self.assertLessEqual(len(sizes),5);self.assertEqual(sum(sizes),22)
        self.assertTrue(all(size<=8 for size in sizes))

if __name__=='__main__':unittest.main(verbosity=2)
