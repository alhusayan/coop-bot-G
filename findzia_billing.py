"""Findzia 156.7.44: guest-first trials and non-blocking durable settlement.

No public purchase-grant endpoint. Checkout remains unavailable until a payment
adapter verifies payment, amount, currency and account ownership server-side.
SQLite transactions are intentionally short; no provider call runs in a lock.
"""
import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from findzia_credit_runtime import CreditRuntime

PLANS = (
    dict(id='pack', name='Findzia Pack', amount_cents=499, currency='USD', credits=20, interval='once'),
    dict(id='plus', name='Findzia Plus', amount_cents=999, currency='USD', credits=40, interval='month'),
    dict(id='pro', name='Findzia Pro', amount_cents=1999, currency='USD', credits=100, interval='month'),
)
SEARCH_PATHS = frozenset(('/api/search', '/api/search/stream', '/api/search/image',
    '/api/search/image/stream', '/api/search/more', '/api/search/more/stream',
    '/api/search/markets/stream', '/api/refine/search/stream'))
HELPER_PATHS = {'/api/guide': ('guide', 4), '/api/evaluate': ('insight', 5),
    '/api/refine/options': ('filters', 12), '/api/media/recover': ('media', 24),
    '/api/stores/ratings': ('ratings', 5), '/api/shopping/resolve': ('resolve', 12),
    '/api/ai/price-intelligence': ('insight', 5), '/api/ai/observe-prices': ('insight', 5),
    '/api/ai/price-history': ('insight', 5), '/api/ai/price-alert': ('insight', 5),
    '/api/ai/shopping': ('insight', 5)}
REQUEST_ID = re.compile(r'^[A-Za-z0-9_-]{20,100}$')

def fingerprint(value):
    return hashlib.sha256(str(value).encode()).hexdigest()

