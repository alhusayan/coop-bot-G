# -*- coding: utf-8 -*-
import os, re, time, base64, requests, json, asyncio, urllib.parse, hashlib, sqlite3, threading
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Request, Response, BackgroundTasks
from bs4 import BeautifulSoup

app = FastAPI()
BUILD_ID = "v53-two-layer-search-20260802"
print("=" * 70)
print(f"STARTING COOP BOT BUILD: {BUILD_ID}")
print("LENS MODE: DIRECT — NO STRICT VISUAL SELECTION")
print("=" * 70)


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
OLD_SEARCH_POOL = ThreadPoolExecutor(max_workers=8)
OLD_LAYER_DUPLICATES = max(1, int(os.environ.get("OLD_LAYER_DUPLICATES", "2")))
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")

OLD_LAYER_ENABLED = env_bool("OLD_LAYER_ENABLED", True)

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
ENABLE_SEARCH_RETRY = env_bool("ENABLE_SEARCH_RETRY", True)
MAX_SEARCH_ATTEMPTS = max(2, int(os.environ.get("MAX_SEARCH_ATTEMPTS", "3")))
MAX_IDENTIFY_ATTEMPTS = max(2, int(os.environ.get("MAX_IDENTIFY_ATTEMPTS", "3")))
AUTO_SEND_PRODUCT_MAPS = env_bool("AUTO_SEND_PRODUCT_MAPS", True)
# Google Lens عبر SerpApi. لا توجد Google Lens API عامة رسمية للاستخدام الخادمي،
# لذلك نستخدم SerpApi للوصول إلى نتائج Lens المنظمة.
SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY", "").strip()
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
ENABLE_GOOGLE_LENS = env_bool("ENABLE_GOOGLE_LENS", True)
LENS_RESULT_LIMIT = max(12, int(os.environ.get("LENS_RESULT_LIMIT", "40")))
LENS_IMAGE_TTL = max(120, int(os.environ.get("LENS_IMAGE_TTL_SECONDS", "600")))
LENS_IMAGE_STORE = {}
LENS_IMAGE_LOCK = threading.Lock()

GROCERY_WORDS = [
    "بيبسي","شيبس","حليب","قهوه","قهوة","شاي","سكر","رز","زيت","صابون","شامبو",
    "برينجلز","كيتكات","نسكافيه","تونه","ماء","عصير","بسكوت","منظف","معجون","حفاض"
]

print("STARTING COOP BOT BUILD: v53-two-layer-search-20260802")
print(
    f"ECONOMIC CONFIG search_model={GEMINI_SEARCH_MODEL} fast_model={GEMINI_FAST_MODEL} "
    f"max_stores={MAX_STORES} search_attempts={MAX_SEARCH_ATTEMPTS} "
    f"identify_attempts={MAX_IDENTIFY_ATTEMPTS} auto_maps={AUTO_SEND_PRODUCT_MAPS}"
)

VERIFIED_PAGE_CACHE = {}
OOS_PHRASES = ["out of stock","غير متوفر","نفدت الكمية","غير متاح","sold out","غير متوفر حاليا","نفذت","not available","temporarily unavailable"]
LISTING_URL_PARTS = ["/search","/s?","/category","/categories","/collection","/collections","/shop/category","?q=","/search_results","/shop/","/listing","/c/"]

def format_price(p):
    """KWD formatting: values below 1 KD always keep all three fils digits."""
    try:
        pf = float(p)
        if pf < 1:
            return f"{pf:.3f}"
        if pf < 100:
            return f"{pf:.3f}".rstrip('0').rstrip('.')
        return f"{pf:.2f}".rstrip('0').rstrip('.')
    except Exception:
        return str(p)


def format_lens_price(price_text, price_value, lang="ar"):
    """Normalise Lens prices so 0.75 KWD becomes 0.750 د.ك, without rounding to 1 KD."""
    numeric = None
    try:
        if price_value not in (None, ""):
            numeric = float(price_value)
    except Exception:
        numeric = None
    if numeric is None:
        m = re.search(r"(?<!\d)(\d+(?:[.,]\d{1,3})?)(?!\d)", str(price_text or "").replace(",", ""))
        if m:
            try:
                numeric = float(m.group(1))
            except Exception:
                numeric = None
    if numeric is None:
        return str(price_text or "").strip()
    currency = "KWD" if lang == "en" else "د.ك"
    return f"{format_price(numeric)} {currency}"

def is_direct_store_url(url):
    """يمنع روابط Google والبحث والتصنيفات؛ يقبل روابط المتاجر المباشرة فقط."""
    if not url or not url.startswith(("http://", "https://")):
        return False
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc.lower().replace("www.", "")
        path_q = (parsed.path + ("?" + parsed.query if parsed.query else "")).lower()
    except Exception:
        return False
    blocked_hosts = (
        "google.com", "google.com.kw", "googleusercontent.com", "gstatic.com",
        "bing.com", "yahoo.com"
    )
    if any(host == h or host.endswith("." + h) for h in blocked_hosts):
        return False
    if not parsed.path or parsed.path == "/":
        return False
    if any(part in path_q for part in LISTING_URL_PARTS):
        # بعض المتاجر تستخدم /shop/ داخل صفحة المنتج؛ نسمح فقط إذا ظهر نمط منتج واضح.
        if not re.search(r"/product/|/products/[^/]{3,}|/p/|/dp/|/item/|/prod/", path_q):
            return False
    # صفحات البراند/القسم ليست صفحات منتج حتى لو كان الرابط طويلاً.
    collection_patterns = (
        r"/designers/[^/]+/shoes/?$", r"/designers/[^/]+/[^/]+/?$",
        r"/brand/[^/]+/?$", r"/brands/[^/]+/?$", r"/mules/?$",
        r"/shoes/?$", r"/women/?$", r"/men/?$"
    )
    if any(re.search(p, parsed.path.lower()) for p in collection_patterns):
        return False
    return True

def direct_urls_only(urls):
    return {name: url for name, url in (urls or {}).items() if is_direct_store_url(url)}

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
    return hashlib.sha256(f"v50|{norm}|{lang}".encode()).hexdigest()

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

IDENTIFY_SYSTEM = """أنت خبير تعرف على المنتجات من الصور للسوق الكويتي.
أرجع دائماً اسمين قابلين للبحث بهذا الشكل فقط:
[الاسم التجاري بالعربية] | [commercial product name in English]
ضع البراند ورقم الموديل إن ظهر. استنتج نوع المنتج من الشعار والشكل والنص الظاهر.
لا ترفض التحديد لمجرد أن الصورة غير كاملة؛ أعطِ أقرب اسم تجاري مفيد للبحث.
مثال: ريموت بي إن سبورت | beIN Sports remote control
سطر واحد فقط، بدون شرح."""

