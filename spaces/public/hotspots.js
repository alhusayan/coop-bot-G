// Keep separate nearby objects selectable (for example a chair under a desk).
export function pieceHotspots(items,width,height){
 const objects=items.flatMap(item=>(item.occurrences?.length?item.occurrences:[{id:item.id,box:item.box}]).map(view=>({...item,box:view.box,marker:view.id})));
 objects.sort((a,b)=>(a.box[2]-a.box[0])*(a.box[3]-a.box[1])-(b.box[2]-b.box[0])*(b.box[3]-b.box[1]));
 const points=[];
 for(const item of objects){
  const [top,left,bottom,right]=item.box;
  const candidates=[[.5,.5],[.2,.2],[.2,.8],[.8,.2],[.8,.8],[.5,.15],[.5,.85]].map(([y,x])=>({y:top+(bottom-top)*y,x:left+(right-left)*x}));
  const clearance=p=>points.length?Math.min(...points.map(other=>Math.hypot((p.x-other.x)*width/1000,(p.y-other.y)*height/1000))):Infinity;
  const choice=candidates.find(point=>clearance(point)>=34)||candidates.sort((a,b)=>clearance(b)-clearance(a))[0];
  points.push({...item,...choice});
 }
 return points;
}

// Image coordinates are normalized to 0..1000, as in the detector inventory.
// Prefer the smaller foreground object when a chair, table and rug overlap.
export function pieceViews(items){
 return items.flatMap(item=>(item.occurrences?.length?item.occurrences:[{id:item.id,box:item.box}]).filter(view=>Array.isArray(view.box)&&view.box.length===4&&view.box.every(Number.isFinite)&&view.box[2]>view.box[0]&&view.box[3]>view.box[1]).map(view=>({id:item.id,marker:String(view.id),box:view.box.map(v=>Math.max(0,Math.min(1000,v)))})));
}
export function pickPhotoPiece(items,x,y){
 if(!Number.isFinite(x)||!Number.isFinite(y)||x<0||x>1000||y<0||y>1000)return null;
 return pieceViews(items).filter(({box:[top,left,bottom,right]})=>x>=left&&x<=right&&y>=top&&y<=bottom)
  .sort((a,b)=>(a.box[2]-a.box[0])*(a.box[3]-a.box[1])-(b.box[2]-b.box[0])*(b.box[3]-b.box[1]))[0]||null;
}
