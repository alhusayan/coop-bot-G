"""Exercise the live UCP boundary, signed choice integration and failure paths."""
import asyncio
import base64
import copy
import json
import os
import time
import unittest
from unittest.mock import Mock, patch

import httpx
from fastapi.responses import StreamingResponse

from experiment.findzia_shopify_catalog import event_line, normalize_products
from findzia_one_catalog import OneCatalog, one_products
from findzia_choice import ChoiceEngine
from tests.test_choice import SIGN, row, services, ai_response


def product():
    return dict(id='gid://shopify/p/one', title='Sony WH-1000XM5 headphones',
                url='https://merchant.example/products/sony-wh1000xm5',
                media=[dict(type='image', url='https://cdn.shopify.com/sony.jpg')],
                variants=[dict(id='gid://shopify/ProductVariant/123', title='Black',
                    options=[dict(name='Color', label='Black')], price=dict(amount=25000, currency='KWD'),
                    availability=dict(available=True), requires=dict(shipping=True),
                    seller=dict(name='Merchant', id='gid://shopify/Shop/1'))])


class CatalogTests(unittest.IsolatedAsyncioTestCase):
    def client(self, handler):
        return OneCatalog(['kw', 'us', 'gb'], SIGN['_fz_evaluation_token'], transport=httpx.MockTransport(handler))

    def test_variant_prices_links_and_minor_units_stay_together(self):
        p = product()
        other = copy.deepcopy(p['variants'][0])
        other.update(id='gid://shopify/ProductVariant/456', title='Silver',
                     options=[dict(name='Color', label='Silver')], price=dict(amount=22000, currency='KWD'))
        p['variants'].append(other)
        rows = one_products([p], 'KW', origin_country='KW')
        self.assertEqual([r['price_amount'] for r in rows], [25, 22])
        self.assertTrue(rows[0]['url'].endswith('variant=123'))
        self.assertTrue(rows[1]['url'].endswith('variant=456'))
        self.assertIn('Silver', rows[1]['title'])
        self.assertEqual(len(normalize_products([p], 'KW')), 1)  # /test contract unchanged
        p['variants'][0]['price'] = dict(amount=1250, currency='JPY')
        self.assertEqual(one_products([p], 'KW')[0]['price_amount'], 1250)

    def test_unavailable_range_subscription_and_ambiguous_variant_rejected(self):
        for change in [dict(availability=dict(available=False)), dict(price=dict(min=2,max=10)),
                       dict(requires=dict(shipping=True, selling_plan=True)), dict(id='unknown')]:
            p = product();p['variants'][0].update(change)
            self.assertEqual(one_products([p], 'KW'), [])

    async def test_signed_origin_and_request_filters_no_destination_guess(self):
        requests = []
        def handler(request):
            body = json.loads(request.content);catalog=body['params']['arguments']['catalog'];requests.append(catalog)
            p = product()
            origin = catalog['filters'].get('ships_from', [{}])[0].get('country', '')
            p['url'] = 'https://' + (origin.lower() or 'unknown') + '.example/products/sony-wh1000xm5'
            return httpx.Response(200, json=dict(result=dict(structuredContent=dict(products=[p]))))
        result = await self.client(handler).search('Sony WH-1000XM5', 'kw')
        self.assertEqual({r['market_scope'] for r in result['items']}, {'local','global'})
        self.assertEqual(len(result['items']),2)
        for r in result['items']:
            signed = SIGN['_fz_evaluation_row'](r['evaluation_token'])
            self.assertEqual(signed['source'],'shopify_catalog')
            self.assertIs(signed['cacheable'],False)
            self.assertEqual(signed['market_country'],r['market_country'])
        self.assertTrue(all(c['filters']['ships_to']['country']=='KW' for c in requests))
        self.assertEqual({c['filters'].get('ships_from',[{}])[0].get('country') for c in requests}, {'KW','US',None})

    async def test_digital_delivery_does_not_prove_local_origin(self):
        p=product();p['variants'][0]['requires']['shipping']=False
        c=self.client(lambda request:httpx.Response(200,json=dict(result=dict(structuredContent=dict(products=[p])))))
        self.assertEqual((await c.search('Sony', 'kw'))['items'],[])

    async def test_first_primary_event_immediate_catalog_before_terminal_and_cancellation(self):
        started=asyncio.Event();release=asyncio.Event()
        c=self.client(lambda request:None)
        async def search(*args,**kwargs):
            started.set();await release.wait()
            return dict(status='ok',items=[dict(url='https://merchant.example/products/a')])
        c.search=search
        primary=dict(event='result',item=dict(url='https://native.example/item',country='kw',evaluation_token='original'))
        async def source():
            yield event_line(primary);yield event_line(dict(event='done',count=1))
        stream=c.supplement(source(),'Sony','kw','en')
        first=await asyncio.wait_for(anext(stream),.2)
        self.assertEqual(json.loads(first),primary)
        await started.wait();release.set()
        rest=[json.loads(line) async for line in stream]
        self.assertEqual([x['event'] for x in rest],['catalog','done'])
        self.assertEqual(rest[-1]['count'],2)

    async def test_slow_lane_bounded_and_cancelled_without_losing_ready_lane(self):
        c=self.client(lambda request:None);c.deadline=.03;cancelled=[]
        async def search(*args,origin_country='',**kwargs):
            if origin_country=='KW':
                return dict(status='ok',items=one_products([product()],'KW',origin_country='KW'))
            try: await asyncio.Event().wait()
            finally: cancelled.append(origin_country)
        c._search=search
        result=await asyncio.wait_for(c.search('Sony','kw'),.3)
        self.assertEqual(len(result['items']),1)
        self.assertEqual(set(cancelled),{'','US'})

    async def test_public_flag_off_and_error_responses_do_not_call_catalog(self):
        c=self.client(lambda request:None)
        for opt,mode,status in [(False,'true',200),(True,'false',200),(True,'true',429)]:
            response=StreamingResponse(iter([]),status_code=status);original=response.body_iterator
            with patch.dict(os.environ,FINDZIA_SHOPIFY_CATALOG_ENABLED=mode):
                c.wrap_response(response,opted_in=opt,query='Sony',country='kw',lang='en',preview=True)
            self.assertIs(response.body_iterator,original)

    async def test_rate_limit_and_error_leave_primary_stream_usable(self):
        c=self.client(lambda request:httpx.Response(429))
        async def source():
            yield event_line(dict(event='result',item=dict(url='https://native.example/p')))
            yield event_line(dict(event='done',count=1))
        events=[json.loads(e) async for e in c.supplement(source(),'Sony','kw','en')]
        self.assertEqual(events[-1]['count'],1)
        self.assertEqual(next(e for e in events if e['event']=='catalog')['items'],[])
        self.assertGreater(c.retry_after,time.monotonic())


