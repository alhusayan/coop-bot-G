import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../public/app.js',import.meta.url),'utf8');
test('specialist click opens the design sheet with one explicit search intent',()=>{
 const code=source.slice(source.indexOf('function openServiceRequest('),source.indexOf('function findSpecialist('));let sheet;
 const context={URL,crypto:{randomUUID:()=> '12345678-1234-1234-1234-123456789abc'},location:{origin:'https://findzia.com',assign(){throw Error('must stay inside design')}},countryCode:()=> 'KW',translate:x=>x,esc:x=>String(x).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;'),showSheet:(html,mode)=>sheet={html,mode}};
 vm.createContext(context);vm.runInContext(code+';openServiceRequest("Carpenter for wall panels")',context);
 assert.equal(sheet.mode,'services');assert.match(sheet.html,/iframe/);assert.match(sheet.html,/designContext=1/);assert.match(sheet.html,/country=KW/);assert.doesNotMatch(sheet.html,/project=services/);
 assert.match(sheet.html,/searchIntent=12345678-1234-1234-1234-123456789abc/);
});
