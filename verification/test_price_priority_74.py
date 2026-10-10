"""Price recovery routing: useful cards first, fixed budgets and exact binding."""
import asyncio
import io
import time
import unittest
from contextlib import redirect_stdout
import test_audit_prices as price_support
import test_ready_tail_73 as tail_support


class PricePriorityTests(unittest.TestCase):
    def setUp(self):
        self.f=price_support.PriceTests();self.f.setUp();self.ns=self.f.ns
        self.ns['WEB_ASYNC_PRICE_SHARED_MARKETS']=2
        self.ns['_web_offer_image_candidates']=lambda r:r.get('images',[])

    def row(self,host='shop.test',**kw):
        return dict(dict(url='https://'+host+'/p',country='kw',title='chair'),**kw)

    def batch(self,rows,tried=None):return self.ns['_web_automatic_price_batches'](rows,tried)

    def test_pictured_offer_needing_only_price_beats_large_incomplete_merchant(self):
        rows={str(i):self.row('many.test',url=f'https://many.test/p{i}') for i in range(8)}
        rows['ready']=self.row('ready.test',images=['photo'],classification_final=True,identity_review_status='completed')
        self.assertEqual(next(iter(self.batch(rows)[0])),'ready')
        self.assertTrue(all(len(b)<=4 for b in self.batch(rows)))
        self.assertLessEqual(len(self.batch(rows)),2)

    def test_within_one_merchant_completed_audit_wins_a_tie(self):
        rows={'pending':self.row(images=['a']),
              'final':self.row(url='https://shop.test/final',images=['b'],
                    classification_final=True,identity_review_status='completed')}
        self.assertEqual(list(self.batch(rows)[0]),['final','pending'])

    def test_local_priority_is_not_lost_to_a_better_global_offer(self):
        rows={'us':self.row('global.test',country='us',images=['a']),
              'kw':self.row('local.test')}
        self.assertEqual(list(self.batch(rows)[0]),['kw'])

    def test_late_unserved_market_still_has_its_reserved_slot(self):
        tried={str(i):self.row('old.test', url=f'https://old.test/p{i}') for i in range(4)}
        rows={'local':self.row(images=['a']),
              'shein':self.row(url='https://us.shein.com/Dress-p-1234567.html',export_store=True)}
        self.assertEqual(list(self.batch(rows,tried)[0]),['shein'])

    def test_price_present_image_missing_uses_image_index(self):
        calls=[]
        self.ns['_fast_provider_search']=lambda engine,*a,**kw:calls.append(engine) or {}
        with redirect_stdout(io.StringIO()):
            self.ns['_web_targeted_price_updates']({'a':self.row(price='10 KWD')},'en',{'country':'kw'})
        self.assertEqual(calls,['test_images'])

    def test_amazon_asin_query_keeps_correct_listing_and_rejects_same_title_other_asin(self):
        row=self.row(url='https://www.amazon.ca/dp/B012345678',country='ca')
        self.f.responses['ca']=[{'link':row['url'],'price':'19 CAD','title':'chair'},
            {'link':'https://www.amazon.ca/dp/B999999999','price':'1 CAD','title':'chair'}]
        with redirect_stdout(io.StringIO()):
            result=self.ns['_web_targeted_price_updates']({'a':row},'en',{'country':'kw'})
        self.assertEqual(self.f.calls,[('(site:amazon.ca "B012345678")','ca','en')])
        self.assertEqual(result['a']['price'],'19.0 CAD')
        self.assertFalse(result['a']['price_verified'])

    def test_asin_never_authorizes_price_from_different_market_or_variant(self):
        row=self.row(url='https://www.amazon.ca/dp/B012345678?seller=A',country='ca')
        self.f.responses['ca']=[{'link':row['url'].replace('amazon.ca','amazon.com'),'price':'19 USD'},
            {'link':row['url'].replace('seller=A','seller=B'),'price':'18 CAD'}]
        with redirect_stdout(io.StringIO()):
            result=self.ns['_web_targeted_price_updates']({'a':row},'en',{'country':'kw'})
        self.assertEqual(result,{})

    def test_non_amazon_url_keeps_title_query(self):
        row=self.row(url='https://amazon.example.com/dp/B012345678')
        with redirect_stdout(io.StringIO()):self.ns['_web_targeted_price_updates']({'a':row},'en',{'country':'kw'})
        self.assertEqual(self.f.calls[0][0],'(site:amazon.example.com chair)')

    def test_stronger_reviewed_matches_use_existing_recovery_slots_first(self):
        rows={str(i):self.row(f'shop{i}.test',images=['photo'],classification_final=True,
              identity_review_status='completed',match_type='similar',match_score=.3)
              for i in range(8)}
        rows['exact']=self.row('exact.test',images=['photo'],classification_final=True,
              identity_review_status='completed',match_type='exact',match_score=.95)
        self.assertEqual(next(iter(self.batch(rows)[0])),'exact')
        self.assertLessEqual(sum(len(batch) for batch in self.batch(rows)),8)

    def test_ikea_sku_query_stays_in_its_country_and_rejects_other_offer(self):
        url='https://www.ikea.com/kw/en/p/poaeng-armchair-birch-veneer-s12345678/'
        row=self.row(url=url,images=['photo'])
        self.f.responses['kw']=[{'link':url,'title':'chair','price':'19 KWD'},
            {'link':url.replace('/kw/','/sa/'),'title':'chair','price':'9 SAR'},
            {'link':url.replace('12345678','99999999'),'title':'chair','price':'1 KWD'}]
        with redirect_stdout(io.StringIO()):
            result=self.ns['_web_targeted_price_updates']({'a':row},'en',{'country':'kw'})
        self.assertEqual(self.f.calls,[('(site:ikea.com/kw "s12345678" price)','kw','ar')])
        self.assertEqual(result['a']['price'],'19.0 KWD')
        self.assertEqual(result['a']['price_source_url'],url)
        self.assertFalse(result['a']['price_verified'])


