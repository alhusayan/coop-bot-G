// Transport and presentation adapter only. The original Findzia service owns
// retrieval, matching, stock and prices; Spaces must not re-audit its results.
import {createHmac,randomBytes} from 'node:crypto';
import {createFindziaClient} from './original-client.mjs';
import {createSearchScheduler} from './search-scheduler.mjs';
import {MARKETS,safeUrl} from './engine.mjs';
export const SEARCH_ENGINE='findzia-original';
export const SEARCH_REVISION=13;
const scheduler=createSearchScheduler();
export const prioritizeOriginalPiece=key=>scheduler.promote(key);
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

export async function searchOriginalPiece(bytes,market,{room,language='en',taskKey=randomBytes(8).toString('hex'),interactive=false,billing,timeout=125000,env=process.env,fetcher=fetch,onProgress=()=>{}}={}){
 if(!MARKETS[market]||!Buffer.isBuffer(bytes)||!bytes.length||!(/^[a-f0-9]{24}$/).test(room||''))throw Error('INVALID_INPUT');
 const secret=env.FINDZIA_SPACES_ENGINE_KEY;if(!secret||secret.length<32)throw Error('ENGINE_UNAVAILABLE');
 return scheduler.run(taskKey,async({queue_ms})=>{
  const started=Date.now(),timing={queue_ms,first_byte_ms:null,first_verified_ms:null,provider_first_verified_ms:null};
  let providerElapsed=null;
  onProgress({phase:'lens',search_timing:timing});
  const results=createOriginalResults(market,update=>{
   if(update.alternatives.length&&timing.first_verified_ms===null){timing.first_verified_ms=Date.now()-started;timing.provider_first_verified_ms=providerElapsed;}
   onProgress({...update,search_timing:{...timing}});
  });
  const accept=event=>{providerElapsed=event.elapsed_ms??providerElapsed;results.accept(event);};
  const body=JSON.stringify({image_base64:bytes.toString('base64'),mime_type:'image/jpeg',country:market,lang:language,spaces_room:room});
  const stamp=String(Math.floor(Date.now()/1000)),nonce=randomBytes(16).toString('hex');
  const signature=createHmac('sha256',secret).update(stamp+'\n'+nonce+'\n'+body).digest('hex');
  // Compression can buffer small NDJSON updates until the entire search ends.
  // Keep this stream uncompressed so reviewed cards arrive immediately.
  const response=await fetcher('https://api.findzia.com/internal/spaces/image/stream',{method:'POST',redirect:'error',headers:{'Content-Type':'application/json','Accept-Encoding':'identity',...(billing?{Authorization:billing.authorization,Origin:billing.origin,'X-Findzia-Request-Id':billing.requestId}:{}),'X-Findzia-Spaces-Time':stamp,'X-Findzia-Spaces-Nonce':nonce,'X-Findzia-Spaces-Signature':signature},body,signal:AbortSignal.timeout(Math.max(1000,Math.min(125000,timeout)))});
  if(!response.ok){let code;try{code=(await response.json()).error;}catch{}const allowed=['credits_exhausted','credits_unavailable','sign_in_required','session_expired','guest_session_expired','search_in_progress','search_already_processed','trial_daily_limit','trial_budget_reached'];throw Error(allowed.includes(code)?code:response.status===429?'PROVIDER_BUSY':'SEARCH_FAILED');}
  if(!response.headers.get('content-type')?.includes('ndjson'))throw Error('SEARCH_FAILED');
  const decoder=new TextDecoder();let buffer='',size=0;
  try{
   for await(const chunk of response.body){
    if(timing.first_byte_ms===null)timing.first_byte_ms=Date.now()-started;
    size+=chunk.length;if(size>24e6)throw Error('SEARCH_FAILED');buffer+=decoder.decode(chunk,{stream:true});
    let end;while((end=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,end).trim();buffer=buffer.slice(end+1);if(line)accept(JSON.parse(line));}
   }
   buffer+=decoder.decode();if(buffer.trim())accept(JSON.parse(buffer));
  }catch(error){if(!results.snapshot().length)throw error;}
  if(results.failed&&!results.snapshot().length)throw Error('SEARCH_FAILED');
  if(!results.complete&&!results.snapshot().length)throw Error('SEARCH_FAILED');
  const diagnostics=results.diagnostics();
  // One original search, just like findzia.com. A hidden automatic second
  // search doubled empty-search latency and blocked the rest of the room.
  return {offers:[],alternatives:results.snapshot(),partial:!results.complete,search_timing:{...timing,total_ms:Date.now()-started},search_diagnostics:{...diagnostics,attempts:1},search_engine:SEARCH_ENGINE,search_market:market};
 },{interactive});
}
