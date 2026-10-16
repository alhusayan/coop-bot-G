import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {PassThrough} from 'node:stream';
import {EventEmitter} from 'node:events';
import vm from 'node:vm';
import {createServer} from '../server.mjs';
import {isSpacePath,transformSpace,proxySpace} from '../spaces-proxy.mjs';
const read=path=>readFileSync(new URL(path,import.meta.url),'utf8');
let server,origin;
before(async()=>{server=createServer({FINDZIA_PAYMENT_PROVIDER:'paddle'});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));origin='http://127.0.0.1:'+server.address().port});
after(()=>new Promise(resolve=>server.close(resolve)));
const get=path=>fetch(origin+path,{redirect:'manual'});
test('one selection section, four large image cards, all local assets available',async()=>{
 const response=await get('/'),html=await response.text();assert.equal(response.status,200);
 assert.equal([...html.matchAll(/class="project-card /g)].length,4);assert.equal([...html.matchAll(/class="project-grid"/g)].length,1);assert.doesNotMatch(html,/class="hero"|intent-picker|faq-section|__ASSET_/);
 for(const path of ['/search','/trial/one-55321448a0352f1ff18b','/space','/trial/services'])assert.ok(html.includes('href="'+path+'"'));
 assert.match(html,/<dialog id="project-layer"/);
 for(const asset of new Set([...html.matchAll(/(?:src|href)="(\/assets\/[^" ]+)"/g)].map(m=>m[1]))){const r=await get(asset);assert.equal(r.status,200,asset);assert.match(r.headers.get('cache-control'),/immutable/)}
 const css=read('../source/findzia-hub.css');assert.match(css,/height:var\(--hub-height\)/);assert.match(css,/grid-template-rows:repeat\(2,minmax\(0,1fr\)\)/);assert.match(css,/env\(safe-area-inset-bottom\)/);assert.match(css,/prefers-reduced-motion/);
});
test('only project documents allow same-origin embedding; home and payment files retain protections',async()=>{
 const home=await get('/');assert.match(home.headers.get('content-security-policy'),/frame-src 'self'/);assert.equal(home.headers.get('x-frame-options'),'DENY');
 for(const path of ['/search','/trial/original','/trial/one-55321448a0352f1ff18b','/trial/services']){const r=await get(path);assert.equal(r.status,200);assert.equal(r.headers.get('x-frame-options'),'SAMEORIGIN');assert.match(r.headers.get('content-security-policy'),/frame-ancestors 'self'/);const html=await r.text();assert.match(html,/findzia-hub-bridge\./);assert.match(html,/findzia-account\./);assert.match(html,/findzia-billing\./)}
 assert.equal((await get('/policies/privacy-policy')).headers.get('x-frame-options'),'DENY');
 const response=await get('/.well-known/apple-developer-merchantid-domain-association');assert.equal(response.headers.get('cache-control'),'no-store');assert.equal(createHash('sha256').update(Buffer.from(await response.arrayBuffer())).digest('hex'),'2de7b483319c713bf649352f7f158f1fedbda92f546bebfe576ae0a2d2c526c6');
 const payment=await get('/?fz_mf_intent=sample&paymentId=sample');assert.equal(payment.status,200);assert.match(await payment.text(),/findzia-billing\./);
});
// A DOM fixture exercises event handlers and navigation without a browser or real credentials.
function hubFixture(href='https://findzia.com/',saved={}){
 class Element{constructor(dataset={}){this.dataset=dataset;this.attributes={};this.listeners={};this.children=[];this.style={setProperty:(key,value)=>this.style[key]=value};this.hidden=false;this.value='';this.textContent='';this.open=false;this.options=[];}addEventListener(name,fn){(this.listeners[name]??=[]).push(fn)}fire(name,event={}){for(const fn of this.listeners[name]||[])fn({target:this,button:0,preventDefault(){},...event})}setAttribute(key,value){this.attributes[key]=value}append(el){this.children.push(el);if(el.tagName==='option')this.options.push(el)}prepend(el){this.children.unshift(el)}remove(){this.removed=true}focus(){this.focused=true}showModal(){this.open=true}close(){this.open=false}querySelector(selector){return node(selector)}}
 const nodes=new Map(),node=key=>{if(!nodes.has(key))nodes.set(key,new Element());return nodes.get(key)};
 const groups={};for(const key of ['language','theme-toggle','account'])groups['[data-'+key+']']=[new Element(),new Element()];groups['[data-project]']=['shop','one','space','services'].map(project=>new Element({project}));groups['[data-t]']=['choose','shop','one','space','services','loading','retry'].map(t=>new Element({t}));groups['[data-language-name]']=[new Element(),new Element()];groups['.account-dot']=[new Element(),new Element()];
 const html=new Element();html.lang='ar';html.dataset.theme='light';const location=new URL(href),messages=[],frames=[],listeners={},stored=new Map(Object.entries(saved)),sessions=new Map(),history=[];
 const document={documentElement:html,activeElement:groups['[data-project]'][0],querySelector:node,querySelectorAll:key=>groups[key]||[],createElement:tag=>{const el=new Element();el.tagName=tag;if(tag==='iframe'){el.contentWindow={postMessage:(data,origin)=>messages.push({data,origin})};frames.push(el)}return el}};
 const window={innerHeight:620,visualViewport:{height:560,scale:1,addEventListener:(name,fn)=>listeners['viewport-'+name]=fn},FindziaAppearance:{apply:()=>({theme:stored.get('findzia-appearance-v1')||'light'})},addEventListener:(name,fn)=>listeners[name]=fn};
 const context={window,document,location,URL,localStorage:{getItem:key=>stored.get(key),setItem:(key,value)=>stored.set(key,value)},sessionStorage:{getItem:key=>sessions.get(key)},history:{state:null,pushState:(state,_,url)=>{history.push(url);location.href=new URL(url,location).href},replaceState:(state,_,url)=>{location.href=new URL(url,location).href}},setTimeout:()=>1,clearTimeout(){}};
 vm.runInNewContext(read('../source/findzia-hub.js'),context);
 return{nodes,node,groups,html,window,location,messages,frames,listeners,stored,history};
}
test('open, close, reopen and browser back preserve a single layer; forged messages ignored',()=>{
 const f=hubFixture();assert.equal(f.html.style['--hub-height'],'560px');f.window.visualViewport.height=488;f.listeners['viewport-resize']();assert.equal(f.html.style['--hub-height'],'488px');
 for(const [index,card]of f.groups['[data-project]'].entries()){card.fire('click');const frame=f.frames.at(-1);assert.equal(f.node('#project-layer').open,true);assert.equal(new URL(frame.src).origin,'https://findzia.com');assert.equal(new URL(frame.src).searchParams.get('hubProject'),card.dataset.project);
 f.listeners.message({origin:'https://evil.example',source:frame.contentWindow,data:{findziaHub:true,type:'close'}});assert.equal(f.node('#project-layer').open,true);
 f.listeners.message({origin:'https://findzia.com',source:frame.contentWindow,data:{findziaHub:true,type:'ready'}});assert.equal(f.node('#layer-status').hidden,true);
 f.groups['[data-account]'][1].fire('click');assert.equal(f.messages.at(-1).data.type,'account');
 f.node('#close-layer').fire('click');assert.equal(f.node('#project-layer').open,false);assert.equal(frame.removed,true);assert.equal(f.location.search,'');assert.equal(f.frames.length,index+1);}
 f.groups['[data-project]'][0].fire('click');f.location.search='';f.listeners.popstate();assert.equal(f.node('#project-layer').open,false);
});
test('canonical language changes both ways; viewport updates and OAuth return stay in overlay',()=>{
 const f=hubFixture('https://findzia.com/?project=space#findzia-login=test-code&flow=test-flow',{'findzia-lang':'ar','findzia-hub-language':'en'});
 assert.equal(f.html.lang,'ar');assert.equal(f.location.hash,'');assert.equal(f.location.search,'?project=space');assert.equal(new URL(f.frames[0].src).pathname,'/space');assert.equal(new URL(f.frames[0].src).hash,'#findzia-login=test-code&flow=test-flow');
 const select=f.groups['[data-language]'][0];select.value='en';select.fire('change');assert.equal(f.stored.get('findzia-lang'),'en');assert.equal(f.html.dir,'ltr');assert.equal(f.messages.at(-1).data.language,'en');
 f.listeners.message({origin:'https://findzia.com',source:f.frames[0].contentWindow,data:{findziaHub:true,type:'language',language:'ar'}});assert.equal(f.html.dir,'rtl');assert.ok(f.groups['[data-language]'].every(x=>x.value==='ar'));
 f.stored.set('findzia-lang','ja');f.listeners.storage({key:'findzia-lang'});assert.equal(f.html.lang,'ja');
 f.node('#close-layer').fire('click');f.groups['[data-project]'][0].fire('click');assert.equal(new URL(f.frames.at(-1).src).hash,'');
});
test('embedded OAuth uses existing PKCE and top-level provider navigation with same-project return',async()=>{
 const bridgeCode=read('../source/findzia-hub-bridge.js'),navigations=[],parent={FindziaHub:true,location:{origin:'https://findzia.com',href:'https://findzia.com/?project=space',assign:value=>navigations.push(value)},postMessage(){}};
 const location=new URL('https://findzia.com/space?hub=1&hubProject=space');const window={addEventListener(){}};
 vm.runInNewContext(bridgeCode,{window,parent,location,URL,URLSearchParams,document:{readyState:'loading',documentElement:{dataset:{}},addEventListener(){}},localStorage:{getItem:()=>null}});
 assert.equal(window.FindziaHubBridge.authReturnURL(),'https://findzia.com/?project=space');assert.throws(()=>window.FindziaHubBridge.navigateAuth('https://evil.example/'));
 let start;const saved=new Map();const account=read('../source/findzia-account.js');const signIn=account.slice(account.indexOf('async function signIn('),account.indexOf('async function resumeLogin('));
 const context={window,busy:false,refreshProviderUI(){},loadConfig:async()=>{},configError:false,config:{providers:{google:true}},toast(){},t:key=>key,root:{fzBilling:{beforeSignIn:async()=>{}}},random:()=> 'random-value',sessionStorage:{setItem:(key,value)=>saved.set(key,value)},flowKey:'findzia-account-v1-login',location,URL,hash:async()=> 'challenge',request:async(path,body)=>{start=body;return{authorize_url:'https://accounts.google.com/o/oauth2/auth'}}};
 await vm.runInNewContext(signIn+';signIn("google")',context);assert.equal(start.return_to,'https://findzia.com/?project=space');assert.equal(start.challenge,'challenge');assert.ok(JSON.parse(saved.get(context.flowKey)).verifier);assert.equal(navigations[0],'https://accounts.google.com/o/oauth2/auth');
});
test('Space allowlist covers app assets, uploads, selections, catalog and media, rejecting proxy destinations',()=>{
 const id='a'.repeat(24);
 for(const path of ['/space','/space/','/app.js','/findzia/account.js','/markets.js','/api/config','/api/jobs',`/api/jobs/${id}`,`/api/jobs/${id}/select/0`,`/api/jobs/${id}/catalog/2/12`,`/api/jobs/${id}/product-details/${'a'.repeat(64)}`,`/media/${id}/original.jpg`])assert.equal(isSpacePath(path),true,path);
 for(const path of ['https://evil.example/','//evil.example/','/api/admin','/../../secret','/media/../secret','/app.js/evil','/%2f%2fevil.example'])assert.equal(isSpacePath(path),false,path);
 const market="export function marketLanguage(market,read=()=>null){return read('spaces-language-choice-'+market+'-v1')||'en';}";const transformed=transformSpace('/markets.js',market,{});assert.equal(vm.runInNewContext(transformed.replace('export ','')+';marketLanguage("JP", key=>key==="findzia-lang"?"ar":null)'),'ar');
 const html=transformSpace('/space','<html><head></head></html>',{script:'/assets/bridge.js',style:'/assets/bridge.css'});assert.match(html,/src="\/assets\/bridge.js"/);
});
test('Space proxy preserves same-origin session cookies, streams POST bodies and rewrites framing',async()=>{
 async function run(path,method,body,replyBody,replyHeaders){let options,uploaded='';const req=new PassThrough();req.url=path;req.method=method;req.headers={cookie:'fz_spaces=existing',authorization:'Bearer test',origin:'https://findzia.com','content-type':'application/json','sec-fetch-site':'same-origin',host:'untrusted.example'};
 const res=new EventEmitter();res.parts=[];res.writeHead=(code,headers)=>{res.statusCode=code;res.headers=headers;res.headersSent=true};res.end=chunk=>{if(chunk)res.parts.push(Buffer.from(chunk));res.writableEnded=true;res.emit('finish')};res.write=chunk=>{res.parts.push(Buffer.from(chunk));return true};res.destroy=()=>{res.destroyed=true};
 const finished=new Promise(resolve=>res.on('finish',resolve));
 proxySpace(req,res,{script:'/assets/bridge.js',style:'/assets/bridge.css'},(config,callback)=>{options=config;const sink=new PassThrough();sink.on('data',chunk=>uploaded+=chunk);sink.on('end',()=>{const reply=new PassThrough();reply.statusCode=200;reply.headers=replyHeaders;callback(reply);reply.end(replyBody)});return sink});req.end(body);await finished;return{options,uploaded,res,body:Buffer.concat(res.parts).toString()}}
 const post=await run('/api/jobs','POST','{"image":"test"}','{"id":"test"}',{'content-type':'application/json'});assert.equal(post.uploaded,'{"image":"test"}');assert.equal(post.options.hostname,'findzia-spaces-production.up.railway.app');assert.equal(post.options.headers.cookie,'fz_spaces=existing');assert.equal(post.options.headers.host,undefined);
 const page=await run('/space?hub=1','GET','','<head></head>',{'content-type':'text/html','content-security-policy':"default-src 'self'; frame-ancestors 'none'",'set-cookie':['fz_spaces=new; Path=/; HttpOnly; Secure; SameSite=Lax'],'x-frame-options':'DENY'});assert.equal(page.options.path,'/?hub=1');assert.equal(page.res.headers['x-frame-options'],'SAMEORIGIN');assert.match(page.res.headers['content-security-policy'],/frame-ancestors 'self'/);assert.equal(page.res.headers['set-cookie'][0],'fz_spaces=new; Path=/; HttpOnly; Secure; SameSite=Lax');assert.match(page.body,/bridge.js/);
});
test('child bridge applies parent language to the real preference control and opens the current account',()=>{
 const stored=new Map([['findzia-lang','ar']]),events={},rootEvents={},posts=[];let accountOpens=0,internalLanguage='en';
 const select={value:'en',options:[{value:'ar'},{value:'en'}],dispatchEvent(){internalLanguage=this.value;root.dataset.lang=this.value;stored.set('findzia-lang',this.value)}};
 const root={dataset:{lang:'en'},fzAccount:{open:()=>accountOpens++},fzRefineBridge:{},querySelector:key=>key==='[data-profile-language-select]'?select:null,addEventListener:(name,fn)=>rootEvents[name]=fn};
 const parent={FindziaHub:true,location:{origin:'https://findzia.com',href:'https://findzia.com/?project=space'},postMessage:(message,origin)=>posts.push({message,origin})};
 const document={documentElement:{dataset:{}},readyState:'complete',querySelector:()=>root,addEventListener(){}};
 const window={addEventListener:(name,fn)=>events[name]=fn,FindziaLocale:{choose(){}},FindziaI18n:{set:(root,lang)=>root.dataset.lang=lang}};
 vm.runInNewContext(read('../source/findzia-hub-bridge.js'),{window,parent,document,location:new URL('https://findzia.com/space?hub=1&hubProject=space'),URL,URLSearchParams,Event,localStorage:{getItem:key=>stored.get(key)}});
 assert.equal(internalLanguage,'ar');assert.equal(document.documentElement.dir,'rtl');assert.equal(posts.at(-1).message.type,'ready');
 events.message({origin:'https://evil.example',source:parent,data:{findziaHub:true,type:'account'}});assert.equal(accountOpens,0);
 events.message({origin:'https://findzia.com',source:parent,data:{findziaHub:true,type:'account'}});assert.equal(accountOpens,1);
 stored.set('findzia-lang','en');events.storage({key:'findzia-lang'});assert.equal(internalLanguage,'en');assert.equal(document.documentElement.dir,'ltr');
 root.fzRefineBridge.accountSearch('chair','KW');assert.equal(posts.at(-1).message.project,'shop');assert.equal(posts.at(-1).message.q,'chair');assert.equal(JSON.stringify(posts).includes('access_token'),false);
});
