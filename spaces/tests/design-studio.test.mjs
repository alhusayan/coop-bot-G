import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseHTML} from 'linkedom';
import {designPresentation,createStyleTour} from '../public/design-studio.js';
import {sceneText} from '../public/space-scene-copy.js';
import {studioCopy} from '../public/design-studio-copy.js';
import {patchHTML} from '../public/live-view.js';
globalThis.document=undefined;
const options={escape:s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),icon:()=>'',translate:s=>s};
const job=()=>({id:'room-a',original:'/original.jpg',designs:[0,1,2].map(i=>({title:'Style '+i,palette:['#abcdef'],status:'generating',image:null}))});
test('pending designs show one original-photo workspace and no disabled result cards',()=>{
 const result=designPresentation(job(),options),{document}=parseHTML(result.stage);
 assert.equal(result.cards,'');assert.equal(result.pending,3);assert.equal(result.ready,0);
 assert.equal(document.querySelectorAll('img').length,1);assert.equal(document.querySelectorAll('[data-action=studio-style]').length,0);
 assert.doesNotMatch(result.stage,/disabled|filter:blur|%|progressbar/);
});
test('waiting stages follow server phases, with no invented timer progress',()=>{
 const j=job();
 for(const [phase,label] of [['understanding','Understanding your room…'],['creating','Designing your space…'],['checking','Reviewing the details…']]){
  j.designs.forEach(d=>d.generation_phase=phase);
  const result=designPresentation(j,{...options,slow:true}),{document}=parseHTML(result.stage);
  assert.equal(result.status,label);
  assert.equal(document.querySelector('h2').textContent,label);
  assert.equal(document.querySelector('[aria-current=step]').textContent.slice(1),label);
  assert.equal(document.querySelectorAll('.studio-steps li').length,3);
  assert.equal(document.querySelector('.scene-breath'),null);
  assert.ok(document.querySelector('.studio-drawing svg'));
 }
 const disconnected=parseHTML(designPresentation(j,{...options,reconnecting:true}).stage).document;
 assert.equal(disconnected.querySelector('[aria-current=step]'),null,'connection loss does not pretend work is advancing');
});
test('style inspiration changes without replacing the photo or animating the room surface',t=>{
 const j=job(),{document}=parseHTML('<div id="studio"></div>');t.mock.property(globalThis,'document',document);
 const root=document.querySelector('#studio');patchHTML(root,designPresentation(j,{...options,styleIndex:0}).stage);
 const photo=root.querySelector('img'),drawing=root.querySelector('.studio-drawing');
 patchHTML(root,designPresentation(j,{...options,styleIndex:1}).stage);
 assert.equal(root.querySelector('img'),photo);assert.equal(root.querySelector('.studio-drawing'),drawing);
 assert.match(root.querySelector('.studio-inspiration').textContent,/Earthy colours/);
 assert.equal(root.querySelectorAll('.studio-palette i').length,3);
 assert.equal(root.querySelectorAll('.studio-inspiration img').length,0);
});
test('a later-index result is immediately usable and stays first when another design arrives',t=>{
 const j=job();j.designs[2].image='/two.jpg';j.designs[2].status='ready';
 const a=designPresentation(j,{...options,order:[2]});
 assert.equal(a.ready,1);assert.equal(a.pending,2);assert.match(a.cards,/data-index="2"/);assert.doesNotMatch(a.cards,/data-index="0"|disabled/);assert.doesNotMatch(a.stage,/studio-photo-wrap/);
 const {document}=parseHTML('<html><body><div id="grid"></div></body></html>');t.mock.property(globalThis,'document',document);
 const grid=document.getElementById('grid');patchHTML(grid,a.cards);const first=grid.firstElementChild,image=first.querySelector('img');
 j.designs[0].image='/zero.jpg';j.designs[0].status='ready';
 const b=designPresentation(j,{...options,order:[2,0]});patchHTML(grid,b.cards);
 assert.equal(grid.firstElementChild,first);assert.equal(first.querySelector('img'),image);assert.equal(grid.querySelectorAll('.design-image[data-action="choose"]')[1].dataset.index,'0');
});
test('completion removes activity; errors retain correct retry indexes; reconnection never claims progress',()=>{
 const j=job();j.designs.forEach((d,i)=>{d.image='/'+i+'.jpg';d.status='ready';});
 assert.equal(designPresentation(j,options).stage,'');
 j.designs[1].image=null;j.designs[1].status='error';
 const failed=designPresentation(j,options);assert.equal(failed.pending,0);assert.match(failed.cards,/data-action="retry" data-index="1"/);
 const slow=designPresentation(job(),{...options,slow:true});assert.match(slow.stage,/No need to start again/);
 const lost=designPresentation(job(),{...options,slow:true,reconnecting:true});assert.match(lost.status,/Reconnecting/);assert.doesNotMatch(lost.stage,/No need to start again/);
});
test('workspace keeps optional preferences and labelled design navigation',()=>{
 const html=readFileSync(new URL('../public/index.html',import.meta.url),'utf8'),app=readFileSync(new URL('../public/app.js',import.meta.url),'utf8');
 const {document}=parseHTML(html);
 assert.equal(document.querySelector('.preferences'),null);
 for(const name of ['budget','keep','notes','width','length'])assert.equal(document.querySelector('#design-form [name="'+name+'"]'),null);
 assert.equal(document.querySelector('[data-action="room-menu"]'),null);
 assert.equal(document.querySelector('#design-variants').getAttribute('aria-label'),'Choose a design');
 assert.equal(document.querySelector('#shopping [data-action="designs"]'),null);
 assert.equal(document.querySelector('#designs [data-action="original"]').getAttribute('aria-label'),'Your photo');
 assert.doesNotMatch(app,/\$\('#currency-label'\)/);
});
test('every supported language has complete waiting copy and live locale changes replace it',()=>{
 assert.equal(Object.keys(studioCopy).length,17);
 for(const [language,copy] of Object.entries(studioCopy)){
  assert.deepEqual(Object.keys(copy),Object.keys(studioCopy.en));
  for(const [key,value] of Object.entries(copy)){assert.ok(value.trim());if(language!=='en')assert.notEqual(value,studioCopy.en[key]);}
  const p=designPresentation(job(),{...options,language});
  assert.equal(p.status,sceneText(language,'working'));
  assert.ok(p.stage.includes(sceneText(language,'working')));
 }
});

