/* FINDZIA_CAMERA_RELEASE=1.0.0 — camera opens only after a shopper taps it. */
(() => {
 'use strict';
 const COPY={
  en:['Point at a product','Opening camera…','Photos','Take photo and search','Switch camera','Allow camera access, or choose a photo.','Camera unavailable. Choose a photo.','Open device camera'],
  ar:['وجّه الكامرة على المنتج','جاري فتح الكامرة…','الصور','صوّر وابحث','تبديل الكامرة','اسمح باستخدام الكامرة، أو اختر صورة.','الكامرة غير متاحة. اختر صورة.','افتح كامرة الجهاز'],
  ja:['商品にカメラを向けてください','カメラを起動しています…','写真','撮影して検索','カメラを切り替え','カメラへのアクセスを許可するか、写真を選んでください。','カメラを利用できません。写真を選んでください。','端末のカメラを開く'],
  ko:['상품을 카메라에 비춰 주세요','카메라 여는 중…','사진','촬영하고 검색','카메라 전환','카메라 접근을 허용하거나 사진을 선택하세요.','카메라를 사용할 수 없습니다. 사진을 선택하세요.','기기 카메라 열기'],
  de:['Kamera auf ein Produkt richten','Kamera wird geöffnet…','Fotos','Fotografieren und suchen','Kamera wechseln','Kamerazugriff erlauben oder ein Foto wählen.','Kamera nicht verfügbar. Wähle ein Foto.','Gerätekamera öffnen'],
  fr:['Cadrez un produit','Ouverture de la caméra…','Photos','Photographier et rechercher','Changer de caméra','Autorisez la caméra ou choisissez une photo.','Caméra indisponible. Choisissez une photo.','Ouvrir la caméra de l’appareil'],
  it:['Inquadra un prodotto','Apertura della fotocamera…','Foto','Scatta e cerca','Cambia fotocamera','Consenti l’accesso alla fotocamera o scegli una foto.','Fotocamera non disponibile. Scegli una foto.','Apri la fotocamera del dispositivo'],
  es:['Apunta a un producto','Abriendo cámara…','Fotos','Hacer foto y buscar','Cambiar cámara','Permite el acceso a la cámara o elige una foto.','Cámara no disponible. Elige una foto.','Abrir la cámara del dispositivo'],
  pt:['Aponte para um produto','A abrir a câmara…','Fotos','Fotografar e pesquisar','Trocar câmara','Permita o acesso à câmara ou escolha uma foto.','Câmara indisponível. Escolha uma foto.','Abrir a câmara do dispositivo'],
  tr:['Kamerayı bir ürüne doğrultun','Kamera açılıyor…','Fotoğraflar','Fotoğraf çek ve ara','Kamerayı değiştir','Kamera erişimine izin verin veya bir fotoğraf seçin.','Kamera kullanılamıyor. Bir fotoğraf seçin.','Cihaz kamerasını aç'],
  ru:['Наведите камеру на товар','Открываем камеру…','Фото','Снять и найти','Сменить камеру','Разрешите доступ к камере или выберите фото.','Камера недоступна. Выберите фото.','Открыть камеру устройства'],
  zh:['将镜头对准商品','正在打开相机…','照片','拍照并搜索','切换相机','请允许使用相机，或选择照片。','相机不可用，请选择照片。','打开设备相机'],
  hi:['कैमरा उत्पाद की ओर करें','कैमरा खुल रहा है…','फ़ोटो','फ़ोटो लें और खोजें','कैमरा बदलें','कैमरे की अनुमति दें या फ़ोटो चुनें।','कैमरा उपलब्ध नहीं है। फ़ोटो चुनें।','डिवाइस का कैमरा खोलें'],
  ur:['کیمرہ پروڈکٹ کی طرف کریں','کیمرہ کھل رہا ہے…','تصاویر','تصویر لیں اور تلاش کریں','کیمرہ بدلیں','کیمرے کی اجازت دیں یا تصویر منتخب کریں۔','کیمرہ دستیاب نہیں۔ تصویر منتخب کریں۔','ڈیوائس کا کیمرہ کھولیں'],
  id:['Arahkan kamera ke produk','Membuka kamera…','Foto','Ambil foto dan cari','Ganti kamera','Izinkan akses kamera atau pilih foto.','Kamera tidak tersedia. Pilih foto.','Buka kamera perangkat'],
  ms:['Halakan kamera pada produk','Membuka kamera…','Foto','Ambil foto dan cari','Tukar kamera','Benarkan akses kamera atau pilih foto.','Kamera tidak tersedia. Pilih foto.','Buka kamera peranti']
 };
 const ICONS={close:'<path d="m6 6 12 12M6 18 18 6"/>',photos:'<rect x="3" y="3" width="18" height="18" rx="4"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m4 18 5-5 3 3 4-6 5 8"/>',flip:'<path d="M19 8a8 8 0 0 0-13-2L3 9m0-6v6h6M5 16a8 8 0 0 0 13 2l3-3m0 6v-6h-6"/>',shutter:'<path d="M4 7h4l2-3h4l2 3h4v13H4Z"/><circle cx="12" cy="13" r="4"/>'};
 const el=(tag,cls)=>{const n=document.createElement(tag);n.className=cls;return n;};
 function button(cls,icon){const b=el('button',cls);b.type='button';if(icon)b.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+ICONS[icon]+'</svg>';return b;}
 function mount(root){
  const input=root.querySelector('input[id^="fz-photo-"]');if(!input||root.fzCamera)return;
  const dialog=el('dialog','fz-camera-dialog');dialog.setAttribute('data-no-i18n','');dialog.setAttribute('aria-label','Findzia');
  const head=el('div','fz-camera-head'),closeButton=button('fz-camera-icon','close'),brand=el('span','fz-camera-brand');brand.textContent='Findzia';head.append(closeButton,brand);
  const view=el('div','fz-camera-view'),video=el('video','fz-camera-video');video.autoplay=true;video.muted=true;video.playsInline=true;video.setAttribute('playsinline','');video.setAttribute('webkit-playsinline','');
  const frame=el('div','fz-camera-frame');frame.setAttribute('aria-hidden','true');for(let i=0;i<4;i++)frame.append(el('i',''));
  const status=el('p','fz-camera-status');status.setAttribute('role','status');
  const fallback=el('div','fz-camera-fallback'),nativeButton=button('fz-camera-native'),retry=button('fz-camera-retry');fallback.hidden=true;fallback.append(nativeButton,retry);
  view.append(video,frame,status,fallback);
  const foot=el('div','fz-camera-foot'),gallery=button('fz-camera-gallery','photos'),galleryLabel=el('span',''),shutter=button('fz-camera-shutter','shutter'),flip=button('fz-camera-icon fz-camera-flip','flip');gallery.append(galleryLabel);foot.append(gallery,shutter,flip);
  dialog.append(head,view,foot);document.body.append(dialog);
  const nativeInput=el('input','');nativeInput.type='file';nativeInput.accept='image/*';nativeInput.setAttribute('capture','environment');nativeInput.hidden=true;root.append(nativeInput);
  let stream=null,epoch=0,facing='environment',origin=null,savedOverflow=null,disposed=false,shooting=false,timer=0;
  const copy=i=>(COPY[root.dataset.lang]||COPY.en)[i];
  const common=(en,ar)=>window.FindziaI18n?.t(en,ar,root)||(root.dataset.lang==='ar'?ar:en);
  function labels(){
   dialog.dir=['ar','ur'].includes(root.dataset.lang)?'rtl':'ltr';
   closeButton.setAttribute('aria-label',common('Close','إغلاق'));galleryLabel.textContent=copy(2);gallery.setAttribute('aria-label',copy(2));
   shutter.setAttribute('aria-label',copy(3));flip.setAttribute('aria-label',copy(4));nativeButton.textContent=copy(7);retry.textContent=common('Try again','حاول مجدداً');
  }
  function stop(){
   clearTimeout(timer);timer=0;epoch++;shutter.disabled=true;flip.disabled=true;
   stream?.getTracks().forEach(track=>track.stop());stream=null;video.pause();video.srcObject=null;dialog.dataset.ready='false';
  }
  function close(){
   stop();shooting=false;
   if(dialog.open)dialog.close();
   if(savedOverflow){document.documentElement.style.overflow=savedOverflow.html;document.body.style.overflow=savedOverflow.body;savedOverflow=null;}
   if(origin?.isConnected)origin.focus({preventScroll:true});origin=null;
  }
  function showError(denied=false){
   stop();status.textContent=copy(denied?5:6);fallback.hidden=false;
  }
  function ready(){
   if(!dialog.open||!stream||video.readyState<2||!video.videoWidth)return;
   clearTimeout(timer);timer=0;shutter.disabled=false;flip.disabled=false;fallback.hidden=true;status.textContent=copy(0);dialog.dataset.ready='true';
  }
  async function start(){
   stop();const request=epoch;shooting=false;fallback.hidden=true;status.textContent=copy(1);
   if(!navigator.mediaDevices?.getUserMedia){showError();retry.hidden=true;return;}
   retry.hidden=false;
   // A slow permission response remains usable, with an explicit native alternative.
   timer=setTimeout(()=>{if(request===epoch&&dialog.open)fallback.hidden=false;},12000);
   try{
    const next=await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:{ideal:facing},width:{ideal:1920},height:{ideal:1440}}});
    if(disposed||request!==epoch||!dialog.open){next.getTracks().forEach(track=>track.stop());return;}
    stream=next;video.srcObject=next;
    const track=next.getVideoTracks()[0];const actual=track?.getSettings?.().facingMode||facing;
    video.dataset.mirrored=String(actual==='user');
    track?.addEventListener('ended',()=>{if(stream===next&&dialog.open)showError();},{once:true});
    await video.play();if(request===epoch)ready();
   }catch(error){if(request===epoch&&dialog.open)showError(['NotAllowedError','SecurityError'].includes(error.name));}
  }
  function open(trigger){
   if(disposed||dialog.open)return;
   origin=trigger;facing='environment';labels();
   if(!navigator.mediaDevices?.getUserMedia){nativeInput.value='';nativeInput.click();return;}
   savedOverflow={html:document.documentElement.style.overflow,body:document.body.style.overflow};
   dialog.showModal();document.documentElement.style.overflow='hidden';document.body.style.overflow='hidden';start();
  }
  function submit(file){
   if(!file)return;
   try{const transfer=new DataTransfer();transfer.items.add(file);input.files=transfer.files;close();input.dispatchEvent(new Event('change',{bubbles:true}));}
   catch(_){showError();}
  }
  async function capture(){
   if(shooting||shutter.disabled||!stream)return;
   shooting=true;shutter.disabled=true;flip.disabled=true;const request=epoch;
   try{
    // Crop to exactly the live view, retaining up to 1920px for Lens matching.
    const width=video.videoWidth,height=video.videoHeight,rect=video.getBoundingClientRect(),ratio=rect.width/rect.height;
    const sw=Math.min(width,height*ratio),sh=Math.min(height,width/ratio),scale=Math.min(1,1920/Math.max(sw,sh));
    const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(sw*scale));canvas.height=Math.max(1,Math.round(sh*scale));
    canvas.getContext('2d').drawImage(video,(width-sw)/2,(height-sh)/2,sw,sh,0,0,canvas.width,canvas.height);
    const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.92));
    if(request!==epoch||!dialog.open)return;
    if(!blob)throw Error('capture_failed');
    submit(new File([blob],'findzia-photo.jpg',{type:'image/jpeg'}));
   }catch(_){if(request===epoch){shooting=false;shutter.disabled=false;flip.disabled=false;status.textContent=common('Try again','حاول مجدداً');}}
  }
  function cameraClick(event){
   const target=event.target.closest?.('[data-dark-photo],[data-photo-btn]');
   if(!target||!root.contains(target)||target.disabled)return;
   event.preventDefault();event.stopImmediatePropagation();open(target);
  }
  function galleryClick(){close();input.value='';input.click();}
  function nativeClick(){close();nativeInput.value='';nativeInput.click();}
  function nativeChange(){const file=nativeInput.files?.[0];submit(file);nativeInput.value='';}
  function visibility(){if(document.hidden)close();}
  function flipCamera(){if(flip.disabled)return;facing=facing==='environment'?'user':'environment';start();}
  function cancelled(event){event.preventDefault();close();}
  closeButton.addEventListener('click',close);dialog.addEventListener('cancel',cancelled);dialog.addEventListener('close',()=>{if(!dialog.open)close();});
  gallery.addEventListener('click',galleryClick);nativeButton.addEventListener('click',nativeClick);retry.addEventListener('click',start);
  shutter.addEventListener('click',capture);flip.addEventListener('click',flipCamera);nativeInput.addEventListener('change',nativeChange);
  video.addEventListener('loadeddata',ready);video.addEventListener('playing',ready);root.addEventListener('click',cameraClick,true);
  document.addEventListener('visibilitychange',visibility);window.addEventListener('pagehide',close);
  function destroy(){disposed=true;close();root.removeEventListener('click',cameraClick,true);document.removeEventListener('visibilitychange',visibility);window.removeEventListener('pagehide',close);dialog.remove();nativeInput.remove();delete root.fzCamera;}
  document.addEventListener('shopify:section:unload',function unload(event){if(event.target?.contains(root)){destroy();document.removeEventListener('shopify:section:unload',unload);}});
  root.fzCamera={destroy,release:'1.0.0'};
 }
 const start=()=>document.querySelectorAll('.fz-home').forEach(mount);
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
 document.addEventListener('shopify:section:load',start);
})();