MSG = {
    "ar": {
        "identifying": "ثواني بس.. أحدد المنتج وأدور لك الأفضل!",
        "searching": "🔍 أدور لك على {q}...",
        "not_found": "ما لقيت المنتج متوفر حالياً بسعر مؤكد 😅 جرب صياغة ثانية أو دز صورة أوضح.",
        "cant_identify": "بحثت أكثر من مرة، لكن ما قدرت أحدد المنتج أو ألقى له نتيجة مؤكدة. دز صورة أوضح أو اكتب اسم المنتج.",
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
        "cant_identify": "I searched several times but couldn’t identify the product or find a verified result. Send a clearer photo or type the product name.",
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

الأولوية دائماً للمتاجر الكبيرة والمعروفة في الكويت، ثم المتاجر المتخصصة حسب نوع المنتج.
ابدأ بالمتاجر الشاملة: جمعية دوت كوم، كيتا، طلبات، نون، لولو، كارفور، ثم أضف المتاجر المتخصصة المناسبة للقسم.
لا تعرض متجراً غير معروف إذا وُجد متجر كويتي معروف يبيع نفس المنتج بسعر موثق.

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
- اذكر فقط المنتجات المتوفرة فعلاً. لا تكتب كلمة InStock أو متوفر مكان السعر.
- أي متجر لا يظهر له سعر رقمي واضح بالدينار الكويتي احذفه من النتيجة.
- ممنوع أن يكون الرد عبارة عن أسماء متاجر مع كلمة متوفر فقط؛ كل سطر عرض يجب أن يحتوي سعراً رقمياً.
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
    data = {"price": None, "available": True, "is_product": True, "title": "", "image_url": ""}
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
                    if not data["image_url"]:
                        image = obj.get("image")
                        if isinstance(image, list) and image:
                            image = image[0]
                        if isinstance(image, dict):
                            image = image.get("url") or image.get("contentUrl")
                        if isinstance(image, str) and image.startswith("http"):
                            data["image_url"] = image
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
    if not data["image_url"]:
        for attrs in ({"property": "og:image"}, {"name": "twitter:image"}, {"property": "twitter:image"}):
            m = soup.find("meta", attrs=attrs)
            if m and m.get("content") and str(m.get("content")).startswith("http"):
                data["image_url"] = str(m.get("content"))
                break
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
            verified[name] = {"url": url, "price": info["price"], "title": info["title"], "image_url": info.get("image_url", "")}
    return verified

def _cleanup_lens_images():
    now = time.time()
    with LENS_IMAGE_LOCK:
        expired = [k for k, v in LENS_IMAGE_STORE.items() if v.get("expires_at", 0) <= now]
        for k in expired:
            LENS_IMAGE_STORE.pop(k, None)

def publish_image_for_lens(image_b64, mime_type):
    """يحفظ صورة واتساب مؤقتاً ويعيد رابطاً عاماً تستطيع Google Lens قراءته."""
    if not PUBLIC_BASE_URL or not image_b64:
        return ""
    try:
        raw = base64.b64decode(image_b64)
    except Exception:
        return ""
    if not raw or len(raw) > 15 * 1024 * 1024:
        return ""
    _cleanup_lens_images()
    token = hashlib.sha256(raw + os.urandom(16)).hexdigest()[:32]
    with LENS_IMAGE_LOCK:
        LENS_IMAGE_STORE[token] = {
            "content": raw,
            "mime": mime_type or "image/jpeg",
            "expires_at": time.time() + LENS_IMAGE_TTL,
        }
    return f"{PUBLIC_BASE_URL}/lens-image/{token}"

def _lens_items(data):
    items = []
    seen = set()
    for key in ("visual_matches", "exact_matches", "products"):
        values = data.get(key) or []
        if isinstance(values, dict):
            values = values.get("results") or []
        for x in values:
            if not isinstance(x, dict):
                continue
            title = (x.get("title") or "").strip()
            link = (x.get("link") or "").strip()
            source = (x.get("source") or "").strip()
            sig = (title.lower(), link.lower())
            if not title or sig in seen:
                continue
            seen.add(sig)
            items.append({
                "title": title,
                "link": link,
                "source": source,
                "position": int(x.get("position") or len(items) + 1),
                "exact": bool(x.get("exact_matches")),
                "thumbnail": (x.get("thumbnail") or x.get("image") or "").strip(),
                "image": (x.get("image") or x.get("thumbnail") or "").strip(),
                "price": ((x.get("price") or {}).get("value") if isinstance(x.get("price"), dict) else str(x.get("price") or "")),
                "price_value": ((x.get("price") or {}).get("extracted_value") if isinstance(x.get("price"), dict) else x.get("extracted_price")),
                "currency": ((x.get("price") or {}).get("currency") if isinstance(x.get("price"), dict) else ""),
                "in_stock": x.get("in_stock"),
                "condition": (x.get("condition") or "").strip(),
            })
    return items[:LENS_RESULT_LIMIT]

def _download_lens_candidate(url):
    """ينزّل صورة مصغرة من نتائج Lens للمقارنة المؤقتة فقط."""
    if not url or not url.startswith(("http://", "https://")):
        return None
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        ctype = (r.headers.get("content-type") or "image/jpeg").split(";")[0]
        if r.status_code != 200 or not r.content or len(r.content) > 5 * 1024 * 1024:
            return None
        if not ctype.startswith("image/"):
            ctype = "image/jpeg"
        return base64.b64encode(r.content).decode(), ctype
    except Exception as e:
        print(f"LENS CANDIDATE IMAGE ERR: {e}")
        return None


def google_lens_lookup(image_b64, mime_type, lang="ar", query_hint=""):
    """يستخدم أفضل نتيجة Google Lens مباشرة، ثم يستخرج وصفاً شكلياً من الصورة الأصلية فقط.

    لا نطلب من Gemini اختيار صورة من صور Lens؛ لأن الصور المصغرة قد لا تُحمّل أو قد تجعل المقارنة
    المتشددة ترجع NONE رغم أن Lens عرّف المنتج بصورة صحيحة.
    """
    if not ENABLE_GOOGLE_LENS or not SERPAPI_API_KEY or not PUBLIC_BASE_URL:
        print("GOOGLE LENS SKIPPED: missing SERPAPI_API_KEY or PUBLIC_BASE_URL")
        return {"aliases": [], "matches": [], "query": ""}

    public_url = publish_image_for_lens(image_b64, mime_type)
    if not public_url:
        print("GOOGLE LENS SKIPPED: could not publish image")
        return {"aliases": [], "matches": [], "query": ""}

    params = {
        "engine": "google_lens",
        "type": "products",
        "url": public_url,
        "api_key": SERPAPI_API_KEY,
        "country": "kw",
        "hl": "en",
        "auto_crop": "true",
        "safe": "active",
        "output": "json",
    }
    if query_hint:
        params["q"] = query_hint[:120]

    try:
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=60)
        if r.status_code >= 400:
            print(f"GOOGLE LENS HTTP {r.status_code}: {r.text[:300]}")
            return {"aliases": [], "matches": [], "query": ""}
        data = r.json()
        if data.get("error"):
            print(f"GOOGLE LENS ERROR: {data.get('error')}")
            return {"aliases": [], "matches": [], "query": ""}

        matches = _lens_items(data)
        if not matches:
            print("GOOGLE LENS: no visual matches")
            return {"aliases": [], "matches": [], "query": ""}

        # اطبع أول النتائج حتى نعرف فعلياً ماذا أعاد Lens.
        for i, m in enumerate(matches[:5], 1):
            print(f"LENS MATCH {i}: {m.get('title','')} | {m.get('source','')} | exact={m.get('exact', False)}")

        # نختار أول نتيجة Visual Match ذات عنوان واضح. exact_matches تحصل على أولوية،
        # ثم ترتيب Google Lens نفسه. نستبعد العناوين العامة جداً فقط.
        generic = re.compile(r"^(mules?|shoes?|slippers?|sandals?|footwear|بوتيغا فينيتا|bottega veneta)$", re.I)
        ranked = []
        for m in matches:
            title = (m.get("title") or "").strip()
            if not title or generic.match(title):
                continue
            score = 1000 if m.get("exact") else 0
            score += max(0, 200 - int(m.get("position") or 99) * 10)
            score += min(len(title), 120) / 10
            if m.get("thumbnail") or m.get("image"):
                score += 10
            ranked.append((score, m))
        chosen = max(ranked, key=lambda x: x[0])[1] if ranked else matches[0]
        chosen_title = (chosen.get("title") or "").strip()

        # Gemini هنا لا يقرر أي نتيجة Lens صحيحة. فقط يصف الصورة الأصلية ويترجم الاسم.
        # هذا يمنحنا اللون/النقشة/الكعب لحماية نتائج الأسعار من المنتجات المختلفة.
        sig_system = (
            "أنت خبير منتجات. الصورة هي المرجع الوحيد. استخرج اسماً عربياً وإنجليزياً ووصفاً شكلياً محافظاً. "
            "لا تخترع رقم موديل. حدد اللون الأساسي، النقشة أو الخامة الظاهرة، وهل المنتج مسطح أو بكعب. "
            "الرد سطر واحد فقط: Arabic name | English name | COLOR | PATTERN | HEEL | TYPE. "
            "HEEL واحدة من FLAT, LOW, HIGH, NONE, UNKNOWN. TYPE مثل MULES, SLIPPERS, SHOES, BAG, ELECTRONICS."
        )
        sig_txt, _ = call_gemini([
            {"inline_data": {"mime_type": mime_type, "data": image_b64}},
            {"text": f"Google Lens title hint: {chosen_title}"},
        ], system=sig_system, use_search=False)
        fields = [x.strip() for x in ((sig_txt or "").strip().splitlines()[0] if sig_txt else "").split("|")]

        ar_name = fields[0] if len(fields) > 0 else ""
        en_name = fields[1] if len(fields) > 1 else ""
        signature = {
            "color": fields[2].lower() if len(fields) > 2 else "",
            "pattern": fields[3].lower() if len(fields) > 3 else "",
            "heel": fields[4].upper() if len(fields) > 4 else "UNKNOWN",
            "type": fields[5].upper() if len(fields) > 5 else "",
        }

        aliases = []
        # عنوان Lens أولاً لأنه أساس التعرف، ثم الترجمتان من الصورة الأصلية.
        for value in (chosen_title, en_name, ar_name):
            value = (value or "").strip()
            if value and value.upper() not in ("NONE", "UNKNOWN") and value not in aliases:
                aliases.append(value)

        query = " | ".join(aliases[:3])
        print(f"GOOGLE LENS DIRECT MATCH: {query}")
        print(f"GOOGLE LENS SIGNATURE: {signature}")
        return {
            "aliases": aliases[:3],
            "matches": matches,
            "query": query,
            "chosen": chosen,
            "signature": signature,
        }
    except Exception as e:
        print(f"GOOGLE LENS EXCEPTION: {e}")
        return {"aliases": [], "matches": [], "query": ""}

def _meaningful_lens_tokens(text):
    """Extract discriminative tokens from the chosen Lens title, excluding generic words and sizes."""
    raw = normalize_ar(text or "").lower()
    toks = re.findall(r"[a-z0-9؀-ۿ]+", raw)
    stop = {
        "women","woman","men","man","size","new","used","authentic","leather","جلد",
        "mules","mule","shoes","shoe","slippers","slipper","sandals","sandal",
        "for","the","and","in","with","kw","kuwait","uae","كويت","نسائي","رجالي",
    }
    out=[]
    for t in toks:
        if t in stop or t.isdigit() or len(t) < 3:
            continue
        if t not in out:
            out.append(t)
    return out


def _lens_offer_compatible(info, url, lens_context):
    """Strict guard for image searches. Candidate title/URL alone must match the Lens identity."""
    if not lens_context:
        return True
    sig = lens_context.get("signature") or {}
    chosen = lens_context.get("chosen") or {}
    candidate_hay = normalize_ar(" ".join([str(info.get("title", "")), str(url)])).lower()
    chosen_title = normalize_ar(str(chosen.get("title", ""))).lower()

    # Brand is mandatory when Lens returned a clear brand.
    brand_aliases = {
        "bottega veneta": ("bottega", "veneta", "بوتيغا", "بوتيقا"),
        "under armour": ("under", "armour", "اندر", "ارمور"),
    }
    for brand, aliases in brand_aliases.items():
        if brand in chosen_title and not any(normalize_ar(a) in candidate_hay for a in aliases):
            return False

    # At least one discriminative Lens token must occur in the candidate itself.
    desired_tokens = _meaningful_lens_tokens(chosen_title)
    descriptor_tokens = [t for t in desired_tokens if t not in ("bottega", "veneta")]
    if descriptor_tokens and not any(t in candidate_hay for t in descriptor_tokens):
        print(f"LENS TOKEN REJECT: wanted={descriptor_tokens} candidate={candidate_hay[:180]}")
        return False

    heel = (sig.get("heel") or "UNKNOWN").upper()
    high_words = ("high heel", "high heels", "stiletto", "kitten heel", "heeled", "pump", "كعب عالي", "كعب ذهبي")
    if heel in ("FLAT", "NONE") and any(normalize_ar(w) in candidate_hay for w in high_words):
        return False

    pattern = normalize_ar(sig.get("pattern") or "")
    if pattern and pattern not in ("unknown", "none", "غير معروف"):
        pattern_groups = {
            "woven": ("woven", "intrecciato", "weave", "handwoven", "منسوج", "ضفيره"),
            "intrecciato": ("woven", "intrecciato", "weave", "handwoven", "منسوج", "ضفيره"),
            "braided": ("braided", "woven", "intrecciato", "مضفر", "منسوج"),
        }
        keys = pattern_groups.get(pattern, (pattern,))
        # For an explicitly woven item, require the candidate itself to say so.
        if pattern in pattern_groups and not any(normalize_ar(k) in candidate_hay for k in keys):
            return False

    color = normalize_ar(sig.get("color") or "")
    if color and color not in ("unknown", "none", "غير معروف"):
        color_map = {
            "brown": ("brown", "tan", "cognac", "camel", "burgundy", "بني", "جملي"),
            "black": ("black", "اسود"),
            "green": ("green", "اخضر"),
            "white": ("white", "ivory", "cream", "ابيض"),
        }
        wanted = tuple(normalize_ar(x) for x in color_map.get(color, (color,)))
        explicit_colors = tuple(normalize_ar(x) for x in (
            "black","green","white","red","blue","silver","gold","pink","purple",
            "اسود","اخضر","ابيض","احمر","ازرق","ذهبي","وردي","بنفسجي"
        ))
        if any(c in candidate_hay for c in explicit_colors) and not any(c in candidate_hay for c in wanted):
            return False

    return True

def filter_verified_with_lens(verified, lens_context):
    if not lens_context:
        return verified
    kept = {}
    for name, info in (verified or {}).items():
        if _lens_offer_compatible(info, info.get("url", ""), lens_context):
            kept[name] = info
        else:
            print(f"LENS PRICE REJECT: {name} -> {info.get('title','')} -> {info.get('url','')}")
    return kept

def rank_verified_by_image(source_b64, source_mime, verified):
    """تم تعطيل فلتر Gemini البصري؛ Lens يحدد الاسم أولاً، والأسعار تبقى من محرك البحث المجرب."""
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
    "جمعية دوت كوم": "jm3eia.com", "جمعيه دوت كوم": "jm3eia.com", "جميعة": "jm3eia.com", "jm3eia": "jm3eia.com",
    "كيتا": "mykeeta.com", "keeta": "mykeeta.com",
    "انترسبورت": "intersport.com.kw", "إنترسبورت": "intersport.com.kw", "intersport": "intersport.com.kw",
    "ديكاثلون": "decathlon.com.kw", "decathlon": "decathlon.com.kw",
}


