import {test} from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
function scene(){
 const tasks=new Map(),motions=[];let id=0;
 class Element{
  constructor(){this.dataset={};this.attributes={};this.children=[];this.style={};this.textContent='';this.hidden=false;}
  append(...items){this.children.push(...items)}replaceChildren(...items){this.children=items}
  setAttribute(k,v){this.attributes[k]=v}removeAttribute(k){delete this.attributes[k]}getAttribute(k){return this.attributes[k]}
  get firstElementChild(){return this.children[0]}
  animate(frames){motions.push(frames);return{cancel(){}}}
 }
 const window={},document={documentElement:{hasAttribute:()=>true},readyState:'loading',createElement:()=>new Element(),addEventListener(){}};
 const context={window,document,URL,Intl,Map,Set,matchMedia:()=>({matches:false}),setTimeout:fn=>{tasks.set(++id,fn);return id},clearTimeout:key=>tasks.delete(key)};
 vm.runInNewContext(readFileSync(new URL('../source/findzia-choice-trial.js',import.meta.url),'utf8'),context);
 return{...window.FindziaChoice,Element,motions,flush(){let n=0;while(tasks.size){if(++n>100)throw Error('Animation did not settle');const [key,fn]=tasks.entries().next().value;tasks.delete(key);fn();}},tasks};
}
test('waiting motif is decorative, with no percentage or simulated store data',()=>{
 const f=scene(),motif=f.searchMotif();assert.equal(motif.getAttribute('aria-hidden'),'true');assert.equal(motif.children.length,3);assert.equal(motif.textContent,'');
});
test('calm price motion settles on real incoming quotes and preserves exact final money',()=>{
 const f=scene(),node=new f.Element(),quotes=[],reels=new f.PriceReels(node,row=>quotes.push(row));
 reels.spin([{url:'https://store.example/item',store:'Store',money:{amount:26.5,currency:'KWD'}}]);f.flush();
 assert.equal(node.dataset.quote,'offer');assert.equal(node.getAttribute('aria-label'),'26.500 KWD · Store');assert.equal(f.tasks.size,0);
 let landed=0;reels.land({amount:19.75,currency:'KWD'},()=>landed++);f.flush();
 assert.equal(node.getAttribute('aria-label'),'19.750 KWD');assert.equal(node.dataset.quote,'final');assert.equal(landed,1);
 assert.ok(f.motions.length>0);assert.ok(f.motions.flat().every(frame=>!String(frame.transform).includes('rotateX')));
 assert.deepEqual(reels.cells.map(cell=>cell.digit).join(''),'19750');
});
