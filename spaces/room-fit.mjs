// All physical dimensions originate in merchant evidence or customer input.
const text=v=>String(v??'').normalize('NFKC').replace(/[٠-٩]/g,c=>c.charCodeAt(0)-1632).replace(/٫/g,'.').toLowerCase();
const unit='(?:mm|cm|metres?|meters?|m|inches|inch|in|ft|feet|سم|مم|متر|بوصة|″|"|′)';
const factor=u=>/^(mm|مم)$/.test(u)?0.1:/^(m|metres?|meters?|متر)$/.test(u)?100:/^(in|inch|inches|بوصة|″|")$/.test(u)?2.54:/^(ft|feet|′)$/.test(u)?30.48:1;
export function centimetres(value,fallbackUnit=''){
 const s=text(value).trim().replace(/(\d),(\d)/g,'$1.$2');
 const m=s.match(new RegExp('^(\\d+(?:\\.\\d+)?)\\s*('+unit+')?$','i'));
 if(!m||!(m[2]||fallbackUnit))return null;
 const n=Number(m[1])*factor(m[2]||fallbackUnit);return n>=1&&n<=1000?Math.round(n*100)/100:null;
}
export function productDimensions(facts=[],kind=''){
 const result={},evidence=[];
 const put=(kind,value,quote)=>{if(value==null)return;if(result[kind]&&Math.abs(result[kind]-value)>1)result.conflict=true;else{result[kind]=value;evidence.push(quote);}};
 const axis={w:'width',width:'width',d:'depth',depth:'depth',h:'height',height:'height',l:'length',length:'length',diameter:'diameter'};
 for(const f of facts){
  const label=text(f.label),value=text(f.value).replace(/\b(?:dia|diam)\b\.?|[øØ⌀]/g,'diameter ').replace(/\b([wdhl])\s*\)/g,'$1');
  if(/seat|armrest|leg |packag|carton|shipping|cushion|مقعد|ذراع|عبوة/.test(label))continue;
  if(!f.quote||!['merchant_page','indexed_merchant_page'].includes(f.source||'merchant_page'))continue;
  const units=[...value.matchAll(new RegExp('(?<=\\d|\\s)('+unit+')(?![a-z])','gi'))].map(m=>m[1]);
  const fallback=units.length&&new Set(units.map(factor)).size===1?units[0]:(label+' '+value).match(new RegExp('('+unit+')\\s*\\)?$','i'))?.[1]||'';
  if(['width','depth','height','length','diameter'].includes(f.kind))put(f.kind,centimetres(value,fallback),f.quote);
  if(f.kind==='dimensions'||f.kind==='size'){
   const axes='width|depth|height|length|diameter|w|d|h|l';
   for(const m of value.matchAll(new RegExp('\\b('+axes+')\\s*[:=]?\\s*(\\d+(?:[.,]\\d+)?)\\s*('+unit+')?(?![a-z])','gi')))put(axis[m[1]],centimetres(m[2],m[3]||fallback),f.quote);
   for(const m of value.matchAll(new RegExp('(\\d+(?:[.,]\\d+)?)\\s*('+unit+')?\\s*\\(?('+axes+')\\b(?!\\s*[:=]?\\s*\\d)','gi')))put(axis[m[3]],centimetres(m[1],m[2]||fallback),f.quote);
   // An explicit axis order is required. Never guess what a bare 80x50x40 means.
   const order=(label+' '+value).match(new RegExp('\\b('+axes+')\\s*[x×/]\\s*('+axes+')\\s*[x×/]\\s*('+axes+')\\b'));
   const nums=value.match(new RegExp('(\\d+(?:[.,]\\d+)?)\\s*[x×]\\s*(\\d+(?:[.,]\\d+)?)\\s*[x×]\\s*(\\d+(?:[.,]\\d+)?)\\s*('+unit+')','i'));
   if(order&&nums)order.slice(1).forEach((key,i)=>put(axis[key],centimetres(nums[i+1],nums[4]),f.quote));
   // A rectangular rug is planar: its two advertised axes can be rotated.
   // Never apply this convention to ambiguous three-dimensional furniture.
   const flat=kind==='rug'&&value.match(new RegExp('^\\s*(\\d+(?:[.,]\\d+)?)\\s*('+unit+')?\\s*[x×]\\s*(\\d+(?:[.,]\\d+)?)\\s*('+unit+')\\s*$','i'));
   if(flat){put('width',centimetres(flat[1],flat[2]||flat[4]),f.quote);put('depth',centimetres(flat[3],flat[4]),f.quote);}
  }
 }
 if(result.conflict)return null;
 if(result.diameter){result.width??=result.diameter;result.depth??=result.diameter;}
 result.depth??=result.length;
 if(!result.width||!result.depth)return null;
 return {width:result.width,depth:result.depth,height:result.height||null,unit:'cm',evidence:[...new Set(evidence)]};
}
export function furnitureSlots(items=[]){
 const seen=new Set();return items.flatMap(item=>{
  const kind=furnitureKind(item.name_en);
  if(!kind||kind==='accessory'||['keep','measure','quote'].includes(item.mode)||item.status==='kept'||seen.has(String(item.id)))return [];
  seen.add(String(item.id));
  return [{item,kind,quantity:Math.max(1,Math.min(12,Math.round(Number(item.quantity)||1))),layer:kind==='rug'?'rug':kind==='lighting'?(/table|desk|bedside|طاولة|مكتب/i.test(item.name_en)?'surface':/pendant|chandelier|ceiling|ثريا|سقف/i.test(item.name_en)?'ceiling':/wall|حائط|جدار/i.test(item.name_en)?'wall':'floor'):'floor'}];
 });
}
export function furnitureKind(value){
 const name=text(value).replace(/[\u064b-\u065f\u0640]/g,'').split(/\bwith\b|\sمع\s/)[0];
 if(/\b(?:cover|throw|blanket|bedding|bedspread|pillow|cushion|duvet|mattress|decor|organizer|headboard|footboard)\b|\bbed\s+(?:linen|sheet|skirt)|بطاني|مفرش|مفارش|وساد|لحاف|غطاء|مرتبة/.test(name))return 'accessory';
 if(/\brug\b|carpet|سجاد/.test(name))return 'rug';
 if(/lamp|chandelier|pendant|sconce|مصباح|ثريا|أباجور|اباجور/.test(name))return 'lighting';
 if(/sofa|sectional|settee|couch|loveseat|chaise|كنب|أريكة|اريكة|صوفا/.test(name))return 'sofa';
 if(/\bbed\b|bedframe|سرير/.test(name)&&! /\bbedside\b/.test(name))return 'bed';
 if(/chair|stool|bench|ottoman|pouf|كرسي|كراسي|مقعد/.test(name))return 'chair';
 if(/\btable\b|\bdesk\b|nightstand|bedside|طاول|طاوله|مكتب/.test(name))return 'table';
 if(/tv unit|tv stand|media unit|sideboard|console|cabinet|wardrobe|dresser|bookcase|shelving|shelf|خزان|دولاب|بوفيه|وحدة تلفزيون|رفوف/.test(name))return 'storage';
 return null;
}
export function candidateMatchesKind(title,kind){const actual=furnitureKind(title);return !actual||actual===kind;}
export function furnitureInstances(products){
 return products.flatMap(p=>Array.from({length:Math.max(1,Math.min(12,Math.round(p.quantity||1)))},(_,i)=>({...p,id:(p.quantity||1)>1?p.id+'.'+(i+1):p.id,product_id:p.id,copy:i+1})));
}
export function roomMeasurements(raw){
 const width=Number(raw.width),length=Number(raw.length);
 if(![width,length].every(n=>Number.isFinite(n)&&n>=1.5&&n<=15))throw Error('ROOM_MEASUREMENTS_REQUIRED');
 return {width:Math.round(width*100),length:Math.round(length*100),unit:'cm',source:'customer'};
}
const overlap=(a,b,gap=0)=>a.x<b.x+b.w+gap&&a.x+a.w+gap>b.x&&a.z<b.z+b.d+gap&&a.z+a.d+gap>b.z;
export function validateLayout(raw,products,room){
 if(!raw||!Array.isArray(raw.placements)||raw.placements.length!==products.length||!Array.isArray(raw.obstacles)||raw.geometry_confidence!=='high')throw Error('ROOM_LAYOUT_UNCERTAIN');
 const ids=new Set();const placements=raw.placements.map(p=>{
  const product=products.find(x=>x.id===p.id);if(!product||ids.has(p.id)||![0,90,180,270].includes(p.rotation))throw Error('ROOM_LAYOUT_UNCERTAIN');ids.add(p.id);
  const rotated=p.rotation%180!==0,{width,depth}=product.dimensions;
  const box={id:p.id,product_id:product.product_id||p.id,layer:product.layer||'floor',on:p.on||null,x:Number(p.x),z:Number(p.z),w:rotated?depth:width,d:rotated?width:depth,rotation:p.rotation};
  if(![box.x,box.z].every(Number.isFinite)||box.x<10||box.z<10||box.x+box.w>room.width-10||box.z+box.d>room.length-10)throw Error('FURNITURE_DOES_NOT_FIT');
  return box;
 });
 const obstacles=raw.obstacles.map(o=>({x:Number(o.x),z:Number(o.z),w:Number(o.width),d:Number(o.depth),kind:String(o.kind||'fixed').slice(0,40)}));
 if(obstacles.some(o=>![o.x,o.z,o.w,o.d].every(Number.isFinite)||o.x<0||o.z<0||o.w<=0||o.d<=0||o.x+o.w>room.width+1||o.z+o.d>room.length+1))throw Error('ROOM_LAYOUT_UNCERTAIN');
 for(let i=0;i<placements.length;i++){
  const a=placements[i];if(a.layer!=='floor')continue;
  if(placements.slice(0,i).some(p=>p.layer==='floor'&&overlap(p,a,20))||obstacles.some(o=>overlap(o,a,10)))throw Error('FURNITURE_DOES_NOT_FIT');
 }
 for(const p of placements.filter(p=>p.layer==='surface')){
  const host=placements.find(x=>x.id===p.on&&x.layer==='floor');
  if(!host||p.x<host.x||p.z<host.z||p.x+p.w>host.x+host.w||p.z+p.d>host.z+host.d)throw Error('FURNITURE_DOES_NOT_FIT');
 }
 // A real path must remain through the proposed rectangles. This checks only
 // the supplied estimated room geometry; it never claims a measured floor plan.
 const entry=raw.entry;if(!entry||![entry.x,entry.z].every(Number.isFinite)||entry.x<0||entry.z<0||entry.x>room.width||entry.z>room.length)throw Error('ROOM_LAYOUT_UNCERTAIN');
 const step=20,cols=Math.ceil(room.width/step),rows=Math.ceil(room.length/step),blocked=(x,z)=>[...placements.filter(p=>p.layer==='floor'),...obstacles.filter(o=>o.kind!=='door')].some(o=>x>=o.x-30&&x<=o.x+o.w+30&&z>=o.z-30&&z<=o.z+o.d+30);
 const start=[Math.min(cols-1,Math.floor(entry.x/step)),Math.min(rows-1,Math.floor(entry.z/step))];
 const queue=[start],seen=new Set();let reached=false;
 while(queue.length){const [x,z]=queue.shift(),key=x+':'+z;if(x<0||z<0||x>=cols||z>=rows||seen.has(key)||blocked((x+.5)*step,(z+.5)*step))continue;seen.add(key);if(x>cols*.25&&x<cols*.75&&z>rows*.25&&z<rows*.75)reached=true;for(const d of [[1,0],[-1,0],[0,1],[0,-1]])queue.push([x+d[0],z+d[1]]);}
 if(!reached)throw Error('FURNITURE_DOES_NOT_FIT');
 return {placements,obstacles,entry,room,estimated:true,walkway_cm:60,margin_cm:10};
}

