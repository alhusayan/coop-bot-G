import test from 'node:test';
import assert from 'node:assert/strict';
import {parseHTML} from 'linkedom';
import {readFileSync} from 'node:fs';
test('the room preview exposes large keep/change controls, correct image and labelled measurements',async()=>{
 const {document,window}=parseHTML(readFileSync(new URL('../public/index.html',import.meta.url),'utf8'));
 Object.assign(globalThis,{document,window,location:{origin:'http://localhost',pathname:'/'},matchMedia:()=>({matches:true}),localStorage:{getItem:()=>null,setItem:()=>{}},Image:class{set src(v){this.onload?.();}async decode(){}}});
 window.scrollTo=()=>{};document.querySelector('#design-canvas').getBoundingClientRect=()=>({width:500,height:400});
 const dialog=document.querySelector('#sheet');dialog.showModal=()=>{dialog.open=true;};dialog.close=()=>{dialog.open=false;};
 const item={id:'1',name_en:'Chair',mode:'ready',status:'done',box:[10,10,700,500],offers:[],alternatives:[]};
 const job={id:'b'.repeat(24),revision:1,options:{market:'KW'},room:'Living room',original:'/original.jpg',designs:[{title:'Warm room',image:'/old.jpg',status:'complete',items:[item],finish:{status:'preview',image:'/preview.jpg',room:{width_cm:400,length_cm:500},limits:{},plan:{picks:[{id:'1',name:'Chair',offer:{title:'Chair',image:'https://example.com/chair.jpg',dimensions:'W: 80 cm'}}],skipped:[]}}}]};
 globalThis.fetch=async path=>new Response(JSON.stringify(path==='/api/config'?{markets:{KW:{en:'Kuwait',currency:'KWD',flag:'🇰🇼'}}}:path==='/api/jobs'?{jobs:[job]}:job),{headers:{'content-type':'application/json'}});
 await import('../public/app.js');
 const click=el=>el.dispatchEvent(new window.Event('click',{bubbles:true}));
 const settle=()=>new Promise(r=>setTimeout(r,15));
 click(document.querySelector('[data-action="history"]'));await settle();click(document.querySelector('[data-action="load-job"]'));await settle();click(document.querySelector('[data-action="choose"]'));await settle();
 assert.equal(document.querySelector('#selected-image').getAttribute('src'),'/preview.jpg');
 assert.match(document.querySelector('#finish-panel').textContent,/Keep this design/);assert.match(document.querySelector('#finish-panel').textContent,/Room fit is approximate/);
 assert.ok(document.querySelector('#hotspots').classList.contains('hidden'));
 click(document.querySelector('[data-action="change-finish"]'));assert.match(document.querySelector('#sheet-content').textContent,/Change a piece/);
 click(document.querySelector('[data-action="close"]'));
 // Exercise the same form used for a fresh room without manipulating app state.
 const button=document.createElement('button');button.dataset.action='finish';document.body.append(button);click(button);
 const form=document.querySelector('#finish-form');assert.ok(form);assert.equal(form.querySelector('[name="width"]').value,'4');assert.equal(form.querySelector('[name="length"]').value,'5');assert.ok(form.querySelector('[name="width"]').closest('label'));assert.match(form.textContent,/Choose my pieces/);
});
