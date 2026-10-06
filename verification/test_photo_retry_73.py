"""Real SQLite credit accounting and ASGI middleware; no production accounts."""
import asyncio
import json
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
import findzia_billing as billing
import test_credit_retries as baseline


class PhotoRetryTests(unittest.TestCase):
    setUp=baseline.CreditRetries.setUp
    member=baseline.CreditRetries.member
    reserve=baseline.CreditRetries.reserve
    expect_error=baseline.CreditRetries.expect_error

    def original(self, member):
        return self.reserve(member,'/api/search/image/stream')

    def test_confirmed_refund_then_success_spends_exactly_one_credit(self):
        member=self.member();rid=self.original(member)
        self.assertIsNone(self.credits.reserve_image_retry(member,rid))
        self.credits.finish(member,rid,False)
        child=self.credits.reserve_image_retry(member,rid)
        self.assertNotEqual(child,rid)
        self.credits.finish(member,child,True)
        self.assertEqual(self.credits.status(member)['remaining'],9)
        with self.accounts.connect() as db:
            self.assertEqual([r[0] for r in db.execute('SELECT delta FROM fz_credit_ledger ORDER BY id')],[-1,1,-1])

    def test_concurrent_fallbacks_share_one_child_admission(self):
        member=self.member();rid=self.original(member);self.credits.finish(member,rid,False)
        barrier=threading.Barrier(4)
        def attempt(_):
            barrier.wait()
            try:return self.credits.reserve_image_retry(member,rid)
            except HTTPException as exc:return exc.status_code
        with ThreadPoolExecutor(max_workers=4) as pool:out=list(pool.map(attempt,range(4)))
        self.assertEqual(sum(isinstance(v,str) for v in out),1)
        self.assertEqual(out.count(409),3)
        self.assertEqual(self.credits.status(member)['remaining'],9)

    def test_spent_or_refunded_child_cannot_be_replayed_or_reopened(self):
        for success in (True,False):
            member=self.member();rid=self.original(member);self.credits.finish(member,rid,False)
            child=self.credits.reserve_image_retry(member,rid);self.credits.finish(member,child,success)
            self.expect_error(409,'search_already_processed',lambda:self.credits.reserve_image_retry(member,rid))
            self.assertEqual(self.credits.status(member)['remaining'],9 if success else 10)

    def test_successful_original_cannot_run_again(self):
        member=self.member();rid=self.original(member);self.credits.finish(member,rid,True)
        self.expect_error(409,'search_already_processed',lambda:self.credits.reserve_image_retry(member,rid))
        self.assertEqual(self.credits.status(member)['remaining'],9)

    def test_retry_is_scoped_to_owner_and_original_image_stream(self):
        member,other=self.member(),self.member();rid=self.original(member);self.credits.finish(member,rid,False)
        for owner,request in [(other,rid),(member,uuid.uuid4().hex)]:
            self.expect_error(409,'search_already_processed',lambda:self.credits.reserve_image_retry(owner,request))
        for path in ('/api/search/stream','/api/search/image'):
            rid=self.reserve(member,path);self.credits.finish(member,rid,False)
            self.expect_error(409,'search_already_processed',lambda:self.credits.reserve_image_retry(member,rid))
        self.assertEqual(self.credits.status(member)['remaining'],10)

    def test_normal_balance_guard_applies_to_child(self):
        member=self.member(quantity=1);rid=self.original(member);self.credits.finish(member,rid,False)
        newer=self.reserve(member);self.credits.finish(member,newer,True)
        self.expect_error(402,'credits_exhausted',lambda:self.credits.reserve_image_retry(member,rid))

    def test_late_original_completion_cannot_change_child_outcome(self):
        member=self.member();rid=self.original(member);self.credits.finish(member,rid,False)
        child=self.credits.reserve_image_retry(member,rid)
        self.credits.finish(member,rid,True);self.credits.finish(member,rid,False)
        self.credits.finish(member,child,True)
        self.assertEqual(self.credits.status(member)['remaining'],9)

    def test_reserved_parent_wait_is_bounded_without_second_admission(self):
        member=self.member();rid=self.original(member)
        async def run():
            middleware=billing.CreditMiddleware(None,None)
            with patch.object(billing,'IMAGE_RETRY_WAIT_SECONDS',.025):
                with self.assertRaises(HTTPException) as caught:
                    await middleware._reserve_search(self.credits,member,rid,'/api/search/image',asyncio.Event())
            self.assertEqual(caught.exception.detail,'search_in_progress')
        asyncio.run(run())
        self.assertEqual(self.credits.status(member)['reserved'],1)
        self.assertEqual(self.credits.status(member)['remaining'],9)

    def test_cancelled_fallback_wait_never_reserves_child(self):
        member=self.member();rid=self.original(member)
        async def run():
            cancelled=asyncio.Event();cancelled.set()
            with self.assertRaises(asyncio.CancelledError):
                await billing.CreditMiddleware(None,None)._reserve_search(self.credits,member,rid,'/api/search/image',cancelled)
        asyncio.run(run())
        self.credits.finish(member,rid,False)
        self.assertEqual(self.credits.status(member)['remaining'],10)

    def test_asgi_disconnect_refunds_parent_before_fallback_runs(self):
        member=self.member();rid=uuid.uuid4().hex;calls=[];messages=[]
        self.credits.actor=lambda request:{'id':member}
        async def run():
            started=asyncio.Event()
            async def app(scope,receive,send):
                calls.append(scope['path'])
                if scope['path'].endswith('/stream'):
                    started.set();await asyncio.Event().wait()
                await send({'type':'http.response.start','status':200,'headers':[(b'content-type',b'application/json')]})
                await send({'type':'http.response.body','body':json.dumps({'results':[{'url':'https://shop.test/item','title':'item'}]}).encode()})
            middleware=billing.CreditMiddleware(app,SimpleNamespace(state=SimpleNamespace(findzia_credits=self.credits)))
            async def receive():return {'type':'http.request','body':b'{}','more_body':False}
            async def send(message):messages.append(message)
            def scope(path):return {'type':'http','method':'POST','path':path,'query_string':b'',
                'headers':[(b'origin',b'https://findzia.com'),(b'x-findzia-request-id',rid.encode())]}
            original=asyncio.create_task(middleware(scope('/api/search/image/stream'),receive,send))
            await started.wait()
            fallback=asyncio.create_task(middleware(scope('/api/search/image'),receive,send))
            await asyncio.sleep(.01)
            self.assertEqual(calls,['/api/search/image/stream'])
            original.cancel()
            with self.assertRaises(asyncio.CancelledError):await original
            await asyncio.wait_for(fallback,2)
            await middleware(scope('/api/search/image'),receive,send)
        asyncio.run(run())
        self.assertEqual(calls,['/api/search/image/stream','/api/search/image'])
        self.assertEqual([m['status'] for m in messages if m['type']=='http.response.start'],[200,409])
        self.assertEqual(self.credits.status(member)['remaining'],9)

    def test_disconnect_during_child_reservation_refunds_child_not_parent_again(self):
        member=self.member();rid=self.original(member);self.credits.finish(member,rid,False)
        entered=threading.Event();release=threading.Event();original=self.credits.reserve_image_retry
        self.credits.actor=lambda request:{'id':member}
        def delayed(*args):
            child=original(*args);entered.set();release.wait(2);return child
        self.credits.reserve_image_retry=delayed
        async def run():
            async def app(*args):self.fail('cancelled admission reached provider')
            async def receive():return {'type':'http.request','body':b'{}','more_body':False}
            async def send(message):self.fail('cancelled request sent response')
            middleware=billing.CreditMiddleware(app,SimpleNamespace(state=SimpleNamespace(findzia_credits=self.credits)))
            scope={'type':'http','method':'POST','path':'/api/search/image','query_string':b'',
                'headers':[(b'origin',b'https://findzia.com'),(b'x-findzia-request-id',rid.encode())]}
            task=asyncio.create_task(middleware(scope,receive,send))
            self.assertTrue(await asyncio.to_thread(entered.wait,1))
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
            release.set()
            deadline=asyncio.get_running_loop().time()+1
            while self.credits.status(member)['remaining']!=10:
                self.assertLess(asyncio.get_running_loop().time(),deadline)
                await asyncio.sleep(.005)
        try:asyncio.run(run())
        finally:release.set()
        with self.accounts.connect() as db:
            states=[r[0] for r in db.execute('SELECT state FROM fz_credit_requests')]
            ledger=[r[0] for r in db.execute('SELECT delta FROM fz_credit_ledger ORDER BY id')]
        self.assertEqual(states,['refunded','refunded'])
        self.assertEqual(ledger,[-1,1,-1,1])


if __name__=='__main__':unittest.main()
