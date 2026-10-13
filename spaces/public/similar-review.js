import {productKey} from './design-picks.js';

// Consume the original engine's completed image comparison. Do not infer
// similarity from names, search rank, provider confidence or SKU identity.
export function approvedSimilar(row){
 if(!row||row.hidden||row.photo_match_status==='rejected'||row.alternative_visual_status!=='approved')return false;
 if(row.classification_final!==true||row.identity_review_status!=='completed')return false;
 if(row.alternative_visual_policy!=='156.7.3'||!row.alternative_visual_proof)return false;
 if(!row.audited_media_path&&!row.audited_image)return false;
 const axes=row.visual_axes||{};
 if(axes.category!=='same')return false;
 const shape=['subtype','function','product_role','form_factor','silhouette','shape_geometry','structure','configuration','support_base'];
 if([...shape,'material','texture','pattern','color'].some(key=>axes[key]==='different'))return false;
 return ['subtype','form_factor','silhouette','shape_geometry','structure','configuration','support_base'].some(key=>axes[key]==='same');
}

export function reviewSimilarCards(root,rows){
 const byKey=new Map(rows.map(row=>[String(row.provider_passthrough&&row.result_id||row.url||''),row]));
 const byURL=new Map(rows.map(row=>[productKey(row.url),row]));
 let approved=0,held=0;
 for(const group of root.querySelectorAll('[data-stable-group="alternative"],[data-cinema-group="alternative"]')){
  let visible=0;
  for(const card of group.querySelectorAll('.fz-card-shell')){
   const key=card.dataset.stableKey||card.querySelector('[data-image-key]')?.getAttribute('data-image-key');
   const row=byKey.get(key)||byURL.get(productKey(card.querySelector('a.fz-tile')?.href));
   const ok=approvedSimilar(row);card.dataset.spacesVisual=ok?'approved':'held';
   if(ok){visible++;approved++;}else held++;
  }
  group.dataset.spacesEmpty=String(visible===0);
  const count=group.querySelector('.fz-market-count');if(count&&count.textContent!==String(visible))count.textContent=String(visible);
 }
 return {approved,held};
}
