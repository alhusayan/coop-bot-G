import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {serviceLocation} from '../source/findzia-services-state.js';
const source=readFileSync(new URL('../source/findzia-services.js',import.meta.url),'utf8');
const code=source.slice(source.indexOf('let networkLocationTask='),source.indexOf('async function locateArea('));
function fixture({area='',response,fetcher}={}){
 const nodes=new Map();const $=key=>{if(!nodes.has(key))nodes.set(key,{value:key==='#svc-area'?area:'',textContent:''});return nodes.get(key)};
 const context={$,country:'SA',language:'en',locationSequence:0,URL,AbortSignal,serviceLocation,updateLocation(){},setCountry(value){context.country=value},fetch:fetcher||(async url=>{assert.equal(url.searchParams.has('latitude'),false);return {ok:true,json:async()=>response||{countryCode:'KW',city:'Kuwait City'}}})};
 vm.createContext(context);vm.runInContext(code,context);return {context,$,run:()=>vm.runInContext('locateFromNetwork()',context)};
}
test('network location fills an empty area without requesting GPS',async()=>{const f=fixture();assert.equal(await f.run(),true);assert.equal(f.context.country,'KW');assert.equal(f.$('#svc-area').value,'Kuwait City');assert.match(f.$('#svc-manual').textContent,/≈/)});
test('saved and manually entered areas outrank delayed network results',async()=>{
 const saved=fixture({area:'Salmiya',fetcher:()=>{throw Error('must not fetch')}});assert.equal(await saved.run(),true);assert.equal(saved.$('#svc-area').value,'Salmiya');
 let resolve;const f=fixture({fetcher:()=>new Promise(r=>resolve=r)}),pending=f.run();f.$('#svc-area').value='Hawally';resolve({ok:true,json:async()=>({countryCode:'KW',city:'Kuwait City'})});assert.equal(await pending,false);assert.equal(f.$('#svc-area').value,'Hawally');
});
test('failure or unsupported location keeps manual input available',async()=>{const f=fixture({fetcher:async()=>{throw Error('offline')}});assert.equal(await f.run(),false);assert.equal(f.$('#svc-area').value,'')});
