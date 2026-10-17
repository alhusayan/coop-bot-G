/* Services trial: shared Findzia identity/wallet; listing data stays separate. */
const root=document.querySelector('[data-services]'),$=s=>root.querySelector(s);
const api='https://api.findzia.com',assets=JSON.parse(root.dataset.serviceAssets);
const read=(key,fallback='')=>{try{return localStorage.getItem(key)||fallback;}catch{return fallback;}};
const write=(key,value)=>{try{localStorage.setItem(key,value);}catch{}};
const {serviceCountries:codes,initialServiceCountry,serviceSearchCredits,serviceResults,serviceWhatsApp,serviceLocation,savedServiceArea,normalizeServiceArea}=await import(assets.state);
let country=initialServiceCountry(read,{zone:Intl.DateTimeFormat().resolvedOptions().timeZone,languages:navigator.languages||[navigator.language]});
let language=read('findzia-lang',navigator.language?.split('-')[0]||'en');
const {serviceDirectory}=await import(assets.catalog);
let locating=false,locationSequence=0,pendingPhoto=null,photoSequence=0,searchAbort=null;
let generation=0,busy=false,retrieving=false,results=null,ready=false,creditConfig=null;
const copy={en:{home:'Findzia home',credits:'Your credits',eyebrow:'FINDZIA · SERVICES',title:'What do you need?',intro:'Choose a service. Find someone nearby.',need:'What do you need?',where:'City or area',queryExample:'Or type any service…',areaExample:'e.g. Salmiya',search:'Find someone nearby',country:'Country',costPending:'Search uses your Findzia credits.',popular:'A place to start',any:'Something else? Just type the service you need.',sort:'Sort by',relevance:'Best match',rating:'Highest rated',resultsNote:'Google Maps listings · Confirm details with the provider.',step1:'Tell us what you need',step1body:'A service and an area. That’s all.',step2:'Meet your options',step2body:'See business details and published reviews.',step3:'Make the connection',step3body:'Call or visit their website directly.',services:'Services',preview:'Preview · Made to make life easier.',preferences:'Your preferences',language:'Language',appearance:'Appearance',auto:'Automatic',light:'Light',dark:'Dark',close:'Close',call:'Call',website:'Website',maps:'Map',noPhone:'No phone number published',noRating:'No published rating',empty:'No specialists found for this search. Try a nearby area or a more specific service. No credits used.',failed:'We couldn’t complete this search. Please try again.',waiting:'Finding specialists for',slow:'Still checking local listings. Your results will appear here.',checking:'Checking your credits…',unavailable:'Couldn’t connect to your account. Reload the page to try again.',reload:'Reload',reviews:'reviews',source:'Google Maps',count:'results',cost:'credits per search · No results, no charge.',free:'Search is currently free.',remaining:'credits',edit:'Change',cancel:'Cancel',details:'Details',noSearchCredit:'You need more search credits. Add credits to continue.',addCredits:'Add credits'},ar:{home:'فاينزيا الرئيسية',credits:'رصيدك',eyebrow:'فاينزيا · الخدمات',title:'شنو تحتاج؟',intro:'اختار الخدمة، ونلقى لك مختص قريب.',need:'شنو تحتاج؟',where:'المدينة أو المنطقة',queryExample:'أو اكتب أي خدمة تحتاجها…',areaExample:'مثلاً: السالمية',search:'ابحث عن مختص قريب',country:'الدولة',costPending:'البحث من رصيدك في فاينزيا.',popular:'من وين نبدأ؟',any:'تحتاج خدمة ثانية؟ اكتبها في خانة البحث.',sort:'ترتيب حسب',relevance:'الأكثر صلة',rating:'الأعلى تقييماً',resultsNote:'بيانات خرائط Google · تأكد من التفاصيل مع المختص.',step1:'قل لنا شنو تحتاج',step1body:'اسم الخدمة والمنطقة. وبس.',step2:'شوف خياراتك',step2body:'بيانات المختصين وتقييماتهم المنشورة.',step3:'تواصل مباشرة',step3body:'اتصل أو افتح موقعهم بكل سهولة.',services:'الخدمات',preview:'نسخة تجريبية · عشان تصير حياتك أسهل.',preferences:'تفضيلاتك',language:'اللغة',appearance:'المظهر',auto:'تلقائي',light:'فاتح',dark:'داكن',close:'إغلاق',call:'اتصل',website:'الموقع',maps:'الخرائط',noPhone:'رقم الهاتف غير منشور',noRating:'لا يوجد تقييم منشور',empty:'ما لقينا مختصين لهذا البحث. جرّب منطقة قريبة أو وصف أوضح للخدمة. ما انخصم رصيد.',failed:'تعذّر إكمال البحث. حاول مرة ثانية.',waiting:'نبحث لك عن مختصين في',slow:'ما زلنا نبحث في القوائم المحلية. النتائج بتظهر هنا.',checking:'نتحقق من رصيدك…',unavailable:'تعذّر الاتصال بحسابك. حدّث الصفحة للمحاولة مجددًا.',reload:'تحديث الصفحة',reviews:'تقييم',source:'خرائط Google',count:'نتائج',cost:'أرصدة للبحث · البحث بدون نتائج مجاني.',free:'البحث مجاني حالياً.',remaining:'رصيد',edit:'تعديل',cancel:'إلغاء',details:'التفاصيل',noSearchCredit:'رصيد البحث غير كافٍ. أضف رصيدًا لمتابعة البحث.',addCredits:'إضافة رصيد'}};

