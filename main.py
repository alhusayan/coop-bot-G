# -*- coding: utf-8 -*-
import os, re, time, base64, requests, json, asyncio, urllib.parse, hashlib, sqlite3, threading
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor, wait
from fastapi import FastAPI, Request, Response, BackgroundTasks
from bs4 import BeautifulSoup

app = FastAPI()
BUILD_ID = "v80-text-google-shopping-lens-format-20260818"
print("=" * 70)
print(f"STARTING COOP BOT BUILD: {BUILD_ID}")
print("IMAGE/TEXT -> FLAGS + CLEAR LOCAL PRICES + LOCAL/US/CHINA")
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
# v73: HTTP passes الخاصة بـ Lens لها pool مستقل حتى لا يحصل deadlock عندما google_lens_lookup يعمل داخل LENS_POOL.
LENS_HTTP_POOL = ThreadPoolExecutor(max_workers=12)
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
# v68: قائمة أطول — 5 نتائج افتراضياً (تُضبط من MAX_STORES في Environment Variables).
MAX_STORES = int(os.environ.get("MAX_STORES", "5"))
MAX_URLS_MERGED = int(os.environ.get("MAX_URLS_MERGED", "8"))
ENABLE_SEARCH_RETRY = env_bool("ENABLE_SEARCH_RETRY", True)
MAX_SEARCH_ATTEMPTS = max(2, int(os.environ.get("MAX_SEARCH_ATTEMPTS", "3")))
MAX_IDENTIFY_ATTEMPTS = max(2, int(os.environ.get("MAX_IDENTIFY_ATTEMPTS", "3")))
AUTO_SEND_PRODUCT_MAPS = env_bool("AUTO_SEND_PRODUCT_MAPS", False)
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
# v72: وضع اللينز المباشر — الصورة تروح لـ Google Lens ثم تُفلتر وتُرتب: محلي -> أمريكا -> الصين فقط.
# بدون تحليل Vision ولا حكم هوية ولا طبقات بحث. أطفئه بـ LENS_DIRECT_MODE=false
# لإرجاع المسار الذكي الكامل. عند عدم وجود نتائج، البوت يرجع تلقائياً للمسار الكامل.
LENS_DIRECT_MODE = env_bool("LENS_DIRECT_MODE", True)
LENS_DIRECT_MAX_LINES = max(3, int(os.environ.get("LENS_DIRECT_MAX_LINES", "8")))
# v76: الحدود القصوى مستقلة وليست حصصاً إلزامية.
# المحلي حتى 5، الولايات المتحدة حتى 4، الصين حتى 4.
# إذا كان سوق ما فيه نتائج أقل نعرض الموجود فقط ولا نملأ العدد إجبارياً.
LENS_DIRECT_LOCAL_MAX = max(0, int(os.environ.get("LENS_DIRECT_LOCAL_MAX", "5")))
LENS_DIRECT_US_MAX = max(0, int(os.environ.get("LENS_DIRECT_US_MAX", "4")))
LENS_DIRECT_CN_MAX = max(0, int(os.environ.get("LENS_DIRECT_CN_MAX", "4")))
LENS_DIRECT_MAX_CTA = max(1, int(os.environ.get("LENS_DIRECT_MAX_CTA", str(LENS_DIRECT_LOCAL_MAX + LENS_DIRECT_US_MAX + LENS_DIRECT_CN_MAX))))
LENS_PRIMARY_MODE = env_bool("LENS_PRIMARY_MODE", True)
LENS_PRIMARY_EXCEPT_TEXT_HEAVY = env_bool("LENS_PRIMARY_EXCEPT_TEXT_HEAVY", True)
# قوة Lens الحقيقية تأتي من تعدد التمريرات: products ثم all (visual+exact) ثم بحث واسع بلا قيد دولة.
ENABLE_LENS_WIDE_FALLBACK = env_bool("ENABLE_LENS_WIDE_FALLBACK", True)
LENS_MIN_MATCHES = max(3, int(os.environ.get("LENS_MIN_MATCHES", "6")))
# تشغيل Vision و Lens بالتوازي: أسرع وأدق دمج. عطّله إذا تبي توفر كريدت SerpApi للعبوات النصية.
LENS_PARALLEL_WITH_VISION = env_bool("LENS_PARALLEL_WITH_VISION", True)
LENS_RESULT_LIMIT = max(12, int(os.environ.get("LENS_RESULT_LIMIT", "40")))
# v73: حد زمني واضح للينز. تمريرات البلدان تعمل بالتوازي، وليس واحدة وراء الثانية.
LENS_HTTP_TIMEOUT_SECONDS = max(6, int(os.environ.get("LENS_HTTP_TIMEOUT_SECONDS", "15")))
LENS_TOTAL_TIMEOUT_SECONDS = max(8, int(os.environ.get("LENS_TOTAL_TIMEOUT_SECONDS", "22")))
LENS_IMAGE_TTL = max(120, int(os.environ.get("LENS_IMAGE_TTL_SECONDS", "600")))
LENS_IMAGE_STORE = {}
LENS_IMAGE_LOCK = threading.Lock()

# ---- Google Shopping عبر SerpApi (v69) ---------------------------------------
# طبقة أسعار منظمة: google_shopping يجيب بطاقات المنتج مع immersive_product_page_token،
# ثم google_immersive_product يفتح بطاقة Google ويرجع قائمة المتاجر بروابط مباشرة وأسعار.
# هذا يدخل المتاجر الصغيرة المفهرسة في Google Merchant (مثل Pro Sports وTigro و3RoodQ8)
# حتى لو ما ذكرها Gemini أبداً.
ENABLE_GOOGLE_SHOPPING = env_bool("ENABLE_GOOGLE_SHOPPING", True)
SHOPPING_RESULT_LIMIT = max(5, int(os.environ.get("SHOPPING_RESULT_LIMIT", "20")))
# كل استدعاء Immersive يستهلك كريدت SerpApi؛ نحدد سقفاً لكل بحث.
IMMERSIVE_LOOKUPS_MAX = max(0, int(os.environ.get("IMMERSIVE_LOOKUPS_MAX", "3")))
IMMERSIVE_MORE_STORES = env_bool("IMMERSIVE_MORE_STORES", True)
SHOPPING_POOL = ThreadPoolExecutor(max_workers=4)
TEXT_SHOPPING_POOL = ThreadPoolExecutor(max_workers=8)


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
    return (
        f"\nIMPORTANT CURRENT USER MARKET: {place} (country code {m['country']}). "
        "For product/store searches use exactly this geographic priority: "
        f"(1) stores in {place}, then (2) United States stores, then (3) China stores. "
        "Reject stores from every other country. Do not require US/China stores to deliver locally. "
        f"Local results should use {currency}; foreign prices may be returned in their original currency because the application converts them. "
        "This LOCAL -> US -> CHINA ordering is more important than price: never place a cheaper US/China offer above a local one. "
        "Ignore any older Kuwait-only or local-only instruction when it conflicts with this rule.\n"
    )

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
    f"google_shopping={ENABLE_GOOGLE_SHOPPING} immersive_max={IMMERSIVE_LOOKUPS_MAX} "
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

# ---- مقارنة نفس المواصفات فقط ------------------------------------------------
# عبوة 250 مل أرخص من لتر لأنها أصغر، وآيفون 128GB أرخص من 256GB لأنه سعة أقل —
# مو لأنه عرض أفضل. نستخرج الحجم/الوزن/السعة من عنوان كل منتج (مع مضاعِف العبوات
# مثل 6×185مل) ونرفض أي عرض مواصفته تختلف عن المرجع.
SIZE_RE = re.compile(
    r"(?:(\d+(?:[.,]\d+)?)\s*[x×*]\s*)?(\d+(?:[.,]\d+)?)\s*"
    r"(مل|ملي لتر|ملل|ml|لتر|ليتر|l|ltr|liter|litre|كجم|كغم|كغ|كيلو جرام|كيلو غرام|كيلو|kg|جرام|غرام|جم|غم|gm|gr|g"
    r"|تيرا بايت|تيرابايت|تيرا|tb|جيجا بايت|جيجابايت|جيجا|غيغا|قيقا|gb)\b",
    re.I,
)
_VOL_UNITS = {"مل", "ملي لتر", "ملل", "ml"}
_VOL_BIG_UNITS = {"لتر", "ليتر", "l", "ltr", "liter", "litre"}
_WT_BIG_UNITS = {"كجم", "كغم", "كغ", "كيلو جرام", "كيلو غرام", "كيلو", "kg"}
_CAP_UNITS = {"جيجا بايت", "جيجابايت", "جيجا", "غيغا", "قيقا", "gb"}
_CAP_BIG_UNITS = {"تيرا بايت", "تيرابايت", "تيرا", "tb"}

def extract_pack_size(text):
    """يعيد (نوع, الكمية الكلية بالمل أو الجرام أو الجيجا) أو None إذا ما فيه حجم مذكور."""
    t = normalize_ar(str(text or ""))
    for m in SIZE_RE.finditer(t):
        try:
            count = float((m.group(1) or "1").replace(",", "."))
            qty = float(m.group(2).replace(",", "."))
        except Exception:
            continue
        unit = m.group(3).lower()
        if unit in _CAP_BIG_UNITS:
            cls, base = "cap", qty * 1000.0
        elif unit in _CAP_UNITS:
            cls, base = "cap", qty
        elif unit in _VOL_BIG_UNITS:
            cls, base = "vol", qty * 1000.0
        elif unit in _VOL_UNITS:
            cls, base = "vol", qty
        elif unit in _WT_BIG_UNITS:
            cls, base = "wt", qty * 1000.0
        else:
            cls, base = "wt", qty
        total = count * base
        if total > 0:
            return (cls, total)
    return None

def format_pack_size(sig):
    if not sig:
        return ""
    cls, total = sig
    if cls == "cap":
        return f"{total/1000:g} تيرا" if total >= 1000 else f"{int(total)} جيجا"
    if cls == "vol":
        return f"{total/1000:g} لتر" if total >= 1000 else f"{int(total)} مل"
    return f"{total/1000:g} كجم" if total >= 1000 else f"{int(total)} جم"

def sizes_compatible(a, b):
    """None = حجم غير معروف فنسمح به. اختلاف يتجاوز 15% = منتج مختلف."""
    if not a or not b:
        return True
    if a[0] != b[0]:
        return False
    lo, hi = sorted((a[1], b[1]))
    return hi <= lo * 1.15

def filter_same_size(offers_dict, reference_text):
    """يبقي فقط العروض المطابقة لحجم المرجع (اسم المنتج المحدد)، أو لحجم الأغلبية إذا المرجع بلا حجم.

    العروض التي لا يظهر حجم في عنوانها تمر (لا نستطيع الحكم عليها)، لكن أي حجم
    صريح مختلف يُرفض — عبوة أصغر أو سعة أقل ليست سعراً أرخص لنفس المنتج.
    """
    if not offers_dict:
        return offers_dict
    ref = extract_pack_size(reference_text)
    sized = {n: extract_pack_size(str(i.get("title", ""))) for n, i in offers_dict.items()}
    if not ref:
        detected = [s for s in sized.values() if s]
        if len(detected) >= 2:
            counts = {}
            for s in detected:
                counts[s] = counts.get(s, 0) + 1
            ref = max(counts, key=counts.get)
    if not ref:
        return offers_dict
    kept = {}
    for name, info in offers_dict.items():
        if sizes_compatible(ref, sized.get(name)):
            kept[name] = info
        else:
            print(f"SIZE MISMATCH REJECT: {name} -> {info.get('title','')} (want~{format_pack_size(ref)}, got {format_pack_size(sized.get(name))})")
    return kept


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
    return hashlib.sha256(f"v72|{market}|{norm}|{lang}".encode()).hexdigest()

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

IDENTIFY_SYSTEM = """أنت خبير تعرف على المنتجات من الصور.
أرجع دائماً اسمين قابلين للبحث بهذا الشكل فقط:
[الاسم التجاري بالعربية] | [commercial product name in English]
ضع البراند ورقم الموديل إن ظهر. إذا ظهر حجم أو وزن أو سعة على العبوة (مثل 1 لتر، 500 مل، 250 جم، 256GB) أدخله في الاسمين، فهو جزء من هوية المنتج.
استنتج نوع المنتج من الشعار والشكل والنص الظاهر.
لا ترفض التحديد لمجرد أن الصورة غير كاملة؛ أعطِ أقرب اسم تجاري مفيد للبحث.
مثال: حليب المراعي كامل الدسم 1 لتر | Almarai Full Fat Milk 1L
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
        "lens_header": "🔍 هذا اللي طلع من Google عن صورتك:",
        "lens_none": "Google ما رجّع نتائج للصورة 😅 أكمل البحث بطريقتي...",
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
        "lens_header": "🔍 Here's what Google returned for your photo:",
        "lens_none": "Google returned no results for the photo 😅 continuing with my own search...",
    },
}

LANG_INSTR = {
    "ar": "رد باللغة العربية فقط حتى لو كان اسم البحث بالإنجليزية: اكتب سطر 📦 ووصف المنتج بالعربية، مع إبقاء اسم البراند والموديل اللاتيني كما هو (مثل: كرة سلة Spalding NBA). أسماء المتاجر تُكتب بأشهر صيغة متداولة لها.",
    "en": "Respond ONLY in English. Keep the exact same response format and emojis, but translate all labels to English — including writing (Phone: NUMBER) instead of (هاتف: رقم). Keep prices in the user's local currency.",
}

def T(lang, key, **kw):
    return MSG.get(lang, MSG["ar"])[key].format(**kw) if kw else MSG.get(lang, MSG["ar"])[key]

def detect_lang(text):
    if re.search(r"[\u0600-\u06FF]", text or ""): return "ar"
    if re.search(r"[A-Za-z]", text or ""): return "en"
    return None

SYSTEM_PROMPT = """
أنت مساعد تسوق عالمي يعتمد موقع المستخدم الحالي. استخدم بحث Google فعلياً للأسعار الحالية، ورتب الأسواق دائماً: بلد المستخدم أولاً، ثم الولايات المتحدة، ثم الصين فقط.

