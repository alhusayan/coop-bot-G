/* FINDZIA_CHOICE_RELEASE=157.0.0 — one real, signed-offer AI decision. */
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
  function parts(money){
    const amount=Number(money?.amount),currency=String(money?.currency||'');
    if(!Number.isFinite(amount)||amount<=0||!/^[A-Z]{3}$/.test(currency))return null;
    try{const p=new Intl.NumberFormat('en-US',{style:'currency',currency}).formatToParts(amount);
      return {major:p.filter(p=>p.type==='integer'||p.type==='group').map(p=>p.value).join(''),minor:p.find(p=>p.type==='fraction')?.value||'',currency,amount};
    }catch(_){return null;}
  }
  class PriceReels {
    constructor(node){this.node=node;this.reels=[];this.animations=[];this.timers=[];this.shape='';this.reduced=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;}
    cancel(){this.animations.forEach(a=>a.cancel());this.animations=[];this.timers.forEach(clearTimeout);this.timers=[];}
    clear(){this.cancel();this.node.replaceChildren();this.shape='';this.reels=[];}
    draw(money){
      const p=parts(money);if(!p)return false;
      this.cancel();this.node.replaceChildren();this.reels=[];
      this.shape=p.major.replace(/\d/g,'#')+'.'+p.minor.length;
      const number=el('span','fz-one-number');number.dir='ltr';number.setAttribute('aria-hidden','true');
      const widthUnits=p.major.replace(/\D/g,'').length*.64+(p.major.match(/,/g)||[]).length*.2+p.minor.length*.32+(p.minor? .1:0);
      if(widthUnits>4.7)number.style.fontSize=`clamp(18px,${Math.min(10,68/widthUnits)}vw,${Math.min(62,360/widthUnits)}px)`;
      const append=(text,fils)=>{
        for(const c of text){
          if(!/\d/.test(c)){number.append(el('span','fz-one-separator',c));continue;}
          const reel=el('span','fz-one-reel'+(fils?' fz-one-fils':'')),track=el('span','fz-one-track');
          for(let i=0;i<120;i++)track.append(el('span','fz-one-digit',String(i%10)));
          const start=Number(c);track.style.transform=`translateY(${-start*1.16}em)`;
          reel.append(track);number.append(reel);this.reels.push({reel,track,start});
        }
      };
      append(p.major,false);
      if(p.minor){number.append(el('span','fz-one-point','.'));append(p.minor,true);}
      this.node.append(number,el('span','fz-one-currency',p.currency==='KWD'&&this.node.closest('[data-lang="ar"]')?'د.ك':p.currency));
      this.node.setAttribute('aria-label',p.amount+' '+p.currency);return true;
    }
    spin(money){
      if(!this.draw(money)||this.reduced())return;
      this.reels.forEach((r,i)=>{
        r.duration=410+i*65;r.reel.classList.add('fz-one-spinning');
        r.animation=r.track.animate([{transform:`translateY(${-r.start*1.16}em)`},{transform:`translateY(${-(r.start+10)*1.16}em)`}],{duration:r.duration,iterations:Infinity,easing:'linear'});
        this.animations.push(r.animation);
      });
      this.node.setAttribute('aria-label','…');
    }
    land(money,done){
      const p=parts(money);if(!p){this.clear();done();return;}
      const shape=p.major.replace(/\d/g,'#')+'.'+p.minor.length;
      if(this.shape!==shape)this.draw(money);
      if(this.reduced()){this.draw(money);done();return;}
      const positions=this.reels.map(r=>r.start+(r.animation?(Number(r.animation.currentTime)||0)%r.duration/r.duration*10:0));
      this.cancel();const digits=(p.major+p.minor).replace(/\D/g,'').split('').map(Number);
      this.reels.forEach((r,i)=>{
        const start=positions[i],end=Math.ceil(start/10)*10+20+digits[i],duration=440+i*85;
        const transform=`translateY(${-end*1.16}em)`;
        const a=r.track.animate([{transform:`translateY(${-start*1.16}em)`},{transform}],{duration,fill:'forwards',easing:'cubic-bezier(.12,.6,.2,1)'});this.animations.push(a);
        this.timers.push(setTimeout(()=>{r.track.style.transform=transform;a.cancel();r.reel.classList.remove('fz-one-spinning');r.reel.classList.add('fz-one-landed');if(i===this.reels.length-1)done();},duration));
      });
      const currency=this.node.querySelector('.fz-one-currency');if(currency)currency.textContent=p.currency==='KWD'&&this.node.closest('[data-lang="ar"]')?'د.ك':p.currency;
      this.node.setAttribute('aria-label',p.amount+' '+p.currency);
    }
  }
  function mount(root){
    const bridge=root.fzRefineBridge,body=root.querySelector('[data-results-body]');
    if(!bridge?.choiceRows||!body||root.fzOneChoice||new URLSearchParams(location.search).get('choice')==='off')return;
    root.dataset.choiceMode='one';
    const text=k=>{const code=(root.dataset.lang||'en').split('-')[0];return(COPY[code]||COPY.en)[keys.indexOf(k)]||k;};
    const box=el('section','fz-one');box.hidden=true;box.setAttribute('aria-label','Findzia');body.before(box);
    const heading=el('h2','fz-one-heading'),stage=el('div','fz-one-stage'),aura=el('div','fz-one-aura'),image=el('img','fz-one-image');
    image.alt='';image.decoding='async';stage.append(aura,image);image.hidden=true;
    const badge=el('span','fz-one-badge'),title=el('h3','fz-one-title'),specs=el('p','fz-one-specs'),price=el('div','fz-one-price');price.setAttribute('role','img');
    const store=el('p','fz-one-store'),shipping=el('p','fz-one-shipping'),saving=el('p','fz-one-saving'),question=el('div','fz-one-question');
    const open=el('a','fz-one-open');open.target='_blank';open.rel='noopener noreferrer';open.hidden=true;
    const retry=el('button','fz-one-open');retry.type='button';retry.hidden=true;
    const actions=el('div','fz-one-actions'),cheaper=el('button','fz-one-small'),quality=el('button','fz-one-small'),newSearch=el('button','fz-one-small');
    [cheaper,quality,newSearch].forEach(b=>b.type='button');actions.append(cheaper,quality,newSearch);
    const detail=el('details','fz-one-details'),summary=el('summary'),reason=el('p','fz-one-reason');detail.append(summary,reason);detail.hidden=true;
    const live=el('p','fz-one-sr');live.setAttribute('role','status');live.setAttribute('aria-live','polite');
    box.append(heading,stage,badge,title,specs,price,store,shipping,saving,question,open,retry,actions,detail,live);
    const reels=new PriceReels(price);
    let generation=-1,requestId=0,controller=null,requestTimer=0,debounce=0,mediaTimer=0,doneAt=0;
    let selected=null,mode='best',answers=[],lastKey='',pending=false,spinning=false,disposed=false,celebrated=false;
    function labels(){badge.textContent=text('badge');open.textContent=text('open');retry.textContent=text('retry');cheaper.textContent=text('cheaper');quality.textContent=text('quality');newSearch.textContent=text('newSearch');summary.textContent=text('why');}
    function cancel(){requestId++;controller?.abort();controller=null;clearTimeout(requestTimer);pending=false;}
    function reset(){cancel();clearTimeout(debounce);clearTimeout(mediaTimer);reels.clear();selected=null;mode='best';answers=[];lastKey='';spinning=false;celebrated=false;doneAt=0;box.hidden=true;box.dataset.state='pending';root.dataset.choiceActive='false';question.replaceChildren();image.hidden=true;image.removeAttribute('src');detail.open=false;}
    function activate(){labels();box.hidden=false;root.dataset.choiceActive='true';badge.hidden=true;actions.hidden=true;open.hidden=true;retry.hidden=true;detail.hidden=true;question.replaceChildren();}
    function pendingView(rows,c){
      activate();box.dataset.state='pending';heading.textContent=text('choosing');store.textContent='';shipping.textContent='';saving.textContent='';
      title.textContent=rows[0]?.title||c.photoDescription||c.query||'';specs.textContent='';
      const source=rows[0]?.image||(c.kind==='image'&&c.image_base64?('data:'+(c.mime_type||'image/jpeg')+';base64,'+c.image_base64.replace(/^data:[^,]+,/,'')):null);
      if(source){image.src=source;image.hidden=false;image.alt=title.textContent;}
      if(!spinning&&rows[0]?.money){reels.spin(rows[0].money);spinning=true;}
    }
    function empty(key){activate();box.dataset.state='empty';heading.textContent=text(key);reels.clear();spinning=false;price.removeAttribute('aria-label');title.textContent='';specs.textContent='';store.textContent='';shipping.textContent='';saving.textContent='';image.hidden=true;retry.hidden=key==='noMatch';actions.hidden=false;cheaper.hidden=true;quality.hidden=true;live.textContent=heading.textContent;}
    function celebrate(){
      if(celebrated||disposed)return;celebrated=true;box.dataset.state='selected';heading.textContent=text('found');live.textContent=text('found')+' '+title.textContent+' '+price.getAttribute('aria-label');
      if(matchMedia('(prefers-reduced-motion: reduce)').matches)return;
      for(let i=0;i<18;i++){
        const s=el('i','fz-one-spark');s.setAttribute('aria-hidden','true');const a=i*Math.PI*2/18,r=65+i%4*18;
        s.style.setProperty('--spark-x',Math.cos(a)*r+'px');s.style.setProperty('--spark-y',Math.sin(a)*r+30+'px');s.style.setProperty('--spark-r',i*37+'deg');stage.append(s);setTimeout(()=>s.remove(),1300);
      }
    }
    function show(value,row){
      selected={value,token:row.token,url:row.url};activate();box.dataset.state='settling';heading.textContent=text('found');
      image.src=row.image;image.hidden=false;image.alt=row.title;title.textContent=row.title;
      specs.textContent=(row.key_specs||[]).slice(0,3).map(s=>s.value).filter(Boolean).join(' · ');
      store.textContent=value.store||row.store||new URL(row.url).hostname.replace(/^www\./,'');
      shipping.textContent=value.money.shipping_known?(value.money.shipping===0?text('shippingKnown'):text('shippingKnown')+' · '+new Intl.NumberFormat(root.dataset.lang||'en',{style:'currency',currency:value.money.currency}).format(value.money.shipping)):text('shippingUnknown');
      // The headline is the item price; known shipping is shown separately.
      saving.textContent='';if(value.savings?.amount>0){saving.textContent=text('saving')+' '+new Intl.NumberFormat(root.dataset.lang||'en',{style:'currency',currency:value.savings.currency}).format(value.savings.amount);saving.title=value.savings.basis==='item_and_shipping'?text('shippingKnown'):text('shippingUnknown');}
      const link=safeURL(value.url);if(!link){empty('unavailable');return;}
      open.href=link;open.hidden=false;badge.hidden=false;actions.hidden=false;cheaper.hidden=false;quality.hidden=false;cheaper.disabled=false;quality.disabled=false;
      reason.textContent=value.reason||'';detail.hidden=!value.reason;
      root.dispatchEvent(new CustomEvent('fz:usage',{bubbles:true,detail:{type:'visible',generation,count:1,source:'ai-choice'}}));
      reels.land(value.money,celebrate);spinning=false;
    }
    function candidates(){return bridge.choiceRows().filter(r=>r.token&&safeURL(r.url)&&safeURL(r.image)&&parts(r.money)).slice(0,48);}
    function queue(){clearTimeout(debounce);debounce=setTimeout(update,100);}
    async function choose(rows,c){
      const key=JSON.stringify([c.generation,c.query,c.country,c.lang,mode,answers,rows.map(r=>r.token)]);
      if(key===lastKey||pending)return;lastKey=key;pending=true;activate();heading.textContent=text('choosing');
      if(!spinning&&rows[0]){reels.spin(rows[0].money);spinning=true;}
      const id=++requestId,ctl=new AbortController();controller=ctl;
      let onAbort;
      const aborted=new Promise((_,reject)=>{onAbort=()=>reject(new Error('aborted'));ctl.signal.addEventListener('abort',onAbort,{once:true});});
      const timeout=new Promise((_,reject)=>{requestTimer=setTimeout(()=>{ctl.abort();reject(new Error('timeout'));},12000);});
      try{
        const work=(async()=>{
          const response=await window.FindziaBillingFetch(root,bridge.api.replace(/\/$/,'')+'/api/choice',{
            method:'POST',signal:ctl.signal,headers:{'Content-Type':'application/json'},credentials:'omit',
            body:JSON.stringify({query:c.query||c.photoDescription||'',kind:c.kind,country:c.country,lang:c.lang,extra_specs:c.extra_specs||'',mode,answers,offer_tokens:rows.map(r=>r.token)})
          });const value=await response.json();if(!response.ok||!value.ok)throw new Error('unavailable');return value;
        })();
        const value=await Promise.race([work,timeout,aborted]);
        if(disposed||id!==requestId||bridge.context().generation!==c.generation)return;
        if(value.status==='question'){
          reels.clear();spinning=false;heading.textContent=text('clarify');title.textContent=value.question;specs.textContent='';store.textContent='';shipping.textContent='';saving.textContent='';
          for(const label of (value.choices||[]).slice(0,3)){const b=el('button','fz-one-answer',label);b.type='button';b.addEventListener('click',()=>{if(pending)return;answers=[String(label).slice(0,160)];lastKey='';selected=null;queue();});question.append(b);}return;
        }
        if(value.status!=='selected'){empty('noMatch');return;}
        const current=candidates().find(r=>r.token===value.token&&r.url===value.url);
        if(!current){lastKey='';queue();return;}
        celebrated=false;show(value,current);
      }catch(_){if(id===requestId&&!disposed)empty('unavailable');}
      finally{ctl.signal.removeEventListener('abort',onAbort);if(id===requestId){clearTimeout(requestTimer);controller=null;pending=false;}}
    }
    function update(){
      if(disposed)return;const c=bridge.context();if(generation!==c.generation){reset();generation=c.generation;}
      if(root.dataset.homeState==='empty'&&!c.busy){reset();return;}
      const rows=candidates();
      // Removal, corrected prices and audit changes invalidate a selected offer.
      if(selected){const row=rows.find(r=>r.token===selected.token&&r.url===selected.url);if(row){labels();return;}selected=null;lastKey='';celebrated=false;reels.clear();spinning=false;}
      if(c.busy){if(!pending)pendingView(rows,c);return;}
      if(!doneAt)doneAt=Date.now();
      if(c.media_pending&&Date.now()-doneAt<4500){pendingView(rows,c);clearTimeout(mediaTimer);mediaTimer=setTimeout(update,300);return;}
      if(!rows.length){if(c.query||c.kind==='image')empty('noMatch');return;}
      choose(rows,c);
    }
    function preference(value){if(pending)return;cancel();mode=value;selected=null;lastKey='';celebrated=false;queue();}
    cheaper.addEventListener('click',()=>preference('cheaper'));quality.addEventListener('click',()=>preference('quality'));
    retry.addEventListener('click',()=>{lastKey='';queue();});newSearch.addEventListener('click',()=>bridge.newSearch());
    image.addEventListener('error',()=>{image.hidden=true;if(selected){selected=null;empty('unavailable');}});
    const resetEvent=()=>{reset();generation=-1;queue();};
    for(const name of ['fz:search-state','fz:search-progress','fz:choice-results'])root.addEventListener(name,queue);
    root.addEventListener('fz:search-reset',resetEvent);
    const langObserver=new MutationObserver(()=>{cancel();selected=null;lastKey='';celebrated=false;queue();});langObserver.observe(root,{attributes:true,attributeFilter:['data-lang']});
    function destroy(){disposed=true;reset();langObserver.disconnect();for(const name of ['fz:search-state','fz:search-progress','fz:choice-results'])root.removeEventListener(name,queue);root.removeEventListener('fz:search-reset',resetEvent);box.remove();delete root.dataset.choiceMode;delete root.dataset.choiceActive;}
    document.addEventListener('shopify:section:unload',function unload(ev){if(ev.target?.contains(root)){destroy();document.removeEventListener('shopify:section:unload',unload);}});
    root.fzOneChoice={update,destroy,release:'157.0.0'};labels();queue();
  }
  window.FindziaChoice={mount,PriceReels,moneyParts:parts};
  const start=()=>document.querySelectorAll('.fz-home').forEach(mount);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
  document.addEventListener('shopify:section:load',start);
})();
