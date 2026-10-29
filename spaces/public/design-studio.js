import {studioCopy} from './design-studio-copy.js?v=20261025-wait1';
// Show real results immediately. Pending concepts never masquerade as previews.
import {sceneText} from './space-scene-copy.js?v=20261019-studio1';
export function designPresentation(job,{escape:esc,icon,translate,language='en',order=[],styleIndex=0,reconnecting=false,slow=false,messages={}}){
 const t=source=>studioCopy[language]?.[source]||translate(source),copy=key=>sceneText(language,key);
 const designs=job.designs||[],ready=designs.filter(d=>d.image).length;
 const pending=designs.filter(d=>!d.image&&d.status!=='error').length;
 const failed=designs.map((d,i)=>({d,i})).filter(({d})=>!d.image&&d.status==='error');
 const unfinished=designs.filter(d=>!d.image&&d.status!=='error');
 const phase=unfinished.some(d=>d.generation_phase==='checking')?2:unfinished.length&&unfinished.every(d=>d.generation_phase==='understanding')?0:1;
 const steps=[t('Understanding your room…'),copy('working'),t('Reviewing the details…')];
 const status=reconnecting?t('Reconnecting… Your designs are safe.'):pending?steps[phase]:ready?t('Choose a design to explore.'):t('We couldn’t create this design. Please try again.');
 const activity='<span class="studio-spinner" aria-hidden="true"></span>';
 const inspiration=[['#d9d3c3','#acae9a','#657561','Soft tones. Clean lines. Room to breathe.'],['#d3b28c','#98734e','#655847','Earthy colours. Natural textures. A warmer feel.'],['#ded3c2','#9a8877','#51483f','Rich textures. Quiet contrast. Refined details.']][styleIndex%3]||[];
 const drawing='<div class="studio-drawing" aria-hidden="true"><svg viewBox="0 0 80 80" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path class="studio-room-line" pathLength="100" d="M10 63V21l30-12 30 12v42L40 75 10 63M40 9v37M10 63l30-17 30 17"/><path d="M23 46V33l19-7 15 6v15M23 40l16-6 18 6M23 46l16 7 18-6M39 34v19M23 46v5M57 47v5M39 53v5"/></svg></div>';
 const progress=steps.map((label,i)=>`<li class="${!reconnecting&&i<phase?'is-complete':''}"${!reconnecting&&i===phase?' aria-current="step"':''}><span class="studio-step-number" aria-hidden="true">${!reconnecting&&i<phase?icon('check',true):i+1}</span><span>${esc(label)}</span></li>`).join('');
 const stage=!pending?'':ready?`<div class="scene-progress" role="status">${activity}<span>${ready} / ${designs.length}</span></div>`:
 `<div class="scene-wait${reconnecting?' is-reconnecting':''}" data-ui-key="waiting:${job.id}" data-no-i18n><div class="scene-media"><img src="${esc(job.original)}" alt="${esc(t('Your original room'))}" draggable="false"></div><div class="scene-bottom scene-wait-copy"><div class="studio-wait-heading">${drawing}<div><h2>${esc(status)}</h2><p>${esc(t('Your designs appear here as they’re ready.'))}</p></div></div><ol class="studio-steps">${progress}</ol><div class="studio-inspiration"><div class="studio-palette" aria-hidden="true">${inspiration.slice(0,3).map(color=>`<i style="background:${color}"></i>`).join('')}</div><div><span>${esc(t('Explore the styles'))}</span><p>${esc(t(inspiration[3]))}</p></div></div><small class="studio-delay">${slow&&!reconnecting?esc(t('Still creating. No need to start again.')):''}</small></div></div>`;
 const indexes=[...new Set([...order,...designs.map((_,i)=>i)])].filter(i=>designs[i]?.image);
 const cards=indexes.map(i=>{const d=designs[i];return `<article data-ui-key="${job.id}:${i}" class="design-card scene-result" data-design-index="${i}"><button class="design-image scene-media" data-action="choose" data-index="${i}" aria-label="${esc(copy('choose')+' — '+t(d.title))}"><img src="${esc(d.image)}" alt="${esc(t(d.title))}" decoding="async" draggable="false"></button></article>`;}).join('')+failed.map(({d,i})=>`<article data-ui-key="${job.id}:${i}" class="design-card scene-result scene-failed" data-design-index="${i}"><div class="scene-media"><img src="${esc(job.original)}" alt=""></div><div class="scene-shade"></div><div class="scene-bottom"><p role="status">${esc(t(messages[d.error]||'We couldn’t create this design. Please try again.'))}</p><button class="scene-primary" data-action="retry" data-index="${i}">${esc(t('Try again · 1 credit'))}</button></div></article>`).join('');
 const navigation=[...indexes,...failed.map(({i})=>i)].map(i=>`<button data-ui-key="design-nav:${i}" data-action="design-slide" data-index="${i}" aria-label="${esc(t(designs[i].title))}" aria-current="false">${i+1}</button>`).join('');
 return {stage,cards,navigation,status,pending,ready};
}

// A tour of style inspiration, independent of generation progress. Polls never
// reset a user's selection; hiding the view or receiving a result stops the tour.
export function createStyleTour({onChange,schedule=setTimeout,cancel=clearTimeout}){
 let jobId='',indexes=[],selected=0,paused=false,reduced=false,active=false,timer=null;
 function stop(){if(timer!==null)cancel(timer);timer=null;}
 function start(){if(timer!==null||!active||paused||reduced||indexes.length<2)return;
  timer=schedule(()=>{timer=null;if(!active||paused||reduced)return;
   selected=indexes[(indexes.indexOf(selected)+1)%indexes.length];onChange();start();
  },6500);
 }
 return {
  sync(next){
   if(jobId!==next.jobId){stop();jobId=next.jobId;selected=next.indexes[0]??0;paused=false;}
   indexes=next.indexes;active=next.active;reduced=next.reduced;
   if(!indexes.includes(selected))selected=indexes[0]??0;
   if(!active||reduced||paused)stop();else start();
   return {styleIndex:selected,paused};
  },
  choose(index){if(!indexes.includes(index))return;selected=index;paused=true;stop();onChange();},
  toggle(){paused=!paused;if(paused)stop();else start();onChange();},
  pause(){if(paused)return;paused=true;stop();onChange();},
  stop(){active=false;stop();}
 };
}
