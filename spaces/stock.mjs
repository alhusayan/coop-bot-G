import {readStoreDetails} from './store-details.mjs';
import {DETAILS_VERSION,sameOfferProduct,productURL} from './product-data.mjs';
import {STOCK_VERSION,stockFresh} from './availability.mjs';
import {safePage} from './engine.mjs';
const pending=new Map();
let active=0;const queue=[];
async function boundedRead(run){if(active>=6)await new Promise(resolve=>queue.push(resolve));else active++;try{return await run();}finally{const next=queue.shift();if(next)next();else active--;}}
export async function checkStock(offer,market,{page=safePage,force=false,catalog=false}={}){
 if(!force&&stockFresh(offer)&&offer.details_version===DETAILS_VERSION)return {...offer};
 const key=market+':'+productURL(offer.link);
 // Only coalesce in-flight default fetches. Stored results carry their own short expiry.
 async function read(){
   const stamp={stock_version:STOCK_VERSION,details_version:DETAILS_VERSION,details_checked_at:new Date().toISOString(),stock_checked_at:new Date().toISOString()};
   try{
     const {pageData,product,stock}=await readStoreDetails(offer,market,{page});
     if(!pageData&&!product&&offer.availability==='out_of_stock')stock.availability='out_of_stock';
     console.log('SPACES_STOCK_CHECK',JSON.stringify({url:offer.link,status:stock.availability,evidence:stock.stock_evidence,dimensions:product?.dimensions_cm,details:product?.dimensions_status}));
     return {...stamp,...stock,product};
   }catch(e){
     console.log('SPACES_STOCK_UNCONFIRMED',JSON.stringify({url:offer.link,reason:e.message}));
     return {...stamp,availability:offer.availability==='out_of_stock'?'out_of_stock':'unknown',stock_evidence:'unconfirmed',details_status:'unconfirmed'};
   }
 }
 let task=page===safePage?pending.get(key):null;
 if(!task){task=page===safePage?boundedRead(read):read();if(page===safePage){pending.set(key,task);task.finally(()=>pending.delete(key));}}
 const {product,...stock}=await task;
 // Stock and dimensions belong to the exact product, not the first gallery photo.
 // Product-first sourcing adopts the product page's own photograph, never an unrelated indexed image.
 // Legacy visual matching retains its stricter gallery identity requirement.
 const normal=v=>String(v||'').toLowerCase().replace(/[^\p{L}\p{N}]+/gu,' ').trim();
 const words=normal(offer.title).split(' ').filter(x=>x.length>2&&!/^(buy|shop|online|with|the|and|kuwait|homecentre|safathome)$/.test(x));
 const sameTitle=words.length>=2&&words.filter(x=>normal(product?.title).split(' ').includes(x)).length/words.length>=.7;
 const catalogIdentity=catalog&&product?.image&&!product.variant_unconfirmed&&productURL(offer.link)===productURL(product.link)&&(!offer.sku||!product.sku||String(offer.sku)===String(product.sku))&&(sameOfferProduct(offer,product)||sameTitle);
 if(catalogIdentity)return {...offer,...product,...stock,catalog_score:offer.catalog_score};
 const identity=sameOfferProduct(offer,product),sameImage=identity&&product?.image===offer.image;
 const size=identity?{sku:product.sku,dimensions_cm:product.dimensions_cm,dimensions:product.dimensions,dimensions_source:product.dimensions_source,dimensions_evidence:product.dimensions_evidence,dimensions_status:product.dimensions_status,details_status:product.dimensions_status}:{};
 if(product&&!identity&&(productURL(offer.link)!==productURL(product.link)||offer.sku&&product.sku&&String(offer.sku)!==String(product.sku)))return {...offer,...stock,availability:'unknown',stock_evidence:'product_identity_unconfirmed',details_status:'unconfirmed'};
 return {...offer,...(sameImage?product:{}),...size,...stock,image:offer.image};
}
export async function refreshItemStock(item,market,{check=checkStock}={}){
 const rows=[...(item.offers||[]),...(item.alternatives||[])];
 const checked=new Map(await Promise.all(rows.map(async o=>[o.link,await check(o,market)])));
 const keep=rows=>(rows||[]).map(o=>checked.get(o.link)).filter(o=>o&&o.availability!=='out_of_stock');
 return {...item,offers:keep(item.offers),alternatives:keep(item.alternatives)};
}
