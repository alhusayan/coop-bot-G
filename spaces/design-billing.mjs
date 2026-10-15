import {createHmac,randomBytes} from 'node:crypto';
const base='https://api.findzia.com';
export async function designBilling(operation,payload,headers={}){
 const key=process.env.FINDZIA_SPACES_ENGINE_KEY||'';
 if(key.length<32)throw Object.assign(Error('credits_unavailable'),{status:503});
 const path='/internal/spaces/design/'+operation,raw=JSON.stringify({...payload,operation:path});
 const stamp=String(Math.floor(Date.now()/1000)),nonce=randomBytes(16).toString('hex');
 const signature=createHmac('sha256',key).update(stamp+'\n'+nonce+'\n'+raw).digest('hex');
 let response;
 try{response=await fetch(base+path,{method:'POST',headers:{'Content-Type':'application/json',...headers,'X-Findzia-Spaces-Time':stamp,'X-Findzia-Spaces-Nonce':nonce,'X-Findzia-Spaces-Signature':signature},body:raw,redirect:'error',signal:AbortSignal.timeout(20000)});}
 catch{throw Object.assign(Error('credits_unavailable'),{status:503});}
 const data=await response.json().catch(()=>({}));
 if(!response.ok)throw Object.assign(Error(data.error||data.detail||'credits_unavailable'),{status:response.status});
 return data;
}
