import {measurementText} from './room-measure-copy.js';
export function referenceErrorKey(code){
 if(code==='REFERENCE_TOO_SMALL')return 'smallError';
 if(code==='REFERENCE_SIZE_REQUIRED')return 'sizeError';
 if(code==='REFERENCE_AREA_NOT_RECTANGULAR')return 'shapeError';
 if(code==='REFERENCE_UNSTABLE'||code==='REFERENCE_UNCLEAR')return 'unstableError';
 if(code==='REFERENCE_POINTS_REQUIRED'||code==='REFERENCE_POINT_ORDER')return 'pointsError';
 return 'photoError';
}
async function photoData(file){
 if(!file?.type.startsWith('image/')||file.size>20*1024*1024)throw Error('INVALID_IMAGE');
 const src=URL.createObjectURL(file);
 try{return await new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>{if(Math.min(img.naturalWidth,img.naturalHeight)<160)return reject(Error('INVALID_IMAGE'));const ratio=Math.min(1,2400/Math.max(img.naturalWidth,img.naturalHeight)),canvas=document.createElement('canvas');canvas.width=Math.round(img.naturalWidth*ratio);canvas.height=Math.round(img.naturalHeight*ratio);const ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(img,0,0,canvas.width,canvas.height);resolve(canvas.toDataURL('image/jpeg',.94));};img.onerror=reject;img.src=src;});}finally{URL.revokeObjectURL(src);}
}
export function createRoomMeasure({context,language,api,showSheet,escape:esc,safe,onUse}){
 let epoch=0;
 return async function openMeasurement(){
  const token=++epoch,c=context();if(!c.job||c.job.demo)return;
  const t=k=>measurementText(language(),k),url='/api/jobs/'+c.job.id+'/measure';
  let phase='reference',active=0,reference=[],points=[],imageId='original',imageURL=c.job.original,result=null,revision=0,busy=false,zoom=1;
  showSheet(`<div class="sheet-body room-measure-form" data-no-i18n><h2>${esc(t('title'))}</h2><p>${esc(t('intro'))}</p><div class="reference-photo-tools"><label class="reference-photo-upload">${esc(t('photo'))}<input type="file" accept="image/*" data-photo hidden></label><button type="button" data-original>${esc(t('original'))}</button></div><div class="reference-steps"><button type="button" data-phase="reference" aria-pressed="true">1 · ${esc(t('reference'))}</button><button type="button" data-phase="area" aria-pressed="false">2 · ${esc(t('areaStep'))}</button></div><p class="reference-guide"></p><div class="reference-viewport"><div class="measure-photo reference-photo"><img src="${esc(safe(imageURL))}" alt="${esc(t('title'))}" draggable="false"><svg viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-hidden="true"></svg></div></div><div class="measure-tools"><div class="measure-point-buttons" role="group">${[1,2,3,4].map((n,i)=>`<button type="button" data-point="${i}" aria-pressed="${i===0}">${n}</button>`).join('')}</div><div class="reference-zoom"><button type="button" data-zoom="out" aria-label="Zoom out">−</button><button type="button" data-zoom="in" aria-label="Zoom in">+</button></div></div><button class="reference-reset" type="button" data-reset>${esc(t('reset'))}</button><div class="reference-size"><label>${esc(t('reference'))}<select data-preset><option value="a4">A4 · 21 × 29.7 cm</option><option value="custom">${esc(t('custom'))}</option></select></label><div class="furnish-measurements"><label>${esc(t('width'))} (m)<input name="reference_width" type="number" min="0.05" max="15" step="0.001" inputmode="decimal" value="0.21"></label><label>${esc(t('length'))} (m)<input name="reference_length" type="number" min="0.05" max="15" step="0.001" inputmode="decimal" value="0.297"></label></div></div><p class="measure-status" role="status" aria-live="polite"></p><button type="button" class="primary wide" data-calculate disabled>${esc(t('next'))}</button><div class="measure-result" hidden></div><p class="furnish-note">${esc(t('note'))}</p></div>`,'measurement');
  const root=document.querySelector('.room-measure-form'),photo=root.querySelector('.measure-photo'),img=photo.querySelector('img'),svg=photo.querySelector('svg'),status=root.querySelector('.measure-status'),calc=root.querySelector('[data-calculate]'),output=root.querySelector('.measure-result'),width=root.querySelector('[name="reference_width"]'),length=root.querySelector('[name="reference_length"]'),preset=root.querySelector('[data-preset]');
  const alive=()=>token===epoch&&root.isConnected&&context().job?.id===c.job.id;
  const selected=()=>phase==='reference'?reference:points;
  const number=v=>Number(String(v).replace(/[٠-٩]/g,x=>x.charCodeAt(0)-1632).replace(/[٫,]/g,'.'));
  function message(value,isError=false){status.textContent=value;status.classList.toggle('measure-error',isError);status.setAttribute('role',isError?'alert':'status');}
  function draw(p,selected,color){return `${p.length>1?`<${p.length===4?'polygon':'polyline'} points="${p.map(v=>v.map(n=>n*1000).join(',')).join(' ')}" style="stroke:${color};fill:none;stroke-width:${selected?5:3};${selected?'':'stroke-dasharray:10 8'}"/>`:''}${selected?p.map((v,i)=>`<circle cx="${v[0]*1000}" cy="${v[1]*1000}" r="18"/><text x="${v[0]*1000}" y="${v[1]*1000}" text-anchor="middle" dominant-baseline="central">${i+1}</text>`).join(''):''}`;}
  function refresh(){
   svg.innerHTML=draw(reference,phase==='reference','#e2b981')+draw(points,phase==='area','#ffffff');
   root.querySelectorAll('[data-point]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.point)===active)));
   root.querySelectorAll('[data-phase]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.phase===phase)));
   root.querySelector('.reference-size').hidden=phase!=='reference';
   root.querySelector('.reference-guide').textContent=t(phase==='reference'?'referenceGuide':'areaGuide');
   const valid=[number(width.value),number(length.value)].every(n=>Number.isFinite(n)&&n>=.05&&n<=15);
   calc.disabled=busy||reference.length!==4||!valid||(phase==='area'&&points.length!==4);
   calc.textContent=t(busy?'calculating':phase==='reference'?'next':'calculate');
   root.querySelector('[data-phase="area"]').disabled=reference.length!==4||!valid||busy;
   root.querySelectorAll('[data-photo],[data-original],[data-preset]').forEach(b=>b.disabled=busy);
  }
  function changed(){revision++;result=null;output.hidden=true;message('');refresh();}
  function setPhase(value){phase=value;active=Math.min(selected().length,3);refresh();}
  photo.addEventListener('click',e=>{if(e.button!==0||busy)return;const r=photo.getBoundingClientRect(),p=[Math.min(1,Math.max(0,(e.clientX-r.left)/r.width)),Math.min(1,Math.max(0,(e.clientY-r.top)/r.height))],list=selected();list[Math.min(active,list.length)]=p;active=Math.min(list.length,3);changed();});
  root.querySelectorAll('[data-point]').forEach(b=>b.addEventListener('click',()=>{active=Number(b.dataset.point);refresh();}));
  root.querySelectorAll('[data-phase]').forEach(b=>b.addEventListener('click',()=>{if(!b.disabled&&!busy)setPhase(b.dataset.phase);}));
  root.querySelector('[data-reset]').addEventListener('click',()=>{if(busy)return;if(phase==='reference')reference=[];else points=[];active=0;changed();});
  root.querySelectorAll('[data-zoom]').forEach(b=>b.addEventListener('click',()=>{zoom=Math.max(1,Math.min(4,zoom+(b.dataset.zoom==='in'?1:-1)));photo.style.width=zoom*100+'%';}));
  preset.addEventListener('change',()=>{if(preset.value==='a4'){width.value='.21';length.value='.297';}changed();});
  for(const input of [width,length])input.addEventListener('input',()=>{preset.value='custom';changed();});
  function changeImage(value){imageId=value.image_id||'original';imageURL=value.image||c.job.original;img.src=safe(imageURL);reference=[];points=[];active=0;phase='reference';zoom=1;photo.style.width='100%';changed();}
  root.querySelector('[data-original]').addEventListener('click',()=>changeImage({image:c.job.original,image_id:'original'}));
  root.querySelector('[data-photo]').addEventListener('change',async e=>{
   const file=e.target.files?.[0];if(!file||busy)return;busy=true;refresh();message(t('calculating'));const start=revision;
   try{const image=await photoData(file);if(!alive())return;const value=await api(url,{method:'POST',body:JSON.stringify({action:'photo',image})});if(alive()&&revision===start)changeImage(value);}catch{if(alive())message(t('photoError'),true);}finally{busy=false;if(alive())refresh();}
  });
  calc.addEventListener('click',async()=>{
   if(calc.disabled)return;if(phase==='reference'){setPhase('area');return;}
   const start=revision;busy=true;refresh();message(t('calculating'));
   try{const value=await api(url,{method:'POST',body:JSON.stringify({action:'reference',image_id:imageId,reference_points:reference,reference_width:number(width.value),reference_length:number(length.value),points})});if(!alive()||start!==revision)return;
    result=value.result;message('');const canUse=result.width>=150&&result.length>=150&&result.width<=1500&&result.length<=1500;
    output.innerHTML=`<div class="measure-result-dimensions" dir="ltr">≈ ${result.width/100} × ${result.length/100} m</div><div class="furnish-area"><span>${esc(t('area'))}</span><strong dir="ltr">≈ ${result.area_m2} m²</strong></div>${result.quality==='rough'?`<p class="furnish-note">${esc(t('rough'))}</p>`:''}${canUse?`<button type="button" class="primary wide" data-use>${esc(t('use'))}</button>`:''}`;output.hidden=false;output.scrollIntoView?.({block:'nearest',behavior:'smooth'});
    output.querySelector('[data-use]')?.addEventListener('click',()=>{if(result)onUse({...result,measurement_id:value.id});});
   }catch(e){if(alive()&&revision===start)message(t(referenceErrorKey(e.code)),true);}finally{busy=false;if(alive())refresh();}
  });
  refresh();const initialRevision=revision;
  try{const state=await api(url);if(!alive()||revision!==initialRevision)return;if(state.method==='reference_scale'){
   changeImage(state);if(state.result?.reference){reference=state.result.reference.points.map(p=>[...p]);points=state.result.points.map(p=>[...p]);width.value=state.result.reference.width_m;length.value=state.result.reference.length_m;preset.value='custom';phase='area';active=3;refresh();}
  }}catch{/* The original photo can still be calibrated when there is no saved measurement. */}
 };
}
