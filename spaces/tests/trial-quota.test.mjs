import test from 'node:test';
import assert from 'node:assert/strict';
import {previewLimits,previewUsage,reservePreview,settlePreview} from '../trial-quota.mjs';
const now=Date.parse('2026-10-12T16:00:00Z'),prefix='2026-10-12:',env={SPACES_DAILY_ROOMS_PER_BROWSER:'30',SPACES_DAILY_REDESIGNS_PER_BROWSER:'30',SPACES_DAILY_ROOMS:'100'};
test('existing browser at the former six-room limit can continue without resetting its history',()=>{
 const q={[prefix+'browser:rooms']:6,[prefix+'all:rooms']:24};
 reservePreview(q,'browser','rooms',{env,now});assert.equal(q[prefix+'browser:rooms'],7);assert.equal(previewUsage(q,'browser',{env,now}).roomsRemaining,23);
});
test('a global rejection never debits the browser and both boundaries are enforced',()=>{
 const q={[prefix+'browser:rooms']:2,[prefix+'all:rooms']:100},before=structuredClone(q);
 assert.throws(()=>reservePreview(q,'browser','rooms',{env,now}),e=>e.message==='TRIAL_LIMIT'&&e.status===429);assert.deepEqual(q,before);
 q[prefix+'all:rooms']=0;q[prefix+'browser:rooms']=30;assert.throws(()=>reservePreview(q,'browser','rooms',{env,now}),/TRIAL_LIMIT/);assert.equal(q[prefix+'all:rooms'],0);
});
test('failed attempts restore the browser allowance once while retaining the provider ceiling',()=>{
 const q={},receipt=reservePreview(q,'browser','redesign',{env,now});
 settlePreview(q,receipt);settlePreview(q,receipt);assert.equal(q[prefix+'browser:redesign'],0);assert.equal(q[prefix+'all:rooms'],1);
 const success=reservePreview(q,'browser','redesign',{env,now});settlePreview(q,success,{success:true});settlePreview(q,success);assert.equal(q[prefix+'browser:redesign'],1);
 const unstarted=reservePreview(q,'browser','rooms',{env,now});settlePreview(q,unstarted,{started:false});assert.equal(q[prefix+'browser:rooms'],0);assert.equal(q[prefix+'all:rooms'],2);
});
test('invalid overrides cannot accidentally remove limits; expired receipts never recreate old counters',()=>{
 assert.deepEqual(previewLimits({SPACES_DAILY_ROOMS:'Infinity',SPACES_DAILY_ROOMS_PER_BROWSER:'0'}),{rooms:30,redesign:30,total:100});
 const q={},receipt=reservePreview(q,'browser','rooms',{env,now});for(const k of Object.keys(q))delete q[k];settlePreview(q,receipt);assert.deepEqual(q,{});
});
