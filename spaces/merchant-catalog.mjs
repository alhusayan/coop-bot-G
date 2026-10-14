// Read a small part of an already discovered merchant's public catalogue.
// This does not call the paid image-search endpoint or consume search credits.
import {parseHTML} from 'linkedom';
import {safePage,safeUrl,productFromPage,MARKETS} from './engine.mjs';
import {sourceDetails} from './sourcing.mjs';
import {pageEvidence} from './product-details.mjs';
import {STOCK_VERSION} from './availability.mjs';
import {pool} from './matching.mjs';

export function catalogueRole(name){
 const s=String(name||'').toLowerCase();
 if(/dining.*table/.test(s))return /dining\s+tables?/i;
 if(/coffee.*table/.test(s))return /coffee\s+tables?/i;
 if(/dining.*chair/.test(s))return /dining\s+(?:arm)?chairs?/i;
 if(/sofa|sectional|couch/.test(s))return /sofas?|sectionals?|couches/i;
 if(/\bbed\b|bedframe/.test(s))return /\bbeds?\b|bed\s*frames?/i;
 if(/desk/.test(s))return /\bdesks?\b/i;
 return null;
}
export function catalogueLinks(html,url,role){
 const origin=new URL(url).origin,{document}=parseHTML(html),seen=new Set(),links=[];
 for(const a of document.querySelectorAll('a[href]')){
  const name=(a.textContent||a.getAttribute('title')||a.querySelector('img')?.getAttribute('alt')||'').replace(/\s+/g,' ').trim();
  if(!role.test(name)||name.length>200)continue;
  let link;try{link=safeUrl(new URL(a.getAttribute('href'),url).href);}catch{continue;}
  if(!link||new URL(link).origin!==origin||new URL(link).hash||/cart|checkout|account|login|wishlist|compare|remove|delete|logout/i.test(new URL(link).pathname)||/\.(?:jpe?g|png|webp|gif|svg|avif|pdf|mp4|webm)$/i.test(new URL(link).pathname)||seen.has(link)||link===url)continue;
  seen.add(link);links.push({name,link});
 }
 // Product names rank above broad navigation labels when both are present.
 return links.sort((a,b)=>Number(b.name.length>24)-Number(a.name.length>24));
}
export async function merchantCatalogue(item,offers,market,{page=safePage,skipLinks=[]}={}){
 const role=catalogueRole(item.name_en);if(!role)return [];
 const skipped=new Set(skipLinks);
 const hosts=new Set(),seeds=offers.filter(o=>o.market_scope==='local'&&o.search_market===market&&role.test(o.title||'')&&sourceDetails(o.link,market)?.market_scope==='local'&&!hosts.has(new URL(o.link).origin)&&hosts.add(new URL(o.link).origin)).slice(0,4);
 for(const seed of seeds){try{
  const original=await page(seed.link,{timeout:5000});if(new URL(original.url).origin!==new URL(seed.link).origin)continue;
  let links=catalogueLinks(original.html,original.url,role).slice(0,4);if(!links.length)continue;
  // If the merchant offers only a category link, follow that observed link
  // once. Never construct guessed product URLs or follow external stores.
  if(links.every(x=>x.name.length<25)){
   const category=await page(links[0].link,{timeout:5000});
   if(new URL(category.url).origin!==new URL(seed.link).origin)continue;
   links=catalogueLinks(category.html,category.url,role).filter(x=>x.name.length>=25).slice(0,4);
  }
  const products=(await pool(links.filter(x=>!skipped.has(x.link)),2,async({link})=>{try{
   const result=await page(link,{timeout:5000});if(new URL(result.url).origin!==new URL(seed.link).origin)return null;
   const product=productFromPage(result.html,result.url,MARKETS[market].currency),scope=sourceDetails(result.url,market);
   if(!product||!role.test(product.title)||scope?.market_scope!=='local'||product.availability!=='listed_available'||product.currency!==MARKETS[market].currency||!(product.price>0))return null;
   // A table-and-chair package cannot masquerade as a standalone table.
   if(/table/i.test(item.name_en)&&/chair|dining set/i.test(product.title))return null;
   const evidence=pageEvidence(result.html,result.url);
   return {...product,...scope,search_engine:'merchant-catalogue',search_market:market,stock_version:STOCK_VERSION,stock_checked_at:new Date().toISOString(),merchant_facts:evidence.facts,price_at_store:false};
  }catch{return null;}})).filter(Boolean);
  console.log('SPACES_FURNISH_CATALOGUE',JSON.stringify({id:String(item.id),host:new URL(seed.link).hostname,read:links.length,products:products.length}));
  if(products.length)return products;
 }catch(e){console.log('SPACES_FURNISH_CATALOGUE_UNAVAILABLE',JSON.stringify({id:String(item.id),reason:e.message}));}}
 return [];
}
