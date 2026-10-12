import test from 'node:test';
import assert from 'node:assert/strict';
import {catalogProducts,catalogMoney,catalogResponse,searchLocalCatalog} from '../shopify.mjs';
const product={title:'Oak table',url:'https://merchant.example/products/table',media:[{type:'image',url:'https://merchant.example/table.jpg'}],variants:[{id:'gid://shopify/ProductVariant/123',requires:{shipping:true},availability:{available:true},price:{amount:120500,currency:'KWD'},seller:{name:'Local furniture'}}]};
const response=products=>({jsonrpc:'2.0',id:1,result:{structuredContent:{products}}});
test('country is sent as both merchant origin and shipping destination, never retried globally',async()=>{
 for(const market of ['KW','SA','AE','QA','BH','OM','GB','US','DE','FR','JP']){
  let calls=0;
  const result=await searchLocalCatalog('oak table',market,{fetcher:async(url,options)=>{calls++;assert.equal(url,'https://catalog.shopify.com/api/ucp/mcp');const body=JSON.parse(options.body),c=body.params.arguments.catalog;assert.deepEqual(c.filters,{ships_to:{country:market},ships_from:[{country:market}],available:true});assert.equal(c.context.address_country,market);return Response.json(response([product]));}});
  assert.equal(calls,1);assert.equal(result.items[0].merchant_country,market);assert.equal(result.items[0].destination_country,market);assert.equal(result.items[0].match,'catalog_suggestion');
 }
});
test('currency never proves locality; digital, unknown shipping and sold-out variants are excluded',()=>{
 for(const edit of [{requires:{shipping:false}},{requires:{}},{requires:{shipping:true,selling_plan:true}},{availability:{available:false}},{availability:{}}]){
  const row=structuredClone(product);Object.assign(row.variants[0],edit);assert.deepEqual(catalogProducts([row],'KW'),[]);
 }
 assert.deepEqual(catalogProducts([product],'ZZ'),[]);
});
test('currency exponents and the exact selected available variant are preserved',()=>{
 assert.deepEqual(catalogMoney({amount:120500,currency:'KWD'}),{amount:120.5,currency:'KWD'});
 assert.deepEqual(catalogMoney({amount:120500,currency:'JPY'}),{amount:120500,currency:'JPY'});
 assert.deepEqual(catalogMoney({amount:1299,currency:'USD'}),{amount:12.99,currency:'USD'});
 assert.equal(catalogMoney({amount:'1299',currency:'USD'}),null);
 const rows=catalogProducts([product],'KW');assert.match(rows[0].link,/variant=123$/);
});
test('rejected origin filters fail closed and catalog images are never fetched',async()=>{
 let calls=0;
 const data=response([product]);data.result.structuredContent.messages=[{code:'unsupported_filter',message:'ships_from'}];
 const result=await searchLocalCatalog('table','KW',{fetcher:async()=>{calls++;return Response.json(data);}});
 assert.equal(result.status,'unavailable');assert.deepEqual(result.items,[]);assert.equal(calls,1);
 assert.deepEqual(catalogResponse({error:{message:'failed'},...response([product])},'KW').items,[]);
});
test('every search is live, failures do not return a previous market response',async()=>{
 let calls=0;const fetcher=async()=>{calls++;return Response.json(response([product]));};
 await searchLocalCatalog('table','KW',{fetcher});await searchLocalCatalog('table','KW',{fetcher});assert.equal(calls,2);
 const result=await searchLocalCatalog('table','SA',{fetcher:async()=>{throw Error('provider down');}});assert.deepEqual(result.items,[]);
});
