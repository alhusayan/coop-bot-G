# -*- coding: utf-8 -*-
import os, re, time, base64, requests, json, asyncio, urllib.parse, hashlib
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import HTMLResponse
from bs4 import BeautifulSoup

app = FastAPI()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_COOP_BOT_TOKEN")

GRAPH_URL = "https://graph.facebook.com/v20.0"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

processed_ids = deque(maxlen=1000)
IMAGE_BUFFER = defaultdict(lambda: {"images": [], "time": 0, "bot_id": ""})
LAST_SEARCH = {}
USER_LANG = {}
PENDING_IMAGES = defaultdict(lambda: {"images": [], "bot_id": ""})
PENDING_ALTS = {}  # from_number -> {"alts": [...], "bot_id":..., "lang":..., "ts":...}

BUFFER_SECONDS = 4
RESOLVER = ThreadPoolExecutor(max_workers=6)
WORKERS = ThreadPoolExecutor(max_workers=3)
SEARCH_POOL = ThreadPoolExecutor(max_workers=8)
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

SEARCH_CACHE = {}
CACHE_TTL = int(os.environ.get("CACHE_TTL_HOURS", "2")) * 3600
CACHE_MAX = 500
CACHE_MIN_STORES = 1
CACHE_MIN_LINKS = 1

# ===== كاش صفحات المتاجر المتحقق منها =====
VERIFIED_PAGE_CACHE = {} # url -> {"data": {...}, "ts":...}
OOS_PHRASES = ["out of stock","غير متوفر","نفدت الكمية","غير متاح","sold out","غير متوفر حاليا","نفذت","not available","temporarily unavailable"]
LISTING_URL_PARTS = ["/search","/s?","/category","/categories","/collection","/collections","/shop/category","?q=","/search_results","/shop/","/listing","/c/"]

def format_price(p):
    try:
        pf = float(p)
        if pf < 100:
            return f"{pf:.3f}".rstrip('0').rstrip('.')
        return f"{pf:.2f}".rstrip('0').rstrip('.')
    except:
        return str(p)

def result_quality(txt, urls):
    return len(extract_store_names(txt or "")), len(urls or {})

def fallback_search_url(query, store=""):
    dom = store_domain(store) if store else ""
    if dom:
        return "https://www.google.com/search?q=" + urllib.parse.quote(f"site:{dom} {query}")
    q = f"{query} {store} الكويت اونلاين".strip() if store else f"{query} الكويت اونلاين"
    return "https://www.google.com/search?q=" + urllib.parse.quote(q)

def normalize_ar(text):
    t = (text or "").lower()
    t = re.sub(r"[أإآ]", "ا", t)
    t = t.replace("ة", "ه").replace("ى", "ي").replace("ئ", "ي").replace("ؤ", "و")
    t = t.replace("ري بان", "ريبان").replace("راي بان", "ريبان").replace("ray ban", "rayban").replace("ray-ban", "rayban")
    return t

def norm_tokens(query):
    t = normalize_ar(query)
    toks = re.findall(r"[\w\u0600-\u06FF]+", t)
    toks = [w[2:] if w.startswith("ال") and len(w) > 4 else w for w in toks]
    return set(toks)

def has_model_token(a, b):
    def models(s): return {t for t in s if re.search(r"\d", t) and re.search(r"[a-z\u0600-\u06FF]", t) and len(t) >= 4}
    return bool(models(a) & models(b))

def cache_key(query, lang):
    norm = re.sub(r"[^\w\u0600-\u06FF]+", "", normalize_ar(query))
    return hashlib.sha256(f"{norm}|{lang}".encode()).hexdigest()

def cache_get(query, lang):
    now = time.time()
    hit = SEARCH_CACHE.get(cache_key(query, lang))
    if hit and (now - hit["ts"]) < CACHE_TTL:
        print(f"CACHE HIT (exact): {query[:60]}")
        return hit["txt"], dict(hit["urls"]), list(hit.get("alts", []))
    qt = norm_tokens(query)
    if not qt: return None
    best, best_score = None, 0.0
    for entry in SEARCH_CACHE.values():
        if entry.get("lang") != lang or (now - entry["ts"]) >= CACHE_TTL: continue
        et = entry.get("tokens") or set()
        if not et: continue
        inter = len(qt & et)
        score = inter / len(qt | et) if (qt | et) else 0
        if has_model_token(qt, et): score += 0.30
        if score > best_score: best, best_score = entry, score
    if best and best_score >= 0.60:
        print(f"CACHE HIT (fuzzy {best_score:.2f}): {query[:50]} ~ {best.get('query','')[:50]}")
        return best["txt"], dict(best["urls"]), list(best.get("alts", []))
    return None

def cache_put(query, lang, txt, urls, alts=None):
    if not txt: return
    if len(SEARCH_CACHE) >= CACHE_MAX:
        oldest = min(SEARCH_CACHE, key=lambda k: SEARCH_CACHE[k]["ts"])
        SEARCH_CACHE.pop(oldest, None)
    SEARCH_CACHE[cache_key(query, lang)] = {
        "txt": txt, "urls": dict(urls), "ts": time.time(),
        "tokens": norm_tokens(query), "query": query, "lang": lang,
        "alts": list(alts or []),
    }

IDENTIFY_SYSTEM = """أنت خبير تعرف على المنتجات. انظر للصورة واكتب الاسم التجاري القياسي للمنتج بصيغة ثابتة دائماً:
[البراند] [نوع المنتج] [رقم الموديل باللاتيني إن ظهر] [اللون/النكهة] [الحجم/الوزن إن ظهر]
رقم الموديل هو أهم عنصر — دور عليه على العبوة أو الذراع أو الملصق (مثل RB3721، SM-S928، MQ2V3).
أمثلة:
- ريبان نظارة شمسية RB3721 اسود 59 مم
- برينجلز كاتشب 200 جرام
سطر واحد فقط."""

