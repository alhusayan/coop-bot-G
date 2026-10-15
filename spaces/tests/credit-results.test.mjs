import test from 'node:test';
import assert from 'node:assert/strict';
import {parseHTML} from 'linkedom';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {createOriginalLayer} from '../public/original-results.js';
const settle=()=>new Promise(resolve=>setImmediate(resolve));
test('both preflight and API billing denial publish the actual reason, even with one remaining credit',()=>{
 const source=readFileSync(new URL('../public/findzia/billing.js',import.meta.url),'utf8');
 const report=source.match(/    function reportSearchBlock\(code\)\{[^\n]+/)[0];
 const block=source.slice(source.indexOf('    function blockSearch(code){'),source.indexOf('    function button(text'));
 const handler=source.slice(source.indexOf('    function handleSearchError(value){'),source.indexOf('    async function ensureGuest'));
 const events=[];
 const runtime={root:{querySelectorAll:()=>[],dispatchEvent:e=>events.push(e),fzBilling:{status:()=>({remaining:1})}},CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail;}},message:code=>'message:'+code,notice(){},limitCodes:new Set(['credits_exhausted','credits_unavailable']),errorCode:x=>x,blockedSearch:null,bridge:{context:()=>({generation:1})}};
 runInNewContext(report+block+handler+";blockSearch('credits_exhausted');handleSearchError('credits_exhausted');",runtime);
 assert.equal(events.length,2);for(const event of events){assert.equal(event.type,'fz:search-blocked');assert.equal(event.detail.code,'credits_exhausted');}
});
for(const code of ['credits_exhausted','credits_unavailable'])test('results layer keeps '+code+' separate from an empty search, and retries only on request',async t=>{
 t.mock.timers.enable({apis:['setTimeout','setInterval','Date']});
 const oldDoc=globalThis.document,oldFetch=globalThis.fetch;
 const {document,window}=parseHTML('<html><body><section id="findzia-home-spaces"></section></body></html>');globalThis.document=document;
 window.HTMLElement.prototype.showModal=function(){this.open=true;};window.HTMLElement.prototype.close=function(){this.open=false;};
 globalThis.fetch=async()=>new Response('crop',{headers:{'Content-Type':'image/jpeg'}});
 const layer=createOriginalLayer({request:async()=>({ok:true}),getLanguage:()=> 'en'});
 let attempts=0,allow=false;
 try{
  await layer.open({key:'room:0:1:SA',name:'Lamp',crop:'/crop.jpg',market:'SA',room:'room',design:0,item:'1'});
  const frame=document.querySelector('iframe');
  const child=parseHTML('<html><body><section class="fz-home"><select data-profile-market-select></select><select data-profile-language-select></select><div data-results-body>Nothing matched that search.</div></section></body></html>');
  const root=child.document.querySelector('.fz-home');for(const select of root.querySelectorAll('select'))Object.defineProperty(select,'value',{value:'SA',writable:true});
  root.fzAccount={open(){}};root.fzBilling={};
  root.fzRefineBridge={context:()=>({country:'SA',busy:false}),snapshot:()=>({view:{items:[]}}),async searchPhoto(){
   attempts++;if(allow)return true;
   root.dispatchEvent(new child.window.CustomEvent('fz:search-blocked',{detail:{code,message:'Could not check your credits. Please try again.'}}));
   root.dispatchEvent(new child.window.CustomEvent('fz:usage',{detail:{code:'credits_unavailable'}}));return false;
  }};
  Object.defineProperty(frame,'contentDocument',{value:child.document});Object.defineProperty(frame,'contentWindow',{value:{Event:child.window.Event,File}});
  frame.dispatchEvent(new window.Event('load'));await settle();await settle();
  const panel=document.querySelector('.original-results-blocked');assert.equal(panel.hidden,false);assert.equal(frame.hidden,true);
  assert.equal(panel.querySelector('.primary').hidden,code!=='credits_exhausted');
  if(code==='credits_exhausted')assert.match(panel.textContent,/out of search credits/);else assert.match(panel.textContent,/Could not check/);
  t.mock.timers.tick(40000);await settle();assert.equal(attempts,1);assert.equal(panel.hidden,false,'deadline must not replace the balance error');
  allow=true;panel.querySelector('.text-button').click();await settle();await settle();
  assert.equal(attempts,2);assert.equal(panel.hidden,true);assert.equal(frame.hidden,false);
 }finally{layer.destroy();globalThis.document=oldDoc;globalThis.fetch=oldFetch;t.mock.timers.reset();}
});
