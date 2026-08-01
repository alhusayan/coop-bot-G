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
PENDING_ALT = {}  # from_number -> {"product":...} بانتظار رد نعم/لا على عرض البديل

BUFFER_SECONDS = 4
RESOLVER = ThreadPoolExecutor(max_workers=10)  # رفعناها: نتحقق من 8-10 صفحات بالتوازي
WORKERS = ThreadPoolExecutor(max_workers=3)
SEARCH_POOL = ThreadPoolExecutor(max_workers=8)
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

SEARCH_CACHE = {}
CACHE_TTL = int(os.environ.get("CACHE_TTL_HOURS", "2")) * 3600
CACHE_MAX = 500
CACHE_MIN_STORES = 1
CACHE_MIN_LINKS = 1

# كم متجر موثق نستهدف بكل رد
TARGET_RESULTS = int(os.environ.get("TARGET_RESULTS", "4"))

# ===== كاش صفحات المتاجر المتحقق منها =====
VERIFIED_PAGE_CACHE = {}
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
        return hit["txt"], dict(hit["urls"])
    qt = norm_tokens(query)
    if not qt: return None
    best, best_score = None, 0.0
    for entry in SEARCH_CACHE.values():
        if entry.get("lang")!= lang or (now - entry["ts"]) >= CACHE_TTL: continue
        et = entry.get("tokens") or set()
        if not et: continue
        inter = len(qt & et)
        score = inter / len(qt | et) if (qt | et) else 0
        if has_model_token(qt, et): score += 0.30
        if score > best_score: best, best_score = entry, score
    if best and best_score >= 0.60:
        print(f"CACHE HIT (fuzzy {best_score:.2f}): {query[:50]} ~ {best.get('query','')[:50]}")
        return best["txt"], dict(best["urls"])
    return None

def cache_put(query, lang, txt, urls):
    if not txt: return
    if len(SEARCH_CACHE) >= CACHE_MAX:
        oldest = min(SEARCH_CACHE, key=lambda k: SEARCH_CACHE[k]["ts"])
        SEARCH_CACHE.pop(oldest, None)
    SEARCH_CACHE[cache_key(query, lang)] = {
        "txt": txt, "urls": dict(urls), "ts": time.time(),
        "tokens": norm_tokens(query), "query": query, "lang": lang,
    }

IDENTIFY_SYSTEM = """أنت خبير تعرف على المنتجات. انظر للصورة واكتب الاسم التجاري القياسي للمنتج بصيغة ثابتة دائماً:
[البراند] [نوع المنتج] [رقم الموديل باللاتيني إن ظهر] [اللون/النكهة] [الحجم/الوزن إن ظهر]
رقم الموديل هو أهم عنصر — دور عليه على العبوة أو الذراع أو الملصق (مثل RB3721، SM-S928، MQ2V3).
أمثلة:
- ريبان نظارة شمسية RB3721 اسود 59 مم
- برينجلز كاتشب 200 جرام
سطر واحد فقط."""

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
        "approx_note": "(~ سعر تقريبي من البحث غير مؤكد)",
        "alt_ask": "😕 ({p})\n\nهذا المنتج غير متوفر حالياً بالمتاجر المعتمدة في الكويت.\n\nتبي أدور لك أقرب بديل له؟ 👇",
        "alt_yes_btn": "نعم دور بديل ✅",
        "alt_no_btn": "لا شكراً",
        "alt_searching": "🔍 تمام، أدور لك أقرب بديل متوفر...",
        "alt_found": "🔁 هذا أقرب بديل متوفر لقيته:",
        "alt_ok": "تمام 👍 إذا تبي أي شي ثاني أنا حاضر!",
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
        "approx_note": "(~ approximate price from search, unverified)",
        "alt_ask": "😕 ({p})\n\nThis product isn't currently available at approved stores in Kuwait.\n\nWant me to find the closest alternative? 👇",
        "alt_yes_btn": "Yes, find one ✅",
        "alt_no_btn": "No thanks",
        "alt_searching": "🔍 On it, looking for the closest in-stock alternative...",
        "alt_found": "🔁 Here's the closest available alternative I found:",
        "alt_ok": "Got it 👍 I'm here if you need anything else!",
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
• [المتجر الرابع] — [السعر] د.ك
• [المتجر الخامس] — [السعر] د.ك
• [المتجر السادس] — [السعر] د.ك
اذكر أكبر عدد ممكن من المتاجر المختلفة (حتى 6) ما دامت من نتائج البحث الفعلية — التنوع مهم.

