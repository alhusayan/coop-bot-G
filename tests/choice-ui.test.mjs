import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {test} from 'node:test';

// A deterministic DOM/animation harness: exercises the production controller,
// not layout. Browser visual QA is a separate deployment check.
function harness(){
  let clock=0,seq=0,reduced=false;
  const timers=new Map(), animations=[];
  class Node extends EventTarget{
    constructor(tag='div'){super();this.tagName=tag;this.children=[];this.dataset={};this.style={setProperty(k,v){this[k]=v;}};this.attrs={};this.className='';this.hidden=false;this.textContent='';
      this.classList={add:(c)=>{this.className+=' '+c;},remove:(c)=>{this.className=this.className.split(' ').filter(x=>x!==c).join(' ');}};}
    get firstElementChild(){return this.children[0]||null;}
    showModal(){this.open=true;} close(){this.open=false;} focus(){}
    get lastElementChild(){return this.children[this.children.length-1]||null;}
    append(...nodes){for(const n of nodes){n.parent=this;this.children.push(n);}}
    replaceChildren(...nodes){this.children=[];this.append(...nodes);}
    before(n){const p=this.parent;n.parent=p;p.children.splice(p.children.indexOf(this),0,n);}
    remove(){if(this.parent)this.parent.children=this.parent.children.filter(x=>x!==this);}
    setAttribute(k,v){this.attrs[k]=String(v);} getAttribute(k){return this.attrs[k]??null;} removeAttribute(k){delete this.attrs[k];}
    matches(s){if(s.startsWith('.'))return this.className.split(' ').includes(s.slice(1));return !!this.attrs[s.slice(1,-1)];}
    querySelector(s){return this.querySelectorAll(s)[0]||null;}
    querySelectorAll(s){return this.children.flatMap(c=>[...(c.matches(s)?[c]:[]),...c.querySelectorAll(s)]);}
    closest(){return null;}
    animate(frames,opts){const a={frames,opts,currentTime:80,cancelled:false,cancel(){this.cancelled=true;}};animations.push(a);return a;}
    contains(n){return this===n||this.children.some(c=>c.contains(n));}
  }
  const document=new Node();document.createElement=t=>new Node(t);document.readyState='loading';
  const context={document,window:{},location:{search:''},URL,URLSearchParams,Intl,AbortController,
    CustomEvent:class extends Event{constructor(n,o={}){super(n);this.detail=o.detail;}},
    MutationObserver:class{observe(){} disconnect(){}},matchMedia:()=>({matches:reduced}),
    Date:class extends Date{static now(){return clock;}},
    setTimeout(fn,delay){const id=++seq;timers.set(id,{at:clock+delay,fn});return id;},clearTimeout(id){timers.delete(id);}};
  vm.runInNewContext(readFileSync(new URL('../frontend/source/findzia-choice.js',import.meta.url),'utf8'),context);
  async function tick(ms=0){const end=clock+ms;for(let i=0;i<100;i++){await Promise.resolve();await Promise.resolve();const next=[...timers].filter(([,v])=>v.at<=end).sort((a,b)=>a[1].at-b[1].at)[0];if(!next){clock=end;for(let j=0;j<12;j++)await Promise.resolve();return;}clock=next[1].at;timers.delete(next[0]);next[1].fn();}throw Error('timer loop');}
  const root=new Node();root.className='fz-home';root.dataset={lang:'ar',homeState:'results',choicePreview:'true'};document.append(root);
  const body=new Node();body.setAttribute('data-results-body','true');root.append(body);
  const state={generation:1,query:'camera',kind:'text',lang:'ar',country:'KW',busy:false};
  const row={token:'signed-1',url:'https://store.example/item',image:'https://store.example/photo.jpg',title:'Camera',store:'Store',key_specs:[],money:{amount:12.345,currency:'KWD'}};
  let rows=[row];root.fzRefineBridge={api:'https://api.example',context:()=>({...state}),choiceRows:()=>rows,newSearch(){state.generation++;state.query='';root.dataset.homeState='empty';}};
  const response=(r=row)=>({ok:true,json:async()=>({ok:true,status:'selected',token:r.token,url:r.url,store:r.store,money:r.money,reason:'Suitable'})});
  return {Node,root,context,state,row,response,animations,timers,tick,setRows:v=>rows=v,setReduced:v=>reduced=v,api:context.window.FindziaChoice};
}

