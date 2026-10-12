import test from 'node:test';
import assert from 'node:assert/strict';
import {searchWithRecovery} from '../matching.mjs';
const item={id:'3',offers:[],alternatives:[]};
test('an empty first search retries automatically and never exposes premature completion',async()=>{
 const updates=[];let calls=0;
 const result=await searchWithRecovery(item,'KW',{onProgress:u=>updates.push(u),run:async(_i,_m,{onProgress,attempt})=>{
   calls++;assert.equal(attempt,calls);
   const offers=attempt===2?[{link:'https://store.example/products/table',match:'visual'}]:[];
   onProgress({offers,alternatives:[],phase:'complete'});return offers;
 }});
 assert.equal(calls,2);assert.equal(result.length,1);
 assert.equal(updates.filter(x=>x.phase==='complete').length,1);
 assert.ok(updates.find(x=>x.phase==='retrying'));
 assert.equal(updates.at(-1).offers.length,1);
});
test('available replacements stop automatic retries and remain distinct from exact matches',async()=>{
 let calls=0,latest;
 const offers=await searchWithRecovery(item,'KW',{onProgress:u=>latest=u,run:async(_i,_m,{onProgress})=>{calls++;onProgress({offers:[],alternatives:[{link:'https://store.example/products/table',match:'replacement'}],phase:'complete'});return [];}});
 assert.equal(calls,1);assert.deepEqual(offers,[]);assert.equal(latest.alternatives.length,1);
});
test('empty searches stop after two passes; persistent provider failures remain errors',async()=>{
 let calls=0;
 await searchWithRecovery(item,'KW',{run:async()=>{calls++;return [];}});assert.equal(calls,2);
 calls=0;await assert.rejects(searchWithRecovery(item,'KW',{run:async()=>{calls++;throw Error('SEARCH_FAILED');}}),/SEARCH_FAILED/);assert.equal(calls,2);
});
test('searching again retains existing store options during the new search',async()=>{
 const original={link:'https://store.example/products/table',match:'replacement'},updates=[];
 await searchWithRecovery({...item,alternatives:[original]},'KW',{onProgress:u=>updates.push(u),run:async(_i,_m,{onProgress})=>{onProgress({offers:[],alternatives:[],phase:'lens'});return [];}});
 assert.ok(updates.every(u=>u.alternatives[0].link===original.link));
});
