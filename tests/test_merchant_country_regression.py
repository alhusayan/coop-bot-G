import ast
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from bs4 import BeautifulSoup
from findzia_market_evidence import MerchantMarkets


class MerchantCountryRegression(unittest.TestCase):
    def setUp(self):
        self.markets = MerchantMarkets({'kw': 'Kuwait', 'sa': 'Saudi Arabia', 'us': 'United States'})
        self.url = 'https://independent.example/products/burger'

    def document(self, *nodes):
        return BeautifulSoup('<script type="application/ld+json">' + json.dumps(list(nodes)) + '</script>', 'html.parser')

    def store(self, country='KW', **extra):
        return dict({'@type': 'OnlineStore', 'url': 'https://independent.example/',
                     'address': {'@type': 'PostalAddress', 'addressCountry': country}}, **extra)

    def scope(self, url=None, country='kw'):
        return self.markets.classify({'url': url or self.url, 'price': '3 KWD'}, country)['market_scope']

    def test_oz_both_domains_every_source_and_market(self):
        for domain in ('ozfactory.net', 'www.ozfactory.net', 'orderozmeat.com', 'www.orderozmeat.com'):
            for source in ('google_lens', 'google', 'serper', 'shopify_catalog'):
                for match in ('similar', 'visual_similarity', 'exact', 'catalog_search'):
                    row = dict(url=f'https://{domain}/products/beef-burger', source=source,
                               match_type=match, price='2.750 KWD', market_scope='unknown')
                    for kind, key in [('result','item'), ('upsert','item'), ('snapshot','results'),
                                      ('snapshot','all_results'), ('catalog','items')]:
                        payload = row if key == 'item' else [row]
                        for destination in ('kw','sa','us'):
                            out = self.markets.event({'event':kind,key:payload},destination)[key]
                            out = out if key == 'item' else out[0]
                            self.assertEqual(out['market_scope'], 'local' if destination == 'kw' else 'global')
                            self.assertEqual(out['merchant_country'], 'KW')
                            self.assertEqual(out['match_type'], match)
                            self.assertEqual(out['price'], row['price'])

    def test_oz_name_price_and_lookalike_cannot_prove_kuwait(self):
        for url in ('https://ozfactory.net.evil.example/p', 'https://other.example/ozfactory.net',
                    'https://ozfactory.example/p?country=kw'):
            row = self.markets.classify(dict(url=url,store='OZ',price='3 KWD'),'kw')
            self.assertEqual(row['market_scope'],'unknown')

    def test_own_store_address_recovers_unknown_for_all_sources(self):
        for country in ('KW','Kuwait', {'@type':'Country','name':'Kuwait'}):
            self.markets.observe_document(self.url, self.document({'@graph':[self.store(country)]}))
            for source in ('google_lens','google','shopify_catalog'):
                out = self.markets.classify(dict(url=self.url,source=source,match_type='similar'),'kw')
                self.assertEqual(out['market_scope'],'local')
                self.assertEqual(out['merchant_country_evidence'],'merchant_address')
                self.assertEqual(out['match_type'],'similar')
            self.assertEqual(self.scope(country='sa'),'global')

    def test_address_is_page_bound_and_does_not_leak_to_regional_branches(self):
        self.markets.observe_document(self.url, self.document(self.store()))
        self.assertEqual(self.scope(),'local')
        for url in ('https://independent.example/sa/products/burger',
                    'https://independent.example/products/burger?country=SA',
                    'https://sa.independent.example/products/burger',
                    'https://independent.example/products/other'):
            self.assertEqual(self.scope(url),'unknown')

    def test_brand_manufacturer_shipping_review_and_unrelated_org_are_not_seller_proof(self):
        for node in (
            {'@type':'Product','brand':self.store(),'manufacturer':self.store()},
            {'@type':'Product','offers':{'shippingDetails':{'addressCountry':'KW'}}},
            {'@type':'Review','itemReviewed':self.store()},
            self.store(url='https://another.example/'),
            {'@type':'Organization','address':{'addressCountry':'KW'}},
            self.store(country='delivery to Kuwait'),
        ):
            self.markets.observe_document(self.url,self.document(node))
            self.assertEqual(self.scope(),'unknown')

    def test_conflicting_addresses_and_later_conflicts_abstain(self):
        self.markets.observe_document(self.url,self.document(self.store()))
        self.markets.observe_document(self.url,self.document(self.store('US')))
        self.assertEqual(self.scope(),'unknown')
        self.markets.observe_document(self.url,self.document(self.store()))
        self.assertEqual(self.scope(),'unknown')

    def test_expiry_and_registered_regional_routes_take_precedence(self):
        with patch('findzia_market_evidence.time.monotonic',return_value=0):
            self.markets.observe_document(self.url,self.document(self.store()))
        with patch('findzia_market_evidence.time.monotonic',return_value=86401):
            self.assertEqual(self.scope(),'unknown')
        url='https://www.ikea.com/sa/en/p/chair'
        self.markets.observe_document(url,self.document(self.store(url='https://www.ikea.com/',country='KW')))
        self.assertEqual(self.scope(url),'global')
        self.assertEqual(self.scope(url,'sa'),'local')

    def test_existing_metadata_validation_observes_address_without_new_fetch(self):
        tree=ast.parse(Path('main.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_web_product_page_metadata')
        # Execute the real page-parser prefix through country observation. No
        # network client is supplied; it can only consume the existing document.
        prefix=fn.body[:6]
        code=compile(ast.fix_missing_locations(ast.Module(body=[ast.FunctionDef(
            name=fn.name,args=fn.args,body=prefix,decorator_list=[])] ,type_ignores=[])),'main.py','exec')
        ns={'BeautifulSoup':BeautifulSoup,'_web_merchant_access_reason':lambda *a:False,
            '_FZ_CATALOG':SimpleNamespace(markets=self.markets)}
        exec(code,ns)
        ns[fn.name](str(self.document(self.store())),self.url)
        self.assertEqual(self.scope(),'local')


if __name__=='__main__': unittest.main()
