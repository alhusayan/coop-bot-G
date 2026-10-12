// This view owns a single live response. It never saves catalog data in history,
// localStorage, room jobs or the visual matching/replacement pipeline.
export function createLocalCatalog({request,escape,safe,money,translate,context,icon}){
 let token=0,controller=null,key='',status='idle',items=[];
 function clear(){token++;controller?.abort();controller=null;key='';items=[];status='idle';}
 function markup(item){
  if(item.mode==='keep'||item.status==='kept')return '';
  const next=context(item);if(key&&key!==next.key)clear();
  return `<section class="shopify-discovery" data-local-catalog><h3>${escape(translate('Local store options','خيارات من متاجر محلية'))}</h3><p class="detail-note">${escape(translate('Compare these pieces with your design.','قارن هالقطع مع تصميمك.'))} · ${escape(next.marketName)}</p><div data-catalog-results>${results()}</div></section>`;
 }
 function results(){
  if(status==='loading')return `<p class="catalog-status" role="status">${escape(translate('Loading local stores…','جاري تحميل المتاجر المحلية…'))}</p>`;
  if(status==='ready')return items.length?items.map(o=>`<article class="replacement-card catalog-card"><a href="${escape(safe(o.link))}" target="_blank" rel="noopener noreferrer"><img src="${escape(safe(o.image))}" alt="${escape(o.title)}" loading="lazy" referrerpolicy="no-referrer"></a><div><h3 translate="no">${escape(o.title)}</h3><p class="merchant" translate="no">${escape(o.source)}</p><strong>${escape(money(o.price,o.currency))}</strong><div class="replacement-actions"><a class="secondary" href="${escape(safe(o.link))}" target="_blank" rel="noopener noreferrer">${escape(translate('View at store','افتح المتجر'))} ${icon('external',true)}</a></div></div></article>`).join(''):`<p class="catalog-status" role="status">${escape(translate('No local store options found.','ما لقينا خيارات من متاجر محلية.'))}</p>`;
  return `${status==='error'?`<p class="catalog-status" role="status">${escape(translate('Couldn’t load local stores. Try again.','تعذّر تحميل المتاجر المحلية. حاول مرة ثانية.'))}</p>`:''}<button class="secondary wide" data-action="local-stores">${escape(translate('Shop local stores','تسوّق المتاجر المحلية'))}</button>`;
 }
 function paint(){const target=document.querySelector('[data-catalog-results]');if(target)target.innerHTML=results();}
 async function load(item){
  if(status==='loading')return;const ctx=context(item);clear();key=ctx.key;const current=++token;controller=new AbortController();status='loading';paint();
  try{const response=await request(ctx.url,{signal:controller.signal,cache:'no-store'});if(!response.ok)throw Error();const data=await response.json();if(current!==token)return;
   // A late response from another room or market must never paint this sheet.
   if(context(item).key!==key)return clear();
   if(data.market!==ctx.market||data.status!=='ok')throw Error();
   items=(data.items||[]).filter(o=>o.merchant_country===ctx.market&&o.destination_country===ctx.market&&o.market_scope==='local');status='ready';
  }catch(e){if(current!==token)return;items=[];status='error';}finally{if(current===token){controller=null;paint();}}
 }
 return {clear,markup,load};
}
