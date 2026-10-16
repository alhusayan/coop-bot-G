import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import vm from 'node:vm';
import {createServer} from '../server.mjs';
let server,origin;
before(async()=>{server=createServer({FINDZIA_PAYMENT_PROVIDER:'paddle'});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));origin='http://127.0.0.1:'+server.address().port});
after(()=>new Promise(resolve=>server.close(resolve)));
const get=path=>fetch(origin+path,{redirect:'manual'});
test('home contains four distinct destinations and every local asset is served',async()=>{
 const r=await get('/'),html=await r.text();assert.equal(r.status,200);assert.match(html,/id="projects"/);assert.equal([...html.matchAll(/class="project-card /g)].length,4);assert.doesNotMatch(html,/__ASSET_|__ANALYTICS__/);
 for(const href of ['/search','/trial/one-55321448a0352f1ff18b','https://findzia-spaces-production.up.railway.app/','/trial/services'])assert.ok(html.includes('href="'+href+'"'));
 const assets=new Set([...html.matchAll(/(?:src|href)="(\/assets\/[^" ]+)"/g)].map(m=>m[1]));assert.ok(assets.size>=8);
 for(const asset of assets){const response=await get(asset);assert.equal(response.status,200,asset);assert.match(response.headers.get('cache-control'),/immutable/);}
 for(const path of ['/search','/search/','/home','/trial/services','/trial/one-55321448a0352f1ff18b','/test','/test/discover'])assert.equal((await get(path)).status,200,path);
});
test('original search and alias retain product, account and billing assets',async()=>{
 for(const path of ['/search','/trial/original','/pages/findzia','/jp']){const html=await(await get(path)).text();assert.match(html,/class="fz-home"/);assert.match(html,/findzia-billing\./);assert.match(html,/findzia-account\./);assert.doesNotMatch(html,/class="project-grid"/);}
 const original=await(await get('/trial/original')).text(),search=await(await get('/search')).text();assert.equal(original,search);
});
test('existing payment returns reach billing without redirect and auth hashes preserve credentials',async()=>{
 const response=await get('/?fz_mf_intent=sample&paymentId=sample');assert.equal(response.status,200);assert.equal(response.headers.get('location'),null);assert.match(await response.text(),/findzia-billing\./);
 const html=readFileSync(new URL('../public/index.html',import.meta.url),'utf8');const boot=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)][0][1];
 for(const hash of ['#findzia-login=sample&flow=flow',' #findzia-auth-error=sample'.trim()]){let next='';vm.runInNewContext(boot,{localStorage:{getItem:()=>null},navigator:{language:'ar'},document:{documentElement:{dataset:{}}},matchMedia:()=>({matches:false}),location:{hash,search:'?utm_source=qa',replace:value=>{next=value}}});assert.equal(next,'/search?utm_source=qa'+hash);}
});
test('Paddle verification bytes remain exact and uncached',async()=>{
 const response=await get('/.well-known/apple-developer-merchantid-domain-association');assert.equal(response.status,200);assert.equal(response.headers.get('cache-control'),'no-store');const bytes=Buffer.from(await response.arrayBuffer());assert.equal(bytes.length,9094);assert.equal(createHash('sha256').update(bytes).digest('hex'),'2de7b483319c713bf649352f7f158f1fedbda92f546bebfe576ae0a2d2c526c6');
});
test('Arabic and English cover all visible keys, scene destinations and interaction states',()=>{
 const html=readFileSync(new URL('../source/findzia-hub.html',import.meta.url),'utf8');let code=readFileSync(new URL('../source/findzia-hub.js',import.meta.url),'utf8');
 // Exercise the actual UI module with a small DOM fixture, including switch handlers.
 class Element{constructor(dataset={}){this.dataset=dataset;this.attrs={};this.style={};this.listeners={};this.classList={toggle(){},add(){},remove(){}};this.textContent='';this.href=''}setAttribute(k,v){this.attrs[k]=v}addEventListener(k,fn){this.listeners[k]=fn}querySelector(){return new Element()} }
 const groups={};for(const attr of ['t','label','alt','scene','intent']){groups[`[data-${attr}]`]=[...html.matchAll(new RegExp(`data-${attr}="([^"]+)"`,'g'))].map(match=>new Element({[attr]:match[1]}));}groups['.reveal']=[];
 const nodes=new Map();const node=key=>{if(!nodes.has(key))nodes.set(key,new Element());return nodes.get(key)};
 const root=new Element();root.lang='ar';root.dataset.theme='light';root.scrollHeight=800;
 const stored=new Map();const window={innerHeight:800,scrollY:0,addEventListener(){}};
 const document={documentElement:root,querySelector:node,querySelectorAll:key=>groups[key]||[],addEventListener(){}};
 vm.runInNewContext(code,{document,window,localStorage:{getItem:key=>stored.get(key)||null,setItem:(key,value)=>stored.set(key,value)},matchMedia:()=>({matches:false,addEventListener(){}}),requestAnimationFrame:fn=>fn(),URL,location:{origin:'https://findzia.com'}});
 for(const item of groups['[data-t]'])assert.ok(item.textContent,'Arabic key: '+item.dataset.t);
 node('#language-toggle').listeners.click();assert.equal(root.lang,'en');assert.equal(root.dir,'ltr');assert.equal(stored.get('findzia-lang'),'en');for(const item of groups['[data-t]'])assert.ok(item.textContent,'English key: '+item.dataset.t);
 for(const button of groups['[data-intent]']){button.listeners.click();assert.equal(button.attrs['aria-pressed'],'true');assert.ok(node('#intent-link').href);assert.ok(node('#intent-description').textContent)}
 for(const button of groups['[data-scene]']){button.listeners.click();assert.equal(button.attrs['aria-pressed'],'true');assert.ok(node('#scene-link').href);assert.ok(node('#scene-caption').textContent)}
 node('#theme-toggle').listeners.click();assert.equal(root.dataset.theme,'dark');node('#motion-toggle').listeners.click();assert.equal(node('#motion-toggle').attrs['aria-pressed'],'true');
 node('#language-toggle').listeners.click();assert.equal(root.dir,'rtl');
});
test('account deep link opens the existing account when ready and preserves other params',()=>{
 const code=readFileSync(new URL('../source/findzia-hub-bridge.js',import.meta.url),'utf8');let listener,opened=0,next='';const root={querySelector:()=>null,addEventListener:(event,fn)=>{assert.equal(event,'fz:account-ready');listener=fn}};
 vm.runInNewContext(code,{URL,URLSearchParams,location:{href:'https://findzia.com/search?account=1&utm_source=qa',search:'?account=1&utm_source=qa'},document:{querySelector:()=>root},history:{state:null,replaceState:(_,__,value)=>{next=value}}});root.fzAccount={open:()=>opened++};listener();assert.equal(opened,1);assert.equal(next,'/search?utm_source=qa');
});
