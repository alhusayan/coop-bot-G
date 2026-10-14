import {Worker} from 'node:worker_threads';
import {resolve} from 'node:path';
let busy=false;
export async function estimateDepth(bytes,{cache=resolve(process.env.SPACES_DATA_DIR||'data','depth-model'),timeout=180000}={}){
 if(busy)throw Error('FURNISH_BUSY');
 busy=true;
 try{return await new Promise((resolve,reject)=>{
  const worker=new Worker(new URL('./depth-worker.mjs',import.meta.url),{workerData:{bytes,cache},execArgv:[]});
  let settled=false;
  const finish=(err,value)=>{if(settled)return;settled=true;clearTimeout(timer);void worker.terminate();err?reject(err):resolve(value);};
  const timer=setTimeout(()=>finish(Error('DEPTH_UNAVAILABLE')),timeout);
  worker.once('message',data=>data.error?finish(Object.assign(Error('DEPTH_UNAVAILABLE'),{cause:data.error})):finish(null,{...data,png:Buffer.from(data.png)}));
  worker.once('error',error=>finish(Object.assign(Error('DEPTH_UNAVAILABLE'),{cause:error.message})));
  worker.once('exit',()=>{if(!settled)finish(Error('DEPTH_UNAVAILABLE'));});
 });}finally{busy=false;}
}
