"""Findzia 156.5.0 Paddle adapter: isolated sandbox/live checkout and verification.

Live checkout starts with an email allowlist; LIVE_OPEN explicitly opens it to members.
A durable inbox survives
restarts. Credit ownership comes from server-created transaction mappings,
never from a browser's completion event, email, or custom_data.
"""
import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlencode

import requests
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

PRICES = {
    'pack': 'pri_01m3kc8m40ag25ec202rsg1v1c',
    'plus': 'pri_01m3kcqgb2jv4ft9maqx70y412',
    'pro': 'pri_01m3kcvmd5nzr7znccbkgnaqdy',
}
CLIENT_TOKEN = 'test_2a54c0aa5fa385d256edc4d2598'
LIVE_PRICES = {
    'pack': 'pri_01m3kvhkye1rj066zyhwwg5bvg',
    'plus': 'pri_01m3kvg8hcy8rfg53xyfyh6mwa',
    'pro': 'pri_01m3kvejyh9rgy4v6yttv9mk91',
}
LIVE_CLIENT_TOKEN = 'live_166d3e561a3df6cc6d2d80247c4'
EVENTS = {'transaction.completed', 'transaction.payment_failed',
          'subscription.created', 'subscription.updated', 'subscription.canceled',
          'subscription.paused', 'subscription.resumed', 'subscription.past_due',
          'adjustment.created', 'adjustment.updated'}


class PaddleAPIError(RuntimeError):
    def __init__(self, status, code='unknown', request_id='unknown'):
        self.status = status
        self.code = code if isinstance(code, str) and re.fullmatch(r'[a-z_0-9]{1,100}', code) else 'unknown'
        self.request_id = request_id if isinstance(request_id, str) and re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', request_id) else 'unknown'
        # Only definite request rejections are safe to retry. Timeouts/5xx remain uncertain.
        self.rejected = status in (400, 401, 403, 404, 405, 422, 429)
        super().__init__('paddle_api_' + str(status))

    def public_code(self):
        if self.status == 401: return 'paddle_authentication_failed'
        if self.status == 403: return 'paddle_access_denied'
        if self.status == 429: return 'checkout_limit'
        return 'paddle_checkout_rejected'


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('missing_period')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('invalid_period')
    return int(dt.timestamp())


