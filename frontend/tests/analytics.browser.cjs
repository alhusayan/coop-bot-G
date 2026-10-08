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
 const server=createServer({FINDZIA_GA4_MEASUREMENT_ID:'G-TEST12345'});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({executablePath:process.env.FINDZIA_TEST_CHROME,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  for(const variant of [{width:390,lang:'en',scheme:'light'}]){
   const context=await browser.newContext({viewport:{width:variant.width,height:844},colorScheme:variant.scheme,locale:variant.lang==='ar'?'ar-KW':'en-GB'});
   const calls=[],errors=[],violations=[],unexpected=[];let remaining=10,scenario='success',imageAttempts=0;
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
    if(url.hostname==='www.googletagmanager.com')return route.fulfill({status:200,contentType:'text/javascript',body:'/* Google transport mocked; inspect dataLayer commands */'});
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
      if(scenario==='error')return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'provider_private_message_not_for_analytics'})});
      if(scenario==='credits')return route.fulfill({status:402,contentType:'application/json',body:JSON.stringify({error:'credits_exhausted'})});
      if(scenario==='fallback'&&p.includes('/image/')){imageAttempts++;return route.fulfill({status:200,contentType:'application/x-ndjson',body:'{invalid\n'});}
      const events=[{event:'query',query:'chair'},...offers.map(item=>({event:'result',item})),{event:'done'}];
      return route.fulfill({status:200,contentType:'application/x-ndjson',body:events.map(x=>JSON.stringify(x)+'\n').join('')});
     }else if(p==='/api/search/image'){Object.assign(data,{query:'chair',results:offers});}
     else if(p==='/api/media/check'||p==='/api/media/check/batch'){
      const body=JSON.parse(route.request().postData()||'{}');
      if(body.images)data.results=body.images.map((_,id)=>({id,status:200,ok:true,usable:true,decision:'product'}));
      else Object.assign(data,{usable:true,decision:'product'});
     }else if(p==='/api/media/recover')data.images=[];
     else if(p==='/api/search/metrics'){}
     else if(p==='/api/refine/options')Object.assign(data,{adaptive:true,plan_token:'test-plan',category:'Chair',selection:{},ranges:{},children:[],facets:[{key:'color',label:'Colour',options:[{label:'Black',token:'black',value_id:'black'},{label:'White',token:'white',value_id:'white'}]}]});
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
   const events=()=>page.evaluate(()=>Array.from(window.dataLayer||[]).filter(x=>x[0]==='event').map(x=>({name:x[1],params:x[2]})));
   const count=async name=>(await events()).filter(x=>x.name===name).length;
   const ready=()=>page.waitForFunction(()=>{const r=document.querySelector('.fz-home');return r?.fzBilling&&r?.fzAccount&&r?.fzRefineBridge&&window.FindziaAnalytics;});
   await page.goto('https://findzia.com/?gclid=fixture_click&q=PRIVATE_QUERY&email=PRIVATE_EMAIL&token=PRIVATE_TOKEN',{waitUntil:'networkidle'});await ready();
   assert.equal(await count('page_view'),1);assert.equal(await count('fz_visit'),1);
   assert.equal((await events())[0].params.visit_source,'google_ads');
   await page.locator('[data-dark-input]').fill('PRIVATE_QUERY');await page.locator('[data-dark-input]').press('Enter');
   await page.waitForFunction(()=>window.FindziaAnalytics.diagnostics().some(x=>x.name==='fz_search_complete'));
   assert.equal(await count('fz_search_start'),1);assert.equal(await count('fz_results_view'),1);assert.equal(await count('fz_search_complete'),1);
   const complete=(await events()).find(x=>x.name==='fz_search_complete');
   assert.equal(complete.params.search_outcome,'results');assert.equal(complete.params.result_count,3);
   assert.equal(complete.params.send_to,'G-TEST12345');
   assert.ok(!/PRIVATE_QUERY|PRIVATE_EMAIL|PRIVATE_TOKEN|fixture@example/.test(JSON.stringify(await events())));
   await page.locator('a.fz-tile').first().click();
   assert.equal(await count('fz_product_click'),1);assert.equal(await count('conversion'),1);
   await page.evaluate(()=>{const s=document.querySelector('[data-solar-mode]');s.value='dark';s.dispatchEvent(new Event('change',{bubbles:true}));});
   await page.waitForFunction(()=>window.FindziaAnalytics.diagnostics().some(x=>x.name==='fz_theme_change'));
   assert.equal((await events()).findLast(x=>x.name==='fz_theme_change').params.theme,'dark');
   // The fallback is one logical search, not two starts or a false error.
   scenario='fallback';
   const png=await page.evaluate(()=>{const c=document.createElement('canvas');c.width=100;c.height=100;c.getContext('2d').fillRect(0,0,100,100);return c.toDataURL('image/png').split(',')[1];});
   await page.locator('input[type=file]').first().setInputFiles({name:'PRIVATE_FILENAME.png',mimeType:'image/png',buffer:Buffer.from(png,'base64')});
   await page.waitForFunction(()=>window.FindziaAnalytics.diagnostics().filter(x=>x.name==='fz_search_complete').length===2);
   assert.equal(imageAttempts,1);assert.equal(await count('fz_search_start'),2);assert.equal(await count('fz_search_error'),0);
   assert.equal((await events()).findLast(x=>x.name==='fz_search_complete').params.search_method,'image');
   assert.ok(!JSON.stringify(await events()).includes('PRIVATE_FILENAME'));
   // Real terminal provider and credit errors are not successful completions.
   for(const [next,code] of [['error','request_failed'],['credits','credits_exhausted']]){
    scenario=next;await page.evaluate(()=>document.querySelector('.fz-home').fzRefineBridge.newSearch());
    await page.locator('[data-dark-input]').fill('another query');await page.locator('[data-dark-input]').press('Enter');
    await page.waitForFunction(code=>window.FindziaAnalytics.diagnostics().some(x=>x.name==='fz_search_error'&&x.params.error_type===code),code);
   }
   assert.equal(await count('fz_search_complete'),2);assert.equal(await count('fz_search_error'),2);
   assert.ok(!JSON.stringify(await events()).includes('provider_private_message'));
   const analytics=(await events()).filter(x=>x.name!=='conversion');
   assert.ok(analytics.every(x=>x.params.send_to==='G-TEST12345'));
   // Owner mode persists, disables both destinations and can be switched off.
   scenario='success';
   await page.goto('https://findzia.com/?fz_test=1',{waitUntil:'networkidle'});await ready();
   assert.equal(await page.evaluate(()=>window.FindziaAnalytics.internal),true);
   await page.locator('[data-dark-input]').fill('owner test');await page.locator('[data-dark-input]').press('Enter');
   await page.waitForFunction(()=>window.FindziaAnalytics.diagnostics().some(x=>x.name==='fz_search_complete'));
   await page.locator('a.fz-tile').first().click();assert.equal((await events()).length,0);
   await page.goto('https://findzia.com/',{waitUntil:'networkidle'});await ready();assert.equal(await page.evaluate(()=>window.FindziaAnalytics.internal),true);
   await page.goto('https://findzia.com/?fz_test=0',{waitUntil:'networkidle'});await ready();assert.equal(await count('fz_visit'),1);
   assert.deepEqual(errors,[]);assert.deepEqual(await page.evaluate(()=>window.__cspErrors||[]),[]);
   console.log(JSON.stringify({ok:true,checks:['text funnel','photo fallback','one event per step','merchant conversion preserved','theme','safe attribution','terminal and credit errors','owner exclusion'],events:analytics.map(x=>x.name)}));
   await context.close();
  }
 }finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
