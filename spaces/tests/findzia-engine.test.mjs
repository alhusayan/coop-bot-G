import test from 'node:test';
import assert from 'node:assert/strict';
import {createHmac} from 'node:crypto';
import {originalOffer,createOriginalResults,searchOriginalPiece} from '../findzia-engine.mjs';
import {filterApprovedItem} from '../sourcing.mjs';
import {preferLocalResults} from '../public/product-order.js';
import {pieceHotspots} from '../public/hotspots.js';

const row={url:'https://danishdesignstore.com/products/green-chair',image:'https://images.example/chair.jpg',title:'Green chair',store:'Danishdesignstore',price:'1,150.00 USD',price_amount:1150,currency:'USD',price_contract:'findzia-money-v1',price_display_ready:true,price_display_currency:'USD',market_scope:'local',match_type:'similar'};

test('original prices, decimals and stores survive without Spaces merchant/audit filters',()=>{
 const items=Array.from({length:14},(_,i)=>({...row,url:`https://store${i}.example/products/chair`,price_amount:134+i/100,price:`${134+i/100} USD`,market_scope:i<7?'local':'global'}));
 const result=preferLocalResults(filterApprovedItem({search_engine:'findzia-original',offers:[],alternatives:items.map(x=>originalOffer(x,'US'))},'US'));
 assert.equal(result.alternatives.length,14);assert.equal(result.alternatives[1].price,134.01);
 assert.equal(result.alternatives.filter(x=>x.market_scope==='international').length,7);
 assert.equal(filterApprovedItem(result,'KW').alternatives.length,0);
 assert.equal(originalOffer({...row,price:'1.150,50 EUR',price_amount:1150.5,price_display_currency:'EUR'},'DE').price_label,'1.150,50 EUR');
});
test('prices arrive later; authoritative removal, invalid price and sold out are honored',()=>{
 const results=createOriginalResults('US');
 results.accept({event:'result',item:{...row,price_amount:null,price_display_ready:false}});assert.equal(results.snapshot().length,0);
 results.accept({event:'upsert',item:row});assert.equal(results.snapshot().length,1);
 results.accept({event:'upsert',item:{url:row.url,price_amount:129.99,price:'129.99 USD'}});assert.equal(results.snapshot()[0].price,129.99);
 results.accept({event:'snapshot',authoritative:true,results:[]});assert.equal(results.snapshot().length,0);
 results.accept({event:'result',item:row});results.accept({event:'upsert',item:{url:row.url,stock_status:'out_of_stock'}});assert.equal(results.snapshot().length,0);
 results.accept({event:'result',item:{...row,stock_status:'in_stock'}});results.accept({event:'remove',url:row.url});assert.equal(results.snapshot().length,0);
 for(const change of [{price_unavailable:true},{price_integrity_status:'pending'},{photo_match_status:'rejected'},{price_amount:0},{price_amount:'134'}])assert.equal(originalOffer({...row,...change},'US'),null);
});
test('same photo, country and original NDJSON transport, without invented search description',async()=>{
 const secret='s'.repeat(64),bytes=Buffer.from('unchanged photo bytes');
 const result=await searchOriginalPiece(bytes,'US',{room:'1'.repeat(24),env:{FINDZIA_SPACES_ENGINE_KEY:secret},fetcher:async(url,options)=>{
  assert.equal(url,'https://api.findzia.com/internal/spaces/image/stream');
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
