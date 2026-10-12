import test from 'node:test';
import assert from 'node:assert/strict';
import {gemini} from '../engine.mjs';
const env={GEMINI_API_KEY:'local-test-only',SPACES_TEXT_MODEL:'gemini-3.8-flash'};
test('inventory recovers once from a provider schema rejection and then validates the JSON',async t=>{
 const configs=[];
 t.mock.method(globalThis,'fetch',async(_url,options)=>{configs.push(JSON.parse(options.body).generationConfig);return configs.length===1?Response.json({error:{message:'unsupported schema'}},{status:400}):Response.json({candidates:[{content:{parts:[{text:'{"items":[]}'}]}}]});});
 assert.deepEqual(await gemini([{text:'inventory'}],{env,json:true,schema:{type:'object',properties:{items:{type:'array',items:{type:'string'}}}}}),{items:[]});
 assert.ok(configs[0].responseSchema);assert.equal(configs[1].responseSchema,undefined);assert.equal(configs.length,2);
});
test('truncated JSON gets one bounded retry with more output capacity',async t=>{
 const configs=[];
 t.mock.method(globalThis,'fetch',async(_url,options)=>{configs.push(JSON.parse(options.body).generationConfig);return Response.json({candidates:[{finishReason:configs.length===1?'MAX_TOKENS':'STOP',content:{parts:[{text:configs.length===1?'{"items":[':'{"items":[]}'}]}}]});});
 assert.deepEqual(await gemini([{text:'inventory'}],{env,json:true}),{items:[]});assert.equal(configs.length,2);assert.ok(configs[1].maxOutputTokens>configs[0].maxOutputTokens);
});
