import asyncio
import hashlib
import hmac
import json
import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from starlette.responses import Response
from findzia_spaces_gateway import SpacesImageGateway, PATH


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def run_request(self, gateway, payload, *, nonce='a'*32, secret='s'*64, stamp=None):
        raw = json.dumps(payload).encode()
        stamp = str(stamp or int(time.time()))
        signature = hmac.new(secret.encode(), stamp.encode()+b'\n'+nonce.encode()+b'\n'+raw, hashlib.sha256).hexdigest()
        scope = {'type':'http', 'method':'POST', 'path':PATH, 'headers':[
            (b'x-findzia-spaces-time',stamp.encode()),(b'x-findzia-spaces-nonce',nonce.encode()),
            (b'x-findzia-spaces-signature',signature.encode())]}
        async def receive(): return {'type':'http.request','body':raw,'more_body':False}
        messages=[]
        async def send(message): messages.append(message)
        with patch.dict(os.environ, {'FINDZIA_SPACES_ENGINE_KEY':'s'*64}):
            await gateway(scope,receive,send)
        return messages

    async def test_exact_original_route_and_bytes(self):
        calls=[]
        async def original(request):
            calls.append(await request.json())
            return Response(b'{"event":"done"}\n',media_type='application/x-ndjson')
        gateway=SpacesImageGateway(SimpleNamespace(web_api_image_search_stream=original))
        payload={'spaces_room':'1'*24,'image_base64':'same-image','country':'US','lang':'en'}
        result=await self.run_request(gateway,payload)
        self.assertEqual(calls,[payload])
        self.assertEqual(result[0]['status'],200)
        self.assertEqual(result[-1]['body'],b'{"event":"done"}\n')
        self.assertEqual(gateway.active,0)
        replay=await self.run_request(gateway,payload)
        self.assertEqual(replay[0]['status'],409)
        self.assertEqual(len(calls),1)

    async def test_invalid_auth_expiry_and_generated_caption_never_call_engine(self):
        async def forbidden(request): raise AssertionError('must not invoke providers')
        gateway=SpacesImageGateway(SimpleNamespace(web_api_image_search_stream=forbidden))
        payload={'spaces_room':'1'*24,'image_base64':'image','country':'US'}
        self.assertEqual((await self.run_request(gateway,payload,secret='wrong'))[0]['status'],401)
        self.assertEqual((await self.run_request(gateway,payload,stamp=int(time.time())-120))[0]['status'],401)
        self.assertEqual((await self.run_request(gateway,dict(payload,caption='invented chair')))[0]['status'],400)
        gateway.active=4
        self.assertEqual((await self.run_request(gateway,payload))[0]['status'],429)


if __name__=='__main__': unittest.main()
