import test from 'node:test';
import assert from 'node:assert/strict';
import {request} from '../public/request.js';

test('the default browser fetch retains its required global receiver',async t=>{
 t.mock.method(globalThis,'fetch',function(){assert.equal(this,globalThis);return Promise.resolve(new Response(null,{status:200}));});
 assert.equal((await request('/api/config')).status,200);
});

test('lost session renews through the current invitation, preserving a pending photo request',async()=>{
 const calls=[],statuses=[401,200,202];
 const options={method:'POST',headers:{'Idempotency-Key':'same-design'},body:'photo-and-preferences'};
 const response=await request('/api/jobs',options,{pathname:'/trial/test-invite',fetch:async(path,opts)=>{calls.push({path,...opts});return new Response(null,{status:statuses.shift()});}});
 assert.equal(response.status,202);assert.deepEqual(calls.map(c=>[c.path,c.method]),[['/api/jobs','POST'],['/trial/test-invite','HEAD'],['/api/jobs','POST']]);
 assert.equal(calls[0].body,calls[2].body);assert.deepEqual(calls[0].headers,calls[2].headers);
});

test('an invitation never causes unbounded retry or bypasses a missing invite',async()=>{
 for(const pathname of ['/','/trial/test-invite']){
  let count=0;const r=await request('/api/config',{}, {pathname,fetch:async()=>{count++;return new Response(null,{status:401});}});
  assert.equal(r.status,401);assert.equal(count,pathname==='/'?1:2);
 }
});

test('temporary connection failures do not latch authentication or replay paid operations',async()=>{
 let count=0;const runtime={pathname:'/trial/test-invite',fetch:async()=>{count++;if(count===1)throw new TypeError('Network interrupted');return new Response(null,{status:200});}};
 await assert.rejects(request('/api/jobs',{method:'POST'},runtime),/Network interrupted/);assert.equal(count,1);
 assert.equal((await request('/api/config',{},runtime)).status,200);
 let failures=0;const response=await request('/api/jobs',{method:'POST'},{pathname:runtime.pathname,fetch:async()=>{failures++;return new Response(null,{status:503});}});
 assert.equal(response.status,503);assert.equal(failures,1);
});

test('caller cancellation stops in-flight requests and cannot renew or replay an aborted operation',async()=>{
 const controller=new AbortController();let seen;
 const pending=request('/api/jobs',{method:'POST',signal:controller.signal},{pathname:'/trial/test-invite',fetch:async(path,opts)=>{
  seen=opts.signal;return new Promise((resolve,reject)=>opts.signal.addEventListener('abort',()=>reject(opts.signal.reason),{once:true}));
 }});
 controller.abort();await assert.rejects(pending,{name:'AbortError'});assert.equal(seen.aborted,true);
 let calls=0;const cancelled=new AbortController();
 await assert.rejects(request('/api/jobs',{method:'POST',signal:cancelled.signal},{pathname:'/trial/test-invite',fetch:async()=>{
  calls++;cancelled.abort();return new Response(null,{status:401});
 }}),{name:'AbortError'});
 assert.equal(calls,1,'an aborted authentication response must not renew or repeat the request');
});

