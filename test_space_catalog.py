import unittest, tempfile, sqlite3
from contextlib import contextmanager
from types import SimpleNamespace
from pathlib import Path
from findzia_space_catalog import ensure_catalog

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

if __name__=='__main__':unittest.main()
