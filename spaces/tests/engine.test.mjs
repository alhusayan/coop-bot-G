import test from 'node:test';
import assert from 'node:assert/strict';
import {numericPrice,priceText,localEvidence,publicIP,productFromPage,sanitizeItems,safeUrl} from '../engine.mjs';
test('new furniture cannot be silently classified as already owned without keep notes',()=>{
 const raw={items:[{name_en:'Nightstand',query_en:'oak nightstand',mode:'keep'}]};
 assert.equal(sanitizeItems(raw)[0].status,'idle');
 assert.equal(sanitizeItems(raw,{keep:'Keep the nightstand'})[0].status,'kept');
});
test('prices preserve thousands and Kuwaiti three decimals, rejecting ambiguous input',()=>{
 assert.equal(numericPrice('1,250.500'),1250.5);assert.equal(numericPrice('١٢٥٫٥٠٠'),125.5);assert.equal(numericPrice('1.299,99'),1299.99);assert.equal(numericPrice('1.2,9.0'),null);assert.equal(numericPrice('-4'),null);assert.equal(numericPrice(''),null);assert.equal(numericPrice(Infinity),null);
 assert.equal(priceText('KWD 129.950','KWD'),129.95);assert.equal(priceText('129.950 د.ك','KWD'),129.95);assert.equal(priceText('$129','KWD'),null);
});
test('private network targets, credentials and non-HTTPS URLs cannot be fetched',()=>{
 for(const ip of ['127.0.0.1','10.0.0.2','172.31.2.1','192.168.1.1','169.254.169.254','100.64.0.1','::1','::ffff:127.0.0.1'])assert.equal(publicIP(ip),false,ip);
 assert.equal(publicIP('8.8.8.8'),true);assert.equal(safeUrl('https://user:pass@example.com'),null);assert.equal(safeUrl('javascript:alert(1)'),null);
});
test('market location uses URL evidence rather than country substring in merchant names',()=>{
 assert.equal(localEvidence('https://www.ikea.com/kw/en/p/sofa','KW'),true);assert.equal(localEvidence('https://shop.com/sa/en/sofa','KW'),false);assert.equal(localEvidence('https://store.kw/p/1','KW'),true);assert.equal(localEvidence('https://kwfake.com/p','KW'),false);
});
function page(product){return `<script type="application/ld+json">${JSON.stringify(product)}</script>`;}
const product={'@type':'Product',name:'Beige sofa',image:'https://example.com/sofa.jpg',offers:{'@type':'Offer',price:'299.500',priceCurrency:'KWD',availability:'https://schema.org/InStock'}};
test('individual product data preserves real currency, missing prices and out-of-stock status',()=>{
 assert.equal(productFromPage(page(product),'https://shop.kw/products/sofa','KWD').price,299.5);
 assert.equal(productFromPage(page(product),'https://shop.kw/products/sofa','SAR').currency,'KWD');
 assert.equal(productFromPage(page({...product,offers:{...product.offers,availability:'https://schema.org/OutOfStock'}}),'https://shop.kw/p/1','KWD').availability,'out_of_stock');
 assert.equal(productFromPage(page([product,product]),'https://shop.kw/collection','KWD'),null);
 assert.equal(productFromPage(page({...product,offers:{priceCurrency:'KWD',lowPrice:15,highPrice:100}}),'https://shop.kw/p','KWD').price,null);
});
test('measured materials and custom cabinetry are not assigned invented quantities',()=>{
 const data=sanitizeItems({items:[{name_en:'tiles',query_en:'ceramic tiles',mode:'measure',quantity:40,box:[1100,-10,20,50]},{name_en:'cabinet',query_en:'cabinet',mode:'quote',quantity:5}]});
 assert.equal(data[0].quantity,null);assert.equal(data[1].quantity,null);assert.equal(data[1].status,'idle');assert.deepEqual(data[0].box,[20,0,1000,50]);
});

test('product without a price remains available, but a category page does not become a product',()=>{
 const p=productFromPage(page({...product,offers:undefined}),'https://shop.kw/products/sofa','KWD');assert.equal(p.title,'Beige sofa');assert.equal(p.price,null);
 assert.equal(productFromPage('<meta property="og:title" content="Sofas"><meta property="og:image" content="https://shop.kw/a.jpg">Add to cart','https://shop.kw/collections/sofas','KWD'),null);
});
test('inventory keeps more than nine elements including measured and custom work',()=>{
 const data=sanitizeItems({items:Array.from({length:20},(_,i)=>({name_en:'Item '+i,query_en:'specific furniture',mode:i===18?'measure':i===19?'quote':'ready',quantity:2,box:[0,0,1000,1000]}))});assert.equal(data.length,20);assert.equal(data[19].quantity,null);
});
