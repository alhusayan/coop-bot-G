const views=new Set(['home','signin','plans','subscription','usage','checkout','profile']);
export function accountReturnPath(value){
 return typeof value==='string'&&(/^\/trial\/[a-f0-9]+$/.test(value)||value==='/')?value:'/';
}
// Retain old OAuth return URLs. The original account owns the PKCE exchange.
export function prepareAccountReturn({location=window.location,history=window.history,storage=sessionStorage}={}){
 const legacy=location.pathname==='/account',auth=/findzia-login|findzia-auth-error/.test(location.hash);
 const params=new URLSearchParams(location.search),view=views.has(params.get('view'))?params.get('view'):'home';
 if(legacy){
  let path='/';try{path=accountReturnPath(storage.getItem('spaces-account-return-path'));}catch{}
  for(const key of ['view','country','lang'])params.delete(key);
  history.replaceState(history.state,'',path+(params.size?'?'+params:'')+location.hash);
 }
 return {legacy,auth,view};
}
export function rememberAccountRoom(){
 document.dispatchEvent(new CustomEvent('spaces:account-navigation'));
 try{sessionStorage.setItem('spaces-account-return-path',accountReturnPath(location.pathname));}catch{}
}
export function openAccountModal(view='home'){
 const root=document.querySelector('#findzia-home-spaces');
 root?.querySelector('[data-dark-menu]')?.close();
 root?.fzAccount?.open(views.has(view)?view:'home');
}
// Frames delegate account prompts to Spaces. OAuth starts in the top document.
export function bindAccountNavigation(root,open){
 root.addEventListener('click',event=>{
  const target=event.target.closest?.('[data-dark-settings],[data-profile-settings],[data-main-nav="account"],[data-main-nav="plans"],[data-account-nav],[data-account-provider]');
  if(!target||!root.contains(target))return;
  const view=target.dataset.accountNav||(target.dataset.mainNav==='plans'?'plans':target.hasAttribute('data-account-provider')?'signin':'home');
  if(!views.has(view))return;
  event.preventDefault();event.stopImmediatePropagation();open(view);
 },true);
 if(root.fzAccount){
  const nativeOpen=root.fzAccount.open;
  root.fzAccount.open=(view='home',...args)=>views.has(view)?open(view):nativeOpen?.(view,...args);
 }
}