أولاً حدد نوع الطلب:

【الحالة 1】منتج محدد بعلامة تجارية واضحة (مثل: آيفون 15 برو، بيبسي، ساعة أبل الترا، بلايستيشن 5):
قارن الأسعار لكن رتب جغرافياً أولاً: بلد المستخدم، ثم الولايات المتحدة، ثم الصين فقط. داخل كل سوق رتب من الأرخص إلى الأغلى، ورد بهذا الشكل فقط:
📦 [اسم المنتج]

✅ [المتجر الأرخص] — [السعر] د.ك
• [المتجر الثاني] — [السعر] د.ك
• [المتجر الثالث] — [السعر] د.ك
• [المتجر الرابع] — [السعر] د.ك
• [المتجر الخامس] — [السعر] د.ك

قاعدة المتاجر: كل فئة لها متاجرها المتخصصة القوية وهي تتقدم على المنصات العامة (نون، طلبات، لولو، كارفور):
- الرياضة واللياقة: Pro Sports (prosportskw.com)، Intersport، Decathlon، Sun & Sand Sports
- الإلكترونيات وألعاب الفيديو: Xcite، Eureka، Best Al-Yousifi، Blink، Jarir، 3RoodQ8 (3roodq8.com)
- ألعاب الأطفال: Tigro (tigro.app)، Toys R Us، 3RoodQ8
- التموينات: جمعية دوت كوم، لولو، كارفور
ابحث في متاجر الفئة المتخصصة أولاً ثم المنصات العامة، ولا تحصر البحث في أي قائمة: اقبل أي متجر محلي يبيع المنتج بسعر موثق ورابط صفحة منتج مباشر، حتى لو لم يكن متجراً مشهوراً.

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
- قارن نفس المواصفات فقط: نفس الحجم/السعة/الوزن، ونفس اللون إذا كان اللون يغيّر السعر. اذكر المواصفة بجانب كل سعر (مثل: 256GB، 1 لتر، أحمر) ولا تدخل نسخة مختلفة المواصفات في نفس المقارنة.
- اعرض المتاجر بهذا الترتيب الإجباري فقط: بلد المستخدم الحالي أولاً، ثم الولايات المتحدة، ثم الصين. احذف أي دولة أخرى. داخل كل سوق رتب من الأرخص إلى الأغلى.
- ممنوع أن يكون الرد عبارة عن أسماء متاجر مع كلمة متوفر فقط؛ كل سطر عرض يجب أن يحتوي سعراً رقمياً.
- رابط كل متجر يجب أن يكون رابط صفحة منتج مباشر (صفحة فيها منتج واحد وسعر واحد). ممنوع روابط الصفحة الرئيسية أو /search أو /category
- لا تخترع سعراً، انسخ السعر كما يظهر في نتيجة البحث اليوم.
- حاول تجيب حتى 5 متاجر مختلفة، وإذا ما لقيت اذكر الموجود ولا تخترع.

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
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=(5, LENS_HTTP_TIMEOUT_SECONDS))
        if r.status_code >= 400:
            print(f"GOOGLE LENS HTTP {r.status_code} type={lens_type or 'all'} country={country or '-'}: {r.text[:300]}")
            return []
        data = r.json()
        if data.get("error"):
            print(f"GOOGLE LENS ERROR type={lens_type or 'all'} country={country or '-'}: {data.get('error')}")
            return []
        items, seen = [], set()
        _collect_lens_items(data, items, seen)
        # v75: نحفظ البلد الذي جاءت منه تمريرة Lens للمراقبة/التشخيص.
        for item in items:
            item["_lens_country"] = (country or "").lower()
        print(f"GOOGLE LENS PASS type={lens_type or 'all'} country={country or '-'} auto_crop={auto_crop} -> {len(items)} items")
        return items
    except Exception as e:
        print(f"GOOGLE LENS PASS EXCEPTION type={lens_type or 'all'}: {e}")
        return []


def _china_store_search_fallback(base_query, limit=8):
    """بحث نصي احتياطي مخصص للصين عندما لا يعيد Lens أي متجر صيني.

    لا يغيّر لغة واجهة المستخدم ولا يترجم استعلام البحث. نستخدم الاسم الإنجليزي/عنوان Lens
    كما هو، ونقيّد كل استعلام بدومين متجر صيني معروف. لا نضيف إلا روابط مباشرة مصنفة صينية.
    """
    if not SERPAPI_API_KEY:
        return []
    q = _shopping_clean_query(base_query or "")
    if not q:
        return []
    targets = [
        ("AliExpress", "aliexpress.com"),
        ("Temu", "temu.com"),
        ("Alibaba", "alibaba.com"),
        ("1688", "1688.com"),
        ("Taobao", "taobao.com"),
        ("SHEIN", "shein.com"),
    ]

    def _one(label, domain):
        # Google Shopping أولاً لأنه يعطينا سعراً منظماً غالباً.
        cards = _serpapi_shopping_request(f'{q} site:{domain}', "us", hl="en")
        out = []
        for pos, card in enumerate(cards or [], 1):
            link = (card.get("link") or "").strip()
            if not link:
                continue
            direct = _shopping_direct_url(link) or link
            try:
                host = urllib.parse.urlparse(direct).netloc.lower().replace("www.", "")
            except Exception:
                host = ""
            if not _host_matches_any(host, (domain,)):
                continue
            title = (card.get("title") or "").strip()
            source = (card.get("source") or label).strip() or label
            price_text = str(card.get("price") or "").strip()
            price_value = card.get("extracted_price")
            currency = detect_currency_code(price_text, "")
            out.append({
                "title": title or q,
                "link": direct,
                "source": source,
                "position": pos,
                "section": "china_store_fallback",
                "exact": False,
                "thumbnail": (card.get("thumbnail") or "").strip(),
                "image": (card.get("thumbnail") or "").strip(),
                "price": price_text,
                "price_value": price_value,
                "currency": currency,
                "in_stock": None,
                "condition": "",
                "_lens_country": "cn",
                "_china_fallback": True,
            })
        return out

    futures = {
        LENS_HTTP_POOL.submit(_one, label, domain): (label, domain)
        for label, domain in targets
    }
    merged, seen = [], set()
    done, not_done = wait(list(futures), timeout=min(LENS_TOTAL_TIMEOUT_SECONDS, 18))
    for fut in done:
        label, domain = futures[fut]
        try:
            for it in fut.result() or []:
                sig = ((it.get("title") or "").lower(), (it.get("link") or "").lower())
                if sig in seen or not is_china_market_result(it):
                    continue
                seen.add(sig)
                merged.append(it)
                if len(merged) >= limit:
                    break
        except Exception as e:
            print(f"CHINA FALLBACK ERR {label}/{domain}: {e}")
        if len(merged) >= limit:
            break
    for fut in not_done:
        fut.cancel()
    print(f"CHINA STORE FALLBACK: query={q[:70]!r} -> {len(merged)} results")
    return merged[:limit]

def google_lens_lookup(image_b64, mime_type, lang="ar", query_hint="", light=False):
    """تعرف بصري متعدد التمريرات ليقترب من قوة تطبيق Google Lens نفسه.

    light=True (وضع اللينز المباشر v72): يعيد نتائج Lens بدون استدعاء Gemini لوصف الصورة،
    ثم يطبق فلتر وترتيب السوق قبل إرسالها للمستخدم.

    التمريرات بالترتيب (نتوقف بمجرد الحصول على نتائج كافية):
      1) type=products + دولة المستخدم + auto_crop -> بطاقات منتجات فيها أسعار.
      2) type=all + دولة المستخدم + auto_crop      -> visual_matches و exact_matches (التعرف الأقوى).
      3) type=all بدون قيد الدولة وبدون auto_crop   -> أوسع بحث، مثل تطبيق Lens تماماً.
    ثم ندمج النتائج (بدون تكرار) ونختار أفضل عنوان، ونستخرج التوقيع الشكلي من الصورة الأصلية.
    """
    if not ENABLE_GOOGLE_LENS or not SERPAPI_API_KEY or not PUBLIC_BASE_URL:
        print("GOOGLE LENS SKIPPED: missing SERPAPI_API_KEY or PUBLIC_BASE_URL")
        return {"aliases": [], "matches": [], "query": ""}

    public_url = publish_image_for_lens(image_b64, mime_type)
    if not public_url:
        print("GOOGLE LENS SKIPPED: could not publish image")
        return {"aliases": [], "matches": [], "query": ""}

    try:
        user_country = current_market().get("country", DEFAULT_COUNTRY)
        merged, seen = [], set()

        def _merge(new_items):
            for it in new_items:
                sig = (it["title"].lower(), it["link"].lower())
                if sig in seen:
                    continue
                seen.add(sig)
                merged.append(it)

        # v73: بلد المستخدم + أمريكا + الصين فقط، وكل تمريرات Lens تعمل بالتوازي.
        # هذا يمنع 6 طلبات × timeout متتالية (سبب التعليق في v72).
        country_order = []
        for cc in (user_country, "us", "cn"):
            if cc and cc not in country_order:
                country_order.append(cc)
        passes = []
        for cc in country_order:
            passes.extend([("products", cc, True), ("all", cc, True)])

        future_map = {
            LENS_HTTP_POOL.submit(_serpapi_lens_request, public_url, lens_type, country, auto_crop, query_hint):
                (lens_type, country, auto_crop)
            for lens_type, country, auto_crop in passes
        }
        # v75: تمريرة صينية موجهة للمتاجر الصينية المعروفة. country=cn وحده قد
        # يعيد مواقع عالمية عامة؛ هذه التمريرة تزيد فرصة AliExpress/Alibaba/Temu/1688/Taobao/SHEIN.
        cn_hint = (query_hint or "").strip()
        cn_hint = (cn_hint + " site:aliexpress.com OR site:temu.com OR site:alibaba.com OR site:1688.com OR site:taobao.com OR site:shein.com").strip()
        cn_future = LENS_HTTP_POOL.submit(
            _serpapi_lens_request, public_url, "all", "cn", True, cn_hint
        )
        future_map[cn_future] = ("all-cn-stores", "cn", True)
        done, not_done = wait(list(future_map), timeout=LENS_TOTAL_TIMEOUT_SECONDS)
        for fut in done:
            lens_type, country, auto_crop = future_map[fut]
            try:
                _merge(fut.result())
            except Exception as e:
                print(f"GOOGLE LENS FUTURE ERR type={lens_type} country={country}: {e}")
        for fut in not_done:
            lens_type, country, _ = future_map[fut]
            fut.cancel()
            print(f"GOOGLE LENS PASS SKIPPED AFTER TOTAL TIMEOUT type={lens_type} country={country}")
        print(f"GOOGLE LENS PARALLEL DONE completed={len(done)}/{len(future_map)} total_timeout={LENS_TOTAL_TIMEOUT_SECONDS}s")

        # أي دولة غير محلي/أمريكا/الصين تُحذف نهائياً.
        allowed = [m for m in merged if result_market_rank(m) != 99]

        # v77: إذا Lens لم يعطِ أي متجر صيني، نشغّل بحثاً نصياً احتياطياً مستقلاً
        # مقيّداً بمتاجر الصين. نشتق الاستعلام من أفضل عنوان بصري موجود ولا نترجمه.
        if not any(result_market_rank(m) == 2 for m in allowed):
            fallback_query = (query_hint or "").strip()
            if not fallback_query and merged:
                fallback_query = (merged[0].get("title") or "").strip()
            cn_extra = _china_store_search_fallback(fallback_query, limit=max(LENS_DIRECT_CN_MAX * 2, 8))
            if cn_extra:
                existing = {((m.get("title") or "").lower(), (m.get("link") or "").lower()) for m in allowed}
                for m in cn_extra:
                    sig = ((m.get("title") or "").lower(), (m.get("link") or "").lower())
                    if sig not in existing and result_market_rank(m) == 2:
                        allowed.append(m); existing.add(sig)

        # نفرض ترتيب الأسواق قبل جودة Lens.
        allowed.sort(key=lambda m: (
            result_market_rank(m),
            0 if m.get("exact") else 1,
            0 if m.get("section") == "visual_matches" else 1,
            int(m.get("position") or 999),
        ))
        # لا نسمح للنتائج المحلية/الأمريكية أن تملأ LENS_RESULT_LIMIT وتحذف الصين.
        # نحتفظ بعدد كافٍ من كل سوق مستقلاً، ثم يطبق send_lens_direct_results سقف 5/4/4 النهائي.
        keep_caps = {
            0: max(LENS_DIRECT_LOCAL_MAX * 3, LENS_DIRECT_LOCAL_MAX),
            1: max(LENS_DIRECT_US_MAX * 3, LENS_DIRECT_US_MAX),
            2: max(LENS_DIRECT_CN_MAX * 3, LENS_DIRECT_CN_MAX),
        }
        matches = []
        for rank in (0, 1, 2):
            market_rows = [m for m in allowed if result_market_rank(m) == rank]
            matches.extend(market_rows[:keep_caps[rank]])
        matches = matches[:max(LENS_RESULT_LIMIT, sum(keep_caps.values()))]
        if not matches:
            print("GOOGLE LENS: no visual matches after all passes")
            return {"aliases": [], "matches": [], "query": ""}

        # اطبع أول النتائج حتى نعرف فعلياً ماذا أعاد Lens.
        for i, m in enumerate(matches[:5], 1):
            print(f"LENS MATCH {i}: {m.get('title','')} | {m.get('source','')} | section={m.get('section','')} exact={m.get('exact', False)}")

        # نختار أفضل نتيجة ذات عنوان واضح. exact ثم المحلي ثم وجود سعر ثم ترتيب Lens.
        generic = re.compile(r"^(mules?|shoes?|slippers?|sandals?|footwear|بوتيغا فينيتا|bottega veneta)$", re.I)
        ranked = []
        for m in matches:
            title = (m.get("title") or "").strip()
            if not title or generic.match(title):
                continue
            score = 2000 if m.get("exact") else 0
            market_rank = result_market_rank(m)
            score += {0: 3000, 1: 1800, 2: 900}.get(market_rank, -5000)
            if m.get("price") or m.get("price_value") not in (None, ""):
                score += 700
            if m.get("section") == "visual_matches":
                score += 250
            score += max(0, 300 - int(m.get("position") or 99) * 12)
            score += min(len(title), 120) / 10
            if m.get("thumbnail") or m.get("image"):
                score += 10
            ranked.append((score, m))
        chosen = max(ranked, key=lambda x: x[0])[1] if ranked else matches[0]
        chosen_title = (chosen.get("title") or "").strip()

        if light:
            # وضع مباشر: بدون وصف Gemini — النتائج تُسلّم كما رجعت من Google.
            return {
                "aliases": [chosen_title] if chosen_title else [],
                "matches": matches,
                "query": chosen_title,
                "chosen": chosen,
                "signature": {},
            }

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
        "shirt","blouse","top","dress","pajama","pajamas","pyjama","pyjamas",
        "nightwear","sleepwear","set","women's","womens","ملابس","قميص","بيجامه","بيجامة",
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

    # Identity tokens are mandatory. For fashion, one generic overlap is not enough:
    # require either the brand/model token, or two discriminative tokens from Lens.
    desired_tokens = _meaningful_lens_tokens(chosen_title)
    descriptor_tokens = [t for t in desired_tokens if t not in ("bottega", "veneta")]
    matched_tokens = [t for t in descriptor_tokens if t in candidate_hay]
    fashion_words = (
        "shirt","blouse","dress","pajama","pyjama","nightwear","sleepwear","satin",
        "printed","striped","قميص","فستان","بيجامه","بيجامة","ساتان","مخطط"
    )
    is_fashion = any(normalize_ar(w) in chosen_title for w in fashion_words)
    if descriptor_tokens:
        needed = 2 if is_fashion and len(descriptor_tokens) >= 2 else 1
        if len(matched_tokens) < needed:
            print(f"LENS TOKEN REJECT: wanted={descriptor_tokens} matched={matched_tokens} candidate={candidate_hay[:180]}")
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
    "توصيل": "taw9eel.com", "التوصيل": "taw9eel.com", "taw9eel": "taw9eel.com", "taw9el": "taw9eel.com",
    "انترسبورت": "intersport.com.kw", "إنترسبورت": "intersport.com.kw", "intersport": "intersport.com.kw",
    "ديكاثلون": "decathlon.com.kw", "decathlon": "decathlon.com.kw",
    # v69: متاجر متخصصة كويتية (دومينات متحقق منها)
    "بروسبورتس": "prosportskw.com", "برو سبورتس": "prosportskw.com", "prosports": "prosportskw.com", "pro sports": "prosportskw.com",
    "تيجرو": "tigro.app", "تيغرو": "tigro.app", "tigro": "tigro.app",
    "عروض كيو ايت": "3roodq8.com", "عروضكيوايت": "3roodq8.com", "3roodq8": "3roodq8.com", "3rstore": "3roodq8.com",
    "سن اند ساند": "sssports.com", "sun and sand": "sssports.com", "sunandsand": "sssports.com", "sssports": "sssports.com",
    "فوت لوكر": "footlocker.com.kw", "footlocker": "footlocker.com.kw",
    "نمشي": "namshi.com", "namshi": "namshi.com",
}


