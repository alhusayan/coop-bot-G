"""Findzia 156.7.54: prepaid catalog; legacy IDs stay valid for reconciliation."""

from fastapi import HTTPException

LEGACY_PLANS = (
    dict(id='pack', name='Findzia Pack', amount_cents=499, currency='USD', credits=20, interval='once'),
    dict(id='plus', name='Findzia Plus', amount_cents=999, currency='USD', credits=40, interval='month'),
    dict(id='pro', name='Findzia Pro', amount_cents=1999, currency='USD', credits=100, interval='month'),
)
PREPAID_PLANS = (
    LEGACY_PLANS[0],
    dict(id='pack50', name='50 searches', amount_cents=999, currency='USD', credits=50, interval='once', recommended=True),
    dict(id='pack100', name='100 searches', amount_cents=1799, currency='USD', credits=100, interval='once'),
)
# Never reuse Plus/Pro IDs or their recurring Paddle prices for a top-up.
PLANS = LEGACY_PLANS + PREPAID_PLANS[1:]
BY_ID = {p['id']: p for p in PLANS}


def purchase_plan(plan_id, *, prepaid=False, once_only=False):
    plan = BY_ID.get(plan_id) if isinstance(plan_id, str) else None
    offered = PREPAID_PLANS if prepaid else LEGACY_PLANS
    if plan is None or plan not in offered or (once_only and plan['interval'] != 'once'):
        raise HTTPException(400, 'invalid_plan')
    return plan


def stored_prepaid(plan_id):
    """Only a plan persisted by the server may determine payment/credit amounts."""
    plan = BY_ID.get(plan_id)
    if not plan or plan['interval'] != 'once':
        raise HTTPException(409, 'payment_plan_mismatch')
    return plan
