/* Browser integration test: all API, store-image and PSP traffic is mocked.
   Run with Playwright installed and FINDZIA_TEST_CHROME pointing to Chromium.
   This does NOT exercise a live Apple wallet, provider or payment. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {pathToFileURL}=require('node:url');
const out=process.env.FINDZIA_TEST_OUTPUT || path.join(__dirname,'../../../work-browser');
fs.mkdirSync(out,{recursive:true});
const picture='<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300"><rect width="300" height="300" fill="#f0f0ec"/><rect x="70" y="50" width="160" height="150" rx="18" fill="#728578"/><path d="M85 200v60M215 200v60" stroke="#3b4e41" stroke-width="14"/></svg>';
const offers=[1,2,3].map((n)=>({title:'Test chair '+n,store:'Test store '+n,url:'https://store.example.test/chair-'+n,
 image:'https://store.example.test/image-'+n+'.svg',price:(20*n)+'.000 KWD',currency:'KWD',country:'KW',market:'local',
 result_group:'local',photo_match_status:'approved',price_display_ready:true,price_display_currency:'KWD',price_amount:20*n,
 price_contract:'findzia-money-v1',price_display_major:String(20*n),price_display_minor:'.000',evaluation_token:'test-'+n}));
(async()=>{
 const {createServer}=await import(pathToFileURL(path.resolve(__dirname,'../server.mjs')));
 const server=createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({executablePath:process.env.FINDZIA_TEST_CHROME,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  for(const variant of [{width:390,lang:'en',scheme:'light'},{width:390,lang:'ar',scheme:'dark'},{width:1440,lang:'en',scheme:'light'},{width:320,lang:'ar',scheme:'dark'}]){
   const context=await browser.newContext({viewport:{width:variant.width,height:844},colorScheme:variant.scheme,locale:variant.lang==='ar'?'ar-KW':'en-GB'});
   const calls=[],errors=[],violations=[],unexpected=[];let remaining=10;
   await context.addInitScript(({lang,scheme})=>{
    localStorage.setItem('findzia-lang',lang);localStorage.setItem('findzia-lang-KW',lang);
    sessionStorage.setItem('findzia-account-v1-session',JSON.stringify({access_token:'test-member-token',expires_at:Math.floor(Date.now()/1000)+3600}));
    document.addEventListener('securitypolicyviolation',e=>window.__cspErrors=(window.__cspErrors||[]).concat(e.effectiveDirective+':'+e.blockedURI));
   },variant);
   await context.route('**/*',async route=>{
    const url=new URL(route.request().url()), p=url.pathname;
    if(url.origin==='https://findzia.com'){
     const r=await fetch(origin+p+url.search);return route.fulfill({status:r.status,headers:Object.fromEntries(r.headers),body:Buffer.from(await r.arrayBuffer())});
    }
    if(url.origin==='https://api.findzia.com'){
     calls.push(p);let data={ok:true};let status=200;
     if(p==='/api/geo')Object.assign(data,{country:'KW',country_code:'KW',country_name:'Kuwait'});
     else if(p==='/api/account/config')data.providers={google:true,apple:true};
     else if(p==='/api/account/me')data.member={id:'test-member',email:'fixture@example.test',name:'Test shopper',provider:'google'};
     else if(p==='/api/billing/config')data.plans=[{id:'pack',credits:20,amount_cents:499,interval:'once'}];
     else if(p==='/api/billing/status'||p==='/api/billing/guest')Object.assign(data,{remaining,balances:{trial:remaining,pack:0},guest_token:'test-guest-token'});
     else if(p==='/api/billing/paddle/config')Object.assign(data,{checkout_available:false});
     else if(p==='/api/billing/myfatoorah/config')Object.assign(data,{enabled:true,checkout_available:true,environment:'live',embedded_available:true,checkout_mode:'embedded',apple_pay_inline:{available:true,origins:['https://findzia.com']}});
     else if(p==='/api/billing/myfatoorah/resume')data.ready_for_payment=true;
     else if(p==='/api/billing/myfatoorah/session')Object.assign(data,{intent:'test-intent',session_id:'test-session'});
     else if(p==='/api/billing/myfatoorah/session/complete'){data.confirmed=true;remaining+=20;}
     else if(p==='/api/search/stream'||p==='/api/search/image/stream'){
      const events=[{event:'query',query:'chair'},...offers.map(item=>({event:'result',item})),{event:'done'}];
      return route.fulfill({status:200,contentType:'application/x-ndjson',body:events.map(x=>JSON.stringify(x)+'\n').join('')});
     }else if(p==='/api/refine/options')Object.assign(data,{adaptive:true,plan_token:'test-plan',category:'Chair',selection:{},ranges:{},children:[],facets:[{key:'color',label:'Colour',options:[{label:'Black',token:'black',value_id:'black'},{label:'White',token:'white',value_id:'white'}]}]});
     else if(p==='/api/guide/context')Object.assign(data,{query:'chair',available:true,status:'ready'});
     else if(p==='/api/guide/discover')Object.assign(data,{available_modes:['guided'],groups:{},question:'Where will you use it?',question_key:'use',choices:[{label:'Home',answer:'Home',search_query:'home chair'},{label:'Office',answer:'Office',search_query:'office chair'}],suggestions:[]});
     else if(p==='/api/guide')Object.assign(data,{status:'ready',question:'Where will you use it?',question_key:'use',choices:[{label:'Home',answer:'Home',search_query:'home chair'},{label:'Office',answer:'Office',search_query:'office chair'}],recommendations:[]});
     else if(p==='/api/stores/ratings')Object.assign(data,{ratings:[]});
     else if(p==='/api/ui/translate')Object.assign(data,{lang:JSON.parse(route.request().postData()).lang,translations:{}});
     else{unexpected.push(p);status=404;data={ok:false,error:'test_not_mocked'};}
     return route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
    }
    if(url.origin==='https://store.example.test')return route.fulfill({status:200,contentType:'image/svg+xml',body:picture});
    if(url.hostname.endsWith('myfatoorah.com')&&p.endsWith('/session.js'))return route.fulfill({status:200,contentType:'text/javascript',body:`window.__mfInits=[];window.myfatoorah={init:function(c){window.__mfInits.push(c);var s=document.getElementById(c.containerId);s.innerHTML='<button type="button" data-test-wallet style="width:100%;height:48px;border:0;border-radius:10px;background:#111;color:white;font-size:18px">Apple Pay — test fixture</button><p style="color:#24332d">Card form test fixture</p>';s.querySelector('button').onclick=function(){c.eventListener({name:'SESSION_STARTED'});c.eventListener({name:'SESSION_CANCELED'});};c.eventListener({name:'VIEW_READY'});}};`});
    // External fonts are unnecessary to verify flow/layout boundaries offline.
    if(url.hostname==='fonts.googleapis.com')return route.fulfill({status:200,contentType:'text/css',body:''});
    unexpected.push(url.origin+p);return route.abort();
   });
   const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
   await page.goto('https://findzia.com/',{waitUntil:'networkidle'});
   await page.waitForFunction(()=>{const r=document.querySelector('.fz-home');return r?.fzBilling&&r?.fzAccount&&r?.fzRefineBridge;});
   assert.equal(await page.locator('.fz-home').getAttribute('data-lang'),variant.lang,'saved language survives the move');
   // Choose themes with the existing control instead of rewriting product CSS.
   await page.evaluate(scheme=>{const s=document.querySelector('[data-solar-mode]');if(s){s.value=scheme;s.dispatchEvent(new Event('change',{bubbles:true}));}},variant.scheme);
   assert.equal(await page.locator('.fz-home').getAttribute('data-theme'),variant.scheme,'theme is active');
   await page.screenshot({path:path.join(out,`home-${variant.width}-${variant.lang}.png`),fullPage:true});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'homepage does not overflow');
   const input=page.locator('[data-dark-input]');await input.fill('chair');await input.press('Enter');
   await page.waitForFunction(()=>document.querySelector('.fz-home').fzRefineBridge.snapshot().view.items.length===3);
   await page.waitForFunction(()=>document.querySelectorAll('.fz-tile img').length>0||document.querySelectorAll('.fz-media-stage img').length>0);
   await page.screenshot({path:path.join(out,`results-${variant.width}-${variant.lang}.png`),fullPage:true});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'results do not overflow');
   const filter=page.locator('[data-refine-open]');await filter.click();
   await page.waitForFunction(()=>document.querySelector('[data-refine-dialog]').open);
   await page.screenshot({path:path.join(out,`filters-${variant.width}-${variant.lang}.png`)});
   await page.locator('[data-refine-close]').click();
   await page.locator('[data-guide-open]').click();
   await page.waitForFunction(()=>document.querySelector('dialog.fz-guide')?.open);
   await page.locator('[data-guide-mode="guided"]').click();
   await page.waitForFunction(()=>document.querySelector('.fz-guide-body')?.textContent.includes('Where will you use it?'));
   await page.screenshot({path:path.join(out,`assistant-${variant.width}-${variant.lang}.png`)});
   await page.evaluate(()=>document.querySelector('dialog.fz-guide').close());
   if(variant.width===390&&variant.lang==='en'){
    const png=await page.evaluate(()=>{const c=document.createElement('canvas');c.width=200;c.height=200;const x=c.getContext('2d');x.fillStyle='#758578';x.fillRect(0,0,200,200);return c.toDataURL('image/png').split(',')[1];});
    await page.locator('input[type=file]').first().setInputFiles({name:'reference.png',mimeType:'image/png',buffer:Buffer.from(png,'base64')});
    await page.waitForFunction(()=>{const r=document.querySelector('.fz-home').fzRefineBridge;return r.context().kind==='image'&&!r.context().busy&&r.snapshot().view.items.length===3;});
    assert.ok(calls.includes('/api/search/image/stream'),'image search uses the existing API stream');
   }
   await page.evaluate(()=>document.querySelector('.fz-home').fzAccount.open('plans'));
   await page.locator('[data-plan-buy]').click();
   await page.waitForFunction(()=>window.__mfInits?.length===1);
   assert.equal(await page.evaluate(()=>window.__mfInits[0].settings.applePay.isEnabled),true);
   assert.equal(await page.evaluate(()=>window.__mfInits[0].shouldHandlePaymentUrl),false);
   await page.locator('[data-test-wallet]').click();
   assert.equal(calls.filter(p=>p.endsWith('/session/complete')).length,0,'cancel does not charge');
   assert.equal(page.url(),'https://findzia.com/','wallet flow stays on the same page');
   await page.screenshot({path:path.join(out,`checkout-${variant.width}-${variant.lang}.png`)});
   const csp=await page.evaluate(()=>window.__cspErrors||[]);violations.push(...csp);
   assert.deepEqual(errors,[],'no JavaScript exceptions');assert.deepEqual(violations,[],'no CSP violations');
   assert.deepEqual(unexpected,[],'no unexpected external requests');
   console.log('PASS',JSON.stringify(variant),'standalone app mounts, search, images, filters, assistant, inline checkout, cancel, no overflow/CSP/JS errors');
   await context.close();
  }
 }finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