test('streamed source prices are shown exactly, including independent flaps and final fils',async()=>{
  const h=harness(),n=new h.Node(),seen=[],reels=new h.api.PriceReels(n,row=>seen.push(row?.money.amount));
  assert.equal(h.api.moneyParts({amount:12.345,currency:'KWD'}).minor,'345');
  assert.equal(h.api.moneyParts({amount:12,currency:'JPY'}).minor,'');
  reels.spin([],'Searching');assert.equal(n.querySelectorAll('.fz-one-reel').length,0);
  assert.equal(n.querySelector('.fz-one-price-wait').textContent,'—');
  reels.spin([{...h.row,money:{amount:4.99,currency:'KWD'}}],'Searching');await h.tick(320);
  assert.deepEqual(n.querySelectorAll('.fz-one-reel').map(t=>t.dataset.digit),['4','9','9','0']);
  assert.match(n.getAttribute('aria-label'),/4.990 KWD/);
  assert.deepEqual(seen.filter(Boolean),[4.99]);
  assert.ok(new Set(h.animations.map(a=>a.opts.duration)).size>2);
  assert.ok(h.animations.every(a=>a.frames.some(f=>f.transform.includes('rotateX('))));
  const first=h.animations.slice();let done=0;
  reels.land({amount:8.125,currency:'KWD'},()=>done++);await h.tick(500);
  assert.equal(done,1);assert.equal(n.getAttribute('aria-label'),'8.125 KWD');
  assert.ok(first.every(a=>a.cancelled));
  assert.deepEqual(n.querySelectorAll('.fz-one-reel').map(t=>t.dataset.digit),['8','1','2','5']);
  assert.equal(n.dataset.spinning,'false');assert.equal(n.dataset.quote,'final');
  assert.equal(h.timers.size,0);reels.clear();
});

test('idle movement stays close to the real quote, moves both ways, and yields to a new quote',async()=>{
  const h=harness(),n=new h.Node(),reels=new h.api.PriceReels(n);const real={...h.row,money:{amount:4.99,currency:'KWD'}};
  reels.spin([real],'Comparing');await h.tick(280);
  let above=false,below=false;
  for(let i=0;i<24;i++){
    await h.tick(100);const value=reels.currentMoney.amount;
    assert.ok(Math.abs(value-4.99)<.04,value);above||=value>4.99;below||=value<4.99;
    if(n.dataset.quote==='between'&&n.dataset.spinning==='false')assert.equal(n.getAttribute('aria-label'),'Comparing');
  }
  assert.ok(above&&below);
  const next={...h.row,url:'https://store.example/new',money:{amount:36.64,currency:'KWD'}};
  reels.spin([real,next],'Comparing');await h.tick(800);
  assert.equal(reels.activeOffer.money.amount,36.64);
  assert.ok(Math.abs(reels.currentMoney.amount-36.64)<.3);
  reels.clear();assert.equal(h.timers.size,0);
});

test('reduced motion settles immediately; cancelling suppresses celebration',async()=>{
  const h=harness(),reels=new h.api.PriceReels(new h.Node());let done=0;
  h.setReduced(true);reels.spin(h.row.money);reels.land(h.row.money,()=>done++);assert.equal(done,1);assert.equal(h.animations.length,0);
  h.setReduced(false);reels.spin(h.row.money);reels.land(h.row.money,()=>done++);reels.clear();await h.tick(2000);assert.equal(done,1);assert.ok(h.animations.every(a=>a.cancelled));
});

