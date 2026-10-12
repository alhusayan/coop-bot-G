// Connect the original Findzia account, billing and menu to the Spaces screens.
// The account API remains the single authority for identity, credits and payment.
const languages={en:'English',ar:'العربية',de:'Deutsch',fr:'Français',it:'Italiano',es:'Español',pt:'Português',tr:'Türkçe',ru:'Русский',ja:'日本語',zh:'中文',ko:'한국어',hi:'हिन्दी',ur:'اردو',id:'Bahasa Indonesia',ms:'Bahasa Melayu'};
const read=(key,fallback)=>{try{return localStorage.getItem(key)||fallback;}catch{return fallback;}};
export async function mountFindzia({getMarket,getMarkets,setMarket,openMarket,openDesigns,home,notice}){
 const root=document.querySelector('#findzia-home-spaces'),menu=root.querySelector('[data-dark-menu]');
 const market=root.querySelector('[data-profile-market-select]'),language=root.querySelector('[data-profile-language-select]'),appearance=root.querySelector('[data-solar-mode]');
 root.fzRefineBridge={api:'https://api.findzia.com',context:()=>({country:getMarket(),query:'',generation:0,busy:false,media_pending:false}),
  newSearch:home,openDesigns,accountNotice:notice,
  accountSaved:()=>{try{return JSON.parse(localStorage.getItem('findzia-saved-v1')||'[]');}catch{return [];}},
  accountRemoveSaved:url=>{const saved=root.fzRefineBridge.accountSaved().filter(x=>x.url!==url);localStorage.setItem('findzia-saved-v1',JSON.stringify(saved));},
  accountSearch:(query,country)=>{const url=new URL('https://findzia.com/');url.searchParams.set('q',query);url.searchParams.set('country',country||getMarket());location.assign(url.href);},
  snapshot:()=>({view:{items:[]},recommendation:null}),restore:()=>{},restoreHomeView:home
 };
 function sync(){
  const markets=getMarkets();market.replaceChildren(...Object.entries(markets).map(([code,m])=>new Option(m.flag+' '+m.en,code)));market.value=getMarket();
  const selected=markets[getMarket()];root.querySelector('[data-dark-market-flag]').textContent=selected?.flag||'🇰🇼';
  root.querySelector('[data-dark-market-open]').setAttribute('aria-label',(window.FindziaI18n?.t('Market, language and currency','السوق واللغة والعملة',root)||'Market, language and currency')+' · '+(selected?.en||''));
 }
 market.addEventListener('change',()=>{setMarket(market.value);sync();});
 language.replaceChildren(...Object.entries(languages).map(([code,label])=>new Option(label,code)));
 function setLanguage(code){
  window.FindziaLocale?.choose(code);window.FindziaI18n?.set(root,code);language.value=code;
  document.documentElement.dir=['ar','ur'].includes(code)?'rtl':'ltr';
  try{localStorage.setItem('findzia-lang',code);}catch{}
  document.dispatchEvent(new CustomEvent('spaces:locale',{detail:{language:code}}));sync();
 }
 language.addEventListener('change',()=>setLanguage(language.value));
 appearance.value=read('findzia-appearance-v1','light');
 appearance.addEventListener('change',()=>{try{localStorage.setItem('findzia-appearance-v1',appearance.value);}catch{}window.FindziaAppearance.apply(root,window.FindziaAppearance.resolve(appearance.value));});
 const trigger=root.querySelector('[data-dark-menu-open]');
 trigger.addEventListener('click',()=>{if(!menu.open)menu.showModal();trigger.setAttribute('aria-expanded','true');});
 root.querySelector('[data-dark-menu-close]').addEventListener('click',()=>menu.close());
 menu.addEventListener('close',()=>trigger.setAttribute('aria-expanded','false'));
 menu.addEventListener('click',event=>{if(event.target===menu){const r=menu.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)menu.close();}});
 root.querySelector('[data-dark-market-open]').addEventListener('click',openMarket);
 root.querySelector('[data-home-link]').addEventListener('click',event=>{event.preventDefault();home();});
 for(const name of ['boot','i18n','motion','support','account','billing']){await import('./findzia/'+name+'.js');if(name==='boot')window.FindziaAppearance.apply(root,window.FindziaAppearance.resolve(appearance.value));}
 window.FindziaLocale.mount(root);language.value=root.dataset.lang;
 sync();window.FindziaI18n.refresh();
 root.querySelectorAll('[data-shell-pending]').forEach(el=>{el.disabled=false;el.removeAttribute('data-shell-pending');});
 return {sync,setLanguage,languages,getLanguage:()=>root.dataset.lang||'en'};
}
