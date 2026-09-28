"""Findzia 156.5.2: retry unpaid checkouts using provider state, without an hour lock.
Disabled by default. Sandbox uses a separate key and an explicit email allowlist.
No card data, browser prices, or redirect claims are accepted as payment proof.
"""
import asyncio
import base64
import hashlib
import hmac
import json
import logging
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

LOG = logging.getLogger('findzia.myfatoorah')

class NoInvoiceTransactions(RuntimeError):
    """Authenticated invoice lookup explicitly reports no transactions."""

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
        self.embedded = env.get('FINDZIA_MYFATOORAH_EMBEDDED_ENABLED','false').lower() == 'true'
        self.apple_verified = env.get('FINDZIA_MYFATOORAH_APPLE_PAY_DOMAIN_VERIFIED','false').lower() == 'true'
        self.task = None
        if credits.available:
            with self.accounts.connect() as db:
                db.executescript('''
                CREATE TABLE IF NOT EXISTS fz_mf_orders(
                  intent TEXT PRIMARY KEY, member TEXT NOT NULL, mode TEXT NOT NULL,
                  invoice TEXT, url TEXT, state TEXT NOT NULL, created INTEGER NOT NULL,
                  checked INTEGER NOT NULL DEFAULT 0, UNIQUE(mode,invoice));
                CREATE INDEX IF NOT EXISTS fz_mf_member ON fz_mf_orders(member,mode,created);
                CREATE TABLE IF NOT EXISTS fz_mf_sessions(
                  intent TEXT PRIMARY KEY, session TEXT NOT NULL, expires INTEGER NOT NULL,
                  payment TEXT);
                CREATE TABLE IF NOT EXISTS fz_mf_jobs(
                  id TEXT PRIMARY KEY, mode TEXT NOT NULL, invoice TEXT NOT NULL,
                  payment TEXT NOT NULL, tries INTEGER NOT NULL DEFAULT 0,
                  next_try INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL DEFAULT 'pending');
                CREATE TABLE IF NOT EXISTS fz_mf_migrations(id TEXT PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS fz_mf_refunds(
                  mode TEXT NOT NULL, invoice TEXT NOT NULL, PRIMARY KEY(mode,invoice));
                ''')

            # One-time retry of owned pending invoices rejected by the old
            # USD-only rule. Every retry still runs the complete API verifier.
            with self.accounts.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                fresh=db.execute('INSERT OR IGNORE INTO fz_mf_migrations VALUES(?)',('156461_currency_'+self.mode,)).rowcount
                if fresh:
                    db.execute("""UPDATE fz_mf_jobs SET state='pending',tries=0,next_try=0
                      WHERE mode=? AND state='review' AND invoice IN
                      (SELECT invoice FROM fz_mf_orders WHERE mode=? AND state='pending')""",(self.mode,self.mode))

    def allowed(self, member):
        return bool(self.ready and member and not member.get('guest') and
            ((self.mode == 'live' and self.live_open) or member.get('email','').lower() in self.test_emails))

    def require(self, member):
        if not self.allowed(member): raise HTTPException(403, 'myfatoorah_not_available')

    def public(self, member):
        return {'ok': True, 'enabled': self.enabled, 'environment': self.mode,
                'checkout_available': self.allowed(member), 'plan_id': 'pack',
                'embedded_available': self.embedded and self.allowed(member),
                'apple_pay_domain_verified': self.apple_verified}

    def api(self, method, path, body=None, intent=None):
        headers = {'Authorization': 'Bearer ' + self.key, 'Content-Type':'application/json'}
        if intent: headers['Idempotency-Key'] = intent
        try:
            r = requests.request(method, self.base + path, headers=headers, json=body,
                                 timeout=(3,12), allow_redirects=False)
            result = r.json()
            # V3 documents this exact response for an invoice with no transactions.
            # Only a lookup of a server-owned numeric invoice can use this signal.
            # Authentication errors, timeouts and generic 404s are never evidence.
            if (method == 'GET' and re.fullmatch(r'/v3/invoices/[0-9]+',path)
                and r.status_code in (200,400,404) and result.get('IsSuccess') is False
                and result.get('Message') == 'No invoices match this InvoiceId'
                and not result.get('ValidationErrors')):
                raise NoInvoiceTransactions('no_invoice_transactions')
            if not 200 <= r.status_code < 300: raise RuntimeError('myfatoorah_api_unavailable')
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

    def review_unfinished(self, member, include_abandoned=False):
        """Reconcile real payments; an unused invoice is not a payment in progress.

        Provider requests run outside SQLite write transactions. Final writes use
        conditional updates so a simultaneous paid/refunded webhook always wins.
        Retired invoices remain mapped, allowing a late payment to be credited.
        """
        with self.accounts.connect() as db:
            rows=db.execute('''SELECT o.*,s.session,s.payment FROM fz_mf_orders o
                LEFT JOIN fz_mf_sessions s ON s.intent=o.intent
                WHERE o.member=? AND o.mode=? AND
                (o.state IN ('creating','pending','session_processing') OR
                 (? AND o.state='abandoned' AND o.created>?))
                ORDER BY o.created DESC''',
                (member['id'],self.mode,int(include_abandoned),int(time.time())-3600)).fetchall()
        paid=False
        for source in rows:
            row=dict(source)
            wait={'intent':row['intent'],'payment_pending':True}
            if row['payment']: wait['payment_id']=row['payment']
            if not row['invoice']:
                # A submitted charge with a lost response is different from an
                # unused invoice. Recover its mapping with a read, never a POST.
                if row['state']=='session_processing' and row['session']:
                    try:
                        session=self.api('GET','/v3/sessions/'+identifier(row['session']))
                        tx=session.get('TransactionResult') or {}
                        inv=identifier(str(tx.get('Invoice',{}).get('Id') or ''))
                        payment=identifier(tx.get('Transaction',{}).get('PaymentId'))
                        with self.accounts.connect() as db:
                            db.execute('BEGIN IMMEDIATE')
                            db.execute("UPDATE fz_mf_orders SET invoice=?,state='pending' WHERE intent=? AND state='session_processing' AND invoice IS NULL",(inv,row['intent']))
                            db.execute('UPDATE fz_mf_sessions SET payment=? WHERE intent=?',(payment,row['intent']))
                        row.update(invoice=inv,payment=payment,state='pending')
                        wait['payment_id']=payment
                    except Exception:
                        return wait
                else: return wait
            try:
                data=self.api('GET','/v3/invoices/'+identifier(row['invoice']))
                inv=data.get('Invoice',{})
                txns=data.get('Transactions')
                if str(inv.get('Id',''))!=row['invoice'] or not isinstance(txns,list):
                    raise ValueError('invoice_response_mismatch')
                inv_state=inv.get('Status')
                if inv_state not in ('PAID','PENDING','CANCELED','CANCELLED','EXPIRED'):
                    raise ValueError('unknown_invoice_state')
                successes=[t for t in txns if isinstance(t,dict) and t.get('Status')=='SUCCESS']
                if inv_state=='PAID' or successes:
                    if not successes: raise ValueError('paid_transaction_missing')
                    payment=identifier(successes[0].get('PaymentId'))
                    if not self.verify(payment,row['invoice'],member['id']): return wait
                    paid=True
                    continue
                # Unknown or active transactions must not be replaced. An invoice
                # remains PENDING even when all its attempts have already failed.
                active=[t for t in txns if not isinstance(t,dict) or t.get('Status') not in ('FAILED','CANCELED','CANCELLED')]
                if active:
                    if row['state']=='abandoned':
                        with self.accounts.connect() as db:
                            db.execute("UPDATE fz_mf_orders SET state='pending' WHERE intent=? AND state='abandoned'",(row['intent'],))
                    if (row['url'] and row['payment'] and any(isinstance(t,dict) and
                        t.get('PaymentId')==row['payment'] and t.get('Status')=='INPROGRESS' for t in active)):
                        wait['authentication_url']=self.valid_url(row['url'])
                    return wait
                if row['payment'] and not txns:
                    raise ValueError('known_payment_missing')
            except NoInvoiceTransactions:
                if row['session'] or row['payment']:
                    return wait  # A known submitted charge needs its final status.
            except Exception as exc:
                LOG.warning('MF_CHECKOUT_REVIEW invoice=%s status=unavailable',row['invoice'])
                raise HTTPException(503,'payment_verification_unavailable') from exc
            with self.accounts.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute("UPDATE fz_mf_orders SET state=? WHERE intent=? AND state='pending'",('failed' if row['session'] else 'abandoned',row['intent']))
                current=db.execute('SELECT state FROM fz_mf_orders WHERE intent=?',(row['intent'],)).fetchone()
                if current['state']=='paid': paid=True
        return {'confirmed':True} if paid else None

    def resume(self, member, intent=None):
        self.require(member)
        if intent:
            identifier(intent)
            with self.accounts.connect() as db:
                row=db.execute('SELECT state FROM fz_mf_orders WHERE intent=? AND member=? AND mode=?',(intent,member['id'],self.mode)).fetchone()
            if not row: raise HTTPException(404,'payment_not_found')
            if row['state']=='paid': return {'confirmed':True}
        return self.review_unfinished(member) or {'ready_for_payment':True}

    def checkout(self, member, plan):
        self.require(member)
        if plan != 'pack': raise HTTPException(400, 'pack_only')
        now = int(time.time())
        with self.accounts.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("UPDATE fz_mf_orders SET state='canceled' WHERE member=? AND mode=? AND state IN ('session_creating','session_ready')",(member['id'],self.mode))
            row = db.execute("SELECT * FROM fz_mf_orders WHERE member=? AND mode=? AND state IN ('creating','pending','session_processing') ORDER BY created DESC LIMIT 1", (member['id'],self.mode)).fetchone()
            if row and (row['state']=='session_processing' or row['created'] > now-3600):
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

    def embedded_session(self, member, plan):
        self.require(member)
        if not self.embedded: raise HTTPException(403,'embedded_not_available')
        if plan != 'pack': raise HTTPException(400,'pack_only')
        previous=self.review_unfinished(member)
        if previous: return previous
        now=int(time.time())
        with self.accounts.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rows=db.execute("SELECT * FROM fz_mf_orders WHERE member=? AND mode=? AND state IN ('creating','pending','session_processing','session_creating','session_ready') ORDER BY created DESC",(member['id'],self.mode)).fetchall()
            for row in rows:
                if row['state'] in ('creating','pending','session_processing'):
                    # Another request may have started payment during the lookup.
                    return {'intent':row['intent'],'payment_pending':True}
                if row['state']=='session_creating' and row['created']>now-60:
                    raise HTTPException(409,'payment_creation_pending')
                if row['state']=='session_ready':
                    session=db.execute('SELECT * FROM fz_mf_sessions WHERE intent=?',(row['intent'],)).fetchone()
                    if session and session['expires']>now+30:
                        return {'intent':row['intent'],'session_id':session['session']}
            db.execute("UPDATE fz_mf_orders SET state='canceled' WHERE member=? AND mode=? AND state IN ('session_creating','session_ready')",(member['id'],self.mode))
            intent='fz_'+secrets.token_urlsafe(24)
            db.execute('INSERT INTO fz_mf_orders(intent,member,mode,state,created) VALUES(?,?,?,?,?)',(intent,member['id'],self.mode,'session_creating',now))
        methods=['googlepay','card']
        if self.apple_verified: methods.append('applepay')
        body={'PaymentMode':'COLLECT_DETAILS','OperationType':'PAY',
              'Order':{'Amount':4.99,'Currency':'USD'},'SupportedPaymentMethods':methods,
              'Language':'EN','SessionExpiry':datetime.fromtimestamp(now+900,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
              'IntegrationUrls':{'Redirection':self.return_url+'?fz_mf_intent='+intent}}
        try:
            data=self.api('POST','/v3/sessions',body,intent)
            session=identifier(data.get('SessionId'))
            order=data.get('Order',{})
            if order.get('Currency')!='USD' or Decimal(str(order.get('Amount'))) != Decimal('4.99'):
                raise ValueError('session_price_mismatch')
            with self.accounts.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                updated=db.execute("UPDATE fz_mf_orders SET state='session_ready' WHERE intent=? AND state='session_creating'",(intent,)).rowcount
                if not updated: raise HTTPException(409,'session_canceled')
                db.execute('INSERT INTO fz_mf_sessions(intent,session,expires) VALUES(?,?,?)',(intent,session,now+900))
            # Never send EncryptionKey or card details to our frontend.
            return {'intent':intent,'session_id':session}
        except Exception as exc:
            with self.accounts.connect() as db:
                db.execute("UPDATE fz_mf_orders SET state='canceled' WHERE intent=? AND state='session_creating'",(intent,))
            raise HTTPException(503,'embedded_unavailable') from exc

    def complete_session(self, member, intent):
        self.require(member); identifier(intent)
        # Browser cannot supply a price, member, session ID or payment ID here.
        with self.accounts.connect() as db:
            owned=db.execute('SELECT state FROM fz_mf_orders WHERE intent=? AND member=? AND mode=?',(intent,member['id'],self.mode)).fetchone()
        if not owned: raise HTTPException(404,'payment_not_found')
        if owned['state']=='session_ready':
            # Recheck recently retired hosted invoices immediately before charging.
            # Opening the form never charges; only this explicit completion does.
            previous=self.review_unfinished(member,include_abandoned=True)
            if previous:
                if previous.get('confirmed'):
                    with self.accounts.connect() as db:
                        db.execute("UPDATE fz_mf_orders SET state='canceled' WHERE intent=? AND state='session_ready'",(intent,))
                return previous
        with self.accounts.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT o.*,s.session,s.expires,s.payment FROM fz_mf_orders o JOIN fz_mf_sessions s ON s.intent=o.intent WHERE o.intent=? AND o.member=? AND o.mode=?',(intent,member['id'],self.mode)).fetchone()
            if not row: raise HTTPException(404,'payment_not_found')
            if row['state']=='paid': return {'confirmed':True}
            if row['state']=='pending': return {'confirmed':False,'url':row['url'],'payment_id':row['payment'],'intent':intent}
            if row['state']!='session_ready': raise HTTPException(409,'payment_creation_pending')
            if row['expires']<=int(time.time()): raise HTTPException(409,'session_expired')
            other=db.execute("SELECT intent FROM fz_mf_orders WHERE member=? AND mode=? AND intent<>? AND state IN ('creating','pending','session_processing') LIMIT 1",(member['id'],self.mode,intent)).fetchone()
            if other: return {'intent':other['intent'],'payment_pending':True}
            db.execute("UPDATE fz_mf_orders SET state='session_processing' WHERE intent=?",(intent,))
        body={'SourceOfFund':{'SessionId':row['session']},'OperationType':'PAY',
              'Order':{'Amount':4.99,'Currency':'USD'},
              'IntegrationUrls':{'Redirection':self.return_url+'?fz_mf_intent='+intent},
              'PaymentExpiry':datetime.fromtimestamp(int(time.time())+1800,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
        try:
            data=self.api('POST','/v3/payments',body,intent)
            invoice=identifier(str(data.get('InvoiceId') or ''))
            payment=identifier(str(data.get('PaymentId') or ''))
            # Only provider checkout URLs; no arbitrary redirect from the browser.
            url=None
            if data.get('PaymentURL'):
                try: url=self.valid_url(data['PaymentURL'])
                except (RuntimeError,ValueError):
                    LOG.warning('Findzia MF invoice=%s unrecognized redirect; verification retained',invoice)
            with self.accounts.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute("UPDATE fz_mf_orders SET invoice=?,url=?,state='pending' WHERE intent=?",(invoice,url,intent))
                db.execute('UPDATE fz_mf_sessions SET payment=? WHERE intent=?',(payment,intent))
                job=hashlib.sha256((self.mode+':session:'+intent).encode()).hexdigest()
                db.execute('INSERT OR IGNORE INTO fz_mf_jobs(id,mode,invoice,payment) VALUES(?,?,?,?)',(job,self.mode,invoice,payment))
        except Exception as exc:
            # Never retry a charge automatically after an ambiguous response.
            # Keep processing state for reconciliation; hosted fallback is blocked.
            raise HTTPException(503,'payment_creation_pending') from exc
        confirmed=False
        if data.get('PaymentCompleted') is True:
            try: confirmed=self.verify(payment,invoice,member['id'])
            except Exception: pass  # Durable verifier retries independently.
        return {'intent':intent,'payment_id':payment,'url':None if confirmed else url,'confirmed':confirmed}

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
        # MyFatoorah separates display, payment and merchant base currencies.
        # Only the authenticated API response for our server-mapped PAID invoice
        # may establish its USD price. Never calculate today's exchange rate or
        # trust a browser/webhook Amount field (not covered by its signature).
        def money(field):
            try: value = Decimal(str(amt.get(field,'')))
            except (InvalidOperation, ValueError):
                raise HTTPException(409,'payment_currency_or_amount_mismatch')
            if not value.is_finite() or value <= 0:
                raise HTTPException(409,'payment_currency_or_amount_mismatch')
            return value
        paid = money('ValueInPayCurrency')
        display_usd = amt.get('DisplayCurrency') == 'USD'
        if display_usd and money('ValueInDisplayCurrency') != Decimal('4.99'):
            raise HTTPException(409,'payment_currency_or_amount_mismatch')
        if amt.get('PayCurrency') == 'USD':
            if paid != Decimal('4.99'):
                raise HTTPException(409,'payment_currency_or_amount_mismatch')
        elif (display_usd and amt.get('PayCurrency') == 'KWD'
              and amt.get('BaseCurrency') == 'KWD'):
            # Converted KWD settlement is valid for this Kuwait merchant only
            # when the provider confirms the exact USD invoice price and the
            # payment covers its base invoice amount (customer fees may add).
            if paid < money('ValueInBaseCurrency'):
                raise HTTPException(409,'payment_currency_or_amount_mismatch')
        else:
            LOG.warning('Findzia MF invoice=%s rejected: currency/amount evidence incomplete',expected_invoice)
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
        try:
            return self.verify(payment,row['invoice'],member['id'])
        except HTTPException as exc:
            LOG.warning('Findzia MF invoice=%s confirmation=%s',row['invoice'],exc.detail)
            raise

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
                LOG.warning('Findzia MF invoice=%s verification=%s',job['invoice'],exc.detail)
                state='review' if exc.status_code==409 else 'pending'
            except Exception:
                LOG.warning('Findzia MF invoice=%s provider verification temporarily unavailable',job['invoice'])
                state='pending'
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
    @app.post('/api/billing/myfatoorah/session')
    async def embedded_session(request:Request):
        m=await member(request); payload=await service.accounts.body(request)
        return result(await asyncio.to_thread(service.embedded_session,m,payload.get('plan_id')))
    @app.post('/api/billing/myfatoorah/session/complete')
    async def complete_session(request:Request):
        m=await member(request); payload=await service.accounts.body(request)
        return result(await asyncio.to_thread(service.complete_session,m,payload.get('intent')))
    @app.post('/api/billing/myfatoorah/resume')
    async def resume(request:Request):
        m=await member(request); payload=await service.accounts.body(request)
        return result(await asyncio.to_thread(service.resume,m,payload.get('intent')))
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