🛒 مصدر العروض ClicFlyer — قاعدة إلزامية لمنتجات التموينات:
لأي منتج بقالة أو تموينات (أغذية، مشروبات، منظفات، عناية شخصية)، نفّذ دائماً بحثاً إضافياً في clicflyer.com (استخدم site:clicflyer.com مع اسم المنتج).
- إذا وجدت عرضاً سارياً أرخص، حطه أول القائمة واكتب (عرض).

【الحالة 2】طلب عام بدون براند محدد (مثل: قهوة فلات وايت حار، عطر رجالي، لابتوب للدراسة):
لا تبحث عن الأرخص! ابحث عن الأفضل تقييماً في الكويت بسعر مناسب.
📦 [وصف الطلب]
🏆 [اسم الخيار الأفضل + مكانه/متجره] — [السعر] د.ك ⭐ [التقييم من 5]
• [خيار ثاني] — [السعر] د.ك ⭐ [التقييم]
• [خيار ثالث] — [السعر] د.ك ⭐ [التقييم]
• [خيار رابع] — [السعر] د.ك ⭐ [التقييم]

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
- إذا لم تجد متاجر كافية، اذكر الموجود فقط ولا تخترع الباقي.

في الحالات 1 و2 و3، سطر أخير إلزامي بأسماء المتاجر الحقيقية التي ذكرتها أنت في القائمة:
LINKS: لولو هايبرماركت=luluhypermarket.com, نون=noon.com, إكسايت=xcite.com
⛔ ممنوع منعاً باتاً كتابة عبارات مثل "اسم الأول" أو "المتجر الثاني" — اكتب الاسم التجاري الفعلي لكل متجر.
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
                        data["title"] = str(obj.get("name",""))[:80]
        except: continue

    if ld_products >= 4:
        data["is_product"] = False

    low_text = soup.get_text(" ", strip=True).lower()[:6000]
    if any(ph in low_text for ph in OOS_PHRASES):
        if low_text.count("غير متوفر") > 0 or low_text.count("out of stock") > 0:
            data["available"] = False

    if not data["price"]:
        m = soup.find("meta", property="product:price:amount")
        if m and m.get("content"):
            try: data["price"] = float(m["content"])
            except: pass

    ul = url.lower()
    if any(p in ul for p in LISTING_URL_PARTS):
        if not re.search(r"/product/|/products/[^/]{3,}|/p/|/dp/|/item/|/prod/", ul):
            if ld_products!= 1:
                data["is_product"] = False

    return data

def verify_offers(urls_map, query):
    if not urls_map: return {}
    verified = {}
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

    results = list(RESOLVER.map(_check, urls_map.items()))
    for r in results:
        if r:
            name, url, info = r
            verified[name] = {"url": url, "price": info["price"], "title": info["title"]}
    return verified

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
    "توصيل": "taw9eel.com", "تريكارت": "trikart.com", "يوباي": "ubuy.com.kw", "ديزرتكارت": "desertcart.com.kw",
    "مطاحن": "kuwaitflourmills.com", "ويبي": "wibi.com.kw",
}
def store_domain(name):
    n = normalize_name(normalize_ar(name))
    for k, d in STORE_DOMAINS.items():
        if k in n or n in k: return d
    return ""
JUNK_STORE = re.compile(r"^(delivery|اونلاين|أونلاين|online|الموقعالرسمي|official)", re.I)
def is_junk_store(name): return bool(JUNK_STORE.match(normalize_name(normalize_ar(name))))

# أسماء قوالب ينسخها Gemini بالغلط من البرومبت ("اسم الأول"...) — نستبدلها باسم المتجر الحقيقي من الدومين
def is_placeholder_name(name):
    x = normalize_name(normalize_ar(name))
    if not x: return True
    if x.startswith("اسمال") or x.startswith("المتجرال") or x.startswith("متجرال"): return True
    return x in {"اسم","المتجر","متجر","الاول","الثاني","الثالث","الرابع","الخامس","السادس",
                 "storename","firststore","secondstore","store","name"}

DOMAIN_DISPLAY = {
    "luluhypermarket": "لولو هايبرماركت", "xcite": "إكسايت", "best": "اليوسفي", "noon": "نون",
    "blink": "بلينك", "eureka": "يوريكا", "jarir": "جرير", "carrefourkuwait": "كارفور",
    "taw9eel": "توصيل Taw9eel", "talabat": "طلبات", "trikart": "تريكارت", "ubuy": "يوباي",
    "desertcart": "ديزرت كارت", "amazon": "أمازون", "boutiqaat": "بوتيكات", "wibi": "ويبي",
    "kuwaitflourmills": "مطاحن الكويت", "deliveroo": "ديليفرو",
}

