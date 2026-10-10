import asyncio
import unittest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from findzia_discover import Discovery, recipe, select_rows, install_discover, display_money
from findzia_market_evidence import MerchantMarkets


def row(i, store='merchant.com.kw', currency='KWD', value='12.500', source='shopify_catalog', **extra):
    return {'url': f'https://{store}/products/{i}', 'image': f'https://{store}/{i}.jpg',
            'title': f'Product {i}', 'store': store, 'money': {'value': value, 'currency': currency},
            'source': source, 'discovery_source': source, 'cacheable': source != 'shopify_catalog', **extra}


class FakeCatalog:
    countries = frozenset(('KW', 'JP', 'US'))

    def __init__(self):
        self.calls = []

    async def _search(self, query, country, lang, *, origin_country=''):
        self.calls.append((query, country, lang, origin_country))
        await asyncio.sleep(0)
        return {'status': 'ok', 'items': [row(query + str(i), f'store{i % 4}.com.kw') for i in range(12)]}


class FakeSources:
    def __init__(self, rows=()):
        self.rows = rows
        self.calls = []

    async def search(self, query, country, scope):
        self.calls.append((query, country, scope))
        return {'status': 'ok', 'items': self.rows}

    async def fx(self, currency):
        return {'USD': '3.25', 'KWD': '1', 'JPY': '500'}


def engine(catalog=None, sources=None, clock=lambda:1200):
    return Discovery(catalog or FakeCatalog(), {'KW':'Kuwait','JP':'Japan','US':'USA'},
        clock=clock, sources=sources, currencies={'KW':'KWD','JP':'JPY','US':'USD'},
        markets=MerchantMarkets(['KW','JP','US'], {'us':[('American','american.test')]}),
        cross_border_domains=['export.example'])


