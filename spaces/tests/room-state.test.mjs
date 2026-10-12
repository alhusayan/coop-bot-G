import test from 'node:test';
import assert from 'node:assert/strict';
import {createRoomContext,acceptsJob} from '../public/room-state.js';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';

test('a late old-room poll or design choice cannot replace a new photo or room',async()=>{
 const context=createRoomContext();const old=context.begin();
 let release;const delayed=new Promise(resolve=>release=resolve);
 let displayed='new room';const oldPoll=delayed.then(()=>{if(context.current(old))displayed='old room';});
 const next=context.begin();release();await oldPoll;
 assert.equal(displayed,'new room');assert.equal(context.current(next),true);
 assert.equal(acceptsJob({id:'new',revision:20},{id:'old',revision:25}),false);
 assert.equal(acceptsJob({id:'new',revision:20},{id:'new',revision:19}),false);
 assert.equal(acceptsJob({id:'new',revision:20},{id:'new',revision:21}),true);
});

test('an older response after opening a piece does not permanently stop polling',async()=>{
 const source=readFileSync(new URL('../public/app.js',import.meta.url),'utf8');
 const fn=source.split('\n').find(line=>line.startsWith('function poll()'));
 let callback,count=0;const context=createRoomContext();context.begin();
 const runtime={pollTimer:null,roomContext:context,state:{job:{id:'room'},view:'shopping'},clearTimeout(){},setTimeout(fn){callback=fn;count++;return count;},api:async()=>({id:'room',revision:1}),applyJob:()=>false,active:()=>true};
 runInNewContext(fn+';poll();',runtime);assert.equal(count,1);
 await callback();assert.equal(count,2,'same-room stale response must schedule another poll');
 context.begin();await callback();assert.equal(count,2,'navigating away must stop the old loop');
});

