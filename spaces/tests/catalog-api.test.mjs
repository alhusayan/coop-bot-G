import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import sharp from 'sharp';
const data=mkdtempSync(join(tmpdir(),'spaces-catalog-'));
process.env.GEMINI_API_KEY='test-only';process.env.SERPER_API_KEY='test-only';process.env.SPACES_DATA_DIR=data;delete process.env.NODE_ENV;delete process.env.SPACES_TRIAL_TOKEN;
const {createServer}=await import('../server.mjs');
const bytes=await sharp({create:{width:600,height:500,channels:3,background:'#adbaab'}}).jpeg().toBuffer();
test('new rooms finish automatically; redesign is isolated, idempotent and retains a saved design on failure',async()=>{
 let calls=0,release,fail=false;
 const s=createServer({catalog:async(_,options)=>{calls++;assert.equal(options.notes,'Olive');if(calls>1)await new Promise(r=>release=r);if(fail)throw Error('STOCK_CHANGED');return {output:bytes,mimeType:'image/jpeg',context:{room_en:'Office'},title:'Your real office',items:[{id:'1',name_en:'Desk',mode:'ready'}],plan:{room:{width_cm:400,length_cm:500},picks:[{id:'1',quantity:1,views:[{position_cm:{x:0,y:0,rotation:0}}],offer:{title:'Real desk',link:'https://safathome.com/desk/p',image:'https://example.com/desk.jpg',availability:'listed_available',dimensions_cm:{width:120,depth:60,height:75}}}]},boxes:{'1':[[100,100,800,800]]}};}});
 await new Promise(r=>s.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+s.address().port;
 const post=(path,b)=>fetch(base+path,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(b)});
 try{
  const b={image:'data:image/jpeg;base64,'+bytes.toString('base64'),market:'KW',width:4,length:5,notes:'Olive'};
  const response=await post('/api/jobs',b);assert.equal(response.status,202);let j=await response.json();assert.equal(j.flow,'catalog-first-v1');assert.equal(j.designs.length,1);
  async function done(){for(let n=0;n<80;n++){j=await fetch(base+'/api/jobs/'+j.id).then(r=>r.json());if(j.designs[0].status!=='generating')return;await new Promise(r=>setTimeout(r,10));}throw Error('timeout');}
  await done();assert.equal(j.designs[0].status,'complete');assert.equal(j.designs[0].title,'Your real office');assert.equal(j.designs[0].items[0].offers.length,1);const saved=j.designs[0].image;
  assert.equal((await post('/api/jobs/'+j.id+'/finish',{design:0})).status,409);
  const path='/api/jobs/'+j.id+'/redesign';fail=true;
  assert.equal((await post(path,{design:0,request_id:'one'})).status,202);
  assert.equal((await post(path,{design:0,request_id:'one'})).status,200);
  assert.equal((await post(path,{design:0,request_id:'two'})).status,409);
  assert.equal(calls,2);release();await done();assert.equal(j.designs[0].image,saved);assert.equal(j.designs[0].error,'STOCK_CHANGED');assert.equal(j.designs[0].items[0].offers.length,1);
 }finally{await new Promise(r=>s.close(r));rmSync(data,{recursive:true,force:true});}
});
