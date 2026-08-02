# -*- coding: utf-8 -*-
import os, re, time, base64, requests, json, asyncio, urllib.parse, hashlib, sqlite3, threading
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Request, Response, BackgroundTasks
from bs4 import BeautifulSoup

app = FastAPI()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
# تقدر تغيّر نموذج البحث ونموذج التعرف على الصور كل واحد بروحه من Environment Variables.
# تركنا الافتراضي نفس نموذجك الحالي حتى لا يتعطل النشر بسبب اسم نموذج غير متاح في حسابك.
GEMINI_SEARCH_MODEL = os.environ.get("GEMINI_SEARCH_MODEL", GEMINI_MODEL)
GEMINI_FAST_MODEL = os.environ.get("GEMINI_FAST_MODEL", GEMINI_MODEL)
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_COOP_BOT_TOKEN")

GRAPH_URL = "https://graph.facebook.com/v20.0"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

processed_ids = deque(maxlen=1000)
IMAGE_BUFFER = defaultdict(lambda: {"images": [], "time": 0, "bot_id": ""})
LAST_SEARCH = {}
USER_LANG = {}
PENDING_IMAGES = defaultdict(lambda: {"images": [], "bot_id": ""})

BUFFER_SECONDS = 4
RESOLVER = ThreadPoolExecutor(max_workers=8)
WORKERS = ThreadPoolExecutor(max_workers=5)
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")

SEARCH_CACHE = {}
# كاش مختلف حسب نوع الطلب: المنتجات 12 ساعة، التموينات 4 ساعات، الخدمات 7 أيام.
CACHE_TTL = int(os.environ.get("CACHE_TTL_HOURS", "12")) * 3600
GROCERY_CACHE_TTL = int(os.environ.get("GROCERY_CACHE_TTL_HOURS", "4")) * 3600
SERVICE_CACHE_TTL = int(os.environ.get("SERVICE_CACHE_TTL_HOURS", "168")) * 3600
CACHE_MAX = int(os.environ.get("CACHE_MAX", "3000"))
CACHE_DB_PATH = os.environ.get("CACHE_DB_PATH", "/tmp/coop_search_cache.sqlite3")
CACHE_DB_LOCK = threading.Lock()
# النسخة الاقتصادية: 3 نتائج فقط واتصال بحث واحد في الوضع الطبيعي.
MAX_STORES = int(os.environ.get("MAX_STORES", "3"))
MAX_URLS_MERGED = int(os.environ.get("MAX_URLS_MERGED", "5"))
ENABLE_SEARCH_RETRY = env_bool("ENABLE_SEARCH_RETRY", False)
AUTO_SEND_PRODUCT_MAPS = env_bool("AUTO_SEND_PRODUCT_MAPS", False)

GROCERY_WORDS = [
    "بيبسي","شيبس","حليب","قهوه","قهوة","شاي","سكر","رز","زيت","صابون","شامبو",
    "برينجلز","كيتكات","نسكافيه","تونه","ماء","عصير","بسكوت","منظف","معجون","حفاض"
]

print(
    f"ECONOMIC CONFIG search_model={GEMINI_SEARCH_MODEL} fast_model={GEMINI_FAST_MODEL} "
    f"max_stores={MAX_STORES} retry={ENABLE_SEARCH_RETRY} auto_maps={AUTO_SEND_PRODUCT_MAPS}"
)

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

def cache_ttl_for(query, txt=""):
    q_norm = normalize_ar(query)
    if txt and re.search(r"(?:🏆|•)\s*.+?\(\s*(?:هاتف|Phone|phone|Tel|tel)\s*:", txt):
        return SERVICE_CACHE_TTL
    if any(w in q_norm for w in GROCERY_WORDS):
        return GROCERY_CACHE_TTL
    return CACHE_TTL

