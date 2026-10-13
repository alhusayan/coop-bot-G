// Design-scoped bookmarks. These display snapshots never enter the stock,
// pricing, payment or room-generation pipelines.
export function productKey(value){
 try{const url=new URL(String(value||''));if(!/^https?:$/.test(url.protocol)||url.username||url.password)return '';
  for(const key of [...url.searchParams.keys()])if(/^utm_/i.test(key)||/^(gclid|fbclid)$/i.test(key))url.searchParams.delete(key);
  url.hash='';return url.href;
 }catch{return '';}
}
export function savedPickImage(pick,rows=[]){
 const current=productKey(pick?.image),temporary=url=>/\/api\/media\/verified\//.test(url);
 if(current&&!temporary(current))return current;
 const row=rows.find(value=>productKey(value.url)===productKey(pick?.url));
 for(const source of [row?.audited_image,row?.image,row?.thumbnail,row?.product_image]){
  const url=productKey(source);if(url&&!temporary(url))return url;
 }
 return current;
}
export function designPick(value){
 const url=productKey(value?.url);if(!url||url.length>4000)throw Error('INVALID_INPUT');
 const clean=(text,max)=>String(text||'').slice(0,max);
 return {url,title:clean(value.title,300),store:clean(value.store,120),image:productKey(value.image).slice(0,4000),
  price:clean(value.price,100).replace(/\s+/g,' ').replace(/\s+([.,]\d)/g,'$1').trim(),flag:clean(value.flag,16),saved_at:Date.now()};
}
export function updateDesignPicks(current,value,remove=false){
 const pick=designPick(value),list=Array.isArray(current)?current:[],next=list.filter(x=>productKey(x.url)!==pick.url);
 if(!remove){if(next.length>=20)throw Error('PICKS_LIMIT');next.push(pick);}
 return next;
}
export function hasSavedResults(view,market){
 return !!(view&&Array.isArray(view.items)&&view.items.length&&view.lastSearch?.kind==='image'&&view.lastSearch.country===market);
}
