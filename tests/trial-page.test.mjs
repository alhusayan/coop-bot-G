import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createServer} from '../frontend/server.mjs';
const config=JSON.parse(readFileSync(new URL('../frontend/trial.json',import.meta.url),'utf8'));
test('trial is isolated from public home, not indexed, and served without cache',async()=>{
  const server=createServer({});await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const origin='http://127.0.0.1:'+server.address().port;
  try{
    const home=await (await fetch(origin+'/')).text();
    assert.ok(!home.includes('data-choice-preview'));
    assert.ok(!home.includes('findzia-choice.'));
    assert.ok(!home.includes(config.path));
    const response=await fetch(origin+config.path,{headers:{Host:'findzia.com'}});
    assert.equal(response.status,200);
    assert.match(response.headers.get('x-robots-tag'),/noindex/);
    assert.equal(response.headers.get('cache-control'),'no-store');
    assert.equal(response.headers.get('referrer-policy'),'no-referrer');
    const trial=await response.text();
    assert.ok(trial.includes('data-choice-preview="true"'));
    assert.ok(trial.includes('findzia-choice.'));
    assert.ok(!trial.includes('findzia-ads.'));
    assert.ok(!trial.includes('findzia-analytics.'));
    assert.ok(!trial.includes('rel="canonical"'));
    assert.equal((await fetch(origin+config.path+'/')).status,200);
    assert.equal((await fetch(origin+config.path,{method:'HEAD'})).status,200);
    assert.equal((await fetch(origin+'/trial/one-wrong')).status,404);
    assert.ok(!(await (await fetch(origin+'/sitemap.xml')).text()).includes('/trial/'));
    assert.match(await (await fetch(origin+'/robots.txt')).text(),/Disallow: \/trial\//);
    assert.equal((await fetch(origin+'/.well-known/apple-developer-merchantid-domain-association')).status,200);
  }finally{await new Promise(r=>server.close(r));}
});
