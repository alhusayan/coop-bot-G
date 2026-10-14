import test from 'node:test';
import assert from 'node:assert/strict';
import {createHmac} from 'node:crypto';
import {originalOffer,createOriginalResults,searchOriginalPiece} from '../findzia-engine.mjs';
import {filterApprovedItem} from '../sourcing.mjs';
import {preferLocalResults} from '../public/product-order.js';
import {pieceHotspots} from '../public/hotspots.js';

const row={url:'https://danishdesignstore.com/products/green-chair',image:'https://images.example/chair.jpg',title:'Green chair',store:'Danishdesignstore',price:'1,150.00 USD',price_amount:1150,currency:'USD',price_contract:'findzia-money-v1',price_display_ready:true,price_display_currency:'USD',market_scope:'local',match_type:'similar',classification_final:true,identity_review_status:'completed',visual_axes:{category:'same',subtype:'same',color:'same'},audited_media_path:'/api/media/verified/test-chair',identity_match_percentage:85};

test('original prices, decimals and stores survive without Spaces merchant/audit filters',()=>{
 const items=Array.from({length:14},(_,i)=>({...row,url:`https://store${i}.example/products/chair`,price_amount:134+i/100,price:`${134+i/100} USD`,market_scope:i<7?'local':'global'}));
 const result=preferLocalResults(filterApprovedItem({search_engine:'findzia-original',offers:[],alternatives:items.map(x=>originalOffer(x,'US'))},'US'));
 assert.equal(result.alternatives.length,14);assert.equal(result.alternatives[1].price,134.01);
 assert.equal(result.alternatives.filter(x=>x.market_scope==='international').length,7);
 assert.equal(filterApprovedItem(result,'KW').alternatives.length,0);
 assert.equal(originalOffer({...row,price:'1.150,50 EUR',price_amount:1150.5,price_display_currency:'EUR'},'DE').price_label,'1.150,50 EUR');
});
test('prices survive sparse updates; snapshots merge and explicit removals are honored like original',()=>{
 const results=createOriginalResults('US');
 results.accept({event:'result',item:{...row,price_amount:null,price_display_ready:false}});assert.equal(results.snapshot().length,0);
 results.accept({event:'upsert',item:row});assert.equal(results.snapshot().length,1);
 results.accept({event:'upsert',item:{url:row.url,market_scope:'local',price_amount:129.99,price:'129.99 USD'}});assert.equal(results.snapshot()[0].price,129.99);
 results.accept({event:'snapshot',authoritative:true,results:[]});assert.equal(results.snapshot().length,1);
 results.accept({event:'upsert',item:{url:row.url,market_scope:'local',price:'',price_amount:null,price_display_ready:false,image:'',retrieval_sources:[]}});assert.equal(results.snapshot()[0].price,129.99);
 results.accept({event:'result',item:row});results.accept({event:'upsert',item:{url:row.url,market_scope:'local',stock_status:'out_of_stock'}});assert.equal(results.snapshot().length,0);
 results.accept({event:'result',item:{...row,stock_status:'in_stock'}});results.accept({event:'remove',url:row.url});assert.equal(results.snapshot().length,0);
 for(const change of [{price_unavailable:true},{price_integrity_status:'pending'},{photo_match_status:'rejected'},{price_amount:0},{price_amount:'134'}])assert.equal(originalOffer({...row,...change},'US'),null);
});
test('same photo, country and original NDJSON transport, without invented search description',async()=>{
 const secret='s'.repeat(64),bytes=Buffer.from('unchanged photo bytes');
 const result=await searchOriginalPiece(bytes,'US',{room:'1'.repeat(24),env:{FINDZIA_SPACES_ENGINE_KEY:secret},fetcher:async(url,options)=>{
  assert.equal(url,'https://api.findzia.com/internal/spaces/image/stream');
  assert.equal(options.headers['Accept-Encoding'],'identity');
  const body=JSON.parse(options.body);assert.equal(body.image_base64,bytes.toString('base64'));assert.equal(body.country,'US');assert.equal(body.caption,undefined);assert.equal(body.query,undefined);
  assert.equal(options.headers['X-Findzia-Spaces-Signature'],createHmac('sha256',secret).update(options.headers['X-Findzia-Spaces-Time']+'\n'+options.headers['X-Findzia-Spaces-Nonce']+'\n'+options.body).digest('hex'));
  const text=[{event:'result',item:row},{event:'done'}].map(x=>JSON.stringify(x)).join('\n');
  return new Response(text,{headers:{'Content-Type':'application/x-ndjson'}});
 }});
 assert.equal(result.alternatives.length,1);assert.equal(result.alternatives[0].source,'Danishdesignstore');assert.equal(result.partial,false);
});
test('a chair and overlapping desk remain independently selectable; all pieces have markers',()=>{
 const items=[{id:'1',name_en:'Desk',box:[100,100,900,900]},{id:'2',name_en:'Chair',box:[300,300,900,700]},...Array.from({length:12},(_,i)=>({id:String(i+3),box:[10+i*50,10,50+i*50,90]}))];
 const points=pieceHotspots(items,700,500);assert.equal(points.length,14);
 const chair=points.find(x=>x.id==='2'),desk=points.find(x=>x.id==='1');assert.ok(Math.hypot((chair.x-desk.x)*.7,(chair.y-desk.y)*.5)>=34);
 for(const point of points){assert.ok(point.x>=point.box[1]&&point.x<=point.box[3]);assert.ok(point.y>=point.box[0]&&point.y<=point.box[2]);}
});
test('Spaces waits for original visual evidence and withholds pending or distant alternatives',()=>{
 const preview={...row,search_origin:'image',classification_final:false,identity_review_status:'pending',photo_match_status:'pending',display_before_audit:true};
 assert.equal(originalOffer(preview,'US'),null);
 assert.equal(originalOffer({...preview,photo_match_status:'rejected'},'US'),null);
 const alternative={...row,search_origin:'image',retrieval_sources:['serper_images']};
 assert.equal(originalOffer(alternative,'US'),null);
 assert.ok(originalOffer({...alternative,alternative_visual_status:'approved',alternative_visual_policy:'156.7.3',alternative_visual_proof:'original-proof'},'US'));
});