def url_host_key(url):
    """مفتاح المتجر من الدومين — يتجاهل السب-دومين (gcc.luluhypermarket.com ← luluhypermarket)"""
    try:
        host = urllib.parse.urlparse(url).netloc.replace("www.", "").lower()
    except Exception:
        return ""
    for k in DOMAIN_DISPLAY:
        if k in host:
            return k
    parts = host.split(".")
    return parts[-2] if len(parts) >= 2 else (parts[0] if parts else "")

def display_store_name(name, url):
    """اسم العرض النهائي: إذا الاسم قالب أو خربان، نستبدله باسم المتجر الحقيقي من دومين اللنك"""
    host = url_host_key(url)
    if not name or is_placeholder_name(name) or is_junk_store(name):
        return DOMAIN_DISPLAY.get(host, host.capitalize() if host else "المتجر")
    return name
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
    return stores[:8]

def is_service_answer(txt): return bool(re.search(r"(?:🏆|•)\s*.+?\(\s*(?:هاتف|Phone|phone|Tel|tel)\s*:", txt or ""))

# ===== كشف "المنتج غير متوفر" وعرض البديل =====
UNAVAIL_RX = re.compile(r"(غير متوفر|غير متاح|لم أجد|لم اجد|ما لقيت|لا يتوفر|not available|couldn't find|could not find|out of stock|no stock)", re.I)

def is_unavailable_answer(txt):
    """رد بدون أي أسعار وفيه عبارة عدم توفر = المنتج مو موجود بالمتاجر"""
    return bool(txt) and not extract_store_offers(txt) and bool(UNAVAIL_RX.search(txt))

def offer_alternative(from_number, product, bot_id, lang):
    """يسأل العميل بأزرار نعم/لا إذا يبي أقرب بديل — ما نسأل مرتين (البديل مالله بديل)"""
    if (product or "").startswith("بديل "):
        send_whatsapp_text(from_number, T(lang, "not_found"), bot_id)
        return
    PENDING_ALT[from_number] = {"product": product}
    send_whatsapp_buttons(from_number, T(lang, "alt_ask", p=product), [
        {"id": "alt_yes", "title": T(lang, "alt_yes_btn")},
        {"id": "alt_no", "title": T(lang, "alt_no_btn")},
    ], bot_id)

def run_alternative_search(from_number, product, bot_id, lang):
    """البحث عن أقرب بديل متوفر وعرضه بنفس شكل المنتجات (تحقق + أزرار + خريطة)"""
    send_whatsapp_text(from_number, T(lang, "alt_searching"), bot_id)
    alt_query = f"بديل {product}"
    prompt = (f"المنتج التالي غير متوفر في متاجر الكويت: ({product}).\n"
              f"مهمتك: ابحث عن أقرب منتج بديل له متوفر فعلاً InStock في متاجر الكويت الإلكترونية — "
              f"نفس نوع المنتج ونفس الاستخدام والحجم تقريباً، من براند آخر أو موديل مشابه.\n"
              f"رد بتنسيق مقارنة الأسعار المعتاد بالضبط: 📦 اسم المنتج البديل ثم قائمة المتاجر بالأسعار، "
              f"مع سطر LINKS بأسماء المتاجر الحقيقية ودوميناتها. {LANG_INSTR[lang]}")
    txt, urls = search_product(alt_query, lang, prompt_text=prompt)
    if txt and extract_store_offers(txt):
        send_whatsapp_text(from_number, T(lang, "alt_found"), bot_id)
    LAST_SEARCH[from_number] = {"product": alt_query}
    need_map = send_product_result(from_number, txt, urls, bot_id, lang, alt_query)
    if need_map:
        send_maps_button(from_number, alt_query, bot_id, lang)

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
    return offers[:8]

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
        # ما رجع شي أصلاً — نعتبره غير متوفر ونعرض البديل
        offer_alternative(from_number, query, bot_id, lang)
        return False
    if is_service_answer(txt):
        send_whatsapp_text(from_number, txt, bot_id)
        return True
    offers = extract_store_offers(txt)
    if not offers:
        if is_unavailable_answer(txt):
            # المنتج غير متوفر: ما نعرض اعتذار Gemini — نسأل العميل إذا يبي بديل
            offer_alternative(from_number, query, bot_id, lang)
            return False
        send_whatsapp_text(from_number, txt, bot_id)
        return False
    title = product_title(txt, query)
    # الرسالة الأولى: اسم المنتج + السطور التقريبية (~) إن وجدت — تكملة الـ4 خيارات
    approx_lines = [l.strip() for l in txt.splitlines() if "~" in l]
    head = title or f"📦 {query}"
    if approx_lines and not best_only:
        head += "\n\n" + "\n".join(approx_lines)
    send_whatsapp_text(from_number, head, bot_id)
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
        # حتى لو سطر LINKS طلع فاضي (المنتج غير متوفر) نشيله — لا يظهر للعميل أبداً
        text = re.sub(r"(?im)^\s*LINKS\s*:?\s*$", "", text).strip()
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
        # وسعنا القمع: نرجع حتى 8 لنكات مرشحة — التحقق بيفلترها والباقي يعوض المرفوض
        return text, dict(list(urls_map.items())[:8])
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
    # اتحاد لنكات كل الجولات: حتى 10 مرشحين للتحقق — يضمن بقاء 4+ بعد الفلترة
    merged_urls = dict(list(merged_urls.items())[:10])
    return best_txt, merged_urls