class PaddleSandbox:
    def __init__(self, credits, env=None):
        env = os.environ if env is None else env
        self.credits, self.accounts = credits, credits.accounts
        self.key = env.get('FINDZIA_PADDLE_API_KEY', '').strip()
        self.secret = env.get('FINDZIA_PADDLE_WEBHOOK_SECRET', '').strip()
        self.test_emails = {s.strip().lower() for s in env.get('FINDZIA_PADDLE_TEST_EMAILS', '').split(',') if s.strip()}
        self.mode = env.get('FINDZIA_PADDLE_ENV', 'sandbox').strip().lower()
        self.live_open = env.get('FINDZIA_PADDLE_LIVE_OPEN', 'false').strip().lower() == 'true'
        self.prices = dict(LIVE_PRICES if self.mode == 'live' else PRICES)
        self.client_token = LIVE_CLIENT_TOKEN if self.mode == 'live' else CLIENT_TOKEN
        self.base = 'https://api.paddle.com' if self.mode == 'live' else 'https://sandbox-api.paddle.com'
        self.portal_host = 'customer-portal.paddle.com' if self.mode == 'live' else 'sandbox-customer-portal.paddle.com'
        # Retain the existing sandbox tables; never replay their pending work into live.
        self.prefix = 'fz_paddle_live_' if self.mode == 'live' else 'fz_paddle_'
        self.provider = 'paddle_' + self.mode
        expected_key_prefix = 'pdl_live_apikey_' if self.mode == 'live' else 'pdl_sdbx_apikey_'
        self.ready = bool(credits.available and self.mode in ('sandbox', 'live')
                          and self.key.startswith(expected_key_prefix) and self.secret
                          and (self.test_emails or (self.mode == 'live' and self.live_open)))
        self.task = None
        self.lock = asyncio.Lock()
        if credits.available:
            with self.accounts.connect() as db:
                db.executescript(f'''
                CREATE TABLE IF NOT EXISTS {self.prefix}checkout(
                  intent TEXT PRIMARY KEY, member TEXT NOT NULL, plan TEXT NOT NULL,
                  txn TEXT UNIQUE, created INTEGER NOT NULL, state TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS {self.prefix}checkout_member ON {self.prefix}checkout(member,created);
                CREATE TABLE IF NOT EXISTS {self.prefix}subscription(
                  id TEXT PRIMARY KEY, member TEXT NOT NULL, customer TEXT NOT NULL,
                  plan TEXT NOT NULL, status TEXT NOT NULL, updated INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS {self.prefix}inbox(
                  event TEXT PRIMARY KEY, payload TEXT NOT NULL, state TEXT NOT NULL,
                  attempts INTEGER NOT NULL DEFAULT 0, next_try INTEGER NOT NULL DEFAULT 0,
                  error TEXT NOT NULL DEFAULT '');
                ''')

    def allowed(self, member):
        return bool(self.ready and member.get('id') and not member.get('guest') and
                    ((self.mode == 'live' and self.live_open) or member.get('email', '').lower() in self.test_emails))

    def require(self, member):
        if not self.allowed(member):
            raise HTTPException(403, 'sandbox_test_account_required' if self.mode == 'sandbox' else 'live_checkout_not_available')

    def public(self, member=None):
        return dict(checkout_available=self.allowed(member or {}), restore_available=self.allowed(member or {}),
                    paddle_environment=self.mode, paddle_client_token=self.client_token)

    def api(self, method, path, body=None, *, envelope=False):
        # Fixed host; never follow provider/browser supplied pagination URLs.
        try:
            response = requests.request(method, self.base + path,
                headers={'Authorization': 'Bearer ' + self.key, 'Content-Type': 'application/json', 'Paddle-Version': '1'},
                json=body, timeout=(3, 12), allow_redirects=False)
            if not 200 <= response.status_code < 300:
                try:
                    payload = response.json()
                    error = payload.get('error') or {}
                    meta = payload.get('meta') or {}
                    exc = PaddleAPIError(response.status_code, error.get('code'), meta.get('request_id'))
                except (ValueError, AttributeError):
                    exc = PaddleAPIError(response.status_code)
                # No response bodies, tokens, customer details, or URLs in logs.
                print('PADDLE_API_ERROR mode=%s status=%s code=%s request_id=%s' %
                      (self.mode, exc.status, exc.code, exc.request_id), flush=True)
                raise exc
            payload = response.json()
            return payload if envelope else payload['data']
        except (requests.RequestException, KeyError, ValueError) as exc:
            print('PADDLE_API_ERROR mode=%s code=transport_or_response_error' % self.mode, flush=True)
            raise RuntimeError('paddle_unavailable') from exc

    def recover_unmapped_checkout(self, member):
        # Only investigate requests whose transaction ID was NEVER returned to a client.
        # Never reset a known transaction or delete payment/credit records.
        with self.accounts.connect() as db:
            row = db.execute(f"SELECT * FROM {self.prefix}checkout WHERE member=? AND txn IS NULL AND state IN ('creating','uncertain') ORDER BY created DESC LIMIT 1", (member['id'],)).fetchone()
        if not row:
            return
        if int(time.time()) - row['created'] < 120:
            raise HTTPException(409, 'checkout_pending')
        start = datetime.fromtimestamp(max(0, row['created']-300), timezone.utc).isoformat()
        query = {'created_at[GTE]': start, 'per_page': 30, 'order_by': 'id[ASC]'}
        matches = []
        seen = set()
        deadline = time.monotonic() + 12
        try:
            for _ in range(20):
                if time.monotonic() >= deadline:
                    raise ValueError('recovery_time_limit')
                page = self.api('GET', '/transactions?' + urlencode(query), envelope=True)
                data = page['data']
                pagination = page['meta']['pagination']
                if not isinstance(data, list) or type(pagination.get('has_more')) is not bool:
                    raise ValueError('invalid_pagination')
                for txn in data:
                    if (txn.get('custom_data') or {}).get('findzia_intent') == row['intent']:
                        matches.append(txn)
                if not pagination['has_more']:
                    break
                cursor = data[-1]['id'] if data else ''
                if not re.fullmatch(r'txn_[a-z0-9]{26}', cursor) or cursor in seen:
                    raise ValueError('invalid_pagination')
                seen.add(cursor)
                query['after'] = cursor
            else:
                raise ValueError('recovery_scan_limit')
            if len(matches) > 1:
                raise ValueError('multiple_matching_transactions')
            txn = matches[0] if matches else None
            if txn:
                items = txn.get('items') or []
                if (not re.fullmatch(r'txn_[a-z0-9]{26}', txn.get('id',''))
                    or txn.get('origin') != 'api' or txn.get('currency_code') != 'USD'
                    or txn.get('collection_mode') != 'automatic'
                    or len(items) != 1 or items[0].get('quantity') != 1
                    or items[0].get('price',{}).get('id') != self.prices[row['plan']]):
                    raise ValueError('recovery_transaction_mismatch')
                state = 'canceled' if txn.get('status') == 'canceled' else 'pending'
            else:
                # Complete provider scan, aged request, and no checkout ID ever exposed.
                # Keep the old intent for audit. No credits are granted during recovery.
                state = 'not_created'
            with self.accounts.connect() as db:
                db.execute(f"UPDATE {self.prefix}checkout SET txn=?,state=? WHERE intent=? AND member=? AND txn IS NULL AND state IN ('creating','uncertain')",
                           (txn['id'] if txn else None, state, row['intent'], member['id']))
            print('PADDLE_CHECKOUT_RECOVERY mode=%s result=%s' % (self.mode, state), flush=True)
        except PaddleAPIError as exc:
            raise HTTPException(503, exc.public_code()) from exc
        except Exception as exc:
            print('PADDLE_CHECKOUT_RECOVERY mode=%s result=verification_incomplete' % self.mode, flush=True)
            raise HTTPException(503, 'paddle_recovery_unavailable') from exc

    def checkout(self, member, plan):
        self.require(member)
        if plan not in self.prices:
            raise HTTPException(400, 'invalid_plan')
        self.recover_unmapped_checkout(member)
        now = int(time.time())
        # One pending checkout per account. Reuse it across tabs/retries.
        with self.accounts.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if plan != 'pack' and db.execute(f"SELECT 1 FROM {self.prefix}subscription WHERE member=? AND status NOT IN ('canceled','paused')", (member['id'],)).fetchone():
                raise HTTPException(409, 'subscription_exists')
            if plan != 'pack' and db.execute('SELECT 1 FROM fz_subscriptions WHERE member=? AND period_end>?', (member['id'],now)).fetchone():
                raise HTTPException(409, 'subscription_exists')
            pending = db.execute(f"SELECT * FROM {self.prefix}checkout WHERE member=? AND state IN ('creating','pending','uncertain') ORDER BY created DESC LIMIT 1", (member['id'],)).fetchone()
            if pending:
                if pending['plan'] == plan and pending['txn']:
                    return {'transaction_id': pending['txn']}
                # Never create another potentially chargeable transaction after a timeout.
                raise HTTPException(409, 'checkout_pending')
            if db.execute(f'SELECT COUNT(*) FROM {self.prefix}checkout WHERE member=? AND created>?', (member['id'],now-3600)).fetchone()[0] >= 10:
                raise HTTPException(429, 'checkout_limit')
            intent = secrets.token_hex(24)
            db.execute(f'INSERT INTO {self.prefix}checkout VALUES(?,?,?,NULL,?,?)', (intent,member['id'],plan,now,'creating'))
        try:
            txn = self.api('POST','/transactions', {
                'items': [{'price_id': self.prices[plan], 'quantity': 1}],
                'currency_code': 'USD', 'collection_mode': 'automatic',
                'custom_data': {'findzia_intent': intent},
            })
            if not re.fullmatch(r'txn_[a-z0-9]{26}', txn.get('id','')):
                raise RuntimeError('invalid_transaction')
        except Exception as exc:
            rejected = isinstance(exc, PaddleAPIError) and exc.rejected
            with self.accounts.connect() as db:
                db.execute(f"UPDATE {self.prefix}checkout SET state=? WHERE intent=?", ('rejected' if rejected else 'uncertain', intent))
            if rejected:
                raise HTTPException(503, exc.public_code()) from exc
            raise HTTPException(503, 'checkout_pending') from exc
        with self.accounts.connect() as db:
            db.execute(f"UPDATE {self.prefix}checkout SET txn=?,state='pending' WHERE intent=?",(txn['id'],intent))
        return {'transaction_id': txn['id']}

    def receive(self, raw, signature):
        if not self.ready:
            raise HTTPException(503, 'payments_not_connected')
        parts = [p.strip().split('=',1) for p in signature.split(';')]
        stamps = [v for k,v in parts if k=='ts'] if all(len(p)==2 for p in parts) else []
        hashes = [v for k,v in parts if k=='h1'] if stamps else []
        if len(stamps)!=1 or not stamps[0].isdigit() or len(stamps[0])>12 or abs(time.time()-int(stamps[0]))>300:
            raise HTTPException(401, 'invalid_signature')
        expected=hmac.new(self.secret.encode(),stamps[0].encode()+b':'+raw,hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(expected,h) for h in hashes):
            raise HTTPException(401, 'invalid_signature')
        try:
            event=json.loads(raw)
            eid=event['event_id'];kind=event['event_type'];data=event['data']
            if not isinstance(eid,str) or not re.fullmatch(r'evt_[a-z0-9]{26}',eid) or not isinstance(data,dict):
                raise ValueError()
        except (ValueError,KeyError,TypeError):
            raise HTTPException(400, 'invalid_event')
        if kind not in EVENTS:
            return
        with self.accounts.connect() as db:
            db.execute(f'INSERT OR IGNORE INTO {self.prefix}inbox(event,payload,state) VALUES(?,?,?)', (eid,raw.decode(),'pending'))

    def owner(self, txn):
        with self.accounts.connect() as db:
            row=db.execute(f'SELECT member,plan FROM {self.prefix}checkout WHERE txn=?',(txn['id'],)).fetchone()
            if not row and txn.get('subscription_id'):
                row=db.execute(f'SELECT member,plan FROM {self.prefix}subscription WHERE id=?',(txn['subscription_id'],)).fetchone()
        if not row:
            raise RuntimeError('unmapped_transaction')
        return row['member'],row['plan']

    def reconcile_transaction(self, txn_id):
        if not re.fullmatch(r'txn_[a-z0-9]{26}',txn_id):
            raise ValueError('invalid_transaction')
        txn=self.api('GET','/transactions/'+txn_id+'?include=adjustments')
        member,plan_id=self.owner(txn)
        if txn['status']=='canceled':
            with self.accounts.connect() as db:
                db.execute(f"UPDATE {self.prefix}checkout SET state='canceled' WHERE txn=?",(txn_id,))
            return False
        if txn['status']!='completed':
            return False
        from findzia_billing import PLANS, fingerprint
        plan=next(p for p in PLANS if p['id']==plan_id)
        items=txn.get('items') or []
        if len(items)!=1 or items[0].get('quantity')!=1 or items[0].get('proration'):
            raise ValueError('unexpected_items')
        price=items[0]['price'];unit=price['unit_price']
        if price['id']!=self.prices[plan_id] or int(unit['amount'])!=plan['amount_cents'] or unit['currency_code']!='USD' or txn.get('currency_code')!='USD' or txn.get('discount_id'):
            raise ValueError('payment_mismatch')
        cycle=price.get('billing_cycle')
        if (plan_id=='pack' and cycle is not None) or (plan_id!='pack' and cycle!={'interval':'month','frequency':1}):
            raise ValueError('billing_cycle_mismatch')
        totals=txn.get('details',{}).get('totals',{})
        if int(totals.get('grand_total','0'))<=0 or int(totals.get('balance','-1'))!=0 or int(totals.get('discount','0'))!=0:
            raise ValueError('unsettled_payment')
        # Both tax-inclusive and tax-exclusive prices are valid. Paddle computes tax.
        gross=int(totals['total']);tax=int(totals['tax']);amount=plan['amount_cents']
        if gross!=amount and gross-tax!=amount:
            raise ValueError('amount_mismatch')
        period=txn.get('billing_period') or {}
        start=timestamp(period.get('starts_at')) if plan_id!='pack' else None
        end=timestamp(period.get('ends_at')) if plan_id!='pack' else None
        if plan_id!='pack' and (not re.fullmatch(r'sub_[a-z0-9]{26}',txn.get('subscription_id') or '') or not re.fullmatch(r'ctm_[a-z0-9]{26}',txn.get('customer_id') or '')):
            raise ValueError('missing_subscription')
        if plan_id!='pack':
            with self.accounts.connect() as db:
                owner=db.execute(f'SELECT member FROM {self.prefix}subscription WHERE id=?',(txn['subscription_id'],)).fetchone()
                if owner and owner['member']!=member:
                    raise ValueError('subscription_owner_conflict')
        adjustments=txn.get('adjustments') or []
        blocked=any(a.get('status')=='approved' and a.get('action') in ('refund','credit','chargeback','chargeback_warning') for a in adjustments)
        # A refunded transaction that arrives before its payment event never grants.
        if not blocked:
            self.credits.apply_verified_purchase(provider=self.provider,event_id='txn:'+txn_id,
                purchase_id=txn_id,member=member,plan_id=plan_id,amount_cents=amount,currency='USD',period_start=start,period_end=end)
        gid=fingerprint(self.provider+':'+txn_id)
        with self.accounts.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute(f"UPDATE {self.prefix}checkout SET state='completed' WHERE txn=?",(txn_id,))
            if blocked:
                row=db.execute('SELECT remaining,revoked FROM fz_credit_grants WHERE id=?',(gid,)).fetchone()
                if row and not row['revoked']:
                    self.credits.ledger(db,member,gid,None,-row['remaining'],'paddle_refund',int(time.time()))
                    db.execute('UPDATE fz_credit_grants SET revoked=1,remaining=0 WHERE id=?',(gid,))
            if plan_id!='pack':
                sid=txn.get('subscription_id');customer=txn.get('customer_id')
                if not sid or not customer:
                    raise ValueError('missing_subscription')
                existing=db.execute(f'SELECT member FROM {self.prefix}subscription WHERE id=?',(sid,)).fetchone()
                if existing and existing['member']!=member:
                    raise ValueError('subscription_owner_conflict')
                db.execute(f'INSERT OR IGNORE INTO {self.prefix}subscription VALUES(?,?,?,?,?,0)',(sid,member,customer,plan_id,'active'))
                db.execute('UPDATE fz_subscriptions SET subscription=? WHERE member=? AND subscription=?',(sid,member,txn_id))
        return not blocked

    def reconcile_subscription(self, sid):
        if not re.fullmatch(r'sub_[a-z0-9]{26}',sid):
            raise ValueError('invalid_subscription')
        sub=self.api('GET','/subscriptions/'+sid)
        updated=timestamp(sub['updated_at'])
        with self.accounts.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute(f'SELECT * FROM {self.prefix}subscription WHERE id=?',(sid,)).fetchone()
            if not row:
                raise RuntimeError('unmapped_subscription')
            if updated<row['updated']:
                return
            db.execute(f'UPDATE {self.prefix}subscription SET status=?,updated=? WHERE id=?',(sub['status'],updated,sid))
            scheduled=sub.get('scheduled_change') or {}
            db.execute('UPDATE fz_subscriptions SET cancel_at_end=? WHERE member=? AND subscription=? AND provider=?',(int(scheduled.get('action')=='cancel'),row['member'],sid,self.provider))
            # No credits are minted by subscription events; only settled transactions.
            # Paid-period credits keep their original expiry when auto-renew is canceled.

    def process(self, event):
        kind=event['event_type'];data=event['data']
        if kind=='transaction.completed' or kind.startswith('adjustment.'):
            self.reconcile_transaction(data['id'] if kind=='transaction.completed' else data['transaction_id'])
        elif kind.startswith('subscription.'):
            self.reconcile_subscription(data['id'])
        # Failed payments create no credits. Existing paid credits expire normally.

    def drain(self):
        with self.accounts.connect() as db:
            rows=db.execute(f"SELECT * FROM {self.prefix}inbox WHERE state='pending' AND next_try<=? ORDER BY rowid LIMIT 10",(int(time.time()),)).fetchall()
        for row in rows:
            try:
                self.process(json.loads(row['payload']))
                with self.accounts.connect() as db:
                    db.execute(f"UPDATE {self.prefix}inbox SET state='done',error='' WHERE event=?",(row['event'],))
            except Exception as exc:
                # Persist failures for retry/inspection; never log payloads or secrets.
                attempts=row['attempts']+1
                with self.accounts.connect() as db:
                    db.execute(f'UPDATE {self.prefix}inbox SET attempts=?,next_try=?,error=? WHERE event=?',
                        (attempts,int(time.time())+min(3600,2**min(attempts,11)),str(exc)[:80] if re.fullmatch(r'[a-z_0-9]+',str(exc)) else type(exc).__name__,row['event']))

    async def worker(self):
        while True:
            try:
                if self.ready:
                    async with self.lock:
                        await asyncio.to_thread(self.drain)
            except asyncio.CancelledError:
                raise
            except Exception:
                print('PADDLE: inbox retry pending')
            await asyncio.sleep(2)

    def portal(self, member):
        self.require(member)
        with self.accounts.connect() as db:
            row=db.execute(f'SELECT customer,id FROM {self.prefix}subscription WHERE member=? ORDER BY updated DESC LIMIT 1',(member['id'],)).fetchone()
        if not row:
            raise HTTPException(404,'no_subscription')
        data=self.api('POST','/customers/'+row['customer']+'/portal-sessions',{'subscription_ids':[row['id']]})
        url=data['urls']['general']['overview']
        parts=urlsplit(url)
        if parts.scheme!='https' or parts.hostname!=self.portal_host or parts.username or parts.password or parts.port:
            raise RuntimeError('invalid_portal_url')
        return url

    def restore(self, member):
        self.require(member)
        with self.accounts.connect() as db:
            rows=db.execute(f'SELECT txn FROM {self.prefix}checkout WHERE member=? AND txn IS NOT NULL ORDER BY created DESC LIMIT 20',(member['id'],)).fetchall()
            subs=db.execute(f'SELECT id FROM {self.prefix}subscription WHERE member=?',(member['id'],)).fetchall()
        for row in rows:
            self.reconcile_transaction(row['txn'])
        # Renewal notifications normally handle this; include last 30 invoices as recovery.
        for sub in subs:
            txns=self.api('GET','/transactions?subscription_id='+sub['id']+'&status=completed&per_page=30')
            for txn in txns:
                self.reconcile_transaction(txn['id'])
            self.reconcile_subscription(sub['id'])


