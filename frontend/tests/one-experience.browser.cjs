/* Private trial integration: real DOM, images, motion and a mocked signed stream. */
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),{pathToFileURL}=require('node:url');
const art=i=>`<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800"><defs><radialGradient id="b"><stop stop-color="#eeeae0"/><stop offset="1" stop-color="#b5beb6"/></radialGradient></defs><rect width="800" height="800" fill="url(#b)"/><g transform="translate(${i*6},0)"><ellipse cx="400" cy="583" rx="216" ry="25" fill="#0002"/><path d="M230 420V335a170 170 0 0 1 340 0v90" fill="none" stroke="${['#253731','#e2d3b9','#243248','#6f423a'][i%4]}" stroke-width="57"/><path d="M230 370v112M570 370v112" stroke="#121b18" stroke-width="24"/><rect x="181" y="360" width="103" height="195" rx="43" fill="${['#243c31','#c6b38f','#22384b','#824f44'][i%4]}"/><rect x="514" y="360" width="103" height="195" rx="43" fill="${['#243c31','#c6b38f','#22384b','#824f44'][i%4]}"/><path d="M205 382v151M591 382v151" stroke="#ffffff22" stroke-width="6" stroke-linecap="round"/></g></svg>`;
const offer=i=>({title:'Studio wireless headphones '+i,store:'Audio Store '+i,url:'https://store.example.test/item-'+i,image:'https://store.example.test/'+i+'.svg',
 price:(24+i)+'.500 KWD',currency:'KWD',country:'KW',market:'local',photo_match_status:'approved',match_type:'exact',
 price_display_ready:true,price_display_currency:'KWD',price_amount:24.5+i,price_contract:'findzia-money-v1',price_display_major:String(24+i),price_display_minor:'.500',evaluation_token:'test-'+i});
