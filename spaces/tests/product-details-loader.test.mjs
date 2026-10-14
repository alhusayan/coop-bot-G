import test from 'node:test';
import assert from 'node:assert/strict';
import {parseHTML} from 'linkedom';
import {createProductDetailsLoader} from '../public/product-facts.js';
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const url='https://store.test/products/table';
function visibleRoot(){
 const {document}=parseHTML('<section><div data-results-body><article class="fz-card-shell"><a class="fz-tile" href="'+url+'"></a></article></div></section>');
 document.querySelector('article').getBoundingClientRect=()=>({top:100,bottom:500,width:300});
 return document.querySelector('section');
}
for(const stage of ['start','poll'])test('details stop after 60 seconds including a slow '+stage+' request',async t=>{
 t.mock.timers.enable({apis:['setTimeout','Date']});let calls=0,updates=0,lastSignal;
 const loader=createProductDetailsLoader({room:'room',design:0,item:'table',getLanguage:()=> 'ar',onUpdate:()=>updates++,request:async(path,opts)=>{
  calls++;lastSignal=opts.signal;
  if(stage==='poll'&&calls===1)return {status:'pending',key:'key'};
  return new Promise((resolve,reject)=>opts.signal.addEventListener('abort',()=>reject(opts.signal.reason),{once:true}));
 }});
 try{
  loader.scan(visibleRoot());await settle();
  t.mock.timers.tick(1200);await settle();
  t.mock.timers.tick(58799);assert.equal(loader.peek(url).status,'pending');
  t.mock.timers.tick(1);await settle();
  assert.equal(lastSignal.aborted,true);assert.equal(loader.peek(url).status,'unavailable');assert.equal(updates,1);
  loader.scan(visibleRoot());t.mock.timers.tick(120000);await settle();
  assert.equal(calls,stage==='start'?1:2,'no automatic repeat after timeout');
 }finally{loader.destroy();t.mock.timers.reset();}
});
test('available details appear immediately and destroying a pending loader aborts it',async t=>{
 t.mock.timers.enable({apis:['setTimeout','Date']});let calls=0,updates=0;
 const facts=[{kind:'material',value:'Solid wood'}];
 const loader=createProductDetailsLoader({room:'room',design:0,item:'table',getLanguage:()=> 'en',onUpdate:()=>updates++,request:async()=>{calls++;return {status:'ready',facts};}});
 try{
  loader.scan(visibleRoot());await settle();assert.equal(loader.peek(url).status,'ready');assert.equal(updates,1);
  t.mock.timers.tick(60000);await settle();assert.deepEqual(loader.peek(url).facts,facts);assert.equal(calls,1);
 }finally{loader.destroy();t.mock.timers.reset();}
});
test('closing the loader cancels polling waits without a later request or UI update',async t=>{
 t.mock.timers.enable({apis:['setTimeout','Date']});let calls=0,updates=0;
 const loader=createProductDetailsLoader({room:'room',design:0,item:'table',getLanguage:()=> 'ar',onUpdate:()=>updates++,request:async()=>{calls++;return {status:'pending',key:'key'};}});
 try{
  loader.scan(visibleRoot());await settle();loader.destroy();await settle();
  t.mock.timers.tick(120000);await settle();assert.equal(calls,1);assert.equal(updates,0);
 }finally{loader.destroy();t.mock.timers.reset();}
});
