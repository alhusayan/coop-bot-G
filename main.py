# -*- coding: utf-8 -*-
import os, re, time, base64, requests, json, asyncio, urllib.parse, hashlib, sqlite3, threading
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Request, Response, BackgroundTasks
from bs4 import BeautifulSoup

app = FastAPI()
BUILD_ID = "v67-exact-visual-identity-20260803"
print("=" * 70)
print(f"STARTING COOP BOT BUILD: {BUILD_ID}")
print("EXACT VISUAL IDENTITY + STRICT LENS/OCR FUSION + GLOBAL FX")
print("=" * 70)


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
# تقدر تغيّر نموذج البحث ونموذج التعرف على الصور كل واحد بروحه من Environment Variables.
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
# اللغة والموقع يُطلبان في أول استخدام. الموقع يُجدَّد كل 3 أيام.
USER_MARKET = {}
USER_LOCATION_TS = {}
PENDING_ONBOARDING = {}
PENDING_GLOBAL_SEARCH = {}
GLOBAL_PENDING_TTL = max(300, int(os.environ.get("GLOBAL_PENDING_TTL_SECONDS", "900")))
LOCATION_TTL_SECONDS = max(3600, int(os.environ.get("LOCATION_TTL_HOURS", "72")) * 3600)
MARKET_CTX = threading.local()
DEFAULT_COUNTRY = os.environ.get("DEFAULT_COUNTRY", "kw").strip().lower() or "kw"
PENDING_IMAGES = defaultdict(lambda: {"images": [], "bot_id": ""})

BUFFER_SECONDS = 4
RESOLVER = ThreadPoolExecutor(max_workers=8)
WORKERS = ThreadPoolExecutor(max_workers=5)
OLD_SEARCH_POOL = ThreadPoolExecutor(max_workers=8)
LENS_POOL = ThreadPoolExecutor(max_workers=4)
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
if not PUBLIC_BASE_URL:
    # على Railway الرابط العام موجود تلقائياً؛ بدونه اللينز ينطفي بصمت.
    _railway_domain = (
        os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
        or os.environ.get("RAILWAY_STATIC_URL", "")
    ).strip()
    if _railway_domain:
        _railway_domain = _railway_domain.replace("https://", "").replace("http://", "").rstrip("/")
        PUBLIC_BASE_URL = f"https://{_railway_domain}"
        print(f"PUBLIC_BASE_URL auto-derived from Railway: {PUBLIC_BASE_URL}")
ENABLE_GOOGLE_LENS = env_bool("ENABLE_GOOGLE_LENS", True)
LENS_PRIMARY_MODE = env_bool("LENS_PRIMARY_MODE", True)
LENS_PRIMARY_EXCEPT_TEXT_HEAVY = env_bool("LENS_PRIMARY_EXCEPT_TEXT_HEAVY", True)
# قوة Lens الحقيقية تأتي من تعدد التمريرات: products ثم all (visual+exact) ثم بحث واسع بلا قيد دولة.
ENABLE_LENS_WIDE_FALLBACK = env_bool("ENABLE_LENS_WIDE_FALLBACK", True)
LENS_MIN_MATCHES = max(3, int(os.environ.get("LENS_MIN_MATCHES", "6")))
# تشغيل Vision و Lens بالتوازي: أسرع وأدق دمج. عطّله إذا تبي توفر كريدت SerpApi للعبوات النصية.
LENS_PARALLEL_WITH_VISION = env_bool("LENS_PARALLEL_WITH_VISION", True)
LENS_RESULT_LIMIT = max(12, int(os.environ.get("LENS_RESULT_LIMIT", "40")))
LENS_IMAGE_TTL = max(120, int(os.environ.get("LENS_IMAGE_TTL_SECONDS", "600")))
LENS_IMAGE_STORE = {}
LENS_IMAGE_LOCK = threading.Lock()


# ---- Global market detection -------------------------------------------------
# Longest-prefix matching. This covers all international calling-code zones; ambiguous
# +1 and +7 default to the most common market unless the user shares location.
CALLING_CODE_TO_COUNTRY = {
    "965":"kw","966":"sa","971":"ae","973":"bh","974":"qa","968":"om","964":"iq","962":"jo","961":"lb","963":"sy","967":"ye","970":"ps",
    "20":"eg","212":"ma","213":"dz","216":"tn","218":"ly","249":"sd","252":"so","253":"dj","269":"km","222":"mr",
    "90":"tr","98":"ir","92":"pk","91":"in","880":"bd","94":"lk","977":"np","93":"af","960":"mv","975":"bt",
    "86":"cn","852":"hk","853":"mo","886":"tw","81":"jp","82":"kr","850":"kp","65":"sg","60":"my","62":"id","63":"ph","66":"th","84":"vn","855":"kh","856":"la","95":"mm","673":"bn","670":"tl","976":"mn",
    "44":"gb","353":"ie","33":"fr","49":"de","39":"it","34":"es","351":"pt","31":"nl","32":"be","352":"lu","41":"ch","43":"at","45":"dk","46":"se","47":"no","358":"fi","354":"is","30":"gr","357":"cy","356":"mt",
    "48":"pl","420":"cz","421":"sk","36":"hu","40":"ro","359":"bg","385":"hr","386":"si","381":"rs","382":"me","387":"ba","389":"mk","355":"al","383":"xk","373":"md","380":"ua","375":"by","370":"lt","371":"lv","372":"ee","7":"ru",
    "1":"us","52":"mx","55":"br","54":"ar","56":"cl","57":"co","58":"ve","51":"pe","593":"ec","591":"bo","595":"py","598":"uy","592":"gy","597":"sr","500":"fk",
    "61":"au","64":"nz","675":"pg","679":"fj","677":"sb","678":"vu","685":"ws","676":"to","686":"ki","688":"tv","691":"fm","692":"mh","680":"pw","674":"nr",
    "27":"za","234":"ng","233":"gh","254":"ke","255":"tz","256":"ug","250":"rw","257":"bi","251":"et","291":"er","260":"zm","263":"zw","267":"bw","264":"na","258":"mz","261":"mg","230":"mu","248":"sc","266":"ls","268":"sz","265":"mw","244":"ao","243":"cd","242":"cg","241":"ga","237":"cm","225":"ci","221":"sn","223":"ml","226":"bf","227":"ne","228":"tg","229":"bj","231":"lr","232":"sl","224":"gn","245":"gw","240":"gq","235":"td","236":"cf","239":"st","238":"cv",
    "972":"il","994":"az","995":"ge","374":"am","992":"tj","993":"tm","996":"kg","998":"uz"
}
COUNTRY_NAMES = {
    "kw":"Kuwait","sa":"Saudi Arabia","ae":"United Arab Emirates","bh":"Bahrain","qa":"Qatar","om":"Oman","iq":"Iraq","jo":"Jordan","lb":"Lebanon","eg":"Egypt","tr":"Turkey",
    "us":"United States","ca":"Canada","gb":"United Kingdom","fr":"France","de":"Germany","it":"Italy","es":"Spain","pt":"Portugal","nl":"Netherlands","be":"Belgium","ch":"Switzerland","at":"Austria",
    "in":"India","cn":"China","jp":"Japan","kr":"South Korea","sg":"Singapore","my":"Malaysia","id":"Indonesia","ph":"Philippines","th":"Thailand","vn":"Vietnam","pk":"Pakistan","bd":"Bangladesh",
    "au":"Australia","nz":"New Zealand","za":"South Africa","ng":"Nigeria","ke":"Kenya","ma":"Morocco","dz":"Algeria","tn":"Tunisia","ru":"Russia","ua":"Ukraine","br":"Brazil","mx":"Mexico","ar":"Argentina"
}
COUNTRY_CURRENCIES = {
    "kw":"KWD","sa":"SAR","ae":"AED","bh":"BHD","qa":"QAR","om":"OMR","iq":"IQD","jo":"JOD","lb":"LBP","eg":"EGP","tr":"TRY",
    "us":"USD","ca":"CAD","gb":"GBP","fr":"EUR","de":"EUR","it":"EUR","es":"EUR","pt":"EUR","nl":"EUR","be":"EUR","ch":"CHF","at":"EUR",
    "in":"INR","cn":"CNY","jp":"JPY","kr":"KRW","sg":"SGD","my":"MYR","id":"IDR","ph":"PHP","th":"THB","vn":"VND","pk":"PKR","bd":"BDT",
    "au":"AUD","nz":"NZD","za":"ZAR","ng":"NGN","ke":"KES","ma":"MAD","dz":"DZD","tn":"TND","ru":"RUB","ua":"UAH","br":"BRL","mx":"MXN","ar":"ARS"
}
COUNTRY_TLDS = {"kw":[".kw"],"sa":[".sa"],"ae":[".ae"],"bh":[".bh"],"qa":[".qa"],"om":[".om"],"tr":[".tr"],"gb":[".uk"],"us":[".us"],"ca":[".ca"],"in":[".in"],"cn":[".cn"],"jp":[".jp"],"au":[".au"],"nz":[".nz"],"de":[".de"],"fr":[".fr"],"it":[".it"],"es":[".es"]}

# العملات ذات الألف فلس: تُعرض دائماً بثلاث خانات عشرية (1.950 وليس 1.95).
THREE_DECIMAL_CURRENCIES = {"KWD", "BHD", "OMR", "JOD", "TND", "LYD"}

# ---- FX: تحويل الأسعار العالمية إلى عملة المستخدم المحلية -------------------
# نستخدم open.er-api.com (مجاني بدون مفتاح، تحديث يومي، يشمل KWD وكل عملات الخليج).
FX_CACHE = {}
FX_CACHE_LOCK = threading.Lock()
FX_CACHE_TTL = max(3600, int(os.environ.get("FX_CACHE_TTL_HOURS", "12")) * 3600)
FX_API_URL = os.environ.get("FX_API_URL", "https://open.er-api.com/v6/latest/{base}")

CURRENCY_SYMBOL_MAP = {
    "$": "USD", "us$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY", "₹": "INR",
    "₩": "KRW", "₺": "TRY", "₽": "RUB", "r$": "BRL", "a$": "AUD", "c$": "CAD",
    "د.إ": "AED", "ر.س": "SAR", "ر.ق": "QAR", "ر.ع": "OMR", "د.ب": "BHD",
    "د.ك": "KWD", "ج.م": "EGP", "د.أ": "JOD",
}
KNOWN_CURRENCY_CODES = set(COUNTRY_CURRENCIES.values()) | {
    "USD","EUR","GBP","JPY","CNY","INR","AED","SAR","QAR","OMR","BHD","KWD",
    "TRY","EGP","JOD","AUD","CAD","CHF","SEK","NOK","DKK","PLN","RUB","BRL",
    "MXN","ZAR","KRW","SGD","MYR","THB","IDR","PHP","VND","PKR","HKD","NZD","TWD"
}

def get_fx_rates(base):
    """أسعار الصرف من عملة الأساس. كاش 12 ساعة حتى لا نستهلك الشبكة مع كل بحث."""
    base = (base or "").upper().strip()
    if not base:
        return {}
    now = time.time()
    with FX_CACHE_LOCK:
        hit = FX_CACHE.get(base)
        if hit and now - hit["ts"] < FX_CACHE_TTL:
            return hit["rates"]
    try:
        r = requests.get(FX_API_URL.format(base=base), timeout=10)
        if r.ok:
            j = r.json()
            rates = j.get("rates") or j.get("conversion_rates") or {}
            if rates:
                with FX_CACHE_LOCK:
                    FX_CACHE[base] = {"rates": rates, "ts": now}
                print(f"FX RATES LOADED base={base} count={len(rates)}")
                return rates
        print(f"FX HTTP {r.status_code} base={base}")
    except Exception as e:
        print(f"FX FETCH ERR base={base}: {e}")
    with FX_CACHE_LOCK:
        hit = FX_CACHE.get(base)
        return hit["rates"] if hit else {}

def convert_to_local(value, from_currency):
    """يحوّل قيمة بعملة أجنبية إلى عملة سوق المستخدم الحالي. يعيد None عند التعذر."""
    try:
        val = float(value)
    except Exception:
        return None
    src = (from_currency or "").upper().strip()
    dst = (current_market().get("currency") or "").upper().strip()
    if not src or not dst:
        return None
    if src == dst:
        return val
    rates = get_fx_rates(src)
    rate = rates.get(dst)
    if not rate:
        return None
    return val * float(rate)

def detect_currency_code(text, fallback=""):
    """يستخرج رمز العملة من نص السعر: KWD أو $ أو ر.س ... إلخ."""
    hay = str(text or "").strip()
    if not hay:
        return (fallback or "").upper()
    m = re.search(r"\b([A-Z]{3})\b", hay.upper())
    if m and m.group(1) in KNOWN_CURRENCY_CODES:
        return m.group(1)
    low = hay.lower()
    # الرموز المركبة أولاً (us$ قبل $).
    for sym in sorted(CURRENCY_SYMBOL_MAP, key=len, reverse=True):
        if sym in low or sym in hay:
            return CURRENCY_SYMBOL_MAP[sym]
    return (fallback or "").upper()

def display_global_price(price_value, price_text, currency_code, lang="ar"):
    """السعر العالمي يُعرض دائماً بعملة المستخدم المحلية بالفلوس الكاملة: 1.950 د.ك (6.35 USD).

    إذا تعذر التحويل (عملة مجهولة أو فشل مصدر الصرف) نعرض السعر الأصلي كما ورد بدل إخفاء العرض.
    """
    src = detect_currency_code(f"{currency_code or ''} {price_text or ''}", currency_code)
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
        return str(price_text or "").strip(), None
    converted = convert_to_local(numeric, src) if src else None
    local_code = (current_market().get("currency") or "").upper()
    if converted is not None:
        label = currency_label(lang)
        original = f" ({format_price(numeric, src)} {src})" if src and src != local_code else ""
        return f"{format_price(converted, local_code)} {label}{original}", converted
    # فشل التحويل: أظهر الأصلي بوضوح ولا تلصق عليه عملة محلية خاطئة.
    shown = str(price_text or "").strip() or f"{format_price(numeric, src)} {src}".strip()
    return shown, None

def infer_country_from_phone(phone):
    digits = re.sub(r"\D", "", phone or "")
    for prefix in sorted(CALLING_CODE_TO_COUNTRY, key=len, reverse=True):
        if digits.startswith(prefix):
            return CALLING_CODE_TO_COUNTRY[prefix]
    return DEFAULT_COUNTRY

def market_for_user(from_number):
    market = dict(USER_MARKET.get(from_number) or {})
    cc = (market.get("country") or DEFAULT_COUNTRY).lower()
    market["country"] = cc
    market.setdefault("country_name", COUNTRY_NAMES.get(cc, cc.upper()))
    market.setdefault("currency", COUNTRY_CURRENCIES.get(cc, ""))
    return market

def activate_market(from_number):
    market = market_for_user(from_number)
    MARKET_CTX.value = market
    USER_MARKET[from_number] = market
    return market

