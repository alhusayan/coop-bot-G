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
  const unlock=await fetch(base+'/trial/test-invite',{redirect:'manual'});assert.equal(unlock.status,303);assert.equal(unlock.headers.get('location'),'/');
  const cookie=unlock.headers.get('set-cookie').split(';')[0];const config=await fetch(base+'/api/config',{headers:{cookie}});assert.equal(config.status,200);assert.equal((await config.json()).markets.KW.currency,'KWD');
  const other=await fetch(base+'/api/jobs/000000000000000000000000',{headers:{cookie}});assert.equal(other.status,404);
  const cross=await fetch(base+'/api/jobs',{method:'POST',headers:{cookie,'sec-fetch-site':'cross-site'},body:'{}'});assert.equal(cross.status,403);
  const root=await fetch(base+'/');assert.match(await root.text(),/Findzia Spaces/);assert.equal(root.headers.get('x-robots-tag'),'noindex, nofollow, noarchive');
  assert.equal((await fetch(base+'/style.css')).status,200);assert.equal((await fetch(base+'/app.js')).status,200);
 }finally{await new Promise(r=>s.close(r));rmSync(process.env.SPACES_DATA_DIR,{recursive:true,force:true});}
});
