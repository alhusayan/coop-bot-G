// Transport and presentation adapter only. The original Findzia service owns
// retrieval, matching, stock and prices; Spaces must not re-audit its results.
import {createHmac,randomBytes} from 'node:crypto';
import {MARKETS,safeUrl} from './engine.mjs';
export const SEARCH_ENGINE='findzia-original';
export const SEARCH_REVISION=11;
let active=0;const queue=[];
async function slot(fn){if(active>=3)await new Promise(resolve=>queue.push(resolve));else active++;try{return await fn();}finally{const next=queue.shift();if(next)next();else active--;}}
const clean=value=>String(value??'').replace(/[\u0000-\u001f]/g,' ').trim();

export function originalOffer(row,market){
 if(!row||row.hidden||row.stock_status==='out_of_stock'||row.in_stock===false||row.price_unavailable||['suspect','unavailable'].includes(row.price_status)||row.price_integrity_status==='pending'||['rejected','pending'].includes(row.photo_match_status))return null;
 const link=safeUrl(row.url),images=[row.image,row.thumbnail,row.image_url,row.product_image,...(row.images||[]),...(row.image_candidates||[])];
 const image=images.map(x=>safeUrl(typeof x==='string'?x:x?.url)).find(Boolean);
 // Prices are already normalized by Findzia's money contract. Never re-parse
 // store prose or discard its decimal/currency/range information.
 const price=row.price_amount,currency=row.price_display_currency||row.currency;
 if(!link||!image||typeof price!=='number'||!Number.isFinite(price)||price<=0||!(/^[A-Z]{3}$/).test(currency||'')||row.price_contract==='findzia-money-v1'&&!row.price_display_ready)return null;
 const local=row.market_scope==='local'||row.market==='local';
 const priceLabel=row.price_contract==='findzia-money-v1'?clean(row.price):'';
 return {link,image,title:clean(row.title||row.raw_title),source:clean(row.store||new URL(link).hostname),price,currency,
  price_label:priceLabel,price_kind:row.price_kind||'exact',price_estimated:row.price_estimated===true,
  original_price:clean(row.original_price),original_currency:row.original_currency||currency,
  market_scope:local?'local':'international',market:local?market:(row.country||row.market_country||null),
  search_engine:SEARCH_ENGINE,search_market:market,match:'findzia_original',match_type:row.match_type||'similar',
  visual_score:row.identity_match_percentage??row.match_percentage??0,
  availability:row.in_stock===true||row.stock_status==='in_stock'?'listed_available':'unknown',
  stock_evidence:row.stock_evidence||'findzia_original',stock_checked_at:row.stock_checked_at||new Date().toISOString(),
  evidence:row.price_source||'findzia_original',match_reason:clean(row.match_reason||row.identity_reason),differences:row.differences||[]};
}

export function createOriginalResults(market,onProgress=()=>{}){
 const rows=new Map();let complete=false,failed=false;
 const key=row=>row?.provider_passthrough&&row.result_id?row.result_id:row?.url;
 function merge(row){const id=key(row);if(!id)return;const previous=rows.get(id)||{};rows.set(id,{...previous,...row});}
 function snapshot(){return [...rows.values()].map(row=>originalOffer(row,market)).filter(Boolean);}
 return {get complete(){return complete;},get failed(){return failed;},snapshot,
  accept(event){
   if(['result','upsert'].includes(event.event)&&event.item)merge(event.item);
   else if(event.event==='snapshot'){
    const incoming=event.results||event.all_results||[];
    if(event.authoritative){const keys=new Set(incoming.map(key));for(const id of rows.keys())if(!keys.has(id))rows.delete(id);}
    for(const row of incoming)merge(row);
   }else if(event.event==='remove'){rows.delete(event.result_id||event.url||key(event.item));}
   else if(event.event==='done')complete=true;
   else if(event.event==='error')failed=true;
   onProgress({offers:[],alternatives:snapshot(),search_engine:SEARCH_ENGINE,search_market:market,
    phase:complete?'complete':event.event==='status'&&event.stage==='identify'?'lens':'checking',search_scope:'findzia',checked:rows.size});
  }
 };
}

export async function searchOriginalPiece(bytes,market,{room,language=MARKETS[market]?.lang||'en',env=process.env,fetcher=fetch,onProgress=()=>{}}={}){
 if(!MARKETS[market]||!Buffer.isBuffer(bytes)||!bytes.length||!(/^[a-f0-9]{24}$/).test(room||''))throw Error('INVALID_INPUT');
 const secret=env.FINDZIA_SPACES_ENGINE_KEY;if(!secret||secret.length<32)throw Error('ENGINE_UNAVAILABLE');
 return slot(async()=>{
  const results=createOriginalResults(market,onProgress);
  const body=JSON.stringify({image_base64:bytes.toString('base64'),mime_type:'image/jpeg',country:market,lang:language,spaces_room:room});
  const stamp=String(Math.floor(Date.now()/1000)),nonce=randomBytes(16).toString('hex');
  const signature=createHmac('sha256',secret).update(stamp+'\n'+nonce+'\n'+body).digest('hex');
  const response=await fetcher('https://api.findzia.com/internal/spaces/image/stream',{method:'POST',redirect:'error',headers:{'Content-Type':'application/json','X-Findzia-Spaces-Time':stamp,'X-Findzia-Spaces-Nonce':nonce,'X-Findzia-Spaces-Signature':signature},body,signal:AbortSignal.timeout(125000)});
  if(!response.ok)throw Error(response.status===429?'PROVIDER_BUSY':'SEARCH_FAILED');
  if(!response.headers.get('content-type')?.includes('ndjson'))throw Error('SEARCH_FAILED');
  const decoder=new TextDecoder();let buffer='',size=0;
  try{
   for await(const chunk of response.body){
    size+=chunk.length;if(size>24e6)throw Error('SEARCH_FAILED');buffer+=decoder.decode(chunk,{stream:true});
    let end;while((end=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,end).trim();buffer=buffer.slice(end+1);if(line)results.accept(JSON.parse(line));}
   }
   buffer+=decoder.decode();if(buffer.trim())results.accept(JSON.parse(buffer));
  }catch(error){if(!results.snapshot().length)throw error;}
  if(results.failed&&!results.snapshot().length)throw Error('SEARCH_FAILED');
  if(!results.complete&&!results.snapshot().length)throw Error('SEARCH_FAILED');
  return {offers:[],alternatives:results.snapshot(),partial:!results.complete,search_engine:SEARCH_ENGINE,search_market:market};
 });
}
