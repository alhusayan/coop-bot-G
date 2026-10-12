import test from 'node:test';
import assert from 'node:assert/strict';
import {createRoomContext,acceptsJob} from '../public/room-state.js';

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
