"""Exact endpoint/inspector logic with transport classes stubbed; no external services."""
import ast, asyncio, hashlib, io, json, threading, unittest
from pathlib import Path
from types import SimpleNamespace
from contextlib import redirect_stdout

class Json:
    def __init__(self, data=None, status_code=200, headers=None):
        self.data,self.status_code,self.headers=data,status_code,headers or {}
class Disconnect(Exception):pass
source=Path(__file__).parents[1]/'findzia_product_media.py'
if not source.is_file():
    source=Path(__file__).with_name('findzia_product_media.fixture.py')
tree=ast.parse(source.read_text());tree.body=[n for n in tree.body if not(isinstance(n,ast.ImportFrom) and n.module.startswith(('fastapi','starlette')))]
ns={'Request':object,'JSONResponse':Json,'Response':Json,'ClientDisconnect':Disconnect}
exec(compile(tree,str(source),'exec'),ns)
Inspector=ns['ProductMediaInspector']
class App:
    def __init__(self):self.state=SimpleNamespace()
    def post(self,path):
        def set(fn):self.check=fn;return fn
        return set
class Req:
    def __init__(self,image='https://shop.test/a.png',token='valid'):self.image,self.token=image,token
    async def body(self):return json.dumps({'image':self.image,'token':self.token}).encode()
def judge(*a,**k):return {'images':[{'id':i,'kind':'product'} for i,_ in enumerate(k['images'])]}
class MediaTests(unittest.TestCase):
    def make(self,decision='product'):
        app=App();self.admissions=0;self.allowed=True;self.downloads=0
        def admit(r):self.admissions+=1;return self.allowed
        def decode(token):
            if token!='valid':raise ValueError()
            return {'image_hashes':[hashlib.sha256(b'https://shop.test/a.png').hexdigest()]}
        def download(url):self.downloads+=1;return {'data':'YQ==','mime_type':'image/png'}
        inspector=ns['install'](app,enabled=lambda:True,rate_allowed=admit,decode_row=decode,normalize_url=lambda x:x,fetch_inline=download,judge=lambda *a,**k:{'images':[{'id':i,'kind':decision} for i,_ in enumerate(k['images'])]})
        self.addCleanup(inspector.shutdown);return app,inspector
    def test_cached_success_survives_exhausted_quota(self):
        app,_=self.make();first=asyncio.run(app.check(Req()));self.allowed=False
        second=asyncio.run(app.check(Req()));self.assertTrue(first['usable'] and second['usable']);self.assertEqual(self.admissions,1);self.assertEqual(self.downloads,1)
    def test_token_validation_before_cache(self):
        app,_=self.make();asyncio.run(app.check(Req()));bad=asyncio.run(app.check(Req(token='wrong')))
        self.assertEqual(bad.status_code,400);self.assertEqual(self.admissions,1)
    def test_unobserved_url_does_not_spend_quota(self):
        app,_=self.make();bad=asyncio.run(app.check(Req(image='https://evil.test/a.png')))
        self.assertEqual(bad.status_code,400);self.assertEqual(self.admissions,0)
    def test_rate_limit_is_retryable_and_not_cached(self):
        app,_=self.make();self.allowed=False;bad=asyncio.run(app.check(Req()))
        self.assertEqual(bad.status_code,429);self.assertEqual(bad.headers['Retry-After'],'60');self.assertTrue(bad.data['retryable']);self.assertEqual(self.downloads,0)
        self.allowed=True;self.assertTrue(asyncio.run(app.check(Req()))['usable'])
    def test_definitive_rejection_stays_rejected(self):
        app,_=self.make('logo');first=asyncio.run(app.check(Req()));self.allowed=False
        second=asyncio.run(app.check(Req()));self.assertFalse(first['usable']);self.assertFalse(second['retryable']);self.assertEqual(self.admissions,1)
    def test_unavailable_retains_retry_metadata(self):
        app,_=self.make('invalid');data=asyncio.run(app.check(Req()));self.assertFalse(data['usable']);self.assertTrue(data['retryable']);self.assertEqual(data['retry_after'],8)
    def test_uncertain_is_retryable(self):
        app,_=self.make('uncertain');data=asyncio.run(app.check(Req()));self.assertFalse(data['usable']);self.assertTrue(data['retryable']);self.assertEqual(data['retry_after'],8)
    def test_singleflight_spends_quota_once(self):
        gate=threading.Event();admissions=[]
        def fetch(url):gate.wait(2);return {'data':'YQ==','mime_type':'image/png'}
        inspector=Inspector(fetch,judge);self.addCleanup(inspector.shutdown)
        a=inspector.inspect('same',lambda:admissions.append(1) or True)
        b=inspector.inspect('same',lambda:admissions.append(1) or False)
        self.assertIs(a,b);gate.set();self.assertEqual(a.result(3),'product');self.assertEqual(admissions,[1])
    def test_402_diagnostic_does_not_log_provider_body(self):
        from test_audit_prices import scope as load_scope
        scope=load_scope(['_web_identity_http_error'])
        for message,category in [('Insufficient credit balance secret-key','insufficient_credit'),('billing disabled secret-key','billing_required'),('quota secret-key','quota_or_budget'),('private account data','unspecified')]:
            with redirect_stdout(io.StringIO()) as output:
                code=scope['_web_identity_http_error'](SimpleNamespace(status_code=402,json=lambda:{'error':{'message':message}}))
            self.assertEqual(code,'http_402');self.assertIn('category='+category,output.getvalue());self.assertNotIn(message,output.getvalue())
if __name__=='__main__':unittest.main(verbosity=2)
