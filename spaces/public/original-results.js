// The frame runs findzia.com's current page, including the original photo
// entry point, wallet, media checks, cards, groups and sorting. No offer adapter.
export function createOriginalLayer({request,getLanguage,onSaved,onStatus,onClose}){
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
 function close(){if(!layer.open)return;layer.close();document.body.style.overflow='';returnFocus?.focus?.({preventScroll:true});onClose?.();}
 back.addEventListener('click',close);layer.addEventListener('cancel',event=>{event.preventDefault();close();});
 retry.addEventListener('click',()=>{if(current&&!current.busy&&!current.loading)run(current);});
 function context(session){return session.root?.fzRefineBridge?.context();}
 async function save(session){
  if(session.saving||!session.startedSearch||!session.root)return;
  const bridge=session.root.fzRefineBridge,view=bridge.snapshot()?.view;
  if(!view||view.lastSearch?.country!==session.market)return;
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
  paint(session);
 }
 async function run(session){
  if(session.loading||session.busy)return;
  session.error='';session.legacy=false;session.launching=true;session.busy=true;session.started=Date.now();session.startedSearch=true;paint(session);onStatus?.(session.key,true);
  try{
   const response=await fetch(session.crop,{credentials:'same-origin',cache:'no-store'});if(!response.ok)throw Error('Photo unavailable');
   const blob=await response.blob(),win=session.frame.contentWindow;
   // The same function used by the original camera/file picker authorizes and
   // charges the one request. Spaces never calls authorizePiece or /focus here.
   const file=new win.File([blob],'room-piece.jpg',{type:blob.type||'image/jpeg'});
   const result=await session.root.fzRefineBridge.searchPhoto(file);
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
  for(const type of ['fz:search-state','fz:result-count','fz:media-state','fz:usage'])root.addEventListener(type,()=>{watch(session);});
  session.timer=setInterval(()=>{watch(session);save(session);},1500);
  if(session.view){
   const response=await fetch(session.crop,{credentials:'same-origin'});
   if(!response.ok)throw Error('Photo unavailable');
   const blob=await response.blob();
   const encoded=await new Promise((resolve,reject)=>{const reader=new win.FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=reject;reader.readAsDataURL(blob);});
   const view={...session.view,lastSearch:{...session.view.lastSearch,image_base64:encoded,mime_type:blob.type||'image/jpeg'}};
   root.dataset.homeState='results';root.fzRefineBridge.restore({view,photos:new Map()});
   root.fzRefineBridge.revealSearchResults?.();paint(session);
  }else await run(session);
 }
 async function open({key,name,crop,market,room,design,item,view,legacy=false,newSearch=false,readOnly=false}){
  returnFocus=document.activeElement;
  let session=sessions.get(key);
  if(session?.error&&!session.root){session.frame.remove();sessions.delete(key);session=null;}
  const existing=!!session;
  if(!session){
   const frame=document.createElement('iframe');frame.title='Findzia — '+name;frame.className='original-results-frame';frame.allow='payment';
   session={key,name,crop,market,design,view,legacy,readOnly,frame,loading:true,busy:false,started:Date.now(),path:'/api/jobs/'+room+'/results/'+item};sessions.set(key,session);
   frame.addEventListener('load',()=>ready(session).catch(()=>{session.loading=false;session.error=text('Could not open Findzia. Close and try again.','تعذّر فتح Findzia. سكّر الطبقة وحاول مجددًا.');paint(session);} ),{once:true});
   frame.src='/api/findzia-results';body.append(frame);
  }
  current=session;for(const other of sessions.values())other.frame.hidden=other!==session;
  paint(session);if(!layer.open){layer.showModal();document.body.style.overflow='hidden';}back.focus({preventScroll:true});
  if(existing&&newSearch&&!session.busy&&!session.loading)await run(session);
 }
 return {open,close,has:key=>sessions.has(key),busy:key=>sessions.get(key)?.busy===true,
  destroy(){close();for(const session of sessions.values()){clearInterval(session.timer);session.frame.remove();}sessions.clear();layer.remove();}};
}
