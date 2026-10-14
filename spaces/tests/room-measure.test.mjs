import test from 'node:test';
import assert from 'node:assert/strict';
import {calibratedMeasurement,validatePoints,suggestMeasurementPoints} from '../room-measure.mjs';
import {measurementText} from '../public/room-measure-copy.js';
import {furnishingLanguages} from '../public/furnishing-copy.js';
// Synthetic pinhole scene: a square seen diagonally. A-B and B-C are
// both 2m, all corners inside the image. This checks 3D distance recovery,
// not the neural model's real-world accuracy.
const size=392,f=size/(2*Math.tan(65*Math.PI/360));
const xyz=[[-Math.SQRT2,1,4+Math.SQRT2],[0,1,4],[Math.SQRT2,1,4+Math.SQRT2]];
const points=xyz.map(([x,y,z])=>[.5+x*f/z/size,.5+y*f/z/size]);
function fixture(){
 const values=new Float32Array(size*size).fill(5);
 points.forEach((p,i)=>{const x=Math.round(p[0]*(size-1)),y=Math.round(p[1]*(size-1));for(let dy=-4;dy<=4;dy++)for(let dx=-4;dx<=4;dx++)values[(y+dy)*size+x+dx]=xyz[i][2];});
 return {values,size,width:size,height:size,left:0,top:0,source_width:size,source_height:size,model:'test-metric',kind:'metric_depth'};
}
test('calibrated metric depth recovers a known perpendicular dimension rather than multiplying two user inputs',()=>{
 const result=calibratedMeasurement(fixture(),points,4);
 assert.equal(result.width,400);assert.equal(result.length,400);assert.equal(result.area_m2,16);
 assert.equal(result.source,'ai_calibrated');assert.equal(result.accuracy_validated,false);assert.equal(result.scope,'selected_visible_area');
 const doubled=calibratedMeasurement(fixture(),points,8);assert.equal(doubled.length,800);
});
test('measurement refuses invalid, short, missing and non-rectangular selections',()=>{
 assert.throws(()=>validatePoints([[0,0],[0,0],[1,1]]),/TOO_CLOSE/);
 assert.throws(()=>validatePoints([[0,0],[1,1],[2,2]]),/POINTS_REQUIRED/);
 assert.throws(()=>calibratedMeasurement(fixture(),points,0),/REFERENCE_REQUIRED/);
 assert.throws(()=>calibratedMeasurement(fixture(),[[.1,.2],[.5,.2],[.9,.2]],4),/NOT_RECTANGULAR/);
});
test('no hidden room corners are fabricated when vision cannot see the boundaries',async()=>{
 const result=await suggestMeasurementPoints(Buffer.from('image'),{generate:async()=>({points:[]})});assert.deepEqual(result,[]);
});
test('measurement instructions are present in all supported languages',()=>{
 for(const lang of furnishingLanguages)for(const key of ['title','intro','reference','loading','calculate','use','reset','note','problem','unavailable','area','ready'])assert.notEqual(measurementText(lang,key),key);
});

test('measurement UI sends one reference, applies server dimensions, and ignores a stale calculation after editing',async()=>{
 const {parseHTML}=await import('linkedom');const {createRoomMeasure}=await import('../public/room-measure.js');
 const {document,Event}=parseHTML('<main id="sheet"></main>');globalThis.document=document;
 const job={id:'a'.repeat(24),original:'/room.jpg'},applied=[],requests=[];
 let release;
 const measure=createRoomMeasure({context:()=>({job}),language:()=> 'ar',escape:String,safe:String,onUse:r=>applied.push(r),showSheet:html=>{document.querySelector('#sheet').innerHTML=html;},api:async(_url,options)=>{
  const b=JSON.parse(options.body);requests.push(b);
  if(b.action==='analyze')return {id:'measurement-1',status:'ready',points};
  return new Promise(resolve=>{release=()=>resolve({id:'measurement-1',status:'ready',result:{width:400,length:500,area_m2:20,source:'ai_calibrated'}});});
 }});
 try{
  await measure();const input=document.querySelector('input'),calculate=document.querySelector('[data-calculate]');
  input.value='4';input.dispatchEvent(new Event('input'));assert.equal(calculate.disabled,false);calculate.click();
  assert.deepEqual(requests.at(-1),{action:'calculate',points,reference:4});
  input.value='6';input.dispatchEvent(new Event('input'));release();await new Promise(r=>setImmediate(r));
  assert.equal(document.querySelector('.measure-result').hidden,true);assert.equal(calculate.disabled,false);
  calculate.click();release();await new Promise(r=>setImmediate(r));document.querySelector('[data-use]').click();
  assert.equal(applied[0].measurement_id,'measurement-1');assert.equal(applied[0].length,500);
 }finally{delete globalThis.document;}
});
