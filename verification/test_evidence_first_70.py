"""Real production functions with deterministic provider/HTTP boundaries."""
import asyncio
import contextlib
import io
import json
import threading
import unittest
from types import SimpleNamespace
from test_audit_prices import scope, Clock
import test_audit_prices as price_support
from test_recovery_66 import INLINE
import test_recovery_66 as audit_support
import test_compact_upload_69 as timing_support


class MissingImageTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.fetches = []
        self.statuses = {}
        def fetch(url, **kw):
            self.fetches.append(url)
            return SimpleNamespace(status_code=self.statuses.get(url,200), headers={'content-type':'image/jpeg'})
        self.ns = scope(['_web_visual_candidate_inline'], {
            'time':self.clock, '_SOCIAL':SimpleNamespace(), '_fz_social_row':lambda row:False,
            '_web_unproxy_image_url':lambda url:url,
            '_web_offer_image_candidates':lambda row:row.get('images',[]),
            '_web_is_http_url':lambda url:url.startswith('https://'),
            '_web_visual_host_allowed':lambda host:True,
            '_web_safe_get':fetch,'_web_safe_response_close':lambda r:None,
            '_web_read_limited_response':lambda *a: b'image',
            '_web_visual_inline_from_bytes':lambda body:dict(INLINE),
            'WEB_VISUAL_CLASSIFIER_FETCH_TIMEOUT_SECONDS':2,
            'WEB_VISUAL_CLASSIFIER_MAX_DOWNLOAD_BYTES':1000,
            'HEADERS':{},'WEB_IMAGE_CACHE_TTL_SECONDS':60,
            'WEB_VISUAL_IMAGE_CACHE':{},'WEB_VISUAL_IMAGE_CACHE_LOCK':threading.Lock()})

    def invoke(self,row,force=True):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.ns['_web_visual_candidate_inline'](row,force)

    def test_missing_primary_is_not_retried_but_valid_alternative_is_refreshed(self):
        bad,good='https://img.test/missing','https://img.test/working'
        self.statuses[bad]=404
        row={'image':bad,'images':[good]}
        self.assertEqual(self.invoke(row)['source_url'],good)
        self.assertEqual(self.invoke(row)['source_url'],good)
        self.assertEqual(self.fetches,[bad,good,good])

    def test_missing_url_is_retried_after_thirty_seconds(self):
        url='https://img.test/gone';self.statuses[url]=410
        self.assertIsNone(self.invoke({'image':url}))
        self.assertIsNone(self.invoke({'image':url}))
        self.statuses[url]=200;self.clock.now=30.1
        self.assertTrue(self.invoke({'image':url}))
        self.assertEqual(self.fetches,[url,url])

    def test_rate_limit_and_server_failure_are_not_definitive_misses(self):
        for status in (429,500,503):
            url=f'https://img.test/{status}';self.statuses[url]=status
            self.assertIsNone(self.invoke({'image':url}))
            self.statuses[url]=200
            self.assertTrue(self.invoke({'image':url}))
            self.assertEqual(self.fetches.count(url),2)

    def test_media_fetch_recovers_after_429_without_force_refresh(self):
        url='https://img.test/transient';self.statuses[url]=429
        self.assertIsNone(self.invoke({'image':url},False))
        self.statuses[url]=200
        self.assertTrue(self.invoke({'image':url},False))
        self.assertEqual(self.fetches,[url,url])

    def test_failed_refresh_revokes_previously_cached_pixels(self):
        url='https://img.test/changed'
        self.assertTrue(self.invoke({'image':url}))
        self.statuses[url]=404
        self.assertIsNone(self.invoke({'image':url}))
        self.clock.now=31
        self.assertIsNone(self.invoke({'image':url},False))
        self.assertEqual(len(self.fetches),3)

    def test_changed_signed_url_can_recover_immediately(self):
        old='https://img.test/p?signature=old';new='https://img.test/p?signature=new'
        self.statuses[old]=404;self.invoke({'image':old})
        self.assertTrue(self.invoke({'image':new}))


