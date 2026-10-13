export const SEARCH_BUDGET_MS=23000;
export function searchBudget(onExpire,{now=Date.now,setTimer=setTimeout,clearTimer=clearTimeout}={}){
 const started=now(),controller=new AbortController();let active=true;
 const budget={signal:controller.signal,started,expired:false,
  get active(){return active;},
  get remaining(){return Math.max(0,SEARCH_BUDGET_MS-(now()-started));},
  finish(){if(!active)return;active=false;clearTimer(timer);},
  cancel(){budget.finish();controller.abort();}
 };
 const timer=setTimer(()=>{if(!active)return;active=false;budget.expired=true;controller.abort();onExpire(budget);},SEARCH_BUDGET_MS);
 return budget;
}
