/* Photo intake regression: real file picker and mocked APIs, no paid searches. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {pathToFileURL}=require('node:url');
(async()=>{
 const {createServer}=await import(pathToFileURL(path.join(__dirname,'../server.mjs')));
 const server=createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({executablePath:process.env.FINDZIA_TEST_CHROME,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const context=await browser.newContext({viewport:{width:390,height:720}}),requests=[],errors=[];
  await context.addInitScript(()=>localStorage.setItem('findzia-lang','en'));
  await context.route('**/*',async route=>{
   const u=new URL(route.request().url()),p=u.pathname;if(u.origin===origin)return route.continue();
   let data={ok:true};
   if(u.origin==='https://api.findzia.com'){
    if(p==='/api/geo')Object.assign(data,{country:'KW',source:'ip'});
    else if(p==='/api/account/config')data.providers={};
    else if(p==='/api/billing/config')data.plans=[];
    else if(p==='/api/billing/guest'||p==='/api/billing/status')Object.assign(data,{remaining:20,balances:{trial:20,pack:0},guest_token:'test-guest'});
    else if(p==='/api/search/image/stream'){
     requests.push(route.request().postDataJSON());
     return route.fulfill({contentType:'application/x-ndjson',body:'{"event":"done"}\n'});
    }
    return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
   }
   return route.fulfill({contentType:u.hostname==='fonts.googleapis.com'?'text/css':'text/javascript',body:''});
  });
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(origin,{waitUntil:'networkidle'});
  const input=page.locator('input[id^="fz-photo-"]');
  const reset=async()=>{await page.waitForFunction(()=>!document.querySelector('.fz-home').fzRefineBridge.context().busy);await page.evaluate(()=>document.querySelector('.fz-home').fzRefineBridge.resetSearchSession());};
  async function upload(file){
   const count=requests.length;await input.setInputFiles(file);
   await page.waitForFunction(()=>document.querySelector('.fz-home').dataset.homeState==='results',{},{timeout:7000});
   await page.waitForFunction(()=>document.querySelector('.fz-home').fzRefineBridge.context().image_base64,{},{timeout:15000});
   await page.waitForFunction(()=>!document.querySelector('.fz-home').fzRefineBridge.context().busy);
   assert.equal(requests.length,count+1,'exactly one image search per selection');
   return requests.at(-1);
  }
  const small=process.env.FINDZIA_TEST_PHOTO||{name:'chair.png',mimeType:'image/png',buffer:Buffer.from(await page.evaluate(()=>{const c=document.createElement('canvas');c.width=710;c.height=1536;c.getContext('2d').fillRect(0,0,710,1536);return c.toDataURL().split(',')[1];}),'base64')};
  const first=await upload(small);
  if(typeof small==='string')assert.equal(first.image_base64,fs.readFileSync(small).toString('base64'),'attached small JPEG arrives unchanged');
  console.log('PASS small photo reaches image search');await reset();
  const large=Buffer.from(await page.evaluate(()=>{
   const c=document.createElement('canvas');c.width=4032;c.height=3024;const ctx=c.getContext('2d'),pixels=ctx.createImageData(c.width,c.height);let seed=23445;
   for(let i=0;i<pixels.data.length;i+=4){seed=(Math.imul(seed,1664525)+1013904223)|0;pixels.data[i]=(seed>>>16)&255;pixels.data[i+1]=(seed>>>8)&255;pixels.data[i+2]=seed&255;pixels.data[i+3]=255;}
   ctx.putImageData(pixels,0,0);return c.toDataURL('image/jpeg',.96).split(',')[1];
  }),'base64');
  assert.ok(large.length>6*1024*1024,'fixture exceeds old 6 MB guard');
  const result=await upload({name:'iphone-large.jpg',mimeType:'image/jpeg',buffer:large});
  assert.equal(result.image_upload.original_bytes,large.length);
  assert.ok(result.image_upload.upload_bytes<6*1024*1024,'large JPEG is resized before upload');
  console.log('PASS large photo',large.length,'->',result.image_upload.upload_bytes);await reset();
  // A read failure must stay visible with actions, rather than silently returning home.
  await page.evaluate(()=>{window.__readPhoto=FileReader.prototype.readAsDataURL;FileReader.prototype.readAsDataURL=function(){queueMicrotask(()=>this.onerror?.(new Event('error')));};});
  await input.setInputFiles(small);
  await page.locator('[data-photo-upload-error]').waitFor({state:'visible'});
  assert.equal(requests.length,2,'unreadable photo is not sent');
  assert.equal(await page.locator('[data-photo-upload-error] button').count(),2,'retry and choose photo are available');
  await page.waitForFunction(()=>{const r=document.querySelector('.fz-home');return r.dataset.pageTransitioning!=='true'&&!r.dataset.waitActive;});
  if(process.env.FINDZIA_TEST_OUTPUT){fs.mkdirSync(process.env.FINDZIA_TEST_OUTPUT,{recursive:true});await page.screenshot({path:path.join(process.env.FINDZIA_TEST_OUTPUT,'photo-read-error.png')});}
  await page.evaluate(()=>FileReader.prototype.readAsDataURL=window.__readPhoto);
  await page.locator('[data-photo-upload-error] button').first().click();
  await page.waitForFunction(()=>document.querySelector('.fz-home').fzRefineBridge.context().image_base64);
  await page.waitForFunction(()=>!document.querySelector('.fz-home').fzRefineBridge.context().busy);
  assert.equal(requests.length,3,'retry uses retained file once');
  console.log('PASS read failure is visible and retry recovers');await reset();
  // Unsupported, uncompressed files above the server limit never enter a paid request.
  await input.setInputFiles({name:'large.heic',mimeType:'image/heic',buffer:Buffer.alloc(17*1024*1024)});
  await page.locator('[data-photo-upload-error]').waitFor({state:'visible'});
  assert.equal(requests.length,3);
  assert.match(await page.locator('[data-photo-upload-error]').textContent(),/smaller|smaller copy/i);
  console.log('PASS oversized undecodable file has visible recovery');
  await reset();await upload(small);assert.equal(requests.length,4,'next selection works after an error');
  assert.deepEqual(errors,[]);await context.close();
 }finally{await browser.close();server.closeAllConnections();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
