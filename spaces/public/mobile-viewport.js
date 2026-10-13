// Account for Safari's changing toolbar and the on-screen keyboard. No fixed
// body or translated page container: long forms remain one scrollable document.
(()=>{
 const html=document.documentElement;
 let pending=false;
 function sync(){
  pending=false;
  const viewport=window.visualViewport;
  if(viewport&&Math.abs(viewport.scale-1)>.05)return;
  html.style.setProperty('--spaces-viewport-height',Math.round(Math.min(window.innerHeight,viewport?.height||window.innerHeight))+'px');
  html.style.setProperty('--spaces-viewport-top',Math.round(viewport?.offsetTop||0)+'px');
 }
 function schedule(){if(!pending){pending=true;requestAnimationFrame(sync);}}
 sync();window.addEventListener('resize',schedule,{passive:true});window.addEventListener('pageshow',schedule);
 window.visualViewport?.addEventListener('resize',schedule,{passive:true});window.visualViewport?.addEventListener('scroll',schedule,{passive:true});
})();
