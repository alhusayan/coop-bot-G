"""Run production transport/decoder against simulated provider HTTP responses.

No external requests or API keys. Includes regressions that fail on v67.
"""
import copy
import io
import json
import threading
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from test_audit_prices import Clock, scope
import test_recovery_66 as recovery

SCHEMA_ERROR = {'error': {'code': 400, 'message': 'Request contains an invalid argument.',
    'status': 'INVALID_ARGUMENT', 'details': [{'@type': 'type.googleapis.com/google.rpc.BadRequest',
        'fieldViolations': [{'field': 'generation_config.response_schema',
            'description': 'Too many states for constrained decoding.'}]}]}}


class Response:
    def __init__(self, status=400, data=None, raw=None, events=None):
        self.status_code, self.closed, self.reads = status, False, 0
        self.raw = raw if raw is not None else json.dumps(data).encode()
        self.events = events or []

    def json(self):
        self.reads += 1
        return json.loads(self.raw)

    def iter_content(self, chunk_size=4096):
        self.reads += 1
        for i in range(0, len(self.raw), chunk_size):
            yield self.raw[i:i+chunk_size]

    def iter_lines(self, **kwargs):
        for event in self.events:
            yield 'data: ' + json.dumps(event)
            yield ''
        raise AssertionError('Waited for EOF after terminal answer')

    def close(self): self.closed = True


