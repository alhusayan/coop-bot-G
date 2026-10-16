/* Services trial: shared Findzia identity/wallet; listing data stays separate. */
const root=document.querySelector('[data-services]'),$=s=>root.querySelector(s);
const api='https://api.findzia.com',assets=JSON.parse(root.dataset.serviceAssets);
const read=(key,fallback='')=>{try{return localStorage.getItem(key)||fallback;}catch{return fallback;}};
const write=(key,value)=>{try{localStorage.setItem(key,value);}catch{}};
const {serviceCountries:codes,initialServiceCountry,serviceSearchCredits,serviceResultsPage,serviceWhatsApp,serviceLocation}=await import(assets.state);
let country=initialServiceCountry(read,{zone:Intl.DateTimeFormat().resolvedOptions().timeZone,languages:navigator.languages||[navigator.language]});
let language=read('findzia-lang',navigator.language?.startsWith('ar')?'ar':'en')==='ar'?'ar':'en';
const {serviceDirectory}=await import(assets.catalog);
let currentPage=0,editing=false,locating=false,locationSequence=0;
let generation=0,busy=false,retrieving=false,results=null,ready=false,creditConfig=null;
const copy={en:{home:'Findzia home',credits:'Your credits',eyebrow:'FINDZIA · SERVICES',title:'What do you need?',intro:'Choose a service. Find someone nearby.',need:'What do you need?',where:'City or area',queryExample:'Or type any service…',areaExample:'e.g. Salmiya',search:'Find someone nearby',country:'Country',costPending:'Search uses your Findzia credits.',popular:'A place to start',any:'Something else? Just type the service you need.',sort:'Sort by',relevance:'Best match',rating:'Highest rated',resultsNote:'Google Maps listings · Confirm details with the provider.',step1:'Tell us what you need',step1body:'A service and an area. That’s all.',step2:'Meet your options',step2body:'See business details and published reviews.',step3:'Make the connection',step3body:'Call or visit their website directly.',services:'Services',preview:'Preview · Made to make life easier.',preferences:'Your preferences',language:'Language',appearance:'Appearance',auto:'Automatic',light:'Light',dark:'Dark',close:'Close',call:'Call',website:'Website',maps:'Map',noPhone:'No phone number published',noRating:'No published rating',empty:'No specialists found for this search. Try a nearby area or a more specific service. No credits used.',failed:'We couldn’t complete this search. Please try again.',waiting:'Finding specialists for',slow:'Still checking local listings. Your results will appear here.',checking:'Checking your credits…',unavailable:'Couldn’t connect to your account. Reload the page to try again.',reload:'Reload',reviews:'reviews',source:'Google Maps',count:'results',cost:'credits per search · No results, no charge.',free:'Search is currently free.',remaining:'credits',edit:'Change',cancel:'Cancel',details:'Details',previous:'Previous',next:'Next',pages:'Results pages',noSearchCredit:'You need more search credits. Add credits to continue.',addCredits:'Add credits'},ar:{home:'فاينزيا الرئيسية',credits:'رصيدك',eyebrow:'فاينزيا · الخدمات',title:'شنو تحتاج؟',intro:'اختار الخدمة، ونلقى لك مختص قريب.',need:'شنو تحتاج؟',where:'المدينة أو المنطقة',queryExample:'أو اكتب أي خدمة تحتاجها…',areaExample:'مثلاً: السالمية',search:'ابحث عن مختص قريب',country:'الدولة',costPending:'البحث من رصيدك في فاينزيا.',popular:'من وين نبدأ؟',any:'تحتاج خدمة ثانية؟ اكتبها في خانة البحث.',sort:'ترتيب حسب',relevance:'الأكثر صلة',rating:'الأعلى تقييماً',resultsNote:'بيانات خرائط Google · تأكد من التفاصيل مع المختص.',step1:'قل لنا شنو تحتاج',step1body:'اسم الخدمة والمنطقة. وبس.',step2:'شوف خياراتك',step2body:'بيانات المختصين وتقييماتهم المنشورة.',step3:'تواصل مباشرة',step3body:'اتصل أو افتح موقعهم بكل سهولة.',services:'الخدمات',preview:'نسخة تجريبية · عشان تصير حياتك أسهل.',preferences:'تفضيلاتك',language:'اللغة',appearance:'المظهر',auto:'تلقائي',light:'فاتح',dark:'داكن',close:'إغلاق',call:'اتصل',website:'الموقع',maps:'الخرائط',noPhone:'رقم الهاتف غير منشور',noRating:'لا يوجد تقييم منشور',empty:'ما لقينا مختصين لهذا البحث. جرّب منطقة قريبة أو وصف أوضح للخدمة. ما انخصم رصيد.',failed:'تعذّر إكمال البحث. حاول مرة ثانية.',waiting:'نبحث لك عن مختصين في',slow:'ما زلنا نبحث في القوائم المحلية. النتائج بتظهر هنا.',checking:'نتحقق من رصيدك…',unavailable:'تعذّر الاتصال بحسابك. حدّث الصفحة للمحاولة مجددًا.',reload:'تحديث الصفحة',reviews:'تقييم',source:'خرائط Google',count:'نتائج',cost:'أرصدة للبحث · البحث بدون نتائج مجاني.',free:'البحث مجاني حالياً.',remaining:'رصيد',edit:'تعديل',cancel:'إلغاء',details:'التفاصيل',previous:'السابق',next:'التالي',pages:'صفحات النتائج',noSearchCredit:'رصيد البحث غير كافٍ. أضف رصيدًا لمتابعة البحث.',addCredits:'إضافة رصيد'}};

