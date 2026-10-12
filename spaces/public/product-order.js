// One order for discovery, retries, grouped items, saved rooms and the UI.
const tier=o=>(o.availability==='out_of_stock'?2:0)+(o.market_scope==='local'?0:1);
export function compareProducts(a,b){return tier(a)-tier(b)||Number(b.visual_score||0)-Number(a.visual_score||0)||Number(b.price!=null)-Number(a.price!=null);}
export function rankProducts(rows,limit=6){
 const byURL=new Map();for(const row of rows){if(!row?.link)continue;const old=byURL.get(row.link);if(!old||Number(row.visual_score||0)>Number(old.visual_score||0))byURL.set(row.link,row);}
 return [...byURL.values()].sort(compareProducts).slice(0,limit);
}
export function hasLocalOptions(item){return [...(item.offers||[]),...(item.alternatives||[])].some(o=>o.market_scope==='local'&&o.availability!=='out_of_stock');}
export function preferLocalResults(item){
 const local=hasLocalOptions(item),keep=rows=>rankProducts((rows||[]).filter(o=>!local||o.market_scope==='local'),Infinity);
 return {...item,offers:keep(item.offers),alternatives:keep(item.alternatives)};
}
