"""Cross-gateway creation lease. Runs only at checkout, never during search."""
from contextlib import contextmanager
from functools import wraps
import secrets
import time

from fastapi import HTTPException


def initialize(service):
    gateways = getattr(service.credits, '_payment_gateways', None)
    if gateways is None:
        gateways = service.credits._payment_gateways = {}
    gateways[service.provider] = service
    if not service.credits.available:
        return
    with service.accounts.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS fz_checkout_creation_lock(
            member TEXT PRIMARY KEY, owner TEXT NOT NULL, expires INTEGER NOT NULL)''')


@contextmanager
def creation(service, member):
    service.require(member)
    # The staged release is inert until the prepaid catalog is enabled.
    if not getattr(service.credits, 'prepaid_enabled', False):
        yield
        return
    gateway = 'myfatoorah' if service.provider.startswith('myfatoorah_') else 'paddle'
    if gateway != service.credits.payment_provider:
        raise HTTPException(409, 'payment_provider_changed')
    owner, now = secrets.token_hex(24), int(time.time())
    with service.accounts.connect() as db:
        taken = db.execute('''INSERT INTO fz_checkout_creation_lock VALUES(?,?,?)
            ON CONFLICT(member) DO UPDATE SET owner=excluded.owner,expires=excluded.expires
            WHERE expires<=?''', (member['id'], owner, now+180, now)).rowcount
    if not taken:
        raise HTTPException(409, 'payment_creation_pending')
    try:
        with service.accounts.connect() as db:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if gateway == 'paddle' and 'fz_mf_orders' in tables:
                # Unsubmitted COLLECT_DETAILS forms cannot charge on their own.
                # Cancel them atomically before opening the alternate gateway.
                db.execute('BEGIN IMMEDIATE')
                db.execute("UPDATE fz_mf_orders SET state='canceled' WHERE member=? AND mode=? AND state IN ('session_creating','session_ready')",
                           (member['id'], service.mode))
                # 'abandoned' is an unused hosted invoice already reviewed by
                # MyFatoorah's verifier, not an in-flight payment. Keep its mapping
                # intact so a late paid webhook can still credit it exactly once.
                row = db.execute('''SELECT 1 FROM fz_mf_orders o
                    WHERE o.member=? AND o.mode=? AND
                    o.state IN ('creating','pending','session_processing') LIMIT 1''',
                    (member['id'], service.mode)).fetchone()
            elif gateway == 'myfatoorah':
                table = 'fz_paddle_live_checkout' if service.mode == 'live' else 'fz_paddle_checkout'
                row = db.execute(f"SELECT 1 FROM {table} WHERE member=? AND state IN ('creating','pending','uncertain') LIMIT 1",
                                 (member['id'],)).fetchone() if table in tables else None
            else:
                row = None
        if row:
            other = 'myfatoorah' if gateway == 'paddle' else 'paddle'
            peer = getattr(service.credits, '_payment_gateways', {}).get(other + '_' + service.mode)
            reviewer = getattr(peer, 'review_before_switch', None)
            # Provider reads must not hold a SQLite write transaction open.
            if reviewer:
                try:
                    resolved = reviewer(member)
                except Exception:
                    print('CHECKOUT_GUARD build=156.7.55 gateway=%s other=%s result=verification_unavailable' % (gateway, other), flush=True)
                    raise HTTPException(409, 'other_payment_pending') from None
                if resolved and resolved.get('confirmed'):
                    yield {'confirmed': True}
                    return
            with service.accounts.connect() as db:
                if gateway == 'paddle':
                    row = db.execute("SELECT state FROM fz_mf_orders WHERE member=? AND mode=? AND state IN ('creating','pending','session_processing') LIMIT 1",
                                     (member['id'], service.mode)).fetchone()
                else:
                    row = db.execute(f"SELECT state FROM {table} WHERE member=? AND state IN ('creating','pending','uncertain') LIMIT 1",
                                     (member['id'],)).fetchone()
            if row:
                print('CHECKOUT_GUARD build=156.7.55 gateway=%s other=%s state=%s result=still_pending' % (gateway, other, row['state']), flush=True)
                raise HTTPException(409, 'other_payment_pending')
        yield None
    finally:
        with service.accounts.connect() as db:
            db.execute('DELETE FROM fz_checkout_creation_lock WHERE member=? AND owner=?', (member['id'], owner))


def guarded(method):
    @wraps(method)
    def wrapped(service, member, *args, **kwargs):
        with creation(service, member) as resolved:
            if resolved is not None:
                return resolved
            return method(service, member, *args, **kwargs)
    return wrapped
