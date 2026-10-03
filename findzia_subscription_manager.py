"""Findzia 156.7.35: authenticated, in-site Paddle subscription management.

Provider data is projected into an allowlisted response. Ownership is anchored
to Findzia's server-created checkout/subscription mappings, never an email or
browser-supplied customer ID. No credit is granted by this interface.
"""
import asyncio
import re
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from urllib.parse import urlencode, urlsplit

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from findzia_billing import PLANS


def ident(value, prefix):
    return isinstance(value, str) and re.fullmatch(prefix + r'_[a-z0-9]{26}', value) is not None


def text(value, limit=1024):
    return value[:limit] if isinstance(value, str) else ''


def minor(value):
    return str(value) if not isinstance(value, bool) and re.fullmatch(r'-?\d{1,15}', str(value)) else None


def totals(data):
    data = data if isinstance(data, dict) else {}
    return {key: minor(data.get(key)) for key in
            ('subtotal', 'discount', 'tax', 'total', 'grand_total', 'credit', 'balance')}


def lines(data):
    result = []
    for item in data or []:
        product = item.get('product') or {}
        result.append(dict(name=text(product.get('name'), 200), quantity=item.get('quantity'),
                           tax_rate=text(item.get('tax_rate'), 30), totals=totals(item.get('totals'))))
    return result


def preview(data):
    if not isinstance(data, dict):
        return None
    details = data.get('details') or data
    return dict(totals=totals(details.get('totals')), items=lines(details.get('line_items')),
                period=data.get('billing_period'))


