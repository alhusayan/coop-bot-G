"""Real money parsers and listing binding; provider transport alone is simulated."""
import unittest
from findzia_choice_prices import labelled_current_quote
from verification import test_audit_prices as support
from concurrent.futures import ThreadPoolExecutor
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

if __name__=='__main__':unittest.main()
