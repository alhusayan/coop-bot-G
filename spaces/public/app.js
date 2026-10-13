import {MARKETS,orderedMarkets,browserMarket,detectMarket} from './markets.js';
import {productKey,updateDesignPicks,hasSavedResults,savedPickImage} from './design-picks.js';
import {createOriginalLayer} from './original-results.js';
import {mountFindzia} from './findzia-shell.js';
import {pieceViews,pickPhotoPiece} from './hotspots.js';
import {createLocalCatalog} from './local-catalog.js';
import {request} from './request.js';
import {patchHTML,updateImage,pieceActivity} from './live-view.js';
import {createRoomContext,acceptsJob} from './room-state.js';
const roomContext=createRoomContext(),optionOrder=new Map();
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const paths={checkCircle:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M8 12l3 3 5-6',camera:'M4 7h4l2-3h4l2 3h4v13H4z M16 13a4 4 0 1 1-8 0 4 4 0 0 1 8 0',plus:'M12 5v14M5 12h14',back:'M19 12H5m6-6-6 6 6 6',forward:'M5 12h14m-6-6 6 6-6 6',chevron:'m7 10 5 5 5-5',folder:'M3 6h7l2 3h9v12H3z',close:'m6 6 12 12M6 18 18 6',spark:'m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z',download:'M12 3v13m-5-5 5 5 5-5M4 17v4h16v-4',compare:'M12 2v20M3 5h7v14H3zm11 0h7v14h-7',check:'m5 12 4 4L19 6',external:'M14 3h7v7M21 3l-11 11M9 5H3v16h16v-6',expand:'M4 9V4h5m6 0h5v5M4 15v5h5m6 0h5v-5',more:'M5 11a1 1 0 1 0 0 2 1 1 0 0 0 0-2m7 0a1 1 0 1 0 0 2 1 1 0 0 0 0-2m7 0a1 1 0 1 0 0 2 1 1 0 0 0 0-2'};
const icon=(name,small=false)=>`<span class="icon${small?' small':''}" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="${paths[name]||paths.spark}"/></svg></span>`;
$$('[data-icon]').forEach(el=>el.innerHTML=`<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[el.dataset.icon]||paths.spark}"/></svg>`);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safe=u=>{try{const a=new URL(u,location.origin);return (a.protocol==='https:'||a.origin===location.origin)&&!a.username&&!a.password?a.href:'';}catch{return '';}};
const fallbackMarkets=MARKETS;
const initialMarket=browserMarket({timeZone:Intl.DateTimeFormat().resolvedOptions().timeZone,languages:globalThis.navigator?.languages||[]});
let marketChosen=false;
const state={view:'home',market:initialMarket,detectedMarket:initialMarket,image:null,job:null,design:0,compare:false,config:{markets:fallbackMarkets},auth:null,selections:{},quantities:{},itemId:null};
try{state.selections=JSON.parse(localStorage.getItem('spaces-v2-selections')||'{}');state.quantities=JSON.parse(localStorage.getItem('spaces-v2-quantities')||'{}');}catch{}
const designBookmarks={},demoViews={};
try{Object.assign(designBookmarks,JSON.parse(localStorage.getItem('spaces-design-picks-v1')||'{}'));Object.assign(demoViews,JSON.parse(localStorage.getItem('spaces-demo-views-v1')||'{}'));}catch{}
let shell,pointFocus=null;
function resultView(item){
 const demo=state.job?.demo&&demoViews[searchKey(item)],recent=demo&&Date.now()-demo.at<86400000?demo.view:null;
 const view=item.original_views?.[countryCode()]||(hasSavedResults(item.original_view,countryCode())?item.original_view:null)||recent;return hasSavedResults(view,countryCode())?view:null;
}
function picksFor(item){return item.design_picks||designBookmarks[keyFor(item)]||[];}
function imageForPick(item,pick){
 const views=[item.original_view,...Object.values(item.original_views||{}),...Object.entries(demoViews).filter(([key])=>key.startsWith(keyFor(item)+':')).map(([,entry])=>entry.view)];
 return savedPickImage(pick,views.flatMap(view=>view?.items||[]));
}
function renderDesignPicks(){
 const host=$('#design-picks');if(!host)return;
 const items=selected()?.items||[],groups=items.filter(item=>picksFor(item).length);
 host.hidden=!groups.length;
 patchHTML(host,groups.length?`<div class="design-picks-heading"><div><h2>${esc(translate('Your design picks','اختياراتك لهذا التصميم'))}</h2><p>${esc(translate('The pieces you saved for this room.','القطع التي حفظتها لهذه الغرفة.'))}</p></div><span>${groups.reduce((n,item)=>n+picksFor(item).length,0)}</span></div><div class="design-picks-grid">${groups.flatMap(item=>picksFor(item).map((pick,index)=>`<article class="design-pick" data-ui-key="${esc(keyFor(item)+':'+pick.url)}"><a class="design-pick-photo" href="${safe(pick.url)}" target="_blank" rel="noopener noreferrer sponsored" aria-label="${esc(pick.title)}"><img src="${esc(safe(imageForPick(item,pick)))}" alt="${esc(pick.title)}" loading="lazy" referrerpolicy="no-referrer"></a><button class="design-pick-remove" aria-pressed="true" data-action="remove-pick" data-id="${item.id}" data-index="${index}" aria-label="${esc(translate('Remove from this design','إزالة من هذا التصميم'))}">${icon('checkCircle',true)}</button><div class="design-pick-copy"><span class="design-pick-piece">${esc(item.name_en)}</span><strong>${esc((pick.price||translate('View price at store','السعر لدى المتجر')).replace(/\s+([.,]\d)/g,'$1'))}</strong><div class="design-pick-store"><span>${esc(pick.store)}</span><span>${esc(pick.flag)}</span></div><a class="design-pick-visit" href="${safe(pick.url)}" target="_blank" rel="noopener noreferrer sponsored">${esc(translate('View at store','عرض في المتجر'))} ${icon('external',true)}</a></div></article>`)).join('')}</div>`:'');
}
async function saveDesignPick(session,product,remove){
 const bookmarkKey=[session.room,session.design,session.item].join(':');
 const sameRoom=state.job?.id===session.room,item=sameRoom?state.job.designs[session.design]?.items.find(x=>x.id===session.item):null;
 const previous=item?.design_picks||designBookmarks[bookmarkKey]||session.picks||[];
 const picks=session.readOnly?updateDesignPicks(previous,product,remove):(await api('/api/jobs/'+session.room+'/picks/'+session.item,{method:'POST',body:JSON.stringify({design:session.design,product,remove})})).picks;
 designBookmarks[bookmarkKey]=picks;if(item)item.design_picks=picks;
 try{localStorage.setItem('spaces-design-picks-v1',JSON.stringify(designBookmarks));}catch{}
 if(sameRoom&&state.design===session.design)renderDesignPicks();return picks;
}
const pointLaunches=new Set(),pointSettled=new Set(),pointStarted=new Map();
let pointTimer;
const translate=(en,ar)=>window.FindziaI18n?.t(en,ar,document.querySelector('.fz-home'))||en;
const localCatalog=createLocalCatalog({request,escape:esc,safe,money,translate,icon,context:item=>({key:[state.job?.id,state.design,state.job?.options?.market,item.id].join(':'),market:state.job?.options?.market,marketName:country().en,url:'/api/jobs/'+state.job?.id+'/catalog/'+state.design+'/'+item.id})});
let pollTimer,toastTimer,renderKey='',shopKey='',submitting=false,sheetMode='',pollErrors=0,gestureDragged=false;
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
const messages={credits_exhausted:'You’ve used your credits. Add credits to search another piece.',credits_unavailable:'Could not check your credits. Please try again.',sign_in_required:'Please open your account and try again.',session_expired:'Please sign in again.',guest_session_expired:'Please reopen your account and try again.',search_in_progress:'Another search is still running. Please wait.',search_already_processed:'This search was already processed. Reopen the piece.',REQUEST_ID_REQUIRED:'Please refresh this page and try again.',OUT_OF_STOCK:'This piece sold out. We’re finding another option.',STOCK_UNCONFIRMED:'Check availability at the store before choosing this piece.',TRIAL_LINK_REQUIRED:'Open your private preview link to start.',NOT_CONFIGURED:'Designs are temporarily unavailable. Please try again later.',MODEL_UNAVAILABLE:'The design service is temporarily unavailable.',GENERATION_FAILED:'We couldn’t create this design. Please try again.',NO_IMAGE:'The design didn’t arrive. Please try again.',PROVIDER_BUSY:'We’re busy right now. Please try again shortly.',TRIAL_LIMIT:'You’ve reached today’s preview limit. Come back tomorrow.',IMAGE_TOO_LARGE:'Choose a photo under 20 MB.',INVALID_IMAGE:'Please try a JPG, PNG or WebP photo.',NOT_A_ROOM:'Please use a clear photo of a room or outdoor space.',INTERRUPTED:'This design was interrupted. Try it again.',NO_ITEMS:'We couldn’t identify the pieces. Please try this design again.',ENGINE_UNAVAILABLE:'Search is temporarily unavailable. Please try again shortly.',SEARCH_FAILED:'The stores aren’t responding. Please try again.',DEMO_READ_ONLY:'Upload your own photo to customise a room.',NOT_FOUND:'This room has expired or belongs to another browser.',JOB_BUSY:'This room is still being prepared.',INVALID_CROP:'This piece is not clear enough to search.',ROOM_FUNCTION_MISMATCH:'This design changed the room’s purpose. Please try again.'};
function toast(text){$('#toast').textContent=translate(text);$('#toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').classList.remove('show'),5500);}
async function api(path,opt={}){const r=await request(path,{...opt,headers:{'Content-Type':'application/json',...opt.headers}});let data;try{data=await r.json();}catch{throw Error('Connection interrupted. Please try again.');}if(!r.ok)throw Object.assign(Error(messages[data.error]||'Something went wrong. Please try again.'),{code:data.error});return data;}
function resetRoom(){originalLayer.close();clearTimeout(pointTimer);pointStarted.clear();pointFocus=null;pointLaunches.clear();roomContext.begin();optionOrder.clear();clearTimeout(pollTimer);closeSheet();state.job=null;state.image=null;state.design=0;state.compare=false;state.itemId=null;updateImage($('#selected-image'),'');renderKey='';shopKey='';pollErrors=0;$('#items-list').innerHTML='';$('#hotspots').innerHTML='';}
function applyJob(job,token){if(!roomContext.current(token)||!acceptsJob(state.job,job))return false;state.job=job;return true;}
async function changeJob(path,body){const token=roomContext.capture(),id=state.job?.id;const job=await api('/api/jobs/'+id+path,{method:'POST',body:JSON.stringify({...body,language:shell?.getLanguage()||'en'})});return state.job?.id===id&&applyJob(job,token);}
function view(name){state.view=name;$$('.view').forEach(x=>x.classList.toggle('hidden',x.id!==name));window.scrollTo({top:0,behavior:'instant'});if(name==='designs')renderDesigns();if(name==='shopping')renderShop();}
function country(){return state.config.markets[state.job?.options?.market||state.market]||fallbackMarkets.KW;}
function money(n,currency=country().currency){if(n==null||!Number.isFinite(n))return 'Price at store';try{return new Intl.NumberFormat('en-US',{style:'currency',currency:currency||'USD',currencyDisplay:'code',maximumFractionDigits:['KWD','BHD','OMR'].includes(currency)?3:2}).format(n);}catch{return currency+' '+n;}}
function syncMarket(){if(!state.config.markets[state.market])state.market=initialMarket;const m=state.config.markets[state.market];$('#currency-label').textContent=m.currency;try{localStorage.setItem('spaces-market',state.market);}catch{}shell?.sync();}
let accessCheck;
function init(){
 if(accessCheck)return accessCheck;
 syncMarket();$('#retry-access').disabled=true;
 accessCheck=(async()=>{
  try{const [config,detected]=await Promise.all([api('/api/config'),detectMarket({fallback:initialMarket})]);state.config=config;state.detectedMarket=detected;if(!marketChosen&&!state.job)state.market=detected;state.auth=true;syncMarket();shell?.setMarketLanguage();$('#auth-notice').classList.add('hidden');$('#retry-access').classList.add('hidden');return true;}
  catch(e){state.auth=e.code==='TRIAL_LINK_REQUIRED'?false:null;$('#auth-notice').textContent=state.auth===false?'This is a private preview. Open the invitation link shared with you.':'Couldn’t connect. Please try again.';$('#auth-notice').classList.remove('hidden');$('#retry-access').classList.remove('hidden');return false;}
  finally{$$('[data-action="upload"], [data-action="camera"], [data-action="demo"]').forEach(el=>el.disabled=state.auth!==true);$('#retry-access').disabled=false;}
 })().finally(()=>accessCheck=null);
 return accessCheck;
}
$('#retry-access').addEventListener('click',init);
window.addEventListener('online',()=>{if(state.auth!==true)init();if(active())poll();});
window.addEventListener('focus',()=>{if(state.auth!==true)init();});
async function normalizeImage(file){if(file.size>20*1024*1024)throw Error(messages.IMAGE_TOO_LARGE);if(!file.type.startsWith('image/'))throw Error(messages.INVALID_IMAGE);const src=URL.createObjectURL(file);try{return await new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>{if(Math.min(img.naturalWidth,img.naturalHeight)<160)return reject(Error('Please choose a clearer room photo.'));const scale=Math.min(1,2000/Math.max(img.naturalWidth,img.naturalHeight)),c=document.createElement('canvas');c.width=Math.round(img.naturalWidth*scale);c.height=Math.round(img.naturalHeight*scale);const ctx=c.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,c.width,c.height);ctx.drawImage(img,0,0,c.width,c.height);resolve(c.toDataURL('image/jpeg',.93));};img.onerror=()=>reject(Error('We couldn’t open this photo. Try exporting it as JPG.'));img.src=src;});}finally{URL.revokeObjectURL(src);}}
async function loadFile(file){if(!file)return;resetRoom();const token=roomContext.capture();try{if(state.auth!==true&&!await init())return;const image=await normalizeImage(file);if(!roomContext.current(token))return;state.image=image;$('#upload-preview').src=state.image;view('setup');}catch(e){toast(e.message);}finally{$('#file-input').value='';$('#camera-input').value='';}}
$('#file-input').addEventListener('change',e=>loadFile(e.target.files[0]));$('#camera-input').addEventListener('change',e=>loadFile(e.target.files[0]));
for(const e of ['dragenter','dragover'])$('#drop-zone').addEventListener(e,x=>{x.preventDefault();$('#drop-zone').classList.add('dragging');});for(const e of ['drop','dragleave'])$('#drop-zone').addEventListener(e,x=>{x.preventDefault();$('#drop-zone').classList.remove('dragging');if(e==='drop')loadFile(x.dataTransfer.files[0]);});
$('#design-form').addEventListener('submit',async e=>{e.preventDefault();if(submitting)return;if(!state.image)return toast('Add a room photo first.');submitting=true;const token=roomContext.begin();clearTimeout(pollTimer);$('#generate-button').disabled=true;try{const job=await api('/api/jobs',{method:'POST',headers:{'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify({...Object.fromEntries(new FormData(e.target)),market:state.market,language:shell?.getLanguage()||'en',image:state.image})});if(!applyJob(job,token))return;renderKey='';view('designs');poll();}catch(e){toast(e.message);}finally{submitting=false;$('#generate-button').disabled=false;}});
function active(){return state.job?.designs.some(d=>['generating','analyzing','searching','adapting'].includes(d.status)||d.items?.some(x=>x.status==='searching'));}
function poll(){clearTimeout(pollTimer);const token=roomContext.capture(),id=state.job?.id;if(!id)return;pollTimer=setTimeout(async()=>{if(!roomContext.current(token)||state.job?.id!==id)return;try{const job=await api('/api/jobs/'+id);if(!applyJob(job,token)){if(roomContext.current(token)&&state.job?.id===id&&active())poll();return;}pollErrors=0;if(state.view==='designs')renderDesigns();if(state.view==='shopping')renderShop();if(active())poll();}catch(e){if(!roomContext.current(token))return;pollErrors++;if(pollErrors===2)toast(translate('Reconnecting to your search…','جارٍ الاتصال…'));if(state.view==='shopping')renderShop();if(active())poll();else toast(e.message);}},Math.min(10000,1500*(pollErrors+1)));}
function renderDesigns(){const j=state.job;if(!j)return;$('#original-thumb').src=j.original;const n=j.designs.filter(d=>d.image).length,working=j.designs.some(d=>d.status==='generating');$('#generation-status').textContent=working?(n?`${n} of 3 ready. You can start exploring.`:'Creating three possibilities…'):n===3?'Three designs, ready to explore.':n?'Choose a design, or retry the others.':'Let’s give that another try.';const key=JSON.stringify(j.designs.map(d=>[d.image,d.status==='error',d.error]));if(key===renderKey)return;renderKey=key;patchHTML($('#design-grid'),j.designs.map((d,i)=>`<article data-ui-key="${j.id}:${i}" class="design-card${d.image?'':' waiting'}"><button class="design-image" data-action="preview" data-index="${i}" aria-label="Preview ${esc(d.title)}" ${d.image?'':'disabled'}><img src="${esc(d.image||j.original)}" alt="${d.image?esc(d.title):'Your original room'}">${!d.image?`<span class="design-progress"><span class="breathing-mark">${icon('spark')}</span>${d.status==='error'?'Let’s try again':'Creating your design'}</span>`:''}</button><div class="design-card-body"><h3>${esc(d.title)}</h3>${d.status==='error'?`<p class="error-copy">${esc(messages[d.error]||messages.GENERATION_FAILED)}</p><button class="secondary wide" data-action="retry" data-index="${i}">Try again</button>`:`<button class="secondary wide" data-action="choose" data-index="${i}" ${!d.image?'disabled':''}>Explore this design ${icon('forward',true)}</button>`}</div></article>`).join(''));}
async function choose(index){if(!state.job?.designs[index]?.image)return;pointFocus=null;const token=roomContext.begin(),id=state.job.id;clearTimeout(pollTimer);closeSheet();state.design=index;state.compare=false;shopKey='';const d=state.job.designs[index];if(!d.items?.length||d.needs_rescan){d.status='analyzing';d.items=[];}view('shopping');try{const job=await api('/api/jobs/'+id+'/select',{method:'POST',body:JSON.stringify({design:index,language:shell?.getLanguage()||'en'})});if(!applyJob(job,token))return;shopKey='';renderShop();poll();}catch(e){if(roomContext.current(token))toast(e.message);}}
const selected=()=>state.job?.designs[state.design];
const keyFor=item=>[state.job.id,state.design,item.id].join(':');
const searchKey=item=>keyFor(item)+':'+countryCode();
function chosen(item){const offers=item.offers||[],key=keyFor(item),offer=offers.find(o=>o.link===state.selections[key])||offers[0]||null;if(offer)state.selections[key]=offer.link;return offer;}
function qty(item){return Math.max(1,Math.min(20,Number(state.quantities[keyFor(item)])||item.quantity||1));}
function persistSelection(){try{localStorage.setItem('spaces-v2-selections',JSON.stringify(state.selections));localStorage.setItem('spaces-v2-quantities',JSON.stringify(state.quantities));}catch{}}
function total(){let sum=0,count=0;const items=selected()?.items||[];for(const item of items){const o=chosen(item);if(item.mode==='ready'&&(!o?.price_kind||o.price_kind==='exact')&&o?.price!=null&&o.currency===country().currency&&o.availability!=='out_of_stock'){sum+=o.price*qty(item);count++;}}return {sum,count,items:items.filter(x=>x.mode!=='keep').length};}
function itemStatus(item){if(item.search_engine==='findzia-original'&&item.alternatives?.length){const prices=item.alternatives.filter(x=>x.currency===country().currency&&typeof x.price==='number'&&Number.isFinite(x.price)&&x.price>0).map(x=>x.price);return item.alternatives.length+' store options'+(prices.length?' · '+money(Math.min(...prices)):'');}if(item.status==='kept')return 'Keep your own';if(item.alternatives?.length)return 'View store options';if(['searching','idle'].includes(item.status))return pieceActivity(item)+'…';if(item.status==='error')return 'Tap to retry';return item.search_engine==='findzia-original'?'No close matches found':'No exact match found';}
const pieceBusy=item=>!!item&&(originalLayer.busy(searchKey(item))||item.status==='searching'||pointLaunches.has(keyFor(item)));
function searchCopy(item){
 if(pollErrors)return translate('Reconnecting to your search…','جارٍ الاتصال…');
 if(pointLaunches.has(keyFor(item)))return translate('Starting your search…','جارٍ إعداد بحثك…');
 if(item.alternatives?.length)return translate('More store options are arriving…','جارٍ التحقق من خيارات إضافية…');
 if(item.checked>0)return translate('Checking the matches…','جارٍ التحقق من تفاصيل المنتج...');
 return translate('Searching stores…','جارٍ البحث في المتاجر…');
}
function searchSeconds(item){const start=pointStarted.get(searchKey(item))||item.started_at||Date.now();return Math.max(0,Math.floor((Date.now()-start)/1000));}
function elapsedLabel(item){return searchSeconds(item)+(shell?.getLanguage()==='ar'?' ث':'s');}
function photoMarkup(items){
 if(!items.length||['analyzing','adapting'].includes(selected().status))return '';
 const item=items.find(x=>pointFocus?.key===keyFor(x)),busy=pieceBusy(item);
 const view=item&&(pieceViews([item]).find(v=>v.marker===pointFocus?.marker)||pieceViews([item])[0]);
 let outline='';
 const guide=!item?`<span class="photo-touch-guide" aria-hidden="true"><span class="touch-ripple">${icon('plus',true)}</span><span>${esc(translate('Tap a piece to shop','اضغط على قطعة للتسوّق'))}</span></span>`:'';
 if(view){const [top,left,bottom,right]=view.box;outline=`<span class="piece-outline${busy?' is-searching':''}" style="top:${top/10}%;left:${left/10}%;width:${(right-left)/10}%;height:${(bottom-top)/10}%" aria-hidden="true"><i></i><i></i><i></i><i></i>${busy?'<span class="piece-scan"></span>':''}</span>`;}
 return `<button class="photo-pick-target" data-ui-key="photo-picker" data-action="photo-pick" aria-label="${esc(translate('Choose a piece in this photo','اختر قطعة من الصورة'))}" aria-busy="${busy}"></button>${outline}${guide}${busy?`<div class="photo-search-status" role="status"><span class="search-spinner" aria-hidden="true"></span><span>${esc(searchCopy(item))}</span><span class="search-elapsed" aria-hidden="true">${elapsedLabel(item)}</span></div>`:''}`;
}
function feedbackMarkup(item){
 if(!item)return '';
 const busy=pieceBusy(item),saved=!!resultView(item),checked=item.phase==='complete'||item.status==='error',free=saved||originalLayer.has(searchKey(item));
 const caption=busy?searchCopy(item):item.error?(messages[item.error]||messages.SEARCH_FAILED):saved?translate('Saved store options · free to open','خيارات محفوظة · عرض مجاني'):item.status==='kept'?translate('Keep your own piece','الاحتفاظ بقطعتك الحالية'):checked?translate('No close matches yet','لم نعثر على نتائج قريبة من هذه القطعة.'):translate('Ready to find this piece','جاهز للبحث عن هذه القطعة');
 const action=free?'item':checked?'search-item':'start-piece';
 const button=free?translate('View options','عرض الخيارات'):translate('Find in stores','ابحث في المتاجر');
 return `<div class="piece-selection-card${busy?' is-searching':''}" data-ui-key="${esc(keyFor(item))}"><div class="piece-selection-summary"><img src="${esc(item.crop||selected().image)}" alt="${esc(item.name_en)}"><div><strong>${esc(item.name_en)}</strong><p role="status">${busy?'<span class="search-spinner" aria-hidden="true"></span>':''}${esc(caption)}${busy?` <span class="search-elapsed" aria-hidden="true">${elapsedLabel(item)}</span>`:''}</p></div>${!busy?`<button class="piece-clear" data-action="clear-piece" aria-label="${esc(translate('Clear selection','إلغاء التحديد'))}">${icon('close',true)}</button>`:''}</div>${busy?'<div class="piece-search-track" aria-hidden="true"><span></span></div>':`<button class="piece-search-button" data-action="${action}" data-id="${item.id}"><span>${esc(button)}</span><span>${free?icon('forward',true):esc(translate('1 credit','رصيد واحد'))}</span></button>`}</div>`;
}
function selectPiece(id,marker){
 const items=selected()?.items||[],item=items.find(x=>x.id===id);if(!item)return;
 const running=items.find(pieceBusy);
 if(running){if(running.id!==id)toast(translate('Your piece is being searched. Store options will open here.','جارٍ البحث عن القطعة. ستظهر خيارات المتاجر هنا.'));return;}
 if(sheetMode==='pieces')closeSheet();
 pointFocus={key:keyFor(item),id,marker:String(marker||pieceViews([item])[0]?.marker||id),waiting:false};renderShop();
 const card=sheetMode==='zoom'?$('[data-zoom-feedback]'):$('#piece-feedback');
 const bounds=card?.getBoundingClientRect();if(bounds&&bounds.bottom>(window.innerHeight||900)-16)card.scrollIntoView?.({block:'nearest',behavior:reduced?'auto':'smooth'});
}
function pickFromPhoto(event,button){
 if(event.detail===0)return browsePieces();
 const rect=button.getBoundingClientRect();if(!rect.width||!rect.height)return;
 const hit=pickPhotoPiece(selected()?.items||[],(event.clientX-rect.left)/rect.width*1000,(event.clientY-rect.top)/rect.height*1000);
 if(hit)selectPiece(hit.id,hit.marker);else toast(translate('Tap closer to a piece, or choose from All pieces.','اضغط بالقرب من القطعة، أو اخترها من «جميع القطع».'));
}
function browsePieces(){
 const items=selected()?.items||[];
 showSheet(`<div class="sheet-body"><h2>${esc(translate('Pieces in your room','قطع غرفتك'))}</h2><p class="pieces-note">${esc(translate('Choose a piece to see it in your room.','اختر قطعة لتحديد موقعها في الصورة.'))}</p><div class="piece-picker-list">${items.map(item=>`<button class="piece-picker-row" data-action="select-piece" data-id="${item.id}"><img src="${esc(item.crop||selected().image)}" alt="" loading="lazy"><span><strong>${esc(item.name_en)}</strong><small>${esc(pieceBusy(item)?searchCopy(item):resultView(item)?translate('Saved options','خيارات محفوظة'):translate('Select piece','اختيار القطعة'))}</small></span>${icon('forward',true)}</button>`).join('')}</div></div>`,'pieces');
}
function renderShop(){
 const d=selected();if(!d)return;
 $('#selected-title').textContent=d.title;
 updateImage($('#selected-image'),state.compare?state.job.original:d.image);
 $('#compare-label').textContent=state.compare?'After':'Before';$('[data-action="compare"]').setAttribute('aria-pressed',String(state.compare));$('#hotspots').classList.toggle('hidden',state.compare);
 const items=d.items||[],preparing=d.status==='analyzing',adapting=d.status==='adapting';
 const pending=items.find(pieceBusy);if(pending&&!items.some(x=>pointFocus?.key===keyFor(x)))pointFocus={key:keyFor(pending),id:pending.id,waiting:true};
 patchHTML($('.stage-hint'),`<span><strong>${esc(translate('Shop this room','تسوّق قطع التصميم'))}</strong><small>${esc(translate('Tap a piece to see store options','اضغط على أي قطعة لعرض خيارات المتاجر'))}</small></span><button class="browse-pieces" data-action="pieces" ${!items.length||preparing||adapting?'disabled':''}>${esc(translate('All pieces','جميع القطع'))}${icon('chevron',true)}</button>`);
 $('#shop-count').textContent='';$('#search-progress').classList.add('hidden');$('#summary-button').classList.add('hidden');$('#items-list').replaceChildren();
 $('#empty-items').classList.toggle('hidden',items.length>0&&!preparing&&!adapting);
 if(!items.length||preparing||adapting)$('#empty-items').innerHTML=d.error?`<p>${esc(messages[d.error]||'We couldn’t identify the pieces.')}</p><button class="secondary" data-action="choose" data-index="${state.design}">Try again</button>`:`<span class="search-spinner" aria-hidden="true"></span><p role="status">${esc(adapting?translate('Updating your design…','جارٍ تحديث تصميمك…'):translate('Finding the pieces in your room…','جارٍ تحديد القطع في غرفتك…'))}</p>`;
 patchHTML($('#hotspots'),photoMarkup(items));
 const zoom=$('[data-zoom-hotspots]');if(zoom)patchHTML(zoom,photoMarkup(items));
 const current=items.find(x=>pointFocus?.key===keyFor(x)),busy=pieceBusy(current);
 patchHTML($('#piece-feedback'),feedbackMarkup(current));renderDesignPicks();
 const zoomFeedback=$('[data-zoom-feedback]');if(zoomFeedback)patchHTML(zoomFeedback,feedbackMarkup(current));
 for(const item of items){const settled=keyFor(item)+':'+item.last_ui_request;if(item.last_ui_request&&item.status!=='searching'&&(item.phase==='complete'||item.status==='error')&&!pointSettled.has(settled)){pointSettled.add(settled);document.querySelector('.fz-home')?.fzBilling?.refresh(true);}}
 if(current&&pointFocus?.waiting&&!pointLaunches.has(keyFor(current))&&(current.alternatives?.length||current.offers?.length||!busy&&(current.phase==='complete'||current.status==='error'))){
  pointFocus.waiting=false;
  if(current.error&&/credits_|session_|sign_in|trial_/.test(current.error))document.querySelector('.fz-home')?.fzBilling?.notice(current.error);
  else renderItem(current);
 }
 if($('#sheet').open&&sheetMode==='item'&&state.itemId){const item=items.find(x=>x.id===state.itemId),newKey=JSON.stringify([state.job.id,state.design,d.status,d.adaptation_error,item,state.selections[keyFor(item||{id:state.itemId})]]);if(item&&$('#sheet-content').dataset.itemKey!==newKey)renderItem(item);}
 clearTimeout(pointTimer);if(items.some(pieceBusy)&&state.view==='shopping')pointTimer=setTimeout(()=>{if(state.view==='shopping')renderShop();},1000);
}
function showSheet(html,mode){
 if(mode==='item'){const item=selected().items.find(x=>x.id===state.itemId);if(item&&item.search_engine!=='findzia-original')html=html.replace(/<\/div>$/,localCatalog.markup(item)+'</div>');}
 else localCatalog.clear();
 const key=mode==='item'?`${state.job.id}:${state.design}:${state.itemId}`:mode;
 const preserve=$('#sheet').open&&sheetMode===mode&&$('#sheet-content').dataset.viewKey===key,top=$('#sheet').scrollTop;
 sheetMode=mode;
 if(preserve)patchHTML($('#sheet-content'),html);else $('#sheet-content').innerHTML=html;
 $('#sheet-content').dataset.viewKey=key;
 if(!$('#sheet').open){$('#sheet').showModal();}
 $('#sheet').scrollTop=preserve?top:0;
}
function closeSheet({cancelSearchFocus=true}={}){if(cancelSearchFocus&&pointFocus)pointFocus.waiting=false;localCatalog.clear();if($('#sheet').open)$('#sheet').close();sheetMode='';state.itemId=null;$('#sheet').style.transform='';}
function renderOriginalItem(item){
 const busy=item.status==='searching',adapting=selected().status==='adapting',rows=item.alternatives||[];
 $('#sheet-content').dataset.itemKey=JSON.stringify([state.job.id,state.design,selected().status,selected().adaptation_error,item,state.selections[keyFor(item)]]);
 const price=offer=>offer.price_at_store?translate('View price at store','السعر لدى المتجر'):(offer.price_estimated?'≈ ':'')+(offer.price_label||money(offer.price,offer.currency));
 const text=adapting?'Placing your piece in this room…':busy?(rows.length?'More store options are arriving…':'Searching with Findzia…'):item.status==='error'?'Couldn’t finish this search. Please try again.':rows.length?rows.length+' '+translate('store options','خيارات المتاجر'):'No close matches found. Try searching again.';
 showSheet(`<div class="sheet-body"><h2>${esc(item.name_en)}${item.quantity>1?` <span class="title-quantity">× ${item.quantity}</span>`:''}</h2><img class="preview-photo" src="${esc(item.crop)}" alt="${esc(item.name_en)}" style="border-radius:20px;max-height:240px"><p class="search-message${busy?' is-active':''}" role="status">${esc(translate(text,({'Searching with Findzia…':'جاري البحث مع Findzia…','More store options are arriving…':'جاري جلب المزيد من خيارات المتاجر…','No close matches found. Try searching again.':'ما لقينا خيارات قريبة من القطعة. جرّب البحث مرة ثانية.'})[text]))}</p>
 ${rows.map((offer,index)=>`<article class="replacement-card" data-ui-key="${esc(offer.link)}"><img src="${esc(safe(offer.image))}" alt="${esc(offer.title)}" loading="lazy"><div><h3>${esc(offer.title)}</h3><p class="merchant">${esc(offer.source)} · ${offer.market_scope==='local'?esc(country().en):'International'}</p><strong>${esc(price(offer))}</strong><div class="replacement-actions">${!state.job.demo&&offer.availability==='listed_available'?`<button class="primary" data-action="use-piece" data-id="${item.id}" data-index="${index}" ${busy||adapting?'disabled':''}>Use in my design</button>`:''}<a class="secondary" href="${esc(safe(offer.link))}" target="_blank" rel="noopener noreferrer">View at store ${icon('external',true)}</a></div></div></article>`).join('')}
 ${!busy&&!adapting&&!state.job.demo?`<button class="secondary wide" data-action="search-item" data-id="${item.id}">${esc(translate('Search again · 1 credit','بحث جديد · رصيد واحد'))}</button>`:''}</div>`,'item');
}
function renderItem(item){state.itemId=item.id;if(item.search_engine==='findzia-original')return renderOriginalItem(item);const o=chosen(item);$('#sheet-content').dataset.itemKey=JSON.stringify([state.job.id,state.design,selected().status,selected().adaptation_error,item,state.selections[keyFor(item)]]);if(!o){
 const busy=item.status==='searching',adapting=selected().status==='adapting';
 const orderKey=keyFor(item),order=optionOrder.get(orderKey)||[];for(const a of item.alternatives||[])if(!order.includes(a.link))order.push(a.link);optionOrder.set(orderKey,order);
 const alternatives=[...(item.alternatives||[])].filter(a=>a.availability!=='out_of_stock').sort((a,b)=>Number(b.market_scope==='local')-Number(a.market_scope==='local')||order.indexOf(a.link)-order.indexOf(b.link));
 showSheet(`<div class="sheet-body"><h2>${esc(item.name_en)}${item.quantity>1?` <span class="title-quantity">× ${item.quantity}</span>`:''}</h2><img class="preview-photo" src="${esc(item.crop||selected().image)}" alt="${esc(item.name_en)}" style="border-radius:20px;max-height:280px"><p class="search-message${busy||adapting?' is-active':''}" role="status">${adapting?'Placing your piece in this room…':item.status==='kept'?'You asked to keep this piece.':busy?pieceActivity(item)+'…':item.status==='error'?'Couldn’t finish this search. Please try again.':alternatives.length?(state.job.demo?'Real pieces at stores. Upload your room to use one.':'Real pieces for your room. Choose one to update the design.'):'We haven’t found this exact piece.'}</p>${selected().adaptation_error?`<p class="notice">${messages[selected().adaptation_error]||'We couldn’t place that piece accurately. Your design is unchanged.'}</p>`:''}
 ${alternatives.map((a,i)=>`<article class="replacement-card" data-ui-key="${esc(a.link)}"><img src="${esc(safe(a.image))}" alt="${esc(a.title)}"><div><h3>${esc(a.title)}</h3><p class="merchant">${esc(a.source)} · ${a.market_scope==='local'?country().en:'International'}</p><strong>${a.price!=null?esc(money(a.price,a.currency)):'Price at store'}</strong><p class="detail-note">${a.availability==='listed_available'?'Listed in stock':'Availability unconfirmed · check at store'}</p>${a.market_scope!=='local'?`<p class="detail-note">Confirm delivery to your address at store</p>`:''}<details class="replacement-differences"><summary>See differences ${icon('plus',true)}</summary><p class="detail-note">${esc((a.differences||[]).join(' · '))}</p></details><div class="replacement-actions">${!state.job.demo&&a.availability==='listed_available'?`<button class="primary" data-action="use-piece" data-id="${item.id}" data-index="${item.alternatives.findIndex(x=>x.link===a.link)}" ${adapting?'disabled':''}>${item.occurrences?.length>1?'Use for all '+item.occurrences.length:'Use in my design'}</button>`:''}<a class="secondary" href="${esc(safe(a.link))}" target="_blank" rel="noopener noreferrer">View at store ${icon('external',true)}</a></div></div></article>`).join('')}
 <details class="product-details"><summary>Piece details ${icon('plus',true)}</summary><p class="detail-note">${esc(item.description)}</p></details>${!['kept','searching','idle'].includes(item.status)&&!state.job.demo&&!adapting?`<button class="secondary wide" data-action="search-item" data-id="${item.id}">${esc(translate('Search again · 1 credit','بحث جديد · رصيد واحد'))}</button>`:''}</div>`,'item');state.itemId=item.id;return;}

 const specRows=[['Includes',o.purchase_unit||'Product shown — confirm store options'],['Colour',o.color||item.specs?.color||'See store photo'],['Material',o.material||item.specs?.material||'Confirm at store'],['Store size',o.dimensions||'Not listed'],['Room fit','Not verified — check measurements'],['Availability',o.availability==='out_of_stock'?'Out of stock':o.availability==='listed_available'?'Listed in stock':'Confirm at store'],['Market',o.market_scope==='local'?country().en:'International · check delivery'],['Price source',o.price==null?'Not published':o.evidence==='product_page'?'Store product page':'Search listing · confirm at store']];
 showSheet(`<div class="sheet-body"><h2>${esc(item.name_en)}${item.quantity>1?` <span class="title-quantity">× ${item.quantity}</span>`:''}</h2><div class="comparison"><figure><figcaption>In your design</figcaption><img src="${esc(item.crop)}" alt="Piece from your design"></figure><figure><figcaption>At the store</figcaption><img src="${esc(safe(o.image))}" alt="${esc(o.title)}"></figure></div>${item.offers.length>1?`<div class="offer-nav" aria-label="Matching store options">${item.offers.map((a,i)=>`<button class="offer-thumb${a.link===o.link?' active':''}" data-action="offer" data-id="${item.id}" data-index="${i}" aria-label="View option ${i+1} from ${esc(a.source)}" aria-pressed="${a.link===o.link}"><img src="${esc(safe(a.image))}" alt="${esc(a.title)}"></button>`).join('')}</div>`:''}<div class="offer-head"><div><h3>${esc(o.title)}</h3><p class="merchant">${esc(o.source)}${o.market_scope!=='local'?' · International':''}</p></div><strong>${esc(o.price!=null?money(o.price,o.currency):'Price at store')}</strong></div><p class="match-note">${icon('check',true)}Visually checked · confirm the size</p><p class="detail-note">${o.availability==='listed_available'?'Listed in stock':'Availability unconfirmed · check at store'}</p>${o.purchase_unit?`<p class="notice">${esc(o.purchase_unit)}</p>`:''}<details class="product-details"><summary>Details & measurements ${icon('plus',true)}</summary><ul class="spec-list">${specRows.map(([a,b])=>`<li><span>${a}</span><span>${esc(b)}</span></li>`).join('')}</ul><p class="detail-note">${esc(o.match_reason)}${item.mode!=='ready'?' Quantity and installation need measuring.':''}</p></details><div class="purchase-actions">${item.mode==='ready'?`<div class="quantity"><button data-action="quantity" data-id="${item.id}" data-delta="-1" aria-label="Reduce quantity">−</button><span>${qty(item)}</span><button data-action="quantity" data-id="${item.id}" data-delta="1" aria-label="Increase quantity">+</button></div>`:''}<a class="primary" href="${esc(safe(o.link))}" target="_blank" rel="noopener noreferrer">${o.availability==='out_of_stock'?'Check availability':'View at store'} ${icon('external',true)}</a></div></div>`,'item');state.itemId=item.id;
}
function countryCode(){return state.market;}
const originalLayer=createOriginalLayer({request:api,getLanguage:()=>shell?.getLanguage()||'en',
 onSaved:(key,view)=>{for(const [index,design] of (state.job?.designs||[]).entries()){const item=design.items?.find(x=>[state.job.id,index,x.id,view.lastSearch.country].join(':')===key);if(!item)continue;item.original_views={...item.original_views,[view.lastSearch.country]:view};item.original_view=view;item.original_saved_at=Date.now();if(state.job.demo){demoViews[key]={view,at:Date.now()};for(const old of Object.keys(demoViews).sort((a,b)=>demoViews[b].at-demoViews[a].at).slice(12))delete demoViews[old];try{localStorage.setItem('spaces-demo-views-v1',JSON.stringify(demoViews));}catch{}}if(state.design===index)renderShop();}},
 onPick:saveDesignPick,
 onStatus:(key,busy)=>{const item=selected()?.items.find(x=>searchKey(x)===key);if(item){if(busy&&!pointStarted.has(key))pointStarted.set(key,Date.now());renderShop();}},
 onClose:()=>{document.querySelector('#findzia-home-spaces')?.fzBilling?.refresh(true);renderShop();}
});
async function openItem(id,{retry=false}={}){
 const item=selected()?.items.find(x=>x.id===id);if(!item)return;
 closeSheet();pointFocus={key:keyFor(item),id,marker:pointFocus?.key===keyFor(item)?pointFocus.marker:undefined,waiting:false};
 await originalLayer.open({key:searchKey(item),name:item.name_en,crop:item.crop,market:countryCode(),room:state.job.id,design:state.design,item:item.id,
  readOnly:!!state.job.demo,newSearch:retry,view:retry?null:resultView(item),picks:picksFor(item)});renderShop();
}

function summary(){const t=total(),items=selected().items;showSheet(`<div class="sheet-body"><h2>Your shopping list</h2><div class="list-total">${t.count?esc(money(t.sum)):'No prices yet'}</div><p>${t.count} of ${t.items} pieces included in this total.</p><ul class="list-items">${items.map(x=>{const o=chosen(x);return `<li><span>${esc(x.name_en)}${x.mode==='ready'?' × '+qty(x):''}</span><span>${o?.price!=null?esc(money(o.price,o.currency)):x.mode==='keep'?'Keep':'—'}</span></li>`;}).join('')}</ul><p class="detail-note">Items without prices, international currencies, measured materials, custom work, delivery and installation are not included.</p><button class="primary wide" data-action="export">Save shopping list ${icon('download',true)}</button></div>`,'summary');}
async function demo(button){resetRoom();const token=roomContext.capture();if(button)button.disabled=true;try{const c=await api('/api/config');if(!roomContext.current(token))return;if(c.demo){const job=await api('/api/jobs/'+c.demo);if(!applyJob(job,token))return;renderKey='';view('designs');if(active())poll();}else{const r=await fetch('/hero.webp');await loadFile(new File([await r.blob()],'example.webp',{type:'image/webp'}));}}catch(e){toast(e.message);}finally{if(button)button.disabled=false;}}
function setMarket(id){if(!state.config.markets[id])return;marketChosen=true;if(state.market===id)return;localCatalog.clear();originalLayer.close();state.market=id;syncMarket();shell?.setMarketLanguage();if(state.view==='shopping')renderShop();}
function openMarket(){const language=shell?.getLanguage()||'en';const names=new Intl.DisplayNames([language],{type:'region'});showSheet(`<div class="sheet-body"><h2>Shop in</h2><p class="market-intro">${esc(translate('Your location first. Choose another market anytime.','بلدك أولًا. يمكنك تغيير بلد التسوّق متى شئت.'))}</p><div class="country-list">${orderedMarkets(state.config.markets,state.detectedMarket).map(([k,m])=>`<button class="country-choice${k===state.market?' selected':''}" data-action="set-market" data-id="${k}" aria-pressed="${k===state.market}"><span class="country-flag" aria-hidden="true">${m.flag}</span><span class="country-name" translate="no">${esc(m.name)}</span>${k===state.detectedMarket?'<span class="country-here" aria-hidden="true">'+icon('check',true)+'</span>':''}</button>`).join('')}</div><div class="market-preferences"><label>${esc(translate('Language','اللغة'))}<select id="spaces-language">${Object.entries(shell?.languages||{en:'English',ar:'العربية'}).map(([k,v])=>`<option value="${k}"${language===k?' selected':''}>${esc(v)}</option>`).join('')}</select></label><label>${esc(translate('Currency','العملة'))}<select aria-label="Currency" disabled><option>${esc(state.config.markets[state.market].currency)}</option></select></label><p>Currency follows the selected market.</p></div></div>`,'market');$('#spaces-language').addEventListener('change',e=>shell?.setLanguage(e.target.value));}
async function history(){resetRoom();const token=roomContext.capture();view('history');$('#history-list').innerHTML='<p>Loading your rooms…</p>';try{const data=await api('/api/jobs');if(!roomContext.current(token))return;$('#history-list').innerHTML=data.jobs.length?data.jobs.map(j=>`<button class="history-card" data-action="load-job" data-id="${j.id}"><img src="${esc(j.designs.find(d=>d.image)?.image||j.original)}" alt="${esc(j.room)}"><div><h3>${esc(j.room)}</h3><p>${new Date(j.created).toLocaleDateString('en-GB',{day:'numeric',month:'short'})}</p></div></button>`).join(''):'<div class="empty-items"><p>Your next room starts with a photo.</p><button class="primary" data-action="upload">Add your room</button></div>';}catch(e){$('#history-list').innerHTML=`<p>${esc(e.message)}</p>`;}}
function downloadBlob(blob,name){const a=document.createElement('a'),u=URL.createObjectURL(blob);a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1500);}
async function saveDesign(){try{const r=await fetch(selected().image);if(!r.ok)throw Error();const blob=await r.blob();downloadBlob(blob,'Findzia-'+selected().id+'.'+(blob.type.includes('jpeg')?'jpg':blob.type.includes('webp')?'webp':'png'));}catch{toast('The image couldn’t be saved. Please try again.');}}
function exportList(){const d=selected(),lines=['Findzia Spaces — '+d.title,'Market: '+country().en,''];for(const item of d.items){const o=chosen(item);lines.push(item.name_en+(item.mode==='ready'?' × '+qty(item):''),o?o.title:'No visually checked store match yet',o?(o.price!=null?money(o.price,o.currency):'Price at store'):'',o?.link||'',o?.dimensions?'Store measurements: '+o.dimensions:'Size must be checked','');}lines.push('Partial total: '+money(total().sum),'Only priced ready-made pieces in the selected currency are included. Confirm size, delivery, availability and price with each store.');downloadBlob(new Blob([lines.join('\n')],{type:'text/plain;charset=utf-8'}),'Findzia-shopping-list.txt');}
document.addEventListener('click',async e=>{const el=e.target.closest('[data-action]');if(!el||el.disabled||gestureDragged)return;const action=el.dataset.action,index=Number(el.dataset.index),id=el.dataset.id;try{switch(action){
 case 'home':resetRoom();view('home');break;
 case 'upload':$('#file-input').click();break;
 case 'camera':$('#camera-input').click();break;
 case 'demo':await demo(el);break;
 case 'market':openMarket();break;
 case 'set-market':setMarket(id);closeSheet();break;
 case 'local-stores':{const item=selected()?.items.find(x=>x.id===state.itemId);if(item)await localCatalog.load(item);break;}
 case 'designs':pointFocus=null;closeSheet();view('designs');break;
 case 'choose':await choose(index);break;
 case 'retry':el.disabled=true;if(await changeJob('/retry',{design:index})){renderKey='';renderDesigns();poll();}break;
 case 'preview':showSheet(`<img class="preview-photo" src="${esc(state.job.designs[index].image)}" alt="${esc(state.job.designs[index].title)}"><div class="preview-actions"><button class="primary wide" data-action="choose" data-index="${index}">Explore this design ${icon('forward')}</button></div>`,'preview');break;
 case 'original':showSheet(`<img class="preview-photo" src="${esc(state.job.original)}" alt="Original room"><div class="preview-actions"><h3>Your original room</h3></div>`,'preview');break;
 case 'zoom':showSheet(`<div class="design-canvas zoom-canvas"><img src="${esc(selected().image)}" alt="Selected room design"><div data-zoom-hotspots></div></div><div class="zoom-feedback" data-zoom-feedback></div><div class="preview-actions"><button class="browse-pieces" data-action="pieces">${esc(translate('All pieces','جميع القطع'))} ${icon('chevron',true)}</button></div>`,'zoom');renderShop();break;
 case 'compare':state.compare=!state.compare;renderShop();break;
 case 'photo-pick':pickFromPhoto(e,el);break;
 case 'pieces':browsePieces();break;
 case 'select-piece':selectPiece(id);break;
 case 'clear-piece':pointFocus=null;renderShop();break;
 case 'start-piece':await openItem(id);break;
 case 'item':openItem(id);break;
 case 'remove-pick':{const item=selected().items.find(x=>x.id===id),product=item&&picksFor(item)[index];if(!product)break;el.disabled=true;try{await saveDesignPick({key:keyFor(item),room:state.job.id,design:state.design,item:id,readOnly:!!state.job.demo},product,true);}finally{el.disabled=false;}break;}
 case 'offer':{const item=selected().items.find(x=>x.id===id);state.selections[keyFor(item)]=item.offers[index].link;persistSelection();shopKey='';renderShop();renderItem(item);break;}
 case 'quantity':{const item=selected().items.find(x=>x.id===id);state.quantities[keyFor(item)]=Math.max(1,Math.min(20,qty(item)+Number(el.dataset.delta)));persistSelection();renderItem(item);shopKey='';renderShop();break;}
 case 'search-item':{el.disabled=true;await openItem(id,{retry:true});break;}
 case 'use-piece':{const item=selected().items.find(x=>x.id===id),offer=item?.alternatives?.[index];if(!offer)break;const previousStatus=selected().status;el.disabled=true;selected().status='adapting';selected().adaptation_error=null;renderItem(item);try{if(await changeJob('/replace',{design:state.design,item:id,offer:offer.link})){shopKey='';renderShop();poll();}}catch(e){selected().status=previousStatus;renderItem(item);throw e;}break;}
 case 'history':closeSheet();await history();break;
 case 'load-job':{resetRoom();const token=roomContext.capture(),job=await api('/api/jobs/'+id);if(applyJob(job,token)){renderKey='';view('designs');if(active())poll();}break;}
 case 'room-menu':showSheet(`<div class="sheet-body"><h2>Your design</h2><div class="menu-list"><button data-action="download">${icon('download')}Save image</button><button data-action="summary">${icon('folder')}Shopping list</button><button data-action="home">${icon('plus')}Start a new room</button></div></div>`,'menu');break;
 case 'download':await saveDesign();break;
 case 'summary':summary();break;
 case 'export':exportList();break;
 case 'close':closeSheet();break;
 }}catch(err){if(el)el.disabled=false;toast(err.message);}});
$('#sheet').addEventListener('click',e=>{if(e.target===$('#sheet')){const b=e.target.getBoundingClientRect();if(e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom)closeSheet();}});
$('#sheet').addEventListener('cancel',()=>{if(pointFocus)pointFocus.waiting=false;});
$('#sheet').addEventListener('close',()=>{if(!$('#sheet').open){sheetMode='';state.itemId=null;localCatalog.clear();}});
// Gentle release feedback; native scrolling and reduced-motion preferences stay intact.
if(!reduced){document.addEventListener('pointerup',e=>{const el=e.target.closest('button:not(.photo-pick-target):not(.hotspot):not(.hero-photo):not(.example-button)');if(el&&!el.disabled&&!gestureDragged)el.animate([{transform:'scale(.98)'},{transform:'scale(1)'}],{duration:200,easing:'ease-out'});});}
let dragStart=null;const handle=$('.sheet-handle');handle.addEventListener('pointerdown',e=>{dragStart={y:e.clientY,t:performance.now()};handle.setPointerCapture(e.pointerId);});handle.addEventListener('pointermove',e=>{if(dragStart){const y=Math.max(0,e.clientY-dragStart.y);$('#sheet').style.transform=`translateY(${y}px)`;}});handle.addEventListener('pointerup',e=>{if(!dragStart)return;const y=e.clientY-dragStart.y,v=y/(performance.now()-dragStart.t);dragStart=null;if(y>90||y>30&&v>.5)closeSheet();else{$('#sheet').style.transform='';if(!reduced)$('#sheet').animate([{transform:`translateY(${Math.max(0,y)}px)`},{transform:'translateY(-7px)',offset:.6},{transform:'translateY(0)'}],{duration:380,easing:'ease-out'});}});
let carouselDrag=null;$('#design-grid').addEventListener('pointerdown',e=>{if(e.pointerType!=='mouse')return;carouselDrag={x:e.clientX,scroll:$('#design-grid').scrollLeft};gestureDragged=false;});$('#design-grid').addEventListener('pointermove',e=>{if(!carouselDrag)return;const dx=e.clientX-carouselDrag.x;if(Math.abs(dx)>8){gestureDragged=true;$('#design-grid').scrollLeft=carouselDrag.scroll-dx;}});document.addEventListener('pointerup',()=>{carouselDrag=null;setTimeout(()=>gestureDragged=false,50);});
new ResizeObserver(()=>{if(state.view==='shopping')renderShop();}).observe($('#design-canvas'));
document.addEventListener('load',event=>{if(state.view==='shopping'&&(event.target.id==='selected-image'||event.target.matches?.('.zoom-canvas>img')))renderShop();},true);
// Only room coordinates are retained across account navigation. Session tokens
// stay exclusively with the original account's same-origin session storage.
document.addEventListener('spaces:account-navigation',()=>{
 try{sessionStorage.setItem('spaces-account-room',JSON.stringify({job:state.job?.id,design:state.design,view:state.view,market:state.market,at:Date.now()}));}catch{}
});
init().then(async allowed=>{
 if(!allowed)return;
 let saved;try{saved=JSON.parse(sessionStorage.getItem('spaces-account-room'));sessionStorage.removeItem('spaces-account-room');}catch{}
 if(!saved||Date.now()-saved.at>86400000||!state.config.markets[saved.market])return;
 state.market=saved.market;marketChosen=true;syncMarket();shell?.setMarketLanguage();
 if(!/^[a-f0-9]{24}$/.test(saved.job||''))return;
 try{const token=roomContext.capture(),job=await api('/api/jobs/'+saved.job);if(!applyJob(job,token))return;state.design=Math.max(0,Math.min(job.designs.length-1,Number(saved.design)||0));view(saved.view==='shopping'?'shopping':'designs');if(active())poll();}catch{toast('Your room is no longer available.');}
});


mountFindzia({getMarket:()=>state.market,getMarkets:()=>state.config.markets,setMarket,openMarket,openDesigns:history,home:()=>{resetRoom();view('home');},notice:toast}).then(value=>{shell=value;syncMarket();shell.setMarketLanguage();}).catch(()=>toast('Couldn’t load the menu. Please refresh.'));

document.addEventListener('spaces:locale',()=>{if(state.view==='shopping')renderShop();originalLayer.refreshLanguage?.();});
