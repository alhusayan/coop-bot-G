import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHmac} from 'node:crypto';
import {parseHTML} from 'linkedom';
import {readFurnishingMeasurements} from '../public/furnishing.js';
const directory=mkdtempSync(join(tmpdir(),'furnish-api-')),owner='1'.repeat(32),id='2'.repeat(24),demo='3'.repeat(24),secret='furnish-test',request='4'.repeat(32);
const job={id,owner,created:Date.now(),options:{market:'KW'},room:'Living room',designs:[{status:'ready',image:'design-0.jpg',matching_version:3,items:[{id:'1',name_en:'Sofa',offers:[],alternatives:[]},{id:'2',name_en:'Coffee table',offers:[],alternatives:[]}],furnishing:{status:'ready',request_id:request}}]};
process.env.NODE_ENV='production';process.env.SPACES_TRIAL_TOKEN=secret;process.env.SPACES_DATA_DIR=directory;
writeFileSync(join(directory,'state.json'),JSON.stringify({jobs:{[id]:job,[demo]:{...job,id:demo,owner:'demo'}},quota:{}}));
const {createServer}=await import('../server.mjs');
test('optional API enforces owner, explicit dimensions, disclosed searches and idempotency before costly work',async()=>{
 const s=createServer();await new Promise(r=>s.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+s.address().port,stamp=Date.now()+60000,value=owner+'.'+stamp;
 const cookie='spaces_session='+value+'.'+createHmac('sha256',secret).update(value).digest('hex');
 const post=(path,payload)=>fetch(base+path,{method:'POST',headers:{cookie,'Content-Type':'application/json'},body:JSON.stringify(payload)});
 const {document}=parseHTML('<form><input name="width" value="6"><input name="length" value="8"></form>');
 const path='/api/jobs/'+id+'/furnish/0',input={...readFurnishingMeasurements(document.querySelector('form')),market:'KW',max_searches:2,request_id:'5'.repeat(32)};
 try{
  assert.equal((await fetch(base+path)).status,401);
  const quote=await (await fetch(base+path+'?market=KW',{headers:{cookie}})).json();assert.equal(quote.searches,2);assert.equal(quote.items.length,2);
  assert.equal((await post(path,{...input,width:0})).status,400);
  assert.equal((await post(path,{...input,max_searches:0})).status,409);
  assert.equal((await post(path,input)).status,401);
  const again=await post(path,{...input,request_id:request});assert.equal(again.status,202);assert.equal((await again.json()).designs[0].furnishing.request_id,request);
  assert.equal((await post('/api/jobs/'+demo+'/furnish/0',input)).status,403);
 }finally{await new Promise(r=>s.close(r));rmSync(directory,{recursive:true,force:true});}
});
