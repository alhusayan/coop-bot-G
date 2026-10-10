/* Live catalog results belong only to the active search: no storage, image
 * proxy, download, AI audit, price-history ingestion or saved-result reuse. */
(() => {
  'use strict';
  const copy = {
    en:['More stores · Shopify','Shipping availability is based on the catalog. Confirm delivery, final price and product options at the store.','Visually similar products; exact match is not verified.'],
    ar:['متاجر إضافية · Shopify','توفر الشحن حسب الكتالوج. تأكد من التوصيل والسعر النهائي وخيارات المنتج عند المتجر.','منتجات متشابهة بالصورة؛ التطابق الدقيق غير مؤكد.'],
    fr:['Autres boutiques · Shopify','Livraison selon le catalogue. Vérifiez la livraison, le prix final et les options auprès de la boutique.','Produits visuellement similaires ; correspondance exacte non vérifiée.'],
    de:['Weitere Shops · Shopify','Versand laut Katalog. Lieferung, Endpreis und Produktoptionen im Shop prüfen.','Optisch ähnliche Produkte; exakte Übereinstimmung nicht geprüft.'],
    es:['Más tiendas · Shopify','Envío según el catálogo. Confirma entrega, precio final y opciones en la tienda.','Productos visualmente similares; coincidencia exacta sin verificar.'],
    it:['Altri negozi · Shopify','Spedizione secondo il catalogo. Verifica consegna, prezzo finale e opzioni nel negozio.','Prodotti visivamente simili; corrispondenza esatta non verificata.'],
    pt:['Mais lojas · Shopify','Envio conforme o catálogo. Confirme entrega, preço final e opções na loja.','Produtos visualmente semelhantes; correspondência exata não verificada.'],
    tr:['Diğer mağazalar · Shopify','Kataloğa göre gönderim. Teslimatı, son fiyatı ve ürün seçeneklerini mağazada doğrulayın.','Görsel olarak benzer ürünler; tam eşleşme doğrulanmadı.'],
    zh:['更多商店 · Shopify','配送信息来自目录。请在商店确认配送、最终价格及商品选项。','外观相似的商品；尚未确认完全匹配。'],
    ja:['その他のストア · Shopify','配送情報はカタログに基づきます。配送、最終価格、商品オプションはストアでご確認ください。','見た目が似ている商品です。完全一致は未確認です。'],
    ko:['더 많은 스토어 · Shopify','배송 정보는 카탈로그 기준입니다. 배송, 최종 가격 및 상품 옵션은 스토어에서 확인하세요.','시각적으로 유사한 상품이며 정확한 일치는 확인되지 않았습니다.'],
    ru:['Другие магазины · Shopify','Доставка по данным каталога. Уточните доставку, итоговую цену и варианты товара в магазине.','Внешне похожие товары; точное совпадение не подтверждено.'],
    hi:['अन्य स्टोर · Shopify','शिपिंग की जानकारी कैटलॉग के अनुसार है। स्टोर पर डिलीवरी, अंतिम कीमत और उत्पाद विकल्प जाँचें।','दिखने में समान उत्पाद; सटीक मिलान सत्यापित नहीं है।'],
    ur:['مزید اسٹورز · Shopify','شپنگ کی معلومات کیٹلاگ کے مطابق ہیں۔ اسٹور پر ترسیل، حتمی قیمت اور مصنوعات کے اختیارات کی تصدیق کریں۔','دیکھنے میں ملتی جلتی مصنوعات؛ مکمل مماثلت کی تصدیق نہیں ہوئی۔'],
    id:['Toko lainnya · Shopify','Pengiriman berdasarkan katalog. Pastikan pengiriman, harga akhir, dan opsi produk di toko.','Produk yang mirip secara visual; kecocokan persis belum diverifikasi.'],
    ms:['Kedai lain · Shopify','Penghantaran mengikut katalog. Sahkan penghantaran, harga akhir dan pilihan produk di kedai.','Produk yang serupa secara visual; padanan tepat belum disahkan.']
  };
  const unknown = {ar:'بلد المتجر غير مؤكد',en:'Store country unconfirmed',fr:'Pays du vendeur non confirmé',de:'Händlerland unbestätigt',es:'País de la tienda sin confirmar',it:'Paese del negozio non confermato',pt:'País da loja não confirmado',tr:'Mağazanın ülkesi doğrulanmadı',zh:'商店所在国家未确认',ja:'ストアの国は未確認',ko:'스토어 국가 미확인',ru:'Страна магазина не подтверждена',hi:'स्टोर के देश की पुष्टि नहीं हुई',ur:'اسٹور کے ملک کی تصدیق نہیں ہوئی',id:'Negara toko belum dikonfirmasi',ms:'Negara kedai belum disahkan'};
  const shipping={ar:'التوصيل والسعر النهائي عند المتجر',en:'Confirm delivery and final price at store',fr:'Livraison et prix final à confirmer en boutique',de:'Lieferung und Endpreis im Shop prüfen',es:'Confirma entrega y precio final en la tienda',it:'Conferma consegna e prezzo finale nel negozio',pt:'Confirme entrega e preço final na loja',tr:'Teslimatı ve son fiyatı mağazada doğrulayın',zh:'请在商店确认配送与最终价格',ja:'配送と最終価格はストアで確認',ko:'배송 및 최종 가격은 스토어에서 확인',ru:'Уточните доставку и итоговую цену в магазине',hi:'स्टोर पर डिलीवरी और अंतिम कीमत जाँचें',ur:'اسٹور پر ترسیل اور حتمی قیمت کی تصدیق کریں',id:'Pastikan pengiriman dan harga akhir di toko',ms:'Sahkan penghantaran dan harga akhir di kedai'};
  const states = new WeakMap();
  const photoGroupCopy = {
    ar:['الأقرب لصورتك','خيارات مشابهة','بحث بصري بواسطة Google Lens'],
    en:['Closest to your photo','Similar options','Visual search powered by Google Lens'],
    fr:['Les plus proches de votre photo','Options similaires','Recherche visuelle avec Google Lens'],
    de:['Am ähnlichsten zu deinem Foto','Ähnliche Optionen','Visuelle Suche mit Google Lens'],
    es:['Lo más parecido a tu foto','Opciones similares','Búsqueda visual con Google Lens'],
    it:['I più simili alla tua foto','Opzioni simili','Ricerca visiva con Google Lens'],
    pt:['Os mais próximos da sua foto','Opções semelhantes','Pesquisa visual com Google Lens'],
    tr:['Fotoğrafına en yakın olanlar','Benzer seçenekler','Google Lens ile görsel arama'],
    zh:['最接近你的照片','相似选项','由 Google Lens 提供视觉搜索'],
    ja:['写真に最も近い商品','似ている商品','Google Lens による画像検索'],
    ko:['사진과 가장 비슷한 상품','비슷한 상품','Google Lens 이미지 검색'],
    ru:['Самые похожие на ваше фото','Похожие варианты','Визуальный поиск с Google Lens'],
    hi:['आपकी फ़ोटो से सबसे मिलते-जुलते','मिलते-जुलते विकल्प','Google Lens से विज़ुअल खोज'],
    ur:['آپ کی تصویر سے قریب ترین','ملتے جلتے اختیارات','Google Lens کے ذریعے تصویری تلاش'],
    id:['Paling mirip dengan fotomu','Pilihan serupa','Penelusuran visual dengan Google Lens'],
    ms:['Paling hampir dengan foto anda','Pilihan serupa','Carian visual dengan Google Lens']
  };
  function photoCopy(language){return photoGroupCopy[language]||photoGroupCopy.en;}
  function isLens(row){return row.source!=='shopify_catalog'&&(row.source==='google_lens'||Array.isArray(row.retrieval_sources)&&row.retrieval_sources.includes('google_lens'));}
  function compareLens(a,b,compare){
    const rank=row=>row.market_scope==='local'?0:row.market_scope==='global'?1:2;
    return rank(a)-rank(b)||compare(a,b);
  }
  function photoGroups(rows,sort,compare,isSocial){
    const groups=[{id:'lens',items:[]},{id:'photo_similar',items:[]},{id:'social',items:[]}];
    for(const row of rows)groups[isSocial(row)?2:isLens(row)?0:1].items.push(row);
    if(sort==='relevance')groups[0].items.sort((a,b)=>compareLens(a,b,compare));
    return groups.filter(group=>group.items.length);
  }
  const similar = {ar:'شبيه',en:'Similar',fr:'Similaire',de:'Ähnlich',es:'Similar',it:'Simile',pt:'Semelhante',tr:'Benzer',zh:'相似',ja:'類似',ko:'유사',ru:'Похожее',hi:'समान',ur:'مشابہ',id:'Serupa',ms:'Serupa'};
  function lang(root){return (root.fzRefineBridge?.context()?.lang||document.documentElement.lang||'en').split('-')[0];}
  function unknownLabel(root){return unknown[lang(root)]||unknown.en;}
  function displayMarket(row,country){
    const out={...row};
    // Legacy prices, search lanes and locale paths are not origin evidence.
    const proof=row.market_policy==='merchant-evidence-v2'&&
      ['shopify_origin_filter','registered_storefront','country_domain'].includes(row.merchant_country_evidence);
    const origin=proof?String(row.merchant_country||'').toUpperCase():'';
    const valid=/^[A-Z]{2}$/.test(origin);
    out.market_scope=valid?(origin===String(country).toUpperCase()?'local':'global'):'unknown';
    out.market=out.market_scope;out.country=valid?origin.toLowerCase():'';
    out.market_country=out.country;out.merchant_country=valid?origin:null;
    out.flag=valid?Array.from(origin,c=>String.fromCodePoint(127397+c.charCodeAt(0))).join(''):'';
    return out;
  }
  function labels(root,row,isSimilar=false){
    // Keep the price and merchant prominent. Shared delivery/match guidance is
    // shown once above the results, not repeated on every mobile card.
    const parts=[];
    if(row.source==='shopify_catalog')parts.push('Shopify');
    if(isSimilar||row.match_type==='visual_similarity')parts.push(similar[lang(root)]||similar.en);
    return parts.length?[parts.join(' · ')]:[];
  }
  function sameOffer(a,b){
    const left=key(a.url),right=key(b.url);if(left===right)return true;
    if(!left||!right)return false;
    const x=new URL(left),y=new URL(right),xVariant=x.searchParams.get('variant'),yVariant=y.searchParams.get('variant');
    if(xVariant&&yVariant&&xVariant!==yVariant)return false;
    x.searchParams.delete('variant');y.searchParams.delete('variant');return x.href===y.href;
  }
  function combine(root,primary){
    const country=root.fzRefineBridge?.context()?.country;
    const rows=primary.map(row=>displayMarket(row,country));
    if(root.dataset.choicePreview==='true')return rows;
    for(const item of states.get(root)?.rows||[]){
      const row=displayMarket(item,country),prior=rows.find(candidate=>sameOffer(candidate,row));
      if(prior){
        if(!prior.merchant_country&&row.merchant_country){
          Object.assign(prior,{merchant_country:row.merchant_country,merchant_country_evidence:row.merchant_country_evidence,market_policy:row.market_policy});
          Object.assign(prior,displayMarket(prior,country));
        }
      }else rows.push(row);
    }
    return rows;
  }
  function safeURL(value) {
    try {
      const url = new URL(value);
      return url.protocol === 'https:' && !url.username && !url.password ? url.href : '';
    } catch (_) { return ''; }
  }
  function key(value) {
    const safe = safeURL(value); if (!safe) return '';
    const url = new URL(safe); url.hash = ''; url.hostname = url.hostname.replace(/^www\./, '');
    url.pathname = url.pathname.replace(/\/$/, '');
    Array.from(url.searchParams.keys()).forEach(k => { if (/^(utm_|gclid$|fbclid$|srsltid$|_gsid$)/i.test(k)) url.searchParams.delete(k); });
    url.searchParams.sort(); return url.href;
  }
  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }
  function mount(root) {
    if (states.has(root)) return;
    const state = {section:null, cards:new Map(), seen:new Set(), rows:[], nav:null,note:null,hasResults:false}; states.set(root, state);
    // The current public header hides the old results-head container. Move the
    // existing, already-bound filter buttons into the visible results flow.
    if(root.dataset.choicePreview!=='true'){
      const filters=root.querySelector('[data-filter-seg]'),body=root.querySelector('[data-results-body]');
      if(filters&&body){
        const nav=element('div','fz-catalog-filters');nav.hidden=true;
        const header=root.querySelector('.fz-fixed-header-inner');
        if(header)header.append(nav);else body.before(nav);
        nav.append(filters);state.nav=nav;
        const note=element('p','fz-catalog-context');note.hidden=true;body.after(note);state.note=note;
      }
    }
    function updateNote(){
      if(!state.note)return;
      const language=lang(root),words=copy[language]||copy.en;
      state.note.hidden=!state.rows.length;
      state.note.textContent=[shipping[language]||shipping.en,...(state.rows.some(row=>row.match_type==='visual_similarity')?[words[2]]:[])].join(' · ');
    }
    function clear() { state.section?.remove(); state.section = null; state.cards.clear(); state.seen.clear(); state.rows=[];state.hasResults=false; if(state.nav)state.nav.hidden=true;updateNote(); root.fzRefineBridge?.renderCatalog?.(); }
    function prune(url) {
      const id = key(url); if (!id) return;
      state.seen.add(id); state.cards.get(id)?.remove(); state.cards.delete(id);
      if (!state.cards.size) { state.section?.remove(); state.section = null; }
    }
    root.addEventListener('fz:search-reset', clear);
    root.addEventListener('fz:search-state',updateNote);
    root.addEventListener('fz:result-count',({detail})=>{state.hasResults=state.hasResults||detail?.count>0;if(state.nav)state.nav.hidden=!state.hasResults;});
    root.addEventListener('fz:search-progress', ({detail:event}) => {
      if (!event) return;
      if (event.event === 'result' || event.event === 'upsert') prune(event.item?.url);
      if (event.event === 'snapshot') (event.results || event.all_results || []).forEach(row => prune(row.url));
      if (['result','upsert','snapshot','remove'].includes(event.event)&&state.rows.length)root.fzRefineBridge?.renderCatalog?.();
      if (event.event !== 'catalog' || event.source !== 'shopify_catalog' || !Array.isArray(event.items)) return;
      state.rows=[];
      for(const row of event.items.slice(0,18)){
        if(!safeURL(row.url)||!safeURL(row.image)||!row.title||!row.price||state.rows.some(r=>sameOffer(r,row)))continue;
        state.rows.push({...row,source:'shopify_catalog',cacheable:false,_fzArrival:root.fzRefineBridge?.nextArrival?.()??Date.now()});
      }
      if(root.dataset.choicePreview!=='true'){state.hasResults=state.hasResults||state.rows.length>0;if(state.nav)state.nav.hidden=!state.hasResults;updateNote();root.fzRefineBridge?.renderCatalog?.();return;}
      state.section?.remove(); state.section = null; state.cards.clear();
      const body = root.querySelector('[data-results-body]'); if (!body) return;
      const language = (root.fzRefineBridge?.context()?.lang || document.documentElement.lang || 'en').split('-')[0];
      const words = copy[language] || copy.en;
      const section = element('section', 'fz-catalog');
      section.dataset.liveCatalog = ''; section.setAttribute('aria-label', words[0]);
      section.append(element('h3', 'fz-catalog-heading', words[0]));
      section.append(element('p', 'fz-catalog-note', words[1]));
      if (event.items.some(row => row.match_type === 'visual_similarity')) section.append(element('p', 'fz-catalog-note', words[2]));
      const grid = element('div', 'fz-catalog-grid'); section.append(grid);
      for (const row of event.items.slice(0, 12)) {
        const url = safeURL(row.url), imageURL = safeURL(row.image), id = key(url);
        if (!url || !imageURL || !row.title || !row.price || state.seen.has(id) || state.cards.has(id)) continue;
        const card = element('a', 'fz-catalog-card');
        card.href = url; card.target = '_blank'; card.rel = 'noopener noreferrer';
        const image = element('img', 'fz-catalog-image');
        image.src = imageURL; image.alt = row.title; image.loading = 'lazy'; image.decoding = 'async';
        image.referrerPolicy = 'no-referrer'; image.width = 320; image.height = 240;
        image.addEventListener('error', () => { image.hidden = true; }, {once:true});
        card.append(image, element('span', 'fz-catalog-title', row.title),
                    element('span', 'fz-catalog-store', row.store), element('strong', 'fz-catalog-price', row.price));
        grid.append(card); state.cards.set(id, card);
      }
      if (state.cards.size) { body.after(section); state.section = section; }
    });
    // A restored browser document must run a fresh search for catalog products.
    window.addEventListener('pagehide', clear);
  }
  window.FindziaCatalog = {mount, combine, displayMarket, labels, unknownLabel, sameOffer, photoCopy, isLens, compareLens, photoGroups, count:root => states.get(root)?.rows.length || 0};
  document.querySelectorAll('.fz-home').forEach(mount);
})();
