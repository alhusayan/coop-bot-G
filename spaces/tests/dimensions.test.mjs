import test from 'node:test';
import assert from 'node:assert/strict';
import {centimetres,dimensionsFromPage,dimensionsFromProduct,fitSize,roomMeasurements,measuredLimits} from '../dimensions.mjs';
const size={width:80,depth:85,height:90},room={width_cm:400,length_cm:500};
test('store units are converted without guessing unlabelled units or mattress title sizes',()=>{
 assert.equal(centimetres('20 inches'),50.8);assert.equal(centimetres({value:800,unitCode:'MMT'}),80);assert.equal(centimetres('١٫٥','m'),150);assert.equal(centimetres('80'),null);
 assert.deepEqual(dimensionsFromProduct({width:'80 cm',depth:{value:85,unitText:'cm'},additionalProperty:{name:'Height (cm)',value:90}}),size);
 assert.deepEqual(dimensionsFromPage('<h1>Bed 120 x 200 cm</h1><p>Package Width (cm) 999</p>'),{});
 assert.deepEqual(dimensionsFromPage('<h2>Product Dimensions</h2>Width (cm) 80 Depth (cm) 85 Height (cm) 90 <h2>Packaging</h2>Width (cm) 999'),size);
 assert.deepEqual(dimensionsFromPage('Product Dimensions Width: 80 cm Depth: 85 cm Height: 90 cm'),size);
 assert.deepEqual(dimensionsFromPage('Product Dimensions Dimensions (cm) (LxWxH) 85 x 80 x 90'),size);
});
test('fit screening rejects oversized, uncertain and materially different-sized furniture',()=>{
 const slot={confidence:90,space:{width:90,depth:95,height:100},target:size};
 assert.equal(fitSize(size,slot,room).status,'estimated');assert.equal(fitSize(size,slot,room).size_verified,false);
 assert.equal(fitSize({...size,width:91},slot,room).ok,false);
 assert.equal(fitSize({...size,width:40},slot,room).ok,false);
 assert.equal(fitSize(size,{...slot,confidence:undefined},room).ok,false);
 assert.equal(fitSize(size,null,room,{width:90,depth:95,height:100}).status,'measured_envelope');
 assert.equal(fitSize({...size,width:600},null,room,{width:700,depth:95,height:100}).ok,false);
 assert.equal(fitSize({width:80,depth:85},slot,room).ok,false);
 assert.throws(()=>roomMeasurements({width:0,length:5}),/ROOM_SIZE_REQUIRED/);
 assert.deepEqual(roomMeasurements({width:'4.2',length:'5'}),{width_cm:420,length_cm:500});
 assert.throws(()=>measuredLimits({'1':{width:90}},[{id:'1'}]),/INVALID_MEASUREMENTS/);
});