# ---- v69: محرك الفئات — كل فئة لها متاجرها المتخصصة القوية أولاً --------------
# المنصات العامة (نون/طلبات/لولو...) دائماً في ذيل القائمة، فلا تكتسح المتخصصين.
GENERAL_MARKETPLACES = ["جمعية دوت كوم", "طلبات", "كيتا", "نون", "لولو", "كارفور"]

CATEGORY_KEYWORDS = {
    "sports": (
        "كره سله", "كره قدم", "كره طايره", "كره تنس", "كره", "مضرب", "تنس", "بادل",
        "سكواش", "ريشه", "بادمنتون", "جيم", "لياقه", "دمبل", "اثقال", "بار حديد",
        "سير كهربائي", "دراجه هوائيه", "دراجه ثابته", "سباحه", "نظاره سباحه", "حبل قفز",
        "سجاده يوغا", "يوغا", "بروتين رياضي", "جوتي رياضي", "حذاء رياضي", "ملابس رياضيه",
        "basketball", "football", "soccer", "volleyball", "tennis", "padel", "racket",
        "squash", "badminton", "gym", "fitness", "dumbbell", "barbell", "kettlebell",
        "treadmill", "bike", "bicycle", "cycling", "swimming", "goggles", "jump rope",
        "yoga", "sneaker", "running shoe", "sportswear", "cricket", "darts",
    ),
    "gaming": (
        "بلايستيشن", "اكس بوكس", "نينتندو", "سويتش", "يد تحكم", "لعبه فيديو", "العاب فيديو",
        "قير", "شاشه قيمنق", "كرسي قيمنق", "سماعه قيمنق", "كيبورد", "ماوس",
        "playstation", "ps5", "ps4", "xbox", "nintendo", "switch", "controller",
        "gaming", "gamepad", "headset", "keyboard", "mouse", "steam deck", "video game",
    ),
    "electronics": (
        "ايفون", "سامسونج", "لابتوب", "تابلت", "ايباد", "تلفزيون", "الكترون", "هاتف",
        "جوال", "ساعه ابل", "ساعه ذكيه", "سماعه", "ايربودز", "كاميرا", "شاحن", "باور بانك",
        "iphone", "samsung", "laptop", "tablet", "ipad", "television", "tv", "phone",
        "smartwatch", "airpods", "earbuds", "camera", "charger", "power bank", "drone",
    ),
    "appliances": (
        "ثلاجه", "غساله", "فرن", "مكيف", "جلايه", "مكنسه", "قلايه", "ميكرويف",
        "fridge", "refrigerator", "washer", "washing machine", "oven", "air conditioner",
        "dishwasher", "vacuum", "air fryer", "microwave",
    ),
    "beauty": (
        "عطر", "عطور", "برفان", "مكياج", "روج", "فاونديشن", "ماسكرا", "كريم", "سيروم",
        "عنايه", "شامبو", "واقي شمس",
        "perfume", "makeup", "foundation", "mascara", "cream", "serum", "skincare",
        "shampoo", "sunscreen", "cosmetic",
    ),
    "pharmacy": (
        "دواء", "صيدليه", "فيتامين", "مكمل", "حفاض", "حفاظ", "بروتين",
        "medicine", "pharmacy", "vitamin", "supplement", "diaper",
    ),
    "grocery": (
        "بيبسي", "شيبس", "حليب", "قهوه", "شاي", "سكر", "رز", "زيت", "ماء", "عصير",
        "بسكوت", "منظف", "صابون", "معجون", "تونه", "نسكافيه", "برينجلز", "كيتكات",
        "grocery", "milk", "coffee", "tea", "rice", "detergent",
    ),
    "food_delivery": (
        "مطعم", "وجبه", "برجر", "بيتزا", "فلات وايت", "شاورما", "دجاج مقلي",
        "restaurant", "burger", "pizza", "shawarma", "meal",
    ),
    "fashion": (
        "ملابس", "قميص", "بنطلون", "فستان", "جاكيت", "كاب", "قبعه", "شنطه", "حقيبه",
        "حذاء", "جوتي", "عبايه", "بيجامه",
        "clothing", "shirt", "pants", "dress", "jacket", "cap", "bag", "shoe", "abaya",
    ),
    "furniture": (
        "اثاث", "كرسي", "طاوله", "سرير", "كنب", "صوفا", "مرتبه", "دولاب",
        "furniture", "chair", "table", "bed", "sofa", "mattress", "wardrobe",
    ),
    "kids_toys": (
        "لعبه اطفال", "العاب اطفال", "لعبه", "العاب", "دميه", "ليغو", "ليجو", "مكعبات",
        "عربانه", "عربه اطفال", "رضاعه", "كرسي طفل", "بزل",
        "toy", "toys", "doll", "lego", "puzzle", "stroller", "baby",
    ),
    "auto": (
        "سياره", "بطاريه سياره", "اطار", "تواير", "زيت محرك", "اكسسوارات سياره", "قطع غيار",
        "car battery", "tyre", "tire", "engine oil", "car accessories", "auto parts",
    ),
}

# المتخصصون أولاً بترتيب القوة، ثم المنصات العامة تُلحق تلقائياً في الذيل.
CATEGORY_SPECIALISTS = {
    "sports": ["Pro Sports Kuwait (prosportskw.com)", "Intersport Kuwait", "Decathlon Kuwait", "Sun & Sand Sports", "Foot Locker Kuwait"],
    "gaming": ["3RoodQ8 (3roodq8.com)", "Xcite", "Eureka", "Blink", "Jarir"],
    "electronics": ["Xcite", "Eureka", "Best Al-Yousifi", "Blink", "Jarir", "3RoodQ8 (3roodq8.com)"],
    "appliances": ["Xcite", "Eureka", "Best Al-Yousifi", "Blink"],
    "beauty": ["Boutiqaat", "Faces", "Sephora Kuwait", "Bloomingdale's Kuwait"],
    "pharmacy": ["Boots Kuwait", "YIACO", "Royal Pharmacy"],
    "grocery": ["جمعية دوت كوم", "Lulu", "Carrefour", "Taw9eel"],
    "food_delivery": ["Keeta", "Talabat", "Deliveroo"],
    "fashion": ["Namshi", "Sun & Sand Sports", "Foot Locker Kuwait", "Centrepoint", "H&M Kuwait"],
    "furniture": ["IKEA Kuwait", "The One", "Home Centre", "Midas"],
    "kids_toys": ["Tigro (tigro.app)", "Toys R Us Kuwait", "3RoodQ8 (3roodq8.com)", "Mothercare", "Babyshop"],
    "auto": ["AlMailem Tires", "Tires Plus", "Xcite"],
}

def detect_category(query):
    """يحدد فئة المنتج من الكلمات؛ الفئات الأدق (رياضة/قيمنق/ألعاب) تُفحص قبل العامة."""
    q = normalize_ar(query)
    for cat in ("gaming", "sports", "kids_toys", "appliances", "pharmacy", "beauty",
                "auto", "furniture", "food_delivery", "grocery", "electronics", "fashion"):
        if any(normalize_ar(w) in q for w in CATEGORY_KEYWORDS.get(cat, ())):
            return cat
    return ""

def priority_stores_for(query):
    """v69: متاجر الفئة المتخصصة أولاً، والمنصات العامة (نون/طلبات...) في ذيل القائمة دائماً."""
    cat = detect_category(query)
    specialists = list(CATEGORY_SPECIALISTS.get(cat, []))
    tail = [m for m in GENERAL_MARKETPLACES if m not in specialists]
    ordered = specialists + tail
    return ordered[:9] if ordered else list(GENERAL_MARKETPLACES)

def store_domain(name):
    n = normalize_name(normalize_ar(name))
    for k, d in STORE_DOMAINS.items():
        if k in n or n in k: return d
    return ""
