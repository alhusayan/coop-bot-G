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
