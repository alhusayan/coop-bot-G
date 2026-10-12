import test from 'node:test';
import assert from 'node:assert/strict';
import sharp from 'sharp';
import {compositeRegion,repairRegion,regionBoxes,repairCatalogProduct} from '../localized-render.mjs';
const base=await sharp({create:{width:600,height:500,channels:3,background:'#abcdef'}}).jpeg().toBuffer();
const boxes=[[300,150,700,450],[300,550,700,850]],offer={title:'Real olive chair',dimensions_cm:{width:80,depth:85,height:90}};
const reference={pick:{id:'1',name:'Chair',quantity:2,offer},bytes:base,part:{inlineData:{mimeType:'image/jpeg',data:base.toString('base64')}}};
test('compositing preserves every pixel outside its repair region and refuses changed framing',async()=>{
 const region={left:120,top:130,width:300,height:250},patch=await sharp({create:{width:300,height:250,channels:3,background:'#123456'}}).png().toBuffer();
 const output=await compositeRegion(base,patch,region),before=await sharp(base).removeAlpha().raw().toBuffer(),after=await sharp(output).removeAlpha().raw().toBuffer();
 let changed=0;
 for(let y=0;y<500;y++)for(let x=0;x<600;x++){const i=(y*600+x)*3,inside=x>=120&&x<420&&y>=130&&y<380;if(!inside)assert.deepEqual(after.subarray(i,i+3),before.subarray(i,i+3));else if(!after.subarray(i,i+3).equals(before.subarray(i,i+3)))changed++;}
 assert.equal(changed,300*250);
 await assert.rejects(compositeRegion(base,await sharp(patch).resize(300,100).png().toBuffer(),region),/REPAIR_FRAMING_CHANGED/);
});
test('local edit rejects collateral changes and wrong copy count before accepting any image',async()=>{
 for(const fault of ['other_items_unchanged','quantity']){
  let images=0,audits=0;
  const generate=async(parts,opts)=>{
   if(opts.image){images++;const bytes=await sharp(Buffer.from(parts[1].inlineData.data,'base64')).resize({width:1200}).jpeg().toBuffer();return {mimeType:'image/jpeg',data:bytes.toString('base64')};}
   const region=repairRegion(boxes,600,500),found=regionBoxes(boxes,region,600,500);
   return {other_items_unchanged:fault!=='other_items_unchanged',room_geometry_unchanged:true,framing_unchanged:true,product_present:true,boxes:fault==='quantity'?[]:found.slice(0,1)};
  };
  await assert.rejects(repairCatalogProduct(base,{...reference,pick:{...reference.pick,quantity:1}},[boxes[0]],{generate,audit:async()=>{audits++;return [offer];}}),/LOCAL_REPAIR_UNVERIFIED/);
  assert.equal(images,2);assert.equal(audits,0);
 }
});
test('every repeated copy passes a product audit and crop boxes map back to full-room coordinates',async()=>{
 let audits=0;
 const result=await repairCatalogProduct(base,reference,boxes,{generate:async(parts,opts)=>{
  if(opts.image){const bytes=await sharp(Buffer.from(parts[1].inlineData.data,'base64')).resize({width:1200}).jpeg().toBuffer();return {mimeType:'image/jpeg',data:bytes.toString('base64')};}
  return {other_items_unchanged:true,room_geometry_unchanged:true,framing_unchanged:true,product_present:true,boxes:regionBoxes(boxes,repairRegion(boxes,600,500),600,500)};
 },audit:async()=>{audits++;return [offer];}});
 assert.equal(audits,2);assert.equal(result.mimeType,'image/png');
 for(let n=0;n<2;n++)for(let k=0;k<4;k++)assert.ok(Math.abs(result.boxes[n][k]-boxes[n][k])<.001);
});
test('failed group edits correct copies individually and checkpoint only approved patches',async()=>{
 let images=0,audits=0,saved=0,fullChecks=0;
 const result=await repairCatalogProduct(base,reference,boxes,{generate:async(parts,opts)=>{
  if(opts.image){images++;const bytes=await sharp(Buffer.from(parts[1].inlineData.data,'base64')).resize({width:1200}).jpeg().toBuffer();return {mimeType:'image/jpeg',data:bytes.toString('base64')};}
  const selected=images===1?boxes:[boxes[images-2]];
  return {other_items_unchanged:true,room_geometry_unchanged:true,framing_unchanged:true,product_present:images>1,boxes:regionBoxes(selected,repairRegion(selected,600,500),600,500)};
 },audit:async()=>++audits%2===0?[offer]:[],validatePatch:async()=>{fullChecks++;return {ok:true};},onPatch:()=>saved++});
 assert.equal(images,3);assert.equal(audits,4);assert.equal(fullChecks,2);assert.equal(saved,2);assert.equal(result.boxes.length,2);assert.deepEqual(result.remaining,[]);
});
test('a full-room collateral change rejects an otherwise valid local patch',async()=>{
 let fullChecks=0;
 await assert.rejects(repairCatalogProduct(base,{...reference,pick:{...reference.pick,quantity:1}},[boxes[0]],{generate:async(parts,opts)=>{
  if(opts.image){const bytes=await sharp(Buffer.from(parts[1].inlineData.data,'base64')).resize({width:1200}).jpeg().toBuffer();return {mimeType:'image/jpeg',data:bytes.toString('base64')};}
  return {other_items_unchanged:true,room_geometry_unchanged:true,framing_unchanged:true,product_present:true,boxes:regionBoxes([boxes[0]],repairRegion([boxes[0]],600,500),600,500)};
 },audit:async()=>[offer],validatePatch:async()=>{fullChecks++;return {ok:false,issues:['Extra table created outside the crop context']};}}),/LOCAL_REPAIR_UNVERIFIED/);
 assert.equal(fullChecks,2);
});
