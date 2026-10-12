import test from 'node:test';
import assert from 'node:assert/strict';
import {availabilityFromPage,stockValue,STOCK_VERSION} from '../availability.mjs';
import {checkStock,refreshItemStock} from '../stock.mjs';
import {rankProducts,hasLocalOptions} from '../public/product-order.js';
const url='https://www.homecentre.com/kw/en/buy-kai-bedside-table/p/123';
const offer={link:url,title:'Kai nightstand',image:'https://cdn.example/gallery-6.jpg',match:'replacement',market_scope:'local',availability:'unknown'};
const product={'@type':'Product',name:'Kai nightstand',image:'https://cdn.example/gallery-1.jpg',sku:'123',offers:{availability:'https://schema.org/OutOfStock'}};
const ld=p=>`<script type="application/ld+json">${JSON.stringify(p)}</script>`;
test('English and Arabic sold-out purchase controls override stale in-stock schema',()=>{
 for(const label of ['Out Of Stock','Sold Out','إنتهى من المخزن','إنتهى من المخزون','نفد المخزون']){
   const html=ld({...product,offers:{availability:'https://schema.org/InStock'}})+`<button disabled>${label}</button>`;
   assert.equal(availabilityFromPage(html,url).availability,'out_of_stock',label);
 }
 assert.equal(stockValue('https://schema.org/Discontinued'),'out_of_stock');
});
test('translation bundles and unrelated variants cannot make the selected product sold out',()=>{
 const html=ld({...product,offers:{availability:'https://schema.org/InStock'}})+'<script type="application/json">{"translations":{"outOfStock":"Out Of Stock"},"recommendations":[{"id":"123","inStock":false}]}</script>';
 assert.equal(availabilityFromPage(html,'https://store.kw/products/123').availability,'listed_available');
 const variants=[{...product,sku:'999',offers:{availability:'https://schema.org/OutOfStock'}},{...product,offers:{availability:'https://schema.org/InStock'}}];
 assert.equal(availabilityFromPage(ld(variants),'https://store.kw/products/123').availability,'listed_available');
 assert.equal(availabilityFromPage(ld([{...product,sku:'888'},{...product,sku:'999'}]),url).availability,'unknown');
});
test('product hydration stock is scoped to the exact SKU and overrides stale schema',()=>{
 const html=ld({...product,offers:{availability:'https://schema.org/InStock'}})+'<script type="application/json">{"props":{"product":{"code":"123","stock":{"stockLevelStatus":"outOfStock"}}},"other":{"code":"456","inStock":true}}</script>';
 assert.deepEqual(availabilityFromPage(html,url),{availability:'out_of_stock',stock_evidence:'product_state'});
});
test('stock is checked independently of the gallery image without replacing visual evidence or price',async()=>{
 const checked=await checkStock({...offer,price:29,currency:'KWD'},'KW',{page:async()=>({url,html:ld({...product,offers:{price:999,priceCurrency:'KWD',availability:'https://schema.org/OutOfStock'}})})});
 assert.equal(checked.availability,'out_of_stock');assert.equal(checked.image,offer.image);assert.equal(checked.price,29);assert.equal(checked.stock_version,STOCK_VERSION);
});
test('inaccessible or ambiguous stock is never labelled in stock; a known sold-out result stays excluded',async()=>{
 const page=async()=>{throw Error('timeout');};
 assert.equal((await checkStock({...offer,availability:'listed_available'},'KW',{page})).availability,'unknown');
 assert.equal((await checkStock({...offer,availability:'out_of_stock'},'KW',{page})).availability,'out_of_stock');
 assert.equal(hasLocalOptions({alternatives:[offer]}),false);
});
test('fresh sold-out evidence defeats older high similarity and is removed from saved alternatives',async()=>{
 const old={...offer,availability:'listed_available',visual_score:99,stock_checked_at:'2026-10-12T09:00:00Z'},fresh={...offer,availability:'out_of_stock',visual_score:60,stock_checked_at:'2026-10-12T10:00:00Z'};
 assert.deepEqual(rankProducts([old,fresh]),[]);assert.deepEqual(rankProducts([fresh,old]),[]);
 const refreshed=await refreshItemStock({offers:[],alternatives:[old]},'KW',{check:async()=>fresh});assert.deepEqual(refreshed.alternatives,[]);
});

test('Landmark SEO in-stock metadata alone is not purchase evidence',()=>{
 const html=ld({...product,offers:{availability:'https://schema.org/InStock'}})+'<meta property="product:availability" content="in stock">';
 assert.equal(availabilityFromPage(html,url).availability,'unknown');
 assert.equal(availabilityFromPage(html+'<button>Add to cart</button>',url).availability,'listed_available');
 assert.equal(availabilityFromPage(html+'<button disabled>Out Of Stock</button>',url).availability,'out_of_stock');
});
test('confirmed global stock cannot be crowded out by uncertain local listings',()=>{
 const local=Array.from({length:4},(_,i)=>({...offer,link:offer.link+i,availability:'unknown',visual_score:99}));
 const global={...offer,link:'https://amazon.com/dp/123',availability:'listed_available',market_scope:'international',visual_score:80};
 assert.equal(rankProducts([...local,global],4)[0].link,global.link);
});
