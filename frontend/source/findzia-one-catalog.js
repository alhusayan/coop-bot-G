/* One-only, live Shopify evidence. No persistence, proxies or image audits. */
(() => {
  'use strict';
  const safe=value=>{try{const u=new URL(value);return u.protocol==='https:'&&!u.username&&!u.password?u.href:'';}catch(_){return '';}};
  function mount(root){
    const bridge=root.fzRefineBridge;
    if(root.dataset.choicePreview!=='true'||!bridge?.choiceRows||root.fzOneCatalog)return;
    const originalRows=bridge.choiceRows,originalLogs=bridge.choiceLogRows;
    let generation=-1,rows=[];
    const sync=()=>{const current=bridge.context().generation;if(current!==generation){generation=current;rows=[];}};
    const merge=primary=>{
      sync();const urls=new Set(primary.map(r=>r.url)),catalog=rows.filter(r=>!urls.has(r.url)).slice(0,18);
      // Retain the native image authorization when both sources share a URL.
      return [...primary.slice(0,48-catalog.length),...catalog];
    };
    bridge.choiceRows=()=>merge(originalRows.call(bridge));
    bridge.choiceLogRows=()=>merge(originalLogs?.call(bridge)||originalRows.call(bridge));
    const reset=()=>{rows=[];generation=-1;};
    const progress=event=>{
      sync();const data=event.detail;
      if(data?.event!=='catalog'||data.source!=='shopify_catalog')return;
      rows=(Array.isArray(data.items)?data.items:[]).filter(r=>r.source==='shopify_catalog'&&
        r.cacheable===false&&r.evaluation_token&&safe(r.url)&&safe(r.image)&&
        ['local','global'].includes(r.market_scope)&&r.market_country&&Number(r.price_amount)>0)
        .map(r=>({token:r.evaluation_token,url:safe(r.url),title:r.title,store:r.store,
          country:r.market_country,market_scope:r.market_scope,image:safe(r.image),
          source:'shopify_catalog',cacheable:false,money:{amount:Number(r.price_amount),currency:r.currency},
          key_specs:r.key_specs||[],match_type:r.match_type}));
      root.dispatchEvent(new CustomEvent('fz:choice-results'));
    };
    root.addEventListener('fz:search-progress',progress);
    root.addEventListener('fz:search-reset',reset);
    root.addEventListener('fz:search-state',sync);
    root.fzOneCatalog={destroy(){reset();bridge.choiceRows=originalRows;bridge.choiceLogRows=originalLogs;
      root.removeEventListener('fz:search-progress',progress);root.removeEventListener('fz:search-reset',reset);
      root.removeEventListener('fz:search-state',sync);delete root.fzOneCatalog;}};
    document.addEventListener('shopify:section:unload',function unload(e){if(e.target?.contains(root)){
      root.fzOneCatalog?.destroy();document.removeEventListener('shopify:section:unload',unload);}});
  }
  const start=()=>document.querySelectorAll('.fz-home').forEach(mount);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
  document.addEventListener('shopify:section:load',start);
})();
