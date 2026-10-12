import test from 'node:test';
import assert from 'node:assert/strict';
import {parseHTML} from 'linkedom';
import {readFileSync} from 'node:fs';
test('one design opens directly with real products; wishes are visible and Redesign never asks for product choices',async()=>{
 const {document,window}=parseHTML(readFileSync(new URL('../public/index.html',import.meta.url),'utf8'));
 Object.assign(globalThis,{document,window,location:{origin:'http://localhost',pathname:'/'},matchMedia:()=>({matches:true}),localStorage:{getItem:()=>null,setItem:()=>{}},Image:class{set src(v){this.onload?.();}async decode(){}}});
 window.scrollTo=()=>{};document.querySelector('#design-canvas').getBoundingClientRect=()=>({width:500,height:400});const dialog=document.querySelector('#sheet');dialog.showModal=()=>dialog.open=true;dialog.close=()=>dialog.open=false;
 assert.equal(document.querySelector('#notes').closest('details'),null);assert.match(document.querySelector('#generate-button').textContent,/Design my room/);assert.doesNotMatch(document.body.textContent,/Three designs|Create 3/);
 const item={id:'1',name_en:'Chair',mode:'ready',status:'done',quantity:2,box:[10,10,700,500],offers:[{title:'Real chair',link:'https://safathome.com/chair/p',image:'https://example.com/chair.jpg',dimensions:'W: 80 cm · D: 85 cm · H: 90 cm'}],alternatives:[]};
 const job={id:'b'.repeat(24),flow:'catalog-first-v1',revision:1,options:{market:'KW'},room:'Living room',original:'/original.jpg',designs:[{title:'Your real room',image:'/real.jpg',status:'complete',items:[item],inventory_revision:123}]};
 const calls=[];globalThis.fetch=async(path,opt={})=>{calls.push(path);if(path.endsWith('/redesign')){job.revision++;job.designs[0].status='generating';job.designs[0].progress={stage:'sourcing'};job.designs[0].catalog_progress={completed:1,total:3};}return new Response(JSON.stringify(path==='/api/config'?{markets:{KW:{en:'Kuwait',currency:'KWD',flag:'🇰🇼'}}}:path==='/api/jobs'?{jobs:[job]}:job));};
 await import('../public/app.js');const click=el=>el.dispatchEvent(new window.Event('click',{bubbles:true}));const settle=()=>new Promise(r=>setTimeout(r,15));
 click(document.querySelector('[data-action="history"]'));await settle();click(document.querySelector('[data-action="load-job"]'));await settle();
 assert.equal(document.querySelector('#shopping').classList.contains('hidden'),false);assert.equal(document.querySelector('[data-action="choose"]'),null);assert.equal(document.querySelector('#selected-image').getAttribute('src'),'/real.jpg');assert.doesNotMatch(document.querySelector('#finish-panel').textContent,/Finish my room/);assert.ok(document.querySelector('[data-action="redesign"]'));
 click(document.querySelector('[data-action="redesign"]'));await settle();assert.ok(calls.some(x=>x.endsWith('/redesign')));assert.equal(document.querySelector('#designs').classList.contains('hidden'),false);assert.match(document.querySelector('#design-grid').textContent,/1 of 3 searches checked/);assert.equal(document.querySelector('[data-action="choose"]'),null);
 click(document.querySelector('[data-action="home"]'));
});
