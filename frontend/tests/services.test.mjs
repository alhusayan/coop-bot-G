import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from '../server.mjs';

test('services trial is separate, unindexed, and connects the original account assets',async()=>{
 const server=createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const origin='http://127.0.0.1:'+server.address().port;
 try{
  const response=await fetch(origin+'/trial/services');assert.equal(response.status,200);
  assert.match(response.headers.get('x-robots-tag'),/noindex/);assert.equal(response.headers.get('cache-control'),'no-store');
  const html=await response.text();assert.match(html,/data-services/);assert.doesNotMatch(html,/\{\{|\{%/);
  const accountAssets=JSON.parse(html.match(/data-service-assets='([^']+)'/)[1]);
  assert.deepEqual(Object.keys(accountAssets),['i18n','support','account','billing','state']);
  const urls=[...html.matchAll(/(?:src|href)="(\/assets\/[^" ]+)"/g)].map(m=>m[1]);
  for(const path of [...urls,...Object.values(accountAssets)])assert.equal((await fetch(origin+path)).status,200,path);
  assert.doesNotMatch(html,/<script[^>]*findzia-(?:shell|choice|ads|analytics)\./);
  const home=await(await fetch(origin+'/')).text();assert.match(home,/See it\. Find it\./);assert.doesNotMatch(home,/data-services/);
 }finally{await new Promise(r=>server.close(r));}
});

import {initialServiceCountry,serviceSearchCredits} from '../source/findzia-services-state.js';
test('service market uses Findzia preferences and supported browser regions',()=>{
 const read=values=>key=>values[key]||'';
 assert.equal(initialServiceCountry(read({'findzia-market-country-v1':'gb'}),{zone:'Asia/Kuwait'}),'GB');
 assert.equal(initialServiceCountry(read({'findzia-market-country-v1':'GB','findzia-services-country-v1':'KW'})),'KW');
 assert.equal(initialServiceCountry(read({}),{zone:'Asia/Tokyo'}),'JP');
 assert.equal(initialServiceCountry(read({}),{zone:'America/Vancouver'}),'CA');
 assert.equal(initialServiceCountry(read({}),{languages:['fr-FR']}),'FR');
 assert.equal(initialServiceCountry(read({'findzia-services-country-v1':'invalid'}),{zone:'Asia/Kuwait'}),'KW');
});

test('service searches distinguish design-only trial credits from usable credit',()=>{
 assert.equal(serviceSearchCredits({credit_unit:'flexible',remaining:3,free_designs:3,free_searches:0,flexible_remaining:0}),0);
 assert.equal(serviceSearchCredits({credit_unit:'flexible',remaining:5,free_designs:3,free_searches:1,flexible_remaining:0}),2);
 assert.equal(serviceSearchCredits({credit_unit:'flexible',remaining:2,free_searches:0,flexible_remaining:2}),2);
 assert.equal(serviceSearchCredits({remaining:4}),4);
 assert.equal(serviceSearchCredits(null),null);
});
