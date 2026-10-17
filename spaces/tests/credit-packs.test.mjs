import test from 'node:test';
import assert from 'node:assert/strict';
import {parseHTML} from 'linkedom';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync(new URL('../public/findzia/billing.js',import.meta.url),'utf8');
const render=source.slice(source.indexOf('    function renderCreditPacks('),source.indexOf('    function renderPlans('));
test('balance notice lists live one-time packs and exact prices without starting checkout',()=>{
 const {document}=parseHTML('<html><body><div id="packs"></div></body></html>'),actions=[];
 const el=(tag,cls='',text='')=>{const node=document.createElement(tag);node.className=cls;node.textContent=text;return node;};
 const button=(text,fn,cls)=>{const node=el('button',cls,text);node.addEventListener('click',fn);return node;};
 const context={config:{plans:[{id:'live-a',name:'Starter',credits:14,amount_cents:777,interval:'once'},{id:'live-b',name:'Extra',credits:30,amount_cents:1234,interval:'once'},{id:'old-monthly',name:'Legacy',credits:100,amount_cents:999,interval:'month'}]},status:null,el,button,tr:en=>en,tf:(en,vars)=>en.replace('{count}',vars.count),account:{open:view=>actions.push(view)},choosePlan:id=>actions.push(id),Intl};
 vm.runInNewContext(render+';this.renderCreditPacks=renderCreditPacks;',context);
 const body=document.querySelector('#packs');assert.equal(context.renderCreditPacks(body,{onChoose:()=>actions.push('close-results')}),true);
 const rows=body.querySelectorAll('button');assert.equal(rows.length,2);assert.match(rows[0].textContent,/Starter14 credits\$7\.77/);assert.match(rows[1].textContent,/\$12\.34/);assert.deepEqual(actions,[]);
 rows[1].click();assert.deepEqual(actions,['close-results','plans','live-b']);
 context.config.plans=[];assert.equal(context.renderCreditPacks(body),false);assert.equal(body.childElementCount,0);
});

test('the design instruction precedes the image and original-photo preview has no white footer',()=>{
 const html=readFileSync(new URL('../public/index.html',import.meta.url),'utf8');
 assert.ok(html.indexOf('class="stage-hint"')<html.indexOf('class="scene-pick-media"'));assert.equal((html.match(/class="stage-hint"/g)||[]).length,1);
 const app=readFileSync(new URL('../public/app.js',import.meta.url),'utf8');const start=app.indexOf("case 'original':"),action=app.slice(start,app.indexOf('break;',start));
 assert.match(action,/original-preview/);assert.doesNotMatch(action,/preview-actions/);
});
