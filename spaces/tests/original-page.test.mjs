import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {frameDocument,savedOriginalView} from '../original-page.mjs';
test('the live original page keeps every inline search and render script unchanged',()=>{
 const file=new URL('../verification/live-findzia.html',import.meta.url);
 let original;try{original=readFileSync(file,'utf8');}catch{original='<html><script>e.fzRefineBridge.searchPhoto=fzAcceptPhoto;</script><script src="/assets/home.js"></script></html>';}
 const framed=frameDocument(original),scripts=html=>[...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)].map(x=>x[1]);
 assert.deepEqual(scripts(framed),scripts(original));assert.match(framed,/https:\/\/findzia.com\/assets\//);
 assert.throws(()=>frameDocument('<html>Error page</html>'));
});
test('saved views keep original rows, prices, groups and order; omit photo bytes and credentials',()=>{
 const rows=[{url:'https://a.test/p',result_group:'alternative',price:'95.000 KWD',evaluation_token:'opaque-a'},{url:'https://b.test/p',result_group:'global',price:'≈ 307.861 KWD'}];
 const view=savedOriginalView({items:rows,lastSearch:{country:'KW',kind:'image',image_base64:'privatephoto'},authorization:'secret',sort:'relevance',filter:'all'},'KW');
 assert.deepEqual(view.items,rows);assert.equal(view.lastSearch.image_base64,undefined);assert.equal(view.authorization,undefined);
 assert.throws(()=>savedOriginalView({items:rows,lastSearch:{country:'SA'}},'KW'));
});
