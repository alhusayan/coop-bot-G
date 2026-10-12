import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
process.env.NODE_ENV='production';process.env.SPACES_TRIAL_TOKEN='test-invite';process.env.SPACES_DATA_DIR=mkdtempSync(join(tmpdir(),'spaces-test-'));
const {createServer}=await import('../server.mjs');
test('private trial requires its invite, serves app assets, and does not reveal another session job',async()=>{
 const s=createServer();await new Promise(r=>s.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+s.address().port;
 try{
  assert.equal((await fetch(base+'/healthz')).status,200);
  assert.equal((await fetch(base+'/api/config')).status,401);
  assert.equal((await fetch(base+'/trial/wrong',{redirect:'manual'})).status,404);
  const unlock=await fetch(base+'/trial/test-invite',{redirect:'manual'});assert.equal(unlock.status,200);assert.equal(unlock.headers.get('location'),null);assert.match(await unlock.text(),/Findzia Spaces/);assert.equal(unlock.headers.get('cache-control'),'no-store');
  const cookie=unlock.headers.get('set-cookie').split(';')[0];const config=await fetch(base+'/api/config',{headers:{cookie}});assert.equal(config.status,200);assert.equal((await config.json()).markets.KW.currency,'KWD');
  const reopen=await fetch(base+'/trial/test-invite',{method:'HEAD',headers:{cookie}});assert.equal(reopen.status,200);assert.equal(reopen.headers.get('set-cookie').split('.')[0],cookie.split('.')[0]);
  // A second browser follows the very same URL, with no cookies from the first.
  const safari=await fetch(base+'/trial/test-invite',{redirect:'manual'});const safariCookie=safari.headers.get('set-cookie').split(';')[0];assert.equal(safari.status,200);assert.notEqual(safariCookie.split('.')[0],cookie.split('.')[0]);assert.equal((await fetch(base+'/api/config',{headers:{cookie:safariCookie}})).status,200);
  const oldHome=await fetch(base+'/',{headers:{cookie},redirect:'manual'});assert.equal(oldHome.status,303);assert.equal(oldHome.headers.get('location'),'/trial/test-invite');
  assert.equal((await fetch(base+'/trial/test-invite',{method:'POST'})).status,404);
  const other=await fetch(base+'/api/jobs/000000000000000000000000',{headers:{cookie}});assert.equal(other.status,404);
  const cross=await fetch(base+'/api/jobs',{method:'POST',headers:{cookie,'sec-fetch-site':'cross-site'},body:'{}'});assert.equal(cross.status,403);
  assert.equal((await fetch(base+'/lens-media/000000000000000000000000/crop-0-1.jpg?expires=9999999999999&sig=fake')).status,404);
  assert.equal((await fetch(base+'/lens-media/000000000000000000000000/original.jpg')).status,404);
  const root=await fetch(base+'/');const html=await root.text();assert.match(html,/Findzia Spaces/);assert.match(html,/<html lang="en" dir="ltr">/);assert.equal(root.headers.get('x-robots-tag'),'noindex, nofollow, noarchive');
  assert.match(html,/data-action="upload" disabled/);assert.match(html,/id="retry-access"/);
  assert.equal((await fetch(base+'/style.css')).status,200);assert.equal((await fetch(base+'/app.js')).status,200);assert.equal((await fetch(base+'/request.js')).status,200);
 }finally{await new Promise(r=>s.close(r));rmSync(process.env.SPACES_DATA_DIR,{recursive:true,force:true});}
});
