/* Real browser flow with mocked shopping/account APIs. No paid search calls. */
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),{pathToFileURL}=require('node:url');
const art='<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400"><rect width="400" height="400" fill="#e6e9df"/><path d="m150 75-80 40 35 105 40-15v135h110V205l40 15 35-105-80-40-50 25Z" fill="#748069"/><path d="M200 100v230" stroke="#f4e7d0" stroke-width="6"/></svg>';
const offer={title:'Ski jacket',store:'Test store',url:'https://store.example.test/jacket',image:'https://store.example.test/jacket.svg',price:'24.500 KWD',currency:'KWD',country:'KW',market:'local',photo_match_status:'approved',price_display_ready:true,price_display_currency:'KWD',price_amount:24.5,price_contract:'findzia-money-v1',price_display_major:'24',price_display_minor:'.500',evaluation_token:'test-jacket'};
(async()=>{
 const {createServer}=await import(pathToFileURL(path.join(__dirname,'../server.mjs'))),server=createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({executablePath:process.env.FINDZIA_TEST_CHROME,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  for(const variant of [{width:390,height:720,lang:'en'},{width:320,height:568,lang:'ar',dark:true},{width:1440,height:900,lang:'ja'}]){
   const context=await browser.newContext({viewport:{width:variant.width,height:variant.height}}),calls=[],errors=[];
   let releaseGuide=null,holdGuide=false;
   await context.addInitScript(v=>{localStorage.setItem('findzia-lang',v.lang);localStorage.setItem('findzia-theme',v.dark?'dark':'light');},variant);
   await context.route('**/*',async route=>{
    const u=new URL(route.request().url()),p=u.pathname;if(u.origin===origin)return route.continue();
    if(u.origin==='https://store.example.test')return route.fulfill({contentType:'image/svg+xml',body:art});
    if(u.origin==='https://api.findzia.com'){
     const payload=route.request().method()==='POST'?route.request().postDataJSON():{};calls.push({path:p,payload});let data={ok:true};
     if(p==='/api/geo')Object.assign(data,{country:'KW',source:'ip'});
     else if(p==='/api/account/config')data.providers={};
     else if(p==='/api/billing/config')data.plans=[];
     else if(p==='/api/billing/guest'||p==='/api/billing/status')Object.assign(data,{remaining:20,balances:{trial:20,pack:0},guest_token:'test-guest'});
     else if(p==='/api/search/image/stream'||p==='/api/search/stream'||p==='/api/refine/search/stream'){
      const refine=p==='/api/refine/search/stream',photo=p==='/api/search/image/stream';
      const events=[{event:'query',query:photo?'Ski jacket':payload.query},...(refine?[{event:'start',display_query:'Ski jacket '+payload.extra_specs,extra_specs_applied:payload.extra_specs}]:[]),{event:'result',item:{...offer,...(refine?{refinement_verified:true,url:offer.url+'-refined'}:{})}},{event:'done',count:1}];
      return route.fulfill({contentType:'application/x-ndjson',body:events.map(e=>JSON.stringify(e)+'\n').join('')});
     }else if(p==='/api/guide/discover'){
      if(holdGuide)await new Promise(r=>releaseGuide=r);
      const second=payload.turns?.length>0;
      Object.assign(data,{status:'question',question:second?'Which colour?':'Which style?',question_key:second?'colour':'style',choices:second?[{label:'Black',answer:'Black'},{label:'Blue',answer:'Blue'}]:[{label:'Ski jacket',answer:'Ski jacket'},{label:'Anorak',answer:'Anorak'}],search_query:payload.kind==='image'?'Unrequested server rewrite':payload.draft_query});
     }else if(p.includes('/media/proxy'))return route.fulfill({contentType:'image/svg+xml',body:art});
     else if(p.startsWith('/api/media/check')){
      if(payload.images)return route.fulfill({contentType:'application/x-ndjson',body:payload.images.map((_,id)=>JSON.stringify({id,ok:true,usable:true,status:200})+'\n').join('')});
      data.usable=true;
     }
     return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
    }
    return route.fulfill({contentType:u.hostname==='fonts.googleapis.com'?'text/css':'text/javascript',body:''});
   });
   const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(origin,{waitUntil:'networkidle'});
   await page.evaluate(dark=>{const s=document.querySelector('[data-solar-mode]');s.value=dark?'dark':'light';s.dispatchEvent(new Event('change',{bubbles:true}));},!!variant.dark);
   const input=page.locator('textarea[id^="fz-query-"]'),query=page.locator('.fz-guide-proposed');
   const upload=async()=>{
    await page.locator('input[id^="fz-photo-"]').setInputFiles({name:'jacket.svg',mimeType:'image/svg+xml',buffer:Buffer.from(art)});
    await page.waitForFunction(()=>{const c=document.querySelector('.fz-home').fzRefineBridge.context();return c.kind==='image'&&!c.busy&&c.can_refine&&c.query==='Ski jacket';});
    assert.equal(await input.inputValue(),'','photo descriptions never enter the text header');
    assert.equal(await page.locator('[data-image-query-chip],[data-image-query-plus]').count(),0);
   };
   const open=async()=>{await page.locator('[data-guide-open]').click();await page.locator('.fz-guide-choice').first().waitFor();};
   await upload();await open();
   assert.equal(await query.inputValue(),'','AI-generated search rewrites cannot replace explicit photo details');
   assert.equal(await page.locator('.fz-guide-context img').count(),0);
   await page.waitForFunction(()=>document.querySelector('[data-guide-photo] img')?.naturalWidth>0);
   await page.evaluate(()=>window.__photoNode=document.querySelector('[data-guide-photo] img'));
   holdGuide=true;await page.locator('.fz-guide-choice').first().click();
   assert.equal(await query.inputValue(),'Ski jacket','selected answer appears immediately during the next question request');
   await page.waitForFunction(()=>document.querySelector('.fz-guide-body').getAttribute('aria-busy')==='true');
   while(!releaseGuide)await new Promise(r=>setTimeout(r,10));holdGuide=false;releaseGuide();releaseGuide=null;
   await page.locator('.fz-guide-choice').first().waitFor();
   assert.equal(await query.inputValue(),'Ski jacket','server response preserves the selected answer');
   await page.locator('.fz-guide-photo-plus').click();assert.equal(await query.evaluate(n=>document.activeElement===n),true);
   await query.fill('Ski jacket waterproof');await page.locator('.fz-guide-choice').first().click();await page.locator('.fz-guide-choice').first().waitFor();
   assert.equal(await query.inputValue(),'Ski jacket waterproof Black','answers append after manually entered details');
   assert.equal(await page.evaluate(()=>window.__photoNode===document.querySelector('[data-guide-photo] img')),true,'question changes retain the same decoded image node');
   assert.equal(await page.locator('.fz-guide-answers').count(),0,'photo answers appear only beside their photo');
   await page.locator('.fz-guide-navigation button').click();assert.equal(await query.inputValue(),'Ski jacket waterproof','Back restores editable details');
   await page.locator('.fz-guide-choice').first().click();await page.locator('.fz-guide-choice').first().waitFor();
   await page.locator('.fz-guide-close').click();await open();assert.equal(await query.inputValue(),'Ski jacket waterproof Black','closing/reopening keeps the draft');
   await page.locator('[data-guide-photo-composer]').scrollIntoViewIfNeeded();
   const bounds=await page.evaluate(()=>{const d=document.querySelector('.fz-guide'),c=d.querySelector('[data-guide-photo-composer]'),q=c.querySelector('textarea'),r=c.getBoundingClientRect(),qr=q.getBoundingClientRect(),ir=c.querySelector('img').getBoundingClientRect();return{overflow:d.scrollWidth>d.clientWidth+1,composerOverflow:c.scrollWidth>c.clientWidth+1,queryWidth:qr.width,imageWidth:ir.width,inComposer:qr.left>=r.left&&qr.right<=r.right};});
   assert.equal(bounds.overflow,false);assert.equal(bounds.composerOverflow,false);assert.ok(bounds.queryWidth>=80&&bounds.imageWidth>=52&&bounds.inComposer,JSON.stringify(bounds));
   if(process.env.FINDZIA_TEST_OUTPUT){fs.mkdirSync(process.env.FINDZIA_TEST_OUTPUT,{recursive:true});await page.screenshot({path:path.join(process.env.FINDZIA_TEST_OUTPUT,`composer-${variant.width}-${variant.lang}.png`)});}
   await page.locator('[data-guide-refine-search]').click();
   await page.waitForFunction(()=>document.querySelector('.fz-home').fzPhotoRefinementDiagnostics()?.status==='complete');
   const refine=calls.find(c=>c.path==='/api/refine/search/stream').payload;
   assert.equal(refine.extra_specs,'Ski jacket waterproof Black');assert.equal(refine.kind,'image');assert.ok(refine.image_base64);assert.equal(await input.inputValue(),'');
   // Removing the attachment switches this composer to an actual text search.
   await upload();await open();await page.locator('.fz-guide-photo-remove').click();await page.locator('.fz-guide-choice').first().waitFor();
   assert.equal(await page.locator('[data-guide-photo]').count(),0);assert.equal(await query.inputValue(),'Ski jacket');
   await query.fill('Blue raincoat');await page.locator('[data-guide-refine-search]').click();
   await page.waitForFunction(()=>{const c=document.querySelector('.fz-home').fzRefineBridge.context();return c.kind==='text'&&!c.busy&&c.query==='Blue raincoat';});
   let textCall=calls.filter(c=>c.path==='/api/search/stream').at(-1).payload;assert.equal(textCall.query,'Blue raincoat');assert.equal(textCall.image_base64,undefined);
   // Main search never silently refines the preceding photo.
   await upload();await input.fill('Coffee table');await input.press('Enter');
   await page.waitForFunction(()=>{const c=document.querySelector('.fz-home').fzRefineBridge.context();return c.kind==='text'&&!c.busy&&c.query==='Coffee table';});
   textCall=calls.filter(c=>c.path==='/api/search/stream').at(-1).payload;assert.equal(textCall.query,'Coffee table');assert.equal(textCall.shopping_context.query,'');
   assert.equal(calls.filter(c=>c.path==='/api/refine/search/stream').length,1,'only the AI photo composer refines a photo');
   assert.deepEqual(errors,[]);console.log('PASS',variant,'photo composer, immediate cumulative answers, stable image, edit/back/reopen, remove, photo refinement and independent text search');await context.close();
  }
 }finally{await browser.close();server.closeAllConnections();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
