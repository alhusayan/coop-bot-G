(()=>{
'use strict';
const $=s=>document.querySelector(s),all=s=>[...document.querySelectorAll(s)],html=document.documentElement;
const languages={ar:'العربية',en:'English',fr:'Français',de:'Deutsch',es:'Español',it:'Italiano',pt:'Português',tr:'Türkçe',ru:'Русский',zh:'中文',ja:'日本語',ko:'한국어',hi:'हिन्दी',ur:'اردو',id:'Indonesia',ms:'Melayu',nl:'Nederlands'};
const labels={
 ar:['وين نبدأ؟','تسوّق وقارن','منتجك الواحد','صمّم مساحتك','اطلب خدمة','حسابي','إغلاق','جاري الفتح…','حاول مرة ثانية','تعذّر فتح المشروع','اللغة','المظهر'],
 en:['Where shall we begin?','Shop & compare','Your one product','Design your space','Find a service','My account','Close','Opening…','Try again','Could not open project','Language','Appearance'],
 fr:['Par où commencer ?','Comparez les prix','Votre produit','Créez votre espace','Trouvez un service'],de:['Wo beginnen wir?','Preise vergleichen','Ihr Produkt','Raum gestalten','Service finden'],es:['¿Por dónde empezamos?','Compra y compara','Tu producto','Diseña tu espacio','Busca un servicio'],it:['Da dove iniziamo?','Acquista e confronta','Il tuo prodotto','Progetta il tuo spazio','Trova un servizio'],pt:['Por onde começamos?','Compre e compare','Seu produto','Crie seu espaço','Encontre um serviço'],tr:['Nereden başlayalım?','Alışveriş ve karşılaştırma','Tek ürünün','Alanını tasarla','Hizmet bul'],ru:['С чего начнём?','Сравните цены','Ваш товар','Создайте интерьер','Найдите услугу'],zh:['从哪里开始？','购物比价','你的单品','设计你的空间','寻找服务'],ja:['何から始めますか？','商品・価格を比較','あなたの一品','空間をデザイン','サービスを探す'],ko:['어디서 시작할까요?','쇼핑과 가격 비교','나만의 상품','공간 디자인','서비스 찾기'],hi:['कहाँ से शुरू करें?','खरीदें और तुलना करें','आपका एक उत्पाद','अपनी जगह सजाएँ','सेवा खोजें'],ur:['کہاں سے شروع کریں؟','خریدیں اور موازنہ کریں','آپ کی ایک چیز','اپنی جگہ سجائیں','خدمت تلاش کریں'],id:['Mulai dari mana?','Belanja & bandingkan','Satu produk Anda','Desain ruang Anda','Temukan layanan'],ms:['Mula dari mana?','Beli & bandingkan','Satu produk anda','Reka ruang anda','Cari perkhidmatan'],nl:['Waar beginnen we?','Winkel en vergelijk','Jouw ene product','Ontwerp je ruimte','Vind een dienst']
};
const storyCopy={"ar":["ابدأ بصورة.","صوّر وقارن الأسعار.","صوّر. نختار لك.","صوّر. صمّم. تسوّق.","صوّر المشكلة. لق المختص.","وابحث عن القطع عبر المتاجر."],"en":["Start with a photo.","Snap. Compare prices.","Snap. Get one pick.","Snap. Redesign. Shop.","Show the problem. Find a pro.","Find the pieces across stores."],"fr":["Tout commence par une photo.","Photographiez. Comparez.","Une photo. Un choix.","Photographiez. Décorez. Achetez.","Une photo du problème. Un pro.","Retrouvez les meubles dans plusieurs boutiques."],"de":["Alles beginnt mit einem Foto.","Foto machen. Preise vergleichen.","Ein Foto. Eine Empfehlung.","Foto. Raumdesign. Einkauf.","Problem zeigen. Profi finden.","Möbel bei verschiedenen Händlern finden."],"es":["Empieza con una foto.","Fotografía. Compara precios.","Una foto. Una elección.","Fotografía. Rediseña. Compra.","Muestra el problema. Encuentra ayuda.","Busca los muebles en distintas tiendas."],"it":["Inizia con una foto.","Scatta. Confronta i prezzi.","Una foto. Una scelta.","Scatta. Arreda. Acquista.","Mostra il problema. Trova un esperto.","Cerca gli arredi in più negozi."],"pt":["Comece com uma foto.","Fotografe. Compare preços.","Uma foto. Uma escolha.","Fotografe. Redecore. Compre.","Mostre o problema. Encontre um profissional.","Encontre os móveis em várias lojas."],"ru":["Начните с фото.","Снимайте. Сравнивайте цены.","Одно фото. Один выбор.","Фото. Дизайн. Покупки.","Покажите проблему. Найдите мастера.","Ищите мебель в разных магазинах."],"zh":["从一张照片开始。","拍照比价。","一张照片，一个优选。","拍照。设计。选购。","拍下问题，找到师傅。","在多家商店寻找设计中的家具。"],"ja":["写真から始めよう。","撮って、価格を比較。","写真から、ひとつを厳選。","撮る。模様替え。買う。","困りごとを撮って、プロを探す。","デザインの家具を複数のお店で探す。"],"ko":["사진 한 장으로 시작하세요.","찍고, 가격을 비교하세요.","사진 한 장, 엄선한 하나.","찍고. 꾸미고. 쇼핑하세요.","문제를 찍고, 전문가를 찾으세요.","여러 매장에서 디자인 속 가구를 찾아보세요."],"hi":["एक तस्वीर से शुरू करें।","फ़ोटो लें। कीमतें मिलाएँ।","एक तस्वीर। एक चुनाव।","फ़ोटो लें। सजाएँ। खरीदें।","समस्या दिखाएँ। विशेषज्ञ पाएँ।","अलग-अलग दुकानों में डिज़ाइन का फ़र्नीचर खोजें।"],"ur":["تصویر سے شروع کریں۔","تصویر لیں۔ قیمتیں ملائیں۔","ایک تصویر۔ ایک انتخاب۔","تصویر لیں۔ سجائیں۔ خریدیں۔","مسئلہ دکھائیں۔ ماہر تلاش کریں۔","مختلف دکانوں میں ڈیزائن کا فرنیچر تلاش کریں۔"],"id":["Mulai dengan foto.","Foto. Bandingkan harga.","Satu foto. Satu pilihan.","Foto. Tata ulang. Belanja.","Foto masalahnya. Temukan ahlinya.","Cari furnitur desain Anda di berbagai toko."],"ms":["Mulakan dengan foto.","Ambil foto. Banding harga.","Satu foto. Satu pilihan.","Ambil foto. Reka. Beli.","Tunjuk masalah. Cari pakar.","Cari perabot rekaan anda di pelbagai kedai."],"nl":["Begin met een foto.","Maak een foto. Vergelijk prijzen.","Eén foto. Eén keuze.","Foto. Nieuw interieur. Winkelen.","Toon het probleem. Vind een vakman.","Vind de meubels bij verschillende winkels."],"tr":["Bir fotoğrafla başlayın.","Fotoğraf çek. Fiyatları karşılaştır.","Bir fotoğraf. Tek seçim.","Fotoğraf çek. Tasarla. Alışveriş yap.","Sorunu göster. Uzman bul.","Tasarımdaki mobilyaları farklı mağazalarda ara."]};
for(const [code,values]of Object.entries(storyCopy))labels[code].splice(0,5,...values.slice(0,5));
const keys=['choose','shop','one','space','services','account','close','loading','retry','error','language','appearance'];
const projects={shop:{path:'/search',title:'Findzia'},one:{path:'/trial/one-55321448a0352f1ff18b',title:'Findzia One'},space:{path:'/space',title:'Findzia Space'},services:{path:'/trial/services',title:'Findzia Services'},account:{path:'/search',title:'Findzia'}};
const read=key=>{try{return localStorage.getItem(key)}catch{return null}},save=(key,value)=>{try{localStorage.setItem(key,value)}catch{}};
const validLang=value=>Object.hasOwn(languages,value)?value:'en';
let isReady=false,noticeTimer=null;
let lang=validLang(read('findzia-lang')||html.lang),active=null,frame=null,returnFocus=null,loadTimer=null;
const header=$('#main-header'),search=$('#header-search'),query=$('#header-query');
const layer=$('#project-layer'),content=$('#project-content'),status=$('#layer-status'),retry=$('#retry-project');
window.FindziaHub=true;
const t=key=>key==='spaceDetail'?(storyCopy[lang]||storyCopy.en)[5]:(labels[lang][keys.indexOf(key)]||labels.en[keys.indexOf(key)]||key);
function send(data){frame?.contentWindow?.postMessage({findziaHub:true,...data},location.origin)}
const ui={ar:{typeQuery:'اكتب اسم الخدمة أولاً',menu:'القائمة',home:'الرئيسية',preferences:'الدولة واللغة والمظهر',country:'الدولة',auto:'تلقائي',light:'فاتح',dark:'داكن',photo:'أضف صورة',takePhoto:'التقط صورة',photos:'اختر من الصور',sectionOptions:'خيارات القسم',search:'بحث',addRoom:'أضف صورة مساحتك من العدسة',loading:'لحظة، جاري تجهيز القسم…',unavailable:'تعذّر تنفيذ الطلب. حاول مرة ثانية.',shop:'ابحث عن منتج…',one:'شنو المنتج اللي تبيه؟',space:'صف مساحتك أو الستايل اللي تبيه…',services:'شنو الخدمة اللي تحتاجها؟'},en:{typeQuery:'Enter a service first',menu:'Menu',home:'Home',preferences:'Country, language & appearance',country:'Country',auto:'Automatic',light:'Light',dark:'Dark',photo:'Add a photo',takePhoto:'Take a photo',photos:'Choose from photos',sectionOptions:'Section options',search:'Search',addRoom:'Add your room with the camera above',loading:'Getting this section ready…',unavailable:'Could not complete this action. Please try again.',shop:'Search for a product…',one:'Which product are you looking for?',space:'Describe your space or style…',services:'What service do you need?'}};
const copy=key=>(ui[lang]||ui.en)[key]||ui.en[key]||key;
const defaultCountries=['KW','SA','AE','QA','BH','OM','GB','US','CA','AU','DE','FR','IT','ES','NL','TR','EG','JO','IN','JP','CN','KR','BR','SG','MY','ID'];
let currentCountry=read('findzia-market-country-v1')||'KW',marketOptions=defaultCountries;
const flag=code=>/^[A-Z]{2}$/.test(code)?String.fromCodePoint(...[...code].map(c=>c.charCodeAt(0)+127397)):'🌐';
function notice(key){const node=$('#header-notice');node.textContent=copy(key);node.hidden=false;clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>node.hidden=true,4200)}
// Same-origin synchronous calls preserve the tap's user activation for iOS file pickers.
function action(name,data={}){try{return frame?.contentWindow?.FindziaHubBridge?.action?.(name,data)||false}catch{return false}}
function measureHeader(){const height=Math.ceil(header.getBoundingClientRect().height);if(height)html.style.setProperty('--header-height',height+'px')}
function renderMarkets(){const select=$('#hub-country');select.replaceChildren();let names;try{names=new Intl.DisplayNames([lang],{type:'region'})}catch{}for(const code of marketOptions){const option=document.createElement('option');option.value=code;option.textContent=flag(code)+' '+(names?.of(code)||code);select.append(option)}select.value=currentCountry}
function headerState(data){if(!data)return;if(typeof data.query==='string'&&document.activeElement!==query)query.value=data.query;if(/^[A-Z]{2}$/.test(data.country||'')){currentCountry=data.country;$('#market-flag').textContent=flag(currentCountry)}if(Array.isArray(data.countries)){const codes=data.countries.filter(c=>typeof c==='string'&&/^[A-Z]{2}$/.test(c));if(codes.length)marketOptions=codes;}$('#header-camera').disabled=!isReady||data.busy===true||data.cameraReady===false;$('#submit-search').disabled=!isReady||data.busy===true;query.disabled=!isReady;}
function preferences(){renderMarkets();$('#hub-theme').value=read('findzia-appearance-v1')||'auto';$('#hub-preferences').showModal()}
function render(){html.lang=lang;html.dir=['ar','ur'].includes(lang)?'rtl':'ltr';all('[data-t]').forEach(el=>el.textContent=t(el.dataset.t));all('[data-language]').forEach(el=>{el.value=lang;el.setAttribute('aria-label',t('language'))});all('[data-language-name]').forEach(el=>el.textContent=languages[lang]);all('[data-account]').forEach(el=>el.setAttribute('aria-label',t('account')));$('#close-layer').setAttribute('aria-label',t('close'));all('[data-theme-toggle]').forEach(el=>{el.setAttribute('aria-label',t('appearance'));el.setAttribute('aria-pressed',String(html.dataset.theme==='dark'))});if(active)$('#layer-title').textContent=active==='account'?t('account'):projects[active].title;
 search.hidden=!active||active==='account';$('#close-layer').hidden=!active;$('#close-layer').setAttribute('aria-label',copy('home'));$('#section-options').hidden=!active;$('#projects').inert=!!active;html.toggleAttribute('data-project-open',!!active);all('[data-ui]').forEach(el=>el.textContent=copy(el.dataset.ui));all('[data-dismiss]').forEach(el=>el.setAttribute('aria-label',t('close')));$('#open-menu').setAttribute('aria-label',copy('menu'));$('#open-preferences').setAttribute('aria-label',copy('preferences'));$('#market-flag').textContent=flag(currentCountry);query.placeholder=copy(active||'shop');$('#search-label').textContent=query.placeholder;$('#header-camera').setAttribute('aria-label',copy('photo'));$('#submit-search').setAttribute('aria-label',copy('search'));measureHeader();}

function setLanguage(value,notify=true){lang=validLang(value);save('findzia-lang',lang);render();if(notify)send({type:'preferences',language:lang,theme:read('findzia-appearance-v1')||'auto'})}
function syncTheme(){const theme=window.FindziaAppearance?.apply()?.theme||(read('findzia-appearance-v1')==='dark'?'dark':'light');html.dataset.theme=theme;render()}
function syncAccount(){let signedIn=false;try{const s=JSON.parse(sessionStorage.getItem('findzia-account-v1-session'));signedIn=!!s?.access_token&&s.expires_at>Date.now()/1000}catch{}all('.account-dot').forEach(el=>el.hidden=!signedIn)}
function viewport(){const v=window.visualViewport;if(v&&Math.abs(v.scale-1)>.05)return;html.style.setProperty('--hub-height',Math.round(Math.min(window.innerHeight,v?.height||window.innerHeight))+'px');measureHeader()}
function ready(){clearTimeout(loadTimer);isReady=true;status.hidden=true;retry.hidden=true;send({type:'preferences',language:lang,theme:read('findzia-appearance-v1')||'auto',country:read('findzia-market-country-v1')});headerState(action('state')||{});syncAccount()}
function showError(){status.hidden=false;status.querySelector('[data-t]').textContent=t('error');retry.hidden=false}
function mountFrame(hash=''){
 frame?.remove();isReady=false;query.value='';query.disabled=true;$('#submit-search').disabled=true;$('#header-camera').disabled=true;status.hidden=false;retry.hidden=true;status.querySelector('[data-t]').textContent=t('loading');
 const url=new URL(projects[active].path,location.origin);if(active!=='account'){const outer=new URL(location.href);for(const key of ['q','country'])if(outer.searchParams.has(key))url.searchParams.set(key,outer.searchParams.get(key))}url.searchParams.set('hub','1');url.searchParams.set('hubProject',active);if(active==='account')url.searchParams.set('account','1');if(hash)url.hash=hash;
 frame=document.createElement('iframe');frame.title=active==='account'?t('account'):projects[active].title;frame.allow='camera; microphone; geolocation; payment; clipboard-write';frame.referrerPolicy='same-origin';frame.src=url.href;frame.addEventListener('error',showError);content.prepend(frame);
 clearTimeout(loadTimer);loadTimer=setTimeout(showError,30000);
}
function openProject(key,{push=true,hash=''}={}){
 if(!Object.hasOwn(projects,key))return;
 if(active===key&&layer.open)return;
 returnFocus=document.activeElement;active=key;render();if(!layer.open)layer.show();
 if(push){const url=new URL(location.href);url.searchParams.set('project',key);url.hash='';history.pushState({findziaHub:true},'',url.pathname+url.search)}
 mountFrame(hash);
}
function closeProject({update=true}={}){
 clearTimeout(loadTimer);frame?.remove();frame=null;active=null;isReady=false;marketOptions=defaultCountries;$('#header-notice').hidden=true;if(layer.open)layer.close();
 if(update){const url=new URL(location.href);url.searchParams.delete('project');url.searchParams.delete('q');url.searchParams.delete('country');url.hash='';history.replaceState(null,'',url.pathname+url.search)}
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
 if(data.type==='header-state')headerState(data);
 if(data.type==='market'&&/^[A-Z]{2}$/.test(data.country||'')){currentCountry=data.country;save('findzia-market-country-v1',currentCountry);save('findzia-services-country-v1',currentCountry);render()}
 if(data.type==='close')closeProject();
 if(data.type==='navigate'&&Object.hasOwn(projects,data.project)){const url=new URL(location.href);for(const key of ['q','country']){url.searchParams.delete(key);if(typeof data[key]==='string'&&data[key].length<=1000)url.searchParams.set(key,data[key])}history.replaceState(history.state,'',url.pathname+url.search);openProject(data.project);}
 if(data.type==='language'&&Object.hasOwn(languages,data.language))setLanguage(data.language,false);
 if(data.type==='appearance')syncTheme();
 if(data.type==='account-state')syncAccount();
});
$('#open-menu').addEventListener('click',()=>$('#hub-menu').showModal());
all('[data-dismiss]').forEach(button=>button.addEventListener('click',()=>$('#'+button.dataset.dismiss).close()));
all('[data-go]').forEach(button=>button.addEventListener('click',()=>{$('#hub-menu').close();openProject(button.dataset.go)}));
$('#menu-home').addEventListener('click',()=>{$('#hub-menu').close();closeProject()});
$('#home-link').addEventListener('click',event=>{if(active){event.preventDefault();closeProject()}});
$('#section-options').addEventListener('click',()=>{$('#hub-menu').close();if(!action('menu'))notice('loading')});
$('#open-preferences').addEventListener('click',()=>{if(active&&isReady&&action('market'))return;preferences()});
$('#menu-preferences').addEventListener('click',()=>{$('#hub-menu').close();preferences()});
$('#hub-theme').addEventListener('change',event=>{save('findzia-appearance-v1',event.target.value);syncTheme();send({type:'preferences',language:lang,theme:event.target.value})});
$('#hub-country').addEventListener('change',event=>{const value=event.target.value;if(!marketOptions.includes(value))return;currentCountry=value;save('findzia-market-country-v1',value);save('findzia-services-country-v1',value);save('findzia-market-country-ts-v1',String(Date.now()));save('findzia_manual_market_v1',value);action('country',{country:value});render()});
query.addEventListener('input',()=>action('query',{query:query.value}));
search.addEventListener('submit',event=>{event.preventDefault();if(!isReady)return notice('loading');const value=action('search',{query:query.value});if(value==='needs-query'){notice('typeQuery');query.focus();return}if(value==='needs-photo'){$('#camera-source').showModal();return}if(!value)notice('unavailable');else query.blur()});
$('#header-camera').addEventListener('click',()=>{if(!isReady)return notice('loading');if(['space','services'].includes(active))$('#camera-source').showModal();else if(!action('camera'))notice('unavailable')});
all('[data-camera-source]').forEach(button=>button.addEventListener('click',()=>{$('#camera-source').close();if(!action(button.dataset.cameraSource))notice('unavailable')}));
if(window.ResizeObserver)new ResizeObserver(measureHeader).observe(header);
window.addEventListener('storage',event=>{if(event.key==='findzia-lang')setLanguage(read('findzia-lang')||lang,false);if(event.key==='findzia-appearance-v1')syncTheme();if(event.key==='findzia-account-v1-session')syncAccount()});
window.addEventListener('popstate',()=>{const key=new URL(location.href).searchParams.get('project');if(key&&Object.hasOwn(projects,key))openProject(key,{push:false});else closeProject({update:false})});
window.addEventListener('resize',viewport,{passive:true});window.visualViewport?.addEventListener('resize',viewport,{passive:true});window.addEventListener('pageshow',()=>{viewport();syncAccount();setLanguage(read('findzia-lang')||lang,false);syncTheme()});
viewport();render();syncTheme();syncAccount();
const initial=new URL(location.href),auth=/(?:^#|&)(?:findzia-login|findzia-auth-error)=/.test(initial.hash),key=initial.searchParams.get('project');
if(auth){const hash=initial.hash;initial.hash='';const project=Object.hasOwn(projects,key)?key:'account';initial.searchParams.set('project',project);history.replaceState({findziaHub:true},'',initial.pathname+initial.search);openProject(project,{push:false,hash})}else if(Object.hasOwn(projects,key))openProject(key,{push:false});else if(initial.searchParams.has('q'))openProject('shop',{push:false});
})();
