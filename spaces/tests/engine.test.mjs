import test from 'node:test';
import assert from 'node:assert/strict';
import {numericPrice,priceText,localEvidence,publicIP,productFromPage,sanitizeItems,searchItem,safeUrl} from '../engine.mjs';
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
test('only an individual product with real matching currency and usable offer is priced',()=>{
 assert.equal(productFromPage(page(product),'https://shop.kw/products/sofa','KWD').price,299.5);
 assert.equal(productFromPage(page(product),'https://shop.kw/products/sofa','SAR'),null);
 assert.equal(productFromPage(page({...product,offers:{...product.offers,availability:'https://schema.org/OutOfStock'}}),'https://shop.kw/p/1','KWD'),null);
 assert.equal(productFromPage(page([product,product]),'https://shop.kw/collection','KWD'),null);
 assert.equal(productFromPage(page({...product,offers:{priceCurrency:'KWD',lowPrice:15,highPrice:100}}),'https://shop.kw/p','KWD'),null);
});
test('measured materials and custom cabinetry are not assigned invented quantities',()=>{
 const data=sanitizeItems({items:[{name_en:'tiles',query_en:'ceramic tiles',mode:'measure',quantity:40,box:[1100,-10,20,50]},{name_en:'cabinet',query_en:'cabinet',mode:'quote',quantity:5}]});
 assert.equal(data[0].quantity,null);assert.equal(data[1].quantity,null);assert.equal(data[1].status,'quote');assert.deepEqual(data[0].box,[20,0,1000,50]);
});
test('search relevance cannot invent or change product prices; other currencies are rejected',async()=>{
 const result=await searchItem({name_en:'sofa',query:'beige sofa'},'KW',{
 search:async()=>({organic:[{title:'Sofa',link:'https://shop.kw/products/sofa'}]}),page:async url=>({url,html:page(product)}),judge:async()=>({accepted:[0],price:1})});
 assert.equal(result.length,1);assert.equal(result[0].price,299.5);assert.equal(result[0].match,'similar');assert.equal(result[0].evidence,'product_page');
});
test('irrelevant priced results are excluded rather than displayed as a design match',async()=>{
 const r=await searchItem({name_en:'sofa',query:'beige sofa'},'KW',{search:async()=>({organic:[{link:'https://shop.kw/products/cover'}]}),page:async url=>({url,html:page({...product,name:'sofa cover'})}),judge:async()=>({accepted:[]})});assert.deepEqual(r,[]);
});
