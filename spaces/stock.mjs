import {availabilityFromPage,STOCK_VERSION,stockFresh} from './availability.mjs';
import {safePage,productFromPage} from './engine.mjs';
import {sourceScope} from './sourcing.mjs';
const pending=new Map(),diagnosed=new Set();
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
     if(/\/(166349668|168271753)$/.test(new URL(offer.link).pathname)&&!diagnosed.has(offer.link)){
       diagnosed.add(offer.link);const raw=p.html.match(/<script[^>]*id="__NEXT_DATA__"[^>]*>([\s\S]*?)<\/script>/)?.[1];const nodes=[];
       try{const data=JSON.parse(raw);function visit(v,path='',depth=0){if(!v||typeof v!=='object'||depth>15||nodes.length>75)return;for(const [k,x] of Object.entries(v)){const where=path+'.'+k;if(/product|sku|inventory|stock|avail|endpoint|baseurl|apiurl/i.test(k))nodes.push({path:where,value:typeof x==='object'?(Array.isArray(x)?'array '+x.length:Object.keys(x).slice(0,40)):String(x).slice(0,180)});if(typeof x==='object'&&!/translation|message|i18n/i.test(k))visit(x,where,depth+1);}}visit(data);}catch{}
       console.log('SPACES_STOCK_STATE',JSON.stringify({url:offer.link,nodes}));
     }
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
 return {...offer,...(sameImage?product:{}),...stock,image:offer.image};
}
export async function refreshItemStock(item,market,{check=checkStock}={}){
 const rows=[...(item.offers||[]),...(item.alternatives||[])];
 const checked=new Map(await Promise.all(rows.map(async o=>[o.link,await check(o,market)])));
 const keep=rows=>(rows||[]).map(o=>checked.get(o.link)).filter(o=>o&&o.availability!=='out_of_stock');
 return {...item,offers:keep(item.offers),alternatives:keep(item.alternatives)};
}
