"""Actual Lens, image and stream coordinators; providers and time are fixtures."""
import ast
import asyncio
import copy
import io
import re
import threading
import unittest
from collections import deque
from contextlib import redirect_stdout
from types import SimpleNamespace

from test_audit_prices import NODES, SOURCE, Clock, scope
import test_ready_tail_73 as stream_support


class LinkedCancel(threading.Event):
    def __init__(self,parent):super().__init__();self.parent=parent
    def is_set(self):return super().is_set() or self.parent.is_set()


class LensFixture:
    def __init__(self, ready_at=2, local_at=2, late_at=30, clear_at=None, reference=True, native=False):
        self.clock=Clock();self.parent=threading.Event();self.previews=[];self.jobs=[]
        clock=self.clock
        class Job:
            def __init__(inner,at,rows):inner.at=at;inner.rows=rows;inner.cancelled=False
            def done(inner):return clock.now>=inner.at
            def result(inner,timeout=None):
                if not inner.done():raise TimeoutError()
                return copy.deepcopy(inner.rows)
            def cancel(inner):inner.cancelled=True;return True
        self.ready=SimpleNamespace(is_set=lambda:ready_at is not None and clock.now>=ready_at
            and (clear_at is None or clock.now<clear_at))
        def row(key,rank):return {'title':'chair '+key,'link':'https://shop.test/'+key,
            'thumbnail':'https://img.test/'+key,'price':'10 KWD','rank':rank,'section':'visual_matches'}
        initial=[row(str(i),0) for i in range(3)]
        specs=[(local_at,initial),(late_at,[row('late',1)])]
        class Pool:
            def submit(inner,fn,*a,**kw):
                at,rows=specs[len(self.jobs)];job=Job(at,rows);self.jobs.append(job);return job
        class NativePool:
            def submit(inner,fn,*args):
                self.native_cancel=args[6];self.native_callback=args[5]
                return Job(30,[])
        def wait(jobs,timeout=0,return_when=None):
            finish=min((j.at for j in jobs),default=clock.now+timeout)
            clock.now=max(clock.now,min(clock.now+timeout,finish))
            done={j for j in jobs if j.done()}
            return done,set(jobs)-done
        ns=dict(time=clock,threading=threading,deque=deque,re=re,
            PUBLIC_BASE_URL='https://test',ENABLE_GOOGLE_LENS=True,SERPAPI_API_KEY='test',
            _INDEPENDENT=SimpleNamespace(available=lambda x:False,share_budget=lambda *a:None,hedge=lambda t:None),
            _IndependentCancel=LinkedCancel,
            publish_image_for_lens=lambda *a:'https://test/image',
            current_market=lambda:{'country':'kw'},DEFAULT_COUNTRY='kw',
            USE_FAST_LENS_PIPELINE=True,_photo_identity_future=lambda *a:Job(0 if reference else 30,{'query':'chair'}),
            _lens_reference_rows=lambda rows,reference:copy.deepcopy(rows),
            _web_image_retrieval_row=lambda row:dict(row),
            _web_merge_retrieval_evidence=lambda *a:None,_lens_has_price=lambda r:bool(r.get('price')),
            _lens_market_passes=lambda *a:[('all','kw',False),('all','us',True)],
            _web_lens_full_frame_url=lambda *a:'https://test/image',LENS_HTTP_POOL=Pool(),
            _serpapi_lens_request=None,LENS_TURBO_MAX_WAIT_SECONDS=4.5,LENS_TOTAL_TIMEOUT_SECONDS=18,
            LENS_HTTP_TIMEOUT_SECONDS=10,LENS_LOCAL_RESCUE_AFTER_SECONDS=2.5,
            LOCAL_DISCOVERY_TIMEOUT=8,LOCAL_DISCOVERY_ENABLED=native,
            MARKET_SUPPLEMENT_POOL=NativePool(),_run_with_market=None,_web_market=lambda c:{'country':c},
            _china_native_image_discovery=None,LOCAL_DISCOVERY_MAX_CALLS=2,
            LENS_LOCAL_LANE_RESCUE=False,result_market_rank=lambda row:row['rank'],
            ANDROID_IMAGE_PROGRESSIVE_MIN_RESULTS=1,ANDROID_IMAGE_PROGRESSIVE_MIN_LOCAL=1,
            LENS_MIN_MATCHES=3,wait=wait,FIRST_COMPLETED='first',
            LENS_TURBO_EMPTY_GRACE_SECONDS=3.5,
            _local_lane_count=lambda rows,ref:sum(r['rank']==0 for r in rows),
            LENS_READY_MIN_SECONDS=8,LENS_READY_GRACE_SECONDS=1,
            LENS_DIRECT_LOCAL_MAX=8,LENS_DIRECT_US_MAX=8,LENS_DIRECT_CN_MAX=8,LENS_RESULT_LIMIT=100,
            _web_result_group=lambda row:'primary',_web_keep_collection_children=lambda rows,allowed:rows)
        exec(compile(ast.Module(body=[copy.deepcopy(NODES['google_lens_lookup'])],type_ignores=[]),str(SOURCE),'exec'),ns)
        self.ns=ns

    def run(self, signal=True):
        with redirect_stdout(io.StringIO()) as output:
            result=self.ns['google_lens_lookup']('image','image/jpeg','en',light=True,
                progress_callback=self.previews.append,cancel_event=self.parent,
                ready_event=self.ready if signal else None)
        self.log=output.getvalue()
        return result


