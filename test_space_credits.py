import asyncio,tempfile,time,unittest,uuid
from pathlib import Path
from fastapi import HTTPException
from findzia_accounts import Accounts
from findzia_billing import Credits
from findzia_space_credits import DESIGN_PATH

class SpaceCredits(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.accounts=Accounts({'FINDZIA_ACCOUNT_DB':str(Path(self.tmp.name)/'credits.sqlite'),'FINDZIA_ACCOUNT_API_URL':'https://api.findzia.com'})
  self.c=Credits(self.accounts,{'FINDZIA_SPACES_PRICING_ENABLED':'true'})
  self.addCleanup(lambda:asyncio.run(self.c.runtime.close()))
  self.guest=self.c.guest(uuid.uuid4().hex);self.member=self.c.guest_member(self.guest['guest_token'])['id']
 def rid(self):return uuid.uuid4().hex
 def reserve(self,path=DESIGN_PATH,count=1):
  ids=[self.rid() for _ in range(count)];self.c.space_policy.reserve(self.member,ids,path);return ids
 def finish(self,ids,success=True):
  for rid in ids:self.c.finish(self.member,rid,success)
 def purchase(self,member=None,plan='space_starter',credits=30,amount=699):
  self.c.apply_verified_purchase(provider='test',event_id=self.rid(),purchase_id=self.rid(),member=member or self.member,plan_id=plan,amount_cents=amount,currency='USD')
 def test_trial_categories_and_partial_failure(self):
  ids=self.reserve(count=3);self.finish(ids[:2]);self.finish(ids[2:],False)
  data=self.c.status(self.member);self.assertEqual((data['free_designs'],data['free_searches']),(1,2))
  self.finish(self.reserve());
  with self.assertRaises(HTTPException):self.reserve()
  for _ in range(2):self.finish(self.reserve('/api/search/image/stream'))
  self.assertEqual(self.c.status(self.member)['remaining'],0)
  with self.assertRaises(HTTPException):self.reserve('/api/search/image/stream')
 def test_purchased_units_never_expire_or_repeat(self):
  self.purchase();self.assertEqual(self.c.status(self.member)['paid_remaining'],30)
  self.finish(self.reserve(count=3))
  for _ in range(2):self.finish(self.reserve('/api/search/image/stream'))
  ids=self.reserve('/api/search/image/stream');self.assertEqual(self.c.status(self.member)['remaining'],28)
  self.finish(ids,False);self.finish(ids,False);self.assertEqual(self.c.status(self.member)['remaining'],30)
  self.finish(self.reserve());self.assertEqual(self.c.status(self.member)['remaining'],29)
  with self.accounts.connect() as db:self.assertIsNone(db.execute("SELECT expires FROM fz_credit_grants WHERE plan='space_starter'").fetchone()[0])
 def test_atomic_batch_insufficient_and_idempotent(self):
  ids=self.reserve(count=3)
  self.assertEqual(self.c.space_policy.reserve(self.member,ids,DESIGN_PATH),[{'member':self.member,'request':r} for r in ids])
  self.assertEqual(self.c.status(self.member)['remaining'],4)
  self.finish(ids)
  with self.assertRaises(HTTPException):self.reserve(count=3)
  self.assertEqual(self.c.status(self.member)['remaining'],4)
 def test_split_grants_refund_exactly(self):
  # Consume the trial first, then split a 2-unit search across two grants.
  self.finish(self.reserve(count=3))
  for _ in range(2):self.finish(self.reserve('/api/search/image/stream'))
  self.purchase();self.purchase()
  with self.accounts.connect() as db:db.execute("UPDATE fz_credit_grants SET remaining=1 WHERE kind='pack'")
  ids=self.reserve('/api/search/image/stream');self.assertEqual(self.c.status(self.member)['remaining'],0)
  self.finish(ids,False);self.assertEqual(self.c.status(self.member)['remaining'],2)
 def test_conversion_preserves_paid_search_capacity_once(self):
  self.purchase(plan='pack',credits=20,amount=499)
  self.assertEqual(self.c.status(self.member)['paid_remaining'],40)
  with self.accounts.connect() as db:self.c.space_policy.convert(db,int(time.time()))
  self.assertEqual(self.c.status(self.member)['paid_remaining'],40)
 def test_crash_recovery_refunds_design_after_lease(self):
  ids=self.reserve(count=3)
  with self.accounts.connect() as db:
   db.execute('UPDATE fz_credit_requests SET created=?',(int(time.time())-7200,))
   self.c.recover(db,int(time.time()))
  self.assertEqual(self.c.status(self.member)['free_designs'],3)
  self.assertEqual(self.c.status(self.member)['remaining'],7)
 def test_new_catalog_only_and_exact_prices(self):
  plans=self.c.public_config()['plans'];self.assertEqual([(p['credits'],p['amount_cents'],p['interval']) for p in plans],[(30,699,'once'),(80,1499,'once'),(180,2999,'once')])

if __name__=='__main__':unittest.main()
