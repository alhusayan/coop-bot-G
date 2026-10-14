// Presentation only: keep the original offer and merchant evidence intact.
const names={color:'Colour',material:'Material',dimensions:'Dimensions',size:'Size',width:'Width',depth:'Depth',height:'Height',length:'Length',diameter:'Diameter',finish:'Finish',brand:'Brand',shape:'Shape',pattern:'Pattern',configuration:'Configuration',care:'Care',assembly:'Assembly',origin:'Country of origin',weight:'Weight',capacity:'Capacity'};
const norm=value=>String(value||'').normalize('NFKC').toLocaleLowerCase().replace(/[\u064b-\u065f\u0670]/g,'').replace(/[٠-٩]/g,c=>String(c.charCodeAt(0)-1632)).replace(/[^\p{L}\p{N}]/gu,'');
const axes=['width','depth','height','length','diameter'];
const measureKinds=new Set(['dimensions','size',...axes]);
function kindOf(fact){return fact.kind||Object.keys(names).find(kind=>names[kind]===fact.label)||'';}
function genericLabel(fact,translate){
 const label=norm(String(fact.label||'').replace(/\([^)]*\)/g,'')),kind=kindOf(fact);
 return [kind,names[kind],translate(names[kind]||''),kind==='color'?'Color':''].filter(Boolean).some(value=>norm(value)===label);
}
export function uniqueFacts(facts=[],translate=value=>value){
 const seen=new Set();
 return facts.filter(f=>f?.value).map(f=>({...f,kind:kindOf(f)})).filter(f=>{
  const label=f.kind==='color'||genericLabel(f,translate)?f.kind:norm(f.label);
  const key=[f.kind,label,norm(f.value)].join(':');if(seen.has(key))return false;seen.add(key);return true;
 });
}
// Parts of a product (seat/armrest/frame/filling) belong in the full sheet.
// Only explicit overall axes can be combined; their labels and units survive.
function overall(fact,translate){return genericLabel(fact,translate)||/^(?:overall|assembled|total)\s+(?:width|depth|height|length|diameter)$/i.test(fact.label||'');}
function primaryMaterial(facts,translate){
 const rank=f=>genericLabel(f,translate)||/^(?:main|primary|principal|principal[e]?|haupt|أساسية|رئيسية)/iu.test(f.label)||/الخامة الرئيسية|المادة الرئيسية/iu.test(f.label)?0:/upholster|cover|tissu|bezug|تنجيد|قماش/iu.test(f.label)?1:3;
 return facts.map((f,i)=>({f,i,rank:rank(f)})).sort((a,b)=>a.rank-b.rank||a.i-b.i)[0]?.f;
}
export function summarizeFacts(input=[],translate=value=>value){
 const facts=uniqueFacts(input,translate),summary=[];
 const color=facts.find(f=>f.kind==='color');if(color)summary.push({...color,label:translate('Colour')});
 const material=primaryMaterial(facts.filter(f=>f.kind==='material'),translate);if(material)summary.push({...material,label:translate('Material')});
 const combined=facts.filter(f=>f.kind==='dimensions'||f.kind==='size');
 const measurements=axes.map(kind=>facts.find(f=>f.kind===kind&&overall(f,translate))).filter(Boolean).slice(0,3);
 const dimensions=combined.find(f=>genericLabel(f,translate)||/overall|assembled|إجمال|كلي/iu.test(f.label))||(!measurements.length?combined[0]:null);
 if(dimensions){
  // Keep the merchant's written axis order; never assign unnamed numbers to axes.
  summary.push({...dimensions,label:combined.length>1&&!genericLabel(dimensions,translate)?translate(dimensions.label):translate('Dimensions')});
 }else{
  if(measurements.length){
   const parts=measurements.map(f=>String(f.value).trim().match(/^([\d٠-٩۰-۹]+(?:[.,][\d٠-٩۰-۹]+)?)\s*([\p{L}″"']+)$/u));
   const sharedUnit=parts.every(Boolean)&&parts.every(p=>norm(p[2])===norm(parts[0][2]));
   summary.push({kind:'dimensions',label:measurements.map(f=>translate(names[f.kind])).join(' × '),value:sharedUnit?parts.map(p=>p[1]).join(' × ')+' '+parts[0][2]:measurements.map(f=>f.value).join(' × ')});
  }
 }
 return summary;
}
export function groupProductFacts(input=[],translate=value=>value){
 const facts=uniqueFacts(input,translate),groups=[{label:'Specifications',facts:[]},{label:'Dimensions',facts:[]},{label:'More details',facts:[]}];
 for(const fact of facts){const group=measureKinds.has(fact.kind)?groups[1]:['color','material','finish','shape','pattern','configuration'].includes(fact.kind)?groups[0]:groups[2];group.facts.push(fact);}
 return groups.filter(g=>g.facts.length).map(g=>({...g,label:translate(g.label)}));
}