MATCH_SYSTEM = """أنت مدقق مطابقة منتجات صارم جداً.
سأعطيك: (1) المنتج المطلوب، (2) قائمة مرقمة بعناوين صفحات منتجات من متاجر.
لكل عنوان قرر واحدة فقط:
- EXACT: نفس المنتج بالضبط — نفس البراند + نفس الموديل/النكهة إن ذُكر + نفس الحجم/اللون إن ذُكر. اختلاف اللغة (عربي/إنجليزي) لا يعتبر اختلافاً.
- SIMILAR: نفس البراند أو نفس فئة المنتج لكن موديل مختلف، حجم مختلف، لون مختلف، نكهة مختلفة، أو إصدار مختلف.
- WRONG: منتج مختلف تماماً أو عنوان غير مفهوم أو فارغ.
قواعد:
- إذا المطلوب فيه رقم موديل والعنوان فيه رقم موديل مختلف = SIMILAR وليس EXACT.
- إذا العنوان ما يذكر الموديل أصلاً والمطلوب فيه موديل = SIMILAR (لا تفترض).
- الشك = SIMILAR وليس EXACT.
رد فقط بأسطر بهذه الصيغة بدون أي كلام إضافي:
1=EXACT
2=SIMILAR
3=WRONG"""

MSG = {
    "ar": {
        "identifying": "ثواني بس.. أحدد المنتج وأدور لك الأفضل!",
        "searching": "🔍 أدور لك على {q}...",
        "not_found": "ما لقيت المنتج متوفر حالياً بسعر مؤكد 😅 جرب صياغة ثانية أو دز صورة أوضح.",
        "cant_identify": "ما قدرت أحدد المنتج، دز صورة أوضح",
        "multi_text": "تمام لقيت {c} منتجات، أسوي سلة...",
        "multi_images": "تمام لقطت {c} منتجات، أسوي سلة...",
        "maps_body": "📍 تبي أقرب مكان؟\n\nاضغط الزر والخريطة بتفتح على أقرب الأماكن حولك 👇",
        "maps_btn": "📍 افتح الخريطة",
        "maps_body_loc": "📍 بحثك الأخير كان عن ({p})\n\nجهزت لك أقرب الأماكن حولك، اضغط الزر وافتح الخريطة 👇",
        "no_saved_product": "ما عندي منتج محفوظ حالياً 😅. ابحث عن منتج أول، وبعدها أدلك على أقرب مكان يبيعه!",
        "lang_saved": "تمام، بكلمك عربي من هني ورايح 🇰🇼\nدز صورة منتج أو اكتب اسمه وأنا حاضر!",
        "alts_offer": "👀 لقيت بعد بدائل مشابهة (مو طبق الأصل) — تبي أعرضها لك؟",
        "alts_offer_no_exact": "ما لقيت المنتج *طبق الأصل* متوفر بسعر مؤكد 😅\nبس عندي بدائل مشابهة قريبة منه — تبيها؟",
        "alts_yes_btn": "✅ عرض البدائل",
        "alts_no_btn": "❌ لا شكراً",
        "alts_ok": "تمام 👍 إذا تبي شي ثاني أنا حاضر!",
        "alts_none": "ما عندي بدائل محفوظة حالياً 😅",
        "alt_tag": "🔄 بديل مشابه",
        "cart_alt_note": "(ما لقيت طبق الأصل — هذا أقرب بديل)",
    },
    "en": {
        "identifying": "One sec.. identifying the product and finding you the best deal!",
        "searching": "🔍 Looking up {q}...",
        "not_found": "Couldn't find it in-stock with a verified price 😅 try another phrasing or a clearer photo.",
        "cant_identify": "Couldn't identify the product",
        "multi_text": "Got it, found {c} products. Building your cart...",
        "multi_images": "Nice, spotted {c} products. Building your cart...",
        "maps_body": "📍 Want the nearest place?\n\nTap the button and the map will open on the closest spots around you 👇",
        "maps_btn": "📍 Open Map",
        "maps_body_loc": "📍 Your last search was ({p})\n\nI've lined up the closest places around you. Tap the button to open the map 👇",
        "no_saved_product": "I don't have a saved product yet 😅. Search for a product first, then I'll point you to the nearest store!",
        "lang_saved": "Great, I'll speak English with you from now on 🇬🇧\nSend a product photo or type its name and I'm on it!",
        "alts_offer": "👀 I also found similar alternatives (not the exact one) — want to see them?",
        "alts_offer_no_exact": "Couldn't find the *exact* product in stock with a verified price 😅\nBut I've got close alternatives — want them?",
        "alts_yes_btn": "✅ Show alternatives",
        "alts_no_btn": "❌ No thanks",
        "alts_ok": "Got it 👍 I'm here if you need anything else!",
        "alts_none": "No saved alternatives right now 😅",
        "alt_tag": "🔄 Similar alternative",
        "cart_alt_note": "(exact match not found — closest alternative)",
    },
}

LANG_INSTR = {
    "ar": "رد باللغة العربية فقط.",
    "en": "Respond ONLY in English. Keep the exact same response format and emojis, but translate all labels to English — including writing (Phone: NUMBER) instead of (هاتف: رقم). Keep prices in KWD.",
}

def T(lang, key, **kw):
    return MSG.get(lang, MSG["ar"])[key].format(**kw) if kw else MSG.get(lang, MSG["ar"])[key]

def detect_lang(text):
    if re.search(r"[\u0600-\u06FF]", text or ""): return "ar"
    if re.search(r"[A-Za-z]", text or ""): return "en"
    return None