class ReadyPriceStopTests(unittest.TestCase):
    def test_ready_snapshot_does_not_start_new_paid_recovery_after_page_miss(self):
        for reason in ('ready_local_sources','ready_local_tail'):
            calls=[]
            def recovery(*args):calls.append(args);return {}
            f=tail_support.PriceTailTests()
            with redirect_stdout(io.StringIO()):
                events,_,_,_=asyncio.run(f.collect(reason=reason,delay=.005,wait_seconds=.5,
                    recovery=recovery,snapshot_ready=True,source_pause=.04,page_succeeds=False))
            self.assertEqual(calls,[])
            self.assertEqual(events[-1]['priced_count'],3)

    def test_paid_recovery_already_running_can_still_complete_within_tail(self):
        calls=[]
        def recovery(rows,*args):
            calls.append(rows);time.sleep(.04)
            return {key:{'price':'5 KWD'} for key in rows}
        f=tail_support.PriceTailTests()
        with redirect_stdout(io.StringIO()):
            events,_,_,_=asyncio.run(f.collect(reason='ready_local_sources',delay=0,wait_seconds=.5,
                recovery=recovery,source_pause=.02,page_succeeds=False))
        self.assertEqual(len(calls),1)
        self.assertEqual(events[-1]['priced_count'],4)
        self.assertEqual(events[-1]['results'][-1]['price'],'5 KWD')

    def test_source_readiness_uses_short_tail_and_preserves_prices(self):
        f=tail_support.PriceTailTests()
        with redirect_stdout(io.StringIO()):
            events,elapsed,futures,_=asyncio.run(f.collect(reason='ready_local_sources'))
        self.assertLess(elapsed,4);self.assertGreaterEqual(elapsed,2.9)
        self.assertEqual(events[-1]['priced_count'],3)
        self.assertEqual(events[-1]['completion_reason'],'ready_local_sources')
        self.assertTrue(futures[0].cancelled())


if __name__=='__main__':unittest.main()
