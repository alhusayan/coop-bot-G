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
from starlette.responses import JSONResponse

PATH = '/internal/spaces/image/stream'


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
            # Request.json uses the same exact bytes whose signature was checked.
            request._body = raw
            # Includes the original input preparation, market validation, Lens
            # pipeline, visual classification, prices, removals and final events.
            response = await self.original.web_api_image_search_stream(request)
            response.headers['x-findzia-search-engine'] = 'original'
            response.headers['Cache-Control'] = 'no-store'
            await response(scope, receive, send)
        finally:
            self.active -= 1
            print('SPACES_ORIGINAL_ENGINE ' + json.dumps({
                'room': room, 'country': payload.get('country'),
                'elapsed_ms': int((time.monotonic() - started) * 1000)}), flush=True)
