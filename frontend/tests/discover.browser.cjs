const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require('playwright');
const trial=JSON.parse(readFileSync(path.join(__dirname,'../trial.json'))).discover_path;
const cats=[['beauty','Beauty','الجمال'],['women','Women','النساء'],['men','Men','الرجال'],['home','Home','المنزل'],['tech','Tech','التقنية'],['active','Active','الرياضة']];
function feed(country='KW',scope='local',edition='100') {
 const currency=country==='JP'?'JPY':'KWD';
 const groups=cats.map(([id,en,ar])=>({id,en,ar,status:'ok',items:Array.from({length:5},(_,i)=>({title:`${en} product ${i}`,store:'Store '+(i%3),url:`https://store${i%3}.example.test/products/${id}-${i}`,image:`https://images.example.test/${id}-${i}.svg`,money:{value:'32.5',currency:i%2?'USD':currency},display_money:{value:i%2?'10.000':'12.500',currency,converted:!!(i%2)},market_scope:scope,merchant_country:scope==='local'?country:'US',discovery_source:i%2?'shopify_catalog':'web_search',discovery_sources:[i%2?'shopify_catalog':'web_search']}))}));
 // A stale/misclassified foreign row must never leak into the local view.
 groups[0].items.push({...groups[0].items[0],title:'Wrong market',merchant_country:scope==='local'?'US':country});
 groups[0].items.push({...groups[0].items[0],title:'Wrong currency',display_money:{value:'99',currency:'EUR'}});
 return {edition,country,currency,scope,theme:Number(edition)%3,cacheable:false,delivery:'mixed_sources',groups,source_counts:{web_search:18,shopify_catalog:12},store_count:3};
}
(async()=>{
 const {createServer}=await import(pathToFileURL(path.join(__dirname,'../server.mjs')));
 const server=createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({executablePath:process.env.FINDZIA_TEST_CHROME,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const home=await fetch(origin);assert.doesNotMatch(await home.text(),/findzia-discover/);
  const response=await fetch(origin+trial);assert.match(response.headers.get('x-robots-tag'),/noindex/);assert.match(response.headers.get('cache-control'),/no-store/);
  for(const variant of [{lang:'en',width:390},{lang:'ar',width:390},{lang:'en',width:1440}]){
   const context=await browser.newContext({viewport:{width:variant.width,height:844},reducedMotion:'reduce'});const errors=[],calls=[];let fail=false,empty=false;
   await context.addInitScript(lang=>localStorage.setItem('findzia-lang',lang),variant.lang);
   await context.route('**/*',async route=>{
    const u=new URL(route.request().url());if(u.origin===origin)return route.continue();
    if(u.hostname==='api.findzia.com'){
     if(u.pathname==='/api/discover/config')return route.fulfill({json:{countries:{KW:'Kuwait',JP:'Japan',SA:'Saudi Arabia'},currencies:{KW:'KWD',JP:'JPY',SA:'SAR'}}});
     calls.push(u.href);if(fail)return route.fulfill({status:503,json:{error:'unavailable'}});
     const result=feed(u.searchParams.get('country'),u.searchParams.get('scope'),String(calls.length+100));if(u.searchParams.has('q'))result.groups=result.groups.slice(0,1);
     if(empty){result.groups.forEach(g=>g.items=[]);result.source_counts={};result.store_count=0;}
     return route.fulfill({json:result});
    }
    if(u.hostname==='images.example.test')return route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 400"><rect width="300" height="400" fill="#eee9df"/><rect x="90" y="100" width="120" height="220" rx="25" fill="#ba8566"/></svg>'});
    return route.abort();
   });
   const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.clock.install();
   await page.goto(origin+trial);await page.locator('.hero').waitFor();
   assert.equal(await page.locator('.product-card').count(),30);assert.equal(calls.length,1);assert.match(calls[0],/scope=local/);
   assert.equal(await page.locator('[data-scope="local"]').getAttribute('aria-pressed'),'true');
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   assert.doesNotMatch(await page.locator('.product-price').allTextContents().then(x=>x.join()),/USD|EUR/);
   assert.equal(await page.locator('.conversion-note').count(),12);
   assert.equal(await page.getByText('Wrong market',{exact:true}).count(),0);
   assert.equal(await page.getByText('Wrong currency',{exact:true}).count(),0);
   const edition=await page.locator('#feed').getAttribute('data-edition');const html=await page.locator('#feed').innerHTML();
   await page.clock.fastForward(660000);assert.equal(calls.length,1);assert.equal(await page.locator('#feed').innerHTML(),html);
   await page.locator('#language').click();assert.equal(calls.length,1);assert.equal(await page.locator('#feed').getAttribute('data-edition'),edition);
   await page.locator('[data-scope="global"]').click();await page.waitForFunction(()=>document.querySelector('#feed').dataset.edition==='102');assert.match(calls[1],/scope=global/);assert.equal(await page.locator('.product-card').count(),30);
   await page.locator('#country').selectOption('JP');await page.waitForFunction(()=>document.querySelector('#feed').dataset.edition==='103');assert.match(calls[2],/country=JP/);assert.match(calls[2],/scope=local/);assert.equal(await page.locator('#currency-badge').textContent(),'JPY');
   assert.doesNotMatch(await page.locator('.product-price').allTextContents().then(x=>x.join()),/KWD|USD|EUR/);
   await page.locator('#query').fill('headphones');await page.locator('.search-submit').click();await page.locator('.search-results').waitFor();assert.match(calls[3],/q=headphones/);
   await page.locator('.search-back').click();await page.locator('.hero').waitFor();
   fail=true;await page.locator('#country').selectOption('KW');await page.locator('#empty').waitFor({state:'visible'});assert.equal(await page.locator('#feed').isVisible(),false);
   fail=false;empty=true;await page.locator('#retry').click();await page.waitForFunction(()=>document.querySelector('#loading').hidden);assert.equal(await page.locator('#feed').isVisible(),false);assert.equal(await page.locator('[data-scope="local"]').getAttribute('aria-pressed'),'true','empty local never silently fills with international');
   empty=false;await page.locator('#retry').click();await page.locator('.hero').waitFor();
   if(process.env.FINDZIA_TEST_SHOTS)await page.screenshot({path:path.join(process.env.FINDZIA_TEST_SHOTS,`market-${variant.lang}-${variant.width}.png`)});
   const stored=await page.evaluate(()=>JSON.stringify({...localStorage,...sessionStorage}));assert.doesNotMatch(stored,/example.test|product|money|image/);
   assert.deepEqual(errors,[]);console.log('PASS',variant,'market isolation, one currency, conversion labels, source diversity, session stability, country/scope switches, empty/failure recovery');await context.close();
  }
 }finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
