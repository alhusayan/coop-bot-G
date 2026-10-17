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

export function serviceResults(items,sort='relevance'){
 const ordered=[...items];
 if(sort==='rating')ordered.sort((a,b)=>(b.rating||0)-(a.rating||0)||(b.reviews||0)-(a.reviews||0));
 return {items:ordered,total:ordered.length};
}

// The server supplies an explicit link found on the business's published website.
export function serviceWhatsApp(row){
 if(!row?.whatsapp_source||row.whatsapp_source!==row.website||!/^https?:\/\//.test(row.whatsapp_source))return '';
 return /^https:\/\/wa\.me\/[1-9]\d{6,14}$/.test(row.whatsapp||'')?row.whatsapp:'';
}
export function serviceLocation(data){
 const country=String(data?.countryCode||'').toUpperCase();
 if(!serviceCountries.includes(country))return null;
 const parts=[data.locality,data.city].filter(v=>typeof v==='string'&&v.trim().length>1).map(v=>v.trim());
 const area=[...new Set(parts)].join(', ').slice(0,120);
 return area?{area,country}:null;
}

// A saved area is a preference, not a promise of continuous GPS access.
export function savedServiceArea(raw){
 try{
  const value=JSON.parse(raw),country=String(value?.country||'').toUpperCase();
  const area=typeof value?.area==='string'?value.area.trim().slice(0,120):'';
  return serviceCountries.includes(country)&&area.length>=2?{area,country}:null;
 }catch{return null;}
}

// Conservative local spelling assistance. Unlisted or ambiguous places go to
// the geographic search provider unchanged; the selected country never changes.
const areaNames={
 KW:'Kuwait City|مدينة الكويت|Kuwait;Salmiya|السالمية;Hawally|حولي|Hawalli;Farwaniya|الفروانية|Farwaniyah;Jahra|الجهراء|Jahrah;Ahmadi|الأحمدي;Fahaheel|الفحيحيل;Mangaf|المنقف;Mahboula|المهبولة;Fintas|الفنطاس;Abu Halifa|أبو حليفة;Sabah Al Salem|صباح السالم;Mishref|مشرف;Salwa|سلوى;Rumaithiya|الرميثية;Jabriya|الجابرية;Bayan|بيان;Shuwaikh|الشويخ;Shamiya|الشامية;Kaifan|كيفان;Rawda|الروضة;Adailiya|العديلية;Qadsiya|القادسية;Qurtuba|قرطبة;Yarmouk|اليرموك;Khaldiya|الخالدية;Surra|السرة;Shuhada|الشهداء;Zahra|الزهراء;Salam|السلام;Hateen|حطين;Siddiq|الصديق;Sabahiya|الصباحية;Riqqa|الرقة;Riqai|الرقعي;Ardiya|العارضية;Khaitan|خيطان;Jleeb Al Shuyoukh|جليب الشيوخ;Abdullah Al Salem|عبدالله السالم',
 SA:'Riyadh|الرياض;Jeddah|جدة|Jidda;Dammam|الدمام;Khobar|الخبر;Dhahran|الظهران;Makkah|مكة|Mecca;Madinah|المدينة المنورة|Medina;Taif|الطائف;Abha|أبها;Tabuk|تبوك;Buraidah|بريدة;Hail|حائل',
 AE:'Dubai|دبي;Abu Dhabi|أبو ظبي|AbuDhabi;Sharjah|الشارقة;Ajman|عجمان;Ras Al Khaimah|رأس الخيمة;Fujairah|الفجيرة;Al Ain|العين;Umm Al Quwain|أم القيوين',
 QA:'Doha|الدوحة;Al Wakrah|الوكرة;Al Khor|الخور;Lusail|لوسيل;Al Rayyan|الريان',
 BH:'Manama|المنامة;Muharraq|المحرق;Riffa|الرفاع;Hamad Town|مدينة حمد;Isa Town|مدينة عيسى',
 OM:'Muscat|مسقط;Salalah|صلالة;Sohar|صحار;Nizwa|نزوى;Seeb|السيب',
 GB:'London|لندن;Manchester|مانشستر;Birmingham|برمنغهام;Liverpool|ليفربول;Edinburgh|إدنبرة',
 US:'New York|نيويورك;Los Angeles|لوس أنجلوس;Chicago|شيكاغو;Houston|هيوستن;San Francisco|سان فرانسيسكو',
 CA:'Toronto|تورونتو;Vancouver|فانكوفر;Montreal|مونتريال;Ottawa|أوتاوا',
 AU:'Sydney|سيدني;Melbourne|ملبورن;Brisbane|بريزبن;Perth|بيرث',
 DE:'Berlin|برلين;Munich|ميونخ|München;Hamburg|هامبورغ;Frankfurt|فرانكفورت',
 FR:'Paris|باريس;Lyon|ليون;Marseille|مارسيليا',
 IT:'Rome|روما|Roma;Milan|ميلانو|Milano;Naples|نابولي|Napoli',
 ES:'Madrid|مدريد;Barcelona|برشلونة;Valencia|فالنسيا',
 NL:'Amsterdam|أمستردام;Rotterdam|روتردام',
 TR:'Istanbul|إسطنبول;Ankara|أنقرة;Antalya|أنطاليا',
 EG:'Cairo|القاهرة;Alexandria|الإسكندرية;Giza|الجيزة',
 JO:'Amman|عمان;Irbid|إربد;Aqaba|العقبة;Zarqa|الزرقاء',
 IN:'Mumbai|مومباي;Delhi|دلهي;Bengaluru|بنغالور|Bangalore;Hyderabad|حيدر أباد',
 JP:'Tokyo|طوكيو;Osaka|أوساكا;Kyoto|كيوتو',
 CN:'Beijing|بكين;Shanghai|شنغهاي;Guangzhou|غوانزو',
 KR:'Seoul|سيول;Busan|بوسان',
 BR:'São Paulo|ساو باولو|Sao Paulo;Rio de Janeiro|ريو دي جانيرو',
 SG:'Singapore|سنغافورة',
 MY:'Kuala Lumpur|كوالالمبور;Johor Bahru|جوهور بهرو',
 ID:'Jakarta|جاكرتا;Surabaya|سورابايا'
};
const areaKey=value=>value.normalize('NFKD').toLocaleLowerCase().replace(/[\u0300-\u036f\u064b-\u065f\u0670\u0640]/g,'').replace(/[أإآٱ]/g,'ا').replace(/ة/g,'ه').replace(/ى/g,'ي').replace(/^(?:ال|al[ -]+)/,'').replace(/[\s’'._-]/g,'');
function spellingDistance(a,b){
 const d=Array.from({length:a.length+1},(_,i)=>Array.from({length:b.length+1},(_,j)=>i===0?j:j===0?i:0));
 for(let i=1;i<=a.length;i++)for(let j=1;j<=b.length;j++){
  d[i][j]=Math.min(d[i-1][j]+1,d[i][j-1]+1,d[i-1][j-1]+(a[i-1]===b[j-1]?0:1));
  if(i>1&&j>1&&a[i-1]===b[j-2]&&a[i-2]===b[j-1])d[i][j]=Math.min(d[i][j],d[i-2][j-2]+1);
 }
 return d[a.length][b.length];
}
export function normalizeServiceArea(value,country){
 const area=String(value||'').trim().replace(/\s+/g,' ').slice(0,120),key=areaKey(area);
 if(!key||!areaNames[country]||/[,،\d]/.test(area))return area;
 const choices=areaNames[country].split(';').map(row=>{
  const [en,ar,aliases='']=row.split('|'),names=[en,ar,...aliases.split(',')].filter(Boolean);
  return {label:/[\u0600-\u06ff]/.test(area)?ar:en,distance:Math.min(...names.map(name=>spellingDistance(key,areaKey(name))))};
 }).sort((a,b)=>a.distance-b.distance);
 const best=choices[0],limit=key.length>=9?2:key.length>=4?1:0;
 return best.distance<=limit&&(choices[1]?.distance??Infinity)>best.distance?best.label:area;
}
