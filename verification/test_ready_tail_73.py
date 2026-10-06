"""Actual stream coordinators, simulated retrieval/audit provider boundaries."""
import asyncio
import concurrent.futures
import contextlib
import contextvars
import io
import json
import threading
import time
import unittest

from test_audit_prices import scope


def offer(key, **changes):
    return dict(dict(id=key, url='https://shop.test/'+str(key), title='chair',
        country='kw', market_scope='local', price='10 KWD', images=['image'],
        classification_final=True, identity_review_status='completed',
        identity_match_percentage=90, match_type='exact'), **changes)


def gates():
    return {
        '_web_row_has_numeric_price':lambda r:bool(r.get('price')),
        '_web_offer_image_candidates':lambda r:r.get('images',[]),
        '_web_confirmable_price':lambda r:not r.get('unconfirmed'),
        '_web_price_review_reason':lambda r,m:r.get('price_problem'),
        '_web_alternative_visible':lambda r:not r.get('alternative_hidden'),
        '_market_offer_allowed':lambda r,m:not r.get('market_blocked'),
        '_fz_product_form_conflict':lambda q,t:t=='wrong form',
        '_card_offer_state':lambda r:r,
        '_web_flag_price_outliers':lambda rows:None,
    }


class ReadyRulesTests(unittest.TestCase):
    def test_each_required_gate_excludes_an_incomplete_or_rejected_offer(self):
        ns=scope(['_web_identity_ready_local_count'],gates())
        count=ns['_web_identity_ready_local_count'];market={'country':'kw'}
        self.assertEqual(count([offer(0)],'chair',market),1)
        for change in ({'market_scope':'global'}, {'classification_final':False},
                {'identity_review_status':'streaming'}, {'hidden':True},
                {'alternative_hidden':True}, {'market_blocked':True},
                {'title':'wrong form'}, {'price':''}, {'unconfirmed':True},
                {'price_problem':'currency_mismatch'}, {'images':[]},
                {'stock_status':'out_of_stock'}):
            with self.subTest(change=change):
                self.assertEqual(count([offer(0,**change)],'chair',market),0)

    def test_priority_is_complete_then_local_and_stable_for_ties(self):
        ns=scope(['_web_identity_review_priority'],gates())
        rows=[offer(1,price=''),offer(2,market_scope='global',country='us'),
              offer(3),offer(4),offer(5,images=[])]
        rows.sort(key=lambda r:ns['_web_identity_review_priority'](r,{'country':'kw'}))
        self.assertEqual([r['id'] for r in rows],[3,4,2,1,5])

    def test_group_price_rejections_do_not_count_or_mutate_source_rows(self):
        rows=[offer(i) for i in range(3)]
        def outliers(candidates):candidates[0].update(price='',price_status='suspect')
        ns=scope(['_web_identity_ready_local_count'],dict(gates(),_web_flag_price_outliers=outliers))
        self.assertEqual(ns['_web_identity_ready_local_count'](rows,'chair',{'country':'kw'}),2)
        self.assertTrue(all(r['price']=='10 KWD' for r in rows))


