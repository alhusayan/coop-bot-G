/* Deterministic DOM/animation lifecycle tests. No browser or live API traffic. */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const source = readFileSync(require('node:path').join(__dirname, '../source/findzia-motion.js'), 'utf8');

function fixture({reduce = false, text = 'Find your product instantly', reflow = false, api = true} = {}) {
  const observations = [], animations = [], events = {}, frames = [], intersections = [];
  let doc;
  class Element {
    constructor(tag, value = '') { this.tagName = tag; this.nodeType = tag === '#text' ? 3 : tag === '#fragment' ? 11 : 1; this.childNodes = []; this.parentNode = null; this.dataset = {}; this.attrs = {}; this.value = value; this.className = ''; this.listeners = {}; this.open = false; this.hidden = false; this.top = 20; this.style = {setProperty() {}}; }
    get children() { return this.childNodes.filter(x => x.nodeType === 1); }
    get textContent() { return this.value + this.childNodes.map(x => x.textContent).join(''); }
    set textContent(v) { this.childNodes.forEach(x => x.parentNode = null); this.childNodes = []; this.value = v; }
    get isConnected() { return this === doc || !!this.parentNode?.isConnected; }
    append(...nodes) { for (const n of nodes) { if (n.nodeType === 11) { this.append(...n.childNodes); continue; } if (n.parentNode) n.parentNode.childNodes = n.parentNode.childNodes.filter(x => x !== n); this.childNodes.push(n); n.parentNode = this; } }
    replaceChildren(...nodes) { this.textContent = ''; this.append(...nodes); }
    matches(selectors) {
      return selectors.split(',').some(selector => {
        let s = selector.trim();
        if (s.includes(':not([hidden])')) { if (this.hidden) return false; s = s.replace(':not([hidden])', ''); }
        const parts = s.split(/\s+/); if (parts.length > 1) return this.matches(parts.at(-1)) && !!this.parentNode?.closest(parts.slice(0,-1).join(' '));
        const tag = s.match(/^[\w-]+/)?.[0]; if (tag && tag !== this.tagName) return false;
        if ([...s.matchAll(/\.([\w-]+)/g)].some(m => !this.className.split(' ').includes(m[1]))) return false;
        return [...s.matchAll(/\[([\w-]+)\]/g)].every(m => this.getAttribute(m[1]) !== null);
      });
    }
    closest(s) { return this.matches(s) ? this : this.parentNode?.closest(s) || null; }
    contains(el) { return this === el || this.childNodes.some(x => x.contains(el)); }
    querySelectorAll(s) { return this.children.flatMap(el => [...(el.matches(s) ? [el] : []), ...el.querySelectorAll(s)]); }
    querySelector(s) { return this.querySelectorAll(s)[0] || null; }
    getAttribute(key) { if (key === 'hidden') return this.hidden ? '' : null; if (key === 'open') return this.open ? '' : null; if (key.startsWith('data-')) return this.dataset[key.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] ?? null; return this.attrs[key] ?? null; }
    getClientRects() { return this.isConnected && !this.closest('[hidden]') ? [this.getBoundingClientRect()] : []; }
    getBoundingClientRect() {
      const i = this.parentNode?.children.indexOf(this) || 0;
      const top = this.className === 'fz-motion-word' ? 20 + Math.floor(i / 2) * 40 : this.top;
      const height = 80 + (reflow && this.children.some(x => x.className === 'fz-motion-word') ? 40 : 0);
      return {top, left: 16, right: 366, bottom: top + height, width: 350, height};
    }
    addEventListener(key, fn) { (this.listeners[key] ||= []).push(fn); }
    removeEventListener() {}
    emit(key, data = {}) { (this.listeners[key] || []).forEach(fn => fn({target: this, type: key, ...data})); }
    animate(keyframes, options) {
      let resolve, reject;
      const a = {target: this, keyframes, options, canceled: false, finished: new Promise((a,b) => {resolve = a; reject = b;}), finish() {resolve();}, cancel() {this.canceled = true; reject(Error('canceled'));}};
      animations.push(a); return a;
    }
  }
  doc = new Element('document'); doc.readyState = 'complete';
  doc.createElement = tag => new Element(tag); doc.createTextNode = text => new Element('#text', text); doc.createDocumentFragment = () => new Element('#fragment');
  const root = new Element('section'); root.className = 'fz-home'; root.dataset.homeState = 'empty'; doc.append(root);
  const home = new Element('div'); home.dataset.darkHome = ''; root.append(home);
  const title = new Element('h1', text); title.className = 'fz-dark-title'; home.append(title);
  const camera = new Element('button'); camera.dataset.darkPhoto = ''; home.append(camera);
  const input = new Element('textarea'); input.dataset.darkInput = ''; home.append(input);
  const mql = {matches: reduce, addEventListener(key, fn) { this.changed = fn; }};
  class Observer { constructor(fn) { this.fn = fn; observations.push(this); } observe(el, options) { this.el = el; this.options = options; } disconnect() {} }
  class Intersection { constructor(fn) { this.fn = fn; this.targets = new Set(); intersections.push(this); } observe(el) {this.targets.add(el);} unobserve(el) {this.targets.delete(el);} }
  const context = {document: doc, matchMedia: () => mql, innerWidth: 390, innerHeight: 844, MutationObserver: Observer, IntersectionObserver: Intersection, requestAnimationFrame: fn => (frames.push(fn), frames.length), addEventListener: (key, fn) => {(events[key] ||= []).push(fn);}};
  context.window = context;
  if (!api) Element.prototype.animate = undefined;
  vm.runInNewContext(source, context);
  const flush = () => { for (const f of frames.splice(0)) f(); };
  const notify = (el, records) => { observations.filter(x => x.el === el).forEach(x => x.fn(records)); flush(); };
  const add = (parent, tag, cls, text = '') => { const el = new Element(tag, text); el.className = cls; parent.append(el); return el; };
  return {context, doc, root, title, camera, input, mql, animations, observations, intersections, flush, notify, add, api: context.FindziaMotion};
}

