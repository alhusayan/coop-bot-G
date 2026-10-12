import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,writeFileSync,rmSync,readFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHmac} from 'node:crypto';
import sharp from 'sharp';
const data=mkdtempSync(join(tmpdir(),'spaces-finish-')),owner='a'.repeat(32),id='b'.repeat(24),token='test-finish-invite';
process.env.NODE_ENV='production';process.env.SPACES_TRIAL_TOKEN=token;process.env.SPACES_DATA_DIR=data;
const bytes=await sharp({create:{width:1000,height:800,channels:3,background:'#bbaa99'}}).jpeg().toBuffer();
mkdirSync(join(data,id));writeFileSync(join(data,id,'design-0.jpg'),bytes);
const size={width:80,depth:85,height:90},views=[{id:'1',box:[100,20,700,430]},{id:'2',box:[100,570,700,980]}],offer={link:'https://www.homecentre.com/kw/en/p/123',image:'https://example.com/chair.jpg',title:'Olive chair',availability:'listed_available',dimensions_cm:size,market_scope:'local'};
const item={id:'1',name_en:'Chair',mode:'ready',status:'done',box:views[0].box,occurrences:views,quantity:2,offers:[],alternatives:[offer]};
writeFileSync(join(data,'state.json'),JSON.stringify({quota:{},jobs:{[id]:{id,owner,created:Date.now(),options:{market:'KW'},room:'Living room',designs:[{image:'design-0.jpg',status:'complete',matching_version:3,items:[item]}]}}}));
const {createServer}=await import('../server.mjs');
test('finish preview is private and reversible; keeping publishes both copies atomically and rechecks stock',async()=>{
 let available=true;
 const plan={room:{width_cm:400,length_cm:500},limits:{},picks:[{id:'1',name:'Chair',views,offer}],options:{'1':[offer]},skipped:[]};
 const s=createServer({recommend:async()=>structuredClone(plan),preview:async()=>({output:bytes,mimeType:'image/jpeg',boxes:{'1':views.map(v=>v.box)}}),stock:async o=>({...o,availability:available?'listed_available':'out_of_stock'})});
 await new Promise(r=>s.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+s.address().port,stamp=Date.now()+60000,value=owner+'.'+stamp,cookie='spaces_session='+value+'.'+createHmac('sha256',token).update(value).digest('hex');
 const post=(action,body={})=>fetch(base+'/api/jobs/'+id+'/'+action,{method:'POST',headers:{cookie,'content-type':'application/json'},body:JSON.stringify({design:0,...body})});
 const job=()=>fetch(base+'/api/jobs/'+id,{headers:{cookie}}).then(r=>r.json());
 async function wait(){for(let n=0;n<100;n++){const j=await job();if(j.designs[0].status!=='finishing')return j;await new Promise(r=>setTimeout(r,10));}throw Error('timeout');}
 try{
  assert.equal((await post('finish')).status,400);
  assert.equal((await fetch(base+'/api/jobs/'+id+'/finish',{method:'POST',body:'{}'})).status,401);
  assert.equal((await post('finish',{width:4,length:5})).status,202);
  let j=await wait(),d=j.designs[0];assert.equal(d.finish.status,'preview');assert.match(d.image,/design-0.jpg$/);assert.notEqual(d.finish.image,d.image);assert.equal(d.items[0].offers.length,0);
  assert.equal((await post('keep-finish',{token:'wrong'})).status,409);
  await post('discard-finish');j=await job();assert.equal(j.designs[0].finish,null);assert.match(j.designs[0].image,/design-0.jpg$/);
  await post('finish',{width:4,length:5});j=await wait();available=false;
  await post('keep-finish',{token:j.designs[0].finish.token});j=await wait();assert.equal(j.designs[0].finish.error,'STOCK_CHANGED');assert.match(j.designs[0].image,/design-0.jpg$/);
  available=true;await post('finish',{width:4,length:5});j=await wait();const preview=j.designs[0].finish.image;
  await post('keep-finish',{token:j.designs[0].finish.token});j=await wait();d=j.designs[0];assert.equal(d.finish.status,'kept');assert.equal(d.image,preview);assert.equal(d.items[0].offers[0].link,offer.link);assert.equal(d.items[0].offers[0].size_verified,false);assert.equal(d.items[0].occurrences.length,2);assert.notEqual(d.items[0].occurrences[0].crop,d.items[0].occurrences[1].crop);
  const stored=JSON.parse(readFileSync(join(data,'state.json'))).jobs[id].designs[0];assert.equal(stored.finish.status,'kept');assert.equal(stored.items[0].offers.length,1);
 }finally{await new Promise(r=>s.close(r));rmSync(data,{recursive:true,force:true});}
});