SYSTEM_PROMPT = """
أنت مساعد تسوق كويتي. استخدم بحث Google فعلياً للأسعار والتقييمات الحالية في الكويت.

أولاً حدد نوع الطلب:

【الحالة 1】منتج محدد بعلامة تجارية واضحة (مثل: آيفون 15 برو، بيبسي، ساعة أبل الترا، بلايستيشن 5):
قارن الأسعار واختر الأرخص، ورد بهذا الشكل فقط:
📦 [اسم المنتج]

✅ [المتجر الأرخص] — [السعر] د.ك
• [المتجر الثاني] — [السعر] د.ك
• [المتجر الثالث] — [السعر] د.ك

⛔ قاعدة المطابقة الحرفية: المنتج في النتائج يجب أن يكون نفس المنتج المطلوب حرفياً — نفس البراند ونفس الموديل ونفس الحجم/اللون إن ذُكر. ممنوع اقتراح موديل قريب أو حجم مختلف في القائمة الرئيسية.

🛒 مصدر العروض ClicFlyer — قاعدة إلزامية لمنتجات التموينات:
لأي منتج بقالة أو تموينات (أغذية، مشروبات، منظفات، عناية شخصية)، نفّذ دائماً بحثاً إضافياً في clicflyer.com (استخدم site:clicflyer.com مع اسم المنتج).
- إذا وجدت عرضاً سارياً أرخص، حطه أول القائمة واكتب (عرض).

【الحالة 2】طلب عام بدون براند محدد (مثل: قهوة فلات وايت حار، عطر رجالي، لابتوب للدراسة):
لا تبحث عن الأرخص! ابحث عن الأفضل تقييماً في الكويت بسعر مناسب.
📦 [وصف الطلب]
🏆 [اسم الخيار الأفضل + مكانه/متجره] — [السعر] د.ك ⭐ [التقييم من 5]
• [خيار ثاني] — [السعر] د.ك ⭐ [التقييم]
• [خيار ثالث] — [السعر] د.ك ⭐ [التقييم]

【الحالة 3】طلب خدمة (فني، بنشر، تبديل بطارية، سباك...):
📦 [وصف الخدمة + المنطقة]
🏆 [اسم المزود] (هاتف: [الرقم]) — [المنطقة] — [السعر] د.ك ⭐ [التقييم]
• [مزود ثاني] (هاتف: [الرقم]) — [المنطقة] — [السعر] د.ك ⭐ [التقييم]
⛔ قاعدة صارمة جداً للأرقام: لا تكتب أي رقم هاتف إلا إذا ظهر حرفياً في نتائج البحث. إذا ما لقيت رقم اكتب (الرقم بالرابط).

【الحالة 4】سؤال معلوماتي عن منتج (المكونات، السعرات، المواصفات...):
أجب على السؤال نفسه مباشرة — لا تعرض مقارنة أسعار.

قواعد جودة صارمة جداً (مخالفتها فشل):
- اذكر فقط المنتجات المتوفرة فعلاً InStock. إذا كان المنتج غير متوفر لا تذكره إطلاقاً.
- رابط كل متجر يجب أن يكون رابط صفحة منتج مباشر (صفحة فيها منتج واحد وسعر واحد). ممنوع منعاً باتاً روابط الصفحة الرئيسية أو /search أو /category أو /collections أو /shop أو صفحات نتائج البحث.
- لا تخترع سعراً، انسخ السعر كما يظهر في نتيجة البحث اليوم.
- إذا لم تجد 3 متاجر، اذكر 1 أو 2 فقط ولا تخترع الباقي.

في الحالات 1 و2 و3، سطر أخير إلزامي:
LINKS: اسم الأول=الدومين الحقيقي, اسم الثاني=الدومين الحقيقي
في الحالة 4: سطر LINKS اختياري.
ممنوع روابط ظاهرة. ممنوع Markdown.
لغة الرد: التزم بلغة الرد المطلوبة في رسالة المستخدم.
"""

MAPS_CATEGORY_SYSTEM = """أنت خبير تسوق في السوق الكويتي.
بناءً على اسم المنتج أو الخدمة، أعطني "عبارة بحث" دقيقة جداً لخرائط جوجل.
قواعد:
- للإلكترونيات: (Xcite OR Eureka OR Best Al Yousifi)
- للأجهزة المنزلية: (Xcite OR Eureka)
- للأدوية: (صيدلية Pharmacy)
- للمواد الغذائية: (جمعية تعاونية Supermarket)
- للخدمات: نوع الخدمة بالعربي والإنجليزي مثل (بنشر Tyre repair)
أعطني عبارة البحث فقط."""

# ===== طبقة التحقق من الصفحة الحقيقية =====
def fetch_html(url):
    if not url or not url.startswith("http"): return ""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200 and len(r.text) > 1500:
            return r.text
    except Exception as e:
        print(f"fetch err {e} {url[:80]}")
    return ""

def parse_product_data(html, url):
    if not html: return None
    soup = BeautifulSoup(html, 'lxml')
    data = {"price": None, "available": True, "is_product": True, "title": ""}
    ld_products = 0

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            raw = script.string
            if not raw: continue
            j = json.loads(raw)
            objs = j if isinstance(j, list) else [j]
            # flatten @graph
            flat = []
            for o in objs:
                if isinstance(o, dict) and o.get("@graph"):
                    flat.extend(o["@graph"])
                else:
                    flat.append(o)
            for obj in flat:
                if not isinstance(obj, dict): continue
                t = str(obj.get("@type",""))
                if "Product" in t or "ProductGroup" in t:
                    ld_products += 1
                    offers = obj.get("offers") or {}
                    if isinstance(offers, list): offers = offers[0] if offers else {}
                    p = offers.get("price") or offers.get("lowPrice") or offers.get("highPrice")
                    if p:
                        try: data["price"] = float(str(p).replace(",",""))
                        except: pass
                    av = str(offers.get("availability","")).lower()
                    if "outofstock" in av or "discontinued" in av or "soldout" in av:
                        data["available"] = False
                    if not data["title"]:
                        data["title"] = str(obj.get("name",""))[:120]
        except: continue

    # عنوان احتياطي من og:title ثم <title> — مهم جداً لمطابقة "طبق الأصل"
    if not data["title"]:
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            data["title"] = og["content"].strip()[:120]
    if not data["title"] and soup.title and soup.title.string:
        data["title"] = soup.title.string.strip()[:120]

    # اذا الصفحة فيها اكثر من 4 منتجات = صفحة قائمة
    if ld_products >= 4:
        data["is_product"] = False

    # تحقق نصي للـ OOS
    low_text = soup.get_text(" ", strip=True).lower()[:6000]
    if any(ph in low_text for ph in OOS_PHRASES):
        if low_text.count("غير متوفر") > 0 or low_text.count("out of stock") > 0:
            data["available"] = False

    # fallback سعر من meta
    if not data["price"]:
        m = soup.find("meta", property="product:price:amount")
        if m and m.get("content"):
            try: data["price"] = float(m["content"])
            except: pass

    # لو الرابط واضح انه قائمة
    ul = url.lower()
    if any(p in ul for p in LISTING_URL_PARTS):
        if not re.search(r"/product/|/products/[^/]{3,}|/p/|/dp/|/item/|/prod/", ul):
            if ld_products != 1:
                data["is_product"] = False

    return data

