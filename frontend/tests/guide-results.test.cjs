const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=readFileSync(path.join(__dirname,'../source/findzia-filters.js'),'utf8');
const home=readFileSync(path.join(__dirname,'../source/findzia-home.liquid'),'utf8');
function identity(){const start=source.indexOf('const guideIdentity='),end=source.indexOf('function mount(root)',start);const env={};vm.createContext(env);vm.runInContext(source.slice(start,end)+';this.guard=guideIdentity;',env);return env.guard;}

test('cached model-changing questions and two-model rewrites never reach the interview',()=>{
 const g=identity();
 for(const [base,wrong] of [['iPhone 18 Pro','iPhone 15 Pro Max'],['آيفون ١٨ برو','iPhone 18 Pro Max'],['Galaxy S26 Ultra','Galaxy S25 Ultra'],['MacBook Air M4','MacBook Pro M4'],['Babolat Pure Aero','Pure Drive']]){
  assert.equal(g.compatible(base,base+' '+wrong),false);
  const result=g.response(base,{question:'Choose a colour for '+wrong,choices:[{label:'Black',answer:'black'}],search_query:base+' '+wrong});
  assert.equal(result.question,'');assert.equal(result.choices.length,0);assert.equal(result.search_query,'');
 }
 assert.equal(g.response('iPhone 18 Pro',{question:'Which model do you prefer?',choices:[]}).question,'');
});

test('valid refinements, generic product questions and manual photo details survive',()=>{
 const g=identity();assert.equal(g.compatible('iPhone 18 Pro','iPhone 18 Pro Black 1 TB',true),true);
 const question={question:'Preferred colour?',question_key:'colour',choices:[{label:'Black',answer:'black'}],search_query:'iPhone 18 Pro Black'};
 assert.equal(g.response('iPhone 18 Pro',question).question,question.question);
 assert.equal(g.response('phone',question),question);
});

function resultsFixture(){
 const buttons=['all','local','alternative','global'].map(key=>({dataset:{filter:key},attrs:{},label:{},count:{},classList:{toggle(){}},setAttribute(k,v){this.attrs[k]=v;},querySelector(s){return s==='[data-category-label]'?this.label:this.count;}}));
 const env={U:[{id:1,market:'local',ready:true},{id:2,market:'global',ready:true},{id:3,market:'local',photo_match_status:'similar',ready:true},{id:4,market:'global',photo_match_status:'rejected',ready:true},{id:5,market:'local',ready:false}],O:'all',I:'relevance',n:'KW',lang:'en',
  Fr:r=>r.market,kr:r=>r.country,ht:r=>!!r.ready,fzOfferCanDisplay:()=>true,fzEarlyPhotoPreview:()=>false,zr:()=>({tier:0,score:0}),Sr:()=>0,tr:()=>env.lang,
  X:null,w:{hidden:true,setAttribute(){},querySelectorAll(){return buttons;}}};
 vm.createContext(env);const start=home.indexOf('function fzResultCategory('),end=home.indexOf('function at(',start);vm.runInContext(home.slice(start,end),env);return {env,buttons};
}
test('All Local Similar Global filter real admitted rows and keep full category counts',()=>{
 const {env,buttons}=resultsFixture();assert.equal(env.tt().length,3);
 for(const [key,ids] of [['local',[1]],['alternative',[3]],['global',[2]],['all',[1,2,3]]]){
  env.O=key;assert.deepEqual(Array.from(env.tt(),r=>r.id),ids);env.w.hidden=true;env.fzUpdateResultTabs(env.tt('all'));
  assert.equal(env.w.hidden,false,'text-result updates must reveal the category controls');
  assert.deepEqual(buttons.map(b=>b.count.textContent),[3,1,1,1]);
  assert.equal(buttons.filter(b=>b.attrs['aria-pressed']==='true')[0].dataset.filter,key);
 }
 env.lang='ar';env.fzUpdateResultTabs(env.tt('all'));assert.deepEqual(buttons.map(b=>b.label.textContent),['الكل','محلي','مشابه','عالمي']);
 env.O='local';env.U.push({id:6,market:'global',ready:true});env.fzUpdateResultTabs(env.tt('all'));assert.equal(buttons[3].count.textContent,2);assert.deepEqual(Array.from(env.tt(),r=>r.id),[1]);
 env.U=env.U.filter(r=>r.market!=='local');assert.equal(env.tt().length,0);assert.equal(env.tt('all').length,2);
 env.fzUpdateResultTabs(env.tt('all'));assert.equal(env.w.hidden,false,'an empty category must keep navigation visible');
});

test('every built inline script parses',()=>{
 const html=readFileSync(path.join(__dirname,'../public/index.html'),'utf8');
 for(const m of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi))if(m[1].trim())new vm.Script(m[1]);
});
