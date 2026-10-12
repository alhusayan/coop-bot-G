// One order for discovery, retries, grouped items, saved rooms and the UI.
const tier=o=>(o.availability==='listed_available'?0:2)+(o.market_scope==='local'?0:1);
export function compareProducts(a,b){return tier(a)-tier(b)||Number(b.visual_score||0)-Number(a.visual_score||0)||Number(b.price!=null)-Number(a.price!=null);}
export function rankProducts(rows,limit=6){
 const byURL=new Map();for(const row of rows){
   if(!row?.link)continue;const old=byURL.get(row.link);
   if(!old){byURL.set(row.link,{...row});continue;}
   const best=Number(row.visual_score||0)>Number(old.visual_score||0)?row:old;
   const recent=(Date.parse(row.stock_checked_at||'')||0)>(Date.parse(old.stock_checked_at||'')||0)?row:old;
   byURL.set(row.link,{...best,...Object.fromEntries(['availability','stock_checked_at','stock_version','stock_evidence'].filter(k=>recent[k]!=null).map(k=>[k,recent[k]]))});
 }
 return [...byURL.values()].filter(o=>o.availability!=='out_of_stock').sort(compareProducts).slice(0,limit);
}
export function hasLocalOptions(item){return [...(item.offers||[]),...(item.alternatives||[])].some(o=>o.market_scope==='local'&&o.availability==='listed_available');}
export function preferLocalResults(item){
 if(item.search_engine==='findzia-original')return {...item,offers:rankProducts(item.offers||[],Infinity),alternatives:rankProducts(item.alternatives||[],Infinity)};
 const local=hasLocalOptions(item),keep=rows=>rankProducts((rows||[]).filter(o=>!local||o.market_scope==='local'),Infinity);
 return {...item,offers:keep(item.offers),alternatives:keep(item.alternatives)};
}

