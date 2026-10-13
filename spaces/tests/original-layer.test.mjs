import test from 'node:test';
import assert from 'node:assert/strict';
import {parseHTML} from 'linkedom';
import {createOriginalLayer} from '../public/original-results.js';

test('one original photo launch; closing/reopening preserves its live page and stored views are free',async()=>{
 const {document,window}=parseHTML('<html><body><button id="open">Open</button></body></html>');
 const beforeDocument=globalThis.document,beforeFetch=globalThis.fetch;globalThis.document=document;
 window.HTMLElement.prototype.showModal=function(){this.open=true;};window.HTMLElement.prototype.close=function(){this.open=false;};
 const calls=[],saved=[],statuses=[];let crops=0,release,busy=false,restores=0;
 globalThis.fetch=async()=>{crops++;return new Response(new Uint8Array([255,216,255,100]),{headers:{'Content-Type':'image/jpeg'}});};
 const layer=createOriginalLayer({request:async(path,options)=>{saved.push(JSON.parse(options.body));return {ok:true};},getLanguage:()=> 'en',onStatus:(key,value)=>statuses.push(value)});
 function original(frame){
  const child=parseHTML('<html><body><section class="fz-home"><select data-profile-market-select></select><select data-profile-language-select></select></section></body></html>');
  const root=child.document.querySelector('.fz-home');for(const select of child.document.querySelectorAll('select'))Object.defineProperty(select,'value',{writable:true,value:''});
  let market='KW';root.querySelector('select').addEventListener('change',e=>market=e.target.value);
  root.fzBilling={};root.fzAccount={};root.fzRefineBridge={
   context:()=>({country:market,kind:'image',busy}),
   searchPhoto:async file=>{calls.push(file);busy=true;await new Promise(resolve=>release=resolve);busy=false;return true;},
   snapshot:()=>({view:{items:[{url:'https://merchant.test/p',price:'95 KWD',result_group:'local'}],lastSearch:{country:market,kind:'image',image_base64:'private bytes'}}}),
   restore:()=>{restores++;},revealSearchResults(){}
  };
  Object.defineProperty(frame,'contentDocument',{value:child.document});Object.defineProperty(frame,'contentWindow',{value:{Event:child.window.Event,File,FileReader:class{readAsDataURL(){this.result='data:image/jpeg;base64,Y3JvcA==';this.onload();}}}});
  frame.dispatchEvent(new window.Event('load'));return root;
 }
 try{
  const input={key:'room:0:1',name:'Sofa',crop:'/media/room/crop.jpg',market:'KW',room:'a'.repeat(24),design:0,item:'1'};
  await layer.open(input);const frame=document.querySelector('iframe');const root=original(frame);
  await new Promise(resolve=>setTimeout(resolve,5));assert.equal(calls.length,1);assert.equal(crops,1);assert.equal(calls[0].type,'image/jpeg');assert.ok(statuses.includes(true));
  layer.close();await layer.open(input);assert.equal(document.querySelector('iframe'),frame);assert.equal(calls.length,1);
  release();await new Promise(resolve=>setTimeout(resolve,5));assert.ok(saved.length);assert.equal(saved.at(-1).view.lastSearch.image_base64,undefined);
  layer.close();await layer.open(input);assert.equal(calls.length,1);
  await layer.open({...input,key:'room:0:2',item:'2',view:saved.at(-1).view});original([...document.querySelectorAll('iframe')][1]);
  await new Promise(resolve=>setTimeout(resolve,5));assert.equal(restores,1);assert.equal(calls.length,1,'restoring never calls searchPhoto');assert.equal(crops,2,'restoring reads only the saved photo, not a new search');
 }finally{layer.destroy();globalThis.document=beforeDocument;globalThis.fetch=beforeFetch;}
});