class Credits:
    def __init__(self, accounts, config=None):
        self.accounts = accounts
        env = os.environ if config is None else config
        self.enabled = str(env.get('FINDZIA_CREDITS_ENABLED', 'true')).lower() in ('true', '1', 'yes')
        self.trial_budget = max(0, int(env.get('FINDZIA_TRIAL_BUDGET_CREDITS', '10000')))
        self.trial_daily_attempts = max(0, int(env.get('FINDZIA_TRIAL_DAILY_ATTEMPTS', '500')))
        self.available = accounts.available
        self.runtime = CreditRuntime(self)
        if self.available:
            try:
                with accounts.connect() as db:
                    db.executescript('''
                    CREATE TABLE IF NOT EXISTS fz_credit_grants(
                      id TEXT PRIMARY KEY,member TEXT NOT NULL REFERENCES fz_members(id),
                      kind TEXT NOT NULL,plan TEXT NOT NULL,quantity INTEGER NOT NULL CHECK(quantity>=0),
                      remaining INTEGER NOT NULL CHECK(remaining>=0),starts INTEGER NOT NULL,
                      expires INTEGER,revoked INTEGER NOT NULL DEFAULT 0);
                    CREATE INDEX IF NOT EXISTS fz_credit_member ON fz_credit_grants(member,expires);
                    CREATE TABLE IF NOT EXISTS fz_trial_claims(
                      member TEXT PRIMARY KEY REFERENCES fz_members(id),device TEXT NOT NULL,created INTEGER NOT NULL);
                    CREATE INDEX IF NOT EXISTS fz_trial_device ON fz_trial_claims(device);
                    CREATE TABLE IF NOT EXISTS fz_credit_requests(
                      member TEXT NOT NULL REFERENCES fz_members(id),request TEXT NOT NULL,grant_id TEXT NOT NULL,
                      kind TEXT NOT NULL,path TEXT NOT NULL,state TEXT NOT NULL,
                      created INTEGER NOT NULL,finished INTEGER,PRIMARY KEY(member,request));
                    CREATE TABLE IF NOT EXISTS fz_credit_ledger(
                      id INTEGER PRIMARY KEY,member TEXT NOT NULL,grant_id TEXT NOT NULL,
                      request TEXT,delta INTEGER NOT NULL,reason TEXT NOT NULL,created INTEGER NOT NULL);
                    CREATE TABLE IF NOT EXISTS fz_helper_usage(
                      member TEXT NOT NULL,day INTEGER NOT NULL,kind TEXT NOT NULL,used INTEGER NOT NULL,
                      PRIMARY KEY(member,day,kind));
                    CREATE TABLE IF NOT EXISTS fz_billing_events(
                      provider TEXT NOT NULL,event TEXT NOT NULL,digest TEXT NOT NULL,created INTEGER NOT NULL,
                      PRIMARY KEY(provider,event));
                    CREATE TABLE IF NOT EXISTS fz_subscriptions(
                      member TEXT PRIMARY KEY,provider TEXT NOT NULL,subscription TEXT NOT NULL,
                      plan TEXT NOT NULL,period_end INTEGER NOT NULL,cancel_at_end INTEGER NOT NULL DEFAULT 0);
                    CREATE TABLE IF NOT EXISTS fz_credit_config(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS fz_guests(
                      device TEXT PRIMARY KEY,member TEXT NOT NULL UNIQUE REFERENCES fz_members(id),
                      token_hash TEXT NOT NULL UNIQUE,created INTEGER NOT NULL,
                      linked_member TEXT REFERENCES fz_members(id));
                    CREATE INDEX IF NOT EXISTS fz_requests_state_created ON fz_credit_requests(state,created);
                    CREATE INDEX IF NOT EXISTS fz_requests_grant_state ON fz_credit_requests(grant_id,state);
                    CREATE INDEX IF NOT EXISTS fz_requests_member_state_created ON fz_credit_requests(member,state,created);
                    CREATE INDEX IF NOT EXISTS fz_requests_created ON fz_credit_requests(created);
                    CREATE INDEX IF NOT EXISTS fz_grants_kind ON fz_credit_grants(kind);
                    ''')
                    db.execute('INSERT OR IGNORE INTO fz_credit_config VALUES(?,?)',('guest_key',secrets.token_hex(32)))
                    self.guest_key=db.execute("SELECT value FROM fz_credit_config WHERE key='guest_key'").fetchone()[0]
            except (OSError, sqlite3.Error):
                self.available = False
                print('BILLING: database unavailable; protected requests fail closed')
        if self.available:
            print('FINDZIA_CREDITS build=156.7.44 balance=read_only completion=durable_journal executors=isolated', flush=True)

    def check(self):
        if not self.available:
            raise HTTPException(503, 'credits_unavailable')

    def public_config(self):
        return dict(build='156.7.44', enabled=self.enabled, available=self.available, trial_credits=10,
                    guest_trial=True,checkout_available=False, restore_available=False, plans=list(PLANS))

    def ledger(self, db, member, grant, request, delta, reason, now):
        db.execute('INSERT INTO fz_credit_ledger(member,grant_id,request,delta,reason,created) VALUES(?,?,?,?,?,?)',
                   (member, grant, request, delta, reason, now))

    def recover(self, db, now):
        # Middleware limits requests to 180 seconds. A crash lease lives 10 minutes;
        # recovery never races a still-authorized search in another worker.
        for row in db.execute("SELECT * FROM fz_credit_requests WHERE state='reserved' AND created<? ORDER BY created LIMIT 64", (now-600,)).fetchall():
            # A completed search awaiting a busy SQLite writer must not be
            # refunded by crash recovery. Its server-owned outcome is durable.
            record = self.runtime.journal.read(row['member'], row['request'])
            self._finish(db, row, record['success'] if record else False, now, 'interrupted')

    def recover_expired(self):
        self.check(); now = int(time.time())
        with self.accounts.connect() as db:
            due = db.execute("SELECT 1 FROM fz_credit_requests WHERE state='reserved' AND created<? LIMIT 1", (now-600,)).fetchone()
        if due:
            with self.accounts.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                self.recover(db, now)

    def claim(self, member, device):
        self.check()
        if not isinstance(device, str) or not REQUEST_ID.fullmatch(device):
            raise HTTPException(400, 'device_id_required')
        now = int(time.time()); key = fingerprint(device)
        with self.accounts.connect() as db:
            if db.execute('SELECT 1 FROM fz_trial_claims WHERE member=?', (member,)).fetchone():
                return
        with self.accounts.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self._claim(db,member,key,now)

    def _claim(self,db,member,key,now):
        if db.execute('SELECT 1 FROM fz_trial_claims WHERE member=?', (member,)).fetchone():
            return
        # Eligibility is consumed even when this browser has already claimed.
        # Rotating its identifier later cannot regrant this account's trial.
        used = db.execute('SELECT 1 FROM fz_trial_claims WHERE device=?', (key,)).fetchone()
        allocated = db.execute("SELECT COALESCE(SUM(quantity),0) FROM fz_credit_grants WHERE kind='trial'").fetchone()[0]
        if not used and allocated + 10 > self.trial_budget:
            # Pausing new trials must never lock a paying member out of
            # an existing balance. Leave their trial eligibility intact.
            paid = db.execute("SELECT 1 FROM fz_credit_grants WHERE member=? AND kind!='trial' AND remaining>0 AND revoked=0 AND starts<=? AND (expires IS NULL OR expires>?)", (member, now, now)).fetchone()
            if paid:
                return
            raise HTTPException(429, 'trial_budget_reached')
        db.execute('INSERT INTO fz_trial_claims VALUES(?,?,?)', (member, key, now))
        if not used:
            gid = 'trial:' + member
            db.execute('INSERT INTO fz_credit_grants VALUES(?,?,?,?,?,?,?,?,0)',
                       (gid, member, 'trial', 'trial', 10, 10, now, None))
            self.ledger(db, member, gid, None, 10, 'trial', now)

    def guest(self,device):
        """Device is a random browser secret, never a fingerprint or account id.

        A deterministic server token makes simultaneous tabs/reloads idempotent.
        The key is persisted with the ledger so deployment does not reset trials.
        Possession authorizes only this guest's free allowance, never an account.
        """
        self.check()
        if not isinstance(device,str) or not REQUEST_ID.fullmatch(device):raise HTTPException(400,'device_id_required')
        now=int(time.time());key=fingerprint(device)
        token='fz_guest_'+hmac.new(self.guest_key.encode(),device.encode(),hashlib.sha256).hexdigest()
        with self.accounts.connect() as db:
            db.execute('BEGIN')
            guest=db.execute('SELECT * FROM fz_guests WHERE device=?',(key,)).fetchone()
            if guest:
                data=self._snapshot(db,guest['member'],now)
                data.update(guest=True,guest_token=token,trial_linked=bool(guest['linked_member']))
                return data
        with self.accounts.connect() as db:
            db.execute('BEGIN IMMEDIATE');self.recover(db,now)
            guest=db.execute('SELECT * FROM fz_guests WHERE device=?',(key,)).fetchone()
            if not guest:
                member='guest:'+secrets.token_hex(16)
                db.execute('INSERT INTO fz_members(id,provider,subject,email,name,created) VALUES(?,?,?,?,?,?)',(member,'guest',key,'','',now))
                self._claim(db,member,key,now)
                # Upgrade from 156.3.8: its trial required a login on this exact
                # browser. Move only that legacy free grant to the browser trial;
                # paid grants, sessions and profile data always remain private.
                legacy=db.execute("""SELECT g.* FROM fz_trial_claims c JOIN fz_credit_grants g
                    ON g.id='trial:'||c.member AND g.member=c.member JOIN fz_members m ON m.id=c.member
                    WHERE c.device=? AND m.provider IN ('google','apple') AND g.kind='trial'
                    AND g.revoked=0 ORDER BY c.created LIMIT 1""",(key,)).fetchone()
                if legacy:
                    if db.execute("SELECT 1 FROM fz_credit_requests WHERE grant_id=? AND state='reserved'",(legacy['id'],)).fetchone():
                        raise HTTPException(409,'trial_transfer_pending')
                    db.execute('UPDATE fz_credit_grants SET member=? WHERE id=?',(member,legacy['id']))
                    db.execute('UPDATE fz_credit_ledger SET member=? WHERE grant_id=?',(member,legacy['id']))
                    for use in db.execute('SELECT * FROM fz_helper_usage WHERE member=?',(legacy['member'],)).fetchall():
                        db.execute('INSERT OR IGNORE INTO fz_helper_usage VALUES(?,?,?,?)',(member,use['day'],use['kind'],use['used']))
                db.execute('INSERT INTO fz_guests VALUES(?,?,?,?,NULL)',(key,member,fingerprint(token),now))
                guest=db.execute('SELECT * FROM fz_guests WHERE device=?',(key,)).fetchone()
            data=self._snapshot(db,guest['member'],now)
            data.update(guest=True,guest_token=token,trial_linked=bool(guest['linked_member']))
            return data

    def guest_member(self,token):
        self.check()
        if not isinstance(token,str) or not re.fullmatch(r'fz_guest_[a-f0-9]{64}',token):raise HTTPException(401,'guest_session_expired')
        with self.accounts.connect() as db:
            row=db.execute('SELECT member FROM fz_guests WHERE token_hash=?',(fingerprint(token),)).fetchone()
            if not row:raise HTTPException(401,'guest_session_expired')
            return {'id':row['member'],'guest':True}

    def actor(self,request):
        token=self.accounts.token(request)
        return self.guest_member(token) if token.startswith('fz_guest_') else self.accounts.member(token)

    def link_guest(self,member,token):
        """Link after verified sign-in. Returns False while a guest search is live.

        Requests retain the original principal for reliable in-flight completion;
        quotas/counts follow the grant's current owner. No login mints a second trial.
        """
        self.check();now=int(time.time())
        if not isinstance(token,str) or not re.fullmatch(r'fz_guest_[a-f0-9]{64}',token):raise HTTPException(401,'guest_session_expired')
        with self.accounts.connect() as db:
            guest=db.execute('SELECT * FROM fz_guests WHERE token_hash=?',(fingerprint(token),)).fetchone()
            if not guest:raise HTTPException(401,'guest_session_expired')
            if guest['linked_member'] and db.execute('SELECT 1 FROM fz_trial_claims WHERE member=?',(member,)).fetchone():
                return True
        with self.accounts.connect() as db:
            db.execute('BEGIN IMMEDIATE');self.recover(db,now)
            guest=db.execute('SELECT * FROM fz_guests WHERE token_hash=?',(fingerprint(token),)).fetchone()
            if not guest:raise HTTPException(401,'guest_session_expired')
            if guest['linked_member']:
                # Switching accounts on one browser must not mint a fresh trial.
                db.execute('INSERT OR IGNORE INTO fz_trial_claims VALUES(?,?,?)',(member,guest['device'],now))
                return True
            owner=guest['member']
            if db.execute("SELECT 1 FROM fz_credit_requests WHERE member IN (?,?) AND state='reserved'",(owner,member)).fetchone():return False
            grant=db.execute("SELECT * FROM fz_credit_grants WHERE member=? AND kind='trial' AND revoked=0",(owner,)).fetchone()
            prior_trial=db.execute("SELECT 1 FROM fz_credit_grants WHERE member=? AND kind='trial'",(member,)).fetchone()
            if grant and not prior_trial:
                db.execute('UPDATE fz_credit_grants SET member=? WHERE id=?',(member,grant['id']))
                db.execute('UPDATE fz_credit_ledger SET member=? WHERE grant_id=?',(member,grant['id']))
            elif grant:
                # Combine consumed usage, not two ten-search allocations.
                consumed=grant['quantity']-grant['remaining']
                for prior in db.execute("SELECT * FROM fz_credit_grants WHERE member=? AND kind='trial' AND revoked=0",(member,)).fetchall():
                    debit=min(consumed,prior['remaining']);consumed-=debit
                    db.execute('UPDATE fz_credit_grants SET remaining=remaining-? WHERE id=?',(debit,prior['id']))
                    if debit:self.ledger(db,member,prior['id'],None,-debit,'guest_usage_merge',now)
                db.execute('UPDATE fz_credit_grants SET revoked=1 WHERE id=?',(grant['id'],))
            db.execute('INSERT OR IGNORE INTO fz_trial_claims VALUES(?,?,?)',(member,guest['device'],now))
            for use in db.execute('SELECT * FROM fz_helper_usage WHERE member=?',(owner,)).fetchall():
                # A legacy trial copied this account's helper history on migration.
                # Count that snapshot once when the same account signs back in.
                merge='MAX(used,excluded.used)' if grant and grant['id']=='trial:'+member else 'used+excluded.used'
                db.execute('INSERT INTO fz_helper_usage VALUES(?,?,?,?) ON CONFLICT(member,day,kind) DO UPDATE SET used='+merge,(member,use['day'],use['kind'],use['used']))
            db.execute('UPDATE fz_guests SET linked_member=? WHERE member=?',(member,owner))
            return True

    def _snapshot(self, db, member, now):
        rows = db.execute('SELECT * FROM fz_credit_grants WHERE member=? AND revoked=0 AND starts<=? AND (expires IS NULL OR expires>?)', (member, now, now)).fetchall()
        balances = {k: sum(r['remaining'] for r in rows if r['kind']==k) for k in ('trial','subscription','pack')}
        active = db.execute('SELECT * FROM fz_subscriptions WHERE member=? AND period_end>?', (member, now)).fetchone()
        counts = {r['kind']: r['n'] for r in db.execute("SELECT r.kind,COUNT(*) n FROM fz_credit_requests r JOIN fz_credit_grants g ON g.id=r.grant_id WHERE g.member=? AND r.state='spent' GROUP BY r.kind", (member,))}
        reserved = db.execute("SELECT COUNT(*) FROM fz_credit_requests r JOIN fz_credit_grants g ON g.id=r.grant_id WHERE g.member=? AND r.state='reserved'", (member,)).fetchone()[0]
        return dict(ok=True, remaining=sum(balances.values()), balances=balances, reserved=reserved,
                    used=counts, subscription=dict(active) if active else None,
                    trial_claimed=bool(db.execute('SELECT 1 FROM fz_trial_claims WHERE member=?',(member,)).fetchone()),
                    plans=list(PLANS), checkout_available=False, restore_available=False,
                    helper_limits={'guide_per_search':4,'insights_per_search':5})

    def status(self, member):
        self.check(); now=int(time.time())
        with self.accounts.connect() as db:
            # A consistent read snapshot; maintenance handles stale reservations.
            db.execute('BEGIN')
            return self._snapshot(db,member,now)

    def reserve(self, member, request_id, path):
        self.check()
        if not REQUEST_ID.fullmatch(request_id or ''):raise HTTPException(400,'request_id_required')
        now=int(time.time()); day=now//86400*86400
        with self.accounts.connect() as db:
            db.execute('BEGIN IMMEDIATE'); self.recover(db,now)
            previous=db.execute('SELECT r.state FROM fz_credit_requests r JOIN fz_credit_grants g ON g.id=r.grant_id WHERE (r.member=? OR g.member=?) AND r.request=?',(member,member,request_id)).fetchone()
            if previous:raise HTTPException(409,'search_in_progress' if previous['state']=='reserved' else 'search_already_processed')
            if db.execute("SELECT COUNT(*) FROM fz_credit_requests r JOIN fz_credit_grants g ON g.id=r.grant_id WHERE g.member=? AND r.state='reserved'",(member,)).fetchone()[0]>=2:
                raise HTTPException(429,'search_in_progress')
            if db.execute("SELECT COUNT(*) FROM fz_credit_requests r JOIN fz_credit_grants g ON g.id=r.grant_id WHERE g.member=? AND r.state='refunded' AND r.created>=?",(member,day)).fetchone()[0]>=5:
                raise HTTPException(429,'retry_limit')
            rows=db.execute('''SELECT * FROM fz_credit_grants WHERE member=? AND remaining>0 AND revoked=0
                AND starts<=? AND (expires IS NULL OR expires>?) ORDER BY
                CASE kind WHEN 'subscription' THEN 0 WHEN 'trial' THEN 1 ELSE 2 END,
                COALESCE(expires,9223372036854775807),starts,id''',(member,now,now)).fetchall()
            if not rows:raise HTTPException(402,'credits_exhausted')
            attempts=db.execute("SELECT COUNT(*) FROM fz_credit_requests r JOIN fz_credit_grants g ON g.id=r.grant_id WHERE g.kind='trial' AND r.created>=?",(day,)).fetchone()[0]
            row=next((r for r in rows if r['kind']!='trial' or attempts<self.trial_daily_attempts),None)
            if row is None:raise HTTPException(429,'trial_daily_limit')
            db.execute('UPDATE fz_credit_grants SET remaining=remaining-1 WHERE id=?',(row['id'],))
            kind='image' if '/image' in path else 'text'
            db.execute('INSERT INTO fz_credit_requests VALUES(?,?,?,?,?,?,?,NULL)',(member,request_id,row['id'],kind,path,'reserved',now))
            self.ledger(db,member,row['id'],request_id,-1,'reserve',now)

    def _finish(self, db, row, success, now, reason='empty_or_failed'):
        if row['state']!='reserved':return
        db.execute('UPDATE fz_credit_requests SET state=?,finished=? WHERE member=? AND request=?',
                   ('spent' if success else 'refunded',now,row['member'],row['request']))
        if not success:
            db.execute('UPDATE fz_credit_grants SET remaining=remaining+1 WHERE id=?',(row['grant_id'],))
            self.ledger(db,row['member'],row['grant_id'],row['request'],1,reason,now)

    def finish(self, member, request_id, success):
        self.check()
        with self.accounts.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM fz_credit_requests WHERE member=? AND request=?',(member,request_id)).fetchone()
            if row:self._finish(db,row,success,int(time.time()))

    def helper(self, member, kind, per_search):
        self.check(); now=int(time.time()); day=now//86400
        with self.accounts.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            funded=db.execute('SELECT COALESCE(SUM(quantity),0) FROM fz_credit_grants WHERE member=? AND revoked=0 AND starts<=? AND (expires IS NULL OR expires>?)',(member,now,now)).fetchone()[0]
            if not funded:raise HTTPException(402,'credits_exhausted')
            attempts=db.execute("SELECT COUNT(*) FROM fz_credit_requests r JOIN fz_credit_grants g ON g.id=r.grant_id WHERE g.member=? AND r.created>=?",(member,day*86400)).fetchone()[0]
            cap=min(funded, attempts+1)*per_search
            used=db.execute('SELECT used FROM fz_helper_usage WHERE member=? AND day=? AND kind=?',(member,day,kind)).fetchone()
            if used and used['used']>=cap:raise HTTPException(429,'helper_limit')
            # Trial helpers must not replenish forever after its ten searches.
            lifetime_funded=db.execute('SELECT COALESCE(SUM(quantity),0) FROM fz_credit_grants WHERE member=? AND revoked=0',(member,)).fetchone()[0]
            lifetime_used=db.execute('SELECT COALESCE(SUM(used),0) FROM fz_helper_usage WHERE member=? AND kind=?',(member,kind)).fetchone()[0]
            if lifetime_used >= lifetime_funded*per_search:raise HTTPException(429,'helper_limit')
            db.execute('INSERT INTO fz_helper_usage VALUES(?,?,?,1) ON CONFLICT(member,day,kind) DO UPDATE SET used=used+1',(member,day,kind))

    def apply_verified_purchase(self, *, provider, event_id, purchase_id, member, plan_id,
                                amount_cents, currency, period_start=None, period_end=None):
        """Internal integration boundary, NEVER exposed as a browser/webhook route.

        A future adapter must verify provider signatures AND fetch the authoritative
        transaction. purchase_id is the stable transaction/invoice id, not a webhook id.
        Subscription periods come from the provider, never a browser or local +30 days.
        """
        self.check(); plan=next((p for p in PLANS if p['id']==plan_id),None)
        if not plan or amount_cents!=plan['amount_cents'] or currency!='USD':raise ValueError('payment_mismatch')
        if not all(isinstance(v,str) and 1<=len(v)<=200 for v in (provider,event_id,purchase_id,member)):raise ValueError('invalid_payment')
        now=int(time.time()); recurring=plan['interval']=='month'
        if recurring and (not isinstance(period_start,int) or not isinstance(period_end,int) or not period_start<period_end or period_start>now+300):raise ValueError('invalid_period')
        start=period_start if recurring else now; expiry=period_end if recurring else None
        gid=fingerprint(provider+':'+purchase_id)
        payload=fingerprint(json.dumps([member,plan_id,amount_cents,currency,period_start,period_end,purchase_id]))
        with self.accounts.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT digest FROM fz_billing_events WHERE provider=? AND event=?',(provider,event_id)).fetchone()
            if prior:
                if prior['digest']!=payload:raise ValueError('event_conflict')
                return False
            existing=db.execute('SELECT * FROM fz_credit_grants WHERE id=?',(gid,)).fetchone()
            if existing and (existing['member']!=member or existing['plan']!=plan_id or existing['expires']!=expiry):raise ValueError('purchase_conflict')
            if recurring and not existing:
                overlap=db.execute("SELECT 1 FROM fz_credit_grants WHERE member=? AND kind='subscription' AND revoked=0 AND starts<? AND expires>?",(member,expiry,start)).fetchone()
                if overlap:raise ValueError('overlapping_subscription_period')
            db.execute('INSERT INTO fz_billing_events VALUES(?,?,?,?)',(provider,event_id,payload,now))
            if existing:return False
            db.execute('INSERT INTO fz_credit_grants VALUES(?,?,?,?,?,?,?,?,0)',(gid,member,'subscription' if recurring else 'pack',plan_id,plan['credits'],plan['credits'],start,expiry))
            self.ledger(db,member,gid,None,plan['credits'],'verified_purchase',now)
            if recurring:
                # Expired/out-of-order delivery cannot replace a newer period.
                db.execute('''INSERT INTO fz_subscriptions VALUES(?,?,?,?,?,0)
                  ON CONFLICT(member) DO UPDATE SET provider=excluded.provider,subscription=excluded.subscription,
                  plan=excluded.plan,period_end=excluded.period_end,cancel_at_end=0
                  WHERE excluded.period_end>fz_subscriptions.period_end''',(member,provider,purchase_id,plan_id,expiry))
            return True


