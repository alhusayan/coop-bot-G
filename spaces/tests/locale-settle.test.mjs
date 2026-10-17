import {sceneText} from '../public/space-scene-copy.js';
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {parseHTML} from 'linkedom';

test('Scene text and accessible labels settle when the page translator reapplies the same locale',async()=>{
 const {document,window}=parseHTML('<html lang="en"><body><span id="discover-label" data-scene="create">Create designs</span><button class="scene-options" aria-label="Design options"></button><dialog id="space-options"></dialog></body></html>');
 let translations=0,loopDetected=false;
 // The actual translator observes accessible labels as well as text, and reapplies html.lang.
 // Bound the fixture so a regression fails instead of freezing the test runner.
 const translator=new window.MutationObserver(()=>{
  if(++translations>10){loopDetected=true;translator.disconnect();return;}
  document.documentElement.lang=document.documentElement.lang;
 });
 translator.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['aria-label','placeholder','title','alt']});
 const observers=[];
 class Observer extends window.MutationObserver{constructor(fn){super(fn);observers.push(this);}}
 const source=readFileSync(new URL('../public/app.js',import.meta.url),'utf8');
 try{
  vm.runInNewContext(source.slice(source.indexOf('function refreshSceneCopy()')),{document,sceneText,$:q=>document.querySelector(q),$$:q=>[...document.querySelectorAll(q)],MutationObserver:Observer});
  document.documentElement.lang='ar';
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(loopDetected,false,'translation must not keep scheduling itself');
  assert.equal(document.getElementById('discover-label').textContent,'صمّم');
  assert.equal(document.querySelector('.scene-options').getAttribute('aria-label'),'خيارات');
  const settled=translations;
  document.documentElement.lang='ar';
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(translations,settled,'reapplying the same locale must not rewrite text');
  document.documentElement.lang='en';
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(document.getElementById('discover-label').textContent,'Create designs');
 }finally{translator.disconnect();observers.forEach(o=>o.disconnect());}
});

test('the shipped translator and Space scene yield to timers during startup and locale changes',async()=>{
 const {document,window}=parseHTML(readFileSync(new URL('../public/index.html',import.meta.url),'utf8'));
 const observers=[];let callbacks=0,loopDetected=false;
 class Observer extends window.MutationObserver{
  constructor(fn){super(records=>{if(++callbacks>100){loopDetected=true;observers.forEach(o=>o.disconnect());return;}fn(records);});observers.push(this);}
 }
 const context=vm.createContext({document,window,sceneText,MutationObserver:Observer,queueMicrotask,NodeFilter:{SHOW_TEXT:4},localStorage:{getItem:()=>null,setItem(){}},$:q=>document.querySelector(q),$$:q=>[...document.querySelectorAll(q)]});
 const source=readFileSync(new URL('../public/app.js',import.meta.url),'utf8');
 try{
  vm.runInContext(source.slice(source.indexOf('function refreshSceneCopy()')),context);
  vm.runInContext(readFileSync(new URL('../public/findzia/i18n.js',import.meta.url),'utf8'),context);
  document.dispatchEvent(new window.Event('DOMContentLoaded'));
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(loopDetected,false,'startup must yield to module loading and the opening timeout');
  for(const language of ['ar','en','ja']){
   window.FindziaI18n.set(document.querySelector('.fz-home'),language);
   await new Promise(resolve=>setTimeout(resolve,0));
   assert.equal(loopDetected,false,language+' must settle');
   assert.equal(document.querySelector('.scene-options').getAttribute('aria-label'),sceneText(language,'options'));
   assert.equal(document.querySelector('#discover-label').textContent,sceneText(language,'create'));
   const settled=callbacks;
   await new Promise(resolve=>setTimeout(resolve,0));
   assert.equal(callbacks,settled,'no self-perpetuating updates');
  }
 }finally{observers.forEach(o=>o.disconnect());}
});
