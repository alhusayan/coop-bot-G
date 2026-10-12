// Leave capacity for the piece the customer opens. A room scan must never
// occupy every transport slot with unrelated pieces.
export function createSearchScheduler({limit=3,backgroundLimit=2}={}){
 const waiting=[],running=new Set(),entries=new Map();
 function drain(){
  while(running.size<limit){
   let index=waiting.findIndex(x=>x.interactive);
   if(index<0){
    if([...running].filter(x=>!x.interactive).length>=backgroundLimit)return;
    index=0;
   }
   const entry=waiting.splice(index,1)[0];if(!entry)return;
   running.add(entry);
   Promise.resolve().then(()=>entry.run({queue_ms:Date.now()-entry.queued,interactive:entry.interactive})).then(entry.resolve,entry.reject).finally(()=>{running.delete(entry);entries.delete(entry.key);drain();});
  }
 }
 function promote(key){const entry=entries.get(key);if(!entry)return false;entry.interactive=true;drain();return true;}
 function run(key,fn,{interactive=false}={}){
  if(entries.has(key)){if(interactive)promote(key);return entries.get(key).promise;}
  const entry={key,run:fn,interactive,queued:Date.now()};
  entry.promise=new Promise((resolve,reject)=>Object.assign(entry,{resolve,reject}));
  entries.set(key,entry);waiting.push(entry);drain();return entry.promise;
 }
 return {run,promote};
}
