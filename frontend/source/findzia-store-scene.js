/* FINDZIA_STORE_SCENE_RELEASE=1.0.0 — decorative storefronts, no search requests. */
(() => {
 'use strict';
 const ART=/* STORE_ART */ null;
 const STORES=[
  {name:'IKEA',domain:'ikea.com',title:'Make yourself at home.',image:'home',tiles:['chair','lamp','home'],style:'home'},
  {name:'Apple',domain:'apple.com',title:'AirPods.',image:'airpods',tiles:['airpods'],style:'tech'},
  {name:'NIKE',domain:'nike.com',title:'Air Force 1.',image:'shoe',tiles:['shoe'],style:'sport'},
  {name:'dyson',domain:'dyson.com',title:'Dyson Corrale.',image:'dyson',tiles:['dyson'],style:'beauty'},
  {name:'IKEA',domain:'ikea.com',title:'A place to pause.',image:'chair',tiles:['home','lamp','chair'],style:'living'},
  {name:'NIKE',domain:'nike.com',title:'The everyday icon.',image:'shoe',tiles:['shoe'],style:'editorial'},
  {name:'IKEA',domain:'ikea.com',title:'Light up your space.',image:'lamp',tiles:['chair','home','lamp'],style:'colour'},
  {name:'Apple',domain:'apple.com',title:'Sound. Beautifully.',image:'airpods',tiles:['airpods'],style:'minimal'}
 ];
 const POSITIONS=[[-.46,-.38],[.32,-.46],[-.12,-.28],[.50,-.05],[-.47,.07],[.38,.26],[-.15,.39],[.11,.05],[-.28,-.55],[.14,-.55],[.55,.47],[-.56,.52],[-.53,-.18],[.28,-.18],[-.31,.25],[.30,.56],[.03,-.4],[-.03,.56],[.57,-.43],[-.61,.35],[.52,.07],[-.39,-.4],[.22,.38],[-.25,-.05]];
 const LABELS={en:['Pause background animation','Play background animation'],ar:['إيقاف حركة الخلفية','تشغيل حركة الخلفية'],ja:['背景アニメーションを停止','背景アニメーションを再生'],ko:['배경 애니메이션 일시 정지','배경 애니메이션 재생'],de:['Hintergrundanimation anhalten','Hintergrundanimation abspielen'],fr:['Mettre l’animation en pause','Lancer l’animation'],it:['Metti in pausa lo sfondo','Riproduci lo sfondo'],es:['Pausar la animación de fondo','Reproducir la animación de fondo'],pt:['Pausar a animação de fundo','Reproduzir a animação de fundo'],tr:['Arka plan animasyonunu duraklat','Arka plan animasyonunu oynat'],ru:['Приостановить анимацию фона','Включить анимацию фона'],zh:['暂停背景动画','播放背景动画'],hi:['पृष्ठभूमि एनिमेशन रोकें','पृष्ठभूमि एनिमेशन चलाएँ'],ur:['پس منظر کی حرکت روکیں','پس منظر کی حرکت چلائیں'],id:['Jeda animasi latar','Putar animasi latar'],ms:['Jeda animasi latar','Mainkan animasi latar']};
 const el=(tag,cls,text)=>{const node=document.createElement(tag);node.className=cls;if(text)node.textContent=text;return node;};
 function photo(key,cls){const img=el('img',cls);img.src=ART[key];img.alt='';img.decoding='async';img.draggable=false;return img;}
 function card(store){
  const panel=el('div','fz-store-card fz-store-card--'+store.style);
  const chrome=el('div','fz-store-chrome'),dots=el('span','fz-store-dots'),address=el('span','fz-store-address',store.domain);dots.append(el('i',''),el('i',''),el('i',''));chrome.append(dots,address,el('span','fz-store-plus','+'));
  const header=el('div','fz-store-header'),brand=el('strong','fz-store-brand',store.name),nav=el('span','fz-store-nav');nav.append(el('i',''),el('i',''),el('i',''));header.append(brand,nav,el('span','fz-store-bag'));
  const hero=el('div','fz-store-hero'),copy=el('div','fz-store-copy');copy.append(el('span','fz-store-eyebrow',store.domain),el('strong','fz-store-headline',store.title),el('span','fz-store-line'),el('span','fz-store-pill'));hero.append(copy,photo(store.image,'fz-store-product'));
  const grid=el('div','fz-store-products');for(const key of store.tiles){const tile=el('div','fz-store-product-tile');tile.append(photo(key,''),el('i',''));grid.append(tile);}
  panel.append(chrome,header,hero,grid);return panel;
 }
 function mount(root){
  const home=root.querySelector('[data-dark-home]');if(!home||root.fzStoreScene||!ART)return;
  const scene=el('div','fz-store-scene'),world=el('div','fz-store-world');scene.setAttribute('aria-hidden','true');scene.setAttribute('data-no-i18n','');scene.inert=true;scene.append(world);root.prepend(scene);
  const planes=POSITIONS.map((point,i)=>{const plane=el('div','fz-store-plane');plane.style.setProperty('--store-delay',-(i*7.31%48)+'s');plane.append(card(STORES[i%STORES.length]));world.append(plane);return plane;});
  const toggle=el('button','fz-store-toggle');toggle.type='button';toggle.setAttribute('data-no-i18n','');toggle.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path class="fz-store-pause-icon" d="M9 7v10M15 7v10"/><path class="fz-store-play-icon" d="m9 6 9 6-9 6Z"/></svg>';home.append(toggle);
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');let paused=reduced.matches||navigator.connection?.saveData===true,disposed=false,frame=0;
  try{const saved=sessionStorage.getItem('findzia-store-motion-paused');if(saved!==null)paused=saved==='true'||reduced.matches;}catch(_){}
  root.dataset.storeScene='1.0.0';
  function size(){
   frame=0;if(disposed||home.offsetHeight===0)return;
   const width=root.clientWidth,height=home.offsetHeight;scene.style.height=height+'px';world.style.setProperty('--store-width',Math.min(330,Math.max(190,width*.24))+'px');
   planes.forEach((plane,i)=>{plane.style.setProperty('--store-x',POSITIONS[i][0]*width+'px');plane.style.setProperty('--store-y',POSITIONS[i][1]*height+'px');});
  }
  function queueSize(){if(!frame)frame=requestAnimationFrame(size);}
  function sync(){
   const visible=root.dataset.homeState==='empty'&&root.dataset.pageTarget!=='results';
   const running=visible&&!paused&&!document.hidden&&!root.dataset.searchFocus&&!document.querySelector('dialog[open]');
   scene.dataset.running=String(running);scene.dataset.visible=String(visible);
   toggle.setAttribute('aria-pressed',String(paused));const label=(LABELS[root.dataset.lang]||LABELS.en)[paused?1:0];toggle.setAttribute('aria-label',label);toggle.title=label;
   if(visible)queueSize();
  }
  function change(){paused=!paused;try{sessionStorage.setItem('findzia-store-motion-paused',String(paused));}catch(_){}sync();}
  function preference(){paused=reduced.matches;sync();}
  toggle.addEventListener('click',change);reduced.addEventListener('change',preference);document.addEventListener('visibilitychange',sync);
  const observer=new MutationObserver(sync);observer.observe(root,{attributes:true,attributeFilter:['data-home-state','data-page-target','data-search-focus','data-lang']});
  const dialogs=new MutationObserver(sync);dialogs.observe(document.body,{subtree:true,attributes:true,attributeFilter:['open']});
  const resize=new ResizeObserver(queueSize);resize.observe(home);resize.observe(root);
  function destroy(){disposed=true;cancelAnimationFrame(frame);observer.disconnect();dialogs.disconnect();resize.disconnect();reduced.removeEventListener('change',preference);document.removeEventListener('visibilitychange',sync);scene.remove();toggle.remove();delete root.dataset.storeScene;delete root.fzStoreScene;}
  document.addEventListener('shopify:section:unload',function unload(event){if(event.target?.contains(root)){destroy();document.removeEventListener('shopify:section:unload',unload);}});
  root.fzStoreScene={destroy,release:'1.0.0'};size();sync();
 }
 const start=()=>document.querySelectorAll('.fz-home').forEach(mount);
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
 document.addEventListener('shopify:section:load',start);
})();
