import test from 'node:test';
import assert from 'node:assert/strict';
import {productFromPage} from '../engine.mjs';
import {dimensionDetails,dimensionsFromPage,usableSize} from '../dimensions.mjs';
import {readProductData,DETAILS_VERSION} from '../product-data.mjs';
import {checkStock} from '../stock.mjs';
import {detailsFromScrape} from '../store-details.mjs';
const url='https://www.safathome.com/vivian-3-seater-sofa-with-3-pillows-beige/p';
const ld=p=>`<script type="application/ld+json">${JSON.stringify(p)}</script>`;
const next=p=>`<script id="__NEXT_DATA__" type="application/json">${JSON.stringify(p)}</script>`;
const sofa={'@type':'Product',name:'Vivian 3-Seater Sofa with 3 Pillows Beige',sku:'90042281',url,image:'https://cdn.media.amplience.net/i/safathome/90042281-01',offers:{availability:'https://schema.org/InStock'}};
const attributes=[{label:'Length (CM)',value:'210'},{label:'Width (CM)',value:'88'},{label:'Height (CM)',value:'92'}];
const html=ld(sofa)+next({props:{pageProps:{meta:{product:{...sofa,dimensions:[],media:[{src:'https://cdn.media.amplience.net/i/safathome/90042281-03'}],sections:[{label:'Construction Details',type:'attributes',attributes}]}}}}});
test('Safat closed construction tab yields 210 x 88 x 92 and enriches an audited gallery image',async()=>{
 const p=productFromPage(html,url,'KWD');assert.deepEqual(p.dimensions_cm,{width:210,depth:88,height:92});assert.ok(p.dimensions_evidence.some(e=>e.text==='Length (CM): 210'));
 const offer={title:sofa.name,link:url+'?srsltid=tracking',image:'https://cdn.media.amplience.net/i/safathome/90042281-03?w=600',price:175,currency:'KWD',stock_version:3,stock_checked_at:new Date().toISOString()};
 let reads=0;const updated=await checkStock(offer,'KW',{page:async()=>{reads++;return {url,html};}});
 assert.equal(reads,1);assert.equal(updated.details_version,DETAILS_VERSION);assert.equal(updated.availability,'listed_available');assert.equal(updated.price,175);assert.equal(updated.image,offer.image);assert.deepEqual(updated.dimensions_cm,p.dimensions_cm);
});
test('Home Centre base64 state scopes dimensions to the selected variant and excludes seat height',()=>{
 const hc='https://www.homecentre.com/kw/en/chair/p/163815641';
 const data={productPageReducerBL:{data:{sku:'163815641-HC',name:'Nuevo chair',variants:[{sku:'163815641'}],productAttributeDetails:[{groupDisplayName:'Weight & Dimensions',attributeDetails:{w:{nameLabel:'Width (cm)',value:'58'},d:{nameLabel:'Depth (cm)',value:'62'},h:{nameLabel:'Height (cm)',value:'83'},seat:{nameLabel:'Seating Height (cm)',value:'48'}}}]}},recommendations:[{sku:'163815641',width:'999 cm'}]};
 const page=next({props:{initialState:Buffer.from(JSON.stringify(data)).toString('base64')}});
 const details=dimensionDetails(page,{},hc);assert.deepEqual(details.size,{width:58,depth:62,height:83});assert.equal(details.evidence[0].source,'product_state');
});
test('tables support explicit US axis notation without guessing an unlabelled triplet',()=>{
 const table=(label,v)=>`<table><tr><th>${label}</th><td>${v}</td></tr></table>`;
 assert.deepEqual(dimensionsFromPage(table('Product Dimensions','35"D x 72"W x 31"H')),{depth:88.9,width:182.88,height:78.74});
 const mirror=dimensionDetails(table('Item Dimensions L x W','30"L x 22"W')+table('Item Dimensions','30 x 22 x 1 inches'),{name:'Wall mirror'});
 assert.deepEqual(mirror.size,{length:76.2,width:55.88});assert.equal(usableSize(mirror.size),false);
 assert.deepEqual(dimensionsFromPage(table('Package Dimensions','100 x 80 x 70 cm')) ,{});
 assert.deepEqual(dimensionsFromPage('<section id="recommendations">'+table('Width (cm)','999')+'</section>'),{});
 assert.deepEqual(dimensionsFromPage('<section id="recommendations"><h2>Product Dimensions</h2>Width (cm) 999 Depth (cm) 999 Height (cm) 999</section>'),{});
});
test('component sets, missing units and conflicting sizes cannot become a verified overall size',()=>{
 const set='<div id="ProductSpecifications-main">Set Contains 1 Table D110 x W220 x H75cm 6 Chairs D53 x W54 x H77cm</div>';
 assert.deepEqual(dimensionsFromPage(set),{});
 assert.deepEqual(dimensionsFromPage('<dl><dt>Width</dt><dd>100</dd></dl>'),{});
 const conflict=dimensionDetails('<table><tr><td>Width (cm)</td><td>100</td></tr><tr><td>Width (cm)</td><td>200</td></tr></table>');
 assert.equal(conflict.size.width,undefined);assert.equal(conflict.status,'conflicting_dimensions');
 assert.deepEqual(dimensionsFromPage('',{length:'100 cm',height:'20 cm'}),{depth:100,height:20});
});
test('unknown requested variants and unrelated SKU data never inherit dimensions',async()=>{
 const variant=url+'?variant=large';assert.equal(productFromPage(html,variant,'KWD'),null);
 const unrelated=await checkStock({link:url,sku:'different',image:sofa.image},'KW',{page:async()=>({url,html})});assert.equal(unrelated.dimensions_cm,undefined);
 const data=readProductData(ld({...sofa,sku:'999'}),'https://store.kw/p/123');assert.equal(data.sku,'999');
});
test('secondary page extraction requires exact product evidence and retains units and source',()=>{
 const offer={link:url,title:sofa.name,sku:'90042281'};
 const data={metadata:{title:sofa.name},markdown:'# '+sofa.name+'\nSKU: 90042281\n| Length (CM) | 210 |\n| Width (CM) | 88 |\n| Height (CM) | 92 |\nAdd to cart'};
 const result=detailsFromScrape(data,offer);assert.deepEqual(result.dimensions_cm,{width:210,depth:88,height:92});assert.equal(result.availability,'listed_available');
 assert.equal(detailsFromScrape({...data,metadata:{canonical:'https://safathome.com/other/p'}},offer),null);
 assert.equal(detailsFromScrape({text:'Verify you are human'},offer),null);
 assert.equal(detailsFromScrape(data,{...offer,link:url+'?variant=other'}),null);
 const unknown=detailsFromScrape({metadata:{title:sofa.name},markdown:'# '+sofa.name+'\nWidth (cm): 210\nAdd to cart'},offer);assert.equal(unknown.availability,'unknown');
});
test('product-first sourcing adopts the exact page photo and dimensions without inheriting an indexed crop',async()=>{
 const offer={title:sofa.name,link:url,image:'https://example.com/indexed-crop.jpg'};
 const legacy=await checkStock(offer,'KW',{page:async()=>({url,html})});assert.equal(legacy.dimensions_cm,undefined);
 const catalog=await checkStock(offer,'KW',{catalog:true,page:async()=>({url,html})});assert.deepEqual(catalog.dimensions_cm,{width:210,depth:88,height:92});assert.equal(catalog.image,sofa.image);assert.equal(catalog.sku,'90042281');
 const wrong=await checkStock({...offer,sku:'wrong' },'KW',{catalog:true,page:async()=>({url,html})});assert.equal(wrong.availability,'unknown');
});
