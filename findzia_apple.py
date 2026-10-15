"""Verified StoreKit consumable credits. Web payment providers are unchanged.

Apple-signed product identity determines units, never a client price or quantity.
Each Apple environment/transaction has exactly one durable grant or tombstone.
"""
import asyncio
import json
import os
import re
import time
import uuid
from pathlib import Path
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from findzia_billing import fingerprint
from findzia_plans import BY_ID

PRODUCTS = {
    'com.findzia.spaces.credits30': 'space_starter',
    'com.findzia.spaces.credits80': 'space_plus',
    'com.findzia.spaces.credits180': 'space_pro',
}
BUNDLE_ID = 'com.findzia.spaces'


def value(v):
    return getattr(v, 'value', v)


class ApplePurchases:
    def __init__(self, credits, config=None):
        self.credits = credits
        self.accounts = credits.accounts
        env = os.environ if config is None else config
        self.live = str(env.get('FINDZIA_IAP_ENABLED', 'false')).lower() == 'true'
        self.test_members = {s.strip() for s in env.get('FINDZIA_IAP_SANDBOX_MEMBERS', '').split(',') if s.strip()}
        self.verifiers = {}
        app_id = str(env.get('FINDZIA_IAP_APP_APPLE_ID', ''))
        if self.accounts.available:
            with self.accounts.connect() as db:
                db.executescript('''
                CREATE TABLE IF NOT EXISTS fz_apple_accounts(
                  member TEXT PRIMARY KEY REFERENCES fz_members(id), token TEXT NOT NULL UNIQUE);
                CREATE TABLE IF NOT EXISTS fz_apple_transactions(
                  environment TEXT NOT NULL, transaction_id TEXT NOT NULL,
                  member TEXT NOT NULL REFERENCES fz_members(id), product TEXT NOT NULL,
                  grant_id TEXT NOT NULL UNIQUE, revoked INTEGER NOT NULL DEFAULT 0,
                  created INTEGER NOT NULL, PRIMARY KEY(environment,transaction_id));
                ''')
        if self.accounts.available and credits.spaces_pricing and re.fullmatch(r'[1-9][0-9]{5,19}', app_id):
            # The official library verifies Apple certificate chains, signatures,
            # certificate revocation, bundle ID, app ID (notifications), and environment.
            from appstoreserverlibrary.signed_data_verifier import SignedDataVerifier
            from appstoreserverlibrary.models.Environment import Environment
            roots = [p.read_bytes() for p in sorted((Path(__file__).parent / 'apple-roots').glob('*.cer'))]
            if not roots: raise RuntimeError('Apple root certificates missing')
            for environment in (Environment.PRODUCTION, Environment.SANDBOX):
                self.verifiers[environment.value] = SignedDataVerifier(roots, True, environment, BUNDLE_ID, int(app_id))

    def context(self, member):
        enabled = bool(self.verifiers and (self.live or member in self.test_members))
        if not enabled:
            return dict(enabled=False, app_account_token=None, product_ids=[])
        with self.accounts.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT OR IGNORE INTO fz_apple_accounts VALUES(?,?)', (member, str(uuid.uuid4())))
            token = db.execute('SELECT token FROM fz_apple_accounts WHERE member=?', (member,)).fetchone()['token']
        return dict(enabled=True, app_account_token=token, product_ids=list(PRODUCTS))

    def verify(self, signed, notification=False):
        if not self.verifiers: raise HTTPException(503, 'apple_purchases_unavailable')
        if not isinstance(signed, str) or not 100 < len(signed) <= 60000:
            raise HTTPException(400, 'invalid_apple_signature')
        from appstoreserverlibrary.signed_data_verifier import VerificationException
        for verifier in self.verifiers.values():
            try:
                return (verifier.verify_and_decode_notification(signed) if notification
                        else verifier.verify_and_decode_signed_transaction(signed))
            except VerificationException:
                continue
        raise HTTPException(400, 'invalid_apple_signature')

    def deliver(self, member, signed):
        txn = self.verify(signed)
        status = self.apply(txn, expected_member=member)
        return dict(ok=True, status=status)

    def apply(self, txn, expected_member=None, revoke=False):
        """Only called with a transaction already verified by Apple's library."""
        product = txn.productId
        environment = value(txn.environment)
        transaction = txn.transactionId
        if (txn.bundleId != BUNDLE_ID or environment not in ('Production', 'Sandbox')
                or product not in PRODUCTS or value(txn.type) != 'Consumable'
                or txn.quantity != 1 or value(txn.inAppOwnershipType) != 'PURCHASED'
                or not isinstance(transaction, str) or not re.fullmatch(r'[0-9]{1,40}', transaction)
                or not isinstance(txn.purchaseDate, int) or txn.purchaseDate > (time.time()+300)*1000):
            raise HTTPException(400, 'apple_transaction_mismatch')
        try: token = str(uuid.UUID(txn.appAccountToken))
        except (ValueError, TypeError, AttributeError): raise HTTPException(400, 'apple_account_missing')
        revoked = revoke or txn.revocationDate is not None
        gid = fingerprint('apple:' + environment + ':' + transaction)
        now = int(time.time())
        with self.accounts.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            owner = db.execute('SELECT member FROM fz_apple_accounts WHERE token=?', (token,)).fetchone()
            if not owner or (expected_member is not None and owner['member'] != expected_member):
                raise HTTPException(409, 'apple_account_mismatch')
            member = owner['member']
            if environment == 'Sandbox' and member not in self.test_members:
                raise HTTPException(403, 'apple_sandbox_not_allowed')
            prior = db.execute('SELECT * FROM fz_apple_transactions WHERE environment=? AND transaction_id=?', (environment, transaction)).fetchone()
            if prior and (prior['member'] != member or prior['product'] != product):
                raise HTTPException(409, 'apple_transaction_conflict')
            if prior and prior['revoked']: return 'revoked'
            # A refund can arrive before the app delivers its purchase. Keep a
            # permanent tombstone so late delivery cannot mint refunded credits.
            if not prior:
                db.execute('INSERT INTO fz_apple_transactions VALUES(?,?,?,?,?,?,?)',
                           (environment, transaction, member, product, gid, int(revoked), now))
            if revoked:
                db.execute('UPDATE fz_apple_transactions SET revoked=1 WHERE grant_id=?', (gid,))
                grant = db.execute('SELECT remaining,revoked FROM fz_credit_grants WHERE id=?', (gid,)).fetchone()
                if grant and not grant['revoked']:
                    self.credits.ledger(db, member, gid, None, -grant['remaining'], 'apple_refund', now)
                    db.execute('UPDATE fz_credit_grants SET revoked=1,remaining=0 WHERE id=?', (gid,))
                return 'revoked'
            if prior: return 'already_credited'
            plan = BY_ID[PRODUCTS[product]]
            db.execute('INSERT INTO fz_credit_grants VALUES(?,?,?,?,?,?,?,?,0)',
                       (gid, member, 'pack', plan['id'], plan['credits'], plan['credits'], now, None))
            self.credits.ledger(db, member, gid, None, plan['credits'], 'apple_verified_purchase', now)
            return 'credited'

    def notification(self, signed):
        notification = self.verify(signed, notification=True)
        kind = value(notification.notificationType)
        if kind == 'TEST': return dict(ok=True)
        data = notification.data
        if not data or not data.signedTransactionInfo: return dict(ok=True)
        txn = self.verify(data.signedTransactionInfo)
        if value(data.environment) != value(txn.environment):
            raise HTTPException(400, 'apple_notification_mismatch')
        # Other events are informational. Consumables are delivered by the app;
        # refunds must revoke even if the app is offline or delivery comes later.
        if kind in ('REFUND', 'REVOKE'):
            self.apply(txn, revoke=True)
        return dict(ok=True)


