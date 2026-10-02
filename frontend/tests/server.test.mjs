import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import vm from 'node:vm';
import { createServer } from '../server.mjs';

let server,origin;
before(async()=>{server=createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));origin='http://127.0.0.1:'+server.address().port;});
after(()=>new Promise(r=>server.close(r)));
const get=p=>fetch(origin+p,{redirect:'manual'});
test('the actual verification response is byte exact, uncached and has no redirect',async()=>{
 const path='/.well-known/apple-developer-merchantid-domain-association';
 for(const host of ['findzia.com','www.findzia.com','preview.up.railway.app']){
  const r=await fetch(origin+path,{headers:{Host:host,'If-None-Match':'*'},redirect:'manual'});
  assert.equal(r.status,200);assert.equal(r.headers.get('location'),null);assert.equal(r.headers.get('cache-control'),'no-store');
  const b=Buffer.from(await r.arrayBuffer());assert.equal(b.length,9094);
  assert.equal(createHash('sha256').update(b).digest('hex'),'c15558d3e155e2031ef39b32775050c283b545d8575643181af3c3b9f03d46a3');
 }
 const h=await fetch(origin+path,{method:'HEAD'});assert.equal(h.headers.get('content-length'),'9094');assert.equal(await h.text(),'');
});
test('homepage is standalone and all linked local assets load',async()=>{
 const r=await get('/');assert.equal(r.status,200);const s=await r.text();assert.ok(!s.includes('{{')&&!s.includes('{%'));
 assert.ok(s.includes('https://api.findzia.com'));assert.ok(!s.includes('asset_url'));assert.ok(!s.includes('/cdn/shop/'));
 const links=[...s.matchAll(/(?:src|href)="(\/assets\/[^" ]+)"/g)].map(m=>m[1]);assert.equal(links.length,10);
 for(const link of links){const a=await get(link);assert.equal(a.status,200);assert.match(a.headers.get('cache-control'),/immutable/);}
 assert.match(r.headers.get('permissions-policy'),/payment=\*/);assert.ok(r.headers.get('content-security-policy').includes('frame-ancestors'));
});
test('legal pages keep the existing published text and routes',async()=>{
 for(const slug of ['terms-of-service','privacy-policy','refund-policy']){
  const r=await get('/policies/'+slug);assert.equal(r.status,200);const s=await r.text();
  const original=readFileSync(new URL('../source/policies/'+slug+'.html',import.meta.url),'utf8');assert.ok(s.includes(original));
  assert.ok(s.includes('info@findzia.com'));assert.ok(!s.includes('shopify-policy__container'));
 }
});
test('query strings for sign-in/payment returns stay on the homepage',async()=>{
 const r=await get('/?fz_mf_intent=sample&paymentId=sample');assert.equal(r.status,200);assert.equal(r.headers.get('location'),null);
});
test('private files, API paths and unknown assets are never exposed or rewritten to the app',async()=>{
 for(const p of ['/source/findzia-home.liquid','/server.mjs','/package.json','/release.json','/../README_AR.md','/%2e%2e%2fserver.mjs','/api/account/me','/assets/missing.js','/.env']) assert.equal((await get(p)).status,404,p);
 assert.equal((await fetch(origin+'/',{method:'POST',body:'x'})).status,405);
});
test('hashed assets revalidate, health responds, and WWW serves the file directly',async()=>{
 const h=await get('/healthz');assert.equal((await h.json()).version,'156.7.26');
 const p=await get('/');const again=await fetch(origin+'/',{headers:{'If-None-Match':p.headers.get('etag')}});assert.equal(again.status,304);
});
test('existing guest credentials survive API hostname change and rollback; existing new credentials win',()=>{
 const code=readFileSync(new URL('../source/findzia-migration.js',import.meta.url),'utf8');
 const old='findzia-guest-v1:https://coop-bot-g-production.up.railway.app',next='findzia-guest-v1:https://api.findzia.com';
 for(const existing of [null,'current-token']){
  const store=new Map([[old,'old-token']]);if(existing)store.set(next,existing);
  vm.runInNewContext(code,{document:{addEventListener(){}},localStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v)}});
  assert.equal(store.get(next),existing||'old-token');assert.equal(store.get(old),'old-token');
 }
 assert.doesNotThrow(()=>vm.runInNewContext(code,{document:{addEventListener(){}},localStorage:{getItem(){throw Error('Blocked');}}}));
});
