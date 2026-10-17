import {test} from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {savedServiceArea,normalizeServiceArea,serviceResults,serviceWhatsApp} from '../source/findzia-services-state.js';
const source=readFileSync(new URL('../source/findzia-services.js',import.meta.url),'utf8');
const section=(from,to)=>source.slice(source.indexOf(from),source.indexOf(to,source.indexOf(from)));
function fixture(){
 const nodes=new Map();
 class Element{
  constructor(){this.value='';this.textContent='';this.dataset={};this.attrs={};this.children=[];this.hidden=false;this.events={};this.valid=true;}
  setAttribute(k,v){this.attrs[k]=v}removeAttribute(k){delete this.attrs[k]}
  append(...items){this.children.push(...items)}prepend(el){this.children.unshift(el)}replaceChildren(...items){this.children=items}
  addEventListener(k,fn){this.events[k]=fn}reportValidity(){return this.valid}checkValidity(){return this.valid}
  focus(){context.document.activeElement=this}blur(){context.document.activeElement=null}scrollIntoView(){this.scrolled=true}
  getBoundingClientRect(){return this.rect||{top:100,bottom:144}}close(){this.closed=true}requestSubmit(){this.submits=(this.submits||0)+1}
 }
 const $=s=>{if(!nodes.has(s))nodes.set(s,new Element());return nodes.get(s)};
 const context={$ ,URL,AbortController,language:'en',country:'KW',busy:false,ready:true,generation:0,pendingPhoto:null,retrieving:false,api:'https://api.findzia.com',
  document:{activeElement:null,createElement:()=>new Element()},window:{innerHeight:500,visualViewport:{height:280}},requestAnimationFrame:fn=>fn(),setTimeout:()=>1,clearTimeout(){},
  savedServiceArea,normalizeServiceArea,serviceResults,serviceWhatsApp,notice(){},updateLocation(){},creditLabel(){},clearPhoto(){},t:k=>k,
  read:()=>'',write(){},remember(){},normalizeArea(){},motion:()=> 'instant',icon:()=>new Element(),sessionStorage:{getItem:()=>null,removeItem(){}},
  setCountry:value=>context.country=value,root:{fzBilling:{refresh:async()=>{}}}};
 vm.createContext(context);return {context,$,run:code=>vm.runInContext(code,context)};
}
test('area survives a new session and old session storage migrates once',()=>{
 const saved=new Map(),legacy=new Map([['findzia-services-area-v2','{"area":"السالمية","country":"KW"}']]);
 function page(){const f=fixture();f.context.read=k=>saved.get(k);f.context.write=(k,v)=>saved.set(k,v);f.context.sessionStorage={getItem:k=>legacy.get(k),removeItem:k=>legacy.delete(k)};f.run(section("const areaStorageKey=",'function clearPhoto'));return f}
 const first=page();first.run('restore()');assert.equal(first.$('#svc-area').value,'السالمية');assert.equal(legacy.size,0);
 first.$('#svc-area').value='Hawally';first.run('remember()');const second=page();second.run('restore()');assert.equal(second.$('#svc-area').value,'Hawally');
 const changedCountry=page();changedCountry.context.country='GB';changedCountry.run('restore()');assert.equal(changedCountry.$('#svc-area').value,'');assert.equal(changedCountry.context.country,'GB');
});
test('directory magnifier and keyboard submit route directly to the service form once',()=>{
 const f=fixture(),queries=[];f.context.chooseService=q=>queries.push(q);f.context.renderDirectory=()=>{};
 f.run(section("const directory=$('#svc-directory');","root.querySelectorAll('.svc-page"));
 f.$('#svc-directory-query').value='  نجار  ';f.$('#svc-directory-form').onsubmit({preventDefault(){}});
 assert.equal(f.$('#svc-directory').closed,true);assert.deepEqual(queries,['نجار']);assert.equal(f.$('#svc-form').submits,1);
 f.context.busy=true;f.$('#svc-directory-form').onsubmit({preventDefault(){}});assert.equal(f.$('#svc-form').submits,1);
});
test('saved area searches without GPS; denied permission opens manual entry without charging',async()=>{
 const f=fixture(),payloads=[];let gps=0,manual=0;
 f.$('#svc-query').value='نجار';f.$('#svc-area').value='السالمية';f.$('#svc-manual-fields').hidden=true;
 f.context.locateArea=async()=>{gps++;return false};f.context.manualArea=()=>manual++;f.context.renderResults=()=>{};
 f.context.root.fzBilling={beforeSearch:async()=>true,fetch:async(url,options)=>{payloads.push(JSON.parse(options.body));return{ok:true,json:async()=>({items:[],area:'السالمية',query:'نجار'})}},refresh:async()=>{}};
 f.run(section("$('#svc-form').addEventListener('submit'","try{for(const name of"));
 await f.$('#svc-form').events.submit({preventDefault(){}});
 assert.equal(gps,0);assert.equal(payloads.length,1);assert.equal(payloads[0].area,'السالمية');assert.equal(f.context.busy,false);
 f.$('#svc-area').value='';f.context.read=()=> '1';await f.$('#svc-form').events.submit({preventDefault(){}});
 assert.equal(gps,0);assert.equal(manual,1);assert.equal(payloads.length,1);
});
test('keyboard resize scrolls only the focused city field when it would be covered',()=>{
 const f=fixture(),area=f.$('#svc-area');f.run(section('function keepAreaVisible()','function normalizeArea()'));
 area.rect={top:260,bottom:308};f.run('keepAreaVisible()');assert.equal(area.scrolled,undefined);
 area.focus();f.run('keepAreaVisible()');assert.equal(area.scrolled,true);
 area.scrolled=false;area.rect={top:50,bottom:94};f.run('keepAreaVisible()');assert.equal(area.scrolled,false);
});
test('results use a short heading and labelled icon-only contacts',()=>{
 const f=fixture();f.context.results={query:'A very long request that belongs in the search input',area:'Salmiya',items:[{title:'Fixture carpenter',tel:'tel:+96555551234',phone:'+96555551234',website:'https://example.com',whatsapp_source:'https://example.com',whatsapp:'https://wa.me/96555551234'}]};
 f.run(section('function node(','const cats='));f.run(section('function text(','function creditLabel'));f.run(section('function safeLink(','function showCreditLimit'));f.run('renderResults(false)');
 assert.equal(f.$('#svc-results-title').textContent,'resultsHeading');
 const card=f.$('#svc-cards').children[0],actions=card.children[1];
 for(const contact of actions.children.slice(0,2)){assert.equal(contact.textContent,'');assert.ok(contact.attrs['aria-label'].includes('Fixture carpenter'));assert.ok(contact.children.length)}
 assert.equal(actions.children[0].href,'tel:+96555551234');assert.equal(actions.children[1].href,'https://wa.me/96555551234');
});

test('switching country clears in-flight results and restores only that country’s saved area',()=>{
 const f=fixture(),saved=new Map();f.context.read=k=>saved.get(k);f.context.write=(k,v)=>saved.set(k,v);f.context.codes=['KW','SA'];f.context.locationSequence=0;f.context.locating=false;f.context.syncSelection=()=>{};
 f.run(section('const areaStorageKey=','function clearPhoto'));
 f.$('#svc-area').value='Salmiya';f.run('remember()');f.context.country='SA';f.$('#svc-area').value='Riyadh';f.run('remember()');
 let aborted=0;f.context.searchAbort={abort:()=>aborted++};f.context.busy=true;f.context.retrieving=true;f.context.results={items:[{title:'Old city'}]};
 f.run(section('const changeCountry=','$('+'\'#svc-country\').onchange'));
 f.run("changeCountry('KW')");assert.equal(f.context.country,'KW');assert.equal(f.$('#svc-area').value,'Salmiya');assert.equal(aborted,1);assert.equal(f.context.busy,false);assert.equal(f.context.results,null);assert.equal(f.$('#svc-results').hidden,true);
 f.run("changeCountry('SA')");assert.equal(f.$('#svc-area').value,'Riyadh');
});
