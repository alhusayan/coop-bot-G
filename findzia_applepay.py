"""Findzia 156.7.14: registration diagnostics for the 156.7.13 Apple Pay window.

The parent storefront keeps its embedded card checkout. This top-level page
uses MyFatoorah's SDK on an origin whose verification file we can actually
serve. No account bearer, PAN, Apple payment token or provider key enters URLs.
Registration success is a prerequisite, not a claim that a live charge passed.
"""
import asyncio
import hashlib
import json
import logging
import re
import secrets
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

LOG = logging.getLogger(__name__)
FILE = Path(__file__).with_name('apple-developer-merchantid-domain-association')
WELL_KNOWN = '/.well-known/apple-developer-merchantid-domain-association'
PAGE_PATH = '/findzia/apple-pay'
API = '/api/billing/myfatoorah/apple-pay'
HEADERS = {'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
           'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY'}
DIAGNOSTIC_BUILD = '156714'


def diagnostic_text(value, secret_values=()):
    """Bounded provider error text, never a response/body/header dump."""
    if not isinstance(value, str):
        return ''
    # Redact before truncation so a partial credential cannot survive the cap.
    for secret in sorted((s for s in secret_values if isinstance(s, str) and s), key=len, reverse=True):
        value = value.replace(secret, '[redacted]')
    value = re.sub(r'(?i)\bBearer\s+\S+', 'Bearer [redacted]', value)
    value = re.sub(r'(?i)\b(?:authorization|api[_ -]?key|access[_ -]?token|secret|password)\s*[:=]\s*\S+',
                   '[redacted credential]', value)
    # Keep the domain/file path useful for diagnosis; omit URL queries/fragments.
    value = re.sub(r'(https?://[^\s\"\'<>?#]+)[?#][^\s\"\'<>]*', r'\1[redacted]', value)
    value = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[redacted email]', value)
    value = re.sub(r'[A-Za-z0-9_+/=.\-]{48,}', '[redacted token]', value)
    value = re.sub(r'\b(?:\d[ -]?){12,19}\b', '[redacted number]', value)
    value = ''.join(' ' if ord(c) < 32 or 127 <= ord(c) <= 159 or c in '\u2028\u2029' else c for c in value)
    return ' '.join(value.split())[:600]


def registration_diagnostic(response, data, secret_values):
    """Only documented error fields. In particular, Data is never logged."""
    result = {'http': response.status_code, 'response_format': 'json' if isinstance(data, dict) else 'non_object_or_non_json'}
    if not isinstance(data, dict):
        return result
    result['provider_success'] = data.get('IsSuccess') if isinstance(data.get('IsSuccess'), bool) else None
    if response.status_code == 200 and data.get('IsSuccess') is True:
        return result
    message = diagnostic_text(data.get('Message'), secret_values)
    if message:
        result['provider_message'] = message
    errors = data.get('ValidationErrors')
    if isinstance(errors, list):
        clean = []
        for error in errors[:4]:
            if not isinstance(error, dict):
                continue
            # Do not log Name, supplied Value, or any undocumented fields.
            message = diagnostic_text(error.get('Error'), secret_values)
            if message:
                clean.append(message)
        if clean:
            result['validation_errors'] = clean
    return result


def origin(value):
    try:
        u = urlsplit(value)
        if (u.scheme != 'https' or u.username or u.password or u.port or
                u.query or u.fragment or u.path not in ('', '/') or
                not re.fullmatch(r'(?=.{1,253}$)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', u.hostname or '') or
                '.' not in u.hostname or re.fullmatch(r'[\d.]+', u.hostname)):
            raise ValueError()
        return 'https://' + u.hostname
    except (ValueError, TypeError):
        raise ValueError('FINDZIA_APPLE_PAY_ORIGIN must be a public HTTPS origin') from None


