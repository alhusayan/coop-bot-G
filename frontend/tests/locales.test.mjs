import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,readdirSync} from 'node:fs';
import vm from 'node:vm';
import {packLocales,LANGUAGES} from '../scripts/locales.mjs';
const sourceDir=new URL('../source/',import.meta.url);
const data=JSON.parse(readFileSync(new URL('findzia-locales.json',sourceDir),'utf8'));
const runtime=readFileSync(new URL('findzia-i18n.js',sourceDir),'utf8');
function fixture(){
  const root={dataset:{lang:'en'}};
  const context={window:{},document:{querySelector:()=>null,readyState:'loading',addEventListener:()=>{},documentElement:{}},
    MutationObserver:class {},requestAnimationFrame:()=>{},
    fetch:()=>{throw Error('UI translation must not use the network');},
    localStorage:{getItem:()=>{throw Error('Stale machine translations must not override shipped copy');}}};
  vm.runInNewContext(runtime.replace('/* UI_TRANSLATIONS */ null',()=>JSON.stringify(packLocales(data))),context);
  return {root,i18n:context.window.FindziaI18n};
}
test('every shipped phrase is available synchronously in all 16 languages',()=>{
  const {root,i18n}=fixture();
  for(const lang of LANGUAGES){
    root.dataset.lang=lang;
    for(const key of Object.keys(data.catalog.en))assert.equal(i18n.t(key,null,root),data.catalog[lang][key],lang+' / '+key);
  }
});
test('language switching preserves interpolation and RTL without a translation service',()=>{
  const {root,i18n}=fixture();
  for(const lang of ['fr','ur','en','ar','ja','de']){
    i18n.set(root,lang);
    assert.equal(root.dir,['ar','ur'].includes(lang)?'rtl':'ltr');
    assert.equal(i18n.format('Get {count} searches',{count:25},root),data.catalog[lang]['Get {count} searches'].replace('{count}','25'));
    assert.equal(i18n.format('Invoice updated {date}',{date:'2026-10-07'},root),data.catalog[lang]['Invoice updated {date}'].replace('{date}','2026-10-07'));
  }
  assert.equal(i18n.direction('ur-PK'),'rtl');
});
test('legacy display variants resolve to the same static phrase',()=>{
  const {root,i18n}=fixture();root.dataset.lang='ar';
  for(const [alias,key] of Object.entries(data.aliases))assert.equal(i18n.t(alias,null,root),data.catalog.ar[key]);
  assert.equal(i18n.t('A new unrecognized message',null,root),'A new unrecognized message');
});
test('build rejects missing phrases and broken placeholders',()=>{
  const incomplete=structuredClone(data);delete incomplete.catalog.ja['My account'];
  assert.throws(()=>packLocales(incomplete),/Incomplete UI catalog/);
  const broken=structuredClone(data);broken.catalog.fr['Pay {price}']='Payer';
  assert.throws(()=>packLocales(broken),/placeholders differ/);
});
test('account navigation and sign-in states have pretranslated copy',()=>{
  const source=readFileSync(new URL('findzia-account.js',sourceDir),'utf8');
  const copy=vm.runInNewContext(source.slice(source.indexOf('const COPY='),source.indexOf('const PATHS='))+';COPY');
  for(const [key,en] of Object.entries(copy.en)){
    if(!en||en===copy.ar[key])continue;
    assert.ok(Object.hasOwn(data.catalog.en,en),key+' / '+en);
  }
});
test('current English/Arabic UI pairs are covered by the static catalog',()=>{
  const untranslated=[];
  const neutral=new Set(['KWD','SAR','AED','OMR','BHD','QAR','Google','Apple','Findzia']);
  const literal=String.raw`(?:'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")`;
  const pairs=new RegExp(String.raw`(${literal})\s*([,:])\s*(${literal})`,'g');
  for(const file of readdirSync(sourceDir).filter(f=>/\.(js|liquid)$/.test(f)&&!f.includes('i18n'))){
    const source=readFileSync(new URL(file,sourceDir),'utf8');
    for(const match of source.matchAll(pairs)){
      let a,b;
      // Regexes and HTML can resemble string pairs; only inspect valid literals.
      try{a=vm.runInNewContext(match[1]);b=vm.runInNewContext(match[3]);}catch{continue;}
      const [en,ar]=match[2]===','?[a,b]:[b,a];
      if(!/[A-Za-z]/.test(en)||/[\u0600-\u06ff<>]/.test(en)||!/[\u0600-\u06ff]/.test(ar))continue;
      if(!neutral.has(en)&&!Object.hasOwn(data.catalog.en,en)&&!Object.hasOwn(data.aliases,en))untranslated.push(file+': '+en);
    }
  }
  assert.deepEqual(untranslated,[]);
});
