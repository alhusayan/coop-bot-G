import test from 'node:test';
import assert from 'node:assert/strict';
import {parseHTML} from 'linkedom';
import {accountDocument,frameDocument} from '../original-page.mjs';
import {accountURL,accountReturnPath,bindAccountNavigation} from '../public/account-navigation.js';
test('account presentation keeps original auth code, and room return cannot redirect elsewhere',()=>{
 const source='<html><head><script>e.fzRefineBridge.searchPhoto=fzAcceptPhoto;</script></head><body></body></html>';
 const page=accountDocument(frameDocument(source));
 assert.match(page,/data-findzia-spaces-account/);assert.doesNotMatch(page,/data-findzia-spaces-results|original-results-frame.css/);
 assert.match(page,/<script>e.fzRefineBridge.searchPhoto=fzAcceptPhoto;<\/script>/);
 assert.equal(accountURL('plans','SA','ar'),'/account?view=plans&country=SA&lang=ar');
 for(const invalid of ['https://evil.test/','//evil.test/','/account','/trial/abc?secret=123','javascript:alert(1)'])assert.equal(accountReturnPath(invalid),'/');
 assert.equal(accountReturnPath('/trial/abc123'),'/trial/abc123');
});
test('account and credit prompts navigate out of the result frame; settings stay available',()=>{
 const {document,window}=parseHTML('<div id="root"><button data-dark-settings>Account</button><button data-main-nav="plans">Plans</button></div>');
 const root=document.querySelector('#root'),navigations=[],local=[];root.fzAccount={open:view=>local.push(view)};
 bindAccountNavigation(root,view=>navigations.push(view));
 root.querySelector('[data-dark-settings]').dispatchEvent(new window.Event('click',{bubbles:true}));
 root.querySelector('[data-main-nav="plans"]').dispatchEvent(new window.Event('click',{bubbles:true}));
 root.fzAccount.open('signin');root.fzAccount.open('checkout');root.fzAccount.open('settings');
 assert.deepEqual(navigations,['home','plans','signin','checkout']);assert.deepEqual(local,['settings']);
});