(async()=>{
 const {createServer}=await import(pathToFileURL(path.join(__dirname,'../server.mjs'))),server=createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const origin='http://127.0.0.1:'+server.address().port,trial=JSON.parse(fs.readFileSync(path.join(__dirname,'../trial.json'))).path;
 const browser=await chromium.launch({executablePath:process.env.FINDZIA_TEST_CHROME,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  for(const variant of [{width:390,height:844,lang:'ar',theme:'dark'},{width:320,height:568,lang:'ar',theme:'light'},{width:1440,height:900,lang:'en',theme:'light'},{width:390,height:844,lang:'ar',theme:'light',photo:true},{width:390,height:844,lang:'ar',theme:'light',photo:true,unavailable:true}]){
   const context=await browser.newContext({viewport:{width:variant.width,height:variant.height}}),errors=[],calls=[];
   await context.addInitScript(v=>{
    localStorage.setItem('findzia-lang',v.lang);localStorage.setItem('findzia-appearance-v1',v.theme);localStorage.setItem('findzia-theme',v.theme);
    const native=window.fetch.bind(window);
    window.fetch=(url,options)=>/\/api\/search\/(?:image\/)?stream/.test(String(url))?Promise.resolve(new Response(new ReadableStream({start(c){window.__stream=c;}}),{headers:{'Content-Type':'application/x-ndjson'}})):native(url,options);
    window.__send=e=>__stream.enqueue(new TextEncoder().encode(JSON.stringify(e)+'\n'));
   },variant);
   await context.route('**/*',async route=>{
    const u=new URL(route.request().url()),p=u.pathname;if(u.origin===origin)return route.continue();
    if(u.origin==='https://store.example.test'||p.includes('/media/proxy'))return route.fulfill({contentType:'image/svg+xml',body:art(Number(p.match(/(\d+)\.svg/)?.[1]||0))});
    if(u.origin==='https://api.findzia.com'){
     let data={ok:true};
     if(p==='/api/geo')Object.assign(data,{country:'KW',source:'ip'});
     else if(p==='/api/account/config')data.providers={};
     else if(p==='/api/billing/config')data.plans=[];
     else if(p==='/api/billing/guest'||p==='/api/billing/status')Object.assign(data,{remaining:20,balances:{trial:20,pack:0},guest_token:'test-guest'});
     else if(p.startsWith('/api/media/check')){
      const body=route.request().postDataJSON();
      if(body.images)return route.fulfill({contentType:'application/x-ndjson',body:body.images.map((_,id)=>JSON.stringify({id,ok:true,usable:true,status:200})+'\n').join('')});
      data.usable=true;
     }else if(p==='/api/choice'){
      const body=route.request().postDataJSON();calls.push(body);
      if(variant.unavailable)Object.assign(data,{status:'unavailable',reason:'visual_incomplete'});
      else if(!variant.photo&&!body.answers.length){const ar=variant.lang==='ar';Object.assign(data,{status:'question',question:ar?'شنو الأهم لك بالسماعة؟':'What matters most in your headphones?',choices:ar?['الاستخدام اليومي','للألعاب','للسفر']:['Everyday listening','Gaming','Travel'],options:ar?[{label:'الاستخدام اليومي',detail:'لاسلكية وخفيفة'},{label:'للألعاب',detail:'ميكروفون مدمج'},{label:'للسفر',detail:'تصميم قابل للطي'}]:[{label:'Everyday listening',detail:'Lightweight and wireless'},{label:'Gaming',detail:'Built-in microphone'},{label:'Travel',detail:'Foldable design'}]});}
      else Object.assign(data,{status:'selected',visual_verified:true,token:'test-2',url:offer(2).url,title:offer(2).title,store:offer(2).store,money:{amount:26.5,currency:'KWD'},reason:'Matches your preference.',match:'suitable'});
     }
     return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
    }
    return route.fulfill({contentType:u.hostname==='fonts.googleapis.com'?'text/css':'text/javascript',body:''});
   });
   const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(origin+trial,{waitUntil:'networkidle'});
   if(variant.photo)await page.evaluate(()=>{const c=document.createElement('canvas');c.width=c.height=32;c.getContext('2d').fillRect(0,0,32,32);document.querySelector('.fz-home').fzRefineBridge.billingResume({image_base64:c.toDataURL('image/png').split(',')[1],mime_type:'image/png',country:'KW'});});
   else await page.evaluate(()=>document.querySelector('.fz-home').fzRefineBridge.accountSearch('headphones'));
   await page.waitForFunction(()=>!!window.__stream);
   await page.evaluate(items=>items.forEach(item=>__send({event:'result',item})),[0,1,2,3,4,5].map(offer));
   await page.waitForFunction(()=>document.querySelector('.fz-home').fzRefineBridge.choiceRows().length===6);
   await page.waitForFunction(()=>document.querySelector('.fz-one-image[data-active="true"]')?.naturalWidth>0);
   if(variant.photo){
    if(!variant.unavailable){
     await page.waitForFunction(()=>document.querySelector('.fz-one').dataset.state==='selected');
     assert.equal(await page.evaluate(()=>document.querySelector('.fz-home').fzRefineBridge.context().busy),true,'pixel match reveals while providers continue');
    }
    await page.evaluate(()=>{__send({event:'done'});__stream.close();});
    await page.waitForFunction(state=>document.querySelector('.fz-one').dataset.state===state,variant.unavailable?'empty':'selected');
    if(variant.unavailable){
     assert.equal(await page.locator('.fz-one-open').first().isVisible(),false);
     assert.ok(await page.locator('.fz-one-image[data-active="true"]').getAttribute('src').then(s=>s.startsWith('data:image/png')),'restore reference on failed review');
     assert.ok(calls.length<=2);
    }else{
     assert.equal(await page.locator('.fz-one-open').first().getAttribute('href'),offer(2).url);
     assert.equal(calls.length,1,'no repeated photo reveal at stream end');
     assert.equal(calls[0].offer_images.length,6);
    }
    assert.deepEqual(errors,[]);console.log('PASS photo',variant.unavailable?'finite incomplete review':'early verified selection, stable at stream end');await context.close();continue;
   }
   const initial=await page.locator('.fz-one-image[data-active="true"]').getAttribute('src');
   if(variant.width===390){
    await page.waitForFunction(src=>document.querySelector('.fz-one-image[data-active="true"]')?.src!==src,initial,{timeout:7000});
    assert.equal(await page.locator('.fz-one').getAttribute('data-state'),'pending');
   }
   if(process.env.FINDZIA_TEST_OUTPUT){fs.mkdirSync(process.env.FINDZIA_TEST_OUTPUT,{recursive:true});await page.screenshot({path:path.join(process.env.FINDZIA_TEST_OUTPUT,`one-pending-${variant.width}.png`)});}
   await page.evaluate(()=>{__send({event:'done'});__stream.close();});
   await page.waitForFunction(()=>document.querySelector('.fz-one').dataset.state==='question');
   assert.equal(await page.locator('.fz-one-answer').count(),3);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true,'no horizontal overflow');
   const card=await page.locator('.fz-one-stage').boundingBox(),answers=await page.locator('.fz-one-question').boundingBox();
   assert.ok(answers.y>=card.y&&answers.y+answers.height<=card.y+card.height,'all question controls fit inside the picture');
   if(process.env.FINDZIA_TEST_OUTPUT)await page.screenshot({path:path.join(process.env.FINDZIA_TEST_OUTPUT,`one-question-${variant.width}.png`),fullPage:true});
   await page.locator('.fz-one-answer').first().click();
   await page.waitForFunction(()=>document.querySelector('.fz-one').dataset.state==='selected');
   await page.waitForFunction(()=>document.querySelector('.fz-one-image[data-active="true"]').getAnimations().length===0);
   assert.equal(await page.locator('.fz-one-price').getAttribute('aria-label'),'26.500 KWD');
   assert.equal(await page.locator('.fz-one-open').first().getAttribute('href'),offer(2).url);
   assert.equal(calls.at(-1).answers.length,1);
   if(process.env.FINDZIA_TEST_OUTPUT)await page.screenshot({path:path.join(process.env.FINDZIA_TEST_OUTPUT,`one-final-${variant.width}.png`),fullPage:true});
   assert.deepEqual(errors,[]);console.log('PASS',variant,'decoded crossfade, question bounds, single answer, physical final price and no page errors');await context.close();
  }
 }finally{await browser.close();server.closeAllConnections();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
