import {readProductData} from './product-data.mjs';
import {dimensionDetails,dimensionLabel} from './dimensions.mjs';
import {availabilityFromPage} from './availability.mjs';
import https from 'node:https';
import dns from 'node:dns/promises';
import net from 'node:net';

export const MARKETS = {
  KW:{name:'الكويت',en:'Kuwait',currency:'KWD',symbol:'د.ك',flag:'🇰🇼',lang:'ar'},
  SA:{name:'السعودية',en:'Saudi Arabia',currency:'SAR',symbol:'ر.س',flag:'🇸🇦',lang:'ar'},
  AE:{name:'الإمارات',en:'United Arab Emirates',currency:'AED',symbol:'د.إ',flag:'🇦🇪',lang:'ar'},
  QA:{name:'قطر',en:'Qatar',currency:'QAR',symbol:'ر.ق',flag:'🇶🇦',lang:'ar'},
  BH:{name:'البحرين',en:'Bahrain',currency:'BHD',symbol:'د.ب',flag:'🇧🇭',lang:'ar'},
  OM:{name:'عُمان',en:'Oman',currency:'OMR',symbol:'ر.ع',flag:'🇴🇲',lang:'ar'},
  GB:{name:'بريطانيا',en:'United Kingdom',currency:'GBP',symbol:'£',flag:'🇬🇧',lang:'en'},
  US:{name:'أمريكا',en:'United States',currency:'USD',symbol:'$',flag:'🇺🇸',lang:'en'},
  DE:{name:'ألمانيا',en:'Germany',currency:'EUR',symbol:'€',flag:'🇩🇪',lang:'de'},
  FR:{name:'فرنسا',en:'France',currency:'EUR',symbol:'€',flag:'🇫🇷',lang:'fr'},
  JP:{name:'اليابان',en:'Japan',currency:'JPY',symbol:'¥',flag:'🇯🇵',lang:'ja'},
};
export const STYLES = [
 {id:'contemporary',ar:'هدوء معاصر',en:'Quiet contemporary',description:'خطوط بسيطة، ألوان متوازنة، ومساحة تتنفّس.',palette:['#ddd4c6','#8e987e','#ac8c6c'],prompt:'Quiet contemporary design: clean architectural lines, warm ivory, muted olive accents, refined practical furniture.'},
 {id:'natural',ar:'دفء طبيعي',en:'Natural warmth',description:'خامات طبيعية ودرجات دافئة تشعرك بالراحة.',palette:['#c3a184','#dfd3b7','#706d4e'],prompt:'Warm natural design: light oak, earthy clay, linen textures, organic shapes, tranquil natural materials, practical furnishings.'},
 {id:'elegant',ar:'أناقة متوازنة',en:'Understated elegance',description:'تفاصيل مدروسة ولمسة فخامة بهدوء.',palette:['#bdb4a7','#554d43','#b99964'],prompt:'Understated elegant design: sophisticated stone, walnut, restrained brass details, rich textures and timeless forms. No ostentation.'}
];
const clean = (v,n=240) => String(v??'').replace(/[\u0000-\u001f]/g,' ').trim().slice(0,n);
export function safeUrl(value){try{const u=new URL(value);return u.protocol==='https:'&&!u.username&&!u.password?u.href:null;}catch{return null;}}
export function numericPrice(v){
 if(typeof v==='number')return Number.isFinite(v)&&v>0?v:null;
 let s=String(v??'').trim().replace(/[٠-٩]/g,c=>String(c.charCodeAt(0)-1632)).replace(/٫/g,'.').replace(/٬/g,',');
 if(!/^\d[\d,. ]*$/.test(s))return null;
 s=s.replace(/ /g,'');
 if(s.includes(',')&&s.includes('.')){
   if(s.lastIndexOf(',')>s.lastIndexOf('.')){if(!/^\d{1,3}(?:\.\d{3})+,\d{1,3}$/.test(s))return null;s=s.replace(/\./g,'').replace(',','.');}
   else {if(!/^\d{1,3}(?:,\d{3})+\.\d{1,3}$/.test(s))return null;s=s.replace(/,/g,'');}
 }else if(/,\d{1,2}$/.test(s)&&!s.includes('.'))s=s.replace(',','.');else s=s.replace(/,/g,'');
 const n=Number(s);return Number.isFinite(n)&&n>0&&n<1e8?n:null;
}
export function priceText(s,currency){
 const codes={KWD:'KWD|KD|د\\.?\\s?ك',SAR:'SAR|ر\\.?\\s?س',AED:'AED|د\\.?\\s?إ',QAR:'QAR|ر\\.?\\s?ق',BHD:'BHD|د\\.?\\s?ب',OMR:'OMR|ر\\.?\\s?ع',GBP:'GBP|£',USD:'USD|US\\$|\\$',EUR:'EUR|€',JPY:'JPY|¥'};
 const token=codes[currency];if(!token)return null;
 const number='([0-9٠-٩][0-9٠-٩,٫٬.]*)';
 const text=String(s||'');
 const m=text.match(new RegExp('(?:'+token+')\\s*'+number,'i'))||text.match(new RegExp(number+'\\s*(?:'+token+')','i'));
 return m?numericPrice(m[1]):null;
}
export function localEvidence(url,market){
 try{const u=new URL(url),m=MARKETS[market],h=u.hostname.toLowerCase(),p=u.pathname.toLowerCase();
 const suffix={GB:'uk',US:'us'}[market]||market.toLowerCase();
 if(market==='KW'&&['safathome.com','www.safathome.com','rullart.com','karazonline.com'].includes(h))return true;
 if(h.endsWith('.'+suffix))return true;
 return new RegExp('(?:^|[./_-])(?:'+market.toLowerCase()+'|'+m.en.toLowerCase().replaceAll(' ','-')+')(?:[./_-]|$)').test(h+p);
 }catch{return false;}
}
export function publicIP(ip){
 if(net.isIP(ip)===4){const a=ip.split('.').map(Number);return !(a[0]===0||a[0]===10||a[0]===127||a[0]>=224||a[0]===169&&a[1]===254||a[0]===172&&a[1]>=16&&a[1]<=31||a[0]===192&&a[1]===168||a[0]===100&&a[1]>=64&&a[1]<=127||a[0]===198&&(a[1]===18||a[1]===19));}
 // Fetch IPv4 only. Reject IPv6 and mapped IPv4 to avoid ambiguous routing.
 return false;
}
export async function safeResource(url,{image=false,depth=0,timeout=6500}={}){
 const target=safeUrl(url);if(!target||depth>3)throw Error('unsafe_url');
 const u=new URL(target);if(u.port&&u.port!=='443')throw Error('unsafe_port');
 const records=await dns.lookup(u.hostname,{all:true,family:4});
 if(!records.length||records.some(r=>!publicIP(r.address)))throw Error('unsafe_address');
 const record=records[0];
 return new Promise((resolve,reject)=>{
   const req=https.get(u,{headers:{'User-Agent':'Mozilla/5.0 (compatible; FindziaSpaces/0.1)','Accept':image?'image/*':'text/html,application/xhtml+xml','Accept-Encoding':'identity'},lookup:(_h,opts,cb)=>opts.all?cb(null,[record]):cb(null,record.address,4),timeout},res=>{
     if([301,302,303,307,308].includes(res.statusCode)){res.resume();if(!res.headers.location)return reject(Error('redirect'));return safeResource(new URL(res.headers.location,u).href,{image,depth:depth+1,timeout}).then(resolve,reject);}
     if(res.statusCode!==200||!(image?/^image\/(jpeg|png|webp)/i.test(String(res.headers['content-type'])):String(res.headers['content-type']).includes('text/html'))){res.resume();return reject(Error('no_page_'+res.statusCode));}
     let chunks=[],size=0;res.on('data',b=>{size+=b.length;if(size>(image?6000000:3000000)){req.destroy();reject(Error('page_large'));}else chunks.push(b);});
     res.on('end',()=>resolve({bytes:Buffer.concat(chunks),html:image?undefined:Buffer.concat(chunks).toString('utf8'),mime:String(res.headers['content-type']).split(';')[0],url:u.href}));res.on('error',reject);
   });req.on('error',reject);req.on('timeout',()=>req.destroy(Error('timeout')));
 });
}
export const safePage=(url,options)=>safeResource(url,options);
export const safeImage=url=>safeResource(url,{image:true});
function unescapeHTML(v){return String(v||'').replace(/&quot;/g,'"').replace(/&amp;/g,'&').replace(/&#39;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>');}
function meta(html,key){
 for(const tag of html.matchAll(/<meta\b[^>]*>/gi)){
 const attrs={};for(const a of tag[0].matchAll(/([\w:-]+)\s*=\s*["']([^"']*)["']/g))attrs[a[1].toLowerCase()]=unescapeHTML(a[2]);
 if((attrs.property||attrs.name||'').toLowerCase()===key)return attrs.content||'';
 }return '';
}
export function productPath(url){try{const u=new URL(url);return !/\/(?:collections|categories|search|blog|blogs|tag)(?:[/?]|$)/i.test(u.pathname)&&(/\/(?:products?|p|item|itm|listing|dp|pd|ip|goods|buy-[^/]+)(?:[/-]|$)|\.html$/i.test(u.pathname)||/(?:^|\.)1688\.com$/.test(u.hostname)&&/^\/offer\/\d+/.test(u.pathname)||/(?:^|\.)taobao\.com$/.test(u.hostname)&&u.pathname==='/item.htm'&&/^\d+$/.test(u.searchParams.get('id')||''));}catch{return false;}}
function dimension(v){if(!v)return '';if(typeof v==='object')return clean([v.value,v.unitText||v.unitCode].filter(Boolean).join(' '),80);return clean(v,80);}
export function productFromPage(html,url,currency){
 const data=readProductData(html,url);if(data.ambiguous||data.variantUnconfirmed)return null;
 const product=data.schema;
 if(!product&&!(productPath(url)&&(/product/i.test(meta(html,'og:type'))||/add to (?:cart|bag|basket)|buy now|أضف للسلة/i.test(html))))return null;
 const offers=product?(Array.isArray(product.offers)?product.offers:[product.offers]).filter(Boolean):[];
 // Keep a store listing with no price, but never make up a zero price or convert currencies.
 const offer=offers.find(o=>o.priceCurrency===currency)||offers[0]||{};
 const pageCurrency=String(offer.priceCurrency||meta(html,'product:price:currency')||'').toUpperCase();
 const price=numericPrice(offer.price||meta(html,'product:price:amount'));
 const img=product?(Array.isArray(product.image)?product.image[0]:product.image):meta(html,'og:image')||data.primaryImage;
 const image=safeUrl((typeof img==='object'?img?.url:img)||data.images[0]||data.primaryImage);
 const title=clean(unescapeHTML(product?.name||meta(html,'og:title')||data.primaryTitle),180);
 if(!title||!image)return null;
 const props=Array.isArray(product?.additionalProperty)?product.additionalProperty:[];
 const dimensions=[['Width',product?.width],['Height',product?.height],['Depth',product?.depth],...props.filter(p=>/dimension|width|height|depth|length|diameter/i.test(p.name||'')).slice(0,4).map(p=>[p.name,p.value])].filter(x=>x[1]).map(([k,v])=>k+': '+dimension(v)).join(' · ');
 const details=dimensionDetails(html,product||{name:title},url,data),dimensions_cm=details.size;
 return {title,product_images:data.images,variant_unconfirmed:data.variantUnconfirmed,dimensions_evidence:details.evidence,dimensions_status:details.status,dimensions_cm,dimensions_source:Object.keys(dimensions_cm).length?'store_product_page':null,price:pageCurrency&&price?price:null,currency:pageCurrency||null,link:url,image,source:new URL(url).hostname.replace(/^www\./,''),evidence:'product_page',...availabilityFromPage(html,url),description:clean(unescapeHTML(product?.description||meta(html,'og:description')).replace(/<[^>]+>/g,' '),1400),color:clean(product?.color||data.rows.find(x=>/^(?:colou?r)$/i.test(x.label))?.value,90),material:clean(product?.material||data.rows.find(x=>/^(?:materials?|material details)$/i.test(x.label))?.value,90),dimensions:clean(dimensionLabel(dimensions_cm)||dimensions,300),sku:clean(data.sku||product?.sku,100)};
}
export function sanitizeItems(data,{keep=''}={}){
 return (Array.isArray(data?.items)?data.items:[]).slice(0,28).map((x,i)=>{
 let box=Array.isArray(x.box)&&x.box.length===4?x.box.map(n=>Math.min(1000,Math.max(0,Number(n)||0))):[200,200,600,600];
 const [y1,x1,y2,x2]=box;box=[Math.min(y1,y2),Math.min(x1,x2),Math.max(y1,y2),Math.max(x1,x2)];
 const mode=x.mode==='keep'&&!String(keep).trim()?'ready':['ready','measure','quote','keep'].includes(x.mode)?x.mode:'ready';
 const specs={};for(const k of ['category','color','material','texture','shape','configuration','legs','details','scale'])specs[k]=clean(x.specs?.[k],220);
 return {id:String(i+1),name:clean(x.name_en||x.name_ar,70)||'Item '+(i+1),name_en:clean(x.name_en,70),query:clean(x.query_en,220),native_query:clean(x.query_native,220),chinese_query:clean(x.query_zh,220),description:clean(x.description_en||x.description_ar,500),specs,mode,quantity:mode==='ready'?Math.max(1,Math.min(12,Math.round(Number(x.quantity)||1))):null,box,status:mode==='keep'?'kept':'idle',offers:[],alternatives:[],size_verified:false};
 }).filter(x=>x.name_en&&x.query);
}
export async function configureModels(env=process.env){
 if(!env.GEMINI_API_KEY)return;
 try{
  const r=await fetch('https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000',{headers:{'x-goog-api-key':env.GEMINI_API_KEY},signal:AbortSignal.timeout(20000)});
  if(!r.ok){console.error('SPACES_MODEL_LIST_HTTP',r.status);return;}
  const data=await r.json();const models=(data.models||[]).filter(x=>x.supportedGenerationMethods?.includes('generateContent')).map(x=>x.name.replace(/^models\//,''));
  const textPreferences=[env.SPACES_TEXT_MODEL,'gemini-3.8-flash','gemini-3.5-flash-lite','gemini-3-flash-preview','gemini-2.5-flash','gemini-2.0-flash'];
  const imagePreferences=[env.SPACES_IMAGE_MODEL,'gemini-nano-banana-2.1','gemini-3.1-flash-image','gemini-3.1-flash-image-preview','gemini-3-pro-image','gemini-3-pro-image-preview','gemini-2.5-flash-image'];
  const text=textPreferences.find(x=>models.includes(x))||models.find(x=>/^gemini.*flash/.test(x)&&!/image|tts|live|audio|robot/.test(x));
  const image=imagePreferences.find(x=>models.includes(x))||models.find(x=>/^gemini.*image/.test(x));
  if(text)env.SPACES_TEXT_MODEL=text;if(image)env.SPACES_IMAGE_MODEL=image;
  console.log('SPACES_MODELS',JSON.stringify({text:env.SPACES_TEXT_MODEL,image:env.SPACES_IMAGE_MODEL,available:models.filter(x=>/gemini/.test(x)).slice(0,35)}));
 }catch(e){console.error('SPACES_MODEL_LIST_FAILED',e.name);}
}
export async function gemini(parts,{image=false,env=process.env,json=false,timeout,maxTokens=14000,schema,jsonRetry=0}={}){
 if(!env.GEMINI_API_KEY)throw Error('GEMINI_NOT_CONFIGURED');
 const model=image?(env.SPACES_IMAGE_MODEL||'gemini-nano-banana-2.1'):(env.SPACES_TEXT_MODEL||'gemini-3.8-flash');
 const config=image?{responseModalities:['TEXT','IMAGE']}:{temperature:0.2,maxOutputTokens:maxTokens,...(json?{responseMimeType:'application/json'}:{})};
 // Keep the same vision model; bounded reasoning avoids spending the deadline on hidden thought tokens.
 if(!image&&/^gemini-3/.test(model))config.thinkingConfig={thinkingLevel:'low'};
 if(json&&schema){const convert=value=>{if(Array.isArray(value))return value.map(convert);if(!value||typeof value!=='object')return value;const result=Object.fromEntries(Object.entries(value).map(([k,v])=>[k,convert(v)]));if(Array.isArray(value.type)){result.type=value.type.find(x=>x!=='null').toUpperCase();result.nullable=value.type.includes('null');}else if(typeof value.type==='string')result.type=value.type.toUpperCase();return result;};config.responseSchema=convert(schema);}
 const response=await fetch('https://generativelanguage.googleapis.com/v1beta/models/'+encodeURIComponent(model)+':generateContent',{method:'POST',headers:{'Content-Type':'application/json','x-goog-api-key':env.GEMINI_API_KEY},body:JSON.stringify({contents:[{role:'user',parts}],generationConfig:config}),signal:AbortSignal.timeout(timeout||(image?170000:65000))});
 if(!response.ok){let detail='';try{const e=await response.json();detail=String(e.error?.message||'').replaceAll(env.GEMINI_API_KEY,'[redacted]').slice(0,220);}catch{}console.error('SPACES_GEMINI_HTTP',response.status,model,detail);if(response.status===400&&schema){console.log('SPACES_SCHEMA_FALLBACK');return gemini(parts,{image,env,json,timeout,maxTokens,jsonRetry});}throw Error(response.status===429?'PROVIDER_BUSY':response.status===400||response.status===404?'MODEL_UNAVAILABLE':'GENERATION_FAILED');}
 const data=await response.json(),out=data.candidates?.[0]?.content?.parts||[];
 if(image){const img=out.find(x=>x.inlineData?.mimeType?.startsWith('image/'));if(!img)throw Error('NO_IMAGE');return img.inlineData;}
 const text=out.filter(x=>!x.thought).map(x=>x.text||'').join('');
 if(!json)return text;
 try{return JSON.parse(text.replace(/^```(?:json)?\s*/,'').replace(/\s*```$/,''));}
 catch(e){console.log('SPACES_JSON_INCOMPLETE',JSON.stringify({finish:data.candidates?.[0]?.finishReason,characters:text.length,retry:jsonRetry}));if(jsonRetry<1)return gemini(parts,{image,env,json,timeout,maxTokens:Math.max(22000,maxTokens*2),schema,jsonRetry:1});throw Error('INCOMPLETE_ANALYSIS');}
}
export async function serper(q,market,{shopping=false,images=false,lang='en',env=process.env}={}){
 if(!env.SERPER_API_KEY)throw Error('SEARCH_NOT_CONFIGURED');
 const r=await fetch('https://google.serper.dev/'+(images?'images':shopping?'shopping':'search'),{method:'POST',headers:{'Content-Type':'application/json','X-API-KEY':env.SERPER_API_KEY},body:JSON.stringify({q,gl:market.toLowerCase(),hl:lang,num:10}),signal:AbortSignal.timeout(12000)});
 if(!r.ok)throw Error('SEARCH_PROVIDER_'+r.status);return r.json();
}
