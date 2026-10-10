import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
class Node extends EventTarget {
 constructor(){super();this.children=[];this.dataset={};this.textContent='';}
 append(...nodes){for(const n of nodes){n.parent=this;this.children.push(n);}}
 before(n){n.parent=this.parent;this.parent.children.splice(this.parent.children.indexOf(this),0,n);}
 after(n){this.parent.append(n);} remove(){if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this);}
 setAttribute(){} querySelector(s){return s==='[data-filter-seg]'?this.filters:s==='[data-results-body]'?this.body:null;}
}
function setup(lang='ar',preview=false,filters=false){
 const root=new Node();root.body=new Node();root.append(root.body);if(preview)root.dataset.choicePreview='true';
 if(filters)root.filters=new Node();
 let paints=0;root.fzRefineBridge={context:()=>({lang,country:'KW'}),renderCatalog:()=>paints++};
 const window=new EventTarget(),document={createElement:()=>new Node(),documentElement:{lang},querySelectorAll:()=>[root]};
 vm.runInNewContext(readFileSync(new URL('../source/findzia-catalog.js',import.meta.url),'utf8'),{window,document,URL,WeakMap,Map,Set});
 const send=detail=>{const e=new Event('fz:search-progress');e.detail=detail;root.dispatchEvent(e);};
 const row={url:'https://store.example/products/1',image:'https://cdn.example/p.jpg',title:'<img onerror=alert(1)>',store:'Store',price:'12.345 KWD',source:'shopify_catalog',cacheable:false};
 return {window,root,send,row,api:window.FindziaCatalog,paints:()=>paints};
}
const event=items=>({event:'catalog',source:'shopify_catalog',items});
test('public catalog joins common rows, rejects unsafe URLs, never adds a separate section',()=>{
 const {root,send,row,api,paints}=setup();send(event([row,{...row,url:'javascript:alert(1)'}]));
 const rows=api.combine(root,[]);assert.equal(rows.length,1);assert.equal(root.children.length,1);assert.equal(paints(),1);
 assert.equal(rows[0].image,row.image);assert.equal(rows[0].title,row.title);assert.equal(rows[0].market_scope,'unknown');
});
test('currency and search country cannot establish local or global country',()=>{
 const {api}=setup();for(const price of ['12 KWD','12 USD']){
  const r=api.displayMarket({country:'kw',market_scope:'local',price,search_country:'KW'},'KW');
  assert.equal(r.market_scope,'unknown');assert.equal(r.flag,'');assert.equal(r.price,price);
 }
 for(const origin of ['KW','US']){
  const row=api.displayMarket({merchant_country:origin,merchant_country_evidence:'shopify_origin_filter',market_policy:'merchant-evidence-v2',price:'12 USD'},'KW');
  assert.equal(row.market_scope,origin==='KW'?'local':'global');
 }
});
test('deduplicates both arrival orders while preserving local evidence without mutating saved primary rows',()=>{
 for(const first of [true,false]){
  const {root,send,row,api}=setup();const primary={...row,source:'google',url:row.url+'?srsltid=abc',country:'kw'};
  const local={...row,url:row.url+'?variant=123&_gsid=track&utm_source=shopify',merchant_country:'KW',merchant_country_evidence:'shopify_origin_filter',market_policy:'merchant-evidence-v2'};
  if(first)send({event:'result',item:primary});send(event([local]));if(!first)send({event:'upsert',item:primary});
  const combined=api.combine(root,[primary]);assert.equal(combined.length,1);assert.equal(combined[0].market_scope,'local');
  assert.equal(primary.merchant_country,undefined);assert.equal(combined[0].source,'google');
 }
});
test('distinct explicit variants remain separate offers',()=>{
 const {root,send,row,api}=setup();send(event([{...row,url:row.url+'?variant=1'},{...row,url:row.url+'?variant=2'}]));
 assert.equal(api.combine(root,[]).length,2);
});
test('new search and bfcache navigation discard ephemeral results',()=>{
 const {window,root,send,row,api}=setup();for(const clear of [()=>root.dispatchEvent(new Event('fz:search-reset')),()=>window.dispatchEvent(new Event('pagehide'))]){
  send(event([row]));clear();assert.equal(api.count(root),0);assert.equal(api.combine(root,[]).length,0);
 }
});
test('visual similarity and uncertain country labels are available in all 16 languages',()=>{
 for(const language of ['ar','en','fr','de','es','it','pt','tr','zh','ja','ko','ru','hi','ur','id','ms']){
  const {root,row,api}=setup(language);assert.equal(api.labels(root,{...row,match_type:'visual_similarity'}).length,3);
  assert.ok(api.unknownLabel(root).length>5);
 }
});
test('existing private One preview retains its live supplement',()=>{
 const {root,row,send,api}=setup('ar',true);send(event([row]));assert.equal(root.children.length,2);
 const card=root.children[1].children.at(-1).children[0];assert.equal(card.children[0].src,row.image);assert.equal(card.children[1].textContent,row.title);
 assert.equal(api.combine(root,[]).length,0);
});
for(const file of ['findzia-home.liquid','findzia-one.liquid']){
 const source=readFileSync(new URL('../source/'+file,import.meta.url),'utf8');
 test(file+': common grouping keeps unknown geography out of local/global and photo neighbors in similar',()=>{
  const code=source.split('\n').filter(line=>line.startsWith('function Fr(')||line.startsWith('function Gr(')).join('\n');
  const c={fzIsSocial:()=>false,fzPhotoAlternative:()=>false,n:'KW',kr:()=>''};vm.createContext(c);vm.runInContext(code,c);
  assert.equal(c.Fr({market_scope:'unknown'}),'unknown');assert.equal(c.Fr({market_scope:'local'}),'local');assert.equal(c.Fr({market_scope:'global'}),'global');
  assert.equal(c.Fr({source:'shopify_catalog',market_scope:'local',match_type:'visual_similarity'}),'alternative');
  assert.equal(c.Gr([{market_scope:'unknown'}])[0].id,'unknown');
 });
 test(file+': catalog rendering bypasses image processing and saving',()=>{
  const start=source.indexOf('function rt(row)'),end=source.indexOf('\n',start);
  const c={sr:v=>String(v).replaceAll('<','&lt;').replaceAll('"','&quot;'),br:r=>r.url};vm.createContext(c);vm.runInContext(source.slice(start,end),c);
  const html=c.rt({source:'shopify_catalog',url:'https://store.example/p',image:'https://cdn.example/p.jpg',title:'<unsafe>'});
  assert.match(html,/data-live-catalog-image src="https:\/\/cdn.example\/p.jpg"/);assert.match(html,/&lt;unsafe>/);
  assert.match(source,/function Zr\(e\)\{if\(e.source==='shopify_catalog'\)return ''/);
  assert.match(source,/function Dt\(\).*items:Mt\(U\)/);
  assert.match(source,/function ht\(row\)\{if\(row.source==='shopify_catalog'\)/);
 });
}

test('public filter buttons are moved from hidden legacy header into visible flow and reset with search',()=>{
 const {root,send,row}=setup('ar',false,true);
 const nav=root.children[0];assert.equal(nav.hidden,true);assert.equal(nav.children[0],root.filters);
 send(event([row]));assert.equal(nav.hidden,false);
 root.dispatchEvent(new Event('fz:search-reset'));assert.equal(nav.hidden,true);
});