class ErrorParsingTests(unittest.TestCase):
    def setUp(self):
        self.ns = scope(['_web_identity_http_error'])

    def classify(self, response, **kwargs):
        with redirect_stdout(io.StringIO()) as out:
            code = self.ns['_web_identity_http_error'](response, **kwargs)
        return code, out.getvalue()

    def test_array_wrapped_schema_error_is_not_lost(self):
        code, _ = self.classify(Response(data=[{'error': {'message': 'The response schema has too many states.'}}]))
        self.assertEqual(code, 'http_400_schema')

    def test_generic_message_uses_field_violation_to_select_compatibility(self):
        code, log = self.classify(Response(data=SCHEMA_ERROR))
        self.assertEqual(code, 'http_400_schema')
        self.assertIn('response_schema', log)
        self.assertIn('INVALID_ARGUMENT', log)

    def test_wrapped_image_error_is_not_lost(self):
        self.assertEqual(self.classify(Response(data=[{'error': {'message': 'Unable to process input image'}}]))[0], 'http_400_image')

    def test_alternate_error_envelopes_are_understood(self):
        for data in ({'message': 'responseSchema is invalid'}, {'error': 'Invalid response schema'},
                     {'errors': [{'message': 'responseJsonSchema is invalid'}]}):
            self.assertEqual(self.classify(Response(data=data))[0], 'http_400_schema')

    def test_diagnostics_never_log_provider_text_or_input(self):
        data = copy.deepcopy(SCHEMA_ERROR)
        secret = 'PRIVATE-TITLE user@example.test https://shop.test/private?key=SECRET YQ=='
        data['error']['message'] += secret
        payload = {'contents': [{'parts': [{'text': secret}, {'inline_data': {'data': secret, 'mime_type': secret}}]}],
                   'generationConfig': {'maxOutputTokens': 4600, 'responseSchema': {'description': secret}}}
        code, log = self.classify(Response(data=[data]), payload=payload, transport='sse')
        self.assertEqual(code, 'http_400_schema')
        for word in secret.split(): self.assertNotIn(word, log)
        self.assertIn('"images": 1', log)
        self.assertIn('"body_shape": "array"', log)
        self.assertIn('"max_output_tokens": 4600', log)

    def test_mixed_image_and_schema_violation_cannot_retry_only_schema(self):
        data = copy.deepcopy(SCHEMA_ERROR)
        data['error']['details'][0]['fieldViolations'].append({'field':'contents[0].parts[1].inline_data','description':'Invalid image'})
        code, log = self.classify(Response(data=data))
        self.assertEqual(code, 'http_400')
        self.assertIn('multiple_invalid_fields', log)

    def test_model_configuration_budget_is_distinct_from_account_budget(self):
        code, log = self.classify(Response(data={'error':{'message':'thinkingBudget is out of range'}}))
        self.assertEqual(code,'http_400'); self.assertIn('generation_config_invalid',log)
        self.assertNotIn('quota_or_budget',log)

    def test_invalid_key_and_credit_are_never_schema_retries(self):
        for status, message, category in [(400, 'API key not valid. schema', 'invalid_api_key'),
                (402, 'Insufficient credit balance', 'insufficient_credit')]:
            code, log = self.classify(Response(status, [{'error': {'message': message}}]))
            self.assertEqual(code, 'http_' + str(status)); self.assertIn(category, log)

    def test_oversized_non_json_and_failed_body_remain_http_errors(self):
        for response, shape in [(Response(raw=b'x'*20000), 'too_large'),
                                (Response(raw=b'<html>PRIVATE ERROR</html>'), 'non_json')]:
            code, log = self.classify(response)
            self.assertEqual(code,'http_400'); self.assertIn(shape,log); self.assertNotIn('PRIVATE ERROR',log)
        response = Response()
        def failed(**kwargs): raise TimeoutError('PRIVATE DETAIL')
        response.iter_content = failed
        code, log = self.classify(response)
        self.assertEqual(code,'http_400'); self.assertNotIn('PRIVATE DETAIL',log)

    def test_diagnostics_read_and_log_response_once(self):
        response = Response(data=SCHEMA_ERROR)
        first, log = self.classify(response)
        second, duplicate = self.classify(response)
        self.assertEqual(first,second); self.assertTrue(log); self.assertEqual(duplicate,'')
        self.assertEqual(response.reads,1)


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.clock, self.cancel, self.calls, self.costs = Clock(), threading.Event(), [], []
        self.replies, self.elapsed = [], []
        def post(url, **kwargs):
            self.calls.append(copy.deepcopy(kwargs))
            self.clock.now += self.elapsed.pop(0) if self.elapsed else 1
            return self.replies.pop(0)
        self.ns = scope(['_web_identity_stream_response', '_web_identity_post_response'], {
            'time': self.clock, 'requests': SimpleNamespace(post=post, Timeout=TimeoutError),
            'GEMINI_API_KEY': 'PRIVATE_KEY', '_api_cost_record': self.costs.append,
            '_gemini_usage_record': lambda *a, **k: None,
            'GEMINI_STATS_LOCK': threading.Lock(), 'GEMINI_STATS': {'plain_calls':0}})
        self.payload = {'systemInstruction': {'parts':[{'text':'strict audit contract'}]},
            'contents':[{'role':'user','parts':[{'text':'candidates 0 and 1'},
                 {'inline_data':{'mime_type':'image/png','data':'YQ=='}},
                 {'inline_data':{'mime_type':'image/jpeg','data':'Yg=='}}]}],
            'generationConfig':{'temperature':0,'responseMimeType':'application/json',
                'maxOutputTokens':2900,'responseSchema':{'type':'OBJECT', 'properties':{'reference_profile':{},'items':{}}}}}

    def ok(self):
        return Response(200, events=[{'candidates':[{'content':{'parts':[{'text':'{"reference_profile":[],"items":[]}'}]},'finishReason':'STOP'}]}])

    def invoke(self, stream=True):
        with redirect_stdout(io.StringIO()) as out:
            if stream:
                result = self.ns['_web_identity_stream_response']('https://test/models/model:generateContent',
                    self.payload, 35, lambda _:None, self.cancel)
            else:
                result = self.ns['_web_identity_post_response']('https://test/models/model:generateContent',
                    self.payload, 35, self.cancel)
        self.log = out.getvalue()
        return result

    def test_array_error_recovers_using_same_images_contract_and_deadline(self):
        bad, good = Response(data=[SCHEMA_ERROR]), self.ok()
        self.replies, self.elapsed = [bad, good], [4, 1]
        original = copy.deepcopy(self.payload)
        answer, error = self.invoke()
        self.assertEqual(error, ''); self.assertEqual(answer['candidates'][0]['finishReason'], 'STOP')
        self.assertEqual(len(self.calls),2)
        self.assertEqual(self.calls[1]['timeout'],(5.0,31.0))
        self.assertEqual(self.calls[1]['json']['contents'],original['contents'])
        self.assertEqual(self.calls[1]['json']['systemInstruction'],original['systemInstruction'])
        self.assertEqual(self.calls[1]['json']['generationConfig'],{k:v for k,v in original['generationConfig'].items() if k!='responseSchema'})
        self.assertEqual(self.payload,original); self.assertTrue(bad.closed and good.closed)
        self.assertEqual(self.costs.count('gemini_identity_schema_retries'),1)

    def test_response_json_schema_is_removed_for_both_transports(self):
        for streaming in (True,False):
            self.setUp()
            config = self.payload['generationConfig']
            config['responseJsonSchema'] = config.pop('responseSchema')
            bad, good = Response(data=[SCHEMA_ERROR]), self.ok()
            self.replies = [bad,good]
            self.invoke(streaming)
            self.assertEqual(len(self.calls),2)
            self.assertNotIn('responseJsonSchema',self.calls[1]['json']['generationConfig'])
            self.assertTrue(bad.closed)

    def test_unknown_bad_input_credit_and_quota_do_not_retry(self):
        for streaming in (True,False):
            for status, message in [(400,'Request contains an invalid argument.'),
                    (400,'Unable to process input image'), (400,'API key not valid'),
                    (402,'Insufficient credit balance'),(429,'Resource exhausted')]:
                self.setUp(); self.replies = [Response(status, {'error':{'message':message}})]
                self.invoke(streaming)
                self.assertEqual(len(self.calls),1)

    def test_schema_rejection_without_schema_does_not_retry(self):
        for streaming in (True,False):
            self.setUp(); self.payload['generationConfig'].pop('responseSchema')
            self.replies = [Response(data=SCHEMA_ERROR)]
            self.invoke(streaming); self.assertEqual(len(self.calls),1)

    def test_second_rejection_stops_after_one_compatibility_attempt(self):
        for streaming in (True,False):
            self.setUp(); first, second = Response(data=SCHEMA_ERROR), Response(data=SCHEMA_ERROR)
            self.replies = [first,second]
            result = self.invoke(streaming)
            self.assertEqual(len(self.calls),2); self.assertTrue(first.closed)
            self.assertEqual(result[1] if streaming else self.ns['_web_identity_http_error'](result),'http_400_schema')

    def test_no_retry_after_deadline_or_cancellation(self):
        for streaming in (True,False):
            self.setUp(); self.elapsed = [34.5]; self.replies = [Response(data=SCHEMA_ERROR)]
            self.invoke(streaming); self.assertEqual(len(self.calls),1)
            self.setUp(); self.cancel.set()
            with self.assertRaisesRegex(RuntimeError,'cancelled'): self.invoke(streaming)
            self.assertEqual(self.calls,[])

    def test_cancellation_after_first_error_closes_stream_and_stops(self):
        self.replies = [Response(data=SCHEMA_ERROR)]
        original = self.ns['requests'].post
        def post(*a,**k):
            response = original(*a,**k); self.cancel.set(); return response
        self.ns['requests'].post = post
        with self.assertRaisesRegex(RuntimeError,'cancelled'): self.invoke()
        self.assertEqual(len(self.calls),1)