# ===== طبقة مطابقة "طبق الأصل" =====
MODEL_RE = re.compile(r"[a-z]{1,4}-?\d{3,}[a-z]{0,3}|\d{3,}[a-z]{1,4}", re.I)
UNIT_TOKENS = {"مم","سم","جرام","جم","مل","لتر","كجم","kg","g","gm","ml","l","mm","cm","inch","انش"}

def extract_models(s):
    t = normalize_ar(s or "")
    out = set()
    for m in MODEL_RE.findall(t):
        clean = m.replace("-", "")
        if clean not in UNIT_TOKENS:
            out.add(clean)
    return out

def token_coverage(query, title):
    qt = norm_tokens(query) - UNIT_TOKENS
    tt = norm_tokens(title) - UNIT_TOKENS
    if not qt or not tt: return 0.0
    return len(qt & tt) / len(qt)

def classify_matches(match_query, items):
    """items: list of (name, url, info). returns dict name -> exact/similar/wrong"""
    res = {}
    pending = []
    qm = extract_models(match_query)
    for name, url, info in items:
        title = info.get("title") or ""
        tm = extract_models(title)
        if qm and tm:
            # رقم الموديل هو الحكم — سريع وحاسم
            res[name] = "exact" if (qm & tm) else "similar"
        else:
            pending.append((name, title))
    if pending:
        listing = "\n".join(f"{i+1}. {t if t else '(بدون عنوان)'}" for i, (n, t) in enumerate(pending))
        prompt = f"المنتج المطلوب: {match_query}\n\nعناوين الصفحات:\n{listing}"
        txt, _ = call_gemini([{"text": prompt}], system=MATCH_SYSTEM, use_search=False)
        verdicts = {}
        for m in re.finditer(r"(\d+)\s*=\s*(EXACT|SIMILAR|WRONG)", txt or "", re.I):
            verdicts[int(m.group(1))] = m.group(2).upper()
        for i, (name, title) in enumerate(pending):
            v = verdicts.get(i + 1)
            if v == "EXACT": res[name] = "exact"
            elif v == "WRONG": res[name] = "wrong"
            elif v == "SIMILAR": res[name] = "similar"
            else:
                # fallback إذا Gemini ما رد: تغطية توكنات
                cov = token_coverage(match_query, title)
                res[name] = "exact" if cov >= 0.75 else ("similar" if cov >= 0.35 else "wrong")
    return res

def verify_offers(urls_map, query, match_query=None):
    """يرجع (exact, similar): متاجر طبق الأصل ومتاجر بدائل مشابهة"""
    if not urls_map: return {}, {}
    match_query = match_query or query
    def _check(item):
        name, url = item
        cached = VERIFIED_PAGE_CACHE.get(url)
        if cached and (time.time() - cached["ts"] < 600):
            info = cached["data"]
        else:
            html = fetch_html(url)
            info = parse_product_data(html, url)
            if info:
                VERIFIED_PAGE_CACHE[url] = {"data": info, "ts": time.time()}
        if not info: return None
        if not info["is_product"]:
            print(f"REJECT LISTING: {name} -> {url}")
            return None
        if not info["available"]:
            print(f"REJECT OOS: {name} -> {url}")
            return None
        if not info["price"] or info["price"] <= 0:
            print(f"REJECT NO PRICE: {name} -> {url}")
            return None
        return (name, url, info)

    results = [r for r in RESOLVER.map(_check, urls_map.items()) if r]
    if not results: return {}, {}

    matches = classify_matches(match_query, results)
    exact, similar = {}, {}
    for name, url, info in results:
        entry = {"url": url, "price": info["price"], "title": info["title"]}
        verdict = matches.get(name, "similar")
        if verdict == "exact":
            exact[name] = entry
        elif verdict == "similar":
            similar[name] = entry
            print(f"SIMILAR (not exact): {name} -> {info['title'][:60]}")
        else:
            print(f"REJECT WRONG PRODUCT: {name} -> {info['title'][:60]}")
    return exact, similar

def get_final_url(url: str):
    if not url or not url.startswith(("http://", "https://")): return ""
    try:
        r = requests.get(url, allow_redirects=True, timeout=12, stream=True, headers=HEADERS)
        final = r.url or url
        r.close()
        return final if final.startswith(("http://", "https://")) else url
    except: return url

def resolve_all(uris): return list(RESOLVER.map(get_final_url, uris))
def clean_domain(dom):
    dom = re.sub(r"^https?://", "", (dom or "").strip().lower())
    return dom.replace("www.", "").split("/")[0]
def domain_key(dom): return clean_domain(dom).split(".")[0]
def normalize_name(value): return re.sub(r"[^\w\u0600-\u06FF]+", "", (value or "").lower())

STORE_DOMAINS = {
    "اليوسفي": "best.com.kw", "بستاليوسفي": "best.com.kw", "اكسايت": "xcite.com", "الغانم": "xcite.com",
    "نون": "noon.com", "بلينك": "blink.com.kw", "يوريكا": "eureka.com.kw", "جرير": "jarir.com",
    "كارفور": "carrefourkuwait.com", "لولو": "luluhypermarket.com", "امازون": "amazon.ae",
    "طلبات": "talabat.com", "ديليفرو": "deliveroo.com.kw", "بوتيكات": "boutiqaat.com",
}
def store_domain(name):
    n = normalize_name(normalize_ar(name))
    for k, d in STORE_DOMAINS.items():
        if k in n or n in k: return d
    return ""
JUNK_STORE = re.compile(r"^(التوصيل|توصيل|delivery|اونلاين|أونلاين|online|الموقعالرسمي|official)", re.I)
def is_junk_store(name): return bool(JUNK_STORE.match(normalize_name(normalize_ar(name))))
def short_query(q):
    q = re.sub(r"\([^)]*\)", " ", q or "")
    q = re.split(r"\s+[-—–]\s+", q)[0]
    return " ".join(q.split()[:6]).strip()

