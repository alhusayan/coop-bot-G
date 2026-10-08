import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from '../server.mjs';

async function withServer(env,run){
 const server=createServer(env);await new Promise(r=>server.listen(0,'127.0.0.1',r));
 try{await run('http://127.0.0.1:'+server.address().port);}finally{await new Promise(r=>server.close(r));}
}
test('runtime config is inert before account setup, never exposes other environment values',async()=>{
 await withServer({SECRET_KEY:'never-public'},async origin=>{
  const r=await fetch(origin+'/analytics-config.json');
  assert.deepEqual(await r.json(),{measurement_id:''});assert.equal(r.headers.get('cache-control'),'no-store');
 });
});
test('validated GA destination is served uncached; collection allowed by CSP; build loads exactly one analytics script',async()=>{
 await withServer({FINDZIA_GA4_MEASUREMENT_ID:'G-TEST12345'},async origin=>{
  const r=await fetch(origin+'/analytics-config.json');assert.deepEqual(await r.json(),{measurement_id:'G-TEST12345'});
  const csp=r.headers.get('content-security-policy');assert.match(csp,/connect-src[^;]*https:\/\/\*\.google-analytics\.com/);
  assert.match(csp,/frame-ancestors 'none'/);
  const html=await(await fetch(origin)).text();const links=[...html.matchAll(/src="(\/assets\/findzia-analytics\.[^"]+)"/g)];
  assert.equal(links.length,1);assert.equal((await fetch(origin+links[0][1])).status,200);
 });
});
test('malformed or non-GA identifiers cannot become a public config or script injection',()=>{
 for(const id of ['AW-18499186413','G-X</script>','https://evil.test','G-abc123'])assert.throws(()=>createServer({FINDZIA_GA4_MEASUREMENT_ID:id}),/Invalid/);
});
