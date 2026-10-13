// The frame runs findzia.com's current page, including the original photo
// entry point, wallet, media checks, cards, groups and sorting. No offer adapter.
import {productKey,hasSavedResults,savedPickImage} from './design-picks.js';
import {reviewSimilarCards} from './similar-review.js';
import {bindAccountNavigation,openAccountModal} from './account-navigation.js';
import {searchBudget,SEARCH_BUDGET_MS} from './search-budget.js';
export function createOriginalLayer({request,getLanguage,onSaved,onStatus,onClose,onPick}){
 const sessions=new Map();let current=null,returnFocus=null;
 const layer=document.createElement('dialog');layer.className='original-results-layer';layer.setAttribute('aria-label','Findzia results');
 const bar=document.createElement('div');bar.className='original-results-bar';
 const back=document.createElement('button');back.type='button';back.className='original-results-back';
 const title=document.createElement('span');title.className='original-results-title';
 const status=document.createElement('span');status.className='original-results-status';status.setAttribute('role','status');
 const progress=document.createElement('div');progress.className='original-results-progress';progress.setAttribute('role','progressbar');progress.setAttribute('aria-valuemin','0');progress.setAttribute('aria-valuemax','100');
 const fill=document.createElement('span');progress.append(fill);
 const percent=document.createElement('small');percent.className='original-results-percent';percent.setAttribute('aria-hidden','true');
 const thumbnail=document.createElement('img');thumbnail.className='original-results-thumb';thumbnail.alt='';
 const subtitle=document.createElement('small');subtitle.className='original-results-subtitle';
 const heading=document.createElement('div');heading.className='original-results-heading';heading.append(subtitle,title);
 const tools=document.createElement('div');tools.className='original-results-tools';tools.append(status,percent,progress);
 const body=document.createElement('div');body.className='original-results-body';
 const waiting=document.createElement('div');waiting.className='original-results-waiting';waiting.setAttribute('aria-hidden','true');
 waiting.innerHTML='<span class="search-spinner"></span><span class="results-skeletons"><i></i><i></i></span>';body.append(waiting);
 bar.append(thumbnail,heading,back);layer.append(bar,tools,body);document.body.append(layer);
 const text=(en,ar)=>globalThis.window?.FindziaI18n?.t(en,ar,document.querySelector('#findzia-home-spaces'))||(getLanguage()==='ar'?ar:en);
 function resultsOnly(session){
  // The full page's decorative home scene and wait screen do not belong in a
  // results-only frame. Both expose teardown APIs; leave the search engine alone.
  const root=session.root;if(!root)return;
  root.fzStoreScene?.destroy();root.fzSearchWait?.destroy();
  delete root.dataset.waitActive;delete root.dataset.waitExiting;
  const theme=document.documentElement.dataset.findziaTheme||document.querySelector('#findzia-home-spaces')?.dataset.theme||'light';
  if(root.dataset.theme!==theme)session.frame.contentWindow.FindziaAppearance?.apply(root,{theme,source:'spaces'});
 }
 function syncLanguage(session){
  const select=session.root?.querySelector('[data-profile-language-select]');if(!select)return;
  const lang=getLanguage();if(select.value!==lang){select.value=lang;select.dispatchEvent(new session.frame.contentWindow.Event('change',{bubbles:true}));}
  session.frame.contentDocument.documentElement.lang=lang;
  // Some original releases do not yet offer Dutch in the hidden selector.
  session.frame.contentWindow.FindziaI18n?.set(session.root,lang);
 } 
 function paint(session){
  if(current!==session)return;
  layer.dir=['ar','ur'].includes(getLanguage())?'rtl':'ltr';
  if(thumbnail.getAttribute('src')!==session.crop)thumbnail.src=session.crop;subtitle.textContent=text('Store options','خيارات المتاجر');
  if(!back.firstChild)back.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg>';
  back.setAttribute('aria-label',text('Done','تم'));title.textContent=session.name;
  const searching=!!(session.busy||session.loading);
  const visible=session.root?.querySelector('[data-results-body] .fz-card-shell:not([data-spaces-visual="held"])');
  waiting.hidden=!!visible||!!session.error||!searching;
  status.textContent=searching?text('Searching…','جارٍ البحث…'):!visible?(session.error||''):'';
  status.setAttribute('aria-busy',String(searching));
  const value=searching?(session.budget?Math.min(99,Math.floor((Date.now()-session.started)/SEARCH_BUDGET_MS*100)):0):100;
  progress.setAttribute('aria-label',text('Search progress','تقدّم البحث'));
  progress.setAttribute('aria-valuenow',String(value));
  progress.setAttribute('aria-valuetext',searching?text('Searching','جارٍ البحث…'):text('Finished','اكتمل البحث'));
  fill.style.width=value+'%';percent.textContent=searching&&session.budget?value+'%':'';
  tools.classList.toggle('is-searching',searching);tools.classList.toggle('is-complete',!searching);
  tools.classList.toggle('has-error',!searching&&!visible&&!!session.error);

 }
 function close(){if(!layer.open)return;save(current);layer.close();returnFocus?.focus?.({preventScroll:true});onClose?.();}
 back.addEventListener('click',close);layer.addEventListener('cancel',event=>{event.preventDefault();close();});

 function context(session){return session.root?.fzRefineBridge?.context();}
 async function save(session){
  if(!session||session.saving||session.busy||session.loading||!session.completed||!session.root)return;
  const bridge=session.root.fzRefineBridge,view=bridge.snapshot()?.view;
  if(!hasSavedResults(view,session.market)||!session.root.querySelector('[data-save-product]'))return;
  // The full original snapshot retains classification and image audit fields.
  // Drop the crop bytes: they are already held by the owned room.
  const clean={...view,lastSearch:{...view.lastSearch,image_base64:undefined}};
  const value=JSON.stringify(clean);if(value===session.saved)return;
  session.saving=true;
  try{if(!session.readOnly)await request(session.path,{method:'POST',body:JSON.stringify({design:session.design,view:clean})});session.saved=value;session.view=clean;onSaved?.(session.key,clean);}
  catch{session.saveFailed=true;}finally{session.saving=false;}
 }
 function watch(session){
  if(!session.root)return;
  resultsOnly(session);
  // Loading a late product photo is not an active search. The native stream
  // can already be finished/stopped while media_pending remains true.
  const c=context(session),busy=!session.budget?.expired&&!!(session.launching||c?.busy||session.root.dataset.searchLaunching==='true');
  if(session.busy!==busy){session.busy=busy;onStatus?.(session.key,busy);if(!busy){save(session);document.querySelector('#findzia-home-spaces')?.fzBilling?.refresh(true);}}
  syncPicks(session);paint(session);
 }
 function syncPicks(session){
  if(!session.root)return;
  const review=reviewSimilarCards(session.root,session.root.fzRefineBridge.snapshot()?.view?.items||[]);
  if(session.reviewNote){
   const visible=session.root.querySelector('[data-results-body] .fz-card-shell:not([data-spaces-visual="held"])');
   const show=review.held>0&&!visible&&!session.busy&&!session.loading;
   session.reviewNote.hidden=!show;
   const message=text('No close similar matches were confirmed for this piece.','لم نجد منتجات مشابهة بدرجة كافية لعرضها.');
   if(session.reviewNote.textContent!==message)session.reviewNote.textContent=message;
  }
  const chosen=new Set((session.picks||[]).map(x=>productKey(x.url)));
  for(const button of session.root?.querySelectorAll('[data-save-product]')||[]){
   const active=chosen.has(productKey(button.dataset.saveProduct)),label=active?text('Remove from this design','إزالة من هذا التصميم'):text('Save to this design','حفظ ضمن هذا التصميم');
   button.setAttribute('aria-pressed',String(active));button.setAttribute('aria-label',label);button.title=label;
   if(!button.querySelector('[data-design-check]'))button.innerHTML='<svg data-design-check viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/></svg>';
  }
 }
 function bindPicks(session){
  const root=session.root;
  root.addEventListener('click',async event=>{
   const button=event.target.closest?.('[data-save-product]');if(!button||!root.contains(button))return;
   // Redirect only the bookmark's destination. Search, card rendering and
   // product details continue to run entirely in the original page.
   event.preventDefault();event.stopImmediatePropagation();if(button.disabled||!onPick)return;
   const card=button.closest('.fz-card-shell'),url=card?.querySelector('a.fz-tile')?.href;if(!url)return;
   const snapshot=root.fzRefineBridge.snapshot(),row=snapshot.view.items.find(x=>productKey(x.url)===productKey(url)),img=card.querySelector('.fz-tile-media img');
   const product={url,title:row?.title||img?.alt||session.name,store:card.querySelector('.fz-tile-store')?.textContent||row?.store||'',
    image:savedPickImage({url,image:img?.currentSrc||img?.src||''},snapshot.view.items),price:card.querySelector('.fz-tile-price')?.innerText||card.querySelector('.fz-tile-price')?.textContent||'',flag:card.querySelector('.fz-inline-flag')?.textContent||''};
   const remove=(session.picks||[]).some(x=>productKey(x.url)===productKey(url));button.disabled=true;
   try{session.picks=await onPick(session,product,remove);syncPicks(session);session.notice.textContent=remove?text('Removed from this design','تمت الإزالة من هذا التصميم'):text('Saved below your room photo','تم الحفظ أسفل صورة غرفتك');}
   catch{session.notice.textContent=text('Could not save. Please try again.','تعذّر الحفظ. أعد المحاولة.');}
   finally{button.disabled=false;clearTimeout(session.noticeTimer);session.noticeTimer=setTimeout(()=>session.notice.textContent='',3500);}
  },true);
  session.notice=root.querySelector('[data-save-notice]');
  if(!session.notice){session.notice=root.ownerDocument.createElement('div');session.notice.setAttribute('role','status');root.append(session.notice);}
  session.reviewNote=root.ownerDocument.createElement('p');session.reviewNote.className='spaces-similar-note';session.reviewNote.hidden=true;session.reviewNote.setAttribute('role','status');root.querySelector('.fz-container')?.append(session.reviewNote);
  const Observer=session.frame.contentWindow.MutationObserver;
  if(Observer){session.pickObserver=new Observer(()=>syncPicks(session));session.pickObserver.observe(root.querySelector('[data-results-body]')||root,{childList:true,subtree:true});}
  syncPicks(session);
 }
 function beginBudget(session){
  session.budget?.cancel();clearInterval(session.progressTimer);
  session.budget=searchBudget(()=>{
   session.loading=false;session.launching=false;session.busy=false;
   // Native restore cancels its launch and request controllers, increments its
   // generation, and retains the real verified photo states. No second request.
   const bridge=session.root?.fzRefineBridge,snapshot=bridge?.snapshot();
   if(snapshot?.view){bridge.restore(snapshot);bridge.revealSearchResults?.();session.root.fzSearchProgress?.stop();session.completed=hasSavedResults(snapshot.view,session.market);}
   const visible=session.root?.querySelector('[data-results-body] .fz-card-shell:not([data-spaces-visual="held"])');
   clearInterval(session.progressTimer);session.error=visible?'':text('No close matches found.','لم نعثر على نتائج قريبة من هذه القطعة.');
   onStatus?.(session.key,false);paint(session);save(session);
  });
  session.started=session.budget.started;
  session.progressTimer=setInterval(()=>paint(session),200);
 }
 async function run(session,reuseBudget=false){
  if(session.loading||session.busy)return;
  if(reuseBudget&&session.budget?.expired)return;
  if(!reuseBudget||!session.budget)beginBudget(session);
  const budget=session.budget;
  session.error='';session.completed=false;session.legacy=false;session.launching=true;session.busy=true;session.startedSearch=true;paint(session);onStatus?.(session.key,true);
  try{
   const response=await fetch(session.crop,{credentials:'same-origin',cache:'no-store',signal:budget.signal});if(!response.ok)throw Error('Photo unavailable');
   const blob=await response.blob(),win=session.frame.contentWindow;
   if(budget.expired||budget.signal.aborted)return;
   // The same function used by the original camera/file picker authorizes and
   // charges the one request. Spaces never calls authorizePiece or /focus here.
   const file=new win.File([blob],'room-piece.jpg',{type:blob.type||'image/jpeg'});
   const result=await session.root.fzRefineBridge.searchPhoto(file);
   if(session.budget!==budget||budget.expired)return;
   session.completed=result!==false;
   if(result===false&&!context(session)?.busy)session.startedSearch=!!context(session)?.kind&&context(session).kind==='image';
  }catch{if(session.budget===budget&&!budget.expired)session.error=text('Could not finish. Try again.','لم يكتمل البحث. أعد المحاولة.');}
  finally{if(session.budget===budget){budget.finish();clearInterval(session.progressTimer);session.launching=false;watch(session);save(session);}}
 }
 async function ready(session){
  const start=Date.now();
  while(Date.now()-start<SEARCH_BUDGET_MS&&!session.budget?.expired){
   const root=session.frame.contentDocument?.querySelector('.fz-home');
   if(root?.fzRefineBridge?.searchPhoto&&root.fzBilling&&root.fzAccount){session.root=root;break;}
   await new Promise(resolve=>setTimeout(resolve,100));
  }
  if(session.budget?.expired)return;
  if(!session.root)throw Error('Original page unavailable');
  const win=session.frame.contentWindow,root=session.root;
  bindAccountNavigation(root,view=>{close();openAccountModal(view);});
  const beforeSearch=win.FindziaBeforeSearch;
  if(beforeSearch)win.FindziaBeforeSearch=async(...args)=>{
   const budget=session.budget;
   if(budget?.expired)return false;
   const allowed=await beforeSearch(...args);
   // A slow credit check must not launch a paid search after our deadline.
   return allowed&&session.budget===budget&&!budget?.expired;
  };
  const market=root.querySelector('[data-profile-market-select]');if(!market)throw Error('Market unavailable');
  market.value=session.market;market.dispatchEvent(new win.Event('change',{bubbles:true}));
  syncLanguage(session);resultsOnly(session);
  session.frame.dataset.ready='true';
  if(context(session).country!==session.market)throw Error('Market unavailable');
  // Warm the EXISTING wallet before displaying the original account controls.
  // This shares same-origin storage, never sends credentials through messages.
  session.loading=false;
  bindPicks(session);
  for(const type of ['fz:search-state','fz:result-count','fz:media-state','fz:usage'])root.addEventListener(type,()=>{watch(session);});
  session.timer=setInterval(()=>{watch(session);save(session);},1500);
  if(hasSavedResults(session.view,session.market)){
   session.loading=true;paint(session);
   const response=await fetch(session.crop,{credentials:'same-origin'});
   if(!response.ok)throw Error('Photo unavailable');
   const blob=await response.blob();
   const encoded=await new Promise((resolve,reject)=>{const reader=new win.FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=reject;reader.readAsDataURL(blob);});
   const view={...session.view,lastSearch:{...session.view.lastSearch,image_base64:encoded,mime_type:blob.type||'image/jpeg'}};
   root.dataset.homeState='results';root.fzRefineBridge.restore({view,photos:new Map()});
   root.fzRefineBridge.revealSearchResults?.();
   // Restore the original media state using its own validator; no new search
   // or credit is involved. Never fabricate a Saved search from legacy rows.
   if(root.fzRefineBridge.prepare){
    const prepared=await root.fzRefineBridge.prepare(view.items,new AbortController().signal);
    if(Array.isArray(prepared)&&!prepared.length)session.error=text('Saved photos are unavailable. No new search was started.','صور البحث المحفوظ غير متاحة. لم يبدأ بحث جديد.');
   }
   session.loading=false;session.completed=true;syncPicks(session);watch(session);
  }else await run(session,true);
 }
 async function open({key,name,crop,market,room,design,item,view,picks=[],newSearch=false,readOnly=false}){
  returnFocus=document.activeElement;
  let session=sessions.get(key);
  if(session?.error&&!session.root){session.frame.remove();sessions.delete(key);session=null;}
  const existing=!!session;
  if(!session){
   const frame=document.createElement('iframe');frame.title='Findzia — '+name;frame.className='original-results-frame';frame.allow='payment';
   session={key,name,crop,market,room,design,item,view,picks,readOnly,frame,loading:true,busy:false,started:Date.now(),path:'/api/jobs/'+room+'/results/'+item};sessions.set(key,session);
   if(!hasSavedResults(view,market))beginBudget(session);
   frame.addEventListener('load',()=>ready(session).catch(()=>{session.budget?.finish();clearInterval(session.progressTimer);session.loading=false;session.error=text('Could not open Findzia. Close and try again.','تعذّر فتح النتائج. أغلق النافذة وأعد المحاولة.');paint(session);} ),{once:true});
   frame.src='/api/findzia-results';body.append(frame);
  }
  session.picks=picks;if(session.root){syncLanguage(session);resultsOnly(session);syncPicks(session);}
  current=session;for(const other of sessions.values())other.frame.hidden=other!==session;
  paint(session);if(!layer.open){layer.showModal();}back.focus({preventScroll:true});
  if(existing&&newSearch&&!session.busy&&!session.loading)await run(session);
 }
 return {open,close,refreshLanguage(){for(const session of sessions.values())if(session.root)syncLanguage(session);if(current)paint(current);},has:key=>sessions.has(key),busy:key=>sessions.get(key)?.busy===true,
  destroy(){close();for(const session of sessions.values()){session.budget?.cancel();clearInterval(session.progressTimer);clearInterval(session.timer);clearTimeout(session.noticeTimer);session.pickObserver?.disconnect();session.frame.remove();}sessions.clear();layer.remove();}};
}