class CatalogChoiceTests(unittest.TestCase):
    def setUp(self):
        self.s=services();self.s['_refine_ai'].side_effect=ai_response
        self.engine=ChoiceEngine(self.s)
        self.native=row('WH-1000XM5',40);self.native.update(title='Sony WH-1000XM5 headphones Black',image='https://native.example/photo.jpg')
        self.catalog=one_products([product()],'KW',origin_country='KW')[0]
        self.catalog.update(market_country='kw',country='kw',card_model='WH-1000XM5')

    def tearDown(self):
        for pool in (self.engine.pool,self.engine.media_pool,self.engine.visual_pool,self.engine.price_pool):pool.shutdown(wait=True)

    def prepare(self,rows,kind='text'):
        tokens=[SIGN['_fz_evaluation_token'](r) for r in rows]
        payload=dict(query='Sony WH-1000XM5 headphones',country='kw',lang='en',kind=kind,offer_tokens=tokens)
        if kind=='image':payload.update(image_base64=base64.b64encode(b'reference').decode(),
            offer_images=[dict(token=t,image=r['image']) for t,r in zip(tokens,rows)])
        return self.engine.prepare(payload)

    def test_cheaper_exact_catalog_variant_enters_same_decision(self):
        result=self.engine.choose(*self.prepare([self.native,self.catalog]))
        self.assertEqual(result['url'],self.catalog['url']);self.assertEqual(result['money']['amount'],25)

    def test_wrong_model_and_unknown_market_do_not_enter_choice(self):
        for change in [dict(title='Sony WH-1000XM4',card_model='WH-1000XM4',url='https://shop.example/products/wh1000xm4'),
                       dict(market_scope='unknown',market_country='')]:
            self.assertEqual(self.prepare([dict(self.catalog,**change)])[1],[])

    def test_different_color_cannot_replace_selected_variant_for_price(self):
        catalog=dict(self.catalog,title='Sony WH-1000XM5 headphones Silver',variant_title='Silver',key_specs=[dict(key='Color',value='Silver')])
        result=self.engine.choose(*self.prepare([self.native,catalog]))
        self.assertEqual(result['url'],self.native['url'])

    def test_photo_requires_native_pixel_anchor_never_downloads_catalog_image(self):
        fetch=self.s['_web_visual_candidate_inline']=Mock(wraps=self.s['_web_visual_candidate_inline'])
        result=self.engine.choose(*self.prepare([self.native,self.catalog],'image'))
        self.assertEqual(result['url'],self.catalog['url'])
        self.assertEqual(result['identity_basis'],'verified_model');self.assertFalse(result['visual_verified'])
        self.assertEqual([c.args[0]['image'] for c in fetch.call_args_list],[self.native['image']])
        self.assertEqual(self.engine.choose(*self.prepare([self.catalog],'image'))['status'],'no_match')

    def test_catalog_choice_is_not_retained_in_result_or_price_cache(self):
        context,candidates=self.prepare([self.catalog])
        _,future=self.engine.submit(context,candidates);self.assertEqual(future.result(timeout=2)['status'],'selected')
        self.assertEqual(self.engine.cache,{});self.assertEqual(self.engine.price_cache,{})
        self.assertEqual(self.engine.visual_cache,{})

    def test_missing_catalog_price_is_not_scraped(self):
        self.s['_web_choice_price_recovery']=Mock()
        self.assertEqual(self.prepare([dict(self.catalog,price_unavailable=True)])[1],[])
        self.s['_web_choice_price_recovery'].assert_not_called()
