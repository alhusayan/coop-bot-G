import {measurementText} from './room-measure-copy.js';
import {furnishingText} from './furnishing-copy.js';
export function createRoomMeasure({context,language,api,showSheet,escape:esc,safe,onUse}){
 let epoch=0;
 return async function openMeasurement(){
  const token=++epoch,c=context();if(!c.job||c.job.demo)return;
  const t=k=>measurementText(language(),k),url='/api/jobs/'+c.job.id+'/measure';
  let state={status:'analyzing'},points=[],active=0,result=null,revision=0,calculating=false;
  showSheet(`<div class="sheet-body room-measure-form" data-no-i18n><h2>${esc(t('title'))}</h2><p>${esc(t('intro'))}</p><div class="measure-photo"><img src="${esc(safe(c.job.original))}" alt="${esc(t('title'))}" draggable="false"><svg viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-hidden="true"></svg></div><div class="measure-tools"><div class="measure-point-buttons" role="group">${[1,2,3].map((n,i)=>`<button type="button" data-point="${i}" aria-pressed="${i===0}">${n}</button>`).join('')}</div><button type="button" data-reset>${esc(t('reset'))}</button></div><label class="measure-reference">${esc(t('reference'))}<input name="reference" type="number" inputmode="decimal" min="0.3" max="15" step="0.01" placeholder="3.00"></label><p class="measure-status" role="status" aria-live="polite">${esc(t('loading'))}</p><button type="button" class="primary wide" data-calculate disabled>${esc(t('calculate'))}</button><div class="measure-result" hidden></div><p class="furnish-note">${esc(t('note'))}</p></div>`,'measurement');
  const root=document.querySelector('.room-measure-form'),photo=root.querySelector('.measure-photo'),svg=photo.querySelector('svg'),input=root.querySelector('input'),status=root.querySelector('.measure-status'),calc=root.querySelector('[data-calculate]'),output=root.querySelector('.measure-result');
  const alive=()=>token===epoch&&root.isConnected&&context().job?.id===c.job.id;
  function refresh(){
   svg.innerHTML=`${points.length>1?`<polyline points="${points.map(p=>p.map(x=>x*1000).join(',')).join(' ')}"/>`:''}${points.map((p,i)=>`<circle cx="${p[0]*1000}" cy="${p[1]*1000}" r="21"/><text x="${p[0]*1000}" y="${p[1]*1000}" text-anchor="middle" dominant-baseline="central">${i+1}</text>`).join('')}`;
   root.querySelectorAll('[data-point]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.point)===active)));
   calc.disabled=calculating||state.status!=='ready'||points.length!==3||!Number.isFinite(Number(input.value))||Number(input.value)<.3||Number(input.value)>15;
   result=null;output.hidden=true;
  }
  // A click does not move a corner when the visitor swipes to scroll.
  photo.addEventListener('click',e=>{
   if(e.button!==0)return;const rect=photo.getBoundingClientRect();
   const p=[Math.min(.999,Math.max(.001,(e.clientX-rect.left)/rect.width)),Math.min(.999,Math.max(.001,(e.clientY-rect.top)/rect.height))];
   points[Math.min(active,points.length)]=p;active=Math.min(points.length,2);revision++;refresh();
  });
  root.querySelectorAll('[data-point]').forEach(b=>b.addEventListener('click',()=>{active=Number(b.dataset.point);refresh();}));
  root.querySelector('[data-reset]').addEventListener('click',()=>{points=[];active=0;revision++;refresh();});input.addEventListener('input',()=>{revision++;refresh();});
  calc.addEventListener('click',async()=>{
   if(calc.disabled)return;const submittedRevision=revision;calculating=true;calc.disabled=true;status.textContent=t('loading');
   try{
    const value=await api(url,{method:'POST',body:JSON.stringify({action:'calculate',points,reference:Number(input.value)})});if(!alive()||revision!==submittedRevision)return;
    state=value;result=value.result;status.textContent='';
    output.innerHTML=`<div class="measure-result-dimensions" dir="ltr">≈ ${result.width/100} × ${result.length/100} m</div><div class="furnish-area"><span>${esc(t('area'))}</span><strong dir="ltr">≈ ${result.area_m2} m²</strong></div><button type="button" class="primary wide" data-use>${esc(t('use'))}</button>`;output.hidden=false;
    output.querySelector('[data-use]').addEventListener('click',()=>{if(result)onUse({...result,measurement_id:state.id});});
   }catch(e){if(alive()&&revision===submittedRevision)status.textContent=t(/^MEASUREMENT_(?:UNAVAILABLE|BUSY)/.test(e.code||'')?'unavailable':'problem');}
   finally{calculating=false;if(alive()){if(revision!==submittedRevision){status.textContent='';refresh();}else calc.disabled=false;}}
  });
  try{
   state=await api(url,{method:'POST',body:JSON.stringify({action:'analyze'})});
   while(alive()&&state.status==='analyzing'){
    await new Promise(resolve=>setTimeout(resolve,1800));if(!alive())return;state=await api(url);
   }
   if(!alive())return;
   if(state.status!=='ready')throw Error('MEASUREMENT_UNAVAILABLE');
   if(!points.length){points=state.result?.points?.map(p=>[...p])||state.points||[];active=Math.min(points.length,2);}
   if(state.result?.reference_m)input.value=state.result.reference_m;
   status.textContent=t('ready');
   if(state.image){const map=document.createElement('details');map.className='furnish-depth measure-depth';map.innerHTML=`<summary>${esc(furnishingText(language(),'depthTitle'))}</summary><img src="${esc(safe(state.image))}" alt="${esc(furnishingText(language(),'depthTitle'))}">`;status.after(map);}
   refresh();
  }catch{if(alive()){state.status='error';status.textContent=t('unavailable');calc.disabled=true;}}
 };
}
