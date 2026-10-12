// A 401 is rejected before a job is created, so only that response may be retried.
// Do not replay a timed-out POST: it may already have started a paid design.
export async function request(path, options={}, runtime={fetch:(...args)=>globalThis.fetch(...args),pathname:globalThis.location?.pathname||'/'}){
  const send=()=>runtime.fetch(path,{...options,credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(35000)});
  let response=await send();
  if(response.status===401&&/^\/trial\/[a-zA-Z0-9_-]+$/.test(runtime.pathname)){
    const renewal=await runtime.fetch(runtime.pathname,{method:'HEAD',credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(15000)});
    if(renewal.ok)response=await send();
  }
  return response;
}
