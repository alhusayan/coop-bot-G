// Planar reference calibration. No inferred depth or assumed camera focal length.
// A projective transform maps the four corners of a known rectangle to metres.
const cross=(a,b,c)=>(b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]);
const distance=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
const polygonArea=p=>Math.abs(p.reduce((s,a,i)=>{const b=p[(i+1)%p.length];return s+a[0]*b[1]-b[0]*a[1];},0))/2;
export function quadrilateral(value){
 if(!Array.isArray(value)||value.length!==4||value.some(p=>!Array.isArray(p)||p.length!==2||p.some(n=>typeof n!=='number'||!Number.isFinite(n)||n<0||n>1)))throw Error('REFERENCE_POINTS_REQUIRED');
 const signs=value.map((p,i)=>cross(p,value[(i+1)%4],value[(i+2)%4]));
 if(signs.some(n=>Math.abs(n)<1e-8)||!signs.every(n=>Math.sign(n)===Math.sign(signs[0])))throw Error('REFERENCE_POINT_ORDER');
 return value.map(p=>[...p]);
}
function solve(rows){
 const n=rows.length;
 for(let k=0;k<n;k++){
  let pivot=k;for(let i=k+1;i<n;i++)if(Math.abs(rows[i][k])>Math.abs(rows[pivot][k]))pivot=i;
  if(Math.abs(rows[pivot][k])<1e-11)throw Error('REFERENCE_UNCLEAR');
  [rows[k],rows[pivot]]=[rows[pivot],rows[k]];
  const scale=rows[k][k];for(let j=k;j<=n;j++)rows[k][j]/=scale;
  for(let i=0;i<n;i++)if(i!==k){const m=rows[i][k];for(let j=k;j<=n;j++)rows[i][j]-=m*rows[k][j];}
 }
 return rows.map(row=>row[n]);
}
export function referenceTransform(points,width,length){
 const target=[[0,0],[width,0],[width,length],[0,length]],rows=[];
 points.forEach(([x,y],i)=>{const [u,v]=target[i];rows.push([x,y,1,0,0,0,-u*x,-u*y,u],[0,0,0,x,y,1,-v*x,-v*y,v]);});
 return [...solve(rows),1];
}
function project(h,[x,y]){
 const d=h[6]*x+h[7]*y+1;if(Math.abs(d)<1e-7)throw Error('REFERENCE_UNSTABLE');
 return [(h[0]*x+h[1]*y+h[2])/d,(h[3]*x+h[4]*y+h[5])/d,d];
}
function dimensions(h,points,reference){
 const p=points.map(v=>project(h,v)),sign=Math.sign(project(h,reference[0])[2]);
 if(p.some(v=>Math.sign(v[2])!==sign||!v.every(Number.isFinite)))throw Error('REFERENCE_UNSTABLE');
 const edges=p.map((v,i)=>distance(v,p[(i+1)%4]));
 return {width:(edges[0]+edges[2])/2,length:(edges[1]+edges[3])/2,area:polygonArea(p),edges,p};
}
export function measureReference({reference_points,reference_width,reference_length,points,source_width,source_height}){
 const ref=quadrilateral(reference_points),area=quadrilateral(points),w=Number(reference_width),l=Number(reference_length);
 if(![w,l].every(n=>Number.isFinite(n)&&n>=.05&&n<=15))throw Error('REFERENCE_SIZE_REQUIRED');
 if(![source_width,source_height].every(n=>Number.isFinite(n)&&n>=160&&n<=10000))throw Error('REFERENCE_IMAGE_REQUIRED');
 const pixels=ref.map(([x,y])=>[x*source_width,y*source_height]);
 if(polygonArea(pixels)<1500||pixels.some((p,i)=>distance(p,pixels[(i+1)%4])<24))throw Error('REFERENCE_TOO_SMALL');
 const h=referenceTransform(ref,w,l),d=dimensions(h,area,ref);
 if(![d.width,d.length].every(n=>n>=.3&&n<=30)||d.area<.1)throw Error('REFERENCE_UNSTABLE');
 // A rectangle is needed for the optional furnishing layout. Do not silently
 // label a trapezoid or an L-shaped room as a measured rectangular room.
 const angles=d.p.map((p,i)=>{const a=d.p[(i+3)%4],b=d.p[(i+1)%4],u=[a[0]-p[0],a[1]-p[1]],v=[b[0]-p[0],b[1]-p[1]];return Math.abs((u[0]*v[0]+u[1]*v[1])/(Math.hypot(...u)*Math.hypot(...v)));});
 if(angles.some(c=>c>Math.sin(12*Math.PI/180))||Math.max(d.edges[0],d.edges[2])/Math.min(d.edges[0],d.edges[2])>1.2||Math.max(d.edges[1],d.edges[3])/Math.min(d.edges[1],d.edges[3])>1.2)throw Error('REFERENCE_AREA_NOT_RECTANGULAR');
 // Sensitivity to a 2px corner perturbation is a conditioning check, not a
 // calibrated confidence interval or a guarantee of physical accuracy.
 let sensitivity=0;
 for(let i=0;i<4;i++)for(let axis=0;axis<2;axis++)for(const direction of [-1,1]){
  const moved=ref.map(p=>[...p]);moved[i][axis]+=direction*2/(axis?source_height:source_width);
  const q=dimensions(referenceTransform(moved,w,l),area,moved);
  sensitivity=Math.max(sensitivity,Math.abs(q.width/d.width-1),Math.abs(q.length/d.length-1),Math.abs(q.area/d.area-1));
 }
 if(sensitivity>.75)throw Error('REFERENCE_UNSTABLE');
 return {width:Math.round(d.width*100),length:Math.round(d.length*100),unit:'cm',area_m2:Math.round(d.area*100)/100,source:'reference_scale',method:'planar_homography',estimated:true,quality:sensitivity>.25?'rough':'standard',accuracy_validated:false,scope:'selected_visible_area',points:area,reference:{points:ref,width_m:w,length_m:l},corner_sensitivity:Math.round(sensitivity*1000)/1000};
}
