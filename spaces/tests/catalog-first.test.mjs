import test from 'node:test';
import assert from 'node:assert/strict';
import sharp from 'sharp';
import {designFromCatalog,validateCatalogPlan,catalogSize,catalogSearchQueries,sourceCatalogItem,renderCatalogRoom} from '../catalog-first.mjs';
const original={inlineData:{mimeType:'image/jpeg',data:'test'}},room={width_cm:400,length_cm:500};
const offer={title:'Olive chair',link:'https://www.safathome.com/olive-chair/p',image:'https://example.com/chair.jpg',availability:'listed_available',dimensions_cm:{width:80,depth:85,height:90}};
const item={id:'1',name_en:'Chair',essential:true,mounting:'floor',quantity:2,room,offers:[offer]};
const layout={choices:[{id:'1',link:offer.link,placements:[{x_cm:0,y_cm:0,rotation:0,box:[50,50,450,400]},{x_cm:200,y_cm:0,rotation:90,box:[50,550,450,900]}]}]};
const context={type:'living_room',room_en:'Living room'};
const brief={title:'Warm room',items:[{name_en:'Chair',query_en:'Olive fabric accent chair',essential:true,mounting:'floor',quantity:2}]};
test('measurements are required before detection, shopping or generation',async()=>{
 let calls=0;await assert.rejects(designFromCatalog(original,{}, {detect:async()=>{calls++;}}),/ROOM_SIZE_REQUIRED/);assert.equal(calls,0);
});
test('automatic choices use supplied products, same SKU for every copy and numerical non-overlapping footprints',()=>{
 const plan=validateCatalogPlan(layout,[item],room);assert.equal(plan.picks.length,1);assert.equal(plan.picks[0].quantity,2);assert.equal(plan.picks[0].offer.link,offer.link);assert.equal(plan.picks[0].offer.size_verified,false);
 for(const change of [x=>x.choices[0].link='https://wrong.example/p',x=>x.choices[0].placements.pop(),x=>x.choices[0].placements[1].x_cm=1,x=>x.choices[0].placements[1].x_cm=399]){const bad=structuredClone(layout);change(bad);assert.throws(()=>validateCatalogPlan(bad,[item],room),/INVALID_CATALOG/);}
 assert.throws(()=>validateCatalogPlan(layout,[{...item,offers:[{...offer,availability:'out_of_stock'}]}],room),/INVALID_CATALOG/);
 assert.equal(catalogSize(item,{width:80,height:90}),false);assert.equal(catalogSize({name_en:'Area rug'},{width:200,length:290}),true);
});
test('all automatic sourcing and fresh stock checks precede the single renderer call',async()=>{
 const events=[];let judgments=0;
 const result=await designFromCatalog(original,{width:4,length:5,market:'KW',notes:'Olive'}, {detect:async()=>context,judge:async()=>++judgments===1?brief:layout,source:async()=>{events.push('source');return [offer];},stock:async o=>{events.push('stock');return {...o,dimensions_cm:{height:90,depth:85,width:80}};},render:async(_,plan)=>{events.push('render');assert.equal(plan.picks[0].quantity,2);return {output:Buffer.from('test'),boxes:{'1':layout.choices[0].placements.map(x=>x.box)}};}});
 assert.deepEqual(events,['source','stock','render']);assert.equal(result.title,'Warm room');assert.equal(result.plan.picks[0].offer.link,offer.link);
});
test('missing essential size/stock and changed stock never produce a fictional room',async()=>{
 let renders=0,judgments=0;const deps={detect:async()=>context,judge:async()=>++judgments===1?brief:layout,source:async()=>[],render:async()=>{renders++;}};
 await assert.rejects(designFromCatalog(original,{width:4,length:5,market:'KW'},deps),/ESSENTIAL_PIECES_MISSING/);assert.equal(renders,0);
 judgments=0;await assert.rejects(designFromCatalog(original,{width:4,length:5,market:'KW'},{...deps,source:async()=>[offer],stock:async o=>({...o,availability:'out_of_stock'})}),/STOCK_CHANGED/);assert.equal(renders,0);
});
const bytes=await sharp({create:{width:100,height:100,channels:3,background:'#abcdef'}}).jpeg().toBuffer();
test('confirmed local products stop the global fallback; unknown stock cannot qualify',async()=>{
 const queries=[];const deps={search:async(q,m)=>{queries.push(m);return {images:[{title:offer.title,link:offer.link,imageUrl:offer.image}]};},judge:async()=>({choices:[{index:0,score:95}]}),fetchImage:async()=>({bytes}),stock:async o=>({...o,availability:'listed_available',dimensions_cm:offer.dimensions_cm})};
 const found=await sourceCatalogItem({...item,query:'Olive chair'},original,{market:'KW'},deps);assert.equal(found.length,1);assert.ok(queries.every(m=>m==='KW'));
 queries.length=0;const empty=await sourceCatalogItem({...item,query:'Olive chair'},original,{market:'KW'},{...deps,stock:async o=>({...o,availability:'unknown',dimensions_cm:offer.dimensions_cm})});assert.equal(empty.length,0);assert.ok(queries.includes('US'));
});
test('renderer includes real product references and rejects a failed visual audit',async()=>{
 const out=await sharp({create:{width:600,height:500,channels:3,background:'#ccc'}}).jpeg().toBuffer();
 let imageCalls=0;const plan={...validateCatalogPlan(layout,[item],room),context,options:{notes:'Olive'}};
 const generate=async(parts,opts)=>{if(opts.image){imageCalls++;assert.equal(parts.filter(p=>p.inlineData).length,2);return {mimeType:'image/jpeg',data:out.toString('base64')};}return {room_geometry_unchanged:true,no_unselected_new_products:true,scale_plausible:true,items:[{id:'1',product_present:true,boxes:layout.choices[0].placements.map(x=>x.box)}]};};
 await assert.rejects(renderCatalogRoom(original,plan,{generate,fetchImage:async()=>({bytes}),verify:async()=>({ok:true}),audit:async()=>[]}),/PLACEMENT_UNVERIFIED/);assert.equal(imageCalls,2);
});

test('retrieval uses broad real-product categories across local stores before a style is rendered',()=>{
 const q=catalogSearchQueries({name_en:'Curved Sectional Sofa',specs:{category:'sofa',color:'cream'}},'KW');assert.equal(q.query,'sofa cream');assert.ok(q.queries.some(([query])=>query.includes('safathome.com')));assert.ok(q.queries.some(([query])=>query.includes('ikea.com/kw/')));assert.equal(catalogSearchQueries({name_en:'Travertine Coffee Table',specs:{color:'white'}},'KW',true).query,'coffee table');
});
