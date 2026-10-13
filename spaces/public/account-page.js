import {accountReturnPath} from './account-navigation.js';
const params=new URLSearchParams(location.search);
const view=['home','signin','plans','subscription','usage','checkout','profile'].includes(params.get('view'))?params.get('view'):'home';
const hadAuthReturn=/findzia-login|findzia-auth-error/.test(location.hash);
function returnToRoom(){let path='/';try{path=accountReturnPath(sessionStorage.getItem('spaces-account-return-path'));}catch{}location.assign(path);}
async function start(){
 let root;
 const started=Date.now();
 while(Date.now()-started<16000){root=document.querySelector('.fz-home');if(root?.fzAccount&&root.fzBilling)break;await new Promise(resolve=>setTimeout(resolve,50));}
 if(!root?.fzAccount||!root.fzBilling){
  const message=document.createElement('p');message.className='spaces-account-error';message.textContent='Could not load your account. / تعذّر فتح الحساب.';
  const back=document.createElement('button');back.textContent='Back to your room / الرجوع للتصميم';back.addEventListener('click',returnToRoom);message.append(back);document.body.append(message);return;
 }
 root.fzStoreScene?.destroy();root.fzSearchWait?.destroy();
 for(const [selector,value] of [['[data-profile-market-select]',params.get('country')],['[data-profile-language-select]',params.get('lang')]]){
  const select=root.querySelector(selector);if(select&&[...select.options].some(x=>x.value===value)){select.value=value;select.dispatchEvent(new Event('change',{bubbles:true}));}
 }
 const dialog=root.querySelector('.fz-account');
 // The original account/payment controllers own every account operation.
 // Only their page presentation changes; OAuth runs in the top document.
 root.addEventListener('click',event=>{
  if(event.target.closest('[data-account-close]')){event.preventDefault();event.stopImmediatePropagation();returnToRoom();}
 },true);
 dialog.addEventListener('cancel',event=>{event.preventDefault();returnToRoom();});
 const label=()=>{
  const close=dialog.querySelector('[data-account-close]');if(!close)return;
  close.setAttribute('aria-label',root.dataset.lang==='ar'?'الرجوع للتصميم':'Back to your room');
  close.title=close.getAttribute('aria-label');
  close.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M19 12H5m6-6-6 6 6 6"/></svg>';
 };
 // OAuth already opens its own status view. Never overwrite an auth error or
 // an automatically resumed payment with an unrelated account screen.
 if(!hadAuthReturn&&!dialog.open)root.fzAccount.open(view);
 label();new MutationObserver(label).observe(dialog,{attributes:true,attributeFilter:['data-view','dir']});
}
start();