test('the original SHEIN store-price exception is retained only for a reviewed close piece',()=>{
 const shein={...row,url:'https://us.shein.com/Beige-Sofa-p-12345678.html',price:'',price_amount:null,price_display_ready:false,price_unavailable:true};
 const offer=originalOffer(shein,'KW');assert.ok(offer);assert.equal(offer.price,null);assert.equal(offer.price_at_store,true);
 assert.equal(filterApprovedItem({search_engine:'findzia-original',alternatives:[offer]},'KW').alternatives.length,1);
 assert.equal(originalOffer({...shein,visual_axes:{category:'different'},identity_match_percentage:18},'KW'),null);
});
test('wrong product, distant color, and upholstery changes cannot pass as similar',()=>{
 const approved={...row,search_origin:'image',retrieval_sources:['serper_images'],alternative_visual_status:'approved',alternative_visual_policy:'156.7.3',alternative_visual_proof:'proof'};
 for(const axes of [{category:'different'},{category:'same',color:'different'},{category:'same',material:'different'},{category:'same',shape_geometry:'different'}])assert.equal(originalOffer({...approved,visual_axes:axes},'US'),null);
 assert.equal(originalOffer({...row,identity_match_percentage:18,visual_axes:{category:'different'}},'US'),null);
 assert.ok(originalOffer({...row,identity_match_percentage:38,conflicts:['brand','model'],visual_axes:{category:'same',subtype:'same',color:'same',material:'same'}},'US'));
});
test('late classifier updates preserve original images, price and Lens evidence',()=>{
 const results=createOriginalResults('KW');const first={...row,search_origin:'image',retrieval_sources:['google_lens']};
 results.accept({event:'result',item:first});
 results.accept({event:'upsert',item:{...first,image:'',price:'',price_amount:null,price_display_ready:false,retrieval_sources:['serper_images'],alternative_visual_status:'approved',alternative_visual_policy:'156.7.3',alternative_visual_proof:'proof'}});
 assert.equal(results.snapshot().length,1);assert.equal(results.snapshot()[0].price,1150);assert.equal(results.snapshot()[0].original_result_group,'local');
});

test('user language is sent unchanged instead of being replaced by the market language',async()=>{
 await searchOriginalPiece(Buffer.from('photo'),'KW',{room:'2'.repeat(24),language:'en',env:{FINDZIA_SPACES_ENGINE_KEY:'s'.repeat(64)},fetcher:async(_url,options)=>{
  const body=JSON.parse(options.body);assert.equal(body.lang,'en');assert.equal(body.country,'KW');
  return new Response(JSON.stringify({event:'done'})+'\n',{headers:{'Content-Type':'application/x-ndjson'}});
 }});
});

