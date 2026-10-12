import {availabilityFromPage,STOCK_VERSION,stockFresh} from './availability.mjs';
import {safePage,productFromPage} from './engine.mjs';
import {sourceScope} from './sourcing.mjs';
const pending=new Map();
export async function checkStock(offer,market,{page=safePage,force=false}={}){
 if(!force&&stockFresh(offer))return {...offer};
 const key=market+':'+offer.link;
 // Only coalesce in-flight default fetches. Stored results carry their own short expiry.
 async function read(){
   const stamp={stock_version:STOCK_VERSION,stock_checked_at:new Date().toISOString()};
   try{
     const p=await page(offer.link,{timeout:5000});
     if(!sourceScope(p.url,market)||sourceScope(p.url,market)!==sourceScope(offer.link,market))return {...stamp,availability:'unknown',stock_evidence:'different_storefront'};
     const stock=availabilityFromPage(p.html,p.url);
     let product;try{product=productFromPage(p.html,p.url,offer.currency);}catch{}
     console.log('SPACES_STOCK_CHECK',JSON.stringify({url:offer.link,status:stock.availability,evidence:stock.stock_evidence}));
     return {...stamp,...stock,product};
   }catch(e){
     console.log('SPACES_STOCK_UNCONFIRMED',JSON.stringify({url:offer.link,reason:e.message}));
     return {...stamp,availability:offer.availability==='out_of_stock'?'out_of_stock':'unknown',stock_evidence:'unconfirmed'};
   }
 }
 let task=page===safePage?pending.get(key):null;
 if(!task){task=read();if(page===safePage){pending.set(key,task);task.finally(()=>pending.delete(key));}}
 const {product,...stock}=await task;
 // Prices/materials from another default gallery variant cannot replace audited data.
 const sameImage=product?.image===offer.image;
 const sku=new URL(offer.link).pathname.match(/\/(?:p|dp|item)\/([^/]+)\/?$/)?.[1];
 const exactSKU=product?.sku&&sku===String(product.sku);
 const size=(sameImage||exactSKU)&&product?.dimensions_cm?{dimensions_cm:product.dimensions_cm,dimensions:product.dimensions,dimensions_source:product.dimensions_source}:{};
 return {...offer,...(sameImage?product:{}),...size,...stock,image:offer.image};
}
export async function refreshItemStock(item,market,{check=checkStock}={}){
 const rows=[...(item.offers||[]),...(item.alternatives||[])];
 const checked=new Map(await Promise.all(rows.map(async o=>[o.link,await check(o,market)])));
 const keep=rows=>(rows||[]).map(o=>checked.get(o.link)).filter(o=>o&&o.availability!=='out_of_stock');
 return {...item,offers:keep(item.offers),alternatives:keep(item.alternatives)};
}