Object.assign(copy.en,{allServices:'All services',directoryIntro:'Find help for every part of life.',directorySearch:'Search all services…',customService:'Search for',useLocation:'Use my location',enterArea:'Enter area',changeArea:'Change',locating:'Finding your area…',locationDenied:'Location permission was denied. You can enter your area below.',locationFailed:'We couldn’t find your area. Please enter it below.',locationUnsupported:'This country is not supported yet. Choose a country and area below.',chooseArea:'Choose your area to find nearby help.',whatsapp:'WhatsApp',resultsNote:'Google Maps listings · WhatsApp requires a registered number.'});
Object.assign(copy.ar,{allServices:'كل الخدمات',directoryIntro:'كل اللي تحتاجه، في مكان واحد.',directorySearch:'ابحث في كل الخدمات…',customService:'ابحث عن',useLocation:'استخدم موقعي',enterArea:'اكتب المنطقة',changeArea:'تغيير',locating:'نحدد منطقتك…',locationDenied:'ما تم السماح بالموقع. تقدر تكتب منطقتك تحت.',locationFailed:'ما قدرنا نحدد منطقتك. اكتبها تحت ونكمل.',locationUnsupported:'هالدولة مو مدعومة حالياً. اختار الدولة والمنطقة تحت.',chooseArea:'حدد منطقتك عشان نلقى لك مختص قريب.',whatsapp:'واتساب',resultsNote:'بيانات خرائط Google · واتساب يعمل إذا كان الرقم مسجلاً فيه.'});
const t=k=>copy[language][k]||copy.en[k]||k;
const icons={grid:'<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',locate:'<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3"/>',whatsapp:'<path d="M20.4 11.6a8.4 8.4 0 0 1-12.6 7.3L3 20.3l1.4-4.7a8.4 8.4 0 1 1 16-4Z"/><path d="m8 7 2 3-1 1c1 2 2 3 4 4l1-1 3 2c-2 4-11-3-10-7Z"/>',search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/>',pin:'<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',ac:'<path d="M12 2v20M3.3 7l17.4 10M3.3 17 20.7 7M9 4l3 3 3-3M9 20l3-3 3 3M3 10l4-1-1-4m15 9-4 1 1 4M6 19l1-4-4-1m15-9-1 4 4 1"/>',plumbing:'<path d="M6 3h6v6h6v6h-6V9H6zM4 3h10M18 13v7M15 20h6M4 9h4"/>',electrical:'<path d="m13 2-9 12h7l-1 8 10-13h-7z"/>',cleaning:'<path d="m17 2-7 12M8 11l6 4-4 7-8-5 6-6ZM16 7h5m-2-2v4M4 3v4M2 5h4"/>',moving:'<path d="M2 5h13v12H2zM15 9h4l3 4v4h-7M6 5v5h5V5"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="19" r="2"/>',garden:'<path d="M12 22V10M12 15C4 15 2 9 3 5c6 0 9 4 9 10ZM12 11c0-7 5-9 9-9 0 6-3 10-9 9Z"/>',business:'<path d="M3 10V5h18v5M3 10c0 3 5 3 5 0 0 3 8 3 8 0 0 3 5 3 5 0M4 13v8h16v-8M9 21v-6h6v6"/>',call:'<path d="m4 3 4-1 3 5-3 3a15 15 0 0 0 6 6l3-3 5 3-1 4c-1 5-20-9-17-17Z"/>',web:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c-5 6-5 12 0 18 5-6 5-12 0-18Z"/>'};
function icon(name){const wrap=document.createElement('span');wrap.dataset.icon=name;wrap.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+(icons[name]||icons.business)+'</svg>';return wrap;}
function node(tag,cls,text){const el=document.createElement(tag);if(cls)el.className=cls;if(text!==undefined)el.textContent=text;return el;}
const cats=[['ac','Air conditioning','تكييف','Air conditioning repair','تصليح تكييف'],['plumbing','Plumbing','سباكة','Plumber','سباك'],['electrical','Electrical','كهرباء','Electrician','كهربائي'],['cleaning','Cleaning','تنظيف','Cleaning services','خدمات تنظيف'],['moving','Moving','نقل عفش','Moving company','نقل عفش'],['garden','Gardens','حدائق','Gardening services','تنسيق حدائق']];
function countryName(code){try{return new Intl.DisplayNames([language],{type:'region'}).of(code);}catch{return code;}}
function flag(code){return [...code].map(c=>String.fromCodePoint(127397+c.charCodeAt(0))).join('');}
function countries(){for(const select of [$('#svc-country'),$('[data-profile-market-select]')]){select.replaceChildren(...codes.map(code=>new Option(flag(code)+' '+countryName(code),code)));select.value=country;}const trigger=$('[data-dark-market-open]');$('[data-dark-market-flag]').textContent=flag(country);trigger.setAttribute('aria-label',t('preferences')+' · '+countryName(country));}
function text(el,value){if(el&&el.textContent!==String(value))el.textContent=value;}
function creditLabel(){const s=root.fzBilling?.status(),c=s||creditConfig;const label=$('#svc-credit span:last-child');text(label,s&&Number.isFinite(s.remaining)?`${s.remaining} ${t('remaining')}`:t('credits'));if(c)text($('#svc-cost'),c.enabled===false?t('free'):language==='ar'&&c.search_cost===2?'رصيدان للبحث · بلا نتائج؟ بلا خصم.':`${c.search_cost||1} ${t('cost')}`);}
function syncSelection(){
 const query=$('#svc-query').value.trim();
 $('#svc-categories').querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.query===query)));
}
function chooseService(query){
 if(busy)return;
 $('#svc-query').value=query;syncSelection();
 const target=$('#svc-area').value.trim()?$('#svc-submit'):$('#svc-locate');
 target.focus({preventScroll:true});$('#svc-form').scrollIntoView({behavior:motion(),block:'nearest'});
}
function localize(){
 root.dataset.lang=language;root.dir=language==='ar'?'rtl':'ltr';document.documentElement.lang=language;document.documentElement.dir=root.dir;
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
 text($('#svc-locate-label'),locating?t('locating'):area||t('useLocation'));
 text($('#svc-manual'),area?t('changeArea'):t('enterArea'));
}
function manualArea(focus=true){
 locationSequence++;locating=false;$('#svc-locate').disabled=false;
 $('#svc-manual-fields').hidden=false;$('#svc-manual').setAttribute('aria-expanded','true');updateLocation();
 if(focus)$('#svc-area').focus({preventScroll:true});
}
async function locateArea(){
 if(locating)return false;
 const sequence=++locationSequence;locating=true;$('#svc-locate').disabled=true;updateLocation();
 const status=$('#svc-location-status');status.hidden=true;
 try{
  if(!navigator.geolocation)throw Error('unsupported');
  const position=await new Promise((resolve,reject)=>navigator.geolocation.getCurrentPosition(resolve,reject,{enableHighAccuracy:false,timeout:12000,maximumAge:0}));
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
  remember();return true;
 }catch(error){
  if(sequence!==locationSequence)return false;
  manualArea(false);status.hidden=false;status.textContent=t(error.code===1?'locationDenied':error.message==='country'?'locationUnsupported':'locationFailed');return false;
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
 const custom=$('#svc-directory-custom');custom.hidden=term.length<2;text(custom,t('customService')+' “'+$('#svc-directory-query').value.trim()+'”');
}
const motion=()=>matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth';
function setLanguage(value){language=value==='ar'?'ar':'en';write('findzia-lang',language);window.FindziaLocale?.choose(language);window.FindziaI18n?.set(root,language);localize();}
function setCountry(value){if(!codes.includes(value))return;country=value;write('findzia-services-country-v1',country);countries();}
function notice(message,loading=false){const box=$('#svc-message');box.replaceChildren();box.hidden=!message;if(!message)return;if(loading)box.append(node('span','svc-loading'));box.append(node('p','',message));}
function safeLink(raw,protocols=['https:','http:']){try{const url=new URL(raw);return protocols.includes(url.protocol)?url.href:'';}catch{return '';}}
function link(label,url,symbol,cls=''){const a=node('a',cls,label);a.href=url;if(!url.startsWith('tel:')){a.target='_blank';a.rel='noopener noreferrer';}if(symbol)a.prepend(icon(symbol));return a;}
function setEditing(value){
 editing=value;
 const hasResults=!!results?.items?.length;
 $('#svc-form').hidden=hasResults&&!editing;
 $('#svc-cancel-edit').hidden=!hasResults||!editing;
 $('#svc-edit').setAttribute('aria-expanded',String(editing));
}
function renderResults(focus=true){
 const view=serviceResultsPage(results.items,$('#svc-sort').value,currentPage);
 currentPage=view.page;
 $('.svc-page').dataset.hasResults=String(view.total>0);
 $('#svc-results').hidden=!view.total;
 $('#svc-suggestions').hidden=!!view.total;
 setEditing(editing);
 text($('#svc-results-title'),results.query);
 text($('#svc-results-location'),`${results.area} · ${view.total} ${t('count')}`);
 const box=$('#svc-cards');box.replaceChildren();
 view.items.forEach((row,index)=>{
  const card=node('article','svc-card'),title=node('h3','',row.title);
  title.dir='auto';title.id=`svc-title-${currentPage}-${index}`;
  card.setAttribute('aria-labelledby',title.id);const heading=node('div','svc-card-heading');heading.append(icon('business'),title);card.append(heading);
  if(row.rating){
   const rating=node('div','svc-rating');
   rating.setAttribute('aria-label',`${row.rating} / 5 · ${row.reviews??'—'} ${t('reviews')}`);
   const star=node('span','svc-star','★');star.setAttribute('aria-hidden','true');
   rating.append(star,node('strong','',String(row.rating)));
   if(row.reviews!=null)rating.append(node('span','',`(${row.reviews})`));
   card.append(rating);
  }
  const actions=node('div','svc-card-actions');
  const hasPhone=/^tel:\+?\d{7,15}$/.test(row.tel);
  if(hasPhone){
   const call=link(t('call'),row.tel,'call','svc-call');
   call.setAttribute('aria-label',t('call')+' '+row.title+' '+row.phone);
   actions.append(call);
  }
  const whatsapp=serviceWhatsApp(row.tel);if(whatsapp)actions.append(link(t('whatsapp'),whatsapp,'whatsapp','svc-whatsapp'));
  const detail=node('div','svc-card-detail');detail.id=`svc-detail-${currentPage}-${index}`;detail.hidden=true;
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
 $('#svc-pagination').hidden=view.pages<2;
 $('#svc-pagination').setAttribute('aria-label',t('pages'));
 $('#svc-prev').disabled=currentPage===0;
 $('#svc-next').disabled=currentPage===view.pages-1;
 text($('#svc-page-number'),`${currentPage+1} / ${view.pages}`);
 if(focus&&view.total){$('#svc-results-title').focus({preventScroll:true});$('#svc-results').scrollIntoView({behavior:motion(),block:'start'});}
}
function showCreditLimit(){notice(t('noSearchCredit'));const button=node('button','',t('addCredits'));button.type='button';button.onclick=()=>root.fzAccount.open('plans');$('#svc-message').append(button);$('#svc-message').scrollIntoView({behavior:motion(),block:'center'});}
function remember(){try{sessionStorage.setItem('findzia-services-last-v1',JSON.stringify({at:Date.now(),results,page:currentPage,query:$('#svc-query').value,area:$('#svc-area').value,country}));}catch{}}
function restore(){try{const saved=JSON.parse(sessionStorage.getItem('findzia-services-last-v1'));if(saved&&Date.now()-saved.at<1800000){$('#svc-query').value=saved.query||'';$('#svc-area').value=saved.area||'';setCountry(saved.country);if(saved.results?.items?.length){results=saved.results;currentPage=saved.page||0;editing=false;renderResults(false);}}}catch{}}
root.fzRefineBridge={api,context:()=>({country,query:$('#svc-query').value,generation,busy:retrieving,media_pending:false}),newSearch:()=>location.assign('/'),openDesigns:()=>location.assign('https://findzia-spaces-production.up.railway.app/'),accountNotice:message=>notice(message),accountSaved:()=>{try{return JSON.parse(localStorage.getItem('findzia-saved-v1')||'[]');}catch{return [];}},accountRemoveSaved:url=>write('findzia-saved-v1',JSON.stringify(root.fzRefineBridge.accountSaved().filter(x=>x.url!==url))),accountSearch:(query,market)=>{const url=new URL('/',location.origin);url.searchParams.set('q',query);url.searchParams.set('country',market||country);location.assign(url);},snapshot:()=>({view:{items:[]},recommendation:null}),restore:()=>restore(),restoreHomeView:()=>{},};
const menu=$('[data-dark-menu]'),trigger=$('[data-dark-menu-open]');trigger.onclick=()=>{menu.showModal();trigger.setAttribute('aria-expanded','true');};$('[data-dark-menu-close]').onclick=()=>menu.close();menu.onclose=()=>trigger.setAttribute('aria-expanded','false');
const preferences=$('#svc-market');$('[data-dark-market-open]').onclick=()=>preferences.showModal();$('#svc-market-close').onclick=()=>preferences.close();
for(const dialog of [preferences,menu,$('#svc-directory')])dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
const changeCountry=value=>{if(value!==country){locationSequence++;locating=false;$('#svc-locate').disabled=false;$('#svc-area').value='';setCountry(value);updateLocation();}};
$('#svc-country').onchange=e=>changeCountry(e.target.value);$('[data-profile-market-select]').onchange=e=>changeCountry(e.target.value);$('[data-profile-language-select]').onchange=e=>setLanguage(e.target.value);$('[data-solar-mode]').value=read('findzia-appearance-v1','auto');$('[data-solar-mode]').onchange=e=>{write('findzia-appearance-v1',e.target.value);window.FindziaAppearance?.apply(root);};
$('#svc-credit').onclick=()=>root.fzAccount?.open('plans');$('#svc-edit').onclick=()=>{setEditing(true);$('#svc-query').focus({preventScroll:true});$('#svc-form').scrollIntoView({behavior:motion(),block:'start'});};
$('#svc-cancel-edit').onclick=()=>{$('#svc-query').value=results.query;$('#svc-area').value=results.area;setCountry(results.country);setEditing(false);$('#svc-edit').focus({preventScroll:true});};
$('#svc-sort').onchange=()=>{currentPage=0;renderResults(false);remember();};
$('#svc-prev').onclick=()=>{currentPage--;renderResults();remember();};
$('#svc-next').onclick=()=>{currentPage++;renderResults();remember();};$('#svc-query').oninput=syncSelection;
$('#svc-locate').onclick=()=>locateArea();$('#svc-manual').onclick=()=>manualArea();$('#svc-area').oninput=()=>{updateLocation();remember();};
const directory=$('#svc-directory');$('#svc-browse').onclick=()=>{directory.showModal();};$('#svc-directory-close').onclick=()=>directory.close();$('#svc-directory-query').oninput=renderDirectory;$('#svc-directory-custom').onclick=()=>{directory.close();chooseService($('#svc-directory-query').value.trim());};
root.querySelectorAll('.svc-page [data-icon],.svc-directory [data-icon]').forEach(el=>el.replaceWith(icon(el.dataset.icon)));
localize();restore();updateLocation();syncSelection();window.FindziaAppearance?.apply(root);
$('#svc-form').setAttribute('data-dark-form','');
$('#svc-form').addEventListener('submit',async event=>{event.preventDefault();if(busy)return;if(!ready){notice(t('unavailable'));return;}if(!$('#svc-query').reportValidity())return;if(!$('#svc-area').value.trim()){if(!$('#svc-manual-fields').hidden){$('#svc-area').reportValidity();return;}if(!await locateArea())return;}if(!$('#svc-area').checkValidity()){manualArea();$('#svc-area').reportValidity();return;}busy=true;generation++;$('#svc-submit').disabled=true;$('#svc-form').setAttribute('aria-busy','true');notice(t('checking'),true);let slowTimer;
 try{if(!await root.fzBilling.beforeSearch({kind:'text',query:$('#svc-query').value,country})){const status=root.fzBilling.status(),available=serviceSearchCredits(status);if(available!==null&&available<(status.search_cost||creditConfig?.search_cost||1))showCreditLimit();else notice('');return;}retrieving=true;document.activeElement?.blur();const payload={query:$('#svc-query').value.trim(),area:$('#svc-area').value.trim(),country,language};remember();notice(`${t('waiting')} ${payload.area}…`,true);slowTimer=setTimeout(()=>notice(t('slow'),true),8500);const response=await root.fzBilling.fetch(api+'/api/services/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:AbortSignal.timeout(35000)});const data=await response.json();if(!response.ok){if(root.fzBilling.handleSearchError(data)){if(data.error==='credits_exhausted')showCreditLimit();else notice('');return;}throw Error(data.error||'search');}results=data;currentPage=0;editing=false;remember();notice(data.items.length?'':t('empty'));renderResults();
 }catch(error){notice(t('failed'));}finally{clearTimeout(slowTimer);busy=false;retrieving=false;$('#svc-submit').disabled=false;$('#svc-form').removeAttribute('aria-busy');await root.fzBilling.refresh(true);creditLabel();}});
try{for(const name of ['i18n','support','account','billing'])await import(assets[name]);window.FindziaLocale.choose(language);window.FindziaI18n.set(root,language);localize();if(!root.fzAccount||!root.fzBilling)throw Error('shell');ready=true;const response=await fetch(api+'/api/billing/config',{signal:AbortSignal.timeout(8000)});if(response.ok){creditConfig=await response.json();creditLabel();}}catch(error){if(!ready){notice(t('unavailable'));const reload=node('button','',t('reload'));reload.onclick=()=>location.reload();$('#svc-message').append(reload);}}
window.addEventListener('pagehide',remember);window.addEventListener('focus',creditLabel);setInterval(()=>{if(!document.hidden)creditLabel();},3000);
