// Read public product evidence, including closed accordions and server hydration.
// Never evaluate scripts or combine recommendations/other variants with the selected SKU.
import {parseHTML} from 'linkedom';
export const DETAILS_VERSION=1;
const arr=v=>v==null?[]:Array.isArray(v)?v:[v];
export const plain=v=>String(v??'').replace(/<[^>]*>/g,' ').replace(/&nbsp;|&#160;/g,' ').replace(/&amp;/g,'&').replace(/[\u200e\u200f\u202a-\u202e]/g,'').replace(/\s+/g,' ').trim();
export function productURL(value,base){
 try{const u=new URL(value,base);for(const k of [...u.searchParams.keys()])if(/^(?:utm_.+|srsltid|gclid|fbclid|ref|ref_)$/i.test(k))u.searchParams.delete(k);u.hash='';u.hostname=u.hostname.replace(/^www\./,'');u.pathname=u.pathname.replace(/\/$/,'');u.searchParams.sort();return u.href;}catch{return '';}
}
export function imageKey(value){try{const u=new URL(value);for(const k of [...u.searchParams.keys()])if(/^(?:w|h|width|height|qlt|quality|fmt|format|fit|crop|resize|sm|v)$/i.test(k))u.searchParams.delete(k);u.searchParams.sort();return u.href;}catch{return '';}}
function urlSKU(url){try{return decodeURIComponent(new URL(url).pathname.match(/\/(?:p|dp|item|itm)\/([^/]+)\/?$/i)?.[1]||'').replace(/\.html$/,'');}catch{return '';}}
function ids(p){return [p?.sku,p?.productID,p?.productId,p?.code,p?.id,p?.mpn].filter(x=>typeof x==='string'||typeof x==='number').map(String);}
function sameProduct(p,url,sku){return !!(sku&&ids(p).includes(sku)||[p.url,p['@id'],p.canonicalUrl,p.selfCanonical].some(v=>v&&productURL(v,url)===productURL(url)));}
function variantID(url){try{const u=new URL(url);return u.searchParams.get('variant')||u.searchParams.get('sku')||u.searchParams.get('sku_id')||'';}catch{return '';}}
const forbidden=/recommend|related|crosssell|upsell|recently|translation|review|cart|navigation|similar|sponsored|compare|packag|shipping|delivery/i;
function gallery(p){return arr(p?.image).concat(arr(p?.images),arr(p?.media),arr(p?.assets),arr(p?.primaryAsset)).flatMap(v=>typeof v==='string'?[v]:[v?.url,v?.src,v?.contentUrl]).filter(x=>/^https:\/\//.test(x||''));}
function propertyRows(node,rows=[],path='',depth=0){
 if(!node||typeof node!=='object'||depth>12||rows.length>180)return rows;
 if(Array.isArray(node)){node.forEach(x=>propertyRows(x,rows,path,depth+1));return rows;}
 const label=node.nameLabel||node.label||node.name||node.key;
 if(label&&['string','number'].includes(typeof node.value))rows.push({label:plain(label),value:plain(node.value),unit:node.unitText||node.unitCode,source:'product_state',section:path});
 for(const [k,v] of Object.entries(node))if(!forbidden.test(k)&&typeof v==='object')propertyRows(v,rows,path+' '+(node.label||node.groupDisplayName||k),depth+1);
 return rows;
}
function blockedNode(node){for(let p=node;p;p=p.parentElement){if(forbidden.test([p.id,p.className,p.getAttribute?.('aria-label')].join(' ')))return true;}return false;}
export function readProductData(html,url){
 const {document}=parseHTML(String(html));const schemas=[],states=[];
 function walk(v,ld=false,path='',depth=0){
  if(!v||typeof v!=='object'||depth>22||states.length>1500)return;
  if(Array.isArray(v)){v.slice(0,300).forEach(x=>walk(x,ld,path,depth+1));return;}
  if(ld&&arr(v['@type']).includes('Product'))schemas.push(v);
  if(!ld&&(v.name||v.title||v.sku||v.code)&&(v.sku||v.sections||v.productAttributeDetails||v.variants||v.additionalProperty))states.push({value:v,path});
  if(ld){for(const k of ['@graph','mainEntity','hasVariant'])if(v[k])walk(v[k],true,path+'.'+k,depth+1);}
  else for(const [k,x] of Object.entries(v))if(!forbidden.test(k)){
   if(k==='initialState'&&typeof x==='string'&&x.length<4000000){try{walk(JSON.parse(Buffer.from(x,'base64').toString('utf8')),false,path+'.decodedState',depth+1);}catch{}}
   else if(typeof x==='object')walk(x,false,path+'.'+k,depth+1);
  }
 }
 for(const s of document.querySelectorAll('script[type="application/ld+json"],script[type="application/json"]')){try{walk(JSON.parse(s.textContent),s.getAttribute('type')==='application/ld+json');}catch{}}
 const sku=urlSKU(url),variant=variantID(url),matched=schemas.filter(p=>sameProduct(p,url,sku));
 const variantSchemas=variant?schemas.filter(p=>ids(p).includes(variant)):[];
 const schema=variantSchemas.length===1?variantSchemas[0]:matched.length===1?matched[0]:schemas.length===1?schemas[0]:null;
 const identitySku=sku||String(schema?.sku||schema?.productID||'');
 const hits=states.filter(x=>sameProduct(x.value,url,identitySku)||identitySku&&arr(x.value.variants).some(v=>ids(v).includes(identitySku)));
 // Prefer the primary product record over nested variant records sharing a SKU.
 hits.sort((a,b)=>Number(/\.meta\.product$|\.productPageReducerBL\.data$|\.product$/.test(b.path))-Number(/\.meta\.product$|\.productPageReducerBL\.data$|\.product$/.test(a.path))||a.path.length-b.path.length);
 let selected=hits[0]?.value;
 if(!selected){const primary=states.filter(x=>/\.meta\.product$|\.productPageReducerBL\.data$|\.product$/.test(x.path)&&schema&&x.value.name===schema.name);if(primary.length===1)selected=primary[0].value;}
 const variants=arr(selected?.variants||selected?.hasVariant);
 const chosenVariant=variant?variants.find(v=>ids(v).includes(variant)):variants.find(v=>ids(v).includes(identitySku));
 const pageVariantConfirmed=!!variant&&(ids(schema).includes(variant)||[schema?.url,...arr(schema?.offers).map(o=>o.url)].some(u=>u&&variantID(u)===variant&&productURL(u,url)===productURL(url)));
 const variantUnconfirmed=!!variant&&!chosenVariant&&!pageVariantConfirmed;
 const rows=[];
 if(schema&&!variantUnconfirmed&&(!variant||pageVariantConfirmed)){for(const p of arr(schema.additionalProperty))propertyRows(p,rows,'product schema');}
 if(selected&&!variantUnconfirmed){
   // Multiple size variants: only variant-specific attributes are safe unless this is an exact SKU page.
   const safeBase=variants.length<=1||ids(selected).includes(identitySku)&&!variant;
   if(safeBase)for(const k of ['sections','productAttributeDetails','attributes','specifications','additionalProperty','dimensions'])propertyRows(selected[k],rows,k);
   if(chosenVariant)for(const k of ['variantAttributeDetails','attributes','specifications','additionalProperty','dimensions'])propertyRows(chosenVariant[k],rows,'variant '+k);
 }
 for(const row of document.querySelectorAll('tr')){
   if(blockedNode(row)||variantUnconfirmed||variant&&!pageVariantConfirmed)continue;
   const cells=[...row.children].filter(n=>/^(TD|TH)$/.test(n.tagName));
   if(cells.length===2){const label=plain(cells[0].textContent),value=plain(cells[1].textContent);if(label.length<100&&value.length<1000)rows.push({label,value,source:'specification_table'});}
 }
 for(const dt of document.querySelectorAll('dt'))if(!blockedNode(dt)&&dt.nextElementSibling?.tagName==='DD'&&!variantUnconfirmed&&(!variant||pageVariantConfirmed))rows.push({label:plain(dt.textContent),value:plain(dt.nextElementSibling.textContent),source:'specification_list'});
 const texts=[];
 for(const node of document.querySelectorAll('[id^="ProductSpecifications"],[id^="ProductDimensions"],[id="productDescription"],[id="product-details"],[id="productDetails"],[id="detailBullets_feature_div"],[id="product-information"],[itemprop="description"]'))if(!blockedNode(node)&&!variantUnconfirmed&&(!variant||pageVariantConfirmed))texts.push(plain(node.textContent).slice(0,10000));
 const images=[...new Set(variant?[...gallery(chosenVariant),...(ids(schema).includes(variant)?gallery(schema):[])]:[...gallery(schema),...gallery(selected),...gallery(chosenVariant)])].slice(0,30);
 const skuRow=rows.find(r=>/^(?:ASIN|SKU|Article Number|Product Code|Item Number)$/i.test(r.label));
 const confirmedSku=String(chosenVariant?.sku||schema?.sku||skuRow?.value||selected?.sku||'');
 const titleNode=document.querySelector('#productTitle')||document.querySelector('h1');
 const primaryTitle=plain(titleNode?.textContent);
 const primaryImg=document.querySelector('#landingImage')||document.querySelector('[itemprop="image"]');
 const primaryImage=primaryImg?.getAttribute('data-old-hires')||primaryImg?.getAttribute('src')||'';
 for(const n of document.querySelectorAll('script,style,template,noscript'))n.remove();
 for(const n of document.querySelectorAll('[id],[class]'))if(forbidden.test([n.id,n.className].join(' ')))n.remove();
 const visibleText=variant&&!pageVariantConfirmed?'':plain(document.toString());
 const scopedSchema=variant&&chosenVariant&&!pageVariantConfirmed?{...chosenVariant,name:selected?.name||schema?.name,image:gallery(chosenVariant)[0],sku:chosenVariant.sku||chosenVariant.id}:schema;
 return {schema:scopedSchema,selected,rows,texts,images,primaryTitle,primaryImage,visibleText,sku:confirmedSku,variantUnconfirmed,ambiguous:schemas.length>1&&!schema};
}
export function sameOfferProduct(offer,product){
 if(!product||product.variant_unconfirmed)return false;
 const requested=variantID(offer.link);if(requested&&productURL(offer.link)!==productURL(product.link))return false;
 if(offer.sku&&product.sku&&String(offer.sku)!==String(product.sku))return false;
 const sku=urlSKU(offer.link);
 if(/^(?:[0-9]{4,}|B[A-Z0-9]{9})$/.test(sku)&&product.sku&&sku!==String(product.sku))return false;
 if(sku&&product.sku===sku||offer.sku&&String(offer.sku)===String(product.sku))return true;
 return !!imageKey(offer.image)&&[product.image,...(product.product_images||[])].some(x=>imageKey(x)===imageKey(offer.image));
}
