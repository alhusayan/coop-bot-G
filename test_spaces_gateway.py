import asyncio
import hashlib
import hmac
import json
import os
import sqlite3
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from starlette.responses import Response, StreamingResponse
from findzia_billing import Credits
from findzia_spaces_gateway import SpacesImageGateway, PATH

ORIGIN='https://findzia-spaces-production.up.railway.app'
class Accounts:
    available=True
    origins={ORIGIN}
    def __init__(self,path):
        self.db_path=str(path)
        with self.connect() as db: db.execute('CREATE TABLE fz_members(id TEXT PRIMARY KEY)')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.db_path);db.row_factory=sqlite3.Row
        try:
            with db: yield db
        finally: db.close()
    def token(self,request): return request.headers.get('authorization','').removeprefix('Bearer ')
    def member(self,token):
        if token!='valid-test-account':raise HTTPException(401,'sign_in_required')
        return {'id':'member'}

class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.accounts=Accounts(Path(self.tmp.name)/'accounts.db')
        self.credits=Credits(self.accounts,{})
        with self.accounts.connect() as db:
            db.execute("INSERT INTO fz_members VALUES('member')")
            db.execute("INSERT INTO fz_credit_grants VALUES('grant','member','pack','test',1,1,0,NULL,0)")
        self.calls=[]
        self.reply=Response(b'{"event":"result","item":{"url":"https://store.test/chair","title":"Chair"}}\n{"event":"done"}\n',media_type='application/x-ndjson')
        async def original(request):
            self.calls.append(await request.json());return self.reply
        self.gateway=SpacesImageGateway(SimpleNamespace(web_api_image_search_stream=original,app=SimpleNamespace(state=SimpleNamespace(findzia_credits=self.credits))))
        self.payload={'spaces_room':'1'*24,'image_base64':'same-image','country':'US','lang':'en'}
    async def asyncTearDown(self):
        await self.credits.runtime.close();self.tmp.cleanup()
    async def run_request(self, *, nonce='a'*32, secret='s'*64, stamp=None, token='valid-test-account',origin=ORIGIN,rid='r'*32,payload=None):
        raw=json.dumps(payload or self.payload).encode();stamp=str(stamp or int(time.time()))
        signature=hmac.new(secret.encode(),stamp.encode()+b'\n'+nonce.encode()+b'\n'+raw,hashlib.sha256).hexdigest()
        scope={'type':'http','method':'POST','path':PATH,'query_string':b'','headers':[
            (b'x-findzia-spaces-time',stamp.encode()),(b'x-findzia-spaces-nonce',nonce.encode()),(b'x-findzia-spaces-signature',signature.encode()),
            (b'content-length',str(len(raw)).encode()),(b'authorization',('Bearer '+token).encode()),(b'origin',origin.encode()),(b'x-findzia-request-id',rid.encode())]}
        received=False
        async def receive():
            nonlocal received
            if not received:
                received=True
                return {'type':'http.request','body':raw,'more_body':False}
            await asyncio.Event().wait()
        messages=[]
        async def send(message): messages.append(message)
        with patch.dict(os.environ,{'FINDZIA_SPACES_ENGINE_KEY':'s'*64}):await self.gateway(scope,receive,send)
        await self.credits.runtime.replay()
        return messages
    async def test_last_credit_delivers_full_original_results_once(self):
        result=await self.run_request()
        self.assertEqual(self.calls,[self.payload]);self.assertEqual(result[0]['status'],200)
        self.assertIn(b'"event":"done"',result[-1]['body']);self.assertEqual(self.credits.status('member')['remaining'],0)
        replay=await self.run_request(nonce='b'*32)
        self.assertEqual(replay[0]['status'],409);self.assertEqual(len(self.calls),1)
        exhausted=await self.run_request(nonce='c'*32,rid='n'*32)
        self.assertEqual(exhausted[0]['status'],402);self.assertEqual(len(self.calls),1)
        with self.accounts.connect() as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM fz_credit_ledger WHERE reason='reserve'").fetchone()[0],1)
    async def test_empty_or_failed_original_response_refunds_credit(self):
        for number,reply in enumerate([Response(b'{"event":"done"}\n',media_type='application/x-ndjson'),Response(b'failed',status_code=503)]):
            self.reply=reply
            await self.run_request(nonce=str(number)*32,rid=str(number)*32)
            self.assertEqual(self.credits.status('member')['remaining'],1)
    async def test_service_signature_alone_cannot_spend_or_search(self):
        for kwargs,status in [({'token':''},401),({'origin':'https://evil.test'},403),({'rid':''},400),({'secret':'wrong'},401),({'stamp':int(time.time())-120},401),({'payload':dict(self.payload,caption='invented chair')},400)]:
            kwargs.setdefault('nonce',hashlib.md5(str(kwargs).encode()).hexdigest())
            result=await self.run_request(**kwargs);self.assertEqual(result[0]['status'],status)
        self.assertEqual(self.calls,[]);self.assertEqual(self.credits.status('member')['remaining'],1)
    async def test_concurrent_duplicate_cannot_reserve_twice(self):
        a,b=await asyncio.gather(self.run_request(nonce='a'*32),self.run_request(nonce='b'*32))
        self.assertEqual(sorted([a[0]['status'],b[0]['status']]),[200,409]);self.assertEqual(len(self.calls),1)
        self.assertEqual(self.credits.status('member')['remaining'],0)
    async def test_existing_guest_wallet_is_used_without_minting_new_credits(self):
        token='fz_guest_'+'f'*64
        with self.accounts.connect() as db:db.execute('INSERT INTO fz_guests VALUES(?,?,?,?,NULL)',('device','member',hashlib.sha256(token.encode()).hexdigest(),int(time.time())))
        result=await self.run_request(token=token)
        self.assertEqual(result[0]['status'],200);self.assertEqual(self.credits.status('member')['remaining'],0)
    async def test_real_stream_and_consumed_upload_finish_with_one_debit(self):
        async def chunks():
            yield b'{"event":"result","item":{"url":"https://store.test/chair","title":"Chair"}}\n'
            await asyncio.sleep(0)
            yield b'{"event":"done"}\n'
        self.reply=StreamingResponse(chunks(),media_type='application/x-ndjson')
        result=await asyncio.wait_for(self.run_request(),timeout=2)
        self.assertEqual(result[0]['status'],200)
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.credits.status('member')['remaining'],0)
        self.assertIn(b'"event":"done"',b''.join(x.get('body',b'') for x in result))
    async def test_replay_and_disabled_billing_fail_closed(self):
        self.credits.enabled=False
        self.assertEqual((await self.run_request())[0]['status'],503)
        self.credits.enabled=True
        self.assertEqual((await self.run_request())[0]['status'],409)
        self.assertEqual(self.calls,[])

if __name__=='__main__':unittest.main()