JUNK_STORE = re.compile(r"^(اونلاين|أونلاين|online|الموقعالرسمي|official)$", re.I)
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
        # "توصيل" و"أونلاين" وأمثالها ليست متاجر؛ غالباً سطر رسوم توصيل التقطه النموذج كعرض.
        if is_junk_store(name):
            print(f"SKIP JUNK STORE LINE: {s[:80]}")
            continue
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
        (("مضرب", "كره", "كرة", "تنس", "بادل", "جيم", "رياضه", "رياضة", "under armour", "nike", "adidas", "sports", "basketball"),
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
    """بحث ثنائي اللغة مع ترتيب السوق الثابت: محلي ثم أمريكا ثم الصين فقط."""
    response_rule = LANG_INSTR[lang]
    market_name = current_market().get('country_name', 'Kuwait')
    return (
        f"ابحث عن المنتج باستخدام العربية والإنجليزية معاً: {query}. "
        "حوّل الاسم داخلياً إلى مرادف عربي ومرادف إنجليزي، وجرّب اسم البراند باللاتيني والعربي. "
        f"رتب النتائج حصراً: متاجر {market_name} أولاً، ثم متاجر الولايات المتحدة، ثم متاجر الصين؛ واحذف أي دولة أخرى. "
        "داخل كل سوق رتب من الأرخص إلى الأغلى، وكل نتيجة يجب أن تحتوي سعراً رقمياً ورابط صفحة منتج مباشر. "
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


# ---- v70: البحث بالإنجليزي، العرض بالعربي ------------------------------------
# فهرسة المتاجر ومحرك Google Shopping أدق بالاسم الإنجليزي التجاري.
# نترجم اسم المنتج مرة واحدة (نموذج سريع رخيص + كاش) ونبحث به،
# بينما الرد للمستخدم يبقى بالعربية بالكامل.
TRANSLATE_NAME_SYSTEM = """أنت مترجم أسماء منتجات تجارية للبحث في المتاجر.
حوّل اسم المنتج إلى الاسم التجاري الإنجليزي الأدق كما يُكتب في صفحات المتاجر.
- أبقِ البراند والموديل والأرقام كما هي (iPhone 15 Pro, 256GB, PS5, Spalding).
- ترجم الوصف والفئة والحجم (كرة سلة -> basketball، 1 لتر -> 1L، حليب كامل الدسم -> full fat milk).
- إذا كان البراند مكتوباً بالعربي حوّله لتهجئته اللاتينية الرسمية (سبولدينج -> Spalding، المراعي -> Almarai).
- لا تشرح ولا تضف خيارات. أرجع سطراً واحداً فقط بالإنجليزية."""

EN_NAME_CACHE = {}
EN_NAME_LOCK = threading.Lock()

def english_search_name(query):
    """يعيد الاسم الإنجليزي التجاري للبحث. الاستعلام الإنجليزي أصلاً يمر كما هو."""
    q = " ".join(str(query or "").split()).strip()
    if not q:
        return ""
    if not re.search(r"[\u0600-\u06FF]", q):
        return q
    key = re.sub(r"\s+", " ", normalize_ar(q))[:150]
    with EN_NAME_LOCK:
        if key in EN_NAME_CACHE:
            return EN_NAME_CACHE[key]
    raw, _ = call_gemini([{"text": q}], system=TRANSLATE_NAME_SYSTEM, use_search=False)
    name = (raw or "").strip().splitlines()[0].strip().strip('"').strip("'")
    # حماية: لازم يكون إنجليزياً فعلاً وبطول منطقي، وإلا نتجاهله ونكمل بالعربي.
    if not re.search(r"[A-Za-z]", name) or re.search(r"[\u0600-\u06FF]", name) or len(name) > 90:
        name = ""
    with EN_NAME_LOCK:
        if len(EN_NAME_CACHE) > 3000:
            EN_NAME_CACHE.clear()
        EN_NAME_CACHE[key] = name
    print(f"EN SEARCH NAME: {q!r} -> {name!r}")
    return name


def _query_candidates(query, english_name=""):
    """v70: صيغ البحث بالإنجليزية أولاً (أدق فهرسة)، والعربية كاحتياط في المحاولات اللاحقة."""
    raw_parts = [p.strip() for p in re.split(r"\s*[|｜]\s*", query or "") if p.strip()]
    ar_parts = [p for p in raw_parts if re.search(r"[\u0600-\u06FF]", p)]
    en_parts = [p for p in raw_parts if re.search(r"[A-Za-z]", p) and not re.search(r"[\u0600-\u06FF]", p)]
    candidates = []
    if english_name:
        candidates.append(english_name)
    candidates.extend(en_parts)
    candidates.extend(ar_parts)
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
    "carrefour kuwait", "lulu kuwait", "jm3eia", "جمعية", "taw9eel", "توصيل", "intersport kuwait",
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

# v72: النتائج المسموحة فقط بعد السوق المحلي هي الولايات المتحدة ثم الصين.
# نستخدم الدومين/اسم المتجر/العملة لأن كثيراً من المتاجر الأمريكية والصينية تعمل على .com.
US_STORE_HINTS = (
    "amazon.com", "walmart.com", "target.com", "bestbuy.com", "costco.com",
    "homedepot.com", "lowes.com", "macys.com", "nordstrom.com", "zappos.com",
    "bhphotovideo.com", "newegg.com", "rei.com", "dickssportinggoods.com", "ebay.com",
)

CHINA_STORE_HINTS = (
    "aliexpress.com", "alibaba.com", "1688.com", "taobao.com", "tmall.com", "shein.com",
    "temu.com", "dhgate.com", "made-in-china.com", "banggood.com", "gearbest.com",
    "jd.com", "pinduoduo.com",
)

def _result_hay_host(item):
    hay = " ".join(str(item.get(k) or "") for k in (
        "title", "source", "link", "domain", "snippet", "price", "price_text", "currency"
    )).lower()
    try:
        host = urllib.parse.urlparse(str(item.get("link") or item.get("url") or "")).netloc.lower().replace("www.", "")
    except Exception:
        host = ""
    return hay, host

def _host_matches_any(host, domains):
    host = (host or "").lower().strip(".")
    for domain in domains:
        d = str(domain or "").lower().strip(".")
        if host == d or host.endswith("." + d):
            return True
    return False

def is_us_market_result(item):
    hay, host = _result_hay_host(item)
    if host.endswith(".us") or _host_matches_any(host, US_STORE_HINTS):
        return True
    # China hints win before USD because Chinese marketplaces often display prices in USD.
    if _host_matches_any(host, CHINA_STORE_HINTS):
        return False
    return any(marker in hay for marker in COUNTRY_CURRENCY_MARKERS.get("us", ()))

def is_china_market_result(item):
    hay, host = _result_hay_host(item)
    if host.endswith(".cn") or _host_matches_any(host, CHINA_STORE_HINTS):
        return True
    return bool(re.search(r"(?:\bCNY\b|\bRMB\b|人民币|中国|china)", hay, flags=re.I))

def result_market_rank(item):
    """0=بلد المستخدم، 1=أمريكا، 2=الصين، 99=مرفوض.

    نفحص السوق الأجنبي الصريح قبل علامة العملة المحلية لأن السعر بعد التحويل قد يحتوي
    KWD/SAR/AED مع العملة الأصلية بين قوسين.
    """
    # v80: نتائج Google Shopping النصية تُنشأ داخلياً من تمريرات سوق منفصلة،
    # لذلك نثق بالتصنيف الذي وضعته التمريرة نفسها بدل إعادة تخمين البلد من .com/العملة.
    forced = item.get("_forced_market_rank") if isinstance(item, dict) else None
    if forced in (0, 1, 2):
        return forced
    cc = (current_market().get("country") or DEFAULT_COUNTRY).lower()
    hay, host = _result_hay_host(item)
    is_us = is_us_market_result(item)
    is_cn = is_china_market_result(item)

    if cc == "us" and is_us:
        return 0
    if cc == "cn" and is_cn:
        return 0

    if cc != "us" and is_us:
        return 1
    if cc != "cn" and is_cn:
        return 1 if cc == "us" else 2

    # دولة رابعة صريحة بالدومين تُرفض حتى لو كان السطر يحتوي السعر المحوّل بعملة المستخدم.
    for other_cc, tlds in COUNTRY_TLDS.items():
        if other_cc not in {cc, "us", "cn"} and any(tld in host for tld in tlds):
            return 99

    # كذلك أي عملة أصلية صريحة غير عملة المستخدم/USD/CNY تعني سوقاً غير مسموح.
    local_cur = (current_market().get("currency") or "").upper()
    allowed_codes = {x for x in (local_cur, "USD", "CNY") if x}
    codes = set(re.findall(r"\b[A-Z]{3}\b", hay.upper())) & KNOWN_CURRENCY_CODES
    if any(code not in allowed_codes for code in codes):
        return 99
    if "£" in hay and "GBP" not in allowed_codes:
        return 99
    if "€" in hay and "EUR" not in allowed_codes:
        return 99

    if is_local_lens_result(item):
        return 0
    return 99

def filter_allowed_market_results(verified, exclude_local=False):
    kept = {}
    for name, info in (verified or {}).items():
        item = {
            "link": info.get("url", ""), "source": name,
            "title": info.get("title", ""), "currency": info.get("currency", ""),
            "price": info.get("price_text", "") or info.get("price", ""),
        }
        rank = result_market_rank(item)
        if rank == 99 or (exclude_local and rank == 0):
            print(f"MARKET FILTER REJECT rank={rank}: {name} -> {info.get('url','')}")
            continue
        info["market_rank"] = rank
        kept[name] = info
    return kept

def prepare_market_offer(info, name, lang="ar"):
    """يحضر السعر والترتيب حسب السوق. المحلي يبقى بعملة المستخدم؛ أمريكا/الصين تُحوّل محلياً."""
    item = {
        "link": info.get("url", ""), "source": name, "title": info.get("title", ""),
        "currency": info.get("currency", ""), "price": info.get("price_text", "") or info.get("price", ""),
    }
    rank = info.get("market_rank")
    if rank is None:
        rank = result_market_rank(item)
    if rank == 99:
        return None
    try:
        numeric = float(info.get("price"))
    except Exception:
        numeric = None
    if numeric is None:
        return None
    if rank == 0:
        shown = f"{format_price(numeric)} {currency_label(lang)}"
        return rank, numeric, shown
    src = (info.get("currency") or "").upper().strip()
    if not src:
        src = "USD" if is_us_market_result(item) else "CNY" if is_china_market_result(item) else ""
    shown, converted = display_global_price(numeric, "", src, lang)
    return rank, (converted if converted is not None else numeric), shown

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


def filter_local_market_only(verified):
    """v68: حارس الوضع المحلي — أي متجر أجنبي واضح (نطاق دولة ثانية أو عملة ثانية) يُرفض.

    المواقع العالمية لا تظهر في البحث المحلي أبداً؛ تظهر فقط بعد موافقة المستخدم
    على «دوّر عالمياً». النتيجة مجهولة الجنسية (لا محلية ولا أجنبية واضحة) تمر.
    """
    kept = {}
    for name, info in (verified or {}).items():
        item = {
            "link": info.get("url", ""), "source": name,
            "title": info.get("title", ""), "currency": info.get("currency", ""),
            "price": info.get("price_text", "") or "",
        }
        # نرفض فقط الأجنبي الواضح: نطاق دولة ثانية أو عملة دولة ثانية صريحة.
        if not is_local_lens_result(item):
            host = ""
            try:
                host = urllib.parse.urlparse(item["link"]).netloc.lower()
            except Exception:
                pass
            cc = (current_market().get("country") or DEFAULT_COUNTRY).lower()
            foreign_tld = any(
                other_cc != cc and any(tld in host for tld in tlds)
                for other_cc, tlds in COUNTRY_TLDS.items()
            )
            hay = " ".join(str(item.get(k) or "") for k in ("title", "source", "currency", "price")).lower()
            foreign_currency = any(
                other_cc != cc and any(marker in hay for marker in markers)
                for other_cc, markers in COUNTRY_CURRENCY_MARKERS.items()
            )
            if foreign_tld or foreign_currency:
                print(f"LOCAL MODE REJECT FOREIGN: {name} -> {info.get('url','')}")
                continue
        kept[name] = info
    return kept

def lens_priced_offers(lens_context, lang="ar", local_only=True, exclude_local=False):
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
        if not title or not is_lens_product_url(url, item) or url in used_urls:
            continue
        market_rank = result_market_rank(item)
        if market_rank == 99:
            print(f"LENS REJECT OTHER COUNTRY: {title} -> {url}")
            continue
        if local_only and market_rank != 0:
            continue
        if exclude_local and market_rank == 0:
            print(f"GLOBAL EXCLUDE LOCAL LENS: {title} -> {url}")
            continue
        if in_stock is False:
            print(f"LENS PRODUCT OOS SKIP: {title} -> {url}")
            continue
        if not price_text and price_value in (None, ""):
            continue
        # v72: العملة المحلية تُعرض كما هي، أما أمريكا/الصين فتحوّل إلى عملة المستخدم.
        # لا نرفض العملة الأجنبية لأنها الآن جزء مقصود من النتائج.
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
        if market_rank == 0:
            shown = format_lens_price(price_text, price_value, lang, currency or None)
        else:
            src_currency = (currency or "").upper().strip()
            if not src_currency:
                src_currency = "USD" if is_us_market_result(item) else "CNY" if is_china_market_result(item) else ""
            shown, converted = display_global_price(price_value, price_text, src_currency, lang)
            if converted is not None:
                numeric = converted
        offers[name] = {
            "url": url,
            "price": numeric,
            "price_text": shown,
            "is_local": market_rank == 0,
            "market_rank": market_rank,
            "title": title,
            "position": int(item.get("position") or i),
            "exact": bool(item.get("exact")),
            "section": item.get("section") or "",
            "image_url": item.get("image") or item.get("thumbnail") or "",
        }
        used_urls.add(url)
    # نفس المواصفات فقط: بطاقة عبوة أصغر أو سعة أقل ليست سعراً أرخص لنفس المنتج.
    offers = filter_same_size(offers, ((lens_context.get("chosen") or {}).get("title") or ""))
    # v72: بلد المستخدم أولاً، ثم أمريكا، ثم الصين فقط. داخل كل سوق: exact/visual ثم السعر.
    ranked = sorted(
        offers.items(),
        key=lambda kv: (
            kv[1].get("market_rank", 99),
            0 if kv[1].get("exact") else 1,
            0 if kv[1].get("section") == "visual_matches" else 1,
            kv[1].get("position", 999),
        ),
    )
    top = ranked[:MAX_STORES]
    top.sort(key=lambda kv: (
        kv[1].get("market_rank", 99),
        kv[1].get("price") if kv[1].get("price") is not None else 10**9,
    ))
    return dict(top)


def verify_lens_direct_matches(lens_context, local_only=True, exclude_local=False):
    """Fallback verifier for Lens URLs that had no price card. Exact matches get priority."""
    if not lens_context:
        return {}
    candidates = {}
    ordered = sorted(
        (lens_context.get("matches") or [])[:24],
        key=lambda m: (result_market_rank(m), 0 if m.get("exact") else 1, int(m.get("position") or 99)),
    )
    for i, m in enumerate(ordered[:8], 1):
        url = (m.get("link") or "").strip()
        title = (m.get("title") or "").strip()
        source = (m.get("source") or f"Lens {i}").strip()
        if not title or not is_lens_product_url(url, m):
            continue
        market_rank = result_market_rank(m)
        if market_rank == 99:
            continue
        if local_only and market_rank != 0:
            continue
        if exclude_local and market_rank == 0:
            print(f"GLOBAL EXCLUDE LOCAL VERIFY: {title} -> {url}")
            continue
        candidates[source] = url
    verified = verify_offers(candidates, (lens_context.get("chosen") or {}).get("title", ""))
    verified = filter_same_size(verified, (lens_context.get("chosen") or {}).get("title", ""))
    if verified:
        print(f"LENS HTML VERIFIED: {list(verified)}")
    return verified


# ---- v69: طبقة Google Shopping + Immersive Product ---------------------------
def _shopping_clean_query(query):
    """اسم بحث نظيف لـ Google Shopping: بدون كابشن المستخدم وبدون مرادفات | المتعددة."""
    q = re.sub(r"^.*?—\s*", "", str(query or "")).strip() or str(query or "")
    q = q.split("|")[0].strip()
    return " ".join(q.split()[:10])


def _serpapi_shopping_request(query, gl, hl="en"):
    """طلب google_shopping واحد. يعيد shopping_results (قد تكون فارغة)."""
    params = {
        "engine": "google_shopping", "q": query, "api_key": SERPAPI_API_KEY,
        "hl": hl, "output": "json",
    }
    if gl:
        params["gl"] = gl
    try:
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=45)
        if r.status_code >= 400:
            print(f"GOOGLE SHOPPING HTTP {r.status_code}: {r.text[:300]}")
            return []
        data = r.json()
        if data.get("error"):
            print(f"GOOGLE SHOPPING ERROR: {data.get('error')}")
            return []
        results = data.get("shopping_results") or []
        print(f"GOOGLE SHOPPING: q={query[:60]!r} gl={gl or '-'} -> {len(results)} cards")
        return results[:SHOPPING_RESULT_LIMIT]
    except Exception as e:
        print(f"GOOGLE SHOPPING EXCEPTION: {e}")
        return []


def _immersive_product_stores(page_token):
    """يفتح بطاقة Immersive Product ويعيد قائمة المتاجر بروابط مباشرة وأسعار."""
    params = {"engine": "google_immersive_product", "page_token": page_token, "api_key": SERPAPI_API_KEY}
    if IMMERSIVE_MORE_STORES:
        # يرفع النتيجة من 3-5 متاجر إلى 13 كحد أقصى حسب توثيق SerpApi.
        params["more_stores"] = "true"
    try:
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=45)
        if r.status_code >= 400:
            print(f"IMMERSIVE HTTP {r.status_code}: {r.text[:200]}")
            return []
        data = r.json()
        if data.get("error"):
            print(f"IMMERSIVE ERROR: {data.get('error')}")
            return []
        stores = (data.get("product_results") or {}).get("stores") or []
        print(f"IMMERSIVE PRODUCT: {len(stores)} store offers")
        return stores
    except Exception as e:
        print(f"IMMERSIVE EXCEPTION: {e}")
        return []


