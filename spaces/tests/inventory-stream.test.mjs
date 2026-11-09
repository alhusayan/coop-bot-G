import test from 'node:test';
import assert from 'node:assert/strict';
import {completedInventory,readInventoryStream} from '../inventory-stream.mjs';
import {inspectCandidate} from '../inventory-pipeline.mjs';
import {gemini} from '../engine.mjs';
test('complete objects survive arbitrary chunks, escaped quotes, Arabic and nested boxes',async()=>{
 const items=[{name_en:'Chair "A"',name_ar:'كرسي',box:[1,2,3,4],selection_boxes:[[1,2,3,4]]},{name_en:'Wall } [',box:[0,0,1000,1000]}];
 const text=JSON.stringify({items});assert.deepEqual(completedInventory(text),items);
 assert.equal(completedInventory(text.slice(0,text.indexOf(',{"name_en"'))).length,1);
 const stream=Array.from(text).map(part=>'data: '+JSON.stringify({candidates:[{content:{parts:[{text:part}]}}]})+'\r\n\r\n').join('');
 const bytes=new TextEncoder().encode(stream),seen=[];
 async function* chunks(){for(let i=0;i<bytes.length;i+=7)yield bytes.slice(i,i+7);}
 const result=await readInventoryStream(chunks(),x=>seen.push(x));
 assert.deepEqual(seen.map(x=>x.length),[1,2]);assert.deepEqual(seen.at(-1),items);
 assert.equal(result.candidates[0].content.parts[0].text,text);
});
test('inventory buffered during verification is delivered only when subscribed after approval',async()=>{
 let progress,finish,approve;const pending=inspectCandidate({verify:()=>new Promise(r=>approve=r),identify:callback=>{progress=callback;return new Promise(r=>finish=r)}});
 await Promise.resolve();progress([{id:'1'}]);approve({ok:true});const result=await pending,seen=[];
 result.inventory.subscribe(items=>seen.push(items));assert.equal(seen[0][0].id,'1');
 progress([{id:'1'},{id:'2'}]);assert.equal(seen.at(-1).length,2);finish(seen.at(-1));await result.inventory;
});
test('Gemini streams complete targets before the full model response finishes',async t=>{
 let controller;const stream=new ReadableStream({start:c=>controller=c}),seen=[];
 const emit=text=>controller.enqueue(new TextEncoder().encode('data: '+JSON.stringify({candidates:[{content:{parts:[{text}]}}]})+'\n\n'));
 t.mock.method(globalThis,'fetch',async url=>{assert.match(url,/streamGenerateContent\?alt=sse$/);return new Response(stream,{headers:{'Content-Type':'text/event-stream'}})});
 let first;const appeared=new Promise(r=>first=r);
 const task=gemini([],{env:{GEMINI_API_KEY:'test',SPACES_TEXT_MODEL:'gemini-3.8-flash'},json:true,onItems:items=>{seen.push(items);first()}});
 emit('{"items":[{"name_en":"Chair","box":[0,0,100,100]}');await appeared;
 assert.equal(seen.length,1);emit(']}');controller.close();assert.equal((await task).items[0].name_en,'Chair');
});
