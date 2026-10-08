import ast
import base64
import hashlib
import hmac
import json
from pathlib import Path
import re
import time
import unittest
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from findzia_choice import ChoiceEngine, install_choice, MAX_BODY


def text(value, limit):
    return str(value or '')[:limit]


def signing_helpers():
    # Exercise the actual application's token encoder/decoder without booting
    # unrelated search providers or billing integrations.
    tree = ast.parse(Path('main.py').read_text())
    names = {'_fz_evaluation_token', '_fz_evaluation_row'}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    env = dict(base64=base64, hashlib=hashlib, hmac=hmac, json=json, time=time,
               _REFINE_KEY=b'unit-test-only-key', _card_text=text,
               _CARD_SPEC_KEYS=re.compile('.*'), _web_offer_image_candidates=lambda row: [],
               _web_is_http_url=lambda u: u.startswith(('https://', 'http://')))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'actual-token-functions', 'exec'), env)
    return env


SIGN = signing_helpers()


def row(model='A1', price=40, currency='KWD', **extra):
    return dict(url='https://shop.example/'+model+'/'+str(price), title=model+' headphones',
                card_model=model, price=str(price), price_amount=price, currency=currency,
                store='Test shop', country='kw', classification_final=True,
                identity_review_status='completed', display_before_audit=False,
                match_type='exact', price_verified=True, **extra)


def services():
    return dict(WEB_API_ENABLED=True, _card_text=text, _web_language=lambda x:x,
                _web_rate_allowed=lambda request:True,
                _fz_evaluation_row=SIGN['_fz_evaluation_row'],
                _fz_listing_text=lambda r:r['title'],
                _findzia_hard_product_mismatch=lambda q,t:'wrong-category' in t,
                _fz_eval_money=lambda r:dict(amount=r['price_amount'],currency=r['currency'],kind=r.get('price_kind','exact')),
                _fz_eval_comparable=lambda a,b:a['card_model']==b['card_model'],
                _fz_eval_point=lambda value,evidence:value if value and all(q in evidence for q in value.get('evidence',[])) else None,
                _refine_ai=Mock(return_value=dict(status='selected',id='p1',match='suitable',reason=None)))


