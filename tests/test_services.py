import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

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
    def client(self, data, blocked=False, **options):
        app = FastAPI()
        provider = Mock(return_value=data)
        install_services(app, provider, {'kw': 'Kuwait', 'gb': 'United Kingdom'}, lambda: True, **options)
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
            {'title': 'أدوات للبيع', 'address': 'السالمية', 'category': 'متجر خردوات'},
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


    def image(self):
        import base64, io
        from PIL import Image
        out = io.BytesIO()
        Image.new('RGB', (40, 30), 'green').save(out, format='JPEG', exif=b'Exif\x00\x00private-location')
        return base64.b64encode(out.getvalue()).decode()

    def test_photo_recognition_searches_detected_service_with_one_charge(self):
        vision = Mock(return_value={'status': 'clear', 'options': [{'en': 'Plumber', 'ar': 'سباك'}]})
        client, provider, runtime = self.client({'places': [{'title': 'Plumber fixture', 'address': 'Salmiya'}]}, vision=vision)
        response = self.search(client, query='', image=self.image())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['query'], 'سباك')
        self.assertTrue(response.json()['items'])
        self.assertEqual(runtime.outcomes, [True])
        self.assertEqual(vision.call_count, 1)
        self.assertIn('سباك', provider.call_args.args[1]['q'])
        import base64
        self.assertNotIn(b'private-location', base64.b64decode(vision.call_args.args[0]))

    def test_photo_ambiguity_or_unknown_refunds_without_search(self):
        for status, options in [('choose', [{'en': 'Plumber', 'ar': 'سباك'}, {'en': 'Cleaning', 'ar': 'تنظيف'}]), ('unknown', [])]:
            vision = Mock(return_value={'status': status, 'options': options})
            client, provider, runtime = self.client({'places': []}, vision=vision)
            response = self.search(client, query='', image=self.image())
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['photo']['status'], status)
            self.assertEqual(response.json()['items'], [])
            provider.assert_not_called()
            self.assertEqual(runtime.outcomes, [False])

    def test_photo_without_credit_never_calls_vision(self):
        vision = Mock()
        client, provider, runtime = self.client({'places': []}, blocked=True, vision=vision)
        self.assertEqual(self.search(client, query='', image=self.image()).status_code, 402)
        vision.assert_not_called()
        provider.assert_not_called()

    def test_invalid_photos_and_vision_failure_refund(self):
        for image in ['', 'not-base64', 'YQ==', 'a' * 2_050_001]:
            vision = Mock()
            client, provider, runtime = self.client({'places': []}, vision=vision)
            self.assertIn(self.search(client, query='', image=image).status_code, (400, 413))
            vision.assert_not_called()
            provider.assert_not_called()
            self.assertEqual(runtime.outcomes, [False])
        client, provider, runtime = self.client({'places': []}, vision=Mock(side_effect=RuntimeError()))
        self.assertEqual(self.search(client, query='', image=self.image()).status_code, 503)
        self.assertEqual(runtime.outcomes, [False])

    def test_only_explicit_published_whatsapp_links_are_returned(self):
        from findzia_services import whatsapp_link, published_whatsapp
        self.assertEqual(whatsapp_link('https://api.whatsapp.com/send?phone=96555551234&text=Hi'), 'https://wa.me/96555551234')
        for value in ['tel:+96555551234', 'https://wa.me.evil.com/96555551234', 'https://wa.me@evil.com/96555551234', 'https://wa.me:8080/96555551234', 'https://wa.me/invalid', 'http://wa.me/96555551234']:
            self.assertEqual(whatsapp_link(value), '')
        response = Mock(status_code=200, headers={'content-type': 'text/html'}, _findzia_session=None)
        response.iter_content.return_value = [b'<a href="tel:+96555551234">Call</a>']
        safe = Mock(return_value=response)
        self.assertEqual(published_whatsapp('https://example.com', safe), '')
        response.iter_content.return_value = [b'<a href="https://wa.me/96555551234">WhatsApp</a>']
        client, provider, runtime = self.client({'places': [{'title': 'Fixture', 'address': 'Salmiya', 'website': 'https://example.com'}]}, safe_get=safe)
        row = self.search(client).json()['items'][0]
        self.assertEqual(row['whatsapp'], 'https://wa.me/96555551234')
        self.assertEqual(row['whatsapp_source'], row['website'])
        self.assertTrue(response.close.called)
        safe.side_effect = ValueError('unsafe_outbound_url')
        self.assertEqual(published_whatsapp('http://127.0.0.1', safe), '')

    def test_vision_request_uses_normalized_image_and_structured_service_response(self):
        from findzia_service_photo import identify_service, photo_suggestions
        import json
        result = {'status': 'choose', 'options': [{'en': 'AC repair', 'ar': 'تصليح تكييف'}]}
        response = Mock()
        response.json.return_value = {'candidates': [{'content': {'parts': [{'text': json.dumps(result)}]}}]}
        with patch('findzia_service_photo.requests.post', return_value=response) as post:
            self.assertEqual(identify_service(self.image(), key='test-only', model='gemini-2.5-flash'), result)
            payload = post.call_args.kwargs['json']
            self.assertEqual(payload['contents'][0]['parts'][0]['inlineData']['mimeType'], 'image/jpeg')
            self.assertEqual(payload['generationConfig']['responseMimeType'], 'application/json')
            self.assertNotIn('tools', payload)
        with self.assertRaises(ValueError):
            photo_suggestions({'status': 'clear', 'options': None})
        self.assertEqual(photo_suggestions({'status': 'clear', 'options': [{'en': '<script>', 'ar': 'سباك'}]})['status'], 'unknown')


if __name__ == '__main__':
    unittest.main()
