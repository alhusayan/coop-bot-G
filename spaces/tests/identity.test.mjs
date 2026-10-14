import test from 'node:test';
import assert from 'node:assert/strict';
import {mergeIdentityGroups,combineResults,searchAllViews,groupIdenticalPieces} from '../identity.mjs';
const chair=(id,box)=>({id,name_en:'Olive armchair',mode:'ready',quantity:1,box,crop:`crop-0-${id}.jpg`,offers:[],alternatives:[],status:'empty'});
const chairs=[chair('1',[100,10,700,400]),chair('2',[100,600,700,990])];
const verdict={groups:[{ids:['1','2'],identical:true,confidence:99,category:'match',color:'match',material:'match',shape:'match',configuration:'match',legs:'match',differences:[]}]};
test('identical chairs merge quantities and rank local options first without losing either crop',()=>{
 const weaker={link:'https://local.example/chair',visual_score:40,market_scope:'local'},stronger={link:'https://global.example/chair',visual_score:87,market_scope:'international'};
 const rows=[{...chairs[0],alternatives:[weaker]},{...chairs[1],alternatives:[stronger,weaker]}];
 const [merged]=mergeIdentityGroups(rows,verdict);assert.equal(merged.quantity,2);assert.equal(merged.occurrences.length,2);assert.equal(merged.alternatives.length,2);assert.equal(merged.alternatives[0].link,weaker.link);assert.deepEqual(rows.map(x=>x.quantity),[1,1]);
});
test('same names alone, different legs, uncertainty or overlapping boxes cannot merge products',()=>{
 assert.equal(mergeIdentityGroups(chairs,{groups:[]}).length,2);
 for(const change of [{legs:'mismatch'},{color:'unclear'},{confidence:70},{differences:['Different arms']}])assert.equal(mergeIdentityGroups(chairs,{groups:[{...verdict.groups[0],...change}]}).length,2);
 assert.equal(mergeIdentityGroups([chairs[0],{...chairs[1],box:chairs[0].box}],verdict).length,2);
});
test('one product cannot be grouped twice, and custom/kept items are not merged into purchase quantities',()=>{
 const rows=[...chairs,chair('3',[720,500,990,950])];
 const grouped=mergeIdentityGroups(rows,{groups:[...verdict.groups,{...verdict.groups[0],ids:['2','3']}]});assert.equal(grouped.length,2);assert.equal(grouped[0].quantity,2);
 assert.equal(mergeIdentityGroups([chairs[0],{...chairs[1],mode:'keep'}],verdict).length,2);
});
test('both camera angles contribute streamed results without turning alternatives into matches',async()=>{
 const calls=[],updates=[];
 const result=await searchAllViews(chairs[0],'KW',{views:[{...chairs[0],target:'left',lensUrl:'left-url'},{...chairs[1],target:'right',lensUrl:'right-url'}],onProgress:x=>updates.push(x),run:async(view,_market,deps)=>{
   calls.push([deps.target,deps.lensUrl]);const row={link:'https://store.kw/'+view.id,visual_score:view.id==='1'?40:90,match:'replacement'};deps.onProgress({offers:[],alternatives:[row],phase:'checking'});return [];
 }});
 assert.deepEqual(calls,[['left','left-url'],['right','right-url']]);assert.deepEqual(result,[]);assert.equal(updates.at(-1).alternatives.length,2);assert.equal(updates.at(-1).alternatives[0].visual_score,90);
});
test('a verified match supersedes the same URL as an alternative',()=>{
 const p={link:'https://shop.example/chair',visual_score:98};const result=combineResults([{offers:[p],alternatives:[]},{offers:[],alternatives:[{...p,visual_score:60}]}]);assert.equal(result.offers.length,1);assert.equal(result.alternatives.length,0);
});
test('visual grouping requires the room evidence as well as the item inventory',async()=>{
 const image={inlineData:{mimeType:'image/jpeg',data:'fixture'}};
 const grouped=await groupIdenticalPieces(chairs,image,{judge:async parts=>{assert.equal(parts[1],image);return verdict;}});assert.equal(grouped.length,1);
});

test('legacy pair quantity is not counted again when both physical copies have their own boxes',()=>{const [merged]=mergeIdentityGroups([{...chairs[0],quantity:2},chairs[1]],verdict);assert.equal(merged.quantity,2);assert.equal(merged.occurrences.length,2);});


test('a high-confidence model verdict cannot merge a desk chair with an armchair',()=>{
 const rows=[{...chairs[0],name_en:'Desk chair',category:'desk_chair'},{...chairs[1],name_en:'Armchair',category:'armchair'}];
 assert.equal(mergeIdentityGroups(rows,verdict).length,2);
});

test('the same review repairs wrong boxes before identity grouping and never merges corrected IDs',async()=>{
 const rows=[{...chairs[0],name_en:'Sofa',box:[300,200,700,800]},{...chairs[1],name_en:'Desk Chair',box:[400,420,700,650]}];
 const result=await groupIdenticalPieces(rows,{}, {judge:async()=>({corrections:[{id:'1',name_en:'Sofa',category:'sofa',box:[300,250,350,750],selection_boxes:[[300,250,350,750]]}],additions:[{name_en:'Desk',category:'desk',box:[350,200,700,850]}],groups:verdict.groups})});
 assert.equal(result.length,3);assert.deepEqual(result[0].box,[300,250,350,750]);assert.equal(result[2].name_en,'Desk');
});
