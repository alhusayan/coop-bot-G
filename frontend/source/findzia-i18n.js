/* FINDZIA_LANGUAGE_PAINT_FIX=156.7.89.1 */
/* FINDZIA_I18N_RELEASE=156.7.89 — static UI translations; reconcile dynamic copy before paint. */
(() => {
 'use strict';
 if(window.FindziaI18n?.version==='156.7.89')return;
 const DATA=/* UI_TRANSLATIONS */ null;
 // Build embeds all pretranslated languages; switching never contacts a translator.
 const catalog=Object.fromEntries(DATA.languages.map(lang=>[lang,Object.fromEntries(DATA.keys.map((key,i)=>[key,DATA.values[lang][i]]))]));
 const aliases=DATA.aliases||{}, supported=new Set(DATA.languages), version=DATA.version;
 const reverse=new Map(), originals=new WeakMap(), attributes=new WeakMap(), mounted=new WeakSet();
 const templates=[];
 let scheduled=false;
 const normalize=lang=>{const code=String(lang||'en').toLowerCase().split(/[-_]/)[0];return supported.has(code)?code:'en';};
 const main=()=>document.querySelector('.fz-home');
 const locale=root=>normalize(root?.dataset?.lang||main()?.dataset?.lang||document.documentElement.lang);
 const direction=lang=>['ar','ur'].includes(normalize(lang))?'rtl':'ltr';
 function index(){
  reverse.clear();
  templates.length=0;
  for(const [lang,values]of Object.entries(catalog))for(const [source,value]of Object.entries(values)){
   if(lang==='en'||!reverse.has(value))reverse.set(value,source);
   if(/\{\w+\}/.test(source)){
    const names=[],escape=s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');let at=0,pattern='^';
    for(const match of value.matchAll(/\{(\w+)\}/g)){pattern+=escape(value.slice(at,match.index))+'(.+?)';names.push(match[1]);at=match.index+match[0].length;}
    pattern+=escape(value.slice(at))+'$';if(names.length)templates.push({source,names,re:new RegExp(pattern)});
   }
  }
 }
 // Never import old machine translations from localStorage. Shipped copy is authoritative.
 index();
 function sourceOf(value){
  if(Object.hasOwn(aliases,value))return aliases[value];
  if(Object.hasOwn(catalog.en,value))return value;
  return reverse.get(value)||null;
 }
 function t(source,arabic,root){
  const lang=locale(root),key=sourceOf(String(source))||String(source);
  const value=catalog[lang]?.[key];
  if(value)return value;
  return lang==='ar'&&arabic?arabic:source;
 }
 function translateValue(value,lang){
  const direct=sourceOf(value);
  if(direct){return catalog[lang]?.[direct]||catalog.en[direct];}
  const text=value.trim(),source=sourceOf(text);
  if(source){const translated=catalog[lang]?.[source]||catalog.en[source];return value.replace(text,translated);}
  for(const template of templates){const match=value.match(template.re);if(!match)continue;
   const args=Object.fromEntries(template.names.map((name,i)=>[name,match[i+1]]));
   return (catalog[lang]?.[template.source]||template.source).replace(/\{(\w+)\}/g,(all,key)=>args[key]??all);
  }
  // Counts keep their exact value. Only a shipped UI phrase is translated.
  const count=value.match(/^(\s*[\d.,]+\s+)(.+?)(\s*)$/);
  if(count){const label=sourceOf(count[2]);if(label){return count[1]+(catalog[lang]?.[label]||label)+count[3];}}
  return value;
 }
 function ignored(el){return !el||el.closest('script,style,textarea,input,code,pre,.fz-brand,.fz-motion-word,[contenteditable="true"],[translate="no"],[data-no-i18n],[data-query-preview]');}
 function scan(scope,root){
  const lang=locale(root);
  if(scope.tagName==='DIALOG'){
   if(scope.lang!==lang)scope.lang=lang;
   if(scope.dir!==direction(lang))scope.dir=direction(lang);
  }
  const walker=document.createTreeWalker(scope,NodeFilter.SHOW_TEXT);
  for(let node=walker.nextNode();node;node=walker.nextNode()){
   if(ignored(node.parentElement)||!node.data.trim())continue;
   const old=originals.get(node),value=node.data;
   if(old?.lang===lang&&value===old.last)continue;
   const source=old&&value===old.last?old.source:value;
   const translated=translateValue(source,lang);
   originals.set(node,{source,last:translated,lang});
   if(value!==translated)node.data=translated;
  }
  for(const el of [scope,...scope.querySelectorAll('[aria-label],[placeholder],[title]')]){
   if(el.closest?.('iframe,script,style,.fz-brand,.fz-motion-word,[contenteditable="true"],[translate="no"],[data-no-i18n],[data-query-preview]'))continue;
   for(const name of ['aria-label','placeholder','title']){
    if(!el.hasAttribute(name))continue;
    let record=attributes.get(el);if(!record){record={};attributes.set(el,record);}
    const value=el.getAttribute(name),old=record[name];
    if(old?.lang===lang&&value===old.last)continue;
    const source=old&&value===old.last?old.source:value;
    const translated=translateValue(source,lang);record[name]={source,last:translated,lang};
    if(value!==translated)el.setAttribute(name,translated);
   }
  }
 }
 function refresh(){
  scheduled=false;
  const root=main();if(!root)return;
  const lang=locale(root),dir=direction(lang);
  // Keep the host Shopify document direction stable. Flipping it also moves
  // off-screen theme drawers and can inflate Safari's RTL layout viewport.
  // Findzia and its top-layer dialogs own their direction independently.
  document.documentElement.lang=lang;
  if(root.dir!==dir)root.dir=dir;
  for(const scope of document.querySelectorAll('.fz-home,dialog[class*="fz"],dialog[id^="findzia-"],.fza-toast'))scan(scope,scope.closest('.fz-home')||root);
  const trigger=root.querySelector('[data-market-open]');
  if(trigger){
   const cc=root.querySelector('[data-market-country]')?.textContent?.trim();
   let country=cc||'';try{country=new Intl.DisplayNames([lang],{type:'region'}).of(cc);}catch(_){}
   const label=t('Market, language and currency',null,root)+(country?' · '+country:'');
   if(trigger.getAttribute('aria-label')!==label)trigger.setAttribute('aria-label',label);
   if(trigger.title!==label)trigger.title=label;
  }
 }
 // Run after a DOM update in the same turn, before any animation frame is painted.
 function schedule(){if(!scheduled){scheduled=true;queueMicrotask(refresh);}}
 function set(root,lang){
  lang=normalize(lang);
  if(root?.dataset.lang!==lang)root.dataset.lang=lang;
  document.documentElement.lang=lang;
  if(root)root.dir=direction(lang);
  refresh();
 }
 function mount(root){if(!root||mounted.has(root))return;mounted.add(root);set(root,locale(root));
  const preferences=root.querySelector('[data-preferences]');
  if(preferences){
   const sync=()=>{preferences.dir=direction(locale(root));
    if(preferences.open)window.FindziaModalScroll?.lock(preferences);
    else window.FindziaModalScroll?.unlock(preferences);
   };
   const watch=new MutationObserver(sync);watch.observe(preferences,{attributes:true,attributeFilter:['open']});
   preferences.addEventListener('close',sync);sync();
   document.addEventListener('shopify:section:unload',function cleanup(event){
    if(!event.target?.contains(root))return;watch.disconnect();preferences.removeEventListener('close',sync);
    window.FindziaModalScroll?.unlock(preferences);document.removeEventListener('shopify:section:unload',cleanup);
   });
  }
 }
 window.FindziaI18n={version,languages:[...supported],t,set,mount,locale,direction,refresh:schedule,
  format:(source,values,root,arabic)=>t(source,arabic,root).replace(/\{(\w+)\}/g,(all,key)=>String(values[key]??all)),
  // Tests and support may inspect keys; no account/customer data is retained.
  known:source=>!!sourceOf(String(source))};
 const observer=new MutationObserver(changes=>{
  if(changes.some(c=>c.type==='childList'||c.type==='characterData'||c.attributeName==='data-lang'||
     ['aria-label','placeholder','title'].includes(c.attributeName)))schedule();
 });
 function start(){document.querySelectorAll('.fz-home').forEach(mount);observer.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['data-lang','aria-label','placeholder','title']});}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
 document.addEventListener('shopify:section:load',event=>{event.target.querySelectorAll('.fz-home').forEach(mount);schedule();});
})();
