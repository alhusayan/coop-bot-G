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
  const states = new WeakMap();
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
    Array.from(url.searchParams.keys()).forEach(k => { if (/^(utm_|gclid$|fbclid$)/i.test(k)) url.searchParams.delete(k); });
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
    const state = {section:null, cards:new Map(), seen:new Set()}; states.set(root, state);
    function clear() { state.section?.remove(); state.section = null; state.cards.clear(); state.seen.clear(); }
    function prune(url) {
      const id = key(url); if (!id) return;
      state.seen.add(id); state.cards.get(id)?.remove(); state.cards.delete(id);
      if (!state.cards.size) { state.section?.remove(); state.section = null; }
    }
    root.addEventListener('fz:search-reset', clear);
    root.addEventListener('fz:search-progress', ({detail:event}) => {
      if (!event) return;
      if (event.event === 'result' || event.event === 'upsert') prune(event.item?.url);
      if (event.event === 'snapshot') (event.results || event.all_results || []).forEach(row => prune(row.url));
      if (event.event !== 'catalog' || event.source !== 'shopify_catalog' || !Array.isArray(event.items)) return;
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
  window.FindziaCatalog = {mount, count:root => states.get(root)?.cards.size || 0};
  document.querySelectorAll('.fz-home').forEach(mount);
})();
