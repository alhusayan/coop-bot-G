/* Run after build, with Playwright and optionally FINDZIA_TEST_CHROME.
 * All API and third-party traffic is mocked; no paid searches or ad events. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const campaign='/?utm_source=google&utm_medium=cpc&utm_campaign=findzia_jp_search&utm_content=photo';
const trial=JSON.parse(readFileSync(path.join(__dirname,'../trial.json'),'utf8')).path;
(async()=>{
 const {createServer}=await import(pathToFileURL(path.join(__dirname,'../server.mjs')));
 const server=createServer();await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({executablePath:process.env.FINDZIA_TEST_CHROME,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  for(const test of [
   {name:'existing Japan ad',url:campaign,geo:'KW',lang:'ja',country:'JP',search:true},
   {name:'Japan ad overrides legacy English',url:campaign,geo:'US',saved:'en',lang:'ja',country:'JP',switch:true},
   {name:'direct Japan page',url:'/jp',geo:'US',lang:'ja',country:'JP'},
   {name:'trailing slash and blocked storage',url:'/jp/',geo:'US',blocked:true,lang:'ja',country:'JP',switch:true},
   {name:'Japan visitor on homepage',url:'/',geo:'JP',lang:'ja',country:'JP'},
   {name:'Japan visitor keeps explicit preference',url:'/',geo:'JP',saved:'ar',lang:'ar',country:'JP'},
   {name:'ordinary homepage unchanged',url:'/',geo:'KW',lang:'en',country:'KW'},
   {name:'other campaign unchanged',url:'/?utm_campaign=findzia_kr_search',geo:'KR',saved:'ko',lang:'ko',country:'KR'},
   {name:'trial uses same Japan entry',url:trial+campaign,geo:'US',lang:'ja',country:'JP'},
  ]){
   const context=await browser.newContext({viewport:{width:390,height:844},locale:'en-US'});
   const errors=[],calls=[];
   await context.addInitScript(({saved,blocked})=>{
    if(saved)localStorage.setItem('findzia-lang',saved);
    if(blocked)Object.defineProperty(window,'localStorage',{get(){throw new DOMException('Blocked','SecurityError');}});
   },test);
   await context.route('**/*',async route=>{
    const url=new URL(route.request().url()),p=url.pathname;
    if(url.origin===origin)return route.continue();
    if(url.origin==='https://api.findzia.com'){
     calls.push({path:p,body:route.request().postDataJSON()});
     let data={ok:true};
     if(p==='/api/geo')Object.assign(data,{country:test.geo,country_code:test.geo,source:'ip'});
     else if(p==='/api/account/config')data.providers={};
     else if(p==='/api/billing/config')data.plans=[];
     else if(p==='/api/billing/status'||p==='/api/billing/guest')Object.assign(data,{remaining:10,balances:{trial:10,pack:0},guest_token:'test-guest'});
     else if(p==='/api/billing/paddle/config'||p==='/api/billing/myfatoorah/config')data.checkout_available=false;
     else if(p==='/api/search/stream')return route.fulfill({contentType:'application/x-ndjson',body:'{"event":"done"}\n'});
     return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
    }
    return route.fulfill({contentType:url.hostname==='fonts.googleapis.com'?'text/css':'text/javascript',body:''});
   });
   const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
   async function check(lang,country){
    await page.waitForFunction(({lang,country})=>{
     const root=document.querySelector('.fz-home'),state=root?.fzRefineBridge?.context();
     return root?.dataset.lang===lang&&state?.lang===lang&&state?.country===country&&document.documentElement.lang===lang;
    },{lang,country},{timeout:10000});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'mobile layout fits');
   }
   await page.goto(origin+test.url,{waitUntil:'networkidle'});
   await check(test.lang,test.country);
   if(test.lang==='ja')assert.match(await page.locator('[data-dark-input]').getAttribute('placeholder'),/[\u3040-\u30ff\u4e00-\u9fff]/,'search placeholder is Japanese');
   if(test.search){
    const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/search/stream');
    const input=page.locator('[data-dark-input]');await input.fill('カメラ');await input.press('Enter');await response;
    const search=calls.find(call=>call.path==='/api/search/stream');
    assert.ok(search,'search was submitted');assert.equal(search.body.country,'JP');assert.equal(search.body.lang,'ja');
   }
   if(test.switch){
    await page.locator('[data-profile-language-select]').selectOption('en',{force:true});
    await check('en','JP');
    if(!test.blocked){await page.reload({waitUntil:'networkidle'});await check('en','JP');}
   }
   if(test.name==='direct Japan page'&&process.env.FINDZIA_TEST_SCREENSHOT)await page.screenshot({path:process.env.FINDZIA_TEST_SCREENSHOT,fullPage:true});
   assert.deepEqual(errors,[],test.name+': no JavaScript errors');
   console.log('PASS',test.name);
   await context.close();
  }
 }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
