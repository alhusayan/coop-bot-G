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
