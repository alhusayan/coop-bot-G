"""Findzia account service. OAuth is enabled only with explicit production config.

Google/Apple identity is verified with PyJWT and their fixed public-key endpoints.
No billing entitlement is created by a browser action. Saved/history stay on-device.
"""
import asyncio
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlencode, urlsplit, parse_qs

import requests
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
try:
    import jwt
except ImportError:
    jwt = None

PROVIDERS = {
    'google': {'authorize':'https://accounts.google.com/o/oauth2/v2/auth',
               'token':'https://oauth2.googleapis.com/token',
               'jwks':'https://www.googleapis.com/oauth2/v3/certs',
               'issuers':['https://accounts.google.com','accounts.google.com']},
    'apple': {'authorize':'https://appleid.apple.com/auth/authorize',
              'token':'https://appleid.apple.com/auth/token',
              'jwks':'https://appleid.apple.com/auth/keys',
              'issuers':['https://appleid.apple.com']},
}

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def challenge(value):
    return base64.urlsafe_b64encode(hashlib.sha256(value.encode()).digest()).decode().rstrip('=')

def origin(value):
    try:
        u=urlsplit(value)
        return f'{u.scheme}://{u.netloc}' if u.scheme=='https' and u.hostname and not u.username and not u.password else ''
    except (TypeError,ValueError): return ''

def display_name(value, strict=False):
    """A display label only; never used to verify or link an identity."""
    if not isinstance(value,str) or len(value)>1024:
        if strict:raise HTTPException(400,'invalid_name')
        return ''
    value=unicodedata.normalize('NFC',value)
    value=re.sub(r'[\x00-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]',' ',value)
    value=' '.join(value.split())
    if '<' in value or '>' in value or (strict and len(value)>100):
        if strict:raise HTTPException(400,'invalid_name')
        return ''
    return value[:100].strip()

def apple_display_name(raw):
    # Apple sends this optional JSON form field on the first consent only.
    # Read it only after code/token/state validation. Its email is not trusted.
    if not isinstance(raw,str) or len(raw)>4096:return ''
    try:
        user=json.loads(raw)
    except (ValueError,TypeError,RecursionError):return ''
    name=user.get('name') if isinstance(user,dict) else None
    if not isinstance(name,dict):return ''
    parts=[display_name(name.get(key,'')) for key in ('firstName','lastName')]
    return display_name(' '.join(part for part in parts if part))

