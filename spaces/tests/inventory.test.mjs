import test from 'node:test';
import assert from 'node:assert/strict';
import {normalizeInventory,identifyPieces,inventorySchema,inventoryRepairTarget} from '../inventory.mjs';
const row={name_en:'Beige sectional sofa',box:[300,200,900,800]};

test('visual objects survive a missing legacy query or standard detection response shape',()=>{
 assert.equal(normalizeInventory({items:[row]})[0].query,row.name_en);
 assert.equal(normalizeInventory([row])[0].name_en,row.name_en);
 const item=normalizeInventory({objects:[{label:'Chair',box_2d:[.1,.2,.6,.8]}]})[0];
 assert.deepEqual(item.box,[100,200,600,800]);assert.equal(item.name_en,'Chair');
 assert.equal(normalizeInventory({items:[{...row,mode:'keep'}]})[0].status,'idle');
 assert.equal(normalizeInventory({items:[{...row,mode:'keep'}]},{keep:'Keep sofa'})[0].status,'kept');
});

test('unusable boxes are rejected instead of inventing a crop or object',()=>{
 for(const box of [undefined,[],[1,2,3],[0,0,0,0],[100,100,NaN,500],[-1,10,500,900],[0,0,1200,900]])assert.equal(normalizeInventory({items:[{...row,box}]}).length,0);
 assert.equal(normalizeInventory({items:[null,{},'chair',{box:row.box}]}).length,0);
});

test('empty structured output gets one bounded corrective pass on the same image',async()=>{
 const photo={inlineData:{data:'same room'}};let calls=0;
 const items=await identifyPieces(photo,{judge:async(parts,options)=>{
  calls++;assert.equal(parts[1],photo);assert.equal(options.schemaFormat,'json');assert.equal(options.schema,inventorySchema);
  return calls===1?{items:[]}:[row];
 }});assert.equal(calls,2);assert.equal(items.length,1);
 calls=0;await assert.rejects(identifyPieces(photo,{judge:async()=>{calls++;return {items:[]};}}),/NO_ITEMS/);assert.equal(calls,2);
});

test('repair is confined to one explicitly selected failed empty design and runs once',()=>{
 const id='a'.repeat(24),failed={image:'design-1.png',items:[],error:'NO_ITEMS'};
 const jobs={[id]:{owner:'customer',designs:[{image:'design-0.png',items:[row]},failed]}};
 assert.equal(inventoryRepairTarget(jobs,id,'1').design,failed);
 for(const [room,index] of [[id,'0'],[id,'2'],[id,''],['b'.repeat(24),'1']])assert.equal(inventoryRepairTarget(jobs,room,index),null);
 failed.inventory_repair_version=1;assert.equal(inventoryRepairTarget(jobs,id,'1'),null);
});

test('an explicitly retail-free architectural concept finishes immediately, but malformed detections still fail',async()=>{
 let calls=0;
 assert.deepEqual(await identifyPieces({}, {judge:async()=>{calls++;return {items:[],no_retail_items:true};}}),[]);
 assert.equal(calls,1);
 for(const response of [{no_retail_items:true},{items:[{name_en:'Lamp'}],no_retail_items:true}])await assert.rejects(identifyPieces({}, {judge:async()=>response}),/NO_ITEMS/);
});

test('visible patches are validated and clipped to the named product instead of using an adjacent object',()=>{
 const [item]=normalizeInventory({items:[{name_en:'Desk',box:[200,200,800,800],selection_boxes:[[100,100,250,300],[300,300,500,500],[850,850,950,950],[NaN,0,1,2]]}]});
 assert.equal(item.category,'desk');assert.deepEqual(item.selection_boxes,[[200,200,250,300],[300,300,500,500]]);
});

test('inventory review corrects a sofa box and adds its separate desk without duplicate additions',async()=>{
 const {applyInventoryReview}=await import('../inventory.mjs');
 const items=normalizeInventory({items:[{name_en:'Sofa',box:[300,200,700,800]},{name_en:'Desk chair',box:[400,420,700,650]}]});
 const desk={name_en:'Desk',category:'desk',box:[350,200,700,850]};
 const revised=applyInventoryReview(items,{corrections:[{id:'1',box:[300,250,350,750],selection_boxes:[[300,250,350,750]]}],additions:[desk,desk]});
 assert.equal(revised.length,3);assert.deepEqual(revised[0].box,[300,250,350,750]);assert.equal(revised[1].name_en,'Desk chair');assert.equal(revised[2].name_en,'Desk');assert.equal(new Set(revised.map(x=>x.id)).size,3);
});

test('refresh keeps valid paid results and identifiers but cannot reuse a corrected wrong-object search',async()=>{
 const {retainInventoryResults}=await import('../inventory.mjs');
 const previous=normalizeInventory({items:[{name_en:'Sofa',box:[300,200,700,800]},{name_en:'Desk chair',box:[400,420,700,650]}]});
 previous[0].original_view={items:[{title:'wrong crop result'}]};previous[1].original_view={items:[{title:'Chair result'}]};
 previous[1].design_picks=[{url:'https://store.test/chair'}];
 const next=normalizeInventory({items:[{name_en:'Sofa',box:[300,250,350,750]},{name_en:'Desk chair',box:[400,420,700,650]},{name_en:'Desk',box:[350,200,700,850]}]});
 const result=retainInventoryResults(previous,next);
 assert.notEqual(result[0].id,'1');assert.equal(result[0].original_view,undefined);
 assert.equal(result[1].id,'2');assert.deepEqual(result[1].original_view,previous[1].original_view);assert.deepEqual(result[1].design_picks,previous[1].design_picks);
 assert.equal(new Set(result.map(x=>x.id)).size,3);
});