def install_apple(app, credits):
    service = ApplePurchases(credits)
    app.state.findzia_apple = service
    accounts = credits.accounts
    def result(data): return JSONResponse(data, headers={'Cache-Control': 'no-store'})
    async def payload(request):
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > 65536: raise HTTPException(413, 'body_too_large')
        try: parsed = json.loads(data)
        except (ValueError, UnicodeError): raise HTTPException(400, 'invalid_json')
        if not isinstance(parsed, dict): raise HTTPException(400, 'invalid_json')
        return parsed
    async def member(request):
        accounts.allow_request(request)
        return (await credits.runtime.run(accounts.member, accounts.token(request)))['id']
    @app.post('/api/billing/apple/context')
    async def apple_context(request: Request):
        who = await member(request)
        return result(await credits.runtime.run(service.context, who))
    @app.post('/api/billing/apple/transactions')
    async def apple_transaction(request: Request):
        who = await member(request)
        data = await payload(request)
        return result(await asyncio.to_thread(service.deliver, who, data.get('signed_transaction')))
    @app.post('/api/billing/apple/notifications')
    async def apple_notification(request: Request):
        # Apple has no browser Origin/session. A verified V2 JWS is mandatory.
        data = await payload(request)
        return result(await asyncio.to_thread(service.notification, data.get('signedPayload')))
