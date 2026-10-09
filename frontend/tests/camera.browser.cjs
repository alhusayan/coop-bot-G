/* Fake Chromium camera and mocked APIs only. Never opens a real device or paid search. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {pathToFileURL}=require('node:url');
(async()=>{
 const {createServer}=await import(pathToFileURL(path.join(__dirname,'../server.mjs')));
 const server=createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({executablePath:process.env.FINDZIA_TEST_CHROME,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
 try{
  for(const variant of [{width:390,height:720,lang:'en'},{width:320,height:568,lang:'ar'},{width:1440,height:900,lang:'ja'}]){
   const context=await browser.newContext({viewport:{width:variant.width,height:variant.height}}),searches=[],errors=[];
   await context.addInitScript(lang=>{
    localStorage.setItem('findzia-lang',lang);window.__streams=[];window.__constraints=[];
    const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia=async constraints=>{
     window.__constraints.push(constraints);
     if(window.__denyCamera)throw new DOMException('Denied','NotAllowedError');
     if(window.__delayCamera)await new Promise(r=>window.__releaseCamera=r);
     const stream=await original(constraints);window.__streams.push(stream);return stream;
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
   await page.waitForFunction(()=>document.querySelector('.fz-home')?.fzCamera);
   assert.equal(await page.evaluate(()=>window.__constraints.length),0,'no camera access before a tap');
   const open=async()=>{await page.locator('[data-dark-photo]').click();await page.waitForFunction(()=>document.querySelector('.fz-camera-dialog').dataset.ready==='true');};
   const stopped=()=>page.waitForFunction(()=>window.__streams.every(s=>s.getTracks().every(t=>t.readyState==='ended')));
   await open();
   assert.equal(searches.length,0,'opening the view does not spend a search');
   assert.deepEqual(await page.evaluate(()=>({audio:__constraints[0].audio,facing:__constraints[0].video.facingMode.ideal})),{audio:false,facing:'environment'});
   assert.equal(await page.locator('.fz-camera-video').getAttribute('playsinline'),'');
   const rect=await page.locator('.fz-camera-dialog').boundingBox();assert.ok(rect.x===0&&rect.y===0&&rect.width===variant.width&&rect.height===variant.height,'fullscreen camera fits viewport');
   const shutter=await page.locator('.fz-camera-shutter').boundingBox();assert.ok(shutter.y+shutter.height<=variant.height,'shutter stays on screen');
   if(process.env.FINDZIA_TEST_OUTPUT){fs.mkdirSync(process.env.FINDZIA_TEST_OUTPUT,{recursive:true});await page.screenshot({path:path.join(process.env.FINDZIA_TEST_OUTPUT,`camera-${variant.width}-${variant.lang}.png`)});}
   await page.locator('.fz-camera-flip').click();await page.waitForFunction(()=>__constraints.length===2&&document.querySelector('.fz-camera-dialog').dataset.ready==='true');
   assert.equal(await page.evaluate(()=>__streams[0].getTracks()[0].readyState),'ended','switch stops previous camera');
   assert.equal(await page.evaluate(()=>__constraints[1].video.facingMode.ideal),'user');
   await page.locator('.fz-camera-shutter').click();
   await page.waitForResponse(r=>new URL(r.url()).pathname==='/api/search/image/stream');await stopped();
   assert.equal(searches.length,1,'one shutter tap runs one existing Lens search');assert.equal(searches[0].mime_type,'image/jpeg');assert.ok(searches[0].image_base64.length>1000);
   assert.equal(await page.locator('.fz-camera-dialog').isVisible(),false);
   // The camera on the results header uses the same direct view.
   await page.waitForFunction(()=>!document.querySelector('.fz-home').fzRefineBridge.context().busy);
   await page.locator('[data-photo-btn]').click();await page.waitForFunction(()=>document.querySelector('.fz-camera-dialog').dataset.ready==='true');
   await page.keyboard.press('Escape');await stopped();assert.equal(searches.length,1,'cancel never searches');
   await page.evaluate(()=>document.querySelector('.fz-home').fzRefineBridge.resetSearchSession());
   await open();
   const fileChooser=page.waitForEvent('filechooser');await page.locator('.fz-camera-gallery').click();const chooser=await fileChooser;await stopped();
   assert.equal(await chooser.element().getAttribute('capture'),null,'gallery remains a regular image picker');
   const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/search/image/stream');
   await chooser.setFiles({name:'album.jpg',mimeType:'image/jpeg',buffer:Buffer.from(searches[0].image_base64,'base64')});await response;assert.equal(searches.length,2,'album uses the same image-search flow');
   await page.waitForFunction(()=>!document.querySelector('.fz-home').fzRefineBridge.context().busy);
   await page.evaluate(()=>{document.querySelector('.fz-home').fzRefineBridge.resetSearchSession();window.__denyCamera=true;});
   await page.locator('[data-dark-photo]').click();await page.locator('.fz-camera-native').waitFor({state:'visible'});
   const nativePicker=page.waitForEvent('filechooser');await page.locator('.fz-camera-native').click();const native=await nativePicker;
   assert.equal(await native.element().getAttribute('capture'),'environment','denied camera has explicit native capture fallback');await native.setFiles([]);assert.equal(searches.length,2);
   // A permission response arriving after close must immediately release tracks.
   await page.evaluate(()=>{window.__denyCamera=false;window.__delayCamera=true;});
   const count=await page.evaluate(()=>__streams.length);await page.locator('[data-dark-photo]').click();
   await page.waitForFunction(()=>typeof window.__releaseCamera==='function');await page.locator('.fz-camera-head button').click();
   await page.evaluate(()=>__releaseCamera());await page.waitForFunction(n=>__streams.length>n,count);await stopped();
   assert.equal(searches.length,2);assert.deepEqual(errors,[]);assert.deepEqual(await page.evaluate(()=>window.__cspErrors||[]),[],'no CSP errors');
   console.log('PASS',variant,'direct camera, flip, capture, gallery, denial, close and late-permission cleanup');
   await context.close();
  }
 }finally{await browser.close();server.closeAllConnections();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
