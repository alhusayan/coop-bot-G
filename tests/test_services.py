import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from findzia_services import install_services, listings, phone, PATH
from findzia_billing import CreditMiddleware


class Runtime:
    async def run(self, fn, *args, **kwargs):
        return fn(*args)
    def track(self, work):
        return asyncio.create_task(work)
    async def complete(self, member, rid, success):
        self.outcomes.append(success)
    def __init__(self):
        self.outcomes = []


class ServicesTests(unittest.TestCase):
    def client(self, data, blocked=False):
        app = FastAPI()
        provider = Mock(return_value=data)
        install_services(app, provider, {'kw': 'Kuwait', 'gb': 'United Kingdom'}, lambda: True)
        runtime = Runtime()
        def reserve(member, rid, path):
            if blocked:
                raise HTTPException(402, 'credits_exhausted')
            return rid
        credits = SimpleNamespace(enabled=True, runtime=runtime, check=lambda: None,
                                  accounts=SimpleNamespace(origins={'https://findzia.com'}),
                                  actor=lambda req: {'id': 'test-user'}, reserve=reserve)
        app.state.findzia_credits = credits
        app.add_middleware(CreditMiddleware, owner=app)
        return TestClient(app), provider, runtime

    def search(self, client, **payload):
        return client.post(PATH, json={'query': 'سباك', 'area': 'السالمية', 'country': 'KW', 'language': 'ar', **payload},
                           headers={'Origin': 'https://findzia.com', 'X-Findzia-Request-Id': 'test-services-request-123456789'})

    def test_real_listing_is_charged_and_kuwait_is_not_remapped(self):
        client, provider, runtime = self.client({'places': [{'title': 'Fixture business', 'address': 'Salmiya, Kuwait', 'phoneNumber': '2222 1234', 'cid': '123456789'}]})
        response = self.search(client)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['items'][0]['tel'], 'tel:+96522221234')
        self.assertEqual(runtime.outcomes, [True])
        args = provider.call_args.args
        self.assertEqual(args[0], 'places')
        self.assertEqual(args[1]['gl'], 'kw')
        self.assertIn('السالمية, Kuwait', args[1]['q'])

    def test_zero_balance_never_calls_provider(self):
        client, provider, runtime = self.client({'places': []}, blocked=True)
        response = self.search(client)
        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.json()['error'], 'credits_exhausted')
        provider.assert_not_called()

    def test_empty_and_failure_refund(self):
        for data, code in [({'places': []}, 200), (None, 503), ({'message': 'error'}, 503)]:
            client, _, runtime = self.client(data)
            self.assertEqual(self.search(client).status_code, code)
            self.assertEqual(runtime.outcomes, [False])

    def test_invalid_location_refunds_without_provider(self):
        client, provider, runtime = self.client({'places': []})
        self.assertEqual(self.search(client, area='').status_code, 400)
        provider.assert_not_called()
        self.assertEqual(runtime.outcomes, [False])

    def test_untrusted_fields_do_not_become_contact_links(self):
        self.assertEqual(phone('3950 24th St'), ('', ''))
        self.assertEqual(phone('javascript:alert(12345678)'), ('', ''))
        self.assertEqual(phone('+٩٦٥ ٢٢٢٢ ١٢٣٤'), ('+965 2222 1234', 'tel:+96522221234'))
        base = {'title': '<script>business</script>', 'address': 'Kuwait', 'website': 'javascript:alert(1)', 'phoneNumber': '123 Main Street', 'rating': 50}
        rows = listings({'places': [base, base, None, {'title': 'Missing address'}]})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['website'], '')
        self.assertEqual(rows[0]['tel'], '')
        self.assertIsNone(rows[0]['rating'])
        self.assertTrue(rows[0]['link'].startswith('https://www.google.com/maps/search/'))

    def test_retail_listing_is_not_presented_as_a_tradesperson(self):
        data = {'places': [
            {'title': 'Tools for sale', 'address': 'Salmiya', 'category': 'Hardware store'},
            {'title': 'Plumber fixture', 'address': 'Salmiya', 'category': 'Plumber'}]}
        self.assertEqual([r['title'] for r in listings(data)], ['Plumber fixture'])

    def test_international_contacts_keep_country_dialling_rules(self):
        for raw, country, expected in [
            ('020 7946 0018', 'GB', 'tel:+442079460018'),
            ('02 3661 8300', 'IT', 'tel:+390236618300'),
            ('٢٢٢٢ ١٢٣٤', 'KW', 'tel:+96522221234'),
            ('+44 20 7946 0018', 'KW', 'tel:+442079460018')]:
            with self.subTest(country=country, raw=raw):
                self.assertEqual(phone(raw, country)[1], expected)
        self.assertEqual(phone('2222 1234'), ('', ''))
        self.assertEqual(phone('2222 1234567890', 'KW'), ('', ''))


if __name__ == '__main__':
    unittest.main()
