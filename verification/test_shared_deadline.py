"""Regression scenarios from 62–65 second Kuwait searches; no paid calls."""
import contextlib
import io
import threading
import time
import unittest

import test_audit_prices as audit
import test_ready_tail_73 as tail


class SharedDeadlineTests(unittest.TestCase):
    def run_case(self,*a,**kw):
        return tail.StreamTailTests().run_case(*a,**kw)

    def test_global_only_does_not_wait_for_all_slow_batches(self):
        rows=[tail.offer(i,market_scope='global',country='us',delay=0 if i<3 else .4) for i in range(8)]
        events,batches,tokens,done_cancelled,elapsed=self.run_case(rows,audit_budget=.06)
        self.assertLess(elapsed,.25)
        self.assertEqual(batches,[[0,1,2],[3]])
        self.assertEqual(events[-1]['completion_reason'],'identity_audit_deadline')
        self.assertEqual(events[-1]['count'],3)
        self.assertEqual(done_cancelled,[False])
        self.assertTrue(all(token.is_set() for token in tokens))
        final=[e for e in events if e.get('event')=='snapshot'][-1]
        self.assertEqual([r['id'] for r in final['results']],[0,1,2])
        self.assertTrue(all(r['classification_final'] for r in final['results']))

    def test_fewer_than_three_local_results_still_has_a_deadline(self):
        rows=[tail.offer(0),tail.offer(1),tail.offer(2,market_scope='global',country='us')]
        rows += [tail.offer(i,market_scope='global',country='us',delay=.4) for i in range(3,7)]
        events,batches,_,_,elapsed=self.run_case(rows,audit_budget=.06)
        self.assertLess(elapsed,.25)
        self.assertEqual(events[-1]['count'],3)
        self.assertEqual(events[-1]['completion_reason'],'identity_audit_deadline')
        self.assertEqual(batches,[[0,1,2],[3]])

    def test_no_completed_audit_is_not_promoted_to_a_valid_result(self):
        events,batches,_,_,elapsed=self.run_case([tail.offer(i,delay=.4) for i in range(5)],audit_budget=.06)
        self.assertLess(elapsed,.25)
        self.assertEqual(events[-1]['count'],0)
        self.assertTrue(events[-1]['partial'])
        self.assertEqual(events[-1]['completion_reason'],'identity_audit_deadline')
        self.assertEqual(batches,[[0,1,2]])

    def test_completed_batches_inside_budget_keep_all_results(self):
        rows=[tail.offer(i,market_scope='global',country='us',delay=.008) for i in range(5)]
        events,batches,_,_,_=self.run_case(rows,audit_budget=.2)
        self.assertEqual(events[-1]['count'],5)
        self.assertNotIn('completion_reason',events[-1])
        self.assertEqual(batches,[[0,1,2],[3],[4]])

    def test_late_retrieval_owns_final_membership(self):
        ready=threading.Event()
        preview=[tail.offer(i) for i in range(3)]
        def search(*args):
            args[5]({'query':'chair','results':preview})
            self.assertTrue(ready.wait(.3))
            time.sleep(.07)
            return {'query':'chair','market':{'country':'kw'},'results':[preview[0],tail.offer(20)]}
        events,batches,_,_,_=self.run_case([],search=search,preview_ready=ready,audit_budget=.04)
        final=[e for e in events if e.get('event')=='snapshot'][-1]
        self.assertEqual([r['id'] for r in final['results']],[0])
        self.assertEqual(batches,[[0,1,2]])
        self.assertEqual(events[-1]['completion_reason'],'identity_audit_deadline')

    def test_text_search_does_not_use_photo_audit_deadline(self):
        rows=[tail.offer(i) for i in range(5)]
        def search(*args):
            time.sleep(.04)
            return {'query':'chair','market':{'country':'kw'},'results':rows}
        events,batches,_,_,_=self.run_case(rows,text=True,search=search,audit_budget=.01)
        self.assertEqual(events[-1]['count'],5)
        self.assertEqual(batches,[])
        self.assertNotIn('completion_reason',events[-1])

    def test_fetch_time_and_shared_owner_wait_use_the_same_window(self):
        clock,rows,ns=audit.AuditWaitTests().make(34)
        deadlines=[]
        def evidence(*a,**kw):
            deadlines.append(kw['_deadline'])
            clock.now+=6
            return 'reference',{0:'image0',1:'image1'}
        def live(*a,**kw):
            deadlines.append(kw['_request_deadline'])
            clock.now=kw['_request_deadline']-2
            return {'items':[{'id':0,'match':'exact'}],'reference_profile':{'kind':'test'}}
        ns['_web_visual_collect_evidence']=evidence
        ns['_web_ai_classifier_request_live']=live
        with contextlib.redirect_stdout(io.StringIO()):
            result=ns['_web_ai_classifier_request']('',rows,{}, {'image_b64':'test'})
        self.assertEqual(deadlines,[35,35])
        self.assertAlmostEqual(clock.now,34)
        self.assertEqual([i['id'] for i in result['items']],[0,1])

    def test_expired_queued_batch_starts_no_image_or_ai_request(self):
        clock,rows,ns=audit.AuditWaitTests().make()
        clock.now=41
        ns['_web_visual_collect_evidence']=lambda *a,**kw:self.fail('late image work')
        ns['_web_ai_classifier_request_live']=lambda *a,**kw:self.fail('late AI request')
        result=ns['_web_ai_classifier_request']('',rows,{}, {'image_b64':'test'},_request_deadline=40)
        self.assertEqual(result['review_error'],'timeout')

    def test_shared_owner_is_not_given_a_fresh_window(self):
        clock,rows,ns=audit.AuditWaitTests().make(60)
        clock.now=38
        ns['_web_ai_classifier_request_live']=lambda *a,**kw:{'items':[{'id':0,'match':'exact'}],'reference_profile':{'kind':'test'}}
        with contextlib.redirect_stdout(io.StringIO()):
            result=ns['_web_ai_classifier_request']('',rows,{}, {'image_b64':'test'},_request_deadline=40)
        self.assertLessEqual(clock.now,40.00001)
        self.assertEqual([i['id'] for i in result['items']],[0])
        self.assertEqual(result['review_error'],'partial_offer_review')

if __name__=='__main__':unittest.main()
