import test from 'node:test';
import assert from 'node:assert/strict';
import {parseHTML} from 'linkedom';
import {approvedSimilar,reviewSimilarCards} from '../public/similar-review.js';

const reviewed={url:'https://store.test/table',classification_final:true,identity_review_status:'completed',alternative_visual_status:'approved',alternative_visual_policy:'156.7.3',alternative_visual_proof:'original-engine-proof',audited_media_path:'/api/media/verified/'+'a'.repeat(32),visual_axes:{category:'same',subtype:'same',material:'same',color:'same'}};
test('Similar waits for original visual proof and rejects books, different shapes and surfaces',()=>{
 assert.equal(approvedSimilar(reviewed),true);
 for(const change of [{classification_final:false,display_before_audit:true},{identity_review_status:'pending'},{alternative_visual_proof:''},{audited_media_path:null},{visual_axes:{category:'different',subtype:'different'}},{visual_axes:{...reviewed.visual_axes,shape_geometry:'different'}},{visual_axes:{...reviewed.visual_axes,material:'different'}},{visual_axes:{category:'same'}}])assert.equal(approvedSimilar({...reviewed,...change}),false);
});
test('only Similar is gated; counts update on approval and rejection without exposing previews',()=>{
 const {document}=parseHTML('<section><div data-stable-group="local"><div class="fz-card-shell" data-stable-key="local"></div></div><div data-stable-group="alternative"><span class="fz-market-count">2</span><div class="fz-card-shell" data-stable-key="https://store.test/table"></div><div class="fz-card-shell" data-stable-key="https://store.test/books"></div></div></section>');
 const root=document.querySelector('section'),group=root.querySelector('[data-stable-group="alternative"]');
 let result=reviewSimilarCards(root,[{...reviewed,classification_final:false},{...reviewed,url:'https://store.test/books',visual_axes:{category:'different'}}]);
 assert.equal(result.approved,0);assert.equal(group.dataset.spacesEmpty,'true');
 result=reviewSimilarCards(root,[reviewed,{...reviewed,url:'https://store.test/books',visual_axes:{category:'different'}}]);
 assert.equal(result.approved,1);assert.equal(result.held,1);assert.equal(group.querySelector('.fz-market-count').textContent,'1');
 assert.equal(root.querySelector('[data-stable-key="local"]').dataset.spacesVisual,undefined);
 reviewSimilarCards(root,[{...reviewed,photo_match_status:'rejected'}]);assert.equal(group.dataset.spacesEmpty,'true');
});
