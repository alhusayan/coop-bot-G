"""156.7.56: merchant-approved separate Paddle purchase; mocked payments only."""
import base64
import copy
import hashlib
import hmac
import json
import time
import unittest
from unittest.mock import patch
import test_prepaid_packs as fixtures
from findzia_myfatoorah import FIELDS, scalar


class IndependentPaymentTests(unittest.TestCase):
    setUp = fixtures.PrepaidTests.setUp
    balance = fixtures.PrepaidTests.balance
    error = fixtures.PrepaidTests.error
    mf_paid = fixtures.PrepaidTests.mf_paid
    paddle_txn = fixtures.PrepaidTests.paddle_txn

    def order(self):
        with self.accounts.connect() as db:
            return dict(db.execute("SELECT * FROM fz_mf_orders WHERE invoice='101'").fetchone())

    def paddle_api(self):
        tid = 'txn_' + 'z' * 26
        txn = {'id': tid, 'status': 'ready', 'origin': 'api', 'collection_mode': 'automatic',
               'currency_code': 'USD', 'payments': [], 'adjustments': [],
               'items': [{'quantity': 1, 'price': {'id': self.paddle.prices['pack50'],
                   'billing_cycle': None, 'unit_price': {'currency_code': 'USD', 'amount': '999'}}}],
               'details': {'totals': {'grand_total': '999', 'balance': '0', 'discount': '0', 'total': '999', 'tax': '0'}}}
        calls = []
        def api(method, path, body=None, **kwargs):
            calls.append((method, path))
            if path.startswith('/prices/'):
                return {'id': self.paddle.prices['pack50'], 'status': 'active',
                        'billing_cycle': None, 'unit_price': {'currency_code': 'USD', 'amount': '999'}}
            if method == 'POST':
                self.assertEqual(path, '/transactions')
                txn['custom_data'] = body['custom_data']
                return {'id': tid}
            self.assertEqual(method, 'GET')
            self.assertIn(path, ['/transactions/' + tid, '/transactions/' + tid + '?include=adjustments'])
            return copy.deepcopy(txn)
        self.paddle.api = api
        return calls, txn

    def disable_mf_sales(self):
        self.mf.ready = self.mf.enabled = False

    def webhook(self, name='PAYMENT_STATUS_CHANGED', signature=None):
        if name == 'PAYMENT_STATUS_CHANGED':
            data = {'Invoice': {'Id': 101, 'Status': 'PAID', 'ExternalIdentifier': 'fixture'},
                    'Transaction': {'Status': 'SUCCESS', 'PaymentId': 'payment1'}}
        else:
            data = {'Refund': {'Id': 'refund1', 'Status': 'REFUNDED'},
                    'Amount': {'ValueInBaseCurrency': '9.99'}, 'ReferencedInvoice': {'Id': 101}}
        signed = ','.join(key + '=' + scalar(data, key) for key in FIELDS[name])
        signature = signature or base64.b64encode(hmac.new(self.mf.secret.encode(), signed.encode(), hashlib.sha256).digest()).decode()
        self.mf.receive(json.dumps({'Event': {'Name': name}, 'Data': data}).encode(), signature)

    def test_pending_mf_states_do_not_block_or_call_myfatoorah(self):
        for state in ['creating', 'pending', 'session_processing', 'abandoned']:
            with self.subTest(state=state):
                with self.accounts.connect() as db:
                    db.execute('DELETE FROM fz_mf_orders')
                    db.execute(f'DELETE FROM {self.paddle.prefix}checkout')
                self.mf_paid('pack50')
                with self.accounts.connect() as db:
                    db.execute('UPDATE fz_mf_orders SET state=?', (state,))
                before = self.order()
                calls, txn = self.paddle_api()
                with patch.object(self.mf, 'api', side_effect=AssertionError('Paddle must not wait for MF')):
                    with patch.object(self.mf, 'review_before_switch', side_effect=AssertionError('No cross-provider review')):
                        self.assertEqual(self.paddle.checkout(self.member, 'pack50')['transaction_id'], txn['id'])
                self.assertEqual(self.order(), before)
                self.assertEqual(sum(method == 'POST' for method, _ in calls), 1)
                self.assertEqual(self.balance(), 0)

    def test_no_mf_credentials_or_registered_peer_cannot_block_paddle(self):
        self.mf_paid('pack50'); self.mf.key = self.mf.secret = ''
        self.credits._payment_gateways.pop(self.mf.provider)
        self.paddle_api()
        self.assertIn('transaction_id', self.paddle.checkout(self.member, 'pack50'))
        self.assertEqual(self.order()['state'], 'pending')

    def test_paddle_double_click_reuses_same_transaction_with_pending_mf(self):
        self.mf_paid('pack50'); calls, txn = self.paddle_api()
        first = self.paddle.checkout(self.member, 'pack50')
        second = self.paddle.checkout(self.member, 'pack50')
        self.assertEqual(first, second)
        self.assertEqual(sum(method == 'POST' for method, _ in calls), 1)

    def test_paddle_inflight_payment_is_not_ignored(self):
        self.mf_paid('pack50'); calls, txn = self.paddle_api()
        self.paddle.checkout(self.member, 'pack50')
        txn.update(status='paid')
        self.assertTrue(self.paddle.checkout(self.member, 'pack100')['payment_pending'])
        self.assertEqual(sum(method == 'POST' for method, _ in calls), 1)

    def test_real_old_and_new_payments_both_credit_once(self):
        self.mf_paid('pack50'); self.disable_mf_sales(); calls, txn = self.paddle_api()
        self.paddle.checkout(self.member, 'pack50')
        self.webhook(); self.webhook(); self.mf.process_jobs(); self.mf.process_jobs()
        self.assertEqual(self.balance(), 50)
        txn['status'] = 'completed'
        self.assertTrue(self.paddle.reconcile_transaction(txn['id']))
        self.assertTrue(self.paddle.reconcile_transaction(txn['id']))
        self.assertEqual(self.balance(), 100)
        self.assertEqual(self.order()['state'], 'paid')

    def test_disabled_mf_sales_still_verify_signed_late_payment(self):
        self.mf_paid('pack50'); self.disable_mf_sales()
        self.assertTrue(self.mf.can_reconcile())
        self.assertFalse(self.mf.public(self.member)['checkout_available'])
        self.webhook(); self.mf.process_jobs()
        self.assertEqual(self.balance(), 50)
        self.error('myfatoorah_not_available', lambda: self.mf.embedded_session(self.member, 'pack50'))

    def test_invalid_signature_never_enqueues_or_grants_credit(self):
        self.mf_paid('pack50'); self.disable_mf_sales()
        self.error('invalid_webhook', lambda: self.webhook(signature='invalid-signature'))
        with self.accounts.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM fz_mf_jobs').fetchone()[0], 0)
        self.assertEqual(self.balance(), 0)

    def test_missing_secret_keeps_webhook_closed(self):
        self.mf_paid('pack50'); self.mf.secret = ''
        self.assertFalse(self.mf.can_reconcile())
        self.error('myfatoorah_not_ready', lambda: self.webhook(signature='invalid'))

    def test_amount_mismatch_on_late_payment_never_grants(self):
        data = self.mf_paid('pack50'); self.disable_mf_sales()
        data['Amount']['ValueInDisplayCurrency'] = 4.99
        self.webhook(); self.mf.process_jobs()
        self.assertEqual(self.balance(), 0)
        self.assertEqual(self.order()['state'], 'pending')

    def test_refund_before_late_payment_prevents_credit(self):
        self.mf_paid('pack50'); self.disable_mf_sales()
        self.webhook('REFUND_STATUS_CHANGED')
        self.webhook(); self.mf.process_jobs()
        self.assertEqual(self.balance(), 0)
        self.assertEqual(self.order()['state'], 'refunded')

    def test_late_refund_revokes_existing_mf_credit_with_sales_disabled(self):
        self.mf_paid('pack50'); self.disable_mf_sales()
        self.webhook(); self.mf.process_jobs()
        self.assertEqual(self.balance(), 50)
        self.webhook('REFUND_STATUS_CHANGED'); self.webhook('REFUND_STATUS_CHANGED')
        self.assertEqual(self.balance(), 0)

    def test_restore_keeps_pending_fact_but_does_not_block_paddle(self):
        self.mf_paid('pack50')
        self.mf.invoice_snapshot = lambda invoice: {'Invoice': {'Id': invoice, 'Status': 'PENDING'},
            'Transactions': [{'Status': 'INPROGRESS', 'PaymentId': 'payment1'}]}
        result = self.mf.restore(self.member)
        self.assertTrue(result['payment_pending']); self.assertFalse(result['blocks_checkout'])
        self.credits.payment_provider = 'myfatoorah'
        self.assertTrue(self.mf.restore(self.member)['blocks_checkout'])

    def test_paid_restore_without_webhook_still_grants_once(self):
        self.mf_paid('pack50'); self.disable_mf_sales()
        self.mf.invoice_snapshot = lambda invoice: {'Invoice': {'Id': invoice, 'Status': 'PAID'},
            'Transactions': [{'Status': 'SUCCESS', 'PaymentId': 'payment1'}]}
        self.assertTrue(self.mf.restore(self.member)['confirmed'])
        self.mf.restore(self.member)
        self.assertEqual(self.balance(), 50)

    def test_background_review_continues_without_new_mf_sales(self):
        self.mf_paid('pack50'); self.disable_mf_sales()
        with self.accounts.connect() as db:
            intent = db.execute('SELECT intent FROM fz_mf_orders').fetchone()[0]
            db.execute('INSERT INTO fz_mf_reviews(intent,requested) VALUES(?,?)', (intent, int(time.time())))
        self.mf.invoice_snapshot = lambda invoice: {'Invoice': {'Id': invoice, 'Status': 'PAID'},
            'Transactions': [{'Status': 'SUCCESS', 'PaymentId': 'payment1'}]}
        self.mf.process_reviews()
        self.assertEqual(self.balance(), 50)


if __name__ == '__main__':
    unittest.main()