def search_product(query, lang, prompt_text=None):
    cached = cache_get(query, lang)
    if cached: return cached
    text_part = prompt_text or f"ابحث عن {query} في الكويت. متوفر فقط InStock ورابط منتج مباشر. اذكر أكبر عدد من المتاجر المختلفة (حتى 6). {LANG_INSTR[lang]}"
    txt, urls = best_of_search([{"text": text_part}], lang)
    if not txt: return "", {}

    # اذا خدمة أو سؤال معلوماتي - لا نحتاج تحقق اسعار
    if is_service_answer(txt) or not extract_store_offers(txt):
        stores, links = result_quality(txt, urls)
        if len(txt) >= 80:
            cache_put(query, lang, txt, urls)
        return txt, urls

    # تحقق حقيقي من الصفحات
    verified = verify_offers(urls, query)

    # ===== جولة الاستكمال: ما وصلنا 4 متاجر موثقة؟ نطلب متاجر إضافية "غير" اللي عندنا ونتحقق منها =====
    if len(verified) < TARGET_RESULTS:
        exclude = "، ".join(sorted(set(list(verified.keys()) + list(urls.keys())))[:10])
        extra_prompt = (f"ابحث عن {query} في الكويت في متاجر إلكترونية أخرى مختلفة تماماً عن هذه: ({exclude}). "
                        f"متوفر فقط InStock ورابط صفحة منتج مباشر. اذكر حتى 6 متاجر مختلفة بنفس التنسيق. {LANG_INSTR[lang]}")
        txt2, urls2 = call_gemini([{"text": extra_prompt}])
        if urls2:
            have_urls = {v["url"] for v in verified.values()} | set(urls.values())
            pool = {n: u for n, u in urls2.items() if u and u not in have_urls}
            if pool:
                more = verify_offers(pool, query)
                for n, info in more.items():
                    if n not in verified and info["url"] not in {v["url"] for v in verified.values()}:
                        verified[n] = info
        print(f"BACKFILL ROUND: now {len(verified)} verified for {query[:50]}")

    if verified:
        cur = "د.ك" if lang == "ar" else "KWD"
        # ===== دمج التكرار: متجر واحد لكل دومين (نفس المتجر ممكن يدخل باسمين) — نخلي الأرخص =====
        by_dom = {}
        for name, info in verified.items():
            dom = url_host_key(info["url"]) or info["url"]
            prev = by_dom.get(dom)
            if not prev or info["price"] < prev[1]["price"]:
                by_dom[dom] = (name, info)
        sorted_v = sorted(by_dom.values(), key=lambda x: x[1]["price"])[:TARGET_RESULTS]
        title = product_title(txt, query)
        lines = [title, ""]
        new_urls = {}
        for i, (name, info) in enumerate(sorted_v):
            disp = display_store_name(name, info["url"])
            if disp in new_urls:
                disp = f"{disp} 2"
            prefix = "✅" if i == 0 else "•"
            lines.append(f"{prefix} {disp} — {format_price(info['price'])} {cur}")
            new_urls[disp] = info["url"]

        # ===== تكملة العرض إلى 4 خيارات: متاجر البحث غير الموثقة كسطور تقريبية (~) بدون أزرار =====
        need = TARGET_RESULTS - len(sorted_v)
        approx = []
        if need > 0:
            seen = {normalize_name(normalize_ar(n)) for n in new_urls}
            seen |= {normalize_name(normalize_ar(n)) for n, _ in sorted_v}
            for o in extract_store_offers(txt):
                if is_placeholder_name(o["name"]) or is_junk_store(o["name"]): continue
                nn = normalize_name(normalize_ar(o["name"]))
                if not nn or any((nn in s or s in nn) for s in seen if s): continue
                line = re.sub(r"^\s*(?:✅|🏆)\s*", "", o["line"])
                line = re.sub(r"(\d+(?:\.\d+)?)(\s*(?:د\.?\s*ك|KWD|KD))", r"~\1\2", line, count=1)
                approx.append(f"• {line}")
                seen.add(nn)
                if len(approx) >= need: break
            if approx:
                lines.append("")
                lines.extend(approx)
                lines.append(T(lang, "approx_note"))
        final_txt = "\n".join(lines)
        cache_put(query, lang, final_txt, new_urls)
        print(f"VERIFIED OK: {query[:50]} -> {len(new_urls)} verified + {len(approx)} approx")
        return final_txt, new_urls
    else:
        print(f"VERIFIED FAIL - all links rejected for: {query}")
        # لا نحفظ بالكاش - نرجع الاصلي كـ fallback لكن بدون كاش
        return txt, urls

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
    # أزرار البديل: نعم/لا
    if btn_id in ("alt_yes","alt_no"):
        pend = PENDING_ALT.pop(from_number, None)
        lang = USER_LANG.get(from_number, "ar")
        if btn_id == "alt_no" or not pend:
            send_whatsapp_text(from_number, T(lang, "alt_ok"), bot_id)
            return
        run_alternative_search(from_number, pend["product"], bot_id, lang)
        return
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

