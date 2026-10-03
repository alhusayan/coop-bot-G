const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=readFileSync(path.join(__dirname,'../source/findzia-billing.js'),'utf8');
function section(start,end){const a=source.indexOf(start),b=source.indexOf(end,a);assert.ok(a>=0&&b>a);return source.slice(a,b);}
function load(code,env={}){const context={Promise,DOMException,AbortController,...env};vm.createContext(context);vm.runInContext(code,context);return context;}

test('account bootstrap abort settles immediately, even when shared work never resolves',async()=>{
 const c=load(section('  function abortable(', '  const el ='));
 const ctl=new AbortController();const pending=c.abortable(new Promise(()=>{}),ctl.signal);
 ctl.abort();await assert.rejects(pending,{name:'AbortError'});
 assert.equal(await c.abortable(Promise.resolve(42),new AbortController().signal),42);
});

test('pre-aborted bootstrap never produces an unhandled shared failure',async()=>{
 const c=load(section('  function abortable(', '  const el =')),ctl=new AbortController();ctl.abort();
 await assert.rejects(c.abortable(Promise.reject(Error('offline')),ctl.signal),{name:'AbortError'});
});

function restoreFixture({mf=true,paddle=true,fail='',balance=true,changeSession=false}={}){
 const calls=[],views=[];
 const env={paymentBusy:false,paymentMessage:'',revision:1,mfConfig:{enabled:mf,checkout_available:mf},paddleConfig:{restore_available:paddle},
 account:{member:()=>({id:'test'}),open:v=>views.push(v),render:()=>{}},tr:en=>en,paymentError:e=>e.message,
 paymentConfig:async()=>{},json:async endpoint=>{calls.push(endpoint);if(endpoint.includes(fail)&&fail)throw Error('provider_unavailable');return {ok:true};},
 refresh:async()=>{if(changeSession)c.revision++;return balance?{remaining:20}:null;}};
 const c=load(section('    async function restorePurchases()', '    function renderCheckout('),env);
 return {c,calls,views};
}

test('restore checks both payment providers for mixed purchase history',async()=>{
 const {c,calls}=restoreFixture();await c.restorePurchases();
 assert.deepEqual(calls,['/myfatoorah/restore','/paddle/restore']);
 assert.match(c.paymentMessage,/up to date/);assert.equal(c.paymentBusy,false);
});

test('partial provider outage does not claim every purchase was restored',async()=>{
 const {c,calls}=restoreFixture({fail:'myfatoorah'});await c.restorePurchases();
 assert.equal(calls.length,2);assert.match(c.paymentMessage,/Some purchases/);assert.equal(c.paymentBusy,false);
});

test('restore supports Paddle-only and detects a failed balance refresh',async()=>{
 const {c,calls}=restoreFixture({mf:false});await c.restorePurchases();assert.deepEqual(calls,['/paddle/restore']);
 const b=restoreFixture({balance:false});await b.c.restorePurchases();assert.equal(b.c.paymentMessage,'credits_unavailable');
});

test('logout during restore cannot announce success for the previous account',async()=>{
 const {c}=restoreFixture({changeSession:true});await c.restorePurchases();assert.doesNotMatch(c.paymentMessage,/up to date/);
});

test('payment failure unlocks same-transaction recovery and shows an actionable message',()=>{
 const body=section("      if(e.name==='checkout.payment.failed'",'      // Programmatic closes');
 for(const name of ['checkout.payment.failed','checkout.payment.error']){
  let message='';const view={paying:true,fallback:{disabled:true}};
  load(body,{e:{name},view,tr:en=>en,checkoutHelp:text=>message=text});
  assert.equal(view.paying,false);assert.equal(view.fallback.disabled,false);assert.match(message,/another card/);
 }
});
