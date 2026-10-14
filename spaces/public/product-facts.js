// Display the original engine's listing evidence. No new search, inference,
// price transformation or image analysis runs here.
import {productKey} from './design-picks.js';
const clean=value=>typeof value==='string'||typeof value==='number'?String(value).replace(/\s+/g,' ').trim().slice(0,180):'';
const kinds={color:'Colour',colour:'Colour',material:'Material',materials:'Material',dimensions:'Dimensions',size:'Size',width:'Width',height:'Height',depth:'Depth',length:'Length',diameter:'Diameter',finish:'Finish',brand:'Brand',shape:'Shape',pattern:'Pattern',configuration:'Configuration'};
const absent=/^(?:unknown|none|null|n\/a|not specified|not stated|غير معروف|غير محدد)$/i;
// Some store titles state measurements that were not promoted to key_specs.
// Keep the exact written units and axis labels; do not estimate from the photo.
export function listedDimensions(title){
 const number=String.raw`\d+(?:[.,]\d+)?`,unit=String.raw`(?:mm|cm|m|inches|inch|in|ft|سم|مم|متر|بوصة|["″])`;
 const part=number+String.raw`\s*(?:-\s*)?`+unit+String.raw`(?!\p{L})\.?(?:\s+[LWDH]\b)?`;
 const repeated=new RegExp(String.raw`(?<![\p{L}\d])`+part+String.raw`\s*[x×]\s*`+part+String.raw`(?:\s*[x×]\s*`+part+')?','iu');
 const shared=new RegExp(String.raw`(?<![\p{L}\d])`+number+String.raw`\s*[x×]\s*`+number+String.raw`(?:\s*[x×]\s*`+number+String.raw`)?\s*`+unit+String.raw`(?!\p{L})`,'iu');
 const source=typeof title==='string'?title.slice(0,1200):'';
 const match=source.match(repeated)||source.match(shared);
 return match?match[0].trim():'';
}
export function productFacts(row={}){
 const values=new Map();
 const add=(kind,value)=>{kind=clean(kind).toLowerCase();value=clean(value);if(kinds[kind]&&value&&!absent.test(value)&&!values.has(kinds[kind]))values.set(kinds[kind],value);};
 // These attributes belong to this offer's structured store/listing data.
 const attributes=row.card_attributes||row.specifications||row.attributes||[];
 const entries=Array.isArray(attributes)?attributes:Object.entries(attributes).map(([name,value])=>({name,value}));
 for(const field of entries.slice(0,40))if(field&&typeof field==='object')add(field.name,field.value);
 for(const fact of (Array.isArray(row.key_specs)?row.key_specs:[])){
  if(!fact||!['structured','listing','candidate_title'].includes(fact.source))continue;
  add(fact.kind||fact.key,fact.value);
 }
 const profile=row.variant_profile?.facts;
 if(profile&&typeof profile==='object')for(const [kind,fact] of Object.entries(profile)){
  if(fact&&['structured','listing','candidate_title'].includes(fact.source))add(kind,fact.label);
 }
 add('brand',row.card_brand);
 // The engine also supplies a candidate profile. Accept only wording that
 // actually appears in this product's listing, never visual estimates.
 const title=clean(row.card_evidence_title||row.raw_title||row.title).toLocaleLowerCase();
 const candidate=row.card_candidate_profile||{};
 for(const key of ['material','dimensions','finish','shape','configuration']){
  const value=clean(candidate[key]);if(value&&title.includes(value.toLocaleLowerCase()))add(key,value);
 }
 const colors=Array.isArray(candidate.colors)?candidate.colors.filter(value=>typeof value==='string'&&value.trim()&&title.includes(value.toLocaleLowerCase())):[];
 if(colors.length)add('color',colors.join(' / '));
 if(!['Dimensions','Size','Width','Height','Depth','Length','Diameter'].some(key=>values.has(key)))add('dimensions',listedDimensions(row.card_evidence_title||row.raw_title||row.title));
 // Preserve axis labels and units; never invent an order, convert units or
 // treat image pixel dimensions as furniture measurements.
 const measured=['Dimensions','Size','Width','Height','Depth','Length','Diameter'].filter(key=>values.has(key)).map(key=>({label:key,value:values.get(key)}));
 return [
  {label:'Colour',value:values.get('Colour')||''},
  {label:'Material',value:values.get('Material')||''},
  ...(measured.length?measured:[{label:'Dimensions',value:''}]),
  ...['Finish','Brand','Shape','Pattern','Configuration'].filter(key=>values.has(key)).slice(0,2).map(key=>({label:key,value:values.get(key)}))
 ];
}
export function syncProductFacts(root,rows=[],translate=value=>value){
 const byUrl=new Map(rows.map(row=>[productKey(row.url),row]));
 for(const card of root.querySelectorAll('[data-results-body] .fz-card-shell')){
  const link=card.querySelector('a.fz-tile'),body=card.querySelector('.fz-tile-body'),row=byUrl.get(productKey(link?.href));
  if(!body||!row)continue;
  const title=clean(row.title||row.raw_title),facts=productFacts(row).map(fact=>({...fact,label:translate(fact.label)}));
  const missing=translate('Not listed'),label=translate('Listed details'),signature=JSON.stringify([title,facts,missing,label]);
  const old=body.querySelector('.spaces-product-facts');
  if(old?.dataset.facts===signature&&body.querySelector('.spaces-product-name'))continue;
  old?.remove();body.querySelector('.spaces-product-name')?.remove();
  const doc=root.ownerDocument,name=doc.createElement('h3');name.className='spaces-product-name';name.textContent=title;name.dir='auto';name.setAttribute('translate','no');name.title=title;body.prepend(name);
  const list=doc.createElement('dl');list.className='spaces-product-facts';list.dataset.facts=signature;list.setAttribute('aria-label',label);list.setAttribute('translate','no');
  for(const fact of facts){const group=doc.createElement('div'),term=doc.createElement('dt'),value=doc.createElement('dd');term.textContent=fact.label;value.textContent=fact.value||missing;value.dir='auto';if(!fact.value)value.className='is-unspecified';group.append(term,value);list.append(group);}
  body.insertBefore(list,body.querySelector('.fz-store-row'));
 }
}
