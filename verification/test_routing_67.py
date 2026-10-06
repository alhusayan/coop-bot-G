"""Regression cases from production: signed snapshots, late exports, real queue batches.

Production functions execute unchanged; transport/model calls are fixtures.
No live searches, payments or deployment are performed.
"""
import asyncio
import base64
import hashlib
import hmac
import io
import json
import threading
import unittest
from concurrent.futures import Future, ThreadPoolExecutor, wait, FIRST_COMPLETED
from contextlib import redirect_stdout
from types import SimpleNamespace
from test_audit_prices import scope
import test_audit_prices as price_support
from test_media_backend import ns as media_ns, Inspector, judge
from test_recovery_66 import INLINE
import test_recovery_66 as audit_support

class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.support=price_support.PriceTests();self.support.setUp();self.ns=self.support.ns
        self.ns['WEB_ASYNC_PRICE_SHARED_MARKETS']=2

    def test_late_shein_gets_final_slot_after_early_local(self):
        batch=self.ns['_web_automatic_price_batches']
        early={'local':{'url':'https://local.test/dress','country':'kw'}}
        self.assertEqual(list(batch(early)[0]),['local'])
        late={str(i):{'url':f'https://kw{i}.test/dress','country':'kw'} for i in range(20)}
        late['shein']={'url':'https://us.shein.com/Dress-p-1234567.html','export_store':True}
        selected=batch(late,early)[:1]
        self.assertEqual(list(selected[0]),['shein'])
        # No extra batch/lookup allowance, and the exact regional binding still runs.
        self.support.responses['us']=[{'link':late['shein']['url'],'price':'12 USD'}]
        with redirect_stdout(io.StringIO()):
            result=self.ns['_web_targeted_price_updates'](selected[0],'ar',{'country':'kw'})
        self.assertIn('shein',result)
        self.assertEqual(self.support.calls[-1][1],'us')

    def test_local_priority_is_retained_on_first_attempt(self):
        rows={'us':{'url':'https://us.shein.com/A-p-1234567.html','export_store':True},
              'kw':{'url':'https://local.test/product','country':'kw'}}
        self.assertEqual(list(self.ns['_web_automatic_price_batches'](rows)[0]),['kw'])

    def test_served_merchant_does_not_monopolize_local_fallback(self):
        tried={'a':{'url':'https://a.test/product','country':'kw'}}
        rows={str(i):{'url':f'https://a.test/product{i}','country':'kw'} for i in range(8)}
        rows['b']={'url':'https://b.test/product','country':'kw'}
        batches=self.ns['_web_automatic_price_batches'](rows,tried)
        self.assertEqual(next(iter(batches[0])),'b')
        self.assertTrue(all(len(batch)<=4 for batch in batches));self.assertLessEqual(len(batches),2)

    def test_us_domestic_and_export_rows_share_slot_without_mixing_countries(self):
        tried={'local':{'url':'https://local.test/product','country':'kw'}}
        rows={f'us{i}':{'url':f'https://store{i}.test/product','country':'us'} for i in range(12)}
        rows.update({f'shein{i}':{'url':f'https://us.shein.com/A-p-{1234567+i}.html','export_store':True}
                     for i in range(20)})
        rows['de']={'url':'https://de.shein.com/A-p-1234567.html','export_store':True}
        batch=self.ns['_web_automatic_price_batches'](rows,tried)[0]
        self.assertEqual(len(batch),4)
        self.assertTrue(any(key.startswith('shein') for key in batch))
        self.assertTrue(any(key.startswith('us') for key in batch))
        self.assertNotIn('de',batch)
        self.assertEqual({self.ns['_web_listing_price_country'](row,{'country':'kw'}) for row in batch.values()},{'us'})

    def test_queue_diagnostics_do_not_expose_listing_or_title(self):
        ns=scope(['_web_log_price_queue'],{'WEB_ASYNC_PRICE_SHARED_MARKETS':2,
            '_web_row_has_numeric_price':lambda row:False,'_more_result_domain':lambda u:'us.shein.com'})
        rows={'id':{'url':'https://us.shein.com/PRIVATE-p-1234567.html','title':'PRIVATE'}}
        with redirect_stdout(io.StringIO()) as output:ns['_web_log_price_queue'](rows,set(),set(),2,'kw')
        result=json.loads(output.getvalue().split('PRICE RECOVERY QUEUE ')[1])
        self.assertEqual(result['hosts']['us.shein.com']['not_selected'],1)
        self.assertNotIn('PRIVATE',output.getvalue());self.assertNotIn('1234567',output.getvalue())

