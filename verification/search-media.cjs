/* All services, including payments, are mocked. No paid requests are made. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {pathToFileURL}=require('node:url');
const out=process.env.FINDZIA_TEST_OUTPUT||path.resolve(__dirname,'../../verification');fs.mkdirSync(out,{recursive:true});
const picture='<svg xmlns="http://www.w3.org/2000/svg" width="200" height="240"><rect width="200" height="240" rx="22" fill="#e8e9e3"/><path d="M80 58h40v40l20 100H60L80 98Z" fill="#ae9981"/></svg>';
const offers=Array.from({length:5},(_,i)=>({title:'Decorative vase '+i,store:'Test shop',url:'https://store.example.test/vase-'+i,image:'https://store.example.test/photo-'+i+'.svg',price:'20.000 KWD',currency:'KWD',country:'KW',market:'local',result_group:'local',photo_match_status:'approved',price_display_ready:true,price_display_currency:'KWD',price_amount:20,price_contract:'findzia-money-v1',price_display_major:'20',price_display_minor:'.000',evaluation_token:'fixture-'+i}));

offers[0].image='https://store.example.test/a9f8.png';offers[0].images=['https://store.example.test/product-0.png'];
offers[1].image='https://store.example.test/a9f8.png';offers[1].images=['https://store.example.test/product-1.png'];
offers[2].image='https://store.example.test/b4f2.png';
offers[3].image='https://store.example.test/shirt-logo-print.png';
offers[4].image='https://store.example.test/c2d3.png';
(async()=>{
 const {createServer}=await import(pathToFileURL(path.resolve(__dirname,'../server.mjs')));
 const server=createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({executablePath:process.env.FINDZIA_TEST_CHROME,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']});
 let checks=0;
 async function fixture({width=390,lang='en',theme='light',payment='paddle',layout='list',recovery='clear',checkoutDelay=600,checkoutResult='normal',confirmDelay=0,mediaDelay=150}={}){
  const context=await browser.newContext({viewport:{width,height:844},locale:lang==='ar'?'ar-KW':'en-GB',colorScheme:theme,reducedMotion:'no-preference'});
  const calls=[],errors=[];let paidCredits=0;
  await context.addInitScript(({lang,theme,payment,layout})=>{
   localStorage.setItem('findzia-results-layout-v1',layout);localStorage.setItem('findzia-appearance-v1',theme);localStorage.setItem('findzia-lang',lang);localStorage.setItem('findzia-lang-KW',lang);
   sessionStorage.setItem('findzia-account-v1-session',JSON.stringify({access_token:'test-member-token',expires_at:Math.floor(Date.now()/1000)+3600}));
   if(false)sessionStorage.setItem('findzia-mf-return-v1',JSON.stringify({intent:'fixture-intent',payment:'fixture-payment',owner:'test',at:Date.now()}));
  },{lang,theme,payment,layout});
  await context.route('**/*',async route=>{
   const u=new URL(route.request().url()),p=u.pathname;
   if(u.origin==='https://findzia.com'){const r=await fetch(origin+p+u.search);return route.fulfill({status:r.status,headers:Object.fromEntries(r.headers),body:Buffer.from(await r.arrayBuffer())});}
   if(u.origin==='https://api.findzia.com'){
    let data={ok:true};const payload=route.request().postData()?JSON.parse(route.request().postData()):{};calls.push({path:p,payload});
    if(p==='/api/geo')Object.assign(data,{country:'KW',country_code:'KW',country_name:'Kuwait'});
    else if(p==='/api/account/config')data.providers={google:true,apple:true};
    else if(p==='/api/account/me')data.member={id:'test',email:'fixture@example.test',name:'Test',provider:'google'};
    else if(p==='/api/billing/config')Object.assign(data,{prepaid_enabled:true,payment_provider:payment==='mf'?'myfatoorah':'paddle',plans:[{id:'pack',name:'20 searches',credits:20,amount_cents:499,interval:'once'},{id:'pack50',name:'50 searches',credits:50,amount_cents:999,interval:'once',recommended:true},{id:'pack100',name:'100 searches',credits:100,amount_cents:1799,interval:'once'}]});
    else if(p==='/api/billing/status'||p==='/api/billing/guest')Object.assign(data,{remaining:20+paidCredits,balances:{trial:20,pack:paidCredits},guest_token:'test-token'});
    else if(p==='/api/billing/myfatoorah/config')Object.assign(data,{enabled:false,checkout_available:false,embedded_available:false,restore_available:true});
    else if(p==='/api/billing/paddle/config')Object.assign(data,{enabled:payment==='paddle',checkout_available:payment==='paddle',restore_available:true,paddle_environment:'sandbox',paddle_client_token:'test_fixture',checkout_plan_ids:['pack','pack50','pack100']});
    else if(p==='/api/billing/myfatoorah/restore'){
     if(recovery==='unavailable')return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({ok:false,detail:'payment_verification_unavailable'})});
     data.payment_pending=['pending','ignored'].includes(recovery);data.blocks_checkout=recovery!=='ignored';
    }
    else if(p==='/api/billing/paddle/restore')data.ok=true;
    else if(p==='/api/billing/myfatoorah/confirm'||p==='/api/billing/myfatoorah/resume')data.confirmed=payment==='success';
    else if(['/api/search/stream','/api/search/image/stream','/api/refine/search/stream'].includes(p)){
     const photo=p.includes('/image/'),refine=p.includes('/refine/');
     const rows=offers.map(item=>({...item,search_origin:photo?'image':'text',retrieval_sources:[photo?'google_lens':'serper_search'],...(refine?{refinement_verified:true}:{})}));
     const events=[{event:'query',query:payload.query||'Decorative vase'},...rows.map(item=>({event:'result',item})),{event:'done',results:rows}];
     return route.fulfill({contentType:'application/x-ndjson',body:events.map(e=>JSON.stringify(e)+'\n').join('')});
    }
    else if(p==='/api/media/check'){
     await new Promise(r=>setTimeout(r,mediaDelay));
     data.usable=!/a9f8|b4f2|c2d3/.test(payload.image);data.decision=data.usable?'product':'logo';
    }
    else if(p==='/api/media/recover'){
     if(payload.token==='fixture-2'){data.images=['https://store.example.test/recovered.png'];data.media_token='recovered-bound-token';}
     else data.images=[];
    }
    else if(p==='/api/guide/discover'){
     const step=payload.answers?.length||0;
     Object.assign(data,{status:'question',question:'Choose detail '+(step+1),question_key:'detail_'+step,choices:[{label:'Choice '+(step+1),answer:'detail'+step},{label:'Another choice',answer:'other'+step}],search_query:[payload.kind==='image'?'':payload.query,...(payload.answers||[])].filter(Boolean).join(' ')});
    }
    else if(p==='/api/billing/paddle/checkout'){await new Promise(r=>setTimeout(r,checkoutDelay));if(checkoutResult==='error')return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({ok:false,error:'paddle_checkout_rejected'})});data.transaction_id='txn_fixture';if(checkoutResult==='pending')Object.assign(data,{payment_pending:true,retry_after:3});}
    else if(p==='/api/billing/paddle/confirm'){if(confirmDelay)await new Promise(r=>setTimeout(r,confirmDelay));data.confirmed=true;const id=calls.find(c=>c.path.endsWith('/paddle/checkout')).payload.plan_id;paidCredits={pack:20,pack50:50,pack100:100}[id];}
    else if(p==='/api/billing/myfatoorah/session'){await new Promise(r=>setTimeout(r,100));Object.assign(data,{intent:'mf_fixture',session_id:'session_fixture'});}
    else if(p==='/api/billing/myfatoorah/session/complete'){data.confirmed=true;const id=calls.find(c=>c.path.endsWith('/myfatoorah/session')).payload.plan_id;paidCredits={pack:20,pack50:50,pack100:100}[id];}
    else if(p==='/api/stores/ratings')data.ratings=[];
    else if(p==='/api/ui/translate')Object.assign(data,{lang:payload.lang,translations:{}});
    else if(p==='/api/refine/options')Object.assign(data,{adaptive:true,plan_token:'fixture',category:'Vase',selection:{},ranges:{},children:[],facets:[]});
    else throw Error('Unexpected API '+p);
    return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
   }
   if(u.hostname==='portal.myfatoorah.com'&&p.endsWith('/session.js'))return route.fulfill({contentType:'application/javascript',body:`window.__mfInits=[];window.myfatoorah={init(o){window.__mfInits.push(o);window.__mfCallback=o.callback;setTimeout(()=>o.eventListener({name:'VIEW_READY'}),5);}};`});
   if(u.hostname==='cdn.paddle.com')return route.fulfill({contentType:'application/javascript',body:`
    window.__opens=[];window.__closes=0;
    window.Paddle={Environment:{set(){}},Initialize(o){window.__callback=o.eventCallback;},Checkout:{
     open(o){window.__opens.push(o);if(o.settings.frameTarget){const host=document.querySelector('.'+o.settings.frameTarget),f=document.createElement('iframe');f.title='Mock Paddle checkout';f.srcdoc='<button>Apple Pay fixture</button>';f.style.cssText='width:100%;height:'+o.settings.frameInitialHeight+'px;border:0';host.append(f);}},
     close(){window.__closes++;document.querySelectorAll('.fzb-wallet-frame iframe').forEach(f=>f.remove());}
    }};
    window.__emit=(name,extra={})=>window.__callback({name,data:{id:'che_fixture',transaction_id:'txn_fixture',settings:{display_mode:'inline'},currency_code:'USD',totals:{subtotal:4.99,tax:0,total:4.99},...extra}});
   `});
   if(u.origin==='https://store.example.test')return route.fulfill({contentType:'image/svg+xml',body:picture});
   if(u.hostname==='fonts.googleapis.com')return route.fulfill({contentType:'text/css',body:''});
   errors.push('Unexpected URL '+u.href);return route.abort();
  });
  const page=await context.newPage();page.setDefaultTimeout(10000);page.on('pageerror',e=>errors.push(e.message));
  await page.goto('https://findzia.com/',{waitUntil:'networkidle'});
  await page.waitForFunction(()=>document.querySelector('.fz-home')?.fzBilling?.status()?.remaining===20);
  return {context,page,calls,errors};
 }

 try{
  for(const [lang,theme,method] of [['en','light','click'],['ar','dark','enter']]){
   const {context,page,calls,errors}=await fixture({lang,theme,mediaDelay:400});
   await page.evaluate(()=>{window.__topCalls=0;const scroll=window.scrollTo;window.scrollTo=function(...args){if(args[0]?.top===0)window.__topCalls++;return scroll.apply(this,args);};});
   const home=page.locator('[data-dark-input]');await home.fill('Ball');
   if(method==='click')await page.locator('[data-dark-submit]').click();else await home.press('Enter');
   const active=await page.evaluate(()=>document.activeElement?.matches('input,textarea'));
   assert.equal(active,false);checks++;
   assert.ok(await page.evaluate(()=>window.__topCalls>0));checks++;
   await page.waitForFunction(()=>document.querySelectorAll('.fz-media-stage img').length===4);
   const sources=await page.locator('.fz-media-stage img').evaluateAll(nodes=>nodes.map(n=>n.src));
   assert.ok(sources.every(src=>!/a9f8|b4f2|c2d3/.test(src)));checks++;
   assert.ok(sources.some(src=>src.includes('shirt-logo-print')));checks++;
   assert.ok(sources.some(src=>src.includes('recovered')));checks++;
   assert.equal(calls.filter(c=>c.path==='/api/media/check'&&c.payload.image.includes('a9f8')).length,1);checks++;
   assert.equal(calls.find(c=>c.path==='/api/media/check'&&c.payload.image.includes('recovered')).payload.token,'recovered-bound-token');checks++;
   assert.equal(await page.locator('a[href="https://store.example.test/vase-4"]').count(),0);checks++;
   await page.screenshot({path:path.join(out,`verified-cards-${lang}.png`),fullPage:true});
   await page.waitForFunction(()=>!document.querySelector('.fz-home').fzRefineBridge.context().busy);
   const result=await page.evaluate(()=>{
    const input=document.querySelector('[id^="fz-query-"]');
    document.body.style.minHeight='2500px';input.focus({preventScroll:true});input.value='Tennis Ball';input.dispatchEvent(new Event('input',{bubbles:true}));
    window.scrollTo({top:500,behavior:'instant'});window.__before=scrollY;
    document.querySelector('[data-search-btn]').click();
    return {before:window.__before,after:scrollY,focused:document.activeElement===input};
   });
   assert.ok(result.before>0);assert.equal(result.after,0);assert.equal(result.focused,false);checks+=3;
   await page.evaluate(()=>{window.scrollTo({top:180,behavior:'instant'});visualViewport.dispatchEvent(new Event('resize'));});
   await page.waitForFunction(()=>scrollY===0);checks++;
   await page.evaluate(()=>{window.dispatchEvent(new Event('touchstart'));window.scrollTo({top:250,behavior:'instant'});visualViewport.dispatchEvent(new Event('resize'));});
   await page.waitForTimeout(100);assert.equal(await page.evaluate(()=>scrollY),250);checks++;
   await page.waitForFunction(()=>!document.querySelector('.fz-home').fzRefineBridge.context().busy);
   const input=page.locator('[id^="fz-query-"]');await input.fill('Basketball');await input.press('Enter');
   assert.equal(await page.evaluate(()=>document.activeElement?.matches('input,textarea')),false);checks++;
   await page.waitForFunction(()=>document.querySelectorAll('.fz-media-stage img').length===4);
   assert.deepEqual(errors,[]);checks++;
   console.log('PASS home/results submit, focus, scroll and verified/recovered media:',lang,theme);
   await context.close();
  }
  // An image is never painted while its AI verdict is pending.
  const {context,page,calls,errors}=await fixture({mediaDelay:1200});
  await page.locator('[data-dark-input]').fill('Chair');await page.locator('[data-dark-input]').press('Enter');
  await page.waitForFunction(()=>document.querySelector('.fz-home').fzRefineBridge.snapshot().view.items.length>0);
  await page.waitForTimeout(250);
  assert.equal(await page.locator('.fz-media-stage img').count(),0);checks++;
  await page.waitForFunction(()=>document.querySelectorAll('.fz-media-stage img').length===4);
  assert.deepEqual(errors,[]);checks++;
  await context.close();
  console.log('PASSED',checks,'search focus, scroll and image admission assertions; providers mocked.');
 }finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
