import asyncio
import threading
import time
import unittest
from findzia_discover_sources import MarketSources


def services():
    calls=[]
    def request(query, market, kind, timeout, cancel):
        calls.append((query,market['country'],kind))
        time.sleep(.02)
        return [{'link':f'https://merchant.com.{market["country"]}/products/{kind}',
                 'image':'https://images.example/a.jpg','title':'Headphones','source':'Merchant',
                 'quote':{'currency':'KWD','min':12.5,'max':12.5,'kind':'exact'}}]
    return {
        'calls':calls,'_local_fast_discovery_kinds':lambda cc,q:['serper_search:en','serper_images:en','serper_shopping:en','serper_search:ar'],
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


if __name__=='__main__':unittest.main()