test('shared client functions are verbatim originals, including sparse updates and price exceptions',async t=>{
 const {readFileSync,existsSync}=await import('node:fs');const {Script}=await import('node:vm');
 const paths=[new URL('../../frontend/source/findzia-home.liquid',import.meta.url),new URL('../../main/frontend__source__findzia-home.liquid',import.meta.url),new URL('../../../frontend/source/findzia-home.liquid',import.meta.url)];
 const path=paths.find(existsSync);if(!path)return t.skip('original checkout not present');
 const original=readFileSync(path,'utf8'),shared=readFileSync(new URL('../original-client.mjs',import.meta.url),'utf8');
 for(const name of ['_r','br','lt','fzSheinPriceLink','fzOfferCanDisplay','$t','Fr','Ct','At']){
  const start=original.indexOf('function '+name+'(');assert.ok(start>=0);
  let fn='';for(let end=original.indexOf('}',start);end>=0;end=original.indexOf('}',end+1)){const candidate=original.slice(start,end+1);try{new Script('('+candidate+')');fn=candidate;break;}catch{}}
  assert.ok(fn&&shared.includes(fn),'original '+name+' must not drift');
 }
});


test('pending visual candidates do not trigger a second hidden search or unchecked previews',async()=>{
 let calls=0;const bodies=[];
 const result=await searchOriginalPiece(Buffer.from('photo'),'KW',{room:'3'.repeat(24),env:{FINDZIA_SPACES_ENGINE_KEY:'s'.repeat(64)},fetcher:async(_url,options)=>{
  bodies.push(options.body);calls++;
  const item=calls===1?{...row,classification_final:false,identity_review_status:'pending',display_before_audit:true}:row;
  return new Response([JSON.stringify({event:'result',item}),JSON.stringify({event:'done'})].join('\n'),{headers:{'Content-Type':'application/x-ndjson'}});
 }});
 assert.equal(calls,1);assert.equal(result.alternatives.length,0);assert.equal(result.search_diagnostics.attempts,1);
});

test('a reviewed card reaches the room while the original stream is still open',async()=>{
 let stream,notify;const first=new Promise(resolve=>notify=resolve);let finished=false;
 const pending=searchOriginalPiece(Buffer.from('photo'),'US',{room:'4'.repeat(24),env:{FINDZIA_SPACES_ENGINE_KEY:'s'.repeat(64)},onProgress:update=>{if(update.alternatives?.length)notify(update);},fetcher:async()=>new Response(new ReadableStream({start(controller){stream=controller;controller.enqueue(new TextEncoder().encode(JSON.stringify({event:'upsert',item:row,elapsed_ms:1000})+'\n'));}}),{headers:{'Content-Type':'application/x-ndjson'}})}).then(result=>{finished=true;return result;});
 const update=await first;assert.equal(finished,false);assert.equal(update.alternatives.length,1);assert.equal(update.search_timing.provider_first_verified_ms,1000);
 stream.enqueue(new TextEncoder().encode('{"event":"done"}\n'));stream.close();
 const result=await pending;assert.equal(result.partial,false);assert.ok(result.search_timing.first_byte_ms!==null);assert.ok(result.search_timing.first_verified_ms!==null);
});

test('a store-price link can never become a zero-price room summary',async()=>{
 const {readFileSync}=await import('node:fs');const {runInNewContext}=await import('node:vm');
 const source=readFileSync(new URL('../public/app.js',import.meta.url),'utf8');
 const fn=source.split('\n').find(line=>line.startsWith('function itemStatus('));
 const status=runInNewContext('('+fn+')',{country:()=>({currency:'KWD'}),money:n=>String(n),pieceActivity:()=>''});
 const item={search_engine:'findzia-original',alternatives:[{currency:'KWD',price:null,price_at_store:true}]};
 assert.equal(status(item),'1 store options');
 item.alternatives.push({currency:'KWD',price:95});assert.equal(status(item),'2 store options · 95');
});

test('retired furnishing options cannot relax ordinary visual matching',()=>{
 const differentLegs={...row,visual_axes:{...row.visual_axes,shape_geometry:'different',support_base:'different'}};
 assert.equal(originalOffer(differentLegs,'US'),null);
 assert.equal(originalOffer(differentLegs,'US',{purpose:'furnishing'}),null);
 const stream=createOriginalResults('US',()=>{},{purpose:'furnishing'});
 stream.accept({event:'result',item:differentLegs});assert.equal(stream.snapshot().length,0);
});
