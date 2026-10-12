import {rankProducts} from './public/product-order.js';
import {MARKETS,safeUrl,localEvidence} from './engine.mjs';

export const SOURCE_POLICY_VERSION=2;
// Owner-approved Findzia sources. Admission never means delivery of every SKU is guaranteed.
export const APPROVED_GLOBAL_STORES=[
 ['Amazon','amazon.com','amazon.co.uk','amazon.de','amazon.fr','amazon.it','amazon.es','amazon.ca','amazon.com.au','amazon.ae','amazon.sa','amazon.co.jp'],
 ['eBay','ebay.com','ebay.co.uk','ebay.de','ebay.fr','ebay.it','ebay.es','ebay.ca','ebay.com.au'],
 ['Walmart','walmart.com','walmart.ca'],['AliExpress','aliexpress.com'],['Temu','temu.com'],['Alibaba','alibaba.com'],['SHEIN','shein.com'],
 ['Made-in-China','made-in-china.com'],['Target','target.com'],['Best Buy','bestbuy.com','bestbuy.ca'],['Newegg','newegg.com'],
 ["Macy’s",'macys.com'],['Nordstrom','nordstrom.com'],['iHerb','iherb.com'],['Pottery Barn','potterybarn.com'],['Etsy','etsy.com'],
 ['Home Depot','homedepot.com'],['Chewy','chewy.com'],["Carter’s",'carters.com'],['RockAuto','rockauto.com'],
 ['Decathlon','decathlon.com','decathlon.co.uk','decathlon.de','decathlon.fr'],['LightInTheBox','lightinthebox.com'],['DHgate','dhgate.com']
].map(([name,...domains])=>({name,domains}));
export const FURNITURE_STORES=[
 {name:'Finnish Design Shop',domains:['finnishdesignshop.com'],shipping_policy:'https://www.finnishdesignshop.com/en-ch/customer-service/delivery'},
 {name:'MOHD',domains:['shop.mohd.it'],shipping_policy:'https://shop.mohd.it/en/shipping-worldwide'},
 {name:'Archiproducts',domains:['archiproducts.com'],shipping_policy:'https://www.archiproducts.com/en/faq-shop',verify_purchase:true}
];
const all=[...APPROVED_GLOBAL_STORES,...FURNITURE_STORES];
const inDomain=(host,root)=>host===root||host.endsWith('.'+root);
const localStores={US:['amazon.com','ebay.com','walmart.com','target.com','bestbuy.com','newegg.com','macys.com','nordstrom.com','potterybarn.com','homedepot.com','wayfair.com'],GB:['amazon.co.uk','ebay.co.uk','wayfair.co.uk'],DE:['amazon.de','ebay.de','wayfair.de'],FR:['amazon.fr','ebay.fr'],SA:['amazon.sa','alrugaibfurniture.com'],AE:['amazon.ae'],KW:['safathome.com','hassanabul.com']};
export function storePolicy(url){const safe=safeUrl(url);if(!safe)return null;const host=new URL(safe).hostname.toLowerCase();return all.find(x=>x.domains.some(d=>inDomain(host,d)))||null;}
export function sourceScope(url,market){
 const safe=safeUrl(url);if(!safe)return null;const host=new URL(safe).hostname.toLowerCase();
 if(localEvidence(safe,market)||(localStores[market]||[]).some(d=>inDomain(host,d)))return 'local';
 return storePolicy(safe)?'international':null;
}
export function sourceDetails(url,market){
 const scope=sourceScope(url,market);if(!scope)return null;const store=storePolicy(url);
 return {market_scope:scope,market:scope==='local'?market:null,source_policy:SOURCE_POLICY_VERSION,shipping_status:'check_at_store',shipping_policy:store?.shipping_policy||null,shipping_note:scope==='local'?'Confirm delivery at store':'Confirm delivery to your address at store'};
}
export function filterApprovedOffers(rows,market){return rankProducts((rows||[]).flatMap(o=>{const details=sourceDetails(o.link,market);return details?[{...o,...details}]:[];}),Infinity);}
export function filterApprovedItem(item,market){return {...item,offers:filterApprovedOffers(item.offers,market),alternatives:filterApprovedOffers(item.alternatives,market)};}
export function requiresPurchaseCheck(url){return storePolicy(url)?.verify_purchase===true;}
export function hasPurchaseEvidence(html){return /"(?:offers|Offer)"\s*[:\]]|add to (?:cart|bag|basket)|buy (?:now|online)|itemprop=["']offers/i.test(html);}
export function furnitureQueries(query){return [[query+' ('+FURNITURE_STORES.map(s=>'site:'+s.domains[0]).join(' OR ')+')','US',{images:true,source:'furniture'}]];}
export function globalQueries(query,chinese,item,attempt=1){
 const subject=[item.name_en,item.specs?.category].filter(Boolean).join(' ');
 const specialist=/appliance|fridge|refrigerator|oven|tv|television|monitor|computer/i.test(subject)?['bestbuy.com','newegg.com']:['potterybarn.com','etsy.com','homedepot.com','target.com'];
 return [
  [query+' (site:amazon.com OR site:ebay.com OR site:walmart.com)','US',{images:true,source:'global'}],
  [chinese+' (site:aliexpress.com OR site:temu.com OR site:shein.com OR site:alibaba.com OR site:made-in-china.com)','CN',{images:true,lang:item.chinese_query?'zh-cn':'en',source:'global'}],
  [query+' ('+specialist.map(d=>'site:'+d).join(' OR ')+')','US',{images:true,source:'global'}],
  ...furnitureQueries(query),
  ...(attempt>1?[[query+' (site:lightinthebox.com OR site:dhgate.com OR site:macys.com OR site:nordstrom.com)','US',{images:true,source:'global'}]]:[])
 ];
}

// Country storefronts are queried as real URLs; a foreign URL is never relabelled local.
export const LOCAL_FURNITURE_SITES={
 SA:['homecentre.com/sa/','homeboxstores.com/sa/','ikea.com/sa/','alrugaibfurniture.com','abyat.com/sa/'],
 KW:['homecentre.com/kw/','homeboxstores.com/kw/','ikea.com/kw/','safathome.com','hassanabul.com','abyat.com/kw/'],
 AE:['homecentre.com/ae/','homeboxstores.com/ae/','ikea.com/ae/'],
 QA:['homecentre.com/qa/','homeboxstores.com/qa/','ikea.com/qa/'],
 BH:['homecentre.com/bh/','homeboxstores.com/bh/','ikea.com/bh/'],
 OM:['homecentre.com/om/','homeboxstores.com/om/'],
 US:['ikea.com/us/','wayfair.com','walmart.com','amazon.com'],
 GB:['ikea.com/gb/','wayfair.co.uk','amazon.co.uk'],
 DE:['ikea.com/de/','wayfair.de','amazon.de'],FR:['ikea.com/fr/','amazon.fr'],JP:['ikea.com/jp/','amazon.co.jp']
};
export function localQueries(item,market,{recovery=false}={}){
 const m=MARKETS[market],q=String(item.query||item.name_en||'').slice(0,200),native=item.native_query||q;
 const sites=LOCAL_FURNITURE_SITES[market]||[],siteQuery=sites.length?' ('+sites.map(x=>'site:'+x).join(' OR ')+')':'';
 // Remove over-specific prose only from retrieval. The full original specs still gate every visual check.
 let simple=String(item.name_en||item.specs?.category||q).replace(/\b(?:modern|contemporary|mid-century|platform)\b/gi,'').replace(/\s+/g,' ').trim();
 if(/\bbed\b/i.test(simple)&&!/\b(?:sofa|daybed|bunk)\b/i.test(simple))simple=simple.replace(/\bframe\b/gi,'').trim();
 if(!recovery)return [[q+' '+m.en,market,{images:true,source:'local'}],[native+' '+m.name+siteQuery,market,{images:true,lang:m.lang,source:'local'}]];
 return [[simple+siteQuery+' '+m.en,market,{images:true,source:'local-recovery'}],[simple+' '+m.en+siteQuery,market,{source:'local-recovery'}]];
}