test('line reveal preserves English/Arabic words and restores text after completion', async () => {
  for (const text of ['Find your product instantly', 'اعثر على منتجك فورًا']) {
    const f = fixture({text}); assert.equal(f.title.textContent, text);
    const words = f.title.children; assert.ok(words.length >= 3);
    assert.deepEqual(words.map(x => x.textContent), text.split(' '));
    const motion = f.animations.filter(x => words.includes(x.target));
    assert.equal(motion[0].options.delay, motion[1].options.delay);
    assert.equal(motion[2].options.delay, 85);
    assert.ok(!f.animations.some(x => x.target === f.input), 'composer is never faded');
    f.animations.forEach(x => x.finish()); await Promise.resolve();
    assert.equal(f.title.textContent, text); assert.equal(f.title.children.length, 0);
    assert.ok(f.animations.every(x => x.canceled), 'finished effects release transforms and filters');
  }
});
test('layout-changing word wrapping falls back to an unsplit heading', () => {
  const f = fixture({reflow: true}); assert.equal(f.title.children.length, 0);
  assert.ok(f.animations.some(x => x.target === f.title));
});
test('reduced motion is immediate and changing the preference cleans up active effects', async () => {
  const off = fixture({reduce: true}); assert.equal(off.animations.length, 0); assert.equal(off.title.children.length, 0);
  const f = fixture(); f.mql.matches = true; f.mql.changed(); await Promise.resolve();
  assert.ok(f.animations.every(x => x.canceled)); assert.equal(f.title.textContent, 'Find your product instantly'); assert.equal(f.title.children.length, 0);
});
test('missing animation support leaves the complete text and all controls visible', () => {
  const f = fixture({api: false}); assert.equal(f.title.children.length, 0); assert.equal(f.title.textContent, 'Find your product instantly'); assert.equal(f.input.hidden, false);
});
test('stream updates and sorting do not replay existing cards', () => {
  const f = fixture(), container = f.add(f.root,'div','results');
  const card = (id) => { const el=f.add(container,'div','fz-card-shell'); const img=f.add(el,'img','');img.dataset.imageKey=id; return el; };
  const a=card('a'); f.api.results(container); const count=f.animations.length;
  f.api.results(container); assert.equal(f.animations.length,count);
  a.parentNode=null; container.childNodes=[]; card('a'); f.api.results(container,new Map([['a',{}]])); assert.equal(f.animations.length,count);
  card('b'); f.api.results(container,new Map([['a',{}]])); assert.equal(f.animations.length,count+1);
  assert.equal(container.children.length,2,'motion never removes or defers results');
});
test('dialog close remains synchronous and payment body is never animated', () => {
  const f=fixture(), dialog=f.add(f.root,'dialog','fz-account');
  const header=f.add(dialog,'header','fza-header'); f.add(header,'h2','','Payment');
  const payment=f.add(dialog,'div','fza-body'), iframe=f.add(payment,'iframe','');
  f.notify(f.root,[{type:'childList',addedNodes:[dialog]}]);
  dialog.open=true; f.notify(dialog,[{type:'attributes',target:dialog,attributeName:'open',addedNodes:[]}]);
  assert.ok(f.animations.some(x=>x.target===dialog)); assert.ok(!f.animations.some(x=>x.target===payment||x.target===iframe));
  dialog.open=false; dialog.emit('close'); assert.equal(dialog.open,false);
  assert.ok(f.animations.filter(x=>x.target===dialog).every(x=>x.canceled));
});
test('assistant questions reveal once while the draft and its search control remain untouched', () => {
  const f=fixture(), dialog=f.add(f.root,'dialog','fz-guide');
  const body=f.add(dialog,'div','fz-guide-body');f.add(body,'h3','fz-guide-question','Colour?');f.add(body,'button','fz-guide-choice','Black');
  const footer=f.add(dialog,'footer','fz-guide-footer');const draft=f.add(footer,'textarea','fz-guide-proposed','Black');const search=f.add(footer,'button','fz-guide-primary','Search');
  f.notify(f.root,[{type:'childList',addedNodes:[dialog]}]);dialog.open=true;
  f.notify(dialog,[{type:'attributes',target:dialog,attributeName:'open',addedNodes:[]}]);const count=f.animations.length;
  f.notify(dialog,[{type:'childList',addedNodes:[]}]);assert.equal(f.animations.length,count);
  assert.equal(draft.textContent,'Black');assert.ok(!f.animations.some(x=>x.target===draft||x.target===search||x.target===footer));
});

