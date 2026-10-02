/* Deterministic DOM/animation lifecycle tests. No browser or live API traffic. */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const source = readFileSync(require('node:path').join(__dirname, '../source/findzia-motion.js'), 'utf8');

function fixture({reduce = false, text = 'Find your product instantly', reflow = false, api = true} = {}) {
  const observations = [], animations = [], events = {}, frames = [];
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
  class Intersection { constructor(fn) { this.fn = fn; this.targets = new Set(); } observe(el) {this.targets.add(el);} unobserve(el) {this.targets.delete(el);} }
  const context = {document: doc, matchMedia: () => mql, innerWidth: 390, innerHeight: 844, MutationObserver: Observer, IntersectionObserver: Intersection, requestAnimationFrame: fn => (frames.push(fn), frames.length), addEventListener: (key, fn) => {(events[key] ||= []).push(fn);}};
  context.window = context;
  if (!api) Element.prototype.animate = undefined;
  vm.runInNewContext(source, context);
  const flush = () => { for (const f of frames.splice(0)) f(); };
  const notify = (el, records) => { observations.filter(x => x.el === el).forEach(x => x.fn(records)); flush(); };
  const add = (parent, tag, cls, text = '') => { const el = new Element(tag, text); el.className = cls; parent.append(el); return el; };
  return {context, doc, root, title, camera, input, mql, animations, observations, flush, notify, add, api: context.FindziaMotion};
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