class App:
    def __init__(self):self.state=SimpleNamespace();self.routes={}
    def post(self,path):
        def register(fn):self.routes[path]=fn;return fn
        return register

class Request:
    def __init__(self,data):self.data=data
    async def body(self):return json.dumps(self.data).encode()

class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.fetches=[];self.calls=[];self.admissions=0;self.quota=100
        self.ns=scope(['_fz_evaluation_token','_fz_evaluation_row','_web_offer_image_candidates'],{
            'base64':base64,'hmac':hmac,'_REFINE_KEY':b'fixture-key',
            '_web_unescape_url':lambda x:x,'_web_unproxy_image_url':lambda x:x,
            '_web_is_http_url':lambda u:isinstance(u,str) and u.startswith('https://'),
            '_web_image_is_placeholder':lambda x:False,'_card_text':lambda x,n:str(x or '')[:n]})
        self.app=App()
        def admit(request):self.admissions+=1;return self.admissions<=self.quota
        def fetch(url):
            self.fetches.append(url)
            return dict(INLINE,data=base64.b64encode(url.encode()).decode())
        def classify(*a,**kw):self.calls.append(len(kw['images']));return judge(*a,**kw)
        self.ins=media_ns['install'](self.app,enabled=lambda:True,rate_allowed=admit,
            decode_row=self.ns['_fz_evaluation_row'],normalize_url=lambda x:x,fetch_inline=fetch,judge=classify)
        self.addCleanup(self.ins.shutdown)

    def token(self,images):
        return self.ns['_fz_evaluation_token']({'url':'https://shop.test/product','images':images})

    def batch(self,images):return asyncio.run(self.app.routes['/api/media/check/batch'](Request({'images':images})))

    def test_six_loaded_images_form_one_ai_batch_and_spend_six_slots(self):
        images=[f'https://img.test/{i}.png' for i in range(6)];token=self.token(images)
        result=self.batch([{'image':u,'token':token} for u in images])
        self.assertEqual([r['usable'] for r in result['results']],[True]*6)
        self.assertEqual(self.calls,[6]);self.assertEqual(self.admissions,6)

    def test_bad_token_in_batch_cannot_suppress_valid_signed_image(self):
        u='https://img.test/a.png';token=self.token([u])
        result=self.batch([{'image':u,'token':'bad'},{'image':u,'token':token}])
        self.assertEqual(result['results'][0]['reason'],'invalid_evaluation_token')
        self.assertTrue(result['results'][1]['usable']);self.assertEqual(self.admissions,1)

    def test_unobserved_image_does_not_download_or_spend_quota(self):
        u='https://img.test/a.png';token=self.token([u])
        with redirect_stdout(io.StringIO()) as output:
            result=self.batch([{'image':'https://other.test/SECRET.png','token':token}])
        self.assertEqual(result['results'][0]['reason'],'unobserved_image')
        self.assertEqual(self.fetches,[]);self.assertEqual(self.admissions,0)
        self.assertNotIn(token,output.getvalue());self.assertNotIn('SECRET',output.getvalue())

    def test_batch_cannot_bypass_per_image_quota_and_cached_images_still_work(self):
        images=['https://img.test/a','https://img.test/b'];token=self.token(images);self.quota=1
        result=self.batch([{'image':u,'token':token} for u in images])
        self.assertTrue(result['results'][0]['usable']);self.assertEqual(result['results'][1]['status'],429)
        result=self.batch([{'image':images[0],'token':token}])
        self.assertTrue(result['results'][0]['usable']);self.assertEqual(self.admissions,2)

    def test_snapshot_and_recovery_tokens_remain_separate(self):
        old=[f'https://img.test/old{i}' for i in range(8)];fresh=['https://img.test/recovered']
        old_token,new_token=self.token(old),self.token(fresh)
        result=self.batch([{'image':old[0],'token':old_token},{'image':fresh[0],'token':new_token}])
        self.assertTrue(all(r['usable'] for r in result['results']))
        self.assertNotIn(hashlib.sha256(fresh[0].encode()).hexdigest(),self.ns['_fz_evaluation_row'](old_token)['image_hashes'])

    def test_raw_spaces_and_unicode_are_verified_before_browser_normalization(self):
        raw='https://img.test/صورة جميلة.png';token=self.token([raw])
        self.assertTrue(self.batch([{'image':raw,'token':token}])['results'][0]['usable'])
        self.assertEqual(self.fetches,[raw])

    def test_recovery_with_eight_old_images_signs_the_new_image(self):
        fresh='https://img.test/fresh'
        pool=ThreadPoolExecutor(max_workers=1);self.addCleanup(pool.shutdown)
        overrides=dict(self.ns,wait=wait,FIRST_COMPLETED=FIRST_COMPLETED,
            _FZ_MEDIA_LOOKUP_POOL=pool,_FZ_MEDIA_PAGE_GRACE=1,
            _web_market=lambda cc:{'country':cc},_run_with_market=lambda market,fn:fn(),
            _web_verified_page_snapshot=lambda *a:{'image_candidates':[fresh]},
            _web_live_page_image=lambda *a:fresh,_api_cost_record=lambda *a:None,
            _web_image_is_generic=lambda *a:False,
            _web_merge_offer_images=lambda a,b:{'image_candidates':b['images']},
            _web_targeted_price_updates=lambda *a,**kw:self.fail('unexpected index call'))
        ns=scope(['_fz_recover_media'],overrides)
        row={'url':'https://shop.test/product','country':'kw',
             'image':'https://img.test/old-primary','images':[f'https://img.test/old{i}' for i in range(8)]}
        result=ns['_fz_recover_media'](row)
        hashes=ns['_fz_evaluation_row'](result['media_token'])['image_hashes']
        self.assertEqual(result['media_images'],[fresh])
        self.assertEqual(hashes,[hashlib.sha256(fresh.encode()).hexdigest()])

    def test_batch_limit_rejected_before_any_work(self):
        result=self.batch([{}]*7)
        self.assertEqual(result.status_code,400);self.assertEqual(result.data['reason'],'invalid_batch')
        self.assertEqual(self.admissions,0)

