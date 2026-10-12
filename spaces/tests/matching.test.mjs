import test from 'node:test';
import assert from 'node:assert/strict';
import sharp from 'sharp';
import {visualDecision,replacementDecision,auditVisual,searchItem,cropPiece} from '../matching.mjs';
const pass={index:0,score:99,category:'match',color:'match',shape:'match',material:'match',configuration:'match',proportions:'match',differences:[],reason:'Visible features agree'};
const image=await sharp({create:{width:300,height:200,channels:3,background:'#aa9988'}}).jpeg().toBuffer();
const target={inlineData:{mimeType:'image/jpeg',data:image.toString('base64')}};
const item={id:'1',name_en:'Rounded dark green chair',query:'dark green rounded tub chair hidden base',specs:{color:'dark green',shape:'rounded',legs:'hidden'}};
const product={'@type':'Product',name:'Rounded green chair',image:'https://shop.kw/chair.jpg',offers:{priceCurrency:'KWD',price:'99.000',availability:'https://schema.org/InStock'}};
const page=p=>`<script type="application/ld+json">${JSON.stringify(p)}</script>`;
const deps={target,lensUrl:'https://rooms.example/crop.jpg',lensSearch:async()=>[{link:'https://shop.kw/products/chair',title:'Rounded green chair'}],page:async url=>({url,html:page(product)}),fetchImage:async()=>({bytes:image}),judge:async()=>({results:[pass]})};
test('different real products are disclosed as replacements, never silently accepted as design matches',async()=>{
 const alternative={...pass,score:35,shape:'mismatch',adaptable:true,differences:['Different leg shape']};
 assert.equal(visualDecision(alternative),false);assert.equal(replacementDecision(alternative),true);
 assert.equal(replacementDecision({...alternative,color:'mismatch'}),false);
 let latest;
 const matches=await searchItem(item,'KW',{...deps,judge:async()=>({results:[alternative]}),search:async()=>({}),onProgress:x=>latest=x});
 assert.deepEqual(matches,[]);assert.equal(latest.alternatives.length,1);assert.equal(latest.alternatives[0].match,'replacement');
});
test('global sources wait for local search and its recovery before publishing',async()=>{
 let finishSlow,started;const slow=new Promise(resolve=>finishSlow=resolve),localStarted=new Promise(resolve=>started=resolve);const countries=[];
 const running=searchItem(item,'KW',{...deps,lensSearch:async()=>[],page:async()=>{throw Error('page unavailable');},search:async(q,country)=>{countries.push(country);if(country==='KW'){started();return slow;}if(country==='US')return {images:[{title:'Green chair',link:'https://www.amazon.com/dp/B012345678',imageUrl:'https://shop.example/chair.jpg'}]};return {};}});
 await localStarted;assert.ok(countries.every(x=>x==='KW'));finishSlow({});const offers=await running;
 assert.equal(offers[0].market_scope,'international');assert.ok(countries.includes('US'));assert.ok(countries.includes('CN'));assert.equal(countries.filter(x=>x==='KW').length,4);
});
test('a high score never overrides wrong colour, shape, configuration, proportions or visible differences',()=>{
 assert.equal(visualDecision(pass),true);
 for(const k of ['category','color','shape','material','configuration','proportions']){assert.equal(visualDecision({...pass,[k]:'mismatch'}),false,k);assert.equal(visualDecision({...pass,[k]:'unclear'}),false,k);}
 assert.equal(visualDecision({...pass,differences:['Gold legs instead of concealed base']}),false);assert.equal(visualDecision({...pass,score:87}),false);
});
test('actual target and store images are required; title-only approval cannot leak into results',async()=>{
 const o={title:'A chair',image:'https://shop.kw/a.jpg'};
 assert.deepEqual(await auditVisual(item,[o],null,{judge:async()=>({results:[pass]})}),[]);
 assert.deepEqual(await auditVisual(item,[o],target,{fetchImage:async()=>{throw Error('unavailable');},judge:async()=>({results:[pass]})}),[]);
});
test('Lens runs first and a checked local match retains the original store price',async()=>{
 const countries=[];const r=await searchItem(item,'KW',{...deps,search:async(_q,country)=>{countries.push(country);return {};},judge:async parts=>{assert.equal(parts.filter(x=>x.inlineData).length,2);return {results:[{...pass,price:1}]};}});
 assert.ok(countries.every(x=>x==='KW'));assert.equal(r[0].price,99);assert.equal(r[0].size_verified,false);assert.equal(r[0].match,'visual');
});
test('a visually checked local listing without a price is not discarded or assigned zero',async()=>{
 const r=await searchItem(item,'KW',{...deps,page:async url=>({url,html:page({...product,offers:undefined})}),search:async()=>({})});assert.equal(r.length,1);assert.equal(r[0].price,null);
});
test('wrong-colour Lens result triggers detailed search, without showing the rejected item',async()=>{
 let textCalls=0;const r=await searchItem(item,'KW',{...deps,judge:async()=>({results:[{...pass,color:'mismatch'}]}),search:async()=>{textCalls++;return {};}});assert.deepEqual(r,[]);assert.ok(textCalls>=3);
});
test('cropping keeps the selected object bounded to the room image',async()=>{
 const bytes=await cropPiece(image,[-15,400,1100,1100]),m=await sharp(bytes).metadata();assert.equal(m.height,200);assert.ok(m.width>175&&m.width<190);assert.equal(m.format,'jpeg');
});
test('unapproved foreign Lens and local-query hits cannot take candidate slots or be audited',async()=>{
 const foreign={link:'https://foreign.example/products/chair',title:'Green chair',imageUrl:'https://shop.kw/chair.jpg'};
 const ebay={...foreign,link:'https://www.ebay.com/itm/123456789'};let audits=0;
 const r=await searchItem(item,'KW',{...deps,lensSearch:async()=>[...Array.from({length:12},(_,i)=>({...foreign,link:foreign.link+i})),ebay],search:async()=>({images:[foreign]}),page:async()=>{throw Error('offline');},judge:async parts=>{audits++;assert.ok(!JSON.stringify(parts).includes('foreign.example'));return {results:[pass]};}});
 assert.equal(audits,1);assert.equal(r.length,1);assert.equal(r[0].link,ebay.link);
});
test('an approved link redirecting to an unapproved foreign store is rejected',async()=>{
 const r=await searchItem(item,'KW',{...deps,lensSearch:async()=>[{link:'https://www.amazon.com/dp/123',title:'Green chair'}],page:async()=>({url:'https://foreign.example/products/chair',html:page(product)}),search:async()=>({})});assert.deepEqual(r,[]);
});
test('furniture catalogue pages need purchase evidence; missing price alone is acceptable',async()=>{
 const link='https://www.archiproducts.com/en/products/designer/armchair_123';const run=html=>searchItem(item,'KW',{...deps,lensSearch:async()=>[{link,title:'Green chair',imageUrl:product.image}],page:async()=>({url:link,html}),search:async()=>({})});
 assert.deepEqual(await run(page({...product,offers:undefined})),[]);
 const r=await run(page({...product,offers:undefined})+'<button>Add to cart</button>');assert.equal(r.length,1);assert.equal(r[0].price,null);assert.equal(r[0].market_scope,'international');
});