def priority_stores_for(query):
    """يرتب أهم المتاجر الكويتية حسب فئة المنتج ويُستخدم داخل طلب البحث."""
    q = normalize_ar(query)
    general = ["جمعية دوت كوم", "طلبات", "كيتا", "نون", "لولو", "كارفور"]

    rules = [
        (("ايفون", "سامسونج", "لابتوب", "تابلت", "بلايستيشن", "اكس بوكس", "تلفزيون", "الكترون", "هاتف", "ساعه ابل", "سماعه"),
         ["Xcite", "Eureka", "Best Al-Yousifi", "Blink", "Jarir", "Noon"]),
        (("ثلاجه", "غساله", "فرن", "مكيف", "جلايه", "مكنسه", "قلايه", "ميكرويف"),
         ["Xcite", "Eureka", "Best Al-Yousifi", "Lulu", "Carrefour", "Noon"]),
        (("عطر", "برفان", "مكياج", "كريم", "سيروم", "عنايه", "شامبو"),
         ["Boutiqaat", "Bloomingdale's Kuwait", "Faces", "Sephora", "Noon", "جمعية دوت كوم"]),
        (("دواء", "صيدليه", "فيتامين", "مكمل", "حفاض", "حفاظ"),
         ["Boots Kuwait", "YIACO", "Royal Pharmacy", "جمعية دوت كوم", "Talabat"]),
        (("بيبسي", "شيبس", "حليب", "قهوه", "شاي", "سكر", "رز", "زيت", "ماء", "عصير", "بسكوت", "منظف", "صابون"),
         ["جمعية دوت كوم", "Lulu", "Carrefour", "Talabat", "Keeta"]),
        (("مطعم", "وجبه", "برجر", "بيتزا", "قهوه", "فلات وايت", "شاورما", "دجاج"),
         ["Keeta", "Talabat", "Deliveroo"]),
        (("ملابس", "قميص", "بنطلون", "حذاء", "كاب", "قبعه", "شنطه", "رياضه"),
         ["Intersport Kuwait", "Decathlon Kuwait", "Sun & Sand Sports", "Foot Locker", "Noon", "Namshi"]),
        (("اثاث", "كرسي", "طاوله", "سرير", "كنب", "مرتبه"),
         ["IKEA Kuwait", "The One", "Home Centre", "Noon", "Lulu"]),
        (("اطفال", "لعبه", "العاب", "عربانه", "رضاعه"),
         ["Toys R Us Kuwait", "Mothercare", "Centrepoint", "Noon", "جمعية دوت كوم"]),
        (("سياره", "بطاريه", "اطار", "زيت محرك", "اكسسوار"),
         ["Tires Plus", "AlMailem", "Xcite", "Noon"]),
    ]
    for words, stores in rules:
        if any(w in q for w in words):
            return stores
    return general

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
            if name and name not in stores:
                stores.insert(0, name)
            continue
        # Accept both formats: "Store — 3.500 KWD" and "Store — KWD 143*".
        m = re.match(r"^\s*(?:✅|🏆|•)\s*(.+?)\s*(?:—|–|-)\s*(.+)$", line)
        if m and re.search(r"\d", m.group(2)):
            name = m.group(1).strip()
            if name and name not in stores:
                stores.append(name)
    return stores[:MAX_STORES]

