// Markets already supported by Findzia's original search engine.
const rows=[
 ['KW','الكويت','Kuwait','KWD','د.ك','🇰🇼','ar'],
 ['SA','السعودية','Saudi Arabia','SAR','ر.س','🇸🇦','ar'],['AE','الإمارات','United Arab Emirates','AED','د.إ','🇦🇪','ar'],
 ['QA','قطر','Qatar','QAR','ر.ق','🇶🇦','ar'],['BH','البحرين','Bahrain','BHD','د.ب','🇧🇭','ar'],['OM','عُمان','Oman','OMR','ر.ع','🇴🇲','ar'],
 ['US','United States','United States','USD','$','🇺🇸','en'],['CN','中国','China','CNY','¥','🇨🇳','zh'],
 ['GB','United Kingdom','United Kingdom','GBP','£','🇬🇧','en'],['DE','Deutschland','Germany','EUR','€','🇩🇪','de'],
 ['FR','France','France','EUR','€','🇫🇷','fr'],['IT','Italia','Italy','EUR','€','🇮🇹','it'],
 ['ES','España','Spain','EUR','€','🇪🇸','es'],['NL','Nederland','Netherlands','EUR','€','🇳🇱','nl'],
 ['CA','Canada','Canada','CAD','$','🇨🇦','en'],['AU','Australia','Australia','AUD','$','🇦🇺','en'],
 ['JP','日本','Japan','JPY','¥','🇯🇵','ja'],['KR','대한민국','South Korea','KRW','₩','🇰🇷','ko'],
 ['IN','भारत','India','INR','₹','🇮🇳','hi'],['TR','Türkiye','Türkiye','TRY','₺','🇹🇷','tr'],
 ['SG','Singapore','Singapore','SGD','$','🇸🇬','en'],['EG','مصر','Egypt','EGP','ج.م','🇪🇬','ar'],
 ['BR','Brasil','Brazil','BRL','R$','🇧🇷','pt'],['MX','México','Mexico','MXN','$','🇲🇽','es']
];
export function supportedMarket(code,fallback='US'){return rows.some(row=>row[0]===code)?code:fallback;}
export function savedMarket(read=key=>localStorage.getItem(key)){try{return supportedMarket(String(read('findzia-market-country-v1')||'').toUpperCase(),'');}catch{return '';}}
export const MARKETS=Object.fromEntries(rows.map(([code,name,en,currency,symbol,flag,lang])=>[code,{name,en,currency,symbol,flag,lang}]));
export function orderedMarkets(markets){return [...new Set([...rows.map(row=>row[0]),...Object.keys(markets)])].filter(code=>markets[code]).map(code=>[code,markets[code]]);}
export function browserMarket({timeZone='',languages=[]}={}){
 const zones={'Asia/Kuwait':'KW','Asia/Riyadh':'SA','Asia/Dubai':'AE','Asia/Qatar':'QA','Asia/Bahrain':'BH','Asia/Muscat':'OM','Asia/Tokyo':'JP','Asia/Shanghai':'CN','Asia/Hong_Kong':'CN','Asia/Seoul':'KR','Asia/Kolkata':'IN','Asia/Calcutta':'IN','Asia/Singapore':'SG','Africa/Cairo':'EG','Europe/London':'GB','Europe/Berlin':'DE','Europe/Paris':'FR','Europe/Rome':'IT','Europe/Madrid':'ES','Europe/Amsterdam':'NL','Europe/Istanbul':'TR','America/Toronto':'CA','America/Vancouver':'CA','America/Mexico_City':'MX','America/Sao_Paulo':'BR','Australia/Sydney':'AU','Australia/Melbourne':'AU','Australia/Perth':'AU','America/New_York':'US','America/Los_Angeles':'US','America/Chicago':'US','America/Denver':'US'};
 if(zones[timeZone])return supportedMarket(zones[timeZone]);
 for(const language of languages){const region=String(language).match(/[-_]([A-Z]{2})(?:$|[-_])/i)?.[1]?.toUpperCase();if(region&&supportedMarket(region,''))return supportedMarket(region);}
 return 'US';
}
export async function detectMarket({fetcher=fetch,fallback='US',timeout=3200}={}){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),timeout);
 try{const response=await fetcher('https://api.findzia.com/api/geo',{cache:'no-store',headers:{Accept:'application/json'},signal:controller.signal});if(!response.ok)return fallback;const data=await response.json(),code=String(data.country||data.country_code||'').toUpperCase();return data.source!=='default'?supportedMarket(code,fallback):fallback;}
 catch{return fallback;}finally{clearTimeout(timer);}
}
export function marketLanguage(market,read=()=>null){return read('spaces-language-choice-'+market+'-v1')||MARKETS[market]?.lang||'en';}