class ResultEvidence:
    """Observe the existing response without buffering/delaying product cards."""
    def __init__(self):self.buffer=b'';self.rows=set();self.status=200;self.streaming=False;self.terminal=False
    def row(self,r):
        if isinstance(r,dict) and (r.get('url') or r.get('link')) and (r.get('title') or r.get('name') or r.get('product_name')):
            self.rows.add(r.get('url') or r.get('link'))
    def event(self,d):
        if not isinstance(d,dict):return
        if d.get('event') in ('result','upsert'):self.row(d.get('item'))
        if d.get('event')=='remove':self.rows.discard(d.get('url'))
        for field in ('results','all_results','items'):
            if isinstance(d.get(field),list):
                for r in d[field]:self.row(r)
        if d.get('event')=='done':
            self.terminal=True
            if d.get('count')==0:self.rows.clear()
    def consume(self,chunk,final=False):
        self.buffer+=chunk
        if self.streaming:
            parts=self.buffer.split(b'\n');self.buffer=parts.pop()
            for p in parts:
                try:self.event(json.loads(p))
                except (ValueError,UnicodeError):pass
        if final and self.buffer:
            try:self.event(json.loads(self.buffer))
            except (ValueError,UnicodeError):pass
            self.buffer=b''
        if len(self.buffer)>16000000:self.buffer=b''


