"""Serve the requested original build, with the preserved experiment under /test.

The original search implementation is unchanged from a332321. Account, payment,
webhook and WhatsApp routes stay on that application. Both search versions use
the same existing credit admission; their provider caches are separate.
"""
import asyncio
import importlib
import os

# Spaces is an owned Findzia frontend. Preserve all existing origins and add only
# its exact production origin before the account and CORS services initialize.
_spaces_origin = 'https://findzia-spaces-production.up.railway.app'
for _name in ('FINDZIA_ACCOUNT_ORIGINS', 'WEB_ALLOWED_ORIGINS'):
    _origins = [x.strip() for x in os.environ.get(_name, 'https://findzia.com,https://www.findzia.com').split(',') if x.strip()]
    if _spaces_origin not in _origins:
        _origins.append(_spaces_origin)
    os.environ[_name] = ','.join(_origins)

import main as original

original.CACHE_DB_PATH += '.original-a332321'
# main initializes these at import time, before the version-specific path above.
# Initialize the same schemas on the isolated file before accepting any request.
original._cache_db_init()
original._serpapi_cache_db_init()
original._web_ai_classifier_db_init()
original._ai_db_init()


class VersionRouter:
    def __init__(self, primary):
        self.primary = primary
        self.experimental = None
        self.lock = asyncio.Lock()

    async def test_app(self):
        if self.experimental is None:
            async with self.lock:
                if self.experimental is None:
                    module = importlib.import_module('experiment.entry')
                    # One account/credit authority, including admission, refunds,
                    # helpers and device guest credits. Never bypass middleware.
                    module.app.state.findzia_accounts = self.primary.state.findzia_accounts
                    module.app.state.findzia_credits = self.primary.state.findzia_credits
                    self.experimental = module.app
        return self.experimental

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        # The catalog provider validates this pre-existing public agent profile.
        # Keep its registered URL while catalog retrieval itself stays in /test.
        if scope['type'] == 'http' and path == '/.well-known/ucp':
            selected = await self.test_app()
            return await selected(scope, receive, send)
        if scope['type'] != 'http' or not (path == '/test' or path.startswith('/test/')):
            return await self.primary(scope, receive, send)
        target = path[5:] or '/'
        scoped = dict(scope, path=target, raw_path=target.encode('utf-8'))
        # Strip the prefix BEFORE every original middleware sees the request.
        # In particular, credit middleware must see /api/search/stream exactly.
        if target.startswith(('/api/account/', '/api/billing/', '/api/paddle/',
                              '/api/myfatoorah/', '/api/payment', '/api/social/')) or not target.startswith('/api/'):
            selected = self.primary
        else:
            selected = await self.test_app()

        async def tagged(message):
            if message['type'] == 'http.response.start':
                message = dict(message, headers=list(message.get('headers', [])) + [
                    (b'x-findzia-version-scope', b'test'),
                    (b'x-robots-tag', b'noindex, nofollow, noarchive'),
                ])
            await send(message)

        return await selected(scoped, receive, tagged)


app = VersionRouter(original.app)

