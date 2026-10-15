// Serve the current Findzia document in a same-origin results frame. Its own
// scripts own search, billing, image validation, ranking and result rendering.
// Only asset addresses and frame-only presentation change; scripts stay intact.
let cached,flight;
export function frameDocument(html){
 if(!html.includes('fzRefineBridge.searchPhoto=')||!html.includes('fzRefineBridge'))throw Error('ORIGINAL_PAGE_UNAVAILABLE');
 return html.replace(/((?:src|href)=["'])\/(assets\/[^"']+|favicon\.svg)(["'])/g,'$1https://findzia.com/$2$3')
  // Spaces shares the original search engine, with its own reviewed UI copy.
  .replace(/(src=["'])https:\/\/findzia\.com\/assets\/findzia-i18n\.[^"']+\.js(["'])/g,'$1/findzia/i18n.js$2')
  .replace(/(src=["'])https:\/\/findzia\.com\/assets\/findzia-billing\.[^"']+\.js(["'])/g,'$1/findzia/billing.js$2')
  .replace(/<html\b/i,'<html data-findzia-spaces-results')
  .replace(/<\/head>/i,'<link rel="stylesheet" href="/original-results-frame.css"><link rel="stylesheet" href="/spaces-typography.css"></head>');
}
export function accountDocument(html){
 return html.replace('data-findzia-spaces-results','data-findzia-spaces-account')
  .replace('<link rel="stylesheet" href="/original-results-frame.css">','<link rel="stylesheet" href="/account-page.css"><script type="module" src="/account-page.js"></script>');
}
export async function originalPage(fetcher=fetch){
 if(cached&&Date.now()-cached.at<60000)return cached.html;
 if(flight)return flight;
 flight=(async()=>{
  const response=await fetcher('https://findzia.com/trial/original',{redirect:'error',signal:AbortSignal.timeout(20000)});
  if(!response.ok||!response.headers.get('content-type')?.includes('text/html'))throw Error('ORIGINAL_PAGE_UNAVAILABLE');
  const html=await response.text();if(html.length>3000000)throw Error('ORIGINAL_PAGE_UNAVAILABLE');
  cached={at:Date.now(),html:frameDocument(html)};return cached.html;
 })().finally(()=>flight=null);
 return flight;
}
// A saved UI view is private to its room owner and never becomes a trusted
// inventory/price record or a paid request. No credentials or photo bytes persist.
export function savedOriginalView(value,market){
 if(!value||!Array.isArray(value.items)||!value.items.length||value.items.length>300)throw Error('INVALID_INPUT');
 if(value.lastSearch?.country!==market)throw Error('INVALID_INPUT');
 const view={query:String(value.query||'').slice(0,500),input:String(value.input||'').slice(0,500),
  items:value.items,sort:['relevance','price','price-desc','newest'].includes(value.sort)?value.sort:'relevance',
  filter:['all','local','global','alternative','social'].includes(value.filter)?value.filter:'all',
  layout:value.layout,arrival:Number(value.arrival)||value.items.length,scroll:0,
  moreExhausted:!!value.moreExhausted,moreError:!!value.moreError,message:String(value.message||'').slice(0,600),
  lastSearch:{kind:'image',country:market,query:String(value.lastSearch.query||'').slice(0,500),mime_type:'image/jpeg'}};
 if(JSON.stringify(view).length>2500000)throw Error('INVALID_INPUT');
 return view;
}
