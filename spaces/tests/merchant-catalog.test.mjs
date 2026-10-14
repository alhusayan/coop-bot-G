import test from 'node:test';
import assert from 'node:assert/strict';
import {merchantCatalogue,catalogueLinks,catalogueRole} from '../merchant-catalog.mjs';
import {productDimensions} from '../room-fit.mjs';
const root='https://furniture.example.co.uk';
const product=(title,{currency='GBP',stock='InStock'}={})=>`<html><body><h1>${title}</h1><script type="application/ld+json">${JSON.stringify({'@type':'Product',name:title,image:root+'/table.jpg',offers:{'@type':'Offer',price:'339.95',priceCurrency:currency,availability:'https://schema.org/'+stock},width:{value:180,unitText:'cm'},depth:{value:90,unitText:'cm'},height:{value:75,unitText:'cm'}})}</script></body></html>`;
test('merchant catalogue follows observed same-store links and validates standalone product stock/price/dimensions',async()=>{
 const pages={
  '/bundle':'<a href="/dining-tables">Dining Tables</a><a href="https://elsewhere.example/products/x">Cheap dining tables elsewhere</a>',
  '/furniture/dining-tables':['Oak 180cm standalone Dining Table','Mango Dining Table with 8 Chairs','Walnut 180cm sold-out Dining Table','Imported USD walnut Dining Table'].map((n,i)=>`<a href="/products/${i}">${n}</a>`).join(''),
  '/products/0':product('Oak 180cm standalone Dining Table'),
  '/products/1':product('Mango Dining Table with 8 Chairs'),
  '/products/2':product('Walnut 180cm sold-out Dining Table',{stock:'OutOfStock'}),
  '/products/3':product('Imported USD walnut Dining Table',{currency:'USD'})
 };
 const calls=[],page=async url=>{calls.push(url);let path=new URL(url).pathname;if(path==='/dining-tables')path='/furniture/dining-tables';assert.ok(pages[path]);return {url:root+path,html:pages[path]};};
 const result=await merchantCatalogue({id:'9',name_en:'dining table'},[{title:'Mango Wood Dining Table 8 Seater',link:root+'/bundle',search_market:'GB',market_scope:'local'}],'GB',{page});
 assert.equal(result.length,1);assert.equal(result[0].price,339.95);assert.equal(result[0].currency,'GBP');assert.equal(result[0].search_engine,'merchant-catalogue');
 assert.equal(productDimensions(result[0].merchant_facts).width,180);assert.equal(result[0].availability,'listed_available');assert.equal(calls.length,6);assert.ok(calls.every(x=>x.startsWith(root)));
 assert.deepEqual(await merchantCatalogue({name_en:'dining table'},[{title:'Dining Table',link:root+'/bundle',search_market:'GB',market_scope:'local'}],'KW',{page}),[]);
});
test('catalogue traversal ignores unrelated furniture, external links, account actions and duplicate URLs',()=>{
 const html='<a href="/products/oak">Oak dining table</a><a href="/products/oak">Same dining table</a><a href="/cart/add">Add dining table</a><a href="//evil.example/x">Oak dining table</a><a href="javascript:alert(1)">Oak dining table</a><a href="/chair">Dining chair</a>';
 assert.deepEqual(catalogueLinks(html,root+'/bundle',catalogueRole('dining table')),[{name:'Oak dining table',link:root+'/products/oak'}]);
});