// Repair only furniture positions within the model's existing room geometry.
// Doors, fixed obstacles, entry, product dimensions and confidence never change.
export function fitFurnitureLayout(raw,products,room,{maxChecks=12000}={}){
 try{return validateLayout(raw,products,room);}catch(e){if(e.message!=='FURNITURE_DOES_NOT_FIT')throw e;}
 // Layered arrangements need the designer to keep lamps on their hosts and
 // dining groups coherent. Do not scatter a whole-room set with a grid search.
 if(products.length>4||products.some(p=>p.layer&&p.layer!=='floor'))throw Error('FURNITURE_DOES_NOT_FIT');
 const obstacles=raw.obstacles.map(o=>({x:Number(o.x),z:Number(o.z),w:Number(o.width),d:Number(o.depth)}));
 if(obstacles.some(o=>![o.x,o.z,o.w,o.d].every(Number.isFinite)||o.x<0||o.z<0||o.w<=0||o.d<=0||o.x+o.w>room.width+1||o.z+o.d>room.length+1))throw Error('ROOM_LAYOUT_UNCERTAIN');
 const candidates=products.map(product=>{
  const previous=raw.placements.find(p=>p.id===product.id),rows=[];
  if(!previous||![previous.x,previous.z].every(Number.isFinite)||![0,90,180,270].includes(previous.rotation))throw Error('ROOM_LAYOUT_UNCERTAIN');
  for(const rotation of [previous.rotation,(previous.rotation+90)%360]){
   const rotated=rotation%180!==0,w=rotated?product.dimensions.depth:product.dimensions.width,d=rotated?product.dimensions.width:product.dimensions.depth;
   const xs=[previous.x],zs=[previous.z];
   for(let x=10;x<=room.width-w-10;x+=20)xs.push(x);
   for(let z=10;z<=room.length-d-10;z+=20)zs.push(z);
   for(const x of new Set(xs))for(const z of new Set(zs)){
    const p={id:product.id,x,z,w,d,rotation};
    if(x<10||z<10||x+w>room.width-10||z+d>room.length-10||obstacles.some(o=>overlap(o,p,10)))continue;
    rows.push({...p,cost:Math.hypot(x-previous.x,z-previous.z)+(rotation===previous.rotation?0:40)});
   }
  }
  return rows.sort((a,b)=>a.cost-b.cost);
 });
 let checks=0,found;const placed=[];
 const visit=index=>{
  if(found||checks>=maxChecks)return;
  if(index===products.length){try{found=validateLayout({...raw,placements:placed},products,room);}catch{}return;}
  for(const p of candidates[index]){
   if(found||checks>=maxChecks)return;
   checks++;
   if(placed.some((q,i)=>overlap(q,p,products[index].kind==='table'&&products[i].kind==='sofa'||products[index].kind==='sofa'&&products[i].kind==='table'?40:20)))continue;
   placed.push(p);visit(index+1);placed.pop();
  }
 };
 visit(0);if(!found)throw Error('FURNITURE_DOES_NOT_FIT');
 return {...found,positions_adjusted:true};
}
