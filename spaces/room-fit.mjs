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
export function productDimensions(facts=[]){
 const result={},evidence=[];
 const put=(kind,value,quote)=>{if(value==null)return;if(result[kind]&&Math.abs(result[kind]-value)>1)result.conflict=true;else{result[kind]=value;evidence.push(quote);}};
 const axis={w:'width',width:'width',d:'depth',depth:'depth',h:'height',height:'height',l:'length',length:'length',diameter:'diameter'};
 for(const f of facts){
  const label=text(f.label),value=text(f.value);
  if(/seat|armrest|leg |packag|carton|shipping|cushion|مقعد|ذراع|عبوة/.test(label))continue;
  if(!f.quote||!['merchant_page','indexed_merchant_page'].includes(f.source||'merchant_page'))continue;
  const fallback=(label+' '+value).match(new RegExp('('+unit+')\\s*\\)?$','i'))?.[1]||'';
  if(['width','depth','height','length','diameter'].includes(f.kind))put(f.kind,centimetres(value,fallback),f.quote);
  if(f.kind==='dimensions'||f.kind==='size'){
   for(const m of value.matchAll(new RegExp('\\b(width|depth|height|length|diameter|w|d|h|l)\\s*[:=]?\\s*(\\d+(?:[.,]\\d+)?)\\s*('+unit+')?','gi')))put(axis[m[1]],centimetres(m[2],m[3]||fallback),f.quote);
   // An explicit axis order is required. Never guess what a bare 80x50x40 means.
   const order=(label+' '+value).match(/\b(w|width)\s*[x×/]\s*(d|depth|l|length)\s*[x×/]\s*(h|height)\b/);
   const nums=value.match(new RegExp('(\\d+(?:[.,]\\d+)?)\\s*[x×]\\s*(\\d+(?:[.,]\\d+)?)\\s*[x×]\\s*(\\d+(?:[.,]\\d+)?)\\s*('+unit+')','i'));
   if(order&&nums)order.slice(1).forEach((key,i)=>put(axis[key],centimetres(nums[i+1],nums[4]),f.quote));
  }
 }
 if(result.conflict)return null;
 if(result.diameter){result.width??=result.diameter;result.depth??=result.diameter;}
 result.depth??=result.length;
 if(!result.width||!result.depth)return null;
 return {width:result.width,depth:result.depth,height:result.height||null,unit:'cm',evidence:[...new Set(evidence)]};
}
export function furnitureSlots(items=[]){
 const kinds=['sofa','bed','table','chair','storage'];
 const seen=new Set(),out=[];
 for(const kind of kinds){const item=items.find(x=>x.mode!=='keep'&&x.status!=='kept'&&furnitureKind(x.name_en)===kind&&!seen.has(x.id));if(item){seen.add(item.id);out.push({item,kind});}}
 return out.slice(0,3);
}
export function furnitureKind(value){
 const name=text(value).split(/\bwith\b/)[0];
 if(/\b(?:cover|throw|blanket|bedding|bedspread|pillow|cushion|duvet|mattress|rug|lamp|decor|organizer|headboard|footboard)\b|\bbed\s+(?:linen|sheet|skirt)/.test(name))return 'accessory';
 if(/sofa|sectional|settee/.test(name))return 'sofa';
 if(/\bbed\b|bedframe/.test(name)&&! /\bbedside\b/.test(name))return 'bed';
 if(/chair|stool/.test(name))return 'chair';
 if(/coffee table|dining table|writing desk|\bdesk\b/.test(name))return 'table';
 if(/tv unit|sideboard|console|cabinet|wardrobe/.test(name))return 'storage';
 return null;
}
export function candidateMatchesKind(title,kind){const actual=furnitureKind(title);return !actual||actual===kind;}
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
  const box={id:p.id,x:Number(p.x),z:Number(p.z),w:rotated?depth:width,d:rotated?width:depth,rotation:p.rotation};
  if(![box.x,box.z].every(Number.isFinite)||box.x<10||box.z<10||box.x+box.w>room.width-10||box.z+box.d>room.length-10)throw Error('FURNITURE_DOES_NOT_FIT');
  return box;
 });
 const obstacles=raw.obstacles.map(o=>({x:Number(o.x),z:Number(o.z),w:Number(o.width),d:Number(o.depth),kind:String(o.kind||'fixed').slice(0,40)}));
 if(obstacles.some(o=>![o.x,o.z,o.w,o.d].every(Number.isFinite)||o.x<0||o.z<0||o.w<=0||o.d<=0||o.x+o.w>room.width+1||o.z+o.d>room.length+1))throw Error('ROOM_LAYOUT_UNCERTAIN');
 for(let i=0;i<placements.length;i++){
  if(placements.slice(0,i).some(p=>overlap(p,placements[i],20))||obstacles.some(o=>overlap(o,placements[i],10)))throw Error('FURNITURE_DOES_NOT_FIT');
 }
 // A real path must remain through the proposed rectangles. This checks only
 // the supplied estimated room geometry; it never claims a measured floor plan.
 const entry=raw.entry;if(!entry||![entry.x,entry.z].every(Number.isFinite)||entry.x<0||entry.z<0||entry.x>room.width||entry.z>room.length)throw Error('ROOM_LAYOUT_UNCERTAIN');
 const step=20,cols=Math.ceil(room.width/step),rows=Math.ceil(room.length/step),blocked=(x,z)=>[...placements,...obstacles.filter(o=>o.kind!=='door')].some(o=>x>=o.x-30&&x<=o.x+o.w+30&&z>=o.z-30&&z<=o.z+o.d+30);
 const start=[Math.min(cols-1,Math.floor(entry.x/step)),Math.min(rows-1,Math.floor(entry.z/step))];
 const queue=[start],seen=new Set();let reached=false;
 while(queue.length){const [x,z]=queue.shift(),key=x+':'+z;if(x<0||z<0||x>=cols||z>=rows||seen.has(key)||blocked((x+.5)*step,(z+.5)*step))continue;seen.add(key);if(x>cols*.25&&x<cols*.75&&z>rows*.25&&z<rows*.75)reached=true;for(const d of [[1,0],[-1,0],[0,1],[0,-1]])queue.push([x+d[0],z+d[1]]);}
 if(!reached)throw Error('FURNITURE_DOES_NOT_FIT');
 return {placements,obstacles,entry,room,estimated:true,walkway_cm:60,margin_cm:10};
}
