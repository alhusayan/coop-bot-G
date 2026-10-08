import ast
import base64
import hashlib
import hmac
import json
import os
import threading
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
    tree = ast.parse(Path(os.environ.get('FINDZIA_MAIN_FILE', 'main.py')).read_text())
    names = {'_fz_evaluation_token', '_fz_evaluation_row'}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    env = dict(base64=base64, hashlib=hashlib, hmac=hmac, json=json, time=time,
               _REFINE_KEY=b'unit-test-only-key', _card_text=text,
               _CARD_SPEC_KEYS=re.compile('.*'), _web_offer_image_candidates=lambda row: [row['image']] if row.get('image') else [],
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


def ai_response(system, data, **kwargs):
    if kwargs.get('images'):
        return dict(status='reviewed', items=[dict(id=c['id'], verdict='match',
            observation='Same visible shape, colour family and placement of details') for c in data['candidates']])
    return dict(status='selected',id=data['offers'][0]['id'],match='suitable',reason=None)


def services():
    return dict(WEB_API_ENABLED=True, _card_text=text, _web_language=lambda x:x,
                _web_rate_allowed=lambda request:True,
                _fz_evaluation_row=SIGN['_fz_evaluation_row'],
                _fz_listing_text=lambda r:r['title'],
                _findzia_hard_product_mismatch=lambda q,t:'wrong-category' in t,
                _fz_eval_money=lambda r:dict(amount=r['price_amount'],currency=r['currency'],kind=r.get('price_kind','exact')),
                _fz_eval_comparable=lambda a,b:a['card_model']==b['card_model'],
                _fz_eval_point=lambda value,evidence:value if value and all(q in evidence for q in value.get('evidence',[])) else None,
                _web_visual_reference_inline=lambda data:dict(mime_type='image/png',data=data),
                _web_visual_candidate_inline=lambda r:dict(mime_type='image/png',data=base64.b64encode(r['image'].encode()).decode()),
                _refine_ai=Mock(return_value=dict(status='selected',id='p1',match='suitable',reason=None)))


class ChoiceTests(unittest.TestCase):
    def setUp(self):
        self.s=services();self.engine=ChoiceEngine(self.s)

    def tearDown(self):
        self.engine.pool.shutdown(wait=True)
        self.engine.media_pool.shutdown(wait=True)
        self.engine.visual_pool.shutdown(wait=True)

    def payload(self, rows, **kw):
        if kw.get('kind') == 'image':
            for r in rows:
                r.setdefault('image',r['url']+'/photo.png')
            kw.setdefault('image_base64',base64.b64encode(b'reference-pixels').decode())
            kw.setdefault('offer_images',[dict(token=SIGN['_fz_evaluation_token'](r),image=r['image']) for r in rows])
        return dict(query='headphones', country='kw', lang='en',
                    offer_tokens=[SIGN['_fz_evaluation_token'](r) for r in rows], **kw)

    def pick(self, rows, **kw):
        if kw.get('kind') == 'image' and self.s['_refine_ai'].side_effect is None:
            self.s['_refine_ai'].side_effect=ai_response
        return self.engine.choose(*self.engine.prepare(self.payload(rows,**kw)))

    def test_original_and_candidate_pixels_reach_vision_as_images(self):
        result=self.pick([row()],kind='image')
        call=self.s['_refine_ai'].call_args_list[0]
        images=call.kwargs['images']
        self.assertEqual([label for label,_ in images],['REFERENCE_IMAGE','CANDIDATE_IMAGE p1'])
        self.assertEqual(images[0][1],dict(mimeType='image/png',data=base64.b64encode(b'reference-pixels').decode()))
        self.assertEqual(set(images[1][1]),{'mimeType','data'})
        self.assertNotIn('_reference_image',call.args[1]['request'])
        self.assertTrue(result['visual_verified'])

    def test_different_coat_cannot_win_even_with_signed_exact_label(self):
        def reject(system,data,**kw):
            return dict(status='reviewed',items=[dict(id=c['id'],verdict='different',
                observation='Dark lapel coat with chest beading differs from light collared sleeve-flower garment') for c in data['candidates']])
        self.s['_refine_ai'].side_effect=reject
        self.assertEqual(self.pick([row('coat',99)],kind='image')['status'],'no_match')
        self.assertEqual(self.s['_refine_ai'].call_count,1)

    def test_rejected_cheaper_offer_cannot_replace_visual_match(self):
        def review(system,data,**kw):
            if kw.get('images'):
                return dict(status='reviewed',items=[dict(id=c['id'],verdict='match' if c['id']=='p1' else 'different',
                    observation='Matching sleeve details' if c['id']=='p1' else 'Different chest details') for c in data['candidates']])
            return ai_response(system,data,**kw)
        self.s['_refine_ai'].side_effect=review
        result=self.pick([row('coat',99),row('coat',5)],kind='image')
        self.assertEqual(result['money']['amount'],99)
        self.assertIsNone(result['savings'])
        self.assertEqual(len(self.s['_refine_ai'].call_args.args[1]['offers']),1)

    def test_missing_or_unsigned_images_never_fall_back_to_text(self):
        p=self.payload([row()],kind='image');p.pop('image_base64')
        with self.assertRaises(ValueError):self.engine.prepare(p)
        p=self.payload([row()],kind='image');p['offer_images'][0]['image']='https://other.example/forged.jpg'
        self.s['_web_visual_candidate_inline']=Mock()
        with self.assertRaises(RuntimeError):self.engine.choose(*self.engine.prepare(p))
        self.s['_web_visual_candidate_inline'].assert_not_called()
        self.s['_refine_ai'].assert_not_called()

    def test_recovered_image_must_belong_to_same_signed_listing(self):
        original=row();p=self.payload([original],kind='image')
        recovered=dict(original,image='https://store.example/recovered.jpg')
        p['offer_images'][0].update(image=recovered['image'],media_token=SIGN['_fz_evaluation_token'](recovered))
        self.s['_refine_ai'].side_effect=ai_response
        self.assertEqual(self.engine.choose(*self.engine.prepare(p))['status'],'selected')
        recovered['url']='https://other.example/item'
        p['offer_images'][0]['media_token']=SIGN['_fz_evaluation_token'](recovered)
        with self.assertRaises(RuntimeError):self.engine.choose(*self.engine.prepare(p))

    def test_all_candidates_beyond_eight_are_visually_reviewed(self):
        def ninth(system,data,**kw):
            if kw.get('images'):
                return dict(status='reviewed',items=[dict(id=c['id'],verdict='match' if c['id']=='p9' else 'different',
                    observation='Visible matching product' if c['id']=='p9' else 'Different construction') for c in data['candidates']])
            return ai_response(system,data,**kw)
        self.s['_refine_ai'].side_effect=ninth
        result=self.pick([row('item'+str(i),i+1) for i in range(9)],kind='image')
        self.assertEqual(result['money']['amount'],9)
        calls=[c for c in self.s['_refine_ai'].call_args_list if c.kwargs.get('images')]
        self.assertEqual(sorted(len(c.kwargs['images']) for c in calls),[2,9])

    def test_visual_cache_is_reused_only_for_same_reference_and_pixels(self):
        self.pick([row()],kind='image')
        self.pick([row()],kind='image')
        calls=lambda:[c for c in self.s['_refine_ai'].call_args_list if c.kwargs.get('images')]
        self.assertEqual(len(calls()),1)
        self.pick([row()],kind='image',image_base64=base64.b64encode(b'another-reference').decode())
        self.assertEqual(len(calls()),2)
        self.s['_web_visual_candidate_inline']=lambda r:dict(mime_type='image/png',data='changed-pixels')
        self.pick([row()],kind='image')
        self.assertEqual(len(calls()),3)

    def test_incomplete_visual_contract_cannot_select(self):
        self.s['_refine_ai'].return_value=dict(status='reviewed',items=[])
        p=self.payload([row()],kind='image')
        with self.assertRaises(ValueError):self.engine.choose(*self.engine.prepare(p))
        self.assertEqual(self.s['_refine_ai'].call_count,2)

    def test_actual_refine_transport_serializes_two_inline_images(self):
        tree=ast.parse(Path(os.environ.get('FINDZIA_MAIN_FILE','main.py')).read_text())
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_refine_ai')
        requests=Mock();requests.post.return_value.json.return_value={'candidates':[{'content':{'parts':[{'text':'{"status":"reviewed","items":[]}'}]}}]}
        env=dict(json=json,re=re,threading=threading,requests=requests,GEMINI_API_KEY='test-only',
            _REFINE_SLOTS=threading.BoundedSemaphore(1),GEMINI_STATS_LOCK=threading.Lock(),GEMINI_STATS={'plain_calls':0},
            GEMINI_BASE_URL='https://provider.invalid',REFINE_MODEL='gemini-2.5-flash',_gemini_usage_record=lambda *a:None)
        exec(compile(ast.Module(body=[node],type_ignores=[]),'actual-refine-transport','exec'),env)
        images=[('REFERENCE_IMAGE',dict(mimeType='image/png',data='reference')),('CANDIDATE_IMAGE p1',dict(mimeType='image/png',data='candidate'))]
        env['_refine_ai']('compare',{},images=images)
        parts=requests.post.call_args.kwargs['json']['contents'][0]['parts']
        self.assertEqual([p['inlineData'] for p in parts if 'inlineData' in p],[x[1] for x in images])

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
        self.assertEqual(offer['visual']['verdict'],'match')
        self.assertTrue(result['visual_verified'])

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
        finally:
            engine.pool.shutdown(wait=True)
            engine.media_pool.shutdown(wait=True)
            engine.visual_pool.shutdown(wait=True)


if __name__=='__main__':unittest.main()
