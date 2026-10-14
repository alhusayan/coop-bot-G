import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {pageEvidence,validateExtracted,extractPageDetails,createDetailsService,detailURL,factKind} from '../product-details.mjs';
const fixture=name=>readFileSync(new URL('./fixtures/'+name+'-specs.html',import.meta.url),'utf8');
const darURL='https://dar-ezz.com/products/%D8%B7%D9%82%D9%85';
const homeURL='https://www.homecentre.com/sa/ar/buy-rustic-comfort-marble-top-coffee-table/p/165438105';

test('actual Dar Ezz description preserves both table sizes and explicit solid-wood material',()=>{
 const page=pageEvidence(fixture('darezz'),darURL);
 assert.equal(page.facts.find(f=>f.kind==='color').value,'أسود مع خشبي - بني مع خشبي');
 assert.equal(page.facts.find(f=>f.kind==='material').value,'خشب صلب');
 assert.deepEqual(page.facts.filter(f=>f.kind==='dimensions').map(f=>[f.label,f.value]),[
  ['طاولة القهوة','العرض 80 سم - العمق 80 سم الارتفاع 33 سم'],
  ['طاولة جانبية','العرض 55 سم - العمق 55 سم -الارتفاع 40 سم']
 ]);
});

test('actual Home Centre div grids preserve axis units and distinguish marble top from solid-wood legs',()=>{
 const page=pageEvidence(fixture('homecentre'),homeURL);
 assert.equal(page.facts.find(f=>f.kind==='color').value,'بلوطي/أبيض');
 assert.deepEqual(page.facts.filter(f=>['width','depth','height'].includes(f.kind)).map(f=>[f.kind,f.value]),[['width','100 سم'],['depth','100 سم'],['height','40 سم']]);
 assert.deepEqual(page.facts.filter(f=>f.kind==='material').map(f=>[f.label,f.value]),[['خامة الأرجل','خشب صلب'],['خامة السطح','رخام']]);
 assert.ok(page.facts.some(f=>f.kind==='assembly'&&f.value==='نعم'));
});

test('tables and definition lists support labels in all 17 UI languages, including hidden accordions',()=>{
 const labels=['Colour','اللون','Farbe','Couleur','Colore','Color','Cor','Renk','Цвет','色','颜色','색상','रंग','رنگ','Warna','Warna','Kleur'];
 for(const label of labels){assert.equal(factKind(label),'color',label);const page=pageEvidence(`<html><body><main><h1>Chair</h1><details><summary>Details</summary><dl><dt>${label}</dt><dd>Olive</dd></dl><table><tr><th>Material</th><td>Oak veneer</td></tr></table></details></main></body></html>`,'https://store.example/products/chair');assert.ok(page.facts.some(f=>f.kind==='color'&&f.value==='Olive'),label);assert.ok(page.facts.some(f=>f.kind==='material'&&f.value==='Oak veneer'));}
});

test('embedded product descriptions are read, recommendation and image dimensions are excluded',()=>{
 const product={'@type':'Product',name:'Console',color:'White',image:{width:1800,height:1200},url:'https://store.example/products/console'};
 const html=`<html><body><main><h1>Console</h1><div class="recommended"><div><span>Material</span><span>Gold</span></div></div></main><script type="application/ld+json">${JSON.stringify(product)}</script><script id="__NEXT_DATA__" type="application/json">${JSON.stringify({props:{product:{name:'Console',description:'Top: marble. Frame: oak veneer.',variants:[{id:2,title:'Small / white',option1:'Small',option2:'white'}]},recommendations:[{name:'Table',description:'Width 500 cm'}]}})}</script></body></html>`;
 const page=pageEvidence(html,product.url+'?variant=2');
 assert.match(page.text,/Frame: oak veneer/);assert.match(page.text,/Selected variant:.*Small/);
 assert.doesNotMatch(page.text,/Gold|500 cm|1800|1200/);assert.ok(!page.facts.some(f=>f.kind==='width'));
});

test('AI facts require exact merchant evidence and cannot introduce or convert numbers',()=>{
 const page=pageEvidence(fixture('darezz'),darURL),quote=page.facts.find(f=>f.label==='طاولة القهوة').quote;
 const result=validateExtracted({facts:[
  {kind:'dimensions',label:'Coffee table',value:'Width 80 cm · Depth 80 cm · Height 33 cm',quote},
  {kind:'dimensions',label:'Coffee table',value:'90 × 80 × 33 cm',quote},
  {kind:'dimensions',label:'Coffee table',value:'31.5 × 31.5 × 13 in',quote},
  {kind:'material',label:'Material',value:'Solid oak',quote:'Material: solid oak'},
  {kind:'price',label:'Price',value:'1',quote}
 ]},page);
 assert.equal(result.length,1);assert.equal(result[0].value,'Width 80 cm · Depth 80 cm · Height 33 cm');
});

test('model failure preserves real DOM facts and reports partial retrieval rather than missing store data',async()=>{
 const page=pageEvidence(fixture('homecentre'),homeURL);
 const result=await extractPageDetails(page,'ar',{model:async()=>{throw Error('timeout')}});
 assert.equal(result.status,'partial');assert.ok(result.facts.some(f=>f.label==='خامة السطح'&&f.value==='رخام'));
});

test('page fetches coalesce, respect concurrency, cache across restarts and keep variant URLs distinct',async()=>{
 const directory=mkdtempSync(join(tmpdir(),'spec-cache-'));let fetched=0,started=0,active=0,peak=0;const releases=[];
 const service=createDetailsService({directory,concurrency:2,onStart:()=>started++,log:()=>{},fetchPage:async url=>{fetched++;active++;peak=Math.max(peak,active);await new Promise(r=>releases.push(r));active--;return {html:fixture('darezz'),url};},model:async()=>({facts:[]})});
 try{
  const a=service.request(darURL,'ar','owner'),b=service.request(darURL+'?utm_source=test','ar','owner');assert.equal(a.key,b.key);
  const variant=service.request(darURL+'?variant=123','ar','owner');assert.notEqual(a.key,variant.key);
  const third=service.request(darURL+'?variant=456','ar','owner');assert.equal(fetched,2);assert.equal(started,3);
  while(releases.length)releases.shift()();await new Promise(r=>setImmediate(r));while(releases.length)releases.shift()();await new Promise(r=>setImmediate(r));
  assert.equal(peak,2);assert.equal(service.get(a.key).status,'ready');assert.equal(service.get(third.key).status,'ready');
  const restored=createDetailsService({directory,onStart:()=>{throw Error('must be cached')},fetchPage:()=>{throw Error('must not refetch')}});
  assert.equal(restored.request(darURL,'ar','owner').status,'ready');assert.equal(fetched,3);
 }finally{rmSync(directory,{recursive:true,force:true});}
});

test('private targets are rejected and blocked pages are explicitly unavailable',async()=>{
 for(const url of ['http://store.example/products/x','https://localhost/x','https://127.0.0.1/x','https://169.254.169.254/x','https://10.1.2.3/x','https://user:password@store.example/x'])assert.throws(()=>detailURL(url));
 const service=createDetailsService({fetchPage:async()=>{throw Error('no_page')},log:()=>{}});const value=service.request(darURL,'ar','owner');await new Promise(r=>setImmediate(r));assert.equal(service.get(value.key).status,'unavailable');assert.deepEqual(service.get(value.key).facts,[]);
});
