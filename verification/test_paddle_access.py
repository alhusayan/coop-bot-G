"""156.7.57 regression checks. Temporary DB and mocked providers only."""
import copy
import io
import time
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from fastapi import HTTPException
from findzia_paddle import PaddleAPIError
from findzia_plans import BY_ID
import test_prepaid_packs as fixtures


class PaddleAccessTests(unittest.TestCase):
    setUp = fixtures.PrepaidTests.setUp
    balance = fixtures.PrepaidTests.balance

    def rows(self):
        with self.accounts.connect() as db:
            return [dict(r) for r in db.execute(f'SELECT * FROM {self.paddle.prefix}checkout ORDER BY created')]

    def pending(self, plan='pack50'):
        self.intent, self.tid = 'a' * 48, 'txn_' + 'x' * 26
        with self.accounts.connect() as db:
            db.execute(f'INSERT INTO {self.paddle.prefix}checkout VALUES(?,?,?,?,?,?)',
                       (self.intent, 'm1', plan, self.tid, int(time.time()) - 20, 'pending'))
        return {'id': self.tid, 'status': 'ready', 'origin': 'api',
                'collection_mode': 'automatic', 'currency_code': 'USD', 'payments': [],
                'custom_data': {'findzia_intent': self.intent},
                'items': [{'quantity': 1, 'price': {'id': self.paddle.prices[plan]}}]}

    def assert_access_error(self, plan, status=403, resume=None):
        with self.assertRaises(HTTPException) as raised:
            self.paddle.checkout(self.member, plan, resume)
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.detail,
                         'paddle_access_denied' if status == 403 else 'paddle_authentication_failed')
        self.assertEqual(self.balance(), 0)
        with self.accounts.connect() as db:
            for table in (self.paddle.prefix + 'checkout_lock', 'fz_checkout_creation_lock'):
                self.assertEqual(db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0], 0)

    def test_existing_transaction_get_access_failure_stops_polling_and_preserves_record(self):
        self.pending(); before = self.rows()
        for status in (401, 403):
            for resume in (None, self.intent):
                with self.subTest(status=status, resume=bool(resume)):
                    self.paddle.api = Mock(side_effect=PaddleAPIError(status, 'forbidden'))
                    self.assert_access_error('pack', status, resume)
                    self.paddle.api.assert_called_once_with('GET', '/transactions/' + self.tid)
                    self.assertEqual(self.rows(), before)

    def test_cancel_access_failure_cannot_create_different_checkout(self):
        txn = self.pending(); before = self.rows()
        self.paddle.api = Mock(side_effect=[txn, PaddleAPIError(403, 'forbidden')])
        self.assert_access_error('pack100')
        self.assertEqual([c.args[0] for c in self.paddle.api.call_args_list], ['GET', 'PATCH'])
        self.assertEqual(self.rows(), before)

    def test_completed_payment_missing_adjustment_access_is_not_false_pending_or_success(self):
        txn = self.pending(); txn['status'] = 'completed'; before = self.rows()
        self.paddle.api = Mock(side_effect=[txn, PaddleAPIError(403, 'forbidden')])
        self.assert_access_error('pack100')
        self.assertEqual(self.paddle.api.call_args_list[-1].args,
                         ('GET', '/transactions/' + self.tid + '?include=adjustments'))
        self.assertEqual(self.rows(), before)

    def test_price_access_failure_leaves_no_order_or_payment(self):
        for plan in ('pack50', 'pack100'):
            with self.subTest(plan=plan):
                self.paddle.api = Mock(side_effect=PaddleAPIError(403, 'forbidden'))
                self.assert_access_error(plan)
                self.paddle.api.assert_called_once_with('GET', '/prices/' + self.paddle.prices[plan])
                self.assertEqual(self.rows(), [])

    def test_create_access_failure_is_rejected_not_pending(self):
        self.paddle.api = Mock(side_effect=PaddleAPIError(403, 'forbidden'))
        self.assert_access_error('pack')
        self.assertEqual(self.paddle.api.call_args.args[:2], ('POST', '/transactions'))
        self.assertEqual([(r['state'], r['txn']) for r in self.rows()], [('rejected', None)])

    def test_restored_read_permission_reopens_same_transaction_without_new_charge(self):
        txn = self.pending(); before = self.rows()
        self.paddle.api = Mock(side_effect=PaddleAPIError(403, 'forbidden'))
        self.assert_access_error('pack50')
        self.paddle.api = Mock(return_value=txn)
        self.assertEqual(self.paddle.checkout(self.member, 'pack50'), {'transaction_id': self.tid})
        self.paddle.api.assert_called_once_with('GET', '/transactions/' + self.tid)
        self.assertEqual(self.rows(), before)

    def test_restored_write_permission_switches_plan_once_after_provider_cancellation(self):
        old = self.pending()
        self.paddle.api = Mock(side_effect=[old, PaddleAPIError(403, 'forbidden')])
        self.assert_access_error('pack100')
        calls = []; new_id = 'txn_' + 'z' * 26; new = {}
        def api(method, path, body=None, **kwargs):
            calls.append((method, path))
            if method == 'GET' and path == '/transactions/' + self.tid:
                return copy.deepcopy(old)
            if method == 'PATCH':
                self.assertEqual((path, body), ('/transactions/' + self.tid, {'status': 'canceled'}))
                old['status'] = 'canceled'
                return copy.deepcopy(old)
            if path.startswith('/prices/'):
                return {'id': self.paddle.prices['pack100'], 'status': 'active', 'billing_cycle': None,
                        'trial_period': None, 'unit_price': {'currency_code': 'USD', 'amount': '1799'}}
            if method == 'POST':
                self.assertEqual(path, '/transactions')
                self.assertEqual(body['items'], [{'price_id': self.paddle.prices['pack100'], 'quantity': 1}])
                new.update(id=new_id, status='ready', origin='api', collection_mode='automatic',
                           currency_code='USD', custom_data=body['custom_data'], payments=[],
                           items=[{'quantity': 1, 'price': {'id': self.paddle.prices['pack100']}}])
                return {'id': new_id}
            self.assertEqual((method, path), ('GET', '/transactions/' + new_id))
            return copy.deepcopy(new)
        self.paddle.api = api
        self.assertEqual(self.paddle.checkout(self.member, 'pack100'), {'transaction_id': new_id})
        self.assertEqual(self.paddle.checkout(self.member, 'pack100'), {'transaction_id': new_id})
        self.assertEqual(sum(m == 'POST' for m, _ in calls), 1)
        self.assertLess(next(i for i, c in enumerate(calls) if c[0] == 'PATCH'),
                        next(i for i, c in enumerate(calls) if c[0] == 'POST'))
        self.assertEqual([r['state'] for r in self.rows()], ['canceled', 'pending'])
        self.assertEqual(self.balance(), 0)

    def test_cancellation_timeout_and_other_provider_failures_keep_pending(self):
        txn = self.pending(); before = self.rows()
        for error in (RuntimeError('paddle_unavailable'), PaddleAPIError(500),
                      PaddleAPIError(429), PaddleAPIError(409), PaddleAPIError(404)):
            with self.subTest(error=str(error)):
                self.paddle.api = Mock(side_effect=[txn, error])
                self.assertTrue(self.paddle.checkout(self.member, 'pack100')['payment_pending'])
                self.assertEqual(self.rows(), before)
                self.assertEqual(self.balance(), 0)

    def test_active_payment_never_cancels_or_creates_second_transaction(self):
        txn = self.pending(); before = self.rows()
        for status in ('authorized', 'authorized_flagged', 'captured', 'created',
                       'pending_no_action_required', 'action_required', 'unknown'):
            with self.subTest(status=status):
                txn['payments'] = [{'status': status}]
                self.paddle.api = Mock(return_value=txn)
                self.assertTrue(self.paddle.checkout(self.member, 'pack')['payment_pending'])
                self.paddle.api.assert_called_once_with('GET', '/transactions/' + self.tid)
                self.assertEqual(self.rows(), before)

    def test_api_logs_operation_without_ids_queries_or_credentials(self):
        response = Mock(status_code=403)
        response.json.return_value = {'error': {'code': 'forbidden', 'detail': 'PRIVATE-DETAIL'},
                                      'meta': {'request_id': 'request-example'}}
        output = io.StringIO()
        with patch('requests.request', return_value=response), redirect_stdout(output):
            with self.assertRaises(PaddleAPIError):
                self.paddle.api('PATCH', '/transactions/PRIVATE-TXN?customer=PRIVATE-EMAIL',
                                {'secret': 'PRIVATE-BODY'})
        log = output.getvalue()
        self.assertIn('operation=PATCH resource=transactions status=403', log)
        self.assertIn('request_id=request-example', log)
        for secret in ('PRIVATE-', self.paddle.key, self.paddle.secret):
            self.assertNotIn(secret, log)


if __name__ == '__main__':
    unittest.main()