def _shopping_direct_url(url):
    """روابط Shopping/Immersive أحياناً تحويلات Google؛ نحلها لرابط المتجر المباشر."""
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        return ""
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return ""
    if "google." in host:
        url = get_final_url(url)
    return url if is_direct_store_url(url) else ""


def google_shopping_offers(query, lang="ar", allow_global=False, lens_context=None, english_name=""):
    """يجمع عروض Google Shopping: روابط البطاقات المباشرة أولاً، ثم Immersive Product

    للبطاقات التي بلا رابط مباشر (ضمن سقف IMMERSIVE_LOOKUPS_MAX للكريدت).
    v70: البحث دائماً بالاسم الإنجليزي (hl=en) لأن فهرسة Google Shopping به أدق.
    الإخراج بنفس مخطط verify_offers: {اسم المتجر: {url, price, title, currency, price_text}}.
    """
    if not ENABLE_GOOGLE_SHOPPING or not SERPAPI_API_KEY:
        return {}
    clean_q = _shopping_clean_query(english_name or query)
    if not clean_q:
        return {}
    gl = "" if allow_global else current_market().get("country", DEFAULT_COUNTRY)
    cards = _serpapi_shopping_request(clean_q, gl or "us", hl="en")
    if not cards:
        return {}

    offers, used_urls, immersive_tokens = {}, set(), []

    def _add(store_name, url, price_text, price_value, title, position):
        url = _shopping_direct_url(url)
        if not url or url in used_urls:
            return
        item = {"link": url, "source": store_name, "title": title, "price": str(price_text or ""), "currency": ""}
        if allow_global:
            if is_local_lens_result(item):
                print(f"SHOPPING GLOBAL EXCLUDE LOCAL: {store_name} -> {url}")
                return
        else:
            if is_foreign_lens_result(item):
                print(f"SHOPPING LOCAL REJECT FOREIGN: {store_name} -> {url}")
                return
        numeric = None
        try:
            numeric = float(price_value) if price_value not in (None, "") else None
        except Exception:
            numeric = None
        if numeric is None:
            numeric = _extract_numeric_price(str(price_text or ""))
        if numeric is None or numeric <= 0:
            return
        src_currency = detect_currency_code(str(price_text or ""), "")
        if allow_global:
            shown, converted = display_global_price(numeric, str(price_text or ""), src_currency, lang)
            sort_price = converted if converted is not None else numeric
        else:
            local_code = (current_market().get("currency") or "").upper()
            if src_currency and src_currency != local_code:
                # gl محلي لكن Google أحياناً يدس بطاقة بعملة أجنبية؛ نرفضها في الوضع المحلي.
                print(f"SHOPPING LOCAL CURRENCY REJECT: {store_name} {price_text}")
                return
            shown = f"{format_price(numeric)} {currency_label(lang)}"
            sort_price = numeric
        name = (store_name or "").strip()[:40] or f"Store {len(offers)+1}"
        base, n = name, 2
        while name in offers:
            name = f"{base} {n}"; n += 1
        offers[name] = {
            "url": url, "price": sort_price, "price_text": shown,
            "title": (title or "").strip(), "currency": src_currency,
            "position": position, "source_layer": "shopping",
        }
        used_urls.add(url)

    for i, card in enumerate(cards, 1):
        title = (card.get("title") or "").strip()
        source = (card.get("source") or "").strip()
        direct = (card.get("link") or "").strip()
        # product_link هو صفحة Google نفسها — ما ينفع كرابط للمستخدم.
        added_before = len(offers)
        if direct:
            _add(source or title, direct, card.get("price"), card.get("extracted_price"), title, i)
        token = (card.get("immersive_product_page_token") or "").strip()
        if token and len(offers) == added_before:
            # ما حصلنا رابط مباشر من البطاقة: نرشحها لفتح Immersive.
            immersive_tokens.append((i, title, token))

    # نفتح Immersive لأفضل البطاقات فقط، بالتوازي، ضمن سقف الكريدت.
    if immersive_tokens and IMMERSIVE_LOOKUPS_MAX > 0 and len(offers) < MAX_STORES:
        picked = immersive_tokens[:IMMERSIVE_LOOKUPS_MAX]
        market_snapshot = current_market()
        futures = {
            SHOPPING_POOL.submit(_run_with_market, market_snapshot, _immersive_product_stores, token): (pos, title)
            for pos, title, token in picked
        }
        for future, (pos, title) in futures.items():
            try:
                stores = future.result(timeout=60) or []
            except Exception as e:
                print(f"IMMERSIVE FUTURE ERR: {e}")
                continue
            for store in stores:
                _add(
                    store.get("name") or "",
                    store.get("link") or "",
                    store.get("price") or store.get("total") or "",
                    store.get("extracted_price") if store.get("extracted_price") not in (None, "") else store.get("extracted_total"),
                    title, pos,
                )

    # نفس المواصفات فقط + توافق هوية Lens إن وجدت (لبحث الصور).
    offers = filter_same_size(offers, clean_q)
    if lens_context:
        offers = filter_verified_with_lens(offers, lens_context)
    if offers:
        print(f"SHOPPING OFFERS FINAL: {[(n, o['price']) for n, o in offers.items()]}")
    return offers


def _shopping_layer_search(query, lang, allow_global=False, lens_context=None, english_name=""):
    """يحوّل عروض Google Shopping إلى نفس صيغة باقي الطبقات (نص + روابط)، مرتبة بالأرخص.

    v70: البحث بالاسم الإنجليزي، لكن سطر 📦 المعروض للمستخدم يبقى بالاسم العربي الأصلي.
    """
    offers = google_shopping_offers(query, lang, allow_global=allow_global, lens_context=lens_context, english_name=english_name)
    if not offers:
        return "", {}
    sorted_v = sorted(offers.items(), key=lambda x: x[1].get("price") if x[1].get("price") is not None else 10**9)
    # العرض: الاسم العربي الأصلي للمستخدم العربي؛ الإنجليزي فقط إذا كان الطلب أصلاً إنجليزياً.
    arabic_display = _shopping_clean_query(query)
    if lang == "ar" and not re.search(r"[\u0600-\u06FF]", arabic_display) and re.search(r"[\u0600-\u06FF]", str(query or "")):
        arabic_display = str(query).strip()
    display = arabic_display or _shopping_clean_query(english_name or query)
    lines = [f"📦 {display}", ""]
    urls = {}
    for i, (name, info) in enumerate(sorted_v[:max(MAX_STORES * 2, 6)]):
        prefix = "✅" if i == 0 else "•"
        size_note = format_pack_size(extract_pack_size(info.get("title", "")))
        size_suffix = f" ({size_note})" if size_note else ""
        lines.append(f"{prefix} {name} — {info.get('price_text') or format_price(info.get('price'))}{size_suffix}")
        urls[name] = info["url"]
    return "\n".join(lines), urls


