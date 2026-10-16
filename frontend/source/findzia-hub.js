(()=>{
'use strict';
const $=s=>document.querySelector(s),all=s=>[...document.querySelectorAll(s)],html=document.documentElement;
const languages={ar:'العربية',en:'English',fr:'Français',de:'Deutsch',es:'Español',it:'Italiano',pt:'Português',tr:'Türkçe',ru:'Русский',zh:'中文',ja:'日本語',ko:'한국어',hi:'हिन्दी',ur:'اردو',id:'Indonesia',ms:'Melayu',nl:'Nederlands'};
const labels={
 ar:['وين نبدأ؟','تسوّق وقارن','منتجك الواحد','صمّم مساحتك','اطلب خدمة','حسابي','إغلاق','جاري الفتح…','حاول مرة ثانية','تعذّر فتح المشروع','اللغة','المظهر'],
 en:['Where shall we begin?','Shop & compare','Your one product','Design your space','Find a service','My account','Close','Opening…','Try again','Could not open project','Language','Appearance'],
 fr:['Par où commencer ?','Comparez les prix','Votre produit','Créez votre espace','Trouvez un service'],de:['Wo beginnen wir?','Preise vergleichen','Ihr Produkt','Raum gestalten','Service finden'],es:['¿Por dónde empezamos?','Compra y compara','Tu producto','Diseña tu espacio','Busca un servicio'],it:['Da dove iniziamo?','Acquista e confronta','Il tuo prodotto','Progetta il tuo spazio','Trova un servizio'],pt:['Por onde começamos?','Compre e compare','Seu produto','Crie seu espaço','Encontre um serviço'],tr:['Nereden başlayalım?','Alışveriş ve karşılaştırma','Tek ürünün','Alanını tasarla','Hizmet bul'],ru:['С чего начнём?','Сравните цены','Ваш товар','Создайте интерьер','Найдите услугу'],zh:['从哪里开始？','购物比价','你的单品','设计你的空间','寻找服务'],ja:['何から始めますか？','商品・価格を比較','あなたの一品','空間をデザイン','サービスを探す'],ko:['어디서 시작할까요?','쇼핑과 가격 비교','나만의 상품','공간 디자인','서비스 찾기'],hi:['कहाँ से शुरू करें?','खरीदें और तुलना करें','आपका एक उत्पाद','अपनी जगह सजाएँ','सेवा खोजें'],ur:['کہاں سے شروع کریں؟','خریدیں اور موازنہ کریں','آپ کی ایک چیز','اپنی جگہ سجائیں','خدمت تلاش کریں'],id:['Mulai dari mana?','Belanja & bandingkan','Satu produk Anda','Desain ruang Anda','Temukan layanan'],ms:['Mula dari mana?','Beli & bandingkan','Satu produk anda','Reka ruang anda','Cari perkhidmatan'],nl:['Waar beginnen we?','Winkel en vergelijk','Jouw ene product','Ontwerp je ruimte','Vind een dienst']
};
const keys=['choose','shop','one','space','services','account','close','loading','retry','error','language','appearance'];
const projects={shop:{path:'/search',title:'Findzia'},one:{path:'/trial/one-55321448a0352f1ff18b',title:'Findzia One'},space:{path:'/space',title:'Findzia Space'},services:{path:'/trial/services',title:'Findzia Services'},account:{path:'/search',title:'Findzia'}};
const read=key=>{try{return localStorage.getItem(key)}catch{return null}},save=(key,value)=>{try{localStorage.setItem(key,value)}catch{}};
const validLang=value=>Object.hasOwn(languages,value)?value:'en';
let lang=validLang(read('findzia-lang')||html.lang),active=null,frame=null,returnFocus=null,loadTimer=null;
const layer=$('#project-layer'),content=$('#project-content'),status=$('#layer-status'),retry=$('#retry-project');
window.FindziaHub=true;
const t=key=>(labels[lang][keys.indexOf(key)]||labels.en[keys.indexOf(key)]||key);
function send(data){frame?.contentWindow?.postMessage({findziaHub:true,...data},location.origin)}
function render(){html.lang=lang;html.dir=['ar','ur'].includes(lang)?'rtl':'ltr';all('[data-t]').forEach(el=>el.textContent=t(el.dataset.t));all('[data-language]').forEach(el=>{el.value=lang;el.setAttribute('aria-label',t('language'))});all('[data-language-name]').forEach(el=>el.textContent=languages[lang]);all('[data-account]').forEach(el=>el.setAttribute('aria-label',t('account')));$('#close-layer').setAttribute('aria-label',t('close'));all('[data-theme-toggle]').forEach(el=>{el.setAttribute('aria-label',t('appearance'));el.setAttribute('aria-pressed',String(html.dataset.theme==='dark'))});if(active)$('#layer-title').textContent=active==='account'?t('account'):projects[active].title;}
function setLanguage(value,notify=true){lang=validLang(value);save('findzia-lang',lang);render();if(notify)send({type:'preferences',language:lang,theme:read('findzia-appearance-v1')||'auto'})}
function syncTheme(){const theme=window.FindziaAppearance?.apply()?.theme||(read('findzia-appearance-v1')==='dark'?'dark':'light');html.dataset.theme=theme;render()}
function syncAccount(){let signedIn=false;try{const s=JSON.parse(sessionStorage.getItem('findzia-account-v1-session'));signedIn=!!s?.access_token&&s.expires_at>Date.now()/1000}catch{}all('.account-dot').forEach(el=>el.hidden=!signedIn)}
function viewport(){const v=window.visualViewport;if(v&&Math.abs(v.scale-1)>.05)return;html.style.setProperty('--hub-height',Math.round(Math.min(window.innerHeight,v?.height||window.innerHeight))+'px')}
function ready(){clearTimeout(loadTimer);status.hidden=true;retry.hidden=true;send({type:'preferences',language:lang,theme:read('findzia-appearance-v1')||'auto'});syncAccount()}
function showError(){status.hidden=false;status.querySelector('[data-t]').textContent=t('error');retry.hidden=false}
function mountFrame(hash=''){
 frame?.remove();status.hidden=false;retry.hidden=true;status.querySelector('[data-t]').textContent=t('loading');
 const url=new URL(projects[active].path,location.origin);if(active==='shop'){const outer=new URL(location.href);for(const key of ['q','country'])if(outer.searchParams.has(key))url.searchParams.set(key,outer.searchParams.get(key))}url.searchParams.set('hub','1');url.searchParams.set('hubProject',active);if(active==='account')url.searchParams.set('account','1');if(hash)url.hash=hash;
 frame=document.createElement('iframe');frame.title=active==='account'?t('account'):projects[active].title;frame.allow='camera; microphone; geolocation; payment; clipboard-write';frame.referrerPolicy='same-origin';frame.src=url.href;frame.addEventListener('error',showError);content.prepend(frame);
 clearTimeout(loadTimer);loadTimer=setTimeout(showError,30000);
}
function openProject(key,{push=true,hash=''}={}){
 if(!Object.hasOwn(projects,key))return;
 if(active===key&&layer.open)return;
 returnFocus=document.activeElement;active=key;render();if(!layer.open)layer.showModal();
 if(push){const url=new URL(location.href);url.searchParams.set('project',key);url.hash='';history.pushState({findziaHub:true},'',url.pathname+url.search)}
 mountFrame(hash);
}
function closeProject({update=true}={}){
 clearTimeout(loadTimer);frame?.remove();frame=null;active=null;if(layer.open)layer.close();
 if(update){const url=new URL(location.href);url.searchParams.delete('project');url.hash='';history.replaceState(null,'',url.pathname+url.search)}
 syncAccount();setLanguage(read('findzia-lang')||lang,false);syncTheme();returnFocus?.focus?.({preventScroll:true});
}
all('[data-language]').forEach(select=>{for(const [value,label]of Object.entries(languages)){const option=document.createElement('option');option.value=value;option.textContent=label;select.append(option)}select.addEventListener('change',()=>setLanguage(select.value))});
all('[data-project]').forEach(card=>card.addEventListener('click',event=>{if(event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;event.preventDefault();openProject(card.dataset.project)}));
all('[data-account]').forEach(button=>button.addEventListener('click',()=>{if(active)send({type:'account'});else openProject('account')}));
all('[data-theme-toggle]').forEach(button=>button.addEventListener('click',()=>{save('findzia-appearance-v1',html.dataset.theme==='dark'?'light':'dark');syncTheme();send({type:'preferences',language:lang,theme:read('findzia-appearance-v1')})}));
$('#close-layer').addEventListener('click',()=>closeProject());layer.addEventListener('cancel',event=>{event.preventDefault();closeProject()});retry.addEventListener('click',()=>mountFrame());
window.addEventListener('message',event=>{
 if(event.origin!==location.origin||event.source!==frame?.contentWindow||event.data?.findziaHub!==true)return;
 const data=event.data;
 if(data.type==='ready')ready();
 if(data.type==='close')closeProject();
 if(data.type==='navigate'&&Object.hasOwn(projects,data.project)){const url=new URL(location.href);for(const key of ['q','country']){url.searchParams.delete(key);if(typeof data[key]==='string'&&data[key].length<=1000)url.searchParams.set(key,data[key])}history.replaceState(history.state,'',url.pathname+url.search);openProject(data.project);}
 if(data.type==='language'&&Object.hasOwn(languages,data.language))setLanguage(data.language,false);
 if(data.type==='appearance')syncTheme();
 if(data.type==='account-state')syncAccount();
});
window.addEventListener('storage',event=>{if(event.key==='findzia-lang')setLanguage(read('findzia-lang')||lang,false);if(event.key==='findzia-appearance-v1')syncTheme();if(event.key==='findzia-account-v1-session')syncAccount()});
window.addEventListener('popstate',()=>{const key=new URL(location.href).searchParams.get('project');if(key&&Object.hasOwn(projects,key))openProject(key,{push:false});else closeProject({update:false})});
window.addEventListener('resize',viewport,{passive:true});window.visualViewport?.addEventListener('resize',viewport,{passive:true});window.addEventListener('pageshow',()=>{viewport();syncAccount();setLanguage(read('findzia-lang')||lang,false);syncTheme()});
viewport();render();syncTheme();syncAccount();
const initial=new URL(location.href),auth=/(?:^#|&)(?:findzia-login|findzia-auth-error)=/.test(initial.hash),key=initial.searchParams.get('project');
if(auth){const hash=initial.hash;initial.hash='';const project=Object.hasOwn(projects,key)?key:'account';initial.searchParams.set('project',project);history.replaceState({findziaHub:true},'',initial.pathname+initial.search);openProject(project,{push:false,hash})}else if(Object.hasOwn(projects,key))openProject(key,{push:false});else if(initial.searchParams.has('q'))openProject('shop',{push:false});
})();
