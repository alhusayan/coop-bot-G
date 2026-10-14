import test from 'node:test';
import assert from 'node:assert/strict';
import sharp from 'sharp';
import {centimetres,productDimensions,roomMeasurements,validateLayout,fitFurnitureLayout,layoutFeedback,furnitureSlots,candidateMatchesKind,furnitureInstances} from '../room-fit.mjs';
import {furnishingQuote,furnishRoom,furnishingRepairTarget,chooseRoomSet,previewProblems,furnishingPlan} from '../furnishing.mjs';
import {furnishingLanguages,furnishingText} from '../public/furnishing-copy.js';
import {readFurnishingMeasurements,furnishingArea,furnishingFailureKey} from '../public/furnishing.js';
import {parseHTML} from 'linkedom';
const f=(kind,value,label=kind)=>({kind,value,label,quote:label+': '+value,source:'merchant_page'});
test('support recovery only targets the selected failed run once, with saved local offers',()=>{
 const id='a'.repeat(24),run={status:'error',error:'FURNISH_PRODUCTS_INCOMPLETE',room:{width:500,length:700},market:'SA'},design={image:'design-2.jpg',furnishing:run,items:[{id:'4',name_en:'Sofa',furnishing_offers:{SA:[{title:'Sofa',link:'https://shop.example/sofa',market_scope:'local'}]}}]},jobs={[id]:{id,owner:'test',designs:[{}, {},design]}};
 assert.equal(furnishingRepairTarget(jobs,id+':2',1)?.index,2);
 assert.equal(furnishingRepairTarget(jobs,id+':0',1),null);assert.equal(furnishingRepairTarget(jobs,'b'.repeat(24)+':2',1),null);
 run.repair_version=1;assert.equal(furnishingRepairTarget(jobs,id+':2',1),null);
 run.status='ready';assert.equal(furnishingRepairTarget(jobs,id+':2',2),null);
 run.status='error';run.market='KW';assert.equal(furnishingRepairTarget(jobs,id+':2',2),null);
});
test('the customer’s 6 × 8 form sends length 8 rather than the controls collection length',()=>{
 const {document}=parseHTML('<form><input name="width" value="6"><input name="length" value="8"><button>Continue</button></form>'),form=document.querySelector('form');
 Object.defineProperty(form,'elements',{value:{length:3}});
 const payload=JSON.parse(JSON.stringify(readFurnishingMeasurements(form)));
 assert.deepEqual(payload,{width:6,length:8});assert.equal(furnishingArea(roomMeasurements(payload)),48);
 form.querySelector('[name="length"]').value='';assert.throws(()=>readFurnishingMeasurements(form),/MEASUREMENTS_REQUIRED/);
 form.querySelector('[name="length"]').value='٨٫٥';assert.equal(readFurnishingMeasurements(form).length,8.5);
 form.querySelector('[name="width"]').value='16';assert.throws(()=>readFurnishingMeasurements(form),/MEASUREMENTS_REQUIRED/);
});
test('merchant dimensions require explicit axes and units; component and conflicting dimensions are rejected',()=>{
 assert.equal(centimetres('٦٥ سم'),65);assert.equal(centimetres('30 in'),76.2);assert.equal(centimetres('2 m'),200);assert.equal(centimetres('70'),null);
 assert.deepEqual(productDimensions([f('dimensions','H72, W70, D64cm','Assembled dimensions')]),{width:70,depth:64,height:72,unit:'cm',evidence:['Assembled dimensions: H72, W70, D64cm']});
 assert.equal(productDimensions([f('dimensions','80 × 50 × 40 cm')]),null);
 const p=productDimensions([f('width','65 cm'),f('depth','80 cm'),f('height','78 cm'),f('height','40 cm','Seat height')]);assert.equal(p.height,78);
 assert.equal(productDimensions([f('width','65 cm'),f('width','70 cm'),f('depth','80 cm')]),null);
 assert.equal(productDimensions([f('width','65','Seat width'),f('depth','80 cm')]),null);
 assert.equal(productDimensions([f('diameter','80 cm'),f('height','40 cm')]).depth,80);
 assert.equal(productDimensions([f('dimensions','120 x 60 x 40 cm','W x D x H')]).width,120);
});
const room=roomMeasurements({width:5,length:6});
const products=[{id:'1',dimensions:{width:210,depth:90,height:80}},{id:'2',dimensions:{width:100,depth:60,height:40}}];
const layout={geometry_confidence:'high',placements:[{id:'1',x:100,z:20,rotation:0},{id:'2',x:150,z:160,rotation:0}],obstacles:[{x:0,z:500,width:100,depth:100,kind:'door'}],entry:{x:50,z:590}};
test('floor layout checks real footprints, boundaries, openings and a 60 cm path',()=>{
 assert.equal(validateLayout(layout,products,room).estimated,true);
 assert.throws(()=>validateLayout({...layout,geometry_confidence:'low'},products,room),/UNCERTAIN/);
 assert.throws(()=>validateLayout({...layout,placements:[layout.placements[0],{id:'2',x:150,z:30,rotation:0}]},products,room),/DOES_NOT_FIT/);
 assert.throws(()=>validateLayout({...layout,placements:[{id:'1',x:400,z:20,rotation:0},layout.placements[1]]},products,room),/DOES_NOT_FIT/);
 assert.throws(()=>validateLayout({...layout,obstacles:[{x:120,z:20,width:50,depth:100,kind:'door'}]},products,room),/DOES_NOT_FIT/);
 assert.throws(()=>roomMeasurements({width:0,length:6}),/MEASUREMENTS/);
});
test('overlapping model positions are repaired without moving doors or changing product sizes',()=>{
 const bad={...layout,placements:[layout.placements[0],{...layout.placements[1],z:30}]},before=JSON.stringify(bad);
 const fixed=fitFurnitureLayout(bad,products,room);
 assert.equal(fixed.positions_adjusted,true);assert.equal(fixed.placements.length,2);
 assert.deepEqual(fixed.entry,bad.entry);assert.equal(fixed.obstacles[0].x,bad.obstacles[0].x);assert.equal(fixed.obstacles[0].w,bad.obstacles[0].width);assert.equal(JSON.stringify(bad),before);
 assert.equal(validateLayout({...bad,placements:fixed.placements},products,room).estimated,true);
 assert.throws(()=>fitFurnitureLayout({...bad,geometry_confidence:'low'},products,room),/UNCERTAIN/);
 assert.throws(()=>fitFurnitureLayout(bad,[{...products[0],dimensions:{width:700,depth:700}},products[1]],room),/DOES_NOT_FIT/);
});
test('an appearance rejection is not described as missing dimensions or unavailable stock',()=>{
 assert.equal(furnishingFailureKey({error:'FURNISH_PRODUCTS_INCOMPLETE',diagnostics:[{incompatible:4}]}),'incompatible');
 assert.equal(furnishingFailureKey({error:'FURNISH_PRODUCTS_INCOMPLETE',diagnostics:[{missing_dimensions:2}]}),'missing');
 assert.equal(furnishingFailureKey({error:'FURNITURE_DOES_NOT_FIT'}),'error');
 for(const language of furnishingLanguages)assert.notEqual(furnishingText(language,'incompatible'),'incompatible');
});
test('a desk chair cannot replace a desk, and bedding cannot replace a bed frame',()=>{
 const slots=furnitureSlots([{id:'1',name_en:'Bed with linen bedding'},{id:'2',name_en:'Desk chair'},{id:'3',name_en:'Writing desk'},{id:'4',name_en:'Armchair'}]);
 assert.equal(slots.find(x=>x.kind==='table').item.id,'3');
 assert.equal(candidateMatchesKind('Textured throw blanket','bed'),false);
 assert.equal(candidateMatchesKind('Upholstered bed frame with storage','bed'),true);
 assert.equal(candidateMatchesKind('Kids desk chair','table'),false);
 assert.equal(candidateMatchesKind('احصل على طاولة قهوة راقية خشبية مودرن','sofa'),false);
 assert.equal(candidateMatchesKind('كرسي مكتب','table'),false);
 assert.equal(candidateMatchesKind('بطانية سرير','bed'),false);
 assert.equal(candidateMatchesKind('كنب زاوية مع وسائد','sofa'),true);
});
test('all supported locales include optional-flow copy and consistent search-credit placeholders',()=>{
 assert.equal(furnishingLanguages.length,17);
 for(const language of furnishingLanguages){for(const key of 'title teaser intro begin cost free depth products layout render verify ready estimate partial error missing demo areaLabel invalidMeasurements depthTitle depthNote layoutTitle'.split(' ')){const value=furnishingText(language,key,3);assert.ok(value&&value!==key,language+':'+key);}assert.equal((furnishingText(language,'cost',3).match(/3/g)||[]).length,2);assert.notEqual(furnishingText(language,'invalidMeasurements'),furnishingText(language,'intro'));}
 assert.equal(furnishingText('ar','title'),'التصميم والتنفيذ');
});