Object.assign(copy.en,{resultsHeading:'Results',allServices:'All services',directoryIntro:'Find help for every part of life.',directorySearch:'Search all services…',customService:'Search for',useLocation:'Use my location',enterArea:'Enter area',changeArea:'Change',locating:'Finding your area…',locationDenied:'Location permission was denied. You can enter your area below.',locationFailed:'We couldn’t find your area. Please enter it below.',locationUnsupported:'This country is not supported yet. Choose a country and area below.',chooseArea:'Choose your area to find nearby help.',whatsapp:'WhatsApp',resultsNote:'Google Maps listings · Contact details published by each business.'});
Object.assign(copy.ar,{resultsHeading:'نتائج البحث',allServices:'كل الخدمات',directoryIntro:'كل اللي تحتاجه، في مكان واحد.',directorySearch:'ابحث في كل الخدمات…',customService:'ابحث عن',useLocation:'استخدم موقعي',enterArea:'اكتب المنطقة',changeArea:'تغيير',locating:'نحدد منطقتك…',locationDenied:'ما تم السماح بالموقع. تقدر تكتب منطقتك تحت.',locationFailed:'ما قدرنا نحدد منطقتك. اكتبها تحت ونكمل.',locationUnsupported:'هالدولة مو مدعومة حالياً. اختار الدولة والمنطقة تحت.',chooseArea:'حدد منطقتك عشان نلقى لك مختص قريب.',whatsapp:'واتساب',resultsNote:'بيانات خرائط Google · وسائل التواصل المنشورة من المختص.'});

