import test from 'node:test';
import assert from 'node:assert/strict';
import {parseHTML} from 'linkedom';
import {productFacts,syncProductFacts} from '../public/product-facts.js';

test('only offer evidence is used; dimensions retain their axes and units',()=>{
 const row={title:'Oak veneer console, beige',card_attributes:[{name:'color',value:'Beige'},{name:'width',value:'120 cm'},{name:'height',value:'65 cm'},{name:'material',value:'Oak veneer'}],key_specs:[{kind:'material',value:'Solid oak',source:'candidate_title'},{kind:'depth',value:'45 cm',source:'visual_inference'}],card_candidate_profile:{material:'Solid oak',dimensions:'150 x 50 cm',colors:['Beige','red']},image:{width:800,height:600},card_brand:'Example'};
 const original=JSON.stringify(row),facts=productFacts(row);
 assert.equal(facts.find(x=>x.label==='Material').value,'Oak veneer');
 assert.deepEqual(facts.filter(x=>['Width','Height'].includes(x.label)),[{label:'Width',value:'120 cm'},{label:'Height',value:'65 cm'}]);
 assert.ok(!facts.some(x=>/45|150|800|600|red/.test(x.value)));
 assert.equal(facts.find(x=>x.label==='Brand').value,'Example');
 assert.equal(JSON.stringify(row),original,'display adapter must leave native result data intact');
 assert.deepEqual(productFacts({}),[{label:'Colour',value:''},{label:'Material',value:''},{label:'Dimensions',value:''}]);
});

test('candidate metadata needs literal listing evidence and unknown values stay unknown',()=>{
 const row={raw_title:'Performance fabric chair, olive',card_candidate_profile:{material:'Performance fabric',colors:['olive'],dimensions:'90 cm'},key_specs:[{kind:'finish',value:'unknown',source:'structured'}]};
 assert.equal(productFacts(row).find(x=>x.label==='Material').value,'Performance fabric');
 assert.equal(productFacts(row).find(x=>x.label==='Colour').value,'olive');
 assert.equal(productFacts(row).find(x=>x.label==='Dimensions').value,'');
});

test('stream updates and locale changes render safely without duplicate nodes or modifying the native price',()=>{
 const {document}=parseHTML('<section><div data-results-body><div class="fz-card-shell"><a class="fz-tile" href="https://shop.test/item"><div class="fz-tile-media"></div><div class="fz-tile-body"><div class="fz-tile-price">95.000 KWD</div><div class="fz-store-row">Shop</div></div></a><button data-save-product="https://shop.test/item"></button></div></div></section>');
 const root=document.querySelector('section'),row={url:'https://shop.test/item',title:'<img src=x onerror=alert(1)>',card_attributes:[{name:'material',value:'<script>bad()</script>'}]};
 syncProductFacts(root,[row]);const list=root.querySelector('dl');syncProductFacts(root,[row]);
 assert.equal(root.querySelector('dl'),list,'mutation observers must settle when data is unchanged');
 assert.equal(root.querySelectorAll('.spaces-product-name').length,1);
 assert.equal(root.querySelector('.spaces-product-name').textContent,row.title);
 assert.equal(root.querySelectorAll('img,script').length,0);
 assert.equal(root.querySelector('.fz-tile-price').textContent,'95.000 KWD');
 const lang={Colour:'اللون',Material:'الخامة',Dimensions:'المقاسات','Not listed':'غير مذكور'};
 syncProductFacts(root,[row],key=>lang[key]||key);
 assert.match(root.querySelector('dl').textContent,/اللونغير مذكور/);
 row.card_attributes.push({name:'color',value:'Beige'});syncProductFacts(root,[row]);
 assert.match(root.querySelector('dl').textContent,/ColourBeige/);
 assert.equal(root.querySelectorAll('dl').length,1);
 assert.equal(root.querySelector('.fz-store-row').previousElementSibling.tagName,'DL');
});