def extract_store_names(text):
    stores = []
    for line in (text or "").splitlines():
        m = re.match(r"^\s*🏪\s*[^:：]*[:：]\s*(.+?)\s*$", line)
        if m:
            name = m.group(1).strip()
            if name and name not in stores: stores.insert(0, name)
            continue
        m = re.match(r"^\s*(?:✅|🏆|•)\s*(.+?)\s*(?:—|–|-)\s*[\d.,]+", line)
        if m:
            name = m.group(1).strip()
            if name and name not in stores: stores.append(name)
    return stores[:5]

def is_service_answer(txt): return bool(re.search(r"(?:🏆|•)\s*.+?\(\s*(?:هاتف|Phone|phone|Tel|tel)\s*:", txt or ""))
def extract_store_offers(txt):
    offers = []
    for line in (txt or "").splitlines():
        s = line.strip()
        m = re.match(r"^(✅|🏆|•)\s*(.+?)\s*(?:—|–|-)\s*[\d.,]+", s)
        if not m: continue
        if re.search(r"\(\s*(?:هاتف|Phone|phone|Tel|tel)\s*:", s): continue
        name = m.group(2).strip()
        best = m.group(1) in ("✅", "🏆")
        body = s if best else s.lstrip("•").strip()
        offers.append({"line": body, "name": name, "best": best})
    return offers[:4]

def product_title(txt, fallback=""):
    m = re.search(r"^\s*📦\s*(.+)$", txt or "", flags=re.M)
    if m: return f"📦 {m.group(1).strip()}"
    return f"📦 {fallback}" if fallback else ""

def match_url(name, urls):
    if not urls: return ""
    if name in urls: return urls[name]
    nn = normalize_name(name)
    for k, v in urls.items():
        kk = normalize_name(k)
        if nn and kk and (nn in kk or kk in nn): return v
    dom = store_domain(name)
    if dom:
        key = domain_key(dom)
        for k, v in urls.items():
            if key and (key in (v or "").lower() or key in normalize_name(k)): return v
    return ""

def maps_search_url(product, lat=None, lng=None):
    category_text, _ = call_gemini([{"text": f"المنتج: {product}"}], system=MAPS_CATEGORY_SYSTEM, use_search=False)
    category = category_text.strip().splitlines()[0].strip() if category_text else product
    safe_category = urllib.parse.quote(category)
    if lat is not None and lng is not None:
        return f"https://www.google.com/maps/search/{safe_category}/@{lat},{lng},15z"
    return f"https://www.google.com/maps/search/{safe_category}"

def send_maps_button(from_number, product, bot_id, lang):
    url = maps_search_url(product)
    send_whatsapp_cta(from_number, T(lang, "maps_body"), url, bot_id, T(lang, "maps_btn"))

def send_product_result(from_number, txt, urls, bot_id, lang, query, best_only=False):
    if not txt:
        send_whatsapp_text(from_number, T(lang, "not_found"), bot_id)
        return False
    if is_service_answer(txt):
        send_whatsapp_text(from_number, txt, bot_id)
        return True
    offers = extract_store_offers(txt)
    if not offers:
        send_whatsapp_text(from_number, txt, bot_id)
        return False
    title = product_title(txt, query)
    if title: send_whatsapp_text(from_number, title, bot_id)
    core = title[2:].strip() if title.startswith("📦") else query
    fq = short_query(core) or short_query(query)
    if best_only:
        best = next((o for o in offers if o["best"]), offers[0])
        offers = [best]
    for o in offers:
        url = match_url(o["name"], urls)
        if not url:
            if is_junk_store(o["name"]): continue
            url = fallback_search_url(fq, o["name"])
        send_whatsapp_cta(from_number, o["line"], url, bot_id, f"🛒 {o['name'][:18]}")
    return True

def offer_alternatives(from_number, alts, bot_id, lang, no_exact=False):
    """يحفظ البدائل ويرسل زر: تبي بدائل مشابهة؟"""
    if not alts: return
    PENDING_ALTS[from_number] = {"alts": alts, "bot_id": bot_id, "lang": lang, "ts": time.time()}
    body = T(lang, "alts_offer_no_exact") if no_exact else T(lang, "alts_offer")
    send_whatsapp_buttons(from_number, body, [
        {"id": "alts_yes", "title": T(lang, "alts_yes_btn")},
        {"id": "alts_no", "title": T(lang, "alts_no_btn")},
    ], bot_id)

def send_alternatives(from_number, alts, bot_id, lang):
    for a in alts[:3]:
        line = f"{T(lang,'alt_tag')}\n{a['name']} — {format_price(a['price'])} د.ك"
        if a.get("title"):
            line += f"\n({a['title'][:70]})"
        send_whatsapp_cta(from_number, line, a["url"], bot_id, f"🛒 {a['name'][:18]}")