class CreditMiddleware:
    def __init__(self, app, owner):self.app=app;self.owner=owner
    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope.get('method')=='OPTIONS':return await self.app(scope,receive,send)
        path=scope['path']; is_search=path in SEARCH_PATHS
        helper=HELPER_PATHS.get(path)
        # Debug probes and the obsolete bot cannot bypass the admission gate.
        blocked=(path=='/webhook' and scope.get('method')=='POST') or (path=='/api/health/serpapi' and b'probe=' in scope.get('query_string',b''))
        if not is_search and not helper and not blocked:return await self.app(scope,receive,send)
        service=getattr(self.owner.state,'findzia_credits',None)
        if service and not service.enabled:return await self.app(scope,receive,send)
        reserved=False;member=None;rid='';evidence=ResultEvidence();started=False;ended=False;completion=None
        async def reply(code,error):
            await JSONResponse({'ok':False,'error':error},status_code=code,headers={'Cache-Control':'no-store'})(scope,receive,send)
        try:
            if not service:raise HTTPException(503,'credits_unavailable')
            if blocked:raise HTTPException(403,'endpoint_disabled')
            if scope.get('method')!='POST':raise HTTPException(405,'method_not_allowed')
            service.check()
            request=Request(scope)
            if request.headers.get('origin') not in service.accounts.origins:raise HTTPException(403,'origin_not_allowed')
            member=await service.runtime.run(service.actor,request)
            if is_search:
                rid=request.headers.get('x-findzia-request-id','')
                # Shield admission too: a disconnect must not orphan a queued
                # reservation that later deducts a credit without retrieval.
                admission=service.runtime.track(service.runtime.run(service.reserve,member['id'],rid,path,write=True))
                try:
                    await asyncio.shield(admission);reserved=True
                except asyncio.CancelledError:
                    async def cancel_admission():
                        try:
                            await admission
                            await service.runtime.complete(member['id'],rid,False)
                        except (HTTPException,OSError,sqlite3.Error):
                            print('CREDITS_ADMISSION cancelled_recovery_pending',flush=True)
                    service.runtime.track(cancel_admission())
                    raise
            else:await service.runtime.run(service.helper,member['id'],*helper,write=True)
        except HTTPException as exc:return await reply(exc.status_code,exc.detail)
        except (OSError,sqlite3.Error):return await reply(503,'credits_unavailable')

        async def observe(message):
            nonlocal started,ended,completion
            if message['type']=='http.response.start':
                evidence.status=message['status'];started=True
                evidence.streaming=any(k.lower()==b'content-type' and b'ndjson' in v for k,v in message.get('headers',[]))
            if message['type']=='http.response.body':
                evidence.consume(message.get('body',b''),not message.get('more_body',False))
                # Persist before the done event (clients cancel their reader at
                # done). SQLite may then retry without holding the response open.
                if reserved and (evidence.terminal or not message.get('more_body',False)):
                    if completion is None:
                        completion=service.runtime.track(service.runtime.complete(member['id'],rid,evidence.status<400 and bool(evidence.rows)))
                    await asyncio.shield(completion)
                    ended=True
            await send(message)
        try:
            await asyncio.wait_for(self.app(scope,receive,observe),timeout=180)
        except asyncio.TimeoutError:
            if not started:await reply(504,'search_timeout')
            else:await observe({'type':'http.response.body','body':b'','more_body':False})
        finally:
            if reserved and not ended:
                # One completion only, even when a client cancels at done. The
                # runtime retains it until the outcome is durable.
                if completion is None:
                    completion=service.runtime.track(service.runtime.complete(member['id'],rid,evidence.status<400 and bool(evidence.rows)))
                await asyncio.shield(completion)