test('all furniture types and repeated quantities are included without a three-kind cap',()=>{
 const items=['Sofa','Coffee table','Dining table','Dining chair','Sideboard','Rug','Table lamp'].map((name,i)=>({id:String(i+1),name_en:name,quantity:i===3?4:1}));
 const slots=furnitureSlots([...items,{id:'9',name_en:'Sofa',mode:'keep'},{id:'10',name_en:'Curtains',mode:'measure'},{id:'11',name_en:'Throw pillow'}]);
 assert.equal(slots.length,7);assert.equal(slots.filter(x=>x.kind==='table').length,2);
 assert.equal(slots.find(x=>x.item.id==='7').layer,'surface');
 const quote=furnishingQuote({items},'KW');assert.equal(quote.items.length,7);assert.equal(quote.quantity,10);assert.equal(quote.searches,6);
 items[0].furnishing_offers={KW:[{title:'Sofa',link:'https://shop.example/sofa',market_scope:'local'}]};
 assert.equal(furnishingQuote({items},'KW').saved,1);assert.equal(furnishingQuote({items},'SA').saved,0);
 assert.equal(furnishingQuote({items},'KW').searches,6,'saved candidates can need one disclosed fallback search');
 const instances=furnitureInstances([{id:'chair',quantity:4,dimensions:{width:50,depth:60}}]);assert.deepEqual(instances.map(p=>p.id),['chair.1','chair.2','chair.3','chair.4']);
});
const completeRoom=roomMeasurements({width:8,length:8});
const names=['Sofa','Coffee table','Dining table','Dining chair','Sideboard','Rug','Table lamp'];
const sizes=[[210,90],[100,60],[180,90],[50,50],[120,40],[300,300],[20,20]];
const completeLayout={geometry_confidence:'high',entry:{x:750,z:790},obstacles:[{x:700,z:700,width:80,depth:100,kind:'door'}],placements:[
 {id:'1',x:100,z:50,rotation:0},{id:'2',x:100,z:200,rotation:0},{id:'3',x:400,z:50,rotation:0},
 {id:'4.1',x:420,z:170,rotation:0},{id:'4.2',x:500,z:170,rotation:0},{id:'5',x:10,z:400,rotation:0},
 {id:'6',x:50,z:30,rotation:0},{id:'7',x:35,z:405,rotation:0,on:'5'}]};