class ChoiceTests(unittest.TestCase):
    def setUp(self):
        self.s=services();self.engine=ChoiceEngine(self.s)

    def tearDown(self):
        self.engine.pool.shutdown(wait=True)

    def payload(self, rows, **kw):
        return dict(query='headphones', country='kw', lang='en',
                    offer_tokens=[SIGN['_fz_evaluation_token'](r) for r in rows], **kw)

    def pick(self, rows, **kw):
        return self.engine.choose(*self.engine.prepare(self.payload(rows,**kw)))

    def test_audit_fields_are_signed_and_preserved(self):
        r=row();decoded=SIGN['_fz_evaluation_row'](SIGN['_fz_evaluation_token'](r))
        for key in ('classification_final','identity_review_status','display_before_audit','match_type'):
            self.assertEqual(decoded[key],r[key])

    def test_forged_and_expired_tokens_do_not_become_candidates(self):
        p=self.payload([row()]);p['offer_tokens'][0]+='x'
        self.assertEqual(self.engine.prepare(p)[1],[])
        token=SIGN['_fz_evaluation_token'](row());raw,_=token.split('.')
        data=json.loads(base64.urlsafe_b64decode(raw+'='*(-len(raw)%4)));data['exp']=0
        raw=base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip('=')
        p['offer_tokens']=[raw+'.'+hmac.new(SIGN['_REFINE_KEY'],raw.encode(),hashlib.sha256).hexdigest()]
        self.assertEqual(self.engine.prepare(p)[1],[])

    def test_unreviewed_image_never_wins(self):
        for update in ({'classification_final':False},{'identity_review_status':'unavailable'},
                       {'identity_review_status':'failed'},{'identity_review_status':'streaming'}):
            r=row();r.update(update)
            self.assertEqual(self.pick([r],kind='image')['status'],'no_match')

    def test_reviewed_similar_candidate_can_be_chosen_without_exact_claim(self):
        r=row();r.update(match_type='similar',classification_reason='minor_colour_difference',
                         match_percentage=88,visual_differences=['slightly different shade'])
        result=self.pick([r],kind='image')
        self.assertEqual(result['status'],'selected')
        self.assertEqual(result['match'],'suitable')
        offer=self.s['_refine_ai'].call_args.args[1]['offers'][0]
        self.assertEqual(offer['identity']['visual_differences'],['slightly different shade'])
        self.assertEqual(offer['identity']['match_percentage'],88)

    def test_completed_audit_supersedes_retained_preview_flag(self):
        r=row();r['display_before_audit']=True
        self.assertEqual(self.pick([r],kind='image')['status'],'selected')

    def test_invalid_price_or_stock_excluded(self):
        for update in ({'price_estimated':True},{'price_kind':'range'}, {'price_integrity_status':'pending'},
                       {'stock_status':'out_of_stock'},{'price_unavailable':True},{'price_unit':'monthly'}):
            r=row();r.update(update)
            self.assertEqual(self.pick([r])['status'],'no_match')

    def test_ai_can_choose_a_suitable_model_over_cheapest(self):
        self.s['_refine_ai'].return_value.update(id='p2')
        result=self.pick([row('A1',10),row('B2',30)])
        self.assertEqual(result['money']['amount'],30)
        self.assertEqual(result['selection'],'ai')

    def test_same_model_lower_price_is_enforced(self):
        result=self.pick([row('A1',40),row('A1',30),row('B2',10)])
        self.assertEqual(result['money']['amount'],30)
        self.assertEqual(result['savings']['amount'],10)

    def test_currencies_not_compared_as_nominal_numbers(self):
        result=self.pick([row('A1',40,'KWD'),row('A1',10,'USD')])
        self.assertEqual(result['money']['currency'],'KWD')
        self.assertIsNone(result['savings'])

    def test_unknown_shipping_never_free_or_total(self):
        result=self.pick([row()]);self.assertFalse(result['money']['shipping_known'])
        self.assertIsNone(result['money']['shipping']);self.assertEqual(result['money']['basis'],'item')

    def test_verified_shipping_changes_comparison(self):
        a=row(price=30,shipping_amount=15,shipping_currency='KWD',shipping_country='kw',shipping_verified=True)
        b=row(price=40,shipping_amount=0,shipping_currency='KWD',shipping_country='kw',shipping_verified=True)
        result=self.pick([a,b]);self.assertEqual(result['money']['amount'],40)
        self.assertEqual(result['savings']['amount'],5)

    def test_shipping_for_other_country_is_unknown(self):
        result=self.pick([row(shipping_amount=0,shipping_currency='KWD',shipping_country='us',shipping_verified=True)])
        self.assertFalse(result['money']['shipping_known'])

    def test_unknown_ai_id_and_repeated_question_fail_closed(self):
        self.s['_refine_ai'].return_value=dict(status='selected',id='p999',match='exact')
        with self.assertRaises(ValueError):self.pick([row()])
        self.s['_refine_ai'].return_value=dict(status='question',question='Your budget?',choices=['20','50'])
        self.assertEqual(self.pick([row()])['status'],'question')
        with self.assertRaises(ValueError):self.pick([row()],answers=['50'])


    def test_malformed_ai_json_retries_without_user_action(self):
        self.s['_refine_ai'].side_effect=[json.JSONDecodeError('truncated','{"status":"selected",',20),
            dict(status='selected',id='p1',match='exact',reason=None)]
        result=self.pick([row()])
        self.assertEqual(result['status'],'selected')
        self.assertEqual(self.s['_refine_ai'].call_count,2)

    def test_complete_json_in_provider_wrapper_is_recovered(self):
        raw='Here is the decision: ```json\n{"status":"selected","id":"p1","match":"exact"}\n```'
        self.s['_refine_ai'].side_effect=json.JSONDecodeError('wrapper',raw,0)
        self.assertEqual(self.pick([row()])['status'],'selected')
        self.assertEqual(self.s['_refine_ai'].call_count,1)

    def test_invalid_ai_json_stops_after_two_attempts(self):
        self.s['_refine_ai'].side_effect=json.JSONDecodeError('truncated','{"status":',10)
        with self.assertRaises(ValueError):self.pick([row()])
        self.assertEqual(self.s['_refine_ai'].call_count,2)

    def test_two_conflicting_decisions_are_not_guessed(self):
        self.s['_refine_ai'].return_value='{"status":"no_match"}{"status":"selected","id":"p1","match":"exact"}'
        with self.assertRaises(ValueError):self.pick([row()])

    def test_cache_prevents_repeat_ai_calls(self):
        context,rows=self.engine.prepare(self.payload([row()]))
        _,future=self.engine.submit(context,rows);first=future.result(timeout=2)
        cached,second=self.engine.submit(context,rows)
        self.assertEqual(cached,first);self.assertIsNone(second)
        self.assertEqual(self.s['_refine_ai'].call_count,1)

    def test_route_success_limits_rate_and_outage(self):
        app=FastAPI();engine=install_choice(app,self.s)
        try:
            with TestClient(app) as client:
                p=self.payload([row()]);response=client.post('/api/choice',json=p)
                self.assertEqual(response.status_code,200);self.assertEqual(response.json()['status'],'selected')
                self.assertEqual(client.post('/api/choice',content=b'x'*(MAX_BODY+1)).status_code,413)
                self.assertEqual(client.post('/api/choice',json={'offer_tokens':'wrong'}).status_code,400)
                self.s['_web_rate_allowed']=lambda r:False
                self.assertEqual(client.post('/api/choice',json=p).status_code,429)
                self.s['_web_rate_allowed']=lambda r:True
                self.s['_refine_ai'].side_effect=RuntimeError('provider unavailable')
                p['query']='different headphones'
                response=client.post('/api/choice',json=p)
                self.assertEqual(response.status_code,503)
                self.assertNotIn('selection',response.json())
        finally:engine.pool.shutdown(wait=True)


if __name__=='__main__':unittest.main()