def install_paddle(app, credits):
    service=PaddleSandbox(credits);app.state.findzia_paddle=service
    def result(data,code=200):
        return JSONResponse(data,status_code=code,headers={'Cache-Control':'no-store'})
    async def member(request):
        service.accounts.allow_request(request)
        return await asyncio.to_thread(service.accounts.member,service.accounts.token(request))
    @app.on_event('startup')
    async def startup():
        service.task=asyncio.create_task(service.worker())
    @app.on_event('shutdown')
    async def shutdown():
        if service.task:
            service.task.cancel()
            try:await service.task
            except asyncio.CancelledError:pass
    @app.post('/api/billing/paddle/webhook')
    async def webhook(request:Request):
        raw=bytearray()
        async for part in request.stream():
            raw.extend(part)
            if len(raw)>262144:raise HTTPException(413,'event_too_large')
        await asyncio.to_thread(service.receive,bytes(raw),request.headers.get('Paddle-Signature',''))
        return result({'ok':True})
    @app.post('/api/billing/paddle/config')
    async def config(request:Request):
        m=await member(request)
        return result({'ok':True,**service.public(m)})
    @app.post('/api/billing/paddle/checkout')
    async def checkout(request:Request):
        m=await member(request);payload=await service.accounts.body(request)
        return result({'ok':True,**await asyncio.to_thread(service.checkout,m,payload.get('plan_id'))})
    @app.post('/api/billing/paddle/confirm')
    async def confirm(request:Request):
        m=await member(request);service.require(m);payload=await service.accounts.body(request)
        tid=payload.get('transaction_id','')
        with service.accounts.connect() as db:
            owned=db.execute(f'SELECT 1 FROM {service.prefix}checkout WHERE txn=? AND member=?',(tid,m['id'])).fetchone()
        if not owned:raise HTTPException(404,'transaction_not_found')
        async with service.lock:
            complete=await asyncio.to_thread(service.reconcile_transaction,tid)
        return result({'ok':True,'confirmed':complete})
    @app.post('/api/billing/paddle/portal')
    async def portal(request:Request):
        m=await member(request)
        return result({'ok':True,'url':await asyncio.to_thread(service.portal,m)})
    @app.post('/api/billing/paddle/restore')
    async def restore(request:Request):
        m=await member(request)
        async with service.lock:
            await asyncio.to_thread(service.restore,m)
        return result({'ok':True,**await asyncio.to_thread(credits.status,m['id'])})
    return service
