/* Fake Chromium camera and mocked APIs only. Never opens a real device or paid search. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {pathToFileURL}=require('node:url');
(async()=>{
 const {createServer}=await import(pathToFileURL(path.join(__dirname,'../server.mjs')));
 const server=createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({executablePath:process.env.FINDZIA_TEST_CHROME,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
 try{
  for(const variant of [{width:390,height:720,lang:'en',theme:'light'},{width:390,height:720,lang:'en',theme:'dark'},{width:1440,height:900,lang:'en',theme:'light'},{width:320,height:568,lang:'ar',theme:'light',reduced:true},{width:390,height:720,lang:'ja',theme:'light'}]){
   const context=await browser.newContext({viewport:{width:variant.width,height:variant.height},hasTouch:true,reducedMotion:variant.reduced?'reduce':'no-preference'}),searches=[],errors=[];
   await context.addInitScript(lang=>{
    localStorage.setItem('findzia-lang',lang);window.__streams=[];window.__constraints=[];
    const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia=async constraints=>{
     window.__constraints.push(constraints);
     if(window.__denyCamera)throw new DOMException('Denied','NotAllowedError');
     if(window.__delayCamera)await new Promise(r=>window.__releaseCamera=r);
     const stream=await original(constraints);
     if(lang==='ja'){
      const track=stream.getVideoTracks()[0],settings=track.getSettings.bind(track),caps=track.getCapabilities.bind(track);let zoom=1;
      track.getCapabilities=()=>({...caps(),zoom:{min:1,max:4,step:.1}});track.getSettings=()=>({...settings(),zoom});
      track.applyConstraints=async c=>{await new Promise(r=>setTimeout(r,15));zoom=c.advanced[0].zoom;(window.__zoomApplied||=[]).push(zoom);};
     }
     window.__streams.push(stream);return stream;
    };
    document.addEventListener('securitypolicyviolation',e=>window.__cspErrors=(window.__cspErrors||[]).concat(e.effectiveDirective+':'+e.blockedURI));
   },variant.lang);
   await context.route('**/*',async route=>{
    const u=new URL(route.request().url()),p=u.pathname;if(u.origin===origin)return route.continue();
    if(u.origin==='https://api.findzia.com'){
     let data={ok:true};
     if(p==='/api/geo')Object.assign(data,{country:'KW',source:'ip'});
     else if(p==='/api/account/config')data.providers={};
     else if(p==='/api/billing/config')data.plans=[];
     else if(p==='/api/billing/status'||p==='/api/billing/guest')Object.assign(data,{remaining:20,balances:{trial:20,pack:0},guest_token:'test-guest'});
     else if(p.includes('/config'))data.checkout_available=false;
     else if(p==='/api/search/image/stream'){searches.push(route.request().postDataJSON());return route.fulfill({contentType:'application/x-ndjson',body:'{"event":"done"}\n'});}
     return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
    }
    return route.fulfill({contentType:u.hostname==='fonts.googleapis.com'?'text/css':'text/javascript',body:''});
   });
   const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
   await page.goto(origin,{waitUntil:'networkidle'});
   await page.waitForFunction(()=>document.querySelector('.fz-home')?.fzStoreScene);
   await page.evaluate(theme=>{document.querySelector('.fz-home').dataset.theme=theme;document.documentElement.dataset.findziaTheme=theme;},variant.theme);
   await page.waitForFunction(()=>Array.from(document.querySelectorAll('.fz-store-scene img')).every(i=>i.complete&&i.naturalWidth>0));
   const scene=page.locator('.fz-store-scene');
   assert.equal(await scene.getAttribute('aria-hidden'),'true');
   assert.equal(await scene.evaluate(n=>n.inert),true,'background never intercepts input');
   assert.equal(searches.length,0,'animation never runs a search');
   assert.equal(await page.evaluate(()=>window.__constraints.length),0,'animation never opens a camera');
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'no horizontal overflow');
   assert.equal(await scene.getAttribute('data-running'),String(!variant.reduced),'respects reduced motion');
   if(!variant.reduced){
    const before=await page.locator('.fz-store-plane').nth(1).evaluate(n=>getComputedStyle(n).transform);
    await page.waitForFunction(before=>getComputedStyle(document.querySelectorAll('.fz-store-plane')[1]).transform!==before,before);
    await page.locator('.fz-store-toggle').click();assert.equal(await scene.getAttribute('data-running'),'false','pause is functional');
   }
   if(process.env.FINDZIA_TEST_OUTPUT){fs.mkdirSync(process.env.FINDZIA_TEST_OUTPUT,{recursive:true});await page.screenshot({path:path.join(process.env.FINDZIA_TEST_OUTPUT,`hero-${variant.width}-${variant.lang}-${variant.theme}.png`)});}
   if(!variant.reduced)await page.locator('.fz-store-toggle').click();
   await page.locator('[data-dark-input]').fill('chair');
   assert.equal(await scene.getAttribute('data-running'),'false','animation rests while typing');
   await page.locator('[data-dark-input]').press('Escape');
   await page.locator('[data-dark-photo]').click();
   await page.waitForFunction(()=>document.querySelector('.fz-camera-dialog').dataset.ready==='true');
   assert.equal(await scene.getAttribute('data-running'),'false','animation rests while camera is open');
   assert.equal(await page.locator('.fz-camera-zoom-range').count(),1,'zoom retained');
   await page.keyboard.press('Escape');
   await page.locator('[data-dark-input]').fill('chair');await page.locator('[data-dark-input]').press('Enter');
   await page.waitForFunction(()=>document.querySelector('.fz-home').dataset.homeState==='results');
   assert.equal(await scene.getAttribute('data-running'),'false');assert.equal(await scene.getAttribute('data-visible'),'false','scene only appears on the home page');
   await page.evaluate(()=>document.querySelector('.fz-home').fzRefineBridge.resetSearchSession());
   await page.waitForFunction(()=>document.querySelector('.fz-store-scene').dataset.visible==='true');
   assert.deepEqual(errors,[]);assert.deepEqual(await page.evaluate(()=>window.__cspErrors||[]),[]);
   console.log('PASS',variant,'scene motion, product images, pause, focus, camera and search');
   await context.close();
  }
 }finally{await browser.close();server.closeAllConnections();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
