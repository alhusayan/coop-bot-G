// A response may only update the room and navigation which started it.
export function createRoomContext(){
 let epoch=0;
 return {begin:()=>++epoch,capture:()=>epoch,current:token=>token===epoch};
}
export function acceptsJob(current,incoming){
 return !!incoming&&(!current||(incoming.id===current.id&&Number(incoming.revision||0)>=Number(current.revision||0)));
}
