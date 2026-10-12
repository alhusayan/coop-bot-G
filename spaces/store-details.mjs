import {safePage,productFromPage} from './engine.mjs';
import {availabilityFromPage} from './availability.mjs';
import {dimensionDetails,dimensionLabel,usableSize} from './dimensions.mjs';
import {productURL,plain} from './product-data.mjs';
import {sourceScope} from './sourcing.mjs';

// Serper's public webpage endpoint; request format verified against its published playground.
// https://serper.dev/playground (webpage: url, includeMarkdown, includeImages).
const pending=new Map(),cache=new Map();
const norm=s=>plain(s).toLowerCase().replace(/[^\p{L}\p{N}]+/gu,' ').trim();
function scopedText(text){return text.split(/(?:\n#{1,6}\s*(?:you may also|recommended|related products|recently viewed|customers also|similar products)|\n(?:Related products|You may also like)\s*\n)/i)[0].slice(0,45000);}
export function detailsFromScrape(data,offer){
 const text=scopedText(String(data.markdown||data.text||''));
 if(!text||/captcha|verify you are human|access denied|sign in to continue/i.test(text.slice(0,1500)))return null;
 const meta=data.metadata||{},url=meta.canonical||meta.canonicalUrl||meta['og:url']||data.url;
 if(url&&productURL(url,offer.link)!==productURL(offer.link))return null;
 // A requested option needs variant evidence; a generic page title cannot establish its size.
 const requested=new URL(offer.link).searchParams.get('variant');
 const sku=offer.sku||new URL(offer.link).pathname.match(/\/(?:p|dp|item|itm)\/([^/]+)\/?$/i)?.[1];
 const title=String(meta.title||data.title||text.match(/^#\s+(.+)$/m)?.[1]||'');
 const words=norm(offer.title).split(' ').filter(w=>w.length>2&&!/^(shop|buy|online|with|the|and|homecentre|kuwait|saudi|arabia|ksa)$/.test(w));
 const titleMatch=words.length>=3&&words.filter(w=>norm(title).split(' ').includes(w)).length/words.length>=.75;
 const skuMatch=sku&&new RegExp('(?:^|[^a-z0-9])'+String(sku).replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'(?:$|[^a-z0-9])','i').test(text);
 if(requested||!skuMatch&&!titleMatch)return null;
 const rows=[];
 for(const line of text.split('\n')){
  const table=line.match(/^\s*\|\s*([^|]{1,100})\s*\|\s*([^|]{1,300})\s*\|?\s*$/);
  const label=line.match(/^\s*(?:[-*]\s*)?(?:\*\*)?((?:Overall |Product |Item )?(?:Width|Depth|Length|Height|Diameter|Dimensions|Size|ASIN|SKU)(?:\s*\([^)]*\))?)(?:\*\*)?\s*:\s*(.{1,250})$/i);
  if(table||label){const m=table||label;rows.push({label:m[1].replaceAll('**','').trim(),value:m[2].replaceAll('**','').trim(),source:'store_page_extraction'});}
 }
 const facts=dimensionDetails('',{name:offer.title},offer.link,{rows,texts:[text.replace(/\|/g,' ')],selected:null,schema:null,variantUnconfirmed:false});
 const labels=text.split('\n').map(x=>plain(x.replace(/[*#]/g,'')).replace(/^\[([^\]]+)\]\([^)]*\)$/,'$1'));
 const sold=labels.some(x=>/^(?:out of stock|sold out|نفد المخزون|إنتهى من المخزن)$/i.test(x));
 // Positive stock requires the exact product identifier and an explicit purchase control.
 const buy=skuMatch&&labels.some(x=>/^(?:add to cart|add to bag|add to basket|أضف إلى السلة)$/i.test(x));
 return {dimensions_cm:facts.size,dimensions:dimensionLabel(facts.size),dimensions_evidence:facts.evidence,dimensions_status:facts.status,dimensions_source:Object.keys(facts.size).length?'store_page_extraction':null,availability:sold?'out_of_stock':buy?'listed_available':'unknown',stock_evidence:sold||buy?'extracted_purchase_control':'unconfirmed'};
}
export async function scrapeDetails(offer,market,{fetcher=fetch,env=process.env}={}){
 if(!env.SERPER_API_KEY||!sourceScope(offer.link,market))return null;
 const key=market+':'+productURL(offer.link),old=cache.get(key);if(old&&Date.now()-old.time<120000)return detailsFromScrape(old.data,offer);
 let task=pending.get(key);
 if(!task){task=(async()=>{
  const res=await fetcher('https://scrape.serper.dev',{method:'POST',headers:{'Content-Type':'application/json','X-API-KEY':env.SERPER_API_KEY},body:JSON.stringify({url:offer.link,includeMarkdown:true}),signal:AbortSignal.timeout(12000)});
  if(!res.ok)throw Error('detail_provider_'+res.status);
  const raw=await res.text();if(raw.length>2000000)throw Error('details_too_large');const data=JSON.parse(raw);
  // Only content metadata is logged; never credentials or full product page contents.
  console.log('SPACES_DETAIL_EXTRACT',JSON.stringify({host:new URL(offer.link).hostname,fields:Object.keys(data),chars:String(data.markdown||data.text||'').length}));
  if(cache.size>=100)cache.delete(cache.keys().next().value);cache.set(key,{time:Date.now(),data});return data;
 })();pending.set(key,task);task.finally(()=>pending.delete(key)).catch(()=>{});}
 return detailsFromScrape(await task,offer);
}
export async function readStoreDetails(offer,market,{page=safePage,fallback=scrapeDetails}={}){
 let pageData,product,stock={availability:'unknown',stock_evidence:'unconfirmed'};
 try{
  pageData=await page(offer.link,{timeout:6500});
  if(!sourceScope(pageData.url,market)||sourceScope(pageData.url,market)!==sourceScope(offer.link,market))throw Error('different_storefront');
  stock=availabilityFromPage(pageData.html,pageData.url);product=productFromPage(pageData.html,pageData.url,offer.currency);
 }catch(e){console.log('SPACES_DETAIL_PAGE_UNCONFIRMED',JSON.stringify({url:offer.link,reason:e.message}));}
 if(page!==safePage)return {pageData,product,stock}; // deterministic injected clients do not call paid providers
 const needSize=!usableSize(product?.dimensions_cm)&&!(/rug|carpet|mirror|wall art|curtain/i.test(offer.title)&&Object.keys(product?.dimensions_cm||{}).length>=2);
 if(needSize||stock.availability==='unknown')try{
   const extra=await fallback(offer,market);
   if(extra){
    if(stock.availability==='unknown'||extra.availability==='out_of_stock')stock={availability:extra.availability,stock_evidence:extra.stock_evidence};
    if(needSize&&Object.keys(extra.dimensions_cm||{}).length){
     // Conflicting extracts cannot silently replace store evidence.
     const conflict=Object.entries(product?.dimensions_cm||{}).some(([k,v])=>extra.dimensions_cm[k]&&Math.abs(extra.dimensions_cm[k]-v)>.1);
     if(!conflict)product={...(product||offer),...extra,link:offer.link,details_identity:'exact_page_extraction'};
    }
   }
 }catch(e){console.log('SPACES_DETAIL_FALLBACK_UNCONFIRMED',JSON.stringify({url:offer.link,reason:e.message}));}
 return {pageData,product,stock};
}
