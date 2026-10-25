import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import sharp from 'sharp';

test('the API serves selectable crops before review and a late review cannot change an opened design',async t=>{
 const directory=mkdtempSync(join(tmpdir(),'spaces-progress-'));
 process.env.NODE_ENV='production';process.env.SPACES_TRIAL_TOKEN='progress-test';process.env.SPACES_DATA_DIR=directory;
 process.env.GEMINI_API_KEY='local-test-only';process.env.SERPER_API_KEY='local-test-only';
 const jpeg=await sharp({create:{width:512,height:512,channels:3,background:'#c3b79e'}}).jpeg().toBuffer();
 let releaseReview,reviewCalls=0;const reviews=new Promise(r=>releaseReview=r),realFetch=globalThis.fetch;
 let releaseRoom,releaseGeneration,releaseCheck;
 const roomGate=new Promise(r=>releaseRoom=r),generationGate=new Promise(r=>releaseGeneration=r),checkGate=new Promise(r=>releaseCheck=r);
 t.mock.method(globalThis,'fetch',async(url,options)=>{
  if(!String(url).startsWith('https://generativelanguage.googleapis.com/'))return realFetch(url,options);
  const input=JSON.parse(options.body),prompt=input.contents[0].parts[0].text;let parts,result;
  if(input.generationConfig.responseModalities?.includes('IMAGE')){await generationGate;parts=[{inlineData:{mimeType:'image/jpeg',data:jpeg.toString('base64')}}];}
  else {
   if(prompt.startsWith('Identify the photographed SPACE')){await roomGate;result={is_space:true,is_room:true,type:'living_room',setting:'interior',room_en:'Living room'};}
   else if(prompt.startsWith('Compare the')){await checkGate;result={meets_brief:true,site_preserved:true,same_function:true,essential_functions_preserved:true};}
   else if(prompt.startsWith('Identify ALL distinct'))result={items:[{name_en:'Armchair',name_ar:'كرسي',category:'armchair',search_kind:'product',mode:'ready',box:[100,100,600,600]}]};
   else if(prompt.startsWith('Review object identities')){reviewCalls++;await reviews;result={corrections:[],groups:[],additions:[{name_en:'Table',category:'table',mode:'ready',box:[650,650,950,950]}]};}
   else throw Error('Unexpected model request: '+prompt.slice(0,40));
   parts=[{text:JSON.stringify(result)}];
  }
  return Response.json({candidates:[{content:{parts}}]});
 });
 const {createServer}=await import('../server.mjs');const server=createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
 async function until(fn){for(let i=0;i<100;i++){const result=await fn();if(result)return result;await new Promise(r=>setTimeout(r,10));}assert.fail('inventory did not settle');}
 try{
  const auth=await fetch(base+'/trial/progress-test'),cookie=auth.headers.get('set-cookie').split(';')[0],headers={cookie,'Content-Type':'application/json'};
  const created=await fetch(base+'/api/jobs',{method:'POST',headers,body:JSON.stringify({market:'KW',image:'data:image/jpeg;base64,'+jpeg.toString('base64')})});assert.equal(created.status,202);const {id}=await created.json();
  const read=async()=>await (await fetch(base+'/api/jobs/'+id,{headers})).json();
  assert.ok((await read()).designs.every(d=>d.generation_phase==='understanding'&&!d.image));
  releaseRoom();
  await until(async()=>{const j=await read();return j.designs.every(d=>d.generation_phase==='creating'&&!d.image);});
  releaseGeneration();
  await until(async()=>{const j=await read();return j.designs.every(d=>d.generation_phase==='checking'&&!d.image);});
  releaseCheck();
  const job=await until(async()=>{const j=await read();return j.designs.every(d=>d.inventory_complete)&&reviewCalls===3&&j;});
  assert.ok(job.designs.every(d=>d.generation_phase==='complete'));
  assert.ok(job.designs.every(d=>d.status==='ready'&&d.items.length===1&&!d.needs_rescan));
  const crop=await fetch(base+job.designs[0].items[0].crop,{headers});assert.equal(crop.status,200);assert.equal(crop.headers.get('content-type'),'image/jpeg');
  const selected=await fetch(base+'/api/jobs/'+id+'/select',{method:'POST',headers,body:JSON.stringify({design:0})});assert.equal(selected.status,202);
  releaseReview();
  const refined=await until(async()=>{const j=await read();return j.designs[1].grouping_version===2&&j.designs[2].grouping_version===2&&j;});
  assert.equal(refined.designs[0].items.length,1);assert.equal(refined.designs[0].items[0].id,job.designs[0].items[0].id);assert.equal(refined.designs[0].items[0].crop,job.designs[0].items[0].crop);
  assert.equal(refined.designs[1].items.length,2);
  const reviewedCrop=await fetch(base+refined.designs[1].items[1].crop,{headers});assert.equal(reviewedCrop.status,200);
  assert.equal(refined.designs[0].opened_image,undefined,'internal revision lock stays private');
 }finally{releaseRoom();releaseGeneration();releaseCheck();releaseReview();await new Promise(r=>server.close(r));rmSync(directory,{recursive:true,force:true});}
});
