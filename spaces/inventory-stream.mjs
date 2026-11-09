// Only complete JSON objects are exposed. Strings, escapes and nested geometry
// are tracked so arbitrary network chunks cannot create partial touch targets.
export function completedInventory(text){
 const start=/"items"\s*:\s*\[/.exec(text);if(!start)return [];
 const items=[];let depth=0,quoted=false,escaped=false,begin=-1;
 for(let i=start.index+start[0].length;i<text.length;i++){
  const c=text[i];
  if(quoted){if(escaped)escaped=false;else if(c==='\\')escaped=true;else if(c==='"')quoted=false;continue;}
  if(c==='"'){quoted=true;continue;}
  if(c==='{'||c==='['){if(depth===0)begin=i;depth++;}
  else if(c==='}'||c===']'){
   if(depth===0)break;
   if(--depth===0){try{items.push(JSON.parse(text.slice(begin,i+1)));}catch{break;}}
  }
 }
 return items;
}
export async function readInventoryStream(body,onItems){
 const decoder=new TextDecoder();let pending='',text='',count=0,finish;
 const event=block=>{
  const raw=block.split('\n').filter(x=>x.startsWith('data:')).map(x=>x.slice(5).trim()).join('\n');
  if(!raw||raw==='[DONE]')return;
  const data=JSON.parse(raw);if(data.error)throw Error('GENERATION_FAILED');
  const candidate=data.candidates?.[0];finish=candidate?.finishReason||finish;
  text+=(candidate?.content?.parts||[]).filter(x=>!x.thought).map(x=>x.text||'').join('');
  if(text.length>300000)throw Error('INCOMPLETE_ANALYSIS');
  const items=completedInventory(text);
  if(items.length>count){count=items.length;onItems(items);}
 };
 for await(const chunk of body){pending+=decoder.decode(chunk,{stream:true});pending=pending.replace(/\r\n/g,'\n');let end;while((end=pending.indexOf('\n\n'))>=0){event(pending.slice(0,end));pending=pending.slice(end+2);}}
 pending+=decoder.decode();if(pending.trim())event(pending);
 return {candidates:[{finishReason:finish,content:{parts:[{text}]}}]};
}