test('one real offer, immediate merchant CTA, cheaper requests retain signed pool',async()=>{
  const h=harness(),calls=[];h.context.window.FindziaBillingFetch=async(_,url,options)=>{calls.push({url,body:JSON.parse(options.body)});return h.response();};
  h.api.mount(h.root);await h.tick(100);await h.tick(0);
  const link=h.root.querySelector('.fz-one-open');assert.equal(link.hidden,false);assert.equal(link.href,h.row.url);assert.equal(calls.length,1);
  assert.deepEqual(calls[0].body.offer_tokens,['signed-1']);assert.equal(h.root.querySelectorAll('.fz-one').length,1);
  await h.tick(1200);assert.equal(h.root.querySelector('.fz-one').dataset.state,'selected');
  h.root.querySelectorAll('.fz-one-small')[0].dispatchEvent(new Event('click'));await h.tick(100);await h.tick(0);
  assert.equal(calls[1].body.mode,'cheaper');h.root.fzOneChoice.destroy();
});

test('a late response from a cancelled search cannot replace the new result',async()=>{
  const h=harness();let resolveOld;
  h.context.window.FindziaBillingFetch=()=>new Promise(r=>resolveOld=r);
  h.api.mount(h.root);await h.tick(100);
  const next={...h.row,token:'signed-2',url:'https://store.example/new',title:'New camera'};h.state.generation=2;h.setRows([next]);
  h.context.window.FindziaBillingFetch=async()=>h.response(next);h.root.fzOneChoice.update();await h.tick(0);await h.tick(0);
  resolveOld(h.response());await h.tick(0);await h.tick(1500);
  assert.equal(h.root.querySelector('.fz-one-open').href,next.url);assert.equal(h.root.querySelector('.fz-one-title').textContent,next.title);h.root.fzOneChoice.destroy();
});

test('missing signed selection fails closed and removed offer hides its link',async()=>{
  const h=harness();h.context.window.FindziaBillingFetch=async()=>h.response();h.api.mount(h.root);await h.tick(100);await h.tick(0);
  h.setRows([]);h.root.fzOneChoice.update();assert.equal(h.root.querySelector('.fz-one-open').hidden,true);assert.equal(h.root.querySelector('.fz-one').dataset.state,'empty');h.root.fzOneChoice.destroy();
});


test('a signed-token refresh keeps the settled offer when its price is unchanged',async()=>{
  const h=harness();let calls=0;h.context.window.FindziaBillingFetch=async()=>{calls++;return h.response();};h.api.mount(h.root);await h.tick(100);await h.tick(0);await h.tick(1500);
  h.setRows([{...h.row,token:'renewed-signature'}]);h.root.fzOneChoice.update();await h.tick(0);
  assert.equal(calls,1);assert.equal(h.root.querySelector('.fz-one').dataset.state,'selected');h.root.fzOneChoice.destroy();
});


test('a corrected identity at the same price triggers a new AI decision',async()=>{
  const h=harness();let calls=0,active=h.row;h.context.window.FindziaBillingFetch=async()=>{calls++;return h.response(active);};h.api.mount(h.root);await h.tick(100);await h.tick(0);await h.tick(1500);
  active={...h.row,token:'corrected',title:'Different camera',match_type:'similar'};h.setRows([active]);h.root.fzOneChoice.update();await h.tick(0);await h.tick(0);
  assert.equal(calls,2);assert.equal(h.root.querySelector('.fz-one-title').textContent,'Different camera');h.root.fzOneChoice.destroy();
});


test('public page cannot mount the trial selection interface',()=>{
  const h=harness();delete h.root.dataset.choicePreview;h.api.mount(h.root);assert.equal(h.root.fzOneChoice,undefined);assert.equal(h.root.querySelector('.fz-one'),null);
});

test('seven live log lines retain latest real offers and deduplicate refreshes',()=>{
  const h=harness(),n=new h.Node(),log=new h.api.SearchLog(n);
  const rows=Array.from({length:12},(_,i)=>({...h.row,url:'https://store.example/'+i,title:'Product '+i,money:{amount:i+1,currency:'KWD'}}));
  log.sync(rows);assert.equal(n.children.length,7);assert.equal(log.entries.length,12);
  assert.equal(n.firstElementChild.querySelector('.fz-one-log-product').textContent,'Product 5');
  log.sync(rows);assert.equal(log.entries.length,12);
  log.sync([{...rows[11],money:{amount:2,currency:'KWD'}}]);assert.equal(log.entries.length,13);
  assert.equal(n.lastElementChild.querySelector('.fz-one-log-price').textContent,'2.000 KWD');log.clear();assert.equal(n.children.length,0);
});

