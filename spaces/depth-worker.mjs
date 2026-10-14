// Public Apache-2.0 model weights; room pixels stay inside this process.
import {parentPort,workerData} from 'node:worker_threads';
import {pipeline,env,RawImage} from '@huggingface/transformers';
import sharp from 'sharp';
env.cacheDir=workerData.cache;
env.allowLocalModels=false;
try{
 const pipe=await pipeline('depth-estimation','onnx-community/depth-anything-v2-small',{
  revision:'4472b7362082ad9968fee890ca0f1e5aca36b93d',dtype:'q8',device:'cpu',
  session_options:{intraOpNumThreads:2,interOpNumThreads:1}
 });
 const input=await RawImage.fromBlob(new Blob([workerData.bytes],{type:'image/jpeg'}));
 const {depth}=await pipe(input);
 const png=await sharp(Buffer.from(depth.data),{raw:{width:depth.width,height:depth.height,channels:depth.channels}}).resize({width:768,withoutEnlargement:true}).png().toBuffer();
 await pipe.dispose();
 parentPort.postMessage({png,model:'Depth Anything V2 Small',kind:'relative_depth'});
}catch(e){parentPort.postMessage({error:String(e.message).slice(0,160)});}