class ApplePayWindow:
    def __init__(self, service, env):
        self.s = service
        self.origin = ''
        self.ready = False
        self.state = 'missing_origin'
        self.task = None
        self.next_check = 0
        self.file = b''
        value = env.get('FINDZIA_APPLE_PAY_ORIGIN', '').strip()
        self.origin_source = 'FINDZIA_APPLE_PAY_ORIGIN' if value else 'unset'
        if not value:
            domain = env.get('RAILWAY_PUBLIC_DOMAIN', '').strip()
            if domain:
                value = domain if domain.startswith('https://') else 'https://' + domain
                self.origin_source = 'RAILWAY_PUBLIC_DOMAIN'
            elif env.get('PUBLIC_BASE_URL', '').strip():
                value = env['PUBLIC_BASE_URL'].strip()
                self.origin_source = 'PUBLIC_BASE_URL'
        self.configured = bool(value)
        if not value:
            return
        try:
            self.origin = origin(value)
            # A distinct top-level origin is intentional; an iframe under the
            # unverified Shopify origin does not solve merchant validation.
            if self.origin in ('https://findzia.com', 'https://www.findzia.com'):
                raise ValueError('Use the independent payment server origin')
        except ValueError:
            self.origin = ''
            self.state = 'invalid_origin'
            return
        try:
            self.file = FILE.read_bytes()
            decoded = json.loads(bytes.fromhex(self.file.decode().strip()))
            if decoded.get('pspId') != 'C552A3D050E8C2C5F3D36AB26FCB8DBF0F085F2C8AFC29BB329A2071C4527C6B':
                raise ValueError('wrong provider verification file')
            if not service.ready or not service.embedded:
                self.state = 'checkout_not_ready'
                return
            self.state = 'awaiting_registration'
        except OSError:
            self.state = 'missing_verification_file'
            return
        except (ValueError, KeyError, UnicodeError):
            self.state = 'invalid_verification_file'
            return
        with self.s.accounts.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS fz_mf_apple_domains(
                    domain_key TEXT PRIMARY KEY, verified INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS fz_mf_apple_windows(
                    token_hash TEXT PRIMARY KEY, intent TEXT NOT NULL,
                    member TEXT NOT NULL, email TEXT NOT NULL,
                    expires INTEGER NOT NULL, language TEXT NOT NULL,
                    theme TEXT NOT NULL);
            ''')

    def public(self, member):
        return {'available': bool(self.ready and self.s.allowed(member)),
                'origin': self.origin, 'status': self.state, 'origin_source': self.origin_source}

    def verify_and_register(self):
        """Bounded, non-payment setup; never turns readiness on from an env flag."""
        if not self.origin or not self.file or not self.s.ready or not self.s.embedded:
            return
        now = int(time.time())
        if now < self.next_check:
            return
        self.next_check = now + 300
        detail = {'build': DIAGNOSTIC_BUILD, 'domain': urlsplit(self.origin).hostname,
                  'stage': 'verification_file'}
        try:
            response = requests.get(self.origin + WELL_KNOWN, timeout=(3, 10), allow_redirects=False)
            detail['http'] = response.status_code
            if response.status_code != 200 or response.content.strip() != self.file.strip():
                self.ready = False
                self.state = 'verification_file_mismatch'
                return
            key = hashlib.sha256((self.origin + '\0' + self.s.mode + '\0' + self.s.key + '\0').encode() + self.file).hexdigest()
            with self.s.accounts.connect() as db:
                row = db.execute('SELECT verified FROM fz_mf_apple_domains WHERE domain_key=?', (key,)).fetchone()
            if not row:
                # This documented endpoint returns Data:null on SUCCESS. The
                # normal v3 payment wrapper correctly expects Data to be a dict.
                detail['stage'] = 'registration'
                detail.pop('http', None)
                response = requests.post(self.s.base + '/v2/RegisterApplePayDomain',
                    headers={'Authorization': 'Bearer ' + self.s.key},
                    json={'DomainName': urlsplit(self.origin).hostname},
                    timeout=(3, 15), allow_redirects=False)
                try:
                    data = response.json()
                except ValueError:
                    data = None
                detail.update(registration_diagnostic(response, data, (self.s.key, self.s.secret)))
                if response.status_code != 200 or not isinstance(data, dict) or data.get('IsSuccess') is not True:
                    self.ready = False
                    self.state = 'registration_rejected'
                    return
                with self.s.accounts.connect() as db:
                    db.execute('INSERT OR REPLACE INTO fz_mf_apple_domains VALUES(?,?)', (key, now))
            else:
                detail['stage'] = 'registration_cache'
            self.ready = True
            self.state = 'registered'
            self.next_check = now + 86400
        except (requests.RequestException, ValueError, OSError) as error:
            self.ready = False
            self.state = 'registration_unavailable'
            # Exception strings may contain request headers or response bodies.
            detail['error_type'] = ('timeout' if isinstance(error, requests.Timeout) else
                                    'tls' if isinstance(error, requests.exceptions.SSLError) else
                                    'connection' if isinstance(error, requests.ConnectionError) else 'request_failed')
        finally:
            LOG.warning('MF_APPLE_PAY status=%s', self.state)
            detail['status'] = self.state
            LOG.warning('MF_APPLE_PAY_DETAIL %s', json.dumps(detail, ensure_ascii=True, separators=(',', ':')))

    def open(self, member, intent, language='en', theme='light'):
        self.s.require(member)
        if not self.ready:
            raise HTTPException(503, 'apple_pay_not_registered')
        # Retire only an unused card form. It cannot subsequently be charged
        # while its replacement Apple Pay form is open on another origin.
        with self.s.accounts.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT state FROM fz_mf_orders WHERE intent=? AND member=? AND mode=?',
                (intent, member['id'], self.s.mode)).fetchone()
            if not row:
                raise HTTPException(404, 'payment_not_found')
            if row['state'] != 'session_ready':
                raise HTTPException(409, 'payment_already_started')
            db.execute("UPDATE fz_mf_orders SET state='canceled' WHERE intent=?", (intent,))
        data = self.s.embedded_session(member, 'pack')
        if not data.get('session_id'):
            return data  # Already-paid / unresolved attempts retain the normal guard.
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        with self.s.accounts.connect() as db:
            db.execute('DELETE FROM fz_mf_apple_windows WHERE expires<?', (now,))
            db.execute('INSERT INTO fz_mf_apple_windows VALUES(?,?,?,?,?,?,?)',
                (hashlib.sha256(token.encode()).hexdigest(), data['intent'], member['id'], member.get('email', ''),
                 now + 900, 'ar' if language == 'ar' else 'en', 'dark' if theme == 'dark' else 'light'))
        return {'intent': data['intent'], 'url': self.origin + PAGE_PATH + '#' + token}

    def ticket(self, token):
        if not self.ready or not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
            raise HTTPException(403, 'apple_pay_window_expired')
        with self.s.accounts.connect() as db:
            row = db.execute('SELECT * FROM fz_mf_apple_windows WHERE token_hash=? AND expires>?',
                (hashlib.sha256(token.encode()).hexdigest(), int(time.time()))).fetchone()
        if not row:
            raise HTTPException(403, 'apple_pay_window_expired')
        member = {'id': row['member'], 'email': row['email']}
        self.s.require(member)
        return dict(row), member

    def session(self, row):
        with self.s.accounts.connect() as db:
            payment = db.execute('''SELECT o.state,s.session,s.expires FROM fz_mf_orders o
                JOIN fz_mf_sessions s ON s.intent=o.intent WHERE o.intent=? AND o.member=? AND o.mode=?''',
                (row['intent'], row['member'], self.s.mode)).fetchone()
        if not payment or payment['state'] != 'session_ready' or payment['expires'] <= time.time() + 10:
            raise HTTPException(409, 'payment_already_started')
        return {'intent': row['intent'], 'session_id': payment['session'],
                'language': row['language'], 'theme': row['theme']}

    def cancel(self, member, intent):
        self.s.require(member)
        with self.s.accounts.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT state FROM fz_mf_orders WHERE intent=? AND member=? AND mode=?',
                (intent, member['id'], self.s.mode)).fetchone()
            if not row:
                raise HTTPException(404, 'payment_not_found')
            if row['state'] == 'session_ready':
                db.execute("UPDATE fz_mf_orders SET state='canceled' WHERE intent=?", (intent,))
        return self.s.resume(member, intent)

    async def worker(self):
        # Let ASGI start accepting requests before checking our own public file.
        await asyncio.sleep(3)
        while True:
            try:
                await asyncio.to_thread(self.verify_and_register)
            except Exception:
                LOG.warning('MF_APPLE_PAY status=setup_unavailable')
            await asyncio.sleep(60)


def install_applepay(app, service, env, member):
    bridge = ApplePayWindow(service, env)
    service.apple_window = bridge

    def result(data):
        return JSONResponse({'ok': True, **data}, headers=HEADERS)

    def own_origin(request):
        # Do not trust arbitrary forwarded Host headers or token query strings.
        if not bridge.origin or request.url.hostname != urlsplit(bridge.origin).hostname:
            raise HTTPException(404, 'not_found')

    def ticket(request):
        own_origin(request)
        if request.headers.get('origin') not in (None, bridge.origin):
            raise HTTPException(403, 'origin_not_allowed')
        auth = request.headers.get('authorization', '')
        return bridge.ticket(auth[7:] if auth.startswith('Bearer ') else '')

    @app.on_event('startup')
    async def startup():
        LOG.warning('MF_APPLE_PAY status=%s source=%s domain=%s',
                    bridge.state, bridge.origin_source, urlsplit(bridge.origin).hostname or 'unset')
        if bridge.state == 'awaiting_registration':
            bridge.task = asyncio.create_task(bridge.worker())

    @app.on_event('shutdown')
    async def shutdown():
        if bridge.task:
            bridge.task.cancel()
            try:
                await bridge.task
            except asyncio.CancelledError:
                pass

    @app.get(WELL_KNOWN)
    async def association(request: Request):
        own_origin(request)
        if not bridge.file:
            raise HTTPException(404, 'not_found')
        return Response(bridge.file, media_type='text/plain', headers={'Cache-Control': 'public, max-age=300', 'X-Content-Type-Options': 'nosniff'})

    @app.get(PAGE_PATH)
    async def page(request: Request):
        own_origin(request)
        config = {'api': API, 'returnOrigin': 'https://' + urlsplit(service.return_url).hostname,
                  'sdk': ('https://demo.myfatoorah.com' if service.mode == 'sandbox' else 'https://portal.myfatoorah.com') + '/sessions/v1/session.js'}
        nonce = secrets.token_urlsafe(18)
        html = PAGE.replace('__CONFIG__', json.dumps(config).replace('<', '\\u003c')).replace('__NONCE__', nonce)
        return HTMLResponse(html, headers={**HEADERS,
            'Content-Security-Policy': "default-src 'none'; script-src 'nonce-" + nonce + "' 'strict-dynamic'; style-src 'unsafe-inline'; frame-src https://*.myfatoorah.com; connect-src 'self' https://*.myfatoorah.com; img-src data: https://*.myfatoorah.com; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
            'Permissions-Policy': 'payment=(self "https://portal.myfatoorah.com" "https://demo.myfatoorah.com")'})

    @app.post(API + '/open')
    async def open_window(request: Request):
        m = await member(request)
        body = await service.accounts.body(request)
        return result(await asyncio.to_thread(bridge.open, m, body.get('intent'), body.get('language'), body.get('theme')))

    @app.post(API + '/cancel')
    async def cancel_window(request: Request):
        m = await member(request)
        body = await service.accounts.body(request)
        return result(await asyncio.to_thread(bridge.cancel, m, body.get('intent')))

    @app.post(API + '/session')
    async def window_session(request: Request):
        row, _ = ticket(request)
        return result(await asyncio.to_thread(bridge.session, row))

    @app.post(API + '/complete')
    async def window_complete(request: Request):
        row, m = ticket(request)
        return result(await asyncio.to_thread(service.complete_session, m, row['intent']))

    @app.post(API + '/status')
    async def window_status(request: Request):
        row, m = ticket(request)
        return result(await asyncio.to_thread(service.resume, m, row['intent']))

    return bridge


PAGE = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Findzia · Apple Pay</title>
<style>
:root{color-scheme:light;--bg:#f7f7f3;--card:#fff;--ink:#26342c;--muted:#657166;--line:#dfe5df;--action:#394e40}
:root[data-theme=dark]{color-scheme:dark;--bg:#0e1915;--card:#1d2922;--ink:#f3f5ef;--muted:#c1cbbf;--line:#415346;--action:#dde8d7}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,Arial,sans-serif;min-height:100dvh;display:grid;place-items:center;padding:24px}
main{width:100%;max-width:420px;background:var(--card);border:1px solid var(--line);border-radius:24px;padding:28px;box-shadow:0 12px 40px #00000009}
.brand{font:36px/1.2 Georgia,serif;letter-spacing:-1.4px;margin:0 0 28px}.brand i{color:#ed852f;font-style:normal}
h1{font-size:22px;margin:0 0 8px}p{color:var(--muted);margin:0 0 24px}.amount{display:flex;justify-content:space-between;gap:16px;margin:20px 0;color:var(--ink)}
#wallet{background:#fff;border-radius:12px;padding:8px;min-height:64px;color-scheme:light}#status{font-size:14px;margin:16px 0;min-height:21px;overflow-wrap:anywhere}
button,a{font:inherit;min-height:44px}button{width:100%;border:1px solid var(--line);background:transparent;color:var(--ink);border-radius:12px;padding:10px 16px;cursor:pointer}button:disabled{opacity:.55}a{display:block;text-align:center;color:var(--ink);padding:10px;text-underline-offset:4px}button:focus-visible,a:focus-visible{outline:3px solid #db9a52;outline-offset:3px}[hidden]{display:none!important}
</style></head><body><main><p class="brand">Findz<i>i</i>a</p><h1 id="title">Apple Pay</h1>
<div class="amount"><span id="quantity">20 searches</span><strong dir="ltr">$4.99 USD</strong></div>
<p id="once">One payment. No renewal.</p><div id="wallet"></div><p id="status" role="status" aria-live="polite">Loading…</p>
<button id="check" hidden>Check payment</button><a id="back">Back to Findzia</a></main>
<script nonce="__NONCE__">
(()=>{'use strict';const config=__CONFIG__,token=location.hash.slice(1);history.replaceState(null,'',location.pathname);
const $=id=>document.getElementById(id),state={submitted:false,busy:false,polls:0,intent:'',lang:'en'},tr=(en,ar)=>state.lang==='ar'?ar:en;
$('back').href=config.returnOrigin;let timer;
async function api(path){const ctrl=new AbortController(),timeout=setTimeout(()=>ctrl.abort(),35000);try{const r=await fetch(config.api+path,{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:'{}',signal:ctrl.signal,credentials:'omit',cache:'no-store'});const d=await r.json();if(!r.ok)throw Error('payment_unavailable');return d;}finally{clearTimeout(timeout);}}
function notify(){try{window.opener?.postMessage({type:'fz:apple-pay-check',intent:state.intent},config.returnOrigin);}catch(_){}}
function done(){clearTimeout(timer);$('wallet').hidden=true;$('check').hidden=true;$('title').textContent=tr('Payment confirmed','تم تأكيد الدفع');$('status').textContent=tr('Your 20 searches have been added.','تمت إضافة 20 بحثًا لرصيدك.');notify();}
function waiting(){ $('wallet').hidden=true;$('check').hidden=false;$('status').textContent=tr('Confirming your payment…','نتحقق من دفعتك…');notify();clearTimeout(timer);if(state.polls<12)timer=setTimeout(check,5000);else $('status').textContent=tr('Payment is still unconfirmed. Check again shortly.','لم يتأكد الدفع بعد. تحقق مرة ثانية بعد قليل.');}
async function check(){if(state.busy)return;state.busy=true;state.polls++;$('check').disabled=true;try{const d=await api('/status');if(d.confirmed)done();else if(d.ready_for_payment){$('status').textContent=tr('Payment did not complete. Return to Findzia to try again.','لم يكتمل الدفع. ارجع إلى Findzia للمحاولة مجددًا.');notify();}else waiting();}catch(_){$('status').textContent=tr('Could not confirm yet. Check again shortly.','تعذّر التأكيد حاليًا. تحقق مرة ثانية بعد قليل.');$('check').hidden=false;}finally{state.busy=false;$('check').disabled=false;}}
$('check').onclick=check;$('back').onclick=e=>{if(window.opener){e.preventDefault();notify();window.close();}};
async function complete(response){if(state.submitted)return;if(response?.isSuccess!==true){$('status').textContent=tr('Apple Pay was not completed. Try again.','لم يكتمل Apple Pay. حاول مرة ثانية.');return;}state.submitted=true;$('wallet').hidden=true;$('status').textContent=tr('Confirming your payment…','نتحقق من دفعتك…');try{const d=await api('/complete');if(d.confirmed){done();return;}if(d.url||d.authentication_url){const u=new URL(d.url||d.authentication_url);if(u.protocol!=='https:'||!['portal.myfatoorah.com','demo.myfatoorah.com','pay.myfatoorah.com','www.myfatoorah.com','myfatoorah.com'].includes(u.hostname)||u.username||u.password||u.port)throw Error();notify();location.assign(u.href);return;}waiting();}catch(_){waiting();}}
(async()=>{try{if(!/^[A-Za-z0-9_-]{43}$/.test(token))throw Error();const d=await api('/session');state.intent=d.intent;state.lang=d.language;document.documentElement.lang=d.language;document.documentElement.dir=d.language==='ar'?'rtl':'ltr';document.documentElement.dataset.theme=d.theme;$('quantity').textContent=tr('20 searches','20 عملية بحث');$('once').textContent=tr('One payment. No renewal.','دفعة واحدة، بدون تجديد.');$('back').textContent=tr('Back to Findzia','العودة إلى Findzia');$('check').textContent=tr('Check payment','تحقق من الدفع');const script=document.createElement('script');script.src=config.sdk;await new Promise((resolve,reject)=>{const deadline=setTimeout(()=>reject(Error()),12000);script.onload=()=>{clearTimeout(deadline);resolve();};script.onerror=()=>{clearTimeout(deadline);reject(Error());};document.head.append(script);});timer=setTimeout(()=>{$('status').textContent=tr('Apple Pay could not load. Return to Findzia and try again.','تعذّر تحميل Apple Pay. ارجع إلى Findzia وحاول مجددًا.');},15000);window.myfatoorah.init({sessionId:d.session_id,containerId:'wallet',shouldHandlePaymentUrl:false,subscribedEvents:['VIEW_READY','SESSION_STARTED','SESSION_CANCELED'],eventListener:e=>{if(e?.name==='VIEW_READY'){clearTimeout(timer);$('status').textContent=tr('Tap Apple Pay to continue.','اضغط Apple Pay للمتابعة.');}if(e?.name==='SESSION_STARTED')clearTimeout(timer);if(e?.name==='SESSION_CANCELED')$('status').textContent=tr('Payment canceled. You can try again.','تم إلغاء الدفع. تقدر تحاول مرة ثانية.');},settings:{applePay:{isEnabled:true,language:d.language,style:{frameWidth:'100%',frameHeight:'48px',button:{height:'48px',type:'pay',borderRadius:'10px'}}},googlePay:{isEnabled:false},card:{isEnabled:false}},callback:complete});}catch(_){$('wallet').hidden=true;$('status').textContent=tr('This payment window is unavailable or expired. Return to Findzia to retry.','نافذة الدفع غير متاحة أو انتهت صلاحيتها. ارجع إلى Findzia للمحاولة.');}})();
})();
</script></body></html>'''
