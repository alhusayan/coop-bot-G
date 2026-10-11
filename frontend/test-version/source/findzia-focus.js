/* FINDZIA_FOCUS_RELEASE=156.7.62 — keep the active search composer clear. */
(()=>{'use strict';
 const selector='[data-dark-input],textarea[id^="fz-query-"],input[id^="fz-query-"]';
 const style=document.createElement('style');style.textContent=`
 .fz-home .fz-focus-surface{transition:filter .24s ease,opacity .24s ease!important}
 .fz-home .fz-focus-muted{filter:blur(5px)!important;opacity:.38!important;pointer-events:none!important;user-select:none}
 @media(prefers-reduced-motion:reduce){.fz-home .fz-focus-surface{transition:none!important}}
 `;document.head.append(style);
 function mount(root){if(root.dataset.focusMounted)return;root.dataset.focusMounted='true';
  let input=null,box=null,suppressClick=0,cleanupTimer=0;const muted=new Map(),surfaces=new Set();
  function restore(el,wasInert){el.inert=wasInert;el.classList.remove('fz-focus-muted');}
  function clear(){input=null;box=null;delete root.dataset.searchFocus;for(const [el,original]of muted)restore(el,original);muted.clear();clearTimeout(cleanupTimer);cleanupTimer=setTimeout(()=>{for(const el of surfaces)el.classList.remove('fz-focus-surface');surfaces.clear();},260);}
  function sync(){
   if(!input||!input.isConnected||!box?.isConnected){clear();return;}
   const next=new Set();let branch=box;
   while(branch&&branch!==root){for(const el of branch.parentElement?.children||[]){if(el===branch||el.matches('script,style,link,dialog,input[type=file]'))continue;next.add(el);}branch=branch.parentElement;}
   for(const [el,original]of muted)if(!next.has(el)){restore(el,original);muted.delete(el);}
   for(const el of next)if(!muted.has(el)){muted.set(el,el.inert);surfaces.add(el);el.classList.add('fz-focus-surface');el.getBoundingClientRect();el.classList.add('fz-focus-muted');el.inert=true;}
  }
  function focus(e){if(!e.target.matches?.(selector))return;clearTimeout(cleanupTimer);input=e.target;box=input.closest('[data-dark-form],.fz-search-row');if(!box)return;root.dataset.searchFocus='true';sync();}
  function blur(){queueMicrotask(()=>{if(input&&document.activeElement!==input)clear();});}
  function pointer(e){suppressClick=0;if(!input||box?.contains(e.target))return;e.preventDefault();e.stopImmediatePropagation();suppressClick=Date.now()+900;const field=input;clear();field.blur();}
  function click(e){if(Date.now()<suppressClick){suppressClick=0;e.preventDefault();e.stopImmediatePropagation();}}
  function key(e){if(input&&e.key==='Escape'){e.preventDefault();input.blur();clear();}}
  root.addEventListener('focusin',focus);root.addEventListener('focusout',blur);document.addEventListener('pointerdown',pointer,true);document.addEventListener('click',click,true);root.addEventListener('keydown',key);
  window.addEventListener('pagehide',clear);const observer=new MutationObserver(()=>{if(input)sync();});observer.observe(root,{childList:true,subtree:true});
  document.addEventListener('shopify:section:unload',function dispose(e){if(!e.target?.contains(root))return;clear();observer.disconnect();root.removeEventListener('focusin',focus);root.removeEventListener('focusout',blur);document.removeEventListener('pointerdown',pointer,true);document.removeEventListener('click',click,true);root.removeEventListener('keydown',key);window.removeEventListener('pagehide',clear);document.removeEventListener('shopify:section:unload',dispose);});
 }
 function boot(){document.querySelectorAll('.fz-home').forEach(mount);}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();document.addEventListener('shopify:section:load',boot);
})();
