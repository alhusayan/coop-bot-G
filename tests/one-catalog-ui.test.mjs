import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

const source=readFileSync(new URL('../frontend/source/findzia-one-catalog.js',import.meta.url),'utf8');
class DetailEvent extends Event{constructor(type,options={}){super(type);this.detail=options.detail;}}
function setup(preview=true){
  const root=new EventTarget();root.dataset={choicePreview:String(preview)};
  const state={generation:1};let primary=[];
  const original=()=>primary;
  root.fzRefineBridge={context:()=>state,choiceRows:original,choiceLogRows:original};
  const document=new EventTarget();document.readyState='complete';document.querySelectorAll=()=>[root];
  vm.runInNewContext(source,{URL,document,CustomEvent:DetailEvent});
  return {root,state,original,setRows:rows=>primary=rows,
    deliver:items=>root.dispatchEvent(new DetailEvent('fz:search-progress',{detail:{event:'catalog',source:'shopify_catalog',items}}))};
}
const offer=(id='a')=>({source:'shopify_catalog',cacheable:false,evaluation_token:'signed-'+id,
  url:'https://shop.example/products/'+id+'?variant=123',image:'https://cdn.shopify.com/'+id+'.jpg',
  title:'Headphones '+id,store:'Store',market_country:'kw',market_scope:'local',price_amount:12.345,currency:'KWD'});

test('signed catalog offers join choice and live prices, capped with space for both sources',()=>{
  const h=setup();h.setRows(Array.from({length:48},(_,i)=>({token:'native'+i,url:'https://native.example/'+i})));
  h.deliver(Array.from({length:20},(_,i)=>offer(String(i))));
  const rows=h.root.fzRefineBridge.choiceRows();assert.equal(rows.length,48);
  assert.equal(rows.filter(r=>r.source==='shopify_catalog').length,18);
  assert.equal(rows.at(-1).money.amount,12.345);assert.equal(rows.at(-1).image,offer('17').image);
  assert.equal(h.root.fzRefineBridge.choiceLogRows().length,48);
});
test('new generation and reset discard catalog evidence without touching primary rows',()=>{
  const h=setup();h.deliver([offer()]);assert.equal(h.root.fzRefineBridge.choiceRows().length,1);
  h.state.generation++;assert.equal(h.root.fzRefineBridge.choiceRows().length,0);
  h.deliver([offer()]);h.root.dispatchEvent(new Event('fz:search-reset'));
  assert.equal(h.root.fzRefineBridge.choiceRows().length,0);
  h.root.fzOneCatalog.destroy();assert.equal(h.root.fzRefineBridge.choiceRows,h.original);
});
test('unsigned, unknown-market and unsafe offers never reach choice',()=>{
  const h=setup();h.deliver([{...offer(),evaluation_token:''},{...offer(),market_scope:'unknown'},
    {...offer(),image:'javascript:alert(1)'},{...offer(),cacheable:true}]);
  assert.equal(h.root.fzRefineBridge.choiceRows().length,0);
});
test('public template cannot activate the adapter',()=>{
  const h=setup(false);h.deliver([offer()]);assert.equal(h.root.fzRefineBridge.choiceRows,h.original);
  assert.equal(h.root.fzOneCatalog,undefined);
});
