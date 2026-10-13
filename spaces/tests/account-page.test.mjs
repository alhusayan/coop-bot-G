import test from 'node:test';
import assert from 'node:assert/strict';
import {parseHTML} from 'linkedom';
import {accountReturnPath,prepareAccountReturn,bindAccountNavigation,openAccountModal} from '../public/account-navigation.js';
test('old account callbacks restore Spaces without losing the one-time auth fragment',()=>{
 const calls=[],fragment='#findzia-login=test-only-code&flow=test-only-flow';
 const result=prepareAccountReturn({location:{pathname:'/account',search:'?view=plans&country=KW&lang=ar&payment=returned',hash:fragment},history:{state:null,replaceState:(...args)=>calls.push(args)},storage:{getItem:()=>'/trial/abc123'}});
 assert.deepEqual(result,{legacy:true,auth:true,view:'plans'});
 assert.equal(calls[0][2],'/trial/abc123?payment=returned'+fragment);
 for(const invalid of ['https://evil.test/','//evil.test/','/account','/trial/abc?secret=123','javascript:alert(1)'])assert.equal(accountReturnPath(invalid),'/');
 const ordinary=prepareAccountReturn({location:{pathname:'/trial/abc123',search:'',hash:fragment},history:{replaceState:()=>assert.fail('native account must consume its own fragment')},storage:{getItem:()=>null}});
 assert.equal(ordinary.auth,true);assert.equal(ordinary.legacy,false);
});
test('a results account prompt closes its layer and opens the parent native account without navigation',()=>{
 const {document,window}=parseHTML('<div id="frame"><button data-dark-settings>Account</button><button data-main-nav="plans">Plans</button><button data-account-provider="apple">Apple</button></div><div id="findzia-home-spaces"><dialog data-dark-menu></dialog></div>');
 const before=globalThis.document;globalThis.document=document;
 try{
  const root=document.querySelector('#frame'),parent=document.querySelector('#findzia-home-spaces'),opens=[],local=[];
  parent.querySelector('dialog').close=()=>{};parent.fzAccount={open:view=>opens.push(view)};
  root.fzAccount={open:view=>local.push(view)};
  bindAccountNavigation(root,openAccountModal);
  for(const button of root.querySelectorAll('button'))button.dispatchEvent(new window.Event('click',{bubbles:true}));
  root.fzAccount.open('signin');root.fzAccount.open('checkout');root.fzAccount.open('settings');
  assert.deepEqual(opens,['home','plans','signin','signin','checkout']);assert.deepEqual(local,['settings']);
 }finally{globalThis.document=before;}
});
