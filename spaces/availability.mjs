// Stock belongs to the selected product/variant, independently of its gallery image.
export const STOCK_VERSION=1;
export const STOCK_TTL=10*60*1000;
const decode=s=>String(s||'').replace(/&quot;/g,'"').replace(/&#39;|&apos;/g,"'").replace(/&nbsp;|&#160;/g,' ').replace(/&amp;/g,'&');
const plain=s=>decode(s).replace(/<[^>]*>/g,' ').replace(/[\u064b-\u065f\u0670]/g,'').replace(/[أإآ]/g,'ا').replace(/\s+/g,' ').trim();
export function stockValue(value){
 const s=plain(typeof value==='object'?value?.['@id']||value?.code||value?.stockLevelStatus||'':value).toLowerCase().replace(/^https?:\/\/schema.org\//,'').replace(/[\s_-]+/g,'');
 if(/^(outofstock|soldout|discontinued|unavailable|نفدالمخزون|نفذالمخزون|غيرمتوفر|انتهىمنالمخزن|انتهىمنالمخزون|نفذمنالمخزون)$/.test(s))return 'out_of_stock';
 if(/^(instock|limitedavailability|available|متوفر|متوفرالمخزون)$/.test(s))return 'listed_available';
 return 'unknown';
}
const attrs=tag=>Object.fromEntries([...tag.matchAll(/([\w:-]+)\s*=\s*["']([^"']*)["']/g)].map(x=>[x[1].toLowerCase(),decode(x[2])]));
const sameURL=(a,b)=>{try{const x=new URL(a,b),y=new URL(b);return x.hostname===y.hostname&&x.pathname.replace(/\/$/,'')===y.pathname.replace(/\/$/,'')&&x.search===y.search;}catch{return false;}};
function combine(values){const known=values.filter(x=>x!=='unknown');return known.length&&known.every(x=>x===known[0])?known[0]:'unknown';}
export function availabilityFromPage(html,url){
 const products=[],states=[];
 const sku=new URL(url).pathname.match(/\/(?:p|dp|item|products)\/([^/]+)\/?$/)?.[1];
 function walk(v,ld=false,depth=0){
   if(!v||typeof v!=='object'||depth>30)return;
   if(Array.isArray(v)){v.forEach(x=>walk(x,ld,depth+1));return;}
   const types=[v['@type']].flat();
   if(types.includes('Product'))products.push(v);
   if(sku&&[v.code,v.sku,v.productId,v.id].some(x=>String(x||'')===sku))states.push(v);
   // Exclude reviews/recommendations from unscoped schema selection.
   if(ld){if(v['@graph'])walk(v['@graph'],true,depth+1);if(v.mainEntity)walk(v.mainEntity,true,depth+1);if(types.includes('ProductGroup'))walk(v.hasVariant,true,depth+1);}
   else for(const [k,x] of Object.entries(v))if(!/recommend|related|translation|messages|review/i.test(k))walk(x,false,depth+1);
 }
 for(const m of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)){
   const a=attrs(m[1]);if(!/application\/(?:ld\+)?json/i.test(a.type||''))continue;
   try{walk(JSON.parse(m[2]),a.type.toLowerCase()==='application/ld+json');}catch{}
 }
 const matched=products.filter(p=>sameURL(p.url||p['@id'],url)||sku&&String(p.sku||p.productID||'')===sku);
 const selected=matched.length===1?matched[0]:products.length===1?products[0]:null;
 let schema='unknown';
 if(selected){
   const offers=[selected.offers||[]].flat();const exact=offers.filter(o=>o.url&&sameURL(o.url,url));
   schema=combine((exact.length?exact:offers).map(o=>stockValue(o.availability)));
 }
 const stateValues=states.flatMap(p=>[stockValue(p.stock?.stockLevelStatus||p.stockLevelStatus||p.availability),typeof p.inStock==='boolean'?(p.inStock?'listed_available':'out_of_stock'):'unknown']);
 const hydrated=combine(stateValues);
 // Actual purchase controls only: never scan translation bundles or arbitrary page prose.
 const body=html.replace(/<(script|style|template|noscript)\b[^>]*>[\s\S]*?<\/\1>/gi,'');
 const controls=[];
 for(const m of body.matchAll(/<(button|a)\b([^>]*)>([\s\S]*?)<\/\1>/gi)){
   const a=attrs(m[2]);if(/\bhidden\b|display\s*:\s*none|visibility\s*:\s*hidden/i.test(m[2])||a['aria-hidden']==='true')continue;
   const label=plain(m[3]);if(label.length>90)continue;
   controls.push({value:stockValue(label),buy:/^(?:add to (?:cart|bag|basket)|buy now|اضف (?:الى |ل)?(?:السلة|سلة التسوق))$/i.test(label),disabled:/\bdisabled\b/.test(m[2])||a['aria-disabled']==='true'});
 }
 const sold=controls.some(x=>x.value==='out_of_stock'),buy=controls.some(x=>x.buy&&!x.disabled);
 if(sold&&!buy)return {availability:'out_of_stock',stock_evidence:'purchase_control'};
 if(hydrated!=='unknown')return {availability:hydrated,stock_evidence:'product_state'};
 if(schema!=='unknown')return {availability:schema,stock_evidence:'product_schema'};
 for(const m of body.matchAll(/<(?:meta|link)\b[^>]*>/gi)){
   const a=attrs(m[0]);if(!/^(?:product:availability|availability)$/i.test(a.property||a.itemprop||''))continue;
   const value=stockValue(a.content||a.href);if(value!=='unknown')return {availability:value,stock_evidence:'product_meta'};
 }
 if(buy&&!sold)return {availability:'listed_available',stock_evidence:'purchase_control'};
 return {availability:'unknown',stock_evidence:'unconfirmed'};
}
export function stockFresh(offer,now=Date.now()){return offer.stock_version===STOCK_VERSION&&now-Date.parse(offer.stock_checked_at||'')<STOCK_TTL;}
