// Publish the first validated inventory before the optional second model pass.
// A customer opening the image freezes its piece identities. A slow review must
// never replace a piece that is being selected, searched, or saved.
export async function prepareInventory({identify,prepare,publish,refine,isCurrent=()=>true,canRefine=()=>true,onReviewError=()=>{}}){
 const initial=await prepare(await identify(),false);
 if(!isCurrent())return;
 publish(initial,false);
 if(!initial.length||!canRefine())return;
 try{
  const review=await refine(initial);
  if(!isCurrent()||!canRefine())return;
  const revised=await prepare(review,true);
  if(isCurrent()&&canRefine())publish(revised,true);
 }catch(error){onReviewError(error);}
}

// Start detection while the independent design check runs. Capture rejection
// immediately so a rejected candidate can be discarded without an unhandled task.
export async function inspectCandidate({verify,identify}){
 const inventory=Promise.resolve().then(identify).then(items=>({items}),error=>({error}));
 const check=await verify();
 return {check,inventory};
}