class StreamTailTests(unittest.TestCase):
    async def collect(self, rows, *, wrapper=False, text=False, tail=.035,
                      search=None, preview_ready=None, cancelled=None, default_search=None,
                      audit_budget=40.0):
        loop=asyncio.get_running_loop();scheduled=[];tokens=[];handles=[]
        cancel=cancelled or threading.Event()
        class Pool:
            def submit(inner, fn, *args):
                payload=args[2];token=args[-2];callback=args[-1]
                batch=payload['results'];scheduled.append([r['id'] for r in batch]);tokens.append(token)
                future=concurrent.futures.Future()
                def deliver():
                    if future.cancelled() or token.is_set():return
                    if preview_ready:preview_ready.set()
                    result={'results':[dict(r,hidden=False) for r in batch],
                            'identity_review_status':'completed'}
                    callback(result)
                    future.set_result(result)
                handles.append(loop.call_later(max(r.get('delay',0) for r in batch),deliver))
                return future
        async def drain(*args):
            if False:yield None
        market={'country':'kw'}
        overrides=dict(gates(),asyncio=asyncio,
            WEB_AI_CLASSIFIER_ENABLED=True,WEB_VISUAL_CLASSIFIER_ENABLED=True,GEMINI_API_KEY='test',
            WEB_IDENTITY_REVIEW_POOL=Pool(),WEB_IDENTITY_BATCH_PARALLEL=1,
            WEB_IDENTITY_FIRST_BATCH=3,WEB_IDENTITY_BATCH_SIZE=1,
            WEB_IDENTITY_READY_LOCAL_MIN=3,WEB_IDENTITY_READY_TAIL_SECONDS=tail,
            WEB_IDENTITY_AUDIT_BUDGET_SECONDS=audit_budget,
            WEB_IDENTITY_HEARTBEAT_SECONDS=.01,BUILD_ID='test',ANDROID_IMAGE_PROGRESSIVE=True,
            _run_with_market=lambda m,fn,*a:fn(*a),
            _web_market=lambda c:market,
            _web_image_retrieval_row=lambda r:dict(r),_web_text_retrieval_row=lambda r:dict(r),
            _web_apply_market_context=lambda r,m:dict(r),
            _web_fail_closed_visual_row=lambda r,reason:dict(r,hidden=True,match_type='similar'),
            _web_identity_offer_key=lambda r:str(r['id']),
            _web_identity_capture_key=lambda r,q:(r['id'],r['title'],q),
            _web_identity_public_row=lambda r:dict(r),
            _web_identity_result_sort_key=lambda r:r['id'],
            _web_group_results=lambda data:dict(data,alternative_count=0),
            _WEB_CLASSIFICATION_LABELS={'en':['Exact','Similar']},
            _fz_social_merge=lambda r,*a:r,
            _web_build_lens_items=lambda partial,*a:partial['results'],
            _web_search_image_sync=default_search or (lambda *a,**kw:{'query':'chair','market':market,'results':rows}),
            _web_attach_captured_result_sections=lambda *a:None,
            _web_spawn_price_enrich_task=lambda *a:None,
            _web_drain_price_enrich_events=drain,_web_stream_event=json.dumps,
            PHOTO_UNDERSTANDING_ENABLED=True,
            PHOTO_IDENTITY_LOCK=threading.Lock(),PHOTO_IDENTITY_PREVIEWS={},
            _photo_identity_key=lambda b:'photo',_photo_identity_public=lambda p,l:p)
        recognized=concurrent.futures.Future();recognized.set_result({'title':'chair'})
        overrides['_photo_identity_future']=lambda *a:recognized
        ns=scope(['_web_stream_image_identity_batches_core','_web_stream_image_identity_batches'],overrides)
        function=ns['_web_stream_image_identity_batches' if wrapper else '_web_stream_image_identity_batches_core']
        kwargs={'market_snapshot':market}
        if text:kwargs['reference_context']={'title':'chair'}
        if search:kwargs['search_fn']=search
        events=[];done_cancelled=[];started=time.monotonic()
        try:
            async for raw in function('photo','image/jpeg','chair','kw','en',cancel,**kwargs):
                event=json.loads(raw);events.append(event)
                if event.get('event')=='done':done_cancelled.append(cancel.is_set())
        finally:
            for handle in handles:handle.cancel()
        return events,scheduled,tokens,done_cancelled,time.monotonic()-started

    def run_case(self,*args,**kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return asyncio.run(self.collect(*args,**kwargs))

    def test_ready_cards_end_tail_and_do_not_promote_pending_offers(self):
        rows=[offer(i,delay=0 if i<3 else .2) for i in range(7)]
        events,batches,tokens,at_done,elapsed=self.run_case(rows)
        self.assertEqual(events[-1]['completion_reason'],'ready_local_tail')
        self.assertTrue(events[-1]['partial'])
        self.assertLess(elapsed,.17)
        self.assertEqual(batches,[[0,1,2],[3]])
        final=[e for e in events if e['event']=='snapshot'][-1]
        self.assertEqual([r['id'] for r in final['results']],[0,1,2])
        self.assertTrue(all(r['classification_final'] for r in final['results']))
        self.assertEqual(at_done,[False])
        self.assertTrue(all(t.is_set() for t in tokens))

    def test_recognition_wrapper_delivers_final_snapshot_and_done_after_tail(self):
        rows=[offer(i,delay=0 if i<3 else .2) for i in range(5)]
        events,*_=self.run_case(rows,wrapper=True)
        self.assertEqual(events[-1]['event'],'done')
        self.assertEqual(events[-1]['completion_reason'],'ready_local_tail')
        self.assertEqual(events[-1]['count'],3)
        self.assertTrue(any(e['event']=='recognition' for e in events))

    def test_less_than_three_local_cards_keeps_late_audit(self):
        rows=[offer(0),offer(1),offer(2,market_scope='global',country='us'),offer(3,delay=.07)]
        events,*_=self.run_case(rows,tail=.015)
        self.assertNotIn('completion_reason',events[-1])
        self.assertEqual(events[-1]['count'],4)

    def test_global_only_search_keeps_late_audit(self):
        rows=[offer(i,market_scope='global',country='us',delay=0 if i<3 else .07) for i in range(4)]
        events,*_=self.run_case(rows,tail=.015)
        self.assertEqual(events[-1]['count'],4)
        self.assertNotIn('completion_reason',events[-1])

    def test_audit_that_finishes_within_tail_is_preserved(self):
        rows=[offer(i,delay=0 if i<3 else .015) for i in range(4)]
        events,*_=self.run_case(rows,tail=.06)
        self.assertEqual(events[-1]['count'],4)
        self.assertNotIn('completion_reason',events[-1])

    def test_tail_waits_for_retrieval_and_removed_preview_cannot_return(self):
        ready=threading.Event();preview=[offer(i) for i in range(3)]
        final=[offer(10,delay=.035)]
        def search(*args):
            args[5]({'query':'chair','results':preview})
            if not ready.wait(.5):raise RuntimeError('preview audit did not run')
            time.sleep(.06)
            return {'query':'chair','market':{'country':'kw'},'results':final}
        events,*_=self.run_case(final,search=search,preview_ready=ready,tail=.015)
        self.assertEqual(events[-1]['count'],1)
        self.assertNotIn('completion_reason',events[-1])
        final_snapshot=[e for e in events if e['event']=='snapshot'][-1]
        self.assertEqual([r['id'] for r in final_snapshot['results']],[10])

    def test_text_path_does_not_schedule_visual_audits(self):
        events,batches,*_=self.run_case([offer(i) for i in range(4)],text=True)
        self.assertEqual(batches,[])
        self.assertEqual(events[-1]['count'],4)
        self.assertNotIn('completion_reason',events[-1])


class PriceTailTests(unittest.TestCase):
    async def collect(self, *, reason='ready_local_tail', delay=10, wait_seconds=10,
                      recovery=None, snapshot_ready=False, source_pause=0, page_succeeds=True):
        loop=asyncio.get_running_loop();handles=[];futures=[]
        class Pool:
            def submit(inner,fn,*args):
                future=concurrent.futures.Future();futures.append(future)
                def finish():
                    if not future.cancelled():future.set_result({'price':'7 KWD'} if page_succeeds else None)
                handles.append(loop.call_later(delay,finish))
                return future
        def price_facts(r):
            return {k:v for k,v in r.items() if k.startswith('price')}
        ns=scope(['_web_with_live_prices'],dict(gates(),asyncio=asyncio,
            _WEB_LIVE_PRICE_ACTIVE=contextvars.ContextVar('live',default=False),
            WEB_LIVE_PRICE_WAIT=10,WEB_LIVE_PRICE_WORKERS=2,WEB_LIVE_PRICE_POOL=Pool(),
            WEB_STOCK_REFRESH_MAX=0,WEB_LIVE_PAGE_IMAGES=False,
            WEB_PRICE_ENRICH_SHOPPING_FALLBACK=bool(recovery),
            _web_market=lambda c:{'country':c},_web_live_page_price=lambda *a:None,
            _web_live_page_image_only=lambda *a:None,
            _web_collection_url=lambda u:False,_web_identity_offer_key=lambda r:r['url'],
            _fz_social_row=lambda r:False,_web_cached_stock_facts=lambda *a:{},
            _web_offer_media_fields=lambda r:{},_web_merge_offer_images=lambda *a:{},
            _web_unproxy_image_url=lambda s:s,_web_is_http_url=lambda s:s.startswith('https://'),
            _web_price_facts=price_facts,_web_price_page_verified=lambda r:False,
            _web_price_display_fields=lambda r:{},_web_merchant_cooldown=lambda u:None,
            _web_flag_price_outliers=lambda rows:None,
            _web_live_snapshot=lambda event,rows:dict(event,results=list(rows.values())),
            _web_price_source_currency=lambda r:'KWD',_web_local_currency_conflict=lambda *a:False,
            _web_page_access_fields=lambda d:{},_CARD_FACT_FIELDS=(),
            _fz_regional_price_store=lambda u:False,
            _web_log_price_queue=lambda *a:None,_more_result_domain=lambda u:'shop.test',
            _web_stream_event=json.dumps,
            # These optional branches are disabled in this fixture.
            _WEB_STOCK_SLOTS=None,_WEB_STOCK_POOL=None,MARKET_CTX=None,
            _web_verified_page_snapshot=None,_web_stock_snapshot_facts=None,
            _WEB_PRICE_REVIEW_SLOTS=None,_WEB_PRICE_REVIEW_POOL=None,
            WEB_PRICE_REVIEW_SECONDS=1,WEB_PRICE_REVIEW_MAX=0,_web_hold_price=None,
            _indexed_recovery_allowed=lambda:bool(recovery),WEB_ASYNC_PRICE_SHARED_MARKETS=2 if recovery else 0,
            _web_automatic_price_batches=lambda rows,tried,market:[rows],_web_targeted_price_updates=recovery))
        ready=[offer(i,image='https://img.test/'+str(i)) for i in range(3)]
        missing=offer(4,price='',images=[])
        closed=[]
        async def source():
            try:
                yield json.dumps({'event':'snapshot','results':ready+[missing],
                    **({'completion_reason':reason,'partial':True} if snapshot_ready else {})})
                if source_pause:await asyncio.sleep(source_pause)
                yield json.dumps({'event':'done','partial':True,'completion_reason':reason})
            finally:closed.append(True)
        started=time.monotonic()
        try:
            events=[json.loads(e) async for e in ns['_web_with_live_prices'](
                source(),'en','kw',wait_seconds=wait_seconds)]
        finally:
            for handle in handles:handle.cancel()
        return events,time.monotonic()-started,futures,closed

    def run_case(self,**kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return asyncio.run(self.collect(**kwargs))

    def test_ready_tail_caps_price_wait_preserves_completed_prices_and_closes_source(self):
        events,elapsed,futures,closed=self.run_case()
        self.assertGreaterEqual(elapsed,2.9)
        self.assertLess(elapsed,4.0)
        final=events[-1]
        self.assertEqual(final['event'],'done')
        self.assertEqual(final['completion_reason'],'ready_local_tail')
        self.assertEqual(final['priced_count'],3)
        self.assertEqual([r['price'] for r in final['results'][:3]],['10 KWD']*3)
        self.assertTrue(futures[0].cancelled())
        self.assertEqual(closed,[True])

    def test_price_finishing_in_existing_shorter_window_is_kept(self):
        events,elapsed,_,_=self.run_case(delay=.025,wait_seconds=.5)
        self.assertLess(elapsed,.5)
        self.assertEqual(events[-1]['priced_count'],4)
        self.assertEqual(events[-1]['results'][-1]['price'],'7 KWD')

    def test_other_completion_reasons_keep_normal_price_window(self):
        events,elapsed,_,_=self.run_case(reason='other',delay=.025,wait_seconds=.5)
        self.assertEqual(events[-1]['priced_count'],4)
        self.assertEqual(events[-1]['completion_reason'],'other')


if __name__=='__main__':unittest.main()
