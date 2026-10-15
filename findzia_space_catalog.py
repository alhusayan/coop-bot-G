"""Create immutable one-time prices for the approved Space packs.

Uses the existing authorized Paddle adapter. Never changes old prices or creates
transactions. Durable attempts and a catalog lookup make uncertain POSTs safe.
"""
import time
from urllib.parse import urlencode
from findzia_plans import SPACE_PLANS

VERSION='findzia-space-flexible-v1'
EXISTING_PACKS={'space_starter':'pack','space_plus':'pack50','space_pro':'pack100'}

def matches_plan(price, plan, product):
    return (price.get('product_id')==product and price.get('status')=='active'
            and price.get('billing_cycle') is None and price.get('trial_period') is None
            and price.get('unit_price')=={'amount':str(plan['amount_cents']),'currency_code':'USD'})

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
        expected_product=product
        matches=[p for p in found if (p.get('custom_data') or {}).get('findzia_catalog')==VERSION and (p.get('custom_data') or {}).get('findzia_plan')==plan['id']]
        with service.accounts.connect() as db:
            saved=db.execute('SELECT * FROM fz_space_paddle_catalog WHERE mode=? AND plan=?',(service.mode,plan['id'])).fetchone()
        configured=service.prices.get(plan['id'])
        price=next((p for p in found if p.get('id')==configured),None) if configured else matches[0] if matches else None
        if configured and not price:price=service.api('GET','/prices/'+configured)
        if not price and saved and saved['price']:price=service.api('GET','/prices/'+saved['price'])
        if not price:
            # The owner may edit existing packs or add prices in the dashboard,
            # where our custom_data tags are absent. Resolve only the same product,
            # exact approved USD amount, and one-time billing before enabling it.
            candidates=[p for p in found if matches_plan(p,plan,product)]
            existing=service.prices.get(EXISTING_PACKS[plan['id']])
            price=next((p for p in candidates if p.get('id')==existing),None)
            if not price and existing:
                prior=next((p for p in found if p.get('id')==existing),None)
                if prior is None:prior=service.api('GET','/prices/'+existing)
                # Existing, explicitly configured pack IDs may belong to separate
                # products. Trust that known ID, while retaining amount/type checks.
                if prior.get('id')==existing and prior.get('product_id') and matches_plan(prior,plan,prior['product_id']):
                    price=prior;expected_product=prior['product_id']
                else:
                    unit=prior.get('unit_price') or {}
                    print('SPACES_PADDLE_EXISTING plan=%s amount=%s currency=%s recurring=%s' %
                          (plan['id'],unit.get('amount'),unit.get('currency_code'),bool(prior.get('billing_cycle'))),flush=True)
            if not price and len(candidates)==1:price=candidates[0]
            if not price and len(candidates)>1:raise RuntimeError('catalog_price_ambiguous')
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
        if price and (configured or (saved and saved['price'])) and price.get('id')==service.prices.get(EXISTING_PACKS[plan['id']]):
            expected_product=price.get('product_id')
        if not matches_plan(price,plan,expected_product):
            raise RuntimeError('catalog_price_mismatch')
        with service.accounts.connect() as db:
            db.execute('INSERT INTO fz_space_paddle_catalog VALUES(?,?,?,?,?) ON CONFLICT(mode,plan) DO UPDATE SET price=excluded.price,state=excluded.state,updated=excluded.updated',
                       (service.mode,plan['id'],price['id'],'ready',int(time.time())))
        service.prices[plan['id']]=price['id']
    print('SPACES_PADDLE_CATALOG ready=true packs=30:699,80:1499,180:2999 currency=USD recurring=false',flush=True)
