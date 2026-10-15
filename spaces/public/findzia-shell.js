import {marketLanguage} from './markets.js';
import {prepareAccountReturn,rememberAccountRoom} from './account-navigation.js';
// Connect the original Findzia account, billing and menu to the Spaces screens.
// The account API remains the single authority for identity, credits and payment.
const languages={en:'English',nl:'Nederlands',ar:'العربية',de:'Deutsch',fr:'Français',it:'Italiano',es:'Español',pt:'Português',tr:'Türkçe',ru:'Русский',ja:'日本語',zh:'中文',ko:'한국어',hi:'हिन्दी',ur:'اردو',id:'Bahasa Indonesia',ms:'Bahasa Melayu'};
const read=(key,fallback)=>{try{return localStorage.getItem(key)||fallback;}catch{return fallback;}};
export function syncLanguageControls(root,code){
 const controls=[root.querySelector('[data-profile-language-select]'),root.ownerDocument.querySelector('#spaces-language')];
 for(const control of controls){
  if(!control)continue;
  // Preserve the current choice if a translated label causes the sheet to repaint.
  for(const option of control.options)option.toggleAttribute('selected',option.value===code);
  const selected=[...control.options].find(option=>option.value===code);
  if(selected)selected.selected=true;
 }
}
export async function mountFindzia({getMarket,getMarkets,setMarket,openMarket,openDesigns,home,notice}){
 const root=document.querySelector('#findzia-home-spaces'),menu=root.querySelector('[data-dark-menu]');
 const market=root.querySelector('[data-profile-market-select]'),language=root.querySelector('[data-profile-language-select]'),appearance=root.querySelector('[data-solar-mode]');
 root.fzRefineBridge={api:'https://api.findzia.com',context:()=>({country:getMarket(),query:'',generation:0,busy:false,media_pending:false}),
  newSearch:home,openDesigns,accountNotice:notice,
  accountSaved:()=>{try{return JSON.parse(localStorage.getItem('findzia-saved-v1')||'[]');}catch{return [];}},
  accountRemoveSaved:url=>{const saved=root.fzRefineBridge.accountSaved().filter(x=>x.url!==url);localStorage.setItem('findzia-saved-v1',JSON.stringify(saved));},
  accountSearch:(query,country)=>{const url=new URL('https://findzia.com/trial/original');url.searchParams.set('q',query);url.searchParams.set('country',country||getMarket());location.assign(url.href);},
  snapshot:()=>({view:{items:[]},recommendation:null}),restore:()=>{root.dataset.homeState='empty';},restoreHomeView:home
 };
 function sync(){
  const markets=getMarkets();market.replaceChildren(...Object.entries(markets).map(([code,m])=>new Option(m.flag+' '+m.en,code)));market.value=getMarket();
  const selected=markets[getMarket()];root.querySelector('[data-dark-market-flag]').textContent=selected?.flag||'🇸🇦';
  let countryName=selected?.en||'';try{countryName=new Intl.DisplayNames([root.dataset.lang||'en'],{type:'region'}).of(getMarket());}catch{}
  root.querySelector('[data-dark-market-open]').setAttribute('aria-label',(window.FindziaI18n?.t('Market, language and currency','السوق واللغة والعملة',root)||'Market, language and currency')+' · '+countryName);
 }
 market.addEventListener('change',()=>{setMarket(market.value);sync();});
 language.replaceChildren(...Object.entries(languages).map(([code,label])=>new Option(label,code)));
 function setLanguage(code,{user=true}={}){
  if(!languages[code])code=getMarkets()[getMarket()]?.lang||'en';
  if(user)try{localStorage.setItem('spaces-language-choice-'+getMarket()+'-v1',code);}catch{}
  syncLanguageControls(root,code);
  window.FindziaLocale?.choose(code);window.FindziaI18n?.set(root,code);
  document.documentElement.dir=['ar','ur'].includes(code)?'rtl':'ltr';
  try{localStorage.setItem('findzia-lang',code);}catch{}
  document.dispatchEvent(new CustomEvent('spaces:locale',{detail:{language:code}}));sync();
 }
 language.addEventListener('change',()=>setLanguage(language.value));
 appearance.value=read('findzia-appearance-v1','auto');
 appearance.addEventListener('change',()=>{try{localStorage.setItem('findzia-appearance-v1',appearance.value);}catch{}window.SpacesTheme?.apply();});
 const trigger=root.querySelector('[data-dark-menu-open]');
 trigger.addEventListener('click',()=>{if(!menu.open)menu.showModal();trigger.setAttribute('aria-expanded','true');});
 root.querySelector('[data-dark-menu-close]').addEventListener('click',()=>menu.close());
 menu.addEventListener('close',()=>trigger.setAttribute('aria-expanded','false'));
 menu.addEventListener('click',event=>{if(event.target===menu){const r=menu.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)menu.close();}});
 root.querySelector('[data-dark-market-open]').addEventListener('click',openMarket);
 root.querySelector('[data-home-link]').addEventListener('click',event=>{event.preventDefault();home();});
 const accountReturn=prepareAccountReturn();
 root.addEventListener('click',event=>{
  if(event.target.closest?.('[data-account-provider],[data-dark-settings],[data-profile-settings],.fz-account button'))rememberAccountRoom();
 },true);
 for(const name of ['i18n','motion','support','account','billing'])await import('./findzia/'+name+'.js');
 // resumeLogin opens its own status view and owns the original code exchange.
 if(accountReturn.legacy&&!accountReturn.auth)root.fzAccount.open(accountReturn.view);
 const done=root.querySelector('[data-account-close]');
 if(done)done.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg>';
 window.FindziaLocale.mount(root);setMarketLanguage();
 sync();window.FindziaI18n.refresh();
 root.querySelectorAll('[data-shell-pending]').forEach(el=>{el.disabled=false;el.removeAttribute('data-shell-pending');});
 function setMarketLanguage(){setLanguage(marketLanguage(getMarket(),key=>read(key,'')),{user:false});}
 return {sync,setLanguage,setMarketLanguage,languages,getLanguage:()=>root.dataset.lang||'en'};
}
