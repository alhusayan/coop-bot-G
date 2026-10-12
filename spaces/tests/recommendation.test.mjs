import test from 'node:test';
import assert from 'node:assert/strict';
import {recommendRoom} from '../recommendation.mjs';
const size={width:80,depth:85,height:90},room={width_cm:400,length_cm:500};
const local={link:'https://www.homecentre.com/kw/en/p/123',image:'https://example.com/chair.jpg',title:'Olive chair',availability:'listed_available',dimensions_cm:size,market_scope:'local',visual_score:89};
const global={...local,link:'https://www.amazon.com/dp/B000000123',market_scope:'international',visual_score:99};
const item={id:'1',name_en:'Olive chair',mode:'ready',offers:[],alternatives:[local,global],occurrences:[{id:'1',box:[50,10,700,400]},{id:'2',box:[50,600,700,990]}]};
const stock=async o=>o;
const judge=async parts=>parts[0].text.startsWith('Estimate')?{slots:[0,1].map(copy=>({id:'1',copy,confidence:90,space:{width:100,depth:100,height:100},target:size}))}:{choices:[{id:'1',link:'https://evil.example/invented'}]};
test('local sized stock beats a higher scoring global result; invented AI links cannot enter the room',async()=>{
 const p=await recommendRoom([item],{},room,'KW',{stock,judge});assert.equal(p.picks.length,1);assert.equal(p.picks[0].offer.link,local.link);assert.equal(p.picks[0].quantity,2);assert.equal(p.picks[0].offer.room_fit.copies.length,2);assert.equal(p.options['1'].length,1);
});
test('global fallback follows local fit and stock checks, and missing dimensions never qualify',async()=>{
 const p=await recommendRoom([{...item,alternatives:[{...local,dimensions_cm:{...size,width:200}},global]}],{},room,'KW',{stock,judge});assert.equal(p.picks[0].offer.link,global.link);
 const q=await recommendRoom([{...item,alternatives:[{...local,availability:'unknown'},{...global,dimensions_cm:{}}]}],{},room,'KW',{stock,judge});assert.equal(q.picks.length,0);assert.equal(q.skipped.length,1);assert.equal(q.skipped[0].reason_code,'store_dimensions');
});
test('every repeated copy must fit and user choices cannot silently change',async()=>{
 const narrow=async parts=>parts[0].text.startsWith('Estimate')?{slots:[{id:'1',copy:0,confidence:90,space:size,target:size},{id:'1',copy:1,confidence:90,space:{...size,width:60},target:size}]}:judge(parts);
 const p=await recommendRoom([item],{},room,'KW',{stock,judge:narrow});assert.equal(p.picks.length,0);
 await assert.rejects(recommendRoom([item],{},room,'KW',{stock,judge,preferred:{'1':'https://evil.example'}}),/CHOICE_NO_LONGER_FITS/);
});
