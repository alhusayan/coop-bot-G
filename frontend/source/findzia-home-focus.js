/* Presentation adapter only. Native search, billing, uploads and design state
   remain the single source of truth in each section. */
(()=>{
 'use strict';
 const words={
  ar:['مساحتك، بتصميم جديد.','أضف صورتك','جرّب مثال','كل قطعة لبيتك.','ابحث عن قطعة','المختص المناسب لبيتك.','اختر الخدمة'],
  en:['Your room. Reimagined.','Add your photo','Try an example','Find your next piece.','Find a piece','The right pro for your home.','Choose a service'],
  fr:['Votre pièce, réinventée.','Ajouter une photo','Voir un exemple','Trouvez la bonne pièce.','Chercher un produit','Le bon pro pour votre maison.','Choisir un service'],
  de:['Ihr Raum. Neu gedacht.','Foto hinzufügen','Beispiel ansehen','Das passende Stück.','Produkt suchen','Die richtigen Profis fürs Zuhause.','Service wählen'],
  es:['Tu espacio, renovado.','Añade tu foto','Prueba un ejemplo','Encuentra tu próxima pieza.','Busca un producto','El profesional para tu hogar.','Elige un servicio'],
  it:['Il tuo spazio, reinventato.','Aggiungi una foto','Prova un esempio','Trova il pezzo giusto.','Cerca un prodotto','Il professionista per casa tua.','Scegli un servizio'],
  pt:['Seu espaço, renovado.','Adicione sua foto','Veja um exemplo','Encontre a peça certa.','Buscar um produto','O profissional para sua casa.','Escolha um serviço'],
  ru:['Ваш интерьер по-новому.','Добавить фото','Посмотреть пример','Найдите нужную вещь.','Найти товар','Мастер для вашего дома.','Выбрать услугу'],
  zh:['让你的空间焕然一新。','添加照片','查看示例','找到心仪的家居好物。','查找商品','为你的家找对师傅。','选择服务'],
  ja:['あなたの空間を、新しく。','写真を追加','実例を見る','ぴったりのアイテムを。','商品を探す','住まいに合う専門家を。','サービスを選ぶ'],
  ko:['내 공간, 새로운 모습.','사진 추가','예시 보기','우리 집에 맞는 제품.','제품 찾기','우리 집에 맞는 전문가.','서비스 선택'],
  hi:['आपका कमरा, नए रूप में।','अपनी तस्वीर जोड़ें','उदाहरण देखें','सही सामान खोजें।','उत्पाद खोजें','आपके घर के लिए सही विशेषज्ञ।','सेवा चुनें'],
  ur:['آپ کی جگہ، ایک نئے انداز میں۔','اپنی تصویر شامل کریں','مثال دیکھیں','اپنے گھر کا سامان تلاش کریں۔','مصنوعات تلاش کریں','آپ کے گھر کے لیے صحیح ماہر۔','خدمت منتخب کریں'],
  id:['Ruang Anda, wajah baru.','Tambahkan foto','Coba contoh','Temukan barang yang pas.','Cari produk','Ahli yang tepat untuk rumah.','Pilih layanan'],
  ms:['Ruang anda, wajah baharu.','Tambah foto','Cuba contoh','Cari barangan yang sesuai.','Cari produk','Pakar yang sesuai untuk rumah.','Pilih perkhidmatan'],
  nl:['Jouw ruimte, opnieuw bedacht.','Voeg je foto toe','Bekijk een voorbeeld','Vind het juiste item.','Zoek een product','De juiste vakman voor je huis.','Kies een dienst'],
  tr:['Alanınız, yeniden tasarlandı.','Fotoğrafınızı ekleyin','Bir örnek deneyin','Doğru parçayı bulun.','Ürün ara','Eviniz için doğru uzman.','Hizmet seçin']
 };
 function mount(){
  const doc=document.documentElement,root=document.querySelector('.fz-home'),project=doc.dataset.hubProject;
  if(!doc.dataset.findziaEmbedded||!root||!['shop','one','space','services'].includes(project))return;
  if(project==='space'&&doc.hasAttribute('data-space-scene'))return;
  const $=selector=>document.querySelector(selector);
  const entry=document.createElement('section');entry.className='experience-entry';entry.setAttribute('data-no-i18n','');
  const content=document.createElement('div');content.className='experience-copy';
  const title=document.createElement('h1');title.tabIndex=-1;
  const actions=document.createElement('div');actions.className='experience-actions';
  const primary=document.createElement('button');primary.type='button';primary.className='experience-primary';
  const secondary=document.createElement('button');secondary.type='button';secondary.className='experience-secondary';
  actions.append(primary);content.append(title,actions);entry.append(content);
  const setText=(el,value)=>{if(el.textContent!==value)el.textContent=value;};
  const composer=mode=>window.FindziaHubBridge?.composer(mode);
  let state=()=>{},observe=[];
  if(project==='space'){
   const home=$('#home');if(!home)return;home.prepend(entry);doc.dataset.experience='space';
   // Keep access errors and their retry action available in the new scene.
   for(const selector of ['#auth-notice','#retry-access']){const el=$(selector);if(el)content.append(el);}
   actions.append(secondary);primary.onclick=()=>composer('photo');secondary.onclick=()=>$('#home [data-action="demo"]')?.click();
   state=()=>{const source=$('[data-action="upload"]');primary.disabled=!!source?.disabled;secondary.disabled=!!$('#home [data-action="demo"]')?.disabled;};
   observe=[$('[data-action="upload"]'),$('#home [data-action="demo"]')];
  }else if(project==='services'){
   const main=$('#services-main');if(!main)return;main.prepend(entry);doc.dataset.experience='services';
   primary.onclick=()=>$('#svc-browse')?.click();
   const form=$('#svc-form'),photo=$('#svc-photo-panel'),page=$('.svc-page');
   const request=document.createElement('h2');request.className='experience-request';request.setAttribute('dir','auto');request.setAttribute('data-no-i18n','');form.prepend(request);
   state=()=>{
    const value=$('#svc-query').value.trim(),hasPhoto=!photo.hidden,results=page.dataset.hasResults==='true';
    const stage=results?'results':value||hasPhoto?'request':'start';
    if(doc.dataset.experienceStage!==stage)doc.dataset.experienceStage=stage;
    entry.hidden=stage!=='start';setText(request,value);request.hidden=!value;
   };
   document.addEventListener('findzia:header-state',state);$('#svc-query').addEventListener('input',state);
   observe=[page,photo,form,$('#svc-submit')];
  }else{
   const home=root.querySelector('[data-dark-home]');if(!home)return;home.append(entry);doc.dataset.experience='shop';
   primary.onclick=()=>composer('query');
  }
  function render(){
   const language=root.dataset.lang||doc.lang,copy=words[language]||words.en;
   setText(title,copy[project==='space'?0:project==='services'?5:3]);
   setText(primary,copy[project==='space'?1:project==='services'?6:4]);setText(secondary,copy[2]);state();
  }
  // Observe only state-bearing attributes, never this adapter's own text.
  const observer=new MutationObserver(render);observer.observe(root,{attributes:true,attributeFilter:['data-lang','data-home-state']});
  for(const el of observe)if(el)observer.observe(el,{attributes:true,attributeFilter:['disabled','hidden','data-has-results']});
  doc.dataset.experienceReady='true';render();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})();
