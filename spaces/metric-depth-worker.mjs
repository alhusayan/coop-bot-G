// Depth Anything V2 Small metric indoor checkpoint (Apache-2.0), exported by
// Kornia. Fixed, integrity-checked weights; no room data is sent to the host.
import {parentPort,workerData} from 'node:worker_threads';
import {mkdir,readFile,writeFile,rename} from 'node:fs/promises';
import {resolve} from 'node:path';
import {createHash} from 'node:crypto';
import {InferenceSession,Tensor} from 'onnxruntime-node';
import sharp from 'sharp';
const SHA='50dbcac7a6d667e365a3ceffdf51cc497aa5e06b6d2c1d5824c252640fbf5bf3';
const URL='https://huggingface.co/kornia/depth-anything/resolve/86f40563e7e87a0839be758988aa804930409a61/depth-anything-v2-metric-small-indoor.onnx';
try{
 await mkdir(workerData.cache,{recursive:true});
 const path=resolve(workerData.cache,'metric-small-392.onnx');let model;
 try{model=await readFile(path);}catch{}
 if(!model||createHash('sha256').update(model).digest('hex')!==SHA){
  const response=await fetch(URL,{signal:AbortSignal.timeout(100000)});if(!response.ok)throw Error('MODEL_DOWNLOAD');
  model=Buffer.from(await response.arrayBuffer());if(createHash('sha256').update(model).digest('hex')!==SHA)throw Error('MODEL_INTEGRITY');
  await writeFile(path+'.tmp',model,{mode:0o600});await rename(path+'.tmp',path);
 }
 const size=392,source=await sharp(workerData.bytes).rotate().metadata();
 // Preserve perspective: letterbox rather than stretch the room into a square.
 const scale=Math.min(size/source.width,size/source.height),width=Math.round(source.width*scale),height=Math.round(source.height*scale);
 const left=Math.floor((size-width)/2),top=Math.floor((size-height)/2);
 const rgb=await sharp(workerData.bytes).rotate().resize(width,height).removeAlpha().toColourspace('srgb').extend({left,right:size-width-left,top,bottom:size-height-top,background:'#7c7470'}).raw().toBuffer();
 const input=new Float32Array(3*size*size),mean=[.485,.456,.406],std=[.229,.224,.225];
 for(let i=0;i<size*size;i++)for(let c=0;c<3;c++)input[c*size*size+i]=(rgb[i*3+c]/255-mean[c])/std[c];
 const session=await InferenceSession.create(model,{intraOpNumThreads:2,interOpNumThreads:1,executionProviders:['cpu']});
 const result=await session.run({input:new Tensor('float32',input,[1,3,size,size])});
 const values=Float32Array.from(result.depth.data);await session.release();
 if(values.length!==size*size||values.some(x=>!Number.isFinite(x)||x<=0||x>20.1))throw Error('INVALID_DEPTH');
 const gray=Buffer.from(values.map(z=>Math.max(0,Math.min(255,255*(1-z/20)))));
 const png=await sharp(gray,{raw:{width:size,height:size,channels:1}}).extract({left,top,width,height}).resize({width:768}).png().toBuffer();
 parentPort.postMessage({values,png,size,width,height,left,top,source_width:source.width,source_height:source.height,model:'Depth Anything V2 Metric Indoor Small',kind:'metric_depth',model_sha256:SHA});
}catch(e){parentPort.postMessage({error:String(e.message).slice(0,160)});}
