import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {webcrypto} from 'node:crypto';
import {parseHTML} from 'linkedom';
import {pieceViews,pickPhotoPiece} from '../public/hotspots.js';
import {createLocalCatalog} from '../public/local-catalog.js';
import {request} from '../public/request.js';
import {patchHTML,updateImage,pieceActivity} from '../public/live-view.js';
import {createRoomContext,acceptsJob} from '../public/room-state.js';

test('clean photo selection is free, loading starts before admission, and cached results reopen free',async()=>{
 const {document,window}=parseHTML(readFileSync(new URL('../public/index.html',import.meta.url),'utf8'));
 globalThis.matchMedia=()=>({matches:true});globalThis.document=document;globalThis.Image=class{set src(value){this.onload?.();}};
 const job={id:'a'.repeat(24),revision:1,room:'Living room',options:{market:'US'},original:'/hero.webp',demo:false,designs:[{title:'Natural warmth',image:'/hero.webp',status:'ready',items:[{id:'1',name_en:'Armchair',box:[200,200,800,800],status:'idle',phase:'queued',crop:'/hero.webp',offers:[],alternatives:[]}]}]};
 let authorizations=0,searches=0,refreshes=0,releaseAuthorization;const authorizationReady=new Promise(resolve=>releaseAuthorization=resolve);const timers=new Set();
 window.HTMLElement.prototype.getBoundingClientRect=()=>({width:390,height:292,top:0,left:0,right:390,bottom:292});
 const dialog=document.querySelector('#sheet');dialog.open=false;dialog.showModal=()=>{dialog.open=true;};dialog.close=()=>{dialog.open=false;};
 window.scrollTo=()=>{};
 document.querySelector('.fz-home').fzBilling={authorizePiece:async()=>{authorizations++;await authorizationReady;return {Authorization:'Bearer test-only'};},refresh:()=>{refreshes++;},notice:()=>{}};
 const fetch=async(path,options={})=>{
  if(path==='/api/config')return Response.json({markets:{US:{currency:'USD',en:'United States',flag:'US'}},demo:job.id});
  if(path.includes('/focus/')){searches++;job.revision++;Object.assign(job.designs[0].items[0],{status:'searching',search_engine:'findzia-original',last_ui_request:'1'});}
  return Response.json(structuredClone(job));
 };
 globalThis.fetch=fetch;
 const storage={getItem:()=>null,setItem:()=>{}};
 const context=vm.createContext({document,window,console,crypto:webcrypto,URL,Intl,Date,Number,String,Boolean,Math,JSON,Map,Set,Image:window.Image,localStorage:storage,matchMedia:()=>({matches:true}),location:{origin:'https://spaces.test'},ResizeObserver:class{observe(){}},setTimeout:(f,ms)=>{const id=setTimeout(f,ms);timers.add(id);return id;},clearTimeout,fetch,request,patchHTML,updateImage,pieceActivity,pieceViews,pickPhotoPiece,createLocalCatalog,createRoomContext,acceptsJob,mountFindzia:async()=>({sync(){},getLanguage:()=> 'en'})});
 try{
  vm.runInContext(readFileSync(new URL('../public/app.js',import.meta.url),'utf8').replace(/^import .*;\n/gm,''),context);
  await vm.runInContext('demo()',context);await vm.runInContext('choose(0)',context);assert.equal(searches,0);
  assert.equal(document.querySelectorAll('.hotspot').length,0);assert.equal(document.querySelectorAll('.piece-outline').length,0);
  vm.runInContext("selectPiece('1')",context);assert.equal(searches,0);assert.equal(authorizations,0);
  assert.equal(document.querySelectorAll('.piece-outline').length,1);assert.match(document.querySelector('.piece-search-button').textContent,/1 credit/);
  const launch=vm.runInContext("openItem('1')",context);
  assert.match(document.querySelector('.photo-search-status').textContent,/Starting your search/);assert.ok(document.querySelector('.piece-search-track'));assert.equal(searches,0);
  releaseAuthorization();await launch;
  assert.equal(searches,1);assert.equal(authorizations,1);assert.equal(dialog.open,false);
  assert.ok(document.querySelector('.piece-outline.is-searching'));assert.equal(document.querySelector('.photo-pick-target').getAttribute('aria-busy'),'true');
  vm.runInContext("pointStarted.set(keyFor(selected().items[0]),Date.now()-6000);renderShop();",context);assert.match(document.querySelector('.photo-search-status').textContent,/6s/);
  vm.runInContext('pointFocus=null;renderShop()',context);assert.ok(document.querySelector('.photo-search-status'));
  await vm.runInContext("openItem('1')",context);assert.equal(searches,1);
  job.revision++;job.designs[0].items[0].alternatives=[{link:'https://store.test/chair',image:'https://store.test/chair.jpg',title:'Close armchair',source:'Local store',price:134,currency:'USD',market_scope:'local'}];
  await vm.runInContext("api('/api/jobs/'+state.job.id).then(job=>{applyJob(job,roomContext.capture());renderShop();})",context);
  assert.equal(dialog.open,true);assert.match(document.querySelector('#sheet-content').textContent,/134/);assert.equal(job.designs[0].items[0].status,'searching');
  job.revision++;Object.assign(job.designs[0].items[0],{phase:'complete',status:'done'});
  await vm.runInContext("api('/api/jobs/'+state.job.id).then(job=>{applyJob(job,roomContext.capture());renderShop();})",context);
  assert.equal(document.querySelectorAll('.photo-search-status').length,0);assert.equal(document.querySelector('.photo-pick-target').getAttribute('aria-busy'),'false');assert.equal(refreshes,1);
  vm.runInContext('closeSheet()',context);await vm.runInContext("openItem('1')",context);
  assert.equal(dialog.open,true);assert.equal(searches,1);assert.equal(authorizations,1);
 }finally{for(const timer of timers)clearTimeout(timer);delete globalThis.document;delete globalThis.Image;}
});
