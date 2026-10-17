import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {parseHTML} from 'linkedom';
import {sceneText,sceneLanguages} from '../public/space-scene-copy.js';
const source=readFileSync(new URL('../public/app.js',import.meta.url),'utf8');
const prepare=source.slice(source.indexOf('async function prepareRedesign()'),source.indexOf('async function loadFile('));
function fixture(){
 const {document}=parseHTML(readFileSync(new URL('../public/index.html',import.meta.url),'utf8'));
 let current=true,screen='',fetches=0;
 const job={id:'saved-room',original:'/media/saved/original.jpg',options:{request:'Warm colours',scope:'decor'},designs:[{image:'/design.jpg'}]};
 const context={state:{job,image:'data:image/jpeg;base64,original'},roomContext:{capture:()=>1,current:()=>current},submitting:false,active:()=>false,$:s=>document.querySelector(s),view:name=>screen=name,
  fetch:async()=>{fetches++;return{ok:true,blob:async()=>({type:'image/jpeg'})}},File:class{},normalizeImage:async()=> 'data:image/jpeg;base64,restored'};
 vm.createContext(context);vm.runInContext(prepare,context);
 return{document,context,job,run:()=>vm.runInContext('prepareRedesign()',context),invalidate:()=>current=false,get screen(){return screen},get fetches(){return fetches}};
}
test('redesign and new-photo controls are visible in both result views and pretranslated',()=>{
 const f=fixture();for(const view of ['designs','shopping'])for(const action of ['redesign','new-design'])assert.ok(f.document.querySelector('#'+view+' [data-action="'+action+'"]'));
 for(const language of sceneLanguages)for(const key of ['redesign','newDesign'])assert.notEqual(sceneText(language,key),key);
});
test('redesign reuses the original photo and preferences without a request or credit charge',async()=>{
 const f=fixture();await f.run();assert.equal(f.context.state.job,f.job);assert.equal(f.fetches,0);assert.equal(f.screen,'setup');assert.equal(f.document.querySelector('#upload-preview').getAttribute('src'),f.context.state.image);assert.equal(f.document.querySelector('#design-request').value,'Warm colours');assert.equal(f.document.querySelector('[name=scope][value=decor]').checked,true);
});
test('saved history can restore its original photo, while stale and busy actions cannot replace the current view',async()=>{
 const f=fixture();f.context.state.image=null;await f.run();assert.equal(f.fetches,1);assert.equal(f.context.state.image,'data:image/jpeg;base64,restored');
 const stale=fixture();stale.context.state.image=null;stale.invalidate();await stale.run();assert.equal(stale.screen,'');assert.equal(stale.context.state.image,null);
 const busy=fixture();busy.context.submitting=true;await busy.run();assert.equal(busy.screen,'');assert.equal(busy.fetches,0);
});
test('new design opens the picker synchronously and cancelling leaves the current job intact',async()=>{
 const f=fixture();let click,opened=0;const input=f.document.querySelector('#file-input');input.click=()=>opened++;
 const context={...f.context,document:{addEventListener:(name,handler)=>click=handler},gestureDragged:false,toast:message=>{throw Error(message)}};
 vm.runInNewContext(source.slice(source.indexOf("document.addEventListener('click',async e=>"),source.indexOf("$('#sheet').addEventListener('click'")),context);
 const button=f.document.querySelector('#designs [data-action="new-design"]');await click({target:button});
 assert.equal(opened,1);assert.equal(context.state.job,f.job);assert.equal(context.state.image,'data:image/jpeg;base64,original');
});
