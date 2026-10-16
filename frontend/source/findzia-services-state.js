// Shared, explicit market choices win over approximate browser location.
export const serviceCountries=['KW','SA','AE','QA','BH','OM','GB','US','CA','AU','DE','FR','IT','ES','NL','TR','EG','JO','IN','JP','CN','KR','BR','SG','MY','ID'];
const zones={
 'Asia/Kuwait':'KW','Asia/Riyadh':'SA','Asia/Dubai':'AE','Asia/Qatar':'QA','Asia/Bahrain':'BH','Asia/Muscat':'OM',
 'Europe/London':'GB','Europe/Berlin':'DE','Europe/Paris':'FR','Europe/Rome':'IT','Europe/Madrid':'ES','Europe/Amsterdam':'NL','Europe/Istanbul':'TR',
 'Africa/Cairo':'EG','Asia/Amman':'JO','Asia/Kolkata':'IN','Asia/Calcutta':'IN','Asia/Tokyo':'JP','Asia/Shanghai':'CN','Asia/Seoul':'KR','Asia/Singapore':'SG','Asia/Kuala_Lumpur':'MY','Asia/Jakarta':'ID',
 'America/Toronto':'CA','America/Vancouver':'CA','America/New_York':'US','America/Chicago':'US','America/Los_Angeles':'US','America/Denver':'US','America/Sao_Paulo':'BR',
 'Australia/Sydney':'AU','Australia/Melbourne':'AU','Australia/Perth':'AU','Australia/Brisbane':'AU'
};
export function initialServiceCountry(read,{zone='',languages=[]}={}){
 for(const key of ['findzia-services-country-v1','findzia-market-country-v1']){
  const value=String(read(key)||'').toUpperCase();if(serviceCountries.includes(value))return value;
 }
 if(zones[zone])return zones[zone];
 for(const locale of languages){const region=String(locale).match(/[-_]([a-z]{2})(?:$|[-_])/i)?.[1]?.toUpperCase();if(serviceCountries.includes(region))return region;}
 return 'US';
}
