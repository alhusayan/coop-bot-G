"""Full last-credit admission/settlement with real SQLite and ASGI middleware.

Provider output is a deterministic fixture; production accounts are untouched.
"""
import asyncio
import json
import unittest
import uuid
from types import SimpleNamespace

from findzia_billing import CreditMiddleware, HELPER_PATHS
import test_credit_retries as fixtures


class LastCreditTests(unittest.TestCase):
    setUp = fixtures.CreditRetries.setUp
    member = fixtures.CreditRetries.member

    def exercise(self, path, quantity, kind='pack', empty=False):
        member = self.member(kind=kind, quantity=quantity)
        self.credits.actor = lambda request: {'id': member}
        events = []
        for market in ('local', 'us', 'china'):
            events.append({'event': 'status', 'stage': 'searching_stores', 'market': market})
            for number in range(6):
                events.append({'event': 'result', 'item': {
                    'title': f'Product {market} {number}',
                    'url': f'https://shop.test/{market}/{number}', 'market': market,
                    'price': '12.00', 'currency': 'USD', 'image': f'https://shop.test/{market}/{number}.png',
                }})
        if empty:
            events = []
        events.append({'event': 'done', 'count': 0 if empty else 18})
        messages, calls, balance_during = [], [], []
        rid = uuid.uuid4().hex

        async def run():
            async def app(scope, receive, send):
                calls.append(scope['path'])
                # Normal admission has already reserved exactly one credit.
                state = self.credits.status(member)
                self.assertEqual(state['remaining'], quantity - 1)
                self.assertEqual(state['reserved'], 1)
                await send({'type': 'http.response.start', 'status': 200,
                            'headers': [(b'content-type', b'application/x-ndjson')]})
                for index, event in enumerate(events):
                    if index == 2:
                        # Completing images and inspecting offers still work at zero.
                        for helper_path in ('/api/media/recover', '/api/stores/ratings', '/api/evaluate'):
                            self.credits.helper(member, *HELPER_PATHS[helper_path])
                    balance_during.append(self.credits.status(member)['remaining'])
                    await send({'type': 'http.response.body',
                                'body': (json.dumps(event) + '\n').encode(), 'more_body': True})
                    await asyncio.sleep(0)
                await send({'type': 'http.response.body', 'body': b'', 'more_body': False})

            middleware = CreditMiddleware(app, SimpleNamespace(state=SimpleNamespace(findzia_credits=self.credits)))
            async def receive():
                return {'type': 'http.request', 'body': b'{"query":"Product","country":"kw","lang":"es"}', 'more_body': False}
            async def send(message):
                messages.append(message)
            scope = {'type': 'http', 'method': 'POST', 'path': path, 'query_string': b'',
                     'headers': [(b'origin', b'https://findzia.com'), (b'x-findzia-request-id', rid.encode())]}
            await middleware(scope, receive, send)
            # The response waits for the durable journal; the SQLite write
            # follows asynchronously without delaying product delivery.
            while self.credits.runtime.tasks:
                await asyncio.gather(*tuple(self.credits.runtime.tasks))
            return middleware, scope, receive, send

        asyncio.run(run())
        output = [json.loads(line) for m in messages if m['type'] == 'http.response.body'
                  for line in m['body'].splitlines() if line]
        self.assertEqual(output, events)
        self.assertEqual(calls, [path])
        self.assertTrue(all(n == quantity - 1 for n in balance_during))
        self.assertEqual(self.credits.status(member)['remaining'], quantity if empty else quantity - 1)
        self.assertEqual(self.credits.status(member)['reserved'], 0)
        return output

    def test_last_credit_receives_identical_complete_output(self):
        for kind in ('pack', 'trial', 'subscription'):
            for path in ('/api/search/stream', '/api/search/image/stream', '/api/refine/search/stream'):
                with self.subTest(kind=kind, path=path):
                    last = self.exercise(path, 1, kind)
                    funded = self.exercise(path, 10, kind)
                    self.assertEqual(last, funded)
                    self.assertEqual(sum(e['event'] == 'result' for e in last), 18)

    def test_empty_last_search_refunds_the_last_credit(self):
        for path in ('/api/search/stream', '/api/search/image/stream', '/api/refine/search/stream'):
            with self.subTest(path=path):
                self.exercise(path, 1, empty=True)

    def test_empty_photo_transport_fallback_uses_same_last_credit(self):
        member = self.member(quantity=1)
        rid = uuid.uuid4().hex
        self.credits.reserve(member, rid, '/api/search/image/stream')
        self.assertEqual(self.credits.status(member)['remaining'], 0)
        self.credits.finish(member, rid, False)
        child = self.credits.reserve_image_retry(member, rid)
        self.assertEqual(self.credits.status(member)['remaining'], 0)
        self.credits.finish(member, child, True)
        self.assertEqual(self.credits.status(member)['remaining'], 0)
        self.assertEqual(self.credits.status(member)['reserved'], 0)


if __name__ == '__main__':
    unittest.main()
