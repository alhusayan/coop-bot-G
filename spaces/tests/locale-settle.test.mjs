import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {parseHTML} from 'linkedom';

test('CTA translation settles when the page translator reapplies the same locale',async()=>{
 const {document,window}=parseHTML('<html lang="en"><body><span id="discover-label">Discover designs</span></body></html>');
 let translations=0,loopDetected=false;
 // The page translator observes text changes and reapplies html.lang.
 // Bound the fixture so a regression fails instead of freezing the test runner.
 const translator=new window.MutationObserver(()=>{
  if(++translations>10){loopDetected=true;translator.disconnect();return;}
  document.documentElement.lang=document.documentElement.lang;
 });
 translator.observe(document.body,{subtree:true,childList:true,characterData:true});
 const observers=[];
 class Observer extends window.MutationObserver{constructor(fn){super(fn);observers.push(this);}}
 const source=readFileSync(new URL('../public/app.js',import.meta.url),'utf8');
 try{
  vm.runInNewContext(source.slice(source.indexOf('const discoverLabels=')),{document,MutationObserver:Observer});
  document.documentElement.lang='ar';
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(loopDetected,false,'translation must not keep scheduling itself');
  assert.equal(document.getElementById('discover-label').textContent,'اكتشف التصاميم');
  const settled=translations;
  document.documentElement.lang='ar';
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(translations,settled,'reapplying the same locale must not rewrite text');
  document.documentElement.lang='en';
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(document.getElementById('discover-label').textContent,'Discover designs');
 }finally{translator.disconnect();observers.forEach(o=>o.disconnect());}
});
