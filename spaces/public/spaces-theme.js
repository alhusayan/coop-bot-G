// Run in the head, before the first paint. The room and its result layer share
// one appearance choice; Findzia still resolves automatic daylight mode.
(() => {
  const html=document.documentElement;
  function apply(){
    const root=document.querySelector('#findzia-home-spaces');
    const appearance=window.FindziaAppearance;
    if(!appearance)return;
    const state=appearance.resolve();
    appearance.apply(root,state);
    document.dispatchEvent(new CustomEvent('spaces:theme',{detail:state}));
  }
  window.SpacesTheme={apply};
  apply();
  document.addEventListener('DOMContentLoaded',apply,{once:true});
  window.addEventListener('pageshow',apply);
  window.addEventListener('storage',event=>{if(event.key==='findzia-appearance-v1')apply();});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)apply();});
  // Automatic mode follows the same daylight calculation as Findzia.
  setInterval(()=>{if(!document.hidden)apply();},60000);
})();
