import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createServer} from '../server.mjs';

test('original and test pages serve their own complete assets and API scope',async()=>{
  const server=createServer({});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const base='http://127.0.0.1:'+server.address().port;
  try{
    const main=await fetch(base+'/'); const mainHTML=await main.text();
    assert.equal(main.status,200);
    assert.equal(mainHTML,readFileSync(new URL('../public/index.html',import.meta.url),'utf8'));
    assert.ok(!mainHTML.includes('findzia-catalog'));
    assert.ok(!mainHTML.includes('https://api.findzia.com/test'));
    for(const path of ['/test','/test/','/test/discover']){
      const response=await fetch(base+path);const html=await response.text();
      assert.equal(response.status,200,path);
      assert.match(response.headers.get('x-robots-tag'),/noindex/);
      assert.equal(response.headers.get('cache-control'),'no-store');
      assert.ok(!/findzia-(ads|analytics)\.[^" ]+\.js/.test(html));
      if(path!=='/test/discover'){
        assert.match(html,/findzia-catalog/);
        assert.match(html,/https:\/\/api\.findzia\.com\/test/);
      }
      for(const match of html.matchAll(/(?:src|href)="(\/test\/assets\/[^" ]+)"/g)){
        assert.equal((await fetch(base+match[1])).status,200,match[1]);
      }
    }
  }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});
