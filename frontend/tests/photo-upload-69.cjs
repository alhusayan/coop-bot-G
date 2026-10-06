const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
const source = fs.readFileSync(path.join(__dirname,'../source/findzia-home.liquid'),'utf8');
const helper = source.split('// FINDZIA_PHOTO_UPLOAD_69_BEGIN')[1].split('// FINDZIA_PHOTO_UPLOAD_69_END')[0];

(async()=>{
 const browser=await chromium.launch({executablePath:process.env.FINDZIA_TEST_CHROME,args:['--no-sandbox','--disable-dev-shm-usage']});
 try {
  const page=await browser.newPage();await page.route('**/*',r=>r.abort());
  await page.setContent('<html><body></body></html>');await page.addScriptTag({content:helper});
  const results=await page.evaluate(async()=>{
   const checks=[];
   function ok(value,label){if(!value)throw Error(label);checks.push(label);}
   async function blob(canvas,type='image/png',quality=.96){return new Promise(r=>canvas.toBlob(r,type,quality));}
   async function decode(data){const im=new Image();im.src='data:'+data.mime_type+';base64,'+data.image_base64;await im.decode();return im;}
   const canvas=document.createElement('canvas');canvas.width=4032;canvas.height=3024;
   const ctx=canvas.getContext('2d');const pixels=ctx.createImageData(canvas.width,canvas.height);
   let seed=23445;
   for(let i=0;i<pixels.data.length;i+=4){seed=(Math.imul(seed,1664525)+1013904223)|0;pixels.data[i]=(seed>>>16)&255;pixels.data[i+1]=(seed>>>8)&255;pixels.data[i+2]=seed&255;pixels.data[i+3]=255;}
   ctx.putImageData(pixels,0,0);
   ctx.fillStyle='#f00';ctx.fillRect(0,0,900,900);
   ctx.fillStyle='#00f';ctx.fillRect(3100,2100,932,924);
   const original=await blob(canvas,'image/jpeg');const prepared=await fzPreparePhotoUpload(original);
   const image=await decode(prepared);
   ok(image.naturalWidth===1600&&image.naturalHeight===1200,'large camera image retains framing at 1600 pixels');
   ok(prepared.image_upload.upload_bytes<original.size*.5,'camera upload shrinks by more than half');
   ok(prepared.mime_type==='image/jpeg','encoded MIME matches transmitted JPEG');
   ok(prepared.image_upload.original_bytes===original.size&&prepared.image_upload.prepare_ms>=0,'preparation telemetry contains actual sizes');
   const sample=document.createElement('canvas');sample.width=1600;sample.height=1200;const draw=sample.getContext('2d');draw.drawImage(image,0,0);
   const red=draw.getImageData(80,80,1,1).data,blue=draw.getImageData(1520,1120,1,1).data;
   ok(red[0]>230&&red[2]<20&&blue[2]>230&&blue[0]<20,'corner detail and orientation are preserved');
   const small=document.createElement('canvas');small.width=280;small.height=400;small.getContext('2d').fillRect(0,0,280,400);
   const tiny=await blob(small);const tinyResult=await fzPreparePhotoUpload(tiny);
   ok(tinyResult.image_upload.upload_bytes===tiny.size&&tinyResult.mime_type==='image/png','small images are not enlarged or reencoded');
   const portrait=document.createElement('canvas');portrait.width=3024;portrait.height=4032;portrait.getContext('2d').drawImage(canvas,0,0,3024,4032);
   const portraitResult=await fzPreparePhotoUpload(await blob(portrait,'image/jpeg'));
   const portraitImage=await decode(portraitResult);ok(portraitImage.width===1200&&portraitImage.height===1600,'portrait aspect ratio is preserved');
   // Browser orientation handling is exercised with a real EXIF rotation tag.
   const jpeg=new Uint8Array(await original.arrayBuffer());
   const exif=new Uint8Array([255,225,0,34,69,120,105,102,0,0,73,73,42,0,8,0,0,0,1,0,18,1,3,0,1,0,0,0,6,0,0,0,0,0,0,0]);
   const rotated=new Blob([jpeg.slice(0,2),exif,jpeg.slice(2)],{type:'image/jpeg'});
   const rotation=await decode(await fzPreparePhotoUpload(rotated));
   ok(rotation.width===1200&&rotation.height===1600,'EXIF orientation is applied before resizing');
   const unsupported=new Blob([new Uint8Array(600000)],{type:'image/heic'});
   const originalHeic=await fzPreparePhotoUpload(unsupported);
   ok(originalHeic.image_upload.upload_bytes===unsupported.size&&originalHeic.mime_type==='image/heic','HEIC retains the existing server decode path');
   const invalid=new Blob([new Uint8Array(600000)],{type:'image/jpeg'});
   ok((await fzPreparePhotoUpload(invalid)).image_upload.upload_bytes===invalid.size,'failed browser decode falls back to original');
   let cancelled=false;try{await fzPreparePhotoUpload(original,()=>true);}catch(e){cancelled=e.name==='AbortError';}
   ok(cancelled,'cancelled search never produces an upload');
   const toBlob=HTMLCanvasElement.prototype.toBlob;
   try{HTMLCanvasElement.prototype.toBlob=function(callback){callback(null);};
    ok((await fzPreparePhotoUpload(original)).image_upload.upload_bytes===original.size,'failed canvas encoding falls back to original');
   }finally{HTMLCanvasElement.prototype.toBlob=toBlob;}
   return {checks,original_bytes:original.size,upload_bytes:prepared.image_upload.upload_bytes,prepare_ms:prepared.image_upload.prepare_ms};
  });
  assert.equal(results.checks.length,12);
  console.log(JSON.stringify(results,null,2));
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
