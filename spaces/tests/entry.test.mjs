import {test} from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../public/app.js',import.meta.url),'utf8');

test('selecting a local photo previews it while account/config are still pending',async()=>{
 const nodes=new Map(),$=key=>{if(!nodes.has(key))nodes.set(key,{reset(){},value:'selected'});return nodes.get(key)};
 const state={auth:null},views=[];
 const context={state,$,roomContext:{capture:()=>1,current:()=>true},resetRoom(){},normalizeImage:async()=> 'data:image/jpeg;fixture',view:name=>views.push(name),toast:assert.fail,init:()=>assert.fail('photo selection must not wait for network')};
 await vm.runInNewContext(source.slice(source.indexOf('async function loadFile('),source.indexOf("$('#file-input').addEventListener"))+';loadFile({name:"room.jpg"})',context);
 assert.equal(state.image,'data:image/jpeg;fixture');assert.equal($('#upload-preview').src,state.image);
 assert.deepEqual(views,['setup']);assert.equal($('#file-input').value,'');
});

test('generation still requires access before charging or creating a job',async()=>{
 const start=source.indexOf("$('#design-form').addEventListener('submit'");
 const end=source.indexOf('\n',start),handlers={},button={};let credits=0,jobs=0;
 const context={$:selector=>selector==='#design-form'?{addEventListener:(name,fn)=>handlers[name]=fn}:button,
  submitting:false,state:{image:'local-photo',auth:null},roomContext:{begin:()=>1,current:()=>true},pollTimer:null,clearTimeout(){},
  init:async()=>false,shellReady:Promise.resolve(),document:{querySelector:()=>({fzBilling:{authorizeDesign:async()=>{credits++;return {}}}})},api:async()=>{jobs++},toast:assert.fail};
 vm.runInNewContext(source.slice(start,end),context);
 await handlers.submit({preventDefault(){}});
 assert.equal(credits,0);assert.equal(jobs,0);assert.equal(context.submitting,false);assert.equal(button.disabled,false);
});
