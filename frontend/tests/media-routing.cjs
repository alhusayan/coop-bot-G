/* All services, including payments, are mocked. No paid requests are made. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {pathToFileURL}=require('node:url');
const out=process.env.FINDZIA_TEST_OUTPUT||path.resolve(__dirname,'../../verification');fs.mkdirSync(out,{recursive:true});
const picture='<svg xmlns="http://www.w3.org/2000/svg" width="200" height="240"><rect width="200" height="240" rx="22" fill="#e8e9e3"/><path d="M80 58h40v40l20 100H60L80 98Z" fill="#ae9981"/></svg>';
const offers=Array.from({length:5},(_,i)=>({title:'Decorative vase '+i,store:'Test shop',url:'https://store.example.test/vase-'+i,image:'https://store.example.test/photo-'+i+'.svg',price:'20.00 EUR',currency:'EUR',country:'DE',market:'local',result_group:'local',photo_match_status:'approved',price_display_ready:true,price_display_currency:'EUR',price_amount:20,price_contract:'findzia-money-v1',price_display_major:'20',price_display_minor:'.00',evaluation_token:'fixture-'+i}));

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
 async function fixture({width=390,lang='en',theme='light',payment='paddle',layout='list',recovery='clear',mediaMode='normal',rows=offers,checkoutDelay=600,checkoutResult='normal',confirmDelay=0,mediaDelay=150,guest=false,configDelay=0,reduced=false,support={mode:'ok',delay:60}}={}){
  const context=await browser.newContext({viewport:{width,height:844},locale:lang==='ar'?'ar-KW':'en-GB',colorScheme:theme,reducedMotion:reduced?'reduce':'no-preference'});
  const calls=[],errors=[];let paidCredits=0;
  await context.addInitScript(({lang,theme,payment,layout,guest})=>{
   localStorage.setItem('findzia-results-layout-v1',layout);localStorage.setItem('findzia-appearance-v1',theme);localStorage.setItem('findzia-lang',lang);localStorage.setItem('findzia-lang-DE',lang);localStorage.setItem('findzia-country','DE');
   if(!guest)sessionStorage.setItem('findzia-account-v1-session',JSON.stringify({access_token:'test-member-token',expires_at:Math.floor(Date.now()/1000)+3600}));
   if(false)sessionStorage.setItem('findzia-mf-return-v1',JSON.stringify({intent:'fixture-intent',payment:'fixture-payment',owner:'test',at:Date.now()}));
  },{lang,theme,payment,layout,guest});
  await context.route('**/*',async route=>{
   const u=new URL(route.request().url()),p=u.pathname;
   if(u.origin==='https://findzia.com'){const r=await fetch(origin+p+u.search);return route.fulfill({status:r.status,headers:Object.fromEntries(r.headers),body:Buffer.from(await r.arrayBuffer())});}
   if(u.origin==='https://api.findzia.com'){
    let data={ok:true};const payload=route.request().postData()?JSON.parse(route.request().postData()):{};calls.push({path:p,payload,at:Date.now(),headers:route.request().headers()});
    if(p==='/api/geo')Object.assign(data,{country:'DE',country_code:'DE',country_name:'Germany'});
    else if(p==='/api/account/config'){await new Promise(r=>setTimeout(r,configDelay));data.providers={google:true,apple:true};}
    else if(p==='/api/account/auth/start'){await new Promise(r=>setTimeout(r,250));return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({ok:false})});}
    else if(p==='/api/support/chat'){
     await new Promise(r=>setTimeout(r,support.delay));
     if(support.mode==='limited')return route.fulfill({status:429,contentType:'application/json',body:JSON.stringify({ok:false})});
     if(support.mode==='error')return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({ok:false})});
     Object.assign(data,{answer:payload.language==='ar'?'تقدر تختار الباقة من حسابي. محادثة المساعدة ما تخصم من رصيد البحث.':'Open My account to view your packs. Help conversations do not use search credits.',mode:'ai',sources:['credits'],actions:['plans','usage','javascript:alert(1)']});
     if(support.mode==='html')data.answer='<img src=x onerror=alert(1)> is plain text.';
    }
    else if(p==='/api/search/metrics')return route.fulfill({status:204,body:''});
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
     const resultRows=rows.map(item=>({...item,media_images:[item.image,...(item.images||[])],search_origin:photo?'image':'text',retrieval_sources:[photo?'google_lens':'serper_search'],...(refine?{refinement_verified:true}:{})}));
     const events=[{event:'query',query:payload.query||'Decorative vase'},...resultRows.map(item=>({event:'result',item})),{event:'done',results:resultRows}];
     return route.fulfill({contentType:'application/x-ndjson',body:events.map(e=>JSON.stringify(e)+'\n').join('')});
    }
    else if(p==='/api/media/check'||p==='/api/media/check/batch'){
     const requests=calls.filter(c=>c.path.startsWith('/api/media/check'));
     if(mediaMode==='once'&&requests.length===1)return route.fulfill({status:429,headers:{'Retry-After':'1'},contentType:'application/json',body:JSON.stringify({ok:false,retryable:true,retry_after:1})});
     await new Promise(r=>setTimeout(r,mediaDelay));
     function verdict(value,id){
      const row=rows.find(row=>row.evaluation_token===value.token);
      const allowed=value.token==='recovered-bound-token'?['https://store.example.test/recovered.png']:row?[row.image,...(row.images||[])]:[];
      if(!allowed.includes(value.image)){errors.push('Invalid image authorization');return {id,ok:false,status:400};}
      const usable=!/a9f8|b4f2|c2d3/.test(value.image);
      return {id,status:200,ok:true,usable,decision:usable?'product':'logo'};
     }
     data=payload.images?{ok:true,results:payload.images.map(verdict)}:verdict(payload,0);
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
     open(o){window.__opens.push(o);if(o.settings.frameTarget){const host=document.querySelector('.'+o.settings.frameTarget),f=document.createElement('iframe');f.title='Mock Paddle checkout';f.src='https://checkout.paddle.com/mock?theme='+o.settings.theme;f.style.cssText=o.settings.frameStyle+'height:'+o.settings.frameInitialHeight+'px;';host.append(f);}},
     close(){window.__closes++;document.querySelectorAll('.fzb-wallet-frame iframe').forEach(f=>f.remove());}
    }};
    window.__emit=(name,extra={})=>window.__callback({name,data:{id:'che_fixture',transaction_id:'txn_fixture',settings:{display_mode:'inline'},currency_code:'USD',totals:{subtotal:9.99,tax:0,total:9.99},...extra}});
   `});
   if(u.hostname==='checkout.paddle.com')return route.fulfill({contentType:'text/html',body:`<!doctype html><html><head><meta charset="utf-8"><style>*{box-sizing:border-box}html,body{margin:0;background:transparent;color:${u.searchParams.get('theme')==='dark'?'#bdc8bf':'#647267'};font:11px/1.5 system-ui}button{display:block;background:${u.searchParams.get('theme')==='dark'?'#f3f5ef':'#202923'};color:${u.searchParams.get('theme')==='dark'?'#202923':'#fff'};width:100%;height:46px;border:0;border-radius:10px;font:22px system-ui}footer{padding:13px 4px 0;text-align:center}a{color:inherit}</style></head><body><button>Apple Pay</button><footer>Payment provider preview · Sold by Paddle<br>Provided by Fancy Gifts and Accessories Design Company<br><a href='#'>Support</a> · <a href='#'>Terms</a> · <a href='#'>Privacy</a></footer></body></html>`});
   if(u.origin==='https://store.example.test')return route.fulfill({contentType:'image/svg+xml',body:picture});
   if(u.hostname==='fonts.googleapis.com')return route.fulfill({contentType:'text/css',body:''});
   errors.push('Unexpected URL '+u.href);return route.abort();
  });
  const page=await context.newPage();page.setDefaultTimeout(10000);page.on('pageerror',e=>errors.push(e.message));
  await page.goto('https://findzia.com/',{waitUntil:'networkidle'});
  await page.waitForFunction(()=>!!document.querySelector('.fz-home')?.fzBilling);
  if(guest)await page.evaluate(()=>document.querySelector('.fz-home').fzBilling.refresh(true,true));
  await page.waitForFunction(()=>document.querySelector('.fz-home')?.fzBilling?.status()?.remaining===20);
  return {context,page,calls,errors,support};
 }


 const check=(x,n)=>{assert.ok(x,n);checks++;};
 const search=async(page,query='Wood door')=>{if(await page.locator('[data-dark-input]').isVisible()){await page.locator('[data-dark-input]').fill(query);await page.locator('[data-dark-submit]').click();}else{await page.locator('textarea.fz-input').fill(query);await page.locator('[data-search-btn]').click();}};
 const cards=page=>page.locator('[data-image-key] img.is-loaded');
 try{
  for(const [lang,theme,mediaMode] of [['de','light','normal'],['ar','dark','normal'],['en','light','once']]){
   const {page,context,calls,errors}=await fixture({lang,theme,mediaMode});
   await search(page);
   try{await page.waitForFunction(()=>document.querySelectorAll('[data-image-key] img.is-loaded').length===4,{},{timeout:22000});}catch(e){console.log(JSON.stringify({calls:calls.filter(c=>c.path.includes('/media/')),errors,dom:await page.evaluate(()=>({cards:document.querySelectorAll('[data-image-key] img.is-loaded').length,empty:document.querySelector('.fz-empty')?.textContent,body:document.querySelector('.fz-home')?.textContent.slice(-1500)}))},null,2));throw e;}
   await page.waitForFunction(()=>document.querySelector('.fz-home').dataset.visibleResultCount==='4');
   await page.waitForTimeout(80);
   const metric=calls.find(c=>c.path==='/api/search/metrics');
   check(!!metric&&metric.payload.kind==='text','Text first-card metric sent');
   check(metric.payload.first_card_ms>=150,'Metric waits for media verdict and render');
   check(metric.payload.search_trace===calls.find(c=>c.path==='/api/search/stream').headers['x-findzia-search-trace'],'Client/server trace correlation');
   check(!JSON.stringify(metric.payload).includes('Wood'),'Metrics exclude shopper query');
   const checksBefore=calls.filter(c=>c.path.startsWith('/api/media/check'));
   check(checksBefore.some(c=>c.path.endsWith('/batch')),'Actual page sends a batch');
   check(checksBefore.every(c=>(c.payload.images||[c.payload]).length<=6),'Batch bound');
   check(!checksBefore.flatMap(c=>c.payload.images||[c.payload]).some(i=>!i.token),'Each image has a token');
   check(calls.find(c=>c.path==='/api/search/stream').payload.lang===lang,'Selected language preserved');
   check(calls.find(c=>c.path==='/api/search/stream').payload.country==='DE','Selected market preserved');
   const count=checksBefore.length;
   await search(page,'Wooden door');
   await page.waitForFunction(()=>document.querySelectorAll('[data-image-key] img.is-loaded').length===4);
   await page.waitForTimeout(100);
   const metrics=calls.filter(c=>c.path==='/api/search/metrics');
   check(metrics.length===2&&new Set(metrics.map(m=>m.payload.search_trace)).size===2,'Exactly one metric per search, new trace on repeat');
   check(calls.filter(c=>c.path.startsWith('/api/media/check')).length===count,'Cached images reused across a new search');
   check(errors.length===0,'No browser errors: '+errors.join('|'));
   if(lang==='ar')await page.screenshot({path:out+'/arabic-dark-media.png',fullPage:true});
   if(lang==='de')await page.screenshot({path:out+'/german-light-media.png',fullPage:true});
   console.log('PASS '+lang+' '+theme+' '+mediaMode+': four complete cards, '+count+' media requests, no invalid authorization.');
   await context.close();
  }
  {
   const {page,context,calls,errors}=await fixture({lang:'ar',theme:'dark'});
   const base64=await page.evaluate(async()=>{
    const c=document.createElement('canvas');c.width=2400;c.height=1800;const x=c.getContext('2d'),d=x.createImageData(c.width,c.height);let state=82;
    for(let i=0;i<d.data.length;i+=4){state=(Math.imul(state,1664525)+1013904223)|0;d.data[i]=(state>>>16)&255;d.data[i+1]=(state>>>8)&255;d.data[i+2]=state&255;d.data[i+3]=255;}
    x.putImageData(d,0,0);return c.toDataURL('image/jpeg',.9).split(',')[1];
   });
   const bytes=Buffer.from(base64,'base64');
   await page.locator('input[type=file]').first().setInputFiles({name:'camera.jpg',mimeType:'image/jpeg',buffer:bytes});
   await page.waitForFunction(()=>document.querySelectorAll('[data-image-key] img.is-loaded').length===4,{},{timeout:22000});
   await page.waitForTimeout(80);
   const photoMetric=calls.filter(c=>c.path==='/api/search/metrics');
   check(photoMetric.length===1&&photoMetric[0].payload.kind==='image','One camera first-card metric');
   check(photoMetric[0].payload.search_trace===calls.find(c=>c.path==='/api/search/image/stream').headers['x-findzia-search-trace'],'Camera client/server trace correlation');
   const payload=calls.find(c=>c.path==='/api/search/image/stream')?.payload;
   check(!!payload&&payload.mime_type==='image/jpeg','Actual camera flow sends prepared JPEG');
   check(payload.image_upload.original_bytes===bytes.length,'Camera telemetry preserves original byte count');
   check(Buffer.from(payload.image_base64,'base64').length===payload.image_upload.upload_bytes,'Uploaded body matches prepared size');
   check(payload.image_upload.upload_bytes<bytes.length*.9,'Actual page transmits smaller image');
   check(errors.length===0,'Camera flow has no browser errors');
   console.log('PASS camera page upload: '+bytes.length+' → '+payload.image_upload.upload_bytes+' bytes, four cards.');
   await context.close();
  }
  console.log('PASS '+checks+' browser checks, all external APIs mocked.');
 }finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
