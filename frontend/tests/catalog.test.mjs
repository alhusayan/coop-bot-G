import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

class Node extends EventTarget {
  constructor(tag='div') { super(); this.tagName=tag; this.children=[]; this.dataset={}; this.attributes={}; this.textContent=''; }
  append(...nodes) { for(const node of nodes){node.parent=this;this.children.push(node);} }
  after(node) { this.parent.append(node); }
  remove() { if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this);this.parent=null; }
  setAttribute(name,value) { this.attributes[name]=value; }
  querySelector(selector) { return selector==='[data-results-body]'?this.body:null; }
}
function setup(lang='ar') {
  const root=new Node();root.body=new Node();root.append(root.body);
  root.fzRefineBridge={context:()=>({lang})};
  const window=new EventTarget();
  const document={createElement:tag=>new Node(tag),documentElement:{lang},querySelectorAll:()=>[root]};
  vm.runInNewContext(readFileSync(new URL('../source/findzia-catalog.js',import.meta.url),'utf8'),{window,document,URL,WeakMap,Map,Set});
  const send=detail=>{const event=new Event('fz:search-progress');event.detail=detail;root.dispatchEvent(event);};
  const row={url:'https://store.example/products/1',image:'https://cdn.example/p.jpg',title:'<img onerror=alert(1)>',store:'Store',price:'12.345 KWD'};
  return {window,root,send,row};
}
test('catalog cards use direct merchant images and safe text and links',()=>{
  const {window,root,send,row}=setup();
  send({event:'catalog',source:'shopify_catalog',items:[row,{...row,url:'javascript:alert(1)'}]});
  assert.equal(window.FindziaCatalog.count(root),1);
  const section=root.children[1], card=section.children.at(-1).children[0];
  assert.match(section.children[0].textContent,/متاجر إضافية/);
  assert.equal(card.href,row.url);assert.equal(card.rel,'noopener noreferrer');
  assert.equal(card.children[0].src,row.image);
  assert.equal(card.children[1].textContent,row.title);
  assert.equal(card.children[3].textContent,'12.345 KWD');
});
test('deduplicates primary results in either arrival order',()=>{
  for(const primaryFirst of [true,false]){
    const {window,root,send,row}=setup();
    const primary={event:'result',item:{url:row.url+'?utm_source=test'}};
    if(primaryFirst)send(primary);
    send({event:'catalog',source:'shopify_catalog',items:[row,row]});
    if(!primaryFirst)send(primary);
    assert.equal(window.FindziaCatalog.count(root),0);assert.equal(root.children.length,1);
  }
});
test('new search and back-forward page retention discard live catalog results',()=>{
  const {window,root,send,row}=setup();
  for(const action of [()=>root.dispatchEvent(new Event('fz:search-reset')),()=>window.dispatchEvent(new Event('pagehide'))]){
    send({event:'catalog',source:'shopify_catalog',items:[row]});
    action();assert.equal(window.FindziaCatalog.count(root),0);assert.equal(root.children.length,1);
  }
});
test('visual search is not presented as verified exact matching in any UI language',()=>{
  for(const lang of ['ar','en','fr','de','es','it','pt','tr','zh','ja','ko','ru','hi','ur','id','ms']){
    const {root,send,row}=setup(lang);
    send({event:'catalog',source:'shopify_catalog',items:[{...row,match_type:'visual_similarity'}]});
    assert.equal(root.children[1].children.length,4);
    assert.ok(root.children[1].children[2].textContent.length>10);
  }
});
