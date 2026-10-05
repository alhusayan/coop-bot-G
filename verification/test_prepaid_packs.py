"""Offline purchase integration tests: temporary SQLite, mocked providers only."""
import asyncio, copy, json, tempfile, time, unittest, uuid
from pathlib import Path
from unittest.mock import patch
from fastapi import HTTPException
from findzia_accounts import Accounts
from findzia_billing import Credits
from findzia_plans import BY_ID, PREPAID_PLANS
from findzia_paddle import PaddleSandbox
from findzia_myfatoorah import MyFatoorahPack
from findzia_applepay import ApplePayWindow


class PrepaidTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.net=patch('requests.request',side_effect=AssertionError('No external calls allowed'))
        self.net.start();self.addCleanup(self.net.stop)
        self.accounts=Accounts({'FINDZIA_ACCOUNT_DB':str(Path(self.tmp.name)/'db.sqlite'),
                               'FINDZIA_ACCOUNT_API_URL':'https://api.findzia.com'})
        self.assertTrue(self.accounts.available)
        self.credits=Credits(self.accounts,{'FINDZIA_PREPAID_PACKS_ENABLED':'true','FINDZIA_PAYMENT_PROVIDER':'paddle'})
        self.addCleanup(lambda:asyncio.run(self.credits.runtime.close()))
        self.member={'id':'m1','email':'fixture@example.test'}
        with self.accounts.connect() as db:
            db.execute('INSERT INTO fz_members(id,provider,subject,email,name,created) VALUES(?,?,?,?,?,?)',
                       ('m1','google','m1',self.member['email'],'Fixture',int(time.time())))
        self.paddle=PaddleSandbox(self.credits,{'FINDZIA_PADDLE_ENV':'sandbox','FINDZIA_PADDLE_API_KEY':'pdl_sdbx_apikey_fixture',
            'FINDZIA_PADDLE_WEBHOOK_SECRET':'fixture','FINDZIA_PADDLE_TEST_EMAILS':self.member['email'],
            'FINDZIA_PADDLE_SANDBOX_PACK50_PRICE_ID':'pri_'+'a'*26,'FINDZIA_PADDLE_SANDBOX_PACK100_PRICE_ID':'pri_'+'b'*26})
        self.mf_env={'FINDZIA_MYFATOORAH_ENABLED':'true','FINDZIA_MYFATOORAH_ENV':'sandbox',
            'FINDZIA_MYFATOORAH_TEST_API_KEY':'fixture','FINDZIA_MYFATOORAH_WEBHOOK_SECRET':'fixture',
            'FINDZIA_MYFATOORAH_EMBEDDED_ENABLED':'true','FINDZIA_MYFATOORAH_TEST_EMAILS':self.member['email']}
        self.mf=MyFatoorahPack(self.credits,self.mf_env)

    def balance(self):return self.credits.status('m1')['remaining']
    def error(self,code,call):
        with self.assertRaises(HTTPException) as cm:call()
        self.assertEqual(cm.exception.detail,code)

    def paddle_txn(self,plan_id,tid=None):
        p=BY_ID[plan_id];now=int(time.time());tid=tid or 'txn_'+uuid.uuid4().hex[:26]
        with self.accounts.connect() as db:
            db.execute(f'INSERT INTO {self.paddle.prefix}checkout VALUES(?,?,?,?,?,?)',
                (uuid.uuid4().hex,'m1',plan_id,tid,now,'pending'))
        txn={'id':tid,'status':'completed','currency_code':'USD','origin':'api','collection_mode':'automatic',
            'items':[{'quantity':1,'price':{'id':self.paddle.prices[plan_id],'unit_price':{'amount':str(p['amount_cents']),'currency_code':'USD'},
                      'billing_cycle':None if p['interval']=='once' else {'interval':'month','frequency':1}}}],
            'details':{'totals':{'grand_total':str(p['amount_cents']),'balance':'0','discount':'0','total':str(p['amount_cents']),'tax':'0'}},'adjustments':[]}
        if p['interval']=='month':
            from datetime import datetime,timezone
            fmt=lambda ts:datetime.fromtimestamp(ts,timezone.utc).isoformat()
            txn.update(subscription_id='sub_'+'a'*26,customer_id='ctm_'+'a'*26,
                       billing_period={'starts_at':fmt(now),'ends_at':fmt(now+86400*30)})
        self.paddle.api=lambda *args,**kw:copy.deepcopy(txn)
        return txn

    def mf_paid(self,plan_id,invoice='101'):
        intent='fz_'+uuid.uuid4().hex;p=BY_ID[plan_id]
        with self.accounts.connect() as db:
            db.execute('INSERT INTO fz_mf_orders(intent,member,mode,invoice,state,created,plan) VALUES(?,?,?,?,?,?,?)',
                       (intent,'m1','sandbox',invoice,'pending',int(time.time()),plan_id))
        data={'Invoice':{'Id':invoice,'Status':'PAID'},'Transaction':{'PaymentId':'payment1','Status':'SUCCESS'},
              'Amount':{'DisplayCurrency':'USD','ValueInDisplayCurrency':p['amount_cents']/100,
                        'PayCurrency':'USD','ValueInPayCurrency':p['amount_cents']/100}}
        self.mf.api=lambda *args,**kw:copy.deepcopy(data)
        return data

    def test_catalog_is_three_one_time_packs(self):
        c=self.credits.public_config();self.assertEqual(c['trial_credits'],10)
        self.assertEqual([(p['credits'],p['amount_cents'],p['interval']) for p in c['plans']],[(20,499,'once'),(50,999,'once'),(100,1799,'once')])
        self.assertEqual([p['id'] for p in c['plans'] if p.get('recommended')],['pack50'])

    def test_staging_flag_preserves_old_catalog(self):
        other=Credits(self.accounts,{});self.addCleanup(lambda:asyncio.run(other.runtime.close()))
        self.assertEqual([p['id'] for p in other.public_config()['plans']],['pack','plus','pro'])

    def test_all_paddle_packs_verified_once_and_no_expiry(self):
        for plan in PREPAID_PLANS:
            txn=self.paddle_txn(plan['id']);self.assertTrue(self.paddle.reconcile_transaction(txn['id']))
            self.assertTrue(self.paddle.reconcile_transaction(txn['id']))
        self.assertEqual(self.balance(),170)
        with self.accounts.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM fz_credit_grants WHERE expires IS NULL AND kind=\'pack\'').fetchone()[0],3)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM fz_subscriptions').fetchone()[0],0)

    def test_all_mf_packs_verified_once_and_no_expiry(self):
        for n,plan in enumerate(PREPAID_PLANS):
            invoice=str(100+n);self.mf_paid(plan['id'],invoice)
            self.assertTrue(self.mf.verify('payment1',invoice,'m1'));self.assertTrue(self.mf.verify('payment1',invoice,'m1'))
        self.assertEqual(self.balance(),170)
        with self.accounts.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM fz_credit_grants WHERE expires IS NULL').fetchone()[0],3)

    def test_quantity_is_finite_not_unlimited(self):
        txn=self.paddle_txn('pack50');self.paddle.reconcile_transaction(txn['id'])
        for n in range(50):
            rid=uuid.uuid4().hex;self.credits.reserve('m1',rid,'/api/search/stream');self.credits.finish('m1',rid,True)
        self.assertEqual(self.balance(),0)
        self.error('credits_exhausted',lambda:self.credits.reserve('m1',uuid.uuid4().hex,'/api/search/stream'))

    def test_legacy_plus_renewal_still_verified(self):
        txn=self.paddle_txn('plus');self.assertTrue(self.paddle.reconcile_transaction(txn['id']))
        self.assertEqual(self.balance(),40)
        self.assertIsNotNone(self.credits.status('m1')['subscription'])

    def test_new_subscription_purchase_not_offered(self):
        self.error('invalid_plan',lambda:self.paddle.checkout(self.member,'plus'))
        self.error('invalid_plan',lambda:self.paddle.checkout(self.member,'pro'))

    def test_wrong_paddle_amount_currency_cycle_or_quantity_rejected(self):
        for field,value in [('amount','499'),('currency','EUR'),('cycle',{'interval':'month','frequency':1}),('quantity',2)]:
            with self.subTest(field=field):
                txn=self.paddle_txn('pack100');item=txn['items'][0]
                if field=='amount':item['price']['unit_price']['amount']=value
                elif field=='currency':item['price']['unit_price']['currency_code']=value
                elif field=='cycle':item['price']['billing_cycle']=value
                else:item['quantity']=value
                with self.assertRaises(ValueError):self.paddle.reconcile_transaction(txn['id'])
        self.assertEqual(self.balance(),0)

    def test_refund_before_or_after_payment_does_not_regrant(self):
        txn=self.paddle_txn('pack50');self.paddle.reconcile_transaction(txn['id'])
        txn['adjustments']=[{'status':'approved','action':'refund','items':[{'type':'full'}]}]
        self.assertFalse(self.paddle.reconcile_transaction(txn['id']));self.assertEqual(self.balance(),0)
        txn['adjustments']=[];self.paddle.reconcile_transaction(txn['id']);self.assertEqual(self.balance(),0)
        txn2=self.paddle_txn('pack100');txn2['adjustments']=[{'status':'approved','action':'refund','items':[]}]
        self.assertFalse(self.paddle.reconcile_transaction(txn2['id']));self.assertEqual(self.balance(),0)

    def test_mf_wrong_amount_owner_or_pending_never_grants(self):
        data=self.mf_paid('pack100')
        self.error('payment_not_found',lambda:self.mf.verify('payment1','101','someone_else'))
        data['Amount']['ValueInDisplayCurrency']=4.99
        self.error('payment_currency_or_amount_mismatch',lambda:self.mf.verify('payment1','101','m1'))
        data['Invoice']['Status']='PENDING';self.assertFalse(self.mf.verify('payment1','101','m1'))
        self.assertEqual(self.balance(),0)

    def test_mf_kwd_settlement_and_refund_tombstone(self):
        data=self.mf_paid('pack50');data['Amount'].update(PayCurrency='KWD',BaseCurrency='KWD',ValueInPayCurrency=3.07,ValueInBaseCurrency=3.07)
        self.assertTrue(self.mf.verify('payment1','101','m1'));self.assertEqual(self.balance(),50)
        self.mf_paid('pack100','102')
        with self.accounts.connect() as db:db.execute('INSERT INTO fz_mf_refunds VALUES(?,?)',('sandbox','102'))
        self.assertFalse(self.mf.verify('payment1','102','m1'));self.assertEqual(self.balance(),50)

    def test_paddle_new_price_checked_before_transaction(self):
        calls=[]
        def api(method,path,body=None,**kw):
            calls.append((method,path,body))
            if path.startswith('/prices/'):
                return {'id':self.paddle.prices['pack50'],'status':'active','billing_cycle':None,'trial_period':None,'unit_price':{'currency_code':'USD','amount':'999'}}
            return {'id':'txn_'+'z'*26}
        self.paddle.api=api;out=self.paddle.checkout(self.member,'pack50')
        self.assertTrue(out['transaction_id'].startswith('txn_'))
        self.assertEqual(calls[-1][2]['items'],[{'price_id':self.paddle.prices['pack50'],'quantity':1}])

    def test_recurring_price_misconfiguration_cannot_charge(self):
        calls=[]
        def api(method,path,body=None,**kw):
            calls.append(method)
            return {'id':self.paddle.prices['pack50'],'status':'active','billing_cycle':{'interval':'month','frequency':1},'unit_price':{'currency_code':'USD','amount':'999'}}
        self.paddle.api=api;self.error('paddle_checkout_rejected',lambda:self.paddle.checkout(self.member,'pack50'))
        self.assertEqual(calls,['GET']);self.assertEqual(self.balance(),0)

    def test_paddle_double_click_reuses_one_transaction(self):
        calls=[];intent='';tid='txn_'+'z'*26
        def api(method,path,body=None,**kw):
            nonlocal intent
            calls.append((method,path))
            if path.startswith('/prices/'):return {'id':self.paddle.prices['pack50'],'status':'active','billing_cycle':None,'unit_price':{'currency_code':'USD','amount':'999'}}
            if method=='POST':intent=body['custom_data']['findzia_intent'];return {'id':tid}
            return {'id':tid,'status':'ready','origin':'api','collection_mode':'automatic','currency_code':'USD','custom_data':{'findzia_intent':intent},'items':[{'quantity':1,'price':{'id':self.paddle.prices['pack50']}}],'payments':[]}
        self.paddle.api=api
        a=self.paddle.checkout(self.member,'pack50');b=self.paddle.checkout(self.member,'pack50')
        self.assertEqual(a,b);self.assertEqual(sum(m=='POST' for m,p in calls),1)

    def test_price_lookup_timeout_does_not_create_pending_purchase(self):
        self.paddle.api=lambda *a,**kw:(_ for _ in ()).throw(RuntimeError('paddle_unavailable'))
        self.error('paddle_configuration_invalid',lambda:self.paddle.checkout(self.member,'pack50'))
        with self.accounts.connect() as db:
            self.assertEqual(db.execute(f'SELECT COUNT(*) FROM {self.paddle.prefix}checkout').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM fz_checkout_creation_lock').fetchone()[0],0)

    def test_resumed_mf_payment_reports_its_original_pack(self):
        self.credits.payment_provider='myfatoorah'
        self.mf_paid('pack50')
        self.mf.invoice_snapshot=lambda invoice:{'Invoice':{'Id':invoice,'Status':'PENDING'},'Transactions':[{'Status':'IN_PROGRESS','PaymentId':'payment1'}]}
        result=self.mf.embedded_session(self.member,'pack100')
        self.assertTrue(result['payment_pending'])
        self.assertEqual((result['plan_id'],result['credits'],result['amount_cents']),('pack50',50,999))

    def test_mf_selected_amount_session_reuse_and_switch(self):
        self.credits.payment_provider='myfatoorah';calls=[]
        def api(method,path,body=None,intent=None):
            self.assertEqual(path,'/v3/sessions');calls.append(body)
            return {'SessionId':'session'+str(len(calls)),'Order':body['Order']}
        self.mf.api=api
        a=self.mf.embedded_session(self.member,'pack50');b=self.mf.embedded_session(self.member,'pack50')
        self.assertEqual(a,b);self.assertEqual(len(calls),1);self.assertEqual(calls[0]['Order']['Amount'],9.99)
        c=self.mf.embedded_session(self.member,'pack100');self.assertNotEqual(c['intent'],a['intent'])
        self.assertEqual(calls[1]['Order']['Amount'],17.99)
        self.error('payment_creation_pending',lambda:self.mf.complete_session(self.member,a['intent']))

    def test_mf_completion_uses_persisted_plan_and_double_click_cannot_recharge(self):
        self.credits.payment_provider='myfatoorah';charges=[]
        def api(method,path,body=None,intent=None):
            if path=='/v3/sessions':return {'SessionId':'session1','Order':body['Order']}
            if method=='POST' and path=='/v3/payments':
                charges.append(body);return {'InvoiceId':111,'PaymentId':'payment1','PaymentCompleted':False}
            raise AssertionError(path)
        self.mf.api=api;out=self.mf.embedded_session(self.member,'pack100')
        self.mf.complete_session(self.member,out['intent']);self.mf.complete_session(self.member,out['intent'])
        self.assertEqual(len(charges),1);self.assertEqual(charges[0]['Order']['Amount'],17.99)

    def test_pending_paddle_still_blocks_switch_to_myfatoorah(self):
        self.paddle_txn('pack100');self.credits.payment_provider='myfatoorah'
        self.error('other_payment_pending',lambda:self.mf.embedded_session(self.member,'pack50'))

    def test_unused_mf_form_can_be_safely_retired_for_paddle(self):
        with self.accounts.connect() as db:
            db.execute("INSERT INTO fz_mf_orders(intent,member,mode,state,created,plan) VALUES('unused','m1','sandbox','session_ready',?,'pack50')",(int(time.time()),))
        self.paddle.api=lambda *a,**kw:{'id':'txn_'+'c'*26}
        self.paddle.checkout(self.member,'pack')
        with self.accounts.connect() as db:self.assertEqual(db.execute("SELECT state FROM fz_mf_orders WHERE intent='unused'").fetchone()[0],'canceled')

    def test_creation_lock_is_shared_across_providers(self):
        with self.accounts.connect() as db:db.execute('INSERT INTO fz_checkout_creation_lock VALUES(?,?,?)',('m1','otherworker',int(time.time())+30))
        self.error('payment_creation_pending',lambda:self.paddle.checkout(self.member,'pack50'))
        self.credits.payment_provider='myfatoorah'
        self.error('payment_creation_pending',lambda:self.mf.embedded_session(self.member,'pack100'))

    def test_provider_setting_does_not_silently_fall_back(self):
        self.error('payment_provider_changed',lambda:self.mf.embedded_session(self.member,'pack50'))

    def test_existing_mf_schema_migrates_without_changing_credits(self):
        with self.accounts.connect() as db:
            db.execute('DROP TABLE fz_mf_orders')
            db.execute('CREATE TABLE fz_mf_orders(intent TEXT PRIMARY KEY,member TEXT NOT NULL,mode TEXT NOT NULL,invoice TEXT,url TEXT,state TEXT NOT NULL,created INTEGER NOT NULL,checked INTEGER NOT NULL DEFAULT 0,UNIQUE(mode,invoice))')
            db.execute("INSERT INTO fz_mf_orders(intent,member,mode,invoice,state,created) VALUES('legacy','m1','sandbox','101','pending',?)",(int(time.time()),))
        new=MyFatoorahPack(self.credits,self.mf_env)
        again=MyFatoorahPack(self.credits,self.mf_env)
        with self.accounts.connect() as db:self.assertEqual(db.execute("SELECT plan FROM fz_mf_orders WHERE intent='legacy'").fetchone()[0],'pack')
        self.assertEqual(self.balance(),0)

    def test_apple_pay_window_keeps_selected_plan(self):
        self.credits.payment_provider='myfatoorah'
        self.mf.api=lambda method,path,body=None,intent=None:{'SessionId':uuid.uuid4().hex,'Order':body['Order']}
        original=self.mf.embedded_session(self.member,'pack100')
        bridge=ApplePayWindow(self.mf,{'RAILWAY_PUBLIC_DOMAIN':'api.findzia.com'})
        bridge.ready=True
        out=bridge.open(self.member,original['intent'],'ar','dark')
        token=out['url'].split('#')[1];ticket,member=bridge.ticket(token);session=bridge.session(ticket)
        self.assertEqual((session['credits'],session['amount_cents']),(100,1799))


if __name__=='__main__':unittest.main(verbosity=2)
