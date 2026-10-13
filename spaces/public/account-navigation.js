const views=new Set(['home','signin','plans','subscription','usage','checkout','profile']);
export function accountURL(view='home',country='KW',language='en'){
 const params=new URLSearchParams({view:views.has(view)?view:'home',country:/^[A-Z]{2}$/.test(country)?country:'KW',lang:/^[a-z]{2}$/.test(language)?language:'en'});
 return '/account?'+params;
}
export function openAccountPage(view,market,language){
 // The full original account runs at the same origin to keep its existing
 // PKCE verifier, member session and guest wallet. No credentials in URLs.
 document.dispatchEvent(new CustomEvent('spaces:account-navigation'));
 try{sessionStorage.setItem('spaces-account-return-path',location.pathname);}catch{}
 location.assign(accountURL(view,market,language));
}
export function accountReturnPath(value){
 return typeof value==='string'&&(/^\/trial\/[a-f0-9]+$/.test(value)||value==='/')?value:'/';
}
export function bindAccountNavigation(root,navigate){
 root.addEventListener('click',event=>{
  const target=event.target.closest?.('[data-dark-settings],[data-profile-settings],[data-main-nav="account"],[data-main-nav="plans"],[data-account-nav],[data-account-provider]');
  if(!target||!root.contains(target))return;
  const view=target.dataset.accountNav||(target.dataset.mainNav==='plans'?'plans':'home');
  if(!views.has(view))return;
  event.preventDefault();event.stopImmediatePropagation();navigate(view);
 },true);
 if(root.fzAccount){
  const open=root.fzAccount.open;
  root.fzAccount.open=(view='home',...args)=>views.has(view)?navigate(view):open(view,...args);
 }
}
