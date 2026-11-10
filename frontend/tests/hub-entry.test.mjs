import {test} from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
const read=path=>readFileSync(new URL(path,import.meta.url),'utf8');
const suite=read('./hub.test.mjs');
const fixtureCode=suite.slice(suite.indexOf('function hubFixture('),suite.indexOf("test('open, close, reopen"));
const hubFixture=vm.runInNewContext(fixtureCode+';hubFixture',{vm,read,URL});

test('Design reveals interactive controls once, without waiting for the account',()=>{
 const f=hubFixture('https://findzia.com/?project=space'),frame=f.frames[0],motions=[];
 frame.animate=(frames,options)=>motions.push({frames,options});
 assert.equal(frame.dataset.surface,'pending');assert.equal(f.node('#layer-status').hidden,false);
 const message=type=>f.listeners.message({origin:'https://findzia.com',source:frame.contentWindow,data:{findziaHub:true,type}});
 message('surface-ready');assert.equal(frame.dataset.surface,'ready');assert.equal(motions.length,1);
 assert.equal(f.node('#layer-status').hidden,true);assert.equal(motions[0].options.duration,240);
 assert.equal(f.html.style['--hub-height'],'560px');
 message('ready');frame.fire('load');assert.equal(motions.length,1,'account and load do not restart the entrance');
 f.node('#close-layer').fire('click');f.groups['[data-project]'].find(x=>x.dataset.project==='space').fire('click');
 assert.equal(f.frames.length,1);assert.equal(frame.hidden,false);assert.equal(motions.length,1);
 assert.equal(f.node('#layer-status').hidden,true);
});

test('late readiness from a hidden Design cannot reveal the new section',()=>{
 const f=hubFixture('https://findzia.com/?project=space'),space=f.frames[0];
 f.groups['[data-project]'].find(x=>x.dataset.project==='services').fire('click');
 const services=f.frames.at(-1);
 f.listeners.message({origin:'https://findzia.com',source:space.contentWindow,data:{findziaHub:true,type:'surface-ready'}});
 assert.equal(services.dataset.surface,'pending');assert.equal(f.node('#layer-status').hidden,false);
 services.fire('load');assert.equal(services.dataset.surface,'ready');
});
