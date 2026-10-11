"""User regressions: Series 7000 vs a 9000/category offer, using real guards."""
import html
import ipaddress
import unittest
import unicodedata
from functools import lru_cache
from unittest.mock import Mock
from bs4 import BeautifulSoup

from findzia_choice import ChoiceEngine
from findzia_choice_identity import model_evidence, requirements
from tests.test_choice import SIGN, row, services
from verification.test_audit_prices import scope

QUERY = 'Philips Lumea Series 7000'
CATEGORY = 'https://www.noon.com/kuwait-en/beauty/personal-care-16343/shaving-and-hair-removal/womens-31112/ipl-laser-hair-removal/philips/'
XCITE = 'https://www.xcite.com/philips-lumea-series-7000-hair-free-smooth-skin-with-satin-compact-pen-trimmer-corded-2-attachement-bri921-60-white/p'


class IdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real = scope(['_findzia_hard_product_mismatch', '_web_collection_products', '_web_collection_url', '_web_indexed_offer_quote'],
                         dict(lru_cache=lru_cache, unicodedata=unicodedata, html=html,
                              BeautifulSoup=BeautifulSoup, ipaddress=ipaddress,
                              _web_image_is_generic=lambda *a:False))

    def setUp(self):
        self.s = services()
        self.s.update({k:self.real[k] for k in ('_findzia_hard_product_mismatch', '_web_collection_url')})
        self.engine = ChoiceEngine(self.s)

    def tearDown(self):
        for pool in (self.engine.pool, self.engine.media_pool, self.engine.visual_pool, self.engine.price_pool):
            pool.shutdown(wait=True)

    def pick(self, rows, query=QUERY):
        payload = dict(query=query, country='kw', lang='en', offer_tokens=[SIGN['_fz_evaluation_token'](r) for r in rows])
        return self.engine.choose(*self.engine.prepare(payload))

    def product(self, title=QUERY, **changes):
        r = row('BRI921/60', 79.56)
        r.update(title=title, url=XCITE, **changes)
        return r

    def test_category_price_cannot_win_or_be_recovered(self):
        category = self.product('Philips IPL & Laser Hair Removal Kuwait')
        category['url'] = CATEGORY
        self.s['_web_choice_price_recovery'] = Mock()
        self.assertEqual(self.pick([category])['status'], 'no_match')
        self.s['_web_choice_price_recovery'].assert_not_called()

    def test_generic_title_or_description_only_model_is_not_proof(self):
        for changes in ({}, {'description':'Also see Philips Lumea Series 7000'}):
            r = self.product('Philips IPL Hair Removal', **changes)
            r['url'] = 'https://shop.example/product/ipl'
            self.assertEqual(self.pick([r])['status'], 'no_match')

    def test_correct_xcite_smooth_skin_title_is_not_an_accessory(self):
        r = self.product(QUERY + ' Hair-Free Smooth Skin with Satin Compact Pen Trimmer BRI921/60')
        self.assertFalse(self.real['_findzia_hard_product_mismatch'](QUERY, r['title']))
        self.assertEqual(self.pick([r])['url'], XCITE)

    def test_category_and_cheaper_9000_never_replace_7000(self):
        correct = self.product()
        wrong = self.product('Philips Lumea 9000 Series BRI958/60')
        wrong.update(url='https://shop.example/product/9000', price_amount=50, card_model='BRI958/60')
        self.assertEqual(self.pick([wrong, correct])['url'], XCITE)

    def test_series_word_order_arabic_and_sku_punctuation(self):
        for query, title in [(QUERY, 'Philips Lumea 7000 Series'),
                             ('Philips Lumea سلسلة ٧٠٠٠', 'Philips Lumea Series 7000'),
                             ('Philips BRI921/60', 'Philips BRI921-60'),
                             ('Sony WH-1000XM5', 'Sony WH1000XM5')]:
            with self.subTest(query=query):
                self.assertTrue(model_evidence(query, {'title':title, 'url':'https://shop.example/product/one'}))

    def test_wrong_model_in_title_cannot_hide_behind_slug(self):
        r = self.product('Philips Lumea Series 9000 BRI958/60')
        self.assertFalse(model_evidence(QUERY, r))
        r['title'] = 'Philips BRI921/00'
        r['card_model'] = 'BRI921/00'
        self.assertFalse(model_evidence('Philips BRI921/60', r))

    def test_specs_and_budgets_are_not_models(self):
        for query in ('chair', 'ثلاجة 500 لتر', 'generator 7500 watts', 'مولد ٧٥٠٠ واط', 'chair 100 KWD', 'phone 256GB'):
            with self.subTest(query=query): self.assertEqual(requirements(query), [])

    def test_named_phone_variant_cannot_be_substituted(self):
        for query, title, expected in [('Samsung S24', 'Samsung S24 Ultra', False),
                                       ('iPhone 15 Pro', 'iPhone 15 Pro Max', False),
                                       ('iPhone 15 Pro Max', 'iPhone 15 Pro Max', True),
                                       ('Samsung S24 Ultra', 'Samsung S25 Ultra', False)]:
            with self.subTest(query=query, title=title):
                self.assertEqual(model_evidence(query, {'title':title}), expected)

    def test_unpriced_exact_model_recovers_without_accepting_substitute(self):
        correct = self.product(price_unavailable=True)
        self.s['_web_choice_price_recovery'] = Mock(side_effect=lambda r,*_:dict(r, price_unavailable=False))
        result = self.pick([correct])
        self.assertEqual(result['url'], XCITE)
        self.assertEqual(result['money']['amount'], 79.56)
        self.s['_web_choice_price_recovery'].assert_called_once()

    def test_failed_recovery_has_no_final_offer_or_price(self):
        result = self.pick([self.product(price_unavailable=True)])
        self.assertEqual(result['status'], 'price_unavailable')
        self.assertNotIn('url', result)
        self.assertNotIn('money', result)

    def test_noon_category_expands_each_product_with_its_own_price_image_url(self):
        cards = []
        for series, price, sku in [('9000','133.69','N90000001A'), ('9000','115.81','N90000002A'), ('7000','79.56','N70000001A')]:
            url = f'https://www.noon.com/kuwait-en/lumea-{series}/{sku}/p/'
            self.assertFalse(self.real['_web_collection_url'](url))
            cards.append(f'<a href="{url}"><img src="https://img.example.com/{sku}.jpg" alt="Philips Lumea {series} Series"><h2>Philips Lumea {series} Series</h2><div data-qa="plp-product-box-price"><div class="_sellingPrice_test">KWD {price}</div></div></a>')
        products = self.real['_web_collection_products']('<html><div data-qa="plp-grid">'+''.join(cards)+'</div></html>', CATEGORY)
        self.assertEqual(len(products), 3)
        good = [p for p in products if '7000' in p['title']][0]
        self.assertIn('N70000001A/p/', good['link'])
        self.assertIn('N70000001A.jpg', good['image'])
        self.assertEqual(self.real['_web_indexed_offer_quote'](good)['min'], 79.56)

