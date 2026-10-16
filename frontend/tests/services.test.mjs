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
  assert.deepEqual(Object.keys(accountAssets),['i18n','support','account','billing']);
  const urls=[...html.matchAll(/(?:src|href)="(\/assets\/[^" ]+)"/g)].map(m=>m[1]);
  for(const path of [...urls,...Object.values(accountAssets)])assert.equal((await fetch(origin+path)).status,200,path);
  assert.doesNotMatch(html,/<script[^>]*findzia-(?:shell|choice|ads|analytics)\./);
  const home=await(await fetch(origin+'/')).text();assert.match(home,/See it\. Find it\./);assert.doesNotMatch(home,/data-services/);
 }finally{await new Promise(r=>server.close(r));}
});