class FullAuditCompatibilityTests(unittest.TestCase):
    def test_recovered_request_still_uses_strict_final_identity_validation(self):
        # Wire the actual production HTTP helper into the existing full audit
        # harness so a successful transport retry cannot bypass final checks.
        for malformed in (False,True):
            harness = recovery.AuditRecoveryTests()
            harness.setup_request([])
            ns = scope(['_web_identity_stream_response'], {
                'time':harness.clock, 'GEMINI_API_KEY':'test',
                '_api_cost_record':lambda *a:None,'_gemini_usage_record':lambda *a,**k:None,
                'GEMINI_STATS_LOCK':threading.Lock(),'GEMINI_STATS':{'plain_calls':0},
                'requests':SimpleNamespace(Timeout=TimeoutError)})
            answer = harness.answer()
            if malformed: answer = answer.replace('"id": 0','"id": 0, "id": 0')
            replies = [Response(data=[SCHEMA_ERROR]), Response(200, events=[{
                'candidates':[{'content':{'parts':[{'text':answer}]},'finishReason':'STOP'}]}])]
            ns['requests'].post = lambda *a,**k: replies.pop(0)
            harness.ns['_web_identity_stream_response'] = ns['_web_identity_stream_response']
            with redirect_stdout(io.StringIO()): result = harness.invoke()
            if malformed:
                self.assertIn('review_error',result); self.assertEqual(harness.seeds,[])
            else:
                self.assertEqual(len(result['items']),1); self.assertTrue(harness.seeds)


if __name__ == '__main__': unittest.main(verbosity=2)
