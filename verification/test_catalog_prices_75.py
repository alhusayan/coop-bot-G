"""Same-offer catalog prices, provider normalization and market/variant guards.

HTML fixtures are synthetic reproductions of observed Noon markup. SHEIN and
provider responses are simulated; no paid APIs or live merchant requests run.
"""
import html
import io
import ipaddress
import json
import unittest
from contextlib import redirect_stdout
from functools import lru_cache
from bs4 import BeautifulSoup
import test_audit_prices as support

NOON = 'https://www.noon.com/kuwait-en/candle/Z123456789ABCZ/p/'
COLLECTION = 'https://www.noon.com/kuwait-en/home-and-kitchen/home-decor/candles-and-holders/scented-candle/category/'
SHEIN = 'https://us.shein.com/Candle-p-1234567.html'


def card(url=NOON, price='KWD 6.57', extra=''):
    return ('<a href="'+url+'"><div class="_wrapper_i1yaq_1">'
            '<img src="https://img.example.com/candle.jpg" alt="Blue candle"/>'
            '<h2>Blue candle</h2><div data-qa="plp-product-box-price">'
            '<div class="_sellingPrice_layq2_13">'+price+'</div>'
            '<span class="_oldPrice_layq2_84 strikeThrough">KWD 13.04</span>'
            '<span class="discount">49% Off</span>'+extra+'</div></div></a>')


class CatalogPrices(unittest.TestCase):
    def setUp(self):
        self.ns = support.scope(['_web_collection_products','_web_fetch_collection',
                                 '_web_catalog_card_quote','_serper_to_serpapi',
                                 '_web_image_search_records','_web_indexed_offer_quote',
                                 '_web_same_index_listing','_web_listing_price_country'], {
            'BeautifulSoup': BeautifulSoup, 'html':html, 'lru_cache':lru_cache, 'ipaddress':ipaddress,
            'current_market': lambda:{'country':'kw'}, 'DEFAULT_COUNTRY':'kw',
            'HEADERS':{}, '_web_image_is_generic':lambda *a:False})

    def quote(self, markup, url=NOON):
        return self.ns['_web_catalog_card_quote'](BeautifulSoup(markup,'html.parser').find('a'),url)

    def test_noon_current_sibling_currency_and_discount(self):
        price='<span class="currency">KWD</span><strong class="amount">6.57</strong>'
        self.assertEqual(self.quote(card(price=price))['min'],6.57)

    def test_shein_current_price_keeps_storefront_currency(self):
        self.assertEqual(self.quote(card(SHEIN,'$8.95'),SHEIN)['currency'],'USD')
        self.assertEqual(self.quote(card(SHEIN,'$8.95'),SHEIN)['min'],8.95)

    def test_shein_euro_current_price(self):
        url=SHEIN.replace('us.shein','fr.shein')
        self.assertEqual(self.quote(card(url,'€8,95'),url)['min'],8.95)

    def test_old_coupon_shipping_installment_and_hidden_prices_do_not_compete(self):
        extra=('<div class="shippingPrice">KWD 1</div><div class="coupon-price">KWD 2</div>'
               '<div class="monthly-price">KWD 3</div><div class="price" hidden>KWD 4</div>'
               '<del class="price">KWD 9</del><div class="price" aria-hidden="true">KWD 8</div>')
        self.assertEqual(self.quote(card(extra=extra))['min'],6.57)

    def test_only_discount_and_old_price_are_not_a_current_price(self):
        self.assertIsNone(self.quote(card(price='')))

    def test_conflicting_current_prices_are_rejected(self):
        self.assertIsNone(self.quote(card(extra='<div class="sale-price">KWD 7.57</div>')))

    def test_bare_number_not_a_price(self):
        self.assertIsNone(self.quote(card(price='4.8')))

    def test_no_cross_card_price_borrowing(self):
        markup='<html><div class="product-card">'+card(price='')+card(NOON.replace('Z123456789ABCZ','Z999999999ABCZ'))+'</div></html>'
        self.assertEqual(self.ns['_web_collection_products'](markup,COLLECTION),[])

    def test_large_navigation_and_unpriced_itemlist_do_not_hide_noon_grid(self):
        # Both original hard caps (1.2 MB and 1800 navigation links) are exceeded.
        listing={'@type':'ItemList','itemListElement':[{'@type':'ListItem','name':'Blue candle','url':NOON}]}
        markup='<html><script type="application/ld+json">'+json.dumps(listing)+'</script>'
        markup+='<nav>'+('<a href="/navigation/">Help</a>'*1900)+'x'*1200000+'</nav>'
        markup+='<div data-qa="plp-grid">'+card(NOON+'?o=seller-a')+'</div></html>'
        rows=self.ns['_web_collection_products'](markup,COLLECTION)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['link'],NOON+'?o=seller-a')
        self.assertEqual(self.ns['_web_indexed_offer_quote'](rows[0])['min'],6.57)
        self.assertTrue(rows[0]['image'])

    def test_partial_last_card_does_not_create_partial_amount(self):
        markup='<html><div data-qa="plp-grid">'+card()+card(NOON.replace('Z123456789ABCZ','Z999999999ABCZ')).split('6.57')[0]+'6'
        rows=self.ns['_web_collection_products'](markup,COLLECTION)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['link'],NOON)

    def test_collection_fetch_uses_bounded_merchant_specific_limit(self):
        calls=[]
        self.ns['_web_merchant_document']=lambda *a,**kw:calls.append(kw) or {'reason':'blocked'}
        for u in (COLLECTION,'https://us.shein.com/pdsearch/candle/','https://other.test/collections/candle'):
            self.assertEqual(self.ns['_web_fetch_collection'](u),[])
        self.assertEqual([c['max_bytes'] for c in calls],[3000000,3000000,1200000])
        self.assertTrue(all(c['html_prefix'] for c in calls))

    def test_shein_provider_image_price_survives_both_normalization_layers(self):
        raw={'images':[{'link':SHEIN,'title':'Blue candle','imageUrl':'https://img.example.com/1.jpg','price':'$8.95','currency':'USD'}]}
        mapped=self.ns['_serper_to_serpapi']('images',raw)
        records=self.ns['_web_image_search_records'](mapped)
        self.assertEqual(len(records),1)
        self.assertEqual(self.ns['_web_indexed_offer_quote'](records[0])['min'],8.95)

    def test_installments_survive_image_normalization_and_are_rejected(self):
        row={'link':SHEIN,'title':'Blue candle','imageUrl':'https://img.example.com/1.jpg','price':'$2.95', 'currency':'USD','installments_description':'4 payments'}
        out=self.ns['_serper_to_serpapi']('images',{'images':[row]})
        self.assertIsNone(self.ns['_web_indexed_offer_quote'](self.ns['_web_image_search_records'](out)[0]))

    def test_organic_rich_price_and_exact_price_attribute_survive(self):
        rows=[{'link':NOON,'rich_snippet':{'top':{'detected_extensions':{'price':6.57,'currency':'KWD'}}}},
              {'link':SHEIN,'attributes':{'Price':'US$8.95','Shipping':'US$1'}}]
        out=self.ns['_serper_to_serpapi']('search',{'organic':rows})['organic_results']
        self.assertEqual([self.ns['_web_indexed_offer_quote'](r)['min'] for r in out],[6.57,8.95])

    def test_discount_attributes_never_become_price(self):
        out=self.ns['_serper_to_serpapi']('search',{'organic':[{'link':SHEIN,'attributes':{'Original Price':'$8.95','Shipping':'$1','Discount':'$2'}}]})['organic_results'][0]
        self.assertIsNone(self.ns['_web_indexed_offer_quote'](out))

    def test_noon_same_sku_allows_name_or_ui_language_change_only(self):
        same=self.ns['_web_same_index_listing']
        self.assertTrue(same(NOON,NOON.replace('/candle/','/blue-candle/').replace('kuwait-en','kuwait-ar')))
        for u in (NOON.replace('kuwait-en','saudi-en'),NOON+'?o=other',NOON+'?currency=USD',NOON.replace('Z123456789ABCZ','Z999999999ABCZ'),NOON.replace('noon.com','noon.com.evil.test')):
            self.assertFalse(same(NOON,u),u)

    def test_shein_market_and_variant_guards_unchanged(self):
        same=self.ns['_web_same_index_listing']
        self.assertTrue(same(SHEIN,SHEIN.replace('Candle-','Bougie-')))
        for u in (SHEIN.replace('us.shein','fr.shein'),SHEIN+'?sku=other',SHEIN+'?currency=EUR',SHEIN.replace('1234567','1234568')):
            self.assertFalse(same(SHEIN,u),u)

    def test_noon_retrieval_market_comes_from_listing_not_visitor(self):
        row={'url':NOON,'country':'us','export_store':True}
        self.assertEqual(self.ns['_web_listing_price_country'](row,{'country':'sa'}),'kw')


