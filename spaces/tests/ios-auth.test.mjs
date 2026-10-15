import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync,mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
const source=readFileSync(new URL('../public/ios-auth.js',import.meta.url),'utf8');
function run(hash){
 const link={},status={},redirects=[];
 const location={hash,pathname:'/ios/auth/callback',replace:url=>redirects.push(url)};
 let cleared=false;
 vm.runInNewContext(source,{URLSearchParams,location,history:{replaceState:()=>{cleared=true;}},document:{getElementById:id=>id==='status'?status:link}});
 return {link,status,redirects,cleared};
}
test('OAuth handoff forwards only the code and flow to the fixed iPhone scheme',()=>{
 const code='x'.repeat(48),flow='y'.repeat(32);
 const app=run('#findzia-login='+code+'&flow='+flow+'&redirect=https://evil.example/');
 assert.equal(app.redirects.length,1);assert.equal(app.link.hidden,false);assert.ok(app.cleared);
 assert.equal(app.redirects[0],'findzia-ios://auth/callback#findzia-login='+code+'&flow='+flow);
});
test('malformed handoffs do not redirect and errors contain no arbitrary text',()=>{
 for(const hash of ['','#findzia-login=x&flow=x','#findzia-login=%3Cscript%3E&flow=x'])assert.equal(run(hash).redirects.length,0);
 assert.equal(run('#findzia-auth-error=arbitrary').redirects[0],'findzia-ios://auth/callback#findzia-auth-error=sign_in_failed');
});
test('callback files are publicly served without cookies, never cached, and protected by CSP',async()=>{
 process.env.NODE_ENV='production';process.env.SPACES_DATA_DIR=mkdtempSync(join(tmpdir(),'spaces-ios-test-'));
 const {createServer}=await import('../server.mjs');
 const server=createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
 try{
  const base='http://127.0.0.1:'+server.address().port;
  for(const path of ['/ios/auth/callback','/ios/auth/callback.js']){
   const res=await fetch(base+path);assert.equal(res.status,200);assert.equal(res.headers.get('cache-control'),'no-store');
   assert.equal(res.headers.get('referrer-policy'),'no-referrer');assert.match(res.headers.get('content-security-policy'),/script-src 'self'/);
  }
 }finally{await new Promise(r=>server.close(r));rmSync(process.env.SPACES_DATA_DIR,{recursive:true,force:true});}
});