def process_single_image(message,bot_id,lang="ar"):
    from_number=message["from"]
    caption=(message.get("image",{}) or {}).get("caption","").strip()
    send_whatsapp_text(from_number,T(lang,"identifying"),bot_id)
    b64,mime=download_whatsapp_media(message["image"]["id"])
    ident,_=call_gemini([{"inline_data":{"mime_type":mime,"data":b64}},{"text":"ما اسم هذا المنتج؟"}], system=IDENTIFY_SYSTEM, use_search=False)
    product_name = ident.strip().splitlines()[0].strip() if ident else ""
    if product_name and caption:
        request_query = f"{caption} — {product_name}"
        prompt_text = f"المنتج في الصورة: {product_name}\nطلب المستخدم عنه: {caption}\nصنّف الطلب وأجب. {LANG_INSTR[lang]}"
        txt,urls=search_product(request_query, lang, prompt_text=prompt_text)
        LAST_SEARCH[from_number] = {"product": request_query}
        query = request_query
    elif product_name:
        txt,urls=search_product(product_name, lang)
        LAST_SEARCH[from_number] = {"product": product_name}
        query = product_name
    else:
        req = caption if caption else "ما هذا المنتج؟ ابحث عن سعره الحالي في الكويت."
        txt,urls=best_of_search([{"inline_data":{"mime_type":mime,"data":b64}},{"text":f"{req} {LANG_INSTR[lang]}"}], lang)
        name_m = re.search(r"📦\s*(.+)", txt or "")
        product_name = name_m.group(1).strip() if name_m else "المنتج"
        query = f"{caption} — {product_name}" if caption else product_name
        LAST_SEARCH[from_number] = {"product": query}
    if not txt:
        send_whatsapp_text(from_number,T(lang,"cant_identify"),bot_id)
        return
    need_map = send_product_result(from_number, txt, urls, bot_id, lang, query)
    if need_map and product_name and product_name!= "المنتج":
        send_maps_button(from_number, query, bot_id, lang)

def identify_image_product(msg):
    try:
        b64,mime=download_whatsapp_media(msg["image"]["id"])
        ident,_=call_gemini([{"inline_data":{"mime_type":mime,"data":b64}},{"text":"ما اسم هذا المنتج؟"}], system=IDENTIFY_SYSTEM, use_search=False)
        return ident.strip().splitlines()[0].strip() if ident else ""
    except: return ""

def process_cart(products, from_number, bot_id, lang="ar"):
    results = list(WORKERS.map(lambda p: (p, *search_product(p, lang)), products))
    any_ok = False
    for p, txt, urls in results:
        if not txt: continue
        any_ok = True
        send_product_result(from_number, txt, urls, bot_id, lang, p, best_only=True)
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
        txt,urls=search_product(products[0], lang)
        LAST_SEARCH[from_number] = {"product": products[0]}
        need_map = send_product_result(from_number, txt, urls, bot_id, lang, products[0])
        if need_map: send_maps_button(from_number, products[0], bot_id, lang)
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
async def health(): return {"status":"v34 alternative product flow"}
