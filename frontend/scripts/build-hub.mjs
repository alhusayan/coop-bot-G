// The unified home is assembled after both independent storefront builds.
// Keep product search on /search, with the previous trial/original alias intact.
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
const base=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const source=resolve(base,'source'),out=resolve(base,'public');
const manifest=JSON.parse(readFileSync(resolve(out,'release.json'),'utf8'));
const hash=body=>createHash('sha256').update(body).digest('hex');
function emit(url,file,body,type,immutable=false){body=Buffer.from(body);const path=resolve(out,file);mkdirSync(dirname(path),{recursive:true});writeFileSync(path,body);manifest.routes[url]={file,sha256:hash(body),type,immutable};return url;}
const files={
 'world.webp':'hub-art/world.webp','product.webp':'hub-art/product.webp','shopping.webp':'hub-art/shopping-wide.webp','service.webp':'services-art/ac.webp',
 'findzia-boot.js':'findzia-boot.js','findzia-hub-bridge.css':'findzia-hub-bridge.css','findzia-hub.css':'findzia-hub.css','findzia-hub.js':'findzia-hub.js','findzia-hub-bridge.js':'findzia-hub-bridge.js'
};
const assets={};
for(const [key,path] of Object.entries(files)){
 const body=readFileSync(resolve(source,path)),ext=key.split('.').at(-1),file='assets/'+key.replace('.'+ext,'.'+hash(body).slice(0,16)+'.'+ext);
 assets[key]=emit('/'+file,file,body,ext,true);
}
const bridgeTags=`<link rel="stylesheet" href="${assets['findzia-hub-bridge.css']}"><script src="${assets['findzia-hub-bridge.js']}"></script>`;
manifest.hubBridge={script:assets['findzia-hub-bridge.js'],style:assets['findzia-hub-bridge.css']};
// Keep original account and billing modules in each project.
const originalEntry=manifest.routes['/'];
let original=readFileSync(resolve(out,originalEntry.file),'utf8').replace('<link rel="canonical" href="https://findzia.com/">','<link rel="canonical" href="https://findzia.com/search">');
original=original.replace('</head>',bridgeTags+'</head>');
emit('/search','search/index.html',original,'html');manifest.routes['/search/']=manifest.routes['/search'];
for(const url of ['/pages/findzia','/jp','/jp/'])manifest.routes[url]=manifest.routes['/search'];
manifest.routes['/trial/original']={...manifest.routes['/search'],preview:true};manifest.routes['/trial/original/']=manifest.routes['/trial/original'];
// Existing One and Services keep their paths and get a route back to the unified home.
for(const url of ['/trial/one-55321448a0352f1ff18b','/trial/services']){
 const entry=manifest.routes[url];if(!entry)throw Error('Missing project route: '+url);
 const html=readFileSync(resolve(out,entry.file),'utf8').replace('</head>',bridgeTags+'</head>');
 writeFileSync(resolve(out,entry.file),html);for(const route of Object.values(manifest.routes))if(route.file===entry.file)route.sha256=hash(html);
}
const analytics=[...original.matchAll(/<script src="[^"]*findzia-(?:ads|analytics)\.[^"]+" defer><\/script>/g)].map(match=>match[0]).join('');
let html=readFileSync(resolve(source,'findzia-hub.html'),'utf8').replace('__ANALYTICS__',analytics);
html=html.replace(/__ASSET_(.*?)__/g,(_,name)=>{if(!assets[name])throw Error('Missing hub asset: '+name);return assets[name];});
if(/__ASSET_|__ANALYTICS__/.test(html))throw Error('Unresolved hub asset');
emit('/','index.html',html,'html');manifest.routes['/index.html']=manifest.routes['/'];manifest.routes['/home']=manifest.routes['/'];manifest.routes['/home/']=manifest.routes['/'];
const sitemapEntry=manifest.routes['/sitemap.xml'];
const sitemap=readFileSync(resolve(out,sitemapEntry.file),'utf8').replace('</urlset>','<url><loc>https://findzia.com/search</loc></url></urlset>');writeFileSync(resolve(out,sitemapEntry.file),sitemap);sitemapEntry.sha256=hash(sitemap);
const healthEntry=manifest.routes['/healthz'];const health=JSON.parse(readFileSync(resolve(out,healthEntry.file),'utf8'));health.hub='20261016.4';health.projects={original:'/search',one:'/trial/one-55321448a0352f1ff18b',space:'/space',services:'/trial/services'};const healthBody=JSON.stringify(health);writeFileSync(resolve(out,healthEntry.file),healthBody);healthEntry.sha256=hash(healthBody);
manifest.hub='20261016.4';writeFileSync(resolve(out,'release.json'),JSON.stringify(manifest,null,2)+'\n');
console.log('Findzia World published at /; Original at /search; One, Space, Services linked.');
