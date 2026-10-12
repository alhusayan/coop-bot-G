// Only explicit manufacturer/store dimensions. Never infer centimetres from photographs.
const axes={width:/^(?:width|w|عرض|العرض)$/i,depth:/^(?:depth|d|length|l|عمق|العمق|طول|الطول)$/i,height:/^(?:height|h|ارتفاع|الارتفاع)$/i};
export function centimetres(value,unit){
 if(value&&typeof value==='object')return centimetres(value.value,value.unitText||value.unitCode);
 const text=String(value??'').replace(/[٠-٩]/g,c=>c.charCodeAt(0)-1632).replace(/٫/g,'.').trim();
 const match=text.match(/^(\d+(?:[.,]\d+)?)\s*([a-z"′″\u0600-\u06ff]*)$/i);if(!match)return null;
 const units=String(unit||match[2]).toLowerCase().trim();
 const factor={cm:1,cmt:1,centimeter:1,centimeters:1,centimetre:1,centimetres:1,'سم':1,mm:.1,mmt:.1,'مم':.1,m:100,mtr:100,'م':100,in:2.54,inh:2.54,inch:2.54,inches:2.54,'"':2.54,'″':2.54,ft:30.48,foot:30.48,feet:30.48,'′':30.48}[units];
 const n=Number(match[1].replace(',','.'))*factor;return Number.isFinite(n)&&n>0&&n<=10000?Math.round(n*100)/100:null;
}
export function dimensionsFromProduct(product={}){
 const result={};
 for(const [key,match] of Object.entries(axes)){
   const direct=centimetres(product[key]??(key==='depth'?product.length:undefined));if(direct)result[key]=direct;
   for(const p of (Array.isArray(product.additionalProperty)?product.additionalProperty:product.additionalProperty?[product.additionalProperty]:[])){
     const name=String(p.name||'').trim(),unit=name.match(/\(([^)]+)\)/)?.[1],label=name.replace(/\([^)]*\)/g,'').trim();
     if(match.test(label)){const cm=centimetres(p.value,p.unitText||p.unitCode||unit);if(cm)result[key]=cm;}
   }
 }
 return result;
}
export function dimensionsFromPage(html,product={}){
 const size=dimensionsFromProduct(product);
 const text=String(html).replace(/<(script|style|template|noscript)\b[^>]*>[\s\S]*?<\/\1>/gi,' ').replace(/<[^>]+>/g,' ').replace(/&nbsp;|&#160;/g,' ').replace(/&amp;/g,'&').replace(/\s+/g,' ');
 // Retail specification block only; never use package, shipping or related-product dimensions.
 const marker=text.match(/(?:Weight\s*(?:&|and)\s*Dimensions|Product Dimensions|الوزن\s*و\s*الأبعاد)/i);
 if(!marker)return size;
 const block=text.slice(marker.index+marker[0].length,marker.index+marker[0].length+1500).split(/(?:Material|General Specifications|Warranty|Packaging|Package|Shipping|Related products|الخامة|مواصفات عامة)/i)[0];
 for(const [key,label] of [['width','Width|العرض'],['depth','Depth|Length|العمق|الطول'],['height','Height|الارتفاع']]){
   const m=block.match(new RegExp('(?:'+label+')\\s*\\((cm|mm|m|in|inch|سم|مم)\\)\\s*:?\\s*(\\d+(?:[.,]\\d+)?)','i'));
   if(m&&!size[key])size[key]=centimetres(m[2],m[1]);
   const labelled=block.match(new RegExp('(?:'+label+')\\s*:?\\s*(\\d+(?:[.,]\\d+)?)\\s*(cm|mm|inches|inch|in|سم|مم)\\b','i'));
   if(labelled&&!size[key])size[key]=centimetres(labelled[1],labelled[2]);
 }
 const combined=block.match(/Dimensions\s*\((cm|mm|m|in)\)\s*\(([LWDH])\s*[x×]\s*([LWDH])\s*[x×]\s*([LWDH])\)\s*:?\s*(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)/i);
 if(combined)for(let i=0;i<3;i++){const key={l:'depth',w:'width',d:'depth',h:'height'}[combined[i+2].toLowerCase()];if(!size[key])size[key]=centimetres(combined[i+5],combined[1]);}
 return size;
}
export function dimensionLabel(size){return ['width','depth','height'].filter(k=>size?.[k]).map(k=>({width:'W',depth:'D',height:'H'}[k])+': '+size[k]+' cm').join(' · ');}
export function usableSize(size){return ['width','depth','height'].every(k=>Number.isFinite(size?.[k])&&size[k]>0&&size[k]<=10000);}
export function roomMeasurements(input){
 const width=Number(input.width),length=Number(input.length);
 if(!Number.isFinite(width)||!Number.isFinite(length)||width<1||length<1||width>50||length>50)throw Error('ROOM_SIZE_REQUIRED');
 return {width_cm:Math.round(width*100),length_cm:Math.round(length*100)};
}
export function measuredLimits(input,items){
 const limits={};for(const item of items){const value=input?.[item.id];if(!value)continue;
   if(!['width','depth','height'].every(k=>Number.isFinite(Number(value[k]))&&Number(value[k])>0&&Number(value[k])<=10000))throw Error('INVALID_MEASUREMENTS');
   limits[item.id]=Object.fromEntries(['width','depth','height'].map(k=>[k,Number(value[k])]));
 }return limits;
}
export function fitSize(size,slot,room,measured){
 if(!usableSize(size))return {ok:false,reason:'Store size missing'};
 const cap=measured||slot?.space,aim=slot?.target;
 if(!usableSize(cap)||!measured&&(!usableSize(aim)||!(Number.isFinite(slot?.confidence)&&slot.confidence>=85)))return {ok:false,reason:'Measure this space'};
 if(size.width>room.width_cm&&size.width>room.length_cm||size.depth>room.width_cm&&size.depth>room.length_cm)return {ok:false,reason:'Too large for this room'};
 if(['width','depth','height'].some(k=>size[k]>cap[k]))return {ok:false,reason:'Too large for this space'};
 // Target proportions are estimates: reject substantial scale changes, never call them measured.
 if(!measured&&['width','depth','height'].some(k=>size[k]<aim[k]*.75||size[k]>aim[k]*1.25))return {ok:false,reason:'Different size from this design'};
 return {ok:true,status:measured?'measured_envelope':'estimated',size_cm:size,space_cm:cap,size_verified:false};
}