class EvidenceTests(unittest.TestCase):
    def test_no_paid_live_request_without_candidate_pixels(self):
        fixture=audit_support.AuditRecoveryTests();fixture.setup_request([],attached=False)
        value=fixture.invoke()
        self.assertEqual(value['review_error'],'candidate_images_unavailable')
        self.assertEqual(fixture.calls,[]);self.assertEqual(fixture.seeds,[])

    def test_mixed_batch_sends_only_attached_candidate_with_original_id(self):
        fixture=audit_support.AuditRecoveryTests();fixture.setup_request([('STOP',fixture.answer())])
        # Put the missing candidate first to catch position/id reassignment.
        fixture.ns['_web_identity_candidates']=lambda rows:[
            {'id':r['_classification_id'],'title':'necklace'} for r in rows]
        rows=[{'_classification_id':7,'title':'missing'}, {'_classification_id':0,'title':'ready'}]
        with contextlib.redirect_stdout(io.StringIO()):
            result=fixture.ns['_web_ai_classifier_request_live']('necklace',rows,{'country':'kw'},
                {'image_b64':'ref'},_prepared_evidence=(INLINE,{0:INLINE}),progress_callback=lambda _:None)
        self.assertEqual([r['id'] for r in result['items']],[0])
        self.assertEqual(len(fixture.calls),1)
        schema=fixture.calls[0]['payload']['generationConfig']['responseSchema']
        self.assertEqual(schema['properties']['items']['maxItems'],1)
        self.assertEqual(rows[0]['_classification_id'],7)

    def test_missing_offer_does_not_own_singleflight_or_start_model(self):
        ns=scope(['_web_ai_classifier_request'],{
            '_web_photo_match_context':lambda v:v,'WEB_IDENTITY_OFFER_CACHE_ENABLED':True,
            '_web_share_media_audit':lambda *a:None,'_web_ai_classifier_cache_get':lambda *a:None,
            '_web_ai_classifier_cache_put':lambda *a:None,'_web_identity_offer_proof':lambda v:v,
            '_api_cost_record':lambda *a:None,
            'WEB_VISUAL_CLASSIFIER_ENABLED':True,
            '_web_visual_collect_evidence':lambda *a:(INLINE,{}),
            '_web_identity_candidates':lambda rows:[{'id':3,'title':'missing'}],
            'WEB_AI_CLASSIFIER_MAX_RESULTS':8,
            '_web_ai_classifier_request_live':lambda *a,**kw:self.fail('paid work without pixels'),
            '_web_identity_offer_content_key':lambda *a:self.fail('unproven cache ownership')})
        with contextlib.redirect_stdout(io.StringIO()):
            result=ns['_web_ai_classifier_request']('x',[{}],{}, {'image_b64':'ref'})
        self.assertEqual(result['review_error'],'candidate_images_unavailable')


class PriceRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.f=price_support.PriceTests();self.f.setUp();self.ns=self.f.ns
        self.ns['_web_offer_image_candidates']=lambda row:row.get('images',[])
        self.clock=Clock();self.ns['time']=self.clock
        self.row={'url':'https://shop.test/products/woven-basket','country':'kw','title':'Woven basket',
                  'images':['https://img.test/a']}

    def invoke(self,row=None,**kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.ns['_web_targeted_price_updates']({'a':row or self.row},'en',{'country':'kw'},**kwargs)

    def test_query_targets_asin_or_product_path_not_generic_title(self):
        self.invoke()
        self.assertEqual(self.f.calls[0][0],'(site:shop.test/products/woven-basket)')
        row=dict(self.row,url='https://www.amazon.sg/dp/B012345678',country='sg')
        self.invoke(row)
        self.assertIn('"B012345678"',self.f.calls[-1][0])

    def test_successful_empty_lookup_cools_down_then_recovers(self):
        self.invoke();self.invoke()
        self.assertEqual(len(self.f.calls),1)
        self.f.responses['kw']=[{'link':self.row['url'],'price':'10 KWD'}]
        self.clock.now=46
        self.assertEqual(self.invoke()['a']['price'],'10.0 KWD')
        self.assertEqual(len(self.f.calls),2)

    def test_provider_errors_do_not_enter_empty_index_cache(self):
        self.ns['_fast_provider_search']=lambda *a,**k:{'error':'unavailable'}
        self.invoke()
        self.ns['_fast_provider_search']=lambda *a,**k:{'organic_results':[{'link':self.row['url'],'price':'10 KWD'}]}
        self.assertIn('a',self.invoke())

    def test_variant_and_market_keep_separate_miss_keys(self):
        self.invoke()
        self.invoke(dict(self.row,url=self.row['url']+'?variant=1'))
        self.invoke(dict(self.row,country='de'))
        self.assertEqual(len(self.f.calls),3)

    def test_queue_uses_budget_for_untried_listing_after_recent_miss(self):
        self.invoke()
        other=dict(self.row,url='https://other.test/products/basket')
        batches=self.ns['_web_automatic_price_batches']({'miss':self.row,'fresh':other})
        self.assertEqual(list(batches[0]),['fresh'])

    def test_wrong_listing_and_wrong_variant_still_cannot_supply_price(self):
        self.f.responses['kw']=[{'link':self.row['url']+'?variant=OTHER','price':'10 KWD'},
                                {'link':'https://shop.test/products/other','price':'5 KWD'}]
        self.assertEqual(self.invoke(),{})

    def test_price_miss_does_not_block_image_only_repair(self):
        self.invoke();self.invoke(image_only=True)
        self.assertEqual(len(self.f.calls),2)


class MetricsTests(unittest.TestCase):
    metric={'search_trace':'ab'*16,'kind':'image','country':'kw','version':'156.7.70',
            'first_card_ms':1234,'visible_count':3}

    def test_metric_only_keeps_counters_and_random_trace(self):
        fn=scope(['_web_client_card_metric'])['_web_client_card_metric']
        value=fn(dict(self.metric,query='PRIVATE',image='SECRET',email='PRIVATE'))
        self.assertNotIn('PRIVATE',json.dumps(value));self.assertNotIn('SECRET',json.dumps(value))
        self.assertEqual(value['measurement'],'client_after_render')

    def test_invalid_metrics_cannot_inject_logs(self):
        fn=scope(['_web_client_card_metric'])['_web_client_card_metric']
        for k,v in [('search_trace','\nFORGED'),('first_card_ms',True),('first_card_ms',180001),
                    ('visible_count',0),('visible_count',-1),('kind','https://private'),('country','kw\n')]:
            with self.assertRaises(ValueError):fn(dict(self.metric,**{k:v}))

    def test_timing_records_trace_without_logging_headers(self):
        cls=timing_support.TimingTests().timing_class(Clock())
        async def app(scope,receive,send):
            await send({'type':'http.response.start','status':200})
        async def send(msg):pass
        async def receive():return {'type':'http.request','body':b''}
        with contextlib.redirect_stdout(io.StringIO()) as log:
            asyncio.run(cls(app)({'type':'http','method':'POST','path':'/api/search/stream',
                'headers':[(b'x-findzia-search-trace',b'ab'*16),(b'authorization',b'SECRET')]},receive,send))
        self.assertIn('SEARCH REQUEST TIMING',log.getvalue())
        self.assertIn('ab'*16,log.getvalue());self.assertNotIn('SECRET',log.getvalue())

    def endpoint(self, chunks, allowed=True):
        class App:
            def post(self,path):return lambda fn:fn
        class Request:
            async def stream(self):
                for chunk in chunks:yield chunk
        ns=scope(['web_api_search_metrics'],{'app':App(),'Request':Request,
            'Response':lambda **kw:SimpleNamespace(**kw),'ClientDisconnect':ConnectionError,
            '_web_rate_allowed':lambda *a,**kw:allowed})
        with contextlib.redirect_stdout(io.StringIO()) as log:
            response=asyncio.run(ns['web_api_search_metrics'](Request()))
        return response.status_code,log.getvalue()

    def test_endpoint_accepts_chunked_metric_and_rejects_large_body(self):
        body=json.dumps(self.metric).encode()
        status,log=self.endpoint([body[:20],body[20:]])
        self.assertEqual(status,204);self.assertIn('CLIENT FIRST CARD',log)
        status,log=self.endpoint([b' '*500,b' '*525])
        self.assertEqual(status,413);self.assertEqual(log,'')

    def test_metrics_rate_limit_and_bad_json_have_no_logged_payload(self):
        self.assertEqual(self.endpoint([b'SECRET'],False),(429,''))
        self.assertEqual(self.endpoint([b'SECRET']),(400,''))


if __name__=='__main__':unittest.main()
