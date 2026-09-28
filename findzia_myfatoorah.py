"""Findzia 156.4.6: MyFatoorah V3 hosted Pack checkout (Kuwait).
Disabled by default. Sandbox uses a separate key and an explicit email allowlist.
No card data, browser prices, or redirect claims are accepted as payment proof.
"""
import asyncio
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

import requests
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

FIELDS = {
    'PAYMENT_STATUS_CHANGED': ('Invoice.Id','Invoice.Status','Transaction.Status','Transaction.PaymentId','Invoice.ExternalIdentifier'),
    'REFUND_STATUS_CHANGED': ('Refund.Id','Refund.Status','Amount.ValueInBaseCurrency','ReferencedInvoice.Id'),
}

def scalar(data, path):
    for key in path.split('.'):
        data = data.get(key) if isinstance(data, dict) else None
    if data is None: return ''
    if not isinstance(data, (str, int)): raise ValueError('invalid_field')
    return str(data)

def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value):
        raise HTTPException(400, 'invalid_payment_id')
    return value

class MyFatoorahPack:
    def __init__(self, credits, env=None):
        env = os.environ if env is None else env
        self.credits, self.accounts = credits, credits.accounts
        self.mode = env.get('FINDZIA_MYFATOORAH_ENV', 'sandbox')
        self.provider = 'myfatoorah_' + self.mode
        self.key = env.get('FINDZIA_MYFATOORAH_TEST_API_KEY' if self.mode == 'sandbox' else 'FINDZIA_MYFATOORAH_API_KEY', '').strip()
        self.secret = env.get('FINDZIA_MYFATOORAH_WEBHOOK_SECRET', '').strip()
        self.return_url = env.get('FINDZIA_MYFATOORAH_RETURN_URL', 'https://findzia.com/').strip()
        origin = urlsplit(self.return_url)
        self.test_emails = {x.strip().lower() for x in env.get('FINDZIA_MYFATOORAH_TEST_EMAILS','').split(',') if x.strip()}
        self.live_open = env.get('FINDZIA_MYFATOORAH_LIVE_OPEN','false').lower() == 'true'
        self.enabled = env.get('FINDZIA_MYFATOORAH_ENABLED', 'false').lower() == 'true'
        self.ready = bool(self.enabled and credits.available and self.key and self.secret
            and self.mode in ('sandbox','live') and origin.scheme == 'https'
            and origin.hostname in ('findzia.com','www.findzia.com')
            and not origin.query and not origin.fragment and not origin.username and not origin.port
            and (self.mode == 'live' or self.test_emails))
        self.base = 'https://apitest.myfatoorah.com' if self.mode == 'sandbox' else 'https://api.myfatoorah.com'
        self.task = None
        if credits.available:
            with self.accounts.connect() as db:
                db.executescript('''
                CREATE TABLE IF NOT EXISTS fz_mf_orders(
                  intent TEXT PRIMARY KEY, member TEXT NOT NULL, mode TEXT NOT NULL,
                  invoice TEXT, url TEXT, state TEXT NOT NULL, created INTEGER NOT NULL,
                  checked INTEGER NOT NULL DEFAULT 0, UNIQUE(mode,invoice));
                CREATE INDEX IF NOT EXISTS fz_mf_member ON fz_mf_orders(member,mode,created);
                CREATE TABLE IF NOT EXISTS fz_mf_jobs(
                  id TEXT PRIMARY KEY, mode TEXT NOT NULL, invoice TEXT NOT NULL,
                  payment TEXT NOT NULL, tries INTEGER NOT NULL DEFAULT 0,
                  next_try INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL DEFAULT 'pending');
                CREATE TABLE IF NOT EXISTS fz_mf_refunds(
                  mode TEXT NOT NULL, invoice TEXT NOT NULL, PRIMARY KEY(mode,invoice));
                ''')

    def allowed(self, member):
        return bool(self.ready and member and not member.get('guest') and
            ((self.mode == 'live' and self.live_open) or member.get('email','').lower() in self.test_emails))

    def require(self, member):
        if not self.allowed(member): raise HTTPException(403, 'myfatoorah_not_available')

    def public(self, member):
        return {'ok': True, 'enabled': self.enabled, 'environment': self.mode,
                'checkout_available': self.allowed(member), 'plan_id': 'pack'}

    def api(self, method, path, body=None, intent=None):
        headers = {'Authorization': 'Bearer ' + self.key, 'Content-Type':'application/json'}
        if intent: headers['Idempotency-Key'] = intent
        try:
            r = requests.request(method, self.base + path, headers=headers, json=body,
                                 timeout=(3,12), allow_redirects=False)
            if not 200 <= r.status_code < 300: raise RuntimeError('myfatoorah_api_unavailable')
            result = r.json()
            if result.get('IsSuccess') is not True or not isinstance(result.get('Data'),dict):
                raise RuntimeError('myfatoorah_api_unavailable')
            return result['Data']
        except (requests.RequestException, ValueError) as exc:
            raise RuntimeError('myfatoorah_api_unavailable') from exc

    def valid_url(self, url):
        p = urlsplit(url)
        hosts = {'demo.myfatoorah.com'} if self.mode == 'sandbox' else {'portal.myfatoorah.com','pay.myfatoorah.com','www.myfatoorah.com','myfatoorah.com'}
        if p.scheme != 'https' or p.hostname not in hosts or p.username or p.password or p.port:
            raise RuntimeError('invalid_checkout_url')
        return url

    def checkout(self, member, plan):
        self.require(member)
        if plan != 'pack': raise HTTPException(400, 'pack_only')
        now = int(time.time())
        with self.accounts.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT * FROM fz_mf_orders WHERE member=? AND mode=? AND state IN ('creating','pending') ORDER BY created DESC LIMIT 1", (member['id'],self.mode)).fetchone()
            if row and row['created'] > now-3600:
                if row['url']: return {'intent':row['intent'],'url':self.valid_url(row['url'])}
                # An ambiguous network response must never create a second invoice.
                raise HTTPException(409, 'payment_creation_pending')
            intent = 'fz_' + secrets.token_urlsafe(24)
            db.execute('INSERT INTO fz_mf_orders(intent,member,mode,state,created) VALUES(?,?,?,?,?)', (intent,member['id'],self.mode,'creating',now))
        body = {'Order':{'Amount':4.99,'Currency':'USD'}, 'OperationType':'PAY',
                'NotificationOption':'LINK','Language':'EN',
                'IntegrationUrls':{'Redirection':self.return_url+'?fz_mf_intent='+intent},
                'PaymentExpiry':datetime.fromtimestamp(now+1800,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
        try:
            data = self.api('POST','/v3/payments',body,intent)
            invoice = identifier(str(data.get('InvoiceId') or ''))
            url = self.valid_url(data.get('PaymentURL') or '')
            with self.accounts.connect() as db:
                db.execute("UPDATE fz_mf_orders SET invoice=?,url=?,state='pending' WHERE intent=?",(invoice,url,intent))
            return {'intent':intent,'url':url}
        except Exception as exc:
            # Keep intent for reconciliation, no automatic POST retry after timeouts.
            raise HTTPException(503,'payment_creation_pending') from exc

    def grant_id(self, invoice):
        return hashlib.sha256((self.provider+':'+invoice).encode()).hexdigest()

    def verify(self, payment, expected_invoice, member=None):
        identifier(payment); identifier(expected_invoice)
        with self.accounts.connect() as db:
            order = db.execute('SELECT * FROM fz_mf_orders WHERE mode=? AND invoice=?',(self.mode,expected_invoice)).fetchone()
        if not order or (member and order['member'] != member): raise HTTPException(404,'payment_not_found')
        data = self.api('GET','/v3/payments/'+payment)
        inv, txn, amt = data.get('Invoice',{}), data.get('Transaction',{}), data.get('Amount',{})
        if str(inv.get('Id','')) != expected_invoice or str(txn.get('PaymentId','')) != payment:
            raise HTTPException(409,'payment_mismatch')
        if inv.get('Status') != 'PAID' or txn.get('Status') != 'SUCCESS': return False
        # Never treat 4.99 KWD as 4.99 USD. Fees/receivables are not purchase amounts.
        try: value = Decimal(str(amt.get('ValueInPayCurrency','')))
        except InvalidOperation: raise HTTPException(409,'payment_mismatch')
        if amt.get('PayCurrency') != 'USD' or not value.is_finite() or value != Decimal('4.99'):
            raise HTTPException(409,'payment_currency_or_amount_mismatch')
        now, gid = int(time.time()), self.grant_id(expected_invoice)
        with self.accounts.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            refunded = db.execute('SELECT 1 FROM fz_mf_refunds WHERE mode=? AND invoice=?',(self.mode,expected_invoice)).fetchone()
            if refunded: return False
            prior = db.execute('SELECT * FROM fz_credit_grants WHERE id=?',(gid,)).fetchone()
            if prior and (prior['member'] != order['member'] or prior['plan'] != 'pack'):
                raise HTTPException(409,'purchase_conflict')
            if not prior:
                db.execute('INSERT INTO fz_credit_grants VALUES(?,?,?,?,?,?,?,?,0)',(gid,order['member'],'pack','pack',20,20,now,None))
                self.credits.ledger(db,order['member'],gid,None,20,'verified_purchase',now)
            db.execute("UPDATE fz_mf_orders SET state='paid' WHERE intent=?",(order['intent'],))
        return True

    def confirm(self, member, intent, payment):
        self.require(member); identifier(intent)
        with self.accounts.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM fz_mf_orders WHERE intent=? AND member=? AND mode=?',(intent,member['id'],self.mode)).fetchone()
            if not row: raise HTTPException(404,'payment_not_found')
            if row['state']=='refunded': return False
            if row['state']=='paid': return True
            if not row['invoice']: return False
            if row['checked'] > int(time.time())-3: raise HTTPException(429,'please_wait')
            db.execute('UPDATE fz_mf_orders SET checked=? WHERE intent=?',(int(time.time()),intent))
        return self.verify(payment,row['invoice'],member['id'])

    def receive(self, raw, signature):
        if not self.ready: raise HTTPException(503,'myfatoorah_not_ready')
        try:
            event = json.loads(raw); name = event['Event']['Name']; data = event['Data']
            fields = FIELDS[name]
            signed = ','.join(key+'='+scalar(data,key) for key in fields)
            expected = base64.b64encode(hmac.new(self.secret.encode(),signed.encode(),hashlib.sha256).digest()).decode()
            if not hmac.compare_digest(expected,signature): raise ValueError('signature')
        except (KeyError,ValueError,TypeError): raise HTTPException(400,'invalid_webhook')
        if name == 'REFUND_STATUS_CHANGED':
            if scalar(data,'Refund.Status') != 'REFUNDED': return
            invoice = identifier(scalar(data,'ReferencedInvoice.Id'))
            # Conservative: any completed refund cancels remaining credits of this Pack.
            # Persist the tombstone even if a payment webhook arrives later.
            with self.accounts.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT OR IGNORE INTO fz_mf_refunds VALUES(?,?)',(self.mode,invoice))
                gid = self.grant_id(invoice)
                grant = db.execute('SELECT * FROM fz_credit_grants WHERE id=?',(gid,)).fetchone()
                if grant and not grant['revoked']:
                    self.credits.ledger(db,grant['member'],gid,None,-grant['remaining'],'myfatoorah_refund',int(time.time()))
                    db.execute('UPDATE fz_credit_grants SET remaining=0,revoked=1 WHERE id=?',(gid,))
                db.execute("UPDATE fz_mf_orders SET state='refunded' WHERE mode=? AND invoice=?",(self.mode,invoice))
            return
        if scalar(data,'Transaction.Status') != 'SUCCESS': return
        invoice, payment = identifier(scalar(data,'Invoice.Id')), identifier(scalar(data,'Transaction.PaymentId'))
        job = hashlib.sha256((self.mode+':'+signed).encode()).hexdigest()
        with self.accounts.connect() as db:
            db.execute('INSERT OR IGNORE INTO fz_mf_jobs(id,mode,invoice,payment) VALUES(?,?,?,?)',(job,self.mode,invoice,payment))

    def process_jobs(self):
        if not self.ready: return
        with self.accounts.connect() as db:
            jobs=db.execute("SELECT * FROM fz_mf_jobs WHERE mode=? AND state='pending' AND next_try<=? LIMIT 20",(self.mode,int(time.time()))).fetchall()
        for job in jobs:
            try:
                done=self.verify(job['payment'],job['invoice'])
                state='done' if done else 'pending'
            except HTTPException as exc:
                state='review' if exc.status_code==409 else 'pending'
            except Exception: state='pending'
            tries=job['tries']+1
            if tries>=20 and state=='pending': state='review'
            with self.accounts.connect() as db:
                db.execute('UPDATE fz_mf_jobs SET state=?,tries=?,next_try=? WHERE id=?',(state,tries,int(time.time())+min(3600,10*2**min(tries,9)),job['id']))

    async def worker(self):
        while True:
            try: await asyncio.to_thread(self.process_jobs)
            except Exception: pass  # Durable jobs survive transient database/network failures.
            await asyncio.sleep(5)


def install_myfatoorah(app, credits):
    service=MyFatoorahPack(credits); app.state.findzia_myfatoorah=service
    def result(data): return JSONResponse({'ok':True,**data},headers={'Cache-Control':'no-store'})
    async def member(request):
        service.accounts.allow_request(request)
        return await asyncio.to_thread(service.accounts.member,service.accounts.token(request))
    @app.on_event('startup')
    async def startup():
        if service.ready: service.task=asyncio.create_task(service.worker())
    @app.on_event('shutdown')
    async def shutdown():
        if service.task:
            service.task.cancel()
            try: await service.task
            except asyncio.CancelledError: pass
    @app.get('/api/billing/myfatoorah/config')
    async def public_config(request:Request):
        service.accounts.allow_request(request)
        return result(service.public(None))
    @app.post('/api/billing/myfatoorah/restore')
    async def restore(request:Request):
        m=await member(request); service.require(m)
        # Only reconcile this member's server-mapped payments; no email matching.
        with service.accounts.connect() as db:
            rows=db.execute('SELECT j.payment,j.invoice FROM fz_mf_jobs j JOIN fz_mf_orders o ON o.mode=j.mode AND o.invoice=j.invoice WHERE o.member=? AND o.mode=? ORDER BY o.created DESC LIMIT 10',(m['id'],service.mode)).fetchall()
        for row in rows:
            await asyncio.to_thread(service.verify,row['payment'],row['invoice'],m['id'])
        return result({})
    @app.post('/api/billing/myfatoorah/config')
    async def config(request:Request): return result(service.public(await member(request)))
    @app.post('/api/billing/myfatoorah/checkout')
    async def checkout(request:Request):
        m=await member(request); payload=await service.accounts.body(request)
        return result(await asyncio.to_thread(service.checkout,m,payload.get('plan_id')))
    @app.post('/api/billing/myfatoorah/confirm')
    async def confirm(request:Request):
        m=await member(request); payload=await service.accounts.body(request)
        confirmed=await asyncio.to_thread(service.confirm,m,payload.get('intent'),payload.get('payment_id'))
        return result({'confirmed':confirmed})
    @app.post('/api/billing/myfatoorah/webhook')
    async def webhook(request:Request):
        raw=bytearray()
        async for part in request.stream():
            raw.extend(part)
            if len(raw)>131072: raise HTTPException(413,'event_too_large')
        await asyncio.to_thread(service.receive,bytes(raw),request.headers.get('myfatoorah-signature',''))
        return result({})
    return service