def current_market():
    return getattr(MARKET_CTX, "value", None) or {"country":DEFAULT_COUNTRY,"country_name":COUNTRY_NAMES.get(DEFAULT_COUNTRY,"Kuwait"),"currency":COUNTRY_CURRENCIES.get(DEFAULT_COUNTRY,"KWD")}

def _run_with_market(market, fn, *args, **kwargs):
    """MARKET_CTX هو threading.local؛ أي عمل داخل ThreadPool يفقد سوق المستخدم بدون هذا الغلاف.

    بدونه: مستخدم سعودي يرسل سلة منتجات أو يمر على الطبقة القديمة -> البحث يرجع للكويت الافتراضية.
    """
    MARKET_CTX.value = market
    return fn(*args, **kwargs)

def currency_label(lang="ar"):
    code = current_market().get("currency") or ""
    if lang == "en" or code != "KWD":
        return code or ""
    return "د.ك"

def market_instruction():
    m = current_market()
    city = m.get("city") or ""
    place = f"{city}, {m['country_name']}" if city else m["country_name"]
    currency = m.get("currency") or "local currency"
    return (f"\nIMPORTANT CURRENT USER MARKET: {place} (country code {m['country']}). "
            f"Return stores that sell/deliver in {place}, and prices in {currency}. "
            "Reject India, China, or any other foreign-country result unless it explicitly delivers to the current market and no local result exists. "
            "Ignore any older Kuwait-specific instruction when the current market is not Kuwait.\n")

def reverse_geocode_market(lat, lng):
    # No API key required. Failure is harmless: coordinates still localise Google Maps.
    try:
        r = requests.get("https://api.bigdatacloud.net/data/reverse-geocode-client", params={"latitude":lat,"longitude":lng,"localityLanguage":"en"}, timeout=8)
        if r.ok:
            j = r.json()
            cc = str(j.get("countryCode") or "").lower()
            if cc:
                return {"country":cc,"country_name":j.get("countryName") or COUNTRY_NAMES.get(cc,cc.upper()),"city":j.get("city") or j.get("locality") or "","currency":COUNTRY_CURRENCIES.get(cc,"")}
    except Exception as e:
        print(f"REVERSE GEOCODE ERR: {e}")
    return {}

GROCERY_WORDS = [
    "بيبسي","شيبس","حليب","قهوه","قهوة","شاي","سكر","رز","زيت","صابون","شامبو",
    "برينجلز","كيتكات","نسكافيه","تونه","ماء","عصير","بسكوت","منظف","معجون","حفاض"
]

print(
    f"ECONOMIC CONFIG search_model={GEMINI_SEARCH_MODEL} fast_model={GEMINI_FAST_MODEL} "
    f"max_stores={MAX_STORES} search_attempts={MAX_SEARCH_ATTEMPTS} "
    f"identify_attempts={MAX_IDENTIFY_ATTEMPTS} auto_maps={AUTO_SEND_PRODUCT_MAPS} "
    f"lens_wide_fallback={ENABLE_LENS_WIDE_FALLBACK} lens_parallel={LENS_PARALLEL_WITH_VISION} "
    f"public_base_url={'SET' if PUBLIC_BASE_URL else 'MISSING'}"
)

VERIFIED_PAGE_CACHE = {}
VERIFIED_PAGE_CACHE_MAX = int(os.environ.get("VERIFIED_PAGE_CACHE_MAX", "600"))
OOS_PHRASES = ["out of stock","غير متوفر","نفدت الكمية","غير متاح","sold out","غير متوفر حاليا","نفذت","not available","temporarily unavailable"]
LISTING_URL_PARTS = ["/search","/s?","/category","/categories","/collection","/collections","/shop/category","?q=","/search_results","/shop/","/listing","/c/"]

def format_price(p, currency=None):
    """عرض السعر بالفلوس دائماً: 1.950 وليس 1.95، و0.750 وليس 0.75.

    للعملات ذات الألف فلس (KWD/BHD/OMR/JOD/TND) ثلاث خانات عشرية كاملة دون حذف الأصفار.
    لباقي العملات خانتان عشريتان ثابتتان.
    """
    try:
        pf = float(p)
    except Exception:
        return str(p)
    code = (currency or current_market().get("currency") or "KWD").upper().strip()
    if code in THREE_DECIMAL_CURRENCIES:
        return f"{pf:.3f}"
    return f"{pf:.2f}"


def format_lens_price(price_text, price_value, lang="ar", currency_code=None):
    """Normalise Lens prices with full fils digits: 1.95 KWD -> 1.950 د.ك."""
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
    label = currency_label(lang)
    return f"{format_price(numeric, currency_code)} {label}"

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

