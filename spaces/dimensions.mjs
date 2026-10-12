import {readProductData} from './product-data.mjs';
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
export function dimensionDetails(html,product={},url='',data){
 data??=readProductData(html,url||'https://example.invalid/products/item');
 if(data.variantUnconfirmed)return {size:{},evidence:[],status:'variant_unconfirmed'};
 const source=Object.keys(product).length?product:data.schema||{};
 const size={},evidence=[];
 const measures={},conflicts=new Set();
 const accept=(axis,value,unit,row)=>{
   const cm=centimetres(value,unit);if(!cm)return;
   if(measures[axis]!=null&&Math.abs(measures[axis]-cm)>.1){conflicts.add(axis);return;}
   measures[axis]=cm;evidence.push({axis,cm,source:row.source,text:(row.label+': '+row.value).slice(0,220)});
 };
 const unit='cm|mm|m|inches|inch|in|ft|سم|مم|م|سنتيمتر|centimeters|centimetres';
 const axisOf=v=>({w:'width',width:'width','عرض':'width','العرض':'width',d:'depth',depth:'depth','عمق':'depth','العمق':'depth',l:'length',length:'length','طول':'length','الطول':'length',h:'height',height:'height','ارتفاع':'height','الارتفاع':'height',diameter:'diameter','قطر':'diameter'})[v.toLowerCase()];
 function rowSize(row){
   if(/packag|carton|shipping|seat|seating|capacity|mattress|سعة|تغليف|مقعد/i.test(row.label+' '+(row.section||'')))return;
   const translated=row.label.replace(/Breite|Largeur/gi,'Width').replace(/Tiefe|Profondeur/gi,'Depth').replace(/Höhe|Hauteur/gi,'Height').replace(/Länge|Longueur/gi,'Length');
   const label=translated.replace(/^(?:overall|assembled|product|item)\s+/i,'').trim();
   const single=label.match(new RegExp('^(width|depth|length|height|diameter|w|d|l|h|عرض|العرض|عمق|العمق|طول|الطول|ارتفاع|الارتفاع|قطر)\\s*(?:\\(('+unit+')\\)|('+unit+'))?$', 'i'));
   if(single){accept(axisOf(single[1]),row.value,row.unit||single[2]||single[3],row);return;}
   if(!/dimension|measurement|size|أبعاد|ابعاد|مقاس/i.test(row.label))return;
   // Examples: 30"L x 22"W; W80 x D85 x H90 cm. Each number must have an axis.
   const suffixUnit=row.value.match(new RegExp('('+unit+')\\s*$','i'))?.[1]||row.label.match(new RegExp('\\(('+unit+')\\)','i'))?.[1];
   const suffix=new RegExp('(\\d+(?:[.,]\\d+)?)\\s*("|″|'+unit+')?\\s*([LWDH])(?=\\s*(?:[x×]|$))','gi');
   const prefix=new RegExp('(?:^|[x×]\\s*)([LWDH])\\s*:?\\s*(\\d+(?:[.,]\\d+)?)\\s*("|″|'+unit+')?','gi');
   for(const m of row.value.matchAll(suffix))accept(axisOf(m[3]),m[1],m[2]||suffixUnit,row);
   for(const m of row.value.matchAll(prefix))accept(axisOf(m[1]),m[2],m[3]||suffixUnit,row);
   const order=(row.label+' '+row.value).match(/([LWDH])\s*[x×]\s*([LWDH])(?:\s*[x×]\s*([LWDH]))?/i);
   const nums=row.value.match(/(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)(?:\s*[x×]\s*(\d+(?:[.,]\d+)?))?/i);
   if(order&&nums&&suffixUnit)for(let i=1;i<=3;i++)if(order[i]&&nums[i])accept(axisOf(order[i]),nums[i],suffixUnit,row);
 }
 for(const key of ['width','depth','height','length','diameter'])if(source[key]){const value=source[key];rowSize({label:key,value:typeof value==='object'?value.value:value,unit:value?.unitText||value?.unitCode,source:'product_schema'});}
 for(const prop of [source.additionalProperty||[]].flat())rowSize({label:prop.name||'',value:prop.value,unit:prop.unitText||prop.unitCode,source:'product_schema'});
 data.rows.forEach(rowSize);
 const text=data.visibleText??String(html).replace(/<(script|style|template|noscript)\b[^>]*>[\s\S]*?<\/\1>/gi,' ').replace(/<[^>]+>/g,' ').replace(/&nbsp;|&#160;/g,' ').replace(/&amp;/g,'&').replace(/\s+/g,' ');
 const marker=text.match(/(?:Weight\s*(?:&|and)\s*Dimensions|Product Dimensions|الوزن\s*و\s*الأبعاد)/i);
 const blocks=[...data.texts];
 if(marker)blocks.push(text.slice(marker.index,marker.index+1500).split(/(?:Material|General Specifications|Warranty|Packaging|Package|Shipping|Related products|الخامة|مواصفات عامة)/i)[0]);
 for(let block of blocks){
   // A set has component measurements, not a single overall size. Never merge its chairs/table.
   if(/set contains|set includes|contents of set/i.test(block))continue;
   block=block.replace(/(?:seat(?:ing)?|package|carton|shipping|maximum|minimum)\s*(?:width|depth|length|height)\s*\([^)]*\)\s*:?\s*[\d.,]+/gi,'');
   const individual=new RegExp('\\b(width|depth|length|height|diameter)\\s*(?:\\(('+unit+')\\)\\s*:?\\s*(\\d+(?:[.,]\\d+)?)|:?\\s*(\\d+(?:[.,]\\d+)?)\\s*('+unit+'))','gi');
   for(const m of block.matchAll(individual))rowSize({label:m[1],value:m[3]||m[4],unit:m[2]||m[5],source:'product_details'});
   const combined=block.match(/Dimensions\s*\((cm|mm|m|in)\)\s*\(([LWDH])\s*[x×]\s*([LWDH])\s*[x×]\s*([LWDH])\)\s*:?\s*(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)/i);
   if(combined)for(let i=0;i<3;i++)accept(axisOf(combined[i+2]),combined[i+5],combined[1],{label:'Dimensions',value:combined[0],source:'product_details'});
 }
 for(const k of conflicts)delete measures[k];
 // Safat calls the horizontal furniture span Length and front-to-back span Width.
 // Keep the store's original labels in evidence; apply this convention only for these products.
 const safat=/^https:\/\/(?:www\.)?safathome\.com\//.test(url)&&/sofa|chair|desk|sideboard|console|cabinet|chest|tv unit/i.test(source.name||data.selected?.name||'');
 if(safat&&measures.length&&measures.width&&!measures.depth){measures.depth=measures.width;measures.width=measures.length;delete measures.length;}
 else if(measures.length&&!measures.depth&&!/mirror|wall art|canvas|picture|rug|carpet|curtain/i.test(source.name||data.selected?.name||'')){measures.depth=measures.length;delete measures.length;}
 // Diameter describes two equal footprint axes only when explicitly supplied by the store.
 if(measures.diameter&&!measures.width&&!measures.depth){measures.width=measures.depth=measures.diameter;delete measures.diameter;}
 for(const [k,v] of Object.entries(measures))if(['width','depth','height','length'].includes(k)){if(size[k]&&Math.abs(size[k]-v)>.1){delete size[k];conflicts.add(k);}else size[k]=v;}
 return {size,evidence:evidence.slice(0,20),status:conflicts.size?'conflicting_dimensions':Object.keys(size).length?'confirmed':'unconfirmed'};
}
export function dimensionsFromPage(html,product={},url=''){return dimensionDetails(html,product,url).size;}
export function dimensionLabel(size){return ['width','depth','height','length'].filter(k=>size?.[k]).map(k=>({width:'W',depth:'D',height:'H',length:'L'}[k])+': '+size[k]+' cm').join(' · ');}
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
