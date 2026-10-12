import test from 'node:test';
import assert from 'node:assert/strict';
import {sourceScope,storePolicy,filterApprovedOffers,globalQueries,sourceDetails,localQueries} from '../sourcing.mjs';
import {productPath} from '../engine.mjs';
import {searchAllViews} from '../identity.mjs';

test('only approved international domains pass, with proper hostname boundaries',()=>{
 for(const host of ['amazon.com','www.ebay.com','walmart.com','aliexpress.com','chinese.alibaba.com','us.shein.com','temu.com','made-in-china.com','dhgate.com','lightinthebox.com','finnishdesignshop.com','shop.mohd.it','archiproducts.com'])assert.equal(sourceScope('https://'+host+'/products/chair','KW'),'international',host);
 for(const host of ['amazon.com.fake.shop','fakeamazon.com','shop.tuckstudio.ca','ajio.com','taobao.com','1688.com','wayfair.com'])assert.equal(sourceScope('https://'+host+'/products/chair','KW'),null,host);
 assert.equal(sourceScope('http://amazon.com/dp/123','KW'),null);
 assert.equal(sourceScope('https://amazon.com@fake.shop/products/chair','KW'),null);
});
test('local stores stay eligible and cross-border availability is not inferred',()=>{
 assert.equal(sourceScope('https://safathome.com/products/chair','KW'),'local');
 assert.equal(sourceScope('https://alrugaibfurniture.com/products/chair','SA'),'local');
 assert.equal(sourceScope('https://alrugaibfurniture.com/products/chair','KW'),null);
 assert.equal(sourceScope('https://wayfair.com/products/chair','US'),'local');
 assert.equal(sourceScope('https://local.de/products/chair','DE'),'local');
 const x=sourceDetails('https://shop.mohd.it/en/chair.html','KW');assert.equal(x.shipping_status,'check_at_store');assert.ok(x.shipping_policy);assert.equal(x.market,null);
});
test('new global furniture lane and eBay/Etsy product links are discoverable',()=>{
 const queries=globalQueries('olive chair','绿色 椅子',{name_en:'chair',chinese_query:'绿色 椅子'});
 assert.equal(queries.filter(x=>x[2].source==='furniture').length,1);
 const all=queries.map(x=>x[0]).join(' ');for(const host of ['ebay.com','finnishdesignshop.com','shop.mohd.it','archiproducts.com'])assert.ok(all.includes('site:'+host));
 assert.ok(!all.includes('taobao'));assert.ok(!all.includes('1688'));assert.ok(!all.includes('wayfair'));
 assert.equal(productPath('https://www.ebay.com/itm/123456789'),true);assert.equal(productPath('https://www.etsy.com/listing/123456/chair'),true);
 assert.equal(productPath('https://www.etsy.com/search?q=chair'),false);assert.equal(storePolicy('https://archiproducts.com/en/products/chair').verify_purchase,true);
});
test('cached foreign results are pruned without changing approved prices or alternatives',async()=>{
 const approved={link:'https://amazon.com/dp/1',price:null,currency:null,match:'replacement'},blocked={link:'https://ajio.com/products/chair',market_scope:'local',match:'visual'};
 const filtered=filterApprovedOffers([approved,blocked],'KW');assert.equal(filtered.length,1);assert.equal(filtered[0].price,null);assert.equal(filtered[0].match,'replacement');
 let latest;await searchAllViews({offers:[blocked],alternatives:[approved]},'KW',{views:[{id:'1'}],stockCheck:async o=>o,run:async()=>[],onProgress:u=>latest=u});assert.equal(latest.offers.length,0);assert.equal(latest.alternatives.length,1);
});

test('local retrieval targets the selected country and simplifies bed retrieval without inventing dimensions',()=>{
 const q=localQueries({name_en:'Single platform bed',query:'single upholstered platform bed with straight headboard',native_query:'سرير مفرد مبطن'},'SA',{recovery:true});
 assert.ok(q.every(([query,country])=>country==='SA'&&query.includes('site:homecentre.com/sa/')&&query.includes('site:ikea.com/sa/')));
 assert.ok(q.every(([query])=>!query.includes('platform')&&!query.includes('120')&&!query.includes('/kw/')));
 assert.equal(sourceScope('https://www.homecentre.com/sa/en/buy-bed/p/123','SA'),'local');assert.equal(sourceScope('https://www.homecentre.com/ae/en/buy-bed/p/123','SA'),null);
});

test('platform beds use real bed-base retail names instead of retrieving attached headboards',()=>{
 const queries=localQueries({name_en:'Single platform bed',query:'single headboardless bed'},'SA',{recovery:true});
 assert.ok(queries[0][0].includes('single bed base'));assert.ok(queries[1][0].includes('قاعدة سرير مفرد'));assert.equal(queries[1][2].lang,'ar');
 const full=localQueries({name_en:'Upholstered single bed',query:'single bed with attached headboard'},'SA',{recovery:true});assert.ok(!full[0][0].includes('bed base'));
});