def is_lens_product_url(url, item=None):
    """Trust a Google Lens shopping/visual card more than our generic URL heuristics.

    Some stores (notably luxury/fashion sites) use SEO product URLs without /product/.
    A Lens result with a source, product title and price is accepted unless it is clearly
    a search/category/brand page or a Google redirect.
    """
    if not url or not url.startswith(("http://", "https://")):
        return False
    try:
        p = urllib.parse.urlparse(url)
        host = p.netloc.lower().replace("www.", "")
        path_q = (p.path + ("?" + p.query if p.query else "")).lower()
    except Exception:
        return False
    if any(host == h or host.endswith("." + h) for h in (
        "google.com", "google.com.kw", "googleusercontent.com", "gstatic.com", "bing.com", "yahoo.com"
    )):
        return False
    if not p.path or p.path == "/":
        return False
    hard_listing = ("/search", "?q=", "/category/", "/categories/", "/collections/", "/listing")
    if any(x in path_q for x in hard_listing):
        return False
    collection_patterns = (
        r"/designers/[^/]+/shoes/?$", r"/designers/[^/]+/[^/]+/?$",
        r"/brand/[^/]+/?$", r"/brands/[^/]+/?$", r"/mules/?$",
        r"/shoes/?$", r"/women/?$", r"/men/?$", r"/pyjamas/?$", r"/pajamas/?$"
    )
    if any(re.search(x, p.path.lower()) for x in collection_patterns):
        return False
    # Lens product/visual card evidence: source + title, and preferably price.
    if item:
        if not (str(item.get("title") or "").strip() and str(item.get("source") or "").strip()):
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
    market = current_market().get("country", DEFAULT_COUNTRY)
    return hashlib.sha256(f"v64|{market}|{norm}|{lang}".encode()).hexdigest()

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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    phone TEXT PRIMARY KEY,
                    lang TEXT,
                    market_json TEXT NOT NULL DEFAULT '{}',
                    location_ts REAL NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL
                )
            """)
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

def load_user_preferences(phone):
    if phone in USER_LANG or phone in USER_MARKET or phone in USER_LOCATION_TS:
        return
    try:
        with CACHE_DB_LOCK, _cache_db_connect() as conn:
            row = conn.execute(
                "SELECT lang, market_json, location_ts FROM user_preferences WHERE phone=?",
                (phone,),
            ).fetchone()
        if not row:
            return
        lang, market_json, location_ts = row
        if lang:
            USER_LANG[phone] = lang
        try:
            market = json.loads(market_json or "{}")
            if market:
                USER_MARKET[phone] = market
        except Exception:
            pass
        USER_LOCATION_TS[phone] = float(location_ts or 0)
    except Exception as e:
        print(f"USER PREF GET ERR: {e}")

def save_user_preferences(phone):
    try:
        with CACHE_DB_LOCK, _cache_db_connect() as conn:
            conn.execute(
                """
                INSERT INTO user_preferences(phone, lang, market_json, location_ts, updated_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(phone) DO UPDATE SET
                    lang=excluded.lang,
                    market_json=excluded.market_json,
                    location_ts=excluded.location_ts,
                    updated_at=excluded.updated_at
                """,
                (phone, USER_LANG.get(phone), json.dumps(USER_MARKET.get(phone) or {}, ensure_ascii=False),
                 float(USER_LOCATION_TS.get(phone, 0)), time.time()),
            )
    except Exception as e:
        print(f"USER PREF PUT ERR: {e}")

def location_is_valid(phone):
    load_user_preferences(phone)
    market = USER_MARKET.get(phone) or {}
    ts = float(USER_LOCATION_TS.get(phone, 0) or 0)
    return bool(market.get("country") and market.get("lat") is not None and market.get("lng") is not None and (time.time() - ts) < LOCATION_TTL_SECONDS)

def cache_pending_message(phone, message, bot_id):
    PENDING_ONBOARDING[phone] = {"message": message, "bot_id": bot_id, "ts": time.time()}

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

IDENTIFY_SYSTEM = """أنت خبير قراءة هوية المنتجات من الصور.
الصورة هي المرجع الوحيد. اقرأ النص المطبوع حرفياً قبل أي استنتاج.
أرجع سطراً واحداً فقط بهذا الشكل:
[اسم عربي دقيق] | [exact searchable English product name]
قواعد صارمة:
- اذكر البراند كما هو مطبوع، واسم المنتج، ورقم الموديل/SKU، والوزن أو السعة إذا كانت ظاهرة.
- ممنوع اختراع أو استبدال البراند أو الموديل بمنتج مشابه أو مكافئ.
- لا تضف Orac أو DecoFiller أو FL300 أو أي اسم آخر إلا إذا كان مكتوباً فعلاً في الصورة.
- إذا كان النص بلغة ثالثة، احتفظ بالبراند كما هو وترجم نوع المنتج فقط.
- إذا لم يظهر موديل فلا تخترع موديل. وإذا لم يظهر براند فاكتب نوع المنتج المحافظ فقط.
مثال: ديكو كرافت معجون فواصل 300 غ | Deco Craft joint compound 300g
سطر واحد فقط، بدون شرح."""

MSG = {
    "ar": {
        "identifying": "ثواني بس.. أحدد المنتج وأدور لك الأفضل!",
        "searching": "🔍 أدور لك على {q}...",
        "not_found": "ما لقيت المنتج متوفر حالياً بسعر مؤكد 😅 جرب صياغة ثانية أو دز صورة أوضح.",
        "identified_not_found": "حددت المنتج ({p}) بس ما لقيت له سعر مؤكد حالياً 😅 جرب تكتب اسمه بصيغة ثانية.",
        "cant_identify": "بحثت أكثر من مرة، لكن ما قدرت أحدد المنتج أو ألقى له نتيجة مؤكدة. دز صورة أوضح أو اكتب اسم المنتج.",
        "image_error": "صار خلل بسيط وأنا أحمّل الصورة 😅 عيد إرسالها مرة ثانية.",
        "multi_text": "تمام لقيت {c} منتجات، أسوي سلة...",
        "multi_images": "تمام لقطت {c} منتجات، أسوي سلة...",
        "maps_body": "📍 تبي أقرب مكان؟\n\nاضغط الزر والخريطة بتفتح على أقرب الأماكن حولك 👇",
        "maps_btn": "📍 افتح الخريطة",
        "maps_body_loc": "📍 بحثك الأخير كان عن ({p})\n\nجهزت لك أقرب الأماكن حولك، اضغط الزر وافتح الخريطة 👇",
        "no_saved_product": "ما عندي منتج محفوظ حالياً 😅. ابحث عن منتج أول، وبعدها أدلك على أقرب مكان يبيعه!",
        "lang_saved": "تمام، بكلمك عربي من هني ورايح 🇰🇼\nدز صورة منتج أو اكتب اسمه وأنا حاضر!",
        "ask_global": "ما لقيت نتيجة محلية مؤكدة لهذا المنتج في موقعك الحالي. تبي أدور لك في المتاجر العالمية؟ 🌍",
        "global_yes": "نعم، ابحث عالميًا 🌍",
        "global_no": "لا، محلي فقط",
        "global_searching": "🌍 أدور لك عالميًا على أفضل النتائج المطابقة...",
        "global_none": "حتى بالبحث العالمي ما لقيت نتيجة مؤكدة ومباشرة لهذا المنتج.",
        "ask_not_found": "ما لقيت نفس المنتج بالضبط متوفر عندك محلياً 😅\n\nشرايك، وش تبيني أسوي؟ 👇",
        "opt_global": "🌍 دوّر عالمياً",
        "opt_similar": "🔄 بدائل مشابهة",
        "opt_no": "لا شكراً 🙏",
        "similar_searching": "🔄 أدور لك على أفضل البدائل المشابهة المتوفرة عندك...",
        "similar_none": "ما لقيت بدائل مشابهة بسعر مؤكد حالياً 😅 جرب صياغة ثانية.",
        "declined_ok": "تمام 🙏 إذا احتجت شي ثاني أنا حاضر!",
        "welcome_reply": "هلا والله! 🌟\nدز صورة المنتج أو اكتب اسمه، وأدور لك أفضل الأسعار والمتاجر القريبة منك 🛒",
        "thanks_reply": "العفو! 🌹 في الخدمة دايماً.. أي منتج ثاني تبيه أنا حاضر!",
    },
    "en": {
        "identifying": "One sec.. identifying the product and finding you the best deal!",
        "searching": "🔍 Looking up {q}...",
        "not_found": "Couldn't find it in-stock with a verified price 😅 try another phrasing or a clearer photo.",
        "identified_not_found": "I identified the product ({p}) but couldn't find a verified price right now 😅 try typing its name differently.",
        "cant_identify": "I searched several times but couldn’t identify the product or find a verified result. Send a clearer photo or type the product name.",
        "image_error": "Something went wrong while loading the image 😅 please send it again.",
        "multi_text": "Got it, found {c} products. Building your cart...",
        "multi_images": "Nice, spotted {c} products. Building your cart...",
        "maps_body": "📍 Want the nearest place?\n\nTap the button and the map will open on the closest spots around you 👇",
        "maps_btn": "📍 Open Map",
        "maps_body_loc": "📍 Your last search was ({p})\n\nI've lined up the closest places around you. Tap the button to open the map 👇",
        "no_saved_product": "I don't have a saved product yet 😅. Search for a product first, then I'll point you to the nearest store!",
        "lang_saved": "Great, I'll speak English with you from now on 🇬🇧\nSend a product photo or type its name and I'm on it!",
        "ask_global": "I couldn't find a verified local result in your current market. Search international stores instead? 🌍",
        "global_yes": "Yes, search globally 🌍",
        "global_no": "No, local only",
        "global_searching": "🌍 Searching international stores for the closest matches...",
        "global_none": "I still couldn't find a verified direct result globally.",
        "ask_not_found": "I couldn't find this exact product available locally 😅\n\nWhat would you like me to do? 👇",
        "opt_global": "🌍 Search globally",
        "opt_similar": "🔄 Similar items",
        "opt_no": "No thanks 🙏",
        "similar_searching": "🔄 Looking for the best similar alternatives available near you...",
        "similar_none": "I couldn't find similar alternatives with a verified price right now 😅 try another phrasing.",
        "declined_ok": "No problem 🙏 I'm here whenever you need me!",
        "welcome_reply": "Hello! 🌟\nSend a product photo or type its name, and I'll find you the best prices and nearby stores 🛒",
        "thanks_reply": "You're welcome! 🌹 Anytime.. just send me the next product!",
    },
}

LANG_INSTR = {
    "ar": "رد باللغة العربية فقط.",
    "en": "Respond ONLY in English. Keep the exact same response format and emojis, but translate all labels to English — including writing (Phone: NUMBER) instead of (هاتف: رقم). Keep prices in the user's local currency.",
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
- أي متجر لا يظهر له سعر رقمي واضح بعملة السوق الحالي احذفه من النتيجة.
- اكتب السعر بالفلوس كاملة دائماً: 1.950 وليس 1.95، و0.750 وليس 0.75.
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
    data = {"price": None, "available": True, "is_product": True, "title": "", "image_url": "", "currency": ""}
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
                    if not data["currency"]:
                        cur = str(offers.get("priceCurrency") or "").upper().strip()
                        if cur in KNOWN_CURRENCY_CODES:
                            data["currency"] = cur
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
    if not data["currency"]:
        m = soup.find("meta", property="product:price:currency")
        if m and m.get("content"):
            cur = str(m["content"]).upper().strip()
            if cur in KNOWN_CURRENCY_CODES:
                data["currency"] = cur
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

def _prune_verified_page_cache():
    if len(VERIFIED_PAGE_CACHE) <= VERIFIED_PAGE_CACHE_MAX:
        return
    # نحذف الأقدم حتى لا تتضخم الذاكرة على Railway مع مرور الأيام.
    items = sorted(VERIFIED_PAGE_CACHE.items(), key=lambda kv: kv[1].get("ts", 0))
    for k, _ in items[: len(items) - VERIFIED_PAGE_CACHE_MAX // 2]:
        VERIFIED_PAGE_CACHE.pop(k, None)

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
    _prune_verified_page_cache()
    for r in results:
        if r:
            name, url, info = r
            verified[name] = {"url": url, "price": info["price"], "title": info["title"], "image_url": info.get("image_url", ""), "currency": info.get("currency", "")}
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

def _collect_lens_items(data, items, seen):
    """يجمع نتائج Lens من كل الأقسام (exact/visual/products) مع تعليم القسم الحقيقي."""
    for key in ("exact_matches", "visual_matches", "products"):
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
                "section": key,
                "exact": key == "exact_matches" or bool(x.get("exact_match")),
                "thumbnail": (x.get("thumbnail") or x.get("image") or "").strip(),
                "image": (x.get("image") or x.get("thumbnail") or "").strip(),
                "price": ((x.get("price") or {}).get("value") if isinstance(x.get("price"), dict) else str(x.get("price") or "")),
                "price_value": ((x.get("price") or {}).get("extracted_value") if isinstance(x.get("price"), dict) else x.get("extracted_price")),
                "currency": ((x.get("price") or {}).get("currency") if isinstance(x.get("price"), dict) else ""),
                "in_stock": x.get("in_stock"),
                "condition": (x.get("condition") or "").strip(),
            })
    return items

def _serpapi_lens_request(public_url, lens_type, country, auto_crop, query_hint):
    """طلب Lens واحد إلى SerpApi ويعيد قائمة النتائج (قد تكون فارغة)."""
    params = {
        "engine": "google_lens",
        "url": public_url,
        "api_key": SERPAPI_API_KEY,
        "hl": "en",
        "safe": "active",
        "output": "json",
    }
    if lens_type:
        params["type"] = lens_type
    if country:
        params["country"] = country
    if auto_crop:
        params["auto_crop"] = "true"
    # q مسموح فقط مع all و visual_matches و products حسب توثيق SerpApi.
    if query_hint and (lens_type in (None, "", "all", "visual_matches", "products")):
        params["q"] = query_hint[:120]
    try:
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=60)
        if r.status_code >= 400:
            print(f"GOOGLE LENS HTTP {r.status_code} type={lens_type or 'all'} country={country or '-'}: {r.text[:300]}")
            return []
        data = r.json()
        if data.get("error"):
            print(f"GOOGLE LENS ERROR type={lens_type or 'all'} country={country or '-'}: {data.get('error')}")
            return []
        items, seen = [], set()
        _collect_lens_items(data, items, seen)
        print(f"GOOGLE LENS PASS type={lens_type or 'all'} country={country or '-'} auto_crop={auto_crop} -> {len(items)} items")
        return items
    except Exception as e:
        print(f"GOOGLE LENS PASS EXCEPTION type={lens_type or 'all'}: {e}")
        return []



# ---- Exact visual identity ---------------------------------------------------
# هوية المنتج تُحسم عالمياً أولاً، ثم نبحث عن السعر المحلي. لا يجوز أن يفوز منتج
# محلي مختلف لمجرد أن عنده سعر أو لأنه من متجر كويتي.
LENS_SECTION_BASE = {
    "exact_matches": 30000,
    "visual_matches": 18000,
    "products": 6000,
}

IDENTITY_NOISE_TOKENS = {
    "the","and","for","with","from","new","used","sale","offer","offers","price","buy","shop",
    "online","official","authentic","original","available","stock","promo","promocja","aldi","ebay",
    "amazon","women","woman","womens","men","man","mens","size","pack","piece","pcs","set",
    "http","https","www","com","net","org","co","uk","html","product","products",
    "de","la","el","para","con","y","en","da","do","na","z","w","i","of","to","in",
    "الكويت","كويت","السعر","شراء","متوفر","اصلي","أصلي","جديد","عرض","خصم","للبيع",
}

IDENTITY_WEAK_TOKENS = {
    "product","item","منتج","ماده","مادة","women","men","kids","adult",
    "shoe","shoes","slipper","slippers","sandal","sandals","bag","bags","shirt","dress",
    "cream","gel","spray","bottle","tube","box","علبه","علبة","عبوه","عبوة",
}


def _identity_words(text):
    raw = normalize_ar(str(text or "")).lower()
    raw = urllib.parse.unquote(raw)
    tokens = re.findall(r"[a-z0-9\u0600-\u06ff]+", raw)
    out = []
    for token in tokens:
        token = token.strip("_-")
        if not token or token in IDENTITY_NOISE_TOKENS or token.isdigit() or len(token) < 2:
            continue
        if token not in out:
            out.append(token)
    return set(out)


def _identity_models(text):
    raw = normalize_ar(str(text or "")).lower()
    models = set()
    for token in re.findall(r"[a-z0-9][a-z0-9._-]{2,}", raw):
        clean = token.strip("._-")
        if not (re.search(r"[a-z]", clean) and re.search(r"\d", clean)):
            continue
        # 300g/500ml أوزان وليست موديلات.
        if re.fullmatch(r"\d+(?:\.\d+)?(?:mg|g|gm|kg|ml|l|oz|lb|gb|tb)", clean):
            continue
        models.add(clean)
    return models


def _identity_sizes(text):
    raw = normalize_ar(str(text or "")).lower().replace(",", ".")
    unit_map = {
        "mg": ("g", 0.001), "g": ("g", 1.0), "gm": ("g", 1.0), "gram": ("g", 1.0),
        "grams": ("g", 1.0), "غ": ("g", 1.0), "جم": ("g", 1.0), "غرام": ("g", 1.0),
        "kg": ("g", 1000.0), "كغ": ("g", 1000.0), "كيلو": ("g", 1000.0),
        "ml": ("ml", 1.0), "مل": ("ml", 1.0), "l": ("ml", 1000.0),
        "liter": ("ml", 1000.0), "litre": ("ml", 1000.0), "لتر": ("ml", 1000.0),
        "oz": ("oz", 1.0), "lb": ("lb", 1.0), "gb": ("gb", 1.0), "tb": ("gb", 1024.0),
    }
    found = set()
    pattern = r"(?<!\w)(\d+(?:\.\d+)?)\s*(mg|grams?|gram|gm|kg|ml|liter|litre|oz|lb|gb|tb|g|l|غرام|كيلو|لتر|جم|كغ|مل|غ)(?!\w)"
    for number, unit in re.findall(pattern, raw, flags=re.I):
        try:
            base_unit, factor = unit_map[unit.lower()]
            value = round(float(number) * factor, 3)
            found.add(f"{value:g}{base_unit}")
        except Exception:
            continue
    return found


IDENTITY_VARIANTS = {
    "max","plus","ultra","mini","lite","pro","se","fe","air","sport","sports",
    "kids","kid","junior","jr","women","womens","men","mens",
}
IDENTITY_ACCESSORY_TOKENS = {
    "case","cover","protector","screen","charger","charging","cable","adapter","strap",
    "holder","mount","replacement","refill","compatible","accessory","accessories",
    "كفر","غطاء","حمايه","حماية","شاحن","كيبل","كابل","سير","حامل","بديل",
}


def _identity_variants(text):
    return _identity_words(text) & IDENTITY_VARIANTS


def _identity_accessories(text):
    return _identity_words(text) & IDENTITY_ACCESSORY_TOKENS


def _identity_numbers(text):
    raw = normalize_ar(str(text or "")).lower()
    return set(re.findall(r"(?<![a-z0-9])\\d{2,5}(?![a-z0-9])", raw))


def _identity_match_details(reference, candidate):
    a = _identity_words(reference)
    b = _identity_words(candidate)
    inter = a & b
    anchors_a = a - IDENTITY_WEAK_TOKENS
    anchors_b = b - IDENTITY_WEAK_TOKENS
    anchor_inter = anchors_a & anchors_b
    models_a, models_b = _identity_models(reference), _identity_models(candidate)
    sizes_a, sizes_b = _identity_sizes(reference), _identity_sizes(candidate)
    variants_a, variants_b = _identity_variants(reference), _identity_variants(candidate)
    accessories_a, accessories_b = _identity_accessories(reference), _identity_accessories(candidate)
    numbers_a, numbers_b = _identity_numbers(reference), _identity_numbers(candidate)
    model_match = bool(models_a & models_b)
    size_match = bool(sizes_a & sizes_b)
    model_conflict = bool(models_a and models_b and not model_match)
    size_conflict = bool(sizes_a and sizes_b and not size_match)
    variant_conflict = bool((variants_b - variants_a) & {"max","plus","ultra","mini","lite","se","fe","air"})
    accessory_conflict = bool(accessories_b and not accessories_a)
    number_conflict = bool(numbers_a and numbers_b and not (numbers_a & numbers_b))

    short_coverage = len(inter) / max(1, min(len(a), len(b))) if a and b else 0.0
    ref_coverage = len(inter) / max(1, len(a)) if a else 0.0
    jaccard = len(inter) / max(1, len(a | b)) if (a or b) else 0.0
    score = 0.45 * short_coverage + 0.30 * ref_coverage + 0.15 * jaccard
    score += min(len(anchor_inter), 3) * 0.08
    if model_match:
        score += 0.45
    if size_match:
        score += 0.18
    if model_conflict:
        score -= 0.65
    if size_conflict:
        score -= 0.30
    if variant_conflict:
        score -= 0.45
    if accessory_conflict:
        score -= 0.65
    if number_conflict:
        score -= 0.35
    score = max(0.0, min(score, 1.5))
    return {
        "score": score,
        "words": a,
        "candidate_words": b,
        "matches": inter,
        "anchors": anchors_a,
        "anchor_matches": anchor_inter,
        "models": models_a,
        "candidate_models": models_b,
        "model_match": model_match,
        "sizes": sizes_a,
        "candidate_sizes": sizes_b,
        "size_match": size_match,
        "variants": variants_a, "candidate_variants": variants_b,
        "accessories": accessories_a, "candidate_accessories": accessories_b,
        "numbers": numbers_a, "candidate_numbers": numbers_b,
        "conflict": model_conflict or size_conflict or variant_conflict or accessory_conflict or number_conflict,
    }


def _lens_section_strength(item):
    return LENS_SECTION_BASE.get(str(item.get("section") or ""), 0) + (8000 if item.get("exact") else 0)


def _canonical_lens_url(url):
    try:
        parsed = urllib.parse.urlsplit(str(url or ""))
        return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), "", ""))
    except Exception:
        return str(url or "").split("?")[0].rstrip("/").lower()


def _best_hint_match(hint, candidate):
    parts = [p.strip() for p in re.split(r"\s*[|｜]\s*", str(hint or "")) if p.strip()]
    if not parts:
        parts = [str(hint or "")]
    details = [_identity_match_details(part, candidate) for part in parts if _identity_words(part)]
    if not details:
        return _identity_match_details("", candidate)
    return max(details, key=lambda d: d["score"])


def _lens_identity_rank(item, matches, hint=""):
    title = str(item.get("title") or "").strip()
    score = _lens_section_strength(item)
    score += max(0, 1800 - min(int(item.get("position") or 99), 99) * 35)

    hint_details = _best_hint_match(hint, title)
    score += int(hint_details["score"] * 6500)
    if hint_details["model_match"]:
        score += 4500
    if hint_details["size_match"]:
        score += 1400
    if len(hint_details["anchor_matches"]) >= 2:
        score += 2200
    if hint_details["conflict"]:
        score -= 7500

    # Consensus among exact/visual results: repeated identity beats one isolated shopping card.
    consensus = 0
    for other in (matches or [])[:30]:
        if other is item or other.get("section") not in ("exact_matches", "visual_matches"):
            continue
        d = _identity_match_details(title, other.get("title") or "")
        if not d["conflict"] and (len(d["anchor_matches"]) >= 2 or d["model_match"] or d["score"] >= 0.58):
            consensus += 1
    score += min(consensus, 5) * 900

    # Locality and price are tiny tie-breakers only. They never decide product identity.
    if is_local_lens_result(item):
        score += 80
    if item.get("price") or item.get("price_value") not in (None, ""):
        score += 30
    return score


def _choose_best_lens_match(matches, hint=""):
    usable = [m for m in (matches or []) if str(m.get("title") or "").strip()]
    if not usable:
        return None
    ranked = sorted(usable, key=lambda m: _lens_identity_rank(m, usable, hint), reverse=True)
    for i, m in enumerate(ranked[:5], 1):
        print(
            f"LENS ID RANK {i}: score={_lens_identity_rank(m, usable, hint)} "
            f"section={m.get('section')} exact={m.get('exact')} title={m.get('title','')}"
        )
    return ranked[0]


def rerank_lens_context_with_vision(lens, vision_name):
    """Rerank the already-fetched Lens pool with literal OCR evidence, without allowing a local price card to win identity."""
    if not lens or not lens.get("matches"):
        return lens
    signature = lens.get("signature") or {}
    evidence = " | ".join(
        x for x in (
            vision_name,
            lens.get("image_name_en", ""),
            lens.get("image_name_ar", ""),
            signature.get("brand", ""),
            signature.get("model", ""),
            signature.get("size", ""),
        ) if x
    )
    chosen = _choose_best_lens_match(lens.get("matches") or [], evidence)
    if not chosen:
        return lens
    old_title = ((lens.get("chosen") or {}).get("title") or "").strip()
    new_title = (chosen.get("title") or "").strip()
    lens["chosen"] = chosen
    lens["vision_name"] = vision_name or ""
    aliases = []
    for value in [new_title, vision_name, lens.get("image_name_en", ""), lens.get("image_name_ar", "")] + list(lens.get("aliases") or []):
        value = str(value or "").strip()
        if value and value != old_title and value.upper() not in ("NONE", "UNKNOWN") and value not in aliases:
            aliases.append(value)
    lens["aliases"] = aliases[:5]
    lens["query"] = " | ".join(lens["aliases"][:4])
    if old_title != new_title:
        print(f"LENS IDENTITY CORRECTED BY OCR: {old_title} -> {new_title}")
    return lens


def strict_identity_context(identity_name, lens=None):
    """Build a fail-closed identity guard even when Vision wins or Lens returns nothing."""
    ctx = dict(lens or {})
    ctx["matches"] = list((lens or {}).get("matches") or [])
    ctx["vision_name"] = str(identity_name or "").strip()
    aliases = []
    for value in split_product_aliases(identity_name) + list((lens or {}).get("aliases") or []):
        value = str(value or "").strip()
        if value and value.upper() not in ("NONE", "UNKNOWN") and value not in aliases:
            aliases.append(value)
    ctx["aliases"] = aliases[:5]
    ctx["query"] = " | ".join(aliases[:4]) or str(identity_name or "").strip()
    # The adopted OCR/judge identity becomes the reference. Existing Lens matches remain only
    # as candidate URLs and must pass compatibility against this reference.
    ctx["chosen"] = {"title": str(identity_name or "").strip(), "link": "", "section": "vision_guard", "exact": True}
    ctx["strict_identity"] = True
    return ctx


def google_lens_lookup(image_b64, mime_type, lang="ar", query_hint=""):
    """Google Lens identity pool: global visual identity first, local shopping cards second."""
    if not ENABLE_GOOGLE_LENS or not SERPAPI_API_KEY or not PUBLIC_BASE_URL:
        print("GOOGLE LENS SKIPPED: missing SERPAPI_API_KEY or PUBLIC_BASE_URL")
        return {"aliases": [], "matches": [], "query": ""}

    public_url = publish_image_for_lens(image_b64, mime_type)
    if not public_url:
        print("GOOGLE LENS SKIPPED: could not publish image")
        return {"aliases": [], "matches": [], "query": ""}

    try:
        user_country = current_market().get("country", DEFAULT_COUNTRY)
        merged = []
        seen = {}

        def _merge(new_items):
            for item in new_items:
                key = _canonical_lens_url(item.get("link")) or normalize_ar(item.get("title") or "")
                if not key:
                    continue
                old_index = seen.get(key)
                if old_index is None:
                    seen[key] = len(merged)
                    merged.append(item)
                    continue
                old = merged[old_index]
                # Keep the stronger identity section, but preserve price/image metadata from either copy.
                if _lens_section_strength(item) > _lens_section_strength(old):
                    stronger, weaker = dict(item), old
                else:
                    stronger, weaker = dict(old), item
                for field in ("price", "price_value", "currency", "thumbnail", "image", "source", "in_stock"):
                    if stronger.get(field) in (None, "") and weaker.get(field) not in (None, ""):
                        stronger[field] = weaker.get(field)
                stronger["exact"] = bool(stronger.get("exact") or weaker.get("exact"))
                merged[old_index] = stronger

        # Product identity must not be restricted to Kuwait. This mirrors the useful part of Lens:
        # find the exact object globally, then use local cards only for availability/price.
        passes = [
            ("all", "", True),
            ("all", user_country, True),
            ("products", user_country, True),
        ]
        if ENABLE_LENS_WIDE_FALLBACK:
            passes.append(("all", "", False))

        for lens_type, country, auto_crop in passes:
            _merge(_serpapi_lens_request(public_url, lens_type, country, auto_crop, query_hint))

        matches = merged[:LENS_RESULT_LIMIT]
        if not matches:
            print("GOOGLE LENS: no visual matches after all passes")
            return {"aliases": [], "matches": [], "query": ""}

        for i, m in enumerate(matches[:8], 1):
            print(
                f"LENS MATCH {i}: {m.get('title','')} | {m.get('source','')} | "
                f"section={m.get('section','')} exact={m.get('exact', False)}"
            )

        chosen = _choose_best_lens_match(matches, query_hint) or matches[0]

        # Read literal package evidence independently from the Lens title. This prevents a wrong
        # shopping card from teaching the vision model a wrong brand/model.
        evidence_system = (
            "الصورة هي المرجع الوحيد. اقرأ هوية المنتج المطبوعة حرفياً ولا تستنتج براند أو موديل غير ظاهر. "
            "أرجع سطراً واحداً فقط: Arabic name | English name | BRAND | MODEL | SIZE | COLOR | PATTERN | HEEL | TYPE. "
            "MODEL وSIZE يكونان NONE إذا لم يظهرا. HEEL واحدة من FLAT, LOW, HIGH, NONE, UNKNOWN."
        )
        evidence_txt, _ = call_gemini([
            {"inline_data": {"mime_type": mime_type, "data": image_b64}},
            {"text": "اقرأ النص الظاهر والبراند واسم المنتج والوزن/السعة بدقة. لا تستخدم أي تخمين خارجي."},
        ], system=evidence_system, use_search=False)
        fields = [x.strip() for x in ((evidence_txt or "").strip().splitlines()[0] if evidence_txt else "").split("|")]
        image_name_ar = fields[0] if len(fields) > 0 else ""
        image_name_en = fields[1] if len(fields) > 1 else ""
        signature = {
            "brand": fields[2] if len(fields) > 2 else "",
            "model": fields[3] if len(fields) > 3 else "",
            "size": fields[4] if len(fields) > 4 else "",
            "color": fields[5].lower() if len(fields) > 5 else "",
            "pattern": fields[6].lower() if len(fields) > 6 else "",
            "heel": fields[7].upper() if len(fields) > 7 else "UNKNOWN",
            "type": fields[8].upper() if len(fields) > 8 else "",
        }

        evidence_hint = " | ".join(x for x in (query_hint, image_name_en, image_name_ar, signature["brand"], signature["model"], signature["size"]) if x)
        chosen = _choose_best_lens_match(matches, evidence_hint) or chosen
        chosen_title = (chosen.get("title") or "").strip()

        aliases = []
        for value in (chosen_title, image_name_en, image_name_ar):
            value = (value or "").strip()
            if value and value.upper() not in ("NONE", "UNKNOWN") and value not in aliases:
                aliases.append(value)

        query = " | ".join(aliases[:3])
        print(f"GOOGLE LENS EXACT IDENTITY: {query}")
        print(f"GOOGLE LENS IMAGE EVIDENCE: {signature}")
        return {
            "aliases": aliases[:4],
            "matches": matches,
            "query": query,
            "chosen": chosen,
            "signature": signature,
            "image_name_ar": image_name_ar,
            "image_name_en": image_name_en,
            "public_url": public_url,
        }
    except Exception as e:
        print(f"GOOGLE LENS EXCEPTION: {e}")
        return {"aliases": [], "matches": [], "query": ""}

def _meaningful_lens_tokens(text):
    """Exact tokens only; never use substring matching (deco must not match decofiller)."""
    return sorted(_identity_words(text) - IDENTITY_WEAK_TOKENS)


def _lens_reference_texts(lens_context):
    if not lens_context:
        return []
    chosen = lens_context.get("chosen") or {}
    sig = lens_context.get("signature") or {}
    refs = [
        chosen.get("title", ""),
        lens_context.get("vision_name", ""),
        lens_context.get("image_name_en", ""),
        lens_context.get("image_name_ar", ""),
        sig.get("brand", ""),
        sig.get("model", ""),
        sig.get("size", ""),
    ] + list(lens_context.get("aliases") or [])
    out = []
    for value in refs:
        value = str(value or "").strip()
        if value and value.upper() not in ("NONE", "UNKNOWN", "غير معروف") and _identity_words(value) and value not in out:
            out.append(value)
    return out


def _lens_compatibility_details(info, url, lens_context):
    candidate = " ".join([str(info.get("title") or ""), str(url or "")]).strip()
    refs = _lens_reference_texts(lens_context)
    if not refs:
        return _identity_match_details("", candidate)
    scored = [_identity_match_details(ref, candidate) for ref in refs]
    best = max(scored, key=lambda d: d["score"])
    combined = _identity_match_details(" ".join(refs), candidate)
    # Positive similarity may come from the best translated/full title, but every known
    # model, capacity, variant and accessory constraint remains mandatory.
    for key in (
        "models","candidate_models","sizes","candidate_sizes","variants","candidate_variants",
        "accessories","candidate_accessories","numbers","candidate_numbers"
    ):
        best[key] = combined.get(key, best.get(key))
    best["model_match"] = combined.get("model_match", best.get("model_match"))
    best["size_match"] = combined.get("size_match", best.get("size_match"))
    best["conflict"] = combined.get("conflict", False)
    return best


def _lens_offer_compatible(info, url, lens_context):
    """Reject a different SKU/brand even when it is local, cheap, or visually similar."""
    if not lens_context:
        return True
    chosen = lens_context.get("chosen") or {}
    chosen_url = _canonical_lens_url(chosen.get("link") or "")
    candidate_url = _canonical_lens_url(url)
    if chosen_url and candidate_url and chosen_url == candidate_url:
        return True

    details = _lens_compatibility_details(info, url, lens_context)
    if details["conflict"]:
        print(
            f"LENS ID CONFLICT REJECT: models={details['models']} vs {details['candidate_models']} "
            f"sizes={details['sizes']} vs {details['candidate_sizes']} "
            f"variants={details.get('variants')} vs {details.get('candidate_variants')} "
            f"accessories={details.get('candidate_accessories')} title={info.get('title','')}"
        )
        return False

    anchor_count = len(details["anchors"])
    anchor_matches = len(details["anchor_matches"])
    word_matches = len(details["matches"])
    strong = (
        details["model_match"]
        or (anchor_count >= 2 and anchor_matches >= 2)
        or (anchor_count == 1 and anchor_matches >= 1 and details["score"] >= 0.48)
        or (word_matches >= 3 and details["score"] >= 0.48)
    )
    if not strong:
        print(
            f"LENS IDENTITY REJECT: score={details['score']:.2f} anchors={sorted(details['anchor_matches'])} "
            f"words={sorted(details['matches'])} candidate={info.get('title','')} -> {url}"
        )
        return False

    # Existing visual guards remain useful after textual identity has passed.
    sig = lens_context.get("signature") or {}
    candidate_hay = normalize_ar(" ".join([str(info.get("title", "")), str(url)])).lower()
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
        if pattern in pattern_groups and not any(normalize_ar(k) in candidate_hay for k in keys):
            return False

    color = normalize_ar(sig.get("color") or "")
    if color and color not in ("unknown", "none", "غير معروف"):
        color_map = {
            "brown": ("brown", "tan", "cognac", "camel", "burgundy", "بني", "جملي"),
            "black": ("black", "اسود"), "green": ("green", "اخضر"),
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
    return f"متجر يبيع {product} {current_market().get('country_name','')}"

def maps_search_url(product, lat=None, lng=None):
    category = maps_category_for(product)
    safe_category = urllib.parse.quote(category)
    if lat is not None and lng is not None:
        return f"https://www.google.com/maps/search/{safe_category}/@{lat},{lng},15z"
    return f"https://www.google.com/maps/search/{safe_category}"

def send_maps_button(from_number, product, bot_id, lang):
    m = market_for_user(from_number)
    url = maps_search_url(product, m.get("lat"), m.get("lng")) if m.get("lat") is not None and m.get("lng") is not None else maps_search_url(product)
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
        "systemInstruction": {"parts": [{"text": system + (market_instruction() if use_search else "")}]},
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
        f"ابحث عن المنتج التالي في {current_market().get('country_name', 'Kuwait')} باستخدام العربية والإنجليزية معاً: {query}. "
        "حوّل الاسم داخلياً إلى مرادف عربي ومرادف إنجليزي، وجرّب اسم البراند باللاتيني والعربي, "
        "ولا تعتبر عدم ظهور نتيجة بلغة واحدة فشلاً قبل تجربة اللغة الأخرى. "
        f"ابدأ بنتائج المتاجر المحلية في {current_market().get('country_name', 'Kuwait')} حتى لو كانت متأخرة في Google، وافحص نتائج أعمق قبل المتاجر الأجنبية. "
        f"اعرض فقط نتائج لها سعر رقمي بعملة {current_market().get('currency', 'البلد')} ورابط صفحة منتج مباشر داخل المتجر. "
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


def fuse_identity_aliases(lens_title, vision_name, extra_aliases=None):
    """دمج هوية Lens مع هوية Vision في قائمة مرادفات واحدة للبحث.

    هذا هو مصدر قوة الخلط: البحث النصي يجرب عنوان Lens الدقيق أولاً،
    ثم الاسم العربي/الإنجليزي من قراءة الصورة، فيغطي فهرسة المتاجر بالعربي والإنجليزي معاً.
    """
    aliases = []
    def _add(value):
        value = (value or "").strip()
        if value and value.upper() not in ("NONE", "UNKNOWN") and value not in aliases:
            aliases.append(value)
    _add(lens_title)
    for part in split_product_aliases(vision_name):
        _add(part)
    for extra in (extra_aliases or []):
        _add(extra)
    return aliases[:4]


def _query_candidates(query):
    """يبني صيغ بحث منفصلة؛ العربية أولاً لأنها غالباً أفضل في فهرسة المتاجر المحلية."""
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


COUNTRY_URL_HINTS = {
    "kw": ("-kw.", "-kw/", "/kw/", "kuwait-", "kuwait/", "kw-en", "kw-ar", "_kw", "bcute-kw"),
    "sa": ("-sa.", "-sa/", "/sa/", "saudi-", "saudi/", "ksa", "sa-en", "sa-ar"),
    "ae": ("-ae.", "-ae/", "/ae/", "uae-", "uae/", "ae-en", "ae-ar"),
    "gb": ("-uk.", "-uk/", "/uk/", "united-kingdom", "gb-en"),
}

COUNTRY_CURRENCY_MARKERS = {
    "kw": ("kwd", "د.ك", " kd", "kuwait dinar"),
    "sa": ("sar", "ر.س", "saudi riyal"),
    "ae": ("aed", "د.إ", "uae dirham"),
    "gb": ("gbp", "£", "pound"),
    "us": ("usd", "$", "us dollar"),
}

def is_local_lens_result(item):
    """Classify a Lens/search result as belonging to the user's current market.

    Covers non-standard Kuwaiti domains such as bcute-kw.com, local URL paths,
    KWD price markers, and store/source text—not only .kw domains.
    """
    m = current_market()
    cc = (m.get("country") or DEFAULT_COUNTRY).lower()
    fields = ("title", "source", "link", "domain", "snippet", "price", "currency")
    hay = " ".join(str(item.get(k) or "") for k in fields).lower()
    link = str(item.get("link") or "").lower()
    try:
        host = urllib.parse.urlparse(link).netloc.lower().replace("www.", "")
    except Exception:
        host = ""

    if any(tld in host for tld in COUNTRY_TLDS.get(cc, [])):
        return True
    if any(hint in f"{host}{link}" for hint in COUNTRY_URL_HINTS.get(cc, ())):
        return True

    country_name = str(m.get("country_name") or "").lower()
    city = str(m.get("city") or "").lower()
    if (country_name and country_name in hay) or (city and city in hay):
        return True

    if cc == "kw" and any(h in hay for h in KUWAIT_STORE_HINTS):
        return True

    # A local-currency marker is useful when Lens omitted the country but gave a product card.
    if any(marker in hay for marker in COUNTRY_CURRENCY_MARKERS.get(cc, ())):
        return True
    return False


def is_foreign_lens_result(item):
    """True only when the result is clearly not local. Unknown results remain false."""
    if is_local_lens_result(item):
        return False
    m = current_market()
    cc = (m.get("country") or DEFAULT_COUNTRY).lower()
    hay = " ".join(str(item.get(k) or "") for k in ("title","source","link","domain","snippet","price","currency")).lower()
    host = urllib.parse.urlparse(str(item.get("link") or "")).netloc.lower()
    for other_cc, tlds in COUNTRY_TLDS.items():
        if other_cc != cc and any(tld in host for tld in tlds):
            return True
    for other_cc, markers in COUNTRY_CURRENCY_MARKERS.items():
        if other_cc != cc and any(marker in hay for marker in markers):
            return True
    # In explicit global mode, a valid non-local product URL is accepted as foreign.
    return bool(host)


def lens_priced_offers(lens_context, lang="ar", local_only=True, exclude_local=False):
    """Use only priced Lens cards that pass exact identity compatibility."""
    if not lens_context:
        return {}
    offers = {}
    used_urls = set()
    for i, item in enumerate(lens_context.get("matches") or [], 1):
        url = (item.get("link") or "").strip()
        title = (item.get("title") or "").strip()
        price_text = str(item.get("price") or "").strip()
        price_value = item.get("price_value")
        currency = (item.get("currency") or "").strip()
        in_stock = item.get("in_stock")
        if not title or not is_lens_product_url(url, item) or url in used_urls:
            continue
        if local_only and not is_local_lens_result(item):
            continue
        if exclude_local and is_local_lens_result(item):
            print(f"GLOBAL EXCLUDE LOCAL LENS: {title} -> {url}")
            continue
        if in_stock is False:
            print(f"LENS PRODUCT OOS SKIP: {title} -> {url}")
            continue
        if not price_text and price_value in (None, ""):
            continue
        if not _lens_offer_compatible(item, url, lens_context):
            continue

        if not exclude_local:
            price_hay = f"{price_text} {currency}".lower()
            expected_currency = (current_market().get("currency") or "").lower()
            currency_aliases = {expected_currency}
            if expected_currency == "kwd":
                currency_aliases.update({"د.ك", "kd"})
            if expected_currency and price_hay.strip() and not any(x and x in price_hay for x in currency_aliases):
                if price_value in (None, ""):
                    continue

        name = _lens_source_name(item, i)
        base = name
        n = 2
        while name in offers:
            name = f"{base} {n}"; n += 1
        try:
            numeric = float(price_value) if price_value not in (None, "") else None
        except Exception:
            numeric = None
        if exclude_local:
            shown, converted = display_global_price(price_value, price_text, currency, lang)
            if converted is not None:
                numeric = converted
        else:
            shown = format_lens_price(price_text, price_value, lang, currency)

        details = _lens_compatibility_details(item, url, lens_context)
        offers[name] = {
            "url": url, "price": numeric, "price_text": shown,
            "is_local": is_local_lens_result(item), "title": title,
            "position": int(item.get("position") or i), "exact": bool(item.get("exact")),
            "section": item.get("section") or "", "image_url": item.get("image") or item.get("thumbnail") or "",
            "identity_score": details.get("score", 0.0),
        }
        used_urls.add(url)

    ranked = sorted(
        offers.items(),
        key=lambda kv: (
            0 if kv[1].get("is_local") else 1,
            0 if kv[1].get("exact") else 1,
            -float(kv[1].get("identity_score") or 0),
            kv[1].get("price") if kv[1].get("price") is not None else 10**12,
            0 if kv[1].get("section") == "visual_matches" else 1,
            kv[1].get("position", 999),
        ),
    )
    return dict(ranked[:MAX_STORES])

def verify_lens_direct_matches(lens_context, local_only=True, exclude_local=False):
    """Verify only direct Lens pages that match the selected identity."""
    if not lens_context:
        return {}
    candidates = {}
    ordered = sorted(
        (lens_context.get("matches") or [])[:24],
        key=lambda m: (
            0 if m.get("exact") else 1,
            0 if m.get("section") == "visual_matches" else 1,
            0 if is_local_lens_result(m) else 1,
            int(m.get("position") or 99),
        ),
    )
    for i, m in enumerate(ordered[:12], 1):
        url = (m.get("link") or "").strip()
        title = (m.get("title") or "").strip()
        source = (m.get("source") or f"Lens {i}").strip()
        if not title or not is_lens_product_url(url, m):
            continue
        if local_only and not is_local_lens_result(m):
            continue
        if exclude_local and is_local_lens_result(m):
            print(f"GLOBAL EXCLUDE LOCAL VERIFY: {title} -> {url}")
            continue
        if not _lens_offer_compatible(m, url, lens_context):
            continue
        candidates[source] = url
    verified = verify_offers(candidates, (lens_context.get("chosen") or {}).get("title", ""))
    verified = filter_verified_with_lens(verified, lens_context)
    if verified:
        print(f"LENS HTML VERIFIED EXACT: {list(verified)}")
    return verified

def _new_layer_search(query, lang, prompt_text=None, source_image_b64=None, source_image_mime=None, lens_context=None, allow_global=False):
    # نتائج الصور تعتمد على الصورة نفسها، لذلك لا نستخدم كاش النص وحده.
    cached = None if source_image_b64 else cache_get(query, lang)
    if cached:
        return cached

    # For image requests, use the product cards returned by Google Lens itself first.
    # This preserves the many visually close results Google shows instead of demanding one exact SKU.
    lens_cards = lens_priced_offers(lens_context, lang, local_only=not allow_global, exclude_local=allow_global)
    if lens_cards:
        display_name = (lens_context.get("chosen") or {}).get("title") or query
        lines = [f"📦 {display_name}", ""]
        new_urls = {}
        for i, (name, info) in enumerate(lens_cards.items()):
            prefix = "✅" if i == 0 else "•"
            shown_price = info.get("price_text") or format_price(info.get("price"))
            lines.append(f"{prefix} {name} — {shown_price}")
            new_urls[name] = info["url"]
        print(f"LENS EXACT/VISUAL CARDS USED: {list(new_urls)}")
        return "\n".join(lines), new_urls

    # If Lens returned direct pages without price metadata, try our HTML verifier once.
    lens_verified = verify_lens_direct_matches(lens_context, local_only=not allow_global, exclude_local=allow_global)
    if lens_verified:
        if allow_global:
            # أسعار أجنبية من HTML: نحولها للعملة المحلية أولاً ثم نرتب بالأرخص المحوَّل.
            for info in lens_verified.values():
                shown, converted = display_global_price(info["price"], "", info.get("currency", ""), lang)
                info["shown"] = shown
                info["sort_price"] = converted if converted is not None else info["price"]
            sorted_v = sorted(lens_verified.items(), key=lambda x: x[1]["sort_price"])
        else:
            for info in lens_verified.values():
                info["shown"] = f"{format_price(info['price'])} {currency_label(lang)}"
            sorted_v = sorted(lens_verified.items(), key=lambda x: x[1]["price"])
        display_name = (lens_context.get("chosen") or {}).get("title") or query
        lines = [f"📦 {display_name}", ""]
        new_urls = {}
        for i, (name, info) in enumerate(sorted_v[:MAX_STORES]):
            prefix = "✅" if i == 0 else "•"
            lines.append(f"{prefix} {name} — {info['shown']}")
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
        # إذا لم نجد نتيجة صالحة، تنتقل المحاولات التالية إلى بحث عام في المتاجر المحلية المعروفة.
        priority_stores = priority_stores_for(search_term)
        stores_hint = "، ".join(priority_stores)
        market_name = current_market().get("country_name", "Kuwait")
        if attempt == 1 and current_market().get("country") == "kw":
            search_scope = (
                f"ابحث حصراً أولاً داخل هذه المتاجر وبنفس ترتيب الأولوية: {stores_hint}. "
                "لا تعرض أي متجر خارج هذه القائمة في هذه المحاولة، وإذا لم تجد فلا تكتب اعتذاراً مطولاً؛ أرجع بلا نتائج لننتقل للبحث العام. "
            )
        elif attempt == 1:
            search_scope = (
                f"ابدأ بأشهر المتاجر المحلية في {market_name} أولاً. "
                "إذا لم تجد فلا تكتب اعتذاراً مطولاً؛ أرجع بلا نتائج لننتقل للبحث العام. "
            )
        else:
            search_scope = (
                f"لم توجد نتيجة صالحة في متاجر الأولوية. "
                f"اعمل الآن بحثاً عاماً واسعاً في جميع متاجر {market_name} التي تبيع المنتج، بما فيها المتاجر المتخصصة، "
                "مع تجنب الإعلانات المبوبة فقط مثل OpenSooq. لا تستبعد المتجر لمجرد أنه ليس ضمن القائمة الأولى. "
            )
        current_prompt = (
            f"{context}ابحث في {market_name} عن هذا الاسم تحديداً: {search_term}. "
            + ((f"الاسم المختار من Google Lens هو: {(lens_context.get('chosen') or {}).get('title','')}. "
                "لا توسع البحث إلى موديلات أخرى من نفس البراند، ولا تقبل اختلافاً واضحاً في اللون أو النقشة أو وجود الكعب. ") if lens_context else "")
            + f"{search_scope}"
            "استخدم الاسم كما هو، ويمكن تجربة تهجئات قريبة لنفس المنتج فقط. "
            "أعطني حتى 3 متاجر فقط، وكل نتيجة يجب أن تحتوي سعراً رقمياً بعملة السوق الحالي "
            "ورابط صفحة المنتج المباشرة داخل المتجر. ممنوع روابط Google وصفحات البحث والتصنيف. "
            "لا تكتب متوفر أو InStock بدلاً من السعر. اكتب السعر بالفلوس كاملة مثل 1.950 وليس 1.95. "
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
                    currency = currency_label(lang)
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
    """Extract a price whether currency appears before or after the number."""
    text = str(line or "").replace(",", "")
    patterns = (
        r"(?:KWD|SAR|AED|BHD|QAR|OMR|USD|EUR|GBP|د\.ك|ر\.س|د\.إ|KD)\s*([0-9]+(?:\.[0-9]{1,3})?)",
        r"([0-9]+(?:\.[0-9]{1,3})?)\s*(?:KWD|SAR|AED|BHD|QAR|OMR|USD|EUR|GBP|د\.ك|ر\.س|د\.إ|KD)",
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
            "is_local": is_local_lens_result({"link": url, "source": offer.get("name", ""), "title": title}),
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


def _old_layer_search(query, lang, prompt_text=None, lens_context=None, allow_global=False):
    """Second layer: the broad multi-query search logic from the older bot."""
    if not OLD_LAYER_ENABLED:
        return "", {}
    if allow_global:
        base_prompt = (
            f"ابحث عالميًا عن {query}. استبعد تمامًا أي متجر داخل {current_market().get('country_name', 'بلد المستخدم')}، لأن البحث المحلي انتهى بالفعل. اقبل المتاجر الأجنبية الموثوقة فقط، مع سعر رقمي واضح ورابط صفحة المنتج المباشر، واذكر العملة الأصلية. {LANG_INSTR[lang]}"
        )
    else:
        base_prompt = prompt_text or (
            f"ابحث عن {query} في {current_market().get('country_name', 'Kuwait')}. متوفر فقط وبسعر رقمي واضح ورابط صفحة منتج مباشر. {LANG_INSTR[lang]}"
        )
    market_name = current_market().get("country_name", "Kuwait")
    if allow_global:
        variants = [
            base_prompt,
            f"{query} buy online worldwide exact product direct page price {LANG_INSTR[lang]}",
            f"{query} international stores exact visual match direct product link {LANG_INSTR[lang]}",
        ]
    elif current_market().get("country") == "kw":
        variants = [
            base_prompt,
            f"{query} افضل سعر في الكويت Xcite Eureka Blink Noon Jarir Lulu Carrefour Best Al Yousifi جمعية دوت كوم - قارن الاسعار {LANG_INSTR[lang]}",
            f"{query} شراء اونلاين الكويت سعر متوفر متجر كويتي صفحة المنتج مباشرة {LANG_INSTR[lang]}",
        ]
    else:
        variants = [
            base_prompt,
            f"{query} best price in {market_name} local stores direct product page {LANG_INSTR[lang]}",
            f"{query} buy online {market_name} local delivery price in {current_market().get('currency','local currency')} {LANG_INSTR[lang]}",
        ]
    # MARKET_CTX يضيع داخل ThreadPool؛ نمرر سوق المستخدم مع كل استدعاء وإلا رجع البحث للكويت الافتراضية.
    market_snapshot = current_market()
    futures = []
    for variant in variants:
        for _ in range(OLD_LAYER_DUPLICATES):
            futures.append(OLD_SEARCH_POOL.submit(_run_with_market, market_snapshot, call_gemini, [{"text": variant}]))
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
    if allow_global and verified:
        verified = {
            name: info for name, info in verified.items()
            if not is_local_lens_result({"link": info.get("url", ""), "source": name, "title": info.get("title", "")})
        }
        print(f"GLOBAL OLD LAYER AFTER LOCAL EXCLUSION: {list(verified)}")
    if lens_context:
        verified = filter_verified_with_lens(verified, lens_context)
    if not verified:
        print("OLD LAYER: no verified direct offers")
        return "", {}

    if allow_global:
        # عالمي: كل سعر يُحوَّل إلى عملة المستخدم المحلية بالفلوس ثم نرتب بالأرخص المحوَّل.
        for info in verified.values():
            shown, converted = display_global_price(info["price"], "", info.get("currency", ""), lang)
            info["shown"] = shown
            info["sort_price"] = converted if converted is not None else info["price"]
        sorted_v = sorted(verified.items(), key=lambda x: x[1]["sort_price"])
    else:
        for info in verified.values():
            info["shown"] = f"{format_price(info['price'])} {currency_label(lang)}"
        sorted_v = sorted(verified.items(), key=lambda x: x[1]["price"])
    title = product_title(best_txt, query)
    lines = [title, ""]
    new_urls = {}
    for i, (name, info) in enumerate(sorted_v[:max(MAX_STORES * 2, 6)]):
        prefix = "✅" if i == 0 else "•"
        lines.append(f"{prefix} {name} — {info['shown']}")
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
        quality += 40 if o.get("is_local") else 0
        quality += _store_priority_value(o.get("name", ""), o.get("url", "")) * 2
        quality += 12 if o.get("layer") == "new" else 8
        quality += max(0, 20 - min(int(o.get("lens_position", 999)), 20))
        return (-quality, o.get("price", 10**9))
    offers.sort(key=rank)
    chosen = offers[:MAX_STORES]

    display_title = ((lens_context or {}).get("chosen") or {}).get("title") or \
                    product_title(new_txt, "").replace("📦", "").strip() or \
                    product_title(old_txt, query).replace("📦", "").strip() or query
    currency = currency_label(lang)
    lines = [f"📦 {display_title}", ""]
    urls = {}
    for i, offer in enumerate(chosen):
        prefix = "✅" if i == 0 else "•"
        lines.append(f"{prefix} {offer['name']} — {format_price(offer['price'])} {currency}")
        urls[offer["name"]] = offer["url"]
    print("TWO LAYER FINAL:", [(o["layer"], o["name"], o["price"]) for o in chosen])
    return "\n".join(lines), urls


def search_product(query, lang, prompt_text=None, source_image_b64=None, source_image_mime=None, lens_context=None, allow_global=False):
    """Two-layer search: new Lens/priority method first, old broad method second, then rank both."""
    cached = None if source_image_b64 or lens_context else cache_get(query, lang)
    if cached:
        return cached

    new_result = _new_layer_search(
        query, lang, prompt_text=prompt_text,
        source_image_b64=source_image_b64, source_image_mime=source_image_mime,
        lens_context=lens_context, allow_global=allow_global,
    )
    print(f"NEW LAYER DONE offers={len(extract_store_offers(new_result[0])) if new_result[0] else 0}")

    # Services and genuine informational answers should not be forced through product comparison.
    if new_result[0] and (is_service_answer(new_result[0]) or is_informational_answer(new_result[0])):
        return new_result

    # For fashion identified by Lens, generic old-layer results are dangerous (e.g. any pajama).
    # Keep only exact/local Lens results. If none exist, the caller asks before global search.
    if lens_context and lens_context.get("force_lens_only"):
        mode = "GLOBAL" if allow_global else "LOCAL"
        print(f"OLD LAYER SKIPPED: FASHION LENS-ONLY {mode} MODE")
        return new_result

    old_result = _old_layer_search(query, lang, prompt_text=prompt_text, lens_context=lens_context, allow_global=allow_global)
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

def send_location_request(to, bot_id, lang="ar", refresh=False):
    if lang == "en":
        body = "📍 Please share your current location so I can show stores and prices near you."
        if refresh:
            body = "📍 It has been 3 days. Please update your current location before the next search."
    else:
        body = "📍 دز موقعك الحالي عشان أطلع لك المتاجر والأسعار في البلد والمنطقة اللي أنت فيها."
        if refresh:
            body = "📍 مرّت 3 أيام. دز موقعك الحالي من جديد قبل البحث عشان أتأكد من البلد والمنطقة."
    url=f"{GRAPH_URL}/{bot_id}/messages"
    h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    payload={
        "messaging_product":"whatsapp",
        "to":to,
        "type":"interactive",
        "interactive":{
            "type":"location_request_message",
            "body":{"text":body[:1024]},
            "action":{"name":"send_location"}
        }
    }
    try:
        r=requests.post(url,json=payload,headers=h,timeout=15)
        if r.ok:
            return True
        print(f"LOCATION REQUEST ERR {r.status_code}: {r.text[:300]}")
    except Exception as e:
        print(f"LOCATION REQUEST ERR: {e}")
    # fallback if the interactive location request is not available for the account/version
    return send_whatsapp_text(to, body + ("\n\nمن واتساب: + ثم الموقع." if lang == "ar" else "\n\nIn WhatsApp: tap +, then Location."), bot_id)

def route_pending_after_location(phone):
    pending = PENDING_ONBOARDING.pop(phone, None)
    if not pending:
        return
    msg = pending.get("message") or {}
    bot_id = pending.get("bot_id") or PHONE_NUMBER_ID
    typ = msg.get("type")
    if typ == "image":
        IMAGE_BUFFER[phone]["images"].append(msg)
        IMAGE_BUFFER[phone]["time"] = time.time()
        IMAGE_BUFFER[phone]["bot_id"] = bot_id
        asyncio.run(process_image_buffer(phone))
    elif typ == "text":
        process_text_message(msg, bot_id, onboarding_checked=True)

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
        load_user_preferences(from_number)
        typ=msg.get("type")

        # Language choices and shared locations must always pass through.
        if typ == "interactive":
            background_tasks.add_task(process_interactive_message,msg,bot_id)
            return {"status":"ok"}
        if typ == "location":
            background_tasks.add_task(process_location_message,msg,bot_id)
            return {"status":"ok"}

        # First use: keep the request, ask for language, then ask for location.
        if from_number not in USER_LANG:
            cache_pending_message(from_number, msg, bot_id)
            background_tasks.add_task(asyncio.to_thread, send_language_choice, from_number, bot_id)
            return {"status":"ok"}

        # Every 3 days: pause the request and refresh location before searching.
        if not location_is_valid(from_number):
            cache_pending_message(from_number, msg, bot_id)
            refresh = bool(USER_LOCATION_TS.get(from_number, 0))
            background_tasks.add_task(asyncio.to_thread, send_location_request, from_number, bot_id, USER_LANG.get(from_number,"ar"), refresh)
            return {"status":"ok"}

        if typ=="image":
            IMAGE_BUFFER[from_number]["images"].append(msg); IMAGE_BUFFER[from_number]["time"]=time.time(); IMAGE_BUFFER[from_number]["bot_id"]=bot_id
            if len(IMAGE_BUFFER[from_number]["images"])==1:
                background_tasks.add_task(process_image_buffer,from_number)
        elif typ=="text":
            background_tasks.add_task(process_text_message,msg,bot_id,True)
    except Exception as e: print(f"webhook err {e}")
    return {"status":"ok"}



def _store_pending_global(phone, bot_id, lang, query, lens_context, prompt_text=None):
    PENDING_GLOBAL_SEARCH[phone] = {
        "bot_id": bot_id, "lang": lang, "query": query,
        "lens_context": lens_context or {}, "prompt_text": prompt_text,
        "ts": time.time(),
    }

def _pop_pending_global(phone):
    item = PENDING_GLOBAL_SEARCH.pop(phone, None)
    if not item:
        return None
    if time.time() - item.get("ts", 0) > GLOBAL_PENDING_TTL:
        return None
    return item

def send_not_found_choice(phone, bot_id, lang):
    """المنتج بالضبط غير متوفر محلياً: 3 خيارات — عالمي، بدائل مشابهة، أو لا شكراً."""
    send_whatsapp_buttons(phone, T(lang, "ask_not_found"), [
        {"id": "nf_global", "title": T(lang, "opt_global")[:20]},
        {"id": "nf_similar", "title": T(lang, "opt_similar")[:20]},
        {"id": "nf_no", "title": T(lang, "opt_no")[:20]},
    ], bot_id)

def run_similar_search(phone, item):
    """بحث بدائل مشابهة: نفس الفئة والاستخدام، محلياً فقط، بدون قيود Lens الصارمة."""
    activate_market(phone)
    bot_id = item["bot_id"]; lang = item["lang"]; query = item["query"]
    send_whatsapp_text(phone, T(lang, "similar_searching"), bot_id)
    # نزيل جزء الكابشن إن وجد ونأخذ اسم المنتج الأساسي.
    base = short_query(re.sub(r"^.*?—\s*", "", query).strip() or query) or short_query(query)
    market_name = current_market().get("country_name", "Kuwait")
    prompts = [
        (f"المنتج التالي غير متوفر محلياً: {base}. اقترح حتى 3 بدائل مشابهة له فعلياً — نفس الفئة "
         f"ونفس الاستخدام ومستوى جودة قريب — متوفرة الآن في متاجر {market_name} فقط. "
         "لكل بديل: اسم البديل الفعلي (وليس اسم المنتج الأصلي)، سعر رقمي واضح بعملة السوق، "
         f"ورابط صفحة المنتج المباشرة داخل المتجر. اكتب السعر بالفلوس كاملة مثل 1.950. {LANG_INSTR[lang]}"),
        (f"3 best in-stock alternatives similar to {base} in {market_name} local online stores, "
         f"each with the alternative's own name, a numeric price, and a direct product page link. {LANG_INSTR[lang]}"),
    ]
    for prompt in prompts:
        txt, urls = call_gemini([{"text": prompt}])
        urls = direct_urls_only(urls)
        offers = extract_store_offers(txt)
        if not txt or not offers or not urls:
            continue
        verified = verify_offers(urls, base)
        if verified:
            sorted_v = sorted(verified.items(), key=lambda x: x[1]["price"])
            title = product_title(txt, f"بدائل مشابهة: {base}" if lang == "ar" else f"Similar to: {base}")
            lines = [title, ""]
            new_urls = {}
            for i, (name, info) in enumerate(sorted_v[:MAX_STORES]):
                prefix = "✅" if i == 0 else "•"
                alt_title = (info.get("title") or "").strip()
                label = f"{name}: {alt_title[:45]}" if alt_title else name
                lines.append(f"{prefix} {label} — {format_price(info['price'])} {currency_label(lang)}")
                new_urls[name] = info["url"]
            send_product_result(phone, "\n".join(lines), new_urls, bot_id, lang, base)
            return
        # بعض المتاجر تمنع فحص HTML؛ نقبل سطور Gemini التي لها رابط منتج مباشر فقط.
        kept = []
        for offer in offers:
            matched = match_url(offer["name"], urls)
            if matched and is_direct_store_url(matched):
                kept.append((offer, matched))
        if kept:
            title = product_title(txt, f"بدائل مشابهة: {base}" if lang == "ar" else f"Similar to: {base}")
            lines = [title, ""]
            new_urls = {}
            for i, (offer, matched) in enumerate(kept[:MAX_STORES]):
                prefix = "✅" if i == 0 else "•"
                body = re.sub(r"^(?:✅|🏆|•)\s*", "", offer["line"]).strip()
                lines.append(f"{prefix} {body}")
                new_urls[offer["name"]] = matched
            send_product_result(phone, "\n".join(lines), new_urls, bot_id, lang, base)
            return
    send_whatsapp_text(phone, T(lang, "similar_none"), bot_id)

def run_global_search(phone, item):
    activate_market(phone)
    bot_id = item["bot_id"]; lang = item["lang"]; query = item["query"]
    send_whatsapp_text(phone, T(lang, "global_searching"), bot_id)
    txt, urls = search_product(
        query, lang, prompt_text=item.get("prompt_text"),
        lens_context=item.get("lens_context"), allow_global=True,
    )
    if txt and urls:
        filtered_urls = {}
        for name, url in urls.items():
            local = is_local_lens_result({"link": url, "source": name, "title": name})
            if local:
                print(f"GLOBAL FINAL GUARD REJECT LOCAL: {name} -> {url}")
            else:
                filtered_urls[name] = url
        if len(filtered_urls) != len(urls):
            # Remove offer lines whose CTA was rejected, so text and buttons stay consistent.
            kept_names = {normalize_name(n) for n in filtered_urls}
            kept_lines = []
            for line in (txt or "").splitlines():
                offer_match = re.match(r"^(?:✅|🏆|•)\s*(.+?)\s*(?:—|–|-)\s*", line.strip())
                if offer_match and normalize_name(offer_match.group(1)) not in kept_names:
                    continue
                kept_lines.append(line)
            txt = "\n".join(kept_lines).strip()
            urls = filtered_urls
    if not txt or not extract_store_offers(txt) or not urls:
        send_whatsapp_text(phone, T(lang, "global_none"), bot_id)
        return
    send_product_result(phone, txt, urls, bot_id, lang, query)

def process_interactive_message(message, bot_id):
    from_number=message["from"]
    reply=(message.get("interactive") or {}).get("button_reply") or {}
    btn_id=reply.get("id","")
    if btn_id in ("global_yes", "nf_global"):
        item = _pop_pending_global(from_number)
        if item:
            run_global_search(from_number, item)
        return
    if btn_id == "nf_similar":
        item = _pop_pending_global(from_number)
        if item:
            run_similar_search(from_number, item)
        return
    if btn_id in ("global_no", "nf_no"):
        PENDING_GLOBAL_SEARCH.pop(from_number, None)
        send_whatsapp_text(from_number, T(USER_LANG.get(from_number, "ar"), "declined_ok"), bot_id)
        return
    if btn_id not in ("lang_ar","lang_en"):
        return
    lang = "ar" if btn_id=="lang_ar" else "en"
    USER_LANG[from_number]=lang
    save_user_preferences(from_number)
    # Do not run the stored search yet. Location is mandatory after language selection.
    send_location_request(from_number, bot_id, lang, refresh=False)

async def process_image_buffer(from_number):
    await asyncio.sleep(BUFFER_SECONDS)
    data=IMAGE_BUFFER.pop(from_number,None)
    if not data: return
    lang=USER_LANG.get(from_number,"ar")
    if len(data["images"])==1: await asyncio.to_thread(process_single_image,data["images"][0],data["bot_id"],lang)
    else: await asyncio.to_thread(process_multi_images,data["images"],from_number,data["bot_id"],lang)

def identify_product_with_retry(b64, mime, lang="ar"):
    """Literal OCR-first product identity. Never substitutes a similar commercial product."""
    prompts = [
        "اقرأ البراند واسم المنتج والموديل والوزن/السعة كما هي مطبوعة. لا تستنتج بديلاً. Arabic name | exact English name.",
        "دقق في كل النص الظاهر والشعار والباركود/الموديل. اذكر فقط ما يظهر فعلاً. Arabic | English.",
        "إذا تعذر اسم كامل، اكتب البراند الظاهر + نوع المنتج المحافظ فقط، بلا موديل مخترع. Arabic | English.",
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
            print(f"IMAGE IDENTIFIED LITERAL attempt={attempt + 1}: {candidate}")
            return candidate
        print(f"IMAGE IDENTIFY ATTEMPT {attempt + 1} FAILED")
    return ""

def _identity_tokens(text):
    t = normalize_ar(text or "")
    return {x for x in re.findall(r"[a-z0-9\u0600-\u06ff]+", t) if len(x) > 2}


def identity_candidates_agree(vision_name, lens_title):
    """Agreement requires exact discriminative tokens/model, not generic or substring overlap."""
    d = _identity_match_details(vision_name, lens_title)
    if d["conflict"]:
        return False
    return bool(
        d["model_match"]
        or (len(d["anchor_matches"]) >= 2 and d["score"] >= 0.42)
        or (len(d["anchor_matches"]) == 1 and len(d["anchors"]) == 1 and d["score"] >= 0.62)
    )

def is_fashion_identity(vision_name, caption=""):
    """Return True for any apparel/fashion item where exact visual design matters."""
    q = normalize_ar(f"{vision_name or ''} {caption or ''}")
    fashion_terms = (
        "ملابس", "قميص", "قميص نسائي", "بلوزه", "بلوزة", "توب", "فستان",
        "بنطلون", "تنوره", "تنورة", "جاكيت", "معطف", "عبايه", "عباية",
        "بيجامه", "بيجامة", "بجامه", "بجامة", "ملابس نوم", "روب", "طقم نسائي",
        "ساتان", "مخطط", "مخططه", "مخططة", "مطبوع", "موضة", "ازياء", "أزياء",
        "حذاء", "شبشب", "صندل", "نعال", "سنيكر", "شنطه", "شنطة", "حقيبه", "حقيبة",
        "shirt", "women's shirt", "womens shirt", "blouse", "top", "dress", "skirt",
        "pants", "trousers", "jacket", "coat", "abaya", "pajama", "pajamas",
        "pyjama", "pyjamas", "nightwear", "sleepwear", "robe", "satin", "printed",
        "striped", "fashion", "apparel", "clothing", "shoe", "mule", "slipper",
        "sandal", "sneaker", "bag", "handbag", "co-ord", "coord"
    )
    return any(term in q for term in fashion_terms)

def _legacy_should_use_google_lens(vision_name, caption=""):
    """Legacy router kept as a fallback when Lens-primary mode is disabled."""
    raw = f"{vision_name or ''} {caption or ''}".strip()
    q = normalize_ar(raw)
    if not vision_name:
        return True

    if is_fashion_identity(vision_name, caption):
        return True

    uncertain = (
        "غير معروف", "منتج غير", "unknown", "unidentified", "possibly", "ربما",
        "قد يكون", "عام", "generic", "لا استطيع", "لا أستطيع"
    )
    if any(x in q for x in uncertain) or len(_identity_tokens(vision_name)) < 2:
        return True

    has_model = bool(re.search(r"\b(?=[a-z0-9-]{4,}\b)(?=[a-z0-9-]*[a-z])(?=[a-z0-9-]*\d)[a-z0-9-]+\b", raw, re.I))
    packaged = (
        "كرتون", "علبه", "عبوه", "جرام", "كيلو", "مل", "لتر", "حليب", "عصير",
        "شيبس", "بسكوت", "كيك", "قهوه", "شاي", "دواء", "كريم", "شامبو",
        "حبوب", "مكمل", "صلصه", "بهارات", "زعفران", "هيل", "منظف",
        "bottle", "pack", "box", "gram", "kg", "ml", "liter", "medicine",
        "shampoo", "cream", "snack", "cake", "coffee", "tea", "spice"
    )
    if has_model or any(x in q for x in packaged):
        return False

    visual_categories = (
        "حذاء", "شبشب", "صندل", "نعال", "ملابس", "قميص", "بنطلون", "فستان",
        "جاكيت", "قبعه", "شنطه", "حقيبه", "نظاره", "ساعه", "خاتم", "قلاده",
        "اثاث", "كرسي", "طاوله", "ديكور", "لعبه", "سياره", "قطعه غيار",
        "shoe", "mule", "slipper", "sandal", "sneaker", "dress", "shirt",
        "jacket", "cap", "hat", "bag", "handbag", "glasses", "sunglasses",
        "watch", "ring", "necklace", "furniture", "chair", "table", "decor",
        "بيجامه", "بيجامة", "بجامه", "بجامة", "ملابس نوم", "روب", "بلوزه", "بلوزة",
        "توب", "طقم نسائي", "قميص نسائي", "ساتان", "مخطط", "مخططه", "مخططة",
        "pajama", "pajamas", "pyjama", "pyjamas", "nightwear", "sleepwear",
        "blouse", "top", "co-ord", "coord", "satin", "printed", "striped"
    )
    return any(x in q for x in visual_categories)


def _is_text_heavy_packaged_product(vision_name, caption=""):
    """Return True for labels/packages where OCR identity is usually stronger than Lens."""
    raw = f"{vision_name or ''} {caption or ''}".strip()
    q = normalize_ar(raw)
    if not q:
        return False

    package_terms = (
        "كرتون", "علبه", "علبة", "عبوه", "عبوة", "جرام", "غرام", "كيلو", "جم", "mg",
        "مل", "لتر", "حليب", "عصير", "شيبس", "بسكوت", "كيك", "قهوه", "قهوة", "شاي",
        "دواء", "كريم", "شامبو", "حبوب", "مكمل", "صلصه", "صلصة", "بهارات", "زعفران",
        "هيل", "منظف", "صابون", "bottle", "pack", "box", "gram", "kg", "g ",
        " g", "ml", "liter", "medicine", "tablet", "capsule", "shampoo", "cream",
        "snack", "cake", "coffee", "tea", "spice", "detergent", "soap"
    )
    text_strength = sum(1 for x in package_terms if x in q)
    has_model = bool(re.search(r"\b(?=[a-z0-9-]{4,}\b)(?=[a-z0-9-]*[a-z])(?=[a-z0-9-]*\d)[a-z0-9-]+\b", raw, re.I))
    has_numbers = bool(re.search(r"\d", raw))
    token_count = len(_identity_tokens(vision_name))
    return has_model or (text_strength >= 1 and (has_numbers or token_count >= 3))


def lens_routing_decision(vision_name, caption=""):
    """Every product image gets Lens; packages use OCR+Lens arbitration rather than Lens suppression."""
    raw = f"{vision_name or ''} {caption or ''}".strip()
    q = normalize_ar(raw)
    if not ENABLE_GOOGLE_LENS:
        return False, "LENS_DISABLED"
    if not vision_name:
        return True, "NO_VISION_IDENTITY"
    if is_fashion_identity(vision_name, caption):
        return True, "FASHION_ALWAYS_LENS"
    uncertain = (
        "غير معروف", "منتج غير", "unknown", "unidentified", "possibly", "ربما",
        "قد يكون", "عام", "generic", "لا استطيع", "لا أستطيع"
    )
    if any(x in q for x in uncertain) or len(_identity_tokens(vision_name)) < 2:
        return True, "UNCERTAIN_IDENTITY"
    if _is_text_heavy_packaged_product(vision_name, caption):
        return True, "TEXT_HEAVY_PACKAGE_OCR_LENS_FUSION"
    if LENS_PRIMARY_MODE:
        return True, "LENS_PRIMARY_DEFAULT"
    return _legacy_should_use_google_lens(vision_name, caption), "LEGACY_ROUTER"

def should_use_google_lens(vision_name, caption=""):
    use_lens, _reason = lens_routing_decision(vision_name, caption)
    return use_lens


def choose_image_identity(image_b64, mime_type, lens, vision_name):
    """Arbitrate between Google Lens and direct vision/OCR.

    Rules: text printed on a package, barcode/model/brand and product type are stronger
    evidence than visual similarity. Lens is stronger for unlabelled fashion/objects.
    """
    lens_title = ((lens.get("chosen") or {}).get("title") or lens.get("query") or "").strip()
    vision_name = (vision_name or "").strip()
    if not lens_title:
        return vision_name, None, "VISION_ONLY"
    if not vision_name:
        return lens_title, lens, "LENS_ONLY"

    judge_system = """أنت حكم دقيق لهوية المنتجات. الصورة هي المرجع النهائي.
قارن بين اقتراح Google Lens واقتراح قارئ النص/الملصق.
قواعد إلزامية:
1) إذا كانت الصورة لعبوة أو منتج عليه ملصق واضح، فاسم البراند والنص المطبوع ونوع المنتج والوزن أقوى من التشابه الشكلي.
2) لا تعتبر منتجين متطابقين لمجرد اشتراكهما في مكون مثل الزعفران أو اللون أو الفئة.
3) إذا قال اقتراح إن المنتج كيك/حلويات والآخر زعفران خام أو بهارات فهما مختلفان قطعاً.
4) للملابس والأحذية والحقائب غير المعلّمة بوضوح، أعط Lens وزناً أكبر.
5) اختر MERGE فقط إذا كان الاقتراحان لنفس المنتج فعلاً ولا يوجد تعارض.
أرجع JSON فقط بهذا الشكل:
{"winner":"VISION"|"LENS"|"MERGE","confidence":0-100,"final_name":"اسم بحث دقيق بالعربي | English","reason":"سبب قصير"}
"""
    top_lens_titles = "\n".join(
        f"- {m.get('section','')}: {m.get('title','')}" for m in (lens.get("matches") or [])[:8]
    )
    signature = lens.get("signature") or {}
    prompt = (
        f"Google Lens selected candidate: {lens_title}\n"
        f"Direct literal vision/OCR candidate: {vision_name}\n"
        f"Literal image evidence: {json.dumps(signature, ensure_ascii=False)}\n"
        f"Other Lens candidates:\n{top_lens_titles}\n"
        "احكم من النص والشعار والموديل/الوزن الظاهر في الصورة. السعر أو كون المتجر محلياً ليس دليلاً على الهوية."
    )
    raw, _ = call_gemini([
        {"inline_data": {"mime_type": mime_type, "data": image_b64}},
        {"text": prompt},
    ], system=judge_system, use_search=False)
    try:
        data = json.loads(re.search(r"\{.*\}", raw or "", flags=re.S).group(0))
    except Exception:
        print(f"IDENTITY JUDGE PARSE FAIL: {raw}")
        return vision_name, None, "VISION_SAFE_FALLBACK"

    winner = str(data.get("winner", "VISION")).upper()
    confidence = int(float(data.get("confidence", 0) or 0))
    final_name = str(data.get("final_name") or "").strip()
    reason = str(data.get("reason") or "").strip()
    print(f"IDENTITY JUDGE: winner={winner} confidence={confidence} reason={reason}")

    # Low confidence must never let Lens override readable package evidence.
    if winner == "LENS" and confidence >= 78:
        return final_name or lens_title, lens, "LENS"
    if winner == "MERGE" and confidence >= 82:
        return final_name or f"{vision_name} | {lens_title}", lens, "MERGE"
    return final_name or vision_name, None, "VISION"

def process_single_image(message,bot_id,lang="ar"):
    from_number=message["from"]
    market = activate_market(from_number)
    caption=(message.get("image",{}) or {}).get("caption","").strip()
    send_whatsapp_text(from_number,T(lang,"identifying"),bot_id)
    try:
        b64,mime=download_whatsapp_media(message["image"]["id"])
    except Exception as e:
        # روابط ميديا واتساب تنتهي صلاحيتها بسرعة؛ لا نترك المستخدم بدون رد.
        print(f"MEDIA DOWNLOAD ERR: {e}")
        send_whatsapp_text(from_number, T(lang, "image_error"), bot_id)
        return

    # FUSION ROUTER (قوة الخلط):
    # 1) Lens و Vision يشتغلان بالتوازي — لا ننتظر أحدهما ليبدأ الآخر.
    # 2) Lens متعدد التمريرات (products -> all -> wide) = نفس قوة تطبيق Lens.
    # 3) الهوية النهائية = دمج عنوان Lens الدقيق + الاسم العربي/الإنجليزي من Vision،
    #    فيبحث النص بكل المرادفات ويغطي الفهرسة العربية والإنجليزية معاً.
    lens_future = None
    if LENS_PARALLEL_WITH_VISION and ENABLE_GOOGLE_LENS and SERPAPI_API_KEY and PUBLIC_BASE_URL:
        lens_future = LENS_POOL.submit(_run_with_market, market, google_lens_lookup, b64, mime, lang, caption)

    vision_name = identify_product_with_retry(b64, mime, lang)
    force_fashion_lens = is_fashion_identity(vision_name, caption)
    use_lens, route_reason = lens_routing_decision(vision_name, caption)
    use_lens = force_fashion_lens or use_lens

    lens = {"aliases": [], "matches": [], "query": ""}
    if use_lens:
        if lens_future is not None:
            try:
                lens = lens_future.result(timeout=150) or lens
            except Exception as e:
                print(f"LENS PARALLEL ERR: {e}")
        else:
            lens = google_lens_lookup(b64, mime, lang, caption or vision_name)
    elif lens_future is not None:
        # هذا الفرع لا يعمل عادة في v67 إلا إذا عُطّل Lens من الإعدادات.
        lens_future.cancel()

    if lens.get("matches"):
        lens = rerank_lens_context_with_vision(lens, vision_name)

    active_lens = None
    identity_source = "VISION"
    combined_name = vision_name
    lens_title = ((lens.get("chosen") or {}).get("title") or lens.get("query") or "").strip()

    print(f"SMART ROUTER: vision={vision_name!r} use_lens={use_lens} force_fashion={force_fashion_lens} reason={route_reason}")
    if use_lens:
        if force_fashion_lens and lens_title:
            # Exact design/pattern matters in fashion. Never downgrade to the generic Vision label.
            lens["force_lens_only"] = True
            combined_name = " | ".join(fuse_identity_aliases(lens_title, "", lens.get("aliases")))
            active_lens = lens
            identity_source = "LENS_FASHION_FORCED"
            print(f"FASHION LENS FORCED: {lens_title}")
        elif lens_title and vision_name:
            if identity_candidates_agree(vision_name, lens_title):
                # الاتفاق = أقوى حالة: نبحث بعنوان Lens الدقيق + اسمي Vision العربي والإنجليزي معاً.
                combined_name = " | ".join(fuse_identity_aliases(lens_title, vision_name))
                active_lens = lens
                identity_source = "VISION+LENS_AGREE_FUSED"
                print("IDENTITY JUDGE SKIPPED: candidates already agree -> fused aliases")
            else:
                judged_name, active_lens, identity_source = choose_image_identity(
                    b64, mime, lens, vision_name
                )
                if active_lens:
                    # حتى بعد فوز Lens، مرادفات Vision تبقى في البحث النصي لتغطية الفهرسة العربية.
                    combined_name = " | ".join(fuse_identity_aliases(judged_name, vision_name))
                else:
                    combined_name = judged_name
        elif lens_title:
            combined_name = " | ".join(fuse_identity_aliases(lens_title, "", lens.get("aliases")))
            active_lens, identity_source = lens, "LENS_ONLY"
        else:
            combined_name, active_lens, identity_source = vision_name, None, "VISION_LENS_EMPTY"
    else:
        print("GOOGLE LENS SKIPPED BY SMART ROUTER")

    # Fail closed: every image-derived search gets an identity guard. If Lens/OCR disagree
    # or Lens is empty, a merely similar local page is rejected instead of being shown.
    if combined_name and active_lens is None:
        active_lens = strict_identity_context(combined_name, lens)
        identity_source = f"{identity_source}_STRICT_GUARD"

    print(f"FINAL IMAGE IDENTITY [{identity_source}]: {combined_name}")

    if combined_name and caption:
        request_query = f"{caption} — {combined_name}"
        prompt_text = (
            f"هوية المنتج المعتمدة: {combined_name}\n"
            f"طلب المستخدم: {caption}\n"
            "ابحث عن نفس المنتج فقط. لا توسع البحث إلى منتج يشاركه المكون أو اللون أو الفئة. "
            f"{LANG_INSTR[lang]}"
        )
        txt,urls=search_product(request_query, lang, prompt_text=prompt_text, lens_context=active_lens)
        query = request_query
    elif combined_name:
        txt,urls=search_product(combined_name, lang, lens_context=active_lens)
        query = combined_name
    else:
        txt, urls = "", {}
        query = caption

    if query:
        LAST_SEARCH[from_number] = {"product": query}
    if not txt or not extract_store_offers(txt):
        if txt and (is_service_answer(txt) or is_informational_answer(txt)):
            send_product_result(from_number, txt, urls, bot_id, lang, query)
            return
        if query:
            # حتى بدون نتائج Lens، البحث العالمي والبدائل يعملان نصياً بالاسم المحدد.
            _store_pending_global(from_number, bot_id, lang, query, active_lens, prompt_text if (combined_name and caption) else None)
            send_not_found_choice(from_number, bot_id, lang)
        else:
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
    # MARKET_CTX يضيع داخل WORKERS؛ بدون الغلاف يبحث للسلة كلها في الدولة الافتراضية.
    market = market_for_user(from_number)
    results = list(WORKERS.map(lambda p: (p, *_run_with_market(market, search_product, p, lang)), products))
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
    activate_market(from_number)
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


# ---- فهم نية المستخدم من الجمل الكاملة --------------------------------------
# المشكلة: "السلام عليكم\nمعجون ضد الصراصير عزكم الله وين أحصله\nمع الشكر"
# كانت تُقص على الأسطر وتتحول إلى «3 منتجات» وهمية. الحل ثلاث طبقات:
#   1) بدون تكلفة: اسم منتج قصير مباشر يمر كما هو (السلوك القديم محفوظ).
#   2) بدون تكلفة: منظف تحيات/أدعية/شكر بالـ regex يستخرج المنتج من الجملة.
#   3) نموذج Gemini السريع (بدون بحث، رخيص) للجمل المعقدة، يرجع JSON بالنية والمنتجات.

GREETING_ONLY_FORMS = {
    "السلامعليكم", "سلامعليكم", "السلامعليكمورحمهاللهوبركاته", "السلامعليكمورحمهالله",
    "هلا", "هلاوالله", "اهلين", "اهلا", "اهلاوسهلا", "مرحبا", "مراحب", "حياكم", "حياكالله",
    "صباحالخير", "صباحالنور", "مساءالخير", "مساءالنور", "شلونكم", "شخباركم", "شلونك", "شخبارك",
    "hi", "hello", "hey", "goodmorning", "goodevening", "salam", "assalamualaikum", "hii", "helloo",
}
THANKS_ONLY_FORMS = {
    "شكرا", "شكرًا", "شكرالك", "شكرالكم", "مشكور", "مشكورين", "تسلم", "تسلمون", "يعطيكالعافيه",
    "يعطيكمالعافيه", "جزاكاللهخير", "جزاكماللهخير", "اللهيعطيكالعافيه", "ماقصرت", "ماقصرتوا",
    "thanks", "thankyou", "thx", "thanku", "ty", "shukran",
}
CONVERSATIONAL_HINTS = (
    "السلام", "عليكم", "صباح", "مساء", "هلا", "مرحبا", "حياك", "لو سمحت", "لوسمحت",
    "شلون", "شخبار", "عساك", "عساكم", "كيفك", "كيف الحال", "اخبارك",
    "عزكم الله", "اعزكم الله", "أعزكم الله", "اكرمكم", "أكرمكم", "حشاكم", "بلا مواخذه", "بلا مؤاخذة",
    "شكرا", "مشكور", "تسلم", "يعطيك", "جزاك", "ما قصرت",
    "وين", "أين", "اين", "احصل", "أحصل", "القى", "ألقى", "الاقي", "ألاقي",
    "ابي", "أبي", "ابغى", "أبغى", "اريد", "أريد", "محتاج", "ودي", "تكفى", "تكفون",
    "ممكن", "عندكم", "عندك", "بكم", "كم سعر", "وش سعر", "شكم", "دلوني", "دلني",
    "ساعدني", "ساعدوني", "ابحث لي", "دور لي", "دورلي", "اشتري", "أشتري",
    "please", "where", "can i", "could you", "i need", "i want", "looking for",
    "how much", "help me", "find me", "thanks", "thank", "how are you", "good morning", "good evening",
)

PLEASANTRY_PATTERNS = [
    r"السلام عليكم(?:\s*ورحمة الله(?:\s*وبركاته)?)?", r"و?عليكم السلام(?:\s*ورحمة الله(?:\s*وبركاته)?)?",
    r"صباح الخير", r"صباح النور", r"مساء الخير", r"مساء النور",
    r"هلا(?:\s*والله)?", r"ا?هلا(?:\s*وسهلا)?", r"مرحبا", r"حياكم?(?:\s*الله)?",
    r"شلونك(?:م)?", r"شخبارك(?:م)?",
    r"[أا]?عزكم الله", r"[أا]كرمكم الله", r"حشاكم", r"بلا م[ؤو]اخذة?ه?",
    r"مع الشكر(?:\s*الجزيل)?", r"و?شكرا(?:\s*جزيلا)?(?:\s*لكم?)?", r"مشكورين?", r"تسلمون?",
    r"يعطيكم?\s*العافيه?ة?", r"جزاكم?\s*الله\s*خيرا?", r"الله يخليكم?", r"ما قصرتو?ا?",
    r"لو سمحتو?ا?", r"من فضلكم?", r"تكفون", r"تكفى", r"ممكن", r"ارجوكم?", r"أرجوكم?", r"رجاء",
    r"وين\s*[أا]?حصله?ا?", r"وين\s*[أا]?لقاه?ا?", r"وين\s*[أا]لاقيه?ا?", r"وين\s*موجوده?",
    r"[أا]ين\s*[أا]جده?ا?", r"[أا]بي\s*[أا]عرف\s*وين", r"دلوني\s*عليه?ا?", r"دلني\s*عليه?ا?",
    r"[أا]بي\s*[أا]شتري", r"[أا]بغى\s*[أا]شتري", r"[أا]ريد\s*شراء", r"[أا]ريد", r"[أا]بغى", r"[أا]بي", r"محتاجه?",
    r"دور\s*لي", r"ابحثو?ا?\s*لي", r"ساعدو?ني",
    r"\bhi\b", r"\bhello\b", r"\bhey\b", r"\bplease\b", r"\bthanks?(?:\s*you)?\b", r"\bthank\s*you\b",
    r"where\s*(?:can|do)\s*i\s*(?:find|get|buy)\s*(?:it|this)?", r"i\s*(?:need|want)", r"looking\s*for",
    r"can\s*you\s*(?:find|get)\s*me", r"help\s*me\s*find",
]
_PLEASANTRY_RE = re.compile("|".join(PLEASANTRY_PATTERNS), flags=re.IGNORECASE)

INTENT_PARSE_SYSTEM = """أنت محلل طلبات لبوت تسوق على واتساب. المستخدم يكتب أحياناً جملة كاملة فيها تحية ودعاء وشكر مع طلبه.
مهمتك استخراج المطلوب الحقيقي فقط.
أرجع JSON فقط بدون أي شرح وبدون Markdown:
{"intent":"search|service|greeting|thanks|chat","products":["اسم المنتج نظيفاً"]}

