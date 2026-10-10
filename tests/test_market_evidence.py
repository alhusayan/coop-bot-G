import asyncio
import json
import unittest
import httpx
from findzia_market_evidence import MerchantMarkets
from findzia_shopify_catalog import ShopifyCatalog, normalize_products
from tests.test_shopify_catalog import product, reply

class MarketTests(unittest.TestCase):
    def setUp(self):
        self.markets = MerchantMarkets(['kw','us','gb','sa','ae','io','co'],
            {'kw':[('Local','local.example')], 'us':[('US','foreign.example')],
             'sa':[('Shared','shared.example')], 'ae':[('Shared','shared.example')]})

    def test_currency_destination_and_search_lane_never_prove_origin(self):
        for price in ('3.250 KWD', '12.00 USD', '30.00 SAR'):
            row=self.markets.classify(dict(url='https://unknown.example/p?country=KW',
                price=price,country='kw',market_rank=0,market_scope='local',_shopping_gl='kw',
                market_evidence='local_currency',destination_country='KW'), 'kw')
            self.assertEqual(row['market_scope'],'unknown')
            self.assertIsNone(row['merchant_country']); self.assertEqual(row['flag'],'')
            self.assertEqual(row['price'],price)

    def test_confirmed_stores_keep_country_regardless_of_price_currency(self):
        for host,price,want in [('local.example','12.00 USD','local'),('foreign.example','3.250 KWD','global'),
                                ('store.com.kw','12.00 USD','local'),('store.co.uk','3.250 KWD','global')]:
            self.assertEqual(self.markets.classify(dict(url='https://'+host+'/p',price=price),'kw')['market_scope'],want)

    def test_ambiguous_generic_domains_and_lookalikes_abstain(self):
        for host in ('shared.example','local.example.attacker.com','shop.io','store.co'):
            self.assertEqual(self.markets.classify(dict(url='https://'+host+'/p'),'kw')['market_scope'],'unknown')

    def test_origin_filter_is_positive_evidence_and_context_relative(self):
        row=dict(url='https://store.example/p',merchant_country='KW',merchant_country_evidence='shopify_origin_filter',price='10.00 USD')
        self.assertEqual(self.markets.classify(row,'kw')['market_scope'],'local')
        self.assertEqual(self.markets.classify(row,'sa')['market_scope'],'global')

    def test_snapshot_and_late_updates_cannot_reintroduce_currency_classification(self):
        row=dict(url='https://unknown.example/p',market_scope='local',country='kw',price='5 KWD')
        for event in (dict(event='upsert',item=row),dict(event='snapshot',results=[row])):
            output=self.markets.event(event,'kw')
            fixed=output.get('item') or output['results'][0]
            self.assertEqual(fixed['market_scope'],'unknown')
        self.assertEqual(row['market_scope'],'local')

    def test_digital_products_cannot_supply_origin_filter_evidence(self):
        for shipping in (False, None):
            item=product()
            item['variants'][0]['requires']={'shipping':shipping}
            row=normalize_products([item],'kw',origin_country='KW')[0]
            self.assertIsNone(row['merchant_country'])
            self.assertEqual(row['market_scope'],'unknown')
        item['variants'][0]['requires']={'shipping':False}
        self.assertEqual(normalize_products([item],'kw',visual=True,origin_country='KW'),[])


class DiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_filter_proves_origin_general_absence_does_not(self):
        seen=[]
        def transport(request):
            args=json.loads(request.content)['params']['arguments']['catalog'];seen.append(args)
            if args['filters'].get('ships_from'):
                return httpx.Response(200,json=reply([product('USD',1500,url='https://local.example/products/a')]))
            return httpx.Response(200,json=reply([product('KWD',3250,url='https://unknown.example/products/b')]))
        catalog=ShopifyCatalog(['kw'],transport=httpx.MockTransport(transport))
        result=await catalog.search('perfume','kw')
        self.assertEqual(len(seen),2)
        self.assertEqual(seen[0]['filters']['ships_from'],[dict(country='KW')])
        self.assertTrue(all(x['filters']['ships_to']==dict(country='KW') for x in seen))
        self.assertEqual([r['market_scope'] for r in result['items']],['local','unknown'])
        self.assertEqual(result['items'][0]['price'],'15.00 USD')
        self.assertEqual(catalog.inflight,0)

    async def test_failed_local_filter_does_not_guess_and_general_still_works(self):
        def transport(request):
            args=json.loads(request.content)['params']['arguments']['catalog']
            if 'ships_from' in args['filters']: return httpx.Response(503)
            return httpx.Response(200,json=reply())
        result=await ShopifyCatalog(['kw'],transport=httpx.MockTransport(transport)).search('p','kw')
        self.assertEqual(result['status'],'ok');self.assertEqual(result['items'][0]['market_scope'],'unknown')
