// Intent is supplied by visual analysis, not a closed list of trades.
const clean=(value,max=180)=>typeof value==='string'?value.replace(/[<>\u0000-\u001f]/g,' ').replace(/\s+/g,' ').trim().slice(0,max):'';
export function pieceIntent(item={}){
 if(['product','service','both'].includes(item.search_kind))return item.search_kind;
 if(item.mode==='quote')return 'service';
 if(item.mode==='measure')return 'both';
 return 'product';
}
export const canShopPiece=item=>pieceIntent(item)!=='service';
export const canServicePiece=item=>pieceIntent(item)!=='product';
export function normalizePieceIntent(row){
 return {search_kind:pieceIntent(row),name_ar:clean(row.name_ar,70),
  service_query_en:clean(row.service_query_en),service_query_ar:clean(row.service_query_ar),
  surface:['wall','floor','ceiling','ground'].includes(row.surface)?row.surface:'object'};
}
export function pieceName(item,language='en'){
 return clean(language==='ar'&&item.name_ar?item.name_ar:item.name_en,70);
}
export function serviceQuery(item,language='en'){
 const ar=language==='ar',query=clean(ar?item.service_query_ar:item.service_query_en);
 if(query)return query;
 return clean((ar?'تنفيذ وتركيب: ':'Make and install: ')+pieceName(item,language));
}
export function serviceDestination(query,country){
 const url=new URL('https://findzia.com/');
 url.searchParams.set('project','services');url.searchParams.set('q',clean(query));
 if(/^[A-Z]{2}$/.test(country||''))url.searchParams.set('country',country);
 return url.href;
}