Object.assign(copy.en,{newSearch:'New search',camera:'Show us with a photo',cameraHint:'Take a photo. Find the right service.',gallery:'Photos',photoPrivacy:'AI analyses your photo to suggest a service.',photoReady:'Find help from your photo',photoPreparing:'Preparing your photo…',photoAnalysing:'Identifying the service and finding nearby help…',photoChoose:'Which service do you need? Choose to see nearby specialists.',photoUnknown:'We couldn’t identify a service. Try a clearer photo or choose a service below. No credits used.',photoInvalid:'This photo could not be read. Try a JPG, PNG or another photo.',photoUnavailable:'Photo recognition is unavailable right now. Try again or choose a service. No credits used.',removePhoto:'Remove photo',photoLocation:'Choose your area to find the right specialist.',photoRetry:'Try photo again'});
Object.assign(copy.ar,{newSearch:'بحث جديد',camera:'صوّر اللي تحتاجه',cameraHint:'صوّر المشكلة، ونلقى لك الخدمة.',gallery:'الصور',photoPrivacy:'نحلل صورتك بالذكاء الاصطناعي لاقتراح الخدمة.',photoReady:'نلقى الخدمة من صورتك',photoPreparing:'نجهز صورتك…',photoAnalysing:'نتعرف على الخدمة ونبحث لك عن مختص قريب…',photoChoose:'شنو الخدمة اللي تحتاجها؟ اختار ونطلع لك المختصين.',photoUnknown:'ما قدرنا نحدد الخدمة. جرّب صورة أوضح أو اختار الخدمة تحت. ما انخصم رصيد.',photoInvalid:'ما قدرنا نقرأ الصورة. جرّب صورة JPG أو PNG أو صوّر مرة ثانية.',photoUnavailable:'تحليل الصور مو متاح حالياً. جرّب مجدداً أو اختار الخدمة. ما انخصم رصيد.',removePhoto:'إزالة الصورة',photoLocation:'حدد منطقتك عشان نلقى المختص المناسب.',photoRetry:'حلل الصورة مرة ثانية'});
Object.assign(copy.en,{title:'Home services',services:'Home services',intro:'Take a photo or describe what your home needs.',directoryIntro:'Design, installation, repairs and care.',queryExample:'e.g. Carpenter, lighting, cleaning…',photoReady:'What does your home need?',photoChoose:'What do you need here? Choose a service or describe it above.',photoUnknown:'What do you need in this photo? Type the service above. No credits used.'});
Object.assign(copy.ar,{title:'خدمات البيت',services:'خدمات البيت',intro:'صوّر أو اكتب شنو يحتاج بيتك.',directoryIntro:'تصميم، تنفيذ، صيانة وتنظيف.',queryExample:'مثلاً: نجار، إضاءة، تنظيف…',photoReady:'شنو يحتاج بيتك؟',photoChoose:'شنو تحتاج بالصورة؟ اختر خدمة أو اكتبها في الأعلى.',photoUnknown:'شنو تحتاج بالصورة؟ اكتب الخدمة في الأعلى. ما انخصم رصيد.'});
const homeText=key=>window.FindziaHomeCopy?.get(language,key);
const t=k=>{const key={title:'services',services:'services',need:'servicesQuery',queryExample:'servicesQuery',intro:'instruction',photoChoose:'servicesQuery',photoUnknown:'photoUnknown',search:'serviceAction'}[k];return key&&homeText(key)||(copy[language]?.[k])||window.FindziaI18n?.t(copy.en[k],copy.ar[k],root)||copy.en[k]||k};
const icons={camera:'<path d="M3 7h4l2-3h6l2 3h4v14H3z"/><circle cx="12" cy="13" r="4"/>',image:'<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1"/><path d="m3 17 6-6 4 4 3-3 5 5"/>',grid:'<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',locate:'<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3"/>',whatsapp:'<path d="M20.4 11.6a8.4 8.4 0 0 1-12.6 7.3L3 20.3l1.4-4.7a8.4 8.4 0 1 1 16-4Z"/><path d="m8 7 2 3-1 1c1 2 2 3 4 4l1-1 3 2c-2 4-11-3-10-7Z"/>',search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/>',pin:'<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',ac:'<path d="M12 2v20M3.3 7l17.4 10M3.3 17 20.7 7M9 4l3 3 3-3M9 20l3-3 3 3M3 10l4-1-1-4m15 9-4 1 1 4M6 19l1-4-4-1m15-9-1 4 4 1"/>',plumbing:'<path d="M6 3h6v6h6v6h-6V9H6zM4 3h10M18 13v7M15 20h6M4 9h4"/>',electrical:'<path d="m13 2-9 12h7l-1 8 10-13h-7z"/>',cleaning:'<path d="m17 2-7 12M8 11l6 4-4 7-8-5 6-6ZM16 7h5m-2-2v4M4 3v4M2 5h4"/>',moving:'<path d="M2 5h13v12H2zM15 9h4l3 4v4h-7M6 5v5h5V5"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="19" r="2"/>',garden:'<path d="M12 22V10M12 15C4 15 2 9 3 5c6 0 9 4 9 10ZM12 11c0-7 5-9 9-9 0 6-3 10-9 9Z"/>',business:'<path d="M3 10V5h18v5M3 10c0 3 5 3 5 0 0 3 8 3 8 0 0 3 5 3 5 0M4 13v8h16v-8M9 21v-6h6v6"/>',call:'<path d="m4 3 4-1 3 5-3 3a15 15 0 0 0 6 6l3-3 5 3-1 4c-1 5-20-9-17-17Z"/>',web:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c-5 6-5 12 0 18 5-6 5-12 0-18Z"/>'};
function icon(name){const wrap=document.createElement('span');wrap.dataset.icon=name;wrap.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+(icons[name]||icons.business)+'</svg>';return wrap;}
function node(tag,cls,text){const el=document.createElement(tag);if(cls)el.className=cls;if(text!==undefined)el.textContent=text;return el;}
const cats=[['ac','Air conditioning','تكييف','Air conditioning repair','تصليح تكييف'],['plumbing','Plumbing','صحي','Plumber','صحي'],['electrical','Electrical','كهرباء','Electrician','كهربائي'],['cleaning','Cleaning','تنظيف','Cleaning services','خدمات تنظيف'],['carpentry','Carpentry & decor','نجارة وديكور','Carpenter and interior decoration','نجار وديكور داخلي'],['garden','Gardens','حدائق','Gardening services','تنسيق حدائق']];
function countryName(code){try{return new Intl.DisplayNames([language],{type:'region'}).of(code);}catch{return code;}}
function flag(code){return [...code].map(c=>String.fromCodePoint(127397+c.charCodeAt(0))).join('');}
function countries(){for(const select of [$('#svc-country'),$('[data-profile-market-select]')]){select.replaceChildren(...codes.map(code=>new Option(flag(code)+' '+countryName(code),code)));select.value=country;}const trigger=$('[data-dark-market-open]');$('[data-dark-market-flag]').textContent=flag(country);trigger.setAttribute('aria-label',t('preferences')+' · '+countryName(country));}
function text(el,value){if(el&&el.textContent!==String(value))el.textContent=value;}
function creditLabel(){const s=root.fzBilling?.status(),c=s||creditConfig;const label=$('#svc-credit span:last-child');text(label,s&&Number.isFinite(s.remaining)?`${s.remaining} ${t('remaining')}`:t('credits'));if(c)text($('#svc-cost'),c.enabled===false?t('free'):language==='ar'&&c.search_cost===2?'رصيدان للبحث · بلا نتائج؟ بلا خصم.':`${c.search_cost||1} ${t('cost')}`);}
function syncSelection(){
 document.dispatchEvent(new Event('findzia:header-state'));
 const query=$('#svc-query').value.trim();
 $('#svc-categories').querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.query===query)));
}
function chooseService(query){
 if(busy)return;
 clearPhoto();$('#svc-query').value=query;syncSelection();
 const target=$('#svc-area').value.trim()?$('#svc-submit'):$('#svc-locate');
 target.focus({preventScroll:true});$('#svc-form').scrollIntoView({behavior:motion(),block:'nearest'});
}
function localize(){
 root.dataset.lang=language;root.dir=['ar','ur'].includes(language)?'rtl':'ltr';document.documentElement.lang=language;document.documentElement.dir=root.dir;
 for(const el of root.querySelectorAll('[data-copy]'))text(el,t(el.dataset.copy));
 for(const el of root.querySelectorAll('[data-placeholder]'))el.placeholder=t(el.dataset.placeholder);
 for(const el of root.querySelectorAll('[data-copy-aria]'))el.setAttribute('aria-label',t(el.dataset.copyAria));
 $('#svc-market-close').setAttribute('aria-label',t('close'));$('#svc-country').setAttribute('aria-label',t('country'));$('#svc-directory-query').setAttribute('aria-label',t('directorySearch'));
 $('[data-profile-language-select]').value=language;countries();
 const box=$('#svc-categories');box.replaceChildren();
 cats.forEach((cat,index)=>{
  const b=node('button','svc-category');b.type='button';b.dataset.query=cat[language==='ar'?4:3];b.style.setProperty('--svc-order',index);
  b.setAttribute('aria-pressed','false');
  const visual=node('span','svc-category-visual'),img=document.createElement('img');
  img.src=assets.images[cat[0]];img.alt='';img.width=320;img.height=240;img.decoding='async';
  visual.append(img,node('span','svc-selected-mark','✓'));
  b.append(visual,node('span','svc-category-label',cat[language==='ar'?2:1]));
  b.onclick=()=>chooseService(b.dataset.query);box.append(b);
 });
 syncSelection();updateLocation();renderDirectory();creditLabel();if(results)renderResults(false);
}
function updateLocation(){
 const area=$('#svc-area').value.trim();
 $('#svc-locate').classList.toggle('is-set',!!area);
 const label=locating?t('locating'):t('useLocation');
 $('#svc-locate').setAttribute('aria-label',label);$('#svc-locate').title=label;$('#svc-locate').setAttribute('aria-busy',String(locating));
 text($('#svc-manual'),area||t('enterArea'));$('#svc-manual').setAttribute('aria-label',area?t('changeArea')+' · '+area:t('enterArea'));
}
function manualArea(focus=true){
 locationSequence++;locating=false;$('#svc-locate').disabled=false;
 $('#svc-manual-fields').hidden=false;$('#svc-manual').setAttribute('aria-expanded','true');updateLocation();
 if(focus){$('#svc-area').focus({preventScroll:true});keepAreaVisible();setTimeout(keepAreaVisible,320);}
}
function keepAreaVisible(){
 if(document.activeElement!==$('#svc-area'))return;
 requestAnimationFrame(()=>{
  const input=$('#svc-area'),rect=input.getBoundingClientRect();
  const height=Math.min(window.innerHeight,window.visualViewport?.height||window.innerHeight);
  if(rect.bottom>height-28||rect.top<16)input.scrollIntoView({block:'center',behavior:'instant'});
 });
}
function normalizeArea(){
 $('#svc-area').value=normalizeServiceArea($('#svc-area').value,country);updateLocation();remember();
}
async function locateArea(){
 if(locating)return false;
 const sequence=++locationSequence;locating=true;$('#svc-locate').disabled=true;updateLocation();
 const status=$('#svc-location-status');status.hidden=true;
 try{
  if(!navigator.geolocation)throw Error('unsupported');
  const position=await new Promise((resolve,reject)=>navigator.geolocation.getCurrentPosition(resolve,reject,{enableHighAccuracy:false,timeout:12000,maximumAge:300000}));
  if(sequence!==locationSequence)return false;
  const url=new URL('https://api.bigdatacloud.net/data/reverse-geocode-client');
  url.searchParams.set('latitude',position.coords.latitude.toFixed(4));url.searchParams.set('longitude',position.coords.longitude.toFixed(4));url.searchParams.set('localityLanguage',language);
  const response=await fetch(url,{credentials:'omit',referrerPolicy:'no-referrer',signal:AbortSignal.timeout(9000)});
  if(!response.ok)throw Error('geocode');
  const data=await response.json(),found=serviceLocation(data);
  if(sequence!==locationSequence)return false;
  if(!found)throw Error(data.countryCode&&!codes.includes(data.countryCode)?'country':'geocode');
  setCountry(found.country);$('#svc-area').value=found.area;
  $('#svc-manual-fields').hidden=true;$('#svc-manual').setAttribute('aria-expanded','false');
  write('findzia-services-location-denied','');remember();return true;
 }catch(error){
  if(sequence!==locationSequence)return false;
  if(error.code===1)write('findzia-services-location-denied','1');
  manualArea();status.hidden=false;status.textContent=t(error.code===1?'locationDenied':error.message==='country'?'locationUnsupported':'locationFailed');return false;
 }finally{if(sequence===locationSequence){locating=false;$('#svc-locate').disabled=false;updateLocation();}}
}
function renderDirectory(){
 const term=$('#svc-directory-query').value.trim().toLocaleLowerCase(),box=$('#svc-directory-groups');box.replaceChildren();
 for(const group of serviceDirectory){
  const groupMatch=(group[0]+' '+group[1]).toLocaleLowerCase().includes(term);
  const rows=group[3].filter(row=>!term||groupMatch||(row[0]+' '+row[1]).toLocaleLowerCase().includes(term));
  if(!rows.length)continue;
  const detail=node('details','svc-directory-group'),summary=node('summary');
  summary.append(icon(group[2]),node('span','',group[language==='ar'?1:0]),node('span','svc-group-plus','+'));detail.append(summary);
  if(term)detail.open=true;
  detail.addEventListener('toggle',()=>{if(detail.open&&!$('#svc-directory-query').value.trim())box.querySelectorAll('details').forEach(d=>{if(d!==detail)d.open=false;});});
  const list=node('div','svc-directory-list');
  rows.forEach(row=>{const button=node('button','',row[language==='ar'?1:0]);button.type='button';button.onclick=()=>{$('#svc-directory').close();chooseService(row[language==='ar'?1:0]);};list.append(button);});
  detail.append(list);box.append(detail);
 }
 $('#svc-directory-submit').disabled=term.length<2;
}
const motion=()=>matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth';
function setLanguage(value){language=window.FindziaHomeCopy?.languages.includes(value)?value:'en';write('findzia-lang',language);window.FindziaLocale?.choose(language);window.FindziaI18n?.set(root,language);localize();}
function setCountry(value){if(!codes.includes(value))return;country=value;write('findzia-services-country-v1',country);write('findzia-market-country-v1',country);countries();document.dispatchEvent(new CustomEvent('findzia:market-change',{detail:{country}}));}
function notice(message,loading=false){const box=$('#svc-message');box.replaceChildren();box.hidden=!message;if(!message)return;if(loading)box.append(node('span','svc-loading'));box.append(node('p','',message));}
function safeLink(raw,protocols=['https:','http:']){try{const url=new URL(raw);return protocols.includes(url.protocol)?url.href:'';}catch{return '';}}
function link(label,url,symbol,cls=''){const a=node('a',cls,label);a.href=url;if(!url.startsWith('tel:')){a.target='_blank';a.rel='noopener noreferrer';}if(symbol)a.prepend(icon(symbol));return a;}
function renderResults(focus=true){
 const view=serviceResults(results.items,$('#svc-sort').value);
 $('.svc-page').dataset.hasResults=String(view.total>0);
 $('#svc-results').hidden=!view.total;
 $('#svc-suggestions').hidden=!!view.total;
 $('#svc-form').hidden=!!view.total;$('#svc-photo-panel').hidden=!!view.total||!pendingPhoto;
 text($('#svc-results-title'),t('resultsHeading'));
 text($('#svc-results-location'),`${results.area} · ${view.total} ${t('count')}`);
 const box=$('#svc-cards');box.replaceChildren();
 view.items.forEach((row,index)=>{
  const card=node('article','svc-card'),title=node('h3','',row.title);
  title.dir='auto';title.id=`svc-title-${index}`;
  card.setAttribute('aria-labelledby',title.id);const heading=node('div','svc-card-heading');heading.append(icon('business'),title);card.append(heading);
  if(row.rating){
   const rating=node('div','svc-rating');
   rating.setAttribute('aria-label',`${row.rating} / 5 · ${row.reviews??'—'} ${t('reviews')}`);
   const star=node('span','svc-star','★');star.setAttribute('aria-hidden','true');
   rating.append(star,node('strong','',String(row.rating)));
   heading.append(rating);
  }
  const actions=node('div','svc-card-actions');
  const hasPhone=/^tel:\+?\d{7,15}$/.test(row.tel);
  if(hasPhone){
   const call=link('',row.tel,'call','svc-call');call.title=t('call');
   call.setAttribute('aria-label',t('call')+' '+row.title+' '+row.phone);
   actions.append(call);
  }
  const whatsapp=serviceWhatsApp(row);if(whatsapp){const contact=link('',whatsapp,'whatsapp','svc-whatsapp');contact.title=t('whatsapp');contact.setAttribute('aria-label',t('whatsapp')+' · '+row.title);actions.append(contact);}
  const detail=node('div','svc-card-detail');detail.id=`svc-detail-${index}`;detail.hidden=true;
  const fullTitle=node('p','svc-full-title',row.title);fullTitle.dir='auto';detail.append(fullTitle);
  if(row.rating)detail.append(node('p','',`${row.rating} / 5 · ${row.reviews??'—'} ${t('reviews')}`));
  if(row.category){const category=node('p','',row.category);category.dir='auto';detail.append(category);}
  const address=node('p','',row.address);address.dir='auto';detail.append(address);
  if(hasPhone){const number=link(row.phone,row.tel,null,'svc-phone');number.dir='ltr';detail.append(number);}
  else detail.append(node('p','',t('noPhone')));
  const links=node('div','svc-extra-links');if(safeLink(row.website))links.append(link(t('website'),safeLink(row.website),'web'));if(safeLink(row.link))links.append(link(t('maps'),safeLink(row.link),'pin'));detail.append(links);
  const more=node('button','svc-detail-toggle',t('details'));more.type='button';
  more.setAttribute('aria-expanded','false');more.setAttribute('aria-controls',detail.id);
  more.onclick=()=>{detail.hidden=!detail.hidden;more.setAttribute('aria-expanded',String(!detail.hidden));};
  actions.append(more);card.append(actions,detail);box.append(card);
 });
 if(focus&&view.total){if(history.state?.findziaServices!=='results')history.pushState({findziaServices:'results'},'',location.href);$('#svc-results-title').focus({preventScroll:true});$('#svc-results').scrollIntoView({behavior:motion(),block:'start'});}
}
function showCreditLimit(){notice(t('noSearchCredit'));const button=node('button','',t('addCredits'));button.type='button';button.onclick=()=>root.fzAccount.open('plans');$('#svc-message').append(button);$('#svc-message').scrollIntoView({behavior:motion(),block:'center'});}
const areaStorageKey='findzia-services-area-v3',areasStorageKey='findzia-services-areas-v1';
function savedAreas(){try{const value=JSON.parse(read(areasStorageKey));return value&&typeof value==='object'&&!Array.isArray(value)?value:{};}catch{return {};}}
function remember(){
 const saved=savedServiceArea(JSON.stringify({area:$('#svc-area').value,country}));
 write(areaStorageKey,saved?JSON.stringify(saved):'');
 const areas=savedAreas();if(saved)areas[country]=saved;else delete areas[country];write(areasStorageKey,JSON.stringify(areas));
}
function restore(){
 let saved=savedServiceArea(JSON.stringify(savedAreas()[country]))||savedServiceArea(read(areaStorageKey));
 if(!saved)try{saved=savedServiceArea(sessionStorage.getItem('findzia-services-area-v2'));}catch{}
 if(saved&&saved.country===country){$('#svc-area').value=saved.area;remember();}
 try{sessionStorage.removeItem('findzia-services-area-v2');sessionStorage.removeItem('findzia-services-last-v1');}catch{}
}
function clearPhoto(){photoSequence++;pendingPhoto=null;$('#svc-photo-panel').hidden=true;$('#svc-photo-preview').removeAttribute('src');$('#svc-photo-options').replaceChildren();$('#svc-camera-input').value='';$('#svc-gallery-input').value='';$('#svc-query').required=true;}
function resetHome(scroll=true){
 generation++;searchAbort?.abort();searchAbort=null;locationSequence++;locating=false;busy=false;retrieving=false;results=null;
 clearPhoto();$('#svc-query').value='';$('#svc-sort').value='relevance';$('#svc-cards').replaceChildren();$('#svc-results-title').textContent='';$('#svc-results-location').textContent='';
 $('.svc-page').dataset.hasResults='false';$('#svc-results').hidden=true;$('#svc-suggestions').hidden=false;$('#svc-form').hidden=false;
 $('#svc-submit').disabled=false;$('#svc-locate').disabled=false;$('#svc-form').removeAttribute('aria-busy');$('#svc-location-status').hidden=true;
 $('#svc-manual-fields').hidden=true;$('#svc-manual').setAttribute('aria-expanded','false');$('#svc-directory-query').value='';renderDirectory();syncSelection();updateLocation();notice('');remember();
 for(const dialog of root.querySelectorAll('dialog[open]'))dialog.close();document.activeElement?.blur();
 if(scroll){$('.svc-intro h1').setAttribute('tabindex','-1');$('.svc-intro h1').focus({preventScroll:true});window.scrollTo({top:0,behavior:'instant'});}
}
async function preparePhoto(file){
 if(!file)return;if(busy)return;
 resetHome(false);const sequence=++photoSequence;busy=true;
 $('#svc-photo-panel').hidden=false;$('#svc-photo-description').textContent=t('photoPreparing');$('#svc-suggestions').hidden=true;
 try{
  if(file.size>20_000_000||(!file.type.startsWith('image/')&&!/\.(heic|heif)$/i.test(file.name)))throw Error('photo');
  const url=URL.createObjectURL(file),img=new Image();
  try{await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=reject;img.src=url;});}finally{URL.revokeObjectURL(url);}
  if(sequence!==photoSequence)return;
  const scale=Math.min(1,1280/Math.max(img.naturalWidth,img.naturalHeight)),canvas=document.createElement('canvas');
  canvas.width=Math.max(1,Math.round(img.naturalWidth*scale));canvas.height=Math.max(1,Math.round(img.naturalHeight*scale));
  const ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(img,0,0,canvas.width,canvas.height);
  const data=canvas.toDataURL('image/jpeg',.82);pendingPhoto=data.split(',')[1];if(!pendingPhoto||pendingPhoto.length>2_000_000)throw Error('photo');
  $('#svc-photo-preview').src=data;$('#svc-photo-description').textContent=t('photoLocation');$('#svc-query').required=false;
  busy=false;$('#svc-form').requestSubmit();
 }catch(error){if(sequence===photoSequence){busy=false;clearPhoto();$('#svc-suggestions').hidden=false;notice(t('photoInvalid'));}}
}
function photoChoices(photo){
 const box=$('#svc-photo-options');box.replaceChildren();
 $('#svc-photo-panel').hidden=false;$('#svc-suggestions').hidden=false;
 $('#svc-photo-description').textContent=t(photo.status==='unknown'?'photoUnknown':'photoChoose');
 for(const option of photo.options||[]){const button=node('button','',option[language==='ar'?'ar':'en']);button.type='button';button.onclick=()=>{if(busy)return;chooseService(option[language==='ar'?'ar':'en']);$('#svc-form').requestSubmit();};box.append(button);}
 // The image is discarded after analysis; choosing a service performs only a text search.
 pendingPhoto=null;$('#svc-query').required=true;
 $('#svc-photo-panel').scrollIntoView({behavior:motion(),block:'start'});
}
root.fzRefineBridge={api,context:()=>({country,query:$('#svc-query').value,generation,busy:retrieving,media_pending:false}),newSearch:()=>resetHome(),openDesigns:()=>location.assign('https://findzia-spaces-production.up.railway.app/'),accountNotice:message=>notice(message),accountSaved:()=>{try{return JSON.parse(localStorage.getItem('findzia-saved-v1')||'[]');}catch{return [];}},accountRemoveSaved:url=>write('findzia-saved-v1',JSON.stringify(root.fzRefineBridge.accountSaved().filter(x=>x.url!==url))),accountSearch:(query,market)=>{const url=new URL('/',location.origin);url.searchParams.set('q',query);url.searchParams.set('country',market||country);location.assign(url);},snapshot:()=>({view:{items:[]},recommendation:null}),restore:()=>restore(),restoreHomeView:()=>resetHome(),};
const menu=$('[data-dark-menu]'),trigger=$('[data-dark-menu-open]');trigger.onclick=()=>{menu.showModal();trigger.setAttribute('aria-expanded','true');};$('[data-dark-menu-close]').onclick=()=>menu.close();menu.onclose=()=>trigger.setAttribute('aria-expanded','false');
const preferences=$('#svc-market');$('[data-dark-market-open]').onclick=()=>preferences.showModal();$('#svc-market-close').onclick=()=>preferences.close();
for(const dialog of [preferences,menu,$('#svc-directory')])dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
const changeCountry=value=>{if(value!==country&&codes.includes(value)){remember();generation++;searchAbort?.abort();searchAbort=null;busy=false;retrieving=false;results=null;locationSequence++;locating=false;$('#svc-locate').disabled=false;$('#svc-submit').disabled=false;$('#svc-form').removeAttribute('aria-busy');$('#svc-cards').replaceChildren();$('#svc-results').hidden=true;$('.svc-page').dataset.hasResults='false';$('#svc-form').hidden=false;$('#svc-area').value='';setCountry(value);restore();updateLocation();notice('');syncSelection();}};
$('#svc-country').onchange=e=>changeCountry(e.target.value);$('[data-profile-market-select]').onchange=e=>changeCountry(e.target.value);$('[data-profile-language-select]').onchange=e=>setLanguage(e.target.value);$('[data-solar-mode]').value=read('findzia-appearance-v1','auto');$('[data-solar-mode]').onchange=e=>{write('findzia-appearance-v1',e.target.value);window.FindziaAppearance?.apply(root);};
$('#svc-credit').onclick=()=>root.fzAccount?.open('plans');$('#svc-edit').onclick=()=>{history.replaceState({findziaServices:'home'},'',location.href);resetHome();};
$('#svc-sort').onchange=()=>renderResults(false);$('#svc-query').oninput=()=>{if(pendingPhoto){clearPhoto();$('#svc-suggestions').hidden=false;}syncSelection();};
$('#svc-camera').onclick=()=>{if(!busy)$('#svc-camera-input').click();};$('#svc-gallery').onclick=()=>{if(!busy)$('#svc-gallery-input').click();};
for(const id of ['svc-camera-input','svc-gallery-input'])$('#'+id).onchange=e=>preparePhoto(e.target.files?.[0]);
$('#svc-photo-clear').onclick=()=>resetHome();
const brand=$('.fz-brand');if(brand){brand.href='/trial/services';brand.onclick=e=>{e.preventDefault();history.replaceState({findziaServices:'home'},'',location.href);resetHome();};}
window.addEventListener('popstate',()=>resetHome());window.addEventListener('pageshow',event=>{if(event.persisted)resetHome();});
$('#svc-locate').onclick=()=>locateArea();$('#svc-manual').onclick=()=>manualArea();$('#svc-area').oninput=()=>{updateLocation();remember();};$('#svc-area').onchange=normalizeArea;$('#svc-area').addEventListener('focus',keepAreaVisible);
window.addEventListener('resize',keepAreaVisible);window.visualViewport?.addEventListener('resize',keepAreaVisible);
const directory=$('#svc-directory');$('#svc-browse').onclick=()=>{directory.showModal();const title=$('#svc-directory-title');title.tabIndex=-1;title.focus({preventScroll:true});};$('#svc-directory-close').onclick=()=>directory.close();$('#svc-directory-query').oninput=renderDirectory;$('#svc-directory-form').onsubmit=event=>{event.preventDefault();const query=$('#svc-directory-query').value.trim();if(query.length<2||busy)return;directory.close();chooseService(query);$('#svc-form').requestSubmit();};
root.querySelectorAll('.svc-page [data-icon],.svc-directory [data-icon]').forEach(el=>el.replaceWith(icon(el.dataset.icon)));
const languageSelect=$('[data-profile-language-select]');for(const code of window.FindziaHomeCopy?.languages||[]){if(![...languageSelect.options].some(o=>o.value===code)){let name=code;try{name=new Intl.DisplayNames([code],{type:'language'}).of(code)}catch{}languageSelect.add(new Option(name,code));}}
localize();restore();resetHome(false);const entryQuery=new URL(location.href).searchParams.get('q');if(entryQuery)chooseService(entryQuery.slice(0,200));history.replaceState({findziaServices:'home'},'',location.href);updateLocation();syncSelection();window.FindziaAppearance?.apply(root);
$('#svc-form').setAttribute('data-dark-form','');
$('#svc-form').addEventListener('submit',async event=>{
 event.preventDefault();if(busy)return;if(!ready){notice(t('unavailable'));return;}
 if(!pendingPhoto&&!$('#svc-query').reportValidity())return;
 busy=true;const ticket=++generation;$('#svc-submit').disabled=true;$('#svc-form').setAttribute('aria-busy','true');let slowTimer;
 try{
  if(!$('#svc-area').value.trim()){
   if(!$('#svc-manual-fields').hidden||read('findzia-services-location-denied')==='1'){manualArea();$('#svc-area').reportValidity();return;}
   if(!await locateArea())return;
  }
  if(ticket!==generation)return;
  if(!$('#svc-area').checkValidity()){manualArea();$('#svc-area').reportValidity();return;}
  normalizeArea();
  notice(t('checking'),true);
  if(!await root.fzBilling.beforeSearch({kind:pendingPhoto?'image':'text',query:$('#svc-query').value,country})){
   if(ticket!==generation)return;const status=root.fzBilling.status(),available=serviceSearchCredits(status);
   if(available!==null&&available<(status.search_cost||creditConfig?.search_cost||1))showCreditLimit();else notice('');return;
  }
  if(ticket!==generation)return;retrieving=true;document.activeElement?.blur();
  const payload={query:$('#svc-query').value.trim(),area:$('#svc-area').value.trim(),country,language};
  if(pendingPhoto)payload.image=pendingPhoto;
  remember();notice(payload.image?t('photoAnalysing'):`${t('waiting')} ${payload.area}…`,true);
  if(payload.image)$('#svc-photo-description').textContent=t('photoAnalysing');
  slowTimer=setTimeout(()=>{if(ticket===generation)notice(payload.image?t('photoAnalysing'):t('slow'),true);},8500);
  const controller=new AbortController();searchAbort=controller;const timeout=setTimeout(()=>controller.abort(),65000);
  let response,data;
  try{response=await root.fzBilling.fetch(api+'/api/services/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:controller.signal});data=await response.json();}finally{clearTimeout(timeout);}
  if(ticket!==generation)return;
  if(!response.ok){if(root.fzBilling.handleSearchError(data)){if(data.error==='credits_exhausted')showCreditLimit();else notice('');return;}throw Error(data.error||'search');}
  if(data.photo&&data.photo.status!=='clear'){notice('');photoChoices(data.photo);return;}
  if(data.photo)$('#svc-query').value=data.query;
  results=data;clearPhoto();notice(data.items.length?'':t('empty'));renderResults();
 }catch(error){if(ticket===generation){notice(t(error.message==='invalid_service_photo'?'photoInvalid':error.message==='service_photo_unavailable'?'photoUnavailable':'failed'));$('#svc-suggestions').hidden=false;}}
 finally{clearTimeout(slowTimer);if(ticket===generation){busy=false;retrieving=false;searchAbort=null;$('#svc-submit').disabled=false;$('#svc-form').removeAttribute('aria-busy');await root.fzBilling.refresh(true);creditLabel();}}
});
try{for(const name of ['i18n','support','account','billing'])await import(assets[name]);window.FindziaLocale.choose(language);window.FindziaI18n.set(root,language);localize();if(!root.fzAccount||!root.fzBilling)throw Error('shell');ready=true;const response=await fetch(api+'/api/billing/config',{signal:AbortSignal.timeout(8000)});if(response.ok){creditConfig=await response.json();creditLabel();}}catch(error){if(!ready){notice(t('unavailable'));const reload=node('button','',t('reload'));reload.onclick=()=>location.reload();$('#svc-message').append(reload);}}
window.addEventListener('pagehide',remember);window.addEventListener('focus',creditLabel);setInterval(()=>{if(!document.hidden)creditLabel();},3000);
