"""Cross-gateway creation lease. Runs only at checkout, never during search."""
from contextlib import contextmanager
from functools import wraps
import secrets
import time

from fastapi import HTTPException


def initialize(service):
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
                # Invoice timeouts/abandonment are never evidence of cancellation.
                row = db.execute('''SELECT 1 FROM fz_mf_orders o
                    WHERE o.member=? AND o.mode=? AND
                    o.state IN ('creating','pending','session_processing','abandoned') LIMIT 1''',
                    (member['id'], service.mode)).fetchone()
            elif gateway == 'myfatoorah':
                table = 'fz_paddle_live_checkout' if service.mode == 'live' else 'fz_paddle_checkout'
                row = db.execute(f"SELECT 1 FROM {table} WHERE member=? AND state IN ('creating','pending','uncertain') LIMIT 1",
                                 (member['id'],)).fetchone() if table in tables else None
            else:
                row = None
            if row:
                raise HTTPException(409, 'other_payment_pending')
        yield
    finally:
        with service.accounts.connect() as db:
            db.execute('DELETE FROM fz_checkout_creation_lock WHERE member=? AND owner=?', (member['id'], owner))


def guarded(method):
    @wraps(method)
    def wrapped(service, member, *args, **kwargs):
        with creation(service, member):
            return method(service, member, *args, **kwargs)
    return wrapped