test('a hidden first paint does not consume the card entrance', () => {
  const f=fixture(), container=f.add(f.root,'div','results');container.hidden=true;
  const card=f.add(container,'article','fz-card-shell'),stage=f.add(card,'div','fz-media-stage');stage.dataset.imageKey='speaker';
  f.api.results(container);assert.ok(!f.animations.some(a=>a.target===card));
  container.hidden=false;f.api.results(container,new Map([['speaker',{}]]));
  assert.equal(f.animations.filter(a=>a.target===card).length,1);
  f.api.results(container);assert.equal(f.animations.filter(a=>a.target===card).length,1);
});

test('late, cached and replacement images reveal their wrapper independently of card admission', () => {
  const f=fixture(), container=f.add(f.root,'div','results'),card=f.add(container,'article','fz-card-shell');
  const stage=f.add(card,'div','fz-media-stage');stage.dataset.imageKey='speaker';
  const photo=f.add(stage,'img','is-loaded');photo.attrs.src='https://store.example/a.jpg';photo.complete=false;photo.naturalWidth=0;
  f.api.results(container);
  assert.equal(f.animations.filter(a=>a.target===stage).length,0);
  photo.complete=true;photo.naturalWidth=800;
  f.root.emit('load',{target:photo});
  f.api.results(container);f.root.emit('load',{target:photo});
  assert.equal(f.animations.filter(a=>a.target===stage).length,1,'load and paint must not double-play');
  assert.ok(!f.animations.some(a=>a.target===photo),'legacy important image rules cannot override a wrapper effect');
  photo.attrs.src='https://store.example/b.jpg';f.root.emit('load',{target:photo});
  assert.equal(f.animations.filter(a=>a.target===stage).length,2,'a replacement source gets its own reveal');
  const stage2=f.add(container,'div','fz-media-stage'),cached=f.add(stage2,'img','');
  cached.complete=true;cached.naturalWidth=600;cached.attrs.src='https://store.example/c.jpg';
  f.notify(f.root,[{type:'childList',addedNodes:[stage2]}]);
  assert.equal(f.animations.filter(a=>a.target===stage2).length,1,'a cached image needs no second load event');
});

