import test from 'node:test';
import assert from 'node:assert/strict';
import sharp from 'sharp';
import {adaptPiece} from '../adaptation.mjs';
const bytes=await sharp({create:{width:1000,height:800,channels:3,background:'#bbaa99'}}).jpeg().toBuffer();
const room={inlineData:{data:bytes.toString('base64'),mimeType:'image/jpeg'}};
const item={name_en:'Bedside table',box:[200,200,600,600]},offer={title:'Real oak bedside table',image:'https://shop.example/table.jpg'};
test('a replacement is committed only after scene preservation and actual-product visual verification',async()=>{
 const deps={fetchImage:async()=>({bytes}),generate:async(_,options)=>options.image?room.inlineData:{other_items_unchanged:true,room_geometry_unchanged:true,product_present:true,box:item.box},audit:async()=>[{...offer,match:'visual'}]};
 const output=await adaptPiece(room,item,offer,deps);assert.equal(output.offer.match,'placed_product');assert.equal(output.offer.size_verified,false);
 await assert.rejects(adaptPiece(room,item,offer,{...deps,audit:async()=>[]}),/PLACEMENT_UNVERIFIED/);
 await assert.rejects(adaptPiece(room,item,offer,{...deps,generate:async(_,options)=>options.image?room.inlineData:{other_items_unchanged:false,room_geometry_unchanged:true,product_present:true,box:item.box}}),/PLACEMENT_UNVERIFIED/);
});