test('generation polls preserve the full original image without a second control panel',t=>{
 const j=job(),{document}=parseHTML('<html><body><div id="studio"></div></body></html>');t.mock.property(globalThis,'document',document);
 const root=document.getElementById('studio');patchHTML(root,designPresentation(j,options).stage);
 const photo=root.querySelector('img');
 patchHTML(root,designPresentation(j,{...options,slow:true}).stage);
 assert.equal(root.querySelector('img'),photo);assert.ok(photo.closest('.scene-media'));
 assert.equal(root.querySelectorAll('button,input,textarea').length,0);
 assert.equal(root.querySelectorAll('.scene-wait').length,1);
 assert.equal(root.querySelectorAll('img').length,1);
});
test('style tour survives polls, respects manual choice and stops off-screen, on results and with reduced motion',()=>{
 let callback,nextId=0,changed=0;const tasks=new Map();
 const tour=createStyleTour({onChange:()=>changed++,schedule(fn,ms){assert.equal(ms,6500);callback=fn;tasks.set(++nextId,fn);return nextId;},cancel:id=>tasks.delete(id)});
 const state={jobId:'one',indexes:[0,1,2],active:true,reduced:false};
 assert.equal(tour.sync(state).styleIndex,0);tour.sync(state);assert.equal(nextId,1,'polling must not restart the tour');
 tasks.clear();callback();assert.equal(tour.sync(state).styleIndex,1);assert.equal(changed,1);
 tour.choose(2);assert.equal(tasks.size,0);assert.deepEqual(tour.sync(state),{styleIndex:2,paused:true});
 tour.choose(9);assert.equal(changed,2,'ignore invalid style indexes');
 tour.toggle();assert.equal(tasks.size,1);tour.sync({...state,active:false});assert.equal(tasks.size,0);
 tour.sync(state);assert.equal(tasks.size,1);tour.stop();assert.equal(tasks.size,0);
 assert.equal(tour.sync({...state,jobId:'two',reduced:true}).styleIndex,0);assert.equal(tasks.size,0);
 tour.choose(1);assert.equal(tasks.size,0);assert.equal(tour.sync({...state,jobId:'two',reduced:true}).styleIndex,1);
});

test('design photos open the selected design directly instead of a duplicate preview',()=>{
 const j=job();j.designs[1].image='/one.jpg';
 const {document}=parseHTML(designPresentation(j,options).cards);
 const photo=document.querySelector('.design-image');assert.equal(photo.dataset.action,'choose');assert.equal(photo.dataset.index,'1');
 assert.equal(photo.querySelector('img').getAttribute('draggable'),'false');
 assert.equal(document.querySelector('h2,.design-card-body'),null);
 assert.equal(photo.getAttribute('aria-label').includes('Style 1'),true);
 assert.doesNotMatch(readFileSync(new URL('../public/app.js',import.meta.url),'utf8'),/case 'preview':/);
});

test('optional customization stays inside the filter and remains form-associated',()=>{
 const {document}=parseHTML(readFileSync(new URL('../public/index.html',import.meta.url),'utf8'));
 assert.equal(document.querySelectorAll('#setup textarea').length,0);
 assert.equal(document.querySelectorAll('#space-options #design-request').length,1);
 assert.equal(document.querySelector('#design-request').getAttribute('form'),'design-form');
 assert.equal(document.querySelectorAll('#space-options input[name=scope]').length,3);
 for(const field of document.querySelectorAll('#space-options input,#space-options textarea'))assert.equal(field.getAttribute('form'),'design-form');
 assert.equal(document.querySelector('#space-options [name=scope][checked]').value,'full');
 assert.equal(document.querySelectorAll('#home .scene-cover').length,1);
 assert.equal(document.querySelector('#home input,#home textarea'),null);
});