def _new_layer_search(query, lang, prompt_text=None, source_image_b64=None, source_image_mime=None, lens_context=None, allow_global=False, english_name=""):
    # نتائج الصور تعتمد على الصورة نفسها، لذلك لا نستخدم كاش النص وحده.
    cached = None if source_image_b64 else cache_get(query, lang)
    if cached:
        return cached

    # For image requests, use the product cards returned by Google Lens itself first.
    # This preserves the many visually close results Google shows instead of demanding one exact SKU.
    lens_cards = lens_priced_offers(lens_context, lang, local_only=False, exclude_local=allow_global)
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
    lens_verified = verify_lens_direct_matches(lens_context, local_only=False, exclude_local=allow_global)
    if lens_verified:
        lens_verified = filter_allowed_market_results(lens_verified, exclude_local=allow_global)
        prepared = []
        for name, info in lens_verified.items():
            ready = prepare_market_offer(info, name, lang)
            if not ready:
                continue
            market_rank, sort_price, shown = ready
            info["shown"] = shown
            info["sort_price"] = sort_price
            info["market_rank"] = market_rank
            prepared.append((name, info))
        sorted_v = sorted(prepared, key=lambda x: (x[1].get("market_rank", 99), x[1].get("sort_price", 10**9)))
        if sorted_v:
            display_name = (lens_context.get("chosen") or {}).get("title") or query
            lines = [f"📦 {display_name}", ""]
            new_urls = {}
            for i, (name, info) in enumerate(sorted_v[:MAX_STORES]):
                prefix = "✅" if i == 0 else "•"
                lines.append(f"{prefix} {name} — {info['shown']}")
                new_urls[name] = info["url"]
            return "\n".join(lines), new_urls

    candidates = _query_candidates(query, english_name=english_name)
    print(f"SEARCH CANDIDATES (EN-FIRST): {candidates}")
    best_txt, best_urls = "", {}

    for attempt in range(1, MAX_SEARCH_ATTEMPTS + 1):
        search_term = candidates[(attempt - 1) % len(candidates)]
        # v70: نبحث بالإنجليزي، ونمرر المقابل العربي كمساعد للمتاجر ذات الفهرسة العربية.
        ar_hint = ""
        for part in re.split(r"\s*[|｜]\s*", str(query or "")):
            if re.search(r"[\u0600-\u06FF]", part):
                ar_hint = re.sub(r"^.*?—\s*", "", part).strip()
                break
        if attempt == 1 and prompt_text:
            context = f"{prompt_text}\n"
        else:
            context = ""

        # v72: البحث النصي نفسه يتبع ترتيب السوق: محلي -> أمريكا -> الصين فقط.
        priority_stores = priority_stores_for(search_term)
        stores_hint = "، ".join(priority_stores)
        market_name = current_market().get("country_name", "Kuwait")
        if attempt == 1:
            search_scope = (
                f"ابدأ بأشهر المتاجر المحلية في {market_name} (مثل: {stores_hint}) ثم وسّع لأي متجر محلي موثوق. "
                "بعد الانتهاء من المحلي ابحث في متاجر الولايات المتحدة، ثم متاجر الصين فقط. "
                "ارفض أي نتيجة من أوروبا أو بريطانيا أو الهند أو اليابان أو أي دولة أخرى. "
            )
        else:
            search_scope = (
                f"اعمل بحثاً أوسع لنفس المنتج مع الحفاظ على هذا الترتيب الإجباري: {market_name} أولاً، ثم الولايات المتحدة، ثم الصين فقط. "
                "لا تسمح لأي دولة رابعة، ولا ترفع نتيجة أمريكية أو صينية فوق نتيجة محلية بسبب السعر. "
            )
        current_prompt = (
            f"{context}ابحث في {market_name} عن هذا الاسم تحديداً: {search_term}. "
            + ((f"المقابل العربي لنفس المنتج (استخدمه أيضاً عند البحث في المتاجر ذات الفهرسة العربية): {ar_hint}. ")
               if ar_hint and not re.search(r"[\u0600-\u06FF]", search_term) else "")
            + ((f"الاسم المختار من Google Lens هو: {(lens_context.get('chosen') or {}).get('title','')}. "
                "لا توسع البحث إلى موديلات أخرى من نفس البراند، ولا تقبل اختلافاً واضحاً في اللون أو النقشة أو وجود الكعب. ") if lens_context else "")
            + f"{search_scope}"
            "استخدم الاسم كما هو، ويمكن تجربة تهجئات قريبة لنفس المنتج فقط. "
            "قارن نفس المنتج بنفس المواصفات فقط (الحجم/السعة/الوزن، واللون إذا كان يغيّر السعر): "
            "عبوة أصغر أو أكبر أو سعة تخزين مختلفة تعتبر منتجاً مختلفاً ولا تدخل المقارنة. "
            "اذكر المواصفة بجانب كل سعر إذا كانت معروفة (مثل: 1 لتر أو 256GB). "
            f"أعطني حتى {MAX_STORES} متاجر مختلفة. الترتيب الإجباري حسب السوق أولاً: {market_name} ثم الولايات المتحدة ثم الصين فقط؛ "
            "وداخل كل سوق فقط رتب من الأرخص إلى الأغلى. كل نتيجة يجب أن تحتوي سعراً رقمياً ورابط صفحة المنتج المباشرة داخل المتجر. "
            "ممنوع روابط Google وصفحات البحث والتصنيف، وممنوع أي متجر من دولة غير هذه الأسواق الثلاثة. "
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
            verified = filter_same_size(verified, query)
            verified = filter_allowed_market_results(verified, exclude_local=allow_global)
            if verified:
                # v72: السوق قبل السعر: محلي -> أمريكا -> الصين. داخل كل سوق الأرخص أولاً.
                prepared = []
                for name, info in verified.items():
                    ready = prepare_market_offer(info, name, lang)
                    if not ready:
                        continue
                    market_rank, sort_price, shown = ready
                    info["market_rank"] = market_rank
                    info["sort_price"] = sort_price
                    info["shown"] = shown
                    prepared.append((name, info))
                sorted_v = sorted(prepared, key=lambda x: (x[1].get("market_rank", 99), x[1].get("sort_price", 10**9)))
                # v70: العنوان المعروض عربي؛ الاسم الإنجليزي للبحث فقط.
                title = product_title(txt, (ar_hint if lang == "ar" and ar_hint else search_term))
                lines = [title, ""]
                new_urls = {}
                for i, (name, info) in enumerate(sorted_v[:MAX_STORES]):
                    prefix = "✅" if i == 0 else "•"
                    size_note = format_pack_size(extract_pack_size(info.get("title", "")))
                    size_suffix = f" ({size_note})" if size_note else ""
                    lines.append(f"{prefix} {name} — {info['shown']}{size_suffix}")
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
                if not (matched and is_direct_store_url(matched)):
                    continue
                item = {"link": matched, "source": offer["name"], "title": offer["line"], "price": offer["line"]}
                market_rank = result_market_rank(item)
                if market_rank == 99 or (allow_global and market_rank == 0):
                    print(f"UNVERIFIED MARKET REJECT rank={market_rank}: {offer['name']} -> {matched}")
                    continue
                numeric = _extract_numeric_price(offer.get("line", ""))
                if numeric is None:
                    continue
                if market_rank == 0:
                    shown = f"{format_price(numeric)} {currency_label(lang)}"
                    sort_price = numeric
                else:
                    src = detect_currency_code(offer.get("line", ""), "USD" if market_rank == 1 else "CNY")
                    shown, converted = display_global_price(numeric, offer.get("line", ""), src, lang)
                    sort_price = converted if converted is not None else numeric
                kept.append({"offer": offer, "url": matched, "market_rank": market_rank, "sort_price": sort_price, "shown": shown})
            kept.sort(key=lambda x: (x["market_rank"], x["sort_price"]))
            if kept:
                title = product_title(txt, (ar_hint if lang == "ar" and ar_hint else search_term))
                lines = [title, ""]
                clean_urls = {}
                for i, rec in enumerate(kept[:MAX_STORES]):
                    prefix = "✅" if i == 0 else "•"
                    offer = rec["offer"]
                    lines.append(f"{prefix} {offer['name']} — {rec['shown']}")
                    clean_urls[offer["name"]] = rec["url"]
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
        market_item = {"link": url, "source": offer.get("name", ""), "title": title, "price": offer.get("line", "")}
        market_rank = result_market_rank(market_item)
        if market_rank == 99:
            continue
        item = {
            "name": offer.get("name", "").strip(),
            "url": url,
            "price": price,
            "title": title,
            "line": offer.get("line", ""),
            "layer": layer,
            "host": host,
            "is_local": market_rank == 0,
            "market_rank": market_rank,
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


def _old_layer_search(query, lang, prompt_text=None, lens_context=None, allow_global=False, english_name=""):
    """Second layer: the broad multi-query search logic from the older bot.

    v70: صيغ البحث بالاسم الإنجليزي أولاً (فهرسة المتاجر به أدق)، مع إبقاء صيغة عربية واحدة كاحتياط.
    """
    if not OLD_LAYER_ENABLED:
        return "", {}
    search_name = english_name or query
    market_name = current_market().get("country_name", "Kuwait")
    if allow_global:
        base_prompt = (
            f"ابحث عن {search_name} في الولايات المتحدة ثم الصين فقط. استبعد بلد المستخدم {market_name} واستبعد كل الدول الأخرى. "
            f"سعر رقمي واضح ورابط صفحة المنتج المباشر مع العملة الأصلية. {LANG_INSTR[lang]}"
        )
        variants = [
            base_prompt,
            f"{search_name} United States buy online exact product direct page price USD {LANG_INSTR[lang]}",
            f"{search_name} China buy online exact product direct page price CNY RMB AliExpress Alibaba 1688 Taobao SHEIN JD {LANG_INSTR[lang]}",
        ]
    else:
        # ثلاث عمليات بحث مستقلة تضمن وجود تغطية فعلية لكل سوق بدلاً من الاعتماد على ترتيب Google العام.
        variants = [
            prompt_text or f"ابحث عن {search_name} في {market_name} فقط، أي متجر محلي يبيعه، بسعر رقمي واضح ورابط صفحة منتج مباشر. {LANG_INSTR[lang]}",
            f"{search_name} United States buy online exact product direct product page current price USD; US stores only. {LANG_INSTR[lang]}",
            f"{search_name} China buy online exact product direct product page current price CNY RMB; Chinese stores only such as AliExpress Alibaba 1688 Taobao SHEIN Tmall JD DHgate. {LANG_INSTR[lang]}",
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
    if lens_context:
        verified = filter_verified_with_lens(verified, lens_context)
    verified = filter_same_size(verified, query)
    verified = filter_allowed_market_results(verified, exclude_local=allow_global)
    if allow_global:
        print(f"GLOBAL OLD LAYER US/CN ONLY: {list(verified)}")
    if not verified:
        print("OLD LAYER: no verified direct offers")
        return "", {}

    prepared = []
    for name, info in verified.items():
        ready = prepare_market_offer(info, name, lang)
        if not ready:
            continue
        market_rank, sort_price, shown = ready
        info["market_rank"] = market_rank
        info["sort_price"] = sort_price
        info["shown"] = shown
        prepared.append((name, info))
    sorted_v = sorted(prepared, key=lambda x: (x[1].get("market_rank", 99), x[1].get("sort_price", 10**9)))
    title = product_title(best_txt, query)
    lines = [title, ""]
    new_urls = {}
    for i, (name, info) in enumerate(sorted_v[:max(MAX_STORES * 2, 6)]):
        prefix = "✅" if i == 0 else "•"
        size_note = format_pack_size(extract_pack_size(info.get("title", "")))
        size_suffix = f" ({size_note})" if size_note else ""
        lines.append(f"{prefix} {name} — {info['shown']}{size_suffix}")
        new_urls[name] = info["url"]
    print(f"OLD LAYER VERIFIED: {list(new_urls)}")
    return "\n".join(lines), new_urls


def _store_priority_value(name, url, query=""):
    """v69: ترتيب حسب فئة المنتج — متخصص الفئة (Pro Sports للرياضة، 3RoodQ8 للقيمنق،

    Tigro لألعاب الأطفال...) يتفوق على المنصات العامة مثل نون وطلبات."""
    text = normalize_name(normalize_ar(f"{name} {url}"))
    raw_text = f"{name} {url}".lower()
    if query:
        ranked_stores = priority_stores_for(query)
        for i, store in enumerate(ranked_stores):
            label = re.sub(r"\([^)]*\)", "", store).strip()
            key = normalize_name(normalize_ar(label))
            dom = store_domain(label)
            dom_key = domain_key(dom) if dom else ""
            # مطابقة بالاسم أو بدومين المتجر داخل الرابط.
            if (key and key in text) or (dom and dom.replace("www.", "") in raw_text) or (dom_key and dom_key in raw_text):
                return 120 - i * 8
    priorities = (
        "prosportskw", "tigro", "3roodq8", "intersport", "decathlon", "sssports",
        "jm3eia", "جمعية", "xcite", "eureka", "best", "yousifi", "blink",
        "jarir", "lulu", "carrefour", "noon", "taw9eel", "توصيل",
        "boutiqaat", "boots", "yiaco", "levelshoes", "future", "talabat", "keeta"
    )
    for i, token in enumerate(priorities):
        if token in raw_text:
            return len(priorities) - i
    return 0


def _merge_two_layers(query, lang, new_result, old_result, lens_context=None, shopping_result=None):
    new_txt, new_urls = new_result
    old_txt, old_urls = old_result
    shop_txt, shop_urls = shopping_result or ("", {})
    new_offers = _result_offers(new_txt, new_urls, "new", lens_context)
    old_offers = _result_offers(old_txt, old_urls, "old", lens_context)
    shop_offers = _result_offers(shop_txt, shop_urls, "shopping", lens_context)
    all_offers = new_offers + old_offers + shop_offers
    if not all_offers:
        if new_txt:
            return new_result
        if shop_txt:
            return shop_txt, shop_urls
        return old_result

    # Deduplicate exact URLs. تفضيل بيانات الطبقات: shopping (سعر Google الحقيقي) ثم new ثم old.
    layer_pref = {"shopping": 2, "new": 1, "old": 0}
    dedup = {}
    for offer in all_offers:
        key = offer["url"].split("?")[0].rstrip("/").lower()
        previous = dedup.get(key)
        if previous is None or layer_pref.get(offer["layer"], 0) > layer_pref.get(previous["layer"], 0):
            dedup[key] = offer

    offers = [o for o in dedup.values() if o.get("market_rank", 99) != 99]
    def rank(o):
        quality = 0
        quality += 100 if o.get("exact") else 0
        # v69: أولوية الفئة داخل السوق نفسه فقط.
        quality += _store_priority_value(o.get("name", ""), o.get("url", ""), query) * 2
        quality += {"shopping": 15, "new": 12, "old": 8}.get(o.get("layer"), 8)
        quality += max(0, 20 - min(int(o.get("lens_position", 999)), 20))
        # v72: رتبة السوق هي المفتاح الأول ولا يمكن للسعر/الجودة تجاوزها.
        return (o.get("market_rank", 99), -quality, o.get("price", 10**9))
    offers.sort(key=rank)
    chosen = offers[:MAX_STORES]
    chosen.sort(key=lambda o: (o.get("market_rank", 99), o.get("price") if o.get("price") is not None else 10**9))

    # v70: العرض للمستخدم العربي دائماً بعنوان عربي — نأخذ أول عنوان فيه حروف عربية
    # (من رد Gemini أو من استعلام المستخدم الأصلي)، وعنوان Lens الإنجليزي احتياط أخير.
    lens_display = ((lens_context or {}).get("chosen") or {}).get("title") or ""
    title_candidates = [
        product_title(new_txt, "").replace("📦", "").strip(),
        product_title(old_txt, "").replace("📦", "").strip(),
        re.sub(r"^.*?—\s*", "", str(query or "")).strip(),
        str(query or "").strip(),
    ]
    display_title = ""
    if lang == "ar":
        for cand in title_candidates:
            if cand and re.search(r"[\u0600-\u06FF]", cand):
                display_title = cand
                break
    if not display_title:
        display_title = lens_display or next((c for c in title_candidates if c), query)
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
    """v69 three-layer search: Google Shopping (structured prices) + Lens/priority layer + broad layer.

    طبقة Shopping تنطلق بالتوازي منذ البداية فلا تضيف زمناً، وتُدمج نتائجها مع الطبقتين
    بترتيب السوق أولاً (محلي -> أمريكا -> الصين) ثم السعر داخل كل سوق.
    """
    cached = None if source_image_b64 or lens_context else cache_get(query, lang)
    if cached:
        return cached

    # v70: ترجمة اسم المنتج للإنجليزي مرة واحدة (كاش) — البحث إنجليزي والعرض عربي.
    english_name = english_search_name(query)

    # Shopping ينطلق أولاً بالتوازي (رخيص وسريع) بينما تشتغل طبقات Gemini.
    market_snapshot = current_market()
    shopping_future = None
    if ENABLE_GOOGLE_SHOPPING and SERPAPI_API_KEY:
        shopping_future = SHOPPING_POOL.submit(
            _run_with_market, market_snapshot, _shopping_layer_search,
            query, lang, allow_global, lens_context, english_name,
        )

    new_result = _new_layer_search(
        query, lang, prompt_text=prompt_text,
        source_image_b64=source_image_b64, source_image_mime=source_image_mime,
        lens_context=lens_context, allow_global=allow_global, english_name=english_name,
    )
    print(f"NEW LAYER DONE offers={len(extract_store_offers(new_result[0])) if new_result[0] else 0}")

    # Services and genuine informational answers should not be forced through product comparison.
    if new_result[0] and (is_service_answer(new_result[0]) or is_informational_answer(new_result[0])):
        if shopping_future:
            shopping_future.cancel()
        return new_result

    def _collect_shopping():
        if not shopping_future:
            return "", {}
        try:
            return shopping_future.result(timeout=90) or ("", {})
        except Exception as e:
            print(f"SHOPPING LAYER ERR: {e}")
            return "", {}

    # For fashion identified by Lens, generic old-layer results are dangerous (e.g. any pajama).
    # Shopping offers passed the Lens-identity filter, so they may still join the merge.
    if lens_context and lens_context.get("force_lens_only"):
        mode = "GLOBAL" if allow_global else "LOCAL"
        print(f"OLD LAYER SKIPPED: FASHION LENS-ONLY {mode} MODE")
        shopping_result = _collect_shopping()
        if shopping_result[0]:
            return _merge_two_layers(query, lang, new_result, ("", {}), lens_context, shopping_result)
        return new_result

    old_result = _old_layer_search(query, lang, prompt_text=prompt_text, lens_context=lens_context, allow_global=allow_global, english_name=english_name)
    print(f"OLD LAYER DONE offers={len(extract_store_offers(old_result[0])) if old_result[0] else 0}")
    shopping_result = _collect_shopping()
    print(f"SHOPPING LAYER DONE offers={len(extract_store_offers(shopping_result[0])) if shopping_result[0] else 0}")
    final_txt, final_urls = _merge_two_layers(query, lang, new_result, old_result, lens_context, shopping_result)
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
    base_en = english_search_name(base)
    market_name = current_market().get("country_name", "Kuwait")
    prompts = [
        (f"المنتج التالي غير متوفر محلياً: {base}" + (f" ({base_en})" if base_en and base_en != base else "") + f". اقترح حتى {MAX_STORES} بدائل مشابهة له فعلياً — نفس الفئة "
         f"ونفس الاستخدام ومستوى جودة قريب — متوفرة الآن في متاجر {market_name} فقط، من أي متجر محلي كان. "
         "لكل بديل: اسم البديل الفعلي (وليس اسم المنتج الأصلي)، سعر رقمي واضح بعملة السوق، "
         f"ورابط صفحة المنتج المباشرة داخل المتجر. رتب من الأرخص إلى الأغلى واكتب السعر بالفلوس كاملة مثل 1.950. {LANG_INSTR[lang]}"),
        (f"{MAX_STORES} best in-stock alternatives similar to {base_en or base} in {market_name} local online stores, "
         f"each with the alternative's own name, a numeric price, and a direct product page link, sorted cheapest first. {LANG_INSTR[lang]}"),
    ]
    for prompt in prompts:
        txt, urls = call_gemini([{"text": prompt}])
        urls = direct_urls_only(urls)
        offers = extract_store_offers(txt)
        if not txt or not offers or not urls:
            continue
        verified = verify_offers(urls, base)
        # v68: البدائل المحلية لا تشمل مواقع أجنبية.
        verified = filter_local_market_only(verified)
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
            if not (matched and is_direct_store_url(matched)):
                continue
            if is_foreign_lens_result({"link": matched, "source": offer["name"], "title": offer["line"]}):
                print(f"SIMILAR LOCAL REJECT FOREIGN: {offer['name']} -> {matched}")
                continue
            kept.append((offer, matched))
        # v68: ترتيب البدائل من الأرخص للأغلى حتى بدون فحص الصفحة.
        kept.sort(key=lambda om: _extract_numeric_price(om[0].get("line", "")) or 10**9)
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
    """يحدد الاسم بالعربي والإنجليزي دائماً، بغض النظر عن لغة واجهة المستخدم."""
    prompts = [
        "حدد المنتج من الشعار والشكل والنص. اكتب الاسم العربي ثم الإنجليزي مفصولين بـ |.",
        "افحص الصورة بدقة أكبر، خصوصاً الشعار والأزرار ورقم الموديل. اكتب Arabic name | English name.",
        "استنتج أقرب اسم تجاري قابل للبحث حتى لو الصورة جزئية. Arabic | English only.",
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




def _identity_tokens(text):
    t = normalize_ar(text or "")
    return {x for x in re.findall(r"[a-z0-9\u0600-\u06ff]+", t) if len(x) > 2}


def identity_candidates_agree(vision_name, lens_title):
    """True when Lens and direct vision clearly describe the same product.

    Avoids a paid judge call when brand/model/type already overlap sufficiently.
    """
    a, b = _identity_tokens(vision_name), _identity_tokens(lens_title)
    if not a or not b:
        return False
    inter = a & b
    # A model/SKU overlap is decisive.
    model_a = {x for x in a if any(c.isdigit() for c in x)}
    model_b = {x for x in b if any(c.isdigit() for c in x)}
    if model_a & model_b:
        return True
    return len(inter) >= 2 and (len(inter) / max(1, min(len(a), len(b)))) >= 0.45




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

def is_generic_commodity(vision_name, caption=""):
    """منتج عام بلا براند أو موديل (كرة سلة عادية، حبل قفز، دمبل...).

    Lens مع هذا النوع يجيب إعلانات عشوائية مشابهة شكلاً (eBay، كرات إسفنجية، مغناطيسات)
    لأن ما فيه هوية بصرية مميزة. البحث النصي بالاسم العام أدق وأرخص، و priority_stores_for
    يوجهه تلقائياً لمتاجر الرياضة المحلية (Intersport / Decathlon / Sun & Sand).
    """
    raw = f"{vision_name or ''} {caption or ''}".strip()
    if not raw:
        return False
    # رقم موديل أو SKU = منتج محدد، مو عام.
    if re.search(r"\b(?=[a-z0-9-]{3,}\b)(?=[a-z0-9-]*[a-z])(?=[a-z0-9-]*\d)[a-z0-9-]+\b", raw, re.I):
        return False
    q = normalize_ar(raw)
    known_brands = (
        "نايك", "nike", "اديداس", "adidas", "سبولدينج", "spalding", "ويلسون", "wilson",
        "مولتن", "molten", "ميكاسا", "mikasa", "بوما", "puma", "ريبوك", "reebok",
        "اندر ارمور", "under armour", "اسيكس", "asics", "ابل", "apple", "سامسونج", "samsung", "سوني", "sony"
    )
    if any(normalize_ar(b) in q for b in known_brands):
        return False
    generic_terms = (
        "كره سله", "basketball", "كره قدم", "football", "soccer ball",
        "كره طايره", "volleyball", "كره تنس", "tennis ball", "كره يد", "handball",
        "حبل قفز", "jump rope", "دمبل", "dumbbell", "سجاده يوغا", "yoga mat",
        "مطاره ماء", "water bottle", "قاروره ماء", "شنطه رياضيه", "gym bag"
    )
    return any(normalize_ar(t) in q for t in generic_terms)

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
    """Lens is the primary engine for most image searches (~70%).

    Only clearly text-heavy packaged/medical/grocery products stay Vision-first,
    plus generic unbranded commodities where Lens returns random lookalike ads.
    """
    raw = f"{vision_name or ''} {caption or ''}".strip()
    q = normalize_ar(raw)
    if not ENABLE_GOOGLE_LENS:
        return False, "LENS_DISABLED"
    if not vision_name:
        return True, "NO_VISION_IDENTITY"

    # Fashion remains a hard Lens-first case.
    if is_fashion_identity(vision_name, caption):
        return True, "FASHION_ALWAYS_LENS"

    # منتج عام (كرة سلة عادية...): Vision-first دائماً — Lens يخربط ويجيب إسفنجيات وإعلانات.
    if is_generic_commodity(vision_name, caption):
        return False, "GENERIC_COMMODITY_VISION_FIRST"

    uncertain = (
        "غير معروف", "منتج غير", "unknown", "unidentified", "possibly", "ربما",
        "قد يكون", "عام", "generic", "لا استطيع", "لا أستطيع"
    )
    if any(x in q for x in uncertain) or len(_identity_tokens(vision_name)) < 2:
        return True, "UNCERTAIN_IDENTITY"

    if LENS_PRIMARY_MODE:
        if LENS_PRIMARY_EXCEPT_TEXT_HEAVY and _is_text_heavy_packaged_product(vision_name, caption):
            return False, "TEXT_HEAVY_PACKAGE_VISION_FIRST"
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
    prompt = (
        f"Google Lens candidate: {lens_title}\n"
        f"Direct vision/OCR candidate: {vision_name}\n"
        "احكم بالاعتماد على الصورة نفسها، وليس على ترتيب Lens."
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

def country_flag_emoji(cc):
    """ISO alpha-2 -> emoji flag. Falls back to globe for unknown codes."""
    cc = str(cc or "").strip().upper()
    if len(cc) == 2 and cc.isalpha():
        try:
            return "".join(chr(127397 + ord(ch)) for ch in cc)
        except Exception:
            pass
    return "🌐"

def _lens_has_price(m):
    return bool(str(m.get("price") or "").strip() or m.get("price_value") not in (None, ""))

def _lens_price_text_local(m, market_rank, lang):
    """Return a clear local-currency price, plus original foreign price when known."""
    raw_price = str(m.get("price") or "").strip()
    price_value = m.get("price_value")
    currency = (m.get("currency") or "").upper().strip()
    if not raw_price and price_value in (None, ""):
        return ""
    if market_rank == 0:
        local_cur = (current_market().get("currency") or "").upper().strip()
        src_local = currency or detect_currency_code(raw_price, local_cur)
        if src_local and local_cur and src_local != local_cur:
            shown, _ = display_global_price(price_value, raw_price, src_local, lang)
            return shown
        return format_lens_price(raw_price, price_value, lang, local_cur or currency or None)

    # لا نفترض CNY لمجرد أن الموقع صيني: AliExpress/Temu كثيراً ما يعرضان USD.
    src = currency or detect_currency_code(raw_price, "")
    if not src:
        src = "USD" if market_rank == 1 else "CNY"
    shown, _ = display_global_price(price_value, raw_price, src, lang)
    return shown

UI_TRANSLATE_CACHE = {}
UI_TRANSLATE_LOCK = threading.Lock()

def translate_ui_titles(titles, lang):
    """ترجمة واجهة العرض فقط. البحث والروابط لا تتغير. أسماء البراند/الموديل تبقى كما هي قدر الإمكان."""
    clean = [re.sub(r"\s+", " ", str(t or "")).strip() for t in titles]
    if not clean or lang == "en":
        return clean
    target = "Arabic" if lang == "ar" else lang
    result = [None] * len(clean)
    missing_idx, missing = [], []
    with UI_TRANSLATE_LOCK:
        for i, t in enumerate(clean):
            key = (lang, t)
            if key in UI_TRANSLATE_CACHE:
                result[i] = UI_TRANSLATE_CACHE[key]
            else:
                missing_idx.append(i)
                missing.append(t)
    if missing:
        system = f"""You translate shopping UI text into {target}.
Translate ONLY the human-readable product description for display.
Do not translate, alter, or localize brand names, model names, SKU codes, sizes, numbers, or store names.
Keep the translation concise.
Return ONLY a JSON array of strings in the same order, no markdown."""
        raw, _ = call_gemini([{"text": json.dumps(missing, ensure_ascii=False)}], system=system, use_search=False)
        translated = []
        try:
            m = re.search(r"\[.*\]", raw or "", flags=re.S)
            parsed = json.loads(m.group(0)) if m else []
            if isinstance(parsed, list):
                translated = [str(x or "").strip() for x in parsed]
        except Exception as e:
            print(f"UI TITLE TRANSLATE PARSE ERR: {e}")
        if len(translated) != len(missing):
            translated = missing
        with UI_TRANSLATE_LOCK:
            if len(UI_TRANSLATE_CACHE) > 5000:
                UI_TRANSLATE_CACHE.clear()
            for idx, original, trans in zip(missing_idx, missing, translated):
                shown = trans or original
                result[idx] = shown
                UI_TRANSLATE_CACHE[(lang, original)] = shown
    return [r or c for r, c in zip(result, clean)]

def send_lens_direct_results(from_number, lens, bot_id, lang, caption=""):
    """v76: CTA-only، مختصر، بأعلام الدول، وترجمة للواجهة فقط.

    الحدود القصوى مستقلة: محلي 5، أمريكا 4، الصين 4.
    لا يوجد حد أدنى أو عدد إلزامي لأي سوق.
    """
    raw_matches = [m for m in (lens.get("matches") or []) if (m.get("title") or "").strip()]
    matches = [m for m in raw_matches if result_market_rank(m) != 99]
    if not matches:
        return False

    # داخل كل سوق: النتائج ذات السعر أولاً، ثم exact/visual، ثم ترتيب Google Lens.
    buckets = {0: [], 1: [], 2: []}
    for m in matches:
        rank = result_market_rank(m)
        if rank in buckets:
            buckets[rank].append(m)
    for rank in buckets:
        buckets[rank].sort(key=lambda m: (
            0 if _lens_has_price(m) else 1,
            0 if m.get("exact") else 1,
            0 if m.get("section") == "visual_matches" else 1,
            int(m.get("position") or 999),
        ))

    # حدود قصوى فقط وليست حصصاً. v79: نتيجة واحدة فقط من كل متجر/merchant.
    # Lens قد يرجّع SHEIN أو Ubuy عدة مرات لنفس المنتج بروابط/عناوين مختلفة؛
    # بما أن الهدف مقارنة المتاجر، نحتفظ بأفضل بطاقة فقط لكل متجر.
    def _merchant_key(m):
        url = (m.get("link") or "").strip()
        source = re.sub(r"\s+", " ", (m.get("source") or "").strip().lower())
        try:
            host = urllib.parse.urlparse(url).netloc.lower().split(":")[0]
            host = host[4:] if host.startswith("www.") else host
        except Exception:
            host = ""

        # توحيد أشهر المتاجر حتى لو جاء source مرة Shein ومرة shein.com.
        known = (
            "shein.com", "aliexpress.com", "temu.com", "alibaba.com", "1688.com",
            "taobao.com", "tmall.com", "amazon.com", "ubuy.com", "westelm.com",
            "hm.com", "wayfair.com",
        )
        for d in known:
            if host == d or host.endswith("." + d) or d in source:
                return d
        if host:
            # host هو المرجع الأقوى للمتاجر غير المعروفة.
            return host
        return re.sub(r"[^a-z0-9]+", "", source) or source

    market_caps = {0: LENS_DIRECT_LOCAL_MAX, 1: LENS_DIRECT_US_MAX, 2: LENS_DIRECT_CN_MAX}
    selected = []
    seen_urls = set()
    seen_merchants = set()
    for rank in (0, 1, 2):
        taken = 0
        cap = market_caps.get(rank, 0)
        if cap <= 0:
            continue
        for m in buckets[rank]:
            url = (m.get("link") or "").strip()
            try:
                host = urllib.parse.urlparse(url).netloc.lower()
            except Exception:
                host = ""
            if not (url.startswith("http") and host and "google." not in host):
                continue
            merchant = _merchant_key(m)
            if url in seen_urls or merchant in seen_merchants:
                print(f"LENS DUP STORE SKIP: merchant={merchant} title={(m.get('title') or '')[:70]}")
                continue
            selected.append(m)
            seen_urls.add(url)
            seen_merchants.add(merchant)
            taken += 1
            if taken >= cap or len(selected) >= LENS_DIRECT_MAX_CTA:
                break
        if len(selected) >= LENS_DIRECT_MAX_CTA:
            break

    if not selected:
        return False

    # الترجمة للواجهة فقط بعد اكتمال البحث والاختيار؛ لا تؤثر على Lens أو Google أو الفلاتر.
    display_titles = translate_ui_titles([(m.get("title") or "").strip() for m in selected], lang)
    for m, display_title in zip(selected, display_titles):
        m["_display_title"] = display_title

    local_cc = (current_market().get("country") or DEFAULT_COUNTRY).lower()
    market_cc = {0: local_cc, 1: "us", 2: "cn"}
    no_price = "السعر غير ظاهر" if lang == "ar" else "Price not shown"

    sent = 0
    market_counts = {0: 0, 1: 0, 2: 0}
    for m in selected:
        market_rank = result_market_rank(m)
        market_counts[market_rank] += 1
        flag = country_flag_emoji(market_cc.get(market_rank, ""))
        source = (m.get("source") or "").strip()
        title = re.sub(r"\s+", " ", (m.get("_display_title") or m.get("title") or "").strip())
        # أقصر عنوان ممكن داخل واتساب، مع بقاء اسم المنتج مفهوماً.
        if len(title) > 105:
            title = title[:102].rstrip(" ,-|—") + "…"
        price_txt = _lens_price_text_local(m, market_rank, lang)

        # شكل مختصر وواضح: العلم + المتجر، المنتج، السعر.
        head = f"{flag} {source}" if source else flag
        body = f"{head}\n{title}"
        if price_txt:
            body += f"\n💰 {price_txt}"
        else:
            body += f"\n💰 {no_price}"

        url = (m.get("link") or "").strip()
        button_source = source or ("المتجر" if lang == "ar" else "Store")
        send_whatsapp_cta(from_number, body[:1000], url, bot_id, f"🛒 {button_source[:18]}")
        sent += 1

    chosen_title = ((lens.get("chosen") or {}).get("title") or selected[0]["title"]).strip()
    LAST_SEARCH[from_number] = {"product": (caption or chosen_title)}
    print(f"LENS DIRECT SENT v79: {sent} CTA; unique_merchants={len(seen_merchants)}; buckets={market_counts}; caps=5/4/4; order=local->us->cn")
    if market_counts[2] == 0:
        print("V77 WARNING: no Chinese-store Lens result survived filters")
    return sent > 0

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

    # v73: Lens المباشر سريع ومحدود زمنياً. إذا لم يرجع نتيجة لا نعيد Lens مرة ثانية في fallback.
    lens_direct_attempted = False
    if LENS_DIRECT_MODE and ENABLE_GOOGLE_LENS and SERPAPI_API_KEY and PUBLIC_BASE_URL:
        lens_direct_attempted = True
        lens_direct = google_lens_lookup(b64, mime, lang, caption, light=True)
        if lens_direct.get("matches"):
            if send_lens_direct_results(from_number, lens_direct, bot_id, lang, caption):
                return
        print("LENS DIRECT MODE: no Google results -> full pipeline fallback")
        send_whatsapp_text(from_number, T(lang, "lens_none"), bot_id)

    # FUSION ROUTER (قوة الخلط):
    # 1) Lens و Vision يشتغلان بالتوازي — لا ننتظر أحدهما ليبدأ الآخر.
    # 2) Lens متعدد التمريرات (products -> all -> wide) = نفس قوة تطبيق Lens.
    # 3) الهوية النهائية = دمج عنوان Lens الدقيق + الاسم العربي/الإنجليزي من Vision،
    #    فيبحث النص بكل المرادفات ويغطي الفهرسة العربية والإنجليزية معاً.
    lens_future = None
    if (not lens_direct_attempted and LENS_PARALLEL_WITH_VISION and ENABLE_GOOGLE_LENS
            and SERPAPI_API_KEY and PUBLIC_BASE_URL):
        lens_future = LENS_POOL.submit(_run_with_market, market, google_lens_lookup, b64, mime, lang, caption)

    vision_name = identify_product_with_retry(b64, mime, lang)
    force_fashion_lens = is_fashion_identity(vision_name, caption)
    use_lens, route_reason = lens_routing_decision(vision_name, caption)
    use_lens = force_fashion_lens or use_lens
    # إذا جرّبنا Lens المباشر بالفعل فلا نكرر نفس الشبكة مرة ثانية؛ نكمل Vision/Text فوراً.
    if lens_direct_attempted:
        use_lens = False
        route_reason = "LENS_DIRECT_ALREADY_ATTEMPTED"

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
        # الراوتر قرر Vision-first (عبوة نصية)؛ نتيجة اللينز المتوازية تُهمل بهدوء.
        lens_future.cancel()

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
    if result_type == "none" and query:
        # كانت هناك عروض لكن كل روابطها غير مباشرة؛ نعرض الخيارات الثلاثة مثل مسار النص تماماً.
        _store_pending_global(from_number, bot_id, lang, query, active_lens, prompt_text if (combined_name and caption) else None)
        send_not_found_choice(from_number, bot_id, lang)
        return
    # v79: لا نرسل الخريطة تلقائياً بعد النتائج. تبقى متاحة فقط إذا طلبها المستخدم صراحة.

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




def _text_shopping_market_matches(query, gl, forced_rank, domain=None, store_label=None, max_cards=18):
    """Google Shopping text pass -> Lens-like cards used by the same v79 CTA renderer.

    Search text is kept exactly in the user's/search language. Translation is display-only later.
    `domain` is used for the four explicit China marketplaces.
    """
    q = _shopping_clean_query(query or "")
    if not q or not SERPAPI_API_KEY:
        return []
    search_q = f"{q} site:{domain}" if domain else q
    cards = _serpapi_shopping_request(search_q, gl, hl="en")
    out, seen = [], set()

    def _append(source, title, url, price_text, price_value, position, currency=""):
        direct = _shopping_direct_url(url)
        if not direct or direct in seen:
            return
        try:
            host = urllib.parse.urlparse(direct).netloc.lower().replace("www.", "")
        except Exception:
            host = ""
        if domain and not _host_matches_any(host, (domain,)):
            return
        src = (source or store_label or host or "Store").strip()
        raw_price = str(price_text or "").strip()
        cur = (currency or detect_currency_code(raw_price, "")).upper().strip()
        # Google Shopping sometimes omits the ISO code while returning a numeric price.
        if not cur:
            if forced_rank == 0:
                cur = (current_market().get("currency") or "").upper().strip()
            elif forced_rank == 1:
                cur = "USD"
            # China marketplaces often expose USD internationally; do not assume CNY unless marked.
            elif forced_rank == 2 and re.search(r"(?:CNY|RMB|¥|￥|人民币)", raw_price, flags=re.I):
                cur = "CNY"
        out.append({
            "title": (title or q).strip(),
            "link": direct,
            "source": store_label or src,
            "position": int(position or len(out) + 1),
            "section": "text_google_shopping",
            "exact": True,
            "thumbnail": "", "image": "",
            "price": raw_price,
            "price_value": price_value,
            "currency": cur,
            "in_stock": None, "condition": "",
            "_forced_market_rank": forced_rank,
            "_shopping_gl": gl,
        })
        seen.add(direct)

    immersive = []
    for pos, card in enumerate(cards[:max_cards], 1):
        title = (card.get("title") or "").strip()
        source = (card.get("source") or store_label or "").strip()
        link = (card.get("link") or "").strip()
        before = len(out)
        if link:
            _append(source, title, link, card.get("price"), card.get("extracted_price"), pos)
        token = (card.get("immersive_product_page_token") or "").strip()
        if token and len(out) == before and not domain:
            immersive.append((pos, title, token))

    # Local/US generic Shopping may hide merchant links behind Immersive Product.
    # Keep this bounded; China site-specific passes deliberately stay direct.
    for pos, title, token in immersive[:max(0, min(IMMERSIVE_LOOKUPS_MAX, 2))]:
        for store in (_immersive_product_stores(token) or []):
            _append(
                store.get("name") or "", title, store.get("link") or "",
                store.get("price") or store.get("total") or "",
                store.get("extracted_price") if store.get("extracted_price") not in (None, "") else store.get("extracted_total"),
                pos,
            )
    return out


def google_shopping_text_lookup(query, lang="ar"):
    """v80 text search: current market -> US -> China marketplaces, all through Google Shopping.

    China is searched explicitly and automatically on AliExpress, Temu, Alibaba and SHEIN.
    Returns a Lens-shaped object so the exact same v79 sorting/dedupe/CTA code is reused.
    """
    q = _shopping_clean_query(query or "")
    if not q or not ENABLE_GOOGLE_SHOPPING or not SERPAPI_API_KEY:
        return {"matches": [], "chosen": {"title": q}, "query": q}

    local_cc = (current_market().get("country") or DEFAULT_COUNTRY).lower()
    jobs = [
        ("local", local_cc, 0, None, None),
    ]
    if local_cc != "us":
        jobs.append(("us", "us", 1, None, None))

    # China: explicit merchant searches, independent of generic Google results.
    china_targets = [
        ("AliExpress", "aliexpress.com"),
        ("Temu", "temu.com"),
        ("Alibaba", "alibaba.com"),
        ("SHEIN", "shein.com"),
    ]
    if local_cc != "cn":
        for label, domain in china_targets:
            jobs.append((f"cn:{label}", "us", 2, domain, label))

    market_snapshot = current_market()
    futures = {}
    for tag, gl, rank, domain, label in jobs:
        fut = TEXT_SHOPPING_POOL.submit(
            _run_with_market, market_snapshot, _text_shopping_market_matches,
            q, gl, rank, domain, label,
        )
        futures[fut] = tag

    matches = []
    for fut, tag in futures.items():
        try:
            part = fut.result(timeout=55) or []
            print(f"TEXT SHOPPING PASS {tag}: {len(part)}")
            matches.extend(part)
        except Exception as e:
            print(f"TEXT SHOPPING PASS ERR {tag}: {e}")

    # Same-size filter where Google titles expose a size/capacity. Unknown sizes are allowed.
    ref_size = extract_pack_size(q)
    if ref_size:
        kept = []
        for m in matches:
            ms = extract_pack_size(m.get("title", ""))
            if sizes_compatible(ref_size, ms):
                kept.append(m)
            else:
                print(f"TEXT SHOPPING SIZE SKIP: {(m.get('title') or '')[:80]}")
        matches = kept

    print(f"TEXT SHOPPING TOTAL: {len(matches)} query={q!r}")
    return {"matches": matches, "chosen": {"title": q}, "query": q, "source": "text_google_shopping"}


def send_text_google_shopping_results(from_number, query, bot_id, lang):
    """Send typed-search results using the exact same UI/order/caps as Lens v79."""
    shopping = google_shopping_text_lookup(query, lang)
    if not shopping.get("matches"):
        return False
    return send_lens_direct_results(from_number, shopping, bot_id, lang, query)


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
        # v80: النص أولاً عبر Google Shopping وبنفس تنسيق Lens v79.
        # البحث يستخدم نص المستخدم نفسه؛ الترجمة تحصل فقط داخل CTA بعد اكتمال البحث.
        if send_text_google_shopping_results(from_number, products[0], bot_id, lang):
            LAST_SEARCH[from_number] = {"product": products[0]}
            return
        # إذا Google Shopping لم يعطِ أي رابط مباشر صالح، نحتفظ بالمسار القديم كـ fallback.
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
        # v79: لا خريطة تلقائية؛ المستخدم يطلب الخريطة عند الحاجة.
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
async def health(): return {"status":"v80 TEXT-GSHOP LENS-CTA LOCAL5-US4-CN4 ALIEXPRESS-TEMU-ALIBABA-SHEIN", "lens_direct_mode":LENS_DIRECT_MODE, "build":BUILD_ID, "location_ttl_hours":LOCATION_TTL_SECONDS//3600}
