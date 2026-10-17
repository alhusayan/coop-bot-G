/* Same-origin project shell. Authentication stays in the existing account module. */
(()=>{
'use strict';
const params=new URLSearchParams(location.search),project=params.get('hubProject');
const projectKeys=['shop','one','space','services','account'];
// Shared links enter the same shell too. Unknown callback/payment parameters
// retain their original handler and are never rewritten.
const entries={'/search':'shop','/trial/original':'shop','/pages/findzia':'shop','/jp':'shop','/trial/one-55321448a0352f1ff18b':'one','/trial/services':'services','/space':'space'};
const entry=entries[location.pathname.replace(/\/$/,'')];
if(parent===window&&entry&&[...params.keys()].every(key=>['q','country','gclid','fbclid'].includes(key)||key.startsWith('utm_'))){const url=new URL('/',location.origin);url.search=location.search;url.hash=location.hash;url.searchParams.set('project',entry);location.replace(url.href);return}

let embedded=false;try{embedded=params.get('hub')==='1'&&projectKeys.includes(project)&&parent!==window&&parent.location.origin===location.origin&&parent.FindziaHub===true}catch{}
const post=data=>{if(embedded)parent.postMessage({findziaHub:true,...data},location.origin)};
if(embedded){
 document.documentElement.dataset.findziaEmbedded='true';
 document.documentElement.dataset.hubProject=project;
 if(project==='account')document.documentElement.dataset.hubAccountOnly='true';
 window.FindziaHubBridge={
  composer(mode='query'){
   // Same-origin direct focus retains iOS keyboard activation from the tap.
   const selector=mode==='photo'?'#header-camera':'#header-query';
   try{const control=parent.document.querySelector(selector);if(control&&!control.disabled){mode==='photo'?control.click():control.focus();return true}}catch{}
   post({type:'composer',mode:mode==='photo'?'photo':'query'});return false;
  },
  action,connectSpace(adapter){space=adapter;publishState()},
  authReturnURL(){const url=new URL(parent.location.href);url.hash='';url.searchParams.set('project',project);return url.href},
  navigateAuth(value){const url=new URL(value);if(url.protocol!=='https:'||!['https://accounts.google.com','https://appleid.apple.com'].includes(url.origin))throw Error('invalid_redirect');parent.location.assign(url.href)}
 };
}
const read=key=>{try{return localStorage.getItem(key)}catch{return null}};
let space=null,lastState='',countryApplying=false;
let root=null,pendingAccount=params.get('account')==='1',applying=false;
const $=selector=>document.querySelector(selector);
const querySelector=()=>project==='services'?'#svc-query':project==='space'?'#design-request':'textarea[id^="fz-query-"]';
function state(){
 const context=root?.fzRefineBridge?.context?.()||{},input=$(querySelector()),select=root?.querySelector('[data-profile-market-select]');
 return {landing:['shop','one'].includes(project)&&root?.dataset.homeState==='empty',scene:project==='space'&&Object.hasOwn(document.documentElement.dataset,'spaceScene'),query:input?.value||'',country:select?.value||context.country||'',countries:select?[...select.options].map(o=>o.value).filter(c=>/^[A-Z]{2}$/.test(c)):[],busy:project==='space'?!!space?.state().busy:project==='services'?!!$('#svc-submit')?.disabled:!!context.busy,cameraReady:project==='space'?!!space?.state().ready:!!root?.fzRefineBridge};
}
function publishState(){if(!embedded||!root)return;const data=state(),serialized=JSON.stringify(data);if(serialized===lastState)return;lastState=serialized;post({type:'header-state',...data})}
function applyCountry(country){const select=root?.querySelector('[data-profile-market-select]');if(countryApplying||!select||!/^[A-Z]{2}$/.test(country||'')||select.value===country||![...select.options].some(o=>o.value===country))return;countryApplying=true;try{select.value=country;select.dispatchEvent(new Event('change',{bubbles:true}));applyLanguage(read('findzia-lang'))}finally{countryApplying=false}publishState()}
function click(selector){const button=$(selector);if(!button||button.disabled)return false;button.click();return true}
function setQuery(value){const input=$(querySelector());if(!input)return false;value=String(value||'').slice(0,project==='space'?600:project==='services'?200:600);if(input.value!==value){input.value=value;input.dispatchEvent(new Event('input',{bubbles:true}))}return true}
function action(name,data={}){
 if(!embedded||!root)return false;
 if(name==='state')return state();
 if(name==='country'){applyCountry(data.country);return true}
 if(name==='prepare'){if(project==='services')root.fzRefineBridge?.newSearch?.();return action('query',data);}
 if(name==='query'){const changed=setQuery(data.query);publishState();return changed;}
 if(name==='services'&&project==='space'){if(space?.state().busy)return false;const q=String(typeof data.query==='string'?data.query:space?.serviceQuery?.()||'').trim().slice(0,180);if(q.length<2)return false;post({type:'navigate',project:'services',q,country:/^[A-Z]{2}$/.test(data.country||'')?data.country:read('findzia-market-country-v1')||''});return true;}
 if(name==='menu')return click('[data-dark-menu-open]');
 if(name==='market')return click('[data-dark-market-open]');
 if(name==='account'){pendingAccount=true;openAccount();return true}
 if(name==='search'){
  if(!setQuery(data.query)||state().busy)return false;
  if(project==='space'){if(!space?.state().hasImage)return 'needs-photo';space.review();publishState();return true}
  if(project==='services'){if(String(data.query||'').trim().length<2&&$('#svc-query')?.required)return 'needs-query';$('#svc-form').hidden=false;$('#svc-form').requestSubmit();return true}
  if(!String(data.query||'').trim())return true;
  return click('[data-search-btn]');
 }
 if(name==='camera'||name==='photos'){
  if(state().busy)return false;
  // All native clicks stay on the originating tap's synchronous stack.
  if(project==='space'){if(!space?.state().ready)return false;return click(name==='camera'?'[data-action="camera"]':'[data-action="upload"]')}
  if(project==='services')return click(name==='camera'?'#svc-camera':'#svc-gallery');
  return click('[data-photo-btn]');
 }
 return false;
}
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
applyLanguage(read('findzia-lang'));applyCountry(read('findzia-market-country-v1'));appearance();openAccount();publishState();if(root.fzAccount)post({type:'ready'})}
function mount(){
 root=document.querySelector('.fz-home');if(!root)return;
 if(!embedded){const brand=root.querySelector('header div.fz-brand');if(brand){const link=document.createElement('a');link.className=brand.className;link.href='/';link.setAttribute('aria-label','Findzia');while(brand.firstChild)link.append(brand.firstChild);brand.replaceWith(link)}}
 root.addEventListener('fz:account-ready',()=>{mounted();const account=root.querySelector('.fz-account');if(project==='account')account?.addEventListener('close',()=>post({type:'close'}));});
 document.addEventListener('change',event=>{
  if(applying)return;
  if(event.target.matches('[data-profile-language-select],#spaces-language,[data-account-preference="language"]')){const language=read('findzia-lang')||event.target.value;applyLanguage(language);post({type:'language',language})}
  if(event.target.matches('[data-solar-mode],[data-account-preference="appearance"]'))post({type:'appearance'});
  if(!countryApplying&&event.target.matches('[data-profile-market-select],#svc-country')){const country=event.target.value;try{localStorage.setItem('findzia-market-country-v1',country);localStorage.setItem('findzia-services-country-v1',country)}catch{}post({type:'market',country})}
  publishState();
 });
 document.addEventListener('click',event=>{if(!embedded)return;const link=event.target.closest('a[href]');if(!link)return;const url=new URL(link.href,location.href);if(url.origin===location.origin&&['/','/home','/home/'].includes(url.pathname)&&!url.search){event.preventDefault();post({type:'close'})}});
 if(embedded){
  const textEntry=node=>!!node?.matches?.('textarea,input:not([type=file]):not([type=checkbox]):not([type=radio]):not([type=hidden]):not([type=button]):not([type=submit])');
  document.addEventListener('focusin',event=>{if(textEntry(event.target))post({type:'text-entry',active:true})});
  document.addEventListener('focusout',()=>queueMicrotask(()=>post({type:'text-entry',active:textEntry(document.activeElement)})));
  document.addEventListener('input',event=>{if(event.target.matches(querySelector()))publishState()});
  document.addEventListener('click',event=>{const choice=event.target.closest?.('[data-action="set-market"]');if(choice&&/^[A-Z]{2}$/.test(choice.dataset.id||'')){try{localStorage.setItem('findzia-market-country-v1',choice.dataset.id);localStorage.setItem('findzia-services-country-v1',choice.dataset.id)}catch{}post({type:'market',country:choice.dataset.id})}queueMicrotask(publishState)},true);
  document.addEventListener('findzia:header-state',publishState);
  document.addEventListener('findzia:market-change',event=>{const country=event.detail?.country;if(!/^[A-Z]{2}$/.test(country||''))return;publishState();if(!countryApplying)post({type:'market',country});});
  root.addEventListener('fz:search-state',publishState);
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!document.querySelector('dialog[open]'))post({type:'close'})});
  if(window.MutationObserver){
   const observer=new MutationObserver(publishState);observer.observe(root,{attributes:true,attributeFilter:['data-home-state','data-lang']});
   for(const target of document.querySelectorAll('#svc-submit,[data-action="camera"],#generate-button'))observer.observe(target,{attributes:true,attributeFilter:['disabled','aria-busy']});
   const market=root.querySelector('[data-profile-market-select]');if(market)new MutationObserver(()=>{applyCountry(read('findzia-market-country-v1'));publishState()}).observe(market,{childList:true});
  }
 }
 mounted();
 // Modules may finish mounting after DOMContentLoaded, notably Space's shell.
 window.addEventListener('load',mounted,{once:true});
}
window.addEventListener('message',event=>{
 if(!embedded||event.origin!==location.origin||event.source!==parent||event.data?.findziaHub!==true)return;
 if(event.data.type==='preferences'){applyLanguage(read('findzia-lang')||event.data.language);applyCountry(event.data.country||read('findzia-market-country-v1'));appearance();publishState()}
 if(event.data.type==='account'){pendingAccount=true;openAccount()}
});
window.addEventListener('storage',event=>{if(event.key==='findzia-lang')applyLanguage(read('findzia-lang'));if(event.key==='findzia-appearance-v1')appearance();if(event.key==='findzia-market-country-v1')applyCountry(read('findzia-market-country-v1'));if(event.key==='findzia-account-v1-session')post({type:'account-state'})});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})();
