const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const source=fs.readFileSync(require('node:path').join(__dirname,'../source/findzia-ads.js'),'utf8');
function setup(){
  const listeners={},scripts=[];
  const window={location:{href:'https://findzia.com/',origin:'https://findzia.com'}};
  const document={head:{appendChild:s=>scripts.push(s)},createElement:()=>({}),addEventListener:(t,f)=>listeners[t]=f};
  const context=vm.createContext({window,document,URL});vm.runInContext(source,context);
  return {window,listeners,scripts,context};
}
function fire(app, options={}){
  const event={type:'click',button:0,isTrusted:true,defaultPrevented:false,target:{closest:()=>({href:'https://store.example/product',target:'_blank'})},...options};
  app.listeners[event.type](event);return event;
}
const conversions=a=>a.window.dataLayer.filter(x=>x[0]==='event');
test('loads base tag once and does not convert page loads',()=>{
  const a=setup();vm.runInContext(source,a.context);assert.equal(a.scripts.length,1);assert.equal(conversions(a).length,0);
});
test('merchant click sends exact label, preserving native navigation',()=>{
  const a=setup();const e=fire(a);assert.equal(conversions(a).length,1);
  assert.equal(conversions(a)[0][2].send_to,'AW-18499186413/Z9ulCObypZQdEO3djPVE');
  assert.equal(e.defaultPrevented,false);assert.equal(a.window.location.href,'https://findzia.com/');
  assert.equal(conversions(a)[0][2].event_callback,undefined);
});
test('ignores non-product, internal, cancelled and synthetic clicks',()=>{
  const a=setup();fire(a,{target:{closest:()=>null}});
  for(const href of ['https://findzia.com/account','https://api.findzia.com/','javascript:void(0)'])fire(a,{target:{closest:()=>({href})}});
  fire(a,{defaultPrevented:true});fire(a,{isTrusted:false});fire(a,{button:2});
  assert.equal(conversions(a).length,0);
});
test('counts middle-click once, ignores right-click',()=>{
  const a=setup();fire(a,{type:'auxclick',button:1});fire(a,{type:'auxclick',button:2});assert.equal(conversions(a).length,1);
});
test('unavailable tag does not break merchant links',()=>{
 const a=setup();a.window.gtag=()=>{throw Error('blocked')};assert.doesNotThrow(()=>fire(a));
});
