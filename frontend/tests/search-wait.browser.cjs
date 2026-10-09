/* Public wait-screen integration: mocked searches/media, no paid API calls.
 * Run after build with FINDZIA_TEST_CHROME pointing to Chromium. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {pathToFileURL}=require('node:url');
const gate=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
const picture='<svg xmlns="http://www.w3.org/2000/svg" width="500" height="650"><rect width="500" height="650" fill="#e9e2d2"/><rect x="130" y="90" width="240" height="470" rx="55" fill="#ed8d25"/><rect x="190" y="45" width="120" height="75" rx="15" fill="#335d43"/><rect x="130" y="260" width="240" height="180" fill="#29553b"/><text x="162" y="350" fill="white" font-size="42">ORANGE</text></svg>';
const offers=Array.from({length:9},(_,i)=>({title:'Orange drink '+i,store:'Store '+i,url:'https://store.example.test/product-'+i,
 image:'https://store.example.test/image-'+i+'.svg',price:'2.500 KWD',currency:'KWD',country:'KW',market:'local',result_group:'local',photo_match_status:'approved',
 price_display_ready:true,price_display_currency:'KWD',price_amount:2.5+i,price_contract:'findzia-money-v1',price_display_major:String(2+i),price_display_minor:'.500',evaluation_token:'test-'+i}));
(async()=>{
 const {createServer}=await import(pathToFileURL(path.join(__dirname,'../server.mjs')));
 const server=createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({executablePath:process.env.FINDZIA_TEST_CHROME,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  for(const variant of [{width:390,height:720,lang:'en',photo:true},{width:320,height:568,lang:'ar',reduced:true},{width:1440,height:900,lang:'en'},{width:390,height:720,lang:'ja'}]){
   const context=await browser.newContext({viewport:{width:variant.width,height:variant.height},reducedMotion:variant.reduced?'reduce':'no-preference'});
   await context.addInitScript(lang=>localStorage.setItem('findzia-lang',lang),variant.lang);
   const errors=[],calls=[];let search=gate(),media=gate(),mode='offers';
   await context.route('**/*',async route=>{
    const url=new URL(route.request().url()),p=url.pathname;
    if(url.origin===origin)return route.continue();
    if(url.origin==='https://store.example.test')return route.fulfill({contentType:'image/svg+xml',body:picture});
    if(url.origin==='https://api.findzia.com'){
     calls.push(p);let data={ok:true};
     if(p==='/api/geo')Object.assign(data,{country:'KW',country_code:'KW',source:'ip'});
     else if(p==='/api/account/config')data.providers={};
     else if(p==='/api/billing/config')data.plans=[];
     else if(p==='/api/billing/status'||p==='/api/billing/guest')Object.assign(data,{remaining:20,balances:{trial:20,pack:0},guest_token:'test-guest'});
     else if(p.includes('/config'))data.checkout_available=false;
     else if(['/api/search/stream','/api/search/image/stream'].includes(p)){
      const current=mode;await search.promise;
      const events=current==='offers'?[{event:'query',query:'Orange drink'},...offers.map(item=>({event:'result',item:{...item,media_images:[item.image],search_origin:p.includes('/image/')?'image':'text'}})),{event:'done'}]:[{event:'done'}];
      return route.fulfill({contentType:'application/x-ndjson',body:events.map(e=>JSON.stringify(e)+'\n').join('')}).catch(()=>{});
     }else if(p.startsWith('/api/media/check')){
      await media.promise;const payload=route.request().postDataJSON();
      if(payload.images)return route.fulfill({contentType:'application/x-ndjson',body:payload.images.map((x,index)=>JSON.stringify({id:index,ok:true,usable:true,status:200})+'\n').join('')}).catch(()=>{});
      Object.assign(data,{usable:true});
     }else if(p.includes('/media/proxy'))return route.fulfill({contentType:'image/svg+xml',body:picture});
     return route.fulfill({contentType:'application/json',body:JSON.stringify(data)}).catch(()=>{});
    }
    return route.fulfill({contentType:url.hostname==='fonts.googleapis.com'?'text/css':'text/javascript',body:''});
   });
   const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
   await page.goto(origin+'/',{waitUntil:'networkidle'});
   await page.waitForFunction(()=>document.querySelector('.fz-home')?.fzSearchWait);
   assert.equal(await page.locator('.fz-search-wait').isVisible(),false,'no loader on idle home');
   const wait=()=>page.waitForFunction(()=>document.querySelector('.fz-home').dataset.waitActive==='true');
   const hidden=()=>page.waitForFunction(()=>!document.querySelector('.fz-home').dataset.waitActive);
   const start=async()=>{const input=page.locator('[data-dark-input]');await input.fill('Orange drink');await input.press('Enter');await wait();};
   if(variant.photo){
    const png=await page.evaluate(()=>{const c=document.createElement('canvas');c.width=500;c.height=650;const x=c.getContext('2d');x.fillStyle='#e9e2d2';x.fillRect(0,0,500,650);x.fillStyle='#ed8d25';x.fillRect(130,90,240,470);return c.toDataURL('image/png').split(',')[1];});
    await page.locator('input[type=file]').first().setInputFiles({name:'orange.png',mimeType:'image/png',buffer:Buffer.from(png,'base64')});await wait();
    await page.waitForFunction(()=>document.querySelector('.fz-search-wait img').src.startsWith('data:image/'));
   }else await start();
   const original=await page.locator('.fz-search-wait img').getAttribute('src');
   assert.equal(await page.locator('.fz-one-scan').evaluate(e=>getComputedStyle(e).display),'block');
   search.resolve();
   await page.waitForFunction(()=>document.querySelectorAll('.fz-search-wait .fz-one-log-line').length===7);
   await page.waitForFunction(()=>document.querySelectorAll('.fz-search-wait .fz-one-reel').length>0);
   if(variant.photo)assert.equal(await page.locator('.fz-search-wait img').getAttribute('src'),original,'original photo does not change to a merchant image');
   if(variant.lang==='ja')assert.match(await page.locator('.fz-one-heading').textContent(),/[\u3040-\u30ff]/,'Japanese labels preserved');
   const geometry=await page.evaluate(()=>{const box=document.querySelector('.fz-search-wait').getBoundingClientRect();const image=document.querySelector('.fz-one-stage').getBoundingClientRect();return {bottom:box.bottom,width:document.documentElement.scrollWidth,viewport:innerWidth,height:innerHeight,imageHeight:image.height};});
   assert.ok(geometry.bottom<=geometry.height+2,JSON.stringify(geometry));assert.ok(geometry.width<=geometry.viewport+1,'no horizontal overflow');assert.ok(geometry.imageHeight>=300,'large image area');
   if(process.env.FINDZIA_TEST_OUTPUT){fs.mkdirSync(process.env.FINDZIA_TEST_OUTPUT,{recursive:true});await page.screenshot({path:path.join(process.env.FINDZIA_TEST_OUTPUT,`wait-${variant.width}-${variant.lang}.png`)});}
   media.resolve();await hidden();
   await page.waitForFunction(()=>document.querySelector('.fz-home').fzRefineBridge.context().can_refine);
   assert.notEqual(await page.locator('[data-results-body]').evaluate(e=>getComputedStyle(e).display),'none','real grid is restored');
   assert.equal(await page.evaluate(()=>!!document.querySelector('.fz-home').fzOneChoice),false,'trial AI mode never mounts on public home');
   assert.equal(calls.some(p=>p.includes('/choice')),false,'no extra AI-choice request');
   // A fresh empty search must exit, and another search must still work.
   await page.evaluate(()=>document.querySelector('.fz-home').fzRefineBridge.resetSearchSession());
   search=gate();mode='empty';await start();search.resolve();await hidden();
   await page.waitForFunction(()=>!document.querySelector('.fz-home').fzRefineBridge.context().busy);
   assert.ok(await page.locator('[data-results-body]').textContent(),'existing empty state stays visible');
   await page.evaluate(()=>document.querySelector('.fz-home').fzRefineBridge.resetSearchSession());
   search=gate();await start();await page.locator('.fz-search-wait button').click();await hidden();search.resolve();
   assert.equal(await page.locator('.fz-home').getAttribute('data-home-state'),'empty','cancel returns home');
   assert.deepEqual(errors,[],'no JavaScript errors');console.log('PASS',variant,'wait, prices, seven-line log, first-card handoff, empty and cancel');
   await context.close();
  }
 }finally{await browser.close();server.closeAllConnections();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