class SharingTests(unittest.TestCase):
    def test_identity_cache_hit_seeds_exact_pixels_without_new_model_call(self):
        audit=audit_support.AuditRecoveryTests();audit.setup_request([])
        cached={'items':[{'id':0,'image_kind':'product'}],'reference_profile':{'category':'necklace'}}
        audit.ns['_web_ai_classifier_cache_get']=lambda key:cached
        audit.evidence[1][0]=dict(INLINE,source_url='https://img.test/a')
        result=audit.invoke()
        self.assertEqual(audit.calls,[]);self.assertEqual(len(audit.seeds),1)
        self.assertEqual(result['items'][0]['audited_image'],'https://img.test/a')
        self.assertNotIn('audited_image',cached['items'][0])

    def test_completed_audit_can_satisfy_queued_but_not_running_work(self):
        calls=[]
        ins=Inspector(lambda u:INLINE,lambda *a,**kw:calls.append(1));self.addCleanup(ins.shutdown)
        ins.active_batches=2
        f=Future();ins.load('https://img.test/a',f)
        self.assertTrue(ins.remember_audit(INLINE,'product'))
        self.assertEqual(f.result(1),'product');self.assertEqual(ins.pending,[])
        ins.active_batches=0
        self.assertEqual(calls,[]);self.assertEqual(ins.stats['audit_reused'],1)

if __name__=='__main__':unittest.main(verbosity=2)
