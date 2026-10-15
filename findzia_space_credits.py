"""Flexible units, category-limited free trial, and atomic multi-grant debits.

Old search credits are converted once at 2 units each, preserving buying power.
Only the authenticated Spaces service may reserve/settle image generation.
"""
import time
from fastapi import HTTPException

DESIGN_PATH = '/internal/spaces/design'

class SpaceCreditPolicy:
    def __init__(self, credits):
        self.c = credits
        with credits.accounts.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS fz_space_allocations(
              member TEXT NOT NULL,request TEXT NOT NULL,grant_id TEXT NOT NULL,
              units INTEGER NOT NULL,category TEXT NOT NULL,
              PRIMARY KEY(member,request,grant_id));
            CREATE TABLE IF NOT EXISTS fz_space_conversions(grant_id TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS fz_space_trial(
              grant_id TEXT PRIMARY KEY,design INTEGER NOT NULL,search INTEGER NOT NULL);
            ''')
            db.execute('BEGIN IMMEDIATE')
            self.convert(db, int(time.time()))

    def convert(self, db, now):
        rows=db.execute("""SELECT g.* FROM fz_credit_grants g
          LEFT JOIN fz_space_conversions m ON m.grant_id=g.id
          WHERE m.grant_id IS NULL AND g.plan NOT LIKE 'space_%'""").fetchall()
        for row in rows:
            db.execute('UPDATE fz_credit_grants SET quantity=quantity*2,remaining=remaining*2 WHERE id=?',(row['id'],))
            db.execute('INSERT INTO fz_space_conversions VALUES(?)',(row['id'],))
            self.c.ledger(db,row['member'],row['id'],None,row['remaining'],'flexible_credit_conversion',now)
            # A reservation admitted by the preceding release must refund its
            # converted value, even when completion arrives after this migration.
            for r in db.execute("SELECT * FROM fz_credit_requests WHERE grant_id=? AND state='reserved'",(row['id'],)).fetchall():
                db.execute('INSERT OR IGNORE INTO fz_space_allocations VALUES(?,?,?,?,?)',
                           (r['member'],r['request'],row['id'],2,'search'))

    def claim(self, db, member, now):
        gid='trial:'+member
        db.execute('INSERT INTO fz_credit_grants VALUES(?,?,?,?,?,?,?,?,0)',(gid,member,'trial','space_trial',7,7,now,None))
        db.execute('INSERT INTO fz_space_trial VALUES(?,?,?)',(gid,3,4))
        self.c.ledger(db,member,gid,None,7,'trial',now)

    def allowance(self, db, member, category):
        return db.execute(f'''SELECT COALESCE(SUM(t.{category}),0) FROM fz_space_trial t
          JOIN fz_credit_grants g ON g.id=t.grant_id WHERE g.member=? AND g.revoked=0''',(member,)).fetchone()[0]

    def snapshot(self, db, member, data):
        data.update(credit_unit='flexible',design_cost=1,search_cost=2,
                    free_designs=self.allowance(db,member,'design'),
                    free_searches=self.allowance(db,member,'search')//2)
        data['paid_remaining']=data['balances']['pack']+data['balances']['subscription']
        # Legacy trial units are flexible; new trial units retain their category.
        restricted=db.execute('''SELECT COALESCE(SUM(g.remaining),0) FROM fz_credit_grants g
          JOIN fz_space_trial t ON t.grant_id=g.id WHERE g.member=? AND g.revoked=0''',(member,)).fetchone()[0]
        data['flexible_remaining']=data['remaining']-restricted
        return data

    def reserve(self, member, ids, path):
        from findzia_billing import REQUEST_ID
        if not 1<=len(ids)<=3 or len(set(ids))!=len(ids) or any(not REQUEST_ID.fullmatch(r or '') for r in ids):
            raise HTTPException(400,'request_id_required')
        category='design' if path==DESIGN_PATH else 'search'
        units=1 if category=='design' else 2
        now=int(time.time());day=now//86400*86400
        with self.c.accounts.connect() as db:
            db.execute('BEGIN IMMEDIATE');self.c.recover(db,now)
            existing=[db.execute('''SELECT r.* FROM fz_credit_requests r JOIN fz_credit_grants g ON g.id=r.grant_id
              WHERE (r.member=? OR g.member=?) AND r.request=?''',(member,member,rid)).fetchone() for rid in ids]
            if any(existing):
                # Service retries with the same identity recover an uncertain
                # admission; public search replays never start paid work again.
                if category=='design' and all(r and r['state']=='reserved' and r['path']==path for r in existing):
                    return [{'member':r['member'],'request':r['request']} for r in existing]
                raise HTTPException(409,'search_in_progress' if any(r and r['state']=='reserved' for r in existing) else 'search_already_processed')
            active=db.execute('''SELECT COUNT(*) FROM fz_credit_requests r JOIN fz_credit_grants g ON g.id=r.grant_id
              WHERE g.member=? AND r.state='reserved' AND (r.path=? OR (?='search' AND r.path!=?))''',
              (member,DESIGN_PATH if category=='design' else path,category,DESIGN_PATH)).fetchone()[0]
            if active+len(ids)>(3 if category=='design' else 2):raise HTTPException(429,'search_in_progress')
            attempts=db.execute("SELECT COUNT(*) FROM fz_credit_requests r JOIN fz_credit_grants g ON g.id=r.grant_id WHERE g.kind='trial' AND r.created>=?",(day,)).fetchone()[0]
            for rid in ids:
                rows=db.execute('''SELECT g.*,t.design,t.search FROM fz_credit_grants g
                  LEFT JOIN fz_space_trial t ON t.grant_id=g.id
                  WHERE g.member=? AND g.remaining>0 AND g.revoked=0 AND g.starts<=? AND (g.expires IS NULL OR g.expires>?)
                  ORDER BY CASE g.kind WHEN 'trial' THEN 0 WHEN 'subscription' THEN 1 ELSE 2 END,COALESCE(g.expires,9223372036854775807),g.starts,g.id''',(member,now,now)).fetchall()
                remaining=units;alloc=[]
                for row in rows:
                    if row['kind']=='trial' and attempts>=self.c.trial_daily_attempts:continue
                    available=row['remaining'] if row[category] is None else min(row['remaining'],row[category])
                    take=min(remaining,available)
                    if take:alloc.append((row,take));remaining-=take
                    if not remaining:break
                if remaining:raise HTTPException(402,'credits_exhausted')
                db.execute('INSERT INTO fz_credit_requests VALUES(?,?,?,?,?,?,?,NULL)',(member,rid,alloc[0][0]['id'],category if category=='design' else ('image' if '/image' in path else 'text'),path,'reserved',now))
                for row,take in alloc:
                    db.execute('UPDATE fz_credit_grants SET remaining=remaining-? WHERE id=?',(take,row['id']))
                    if row[category] is not None:db.execute(f'UPDATE fz_space_trial SET {category}={category}-? WHERE grant_id=?',(take,row['id']))
                    db.execute('INSERT INTO fz_space_allocations VALUES(?,?,?,?,?)',(member,rid,row['id'],take,category))
                    self.c.ledger(db,member,row['id'],rid,-take,'reserve',now)
                if any(row['kind']=='trial' for row,_ in alloc):attempts+=1
            return [{'member':member,'request':rid} for rid in ids]

    def refund(self, db, row, now, reason):
        allocations=db.execute('SELECT * FROM fz_space_allocations WHERE member=? AND request=?',(row['member'],row['request'])).fetchall()
        if not allocations:
            allocations=[dict(grant_id=row['grant_id'],units=1,category='search')]
        for item in allocations:
            db.execute('UPDATE fz_credit_grants SET remaining=remaining+? WHERE id=?',(item['units'],item['grant_id']))
            category=item['category']
            db.execute(f'UPDATE fz_space_trial SET {category}={category}+? WHERE grant_id=?',(item['units'],item['grant_id']))
            self.c.ledger(db,row['member'],item['grant_id'],row['request'],item['units'],reason,now)
