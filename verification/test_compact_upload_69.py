"""Compact-schema isolation and ASGI timing; all model traffic simulated."""
import ast
import asyncio
import copy
import io
import json
import threading
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from test_audit_prices import scope, Clock, SOURCE
import test_audit_errors_68 as transport
import test_recovery_66 as recovery

GENERIC = {'error': {'code':400, 'status':'INVALID_ARGUMENT', 'message':'Request contains an invalid argument.'}}

class CompactTests(unittest.TestCase):
    def setUp(self):
        self.h = transport.TransportTests()
        self.h.setUp()
        schema_ns = scope(['_web_identity_response_schema'])
        self.h.payload['generationConfig']['responseSchema'] = schema_ns['_web_identity_response_schema'](2)
        self.original = copy.deepcopy(self.h.payload)

    def test_same_request_retries_with_only_array_bounds_changed_and_learns_acceptance(self):
        for streaming in (True,False):
            self.setUp()
            bad, good = transport.Response(data=GENERIC), self.h.ok()
            self.h.replies = [bad, good]
            result = self.h.invoke(streaming)
            self.assertEqual(len(self.h.calls),2)
            if streaming:self.assertEqual(result[1],'')
            before, after = [c['json'] for c in self.h.calls]
            expected = copy.deepcopy(before)
            def strip(v):
                if isinstance(v,dict):
                    v.pop('minItems',None);v.pop('maxItems',None)
                    for child in v.values():strip(child)
                elif isinstance(v,list):
                    for child in v:strip(child)
            strip(expected['generationConfig']['responseSchema'])
            self.assertEqual(after,expected)
            self.assertEqual(self.h.payload,self.original)
            self.assertIn('outcome=accepted_http',self.h.log)
            self.assertIn('retry=array_bounds',self.h.log)
            self.assertTrue(bad.closed)
            self.h.replies = [self.h.ok()]
            self.h.invoke(streaming)
            self.assertEqual(len(self.h.calls),3)
            self.assertEqual(self.h.calls[-1]['json'],expected)

    def test_same_model_different_count_reuses_mode_but_another_model_does_not(self):
        self.h.replies = [transport.Response(data=GENERIC),self.h.ok()];self.h.invoke()
        config=self.h.payload['generationConfig']['responseSchema']['properties']['items']
        config.update(minItems=4,maxItems=4)
        self.h.replies=[self.h.ok()];self.h.invoke()
        self.assertNotIn('maxItems',self.h.calls[-1]['json']['generationConfig']['responseSchema']['properties']['items'])
        payload,_,learned=self.h.ns['_web_audit_cached_payload']('https://other/models/new:streamGenerateContent',self.h.payload)
        self.assertFalse(learned);self.assertIn('maxItems',payload['generationConfig']['responseSchema']['properties']['items'])

    def test_failed_comparison_stops_after_two_requests_and_does_not_learn(self):
        self.h.replies=[transport.Response(data=GENERIC),transport.Response(data=GENERIC)]
        self.assertEqual(self.h.invoke()[1],'http_400')
        self.assertEqual(len(self.h.calls),2);self.assertFalse(self.h.ns['_WEB_AUDIT_SCHEMA_MODES'])
        self.assertIn('outcome=rejected',self.h.log)

    def test_cached_rejection_invalidates_mode(self):
        self.h.replies=[transport.Response(data=GENERIC),self.h.ok()];self.h.invoke()
        self.h.replies=[transport.Response(data=GENERIC)];self.h.invoke()
        self.assertEqual(len(self.h.calls),3);self.assertFalse(self.h.ns['_WEB_AUDIT_SCHEMA_MODES'])

    def test_no_retry_for_image_configuration_credit_or_unknown_shape(self):
        for data,status in [({'error':{'message':'Invalid image','status':'INVALID_ARGUMENT'}},400),
            ({'error':{'message':'maxOutputTokens out of range','status':'INVALID_ARGUMENT'}},400),
            ({'error':{'message':'Insufficient credit'}},402),
            ({'error':{'message':'An unknown error'}},400)]:
            self.setUp();self.h.replies=[transport.Response(status,data)]
            self.h.invoke();self.assertEqual(len(self.h.calls),1)

    def test_original_deadline_and_cancellation_are_preserved(self):
        self.h.elapsed=[8,2];self.h.replies=[transport.Response(data=GENERIC),self.h.ok()]
        self.h.invoke();self.assertEqual(self.h.calls[1]['timeout'],(5.,27.))
        self.setUp();self.h.elapsed=[34.5];self.h.replies=[transport.Response(data=GENERIC)]
        self.h.invoke();self.assertEqual(len(self.h.calls),1)
        self.setUp();self.h.cancel.set()
        with self.assertRaisesRegex(RuntimeError,'cancelled'):self.h.invoke()
        self.assertEqual(self.h.calls,[])

    def test_photo_understanding_and_text_requests_are_not_comparison_targets(self):
        for payload in [dict(self.h.payload,contents=[]),
                dict(self.h.payload,generationConfig={'responseSchema':{'properties':{'product_type':{}}}})]:
            self.assertIsNone(self.h.ns['_web_audit_compact_payload'](payload))

    def test_mode_expires_and_does_not_store_images_or_prompts(self):
        self.h.replies=[transport.Response(data=GENERIC),self.h.ok()];self.h.invoke()
        cache=self.h.ns['_WEB_AUDIT_SCHEMA_MODES']
        self.assertTrue(all(len(key)==64 and isinstance(value,(int,float)) for key,value in cache.items()))
        self.h.clock.now+=3601
        self.h.replies=[transport.Response(data=GENERIC),self.h.ok()];self.h.invoke()
        self.assertIn('maxItems',self.h.calls[-2]['json']['generationConfig']['responseSchema']['properties']['items'])

