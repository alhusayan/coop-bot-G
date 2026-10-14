import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,writeFileSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHmac} from 'node:crypto';
import sharp from 'sharp';
test('retired image measurement route is disabled and retains ownership checks',async()=>{
 const dir=mkdtempSync(join(tmpdir(),'reference-api-')),owner='1'.repeat(32),id='a'.repeat(24),secret='reference-test';
 process.env.NODE_ENV='production';process.env.SPACES_TRIAL_TOKEN=secret;process.env.SPACES_DATA_DIR=dir;
 mkdirSync(join(dir,id));const photo=await sharp({create:{width:2000,height:1600,channels:3,background:'#dde0da'}}).jpeg().toBuffer();writeFileSync(join(dir,id,'original.jpg'),photo);
 writeFileSync(join(dir,'state.json'),JSON.stringify({jobs:{[id]:{id,owner,created:Date.now(),options:{market:'KW'},designs:[]}},quota:{}}));
 const {createServer}=await import('../server.mjs');const server=createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
 const cookie=who=>{const v=who+'.'+(Date.now()+60000);return 'spaces_session='+v+'.'+createHmac('sha256',secret).update(v).digest('hex');};
 const path='/api/jobs/'+id+'/measure',post=(payload,who=owner)=>fetch(base+path,{method:'POST',headers:{cookie:cookie(who),'Content-Type':'application/json'},body:JSON.stringify(payload)});
 const project=([x,y])=>[(.11*x+.04*y+.1)/(1+.09*y),(.015*x+.12*y+.12)/(1+.09*y)],input={action:'reference',image_id:'original',reference_points:[[0,0],[1,0],[1,1],[0,1]].map(project),reference_width:1,reference_length:1,points:[[0,0],[4,0],[4,5],[0,5]].map(project)};
 try{
  assert.equal((await post(input,'2'.repeat(32))).status,404);
  for(const action of ['reference','analyze','photo'])assert.equal((await post({action})).status,410);
  assert.equal((await fetch(base+path,{headers:{cookie:cookie(owner)}})).status,410);
  assert.equal(JSON.parse(readFileSync(join(dir,'state.json'),'utf8')).jobs[id].measurement,undefined);
 }finally{await new Promise(r=>server.close(r));rmSync(dir,{recursive:true,force:true});}
});
