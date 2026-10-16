import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,writeFileSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHmac,createHash} from 'node:crypto';
import sharp from 'sharp';
const directory=mkdtempSync(join(tmpdir(),'piece-refresh-')),owner='1'.repeat(32),id='2'.repeat(24),secret='piece-refresh-test';
process.env.NODE_ENV='production';process.env.SPACES_TRIAL_TOKEN=secret;process.env.SPACES_DATA_DIR=directory;process.env.GEMINI_API_KEY='local-test';
const pixels=await sharp({create:{width:800,height:800,channels:3,background:'#cfc0a0'}}).jpeg().toBuffer();
mkdirSync(join(directory,id));writeFileSync(join(directory,id,'design-0.jpg'),pixels);
const sofa={id:'1',name_en:'Sofa',mode:'ready',box:[300,200,700,800],offers:[],alternatives:[],status:'idle',original_view:{items:[{title:'Previous sofa search'}],lastSearch:{country:'KW'}}};
const chair={id:'2',name_en:'Desk chair',mode:'ready',box:[400,420,700,650],offers:[],alternatives:[],status:'idle',original_view:{items:[{title:'Saved chair'}],lastSearch:{country:'KW'}},design_picks:[{url:'https://store.test/chair'}]};
writeFileSync(join(directory,'state.json'),JSON.stringify({jobs:{[id]:{id,owner,created:Date.now(),options:{market:'KW',keep:''},room:'Bedroom',designs:[{status:'ready',image:'design-0.jpg',matching_version:3,inventory_version:2,items:[sofa,chair]}]}},quota:{}}));
const {createServer}=await import('../server.mjs');
test('opening an old design repairs its inventory once without redrawing the image or spending search credit',async t=>{
 const realFetch=globalThis.fetch,calls=[];
 t.mock.method(globalThis,'fetch',async(url,options)=>{
  if(!String(url).startsWith('https://generativelanguage.googleapis.com/'))return realFetch(url,options);
  const body=JSON.parse(options.body),prompt=body.contents[0].parts[0].text;calls.push(prompt);
  assert.equal(body.generationConfig.responseModalities,undefined,'no image regeneration');
  const value=prompt.startsWith('Identify ALL distinct')?{items:[{name_en:'Sofa',box:[300,250,350,750],selection_boxes:[[300,250,350,750]]},{name_en:'Desk chair',box:chair.box},{name_en:'Desk',box:[350,200,700,850]},{name_en:'Custom wall panelling',search_kind:'service',service_query_ar:'نجار لتفصيل ديكور حائط',surface:'wall',mode:'quote',box:[0,0,200,1000]}]}:{corrections:[],additions:[],groups:[]};
  return Response.json({candidates:[{content:{parts:[{text:JSON.stringify(value)}]}}]});
 });
 const s=createServer();await new Promise(r=>s.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+s.address().port,stamp=Date.now()+60000,value=owner+'.'+stamp;
 const cookie='spaces_session='+value+'.'+createHmac('sha256',secret).update(value).digest('hex');
 try{
  const before=await (await fetch(base+'/api/jobs/'+id,{headers:{cookie}})).json();assert.equal(before.designs[0].needs_rescan,true);
  const select=()=>fetch(base+'/api/jobs/'+id+'/select',{method:'POST',headers:{cookie,'Content-Type':'application/json'},body:'{"design":0}'});
  assert.equal((await select()).status,202);
  let result;
  for(let i=0;i<100;i++){result=await (await fetch(base+'/api/jobs/'+id,{headers:{cookie}})).json();if(!result.designs[0].needs_rescan&&result.designs[0].status==='ready')break;await new Promise(r=>setTimeout(r,10));}
  const d=result.designs[0];assert.equal(d.status,'ready');assert.equal(d.needs_rescan,false);assert.equal(d.items.length,4);const wall=d.items.find(x=>x.name_en==='Custom wall panelling');assert.equal(wall.search_kind,'service');assert.equal(wall.service_query_ar,'نجار لتفصيل ديكور حائط');assert.equal(d.inventory_backup,undefined);
  const saved=d.items.find(x=>x.name_en==='Desk chair');assert.equal(saved.id,'2');assert.deepEqual(saved.original_view,chair.original_view);assert.deepEqual(saved.design_picks,chair.design_picks);
  const corrected=d.items.find(x=>x.name_en==='Sofa');assert.notEqual(corrected.id,'1');assert.equal(corrected.original_view,undefined);
  assert.ok(d.items.every(x=>x.crop));assert.equal(calls.length,2);
  await select();assert.equal(calls.length,2,'repair is not repeated');
  assert.equal(createHash('sha256').update(readFileSync(join(directory,id,'design-0.jpg'))).digest('hex'),createHash('sha256').update(pixels).digest('hex'));
  const stored=JSON.parse(readFileSync(join(directory,'state.json'),'utf8'));assert.deepEqual(stored.jobs[id].designs[0].inventory_backup.items[0].original_view,sofa.original_view);
  assert.ok(Object.keys(stored.quota).every(key=>key.endsWith(':select')),'only free inventory selection allowance is touched');
 }finally{await new Promise(r=>s.close(r));rmSync(directory,{recursive:true,force:true});}
});
