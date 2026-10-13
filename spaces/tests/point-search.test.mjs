import test from 'node:test';
import assert from 'node:assert/strict';
import {createHmac} from 'node:crypto';
import {mkdtempSync,mkdirSync,writeFileSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

const root=mkdtempSync(join(tmpdir(),'spaces-point-')),id='a'.repeat(24),owner='b'.repeat(32),stamp=Date.now()+3600000;
process.env.NODE_ENV='test';process.env.SPACES_TRIAL_TOKEN='test-invite';process.env.SPACES_DATA_DIR=root;process.env.FINDZIA_SPACES_ENGINE_KEY='s'.repeat(64);
const cookie='spaces_session='+owner+'.'+stamp+'.'+createHmac('sha256','test-invite').update(owner+'.'+stamp).digest('hex');
const authorization='Bearer test-customer-token-no-real-credit';
const row={url:'https://store.example/products/chair',image:'https://images.example/chair.jpg',title:'Green chair',store:'Local store',price:'134 USD',price_amount:134,currency:'USD',price_contract:'findzia-money-v1',price_display_ready:true,price_display_currency:'USD',market_scope:'local',match_type:'similar',classification_final:true,identity_review_status:'completed',visual_axes:{category:'same',subtype:'same',color:'same'},audited_media_path:'/api/media/verified/test-chair'};
const pieces=['1','2'].map(id=>({id,name_en:'Chair '+id,mode:'ready',box:[100,100,700,700],crop:'crop-0-'+id+'.jpg',status:'idle',phase:'queued',offers:[],alternatives:[]}));
mkdirSync(join(root,id));for(const item of pieces)writeFileSync(join(root,id,item.crop),'test pixels '+item.id);
writeFileSync(join(root,'state.json'),JSON.stringify({quota:{},jobs:{[id]:{id,owner,created:Date.now(),room:'Living room',options:{market:'US',language:'en'},designs:[{image:'design-0.jpg',status:'ready',items:pieces,matching_version:3,search_revision:13,grouping_version:1,shop_requested:true}]}}}));
const {createServer}=await import('../server.mjs');

test('room navigation is free; a point starts only its original search and replay cannot charge twice',async()=>{
 const server=createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port,nativeFetch=globalThis.fetch,calls=[];let stream;
 globalThis.fetch=async(url,options)=>{
  assert.equal(url,'https://api.findzia.com/internal/spaces/image/stream');calls.push(options);
  assert.equal(options.headers.Authorization,authorization);assert.equal(options.headers.Origin,base);
  assert.match(options.headers['X-Findzia-Request-Id'],/^[a-f0-9]{32}$/);
  const payload=JSON.parse(options.body);assert.equal(payload.country,'US');assert.equal(payload.image_base64,Buffer.from('test pixels 1').toString('base64'));
  return new Response(new ReadableStream({start(controller){stream=controller;}}),{headers:{'Content-Type':'application/x-ndjson'}});
 };
 const read=()=>nativeFetch(base+'/api/jobs/'+id,{headers:{cookie}}).then(r=>r.json());
 const post=(path,body={},headers={})=>nativeFetch(base+'/api/jobs/'+id+path,{method:'POST',headers:{cookie,'Content-Type':'application/json',...headers},body:JSON.stringify({design:0,...body})});
 const waitComplete=async()=>{for(let n=0;n<100;n++){const job=await read();if(job.designs[0].items[0].phase==='complete')return job;await new Promise(r=>setTimeout(r,5));}throw Error('not completed');};
 const finish=()=>{stream.enqueue(new TextEncoder().encode([JSON.stringify({event:'result',item:row}),JSON.stringify({event:'done'})].join('\n')+'\n'));stream.close();};
 try{
  await read();assert.equal((await post('/select',{language:'ar'})).status,202);await read();assert.equal(calls.length,0);
  assert.equal((await post('/focus/1',{request_id:'1'.repeat(32)},{Origin:base})).status,401);
  assert.equal((await post('/focus/1',{request_id:'1'.repeat(32)},{Origin:'http://localhost',Authorization:authorization})).status,403);
  assert.equal(calls.length,0);
  const searchHeaders={Authorization:authorization,Origin:base};
  assert.equal((await post('/focus/1',{request_id:'1'.repeat(32),country:'KW',language:'en'},searchHeaders)).status,202);
  await post('/focus/1',{request_id:'2'.repeat(32)},searchHeaders);await post('/search/1',{request_id:'3'.repeat(32)},searchHeaders);
  let job=await read();assert.equal(calls.length,1);assert.equal(job.designs[0].items[1].status,'idle');
  finish();job=await waitComplete();assert.equal(job.designs[0].items[0].alternatives.length,1);assert.equal(job.designs[0].items[0].alternatives[0].price,134);
  assert.equal((await post('/focus/1')).status,200);await post('/select');await read();assert.equal(calls.length,1);
  await post('/search/1',{request_id:'4'.repeat(32)},searchHeaders);assert.equal(calls.length,2);assert.notEqual(calls[0].headers['X-Findzia-Request-Id'],calls[1].headers['X-Findzia-Request-Id']);
  finish();await waitComplete();await post('/search/1',{request_id:'4'.repeat(32)},searchHeaders);assert.equal(calls.length,2);
  const other=await nativeFetch(base+'/api/jobs/'+id,{headers:{cookie:cookie.replace(owner,'c'.repeat(32))}});assert.equal(other.status,401);
  const persisted=readFileSync(join(root,'state.json'),'utf8');assert.ok(!persisted.includes(authorization));assert.ok(!persisted.includes('test-customer-token'));assert.ok(!JSON.stringify(await read()).includes(authorization));
 }finally{globalThis.fetch=nativeFetch;try{stream?.close();}catch{}await new Promise(r=>server.close(r));rmSync(root,{recursive:true,force:true});}
});
