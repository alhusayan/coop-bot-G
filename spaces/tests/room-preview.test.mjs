import test from 'node:test';
import assert from 'node:assert/strict';
import sharp from 'sharp';
import {createRoomPreview,checkPreviewBoxes} from '../room-preview.mjs';
const bytes=await sharp({create:{width:1000,height:800,channels:3,background:'#bbaa99'}}).jpeg().toBuffer(),room={inlineData:{mimeType:'image/jpeg',data:bytes.toString('base64')}};
const views=[{box:[100,20,700,430]},{box:[100,570,700,980]}],offer={title:'Olive chair',image:'https://example.com/chair.jpg',dimensions_cm:{width:80,depth:80,height:90}};
const picks=[{id:'1',name:'Chair',views,offer}],check={other_items_unchanged:true,room_geometry_unchanged:true,scale_plausible:true,items:[{id:'1',product_present:true,boxes:views.map(x=>x.box)}]};
test('room preview verifies both copies and fails closed on product or room changes',async()=>{
 let audits=0;const deps={generate:async(_,opts)=>opts.image?room.inlineData:check,fetchImage:async()=>({bytes}),audit:async()=>{audits++;return [offer];}};
 const result=await createRoomPreview(room,{picks,room:{width_cm:400,length_cm:500}},deps);assert.equal(audits,2);assert.equal(result.boxes['1'].length,2);
 await assert.rejects(createRoomPreview(room,{picks}, {...deps,audit:async()=>[]}),/PLACEMENT_UNVERIFIED/);
 assert.throws(()=>checkPreviewBoxes({...check,scale_plausible:false},picks),/PLACEMENT_UNVERIFIED/);
 assert.throws(()=>checkPreviewBoxes({...check,items:[{...check.items[0],boxes:[views[0].box]}]},picks),/PLACEMENT_UNVERIFIED/);
 assert.throws(()=>checkPreviewBoxes({...check,items:[{...check.items[0],boxes:[views[0].box,views[0].box]}]},picks),/PLACEMENT_UNVERIFIED/);
});