قواعد إلزامية:
- "search": المستخدم يريد منتجاً. احذف التحية والدعاء (مثل: عزكم الله، أكرمكم الله، حشاكم) والشكر وعبارات مثل (وين أحصله، أبي أشتري، دلوني). أبقِ اسم المنتج وصفاته فقط.
- المنتج الواحد = عنصر واحد في products حتى لو كانت الرسالة على عدة أسطر. لا تقسم الجملة الواحدة أبداً.
- عدة منتجات مختلفة فعلاً (مفصولة بفواصل أو "و") = عدة عناصر.
- "service": طلب فني/سباك/كهربائي/تصليح... ضع وصف الخدمة والمنطقة في products.
- "greeting": تحية فقط بلا أي طلب. products فارغة.
- "thanks": شكر فقط بلا طلب جديد. products فارغة.
- "chat": كلام عام أو سؤال غير متعلق بمنتج. products فارغة.
مثال: "السلام عليكم معجون ضد الصراصير عزكم الله وين أحصله مع الشكر"
الجواب: {"intent":"search","products":["معجون ضد الصراصير"]}"""

def strip_pleasantries(text):
    """يشيل التحيات والأدعية والشكر وعبارات الطلب، ويرجع المتبقي كسطر واحد."""
    cleaned = _PLEASANTRY_RE.sub(" ", text or "")
    cleaned = re.sub(r"[،,.!؟?]+", " ", cleaned)
    return " ".join(cleaned.split()).strip()

def parse_user_intent(user_text, lang):
    """يفهم الجملة الكاملة ويرجع {"intent": ..., "products": [...]}."""
    text = (user_text or "").strip()
    compact = re.sub(r"[^\w\u0600-\u06FF]", "", normalize_ar(text))

    if compact in GREETING_ONLY_FORMS:
        return {"intent": "greeting", "products": []}
    if compact in THANKS_ONLY_FORMS:
        return {"intent": "thanks", "products": []}

    norm = normalize_ar(text)
    conversational = ("؟" in text or "?" in text or
                      any(normalize_ar(h) in norm for h in CONVERSATIONAL_HINTS))

    # الطبقة 1 (بدون تكلفة): اسم منتج مباشر قصير — نفس سلوك البوت القديم بالضبط.
    if not conversational and len(text.split()) <= 7:
        return {"intent": "search", "products": extract_products(text)}

    # الطبقة 3: جملة محادثة — نموذج سريع رخيص يستخرج النية والمنتجات.
    raw, _ = call_gemini([{"text": text}], system=INTENT_PARSE_SYSTEM, use_search=False)
    try:
        data = json.loads(re.search(r"\{.*\}", raw or "", flags=re.S).group(0))
        intent = str(data.get("intent") or "search").lower().strip()
        products = [str(p).strip() for p in (data.get("products") or []) if str(p).strip()]
        if intent in ("greeting", "thanks", "chat") and not products:
            print(f"INTENT PARSED: {intent} (no products)")
            return {"intent": intent, "products": []}
        if intent in ("search", "service") and products:
            print(f"INTENT PARSED: {intent} products={products}")
            return {"intent": "search", "products": products[:6]}
    except Exception:
        print(f"INTENT PARSE FAIL: {raw!r}")

    # الطبقة 2 (احتياط بدون تكلفة): تنظيف regex ثم اعتبار المتبقي منتجاً واحداً —
    # لا نقسم على الأسطر أبداً لأن الجملة المحادثية جملة واحدة.
    cleaned = strip_pleasantries(text)
    if cleaned and len(cleaned) >= 3:
        print(f"INTENT REGEX FALLBACK: {cleaned!r}")
        return {"intent": "search", "products": [cleaned]}
    # ما بقي شيء بعد التنظيف = كانت مجاملات فقط.
    return {"intent": "greeting" if not compact.strip() or any(g in compact for g in ("سلام", "هلا", "مرحبا")) else "chat", "products": []}


def process_text_message(message,bot_id,onboarding_checked=False):
    from_number=message["from"]
    load_user_preferences(from_number)
    if not onboarding_checked:
        if from_number not in USER_LANG:
            cache_pending_message(from_number, message, bot_id); send_language_choice(from_number, bot_id); return
        if not location_is_valid(from_number):
            cache_pending_message(from_number, message, bot_id); send_location_request(from_number, bot_id, USER_LANG.get(from_number,"ar"), bool(USER_LOCATION_TS.get(from_number,0))); return
    activate_market(from_number); user_text=message["text"]["body"]
    cmd=re.sub(r"[^\w\u0600-\u06FF]","",user_text.strip().lower())
    if cmd in ("لغة","اللغة","غيراللغة","language","lang","changelanguage"):
        send_language_choice(from_number, bot_id); return
    detected=detect_lang(user_text)
    if detected and USER_LANG.get(from_number) != detected:
        USER_LANG[from_number]=detected
        save_user_preferences(from_number)
    lang=USER_LANG.get(from_number,"ar")
    if is_map_command(user_text):
        send_last_search_map(from_number, bot_id, lang)
        return
    pend=PENDING_IMAGES.pop(from_number,None)
    if pend and pend["images"]:
        # الرسالة النصية بعد صورة معلقة تُعامل كوصف للصورة نفسها،
        # ولا نكمل لمعالجتها كبحث نصي مستقل (كان يسبب بحثين وردّين مزدوجين).
        if len(pend["images"])==1:
            img_msg = pend["images"][0]
            img = img_msg.setdefault("image", {})
            if not (img.get("caption") or "").strip():
                img["caption"] = user_text.strip()
            process_single_image(img_msg, pend["bot_id"], lang)
        else:
            process_multi_images(pend["images"], from_number, pend["bot_id"], lang)
        return
    parsed = parse_user_intent(user_text, lang)
    intent = parsed.get("intent", "search")
    if intent == "greeting":
        send_whatsapp_text(from_number, T(lang, "welcome_reply"), bot_id)
        return
    if intent == "thanks":
        send_whatsapp_text(from_number, T(lang, "thanks_reply"), bot_id)
        return
    if intent == "chat":
        # كلام عام بلا منتج: نرحب ونوجه بدل ما نبحث عن جملة عشوائية.
        send_whatsapp_text(from_number, T(lang, "welcome_reply"), bot_id)
        return
    products = [p for p in (parsed.get("products") or []) if p.strip()] or extract_products(user_text)
    if len(products)==1:
        send_whatsapp_text(from_number,T(lang,"searching",q=products[0]),bot_id)
        txt,urls=search_product(products[0], lang)
        LAST_SEARCH[from_number] = {"product": products[0]}
        if not txt or (not extract_store_offers(txt) and not is_service_answer(txt) and not is_informational_answer(txt)):
            # ما لقينا المنتج بالضبط محلياً: نعرض الخيارات الثلاثة بدل رسالة الاعتذار وحدها.
            _store_pending_global(from_number, bot_id, lang, products[0], None, None)
            send_not_found_choice(from_number, bot_id, lang)
            return
        result_type = send_product_result(from_number, txt, urls, bot_id, lang, products[0])
        if result_type == "none":
            # كانت هناك عروض لكن كل روابطها غير مباشرة؛ نفس الخيارات تنفع هنا أيضاً.
            _store_pending_global(from_number, bot_id, lang, products[0], None, None)
            send_not_found_choice(from_number, bot_id, lang)
        elif result_type == "service" or (result_type == "product" and AUTO_SEND_PRODUCT_MAPS):
            send_maps_button(from_number, products[0], bot_id, lang)
    else:
        send_whatsapp_text(from_number,T(lang,"multi_text",c=len(products)),bot_id)
        process_cart(products, from_number, bot_id, lang)

def process_location_message(message, bot_id):
    from_number = message["from"]
    load_user_preferences(from_number)
    lat = message["location"]["latitude"]; lng = message["location"]["longitude"]
    geo = reverse_geocode_market(lat, lng)
    market = market_for_user(from_number)
    market.update(geo)
    market.update({"lat":lat,"lng":lng})
    USER_MARKET[from_number]=market
    USER_LOCATION_TS[from_number]=time.time()
    MARKET_CTX.value=market
    save_user_preferences(from_number)
    print(f"USER MARKET UPDATED: {from_number} -> {market}; valid_for_hours={LOCATION_TTL_SECONDS/3600:.0f}")
    lang = USER_LANG.get(from_number, "ar")
    city = market.get("city") or market.get("country_name") or market.get("country", "").upper()
    msg = f"تم حفظ موقعك: {city} ✅\nراح أطلب تحديثه بعد 3 أيام." if lang == "ar" else f"Location saved: {city} ✅\nI’ll ask you to update it again after 3 days."
    send_whatsapp_text(from_number, msg, bot_id)
    route_pending_after_location(from_number)

@app.get("/")
async def health(): return {"status":"v67 EXACT VISUAL IDENTITY", "build":BUILD_ID, "location_ttl_hours":LOCATION_TTL_SECONDS//3600}
