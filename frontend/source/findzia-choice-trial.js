/* FINDZIA_CHOICE_RELEASE=157.0.12 — photo identity is independent of price availability. */
(() => {
  'use strict';
  const COPY = {
    en:['Choosing for you…','Found it ✨','Findzia’s pick','Shipping at checkout','Shipping included','View offer','Why this one?','Try again','Couldn’t choose right now.','No matching offer confirmed yet.','Cheaper','Higher quality','One quick question','New search','Less by','Offer details'],
    ar:['أختار لك…','لقيناها لك ✨','اختيار Findzia','الشحن عند المتجر','الشحن مشمول','شوف العرض','ليش اخترته؟','حاول مجددًا','ما قدرت أحسم الحين.','ما تأكدنا من عرض مطابق للحين.','أرخص','جودة أعلى','سؤال سريع','بحث جديد','أقل بـ','تفاصيل العرض'],
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
  // A refreshed image proxy or match label is not a different offer. Keep the
  // signed source, identity, specifications and price in the decision key.
  function rowVersion(row){return JSON.stringify([row.url,row.title,row.vision_image||row.image,row.money?.amount,row.money?.currency,row.key_specs]);}
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
  const PROVISIONAL={en:'Best so far',ar:'أفضل المتوفر حاليًا',fr:'Meilleur choix actuel',de:'Bisher beste Wahl',es:'Mejor hasta ahora',pt:'Melhor até agora',tr:'Şu ana kadarki en iyi',ru:'Пока лучший вариант',zh:'目前最佳',hi:'अब तक का सबसे अच्छा',ur:'اب تک کا بہترین'};
  const extraKeys=['comparing','log','close','yourChoice','checking','results','searching','deciding'];
  const QUESTION_COPY={
    en:['Choose for me','One tap to narrow it down','Use this preference'],ar:['اختَر لي','اختيار واحد يقرّبنا لطلبك','اعتماد الاختيار'],
    fr:['Choisissez pour moi','Un choix pour affiner','Utiliser ce choix'],de:['Wähle für mich','Mit einem Tipp eingrenzen','Auswahl verwenden'],
    es:['Elige por mí','Un toque para concretar','Usar esta opción'],pt:['Escolha por mim','Um toque para refinar','Usar esta opção'],
    tr:['Benim için seç','Tek dokunuşla daralt','Bu tercihi kullan'],ru:['Выберите за меня','Один выбор для уточнения','Использовать выбор'],
    zh:['帮我选','点一下，缩小范围','使用此偏好'],hi:['मेरे लिए चुनें','एक टैप से पसंद बताएं','यह पसंद अपनाएं'],ur:['میرے لیے منتخب کریں','ایک انتخاب سے تلاش بہتر کریں','یہ ترجیح استعمال کریں'],
    ja:['おまかせ','タップして絞り込む','この条件を使う'],ko:['대신 골라주세요','한 번 눌러 조건 좁히기','이 조건 적용'],
    it:['Scegli per me','Un tocco per affinare','Usa questa preferenza'],nl:['Kies voor mij','Verfijn met één tik','Gebruik deze voorkeur'],id:['Pilihkan untuk saya','Satu ketukan untuk memperjelas','Gunakan pilihan ini']
  };
  const reduced=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
  const formatMoney=m=>{const p=parts(m);return p?p.major+(p.minor?'.'+p.minor:'')+' '+p.currency:'';};
  const STORE_PRICE={en:'Check price at store',ar:'شوف السعر في المتجر',fr:'Prix en boutique',de:'Preis im Shop prüfen',es:'Consultar precio en tienda',pt:'Ver preço na loja',tr:'Mağazada fiyatı gör',ru:'Цена у продавца',zh:'到商店查看价格',hi:'स्टोर पर कीमत देखें',ur:'اسٹور پر قیمت دیکھیں'};
  const currencyFor=c=>/^[A-Z]{3}$/.test(c.currency||'')?c.currency:({kw:'KWD',sa:'SAR',ae:'AED',qa:'QAR',bh:'BHD',om:'OMR',gb:'GBP',uk:'GBP',cn:'CNY',jp:'JPY',in:'INR',de:'EUR',fr:'EUR',es:'EUR',it:'EUR',pt:'EUR',us:'USD',ca:'CAD',au:'AUD'}[String(c.country||'').toLowerCase()]||'USD');

  // Each digit is a split flap with its own clock and hinge, not a scrolling texture.
  // Loading lands on streamed source prices; idle excursions stay close to the last quote.
  // Only a signed, reviewed offer can set the final selected price.
  class PriceReels {
    constructor(node,onQuote=()=>{}){this.node=node;this.onQuote=onQuote;this.cells=[];this.shape='';this.spinning=false;this.epoch=0;this.canAnimate=true;this.live=false;this.liveTimer=0;this.moving=false;this.currentMoney=null;this.activeOffer=null;this.offers=[];this.queue=[];this.seen=new Set();this.idleStep=0;}
    stopMotion(){
      this.epoch++;this.moving=false;
      for(const cell of this.cells){clearTimeout(cell.timer);cell.motions.forEach(a=>a.cancel());cell.motions=[];this.paint(cell,cell.next??cell.digit);}
    }
    cancel(){clearTimeout(this.liveTimer);this.liveTimer=0;this.live=false;this.spinning=false;this.stopMotion();}
    clear(){this.cancel();this.node.replaceChildren();this.cells=[];this.shape='';this.currentMoney=null;this.activeOffer=null;this.offers=[];this.queue=[];this.seen.clear();this.node.removeAttribute('aria-label');delete this.node.dataset.spinning;delete this.node.dataset.quote;}
    paint(cell,digit){
      cell.digit=digit;cell.next=null;cell.node.dataset.digit=String(digit);
      for(const face of [cell.upper,cell.lower,cell.out,cell.into])face.firstElementChild.textContent=String(digit);
      cell.out.hidden=true;cell.into.hidden=true;
    }
    build(major,minor,currency,rolling,positions=new Map()){
      const shape=major.replace(/\d/g,'0')+':'+minor.length+':'+currency;
      if(this.shape===shape&&this.cells.length){
        const digits=(major+minor).replace(/\D/g,'').split('').map(Number);
        this.cells.forEach((cell,i)=>cell.target=digits[i]);this.node.dataset.spinning=String(rolling);return;
      }
      this.shape=shape;
      this.node.replaceChildren();this.cells=[];
      const number=el('span','fz-one-number'),big=el('span','fz-one-major'),small=el('span','fz-one-fils');number.dir='ltr';number.setAttribute('aria-hidden','true');
      const add=(parent,char,place)=>{
        if(!/\d/.test(char)){parent.append(el('span','fz-one-punctuation',char));return;}
        const node=el('span','fz-one-reel');node.dataset.place=place;
        const face=(name)=>{const n=el('span','fz-one-face '+name);n.append(el('span','fz-one-glyph',char));node.append(n);return n;};
        const cell={node,upper:face('fz-one-upper'),lower:face('fz-one-lower'),out:face('fz-one-flap-out'),into:face('fz-one-flap-in'),digit:Number(char),next:null,timer:0,motions:[]};
        cell.place=place;cell.target=Number(char);
        this.paint(cell,positions.get(place)??cell.digit);parent.append(node);this.cells.push(cell);
      };
      let place=major.replace(/\D/g,'').length;
      for(const char of major)add(big,char,/\d/.test(char)?'major:'+ --place:'');number.append(big);
      if(minor){small.append(el('span','fz-one-punctuation','.'));let index=0;for(const char of minor)add(small,char,'minor:'+index++);number.append(small);}
      const units=major.replace(/\D/g,'').length*.64+(major.match(/,/g)||[]).length*.27+minor.length*.32+1.15;
      number.style.fontSize=`clamp(22px,${Math.min(15,78/units)}vw,${Math.min(72,430/units)}px)`;
      this.node.append(number,el('span','fz-one-currency',currency));this.node.dataset.spinning=String(rolling);
      this.canAnimate=typeof this.cells[0]?.out.animate==='function';
    }
    flip(cell,digit,duration,done,direction=1){
      const epoch=this.epoch;
      cell.next=digit;cell.node.dataset.direction=direction<0?'up':'down';
      cell.upper.firstElementChild.textContent=String(direction<0?cell.digit:digit);
      cell.lower.firstElementChild.textContent=String(direction<0?digit:cell.digit);
      cell.out.firstElementChild.textContent=String(cell.digit);
      cell.into.firstElementChild.textContent=String(digit);
      cell.out.hidden=false;cell.into.hidden=false;
      cell.motions=[
        cell.out.animate([{transform:'rotateX(0deg)',filter:'brightness(1)'},{transform:`rotateX(${-92*direction}deg)`,filter:'brightness(.3)'}],{duration:duration*.4,easing:'cubic-bezier(.5,.05,.85,.5)',fill:'both'}),
        cell.into.animate([{transform:`rotateX(${90*direction}deg)`,filter:'brightness(.35)',offset:0},{transform:`rotateX(${-12*direction}deg)`,filter:'brightness(1.14)',offset:.65},{transform:`rotateX(${5*direction}deg)`,filter:'brightness(.97)',offset:.84},{transform:'rotateX(0deg)',filter:'brightness(1)',offset:1}],{duration:duration*.6,delay:duration*.4,easing:'linear',fill:'both'})
      ];
      cell.timer=setTimeout(()=>{
        if(epoch!==this.epoch)return;
        this.paint(cell,digit);cell.motions.forEach(a=>a.cancel());cell.motions=[];done();
      },duration);
    }
    move(money,done,duration=300,landing=false){
      const p=parts(money);if(!p)return;
      const positions=this.currentMoney?.currency===p.currency?new Map(this.cells.map(c=>[c.place,c.next??c.digit])):new Map();
      const direction=this.currentMoney&&p.currency===this.currentMoney.currency&&p.amount<this.currentMoney.amount?-1:1;
      this.stopMotion();this.build(p.major,p.minor,p.currency,true,positions);this.currentMoney={amount:p.amount,currency:p.currency};
      if(reduced()||!this.canAnimate){this.cells.forEach(c=>this.paint(c,c.target));this.node.dataset.spinning='false';done();return;}
      const epoch=this.epoch;let remaining=this.cells.length;this.moving=true;
      this.cells.forEach((cell,i)=>{
        const steps=landing?3+i%3:2+i%2;let step=0;
        const run=()=>{
          if(epoch!==this.epoch)return;
          const last=++step===steps,digit=last?cell.target:(cell.digit+direction+10)%10;
          const pace=duration/steps*(.65+.7*(step-1)/Math.max(1,steps-1));
          this.flip(cell,digit,pace,()=>{
            if(epoch!==this.epoch)return;
            if(!last){run();return;}
            if(--remaining===0){this.moving=false;this.node.dataset.spinning='false';done();}
          },direction);
        };
        cell.timer=setTimeout(run,i*(landing?26:9));
      });
    }
    spin(input={},label='Comparing prices'){
      const incoming=Array.isArray(input)?input:[input];
      const offers=incoming.map((row,i)=>{const money=row.money||row;return parts(money)?{...row,money,key:(row.url||String(i))+':'+formatMoney(money)}:null;}).filter(Boolean);
      const valid=new Set(offers.map(o=>o.key));
      this.queue=this.queue.filter(o=>valid.has(o.key));
      this.queue.push(...offers.filter(o=>!this.seen.has(o.key)));
      this.queue=this.queue.slice(-7);this.offers=offers;this.seen=valid;this.label=label;
      this.node.setAttribute('aria-label',label);
      if(this.activeOffer&&!valid.has(this.activeOffer.key)){this.activeOffer=null;this.cancel();}
      const starting=!this.live;this.live=true;this.spinning=true;
      if(!offers.length){
        if(starting||this.cells.length){this.stopMotion();this.cells=[];this.currentMoney=null;this.node.replaceChildren(el('span','fz-one-price-wait','—'));this.node.dataset.spinning='true';this.node.dataset.quote='waiting';this.onQuote(null);}
        return;
      }
      if(starting||(!this.moving&&this.queue.length)){clearTimeout(this.liveTimer);this.play();}
    }
    play(){
      this.liveTimer=0;if(!this.live)return;
      const next=this.queue.shift();
      if(next){this.activeOffer=next;this.idleStep=0;this.onQuote(next);}
      const source=this.activeOffer;if(!source)return;
      let money=source.money,real=true;
      if(!next&&!reduced()){
        // Small excursions around the last REAL quote, then return to it.
        // These transient frames are never announced or logged as store prices.
        this.idleStep++;
        if(this.idleStep%2){
          const p=parts(source.money),factor=10**p.minor.length;
          const delta=Math.max(1,Math.round(p.amount*factor*(.002+((this.idleStep*7)%5)*.001)));
          const sign=this.idleStep%4===1?1:-1;
          money={amount:Math.max(1,Math.round(p.amount*factor)+sign*delta)/factor,currency:p.currency};real=false;
        }
      }
      this.node.dataset.quote=real?'offer':'between';this.node.setAttribute('aria-label',this.label);
      this.move(money,()=>{
        if(!this.live)return;
        this.node.setAttribute('aria-label',real?formatMoney(source.money)+(source.store?' · '+source.store:''):this.label);
        if(reduced()&&!this.queue.length)return;
        this.liveTimer=setTimeout(()=>this.play(),real?300:80);
      },next?260:210);
    }
    land(money,done=()=>{}){
      if(!parts(money)){this.clear();return;}
      this.cancel();this.node.dataset.quote='final';this.node.setAttribute('aria-label',formatMoney(money));
      this.move(money,done,760,true);
    }
  }

  // Two decoded layers avoid white flashes. At most four distinct candidate
  // photos enter the search sequence; a final result always takes precedence.
  class PhotoSequence {
    constructor(first,second,placeholder){this.layers=[first,second];this.placeholder=placeholder;this.active=0;this.epoch=0;this.timer=0;this.fadeTimer=0;this.loadTimer=0;this.used=new Set();this.rows=[];this.source='';this.count=0;this.paused=true;this.loading=false;this.nextAt=0;this.loader=null;
      for(const n of this.layers)n.addEventListener('error',()=>{if(n.dataset.active==='true'){n.hidden=true;this.placeholder.hidden=false;}});
    }
    stop(){this.paused=true;clearTimeout(this.timer);this.timer=0;this.epoch++;this.loading=false;clearTimeout(this.loadTimer);if(this.loader){this.loader.onload=null;this.loader.onerror=null;this.loader=null;}}
    reset(){this.stop();clearTimeout(this.fadeTimer);this.fadeTimer=0;this.used.clear();this.rows=[];this.source='';this.count=0;this.active=0;this.nextAt=0;for(const n of this.layers){n.getAnimations?.().forEach(a=>a.cancel());n.hidden=true;n.removeAttribute('src');n.dataset.active='false';}this.placeholder.hidden=false;}
    swap(source,alt,final=false){
      if(!source||source===this.source)return;
      const epoch=++this.epoch;this.loading=true;clearTimeout(this.loadTimer);
      if(this.loader){this.loader.onload=null;this.loader.onerror=null;}
      const loader=new Image();this.loader=loader;loader.decoding='async';
      const failed=()=>{if(epoch!==this.epoch)return;this.epoch++;clearTimeout(this.loadTimer);loader.onload=null;loader.onerror=null;this.loading=false;this.loader=null;if(final){for(const n of this.layers)n.hidden=true;this.source='';this.placeholder.hidden=false;}else this.schedule();};
      loader.onerror=failed;
      loader.onload=async()=>{
        try{await loader.decode?.();}catch(_){}
        if(epoch!==this.epoch)return;
        clearTimeout(this.loadTimer);this.loading=false;this.loader=null;
        for(const n of this.layers)n.getAnimations?.().forEach(a=>a.cancel());
        const previous=this.layers[this.active],next=this.layers[1-this.active],had=!!this.source;
        next.src=source;next.alt=alt||'';next.hidden=false;next.dataset.active='true';next.dataset.final=String(final);
        previous.dataset.active='false';this.active=1-this.active;this.source=source;this.placeholder.hidden=true;
        clearTimeout(this.fadeTimer);
        if(had&&!reduced()&&next.animate){
          next.animate([{opacity:0,transform:'scale(1.035)'},{opacity:1,transform:'scale(1)'}],{duration:final?950:850,easing:'cubic-bezier(.2,.65,.25,1)'});
          previous.animate([{opacity:1},{opacity:0}],{duration:850,easing:'ease-in-out'});
          this.fadeTimer=setTimeout(()=>{previous.hidden=true;},960);
        }else previous.hidden=true;
        if(!final)this.schedule();
      };
      this.loadTimer=setTimeout(failed,5000);loader.src=source;
    }
    schedule(){
      clearTimeout(this.timer);this.timer=0;
      if(this.paused||this.loading||this.count>=4||reduced())return;
      const available=this.rows.filter(r=>!this.used.has(r.image));if(!available.length)return;
      this.timer=setTimeout(()=>{
        this.timer=0;if(this.paused)return;
        const choices=this.rows.filter(r=>!this.used.has(r.image));if(!choices.length)return;
        // Spread picks across the available pool instead of chasing every event.
        const row=choices[Math.min(choices.length-1,Math.floor(choices.length*this.count/4))];
        this.used.add(row.image);this.count++;this.nextAt=Date.now()+3400;this.swap(row.image,row.title);
      },Math.max(0,this.nextAt-Date.now()));
    }
    preview(rows,reference,alt){
      this.rows=rows.filter(r=>safeURL(r.image));this.paused=false;
      if(!this.source&&!this.loading){
        const first=reference||this.rows[0]?.image;
        if(first){this.used.add(first);if(!reference)this.count++;this.nextAt=Date.now()+3000;this.swap(first,alt||this.rows[0]?.title);}
      }
      this.schedule();
    }
    settle(source,alt){this.stop();this.swap(source,alt,true);}
  }

  class SearchLog {
    constructor(node){this.node=node;this.entries=[];this.seen=new Map();this.limit=7;}
    clear(){this.entries=[];this.seen.clear();this.activeKey='';this.node.replaceChildren();}
    add(key,entry){
      const version=JSON.stringify(entry);if(this.seen.get(key)===version)return;this.seen.set(key,version);
      this.entries.push(entry);if(this.entries.length>200)this.entries.shift();
      const row=el('div','fz-one-log-line');row.dir='ltr';
      row.dataset.key=key;row.dataset.active=String(key===this.activeKey);
      row.append(el('span','fz-one-log-mark',entry.price?'›':'·'),el('bdi','fz-one-log-site',entry.site||''),el('bdi','fz-one-log-product',entry.title||''),el('bdi','fz-one-log-price',entry.price||''));
      this.node.append(row);while(this.node.children.length>this.limit)this.node.firstElementChild.remove();
    }
    highlight(key){this.activeKey=key;for(const row of this.node.children)row.dataset.active=String(row.dataset.key===key);}
    sync(rows){for(const row of rows){const url=safeURL(row.url);if(!url||!parts(row.money))continue;this.add(url,{site:row.store||new URL(url).hostname.replace(/^www\./,''),title:row.title,price:formatMoney(row.money)});}}
  }
  function mount(root){
    const bridge=root.fzRefineBridge,body=root.querySelector('[data-results-body]');
    if(root.dataset.choicePreview!=='true'||!bridge?.choiceRows||!body||root.fzOneChoice||new URLSearchParams(location.search).get('choice')==='off')return;
    root.dataset.choiceMode='one';
    const text=k=>{const lang=(root.dataset.lang||'en').split('-')[0],i=keys.indexOf(k);return i>=0?(COPY[lang]||COPY.en)[i]:(EXTRA[lang]||EXTRA.en)[extraKeys.indexOf(k)]||k;};
    const box=el('section','fz-one');box.hidden=true;box.setAttribute('aria-label','Findzia');body.before(box);
    const heading=el('h2','fz-one-heading'),stage=el('div','fz-one-stage'),aura=el('div','fz-one-aura'),image=el('img','fz-one-image'),imageBack=el('img','fz-one-image'),scan=el('div','fz-one-scan');scan.setAttribute('aria-hidden','true');
    const placeholder=el('span','fz-one-image-placeholder','⌕');placeholder.setAttribute('aria-hidden','true');image.alt='';image.decoding='async';image.hidden=true;
    const shade=el('div','fz-one-shade');shade.setAttribute('aria-hidden','true');
    imageBack.alt='';imageBack.decoding='async';imageBack.hidden=true;
    const photos=new PhotoSequence(image,imageBack,placeholder);
    const badge=el('span','fz-one-badge');stage.append(aura,placeholder,image,imageBack,shade,scan,heading,badge);
    const title=el('h3','fz-one-title'),specs=el('p','fz-one-specs'),price=el('div','fz-one-price');price.setAttribute('role','img');
    const priceSource=el('p','fz-one-price-source');priceSource.hidden=true;
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
    const details=el('div','fz-one-details');details.append(title,specs,price,priceSource,merchant,question,open,retry,logWrap);stage.append(details);
    box.append(stage,actions,live);
    const log=new SearchLog(logLines),reels=new PriceReels(price,row=>{priceSource.hidden=!row;priceSource.textContent=row?((row.store||new URL(row.url).hostname)+' · '+formatMoney(row.money)):'';log.highlight(row?.url||'');});
    let generation=-1,requestId=0,controller=null,requestTimer=0,debounce=0,mediaTimer=0,retryTimer=0,earlyTimer=0,answerTimer=0,doneAt=0,eligibleAt=null,earlyCalls=0,finalRefreshes=0;
    let selected=null,mode='best',answers=[],questionSkipped=false,lastKey='',deferredNoMatchKey='',pending=false,disposed=false,celebrated=false,frozenSource='',autoRetries=0,dialogMode='results',awaitingQuestion=false,usageAnnounced=false;
    const header=root.querySelector('[data-fixed-header]');
    function fit(){
      const viewport=window.visualViewport;if(viewport?.scale>1.2)return;
      const height=viewport?.height||window.innerHeight||720,headerHeight=header?.getBoundingClientRect().height||108;
      box.style.setProperty('--one-room',Math.max(300,Math.floor(height-headerHeight-16))+'px');
      if(!box.hidden&&box.getBoundingClientRect&&stage.getBoundingClientRect){
        const bounds=box.getBoundingClientRect(),picture=stage.getBoundingClientRect();
        const top=Math.max(headerHeight,bounds.top-(viewport?.offsetTop||0));
        const rest=Math.max(0,bounds.height-picture.height);
        const needed=box.dataset.state==='question'?(details.getBoundingClientRect?.().height||0)+120:310;
        const imageHeight=Math.max(310,needed,Math.min(820,Math.floor(height-top-rest-10)));
        box.style.setProperty('--one-image-height',imageHeight+'px');
        stage.style.setProperty('--scan-travel',Math.max(120,imageHeight*.66)+'px');
      }
    }

    function labels(){open.textContent=text('open');retry.textContent=text('retry');cheaper.textContent=text('cheaper');quality.textContent=text('quality');newSearch.textContent=text('newSearch');close.setAttribute('aria-label',text('close'));whyButton.setAttribute('aria-label',text('why'));whyButton.title=text('why');logCaption.textContent=text('log');}
    function cancel(){requestId++;controller?.abort();controller=null;clearTimeout(requestTimer);clearTimeout(retryTimer);clearTimeout(earlyTimer);clearTimeout(mediaTimer);earlyTimer=0;pending=false;}
    function closeDialog(){dialog.close?.();logButton.setAttribute('aria-expanded','false');}
    function reset(){
      cancel();clearTimeout(debounce);debounce=0;clearTimeout(mediaTimer);clearTimeout(answerTimer);photos.reset();reels.clear();log.clear();selected=null;mode='best';answers=[];questionSkipped=false;lastKey='';deferredNoMatchKey='';celebrated=false;doneAt=0;autoRetries=0;frozenSource='';eligibleAt=null;earlyCalls=0;finalRefreshes=0;awaitingQuestion=false;usageAnnounced=false;
      box.hidden=true;box.dataset.state='pending';root.dataset.choiceActive='false';question.replaceChildren();image.hidden=true;image.removeAttribute('src');placeholder.hidden=false;closeDialog();
    }
    function activate(){labels();price.hidden=false;priceSource.hidden=true;box.hidden=false;root.dataset.choiceActive='true';badge.hidden=true;actions.hidden=true;open.hidden=true;retry.hidden=true;merchant.hidden=true;whyButton.hidden=true;question.replaceChildren();logWrap.hidden=false;fit();}
    function freezeImage(rows,c){
      const original=c.kind==='image'&&c.image_base64?('data:'+(c.mime_type||'image/jpeg')+';base64,'+c.image_base64.replace(/^data:[^,]+,/,'')):'';
      if(!frozenSource)frozenSource=original||rows[0]?.image||'';
      photos.preview(rows,original,c.query||c.photoDescription);
    }
    function priceRows(rows){return (bridge.choiceLogRows?.()||rows).filter(r=>safeURL(r.url)&&parts(r.money));}
    function syncLog(rows){
      log.sync(priceRows(rows));logCount.textContent=String(rows.length);logButton.disabled=!rows.length;
      logButton.setAttribute('aria-label',text('results')+' · '+rows.length);logButton.title=text('results');
      if(dialog.open&&dialogMode==='results')renderOffers(rows);
    }
    function pendingView(rows,c){
      activate();box.dataset.state='pending';heading.textContent=text(c.kind==='image'?'checking':'choosing');title.textContent='';specs.textContent='';store.textContent='';shipping.textContent='';
      actions.hidden=false;cheaper.hidden=true;quality.hidden=true;
      freezeImage(rows,c);reels.spin(priceRows(rows),text('comparing'));priceSource.hidden=!reels.activeOffer;
      fit();
    }
    function empty(key){
      photos.stop();
      if(bridge.context().kind==='image'&&frozenSource)photos.settle(frozenSource,'');
      activate();box.dataset.state='empty';box.dataset.emptyReason=key;heading.textContent=text(key);reels.clear();title.textContent='';specs.textContent='';store.textContent='';shipping.textContent='';
      retry.hidden=false;actions.hidden=false;cheaper.hidden=true;quality.hidden=true;whyButton.hidden=true;logWrap.hidden=true;live.textContent=heading.textContent;
    }
    function celebrate(){
      if(celebrated||disposed)return;celebrated=true;box.dataset.state='selected';heading.textContent=text('found');live.textContent=text('found')+' '+title.textContent+' '+(price.getAttribute('aria-label')||'');fit();
      if(reduced())return;
      for(let i=0;i<14;i++){const s=el('i','fz-one-spark');s.setAttribute('aria-hidden','true');const a=i*Math.PI*2/14,r=60+i%4*16;s.style.setProperty('--spark-x',Math.cos(a)*r+'px');s.style.setProperty('--spark-y',Math.sin(a)*r+25+'px');s.style.setProperty('--spark-r',i*37+'deg');stage.append(s);setTimeout(()=>s.remove(),1300);}
    }
    function show(value,row,manual=false){
      const link=safeURL(row.url);if(!link){empty('unavailable');return;}
      selected={value,token:row.token,url:row.url,version:rowVersion(row),manual};activate();box.dataset.state='settling';heading.textContent=text('found');
      photos.settle(row.image,row.title);title.textContent=row.title;title.title=row.title;
      specs.textContent=(row.key_specs||[]).slice(0,2).map(s=>s.value).filter(s=>s&&!row.title.toLowerCase().includes(String(s).toLowerCase())).join(' · ');
      store.textContent=value.store||row.store||new URL(link).hostname.replace(/^www\./,'');store.title=store.textContent;
      shipping.textContent=value.money?.shipping_known?(value.money.shipping===0?text('shippingKnown'):text('shippingKnown')+' · '+formatMoney({amount:value.money.shipping,currency:value.money.currency})):text('shippingUnknown');
      merchant.hidden=false;open.href=link;open.hidden=false;badge.hidden=false;badge.textContent=manual?text('yourChoice'):value.match==='suitable'&&bridge.context().kind==='image'?(root.dataset.lang==='ar'?'أقرب لطلبك':'Closest match'):text('badge');
      actions.hidden=false;cheaper.hidden=false;quality.hidden=false;cheaper.disabled=false;quality.disabled=false;whyButton.hidden=!value.reason;
      reason.textContent=value.reason||'';logWrap.hidden=true;syncLog(candidates());
      if(!usageAnnounced){usageAnnounced=true;root.dispatchEvent(new CustomEvent('fz:usage',{bubbles:true,detail:{type:'visible',generation,count:1,source:manual?'offer-choice':'ai-choice'}}));}
      if(parts(value.money)){reels.land(value.money,celebrate);}
      else{reels.clear();const label=STORE_PRICE[(root.dataset.lang||'en').split('-')[0]]||STORE_PRICE.en;price.append(el('span','fz-one-store-price',label));price.setAttribute('aria-label',label);celebrate();}
      fit();
    }
    function candidates(){const photo=bridge.context().kind==='image';return bridge.choiceRows().filter(r=>r.token&&safeURL(r.url)&&safeURL(r.image)&&(photo||parts(r.money)));}
    function renderOffers(rows=candidates()){
      offerList.replaceChildren();
      rows.forEach((row,i)=>{
        const b=el('button','fz-one-offer-row');b.type='button';b.dir='ltr';b.setAttribute('aria-label',row.title+' · '+(row.store||new URL(row.url).hostname)+' · '+formatMoney(row.money));
        b.setAttribute('aria-pressed',String(selected?.url===row.url));
        const info=el('span','fz-one-offer-info');info.append(el('bdi','fz-one-offer-site',row.store||new URL(row.url).hostname),el('bdi','fz-one-offer-title',row.title));
        b.append(el('span','fz-one-offer-index',String(i+1).padStart(2,'0')),info,el('bdi','fz-one-offer-price',formatMoney(row.money)||(STORE_PRICE[(root.dataset.lang||'en').split('-')[0]]||STORE_PRICE.en)));
        b.addEventListener('click',()=>{
          const current=candidates().find(r=>r.url===row.url&&rowVersion(r)===rowVersion(row));if(!current){renderOffers();return;}
          cancel();closeDialog();celebrated=false;show({url:current.url,token:current.token,store:current.store,money:current.money,reason:'',match:current.match_type},current,true);
        });offerList.append(b);
      });
    }
    function openDialog(mode){dialogMode=mode;dialogTitle.textContent=text(mode==='reason'?'why':'results');reason.hidden=mode!=='reason';offerList.hidden=mode==='reason';if(mode==='results')renderOffers();dialog.showModal?.();logButton.setAttribute('aria-expanded','true');close.focus?.();}
    function queue(){if(!debounce)debounce=setTimeout(()=>{debounce=0;update();},40);}
    function ask(value){
      awaitingQuestion=true;photos.stop();reels.clear();priceSource.hidden=true;box.dataset.state='question';price.hidden=true;heading.textContent=text('clarify');title.textContent=value.question;logWrap.hidden=true;question.replaceChildren();
      const copy=QUESTION_COPY[(root.dataset.lang||'en').split('-')[0]]||QUESTION_COPY.en;
      const intro=el('p','fz-one-question-note',copy[1]),choices=el('div','fz-one-options');
      choices.setAttribute('role','group');choices.setAttribute('aria-label',value.question);
      question.append(intro,choices);
      const answer=(label,button,skip=false)=>{
        if(pending||!awaitingQuestion||answerTimer)return;
        const at=generation;questionSkipped=skip;
        const picked=label.slice(0,80);
        answers=[value.question.slice(0,157-picked.length)+' — '+picked];
        question.querySelectorAll('button').forEach(b=>{b.disabled=true;b.setAttribute('aria-pressed',String(b===button));});
        live.textContent=label;lastKey='';selected=null;earlyCalls=0;
        answerTimer=setTimeout(()=>{answerTimer=0;if(at!==generation||disposed)return;awaitingQuestion=false;queue();},reduced()?0:180);
      };
      for(const label of [...new Set(value.choices||[])].filter(s=>typeof s==='string'&&s.trim()).slice(0,3)){
        const b=el('button','fz-one-answer');b.type='button';b.setAttribute('aria-pressed','false');
        const lines=el('span','fz-one-answer-copy'),caption=el('strong','fz-one-answer-label',label);
        lines.append(caption);
        const detail=value.options?.find(o=>o.label===label)?.detail;
        if(detail)lines.append(el('span','fz-one-answer-detail',detail));
        const arrow=el('span','fz-one-answer-arrow','↗');arrow.setAttribute('aria-hidden','true');b.append(lines,arrow);
        b.addEventListener('click',()=>answer(label,b));choices.append(b);
      }
      const skip=el('button','fz-one-question-skip',copy[0]);skip.type='button';skip.addEventListener('click',()=>answer(copy[0],skip,true));question.append(skip);
      live.textContent=value.question;fit();
    }
    function choiceKey(rows,c){return JSON.stringify([c.generation,c.query,c.kind,c.country,c.lang,c.extra_specs||'',mode,answers,rows.slice(0,48).map(rowVersion).sort()]);}
    function selectionCaption(c){
      if(!selected)return;
      const provisional=c.kind!=='image'&&!!(c.busy||c.media_pending||pending);box.dataset.provisional=String(provisional);
      badge.textContent=selected.manual?text('yourChoice'):provisional?(PROVISIONAL[(root.dataset.lang||'en').split('-')[0]]||PROVISIONAL.en):selected.value.match==='suitable'&&c.kind==='image'?(root.dataset.lang==='ar'?'أقرب لطلبك':'Closest match'):text('badge');
    }
    async function choose(rows,c){
      rows=rows.slice(0,48);
      const key=choiceKey(rows,c);
      if(key===lastKey||pending)return;lastKey=key;pending=true;
      if(c.busy)earlyCalls++;
      else if(c.kind==='image')finalRefreshes++;
      if(!selected)pendingView(rows,c);else selectionCaption(c);
      log.add('decision',{site:'AI',title:text('deciding')});
      let followUp=false;
      const id=++requestId,ctl=new AbortController();controller=ctl;
      const timeout=new Promise((_,reject)=>{requestTimer=setTimeout(()=>{ctl.abort();reject(new Error('timeout'));},24000);});
      try{
        const work=(async()=>{
          const response=await window.FindziaBillingFetch(root,bridge.api.replace(/\/$/,'')+'/api/choice',{
            method:'POST',signal:ctl.signal,headers:{'Content-Type':'application/json'},credentials:'omit',
            body:JSON.stringify({query:c.query||c.photoDescription||'',kind:c.kind,country:c.country,lang:c.lang,extra_specs:c.extra_specs||'',mode,answers,skip_question:questionSkipped,offer_tokens:rows.map(r=>r.token),
              ...(c.kind==='image'?{image_base64:c.image_base64,offer_images:rows.map(r=>({token:r.token,image:r.vision_image,media_token:r.media_token}))}:{})})
          });const value=await response.json();if(!response.ok||!value.ok){const error=new Error('unavailable');error.retryable=response.status>=500;throw error;}return value;
        })();
        const value=await Promise.race([work,timeout]);
        if(disposed||id!==requestId||bridge.context().generation!==c.generation)return;
        autoRetries=0;
        const now=bridge.context(),currentRows=candidates();
        if(value.status!=='selected'&&(now.busy||(choiceKey(currentRows,now)!==key&&(c.kind!=='image'||finalRefreshes<2)))){
          // Partial evidence must not flash an error or a premature question.
          lastKey='';followUp=!now.busy;return;
        }
        if(value.status==='question'){
          if(selected)return;
          ask(value);return;
        }
        if(value.status==='unavailable'){
          if(!selected)empty('unavailable');return;
        }
        if(value.status!=='selected'){
          // Images may finish after the bounded first decision. Do not declare
          // no match until those offers have had their chance to be reviewed.
          if(c.kind==='image'&&now.media_pending&&Date.now()-doneAt<4500){
            deferredNoMatchKey=key;clearTimeout(mediaTimer);mediaTimer=setTimeout(update,250);return;
          }
          if(!selected)empty('noMatch');return;
        }
        if(c.kind==='image'&&value.visual_verified!==true){const error=new Error('visual_review_required');error.retryable=false;throw error;}
        const current=currentRows.find(r=>r.url===value.url&&rowVersion(r)===rowVersion(rows.find(o=>o.token===value.token)||{}));
        if(!current){lastKey='';followUp=true;return;}
        if(selected?.version===rowVersion(current)){
          selected.value=value;selected.token=current.token;reason.textContent=value.reason||'';whyButton.hidden=!value.reason;
        }else{celebrated=false;show(value,current);}
        followUp=true;
      }catch(error){
        if(id!==requestId||disposed||bridge.context().generation!==c.generation)return;
        if(selected){selectionCaption(bridge.context());return;}
        if(bridge.context().busy){lastKey='';return;}
        if(autoRetries<1&&error.retryable!==false){autoRetries++;lastKey='';retryTimer=setTimeout(()=>{retryTimer=0;if(id===requestId)update();},650);}
        else empty('unavailable');
      }finally{
        if(id===requestId){clearTimeout(requestTimer);controller=null;pending=false;selectionCaption(bridge.context());if(followUp)queue();}
      }
    }
    function update(){
      if(disposed)return;const c=bridge.context();if(generation!==c.generation){reset();generation=c.generation;}
      if(root.dataset.homeState==='empty'&&!c.busy){reset();return;}
      const rows=candidates();syncLog(rows);
      if(!log.entries.length&&(c.busy||rows.length))log.add('start',{site:'>',title:text('searching')});
      if(selected){
        const row=rows.find(r=>rowVersion(r)===selected.version);
        if(row){
          selected.token=row.token;selectionCaption(c);
          // One photo search reveals one settled decision. New arrivals stay
          // in the offers list; removal or a real correction still invalidates it.
          if(selected.manual||c.kind==='image'||pending||c.busy||retryTimer)return;
          // Refine once at stream completion, then once after outstanding media.
          // Keep the usable result visible during this background decision.
          if(choiceKey(rows,c)!==lastKey&&(!c.media_pending||finalRefreshes<1)){
            finalRefreshes++;choose(rows,c);
          }
          return;
        }
        cancel();selected=null;lastKey='';celebrated=false;autoRetries=0;earlyCalls=0;eligibleAt=null;reels.clear();
      }
      if(awaitingQuestion)return;
      if(!c.busy&&!pending&&box.dataset.state==='empty'&&lastKey===choiceKey(rows,c))return;
      if(c.kind==='image'&&!c.busy&&!pending&&box.dataset.state==='empty'&&finalRefreshes>=2)return;
      if(c.busy||rows.length||pending)pendingView(rows,c);
      if(pending||retryTimer)return;
      if(c.kind==='image'){
        if(!c.busy&&!doneAt)doneAt=Date.now();
        if(deferredNoMatchKey===choiceKey(rows,c)){
          if(c.busy||(c.media_pending&&Date.now()-doneAt<4500)){clearTimeout(mediaTimer);mediaTimer=setTimeout(update,250);return;}
          empty('noMatch');return;
        }
        deferredNoMatchKey='';
      }
      if(rows.length){
        if(eligibleAt===null)eligibleAt=Date.now();
        // A fixed short collection window cannot be postponed by progress events.
        if(c.busy){
          if(earlyCalls)return;
          const wait=(c.kind==='image'?1200:220)-(Date.now()-eligibleAt);
          if(wait>0){if(!earlyTimer)earlyTimer=setTimeout(()=>{earlyTimer=0;update();},wait);return;}
        }
        clearTimeout(earlyTimer);earlyTimer=0;choose(rows,c);return;
      }
      if(c.busy)return;
      if(!doneAt)doneAt=Date.now();
      // Wait for an image only when there is no ready, reviewed offer at all.
      if(c.media_pending&&Date.now()-doneAt<4500){pendingView(rows,c);clearTimeout(mediaTimer);mediaTimer=setTimeout(update,200);return;}
      if(c.query||c.kind==='image')empty('noMatch');
    }

    function preference(value){cancel();mode=value;selected=null;lastKey='';celebrated=false;autoRetries=0;earlyCalls=0;finalRefreshes=0;awaitingQuestion=false;queue();}
    cheaper.addEventListener('click',()=>preference('cheaper'));quality.addEventListener('click',()=>preference('quality'));
    retry.addEventListener('click',()=>{if(box.dataset.emptyReason==='noMatch'&&bridge.retryChoiceSearch?.())return;lastKey='';autoRetries=0;earlyCalls=0;finalRefreshes=0;awaitingQuestion=false;queue();});newSearch.addEventListener('click',()=>bridge.newSearch());
    logButton.addEventListener('click',()=>openDialog('results'));whyButton.addEventListener('click',()=>openDialog('reason'));close.addEventListener('click',closeDialog);
    dialog.addEventListener('close',()=>{logButton.setAttribute('aria-expanded','false');});
    dialog.addEventListener('click',event=>{if(event.target===dialog){const b=dialog.getBoundingClientRect();if(event.clientX<b.left||event.clientX>b.right||event.clientY<b.top||event.clientY>b.bottom)closeDialog();}});
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
    const langObserver=new MutationObserver(()=>{cancel();selected=null;lastKey='';celebrated=false;autoRetries=0;earlyCalls=0;awaitingQuestion=false;log.clear();queue();});langObserver.observe(root,{attributes:true,attributeFilter:['data-lang']});
    const sizeObserver=window.ResizeObserver?new ResizeObserver(fit):null;if(header)sizeObserver?.observe(header);sizeObserver?.observe(actions);sizeObserver?.observe(details);
    window.addEventListener?.('resize',fit);window.visualViewport?.addEventListener('resize',fit);
    document.fonts?.ready?.then(()=>{if(!disposed)fit();});
    function destroy(){disposed=true;reset();langObserver.disconnect();sizeObserver?.disconnect();for(const name of ['fz:search-state','fz:choice-results'])root.removeEventListener(name,queue);root.removeEventListener('fz:search-progress',progressEvent);root.removeEventListener('fz:search-reset',resetEvent);window.removeEventListener?.('resize',fit);window.visualViewport?.removeEventListener('resize',fit);box.remove();dialog.remove();delete root.dataset.choiceMode;delete root.dataset.choiceActive;}
    document.addEventListener('shopify:section:unload',function unload(ev){if(ev.target?.contains(root)){destroy();document.removeEventListener('shopify:section:unload',unload);}});
    root.fzOneChoice={update,destroy,release:'157.0.12'};labels();queue();
  }
  window.FindziaChoice={mount,PriceReels,PhotoSequence,SearchLog,moneyParts:parts};
  const start=()=>document.querySelectorAll('.fz-home').forEach(mount);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
  document.addEventListener('shopify:section:load',start);
})();
