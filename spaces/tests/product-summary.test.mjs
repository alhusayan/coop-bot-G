import test from 'node:test';
import assert from 'node:assert/strict';
import {parseHTML} from 'linkedom';
import {summarizeFacts,groupProductFacts} from '../public/product-summary.js';
import {syncProductFacts,syncProductDetails} from '../public/product-facts.js';
const fact=(kind,label,value)=>({kind,label,value,source:'merchant_page'});
const chair=[fact('color','Colour','Beige Brown'),fact('material','Main Material','Fabric'),fact('material','Additional Material','Plywood Rubberwood'),fact('material','Filling Material','Foam'),fact('material','Material Composition','100% Polyester'),fact('width','Width','65 cm'),fact('depth','Depth','80 cm'),fact('height','Height','78 cm'),fact('height','Armrest Height','57 cm'),fact('height','Seat Height','40 cm'),fact('assembly','Assembly','Full Assembly Required'),fact('weight','Weight','13 kg'),fact('capacity','Weight Capacity','150 kg')];
test('long chair specification records become three essentials without losing any full details',()=>{
 const original=JSON.stringify(chair),summary=summarizeFacts(chair);
 assert.deepEqual(summary.map(x=>[x.label,x.value]),[['Colour','Beige Brown'],['Material','Fabric'],['Width × Depth × Height','65 × 80 × 78 cm']]);
 assert.equal(groupProductFacts(chair).flatMap(g=>g.facts).length,chair.length);
 assert.equal(JSON.stringify(chair),original);
});
test('assembled measurements appear once and partial component measurements never become overall dimensions',()=>{
 const argos=[fact('material','Upholstery','Linen'),fact('dimensions','Assembled Dimensions','H72, W70, D64cm'),fact('height','Height','72cm'),fact('width','Width','70cm'),fact('depth','Depth','64cm')];
 assert.deepEqual(summarizeFacts(argos).map(f=>f.value),['Linen','H72, W70, D64cm']);
 assert.equal(summarizeFacts([fact('height','Seat Height','40 cm')]).length,0);
 assert.equal(summarizeFacts([...chair,fact('dimensions','Seat Dimensions','40 x 50 cm')]).at(-1).value,'65 × 80 × 78 cm');
 assert.equal(summarizeFacts([fact('width','Width','65 cm'),fact('height','Height','30 in')]).at(-1).value,'65 cm × 30 in');
});
test('Arabic primary labels, repeated colours and component materials remain distinct',()=>{
 const labels={Colour:'اللون',Material:'الخامة',Dimensions:'المقاسات',Width:'العرض',Depth:'العمق',Height:'الارتفاع'},t=k=>labels[k]||k;
 const facts=[fact('color','اللون','بيج'),fact('color','Colour','بيج'),fact('material','خامة السطح','رخام'),fact('material','خامة الأرجل','خشب صلب'),fact('width','العرض (سم)','100 سم'),fact('depth','العمق','100 سم'),fact('height','الارتفاع','40 سم'),fact('height','ارتفاع المقعد','30 سم')];
 const summary=summarizeFacts(facts,t);assert.equal(summary.length,3);assert.equal(summary[2].label,'العرض × العمق × الارتفاع');assert.equal(summary[2].value,'100 × 100 × 40 سم');
 const full=groupProductFacts(facts,t).flatMap(g=>g.facts);assert.equal(full.filter(f=>f.kind==='color').length,1);assert.equal(full.filter(f=>f.kind==='material').length,2);
});
test('cards stay concise while native details keep every sourced fact and remain idempotent across updates',()=>{
 const {document}=parseHTML('<section class="fz-home"><div data-results-body><article class="fz-card-shell"><a class="fz-tile" href="https://shop.test/chair"><div class="fz-tile-body"><div class="fz-tile-price">£75</div><div class="fz-store-row">Store</div></div></a></article></div><dialog class="fz-insights" open><header class="fz-insights-head"><h2>Product details & insights</h2><button class="fz-insights-close">×</button></header><div class="fz-insights-body"><div class="fz-insights-hero">Chair</div><dl class="fz-insights-specs">Old duplicate facts</dl><p class="fz-insights-summary">Existing buying insights</p><footer><a href="https://shop.test/chair">View product</a></footer></div></dialog></section>');
 const root=document.querySelector('section'),row={url:'https://shop.test/chair',title:'Chair'},page={status:'ready',facts:chair},loader={peek:()=>page};
 syncProductFacts(root,[row],x=>x,loader);syncProductDetails(root,row,x=>x,loader);
 assert.equal(root.querySelectorAll('.spaces-product-facts>div').length,3);assert.doesNotMatch(root.querySelector('.fz-tile-body').textContent,/Assembly|Foam|Weight|From the product/);
 assert.equal(root.querySelectorAll('.spaces-full-specs dd').length,chair.length);
 assert.equal(root.querySelector('.fz-insights-specs'),null);assert.equal(root.querySelector('.fz-insights-summary').textContent,'Existing buying insights');assert.equal(root.querySelector('.fz-tile-price').textContent,'£75');
 const full=root.querySelector('.spaces-full-specs');syncProductDetails(root,row,x=>x,loader);assert.equal(root.querySelector('.spaces-full-specs'),full);
 page.facts=[...chair,fact('care','Care','<script>do not run</script>')];syncProductDetails(root,row,x=>x,loader);
 assert.match(root.querySelector('.spaces-full-specs').textContent,/<script>do not run<\/script>/);assert.equal(root.querySelectorAll('script').length,0);
 // The original AI renderer may replace its own body after a response.
 root.querySelector('.spaces-full-specs').remove();syncProductDetails(root,row,x=>x,loader);assert.equal(root.querySelectorAll('.spaces-full-specs').length,1);
});
