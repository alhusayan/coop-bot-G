import ast
import re
import unittest
from pathlib import Path
from findzia_guide_identity import compatible, models, question_allowed


class GuideIdentityTests(unittest.TestCase):
    def test_exact_models_and_variants(self):
        cases = [('iPhone 18 Pro', 'iPhone 15 Pro Max'),
                 ('iPhone 18 Pro', 'iPhone 18 Pro Max'),
                 ('Galaxy S26 Ultra', 'Galaxy S25 Ultra'),
                 ('MacBook Air M4', 'MacBook Pro M4'),
                 ('Sony WH-1000XM5', 'Sony WH-1000XM4'),
                 ('Canon R50', 'Canon R10'), ('JBL Flip 7', 'JBL Flip 6')]
        for base, other in cases:
            with self.subTest(base=base, other=other):
                self.assertFalse(compatible(base, other))
                self.assertFalse(compatible(base, base + ' ' + other))
                self.assertTrue(compatible(base, base + ' black 256 GB', True))
                self.assertTrue(compatible(base, 'under KWD 400 size EU 44'))

    def test_arabic_and_compact_models(self):
        self.assertEqual(models('آيفون ١٨ برو'), models('iPhone18 Pro'))
        self.assertFalse(compatible('آيفون ١٨ برو', 'iPhone 15 Pro Max'))
        self.assertFalse(compatible('جالكسي S26 الترا', 'Galaxy S25 Ultra'))
        self.assertTrue(compatible('آيفون ١٨ برو', 'iPhone 18 Pro 1 TB', True))

    def test_generic_queries_and_specs_are_not_models(self):
        for base in ['phone', 'laptop 16 GB', 'chair 45 cm', 'Bluetooth 5.3 speaker']:
            self.assertFalse(models(base))
            self.assertTrue(compatible(base, 'iPhone 18 Pro'))

    def test_bad_question_and_option_are_suppressed(self):
        base = 'iPhone 18 Pro'
        self.assertFalse(question_allowed(base, {'question_key': 'preferred_model'}))
        self.assertFalse(question_allowed(base, {'question': 'Color for iPhone 15 Pro Max?'}))
        self.assertFalse(question_allowed(base, {'question': 'Your choice?', 'choices': [
            {'label': 'Keep this model', 'answer': 'iPhone 15 Pro Max'}]}))
        self.assertFalse(question_allowed(base, {'question_key': 'storage_capacity'}, ['storage']))
        self.assertTrue(question_allowed(base, {'question_key': 'colour', 'question': 'Preferred colour?',
            'choices': [{'label': 'Black', 'answer': 'black'}, {'label': 'White', 'answer': 'white'}]}))

    def test_actual_query_path_rejects_contaminated_fallback(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'main.py').read_text())
        funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_fz_needs_query']
        env = dict(_fz_needs_identity_ok=compatible, re=re,
                   _refine_safe_query=lambda s: str(s or '').strip(),
                   _findzia_hard_product_mismatch=lambda a,b: False,
                   _fz_product_form_conflict=lambda a,b,**kw: False,
                   _intent_profile=lambda c: {}, _web_ascii_digits=lambda s:s,
                   _fz_facet_norm=lambda s:s.casefold())
        exec(compile(ast.Module(body=funcs, type_ignores=[]), 'main.py', 'exec'), env)
        context = dict(query='iPhone 18 Pro', kind='text', answers=['iPhone 15 Pro Max', '1 TB'],
                       draft_query='iPhone 18 Pro iPhone 15 Pro Max 1 TB')
        query = env['_fz_needs_query']
        for generated in ['', 'iPhone 15 Pro Max 1 TB', context['draft_query']]:
            self.assertEqual(query(context, generated), 'iPhone 18 Pro 1 TB')
        context.update(answers=['Black'], draft_query='iPhone 18 Pro Black 256 GB')
        self.assertEqual(query(context), context['draft_query'])
        photo = dict(query='photo', kind='image', extra_specs='', answers=['blue'], draft_query='blue')
        self.assertEqual(query(photo, 'blue dress'), 'blue')


if __name__ == '__main__':
    unittest.main()
