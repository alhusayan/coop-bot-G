/* Same-origin project shell. Authentication stays in the existing account module. */
(()=>{
'use strict';
const params=new URLSearchParams(location.search),project=params.get('hubProject');
const projectKeys=['shop','one','space','services','account'];
let embedded=false;try{embedded=params.get('hub')==='1'&&projectKeys.includes(project)&&parent!==window&&parent.location.origin===location.origin&&parent.FindziaHub===true}catch{}
const post=data=>{if(embedded)parent.postMessage({findziaHub:true,...data},location.origin)};
if(embedded){
 document.documentElement.dataset.findziaEmbedded='true';
 if(project==='account')document.documentElement.dataset.hubAccountOnly='true';
 window.FindziaHubBridge={
  authReturnURL(){const url=new URL(parent.location.href);url.hash='';url.searchParams.set('project',project);return url.href},
  navigateAuth(value){const url=new URL(value);if(url.protocol!=='https:'||!['https://accounts.google.com','https://appleid.apple.com'].includes(url.origin))throw Error('invalid_redirect');parent.location.assign(url.href)}
 };
}
const read=key=>{try{return localStorage.getItem(key)}catch{return null}};
let root=null,pendingAccount=params.get('account')==='1',applying=false;
function applyLanguage(language){
 if(!root||!language||applying)return;applying=true;
 try{
  window.FindziaLocale?.choose(language);
  const select=root.querySelector('[data-profile-language-select]');
  if(select&&[...select.options].some(option=>option.value===language)&&select.value!==language){select.value=language;select.dispatchEvent(new Event('change',{bubbles:true}))}
  if(window.FindziaI18n&&root.dataset.lang!==language)window.FindziaI18n.set(root,language);
  document.documentElement.lang=language;document.documentElement.dir=['ar','ur'].includes(language)?'rtl':'ltr';
 }finally{applying=false}
}
function appearance(){window.FindziaAppearance?.apply(root);const select=root?.querySelector('[data-solar-mode]'),mode=read('findzia-appearance-v1')||'auto';if(select&&select.value!==mode){select.value=mode;select.dispatchEvent(new Event('change',{bubbles:true}))}}
function openAccount(){if(pendingAccount&&root?.fzAccount){pendingAccount=false;root.fzAccount.open();if(params.has('account')){const url=new URL(location.href);url.searchParams.delete('account');history.replaceState(history.state,'',url.pathname+url.search+url.hash)}}}
function mounted(){if(!root)return;
 if(embedded&&root.fzRefineBridge){if(project!=='space')root.fzRefineBridge.openDesigns=()=>post({type:'navigate',project:'space'});if(['space','services'].includes(project))root.fzRefineBridge.accountSearch=(q,country)=>post({type:'navigate',project:'shop',q,country});}
applyLanguage(read('findzia-lang'));appearance();openAccount();if(root.fzAccount)post({type:'ready'})}
function mount(){
 root=document.querySelector('.fz-home');if(!root)return;
 if(!embedded){const brand=root.querySelector('header div.fz-brand');if(brand){const link=document.createElement('a');link.className=brand.className;link.href='/';link.setAttribute('aria-label','Findzia');while(brand.firstChild)link.append(brand.firstChild);brand.replaceWith(link)}}
 root.addEventListener('fz:account-ready',()=>{mounted();const account=root.querySelector('.fz-account');if(project==='account')account?.addEventListener('close',()=>post({type:'close'}));});
 document.addEventListener('change',event=>{
  if(applying)return;
  if(event.target.matches('[data-profile-language-select],#spaces-language,[data-account-preference="language"]')){const language=read('findzia-lang')||event.target.value;applyLanguage(language);post({type:'language',language})}
  if(event.target.matches('[data-solar-mode],[data-account-preference="appearance"]'))post({type:'appearance'});
 });
 document.addEventListener('click',event=>{if(!embedded)return;const link=event.target.closest('a[href]');if(!link)return;const url=new URL(link.href,location.href);if(url.origin===location.origin&&['/','/home','/home/'].includes(url.pathname)&&!url.search){event.preventDefault();post({type:'close'})}});
 mounted();
 // Modules may finish mounting after DOMContentLoaded, notably Space's shell.
 window.addEventListener('load',mounted,{once:true});
}
window.addEventListener('message',event=>{
 if(!embedded||event.origin!==location.origin||event.source!==parent||event.data?.findziaHub!==true)return;
 if(event.data.type==='preferences'){applyLanguage(read('findzia-lang')||event.data.language);appearance()}
 if(event.data.type==='account'){pendingAccount=true;openAccount()}
});
window.addEventListener('storage',event=>{if(event.key==='findzia-lang')applyLanguage(read('findzia-lang'));if(event.key==='findzia-appearance-v1')appearance();if(event.key==='findzia-account-v1-session')post({type:'account-state'})});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})();
