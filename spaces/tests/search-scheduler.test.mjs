import test from 'node:test';
import assert from 'node:assert/strict';
import {createSearchScheduler} from '../search-scheduler.mjs';
const tick=()=>new Promise(resolve=>setImmediate(resolve));

test('opened piece starts ahead of a full background room queue, without duplicating it',async()=>{
 const queue=createSearchScheduler(),started=[],releases=new Map();
 const run=key=>queue.run(key,()=>{started.push(key);return new Promise(resolve=>releases.set(key,resolve));});
 const jobs=['sofa','desk','rug','lamp'].map(run);await tick();assert.deepEqual(started,['sofa','desk']);
 assert.equal(queue.promote('lamp'),true);await tick();assert.deepEqual(started,['sofa','desk','lamp']);
 const same=queue.run('lamp',()=>assert.fail('duplicate search'),{interactive:true});assert.equal(same,jobs[3]);
 releases.get('lamp')();await tick();assert.deepEqual(started,['sofa','desk','lamp']);
 releases.get('sofa')();await tick();assert.deepEqual(started,['sofa','desk','lamp','rug']);
 releases.get('desk')();releases.get('rug')();await Promise.all(jobs);
});

test('provider failure releases capacity and interactive requests remain bounded',async()=>{
 const queue=createSearchScheduler(),started=[],release=[];
 const jobs=Array.from({length:4},(_,i)=>queue.run(String(i),()=>{started.push(i);return new Promise((resolve,reject)=>release[i]=i===0?()=>reject(Error('failed')):resolve);},{interactive:true}).catch(e=>e.message));
 await tick();assert.equal(started.length,3);release[0]();await tick();assert.deepEqual(started,[0,1,2,3]);
 release[1]();release[2]();release[3]();assert.equal((await Promise.all(jobs))[0],'failed');
});