test('image query stays frozen while incoming product pictures change',async()=>{
  const h=harness();h.state.kind='image';h.state.image_base64='cGhvdG8=';h.state.busy=true;h.setRows([]);
  h.context.window.FindziaBillingFetch=async()=>h.response();h.api.mount(h.root);await h.tick(100);
  const picture=h.root.querySelector('.fz-one-image'),original=picture.src;
  assert.equal(original,'data:image/jpeg;base64,cGhvdG8=');
  assert.equal(h.root.querySelector('.fz-one-price').dataset.spinning,'true');
  h.setRows([h.row]);h.root.fzOneChoice.update();assert.equal(picture.src,original);
  h.setRows([{...h.row,image:'https://store.example/other.jpg'}]);h.root.fzOneChoice.update();assert.equal(picture.src,original);
  h.setRows([h.row]);h.state.busy=false;h.root.fzOneChoice.update();await h.tick(0);await h.tick(0);
  assert.equal(picture.src,h.row.image);picture.dispatchEvent(new Event('error'));
  assert.equal(picture.src,original);assert.equal(h.root.querySelector('.fz-one-open').hidden,false);h.root.fzOneChoice.destroy();
});

test('transient 503 retries automatically without showing Could not choose',async()=>{
  const h=harness();let calls=0;
  h.context.window.FindziaBillingFetch=async()=>++calls===1?{ok:false,status:503,json:async()=>({ok:false})}:h.response();
  h.api.mount(h.root);await h.tick(100);await h.tick(0);
  assert.equal(h.root.querySelector('.fz-one').dataset.state,'pending');assert.equal(h.root.querySelectorAll('.fz-one-open')[1].hidden,true);
  await h.tick(700);await h.tick(0);await h.tick(1500);
  assert.equal(calls,2);assert.equal(h.root.querySelector('.fz-one').dataset.state,'selected');h.root.fzOneChoice.destroy();
});

test('persistent failure has a bounded retry and a recoverable results picker',async()=>{
  const h=harness();let calls=0;h.context.window.FindziaBillingFetch=async()=>{calls++;return{ok:false,status:503,json:async()=>({ok:false})};};
  h.api.mount(h.root);await h.tick(100);await h.tick(700);await h.tick(3000);
  assert.equal(calls,2);assert.equal(h.root.querySelector('.fz-one').dataset.state,'empty');
  h.root.fzOneChoice.update();assert.equal(h.root.querySelector('.fz-one').dataset.state,'empty');
  h.root.querySelectorAll('.fz-one-icon')[1].dispatchEvent(new Event('click'));
  // The icon opens current offers; selecting one is explicitly a user selection.
  assert.equal(h.root.querySelector('.fz-one-dialog').open,true);
  h.root.querySelector('.fz-one-offer-row').dispatchEvent(new Event('click'));
  assert.equal(h.root.querySelector('.fz-one-badge').textContent,'اختيارك');
  assert.equal(h.root.querySelector('.fz-one-open').href,h.row.url);assert.equal(calls,2);h.root.fzOneChoice.destroy();
});

test('removed results cannot be chosen from an already open list',async()=>{
  const h=harness();h.context.window.FindziaBillingFetch=async()=>h.response();h.api.mount(h.root);await h.tick(100);await h.tick(0);
  h.root.querySelectorAll('.fz-one-icon')[1].dispatchEvent(new Event('click'));
  const button=h.root.querySelector('.fz-one-offer-row');h.setRows([]);button.dispatchEvent(new Event('click'));
  assert.equal(h.root.querySelectorAll('.fz-one-offer-row').length,0);
  h.root.fzOneChoice.update();assert.equal(h.root.querySelector('.fz-one-open').hidden,true);h.root.fzOneChoice.destroy();
});

