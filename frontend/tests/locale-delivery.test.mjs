import {test,after} from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {readFileSync} from 'node:fs';
import {gunzipSync,brotliDecompressSync} from 'node:zlib';
import {createServer} from '../server.mjs';
const manifest=JSON.parse(readFileSync(new URL('../public/release.json',import.meta.url),'utf8'));
const route=Object.keys(manifest.routes).find(p=>p.includes('findzia-i18n.'));
const original=readFileSync(new URL('../public/'+manifest.routes[route].file,import.meta.url));
const server=createServer({});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
after(()=>new Promise(resolve=>server.close(resolve)));
function request(path,headers={},method='GET'){
 return new Promise((resolve,reject)=>{
  const req=http.request({host:'127.0.0.1',port:server.address().port,path,headers,method},res=>{
   const chunks=[];res.on('data',c=>chunks.push(c));res.on('end',()=>resolve({status:res.statusCode,headers:res.headers,body:Buffer.concat(chunks)}));
  });req.on('error',reject);req.end();
 });
}
test('compressed language bundles decode exactly and use encoding-specific cache validators',async()=>{
 const identity=await request(route),br=await request(route,{'accept-encoding':'br, gzip'}),gzip=await request(route,{'accept-encoding':'br;q=0,gzip'});
 assert.deepEqual(identity.body,original);
 assert.equal(br.headers['content-encoding'],'br');assert.deepEqual(brotliDecompressSync(br.body),original);
 assert.equal(gzip.headers['content-encoding'],'gzip');assert.deepEqual(gunzipSync(gzip.body),original);
 assert.ok(br.body.length<original.length/2);assert.equal(br.headers.vary,'Accept-Encoding');
 assert.notEqual(br.headers.etag,identity.headers.etag);
 const cached=await request(route,{'accept-encoding':'br','if-none-match':br.headers.etag});assert.equal(cached.status,304);
 const other=await request(route,{'if-none-match':br.headers.etag});assert.equal(other.status,200);
 const head=await request(route,{'accept-encoding':'gzip'},'HEAD');assert.equal(head.body.length,0);assert.equal(Number(head.headers['content-length']),gzip.body.length);
 const disabled=await request(route,{'accept-encoding':'br;q=0,gzip;q=0'});assert.equal(disabled.headers['content-encoding'],undefined);
});
test('Apple Pay certificate and Google Ads permissions are preserved',async()=>{
 const file=await request('/.well-known/apple-developer-merchantid-domain-association',{'accept-encoding':'br, gzip'});
 assert.equal(file.headers['content-encoding'],undefined);assert.equal(file.body.length,9094);
 assert.match(file.headers['content-security-policy'],/script-src[^;]*https:\/\/googleads\.g\.doubleclick\.net/);
});