test('incremental cards are discovered without a render hook and reveal only when scrolled into view', () => {
  const f=fixture(), card=f.add(f.root,'article','fz-card-shell');card.top=1200;
  const heading=f.add(f.root,'h2','fz-market-head','Local market');
  f.notify(f.root,[{type:'childList',addedNodes:[heading,card]}]);
  assert.ok(f.animations.some(a=>a.target===heading));assert.ok(!f.animations.some(a=>a.target===card));
  const observer=f.intersections[0];assert.ok(observer.targets.has(card));
  card.top=500;observer.fn([{target:card,isIntersecting:true}]);
  assert.equal(f.animations.filter(a=>a.target===card).length,1);assert.ok(!observer.targets.has(card));
  f.api.results(f.root);assert.equal(f.animations.filter(a=>a.target===card).length,1);
});

test('account navigation reveals actual sections and plans, including later body replacement', () => {
  const f=fixture(),dialog=f.add(f.root,'dialog','fz-account'),header=f.add(dialog,'header','fza-header');
  f.add(header,'h2','','Settings');const body=f.add(dialog,'div','fza-body');
  const intro=f.add(body,'div','fza-page-intro','Your account');
  const group=f.add(body,'section','fza-group'),field=f.add(group,'label','fza-field','Market');
  const list=f.add(body,'div','fza-product-list'),product=f.add(list,'article','fza-product');
  const plans=f.add(body,'div','fzb-plans'),plan=f.add(plans,'article','fzb-plan','40 searches');
  f.notify(f.root,[{type:'childList',addedNodes:[dialog]}]);dialog.open=true;
  f.notify(dialog,[{type:'attributes',target:dialog,attributeName:'open',addedNodes:[]}]);
  for(const el of [intro,group,product,plan])assert.ok(f.animations.some(a=>a.target===el));
  assert.ok(!f.animations.some(a=>a.target===field),'do not stack nested section reveals');
  const count=f.animations.length;f.notify(dialog,[{type:'childList',addedNodes:[]}]);assert.equal(f.animations.length,count);
  body.replaceChildren();const next=f.add(body,'section','fza-group');
  f.notify(dialog,[{type:'childList',addedNodes:[next]}]);assert.ok(!f.animations.some(a=>a.target===next),'same view refresh must remain visible');
  dialog.dataset.view='plans';f.notify(dialog,[{type:'attributes',target:dialog,attributeName:'data-view'}]);
  assert.ok(f.animations.some(a=>a.target===next),'real navigation still reveals sections');
});

test('menu, preferences, product details, disclosure content and popovers have entry motion', () => {
  const f=fixture(),menu=f.add(f.root,'dialog','fz-dark-menu');menu.dataset.darkMenu='';
  const label=f.add(menu,'h3','fza-nav-label','My account'),item=f.add(menu,'button','fza-nav-link','Saved products');
  const preferences=f.add(f.root,'dialog','fz-settings-dialog');preferences.dataset.preferences='';
  const field=f.add(preferences,'label','fz-preferences-field','Market');
  const disclosure=f.add(preferences,'details','fz-setting-row');f.add(disclosure,'summary','','Privacy');const answer=f.add(disclosure,'p','','Your preferences');
  const insights=f.add(f.root,'dialog','fz-insights'),hero=f.add(insights,'div','fz-insights-hero'),specs=f.add(insights,'dl','fz-insights-specs');
  f.notify(f.root,[{type:'childList',addedNodes:[menu,preferences,insights]}]);
  for(const dialog of [menu,preferences,insights]){dialog.open=true;f.notify(dialog,[{type:'attributes',target:dialog,attributeName:'open',addedNodes:[]}]);}
  for(const el of [menu,label,item,field,hero,specs])assert.ok(f.animations.some(a=>a.target===el));
  const expansion=f.animations.find(a=>a.target===menu);assert.ok(expansion.keyframes[0].clipPath);assert.equal(expansion.options.duration,440);
  disclosure.open=true;disclosure.emit('toggle');assert.ok(f.animations.some(a=>a.target===answer));
  const popover=f.add(f.root,'div','fz-sort-menu');popover.dataset.sortMenu='';popover.hidden=true;
  f.notify(f.root,[{type:'childList',addedNodes:[popover]}]);assert.ok(!f.animations.some(a=>a.target===popover));
  popover.hidden=false;f.notify(popover,[{type:'attributes',target:popover,attributeName:'hidden',addedNodes:[]}]);popover.emit('toggle');
  assert.equal(f.animations.filter(a=>a.target===popover).length,1);
  popover.hidden=true;popover.emit('toggle');popover.hidden=false;popover.emit('toggle');
  assert.equal(f.animations.filter(a=>a.target===popover).length,2);
});

