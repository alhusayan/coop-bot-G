import {studioCopy} from './design-studio-copy.js?v=20261015-studio2';
// Show real results immediately. Pending concepts never masquerade as previews.
export function designPresentation(job,{escape:esc,icon,translate,language='en',order=[],reconnecting=false,slow=false,messages={},styleIndex=0,paused=false,reduced=false}){
 const t=source=>studioCopy[language]?.[source]||translate(source);
 const designs=job.designs||[],ready=designs.filter(d=>d.image).length;
 const pending=designs.map((d,i)=>({d,i})).filter(({d})=>!d.image&&d.status!=='error');
 const failed=designs.map((d,i)=>({d,i})).filter(({d})=>!d.image&&d.status==='error');
 const status=reconnecting?t('Reconnecting… Your designs are safe.'):
  pending.length?(ready?t('{count} of 3 ready. You can start exploring.').replace('{count}',ready):t('Your designs appear here as they’re ready.')):
  ready===3?t('Choose a design to explore.'):ready?t('Choose a design, or retry the others.'):t('We couldn’t create this design. Please try again.');
 const bars='<span class="studio-activity" aria-hidden="true"><i></i><i></i><i></i></span>';
 const palettes=d=>(d.palette||[]).filter(c=>/^#[\da-f]{6}$/i.test(c)).slice(0,3).map(c=>`<i style="--swatch:${c}"></i>`).join('');
 const rows=pending.map(({d,i})=>`<div class="studio-concept" data-ui-key="concept:${i}"><span class="studio-number" aria-hidden="true">0${i+1}</span><span class="studio-concept-name">${esc(t(d.title))}</span><span class="studio-palette" aria-hidden="true">${palettes(d)}</span></div>`).join('');
 const note=reconnecting?t('Reconnecting… Your designs are safe.'):slow?t('Still creating. No need to start again.'):t('Explore each design as soon as it’s ready.');
 const current=pending.find(({i})=>i===styleIndex)||pending[0];
 const descriptions=['Soft tones. Clean lines. Room to breathe.','Earthy colours. Natural textures. A warmer feel.','Rich textures. Quiet contrast. Refined details.'];
 const mood=current?`<div class="studio-mood-head"><span>${esc(t('Explore the styles'))}</span>${reduced?'':`<button class="studio-play" data-action="studio-play" aria-label="${esc(t(paused?'Play slideshow':'Pause slideshow'))}" title="${esc(t(paused?'Play slideshow':'Pause slideshow'))}"><svg viewBox="0 0 24 24" aria-hidden="true">${paused?'<path d="m9 5 11 7-11 7Z"/>':'<path d="M8 5v14M16 5v14"/>'}</svg></button>`}</div><div class="studio-style-tabs" role="group" aria-label="${esc(t('Explore the styles'))}">${pending.map(({d,i})=>`<button data-ui-key="style-tab:${i}" data-action="studio-style" data-index="${i}" aria-pressed="${i===current.i}" aria-label="${esc(t(d.title))}"><span>0${i+1}</span><span class="studio-palette" aria-hidden="true">${palettes(d)}</span></button>`).join('')}</div><div class="studio-mood" data-ui-key="mood:${current.i}"><div class="studio-materials" aria-hidden="true">${palettes(current.d)}</div><h3>${esc(t(current.d.title))}</h3><p>${esc(t(descriptions[current.i]||descriptions[0]))}</p></div>`:'';
 const stage=!pending.length?'':ready?`<aside class="studio-pending" data-ui-key="pending:${job.id}"><div class="studio-pending-title">${bars}<span>${esc(t('Creating your design'))}</span></div><div class="studio-concepts">${rows}</div></aside>`:
  `<div class="studio-workspace${paused?' is-paused':''}${reconnecting?' is-reconnecting':''}" data-ui-key="studio:${job.id}"><div class="studio-photo-wrap"><div class="studio-paper paper-back" aria-hidden="true"></div><div class="studio-paper paper-middle" aria-hidden="true"></div><figure class="studio-photo"><img src="${esc(job.original)}" alt="${esc(t('Your original room'))}"><figcaption>${esc(t('Your photo'))}</figcaption><span class="studio-frame" aria-hidden="true"></span></figure></div><div class="studio-copy"><div class="studio-heading">${bars}<h2>${esc(t('Creating three possibilities…'))}</h2></div>${mood}<p class="studio-note">${esc(note)}</p></div></div>`;
 const indexes=[...new Set([...order,...designs.map((_,i)=>i)])].filter(i=>designs[i]?.image);
 const cards=indexes.map(i=>{const d=designs[i];return `<article data-ui-key="${job.id}:${i}" class="design-card is-ready" data-design-index="${i}"><button class="design-image" data-action="preview" data-index="${i}" aria-label="${esc(t('Enlarge design'))}"><img src="${esc(d.image)}" alt="${esc(t(d.title))}" decoding="async"></button><div class="design-card-body"><h3>${esc(t(d.title))}</h3><button class="secondary wide" data-action="choose" data-index="${i}">${esc(t('Explore this design'))} ${icon('forward',true)}</button></div></article>`;}).join('')+failed.map(({d,i})=>`<article data-ui-key="${job.id}:${i}" class="design-card design-failed"><div class="design-card-body"><h3>${esc(t(d.title))}</h3><p class="error-copy">${esc(t(messages[d.error]||'We couldn’t create this design. Please try again.'))}</p><button class="secondary wide" data-action="retry" data-index="${i}">${esc(t('Try again · 1 credit'))}</button></div></article>`).join('');
 const navigation=indexes.map(i=>`<button data-ui-key="design-nav:${i}" data-action="design-slide" data-index="${i}" aria-label="${esc(t(designs[i].title))}" aria-current="false">0${i+1}</button>`).join('');
 return {stage,cards,navigation,status,pending:pending.length,ready};
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