def is_service_answer(txt): return bool(re.search(r"(?:🏆|•)\s*.+?\(\s*(?:هاتف|Phone|phone|Tel|tel)\s*:", txt or ""))
def extract_store_offers(txt):
    offers = []
    for line in (txt or "").splitlines():
        s = line.strip()
        # Price may appear before or after KWD and may include an asterisk from Lens.
        m = re.match(r"^(✅|🏆|•)\s*(.+?)\s*(?:—|–|-)\s*(.+)$", s)
        if not m or not re.search(r"\d", m.group(3)):
            continue
        if re.search(r"\(\s*(?:هاتف|Phone|phone|Tel|tel)\s*:", s):
            continue
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
    """اختيار نوع المتاجر في خرائط Google حسب تصنيف المنتج، بدون اتصال Gemini."""
    q = normalize_ar(product)
    service_intent = any(w in q for w in (
        "فني", "تصليح", "صيانه", "صيانة", "تركيب", "عطل", "خدمه", "خدمة",
        "repair", "service", "installation", "technician"
    ))

    service_rules = [
        (("بنشر", "اطارات", "إطارات", "تبديل بطاريه", "تبديل بطارية", "tyre", "tire", "car battery"),
         "محل إطارات وبطاريات سيارات Tyre and car battery shop"),
        (("سباك", "plumber", "plumbing"), "سباك Plumbing service"),
        (("كهربائي", "electrician"), "كهربائي Electrician"),
        (("فني زجاج", "فني مرايا", "glass repair"), "فني زجاج ومرايا Glass repair"),
        (("نجار", "carpenter"), "نجار Carpenter"),
        (("غسيل سياره", "غسيل سيارة", "تلميع سياره", "car wash", "detailing"), "Car wash detailing"),
        (("مفتاح", "اقفال", "أقفال", "locksmith"), "محل مفاتيح وأقفال Locksmith"),
        (("مكافحة حشرات", "pest control"), "مكافحة حشرات Pest control"),
    ]
    for words, category in service_rules:
        if any(w in q for w in words):
            return category

    if service_intent:
        if any(w in q for w in ("تكييف", "مكيف", "سنترال", "air condition")):
            return "فني تكييف Air conditioning repair"
        if any(w in q for w in ("زجاج", "مرايا", "المنيوم", "الومنيوم", "aluminium")):
            return "فني زجاج وألمنيوم Glass and aluminium repair"
        if any(w in q for w in ("كهرباء", "افياش", "إنارة", "اناره", "electrical")):
            return "كهربائي Electrician"
        if any(w in q for w in ("غساله", "ثلاجه", "فرن", "جلايه", "مكنسه", "appliance")):
            return "صيانة أجهزة منزلية Home appliance repair"

    category_rules = [
        (("عطر", "عطور", "برفان", "perfume", "eau de parfum", "eau de toilette"),
         "محل عطور Perfume store"),
        (("مكياج", "روج", "فاونديشن", "ماسكرا", "كونسيلر", "مستحضرات تجميل", "cosmetic", "makeup"),
         "متجر مستحضرات تجميل Cosmetics store"),
        (("كريم", "سيروم", "واقي شمس", "عناية بالبشره", "عناية بالبشرة", "skincare"),
         "صيدلية أو متجر عناية بالبشرة Pharmacy skincare store"),
        (("دواء", "صيدليه", "صيدلية", "فيتامين", "مكمل", "حفاض", "حفاظ", "pharmacy", "medicine"),
         "صيدلية Pharmacy"),
        (("نظاره", "نظارة", "عدسات", "sunglasses", "eyeglasses", "contact lens"),
         "محل نظارات Optician"),
        (("ساعه", "ساعة", "رولكس", "watch"), "محل ساعات Watch store"),
        (("ذهب", "مجوهرات", "خاتم", "سلسله", "سلسلة", "jewelry", "jewellery"),
         "محل مجوهرات Jewelry store"),
        (("ملابس", "تيشيرت", "قميص", "بنطلون", "فستان", "جاكيت", "قبعه", "قبعة", "كاب", "shirt", "dress", "cap", "clothing"),
         "Intersport OR Decathlon OR Sun and Sand Sports OR متجر ملابس Fashion store"),
        (("حذاء", "جوتي", "سنيكر", "shoe", "sneaker"), "Intersport OR Decathlon OR Foot Locker OR متجر أحذية Shoe store"),
        (("مضرب", "كره", "كرة", "تنس", "بادل", "جيم", "رياضه", "رياضة", "under armour", "nike", "adidas", "sports"),
         "Intersport OR Decathlon OR Sun and Sand Sports OR متجر رياضي Sports store"),
        (("ايفون", "آيفون", "سامسونج", "لابتوب", "بلايستيشن", "تلفزيون", "الكترون", "هاتف", "جوال", "كاميرا",
          "iphone", "samsung", "laptop", "playstation", "television", "electronics"),
         "متجر إلكترونيات Electronics store"),
        (("ثلاجه", "ثلاجة", "غساله", "غسالة", "فرن", "مكيف", "جلايه", "جلاية", "مكنسه", "مكنسة"),
         "متجر أجهزة منزلية Home appliances store"),
        (("كنب", "صوفا", "طاولة", "كرسي", "اثاث", "أثاث", "مرتبه", "مرتبة", "furniture", "mattress"),
         "متجر أثاث Furniture store"),
        (("ادوات منزليه", "أدوات منزلية", "صحون", "قدور", "مطبخ", "kitchenware", "homeware"),
         "متجر أدوات منزلية Homeware store"),
        (("العاب اطفال", "ألعاب أطفال", "لعبه", "لعبة", "toy"), "متجر ألعاب أطفال Toy store"),
        (("عربانه", "عربة أطفال", "كرسي طفل", "رضاعه", "رضاعة", "baby"),
         "متجر مستلزمات أطفال Baby store"),
        (("قطع غيار", "زيت محرك", "اكسسوارات سياره", "إكسسوارات سيارة", "car accessories", "auto parts"),
         "متجر قطع غيار وإكسسوارات سيارات Auto parts store"),
        (("دريل", "عدد", "ادوات", "أدوات", "مسمار", "صبغ", "دهان", "hardware", "tools"),
         "متجر عدد وأدوات Hardware store"),
        (("اكل قطط", "أكل قطط", "اكل كلاب", "أكل كلاب", "حيوانات", "pet"),
         "متجر مستلزمات حيوانات أليفة Pet store"),
        (("كتاب", "روايه", "رواية", "قرطاسيه", "قرطاسية", "book", "stationery"),
         "مكتبة Bookstore stationery"),
    ]
    for words, category in category_rules:
        if any(w in q for w in words):
            return category

    if any(w in q for w in GROCERY_WORDS) or any(w in q for w in (
        "مياه", "مشروب", "اغذيه", "أغذية", "طعام", "شوكولاته", "شوكولاتة",
        "مناديل", "منظف", "غسيل", "grocery", "food", "beverage"
    )):
        return "جمعية تعاونية أو سوبرماركت Supermarket"

    # بدل البحث عن اسم المنتج وحده، نضيف صيغة متجر حتى تكون نتائج الخريطة أماكن بيع.
    return f"متجر يبيع {product} الكويت"

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
    sent = 0
    for o in offers[:MAX_STORES]:
        url = match_url(o["name"], urls)
        # ممنوع تماماً تحويل المستخدم إلى Google أو صفحة بحث أو تصنيف.
        if not is_direct_store_url(url):
            print(f"SKIP NON-DIRECT CTA: {o['name']} -> {url}")
            continue
        send_whatsapp_cta(from_number, o["line"], url, bot_id, f"🛒 {o['name'][:18]}")
        sent += 1
    if sent == 0:
        send_whatsapp_text(from_number, T(lang, "not_found"), bot_id)
        return "none"
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

