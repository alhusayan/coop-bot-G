import test from 'node:test';
import assert from 'node:assert/strict';
import {measureReference} from '../reference-measure.mjs';
const project=([x,y])=>[(.11*x+.04*y+.1)/(1+.09*y),(.015*x+.12*y+.12)/(1+.09*y)];
const ref=[[0,0],[1,0],[1,1],[0,1]].map(project),area=[[0,0],[4,0],[4,5],[0,5]].map(project);
const input={reference_points:ref,reference_width:1,reference_length:1,points:area,source_width:2000,source_height:1600};
test('a tilted reference recovers a known 4 by 5 metre floor, unlike a constant pixel scale',()=>{
 const result=measureReference(input);assert.equal(result.width,400);assert.equal(result.length,500);assert.equal(result.area_m2,20);assert.equal(result.source,'reference_scale');assert.equal(result.accuracy_validated,false);
 const scaled=measureReference({...input,reference_width:2,reference_length:2});assert.equal(scaled.width,800);assert.equal(scaled.area_m2,80);
 const reversed=measureReference({...input,reference_points:[...ref].reverse(),points:[...area].reverse()});assert.equal(reversed.area_m2,20);
});
test('crossed, missing, tiny or impossible reference geometry produces specific actionable errors',()=>{
 assert.throws(()=>measureReference({...input,reference_points:[ref[0],ref[2],ref[1],ref[3]]}),/POINT_ORDER/);
 assert.throws(()=>measureReference({...input,points:area.slice(0,3)}),/POINTS_REQUIRED/);
 assert.throws(()=>measureReference({...input,reference_width:0}),/SIZE_REQUIRED/);
 assert.throws(()=>measureReference({...input,reference_points:[[.1,.1],[.101,.1],[.101,.101],[.1,.101]]}),/TOO_SMALL/);
 assert.throws(()=>measureReference({...input,points:[[0,0],[4,0],[2,5],[0,5]].map(project)}),/AREA_NOT_RECTANGULAR/);
});
test('A4 has separate short and long sides, both used by the projective calibration',()=>{
 const scale=p=>[.1+p[0]*.9,.1+p[1]*.9];
 const result=measureReference({reference_points:[[0,0],[.21,0],[.21,.297],[0,.297]].map(scale),reference_width:.21,reference_length:.297,points:[[0,0],[.8,0],[.8,.9],[0,.9]].map(scale),source_width:2000,source_height:2000});
 assert.equal(result.width,80);assert.equal(result.length,90);assert.equal(result.area_m2,.72);
});
