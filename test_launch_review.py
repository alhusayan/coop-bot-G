"""Offline launch regression tests; no provider calls or app startup."""
import ast
import copy
import html
import re
import unittest
import unicodedata
from pathlib import Path
from findzia_search_quality import explicit_text_conflict

ROOT=Path(__file__).resolve().parents[1]

def photo_helpers():
    tree=ast.parse((ROOT/'main.py').read_text())
    names={'normalize_ar','_web_ascii_digits','_fz_facet_norm','_parity_norm','_parity_has','_parity_values',
           '_refine_canonical_key','_photo_addition_steps','_photo_extra_context','_refine_effective_base','_photo_refinement_plan',
           '_FZ_FACET_ALIASES','_REFINE_COLOR_WORDS','_REFINE_COLOR_RE','_PARITY_COLORS','_PARITY_MATERIALS','_PHOTO_EXTRA_NEGATION','_PHOTO_SEARCH_PREFERENCE_RE'}
    selected=[]
    for node in tree.body:
        if isinstance(node,ast.FunctionDef) and node.name in names:selected.append(node)
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in node.targets):selected.append(node)
    env=dict(re=re,copy=copy,html=html,unicodedata=unicodedata,_PHOTO_ADDITION_LIMIT=500,_intent_label=lambda key,lang:key)
    exec(compile(ast.Module(body=selected,type_ignores=[]),'main.py','exec'),env)
    return env

class SearchQuality(unittest.TestCase):
    def test_fast_provider_admission_rejects_conflicts_before_passthrough(self):
        tree=ast.parse((ROOT/'main.py').read_text())
        names={'_web_serper_text_passthrough','_local_discovery_candidate_ok'}
        functions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
        env={'_web_text_explicit_conflict':explicit_text_conflict}
        exec(compile(ast.Module(body=functions,type_ignores=[]),'main.py','exec'),env)
        row={'text_provider_passthrough':True,'search_origin':'text','retrieval_sources':['serper_shopping']}
        check=env['_local_discovery_candidate_ok']
        self.assertFalse(check('JBL Flip 7',dict(row,title='JBL Flip 6 speaker')))
        self.assertFalse(check('JBL Flip 7',dict(row,title='Replacement battery for JBL Flip 7')))
        self.assertTrue(check('JBL Flip 7',dict(row,title='JBL Flip 7 black speaker')))

    def test_explicit_wrong_models(self):
        for query,title in [('JBL Flip 7','JBL Flip 6 portable speaker'),('iPhone 17','Apple iPhone 16'),('Canon R50','Canon R10 camera'),('Sony WH-1000','Sony WH-900 headset')]:
            with self.subTest(query=query):self.assertTrue(explicit_text_conflict(query,title))

    def test_accessory_is_not_device(self):
        self.assertTrue(explicit_text_conflict('JBL Flip 7','3.6V battery replacement for JBL Flip 7'))
        self.assertTrue(explicit_text_conflict('chair','Stretch cover for chair'))

    def test_valid_variants_bundles_and_generic_queries_stay(self):
        for query,title in [('JBL Flip 7','JBL Flip 7 speaker with case for travel'),
            ('battery for JBL Flip 7','Replacement battery for JBL Flip 7'),
            ('case for iPhone 17','Protective case for iPhone 17'),
            ('JBL Flip 7','JBL Flip 6 / Flip 7'),('chair','Dining chair 45 cm'),
            ('laptop 16 GB','laptop 32 GB'),('Bluetooth 5 speaker','Bluetooth 6 speaker'),
            ('mobile','Samsung Galaxy S26'),('فستان','فستان سهرة'),('robe','Robe longue')]:
            with self.subTest(query=query,title=title):self.assertFalse(explicit_text_conflict(query,title))

class PhotoRefinement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.h=photo_helpers()

    def test_changing_colour_replaces_previous_edit_and_keeps_identity(self):
        base={'kind':'image','base':'JBL Flip 7 Black speaker','steps':[]}
        blue=self.h['_photo_extra_context'](base,'blue')
        red=self.h['_photo_extra_context'](blue,'red')
        self.assertEqual(base['steps'],[])
        self.assertEqual([s['term'] for s in red['steps']],['red'])
        self.assertEqual(self.h['_refine_effective_base'](red),'JBL Flip 7 speaker')
        self.assertEqual(red['root_reference'],base['base'])

    def test_storage_and_size_replacement(self):
        for base,extra,missing in [('Phone 128GB','256GB','128GB'),('Shoes size EU 42','size EU 44','EU 42')]:
            context=self.h['_photo_extra_context']({'kind':'image','base':base,'steps':[]},extra)
            self.assertNotIn(missing,self.h['_refine_effective_base'](context))
            self.assertEqual(context['user_extra'],extra)

    def test_brand_protection_and_nonenglish_colour(self):
        context=self.h['_photo_extra_context']({'kind':'image','base':'Black and Decker black drill','steps':[]},'rouge')
        self.assertEqual(context['steps'][0]['term'],'red')
        self.assertIn('Black and Decker',self.h['_refine_effective_base'](context))

    def test_negation_and_unknown_requirements_never_disappear(self):
        steps=self.h['_photo_addition_steps']('not red waterproof')
        self.assertEqual(steps[0]['key'],'custom_request')
        self.assertEqual(steps[0]['term'],'not red waterproof')

    def test_retrieval_keeps_full_preference_but_lens_hint_is_concise(self):
        ctx={'base':'JBL Flip 7 7 speaker','query_en':'JBL Flip 7 7 speaker black latest model indoors',
             'steps':[{'key':'color','term':'black'},{'key':'custom_request','term':'latest model indoors'}]}
        result=self.h['_photo_refinement_plan'](ctx)
        self.assertEqual(result['lens_hint'],'black')
        self.assertIn('latest model indoors',result['query'])
        self.assertNotIn('7 7',result['query'])

if __name__=='__main__':unittest.main()
