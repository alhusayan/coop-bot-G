/* FINDZIA_CHOICE_RELEASE=157.0.3 — one real, signed-offer AI decision. */
(() => {
  'use strict';
  const COPY = {
    en:['Choosing for you…','Found it ✨','Findzia’s pick','Shipping at checkout','Shipping included','View offer','Why this one?','Try again','Couldn’t choose right now.','Add a detail or try another photo.','Cheaper','Higher quality','One quick question','New search','Less by','Offer details'],
    ar:['أختار لك…','لقيناها لك ✨','اختيار Findzia','الشحن عند المتجر','الشحن مشمول','شوف العرض','ليش اخترته؟','حاول مجددًا','ما قدرت أحسم الحين.','أضف تفصيل أو جرّب صورة ثانية.','أرخص','جودة أعلى','سؤال سريع','بحث جديد','أقل بـ','تفاصيل العرض'],
    fr:['Je choisis pour vous…','Trouvé ✨','Choix Findzia','Livraison à vérifier','Livraison incluse','Voir l’offre','Pourquoi ce choix ?','Réessayer','Choix indisponible.','Précisez ou essayez une autre photo.','Moins cher','Meilleure qualité','Une question','Nouvelle recherche','Moins de','Détails'],
    de:['Ich wähle für dich…','Gefunden ✨','Findzia-Auswahl','Versand beim Händler','Versand enthalten','Angebot ansehen','Warum dieses?','Erneut versuchen','Auswahl nicht verfügbar.','Ergänze Details oder ein anderes Foto.','Günstiger','Höhere Qualität','Eine kurze Frage','Neue Suche','Weniger um','Angebotsdetails'],
    es:['Eligiendo para ti…','Encontrado ✨','Elección Findzia','Envío en la tienda','Envío incluido','Ver oferta','¿Por qué este?','Reintentar','No pude elegir ahora.','Añade detalles o prueba otra foto.','Más barato','Más calidad','Una pregunta','Nueva búsqueda','Menos por','Detalles'],
    pt:['A escolher para si…','Encontrado ✨','Escolha Findzia','Envio na loja','Envio incluído','Ver oferta','Porquê este?','Tentar novamente','Não foi possível escolher.','Adicione detalhes ou outra foto.','Mais barato','Mais qualidade','Uma pergunta','Nova pesquisa','Menos','Detalhes'],
    tr:['Senin için seçiyorum…','Bulduk ✨','Findzia seçimi','Kargo mağazada','Kargo dahil','Teklifi gör','Neden bu?','Tekrar dene','Şimdi seçilemedi.','Ayrıntı ekle veya başka fotoğraf dene.','Daha ucuz','Daha kaliteli','Kısa bir soru','Yeni arama','Daha az','Teklif ayrıntıları'],
    ru:['Выбираю для вас…','Нашли ✨','Выбор Findzia','Доставка у продавца','Доставка включена','Посмотреть','Почему этот?','Повторить','Не удалось выбрать.','Уточните запрос или смените фото.','Дешевле','Выше качество','Один вопрос','Новый поиск','Дешевле на','Об предложении'],
    zh:['正在为你挑选…','找到了 ✨','Findzia 精选','运费以商店为准','含运费','查看优惠','为什么选它？','重试','暂时无法选择。','补充说明或换张照片。','更便宜','更高品质','一个小问题','重新搜索','便宜','优惠详情'],
    hi:['आपके लिए चुन रहे हैं…','मिल गया ✨','Findzia की पसंद','शिपिंग स्टोर पर','शिपिंग शामिल','ऑफ़र देखें','यही क्यों?','फिर कोशिश करें','अभी चुन नहीं सके।','विवरण जोड़ें या दूसरी फ़ोटो लें।','सस्ता','बेहतर गुणवत्ता','एक सवाल','नई खोज','इतना कम','ऑफ़र विवरण'],
    ur:['آپ کے لیے منتخب کر رہے ہیں…','مل گیا ✨','Findzia کا انتخاب','شپنگ اسٹور پر','شپنگ شامل','آفر دیکھیں','یہ کیوں؟','دوبارہ کوشش','ابھی منتخب نہیں ہو سکا۔','تفصیل شامل کریں یا دوسری تصویر دیں۔','سستا','بہتر معیار','ایک سوال','نئی تلاش','اتنا کم','آفر کی تفصیل']
  };
  const keys=['choosing','found','badge','shippingUnknown','shippingKnown','open','why','retry','unavailable','noMatch','cheaper','quality','clarify','newSearch','saving','details'];
  function el(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
  function safeURL(value){try{const u=new URL(value);return /^https?:$/.test(u.protocol)&&!u.username&&!u.password?u.href:'';}catch(_){return '';}}
  function rowVersion(row){return JSON.stringify([row.url,row.title,row.image,row.money?.amount,row.money?.currency,row.key_specs,row.match_type]);}
  function parts(money){
    const amount=Number(money?.amount),currency=String(money?.currency||'');
    if(!Number.isFinite(amount)||amount<=0||!/^[A-Z]{3}$/.test(currency))return null;
    try{const p=new Intl.NumberFormat('en-US',{style:'currency',currency}).formatToParts(amount);
      return {major:p.filter(p=>p.type==='integer'||p.type==='group').map(p=>p.value).join(''),minor:p.find(p=>p.type==='fraction')?.value||'',currency,amount};
    }catch(_){return null;}
  }
  const EXTRA={
    en:['Comparing prices','Search log','Close','Your choice','Checking','Results','Searching stores','Choosing the best match'],
    ar:['نقارن الأسعار','سجل البحث','إغلاق','اختيارك','نفحص','النتائج','نبحث بالمتاجر','نختار الأنسب لك'],
    fr:['Comparaison des prix','Journal de recherche','Fermer','Votre choix','Vérification','Résultats','Recherche de magasins','Choix du meilleur résultat'],
    de:['Preisvergleich','Suchprotokoll','Schließen','Deine Auswahl','Prüfung','Ergebnisse','Shops werden durchsucht','Beste Übereinstimmung wählen'],
    es:['Comparando precios','Registro de búsqueda','Cerrar','Tu elección','Verificando','Resultados','Buscando tiendas','Eligiendo la mejor opción'],
    pt:['Comparando preços','Registo da pesquisa','Fechar','A sua escolha','A verificar','Resultados','A pesquisar lojas','A escolher a melhor opção'],
    tr:['Fiyatlar karşılaştırılıyor','Arama günlüğü','Kapat','Senin seçimin','Kontrol ediliyor','Sonuçlar','Mağazalar aranıyor','En uygun seçenek seçiliyor'],
    ru:['Сравниваем цены','Журнал поиска','Закрыть','Ваш выбор','Проверяем','Результаты','Поиск в магазинах','Выбираем лучший вариант'],
    zh:['正在比价','搜索记录','关闭','你的选择','核验中','结果','正在搜索商店','正在选择最佳匹配'],
    hi:['कीमतों की तुलना','खोज लॉग','बंद करें','आपकी पसंद','जाँच जारी','नतीजे','स्टोर खोज रहे हैं','सबसे अच्छा विकल्प चुन रहे हैं'],
    ur:['قیمتوں کا موازنہ','تلاش کا ریکارڈ','بند کریں','آپ کا انتخاب','جانچ جاری','نتائج','اسٹور تلاش ہو رہے ہیں','بہترین انتخاب کر رہے ہیں']
  };
  const extraKeys=['comparing','log','close','yourChoice','checking','results','searching','deciding'];
  const reduced=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
  const formatMoney=m=>{const p=parts(m);return p?p.major+(p.minor?'.'+p.minor:'')+' '+p.currency:'';};
  const currencyFor=c=>/^[A-Z]{3}$/.test(c.currency||'')?c.currency:({kw:'KWD',sa:'SAR',ae:'AED',qa:'QAR',bh:'BHD',om:'OMR',gb:'GBP',uk:'GBP',cn:'CNY',jp:'JPY',in:'INR',de:'EUR',fr:'EUR',es:'EUR',it:'EUR',pt:'EUR',us:'USD',ca:'CAD',au:'AUD'}[String(c.country||'').toLowerCase()]||'USD');

  // Independent physical reels are a decorative searching state, not price quotes.
  // Only land() assigns a price label, using the selected signed offer.
  class PriceReels {
    constructor(node){this.node=node;this.animations=[];this.timer=0;this.spinning=false;this.cells=[];this.shape='';}
    cancel(){clearTimeout(this.timer);this.animations.forEach(a=>a.cancel());this.animations=[];this.spinning=false;}
    clear(){this.cancel();this.node.replaceChildren();this.cells=[];this.shape='';this.node.removeAttribute('aria-label');delete this.node.dataset.spinning;}
    build(major,minor,currency,rolling){
      this.node.replaceChildren();this.cells=[];
      const number=el('span','fz-one-number'),big=el('span','fz-one-major'),small=el('span','fz-one-fils');number.dir='ltr';number.setAttribute('aria-hidden','true');
      const add=(parent,char,place)=>{
        if(!/\d/.test(char)){parent.append(el('span','fz-one-punctuation',char));return;}
        const cell=el('span','fz-one-reel'),track=el('span','fz-one-track');
        for(let i=0;i<40;i++)track.append(el('span','fz-one-digit',String(i%10)));
        const digit=Number(char);track.style.transform=`translateY(-${digit}em)`;cell.append(track);parent.append(cell);this.cells.push({cell,track,digit,place});
      };
      let place=major.replace(/\D/g,'').length;
      for(const char of major)add(big,char,/\d/.test(char)?'major:'+ --place:'');number.append(big);
      if(minor){small.append(el('span','fz-one-punctuation','.'));let index=0;for(const char of minor)add(small,char,'minor:'+index++);number.append(small);}
      // Long prices keep every digit inside the available width.
      const units=major.replace(/\D/g,'').length*.62+(major.match(/,/g)||[]).length*.28+minor.length*.32+1.15;
      number.style.fontSize=`clamp(22px,${Math.min(13,87/units)}vw,${Math.min(64,430/units)}px)`;
      this.node.append(number,el('span','fz-one-currency',currency));this.node.dataset.spinning=String(rolling);
    }
    spin(input={},label='Comparing prices'){
      const list=Array.isArray(input)?input:[input],money=list.find(parts),currency=money?.currency||input.currency||'KWD';
      const p=money?parts(money):{major:'000',minor:new Intl.NumberFormat('en-US',{style:'currency',currency}).formatToParts(0).find(p=>p.type==='fraction')?.value||'',currency};
      const major='0'.repeat(Math.max(3,p.major.replace(/\D/g,'').length)),shape=major.length+':'+p.minor.length+':'+currency;
      if(this.spinning&&shape===this.shape)return;
      this.cancel();this.shape=shape;this.spinning=true;this.build(major,p.minor.replace(/\d/g,'0'),currency,true);this.node.setAttribute('aria-label',label);
      if(reduced()){this.node.replaceChildren(el('span','fz-one-price-wait','···'),el('span','fz-one-currency',currency));return;}
      this.cells.forEach((cell,i)=>{
        const {track}=cell;
        const start=(i*3+Math.floor(Math.random()*10))%10,duration=540+i*91+Math.floor(Math.random()*100);
        cell.start=start;cell.duration=duration;
        cell.motion=track.animate([{transform:`translateY(-${start}em)`},{transform:`translateY(-${start+10}em)`}],{duration,iterations:Infinity,easing:'linear'});
        this.animations.push(cell.motion);
      });
    }
    land(money,done=()=>{}){
      const p=parts(money);if(!p){this.clear();return;}
      const positions=new Map(this.cells.map(cell=>[cell.place,cell.motion?
        cell.start+((Number(cell.motion.currentTime)||0)%cell.duration)/cell.duration*10:cell.digit]));
      this.cancel();this.shape='';this.build(p.major,p.minor,p.currency,false);this.node.setAttribute('aria-label',formatMoney(money));
      if(reduced()){done();return;}
      let finish=0;
      this.cells.forEach(({track,digit,place},i)=>{
        const start=positions.get(place)??(digit+3+i*2)%10,end=30+digit,duration=680+i*85+(i%3)*60;finish=Math.max(finish,duration);
        this.animations.push(track.animate([{transform:`translateY(-${start}em)`},{transform:`translateY(-${end}em)`}],{duration,easing:'cubic-bezier(.12,.63,.19,1)',fill:'forwards'}));
      });
      this.timer=setTimeout(()=>{this.animations.forEach(a=>a.cancel());this.animations=[];done();},finish);
    }
  }

  class SearchLog {
    constructor(node){this.node=node;this.entries=[];this.seen=new Map();this.limit=7;}
    clear(){this.entries=[];this.seen.clear();this.node.replaceChildren();}
    add(key,entry){
      const version=JSON.stringify(entry);if(this.seen.get(key)===version)return;this.seen.set(key,version);
      this.entries.push(entry);if(this.entries.length>200)this.entries.shift();
      const row=el('div','fz-one-log-line');row.dir='ltr';
      row.append(el('span','fz-one-log-mark',entry.price?'›':'·'),el('bdi','fz-one-log-site',entry.site||''),el('bdi','fz-one-log-product',entry.title||''),el('bdi','fz-one-log-price',entry.price||''));
      this.node.append(row);while(this.node.children.length>this.limit)this.node.firstElementChild.remove();
    }
    sync(rows){for(const row of rows){const url=safeURL(row.url);if(!url||!parts(row.money))continue;this.add(url,{site:row.store||new URL(url).hostname.replace(/^www\./,''),title:row.title,price:formatMoney(row.money)});}}
  }
  function mount(root){
    const bridge=root.fzRefineBridge,body=root.querySelector('[data-results-body]');
    if(root.dataset.choicePreview!=='true'||!bridge?.choiceRows||!body||root.fzOneChoice||new URLSearchParams(location.search).get('choice')==='off')return;
    root.dataset.choiceMode='one';
    const text=k=>{const lang=(root.dataset.lang||'en').split('-')[0],i=keys.indexOf(k);return i>=0?(COPY[lang]||COPY.en)[i]:(EXTRA[lang]||EXTRA.en)[extraKeys.indexOf(k)]||k;};
    const box=el('section','fz-one');box.hidden=true;box.setAttribute('aria-label','Findzia');body.before(box);
    const heading=el('h2','fz-one-heading'),stage=el('div','fz-one-stage'),aura=el('div','fz-one-aura'),image=el('img','fz-one-image'),scan=el('div','fz-one-scan');scan.setAttribute('aria-hidden','true');
    const placeholder=el('span','fz-one-image-placeholder','⌕');placeholder.setAttribute('aria-hidden','true');image.alt='';image.decoding='async';image.hidden=true;
    const badge=el('span','fz-one-badge');stage.append(aura,placeholder,image,scan,badge);
    const title=el('h3','fz-one-title'),specs=el('p','fz-one-specs'),price=el('div','fz-one-price');price.setAttribute('role','img');
    const merchant=el('div','fz-one-merchant'),store=el('p','fz-one-store'),shipping=el('p','fz-one-shipping');merchant.append(store,shipping);
    const question=el('div','fz-one-question'),open=el('a','fz-one-open');open.target='_blank';open.rel='noopener noreferrer';open.hidden=true;
    const retry=el('button','fz-one-open');retry.type='button';retry.hidden=true;
    const actions=el('div','fz-one-actions'),cheaper=el('button','fz-one-small'),quality=el('button','fz-one-small'),newSearch=el('button','fz-one-small');
    const logButton=el('button','fz-one-icon'),whyButton=el('button','fz-one-icon','ⓘ');[cheaper,quality,newSearch,logButton,whyButton].forEach(b=>b.type='button');
    const logGlyph=el('span','fz-one-code-glyph','≡'),logCount=el('span','fz-one-log-count');logGlyph.setAttribute('aria-hidden','true');logButton.append(logGlyph,logCount);
    const panelId=(root.id||'findzia')+'-one-offers';logButton.setAttribute('aria-haspopup','dialog');logButton.setAttribute('aria-controls',panelId);logButton.setAttribute('aria-expanded','false');
    actions.append(cheaper,quality,newSearch,whyButton,logButton);
    const logWrap=el('div','fz-one-log'),logCaption=el('div','fz-one-log-caption'),logLines=el('div','fz-one-log-lines');logLines.setAttribute('aria-hidden','true');logWrap.append(logCaption,logLines);
    const dialog=el('dialog','fz-one-dialog');dialog.id=panelId;dialog.setAttribute('aria-labelledby',panelId+'-title');
    const dialogHead=el('div','fz-one-dialog-head'),dialogTitle=el('h2'),close=el('button','fz-one-icon','×');dialogTitle.id=panelId+'-title';close.type='button';dialogHead.append(dialogTitle,close);
    const reason=el('p','fz-one-reason'),offerList=el('div','fz-one-offers');dialog.append(dialogHead,reason,offerList);root.append(dialog);
    const live=el('p','fz-one-sr');live.setAttribute('role','status');live.setAttribute('aria-live','polite');
    box.append(heading,stage,title,specs,price,merchant,question,open,retry,actions,logWrap,live);
    const reels=new PriceReels(price),log=new SearchLog(logLines);
    let generation=-1,requestId=0,controller=null,requestTimer=0,debounce=0,mediaTimer=0,retryTimer=0,doneAt=0;
    let selected=null,mode='best',answers=[],lastKey='',pending=false,disposed=false,celebrated=false,frozenSource='',autoRetries=0,dialogMode='results';
    const header=root.querySelector('[data-fixed-header]');
    function fit(){
      const viewport=window.visualViewport;if(viewport?.scale>1.2)return;
      const height=viewport?.height||window.innerHeight||720,headerHeight=header?.getBoundingClientRect().height||108;
      box.style.setProperty('--one-room',Math.max(300,Math.floor(height-headerHeight-16))+'px');
      if(!box.hidden&&box.getBoundingClientRect&&stage.getBoundingClientRect){
        const bounds=box.getBoundingClientRect(),picture=stage.getBoundingClientRect();
        const top=Math.max(headerHeight,bounds.top-(viewport?.offsetTop||0));
        const rest=Math.max(0,bounds.height-picture.height);
        const imageHeight=Math.max(140,Math.min((window.innerWidth||390)>=900?470:360,Math.floor(height-top-rest-10)));
        box.style.setProperty('--one-image-height',imageHeight+'px');
        stage.style.setProperty('--scan-travel',(imageHeight-4)+'px');
      }
    }
    function labels(){open.textContent=text('open');retry.textContent=text('retry');cheaper.textContent=text('cheaper');quality.textContent=text('quality');newSearch.textContent=text('newSearch');close.setAttribute('aria-label',text('close'));whyButton.setAttribute('aria-label',text('why'));whyButton.title=text('why');logCaption.textContent=text('log');}
    function cancel(){requestId++;controller?.abort();controller=null;clearTimeout(requestTimer);clearTimeout(retryTimer);pending=false;}
    function closeDialog(){dialog.close?.();logButton.setAttribute('aria-expanded','false');}
    function reset(){
      cancel();clearTimeout(debounce);clearTimeout(mediaTimer);reels.clear();log.clear();selected=null;mode='best';answers=[];lastKey='';celebrated=false;doneAt=0;autoRetries=0;frozenSource='';
      box.hidden=true;box.dataset.state='pending';root.dataset.choiceActive='false';question.replaceChildren();image.hidden=true;image.removeAttribute('src');placeholder.hidden=false;closeDialog();
    }
    function activate(){labels();box.hidden=false;root.dataset.choiceActive='true';badge.hidden=true;actions.hidden=true;open.hidden=true;retry.hidden=true;merchant.hidden=true;whyButton.hidden=true;question.replaceChildren();logWrap.hidden=false;fit();}
    function setImage(source,alt){if(!source)return;image.src=source;image.alt=alt||'';image.hidden=false;placeholder.hidden=true;}
    function freezeImage(rows,c){
      if(frozenSource)return;
      const original=c.kind==='image'&&c.image_base64?('data:'+(c.mime_type||'image/jpeg')+';base64,'+c.image_base64.replace(/^data:[^,]+,/,'')):'';
      const source=original||rows[0]?.image;if(source){frozenSource=source;setImage(source,c.query||c.photoDescription);}
    }
    function syncLog(rows){
      log.sync(bridge.choiceLogRows?.()||rows);logCount.textContent=String(rows.length);logButton.disabled=!rows.length;
      logButton.setAttribute('aria-label',text('results')+' · '+rows.length);logButton.title=text('results');
      if(dialog.open&&dialogMode==='results')renderOffers(rows);
    }
    function pendingView(rows,c){
      activate();box.dataset.state='pending';heading.textContent=text('choosing');title.textContent='';specs.textContent='';store.textContent='';shipping.textContent='';
      freezeImage(rows,c);reels.spin(rows.length?rows.map(r=>r.money):{currency:currencyFor(c)},text('comparing'));
      fit();
    }
    function empty(key){
      activate();box.dataset.state='empty';heading.textContent=text(key);reels.clear();title.textContent='';specs.textContent='';store.textContent='';shipping.textContent='';
      retry.hidden=false;actions.hidden=false;cheaper.hidden=true;quality.hidden=true;whyButton.hidden=true;logWrap.hidden=true;live.textContent=heading.textContent;
    }
    function celebrate(){
      if(celebrated||disposed)return;celebrated=true;box.dataset.state='selected';heading.textContent=text('found');live.textContent=text('found')+' '+title.textContent+' '+price.getAttribute('aria-label');fit();
      if(reduced())return;
      for(let i=0;i<14;i++){const s=el('i','fz-one-spark');s.setAttribute('aria-hidden','true');const a=i*Math.PI*2/14,r=60+i%4*16;s.style.setProperty('--spark-x',Math.cos(a)*r+'px');s.style.setProperty('--spark-y',Math.sin(a)*r+25+'px');s.style.setProperty('--spark-r',i*37+'deg');stage.append(s);setTimeout(()=>s.remove(),1300);}
    }
    function show(value,row,manual=false){
      const link=safeURL(row.url);if(!link){empty('unavailable');return;}
      selected={value,token:row.token,url:row.url,version:rowVersion(row),manual};activate();box.dataset.state='settling';heading.textContent=text('found');
      setImage(row.image,row.title);title.textContent=row.title;title.title=row.title;
      specs.textContent=(row.key_specs||[]).slice(0,2).map(s=>s.value).filter(s=>s&&!row.title.toLowerCase().includes(String(s).toLowerCase())).join(' · ');
      store.textContent=value.store||row.store||new URL(link).hostname.replace(/^www\./,'');store.title=store.textContent;
      shipping.textContent=value.money.shipping_known?(value.money.shipping===0?text('shippingKnown'):text('shippingKnown')+' · '+formatMoney({amount:value.money.shipping,currency:value.money.currency})):text('shippingUnknown');
      merchant.hidden=false;open.href=link;open.hidden=false;badge.hidden=false;badge.textContent=manual?text('yourChoice'):value.match==='suitable'&&bridge.context().kind==='image'?(root.dataset.lang==='ar'?'أقرب لطلبك':'Closest match'):text('badge');
      actions.hidden=false;cheaper.hidden=false;quality.hidden=false;cheaper.disabled=false;quality.disabled=false;whyButton.hidden=!value.reason;
      reason.textContent=value.reason||'';logWrap.hidden=true;syncLog(candidates());
      root.dispatchEvent(new CustomEvent('fz:usage',{bubbles:true,detail:{type:'visible',generation,count:1,source:manual?'offer-choice':'ai-choice'}}));
      reels.land(value.money,celebrate);
      fit();
    }
    function candidates(){return bridge.choiceRows().filter(r=>r.token&&safeURL(r.url)&&safeURL(r.image)&&parts(r.money));}
    function renderOffers(rows=candidates()){
      offerList.replaceChildren();
      rows.forEach((row,i)=>{
        const b=el('button','fz-one-offer-row');b.type='button';b.dir='ltr';b.setAttribute('aria-label',row.title+' · '+(row.store||new URL(row.url).hostname)+' · '+formatMoney(row.money));
        b.setAttribute('aria-pressed',String(selected?.url===row.url));
        const info=el('span','fz-one-offer-info');info.append(el('bdi','fz-one-offer-site',row.store||new URL(row.url).hostname),el('bdi','fz-one-offer-title',row.title));
        b.append(el('span','fz-one-offer-index',String(i+1).padStart(2,'0')),info,el('bdi','fz-one-offer-price',formatMoney(row.money)));
        b.addEventListener('click',()=>{
          const current=candidates().find(r=>r.url===row.url&&rowVersion(r)===rowVersion(row));if(!current){renderOffers();return;}
          cancel();closeDialog();celebrated=false;show({url:current.url,token:current.token,store:current.store,money:current.money,reason:'',match:current.match_type},current,true);
        });offerList.append(b);
      });
    }
    function openDialog(mode){dialogMode=mode;dialogTitle.textContent=text(mode==='reason'?'why':'results');reason.hidden=mode!=='reason';offerList.hidden=mode==='reason';if(mode==='results')renderOffers();dialog.showModal?.();logButton.setAttribute('aria-expanded','true');close.focus?.();}
    function queue(){clearTimeout(debounce);debounce=setTimeout(update,60);}
    async function choose(rows,c){
      rows=rows.slice(0,48);
      const key=JSON.stringify([c.generation,c.query,c.country,c.lang,mode,answers,rows.map(r=>r.token)]);
      if(key===lastKey||pending)return;lastKey=key;pending=true;pendingView(rows,c);log.add('decision',{site:'AI',title:text('deciding')});
      const id=++requestId,ctl=new AbortController();controller=ctl;
      const timeout=new Promise((_,reject)=>{requestTimer=setTimeout(()=>{ctl.abort();reject(new Error('timeout'));},24000);});
      try{
        const work=(async()=>{
          const response=await window.FindziaBillingFetch(root,bridge.api.replace(/\/$/,'')+'/api/choice',{
            method:'POST',signal:ctl.signal,headers:{'Content-Type':'application/json'},credentials:'omit',
            body:JSON.stringify({query:c.query||c.photoDescription||'',kind:c.kind,country:c.country,lang:c.lang,extra_specs:c.extra_specs||'',mode,answers,offer_tokens:rows.map(r=>r.token)})
          });const value=await response.json();if(!response.ok||!value.ok){const error=new Error('unavailable');error.retryable=response.status>=500;throw error;}return value;
        })();
        const value=await Promise.race([work,timeout]);
        if(disposed||id!==requestId||bridge.context().generation!==c.generation)return;
        autoRetries=0;
        if(value.status==='question'){
          reels.clear();box.dataset.state='question';heading.textContent=text('clarify');title.textContent=value.question;logWrap.hidden=true;
          for(const label of (value.choices||[]).slice(0,3)){const b=el('button','fz-one-answer',label);b.type='button';b.addEventListener('click',()=>{if(pending)return;answers=[String(label).slice(0,160)];lastKey='';selected=null;queue();});question.append(b);}return;
        }
        if(value.status!=='selected'){empty('noMatch');return;}
        const current=candidates().find(r=>r.url===value.url&&rowVersion(r)===rowVersion(rows.find(o=>o.token===value.token)||{}));
        if(!current){lastKey='';queue();return;}
        celebrated=false;show(value,current);
      }catch(error){
        if(id!==requestId||disposed||bridge.context().generation!==c.generation)return;
        if(autoRetries<1&&error.retryable!==false){autoRetries++;lastKey='';retryTimer=setTimeout(()=>{if(id===requestId)update();},650);}
        else empty('unavailable');
      }finally{if(id===requestId){clearTimeout(requestTimer);controller=null;pending=false;}}
    }
    function update(){
      if(disposed)return;const c=bridge.context();if(generation!==c.generation){reset();generation=c.generation;}
      if(root.dataset.homeState==='empty'&&!c.busy){reset();return;}
      const rows=candidates();syncLog(rows);
      if(!log.entries.length&&(c.busy||rows.length))log.add('start',{site:'>',title:text('searching')});
      if(selected){const row=rows.find(r=>rowVersion(r)===selected.version);if(row){selected.token=row.token;return;}selected=null;lastKey='';celebrated=false;autoRetries=0;reels.clear();}
      if(c.busy){if(!pending)pendingView(rows,c);return;}
      if(!doneAt)doneAt=Date.now();
      if(c.media_pending&&Date.now()-doneAt<4500){pendingView(rows,c);clearTimeout(mediaTimer);mediaTimer=setTimeout(update,300);return;}
      if(!rows.length){if(c.query||c.kind==='image')empty('noMatch');return;}
      choose(rows,c);
    }
    function preference(value){if(pending)return;cancel();mode=value;selected=null;lastKey='';celebrated=false;autoRetries=0;queue();}
    cheaper.addEventListener('click',()=>preference('cheaper'));quality.addEventListener('click',()=>preference('quality'));
    retry.addEventListener('click',()=>{lastKey='';autoRetries=0;queue();});newSearch.addEventListener('click',()=>bridge.newSearch());
    logButton.addEventListener('click',()=>openDialog('results'));whyButton.addEventListener('click',()=>openDialog('reason'));close.addEventListener('click',closeDialog);
    dialog.addEventListener('close',()=>{logButton.setAttribute('aria-expanded','false');});
    dialog.addEventListener('click',event=>{if(event.target===dialog){const b=dialog.getBoundingClientRect();if(event.clientX<b.left||event.clientX>b.right||event.clientY<b.top||event.clientY>b.bottom)closeDialog();}});
    image.addEventListener('error',()=>{
      // An image CDN failure must never throw away an already valid AI choice.
      if(frozenSource&&image.src!==frozenSource){setImage(frozenSource,title.textContent);return;}
      image.hidden=true;placeholder.hidden=false;
    });
    const resetEvent=()=>{reset();generation=-1;queue();};
    const progressEvent=event=>{
      if(generation!==bridge.context().generation)update();
      const data=event.detail;
      if(data?.event==='status'&&typeof data.stage==='string'){
        log.add('stage:'+data.stage,{site:'findzia',title:text('checking')+' / '+data.stage.replace(/_/g,' ').slice(0,65)});
      }
      queue();
    };
    for(const name of ['fz:search-state','fz:choice-results'])root.addEventListener(name,queue);
    root.addEventListener('fz:search-progress',progressEvent);
    root.addEventListener('fz:search-reset',resetEvent);
    const langObserver=new MutationObserver(()=>{cancel();selected=null;lastKey='';celebrated=false;autoRetries=0;log.clear();queue();});langObserver.observe(root,{attributes:true,attributeFilter:['data-lang']});
    const sizeObserver=window.ResizeObserver?new ResizeObserver(fit):null;if(header)sizeObserver?.observe(header);
    window.addEventListener?.('resize',fit);window.visualViewport?.addEventListener('resize',fit);
    document.fonts?.ready?.then(()=>{if(!disposed)fit();});
    function destroy(){disposed=true;reset();langObserver.disconnect();sizeObserver?.disconnect();for(const name of ['fz:search-state','fz:choice-results'])root.removeEventListener(name,queue);root.removeEventListener('fz:search-progress',progressEvent);root.removeEventListener('fz:search-reset',resetEvent);window.removeEventListener?.('resize',fit);window.visualViewport?.removeEventListener('resize',fit);box.remove();dialog.remove();delete root.dataset.choiceMode;delete root.dataset.choiceActive;}
    document.addEventListener('shopify:section:unload',function unload(ev){if(ev.target?.contains(root)){destroy();document.removeEventListener('shopify:section:unload',unload);}});
    root.fzOneChoice={update,destroy,release:'157.0.3'};labels();queue();
  }
  window.FindziaChoice={mount,PriceReels,SearchLog,moneyParts:parts};
  const start=()=>document.querySelectorAll('.fz-home').forEach(mount);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
  document.addEventListener('shopify:section:load',start);
})();
