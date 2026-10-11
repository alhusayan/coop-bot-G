/* Findzia usage funnel v1. No queries, images, account IDs or error messages. */
(() => {
  'use strict';
  if (window.FindziaAnalytics) return;
  const root = document.querySelector('.fz-home');
  const traffic = window.FindziaTraffic || {internal:false};
  let measurementId = '', stopped = false, queue = [], active = null, timer;
  const diagnostics = [];
  const currentURL = new URL(location.href);
  const pagePath=['/','/index.html','/pages/findzia','/policies/privacy-policy','/policies/terms-of-service','/policies/refund-policy'].includes(location.pathname.replace(/\/$/, '')||'/') ? location.pathname : '/404.html';
  const safeURL = new URL(location.origin + pagePath);
  // Preserve campaign attribution while excluding search text and arbitrary URLs.
  for (const key of ['gclid','gbraid','wbraid','utm_source','utm_medium','utm_campaign','utm_id','utm_content']) {
    const value = currentURL.searchParams.get(key);
    if (value && value.length <= 200 && /^[\p{L}\p{N}_.~+ -]+$/u.test(value)) safeURL.searchParams.set(key,value);
  }
  let referrer = '';
  try { referrer = new URL(document.referrer).origin + '/'; } catch (_) {}
  const source = ['gclid','gbraid','wbraid'].some(k=>currentURL.searchParams.has(k)) ? 'google_ads'
    : currentURL.searchParams.has('utm_source') ? 'campaign' : referrer && referrer !== location.origin+'/' ? 'referral' : 'direct';
  function theme() { return root?.dataset.theme === 'dark' ? 'dark' : 'light'; }
  function context() { try { return root?.fzRefineBridge?.context() || {}; } catch (_) { return {}; } }
  function common() {
    return {theme:theme(), ui_language:/^[a-z]{2}(-[A-Za-z]{2})?$/.test(root?.dataset.lang||'')?root.dataset.lang:'en',
      visit_source:source, traffic_type:traffic.internal?'internal':'external',
      page_location:safeURL.href, page_referrer:referrer, page_title:document.title};
  }
  function deliver(event) {
    try { window.gtag('event',event.name,{...event.params,send_to:measurementId}); } catch (_) {}
  }
  function emit(name, params={}) {
    try {
      const event = {name,params:{...common(),...params}};
      // Diagnostics contain the same minimal payload and are bounded in memory.
      diagnostics.push(event); if(diagnostics.length>40)diagnostics.shift();
      if(traffic.internal || stopped)return;
      if(measurementId)deliver(event);
      else if(queue.length<60)queue.push(event);
    } catch (_) { /* Analytics must never affect search or navigation. */ }
  }
  function searchParams(search) {
    return {search_method:search.method,search_mode:search.mode,
      result_count:search.count,duration_ms:Math.max(0,Math.round(performance.now()-search.started))};
  }
  function cancel(reason) {
    if(active && !active.finished) {
      active.finished=true;
      emit('fz_search_cancel',{...searchParams(active),cancel_reason:reason});
    }
  }
  function reconcile() {
    const search=active, state=context();
    if(!search || search.finished || state.generation!==search.generation)return;
    if(!search.received || state.busy || state.media_pending)return;
    search.finished=true;
    emit('fz_search_complete',{...searchParams(search),search_outcome:search.partial?'partial':search.count?'results':'empty'});
  }
  function schedule() { clearTimeout(timer); timer=setTimeout(reconcile,100); }
  function usage(event) {
    const d=event.detail || {};
    if(d.type==='start') {
      if(active?.generation===d.generation)return;
      cancel('new_search');
      active={generation:d.generation,method:d.method==='image'?'image':'text',mode:d.mode==='refinement'?'refinement':'initial',
        started:performance.now(),count:0,received:false,finished:false,visible:false,partial:false};
      emit('fz_search_start',searchParams(active));
    } else if(d.type==='blocked') {
      emit('fz_search_blocked',{search_method:d.method==='image'?'image':'text',error_type:d.code==='credits_exhausted'?'credits_exhausted':'credits_unavailable'});
    } else if(d.type==='reset') { cancel('new_search'); }
    else if(active && d.generation===active.generation) {
      if(d.type==='received') { active.received=true; active.partial=!!d.partial; schedule(); }
      if(d.type==='failure' && !active.finished) {
        active.finished=true;
        const allowed=['timeout','cancelled','credits_exhausted','credits_unavailable','rate_limit','auth','network','stream_interrupted','request_failed'];
        const code=allowed.includes(d.code)?d.code:'request_failed';
        if(code==='cancelled')emit('fz_search_cancel',{...searchParams(active),cancel_reason:'cancelled'});
        else emit('fz_search_error',{...searchParams(active),error_type:code});
      }
      if(d.type==='visible' && !active.visible) {
        active.visible=true;
        active.count=Math.max(0,Math.min(1000,Number(d.count)||0));
        if(active.count)emit('fz_results_view',searchParams(active));
      }
      if(d.type==='count' && !active.finished) {
        active.count=Math.max(0,Math.min(1000,Number(d.count)||0));
        schedule();
      }
    }
  }
  document.addEventListener('fz:usage',event=>{try{usage(event);}catch(_){}});
  let typed=false, lastTheme=theme();
  if(root) {
    root.addEventListener('input',event=>{
      if(!event.isTrusted || typed || !event.target.matches('[data-dark-input],[id^="fz-query-"]') || !event.target.value.trim())return;
      typed=true;emit('fz_search_input');
    });
    // Capture the real lens action, not the mirrored click from the home dock.
    root.addEventListener('click',event=>{
      if(event.isTrusted && event.target.closest('[data-dark-photo],[data-photo-btn]'))emit('fz_lens_click');
    },true);
    root.addEventListener('change',event=>{
      if(event.isTrusted && event.target.matches('input[type="file"]') && event.target.files?.length)emit('fz_photo_selected');
    },true);
    for(const name of ['fz:search-state','fz:media-state'])root.addEventListener(name,schedule);
    new MutationObserver(()=>{
      const next=theme();if(next!==lastTheme){lastTheme=next;emit('fz_theme_change');}
    }).observe(root,{attributes:true,attributeFilter:['data-theme']});
  }
  function productClick(event) {
    if(!event.isTrusted || event.defaultPrevented || (event.type==='click'?event.button!==0:event.button!==1))return;
    const anchor=event.target.closest?.('a.fz-tile,a.fz-quick-card,a.fz-saved-link,a.fz-insights-cta');
    if(!anchor)return;
    try {
      const url=new URL(anchor.href,location.href);
      if(!/^https?:$/.test(url.protocol) || url.origin===location.origin || url.hostname==='findzia.com' || url.hostname.endsWith('.findzia.com'))return;
      emit('fz_product_click',{search_method:active?.method||'none',product_surface:anchor.matches('.fz-saved-link')?'saved':anchor.matches('.fz-quick-card')?'recommendation':'results'});
    }catch(_){}
  }
  document.addEventListener('click',productClick);
  document.addEventListener('auxclick',productClick);
  window.addEventListener('pagehide',()=>cancel('page_exit'));
  window.FindziaAnalytics = {version:1,internal:traffic.internal,diagnostics:()=>diagnostics.map(x=>({name:x.name,params:{...x.params}}))};
  emit('page_view'); if(root)emit('fz_visit');
  if(traffic.internal){stopped=true;queue=[];return;}
  // Runtime setting lets deployment precede GA account provisioning safely.
  const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),4000);
  fetch('/analytics-config.json',{credentials:'omit',signal:controller.signal,cache:'no-store'})
    .then(response=>response.ok?response.json():null)
    .then(config=>{
      if(!/^G-[A-Z0-9]{5,20}$/.test(config?.measurement_id||'')){stopped=true;queue=[];return;}
      measurementId=config.measurement_id;
      window.dataLayer=window.dataLayer||[];
      window.gtag=window.gtag||function(){window.dataLayer.push(arguments);};
      window.gtag('config',measurementId,{send_page_view:false,allow_google_signals:false,allow_ad_personalization_signals:false,...common()});
      for(const event of queue)deliver(event);queue=[];
    }).catch(()=>{stopped=true;queue=[];}).finally(()=>clearTimeout(timeout));
})();
