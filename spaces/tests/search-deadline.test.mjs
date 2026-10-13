import test from 'node:test';
import assert from 'node:assert/strict';
import {parseHTML} from 'linkedom';
import {createOriginalLayer} from '../public/original-results.js';
const settle=()=>new Promise(resolve=>setImmediate(resolve));

for(const mode of ['stream','credit-check','page-boot'])test('16-second deadline cancels '+mode+' without a second paid search',async t=>{
 t.mock.timers.enable({apis:['setTimeout','Date']});
 const savedDocument=globalThis.document,savedFetch=globalThis.fetch;
 const {document,window}=parseHTML('<html><body></body></html>');globalThis.document=document;
 window.HTMLElement.prototype.showModal=function(){this.open=true;};window.HTMLElement.prototype.close=function(){this.open=false;};
 globalThis.fetch=async()=>new Response('crop',{headers:{'Content-Type':'image/jpeg'}});
 let releaseCredit,releaseStream,requests=0,restored=null,busy=false;
 const crop={key:'room:0:1:KW',name:'Sofa',crop:'/crop.jpg',market:'KW',room:'a'.repeat(24),design:0,item:'1'};
 const row={url:'https://store.test/p',price:'95 KWD',result_group:'local'};
 const layer=createOriginalLayer({request:async()=>({ok:true}),getLanguage:()=> 'en'});
 try{
  await layer.open(crop);const frame=document.querySelector('iframe');
  if(mode!=='page-boot'){
   const child=parseHTML('<html><body><section class="fz-home"><select data-profile-market-select></select><select data-profile-language-select></select><div data-results-body></div></section></body></html>');
   const root=child.document.querySelector('.fz-home');for(const select of root.querySelectorAll('select'))Object.defineProperty(select,'value',{value:'KW',writable:true});
   const win={Event:child.window.Event,File,FindziaBeforeSearch:async()=>mode==='credit-check'?new Promise(resolve=>releaseCredit=resolve):true};
   root.fzAccount={open(){}};root.fzBilling={};
   const photos=new Map([['photo',{winner:'verified.jpg'}]]);
   root.fzRefineBridge={context:()=>({country:'KW',busy,media_pending:true}),snapshot:()=>({view:{items:requests?[row]:[],lastSearch:{country:'KW',kind:'image'}},photos}),
    restore(snapshot){restored=snapshot;busy=false;releaseStream?.(false);},revealSearchResults(){},
    async searchPhoto(){if(!await win.FindziaBeforeSearch(root,{}))return false;requests++;busy=true;root.querySelector('[data-results-body]').innerHTML='<article class="fz-card-shell"><button data-save-product="https://store.test/p"></button></article>';return new Promise(resolve=>releaseStream=resolve);}
   };
   Object.defineProperty(frame,'contentDocument',{value:child.document});Object.defineProperty(frame,'contentWindow',{value:win});
   frame.dispatchEvent(new window.Event('load'));await settle();await settle();
   t.mock.timers.tick(15999);assert.equal(layer.busy(crop.key),true);
   t.mock.timers.tick(1);await settle();assert.equal(layer.busy(crop.key),false);
   assert.equal(restored.photos,photos,'the native verified image map is preserved');
   if(mode==='stream'){assert.equal(requests,1);assert.equal(restored.view.items[0],row);assert.match(document.querySelector('.original-results-status').textContent,/received so far/);}
   else{releaseCredit(true);await settle();assert.equal(requests,0,'a credit response after the deadline cannot start a search');}
  }else{t.mock.timers.tick(16000);assert.equal(layer.busy(crop.key),false);assert.equal(requests,0);}
  assert.equal(document.querySelector('.original-results-status').getAttribute('aria-busy'),'false');
  t.mock.timers.tick(30000);await settle();assert.equal(requests,mode==='stream'?1:0,'no automatic retry');
 }finally{layer.destroy();globalThis.document=savedDocument;globalThis.fetch=savedFetch;t.mock.timers.reset();}
});
