import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHmac} from 'node:crypto';
import {updateDesignPicks,hasSavedResults,savedPickImage} from '../public/design-picks.js';

test('bookmarks stay within their room, design and piece and survive reopening',async()=>{
 const dir=mkdtempSync(join(tmpdir(),'spaces-picks-')),owner='1'.repeat(32),id='a'.repeat(24),secret='picks-test';
 process.env.SPACES_TRIAL_TOKEN=secret;process.env.SPACES_DATA_DIR=dir;process.env.NODE_ENV='production';
 const design=()=>({status:'ready',matching_version:3,items:[{id:'1',status:'idle',offers:[],alternatives:[]}]});
 writeFileSync(join(dir,'state.json'),JSON.stringify({jobs:{[id]:{id,owner,created:Date.now(),options:{market:'KW'},designs:[design(),design()]}},quota:{}}));
 const {createServer}=await import('../server.mjs');const server=createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const base='http://127.0.0.1:'+server.address().port;
 const cookie=who=>{const data=who+'.'+(Date.now()+60000);return 'spaces_session='+data+'.'+createHmac('sha256',secret).update(data).digest('hex');};
 const request=(who,body)=>fetch(base+'/api/jobs/'+id+'/picks/1',{method:'POST',headers:{cookie:cookie(who),'Content-Type':'application/json'},body:JSON.stringify(body)});
 try{
  const product={url:'https://shop.test/products/chair?utm_source=findzia',title:'Chair',price:'KWD 95.000',image:'https://shop.test/chair.jpg'};
  assert.equal((await request('2'.repeat(32),{design:0,product})).status,404);
  assert.equal((await request(owner,{design:0,product:{url:'javascript:alert(1)'}})).status,400);
  assert.equal((await request(owner,{design:0,product})).status,200);
  await request(owner,{design:0,product});
  const job=await (await fetch(base+'/api/jobs/'+id,{headers:{cookie:cookie(owner)}})).json();
  assert.equal(job.designs[0].items[0].design_picks.length,1);assert.equal(job.designs[1].items[0].design_picks,undefined);
  assert.equal(job.designs[0].items[0].design_picks[0].price,'KWD 95.000');
  for(const country of ['KW','US']){
   const view={items:[{url:'https://shop.test/'+country}],lastSearch:{kind:'image',country}};
   assert.equal((await fetch(base+'/api/jobs/'+id+'/results/1',{method:'POST',headers:{cookie:cookie(owner),'Content-Type':'application/json'},body:JSON.stringify({design:0,view})})).status,200);
  }
  const markets=await (await fetch(base+'/api/jobs/'+id,{headers:{cookie:cookie(owner)}})).json();
  assert.deepEqual(Object.keys(markets.designs[0].items[0].original_views).sort(),['KW','US']);
  assert.equal(readFileSync(join(dir,'state.json'),'utf8').includes('https://shop.test/products/chair'),true);
  assert.equal((await request(owner,{design:0,product,remove:true})).status,200);
  const removed=await (await fetch(base+'/api/jobs/'+id,{headers:{cookie:cookie(owner)}})).json();assert.equal(removed.designs[0].items[0].design_picks.length,0);
 }finally{await new Promise(r=>server.close(r));rmSync(dir,{recursive:true,force:true});}
});
test('empty or wrong-market snapshots cannot masquerade as a saved search',()=>{
 assert.equal(hasSavedResults({items:[],lastSearch:{kind:'image',country:'KW'}},'KW'),false);
 assert.equal(hasSavedResults({items:[{}],lastSearch:{kind:'image',country:'SA'}},'KW'),false);
 assert.throws(()=>updateDesignPicks(Array.from({length:20},(_,i)=>({url:'https://shop.test/'+i})),{url:'https://shop.test/new'}),/PICKS_LIMIT/);
});

test('saved product photos use a durable source instead of an expired verified-media cache',()=>{
 const pick={url:'https://shop.test/table',image:'https://api.findzia.com/api/media/verified/expired'};
 const row={url:pick.url,audited_image:'https://shop.test/table.jpg',image:'https://shop.test/other.jpg'};
 assert.equal(savedPickImage(pick,[row]),row.audited_image);
 assert.equal(savedPickImage({...pick,image:'https://shop.test/chosen.jpg'},[row]),'https://shop.test/chosen.jpg');
 assert.equal(savedPickImage(pick,[{...row,audited_image:'javascript:alert(1)'}]),row.image);
 assert.equal(savedPickImage(pick,[{...row,url:'https://different.test/table'}]),pick.image);
});
