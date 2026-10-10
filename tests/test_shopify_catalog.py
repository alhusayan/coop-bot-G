import ast
import asyncio
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from findzia_shopify_catalog import ShopifyCatalog, agent_profile, event_line, install_catalog, money, normalize_products


def product(currency='KWD', amount=12345, url='https://merchant.example/products/one', **extra):
    return dict(id='gid://shopify/p/1', title='<b>Sample product</b>',
                media=[dict(type='image', url='https://cdn.example/one.jpg')],
                variants=[dict(id='gid://shopify/ProductVariant/1', url=url,
                    price=dict(amount=amount, currency=currency), availability=dict(available=True),
                    seller=dict(name='Store'), requires=dict(shipping=True))], **extra)


def reply(products=None):
    return dict(jsonrpc='2.0', id=1, result=dict(structuredContent=dict(
        status='success', products=[product()] if products is None else products)))


def countries():
    tree = ast.parse(Path('main.py').read_text())
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'COUNTRY_META' for t in node.targets):
            values.update(ast.literal_eval(node.value))
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            f = node.value.func
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == 'COUNTRY_META' and f.attr == 'update':
                values.update(ast.literal_eval(node.value.args[0]))
    return values


class NormalizeTests(unittest.TestCase):
    def test_minor_units(self):
        for code, amount, want in [('KWD', 12345, '12.345'), ('BHD', 1000, '1.000'),
                                   ('OMR', 500, '0.500'), ('JPY', 1200, '1200'),
                                   ('KRW', 2500, '2500'), ('USD', 1999, '19.99'),
                                   ('CLF', 12345, '1.2345')]:
            self.assertEqual(money(dict(currency=code, amount=amount))['value'], want)
        for amount in [-1, True, 1.5, '1234', None]:
            self.assertIsNone(money(dict(currency='USD', amount=amount)))

    def test_shipping_never_establishes_merchant_origin(self):
        row = normalize_products([product('USD', 1299)], 'kw')[0]
        self.assertEqual(row['destination_country'], 'KW')
        self.assertIsNone(row['merchant_country'])
        self.assertEqual(row['market_scope'], 'unknown')
        self.assertFalse(row['shipping_cost_verified'])
        self.assertFalse(row['cacheable'])
        self.assertEqual(row['image'], 'https://cdn.example/one.jpg')
        self.assertEqual(row['title'], 'Sample product')

    def test_invalid_unavailable_and_duplicate_products(self):
        bad = product(); bad['variants'][0]['availability']['available'] = False
        self.assertEqual(normalize_products([bad], 'kw'), [])
        self.assertEqual(normalize_products([product(url='javascript:alert(1)')], 'kw'), [])
        self.assertEqual(normalize_products([product(url='https://user:pass@store.example/p')], 'kw'), [])
        self.assertEqual(len(normalize_products([product(), product()], 'kw')), 1)
        self.assertEqual(normalize_products([product()], 'jp', True)[0]['match_type'], 'visual_similarity')

    def test_profile_only_advertises_catalog(self):
        app = FastAPI(); install_catalog(app, ['kw'])
        with TestClient(app) as client:
            response = client.get('/.well-known/ucp')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), agent_profile())
        self.assertEqual(response.json()['ucp']['payment_handlers'], {})
        self.assertNotIn('dev.ucp.shopping.checkout', response.json()['ucp']['capabilities'])


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_registered_country_uses_exact_destination(self):
        requests = []
        def transport(request):
            requests.append(json.loads(request.content)['params']['arguments']['catalog'])
            return httpx.Response(200, json=reply())
        all_countries = countries()
        self.assertGreater(len(all_countries), 200)
        catalog = ShopifyCatalog(all_countries, transport=httpx.MockTransport(transport))
        for country in all_countries:
            result = await catalog._search('عطر عود', country, 'ar')
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(requests[-1]['filters']['ships_to'], dict(country=country.upper()))
            self.assertEqual(requests[-1]['context']['address_country'], country.upper())
        self.assertEqual((await catalog._search('test', 'ZZ'))['status'], 'unsupported_country')
        self.assertEqual(len(requests), len(all_countries))

    async def test_image_payload_is_forwarded_without_remote_download(self):
        seen = []
        def transport(request):
            seen.append(json.loads(request.content))
            self.assertEqual(str(request.url), 'https://catalog.shopify.com/api/ucp/mcp')
            return httpx.Response(200, json=reply())
        catalog = ShopifyCatalog(['jp'], transport=httpx.MockTransport(transport))
        result = await catalog._search('', 'jp', image_b64='aW1hZ2U=', mime='image/png')
        self.assertEqual(result['items'][0]['match_type'], 'visual_similarity')
        args = seen[0]['params']['arguments']['catalog']
        self.assertNotIn('query', args)
        self.assertEqual(args['like'][0]['image'], dict(content_type='image/png', data='aW1hZ2U='))

    async def test_repeat_search_is_fresh_and_rate_limit_has_no_retry(self):
        calls = []
        def transport(request):
            calls.append(request)
            return httpx.Response(200 if len(calls) < 3 else 429, json=reply())
        catalog = ShopifyCatalog(['kw'], transport=httpx.MockTransport(transport))
        await catalog._search('same', 'kw'); await catalog._search('same', 'kw')
        self.assertEqual(len(calls), 2)
        self.assertEqual((await catalog._search('same', 'kw'))['status'], 'rate_limited')
        self.assertEqual((await catalog._search('same', 'kw'))['status'], 'busy')
        self.assertEqual(len(calls), 3)
        self.assertEqual(catalog.inflight, 0)

    async def test_failure_and_timeout_are_nonfatal(self):
        for status in (401, 500, 503):
            catalog = ShopifyCatalog(['kw'], transport=httpx.MockTransport(lambda r: httpx.Response(status)))
            self.assertEqual((await catalog._search('test', 'kw'))['items'], [])
        def timeout(request):
            raise httpx.ReadTimeout('slow', request=request)
        catalog = ShopifyCatalog(['kw'], transport=httpx.MockTransport(timeout))
        self.assertEqual((await catalog._search('test', 'kw'))['status'], 'timeout')

    async def test_provider_errors_and_ignored_filters(self):
        for body in [dict(error=dict(code=1)), dict(result=dict(isError=True)), {'unexpected': []}]:
            catalog = ShopifyCatalog(['kw'], transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body)))
            self.assertEqual((await catalog._search('test', 'kw'))['items'], [])
        body = reply(); body['result']['structuredContent']['messages'] = [dict(code='unsupported_filter')]
        catalog = ShopifyCatalog(['kw'], transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body)))
        self.assertEqual((await catalog._search('test', 'kw'))['status'], 'unsupported_filter')


class StreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_primary_card_does_not_wait_for_catalog(self):
        release = asyncio.Event()
        catalog = ShopifyCatalog(['kw'])
        async def search(*args, **kwargs):
            await release.wait()
            return dict(status='ok', items=normalize_products([product()], 'kw'))
        catalog.search = search
        async def source():
            yield event_line(dict(event='result', item=dict(url='https://local.example/p', title='Local')))
            yield event_line(dict(event='done', count=1))
        stream = catalog.supplement(source(), 'test', 'kw', 'ar')
        first = await asyncio.wait_for(anext(stream), .2)
        self.assertEqual(json.loads(first)['event'], 'result')
        release.set()
        rest = [json.loads(chunk) async for chunk in stream]
        self.assertEqual([e['event'] for e in rest], ['catalog', 'done'])
        self.assertEqual(rest[-1]['count'], 2)

    async def test_cancel_cancels_provider_and_source(self):
        started, cancelled, source_closed = asyncio.Event(), asyncio.Event(), asyncio.Event()
        catalog = ShopifyCatalog(['kw'])
        async def search(*args, **kwargs):
            started.set()
            try: await asyncio.Event().wait()
            finally: cancelled.set()
        catalog.search = search
        async def source():
            try:
                yield event_line(dict(event='start'))
                await asyncio.Event().wait()
            finally: source_closed.set()
        stream = catalog.supplement(source(), 'test', 'kw', 'ar')
        await anext(stream); await started.wait(); await stream.aclose()
        self.assertTrue(cancelled.is_set()); self.assertTrue(source_closed.is_set())

    async def test_duplicate_not_emitted_and_empty_source_settles_once(self):
        from findzia_billing import ResultEvidence
        catalog = ShopifyCatalog(['kw'])
        async def search(*args, **kwargs):
            await asyncio.sleep(.01)
            return dict(status='ok', items=normalize_products([product()], 'kw'))
        catalog.search = search
        for duplicate in (True, False):
            async def source():
                if duplicate: yield event_line(dict(event='result', item=dict(url=product()['variants'][0]['url'], title='Primary')))
                yield event_line(dict(event='done', count=int(duplicate)))
            events = [json.loads(c) async for c in catalog.supplement(source(), 'test', 'kw', 'ar')]
            self.assertEqual(len(next(e for e in events if e['event'] == 'catalog')['items']), 1)
            self.assertEqual(sum(e['event'] == 'done' for e in events), 1)
            evidence = ResultEvidence()
            for event in events: evidence.event(event)
            self.assertEqual(len(evidence.rows), 1)

    async def test_disabled_old_clients_and_preview_are_isolated(self):
        catalog = ShopifyCatalog(['kw'])
        async def source(): yield event_line(dict(event='done'))
        for mode, opted, preview, active in [('false', True, True, False), ('true', False, False, False),
                                            ('preview', True, False, False), ('preview', True, True, True),
                                            ('true', True, False, True)]:
            response = StreamingResponse(source())
            original = response.body_iterator
            with patch.dict(os.environ, FINDZIA_SHOPIFY_CATALOG_ENABLED=mode):
                catalog.wrap_response(response, opted_in=opted, preview=preview, query='q', country='kw', lang='ar')
            self.assertEqual(response.body_iterator is not original, active)
            if active: self.assertEqual(response.headers['cache-control'], 'no-store, no-transform')

    async def test_recommendations_keep_terminal_done_without_catalog(self):
        catalog = ShopifyCatalog(['kw'])
        async def search(*args, **kwargs):
            await asyncio.sleep(5)
            return dict(status='ok', items=[])
        catalog.search = search
        async def source():
            yield event_line(dict(event='recommendations', data={}))
            yield event_line(dict(event='done'))
        events = [json.loads(c) async for c in catalog.supplement(source(), 'q', 'kw', 'ar')]
        self.assertEqual([e['event'] for e in events], ['recommendations', 'done'])


if __name__ == '__main__': unittest.main()
