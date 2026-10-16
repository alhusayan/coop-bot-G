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
  assert.deepEqual(Object.keys(accountAssets),['i18n','support','account','billing','state','catalog','images']);
  const urls=[...html.matchAll(/(?:src|href)="(\/assets\/[^" ]+)"/g)].map(m=>m[1]);
  for(const path of [...urls,...Object.entries(accountAssets).filter(([key])=>key!=='images').map(([,value])=>value),...Object.values(accountAssets.images)])assert.equal((await fetch(origin+path)).status,200,path);
  assert.doesNotMatch(html,/<script[^>]*findzia-(?:shell|choice|ads|analytics)\./);
  const home=await(await fetch(origin+'/')).text();assert.match(home,/class="project-grid"/);assert.doesNotMatch(home,/data-services/);
 }finally{await new Promise(r=>server.close(r));}
});

import {initialServiceCountry,serviceSearchCredits,serviceResults} from '../source/findzia-services-state.js';
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

test('continuous results retain every row and sort the complete set',()=>{
 const rows=Array.from({length:12},(_,i)=>({title:String(i+1),rating:i+1}));
 assert.deepEqual(serviceResults(rows).items,rows);
 assert.deepEqual(serviceResults(rows,'rating').items.map(r=>r.title),[...rows].reverse().map(r=>r.title));
 assert.equal(serviceResults([]).items.length,0);
 assert.equal(rows[0].title,'1');
});

import {serviceWhatsApp,serviceLocation} from '../source/findzia-services-state.js';
import {serviceDirectory,serviceCount} from '../source/findzia-services-catalog.js';
test('WhatsApp requires an explicit safe link and its published business source',()=>{
 const row={tel:'tel:+96555551234',website:'https://example.com',whatsapp_source:'https://example.com',whatsapp:'https://wa.me/96555551234'};
 assert.equal(serviceWhatsApp(row),'https://wa.me/96555551234');
 assert.equal(serviceWhatsApp({tel:row.tel}),'');
 assert.equal(serviceWhatsApp({...row,whatsapp_source:''}),'');
 assert.equal(serviceWhatsApp({...row,whatsapp_source:'https://unrelated.example'}),'');
 for(const whatsapp of ['https://wa.me.evil.com/96555551234','https://wa.me/abc','javascript:alert(1)','https://wa.me/96555551234?text=hello',null])assert.equal(serviceWhatsApp({...row,whatsapp}),'');
});
test('location resolves an area and supported country without inventing either',()=>{
 assert.deepEqual(serviceLocation({countryCode:'KW',locality:'Salmiya',city:'Salmiya'}),{country:'KW',area:'Salmiya'});
 assert.deepEqual(serviceLocation({countryCode:'GB',locality:'Camden',city:'London'}),{country:'GB',area:'Camden, London'});
 assert.equal(serviceLocation({countryCode:'KW',countryName:'Kuwait'}),null);
 assert.equal(serviceLocation({countryCode:'ZZ',locality:'Unknown'}),null);
});
test('home directory includes custom work and maintenance without acting as a search whitelist',()=>{
 assert.ok(serviceDirectory.length>=7);assert.ok(serviceCount>=90);
 const names=serviceDirectory.flatMap(g=>g[3].map(r=>r[0]));assert.ok(names.includes('Wood wall panel installation'));assert.ok(names.includes('Home EV charger installation'));assert.ok(!names.includes('Car mechanic'));
 for(const group of serviceDirectory){assert.ok(group[0]&&group[1]&&group[3].length);for(const row of group[3])assert.ok(row[0]&&row[1]);}
});
test('GPS and geocoding are enabled only for the services document',async()=>{
 const server=createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
 try{const service=await fetch(origin+'/trial/services'),home=await fetch(origin+'/');
 assert.match(service.headers.get('permissions-policy'),/geolocation=\(self\)/);
 assert.match(service.headers.get('content-security-policy'),/https:\/\/api.bigdatacloud.net/);
 assert.doesNotMatch(home.headers.get('content-security-policy'),/bigdatacloud/);
 }finally{await new Promise(r=>server.close(r));}
});