def bilingual_search_instruction(query, lang):
    """يجبر البحث في الفهرسة العربية والإنجليزية مع إبقاء الرد بلغة المستخدم."""
    response_rule = LANG_INSTR[lang]
    return (
        f"ابحث عن المنتج التالي في الكويت باستخدام العربية والإنجليزية معاً: {query}. "
        "حوّل الاسم داخلياً إلى مرادف عربي ومرادف إنجليزي، وجرّب اسم البراند باللاتيني والعربي، "
        "ولا تعتبر عدم ظهور نتيجة بلغة واحدة فشلاً قبل تجربة اللغة الأخرى. "
        "ابدأ بنتائج المتاجر الكويتية المعروفة حتى لو كانت متأخرة في Google، وافحص نتائج أعمق قبل المتاجر الأجنبية. "
        "اعرض فقط نتائج لها سعر رقمي بالدينار الكويتي ورابط صفحة منتج مباشر داخل المتجر. "
        f"{response_rule}"
    )


def split_product_aliases(product_name):
    """ينظف الاسم الثنائي الناتج من تحليل الصورة ويحتفظ بالاسمين للبحث."""
    parts = [p.strip() for p in re.split(r"\s*[|｜]\s*", product_name or "") if p.strip()]
    unique = []
    for part in parts:
        if part not in unique:
            unique.append(part)
    return unique[:2]


def _query_candidates(query):
    """يبني صيغ بحث منفصلة؛ العربية أولاً لأنها غالباً أفضل في فهرسة متاجر الكويت."""
    raw_parts = [p.strip() for p in re.split(r"\s*[|｜]\s*", query or "") if p.strip()]
    ar_parts = [p for p in raw_parts if re.search(r"[\u0600-\u06FF]", p)]
    en_parts = [p for p in raw_parts if re.search(r"[A-Za-z]", p)]
    candidates = ar_parts + en_parts
    if query and query.strip() not in candidates:
        candidates.append(query.strip())
    unique = []
    for item in candidates:
        if item and item not in unique:
            unique.append(item)
    return unique or [query]


def is_no_result_answer(txt):
    """يميز رسائل عدم العثور حتى لا تُرسل للمستخدم قبل استنفاد كل المحاولات."""
    t = normalize_ar(txt or "")
    phrases = (
        "لم يتم العثور", "لم اعثر", "ما لقيت", "تعذر العثور", "لا توجد نتائج",
        "غير موجود ضمن نتائج البحث", "لم اجد", "عذرا",
        "could not find", "couldn't find", "no results", "not found",
        "unable to find", "was not found", "couldn’t find"
    )
    return any(normalize_ar(p) in t for p in phrases)


def is_informational_answer(txt):
    """يسمح فقط بالإجابة المعلوماتية الحقيقية، وليس اعتذار عدم العثور."""
    if not txt or is_no_result_answer(txt):
        return False
    if extract_store_offers(txt) or is_service_answer(txt) or "📦" in txt:
        return False
    # أسئلة معلوماتية غالباً تحتوي شرحاً أطول ولا تحتوي لغة فشل البحث.
    return len(txt.strip()) >= 80


def _lens_source_name(item, index):
    source = (item.get("source") or "").strip()
    if source:
        return source[:40]
    try:
        host = urllib.parse.urlparse(item.get("link") or "").netloc.replace("www.", "")
        return (host.split(".")[0] or f"Lens {index}")[:40]
    except Exception:
        return f"Lens {index}"


KUWAIT_STORE_HINTS = (
    ".com.kw", ".kw", "kuwait", "الكويت", "xcite", "eureka", "best al yousifi",
    "best alyousifi", "jarir", "level shoes", "future store", "blink", "noon kuwait",
    "carrefour kuwait", "lulu kuwait", "jm3eia", "جمعية", "intersport kuwait",
    "decathlon kuwait", "boutiqaat", "boots kuwait", "yiaco", "royal pharmacy",
    "talabat kuwait", "keeta kuwait"
)


def is_kuwait_lens_result(item):
    """Detect Kuwait merchants even when Google Lens ranks them after foreign stores."""
    text = " ".join([
        str(item.get("source") or ""), str(item.get("link") or ""),
        str(item.get("title") or ""), str(item.get("currency") or ""),
        str(item.get("price") or "")
    ]).lower()
    try:
        host = urllib.parse.urlparse(item.get("link") or "").netloc.lower()
    except Exception:
        host = ""
    return host.endswith(".kw") or any(h in text for h in KUWAIT_STORE_HINTS)