test('a suitable local replacement ends discovery before any foreign Lens audit or global query',async()=>{
 const local={link:'https://www.homecentre.com/sa/en/buy-bed/p/123',title:'Beige single bed',imageUrl:'https://shop.kw/local.jpg'},foreign={...local,link:'https://www.amazon.com/dp/123',imageUrl:'https://shop.kw/foreign.jpg'};
 const seenImages=[],countries=[];let latest;
 await searchItem(item,'SA',{...deps,lensSearch:async()=>[foreign,local],fetchImage:async url=>{seenImages.push(url);return {bytes:image};},search:async(_q,country)=>{countries.push(country);return {};},page:async()=>{throw Error('offline');},judge:async()=>({results:[{...pass,score:65,shape:'mismatch',adaptable:true,differences:['Different arms']}]}),onProgress:x=>latest=x});
 assert.ok(countries.every(x=>x==='SA'));assert.ok(!seenImages.includes(foreign.imageUrl));assert.equal(latest.alternatives[0].market_scope,'local');
});
test('local recovery finds a bed before approved international stores are called',async()=>{
 const calls=[],phases=[];const r=await searchItem({...item,name_en:'Single platform bed'},'SA',{...deps,lensSearch:async()=>[],page:async()=>{throw Error('offline');},search:async(q,country,opts)=>{calls.push([q,country]);return opts.source==='local-recovery'?{images:[{link:'https://www.homecentre.com/sa/en/buy-single-bed/p/123',title:'Single bed',imageUrl:product.image}]}:{};},onProgress:x=>phases.push(x.phase)});
 assert.equal(r[0].market_scope,'local');assert.equal(calls.length,4);assert.ok(calls.every(x=>x[1]==='SA'));assert.ok(phases.includes('local-recovery'));assert.ok(!phases.includes('global'));
});