class LocalBoundsTests(unittest.TestCase):
    def setUp(self):
        self.h=recovery.AuditRecoveryTests();self.h.setup_request([])
        self.value=json.loads(self.h.answer())
        self.valid=scope(['_web_identity_local_array_bounds'])['_web_identity_local_array_bounds']

    def test_valid_wire_and_sparse_profiles_pass(self):
        self.assertTrue(self.valid(self.value,1,complete=True))
        self.value['reference_profile']={'category':'necklace'}
        self.assertTrue(self.valid(self.value,1,complete=True))

    def test_array_limits_remain_local_even_if_provider_accepts_compact_schema(self):
        for field in ('same_axes','different_axes','differences'):
            value=copy.deepcopy(self.value);value['items'][0][field]=['category']*41
            self.assertFalse(self.valid(value,1,complete=True))
        value=copy.deepcopy(self.value);value['items'][0]['candidate_profile'][0]['values']=['x']*9
        self.assertFalse(self.valid(value,1,complete=True))
        value=copy.deepcopy(self.value);value['reference_profile']*=100
        self.assertFalse(self.valid(value,1,complete=True))
        self.assertFalse(self.valid(self.value,2,complete=True))

    def test_oversized_answer_is_rejected_by_real_classifier_and_never_seeds_media(self):
        self.value['items'][0]['same_axes']=['category']*41
        self.h.setup_request([('STOP',json.dumps(self.value))])
        self.assertEqual(self.h.invoke()['review_error'],'invalid_array_bounds')
        self.assertEqual(self.h.seeds,[])

    def test_oversized_wire_profile_never_publishes_a_provisional_item(self):
        self.value['items'][0]['candidate_profile'][0]['values']=['necklace']*9
        partial=scope(['_web_identity_partial_response'])['_web_identity_partial_response']
        self.assertEqual(partial(json.dumps(self.value)),{})

class TimingTests(unittest.TestCase):
    def timing_class(self,clock):
        node=next(n for n in ast.parse(SOURCE.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='_FindziaImageTiming')
        ns=scope(['_web_search_trace_id'], {'time':clock,'json':json})
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(SOURCE),'exec'),ns)
        return ns['_FindziaImageTiming']

    def test_upload_delay_is_distinct_from_time_to_first_response(self):
        clock=Clock();messages=[{'type':'http.request','body':b'a'*10,'more_body':True},
                              {'type':'http.request','body':b'b'*20,'more_body':False}]
        received=[];sent=[]
        async def receive():clock.now+=5;return messages.pop(0)
        async def send(message):sent.append(message)
        async def app(scope,receive,send):
            received.extend([await receive(),await receive()]);clock.now+=2
            await send({'type':'http.response.start','status':200,'headers':[]})
            clock.now+=.5;await send({'type':'http.response.body','body':b'ok','more_body':True})
            clock.now+=1;await send({'type':'http.response.body','body':b'','more_body':False})
        with redirect_stdout(io.StringIO()) as out:
            asyncio.run(self.timing_class(clock)(app)({'type':'http','method':'POST','path':'/api/search/image/stream'},receive,send))
        data=json.loads(out.getvalue().split('IMAGE REQUEST TIMING ',1)[1])
        self.assertEqual((data['body_bytes'],data['body_complete_ms'],data['headers_ms'],data['first_body_ms'],data['total_ms']),
                         (30,10000,12000,12500,13500))
        self.assertEqual(len(received),2);self.assertEqual(len(sent),3)
        self.assertNotIn('aaaaaaaaaa',out.getvalue())

    def test_disconnect_and_unrelated_routes_are_passed_through(self):
        clock=Clock();seen=[]
        async def app(scope,receive,send):seen.append(await receive());raise asyncio.CancelledError()
        async def receive():return {'type':'http.disconnect'}
        async def send(message):pass
        with redirect_stdout(io.StringIO()) as out:
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(self.timing_class(clock)(app)({'type':'http','method':'POST','path':'/api/search/image/stream'},receive,send))
        self.assertEqual(seen,[{'type':'http.disconnect'}]);self.assertIn('"status": null',out.getvalue())

    def test_normalization_runs_off_loop_and_only_numeric_metadata_is_logged(self):
        clock=Clock();main_thread=threading.get_ident();threads=[]
        def normalize(data,mime):threads.append(threading.get_ident());return b'small','image/jpeg'
        ns=scope(['_web_prepare_image_bytes'],{'time':clock,'asyncio':asyncio,'_web_normalize_uploaded_image_bytes':normalize})
        request=SimpleNamespace(scope={'findzia_image_timing':{}})
        result=asyncio.run(ns['_web_prepare_image_bytes'](request,b'original','image/png',
            {'original_bytes':1000,'upload_bytes':500,'prepare_ms':42,'filename':'SECRET','url':'PRIVATE'}))
        self.assertEqual(result,(b'small','image/jpeg'));self.assertNotEqual(threads[0],main_thread)
        self.assertEqual(request.scope['findzia_image_timing']['client_upload_bytes'],500)
        self.assertNotIn('SECRET',json.dumps(request.scope));self.assertNotIn('PRIVATE',json.dumps(request.scope))

if __name__=='__main__':unittest.main(verbosity=2)
