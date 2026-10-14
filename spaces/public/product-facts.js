// Listing evidence is a fallback while the exact merchant page is read.
// Enrichment never changes native search results, prices, ranking or credits.
import {productKey} from './design-picks.js';
import {summarizeFacts,groupProductFacts} from './product-summary.js';
const clean=value=>typeof value==='string'||typeof value==='number'?String(value).replace(/\s+/g,' ').trim().slice(0,180):'';
const kinds={color:'Colour',colour:'Colour',material:'Material',materials:'Material',dimensions:'Dimensions',size:'Size',width:'Width',height:'Height',depth:'Depth',length:'Length',diameter:'Diameter',finish:'Finish',brand:'Brand',shape:'Shape',pattern:'Pattern',configuration:'Configuration'};
const pageKinds={...kinds,care:'Care',assembly:'Assembly',origin:'Country of origin',weight:'Weight',capacity:'Capacity'};
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
export function createProductDetailsLoader({request,room,design,item,getLanguage,onUpdate,isActive=()=>true}){
 const entries=new Map(),controllers=new Set();let active=0,destroyed=false;
 const path='/api/jobs/'+room+'/product-details';
 const key=url=>getLanguage()+':'+productKey(url);
 const pause=(ms,signal)=>new Promise((resolve,reject)=>{
  signal.throwIfAborted();
  const abort=()=>{clearTimeout(timer);reject(signal.reason);};
  const timer=setTimeout(()=>{signal.removeEventListener('abort',abort);resolve();},ms);
  signal.addEventListener('abort',abort,{once:true});
 });
 async function load(url){
  const language=getLanguage(),id=key(url),controller=new AbortController();active++;controllers.add(controller);
  // An absolute limit includes the initial request, polling and connection time.
  // Results remain usable while each visible product's specifications arrive.
  const deadline=setTimeout(()=>controller.abort(),60000);
  entries.set(id,{status:'pending',facts:[]});
  try{
   let value=await request(path,{method:'POST',body:JSON.stringify({url,language,design,item}),signal:controller.signal});
   while(value.status==='pending'&&!destroyed){
    await pause(1200,controller.signal);if(destroyed)break;
    const next=await request(path+'/'+value.key,{signal:controller.signal});value={...next,key:value.key};
   }
   if(!destroyed)entries.set(id,value.status==='pending'||value.status==='busy'?{status:'unavailable',facts:[]}:value);
  }catch{if(!destroyed)entries.set(id,{status:'unavailable',facts:[]});}
  finally{clearTimeout(deadline);active--;controllers.delete(controller);if(!destroyed)onUpdate?.();}
 }
 return {
  peek:url=>entries.get(key(url)),
  scan(root){
   if(destroyed||!isActive())return;
   for(const card of root.querySelectorAll('[data-results-body] .fz-card-shell:not([data-spaces-visual="held"])')){
    if(active>=3)break;
    const url=productKey(card.querySelector('a.fz-tile')?.href);if(!url||entries.has(key(url)))continue;
    if(typeof card.getBoundingClientRect!=='function')continue;
    const rect=card.getBoundingClientRect(),height=root.ownerDocument.defaultView?.innerHeight||900;
    if(rect.bottom<=0||rect.top>height+250||!rect.width)continue;
    void load(url);
   }
  },
  destroy(){destroyed=true;for(const controller of controllers)controller.abort();}
 };
}
export function displayedFacts(row,page){
 if(!page?.facts?.length)return productFacts(row).filter(x=>x.value);
 const facts=page.facts.map(f=>({label:/^(color|material|width|height|depth|size|weight)$/i.test(f.label)?pageKinds[f.kind]:(f.label||pageKinds[f.kind]),value:f.value,kind:f.kind,quote:f.quote}));
 const present=new Set(facts.map(f=>pageKinds[f.kind]));
 for(const fallback of productFacts(row))if(fallback.value&&!present.has(fallback.label)&&!(['Width','Height','Depth','Length','Diameter'].includes(fallback.label)&&present.has('Dimensions')))facts.push(fallback);
 return facts;
}
export function syncProductFacts(root,rows=[],translate=value=>value,details){
 const byUrl=new Map(rows.map(row=>[productKey(row.url),row]));
 for(const card of root.querySelectorAll('[data-results-body] .fz-card-shell')){
  const link=card.querySelector('a.fz-tile'),body=card.querySelector('.fz-tile-body'),row=byUrl.get(productKey(link?.href));
  if(!body||!row)continue;
  const page=details?.peek(row.url),title=clean(row.title||row.raw_title),facts=summarizeFacts(displayedFacts(row,page),translate);
  const state=details?(page?.status||'pending'):'';
  const note=state==='pending'?'Reading store details…':'';
  const missing=translate('Not listed'),label=translate('Listed details'),signature=JSON.stringify([title,facts,missing,label,translate(note),state]);
  const old=body.querySelector('.spaces-product-facts');
  if(old?.dataset.facts===signature&&body.querySelector('.spaces-product-name'))continue;
  old?.remove();body.querySelector('.spaces-product-name')?.remove();body.querySelector('.spaces-product-source')?.remove();
  const doc=root.ownerDocument,name=doc.createElement('h3');name.className='spaces-product-name';name.textContent=title;name.dir='auto';name.setAttribute('translate','no');name.title=title;body.prepend(name);
  const list=doc.createElement('dl');list.className='spaces-product-facts';list.dataset.facts=signature;list.setAttribute('aria-label',label);list.setAttribute('translate','no');
  for(const fact of facts){const group=doc.createElement('div'),term=doc.createElement('dt'),value=doc.createElement('dd');term.textContent=fact.label;value.textContent=fact.value||missing;value.dir='auto';if(!fact.value)value.className='is-unspecified';group.append(term,value);list.append(group);}
  body.insertBefore(list,body.querySelector('.fz-store-row'));
  if(note){const source=doc.createElement('p');source.className='spaces-product-source';source.dataset.state=state;source.textContent=translate(note)||note;source.setAttribute('translate','no');if(state==='pending')source.setAttribute('role','status');body.insertBefore(source,body.querySelector('.fz-store-row'));}
 }
}

