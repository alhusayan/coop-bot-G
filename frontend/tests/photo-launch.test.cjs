/* Exercise the real camera intake and credit gate without spending credits. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const vm=require('node:vm');
const {join}=require('node:path');
const read=name=>readFileSync(join(__dirname,'../source',name),'utf8');
const home=read('findzia-home.liquid'),billing=read('findzia-billing.js');
const section=(source,start,end)=>source.slice(source.indexOf(start),source.indexOf(end,source.indexOf(start)));
function fixture(gate){
 const calls=[],events=[],states=[],nodes=[];
 const root={dataset:{homeState:'empty',cameraHandoff:'true',lang:'en'},fzRefineBridge:{snapshot:()=>({view:{items:[]}}),accountNotice:message=>calls.push(['notice',message])},
  dispatchEvent:event=>events.push(event),fzBilling:{beforeSearch:gate,status:()=>({remaining:0})}};
 const context={Promise,DOMException,AbortController,CustomEvent:class{constructor(type,init){this.type=type;this.detail=init.detail}},
  setTimeout,clearTimeout,window:{},document:{createElement:()=>({dataset:{},setAttribute(){}})},URL:{createObjectURL:()=> 'blob:test-photo'},
  e:root,fzPhotoPreviewURL:'',fzFailedPhotoFile:null,Le:0,K:'',g:{value:''},w:{hidden:true},W:null,B:0,U:[],b:{replaceChildren:n=>nodes.push(n),querySelector:()=>null},_:{classList:{add(){}}},
  fzClearPhotoPreview(){context.fzPhotoPreviewURL=''},fzUpdatePhotoUI(){},Ut(){},Bt(){return ++context.B},
  Ue(home){root.dataset.homeState=home?'empty':'results';states.push(root.dataset.homeState)},
  fr(busy){root.busy=busy},ar:x=>x,nr:()=> 'en',zt(){},cr(){},Pt:async()=> 'KW',Ft(){},
  fzPreparePhotoUpload:async file=>{calls.push(['upload',file]);return {image_base64:'test-image',mime_type:'image/jpeg'}},
  fzSearchPhoto:async(payload,generation)=>{calls.push(['search',payload,generation]);context.U.push({title:'Test tissue box',price:2})},
  St:()=>calls.push(['render',context.U.length]),Ke(){},fzPhotoSearchFailed:error=>calls.push(['error',error.message]),fzPhotoUploadFailed:()=>{throw Error('unexpected upload failure')}};
 vm.createContext(context);
 vm.runInContext(section(home,'var fzPendingLaunch=null;','e.fzRefineBridge.billingResume='),context);
 vm.runInContext(section(billing,'  function abortable(','  const el =')+section(billing,'  async function waitFor(','  function pendingStore('),context);
 vm.runInContext(section(home,'async function fzAcceptPhoto(file)','function fzPhotoUploadFailed('),context);
 return{context,root,calls,events,states,nodes};
}
test('camera file reaches search exactly once and renders received matches after credit approval',async()=>{
 let release;const f=fixture(()=>new Promise(resolve=>release=resolve)),file={name:'capture.jpg',size:12000};
 const result=f.context.fzAcceptPhoto(file);await Promise.resolve();await Promise.resolve();
 assert.equal(f.root.dataset.homeState,'results','show progress before network/credit latency');assert.equal(f.root.busy,true);
 assert.equal(f.calls.length,0,'no upload or paid retrieval before authorization');
 release(true);assert.equal(await result,true);
 assert.equal(f.calls.filter(x=>x[0]==='search').length,1);assert.equal(f.calls.find(x=>x[0]==='upload')[1],file);
 assert.equal(f.calls.find(x=>x[0]==='search')[1].image_base64,'test-image');assert.deepEqual(f.calls.at(-1),['render',1]);
 assert.equal(f.root.dataset.homeState,'results');assert.equal(f.root.busy,false);
});
test('credit check failure emits visible recovery instead of silently returning to the landing',async()=>{
 const f=fixture(async()=>{throw Error('offline')});assert.equal(await f.context.fzAcceptPhoto({name:'photo.jpg'}),false);
 const blocked=f.events.find(x=>x.type==='fz:search-blocked');assert.equal(blocked.detail.code,'credits_unavailable');assert.match(blocked.detail.message,/try again/i);
 assert.equal(f.root.dataset.homeState,'empty');assert.equal(f.root.busy,false);assert.ok(!f.calls.some(x=>x[0]==='search'));
});
test('a denied search never uploads or spends credit and restores a usable landing',async()=>{
 const f=fixture(async()=>false);assert.equal(await f.context.fzAcceptPhoto({name:'photo.jpg'}),false);
 assert.equal(f.root.dataset.homeState,'empty');assert.equal(f.root.busy,false);assert.equal(f.context.fzPhotoPreviewURL,'');
 assert.ok(!f.calls.some(x=>['search','upload'].includes(x[0])));
});
