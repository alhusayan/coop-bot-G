import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseHTML} from 'linkedom';
import {designPresentation} from '../public/design-studio.js';
import {studioCopy} from '../public/design-studio-copy.js';
import {patchHTML} from '../public/live-view.js';
globalThis.document=undefined;
const options={escape:s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),icon:()=>'',translate:s=>s};
const job=()=>({id:'room-a',original:'/original.jpg',designs:[0,1,2].map(i=>({title:'Style '+i,palette:['#abcdef'],status:'generating',image:null}))});
test('pending designs show one original-photo workspace and no disabled result cards',()=>{
 const result=designPresentation(job(),options),{document}=parseHTML(result.stage);
 assert.equal(result.cards,'');assert.equal(result.pending,3);assert.equal(result.ready,0);
 assert.equal(document.querySelectorAll('img').length,1);assert.equal(document.querySelectorAll('.studio-concept').length,3);
 assert.doesNotMatch(result.stage,/disabled|filter:blur|%|progressbar/);
});
test('a later-index result is immediately usable and stays first when another design arrives',t=>{
 const j=job();j.designs[2].image='/two.jpg';j.designs[2].status='ready';
 const a=designPresentation(j,{...options,order:[2]});
 assert.equal(a.ready,1);assert.equal(a.pending,2);assert.match(a.cards,/data-index="2"/);assert.doesNotMatch(a.cards,/data-index="0"|disabled/);assert.doesNotMatch(a.stage,/studio-photo-wrap/);
 const {document}=parseHTML('<html><body><div id="grid"></div></body></html>');t.mock.property(globalThis,'document',document);
 const grid=document.getElementById('grid');patchHTML(grid,a.cards);const first=grid.firstElementChild,image=first.querySelector('img');
 j.designs[0].image='/zero.jpg';j.designs[0].status='ready';
 const b=designPresentation(j,{...options,order:[2,0]});patchHTML(grid,b.cards);
 assert.equal(grid.firstElementChild,first);assert.equal(first.querySelector('img'),image);assert.equal(grid.querySelectorAll('[data-action="choose"]')[1].dataset.index,'0');
});
test('completion removes activity; errors retain correct retry indexes; reconnection never claims progress',()=>{
 const j=job();j.designs.forEach((d,i)=>{d.image='/'+i+'.jpg';d.status='ready';});
 assert.equal(designPresentation(j,options).stage,'');
 j.designs[1].image=null;j.designs[1].status='error';
 const failed=designPresentation(j,options);assert.equal(failed.pending,0);assert.match(failed.cards,/data-action="retry" data-index="1"/);
 const slow=designPresentation(job(),{...options,slow:true});assert.match(slow.stage,/No need to start again/);
 const lost=designPresentation(job(),{...options,slow:true,reconnecting:true});assert.match(lost.status,/Reconnecting/);assert.doesNotMatch(lost.stage,/No need to start again/);
});
test('setup removes the whole preference form and compact navigation keeps accessible controls',()=>{
 const html=readFileSync(new URL('../public/index.html',import.meta.url),'utf8'),app=readFileSync(new URL('../public/app.js',import.meta.url),'utf8');
 const {document}=parseHTML(html);
 assert.equal(document.querySelector('.preferences'),null);
 for(const name of ['budget','keep','notes','width','length'])assert.equal(document.querySelector('#design-form [name="'+name+'"]'),null);
 assert.equal(document.querySelector('[data-action="room-menu"]'),null);
 assert.equal(document.querySelector('#shopping [data-action="designs"]').getAttribute('aria-label'),'All designs');
 assert.equal(document.querySelector('#designs [data-action="original"]').getAttribute('aria-label'),'Your photo');
 assert.doesNotMatch(app,/\$\('#currency-label'\)/);
});
test('every supported language has complete waiting copy and live locale changes replace it',()=>{
 assert.equal(Object.keys(studioCopy).length,17);
 for(const [language,copy] of Object.entries(studioCopy)){
  assert.deepEqual(Object.keys(copy),Object.keys(studioCopy.en));
  for(const [key,value] of Object.entries(copy)){assert.ok(value.trim());if(language!=='en')assert.notEqual(value,studioCopy.en[key]);}
  const p=designPresentation(job(),{...options,language});
  assert.equal(p.status,copy['Your designs appear here as they’re ready.']);
  assert.ok(p.stage.includes(copy['Explore each design as soon as it’s ready.']));
 }
});
