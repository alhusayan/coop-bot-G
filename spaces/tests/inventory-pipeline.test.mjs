import test from 'node:test';
import assert from 'node:assert/strict';
import {prepareInventory} from '../inventory-pipeline.mjs';
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
function fixture(){
 const review=deferred(),published=deferred(),events=[],initial=[{id:'1',box:[100,100,700,700]}];let opened=false,current=true;
 const run=()=>prepareInventory({identify:async()=>initial,prepare:async(items,refined)=>{events.push(refined?'review-crops':'first-crops');return items.map(x=>({...x,crop:'/crop.jpg'}));},publish:(items,refined)=>{events.push({items,refined});published.resolve();},refine:async()=>{events.push('review');return review.promise;},canRefine:()=>!opened,isCurrent:()=>current});
 return {review,published,events,run,open:()=>opened=true,replace:()=>current=false};
}
test('usable crops publish while the second model call is still pending',async()=>{
 const f=fixture(),task=f.run();await f.published.promise;
 assert.deepEqual(f.events.map(x=>typeof x==='string'?x:x.refined),['first-crops',false,'review']);
 assert.equal(f.events[1].items[0].crop,'/crop.jpg');
 f.review.resolve([{id:'2'}]);await task;
 assert.equal(f.events.at(-1).refined,true);
});
test('opening the design during review freezes piece IDs and prevents replacement crops',async()=>{
 const f=fixture(),task=f.run();await f.published.promise;f.open();
 f.review.resolve([{id:'2'}]);await task;
 assert.equal(f.events.filter(x=>typeof x==='object').length,1);
 assert.equal(f.events[1].items[0].id,'1');assert.ok(!f.events.includes('review-crops'));
});
test('an already open design skips the second model request entirely',async()=>{
 const f=fixture();f.open();await f.run();assert.deepEqual(f.events.map(x=>typeof x==='string'?x:x.refined),['first-crops',false]);
});
test('a superseded image never receives a late review',async()=>{
 const f=fixture(),task=f.run();await f.published.promise;f.replace();f.review.resolve([{id:'2'}]);await task;
 assert.equal(f.events.filter(x=>typeof x==='object').length,1);
});
test('opening during review cropping also freezes the published inventory',async()=>{
 const crop=deferred(),entered=deferred(),publications=[];let open=false;
 const task=prepareInventory({identify:async()=>[{id:'1'}],prepare:async(items,review)=>{if(review){entered.resolve();await crop.promise;}return items;},publish:items=>publications.push(items),refine:async()=>[{id:'2'}],canRefine:()=>!open});
 await entered.promise;open=true;crop.resolve();await task;assert.equal(publications.length,1);assert.equal(publications[0][0].id,'1');
});
test('a failed optional review preserves a ready inventory and reports its failure',async()=>{
 const items=[{id:'1'}],published=[],errors=[];
 await prepareInventory({identify:async()=>items,prepare:async x=>x,publish:x=>published.push(x),refine:async()=>{throw Error('PROVIDER_BUSY');},onReviewError:e=>errors.push(e.message)});
 assert.deepEqual(published,[items]);assert.deepEqual(errors,['PROVIDER_BUSY']);
});

test('candidate detection starts during verification and does not delay displaying an approved render',async()=>{
 const {inspectCandidate}=await import('../inventory-pipeline.mjs');let verifyDone,identifyDone,started=false;
 const pending=inspectCandidate({verify:()=>new Promise(r=>verifyDone=r),identify:()=>{started=true;return new Promise(r=>identifyDone=r)}});
 await Promise.resolve();assert.equal(started,true);
 verifyDone({ok:true});const result=await pending;assert.equal(result.check.ok,true);
 identifyDone([{id:'1'}]);assert.deepEqual((await result.inventory).items,[{id:'1'}]);
});
test('discarded render captures detection failure without publishing inventory',async()=>{
 const {inspectCandidate}=await import('../inventory-pipeline.mjs');const error=Error('unavailable');
 const result=await inspectCandidate({verify:async()=>({ok:false}),identify:async()=>{throw error}});
 assert.equal(result.check.ok,false);assert.equal((await result.inventory).error,error);
});