def install_billing(app, accounts):
    service=Credits(accounts);app.state.findzia_credits=service
    @app.on_event('startup')
    async def start_credit_maintenance():service.runtime.start()
    @app.on_event('shutdown')
    async def stop_credit_maintenance():await service.runtime.close()
    def result(data,status=200):return JSONResponse(data,status_code=status,headers={'Cache-Control':'no-store'})
    @app.get('/api/billing/config')
    async def billing_config():return result(dict(ok=True,**service.public_config()))
    @app.post('/api/billing/guest')
    async def guest(request:Request):
        accounts.allow_request(request);payload=await accounts.body(request)
        return result(await service.runtime.run(service.guest,payload.get('device_id')))
    @app.post('/api/billing/status')
    async def status(request:Request):
        accounts.allow_request(request);payload=await accounts.body(request)
        member=await service.runtime.run(service.actor,request)
        if member.get('guest'):
            data=await service.runtime.run(service.status,member['id']);data['guest']=True
            return result(data)
        linked=True
        if payload.get('guest_token'):
            linked=await service.runtime.run(service.link_guest,member['id'],payload['guest_token'])
        if linked:await service.runtime.run(service.claim,member['id'],payload.get('device_id'))
        data=await service.runtime.run(service.status,member['id']);data.update(guest=False,trial_link_pending=not linked)
        return result(data)
    @app.post('/api/billing/checkout')
    async def checkout(request:Request):
        accounts.allow_request(request)
        await asyncio.to_thread(accounts.member,accounts.token(request))
        return result({'ok':False,'error':'payments_not_connected'},503)

    # Optional Paddle Sandbox integration; no changes to search admission.
    from findzia_paddle import install_paddle
    install_paddle(app, service)
    from findzia_myfatoorah import install_myfatoorah
    install_myfatoorah(app, service)
