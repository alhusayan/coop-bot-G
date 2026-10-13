import test from 'node:test';
import assert from 'node:assert/strict';
import {MARKETS,orderedMarkets,browserMarket,detectMarket,marketLanguage} from '../public/markets.js';
import {MARKETS as serverMarkets} from '../engine.mjs';
test('geo uses the same browser-facing Findzia endpoint and rejects server defaults',async()=>{
 let request;const fetcher=async(url,options)=>{request={url,options};return Response.json({country:'kw',source:'ip'});};
 assert.equal(await detectMarket({fetcher,fallback:'US'}),'KW');assert.equal(request.url,'https://api.findzia.com/api/geo');assert.equal(request.options.cache,'no-store');
 assert.equal(await detectMarket({fetcher:async()=>Response.json({country:'US',source:'default'}),fallback:'JP'}),'JP');
 assert.equal(await detectMarket({fetcher:async()=>{throw Error('offline');},fallback:'DE'}),'DE');
 assert.equal(await detectMarket({fetcher:async()=>Response.json({country:'ZZ'}),fallback:'GB'}),'GB');
});
test('detected market first, original supported global markets after it, no duplicates',()=>{
 assert.equal(serverMarkets,MARKETS);assert.equal(Object.keys(MARKETS).length,24);
 const order=orderedMarkets(MARKETS,'KW').map(([code])=>code);assert.deepEqual(order.slice(0,4),['KW','US','CN','JP']);assert.equal(new Set(order).size,24);
 assert.equal(browserMarket({timeZone:'Asia/Kuwait',languages:['en-US']}),'KW');assert.equal(browserMarket({languages:['de-DE']}),'DE');
});
test('native market language with a separate explicit override for each country',()=>{
 const saved=new Map([['spaces-language-choice-KW-v1','en']]);const read=key=>saved.get(key);
 assert.equal(marketLanguage('KW'),'ar');assert.equal(marketLanguage('KW',read),'en');assert.equal(marketLanguage('JP',read),'ja');assert.equal(marketLanguage('NL',read),'nl');assert.equal(marketLanguage('FR',read),'fr');
});
