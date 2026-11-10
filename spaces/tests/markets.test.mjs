import test from 'node:test';
import assert from 'node:assert/strict';
import {MARKETS,orderedMarkets,browserMarket,detectMarket,marketLanguage,supportedMarket,savedMarket} from '../public/markets.js';
import {MARKETS as serverMarkets} from '../engine.mjs';
test('geo uses the same browser-facing Findzia endpoint and rejects server defaults',async()=>{
 let request;const fetcher=async(url,options)=>{request={url,options};return Response.json({country:'kw',source:'ip'});};
 assert.equal(await detectMarket({fetcher,fallback:'US'}),'KW');assert.equal(request.url,'https://api.findzia.com/api/geo');assert.equal(request.options.cache,'no-store');
 assert.equal(await detectMarket({fetcher:async()=>Response.json({country:'US',source:'default'}),fallback:'JP'}),'JP');
 assert.equal(await detectMarket({fetcher:async()=>{throw Error('offline');},fallback:'DE'}),'DE');
 assert.equal(await detectMarket({fetcher:async()=>Response.json({country:'ZZ'}),fallback:'GB'}),'GB');
});
test('Design uses the original shopping countries and order, including all Gulf countries',()=>{
 const expected=['KW','SA','AE','QA','BH','OM','US','CN','GB','DE','FR','IT','ES','NL','CA','AU','JP','KR','IN','TR','SG','EG','BR','MX'];
 assert.equal(serverMarkets,MARKETS);assert.deepEqual(Object.keys(MARKETS),expected);
 assert.deepEqual(orderedMarkets(MARKETS,'SA').map(([code])=>code),expected);
 assert.equal(browserMarket({timeZone:'Asia/Kuwait',languages:['en-US']}),'KW');assert.equal(browserMarket({languages:['de-DE']}),'DE');
});
test('Gulf location detection keeps each country and its currency instead of substituting a neighbour',async()=>{
 for(const [code,city,currency] of [['KW','Kuwait','KWD'],['SA','Riyadh','SAR'],['AE','Dubai','AED'],['QA','Qatar','QAR'],['BH','Bahrain','BHD'],['OM','Muscat','OMR']]){
  assert.equal(supportedMarket(code),code);assert.equal(MARKETS[code].currency,currency);
  assert.equal(browserMarket({timeZone:'Asia/'+city}),code);
  assert.equal(await detectMarket({fetcher:async()=>Response.json({country:code.toLowerCase(),source:'ip'})}),code);
 }
});
test('Design restores the site country before background location detection',()=>{
 const stored=new Map([['findzia-market-country-v1','KW'],['spaces-market','SA']]);
 assert.equal(savedMarket(key=>stored.get(key)),'KW');
 assert.equal(savedMarket(()=>null),'');assert.equal(savedMarket(()=>'ZZ'),'');assert.equal(savedMarket(()=>{throw Error('blocked storage');}),'');
});
test('native market language with a separate explicit override for each country',()=>{
 const saved=new Map([['spaces-language-choice-SA-v1','en']]);const read=key=>saved.get(key);
 assert.equal(marketLanguage('SA'),'ar');assert.equal(marketLanguage('SA',read),'en');assert.equal(marketLanguage('JP',read),'ja');assert.equal(marketLanguage('NL',read),'nl');assert.equal(marketLanguage('FR',read),'fr');
});
