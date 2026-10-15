import asyncio
import tempfile
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from fastapi import HTTPException
from findzia_accounts import Accounts
from findzia_billing import Credits
from findzia_apple import ApplePurchases, BUNDLE_ID

class AppleCredits(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Accounts({'FINDZIA_ACCOUNT_DB':str(Path(self.tmp.name)/'db'),'FINDZIA_ACCOUNT_API_URL':'https://api.findzia.com'})
        self.c=Credits(self.a,{'FINDZIA_SPACES_PRICING_ENABLED':'true'})
        self.addCleanup(lambda:asyncio.run(self.c.runtime.close()))
        self.member='member-apple';self.other='member-google'
        with self.a.connect() as db:
            for m in (self.member,self.other):
                db.execute('INSERT INTO fz_members(id,provider,subject,email,name,created) VALUES(?,?,?,?,?,?)',(m,'apple',m,'','Customer',int(time.time())))
        self.service=ApplePurchases(self.c,{'FINDZIA_IAP_ENABLED':'true','FINDZIA_IAP_APP_APPLE_ID':'1234567890'})
        self.token=self.service.context(self.member)['app_account_token']
    def txn(self,**kw):
        return SimpleNamespace(**(dict(bundleId=BUNDLE_ID,environment='Production',transactionId='10000000001',
            productId='com.findzia.spaces.credits30',type='Consumable',quantity=1,inAppOwnershipType='PURCHASED',
            purchaseDate=int(time.time()*1000),appAccountToken=self.token,revocationDate=None)|kw))
    def paid(self):return self.c.status(self.member)['paid_remaining']
    def reject(self,txn,code=400,member=None):
        with self.assertRaises(HTTPException) as e:self.service.apply(txn,expected_member=member or self.member)
        self.assertEqual(e.exception.status_code,code)
    def test_real_verifier_rejects_forged_signature(self):
        import base64,json
        def b(x):return base64.urlsafe_b64encode(json.dumps(x).encode()).decode().rstrip('=')
        fake=b({'alg':'none'})+'.'+b({'bundleId':BUNDLE_ID,'environment':'Production','productId':'com.findzia.spaces.credits30','appAccountToken':self.token})+'.'
        with self.assertRaises(HTTPException):self.service.deliver(self.member,fake)
        self.assertEqual(self.paid(),0)
    def test_retries_and_parallel_delivery_grant_once(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            result=list(pool.map(lambda _:self.service.apply(self.txn(),expected_member=self.member),range(16)))
        self.assertEqual(result.count('credited'),1);self.assertEqual(self.paid(),30)
        with self.a.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM fz_credit_ledger WHERE reason='apple_verified_purchase'").fetchone()[0],1)
            self.assertIsNone(db.execute('SELECT expires FROM fz_credit_grants').fetchone()[0])
    def test_all_three_packs(self):
        for i,n in enumerate((30,80,180)):
            self.service.apply(self.txn(transactionId=str(101+i),productId=f'com.findzia.spaces.credits{n}'),expected_member=self.member)
        self.assertEqual(self.paid(),290)
    def test_product_bundle_type_quantity_and_owner_are_checked(self):
        for values in [dict(productId='invented'),dict(bundleId='evil.bundle'),dict(type='Auto-Renewable Subscription'),dict(quantity=2),dict(inAppOwnershipType='FAMILY_SHARED'),dict(appAccountToken='not-uuid'),dict(transactionId='../bad'),dict(purchaseDate=int((time.time()+600)*1000))]:
            self.reject(self.txn(**values))
        self.reject(self.txn(),409,member=self.other);self.assertEqual(self.paid(),0)
    def test_sandbox_is_denied_without_explicit_member_allowlist(self):
        self.reject(self.txn(environment='Sandbox'),403)
        self.service.test_members.add(self.member)
        self.assertEqual(self.service.apply(self.txn(environment='Sandbox'),expected_member=self.member),'credited')
        self.assertEqual(self.paid(),30)
    def test_refund_before_purchase_blocks_all_replays(self):
        self.service.apply(self.txn(),revoke=True)
        self.assertEqual(self.service.apply(self.txn(),expected_member=self.member),'revoked')
        self.assertEqual(self.paid(),0)
    def test_refund_revokes_remaining_and_duplicate_refund_is_noop(self):
        self.service.apply(self.txn(),expected_member=self.member)
        rid=uuid.uuid4().hex
        self.c.space_policy.reserve(self.member,[rid],'/internal/spaces/design');self.c.finish(self.member,rid,True)
        self.assertEqual(self.paid(),29)
        for _ in range(3):self.service.apply(self.txn(),revoke=True)
        self.assertEqual(self.paid(),0)
        with self.a.connect() as db:self.assertEqual(db.execute("SELECT delta FROM fz_credit_ledger WHERE reason='apple_refund'").fetchall()[0][0],-29)
    def test_refund_cannot_race_late_delivery(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda revoke:self.service.apply(self.txn(),expected_member=self.member,revoke=revoke),(False,True)))
        self.assertEqual(self.paid(),0)
        self.assertEqual(self.service.apply(self.txn()),'revoked')
    def test_configuration_is_closed_by_default_and_tokens_are_stable(self):
        closed=ApplePurchases(self.c,{})
        self.assertFalse(closed.context(self.member)['enabled'])
        self.assertEqual(self.service.context(self.member)['app_account_token'],self.token)
        self.assertNotEqual(self.service.context(self.other)['app_account_token'],self.token)
    def test_signed_refund_notification_uses_verified_nested_transaction(self):
        notification=SimpleNamespace(notificationType='REFUND',data=SimpleNamespace(environment='Production',signedTransactionInfo='nested'))
        self.service.verify=Mock(side_effect=[notification,self.txn()])
        self.assertTrue(self.service.notification('outer')['ok'])
        self.assertEqual(self.service.apply(self.txn()),'revoked')
        self.assertEqual(self.service.verify.call_args_list[0].kwargs,{'notification':True})
    def test_http_routes_require_origin_and_authenticated_account(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from findzia_apple import install_apple
        from findzia_accounts import digest
        from unittest.mock import patch
        token='test-session-token'
        with self.a.connect() as db:
            db.execute('INSERT INTO fz_sessions VALUES(?,?,?)',(digest(token),self.member,int(time.time())+3600))
        app=FastAPI()
        with patch.dict('os.environ',{'FINDZIA_IAP_APP_APPLE_ID':'1234567890','FINDZIA_IAP_ENABLED':'true'}):
            install_apple(app,self.c)
        with TestClient(app) as client:
            url='/api/billing/apple/context'
            self.assertEqual(client.post(url,json={}).status_code,403)
            self.assertEqual(client.post(url,json={},headers={'Origin':'https://findzia.com'}).status_code,401)
            headers={'Origin':'https://findzia.com','Authorization':'Bearer '+token}
            response=client.post(url,json={},headers=headers)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['app_account_token'],self.token)
            bad=client.post('/api/billing/apple/transactions',json={'signed_transaction':'forged'},headers=headers)
            self.assertEqual(bad.status_code,400)
            huge=client.post('/api/billing/apple/transactions',content='x'*70000,headers=headers)
            self.assertEqual(huge.status_code,413)
            self.assertEqual(self.paid(),0)

    def test_existing_transaction_cannot_change_pack(self):
        self.service.apply(self.txn())
        self.reject(self.txn(productId='com.findzia.spaces.credits180'),409)
        self.assertEqual(self.paid(),30)

if __name__=='__main__':unittest.main()