def lens_priced_offers(lens_context, lang="ar"):
    """Use Google Lens product cards directly.

    Lens already supplies a visual match, direct product URL, displayed price and stock state.
    We therefore do not force the page through our HTML parser first; that parser can wrongly
    reject JS-heavy stores or replace a visually good alternative with a different SKU.
    """
    if not lens_context:
        return {}
    offers = {}
    used_urls = set()
    for i, item in enumerate(lens_context.get("matches") or [], 1):
        url = (item.get("link") or "").strip()
        title = (item.get("title") or "").strip()
        price_text = (item.get("price") or "").strip()
        price_value = item.get("price_value")
        currency = (item.get("currency") or "").strip()
        in_stock = item.get("in_stock")
        if not title or not is_direct_store_url(url) or url in used_urls:
            continue
        if in_stock is False:
            print(f"LENS PRODUCT OOS SKIP: {title} -> {url}")
            continue
        if not price_text and price_value in (None, ""):
            continue
        # Kuwait localization usually returns KWD. Keep only KWD-like cards so the WhatsApp
        # result remains comparable; foreign-currency Lens cards can still be found by fallback search.
        price_hay = f"{price_text} {currency}".lower()
        if not any(x in price_hay for x in ("kwd", "د.ك", "kd")):
            continue
        name = _lens_source_name(item, i)
        base = name
        n = 2
        while name in offers:
            name = f"{base} {n}"; n += 1
        numeric = None
        try:
            numeric = float(price_value) if price_value not in (None, "") else None
        except Exception:
            numeric = None
        offers[name] = {
            "url": url,
            "price": numeric,
            "price_text": format_lens_price(price_text, price_value, lang),
            "is_kuwait": is_kuwait_lens_result(item),
            "title": title,
            "position": int(item.get("position") or i),
            "exact": bool(item.get("exact")),
            "image_url": item.get("image") or item.get("thumbnail") or "",
        }
        used_urls.add(url)
    # Kuwait merchants come first even if Google placed them fifth/sixth; then exactness and Lens position.
    ranked = sorted(
        offers.items(),
        key=lambda kv: (
            0 if kv[1].get("is_kuwait") else 1,
            0 if kv[1].get("exact") else 1,
            kv[1].get("position", 999),
        ),
    )
    return dict(ranked[:MAX_STORES])


def verify_lens_direct_matches(lens_context):
    """Fallback verifier for Lens URLs that had no price card."""
    if not lens_context:
        return {}
    candidates = {}
    for i, m in enumerate((lens_context.get("matches") or [])[:8], 1):
        url = (m.get("link") or "").strip()
        title = (m.get("title") or "").strip()
        source = (m.get("source") or f"Lens {i}").strip()
        if not title or not is_direct_store_url(url):
            continue
        candidates[source] = url
    verified = verify_offers(candidates, (lens_context.get("chosen") or {}).get("title", ""))
    if verified:
        print(f"LENS HTML VERIFIED: {list(verified)}")
    return verified


def _new_layer_search(query, lang, prompt_text=None, source_image_b64=None, source_image_mime=None, lens_context=None):
    # نتائج الصور تعتمد على الصورة نفسها، لذلك لا نستخدم كاش النص وحده.
    cached = None if source_image_b64 else cache_get(query, lang)
    if cached:
        return cached

    # For image requests, use the product cards returned by Google Lens itself first.
    # This preserves the many visually close results Google shows instead of demanding one exact SKU.
    lens_cards = lens_priced_offers(lens_context, lang)
    if lens_cards:
        display_name = (lens_context.get("chosen") or {}).get("title") or query
        lines = [f"📦 {display_name}", ""]
        new_urls = {}
        for i, (name, info) in enumerate(lens_cards.items()):
            prefix = "✅" if i == 0 else "•"
            shown_price = info.get("price_text") or format_price(info.get("price"))
            lines.append(f"{prefix} {name} — {shown_price}")
            new_urls[name] = info["url"]
        print(f"LENS PRODUCT CARDS USED: {list(new_urls)}")
        return "\n".join(lines), new_urls

    # If Lens returned direct pages without price metadata, try our HTML verifier once.
    lens_verified = verify_lens_direct_matches(lens_context)
    if lens_verified:
        sorted_v = sorted(lens_verified.items(), key=lambda x: x[1]["price"])
        display_name = (lens_context.get("chosen") or {}).get("title") or query
        lines = [f"📦 {display_name}", ""]
        new_urls = {}
        for i, (name, info) in enumerate(sorted_v[:MAX_STORES]):
            prefix = "✅" if i == 0 else "•"
            currency = "KWD" if lang == "en" else "د.ك"
            lines.append(f"{prefix} {name} — {format_price(info['price'])} {currency}")
            new_urls[name] = info["url"]
        return "\n".join(lines), new_urls

    candidates = _query_candidates(query)
    best_txt, best_urls = "", {}

    for attempt in range(1, MAX_SEARCH_ATTEMPTS + 1):
        search_term = candidates[(attempt - 1) % len(candidates)]
        if attempt == 1 and prompt_text:
            context = f"{prompt_text}\n"
        else:
            context = ""

        # المحاولة الأولى تكون حصراً داخل المتاجر ذات الأولوية.
        # إذا لم نجد نتيجة صالحة، تنتقل المحاولات التالية إلى بحث عام في متاجر الكويت المعروفة.
        priority_stores = priority_stores_for(search_term)
        stores_hint = "، ".join(priority_stores)
        if attempt == 1:
            search_scope = (
                f"ابحث حصراً أولاً داخل هذه المتاجر وبنفس ترتيب الأولوية: {stores_hint}. "
                "لا تعرض أي متجر خارج هذه القائمة في هذه المحاولة، وإذا لم تجد فلا تكتب اعتذاراً مطولاً؛ أرجع بلا نتائج لننتقل للبحث العام. "
            )
        else:
            search_scope = (
                f"لم توجد نتيجة صالحة في متاجر الأولوية ({stores_hint}). "
                "اعمل الآن بحثاً عاماً واسعاً في جميع متاجر الكويت التي تبيع المنتج، بما فيها المتاجر المتخصصة، "
                "مع تجنب الإعلانات المبوبة فقط مثل OpenSooq. لا تستبعد المتجر لمجرد أنه ليس ضمن القائمة الأولى. "
            )
        current_prompt = (
            f"{context}ابحث في الكويت عن هذا الاسم تحديداً: {search_term}. "
            + ((f"الاسم المختار من Google Lens هو: {(lens_context.get('chosen') or {}).get('title','')}. "
                "لا توسع البحث إلى موديلات أخرى من نفس البراند، ولا تقبل اختلافاً واضحاً في اللون أو النقشة أو وجود الكعب. ") if lens_context else "")
            + f"{search_scope}"
            "استخدم الاسم كما هو، ويمكن تجربة تهجئات قريبة لنفس المنتج فقط. "
            "أعطني حتى 3 متاجر فقط، وكل نتيجة يجب أن تحتوي سعراً رقمياً بالدينار الكويتي "
            "ورابط صفحة المنتج المباشرة داخل المتجر. ممنوع روابط Google وصفحات البحث والتصنيف. "
            "لا تكتب متوفر أو InStock بدلاً من السعر. "
            f"{LANG_INSTR[lang]}"
        )

        txt, urls = call_gemini([{"text": current_prompt}])
        urls = direct_urls_only(urls)
        offers = extract_store_offers(txt)

        if is_service_answer(txt):
            if len(txt) >= 40:
                cache_put(query, lang, txt, urls)
            return txt, urls
        # لا نرسل اعتذار Gemini مباشرة؛ نكمل باقي المحاولات والبحث العام.
        if is_informational_answer(txt):
            return txt, urls
        if is_no_result_answer(txt) or (txt and not offers):
            print(f"SEARCH ATTEMPT {attempt} NO RESULT: {search_term}")
            continue

        if txt and offers and urls:
            verified = verify_offers(urls, search_term)
            verified = filter_verified_with_lens(verified, lens_context)
            if verified:
                # Google Lens استُخدم قبل البحث لتحديد المنتج. لا نحذف نتائج الأسعار بسبب تقييم بصري تخميني.
                sorted_v = sorted(verified.items(), key=lambda x: x[1]["price"])
                title = product_title(txt, search_term)
                lines = [title, ""]
                new_urls = {}
                for i, (name, info) in enumerate(sorted_v[:MAX_STORES]):
                    prefix = "✅" if i == 0 else "•"
                    currency = "KWD" if lang == "en" else "د.ك"
                    lines.append(f"{prefix} {name} — {format_price(info['price'])} {currency}")
                    new_urls[name] = info["url"]
                final_txt = "\n".join(lines)
                if not source_image_b64:
                    cache_put(query, lang, final_txt, new_urls)
                return final_txt, new_urls

            # For image/Lens searches, never fall back to an unverified page. A direct URL
            # can still be a different SKU, a sold-out page, or a collection page.
            if lens_context:
                print("LENS STRICT: no verified exact product; skipping unverified CTA fallback")
                continue

            # بعض المتاجر تمنع فحص HTML؛ نقبل العرض فقط مع رابط منتج مباشر حقيقي.
            kept = []
            for offer in offers:
                matched = match_url(offer["name"], urls)
                if matched and is_direct_store_url(matched):
                    kept.append(offer)
            if kept:
                title = product_title(txt, search_term)
                lines = [title, ""]
                clean_urls = {}
                for i, offer in enumerate(kept[:MAX_STORES]):
                    prefix = "✅" if i == 0 else "•"
                    body = re.sub(r"^(?:✅|🏆|•)\s*", "", offer["line"]).strip()
                    lines.append(f"{prefix} {body}")
                    clean_urls[offer["name"]] = match_url(offer["name"], urls)
                final_txt = "\n".join(lines)
                if not source_image_b64:
                    cache_put(query, lang, final_txt, clean_urls)
                return final_txt, clean_urls

        best_txt, best_urls = txt or best_txt, urls or best_urls
        print(f"SEARCH ATTEMPT {attempt} FAILED term={search_term}")

    return "", {}