// Add the complete merchant specifications to the existing information dialog.
// Its buying insights, store link and original evaluation continue to work.
export function syncProductDetails(root,row,translate=value=>value,details){
 const dialog=root.querySelector('.fz-insights[open]'),body=dialog?.querySelector('.fz-insights-body');
 if(!body||!row)return;
 const page=details?.peek(row.url),groups=groupProductFacts(displayedFacts(row,page),translate);
 const state=page?.status||'pending';
 const note=state==='pending'?'Reading store details…':state==='ready'?(page?.retrieval==='indexed_merchant_page'?'Listed details':'From the product page'):state==='partial'?'Some details could not be retrieved':state==='empty'?'No specifications found on this page':'Details could not be retrieved';
 const signature=JSON.stringify([row.url,groups,state,translate(note)]);
 // Native listing facts are already merged into the sourced sections below.
 body.querySelector('.fz-insights-specs')?.remove();
 const heading=dialog.querySelector('.fz-insights-head h2');if(heading&&heading.textContent!==translate('Product details'))heading.textContent=translate('Product details');
 const exit=dialog.querySelector('.fz-insights-close');
 if(exit){exit.setAttribute('aria-label',translate('Done'));if(!exit.querySelector('svg'))exit.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg>';}
 const old=body.querySelector('.spaces-full-specs');if(old?.dataset.facts===signature)return;
 const doc=root.ownerDocument,section=doc.createElement('section');section.className='spaces-full-specs';section.dataset.facts=signature;section.setAttribute('translate','no');
 for(const group of groups){
  const block=doc.createElement('section'),label=doc.createElement('h3'),list=doc.createElement('dl');label.textContent=group.label;block.className='spaces-spec-group';block.append(label,list);
  for(const fact of group.facts){const entry=doc.createElement('div'),term=doc.createElement('dt'),value=doc.createElement('dd');term.textContent=translate(fact.label)||fact.label;value.textContent=fact.value;value.dir='auto';entry.append(term,value);list.append(entry);}
  section.append(block);
 }
 const source=doc.createElement('p');source.className='spaces-product-source';source.dataset.state=state;source.textContent=translate(note);if(state==='pending')source.setAttribute('role','status');section.append(source);
 if(old)old.replaceWith(section);else body.insertBefore(section,body.querySelector('.fz-insights-hero')?.nextSibling||body.firstChild);
}