async function fixture(){
 const bytes=await sharp({create:{width:800,height:600,channels:3,background:'#baa995'}}).jpeg().toBuffer(),image={mimeType:'image/jpeg',data:bytes.toString('base64')};
 const items=names.map((name,i)=>({id:String(i+1),name_en:name,quantity:i===3?2:1,box:[100,100,800,800],furnishing_offers:{KW:[0,1].map(n=>({title:name+' option '+n,link:'https://shop.example/product/'+i+'/'+n,image:'https://shop.example/photo.jpg',market_scope:'local',availability:'listed_available'}))}}));
 const phases=[],events=[],requests=[],renders=[];
 const review={room_preserved:true,scale_plausible:true,openings_clear:true,cohesive_design:true,all_furniture_accounted_for:true,unlisted_furniture:[],products:items.map(p=>({id:p.id,identity_preserved:true,quantity:p.quantity,boxes:Array.from({length:p.quantity},(_,i)=>[100+i*300,100,350+i*300,400])}))};
 const input={original:bytes,concept:bytes,design:{items},room:completeRoom,market:'KW',owner:'test',details:{request:url=>{const i=Number(url.split('/').at(-2));return {status:'ready',facts:[f('width',sizes[i][0]+' cm'),f('depth',sizes[i][1]+' cm')]};}},discover:async item=>{requests.push(item.id);return [];},progress:x=>phases.push(x),onSelection:(products,diagnostics,coverage)=>events.push({products,diagnostics,coverage})};
 const deps={fetchImage:async()=>({bytes}),stock:async()=>({availability:'listed_available'}),audit:async(_,offers)=>offers,candidateReview:async item=>({units_per_offer:item.id==='4'?2:1}),generate:async(parts,options)=>{
  if(options.image){renders.push(parts[0].text);return image;}
  if(parts[0].text.startsWith('Act as'))return {selections:items.map(p=>({id:p.id,candidate:p.id==='1'?1:0})),design_direction:'Warm oak, ivory and olive; balanced layered lighting.'};
  if(parts[0].text.startsWith('Audit'))return structuredClone(review);
  return structuredClone(completeLayout);
 }};
 return {bytes,items,phases,events,requests,renders,review,input,deps};
}
test('complete pipeline coordinates real alternatives, preserves quantities and validates rug/table-lamp layers',async()=>{
 const x=await fixture(),before=JSON.stringify(x.items),result=await furnishRoom(x.input,x.deps);
 assert.equal(result.products.length,7);assert.equal(result.partial,false);assert.equal(result.version,2);assert.equal(result.layout.placements.length,8);
 assert.equal(result.products[0].offer.link,'https://shop.example/product/0/1');
 assert.equal(result.products[3].quantity,2);assert.equal(result.products[3].purchase_quantity,1);
 assert.equal(result.coverage.quantity,8);assert.deepEqual(result.coverage.missing,[]);assert.equal(x.requests.length,0);
 assert.equal(JSON.stringify(x.items),before);assert.deepEqual(x.phases,['products','curate','layout','render','verify']);
 assert.ok(!result.products.some(p=>p.bytes));assert.match(x.renders[0],/Do not invent extra sofas/);
 const instances=furnitureInstances(result.products);assert.equal(validateLayout(completeLayout,instances,completeRoom).placements.length,8);
 const bad=structuredClone(completeLayout);bad.placements.at(-1).x=600;assert.throws(()=>validateLayout(bad,instances,completeRoom),/DOES_NOT_FIT/);
});
test('missing furniture triggers one fallback and blocks a misleading partial room',async()=>{
 const x=await fixture();x.input.details.request=url=>url.includes('/2/')?{status:'ready',facts:[]}:{status:'ready',facts:[f('width','50 cm'),f('depth','50 cm')]};
 await assert.rejects(furnishRoom(x.input,x.deps),/PRODUCTS_INCOMPLETE/);
 assert.deepEqual(x.requests,['3']);assert.equal(x.renders.length,0);assert.deepEqual(x.events.at(-1).coverage.missing,[{id:'3',name:'Dining table'}]);
 assert.equal(x.events.at(-1).products.length,6);
});
test('failed saved offers are replaced by a new authorized search before rendering',async()=>{
 const x=await fixture(),old=x.input.details.request;
 x.input.details.request=url=>url.includes('/2/')&&!url.endsWith('/fresh')?{status:'ready',facts:[]}:old(url);
 x.input.discover=async item=>{x.requests.push(item.id);return [{...item.furnishing_offers.KW[0],link:'https://shop.example/product/2/fresh'}];};
 const result=await furnishRoom(x.input,x.deps);assert.deepEqual(x.requests,['3']);assert.ok(result.products.find(p=>p.id==='3').offer.link.endsWith('/fresh'));
});
test('extra invented furniture is corrected once; persistent missing copies cannot pass',async()=>{
 const x=await fixture(),base=x.deps.generate;let audits=0;
 x.deps.generate=async(parts,opts)=>{if(parts[0].text.startsWith('Audit')&&audits++===0)return {...x.review,all_furniture_accounted_for:false,unlisted_furniture:['unlisted armchair']};return base(parts,opts);};
 const result=await furnishRoom(x.input,x.deps);assert.equal(result.partial,false);assert.equal(x.renders.length,2);assert.match(x.renders[1],/unlisted armchair/);
 const y=await fixture();y.review.products[3].quantity=1;
 await assert.rejects(furnishRoom(y.input,y.deps),/PREVIEW_UNVERIFIED/);assert.equal(y.renders.length,2);
});
test('curation cannot omit, duplicate, or invent a product candidate',()=>{
 const groups=[{item:{id:'1'},candidates:[{id:'1'}]},{item:{id:'2'},candidates:[{id:'2'}]}];
 for(const selections of [[{id:'1',candidate:0}],[{id:'1',candidate:0},{id:'1',candidate:0}],[{id:'1',candidate:0},{id:'2',candidate:2}]])assert.throws(()=>chooseRoomSet(groups,{selections}),/SELECTION_UNVERIFIED/);
});
test('all supported languages explain the complete flow and quantities',()=>{
 for(const lang of furnishingLanguages)for(const key of ['curate','completeNote','legacy','schedule','packs','unitsPerPack'])assert.notEqual(furnishingText(lang,key,4),key,lang+':'+key);
});