def _extract_numeric_price(line):
    """Extract a KWD price whether currency appears before or after the number."""
    text = str(line or "").replace(",", "")
    patterns = (
        r"(?:KWD|د\.ك|KD)\s*([0-9]+(?:\.[0-9]{1,3})?)",
        r"([0-9]+(?:\.[0-9]{1,3})?)\s*(?:KWD|د\.ك|KD)",
        r"—\s*([0-9]+(?:\.[0-9]{1,3})?)",
    )
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                pass
    return None


def _result_offers(txt, urls, layer, lens_context=None):
    """Convert a formatted bot result into comparable offer records."""
    out = []
    if not txt:
        return out
    title = product_title(txt, "").replace("📦", "").strip()
    for offer in extract_store_offers(txt):
        url = match_url(offer.get("name", ""), urls or {})
        if not is_direct_store_url(url):
            continue
        price = _extract_numeric_price(offer.get("line", ""))
        if price is None or price <= 0:
            continue
        host = urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
        item = {
            "name": offer.get("name", "").strip(),
            "url": url,
            "price": price,
            "title": title,
            "line": offer.get("line", ""),
            "layer": layer,
            "host": host,
            "is_kuwait": host.endswith(".kw") or host.endswith(".com.kw") or any(h in (host + " " + offer.get("name", "").lower()) for h in KUWAIT_STORE_HINTS),
            "exact": False,
            "lens_position": 999,
        }
        if lens_context:
            for m in lens_context.get("matches") or []:
                if (m.get("link") or "").strip() == url:
                    item["exact"] = bool(m.get("exact"))
                    item["lens_position"] = int(m.get("position") or 999)
                    break
        out.append(item)
    return out


def _old_layer_search(query, lang, prompt_text=None, lens_context=None):
    """Second layer: the broad multi-query search logic from the older bot."""
    if not OLD_LAYER_ENABLED:
        return "", {}
    base_prompt = prompt_text or (
        f"ابحث عن {query} في الكويت. متوفر فقط وبسعر رقمي واضح ورابط صفحة منتج مباشر. {LANG_INSTR[lang]}"
    )
    variants = [
        base_prompt,
        f"{query} افضل سعر في الكويت Xcite Eureka Blink Noon Jarir Lulu Carrefour Best Al Yousifi جمعية دوت كوم - قارن الاسعار {LANG_INSTR[lang]}",
        f"{query} شراء اونلاين الكويت سعر متوفر متجر كويتي صفحة المنتج مباشرة {LANG_INSTR[lang]}",
    ]
    futures = []
    for variant in variants:
        for _ in range(OLD_LAYER_DUPLICATES):
            futures.append(OLD_SEARCH_POOL.submit(call_gemini, [{"text": variant}]))
    results = []
    for future in futures:
        try:
            txt, urls = future.result(timeout=90)
            urls = direct_urls_only(urls)
            if txt and urls and extract_store_offers(txt):
                results.append((txt, urls))
        except Exception as exc:
            print(f"OLD LAYER FUTURE ERR: {exc}")
    if not results:
        print("OLD LAYER: no usable result")
        return "", {}

    merged_urls = {}
    best_txt = max(results, key=lambda r: (len(extract_store_offers(r[0])), len(r[1])))[0]
    for _, urls in results:
        for name, url in urls.items():
            if name not in merged_urls and url not in merged_urls.values():
                merged_urls[name] = url

    verified = verify_offers(merged_urls, query)
    if lens_context:
        verified = filter_verified_with_lens(verified, lens_context)
    if not verified:
        print("OLD LAYER: no verified direct offers")
        return "", {}

    sorted_v = sorted(verified.items(), key=lambda x: x[1]["price"])
    title = product_title(best_txt, query)
    currency = "KWD" if lang == "en" else "د.ك"
    lines = [title, ""]
    new_urls = {}
    for i, (name, info) in enumerate(sorted_v[:max(MAX_STORES * 2, 6)]):
        prefix = "✅" if i == 0 else "•"
        lines.append(f"{prefix} {name} — {format_price(info['price'])} {currency}")
        new_urls[name] = info["url"]
    print(f"OLD LAYER VERIFIED: {list(new_urls)}")
    return "\n".join(lines), new_urls


def _store_priority_value(name, url):
    text = f"{name} {url}".lower()
    priorities = (
        "jm3eia", "جمعية", "xcite", "eureka", "best", "yousifi", "blink",
        "jarir", "lulu", "carrefour", "noon", "intersport", "decathlon",
        "boutiqaat", "boots", "yiaco", "levelshoes", "future", "talabat", "keeta"
    )
    for i, token in enumerate(priorities):
        if token in text:
            return len(priorities) - i
    return 0