class Accounts:
    def __init__(self, config=None):
        env=os.environ if config is None else config
        self.db_path=env.get('FINDZIA_ACCOUNT_DB','')
        self.base=env.get('FINDZIA_ACCOUNT_API_URL','').rstrip('/')
        self.origins={x.strip() for x in env.get('FINDZIA_ACCOUNT_ORIGINS','https://findzia.com,https://www.findzia.com').split(',') if origin(x.strip())==x.strip()}
        self.ids={p:env.get('FINDZIA_'+p.upper()+'_CLIENT_ID','') for p in PROVIDERS}
        self.google_secret=env.get('FINDZIA_GOOGLE_CLIENT_SECRET','')
        self.apple_team=env.get('FINDZIA_APPLE_TEAM_ID','')
        self.apple_key_id=env.get('FINDZIA_APPLE_KEY_ID','')
        self.apple_key=env.get('FINDZIA_APPLE_PRIVATE_KEY','').replace('\\n','\n')
        self.available=bool(jwt and self.db_path and Path(self.db_path).is_absolute() and origin(self.base)==self.base and self.origins)
        self.keys={}
        self.lock=threading.Lock()
        self.rate={}
        if self.available:
            try:
                Path(self.db_path).parent.mkdir(parents=True,exist_ok=True)
                self.initialize()
            except (OSError,sqlite3.Error):
                self.available=False
                print('ACCOUNTS: persistent database unavailable; sign-in disabled')

    def connect(self):
        db=sqlite3.connect(self.db_path,timeout=5)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def initialize(self):
        with self.connect() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS fz_members(id TEXT PRIMARY KEY,provider TEXT NOT NULL,subject TEXT NOT NULL,email TEXT NOT NULL,name TEXT NOT NULL,phone TEXT NOT NULL DEFAULT '',created INTEGER NOT NULL,name_custom INTEGER NOT NULL DEFAULT 0,UNIQUE(provider,subject));
            CREATE TABLE IF NOT EXISTS fz_sessions(hash TEXT PRIMARY KEY,member TEXT NOT NULL REFERENCES fz_members(id),expires INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS fz_oauth(state TEXT PRIMARY KEY,provider TEXT NOT NULL,nonce TEXT NOT NULL,verifier TEXT NOT NULL,challenge TEXT NOT NULL,flow TEXT NOT NULL,return_to TEXT NOT NULL,expires INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS fz_exchange(hash TEXT PRIMARY KEY,member TEXT NOT NULL REFERENCES fz_members(id),challenge TEXT NOT NULL,flow TEXT NOT NULL,origin TEXT NOT NULL,expires INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS fz_sessions_expiry ON fz_sessions(expires);
            CREATE INDEX IF NOT EXISTS fz_oauth_expiry ON fz_oauth(expires);
            CREATE INDEX IF NOT EXISTS fz_exchange_expiry ON fz_exchange(expires);
            ''')
            # Preserve existing accounts, sessions and credit tables on upgrade.
            db.execute('BEGIN IMMEDIATE')
            if 'name_custom' not in {row['name'] for row in db.execute('PRAGMA table_info(fz_members)')}:
                db.execute('ALTER TABLE fz_members ADD COLUMN name_custom INTEGER NOT NULL DEFAULT 0')
        os.chmod(self.db_path,0o600)

    def enabled(self,p):
        return self.available and isinstance(p,str) and p in PROVIDERS and bool(self.ids[p]) and bool(self.google_secret if p=='google' else self.apple_key and self.apple_team and self.apple_key_id)

    def config(self):
        return {'ok':True,'providers':{p:self.enabled(p) for p in PROVIDERS},
                'billing':{'available':False,'restore':False,'upgrade':False},
                'saved_scope':'device','history_scope':'device','usage_scope':'device'}

    def allow_request(self,request,mutation=True):
        if mutation and request.headers.get('origin') not in self.origins:
            raise HTTPException(403,'origin_not_allowed')
        # Only the immediate peer is trusted. Do not accept spoofable X-Forwarded-For.
        key=request.client.host if request.client else 'unknown';now=time.monotonic()
        with self.lock:
            entries=[t for t in self.rate.get(key,[]) if now-t<60]
            if len(entries)>=40:raise HTTPException(429,'try_later')
            entries.append(now);self.rate[key]=entries
            if len(self.rate)>4096:
                self.rate={k:v for k,v in self.rate.items() if v and now-v[-1]<60}

    async def body(self,request):
        raw=b''
        async for chunk in request.stream():
            raw+=chunk
            if len(raw)>8192:raise HTTPException(413,'request_too_large')
        try:
            value=json.loads(raw)
            if not isinstance(value,dict):raise ValueError()
            return value
        except (ValueError,TypeError):raise HTTPException(400,'invalid_request')

    def clean_expired(self,db):
        for table in ('fz_oauth','fz_exchange','fz_sessions'):
            db.execute(f'DELETE FROM {table} WHERE expires < ?',(int(time.time()),))

    def prepare(self,payload,request_origin):
        p=payload.get('provider');ret=payload.get('return_to','');ch=payload.get('challenge','');flow=payload.get('flow','')
        if not self.enabled(p):raise HTTPException(503,'sign_in_unavailable')
        if not isinstance(ret,str) or len(ret)>2048 or origin(ret)!=request_origin or request_origin not in self.origins or urlsplit(ret).fragment or any(c in ret for c in '\r\n\\'):
            raise HTTPException(400,'invalid_return_url')
        if not isinstance(ch,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',ch) or not isinstance(flow,str) or not re.fullmatch(r'[A-Za-z0-9_-]{24,100}',flow):
            raise HTTPException(400,'invalid_challenge')
        state=secrets.token_urlsafe(32);nonce=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48)
        with self.connect() as db:
            self.clean_expired(db)
            db.execute('INSERT INTO fz_oauth VALUES(?,?,?,?,?,?,?,?)',(digest(state),p,nonce,verifier,ch,flow,ret,int(time.time())+600))
        params={'client_id':self.ids[p],'redirect_uri':self.base+'/api/account/auth/'+p+'/callback','response_type':'code','state':state,'nonce':nonce}
        if p=='google':params.update(scope='openid email profile',code_challenge=challenge(verifier),code_challenge_method='S256',prompt='select_account')
        else:params.update(scope='name email',response_mode='form_post')
        return {'ok':True,'authorize_url':PROVIDERS[p]['authorize']+'?'+urlencode(params)}

    def apple_secret(self):
        now=int(time.time())
        return jwt.encode({'iss':self.apple_team,'iat':now,'exp':now+300,'aud':'https://appleid.apple.com','sub':self.ids['apple']},self.apple_key,algorithm='ES256',headers={'kid':self.apple_key_id})

    def verify(self,p,token,nonce):
        if not isinstance(token,str) or len(token)>20000:raise ValueError('invalid_identity')
        # Never choose the key URL or allowed algorithm from an untrusted token.
        header=jwt.get_unverified_header(token)
        if header.get('alg')!='RS256':raise ValueError('invalid_algorithm')
        with self.lock:
            if p not in self.keys:self.keys[p]=jwt.PyJWKClient(PROVIDERS[p]['jwks'],cache_jwk_set=True,lifespan=3600,timeout=5)
            keys=self.keys[p]
        key=keys.get_signing_key_from_jwt(token).key
        claims=jwt.decode(token,key,algorithms=['RS256'],audience=self.ids[p],issuer=PROVIDERS[p]['issuers'],leeway=30,
                          options={'require':['sub','iss','aud','exp','iat','nonce']})
        if not hmac.compare_digest(str(claims['nonce']),nonce):raise ValueError('invalid_nonce')
        if claims.get('azp') and claims['azp']!=self.ids[p]:raise ValueError('invalid_presenter')
        if not isinstance(claims['sub'],str) or not 1<=len(claims['sub'])<=255:raise ValueError('invalid_subject')
        return claims

    def complete(self,p,params):
        state=params.get('state','');code=params.get('code','')
        if not self.enabled(p) or not isinstance(state,str) or len(state)>200:raise HTTPException(400,'invalid_sign_in')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM fz_oauth WHERE state=? AND provider=? AND expires>?',(digest(state),p,int(time.time()))).fetchone()
            if not row:raise HTTPException(400,'sign_in_expired')
            db.execute('DELETE FROM fz_oauth WHERE state=?',(digest(state),))
        row=dict(row)
        failure=row['return_to']+'#findzia-auth-error=sign_in_failed'
        if params.get('error') or not isinstance(code,str) or not code or len(code)>4096:return failure
        try:
            data={'grant_type':'authorization_code','client_id':self.ids[p],'client_secret':self.google_secret if p=='google' else self.apple_secret(),
                  'code':code,'redirect_uri':self.base+'/api/account/auth/'+p+'/callback'}
            if p=='google':data['code_verifier']=row['verifier']
            response=requests.post(PROVIDERS[p]['token'],data=data,timeout=(3,7),allow_redirects=False)
            response.raise_for_status();claims=self.verify(p,response.json().get('id_token'),row['nonce'])
            verified=claims.get('email_verified') in (True,'true')
            email=str(claims.get('email') or '')[:254] if verified else ''
            name=apple_display_name(params.get('user')) if p=='apple' else display_name(claims.get('name',''))
            handoff=secrets.token_urlsafe(32);now=int(time.time())
            with self.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                found=db.execute('SELECT id FROM fz_members WHERE provider=? AND subject=?',(p,claims['sub'])).fetchone()
                uid=found['id'] if found else secrets.token_urlsafe(18)
                if found:
                    if email:db.execute('UPDATE fz_members SET email=? WHERE id=?',(email,uid))
                    if name:db.execute("UPDATE fz_members SET name=? WHERE id=? AND name='' AND name_custom=0",(name,uid))
                else:db.execute('INSERT INTO fz_members(id,provider,subject,email,name,created) VALUES(?,?,?,?,?,?)',(uid,p,claims['sub'],email,name,now))
                # Never merge accounts solely because their email addresses match.
                db.execute('INSERT INTO fz_exchange VALUES(?,?,?,?,?,?)',(digest(handoff),uid,row['challenge'],row['flow'],origin(row['return_to']),now+90))
            return row['return_to']+'#'+urlencode({'findzia-login':handoff,'flow':row['flow']})
        except Exception:
            # Tokens, codes and personal data are deliberately not logged.
            return failure

    def exchange(self,payload,request_origin):
        if not self.available:raise HTTPException(503,'sign_in_unavailable')
        code=payload.get('code','');verifier=payload.get('verifier','');flow=payload.get('flow','')
        if not isinstance(code,str) or len(code)>200 or not isinstance(verifier,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43,128}',verifier):
            raise HTTPException(400,'invalid_exchange')
        now=int(time.time())
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM fz_exchange WHERE hash=? AND expires>?',(digest(code),now)).fetchone()
            if not row or row['origin']!=request_origin or row['flow']!=flow or not hmac.compare_digest(row['challenge'],challenge(verifier)):
                raise HTTPException(400,'invalid_exchange')
            db.execute('DELETE FROM fz_exchange WHERE hash=?',(digest(code),))
            token=secrets.token_urlsafe(48);expires=now+43200
            db.execute('INSERT INTO fz_sessions VALUES(?,?,?)',(digest(token),row['member'],expires))
        return {'ok':True,'access_token':token,'expires_at':expires,'member':self.member(token)}

    def token(self,request):
        value=request.headers.get('authorization','')
        if not value.startswith('Bearer ') or len(value)>256:raise HTTPException(401,'sign_in_required')
        return value[7:]

    def member(self,token):
        if not self.available:raise HTTPException(401,'sign_in_required')
        with self.connect() as db:
            row=db.execute('SELECT m.id,m.provider,m.email,m.name,m.phone FROM fz_sessions s JOIN fz_members m ON m.id=s.member WHERE s.hash=? AND s.expires>?',(digest(token),int(time.time()))).fetchone()
        if not row:raise HTTPException(401,'session_expired')
        return dict(row)

    def phone(self,token,value):
        # Keep the old phone-only contract for callers already using it.
        return self.profile(token,{'phone':value})

    def profile(self,token,payload):
        member=self.member(token)
        if not isinstance(payload,dict):raise HTTPException(400,'invalid_request')
        updates={}
        if 'name' in payload:
            updates['name']=display_name(payload['name'],strict=True)
            updates['name_custom']=1
        if 'phone' in payload:
            value=payload['phone']
            if not isinstance(value,str):raise HTTPException(400,'invalid_phone')
            value=re.sub(r'[\s()-]','',value)
            if value and not re.fullmatch(r'\+[1-9][0-9]{6,14}',value):raise HTTPException(400,'invalid_phone')
            updates['phone']=value
        # Only the explicitly allowed fields above can be changed. Validate
        # everything before the atomic write; partial updates preserve others.
        if updates:
            with self.connect() as db:
                db.execute('UPDATE fz_members SET '+','.join(key+'=?' for key in updates)+' WHERE id=?',(*updates.values(),member['id']))
        return {'ok':True,'member':self.member(token),'phone_verified':False}

    def logout(self,token):
        if self.available:
            with self.connect() as db:db.execute('DELETE FROM fz_sessions WHERE hash=?',(digest(token),))
        return {'ok':True}


def install_accounts(app):
    service=Accounts();app.state.findzia_accounts=service
    def result(data,status=200):return JSONResponse(data,status_code=status,headers={'Cache-Control':'no-store'})

    @app.get('/api/account/config')
    async def config():
        value=service.config()
        credits=getattr(app.state,'findzia_credits',None)
        if credits:
            value.update(usage_scope='account',credits=credits.public_config())
        return result(value)

    @app.post('/api/account/auth/start')
    async def start(request:Request):
        service.allow_request(request)
        payload=await service.body(request)
        return result(await asyncio.to_thread(service.prepare,payload,request.headers['origin']))

    @app.api_route('/api/account/auth/{provider}/callback',methods=['GET','POST'])
    async def callback(provider:str,request:Request):
        service.allow_request(request,False)
        if request.method=='POST':
            raw=b''
            async for chunk in request.stream():
                raw+=chunk
                if len(raw)>16384:raise HTTPException(413,'request_too_large')
            try:params={k:v[0] for k,v in parse_qs(raw.decode('utf-8','replace'),max_num_fields=16).items()}
            except ValueError:raise HTTPException(400,'invalid_callback')
        else:params=dict(request.query_params)
        try:dest=await asyncio.to_thread(service.complete,provider,params)
        except HTTPException:
            return HTMLResponse('<!doctype html><meta name="viewport" content="width=device-width"><title>Findzia</title><p>This sign-in link has expired. Return to Findzia and try again.</p>',status_code=400,headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'none'"})
        return RedirectResponse(dest,status_code=303,headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})

    @app.post('/api/account/auth/exchange')
    async def exchange(request:Request):
        service.allow_request(request);payload=await service.body(request)
        return result(await asyncio.to_thread(service.exchange,payload,request.headers['origin']))

    @app.get('/api/account/me')
    async def me(request:Request):
        service.allow_request(request,False)
        member=await asyncio.to_thread(service.member,service.token(request))
        credits=getattr(app.state,'findzia_credits',None)
        balance=await asyncio.to_thread(credits.status,member['id']) if credits and credits.available else None
        return result({'ok':True,'member':member,'credits':balance,
                       'subscription':balance.get('subscription') if balance else {'status':'unavailable'},
                       'limit':balance.get('remaining') if balance else None})

    @app.post('/api/account/profile')
    async def profile(request:Request):
        service.allow_request(request);payload=await service.body(request)
        return result(await asyncio.to_thread(service.profile,service.token(request),payload))

    @app.post('/api/account/logout')
    async def logout(request:Request):
        service.allow_request(request)
        return result(await asyncio.to_thread(service.logout,service.token(request)))

    @app.post('/api/account/restore')
    async def restore(request:Request):
        service.allow_request(request)
        return result({'ok':False,'error':'purchases_not_connected'},503)
