/* A real progressive stream with mocked network/account responses. No paid calls. */
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),{pathToFileURL}=require('node:url');
const art='<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400"><rect width="400" height="400" fill="#ddd"/><rect x="70" y="140" width="260" height="60" rx="10" fill="#886c43"/><path d="M90 200v90M310 200v90" stroke="#886c43" stroke-width="16"/></svg>';
const offer=(id,market='global')=>({title:'Coffee table '+id,store:'Store '+id,url:'https://store.example.test/'+id,image:'https://store.example.test/'+id+'.svg',
 price:'24.500 KWD',currency:'KWD',country:market==='local'?'KW':'US',market,photo_match_status:'approved',
 price_display_ready:true,price_display_currency:'KWD',price_amount:24.5,price_contract:'findzia-money-v1',price_display_major:'24',price_display_minor:'.500',evaluation_token:'test-'+id});
(async()=>{
 const {createServer}=await import(pathToFileURL(path.join(__dirname,'../server.mjs'))),server=createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({executablePath:process.env.FINDZIA_TEST_CHROME,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  for(const variant of [{width:390,height:720,lang:'en'},{width:320,height:568,lang:'ar',reduced:true},{width:1440,height:900,lang:'ja'}]){
   const context=await browser.newContext({viewport:{width:variant.width,height:variant.height},reducedMotion:variant.reduced?'reduce':'no-preference'});
   let releaseBilling;const billing=new Promise(r=>releaseBilling=r),errors=[];
   await context.addInitScript(lang=>{
    localStorage.setItem('findzia-lang',lang);localStorage.setItem('findzia-theme','light');
    const native=window.fetch.bind(window);
    window.fetch=(url,options)=>{
     if(String(url).includes('/api/search/image/stream'))return Promise.resolve(new Response(new ReadableStream({start(c){window.__stream=c;}}),{headers:{'Content-Type':'application/x-ndjson'}}));
     return native(url,options);
    };
    window.__send=event=>window.__stream.enqueue(new TextEncoder().encode(JSON.stringify(event)+'\n'));
   },variant.lang);
   await context.route('**/*',async route=>{
    const u=new URL(route.request().url()),p=u.pathname;if(u.origin===origin)return route.continue();
    if(u.origin==='https://store.example.test')return route.fulfill({contentType:'image/svg+xml',body:art});
    if(u.origin==='https://api.findzia.com'){
     let data={ok:true};
     if(p==='/api/geo')Object.assign(data,{country:'KW',source:'ip'});
     else if(p==='/api/account/config')data.providers={};
     else if(p==='/api/billing/config')data.plans=[];
     else if(p==='/api/billing/guest'||p==='/api/billing/status'){await billing;Object.assign(data,{remaining:20,balances:{trial:20,pack:0},guest_token:'test-guest'});}
     else if(p.includes('/media/proxy'))return route.fulfill({contentType:'image/svg+xml',body:art});
     else if(p.startsWith('/api/media/check')){
      const body=route.request().postDataJSON();
      if(body.images)return route.fulfill({contentType:'application/x-ndjson',body:body.images.map((_,id)=>JSON.stringify({id,ok:true,usable:true,status:200})+'\n').join('')});
      data.usable=true;
     }
     return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
    }
    return route.fulfill({contentType:u.hostname==='fonts.googleapis.com'?'text/css':'text/javascript',body:''});
   });
   const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(origin,{waitUntil:'networkidle'});
   await page.locator('input[id^="fz-photo-"]').setInputFiles({name:'table.svg',mimeType:'image/svg+xml',buffer:Buffer.from(art)});
   await page.waitForFunction(()=>{const img=document.querySelector('.fz-search-wait img');return img?.src.startsWith('blob:')&&img.naturalWidth>0&&document.querySelector('.fz-home').dataset.waitActive==='true';});
   assert.equal(await page.evaluate(()=>!!window.__stream),false,'photo appears while credit check is still pending');
   releaseBilling();await page.waitForFunction(()=>!!window.__stream);
   const geometry=()=>page.locator('.fz-fixed-header').evaluate(n=>({height:n.getBoundingClientRect().height,camera:n.querySelector('.fz-camera-hero').getBoundingClientRect().top}));
   const waiting=await geometry();
   await page.evaluate(()=>{window.__handoff=[];window.__recordHandoff=true;const sample=()=>{const root=document.querySelector('.fz-home'),body=root.querySelector('[data-results-body]');window.__handoff.push({waiting:root.dataset.waitActive==='true',exiting:root.dataset.waitExiting==='true',body:getComputedStyle(body).display});if(window.__recordHandoff)requestAnimationFrame(sample);};sample();});
   await page.evaluate(item=>__send({event:'result',item}),offer('a'));
   await page.waitForFunction(()=>{const r=document.querySelector('.fz-home');return r.fzRefineBridge.context().can_refine&&!r.dataset.waitActive&&!r.dataset.waitExiting;});
   await page.evaluate(()=>window.__recordHandoff=false);
   assert.equal(await page.evaluate(()=>document.querySelector('.fz-home').fzRefineBridge.context().busy),true,'first result arrives before stream completion');
   const ready=await geometry();assert.ok(Math.abs(ready.height-waiting.height)<2,'header does not jump when first card arrives during search');assert.ok(Math.abs(ready.camera-waiting.camera)<2);
   if(!variant.reduced)assert.equal(await page.evaluate(()=>__handoff.some(x=>x.exiting&&x.body!=='none')),true,'received cards are visible under the outgoing photo');
   await page.evaluate(()=>{window.__firstCard=document.querySelector('.fz-card-shell');window.__firstImage=__firstCard.querySelector('img');});
   await page.evaluate(item=>__send({event:'result',item}),offer('b','local'));
   await page.waitForFunction(()=>document.querySelectorAll('.fz-card-shell').length===2);
   if(!variant.reduced)assert.equal(await page.evaluate(()=>__firstCard.getAnimations().some(a=>a.id==='fz-result-move')),true,'existing card glides when a new group arrives');
   await page.evaluate(item=>__send({event:'upsert',item}),offer('a','local'));
   await page.waitForFunction(()=>document.querySelector('[data-stable-group="local"]')?.querySelectorAll('.fz-card-shell').length===2);
   assert.equal(await page.evaluate(()=>__firstCard===document.querySelector('[data-stable-group="local"] .fz-card-shell')&&__firstCard.querySelector('img')===__firstImage),true,'classification changes move the original card and loaded image');
   await page.evaluate(()=>{__send({event:'done'});__stream.close();});
   await page.waitForFunction(()=>!document.querySelector('.fz-home').fzRefineBridge.context().busy);
   assert.deepEqual(await geometry(),ready,'completion keeps the same header geometry');
   await page.waitForFunction(()=>[...document.querySelectorAll('.fz-card-shell,.fz-market-head')].every(n=>n.getAnimations({subtree:true}).every(a=>a.playState!=='running')));
   if(process.env.FINDZIA_TEST_OUTPUT){fs.mkdirSync(process.env.FINDZIA_TEST_OUTPUT,{recursive:true});await page.screenshot({path:path.join(process.env.FINDZIA_TEST_OUTPUT,`handoff-${variant.width}-${variant.lang}.png`)});}
   await page.locator('[data-image-query-chip]').click();
   assert.equal(await page.locator('[data-image-query-chip]').isVisible(),false,'removing the photo releases the immediate preview too');
   assert.equal(await page.evaluate(()=>document.querySelector('.fz-home').fzRefineBridge.context().preview_image),'');
   assert.deepEqual(errors,[]);console.log('PASS',variant,'early photo, overlapping handoff, fixed header, incremental card motion and identity');await context.close();
  }
 }finally{await browser.close();server.closeAllConnections();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
