/* Shared modal ownership keeps the page fixed on touch browsers as well. */
window.FindziaModalScroll=window.FindziaModalScroll||(()=>{
 const owners=new Set();let saved=null;
 const keys=['position','top','left','right','width','overflow','paddingRight'];
 return {lock(owner){if(owners.has(owner))return;owners.add(owner);if(saved)return;
  const body=document.body,html=document.documentElement,x=window.scrollX||0,y=window.scrollY||0;
  saved={x,y,body:Object.fromEntries(keys.map(k=>[k,body.style[k]])),overflow:html.style.overflow,overscroll:html.style.overscrollBehavior,behavior:html.style.scrollBehavior};
  const gap=Math.max(0,(window.innerWidth||html.clientWidth)-html.clientWidth);
  if(gap)body.style.paddingRight=((parseFloat(window.getComputedStyle(body).paddingRight)||0)+gap)+'px';
  Object.assign(body.style,{position:'fixed',top:-y+'px',left:-x+'px',right:'0',width:'100%',overflow:'hidden'});
  html.style.overflow='hidden';html.style.overscrollBehavior='none';
 },unlock(owner){if(!owners.delete(owner)||owners.size||!saved)return;const state=saved;saved=null;
  Object.assign(document.body.style,state.body);const html=document.documentElement;
  html.style.overflow=state.overflow;html.style.overscrollBehavior=state.overscroll;html.style.scrollBehavior='auto';
  window.scrollTo(state.x,state.y);html.style.scrollBehavior=state.behavior;
 }};
})();
function fzReadLocale(s) {
    var b = Uint8Array.from(atob(s), c => c.charCodeAt(0)),
        o = [],
        i = 0;
    while (i < b.length) {
        var f = b[i++];
        for (var j = 0; j < 8 && i < b.length; j++) {
            if (f & (1 << j)) {
                var d = (b[i++] << 8) | b[i++],
                    n = b[i++] + 3;
                while (n--) o.push(o[o.length - d]);
            } else o.push(b[i++]);
        }
    }
    return JSON.parse(new TextDecoder().decode(new Uint8Array(o)));
}(function() {
    "use strict";
    if (window.FindziaFiltersV15620) {
        window.FindziaFiltersV15620.scan(document);
        return;
    }

    function _b(_1j) {
        return String(_1j || "").normalize("NFKC").toLowerCase().replace(/[\u064b-\u065f\u0670\u0640]/g, "").replace(/[أإآ]/g, "ا").replace(/ى/g, "ي").replace(/ة/g, "ه").replace(/[^\p{L}\p{N}]+/gu, " ").trim();
    }
    const _2r = {
        "colour": "color",
        "colours": "color",
        "colors": "color",
        "colour_family": "color",
        "color_family": "color",
        "dress_color": "color",
        "storage_capacity": "storage",
        "capacity_storage": "storage",
        "phone_storage": "storage",
        "internal_storage": "storage",
        "phone_model": "model",
        "iphone_model": "model",
        "model_series": "model",
        "model_name": "model",
        "generation": "model",
        "series": "model",
        "price_range": "price",
        "budget": "price",
        "cost": "price",
        "product_condition": "condition",
        "item_condition": "condition",
        "fabric": "material",
        "fabric_type": "material",
        "fabric_material": "material",
        "material_type": "material",
        "dress_material": "material",
        "dress_fabric": "material",
        "construction_material": "material",
        "clothing_size": "size",
        "dress_size": "size",
        "apparel_size": "size",
        "shoe_size": "size",
        "ring_size": "size",
        "dress_length": "length",
        "skirt_length": "length",
        "hem_length": "length",
        "garment_length": "length",
        "cut": "silhouette",
        "dress_cut": "silhouette",
        "dress_silhouette": "silhouette",
        "dress_shape": "silhouette",
        "body_fit": "fit",
        "clothing_fit": "fit",
        "garment_fit": "fit",
        "sleeves": "sleeve",
        "sleeve_length": "sleeve",
        "sleeve_type": "sleeve",
        "neck_line": "neckline",
        "neck_style": "neckline",
        "neck_type": "neckline",
        "neckline_type": "neckline",
        "brands": "brand",
        "designer": "brand",
        "manufacturer": "brand",
        "display_size": "screen_size",
        "display_inches": "screen_size",
        "screen_diagonal": "screen_size",
        "ram": "memory",
        "ram_size": "memory",
        "ram_capacity": "memory",
        "pattern_type": "pattern",
        "print": "pattern",
        "print_pattern": "pattern",
        "decoration": "embellishment",
        "embellishments": "embellishment",
        "detailing": "embellishment",
        "product_type": "type",
        "dress_type": "type",
        "category_type": "type",
        "subtype": "type",
        "use_case": "intended_use",
        "usage": "intended_use",
        "gemstones": "gemstone",
        "stone_type": "gemstone"
    };
    const _l = {
        "type": ["Type", "النوع"],
        "size": ["Size", "المقاس"],
        "color": ["Colour", "اللون"],
        "length": ["Length", "الطول"],
        "silhouette": ["Silhouette", "القَصّة"],
        "fit": ["Fit", "الملاءمة"],
        "sleeve": ["Sleeves", "الأكمام"],
        "neckline": ["Neckline", "فتحة الرقبة"],
        "material": ["Material", "الخامة"],
        "pattern": ["Pattern", "النقشة"],
        "embellishment": ["Details", "الزخرفة"],
        "occasion": ["Occasion", "المناسبة"],
        "brand": ["Brand", "الماركة"],
        "price": ["Price", "السعر"],
        "model": ["Model", "الموديل"],
        "storage": ["Storage", "السعة التخزينية"],
        "memory": ["Memory (RAM)", "الذاكرة العشوائية"],
        "screen_size": ["Screen size", "حجم الشاشة"],
        "condition": ["Condition", "الحالة"],
        "shape": ["Shape", "الشكل"],
        "finish": ["Finish", "اللمسة النهائية"],
        "gemstone": ["Gemstone", "الحجر الكريم"]
    };
    const _33 = {
        "dress": ["type", "size", "color", "length", "silhouette", "fit", "sleeve", "neckline", "material", "pattern", "embellishment", "occasion", "brand", "condition", "price"],
        "phone": ["model", "storage", "color", "condition", "screen_size", "memory", "network", "sim", "brand", "price"],
        "furniture": ["type", "size", "dimensions", "color", "material", "shape", "style", "finish", "brand", "condition", "price"],
        "jewellery": ["type", "size", "material", "gemstone", "color", "shape", "style", "brand", "condition", "price"],
        "generic": ["type", "model", "size", "storage", "color", "length", "material", "shape", "style", "fit", "finish", "brand", "condition", "price"]
    };

    function _2y(_2z) {
        _2z = _b(_2z);
        if (/\bdress(?:es)?\b|\bgown\b|فستان|فساتين/.test(_2z)) return "dress";
        if (/\b(iphone|phone|smartphone|smartphones|mobile)\b|ايفون|هاتف|هواتف|جوال/.test(_2z)) return "phone";
        if (/jewel|necklace|earring|bracelet|مجوهر|قلاد|خاتم|خواتم|اقراط|اساور/.test(_2z)) return "jewellery";
        if (/furniture|chair|table|sofa|كرسي|طاول|كنب|اثاث/.test(_2z)) return "furniture";
        return "generic";
    }

    function fzFacetKey(value) {
        const key=String(value||'').trim().toLowerCase().replace(/[\s-]+/g,'_');
        return _2r[key]||key;
    }
    function _2b(plan, query, language) {
        const groups=new Map(), labels=new Map(), selection={}, ranges={};
        const selected=new Set(Object.values(plan.selection||{}));
        for(const [key,value] of Object.entries(plan.selection||{})) selection[fzFacetKey(key)]=value;
        for(const [key,value] of Object.entries(plan.ranges||{})) ranges[fzFacetKey(key)]=value;
        for(const raw of Array.isArray(plan.facets)?plan.facets:[]) {
            if(!raw||typeof raw.key!=='string')continue;
            let key=fzFacetKey(raw.key), label=_b(raw.label);
            if(!key||key.startsWith('__'))continue;
            if(!_l[key])key=Object.keys(_l).find(k=>_l[k].some(v=>_b(v)===label))||labels.get(label)||key;
            if(raw.key in (plan.selection||{}))selection[key]=plan.selection[raw.key];
            let facet=groups.get(key);
            if(!facet){
                facet={...raw,key,label:plan.display_language===language?String(raw.label||key):_l[key]?(window.FindziaI18n?.t(_l[key][0],_l[key][1],{dataset:{lang:language}})||_l[key][language==='ar'?1:0]):String(raw.label||key),options:[],invalidates:[],depends_on:[],_seen:new Map()};
                groups.set(key,facet);if(label)labels.set(label,key);
            }
            for(const field of ['invalidates','depends_on'])facet[field]=[...new Set([...facet[field],...(Array.isArray(raw[field])?raw[field]:[]).map(fzFacetKey)])].filter(k=>k!==key);
            for(const option of Array.isArray(raw.options)?raw.options:[]) {
                if(!option||typeof option.label!=='string'||!option.label.trim()||typeof option.token!=='string'||!option.token)continue;
                const norm=_b(option.label), identity=option.value_id||norm;
                const duplicate=facet._seen.get(identity)??facet._seen.get(norm);
                const value={...option,label:option.label.trim(),sourceKey:raw.key};
                if(duplicate!==undefined){
                    if(selected.has(option.token))facet.options[duplicate]=value;
                    else if(selected.has(facet.options[duplicate].token))selection[key]=facet.options[duplicate].token;
                    continue;
                }
                facet._seen.set(identity,facet.options.length);facet._seen.set(norm,facet.options.length);facet.options.push(value);
            }
        }
        const family=_2y(query+' '+(plan.category||'')), order=_33[family];
        const facets=[...groups.values()].filter(f=>f.control==='range'||f.options.length>=2||(selection[f.key]&&f.options.length));
        const rank=k=>k==='price'?1000:order.includes(k)?order.indexOf(k):900;
        if(!plan.adaptive)facets.sort((a,b)=>rank(a.key)-rank(b.key)||a.key.localeCompare(b.key,'en'));
        facets.forEach(f=>delete f._seen);
        const seen=new Set();
        const children=(Array.isArray(plan.children||plan.choices)?plan.children||plan.choices:[]).filter(c=>{
            if(!c||typeof c.token!=='string'||!c.label||seen.has(_b(c.label)))return false;
            seen.add(_b(c.label));return true;
        }).map(c=>({id:c.id,label:c.label,token:c.token,query_native:c.query_native}));
        return {...plan,facets,children,choices:children,selection,ranges,_family:family};
    }

    function _23(_r) {
        if (!_r || _r.dataset.findziaFiltersMounted || !_r.fzRefineBridge) return;
        const _k = _r.fzRefineBridge,
            el = _4l => _r.querySelector("[data-refine-" + _4l + "]");
        const _18 = el("dialog");
        const _10 = _r.querySelector("[data-refine]");
        if (!_10 || !_18) return;
        _10.classList.add("fz-compact-filters");
        const _3e = el("rail"),
            _3l = el("status"),
            _q = el("groups"),
            _14 = el("open");
        const _16 = el("apply"),
            _s = el("clear"),
            _3m = el("retry"),
            _24 = el("cancel"),
            _2s = el("scroll");
        const top = _10.querySelector(".fz-refine-top");
        top.replaceChildren(_14, _3e);
        for (const _4l of ["context", "question", "skip"]) el(_4l)?.remove();
        const _i = document.createElement("input");
        _i.type = "search";
        _i.autocomplete = "off";
        _i.className = "fz-filter-option-search";
        _i.dataset.filterOptionSearch = "";
        _2s.before(_i);
        let _0 = _4t(),
            _1y = false,
            _2j = false,
            _m = false,
            _checking = false,
            _25 = 0;
        let seq = 0,
            _1w = 0,
            _1o = null,
            _19 = null,
            _34 = null,
            _1g = "",
            _1d = null;
        let _7 = "",
            _y = {},
            _2 = {},
            _2d = null,
            _1e = new Map();
        let _d = null,
            _2e = false,
            _1p = 0,
            _1k = null,
            _2k = null,
            _3d = "";
        const _2w = new Map(), branchPlans = new Map();
        const _t = new Set(),
            _u = new Set();
        const _2c = {
            sleeve: ["sleeve_style"],
            length: ["train"],
            model: ["storage", "memory", "processor", "screen_size", "sim", "network", "head_size", "weight", "string_pattern"]
        };
        let _e = false,
            _v = false,
            _2l = false,
            _26 = null;
        const _z = document.createElement("p");
        _z.className = "fz-filter-updating";
        _z.hidden = true;
        _z.setAttribute("role", "status");
        _q.after(_z);

        function _2m(_w) {
            _2l = _w.type === "keydown" && ["Tab", "ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight"].includes(_w.key);
            _r.dataset.focusMode = _2l ? "keyboard" : "pointer";
        }
        _r.addEventListener("pointerdown", _2m, true);
        _r.addEventListener("keydown", _2m, true);
        _r.dataset.focusMode = "pointer";

        function _4b(_40) {
            const map = new Map();
            for (const e of _40.children)
                if (e.dataset.facet && !e.hidden) map.set(e.dataset.facet, e.getBoundingClientRect());
            return map;
        }

        function _41(_40, _1i) {
            if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
            let _4s = 0;
            for (const e of _40.children) {
                if (e.hidden || !e.dataset.facet || !e.animate) continue;
                const old = _1i.get(e.dataset.facet),
                    now = e.getBoundingClientRect();
                const x = old ? old.left - now.left : dir() === "rtl" ? -14 : 14,
                    y = old ? old.top - now.top : 6;
                if (Math.abs(x) + Math.abs(y) < 1) continue;
                e.getAnimations().forEach(a => a.cancel());
                e.animate([{
                    transform: `translate(${x}px,${y}px)`,
                    opacity: old ? 1 : .2
                }, {
                    transform: `translate(${-x*.045}px,${-y*.045}px)`,
                    opacity: 1,
                    offset: .8
                }, {
                    transform: "translate(0,0)",
                    opacity: 1
                }], {
                    duration: 260,
                    delay: Math.min(_4s++ * 18, 72),
                    easing: "cubic-bezier(.2,.8,.2,1)"
                });
            }
        }

        function _1z(_3, _a) {
            const _2a = new Set([...(_3.invalidates || []), ...(_2c[_3.key] || [])]);
            if (["type", "product_scope", "accessory_type"].includes(_3.key))
                for (const f of _a.facets)
                    if (!["brand", "price", _3.key].includes(f.key)) _2a.add(f.key);
            if (_3.key === "brand" && (_a.intent?.model_led || _3.invalidates?.includes("model")))
                for (const k of ["model", ..._2c.model]) _2a.add(k);
            for (const f of _a.facets)
                if ((f.depends_on || []).includes(_3.key)) _2a.add(f.key);
            _2a.delete(_3.key);
            _2a.delete("price");
            return _2a;
        }

        function _3n(key) {
            const f = _d?.facets.find(f => f.key === key);
            delete _y[key];
            delete _2[key];
            if (f) _x(f);
            _20();
            _n(key);
        }

        function _3b(key) {
            if (_1y || !_0.plan) return;
            const _8 = _1b(_0.selected),
                _6 = _1b(_0.ranges);
            delete _8[key];
            delete _6[key];
            const f = _0.plan.facets.find(f => f.key === key);
            if (f)
                for (const k of _1z(f, _0.plan)) {
                    delete _8[k];
                    delete _6[k];
                }
            run({
                kind: "filters",
                plan: _0.plan,
                selection: _8,
                ranges: _6
            });
        }

        function _2n(key, _5, _f) {
            const b = _28("×", _w => {
                _w.preventDefault();
                _w.stopPropagation();
                _f(key);
            }, "fz-filter-remove");
            b.dataset.removeFacet = key;
            b.setAttribute("aria-label", t("remove") + " " + _5);
            b.title = t("remove") + " " + _5;
            return b;
        }
        const _54 = {"en":{"all":"All filters","filters":"Filters","categories":"Browse categories","apply":"Show results","clear":"Clear all","any":"No preference","search":"Search filter options","from":"Min","to":"Max","price":"Price","back":"All categories","preparing":"Preparing categories and filters…","searching":"Searching with your choices…","empty":"No verified matches for these choices. Remove a filter or choose a broader category.","failed":"The search could not finish. Your previous results are still shown.","unavailable":"Some filters could not be loaded. Try again.","retry":"Try again","cancel":"Cancel","close":"Close","selected":"selected","invalid":"Enter a valid price range.","more":"More filters","remove":"Remove","preferences":"Choose preferences to search for. Availability and specifications are checked on each offer."},"ar":{"all":"كل الفلاتر","filters":"الفلاتر","categories":"تصفح الأقسام","apply":"عرض النتائج","clear":"مسح الفلاتر","any":"بدون تحديد","search":"ابحث داخل الخيارات","from":"من","to":"إلى","price":"السعر","back":"كل الأقسام","preparing":"نجهّز الأقسام والفلاتر…","searching":"نبحث حسب اختياراتك…","empty":"ما لقينا نتائج مؤكدة لهالاختيارات. شيل فلتر أو ارجع لقسم أشمل.","failed":"ما اكتمل البحث. المعروض نتائج بحثك السابق.","unavailable":"تعذّر تحميل بعض الفلاتر. حاول مجددًا.","retry":"حاول مجددًا","cancel":"إلغاء","close":"إغلاق","selected":"محدد","invalid":"أدخل نطاق سعر صحيح.","more":"فلاتر إضافية","remove":"إزالة","preferences":"اختَر المواصفات للبحث عنها. نتحقق من توفرها ومطابقتها لكل عرض."},"fr":{"all":"Tous les filtres","filters":"Filtres","categories":"Catégories","apply":"Voir les résultats","clear":"Tout effacer","any":"Sans préférence","search":"Rechercher une option","from":"Min","to":"Max","price":"Prix","back":"Toutes les catégories","remove":"Retirer"},"de":{"all":"Alle Filter","filters":"Filter","categories":"Kategorien","apply":"Ergebnisse anzeigen","clear":"Zurücksetzen","any":"Keine Präferenz","search":"Optionen suchen","from":"Min","to":"Max","price":"Preis","back":"Alle Kategorien","remove":"Entfernen"},"es":{"all":"Todos los filtros","filters":"Filtros","categories":"Categorías","apply":"Ver resultados","clear":"Borrar todo","any":"Sin preferencia","search":"Buscar opciones","from":"Mín","to":"Máx","price":"Precio","back":"Todas las categorías","remove":"Quitar"},"it":{"all":"Tutti i filtri","filters":"Filtri","categories":"Categorie","apply":"Mostra risultati","clear":"Cancella tutto","any":"Nessuna preferenza","search":"Cerca opzioni","from":"Min","to":"Max","price":"Prezzo","remove":"Rimuovi"},"pt":{"all":"Todos os filtros","filters":"Filtros","categories":"Categorias","apply":"Ver resultados","clear":"Limpar tudo","any":"Sem preferência","search":"Buscar opções","from":"Mín","to":"Máx","price":"Preço","remove":"Remover"},"tr":{"all":"Tüm filtreler","filters":"Filtreler","categories":"Kategoriler","apply":"Sonuçları göster","clear":"Tümünü temizle","any":"Tercih yok","search":"Seçenek ara","from":"Min","to":"Maks","price":"Fiyat","remove":"Kaldır"},"ru":{"all":"Все фильтры","filters":"Фильтры","categories":"Категории","apply":"Показать результаты","clear":"Сбросить","any":"Не важно","search":"Поиск вариантов","from":"От","to":"До","price":"Цена","remove":"Удалить"},"zh":{"all":"所有筛选","filters":"筛选","categories":"浏览分类","apply":"查看结果","clear":"清除筛选","any":"不限","search":"搜索选项","from":"最低","to":"最高","price":"价格","remove":"删除"},"ja":{"all":"すべての条件","filters":"絞り込み","categories":"カテゴリー","apply":"結果を表示","clear":"すべて解除","any":"指定なし","search":"条件を検索","from":"最低","to":"最高","price":"価格","remove":"削除"},"ko":{"all":"모든 필터","filters":"필터","categories":"카테고리","apply":"결과 보기","clear":"모두 지우기","any":"상관없음","search":"옵션 검색","from":"최소","to":"최대","price":"가격","remove":"삭제"},"hi":{"all":"सभी फ़िल्टर","filters":"फ़िल्टर","categories":"श्रेणियाँ","apply":"नतीजे देखें","clear":"फ़िल्टर हटाएँ","any":"कोई प्राथमिकता नहीं","search":"विकल्प खोजें","from":"न्यूनतम","to":"अधिकतम","price":"कीमत","remove":"हटाएँ"},"ur":{"all":"تمام فلٹرز","filters":"فلٹرز","categories":"زمرے","apply":"نتائج دکھائیں","clear":"فلٹرز ہٹائیں","any":"کوئی ترجیح نہیں","search":"اختیارات تلاش کریں","from":"کم از کم","to":"زیادہ سے زیادہ","price":"قیمت","remove":"ہٹائیں"},"id":{"all":"Semua filter","filters":"Filter","categories":"Kategori","apply":"Lihat hasil","clear":"Hapus filter","any":"Tanpa preferensi","search":"Cari opsi","from":"Min","to":"Maks","price":"Harga","remove":"Hapus"},"ms":{"all":"Semua penapis","filters":"Penapis","categories":"Kategori","apply":"Lihat hasil","clear":"Padam penapis","any":"Tiada pilihan","search":"Cari pilihan","from":"Min","to":"Maks","price":"Harga","remove":"Padam"}};

        Object.assign(_54.en, {all:"Refine your search", filters:"Search words", apply:"Search · 1 credit", search:"Find a specification or model", more:"More specifications", explainer:"Choose what matters. We’ll add these words to your search."});
        Object.assign(_54.ar, {all:"خصّص بحثك", filters:"كلمات تساعد بحثك", apply:"ابحث · رصيد واحد", search:"ابحث عن مواصفة أو موديل", more:"مواصفات أخرى", explainer:"اختر اللي يهمك، ونضيفه إلى بحثك الحالي."});
        function _4t() {
            return {
                origin: null,
                plan: null,
                nodeToken: "",
                selected: {},
                ranges: {},
                rootSnapshot: null
            };
        }

        function _1a() {
            return _r.dataset.lang || _k.context().lang || "en";
        }

        function t(key) {
            return window.FindziaI18n?.t(_54.en[key] || key, _54.ar[key], _r) || _54[_1a()]?.[key] || _54.en[key] || key;
        }

        function dir() {
            return ["ar", "ur", "fa", "he"].includes(_1a()) ? "rtl" : "ltr";
        }

        function _1b(x) {
            return JSON.parse(JSON.stringify(x || {}));
        }

        function _27(fn) {
            _25++;
            try {
                return fn();
            } finally {
                _25--;
            }
        }

        function _28(_5, _f, cls) {
            const b = document.createElement("button");
            b.type = "button";
            b.className = cls || "";
            b.textContent = _5;
            b.addEventListener("click", _f);
            return b;
        }

        function _4c(f, _1 = _0.selected) {
            return (f.options || []).find(o => o.token === _1[f.key]);
        }

        function _3o() {
            return Object.keys(_0.selected).length + Object.keys(_0.ranges).length;
        }

        function _46(r) {
            return (r.min ?? 0) + " – " + (r.max ?? "∞") + " " + (r.currency || "");
        }

        function _2f(f, _8 = _0.selected, _6 = _0.ranges) {
            return _4c(f, _8)?.label || (_6[f.key] ? _46(_6[f.key]) : "");
        }

        function say(_2z, _21 = false) {
            _3l.textContent = _2z || "";
            _3m.hidden = !_21;
            _10.querySelector(".fz-refine-feedback").hidden = !_2z && !_1y;
        }

        function _1u(on) {
            window.FindziaModalScroll[on?'lock':'unlock'](_18);
        }

        function _2x() {
            if (_18.open) _18.close();
            _1u(false);
        }

        function _4d() {
            return (_0.origin?.country || "") + "|" + (_0.origin?.kind || "") + "|" + _0.nodeToken;
        }

        function _2t() {
            if (_m) return;
            const _4e = _3e.scrollLeft,
                _1i = _4b(_3e);
            _10.hidden = !_0.origin || (_0.origin.kind === "image" && _r.dataset.photoFiltersUnavailable === "true");
            _10.dir = dir();
            _18.dir = dir();
            _10.dataset.state = _1y ? "searching" : _2j ? "loading" : "ready";
            el("open-label").textContent = t("all");
            _14.hidden = !_0.origin;
            _14.disabled = _1y;
            _14.setAttribute("aria-busy", String(_2j));
            _14.setAttribute("aria-label", t("all") + (_3o() ? " · " + _3o() : ""));
            el("count").textContent = String(_3o());
            el("count").hidden = !_3o();
            el("close").setAttribute("aria-label", t("close"));
            _3m.textContent = t("retry");
            _24.textContent = t("cancel");
            _24.hidden = !_1y;
            _10.querySelector(".fz-refine-feedback").hidden = !_3l.textContent && !_1y;
            _3e.replaceChildren();
            // Selected specifications remain in the composed search sentence.
            // Keep the toolbar calm: no duplicate chips beside the four tools.
            _3e.hidden = true;
        }

        function _36(key, _5, _1 = "") {
            const _4 = document.createElement("details");
            _4.className = "fz-refine-group";
            _4.dataset.facet = key;
            const _3f = document.createElement("summary"),
                _3g = document.createElement("span"),
                _1j = document.createElement("span");
            _3g.className = "fz-filter-label";
            _3g.textContent = _5;
            _1j.className = "fz-filter-value";
            _1j.textContent = _1;
            _3f.append(_3g, _1j);
            _4.append(_3f);
            const _g = _2n(key, _5, _3n);
            _g.hidden = !_1;
            if (_7) _4.append(_g);
            else _3f.append(_g);

            return _4;
        }

        function _37() {
            const _a = _d || _0.plan;
            if (!_a || (!_a.children.length && !(_a.breadcrumbs || []).some(b => !b.current))) return;
            const _4 = _36("__categories", t("categories"), _a.category || "");
            const nav = document.createElement("nav");
            nav.className = "fz-filter-text-navigation";
            nav.setAttribute("aria-label", t("categories"));
            (_a.breadcrumbs || []).filter(b => !b.current).forEach(_4f => {
                const b = _28((dir() === "rtl" ? "› " : "‹ ") + _4f.label, () => _3v(_4f.token, _4f.label), "fz-filter-back");
                nav.append(b);
            });
            for (const _3p of _a.children) {
                const b = _28(_3p.label, () => _3v(_3p.token, _3p.query_native || _3p.label), "fz-refine-option fz-filter-child");
                b.dataset.categoryId = _3p.id || "";
                nav.append(b);
            }
            _4.append(nav);
            _4.open = _7 === "__categories";
            _q.append(_4);
        }

        function _2g(key, _4z) {
            if (_1y || !_0.origin) return;
            _7 = key || "";
            _2d = _4z || _14;
            _d = _0.plan;
            _y = _1b(_0.selected);
            _2 = _1b(_0.ranges);
            _3d = "";
            _t.clear();
            _e = false;
            _v = false;
            _11();
            _i.value = "";
            _1e.clear();
            _q.replaceChildren();
            if (_d) _20();
            else {
                el("dialog-title").textContent=t("all");
                _i.hidden=true;_s.hidden=true;_16.hidden=true;
                const note=document.createElement('p');note.textContent=t("preparing");_q.append(note);
            }
            if (!_18.open) _18.showModal();
            _1u(true);
            _2s.scrollTop = 0;
            el("dialog-title").tabIndex = -1;
            el("dialog-title").focus({
                preventScroll: true
            });
            if (!_d && !_2j) _2p(_0.nodeToken,true);
            else if (_d?.quick_plan) _3r(false);
        }

        function _20() {
            const active=document.activeElement;
            const focus=active&&_q.contains(active)?{facet:active.dataset.facetKey||active.closest('details')?.dataset.facet,label:_b(active.textContent),bound:active.dataset.priceBound}:null;
            const _1i = _4b(_q),
                _59 = new Set([..._q.querySelectorAll("details[open]")].map(e => e.dataset.facet));
            _q.replaceChildren();
            _i.placeholder = t("search");
            _i.setAttribute("aria-label", t("search"));
            const all = !_7;
            const _c = (_d || _0.plan).facets.filter(f => !_t.has(f.key) && (all || f.key === _7));
            _18.dataset.singleFilter = all ? "false" : "true";
            _i.hidden = _c.length === 1 && _c[0].control === "range";
            el("dialog-title").textContent = all ? t("all") : _7 === "__categories" ? t("categories") : _c[0]?.label || t("filters");
            el("category").textContent = (_d || _0.plan).category || "Findzia";
            el("explainer").textContent = _0.origin?.kind==='image' ? (_1a()==='ar'?'نضيف اختياراتك إلى الصورة الحالية.':'Add your choices to this photo search.') : t("explainer");
            if (all || _7 === "__categories") _37();
            _c.forEach((_3, _4s) => {
                const _4 = _36(_3.key, _3.label, _2f(_3, _y, _2));
                _4.open = !!_7 || _59.has(_3.key) || (!_59.size && _4s<2) || !!_y[_3.key];
                if (_7) {
                    _4.classList.add("fz-single-facet");
                    _4.querySelector("summary").hidden = true;
                }
                const _1s = document.createElement("div");
                _1s.className = "fz-refine-choices";
                _1s.setAttribute("role", "group");
                _1s.setAttribute("aria-label", _3.label);
                _4.append(_1s);

                function _1f() {
                    _4.querySelectorAll("[data-price-bound]").forEach(e => e.value = "");
                }
                const any = _28(t("any"), () => {
                    delete _y[_3.key];
                    delete _2[_3.key];
                    _1f();
                    _x(_3);
                    _15();
                    _n(_3.key);
                }, "fz-refine-option");
                any.dataset.facetKey = _3.key;
                any.dataset.filterToken = "";
                _1s.append(any);
                for (const opt of _3.options) {
                    const b = _28(opt.label, () => {
                        delete _2[_3.key];
                        _1f();
                        if (_y[_3.key] === opt.token) delete _y[_3.key];
                        else _y[_3.key] = opt.token;
                        _x(_3);
                        _15();
                        _n(_3.key);
                    }, "fz-refine-option");
                    b.dataset.facetKey = _3.key;
                    b.dataset.filterToken = opt.token;
                    if(opt.source_refs?.length) b.dataset.observedOption='true';
                    b.title=opt.source_refs?.length?(_1a()==='ar'?'ورد في نتائج البحث':'Seen in search results'):opt.label;
                    _1s.append(b);
                }
                if (_3.control === "range") {
                    const _32 = _3j(_3);
                    if (_32.items.length) {
                        const _50 = document.createElement("p");
                        _50.className = "fz-price-guidance";
                        _50.textContent = _32.estimated ? (_1a() === "ar" ? "ميزانيات تقديرية لهذه الفئة والسوق، وليست أسعار عروض مؤكدة." : "Estimated budgets for this category and market, not confirmed offer prices.") : (_1a() === "ar" ? "نطاقات مقترحة من الأسعار المتاحة في هذا السوق." : "Suggested ranges from available prices in this market.");
                        _4.append(_50);
                        const _43 = document.createElement("div");
                        _43.className = "fz-refine-choices fz-price-presets";
                        for (const _3h of _32.items) {
                            const b = _28(_3h.label, () => {
                                delete _y[_3.key];
                                _2[_3.key] = _1b(_3h.numeric);
                                _1f();
                                _4.querySelectorAll("[data-price-bound]").forEach(i => i.value = _3h.numeric[i.dataset.priceBound] ?? "");
                                _15();
                                if (_e) _n("price");
                            }, "fz-refine-option");
                            b.dataset.pricePreset = JSON.stringify(_3h.numeric);
                            _43.append(b);
                        }
                        _4.append(_43);
                    }
                    const row = document.createElement("div");
                    row.className = "fz-filter-range";
                    ["min", "max"].forEach(k => {
                        const _5 = document.createElement("label");
                        _5.textContent = (k === "min" ? t("from") : t("to")) + " " + (_3.currency || "");
                        const _1h = document.createElement("input");
                        _1h.type = "number";
                        _1h.min = "0";
                        _1h.step = "any";
                        _1h.inputMode = "decimal";
                        _1h.dataset.priceBound = k;
                        _1h.value = _2[_3.key]?.[k] ?? "";
                        _1h.addEventListener("input", () => {
                            delete _y[_3.key];
                            const r = {
                                currency: _3.currency
                            };
                            let set = false;
                            row.querySelectorAll("input").forEach(i => {
                                if (i.value !== "") {
                                    r[i.dataset.priceBound] = Number(i.value);
                                    set = true;
                                }
                            });
                            if (set) _2[_3.key] = r;
                            else delete _2[_3.key];
                            _15();
                            if (_e) _n("price");
                        });
                        _5.append(_1h);
                        row.append(_5);
                    });
                    _4.append(row);
                }
                _q.append(_4);
            });
            _15();
            _41(_q, _1i);
            if(focus){
                const group=[..._q.querySelectorAll('[data-facet]')].find(n=>n.dataset.facet===focus.facet);
                const target=group&&(focus.bound?group.querySelector('[data-price-bound="'+focus.bound+'"]'):[...group.querySelectorAll('button')].find(n=>_b(n.textContent)===focus.label)||group.querySelector('summary'));
                target?.focus({preventScroll:true});
            }
        }

        function renderWordPreview() {
            let preview=_18.querySelector('[data-refine-preview]');
            if(!preview){preview=document.createElement('div');preview.dataset.refinePreview='';preview.className='fz-word-preview';_18.querySelector('.fz-refine-sheet-head').append(preview);}
            preview.replaceChildren();
            const plan=_d||_0.plan;
            for(const f of plan?.facets||[]){const choice=f.options.find(o=>o.token===_y[f.key]);const range=_2[f.key];if(!choice&&!range)continue;
                const label=choice?.label||_2f(f,_y,_2),chip=_28(label+' ×',()=>_3n(f.key),'fz-word-chip');chip.setAttribute('aria-label',t('remove')+' '+label);preview.append(chip);}
            preview.hidden=!preview.children.length;
            const category=el('category');category.title=_0.origin?.photoDescription||_0.origin?.query||'';
        }
        function _15() {
            renderWordPreview();
            _q.querySelectorAll("[data-filter-token]").forEach(b => b.setAttribute("aria-pressed", String((_y[b.dataset.facetKey] || "") === b.dataset.filterToken && !_2[b.dataset.facetKey])));
            _q.querySelectorAll("details[data-facet]").forEach(s => {
                const f = (_d || _0.plan).facets.find(f => f.key === s.dataset.facet);
                if (f) {
                    s.querySelector(".fz-filter-value").textContent = _2f(f, _y, _2);
                    const x = s.querySelector("[data-remove-facet]");
                    if (x) x.hidden = !_y[f.key] && !_2[f.key];
                }
            });
            _q.querySelectorAll("[data-price-preset]").forEach(b => b.setAttribute("aria-pressed", String(JSON.stringify(_2.price || {}) === b.dataset.pricePreset)));
            _z.hidden = !_e && !_v;
            _z.textContent = _v ? t("unavailable") : (_1a() === "ar" ? "نجهّز المواصفات المناسبة…" : "Preparing matching options…");
            if(_v){const retry=_28(t('retry'),()=>_3r(true),'fz-filter-refresh');_z.append(' ',retry);}
            const _4v = Object.keys(_y).length + Object.keys(_2).length;
            el("draft-count").textContent = _4v ? _4v + " " + t("selected") : "";
            _s.textContent = _7 ? t("any") : t("clear");
            _s.hidden = _7 === "__categories";
            _16.hidden = _7 === "__categories";
            _16.textContent = t("apply");
            _16.disabled = _1y || _checking || !_d;
        }

        function _3c() {
            const _3i = _b(_i.value);
            _q.querySelectorAll("details").forEach(_4 => {
                if (_3i && !_1e.has(_4)) _1e.set(_4, _4.open);
                const _44 = _b(_4.querySelector(".fz-filter-label").textContent);
                let _1l = false;
                _4.querySelectorAll(".fz-refine-option,.fz-filter-back").forEach(b => {
                    b.hidden = !!_3i && !_b(b.textContent).includes(_3i) && !_44.includes(_3i);
                    _1l = _1l || !b.hidden;
                });
                _4.hidden = !!_3i && !_1l && !_44.includes(_3i);
                if (_3i && !_4.hidden) _4.open = true;
                if (!_3i && _1e.has(_4)) _4.open = _1e.get(_4);
            });
            if (!_3i) _1e.clear();
        }

        function _j(_a, _8, _6) {
            return JSON.stringify([Object.entries(_8).sort().map(([key, _h]) => {
                const o = _a?.facets.find(f => f.key === key)?.options.find(o => o.token === _h);
                return [key, o?.value_id || _b(o?.label || _h)];
            }), _6]);
        }

        function _22(_o, _a, _1c, _8) {
            if (_o.adaptive && _a.selection) {
                const _3q = {};
                for (const [k, _h] of Object.entries(_a.selection || {})) {
                    if (_a.facets.find(f => f.key === k)?.options.some(o => o.token === _h)) _3q[k] = _h;
                    else throw new Error("invalid_selection_mapping");
                }
                return _3q;
            }
            const _3q = {};
            for (const [k, _h] of Object.entries(_8 || {})) {
                const old = _1c?.facets.find(f => f.key === k)?.options.find(o => o.token === _h);
                const o = _a.facets.find(f => f.key === k)?.options.find(o => old && ((old.value_id && o.value_id === old.value_id) || _b(o.label) === _b(old.label)));
                if (!o) throw new Error("selection_missing");
                _3q[k] = o.token;
            }
            return _3q;
        }

        function _x(_3) {
            const _1i = _4b(_q);
            for (const key of _1z(_3, _d || _0.plan)) {
                delete _y[key];
                delete _2[key];
                _t.add(key);
                _q.querySelectorAll("[data-facet]").forEach(e => {
                    if (e.dataset.facet === key) e.remove();
                });
            }
            _41(_q, _1i);
        }

        function _11() {
            _1p++;
            clearTimeout(_2k);
            _1k?.abort();
            _1k = null;
            _2e = false;
        }

        async function planRequest(payload, ctl, timeout) {
            let timer, abort;
            const stopped=new Promise((_,reject)=>{
                abort=()=>reject(new DOMException('Aborted','AbortError'));
                ctl.signal.addEventListener('abort',abort,{once:true});
                if(ctl.signal.aborted)abort();
                timer=setTimeout(()=>ctl.abort(),timeout);
            });
            try {
                return await Promise.race([
                    (async()=>{
                        const response=await window.FindziaBillingFetch(_r,_k.api+"/api/refine/options",{
                            method:"POST",headers:{"Content-Type":"application/json"},
                            body:JSON.stringify(payload),signal:ctl.signal});
                        const data=await response.json();
                        if(!response.ok||!data.ok||!Array.isArray(data.facets))throw new Error(data.error||"invalid_plan");
                        return data;
                    })(),stopped
                ]);
            } finally {clearTimeout(timer);ctl.signal.removeEventListener('abort',abort);}
        }

        function _n(_4n) {
            const changed=(_d||_0.plan)?.facets.find(f=>f.key===_4n);
            const _2h = ["brand", "model", "type", "product_scope", "accessory_type", "sleeve", "length"].includes(_4n) || (changed && _1z(changed,_d||_0.plan).size>0);
            if (!_d?.adaptive || (!_2h && !_e && !_2e)) return;
            _11();
            _e = true;
            _v = false;
            _15();
            _2k = setTimeout(() => _3r(true), 40);
        }
        async function _3r(_2h) {
            if (!_18.open || !_0.origin || !_d || _m) return;
            const _1c = _d,
                _1 = _1b(_y),
                _6 = _1b(_2);
            const _47 = _j(_1c, _1, _6),
                id = ++_1p;
            const ctl = new AbortController();
            _1k = ctl;
            _2e=true;
            const _p = _1r("");
            delete _p.context_token;
            _p.plan_token = _1c.plan_token;
            _p.quick_plan = !!_2h;
            _p.tokens = Object.values(_1);
            _p.ranges = _6;
            try {
                const cached=branchPlans.get(_47);
                const _o = _2h && cached && Date.now()-cached.at<120000 ? cached.plan : await planRequest(_p,ctl,_2h ? 6000 : 14500);
                branchPlans.set(_47,{at:Date.now(),plan:_o});
                while(branchPlans.size>24)branchPlans.delete(branchPlans.keys().next().value);
                if (id !== _1p || !_18.open || _m || _47 !== _j(_1c, _y, _2)) return;
                const _a = _2b(_o, _0.origin.query, _1a());
                const _51 = _22(_o, _a, _1c, _1);
                const top = _2s.scrollTop, searchText = _i.value;
                _d = _a;
                _y = _51;
                _2 = _1b(_o.adaptive ? _o.ranges || {} : _6);
                _t.clear();
                _e = false;
                _v = false;
                if (_2h && !_a.facets.some(f=>f.key===_7)) { _7=""; _3d=""; }
                _2e = false;
                _i.value = searchText;
                _20();
                _3c();
                _2s.scrollTop = Math.min(top, _2s.scrollHeight - _2s.clientHeight);

            } catch (_21) {
                if (id === _1p && _18.open) {
                    _e = false;
                    _v = true;
                }
            } finally {
                if (id === _1p) {
                    _2e = false;
                    _1k = null;
                    _15();
                }
            }
        }

        function _3j(_3) {
            const _55 = r => r && r.currency === _3.currency && (r.min == null || Number.isFinite(r.min) && r.min >= 0) && (r.max == null || Number.isFinite(r.max) && r.max >= 0) && (r.min != null || r.max != null) && (r.min == null || r.max == null || r.min <= r.max);
            const _3t = (_3.presets || []).filter(p => typeof p.label === "string" && _55(p.numeric));
            if (_3t.length) return {
                items: _3t.slice(0, 4),
                estimated: _3.preset_basis === "estimated"
            };
            if (Object.keys(_y || {}).length || _e) return {
                items: [],
                estimated: false
            };
            const cc = _0.origin?.country?.toLowerCase();
            const _4g = _k.snapshot()?.view?.items || [];
            const _56 = new Set();
            const _1q = _4g.filter(r => {
                if (!r.url || _56.has(r.url)) return false;
                _56.add(r.url);
                return String(r.country || "").toLowerCase() === cc && r.currency === _3.currency && !r.price_unavailable && !["suspect", "unavailable"].includes(r.price_status) && !["range", "from", "up_to", "installment"].includes(r.price_kind) && !(/\/mo|per month|شهري|قسط/i.test(r.price || ""));
            }).map(r => Number(r.price_amount ?? r.price_value)).filter(v => Number.isFinite(v) && v > 0).sort((a, b) => a - b);
            if (_1q.length < 4) return {
                items: [],
                estimated: false
            };
            const _4w = 10 ** -new Intl.NumberFormat("en", {
                style: "currency",
                currency: _3.currency
            }).resolvedOptions().maximumFractionDigits;
            const _52 = [.25, .5, .75].map(p => _1q[Math.floor((_1q.length - 1) * p)]);
            const _3u = [...new Set(_52)].filter(v => v > _1q[0] && v < _1q[_1q.length - 1]);
            const nf = v => new Intl.NumberFormat("en", {
                maximumFractionDigits: 3
            }).format(v);
            const _2o = _3u.map((v, i) => ({
                label: (i ? nf(_3u[i - 1]) + " – " : _1a() === "ar" ? "حتى " : "Up to ") + nf(v) + " " + _3.currency,
                numeric: {
                    min: i ? Number((_3u[i - 1] + _4w).toFixed(3)) : 0,
                    max: v,
                    currency: _3.currency
                }
            }));
            if (_3u.length) _2o.push({
                label: (_1a() === "ar" ? "أكثر من " : "Over ") + nf(_3u[_3u.length - 1]) + " " + _3.currency,
                numeric: {
                    min: Number((_3u[_3u.length - 1] + _4w).toFixed(3)),
                    currency: _3.currency
                }
            });
            return {
                items: _2o,
                estimated: false
            };
        }

        function _1r(_h) {
            const c = _0.origin,
                now = _k.context(),
                _o = {
                    query: c.query,
                    context_token: _h || "",
                    country: c.country.toLowerCase(),
                    lang: now.lang,
                    kind: c.kind,
                    sample_titles: now.sample_titles || [],
                    offer_tokens: (_k.snapshot()?.view?.items || []).filter(r=>r.evaluation_token).slice(0,24).map(r=>r.evaluation_token)
                };
            if (c.kind === "image") Object.assign(_o, {
                image_base64: c.image_base64 || now.image_base64,
                mime_type: c.mime_type || now.mime_type,
                base_query: c.photoDescription || now.photoDescription || c.query,
                extra_specs: String(now.user_extra_specs ?? now.extra_specs ?? ""),
                extra_intent: "filters"
            });
            return _o;
        }
        async function _2p(_h, _57 = false) {
            if (!_0.origin || _m) return;
            const key = _4d() + "|" + _0.origin.query + "|" + _r.dataset.lang + "|" + _j(_0.plan, _0.selected, _0.ranges);
            if (_2w.has(key) && !_57 && Date.now() - _2w.get(key)._loadedAt < 600000) {
                _0.plan = _2w.get(key);
                _0.selected=_1b(_0.plan.selection||{});_0.ranges=_1b(_0.plan.ranges||{});
                _2t();
                return;
            }
            _19?.abort();
            const ctl = new AbortController();
            _19 = ctl;
            const id = ++_1w;
            _2j = true;
            _2t();
            try {
                const _p = _1r(_h);
                _p.quick_plan = true;
                if (_0.plan?.adaptive) {
                    delete _p.context_token;
                    _p.plan_token = _0.plan.plan_token;
                    _p.tokens = Object.values(_0.selected);
                    _p.ranges = _0.ranges;
                }
                const _o = await planRequest(_p,ctl,6000);
                if (id !== _1w || _m || _1y) return;
                const _a = _2b(_o, _0.origin.query, _1a());
                const _3q = _22(_o, _a, _0.plan, _0.selected);
                if (_o.adaptive) _0.ranges = _1b(_o.ranges || {});
                _u.clear();
                _a._loadedAt = Date.now();
                _0.selected = _3q;
                _0.plan = _a;
                _2w.set(key, _a);
                while (_2w.size > 20) _2w.delete(_2w.keys().next().value);
                if (!_1y) say("");
                if (_18.open && !_d) {
                    _d=_a;_y=_1b(_0.selected);_2=_1b(_0.ranges);_20();
                    if (_d.quick_plan) _3r(false);
                }

            } catch (_21) {
                if (id === _1w && !_m) {
                    
                    if(!_0.plan){
                        say(t("unavailable"), true);
                        if(_18.open&&!_d){_q.replaceChildren();const note=document.createElement('p');note.textContent=t('unavailable');_q.append(note,_28(t('retry'),()=>_2p(_0.nodeToken,true),'fz-refine-option'));}
                    }
                }
            } finally {
                if (id === _1w) {
                    _2j = false;
                    _19 = null;
                    _2t();
                }
            }
        }

        function _3v(_h, _5) {
            if (!_h || _1y) return;
            const _1c = {
                nodeToken: _0.nodeToken,
                plan: _0.plan,
                selected: _1b(_0.selected),
                ranges: _1b(_0.ranges)
            };
            run({
                kind: "category",
                token: _h,
                label: _5,
                previous: _1c
            });
        }
        async function run(_f) {
            if (!_0.origin || _m || _1y || _checking) return;
            const submittedContext=_k.context(),wasOpen=_18.open;
            _checking=true;_15();
            let allowed=false;
            try {allowed=await window.FindziaBeforeSearch(_r,{});} catch (_) {say(t('failed'),true);}
            finally {_checking=false;_15();}
            const currentContext=_k.context();
            if(_m||!_0.origin||['generation','country','lang','kind',submittedContext.kind==='image'?'image_base64':'query'].some(k=>submittedContext[k]!==currentContext[k])||(wasOpen&&!_18.open))return;
            if(!allowed){_2x();return;}
            const _13 = _f.plan || _0.plan;
            _1w++;_19?.abort();_19=null;_2j=false;
            _11();
            _2x();
            _1o?.abort();
            const ctl = new AbortController();
            _1o = ctl;
            const id = ++seq;
            const _1i = _k.snapshot(),
                _3w = _1b(_0.selected),
                _48 = _1b(_0.ranges);
            _1d = _f;
            _1y = true;
            if (_f.kind === "filters")
                for (const f of (_0.plan?.facets || [])) {
                    const a = _4c(f, _0.selected),
                        n = _13?.facets.find(x => x.key === f.key)?.options.find(x => x.token === _f.selection?.[f.key]);
                    if ((a?.value_id || a?.label || "") !== (n?.value_id || n?.label || ""))
                        for (const k of _1z(f, _0.plan))
                            if (!_f.selection?.[k]) _u.add(k);
                }
            const _29 = _k.context();
            const _9 = {
                ..._0.origin,
                query: _f.label || _29.query,
                extra_specs: _f.extraSpecs !== undefined ? _f.extraSpecs : String(_29.user_extra_specs ?? _29.extra_specs ?? "")
            };
            if (_9.kind === "image") {
                _9.image_base64 = _9.image_base64 || _29.image_base64;
                _9.photoDescription = _9.photoDescription || _29.photoDescription;
            }
            const _p = _1r(_f.kind === "category" ? _f.token : "");
            if (_9.kind === "image") {
                _p.extra_specs = _9.extra_specs;
                _p.extra_intent = _f.extraSpecs !== undefined ? "replace" : "filters";
            }
            if (_f.kind === "filters") {
                if (!_13) {
                    _1y = false;
                    return;
                }
                delete _p.context_token;
                _p.plan_token = _13.plan_token;
                _p.tokens = Object.keys(_f.selection || {}).sort().map(k => _f.selection[k]);
                _p.ranges = _f.ranges || {};
            }
            _27(() => _k.begin(_9));
            say("");
            _2t();
            _r.fzSearchProgress?.set(_9.kind === "image" ? "searching_photo_and_text" : "checking_filters");
            let _2q = _f.label || _29.query,
                _49 = null,
                _38 = null,
                _39 = false;
            const _4g = new Map();
            let deadlineReached=false;
            const _3s = setTimeout(() => {deadlineReached=true;ctl.abort();}, 65000);
            try {
                const _12 = await window.FindziaBillingFetch(_r,_k.api + "/api/refine/search/stream", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        Accept: "application/x-ndjson"
                    },
                    body: JSON.stringify(_p),
                    signal: ctl.signal
                });
                if (!_12.ok) {
                    const _o = await _12.json().catch(() => ({}));
                    throw new Error(_o.error || "refinement_failed");
                }
                if (!_12.body?.getReader) throw new Error("invalid_stream");
                _38 = _12.body.getReader();
                const _4o = new TextDecoder();
                let _2u = "";

                function _w(_o) {
                    if (id !== seq) return;
                    if (_9.kind === "image" && typeof _o.extra_specs_applied === "string") {
                        _9.extra_specs = _o.extra_specs_applied;
                        _9.user_extra_specs = _o.photo_extra_input ?? _p.extra_specs;
                        _k.streamPhotoWords?.(_9.extra_specs, _9.user_extra_specs);
                    }
                    _r.fzSearchProgress?.event(_o);
                    if (typeof _o.display_query === "string" && _o.display_query.trim()) {
                        _2q = _o.display_query;
                        _27(() => _k.streamQuery(_2q));
                    }
                    if (["result", "upsert"].includes(_o.event) && _o.item?.url && _o.item.refinement_verified) {
                        _4g.set(_o.item.url, _o.item);
                        _27(() => _k.stage(_o.item));
                    } else if (_o.event === "remove") {
                        _4g.delete(_o.url);
                        _27(() => _k.remove(_o.url));
                    } else if (_o.event === "done") _49 = _o;
                    else if (_o.event === "error" && !_o.recoverable) throw new Error(_o.error || "search_failed");
                }
                for (;;) {
                    const _4h = await _38.read();
                    if (id !== seq || _m) {
                        await _38.cancel();
                        return;
                    }
                    _2u += _4o.decode(_4h.value || new Uint8Array(), {
                        stream: !_4h.done
                    });
                    if (_2u.length > 8000000) throw new Error("invalid_stream");
                    const _4x = _2u.split("\n");
                    _2u = _4x.pop();
                    for (const _58 of _4x)
                        if (_58.trim()) _w(JSON.parse(_58));
                    if (_49) break;
                    if (_4h.done) {
                        if (_2u.trim()) _w(JSON.parse(_2u));
                        break;
                    }
                }
                if (!_49) throw new Error("interrupted");
                await _k.prepare([..._4g.values()], ctl.signal);
                if (id !== seq || _m) return;
                const _1l = _27(() => _k.complete(_2q));
                if (!_1l && _49.partial) {
                    if (_9.kind === "image") {
                        delete _r.dataset.photoFiltersUnavailable;
                        queueMicrotask(() => _k.photoNotice?.(t("failed")));
                    }
                    _27(() => _k.restore(_1i));
                    say(t("failed"), true);
                } else {
                    if (!_1l) _27(() => _k.commitEmpty?.(_2q, _9, t("empty")));
                    if (_f.kind === "filters") {
                        _0.plan = _13;
                        _0.selected = _1b(_f.selection);
                        _0.ranges = _1b(_f.ranges);
                    } else {
                        _0.nodeToken = _f.token;
                        _0.plan = null;
                        _0.selected = {};
                        _0.ranges = {};
                    }
                    _39 = true;
                    _1d = null;
                    say(!_1l ? t("empty") : "");
                }
            } catch (_21) {
                if (id !== seq || _m) return;
                if (_27(() => _r.fzBilling?.handleSearchError(_21))) {
                    _0.selected = _3w;
                    _0.ranges = _48;
                    _1d = null;
                    say("");
                    return;
                }
                if (_21.name === "AbortError" && !deadlineReached) {
                    _27(() => _k.restore(_1i));
                    say("");
                    _1d = null;
                } else {
                    try{await _k.prepare([..._4g.values()],ctl.signal);}catch(_){}
                    if(id!==seq||_m)return;
                    if(ctl.signal.aborted&&!deadlineReached){_27(()=>_k.restore(_1i));say('');_1d=null;return;}
                    const _1l = _27(() => _k.complete(_2q));
                    if (!_1l) {
                        if (_9.kind === "image") {
                            delete _r.dataset.photoFiltersUnavailable;
                            queueMicrotask(() => _k.photoNotice?.(t("failed")));
                        }
                        _27(() => _k.restore(_1i));
                        _0.selected = _3w;
                        _0.ranges = _48;
                        say(t("failed"), true);
                    } else {
                        _39 = true;
                        if (_f.kind === "filters") {
                            _0.plan = _13;
                            _0.selected = _1b(_f.selection);
                            _0.ranges = _1b(_f.ranges);
                        } else {
                            _0.nodeToken = _f.token;
                            _0.plan = null;
                            _0.selected = {};
                            _0.ranges = {};
                        }
                        say("");
                        _1d=null;
                    }
                }
            } finally {
                clearTimeout(_3s);
                if (_38) try {
                    await _38.cancel();
                } catch (_) {}
                if (id === seq) {
                    _1y = false;
                    _1o = null;
                    _1g=_k.context().query;
                    _27(() => _k.finish());
                    _r.fzSearchProgress?.stop();
                    _2t();
                    if (_39 && (_f.kind === "category" || _0.plan?.adaptive)) _2p(_0.nodeToken, true);
                }
            }
        }

        function _3x() {
            if (_25) return;
            seq++;
            _1w++;
            _1o?.abort();
            _19?.abort();
            _1o = _19 = null;
            _1y = _2j = false;
            _11();
            _t.clear();
            _u.clear();
            _e = false;
            _v = false;
            _d = null;
            _0 = _4t();
            _2w.clear();branchPlans.clear();
            _1g = "";
            _1d = null;
            _2x();
            say("");
            _10.hidden = true;
            clearTimeout(_34);_34=null;
            _14.hidden=true;
        }

        function _1m() {
            if (_25) return;
            if (_34) return;
            _34 = setTimeout(() => {
                _34=null;
                if (_m || _1y || _25 || _r.dataset.homeState === "empty") return;
                const c = _k.context();
                if (!c.query || !_k.api) return;
                if (!_0.origin) {
                    _0.origin = c;
                    _0.rootSnapshot = _k.snapshot();
                    _1g = c.query;
                    _2p("");
                    return;
                }
                if (c.kind !== _0.origin.kind || c.country !== _0.origin.country || (c.kind === "image" && c.image_base64 !== _0.origin.image_base64)) {
                    _3x();
                    _1m();
                    return;
                }
                if (c.kind === "image") {
                    _0.origin.image_base64 = c.image_base64 || _0.origin.image_base64;
                    _0.origin.mime_type = c.mime_type || _0.origin.mime_type;
                    _0.origin.photoDescription = c.photoDescription || _0.origin.photoDescription;
                    _0.origin.extra_specs = c.extra_specs || "";
                    _0.origin.user_extra_specs = c.user_extra_specs;
                }
                if (c.query !== _1g && c.kind === "image" && (_18.open || _3o())) {
                    // Recognition can improve while the same photo is displayed.
                    // It must not close the sheet or erase the shopper's choices.
                    _1g=c.query;
                    return;
                }
                if (c.query !== _1g) {
                    _3x();
                    _0.origin = c;
                    _0.plan=null;_0.selected={};_0.ranges={};
                    _1g = c.query;
                    _2p("", true);
                }
            }, 60);
        }
        _14.hidden=true;
        _14.addEventListener("click", () => _2g("", _14));
        el("close").addEventListener("click", _2x);
        _18.addEventListener("close", () => {
            _1u(false);
            _11();
            _d = null;
            if (!_1y && _2d?.isConnected) _2d.focus({
                preventScroll: true
            });
        });
        _18.addEventListener("click", _w => {
            if (_w.target !== _18) return;
            const r = _18.getBoundingClientRect();
            if (_w.clientX < r.left || _w.clientX > r.right || _w.clientY < r.top || _w.clientY > r.bottom) _2x();
        });
        _i.addEventListener("input", _3c);
        _s.addEventListener("click", () => {
            const key = _7;
            if (key) {
                const f = _d?.facets.find(f => f.key === key);
                delete _y[key];
                delete _2[key];
                if (f) _x(f);
            } else {
                for (const f of _d?.facets || [])
                    if (_y[f.key]) _x(f);
                _y = {};
                _2 = {};
            }
            _20();
            _n(key || "brand");
        });
        _16.addEventListener("click", () => {
            if(!_d||_1y)return;
            for (const r of Object.values(_2))
                if ((r.min != null && (!Number.isFinite(r.min) || r.min < 0)) || (r.max != null && (!Number.isFinite(r.max) || r.max < 0)) || (r.min != null && r.max != null && r.min > r.max)) {
                    el("draft-count").textContent = t("invalid");
                    return;
                } if (_j(_d, _y, _2) === _j(_0.plan, _0.selected, _0.ranges)) {
                _2x();
                return;
            }
            run({
                kind: "filters",
                plan: _d || _0.plan,
                selection: _1b(_y),
                ranges: _1b(_2)
            });
        });
        _3m.addEventListener("click", () => _1d ? run(_1d) : _2p(_0.nodeToken, true));
        _24.addEventListener("click", () => _1o?.abort());
        _r.addEventListener("fz:search-reset", _3x);
        _r.addEventListener("fz:search-state", _1m);
        const _3y = new MutationObserver(_4p => {
            if (_r.dataset.homeState === "empty") _3x();
            else if (_4p.some(c => c.attributeName === "data-lang")) {
                if(_18.open)_2x();
                _2w.clear();branchPlans.clear();
                _2t();
                if (_0.origin && !_1y) _2p(_0.nodeToken, true);
            }
        });
        _3y.observe(_r, {
            attributes: true,
            attributeFilter: ["data-home-state", "data-lang"]
        });

        function _4i(_w) {
            if (!_w.target?.contains(_r)) return;
            _3x();
            _m = true;
            _3y.disconnect();
            _r.removeEventListener("fz:search-reset", _3x);
            _r.removeEventListener("fz:search-state", _1m);

            _r.removeEventListener("pointerdown", _2m, true);
            _r.removeEventListener("keydown", _2m, true);
            _z.remove();
            if (_k.resubmitUnchanged === _fzResubmit) delete _k.resubmitUnchanged;
            delete _k.submitPhotoExtras;
            delete _r.dataset.findziaFiltersMounted;
            document.removeEventListener("shopify:section:unload", _4i);
        }
        document.addEventListener("shopify:section:unload", _4i);
        const _fzResubmit = function(value) {
            if (!_0.origin || !_0.plan || _m || _0.origin.kind === 'image') return false;
            const live = _k.context(),
                total = Object.keys(_0.selected || {}).length + Object.keys(_0.ranges || {}).length;
            const norm = v => String(v || '').normalize('NFKC').replace(/\s+/g, ' ').trim().toLowerCase();
            if (!total || String(live.country).toLowerCase() !== String(_0.origin.country).toLowerCase() || norm(value) !== norm(live.query)) return false;
            if (!_1y) run({
                kind: 'filters',
                plan: _0.plan,
                selection: _1b(_0.selected),
                ranges: _1b(_0.ranges),
                resubmit: true
            });
            return true;
        };
        _k.resubmitUnchanged = _fzResubmit;
        _k.submitPhotoExtras = function(extra) {
            if (!_0.origin || _0.origin.kind !== "image" || !_0.plan || _m) return false;
            const live = _k.context();
            if (live.image_base64 !== _0.origin.image_base64) return false;
            if (!_3o()) return false;
            if (!_1y) run({
                kind: "filters",
                plan: _0.plan,
                selection: _1b(_0.selected),
                ranges: _1b(_0.ranges),
                extraSpecs: extra
            });
            return true;
        };
        _r.dataset.findziaFiltersMounted = "156.7.21";
        _1m();
    }

    function _1n(_r) {
        if (!_r || !_r.classList || !_r.classList.contains("fz-home") || !_r.fzRefineBridge) return;
        if (_r.dataset.findziaFiltersMounted) return;
        try {
            const _4j = ["dialog", "rail", "status", "groups", "open", "apply", "clear", "retry", "cancel", "scroll", "close", "dialog-title", "category", "explainer", "draft-count"];
            if (!_r.querySelector("[data-refine]") || _4j.some(n => !_r.querySelector("[data-refine-" + n + "]"))) throw new Error("Incomplete filter markup");
            _23(_r);
            if (!_r.dataset.findziaFiltersMounted) throw new Error("Filters not mounted");
            _r.dataset.findziaFilterAsset = "ready";
            _r.dispatchEvent(new CustomEvent("fz:filters-ready", {
                bubbles: true
            }));
        } catch (_21) {
            _r.dataset.findziaFilterAsset = "error";
            console.error("Findzia filters initialization failed", _21);
            _r.dispatchEvent(new CustomEvent("fz:filters-error", {
                bubbles: true
            }));
        }
    }

    function _1t(_3a) {
        if (_3a && _3a.matches && _3a.matches(".fz-home")) _1n(_3a);
        if (_3a && _3a.querySelectorAll) _3a.querySelectorAll(".fz-home").forEach(_1n);
    }
    window.FindziaFiltersV15620 = {
        version: "156.7.21",
        mount: _1n,
        scan: _1t
    };
    _1t(document);
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function() {
        _1t(document);
    }, {
        once: true
    });
    document.addEventListener("shopify:section:load", function(_w) {
        _1t(_w.target);
    });
    document.addEventListener("fz:core-ready", function(_w) {
        _1n(_w.target);
    });
})();
window.FindziaFiltersV15548=window.FindziaFiltersV15620;
window.FindziaFiltersV15547=window.FindziaFiltersV15620;
window.FindziaFiltersV15543=window.FindziaFiltersV15620;
/* Findzia 156.7.15 — preferred 156.3 guided conversation + reviewed model picks. */
(()=>{'use strict';
const COPY={en:{title:'AI Shopping Assistant',overall:'Best Overall',quality:'Best Quality',budget:'Budget',discovery:'AI Pick',guided:'Help me choose',alternatives:'Find alternatives',start:'What matters to you?',close:'Close',back:'Back',loading:'Loading…',search:'Search',retry:'Try again',credit:'Each search uses 1 credit.',edit:'Refine your search',placeholder:'Add your preferences',unavailable:'Add what matters to you and search again.',fresh:'Choose a suggestion to start a new search.',same:'Search for this product',research:'Finding reviewed models…',reviews:'Sources',basis:'Selected from independent reviews',nomodes:'No reviewed picks for this search yet.',value:'Best Value',limitation:'Consider',searchmodel:'Find this model'},ar:{title:'مساعد التسوّق الذكي',overall:'الأفضل إجمالًا',quality:'أفضل جودة',budget:'اقتصادي',discovery:'ترشيح ذكي',guided:'ساعدني أختار',alternatives:'ابحث عن بدائل',start:'شنو الأهم لك؟',close:'إغلاق',back:'رجوع',loading:'جاري التحميل…',search:'ابحث',retry:'حاول مجددًا',credit:'كل بحث يستخدم رصيدًا واحدًا.',edit:'خصّص بحثك',placeholder:'أضف تفضيلاتك',unavailable:'أضف ما يهمك وابحث مجددًا.',fresh:'اختر اقتراحًا لبدء بحث جديد.',same:'ابحث عن هذا المنتج',research:'نبحث عن موديلات موصى بها…',reviews:'المصادر',basis:'اختيارات مبنية على مراجعات مستقلة',nomodes:'لا تتوفر ترشيحات موثوقة لهذا البحث حاليًا.',value:'أفضل قيمة',limitation:'خذ بعين الاعتبار',searchmodel:'ابحث عن هذا الموديل'}};
Object.assign(COPY.en,{sub:'A little guidance. A better choice.',needs:'Your use, budget, or what matters…',send:'Continue',answers:'Your answers',editanswers:'Change my answers',proposed:'Proposed search',applyneeds:'Search with these choices',tip:'One useful check',prefs:'Your shopping preferences',remember:'Remember my preferences on this device',privacy:'Save your searches and answers here only if you choose. Relevant preferences can help future guidance. You can edit or erase them.',none:'Nothing saved yet.',remove:'Remove',save:'Save',clear:'Erase saved preferences',previous:'Previous search',preference:'Your preference',guideloading:'Understanding your needs…',freeanswer:'Or tell me in your own words'});
Object.assign(COPY.ar,{sub:'نفهم احتياجك، ونوضح لك الخيارات.',needs:'استخدامك، ميزانيتك، أو الشي الأهم لك…',send:'متابعة',answers:'إجاباتك',editanswers:'غيّر إجاباتي',proposed:'البحث المقترح',applyneeds:'ابحث بهذه الاختيارات',tip:'شي يستحق التأكد',prefs:'تفضيلاتك في التسوق',remember:'احفظ تفضيلاتي على هذا الجهاز',privacy:'نحفظ بحثك وإجاباتك هنا باختيارك فقط. نستفيد من التفضيلات المرتبطة في المساعدة القادمة، وتقدر تعدّلها أو تمسحها.',none:'ما فيه تفضيلات محفوظة بعد.',remove:'حذف',save:'حفظ',clear:'امسح التفضيلات المحفوظة',previous:'بحث سابق',preference:'تفضيلك',guideloading:'نفهم احتياجك…',freeanswer:'أو اكتب اللي تبيه بطريقتك'});
const PREF_KEY='findzia-shopping-preferences-v1';
const privateSearch=/panadol|paracetamol|medicin|medicat|pain\s*relief|pregnan|diabet|antidepress|sexual|religio|politic|دواء|ادويه|أدوية|بنادول|بانادول|علاج|مسكن|حمل|جنس|سكري|اكتئاب|دين\b|سياس/i;
function clean(s,n=200){return String(s||'').replace(/\s+/g,' ').trim().slice(0,n);}
function loadProfile(){try{const p=JSON.parse(localStorage.getItem(PREF_KEY)||'null');if(p?.version===1)return{version:1,enabled:p.enabled===true,entries:(Array.isArray(p.entries)?p.entries:[]).filter(e=>e&&typeof e.query==='string'&&typeof e.preference==='string'&&e.at>Date.now()-90*864e5&&!privateSearch.test(e.query+' '+e.preference)).slice(-20).map(e=>({query:clean(e.query,180),preference:clean(e.preference,180),at:e.at}))};}catch(_){}return{version:1,enabled:false,entries:[]};}
function persist(profile){try{localStorage.setItem(PREF_KEY,JSON.stringify(profile));}catch(_){}}
const paths={overall:'M12 3 3 8l9 5 9-5-9-5ZM3 12l9 5 9-5M3 16l9 5 9-5',quality:'m12 3 2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1L3.2 9.4l6.1-.9L12 3Z',budget:'M20 12 12 20l-9-9V3h8l9 9ZM7 7h.01',discovery:'m12 3 2.2 6.8L21 12l-6.8 2.2L12 21l-2.2-6.8L3 12l6.8-2.2L12 3Z',guided:'M4 4h16v13H9l-5 4V4ZM8 9h8M8 13h5',arrow:'M5 12h14m-5-5 5 5-5 5'};
function node(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
function button(text,cls,fn){const b=node('button',cls,text);b.type='button';b.addEventListener('click',fn);return b;}
function icon(kind){const s=document.createElementNS('http://www.w3.org/2000/svg','svg');s.setAttribute('viewBox','0 0 24 24');s.setAttribute('fill','none');s.setAttribute('stroke','currentColor');s.setAttribute('stroke-width','1.6');s.setAttribute('stroke-linecap','round');s.setAttribute('stroke-linejoin','round');s.setAttribute('aria-hidden','true');s.innerHTML='<path d="'+(paths[kind]||paths.discovery)+'"/>';return s;}
function mount(root){
 if(root.dataset.guideMounted||!root.fzRefineBridge||!root.dataset.findziaFiltersMounted)return;
 const bridge=root.fzRefineBridge,top=root.querySelector('.fz-refine-top'),refine=root.querySelector('[data-refine]');if(!top||!refine)return;
 root.dataset.guideMounted='156.7.21';const t=k=>window.FindziaI18n?.t(COPY.en[k]||k,COPY.ar[k],root)||COPY[root.dataset.lang==='ar'?'ar':'en'][k]||k;
 let origin=null,mode='',answers=[],turns=[],data=null,overview=null,busy=false,controller=null,serial=0,disposed=false,returnFocus=null,profile=loadProfile();
 const trigger=button('','fz-guide-open',open);trigger.dataset.guideOpen='';trigger.setAttribute('aria-haspopup','dialog');trigger.append(icon('discovery'));top.append(trigger);
 const fallback=node('div','fz-guide-fallback');fallback.hidden=true;refine.after(fallback);
 const dialog=node('dialog','fz-guide');dialog.id=root.id+'-guide';dialog.setAttribute('aria-modal','true');dialog.setAttribute('aria-labelledby',dialog.id+'-title');trigger.setAttribute('aria-controls',dialog.id);
 const head=node('header','fz-guide-head'),title=node('h2','',t('title'));title.id=dialog.id+'-title';title.tabIndex=-1;
 const close=button('×','fz-guide-close',()=>dialog.close());head.append(title,close);
 const body=node('div','fz-guide-body'),footer=node('footer','fz-guide-footer'),form=node('form','fz-guide-form fz-guide-answer-form'),input=node('textarea','fz-guide-input'),send=node('button','fz-guide-primary');
 input.rows=2;input.maxLength=200;input.dir='auto';input.autocomplete='off';send.type='submit';form.append(input,send);footer.hidden=true;dialog.append(head,body);root.append(dialog);
 form.addEventListener('submit',e=>{e.preventDefault();const answer=clean(input.value);if(!answer||busy)return;input.value='';answerWith(answer);});
 function sameContext(a,b){return a&&b&&['generation',a.kind==='image'?'image_base64':'query','country','lang','kind','extra_specs'].every(k=>(a[k]||'')===(b[k]||''));}
 function remember(answer){if(!profile.enabled||!origin||privateSearch.test(origin.query+' '+answer))return;const query=clean(origin.query,180),preference=clean(answer,180);if(!query||!preference)return;profile.entries=profile.entries.filter(e=>e.query!==query||e.preference!==preference);profile.entries.push({query,preference,at:Date.now()});profile.entries=profile.entries.slice(-20);persist(profile);}
 function answerWith(answer){if(busy||!origin)return;turns.push({question:data?.question||'',question_key:data?.question_key||'',answer:clean(answer),search_query:data?.search_query||''});turns=turns.slice(-6);answers=turns.map(t=>t.answer);remember(answer);data=null;discover();}

 function cancel(){serial++;controller?.abort();controller=null;busy=false;}
 function update(){if(disposed)return;const c=bridge.context();trigger.title=t('title');trigger.setAttribute('aria-label',t('title'));trigger.hidden=!c.query||root.dataset.homeState==='empty';trigger.disabled=!!c.busy&&!c.can_refine;trigger.dataset.guideAvailable=String(!trigger.hidden&&!trigger.disabled);fallback.hidden=!refine.hidden||trigger.hidden;const host=refine.hidden?fallback:top;if(trigger.parentElement!==host)host.append(trigger);
  if(origin&&!sameContext(origin,c)){cancel();origin=null;mode='';data=null;overview=null;if(dialog.open)dialog.close();}
 }
 function open(){update();if(trigger.hidden||trigger.disabled)return;const c=bridge.context();if(!sameContext(origin,c)){origin={...c};mode='';answers=[];turns=[];data=null;overview=null;input.value='';}returnFocus=document.activeElement;dialog.dir=['ar','ur'].includes(root.dataset.lang)?'rtl':'ltr';title.textContent=t('title');close.setAttribute('aria-label',t('close'));dialog.dataset.theme=root.dataset.theme;input.placeholder=t('needs');input.setAttribute('aria-label',t('needs'));send.textContent=t('send');if(!dialog.open)dialog.showModal();window.FindziaModalScroll.lock(dialog);render();title.focus({preventScroll:true});if(!mode&&!overview)loadOverview();else if(mode&&!data)discover();}
 async function request(path,payload,timeout){cancel();const id=++serial,ctl=new AbortController();controller=ctl;busy=true;render();
  // The deadline covers account bootstrap AND response.json(), even if a
  // wrapper/provider ignores AbortSignal. Closing the dialog settles it too.
  let abort;const stopped=new Promise(resolve=>{abort=()=>resolve({ok:false});ctl.signal.addEventListener('abort',abort,{once:true});});
  const timer=setTimeout(()=>ctl.abort(),timeout);
  try{const work=(async()=>{const response=await window.FindziaBillingFetch(root,bridge.api.replace(/\/$/,'')+path,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'omit',signal:ctl.signal,body:JSON.stringify(payload)});const value=await response.json();return response.ok&&value?.ok?value:{ok:false};})();
   const value=await Promise.race([work,stopped]);return id===serial&&!disposed?value:null;
  }catch(_){return id===serial&&!disposed?{ok:false}:null;}
  finally{clearTimeout(timer);ctl.signal.removeEventListener('abort',abort);if(id===serial){busy=false;controller=null;}}
 }
 async function loadOverview(){const result=await request('/api/guide/discover',{query:origin.query,kind:origin.kind,extra_specs:origin.extra_specs||'',country:origin.country,lang:root.dataset.lang,mode:'overview',answers:[]},24500);if(!result)return;overview=result;render();}
 async function choose(value){if(!origin)return;cancel();mode=value;answers=[];turns=[];input.value='';data=null;if(overview?.groups?.[value]?.length){data={ok:true,suggestions:overview.groups[value]};render();return;}await discover();}
 async function discover(){const payload={query:origin.query,kind:origin.kind,extra_specs:origin.extra_specs||'',country:origin.country,lang:root.dataset.lang,mode,answers};if(mode==='guided')Object.assign(payload,{guided_version:2,turns,history:profile.enabled?loadProfile().entries:[]});const result=await request('/api/guide/discover',payload,mode==='guided'?12500:24500);if(!result)return;data=result;render();}
 function search(query,refinement=false){if(busy||!query?.trim()||!origin)return;const c=bridge.context();if(!sameContext(origin,c))return;const launch=refinement&&origin.kind==='image'?bridge.guideSearch:bridge.guideDiscoverSearch||bridge.accountSearch;if(typeof launch!=='function')return;if(launch(query.trim(),origin.country)!==false)dialog.close();}
 function status(){const n=node('p','fz-guide-status',t(mode==='guided'?'guideloading':mode?'loading':'research'));n.setAttribute('role','status');n.setAttribute('aria-busy','true');body.append(n);}
 function render(){footer.hidden=mode!=='guided';send.disabled=busy;body.replaceChildren();body.setAttribute('aria-busy',String(busy));body.append(node('p','fz-guide-context',origin?.query||''));
  if(!mode){
   body.append(node('h3','fz-guide-question',t('start')));if(busy)status();else if(!overview?.available_modes?.length)body.append(node('p','fz-guide-note',t('nomodes')));const grid=node('div','fz-guide-mode-grid');for(const key of [...['overall','quality','budget','discovery'].filter(k=>overview?.groups?.[k]?.length),'guided']){const b=button('','fz-guide-mode'+(key==='guided'?' fz-guide-mode-guided':''),()=>choose(key));b.dataset.guideMode=key;b.append(icon(key),node('span','',t(key==='budget'?'value':key)));if(key==='guided'){const arrow=icon('arrow');arrow.classList.add('fz-guide-mode-arrow');b.append(arrow);}grid.append(b);}const alternatives=button(t('alternatives'),'fz-guide-text fz-guide-alternatives',()=>choose('alternatives'));alternatives.dataset.guideAlternatives='';body.append(grid,alternatives);return;
  }
  const back=button(t('back'),'fz-guide-text',()=>{cancel();mode='';data=null;answers=[];turns=[];input.value='';render();if(!overview)loadOverview();});body.append(back);
  if(mode==='guided'&&answers.length){const chips=node('div','fz-guide-answers');chips.setAttribute('aria-label',t('answers'));chips.setAttribute('data-no-i18n','');answers.forEach(a=>chips.append(node('span','',a)));body.append(chips);}
  if(busy){status();return;}
  if(mode==='guided'){renderGuided();return;}
  if(data?.question&&data.choices?.length>=2){body.append(node('h3','fz-guide-question',data.question));const options=node('div','fz-guide-options');for(const choice of data.choices.slice(0,4))options.append(button(choice.label,'fz-guide-choice',()=>{if(busy)return;answers.push(choice.answer||choice.label);data=null;discover();}));body.append(options);return;}
  if(data?.suggestions?.length){body.append(node('h3','fz-guide-question',t(mode==='budget'?'value':mode)),node('p','fz-guide-note',data.suggestions.some(s=>s.basis==='review_inference')?t('basis'):t('fresh')));const list=node('div','fz-guide-suggestions');for(const suggestion of data.suggestions.slice(0,3)){
    const card=node('article','fz-guide-suggestion');card.append(node('h3','',suggestion.title));if(suggestion.reason)card.append(node('p','',suggestion.reason));if(suggestion.tradeoff)card.append(node('p','fz-guide-tradeoff',t('limitation')+': '+suggestion.tradeoff));const sources=node('div','fz-guide-sources');for(const source of suggestion.sources||[]){try{const url=new URL(source.url);if(!['https:','http:'].includes(url.protocol)||url.username||url.password)continue;const a=node('a','',url.hostname.replace(/^www\./,''));a.href=url.href;a.target='_blank';a.rel='noopener noreferrer';a.title=source.title||a.textContent;sources.append(a);}catch(_){}}if(sources.children.length){sources.setAttribute('aria-label',t('reviews'));card.append(sources);}const b=button(t(suggestion.basis==='review_inference'?'searchmodel':'search'),'fz-guide-primary',()=>search(suggestion.search_query));b.dataset.suggestionSearch=suggestion.search_query;card.append(b);list.append(card);
   }body.append(list,node('p','fz-guide-note',t('credit')));return;}
  // A provider failure never substitutes or relabels the customer's existing cards.
  body.append(node('p','fz-guide-note',t('unavailable')));const form=node('form','fz-guide-form'),label=node('label','',t('edit')),input=node('input');input.type='text';input.value=origin.query;input.maxLength=240;input.dir='auto';label.append(input);const submit=node('button','fz-guide-primary',t('search'));submit.type='submit';form.append(label,submit);form.addEventListener('submit',e=>{e.preventDefault();search(input.value);});body.append(form,button(t('retry'),'fz-guide-text',discover),node('p','fz-guide-note',t('credit')));
 }
 function renderGuided(){
  if(data?.intro)body.append(node('p','fz-guide-intro',data.intro));
  if(data?.question&&data.choices?.length>=2){body.append(node('h3','fz-guide-question',data.question));const options=node('div','fz-guide-options');for(const choice of data.choices.slice(0,4))options.append(button(choice.label,'fz-guide-choice',()=>answerWith(choice.answer||choice.label)));body.append(options);}
  if(data?.next_tip)body.append(node('p','fz-guide-tip',t('tip')+' · '+data.next_tip));
  if(data?.search_query){const box=node('form','fz-guide-search'),label=node('label','',t('proposed')),query=node('textarea','fz-guide-proposed');query.rows=2;query.maxLength=240;query.value=data.search_query;query.dir='auto';query.setAttribute('aria-label',t('proposed'));label.append(query);const apply=node('button','fz-guide-primary',t('applyneeds'));apply.type='submit';apply.dataset.guideRefineSearch='';box.append(label,apply,node('p','fz-guide-note',t('credit')));box.addEventListener('submit',e=>{e.preventDefault();search(query.value,true);});body.append(box);}
  if(!data?.question&&!data?.search_query){body.append(node('p','fz-guide-note',t('unavailable')),button(t('retry'),'fz-guide-text',discover));const manual=node('form','fz-guide-form'),label=node('label','',t('edit')),q=node('input');q.value=origin.kind==='image'?(origin.extra_specs||answers.join(' ')):[origin.query,...answers].join(' ');q.maxLength=240;q.dir='auto';label.append(q);const go=node('button','fz-guide-primary',t('search'));go.type='submit';manual.append(label,go);manual.addEventListener('submit',e=>{e.preventDefault();search(q.value,true);});body.append(manual);}
  if(answers.length)body.append(button(t('editanswers'),'fz-guide-text',()=>{answers=[];turns=[];data=null;discover();}));
  const more=node('details','fz-guide-free-answer');more.append(node('summary','',t('freeanswer')),form);body.append(more);renderPreferences();
 }
 function renderPreferences(){const details=node('details','fz-guide-preferences');details.append(node('summary','',t('prefs')));const label=node('label','fz-guide-pref-toggle'),check=node('input');check.type='checkbox';check.checked=profile.enabled;check.dataset.guideRemember='';label.append(check,document.createTextNode(t('remember')));details.append(label,node('p','fz-guide-note',t('privacy')));const list=node('div');details.append(list);
  check.addEventListener('change',()=>{profile.enabled=check.checked;persist(profile);if(profile.enabled)answers.forEach(remember);renderList();});
  function renderList(){list.replaceChildren();if(!profile.entries.length)list.append(node('p','fz-guide-note',t('none')));else{profile.entries.slice().reverse().forEach(entry=>{const row=node('div','fz-guide-pref-row'),q=node('input'),a=node('input');q.value=entry.query;a.value=entry.preference;q.maxLength=a.maxLength=180;q.dir=a.dir='auto';q.setAttribute('aria-label',t('previous'));a.setAttribute('aria-label',t('preference'));const actions=node('div','fz-guide-pref-actions');actions.append(button(t('save'),'fz-guide-text',()=>{if(privateSearch.test(q.value+' '+a.value))return;entry.query=clean(q.value,180);entry.preference=clean(a.value,180);entry.at=Date.now();profile.entries=profile.entries.filter(x=>x.query&&x.preference);persist(profile);renderList();}),button(t('remove'),'fz-guide-text',()=>{profile.entries=profile.entries.filter(x=>x!==entry);persist(profile);renderList();}));row.append(q,a,actions);list.append(row);});list.append(button(t('clear'),'fz-guide-text',()=>{profile.entries=[];profile.enabled=false;check.checked=false;persist(profile);renderList();}));}}
  renderList();body.append(details);
 }
 function storageChanged(event){if(event.key===PREF_KEY){profile=loadProfile();if(dialog.open&&!busy)render();}}
 window.addEventListener('storage',storageChanged);
 dialog.addEventListener('close',()=>{cancel();window.FindziaModalScroll.unlock(dialog);if(returnFocus?.isConnected)returnFocus.focus({preventScroll:true});});
 dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
 const observer=new MutationObserver(update);observer.observe(root,{attributes:true,attributeFilter:['data-lang','data-home-state']});const hiddenObserver=new MutationObserver(update);hiddenObserver.observe(refine,{attributes:true,attributeFilter:['hidden']});
 const events=['fz:search-state','fz:search-reset','fz:filters-ready'];events.forEach(name=>root.addEventListener(name,update));
 document.addEventListener('shopify:section:unload',function cleanup(e){if(!e.target?.contains(root))return;disposed=true;cancel();window.removeEventListener('storage',storageChanged);window.FindziaModalScroll.unlock(dialog);observer.disconnect();hiddenObserver.disconnect();events.forEach(name=>root.removeEventListener(name,update));dialog.remove();trigger.remove();fallback.remove();delete root.dataset.guideMounted;document.removeEventListener('shopify:section:unload',cleanup);});update();
}
const style=node('style');style.textContent=`
.fz-guide{--g-bg:#fff;--g-line:#e1e6df;--g-ink:#20312a;--g-muted:#59675e;--g-soft:#f3f5f2;--g-accent:#354e3f;--g-on:#fff;box-sizing:border-box;width:min(560px,calc(100vw - 24px));max-width:none;height:auto;max-height:88vh;max-height:88dvh;margin:auto;padding:0;border:1px solid var(--g-line);border-radius:18px;color:var(--g-ink);background:var(--g-bg);overflow:auto;overscroll-behavior:contain;touch-action:pan-y;-webkit-overflow-scrolling:touch;font-family:inherit}
.fz-guide[data-theme=dark]{--g-bg:#202622;--g-line:#465348;--g-ink:#f5f6f0;--g-muted:#bcc7bd;--g-soft:#303b32;--g-accent:#dce5d1;--g-on:#202622}.fz-home[id] dialog.fz-guide[open]{display:block;height:auto}.fz-guide::backdrop{background:#15221c70;backdrop-filter:blur(5px)}.fz-guide *{box-sizing:border-box}.fz-guide [hidden]{display:none!important}.fz-guide button,.fz-guide input{font:inherit}.fz-guide button{cursor:pointer}.fz-guide button:focus-visible,.fz-guide input:focus-visible{outline:2px solid var(--g-accent);outline-offset:3px}.fz-home[id] dialog.fz-guide .fz-guide-head h2:focus{outline:none!important;box-shadow:none!important}
.fz-guide-head{position:sticky;top:0;z-index:1;background:var(--g-bg);display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 20px;border-bottom:1px solid var(--g-line);flex:none}.fz-guide-head h2{font-size:19px;line-height:1.4;font-weight:650;margin:0}.fz-guide-close{width:40px;height:40px;border-radius:12px;border:1px solid var(--g-line);background:none;color:inherit;font-size:26px!important;flex:none}.fz-home[id] dialog.fz-guide .fz-guide-body{display:block;height:auto;max-height:none;padding:20px;overflow:visible;min-height:120px;flex:none}.fz-guide-context{font-size:13px;line-height:1.6;color:var(--g-muted);margin:0 0 16px;overflow-wrap:anywhere}.fz-guide-question{font-size:19px;line-height:1.5;font-weight:600;margin:4px 0 16px}.fz-guide-mode-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.fz-guide-mode{display:flex;align-items:center;gap:12px;min-height:72px;padding:16px 13px;background:var(--g-bg);color:var(--g-ink);border:1px solid var(--g-line);border-radius:12px;text-align:start;font-size:14px!important;font-weight:600!important}.fz-guide-mode:hover,.fz-guide-choice:hover{background:var(--g-soft);border-color:var(--g-accent)}.fz-guide-mode svg{width:22px;height:22px;flex:none;color:var(--g-accent)}.fz-guide-mode span{overflow-wrap:anywhere}.fz-guide-mode-guided{grid-column:1/-1;background:var(--g-soft);border-color:color-mix(in srgb,var(--g-accent) 24%,var(--g-line))}.fz-guide-mode-guided span{flex:1}.fz-guide-mode .fz-guide-mode-arrow{width:18px;height:18px;opacity:.75}.fz-guide[dir=rtl] .fz-guide-mode-arrow{transform:scaleX(-1)}.fz-guide-alternatives{margin-top:8px}.fz-guide-text{background:none;border:0;color:var(--g-accent);font-size:13px!important;min-height:44px;padding:10px 0;text-decoration:underline;text-underline-offset:3px;text-align:start}.fz-guide-status{font-size:14px;padding:22px 0;color:var(--g-muted);margin:0}.fz-guide-status:before{content:'';display:inline-block;width:12px;height:12px;margin-inline-end:10px;border:2px solid var(--g-line);border-top-color:var(--g-accent);border-radius:50%;animation:fzg-spin .8s linear infinite}@keyframes fzg-spin{to{transform:rotate(360deg)}}
.fz-guide-primary{display:block;width:100%;min-height:46px;padding:12px 16px;border:0;border-radius:10px;color:var(--g-on);background:var(--g-accent);font-size:14px!important;font-weight:600!important}.fz-guide-primary:disabled{opacity:.6;cursor:default}.fz-guide-note{font-size:12px;line-height:1.7;color:var(--g-muted);margin:14px 0}.fz-guide-options{display:grid;gap:10px}.fz-guide-choice{min-height:48px;padding:12px 15px;text-align:start;border:1px solid var(--g-line);border-radius:10px;background:var(--g-bg);color:inherit;font-size:14px!important}.fz-guide-suggestions{display:grid;gap:12px}.fz-guide-suggestion{padding:18px;border:1px solid var(--g-line);border-radius:12px}.fz-guide-suggestion h3{font-size:16px;font-weight:600;line-height:1.5;margin:0;overflow-wrap:anywhere}.fz-guide-suggestion p{font-size:13px;line-height:1.6;color:var(--g-muted);margin:8px 0 14px}.fz-guide-suggestion .fz-guide-primary{margin-top:16px}.fz-guide-sources{display:flex;flex-wrap:wrap;gap:6px 12px;margin-top:12px}.fz-guide-sources a{color:var(--g-accent);font-size:12px;line-height:1.7;text-decoration:underline;text-underline-offset:3px;overflow-wrap:anywhere}.fz-guide-suggestion .fz-guide-tradeoff{border-inline-start:2px solid var(--g-line);padding-inline-start:10px}.fz-guide-form label{display:block;font-size:13px}.fz-guide-form input{display:block;min-height:46px;width:100%;margin:8px 0 14px;padding:10px;border:1px solid var(--g-line);border-radius:8px;background:var(--g-bg);color:var(--g-ink);font-size:16px}
.fz-home .fz-guide-open{width:42px;height:42px;display:inline-flex;align-items:center;justify-content:center;border:1px solid var(--fz-line,#e1e6df);border-radius:12px;background:transparent;color:var(--fz-ink,#20312a);cursor:pointer;flex:none}.fz-guide-open svg{width:20px;height:20px}.fz-home .fz-guide-open[hidden],.fz-home .fz-guide-fallback[hidden]{display:none!important}.fz-guide-open:disabled{opacity:.45}.fz-guide-fallback{display:flex}.fz-home[id][data-theme] .fz-results-tools [data-refine-open][hidden]{display:none!important}
.fz-guide textarea{font:inherit;color:var(--g-ink);background:var(--g-bg);font-size:16px;line-height:1.6;resize:vertical;min-height:48px;max-height:140px;border:1px solid var(--g-line);border-radius:12px;padding:12px;width:100%;outline-offset:3px}.fz-guide textarea:focus-visible{outline:2px solid var(--g-accent)}.fz-guide-footer{position:sticky;bottom:0;padding:12px 20px max(12px,env(safe-area-inset-bottom));background:var(--g-bg);border-top:1px solid var(--g-line);z-index:1}.fz-guide-answer-form{display:flex;align-items:flex-end;gap:10px}.fz-guide-answer-form textarea{min-width:0;flex:1;resize:none}.fz-guide-answer-form .fz-guide-primary{width:auto;flex:none;min-height:48px}.fz-guide-answers{display:flex;gap:8px;flex-wrap:wrap;margin:4px 0 18px}.fz-guide-answers span{font-size:13px;line-height:1.5;padding:7px 11px;border-radius:10px;background:var(--g-soft);overflow-wrap:anywhere}.fz-guide-intro{font-size:15px;line-height:1.7;margin:0 0 16px}.fz-guide-tip{font-size:13px;line-height:1.8;padding-inline-start:12px;border-inline-start:2px solid var(--g-line);margin:20px 0}.fz-guide-search{margin:20px 0 8px;padding:16px;border-radius:14px;background:var(--g-soft)}.fz-guide-search label{font-size:13px;line-height:1.7}.fz-guide-search textarea{display:block;margin:8px 0 12px}.fz-guide-search .fz-guide-note{margin-bottom:0}.fz-guide-preferences{border-top:1px solid var(--g-line);margin-top:16px;padding-top:12px}.fz-guide-preferences summary{font-size:13px;line-height:1.7;cursor:pointer;min-height:40px;padding:8px 0}.fz-guide-pref-toggle{display:flex;align-items:center;gap:10px;font-size:13px;line-height:1.6}.fz-guide-pref-toggle input{width:18px;height:18px;accent-color:var(--g-accent);flex:none}.fz-guide-pref-row{padding:12px;background:var(--g-soft);border-radius:12px;margin:10px 0}.fz-guide-pref-row input{width:100%;min-height:44px;font-size:16px;color:var(--g-ink);background:var(--g-bg);border:1px solid var(--g-line);border-radius:8px;padding:8px;margin:4px 0}.fz-guide-pref-actions{display:flex;gap:20px}
@media(max-width:360px){.fz-guide-mode-grid{grid-template-columns:1fr}}@media(prefers-reduced-motion:reduce){.fz-guide-status:before{animation:none}}
`;document.head.append(style);
const boot=()=>document.querySelectorAll('.fz-home').forEach(mount);boot();let attempts=0;const timer=setInterval(()=>{boot();if(++attempts>80||[...document.querySelectorAll('.fz-home')].every(r=>r.dataset.guideMounted))clearInterval(timer);},250);document.addEventListener('shopify:section:load',boot);document.addEventListener('fz:filters-ready',boot);
})();
