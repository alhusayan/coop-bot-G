import { readFileSync, writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const base = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const src = resolve(base, 'source'), dest = resolve(base, 'public');
const version = '156.7.84', api = 'https://api.findzia.com';
// Preserve the live section scope to avoid unnecessary DOM/storage changes.
const section = 'template--19963721449543__findzia_home_h4wBLq';
// Both original PSP files are shipped. Runtime selects one using Railway's
// FINDZIA_PAYMENT_PROVIDER; switching does not edit or rebuild certificate bytes.
const applePayHashes = {
  paddle: '2de7b483319c713bf649352f7f158f1fedbda92f546bebfe576ae0a2d2c526c6',
  myfatoorah: 'c15558d3e155e2031ef39b32775050c283b545d8575643181af3c3b9f03d46a3',
};
const expected = applePayHashes.paddle;
const hash = b => createHash('sha256').update(b).digest('hex');
const read = p => readFileSync(resolve(src, p));
const sourceReleases={home:read('findzia-home.liquid').toString().match(/FINDZIA_HOME_RELEASE=([0-9.]+)/)?.[1],shell:read('findzia-shell.js').toString().match(/FINDZIA_SHELL_RELEASE=([0-9.]+)/)?.[1]};
sourceReleases.boot=read('findzia-boot.js').toString().match(/FINDZIA_BOOT_RELEASE=([0-9.]+)/)?.[1];
sourceReleases.billing=read('findzia-billing.js').toString().match(/FINDZIA_BILLING_RELEASE=([0-9.]+)/)?.[1];
sourceReleases.subscriptions=read('findzia-subscriptions.js').toString().match(/FINDZIA_SUBSCRIPTIONS_RELEASE=([0-9.]+)/)?.[1];
sourceReleases.guide=read('findzia-filters.js').toString().match(/FINDZIA_GUIDE_RELEASE=([0-9.]+)/)?.[1];
sourceReleases.account=read('findzia-account.js').toString().match(/FINDZIA_ACCOUNT_RELEASE=([0-9.]+)/)?.[1];
sourceReleases.motion=read('findzia-motion.js').toString().match(/FINDZIA_MOTION_RELEASE=([0-9.]+)/)?.[1];
sourceReleases.motionCSS=read('findzia-motion.css').toString().match(/FINDZIA_MOTION_CSS_RELEASE=([0-9.]+)/)?.[1];
sourceReleases.support=read('findzia-support.js').toString().match(/FINDZIA_SUPPORT_RELEASE=([0-9.]+)/)?.[1];
sourceReleases.focus=read('findzia-focus.js').toString().match(/FINDZIA_FOCUS_RELEASE=([0-9.]+)/)?.[1];
if(JSON.parse(read('findzia-support.json').toString('utf8')).version!=='156.7.62')throw Error('Support knowledge release mismatch.');
const packageVersion=JSON.parse(readFileSync(resolve(base,'package.json'),'utf8')).version;
if(packageVersion!==version)throw Error('Release mismatch: replace frontend/package.json and frontend/scripts/build.mjs together.');
if(sourceReleases.boot!=='156.7.43')throw Error('Release mismatch: expected frontend/source/findzia-boot.js version 156.7.43.');
for(const [key,file] of [['support','findzia-support.js'],['focus','findzia-focus.js'],['home','findzia-home.liquid'],['shell','findzia-shell.js'],['billing','findzia-billing.js'],['subscriptions','findzia-subscriptions.js'],['guide','findzia-filters.js'],['account','findzia-account.js'],['motion','findzia-motion.js'],['motionCSS','findzia-motion.css']]){
  const expectedVersion=key==='home'?version:key==='billing'?'156.7.83':['account','motion','support','focus'].includes(key)?'156.7.62':key==='subscriptions'?'156.7.60':key==='motionCSS'?'156.7.53':key==='guide'?'156.7.48':'156.7.43';
  if(sourceReleases[key]!==expectedVersion)throw Error('Release mismatch: replace frontend/source/'+file+' with version '+expectedVersion+'.');
}
const routes = {};
rmSync(dest, {recursive:true, force:true}); mkdirSync(dest, {recursive:true});
function emit(url, file, bytes, type, immutable=false) {
  bytes = Buffer.isBuffer(bytes) ? bytes : Buffer.from(bytes);
  const path = resolve(dest,file); mkdirSync(dirname(path),{recursive:true}); writeFileSync(path,bytes);
  routes[url] = {file,sha256:hash(bytes),type,immutable}; return url;
}
const assets = new Map();
for (const name of ['findzia-support.js','findzia-focus.js','findzia-account.js','findzia-subscriptions.js','findzia-billing.js','findzia-filters.js','findzia-i18n.js','findzia-shell.js','findzia-product-details.css','findzia-migration.js','findzia-standalone.css','findzia-motion.js','findzia-motion.css']) {
  const bytes=name==='findzia-support.js'?Buffer.from(read(name).toString().replace('/* SUPPORT_KNOWLEDGE */ null',JSON.stringify(JSON.parse(read('findzia-support.json').toString('utf8'))))):read(name), ext=name.split('.').at(-1), file='assets/'+name.replace('.'+ext,'.'+hash(bytes).slice(0,16)+'.'+ext);
  assets.set(name,emit('/'+file,file,bytes,ext,true));
}
const applePayFiles = {};
for (const [provider, sha256] of Object.entries(applePayHashes)) {
  const bytes = read('apple-pay/'+provider);
  if (bytes.length!==9094 || hash(bytes)!==sha256) throw Error('Apple Pay original file mismatch: '+provider);
  const file = 'apple-pay/'+provider;
  mkdirSync(resolve(dest,'apple-pay'),{recursive:true});
  writeFileSync(resolve(dest,file),bytes);
  // These private build assets are not HTTP routes. Only the selected file
  // is exposed at the official well-known path by server.mjs.
  applePayFiles[provider] = {file,sha256};
}
const association=read('apple-pay/paddle');
emit('/.well-known/apple-developer-merchantid-domain-association','.well-known/apple-developer-merchantid-domain-association',association,'txt');

let home=read('findzia-home.liquid').toString('utf8');
home=home.replace(/{% comment %}[\s\S]*?{% endcomment %}/g,'').replace(/{% schema %}[\s\S]*?{% endschema %}/g,'');
const values = new Map([
  ['{{ section.id }}',section],
  ["{{ section.settings.api_base_url | default: 'https://coop-bot-g-production.up.railway.app' | json }}",JSON.stringify(api)],
  ['{{ localization.country.iso_code | json }}','""'],
  ['{{ localization.country.name | json }}','""'],
  ["{{ 'now' | date: '%Y' }}",'2026'],
  ["{{ shop.terms_of_service.url | default: '/policies/terms-of-service' | escape }}",'/policies/terms-of-service'],
  ["{{ shop.privacy_policy.url | default: '/policies/privacy-policy' | escape }}",'/policies/privacy-policy'],
  ["{{ shop.refund_policy.url | default: '/policies/refund-policy' | escape }}",'/policies/refund-policy'],
]);
for (const [token,value] of values) home=home.split(token).join(value);
home=home.replace(/{{ '([^']+)' \| asset_url }}/g,(_,name)=>{
  if(!assets.has(name))throw Error('Unknown asset '+name); return assets.get(name);
});
if (/\{[{%]/.test(home)) throw Error('Unresolved Liquid template expression');

const baseline=`*,*::before,*::after{box-sizing:border-box}html{background:#f4f3f1;color-scheme:light;font-size:16px;-webkit-text-size-adjust:100%}body{margin:0;background:#f4f3f1;color:#24322c;font:16px/1.5 Arial,sans-serif}button,input,select,textarea{font:inherit}button{cursor:pointer}img,svg{vertical-align:middle}button:disabled{cursor:default}[hidden]{display:none!important}html[data-findzia-theme="dark"],html[data-findzia-theme="dark"] body{background:#111917;color:#eef2ed;color-scheme:dark}a{color:inherit}dialog{color:inherit}body>main{min-width:0}button:focus-visible,a:focus-visible{outline:2px solid #b97944;outline-offset:3px}`;
const legalCSS=`.legal{max-width:820px;margin:auto;padding:32px 24px 64px;line-height:1.8}.legal header{display:flex;justify-content:space-between;align-items:center;gap:24px;margin-bottom:40px}.legal .brand{font-family:Georgia,serif;font-size:36px;text-decoration:none;letter-spacing:-1px}.legal article{overflow-wrap:anywhere}.legal h1{font-size:30px;line-height:1.25}.legal h2,.legal h3{line-height:1.4;margin-top:32px}.legal article a{color:#8b4f25}.legal footer{margin-top:40px;border-top:1px solid #dce1da;padding-top:20px}.legal footer nav{display:flex;flex-wrap:wrap;gap:16px;font-size:14px}html[data-findzia-theme="dark"] .legal article a{color:#f5c291}html[data-findzia-theme="dark"] .legal footer{border-color:#3c4a41}`;
function page(body,title,canonical,extraStyle='') {
  return `<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="description" content="Find products with a photo or a few words. Compare local and global stores with Findzia."><meta name="theme-color" content="#101b17"><script data-findzia-boot>${read('findzia-boot.js').toString()}</script><title>${title}</title><link rel="canonical" href="https://findzia.com${canonical}"><link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="preconnect" href="https://api.findzia.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><style>${baseline}${extraStyle}</style><link rel="stylesheet" href="${assets.get('findzia-motion.css')}"><script src="${assets.get('findzia-motion.js')}" defer></script></head><body>${body}</body></html>\n`;
}
// The wrapper IDs match the original scoped CSS; no Shopify runtime is loaded.
emit('/','index.html',page(`<link rel="stylesheet" href="${assets.get('findzia-standalone.css')}"><script src="${assets.get('findzia-migration.js')}"></script><main id="MainContent"><div class="shopify-section section-findzia-home" id="shopify-section-${section}">${home}</div></main>`,'Findzia — Find your product instantly','/'),'html');
// Keep known landing links working; unknown routes remain a real 404.
routes['/index.html']=routes['/']; routes['/pages/findzia']=routes['/'];
const policies=[['terms-of-service','Terms of Service'],['privacy-policy','Privacy Policy'],['refund-policy','Refund Policy']];
const nav=policies.map(([slug,title])=>`<a href="/policies/${slug}">${title}</a>`).join('');
for (const [slug,title] of policies) {
  const body=read('policies/'+slug+'.html').toString('utf8');
  const html=page(`<main class="legal"><header><a class="brand" href="/">Findzia</a><a href="/">Back to search</a></header><article>${body}</article><footer><nav>${nav}</nav></footer></main>`,title+' — Findzia','/policies/'+slug,legalCSS);
  emit('/policies/'+slug,'policies/'+slug+'.html',html,'html');
  routes['/policies/'+slug+'/']=routes['/policies/'+slug];
}
emit('/404.html','404.html',page('<main class="legal"><h1>Page not found</h1><p><a href="/">Back to Findzia</a></p></main>','Page not found — Findzia','/',legalCSS),'html');
emit('/favicon.svg','favicon.svg','<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="15" fill="#20352a"/><text x="14" y="48" fill="#f7f7f3" font-family="Georgia,serif" font-size="49">F</text><circle cx="49" cy="16" r="4" fill="#ef9d57"/></svg>','svg');
emit('/robots.txt','robots.txt','User-agent: *\nAllow: /\nDisallow: /healthz\nSitemap: https://findzia.com/sitemap.xml\n','txt');
emit('/sitemap.xml','sitemap.xml','<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+['/',...policies.map(([s])=>'/policies/'+s)].map(p=>'<url><loc>https://findzia.com'+p+'</loc></url>').join('')+'</urlset>','xml');
emit('/healthz','health.json',JSON.stringify({ok:true,service:'findzia-frontend',version,sourceReleases}),'json');
writeFileSync(resolve(dest,'release.json'),JSON.stringify({version,api,section,apple_pay_file_sha256:expected,apple_pay_files:applePayFiles,routes},null,2)+'\n');
console.log(`Built Findzia ${version}: ${Object.keys(routes).length} routes, both original Apple Pay files verified.`);

