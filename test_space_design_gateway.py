import asyncio,hashlib,hmac,json,os,tempfile,time,unittest,uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from findzia_accounts import Accounts
from findzia_billing import Credits
from findzia_spaces_gateway import SpacesImageGateway,DESIGN_RESERVE,DESIGN_FINISH

class DesignGateway(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.accounts=Accounts({'FINDZIA_ACCOUNT_DB':str(Path(self.tmp.name)/'db'),'FINDZIA_ACCOUNT_API_URL':'https://api.findzia.com','FINDZIA_ACCOUNT_ORIGINS':'https://findzia.com'})
  self.c=Credits(self.accounts,{'FINDZIA_SPACES_PRICING_ENABLED':'true'});g=self.c.guest(uuid.uuid4().hex);self.token=g['guest_token'];self.member=self.c.guest_member(self.token)['id'];self.gateway=SpacesImageGateway(SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(findzia_credits=self.c))))
 async def asyncTearDown(self):await self.c.runtime.close();self.tmp.cleanup()
 async def call(self,path,payload,token=None,operation=None):
  raw=json.dumps({**payload,'operation':operation or path}).encode();stamp=str(int(time.time()));nonce=uuid.uuid4().hex;key='s'*64
  signature=hmac.new(key.encode(),stamp.encode()+b'\n'+nonce.encode()+b'\n'+raw,hashlib.sha256).hexdigest()
  scope={'type':'http','method':'POST','path':path,'query_string':b'','headers':[(b'x-findzia-spaces-time',stamp.encode()),(b'x-findzia-spaces-nonce',nonce.encode()),(b'x-findzia-spaces-signature',signature.encode()),(b'authorization',('Bearer '+(token if token is not None else self.token)).encode()),(b'origin',b'https://findzia.com')]}
  async def receive():return {'type':'http.request','body':raw,'more_body':False}
  messages=[]
  async def send(m):messages.append(m)
  with patch.dict(os.environ,{'FINDZIA_SPACES_ENGINE_KEY':key}):await self.gateway(scope,receive,send)
  return messages[0]['status'],json.loads(messages[1]['body'])
 async def test_batch_charge_success_partial_refund_and_no_double_spend(self):
  ids=[uuid.uuid4().hex for _ in range(3)]
  status,data=await self.call(DESIGN_RESERVE,{'requests':ids});self.assertEqual(status,200)
  self.assertEqual(self.c.status(self.member)['remaining'],4)
  status,repeat=await self.call(DESIGN_RESERVE,{'requests':ids});self.assertEqual(data,repeat)
  for i,ref in enumerate(data['reservations']):
   status,_=await self.call(DESIGN_FINISH,{**ref,'success':i!=2},token='');self.assertEqual(status,200)
  self.assertEqual(self.c.status(self.member)['free_designs'],1)
  status,_=await self.call(DESIGN_FINISH,{**data['reservations'][0],'success':False},token='');self.assertEqual(status,200)
  self.assertEqual(self.c.status(self.member)['free_designs'],1)
 async def test_bad_actor_and_cross_operation_signature_are_rejected(self):
  ids=[uuid.uuid4().hex]
  status,_=await self.call(DESIGN_RESERVE,{'requests':ids},token='');self.assertEqual(status,401)
  status,_=await self.call(DESIGN_RESERVE,{'requests':ids},operation=DESIGN_FINISH);self.assertEqual(status,400)
  self.assertEqual(self.c.status(self.member)['remaining'],7)

if __name__=='__main__':unittest.main()