test('an automatic retry is cancelled when a new search starts',async()=>{
  const h=harness();let calls=0;h.context.window.FindziaBillingFetch=async()=>{calls++;return{ok:false,status:503,json:async()=>({ok:false})};};
  h.api.mount(h.root);await h.tick(100);await h.tick(0);
  h.state.generation++;h.state.busy=true;h.setRows([]);h.root.fzOneChoice.update();await h.tick(1400);
  assert.equal(calls,1);assert.equal(h.root.querySelector('.fz-one').dataset.state,'pending');h.root.fzOneChoice.destroy();
});

test('phone viewport reserves measured content and header before sizing the photo',async()=>{
  const h=harness();h.state.busy=true;h.setRows([]);h.context.window.innerHeight=660;
  h.api.mount(h.root);await h.tick(100);
  const box=h.root.querySelector('.fz-one'),picture=h.root.querySelector('.fz-one-stage');
  box.getBoundingClientRect=()=>({top:108,height:350});picture.getBoundingClientRect=()=>({height:300});
  h.root.fzOneChoice.update();assert.equal(box.style['--one-image-height'],'492px');
  h.context.window.innerHeight=540;h.root.fzOneChoice.update();assert.equal(box.style['--one-image-height'],'372px');h.root.fzOneChoice.destroy();
});

// Rapid currency/shape changes and reset must never leak old digit callbacks.
test('a new final offer cancels the previous landing and retains all decimal places',async()=>{
  const h=harness(),n=new h.Node(),reels=new h.api.PriceReels(n);let old=0,fresh=0;
  reels.spin({currency:'USD'});await h.tick(250);
  reels.land({amount:99999.99,currency:'USD'},()=>old++);await h.tick(120);
  reels.land({amount:0.025,currency:'KWD'},()=>fresh++);await h.tick(1800);
  assert.equal(old,0);assert.equal(fresh,1);
  assert.equal(n.getAttribute('aria-label'),'0.025 KWD');
  assert.deepEqual(n.querySelectorAll('.fz-one-reel').map(c=>c.dataset.digit),['0','0','2','5']);
  reels.clear();assert.equal(h.timers.size,0);
});


test('the counter reads the same log offers before images are ready',async()=>{
  const h=harness();h.state.busy=true;h.setRows([]);
  const offer={...h.row,money:{amount:3,currency:'KWD'}};
  h.root.fzRefineBridge.choiceLogRows=()=>[offer];
  h.context.window.FindziaBillingFetch=()=>{throw Error('No reviewed candidates yet');};
  h.api.mount(h.root);await h.tick(360);
  assert.equal(h.root.querySelector('.fz-one-log-price').textContent,'3.000 KWD');
  assert.equal(h.root.querySelector('.fz-one-price-source').textContent,'Store · 3.000 KWD');
  assert.deepEqual(h.root.querySelectorAll('.fz-one-reel').map(n=>n.dataset.digit),['3','0','0','0']);
  assert.equal(h.root.querySelector('.fz-one-log-line').dataset.active,'true');
  h.root.fzOneChoice.destroy();
});

test('first ready offers start AI selection while retrieval is still busy',async()=>{
  const h=harness();h.state.busy=true;h.state.media_pending=true;let calls=0;
  h.context.window.FindziaBillingFetch=async()=>{calls++;return h.response();};
  h.api.mount(h.root);await h.tick(200);assert.equal(calls,0);
  await h.tick(180);assert.equal(calls,1);
  assert.equal(h.root.querySelector('.fz-one-open').hidden,false);
  assert.equal(h.root.querySelector('.fz-one-open').href,h.row.url);
  assert.equal(h.root.querySelector('.fz-one-badge').textContent,'أفضل المتوفر حاليًا');
  assert.equal(h.state.busy,true);h.root.fzOneChoice.destroy();
});

test('ready selection skips unrelated pending media without the old 4.5 second wait',async()=>{
  const h=harness();h.state.media_pending=true;let calls=0;
  h.context.window.FindziaBillingFetch=async()=>{calls++;return h.response();};
  h.api.mount(h.root);await h.tick(100);assert.equal(calls,1);
  assert.equal(h.root.querySelector('.fz-one-open').hidden,false);h.root.fzOneChoice.destroy();
});

