import test from 'node:test';
import assert from 'node:assert/strict';
import {pieceViews,pickPhotoPiece} from '../public/hotspots.js';

test('direct photo taps select a foreground chair independently of overlapping desk and rug',()=>{
 const items=[{id:'rug',box:[300,100,980,900]},{id:'desk',box:[200,200,850,750]},{id:'chair',box:[420,380,800,620]}];
 assert.equal(pickPhotoPiece(items,500,600).id,'chair');
 assert.equal(pickPhotoPiece(items,250,300).id,'desk');
 assert.equal(pickPhotoPiece(items,150,900).id,'rug');
 assert.equal(pickPhotoPiece(items,10,10),null);
 for(const [x,y] of [[NaN,50],[50,Infinity],[-1,400],[1001,600]])assert.equal(pickPhotoPiece(items,x,y),null);
});
test('a repeated product selects its tapped occurrence without creating a second charged piece',()=>{
 const items=[{id:'4',box:[100,100,400,350],occurrences:[{id:'4',box:[100,100,400,350]},{id:'5',box:[500,600,900,950]}]}];
 const hit=pickPhotoPiece(items,800,700);assert.equal(hit.id,'4');assert.equal(hit.marker,'5');assert.deepEqual(hit.box,[500,600,900,950]);
 assert.equal(pieceViews(items).length,2);
});
test('invalid detections never create an invented full-photo selection',()=>{
 assert.deepEqual(pieceViews([{id:'bad',box:[0,0,NaN,40]},{id:'flat',box:[50,50,50,60]},{id:'none'}]),[]);
});

test('overlapping desk and chair remain separate choices, excluding a background rug',async()=>{
 const {pickPhotoCandidates}=await import('../public/hotspots.js');
 const items=[{id:'rug',name_en:'Area rug',box:[100,100,990,990]},{id:'desk',name_en:'Desk',box:[300,200,750,850]},{id:'chair',name_en:'Desk chair',box:[450,420,800,650]}];
 assert.deepEqual(pickPhotoCandidates(items,500,600).map(x=>x.id),['chair','desk']);
 assert.equal(pickPhotoCandidates(items,120,900)[0].id,'rug');
});

test('visible selection patches do not select the occluded sofa through a desk and chair',async()=>{
 const {pickPhotoCandidates}=await import('../public/hotspots.js');
 const items=[
  {id:'sofa',box:[300,250,650,800],selection_boxes:[[300,250,360,700]]},
  {id:'desk',box:[350,200,700,850],selection_boxes:[[360,200,410,850],[410,250,700,350]]},
  {id:'chair',box:[400,420,720,650],selection_boxes:[[420,430,650,630]]}
 ];
 assert.deepEqual(pickPhotoCandidates(items,500,500).map(x=>x.id),['chair']);
 assert.deepEqual(pickPhotoCandidates(items,300,500).map(x=>x.id),['desk']);
 assert.deepEqual(pickPhotoCandidates(items,500,330).map(x=>x.id),['sofa']);
});


test('doors, fitted decoration and uncovered finishes are selectable without stealing furniture taps',()=>{
 const items=[{id:'wall',name_en:'Limewash wall',surface:'wall',box:[0,0,1000,1000]},
 {id:'door',name_en:'Oak door',surface:'object',search_kind:'both',box:[100,50,900,300]},
 {id:'decor',name_en:'Timber screen',surface:'object',search_kind:'service',box:[100,700,900,950]},
 {id:'chair',name_en:'Chair',box:[500,400,900,650]}];
 assert.equal(pickPhotoPiece(items,100,500).id,'door');
 assert.equal(pickPhotoPiece(items,800,500).id,'decor');
 assert.equal(pickPhotoPiece(items,500,700).id,'chair');
 assert.equal(pickPhotoPiece(items,500,200).id,'wall');
 const floor=[{id:'floor',surface:'floor',box:[0,0,1000,1000]},{id:'rug',category:'rug',box:[300,100,900,900]}];
 assert.equal(pickPhotoPiece(floor,500,500).id,'rug');
 assert.equal(pickPhotoPiece(floor,50,900).id,'floor');
});
