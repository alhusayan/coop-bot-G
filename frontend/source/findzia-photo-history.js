/* Photo history stays on this browser: at most 12 photos for 30 days. */
(() => {
 'use strict';
 const memory=new Map();let connection,revision=0,writes=Promise.resolve();
 const enabled=()=>{try{return JSON.parse(localStorage.getItem('findzia-account-v1-preferences')||'{}').history!==false;}catch(_){return true;}};
 const notify=()=>document.dispatchEvent(new Event('fz:photo-history'));
 function db(){
  if(!connection)connection=new Promise(resolve=>{
   try{const r=indexedDB.open('findzia-photo-history-v1',1);r.onupgradeneeded=()=>r.result.createObjectStore('photos',{keyPath:'id'});r.onsuccess=()=>{r.result.onversionchange=()=>r.result.close();resolve(r.result);};r.onerror=r.onblocked=()=>resolve(null);}catch(_){resolve(null);}
  });return connection;
 }
 async function read(){
  const d=await db();if(!d)return [...memory.values()];
  return new Promise(resolve=>{try{const r=d.transaction('photos').objectStore('photos').getAll();r.onsuccess=()=>resolve(r.result);r.onerror=()=>resolve([...memory.values()]);}catch(_){resolve([...memory.values()]);}});
 }
 async function edit(action,value){
  const d=await db();
  if(action==='clear')memory.clear();else if(action==='delete')memory.delete(value);else memory.set(value.id,value);
  if(!d)return;
  await new Promise(resolve=>{try{const tx=d.transaction('photos','readwrite');tx.objectStore('photos')[action](...(action==='clear'?[]:[value]));tx.oncomplete=tx.onerror=tx.onabort=()=>resolve();}catch(_){resolve();}});
 }
 async function compress(file){
  let image,url;
  try{
   if(window.createImageBitmap)try{image=await createImageBitmap(file);}catch(_){}
   if(!image){url=URL.createObjectURL(file);image=new Image();image.src=url;await image.decode();}
   const w=image.naturalWidth||image.width,h=image.naturalHeight||image.height;if(!w||!h)return null;
   const scale=Math.min(1,1600/Math.max(w,h)),canvas=document.createElement('canvas');canvas.width=Math.round(w*scale);canvas.height=Math.round(h*scale);
   canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);
   return await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.88));
  }finally{image?.close?.();if(url)URL.revokeObjectURL(url);}
 }
 function enqueue(task){writes=writes.then(task,task).catch(()=>{});return writes;}
 async function save(file){
  const version=revision;if(!enabled()||!file?.type.startsWith('image/'))return;
  try{
   const blob=await compress(file);if(!blob||version!==revision||!enabled())return;
   const hash=await crypto.subtle.digest('SHA-256',await blob.arrayBuffer());const id=Array.from(new Uint8Array(hash),b=>b.toString(16).padStart(2,'0')).join('');
   await enqueue(async()=>{
    if(version!==revision||!enabled())return;
    await edit('put',{id,blob,at:Date.now()});
    const all=(await read()).sort((a,b)=>b.at-a.at);
    for(let i=0;i<all.length;i++)if(i>=12||Date.now()-all[i].at>30*864e5)await edit('delete',all[i].id);
    notify();
   });
  }catch(_){}
 }
 function list(){return enqueue(async()=>{
  const rows=(await read()).sort((a,b)=>b.at-a.at),keep=[];
  for(const row of rows){if(row.blob instanceof Blob&&Date.now()-row.at<30*864e5&&keep.length<12)keep.push(row);else await edit('delete',row.id);}
  return keep;
 });}
 const remove=id=>enqueue(async()=>{await edit('delete',id);notify();});
 function clear(){revision++;return enqueue(async()=>{await edit('clear');notify();});}
 document.addEventListener('fz:history-cleared',clear);
 window.FindziaPhotoHistory={save,list,remove,clear,enabled};
})();
