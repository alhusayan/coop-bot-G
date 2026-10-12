// Transport and presentation adapter only. The original Findzia service owns
// retrieval, matching, stock and prices; Spaces must not re-audit its results.
import {createHmac,randomBytes} from 'node:crypto';
import {createFindziaClient} from './original-client.mjs';
import {MARKETS,safeUrl} from './engine.mjs';
export const SEARCH_ENGINE='findzia-original';
export const SEARCH_REVISION=13;
let active=0;const queue=[];
async function slot(fn){if(active>=3)await new Promise(resolve=>queue.push(resolve));else active++;try{return await fn();}finally{const next=queue.shift();if(next)next();else active--;}}
const clean=value=>String(value??'').replace(/[\u0000-\u001f]/g,' ').trim();

// The same state reducer and display contract as the original website.
// Spaces adds only the requested completed visual-evidence gate, below.
export function closeVisualDecision(row,group){
 const axes=row.visual_axes||{};
 if(row.hidden||row.photo_match_status==='rejected'||row.alternative_visual_status==='rejected')return {ok:false,reason:'rejected'};
 if(row.classification_final!==true||row.identity_review_status!=='completed')return {ok:false,reason:'visual_review_pending'};
 const structural=['category','subtype','function','product_role','form_factor','silhouette','shape_geometry','structure','configuration','support_base'];
 if(structural.some(axis=>axes[axis]==='different'))return {ok:false,reason:'different_product_design'};
 if(axes.color==='different')return {ok:false,reason:'different_color'};
 if(group==='alternative'){
  if(row.alternative_visual_status!=='approved'||row.alternative_visual_policy!=='156.7.3'||!row.alternative_visual_proof)return {ok:false,reason:'alternative_unverified'};
  if(axes.material==='different'||axes.texture==='different'||axes.pattern==='different')return {ok:false,reason:'different_surface'};
 }
 // SKU scores penalize unknown/different brands and models; a generated room
 // has no proven SKU. Use the completed visual axes, never that identity score.
 if(axes.category!=='same'||!row.audited_media_path&&!row.audited_image)return {ok:false,reason:'visual_evidence_missing'};
 return {ok:true,reason:'original_visual_review'};
}

function adaptOffer({row,money,images,group,key,priceAtStore},market){
 const decision=closeVisualDecision(row,group);
 if(!decision.ok)return null;
 const link=safeUrl(row.url),image=images.map(safeUrl).find(Boolean);
 if(!link||!image)return null;
 const local=row.market_scope==='local'||row.market==='local';
 return {link,image,image_candidates:images.filter(safeUrl),title:clean(row.title||row.raw_title),source:clean(row.store||new URL(link).hostname),
  price:money?.value??null,currency:money?.currency||MARKETS[market].currency,price_at_store:priceAtStore,
  price_label:money?clean(row.price):'',price_kind:row.price_kind||'exact',price_estimated:row.price_estimated===true,
  original_price:clean(row.original_price),original_currency:row.original_currency||money?.currency,
  market_scope:local?'local':'international',market:local?market:(row.country||row.market_country||null),
  search_engine:SEARCH_ENGINE,search_market:market,original_result_key:key,original_result_group:group,
  match:'findzia_original',match_type:row.match_type||'similar',visual_score:row.identity_match_percentage??row.match_percentage??0,
  visual_review:decision.reason,visual_differences:row.visual_differences||[],
  availability:row.in_stock===true||row.stock_status==='in_stock'?'listed_available':'unknown',
  stock_evidence:row.stock_evidence||'findzia_original',stock_checked_at:row.stock_checked_at||new Date().toISOString(),
  evidence:row.price_source||'findzia_original',match_reason:clean(row.match_reason||row.identity_reason),differences:row.differences||[]};
}
export function originalOffer(row,market){const client=createFindziaClient(market);client.accept({event:'result',item:row});const entry=client.rows()[0];return entry?adaptOffer(entry,market):null;}

export function createOriginalResults(market,onProgress=()=>{}){
 const client=createFindziaClient(market);let complete=false,failed=false;
 function snapshot(){return client.rows().map(entry=>adaptOffer(entry,market)).filter(Boolean);}
 function diagnostics(){const entries=client.rows(),hidden={};for(const entry of entries){const d=closeVisualDecision(entry.row,entry.group);if(!d.ok)hidden[d.reason]=(hidden[d.reason]||0)+1;else if(!entry.images.length)hidden.image_unavailable=(hidden.image_unavailable||0)+1;}
  return {original_candidates:entries.length,original_with_images:entries.filter(x=>x.images.length).length,displayed:snapshot().length,held:hidden};}
 return {get complete(){return complete;},get failed(){return failed;},snapshot,diagnostics,
  accept(event){
   client.accept(event);
   if(event.event==='done')complete=true;
   else if(event.event==='error')failed=true;
   onProgress({offers:[],alternatives:snapshot(),search_engine:SEARCH_ENGINE,search_market:market,
    phase:complete?'complete':'checking',search_scope:'findzia',checked:client.all().length});
  }
 };
}

export async function searchOriginalPiece(bytes,market,{room,language='en',env=process.env,fetcher=fetch,onProgress=()=>{}}={}){
 if(!MARKETS[market]||!Buffer.isBuffer(bytes)||!bytes.length||!(/^[a-f0-9]{24}$/).test(room||''))throw Error('INVALID_INPUT');
 const secret=env.FINDZIA_SPACES_ENGINE_KEY;if(!secret||secret.length<32)throw Error('ENGINE_UNAVAILABLE');
 return slot(async()=>{
  for(let attempt=0;attempt<2;attempt++){
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
  const diagnostics=results.diagnostics();
  // One bounded retry of the exact original request only when it ended with
  // no verified options but still had priced candidates awaiting image review.
  if(attempt===0&&results.complete&&!results.failed&&!results.snapshot().length&&diagnostics.held.visual_review_pending){
   onProgress({phase:'checking',search_scope:'findzia'});continue;
  }
  return {offers:[],alternatives:results.snapshot(),partial:!results.complete,search_diagnostics:{...diagnostics,attempts:attempt+1},search_engine:SEARCH_ENGINE,search_market:market};
  }
 });
}