def _merge_two_layers(query, lang, new_result, old_result, lens_context=None):
    new_txt, new_urls = new_result
    old_txt, old_urls = old_result
    new_offers = _result_offers(new_txt, new_urls, "new", lens_context)
    old_offers = _result_offers(old_txt, old_urls, "old", lens_context)
    all_offers = new_offers + old_offers
    if not all_offers:
        return new_result if new_txt else old_result

    # Deduplicate exact URLs first, then same store+price. Prefer Lens/new-layer metadata.
    dedup = {}
    for offer in all_offers:
        key = offer["url"].split("?")[0].rstrip("/").lower()
        previous = dedup.get(key)
        if previous is None:
            dedup[key] = offer
        elif offer["layer"] == "new" and previous["layer"] != "new":
            dedup[key] = offer

    offers = list(dedup.values())
    def rank(o):
        quality = 0
        quality += 100 if o.get("exact") else 0
        quality += 40 if o.get("is_kuwait") else 0
        quality += _store_priority_value(o.get("name", ""), o.get("url", "")) * 2
        quality += 12 if o.get("layer") == "new" else 8
        quality += max(0, 20 - min(int(o.get("lens_position", 999)), 20))
        return (-quality, o.get("price", 10**9))
    offers.sort(key=rank)
    chosen = offers[:MAX_STORES]

    display_title = ((lens_context or {}).get("chosen") or {}).get("title") or \
                    product_title(new_txt, "").replace("📦", "").strip() or \
                    product_title(old_txt, query).replace("📦", "").strip() or query
    currency = "KWD" if lang == "en" else "د.ك"
    lines = [f"📦 {display_title}", ""]
    urls = {}
    for i, offer in enumerate(chosen):
        prefix = "✅" if i == 0 else "•"
        lines.append(f"{prefix} {offer['name']} — {format_price(offer['price'])} {currency}")
        urls[offer["name"]] = offer["url"]
    print("TWO LAYER FINAL:", [(o["layer"], o["name"], o["price"]) for o in chosen])
    return "\n".join(lines), urls


def search_product(query, lang, prompt_text=None, source_image_b64=None, source_image_mime=None, lens_context=None):
    """Two-layer search: new Lens/priority method first, old broad method second, then rank both."""
    cached = None if source_image_b64 or lens_context else cache_get(query, lang)
    if cached:
        return cached

    new_result = _new_layer_search(
        query, lang, prompt_text=prompt_text,
        source_image_b64=source_image_b64, source_image_mime=source_image_mime,
        lens_context=lens_context,
    )
    print(f"NEW LAYER DONE offers={len(extract_store_offers(new_result[0])) if new_result[0] else 0}")

    # Services and genuine informational answers should not be forced through product comparison.
    if new_result[0] and (is_service_answer(new_result[0]) or is_informational_answer(new_result[0])):
        return new_result

    old_result = _old_layer_search(query, lang, prompt_text=prompt_text, lens_context=lens_context)
    print(f"OLD LAYER DONE offers={len(extract_store_offers(old_result[0])) if old_result[0] else 0}")
    final_txt, final_urls = _merge_two_layers(query, lang, new_result, old_result, lens_context)
    if final_txt and not source_image_b64 and not lens_context:
        cache_put(query, lang, final_txt, final_urls)
    return final_txt, final_urls

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

@app.get("/lens-image/{token}")
async def lens_image(token: str):
    _cleanup_lens_images()
    with LENS_IMAGE_LOCK:
        item = LENS_IMAGE_STORE.get(token)
    if not item:
        return Response("not found", status_code=404)
    return Response(content=item["content"], media_type=item.get("mime", "image/jpeg"), headers={"Cache-Control": "no-store"})

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

def identify_product_with_retry(b64, mime, lang="ar"):
    """يحدد الاسم بالعربي والإنجليزي دائماً، بغض النظر عن لغة واجهة المستخدم."""
    prompts = [
        "حدد المنتج من الشعار والشكل والنص. اكتب الاسم العربي ثم الإنجليزي مفصولين بـ |.",
        "افحص الصورة بدقة أكبر، خصوصاً الشعار والأزرار ورقم الموديل. اكتب Arabic name | English name.",
        "استنتج أقرب اسم تجاري قابل للبحث في الكويت حتى لو الصورة جزئية. Arabic | English only.",
    ]
    bad_phrases = (
        "ما قدرت", "لا استطيع", "لا أستطيع", "غير واضح", "لا يمكن تحديد",
        "couldn't identify", "cannot identify", "can't identify", "unable to identify",
        "unknown product", "not sure"
    )
    for attempt in range(MAX_IDENTIFY_ATTEMPTS):
        ident, _ = call_gemini(
            [{"inline_data": {"mime_type": mime, "data": b64}}, {"text": prompts[min(attempt, len(prompts)-1)]}],
            system=IDENTIFY_SYSTEM,
            use_search=False,
        )
        candidate = ident.strip().splitlines()[0].strip() if ident else ""
        if candidate and not any(p in candidate.lower() for p in bad_phrases):
            if "|" not in candidate:
                # لا نرفض الاسم الأحادي؛ البحث سيبدأ به ثم يحاول الصياغة الأخرى في المحاولات التالية.
                candidate = candidate.strip()
            print(f"IMAGE IDENTIFIED attempt={attempt + 1}: {candidate}")
            return candidate
        print(f"IMAGE IDENTIFY ATTEMPT {attempt + 1} FAILED")
    return ""


def process_single_image(message,bot_id,lang="ar"):
    from_number=message["from"]
    caption=(message.get("image",{}) or {}).get("caption","").strip()
    send_whatsapp_text(from_number,T(lang,"identifying"),bot_id)
    b64,mime=download_whatsapp_media(message["image"]["id"])

    # 1) Google Lens يحدد المنتج بصرياً.
    lens = google_lens_lookup(b64, mime, lang, caption)
    lens_name = lens.get("query", "")

    # 2) إذا Lens لم يرجع شيئاً، نرجع للتعرف السابق كخطة احتياطية.
    fallback_name = ""
    if not lens_name:
        fallback_name = identify_product_with_retry(b64, mime, lang)

    aliases = lens.get("aliases") or split_product_aliases(fallback_name)
    chosen_title = ((lens.get("chosen") or {}).get("title") or "").strip()
    # اسم Lens المختار أولاً؛ الأسماء الأخرى مرادفات احتياطية فقط.
    combined_name = chosen_title or (" | ".join(aliases) if aliases else fallback_name)

    if combined_name and caption:
        request_query = f"{caption} — {combined_name}"
        prompt_text = (
            f"Google Lens/تحليل الصورة حدد المنتج بهذه الأسماء: {combined_name}\n"
            f"طلب المستخدم عنه: {caption}\n"
            "ابحث عن نفس المنتج المحدد، ثم طبّق قواعد المتاجر والأسعار والروابط المباشرة. "
            f"{LANG_INSTR[lang]}"
        )
        txt,urls=search_product(request_query, lang, prompt_text=prompt_text, lens_context=lens)
        query = request_query
    elif combined_name:
        txt,urls=search_product(combined_name, lang, lens_context=lens)
        query = combined_name
    else:
        txt, urls = "", {}
        query = caption

    if query:
        LAST_SEARCH[from_number] = {"product": query}
    if not txt:
        send_whatsapp_text(from_number,T(lang,"cant_identify"),bot_id)
        return
    result_type = send_product_result(from_number, txt, urls, bot_id, lang, query)
    if query and (result_type == "service" or (result_type == "product" and AUTO_SEND_PRODUCT_MAPS)):
        send_maps_button(from_number, query, bot_id, lang)

def identify_image_product(msg):
    try:
        b64,mime=download_whatsapp_media(msg["image"]["id"])
        return identify_product_with_retry(b64, mime, "ar")
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
async def health(): return {"status":"v53 TWO-LAYER SEARCH + RESULT RANKING", "build":BUILD_ID}