def call_gemini(parts, system=SYSTEM_PROMPT, use_search=True):
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 2000},
    }
    if use_search: payload["tools"] = [{"google_search": {}}]
    try:
        r = requests.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload, timeout=90)
        if r.status_code >= 400:
            print(f"Gemini HTTP {r.status_code}: {r.text[:500]}")
            return "", {}
        data = r.json()
        candidates = data.get("candidates") or []
        if not candidates: return "", {}
        cand = candidates[0]
        text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", [])).strip()
        pairs = []
        m = re.search(r"(?im)^\s*LINKS\s*:\s*(.+)$", text)
        if m:
            raw = m.group(1)
            for part in re.split(r"[,،]+", raw):
                part = part.strip()
                if "=" in part:
                    name, dom = part.split("=", 1)
                    name, dom = name.strip(), clean_domain(dom)
                    if name and "." in dom: pairs.append((name, dom))
            text = re.sub(r"(?im)^\s*LINKS\s*:.*$", "", text).strip()
        text = re.sub(r"https?://\S+", "", text).replace("**", "").strip()
        metadata = cand.get("groundingMetadata", {}) or {}
        chunks = metadata.get("groundingChunks", []) or []
        uris = [(c.get("web") or {}).get("uri", "") for c in chunks]
        finals = resolve_all(uris[:15]) if uris else []
        records = []
        for i, chunk in enumerate(chunks[:15]):
            web = chunk.get("web") or {}
            raw_uri = web.get("uri", "")
            final_uri = finals[i] if i < len(finals) else raw_uri
            records.append({"title": web.get("title", ""), "raw": raw_uri, "url": final_uri or raw_uri})
        urls_map = {}
        used_urls = set()
        stores = extract_store_names(text)
        supports = metadata.get("groundingSupports", []) or []
        for store in stores:
            store_norm = normalize_name(store)
            for support in supports:
                segment = (support.get("segment") or {}).get("text", "")
                if store_norm and store_norm in normalize_name(segment):
                    for idx in support.get("groundingChunkIndices", []) or []:
                        if 0 <= idx < len(records):
                            url = records[idx]["url"]
                            if url and url not in used_urls:
                                urls_map[store] = url
                                used_urls.add(url)
                                break
                if store in urls_map: break
        for name, dom in pairs:
            if name in urls_map: continue
            key = domain_key(dom)
            for rec in records:
                haystack = f"{rec['title']} {rec['raw']} {rec['url']}".lower()
                if rec["url"] and key and key in haystack and rec["url"] not in used_urls:
                    urls_map[name] = rec["url"]
                    used_urls.add(rec["url"])
                    break
        for store in stores:
            if store in urls_map: continue
            store_norm = normalize_name(store)
            for rec in records:
                if rec["url"] and store_norm and store_norm in normalize_name(rec["title"]):
                    if rec["url"] not in used_urls:
                        urls_map[store] = rec["url"]
                        used_urls.add(rec["url"])
                        break
        for store in stores:
            if store in urls_map: continue
            dom = store_domain(store)
            if not dom: continue
            key = domain_key(dom)
            for rec in records:
                haystack = f"{rec['title']} {rec['raw']} {rec['url']}".lower()
                if rec["url"] and key and key in haystack and rec["url"] not in used_urls:
                    urls_map[store] = rec["url"]
                    used_urls.add(rec["url"])
                    break
        if not urls_map:
            for rec in records:
                url = rec["url"]
                if not url or url in used_urls: continue
                label = source_label(rec["title"], url)
                if label not in urls_map:
                    urls_map[label] = url
                    used_urls.add(url)
                if len(urls_map) == 3: break
        return text, dict(list(urls_map.items())[:4])
    except Exception as e:
        print(f"Gemini err {e}"); return "", {}

def source_label(title, url):
    title = (title or "").strip()
    if title: return title[:40]
    try:
        host = urllib.parse.urlparse(url).netloc.replace("www.", "")
        return host.split(".")[0] or "المتجر"
    except: return "المتجر"

SEARCH_RUNS = int(os.environ.get("SEARCH_RUNS", "4"))
def answer_score(txt, urls):
    stores, links = result_quality(txt, urls)
    return stores * 2 + links * 3 + (1 if txt and "📦" in txt else 0)

def best_of_search(parts, lang):
    try:
        futs = [SEARCH_POOL.submit(call_gemini, parts) for _ in range(SEARCH_RUNS)]
        results = [f.result() for f in futs]
    except Exception as e:
        print(f"best_of_search err {e}")
        return call_gemini(parts)
    results = [(t, u) for (t, u) in results if t]
    if not results: return "", {}
    scored = sorted(results, key=lambda r: answer_score(r[0], r[1]), reverse=True)
    best_txt, best_urls = scored[0]
    merged_urls = dict(best_urls)
    for _, u in scored[1:]:
        for n, link in u.items():
            if n not in merged_urls and link not in merged_urls.values():
                merged_urls[n] = link
    merged_urls = dict(list(merged_urls.items())[:4])
    return best_txt, merged_urls

def search_product(query, lang, prompt_text=None, match_name=None):
    """يرجع (txt, urls, alts)
    txt/urls = نتائج طبق الأصل فقط
    alts = بدائل مشابهة [{name,url,price,title}] تُعرض فقط إذا وافق المستخدم"""
    cached = cache_get(query, lang)
    if cached: return cached
    text_part = prompt_text or f"ابحث عن {query} في الكويت. متوفر فقط InStock ورابط منتج مباشر لنفس المنتج بالضبط. {LANG_INSTR[lang]}"
    txt, urls = best_of_search([{"text": text_part}], lang)
    if not txt: return "", {}, []

    # اذا خدمة أو سؤال معلوماتي - لا نحتاج تحقق اسعار ولا مطابقة
    if is_service_answer(txt) or not extract_store_offers(txt):
        if len(txt) >= 80:
            cache_put(query, lang, txt, urls)
        return txt, urls, []

    # تحقق حقيقي من الصفحات + تصنيف طبق الأصل / مشابه
    exact, similar = verify_offers(urls, query, match_query=match_name or query)

    alts = []
    for name, info in sorted(similar.items(), key=lambda x: x[1]["price"]):
        alts.append({"name": name, "url": info["url"], "price": info["price"], "title": info.get("title", "")})

    if exact:
        sorted_v = sorted(exact.items(), key=lambda x: x[1]["price"])
        title = product_title(txt, query)
        lines = [title, ""]
        new_urls = {}
        for i, (name, info) in enumerate(sorted_v[:4]):
            prefix = "✅" if i == 0 else "•"
            lines.append(f"{prefix} {name} — {format_price(info['price'])} د.ك")
            new_urls[name] = info["url"]
        final_txt = "\n".join(lines)
        cache_put(query, lang, final_txt, new_urls, alts)
        print(f"VERIFIED EXACT: {query} -> {len(new_urls)} stores, {len(alts)} alts")
        return final_txt, new_urls, alts

    if alts:
        # ما فيه طبق الأصل — بس فيه بدائل متحقق منها. لا نعرضها الا بموافقة المستخدم.
        print(f"NO EXACT - {len(alts)} similar alts for: {query}")
        return "", {}, alts

    print(f"VERIFIED FAIL - all links rejected for: {query}")
    # fallback أخير: نرجع نتيجة Gemini بدون كاش (غير متحقق منها)
    return txt, urls, []

def extract_products(text):
    text=re.sub(r'^[•\-\*\d\.\)\s]+','',text,flags=re.M)
    parts=re.split(r'\s*(?:\n+|\+|,|،| و | & )\s*',text.strip())
    parts=[p.strip() for p in parts if len(p.strip())>2]
    return parts[:6] if len(parts)>1 else [text.strip()]

