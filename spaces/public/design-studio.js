import {studioCopy} from './design-studio-copy.js?v=20261016-credit1';
// Show real results immediately. Pending concepts never masquerade as previews.
import {sceneText} from './space-scene-copy.js?v=20261017-scene4';
export function designPresentation(job,{escape:esc,icon,translate,language='en',order=[],reconnecting=false,slow=false,messages={}}){
 const t=source=>studioCopy[language]?.[source]||translate(source),copy=key=>sceneText(language,key);
 const designs=job.designs||[],ready=designs.filter(d=>d.image).length;
 const pending=designs.filter(d=>!d.image&&d.status!=='error').length;
 const failed=designs.map((d,i)=>({d,i})).filter(({d})=>!d.image&&d.status==='error');
 const status=reconnecting?t('Reconnecting… Your designs are safe.'):pending?copy('working'):ready?t('Choose a design to explore.'):t('We couldn’t create this design. Please try again.');
 const activity='<span class="scene-breath" aria-hidden="true"><i></i><i></i><i></i></span>';
 const stage=!pending?'':ready?`<div class="scene-progress" role="status">${activity}<span>${ready} / ${designs.length}</span></div>`:
 `<div class="scene-wait" data-ui-key="waiting:${job.id}"><div class="scene-media"><img src="${esc(job.original)}" alt="${esc(t('Your original room'))}" draggable="false"></div><div class="scene-shade"></div><div class="scene-bottom scene-wait-copy">${activity}<p>${esc(status)}</p>${slow&&!reconnecting?`<small>${esc(t('Still creating. No need to start again.'))}</small>`:''}</div></div>`;
 const indexes=[...new Set([...order,...designs.map((_,i)=>i)])].filter(i=>designs[i]?.image);
 const cards=indexes.map(i=>{const d=designs[i];return `<article data-ui-key="${job.id}:${i}" class="design-card scene-result" data-design-index="${i}"><button class="design-image scene-media" data-action="choose" data-index="${i}" aria-label="${esc(copy('choose'))}"><img src="${esc(d.image)}" alt="${esc(t(d.title))}" decoding="async" draggable="false"></button><div class="scene-shade"></div><div class="design-card-body scene-bottom"><h2>${esc(t(d.title))}</h2><button class="scene-primary" data-action="choose" data-index="${i}">${esc(copy('choose'))}${icon('forward',true)}</button></div></article>`;}).join('')+failed.map(({d,i})=>`<article data-ui-key="${job.id}:${i}" class="design-card scene-result scene-failed" data-design-index="${i}"><div class="scene-media"><img src="${esc(job.original)}" alt=""></div><div class="scene-shade"></div><div class="scene-bottom"><p role="status">${esc(t(messages[d.error]||'We couldn’t create this design. Please try again.'))}</p><button class="scene-primary" data-action="retry" data-index="${i}">${esc(t('Try again · 1 credit'))}</button></div></article>`).join('');
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
