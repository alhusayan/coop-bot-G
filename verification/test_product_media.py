"""Offline safety and batching checks; no external requests or paid AI calls."""
import base64
import hashlib
import json
import threading
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from findzia_product_media import ProductMediaInspector, install


def inline(value):
    return {'mime_type':'image/jpeg','data':base64.b64encode(value.encode()).decode()}


class ProductMediaTests(unittest.TestCase):
    def create(self, fetch=None, judge=None, clock=None):
        def default_judge(system,data,**kwargs):
            return {'images':[{'id':i['id'],'kind':'product'} for i in data['images']]}
        inspector=ProductMediaInspector(fetch or inline,judge or default_judge,**({'clock':clock} if clock else {}))
        self.addCleanup(inspector.shutdown);return inspector

    def test_exact_candidate_pixels_and_multiple_kinds(self):
        observed=[]
        def judge(system,data,**kwargs):
            images=kwargs['images']; observed.extend(images)
            return {'images':[{'id':i,'kind':base64.b64decode(img['data']).decode()}
                              for i,(_,img) in enumerate(images)]}
        inspector=self.create(judge=judge)
        names=['product','logo','text_only','placeholder','uncertain']
        futures=[inspector.inspect(name) for name in names]
        self.assertEqual([f.result(3) for f in futures],names)
        self.assertEqual(len(observed),5)
        self.assertTrue(all(img['mimeType']=='image/jpeg' for _,img in observed))

    def test_duplicate_urls_and_identical_bytes_share_one_judgement(self):
        seen=[]; downloads=[]
        def fetch(url): downloads.append(url); return inline('same-logo')
        def judge(system,data,**kwargs):
            seen.append(data); return {'images':[{'id':0,'kind':'logo'}]}
        inspector=self.create(fetch,judge)
        a=inspector.inspect('first');b=inspector.inspect('first');c=inspector.inspect('second')
        self.assertIs(a,b)
        self.assertEqual([f.result(3) for f in [a,b,c]],['logo']*3)
        self.assertEqual(len(seen),1);self.assertEqual(len(downloads),2)
        self.assertEqual(inspector.inspect('first').result(),'logo');self.assertEqual(len(downloads),2)

    def test_batches_never_exceed_eight_images(self):
        sizes=[]
        def judge(system,data,**kwargs):
            sizes.append(len(data['images']));return {'images':[{'id':x['id'],'kind':'product'} for x in data['images']]}
        inspector=self.create(judge=judge)
        futures=[inspector.inspect(str(i)) for i in range(18)]
        self.assertEqual([f.result(3) for f in futures],['product']*18)
        self.assertEqual(sum(sizes),18);self.assertLessEqual(max(sizes),8)
        self.assertLess(len(sizes),18)

    def test_missing_duplicate_invalid_and_string_ids_do_not_pass(self):
        cases=[{}, {'images':[]}, {'images':[{'id':0,'kind':'product'},{'id':0,'kind':'product'}]},
               {'images':[{'id':'0','kind':'product'}]}, {'images':[{'id':True,'kind':'product'}]},
               {'images':[{'id':0,'kind':'accepted'}]}, {'images':[{'id':9,'kind':'product'}]}]
        for result in cases:
            inspector=self.create(judge=lambda *args,**kw:result)
            self.assertEqual(inspector.inspect('photo').result(3),'unavailable')

    def test_unavailable_model_or_unreadable_image_never_approved(self):
        def fail(*a,**kw): raise RuntimeError('mock outage')
        self.assertEqual(self.create(judge=fail).inspect('photo').result(3),'unavailable')
        self.assertEqual(self.create(fetch=lambda u:None).inspect('photo').result(3),'unavailable')

    def test_transient_failure_can_retry_after_short_cache(self):
        now=[10]; calls=[]
        def judge(*a,**kw):
            calls.append(1)
            if len(calls)==1: raise RuntimeError('retry')
            return {'images':[{'id':0,'kind':'product'}]}
        inspector=self.create(judge=judge,clock=lambda:now[0])
        self.assertEqual(inspector.inspect('photo').result(3),'unavailable')
        now[0]=20
        self.assertEqual(inspector.inspect('photo').result(3),'product')

    def test_work_queue_is_bounded(self):
        release=threading.Event()
        def fetch(url):release.wait(2);return inline(url)
        inspector=self.create(fetch=fetch)
        futures=[inspector.inspect(str(i)) for i in range(48)]
        self.assertEqual(inspector.inspect('overflow').result(),'unavailable')
        release.set()
        self.assertEqual([f.result(5) for f in futures],['product']*48)

    def endpoint(self, decision='product'):
        image='https://merchant.example/product.png';downloads=[];app=FastAPI()
        def decode(token):
            if token!='signed':raise ValueError('invalid_token')
            return {'image_hashes':[hashlib.sha256(image.encode()).hexdigest()]}
        def fetch(url):downloads.append(url);return inline(url)
        inspector=install(app,enabled=lambda:True,rate_allowed=lambda r:True,
            decode_row=decode,normalize_url=lambda u:u if isinstance(u,str) else '',fetch_inline=fetch,
            judge=lambda system,data,**kw:{'images':[{'id':0,'kind':decision}]})
        self.addCleanup(inspector.shutdown)
        return TestClient(app),image,downloads

    def test_endpoint_only_fetches_signed_observed_images(self):
        client,image,downloads=self.endpoint()
        for token,url in [('forged',image),('signed','http://127.0.0.1/private'),('signed','https://other.example/file')]:
            self.assertEqual(client.post('/api/media/check',json={'token':token,'image':url}).status_code,400)
        self.assertEqual(downloads,[])
        r=client.post('/api/media/check',json={'token':'signed','image':image})
        self.assertTrue(r.json()['usable']);self.assertEqual(downloads,[image])

    def test_endpoint_negative_decisions_and_large_request(self):
        for decision in ['logo','text_only','placeholder','uncertain']:
            client,image,_=self.endpoint(decision)
            self.assertFalse(client.post('/api/media/check',json={'token':'signed','image':image}).json()['usable'])
        self.assertEqual(client.post('/api/media/check',content=' '*20001).status_code,400)


if __name__=='__main__': unittest.main()
