// Open merchant links from the Space window, never inside its results frame.
const storeLinks='.fz-card-shell a[href],a.fz-tile[href],a[data-offer-key][href],a.fz-saved-link[href],.fz-insights a[href],.design-pick a[href],.replacement-card a[href],.purchase-actions a[href]';
export function bindStoreLinks(doc,open=(url)=>window.open(url,'_blank','noopener,noreferrer')){
 const click=event=>{
  const link=event.target.closest?.(storeLinks);if(!link)return;
  let url;try{url=new URL(link.href,doc.baseURI);}catch{return;}
  if(!['https:','http:'].includes(url.protocol)||url.origin===new URL(doc.baseURI).origin)return;
  link.target='_blank';link.rel=[...new Set((link.rel+' noopener noreferrer').trim().split(/\s+/))].join(' ');
  // Preserve browser shortcuts and middle-click, using the safe native target.
  if(event.button>0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
  event.preventDefault();event.stopImmediatePropagation();
  // Synchronous user activation supports mobile browsers. Never fall back to
  // navigating the Space page if the browser blocks the new tab.
  open(url.href);
 };
 doc.addEventListener('click',click,true);
 return ()=>doc.removeEventListener('click',click,true);
}
