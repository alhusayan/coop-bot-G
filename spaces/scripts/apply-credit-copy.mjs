import {readFileSync,writeFileSync} from 'node:fs';
const path=new URL('../public/findzia/i18n.js',import.meta.url);
const source=readFileSync(path,'utf8'),match=source.match(/ const DATA=(.+);\n \/\/ Build embeds/);
if(!match)throw Error('Missing translation catalog');
const data=JSON.parse(match[1]),copy=JSON.parse(readFileSync(new URL('credit-copy.json',import.meta.url),'utf8'));
for(const key of [...copy.keys,'Credits remaining: {count}'])if(!data.keys.includes(key)){
 data.keys.push(key);for(const language of data.languages)data.values[language].push(key);
}
for(const language of data.languages){
 const values=language==='en'?copy.keys:copy[language];
 if(values?.length!==copy.keys.length)throw Error('Incomplete credit copy: '+language);
 copy.keys.forEach((key,i)=>data.values[language][data.keys.indexOf(key)]=values[i]);
 data.values[language][data.keys.indexOf('Credits remaining: {count}')]=values[1]+': {count}';
 for(const [old,key] of Object.entries(copy.aliases)){
  data.aliases[old]=key;
  if(data.keys.includes(old))data.values[language][data.keys.indexOf(old)]=data.values[language][data.keys.indexOf(key)];
 }
}
data.version='156.7.89-spaces.6';
writeFileSync(path,source.replace(match[0],' const DATA='+JSON.stringify(data)+';\n // Build embeds'));
