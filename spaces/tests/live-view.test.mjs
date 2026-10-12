import test from 'node:test';
import assert from 'node:assert/strict';
import {parseHTML} from 'linkedom';
import {patchHTML,pieceActivity,updateImage} from '../public/live-view.js';
globalThis.document=undefined;globalThis.Image=undefined;globalThis.matchMedia=undefined;
test('streaming results preserve image nodes, open details and unchanged cards',t=>{
 const {document}=parseHTML('<html><body><div id="root"></div></body></html>');t.mock.property(globalThis,'document',document);
 const root=document.getElementById('root');
 patchHTML(root,'<article data-ui-key="a"><img src="/crop.jpg"><p>Searching</p><details><summary>Differences</summary><p>Legs</p></details></article><article data-ui-key="b"><img src="/b.jpg"></article>');
 const a=root.children[0],image=a.querySelector('img'),b=root.children[1],details=a.querySelector('details');details.setAttribute('open','');
 patchHTML(root,'<article data-ui-key="a"><img src="/crop.jpg"><p>View store options</p><details><summary>Differences</summary><p>Legs</p></details></article><article data-ui-key="b"><img src="/b.jpg"></article><article data-ui-key="c">New option</article>');
 assert.equal(root.children[0],a);assert.equal(a.querySelector('img'),image);assert.equal(root.children[1],b);assert.equal(a.querySelector('details'),details);assert.ok(details.hasAttribute('open'));assert.match(a.textContent,/View store options/);
});
test('image changes wait for decode and a late old image cannot replace the newer request',async t=>{
 const {document}=parseHTML('<html><body><img id="photo" src="/old.jpg"></body></html>');const pending=[];
 t.mock.property(globalThis,'Image',class {constructor(){pending.push(this);}async decode(){}});
 t.mock.property(globalThis,'matchMedia',()=>({matches:true}));
 const image=document.getElementById('photo');updateImage(image,'/new-a.jpg');updateImage(image,'/new-b.jpg');
 assert.equal(image.getAttribute('src'),'/old.jpg');await pending[0].onload();assert.equal(image.getAttribute('src'),'/old.jpg');await pending[1].onload();assert.equal(image.getAttribute('src'),'/new-b.jpg');
});
test('activity distinguishes queued, active, automatic retry and complete results',()=>{
 assert.equal(pieceActivity({status:'idle'}),'Up next');assert.equal(pieceActivity({status:'searching',phase:'checking'}),'Checking matches');assert.equal(pieceActivity({status:'searching',search_attempt:2}),'Looking further');assert.equal(pieceActivity({status:'empty',phase:'complete'}),'');
});
