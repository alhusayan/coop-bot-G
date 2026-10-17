// A fixed, owned upstream keeps Space in the same browser origin as the hub.
// Never use client input as a hostname or an upstream URL.
import https from 'node:https';
const assets=new Set(['space-scene.css','space-scene-copy.js','space-cover.webp','app.js','request.js','room-state.js','live-view.js','style.css','hero.webp','icon.svg','design-studio.js','design-studio-copy.js','design-studio.css','store-links.js','spaces-typography.css','markets.js','findzia-shell.js','findzia-shell.css','local-catalog.js','hotspots.js','piece-intent.js','original-results.js','original-results-frame.css','design-picks.js','product-facts.js','product-summary.js','similar-review.js','spaces-theme.js','mobile-viewport.js','account-navigation.js','account-page.js','account-page.css','search-budget.js'].map(name=>'/'+name));
for(const name of ['original.css','fonts.css','motion.css','boot.js','i18n.js','motion.js','support.js','account.js','billing.js','fonts/OFL-Cairo.txt'])assets.add('/findzia/'+name);
export function isSpacePath(path){return path==='/space'||path==='/space/'||path==='/account'||assets.has(path)||/^\/api\/(?:config|findzia-results|jobs(?:\/[a-f0-9]{24}(?:\/(?:measure|product-details(?:\/[a-f0-9]{64})?|catalog\/[0-2]\/\d{1,2}|(?:select|retry|search|focus|replace|results|picks)(?:\/\d+)?))?)?)$/.test(path)||/^\/(?:media|lens-media)\/[a-f0-9]{24}\/[a-zA-Z0-9_.-]+$/.test(path)}
export function transformSpace(path,text,bridge){
 if(path==='/space'||path==='/space/'||path==='/account')return text.replace(/src=(["'])(\/app\.js(?:\?[^"']*)?)\1/g,(_,quote,url)=>`src=${quote}${url}${url.includes('?')?'&':'?'}hubHeader=20261017.3${quote}`).replace('</head>',`${bridge.fonts||''}${bridge.copy?`<script src="${bridge.copy}"></script><script defer src="${bridge.focus}"></script>`:''}<link rel="stylesheet" href="${bridge.style}"><script src="${bridge.script}"></script></head>`);
 if(path==='/findzia/account.js')return text.replace('const dest=new URL(location.href);','const dest=new URL(window.FindziaHubBridge?.authReturnURL()||location.href);').replace('location.assign(url.href);','if(window.FindziaHubBridge)window.FindziaHubBridge.navigateAuth(url.href);else location.assign(url.href);');
 if(path==='/app.js')return text+`
window.FindziaHubBridge?.connectSpace({state:()=>({ready:state.auth===true,busy:submitting,hasImage:!!state.image}),review:()=>view('setup'),serviceQuery:()=>{const item=selected()?.items?.find(x=>x.id===(pointFocus?.id??state.itemId));return item?translate(item.service_query_en||'Make and install: '+item.name_en,item.service_query_ar||'تنفيذ وتركيب: '+(item.name_ar||item.name_en)):translate('Home interior decoration','ديكور داخلي للمنزل')}});
`;
 if(path==='/markets.js')return text.replace("return read('spaces-language-choice-'+market+'-v1')", "return read('findzia-lang')||read('spaces-language-choice-'+market+'-v1')");
 return text;
}
export function proxySpace(req,res,bridge,request=https.request){
 const path=(req.url||'').split('?')[0];
 if(!isSpacePath(path))throw Error('Invalid Space route');
 const transformed=['/space','/space/','/account','/findzia/account.js','/markets.js','/app.js'].includes(path);
 const pass={};for(const name of ['accept','accept-language','content-type','content-length','cookie','authorization','origin','idempotency-key','sec-fetch-site','sec-fetch-mode','range'])if(req.headers[name])pass[name]=req.headers[name];
 // Transform identity bytes, with no stale upstream conditional cache response.
 pass['accept-encoding']='identity';if(!transformed&&req.headers['if-none-match'])pass['if-none-match']=req.headers['if-none-match'];
 const upstreamPath=['/space','/space/'].includes(path)?'/'+(req.url.includes('?')?'?'+req.url.split('?').slice(1).join('?'):''):req.url;
 const fail=()=>{if(res.destroyed)return;if(!res.headersSent)res.writeHead(502,{'Content-Type':'text/plain; charset=utf-8','Cache-Control':'no-store'});res.end('Temporarily unavailable. Please try again.');};
 const upstream=request({hostname:'findzia-spaces-production.up.railway.app',port:443,method:req.method,path:upstreamPath,headers:pass,timeout:180000},reply=>{
  const headers={...reply.headers};for(const name of ['connection','keep-alive','transfer-encoding','upgrade'])delete headers[name];
  headers['x-frame-options']='SAMEORIGIN';
  if(headers['content-security-policy'])headers['content-security-policy']=headers['content-security-policy'].replace("frame-ancestors 'none'","frame-ancestors 'self'");
  if(transformed&&reply.statusCode===200&&req.method!=='HEAD'){
   let size=0;const chunks=[];reply.on('data',chunk=>{size+=chunk.length;if(size>2000000){upstream.destroy();fail();return}chunks.push(chunk)});
   reply.on('error',fail);reply.on('end',()=>{if(res.writableEnded||res.destroyed)return;const body=Buffer.from(transformSpace(path,Buffer.concat(chunks).toString('utf8'),bridge));delete headers.etag;delete headers['content-encoding'];headers['content-length']=body.length;headers['cache-control']='no-store';res.writeHead(200,headers);res.end(body)});
  }else{res.writeHead(reply.statusCode||502,headers);reply.on('error',()=>res.destroy());reply.pipe(res)}
 });
 upstream.on('error',fail);upstream.on('timeout',()=>upstream.destroy());req.on('aborted',()=>upstream.destroy());res.on('close',()=>{if(!res.writableEnded)upstream.destroy()});req.pipe(upstream);
}
