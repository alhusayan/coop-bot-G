/* Keep account links and the unified-home return available in existing projects. */
(()=>{
 'use strict';
 const accountRequested=new URLSearchParams(location.search).get('account')==='1';
 const root=document.querySelector('.fz-home');
 if(!root)return;
 const brand=root.querySelector('.fz-dark-header .fz-brand');
 if(brand&&brand.tagName!=='A'){
  const link=document.createElement('a');link.className=brand.className;link.href='/';link.setAttribute('aria-label','Findzia');link.style.textDecoration='none';
  while(brand.firstChild)link.appendChild(brand.firstChild);brand.replaceWith(link);
 }
 if(accountRequested){
  const open=()=>{if(!root.fzAccount)return false;root.fzAccount.open();const url=new URL(location.href);url.searchParams.delete('account');history.replaceState(history.state,'',url.pathname+url.search+url.hash);return true;};
  if(!open())root.addEventListener('fz:account-ready',open,{once:true});
 }
})();
