/* FINDZIA_GUIDE_RELEASE=156.7.48 */
/* Shared modal ownership keeps the page fixed on touch browsers as well. */
window.FindziaModalScroll=window.FindziaModalScroll||(()=>{
 const owners=new Set();let saved=null;
 const keys=['position','top','left','right','width','overflow','paddingRight'];
 return {lock(owner){if(owners.has(owner))return;owners.add(owner);if(saved)return;
  const body=document.body,html=document.documentElement,x=window.scrollX||0,y=window.scrollY||0;
  saved={x,y,body:Object.fromEntries(keys.map(k=>[k,body.style[k]])),overflow:html.style.overflow,overscroll:html.style.overscrollBehavior,behavior:html.style.scrollBehavior};
  const gap=Math.max(0,(window.innerWidth||html.clientWidth)-html.clientWidth);
  if(gap)body.style.paddingRight=((parseFloat(window.getComputedStyle(body).paddingRight)||0)+gap)+'px';
  Object.assign(body.style,{position:'fixed',top:-y+'px',left:-x+'px',right:'0',width:'100%',overflow:'hidden'});
  html.style.overflow='hidden';html.style.overscrollBehavior='none';
 },resetPosition(){if(saved){saved.x=0;saved.y=0;document.body.style.top='0px';document.body.style.left='0px';}
 },unlock(owner){if(!owners.delete(owner)||owners.size||!saved)return;const state=saved;saved=null;
  Object.assign(document.body.style,state.body);const html=document.documentElement;
  html.style.overflow=state.overflow;html.style.overscrollBehavior=state.overscroll;html.style.scrollBehavior='auto';
  window.scrollTo(state.x,state.y);html.style.scrollBehavior=state.behavior;
 }};
})();
/* Findzia 156.7.24 — step-by-step assistant. No filter panel or filter requests. */
(()=>{'use strict';
const COPY={en:{title:'AI Shopping Assistant',overall:'Best Overall',quality:'Best Quality',budget:'Budget',discovery:'AI Pick',guided:'Help me choose',alternatives:'Find alternatives',start:'What matters to you?',close:'Close',back:'Back',loading:'Loading…',search:'Search',retry:'Try again',credit:'Each search uses 1 credit.',edit:'Refine your search',placeholder:'Add your preferences',unavailable:'Add what matters to you and search again.',fresh:'Choose a suggestion to start a new search.',same:'Search for this product',research:'Finding reviewed models…',reviews:'Sources',basis:'Selected from independent reviews',nomodes:'No reviewed picks for this search yet.',value:'Best Value',limitation:'Consider',searchmodel:'Find this model'},ar:{title:'مساعد التسوّق الذكي',overall:'الأفضل إجمالًا',quality:'أفضل جودة',budget:'اقتصادي',discovery:'ترشيح ذكي',guided:'ساعدني أختار',alternatives:'ابحث عن بدائل',start:'شنو الأهم لك؟',close:'إغلاق',back:'رجوع',loading:'جاري التحميل…',search:'ابحث',retry:'حاول مجددًا',credit:'كل بحث يستخدم رصيدًا واحدًا.',edit:'خصّص بحثك',placeholder:'أضف تفضيلاتك',unavailable:'أضف ما يهمك وابحث مجددًا.',fresh:'اختر اقتراحًا لبدء بحث جديد.',same:'ابحث عن هذا المنتج',research:'نبحث عن موديلات موصى بها…',reviews:'المصادر',basis:'اختيارات مبنية على مراجعات مستقلة',nomodes:'لا تتوفر ترشيحات موثوقة لهذا البحث حاليًا.',value:'أفضل قيمة',limitation:'خذ بعين الاعتبار',searchmodel:'ابحث عن هذا الموديل'}};
Object.assign(COPY.en,{sub:'A little guidance. A better choice.',needs:'Your use, budget, or what matters…',send:'Continue',answers:'Your answers',editanswers:'Change my answers',proposed:'Proposed search',applyneeds:'Search with these choices',tip:'One useful check',prefs:'Your shopping preferences',remember:'Remember my preferences on this device',privacy:'Save your searches and answers here only if you choose. Relevant preferences can help future guidance. You can edit or erase them.',none:'Nothing saved yet.',remove:'Remove',save:'Save',clear:'Erase saved preferences',previous:'Previous search',preference:'Your preference',guideloading:'Understanding your needs…',freeanswer:'Or tell me in your own words'});
Object.assign(COPY.ar,{sub:'نفهم احتياجك، ونوضح لك الخيارات.',needs:'استخدامك، ميزانيتك، أو الشي الأهم لك…',send:'متابعة',answers:'إجاباتك',editanswers:'غيّر إجاباتي',proposed:'البحث المقترح',applyneeds:'ابحث بهذه الاختيارات',tip:'شي يستحق التأكد',prefs:'تفضيلاتك في التسوق',remember:'احفظ تفضيلاتي على هذا الجهاز',privacy:'نحفظ بحثك وإجاباتك هنا باختيارك فقط. نستفيد من التفضيلات المرتبطة في المساعدة القادمة، وتقدر تعدّلها أو تمسحها.',none:'ما فيه تفضيلات محفوظة بعد.',remove:'حذف',save:'حفظ',clear:'امسح التفضيلات المحفوظة',previous:'بحث سابق',preference:'تفضيلك',guideloading:'نفهم احتياجك…',freeanswer:'أو اكتب اللي تبيه بطريقتك'});
Object.assign(COPY.en,{step:'Step',optional:'Answer what matters, or search now.',explore:'Explore recommendations',photoquery:'Photo + search details',photoplaceholder:'Add a colour, size, material, or other detail',photosearch:'Search with this photo',change:'Change answer',ready:'Your search is ready. Add more details if you want.'});
Object.assign(COPY.ar,{step:'الخطوة',optional:'جاوب على اللي يهمك، أو ابحث الحين.',explore:'استكشف الترشيحات',photoquery:'الصورة + تفاصيل البحث',photoplaceholder:'أضف اللون أو المقاس أو الخامة أو أي تفصيل',photosearch:'ابحث بهالصورة',change:'تعديل الإجابة',ready:'بحثك جاهز. تقدر تضيف تفاصيل أكثر إذا تبي.'});
Object.assign(COPY.en,{applyneeds:'Search now',shortcredit:'1 credit',proposed:'Your search',photoquery:'Photo details',photoplaceholder:'Add a detail',freeanswer:'Write my own answer',ready:'Ready to search',moreoptions:'More options',needs:'What matters to you?',guideloading:'Choosing the next question…'});
Object.assign(COPY.ar,{applyneeds:'ابحث الآن',shortcredit:'رصيد واحد',proposed:'بحثك',photoquery:'تفاصيل الصورة',photoplaceholder:'أضف تفصيلًا',freeanswer:'أكتب إجابتي',ready:'جاهز للبحث',moreoptions:'خيارات إضافية',needs:'شنو يهمك؟',guideloading:'نجهّز السؤال التالي…'});
Object.assign(COPY.en,{removephoto:'Remove photo',adddetails:'Add details to this photo',referencephoto:'Search photo'});
Object.assign(COPY.ar,{removephoto:'إزالة الصورة',adddetails:'أضف تفاصيل للصورة',referencephoto:'صورة البحث'});
const MAX_QUESTIONS=4;
const usedLabels={en:'AI has already been applied to this search',ar:'تم استخدام AI لهذا البحث',fr:'L’IA a déjà été appliquée à cette recherche',de:'KI wurde bereits für diese Suche verwendet',es:'La IA ya se ha aplicado a esta búsqueda',it:'L’IA è già stata applicata a questa ricerca',pt:'A IA já foi aplicada a esta pesquisa',tr:'Yapay zekâ bu aramada zaten kullanıldı',ru:'ИИ уже применён к этому поиску',zh:'此搜索已使用 AI',ja:'この検索にはすでに AI が適用されています',ko:'이 검색에는 이미 AI가 적용되었습니다',hi:'इस खोज में AI का उपयोग हो चुका है',ur:'اس تلاش میں AI پہلے ہی استعمال ہو چکا ہے',id:'AI sudah digunakan untuk pencarian ini',ms:'AI sudah digunakan untuk carian ini'};
const PREF_KEY='findzia-shopping-preferences-v1';
const privateSearch=/panadol|paracetamol|medicin|medicat|pain\s*relief|pregnan|diabet|antidepress|sexual|religio|politic|دواء|ادويه|أدوية|بنادول|بانادول|علاج|مسكن|حمل|جنس|سكري|اكتئاب|دين\b|سياس/i;
function clean(s,n=200){return String(s||'').replace(/\s+/g,' ').trim().slice(0,n);}
function loadProfile(){try{const p=JSON.parse(localStorage.getItem(PREF_KEY)||'null');if(p?.version===1)return{version:1,enabled:p.enabled===true,entries:(Array.isArray(p.entries)?p.entries:[]).filter(e=>e&&typeof e.query==='string'&&typeof e.preference==='string'&&e.at>Date.now()-90*864e5&&!privateSearch.test(e.query+' '+e.preference)).slice(-20).map(e=>({query:clean(e.query,180),preference:clean(e.preference,180),at:e.at}))};}catch(_){}return{version:1,enabled:false,entries:[]};}
function persist(profile){try{localStorage.setItem(PREF_KEY,JSON.stringify(profile));}catch(_){}}
const paths={overall:'M12 3 3 8l9 5 9-5-9-5ZM3 12l9 5 9-5M3 16l9 5 9-5',quality:'m12 3 2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1L3.2 9.4l6.1-.9L12 3Z',budget:'M20 12 12 20l-9-9V3h8l9 9ZM7 7h.01',discovery:'m12 3 2.2 6.8L21 12l-6.8 2.2L12 21l-2.2-6.8L3 12l6.8-2.2L12 3Z',guided:'M4 4h16v13H9l-5 4V4ZM8 9h8M8 13h5',arrow:'M5 12h14m-5-5 5 5-5 5'};
function node(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
function button(text,cls,fn){const b=node('button',cls,text);b.type='button';b.addEventListener('click',fn);return b;}
function icon(kind){const s=document.createElementNS('http://www.w3.org/2000/svg','svg');s.setAttribute('viewBox','0 0 24 24');s.setAttribute('fill','none');s.setAttribute('stroke','currentColor');s.setAttribute('stroke-width','1.6');s.setAttribute('stroke-linecap','round');s.setAttribute('stroke-linejoin','round');s.setAttribute('aria-hidden','true');s.innerHTML='<path d="'+(paths[kind]||paths.discovery)+'"/>';return s;}
function mount(root){
 if(root.dataset.guideMounted||!root.fzRefineBridge)return;
 const bridge=root.fzRefineBridge,top=root.querySelector('[data-assistant-tools]');if(!top)return;
 root.dataset.guideMounted='156.7.48';const t=k=>window.FindziaI18n?.t(COPY.en[k]||k,COPY.ar[k],root)||COPY[root.dataset.lang==='ar'?'ar':'en'][k]||k;
 let origin=null,photoAttached=false,mode='guided',answers=[],turns=[],frames=[],draft='',draftVersion=0,data=null,overview=null,busy=false,controller=null,serial=0,disposed=false,returnFocus=null,profile=loadProfile();
 const trigger=button('','fz-guide-open',open);trigger.dataset.guideOpen='';trigger.setAttribute('aria-haspopup','dialog');trigger.append(icon('discovery'));top.append(trigger);
 const dialog=node('dialog','fz-guide');dialog.id=root.id+'-guide';dialog.setAttribute('aria-modal','true');dialog.setAttribute('aria-labelledby',dialog.id+'-title');trigger.setAttribute('aria-controls',dialog.id);
 const head=node('header','fz-guide-head'),title=node('h2','',t('title'));title.id=dialog.id+'-title';title.tabIndex=-1;
 const close=button('×','fz-guide-close',()=>dialog.close());head.append(title,close);
 const body=node('div','fz-guide-body'),footer=node('footer','fz-guide-footer'),form=node('form','fz-guide-form fz-guide-answer-form'),input=node('textarea','fz-guide-input'),send=node('button','fz-guide-primary');
 input.rows=2;input.maxLength=200;input.dir='auto';input.autocomplete='off';send.type='submit';form.append(input,send);footer.hidden=false;dialog.append(head,body,footer);root.append(dialog);
 // Reuse the decoded thumbnail while questions and answers change.
 const photoChip=node('div','fz-guide-photo-chip'),photoImage=node('img'),removePhoto=button('×','fz-guide-photo-remove',detachPhoto);
 photoChip.dataset.guidePhoto='';photoChip.append(photoImage,removePhoto);
 function hasPhoto(){return origin?.kind==='image'&&photoAttached;}
 function detachPhoto(){
  cancel();photoAttached=false;mode='guided';answers=[];turns=[];frames=[];
  draft=joinQuery(origin.photoDescription||origin.query,draft);draftVersion++;data=null;overview=null;
  discover();body.querySelector('.fz-guide-proposed')?.focus({preventScroll:true});
 }
 form.addEventListener('submit',e=>{e.preventDefault();const answer=clean(input.value);if(!answer||busy)return;input.value='';answerWith(answer);});
 function sameContext(a,b){return a&&b&&['generation',a.kind==='image'?'image_base64':'query','country','lang','kind','extra_specs'].every(k=>(a[k]||'')===(b[k]||''));}
 function remember(answer){if(!profile.enabled||!origin||privateSearch.test(origin.query+' '+answer))return;const query=clean(origin.query,180),preference=clean(answer,180);if(!query||!preference)return;profile.entries=profile.entries.filter(e=>e.query!==query||e.preference!==preference);profile.entries.push({query,preference,at:Date.now()});profile.entries=profile.entries.slice(-20);persist(profile);}
 function joinQuery(base,answer){const a=clean(base,240),b=clean(answer);if(!b)return a;if(a.toLocaleLowerCase().includes(b.toLocaleLowerCase()))return a;if(b.toLocaleLowerCase().includes(a.toLocaleLowerCase()))return b;return [a,b].filter(Boolean).join(' ');}
 function baseDraft(){return hasPhoto()?(origin.photo_edit_draft??origin.user_extra_specs??origin.extra_specs??''):(origin?.query||'');}
 function answerWith(answer){if(busy||!origin||turns.length>=MAX_QUESTIONS)return;answer=clean(answer);if(!answer)return;frames.push({data,draft,answers:[...answers],turns:[...turns]});turns.push({question:data?.question||'',question_key:data?.question_key||'',answer,search_query:draft});answers=turns.map(t=>t.answer);draft=joinQuery(draft,answer);draftVersion++;remember(answer);data=null;discover();}
 function backTo(index){const frame=frames[index];if(!frame)return;cancel();data=frame.data;draft=frame.draft;draftVersion++;answers=[...frame.answers];turns=[...frame.turns];frames=frames.slice(0,index);render();}


 function cancel(){serial++;controller?.abort();controller=null;busy=false;}
 function update(){if(disposed)return;const c=bridge.context();trigger.title=c.ai_used?(usedLabels[root.dataset.lang]||usedLabels.en):t('title');trigger.setAttribute('aria-label',trigger.title);trigger.hidden=!c.query||root.dataset.homeState==='empty';trigger.disabled=c.ai_used===true||(!!c.busy&&!c.can_refine);trigger.dataset.guideUsed=String(c.ai_used===true);trigger.dataset.guideAvailable=String(!trigger.hidden&&!trigger.disabled);
  if(origin&&!sameContext(origin,c)){cancel();origin=null;mode='guided';data=null;overview=null;if(dialog.open)dialog.close();}
 }
 function open(){update();if(trigger.hidden||trigger.disabled)return;const c=bridge.context();if(!sameContext(origin,c)){origin={...c};photoAttached=c.kind==='image';mode='guided';answers=[];turns=[];frames=[];draft=baseDraft();draftVersion++;data=null;overview=null;input.value='';}returnFocus=document.activeElement;dialog.dir=['ar','ur'].includes(root.dataset.lang)?'rtl':'ltr';title.textContent=t('title');close.setAttribute('aria-label',t('close'));dialog.dataset.theme=root.dataset.theme;input.placeholder=t('needs');input.setAttribute('aria-label',t('needs'));send.textContent=t('send');if(!dialog.open)dialog.showModal();window.FindziaModalScroll.lock(dialog);render();title.focus({preventScroll:true});if(!mode&&!overview)loadOverview();else if(mode&&!data)discover();}
 async function request(path,payload,timeout){cancel();const id=++serial,ctl=new AbortController();controller=ctl;busy=true;render();
  // The deadline covers account bootstrap AND response.json(), even if a
  // wrapper/provider ignores AbortSignal. Closing the dialog settles it too.
  let abort;const stopped=new Promise(resolve=>{abort=()=>resolve({ok:false});ctl.signal.addEventListener('abort',abort,{once:true});});
  const timer=setTimeout(()=>ctl.abort(),timeout);
  try{const work=(async()=>{const response=await window.FindziaBillingFetch(root,bridge.api.replace(/\/$/,'')+path,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'omit',signal:ctl.signal,body:JSON.stringify(payload)});const value=await response.json();return response.ok&&value?.ok?value:{ok:false};})();
   const value=await Promise.race([work,stopped]);return id===serial&&!disposed?value:null;
  }catch(_){return id===serial&&!disposed?{ok:false}:null;}
  finally{clearTimeout(timer);ctl.signal.removeEventListener('abort',abort);if(id===serial){busy=false;controller=null;}}
 }
 async function loadOverview(){const result=await request('/api/guide/discover',{query:origin.query,kind:hasPhoto()?'image':'text',extra_specs:hasPhoto()?origin.extra_specs||'':'',country:origin.country,lang:root.dataset.lang,mode:'overview',answers:[]},24500);if(!result)return;overview=result;render();}
 async function choose(value){if(!origin)return;cancel();mode=value;answers=[];turns=[];frames=[];draft=baseDraft();draftVersion++;input.value='';data=null;if(overview?.groups?.[value]?.length){data={ok:true,suggestions:overview.groups[value]};render();return;}await discover();}
 async function discover(){if(!origin||bridge.context().ai_used)return;if(mode==='guided'&&turns.length>=MAX_QUESTIONS){cancel();data={ok:true,status:'ready',question:'',choices:[],search_query:draft};render();return;}const payload={query:origin.query,kind:hasPhoto()?'image':'text',extra_specs:hasPhoto()?origin.extra_specs||'':'',country:origin.country,lang:root.dataset.lang,mode,answers};if(mode==='guided')Object.assign(payload,{guided_version:2,turns,draft_query:draft.length<=240?draft:'',history:profile.enabled?loadProfile().entries:[]});const revision=draftVersion;const result=await request('/api/guide/discover',payload,mode==='guided'?12500:24500);if(!result)return;data=result;if(mode==='guided'&&!hasPhoto()&&revision===draftVersion&&result.search_query)draft=result.search_query;render();}
 function search(query,refinement=false){if(!origin||(!query?.trim()&&!(refinement&&hasPhoto())))return;const c=bridge.context();if(!sameContext(origin,c)||c.ai_used)return;const launch=refinement&&hasPhoto()?bridge.guideSearch:bridge.guideDiscoverSearch||bridge.accountSearch;if(typeof launch!=='function')return;cancel();if(launch(String(query||'').trim(),origin.country)!==false)dialog.close();}
 function status(){const n=node('p','fz-guide-status',t(mode==='guided'?'guideloading':mode?'loading':'research'));n.setAttribute('role','status');n.setAttribute('aria-busy','true');body.append(n);}
 let renderedStep='';
 function render(){
  const active=document.activeElement,editing=active?.matches('.fz-guide-proposed'),freeEditing=active===input;
  const selection=editing?[active.selectionStart,active.selectionEnd]:null;
  const scroll=body.scrollTop,step=mode+':'+turns.length,keepScroll=step===renderedStep;
  const freeOpen=!!body.querySelector('.fz-guide-free-answer[open]');
  renderedStep=step;paint();
  if(freeOpen&&keepScroll){const free=body.querySelector('.fz-guide-free-answer');if(free)free.open=true;}
  if(editing){const next=body.querySelector('.fz-guide-proposed');next?.focus({preventScroll:true});if(next&&selection)next.setSelectionRange(...selection);}
  else if(freeEditing&&keepScroll)input.focus({preventScroll:true});
  body.scrollTop=keepScroll?scroll:0;
 }
 function paint(){footer.hidden=mode!=='guided';send.disabled=busy;body.replaceChildren();body.setAttribute('aria-busy',String(busy));if(!hasPhoto()||mode!=='guided'){const context=node('div','fz-guide-context'),contextText=node('span','',origin?.photoDescription||origin?.query||'');contextText.title=contextText.textContent;context.append(contextText);body.append(context);}
  if(!mode){
   body.append(node('h3','fz-guide-question',t('start')));if(busy)status();else if(!overview?.available_modes?.length)body.append(node('p','fz-guide-note',t('nomodes')));const grid=node('div','fz-guide-mode-grid');for(const key of [...['overall','quality','budget','discovery'].filter(k=>overview?.groups?.[k]?.length),'guided']){const b=button('','fz-guide-mode'+(key==='guided'?' fz-guide-mode-guided':''),()=>choose(key));b.dataset.guideMode=key;b.append(icon(key),node('span','',t(key==='budget'?'value':key)));if(key==='guided'){const arrow=icon('arrow');arrow.classList.add('fz-guide-mode-arrow');b.append(arrow);}grid.append(b);}body.append(grid);return;
  }
  const nav=node('div','fz-guide-navigation');if(mode==='guided'){nav.append(node('span','fz-guide-step',t('step')+' '+Math.min(MAX_QUESTIONS,answers.length+1)+' / '+MAX_QUESTIONS));if(frames.length)nav.append(button(t('back'),'fz-guide-text',()=>backTo(frames.length-1)));}else nav.append(button(t('guided'),'fz-guide-text',()=>choose('guided')));body.append(nav);
  if(mode==='guided'&&!hasPhoto()&&answers.length){const chips=node('div','fz-guide-answers');chips.setAttribute('aria-label',t('answers'));chips.setAttribute('data-no-i18n','');answers.forEach((a,i)=>{const chip=button(a,'fz-guide-answer',()=>backTo(i));chip.title=t('change');chip.setAttribute('aria-label',t('change')+': '+a);chips.append(chip);});body.append(chips);}
  if(mode==='guided'){renderGuided();return;}
  if(busy){status();return;}
  if(answers.length<MAX_QUESTIONS&&data?.question&&data.choices?.length>=2){body.append(node('h3','fz-guide-question',data.question));const options=node('div','fz-guide-options');for(const choice of data.choices.slice(0,4))options.append(button(choice.label,'fz-guide-choice',()=>{if(busy)return;answers.push(choice.answer||choice.label);data=null;discover();}));body.append(options);return;}
  if(data?.suggestions?.length){body.append(node('h3','fz-guide-question',t(mode==='budget'?'value':mode)),node('p','fz-guide-note',data.suggestions.some(s=>s.basis==='review_inference')?t('basis'):t('fresh')));const list=node('div','fz-guide-suggestions');for(const suggestion of data.suggestions.slice(0,3)){
    const card=node('article','fz-guide-suggestion');card.append(node('h3','',suggestion.title));if(suggestion.reason)card.append(node('p','',suggestion.reason));if(suggestion.tradeoff)card.append(node('p','fz-guide-tradeoff',t('limitation')+': '+suggestion.tradeoff));const sources=node('div','fz-guide-sources');for(const source of suggestion.sources||[]){try{const url=new URL(source.url);if(!['https:','http:'].includes(url.protocol)||url.username||url.password)continue;const a=node('a','',url.hostname.replace(/^www\./,''));a.href=url.href;a.target='_blank';a.rel='noopener noreferrer';a.title=source.title||a.textContent;sources.append(a);}catch(_){}}if(sources.children.length){sources.setAttribute('aria-label',t('reviews'));card.append(sources);}const b=button(t(suggestion.basis==='review_inference'?'searchmodel':'search'),'fz-guide-primary',()=>search(suggestion.search_query));b.dataset.suggestionSearch=suggestion.search_query;card.append(b);list.append(card);
   }body.append(list,node('p','fz-guide-note',t('credit')));return;}
  // A provider failure never substitutes or relabels the customer's existing cards.
  body.append(node('p','fz-guide-note',t('unavailable')));const form=node('form','fz-guide-form'),label=node('label','',t('edit')),input=node('input');input.type='text';input.value=origin.query;input.maxLength=240;input.dir='auto';label.append(input);const submit=node('button','fz-guide-primary',t('search'));submit.type='submit';form.append(label,submit);form.addEventListener('submit',e=>{e.preventDefault();search(input.value);});body.append(form,button(t('retry'),'fz-guide-text',discover),node('p','fz-guide-note',t('credit')));
 }
 function renderGuided(){
  if(busy)status();
  else if(answers.length<MAX_QUESTIONS&&data?.question&&data.choices?.length>=2){
   const question=node('h3','fz-guide-question',data.question);question.id=dialog.id+'-question';body.append(question);
   const options=node('div','fz-guide-options');options.setAttribute('role','group');options.setAttribute('aria-labelledby',question.id);
   for(const choice of data.choices.slice(0,4))options.append(button(choice.label,'fz-guide-choice',()=>answerWith(choice.answer||choice.label)));body.append(options);
  }else if(data?.ok===false)body.append(node('p','fz-guide-note',t('unavailable')),button(t('retry'),'fz-guide-text',discover));
  else if(data)body.append(node('h3','fz-guide-question',t('ready')));
  if(turns.length<MAX_QUESTIONS){const more=node('details','fz-guide-free-answer');more.append(node('summary','',t('freeanswer')),form);body.append(more);}
  renderSearchDock();
  const extras=node('details','fz-guide-extras');extras.append(node('summary','',t('moreoptions')));
  const explore=button(t('explore'),'fz-guide-text',()=>{cancel();mode='';render();if(!overview)loadOverview();});extras.append(explore);
  renderPreferences(extras);body.append(extras);
 }
 function renderSearchDock(){
  // The picture and all selected details are one editable photo query.
  // Only the submit action stays in the footer; the composer scrolls normally.
  footer.replaceChildren();const photo=hasPhoto(),box=node('form','fz-guide-search'),label=node('label','',t(photo?'photoquery':'proposed')),query=node('textarea','fz-guide-proposed');
  box.id=dialog.id+'-search';query.id=box.id+'-query';label.htmlFor=query.id;
  query.rows=2;query.maxLength=240;query.value=draft;query.dir='auto';query.setAttribute('aria-label',label.textContent);query.setAttribute('data-no-i18n','');
  box.append(label);
  if(photo){
   const composer=node('div','fz-guide-photo-composer');composer.dataset.guidePhotoComposer='';
   const source=origin.preview_image||(origin.image_base64?.startsWith('data:')?origin.image_base64:'data:'+(origin.mime_type||'image/jpeg')+';base64,'+origin.image_base64);
   if(photoImage.getAttribute('src')!==source)photoImage.src=source;
   photoImage.alt=t('referencephoto');removePhoto.setAttribute('aria-label',t('removephoto'));
   const plus=button('+','fz-guide-photo-plus',()=>{query.focus();query.setSelectionRange(query.value.length,query.value.length);});plus.setAttribute('aria-label',t('adddetails'));
   query.placeholder=t('photoplaceholder');composer.append(photoChip,plus,query);box.append(composer);
  }else box.append(query);
  const apply=node('button','fz-guide-primary');apply.type='submit';apply.dataset.guideRefineSearch='';apply.setAttribute('form',box.id);
  const caption=node('span',''),cost=node('span','fz-guide-cost',t('shortcredit'));apply.append(caption,cost);
  const note=node('p','fz-guide-note');note.setAttribute('role','status');
  function validate(){caption.textContent=t(photo&&!draft.trim()?'photosearch':'applyneeds');const valid=draft.length<=240&&(photo||!!draft.trim());apply.disabled=!valid;note.hidden=draft.length<=240;note.textContent=note.hidden?'':(root.dataset.lang==='ar'?'اختصر جملة البحث إلى 240 حرف.':'Shorten your search to 240 characters.');}
  function fitDetails(){if(!photo)return;query.style.height='72px';query.style.height=Math.min(168,Math.max(72,query.scrollHeight))+'px';}
  query.addEventListener('input',()=>{draft=query.value;draftVersion++;validate();fitDetails();});validate();
  box.append(note);box.addEventListener('submit',e=>{e.preventDefault();if(!apply.disabled)search(query.value,true);});body.append(box);footer.append(apply);
  fitDetails();
 }
 function renderPreferences(parent=body){const details=node('details','fz-guide-preferences');details.append(node('summary','',t('prefs')));const label=node('label','fz-guide-pref-toggle'),check=node('input');check.type='checkbox';check.checked=profile.enabled;check.dataset.guideRemember='';label.append(check,document.createTextNode(t('remember')));details.append(label,node('p','fz-guide-note',t('privacy')));const list=node('div');details.append(list);
  check.addEventListener('change',()=>{profile.enabled=check.checked;persist(profile);if(profile.enabled)answers.forEach(remember);renderList();});
  function renderList(){list.replaceChildren();if(!profile.entries.length)list.append(node('p','fz-guide-note',t('none')));else{profile.entries.slice().reverse().forEach(entry=>{const row=node('div','fz-guide-pref-row'),q=node('input'),a=node('input');q.value=entry.query;a.value=entry.preference;q.maxLength=a.maxLength=180;q.dir=a.dir='auto';q.setAttribute('aria-label',t('previous'));a.setAttribute('aria-label',t('preference'));const actions=node('div','fz-guide-pref-actions');actions.append(button(t('save'),'fz-guide-text',()=>{if(privateSearch.test(q.value+' '+a.value))return;entry.query=clean(q.value,180);entry.preference=clean(a.value,180);entry.at=Date.now();profile.entries=profile.entries.filter(x=>x.query&&x.preference);persist(profile);renderList();}),button(t('remove'),'fz-guide-text',()=>{profile.entries=profile.entries.filter(x=>x!==entry);persist(profile);renderList();}));row.append(q,a,actions);list.append(row);});list.append(button(t('clear'),'fz-guide-text',()=>{profile.entries=[];profile.enabled=false;check.checked=false;persist(profile);renderList();}));}}
  renderList();parent.append(details);
 }
 function storageChanged(event){if(event.key===PREF_KEY){profile=loadProfile();if(dialog.open&&!busy)render();}}
 window.addEventListener('storage',storageChanged);
 dialog.addEventListener('close',()=>{cancel();window.FindziaModalScroll.unlock(dialog);if(returnFocus?.isConnected)returnFocus.focus({preventScroll:true});});
 dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
 const observer=new MutationObserver(update);observer.observe(root,{attributes:true,attributeFilter:['data-lang','data-home-state']});
 const events=['fz:search-state','fz:search-reset'];events.forEach(name=>root.addEventListener(name,update));
 document.addEventListener('shopify:section:unload',function cleanup(e){if(!e.target?.contains(root))return;disposed=true;cancel();window.removeEventListener('storage',storageChanged);window.FindziaModalScroll.unlock(dialog);observer.disconnect();events.forEach(name=>root.removeEventListener(name,update));dialog.remove();trigger.remove();delete root.dataset.guideMounted;document.removeEventListener('shopify:section:unload',cleanup);});update();
}
const style=node('style');style.textContent=`
.fz-guide{--g-bg:#fff;--g-line:#e1e6df;--g-ink:#20312a;--g-muted:#59675e;--g-soft:#f3f5f2;--g-accent:#354e3f;--g-on:#fff;box-sizing:border-box;width:min(560px,calc(100vw - 24px));max-width:none;height:auto;max-height:88vh;max-height:88dvh;margin:auto;padding:0;border:1px solid var(--g-line);border-radius:18px;color:var(--g-ink);background:var(--g-bg);overflow:hidden;overscroll-behavior:contain;touch-action:pan-y;-webkit-overflow-scrolling:touch;font-family:inherit}
.fz-guide[data-theme=dark]{--g-bg:#202622;--g-line:#465348;--g-ink:#f5f6f0;--g-muted:#bcc7bd;--g-soft:#303b32;--g-accent:#dce5d1;--g-on:#202622}.fz-home[id] dialog.fz-guide[open]{display:flex;flex-direction:column;height:auto}.fz-guide::backdrop{background:#15221c70;backdrop-filter:blur(5px)}.fz-guide *{box-sizing:border-box}.fz-guide [hidden]{display:none!important}.fz-guide button,.fz-guide input{font:inherit}.fz-guide button{cursor:pointer}.fz-guide button:focus-visible,.fz-guide input:focus-visible{outline:2px solid var(--g-accent);outline-offset:3px}.fz-home[id] dialog.fz-guide .fz-guide-head h2:focus{outline:none!important;box-shadow:none!important}
.fz-guide-head{position:sticky;top:0;z-index:1;background:var(--g-bg);display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 20px;border-bottom:1px solid var(--g-line);flex:none}.fz-guide-head h2{font-size:19px;line-height:1.4;font-weight:650;margin:0}.fz-guide-close{width:40px;height:40px;border-radius:12px;border:1px solid var(--g-line);background:none;color:inherit;font-size:26px!important;flex:none}.fz-home[id] dialog.fz-guide .fz-guide-body{display:block;height:auto;max-height:none;padding:16px 20px;overflow:auto;overscroll-behavior:contain;min-height:0;flex:1 1 auto}.fz-guide-context{font-size:13px;line-height:1.6;color:var(--g-muted);margin:0 0 16px;overflow-wrap:anywhere}.fz-guide-question{font-size:19px;line-height:1.5;font-weight:600;margin:4px 0 16px}.fz-guide-mode-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.fz-guide-mode{display:flex;align-items:center;gap:12px;min-height:72px;padding:16px 13px;background:var(--g-bg);color:var(--g-ink);border:1px solid var(--g-line);border-radius:12px;text-align:start;font-size:14px!important;font-weight:600!important}.fz-guide-mode:hover,.fz-guide-choice:hover{background:var(--g-soft);border-color:var(--g-accent)}.fz-guide-mode svg{width:22px;height:22px;flex:none;color:var(--g-accent)}.fz-guide-mode span{overflow-wrap:anywhere}.fz-guide-mode-guided{grid-column:1/-1;background:var(--g-soft);border-color:color-mix(in srgb,var(--g-accent) 24%,var(--g-line))}.fz-guide-mode-guided span{flex:1}.fz-guide-mode .fz-guide-mode-arrow{width:18px;height:18px;opacity:.75}.fz-guide[dir=rtl] .fz-guide-mode-arrow{transform:scaleX(-1)}.fz-guide-alternatives{margin-top:8px}.fz-guide-text{background:none;border:0;color:var(--g-accent);font-size:13px!important;min-height:44px;padding:10px 0;text-decoration:underline;text-underline-offset:3px;text-align:start}.fz-guide-status{font-size:14px;padding:22px 0;color:var(--g-muted);margin:0}.fz-guide-status:before{content:'';display:inline-block;width:12px;height:12px;margin-inline-end:10px;border:2px solid var(--g-line);border-top-color:var(--g-accent);border-radius:50%;animation:fzg-spin .8s linear infinite}@keyframes fzg-spin{to{transform:rotate(360deg)}}
.fz-guide-primary{display:block;width:100%;min-height:46px;padding:12px 16px;border:0;border-radius:10px;color:var(--g-on);background:var(--g-accent);font-size:14px!important;font-weight:600!important}.fz-guide-primary:disabled{opacity:.6;cursor:default}.fz-guide-note{font-size:12px;line-height:1.7;color:var(--g-muted);margin:14px 0}.fz-guide-options{display:grid;gap:10px}.fz-guide-choice{min-height:48px;padding:12px 15px;text-align:start;border:1px solid var(--g-line);border-radius:10px;background:var(--g-bg);color:inherit;font-size:14px!important}.fz-guide-suggestions{display:grid;gap:12px}.fz-guide-suggestion{padding:18px;border:1px solid var(--g-line);border-radius:12px}.fz-guide-suggestion h3{font-size:16px;font-weight:600;line-height:1.5;margin:0;overflow-wrap:anywhere}.fz-guide-suggestion p{font-size:13px;line-height:1.6;color:var(--g-muted);margin:8px 0 14px}.fz-guide-suggestion .fz-guide-primary{margin-top:16px}.fz-guide-sources{display:flex;flex-wrap:wrap;gap:6px 12px;margin-top:12px}.fz-guide-sources a{color:var(--g-accent);font-size:12px;line-height:1.7;text-decoration:underline;text-underline-offset:3px;overflow-wrap:anywhere}.fz-guide-suggestion .fz-guide-tradeoff{border-inline-start:2px solid var(--g-line);padding-inline-start:10px}.fz-guide-form label{display:block;font-size:13px}.fz-guide-form input{display:block;min-height:46px;width:100%;margin:8px 0 14px;padding:10px;border:1px solid var(--g-line);border-radius:8px;background:var(--g-bg);color:var(--g-ink);font-size:16px}
.fz-home .fz-guide-open{width:42px;height:42px;display:inline-flex;align-items:center;justify-content:center;border:1px solid var(--fz-line,#e1e6df);border-radius:12px;background:transparent;color:var(--fz-ink,#20312a);cursor:pointer;flex:none}.fz-guide-open svg{width:20px;height:20px}.fz-home .fz-guide-open[hidden],.fz-home .fz-guide-fallback[hidden]{display:none!important}.fz-guide-open:disabled{opacity:.45}.fz-guide-fallback{display:flex}.fz-home[id][data-theme] .fz-results-tools [data-refine-open][hidden]{display:none!important}
.fz-guide textarea{font:inherit;color:var(--g-ink);background:var(--g-bg);font-size:16px;line-height:1.6;resize:vertical;min-height:48px;max-height:140px;border:1px solid var(--g-line);border-radius:12px;padding:12px;width:100%;outline-offset:3px}.fz-guide textarea:focus-visible{outline:2px solid var(--g-accent)}.fz-guide-footer{flex:none;position:relative;padding:12px 20px max(12px,env(safe-area-inset-bottom));background:var(--g-bg);border-top:1px solid var(--g-line);z-index:1}.fz-guide-answer-form{display:flex;align-items:flex-end;gap:10px}.fz-guide-answer-form textarea{min-width:0;flex:1;resize:none}.fz-guide-answer-form .fz-guide-primary{width:auto;flex:none;min-height:48px}.fz-guide-answers{display:flex;gap:8px;flex-wrap:wrap;margin:4px 0 18px}.fz-guide-answers span{font-size:13px;line-height:1.5;padding:7px 11px;border-radius:10px;background:var(--g-soft);overflow-wrap:anywhere}.fz-guide-intro{font-size:15px;line-height:1.7;margin:0 0 16px}.fz-guide-tip{font-size:13px;line-height:1.8;padding-inline-start:12px;border-inline-start:2px solid var(--g-line);margin:20px 0}.fz-guide-search{margin:0;padding:0;border:0;background:var(--g-bg)}.fz-guide-search label{font-size:13px;line-height:1.7}.fz-guide-search textarea{display:block;margin:8px 0 12px}.fz-guide-search .fz-guide-note{margin:8px 0 0;text-align:center}.fz-guide-search textarea{height:68px;min-height:48px;max-height:96px;margin:6px 0 10px}.fz-guide-preferences{border-top:1px solid var(--g-line);margin-top:16px;padding-top:12px}.fz-guide-preferences summary{font-size:13px;line-height:1.7;cursor:pointer;min-height:40px;padding:8px 0}.fz-guide-pref-toggle{display:flex;align-items:center;gap:10px;font-size:13px;line-height:1.6}.fz-guide-pref-toggle input{width:18px;height:18px;accent-color:var(--g-accent);flex:none}.fz-guide-pref-row{padding:12px;background:var(--g-soft);border-radius:12px;margin:10px 0}.fz-guide-pref-row input{width:100%;min-height:44px;font-size:16px;color:var(--g-ink);background:var(--g-bg);border:1px solid var(--g-line);border-radius:8px;padding:8px;margin:4px 0}.fz-guide-pref-actions{display:flex;gap:20px}
.fz-guide-context{display:flex;align-items:center;gap:10px;margin-bottom:12px}.fz-guide-context img{width:40px;height:40px;object-fit:contain;border-radius:8px;background:var(--g-soft);flex:none}.fz-guide-navigation{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:8px}.fz-guide-step{font-size:12px;line-height:1.5;font-weight:600;color:var(--g-muted)}.fz-guide-hint{font-size:13px;line-height:1.6;color:var(--g-muted);margin:0 0 16px}.fz-guide-answers .fz-guide-answer{font:inherit;font-size:12px;min-height:36px;line-height:1.5;padding:7px 11px;border:1px solid var(--g-line);border-radius:18px;background:var(--g-soft);color:var(--g-ink);overflow-wrap:anywhere;text-align:start}.fz-guide-free-answer{margin:12px 0 0}.fz-guide-free-answer summary{font-size:13px;line-height:1.6;min-height:44px;padding:10px 0;color:var(--g-accent);cursor:pointer}.fz-guide-preferences{margin-top:4px}.fz-guide-preferences:has([data-guide-remember]:not(:checked)){border:0;padding-top:0}.fz-guide-body .fz-guide-status{padding:16px 0}.fz-guide-navigation .fz-guide-text{padding:4px 0;min-height:32px}@media(max-height:560px){.fz-guide{max-height:96dvh}.fz-guide-head{padding:10px 16px}.fz-guide-footer{padding:8px 16px}.fz-guide-search textarea{height:48px}.fz-guide-search .fz-guide-note{margin-top:4px}.fz-guide-primary{padding:8px 12px;min-height:44px}}
@media(max-width:360px){.fz-guide-mode-grid{grid-template-columns:1fr}}@media(prefers-reduced-motion:reduce){.fz-guide-status:before{animation:none}}
/* 156.7.43: readable choices and one compact action; no overlaying query dock. */
.fz-guide{--g-line:#c6d1c8;--g-muted:#4d6054;--g-soft:#eef3ee;--g-choice-line:#8a9f90;--g-selected:#345541;--g-selected-ink:#fff;--g-accent:#345541;width:min(560px,calc(100vw - 24px));max-height:calc(100vh - 32px);max-height:min(88dvh,840px);border-radius:24px}
.fz-guide[data-theme=dark]{--g-bg:#1b2922;--g-line:#526a59;--g-muted:#c1d1c5;--g-soft:#2b4133;--g-choice-line:#819b88;--g-selected:#d9ebd8;--g-selected-ink:#173120;--g-accent:#d9ebd8;--g-on:#173120}
.fz-home[id] dialog.fz-guide .fz-guide-head{position:relative;padding:18px 20px;gap:14px}
.fz-home[id] dialog.fz-guide .fz-guide-head h2{font-size:20px;line-height:1.3;font-weight:650;letter-spacing:-.3px}
.fz-home[id] dialog.fz-guide .fz-guide-close{width:44px;height:44px;border-radius:50%;background:var(--g-soft);border-color:var(--g-line)}
.fz-home[id] dialog.fz-guide .fz-guide-body{padding:20px;scroll-padding:16px;scrollbar-width:thin}
.fz-guide-context{font-size:15px;line-height:1.45;margin:0 0 16px;gap:12px}
.fz-guide-context img{width:42px;height:48px;object-fit:contain}
.fz-guide-context>span{min-width:0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.fz-guide-navigation{margin-bottom:12px;min-height:36px}
.fz-guide-step{font-size:14px;font-weight:600}
.fz-guide-navigation .fz-guide-text{padding:8px 12px;min-height:44px;border-radius:10px;background:var(--g-soft)}
.fz-guide-text{font-size:15px!important;line-height:1.5;text-decoration:none;padding:10px 0}
.fz-guide-question{font-size:22px;line-height:1.35;font-weight:650;letter-spacing:-.25px;margin:4px 0 18px;overflow-wrap:anywhere}
.fz-guide-options{gap:10px}
.fz-guide-choice{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:56px;padding:15px 16px;border:1px solid var(--g-choice-line);border-radius:14px;background:var(--g-soft);color:var(--g-ink);font-size:16px!important;line-height:1.45;font-weight:500;text-align:start;transition:background 140ms ease,border-color 140ms ease}
.fz-guide-choice:after{content:'';width:9px;height:9px;flex:0 0 9px;border-inline-end:2px solid currentColor;border-top:2px solid currentColor;transform:rotate(45deg);opacity:.75}
.fz-guide[dir=rtl] .fz-guide-choice:after{transform:rotate(-45deg)}
.fz-guide-choice:focus-visible{outline:3px solid var(--g-selected);outline-offset:3px}
.fz-guide-choice:active{background:var(--g-selected);color:var(--g-selected-ink)}
@media(hover:hover){.fz-guide-choice:hover{background:var(--g-bg);border-color:var(--g-selected)}}
.fz-guide-answers{gap:8px;margin:0 0 18px}
.fz-guide-answers .fz-guide-answer{display:inline-flex;align-items:center;gap:7px;min-height:40px;font-size:14px;line-height:1.4;padding:9px 12px;border-radius:20px;border-color:var(--g-selected);background:var(--g-selected);color:var(--g-selected-ink)}
.fz-guide-answer:before{content:'✓';font-size:14px;font-weight:700}
.fz-guide-free-answer{margin:14px 0 0;border:0;padding:0}
.fz-guide-free-answer summary,.fz-guide-extras>summary{font-size:15px;line-height:1.5;min-height:44px;padding:12px 0;color:var(--g-muted);cursor:pointer}
.fz-guide-free-answer .fz-guide-form{display:grid;gap:10px;padding:4px 0 10px}
.fz-guide-free-answer .fz-guide-primary{width:100%}
.fz-guide-search{margin:18px 0 0;padding:18px 0 0;border-top:1px solid var(--g-line);background:none}
.fz-guide-search label{display:block;font-size:15px;line-height:1.5;font-weight:600}
.fz-guide-search textarea{font-size:16px;line-height:1.5;font-weight:400;height:76px;max-height:140px;margin:8px 0 0;padding:12px;border-color:var(--g-choice-line);background:var(--g-bg);resize:vertical}
.fz-guide-search .fz-guide-note{font-size:14px;text-align:start;margin:8px 0 0}
.fz-guide-extras{margin-top:10px}
.fz-guide-extras>summary{color:var(--g-muted)}
.fz-guide-preferences summary,.fz-guide-pref-toggle{font-size:15px}
.fz-guide-note,.fz-guide-suggestion p{font-size:15px;line-height:1.6}
.fz-guide-status{font-size:16px;min-height:64px}
.fz-guide-footer{position:relative;flex:none;z-index:auto;padding:12px 20px max(12px,env(safe-area-inset-bottom));border-top:1px solid var(--g-line)}
.fz-guide-primary{font-size:16px!important;line-height:1.4;min-height:52px;border-radius:14px}
.fz-guide-footer>.fz-guide-primary{display:flex;align-items:center;justify-content:center;gap:12px;flex-wrap:wrap}
.fz-guide-cost{font-size:14px;font-weight:500;border-inline-start:1px solid currentColor;padding-inline-start:12px;white-space:nowrap}
@media(max-width:360px){.fz-home[id] dialog.fz-guide .fz-guide-head,.fz-home[id] dialog.fz-guide .fz-guide-body{padding:16px}.fz-guide-head h2{font-size:18px!important}.fz-guide-question{font-size:21px}.fz-guide-footer{padding-inline:16px}}
@media(max-height:560px){.fz-guide{max-height:calc(100dvh - 16px)}.fz-home[id] dialog.fz-guide .fz-guide-head{padding:10px 16px}.fz-home[id] dialog.fz-guide .fz-guide-body{padding:16px}.fz-guide-footer{padding:8px 16px}.fz-guide-primary{min-height:48px}}
@media(prefers-reduced-motion:reduce){.fz-guide-choice{transition:none}}
/* Photo composer: a larger reference chip, then + and editable AI answers. */
.fz-guide-photo-composer{display:flex;align-items:center;gap:8px;min-width:0;margin-top:8px;padding:10px;border:1px solid var(--g-choice-line);border-radius:16px;background:var(--g-bg)}
.fz-guide-photo-composer:focus-within{border-color:var(--g-accent);box-shadow:0 0 0 1px var(--g-accent)}
.fz-guide-photo-chip{display:flex;align-items:center;flex:none;gap:2px;padding:4px;border:1px solid var(--g-line);border-radius:12px;background:var(--g-soft)}
.fz-guide-photo-chip img{display:block;width:60px;height:64px;object-fit:cover;border-radius:8px;flex:none;animation:none;transition:none}
.fz-home[id] dialog.fz-guide .fz-guide-photo-remove{display:grid;place-items:center;width:32px;min-width:32px;height:44px;min-height:44px;padding:0;border:0;border-radius:8px;background:none;color:var(--g-muted);font-size:24px;line-height:1}
.fz-home[id] dialog.fz-guide .fz-guide-photo-plus{display:grid;place-items:center;flex:0 0 28px;min-width:28px;min-height:44px;padding:0;border:0;background:none;color:var(--g-muted);font-size:24px;line-height:1;border-radius:8px}
.fz-home[id] dialog.fz-guide .fz-guide-photo-composer textarea{flex:1;min-width:0;width:0;height:72px;min-height:72px;max-height:168px;margin:0;padding:12px 0;border:0;border-radius:0;resize:none;box-shadow:none;background:transparent;outline:none;font-size:16px;line-height:24px}
@media(max-width:360px){.fz-guide-photo-composer{gap:4px;padding:8px}.fz-guide-photo-chip img{width:52px;height:60px}.fz-home[id] dialog.fz-guide .fz-guide-photo-plus{flex-basis:24px;min-width:24px}}
`;document.head.append(style);
const boot=()=>document.querySelectorAll('.fz-home').forEach(mount);boot();let attempts=0;const timer=setInterval(()=>{boot();if(++attempts>80||[...document.querySelectorAll('.fz-home')].every(r=>r.dataset.guideMounted))clearInterval(timer);},250);document.addEventListener('shopify:section:load',boot);document.addEventListener('DOMContentLoaded',boot);
})();
