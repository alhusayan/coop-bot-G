const limit=(value,fallback)=>Number.isSafeInteger(Number(value))&&Number(value)>0?Math.min(1000,Number(value)):fallback;
const day=now=>new Date(now).toISOString().slice(0,10);
export function previewLimits(env=process.env){
 return {rooms:limit(env.SPACES_DAILY_ROOMS_PER_BROWSER,30),redesign:limit(env.SPACES_DAILY_REDESIGNS_PER_BROWSER,30),total:limit(env.SPACES_DAILY_ROOMS,100)};
}
export function previewUsage(quota,owner,{env=process.env,now=Date.now()}={}){
 const limits=previewLimits(env),prefix=day(now)+':'+owner+':';
 return {dailyRooms:limits.rooms,roomsRemaining:Math.max(0,limits.rooms-(quota[prefix+'rooms']||0)),dailyRedesigns:limits.redesign,redesignsRemaining:Math.max(0,limits.redesign-(quota[prefix+'redesign']||0))};
}
export function reservePreview(quota,owner,kind,{env=process.env,now=Date.now()}={}){
 if(!['rooms','redesign'].includes(kind))throw Error('INVALID_QUOTA_KIND');
 const limits=previewLimits(env),prefix=day(now)+':',ownerKey=prefix+owner+':'+kind,totalKey=prefix+'all:rooms';
 // Check both allowances before changing either counter. A rejected request costs no credit.
 if((quota[ownerKey]||0)>=limits[kind]||(quota[totalKey]||0)>=limits.total)throw Object.assign(Error('TRIAL_LIMIT'),{status:429});
 quota[ownerKey]=(quota[ownerKey]||0)+1;quota[totalKey]=(quota[totalKey]||0)+1;
 return {ownerKey,totalKey,settled:false};
}
export function settlePreview(quota,reservation,{success=false,started=true}={}){
 if(!reservation||reservation.settled)return;
 if(!success&&Object.hasOwn(quota,reservation.ownerKey))quota[reservation.ownerKey]=Math.max(0,quota[reservation.ownerKey]-1);
 // Provider work still counts towards the service-wide cost ceiling even when it fails.
 if(!started&&Object.hasOwn(quota,reservation.totalKey))quota[reservation.totalKey]=Math.max(0,quota[reservation.totalKey]-1);
 reservation.settled=true;
}
