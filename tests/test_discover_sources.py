import asyncio
import threading
import time
import unittest
from findzia_discover_sources import MarketSources
from findzia_market_evidence import MerchantMarkets


def services():
    calls=[]; markets=[]
    def request(query, market, kind, timeout, cancel):
        calls.append((query,market['country'],kind))
        markets.append(dict(market))
        time.sleep(.02)
        return [{'link':f'https://merchant.com.{market["country"]}/products/{kind}',
                 'image':'https://images.example/a.jpg','title':'Headphones','source':'Merchant',
                 'quote':{'currency':'KWD','min':12.5,'max':12.5,'kind':'exact'}}]
    return {
        'calls':calls,'markets':markets,'_local_fast_discovery_kinds':lambda cc,q:['serper_search:en','serper_images:en','serper_shopping:en','serper_search:ar'],
        '_local_primary_discovery_kinds':lambda cc:['broad_en'],
        '_local_discovery_request':request,'_web_market':lambda cc:{'country':cc},
        '_run_with_market':lambda market,fn:fn(), '_web_offer_image_candidates':lambda r:[r.get('image')],
        '_web_indexed_offer_quote':lambda r:r.get('quote'),'_web_collection_url':lambda url:'/collections/' in url,
        '_ui_plain_store_name':lambda name,url:name,
        'get_fx_rates':lambda currency:{'USD':3.25},'FX_CACHE_LOCK':threading.Lock(),
        'FX_CACHE':{'KWD':{'ts':time.time()}},'FAST_PROVIDERS':['serper'],
        'DEFAULT_GLOBAL_COUNTRIES':('us','cn'),
    }


class SourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_flight_and_ten_minute_web_cache_are_market_scoped(self):
        s=services();source=MarketSources(s)
        try:
            a,b=await asyncio.gather(source.search('headphones','KW','local'),source.search('headphones','KW','local'))
            self.assertEqual(len(s['calls']),2)
            self.assertTrue(all(m['_text_serper_passthrough'] for m in s['markets']))
            self.assertEqual({r['discovery_source'] for r in a['items']},{'web_search','shopping_search'})
            await source.search('headphones','KW','local')
            self.assertEqual(len(s['calls']),2)
            await source.search('headphones','JP','local')
            self.assertEqual(len(s['calls']),4)
            self.assertFalse(any(r['source']=='shopify_catalog' for _,rows in source.cache.values() for r in rows))
        finally:source.pool.shutdown(wait=True)

    async def test_old_fx_fallback_is_rejected(self):
        s=services();source=MarketSources(s)
        try:
            self.assertEqual((await source.fx('KWD'))['USD'],'3.25')
            s['FX_CACHE']['KWD']['ts']=time.time()-90000
            self.assertEqual(await source.fx('KWD'),{})
        finally:source.pool.shutdown(wait=True)

    async def test_only_existing_enabled_lanes_and_direct_priced_products(self):
        s=services();source=MarketSources(s)
        try:
            self.assertEqual([spec[2] for spec in source.specs('shoes','KW','local')],['serper_search:en','serper_shopping:en'])
            s['_shopping_gl_supported'] = lambda cc: cc == 'us'
            s['_fast_provider_supports_operators'] = lambda provider: provider == 'serper'
            self.assertEqual([spec[2] for spec in source.specs('shoes','KW','local')],['serper_search:en','serper_search:en:scoped'])
            self.assertEqual([spec[2] for spec in source.specs('shoes','US','local')],['serper_search:en','serper_shopping:en'])
            self.assertEqual(source.specs('shoes','US','global'),[('global','cn','global_fast')])
            rows=s['_local_discovery_request']('shoes',{'country':'kw'},'search',8,None)
            self.assertEqual(len(source.normalize(rows,'web_search')),1)
            self.assertEqual(source.normalize([dict(rows[0],in_stock=False)],'web_search'),[])
            self.assertEqual(source.normalize([dict(rows[0],link='https://merchant.com.kw/collections/shoes')],'web_search'),[])
            self.assertEqual(source.normalize([dict(rows[0],quote=None)],'web_search'),[])
        finally:source.pool.shutdown(wait=True)

    async def test_page_recovery_is_bounded_single_flight_and_never_reads_catalog(self):
        s=services(); calls=[]
        def snapshot(url,country):
            calls.append(url);time.sleep(.02)
            return dict(ok=True,is_product=True,url=url,title='Headphones',image='https://images.example/page.jpg',
                        price=18,currency='KWD',availability='InStock')
        s.update(_web_verified_page_snapshot=snapshot,
                 _findzia_hard_product_mismatch=lambda a,b:b=='Wrong product',
                 _web_quote_from_fields=lambda snap:dict(kind='exact',min=snap['price'],max=snap['price'],currency=snap['currency']))
        source=MarketSources(s,MerchantMarkets(['KW','US']))
        def row(host,source='web_search',**extra):
            return dict(url=f'https://{host}/products/one',title='Headphones',image='',money=None,discovery_source=source,**extra)
        rows=[row('one.com.kw'),row('two.com.kw'),row('three.com.kw'),row('foreign.us'),
              row('unknown.com'),row('catalog.com.kw','shopify_catalog')]
        try:
            a,b=await asyncio.gather(source.recover(rows,'KW','local'),source.recover(rows,'KW','local'))
            self.assertEqual(len(calls),2)
            self.assertEqual(sum(bool(r['money'] and r['image']) for r in a),2)
            self.assertEqual(a,b)
            await source.recover(rows,'KW','local');self.assertEqual(len(calls),2)
            self.assertFalse(any('catalog' in url or 'foreign' in url or 'unknown' in url for url in calls))
            self.assertTrue(all('merchant_country' not in r for r in rows))
        finally:
            source.pool.shutdown(wait=True);source.page_pool.shutdown(wait=True)

    async def test_page_data_cannot_cross_product_variant_or_replace_indexed_quote(self):
        s=services(); snap={}
        s.update(_web_verified_page_snapshot=lambda *a:snap,
                 _findzia_hard_product_mismatch=lambda a,b:b=='Wrong product',
                 _web_quote_from_fields=lambda v:dict(kind='range',min=10,max=15,currency='KWD'))
        source=MarketSources(s,MerchantMarkets(['KW']))
        row=dict(url='https://shop.com.kw/products/one?variant=1',title='Headphones',image='',money=None,
                 merchant_country='KW',discovery_source='web_search')
        base=dict(ok=True,is_product=True,url=row['url'],title='Headphones',image='https://images.example/p.jpg')
        try:
            for patch in (dict(url=row['url'].replace('variant=1','variant=2')),dict(url='https://shop.com.kw/collections/all'),
                          dict(title='Wrong product'),dict(page_fetch_status='blocked'),dict(is_product=False)):
                snap.clear();snap.update(base,**patch)
                self.assertEqual(source._page(row,'KW'),{})
            snap.clear();snap.update(base,availability='https://schema.org/OutOfStock')
            self.assertEqual(source._page(row,'KW'),{'unavailable':True})
            snap.clear();snap.update(base)
            recovered=source._page(row,'KW')
            self.assertEqual((recovered['money']['min'],recovered['money']['max']),('10','15'))
            self.assertEqual(recovered['image'],base['image'])
            self.assertNotIn('money',source._page(dict(row,money={'value':'2','currency':'KWD'}),'KW'))
        finally:
            source.pool.shutdown(wait=True);source.page_pool.shutdown(wait=True)


if __name__=='__main__':unittest.main()
