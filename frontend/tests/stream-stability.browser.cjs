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
  for(const variant of [{width:390,height:720,lang:'en'},{width:320,height:568,lang:'ar',reduced:true},{width:1440,height:900,lang:'ja'},{width:390,height:720,lang:'en',layout:'list'},{width:1440,height:900,lang:'ja',layout:'cinema'}].filter(v=>!process.env.FINDZIA_TEST_LAYOUT||(v.layout||'grid')===process.env.FINDZIA_TEST_LAYOUT)){
   const context=await browser.newContext({viewport:{width:variant.width,height:variant.height},reducedMotion:variant.reduced?'reduce':'no-preference'});
   let releaseBilling;const billing=new Promise(r=>releaseBilling=r),errors=[];
   await context.addInitScript(variant=>{
    localStorage.setItem('findzia-results-layout-v1',variant.layout||'grid');
    localStorage.setItem('findzia-lang',variant.lang);localStorage.setItem('findzia-theme','light');
    const native=window.fetch.bind(window);
    window.fetch=(url,options)=>{
     if(String(url).includes('/api/search/image/stream'))return Promise.resolve(new Response(new ReadableStream({start(c){window.__stream=c;}}),{headers:{'Content-Type':'application/x-ndjson'}}));
     return native(url,options);
    };
    window.__send=event=>window.__stream.enqueue(new TextEncoder().encode(JSON.stringify(event)+'\n'));
   },variant);
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
   assert.equal(await page.locator('.fz-search-wait .fz-one-price,.fz-search-wait .fz-one-reel').count(),0);
   const settle=()=>page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
   const cardCount=count=>page.waitForFunction(n=>document.querySelectorAll('[data-results-body] .fz-card-shell').length===n,count);
   const selector='[data-results-body] .fz-card-shell';
   const marketGroups=()=>page.locator('[data-results-body]>.fz-market-group').evaluateAll(nodes=>nodes.map(n=>n.dataset.stableGroup||n.dataset.cinemaGroup));
   const measure=()=>page.evaluate(()=>Object.fromEntries([...document.querySelectorAll('[data-results-body] .fz-card-shell')].map(card=>{
    const rect=card.getBoundingClientRect(),group=card.closest('.fz-market-group'),gr=card.parentElement.getBoundingClientRect(),img=card.querySelector('img'),ir=img.getBoundingClientRect();
    return[card.dataset.stableKey||card.dataset.cinemaKey,{group:group.dataset.stableGroup||group.dataset.cinemaGroup,x:rect.x,y:rect.y-gr.y,w:rect.width,h:rect.height,ix:ir.x-rect.x,iy:ir.y-rect.y,iw:ir.width,ih:ir.height}];
   })));
   const pinned=async(before,why)=>{await settle();const after=await measure();for(const [key,rect]of Object.entries(before))if(after[key]&&after[key].group===rect.group)for(const prop of Object.keys(rect).filter(p=>p!=='group'))assert.ok(Math.abs(rect[prop]-after[key][prop])<1,why+' '+key+' '+prop+': '+rect[prop]+' -> '+after[key][prop]);};
   await settle();let baseline=await measure();
   await page.evaluate(()=>{window.__originalCard=document.querySelector('.fz-card-shell');window.__originalImage=__originalCard.querySelector('img');});
   const readTop=()=>page.evaluate(()=>__originalCard.getBoundingClientRect().top);
   const send=async(event,item)=>{await page.evaluate(x=>__send(x),{event,item});await settle();};
   const originalTop=await readTop();
   await send('result',offer('b','local'));await cardCount(2);await pinned(baseline,'late local');
   assert.deepEqual(await marketGroups(),['local','global']);
   if(variant.layout!=='list')assert.ok(Math.abs(await readTop()-originalTop)<1,'late local section preserves the visible product position');
   const similar={...offer('similar','global'),search_origin:'image',image_query_result:true,retrieval_sources:['bing_reverse_image'],alternative_visual_status:'approved',alternative_visual_policy:'156.7.3',alternative_visual_proof:'test-proof'};
   await send('result',similar);await cardCount(3);
   assert.deepEqual(await marketGroups(),['local','alternative','global']);
   if(variant.layout!=='list')assert.ok(Math.abs(await readTop()-originalTop)<1,'similar section also preserves the visible product');
   assert.equal(await page.locator('.fz-market-head h3').count(),3);
   assert.equal(await page.locator('.fz-market-head h3').first().isVisible(),true);
   assert.deepEqual(await page.locator('[data-results-body] .fz-market-count').allTextContents(),['1','1','1']);
   if(process.env.FINDZIA_TEST_OUTPUT){fs.mkdirSync(process.env.FINDZIA_TEST_OUTPUT,{recursive:true});await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(process.env.FINDZIA_TEST_OUTPUT,`groups-${variant.width}-${variant.lang}-${variant.layout||'grid'}.png`),fullPage:true});}
   baseline=await measure();
   for(let i=0;i<8;i++){
    await send('result',{...offer('late-'+i,'local'),match_type:'exact',match_score:1,price_amount:1+i,price_display_major:String(1+i)});
    await cardCount(i+4);await pinned(baseline,'new higher-ranked offer');baseline=await measure();
   }
   await send('upsert',{...offer('a'),match_type:'exact',match_score:0.99,price_amount:32,price_display_major:'32'});
   await pinned(baseline,'price correction');
   assert.equal(await page.evaluate(()=>__originalCard.isConnected&&__originalImage===__originalCard.querySelector('img')),true);
   await send('upsert',{...offer('b','local'),hidden:true});await cardCount(10);
   if(variant.layout!=='cinema')await pinned(baseline,'rejection');
   baseline=await measure();await send('result',offer('replacement','local'));await cardCount(11);
   if(variant.layout!=='cinema')await pinned(baseline,'retired slot refill');
   assert.equal(await page.locator('.fz-result-gap').count(),0);
   await page.evaluate(()=>{const top=document.querySelector('.fz-fixed-header').getBoundingClientRect().bottom;scrollBy(0,__originalCard.getBoundingClientRect().top-top-30);});await settle();
   const reading=await readTop();baseline=await measure();
   for(let i=8;i<12;i++){await send('result',offer('late-'+i,'local'));await cardCount(i+4);await pinned(baseline,'stream while reading');assert.ok(Math.abs(await readTop()-reading)<1,'growing local section preserves viewport anchor');}
   await send('upsert',{...similar,hidden:true});await cardCount(14);
   assert.deepEqual(await marketGroups(),['local','global'],'an empty section is removed');
   assert.ok(Math.abs(await readTop()-reading)<1,'removing an earlier section preserves viewport anchor');
   baseline=await measure();
   await page.evaluate(()=>{__send({event:'done'});__stream.close();});
   await page.waitForFunction(()=>!document.querySelector('.fz-home').fzRefineBridge.context().busy);await pinned(baseline,'completion');
   const stageEffects=await page.evaluate(()=>[...document.querySelectorAll('.fz-media-stage')].flatMap(n=>n.getAnimations()).length);
   assert.equal(stageEffects,0,'existing product photos never replay media fades');
   await page.evaluate(()=>scrollTo(0,0));
   await page.locator('[data-sort-trigger]').click();await page.locator('[data-sort-value="price"]').click();await settle();
   assert.equal(await page.locator('.fz-card-shell').first().getAttribute(variant.layout==='cinema'?'data-cinema-key':'data-stable-key'),'https://store.example.test/late-0','explicit price sort still works');
   if(process.env.FINDZIA_TEST_OUTPUT){fs.mkdirSync(process.env.FINDZIA_TEST_OUTPUT,{recursive:true});await page.screenshot({path:path.join(process.env.FINDZIA_TEST_OUTPUT,`stable-${variant.width}-${variant.lang}-${variant.layout||'grid'}.png`)});}
   assert.deepEqual(errors,[]);console.log('PASS',variant,'ordered market sections, retained images, stable group slots, viewport anchoring, rejections and manual sort');await context.close();

  }
 }finally{await browser.close();server.closeAllConnections();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
