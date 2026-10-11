"""Real money parsers and listing binding; provider transport alone is simulated."""
import unittest
from findzia_choice_prices import labelled_current_quote, race_listing_prices
from verification import test_audit_prices as support
from concurrent.futures import ThreadPoolExecutor, Future
import threading
import time
from functools import lru_cache

JYSK='https://jysk.com.kw/armchair-sindal-black-3305416.html'
SALE='Special Price KD 38.500 Regular Price KD 55.000 You Save 30% (KD 16.50)'

class ChoicePriceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns=support.scope(['_web_price_quote'])

    def quote(self, text):
        return labelled_current_quote({'snippet':text},self.ns['_web_price_quote'],'kw')

    def test_current_price_is_not_old_price_or_savings(self):
        quote=self.quote(SALE)
        self.assertEqual((quote['min'],quote['currency']),(38.5,'KWD'))

    def test_ambiguous_or_conditional_prices_rejected(self):
        for text in ['KD 38.500 KD 55.000', 'Regular Price KD 55.000 You Save KD 16.50',
                     'Sale Price 38.500', 'Now KD 2 per month', 'Sale Price KD 2 with coupon SAVE',
                     'Sale Price from KD 2', 'Now KD 2–KD 5',
                     'Sale Price KD 38.500 Current Price KD 35.000']:
            with self.subTest(text=text):self.assertIsNone(self.quote(text))

    def test_blocked_merchant_recovers_indexed_price_through_real_final_money_gate(self):
        fixture=support.PriceTests();fixture.setUp()
        fixture.responses['kw']=[{'link':JYSK,'title':'Armchair SINDAL black','snippet':SALE}]
        with ThreadPoolExecutor(max_workers=1) as pool:
            overrides=dict(fixture.ns,lru_cache=lru_cache,
                           _web_live_page_price=lambda *a:{'page_fetch_status':'blocked'},
                           _FZ_CHOICE_PRICE_PAGE_POOL=pool)
            ns=support.scope(['_web_choice_price_recovery','_fz_eval_money'],overrides)
            row={'url':JYSK,'title':'Armchair SINDAL black','country':'kw','currency':'KWD',
                 'market_scope':'local','price_unavailable':True,'price_status':'unavailable'}
            result=ns['_web_choice_price_recovery'](row,'kw','en')
            self.assertEqual(ns['_fz_eval_money'](result)['amount'],38.5)
            self.assertFalse(result['price_unavailable'])
            self.assertEqual(result['price_status'],'indexed')

    def test_exact_listing_recovery_passes_final_price_policy(self):
        fixture=support.PriceTests();fixture.setUp();ns=fixture.ns
        row={'url':JYSK,'title':'Armchair SINDAL black','country':'kw','market_scope':'local'}
        fixture.responses['kw']=[{'link':JYSK,'title':row['title'],'snippet':SALE}]
        # Original shared route retains its existing strict parser.
        before=ns['_web_targeted_price_updates']({JYSK:row},'en',{'country':'kw','currency':'KWD'})
        self.assertFalse(before.get(JYSK,{}).get('price'))
        updates=ns['_web_targeted_price_updates']({JYSK:row},'en',{'country':'kw','currency':'KWD'},choice_price=True)
        recovered=dict(row,**updates[JYSK])
        self.assertEqual(recovered['price'],'38.5 KWD')
        self.assertEqual(recovered['price_source_url'],JYSK)
        self.assertTrue(ns['_web_confirmable_price'](recovered))
        # Another SKU or another storefront cannot donate its sale price.
        for url in [JYSK.replace('3305416','3305417'),JYSK.replace('.com.kw','.ae')]:
            fixture.responses['kw']=[{'link':url,'title':row['title'],'snippet':SALE}]
            updates=ns['_web_targeted_price_updates']({JYSK:row},'en',{'country':'kw','currency':'KWD'},choice_price=True)
            self.assertFalse(updates.get(JYSK,{}).get('price'))

    def test_regional_sale_price_survives_store_policy_but_not_wrong_currency(self):
        fixture=support.PriceTests();fixture.setUp()
        overrides=dict(fixture.ns,lru_cache=lru_cache)
        # Use the actual regional policy too, not the nonregional transport fixture.
        for name in ('_web_targeted_price_updates','_fz_regional_price_store','_fz_regional_index_quote'):
            overrides.pop(name,None)
        ns=support.scope(['_web_targeted_price_updates','_fz_regional_price_store','_fz_regional_index_quote'],overrides)
        url='https://intersport.com.kw/adidas-metalbone-ctrl-2026-padel-racket.html'
        row={'url':url,'title':'Adidas Metalbone CTRL 2026','country':'kw','market_scope':'local'}
        market={'country':'kw','currency':'KWD'}
        for snippet,expected in [(SALE,'38.5 KWD'),(SALE.replace('KD','AED'),None),
                                 ('Regular Price KD 55 Save KD 16.50',None),
                                 ('Special Price KD 38.500 Current Price KD 35.000',None)]:
            with self.subTest(snippet=snippet):
                fixture.responses['kw']=[{'link':url,'title':row['title'],'snippet':snippet}]
                updates=ns['_web_targeted_price_updates']({url:row},'en',market,choice_price=True)
                self.assertEqual(updates.get(url,{}).get('price'),expected)

    def test_page_price_finishing_after_empty_index_is_not_discarded(self):
        fixture=support.PriceTests();fixture.setUp()
        row={'url':JYSK,'title':'Armchair SINDAL black','country':'kw','market_scope':'local'}
        page_ready=threading.Event()
        def page(*args):
            page_ready.wait(2)
            # Ensure the empty index has returned before this result completes.
            time.sleep(.02)
            return {'price':'38.5 KWD','price_amount':38.5,'currency':'KWD',
                    'price_verified':True,'price_status':'verified','price_source':'product_page'}
        def index(*args,**kwargs):
            page_ready.set()
            return {}
        with ThreadPoolExecutor(1) as pages, ThreadPoolExecutor(1) as indexes:
            overrides=dict(fixture.ns,lru_cache=lru_cache,_web_live_page_price=page,
                _web_targeted_price_updates=index,_FZ_CHOICE_PRICE_PAGE_POOL=pages,
                _FZ_CHOICE_PRICE_INDEX_POOL=indexes)
            ns=support.scope(['_web_choice_price_recovery','_fz_eval_money'],overrides)
            result=ns['_web_choice_price_recovery'](row,'kw','en')
            self.assertIsNotNone(result,'An empty index must not cancel an outstanding merchant price')
            self.assertEqual(ns['_fz_eval_money'](result)['amount'],38.5)
            self.assertTrue(result['price_verified'])

    def test_fast_merchant_price_avoids_an_index_request(self):
        page=Future();page.set_result({'price':'38.5 KWD'})
        result,states=race_listing_prices(page,lambda:self.fail('Unnecessary index lookup'),lambda value:value)
        self.assertEqual(result['price'],'38.5 KWD')
        self.assertEqual(states,{'page':'accepted'})

    def test_valid_index_does_not_wait_for_blocked_page_and_deadline_is_finite(self):
        page=Future();page.set_running_or_notify_cancel()
        index=Future();index.set_result({'price':'38.5 KWD'})
        result,states=race_listing_prices(page,lambda:index,lambda value:value,timeout=.1,grace=0)
        self.assertEqual(result['price'],'38.5 KWD')
        self.assertEqual(states,{'index':'accepted','page':'pending'})
        pending=Future();pending.set_running_or_notify_cancel()
        result,states=race_listing_prices(page,lambda:pending,lambda value:value,timeout=.01,grace=0)
        self.assertIsNone(result)
        self.assertEqual(states,{'index':'pending','page':'pending'})

    def test_out_of_stock_cannot_borrow_index_price(self):
        page=Future();page.set_result({'availability':'https://schema.org/OutOfStock'})
        result,states=race_listing_prices(page,lambda:self.fail('Known unavailable product'),lambda value:value)
        self.assertIsNone(result)
        self.assertEqual(states,{'page':'out_of_stock'})

if __name__=='__main__':unittest.main()
