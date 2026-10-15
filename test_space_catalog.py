import unittest, tempfile, sqlite3
from contextlib import contextmanager
from types import SimpleNamespace
from pathlib import Path
from findzia_space_catalog import ensure_catalog
from findzia_plans import SPACE_PLANS

class Catalog(unittest.TestCase):
 def test_idempotent_prices_and_no_transactions(self):
  with tempfile.TemporaryDirectory() as d:
   @contextmanager
   def connect():
    db=sqlite3.connect(Path(d)/'db');db.row_factory=sqlite3.Row
    try:
     with db:yield db
    finally:db.close()
   prices=[];writes=[]
   def api(method,path,body=None,envelope=False):
    if path=='/prices/old':return {'product_id':'pro_test','tax_mode':'external'}
    if method=='GET' and path.startswith('/prices?'):return {'data':prices,'meta':{'pagination':{'has_more':False}}}
    if method=='POST' and path=='/prices':
     writes.append(body);p={**body,'id':'pri_'+str(len(writes)).zfill(26),'status':'active'};prices.append(p);return p
    raise AssertionError((method,path))
   service=SimpleNamespace(ready=True,mode='sandbox',accounts=SimpleNamespace(connect=connect),api=api,prices={'pack':'old'})
   ensure_catalog(service);ensure_catalog(service)
   self.assertEqual(len(writes),3)
   self.assertEqual([p['unit_price']['amount'] for p in writes],['699','1499','2999'])
   self.assertTrue(all(p['billing_cycle'] is None for p in writes))
   self.assertEqual(set(service.prices),{'pack','space_starter','space_plus','space_pro'})

 def test_dashboard_prices_recover_pending_without_creating(self):
  for reuse_ids in (True,False,"separate"):
   with self.subTest(reuse_ids=reuse_ids), tempfile.TemporaryDirectory() as d:
    @contextmanager
    def connect():
     db=sqlite3.connect(Path(d)/'db');db.row_factory=sqlite3.Row
     try:
      with db:yield db
     finally:db.close()
    old={'pack':'old_starter','pack50':'old_plus','pack100':'old_pro'}
    prices=[dict(id=list(old.values())[i] if reuse_ids else 'new_'+p['id'],product_id=('pro_other_'+str(i) if reuse_ids=='separate' and i else 'pro_test'),
      status='active',billing_cycle=None,trial_period=None,
      unit_price={'amount':str(p['amount_cents']),'currency_code':'USD'}) for i,p in enumerate(SPACE_PLANS)]
    def api(method,path,body=None,envelope=False):
     self.assertEqual(method,'GET')
     if path=='/prices/old_starter':return {'product_id':'pro_test','tax_mode':'external'}
     if path.startswith('/prices?'):return {'data':[p for p in prices if p['product_id']=='pro_test'],'meta':{'pagination':{'has_more':False}}}
     match=next((p for p in prices if path=='/prices/'+p['id']),None)
     return match or dict(id=path.split('/')[-1],product_id='pro_test',status='active',unit_price={'amount':'499','currency_code':'USD'},billing_cycle=None)
    with connect() as db:
     db.execute('CREATE TABLE fz_space_paddle_catalog(mode TEXT,plan TEXT,price TEXT,state TEXT,updated INTEGER,PRIMARY KEY(mode,plan))')
     db.execute("INSERT INTO fz_space_paddle_catalog VALUES('live','space_starter',NULL,'creating',0)")
    service=SimpleNamespace(ready=True,mode='live',accounts=SimpleNamespace(connect=connect),api=api,prices=dict(old))
    ensure_catalog(service);ensure_catalog(service)
    for key,value in old.items():self.assertEqual(service.prices[key],value)
    for plan,price in zip(SPACE_PLANS,prices):self.assertEqual(service.prices[plan['id']],price['id'])
    with connect() as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM fz_space_paddle_catalog WHERE state='ready'").fetchone()[0],3)

 def test_manual_price_validation(self):
  from findzia_space_catalog import matches_plan
  plan=SPACE_PLANS[0]
  good=dict(product_id='pro_test',status='active',billing_cycle=None,trial_period=None,unit_price={'amount':'699','currency_code':'USD'})
  self.assertTrue(matches_plan(good,plan,'pro_test'))
  for change in ({'product_id':'pro_other'},{'status':'archived'},
    {'billing_cycle':{'interval':'month','frequency':1}},
    {'trial_period':{'interval':'day','frequency':7}},
    {'unit_price':{'amount':'499','currency_code':'USD'}},
    {'unit_price':{'amount':'699','currency_code':'EUR'}}):
   with self.subTest(change=change):self.assertFalse(matches_plan({**good,**change},plan,'pro_test'))

if __name__=='__main__':unittest.main()
