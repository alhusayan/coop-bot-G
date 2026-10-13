import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {parseHTML} from 'linkedom';
import {frameDocument} from '../original-page.mjs';
import {syncLanguageControls} from '../public/findzia-shell.js';

const code=readFileSync(new URL('../public/findzia/i18n.js',import.meta.url),'utf8');
const catalog=JSON.parse(code.match(/ const DATA=(.+);\n \/\/ Build embeds/)[1]);
const value=(language,key)=>catalog.values[language][catalog.keys.indexOf(key)];

test('every supported language covers the complete Spaces flow and retains interpolation fields',()=>{
 assert.equal(catalog.languages.length,17);
 for(const language of catalog.languages){
  const values=catalog.values[language];
  assert.equal(values.length,catalog.keys.length,language);
  values.forEach((text,index)=>{
   assert.ok(text.trim(),language+': '+catalog.keys[index]);
   assert.deepEqual([...text.matchAll(/\{\w+\}/g)].map(x=>x[0]).sort(),[...catalog.keys[index].matchAll(/\{\w+\}/g)].map(x=>x[0]).sort(),language+': '+catalog.keys[index]);
   // These two words are also the correct German/Italian terms.
   if(language!=='en'&&index>=794&&!['de:Optional','it:Password'].includes(language+':'+catalog.keys[index]))assert.notEqual(text,catalog.values.en[index],language+': '+catalog.keys[index]);
  });
 }
 const arabic=catalog.values.ar.join('\n');
 assert.doesNotMatch(arabic,/(?:شلون|شكثر|باچر|الحين|هالتصميم|هالغرفة|عشان|تقدر|كردت|شسوي|لقّ القطع)/);
 assert.equal(value('ar','Details'),'التفاصيل');
 assert.equal(value('ar','Your room, reimagined.'),'غرفتك، بتصميم جديد.');
});

test('changing locale repeatedly updates full sentences, saved states, input hints and counts',()=>{
 const {document,window}=parseHTML('<html lang="en"><body><section class="fz-home" data-lang="en"></section><main data-spaces-content><h1>Your room, reimagined.</h1><p id="count">2 of 3 ready. You can start exploring.</p><button id="save" aria-label="Save to this design">Save to this design</button><input placeholder="e.g. Keep my sofa"><img alt="Your original room"></main><footer>Made for your space.</footer></body></html>');
 window.location={pathname:'/',search:''};
 const context=vm.createContext({window,document,NodeFilter:{SHOW_TEXT:4},URLSearchParams,localStorage:{getItem:()=>null},MutationObserver:class{observe(){} disconnect(){}},queueMicrotask:()=>{}});
 vm.runInContext(code,context);
 const root=document.querySelector('.fz-home'),i18n=window.FindziaI18n;
 for(const language of [...catalog.languages,'ar','fr','en','ar']){
  i18n.set(root,language);
  assert.equal(document.querySelector('h1').textContent,value(language,'Your room, reimagined.'));
  assert.equal(document.querySelector('input').placeholder,value(language,'e.g. Keep my sofa'));
  assert.equal(document.querySelector('#save').getAttribute('aria-label'),value(language,'Save to this design'));
  assert.equal(document.querySelector('img').getAttribute('alt'),value(language,'Your original room'));
  assert.equal(document.querySelector('#count').textContent,value(language,'{count} of 3 ready. You can start exploring.').replace('{count}','2'));
  assert.equal(root.dir,['ar','ur'].includes(language)?'rtl':'ltr');
  assert.equal(document.querySelector('footer').textContent,value(language,'Made for your space.'));
 }
 // New messages arriving after a locale switch must translate too.
 document.querySelector('#save').textContent='Removed from this design';
 i18n.set(root,'ar');
 assert.equal(document.querySelector('#save').textContent,'تمت الإزالة من هذا التصميم');
});

test('the results frame loads reviewed copy and Cairo while retaining the original engine',()=>{
 const original='<html><head><script src="/assets/findzia-i18n.abc123.js" defer></script><script src="/assets/findzia-account.abc123.js" defer></script></head><body><script>root.fzRefineBridge.searchPhoto=search;root.fzRefineBridge.render=render;</script></body></html>';
 const framed=frameDocument(original);
 assert.match(framed,/src="\/findzia\/i18n.js" defer/);
 assert.match(framed,/href="\/spaces-typography.css"/);
 assert.match(framed,/src="https:\/\/findzia.com\/assets\/findzia-account.abc123.js" defer/);
 assert.equal(framed.match(/<script>(.*?)<\/script>/)[1],original.match(/<script>(.*?)<\/script>/)[1]);
});

test('a language change survives a translated market-sheet repaint',()=>{
 const {document}=parseHTML('<html><body><section id="root"><select data-profile-language-select><option value="ar" selected>العربية</option><option value="de">Deutsch</option></select></section><div id="sheet"><select id="spaces-language"><option value="ar" selected>العربية</option><option value="de">Deutsch</option></select></div></body></html>');
 const root=document.querySelector('#root');
 for(const code of ['de','ar','de']){
  syncLanguageControls(root,code);
  const sheet=document.querySelector('#sheet');sheet.innerHTML=sheet.innerHTML;
  assert.equal(document.querySelector('#spaces-language').value,code);
  assert.equal(root.querySelector('select').value,code);
 }
});
