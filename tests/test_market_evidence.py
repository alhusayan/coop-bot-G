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

class VerifiedStorefrontTests(unittest.TestCase):
    def test_furniture_national_storefronts_survive_both_photo_filters(self):
        markets=MerchantMarkets(['kw','sa','ae','qa','eg','jp','de','gb','us','bh','om'])
        for host,cc,lang in [('ikea.com','kw','en'),('ikea.com','sa','ar'),
                             ('ikea.com','jp','ja'),('ikea.com','de','de'),
                             ('ikea.com','gb','en'),('homecentre.com','kw','en'),
                             ('homecentre.com','qa','ar'),('homecentre.com','eg','en')]:
            for source in ('google_lens','shopify_catalog'):
                row=dict(url=f'https://www.{host}/{cc}/{lang}/p/chair-12345678/',
                         source=source,match_type='similar',price='15 USD')
                local=markets.classify(row,cc)
                self.assertEqual(local['market_scope'],'local')
                self.assertEqual(local['merchant_country'],cc.upper())
                self.assertEqual(local['match_type'],'similar')
                self.assertEqual(local['price'],'15 USD')
                self.assertEqual(markets.classify(row,'us')['market_scope'],'global')
        for url in ('https://ikea.com/global/en/p/chair',
                    'https://ikea.com/kw-fake/en/p/chair',
                    'https://ikea.com/p/chair?country=kw',
                    'https://ikea.com.evil.example/kw/en/p/chair',
                    'https://homecentre.com/en/p/chair?country=kw',
                    'https://homecentre.com/kw-fake/en/p/chair'):
            self.assertEqual(markets.classify(dict(url=url),'kw')['market_scope'],'unknown')

    def test_recording_photo_stores_recover_local_without_losing_similarity(self):
        markets=MerchantMarkets(['kw','sa','ae','bh','qa','om','lb','iq'])
        urls=('https://www.azadea.com/kw/en/buy-kipsta-volleyball/54_8972682_000.html',
              'https://gcc.luluhypermarket.com/en-kw/volleyball-assorted/p/114752',
              'https://alnasser.net/products/volleyball',
              'https://prosportskw.com/products/molten-v5m5000-volleyball-size-5',
              'https://thebr.com/products/jh1273')
        for source in ('google_lens','shopify_catalog'):
            rows=[dict(url=url,source=source,match_type='visual_similarity',
                       price='8.00 USD',market_scope='unknown') for url in urls]
            for key in ('items','results','all_results'):
                output=markets.event({'event':'snapshot',key:rows},'kw')[key]
                self.assertEqual([r['market_scope'] for r in output],['local']*len(urls))
                self.assertTrue(all(r['match_type']=='visual_similarity' for r in output))
                self.assertTrue(all(r['price']=='8.00 USD' for r in output))
            self.assertTrue(all(r['market_scope']=='unknown' for r in rows))
            self.assertTrue(all(markets.classify(r,'sa')['market_scope']=='global' for r in rows))

    def test_national_branches_do_not_inherit_kuwait_or_buyer_destination(self):
        markets=MerchantMarkets(['kw','sa','ae','bh','qa','om','lb','iq'])
        for url,country in (
                ('https://www.alnasser.net/ar/products/ball','kw'),
                ('https://ksa.alnasser.net/products/ball','sa'),
                ('https://bh.alnasser.net/products/ball','bh'),
                ('https://azadea.com/en/product/ball','ae'),
                ('https://azadea.com/lb/en/product/ball','lb'),
                ('https://azadea.com/qa/en/product/ball','qa'),
                ('https://azadea.com/iq/ar/product/ball','iq'),
                ('https://letstango.com/products/mikasa-volley-ball','ae'),
                *((f'https://gcc.luluhypermarket.com/{lang}-{cc}/ball/p/123',cc)
                  for lang in ('en','ar') for cc in ('kw','sa','ae','bh','qa','om'))):
            with self.subTest(url=url):
                row=dict(url=url,price='3 KWD',match_type='similar')
                self.assertEqual(markets.classify(row,country)['market_scope'],'local')
                self.assertEqual(markets.classify(row,'kw')['market_country'],country)
        for url in ('https://unknown.alnasser.net/products/ball',
                    'https://ksa.alnasser.net.evil.example/products/ball',
                    'https://gcc.luluhypermarket.com/en-kw-fake/p/123',
                    'https://gcc.luluhypermarket.com/p/123?country=kw',
                    'https://azadea.com/kw-fake/en/ball',
                    'https://unknown.example/kw/en/ball',
                    'https://azadea.com/product/ball?country=kw'):
            with self.subTest(url=url):
                self.assertEqual(markets.classify(dict(url=url),'kw')['market_scope'],'unknown')

    def test_known_local_stores_and_national_routes_ignore_currency(self):
        markets=MerchantMarkets(['kw','sa','ae','bh','qa','om','eg','us'])
        for url in ('https://rullart.com/en/products/rug',
                    'https://www.karazonline.com/en/product/1',
                    'https://www.centrepointstores.com/kw/en/p/1',
                    'https://www.noon.com/kuwait-en/product/N1/p/'):
            with self.subTest(url=url):
                row=markets.classify(dict(url=url,price='20 USD'),'kw')
                self.assertEqual(row['market_scope'],'local')
                self.assertEqual(row['merchant_country_evidence'],'registered_storefront')
                self.assertEqual(markets.classify(dict(url=url,price='20 KWD'),'sa')['market_scope'],'global')

    def test_national_routes_require_registered_host_and_whole_path(self):
        markets=MerchantMarkets(['kw','sa'])
        for url in ('https://unknown.example/kw/en/p',
                    'https://centrepointstores.com.evil.example/kw/en/p',
                    'https://centrepointstores.com/kw-fake/en/p',
                    'https://centrepointstores.com/p?country=kw',
                    'https://noon.com/kuwait-en-fake/p',
                    'https://rullart.com.evil.example/p'):
            with self.subTest(url=url):
                self.assertEqual(markets.classify(dict(url=url),'kw')['market_scope'],'unknown')
