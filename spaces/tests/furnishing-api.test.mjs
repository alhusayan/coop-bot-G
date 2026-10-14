import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHmac} from 'node:crypto';
const directory=mkdtempSync(join(tmpdir(),'retired-furnish-api-')),owner='1'.repeat(32),id='2'.repeat(24),secret='furnish-test';
const job={id,owner,created:Date.now(),options:{market:'KW'},room:'Living room',designs:[{status:'ready',image:'design-0.jpg',matching_version:3,items:[{id:'1',name_en:'Sofa',offers:[],alternatives:[],furnishing_offers:{KW:[{title:'old furnishing candidate'}]}}],furnishing:{status:'render',products:[{id:'old-product'}]}}]};
process.env.NODE_ENV='production';process.env.SPACES_TRIAL_TOKEN=secret;process.env.SPACES_DATA_DIR=directory;
writeFileSync(join(directory,'state.json'),JSON.stringify({jobs:{[id]:job},quota:{}}));
const {createServer}=await import('../server.mjs');
test('removed furnishing endpoints and assets cannot start work or expose old furnishing results',async()=>{
 const s=createServer();await new Promise(r=>s.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+s.address().port,stamp=Date.now()+60000,value=owner+'.'+stamp;
 const cookie='spaces_session='+value+'.'+createHmac('sha256',secret).update(value).digest('hex');
 try{
  for(const method of ['GET','POST'])assert.equal((await fetch(base+'/api/jobs/'+id+'/furnish/0',{method,headers:{cookie,'Content-Type':'application/json'},...(method==='POST'?{body:JSON.stringify({width:6,length:8,market:'KW',max_searches:6,request_id:'5'.repeat(32)})}:{})})).status,404);
  for(const path of ['/furnishing.js','/furnishing-copy.js','/furnishing.css'])assert.equal((await fetch(base+path)).status,404);
  const response=await fetch(base+'/api/jobs/'+id,{headers:{cookie}});assert.equal(response.status,200);const saved=await response.json();
  assert.equal(saved.designs[0].furnishing,undefined);assert.equal(saved.designs[0].items[0].furnishing_offers,undefined);assert.equal(saved.designs[0].status,'ready');
  const state=JSON.parse(readFileSync(join(directory,'state.json'),'utf8'));assert.deepEqual(state.quota,{});assert.equal(state.jobs[id].designs[0].furnishing.status,'render','historical data is preserved but no longer resumed');
 }finally{await new Promise(r=>s.close(r));rmSync(directory,{recursive:true,force:true});}
});