class RecoveryQueries(unittest.TestCase):
    def test_noon_query_uses_observed_sku_locale_and_same_offer_price(self):
        fixture=support.PriceTests();fixture.setUp()
        row={'url':NOON+'?o=one','title':'Blue candle','country':'kw'}
        fixture.responses['kw']=[{'link':row['url'].replace('/candle/','/new-name/'),'price':'6.57 KWD'},
                                  {'link':NOON+'?o=two','price':'1 KWD'}]
        with redirect_stdout(io.StringIO()):
            updates=fixture.recover({'a':row})
        self.assertEqual(fixture.calls,[('(site:noon.com/kuwait-en "Z123456789ABCZ" price)','kw','ar')])
        self.assertEqual(updates['a']['price'],'6.57 KWD')

    def test_shein_price_query_is_scoped_and_does_not_add_requests(self):
        fixture=support.PriceTests();fixture.setUp()
        row={'url':SHEIN,'title':'Blue candle','country':'cn','export_store':True}
        fixture.responses['us']=[{'link':SHEIN,'price':'US$8.95'}, {'link':SHEIN.replace('us.shein','fr.shein'),'price':'EUR 1'}]
        with redirect_stdout(io.StringIO()):
            result=fixture.recover({'a':row})
        self.assertEqual(fixture.calls,[('(site:us.shein.com "1234567" price)','us','en')])
        self.assertEqual(result['a']['price'],'8.95 USD')


if __name__=='__main__':unittest.main()
