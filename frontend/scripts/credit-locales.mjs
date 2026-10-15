// Merge the reviewed credit copy at build time; no translation network request.
export function applyCreditCopy(data,copy){
 for(const language of data.languages){
  const values=language==='en'?copy.keys:copy[language];
  if(!values||values.length!==copy.keys.length)throw Error('Incomplete credit copy: '+language);
  copy.keys.forEach((key,i)=>data.catalog[language][key]=values[i]);
  data.catalog[language]['Credits remaining: {count}']=data.catalog[language]['Credits remaining']+': {count}';
  for(const [old,key] of Object.entries(copy.aliases))data.catalog[language][old]=data.catalog[language][key];
 }
 Object.assign(data.aliases,copy.aliases);return data;
}