class LensCompletionTests(unittest.TestCase):
    def test_three_audited_local_signal_stops_source_wait_after_eight_seconds(self):
        f=LensFixture();result=f.run()
        self.assertGreaterEqual(f.clock.now,8);self.assertLess(f.clock.now,8.3)
        self.assertEqual(result['retrieval_completion'],'ready_local_sources')
        self.assertEqual(len(result['matches']),3)
        self.assertFalse(f.parent.is_set());self.assertTrue(f.jobs[-1].cancelled)
        self.assertIn('LENS READY COMPLETE',f.log)

    def test_no_signal_preserves_full_wait_and_late_results(self):
        f=LensFixture(ready_at=None,late_at=12);result=f.run()
        self.assertGreaterEqual(f.clock.now,12)
        self.assertEqual(len(result['matches']),4)
        self.assertNotIn('retrieval_completion',result)

    def test_legacy_caller_without_feedback_keeps_existing_wait(self):
        f=LensFixture(late_at=12);result=f.run(signal=False)
        self.assertGreaterEqual(f.clock.now,12)
        self.assertEqual(len(result['matches']),4)

    def test_late_ready_signal_gets_a_full_grace_and_keeps_completed_provider(self):
        f=LensFixture(ready_at=9,late_at=9.6);result=f.run()
        self.assertEqual(len(result['matches']),4)
        self.assertGreaterEqual(f.clock.now,9.6)
        self.assertNotIn('retrieval_completion',result)

    def test_revoked_readiness_does_not_finish_retrieval(self):
        f=LensFixture(ready_at=7.4,clear_at=7.8,late_at=12);result=f.run()
        self.assertGreaterEqual(f.clock.now,12)
        self.assertEqual(len(result['matches']),4)

    def test_unresolved_reference_cannot_finish_from_readiness_signal(self):
        f=LensFixture(reference=False,late_at=12);result=f.run()
        self.assertGreaterEqual(f.clock.now,12)
        self.assertNotIn('retrieval_completion',result)

    def test_client_cancellation_still_returns_cancelled_result(self):
        f=LensFixture();f.parent.set();result=f.run()
        self.assertTrue(result['cancelled']);self.assertEqual(result['matches'],[])

    def test_ready_finish_stops_native_lane_without_cancelling_parent(self):
        f=LensFixture(native=True);result=f.run()
        self.assertEqual(result['retrieval_completion'],'ready_local_sources')
        self.assertTrue(f.native_cancel.is_set());self.assertFalse(f.parent.is_set())
        before=len(f.previews);f.native_callback([{'title':'late','link':'https://test/late'}])
        self.assertEqual(len(f.previews),before)


class ReadinessIntegrationTests(unittest.TestCase):
    def test_core_signals_only_after_completed_audits_before_retrieval_finishes(self):
        fixture=stream_support.StreamTailTests()
        rows=[stream_support.offer(i,delay=.04) for i in range(3)]
        observed=[]
        def search(*args,ready_event=None):
            self.assertIsNotNone(ready_event);observed.append(ready_event.is_set())
            args[5]({'query':'chair','results':rows})
            self.assertFalse(ready_event.wait(.01),'unreviewed candidates signaled readiness')
            self.assertTrue(ready_event.wait(1),'completed audits never signaled retrieval')
            self.assertFalse(args[7].is_set(),'readiness cancelled the parent search')
            return {'query':'chair','market':{'country':'kw'},'results':rows,
                    'retrieval_completion':'ready_local_sources'}
        with redirect_stdout(io.StringIO()):
            events,batches,_,at_done,_=asyncio.run(fixture.collect(rows,default_search=search,wrapper=True))
        self.assertEqual(observed,[False]);self.assertEqual(batches,[[0,1,2]])
        self.assertEqual(events[-1]['event'],'done')
        self.assertEqual(events[-1]['completion_reason'],'ready_local_sources')
        self.assertEqual(events[-1]['count'],3);self.assertEqual(at_done,[False])

    def test_image_coordinator_passes_signal_to_lens_and_preserves_completion(self):
        event=threading.Event();seen=[]
        def lens(*a,**kw):
            seen.append(kw['ready_event'])
            return {'query':'chair','matches':[{}],'retrieval_completion':'ready_local_sources'}
        ns={
            're':re, 'MARKET_CTX':SimpleNamespace(), '_web_market':lambda c:{'country':c},'WEB_API_MAX_QUERY_CHARS':200,
            'LENS_DIRECT_MODE':True,'ENABLE_GOOGLE_LENS':True,'SERPAPI_API_KEY':'x','PUBLIC_BASE_URL':'x',
            'google_lens_lookup':lens,'_web_build_lens_items':lambda *a:[{'url':'https://test/p'}],
            'USE_V106_5_RESULT_PIPELINE':True,'_web_attach_captured_result_sections':lambda data,*a,**kw:data,
        }
        exec(compile(ast.Module(body=[copy.deepcopy(NODES['_web_search_image_sync'])],type_ignores=[]),str(SOURCE),'exec'),ns)
        with redirect_stdout(io.StringIO()):
            result=ns['_web_search_image_sync']('photo','image/jpeg','','kw','en',ready_event=event)
        self.assertEqual(seen,[event]);self.assertEqual(result['retrieval_completion'],'ready_local_sources')


if __name__=='__main__':unittest.main()
