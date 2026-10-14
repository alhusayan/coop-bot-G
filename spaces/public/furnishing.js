import {furnishingText} from './furnishing-copy.js';
const phases=['products','curate','layout','render','verify'];
export const isFurnishing=run=>phases.includes(run?.status);
// Named controls such as "length" must not be read through form.elements.length:
// that property is the number of controls, not the customer's length input.
export function readFurnishingMeasurements(form){
 const read=name=>Number(String(form.querySelector(`[name="${name}"]`)?.value||'').replace(/[٠-٩]/g,c=>c.charCodeAt(0)-1632).replace(/[٫,]/g,'.'));
 const width=read('width'),length=read('length');
 if(![width,length].every(n=>Number.isFinite(n)&&n>=1.5&&n<=15))throw Object.assign(Error('ROOM_MEASUREMENTS_REQUIRED'),{code:'ROOM_MEASUREMENTS_REQUIRED'});
 return {width,length};
}
export function furnishingArea(room){return Math.round(room.width*room.length/10000*100)/100;}
export function furnishingFailureKey(run){
 if(run?.error!=='FURNISH_PRODUCTS_INCOMPLETE')return 'error';
 if(/credits_exhausted|credits_unavailable/.test(run.coverage?.stop_reason||''))return 'credits';
 const missing=new Set((run.coverage?.missing||[]).map(x=>String(x.id)));
 return run.diagnostics?.some(row=>(!missing.size||missing.has(String(row.id)))&&row.incompatible>0&&!row.missing_dimensions&&!row.stock_unknown)?'incompatible':'missing';
}
export function createFurnishing({context,language,translate,api,apply,showSheet,closeSheet,poll,escape:esc,safe,money,icon,patch}){
 const host=document.createElement('section');host.id='furnishing-option';host.className='furnishing-option';host.dataset.noI18n='';
 document.querySelector('#piece-feedback').before(host);
 const t=(key,count)=>furnishingText(language(),key,count);
 const mark='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 10 12 3l9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1zM7 15h10v6M7 15v-3h10v3M5 16v3m14-3v3"/></svg>';
 function area(room){return `<div class="furnish-area"><span>${esc(t('areaLabel'))}</span><strong dir="ltr">${furnishingArea(room)} m²</strong></div>`;}
 function analysis(run){
  if(!run?.room||run.room.source!=='customer')return '';
  const layout=run.layout;
  const plan=layout?`<div class="furnish-floor-plan"><h3>${esc(t('layoutTitle'))}</h3><svg viewBox="-25 -25 ${run.room.width+50} ${run.room.length+50}" role="img" aria-label="${esc(t('layoutTitle'))}"><rect class="floor" x="0" y="0" width="${run.room.width}" height="${run.room.length}" rx="6"/>${layout.obstacles.map(o=>`<rect class="obstacle" x="${o.x}" y="${o.z}" width="${o.w}" height="${o.d}"/>`).join('')}${layout.placements.map((p,i)=>`<g><rect class="piece piece-${p.layer||'floor'}" x="${p.x}" y="${p.z}" width="${p.w}" height="${p.d}" rx="8"/><text x="${p.x+p.w/2}" y="${p.z+p.d/2}" dominant-baseline="middle" text-anchor="middle">${i+1}</text></g>`).join('')}</svg><ol>${layout.placements.map(p=>`<li>${esc((run.products||[]).find(x=>x.id===(p.product_id||p.id))?.name||context().design?.items.find(x=>String(x.id)===p.id)?.name_en||'')} <span dir="ltr">${p.w} × ${p.d} cm</span></li>`).join('')}</ol></div>`:'';
  return `<section class="furnish-space-summary">${area(run.room)}${plan?`<details class="furnish-depth"><summary>${esc(t('layoutTitle'))}</summary>${plan}</details>`:''}</section>`;
 }
 function render(){
  const c=context(),run=c.design?.furnishing,busy=isFurnishing(run);host.hidden=!c.design?.image;
  const content=run?.status==='ready'&&run.version===2?`<div class="furnish-result"><div class="furnish-result-heading"><h2>${esc(t('ready'))}</h2><span>${icon('checkCircle',true)}</span></div><img class="furnish-result-photo" src="${esc(safe(run.image))}" alt="${esc(t('ready'))}"><p class="furnish-note">${esc(t('completeNote'))}</p>${run.coverage?.omitted?.length?`<p class="furnish-note">${esc(t('adapted'))}</p>`:''}<div class="furnish-products">${(run.products||[]).map(p=>`<a class="furnish-product" href="${esc(safe(p.offer.link))}" target="_blank" rel="noopener noreferrer sponsored"><img src="${esc(safe(p.offer.image))}" alt="${esc(p.offer.title)}" loading="lazy" referrerpolicy="no-referrer"><div><strong>${esc(p.offer.title)} <b dir="ltr">× ${p.quantity||1}</b></strong><small dir="auto">${esc([p.dimensions.width,p.dimensions.depth,p.dimensions.height].filter(Boolean).join(' × '))} cm</small><span>${esc(p.offer.price_label||money(p.offer.price,p.offer.currency))}</span><small>${esc(p.offer.source)}</small>${p.units_per_offer>1?`<small>${esc(t('packs',p.purchase_quantity))} · ${esc(t('unitsPerPack',p.units_per_offer))}</small>`:''}</div>${icon('external',true)}</a>`).join('')}</div></div>`:busy?`<div class="furnish-progress" role="status" aria-live="polite"><span class="search-spinner" aria-hidden="true"></span><strong>${esc(t(run.status))}</strong>${run.product_progress?`<span class="furnish-count" dir="ltr">${run.product_progress.found} / ${run.product_progress.total}</span>`:''}<div class="furnish-stages" aria-hidden="true">${phases.map((_,i)=>`<i class="${i<=phases.indexOf(run.status)?'complete':''}"></i>`).join('')}</div></div>`:run?.status==='error'?`<p class="furnish-note" role="status">${esc(t(furnishingFailureKey(run)))}</p>${run.coverage?.missing?.length?`<ul class="furnish-missing">${run.coverage.missing.map(x=>`<li>${esc(x.name)}</li>`).join('')}</ul>`:''}`:run?.status==='ready'?`<p class="furnish-note">${esc(t('legacy'))}</p>`:'';
  patch(host,`<button class="furnish-launch" data-furnish-open ${busy?'disabled':''}><span class="furnish-icon">${mark}</span><span><strong>${esc(t('title'))}</strong><small>${esc(t('teaser'))}</small></span>${icon('forward',true)}</button>${analysis(run)}${content}`);
 }
 let opening=0;
 async function open(){
  const epoch=++opening,c=context();if(!c.job||!c.design)return;
  showSheet(`<div class="sheet-body furnishing-form" data-no-i18n><h2>${esc(t('title'))}</h2><p>${esc(t('intro'))}</p><span class="search-spinner" role="status" aria-label="${esc(translate('Loading…'))}"></span></div>`,'furnishing');
  let quote;try{quote=await api('/api/jobs/'+c.job.id+'/furnish/'+c.index+'?market='+c.market);}catch{quote={items:[],searches:0};}
  const latest=context();if(epoch!==opening||latest.job?.id!==c.job.id||latest.index!==c.index||!document.querySelector('#sheet').open)return;
  const blocked=c.job.demo||!quote.items.length,previous=c.design.furnishing?.room,room=previous?.source==='customer'?previous:null;
  showSheet(`<div class="sheet-body furnishing-form" data-no-i18n><span class="furnish-form-icon">${mark}</span><h2>${esc(t('title'))}</h2><p>${esc(t('intro'))}</p><p class="furnish-note">${esc(t('adaptivePlan'))}</p><form id="furnishing-form"><div class="furnish-measurements"><label>${esc(translate('Width'))} (m)<input name="width" type="number" inputmode="decimal" min="1.5" max="15" step="0.01" required value="${room?.width/100||c.job.options.width||''}" placeholder="4.00"></label><label>${esc(translate('Length'))} (m)<input name="length" type="number" inputmode="decimal" min="1.5" max="15" step="0.01" required value="${room?.length/100||c.job.options.length||''}" placeholder="5.00"></label></div><p class="furnish-schedule">${esc(t('schedule',quote.quantity||quote.items.length))}</p><div class="furnish-cost">${esc(t(quote.searches?'cost':'free',quote.searches))}</div><p class="furnish-note">${esc(t(blocked?(c.job.demo?'demo':'missing'):'estimate'))}</p><p class="furnish-form-error" role="alert" hidden></p><button class="primary wide" type="submit" ${blocked?'disabled':''}>${esc(t('begin'))}${icon('spark',true)}</button></form></div>`,'furnishing');
  const form=document.querySelector('#furnishing-form');
  const areaPreview=document.createElement('div');areaPreview.className='furnish-area-preview';form.querySelector('.furnish-measurements').after(areaPreview);
  function updateArea(){try{const r=readFurnishingMeasurements(form);areaPreview.innerHTML=area({width:r.width*100,length:r.length*100,source:'customer'});}catch{areaPreview.innerHTML='';}}
  form.addEventListener('input',updateArea);updateArea();
  form.addEventListener('submit',async event=>{
   event.preventDefault();if(blocked||!form.reportValidity())return;const button=form.querySelector('button[type="submit"]');if(button.disabled)return;button.disabled=true;
   const error=form.querySelector('.furnish-form-error');error.hidden=true;
   try{
    const measurements=readFurnishingMeasurements(form);
    const auth=quote.searches?await document.querySelector('#findzia-home-spaces')?.fzBilling?.authorizePiece():{};
    if(quote.searches&&!auth){button.disabled=false;return;}
    const now=context();if(now.job?.id!==c.job.id||now.index!==c.index||now.market!==c.market)return;
    const job=await api('/api/jobs/'+c.job.id+'/furnish/'+c.index,{method:'POST',headers:auth,body:JSON.stringify({...measurements,market:c.market,language:language(),max_searches:quote.searches,request_id:crypto.randomUUID()})});
    if(context().job?.id!==c.job.id||context().index!==c.index)return;
    apply(job);closeSheet();render();poll();
   }catch(e){error.textContent=e.code==='FURNISH_PRODUCTS_INCOMPLETE'?t('missing'):e.code==='ROOM_MEASUREMENTS_REQUIRED'?t('invalidMeasurements'):e.message;error.hidden=false;button.disabled=false;}
  });
 }
 host.addEventListener('click',e=>{if(e.target.closest('[data-furnish-open]'))void open();});
 return {render,open};
}
