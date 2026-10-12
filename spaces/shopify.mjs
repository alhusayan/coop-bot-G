// Live-only supplement to Spaces. Never persist these results or download their
// images: https://shopify.dev/docs/agents/catalog#usage-guidelines
import {MARKETS} from './engine.mjs';
const ENDPOINT='https://catalog.shopify.com/api/ucp/mcp';
const PROFILE='https://api.findzia.com/.well-known/ucp';
const zero=new Set('BIF CLP DJF GNF ISK JPY KMF KRW PYG RWF UGX VND VUV XAF XOF XPF'.split(' '));
const three=new Set('BHD IQD JOD KWD LYD OMR TND'.split(' '));
const four=new Set(['CLF','UYW']);
let inflight=0,retryAt=0;
const text=(value,limit=240)=>String(value||'').replace(/<[^>]*>/g,'').replace(/[\u0000-\u001f\u007f]/g,' ').trim().slice(0,limit);
function url(value){try{if(typeof value!=='string'||value.length>4096||/\s/.test(value))return '';const u=new URL(value);return u.protocol==='https:'&&!u.username&&!u.password?u.href:'';}catch{return '';}}
export function catalogMoney(price){
 if(!Number.isSafeInteger(price?.amount)||price.amount<0||!(/^[A-Z]{3}$/).test(price.currency))return null;
 const digits=zero.has(price.currency)?0:three.has(price.currency)?3:four.has(price.currency)?4:2;
 return {amount:price.amount/10**digits,currency:price.currency};
}
export function catalogProducts(products,market){
 if(!MARKETS[market]||!Array.isArray(products))return [];
 const rows=[],seen=new Set();
 for(const product of products.slice(0,50)){
  if(!product||!Array.isArray(product.variants))continue;
  for(const variant of product.variants.slice(0,50)){
   // Digital products may bypass ships_from. Only physical available variants
   // from this country-filtered response constitute local-origin evidence.
   if(variant?.requires?.shipping!==true||variant.availability?.available!==true||variant.requires.selling_plan||variant.requires.components)continue;
   const money=catalogMoney(variant.price),title=text(product.title),seller=variant.seller;
   let link=url(variant.url||product.url);
   if(!money||!title||!link||!seller||typeof seller!=='object')continue;
   const id=String(variant.id||'').match(/^gid:\/\/shopify\/ProductVariant\/(\d+)$/)?.[1];
   if(id){const u=new URL(link);u.searchParams.set('variant',id);link=u.href;}
   const image=[...(Array.isArray(variant.media)?variant.media:[]),...(Array.isArray(product.media)?product.media:[])].find(m=>m?.type==='image'&&url(m.url));
   if(!image||seen.has(link))continue;
   seen.add(link);rows.push({title,link,image:url(image.url),source:text(seller.name||new URL(link).hostname,120),price:money.amount,currency:money.currency,market_scope:'local',merchant_country:market,destination_country:market,origin_evidence:'shopify_ships_from',availability:'listed_available',match:'catalog_suggestion'});break;
  }
 }
 return rows.slice(0,8);
}
export function catalogResponse(data,market){
 const result=data?.result,content=result?.structuredContent;
 if(data?.error||result?.isError||!Array.isArray(content?.products)||content.status&&!['success','ok'].includes(content.status))return {status:'unavailable',items:[]};
 // Do not retry without origin/availability filters if the provider rejects one.
 if((content.messages||[]).some(m=>/unsupported|ignored|invalid.*filter/i.test(String(m?.code||'')+' '+String(m?.message||''))))return {status:'unavailable',items:[]};
 return {status:'ok',items:catalogProducts(content.products,market)};
}
export async function searchLocalCatalog(query,market,{fetcher=fetch,language='en'}={}){
 if(!MARKETS[market]||!text(query,400))return {status:'invalid_market',items:[]};
 if(inflight>=8||Date.now()<retryAt)return {status:'busy',items:[]};
 inflight++;
 const payload={jsonrpc:'2.0',id:1,method:'tools/call',params:{name:'search_catalog',arguments:{meta:{'ucp-agent':{profile:PROFILE}},catalog:{query:text(query,400),context:{address_country:market,language},filters:{ships_to:{country:market},ships_from:[{country:market}],available:true},pagination:{limit:8}}}}};
 try{
  const response=await fetcher(ENDPOINT,{method:'POST',headers:{'Content-Type':'application/json',Accept:'application/json, text/event-stream'},body:JSON.stringify(payload),redirect:'error',signal:AbortSignal.timeout(12000)});
  if(response.status===429){retryAt=Date.now()+60000;return {status:'busy',items:[]};}
  if(!response.ok)return {status:'unavailable',items:[]};
  const chunks=[];let size=0;
  for await(const chunk of response.body){size+=chunk.length;if(size>2000000)return {status:'unavailable',items:[]};chunks.push(chunk);}
  const body=Buffer.concat(chunks).toString('utf8');
  const data=response.headers.get('content-type')?.includes('text/event-stream')?body.split(/\r?\n/).filter(x=>x.startsWith('data:')).map(x=>x.slice(5).trim()).filter(x=>x&&x!=='[DONE]').map(x=>JSON.parse(x)).find(x=>x.id===1):JSON.parse(body);
  return catalogResponse(data,market);
 }catch{return {status:'unavailable',items:[]};}finally{inflight--;}
}
