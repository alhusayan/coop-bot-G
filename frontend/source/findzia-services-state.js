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

// Design-only trial credits cannot fund a service search.
export function serviceSearchCredits(status){
 if(!status)return null;
 return status.credit_unit==='flexible'
  ?(status.flexible_remaining||0)+(status.free_searches||0)*2
  :status.remaining;
}

export function serviceResultsPage(items,sort='relevance',requestedPage=0){
 const ordered=[...items];
 if(sort==='rating')ordered.sort((a,b)=>(b.rating||0)-(a.rating||0)||(b.reviews||0)-(a.reviews||0));
 const pages=Math.max(1,Math.ceil(ordered.length/4));
 const page=Math.min(pages-1,Math.max(0,Math.trunc(Number(requestedPage)||0)));
 return {items:ordered.slice(page*4,page*4+4),page,pages,total:ordered.length};
}

// Click-to-chat is offered for published international numbers; registration is not asserted.
export function serviceWhatsApp(tel){
 const number=String(tel||'').replace(/^tel:/,'');
 return /^\+[1-9]\d{6,14}$/.test(number)?'https://wa.me/'+number.slice(1):'';
}
export function serviceLocation(data){
 const country=String(data?.countryCode||'').toUpperCase();
 if(!serviceCountries.includes(country))return null;
 const parts=[data.locality,data.city].filter(v=>typeof v==='string'&&v.trim().length>1).map(v=>v.trim());
 const area=[...new Set(parts)].join(', ').slice(0,120);
 return area?{area,country}:null;
}