test('assistant recommendation modes animate even without a question or choices', () => {
  const f=fixture(),dialog=f.add(f.root,'dialog','fz-guide'),mode=f.add(dialog,'button','fz-guide-mode','Best quality');
  f.notify(f.root,[{type:'childList',addedNodes:[dialog]}]);dialog.open=true;
  f.notify(dialog,[{type:'attributes',target:dialog,attributeName:'open',addedNodes:[]}]);
  assert.ok(f.animations.some(a=>a.target===mode));
});

test('menu entry is not overridden by a short open-state CSS transition', () => {
  const css=readFileSync(require('node:path').join(__dirname,'../source/findzia-motion.css'),'utf8');
  assert.match(css,/dialog\[data-dark-menu\]\[data-fz-motion-dialog\]\[open\]\{[^}]*transition:none/);
  assert.match(css,/display 160ms allow-discrete/,'native close stays synchronous with an optional visual exit');
});

test('login busy and balance updates do not replay equivalent sections', () => {
 const f=fixture(),dialog=f.add(f.root,'dialog','fz-account'),header=f.add(dialog,'header','fza-header');
 f.add(header,'h2','','My account');dialog.dataset.view='home';const body=f.add(dialog,'div','fza-body');
 const paint=balance=>{body.replaceChildren();return [f.add(body,'section','fza-providers','Sign in'),f.add(body,'section','fzb-credit-card',balance),f.add(body,'section','fza-group','Details')];};
 paint('—');f.notify(f.root,[{type:'childList',addedNodes:[dialog]}]);dialog.open=true;
 f.notify(dialog,[{type:'attributes',target:dialog,attributeName:'open'}]);
 for(const balance of ['—','28','28']){
  const nodes=paint(balance);f.notify(dialog,[{type:'childList',addedNodes:nodes}]);
  assert.ok(!f.animations.some(a=>nodes.includes(a.target)),'replacement DOM must stay visible');
 }
 assert.ok(f.animations.filter(a=>!a.target.isConnected).every(a=>a.canceled));
});

test('assistant rerenders preserve question and photo visibility', () => {
 const f=fixture(),dialog=f.add(f.root,'dialog','fz-guide');
 const paint=()=>{
  dialog.replaceChildren();const q=f.add(dialog,'h2','fz-guide-question','Which colour?');
  const choice=f.add(dialog,'button','fz-guide-choice','Black'),intro=f.add(dialog,'p','fz-guide-intro','Choose what matters');
  const context=f.add(dialog,'div','fz-guide-context'),img=f.add(context,'img','');
  img.complete=true;img.naturalWidth=100;img.attrs.src='speaker.jpg';return [q,choice,intro,img];
 };
 paint();f.notify(f.root,[{type:'childList',addedNodes:[dialog]}]);dialog.open=true;
 f.notify(dialog,[{type:'attributes',target:dialog,attributeName:'open'}]);
 const nodes=paint();f.notify(dialog,[{type:'childList',addedNodes:nodes}]);
 f.notify(f.root,[{type:'childList',addedNodes:nodes}]);
 assert.ok(!f.animations.some(a=>nodes.includes(a.target)));
 nodes[0].textContent='Where will you use it?';f.notify(dialog,[{type:'childList',addedNodes:[]}]);
 assert.ok(f.animations.some(a=>a.target===nodes[0]));assert.equal(nodes[0].children.length,0);
});

test('secure-login background transition cancels active effects', () => {
 const f=fixture();f.doc.hidden=true;f.doc.emit('visibilitychange');assert.ok(f.animations.every(a=>a.canceled));
});