class DiscoveryTests(unittest.IsolatedAsyncioTestCase):
    def test_editions_are_stable_until_ten_minute_boundary(self):
        self.assertEqual(recipe(601), recipe(1199))
        a, b = recipe(1199), recipe(1200)
        self.assertNotEqual(a['edition'], b['edition'])
        self.assertTrue(all(x['query'] != y['query'] for x, y in zip(a['categories'], b['categories'])))

    def test_diversity_dedup_and_prices(self):
        rows = [row(i, f'web{i}.com.kw',source='web_search') for i in range(8)]
        rows += [row(i, f'catalog{i}.com.kw') for i in range(8)]
        for r in rows:
            r['display_money'] = display_money(r['money'], 'KWD', {})
        seen = set()
        chosen = select_rows(rows, 'seed', seen)
        self.assertEqual(len(chosen),8)
        self.assertEqual(sum(r['source']=='shopify_catalog' for r in chosen),4)
        self.assertEqual(sum(r['source']=='web_search' for r in chosen),4)
        self.assertTrue(set(r['url'] for r in chosen).isdisjoint(r['url'] for r in select_rows(rows, 'seed', seen)))
        duplicate=dict(rows[0],source='shopping_search',discovery_source='shopping_search')
        combined=select_rows([rows[0],duplicate],'seed',set())
        self.assertEqual(len(combined),1)
        self.assertEqual(combined[0]['discovery_sources'],['shopping_search','web_search'])

    def test_sparse_groups_fill_after_giving_other_merchants_priority(self):
        rows=[row(i,'web.com.kw',source='web_search') for i in range(12)]
        rows += [row(i,f'catalog{i}.com.kw') for i in range(4)]
        for r in rows:
            r['display_money']=display_money(r['money'],'KWD',{})
        chosen=select_rows(rows,'seed',set())
        self.assertEqual(len(chosen),8)
        self.assertEqual(sum(r['source']=='web_search' for r in chosen),4)
        self.assertEqual(len({r['store'] for r in chosen}),5)
        self.assertEqual(len(select_rows(rows[:12],'seed',set())),4)

    def test_currency_conversion_never_relabels_and_respects_precision(self):
        raw={'value':'32.50','currency':'USD'}
        converted=display_money(raw,'KWD',{'USD':'3.25'})
        self.assertEqual(converted['value'],'10.000')
        self.assertTrue(converted['converted'])
        self.assertEqual(raw['currency'],'USD')
        self.assertEqual(display_money({'value':'10.5','currency':'JPY'},'JPY',{})['value'],'11')
        self.assertIsNone(display_money(raw,'KWD',{}))
        for bad in ('NaN','Infinity','0','-1'):
            self.assertIsNone(display_money(raw,'KWD',{'USD':bad}))
        money={'value':'32.5','currency':'USD','kind':'range','min':'32.5','max':'65'}
        shown=display_money(money,'KWD',{'USD':'3.25'})
        self.assertEqual((shown['min'],shown['max']),('10.000','20.000'))

    async def test_market_and_currency_are_independent_and_scopes_do_not_mix(self):
        class Catalog(FakeCatalog):
            async def _search(self,*a,**k):return {'status':'ok','items':[]}
        sources=FakeSources([
            row('local','kuwait.com.kw',currency='USD',value='32.5',source='web_search'),
            row('foreign','american.test',currency='KWD',source='shopping_search'),
            row('unknown','mystery.test',currency='KWD',source='web_search'),
            row('export','export.example',source='web_search'),
        ])
        d=engine(Catalog(),sources)
        local=await d.feed('KW','en','shoes')
        rows=local['groups'][0]['items']
        self.assertEqual([r['title'] for r in rows],['Product local'])
        self.assertEqual(rows[0]['display_money']['value'],'10.000')
        self.assertEqual(rows[0]['market_scope'],'local')
        international=await d.feed('KW','en','shoes','global')
        rows=international['groups'][0]['items']
        self.assertEqual({r['title'] for r in rows},{'Product foreign','Product export'})
        self.assertTrue(all(r['display_money']['currency']=='KWD' for r in rows))
        export=next(r for r in rows if r['title']=='Product export')
        self.assertIsNone(export['merchant_country'])
        self.assertEqual(international['scope'],'global')

    async def test_every_visit_keeps_catalog_live_and_filters_by_origin(self):
        catalog=FakeCatalog();discovery=engine(catalog)
        first=await discovery.feed('KW','en');second=await discovery.feed('KW','en')
        self.assertEqual(len(catalog.calls),12)
        self.assertTrue(all(call[3]=='KW' for call in catalog.calls))
        self.assertEqual(first['edition'],second['edition'])
        self.assertEqual(len(first['groups']),6)
        urls=[r['url'] for g in first['groups'] for r in g['items']]
        self.assertEqual(len(urls),len(set(urls)))
        self.assertFalse(first['cacheable']);self.assertEqual(discovery.inflight,0)
        await discovery.feed('KW','en','shoes','global')
        self.assertEqual(catalog.calls[-1][3],'')

    async def test_no_fx_never_shows_foreign_currency(self):
        class Catalog(FakeCatalog):
            async def _search(self,*a,**k):return {'status':'ok','items':[row('usd',currency='USD')]}
        result=await engine(Catalog()).feed('KW','en','shoes')
        self.assertEqual(result['groups'][0]['items'],[])
        self.assertEqual(result['excluded']['currency'],1)

    async def test_one_category_failure_keeps_other_collections(self):
        catalog=FakeCatalog();search=catalog._search
        async def fail(query,country,lang,**kwargs):
            if query==recipe(1200)['categories'][0]['query']:raise ValueError('provider unavailable')
            return await search(query,country,lang,**kwargs)
        catalog._search=fail
        feed=await engine(catalog).feed('KW','ar')
        self.assertEqual(sum(bool(g['items']) for g in feed['groups']),5)

    async def test_routes_validate_country_scope_no_store_and_rate_limit(self):
        app=FastAPI();discovery=install_discover(app,{'kw':'Kuwait','jp':'Japan'})
        discovery.catalog=FakeCatalog();discovery.currencies={'KW':'KWD','JP':'JPY'}
        async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
            config=await client.get('/api/discover/config')
            self.assertEqual(config.json()['currencies']['JP'],'JPY')
            self.assertEqual((await client.get('/api/discover/trial?country=ZZ')).status_code,400)
            self.assertEqual((await client.get('/api/discover/trial?scope=all')).status_code,400)
            for i in range(8):
                response=await client.get('/api/discover/trial?country=JP&q=headphones')
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json()['country'],'JP')
                self.assertEqual(response.json()['scope'],'local')
                self.assertIn('no-store',response.headers['cache-control'])
            self.assertEqual(len(discovery.catalog.calls),8)
            self.assertEqual((await client.get('/api/discover/trial')).status_code,429)

    async def test_cancellation_releases_admission_and_tasks(self):
        catalog=FakeCatalog();stopped=[]
        async def slow(*args,**kwargs):
            try:await asyncio.sleep(60)
            finally:stopped.append(True)
        catalog._search=slow;discovery=engine(catalog)
        task=asyncio.create_task(discovery.feed('KW','en'));await asyncio.sleep(.01);task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(discovery.inflight,0);self.assertEqual(len(stopped),6)


if __name__=='__main__':unittest.main()
