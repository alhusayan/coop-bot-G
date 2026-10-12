import test from 'node:test';
import assert from 'node:assert/strict';
import {rankProducts,preferLocalResults,hasLocalOptions} from '../public/product-order.js';
import {searchWithRecovery} from '../matching.mjs';
const local={link:'https://shop.kw/products/chair',market_scope:'local',visual_score:65,price:null,match:'replacement'},global={link:'https://amazon.com/dp/123',market_scope:'international',visual_score:99,match:'visual'};
test('local options stay first even when global similarity or price is stronger',()=>{
 assert.equal(rankProducts([global,local])[0].link,local.link);
 const better={...local,link:local.link+'2',visual_score:90};assert.deepEqual(rankProducts([local,global,better]).map(x=>x.link),[better.link,local.link,global.link]);
});
test('a local replacement remains visible when an old international exact match is cached',()=>{
 const item=preferLocalResults({offers:[global],alternatives:[local]});assert.deepEqual(item.offers,[]);assert.equal(item.alternatives[0].match,'replacement');
 assert.equal(hasLocalOptions(item),true);assert.equal(hasLocalOptions({alternatives:[{...local,availability:'out_of_stock'}]}),false);
});
test('new local results displace a full retained international batch during retry',async()=>{
 const before=Array.from({length:4},(_,i)=>({...global,link:global.link+i}));let latest;
 await searchWithRecovery({offers:before,alternatives:[]},'KW',{onProgress:x=>latest=x,run:async()=>[local]});assert.equal(latest.offers[0].link,local.link);assert.equal(latest.offers.length,4);
});
