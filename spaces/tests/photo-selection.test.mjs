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