test('merchant suffix axes, arbitrary labeled order and flat rugs preserve explicit evidence',()=>{
 assert.deepEqual(productDimensions([f('dimensions','200cm (W) x 95cm (D) x 75cm (H)')]).width,200);
 assert.equal(productDimensions([f('dimensions','75 x 95 x 200 cm','H x D x W')]).width,200);
 assert.equal(productDimensions([f('dimensions','H: 58 cm, Dia: 35 cm')]).width,35);
 assert.equal(productDimensions([f('dimensions','Height 58 cm, Diameter 35 cm')]).depth,35);
 assert.equal(productDimensions([f('dimensions','160 x 230 cm')],'rug').depth,230);
 assert.equal(productDimensions([f('dimensions','160 cm x 230 cm')],'rug').width,160);
 assert.equal(productDimensions([f('dimensions','160 x 230 cm')],'table'),null);
 assert.equal(productDimensions([f('dimensions','160 x 230 x 80 cm')],'rug'),null);
});
test('repeated dining chairs share one search and retain every requested copy',()=>{
 const items=[{id:'1',name_en:'Sofa'},...['2','3','4'].map((id,i)=>({id,name_en:'Dining chair',quantity:i===1?2:1})),{id:'5',name_en:'Armchair'},{id:'6',name_en:'Dining table'},{id:'7',name_en:'Table lamp'}];
 const plan=furnishingPlan({items}),chairs=plan.find(p=>p.item.id==='2');
 assert.equal(chairs.quantity,4);assert.equal(chairs.members.length,3);assert.equal(chairs.required,true);
 assert.equal(plan.find(p=>p.item.id==='5').required,false);assert.equal(plan.find(p=>p.item.id==='7').required,false);
 const quote=furnishingQuote({items},'GB');assert.equal(quote.searches,5);assert.equal(quote.quantity,8);
});
test('credit exhaustion and missing accents still produce a fully sourced living/dining collection',async()=>{
 const x=await fixture(),details=x.input.details.request,base=x.deps.generate;
 x.items.push({id:'11',name_en:'Dining chair',quantity:2,box:[100,100,800,800]});
 x.input.details.request=url=>/\/product\/[456]\//.test(url)?{status:'ready',facts:[]}:details(url);
 x.input.discover=async item=>{x.requests.push(item.id);throw Error('credits_exhausted');};
 const proposal=structuredClone(completeLayout);proposal.placements=proposal.placements.filter(p=>!['5','6','7'].includes(p.id));proposal.placements.push({id:'4.3',x:420,z:270,rotation:0},{id:'4.4',x:500,z:270,rotation:0});
 x.review.products=x.review.products.filter(p=>!['5','6','7'].includes(p.id));
 Object.assign(x.review.products.find(p=>p.id==='4'),{quantity:4,boxes:Array.from({length:4},(_,i)=>[i*200,100,i*200+150,400])});
 x.deps.generate=async(parts,opts)=>{
  if(parts[0].text.startsWith('Act as'))return {selections:['1','2','3','4'].map(id=>({id,candidate:0})),design_direction:'Coordinated seating and dining, without unsourced accents.'};
  if(parts[0].text.startsWith('Plan'))return proposal;
  return base(parts,opts);
 };
 const result=await furnishRoom(x.input,x.deps);
 assert.equal(result.products.length,4);assert.equal(result.products.find(p=>p.id==='4').quantity,4);assert.equal(result.layout.placements.length,7);
 assert.deepEqual(result.coverage.missing,[]);assert.equal(result.coverage.omitted.length,3);assert.equal(result.coverage.stop_reason,'credits_exhausted');
 assert.equal(x.requests.length,1,'never send more paid searches after the first credit failure');assert.equal(result.partial,false);
 assert.deepEqual(result.products.find(p=>p.id==='4').source_item_ids,['4','11']);
 assert.match(x.renders[0],/Replace\/remove ALL other imagined concept furniture/);
});
test('fresh verified source stock is reused without redundant merchant requests',async()=>{
 const x=await fixture();for(const item of x.items)for(const o of item.furnishing_offers.KW)Object.assign(o,{search_engine:'findzia-original',stock_checked_at:new Date().toISOString()});
 let requests=0;x.deps.stock=async()=>{requests++;throw Error('should reuse fresh stock');};
 assert.equal((await furnishRoom(x.input,x.deps)).products.length,7);assert.equal(requests,0);
});
test('credit failures are explained accurately and optional adaptation is translated',()=>{
 assert.equal(furnishingFailureKey({error:'FURNISH_PRODUCTS_INCOMPLETE',coverage:{stop_reason:'credits_exhausted'}}),'credits');
 for(const lang of furnishingLanguages)for(const key of ['adaptivePlan','adapted','credits'])assert.notEqual(furnishingText(lang,key),key);
});

