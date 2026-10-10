/* Real UI, synthetic streams and images. No provider, billing or merchant calls. */
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const path=require('node:path'),{pathToFileURL}=require('node:url'),{spawnSync}=require('node:child_process');
const classified=spawnSync(process.env.FINDZIA_TEST_PYTHON||'python',['-c',"import json; from findzia_market_evidence import MerchantMarkets; rows=json.load(open('tests/fixtures/kuwait_similar_storefronts.json')); m=MerchantMarkets(['kw','sa','ae','bh','qa','om','us']); print(json.dumps([m.classify(dict(r,source='google_lens',match_type='similar'), 'kw') for r in rows]))"],{cwd:path.join(__dirname,'../..'),encoding:'utf8'});
assert.equal(classified.status,0,classified.stderr);const marketRows=JSON.parse(classified.stdout);
const art='<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400"><rect width="400" height="400" fill="#ddd"/><rect x="70" y="140" width="260" height="60" rx="10" fill="#886c43"/></svg>';
const offer=(id,scope='local',extra={})=>({title:'Coffee table '+id,store:'Store '+id,
 url:'https://store.example.test/products/'+id,image:'https://store.example.test/'+id+'.svg',
 price:'24.500 KWD',currency:'KWD',market_scope:scope,merchant_country:scope==='local'?'KW':'US',
 merchant_country_evidence:'registered_storefront',market_policy:'merchant-evidence-v2',
 evaluation_token:'mock-media-token',source:'google_lens',retrieval_sources:['google_lens'],search_origin:'image',photo_match_status:'approved',
 match_type:'similar',match_score:.5,price_display_ready:true,price_display_currency:'KWD',price_amount:24.5,
 price_contract:'findzia-money-v1',price_display_major:'24',price_display_minor:'.500',...extra});
(async()=>{
 const {createServer}=await import(pathToFileURL(path.join(__dirname,'../server.mjs')));
 const server=createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({executablePath:process.env.FINDZIA_TEST_CHROME,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  for(const variant of [{lang:'en',layout:'grid'},{lang:'ar',layout:'grid'},{lang:'en',layout:'list'},{lang:'ar',layout:'cinema'}]){
   const context=await browser.newContext({viewport:{width:390,height:780},reducedMotion:'reduce'});
   const errors=[];
   await context.addInitScript(v=>{
    localStorage.setItem('findzia-results-layout-v1',v.layout);localStorage.setItem('findzia-lang',v.lang);
    localStorage.setItem('findzia-theme','light');
    const native=fetch.bind(window);
    window.fetch=(url,options)=>/\/api\/search\/(?:image\/)?stream/.test(String(url))?
     Promise.resolve(new Response(new ReadableStream({start(c){window.__stream=c;}}),{headers:{'Content-Type':'application/x-ndjson'}})):native(url,options);
    window.__send=e=>__stream.enqueue(new TextEncoder().encode(JSON.stringify(e)+'\n'));
   },variant);
   await context.route('**/*',async route=>{
    const u=new URL(route.request().url()),p=u.pathname;
    if(u.origin===origin)return route.continue();
    if(u.hostname==='store.example.test'||p.includes('/media/proxy'))return route.fulfill({contentType:'image/svg+xml',body:art});
    if(u.origin==='https://api.findzia.com'){
     let data={ok:true};
     if(p==='/api/geo')data.country='KW';
     else if(p==='/api/account/config')data.providers={};
     else if(p==='/api/billing/config')data.plans=[];
     else if(p==='/api/billing/guest'||p==='/api/billing/status')Object.assign(data,{remaining:20,balances:{trial:20,pack:0},guest_token:'test-guest'});
     else if(p.startsWith('/api/media/check')){
      const body=route.request().postDataJSON();
      if(body.images)return route.fulfill({contentType:'application/x-ndjson',body:body.images.map((_,id)=>JSON.stringify({id,ok:true,usable:true,status:200})+'\n').join('')});
      data.usable=true;
     }
     return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
    }
    return route.fulfill({contentType:u.hostname==='fonts.googleapis.com'?'text/css':'text/javascript',body:''});
   });
   const page=await context.newPage();page.setDefaultTimeout(12000);page.on('pageerror',e=>errors.push(e.message));
   await page.goto(origin,{waitUntil:'networkidle'});
   await page.locator('input[id^="fz-photo-"]').setInputFiles({name:'table.svg',mimeType:'image/svg+xml',buffer:Buffer.from(art)});
   await page.waitForFunction(()=>!!window.__stream);
   const send=e=>page.evaluate(event=>__send(event),e);
   const keys=()=>page.locator('.fz-card-shell').evaluateAll(nodes=>nodes.map(n=>n.dataset.stableKey||n.dataset.cinemaKey));
   const rows=marketRows.map((row,i)=>offer(String(i),'local',row));
   for(const row of rows)await send({event:'result',item:row});
   await page.waitForFunction(()=>document.querySelectorAll('.fz-card-shell').length===13);
   for(const [filter,count] of [['local',9],['alternative',13],['global',3],['all',13]]){
    await page.locator('[data-filter="'+filter+'"]').click();
    await page.waitForFunction(count=>document.querySelectorAll('.fz-card-shell').length===count,count);
    const actual=await keys();
    assert.equal(new Set(actual).size,count,'All never duplicates an offer');
    const expected=rows.filter(r=>filter==='local'?r.market_scope==='local':filter==='global'?r.market_scope==='global':true).map(r=>r.url).sort();
    assert.deepEqual(actual.sort(),expected,filter+' contains the correct storefronts');
   }
   // A late snapshot goes through the same display normalization and filters.
   await send({event:'snapshot',results:rows});
   await page.locator('[data-filter="local"]').click();
   await page.waitForFunction(()=>document.querySelectorAll('.fz-card-shell').length===9);
   await page.evaluate(()=>{__send({event:'done'});__stream.close();});
   await page.waitForFunction(()=>!document.querySelector('.fz-home').fzRefineBridge.context().busy);
   assert.deepEqual(errors,[]);console.log('PASS',variant,'9 Kuwait, 13 Similar, 3 Global, 13 unique All');
   await context.close();
  }
 }finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