class SubscriptionManager:
    def __init__(self, paddle):
        self.p = paddle
        if paddle.credits.available:
            with paddle.accounts.connect() as db:
                db.executescript(f'''
                CREATE TABLE IF NOT EXISTS {paddle.prefix}manage_lock(
                  resource TEXT PRIMARY KEY, owner TEXT NOT NULL, expires INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS {paddle.prefix}payment_update(
                  txn TEXT PRIMARY KEY, member TEXT NOT NULL, subscription TEXT NOT NULL,
                  created INTEGER NOT NULL);
                ''')

    def require(self, member):
        if not member.get('id') or member.get('guest'):
            raise HTTPException(401, 'sign_in_required')
        # Existing customers can manage their subscriptions even if new sales
        # are temporarily closed with LIVE_OPEN=false.
        if not self.p.management_available(member):
            raise HTTPException(503, 'subscription_management_unavailable')

    def subscriptions(self, member):
        self.require(member)
        with self.p.accounts.connect() as db:
            return [dict(row) for row in db.execute(
                f"SELECT * FROM {self.p.prefix}subscription WHERE member=? ORDER BY CASE WHEN status IN ('active','past_due','trialing') THEN 0 ELSE 1 END,updated DESC,id DESC",
                (member['id'],)).fetchall()]

    def owned_sub(self, member, sid):
        self.require(member)
        if not ident(sid, 'sub'):
            raise HTTPException(404, 'subscription_not_found')
        with self.p.accounts.connect() as db:
            row = db.execute(f'SELECT * FROM {self.p.prefix}subscription WHERE member=? AND id=?',
                             (member['id'], sid)).fetchone()
        if not row:
            raise HTTPException(404, 'subscription_not_found')
        return dict(row)

    def fetch_sub(self, member, sid):
        row = self.owned_sub(member, sid)
        sub = self.p.api('GET', '/subscriptions/' + sid + '?include=next_transaction,recurring_transaction_details')
        self.check_sub(row, sub)
        return row, sub

    @staticmethod
    def check_sub(row, sub):
        if sub.get('id') != row['id'] or sub.get('customer_id') != row['customer']:
            raise RuntimeError('subscription_ownership_mismatch')

    def sub_view(self, row, sub):
        plan = next((p for p in PLANS if p['id'] == row['plan']), {})
        change = sub.get('scheduled_change')
        state = sub.get('status')
        can_cancel = state in ('active', 'trialing') and not change
        can_keep = state in ('active', 'trialing') and (change or {}).get('action') == 'cancel'
        return dict(id=sub['id'], plan_id=row['plan'], name=plan.get('name', 'Findzia'),
                    credits=plan.get('credits'), status=state,
                    currency=sub.get('currency_code'), billing_cycle=sub.get('billing_cycle'),
                    started_at=sub.get('started_at'), next_billed_at=sub.get('next_billed_at'),
                    current_period=sub.get('current_billing_period'), canceled_at=sub.get('canceled_at'),
                    scheduled_change={k: change.get(k) for k in ('action', 'effective_at')} if change else None,
                    updated_at=sub.get('updated_at'), next_payment=preview(sub.get('next_transaction')),
                    recurring=preview(sub.get('recurring_transaction_details')),
                    actions=dict(cancel=can_cancel, keep=can_keep,
                                 payment_method=sub.get('collection_mode') == 'automatic' and state in ('active', 'past_due')))

    def overview(self, member, sid=None):
        rows = self.subscriptions(member)
        if sid is not None:
            self.owned_sub(member, sid)
        chosen = sid or (rows[0]['id'] if rows else None)
        sub = None
        if chosen:
            row, data = self.fetch_sub(member, chosen)
            sub = self.sub_view(row, data)
        return dict(subscription=sub, subscriptions=[dict(id=r['id'], plan_id=r['plan'], status=r['status']) for r in rows])

    def transaction_owner(self, member, txn):
        tid = txn.get('id')
        if not ident(tid, 'txn'):
            raise HTTPException(404, 'transaction_not_found')
        with self.p.accounts.connect() as db:
            local = db.execute(f'SELECT member,plan,intent FROM {self.p.prefix}checkout WHERE txn=?', (tid,)).fetchone()
            sub = db.execute(f'SELECT member,plan,customer FROM {self.p.prefix}subscription WHERE id=?',
                             (txn.get('subscription_id') or '',)).fetchone()
        if local:
            if local['member'] != member['id']:
                raise HTTPException(404, 'transaction_not_found')
            if (txn.get('custom_data') or {}).get('findzia_intent') != local['intent']:
                raise RuntimeError('transaction_mapping_mismatch')
            return local['plan']
        if sub and sub['member'] == member['id'] and sub['customer'] == txn.get('customer_id'):
            return sub['plan']
        raise HTTPException(404, 'transaction_not_found')

    def fetch_transaction(self, member, tid):
        self.require(member)
        if not ident(tid, 'txn'):
            raise HTTPException(404, 'transaction_not_found')
        # Never inspect a known checkout belonging to a different account.
        with self.p.accounts.connect() as db:
            row = db.execute(f'SELECT member FROM {self.p.prefix}checkout WHERE txn=?', (tid,)).fetchone()
        if row and row['member'] != member['id']:
            raise HTTPException(404, 'transaction_not_found')
        txn = self.p.api('GET', '/transactions/' + tid + '?include=customer,address,business,adjustments')
        if txn.get('id') != tid:
            raise RuntimeError('transaction_mapping_mismatch')
        plan = self.transaction_owner(member, txn)
        return txn, plan

    def transaction_view(self, txn, plan_id):
        plan = next((p for p in PLANS if p['id'] == plan_id), {})
        details = txn.get('details') or {}
        successful = [p for p in txn.get('payments') or [] if p.get('status') == 'captured']
        method = (successful[-1].get('method_details') or {}) if successful else {}
        card = method.get('card') or {}
        amount = totals(details.get('totals'))
        invoice = txn.get('status') == 'completed' or (txn.get('collection_mode') == 'manual' and txn.get('status') == 'billed')
        invoice = invoice and amount['total'] is not None and int(amount['total']) > 0
        customer, address, business = txn.get('customer') or {}, txn.get('address') or {}, txn.get('business') or {}
        return dict(id=txn['id'], subscription_id=txn.get('subscription_id'), name=plan.get('name', 'Findzia'),
                    credits=plan.get('credits'), status=txn.get('status'), origin=txn.get('origin'),
                    currency=txn.get('currency_code'), date=txn.get('billed_at') or txn.get('created_at'),
                    period=txn.get('billing_period'), totals=amount, items=lines(details.get('line_items')),
                    invoice_number=txn.get('invoice_number'), revised_at=txn.get('revised_at'),
                    invoice_available=bool(invoice), can_revise=bool(invoice and not txn.get('revised_at')),
                    payment_method=dict(type=text(method.get('type'), 40), brand=text(card.get('type'), 40),
                                        last4=card.get('last4') if re.fullmatch(r'\d{4}', str(card.get('last4', ''))) else ''),
                    adjustments=[dict(action=a.get('action'), status=a.get('status'), totals=totals(a.get('totals')))
                                 for a in txn.get('adjustments') or []],
                    billing=dict(name=text(customer.get('name')), email=text(customer.get('email'), 254),
                                 business_name=text(business.get('name')), tax_identifier=text(business.get('tax_identifier')),
                                 address={k: text(address.get(k)) for k in ('first_line','second_line','city','region','postal_code','country_code')}))

    def transaction(self, member, tid):
        txn, plan = self.fetch_transaction(member, tid)
        return dict(transaction=self.transaction_view(txn, plan))

    def history(self, member, cursor=None):
        rows = self.subscriptions(member)
        cursor = cursor or {}
        if not isinstance(cursor, dict) or set(cursor) - {'local_after','remote_after','local_done','remote_done'}:
            raise HTTPException(400, 'invalid_cursor')
        for field in ('local_after', 'remote_after'):
            if cursor.get(field) is not None and not ident(cursor[field], 'txn'):
                raise HTTPException(400, 'invalid_cursor')
        for field in ('local_done', 'remote_done'):
            if field in cursor and type(cursor[field]) is not bool:
                raise HTTPException(400, 'invalid_cursor')
        with self.p.accounts.connect() as db:
            checkouts = [] if cursor.get('local_done') else db.execute(
                f'SELECT txn FROM {self.p.prefix}checkout WHERE member=? AND txn IS NOT NULL AND (? IS NULL OR txn<?) ORDER BY txn DESC LIMIT 21',
                (member['id'], cursor.get('local_after'), cursor.get('local_after'))).fetchall()
        tids = [r['txn'] for r in checkouts[:20]]
        queries = []
        if tids:
            queries.append(('local', dict(id=','.join(tids), per_page=30, order_by='id[DESC]', include='adjustments')))
        if rows and not cursor.get('remote_done'):
            query = dict(subscription_id=','.join(r['id'] for r in rows), per_page=20, order_by='id[DESC]', include='adjustments')
            if cursor.get('remote_after'):
                query['after'] = cursor['remote_after']
            queries.append(('remote', query))
        def get(entry):
            key, query = entry
            return key, self.p.api('GET', '/transactions?' + urlencode(query), envelope=True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            pages = dict(pool.map(get, queries))
        result = {}
        remote_after, remote_done = cursor.get('remote_after'), True
        for key, page in pages.items():
            data = page.get('data')
            if not isinstance(data, list):
                raise RuntimeError('invalid_history_response')
            for txn in data:
                # Provider filtering never substitutes for the account boundary.
                plan = self.transaction_owner(member, txn)
                if key == 'local' and txn['id'] not in tids:
                    raise RuntimeError('invalid_history_response')
                if key == 'remote' and txn.get('subscription_id') not in {r['id'] for r in rows}:
                    raise RuntimeError('invalid_history_response')
                if txn.get('status') not in ('completed','paid','billed','past_due','canceled') or txn.get('origin') == 'subscription_payment_method_change':
                    continue
                result[txn['id']] = self.transaction_view(txn, plan)
            if key == 'remote':
                more = (page.get('meta') or {}).get('pagination', {}).get('has_more')
                if type(more) is not bool or (more and not data):
                    raise RuntimeError('invalid_history_response')
                remote_done = not more
                remote_after = data[-1]['id'] if data else remote_after
                if more and remote_after == cursor.get('remote_after'):
                    raise RuntimeError('invalid_history_response')
        local_done = bool(cursor.get('local_done') or len(checkouts) <= 20)
        next_cursor = None if local_done and remote_done else dict(
            local_after=tids[-1] if tids else cursor.get('local_after'), remote_after=remote_after,
            local_done=local_done, remote_done=remote_done)
        return dict(payments=sorted(result.values(), key=lambda p: p.get('date') or '', reverse=True), next_cursor=next_cursor)

    @contextmanager
    def action(self, member, resource):
        self.require(member)
        owner, now = secrets.token_hex(16), int(time.time())
        with self.p.accounts.connect() as db:
            acquired = db.execute(f'''INSERT INTO {self.p.prefix}manage_lock VALUES(?,?,?)
                ON CONFLICT(resource) DO UPDATE SET owner=excluded.owner,expires=excluded.expires WHERE expires<=?''',
                (resource, owner, now + 120, now)).rowcount
        if not acquired:
            raise HTTPException(409, 'management_action_pending')
        try:
            yield
        finally:
            with self.p.accounts.connect() as db:
                db.execute(f'DELETE FROM {self.p.prefix}manage_lock WHERE resource=? AND owner=?', (resource, owner))

    def change_renewal(self, member, sid, action, expected):
        self.owned_sub(member, sid)
        with self.action(member, sid):
            row, sub = self.fetch_sub(member, sid)
            change = (sub.get('scheduled_change') or {}).get('action')
            # Safe retries after a response was lost; no second provider mutation.
            if action == 'cancel' and (change == 'cancel' or sub.get('status') == 'canceled'):
                return dict(subscription=self.sub_view(row, sub))
            if action == 'keep' and not change and sub.get('status') in ('active', 'trialing'):
                return dict(subscription=self.sub_view(row, sub))
            if not isinstance(expected, str) or expected != sub.get('updated_at'):
                raise HTTPException(409, 'subscription_changed')
            if not self.sub_view(row, sub)['actions'].get(action):
                raise HTTPException(409, 'subscription_change_not_available')
            if action == 'cancel':
                updated = self.p.api('POST', '/subscriptions/' + sid + '/cancel', {'effective_from':'next_billing_period'})
            else:
                updated = self.p.api('PATCH', '/subscriptions/' + sid, {'scheduled_change':None})
            self.check_sub(row, updated)
            actual = (updated.get('scheduled_change') or {}).get('action')
            if (action == 'cancel' and actual != 'cancel' and updated.get('status') != 'canceled') or (action == 'keep' and actual):
                raise RuntimeError('subscription_change_unconfirmed')
            # Synchronize the existing subscription flag, without touching credits.
            self.p.reconcile_subscription(sid)
            return self.overview(member, sid)

    def payment_method(self, member, sid):
        self.owned_sub(member, sid)
        with self.action(member, sid):
            row, sub = self.fetch_sub(member, sid)
            if not self.sub_view(row, sub)['actions']['payment_method']:
                raise HTTPException(409, 'payment_update_not_available')
            txn = self.p.api('GET', '/subscriptions/' + sid + '/update-payment-method-transaction')
            if not ident(txn.get('id'), 'txn') or txn.get('subscription_id') != sid or txn.get('customer_id') != row['customer']:
                raise RuntimeError('payment_update_ownership_mismatch')
            amount = totals((txn.get('details') or {}).get('totals'))
            if sub['status'] == 'active' and (txn.get('origin') != 'subscription_payment_method_change' or amount['grand_total'] != '0'):
                raise RuntimeError('payment_update_amount_mismatch')
            if sub['status'] == 'past_due' and txn.get('status') != 'past_due':
                raise RuntimeError('payment_update_status_mismatch')
            with self.p.accounts.connect() as db:
                db.execute(f'INSERT OR IGNORE INTO {self.p.prefix}payment_update VALUES(?,?,?,?)',
                           (txn['id'], member['id'], sid, int(time.time())))
            return dict(transaction_id=txn['id'], past_due=sub['status']=='past_due',
                        currency=txn.get('currency_code'), amount=amount['grand_total'])

    def payment_status(self, member, tid):
        self.require(member)
        with self.p.accounts.connect() as db:
            row = db.execute(f'SELECT * FROM {self.p.prefix}payment_update WHERE txn=? AND member=?', (tid, member['id'])).fetchone()
        if not row:
            raise HTTPException(404, 'transaction_not_found')
        self.owned_sub(member, row['subscription'])
        txn, _ = self.fetch_transaction(member, tid)
        if txn.get('subscription_id') != row['subscription']:
            raise RuntimeError('payment_update_ownership_mismatch')
        complete = txn.get('status') == 'completed'
        if complete and txn.get('origin') != 'subscription_payment_method_change':
            # Overdue renewals still go through the existing verified, idempotent
            # purchase reconciler. A browser success event is never proof of payment.
            self.p.reconcile_transaction(tid)
        return dict(confirmed=complete)

    def invoice(self, member, tid):
        txn, plan = self.fetch_transaction(member, tid)
        if not self.transaction_view(txn, plan)['invoice_available']:
            raise HTTPException(409, 'invoice_not_available')
        result = self.p.api('GET', '/transactions/' + tid + '/invoice?disposition=attachment')
        url = result.get('url', '')
        u = urlsplit(url)
        host = (u.hostname or '').lower()
        # Only a provider-generated, short-lived invoice link is returned.
        trusted = host.endswith('.paddle.com') or (host.startswith('paddle-') and host.endswith('.amazonaws.com'))
        if u.scheme != 'https' or not trusted or u.username or u.password or u.port or not u.path:
            raise RuntimeError('invalid_invoice_url')
        return dict(url=url)

    def revise(self, member, tid, payload):
        txn, plan = self.fetch_transaction(member, tid)
        if payload.get('confirmed') is not True:
            raise HTTPException(400, 'invoice_confirmation_required')
        fields = payload.get('changes')
        limits = {'customer':{'name':1024}, 'business':{'name':1024,'tax_identifier':1024},
                  'address':{'first_line':1024,'second_line':1024,'city':200,'region':200}}
        if not isinstance(fields, dict) or not fields or set(fields)-set(limits):
            raise HTTPException(400, 'invalid_invoice_changes')
        for group, values in fields.items():
            if not isinstance(values, dict) or not values or set(values)-set(limits[group]):
                raise HTTPException(400, 'invalid_invoice_changes')
            for key, value in values.items():
                if not isinstance(value, str) or not value.strip() or len(value)>limits[group][key] or re.search(r'[\x00-\x1f]',value):
                    raise HTTPException(400, 'invalid_invoice_changes')
        with self.action(member, tid):
            txn, plan = self.fetch_transaction(member, tid)
            if not self.transaction_view(txn, plan)['can_revise']:
                raise HTTPException(409, 'invoice_already_revised')
            updated = self.p.api('POST', '/transactions/' + tid + '/revise', fields)
            if updated.get('id') != tid or not updated.get('revised_at'):
                raise RuntimeError('invoice_revision_unconfirmed')
            self.transaction_owner(member, updated)
            return self.transaction(member, tid)


def install_subscription_manager(app, paddle):
    service = SubscriptionManager(paddle)
    app.state.findzia_subscription_manager = service

    async def run(request, method):
        paddle.accounts.allow_request(request)
        member = await asyncio.to_thread(paddle.accounts.member, paddle.accounts.token(request))
        service.require(member)
        payload = await paddle.accounts.body(request)
        try:
            data = await asyncio.to_thread(method, member, payload)
            return JSONResponse({'ok':True, **data}, headers={'Cache-Control':'no-store'})
        except HTTPException:
            raise
        except Exception as exc:
            from findzia_paddle import PaddleAPIError
            code = 'management_refresh_required'
            if isinstance(exc, PaddleAPIError):
                code = 'management_permission_required' if exc.status in (401,403) else 'management_provider_unavailable'
            # No customer details, invoice links or payment credentials in logs.
            print('FINDZIA_SUBSCRIPTIONS build=156735 error=' + code, flush=True)
            return JSONResponse({'ok':False,'error':code},status_code=503,headers={'Cache-Control':'no-store'})

    @app.post('/api/billing/paddle/manage/overview')
    async def overview(request:Request):
        return await run(request, lambda m,p: service.overview(m,p.get('subscription_id')))

    @app.post('/api/billing/paddle/manage/history')
    async def history(request:Request):
        return await run(request, lambda m,p: service.history(m,p.get('cursor')))

    @app.post('/api/billing/paddle/manage/transaction')
    async def transaction(request:Request):
        return await run(request, lambda m,p: service.transaction(m,p.get('transaction_id')))

    @app.post('/api/billing/paddle/manage/invoice')
    async def invoice(request:Request):
        return await run(request, lambda m,p: service.invoice(m,p.get('transaction_id')))

    @app.post('/api/billing/paddle/manage/invoice/revise')
    async def revise(request:Request):
        return await run(request, lambda m,p: service.revise(m,p.get('transaction_id'),p))

    @app.post('/api/billing/paddle/manage/cancel')
    async def cancel(request:Request):
        def confirmed(m,p):
            if p.get('confirmed') is not True:
                raise HTTPException(400, 'renewal_confirmation_required')
            return service.change_renewal(m,p.get('subscription_id'),'cancel',p.get('updated_at'))
        return await run(request, confirmed)

    @app.post('/api/billing/paddle/manage/keep')
    async def keep(request:Request):
        def confirmed(m,p):
            if p.get('confirmed') is not True:
                raise HTTPException(400, 'renewal_confirmation_required')
            return service.change_renewal(m,p.get('subscription_id'),'keep',p.get('updated_at'))
        return await run(request, confirmed)

    @app.post('/api/billing/paddle/manage/payment-method')
    async def payment_method(request:Request):
        return await run(request, lambda m,p: service.payment_method(m,p.get('subscription_id')))

    @app.post('/api/billing/paddle/manage/payment-status')
    async def payment_status(request:Request):
        return await run(request, lambda m,p: service.payment_status(m,p.get('transaction_id')))
    return service
