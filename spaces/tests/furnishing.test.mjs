import test from 'node:test';
import assert from 'node:assert/strict';
import sharp from 'sharp';
import {centimetres,productDimensions,roomMeasurements,validateLayout,furnitureSlots,candidateMatchesKind} from '../room-fit.mjs';
import {furnishingQuote,furnishRoom,furnishingRepairTarget} from '../furnishing.mjs';
import {furnishingLanguages,furnishingText} from '../public/furnishing-copy.js';
import {readFurnishingMeasurements,furnishingArea} from '../public/furnishing.js';
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
test('optional sourcing is bounded, country-scoped and uses saved searches without another charge',()=>{
 const items=[{id:'1',name_en:'Sofa'},{id:'2',name_en:'Coffee table'},{id:'3',name_en:'Armchair'},{id:'4',name_en:'TV unit'},{id:'5',name_en:'Throw pillow'}];
 assert.equal(furnitureSlots(items).length,3);assert.equal(furnishingQuote({items},'KW').searches,3);
 items[0].furnishing_offers={KW:[{link:'https://shop.example/sofa',market_scope:'local',availability:'listed_available'}]};
 assert.equal(furnishingQuote({items},'KW').searches,2);assert.equal(furnishingQuote({items},'SA').searches,3);
});
test('a desk chair cannot replace a desk, and bedding cannot replace a bed frame',()=>{
 const slots=furnitureSlots([{id:'1',name_en:'Bed with linen bedding'},{id:'2',name_en:'Desk chair'},{id:'3',name_en:'Writing desk'},{id:'4',name_en:'Armchair'}]);
 assert.equal(slots.find(x=>x.kind==='table').item.id,'3');
 assert.equal(candidateMatchesKind('Textured throw blanket','bed'),false);
 assert.equal(candidateMatchesKind('Upholstered bed frame with storage','bed'),true);
 assert.equal(candidateMatchesKind('Kids desk chair','table'),false);
});
test('all supported locales include optional-flow copy and consistent search-credit placeholders',()=>{
 assert.equal(furnishingLanguages.length,17);
 for(const language of furnishingLanguages){for(const key of 'title teaser intro begin cost free depth products layout render verify ready estimate partial error missing demo areaLabel invalidMeasurements depthTitle depthNote layoutTitle'.split(' ')){const value=furnishingText(language,key,3);assert.ok(value&&value!==key,language+':'+key);}assert.equal((furnishingText(language,'cost',3).match(/3/g)||[]).length,2);assert.notEqual(furnishingText(language,'invalidMeasurements'),furnishingText(language,'intro'));}
 assert.equal(furnishingText('ar','title'),'التصميم والتنفيذ');
});
test('furnishing pipeline retains originals and rejects a misleading generated preview',async()=>{
 const bytes=await sharp({create:{width:800,height:600,channels:3,background:'#baa995'}}).jpeg().toBuffer();
 const image={mimeType:'image/jpeg',data:bytes.toString('base64')};
 const items=['Sofa','Coffee table'].map((name,i)=>({id:String(i+1),name_en:name,box:[100,100,800,800],furnishing_offers:{KW:[{link:'https://shop.example/product/'+i,image:'https://shop.example/image.jpg',title:name,market_scope:'local',availability:'listed_available'}]}}));
 const initial=JSON.stringify(items),phases=[],observations=[];
 const dependencies={depth:async()=>({png:bytes,model:'test',kind:'relative_depth'}),fetchImage:async()=>({bytes}),stock:async()=>({availability:'listed_available'}),audit:async(_,offers)=>offers,candidateReview:async()=>true,
  generate:async(parts,opts)=>opts.image?image:parts[0].text.startsWith('Audit')?{room_preserved:true,scale_plausible:true,openings_clear:true,products:[{id:'1',identity_preserved:true,box:[100,100,400,800]},{id:'2',identity_preserved:true,box:[500,100,800,800]}]}:layout};
 const input={original:bytes,concept:bytes,design:{items},room,market:'KW',owner:'test',details:{request:url=>({status:'ready',facts:url.endsWith('/0')?[f('width','210 cm'),f('depth','90 cm')]:[f('width','100 cm'),f('depth','60 cm')]})},discover:()=>{throw Error('unwanted paid search');},progress:p=>phases.push(p),onDepth:value=>observations.push({kind:value.kind,phase:phases.at(-1)}),onLayout:(value,products)=>observations.push({placements:value.placements.length,photos:products.some(p=>p.bytes),phase:phases.at(-1)})};
 const result=await furnishRoom(input,dependencies);assert.equal(result.products.length,2);assert.equal(JSON.stringify(items),initial);assert.deepEqual(phases,['depth','products','layout','render','verify']);
 assert.deepEqual(observations,[{kind:'relative_depth',phase:'depth'},{placements:2,photos:false,phase:'layout'}]);
 await assert.rejects(furnishRoom(input,{...dependencies,generate:async(parts,opts)=>parts[0].text.startsWith('Audit')?{room_preserved:false}:dependencies.generate(parts,opts)}),/PREVIEW_UNVERIFIED/);
 await assert.rejects(furnishRoom(input,{...dependencies,stock:async()=>({availability:'unknown'})}),/PRODUCTS_INCOMPLETE/);
});

test('one broken merchant page does not discard another real piece; partial preview is explicit',async()=>{
 const bytes=await sharp({create:{width:800,height:600,channels:3,background:'#baa995'}}).jpeg().toBuffer();
 const image={mimeType:'image/jpeg',data:bytes.toString('base64')};
 const items=['Sofa','Coffee table'].map((name,i)=>({id:String(i+1),name_en:name,box:[100,100,800,800],furnishing_offers:{KW:[{link:'https://shop.example/product/'+i,image:'https://shop.example/p.jpg',title:name,market_scope:'local',availability:'listed_available'}]}}));
 const result=await furnishRoom({original:bytes,concept:bytes,design:{items},room,market:'KW',owner:'test',details:{request:url=>{if(url.endsWith('/1'))throw Error('merchant unavailable');return {status:'ready',facts:[f('width','210 cm'),f('depth','90 cm')]};}},discover:()=>{throw Error('unwanted new search');},progress:()=>{}},{depth:async()=>({png:bytes,model:'test',kind:'relative_depth'}),fetchImage:async()=>({bytes}),stock:async()=>({availability:'listed_available'}),candidateReview:async()=>true,audit:async(_,offers)=>offers,generate:async(parts,options)=>options.image?image:parts[0].text.startsWith('Audit')?{room_preserved:true,scale_plausible:true,openings_clear:true,products:[{id:'1',identity_preserved:true,box:[100,100,800,800]}]}:{...layout,placements:[layout.placements[0]]}});
 assert.equal(result.products.length,1);assert.equal(result.partial,true);
});
