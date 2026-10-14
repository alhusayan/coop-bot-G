import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import sharp from 'sharp';
import {detectRoom,designPrompt,verifyRoomFunction} from '../room-function.mjs';
import {STYLES} from '../engine.mjs';

for(const [type,setting,request,label] of [
 ['empty_land','land','فيلا مع حديقة على الأرض','Villa and garden'],
 ['courtyard','outdoor','حديقة مع جلسة مظللة','Courtyard garden'],
 ['facade','facade','تحديث واجهة المبنى','Building exterior'],
 ['empty_room','interior','مطبخ من الصفر','Kitchen'],
 ['unfinished','interior','حمام حديث','Bathroom']
])test(`accepts ${type} as a site and verifies its requested new use`,async()=>{
 const before={inlineData:{data:'source'}},after={inlineData:{data:'concept'}};
 const options={request,scope:'scratch',width:25,length:40};
 const context=await detectRoom(before,{...options,judge:async parts=>{
  assert.equal(parts[1],before);assert.ok(parts[0].text.includes(request));
  return {is_space:true,is_room:false,type,setting,is_empty:true,room_en:'Existing site',target:{label,brief:request,required_functions:['Requested layout']}};
 }});
 assert.equal(context.type,type);assert.equal(context.room_en,label);assert.equal(context.preferences.scope,'scratch');
 const prompt=designPrompt(context,options,STYLES[0].prompt,'KWD');
 assert.ok(prompt.includes(request));assert.match(prompt,/new building is allowed when requested/);assert.match(prompt,/"width_metres":25/);
 assert.doesNotMatch(prompt,/Do not hallucinate a larger room or change its function/);
 const verify=async result=>verifyRoomFunction(before,after,context,{judge:async parts=>{assert.equal(parts[1],before);assert.equal(parts[2],after);assert.ok(parts[0].text.includes(request));return result;}});
 assert.equal((await verify({meets_brief:true,site_preserved:true})).ok,true);
 assert.equal((await verify({meets_brief:false,site_preserved:true})).ok,false);
 assert.equal((await verify({meets_brief:true,site_preserved:false})).ok,false);
});

test('decor scope continues to preserve built features and invalid subjects remain rejected',async()=>{
 assert.match(designPrompt({type:'office'},{scope:'decor'},'Quiet design','KWD'),/Only movable furniture/);
 assert.match(designPrompt({type:'office'},{scope:'decor'},'Quiet design','KWD'),/usable work desk/);
 await assert.rejects(detectRoom({}, {judge:async()=>({is_space:false,is_room:true,type:'other'})}),/NOT_A_ROOM/);
});

test('bare-land request completes all designs, and reopening a retail-free concept does not restart inventory',async t=>{
 const directory=mkdtempSync(join(tmpdir(),'spaces-site-test-'));
 process.env.NODE_ENV='production';process.env.SPACES_TRIAL_TOKEN='site-test';process.env.SPACES_DATA_DIR=directory;
 process.env.GEMINI_API_KEY='local-test-only';process.env.SERPER_API_KEY='local-test-only';
 const jpeg=await sharp({create:{width:512,height:512,channels:3,background:'#c3b79e'}}).jpeg().toBuffer();
 const modelCalls=[],realFetch=globalThis.fetch;
 t.mock.method(globalThis,'fetch',async(url,options)=>{
  if(!String(url).startsWith('https://generativelanguage.googleapis.com/'))return realFetch(url,options);
  const input=JSON.parse(options.body),prompt=input.contents[0].parts[0].text;modelCalls.push(prompt);
  let parts;
  if(input.generationConfig.responseModalities?.includes('IMAGE'))parts=[{inlineData:{mimeType:'image/jpeg',data:jpeg.toString('base64')}}];
  else {
   let result;
   if(prompt.startsWith('Identify the photographed SPACE'))result={is_space:true,is_room:false,type:'empty_land',setting:'land',is_empty:true,room_en:'Empty plot',target:{label:'Villa',brief:'فيلا على أرض فاضية',required_functions:['Villa','Outdoor access']}};
   else if(prompt.startsWith('Compare the original space/site'))result={meets_brief:true,site_preserved:true};
   else if(prompt.startsWith('Identify ALL distinct'))result={items:[],no_retail_items:true};
   else throw Error('Unexpected model request');
   parts=[{text:JSON.stringify(result)}];
  }
  return Response.json({candidates:[{content:{parts}}]});
 });
 const {createServer}=await import('../server.mjs');
 const server=createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
 try{
  const auth=await fetch(base+'/trial/site-test'),cookie=auth.headers.get('set-cookie').split(';')[0];
  const result=await fetch(base+'/api/jobs',{method:'POST',headers:{cookie,'Content-Type':'application/json'},body:JSON.stringify({market:'KW',request:'فيلا على أرض فاضية',scope:'scratch',width:120,length:200,image:'data:image/jpeg;base64,'+jpeg.toString('base64')})});
  assert.equal(result.status,202);const initial=await result.json();let job;
  for(let i=0;i<50;i++){
   job=await (await fetch(base+'/api/jobs/'+initial.id,{headers:{cookie}})).json();
   if(job.designs.every(d=>d.status==='ready'&&d.inventory_complete))break;
   await new Promise(r=>setTimeout(r,10));
  }
  assert.equal(job.options.request,'فيلا على أرض فاضية');assert.equal(job.options.scope,'scratch');assert.equal(job.options.width,120);assert.equal(job.options.length,200);
  assert.equal(job.room,'Villa');assert.equal(job.designs.length,3);
  for(const design of job.designs){assert.equal(design.status,'ready');assert.equal(design.error,null);assert.equal(design.inventory_complete,true);assert.deepEqual(design.items,[]);assert.ok(design.image);}
  assert.equal(modelCalls.length,10,'one classification, three renders, three checks, three inventories');
  for(let i=0;i<3;i++){
   const selected=await fetch(base+'/api/jobs/'+job.id+'/select',{method:'POST',headers:{cookie,'Content-Type':'application/json'},body:JSON.stringify({design:0})});
   assert.equal(selected.status,202);assert.equal((await selected.json()).designs[0].status,'ready');
  }
  assert.equal(modelCalls.length,10,'reopening does not repeat work');
  const stored=JSON.parse(readFileSync(join(directory,'state.json'),'utf8'));
  assert.ok(Object.keys(stored.quota).every(key=>!key.endsWith(':select')),'no selection quota spent on a completed empty inventory');
 }finally{await new Promise(r=>server.close(r));rmSync(directory,{recursive:true,force:true});}
});
