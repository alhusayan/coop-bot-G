"""Create immutable one-time prices for the approved Space packs.

Uses the existing authorized Paddle adapter. Never changes old prices or creates
transactions. Durable attempts and a catalog lookup make uncertain POSTs safe.
"""
import time
from urllib.parse import urlencode
from findzia_plans import SPACE_PLANS

VERSION='findzia-space-flexible-v1'

def ensure_catalog(service):
    if not service.ready:return
    with service.accounts.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS fz_space_paddle_catalog(mode TEXT,plan TEXT,price TEXT,state TEXT,updated INTEGER,PRIMARY KEY(mode,plan))')
    base=service.api('GET','/prices/'+service.prices['pack'])
    product=base['product_id']
    found=[];after=None
    for _ in range(20):
        query={'product_id':product,'per_page':200,'status':'active'}
        if after:query['after']=after
        page=service.api('GET','/prices?'+urlencode(query),envelope=True)
        found.extend(page.get('data') or [])
        if not page.get('meta',{}).get('pagination',{}).get('has_more'):break
        if not page.get('data'):raise RuntimeError('catalog_pagination')
        after=page['data'][-1]['id']
    else:raise RuntimeError('catalog_pagination')
    for plan in SPACE_PLANS:
        matches=[p for p in found if (p.get('custom_data') or {}).get('findzia_catalog')==VERSION and (p.get('custom_data') or {}).get('findzia_plan')==plan['id']]
        with service.accounts.connect() as db:
            saved=db.execute('SELECT * FROM fz_space_paddle_catalog WHERE mode=? AND plan=?',(service.mode,plan['id'])).fetchone()
        configured=service.prices.get(plan['id'])
        price=next((p for p in found if p.get('id')==configured),None) if configured else matches[0] if matches else None
        if configured and not price:price=service.api('GET','/prices/'+configured)
        if not price and saved and saved['price']:price=service.api('GET','/prices/'+saved['price'])
        if not price:
            # After an ambiguous create, list-only retries avoid duplicate prices.
            if saved and saved['state']=='creating':raise RuntimeError('catalog_creation_uncertain')
            with service.accounts.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                if db.execute('SELECT 1 FROM fz_space_paddle_catalog WHERE mode=? AND plan=?',(service.mode,plan['id'])).fetchone():raise RuntimeError('catalog_creation_pending')
                db.execute('INSERT INTO fz_space_paddle_catalog VALUES(?,?,NULL,?,?)',(service.mode,plan['id'],'creating',int(time.time())))
            price=service.api('POST','/prices',{'product_id':product,'description':VERSION+' '+plan['id'],
              'name':plan['name']+' — '+str(plan['credits'])+' credits',
              'billing_cycle':None,'trial_period':None,'tax_mode':base.get('tax_mode','account_setting'),
              'unit_price':{'amount':str(plan['amount_cents']),'currency_code':'USD'},
              'quantity':{'minimum':1,'maximum':1},
              'custom_data':{'findzia_catalog':VERSION,'findzia_plan':plan['id']}})
        if (price.get('product_id')!=product or price.get('status')!='active' or price.get('billing_cycle') is not None
            or price.get('trial_period') is not None or price.get('unit_price')!={'amount':str(plan['amount_cents']),'currency_code':'USD'}):
            raise RuntimeError('catalog_price_mismatch')
        with service.accounts.connect() as db:
            db.execute('INSERT INTO fz_space_paddle_catalog VALUES(?,?,?,?,?) ON CONFLICT(mode,plan) DO UPDATE SET price=excluded.price,state=excluded.state,updated=excluded.updated',
                       (service.mode,plan['id'],price['id'],'ready',int(time.time())))
        service.prices[plan['id']]=price['id']
    print('SPACES_PADDLE_CATALOG ready=true packs=30:699,80:1499,180:2999 currency=USD recurring=false',flush=True)