def _cache_db_connect():
    parent = os.path.dirname(CACHE_DB_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(CACHE_DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def _cache_db_init():
    try:
        with CACHE_DB_LOCK, _cache_db_connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS search_cache (
                    cache_key TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    lang TEXT NOT NULL,
                    txt TEXT NOT NULL,
                    urls_json TEXT NOT NULL,
                    ts REAL NOT NULL,
                    expires_at REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_search_cache_expiry ON search_cache(expires_at)")
            conn.execute("DELETE FROM search_cache WHERE expires_at <= ?", (time.time(),))
    except Exception as e:
        print(f"CACHE DB INIT ERR: {e}")

def _cache_db_get(key):
    try:
        with CACHE_DB_LOCK, _cache_db_connect() as conn:
            row = conn.execute(
                "SELECT query, lang, txt, urls_json, ts, expires_at FROM search_cache WHERE cache_key=?",
                (key,),
            ).fetchone()
            if not row:
                return None
            query, lang, txt, urls_json, ts, expires_at = row
            if expires_at <= time.time():
                conn.execute("DELETE FROM search_cache WHERE cache_key=?", (key,))
                return None
            return {
                "query": query,
                "lang": lang,
                "txt": txt,
                "urls": json.loads(urls_json or "{}"),
                "ts": ts,
                "expires_at": expires_at,
                "tokens": norm_tokens(query),
            }
    except Exception as e:
        print(f"CACHE DB GET ERR: {e}")
        return None

def _cache_db_put(key, entry):
    try:
        with CACHE_DB_LOCK, _cache_db_connect() as conn:
            conn.execute(
                """
                INSERT INTO search_cache(cache_key, query, lang, txt, urls_json, ts, expires_at)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    query=excluded.query,
                    lang=excluded.lang,
                    txt=excluded.txt,
                    urls_json=excluded.urls_json,
                    ts=excluded.ts,
                    expires_at=excluded.expires_at
                """,
                (
                    key,
                    entry["query"],
                    entry["lang"],
                    entry["txt"],
                    json.dumps(entry["urls"], ensure_ascii=False),
                    entry["ts"],
                    entry["expires_at"],
                ),
            )
    except Exception as e:
        print(f"CACHE DB PUT ERR: {e}")

_cache_db_init()

def cache_get(query, lang):
    now = time.time()
    key = cache_key(query, lang)
    hit = SEARCH_CACHE.get(key)
    if not hit:
        hit = _cache_db_get(key)
        if hit:
            SEARCH_CACHE[key] = hit
    if hit and now < hit.get("expires_at", 0):
        print(f"CACHE HIT (exact): {query[:60]}")
        return hit["txt"], dict(hit["urls"])

    qt = norm_tokens(query)
    if not qt:
        return None
    best, best_score = None, 0.0
    for entry in SEARCH_CACHE.values():
        if entry.get("lang") != lang or now >= entry.get("expires_at", 0):
            continue
        et = entry.get("tokens") or set()
        if not et:
            continue
        inter = len(qt & et)
        score = inter / len(qt | et) if (qt | et) else 0
        if has_model_token(qt, et):
            score += 0.30
        if score > best_score:
            best, best_score = entry, score
    if best and best_score >= 0.68:
        print(f"CACHE HIT (fuzzy {best_score:.2f}): {query[:50]} ~ {best.get('query','')[:50]}")
        return best["txt"], dict(best["urls"])
    return None

def cache_put(query, lang, txt, urls):
    if not txt:
        return
    if len(SEARCH_CACHE) >= CACHE_MAX:
        oldest = min(SEARCH_CACHE, key=lambda k: SEARCH_CACHE[k].get("ts", 0))
        SEARCH_CACHE.pop(oldest, None)
    now = time.time()
    ttl = cache_ttl_for(query, txt)
    key = cache_key(query, lang)
    entry = {
        "txt": txt,
        "urls": dict(urls),
        "ts": now,
        "expires_at": now + ttl,
        "tokens": norm_tokens(query),
        "query": query,
        "lang": lang,
    }
    SEARCH_CACHE[key] = entry
    _cache_db_put(key, entry)

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

حاول تجيب 3 متاجر مختلفة فقط إذا تقدر: Xcite, Eureka, Blink, Noon, Jarir, Lulu, Carrefour, Amazon.ae, Best Al-Yousifi

🛒 مصدر العروض ClicFlyer — قاعدة إلزامية لمنتجات التموينات:
لأي منتج بقالة أو تموينات (أغذية، مشروبات، منظفات، عناية شخصية)، ابحث ضمن نفس طلب البحث في clicflyer.com أيضاً (استخدم site:clicflyer.com مع اسم المنتج).
- إذا وجدت عرضاً سارياً أرخص، حطه أول القائمة واكتب (عرض).

【الحالة 2】طلب عام بدون براند محدد (مثل: قهوة فلات وايت حار، عطر رجالي، لابتوب للدراسة):
لا تبحث عن الأرخص! ابحث عن الأفضل تقييماً في الكويت بسعر مناسب.
📦 [وصف الطلب]
🏆 [اسم الخيار الأفضل + مكانه/متجره] — [السعر] د.ك ⭐ [التقييم من 5]
• [خيار ثاني] — [السعر] د.ك ⭐ [التقييم]
• [خيار ثالث] — [السعر] د.ك ⭐ [التقييم]

【الحالة 3】طلب خدمة (فني، بنشر، تبديل بطارية، سباك...):
📦 [وصف الخدمة + المنطقة]
🏆 [اسم أفضل مزود فقط] (هاتف: [الرقم]) — [المنطقة] — [السعر إن وجد] د.ك ⭐ [التقييم]
⛔ قاعدة صارمة جداً للأرقام: لا تكتب أي رقم هاتف إلا إذا ظهر حرفياً في نتائج البحث. إذا ما لقيت رقم اكتب (الرقم بالرابط).

【الحالة 4】سؤال معلوماتي عن منتج (المكونات، السعرات، المواصفات...):
أجب على السؤال نفسه مباشرة — لا تعرض مقارنة أسعار.

قواعد جودة صارمة جداً:
- اذكر فقط المنتجات المتوفرة فعلاً InStock.
- رابط كل متجر يجب أن يكون رابط صفحة منتج مباشر (صفحة فيها منتج واحد وسعر واحد). ممنوع روابط الصفحة الرئيسية أو /search أو /category
- لا تخترع سعراً، انسخ السعر كما يظهر في نتيجة البحث اليوم.
- حاول تجيب 3 متاجر فقط، وإذا ما لقيت اذكر الموجود ولا تخترع.

في الحالات 1 و2 و3، سطر أخير إلزامي:
LINKS: اسم الأول=الدومين الحقيقي, اسم الثاني=الدومين الحقيقي
في الحالة 4: سطر LINKS اختياري.
ممنوع روابط ظاهرة. ممنوع Markdown.
لغة الرد: التزم بلغة الرد المطلوبة في رسالة المستخدم.
"""

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
    return stores[:MAX_STORES]

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
    return offers[:MAX_STORES]

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

def maps_category_for(product):
    """تصنيف محلي سريع للخريطة بدون أي اتصال Gemini إضافي."""
    q = normalize_ar(product)
    service_intent = any(w in q for w in ("فني", "تصليح", "صيانه", "صيانة", "تركيب", "عطل", "خدمه", "خدمة"))

    # كلمات تدل على خدمة بحد ذاتها.
    direct_service_rules = [
        (("بنشر", "تبديل بطاريه", "تبديل بطارية"), "بنشر تبديل إطارات بطارية Tyre repair"),
        (("سباك",), "سباك Plumbing service"),
        (("كهربائي",), "كهربائي Electrician"),
        (("فني زجاج", "فني مرايا"), "فني زجاج ومرايا Glass repair"),
        (("نجار",), "نجار Carpenter"),
        (("غسيل سياره", "تلميع سياره"), "Car wash detailing"),
    ]
    for words, category in direct_service_rules:
        if any(w in q for w in words):
            return category

    # الكلمات التالية قد تكون منتجاً أو خدمة؛ لا نعاملها كخدمة إلا مع نية صريحة.
    if service_intent:
        if any(w in q for w in ("تكييف", "مكيف", "سنترال")):
            return "فني تكييف Air conditioning repair"
        if any(w in q for w in ("زجاج", "مرايا", "المنيوم", "الومنيوم")):
            return "فني زجاج ومرايا Glass repair"
        if any(w in q for w in ("كهرباء", "افياش", "إنارة", "اناره")):
            return "كهربائي Electrician"

    if any(w in q for w in ("ثلاجه", "غساله", "فرن", "مكيف", "جلايه", "مكنسه")):
        return "Xcite OR Eureka home appliances"
    if any(w in q for w in ("ايفون", "سامسونج", "لابتوب", "بلايستيشن", "تلفزيون", "ساعه ابل", "الكترون")):
        return "Xcite OR Eureka OR Best Al Yousifi electronics"
    if any(w in q for w in ("دواء", "صيدليه", "فيتامين", "كريم", "شامبو", "حفاظ", "حفاض")):
        return "صيدلية Pharmacy"
    if any(w in q for w in GROCERY_WORDS):
        return "جمعية تعاونية Supermarket"
    return product

def maps_search_url(product, lat=None, lng=None):
    category = maps_category_for(product)
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
        return "none"
    if is_service_answer(txt):
        # الخدمات: رسالة واحدة فيها الاسم والرقم، وبعدها الخريطة بدون روابط متاجر.
        send_whatsapp_text(from_number, txt, bot_id)
        return "service"
    offers = extract_store_offers(txt)
    if not offers:
        send_whatsapp_text(from_number, txt, bot_id)
        return "info"
    title = product_title(txt, query)
    if title:
        send_whatsapp_text(from_number, title, bot_id)
    core = title[2:].strip() if title.startswith("📦") else query
    fq = short_query(core) or short_query(query)
    if best_only:
        best = next((o for o in offers if o["best"]), offers[0])
        offers = [best]
    for o in offers[:MAX_STORES]:
        url = match_url(o["name"], urls)
        if not url:
            if is_junk_store(o["name"]):
                continue
            url = fallback_search_url(fq, o["name"])
        send_whatsapp_cta(from_number, o["line"], url, bot_id, f"🛒 {o['name'][:18]}")
    return "product"

GEMINI_STATS = {"search_calls": 0, "plain_calls": 0}
GEMINI_STATS_LOCK = threading.Lock()

def call_gemini(parts, system=SYSTEM_PROMPT, use_search=True):
    model = GEMINI_SEARCH_MODEL if use_search else GEMINI_FAST_MODEL
    gemini_url = f"{GEMINI_BASE_URL}/{model}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": 0,
            # الرد المطلوب قصير؛ خفض الحد يقلل التوكنز ويمنع الردود الطويلة.
            "maxOutputTokens": 1000 if use_search else 300,
        },
    }
    if use_search:
        payload["tools"] = [{"google_search": {}}]
    with GEMINI_STATS_LOCK:
        key = "search_calls" if use_search else "plain_calls"
        GEMINI_STATS[key] += 1
        print(f"GEMINI CALL model={model} search={use_search} totals={GEMINI_STATS}")
    try:
        r = requests.post(gemini_url, params={"key": GEMINI_API_KEY}, json=payload, timeout=90)
        if r.status_code >= 400:
            print(f"Gemini HTTP {r.status_code}: {r.text[:500]}")
            return "", {}
        data = r.json()
        candidates = data.get("candidates") or []
        if not candidates:
            return "", {}
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
                    if name and "." in dom:
                        pairs.append((name, dom))
            text = re.sub(r"(?im)^\s*LINKS\s*:.*$", "", text).strip()
        text = re.sub(r"https?://\S+", "", text).replace("**", "").strip()
        metadata = cand.get("groundingMetadata", {}) or {}
        chunks = metadata.get("groundingChunks", []) or []
        uris = [(c.get("web") or {}).get("uri", "") for c in chunks]
        finals = resolve_all(uris[:12]) if uris else []
        records = []
        for i, chunk in enumerate(chunks[:12]):
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
                if store in urls_map:
                    break
        for name, dom in pairs:
            if name in urls_map:
                continue
            key = domain_key(dom)
            for rec in records:
                haystack = f"{rec['title']} {rec['raw']} {rec['url']}".lower()
                if rec["url"] and key and key in haystack and rec["url"] not in used_urls:
                    urls_map[name] = rec["url"]
                    used_urls.add(rec["url"])
                    break
        for store in stores:
            if store in urls_map:
                continue
            dom = store_domain(store)
            if not dom:
                continue
            key = domain_key(dom)
            for rec in records:
                haystack = f"{rec['title']} {rec['raw']} {rec['url']}".lower()
                if rec["url"] and key and key in haystack and rec["url"] not in used_urls:
                    urls_map[store] = rec["url"]
                    used_urls.add(rec["url"])
                    break
        if len(urls_map) < MAX_STORES:
            for rec in records:
                url = rec["url"]
                if not url or url in used_urls:
                    continue
                label = source_label(rec["title"], url)
                if label not in urls_map:
                    urls_map[label] = url
                    used_urls.add(url)
                if len(urls_map) >= MAX_STORES:
                    break
        return text, dict(list(urls_map.items())[:MAX_STORES])
    except Exception as e:
        print(f"Gemini err {e}")
        return "", {}

def source_label(title, url):
    title = (title or "").strip()
    if title: return title[:40]
    try:
        host = urllib.parse.urlparse(url).netloc.replace("www.", "")
        return host.split(".")[0] or "المتجر"
    except: return "المتجر"

def best_of_search(parts, lang="ar"):
    """اتصال واحد فقط. يعاد الاتصال مرة واحدة فقط عند فشل تقني وبموافقة Environment Variable."""
    txt, urls = call_gemini(parts)
    if txt or not ENABLE_SEARCH_RETRY:
        return txt, urls
    print("SEARCH RETRY: first call returned empty")
    return call_gemini(parts)

def search_product(query, lang, prompt_text=None):
    cached = cache_get(query, lang)
    if cached:
        return cached

    q_norm = normalize_ar(query)
    grocery_hint = ""
    if any(w in q_norm for w in GROCERY_WORDS):
        grocery_hint = " ابحث ضمن نفس العملية أيضاً في عروض ClicFlyer إن وُجد عرض سارٍ."

    single_prompt = prompt_text or (
        f"ابحث عن {query} في الكويت. أعطني أفضل 3 نتائج فقط، متوفر InStock، "
        f"وكل رابط يجب أن يكون صفحة منتج مباشرة.{grocery_hint} {LANG_INSTR[lang]}"
    )

    # أهم تعديل اقتصادي: اتصال Gemini Grounded Search واحد فقط لكل بحث غير موجود في الكاش.
    txt, merged_urls = call_gemini([{"text": single_prompt}])
    if not txt and ENABLE_SEARCH_RETRY:
        fallback_prompt = (
            f"ابحث مرة أخيرة عن {query} في الكويت وأعطني المتوفر فقط مع 3 نتائج كحد أقصى. "
            f"{LANG_INSTR[lang]}"
        )
        txt, merged_urls = call_gemini([{"text": fallback_prompt}])

    if not txt:
        return "", {}

    merged_urls = dict(list((merged_urls or {}).items())[:MAX_URLS_MERGED])

    if is_service_answer(txt) or not extract_store_offers(txt):
        if len(txt) >= 40:
            cache_put(query, lang, txt, merged_urls)
        return txt, merged_urls

    verified = verify_offers(merged_urls, query)
    if verified:
        sorted_v = sorted(verified.items(), key=lambda x: x[1]["price"])
        title = product_title(txt, query)
        lines = [title, ""]
        new_urls = {}
        for i, (name, info) in enumerate(sorted_v[:MAX_STORES]):
            prefix = "✅" if i == 0 else "•"
            lines.append(f"{prefix} {name} — {format_price(info['price'])} د.ك")
            new_urls[name] = info["url"]
        final_txt = "\n".join(lines)
        cache_put(query, lang, final_txt, new_urls)
        print(f"VERIFIED OK: {query} -> {len(new_urls)} stores from {len(merged_urls)} raw")
        return final_txt, new_urls

    print(f"VERIFIED FAIL - returning raw result for: {query}")
    cache_put(query, lang, txt, merged_urls)
    return txt, merged_urls

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
    result_type = send_product_result(from_number, txt, urls, bot_id, lang, query)
    if product_name and product_name != "المنتج":
        if result_type == "service" or (result_type == "product" and AUTO_SEND_PRODUCT_MAPS):
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

def is_map_command(text):
    compact = re.sub(r"[^\w\u0600-\u06FF]", "", normalize_ar(text))
    exact = {
        "الخريطه", "خريطه", "الموقع", "موقع", "اللوكيشن", "لوكيشن",
        "الاقرب", "اقربمكان", "وينه", "ويناحصله", "وينالاقيه",
        "map", "location", "nearest", "closest"
    }
    return compact in exact

def send_last_search_map(from_number, bot_id, lang):
    last_search = LAST_SEARCH.get(from_number)
    if not last_search or not last_search.get("product"):
        send_whatsapp_text(from_number, T(lang, "no_saved_product"), bot_id)
        return
    send_maps_button(from_number, last_search["product"], bot_id, lang)

def process_text_message(message,bot_id):
    from_number=message["from"]; user_text=message["text"]["body"]
    cmd=re.sub(r"[^\w\u0600-\u06FF]","",user_text.strip().lower())
    if cmd in ("لغة","اللغة","غيراللغة","language","lang","changelanguage"):
        send_language_choice(from_number, bot_id); return
    detected=detect_lang(user_text)
    if detected: USER_LANG[from_number]=detected
    lang=USER_LANG.get(from_number,"ar")
    if is_map_command(user_text):
        send_last_search_map(from_number, bot_id, lang)
        return
    pend=PENDING_IMAGES.pop(from_number,None)
    if pend and pend["images"]:
        if len(pend["images"])==1: process_single_image(pend["images"][0], pend["bot_id"], lang)
        else: process_multi_images(pend["images"], from_number, pend["bot_id"], lang)
    products=extract_products(user_text)
    if len(products)==1:
        send_whatsapp_text(from_number,T(lang,"searching",q=products[0]),bot_id)
        txt,urls=search_product(products[0], lang)
        LAST_SEARCH[from_number] = {"product": products[0]}
        result_type = send_product_result(from_number, txt, urls, bot_id, lang, products[0])
        if result_type == "service" or (result_type == "product" and AUTO_SEND_PRODUCT_MAPS):
            send_maps_button(from_number, products[0], bot_id, lang)
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
async def health(): return {"status":"v33 economic - one grounded search + persistent cache + maps without AI"}
