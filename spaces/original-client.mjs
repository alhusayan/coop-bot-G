// Original Findzia client functions, copied verbatim from frontend/source/findzia-home.liquid.
// Source: main@699207538a707691283fa600b6e09b9841fbbcf9. UI-only hooks are no-ops.
// Price/image merge, visibility, source membership and removal semantics remain original.
export function createFindziaClient(market='KW') {
 const n=market,r='https://api.findzia.com',location={origin:'https://findzia.com'},window={location};
 const ge={BIF:0,CLP:0,DJF:0,GNF:0,ISK:0,JPY:0,KMF:0,KRW:0,PYG:0,RWF:0,UGX:0,VND:0,VUV:0,XAF:0,XOF:0,XPF:0,BHD:3,IQD:3,JOD:3,KWD:3,LYD:3,OMR:3,TND:3,CLF:4,UYW:4},q=new Map();let U=[],j={},H={},F=0,Q=false;
 const b={innerHTML:''},wt=()=>{},pt=()=>{},dt=x=>x;
function gr(e){return Object.prototype.hasOwnProperty.call(ge,e)?ge[e]:2;}
function mr(e){return String(e||"").replace(/[.*+?^${}()|[\]\\]/g,"\\$&");}
function vr(e){return String(null==e?"":e).replace(/[٠-٩]/g,function(e){return String(e.charCodeAt(0)-1632);}).replace(/[۰-۹]/g,function(e){return String(e.charCodeAt(0)-1776);}).replace(/٫/g,".").replace(/٬/g,",").replace(/[\u00a0\u202f]/g," ").replace(/’/g,"'");}
function yr(e,r,t){var a=String(null==e?"":e),n=vr(e).trim();if(a.includes("٫")&&(t="."),!/^\d[\d.,' ]*$/.test(n))return null;function i(e,r){var t=e.split(r);return t.length>1&&/^\d{1,3}$/.test(t[0])&&(t.slice(1).every(function(e){return/^\d{3}$/.test(e);})||","===r&&/^\d{3}$/.test(t[t.length-1])&&t.slice(1,-1).every(function(e){return/^\d{2}$/.test(e);}));}
for(var o of["'"," "])
if(n.includes(o)){if(!i(n.split(/[.,]/,1)[0],o))return null;n=n.split(o).join("");}var s=(n.match(/\./g)||[]).length,c=(n.match(/,/g)||[]).length,l=gr(r);if(s&&c){var u=n.lastIndexOf(".")>n.lastIndexOf(",")?".":",",d="."===u?",":".",f=n.split(u);if(2!==f.length||!new RegExp("^\\d{1,"+Math.max(2,l)+"}$").test(f[1])||!i(f[0],d))return null;n=f[0].split(d).join("")+"."+f[1];}else if(s||c){var p=s?".":",";if((f=n.split(p)).length>2){if(!i(n,p))return null;n=f.join("");}else{var m=f[0],h=f[1];if(!/^\d+$/.test(m)||!/^\d+$/.test(h))return null;if(t)
if(p!==t){if(!i(n,p))return null;n=f.join("");}else{if(h.length>Math.max(4,l))return null;n=m+"."+h;}
else if(0===Number(m)&&h.length<=4||h.length<=2||"."===p&&(3===l||4===l)&&h.length===l)n=m+"."+h;else{if(3!==h.length||!i(n,p))return null;n=f.join("");}}}
var g=Number(n);return Number.isFinite(g)&&g>0?g:null;}
function _r(e,r){e=e||{};if(fzIsSocial(e)&&Number(e.expires_at)<=Date.now()/1000)return null;if(e.hidden||e.stock_status==="out_of_stock"||e.in_stock===false||e.price_integrity_status==='pending')return null;if(e.price_unavailable||"suspect"===e.price_status||"unavailable"===e.price_status)return null;if("findzia-money-v1"===e.price_contract){if(!e.price_display_ready||!/^[A-Z]{3}$/.test(e.price_display_currency||""))return null;var t=e.price_amount;return"number"!=typeof t||!Number.isFinite(t)||t<=0?null:{value:t,currency:e.price_display_currency,major:e.price_display_major,minor:e.price_display_minor,kind:e.price_kind||"exact",highMajor:e.price_display_high_major||"",highMinor:e.price_display_high_minor||"",unit:e.price_unit||""};}
var a=String(null==r?e.price||"":r).split(" (")[0].trim(),n=vr(a),i=String((n.match(/(?<![A-Z])[A-Z]{3}(?![A-Z])/i)||[])[0]||e.currency||"").toUpperCase(),o={"د.ك":"KWD","دك":"KWD",KD:"KWD","ر.س":"SAR","د.إ":"AED","ر.ع":"OMR","د.ب":"BHD","ر.ق":"QAR",US$:"USD",R$:"BRL",RMB:"CNY","€":"EUR","£":"GBP","₹":"INR","₩":"KRW","₺":"TRY"};(i=o[i]||i)||Object.keys(o).some(function(e){if(n.toUpperCase().includes(e.toUpperCase()))return i=o[e],!0;});var s=String(e.country||e.market_country||"").toUpperCase();if(!i&&n.includes("$")&&(i={US:"USD",CA:"CAD",AU:"AUD",NZ:"NZD",HK:"HKD",SG:"SGD",TW:"TWD",MX:"MXN"}[s]||""),!i&&/[¥￥]/.test(n)&&(i={CN:"CNY",JP:"JPY"}[s]||""),!/^[A-Z]{3}$/.test(i))return null;var c=n.replace(new RegExp("(?<![A-Z])"+i+"(?![A-Z])","ig"),"");Object.keys(o).sort(function(e,r){return r.length-e.length;}).forEach(function(e){c=c.replace(new RegExp(mr(e),"gi"),"");});var l=yr(c=c.replace(/[$¥￥]/g,"").trim(),i,a.includes("٫")?".":"");if(!l)return null;var u=new Intl.NumberFormat("en-US",{minimumFractionDigits:gr(i),maximumFractionDigits:gr(i)}).formatToParts(l);return u.some(function(e){return("integer"===e.type||"fraction"===e.type)&&/[1-9]/.test(e.value);})?{value:l,currency:i,major:u.filter(function(e){return"integer"===e.type||"group"===e.type;}).map(function(e){return e.value;}).join(""),minor:u.filter(function(e){return"decimal"===e.type||"fraction"===e.type;}).map(function(e){return e.value;}).join("")}:null;}
function br(e){return e&&e.provider_passthrough&&e.result_id?e.result_id:String(e&&e.url||"").trim()||[e&&e.market,e&&e.store,e&&e.title].join("|");}
function kr(e){if("local"===e.market||"local"===e.market_scope)return n;var r=String(e.country||e.store_country||e.market_country||"").toUpperCase();return Lt(r)?r:"us"===e.market?"US":"china"===e.market?"CN":"";}
function Lt(e){return/^[A-Za-z]{2}$/.test(String(e||"").trim());}
function or(e){if("string"!=typeof e||!e.trim())return"";try{var r=new URL(String(e||""),window.location.origin);return"http:"===r.protocol||"https:"===r.protocol?r.href:"";}catch(e){return"";}}
function Ar(e){if("string"!=typeof e||!/^https?:\/\//i.test(e))return"";try{var t=new URL(e),a=t.hostname.toLowerCase();return t.username||t.password||/^(?:localhost|127\.|0\.|\[)/.test(a)||/\.(?:local|internal)$/.test(a)||/(^|\.)google\.[a-z.]+$/.test(a)||/(^|\.)(?:googleadservices\.com|googleusercontent\.com|gstatic\.com|serpapi\.com|railway\.app)$/.test(a)||r&&t.origin===new URL(r).origin?"":t.href;}catch(e){return"";}}
function et(row) {
    const url=row.provider_passthrough?Ar(row.url):or(row.url||'');
    if(!url)return '';
    try {const parsed=new URL(url);
      if(/\/(?:product-category|product-tag|collections?|categor(?:y|ies)|catalog|browse|search|results)(?:\/|$)/i.test(decodeURIComponent(parsed.pathname))&&!/\/(?:products?|dp|item)\//i.test(parsed.pathname))return '';
      if(/(?:^|\.)miinto\.(?:[a-z]{2,3}|co\.uk|com\.[a-z]{2})$/i.test(parsed.hostname)&&!parsed.pathname.startsWith('/p-'))return '';
    }catch(_){return '';}
    return url;
  }
function ut(url){try{const u=new URL(url);if(u.pathname.endsWith('/api/img-proxy'))return 'proxy:'+u.searchParams.get('u');}catch(_){}return url;}
function fzPlaceholderImage(value){
 let raw=String(value||'').trim().replace(/&amp;/g,'&').replace(/\\\//g,'/');
 const asset=/(?:^|\/)(?:ajax[-_])?(?:spinner|preloader|loader|loading(?:[-_](?:spinner|icon|indicator))?|placeholder|no[-_]?image|image[-_]?(?:placeholder|not[-_]?(?:found|available)))(?:[-_.](?:[0-9a-f]{6,}|v?\d+|small|large|dark|light|white|black|grey|gray))*\.(?:gif|svg|png|webp|jpe?g|avif)(?:$|\/)/i;
 for(let depth=0;depth<4;depth++){
  try{
   const url=new URL(raw,location.origin);let path=url.pathname;
   for(let i=0;i<2;i++){try{path=decodeURIComponent(path);}catch(_){break;}}
   if(asset.test(path))return true;
   let inner='';for(const key of ['u','url','src','image']){inner=url.searchParams.getAll(key).find(v=>/^(?:https?:)?\/\//.test(v))||'';if(inner)break;}
   if(!inner||inner===raw)break;raw=inner;
  }catch(_){break;}
 }
 return false;
}
function lt(row){
 const urls=[],seen=new Set();
 function add(value){
  if(Array.isArray(value)){value.slice(0,16).forEach(add);return;}
  if(value&&typeof value==='object'){add(value.url||value.src||value.contentUrl);return;}
  if(typeof value!=='string'||!value.trim()||value===row.image_recovery_url)return;
  try{
   const url=new URL(value.trim().replace(/&amp;/g,'&'),/^\/api\//.test(value)?r:or(row.url)||r||location.origin);
   if(!/^https?:$/.test(url.protocol)||fzPlaceholderImage(url.href))return;
   if(url.pathname.endsWith('/api/img-proxy')){
    const raw=url.searchParams.get('u');
    if(raw===row.url||raw===row.link)return;
    add(raw);
    if(!r||url.origin!==new URL(r).origin||!url.searchParams.has('sig'))return;
   }
   if(url.href===row.url||url.href===row.link||seen.has(ut(url.href)))return;
   seen.add(ut(url.href));urls.push(url.href);
  }catch(_){}
 }
 ['audited_image','serpapi_thumbnail','thumbnail','image','image_url','product_image','thumbnails','images','image_candidates'].forEach(key=>add(row[key]));
 const rank=url=>/\/api\/img-proxy\?/.test(url)?2:/^https?:\/\/[^/]*(?:gstatic\.com|googleusercontent\.com|serpapi\.com)\//.test(url)?0:1;
 return urls.sort((a,b)=>rank(a)-rank(b)).slice(0,16);
}
function fzIsSocial(row){return !!(row&&row.social_id&&(row.result_group==='social'||row.price_source==='social_post'));}
function fzEarlyPhotoPreview(row){
 return !!(row?.display_before_audit===true&&!row.classification_final&&!row.hidden&&
  (row.search_origin==='image'||row.image_query_result)&&row.photo_match_status!=='rejected'&&
  row.alternative_visual_status!=='rejected');
}
function fzPhotoAlternative(row) {
    if(fzIsSocial(row))return false;
    const origin=row.search_origin||row.reference_search_kind;
    if(origin==='text') return false;
    const sources=row.retrieval_sources||[];
    if(!(origin==='image'||row.image_query_result)) return false;
    if(sources.some(s=>s.includes('bing_'))) return true;
    if(sources.includes('google_lens')) return false;
    return row.result_group==='alternative'||sources.some(s=>/^(?:serper|brave_search)(?:_|$)/.test(s));
  }
function fzAlternativePending(row){
if(fzEarlyPhotoPreview(row))return false;
const origin=row.search_origin||row.reference_search_kind;
const socialPhoto=fzIsSocial(row)&&(origin==='image'||(origin!=='text'&&row.image_query_result));
return (fzPhotoAlternative(row)||socialPhoto)&&(row.alternative_visual_status!=='approved'||!['156.7.2','156.7.3'].includes(row.alternative_visual_policy)||!row.alternative_visual_proof);
}
function fzSheinPriceLink(row){
 if(!row||_r(row)||row.hidden||row.in_stock===false||row.stock_status==='out_of_stock'||row.price_integrity_status==='pending')return false;
 if(['rejected','pending'].includes(row.photo_match_status)||fzAlternativePending(row))return false;
 try{
  const url=new URL(et(row));
  return url.protocol==='https:'&&!url.username&&!url.password&&!url.port&&
   /(^|\.)shein\.com$/i.test(url.hostname)&&/(?:-p-|\/product-p-)\d+(?:\.html)?\/?$/i.test(url.pathname);
 }catch(_){return false;}
}
function fzOfferCanDisplay(row){return !!_r(row)||fzSheinPriceLink(row);}
function $t(e) {
  return e && !!et(e) && !fzAlternativePending(e) && fzOfferCanDisplay(e) && (e.market || e.country || e.market_scope) && "rejected" !== e.photo_match_status && ("pending" !== e.photo_match_status || fzEarlyPhotoPreview(e));
}
function Fr(e){if(fzIsSocial(e))return"social";if(fzPhotoAlternative(e))return"alternative";var r=String(e.market_scope||"").toLowerCase(),t=String(e.market||"").toLowerCase();if("local"===r||"global"===r)return r;if("local"===t||"global"===t)return t;var a=kr(e),i=String(n).toUpperCase();return a?a.toUpperCase()===i?"local":"global":e.provider_passthrough&&String(e.search_country||"").toUpperCase()===i?"local":"global";}
function Ct(e){if(e&&(e.hidden||e.stock_status==="out_of_stock"||e.in_stock===false||fzAlternativePending(e))){At(e.url||e.link);return;}
if(e&&function(e){return!!e;}(e)&&(Q&&(Q=!1,b.innerHTML=""),String(e.market||"")||e.country||e.market_scope)){var r=br(e);if(r){if(null!=j[r]){var t=U[j[r]],a=Object.assign({},t,e);a._fzArrival=t._fzArrival,["image","thumbnail","image_url","product_image","thumbnails","images","image_candidates","image_recovery_url"].forEach(function(r){(!e[r]||Array.isArray(e[r])&&!e[r].length)&&(a[r]=t[r]);});var n="pending"===e.price_integrity_status||"suspect"===e.price_status||"unavailable"===e.price_status||!0===e.price_unavailable;String(e.price||"").trim()||!String(t.price||"").trim()||n||(["price","price_amount","currency","original_price","original_currency","price_source","price_verified","price_status","price_compare_value","price_compare_currency","price_contract","price_display_ready","price_display_major","price_display_minor","price_display_currency","price_kind","price_min","price_max","price_unit","price_tax_note","price_display_high_major","price_display_high_minor"].forEach(function(r){(!("number"==typeof e.price_compare_value&&Number.isFinite(e.price_compare_value)&&e.price_compare_value>0&&/^[A-Z]{3}$/.test(e.price_compare_currency||""))||"price_compare_value"!==r&&"price_compare_currency"!==r)&&(a[r]=t[r]);}),a.price_pending=!1,a.price_unavailable=!1),a.image_candidates=Array.from(new Set(lt(e).concat(lt(t)))).slice(0,12),a.retrieval_sources=Array.from(new Set((t.retrieval_sources||[]).concat(e.retrieval_sources||[]))),a.image_query_result=!(!t.image_query_result&&!e.image_query_result),a.result_group=Fr(a),U[j[r]]=a;}else e=Object.assign({},e,{_fzArrival:++F}),U.push(e),j[r]=U.length-1;pt(dt(U[j[r]]));wt();}}}
function At(e){var r=String(e||"").trim(),state=q.get(r);q.delete(r);if(state)Array.from(state.cancels).forEach(cancel=>cancel());U=U.filter(function(e){return br(e)!==r;}),j={},U.forEach(function(e,r){j[br(e)]=r;}),wt();}
 return {
  accept(event){if(['result','upsert'].includes(event.event))Ct(event.item||{});else if(event.event==='snapshot')(event.results||event.all_results||[]).forEach(Ct);else if(event.event==='remove')At(event.url);},
  rows(){return U.filter($t).map(row=>({row,money:_r(row),images:lt(row),group:Fr(row),key:br(row),priceAtStore:fzSheinPriceLink(row)}));},
  all(){return U.map(row=>({...row}));}
 };
}
