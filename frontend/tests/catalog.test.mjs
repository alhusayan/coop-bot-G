import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
class Node extends EventTarget {
 constructor(){super();this.children=[];this.dataset={};this.textContent='';}
 append(...nodes){for(const n of nodes){n.parent=this;this.children.push(n);}}
 before(n){n.parent=this.parent;this.parent.children.splice(this.parent.children.indexOf(this),0,n);}
 after(n){this.parent.append(n);} remove(){if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this);}
 setAttribute(){} querySelector(s){return s==='[data-filter-seg]'?this.filters:s==='[data-results-body]'?this.body:s==='.fz-fixed-header-inner'?this.header:null;}
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
  const {root,row,api}=setup(language);assert.equal(api.labels(root,{...row,match_type:'visual_similarity'}).length,1);assert.ok(!api.labels(root,{...row,match_type:'visual_similarity'})[0].includes('verified'));
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
  const code=source.split('\n').filter(line=>line.startsWith('function Fr(')||line.startsWith('function Gr(')||line.startsWith('function fzIsSimilar(')||line.startsWith('function fzMatchesResultFilter(')).join('\n');
  const c={fzIsSocial:()=>false,fzPhotoAlternative:()=>false,n:'KW',kr:()=>'',O:'all'};vm.createContext(c);vm.runInContext(code,c);
  assert.equal(c.Fr({market_scope:'unknown'}),'unknown');assert.equal(c.Fr({market_scope:'local'}),'local');assert.equal(c.Fr({market_scope:'global'}),'global');
  assert.equal(c.Fr({source:'shopify_catalog',market_scope:'local',match_type:'visual_similarity'}),'local');
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

for(const file of ['findzia-home.liquid','findzia-one.liquid']){
 const source=readFileSync(new URL('../source/'+file,import.meta.url),'utf8');
 test(file+': local/global and similarity overlap without hiding offers or duplicating All',()=>{
  const code=source.split('\n').filter(line=>/^(function (Fr|Gr|fzIsSimilar|fzMatchesResultFilter)\()/.test(line)).join('\n');
  const c={fzIsSocial:r=>!!r.social_id,fzPhotoAlternative:()=>false,O:'all'};vm.createContext(c);vm.runInContext(code,c);
  const rows=[{market_scope:'local',match_type:'similar'},{market_scope:'global',match_type:'visual_similarity'}, {market_scope:'unknown',match_type:'similar'},{market_scope:'global',match_type:'exact'}];
  for(const [filter,count] of [['all',4],['local',1],['global',2],['alternative',3],['social',0]]){
   c.O=filter;const selected=rows.filter(c.fzMatchesResultFilter);assert.equal(selected.length,count);
   if(filter==='alternative'){const groups=c.Gr(selected);assert.equal(groups.length,1);assert.equal(groups[0].id,'alternative');}
   if(filter==='all'){assert.equal(c.Gr(selected)[0].id,'local');assert.equal(c.Gr(selected).flatMap(g=>g.items).length,4);}
  }
 });
 test(file+': primary and catalog storefront evidence survives display normalization in both photo filters',()=>{
  const {root,send,row,api}=setup();
  const proof={market_policy:'merchant-evidence-v2',merchant_country_evidence:'registered_storefront',match_type:'visual_similarity'};
  const primary=[{...row,...proof,source:'google_lens',url:'https://azadea.com/kw/en/buy-kipsta/54_8972682_000.html',merchant_country:'KW'},
   {...row,...proof,source:'google_lens',url:'https://gcc.luluhypermarket.com/en-kw/volleyball-assorted/p/114752',merchant_country:'KW'}];
  send(event([{...row,...proof,url:'https://alnasser.net/products/volleyball',merchant_country:'KW'},
   {...row,...proof,url:'https://ksa.alnasser.net/products/volleyball',merchant_country:'SA'}]));
  const rows=api.combine(root,primary);
  const code=source.split('\n').filter(line=>/^(function (Fr|Gr|fzIsSimilar|fzMatchesResultFilter)\()/.test(line)).join('\n');
  const c={fzIsSocial:()=>false,fzPhotoAlternative:()=>false,O:'all'};vm.createContext(c);vm.runInContext(code,c);
  const select=filter=>{c.O=filter;return rows.filter(c.fzMatchesResultFilter).map(r=>r.url);};
  const all=select('all'),local=select('local'),global=select('global'),similar=select('alternative');
  assert.equal(new Set(all).size,4);assert.equal(local.length,3);assert.equal(global.length,1);
  assert.deepEqual(similar,all);assert.ok(local.every(url=>similar.includes(url)));
  assert.ok(global.every(url=>similar.includes(url)));assert.ok(local.every(url=>!global.includes(url)));
 });
 test(file+': empty filter after partial photo success cannot show timeout or media retry',()=>{
  const c={W:{photoSearchIssue:'timeout'},e:{dataset:{},dispatchEvent(){}},ee:false,Kt:false,Vt:null,Jt:false,fzUsableResults:true,
   fzHasSearchResults:()=>true,fzMediaPending:()=>false,fzReadingAnchor:()=>null,fzCardRects:()=>new Map(),
   fzMeasureFirstCard(){},Yt(){},fzUsage(){},CustomEvent:class{},photoErrors:0,mediaErrors:0,
   fzRenderPhotoIssue(){c.photoErrors++},fzRenderMediaIssue(){},fzResultMotion(){},fzFitCinema(){},fzKeepReadingAnchor(){},Ft(){}};
  vm.createContext(c);
  vm.runInContext(source.slice(source.indexOf('function Qt(count)'),source.indexOf('function Xt()')),c);
  c.fzPaintResults=()=>c.Qt(0);
  vm.runInContext(source.slice(source.indexOf('function St(){'),source.indexOf('function fzFitCinema(){')),c);
  c.St();assert.equal(c.fzUsableResults,true);assert.equal(c.photoErrors,0);
  c.fzHasSearchResults=()=>false;c.St();assert.equal(c.photoErrors,1);
  assert.match(source,/O!=="all"&&fzHasSearchResults\(\)\?ar\("no_filter"\)/);
  assert.doesNotMatch(source,/Search stopped\. Your matches are ready to browse/);
 });
}
test('primary results also reveal filters, and an empty filter keeps navigation available',()=>{
 const {root,send}=setup('en',false,true);const nav=root.children[0],note=root.children[1];
 const emit=count=>{const ev=new Event('fz:result-count');ev.detail={count};root.dispatchEvent(ev);};
 emit(57);assert.equal(nav.hidden,false);emit(0);assert.equal(nav.hidden,false);assert.equal(note.hidden,true);
 root.dispatchEvent(new Event('fz:search-reset'));assert.equal(nav.hidden,true);
});

for(const file of ['findzia-home.liquid','findzia-one.liquid']){
 const source=readFileSync(new URL('../source/'+file,import.meta.url),'utf8');
 test(file+': storefront homepages cannot be published as priced product cards',()=>{
  const c={URL,or:v=>v,Ar:v=>v};vm.createContext(c);
  vm.runInContext(source.slice(source.indexOf('function et(row)'),source.indexOf('function fzHasSearchResults')),c);
  for(const path of ['/','/en','/ar/','/en/home','/home/','/index.html'])assert.equal(c.et({url:'https://rullart.com'+path}),'');
  const url='https://rullart.com/en/product/daily-prayer-set/prayer-set-pink-co-00076';assert.equal(c.et({url}),url);
 });
}
