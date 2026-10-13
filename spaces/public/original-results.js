// The frame runs findzia.com's current page, including the original photo
// entry point, wallet, media checks, cards, groups and sorting. No offer adapter.
import {productKey,hasSavedResults} from './design-picks.js';
import {reviewSimilarCards} from './similar-review.js';
export function createOriginalLayer({request,getLanguage,onSaved,onStatus,onClose,onPick}){
 const sessions=new Map();let current=null,returnFocus=null;
 const layer=document.createElement('dialog');layer.className='original-results-layer';layer.setAttribute('aria-label','Findzia results');
 const bar=document.createElement('div');bar.className='original-results-bar';
 const back=document.createElement('button');back.type='button';back.className='original-results-back';
 const title=document.createElement('span');title.className='original-results-title';
 const status=document.createElement('span');status.className='original-results-status';status.setAttribute('role','status');
 const retry=document.createElement('button');retry.type='button';retry.className='original-results-retry';retry.hidden=true;
 const body=document.createElement('div');body.className='original-results-body';
 bar.append(back,title,status,retry);layer.append(bar,body);document.body.append(layer);
 const text=(en,ar)=>getLanguage()==='ar'?ar:en;
 function paint(session){
  if(current!==session)return;
  back.textContent='×';back.setAttribute('aria-label',text('Close results','إغلاق النتائج'));title.textContent=session.name;
  retry.textContent=text('Search again · 1 credit','بحث جديد · كردت واحد');retry.hidden=session.busy||session.loading;
  const elapsed=Math.max(0,Math.floor((Date.now()-session.started)/1000));
  status.classList.toggle('is-searching',session.busy||session.loading);
  status.textContent=session.loading?text('Opening Findzia…','جاري فتح Findzia…'):session.busy?text('Searching… ','جاري البحث… ')+elapsed+text('s',' ث'):session.error||session.legacy?session.error||text('Saved search','بحث محفوظ'):'';
 }
 function close(){if(!layer.open)return;save(current);layer.close();document.body.style.overflow='';returnFocus?.focus?.({preventScroll:true});onClose?.();}
 back.addEventListener('click',close);layer.addEventListener('cancel',event=>{event.preventDefault();close();});
 retry.addEventListener('click',()=>{if(current&&!current.busy&&!current.loading)run(current);});
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
  const c=context(session),busy=!!(session.launching||c?.busy||c?.media_pending||session.root.dataset.searchLaunching);
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
   const message=text('No close similar matches were confirmed for this piece.','ما تأكدنا من وجود منتجات مشابهة وقريبة لهالقطعة.');
   if(session.reviewNote.textContent!==message)session.reviewNote.textContent=message;
  }
  const chosen=new Set((session.picks||[]).map(x=>productKey(x.url)));
  for(const button of session.root?.querySelectorAll('[data-save-product]')||[]){
   const active=chosen.has(productKey(button.dataset.saveProduct)),label=active?text('Remove from this design','إزالة من هالتصميم'):text('Save to this design','احفظ لهالتصميم');
   button.setAttribute('aria-pressed',String(active));button.setAttribute('aria-label',label);button.title=label;
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
    image:img?.currentSrc||img?.src||'',price:card.querySelector('.fz-tile-price')?.innerText||card.querySelector('.fz-tile-price')?.textContent||'',flag:card.querySelector('.fz-inline-flag')?.textContent||''};
   const remove=(session.picks||[]).some(x=>productKey(x.url)===productKey(url));button.disabled=true;
   try{session.picks=await onPick(session,product,remove);syncPicks(session);session.notice.textContent=remove?text('Removed from this design','تمت الإزالة من هالتصميم'):text('Saved below your room photo','انحفظ تحت صورة غرفتك');}
   catch{session.notice.textContent=text('Could not save. Please try again.','تعذّر الحفظ. حاول مرة ثانية.');}
   finally{button.disabled=false;clearTimeout(session.noticeTimer);session.noticeTimer=setTimeout(()=>session.notice.textContent='',3500);}
  },true);
  session.notice=root.querySelector('[data-save-notice]');
  if(!session.notice){session.notice=root.ownerDocument.createElement('div');session.notice.setAttribute('role','status');root.append(session.notice);}
  session.reviewNote=root.ownerDocument.createElement('p');session.reviewNote.className='spaces-similar-note';session.reviewNote.hidden=true;session.reviewNote.setAttribute('role','status');root.querySelector('.fz-container')?.append(session.reviewNote);
  const Observer=session.frame.contentWindow.MutationObserver;
  if(Observer){session.pickObserver=new Observer(()=>syncPicks(session));session.pickObserver.observe(root.querySelector('[data-results-body]')||root,{childList:true,subtree:true});}
  syncPicks(session);
 }
 async function run(session){
  if(session.loading||session.busy)return;
  session.error='';session.completed=false;session.legacy=false;session.launching=true;session.busy=true;session.started=Date.now();session.startedSearch=true;paint(session);onStatus?.(session.key,true);
  try{
   const response=await fetch(session.crop,{credentials:'same-origin',cache:'no-store'});if(!response.ok)throw Error('Photo unavailable');
   const blob=await response.blob(),win=session.frame.contentWindow;
   // The same function used by the original camera/file picker authorizes and
   // charges the one request. Spaces never calls authorizePiece or /focus here.
   const file=new win.File([blob],'room-piece.jpg',{type:blob.type||'image/jpeg'});
   const result=await session.root.fzRefineBridge.searchPhoto(file);session.completed=result!==false;
   if(result===false&&!context(session)?.busy)session.startedSearch=!!context(session)?.kind&&context(session).kind==='image';
  }catch{session.error=text('Could not finish. Try again.','تعذّر إكمال البحث. حاول مرة ثانية.');}
  finally{session.launching=false;watch(session);save(session);}
 }
 async function ready(session){
  const start=Date.now();
  while(Date.now()-start<25000){
   const root=session.frame.contentDocument?.querySelector('.fz-home');
   if(root?.fzRefineBridge?.searchPhoto&&root.fzBilling&&root.fzAccount){session.root=root;break;}
   await new Promise(resolve=>setTimeout(resolve,100));
  }
  if(!session.root)throw Error('Original page unavailable');
  const win=session.frame.contentWindow,root=session.root;
  const market=root.querySelector('[data-profile-market-select]');if(!market)throw Error('Market unavailable');
  market.value=session.market;market.dispatchEvent(new win.Event('change',{bubbles:true}));
  const lang=root.querySelector('[data-profile-language-select]');if(lang){lang.value=getLanguage();lang.dispatchEvent(new win.Event('change',{bubbles:true}));}
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
   if(root.fzRefineBridge.prepare)await root.fzRefineBridge.prepare(view.items,new AbortController().signal);
   session.loading=false;syncPicks(session);watch(session);
  }else await run(session);
 }
 async function open({key,name,crop,market,room,design,item,view,picks=[],newSearch=false,readOnly=false}){
  returnFocus=document.activeElement;
  let session=sessions.get(key);
  if(session?.error&&!session.root){session.frame.remove();sessions.delete(key);session=null;}
  const existing=!!session;
  if(!session){
   const frame=document.createElement('iframe');frame.title='Findzia — '+name;frame.className='original-results-frame';frame.allow='payment';
   session={key,name,crop,market,room,design,item,view,picks,readOnly,frame,loading:true,busy:false,started:Date.now(),path:'/api/jobs/'+room+'/results/'+item};sessions.set(key,session);
   frame.addEventListener('load',()=>ready(session).catch(()=>{session.loading=false;session.error=text('Could not open Findzia. Close and try again.','تعذّر فتح Findzia. سكّر الطبقة وحاول مجددًا.');paint(session);} ),{once:true});
   frame.src='/api/findzia-results';body.append(frame);
  }
  session.picks=picks;if(session.root)syncPicks(session);
  current=session;for(const other of sessions.values())other.frame.hidden=other!==session;
  paint(session);if(!layer.open){layer.showModal();document.body.style.overflow='hidden';}back.focus({preventScroll:true});
  if(existing&&newSearch&&!session.busy&&!session.loading)await run(session);
 }
 return {open,close,has:key=>sessions.has(key),busy:key=>sessions.get(key)?.busy===true,
  destroy(){close();for(const session of sessions.values()){clearInterval(session.timer);clearTimeout(session.noticeTimer);session.pickObserver?.disconnect();session.frame.remove();}sessions.clear();layer.remove();}};
}
