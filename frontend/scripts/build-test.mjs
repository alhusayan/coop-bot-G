// Add the preserved experiment after building the unchanged original storefront.
import {execFileSync} from 'node:child_process';
import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import {resolve, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';

const base=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const dest=resolve(base,'public'), snapshot=resolve(base,'test-version');
execFileSync(process.execPath,[resolve(snapshot,'scripts/build.mjs')],{stdio:'inherit'});
const manifest=JSON.parse(readFileSync(resolve(dest,'release.json'),'utf8'));
const trial=JSON.parse(readFileSync(resolve(snapshot,'public/release.json'),'utf8'));
const config=JSON.parse(readFileSync(resolve(snapshot,'trial.json'),'utf8'));
const hashes=new Map();
for(const [url,entry] of Object.entries(trial.routes)){
  if(url.startsWith('/.well-known/') || ['/robots.txt','/sitemap.xml','/healthz'].includes(url)) continue;
  let body=readFileSync(resolve(snapshot,'public',entry.file));
  if(['html','js','css'].includes(entry.type)){
    let text=body.toString().replaceAll('/assets/','/test/assets/');
    if(entry.type==='html'){
      text=text.replace(/<script src="[^"]*findzia-(?:ads|analytics)\.[^"]+" defer><\/script>/g,'');
      text=text.replace(/<link rel="canonical"[^>]*>/g,'');
      text=text.replace('<head>','<head><meta name="robots" content="noindex, nofollow, noarchive">');
      text=text.replaceAll('href="/"','href="/test"').replaceAll('href="/policies/','href="/test/policies/');
    }
    body=Buffer.from(text);
  }
  const file='test/'+entry.file, path=resolve(dest,file);
  mkdirSync(dirname(path),{recursive:true});writeFileSync(path,body);
  const testEntry={...entry,file,sha256:createHash('sha256').update(body).digest('hex'),immutable:false,preview:true};
  manifest.routes['/test'+(url==='/'?'':url)]=testEntry;
  hashes.set(url,testEntry);
}
manifest.routes['/test/']=manifest.routes['/test'];
manifest.routes['/test/discover']=hashes.get(config.discover_path);
manifest.routes['/test/discover/']=hashes.get(config.discover_path);
// Keep the previously shared discovery trial link working on the experiment.
manifest.routes[config.discover_path]=hashes.get(config.discover_path);
manifest.routes[config.discover_path+'/']=hashes.get(config.discover_path);
const robots=resolve(dest,manifest.routes['/robots.txt'].file);
const body=Buffer.from(readFileSync(robots,'utf8').replace('Disallow: /trial/','Disallow: /trial/\nDisallow: /test'));
writeFileSync(robots,body);
manifest.routes['/robots.txt'].sha256=createHash('sha256').update(body).digest('hex');
manifest.versionScopes={original:'a3323218da88706312149391358be2196986a0d1',test:'c18f61fcb8293def593785ad0945206571ce32f9'};
writeFileSync(resolve(dest,'release.json'),JSON.stringify(manifest,null,2)+'\n');
console.log('Original homepage retained byte for byte; preserved experiment available at /test and /test/discover.');
