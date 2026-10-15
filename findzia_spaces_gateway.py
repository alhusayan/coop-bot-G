"""Authenticated Spaces transport to the ORIGINAL photo route, not a search fork.

Spaces keeps its existing private-preview room/search admission. The service
credential is server-only and accepted for this one image-search operation.
Public Findzia search/account/billing middleware and pricing are unchanged.
"""
import asyncio
import hashlib
import hmac
import json
import os
import re
import time
from collections import Counter

from starlette.requests import Request
from fastapi import HTTPException
from starlette.responses import JSONResponse
from findzia_billing import CreditMiddleware

PATH = '/internal/spaces/image/stream'
DESIGN_RESERVE = '/internal/spaces/design/reserve'
DESIGN_FINISH = '/internal/spaces/design/finish'
PATHS = frozenset((PATH, DESIGN_RESERVE, DESIGN_FINISH))


class SpacesImageGateway:
    def __init__(self, original):
        self.original = original
        self.active = 0
        self.nonces = {}
        self.day = ''
        self.usage = Counter()

    async def __call__(self, scope, receive, send):
        async def fail(code, status):
            await JSONResponse({'error': code}, status_code=status,
                               headers={'Cache-Control': 'no-store'})(scope, receive, send)

        key = os.environ.get('FINDZIA_SPACES_ENGINE_KEY', '')
        if scope.get('method') != 'POST' or len(key) < 32:
            return await fail('not_found', 404)
        request = Request(scope, receive)
        stamp = request.headers.get('x-findzia-spaces-time', '')
        nonce = request.headers.get('x-findzia-spaces-nonce', '')
        signature = request.headers.get('x-findzia-spaces-signature', '')
        now = time.time()
        if (not stamp.isdigit() or abs(now - int(stamp)) > 90 or
                not re.fullmatch(r'[a-f0-9]{32}', nonce) or
                not re.fullmatch(r'[a-f0-9]{64}', signature)):
            return await fail('unauthorized', 401)
        data = bytearray()
        async for part in request.stream():
            data.extend(part)
            if len(data) > 18 * 1024 * 1024:
                return await fail('image_too_large', 413)
        raw = bytes(data)
        expected = hmac.new(key.encode(), stamp.encode() + b'\n' + nonce.encode() + b'\n' + raw,
                            hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return await fail('unauthorized', 401)
        self.nonces = {n: expiry for n, expiry in self.nonces.items() if expiry > now}
        if nonce in self.nonces:
            return await fail('replayed_request', 409)
        self.nonces[nonce] = now + 180
        if scope.get('path') in (DESIGN_RESERVE, DESIGN_FINISH):
            try:
                payload=json.loads(raw)
                if payload.get('operation')!=scope['path']:raise HTTPException(400,'invalid_request')
                credits=getattr(self.original.app.state,'findzia_credits',None)
                if not credits or not credits.available or not credits.enabled or not credits.spaces_pricing:
                    raise HTTPException(503,'credits_unavailable')
                if scope['path']==DESIGN_RESERVE:
                    if request.headers.get('origin') not in credits.accounts.origins:raise HTTPException(403,'origin_not_allowed')
                    actor=await asyncio.to_thread(credits.actor,request)
                    ids=payload.get('requests')
                    if not isinstance(ids,list) or any(not isinstance(v,str) for v in ids):raise HTTPException(400,'invalid_request')
                    from findzia_space_credits import DESIGN_PATH
                    reservations=await asyncio.to_thread(credits.space_policy.reserve,actor['id'],ids,DESIGN_PATH)
                    value={'ok':True,'reservations':reservations}
                else:
                    member,rid=payload.get('member'),payload.get('request')
                    if not isinstance(member,str) or not isinstance(rid,str) or not isinstance(payload.get('success'),bool):raise HTTPException(400,'invalid_request')
                    with credits.accounts.connect() as db:
                        row=db.execute("SELECT * FROM fz_credit_requests WHERE member=? AND request=? AND path='/internal/spaces/design'",(member,rid)).fetchone()
                    if not row:raise HTTPException(404,'not_found')
                    await asyncio.to_thread(credits.finish,member,rid,payload['success'])
                    value={'ok':True}
                return await JSONResponse(value,headers={'Cache-Control':'no-store'})(scope,receive,send)
            except HTTPException as exc:return await fail(exc.detail,exc.status_code)
            except (ValueError,TypeError,KeyError):return await fail('invalid_request',400)
        try:
            payload = json.loads(raw)
            room = payload['spaces_room']
            if not re.fullmatch(r'[a-f0-9]{24}', room):
                raise ValueError()
            if payload.get('one_catalog') or payload.get('caption') or payload.get('query'):
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            return await fail('invalid_request', 400)
        day = time.strftime('%Y-%m-%d', time.gmtime(now))
        if self.day != day:
            self.day, self.usage = day, Counter()
        if self.active >= 4:
            return await fail('service_busy', 429)
        if self.usage['total'] >= 2000 or self.usage[room] >= 120:
            return await fail('preview_limit', 429)
        self.nonces[nonce] = now + 180
        self.usage.update(['total', room])
        self.active += 1
        started = time.monotonic()
        try:
            # A service signature authenticates Spaces, NOT a customer's wallet.
            # Require the existing account/guest bearer, origin and request ID.
            # Reuse the original atomic one-credit reservation and durable refund
            # settlement; no separate Spaces balance or client-authored debit.
            owner = getattr(self.original, 'app', None)
            credits = getattr(getattr(owner, 'state', None), 'findzia_credits', None)
            if not credits or not credits.enabled or not credits.available:
                return await fail('credits_unavailable', 503)
            async def original_search(billed_scope, billed_receive, billed_send):
                billed_request = Request(billed_scope, billed_receive)
                billed_request._body = raw
                response = await self.original.web_api_image_search_stream(billed_request)
                response.headers['x-findzia-search-engine'] = 'original'
                response.headers['Cache-Control'] = 'no-store'
                await response(billed_scope, billed_receive, billed_send)
            # The protected public path selects its existing billing policy.
            # Retrieval still calls the exact same function with the signed bytes.
            billed_scope = dict(scope, path='/api/search/image/stream',
                                raw_path=b'/api/search/image/stream')
            await CreditMiddleware(original_search, owner)(billed_scope, receive, send)
        finally:
            self.active -= 1
            print('SPACES_ORIGINAL_ENGINE ' + json.dumps({
                'room': room, 'country': payload.get('country'),
                'elapsed_ms': int((time.monotonic() - started) * 1000)}), flush=True)