test('later reviewed offers are considered without blanking the early usable result',async()=>{
  const h=harness();h.state.busy=true;let calls=0,finish,usage=0;h.root.addEventListener('fz:usage',()=>usage++);
  h.context.window.FindziaBillingFetch=async()=>{calls++;return h.response();};
  h.api.mount(h.root);await h.tick(800);assert.equal(calls,1);
  const newer={...h.row,url:'https://store.example/better',token:'signed-2',title:'Better camera',money:{amount:9.99,currency:'KWD'}};
  h.setRows([h.row,newer]);h.root.fzOneChoice.update();await h.tick(100);assert.equal(calls,1);
  h.state.busy=false;h.context.window.FindziaBillingFetch=()=>{calls++;return new Promise(r=>finish=r);};
  h.root.fzOneChoice.update();await h.tick(0);assert.equal(calls,2);
  assert.equal(h.root.querySelector('.fz-one-open').href,h.row.url);
  assert.equal(h.root.querySelector('.fz-one-open').hidden,false);
  finish(h.response(newer));await h.tick(600);
  assert.equal(h.root.querySelector('.fz-one-open').href,newer.url);
  assert.equal(h.root.querySelector('.fz-one-price').getAttribute('aria-label'),'9.990 KWD');
  assert.equal(usage,1);
  h.root.fzOneChoice.destroy();
});

test('manual selection remains selected after background search completion',async()=>{
  const h=harness();h.state.busy=true;let calls=0;
  h.context.window.FindziaBillingFetch=async()=>{calls++;return h.response();};
  h.api.mount(h.root);await h.tick(800);
  h.root.querySelectorAll('.fz-one-icon')[1].dispatchEvent(new Event('click'));
  h.root.querySelector('.fz-one-offer-row').dispatchEvent(new Event('click'));
  h.setRows([h.row,{...h.row,url:'https://store.example/other',token:'signed-2'}]);h.state.busy=false;h.root.fzOneChoice.update();await h.tick(600);
  assert.equal(calls,1);assert.equal(h.root.querySelector('.fz-one-badge').textContent,'اختيارك');h.root.fzOneChoice.destroy();
});

test('removed or corrected quotes cannot reappear from the live-price queue',async()=>{
  const h=harness(),n=new h.Node(),seen=[],reels=new h.api.PriceReels(n,row=>{if(row)seen.push(row.money.amount);});
  const a={...h.row,money:{amount:3,currency:'KWD'}},b={...h.row,url:'https://store.example/b',money:{amount:9,currency:'KWD'}};
  reels.spin([a,b]);await h.tick(280);
  const corrected={...b,money:{amount:10,currency:'KWD'}};reels.spin([corrected]);await h.tick(500);
  assert.equal(reels.activeOffer.money.amount,10);assert.ok(!seen.includes(9));
  reels.land({amount:1200,currency:'JPY'});await h.tick(600);
  assert.equal(n.getAttribute('aria-label'),'1,200 JPY');
  assert.equal(n.querySelectorAll('.fz-one-fils').length,0);
  assert.deepEqual(n.querySelectorAll('.fz-one-reel').map(c=>c.dataset.digit),['1','2','0','0']);
  reels.clear();assert.equal(h.timers.size,0);
});


test('an early no-match waits for the full pool instead of flashing a failure',async()=>{
  const h=harness();h.state.busy=true;let calls=0;
  h.context.window.FindziaBillingFetch=async()=>{calls++;return {ok:true,json:async()=>({ok:true,status:'no_match'})};};
  h.api.mount(h.root);await h.tick(500);assert.equal(calls,1);
  assert.equal(h.root.querySelector('.fz-one').dataset.state,'pending');
  h.state.busy=false;h.context.window.FindziaBillingFetch=async()=>{calls++;return h.response();};
  h.root.fzOneChoice.update();await h.tick(500);
  assert.equal(calls,2);assert.equal(h.root.querySelector('.fz-one').dataset.state,'selected');
  h.root.fzOneChoice.destroy();
});