def download_whatsapp_media(mid):
    h={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    meta=requests.get(f"{GRAPH_URL}/{mid}",headers=h,timeout=20).json()
    img=requests.get(meta["url"],headers=h,timeout=30)
    return base64.b64encode(img.content).decode(), meta.get("mime_type","image/jpeg")

def send_whatsapp_text(to,text,bot_id):
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    payload={"messaging_product":"whatsapp","to":to,"type":"text","text":{"body":text[:3900]}}
    try: return requests.post(url,json=payload,headers=h,timeout=15).ok
    except: return False

def send_whatsapp_cta(to,body,link,bot_id,title):
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    payload={"messaging_product":"whatsapp","to":to,"type":"interactive","interactive":{"type":"cta_url","body":{"text":body[:1024]},"action":{"name":"cta_url","parameters":{"display_text":title[:20],"url":link}}}}
    try: return requests.post(url,json=payload,headers=h,timeout=15).ok
    except: return False

def send_whatsapp_buttons(to, body, buttons, bot_id):
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    btns=[{"type":"reply","reply":{"id":b["id"],"title":b["title"][:20]}} for b in buttons[:3]]
    payload={"messaging_product":"whatsapp","to":to,"type":"interactive","interactive":{"type":"button","body":{"text":body[:1024]},"action":{"buttons":btns}}}
    try: return requests.post(url,json=payload,headers=h,timeout=15).ok
    except: return False

def send_language_choice(to, bot_id):
    body = "🌐 اختر لغتك المفضلة\nChoose your preferred language"
    send_whatsapp_buttons(to, body, [{"id": "lang_ar", "title": "العربية 🇰🇼"},{"id": "lang_en", "title": "English 🇬🇧"}], bot_id)

@app.get("/webhook")
async def verify(request: Request):
    p=request.query_params
    if p.get("hub.mode")=="subscribe" and p.get("hub.verify_token")==VERIFY_TOKEN:
        return Response(content=p.get("hub.challenge"), media_type="text/plain")
    return Response("fail",403)

@app.post("/webhook")
async def receive(request: Request, background_tasks: BackgroundTasks):
    data=await request.json()
    try:
        value=data["entry"][0]["changes"][0]["value"]
        if "messages" not in value: return {"status":"ok"}
        msg=value["messages"][0]; mid=msg.get("id")
        if mid in processed_ids: return {"status":"dup"}
        processed_ids.append(mid)
        bot_id=value.get("metadata",{}).get("phone_number_id",PHONE_NUMBER_ID)
        from_number=msg["from"]
        if msg.get("type")=="image":
            caption = (msg.get("image",{}) or {}).get("caption","").strip()
            cap_lang = detect_lang(caption) if caption else None
            if cap_lang: USER_LANG[from_number] = cap_lang
            if from_number not in USER_LANG:
                pend=PENDING_IMAGES[from_number]
                pend["images"].append(msg); pend["bot_id"]=bot_id
                if len(pend["images"])==1:
                    background_tasks.add_task(asyncio.to_thread, send_language_choice, from_number, bot_id)
            else:
                IMAGE_BUFFER[from_number]["images"].append(msg); IMAGE_BUFFER[from_number]["time"]=time.time(); IMAGE_BUFFER[from_number]["bot_id"]=bot_id
                if len(IMAGE_BUFFER[from_number]["images"])==1:
                    background_tasks.add_task(process_image_buffer,from_number)
        elif msg.get("type")=="text":
            background_tasks.add_task(process_text_message,msg,bot_id)
        elif msg.get("type")=="interactive":
            background_tasks.add_task(process_interactive_message,msg,bot_id)
        elif msg.get("type")=="location":
            background_tasks.add_task(process_location_message,msg,bot_id)
    except Exception as e: print(f"webhook err {e}")
    return {"status":"ok"}

def process_interactive_message(message, bot_id):
    from_number=message["from"]
    reply=(message.get("interactive") or {}).get("button_reply") or {}
    btn_id=reply.get("id","")

    # ===== أزرار البدائل المشابهة =====
    if btn_id in ("alts_yes","alts_no"):
        lang=USER_LANG.get(from_number,"ar")
        pend=PENDING_ALTS.pop(from_number,None)
        if btn_id=="alts_no":
            send_whatsapp_text(from_number, T(lang,"alts_ok"), bot_id)
            return
        if not pend or not pend.get("alts"):
            send_whatsapp_text(from_number, T(lang,"alts_none"), bot_id)
            return
        send_alternatives(from_number, pend["alts"], pend.get("bot_id") or bot_id, pend.get("lang") or lang)
        return

    # ===== أزرار اللغة =====
    if btn_id not in ("lang_ar","lang_en"): return
    lang = "ar" if btn_id=="lang_ar" else "en"
    USER_LANG[from_number]=lang
    pend=PENDING_IMAGES.pop(from_number,None)
    if pend and pend["images"]:
        if len(pend["images"])==1: process_single_image(pend["images"][0], pend["bot_id"], lang)
        else: process_multi_images(pend["images"], from_number, pend["bot_id"], lang)
    else:
        send_whatsapp_text(from_number, T(lang,"lang_saved"), bot_id)

async def process_image_buffer(from_number):
    await asyncio.sleep(BUFFER_SECONDS)
    data=IMAGE_BUFFER.pop(from_number,None)
    if not data: return
    lang=USER_LANG.get(from_number,"ar")
    if len(data["images"])==1: await asyncio.to_thread(process_single_image,data["images"][0],data["bot_id"],lang)
    else: await asyncio.to_thread(process_multi_images,data["images"],from_number,data["bot_id"],lang)

def finish_search_result(from_number, txt, urls, alts, bot_id, lang, query, send_map=True):
    """يرسل النتائج طبق الأصل، وبعدها يعرض خيار البدائل إن وجدت"""
    if txt:
        ok = send_product_result(from_number, txt, urls, bot_id, lang, query)
        if alts:
            offer_alternatives(from_number, alts, bot_id, lang, no_exact=False)
        if ok and send_map:
            send_maps_button(from_number, query, bot_id, lang)
        return ok
    if alts:
        # ما فيه طبق الأصل — نسأله إذا يبي البدائل
        offer_alternatives(from_number, alts, bot_id, lang, no_exact=True)
        return True
    send_whatsapp_text(from_number, T(lang,"not_found"), bot_id)
    return False

def process_single_image(message,bot_id,lang="ar"):
    from_number=message["from"]
    caption=(message.get("image",{}) or {}).get("caption","").strip()
    send_whatsapp_text(from_number,T(lang,"identifying"),bot_id)
    b64,mime=download_whatsapp_media(message["image"]["id"])
    ident,_=call_gemini([{"inline_data":{"mime_type":mime,"data":b64}},{"text":"ما اسم هذا المنتج؟"}], system=IDENTIFY_SYSTEM, use_search=False)
    product_name = ident.strip().splitlines()[0].strip() if ident else ""
    if product_name and caption:
        request_query = f"{caption} — {product_name}"
        prompt_text = f"المنتج في الصورة: {product_name}\nطلب المستخدم عنه: {caption}\nصنّف الطلب وأجب. المطلوب نفس المنتج بالضبط. {LANG_INSTR[lang]}"
        txt,urls,alts=search_product(request_query, lang, prompt_text=prompt_text, match_name=product_name)
        LAST_SEARCH[from_number] = {"product": request_query}
        query = request_query
    elif product_name:
        # المطابقة تتم على اسم المنتج المتعرف عليه من الصورة — طبق الأصل
        txt,urls,alts=search_product(product_name, lang, match_name=product_name)
        LAST_SEARCH[from_number] = {"product": product_name}
        query = product_name
    else:
        req = caption if caption else "ما هذا المنتج؟ ابحث عن سعره الحالي في الكويت."
        txt,urls=best_of_search([{"inline_data":{"mime_type":mime,"data":b64}},{"text":f"{req} {LANG_INSTR[lang]}"}], lang)
        alts=[]
        name_m = re.search(r"📦\s*(.+)", txt or "")
        product_name = name_m.group(1).strip() if name_m else "المنتج"
        query = f"{caption} — {product_name}" if caption else product_name
        LAST_SEARCH[from_number] = {"product": query}
    if not txt and not alts:
        send_whatsapp_text(from_number,T(lang,"cant_identify"),bot_id)
        return
    send_map = bool(product_name and product_name != "المنتج")
    finish_search_result(from_number, txt, urls, alts, bot_id, lang, query, send_map=send_map)

def identify_image_product(msg):
    try:
        b64,mime=download_whatsapp_media(msg["image"]["id"])
        ident,_=call_gemini([{"inline_data":{"mime_type":mime,"data":b64}},{"text":"ما اسم هذا المنتج؟"}], system=IDENTIFY_SYSTEM, use_search=False)
        return ident.strip().splitlines()[0].strip() if ident else ""
    except: return ""

def process_cart(products, from_number, bot_id, lang="ar"):
    results = list(WORKERS.map(lambda p: (p, *search_product(p, lang)), products))
    any_ok = False
    for p, txt, urls, alts in results:
        if txt:
            any_ok = True
            send_product_result(from_number, txt, urls, bot_id, lang, p, best_only=True)
        elif alts:
            # بالسلة ما نوقف نسأل عن كل منتج — نعطيه أقرب بديل معلّم بوضوح
            any_ok = True
            a = alts[0]
            line = f"📦 {p}\n{T(lang,'cart_alt_note')}\n{T(lang,'alt_tag')}: {a['name']} — {format_price(a['price'])} د.ك"
            send_whatsapp_cta(from_number, line, a["url"], bot_id, f"🛒 {a['name'][:18]}")
    if not any_ok:
        send_whatsapp_text(from_number, T(lang, "not_found"), bot_id)
        return
    LAST_SEARCH[from_number] = {"product": products[0]}

def process_multi_images(messages,from_number,bot_id,lang="ar"):
    send_whatsapp_text(from_number,T(lang,"multi_images",c=len(messages)),bot_id)
    names=[n for n in WORKERS.map(identify_image_product,messages) if n]
    if not names:
        send_whatsapp_text(from_number,T(lang,"cant_identify"),bot_id)
        return
    process_cart(names, from_number, bot_id, lang)

def process_text_message(message,bot_id):
    from_number=message["from"]; user_text=message["text"]["body"]
    cmd=re.sub(r"[^\w\u0600-\u06FF]","",user_text.strip().lower())
    if cmd in ("لغة","اللغة","غيراللغة","language","lang","changelanguage"):
        send_language_choice(from_number, bot_id); return
    detected=detect_lang(user_text)
    if detected: USER_LANG[from_number]=detected
    lang=USER_LANG.get(from_number,"ar")
    pend=PENDING_IMAGES.pop(from_number,None)
    if pend and pend["images"]:
        if len(pend["images"])==1: process_single_image(pend["images"][0], pend["bot_id"], lang)
        else: process_multi_images(pend["images"], from_number, pend["bot_id"], lang)
    products=extract_products(user_text)
    if len(products)==1:
        send_whatsapp_text(from_number,T(lang,"searching",q=products[0]),bot_id)
        txt,urls,alts=search_product(products[0], lang)
        LAST_SEARCH[from_number] = {"product": products[0]}
        finish_search_result(from_number, txt, urls, alts, bot_id, lang, products[0])
    else:
        send_whatsapp_text(from_number,T(lang,"multi_text",c=len(products)),bot_id)
        process_cart(products, from_number, bot_id, lang)

def process_location_message(message, bot_id):
    from_number = message["from"]
    lat = message["location"]["latitude"]; lng = message["location"]["longitude"]
    lang = USER_LANG.get(from_number, "ar")
    last_search = LAST_SEARCH.get(from_number)
    if not last_search or not last_search.get("product"):
        send_whatsapp_text(from_number, T(lang,"no_saved_product"), bot_id); return
    product = last_search["product"]
    maps_url = maps_search_url(product, lat, lng)
    body = T(lang,"maps_body_loc",p=product)
    send_whatsapp_cta(from_number, body, maps_url, bot_id, T(lang,"maps_btn"))

@app.get("/")
async def health(): return {"status":"v32 exact-match + similar alternatives on demand"}
