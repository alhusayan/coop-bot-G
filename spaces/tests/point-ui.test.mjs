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

test('clean photo selection is free and opens the original layer without a Spaces search',async()=>{
 const {document,window}=parseHTML(readFileSync(new URL('../public/index.html',import.meta.url),'utf8'));
 globalThis.matchMedia=()=>({matches:true});globalThis.document=document;globalThis.Image=class{set src(value){this.onload?.();}};
 const job={id:'a'.repeat(24),revision:1,room:'Living room',options:{market:'US'},original:'/hero.webp',demo:false,designs:[{title:'Natural warmth',image:'/hero.webp',status:'ready',items:[{id:'1',name_en:'Armchair',box:[200,200,800,800],status:'idle',phase:'queued',crop:'/hero.webp',offers:[],alternatives:[]}]}]};
 let authorizations=0,searches=0;const opens=[],timers=new Set();
 window.HTMLElement.prototype.getBoundingClientRect=()=>({width:390,height:292,top:0,left:0,right:390,bottom:292});
 const dialog=document.querySelector('#sheet');dialog.open=false;dialog.showModal=()=>{dialog.open=true;};dialog.close=()=>{dialog.open=false;};window.scrollTo=()=>{};
 document.querySelector('.fz-home').fzBilling={authorizePiece:async()=>{authorizations++;},refresh(){}};
 const fetch=async(path,options={})=>{if(path==='/api/config')return Response.json({markets:{US:{currency:'USD',en:'United States',flag:'US'}},demo:job.id});if(/\/(focus|search)\//.test(path))searches++;return Response.json(structuredClone(job));};
 globalThis.fetch=fetch;const storage={getItem:()=>null,setItem:()=>{}};
 const context=vm.createContext({document,window,console,crypto:webcrypto,URL,Intl,Date,Number,String,Boolean,Math,JSON,Map,Set,Image:window.Image,localStorage:storage,matchMedia:()=>({matches:true}),location:{origin:'https://spaces.test'},ResizeObserver:class{observe(){}},setTimeout:(f,ms)=>{const id=setTimeout(f,ms);timers.add(id);return id;},clearTimeout,fetch,request,patchHTML,updateImage,pieceActivity,pieceViews,pickPhotoPiece,createLocalCatalog,createRoomContext,acceptsJob,createOriginalLayer:()=>({close(){},open:async value=>opens.push(value)}),mountFindzia:async()=>({sync(){},getLanguage:()=> 'en'})});
 try{
  vm.runInContext(readFileSync(new URL('../public/app.js',import.meta.url),'utf8').replace(/^import .*;\n/gm,''),context);
  await vm.runInContext('demo()',context);await vm.runInContext('choose(0)',context);
  assert.equal(document.querySelectorAll('.hotspot').length,0);assert.equal(document.querySelectorAll('.piece-outline').length,0);
  vm.runInContext("selectPiece('1')",context);assert.equal(searches,0);assert.equal(authorizations,0);assert.equal(opens.length,0);
  assert.equal(document.querySelectorAll('.piece-outline').length,1);
  await vm.runInContext("openItem('1')",context);
  assert.equal(opens.length,1);assert.equal(opens[0].market,'US');assert.equal(opens[0].crop,'/hero.webp');assert.equal(opens[0].view,null);
  assert.equal(searches,0);assert.equal(authorizations,0,'only the original page can authorize and charge');
  vm.runInContext("selected().items[0].original_view={items:[],lastSearch:{country:'US'}}",context);
  await vm.runInContext("openItem('1')",context);assert.ok(opens[1].view);assert.equal(opens[1].newSearch,false);
 }finally{for(const timer of timers)clearTimeout(timer);delete globalThis.document;delete globalThis.Image;}
});
