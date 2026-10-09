/* FINDZIA_WAIT_RELEASE=1.0.0 — public search presentation; retrieval stays unchanged. */
(() => {
  'use strict';
  const el=(tag,cls)=>{const node=document.createElement(tag);node.className=cls;return node;};
  function mount(root){
    const bridge=root.fzRefineBridge,shared=window.FindziaChoice,body=root.querySelector('[data-results-body]');
    if(root.dataset.choicePreview==='true'||root.fzSearchWait||!bridge?.searchWaitRows||!shared||!body)return;
    const box=el('section','fz-one fz-search-wait'),stage=el('div','fz-one-stage');
    box.hidden=true;box.dataset.state='pending';box.setAttribute('data-no-i18n','');
    const aura=el('div','fz-one-aura'),placeholder=el('span','fz-one-image-placeholder');
    placeholder.textContent='⌕';placeholder.setAttribute('aria-hidden','true');
    const image=el('img','fz-one-image');image.hidden=true;image.alt='';
    const shade=el('div','fz-one-shade'),scan=el('div','fz-one-scan');scan.setAttribute('aria-hidden','true');
    const heading=el('h2','fz-one-heading');heading.setAttribute('role','status');
    const details=el('div','fz-one-details'),price=el('div','fz-one-price');price.setAttribute('role','img');
    const source=el('p','fz-one-price-source'),logBox=el('div','fz-one-log'),caption=el('div','fz-one-log-caption'),lines=el('div','fz-one-log-lines');
    lines.setAttribute('aria-hidden','true');logBox.append(caption,lines);details.append(price,source,logBox);
    stage.append(aura,placeholder,image,shade,scan,heading,details);
    const actions=el('div','fz-one-actions'),cancel=el('button','fz-one-small');cancel.type='button';actions.append(cancel);
    box.append(stage,actions);body.before(box);
    const log=new shared.SearchLog(lines),reels=new shared.PriceReels(price,row=>{
      source.textContent=row?.store||'';log.highlight(row?.url||'');
    });
    const header=root.querySelector('.fz-fixed-header');
    let generation=null,handedOff=false,frozen='',frame=0,disposed=false;
    const text=(en,ar)=>window.FindziaI18n?.t(en,ar,root)||(root.dataset.lang==='ar'?ar:en);
    function fit(){
      if(box.hidden||disposed)return;
      const viewport=window.visualViewport;
      const height=viewport?.height||innerHeight;
      const top=Math.max(header?.getBoundingClientRect().bottom||0,box.getBoundingClientRect().top-(viewport?.offsetTop||0));
      // Include iPhone safe-area padding as well as the cancel action.
      const rest=box.getBoundingClientRect().height-stage.getBoundingClientRect().height+8;
      const room=Math.max(250,Math.min(820,height-top-rest));
      box.style.setProperty('--one-image-height',room+'px');
      stage.style.setProperty('--scan-travel',Math.max(120,room*.66)+'px');
    }
    function hide(){box.hidden=true;delete root.dataset.waitActive;reels.cancel();}
    function reset(){
      hide();reels.clear();log.clear();source.textContent='';frozen='';image.removeAttribute('src');image.hidden=true;placeholder.hidden=false;handedOff=false;
    }
    function freeze(rows,c){
      if(frozen)return;
      const original=c.kind==='image'&&c.image_base64;
      let url=original?'data:'+(c.mime_type||'image/jpeg')+';base64,'+original.replace(/^data:[^,]+,/,''):'';
      // Uploaded photos remain the reference throughout a photo search.
      if(!url&&c.kind!=='image')url=rows.find(row=>row.image)?.image||'';
      if(!url||(!original&&!/^https?:\/\//i.test(url)))return;
      frozen=url;image.src=url;image.hidden=false;placeholder.hidden=true;
    }
    function update(){
      frame=0;if(disposed)return;
      const c=bridge.context();
      if(generation!==c.generation){reset();generation=c.generation;}
      if(c.can_refine){handedOff=true;hide();return;}
      const results=(root.dataset.pageTarget||root.dataset.homeState)==='results';
      if(handedOff||!results||!(c.busy||c.media_pending||root.dataset.searchLaunching==='true')){hide();return;}
      box.hidden=false;root.dataset.waitActive='true';
      heading.textContent=text('Searching stores…','جارٍ البحث في المتاجر…');
      caption.textContent=text('Checking product prices…','جارٍ التحقق من أسعار المنتجات…');
      cancel.textContent=text('New search','بحث جديد');
      const rows=bridge.searchWaitRows();
      freeze(rows,c);log.sync(rows);reels.spin(rows,caption.textContent);fit();
    }
    function queue(){if(!frame&&!disposed)frame=requestAnimationFrame(update);}
    function progress(event){
      // Sync generation before adding a status, so the first event isn't erased.
      update();
      if(!box.hidden&&event.detail?.event==='status'){
        const stage=String(event.detail.stage||'search').slice(0,60);
        log.add('stage:'+stage,{site:'findzia',title:heading.textContent});
      }
      queue();
    }
    function cancelSearch(){bridge.resetSearchSession();reset();queue();}
    cancel.addEventListener('click',cancelSearch);
    image.addEventListener('error',()=>{image.hidden=true;placeholder.hidden=false;});
    const events=['fz:search-state','fz:search-reset','fz:result-count'];
    events.forEach(name=>root.addEventListener(name,queue));
    root.addEventListener('fz:search-progress',progress);
    const observer=new MutationObserver(queue);
    observer.observe(root,{attributes:true,attributeFilter:['data-home-state','data-page-target','data-search-launching','data-lang']});
    const sizeObserver=window.ResizeObserver?new ResizeObserver(fit):null;
    if(header)sizeObserver?.observe(header);sizeObserver?.observe(actions);
    window.addEventListener('resize',fit);window.visualViewport?.addEventListener('resize',fit);
    function destroy(){
      disposed=true;cancelAnimationFrame(frame);reset();observer.disconnect();sizeObserver?.disconnect();
      events.forEach(name=>root.removeEventListener(name,queue));root.removeEventListener('fz:search-progress',progress);
      window.removeEventListener('resize',fit);window.visualViewport?.removeEventListener('resize',fit);box.remove();delete root.fzSearchWait;
    }
    document.addEventListener('shopify:section:unload',function unload(event){if(event.target?.contains(root)){destroy();document.removeEventListener('shopify:section:unload',unload);}});
    root.fzSearchWait={destroy,release:'1.0.0'};queue();
  }
  const start=()=>document.querySelectorAll('.fz-home').forEach(mount);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
  document.addEventListener('shopify:section:load',start);
})();
