// Keep DOM nodes, decoded images, keyboard focus and expanded details across polls.
const nodeKey=node=>node.nodeType===1?(node.getAttribute('data-ui-key')||node.id||''):'';
const same=(a,b)=>a.nodeType===b.nodeType&&(a.nodeType!==1||a.tagName===b.tagName)&&nodeKey(a)===nodeKey(b);
export function patchHTML(root,html){
 const template=document.createElement('template');template.innerHTML=html;
 patchChildren(root,template.content);
}
function patchChildren(root,next){
 const available=[...root.childNodes],used=new Set();let cursor=root.firstChild;
 for(const desired of [...next.childNodes]){
   const key=nodeKey(desired);
   let node=key?available.find(n=>!used.has(n)&&nodeKey(n)===key&&same(n,desired)):available.find(n=>!used.has(n)&&!nodeKey(n)&&same(n,desired));
   if(!node)node=desired.cloneNode(true);else updateNode(node,desired);
   if(node!==cursor)root.insertBefore(node,cursor);
   used.add(node);cursor=node.nextSibling;
 }
 for(const node of available)if(!used.has(node))node.remove();
}
function updateNode(node,next){
 if(node.nodeType!==1){if(node.nodeValue!==next.nodeValue)node.nodeValue=next.nodeValue;return;}
 for(const attr of [...node.attributes])if(!next.hasAttribute(attr.name)&&!(node.tagName==='DETAILS'&&attr.name==='open'))node.removeAttribute(attr.name);
 for(const attr of [...next.attributes]){
   if(node.tagName==='IMG'&&attr.name==='src'){updateImage(node,attr.value);continue;}
   if(node.getAttribute(attr.name)!==attr.value)node.setAttribute(attr.name,attr.value);
 }
 patchChildren(node,next);
}
const imageRequests=new WeakMap();
export function updateImage(node,src){
 if(!src){imageRequests.delete(node);node.removeAttribute('src');return;}
 if(node.getAttribute('src')===src){imageRequests.delete(node);return;}
 if(imageRequests.get(node)===src)return;
 imageRequests.set(node,src);
 const pending=new Image();pending.decoding='async';
 pending.onload=async()=>{
   try{await pending.decode();}catch{}
   if(imageRequests.get(node)!==src||!node.isConnected)return;
   imageRequests.delete(node);node.src=src;
   if(!matchMedia('(prefers-reduced-motion: reduce)').matches)node.animate([{opacity:.55},{opacity:1}],{duration:420,easing:'ease-out'});
 };
 pending.onerror=()=>{if(imageRequests.get(node)===src)imageRequests.delete(node);};
 pending.src=src;
}
export function pieceActivity(item){
 if(item.status==='idle')return 'Up next';
 if(item.status!=='searching')return '';
 if(item.search_attempt>1||item.phase==='retrying')return 'Looking further';
 if(item.phase==='checking')return item.search_scope==='local'?'Checking local options':'Checking matches';
 if(item.search_scope==='local')return item.phase==='local-recovery'?'More local stores':'Searching locally';
 if(item.search_scope==='global')return 'International options';
 return 'Searching stores';
}