test('prefix dimensions are not also misread as suffixes of the preceding axis',()=>{
 for(const value of ['W200 cm D100 cm H75 cm','Width: 200 cm Depth: 100 cm Height: 75 cm','W200 D100 H75cm']){
  const dimensions=productDimensions([f('dimensions',value)]);assert.equal(dimensions.width,200,value);assert.equal(dimensions.depth,100,value);assert.equal(dimensions.height,75,value);
 }
});

test('a verified standalone merchant alternative completes the core set without another paid image search',async()=>{
 const x=await fixture(),original=x.input.details.request,persisted=[];
 x.input.details.request=url=>url.includes('/2/')?{status:'ready',facts:[]}:original(url);
 x.input.onCatalogue=(item,rows)=>persisted.push([item.id,rows]);
 x.deps.catalogue=async item=>item.id==='3'?[{...item.furnishing_offers.KW[0],link:'https://shop.example/standalone-table',merchant_facts:[f('width','180 cm'),f('depth','90 cm')]}]:[];
 const result=await furnishRoom(x.input,x.deps);assert.equal(result.products.length,7);assert.equal(x.requests.length,0);assert.equal(persisted.length,1);assert.equal(result.products.find(p=>p.id==='3').offer.link,'https://shop.example/standalone-table');
});
test('whole-room chair clearance is corrected locally without scattering the dining group',()=>{
 const room={width:600,length:800},products=[{id:'table',kind:'table',dimensions:{width:180,depth:90}},...Array.from({length:4},(_,i)=>({id:'chair'+i,kind:'chair',dimensions:{width:55,depth:60}})),{id:'sofa',kind:'sofa',dimensions:{width:240,depth:95}}];
 const raw={geometry_confidence:'high',entry:{x:50,z:790},obstacles:[],placements:[{id:'table',x:180,z:200,rotation:0},{id:'chair0',x:190,z:135,rotation:180},{id:'chair1',x:285,z:135,rotation:180},{id:'chair2',x:190,z:295,rotation:0},{id:'chair3',x:285,z:295,rotation:0},{id:'sofa',x:180,z:500,rotation:0}]};
 assert.throws(()=>validateLayout(raw,products,room),/DOES_NOT_FIT/);
 const feedback=layoutFeedback(raw,products,room);assert.equal(feedback.issues.filter(x=>x.type==='furniture_clearance').length,4);
 const fixed=fitFurnitureLayout(raw,products,room);assert.equal(fixed.positions_adjusted,true);assert.equal(fixed.placements.length,6);
 for(const p of fixed.placements){const old=raw.placements.find(x=>x.id===p.id);assert.equal(p.rotation,old.rotation);assert.ok(Math.abs(p.x-old.x)<=40&&Math.abs(p.z-old.z)<=40);}
 assert.deepEqual(fixed.entry,raw.entry);assert.equal(validateLayout({...raw,placements:fixed.placements},products,room).estimated,true);
});
