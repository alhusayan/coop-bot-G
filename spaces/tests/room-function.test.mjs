import test from 'node:test';
import assert from 'node:assert/strict';
import {detectRoom,roomBrief,verifyRoomFunction} from '../room-function.mjs';
test('room evidence and office functions survive classification into the design brief',async()=>{
 const context=await detectRoom({inlineData:{}},{judge:async()=>({is_room:true,type:'office',room_en:'Office',confidence:.97,evidence:['Desk and computer','Guest armchairs'],required_functions:['Computer work','Guest seating'],zones:['Desk at rear'],fixed_features:'Window on left'})});
 assert.equal(context.type,'office');assert.match(roomBrief(context),/usable work desk/);assert.match(roomBrief(context),/Desk at rear/);assert.match(roomBrief(context),/Guest seating/);
});
test('unknown room categories preserve visible function and non-room photos cannot generate designs',async()=>{
 const unknown=await detectRoom({}, {judge:async()=>({is_room:true,type:'invented',room_en:'Empty interior'})});assert.equal(unknown.type,'other');
 await assert.rejects(detectRoom({}, {judge:async()=>({is_room:false})}),/NOT_A_ROOM/);
});
test('losing an essential function fails verification even when the general room category agrees',async()=>{
 const context={type:'office'},before={inlineData:{data:'before'}},after={inlineData:{data:'after'}};
 const noDesk=await verifyRoomFunction(before,after,context,{judge:async parts=>{assert.equal(parts[1],before);assert.equal(parts[2],after);return {same_function:true,essential_functions_preserved:false,reason:'No workstation'};}});assert.equal(noDesk.ok,false);
 assert.equal((await verifyRoomFunction(before,after,context,{judge:async()=>({same_function:true,essential_functions_preserved:true})})).ok,true);
});

test('an office waiting area preserves reception seating without inventing a work desk',async()=>{const context=await detectRoom({}, {judge:async()=>({is_room:true,type:'office',room_en:'office reception / waiting area',confidence:.9})});assert.equal(context.type,'reception');assert.match(roomBrief(context),/Do not invent a workstation/);});
