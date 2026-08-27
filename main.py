# -*- coding: utf-8 -*-
import os, re, time, base64, requests, json, asyncio, urllib.parse, hashlib, sqlite3, threading
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from bs4 import BeautifulSoup

app = FastAPI()

# Browser frontend (Shopify/findzia.com) may call the same Railway search engine.
_WEB_CORS_ORIGINS = [x.strip() for x in os.environ.get(
    "WEB_ALLOWED_ORIGINS",
    "https://findzia.com,https://www.findzia.com"
).split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_WEB_CORS_ORIGINS,
    allow_origin_regex=os.environ.get(
        "WEB_ALLOWED_ORIGIN_REGEX",
        r"^https://[a-z0-9-]+\.myshopify\.com$"
    ),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
    max_age=86400,
)
BUILD_ID = "v105.1-whatsapp-auto-language-20260827"
print("=" * 70)
print(f"STARTING COOP BOT BUILD: {BUILD_ID}")
print("GLOBAL GEO + IMAGE PROXY/RESCUE -> STRONG LOCAL + US + CHINA | 10 LANGS | WORLD CURRENCIES")
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
PROCESSED_IDS_LOCK = threading.Lock()
IMAGE_BUFFER = defaultdict(lambda: {"images": [], "time": 0, "bot_id": ""})
LAST_SEARCH = {}
USER_LANG = {}
# اللغة تُطلب في أول استخدام فقط؛ السوق والعملة يُحددان تلقائياً من فتح خط WhatsApp.
USER_MARKET = {}
USER_LOCATION_TS = {}
PENDING_ONBOARDING = {}
PENDING_GLOBAL_SEARCH = {}
# نتائج البحث الحالي التي يمكن توسيعها يدوياً إلى دول أخرى بعد العرض.
PENDING_MORE_RESULTS = {}
GLOBAL_PENDING_TTL = max(300, int(os.environ.get("GLOBAL_PENDING_TTL_SECONDS", "900")))
# Recommendation picks should survive normal user delays and transient process restarts.
BRAND_PICK_TTL = max(3600, int(os.environ.get("BRAND_PICK_TTL_HOURS", "6")) * 3600)
LOCATION_TTL_SECONDS = max(3600, int(os.environ.get("LOCATION_TTL_HOURS", "72")) * 3600)
MARKET_CTX = threading.local()
DEFAULT_COUNTRY = os.environ.get("DEFAULT_COUNTRY", "kw").strip().lower() or "kw"
PENDING_IMAGES = defaultdict(lambda: {"images": [], "bot_id": ""})

# v84 latency tuning: single images no longer wait a fixed 4 seconds.
# We debounce briefly so several images sent together still form one batch.
IMAGE_BUFFER_IDLE_SECONDS = max(0.35, float(os.environ.get("IMAGE_BUFFER_IDLE_SECONDS", "0.6")))
IMAGE_BUFFER_MAX_WAIT_SECONDS = max(IMAGE_BUFFER_IDLE_SECONDS, float(os.environ.get("IMAGE_BUFFER_MAX_WAIT_SECONDS", "1.5")))

# Network deadlines are deliberately bounded: a slow upstream should not freeze WhatsApp.
GEMINI_SEARCH_TIMEOUT_SECONDS = max(15, int(os.environ.get("GEMINI_SEARCH_TIMEOUT_SECONDS", "28")))
GEMINI_PLAIN_TIMEOUT_SECONDS = max(8, int(os.environ.get("GEMINI_PLAIN_TIMEOUT_SECONDS", "22")))
SERPAPI_TIMEOUT_SECONDS = max(8, int(os.environ.get("SERPAPI_TIMEOUT_SECONDS", "13")))
MARKET_FALLBACK_TIMEOUT_SECONDS = max(4, int(os.environ.get("MARKET_FALLBACK_TIMEOUT_SECONDS", "6")))
WHATSAPP_TIMEOUT_SECONDS = max(5, int(os.environ.get("WHATSAPP_TIMEOUT_SECONDS", "10")))
RESOLVE_TIMEOUT_SECONDS = max(3, int(os.environ.get("RESOLVE_TIMEOUT_SECONDS", "7")))
FINAL_URL_CACHE_TTL = max(300, int(os.environ.get("FINAL_URL_CACHE_TTL_SECONDS", "3600")))
FINAL_URL_CACHE = {}
FINAL_URL_CACHE_LOCK = threading.Lock()

RESOLVER = ThreadPoolExecutor(max_workers=8)
WORKERS = ThreadPoolExecutor(max_workers=5)
OLD_SEARCH_POOL = ThreadPoolExecutor(max_workers=8)
LENS_POOL = ThreadPoolExecutor(max_workers=4)
# v73: HTTP passes الخاصة بـ Lens لها pool مستقل حتى لا يحصل deadlock عندما google_lens_lookup يعمل داخل LENS_POOL.
LENS_HTTP_POOL = ThreadPoolExecutor(max_workers=12)
MARKET_SUPPLEMENT_POOL = ThreadPoolExecutor(max_workers=3)
OLD_LAYER_DUPLICATES = max(1, min(2, int(os.environ.get("OLD_LAYER_DUPLICATES", "1"))))
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")

OLD_LAYER_ENABLED = env_bool("OLD_LAYER_ENABLED", True)

SEARCH_CACHE = {}
# كاش مختلف حسب نوع الطلب. لأن السعر عنصر أساسي، نضع سقفاً قصيراً للكاش حتى لا
# نعيد سعراً قديماً لساعات حتى لو كانت متغيرات البيئة القديمة مضبوطة على 12h/4h.
_PRODUCT_CACHE_CONFIG = int(os.environ.get("CACHE_TTL_HOURS", "12")) * 3600
_GROCERY_CACHE_CONFIG = int(os.environ.get("GROCERY_CACHE_TTL_HOURS", "4")) * 3600
CACHE_TTL = min(_PRODUCT_CACHE_CONFIG, max(300, int(os.environ.get("PRODUCT_PRICE_CACHE_MINUTES", "30")) * 60))
GROCERY_CACHE_TTL = min(_GROCERY_CACHE_CONFIG, max(300, int(os.environ.get("GROCERY_PRICE_CACHE_MINUTES", "15")) * 60))
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
LENS_DIRECT_MAX_LINES = max(3, min(10, int(os.environ.get("LENS_DIRECT_MAX_LINES", "10"))))
# v76: الحدود القصوى مستقلة وليست حصصاً إلزامية.
# v85.4 Fast caps: المحلي حتى 4، الولايات المتحدة حتى 3، الصين حتى 3.
# هذه حدود قصوى حقيقية حتى لو بقيت Environment Variables القديمة أعلى في Railway.
# يمكن للـ Environment خفض الحد، لكنه لا يستطيع رفعه فوق 4/3/3.
LENS_DIRECT_LOCAL_MAX = max(0, min(4, int(os.environ.get("LENS_DIRECT_LOCAL_MAX", "4"))))
LENS_DIRECT_US_MAX = max(0, min(3, int(os.environ.get("LENS_DIRECT_US_MAX", "3"))))
LENS_DIRECT_CN_MAX = max(0, min(3, int(os.environ.get("LENS_DIRECT_CN_MAX", "3"))))
LENS_DIRECT_MAX_CTA = max(1, int(os.environ.get("LENS_DIRECT_MAX_CTA", str(LENS_DIRECT_LOCAL_MAX + LENS_DIRECT_US_MAX + LENS_DIRECT_CN_MAX))))

# "ابحث أكثر" has its own smaller caps; primary v79 search above stays unchanged.
MORE_LOCAL_MAX = max(0, int(os.environ.get("MORE_LOCAL_MAX", "3")))
MORE_US_MAX = max(0, int(os.environ.get("MORE_US_MAX", "2")))
MORE_CN_MAX = max(0, int(os.environ.get("MORE_CN_MAX", "2")))
MORE_TOTAL_MAX = max(1, MORE_LOCAL_MAX + MORE_US_MAX + MORE_CN_MAX)

LENS_PRIMARY_MODE = env_bool("LENS_PRIMARY_MODE", True)
LENS_PRIMARY_EXCEPT_TEXT_HEAVY = env_bool("LENS_PRIMARY_EXCEPT_TEXT_HEAVY", True)
# قوة Lens الحقيقية تأتي من تعدد التمريرات: products ثم all (visual+exact) ثم بحث واسع بلا قيد دولة.
ENABLE_LENS_WIDE_FALLBACK = env_bool("ENABLE_LENS_WIDE_FALLBACK", True)
LENS_MIN_MATCHES = max(3, min(5, int(os.environ.get("LENS_MIN_MATCHES", "5"))))
# تشغيل Vision و Lens بالتوازي: أسرع وأدق دمج. عطّله إذا تبي توفر كريدت SerpApi للعبوات النصية.
LENS_PARALLEL_WITH_VISION = env_bool("LENS_PARALLEL_WITH_VISION", True)
LENS_RESULT_LIMIT = max(12, int(os.environ.get("LENS_RESULT_LIMIT", "40")))
# v73: حد زمني واضح للينز. تمريرات البلدان تعمل بالتوازي، وليس واحدة وراء الثانية.
LENS_HTTP_TIMEOUT_SECONDS = max(6, int(os.environ.get("LENS_HTTP_TIMEOUT_SECONDS", "13")))
LENS_TOTAL_TIMEOUT_SECONDS = max(8, int(os.environ.get("LENS_TOTAL_TIMEOUT_SECONDS", "12")))
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
LOCAL_SHOPPING_POOL = ThreadPoolExecutor(max_workers=max(4, int(os.environ.get("LOCAL_SHOPPING_WORKERS", "6"))))
LOCAL_SHOPPING_PRIMARY_PASSES = max(1, min(3, int(os.environ.get("LOCAL_SHOPPING_PRIMARY_PASSES", "2"))))
LOCAL_RESULTS_TARGET = max(2, int(os.environ.get("LOCAL_RESULTS_TARGET", "4")))
LOCAL_STORE_RESCUE_MAX = max(0, min(4, int(os.environ.get("LOCAL_STORE_RESCUE_MAX", "3"))))
LOCAL_COUNTRY_RESCUE_ENABLED = env_bool("LOCAL_COUNTRY_RESCUE_ENABLED", True)
LOCAL_COUNTRY_RESCUE_PASSES = max(1, min(2, int(os.environ.get("LOCAL_COUNTRY_RESCUE_PASSES", "1"))))
LOCAL_AI_QUERY_RESCUE_ENABLED = env_bool("LOCAL_AI_QUERY_RESCUE_ENABLED", True)
LOCAL_QUERY_CACHE = {}
LOCAL_QUERY_CACHE_LOCK = threading.Lock()


# ---- Global market detection v85 ----------------------------------------------
# Worldwide market profile: country name + all tender currencies + commerce search language.
# This is intentionally static so Railway does not depend on pycountry/Babel at runtime.
COUNTRY_META = {
    'ae': ('United Arab Emirates', ('AED',), 'en'),
    'af': ('Afghanistan', ('AFN',), 'ps'),
    'ag': ('Antigua and Barbuda', ('XCD',), 'en'),
    'ai': ('Anguilla', ('XCD',), 'en'),
    'al': ('Albania', ('ALL',), 'sq'),
    'am': ('Armenia', ('AMD',), 'hy'),
    'ao': ('Angola', ('AOA',), 'pt'),
    'ar': ('Argentina', ('ARS',), 'es'),
    'as': ('American Samoa', ('USD',), 'en'),
    'at': ('Austria', ('EUR',), 'de'),
    'au': ('Australia', ('AUD',), 'en'),
    'aw': ('Aruba', ('AWG',), 'nl'),
    'az': ('Azerbaijan', ('AZN',), 'az'),
    'ba': ('Bosnia and Herzegovina', ('BAM',), 'bs'),
    'bb': ('Barbados', ('BBD',), 'en'),
    'bd': ('Bangladesh', ('BDT',), 'en'),
    'be': ('Belgium', ('EUR',), 'nl'),
    'bf': ('Burkina Faso', ('XOF',), 'fr'),
    'bg': ('Bulgaria', ('BGN',), 'bg'),
    'bh': ('Bahrain', ('BHD',), 'ar'),
    'bi': ('Burundi', ('BIF',), 'fr'),
    'bj': ('Benin', ('XOF',), 'fr'),
    'bm': ('Bermuda', ('BMD',), 'en'),
    'bn': ('Brunei Darussalam', ('BND',), 'ms'),
    'bo': ('Bolivia, Plurinational State of', ('BOB',), 'es'),
    'br': ('Brazil', ('BRL',), 'pt'),
    'bs': ('Bahamas', ('BSD',), 'en'),
    'bt': ('Bhutan', ('INR', 'BTN'), 'dz'),
    'bw': ('Botswana', ('BWP',), 'en'),
    'by': ('Belarus', ('BYN',), 'ru'),
    'bz': ('Belize', ('BZD',), 'en'),
    'ca': ('Canada', ('CAD',), 'en'),
    'cc': ('Cocos (Keeling) Islands', ('AUD',), 'en'),
    'cd': ('Congo, The Democratic Republic of the', ('CDF',), 'fr'),
    'cf': ('Central African Republic', ('XAF',), 'fr'),
    'cg': ('Congo', ('XAF',), 'fr'),
    'ch': ('Switzerland', ('CHF',), 'de'),
    'ci': ("Côte d'Ivoire", ('XOF',), 'fr'),
    'ck': ('Cook Islands', ('NZD',), 'en'),
    'cl': ('Chile', ('CLP',), 'es'),
    'cm': ('Cameroon', ('XAF',), 'en'),
    'cn': ('China', ('CNY',), 'zh'),
    'co': ('Colombia', ('COP',), 'es'),
    'cr': ('Costa Rica', ('CRC',), 'es'),
    'cu': ('Cuba', ('CUP',), 'es'),
    'cv': ('Cabo Verde', ('CVE',), 'pt'),
    'cx': ('Christmas Island', ('AUD',), 'en'),
    'cy': ('Cyprus', ('EUR',), 'el'),
    'cz': ('Czechia', ('CZK',), 'cs'),
    'de': ('Germany', ('EUR',), 'de'),
    'dj': ('Djibouti', ('DJF',), 'fr'),
    'dk': ('Denmark', ('DKK',), 'da'),
    'dm': ('Dominica', ('XCD',), 'en'),
    'do': ('Dominican Republic', ('DOP',), 'es'),
    'dz': ('Algeria', ('DZD',), 'fr'),
    'ec': ('Ecuador', ('USD',), 'es'),
    'ee': ('Estonia', ('EUR',), 'et'),
    'eg': ('Egypt', ('EGP',), 'ar'),
    'eh': ('Western Sahara', ('MAD',), 'es'),
    'er': ('Eritrea', ('ERN',), 'ti'),
    'es': ('Spain', ('EUR',), 'es'),
    'et': ('Ethiopia', ('ETB',), 'am'),
    'fi': ('Finland', ('EUR',), 'fi'),
    'fj': ('Fiji', ('FJD',), 'en'),
    'fk': ('Falkland Islands (Malvinas)', ('FKP',), 'en'),
    'fm': ('Micronesia, Federated States of', ('USD',), 'en'),
    'fo': ('Faroe Islands', ('DKK',), 'fo'),
    'fr': ('France', ('EUR',), 'fr'),
    'ga': ('Gabon', ('XAF',), 'fr'),
    'gb': ('United Kingdom', ('GBP',), 'en'),
    'gd': ('Grenada', ('XCD',), 'en'),
    'ge': ('Georgia', ('GEL',), 'ka'),
    'gf': ('French Guiana', ('EUR',), 'fr'),
    'gg': ('Guernsey', ('GBP',), 'en'),
    'gh': ('Ghana', ('GHS',), 'en'),
    'gi': ('Gibraltar', ('GIP',), 'en'),
    'gl': ('Greenland', ('DKK',), 'kl'),
    'gm': ('Gambia', ('GMD',), 'en'),
    'gn': ('Guinea', ('GNF',), 'fr'),
    'gp': ('Guadeloupe', ('EUR',), 'fr'),
    'gq': ('Equatorial Guinea', ('XAF',), 'es'),
    'gr': ('Greece', ('EUR',), 'el'),
    'gs': ('South Georgia and the South Sandwich Islands', ('GBP',), 'en'),
    'gt': ('Guatemala', ('GTQ',), 'es'),
    'gu': ('Guam', ('USD',), 'en'),
    'gw': ('Guinea-Bissau', ('XOF',), 'pt'),
    'gy': ('Guyana', ('GYD',), 'en'),
    'hk': ('Hong Kong', ('HKD',), 'en'),
    'hm': ('Heard Island and McDonald Islands', ('AUD',), 'en'),
    'hn': ('Honduras', ('HNL',), 'es'),
    'hr': ('Croatia', ('EUR',), 'hr'),
    'ht': ('Haiti', ('HTG', 'USD'), 'fr'),
    'hu': ('Hungary', ('HUF',), 'hu'),
    'id': ('Indonesia', ('IDR',), 'id'),
    'ie': ('Ireland', ('EUR',), 'en'),
    'il': ('Israel', ('ILS',), 'he'),
    'im': ('Isle of Man', ('GBP',), 'en'),
    'in': ('India', ('INR',), 'en'),
    'io': ('British Indian Ocean Territory', ('USD',), 'en'),
    'iq': ('Iraq', ('IQD',), 'ar'),
    'ir': ('Iran, Islamic Republic of', ('IRR',), 'fa'),
    'is': ('Iceland', ('ISK',), 'is'),
    'it': ('Italy', ('EUR',), 'it'),
    'je': ('Jersey', ('GBP',), 'en'),
    'jm': ('Jamaica', ('JMD',), 'en'),
    'jo': ('Jordan', ('JOD',), 'ar'),
    'jp': ('Japan', ('JPY',), 'ja'),
    'ke': ('Kenya', ('KES',), 'en'),
    'kg': ('Kyrgyzstan', ('KGS',), 'ky'),
    'kh': ('Cambodia', ('KHR',), 'km'),
    'ki': ('Kiribati', ('AUD',), 'en'),
    'km': ('Comoros', ('KMF',), 'ar'),
    'kn': ('Saint Kitts and Nevis', ('XCD',), 'en'),
    'kp': ("Korea, Democratic People's Republic of", ('KPW',), 'ko'),
    'kr': ('Korea, Republic of', ('KRW',), 'ko'),
    'kw': ('Kuwait', ('KWD',), 'ar'),
    'ky': ('Cayman Islands', ('KYD',), 'en'),
    'kz': ('Kazakhstan', ('KZT',), 'ru'),
    'la': ("Lao People's Democratic Republic", ('LAK',), 'lo'),
    'lb': ('Lebanon', ('LBP',), 'ar'),
    'lc': ('Saint Lucia', ('XCD',), 'en'),
    'li': ('Liechtenstein', ('CHF',), 'de'),
    'lk': ('Sri Lanka', ('LKR',), 'si'),
    'lr': ('Liberia', ('LRD',), 'en'),
    'ls': ('Lesotho', ('ZAR', 'LSL'), 'en'),
    'lt': ('Lithuania', ('EUR',), 'lt'),
    'lu': ('Luxembourg', ('EUR',), 'fr'),
    'lv': ('Latvia', ('EUR',), 'lv'),
    'ly': ('Libya', ('LYD',), 'ar'),
    'ma': ('Morocco', ('MAD',), 'fr'),
    'mc': ('Monaco', ('EUR',), 'fr'),
    'md': ('Moldova, Republic of', ('MDL',), 'ro'),
    'mg': ('Madagascar', ('MGA',), 'fr'),
    'mh': ('Marshall Islands', ('USD',), 'en'),
    'mk': ('North Macedonia', ('MKD',), 'mk'),
    'ml': ('Mali', ('XOF',), 'fr'),
    'mn': ('Mongolia', ('MNT',), 'mn'),
    'mo': ('Macao', ('MOP',), 'zh'),
    'mp': ('Northern Mariana Islands', ('USD',), 'en'),
    'mq': ('Martinique', ('EUR',), 'fr'),
    'mr': ('Mauritania', ('MRU',), 'ar'),
    'ms': ('Montserrat', ('XCD',), 'en'),
    'mt': ('Malta', ('EUR',), 'mt'),
    'mu': ('Mauritius', ('MUR',), 'en'),
    'mv': ('Maldives', ('MVR',), 'dv'),
    'mw': ('Malawi', ('MWK',), 'en'),
    'mx': ('Mexico', ('MXN',), 'es'),
    'my': ('Malaysia', ('MYR',), 'en'),
    'mz': ('Mozambique', ('MZN',), 'pt'),
    'na': ('Namibia', ('ZAR', 'NAD'), 'en'),
    'nc': ('New Caledonia', ('XPF',), 'fr'),
    'ne': ('Niger', ('XOF',), 'fr'),
    'nf': ('Norfolk Island', ('AUD',), 'en'),
    'ng': ('Nigeria', ('NGN',), 'en'),
    'ni': ('Nicaragua', ('NIO',), 'es'),
    'nl': ('Netherlands', ('EUR',), 'nl'),
    'no': ('Norway', ('NOK',), 'no'),
    'np': ('Nepal', ('NPR',), 'ne'),
    'nr': ('Nauru', ('AUD',), 'en'),
    'nu': ('Niue', ('NZD',), 'en'),
    'nz': ('New Zealand', ('NZD',), 'en'),
    'om': ('Oman', ('OMR',), 'ar'),
    'pa': ('Panama', ('PAB', 'USD'), 'es'),
    'pe': ('Peru', ('PEN',), 'es'),
    'pf': ('French Polynesia', ('XPF',), 'fr'),
    'pg': ('Papua New Guinea', ('PGK',), 'en'),
    'ph': ('Philippines', ('PHP',), 'en'),
    'pk': ('Pakistan', ('PKR',), 'en'),
    'pl': ('Poland', ('PLN',), 'pl'),
    'pm': ('Saint Pierre and Miquelon', ('EUR',), 'fr'),
    'pn': ('Pitcairn', ('NZD',), 'en'),
    'pr': ('Puerto Rico', ('USD',), 'es'),
    'pt': ('Portugal', ('EUR',), 'pt'),
    'pw': ('Palau', ('USD',), 'en'),
    'py': ('Paraguay', ('PYG',), 'es'),
    'qa': ('Qatar', ('QAR',), 'ar'),
    're': ('Réunion', ('EUR',), 'fr'),
    'ro': ('Romania', ('RON',), 'ro'),
    'rs': ('Serbia', ('RSD',), 'rs'),
    'ru': ('Russian Federation', ('RUB',), 'ru'),
    'rw': ('Rwanda', ('RWF',), 'rw'),
    'sa': ('Saudi Arabia', ('SAR',), 'ar'),
    'sb': ('Solomon Islands', ('SBD',), 'en'),
    'sc': ('Seychelles', ('SCR',), 'fr'),
    'sd': ('Sudan', ('SDG',), 'ar'),
    'se': ('Sweden', ('SEK',), 'sv'),
    'sg': ('Singapore', ('SGD',), 'en'),
    'sh': ('Saint Helena, Ascension and Tristan da Cunha', ('SHP',), 'en'),
    'si': ('Slovenia', ('EUR',), 'sl'),
    'sj': ('Svalbard and Jan Mayen', ('NOK',), 'no'),
    'sk': ('Slovakia', ('EUR',), 'sk'),
    'sl': ('Sierra Leone', ('SLE',), 'en'),
    'sm': ('San Marino', ('EUR',), 'it'),
    'sn': ('Senegal', ('XOF',), 'fr'),
    'so': ('Somalia', ('SOS',), 'so'),
    'sr': ('Suriname', ('SRD',), 'nl'),
    'ss': ('South Sudan', ('SSP',), 'en'),
    'st': ('Sao Tome and Principe', ('STN',), 'pt'),
    'sv': ('El Salvador', ('USD',), 'es'),
    'sy': ('Syrian Arab Republic', ('SYP',), 'ar'),
    'sz': ('Eswatini', ('SZL',), 'en'),
    'td': ('Chad', ('XAF',), 'fr'),
    'tf': ('French Southern Territories', ('EUR',), 'fr'),
    'tg': ('Togo', ('XOF',), 'fr'),
    'th': ('Thailand', ('THB',), 'th'),
    'tj': ('Tajikistan', ('TJS',), 'tg'),
    'tk': ('Tokelau', ('NZD',), 'en'),
    'tl': ('Timor-Leste', ('USD',), 'pt'),
    'tm': ('Turkmenistan', ('TMT',), 'tk'),
    'tn': ('Tunisia', ('TND',), 'fr'),
    'to': ('Tonga', ('TOP',), 'en'),
    'tr': ('Türkiye', ('TRY',), 'tr'),
    'tt': ('Trinidad and Tobago', ('TTD',), 'en'),
    'tv': ('Tuvalu', ('AUD',), 'en'),
    'tw': ('Taiwan, Province of China', ('TWD',), 'zh'),
    'tz': ('Tanzania, United Republic of', ('TZS',), 'en'),
    'ua': ('Ukraine', ('UAH',), 'uk'),
    'ug': ('Uganda', ('UGX',), 'en'),
    'us': ('United States', ('USD',), 'en'),
    'uy': ('Uruguay', ('UYU',), 'es'),
    'uz': ('Uzbekistan', ('UZS',), 'uz'),
    'vc': ('Saint Vincent and the Grenadines', ('XCD',), 'en'),
    've': ('Venezuela, Bolivarian Republic of', ('VES',), 'es'),
    'vn': ('Viet Nam', ('VND',), 'vi'),
    'vu': ('Vanuatu', ('VUV',), 'bi'),
    'wf': ('Wallis and Futuna', ('XPF',), 'fr'),
    'ws': ('Samoa', ('WST',), 'sm'),
    'xk': ('Kosovo', ('EUR',), 'sq'),
    'ye': ('Yemen', ('YER',), 'ar'),
    'yt': ('Mayotte', ('EUR',), 'fr'),
    'za': ('South Africa', ('ZAR',), 'en'),
    'zm': ('Zambia', ('ZMW',), 'en'),
    'zw': ('Zimbabwe', ('USD', 'ZWG'), 'en'),
}

CALLING_CODE_TO_COUNTRY = {
    '1': 'us',
    '7': 'ru',
    '20': 'eg',
    '27': 'za',
    '30': 'gr',
    '31': 'nl',
    '32': 'be',
    '33': 'fr',
    '34': 'es',
    '36': 'hu',
    '39': 'it',
    '40': 'ro',
    '41': 'ch',
    '43': 'at',
    '44': 'gb',
    '45': 'dk',
    '46': 'se',
    '47': 'no',
    '48': 'pl',
    '49': 'de',
    '51': 'pe',
    '52': 'mx',
    '53': 'cu',
    '54': 'ar',
    '55': 'br',
    '56': 'cl',
    '57': 'co',
    '58': 've',
    '60': 'my',
    '61': 'au',
    '62': 'id',
    '63': 'ph',
    '64': 'nz',
    '65': 'sg',
    '66': 'th',
    '76': 'kz',
    '77': 'kz',
    '81': 'jp',
    '82': 'kr',
    '84': 'vn',
    '86': 'cn',
    '90': 'tr',
    '91': 'in',
    '92': 'pk',
    '93': 'af',
    '94': 'lk',
    '98': 'ir',
    '211': 'ss',
    '212': 'ma',
    '213': 'dz',
    '216': 'tn',
    '218': 'ly',
    '220': 'gm',
    '221': 'sn',
    '222': 'mr',
    '223': 'ml',
    '224': 'gn',
    '225': 'ci',
    '226': 'bf',
    '227': 'ne',
    '228': 'tg',
    '229': 'bj',
    '230': 'mu',
    '231': 'lr',
    '232': 'sl',
    '233': 'gh',
    '234': 'ng',
    '235': 'td',
    '236': 'cf',
    '237': 'cm',
    '238': 'cv',
    '239': 'st',
    '240': 'gq',
    '241': 'ga',
    '242': 'cg',
    '243': 'cd',
    '244': 'ao',
    '245': 'gw',
    '246': 'io',
    '248': 'sc',
    '249': 'sd',
    '250': 'rw',
    '251': 'et',
    '252': 'so',
    '253': 'dj',
    '254': 'ke',
    '255': 'tz',
    '256': 'ug',
    '257': 'bi',
    '258': 'mz',
    '260': 'zm',
    '261': 'mg',
    '262': 're',
    '263': 'zw',
    '264': 'na',
    '265': 'mw',
    '266': 'ls',
    '267': 'bw',
    '268': 'sz',
    '269': 'km',
    '290': 'sh',
    '291': 'er',
    '297': 'aw',
    '298': 'fo',
    '299': 'gl',
    '350': 'gi',
    '351': 'pt',
    '352': 'lu',
    '353': 'ie',
    '354': 'is',
    '355': 'al',
    '356': 'mt',
    '357': 'cy',
    '358': 'fi',
    '359': 'bg',
    '370': 'lt',
    '371': 'lv',
    '372': 'ee',
    '373': 'md',
    '374': 'am',
    '375': 'by',
    '377': 'mc',
    '378': 'sm',
    '380': 'ua',
    '381': 'rs',
    '385': 'hr',
    '386': 'si',
    '387': 'ba',
    '389': 'mk',
    '420': 'cz',
    '421': 'sk',
    '423': 'li',
    '500': 'fk',
    '501': 'bz',
    '502': 'gt',
    '503': 'sv',
    '504': 'hn',
    '505': 'ni',
    '506': 'cr',
    '507': 'pa',
    '508': 'pm',
    '509': 'ht',
    '590': 'gp',
    '591': 'bo',
    '592': 'gy',
    '593': 'ec',
    '594': 'gf',
    '595': 'py',
    '596': 'mq',
    '597': 'sr',
    '598': 'uy',
    '670': 'tl',
    '672': 'nf',
    '673': 'bn',
    '674': 'nr',
    '675': 'pg',
    '676': 'to',
    '677': 'sb',
    '678': 'vu',
    '679': 'fj',
    '680': 'pw',
    '681': 'wf',
    '682': 'ck',
    '683': 'nu',
    '685': 'ws',
    '686': 'ki',
    '687': 'nc',
    '688': 'tv',
    '689': 'pf',
    '690': 'tk',
    '691': 'fm',
    '692': 'mh',
    '850': 'kp',
    '852': 'hk',
    '853': 'mo',
    '855': 'kh',
    '856': 'la',
    '880': 'bd',
    '886': 'tw',
    '960': 'mv',
    '961': 'lb',
    '962': 'jo',
    '963': 'sy',
    '964': 'iq',
    '965': 'kw',
    '966': 'sa',
    '967': 'ye',
    '968': 'om',
    '971': 'ae',
    '972': 'il',
    '973': 'bh',
    '974': 'qa',
    '975': 'bt',
    '976': 'mn',
    '977': 'np',
    '992': 'tj',
    '993': 'tm',
    '994': 'az',
    '995': 'ge',
    '996': 'kg',
    '998': 'uz',
    '1242': 'bs',
    '1246': 'bb',
    '1264': 'ai',
    '1268': 'ag',
    '1345': 'ky',
    '1441': 'bm',
    '1473': 'gd',
    '1664': 'ms',
    '1670': 'mp',
    '1671': 'gu',
    '1684': 'as',
    '1758': 'lc',
    '1767': 'dm',
    '1784': 'vc',
    '1787': 'pr',
    '1809': 'do',
    '1829': 'do',
    '1849': 'do',
    '1868': 'tt',
    '1869': 'kn',
    '1876': 'jm',
    '1939': 'pr',
    '4779': 'sj',
}


# +1 is shared by US/Canada/Caribbean. Caribbean full prefixes are already in the table;
# Canada needs area-code refinement because its country calling code is only +1.
NANP_CANADA_AREA_CODES = {
    "204","226","236","249","250","257","263","289","306","343","354","365","367","368",
    "382","403","416","418","428","431","437","438","450","468","474","506","514","519","548",
    "579","581","584","587","604","613","639","647","672","683","705","709","742","753","778",
    "780","782","807","819","825","867","873","879","902","905"
}

# Manual additions missing from the bundled country dataset but relevant to real users.
COUNTRY_META.update({
    "ad": ("Andorra", ("EUR",), "ca"),
    "ax": ("Åland Islands", ("EUR",), "sv"),
    "bq": ("Bonaire, Sint Eustatius and Saba", ("USD",), "nl"),
    "bl": ("Saint Barthélemy", ("EUR",), "fr"),
    "cw": ("Curaçao", ("XCG",), "nl"),
    "mf": ("Saint Martin", ("EUR",), "fr"),
    "mm": ("Myanmar", ("MMK",), "my"),
    "me": ("Montenegro", ("EUR",), "sr"),
    "ps": ("Palestine", ("ILS", "JOD"), "ar"),
    "sx": ("Sint Maarten", ("XCG",), "nl"),
    "tc": ("Turks and Caicos Islands", ("USD",), "en"),
    "va": ("Vatican City", ("EUR",), "it"),
    "vg": ("British Virgin Islands", ("USD",), "en"),
    "vi": ("U.S. Virgin Islands", ("USD",), "en"),
})
CALLING_CODE_TO_COUNTRY.update({
    "376":"ad", "95":"mm", "382":"me", "970":"ps", "383":"xk",
    "5999":"cw", "5997":"bq", "5994":"bq", "5993":"bq", "599":"bq",
    "1721":"sx", "1649":"tc", "1284":"vg", "1340":"vi", "3906698":"va",
    # Shared calling-code refinements where the subscriber prefix is distinctive.
    "441481":"gg", "441534":"je", "441624":"im",
    "35818":"ax", "262269":"yt", "262639":"yt",
    "59059027":"bl", "59059029":"mf",
})

COUNTRY_NAMES = {cc: meta[0] for cc, meta in COUNTRY_META.items()}
COUNTRY_CURRENCY_CODES = {cc: tuple(meta[1]) for cc, meta in COUNTRY_META.items()}
COUNTRY_CURRENCIES = {cc: (meta[1][0] if meta[1] else "") for cc, meta in COUNTRY_META.items()}
COUNTRY_SEARCH_HL = {cc: (meta[2] or "en") for cc, meta in COUNTRY_META.items()}
# ISO alpha-2 matches ccTLD for practically every shopping market; UK is the important exception.
COUNTRY_TLDS = {cc: ((".uk",) if cc == "gb" else (f".{cc}",)) for cc in COUNTRY_META}
# Keep legacy aliases that appear in retail URLs.
COUNTRY_TLDS["gb"] = (".uk", ".co.uk")
COUNTRY_TLDS["us"] = (".us",)

# Currency decimal precision used for retail display. Default is 2 decimals.
CURRENCY_DECIMALS = {
    "AFN":0,"ALL":0,"BHD":3,"BIF":0,"CLP":0,"DJF":0,"GNF":0,"IQD":0,"IRR":0,"ISK":0,
    "JOD":3,"JPY":0,"KMF":0,"KPW":0,"KRW":0,"KWD":3,"LAK":0,"LBP":0,"LYD":3,"MGA":0,
    "OMR":3,"PYG":0,"RSD":0,"RWF":0,"SOS":0,"SYP":0,"TND":3,"UGX":0,"VND":0,"VUV":0,
    "XAF":0,"XOF":0,"XPF":0,"YER":0,
}
THREE_DECIMAL_CURRENCIES = {code for code, digits in CURRENCY_DECIMALS.items() if digits == 3}
ZERO_DECIMAL_CURRENCIES = {code for code, digits in CURRENCY_DECIMALS.items() if digits == 0}


# ---- FX: تحويل الأسعار العالمية إلى عملة المستخدم المحلية -------------------
# نستخدم open.er-api.com (مجاني بدون مفتاح، تحديث يومي، يشمل KWD وكل عملات الخليج).
FX_CACHE = {}
FX_CACHE_LOCK = threading.Lock()
FX_CACHE_TTL = max(3600, int(os.environ.get("FX_CACHE_TTL_HOURS", "12")) * 3600)
FX_API_URL = os.environ.get("FX_API_URL", "https://open.er-api.com/v6/latest/{base}")

CURRENCY_SYMBOL_MAP = {
    "us$":"USD", "€":"EUR", "₹":"INR", "₩":"KRW", "₺":"TRY", "₽":"RUB", "r$":"BRL",
    "a$":"AUD", "c$":"CAD", "hk$":"HKD", "s$":"SGD", "nz$":"NZD", "nt$":"TWD",
    "د.إ":"AED", "ر.س":"SAR", "ر.ق":"QAR", "ر.ع":"OMR", "د.ب":"BHD", "د.ك":"KWD",
    "ج.م":"EGP", "د.أ":"JOD", "₪":"ILS", "₴":"UAH", "₸":"KZT", "₾":"GEL", "₼":"AZN",
    "฿":"THB", "₫":"VND", "₱":"PHP", "₦":"NGN", "₵":"GHS", "৳":"BDT", "₲":"PYG",
    "₭":"LAK", "₮":"MNT", "zł":"PLN", "kč":"CZK", "ft":"HUF",
}
KNOWN_CURRENCY_CODES = set(code for codes in COUNTRY_CURRENCY_CODES.values() for code in codes) | {
    "USD","EUR","GBP","JPY","CNY","INR","AED","SAR","QAR","OMR","BHD","KWD","TRY","EGP",
    "JOD","AUD","CAD","CHF","SEK","NOK","DKK","PLN","RUB","BRL","MXN","ZAR","KRW","SGD",
    "MYR","THB","IDR","PHP","VND","PKR","HKD","NZD","TWD"
}

# Symbols shared by many countries must be interpreted in market context, not hardwired to USD/JPY/GBP.
DOLLAR_LIKE_CODES = {"USD","CAD","AUD","NZD","SGD","HKD","TWD","MXN","ARS","CLP","COP","UYU","BMD","BBD","BSD","BZD","BND","FJD","GYD","JMD","KYD","LRD","NAD","SBD","SRD","TTD","XCD"}
YEN_LIKE_CODES = {"JPY","CNY"}
POUND_LIKE_CODES = {"GBP","EGP","FKP","GIP","SHP","SSP","SYP"}

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

def detect_currency_code(text, fallback="", country_code=None):
    """Detect currency with market-aware handling for ambiguous $, ¥ and £ symbols."""
    hay = str(text or "").strip()
    fallback = (fallback or "").upper().strip()
    if not hay:
        return fallback
    m = re.search(r"\b([A-Z]{3})\b", hay.upper())
    if m and m.group(1) in KNOWN_CURRENCY_CODES:
        return m.group(1)
    low = hay.lower()
    # Explicit multi-character/non-ambiguous symbols first.
    for sym in sorted(CURRENCY_SYMBOL_MAP, key=len, reverse=True):
        if sym in low or sym in hay:
            return CURRENCY_SYMBOL_MAP[sym]
    # Resolve shared symbols from the supplied/local market before applying global defaults.
    cc = (country_code or (current_market().get("country") if "current_market" in globals() else "") or "").lower()
    local_codes = set(COUNTRY_CURRENCY_CODES.get(cc, ()))
    preferred = fallback or (next(iter(local_codes)) if len(local_codes) == 1 else "")
    if "$" in hay:
        if preferred in DOLLAR_LIKE_CODES:
            return preferred
        for code in COUNTRY_CURRENCY_CODES.get(cc, ()):
            if code in DOLLAR_LIKE_CODES:
                return code
        return "USD"
    if "¥" in hay or "￥" in hay:
        if preferred in YEN_LIKE_CODES:
            return preferred
        if "CNY" in local_codes:
            return "CNY"
        if "JPY" in local_codes:
            return "JPY"
        return "JPY"
    if "£" in hay:
        if preferred in POUND_LIKE_CODES:
            return preferred
        for code in COUNTRY_CURRENCY_CODES.get(cc, ()):
            if code in POUND_LIKE_CODES:
                return code
        return "GBP"
    return fallback


def display_global_price(price_value, price_text, currency_code, lang="ar"):
    """السعر العالمي يُعرض دائماً بعملة المستخدم المحلية بالفلوس الكاملة: 1.950 د.ك (6.35 USD).

    إذا تعذر التحويل (عملة مجهولة أو فشل مصدر الصرف) نعرض السعر الأصلي كما ورد بدل إخفاء العرض.
    """
    src = detect_currency_code(f"{currency_code or ''} {price_text or ''}", currency_code, current_market().get("country"))
    numeric = None
    try:
        if price_value not in (None, ""):
            numeric = float(price_value)
    except Exception:
        numeric = None
    if numeric is None:
        try:
            numeric = _extract_numeric_price(str(price_text or ""))
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

def country_currency_codes(cc=None):
    cc = (cc or current_market().get("country") or DEFAULT_COUNTRY).lower()
    return COUNTRY_CURRENCY_CODES.get(cc, tuple(filter(None, (COUNTRY_CURRENCIES.get(cc, ""),))))


def country_search_hl(cc=None):
    cc = (cc or current_market().get("country") or DEFAULT_COUNTRY).lower()
    return COUNTRY_SEARCH_HL.get(cc, "en") or "en"


def country_tlds(cc=None):
    cc = (cc or current_market().get("country") or DEFAULT_COUNTRY).lower()
    return COUNTRY_TLDS.get(cc, (f".{cc}",) if len(cc) == 2 else ())


def infer_country_from_phone(phone):
    """Infer market from WhatsApp international number, including shared calling-code zones."""
    digits = re.sub(r"\D", "", phone or "")
    # International 00 prefix can appear in manually supplied/test values.
    if digits.startswith("00"):
        digits = digits[2:]
    # North American Numbering Plan: Caribbean prefixes are represented as 1xxx in the main table.
    # Canada has only +1, so refine it from the next three digits; otherwise default +1 to US.
    if digits.startswith("1") and len(digits) >= 4:
        full4 = digits[:4]
        if full4 in CALLING_CODE_TO_COUNTRY and full4 != "1":
            return CALLING_CODE_TO_COUNTRY[full4]
        if digits[1:4] in NANP_CANADA_AREA_CODES:
            return "ca"
        return "us"
    # Kazakhstan uses +76/+77 while Russia uses the rest of +7.
    if digits.startswith(("76", "77")):
        return "kz"
    for prefix in sorted(CALLING_CODE_TO_COUNTRY, key=len, reverse=True):
        if digits.startswith(prefix):
            return CALLING_CODE_TO_COUNTRY[prefix]
    return DEFAULT_COUNTRY


# ---- Admin/test market override ------------------------------------------------
# Lets the same WhatsApp number test any market with commands such as:
#   Market Germany
#   Market Japan
#   Market Auto
# The override is stored in user_preferences via USER_MARKET, so Railway restarts/workers
# do not immediately lose the selected test market. Normal users remain phone-prefix based.
MARKET_NAME_ALIASES = {
    "usa": "us", "unitedstates": "us", "america": "us",
    "uk": "gb", "unitedkingdom": "gb", "britain": "gb", "greatbritain": "gb",
    "uae": "ae", "emirates": "ae", "unitedarabemirates": "ae",
    "saudi": "sa", "saudiarabia": "sa",
    "korea": "kr", "southkorea": "kr",
    "russia": "ru", "turkiye": "tr", "turkey": "tr",
    "czechia": "cz", "czechrepublic": "cz",
}

def _norm_market_name(value):
    import unicodedata
    t = unicodedata.normalize("NFKD", str(value or "").strip().casefold())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", t)

def resolve_market_country(value):
    """Resolve ISO-2 code or an English country name/alias to a supported market."""
    raw = str(value or "").strip()
    if not raw:
        return None
    cc = raw.lower()
    if len(cc) == 2 and cc in COUNTRY_NAMES:
        return cc
    key = _norm_market_name(raw)
    if key in MARKET_NAME_ALIASES:
        return MARKET_NAME_ALIASES[key]
    for code, name in COUNTRY_NAMES.items():
        if _norm_market_name(name) == key:
            return code
    return None

def set_market_override(phone, cc):
    load_user_preferences(phone)
    market = dict(USER_MARKET.get(phone) or {})
    market["market_override"] = cc.lower()
    market["market_source"] = "manual_test"
    USER_MARKET[phone] = market
    save_user_preferences(phone)
    return market_for_user(phone)

def clear_market_override(phone):
    load_user_preferences(phone)
    market = dict(USER_MARKET.get(phone) or {})
    market.pop("market_override", None)
    market["market_source"] = "phone_prefix"
    USER_MARKET[phone] = market
    save_user_preferences(phone)
    return market_for_user(phone)

def market_for_user(from_number):
    """Resolve the active worldwide market.

    Normally the WhatsApp calling code is the source of truth. During explicit Market <country>
    testing, a persisted manual override takes precedence until Market Auto is sent.
    """
    market = dict(USER_MARKET.get(from_number) or {})
    override = str(market.get("market_override") or "").strip().lower()
    cc = override if override in COUNTRY_NAMES else (infer_country_from_phone(from_number) or DEFAULT_COUNTRY).lower()
    currencies = COUNTRY_CURRENCY_CODES.get(cc) or tuple(filter(None, (COUNTRY_CURRENCIES.get(cc, ""),)))
    market["country"] = cc
    market["country_name"] = COUNTRY_NAMES.get(cc, cc.upper())
    market["currency"] = currencies[0] if currencies else ""
    market["currencies"] = list(currencies)
    market["search_hl"] = COUNTRY_SEARCH_HL.get(cc, "en")
    market["tlds"] = list(country_tlds(cc))
    market["market_source"] = "manual_test" if override else "phone_prefix"
    market.pop("lat", None)
    market.pop("lng", None)
    market.pop("city", None)
    return market


def activate_market(from_number):
    market = market_for_user(from_number)
    MARKET_CTX.value = market
    USER_MARKET[from_number] = market
    USER_LOCATION_TS[from_number] = time.time()
    return market


def ensure_market_from_phone(from_number, persist=False):
    before = dict(USER_MARKET.get(from_number) or {})
    market = activate_market(from_number)
    changed = any(before.get(k) != market.get(k) for k in ("country", "country_name", "currency", "market_source"))
    if persist and changed:
        save_user_preferences(from_number)
    return market


def current_market():
    base_cc = DEFAULT_COUNTRY
    base_codes = COUNTRY_CURRENCY_CODES.get(base_cc) or (COUNTRY_CURRENCIES.get(base_cc, "KWD"),)
    return getattr(MARKET_CTX, "value", None) or {
        "country": base_cc,
        "country_name": COUNTRY_NAMES.get(base_cc, "Kuwait"),
        "currency": base_codes[0] if base_codes else "KWD",
        "currencies": list(base_codes),
        "search_hl": COUNTRY_SEARCH_HL.get(base_cc, "ar"),
        "tlds": list(country_tlds(base_cc)),
    }


def _run_with_market(market, fn, *args, **kwargs):
    MARKET_CTX.value = market
    return fn(*args, **kwargs)


def currency_label(lang="ar"):
    code = current_market().get("currency") or ""
    # Keep the familiar Kuwait label for Arabic; ISO codes are clearer and universal elsewhere.
    if lang == "ar" and code == "KWD":
        return "د.ك"
    return code or ""


def market_instruction():
    m = current_market()
    cc = (m.get("country") or DEFAULT_COUNTRY).lower()
    country = m.get("country_name") or COUNTRY_NAMES.get(cc, cc.upper())
    currency = m.get("currency") or "local currency"
    currencies = ", ".join(m.get("currencies") or country_currency_codes(cc)) or currency
    hl = m.get("search_hl") or country_search_hl(cc)
    tlds = ", ".join(country_tlds(cc))
    priority = priority_stores_for("") if "priority_stores_for" in globals() else []
    stores = ", ".join(priority[:6]) if priority else "the strongest local specialist retailers and marketplaces"
    kuwait_extra = ""
    if cc == "kw":
        # Preserve the exact Kuwait strength from the original bot instead of replacing it with a generic global rule.
        kuwait_extra = (
            " Kuwait premium local discovery: actively check Pro Sports, Intersport, Decathlon, Sun & Sand Sports for sports; "
            "Xcite, Eureka Kuwait, Best Al-Yousifi, Blink, Jarir and 3RoodQ8 for electronics/gaming; Tigro and Toys R Us for toys; "
            "Jm3eia, Lulu, Carrefour and Taw9eel for grocery, plus any smaller Kuwait merchant indexed by Google Shopping."
        )
    return (
        f"\nIMPORTANT CURRENT USER MARKET: {country} (ISO country {cc.upper()}, Google gl={cc}, preferred hl={hl}). "
        f"Accepted local currencies: {currencies}; primary display currency: {currency}; local ccTLD evidence: {tlds}. "
        "LOCAL RESULTS ARE THE CORE PRODUCT: exhaust the local market before relying on foreign results. "
        f"Search the product using the user's wording, its commercial English name, and when useful the main local commerce language ({hl}). "
        f"Prioritize {stores}, but never limit discovery to a fixed list: include small genuine local merchants indexed in Google Shopping/Search. "
        "Use geography in this exact order: (1) the user's local country, (2) United States, (3) China only. Reject every fourth country. "
        "Do not move a cheaper US/China offer above a genuine local offer. Foreign stores do not need to ship locally. "
        "Treat Heureka/heureka.cz/heureka.sk as blocked comparison sites in every market; do NOT confuse them with Eureka Kuwait. "
        "A local .com merchant is valid when Google local targeting, local currency, country text/path, or merchant evidence clearly ties it to the user's market. "
        + kuwait_extra + "\n"
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
# v79.4: نسمح حتى نتيجتين من نفس المتجر/الدومين، ونحاول حذف صفحات المنتج المؤكد نفادها.
RESULTS_PER_STORE_MAX = max(1, int(os.environ.get("RESULTS_PER_STORE_MAX", "1")))
ENABLE_RESULT_STOCK_CHECK = env_bool("ENABLE_RESULT_STOCK_CHECK", True)
# Normal result cards use stock metadata/cache only. Live merchant-page GETs are opt-in because
# they can add several seconds and some stores intentionally block bots.
ENABLE_LIVE_STOCK_NETWORK_CHECK = env_bool("ENABLE_LIVE_STOCK_NETWORK_CHECK", False)
# Deep merchant HTML verification is also opt-in; grounded/Lens data is the normal fast path.
ENABLE_LIVE_PAGE_VERIFICATION = env_bool("ENABLE_LIVE_PAGE_VERIFICATION", False)
LISTING_URL_PARTS = ["/search","/s?","/category","/categories","/collection","/collections","/shop/category","?q=","/search_results","/shop/","/listing","/c/"]

# v80: مواقع/مصادر ممنوعة من الظهور نهائياً في بطاقات النتائج.
# مهم: Heureka (بحرف H) موقع مقارنة تشيكي/سلوفاكي؛ لا تخلطه مع Eureka الكويتية.
BLOCKED_STORE_DOMAINS = ("heureka.cz", "heureka.sk", "heureka.group")
BLOCKED_STORE_NAME_TOKENS = ("heureka",)

def is_blocked_store(name="", url=""):
    name_norm = re.sub(r"[^a-z0-9]+", "", str(name or "").lower())
    if any(tok in name_norm for tok in BLOCKED_STORE_NAME_TOKENS):
        return True
    try:
        host = urllib.parse.urlparse(str(url or "")).netloc.lower().split(":")[0]
        host = host[4:] if host.startswith("www.") else host
    except Exception:
        host = ""
    return any(host == d or host.endswith("." + d) for d in BLOCKED_STORE_DOMAINS)

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
    digits = int(CURRENCY_DECIMALS.get(code, 2))
    return f"{pf:.{digits}f}"


def format_lens_price(price_text, price_value, lang="ar", currency_code=None):
    """Normalise Lens prices with full fils digits: 1.95 KWD -> 1.950 د.ك."""
    numeric = None
    try:
        if price_value not in (None, ""):
            numeric = float(price_value)
    except Exception:
        numeric = None
    if numeric is None:
        try:
            numeric = _extract_numeric_price(str(price_text or ""))
        except Exception:
            numeric = None
    if numeric is None:
        return str(price_text or "").strip()
    label = currency_label(lang)
    return f"{format_price(numeric, currency_code)} {label}"

def is_direct_store_url(url):
    """يمنع روابط Google والبحث والتصنيفات والمصادر المحظورة؛ يقبل صفحات المتاجر المباشرة فقط."""
    if not url or not url.startswith(("http://", "https://")):
        return False
    if is_blocked_store("", url):
        print(f"BLOCKED STORE URL: {url[:120]}")
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
    return {
        name: url for name, url in (urls or {}).items()
        if not is_blocked_store(name, url) and is_direct_store_url(url)
    }

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
    return hashlib.sha256(f"v85-global-geo|{market}|{norm}|{lang}".encode()).hexdigest()

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
    """v81 compatibility shim: market is valid as soon as phone prefix can be resolved."""
    load_user_preferences(phone)
    market = ensure_market_from_phone(phone, persist=False)
    return bool(market.get("country"))

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
        "identifying": "✨ ثواني.. أحدد المنتج وأدور لك أفضل الخيارات.",
        "searching": "🔎 أدور لك على {q}...",
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
        "lens_header": "✨ لقيت لك هالنتائج المطابقة:",
        "lens_none": "🔎 ما لقيت نتائج كافية من الصورة، بجرب لك طريقة ثانية...",
        "market_from_phone": "✅ تم تحديد بلدك من رقم WhatsApp: {country}",
    },
    "en": {
        "identifying": "✨ One moment.. identifying the product and finding the best options.",
        "searching": "🔎 Looking for {q}...",
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
        "lens_header": "✨ Here are the matching results I found:",
        "lens_none": "🔎 I didn’t find enough results from the image, trying another method...",
        "market_from_phone": "✅ Your country is set from your WhatsApp number: {country}",
    },
}

# v82: 10-language UI. Hindi and Urdu intentionally appear last in the WhatsApp selector.
MSG["hi"] = {
    "identifying": "✨ एक पल... प्रोडक्ट पहचान रहा हूँ और सबसे अच्छे विकल्प ढूँढ रहा हूँ।",
    "searching": "🔎 {q} ढूँढ रहा हूँ...",
    "not_found": "अभी पक्की कीमत के साथ उपलब्ध नतीजा नहीं मिला 😅 नाम थोड़ा अलग लिखें या साफ़ फोटो भेजें।",
    "identified_not_found": "मैंने प्रोडक्ट ({p}) पहचान लिया, लेकिन अभी पक्की कीमत नहीं मिली 😅 नाम दूसरी तरह लिखकर देखें।",
    "cant_identify": "कई बार कोशिश की, लेकिन प्रोडक्ट ठीक से पहचान नहीं पाया या पक्का नतीजा नहीं मिला। साफ़ फोटो भेजें या प्रोडक्ट का नाम लिखें।",
    "image_error": "फोटो लोड करते समय छोटी-सी समस्या हुई 😅 कृपया फोटो दोबारा भेजें।",
    "multi_text": "ठीक है, {c} प्रोडक्ट मिले। कार्ट बना रहा हूँ...",
    "multi_images": "अच्छा, {c} प्रोडक्ट पहचान लिए। कार्ट बना रहा हूँ...",
    "maps_body": "📍 आस-पास कहाँ मिलता है देखना है? नीचे बटन दबाकर मैप खोलें 👇",
    "maps_btn": "📍 मैप खोलें",
    "maps_body_loc": "📍 आपकी पिछली खोज ({p}) थी। नीचे बटन दबाकर आस-पास के स्टोर देखें 👇",
    "no_saved_product": "अभी कोई प्रोडक्ट सेव नहीं है 😅 पहले किसी प्रोडक्ट की खोज करें।",
    "lang_saved": "ठीक है, अब से मैं हिंदी में बात करूँगा 🇮🇳\nप्रोडक्ट की फोटो भेजें या नाम लिखें।",
    "ask_global": "आपके देश में पक्का नतीजा नहीं मिला। क्या अंतरराष्ट्रीय स्टोर में खोजूँ? 🌍",
    "global_yes": "हाँ, दुनिया भर में खोजें 🌍",
    "global_no": "नहीं, केवल स्थानीय",
    "global_searching": "🌍 अंतरराष्ट्रीय स्टोर में सबसे मिलते-जुलते नतीजे ढूँढ रहा हूँ...",
    "global_none": "अंतरराष्ट्रीय खोज में भी पक्का सीधा नतीजा नहीं मिला।",
    "ask_not_found": "यह बिल्कुल वही प्रोडक्ट स्थानीय रूप से नहीं मिला 😅\n\nआप क्या करना चाहेंगे? 👇",
    "opt_global": "🌍 दुनिया भर में खोजें",
    "opt_similar": "🔄 मिलते-जुलते विकल्प",
    "opt_no": "नहीं धन्यवाद 🙏",
    "similar_searching": "🔄 आपके लिए सबसे अच्छे मिलते-जुलते विकल्प ढूँढ रहा हूँ...",
    "similar_none": "अभी पक्की कीमत के साथ मिलते-जुलते विकल्प नहीं मिले 😅 दूसरी तरह लिखकर देखें।",
    "declined_ok": "ठीक है 🙏 जब चाहें मैं यहाँ हूँ!",
    "welcome_reply": "नमस्ते! 🌟\nप्रोडक्ट की फोटो भेजें या नाम लिखें, मैं कीमतें और अच्छे स्टोर ढूँढ दूँगा 🛒",
    "thanks_reply": "आपका स्वागत है! 🌹 अगला प्रोडक्ट भेज दीजिए।",
    "lens_header": "✨ ये मिलते-जुलते नतीजे मिले:",
    "lens_none": "🔎 फोटो से पर्याप्त नतीजे नहीं मिले, दूसरी विधि आज़मा रहा हूँ...",
    "market_from_phone": "✅ आपका देश WhatsApp नंबर से तय कर दिया गया है: {country}",
}

MSG["ur"] = {
    "identifying": "✨ ایک لمحہ... پروڈکٹ پہچان رہا ہوں اور بہترین آپشنز تلاش کر رہا ہوں۔",
    "searching": "🔎 {q} تلاش کر رہا ہوں...",
    "not_found": "ابھی تصدیق شدہ قیمت کے ساتھ دستیاب نتیجہ نہیں ملا 😅 نام مختلف انداز میں لکھیں یا صاف تصویر بھیجیں۔",
    "identified_not_found": "میں نے پروڈکٹ ({p}) پہچان لیا، مگر ابھی تصدیق شدہ قیمت نہیں ملی 😅 نام دوسری طرح لکھ کر دیکھیں۔",
    "cant_identify": "کئی بار کوشش کی، مگر پروڈکٹ درست طور پر پہچان نہیں سکا یا پکا نتیجہ نہیں ملا۔ صاف تصویر بھیجیں یا پروڈکٹ کا نام لکھیں۔",
    "image_error": "تصویر لوڈ کرتے وقت معمولی مسئلہ ہوا 😅 براہِ کرم دوبارہ بھیجیں۔",
    "multi_text": "ٹھیک ہے، {c} پروڈکٹس مل گئے۔ کارٹ بنا رہا ہوں...",
    "multi_images": "اچھا، {c} پروڈکٹس پہچان لیے۔ کارٹ بنا رہا ہوں...",
    "maps_body": "📍 قریب کہاں ملتا ہے؟ نیچے بٹن دبا کر نقشہ کھولیں 👇",
    "maps_btn": "📍 نقشہ کھولیں",
    "maps_body_loc": "📍 آپ کی آخری تلاش ({p}) تھی۔ نیچے بٹن دبا کر قریب کے اسٹور دیکھیں 👇",
    "no_saved_product": "ابھی کوئی پروڈکٹ محفوظ نہیں 😅 پہلے کسی پروڈکٹ کی تلاش کریں۔",
    "lang_saved": "ٹھیک ہے، اب سے میں اردو میں بات کروں گا 🇵🇰\nپروڈکٹ کی تصویر بھیجیں یا نام لکھیں۔",
    "ask_global": "آپ کے ملک میں تصدیق شدہ نتیجہ نہیں ملا۔ کیا بین الاقوامی اسٹورز میں تلاش کروں؟ 🌍",
    "global_yes": "ہاں، دنیا بھر میں تلاش کریں 🌍",
    "global_no": "نہیں، صرف مقامی",
    "global_searching": "🌍 بین الاقوامی اسٹورز میں قریب ترین نتائج تلاش کر رہا ہوں...",
    "global_none": "بین الاقوامی تلاش میں بھی تصدیق شدہ براہِ راست نتیجہ نہیں ملا۔",
    "ask_not_found": "یہ بالکل وہی پروڈکٹ مقامی طور پر نہیں ملا 😅\n\nآپ کیا کرنا چاہیں گے؟ 👇",
    "opt_global": "🌍 دنیا بھر میں تلاش کریں",
    "opt_similar": "🔄 ملتے جلتے متبادل",
    "opt_no": "نہیں شکریہ 🙏",
    "similar_searching": "🔄 آپ کے لیے بہترین ملتے جلتے متبادل تلاش کر رہا ہوں...",
    "similar_none": "ابھی تصدیق شدہ قیمت کے ساتھ ملتے جلتے متبادل نہیں ملے 😅 دوسری طرح لکھ کر دیکھیں۔",
    "declined_ok": "ٹھیک ہے 🙏 جب چاہیں میں حاضر ہوں!",
    "welcome_reply": "السلام علیکم! 🌟\nپروڈکٹ کی تصویر بھیجیں یا نام لکھیں، میں بہترین قیمتیں اور اسٹورز تلاش کر دوں گا 🛒",
    "thanks_reply": "خوش آمدید! 🌹 اگلا پروڈکٹ بھیج دیں۔",
    "lens_header": "✨ یہ ملتے جلتے نتائج ملے:",
    "lens_none": "🔎 تصویر سے کافی نتائج نہیں ملے، دوسرا طریقہ آزما رہا ہوں...",
    "market_from_phone": "✅ آپ کا ملک WhatsApp نمبر سے طے کیا گیا ہے: {country}",
}


MSG["fr"] = {
    "identifying": "✨ Un instant… j’identifie le produit et je cherche les meilleures options.",
    "searching": "🔎 Je cherche {q}…",
    "not_found": "Je n’ai pas trouvé de résultat disponible avec un prix fiable 😅 essayez une autre formulation ou une photo plus nette.",
    "identified_not_found": "J’ai identifié le produit ({p}), mais je n’ai pas trouvé de prix fiable pour le moment 😅 essayez d’écrire son nom autrement.",
    "cant_identify": "J’ai essayé plusieurs fois, mais je n’ai pas pu identifier le produit ni trouver un résultat fiable. Envoyez une photo plus nette ou écrivez le nom du produit.",
    "image_error": "Un petit problème est survenu pendant le chargement de l’image 😅 renvoyez-la s’il vous plaît.",
    "multi_text": "Parfait, j’ai trouvé {c} produits. Je prépare le panier…",
    "multi_images": "Parfait, j’ai repéré {c} produits. Je prépare le panier…",
    "maps_body": "📍 Vous voulez voir où le trouver à proximité ? Ouvrez la carte ci-dessous 👇",
    "maps_btn": "📍 Ouvrir la carte",
    "maps_body_loc": "📍 Votre dernière recherche était ({p}). Ouvrez la carte pour voir les magasins à proximité 👇",
    "no_saved_product": "Je n’ai aucun produit enregistré pour le moment 😅 recherchez d’abord un produit.",
    "lang_saved": "Parfait, je vous répondrai désormais en français 🇫🇷\nEnvoyez une photo du produit ou écrivez son nom.",
    "ask_global": "Je n’ai pas trouvé de résultat local fiable. Voulez-vous que je cherche dans les boutiques internationales ? 🌍",
    "global_yes": "Oui, chercher à l’international 🌍",
    "global_no": "Non, local uniquement",
    "global_searching": "🌍 Je cherche les meilleures correspondances dans les boutiques internationales…",
    "global_none": "Je n’ai pas trouvé non plus de résultat international direct et fiable.",
    "ask_not_found": "Je n’ai pas trouvé exactement ce produit localement 😅\n\nQue voulez-vous faire ? 👇",
    "opt_global": "🌍 Chercher à l’international",
    "opt_similar": "🔄 Alternatives similaires",
    "opt_no": "Non merci 🙏",
    "similar_searching": "🔄 Je cherche les meilleures alternatives similaires disponibles…",
    "similar_none": "Je n’ai pas trouvé d’alternative similaire avec un prix fiable pour le moment 😅 essayez une autre formulation.",
    "declined_ok": "Très bien 🙏 je reste disponible si vous avez besoin d’autre chose !",
    "welcome_reply": "Bonjour ! 🌟\nEnvoyez une photo du produit ou écrivez son nom, et je trouverai les meilleurs prix et magasins 🛒",
    "thanks_reply": "Avec plaisir ! 🌹 Envoyez-moi le prochain produit quand vous voulez.",
    "lens_header": "✨ Voici les résultats correspondants que j’ai trouvés :",
    "lens_none": "🔎 Je n’ai pas trouvé assez de résultats à partir de l’image, j’essaie une autre méthode…",
    "market_from_phone": "✅ Votre pays a été défini à partir de votre numéro WhatsApp : {country}",
}

MSG["es"] = {
    "identifying": "✨ Un momento… estoy identificando el producto y buscando las mejores opciones.",
    "searching": "🔎 Buscando {q}…",
    "not_found": "No encontré un resultado disponible con un precio fiable 😅 prueba otra forma de escribirlo o envía una foto más clara.",
    "identified_not_found": "Identifiqué el producto ({p}), pero ahora mismo no encontré un precio fiable 😅 prueba a escribir el nombre de otra forma.",
    "cant_identify": "Lo intenté varias veces, pero no pude identificar el producto ni encontrar un resultado fiable. Envía una foto más clara o escribe el nombre del producto.",
    "image_error": "Hubo un pequeño problema al cargar la imagen 😅 vuelve a enviarla, por favor.",
    "multi_text": "Perfecto, encontré {c} productos. Preparando el carrito…",
    "multi_images": "Perfecto, detecté {c} productos. Preparando el carrito…",
    "maps_body": "📍 ¿Quieres ver dónde encontrarlo cerca? Abre el mapa de abajo 👇",
    "maps_btn": "📍 Abrir mapa",
    "maps_body_loc": "📍 Tu última búsqueda fue ({p}). Abre el mapa para ver tiendas cercanas 👇",
    "no_saved_product": "Todavía no tengo ningún producto guardado 😅 busca un producto primero.",
    "lang_saved": "Perfecto, a partir de ahora te responderé en español 🇪🇸\nEnvía una foto del producto o escribe su nombre.",
    "ask_global": "No encontré un resultado local fiable. ¿Quieres que busque en tiendas internacionales? 🌍",
    "global_yes": "Sí, buscar internacionalmente 🌍",
    "global_no": "No, solo local",
    "global_searching": "🌍 Buscando las mejores coincidencias en tiendas internacionales…",
    "global_none": "Tampoco encontré un resultado internacional directo y fiable.",
    "ask_not_found": "No encontré exactamente este producto a nivel local 😅\n\n¿Qué quieres hacer? 👇",
    "opt_global": "🌍 Buscar internacionalmente",
    "opt_similar": "🔄 Alternativas similares",
    "opt_no": "No, gracias 🙏",
    "similar_searching": "🔄 Buscando las mejores alternativas similares disponibles…",
    "similar_none": "Ahora mismo no encontré alternativas similares con un precio fiable 😅 prueba otra forma de buscar.",
    "declined_ok": "Perfecto 🙏 aquí estoy cuando necesites algo más.",
    "welcome_reply": "¡Hola! 🌟\nEnvía una foto del producto o escribe su nombre y buscaré los mejores precios y tiendas 🛒",
    "thanks_reply": "¡De nada! 🌹 Envíame el siguiente producto cuando quieras.",
    "lens_header": "✨ Estos son los resultados coincidentes que encontré:",
    "lens_none": "🔎 No encontré suficientes resultados con la imagen; probaré otro método…",
    "market_from_phone": "✅ Tu país se ha definido a partir de tu número de WhatsApp: {country}",
}

MSG["pt"] = {
    "identifying": "✨ Um momento… estou identificando o produto e procurando as melhores opções.",
    "searching": "🔎 Procurando {q}…",
    "not_found": "Não encontrei um resultado disponível com preço confiável 😅 tente escrever de outra forma ou envie uma foto mais nítida.",
    "identified_not_found": "Identifiquei o produto ({p}), mas não encontrei um preço confiável agora 😅 tente escrever o nome de outra forma.",
    "cant_identify": "Tentei várias vezes, mas não consegui identificar o produto nem encontrar um resultado confiável. Envie uma foto mais nítida ou escreva o nome do produto.",
    "image_error": "Houve um pequeno problema ao carregar a imagem 😅 envie-a novamente, por favor.",
    "multi_text": "Perfeito, encontrei {c} produtos. Montando o carrinho…",
    "multi_images": "Perfeito, identifiquei {c} produtos. Montando o carrinho…",
    "maps_body": "📍 Quer ver onde encontrar perto de você? Abra o mapa abaixo 👇",
    "maps_btn": "📍 Abrir mapa",
    "maps_body_loc": "📍 Sua última busca foi ({p}). Abra o mapa para ver lojas próximas 👇",
    "no_saved_product": "Ainda não tenho nenhum produto salvo 😅 pesquise um produto primeiro.",
    "lang_saved": "Perfeito, a partir de agora vou responder em português 🇵🇹\nEnvie uma foto do produto ou escreva o nome.",
    "ask_global": "Não encontrei um resultado local confiável. Quer que eu pesquise em lojas internacionais? 🌍",
    "global_yes": "Sim, pesquisar internacionalmente 🌍",
    "global_no": "Não, apenas local",
    "global_searching": "🌍 Procurando as melhores correspondências em lojas internacionais…",
    "global_none": "Também não encontrei um resultado internacional direto e confiável.",
    "ask_not_found": "Não encontrei exatamente este produto localmente 😅\n\nO que você gostaria de fazer? 👇",
    "opt_global": "🌍 Pesquisar internacionalmente",
    "opt_similar": "🔄 Alternativas semelhantes",
    "opt_no": "Não, obrigado 🙏",
    "similar_searching": "🔄 Procurando as melhores alternativas semelhantes disponíveis…",
    "similar_none": "Não encontrei alternativas semelhantes com preço confiável agora 😅 tente outra busca.",
    "declined_ok": "Tudo certo 🙏 estou aqui quando precisar.",
    "welcome_reply": "Olá! 🌟\nEnvie uma foto do produto ou escreva o nome e eu encontro os melhores preços e lojas 🛒",
    "thanks_reply": "De nada! 🌹 Envie o próximo produto quando quiser.",
    "lens_header": "✨ Estes são os resultados correspondentes que encontrei:",
    "lens_none": "🔎 Não encontrei resultados suficientes pela imagem; vou tentar outro método…",
    "market_from_phone": "✅ Seu país foi definido a partir do seu número do WhatsApp: {country}",
}

MSG["tr"] = {
    "identifying": "✨ Bir saniye… ürünü tanımlıyor ve en iyi seçenekleri arıyorum.",
    "searching": "🔎 {q} aranıyor…",
    "not_found": "Doğrulanabilir fiyatı olan uygun bir sonuç bulamadım 😅 farklı bir ifadeyle deneyin veya daha net bir fotoğraf gönderin.",
    "identified_not_found": "Ürünü ({p}) tanımladım ancak şu anda güvenilir bir fiyat bulamadım 😅 adını farklı şekilde yazmayı deneyin.",
    "cant_identify": "Birkaç kez denedim ancak ürünü tanımlayamadım veya güvenilir bir sonuç bulamadım. Daha net bir fotoğraf gönderin ya da ürün adını yazın.",
    "image_error": "Görsel yüklenirken küçük bir sorun oluştu 😅 lütfen tekrar gönderin.",
    "multi_text": "Tamam, {c} ürün buldum. Sepeti hazırlıyorum…",
    "multi_images": "Tamam, {c} ürün tespit ettim. Sepeti hazırlıyorum…",
    "maps_body": "📍 Yakında nerede bulabileceğinizi görmek ister misiniz? Aşağıdaki haritayı açın 👇",
    "maps_btn": "📍 Haritayı aç",
    "maps_body_loc": "📍 Son aramanız ({p}) idi. Yakındaki mağazaları görmek için haritayı açın 👇",
    "no_saved_product": "Henüz kayıtlı bir ürün yok 😅 önce bir ürün arayın.",
    "lang_saved": "Harika, bundan sonra Türkçe yanıt vereceğim 🇹🇷\nÜrünün fotoğrafını gönderin veya adını yazın.",
    "ask_global": "Yerel olarak güvenilir bir sonuç bulamadım. Uluslararası mağazalarda arayayım mı? 🌍",
    "global_yes": "Evet, dünya çapında ara 🌍",
    "global_no": "Hayır, yalnızca yerel",
    "global_searching": "🌍 Uluslararası mağazalarda en iyi eşleşmeleri arıyorum…",
    "global_none": "Uluslararası aramada da güvenilir ve doğrudan bir sonuç bulamadım.",
    "ask_not_found": "Bu ürünün tam aynısını yerel olarak bulamadım 😅\n\nNe yapmak istersiniz? 👇",
    "opt_global": "🌍 Dünya çapında ara",
    "opt_similar": "🔄 Benzer alternatifler",
    "opt_no": "Hayır, teşekkürler 🙏",
    "similar_searching": "🔄 Mevcut en iyi benzer alternatifleri arıyorum…",
    "similar_none": "Şu anda güvenilir fiyatı olan benzer bir alternatif bulamadım 😅 farklı bir arama deneyin.",
    "declined_ok": "Tamamdır 🙏 ihtiyacınız olduğunda buradayım.",
    "welcome_reply": "Merhaba! 🌟\nÜrünün fotoğrafını gönderin veya adını yazın; en iyi fiyatları ve mağazaları bulayım 🛒",
    "thanks_reply": "Rica ederim! 🌹 Sıradaki ürünü istediğiniz zaman gönderin.",
    "lens_header": "✨ Bulduğum eşleşen sonuçlar:",
    "lens_none": "🔎 Görselden yeterli sonuç bulamadım, başka bir yöntem deniyorum…",
    "market_from_phone": "✅ Ülkeniz WhatsApp numaranızdan belirlendi: {country}",
}

MSG["ru"] = {
    "identifying": "✨ Один момент… определяю товар и ищу лучшие варианты.",
    "searching": "🔎 Ищу {q}…",
    "not_found": "Не удалось найти доступный вариант с надежной ценой 😅 попробуйте другую формулировку или отправьте более четкое фото.",
    "identified_not_found": "Я определил товар ({p}), но сейчас не нашел надежную цену 😅 попробуйте написать название иначе.",
    "cant_identify": "Я попробовал несколько раз, но не смог определить товар или найти надежный результат. Отправьте более четкое фото или напишите название товара.",
    "image_error": "При загрузке изображения возникла небольшая ошибка 😅 отправьте его еще раз.",
    "multi_text": "Готово, найдено товаров: {c}. Собираю корзину…",
    "multi_images": "Готово, распознано товаров: {c}. Собираю корзину…",
    "maps_body": "📍 Хотите посмотреть, где найти товар поблизости? Откройте карту ниже 👇",
    "maps_btn": "📍 Открыть карту",
    "maps_body_loc": "📍 Ваш последний поиск: ({p}). Откройте карту, чтобы увидеть ближайшие магазины 👇",
    "no_saved_product": "Пока нет сохраненного товара 😅 сначала выполните поиск товара.",
    "lang_saved": "Отлично, теперь я буду отвечать по-русски 🇷🇺\nОтправьте фото товара или напишите его название.",
    "ask_global": "Не удалось найти надежный локальный результат. Поискать в международных магазинах? 🌍",
    "global_yes": "Да, искать по всему миру 🌍",
    "global_no": "Нет, только локально",
    "global_searching": "🌍 Ищу лучшие совпадения в международных магазинах…",
    "global_none": "В международном поиске также не найден надежный прямой результат.",
    "ask_not_found": "Точно такой товар локально не найден 😅\n\nЧто вы хотите сделать? 👇",
    "opt_global": "🌍 Искать по всему миру",
    "opt_similar": "🔄 Похожие варианты",
    "opt_no": "Нет, спасибо 🙏",
    "similar_searching": "🔄 Ищу лучшие доступные похожие варианты…",
    "similar_none": "Сейчас не удалось найти похожие варианты с надежной ценой 😅 попробуйте другой запрос.",
    "declined_ok": "Хорошо 🙏 я здесь, когда понадоблюсь.",
    "welcome_reply": "Здравствуйте! 🌟\nОтправьте фото товара или напишите его название — я найду лучшие цены и магазины 🛒",
    "thanks_reply": "Пожалуйста! 🌹 Отправляйте следующий товар, когда захотите.",
    "lens_header": "✨ Вот найденные совпадающие результаты:",
    "lens_none": "🔎 По изображению недостаточно результатов, пробую другой способ…",
    "market_from_phone": "✅ Ваша страна определена по номеру WhatsApp: {country}",
}

MSG["zh"] = {
    "identifying": "✨ 稍等一下…正在识别商品并查找最佳选项。",
    "searching": "🔎 正在查找 {q}…",
    "not_found": "暂时没有找到带可靠价格的可购结果 😅 请换一种写法，或发送更清晰的图片。",
    "identified_not_found": "已识别商品（{p}），但暂时没有找到可靠价格 😅 请尝试换一种名称搜索。",
    "cant_identify": "我尝试了多次，但仍无法准确识别商品或找到可靠结果。请发送更清晰的图片，或直接输入商品名称。",
    "image_error": "加载图片时出现了小问题 😅 请重新发送。",
    "multi_text": "好的，找到 {c} 件商品，正在整理购物车…",
    "multi_images": "好的，识别到 {c} 件商品，正在整理购物车…",
    "maps_body": "📍 想看看附近哪里可以买到吗？请打开下方地图 👇",
    "maps_btn": "📍 打开地图",
    "maps_body_loc": "📍 您上次搜索的是（{p}）。打开地图即可查看附近商店 👇",
    "no_saved_product": "目前还没有保存的商品 😅 请先搜索一个商品。",
    "lang_saved": "好的，接下来我会用中文为您服务 🇨🇳\n发送商品图片或直接输入商品名称即可。",
    "ask_global": "本地没有找到可靠结果。需要我继续搜索国际商店吗？ 🌍",
    "global_yes": "是，搜索全球商店 🌍",
    "global_no": "否，仅搜索本地",
    "global_searching": "🌍 正在国际商店中查找最佳匹配结果…",
    "global_none": "国际搜索中也没有找到可靠的直接购买结果。",
    "ask_not_found": "本地没有找到完全相同的商品 😅\n\n您希望我接下来怎么做？ 👇",
    "opt_global": "🌍 搜索全球商店",
    "opt_similar": "🔄 查看相似替代品",
    "opt_no": "不用了，谢谢 🙏",
    "similar_searching": "🔄 正在查找最佳相似替代品…",
    "similar_none": "暂时没有找到带可靠价格的相似替代品 😅 请尝试其他搜索方式。",
    "declined_ok": "好的 🙏 随时需要都可以找我。",
    "welcome_reply": "您好！🌟\n发送商品图片或输入商品名称，我会帮您查找最佳价格和商店 🛒",
    "thanks_reply": "不客气！🌹 随时发送下一个商品。",
    "lens_header": "✨ 找到以下匹配结果：",
    "lens_none": "🔎 图片结果不足，正在尝试其他方式…",
    "market_from_phone": "✅ 已根据您的 WhatsApp 号码确定国家/地区：{country}",
}


# v84: complete localization for recommendation/cart follow-ups.
# These keys existed only in ar/en/hi/ur in v83, which caused English leakage in six UI languages.
MSG["fr"].update({
    "cart_comparing": "🧺 {c} articles trouvés… je compare le panier complet entre les boutiques pour trouver l’option la plus simple et avantageuse !",
    "cart_expired": "Cette liste de panier a expiré 😅 renvoyez les articles et je la reconstruirai.",
    "cart_not_anywhere": "⛔ Introuvable dans les boutiques listées : {items}",
    "cart_pick_prompt": "Choisissez une boutique et je vous enverrai tous les articles avec leurs liens directs — une seule commande, un seul panier 👇",
    "cart_plan_total": "💰 Total du plan : {t}",
    "cart_session_tip": "💡 Ajoutez le premier article avec le bouton, puis cherchez les autres dans la même boutique afin de tout garder dans un seul panier.",
    "cart_store_button": "Choisir boutique",
    "cart_total": "💰 Total du panier : {t}",
    "chat_redirect": "Je suis là 🙌 Envoyez le nom ou la photo d’un produit pour comparer les prix, ou indiquez le service recherché 🛒",
    "compare_searching": "⚖️ Votre demande est générale ; je compare d’abord les meilleures marques et options !",
    "list_button": "Choisir produit",
    "pick_prompt": "Choisissez un produit dans la liste et je chercherai les meilleurs prix disponibles 👇",
})
MSG["es"].update({
    "cart_comparing": "🧺 Encontré {c} artículos… comparo la cesta completa entre tiendas para encontrar la opción más práctica y conveniente.",
    "cart_expired": "Esa lista de cesta caducó 😅 envía los artículos de nuevo y la reconstruyo.",
    "cart_not_anywhere": "⛔ No encontrado en ninguna tienda de la lista: {items}",
    "cart_pick_prompt": "Elige una tienda y te enviaré todos los artículos con sus enlaces directos — un pedido, una sola cesta 👇",
    "cart_plan_total": "💰 Total del plan: {t}",
    "cart_session_tip": "💡 Añade el primer artículo desde el botón y luego busca los demás en la misma tienda para mantenerlos en una sola cesta.",
    "cart_store_button": "Elegir tienda",
    "cart_total": "💰 Total de la cesta: {t}",
    "chat_redirect": "Estoy aquí 🙌 Envía el nombre o la foto de un producto para comparar precios, o escribe el servicio que necesitas 🛒",
    "compare_searching": "⚖️ Tu solicitud es general; primero compararé las mejores marcas y opciones.",
    "list_button": "Elegir producto",
    "pick_prompt": "Elige un producto de la lista y buscaré los mejores precios disponibles 👇",
})
MSG["pt"].update({
    "cart_comparing": "🧺 Encontrei {c} itens… estou comparando o carrinho completo entre lojas para achar a opção mais prática e vantajosa!",
    "cart_expired": "Essa lista do carrinho expirou 😅 envie os itens novamente e eu refaço.",
    "cart_not_anywhere": "⛔ Não encontrado em nenhuma loja da lista: {items}",
    "cart_pick_prompt": "Escolha uma loja e enviarei todos os itens com links diretos — um pedido, um único carrinho 👇",
    "cart_plan_total": "💰 Total do plano: {t}",
    "cart_session_tip": "💡 Adicione o primeiro item pelo botão e depois procure os demais na mesma loja para manter tudo em um único carrinho.",
    "cart_store_button": "Escolher loja",
    "cart_total": "💰 Total do carrinho: {t}",
    "chat_redirect": "Estou aqui 🙌 Envie o nome ou a foto de um produto para comparar preços, ou escreva o serviço de que precisa 🛒",
    "compare_searching": "⚖️ Seu pedido é geral; primeiro vou comparar as melhores marcas e opções!",
    "list_button": "Escolher produto",
    "pick_prompt": "Escolha um produto da lista e eu buscarei os melhores preços disponíveis 👇",
})
MSG["tr"].update({
    "cart_comparing": "🧺 {c} ürün buldum… en kolay ve avantajlı seçeneği bulmak için tüm sepeti mağazalar arasında karşılaştırıyorum!",
    "cart_expired": "Bu sepet listesi artık geçerli değil 😅 ürünleri yeniden gönderin, tekrar hazırlayayım.",
    "cart_not_anywhere": "⛔ Listelenen mağazaların hiçbirinde bulunamadı: {items}",
    "cart_pick_prompt": "Bir mağaza seçin; tüm ürünleri doğrudan bağlantılarıyla tek sipariş ve tek sepet halinde göndereyim 👇",
    "cart_plan_total": "💰 Plan toplamı: {t}",
    "cart_session_tip": "💡 İlk ürünü düğmeden ekleyin, ardından diğerlerini aynı mağazada arayın; böylece hepsi tek sepette kalır.",
    "cart_store_button": "Mağaza seç",
    "cart_total": "💰 Sepet toplamı: {t}",
    "chat_redirect": "Buradayım 🙌 Fiyat karşılaştırması için ürün adı/fotoğrafı gönderin veya ihtiyacınız olan hizmeti yazın 🛒",
    "compare_searching": "⚖️ İsteğiniz genel; önce en iyi marka ve seçenekleri karşılaştırıyorum!",
    "list_button": "Ürün seç",
    "pick_prompt": "Listeden bir ürün seçin, mevcut en iyi fiyatları arayayım 👇",
})
MSG["ru"].update({
    "cart_comparing": "🧺 Найдено товаров: {c}. Сравниваю всю корзину по магазинам, чтобы найти самый удобный и выгодный вариант!",
    "cart_expired": "Срок этой корзины истёк 😅 отправьте список товаров ещё раз, и я соберу её заново.",
    "cart_not_anywhere": "⛔ Не найдено ни в одном магазине из списка: {items}",
    "cart_pick_prompt": "Выберите магазин — я отправлю все товары с прямыми ссылками, чтобы оформить один заказ и одну корзину 👇",
    "cart_plan_total": "💰 Общая сумма плана: {t}",
    "cart_session_tip": "💡 Добавьте первый товар кнопкой, затем найдите остальные в том же магазине, чтобы всё осталось в одной корзине.",
    "cart_store_button": "Выбрать магазин",
    "cart_total": "💰 Сумма корзины: {t}",
    "chat_redirect": "Я здесь 🙌 Отправьте название/фото товара для сравнения цен или напишите, какая услуга вам нужна 🛒",
    "compare_searching": "⚖️ Запрос общий — сначала сравню лучшие бренды и варианты!",
    "list_button": "Выбрать товар",
    "pick_prompt": "Выберите товар из списка, и я найду лучшие доступные цены 👇",
})
MSG["zh"].update({
    "cart_comparing": "🧺 找到 {c} 件商品…正在对比不同商店的整份购物清单，帮您找更省事、更划算的方案！",
    "cart_expired": "这份购物清单已过期 😅 请重新发送商品，我会马上重新整理。",
    "cart_not_anywhere": "⛔ 以下商品在所列商店中都未找到：{items}",
    "cart_pick_prompt": "请选择一家商店，我会把全部商品的直接链接发给您 — 一次下单，一个购物车 👇",
    "cart_plan_total": "💰 整体方案总计：{t}",
    "cart_session_tip": "💡 先通过按钮加入第一件商品，再在同一家商店里搜索其余商品，这样可以保留在同一个购物车中。",
    "cart_store_button": "选择商店",
    "cart_total": "💰 购物车总计：{t}",
    "chat_redirect": "我在这里 🙌 发送商品名称/图片即可比较价格，也可以直接告诉我您需要的服务 🛒",
    "compare_searching": "⚖️ 您的需求比较宽泛，我会先比较最合适的品牌和选项！",
    "list_button": "选择商品",
    "pick_prompt": "请从列表中选择一件商品，我会继续查找最佳可用价格 👇",
})


LANGUAGE_NAMES_EN = {
    "ar":"Arabic", "en":"English", "fr":"French", "es":"Spanish", "pt":"Portuguese",
    "tr":"Turkish", "ru":"Russian", "zh":"Simplified Chinese", "hi":"Hindi", "ur":"Urdu",
    "de":"German", "it":"Italian", "nl":"Dutch", "pl":"Polish", "ja":"Japanese",
    "ko":"Korean", "fa":"Persian", "uk":"Ukrainian", "el":"Greek", "he":"Hebrew",
    "th":"Thai", "vi":"Vietnamese", "id":"Indonesian", "ms":"Malay", "bn":"Bengali",
    "ta":"Tamil", "te":"Telugu", "mr":"Marathi", "ne":"Nepali", "sv":"Swedish",
    "no":"Norwegian", "da":"Danish", "fi":"Finnish", "cs":"Czech", "sk":"Slovak",
    "hu":"Hungarian", "ro":"Romanian", "bg":"Bulgarian", "hr":"Croatian", "sr":"Serbian",
    "sl":"Slovenian", "lt":"Lithuanian", "lv":"Latvian", "et":"Estonian", "ca":"Catalan",
    "sw":"Swahili", "af":"Afrikaans", "sq":"Albanian", "hy":"Armenian", "ka":"Georgian",
    "az":"Azerbaijani", "kk":"Kazakh", "uz":"Uzbek", "tl":"Filipino", "fil":"Filipino"
}
LANGUAGE_SELECTION = {
    "lang_ar": ("ar", "العربية 🇰🇼"),
    "lang_en": ("en", "English 🇬🇧"),
    "lang_fr": ("fr", "Français 🇫🇷"),
    "lang_es": ("es", "Español 🇪🇸"),
    "lang_pt": ("pt", "Português 🇵🇹"),
    "lang_tr": ("tr", "Türkçe 🇹🇷"),
    "lang_ru": ("ru", "Русский 🇷🇺"),
    "lang_zh": ("zh", "中文 🇨🇳"),
    "lang_hi": ("hi", "हिन्दी 🇮🇳"),
    "lang_ur": ("ur", "اردو 🇵🇰"),
}

LANG_INSTR = {
    "ar": "رد باللغة العربية فقط حتى لو كان اسم البحث بالإنجليزية: اكتب سطر 📦 ووصف المنتج بالعربية، مع إبقاء اسم البراند والموديل اللاتيني كما هو. أسماء المتاجر تُكتب بأشهر صيغة متداولة لها.",
    "en": "Respond ONLY in English. Keep the exact response format and emojis. Keep brand/model names unchanged when appropriate. Keep local prices in the user's local currency.",
    "fr": "Répondez UNIQUEMENT en français pour l’interface et les descriptions. Conservez les marques, modèles, tailles et références dans leur forme d’origine si nécessaire. Gardez exactement le même format et les mêmes emojis.",
    "es": "Responde ÚNICAMENTE en español para la interfaz y las descripciones. Mantén marcas, modelos, tallas y referencias en su forma original cuando corresponda. Conserva exactamente el mismo formato y emojis.",
    "pt": "Responda SOMENTE em português para a interface e descrições. Mantenha marcas, modelos, tamanhos e referências na forma original quando apropriado. Preserve exatamente o mesmo formato e emojis.",
    "tr": "Arayüz ve açıklama metinlerinde SADECE Türkçe yanıt ver. Marka/model, beden ve referans kodlarını gerektiğinde özgün biçiminde tut. Aynı formatı ve emojileri koru.",
    "ru": "Отвечайте ТОЛЬКО на русском языке в интерфейсе и описаниях. Названия брендов, моделей, размеров и артикулов при необходимости сохраняйте в исходном виде. Сохраняйте тот же формат и эмодзи.",
    "zh": "界面和描述文字仅使用简体中文。品牌名、型号、尺寸和 SKU 等必要信息保持原样。严格保留相同的输出格式和表情符号。",
    "hi": "Respond ONLY in Hindi (Devanagari) for all UI and descriptive text. Keep brand/model names in their normal Latin form when appropriate. Keep the exact response format and emojis. Keep local prices in the user's local currency.",
    "ur": "Respond ONLY in Urdu for all UI and descriptive text. Keep brand/model names in their normal Latin form when appropriate. Keep the exact response format and emojis. Keep local prices in the user's local currency.",
}

DYNAMIC_UI_TRANSLATION_CACHE = {}
DYNAMIC_UI_TRANSLATION_LOCK = threading.Lock()
DYNAMIC_UI_TRANSLATION_MAX = 4000

def language_name_en(lang):
    code = str(lang or "en").strip().lower().replace("_", "-").split("-")[0]
    return LANGUAGE_NAMES_EN.get(code) or f"language code {code}"

def lang_instr(lang):
    code = str(lang or "en").strip().lower().replace("_", "-").split("-")[0]
    if code in LANG_INSTR:
        return LANG_INSTR[code]
    name = language_name_en(code)
    return (
        f"Respond ONLY in {name}. Keep the exact response format and emojis. "
        "Do not translate or alter brand names, model names, SKUs, sizes, URLs, phone numbers, "
        "or currency codes unless normal grammar requires surrounding words to change."
    )

def _dynamic_translate_ui(text, lang):
    """Translate fallback UI text only for languages that do not have a built-in table."""
    code = str(lang or "en").strip().lower().replace("_", "-").split("-")[0]
    source = str(text or "")
    if not source or code in MSG or code == "en":
        return source
    key = (code, source)
    with DYNAMIC_UI_TRANSLATION_LOCK:
        hit = DYNAMIC_UI_TRANSLATION_CACHE.get(key)
    if hit:
        return hit
    name = language_name_en(code)
    system = (
        f"Translate the following WhatsApp bot UI text into {name}. "
        "Return ONLY the translated text, no quotes and no explanation. "
        "Preserve emojis, line breaks, URLs, phone numbers, prices, currency codes, brand names, "
        "model names, SKUs and product names exactly when appropriate. Do not add information."
    )
    try:
        raw, _ = call_gemini([{"text": source}], system=system, use_search=False)
        translated = (raw or "").strip()
        translated = re.sub(r'^["“”]+|["“”]+$', "", translated).strip()
        if not translated:
            translated = source
    except Exception as e:
        print(f"DYNAMIC UI TRANSLATE ERR lang={code}: {e}")
        translated = source
    with DYNAMIC_UI_TRANSLATION_LOCK:
        if len(DYNAMIC_UI_TRANSLATION_CACHE) >= DYNAMIC_UI_TRANSLATION_MAX:
            DYNAMIC_UI_TRANSLATION_CACHE.clear()
        DYNAMIC_UI_TRANSLATION_CACHE[key] = translated
    return translated

def T(lang, key, **kw):
    code = str(lang or "en").strip().lower().replace("_", "-").split("-")[0]
    table = MSG.get(code)
    if table:
        value = table.get(key, MSG["en"].get(key, MSG["ar"].get(key, key)))
        return value.format(**kw) if kw else value
    value = MSG["en"].get(key, MSG["ar"].get(key, key))
    rendered = value.format(**kw) if kw else value
    return _dynamic_translate_ui(rendered, code)


UI_TEXT = {
    "price_at_store": {"ar":"💰 السعر عند المتجر","en":"💰 Price at store","fr":"💰 Prix en boutique","es":"💰 Precio en tienda","pt":"💰 Preço na loja","tr":"💰 Fiyat mağazada","ru":"💰 Цена в магазине","zh":"💰 商店价格","hi":"💰 कीमत स्टोर पर","ur":"💰 قیمت اسٹور پر"},
    "similar_to": {"ar":"بدائل مشابهة: {base}","en":"Similar to: {base}","fr":"Similaire à : {base}","es":"Similar a: {base}","pt":"Semelhante a: {base}","tr":"Benzeri: {base}","ru":"Похожие варианты: {base}","zh":"相似商品：{base}","hi":"मिलते-जुलते विकल्प: {base}","ur":"ملتے جلتے متبادل: {base}"},
    "more_store_q": {"ar":"✨ تبي أشوف لك متاجر إضافية لنفس المنتج؟","en":"✨ Want more stores for the same product?","fr":"✨ Voir d’autres boutiques pour le même produit ?","es":"✨ ¿Quieres ver más tiendas para el mismo producto?","pt":"✨ Quer ver mais lojas para o mesmo produto?","tr":"✨ Aynı ürün için daha fazla mağaza bulayım mı?","ru":"✨ Найти еще магазины с этим товаром?","zh":"✨ 要继续查找更多销售同款商品的商店吗？","hi":"✨ इसी प्रोडक्ट के लिए और स्टोर खोजूँ?","ur":"✨ اسی پروڈکٹ کے لیے مزید اسٹورز تلاش کروں؟"},
    "search_more": {"ar":"🔎 ابحث أكثر","en":"🔎 Search more","fr":"🔎 Plus de résultats","es":"🔎 Buscar más","pt":"🔎 Buscar mais","tr":"🔎 Daha fazla ara","ru":"🔎 Найти еще","zh":"🔎 查找更多","hi":"🔎 और खोजें","ur":"🔎 مزید تلاش"},
    "looking_more": {"ar":"🔎 أدور لك على متاجر إضافية...","en":"🔎 Looking for more stores...","fr":"🔎 Recherche d’autres boutiques…","es":"🔎 Buscando más tiendas…","pt":"🔎 Procurando mais lojas…","tr":"🔎 Daha fazla mağaza aranıyor…","ru":"🔎 Ищу дополнительные магазины…","zh":"🔎 正在查找更多商店…","hi":"🔎 और स्टोर ढूँढ रहा हूँ...","ur":"🔎 مزید اسٹورز تلاش کر رہا ہوں..."},
    "all_results": {"ar":"✅ هذي تقريباً كل النتائج المطابقة اللي قدرت ألقاها حالياً.","en":"✅ That's about all the matching store results I could find right now.","fr":"✅ C’est à peu près tout ce que j’ai pu trouver pour le moment.","es":"✅ Estos son prácticamente todos los resultados coincidentes que pude encontrar ahora.","pt":"✅ Estes são praticamente todos os resultados correspondentes que encontrei agora.","tr":"✅ Şimdilik bulabildiğim eşleşen mağaza sonuçları bunlar.","ru":"✅ Это почти все подходящие результаты, которые удалось найти сейчас.","zh":"✅ 目前能找到的匹配商店结果基本都在这里了。","hi":"✅ अभी लगभग इतने ही मिलते-जुलते स्टोर नतीजे मिले।","ur":"✅ فی الحال تقریباً یہی تمام ملتے جلتے اسٹور نتائج مل سکے۔"},
    "expired": {"ar":"انتهت صلاحية البحث 😅 ابحث عن المنتج مرة ثانية.","en":"That search expired 😅 search for the product again.","fr":"Cette recherche a expiré 😅 relancez la recherche du produit.","es":"Esa búsqueda caducó 😅 vuelve a buscar el producto.","pt":"Essa busca expirou 😅 pesquise o produto novamente.","tr":"Bu aramanın süresi doldu 😅 ürünü tekrar arayın.","ru":"Срок этого поиска истек 😅 выполните поиск товара снова.","zh":"这次搜索已过期 😅 请重新搜索商品。","hi":"यह खोज समाप्त हो गई 😅 प्रोडक्ट दोबारा खोजें।","ur":"یہ تلاش ختم ہو گئی 😅 پروڈکٹ دوبارہ تلاش کریں۔"},
    "store": {"ar":"المتجر","en":"Store","fr":"Boutique","es":"Tienda","pt":"Loja","tr":"Mağaza","ru":"Магазин","zh":"商店","hi":"स्टोर","ur":"اسٹور"},
    "items": {"ar":"أصناف","en":"items","fr":"articles","es":"artículos","pt":"itens","tr":"ürün","ru":"товаров","zh":"件商品","hi":"आइटम","ur":"آئٹمز"},
    "completes": {"ar":"يكمل","en":"completes","fr":"complète","es":"completa","pt":"completa","tr":"tamamlar","ru":"дополняет","zh":"补全","hi":"पूरा करता है","ur":"مکمل کرتا ہے"},
    "recommended": {"ar":"منتج مقترح","en":"Recommended option","fr":"Option recommandée","es":"Opción recomendada","pt":"Opção recomendada","tr":"Önerilen seçenek","ru":"Рекомендуемый вариант","zh":"推荐选项","hi":"सुझाया गया विकल्प","ur":"تجویز کردہ آپشن"},
}

def U(lang, key, **kw):
    code = str(lang or "en").strip().lower().replace("_", "-").split("-")[0]
    table = UI_TEXT.get(key) or {}
    if code in table:
        value = table[code]
        return value.format(**kw) if kw else value
    value = table.get("en") or key
    rendered = value.format(**kw) if kw else value
    return _dynamic_translate_ui(rendered, code)

_LANG_DETECT_CACHE = {}
_LANG_DETECT_LOCK = threading.Lock()

def _normalize_lang_code(code):
    code = str(code or "").strip().lower().replace("_", "-")
    if not code:
        return None
    code = code.split("-")[0]
    aliases = {"iw":"he", "in":"id", "fil":"tl", "zh-cn":"zh", "zh-tw":"zh"}
    return aliases.get(code, code) if re.fullmatch(r"[a-z]{2,3}", code) else None

def _fast_language_hint(text):
    """High-confidence local hints; ambiguous/mixed text falls through to Gemini."""
    t = str(text or "").strip()
    low = t.casefold()
    if not t:
        return None

    # Distinct scripts / letters.
    if re.search(r"[\u3040-\u30FF]", t): return "ja"
    if re.search(r"[\uAC00-\uD7AF]", t): return "ko"
    if re.search(r"[\u4E00-\u9FFF]", t): return "zh"
    if re.search(r"[\u0590-\u05FF]", t): return "he"
    if re.search(r"[\u0E00-\u0E7F]", t): return "th"
    if re.search(r"[\u0370-\u03FF]", t): return "el"
    if re.search(r"[\u10A0-\u10FF]", t): return "ka"
    if re.search(r"[\u0530-\u058F]", t): return "hy"
    if re.search(r"[іїєґІЇЄҐ]", t): return "uk"
    if re.search(r"[\u0400-\u04FF]", t): return "ru"
    if re.search(r"[\u0980-\u09FF]", t): return "bn"
    if re.search(r"[\u0B80-\u0BFF]", t): return "ta"
    if re.search(r"[\u0C00-\u0C7F]", t): return "te"

    # Arabic-family scripts: prefer clear lexical markers; otherwise let Gemini decide.
    if re.search(r"[\u0600-\u06FF]", t):
        if re.search(r"[ٹڈڑںھہءے]", t) or re.search(r"\b(ہے|میں|کے|کی|کو|اور|چاہیے|قیمت)\b", t):
            return "ur"
        if re.search(r"\b(است|برای|می|قیمت|کجا|لطفا|لطفاً)\b", t) or re.search(r"[ژگپ]", t):
            return "fa"
        if re.search(r"\b(ابي|أبي|ابغى|اريد|أريد|ابحث|بحث|سعر|وين|مرحبا|السلام|شكرا|شكراً|خدمة|منتج)\b", low):
            return "ar"

    # Strong Latin markers.
    if "¿" in t or "¡" in t or "ñ" in low: return "es"
    if re.search(r"[ãõ]", low): return "pt"
    if re.search(r"[ğış]", low): return "tr"
    if "ß" in low: return "de"

    tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿİıĞğŞşÇç]+", low)
    if not tokens:
        return None
    sets = {
        "en": {"hello","hi","please","find","search","price","store","service","want","need","thanks","thank","where","best","for","with"},
        "fr": {"bonjour","salut","merci","cherche","chercher","trouve","trouver","prix","magasin","service","je","veux","pour","avec","où"},
        "es": {"hola","gracias","busco","buscar","encuentra","encontrar","precio","tienda","servicio","quiero","para","con","donde","dónde"},
        "pt": {"olá","ola","obrigado","obrigada","procuro","buscar","encontrar","preço","preco","loja","serviço","servico","quero","para","com","onde"},
        "tr": {"merhaba","teşekkür","tesekkur","ara","arıyorum","ariyorum","fiyat","mağaza","magaza","hizmet","istiyorum","için","icin","ile"},
        "de": {"hallo","danke","suche","finden","preis","laden","geschäft","geschaft","service","ich","möchte","mochte","für","fur","mit","wo"},
        "it": {"ciao","grazie","cerco","cerca","trovare","prezzo","negozio","servizio","voglio","vorrei","per","con","dove"},
        "nl": {"hallo","dank","zoek","vinden","prijs","winkel","dienst","wil","voor","met","waar"},
        "pl": {"cześć","czesc","dziękuję","dziekuje","szukam","znajdź","znajdz","cena","sklep","usługa","usluga","chcę","chce","gdzie"},
        "id": {"halo","terima","kasih","cari","harga","toko","layanan","saya","ingin","untuk","dengan","dimana"},
        "ms": {"hai","terima","kasih","cari","harga","kedai","perkhidmatan","saya","mahu","untuk","dengan","di mana"},
    }
    scores = {code: sum(1 for tok in tokens if tok in words) for code, words in sets.items()}
    best = max(scores, key=scores.get)
    if scores[best] >= 2:
        return best
    if len(tokens) <= 2 and scores[best] == 1 and tokens[0] in sets[best]:
        return best
    return None

def detect_lang(text, current_lang=None):
    """Detect the language of each TEXT message; brand/model-only text does not force a switch."""
    raw_text = str(text or "").strip()
    if not raw_text:
        return None

    key = raw_text.casefold()[:240]
    with _LANG_DETECT_LOCK:
        cached = _LANG_DETECT_CACHE.get(key)
    if cached is not None:
        return cached or None

    fast = _fast_language_hint(raw_text)
    if fast:
        result = fast
    else:
        # Avoid a network call for pure SKU/model strings with almost no linguistic signal.
        words = re.findall(r"[^\W\d_]+", raw_text, flags=re.UNICODE)
        alpha_chars = sum(ch.isalpha() for ch in raw_text)
        if alpha_chars < 2:
            result = None
        else:
            system = """Detect the dominant NATURAL LANGUAGE of the user's WhatsApp text.
Return ONLY compact JSON:
{"code":"xx","name":"English language name","confidence":0.00,"natural":true}
Rules:
- code = ISO 639-1 two-letter code when available.
- Detect the language of the user's actual wording/instructions, not brand names, model names, SKUs, URLs or store names.
- If the text is only a brand/model/SKU/product code and has no meaningful natural-language wording, set natural=false.
- For mixed text, choose the dominant language used to address the bot.
- Do not translate or answer the message."""
            try:
                out, _ = call_gemini([{"text": raw_text[:500]}], system=system, use_search=False)
                m = re.search(r"\{.*\}", out or "", flags=re.S)
                data = json.loads(m.group(0)) if m else {}
                code = _normalize_lang_code(data.get("code"))
                name = str(data.get("name") or "").strip()
                confidence = float(data.get("confidence") or 0)
                natural = bool(data.get("natural"))
                if code and name:
                    LANGUAGE_NAMES_EN.setdefault(code, name)
                result = code if code and natural and confidence >= 0.60 else None
            except Exception as e:
                print(f"LANG DETECT ERR: {e}")
                result = None

    with _LANG_DETECT_LOCK:
        if len(_LANG_DETECT_CACHE) > 3000:
            _LANG_DETECT_CACHE.clear()
        _LANG_DETECT_CACHE[key] = result or ""
    return result

def auto_language_from_text(phone, text, persist=True):
    """Every incoming text can switch the bot to the language used in that message."""
    previous = USER_LANG.get(phone)
    detected = detect_lang(text, previous)
    if not detected:
        if previous:
            return previous, False
        # For a brand/model-only first message, use the user's phone-market language.
        market = market_for_user(phone)
        detected = _normalize_lang_code(market.get("search_hl")) or "en"

    changed = previous != detected
    USER_LANG[phone] = detected
    if persist and changed:
        save_user_preferences(phone)
    if changed:
        print(f"AUTO LANGUAGE: {phone} {previous or '-'} -> {detected} ({language_name_en(detected)})")
    return detected, changed

SYSTEM_PROMPT = """
أنت مساعد تسوق عالمي يعتمد سوق المستخدم المحلي الحالي. السوق المحلي هو أهم جزء في الخدمة ويجب البحث فيه بقوة قبل النتائج الأجنبية.

أولاً حدد نوع الطلب:

【الحالة 1】منتج محدد بعلامة/موديل واضح:
قارن نفس المنتج ونفس المواصفات. رتب جغرافياً دائماً: بلد المستخدم المحلي أولاً، ثم الولايات المتحدة، ثم الصين فقط. داخل كل سوق رتب من الأرخص إلى الأغلى.
📦 [اسم المنتج]
✅ [المتجر] — [السعر الرقمي + العملة]
• [المتجر] — [السعر الرقمي + العملة]

قاعدة المحلي: ابحث في المتاجر المتخصصة القوية في بلد المستخدم ثم المنصات العامة، ووسّع لأي متجر محلي حقيقي مفهرس في Google Shopping/Search. لا تحصر البحث في قائمة ثابتة، ولا تفترض أن .com يعني متجر أمريكي؛ قد يكون متجراً محلياً.

【الحالة 2】طلب عام بدون براند/موديل محدد:
لا تبحث عن الأرخص فقط. اقترح أفضل الخيارات المناسبة والمتاحة في سوق المستخدم المحلي، وباللغة التي طلبها المستخدم، ثم اسمح له باختيار منتج للبحث عن أسعاره.

【الحالة 3】طلب خدمة:
ابحث محلياً في بلد المستخدم. لا تكتب رقم هاتف إلا إذا ظهر حرفياً في نتائج البحث.

【الحالة 4】سؤال معلوماتي عن منتج:
أجب عن السؤال مباشرة ولا تعرض مقارنة أسعار إلا إذا طلب المستخدم ذلك.

قواعد جودة صارمة:
- السوق المحلي أولاً دائماً، وبعده الولايات المتحدة ثم الصين فقط؛ ارفض أي دولة رابعة.
- لا تجعل السعر الأرخص في أمريكا/الصين يتقدم على عرض محلي صحيح.
- قارن نفس المواصفات فقط: الحجم/السعة/الوزن/الموديل واللون إذا كان يؤثر في السعر.
- كل رابط شراء يجب أن يكون صفحة منتج مباشرة، وليس Google ولا صفحة بحث/تصنيف.
- لا تخترع سعراً أو متجراً. استخدم السعر الموجود في نتيجة البحث الحالية.
- اكتب السعر بالعملة الصحيحة للسوق كما تظهر، والتطبيق يتولى التنسيق والتحويل عند الحاجة.
- استبعد Heureka / heureka.cz / heureka.sk دائماً لأنه موقع مقارنة وليس متجراً مباشراً. لا تستبعد Eureka الكويتية.
- لا تفترض أن رمز $ يعني USD دائماً؛ احترم سياق بلد المستخدم والعملة التي يحددها التطبيق.
- في البحث المحلي استخدم اسم المنتج بصياغة المستخدم + الاسم التجاري الإنجليزي + لغة التجارة المحلية عندما تفيد الفهرسة.

في نتائج المتاجر أضف سطر LINKS داخلياً لربط أسماء المتاجر بالمصادر، ولا تعرض روابط خام للمستخدم.
لغة الرد: التزم حصراً بلغة المستخدم المحددة في الواجهة.
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
                        except Exception: pass
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
        except Exception: continue
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
            except Exception: pass
    if not data["currency"]:
        m = soup.find("meta", property="product:price:currency")
        if m and m.get("content"):
            cur = str(m["content"]).upper().strip()
            if cur in KNOWN_CURRENCY_CODES:
                data["currency"] = cur

    # v79.1: price fallbacks for stores whose JSON-LD is incomplete (Amazon/eBay/Temu/Alibaba, etc.).
    if not data["price"]:
        price_candidates = []
        selectors = [
            ('meta[itemprop="price"]', 'content'), ('meta[name="price"]', 'content'),
            ('meta[property="og:price:amount"]', 'content'), ('meta[name="twitter:data1"]', 'content'),
        ]
        for sel, attr in selectors:
            node = soup.select_one(sel)
            if node and node.get(attr):
                price_candidates.append(str(node.get(attr)))
        for sel in ('.a-price .a-offscreen', '.a-price-whole', '[itemprop="price"]', '.x-price-primary span'):
            node = soup.select_one(sel)
            if node:
                price_candidates.append(node.get_text(" ", strip=True))
        # JSON/script fallbacks used by many JS-heavy commerce sites.
        raw_html = html[:1200000]
        for pat in (
            r'"priceAmount"\s*:\s*"?(\d+(?:\.\d{1,3})?)',
            r'"salePrice"\s*:\s*"?(\d+(?:\.\d{1,3})?)',
            r'"currentPrice"\s*:\s*"?(\d+(?:\.\d{1,3})?)',
            r'"price"\s*:\s*"(\d+(?:\.\d{1,3})?)"',
        ):
            mm = re.search(pat, raw_html, flags=re.I)
            if mm:
                price_candidates.append(mm.group(1))
                break
        for cand in price_candidates:
            mm = re.search(r'(?<!\d)(\d+(?:[.,]\d{1,3})?)(?!\d)', str(cand).replace(',', ''))
            if not mm:
                continue
            try:
                val = float(mm.group(1))
            except Exception:
                continue
            if val > 0:
                data["price"] = val
                if not data["currency"]:
                    data["currency"] = detect_currency_code(str(cand), "")
                break
    if not data["currency"]:
        # Currency hints from structured HTML/text; conservative domain fallback only when price exists.
        raw_head = html[:250000]
        mm = re.search(r'"priceCurrency"\s*:\s*"([A-Z]{3})"', raw_head, flags=re.I)
        if mm and mm.group(1).upper() in KNOWN_CURRENCY_CODES:
            data["currency"] = mm.group(1).upper()
        elif data["price"]:
            host = urllib.parse.urlparse(url).netloc.lower()
            if any(d in host for d in ('amazon.com','ebay.com','walmart.com','bestbuy.com','newegg.com','aliexpress.com','temu.com')):
                data["currency"] = 'USD'
            elif any(d in host for d in ('1688.com','taobao.com','tmall.com')):
                data["currency"] = 'CNY'
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

def _result_confirmed_out_of_stock(item):
    """Best-effort stock guard for displayed text/Lens results.

    Returns True only when the source/page positively says the item is unavailable.
    Network blocks, anti-bot pages, parsing failures, or missing stock metadata are treated
    as UNKNOWN and therefore kept — we never hide an offer merely because we could not verify it.
    """
    if not ENABLE_RESULT_STOCK_CHECK:
        return False
    if isinstance(item, dict) and item.get("in_stock") is False:
        return True
    url = (item.get("link") or item.get("url") or "").strip() if isinstance(item, dict) else str(item or "").strip()
    if not url.startswith(("http://", "https://")):
        return False
    try:
        cached = VERIFIED_PAGE_CACHE.get(url)
        if cached and (time.time() - cached.get("ts", 0) < 600):
            info = cached.get("data")
            return bool(info and info.get("available") is False)
        if not ENABLE_LIVE_STOCK_NETWORK_CHECK:
            return False
        html = fetch_html(url)
        if not html:
            return False
        info = parse_product_data(html, url)
        if info:
            VERIFIED_PAGE_CACHE[url] = {"data": info, "ts": time.time()}
            _prune_verified_page_cache()
        return bool(info and info.get("available") is False)
    except Exception as e:
        print(f"STOCK CHECK UNKNOWN: {url[:90]} -> {e}")
        return False


def _filter_confirmed_oos(items, label="RESULT"):
    """Drop only confirmed OOS items; avoid thread overhead unless live HTTP checks are enabled."""
    seq = list(items or [])
    if not seq or not ENABLE_RESULT_STOCK_CHECK:
        return seq
    try:
        if ENABLE_LIVE_STOCK_NETWORK_CHECK:
            flags = list(RESOLVER.map(_result_confirmed_out_of_stock, seq))
        else:
            # Normal fast path: explicit metadata + cache only, no merchant-page requests.
            flags = [_result_confirmed_out_of_stock(item) for item in seq]
    except Exception as e:
        print(f"{label} STOCK FILTER ERR: {e}")
        return seq
    kept = []
    for item, is_oos in zip(seq, flags):
        if is_oos:
            url = (item.get("link") or item.get("url") or "") if isinstance(item, dict) else ""
            title = (item.get("title") or item.get("source") or "") if isinstance(item, dict) else ""
            print(f"{label} OOS SKIP: {title[:70]} -> {url[:100]}")
            continue
        kept.append(item)
    return kept


def verify_offers(urls_map, query):
    """Optional deep HTML verifier. Disabled by default to keep searches fast and non-destructive."""
    if not urls_map:
        return {}
    verified = {}
    def _check(item):
        name, url = item
        if is_blocked_store(name, url):
            print(f"REJECT BLOCKED STORE: {name} -> {url}")
            return None
        cached = VERIFIED_PAGE_CACHE.get(url)
        if cached and (time.time() - cached["ts"] < 600):
            info = cached["data"]
        elif ENABLE_LIVE_PAGE_VERIFICATION:
            html = fetch_html(url)
            info = parse_product_data(html, url)
            if info:
                VERIFIED_PAGE_CACHE[url] = {"data": info, "ts": time.time()}
        else:
            # Do not block the user on merchant HTML. The caller can use grounded/Lens data.
            return None
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
            if is_blocked_store(source, link):
                print(f"LENS BLOCKED STORE SKIP: {source} -> {link}")
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
        cards = _serpapi_shopping_request(f'{q} site:{domain}', "us", hl="en", timeout_seconds=MARKET_FALLBACK_TIMEOUT_SECONDS)
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
            currency = detect_currency_code(price_text, "CNY", "cn")
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
    done, not_done = wait(list(futures), timeout=MARKET_FALLBACK_TIMEOUT_SECONDS)
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


def _shopping_card_to_market_item(card, fallback_source="", lens_country=""):
    link = (card.get("link") or "").strip()
    if not link:
        return None
    direct = _shopping_direct_url(link) or link
    source = (card.get("source") or fallback_source or "").strip()
    if not direct.startswith(("http://", "https://")):
        return None
    if is_blocked_store(source, direct):
        print(f"SHOPPING BLOCKED STORE SKIP: {source} -> {direct}")
        return None
    price_text = str(card.get("price") or "").strip()
    return {
        "title": (card.get("title") or "").strip(),
        "link": direct,
        "source": source,
        "position": int(card.get("position") or 999),
        "section": "market_presence_fallback",
        "exact": False,
        "thumbnail": (card.get("thumbnail") or "").strip(),
        "image": (card.get("thumbnail") or "").strip(),
        "price": price_text,
        "price_value": card.get("extracted_price"),
        "currency": detect_currency_code(price_text, COUNTRY_CURRENCIES.get(lens_country, ""), lens_country),
        "in_stock": None,
        "condition": "",
        "_lens_country": lens_country,
        "_market_presence_fallback": True,
    }


def _market_presence_fallback(base_query, rank, limit=6):
    """Search a market only when the normal first search found zero candidates there.

    rank 0 = user's local market, 1 = US, 2 = China.
    Strong marketplaces are queried first for US/China.
    Returned candidates still pass the normal relevance/stock filters.
    """
    if not SERPAPI_API_KEY:
        return []
    q = _shopping_clean_query(base_query or "")
    if not q:
        return []

    if rank == 2:
        return _china_store_search_fallback(q, limit=limit)

    local_cc = (current_market().get("country") or DEFAULT_COUNTRY).lower()
    if rank == 0:
        specs = [("Local", "", local_cc)]
        specs.extend((label, domain, local_cc) for label, domain in local_rescue_store_specs(q, LOCAL_STORE_RESCUE_MAX))
    else:
        specs = [
            ("Amazon", "amazon.com", "us"),
            ("eBay", "ebay.com", "us"),
            ("Walmart", "walmart.com", "us"),
            ("US", "", "us"),
        ]

    def _one(label, domain, gl):
        search_q = f"{q} site:{domain}" if domain else q
        cards = _serpapi_shopping_request(search_q, gl, hl=(country_search_hl(gl) if rank == 0 else "en"), timeout_seconds=MARKET_FALLBACK_TIMEOUT_SECONDS)
        out = []
        for card in cards or []:
            item = _shopping_card_to_market_item(card, label, gl)
            if not item:
                continue
            if domain:
                try:
                    host = urllib.parse.urlparse(item["link"]).netloc.lower().replace("www.", "")
                except Exception:
                    host = ""
                if not _host_matches_any(host, (domain,)):
                    continue
            if result_market_rank(item) != rank:
                continue
            out.append(item)
        return out

    futures = {
        LENS_HTTP_POOL.submit(_one, label, domain, gl): (label, domain)
        for label, domain, gl in specs
    }
    merged, seen = [], set()
    done, pending = wait(list(futures), timeout=MARKET_FALLBACK_TIMEOUT_SECONDS)
    # Deterministic ranking after parallel fetches.
    gathered = []
    for fut in done:
        try:
            gathered.extend(fut.result() or [])
        except Exception as e:
            print(f"MARKET PRESENCE FALLBACK ERR rank={rank}: {e}")
    for fut in pending:
        fut.cancel()

    if rank == 1:
        gathered.sort(key=lambda x: (
            _us_store_priority(x.get("source"), x.get("link")),
            int(x.get("position") or 999),
        ))
    else:
        gathered.sort(key=lambda x: int(x.get("position") or 999))

    for item in gathered:
        sig = ((item.get("title") or "").lower(), (item.get("link") or "").lower())
        if sig in seen:
            continue
        seen.add(sig)
        merged.append(item)
        if len(merged) >= limit:
            break

    print(f"MARKET PRESENCE FALLBACK rank={rank} query={q[:70]!r} -> {len(merged)}")
    return merged


def _supplement_missing_markets(candidates, query, label="FIRST"):
    """Second-chance coverage for missing markets, with all missing markets checked in parallel."""
    seq = list(candidates or [])
    existing = {
        ((x.get("title") or "").lower(), (x.get("link") or "").lower())
        for x in seq
    }
    counts = {r: sum(1 for x in seq if result_market_rank(x) == r) for r in (0, 1, 2)}
    local_target = min(LENS_DIRECT_LOCAL_MAX, LOCAL_RESULTS_TARGET)
    missing = []
    if counts[0] < local_target:
        missing.append(0)
    if counts[1] == 0:
        missing.append(1)
    if counts[2] == 0:
        missing.append(2)
    if not missing or not SERPAPI_API_KEY:
        return seq

    market_snapshot = current_market()
    futures = {
        MARKET_SUPPLEMENT_POOL.submit(_run_with_market, market_snapshot, _market_presence_fallback, query, rank, 6): rank
        for rank in missing
    }
    done, pending = wait(list(futures), timeout=MARKET_FALLBACK_TIMEOUT_SECONDS + 1)
    gathered = {}
    for fut in done:
        rank = futures[fut]
        try:
            gathered[rank] = fut.result() or []
        except Exception as e:
            print(f"{label}: market supplement error rank={rank}: {e}")
    for fut in pending:
        fut.cancel()

    for rank in (0, 1, 2):
        extra = gathered.get(rank) or []
        for item in extra:
            sig = ((item.get("title") or "").lower(), (item.get("link") or "").lower())
            if sig in existing:
                continue
            seq.append(item)
            existing.add(sig)
        if extra:
            print(f"{label}: supplemented weak/missing market rank={rank} with {len(extra)} candidate(s)")
    return seq


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

        merged_by_sig = {}
        def _merge(new_items):
            # نفس بطاقة Lens قد تصل من أكثر من تمريرة. سابقاً كنا نحتفظ بأول نسخة
            # ونرمي الثانية حتى لو كانت الثانية تحمل السعر. الآن ندمج metadata مجاناً
            # من كل تمريرات Lens بدون أي HTTP إضافي.
            for it in new_items:
                sig = (it["title"].lower(), it["link"].lower())
                if sig in seen:
                    prev = merged_by_sig.get(sig)
                    if prev is not None:
                        if (not _lens_has_price(prev)) and _lens_has_price(it):
                            for k in ("price", "price_value", "currency", "in_stock", "condition"):
                                if it.get(k) not in (None, ""):
                                    prev[k] = it.get(k)
                            prev["price_source"] = "lens_duplicate_pass"
                            print(f"LENS DUP PRICE MERGE: {(prev.get('source') or '')[:35]} -> {prev.get('price') or prev.get('price_value')}")
                        # معلومات المخزون الصريحة أفضل من None حتى لو لم يتغير السعر.
                        if prev.get("in_stock") is None and it.get("in_stock") is not None:
                            prev["in_stock"] = it.get("in_stock")
                    continue
                seen.add(sig)
                merged.append(it)
                merged_by_sig[sig] = it

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
        # Fast staged wait: all Lens passes start together. If enough strong local-first evidence
        # arrives quickly, do not wait for a single slow duplicate pass. If not, preserve the
        # original quality behavior and continue up to the full total timeout.
        all_futures = set(future_map)
        done_fast, pending = wait(all_futures, timeout=min(LENS_FAST_READY_SECONDS, LENS_TOTAL_TIMEOUT_SECONDS))
        for fut in done_fast:
            lens_type, country, auto_crop = future_map[fut]
            try:
                _merge(fut.result())
            except Exception as e:
                print(f"GOOGLE LENS FUTURE ERR type={lens_type} country={country}: {e}")
        rank_counts = {r: sum(1 for x in merged if result_market_rank(x) == r) for r in (0, 1, 2)}
        # Exit early only when local is strong AND US/China already have coverage, so the
        # later missing-market supplement does not re-add the latency we just removed.
        enough_fast = (rank_counts[0] >= 2 and rank_counts[1] >= 1 and rank_counts[2] >= 1
                       and len(merged) >= max(5, LENS_MIN_MATCHES))
        done = set(done_fast)
        if pending and not enough_fast:
            remaining = max(0.0, LENS_TOTAL_TIMEOUT_SECONDS - min(LENS_FAST_READY_SECONDS, LENS_TOTAL_TIMEOUT_SECONDS))
            done_more, pending = wait(pending, timeout=remaining)
            done |= done_more
            for fut in done_more:
                lens_type, country, auto_crop = future_map[fut]
                try:
                    _merge(fut.result())
                except Exception as e:
                    print(f"GOOGLE LENS FUTURE ERR type={lens_type} country={country}: {e}")
        for fut in pending:
            lens_type, country, _ = future_map[fut]
            fut.cancel()
            print(f"GOOGLE LENS PASS SKIPPED AFTER FAST/TOTAL TIMEOUT type={lens_type} country={country}")
        print(f"GOOGLE LENS PARALLEL DONE completed={len(done)}/{len(future_map)} fast_ready={enough_fast} total_timeout={LENS_TOTAL_TIMEOUT_SECONDS}s")

        # أي دولة غير محلي/أمريكا/الصين تُحذف نهائياً.
        allowed = [m for m in merged if result_market_rank(m) != 99]

        # First-search market presence: do not finish with a missing LOCAL/US/CHINA
        # bucket until that missing market gets a dedicated fallback attempt.
        # This does not force a result when the exact product is not found there.
        fallback_query = (query_hint or "").strip()
        if not fallback_query and merged:
            fallback_query = (merged[0].get("title") or "").strip()
        allowed = _supplement_missing_markets(allowed, fallback_query, "FIRST-LENS")

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
            # v79.1 accuracy: one fast vision identity pass anchors relevance.
            # It does NOT search or reorder stores; it only says what physical product is in the image.
            visual_identity = ""
            try:
                id_system = (
                    "Identify the physical product in the image for shopping search. "
                    "Return one concise English commercial identity only: product type + brand/model if visibly supported. "
                    "Do not guess a brand/model. Do not mention colors unless identity-critical. No explanation."
                )
                visual_identity, _ = call_gemini([
                    {"inline_data": {"mime_type": mime_type, "data": image_b64}},
                    {"text": f"Lens hint only (may be wrong): {chosen_title}"},
                ], system=id_system, use_search=False)
                visual_identity = re.sub(r"\s+", " ", (visual_identity or "").strip()).strip(' .-|')[:180]
                print(f"LENS VISUAL IDENTITY: {visual_identity}")
            except Exception as e:
                print(f"LENS VISUAL IDENTITY FAIL: {e}")
            return {
                "aliases": [x for x in (visual_identity, chosen_title) if x],
                "matches": matches,
                "query": visual_identity or chosen_title,
                "visual_identity": visual_identity,
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
    """Resolve a grounded redirect with a short TTL cache; failures keep the original URL."""
    if not url or not url.startswith(("http://", "https://")):
        return ""
    now = time.time()
    with FINAL_URL_CACHE_LOCK:
        hit = FINAL_URL_CACHE.get(url)
        if hit and now - hit["ts"] < FINAL_URL_CACHE_TTL:
            return hit["url"]
    final = url
    try:
        r = requests.get(url, allow_redirects=True, timeout=(3, RESOLVE_TIMEOUT_SECONDS), stream=True, headers=HEADERS)
        final = r.url or url
        r.close()
    except Exception as e:
        print(f"resolve err {e} {url[:80]}")
    with FINAL_URL_CACHE_LOCK:
        if len(FINAL_URL_CACHE) >= 2000:
            # Cheap bounded cache: remove the oldest half only when needed.
            oldest = sorted(FINAL_URL_CACHE.items(), key=lambda kv: kv[1].get("ts", 0))[:1000]
            for key, _ in oldest:
                FINAL_URL_CACHE.pop(key, None)
        FINAL_URL_CACHE[url] = {"url": final, "ts": now}
    return final

def resolve_all(uris):
    return list(RESOLVER.map(get_final_url, uris))


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


# v85: country-level merchant hints are a BOOST, never a whitelist. Google local discovery remains open.
COUNTRY_MAJOR_STORE_DOMAINS = {
    "us": [("Amazon","amazon.com"),("Walmart","walmart.com"),("Target","target.com"),("Best Buy","bestbuy.com"),("eBay","ebay.com")],
    "ca": [("Amazon Canada","amazon.ca"),("Walmart Canada","walmart.ca"),("Best Buy Canada","bestbuy.ca"),("Canadian Tire","canadiantire.ca")],
    "gb": [("Amazon UK","amazon.co.uk"),("Argos","argos.co.uk"),("Currys","currys.co.uk"),("John Lewis","johnlewis.com")],
    "fr": [("Amazon France","amazon.fr"),("Fnac","fnac.com"),("Darty","darty.com"),("Cdiscount","cdiscount.com"),("Carrefour","carrefour.fr")],
    "de": [("Amazon Germany","amazon.de"),("MediaMarkt","mediamarkt.de"),("Saturn","saturn.de"),("Otto","otto.de")],
    "es": [("Amazon Spain","amazon.es"),("El Corte Inglés","elcorteingles.es"),("MediaMarkt","mediamarkt.es"),("Carrefour","carrefour.es")],
    "it": [("Amazon Italy","amazon.it"),("MediaWorld","mediaworld.it"),("Unieuro","unieuro.it")],
    "nl": [("bol","bol.com"),("Coolblue","coolblue.nl"),("MediaMarkt","mediamarkt.nl"),("Amazon Netherlands","amazon.nl")],
    "be": [("bol","bol.com"),("Coolblue","coolblue.be"),("MediaMarkt","mediamarkt.be"),("Amazon Belgium","amazon.com.be")],
    "ch": [("Galaxus","galaxus.ch"),("Digitec","digitec.ch"),("Brack","brack.ch"),("Manor","manor.ch")],
    "at": [("MediaMarkt","mediamarkt.at"),("Amazon Germany","amazon.de"),("Otto Austria","ottoversand.at")],
    "ie": [("Currys Ireland","currys.ie"),("Harvey Norman","harveynorman.ie"),("Amazon UK","amazon.co.uk")],
    "pt": [("Worten","worten.pt"),("Fnac Portugal","fnac.pt"),("Continente","continente.pt")],
    "pl": [("Allegro","allegro.pl"),("Media Expert","mediaexpert.pl"),("RTV Euro AGD","euro.com.pl")],
    "cz": [("Alza","alza.cz"),("Datart","datart.cz"),("Mall","mall.cz")],
    "se": [("Amazon Sweden","amazon.se"),("Elgiganten","elgiganten.se"),("CDON","cdon.se")],
    "no": [("Elkjøp","elkjop.no"),("Komplett","komplett.no"),("Power","power.no")],
    "dk": [("Elgiganten","elgiganten.dk"),("Proshop","proshop.dk"),("Power","power.dk")],
    "fi": [("Verkkokauppa","verkkokauppa.com"),("Gigantti","gigantti.fi"),("Power","power.fi")],
    "tr": [("Trendyol","trendyol.com"),("Hepsiburada","hepsiburada.com"),("Amazon Turkey","amazon.com.tr"),("n11","n11.com")],
    "ru": [("Ozon","ozon.ru"),("Wildberries","wildberries.ru"),("Yandex Market","market.yandex.ru")],
    "ua": [("Rozetka","rozetka.com.ua"),("Prom","prom.ua"),("Epicentr","epicentrk.ua")],
    "sa": [("Amazon Saudi","amazon.sa"),("Noon","noon.com"),("Jarir","jarir.com"),("eXtra","extra.com"),("Carrefour","carrefourksa.com")],
    "ae": [("Amazon UAE","amazon.ae"),("Noon","noon.com"),("Carrefour UAE","carrefouruae.com"),("Sharaf DG","sharafdg.com"),("Jumbo","jumbo.ae")],
    "eg": [("Amazon Egypt","amazon.eg"),("Noon","noon.com"),("B.TECH","btech.com"),("Carrefour Egypt","carrefouregypt.com")],
    "in": [("Amazon India","amazon.in"),("Flipkart","flipkart.com"),("Croma","croma.com"),("Reliance Digital","reliancedigital.in"),("Myntra","myntra.com")],
    "pk": [("Daraz","daraz.pk"),("PriceOye","priceoye.pk")],
    "bd": [("Daraz Bangladesh","daraz.com.bd"),("Pickaboo","pickaboo.com")],
    "cn": [("JD","jd.com"),("Tmall","tmall.com"),("Taobao","taobao.com"),("Suning","suning.com")],
    "jp": [("Amazon Japan","amazon.co.jp"),("Rakuten","rakuten.co.jp"),("Yodobashi","yodobashi.com"),("Bic Camera","biccamera.com")],
    "kr": [("Coupang","coupang.com"),("Gmarket","gmarket.co.kr"),("11st","11st.co.kr")],
    "sg": [("Shopee Singapore","shopee.sg"),("Lazada Singapore","lazada.sg"),("Amazon Singapore","amazon.sg"),("Courts","courts.com.sg")],
    "my": [("Shopee Malaysia","shopee.com.my"),("Lazada Malaysia","lazada.com.my"),("Harvey Norman","harveynorman.com.my")],
    "id": [("Tokopedia","tokopedia.com"),("Shopee Indonesia","shopee.co.id"),("Blibli","blibli.com"),("Lazada Indonesia","lazada.co.id")],
    "ph": [("Shopee Philippines","shopee.ph"),("Lazada Philippines","lazada.com.ph")],
    "th": [("Shopee Thailand","shopee.co.th"),("Lazada Thailand","lazada.co.th"),("Central","central.co.th"),("Power Buy","powerbuy.co.th")],
    "vn": [("Shopee Vietnam","shopee.vn"),("Lazada Vietnam","lazada.vn"),("Tiki","tiki.vn")],
    "au": [("Amazon Australia","amazon.com.au"),("JB Hi-Fi","jbhifi.com.au"),("Harvey Norman","harveynorman.com.au"),("Kmart","kmart.com.au")],
    "nz": [("The Warehouse","thewarehouse.co.nz"),("Noel Leeming","noelleeming.co.nz"),("Mighty Ape","mightyape.co.nz"),("Harvey Norman","harveynorman.co.nz")],
    "br": [("Mercado Livre","mercadolivre.com.br"),("Amazon Brazil","amazon.com.br"),("Magazine Luiza","magazineluiza.com.br")],
    "mx": [("Mercado Libre","mercadolibre.com.mx"),("Amazon Mexico","amazon.com.mx"),("Walmart Mexico","walmart.com.mx"),("Liverpool","liverpool.com.mx")],
    "ar": [("Mercado Libre","mercadolibre.com.ar"),("Frávega","fravega.com")],
    "cl": [("Mercado Libre","mercadolibre.cl"),("Falabella","falabella.com"),("Paris","paris.cl")],
    "co": [("Mercado Libre","mercadolibre.com.co"),("Falabella","falabella.com.co"),("Éxito","exito.com")],
    "pe": [("Mercado Libre","mercadolibre.com.pe"),("Falabella","falabella.com.pe"),("Ripley","ripley.com.pe")],
    "za": [("Takealot","takealot.com"),("Makro","makro.co.za"),("Woolworths","woolworths.co.za")],
    "ng": [("Jumia Nigeria","jumia.com.ng"),("Konga","konga.com")],
    "ke": [("Jumia Kenya","jumia.co.ke"),("Carrefour Kenya","carrefour.ke")],
    "ma": [("Jumia Morocco","jumia.ma"),("Marjane","marjane.ma")],
    "il": [("KSP","ksp.co.il"),("Ivory","ivory.co.il")],
}

def country_major_store_specs(cc=None):
    cc = (cc or current_market().get("country") or DEFAULT_COUNTRY).lower()
    return list(COUNTRY_MAJOR_STORE_DOMAINS.get(cc, ()))

def detect_category(query):
    """يحدد فئة المنتج من الكلمات؛ الفئات الأدق (رياضة/قيمنق/ألعاب) تُفحص قبل العامة."""
    q = normalize_ar(query)
    for cat in ("gaming", "sports", "kids_toys", "appliances", "pharmacy", "beauty",
                "auto", "furniture", "food_delivery", "grocery", "electronics", "fashion"):
        if any(normalize_ar(w) in q for w in CATEGORY_KEYWORDS.get(cat, ())):
            return cat
    return ""

def priority_stores_for(query):
    """Strong local merchant hints. Kuwait keeps the original category engine; other markets use country retailers."""
    cc = (current_market().get("country") or DEFAULT_COUNTRY).lower()
    if cc == "kw":
        cat = detect_category(query)
        specialists = list(CATEGORY_SPECIALISTS.get(cat, []))
        tail = [m for m in GENERAL_MARKETPLACES if m not in specialists]
        ordered = specialists + tail
        return ordered[:9] if ordered else list(GENERAL_MARKETPLACES)
    return [label for label, _ in country_major_store_specs(cc)][:9]


def store_domain(name):
    # Explicit "Store (domain.tld)" always wins.
    mm = re.search(r"\(([a-z0-9.-]+\.[a-z]{2,})\)", str(name or ""), flags=re.I)
    if mm:
        return mm.group(1).lower()
    cc = (current_market().get("country") or DEFAULT_COUNTRY).lower()
    n = normalize_name(normalize_ar(name))
    if cc != "kw":
        for label, domain in country_major_store_specs(cc):
            key = normalize_name(normalize_ar(label))
            if key and (key in n or n in key):
                return domain
        return ""
    for k, d in STORE_DOMAINS.items():
        if k in n or n in k:
            return d
    return ""


def local_rescue_store_specs(query, max_count=None):
    """Direct-store rescue list used only if broad local discovery is weak."""
    max_count = LOCAL_STORE_RESCUE_MAX if max_count is None else max_count
    if max_count <= 0:
        return []
    seen, out = set(), []
    for label in priority_stores_for(query):
        domain = store_domain(label)
        if not domain:
            continue
        key = domain.lower().replace("www.", "")
        if key in seen:
            continue
        seen.add(key)
        out.append((label, key))
        if len(out) >= max_count:
            break
    # For non-Kuwait markets, country list may contain extra merchants not returned by priority list.
    if len(out) < max_count:
        for label, domain in country_major_store_specs():
            key = domain.lower().replace("www.", "")
            if key in seen:
                continue
            seen.add(key); out.append((label, key))
            if len(out) >= max_count:
                break
    return out

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
        if is_blocked_store(name, ""):
            print(f"SKIP BLOCKED STORE LINE: {name}")
            continue
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
    if is_blocked_store(name, ""):
        return ""
    if name in urls:
        return "" if is_blocked_store(name, urls[name]) else urls[name]
    nn = normalize_name(name)
    for k, v in urls.items():
        kk = normalize_name(k)
        if nn and kk and (nn in kk or kk in nn): return "" if is_blocked_store(k, v) else v
    dom = store_domain(name)
    if dom:
        key = domain_key(dom)
        for k, v in urls.items():
            if key and (key in (v or "").lower() or key in normalize_name(k)): return "" if is_blocked_store(k, v) else v
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

# ---- v105: نتائج الخدمات = بطاقة لكل مزود + زر يفتح واتساب برسالة طلب الخدمة جاهزة ----
_SERVICE_LINE_RE = re.compile(
    r"^\s*(🏆|✅|•)\s*(.+?)\s*\(\s*(?:هاتف|Phone|phone|Tel|tel)\s*[:：]\s*([^)]+?)\s*\)\s*(?:(?:—|–|-|:|،|,)\s*)?(.*)$"
)

SERVICE_REQUEST_MSG = {
    "ar": "السلام عليكم 👋\nأحتاج {service}\nمتى ممكن؟",
    "en": "Hello 👋\nI need {service}\nWhen are you available?",
    "fr": "Bonjour 👋\nJ’ai besoin de : {service}\nQuand êtes-vous disponible ?",
    "es": "Hola 👋\nNecesito: {service}\n¿Cuándo está disponible?",
    "pt": "Olá 👋\nPreciso de: {service}\nQuando está disponível?",
    "tr": "Merhaba 👋\n{service} lazım\nNe zaman müsaitsiniz?",
    "ru": "Здравствуйте 👋\nНужно: {service}\nКогда вы доступны?",
    "zh": "您好 👋\n我需要：{service}\n什么时候方便？",
    "hi": "नमस्ते 👋\nमुझे चाहिए: {service}\nआप कब उपलब्ध हैं?",
    "ur": "السلام علیکم 👋\nمجھے چاہیے: {service}\nآپ کب دستیاب ہیں؟",
}
SERVICE_REQUEST_BUTTON = {
    "ar": "📲 اطلب الخدمة", "en": "📲 Request service", "fr": "📲 Demander", "es": "📲 Solicitar",
    "pt": "📲 Solicitar", "tr": "📲 Talep gönder", "ru": "📲 Запросить", "zh": "📲 预约服务",
    "hi": "📲 सेवा मांगें", "ur": "📲 سروس مانگیں",
}

def _market_dial_code(cc=None):
    """رمز الاتصال الدولي لسوق المستخدم الحالي (الكويت = 965) من جدول CALLING_CODE_TO_COUNTRY."""
    cc = (cc or current_market().get("country") or DEFAULT_COUNTRY or "kw").lower()
    codes = [code for code, c in CALLING_CODE_TO_COUNTRY.items() if c == cc]
    if not codes:
        return "965" if cc == "kw" else ""
    return sorted(codes, key=len)[0]

def _service_phone_intl(raw_phone, dial=None):
    """يحوّل رقم المزود كما ظهر في النتائج إلى صيغة دولية بدون + مناسبة لرابط wa.me."""
    digits = re.sub(r"\D", "", str(raw_phone or ""))
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) < 6:
        return ""
    dial = dial if dial is not None else _market_dial_code()
    if dial and digits.startswith(dial) and len(digits) >= len(dial) + 6:
        return digits
    return f"{dial}{digits.lstrip('0')}" if dial else digits

def _service_request_link(intl_phone, service_desc, lang="ar"):
    template = SERVICE_REQUEST_MSG.get(lang) or _dynamic_translate_ui(SERVICE_REQUEST_MSG["en"], lang)
    service = re.sub(r"\s+", " ", str(service_desc or "")).strip()[:120]
    msg = template.format(service=service) if service else template.split("\n")[0]
    return f"https://wa.me/{intl_phone}?text={urllib.parse.quote(msg)}"

def parse_service_providers(txt):
    """يقسم رد الخدمات إلى: مقدمة نصية (إجابة سؤال فني إن وجدت) + قائمة مزودين {emoji, name, phone, detail}."""
    intro, providers = [], []
    for line in (txt or "").splitlines():
        s = line.strip()
        if not s:
            continue
        if re.match(r"(?im)^\s*LINKS\s*:", s):
            continue
        m = _SERVICE_LINE_RE.match(s)
        if m:
            providers.append({"emoji": m.group(1), "name": m.group(2).strip(" -—–:"), "phone": m.group(3).strip(), "detail": (m.group(4) or "").strip(" -—–")})
        elif not providers:
            intro.append(s)
    return "\n".join(intro).strip(), providers

def send_service_result(from_number, txt, bot_id, lang, service_desc):
    """v105: الأرقام تظهر كنص عادي، والرابط الوحيد هو زر واتساب برسالة طلب الخدمة الجاهزة.

    يعيد عدد البطاقات المرسلة؛ عند فشل التحليل يرسل النص كما هو (السلوك القديم)."""
    intro, providers = parse_service_providers(txt)
    if not providers:
        send_whatsapp_text(from_number, txt, bot_id)
        return 0
    if intro:
        send_whatsapp_text(from_number, intro, bot_id)
    dial = _market_dial_code()
    sent = 0
    button = (SERVICE_REQUEST_BUTTON.get(lang) or _dynamic_translate_ui(SERVICE_REQUEST_BUTTON["en"], lang))[:20]
    for p in providers[:MAX_STORES]:
        body = f"{p['emoji']} {p['name']}\n📞 {p['phone']}"
        if p.get("detail"):
            body += f"\n{p['detail']}"
        intl = _service_phone_intl(p["phone"], dial)
        if not intl:
            send_whatsapp_text(from_number, body, bot_id)
            continue
        ok = send_whatsapp_cta(from_number, body, _service_request_link(intl, service_desc, lang), bot_id, button)
        if not ok:
            send_whatsapp_text(from_number, body, bot_id)
        sent += 1
    return sent


def send_product_result(from_number, txt, urls, bot_id, lang, query, best_only=False):
    if not txt:
        send_whatsapp_text(from_number, T(lang, "not_found"), bot_id)
        return "none"
    if is_service_answer(txt):
        # v105: الخدمات: بطاقة لكل مزود (اسم + رقم كنص) وزر واتساب برسالة طلب الخدمة.
        send_service_result(from_number, txt, bot_id, lang, query)
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
        r = requests.post(gemini_url, params={"key": GEMINI_API_KEY}, json=payload, timeout=(5, GEMINI_SEARCH_TIMEOUT_SECONDS if use_search else GEMINI_PLAIN_TIMEOUT_SECONDS))
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
    except Exception: return "المتجر"

def best_of_search(parts, lang="ar"):
    """اتصال واحد فقط. يعاد الاتصال مرة واحدة فقط عند فشل تقني وبموافقة Environment Variable."""
    txt, urls = call_gemini(parts)
    if txt or not ENABLE_SEARCH_RETRY:
        return txt, urls
    print("SEARCH RETRY: first call returned empty")
    return call_gemini(parts)

def bilingual_search_instruction(query, lang):
    """Worldwide search aliases: user's wording + English commercial name + local commerce language."""
    response_rule = lang_instr(lang)
    m = current_market()
    market_name = m.get("country_name", "Kuwait")
    hl = m.get("search_hl") or country_search_hl()
    return (
        f"Search this exact product in {market_name}: {query}. "
        f"Use the user's wording, the commercial English name, and a {hl} local-market wording when that improves discovery. "
        f"Exhaust genuine {market_name} stores first; then United States; then China only. Reject every other country. "
        "Within each market sort by price, but geography always outranks price. Every offer needs a numeric current price and direct product page. "
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
    # Latin-script product names are searchable as-is. Translate Arabic/Urdu, Devanagari, CJK and Cyrillic once (cached).
    if not re.search(r"[\u0600-\u06FF\u0900-\u097F\u3040-\u30FF\u3400-\u9FFF\u0400-\u04FF]", q):
        return q
    # Image/AI identities often already contain "Arabic | English". Reuse the Latin alias
    # instead of paying for another translation round-trip.
    if re.search(r"[A-Za-z]", q):
        parts = [x.strip() for x in re.split(r"\s*[|｜]\s*", q) if x.strip()]
        latin = next((x for x in parts if re.search(r"[A-Za-z]", x) and not re.search(r"[\u0600-\u06FF\u0900-\u097F\u3040-\u30FF\u3400-\u9FFF\u0400-\u04FF]", x)), "")
        if latin and len(latin) <= 100:
            return latin
    key = re.sub(r"\s+", " ", normalize_ar(q))[:150]
    with EN_NAME_LOCK:
        if key in EN_NAME_CACHE:
            return EN_NAME_CACHE[key]
    raw, _ = call_gemini([{"text": q}], system=TRANSLATE_NAME_SYSTEM, use_search=False)
    name = (raw or "").strip().splitlines()[0].strip().strip('"').strip("'")
    # حماية: لازم يكون إنجليزياً فعلاً وبطول منطقي، وإلا نتجاهله ونكمل بالعربي.
    if not re.search(r"[A-Za-z]", name) or re.search(r"[\u0600-\u06FF\u0900-\u097F\u3040-\u30FF\u3400-\u9FFF\u0400-\u04FF]", name) or len(name) > 90:
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
    ".com.kw", ".kw", "kuwait", "الكويت", "xcite", "eureka", "best al yousifi", "best alyousifi",
    "jarir", "level shoes", "future store", "blink", "noon kuwait", "carrefour kuwait", "lulu kuwait",
    "jm3eia", "جمعية", "taw9eel", "توصيل", "intersport kuwait", "decathlon kuwait", "boutiqaat",
    "boots kuwait", "yiaco", "royal pharmacy", "talabat kuwait", "keeta kuwait"
)

US_STORE_HINTS = (
    "amazon.com", "walmart.com", "target.com", "bestbuy.com", "costco.com", "homedepot.com", "lowes.com",
    "macys.com", "nordstrom.com", "zappos.com", "bhphotovideo.com", "newegg.com", "rei.com",
    "dickssportinggoods.com", "ebay.com",
)
CHINA_STORE_HINTS = (
    "aliexpress.com", "alibaba.com", "1688.com", "taobao.com", "tmall.com", "shein.com", "temu.com",
    "dhgate.com", "made-in-china.com", "banggood.com", "gearbest.com", "jd.com", "pinduoduo.com",
)


def _result_hay_host(item):
    hay = " ".join(str(item.get(k) or "") for k in (
        "title", "source", "link", "domain", "snippet", "price", "price_text", "currency", "country", "market_country", "_lens_country", "_shopping_gl"
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


def _explicit_market_country(item):
    """Country asserted by the merchant/result itself. Search geo (gl/Lens country) is NOT merchant country."""
    for key in ("market_country", "country"):
        value = str((item or {}).get(key) or "").lower().strip()
        if len(value) == 2 and value in COUNTRY_META:
            return value
    return ""


def _search_geo_country(item):
    """Soft geo signal: country used to run Google Shopping/Lens, not proof of seller location."""
    for key in ("_shopping_gl", "_lens_country"):
        value = str((item or {}).get(key) or "").lower().strip()
        if len(value) == 2 and value in COUNTRY_META:
            return value
    return ""


def _host_country_code(host):
    host = (host or "").lower().split(":",1)[0]
    if not host:
        return ""
    for cc in COUNTRY_META:
        for tld in country_tlds(cc):
            if host == tld.lstrip(".") or host.endswith(tld):
                return cc
    return ""


def _dynamic_country_url_hit(cc, link, host):
    cc = (cc or "").lower()
    if not cc or len(cc) != 2:
        return False
    text = f"{host} {link}".lower()
    tokens = (f"/{cc}/", f"-{cc}/", f"-{cc}.", f"_{cc}", f"{cc}-en", f"{cc}-ar", f"{cc}-fr", f"{cc}-es")
    return any(t in text for t in tokens)


def _explicit_currency_codes(item):
    hay, _ = _result_hay_host(item)
    return set(re.findall(r"\b[A-Z]{3}\b", hay.upper())) & KNOWN_CURRENCY_CODES


def is_us_market_result(item):
    explicit = _explicit_market_country(item)
    if explicit:
        return explicit == "us"
    hay, host = _result_hay_host(item)
    if host.endswith(".us") or _host_matches_any(host, US_STORE_HINTS):
        return True
    if _host_matches_any(host, CHINA_STORE_HINTS):
        return False
    # USD is useful evidence only when it is not also a legal/local currency in the user's market.
    local_codes = set(country_currency_codes())
    if "USD" in _explicit_currency_codes(item) and "USD" not in local_codes:
        return True
    # Search geo (gl/Lens country) is only where Google was queried, not proof that the merchant is American.
    return False


def is_china_market_result(item):
    explicit = _explicit_market_country(item)
    if explicit:
        return explicit == "cn"
    hay, host = _result_hay_host(item)
    if host.endswith(".cn") or _host_matches_any(host, CHINA_STORE_HINTS):
        return True
    local_codes = set(country_currency_codes())
    if ("CNY" in _explicit_currency_codes(item) and "CNY" not in local_codes) or bool(re.search(r"\bRMB\b|人民币|中国|china", hay, flags=re.I)):
        return True
    # Search geo (gl/Lens country) is only where Google was queried, not proof that the merchant is Chinese.
    return False


def is_local_lens_result(item):
    """Strict worldwide local-market classifier using merchant evidence, never search-geo alone."""
    m = current_market()
    cc = (m.get("country") or DEFAULT_COUNTRY).lower()
    explicit = _explicit_market_country(item)
    if explicit:
        return explicit == cc
    hay, host = _result_hay_host(item)
    link = str((item or {}).get("link") or (item or {}).get("url") or "").lower()
    host_cc = _host_country_code(host)
    if host_cc:
        return host_cc == cc
    if _dynamic_country_url_hit(cc, link, host):
        return True
    country_name = str(m.get("country_name") or "").lower()
    if country_name and country_name in hay:
        return True
    if cc == "kw" and any(h in hay for h in KUWAIT_STORE_HINTS):
        return True
    for label, domain in country_major_store_specs(cc):
        if _host_matches_any(host, (domain,)) or normalize_name(label) in normalize_name(hay):
            return True
    codes = _explicit_currency_codes(item)
    local_codes = set(country_currency_codes(cc))
    if codes & local_codes:
        return True
    # For symbol-only prices ($/¥/£), resolve using local market context instead of assuming USD/JPY/GBP.
    price_blob = " ".join(str((item or {}).get(k) or "") for k in ("price", "price_text", "currency")).strip()
    if price_blob:
        # Currency is LOCAL evidence only when it is actually present in the result.
        # Never feed the local currency as a fallback here, otherwise a blank/unknown
        # price returned by gl=KW gets silently interpreted as KWD and becomes falsely local.
        detected = detect_currency_code(price_blob, "", cc)
        if detected and detected in local_codes:
            return True
    # IMPORTANT: Google/Lens search geo is NOT merchant nationality.
    # A result returned by gl=KW can still be Italian, German, etc. Therefore an ambiguous
    # generic-domain result is never labelled LOCAL unless one of the hard/merchant signals
    # above confirms it (ccTLD/path/country text/known local merchant/local currency).
    return False


def is_foreign_lens_result(item):
    if is_local_lens_result(item):
        return False
    cc = (current_market().get("country") or DEFAULT_COUNTRY).lower()
    explicit = _explicit_market_country(item)
    if explicit and explicit != cc:
        return True
    _, host = _result_hay_host(item)
    host_cc = _host_country_code(host)
    if host_cc and host_cc != cc:
        return True
    codes = _explicit_currency_codes(item)
    local_codes = set(country_currency_codes(cc))
    if codes and not (codes & local_codes):
        return True
    # Search geo is not seller nationality, so never use it alone as foreign proof either.
    return bool(host and (_host_matches_any(host, US_STORE_HINTS) or _host_matches_any(host, CHINA_STORE_HINTS)))


def result_market_rank(item):
    """0=local market, 1=US, 2=China, 99=reject/other country."""
    cc = (current_market().get("country") or DEFAULT_COUNTRY).lower()
    url = str((item or {}).get("link") or (item or {}).get("url") or "")
    source = str((item or {}).get("source") or (item or {}).get("name") or "")
    if is_blocked_store(source, url):
        return 99
    explicit = _explicit_market_country(item)
    if explicit == cc:
        return 0
    if explicit == "us":
        return 0 if cc == "us" else 1
    if explicit == "cn":
        return 0 if cc == "cn" else (1 if cc == "us" else 2)
    # Explicit third-country geo targeting is not allowed.
    if explicit and explicit not in {cc, "us", "cn"}:
        return 99
    # Check strong US/China merchant evidence before generic local-currency evidence.
    # This matters in USD-local markets (e.g. Ecuador/Panama): amazon.com must stay US,
    # not become "local" merely because both markets use USD.
    if cc != "us" and is_us_market_result(item):
        return 1
    if cc != "cn" and is_china_market_result(item):
        return 1 if cc == "us" else 2
    if is_local_lens_result(item):
        return 0
    if is_us_market_result(item):
        return 0 if cc == "us" else 1
    if is_china_market_result(item):
        return 0 if cc == "cn" else (1 if cc == "us" else 2)
    _, host = _result_hay_host(item)
    host_cc = _host_country_code(host)
    if host_cc and host_cc not in {cc, "us", "cn"}:
        return 99
    # A clearly different currency is foreign; only USD/CNY are permitted foreign markets.
    codes = _explicit_currency_codes(item)
    local_codes = set(country_currency_codes(cc))
    if codes:
        if codes & local_codes:
            return 0
        if "USD" in codes and "USD" not in local_codes:
            return 1
        if "CNY" in codes and "CNY" not in local_codes:
            return 2 if cc != "us" else 1
        return 99
    return 99


def filter_allowed_market_results(verified, exclude_local=False):
    kept = {}
    for name, info in (verified or {}).items():
        item = {
            "link": info.get("url", ""), "source": name, "title": info.get("title", ""),
            "currency": info.get("currency", ""), "price": info.get("price_text", "") or info.get("price", ""),
            "market_country": info.get("market_country", "") or info.get("country", ""),
        }
        rank = result_market_rank(item)
        if rank == 99 or (exclude_local and rank == 0):
            print(f"MARKET FILTER REJECT rank={rank}: {name} -> {info.get('url','')}")
            continue
        info["market_rank"] = rank
        kept[name] = info
    return kept


def prepare_market_offer(info, name, lang="ar"):
    item = {
        "link": info.get("url", ""), "source": name, "title": info.get("title", ""),
        "currency": info.get("currency", ""), "price": info.get("price_text", "") or info.get("price", ""),
        "market_country": info.get("market_country", "") or info.get("country", ""),
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
        return rank, numeric, f"{format_price(numeric)} {currency_label(lang)}"
    src = (info.get("currency") or "").upper().strip()
    if not src:
        src = "USD" if rank == 1 else "CNY"
    shown, converted = display_global_price(numeric, "", src, lang)
    return rank, (converted if converted is not None else numeric), shown

def filter_local_market_only(verified):
    kept = {}
    for name, info in (verified or {}).items():
        item = {
            "link": info.get("url", ""), "source": name, "title": info.get("title", ""),
            "currency": info.get("currency", ""), "price": info.get("price_text", "") or info.get("price", ""),
            "market_country": info.get("market_country", "") or info.get("country", ""),
        }
        if result_market_rank(item) != 0:
            print(f"LOCAL MODE REJECT FOREIGN/UNKNOWN: {name} -> {info.get('url','')}")
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


def _serpapi_shopping_request(query, gl, hl="en", timeout_seconds=None):
    """طلب google_shopping واحد. يعيد shopping_results (قد تكون فارغة)."""
    params = {
        "engine": "google_shopping", "q": query, "api_key": SERPAPI_API_KEY,
        "hl": hl, "output": "json",
    }
    if gl:
        params["gl"] = gl
    try:
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=(4, timeout_seconds or SERPAPI_TIMEOUT_SECONDS))
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
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=(4, SERPAPI_TIMEOUT_SECONDS))
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


def _ai_local_market_search_query(query, english_name=""):
    """Conditional FAST translation/normalization for weak local markets only. No web search here."""
    if not LOCAL_AI_QUERY_RESCUE_ENABLED:
        return ""
    m = current_market()
    cc = (m.get("country") or DEFAULT_COUNTRY).lower()
    country_name = m.get("country_name") or cc.upper()
    local_hl = m.get("search_hl") or country_search_hl(cc)
    base = _shopping_clean_query(english_name or query) or _shopping_clean_query(query)
    if not base or not local_hl or local_hl == "en":
        return ""
    key = (cc, normalize_ar(base).lower())
    now = time.time()
    with LOCAL_QUERY_CACHE_LOCK:
        hit = LOCAL_QUERY_CACHE.get(key)
        if hit and now - hit[0] < 86400:
            return hit[1]
    system = f"""You create ONE high-precision shopping search query for the local retail market in {country_name}.
Return ONLY the query, one line, no explanation.
Use the dominant language/wording that shoppers and local stores in {country_name} commonly use.
Preserve every brand, model, SKU, capacity, size and number exactly. Never invent specifications.
Translate only generic product/category words when that improves local merchant discovery.
If the original international/English wording is already what local stores use, return it unchanged."""
    try:
        raw, _ = text77_call_gemini([{"text": base}], system=system, use_search=False)
        candidate = re.sub(r"^[\s\"'`]+|[\s\"'`]+$", "", (raw or "").splitlines()[0].strip()) if raw else ""
        candidate = re.sub(r"^(?:QUERY|SEARCH_QUERY)\s*:\s*", "", candidate, flags=re.I).strip()
        # Protect model/SKU tokens containing digits from accidental translation/hallucination.
        must_keep = {t.lower() for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9._/-]*", base) if re.search(r"\d", t)}
        cand_low = candidate.lower()
        if not candidate or len(candidate) > 180 or any(tok not in cand_low for tok in must_keep):
            candidate = ""
    except Exception as e:
        print(f"LOCAL AI QUERY ERR {cc}: {e}")
        candidate = ""
    with LOCAL_QUERY_CACHE_LOCK:
        if len(LOCAL_QUERY_CACHE) > 2000:
            LOCAL_QUERY_CACHE.clear()
        LOCAL_QUERY_CACHE[key] = (now, candidate)
    if candidate and candidate.lower() != base.lower():
        print(f"LOCAL AI QUERY market={cc}: {base!r} -> {candidate!r}")
    return candidate


def google_shopping_offers(query, lang="ar", allow_global=False, lens_context=None, english_name=""):
    """Worldwide Google Shopping layer with local-first multi-locale discovery.

    LOCAL mode preserves the original English/gl pass and adds a parallel local-language pass.
    A direct-store rescue is triggered only when local coverage is still below LOCAL_RESULTS_TARGET.
    """
    if not ENABLE_GOOGLE_SHOPPING or not SERPAPI_API_KEY:
        return {}
    raw_q = _shopping_clean_query(query)
    en_q = _shopping_clean_query(english_name or query)
    if not (raw_q or en_q):
        return {}

    m = current_market()
    local_cc = (m.get("country") or DEFAULT_COUNTRY).lower()
    local_hl = (m.get("search_hl") or country_search_hl(local_cc) or "en").lower()

    if allow_global:
        specs = [(en_q or raw_q, "us", "en")]
    else:
        # Pass 1 is exactly the successful original behavior: commercial English name + local gl + hl=en.
        specs = [(en_q or raw_q, local_cc, "en")]
        # Pass 2 gives local-language indexing a real chance (Arabic in Kuwait, Japanese in Japan, etc.).
        local_query = raw_q or en_q
        if (local_query, local_cc, local_hl) not in specs:
            specs.append((local_query, local_cc, local_hl))
        # Optional third pass is useful when query was translated and the local language differs from English.
        if LOCAL_SHOPPING_PRIMARY_PASSES >= 3 and en_q and local_hl != "en" and (en_q, local_cc, local_hl) not in specs:
            specs.append((en_q, local_cc, local_hl))
        specs = specs[:LOCAL_SHOPPING_PRIMARY_PASSES]

    def _fetch_spec(spec):
        q, gl, hl = spec
        cards = _serpapi_shopping_request(q, gl, hl=hl)
        out = []
        for card in cards or []:
            c = dict(card)
            c["_shopping_gl"] = gl
            c["_shopping_hl"] = hl
            c["_shopping_query"] = q
            out.append(c)
        return out

    cards = []
    if len(specs) == 1:
        cards = _fetch_spec(specs[0])
    else:
        futures = {LOCAL_SHOPPING_POOL.submit(_fetch_spec, spec): spec for spec in specs}
        for fut, spec in futures.items():
            try:
                cards.extend(fut.result(timeout=SERPAPI_TIMEOUT_SECONDS + 5) or [])
            except Exception as e:
                print(f"LOCAL SHOPPING PASS ERR spec={spec}: {e}")

    # Deduplicate cards returned by multiple locales while preserving the earliest/best pass.
    dedup_cards, seen_cards = [], set()
    for card in cards:
        sig = (
            str(card.get("link") or "").split("?")[0].lower(),
            str(card.get("title") or "").lower(),
            str(card.get("source") or "").lower(),
            str(card.get("price") or "").lower(),
        )
        if sig in seen_cards:
            continue
        seen_cards.add(sig); dedup_cards.append(card)
    cards = dedup_cards
    if not cards:
        print(f"SHOPPING PRIMARY EMPTY market={local_cc} allow_global={allow_global}; continuing to rescue layers")

    offers, used_urls, immersive_tokens = {}, set(), []

    def _add(store_name, url, price_text, price_value, title, position, market_country=""):
        url = _shopping_direct_url(url)
        if not url or url in used_urls:
            return
        if is_blocked_store(store_name, url):
            print(f"SHOPPING BLOCKED STORE REJECT: {store_name} -> {url}")
            return
        search_gl = (market_country or ("us" if allow_global else local_cc)).lower()
        item = {
            "link": url, "source": store_name, "title": title, "price": str(price_text or ""),
            "currency": "", "market_country": "", "_shopping_gl": search_gl,
        }
        market_rank = result_market_rank(item)
        if allow_global:
            expected_rank = 1 if search_gl == "us" else (2 if search_gl == "cn" else None)
            if market_rank == 0 or market_rank == 99 or (expected_rank is not None and market_rank != expected_rank):
                print(f"SHOPPING GLOBAL MARKET REJECT rank={market_rank} gl={search_gl}: {store_name} -> {url}")
                return
        else:
            # Google gl is a strong search signal, but not proof of merchant nationality.
            # Strong US/China hosts and third-country ccTLDs are rejected before the soft gl-local fallback.
            if market_rank != 0:
                print(f"SHOPPING LOCAL REJECT rank={market_rank} gl={search_gl}: {store_name} -> {url}")
                return
        resolved_market_country = local_cc if market_rank == 0 else ("us" if market_rank == 1 else "cn" if market_rank == 2 else "")
        try:
            numeric = float(price_value) if price_value not in (None, "") else None
        except Exception:
            numeric = None
        if numeric is None:
            numeric = _extract_numeric_price(str(price_text or ""))
        if numeric is None or numeric <= 0:
            return

        if allow_global:
            fallback_cur = "USD" if search_gl == "us" else "CNY" if search_gl == "cn" else ""
            src_currency = detect_currency_code(str(price_text or ""), fallback_cur, search_gl)
            shown, converted = display_global_price(numeric, str(price_text or ""), src_currency, lang)
            sort_price = converted if converted is not None else numeric
        else:
            accepted = set(country_currency_codes(local_cc))
            local_primary = (m.get("currency") or "").upper()
            src_currency = detect_currency_code(str(price_text or ""), local_primary, local_cc)
            if src_currency and accepted and src_currency not in accepted:
                print(f"SHOPPING LOCAL CURRENCY REJECT: {store_name} {price_text} detected={src_currency}")
                return
            src_currency = src_currency or local_primary
            if src_currency and src_currency != local_primary:
                converted = convert_to_local(numeric, src_currency)
                sort_price = converted if converted is not None else numeric
                shown = f"{format_price(numeric, src_currency)} {src_currency}"
            else:
                sort_price = numeric
                shown = f"{format_price(numeric, local_primary)} {currency_label(lang)}"

        name = (store_name or "").strip()[:40] or f"Store {len(offers)+1}"
        base, n = name, 2
        while name in offers:
            name = f"{base} {n}"; n += 1
        offers[name] = {
            "url": url, "price": sort_price, "price_text": shown, "title": (title or "").strip(),
            "currency": src_currency, "position": position, "source_layer": "shopping",
            "market_country": resolved_market_country, "search_gl": search_gl,
        }
        used_urls.add(url)

    for i, card in enumerate(cards, 1):
        title = (card.get("title") or "").strip()
        source = (card.get("source") or "").strip()
        direct = (card.get("link") or "").strip()
        gl = (card.get("_shopping_gl") or ("us" if allow_global else local_cc)).lower()
        added_before = len(offers)
        if direct:
            _add(source or title, direct, card.get("price"), card.get("extracted_price"), title, i, gl)
        token = (card.get("immersive_product_page_token") or "").strip()
        if token and len(offers) == added_before:
            immersive_tokens.append((i, title, token, gl))

    if immersive_tokens and IMMERSIVE_LOOKUPS_MAX > 0 and len(offers) < MAX_STORES:
        picked = immersive_tokens[:IMMERSIVE_LOOKUPS_MAX]
        market_snapshot = current_market()
        futures = {
            SHOPPING_POOL.submit(_run_with_market, market_snapshot, _immersive_product_stores, token): (pos, title, gl)
            for pos, title, token, gl in picked
        }
        for future, (pos, title, gl) in futures.items():
            try:
                stores = future.result(timeout=SERPAPI_TIMEOUT_SECONDS + 5) or []
            except Exception as e:
                print(f"IMMERSIVE FUTURE ERR: {e}")
                continue
            for store in stores:
                _add(
                    store.get("name") or "", store.get("link") or "",
                    store.get("price") or store.get("total") or "",
                    store.get("extracted_price") if store.get("extracted_price") not in (None, "") else store.get("extracted_total"),
                    title, pos, gl,
                )

    # Rescue local merchant domains only when broad local Shopping is weak. No penalty for strong markets.
    if not allow_global and len(offers) < LOCAL_RESULTS_TARGET and LOCAL_STORE_RESCUE_MAX > 0:
        rescue_specs = local_rescue_store_specs(query, LOCAL_STORE_RESCUE_MAX)
        def _rescue(label, domain):
            q = en_q or raw_q
            rs = _serpapi_shopping_request(f"{q} site:{domain}", local_cc, hl=local_hl, timeout_seconds=MARKET_FALLBACK_TIMEOUT_SECONDS)
            return label, domain, rs
        futures = {LOCAL_SHOPPING_POOL.submit(_rescue, label, domain):(label,domain) for label,domain in rescue_specs}
        for fut, (label, domain) in futures.items():
            try:
                _, _, rs = fut.result(timeout=MARKET_FALLBACK_TIMEOUT_SECONDS + 4)
            except Exception as e:
                print(f"LOCAL STORE RESCUE ERR {label}: {e}")
                continue
            for card in rs or []:
                link = (card.get("link") or "").strip()
                direct = _shopping_direct_url(link) or link
                try:
                    host = urllib.parse.urlparse(direct).netloc.lower().replace("www.", "")
                except Exception:
                    host = ""
                if not _host_matches_any(host, (domain,)):
                    continue
                _add(card.get("source") or label, direct, card.get("price"), card.get("extracted_price"), card.get("title") or "", int(card.get("position") or 999), local_cc)

    # Generic country rescue for markets without a curated merchant profile or where the first passes were sparse.
    # Runs only on weak LOCAL coverage, so Kuwait/other strong markets do not pay extra latency when already healthy.
    if not allow_global and LOCAL_COUNTRY_RESCUE_ENABLED and len(offers) < LOCAL_RESULTS_TARGET:
        country_name = str(m.get("country_name") or "").strip()
        rescue_queries = []
        base = en_q or raw_q
        if country_name and base:
            rescue_queries.append(f"{base} {country_name}")
        if LOCAL_COUNTRY_RESCUE_PASSES >= 2 and raw_q and raw_q.lower() != base.lower() and country_name:
            rescue_queries.append(f"{raw_q} {country_name}")
        for rq in rescue_queries[:LOCAL_COUNTRY_RESCUE_PASSES]:
            try:
                rs = _serpapi_shopping_request(rq, local_cc, hl=local_hl, timeout_seconds=MARKET_FALLBACK_TIMEOUT_SECONDS)
            except Exception as e:
                print(f"LOCAL COUNTRY RESCUE ERR {local_cc}/{rq[:70]}: {e}")
                rs = []
            for card in rs or []:
                _add(
                    card.get("source") or country_name or "Local", card.get("link") or "",
                    card.get("price") or "", card.get("extracted_price"),
                    card.get("title") or "", int(card.get("position") or 999), local_cc,
                )
                if len(offers) >= LOCAL_RESULTS_TARGET:
                    break
            if len(offers) >= LOCAL_RESULTS_TARGET:
                break

    # Final LOCAL-only rescue: translate/normalize product identity into the market's own retail wording.
    # It runs only when all no-AI local passes are still below target, protecting normal response time.
    if not allow_global and LOCAL_AI_QUERY_RESCUE_ENABLED and len(offers) < LOCAL_RESULTS_TARGET:
        localized_q = _ai_local_market_search_query(raw_q or query, en_q or english_name)
        if localized_q and localized_q.lower() not in {str(en_q or "").lower(), str(raw_q or "").lower()}:
            try:
                rs = _serpapi_shopping_request(localized_q, local_cc, hl=local_hl, timeout_seconds=MARKET_FALLBACK_TIMEOUT_SECONDS)
            except Exception as e:
                print(f"LOCAL AI SHOPPING RESCUE ERR {local_cc}: {e}")
                rs = []
            for card in rs or []:
                _add(
                    card.get("source") or (m.get("country_name") or "Local"), card.get("link") or "",
                    card.get("price") or "", card.get("extracted_price"),
                    card.get("title") or "", int(card.get("position") or 999), local_cc,
                )
                if len(offers) >= LOCAL_RESULTS_TARGET:
                    break

    offers = filter_same_size(offers, en_q or raw_q)
    if lens_context:
        offers = filter_verified_with_lens(offers, lens_context)
    if offers:
        print(f"SHOPPING OFFERS FINAL market={local_cc} passes={specs}: {[(n, o['price']) for n, o in offers.items()]}")
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
            _stores_phrase = (f"ابدأ بالمتاجر المحلية القوية مثل: {stores_hint}، ثم وسّع لأي متجر محلي موثوق. " if stores_hint else "ابدأ بأقوى المتاجر المتخصصة والمنصات المحلية، ثم وسّع لأي متجر محلي موثوق. ")
            search_scope = (
                _stores_phrase
                + f"ابحث محلياً أيضاً بصياغة لغة السوق {country_search_hl()} وبالعملة/العملات المحلية {', '.join(country_currency_codes())}. "
                + "بعد استنفاد المحلي ابحث في الولايات المتحدة، ثم الصين فقط. "
                + f"ارفض أي دولة أخرى غير {market_name} والولايات المتحدة والصين. "
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
            "لا تكتب متوفر أو InStock بدلاً من السعر. حافظ على السعر الرقمي والعملة كما في المصدر؛ التطبيق ينسق عدد الخانات حسب العملة. "
            f"{lang_instr(lang)}"
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


_PRICE_CHAR_TRANSLATION = str.maketrans({
    **{ord(a): b for a, b in zip("٠١٢٣٤٥٦٧٨٩", "0123456789")},
    **{ord(a): b for a, b in zip("۰۱۲۳۴۵۶۷۸۹", "0123456789")},
    ord("٫"): ".", ord("٬"): ",",
})

def _normalize_price_chars(value):
    return str(value or "").translate(_PRICE_CHAR_TRANSLATION)


def _normalize_price_token(token, currency_code=""):
    t = _normalize_price_chars(token).replace("\u00a0", " ").replace("\u202f", " ").strip()
    t = re.sub(r"\s+", "", t)
    if not t:
        return None
    # Keep only numeric separators/sign.
    t = re.sub(r"[^0-9,.-]", "", t)
    if not re.search(r"\d", t):
        return None
    neg = t.startswith("-")
    t = t.lstrip("-")
    dots, commas = t.count("."), t.count(",")
    decimals = CURRENCY_DECIMALS.get((currency_code or "").upper(), 2)
    if dots and commas:
        # Last separator is decimal when it has a plausible minor-unit tail; the other is thousands.
        last_dot, last_comma = t.rfind("."), t.rfind(",")
        dec_sep = "." if last_dot > last_comma else ","
        tail = len(t) - max(last_dot, last_comma) - 1
        if tail in ({decimals} if decimals in (0,3) else {1,2}):
            thou = "," if dec_sep == "." else "."
            t = t.replace(thou, "").replace(dec_sep, ".")
        else:
            t = t.replace(".", "").replace(",", "")
    elif commas:
        pos = t.rfind(","); tail = len(t) - pos - 1
        if (decimals == 3 and tail == 3) or (decimals == 2 and tail in (1,2)):
            t = t[:pos].replace(",", "") + "." + t[pos+1:]
        else:
            t = t.replace(",", "")
    elif dots:
        pos = t.rfind("."); tail = len(t) - pos - 1
        if t.count(".") > 1:
            if (decimals == 3 and tail == 3) or (decimals == 2 and tail in (1,2)):
                t = t[:pos].replace(".", "") + "." + t[pos+1:]
            else:
                t = t.replace(".", "")
        elif decimals == 0 and tail == 3:
            t = t.replace(".", "")
    try:
        val = float(t)
        return -val if neg else val
    except Exception:
        return None


def _extract_numeric_price(line):
    """Worldwide price parser: supports ISO currencies and comma/dot/space locale formatting."""
    text = _normalize_price_chars(line).replace("\u00a0", " ").replace("\u202f", " ")
    cur = detect_currency_code(text, "")
    # Price normally sits after the final dash in generated offer lines; this avoids model numbers in titles.
    parts = re.split(r"\s+(?:—|–|-)\s+", text)
    zones = [parts[-1]] if len(parts) > 1 else []
    zones.append(text)
    number_re = re.compile(r"(?<!\w)(\d{1,3}(?:,\d{2})+,\d{3}(?:\.\d{1,3})?|\d{1,3}(?:[ .,'’]\d{3})+(?:[.,]\d{1,3})?|\d+(?:[.,]\d{1,3})?)(?!\w)")
    for zone in zones:
        matches = list(number_re.finditer(zone))
        if not matches:
            continue
        # Prefer a number adjacent to currency; otherwise the last number in the price zone.
        ranked = []
        for mm in matches:
            context = zone[max(0, mm.start()-12): min(len(zone), mm.end()+12)]
            has_cur = bool(re.search(r"\b[A-Z]{3}\b|US\$|A\$|C\$|S\$|HK\$|NZ\$|NT\$|[$€£¥￥₹₩₺₽₪₴₸₾₼฿₫₱₦₵৳₲₭₮]|د\.ك|ر\.س|د\.إ|ر\.ق|ر\.ع|د\.ب|KD\b|RMB\b", context, re.I))
            ranked.append((1 if has_cur else 0, mm.start(), mm.group(1)))
        ranked.sort(reverse=True)
        for _, _, token in ranked:
            val = _normalize_price_token(token, cur)
            if val is not None and val > 0:
                return val
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
            f"سعر رقمي واضح ورابط صفحة المنتج المباشر مع العملة الأصلية. {lang_instr(lang)}"
        )
        variants = [
            base_prompt,
            f"{search_name} United States buy online exact product direct page price USD {lang_instr(lang)}",
            f"{search_name} China buy online exact product direct page price CNY RMB AliExpress Alibaba 1688 Taobao SHEIN JD {lang_instr(lang)}",
        ]
    else:
        # ثلاث عمليات بحث مستقلة تضمن وجود تغطية فعلية لكل سوق بدلاً من الاعتماد على ترتيب Google العام.
        variants = [
            prompt_text or f"ابحث عن {search_name} في {market_name} فقط. استخدم الاسم التجاري الإنجليزي ولغة السوق {country_search_hl()}، وافحص المتاجر المتخصصة والمحلية الصغيرة. السعر يجب أن يكون رقمياً بعملة محلية مقبولة ({', '.join(country_currency_codes())}) ورابط صفحة منتج مباشر. {lang_instr(lang)}",
            f"{search_name} United States buy online exact product direct product page current price USD; US stores only. {lang_instr(lang)}",
            f"{search_name} China buy online exact product direct product page current price CNY RMB; Chinese stores only such as AliExpress Alibaba 1688 Taobao SHEIN Tmall JD DHgate. {lang_instr(lang)}",
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
            txt, urls = future.result(timeout=GEMINI_SEARCH_TIMEOUT_SECONDS + 5)
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
    if (current_market().get("country") or DEFAULT_COUNTRY).lower() == "kw":
        priorities = (
            "prosportskw", "tigro", "3roodq8", "intersport", "decathlon", "sssports",
            "jm3eia", "جمعية", "xcite", "eureka", "best", "yousifi", "blink", "jarir",
            "lulu", "carrefour", "noon", "taw9eel", "توصيل", "boutiqaat", "boots", "yiaco",
            "levelshoes", "future", "talabat", "keeta"
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
    else:
        # For English/Hindi/Urdu prefer Gemini's localized title before raw Lens English.
        display_title = next((c for c in title_candidates if c), "")
    if not display_title:
        display_title = lens_display or str(query or "")
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
            return shopping_future.result(timeout=SERPAPI_TIMEOUT_SECONDS + 8) or ("", {})
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
    meta=_whatsapp_http_session().get(f"{GRAPH_URL}/{mid}",headers=h,timeout=(3, WHATSAPP_TIMEOUT_SECONDS)).json()
    img=_whatsapp_http_session().get(meta["url"],headers=h,timeout=(3, max(WHATSAPP_TIMEOUT_SECONDS, 15)))
    return base64.b64encode(img.content).decode(), meta.get("mime_type","image/jpeg")


_UI_STORE_ALIASES = {
    "amazon.com": "Amazon",
    "amazon.sa": "Amazon",
    "amazon.ae": "Amazon",
    "ebay.com": "eBay",
    "walmart.com": "Walmart",
    "aliexpress.com": "AliExpress",
    "alibaba.com": "Alibaba",
    "temu.com": "Temu",
    "shein.com": "SHEIN",
    "underarmour.sa": "Under Armour",
    "underarmour.com": "Under Armour",
    "theathletesfoot.com.kw": "The Athlete's Foot",
    "theathletesfoot.com": "The Athlete's Foot",
    "sunandsandsports.com": "Sun & Sand Sports",
    "next.sa": "Next",
    "next.com": "Next",
    "made-in-china.com": "Made-in-China",
    "whizzcart.com": "Whizzcart",
    "q8supply.com": "Q8Supply",
}


def _ui_plain_store_name(source="", link=""):
    """Human-readable merchant name with no domain/TLD, so WhatsApp won't auto-link it."""
    raw = re.sub(r"\s+", " ", str(source or "")).strip()
    try:
        host = urllib.parse.urlparse(str(link or "")).netloc.lower().split(":")[0]
        host = host[4:] if host.startswith("www.") else host
    except Exception:
        host = ""

    for dom, label in _UI_STORE_ALIASES.items():
        if host == dom or host.endswith("." + dom):
            return label
    low = raw.lower().replace("www.", "").strip()
    for dom, label in _UI_STORE_ALIASES.items():
        if dom in low:
            return label

    # If source itself looks like a domain, display only a clean merchant label.
    if re.fullmatch(r"(?:www\.)?[a-z0-9][a-z0-9.-]*\.[a-z]{2,}(?:\.[a-z]{2,})?", low, flags=re.I):
        stem = low.split(".")[0].replace("-", " ").replace("_", " ")
        return " ".join(w.capitalize() for w in stem.split()) or ("المتجر")

    # Strip a trailing TLD from mixed labels such as "Amazon.com" while keeping normal names.
    cleaned = re.sub(r"\.(?:com|net|org|co|sa|ae|kw|qa|bh|om|uk|de|fr|es|cn)(?:\.[a-z]{2})?\b", "", raw, flags=re.I)
    cleaned = re.sub(r"^www\.", "", cleaned, flags=re.I)
    return cleaned.strip(" .-/") or ("المتجر")


def _compact_ui_title(value, max_len=68):
    """Keep WhatsApp result cards short: product identity, not SEO/search-result prose."""
    s = re.sub(r"\s+", " ", str(value or "")).strip()

    # English cards need much stronger shortening because search-result titles are often SEO-heavy.
    latin_chars = len(re.findall(r"[A-Za-z]", s))
    arabic_chars = len(re.findall(r"[\u0600-\u06FF]", s))
    mostly_english = latin_chars > arabic_chars

    if mostly_english:
        # Keep the useful first phrase and remove common shopping/SEO filler.
        parts = [p.strip() for p in re.split(r"\s*[|｜]\s*", s) if p.strip()]
        if parts:
            s = parts[0]

        s = re.sub(
            r"^(?:buy|shop|order|get|find)\s+",
            "",
            s,
            flags=re.I,
        )
        s = re.sub(
            r"\b(?:online|for sale|free shipping|fast delivery|new arrival|best seller|hot sale|official store)\b",
            " ",
            s,
            flags=re.I,
        )
        s = re.sub(
            r"\b(?:for women|for men|for girls|for boys|women'?s|men'?s|girl'?s|boy'?s)\b",
            " ",
            s,
            flags=re.I,
        )
        s = re.sub(
            r"\b(?:large[- ]capacity|casual|lightweight|fashion|stylish|premium)\b",
            " ",
            s,
            flags=re.I,
        )
        s = re.sub(
            r"\b(?:in|from|at)\s+(?:Kuwait|Saudi Arabia|UAE|United Arab Emirates|USA|United States|UK|United Kingdom)\b",
            " ",
            s,
            flags=re.I,
        )
        # Remove trailing merchant/location fragments after a dash.
        s = re.sub(
            r"\s*[-–—]\s*(?:Amazon|eBay|Walmart|SHEIN|AliExpress|Alibaba|Temu|Kuwait|Saudi Arabia|UAE).*$",
            "",
            s,
            flags=re.I,
        )
        s = re.sub(r"\s*[,;:]\s*", " ", s)
        s = re.sub(r"\s{2,}", " ", s).strip(" ,-|–—")

        # Max 8 useful words in English cards.
        words = s.split()
        if len(words) > 8:
            s = " ".join(words[:8]).rstrip(" ,-|–—") + "…"
        elif len(s) > 58:
            cut = s[:59]
            if " " in cut:
                cut = cut.rsplit(" ", 1)[0]
            s = cut.rstrip(" ,-|–—") + "…"
        return s

    # Arabic cleanup.
    s = re.sub(r"^(?:اشتر(?:ي|ِ)?|اشتري|تسوق|تسوّق|اطلب|شراء)\s+", "", s, flags=re.I)
    s = re.sub(r"\b(?:أونلاين|اونلاين)\s+(?:في|من)\s+[^|،,\-–—]{2,25}\b", "", s, flags=re.I)
    s = re.sub(r"\b(?:في|من)\s+(?:الكويت|السعودية|الإمارات|الامارات|قطر|البحرين|عمان|بريطانيا|ألمانيا|المانيا|فرنسا|إسبانيا|اسبانيا)\b", "", s, flags=re.I)
    parts = [p.strip() for p in re.split(r"\s*[|｜]\s*", s) if p.strip()]
    if parts:
        s = parts[0]
    s = re.sub(r"\s*[-–—]\s*(?:تسوق|تسوّق|متوفر|اونلاين|أونلاين).*$", "", s, flags=re.I)
    s = re.sub(r"\s{2,}", " ", s).strip(" ,-|–—")
    if len(s) > max_len:
        cut = s[:max_len + 1]
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        s = cut.rstrip(" ,-|–—") + "…"
    return s



def _script_class(token):
    t = str(token or "")
    if re.search(r"[\u0600-\u06FF]", t):
        return "ar"
    if re.search(r"[A-Za-z]", t):
        return "en"
    if re.search(r"\d", t):
        return "num"
    return "neutral"


def _single_direction_lines(text_value, lang="ar", max_groups=3):
    s = re.sub(r"\s+", " ", str(text_value or "")).strip()
    if not s:
        return []
    tokens = s.split()
    groups, current = [], []
    current_cls = None
    default_cls = "ar" if lang in ("ar", "ur") else "en"
    for tok in tokens:
        cls = _script_class(tok)
        if cls in ("num", "neutral"):
            cls = current_cls or default_cls
        if current and cls != current_cls:
            groups.append(" ".join(current).strip())
            current = [tok]
            current_cls = cls
        else:
            current.append(tok)
            current_cls = cls if current_cls is None else current_cls
    if current:
        groups.append(" ".join(current).strip())
    groups = [g for g in groups if g]
    if len(groups) > max_groups:
        groups = groups[:max_groups - 1] + [" ".join(groups[max_groups - 1:]).strip()]
    return groups


def _split_price_display(price_text):
    s = re.sub(r"\s+", " ", str(price_text or "")).strip()
    if not s:
        return "", ""
    m = re.match(r"^(.*?)\s*\(([^()]+)\)\s*$", s)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return s, ""


def _build_compact_card_body(flag, store, title, price_text, lang="ar"):
    lines = []

    # Store name lives in the CTA button; only the country flag stays in the card header.
    if str(flag or "").strip():
        lines.append(str(flag).strip())

    # Product/category + model remain normal text.
    title_lines = _single_direction_lines(_compact_ui_title(title or ""), lang, max_groups=3)
    for tline in title_lines:
        if tline.strip():
            lines.append(tline.strip())

    # v80.1: لا نحذف أي بطاقة بسبب غياب السعر. نعرض السعر إذا استُخرج بأمان،
    # وإلا نبقي البطاقة مع تنبيه قصير بدل اختراع رقم أو إخفاء النتيجة بالكامل.
    price_main, price_secondary = _split_price_display(price_text or "")
    if price_main and re.search(r"\d", price_main):
        lines.append(f"*💰 {price_main}*")
        if price_secondary:
            lines.append(f"_({price_secondary})_")
    else:
        lines.append(U(lang, "price_at_store"))

    return "\n".join(lines).strip()



def _break_numeric_autolinks(value):
    """Break WhatsApp auto-linking of long standalone numeric/SKU-like sequences invisibly."""
    s = str(value or "")
    # e.g. 001-1381645 or 123456789. Prices such as 8.000 and 79.00 are excluded.
    pat = re.compile(r"(?<![\d.])((?:\d[\s-]?){7,}\d?)(?![\d.])")
    def repl(m):
        token = m.group(1)
        digit_positions = [i for i, ch in enumerate(token) if ch.isdigit()]
        if len(digit_positions) < 7:
            return token
        pos = digit_positions[min(2, len(digit_positions)-1)] + 1
        return token[:pos] + "\u2060" + token[pos:]
    return pat.sub(repl, s)


def _remove_ui_autolinks(value):
    """Remove URLs/domain patterns from visible WhatsApp text; CTA action remains the only link."""
    s = str(value or "")
    # Full URLs are never allowed in visible text.
    s = re.sub(r"https?://\S+", "", s, flags=re.I)

    # Convert visible domains into plain labels, without touching decimal prices.
    domain_re = re.compile(
        r"\b(?:www\.)?([a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)+\.(?:com|net|org|co|sa|ae|kw|qa|bh|om|uk|de|fr|es|cn|app))\b",
        flags=re.I,
    )
    def repl(m):
        dom = m.group(1).lower().replace("www.", "")
        if dom in _UI_STORE_ALIASES:
            return _UI_STORE_ALIASES[dom]
        # Try suffix aliases first (e.g. shop.amazon.com).
        for known, label in _UI_STORE_ALIASES.items():
            if dom.endswith("." + known):
                return label
        stem = dom.split(".")[0].replace("-", " ").replace("_", " ")
        return " ".join(w.capitalize() for w in stem.split())
    s = domain_re.sub(repl, s)

    # Catch common one-dot domains that the broad expression can miss.
    s = re.sub(
        r"\b([A-Za-z][A-Za-z0-9-]{1,40})\.(com|sa|ae|kw|qa|bh|om|uk|de|fr|es|cn)\b",
        lambda m: _UI_STORE_ALIASES.get(
            f"{m.group(1).lower()}.{m.group(2).lower()}",
            m.group(1).replace("-", " ").title()
        ),
        s,
        flags=re.I,
    )
    s = _break_numeric_autolinks(s)
    return re.sub(r"[ \t]{2,}", " ", s).strip()


_WHATSAPP_HTTP_CTX = threading.local()

def _whatsapp_http_session():
    """Per-worker keep-alive session: speeds consecutive WhatsApp card sends safely across threads."""
    session = getattr(_WHATSAPP_HTTP_CTX, "session", None)
    if session is None:
        session = requests.Session()
        _WHATSAPP_HTTP_CTX.session = session
    return session

def send_whatsapp_text(to,text,bot_id):
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    safe_text = _remove_ui_autolinks(text)
    payload={"messaging_product":"whatsapp","to":to,"type":"text","text":{"body":safe_text[:3900]}}
    try: return _whatsapp_http_session().post(url,json=payload,headers=h,timeout=(3, WHATSAPP_TIMEOUT_SECONDS)).ok
    except Exception: return False

def send_whatsapp_cta(to,body,link,bot_id,title):
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    safe_body = _remove_ui_autolinks(body)
    safe_title = _remove_ui_autolinks(title)
    payload={"messaging_product":"whatsapp","to":to,"type":"interactive","interactive":{"type":"cta_url","body":{"text":safe_body[:1024]},"action":{"name":"cta_url","parameters":{"display_text":safe_title[:20],"url":link}}}}
    try: return _whatsapp_http_session().post(url,json=payload,headers=h,timeout=(3, WHATSAPP_TIMEOUT_SECONDS)).ok
    except Exception: return False

def send_whatsapp_buttons(to, body, buttons, bot_id):
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    btns=[{"type":"reply","reply":{"id":b["id"],"title":_remove_ui_autolinks(b["title"])[:20]}} for b in buttons[:3]]
    payload={"messaging_product":"whatsapp","to":to,"type":"interactive","interactive":{"type":"button","body":{"text":_remove_ui_autolinks(body)[:1024]},"action":{"buttons":btns}}}
    try: return _whatsapp_http_session().post(url,json=payload,headers=h,timeout=(3, WHATSAPP_TIMEOUT_SECONDS)).ok
    except Exception: return False

def send_language_choice(to, bot_id):
    body = "🌐 Choose your language\n\nTip: you can also just type in any language and Findzia will automatically reply in that language."
    rows = [{"id": btn_id, "title": title} for btn_id, (_code, title) in LANGUAGE_SELECTION.items()]
    return send_whatsapp_list(to, body, rows, bot_id, "Languages")

def send_location_request(to, bot_id, lang="ar", refresh=False):
    """Compatibility wrapper: v81 never asks for GPS; market comes from phone prefix."""
    market = ensure_market_from_phone(to, persist=True)
    country = market.get("country_name") or market.get("country", "").upper()
    return send_whatsapp_text(to, T(lang, "market_from_phone", country=country), bot_id)

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
        if mid:
            with PROCESSED_IDS_LOCK:
                if mid in processed_ids:
                    return {"status":"dup"}
                processed_ids.append(mid)
        bot_id=value.get("metadata",{}).get("phone_number_id",PHONE_NUMBER_ID)
        from_number=msg["from"]
        load_user_preferences(from_number)
        ensure_market_from_phone(from_number, persist=True)
        typ=msg.get("type")

        # Interactive language/search choices always pass through.
        if typ == "interactive":
            background_tasks.add_task(process_interactive_message,msg,bot_id)
            return {"status":"ok"}
        # GPS is no longer required for market detection. If a user sends it manually,
        # acknowledge it without changing the phone-prefix market.
        if typ == "location":
            background_tasks.add_task(process_location_message,msg,bot_id)
            return {"status":"ok"}

        # v105.1: a TEXT message no longer waits for the language selector.
        # Its own language is detected automatically and saved before the search/reply starts.
        if typ == "text":
            background_tasks.add_task(process_text_message, msg, bot_id, True)
            return {"status":"ok"}

        # For a first-ever IMAGE with no text/caption language signal, keep the manual selector.
        if from_number not in USER_LANG:
            cache_pending_message(from_number, msg, bot_id)
            background_tasks.add_task(asyncio.to_thread, send_language_choice, from_number, bot_id)
            return {"status":"ok"}

        if typ=="image":
            IMAGE_BUFFER[from_number]["images"].append(msg); IMAGE_BUFFER[from_number]["time"]=time.time(); IMAGE_BUFFER[from_number]["bot_id"]=bot_id
            if len(IMAGE_BUFFER[from_number]["images"])==1:
                background_tasks.add_task(process_image_buffer,from_number)
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
         f"ورابط صفحة المنتج المباشرة داخل المتجر. رتب من الأرخص إلى الأغلى واكتب السعر بالفلوس كاملة مثل 1.950. {lang_instr(lang)}"),
        (f"{MAX_STORES} best in-stock alternatives similar to {base_en or base} in {market_name} local online stores, "
         f"each with the alternative's own name, a numeric price, and a direct product page link, sorted cheapest first. {lang_instr(lang)}"),
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
            title = product_title(txt, U(lang, "similar_to", base=base))
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
            title = product_title(txt, U(lang, "similar_to", base=base))
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

def _more_result_domain(url):
    try:
        host = urllib.parse.urlparse(str(url or "")).netloc.lower().split(":")[0]
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _send_more_results_choice(phone, bot_id, lang="ar"):
    body = U(lang, "more_store_q")
    title = U(lang, "search_more")
    return send_whatsapp_buttons(phone, body, [{"id":"more_results","title":title}], bot_id)


def _save_more_results_state(phone, query, bot_id, lang, origin, shown_items, image_b64="", image_mime="", visual_identity="", reset=False):
    prev = {} if reset else (PENDING_MORE_RESULTS.get(phone) or {})
    seen_domains = set(prev.get("seen_domains") or [])
    seen_urls = set(prev.get("seen_urls") or [])
    for item in shown_items or []:
        url = str((item or {}).get("link") or "").strip()
        if url:
            seen_urls.add(url)
            dom = _more_result_domain(url)
            if dom:
                seen_domains.add(dom)
    PENDING_MORE_RESULTS[phone] = {
        "query": re.sub(r"\s+", " ", str(query or "")).strip(),
        "bot_id": bot_id, "lang": lang, "origin": origin,
        "image_b64": image_b64 if origin == "lens" else "",
        "image_mime": image_mime if origin == "lens" else "",
        "visual_identity": visual_identity if origin == "lens" else "",
        "seen_domains": sorted(seen_domains), "seen_urls": sorted(seen_urls), "ts": time.time(),
    }


def _more_exclusion_instruction(seen_domains):
    domains = [d for d in sorted(set(seen_domains or [])) if d][:18]
    return (" استبعد هذه المواقع لأنها ظهرت سابقاً: " + ", ".join(domains) + ".") if domains else ""


def legacy_text_product_search_more(product, lang, seen_domains):
    market_name = current_market().get("country_name", "Kuwait")
    total_cap = MORE_TOTAL_MAX
    exclusion = _more_exclusion_instruction(seen_domains)
    alt = english_search_name(product) if re.search(r"[\u0600-\u06FF]", str(product or "")) else arabic_search_name(product)
    alt = (alt or "").strip()
    extra_name = f" والاسم الآخر لنفس المنتج هو {alt}." if alt and alt.lower() != str(product).strip().lower() else ""
    prompt = (
        f"ابحث مرة أخرى بعمق عن نفس المنتج بالضبط: {product}.{extra_name} "
        f"المستخدم شاهد نتائج سابقة ويريد متاجر إضافية جديدة فقط.{exclusion} "
        f"نفس ترتيب البحث الأصلي لكن بحدود الدفعة الإضافية: أولاً متاجر {market_name} المحلية حتى {MORE_LOCAL_MAX}، "
        f"ثم الولايات المتحدة حتى {MORE_US_MAX}، ثم الصين حتى {MORE_CN_MAX}. "
        "لا تعرض دولة رابعة. لا تكرر أي متجر أو دومين ظهر سابقاً. "
        "كل نتيجة يجب أن تكون نفس المنتج والموديل/الحجم، بسعر رقمي ورابط صفحة منتج مباشر. "
        f"{TEXT77_lang_instr(lang)}"
    )
    return legacy_v26_best_of_search([{"text": prompt}], total_cap, True, product)


def run_more_results_search(phone, item):
    activate_market(phone)
    bot_id = item.get("bot_id") or PHONE_NUMBER_ID
    lang = item.get("lang") or USER_LANG.get(phone, "ar")
    query = (item.get("query") or "").strip()
    seen_domains = set(item.get("seen_domains") or [])
    seen_urls = set(item.get("seen_urls") or [])
    if not query:
        return False
    send_whatsapp_text(phone, U(lang, "looking_more"), bot_id)
    if item.get("origin") == "lens" and item.get("image_b64") and item.get("image_mime"):
        exclude_q = " ".join(f"-site:{d}" for d in list(seen_domains)[:5])
        q_hint = re.sub(r"\s+", " ", f"{query} buy shop other retailers {exclude_q}").strip()[:120]
        lens = google_lens_lookup(item["image_b64"], item["image_mime"], lang, q_hint, light=True)
        if lens.get("matches") and send_lens_direct_results(phone, lens, bot_id, lang, caption=query, image_b64=item.get("image_b64") or "", image_mime=item.get("image_mime") or "", exclude_domains=seen_domains, exclude_urls=seen_urls, more_mode=True):
            return True
    else:
        txt, urls = legacy_text_product_search_more(query, lang, seen_domains)
        if txt and urls and send_text_lens_style_results(phone, txt, urls, bot_id, lang, query, exclude_domains=seen_domains, exclude_urls=seen_urls, more_mode=True):
            return True
    PENDING_MORE_RESULTS.pop(phone, None)
    send_whatsapp_text(phone, U(lang, "all_results"), bot_id)
    return False


def process_interactive_message(message, bot_id):
    from_number=message["from"]
    inter=(message.get("interactive") or {})
    reply=inter.get("button_reply") or inter.get("list_reply") or {}
    btn_id=reply.get("id","")

    if btn_id == "more_results":
        item = PENDING_MORE_RESULTS.get(from_number) or {}
        lang_ = item.get("lang") or USER_LANG.get(from_number, "ar")
        if item and time.time() - float(item.get("ts") or 0) <= GLOBAL_PENDING_TTL:
            item["ts"] = time.time()
            PENDING_MORE_RESULTS[from_number] = item
            run_more_results_search(from_number, item)
        else:
            PENDING_MORE_RESULTS.pop(from_number, None)
            send_whatsapp_text(from_number, U(lang_, "expired"), bot_id)
        return

    # Region-expansion UI removed by request. Ignore stale old buttons.
    if btn_id == "region_gcc" or btn_id.startswith("gcc_") or btn_id in ("region_uk", "region_eu"):
        return

    # v77.7 typed basket store selection.
    if btn_id.startswith("cart_"):
        item = PENDING_CART_PICKS.get(from_number)
        if item and time.time() - item.get("ts", 0) > GLOBAL_PENDING_TTL:
            item = None
        lang_ = (item or {}).get("lang", USER_LANG.get(from_number, "ar"))
        idx = int(btn_id[5:]) if btn_id[5:].isdigit() else -1
        if item and 0 <= idx < len(item.get("stores") or []):
            activate_market(from_number)
            send_cart_from_store(from_number, idx, item["stores"], item.get("products") or [], item.get("bot_id") or bot_id, lang_)
        else:
            send_whatsapp_text(from_number, T(lang_, "cart_expired"), bot_id)
        return

    # v84.3: recommendation selection is self-contained and resilient.
    # New list rows carry the product identity inside the row id (pickq_...).
    # This means a restart/worker switch cannot make a fresh choice "expire".
    # Old pick_N rows are also supported and fall back to WhatsApp's reply title.
    if btn_id.startswith("pickq_") or btn_id.startswith("pick_"):
        item = PENDING_BRAND_PICKS.get(from_number) or {}
        lang_ = item.get("lang") or USER_LANG.get(from_number, "ar")
        picked = ""

        if btn_id.startswith("pickq_"):
            token = btn_id[6:]
            try:
                pad = "=" * ((4 - len(token) % 4) % 4)
                picked = base64.urlsafe_b64decode((token + pad).encode("ascii")).decode("utf-8", "ignore")
            except Exception as e:
                print(f"PICK TOKEN DECODE ERR: {e}")
                picked = ""
        else:
            raw_idx = btn_id[5:]
            pick_idx = int(raw_idx) if raw_idx.isdigit() else -1
            options = item.get("options") or []
            if 0 <= pick_idx < len(options):
                picked = options[pick_idx]

        # Critical fallback: list replies contain the visible title. Use it rather than
        # rejecting a user's selection if in-memory state disappeared.
        # v105: عنوان الصف صار نوع التوصية (🏆 الأفضل...) والمنتج في الوصف قبل الشرطة.
        if not picked:
            desc = str(reply.get("description") or "")
            desc_product = re.split(r"\s+(?:—|–|-)\s+", desc, maxsplit=1)[0].strip()
            title = str(reply.get("title") or "")
            title_is_label = bool(re.match(r"^\s*(?:🏆|💎|💰|✨|⭐)", title))
            picked = (desc_product if (title_is_label or not title) else title) or desc_product or title
        picked = _clean_pick_label(picked)
        if not picked:
            send_whatsapp_text(from_number, U(lang_, "expired"), bot_id)
            return

        # State improves normalization while present, but is no longer required.
        if item and time.time() - float(item.get("ts") or 0) <= BRAND_PICK_TTL:
            original = item.get("original_query") or ""
            target_bot_id = item.get("bot_id") or bot_id
        else:
            original = ""
            target_bot_id = bot_id

        activate_market(from_number)
        search_query = ai_recommendation_pick_search_query(original, picked, lang_)
        LAST_SEARCH[from_number] = {"product": search_query}
        PENDING_BRAND_PICKS.pop(from_number, None)
        execute_product_search(from_number, search_query, target_bot_id, lang_)
        return

    # Shared buttons: text77 uses text77 follow-ups; image/Lens keeps v79 handlers exactly.
    if btn_id in ("global_yes", "nf_global"):
        item = _pop_pending_global(from_number)
        if item:
            if item.get("origin") == "text77":
                run_text_global_search(from_number, item)
            else:
                run_global_search(from_number, item)
        return
    if btn_id == "nf_similar":
        item = _pop_pending_global(from_number)
        if item:
            if item.get("origin") == "text77":
                run_text_similar_search(from_number, item)
            else:
                run_similar_search(from_number, item)
        return
    if btn_id in ("global_no", "nf_no"):
        PENDING_GLOBAL_SEARCH.pop(from_number, None)
        send_whatsapp_text(from_number, T(USER_LANG.get(from_number, "ar"), "declined_ok"), bot_id)
        return
    if btn_id not in LANGUAGE_SELECTION:
        return
    lang = LANGUAGE_SELECTION[btn_id][0]
    USER_LANG[from_number] = lang
    market = ensure_market_from_phone(from_number, persist=False)
    save_user_preferences(from_number)
    send_whatsapp_text(from_number, T(lang, "lang_saved"), bot_id)
    print(f"LANGUAGE SAVED: {from_number} -> {lang}; MARKET FROM PHONE -> {market.get('country')}")
    route_pending_after_location(from_number)

async def process_image_buffer(from_number):
    # Debounce until the user stops sending images, but never impose the old fixed 4s delay.
    started = time.monotonic()
    while True:
        data = IMAGE_BUFFER.get(from_number)
        if not data:
            return
        idle = max(0.0, time.time() - float(data.get("time") or 0))
        elapsed = time.monotonic() - started
        if idle >= IMAGE_BUFFER_IDLE_SECONDS or elapsed >= IMAGE_BUFFER_MAX_WAIT_SECONDS:
            break
        await asyncio.sleep(min(0.25, max(0.05, IMAGE_BUFFER_IDLE_SECONDS - idle)))
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
    """True only for a usable numeric selling price, not merely any non-empty text/model number."""
    if not isinstance(m, dict):
        return False
    try:
        if m.get("price_value") not in (None, "") and float(m.get("price_value")) > 0:
            return True
    except Exception:
        pass
    raw = str(m.get("price") or "").strip()
    if not raw:
        return False
    numeric = _extract_numeric_price(raw)
    if numeric is not None and numeric > 0:
        return True
    # SerpApi sometimes returns a bare short numeric string while extracted_price is absent.
    if len(raw) <= 24 and re.fullmatch(r"\s*[$€£¥￥]?\s*\d+(?:[.,]\d{1,3})?\s*(?:[A-Z]{3}|د\.ك|KD|RMB)?\s*", raw, flags=re.I):
        try:
            return float(re.search(r"\d+(?:[.,]\d{1,3})?", raw.replace(",", "")).group(0)) > 0
        except Exception:
            return False
    return False

def _safe_embedded_price(item):
    """Extract only a currency-tagged price already present in Lens text; no network call.

    We intentionally refuse bare numbers so model names such as iPhone 16 / WH-1000XM5
    are never mistaken for a price.
    """
    if not isinstance(item, dict) or _lens_has_price(item):
        return item
    text = " ".join(str(item.get(k) or "") for k in ("price", "title", "snippet", "extensions"))
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return item
    currency_pat = r"(?:KWD|KD|د\.ك|دينار|USD|US\$|\$|SAR|ر\.س|AED|د\.إ|QAR|OMR|BHD|CNY|RMB|¥|￥|EUR|€|GBP|£)"
    pats = (
        rf"({currency_pat})\s*([0-9]+(?:[.,][0-9]{{1,3}})?)",
        rf"([0-9]+(?:[.,][0-9]{{1,3}})?)\s*({currency_pat})",
    )
    cur = ""
    num = None
    raw = ""
    for idx, pat in enumerate(pats):
        m = re.search(pat, text, flags=re.I)
        if not m:
            continue
        if idx == 0:
            cur_token, num_token = m.group(1), m.group(2)
        else:
            num_token, cur_token = m.group(1), m.group(2)
        try:
            num = float(num_token.replace(",", ""))
        except Exception:
            num = None
        if num and num > 0:
            raw = m.group(0)
            cur = detect_currency_code(cur_token, "")
            break
    if not num:
        return item
    out = dict(item)
    rank = result_market_rank(out)
    if not cur:
        cur = (current_market().get("currency") or "KWD").upper() if rank == 0 else ("USD" if rank == 1 else "CNY")
    out["price_value"] = num
    out["currency"] = cur
    out["price"] = raw or f"{format_price(num, cur)} {cur}"
    out["price_source"] = "embedded_lens_text"
    return out


def _price_identity_score(a, b):
    """Conservative score for borrowing a price from another already-returned Lens card."""
    ta, tb = _identity_tokens(a or ""), _identity_tokens(b or "")
    if not ta or not tb:
        return 0.0
    model_a = {x for x in ta if any(c.isdigit() for c in x)}
    model_b = {x for x in tb if any(c.isdigit() for c in x)}
    if model_a and model_b and not (model_a & model_b):
        return 0.0
    inter = len(ta & tb)
    score = inter / max(1, min(len(ta), len(tb)))
    if model_a & model_b:
        score += 0.50
    return score


def _fill_prices_from_existing_lens_pool(selected, pool):
    """Fill missing prices from cards already fetched in this Lens request.

    No merchant-page fetch and no extra SerpApi/Gemini lookup. Price is copied only when
    merchant, model/title identity and pack size are compatible. Every selected card is preserved.
    """
    out = [dict(x) for x in (selected or [])]
    pool = [_safe_embedded_price(dict(x)) for x in (pool or [])]
    for i, item in enumerate(out):
        item = _safe_embedded_price(item)
        if _lens_has_price(item):
            out[i] = item
            continue
        merchant = _lens_merchant_key(item.get("source"), item.get("link"))
        title = str(item.get("title") or "")
        sig = extract_pack_size(title)
        best = None
        best_score = 0.0
        for cand in pool:
            if not _lens_has_price(cand):
                continue
            if _lens_merchant_key(cand.get("source"), cand.get("link")) != merchant:
                continue
            if not sizes_compatible(sig, extract_pack_size(cand.get("title") or "")):
                continue
            score = _price_identity_score(title, cand.get("title") or "")
            if score >= 0.72 and score > best_score:
                best, best_score = cand, score
        if best:
            for k in ("price", "price_value", "currency"):
                if best.get(k) not in (None, ""):
                    item[k] = best.get(k)
            item["price_source"] = "existing_lens_pool"
            print(f"LENS PRICE REUSE: {(item.get('source') or '')[:35]} score={best_score:.2f} -> {item.get('price') or item.get('price_value')}")
        out[i] = item
    return out


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
    target = language_name_en(lang)
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
Keep only the product identity and the few attributes needed to distinguish it (brand/model/type/color/size).
Remove shopping/SEO filler such as buy, shop, online, available in, for men/women, city/country/store wording unless essential to identify the product.
Aim for 3-8 words and at most 65 characters.
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

def _lens_ai_relevance_filter(lens):
    """Infer the product identity from the Lens result set and keep only direct matches.

    This is intentionally independent from store/country/price priority: relevance wins first.
    It catches cases like a coffee maker appearing among restaurant-pager results.
    """
    matches = list((lens or {}).get("matches") or [])
    if not ENABLE_RELEVANCE_FILTER or len(matches) < 3:
        return matches
    sample = matches[:30]
    rows = []
    for i, m in enumerate(sample, 1):
        rows.append(f"{i}. {(m.get('title') or '')[:180]} | store={(m.get('source') or '')[:50]} | exact={bool(m.get('exact'))}")
    system = """You are a strict visual-shopping result validator.
Infer the ONE physical product type/model that the Lens result set is actually about, using consensus across titles and exact/visual signals.
Then keep only results that sell that same product or a clearly compatible variant of the same product type and use.
Reject unrelated products even if they come from a preferred store/country or have a price.
Example: for a restaurant coaster pager/calling system, reject coffee makers, vitamins, lights, unrelated electronics, manuals, accessories, and replacement parts unless the target itself is that accessory.
Do not use price or merchant priority as relevance evidence.
Return JSON only: {"target":"short identity","keep":[1,2,4]}"""
    visual_identity = str((lens or {}).get("visual_identity") or "").strip()
    prompt = (f"Visual AI identity from the original image: {visual_identity or 'UNKNOWN'}\n"
              "Use this as the strongest anchor when it is specific and consistent with the Lens set.\n\n"
              "Lens candidates:\n" + "\n".join(rows))
    try:
        raw, _ = call_gemini([{"text": prompt}], system=system, use_search=False)
        data = json.loads(re.search(r"\{.*\}", raw or "", flags=re.S).group(0))
        keep = {int(x) for x in (data.get("keep") or []) if str(x).isdigit()}
        filtered = [m for i, m in enumerate(sample, 1) if i in keep]
        # Safety: require at least one kept item; unlike old fallback, do NOT restore unrelated rows.
        if filtered:
            target = str(data.get("target") or "").strip()
            if target:
                lens["relevance_target"] = target
            dropped = len(sample) - len(filtered)
            if dropped:
                print(f"LENS AI RELEVANCE: target={target!r} kept={len(filtered)}/{len(sample)} dropped={dropped}")
            return filtered
    except Exception as e:
        print(f"LENS AI RELEVANCE FAIL: {e}")
    return matches


def _lens_merchant_key(name, url=""):
    """Canonical merchant key used to match Lens cards with typed-text search offers."""
    try:
        host = urllib.parse.urlparse(str(url or "")).netloc.lower().split(":")[0]
        host = host[4:] if host.startswith("www.") else host
    except Exception:
        host = ""
    aliases = (
        "amazon.com", "ebay.com", "walmart.com", "aliexpress.com", "temu.com",
        "alibaba.com", "shein.com", "1688.com", "taobao.com", "tmall.com",
        "made-in-china.com", "newegg.com", "bestbuy.com",
    )
    hay = f"{name or ''} {host}".lower()
    for dom in aliases:
        label = dom.split(".")[0]
        if dom in hay or normalize_name(label) in normalize_name(hay):
            return dom
    return host or normalize_name(str(name or ""))


def send_lens_direct_results(from_number, lens, bot_id, lang, caption="", image_b64="", image_mime="", exclude_domains=None, exclude_urls=None, more_mode=False):
    """v76: CTA-only، مختصر، بأعلام الدول، وترجمة للواجهة فقط.

    الحدود القصوى مستقلة: محلي 5، أمريكا 4، الصين 4.
    لا يوجد حد أدنى أو عدد إلزامي لأي سوق.
    """
    exclude_domains = {str(x).lower() for x in (exclude_domains or []) if x}
    exclude_urls = {str(x).strip() for x in (exclude_urls or []) if x}
    raw_matches = [m for m in (lens.get("matches") or []) if (m.get("title") or "").strip()]
    if exclude_domains or exclude_urls:
        raw_matches = [m for m in raw_matches if str(m.get("link") or "").strip() not in exclude_urls and _more_result_domain(m.get("link")) not in exclude_domains]
    # Relevance BEFORE country/store priority: unrelated preferred-store results must never win.
    lens_for_filter = dict(lens or {})
    lens_for_filter["matches"] = raw_matches
    raw_matches = _lens_ai_relevance_filter(lens_for_filter)
    if lens_for_filter.get("relevance_target"):
        lens["relevance_target"] = lens_for_filter["relevance_target"]
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
            _us_store_priority(m.get("source"), m.get("link")) if rank == 1
            else (_china_store_priority(m.get("source"), m.get("link")) if rank == 2 else 99),
            0 if _lens_has_price(m) else 1,
            0 if m.get("exact") else 1,
            0 if m.get("section") == "visual_matches" else 1,
            int(m.get("position") or 999),
        ))
        # فحص مخزون لأفضل المرشحين فقط حتى لا نبطئ Lens بعشرات طلبات HTTP.
        # نأخذ cap+2 لإعطاء بديلين إذا كانت بعض البطاقات خالصة.
        _active_probe_caps = (
            {0: MORE_LOCAL_MAX, 1: MORE_US_MAX, 2: MORE_CN_MAX}
            if more_mode
            else {0: LENS_DIRECT_LOCAL_MAX, 1: LENS_DIRECT_US_MAX, 2: LENS_DIRECT_CN_MAX}
        )
        _cap = _active_probe_caps.get(rank, 0)
        _probe_n = max(_cap + 2, _cap)
        _head = _filter_confirmed_oos(buckets[rank][:_probe_n], f"LENS-{rank}")
        buckets[rank] = _head + buckets[rank][_probe_n:]

    # حدود قصوى فقط وليست حصصاً. نسمح حتى نتيجتين من نفس المتجر/merchant.
    # نمنع تكرار نفس الرابط نفسه، لكن قد يظهر SKU/عرض ثانٍ من Amazon أو eBay أو غيرهما.
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

    market_caps = (
        {0: MORE_LOCAL_MAX, 1: MORE_US_MAX, 2: MORE_CN_MAX}
        if more_mode
        else {0: LENS_DIRECT_LOCAL_MAX, 1: LENS_DIRECT_US_MAX, 2: LENS_DIRECT_CN_MAX}
    )
    selected = []
    seen_urls = set()
    merchant_counts = defaultdict(int)
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
            if url in seen_urls:
                print(f"LENS DUP URL SKIP: merchant={merchant} title={(m.get('title') or '')[:70]}")
                continue
            if merchant_counts[merchant] >= RESULTS_PER_STORE_MAX:
                print(f"LENS STORE CAP SKIP: merchant={merchant} cap={RESULTS_PER_STORE_MAX}")
                continue
            selected.append(m)
            seen_urls.add(url)
            merchant_counts[merchant] += 1
            taken += 1
            if taken >= cap or len(selected) >= LENS_DIRECT_MAX_CTA:
                break
        if len(selected) >= LENS_DIRECT_MAX_CTA:
            break

    if not selected:
        return False

    # v80.1 PRICE-SMART: لا نزور صفحات المتاجر ولا نحذف أي بطاقة.
    # نستعيد السعر مجاناً من بيانات Lens الموجودة: النص المضمّن أو نسخة أخرى من نفس
    # المتجر/الموديل في تمريرات Lens المتعددة. إذا بقي السعر مجهولاً تبقى البطاقة.
    selected = _fill_prices_from_existing_lens_pool(selected, raw_matches)
    missing_prices = sum(1 for m in selected if not _lens_has_price(m))
    if missing_prices:
        print(f"LENS PRICE-SMART: preserved {missing_prices} card(s) with no safely extracted numeric price")

    # الترجمة للواجهة فقط بعد اكتمال البحث والاختيار؛ لا تؤثر على Lens أو Google أو الفلاتر.
    display_titles = translate_ui_titles([(m.get("title") or "").strip() for m in selected], lang)
    for m, display_title in zip(selected, display_titles):
        m["_display_title"] = display_title

    local_cc = (current_market().get("country") or DEFAULT_COUNTRY).lower()
    market_cc = {0: local_cc, 1: "us", 2: "cn"}
    sent = 0
    market_counts = {0: 0, 1: 0, 2: 0}
    for m in selected:
        market_rank = result_market_rank(m)
        flag = country_flag_emoji(market_cc.get(market_rank, ""))
        source = _ui_plain_store_name((m.get("source") or "").strip(), (m.get("link") or "").strip())
        title = _compact_ui_title(m.get("_display_title") or m.get("title") or "")
        price_txt = _lens_price_text_local(m, market_rank, lang)

        # بطاقة مرتبة: متجر -> منتج -> سعر، بدون خلط عربي/إنجليزي في نفس السطر.
        body = _build_compact_card_body(flag, source, title, price_txt, lang)
        if not body:
            continue

        url = (m.get("link") or "").strip()
        button_source = source or (U(lang, "store"))
        send_whatsapp_cta(from_number, body[:1000], url, bot_id, button_source)
        market_counts[market_rank] += 1
        sent += 1

    chosen_title = ((lens.get("chosen") or {}).get("title") or selected[0]["title"]).strip()
    expansion_query = (
        (lens.get("relevance_target") or "").strip()
        or chosen_title
        or (caption or "").strip()
    )
    LAST_SEARCH[from_number] = {"product": (caption or expansion_query or chosen_title)}
    print(f"LENS DIRECT SENT v79: {sent} CTA; merchants={len(merchant_counts)}; per_store_cap={RESULTS_PER_STORE_MAX}; buckets={market_counts}; caps=5/4/4; order=local->us->cn")
    if market_counts[2] == 0:
        print("V77 WARNING: no Chinese-store Lens result survived filters")
    if sent > 0 and expansion_query:
        _save_more_results_state(from_number, expansion_query, bot_id, lang, "lens", selected, image_b64=image_b64, image_mime=image_mime, visual_identity=(lens.get("visual_identity") or lens.get("relevance_target") or expansion_query), reset=not more_mode)
        _send_more_results_choice(from_number, bot_id, lang)
    return sent > 0

def process_single_image(message,bot_id,lang="ar"):
    from_number=message["from"]
    market = activate_market(from_number)
    caption=(message.get("image",{}) or {}).get("caption","").strip()
    # Start media download immediately; status message is sent in parallel.
    WORKERS.submit(send_whatsapp_text, from_number, T(lang,"identifying"), bot_id)
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
            if send_lens_direct_results(
                from_number, lens_direct, bot_id, lang, caption,
                image_b64=b64, image_mime=mime
            ):
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
                lens = lens_future.result(timeout=LENS_TOTAL_TIMEOUT_SECONDS + 5) or lens
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
            f"{lang_instr(lang)}"
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
    except Exception: return ""

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



# =============================================================================
# v79 TEXT SEARCH ENGINE = v77.7 (ISOLATED FROM IMAGE/LENS)
# IMPORTANT: This section is used only by typed-text flows. v79 Lens/search_product
# and all image functions remain untouched.
# =============================================================================

PENDING_BRAND_PICKS = {}
PENDING_CART_PICKS = {}
SEARCH_RUNS = max(1, min(3, int(os.environ.get("SEARCH_RUNS", "2"))))
TOURNAMENT_GRACE_SECONDS = max(0.25, float(os.environ.get("TOURNAMENT_GRACE_SECONDS", "1.2")))
LENS_FAST_READY_SECONDS = max(3.0, min(5.0, float(os.environ.get("LENS_FAST_READY_SECONDS", "5.0"))))

V26_SEARCH_POOL = ThreadPoolExecutor(max_workers=8)
SIMILAR_MAX_STORES = max(MAX_STORES, int(os.environ.get("SIMILAR_MAX_STORES", "10")))

# Missing v77.7 text UI keys are added without replacing any existing v79/Lens messages.
MSG["ar"].update({
    "ask_global_after_local": "لقيت لك النتائج المحلية فوق 👆\nتبي أدور لك نفس المنتج في المتاجر العالمية أيضاً؟ 🌍",
    "compare_searching": "⚖️ طلبك عام بدون ماركة محددة.. أسوي لك مقارنة بين أفضل البراندات المتوفرة!",
    "pick_prompt": "اختر منتجاً من القائمة وأدور لك أفضل الأسعار المتوفرة 👇",
    "list_button": "اختر منتج",
    "cart_comparing": "🧺 لقيت {c} أصناف.. أقارن لك السلة كاملة في المتاجر وأشوف وين تطلع أوفر وأسهل!",
    "cart_pick_prompt": "اختر متجراً وأرسل لك كل أصنافك بروابطها المباشرة داخله — طلبية وحدة وسلة وحدة 👇",
    "cart_store_button": "اختر متجر",
    "cart_total": "💰 مجموع السلة: {t}",
    "cart_expired": "قائمة السلة قدمت 😅 دز قائمة الأصناف من جديد وأجهزها لك على طول.",
    "cart_session_tip": "💡 المهم: أضف الصنف الأول من الزر، وبعدها دوّر باقي الأصناف من بحث المتجر بنفس الصفحة — لا ترجع لواتساب بين كل صنف عشان تتراكم كلها في سلة وحدة.",
    "cart_plan_total": "💰 مجموع الخطة كاملة: {t}",
    "cart_not_anywhere": "⛔ ما لقيتها في أي متجر بالقائمة: {items}",
    "chat_redirect": "أنا حاضر ومعك! 🙌\nدز اسم المنتج أو صورته وأدور لك أفضل الأسعار، أو اكتب طلب الخدمة اللي تحتاجها 🛒",
})
MSG["en"].update({
    "ask_global_after_local": "Found local results above 👆 Want me to also search international stores for the same product? 🌍",
    "compare_searching": "⚖️ Your request is generic, so I’m comparing the best brands/options first!",
    "pick_prompt": "Pick a product and I’ll search the best available prices 👇",
    "list_button": "Pick product",
    "cart_comparing": "🧺 Found {c} items.. comparing your full basket across stores to find the easiest best-value option!",
    "cart_pick_prompt": "Pick a store and I’ll send all your items with direct links inside it — one order, one cart 👇",
    "cart_store_button": "Pick store",
    "cart_total": "💰 Basket total: {t}",
    "cart_expired": "That basket list expired 😅 send your items again and I’ll rebuild it.",
    "cart_session_tip": "💡 Add the first item from the button, then find the rest using the store search in the same page so they stay in one cart.",
    "cart_plan_total": "💰 Full plan total: {t}",
    "cart_not_anywhere": "⛔ Not found in any listed store: {items}",
    "chat_redirect": "I’m here 🙌 Send a product name/photo for prices, or type the service you need 🛒",
})

# Complete localization for the post-local-results international-search prompt.
MSG["fr"]["ask_global_after_local"] = "J’ai trouvé les résultats locaux ci-dessus 👆 Voulez-vous que je cherche aussi le même produit dans les boutiques internationales ? 🌍"
MSG["es"]["ask_global_after_local"] = "Encontré los resultados locales arriba 👆 ¿Quieres que busque también el mismo producto en tiendas internacionales? 🌍"
MSG["pt"]["ask_global_after_local"] = "Encontrei os resultados locais acima 👆 Quer que eu procure o mesmo produto também em lojas internacionais? 🌍"
MSG["tr"]["ask_global_after_local"] = "Yerel sonuçları yukarıda buldum 👆 Aynı ürünü uluslararası mağazalarda da aramamı ister misiniz? 🌍"
MSG["ru"]["ask_global_after_local"] = "Локальные результаты уже выше 👆 Искать этот же товар также в международных магазинах? 🌍"
MSG["zh"]["ask_global_after_local"] = "上面已经找到本地结果 👆 要不要继续在国际商店中搜索同一商品？🌍"

MSG["hi"].update({
    "ask_global_after_local": "स्थानीय नतीजे ऊपर हैं 👆 क्या इसी प्रोडक्ट के लिए अंतरराष्ट्रीय स्टोर भी खोजूँ? 🌍",
    "compare_searching": "⚖️ आपका अनुरोध सामान्य है, इसलिए पहले सबसे अच्छे ब्रांड/विकल्पों की तुलना कर रहा हूँ!",
    "pick_prompt": "कोई प्रोडक्ट चुनें, फिर मैं उसकी सबसे अच्छी उपलब्ध कीमतें खोजूँगा 👇",
    "list_button": "प्रोडक्ट चुनें",
    "cart_comparing": "🧺 {c} आइटम मिले.. पूरी कार्ट की अलग-अलग स्टोर में तुलना कर रहा हूँ!",
    "cart_pick_prompt": "स्टोर चुनें और मैं सभी आइटम के सीधे लिंक एक ही जगह भेज दूँगा 👇",
    "cart_store_button": "स्टोर चुनें",
    "cart_total": "💰 कार्ट कुल: {t}",
    "cart_expired": "यह कार्ट सूची समाप्त हो गई 😅 आइटम दोबारा भेजें।",
    "cart_session_tip": "💡 पहले आइटम को बटन से जोड़ें, फिर उसी स्टोर में बाकी आइटम खोजें ताकि एक ही कार्ट रहे।",
    "cart_plan_total": "💰 पूरी योजना का कुल: {t}",
    "cart_not_anywhere": "⛔ किसी सूचीबद्ध स्टोर में नहीं मिला: {items}",
    "chat_redirect": "मैं यहाँ हूँ 🙌 कीमत के लिए प्रोडक्ट का नाम/फोटो भेजें या अपनी ज़रूरत की सेवा लिखें 🛒",
})
MSG["ur"].update({
    "ask_global_after_local": "مقامی نتائج اوپر ہیں 👆 کیا اسی پروڈکٹ کے لیے بین الاقوامی اسٹورز بھی تلاش کروں؟ 🌍",
    "compare_searching": "⚖️ آپ کی درخواست عمومی ہے، اس لیے پہلے بہترین برانڈز/آپشنز کا موازنہ کر رہا ہوں!",
    "pick_prompt": "ایک پروڈکٹ منتخب کریں، پھر میں اس کی بہترین دستیاب قیمتیں تلاش کروں گا 👇",
    "list_button": "پروڈکٹ منتخب کریں",
    "cart_comparing": "🧺 {c} آئٹمز مل گئے.. پوری کارٹ کا مختلف اسٹورز میں موازنہ کر رہا ہوں!",
    "cart_pick_prompt": "اسٹور منتخب کریں اور میں تمام آئٹمز کے براہِ راست لنکس ایک جگہ بھیج دوں گا 👇",
    "cart_store_button": "اسٹور منتخب کریں",
    "cart_total": "💰 کارٹ کا کل: {t}",
    "cart_expired": "یہ کارٹ فہرست ختم ہو گئی 😅 آئٹمز دوبارہ بھیجیں۔",
    "cart_session_tip": "💡 پہلا آئٹم بٹن سے شامل کریں، پھر اسی اسٹور میں باقی آئٹمز تلاش کریں تاکہ ایک ہی کارٹ رہے۔",
    "cart_plan_total": "💰 مکمل منصوبے کا کل: {t}",
    "cart_not_anywhere": "⛔ کسی درج شدہ اسٹور میں نہیں ملا: {items}",
    "chat_redirect": "میں حاضر ہوں 🙌 قیمت کے لیے پروڈکٹ کا نام/تصویر بھیجیں یا مطلوبہ سروس لکھیں 🛒",
})

COUNTRY_NAMES_AR = {
    "kw": "الكويت", "sa": "السعودية", "ae": "الإمارات", "bh": "البحرين", "qa": "قطر",
    "om": "عمان", "iq": "العراق", "jo": "الأردن", "lb": "لبنان", "eg": "مصر",
    "sy": "سوريا", "ye": "اليمن", "ps": "فلسطين", "ma": "المغرب", "dz": "الجزائر",
    "tn": "تونس", "ly": "ليبيا", "sd": "السودان",
}

TEXT77_LANG_INSTR = {
    "ar": "رد باللغة العربية فقط في نصوص الواجهة، لكن لا تحوّل أسعار المتاجر الأجنبية. أبقِ السعر والعملة الأصلية كما ظهرا في المصدر: متاجر أمريكا USD، والمتاجر الصينية USD أو CNY/RMB حسب المصدر. الأسعار المحلية فقط بعملة بلد المستخدم. يجب أن يحتوي كل سطر متجر على السعر الرقمي والعملة الأصلية صراحةً.",
    "en": "Respond in English for UI text, but NEVER convert foreign-store prices. Preserve the exact source currency: US stores in USD; China stores in USD or CNY/RMB as shown by the source. Only local-store prices use the user's local currency. Every store line must explicitly include numeric price plus original currency.",
    "fr": "Répondez en français pour l’interface, mais ne convertissez JAMAIS les prix des boutiques étrangères. Conservez la devise exacte de la source : USD pour les boutiques américaines ; USD ou CNY/RMB pour les boutiques chinoises. Seuls les prix locaux utilisent la devise locale de l’utilisateur.",
    "es": "Responde en español para la interfaz, pero NUNCA conviertas los precios de tiendas extranjeras. Conserva la moneda exacta de la fuente: USD para tiendas de EE. UU.; USD o CNY/RMB para tiendas chinas. Solo los precios locales usan la moneda local del usuario.",
    "pt": "Responda em português para a interface, mas NUNCA converta preços de lojas estrangeiras. Preserve a moeda exata da fonte: USD para lojas dos EUA; USD ou CNY/RMB para lojas chinesas. Apenas os preços locais usam a moeda local do usuário.",
    "tr": "Arayüz metinlerinde Türkçe yanıt ver, ancak yabancı mağaza fiyatlarını ASLA dönüştürme. Kaynaktaki para birimini aynen koru: ABD mağazaları USD; Çin mağazaları kaynakta göründüğü gibi USD veya CNY/RMB. Yalnızca yerel mağaza fiyatları kullanıcının yerel para biriminde olsun.",
    "ru": "Для интерфейса отвечайте по-русски, но НИКОГДА не конвертируйте цены зарубежных магазинов. Сохраняйте валюту источника: магазины США — USD; китайские магазины — USD или CNY/RMB, как указано в источнике. Только локальные цены используют местную валюту пользователя.",
    "zh": "界面文字使用简体中文，但绝不要转换海外商店的价格。保留来源中的原始货币：美国商店使用 USD；中国商店按来源保留 USD 或 CNY/RMB。只有本地商店价格使用用户所在国家/地区的本地货币。",
    "hi": "UI टेक्स्ट हिंदी में दें, लेकिन विदेशी स्टोर की कीमतों को कभी कन्वर्ट न करें। स्रोत की मूल मुद्रा रखें: US स्टोर USD में; चीन के स्टोर स्रोत के अनुसार USD या CNY/RMB में। केवल स्थानीय स्टोर की कीमत उपयोगकर्ता की स्थानीय मुद्रा में हो।",
    "ur": "UI متن اردو میں دیں، مگر غیر ملکی اسٹور کی قیمت کبھی تبدیل نہ کریں۔ اصل ماخذ کی کرنسی برقرار رکھیں: امریکی اسٹور USD میں؛ چینی اسٹور ماخذ کے مطابق USD یا CNY/RMB میں۔ صرف مقامی اسٹور کی قیمت صارف کی مقامی کرنسی میں ہو۔",
}

def text77_lang_instr(lang):
    code = str(lang or "en").strip().lower().replace("_", "-").split("-")[0]
    if code in TEXT77_LANG_INSTR:
        return TEXT77_LANG_INSTR[code]
    name = language_name_en(code)
    return (
        f"Respond in {name} for all user-facing UI and descriptive text, but NEVER convert foreign-store prices. "
        "Preserve the exact source currency: US stores in USD; China stores in USD or CNY/RMB exactly as shown by the source. "
        "Only local-store prices use the user's local currency. Every store line must explicitly include a numeric price and currency. "
        "Keep brand names, model names, SKUs, sizes, URLs and currency codes unchanged."
    )


TEXT77_SYSTEM_PROMPT = SYSTEM_PROMPT + """

IMPORTANT OVERRIDE FOR TYPED-TEXT SEARCH ONLY:
Ignore any earlier instruction that forces all prices into KWD or the user's local currency.
For LOCAL stores, return the source price in the user's local currency.
For UNITED STATES stores, return the source price in USD, never converted.
For CHINA stores, return the source price exactly as listed by the store, normally USD or CNY/RMB, never converted.
The application will perform FX conversion after retrieval. Therefore preserving the original numeric price and original currency is mandatory.
Do not output a converted local-currency value for a foreign store.
"""

def text77_market_instruction():
    """Typed-text global market rule with premium local discovery."""
    m = current_market()
    cc = (m.get("country") or DEFAULT_COUNTRY).lower()
    place = m.get("country_name") or COUNTRY_NAMES.get(cc, cc.upper())
    currency = m.get("currency") or "local currency"
    currencies = ", ".join(country_currency_codes(cc)) or currency
    hl = m.get("search_hl") or country_search_hl(cc)
    tlds = ", ".join(country_tlds(cc))
    local_stores = priority_stores_for("")
    stores_hint = ", ".join(local_stores[:6]) if local_stores else "strong local specialist stores and marketplaces"
    return (
        f"\nIMPORTANT TYPED-TEXT GEO RULE: local market is {place} (gl={cc}, hl={hl}, ccTLD={tlds}). "
        f"Accepted local currencies: {currencies}; primary display currency: {currency}. "
        "LOCAL IS THE MAIN PRODUCT: search it deeply before foreign markets. Use the user's wording, commercial English name, and local-commerce wording when useful. "
        f"Check {stores_hint}, then broaden to smaller genuine local merchants indexed by Google; this is not a whitelist. "
        f"Return in strict order: up to {LENS_DIRECT_LOCAL_MAX} LOCAL {place} results, then up to {LENS_DIRECT_US_MAX} US, then up to {LENS_DIRECT_CN_MAX} China. Reject every fourth country. "
        "Heureka/heureka.cz/heureka.sk is blocked globally as a comparison site; Eureka Kuwait is allowed. "
        f"Local prices use a valid local source currency ({currencies}); US stays USD; China stays source USD or CNY/RMB. Never convert foreign prices in the AI response. "
        "A .com domain can still be local when Google local targeting, local currency, country path/text, or merchant identity ties it to the local market. "
        "For SERVICES keep providers local only.\n"
    )


def text77_store_domain(name):
    """Use the same market-aware domain resolver as the global engine."""
    return store_domain(name)

def text77_extract_store_offers(txt, limit=None):
    offers = []
    for line in (txt or "").splitlines():
        s = line.strip()
        m = re.match(r"^(✅|🏆|•)\s*(.+?)\s*(?:—|–|-)\s*(.+)$", s)
        if not m or not re.search(r"\d", m.group(3)):
            continue
        if re.search(r"\(\s*(?:هاتف|Phone|phone|Tel|tel)\s*:", s):
            continue
        name = _clean_store_name(m.group(2)) if '_clean_store_name' in globals() else m.group(2).strip()
        if is_blocked_store(name, ""):
            print(f"TEXT77 BLOCKED STORE LINE SKIP: {name}")
            continue
        s = f"{m.group(1)} {name} — {m.group(3).strip()}"
        if is_junk_store(name):
            continue
        best = m.group(1) in ("✅", "🏆")
        body = s if best else s.lstrip("•").strip()
        offers.append({"line": body, "name": name, "best": best})
    cap = MAX_STORES if limit is None else max(1, int(limit))
    return offers[:cap]

def text77_call_gemini(parts, system=TEXT77_SYSTEM_PROMPT, use_search=True):
    """v77.7 call_gemini semantics, but isolated to typed text flows."""
    model = GEMINI_SEARCH_MODEL if use_search else GEMINI_FAST_MODEL
    gemini_url = f"{GEMINI_BASE_URL}/{model}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": system + (text77_market_instruction() if use_search else "")}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 1000 if use_search else 300},
    }
    if use_search:
        payload["tools"] = [{"google_search": {}}]
    with GEMINI_STATS_LOCK:
        key = "search_calls" if use_search else "plain_calls"
        GEMINI_STATS[key] += 1
        print(f"TEXT77 GEMINI CALL model={model} search={use_search} totals={GEMINI_STATS}")
    try:
        r = requests.post(gemini_url, params={"key": GEMINI_API_KEY}, json=payload, timeout=(5, GEMINI_SEARCH_TIMEOUT_SECONDS if use_search else GEMINI_PLAIN_TIMEOUT_SECONDS))
        if r.status_code >= 400:
            print(f"TEXT77 Gemini HTTP {r.status_code}: {r.text[:500]}")
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
            for part in re.split(r"[,،]+", m.group(1)):
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
        urls_map, used_urls = {}, set()
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
                                urls_map[store] = url; used_urls.add(url); break
                if store in urls_map:
                    break
        for name, dom in pairs:
            if name in urls_map:
                continue
            key = domain_key(dom)
            for rec in records:
                haystack = f"{rec['title']} {rec['raw']} {rec['url']}".lower()
                if rec["url"] and key and key in haystack and rec["url"] not in used_urls:
                    urls_map[name] = rec["url"]; used_urls.add(rec["url"]); break
        for store in stores:
            if store in urls_map:
                continue
            dom = text77_store_domain(store)
            if not dom:
                continue
            key = domain_key(dom)
            for rec in records:
                haystack = f"{rec['title']} {rec['raw']} {rec['url']}".lower()
                if rec["url"] and key and key in haystack and rec["url"] not in used_urls:
                    urls_map[store] = rec["url"]; used_urls.add(rec["url"]); break
        if len(urls_map) < MAX_STORES:
            for rec in records:
                url = rec["url"]
                if not url or url in used_urls:
                    continue
                label = source_label(rec["title"], url)
                if label not in urls_map:
                    urls_map[label] = url; used_urls.add(url)
                if len(urls_map) >= MAX_STORES:
                    break
        return text, dict(list(urls_map.items())[:MAX_STORES])
    except Exception as e:
        print(f"TEXT77 Gemini err {e}")
        return "", {}

def text77_bilingual_search_instruction(query, lang):
    m = current_market()
    market_name = m.get("country_name", "Kuwait")
    hl = m.get("search_hl") or country_search_hl()
    return (
        f"Search this exact product deeply in the LOCAL market {market_name}: {query}. "
        f"Use the original wording, English commercial name, and local commerce language {hl}. "
        f"Do not stop at famous stores; inspect smaller genuine {market_name} merchants indexed by Google. "
        f"Local prices must be numeric and use an accepted local currency ({', '.join(country_currency_codes())}). "
        f"Then US and China only if needed. {TEXT77_lang_instr(lang)}"
    )


def text77_is_local_result(item):
    return is_local_lens_result(item)


def text77_is_foreign_result(item):
    return is_foreign_lens_result(item)

def text77_store_pending_global(phone, bot_id, lang, query):
    _store_pending_global(phone, bot_id, lang, query, None, None)
    if phone in PENDING_GLOBAL_SEARCH:
        PENDING_GLOBAL_SEARCH[phone]["origin"] = "text77"

# v77.7 classifier references this intent; the original file omitted the constant.
# Defining it here realizes the behavior documented by the v77.7 classifier comments.
BRAND_DETECTION_SYSTEM = """Decide whether the user's product request explicitly contains a specific brand or model name.
Return exactly YES or NO. Do not explain. A category without a brand/model is NO."""

ENABLE_RELEVANCE_FILTER = env_bool("ENABLE_RELEVANCE_FILTER", True)
_NON_PRODUCT_WORDS = (
    "owners manual", "owner's manual", "service manual", "workshop manual", "repair manual", "manual pdf", "handbook",
    "wiring diagram", "parts catalog", "parts catalogue", "spare part", "spare parts", "دليل المالك", "دليل الاستخدام",
    "كتيب", "دليل الصيانه", "دليل الصيانة", "قطع غيار", "مخطط", "متوافق مع", "compatible with", "replacement for",
    "مروحه", "مروحة", "propeller", "impeller", "ستارتر", "starter motor", "كاربريتر", "carburetor", "carburettor",
    "بواجي", "spark plug", "gasket", "فلتر زيت", "oil filter", "فلتر هواء", "air filter", "sensor for", "sticker", "decal",
)
RELEVANCE_FILTER_SYSTEM = """أنت مدقق نتائج لبوت تسوق. أعد فقط أرقام النتائج التي تبيع المنتج المطلوب نفسه كاملاً.
ارفض الكتيبات وPDF وقطع الغيار والإكسسوارات والخدمات والتأجير إلا إذا كان طلب المستخدم نفسه عنها.
أرجع JSON فقط: {\"keep\":[1,3]}"""
SIMILAR_RELEVANCE_FILTER_SYSTEM = """أنت مدقق نتائج لبدائل مشابهة. أبقِ البدائل الحقيقية من نفس الفئة والاستخدام،
وارفض المنتج الأصلي نفسه والكتيبات وقطع الغيار والملحقات والخدمات. أرجع JSON فقط: {\"keep\":[1,3]}"""
_URL_ALIVE_CACHE = {}; _URL_ALIVE_LOCK = threading.Lock()
_STORE_HOME_CACHE = {}; _STORE_HOME_LOCK = threading.Lock()
STORE_DOMAIN_SYSTEM = """أرجع دومين الموقع الرسمي للمتجر فقط بدون https وبدون شرح. إذا لم تكن متأكداً 100% أرجع NONE."""
TRANSLATE_TITLES_SYSTEM = """ترجم أسماء المنتجات التالية إلى العربية بأسلوب متجر واضح ومختصر. أبقِ البراند والموديل والأرقام كما هي.
سطر واحد لكل منتج وبنفس الترقيم. بدون شرح."""
AR_TITLE_CACHE = {}; AR_TITLE_LOCK = threading.Lock()

_STORE_GENERIC_TOKENS = {
    "هايبر", "هاير", "ماركت", "هايبرماركت", "هايرماركت", "سوبرماركت", "سوبر", "مول", "اسواق", "سوق", "مركز", "سنتر", "center", "centre",
    "اونلاين", "اون", "لاين", "الكويت", "كويت", "متجر", "محل", "شركه", "شركة", "hyper", "market", "hypermarket", "supermarket", "super", "store", "shop", "online", "kuwait", "kw", "mall", "co", "company", "the",
}
STORE_UNIFY_SYSTEM = """أنت موحّد أسماء متاجر. جمّع الأرقام التي تعود لنفس المتجر الفعلي حتى لو اختلف الإملاء أو اللغة.
أرجع JSON فقط: {\"groups\":[[1,3],[2],[4,5]]} بحيث يظهر كل رقم مرة واحدة بالضبط."""
_STORE_UNIFY_CACHE = {}; _STORE_UNIFY_LOCK = threading.Lock()
KNOWN_SEARCH_TEMPLATES = {
    "luluhypermarket": "https://gcc.luluhypermarket.com/en-kw/search?text={q}",
    "carrefourkuwait": "https://www.carrefourkuwait.com/mafkwt/en/v4/search?keyword={q}",
    "taw9eel": "https://www.taw9eel.com/en/catalogsearch/result/?q={q}",
    "sultan-center": "https://www.sultan-center.com/catalogsearch/result/?q={q}",
    "jm3eia": "https://www.jm3eia.com/en/search?q={q}",
    "safathome": "https://www.safathome.com/catalogsearch/result/?q={q}",
    "xcite": "https://www.xcite.com/search?text={q}",
    "abyat": "https://www.abyat.com/kw/en/search/{q}",
}
_GENERIC_SEARCH_PATTERNS = ("https://{d}/catalogsearch/result/?q={q}", "https://{d}/search?q={q}", "https://{d}/en/search?q={q}")
_SEARCH_TMPL_CACHE = {}; _SEARCH_TMPL_LOCK = threading.Lock()
CART_ITEM_DEADLINE = max(60, int(os.environ.get("CART_DEADLINE_SECONDS", "240")))
CART_CONCURRENCY = max(1, int(os.environ.get("CART_CONCURRENCY", "2")))


def _clean_store_name(name):
    """v74.5: تنظيف اسم المتجر من أقواس Gemini الزائدة: «[إكسايت] (» -> «إكسايت»."""
    n = re.sub(r"[\[\]«»\"']+", "", str(name or ""))
    n = re.sub(r"\(\s*[^)]*\)?\s*$", "", n)  # قوس مفتوح أو فاضي بنهاية الاسم
    return " ".join(n.split()).strip(" -—–:،") or str(name or "").strip()

def _fast_relevance_confident(query, candidates):
    """True when returned titles already contain strong query/model evidence.

    This avoids an extra plain-Gemini relevance round-trip for obvious exact-model searches.
    Ambiguous results still use the AI filter.
    """
    seq = list(candidates or [])
    if not seq:
        return False
    q_tokens = norm_tokens(query)
    if not q_tokens:
        return False
    q_models = {t for t in q_tokens if any(ch.isdigit() for ch in t) and len(t) >= 2}
    confident = 0
    considered = 0
    for item in seq:
        title = str(item.get("title") or item.get("line") or "")
        t_tokens = norm_tokens(title)
        if not t_tokens:
            continue
        considered += 1
        if q_models:
            if q_models & t_tokens:
                confident += 1
        else:
            overlap = len(q_tokens & t_tokens) / max(1, min(len(q_tokens), len(t_tokens)))
            if overlap >= 0.60:
                confident += 1
    return considered > 0 and confident / considered >= 0.80


def filter_relevant_offers(query, offers, urls, use_ai=True, mode="exact"):
    """v74.9: يرمي النتائج غير ذات الصلة (كتيب بدل اليخت...). طبقتان: كلمات قاطعة ثم حكم ذكي."""
    if not offers:
        return offers
    q_norm = normalize_ar(str(query or ""))
    wants_non_product = any(normalize_ar(w) in q_norm for w in _NON_PRODUCT_WORDS)
    kept = []
    for o in offers:
        hay = normalize_ar(f"{o.get('line','')} {match_url(o.get('name',''), urls or {})}")
        if not wants_non_product and any(normalize_ar(w) in hay for w in _NON_PRODUCT_WORDS):
            print(f"RELEVANCE HARD-DROP: {o.get('line','')[:80]}")
            continue
        kept.append(o)
    if not use_ai or not ENABLE_RELEVANCE_FILTER or not kept or len(kept) == 0:
        return kept
    # حكم ذكي واحد سريع للدفعة كلها — يمسك الحالات اللي ما تمسكها الكلمات.
    numbered = []
    for i, o in enumerate(kept, 1):
        u = match_url(o.get("name", ""), urls or {})
        try:
            host = urllib.parse.urlparse(u or "").netloc.replace("www.", "")
        except Exception:
            host = ""
        numbered.append(f"{i}. {o.get('line','')[:100]} — {host}")
    prompt_label = "المنتج المرجعي للبدائل" if mode == "similar" else "طلب المستخدم"
    prompt = f"{prompt_label}: {query}\n\nالنتائج:\n" + "\n".join(numbered)
    relevance_system = SIMILAR_RELEVANCE_FILTER_SYSTEM if mode == "similar" else RELEVANCE_FILTER_SYSTEM
    raw, _ = text77_call_gemini([{"text": prompt}], system=relevance_system, use_search=False)
    try:
        data = json.loads(re.search(r"\{.*\}", raw or "", flags=re.S).group(0))
        keep_idx = {int(x) for x in (data.get("keep") or [])}
        ai_kept = [o for i, o in enumerate(kept, 1) if i in keep_idx]
        dropped = [o.get("line", "")[:60] for i, o in enumerate(kept, 1) if i not in keep_idx]
        if dropped:
            print(f"RELEVANCE AI-DROP ({len(dropped)}): {dropped[:4]}")
        # حماية: إذا الحكم رمى كل شي بدون سبب واضح نبقي القائمة (أفضل من إخفاء نتائج صحيحة).
        return ai_kept if ai_kept else kept
    except Exception:
        print(f"RELEVANCE AI PARSE FAIL — keeping as-is: {raw!r}")
        return kept

def url_is_alive(url):
    """فحص سريع (كاش) أن الرابط يفتح فعلاً — Safari can't open the page ممنوعة."""
    u = str(url or "").strip()
    if not u.startswith("http"):
        return False
    key = u.split("?")[0][:200]
    with _URL_ALIVE_LOCK:
        hit = _URL_ALIVE_CACHE.get(key)
        if hit and time.time() - hit["ts"] < 21600:
            return hit["ok"]
    ok = False
    try:
        r = requests.head(u, headers=HEADERS, timeout=6, allow_redirects=True)
        ok = r.status_code < 400
        if not ok and r.status_code in (403, 405, 501):
            # بعض المتاجر تمنع HEAD؛ نجرب GET خفيف.
            r = requests.get(u, headers=HEADERS, timeout=8, stream=True)
            ok = r.status_code < 400
            r.close()
    except Exception as e:
        print(f"URL ALIVE FAIL: {u[:80]} -> {e.__class__.__name__}")
        ok = False
    with _URL_ALIVE_LOCK:
        if len(_URL_ALIVE_CACHE) > 3000:
            _URL_ALIVE_CACHE.clear()
        _URL_ALIVE_CACHE[key] = {"ok": ok, "ts": time.time()}
    return ok

def resolve_store_homepage(name):
    """رابط للمتجر عندما لا يوجد رابط منتج: القاموس أولاً، ثم ذكاء اصطناعي (كاش)."""
    name = str(name or "").strip()
    if not name:
        return ""
    dom = text77_store_domain(name)
    if dom:
        return f"https://{dom}"
    key = normalize_name(normalize_ar(name))[:80]
    if not key:
        return ""
    with _STORE_HOME_LOCK:
        if key in _STORE_HOME_CACHE:
            return _STORE_HOME_CACHE[key]
    raw, _ = text77_call_gemini(
        [{"text": f"المتجر: {name}\nالبلد: {current_market().get('country_name', 'Kuwait')}"}],
        system=STORE_DOMAIN_SYSTEM, use_search=False,
    )
    ans = (raw or "").strip().splitlines()[0].strip().lower() if raw else ""
    ans = ans.replace("https://", "").replace("http://", "").strip("/ ")
    url = ""
    if ans and ans != "none" and re.fullmatch(r"[a-z0-9][a-z0-9.-]{2,60}\.[a-z]{2,10}", ans):
        candidate = f"https://{ans}"
        # v74.15: الذكاء أحياناً يخمّن دومينات غير موجودة (mustafakaram.com...) رغم
        # التحذير — الفحص الحي إلزامي: رابط ميت = كأنه ما انحل.
        if url_is_alive(candidate):
            url = candidate
        else:
            print(f"STORE HOMEPAGE DEAD — REJECTED: {ans}")
    with _STORE_HOME_LOCK:
        if len(_STORE_HOME_CACHE) > 2000:
            _STORE_HOME_CACHE.clear()
        _STORE_HOME_CACHE[key] = url
    print(f"STORE HOMEPAGE RESOLVED: {name!r} -> {url or 'NONE'}")
    return url

def v26_answer_score(txt, urls, max_results=None):
    """v26: تقييم قوة الجواب — المتاجر أهم شي، ثم اللنكات، ثم سلامة التنسيق.

    ``max_results`` موجود للتوافق مع مسار v76، لكن طريقة تقييم v26 الأصلية لم تتغير.
    """
    stores = len(extract_store_names(txt or ""))
    links = len(urls or {})
    score = stores * 2 + links * 3
    if txt and "📦" in txt:
        score += 1
    return score

def _merge_v26_offer_text(results, title_line, max_results):
    """v76: اتحاد عروض جولات v26 نفسها، وليس اللنكات فقط.

    هذا مهم للبدائل: كل جولة Google grounding قد تجد براند/متجر مختلف،
    فنأخذ أفضل عروض الجميع حتى نكوّن قائمة أوسع ثم نرتبها بالسعر.
    """
    picked = {}
    for txt, urls in results:
        for offer in text77_extract_store_offers(txt or "", limit=max_results):
            key = normalize_name(offer.get("name", ""))
            if not key:
                continue
            price = _extract_numeric_price(offer.get("line", ""))
            prev = picked.get(key)
            if prev is None or ((price is not None) and (prev[0] is None or price < prev[0])):
                picked[key] = (price, offer)
    if not picked:
        return results[0][0] if results else ""
    ordered = sorted(
        (v for v in picked.values()),
        key=lambda x: (x[0] is None, x[0] if x[0] is not None else 10**12),
    )[:max_results]
    lines = []
    for i, (_, offer) in enumerate(ordered):
        body = re.sub(r"^(?:✅|🏆|•)\s*", "", offer.get("line", "")).strip()
        if body:
            lines.append(f"{'✅' if i == 0 else '•'} {body}")
    return (title_line.strip() + "\n" + "\n".join(lines)).strip()

def _fast_tournament_results(futs, limit, timeout_seconds):
    """Return tournament results without waiting for a slow duplicate when a strong answer is already ready.

    All runs still start in parallel. After the first completion, a strong result gets only a short
    grace window for peers to join; weak/empty first results keep the full timeout for quality.
    """
    pending = set(futs)
    results = []
    if not pending:
        return results
    done, pending = wait(pending, timeout=timeout_seconds, return_when=FIRST_COMPLETED)
    for f in done:
        try:
            r = f.result()
            if r and r[0]:
                results.append(r)
        except Exception as e:
            print(f"TOURNAMENT FIRST ERR: {e}")
    def strong():
        for txt, urls in results:
            offers = text77_extract_store_offers(txt, limit=limit)
            if len(offers) >= min(3, limit) and len(urls or {}) >= min(2, limit):
                return True
        return False
    if pending:
        extra_wait = TOURNAMENT_GRACE_SECONDS if strong() else timeout_seconds
        done2, pending2 = wait(pending, timeout=extra_wait)
        for f in done2:
            try:
                r = f.result()
                if r and r[0]:
                    results.append(r)
            except Exception as e:
                print(f"TOURNAMENT PEER ERR: {e}")
        for f in pending2:
            f.cancel()
    return results

def v26_best_of_search(parts, max_results=None, merge_offers=False, merge_title=""):
    """v26 tournament with an optional v76 union mode for similar alternatives.

    Normal callers are unchanged. For alternatives, ``merge_offers=True`` unions
    different stores/products discovered across SEARCH_RUNS instead of throwing
    away everything except the winning text.
    """
    limit = MAX_STORES if max_results is None else max(1, int(max_results))
    market_snapshot = current_market()
    try:
        futs = [V26_SEARCH_POOL.submit(_run_with_market, market_snapshot, text77_call_gemini, parts)
                for _ in range(SEARCH_RUNS)]
        results = _fast_tournament_results(futs, limit, GEMINI_SEARCH_TIMEOUT_SECONDS + 5)
    except Exception as e:
        print(f"v26 best_of_search err {e}")
        return text77_call_gemini(parts)

    results = [(t, u) for (t, u) in results if t]
    if not results:
        return "", {}

    scored = sorted(results, key=lambda r: v26_answer_score(r[0], r[1], limit), reverse=True)
    best_txt, best_urls = scored[0]

    # اتحاد اللنكات: الفائز أولاً، ثم بقية الجولات تكمل النواقص.
    merged_urls = dict(best_urls)
    for _, u in scored[1:]:
        for n, link in u.items():
            if n not in merged_urls and link not in merged_urls.values():
                merged_urls[n] = link
    merged_urls = dict(list(merged_urls.items())[:max(limit, 4)])

    if merge_offers:
        best_txt = _merge_v26_offer_text(scored, merge_title or product_title(best_txt, ""), limit)

    print({"v26_tournament": [v26_answer_score(t, u, limit) for t, u in scored],
           "winner_stores": len(text77_extract_store_offers(best_txt, limit=limit)),
           "total_links": len(merged_urls),
           "merged_offers": bool(merge_offers)})
    return best_txt, merged_urls

def arabic_titles(titles):
    """يعيد {العنوان الأصلي: الترجمة العربية}. العناوين العربية أصلاً تمر كما هي، وعند
    فشل الترجمة يُعرض الأصل الإنجليزي بدل بطاقة فارغة."""
    out, todo = {}, []
    for t in titles:
        t = (t or "").strip()
        if not t:
            continue
        key = t.lower()
        with AR_TITLE_LOCK:
            cached = AR_TITLE_CACHE.get(key)
        if cached:
            out[t] = cached
        elif re.search(r"[\u0600-\u06FF]", t):
            out[t] = t
        elif t not in todo:
            todo.append(t)
    if todo:
        numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(todo))
        raw, _ = text77_call_gemini([{"text": numbered}], system=TRANSLATE_TITLES_SYSTEM, use_search=False)
        lines = [re.sub(r"^\s*\d+[\.\)\-]\s*", "", l).strip() for l in (raw or "").splitlines() if l.strip()]
        with AR_TITLE_LOCK:
            if len(AR_TITLE_CACHE) > 3000:
                AR_TITLE_CACHE.clear()
            for i, t in enumerate(todo):
                tr = lines[i] if i < len(lines) and re.search(r"[\u0600-\u06FF]", lines[i]) else t
                out[t] = tr
                AR_TITLE_CACHE[t.lower()] = tr
        print(f"AR TITLES TRANSLATED: {len(todo)}")
    return out

def arabic_search_name(query):
    """v74.7: المقابل العربي لاسم إنجليزي (Toyota Land Cruiser -> تويوتا لاند كروزر).

    نفس فكرة english_search_name بالاتجاه المعاكس — نموذج سريع رخيص + كاش،
    حتى يبحث البوت بالاسمين مهما كانت لغة كتابة المستخدم.
    """
    q = " ".join(str(query or "").split()).strip()
    if not q or re.search(r"[\u0600-\u06FF]", q):
        return ""
    translated = arabic_titles([q]).get(q, "")
    return translated if translated and translated != q else ""

def send_whatsapp_list(to, body, rows, bot_id, button_title="اختر"):
    """v74: رسالة قائمة تفاعلية (حتى 10 صفوف) — لاختيار منتج من مقارنة البراندات."""
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    clean_rows=[]
    for r in rows[:10]:
        row={"id":r["id"],"title":_remove_ui_autolinks(str(r.get("title","")))[:24]}
        desc=_remove_ui_autolinks(str(r.get("description","") or ""))[:72]
        if desc: row["description"]=desc
        clean_rows.append(row)
    payload={"messaging_product":"whatsapp","to":to,"type":"interactive","interactive":{
        "type":"list","body":{"text":_remove_ui_autolinks(body)[:1024]},
        "action":{"button":_remove_ui_autolinks(button_title)[:20],"sections":[{"title":_remove_ui_autolinks(button_title)[:24],"rows":clean_rows}]}}}
    try:
        r=_whatsapp_http_session().post(url,json=payload,headers=h,timeout=(3, WHATSAPP_TIMEOUT_SECONDS))
        if not r.ok: print(f"LIST MSG ERR {r.status_code}: {r.text[:200]}")
        return r.ok
    except Exception as e:
        print(f"LIST MSG ERR: {e}"); return False


# ---- Region expansion removed in v84: the UI was already disabled. ------------

def _host_of(url):
    try:
        return urllib.parse.urlparse(str(url or "")).netloc.lower().replace("www.", "")
    except Exception:
        return ""

def canonical_store_key(name, url=""):
    """v75.3: هوية موحدة للمتجر — «لولو هايبر ماركت» و«لولو هايبرماركت» و«لولو الكويت»

    كلها متجر واحد: الدومين أولاً، ثم قاموس المتاجر، ثم الاسم بعد إزالة الكلمات العامة."""
    host = _host_of(url)
    if host:
        return domain_key(host)
    dom = text77_store_domain(name)
    if dom:
        return domain_key(dom)
    n = normalize_ar(str(name or ""))
    toks = [t for t in re.findall(r"[\w\u0600-\u06FF]+", n) if t not in _STORE_GENERIC_TOKENS]
    core = " ".join(toks).strip()
    if core:
        dom = text77_store_domain(core)
        if dom:
            return domain_key(dom)
    key = normalize_name("".join(toks))
    return key or normalize_name(n)

def unify_store_groups(names):
    """يرجع مجموعات فهارس الأسماء المتطابقة فعلياً — حكم ذكي واحد سريع (كاش)."""
    if len(names) < 2:
        return [[i] for i in range(len(names))]
    key = "|".join(sorted(normalize_name(normalize_ar(n)) for n in names))[:400]
    with _STORE_UNIFY_LOCK:
        if key in _STORE_UNIFY_CACHE:
            return _STORE_UNIFY_CACHE[key]
    numbered = "\n".join(f"{i}. {n}" for i, n in enumerate(names, 1))
    raw, _ = text77_call_gemini([{"text": numbered}], system=STORE_UNIFY_SYSTEM, use_search=False)
    groups = None
    try:
        data = json.loads(re.search(r"\{.*\}", raw or "", flags=re.S).group(0))
        cand = [[int(x) - 1 for x in g] for g in (data.get("groups") or []) if g]
        seen = sorted(i for g in cand for i in g)
        if seen == list(range(len(names))):
            groups = cand
        else:
            print(f"STORE UNIFY INVALID GROUPS (missing/dup idx): {raw!r}")
    except Exception:
        print(f"STORE UNIFY PARSE FAIL: {raw!r}")
    if groups is None:
        groups = [[i] for i in range(len(names))]
    with _STORE_UNIFY_LOCK:
        if len(_STORE_UNIFY_CACHE) > 500:
            _STORE_UNIFY_CACHE.clear()
        _STORE_UNIFY_CACHE[key] = groups
    return groups

def merge_store_matrix_ai(stores):
    """v75.5: دمج نهائي بالذكاء — «لولو هاير ماركت» و«Lulu» يصيرون متجراً واحداً

    مهما كان الإملاء. لكل صنف يبقى أرخص سعر، والاسم المعروض الأقصر."""
    entries = list(stores.values())
    if len(entries) < 2:
        return stores
    names = [e["name"] for e in entries]
    groups = unify_store_groups(names)
    if all(len(g) == 1 for g in groups):
        return stores
    merged = {}
    for gi, group in enumerate(groups):
        base = min((entries[i] for i in group), key=lambda e: len(e["name"]))
        bucket = {"name": base["name"], "items": {}}
        for i in group:
            for p, inf in entries[i]["items"].items():
                prev = bucket["items"].get(p)
                if prev is None or inf["price"] < prev["price"]:
                    bucket["items"][p] = inf
        merged[f"g{gi}"] = bucket
    if len(merged) != len(entries):
        print(f"STORE UNIFY MERGED: {len(entries)} -> {len(merged)} stores: {[m['name'] for m in merged.values()]}")
    return merged

def store_search_url(store_name, query):
    """رابط نتائج بحث المتجر عن الصنف — أفضل بكثير من الرئيسية. يُفحص حياً ويُكاش القالب."""
    dom = text77_store_domain(store_name)
    host = clean_domain(dom) if dom else _host_of(resolve_store_homepage(store_name))
    if not host:
        return ""
    q = urllib.parse.quote(" ".join(str(query or "").split())[:80])
    with _SEARCH_TMPL_LOCK:
        cached_tmpl = _SEARCH_TMPL_CACHE.get(host)
    candidates = [cached_tmpl] if cached_tmpl else []
    if not candidates:
        dkey = host.split(".")[0]
        if dkey in KNOWN_SEARCH_TEMPLATES:
            candidates.append(KNOWN_SEARCH_TEMPLATES[dkey])
        candidates += [p.replace("{d}", host) for p in _GENERIC_SEARCH_PATTERNS]
    for tmpl in candidates:
        url = tmpl.replace("{q}", q)
        if url_is_alive(url):
            with _SEARCH_TMPL_LOCK:
                if len(_SEARCH_TMPL_CACHE) > 500:
                    _SEARCH_TMPL_CACHE.clear()
                _SEARCH_TMPL_CACHE[host] = tmpl
            return url
    return ""

def cart_item_search(product, lang):
    """v75.4: بحث صنف السلة بالمسار الذكي الكامل القديم (بطولة v26) — بطلب من خالد.

    بطولة SEARCH_RUNS بحوث Gemini متوازية لنفس الصنف، الأقوى يفوز واللنكات اتحاد
    الجولات (نفس محرك البحث النصي والبدائل حرفياً). العرض يبقى بتنسيق v75.3.
    عند فشل البطولة: محاولة موسعة باتصال واحد كشبكة أمان. الكاش يخدم التكرار.
    """
    cached = cache_get(product, lang)
    if cached:
        return cached
    txt, urls = v26_best_of_search([{"text": text77_bilingual_search_instruction(product, lang)}])
    urls = direct_urls_only(urls)
    if txt and text77_extract_store_offers(txt) and not is_no_result_answer(txt):
        cache_put(product, lang, txt, urls)
        return txt, urls
    market_name = current_market().get("country_name", "Kuwait")
    txt, urls = text77_call_gemini([{"text": (
        f"ابحث عن {product} في أي متجر محلي في {market_name} يبيعه بسعر رقمي واضح "
        f"ورابط صفحة منتج مباشر. حتى {MAX_STORES} متاجر من الأرخص للأغلى. {TEXT77_lang_instr(lang)}"
    )}])
    urls = direct_urls_only(urls)
    if txt and text77_extract_store_offers(txt) and not is_no_result_answer(txt):
        cache_put(product, lang, txt, urls)
        return txt, urls
    return "", {}

def run_cart_comparison(products, from_number, bot_id, lang="ar"):
    """v75: السلة الموحدة — بدل أرخص متجر لكل صنف لحاله (وتشتت الطلب على 4 متاجر)،

    نجمع نتائج كل الأصناف ونبني مصفوفة متجر × صنف: كم صنفاً يغطي كل متجر ومجموع
    سلته، ونعرض قائمة متاجر مرتبة (الأشمل ثم الأوفر). يختار المستخدم متجراً واحداً
    فنرسل كل أصنافه بروابط صفحاتها المباشرة داخل نفس المتجر — طلبية وحدة وسلة وحدة.
    """
    market = market_for_user(from_number)
    send_whatsapp_text(from_number, T(lang, "cart_comparing", c=len(products)), bot_id)
    # v75.2: بحث خفيف بالتوازي + مهلة قصوى إجمالية — اللي يتأخر عن المهلة ينحسب غير موجود،
    # والسلة تكمل بما توفر بدل ما تعلق للأبد. وأي خطأ داخلي = رد واضح مو صمت.
    results = []
    try:
        # v75.4: موجات بتزامن محدود — كل صنف بطولة كاملة، والموجة تمنع تزاحم المسابح.
        deadline = time.time() + CART_ITEM_DEADLINE
        for start in range(0, len(products), CART_CONCURRENCY):
            wave = products[start:start + CART_CONCURRENCY]
            futures = {WORKERS.submit(_run_with_market, market, cart_item_search, p, lang): p for p in wave}
            for future, p in futures.items():
                remain = max(5.0, deadline - time.time())
                try:
                    txt, urls = future.result(timeout=remain)
                except Exception as e:
                    print(f"CART ITEM TIMEOUT/ERR ({p}): {e.__class__.__name__}")
                    txt, urls = "", {}
                results.append((p, txt, urls))
            if time.time() >= deadline:
                # المهلة انتهت: الأصناف الباقية تنحسب غير موجودة والسلة تكمل بما توفر.
                for p in products[start + CART_CONCURRENCY:]:
                    print(f"CART DEADLINE SKIP: {p}")
                    results.append((p, "", {}))
                break
    except Exception as e:
        print(f"CART GATHER CRASH: {e}")
        send_whatsapp_text(from_number, T(lang, "not_found"), bot_id)
        return

    stores = {}
    try:
        for p, txt, urls in results:
            if not txt:
                continue
            offers = filter_relevant_offers(p, text77_extract_store_offers(txt), urls, use_ai=False)
            for o in offers:
                url = match_url(o.get("name", ""), urls or {})
                price = _extract_numeric_price(o.get("line", ""))
                if price is None or price <= 0:
                    continue
                host = _host_of(url)
                key = canonical_store_key(o.get("name", ""), url)
                if not key:
                    continue
                display = _clean_store_name(o.get("name", "")) or key
                s = stores.setdefault(key, {"name": display, "items": {}})
                # v75.3: نعتمد أقصر اسم معروض لنفس المتجر (لولو أنظف من لولو هايبر ماركت الكويت).
                if display and len(display) < len(s["name"]):
                    s["name"] = display
                prev = s["items"].get(p)
                if prev is None or price < prev["price"]:
                    s["items"][p] = {"price": price, "url": url}
    except Exception as e:
        print(f"CART MATRIX CRASH: {e}")
        stores = {}
    # v75.5: دمج نهائي بالذكاء — أي صيغ مختلفة لنفس المتجر تتوحد مهما كان الإملاء.
    try:
        stores = merge_store_matrix_ai(stores)
    except Exception as e:
        print(f"STORE UNIFY CRASH (keeping as-is): {e}")

    if not stores:
        # احتياط: السلوك القديم — أفضل عرض لكل صنف على حدة.
        any_ok = False
        for p, txt, urls in results:
            if not txt:
                continue
            any_ok = True
            send_product_result(from_number, txt, urls, bot_id, lang, p, best_only=True)
        if not any_ok:
            send_whatsapp_text(from_number, T(lang, "not_found"), bot_id)
        return

    n = len(products)
    ranked = sorted(
        stores.values(),
        key=lambda s: (-len(s["items"]), sum(i["price"] for i in s["items"].values())),
    )[:6]

    unit = U(lang, "items")
    # v75.5: بدون رسالة ملخص — قائمة الاختيار وحدها تكفي (وصف كل صف فيه التغطية والمجموع).
    rows = []
    for i, s in enumerate(ranked):
        cov = len(s["items"])
        total = sum(x["price"] for x in s["items"].values())
        rows.append({
            "id": f"cart_{i}",
            "title": s["name"][:24],
            "description": f"{cov}/{n} {unit} — {format_price(total)} {currency_label(lang)}"[:72],
        })
    PENDING_CART_PICKS[from_number] = {
        "stores": [(s["name"], s["items"]) for s in ranked],
        "products": list(products), "bot_id": bot_id, "lang": lang, "ts": time.time(),
    }
    send_whatsapp_list(from_number, T(lang, "cart_pick_prompt"), rows, bot_id, T(lang, "cart_store_button"))
    LAST_SEARCH[from_number] = {"product": products[0]}
    print(f"CART COMPARISON SENT: {[(s['name'], len(s['items'])) for s in ranked]}")

def _greedy_cart_completion(remaining, stores_list, used_idx):
    """v75.1: تغطية النواقص من متاجر القائمة نفسها — كل مرة نختار المتجر الذي يغطي

    أكبر عدد من الأصناف المتبقية (وعند التساوي الأرخص)، حتى تكتمل السلة أو تنفد المتاجر."""
    plans, rem, used = [], set(remaining), set(used_idx)
    while rem:
        best = None
        for i, (nm, items) in enumerate(stores_list):
            if i in used:
                continue
            cover = [p for p in rem if p in items]
            if not cover:
                continue
            total = sum(items[p]["price"] for p in cover)
            score = (len(cover), -total)
            if best is None or score > best[0]:
                best = (score, i, nm, cover, total)
        if best is None:
            break
        _score, i, nm, cover, _total = best
        used.add(i)
        rem -= set(cover)
        plans.append((i, nm, {p: stores_list[i][1][p] for p in cover}))
    return plans, sorted(rem)

def _send_store_cart_block(from_number, store_name, items_map, products_order, bot_id, lang, is_main):
    """v75.3: كتلة متجر بالشكل المطلوب — رأس واضح مختصر، ثم كل منتج ببطاقة CTA خاصة.

    رأس المتجر الرئيسي: «🧺 لولو — 4/6 أصناف — 3.435 د.ك»
    رأس التكملة:        «🧩 جمعية — يكمل صنفين — 1.250 د.ك»
    وتحت كل رأس: بطاقة لكل منتج (اسم + سعر) بزر يفتح صفحته المباشرة، وإلا رئيسية المتجر.
    """
    ordered = [p for p in products_order if p in items_map]
    if not ordered:
        return 0.0
    total = sum(items_map[p]["price"] for p in ordered)
    unit = U(lang, "items")
    if is_main:
        header = f"🧺 {store_name} — {len(ordered)} {unit} — {format_price(total)} {currency_label(lang)}"
    else:
        verb = U(lang, "completes")
        header = f"🧩 {store_name} — {verb} {len(ordered)} {unit} — {format_price(total)} {currency_label(lang)}"
    send_whatsapp_text(from_number, header, bot_id)
    store_home = None
    for i, p in enumerate(ordered, 1):
        inf = items_map[p]
        body = f"{i}. {p} — {format_price(inf['price'])} {currency_label(lang)}"
        url = inf.get("url") or ""
        if not (url and is_direct_store_url(url)):
            # v75.5: الأفضلية لرابط نتائج بحث المتجر عن الصنف نفسه — يوصلك للمنتج مو للرئيسية.
            search_link = store_search_url(store_name, p)
            if search_link:
                url = search_link
            else:
                if store_home is None:
                    store_home = resolve_store_homepage(store_name) or ""
                url = url if (url and url.startswith("http") and "google." not in _host_of(url)) else store_home
        if url:
            send_whatsapp_cta(from_number, body, url, bot_id, f"🛒 {store_name[:18]}")
        else:
            send_whatsapp_text(from_number, body, bot_id)
    return total

def send_cart_from_store(from_number, chosen_idx, stores_list, products, bot_id, lang):
    """v75.3: الترتيب المطلوب — المتجر الأكثر أصنافاً (المختار) أولاً وتحته منتجاته

    ببطاقات CTA، ثم متجر التكملة ومنتجاته، وهكذا حتى تكتمل السلة. المجموع بالنهاية
    مع نصيحة الجلسة الواحدة مرة واحدة فقط.
    """
    store_name, items = stores_list[chosen_idx]
    plan_total = _send_store_cart_block(from_number, store_name, items, products, bot_id, lang, is_main=True)
    remaining = [p for p in products if p not in items]
    if remaining:
        plans, still_missing = _greedy_cart_completion(remaining, stores_list, {chosen_idx})
        for _i, nm, cover_items in plans:
            plan_total += _send_store_cart_block(from_number, nm, cover_items, products, bot_id, lang, is_main=False)
        tail = T(lang, "cart_plan_total", t=f"{format_price(plan_total)} {currency_label(lang)}")
        if still_missing:
            joiner = "، " if lang in ("ar", "ur") else ", "
            tail += "\n" + T(lang, "cart_not_anywhere", items=joiner.join(still_missing))
    else:
        tail = T(lang, "cart_total", t=f"{format_price(plan_total)} {currency_label(lang)}")
    tail += "\n\n" + T(lang, "cart_session_tip")
    send_whatsapp_text(from_number, tail, bot_id)
    return True

LEGACY_TEXT_SEARCH_SYSTEM = r"""
أنت مساعد تسوق. استخدم بحث Google فعلياً للأسعار والتقييمات الحالية في سوق المستخدم المحلي.

أولاً حدد نوع الطلب:

【الحالة 1】منتج محدد بعلامة تجارية واضحة:
قارن الأسعار واختر الأرخص، ورد بهذا الشكل فقط:
📦 [اسم المنتج]

✅ [المتجر الأرخص] — [السعر بعملة السوق]
• [المتجر الثاني] — [السعر بعملة السوق]
• [المتجر الثالث] — [السعر بعملة السوق]

【الحالة 2】طلب عام بدون براند محدد:
ابحث عن أفضل الخيارات المتوفرة محلياً بسعر مناسب، مع الالتزام بالتنسيق الذي يطلبه المستخدم في الرسالة.

【الحالة 3】طلب خدمة:
ابحث عن أفضل مزودي الخدمة محلياً، ولا تكتب رقم هاتف إلا إذا ظهر حرفياً في نتائج Google.

【الحالة 4】سؤال معلوماتي:
أجب على السؤال نفسه مباشرة ولا تعرض مقارنة أسعار إلا إذا طلبها المستخدم.

في نتائج التسوق التي تحتوي متاجر، سطر أخير إلزامي:
LINKS: اسم الأول=الدومين الحقيقي, اسم الثاني=الدومين الحقيقي, اسم الثالث=الدومين الحقيقي
لا تخمّن الدومين، ولا تذكر متجراً أو خياراً من دون مصدر بحث.
استبعد Heureka / heureka.cz / heureka.sk نهائياً من نتائج التسوق؛ لا تخلطه مع Eureka الكويتية.
ممنوع روابط ظاهرة في النص. ممنوع Markdown.
"""


def _legacy_extract_store_names(text, limit=None):
    """نسخة متوافقة مع عرض v76: تستخرج اسم المتجر من سطور العرض الحالية."""
    cap = MAX_STORES if limit is None else max(1, int(limit))
    names=[]
    for o in text77_extract_store_offers(text or "", limit=cap):
        n=str(o.get("name") or "").strip()
        if n and n not in names:
            names.append(n)
    return names[:cap]


def legacy_v26_call_gemini(parts, system=LEGACY_TEXT_SEARCH_SYSTEM, max_results=None):
    """محرك call_gemini من الكود المرفق: GroundingSupports أولاً ثم LINKS ثم titles.

    مخصص للبحث النصي والبدائل فقط. لا يستخدم صوراً ولا Google Lens.
    """
    limit = MAX_STORES if max_results is None else max(1, int(max_results))
    model = GEMINI_SEARCH_MODEL
    gemini_url = f"{GEMINI_BASE_URL}/{model}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": system + text77_market_instruction()}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 2000},
        "tools": [{"google_search": {}}],
    }
    try:
        with GEMINI_STATS_LOCK:
            GEMINI_STATS["search_calls"] += 1
            print(f"LEGACY V26 CALL model={model} totals={GEMINI_STATS}")
        r = requests.post(gemini_url, params={"key": GEMINI_API_KEY}, json=payload, timeout=(5, GEMINI_SEARCH_TIMEOUT_SECONDS))
        if r.status_code >= 400:
            print(f"LEGACY V26 Gemini HTTP {r.status_code}: {r.text[:500]}")
            return "", {}
        data = r.json()
        candidates = data.get("candidates") or []
        if not candidates:
            print(f"LEGACY V26 no candidates: {str(data)[:500]}")
            return "", {}
        cand = candidates[0]
        text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", [])).strip()

        # LINKS line from the old supplied engine.
        pairs=[]
        m=re.search(r"(?im)^\s*LINKS\s*:\s*(.+)$", text)
        if m:
            for part in re.split(r"[,،]+", m.group(1)):
                part=part.strip()
                if "=" in part:
                    name,dom=part.split("=",1)
                    name,dom=name.strip(),clean_domain(dom)
                    if name and "." in dom:
                        pairs.append((name,dom))
            text=re.sub(r"(?im)^\s*LINKS\s*:.*$", "", text).strip()
        text=re.sub(r"https?://\S+", "", text).replace("**", "").strip()

        metadata=cand.get("groundingMetadata",{}) or {}
        chunks=metadata.get("groundingChunks",[]) or []
        uris=[(c.get("web") or {}).get("uri","") for c in chunks]
        finals=resolve_all(uris[:16]) if uris else []
        records=[]
        for i,chunk in enumerate(chunks[:16]):
            web=chunk.get("web") or {}
            raw_uri=web.get("uri","")
            final_uri=finals[i] if i < len(finals) else raw_uri
            records.append({"title":web.get("title",""),"raw":raw_uri,"url":final_uri or raw_uri})

        urls_map={}
        used_urls=set()
        stores=_legacy_extract_store_names(text, limit)

        # 1) أفضل ربط: groundingSupports الخاصة بالسطر الذي يحتوي اسم المتجر.
        supports=metadata.get("groundingSupports",[]) or []
        for store in stores:
            store_norm=normalize_name(store)
            for support in supports:
                segment=(support.get("segment") or {}).get("text","")
                if store_norm and store_norm in normalize_name(segment):
                    for cidx in support.get("groundingChunkIndices",[]) or []:
                        if 0 <= cidx < len(records):
                            url=records[cidx]["url"]
                            if url and url not in used_urls:
                                urls_map[store]=url; used_urls.add(url); break
                if store in urls_map:
                    break

        # 2) LINKS domains ضد روابط Grounding الحقيقية.
        for name,dom in pairs:
            if name in urls_map: continue
            key=domain_key(dom)
            for rec in records:
                hay=f"{rec['title']} {rec['raw']} {rec['url']}".lower()
                if rec['url'] and key and key in hay and rec['url'] not in used_urls:
                    urls_map[name]=rec['url']; used_urls.add(rec['url']); break

        # 3) اسم المتجر ضد عنوان المصدر.
        for store in stores:
            if store in urls_map: continue
            sn=normalize_name(store)
            for rec in records:
                if rec['url'] and sn and sn in normalize_name(rec['title']) and rec['url'] not in used_urls:
                    urls_map[store]=rec['url']; used_urls.add(rec['url']); break

        # لا نستخدم مصادر عشوائية كأسماء متاجر إذا لدينا سطور عروض؛ العرض الحالي يعتمد
        # على أسماء المتاجر في النص، وsend_product_result سيقوم بالحارس النهائي للـCTA.
        print({"legacy_stores":stores,"legacy_links_pairs":pairs,
               "grounding_chunks":len(chunks),"resolved_buttons":list(urls_map)})
        return text, dict(list(urls_map.items())[:max(limit,4)])
    except Exception as e:
        print(f"LEGACY V26 Gemini err {e}")
        return "", {}


def legacy_v26_best_of_search(parts, max_results=None, merge_offers=False, merge_title=""):
    """بطولة الكود القديم: SEARCH_RUNS بالتوازي، الأفضل يفوز، والروابط اتحاد الجميع."""
    limit=MAX_STORES if max_results is None else max(1,int(max_results))
    market_snapshot=current_market()
    try:
        futs=[V26_SEARCH_POOL.submit(_run_with_market, market_snapshot,
                                     legacy_v26_call_gemini, parts,
                                     LEGACY_TEXT_SEARCH_SYSTEM, limit)
              for _ in range(SEARCH_RUNS)]
        results=_fast_tournament_results(futs, limit, GEMINI_SEARCH_TIMEOUT_SECONDS + 5)
    except Exception as e:
        print(f"LEGACY V26 best_of_search err {e}")
        return legacy_v26_call_gemini(parts, max_results=limit)
    results=[(tt,uu) for tt,uu in results if tt]
    if not results: return "",{}
    scored=sorted(results,key=lambda x:v26_answer_score(x[0],x[1],limit),reverse=True)
    best_txt,best_urls=scored[0]
    merged_urls=dict(best_urls)
    for _,u in scored[1:]:
        for n,link in u.items():
            if n not in merged_urls and link not in merged_urls.values():
                merged_urls[n]=link
    merged_urls=dict(list(merged_urls.items())[:max(limit,4)])
    if merge_offers:
        best_txt=_merge_v26_offer_text(scored, merge_title or product_title(best_txt,""), limit)
    print({"legacy_v26_tournament":[v26_answer_score(tt,uu,limit) for tt,uu in scored],
           "winner_stores":len(text77_extract_store_offers(best_txt,limit=limit)),
           "total_links":len(merged_urls),"merged_offers":bool(merge_offers)})
    return best_txt,merged_urls



US_STORE_PRIORITY = (
    ("amazon.com", "Amazon"),
    ("ebay.com", "eBay"),
    ("walmart.com", "Walmart"),
)

# Same first-search principle for the strongest Chinese global marketplaces.
CHINA_STORE_PRIORITY = (
    ("aliexpress.com", "AliExpress"),
    ("temu.com", "Temu"),
    ("alibaba.com", "Alibaba"),
    ("shein.com", "SHEIN"),
    ("dhgate.com", "DHgate"),
    ("made-in-china.com", "Made-in-China"),
    ("banggood.com", "Banggood"),
    ("1688.com", "1688"),
    ("taobao.com", "Taobao"),
    ("tmall.com", "Tmall"),
    ("jd.com", "JD"),
)


def _us_store_priority(name, url):
    """Lower = stronger priority inside the US bucket only."""
    hay = f"{name or ''} {url or ''}".lower()
    for idx, (domain, label) in enumerate(US_STORE_PRIORITY):
        if domain in hay or normalize_name(label) in normalize_name(hay):
            return idx
    return 99


def _china_store_priority(name, url):
    """Lower = stronger priority inside the China bucket only."""
    hay = f"{name or ''} {url or ''}".lower()
    for idx, (domain, label) in enumerate(CHINA_STORE_PRIORITY):
        if domain in hay or normalize_name(label) in normalize_name(hay):
            return idx
    return 99



def legacy_text_product_search(product, lang):
    """v84 typed engine: search immediately in the user's wording; translate only on failure."""
    cache_query = f"__TEXT79_MARKET_COVERAGE__::{product}"
    cached = cache_get(cache_query, lang)
    if cached:
        return cached

    m = current_market()
    market_name = m.get("country_name", "Kuwait")
    local_cc = (m.get("country") or DEFAULT_COUNTRY).lower()
    local_hl = m.get("search_hl") or country_search_hl(local_cc)
    local_currencies = ", ".join(country_currency_codes(local_cc))
    local_tlds = ", ".join(country_tlds(local_cc))
    local_stores = priority_stores_for(product)
    local_store_hint = ", ".join(local_stores[:7]) if local_stores else "the strongest specialist and marketplace stores in the country"
    total_cap = max(1, LENS_DIRECT_LOCAL_MAX + LENS_DIRECT_US_MAX + LENS_DIRECT_CN_MAX)
    soft = None

    def _attempt(primary, secondary=""):
        extra = (f" وابحث أيضاً بالاسم الآخر لنفس المنتج: {secondary}." if secondary else "")
        prompt = (
            f"ابحث عن نفس المنتج بالضبط: {primary}.{extra} "
            "إذا كان اسم المنتج مكتوباً بلغة غير لغة المتجر، افهم الاسم التجاري المكافئ تلقائياً أثناء بحث Google. "
            f"LOCAL SEARCH BOOST: في {market_name} ابحث بصياغة المستخدم + الاسم التجاري الإنجليزي + صياغة لغة السوق {local_hl}. "
            f"استخدم إشارات السوق gl={local_cc} و ccTLD={local_tlds} والعملات المحلية {local_currencies}. ابدأ بالمتاجر القوية مثل {local_store_hint} ثم وسّع للمتاجر المحلية الصغيرة المفهرسة؛ القائمة ليست whitelist. "
            f"ابحث تلقائياً في ثلاث مجموعات فقط وبالترتيب الإلزامي: "
            f"أولاً متاجر {market_name} المحلية حتى {LENS_DIRECT_LOCAL_MAX}، "
            f"ثم متاجر الولايات المتحدة حتى {LENS_DIRECT_US_MAX}، "
            f"ثم المتاجر الصينية حتى {LENS_DIRECT_CN_MAX}. "
            "بالنسبة لأمريكا: ابحث بشكل طبيعي في المتاجر الأمريكية، وإذا ظهرت نتائج مطابقة فرتبها داخل القسم الأمريكي بهذه الأولوية فقط: Amazon ثم eBay ثم Walmart ثم باقي المتاجر الأمريكية. لا تفرض ظهور أي متجر إذا لم توجد نتيجة مطابقة. "
            "بالنسبة للصين ابحث مباشرة في AliExpress وTemu وAlibaba وSHEIN عندما توجد نتيجة مطابقة، ويمكن استخدام متاجر صينية أخرى. "
            "لا تعرض أي دولة رابعة. استبعد Heureka/heureka.cz/heureka.sk نهائياً ولا تعتبره متجراً محلياً. لا تجعل الأعداد حصصاً إلزامية؛ اعرض الموجود المطابق فقط. "
            "مهم جداً: لا تنه البحث قبل فحص الأسواق الثلاثة كلها. إذا كان نفس المنتج المطابق موجوداً في السوق المحلي أو أمريكا أو الصين فيجب أن يظهر على الأقل متجر واحد من ذلك السوق؛ لا تحذف سوقاً كاملاً بسبب أن سوقاً آخر أعاد نتائج أكثر أو أسرع. "
            "لكل نتيجة اذكر اسم المتجر، اسم المنتج المطابق، السعر الرقمي والعملة، واربطه بصفحة المنتج المباشرة. "
            f"{TEXT77_lang_instr(lang)}"
        )
        return legacy_v26_best_of_search([{"text": prompt}], total_cap, True, product)

    # Fast path: no translation call before the search.
    txt, urls = _attempt(product)
    if txt and not is_no_result_answer(txt) and text77_extract_store_offers(txt, limit=total_cap):
        if urls:
            cache_put(cache_query, lang, txt, urls)
            return txt, urls
        soft = (txt, {})

    # Only if the first grounded search failed, generate an alternate-language identity and retry.
    _nonlatin = bool(re.search(r"[\u0600-\u06FF\u0900-\u097F\u3040-\u30FF\u3400-\u9FFF\u0400-\u04FF]", str(product or "")))
    if _nonlatin:
        alt = english_search_name(product) or ""
    elif local_hl == "ar":
        alt = arabic_search_name(product) or ""
    else:
        alt = ""
    if alt and alt.strip().lower() != str(product).strip().lower():
        txt2, urls2 = _attempt(alt, product)
        if txt2 and not is_no_result_answer(txt2) and text77_extract_store_offers(txt2, limit=total_cap):
            if urls2:
                cache_put(cache_query, lang, txt2, urls2)
                return txt2, urls2
            if soft is None:
                soft = (txt2, {})
    return soft or ("", {})

def v26_text_search(product, lang):
    """v76.4: توافق اسمي فقط؛ البحث النصي الفعلي صار محرك الكود المرفق من المستخدم."""
    return legacy_text_product_search(product, lang)

def execute_service_search(from_number, service_desc, original_text, bot_id, lang):
    """v74.4: مسار الخدمات — يفهم رسالة المستخدم كاملة: يجاوب على سؤاله الفني إن وجد,

    ثم يجيب 5 مزودي خدمة على الأقل بأرقام هواتف مرتبة. يستخدم بطولة v26 نفسها.
    """
    send_whatsapp_text(from_number, T(lang, "searching", q=service_desc), bot_id)
    LAST_SEARCH[from_number] = {"product": service_desc}
    market_name = current_market().get("country_name", "Kuwait")
    has_question = bool(re.search(r"[؟?]|هل |ليش |وش سبب|why |does |is it", original_text or ""))
    question_part = (
        ("رسالة المستخدم الكاملة:\n" + str(original_text or "").strip()[:600] + "\n\n"
         "أولاً: إذا في رسالته سؤال فني (مثل: هل الطفح يخرب المكينة؟) أجب عنه بإيجاز في 2-3 أسطر قبل القائمة. ")
        if has_question and original_text and original_text.strip() != service_desc.strip() else ""
    )
    prompt = (
        f"{question_part}"
        f"هذا طلب خدمة وليس منتجاً: {service_desc}. "
        f"طبق الحالة 3 بالضبط: ابحث في Google وأعطني 5 مزودي خدمة على الأقل في {market_name} "
        "مع أرقام هواتفهم الظاهرة فعلاً في نتائج البحث، مرتبين من الأعلى تقييماً. "
        "اكتب كل مزود في سطر واحد فقط بهذا الشكل الحرفي بدون أي إضافات:\n"
        "🏆 [اسم المزود] (هاتف: [الرقم]) — [المنطقة أو التقييم باختصار]\n"
        "• [اسم المزود] (هاتف: [الرقم]) — [المنطقة أو التقييم باختصار]\n"
        "بدون روابط، بدون Markdown، بدون فقرات شرح بعد القائمة. "
        f"{TEXT77_lang_instr(lang)}"
    )
    txt, urls = "", {}
    try:
        txt, urls = v26_best_of_search([{"text": prompt}])
        if not txt or is_no_result_answer(txt):
            # محاولة أخيرة باتصال مباشر قبل الاعتذار.
            txt, urls = text77_call_gemini([{"text": prompt}])
    except Exception as e:
        print(f"SERVICE SEARCH CRASH: {e}")
        txt = ""
    if not txt or is_no_result_answer(txt):
        send_whatsapp_text(from_number, T(lang, "not_found"), bot_id)
        return
    # v105: بطاقة لكل مزود + زر واتساب برسالة طلب الخدمة (الرقم يظهر كنص فقط).
    send_service_result(from_number, txt, bot_id, lang, service_desc)
    # typed service search: no automatic map


def _text_offer_item(offer, urls):
    name = str(offer.get("name") or "").strip()
    line = str(offer.get("line") or "").strip()
    url = match_url(name, urls or {}) or ""
    detail = re.sub(r"^(?:✅|🏆|•)\s*", "", line).strip()
    if name:
        detail = re.sub(rf"^{re.escape(name)}\s*(?:—|–|-)\s*", "", detail, flags=re.I).strip()
    return {"source": name, "title": detail, "link": url, "price": detail}


def _text_offer_price_and_title(detail):
    """Split a typed offer using the final dash/price segment; supports every ISO currency code."""
    text = re.sub(r"\s+", " ", str(detail or "")).strip()
    parts = re.split(r"\s+(?:—|–|-)\s+", text)
    if len(parts) >= 2 and _extract_numeric_price(parts[-1]) is not None:
        return " — ".join(parts[:-1]).strip(), parts[-1].strip()
    has_currency = bool(re.search(r"\b[A-Z]{3}\b|US\$|A\$|C\$|S\$|HK\$|NZ\$|[$€£¥￥₹₩₺₽₪₴₸₾₼฿₫₱₦₵৳₲₭₮]|د\.ك|ر\.س|د\.إ|ر\.ق|ر\.ع|د\.ب|KD\b|RMB\b", text, re.I))
    if has_currency and _extract_numeric_price(text) is not None:
        return "", text
    return text, ""


def _text_price_local(raw_price, market_rank, lang):
    """Typed-search display: local converted price + original foreign price in parentheses."""
    raw = str(raw_price or "").strip()
    if not raw:
        return ""
    local_cur = (current_market().get("currency") or "").upper().strip()
    src = detect_currency_code(raw, local_cur if market_rank == 0 else ("USD" if market_rank == 1 else "CNY" if market_rank == 2 else ""), current_market().get("country") if market_rank == 0 else ("us" if market_rank == 1 else "cn" if market_rank == 2 else ""))
    if not src:
        if market_rank == 0:
            src = local_cur
        elif market_rank == 1:
            src = "USD"
        elif market_rank == 2:
            src = "CNY"

    # Local offer: no duplicate original-price parenthesis.
    if market_rank == 0 and (not src or src == local_cur):
        return format_lens_price(raw, None, lang, local_cur or src or None)

    numeric = None
    m = re.search(r"(?<!\d)(\d+(?:[.,]\d{1,3})?)(?!\d)", raw.replace(",", ""))
    if m:
        try:
            numeric = float(m.group(1))
        except Exception:
            numeric = None
    if numeric is None:
        return raw

    converted = convert_to_local(numeric, src) if src else None
    if converted is None:
        return raw

    local_label = currency_label(lang)
    original = f"{format_price(numeric, src)} {src}"
    return f"{format_price(converted, local_cur)} {local_label} ({original})"


def send_text_lens_style_results(from_number, txt, urls, bot_id, lang, query, exclude_domains=None, exclude_urls=None, more_mode=False):
    """Typed search UI: flags + local->US->China + local-currency prices + up to two CTAs per merchant."""
    exclude_domains = {str(x).lower() for x in (exclude_domains or []) if x}
    exclude_urls = {str(x).strip() for x in (exclude_urls or []) if x}
    total_cap = MORE_TOTAL_MAX if more_mode else max(1, LENS_DIRECT_LOCAL_MAX + LENS_DIRECT_US_MAX + LENS_DIRECT_CN_MAX)
    offers = text77_extract_store_offers(txt or "", limit=max(total_cap * 2, total_cap))
    candidates = []
    for offer in offers:
        item = _text_offer_item(offer, urls)
        if not item["link"] or not item["link"].startswith(("http://", "https://")):
            continue
        _url = str(item.get("link") or "").strip()
        _dom = _more_result_domain(_url)
        if _url in exclude_urls or (_dom and _dom in exclude_domains):
            continue
        rank = result_market_rank(item)
        if rank == 99:
            print(f"TEXT UI MARKET REJECT: {item['source']} -> {item['link']}")
            continue
        item["market_rank"] = rank
        candidates.append(item)

    # Primary search remains v79. Only a missing market gets a second chance.
    if not more_mode:
        candidates = _supplement_missing_markets(candidates, query, "FIRST-TEXT")
        for _c in candidates:
            _c["market_rank"] = result_market_rank(_c)

    # Relevance must win before merchant priority. Use the existing strict AI offer filter on typed results.
    _offer_rows = [{"line": (o.get("title") or ""), "name": (o.get("source") or "")} for o in candidates]
    _tmp_urls = {(o.get("source") or ""): (o.get("link") or "") for o in candidates}
    _skip_ai_relevance = _fast_relevance_confident(query, candidates)
    _kept_rows = filter_relevant_offers(query, _offer_rows, _tmp_urls, use_ai=not _skip_ai_relevance, mode="exact")
    if _skip_ai_relevance:
        print("TEXT RELEVANCE: strong exact-token evidence -> AI filter skipped")
    _kept_keys = {(r.get("name") or "", r.get("line") or "") for r in _kept_rows}
    candidates = [o for o in candidates if ((o.get("source") or "", o.get("title") or "") in _kept_keys)]

    # نفس حارس المخزون المستخدم في Lens: نحذف المؤكد نفاده فقط، ونبقي الحالة المجهولة.
    candidates = _filter_confirmed_oos(candidates, "TEXT")

    caps = (
        {0: MORE_LOCAL_MAX, 1: MORE_US_MAX, 2: MORE_CN_MAX}
        if more_mode
        else {0: LENS_DIRECT_LOCAL_MAX, 1: LENS_DIRECT_US_MAX, 2: LENS_DIRECT_CN_MAX}
    )
    selected, merchant_counts, seen_urls = [], defaultdict(int), set()
    for rank in (0, 1, 2):
        taken = 0
        bucket = [x for x in candidates if x["market_rank"] == rank]
        if rank == 1:
            bucket.sort(key=lambda x: _us_store_priority(x.get("source"), x.get("link")))
        elif rank == 2:
            bucket.sort(key=lambda x: _china_store_priority(x.get("source"), x.get("link")))
        for item in bucket:
            try:
                host = urllib.parse.urlparse(item["link"]).netloc.lower().split(":")[0]
                host = host[4:] if host.startswith("www.") else host
            except Exception:
                host = ""
            merchant = host or normalize_name(item["source"])
            url = (item.get("link") or "").strip()
            if not merchant or url in seen_urls:
                continue
            if merchant_counts[merchant] >= RESULTS_PER_STORE_MAX:
                continue
            merchant_counts[merchant] += 1
            seen_urls.add(url)
            selected.append(item)
            taken += 1
            if taken >= caps.get(rank, 0):
                break

    if not selected:
        return False

    # Typed search already asks Google-grounded search for prices. Do not add merchant-page
    # HTTP lookups and do not shrink the result set if one line lacks a parsable price.
    priced_rows = []
    for item in selected:
        raw_title, raw_price = _text_offer_price_and_title(item["title"])
        shown_price = _text_price_local(raw_price, item["market_rank"], lang) if raw_price else ""
        priced_rows.append((item, raw_title, shown_price))

    display_titles = [raw_title or query for _, raw_title, _ in priced_rows]
    translated = display_titles  # v84: typed Gemini output is already localized; avoid a second AI round-trip
    local_cc = (current_market().get("country") or DEFAULT_COUNTRY).lower()
    rank_cc = {0: local_cc, 1: "us", 2: "cn"}

    counts = {0: 0, 1: 0, 2: 0}
    sent_items = []
    for (item, _raw_title, shown_price), shown_title in zip(priced_rows, translated):
        rank = item["market_rank"]
        flag = country_flag_emoji(rank_cc.get(rank, ""))
        store = _ui_plain_store_name(item["source"] or "", item.get("link") or "") or (U(lang, "store"))
        title = _compact_ui_title(shown_title or query)
        body = _build_compact_card_body(flag, store, title, shown_price, lang)
        if not body:
            continue
        send_whatsapp_cta(from_number, body[:1000], item["link"], bot_id, store)
        counts[rank] += 1
        sent_items.append(item)

    if not sent_items:
        return False
    LAST_SEARCH[from_number] = {"product": query}
    print(f"TEXT LENS-STYLE SENT: {len(sent_items)} CTA; per_store_cap={RESULTS_PER_STORE_MAX}; buckets={counts}; caps=5/4/4; order=local->us->cn")
    _save_more_results_state(from_number, query, bot_id, lang, "text", sent_items, reset=not more_mode)
    _send_more_results_choice(from_number, bot_id, lang)
    return True


def execute_product_search(from_number, product, bot_id, lang):
    """Typed product search: v77.7 engine + v79 Lens-like presentation.

    Searches local, US and China automatically. No global-search choice and no map.
    """
    # Do not block backend search on WhatsApp network latency.
    WORKERS.submit(send_whatsapp_text, from_number, T(lang, "searching", q=product), bot_id)
    try:
        txt, urls = v26_text_search(product, lang)
        if not txt:
            print("TEXT LEGACY V26 PATH EMPTY — no current-engine fallback by design")
    except Exception as e:
        print(f"TEXT SEARCH CRASH: {e}")
        txt, urls = "", {}
    LAST_SEARCH[from_number] = {"product": product}
    if not txt or not text77_extract_store_offers(txt, limit=30):
        send_whatsapp_text(from_number, T(lang, "not_found"), bot_id)
        return
    if not send_text_lens_style_results(from_number, txt, urls, bot_id, lang, product):
        send_whatsapp_text(from_number, T(lang, "not_found"), bot_id)
        return
    # No global-search buttons and no map for typed product searches.

# ---- v74.6: مصنّف الطلبات — ذكاء اصطناعي خالص، بدون أي قاموس -----------------
# القاموس الثابت مستحيل يغطي ملايين المنتجات (يخت، موطور مخيمات، مكينة بر...).
# القرار كله لنموذج سريع رخيص (بدون بحث + كاش + إعادة محاولة) بتعريفات وأمثلة قوية.
REQUEST_CLASSIFIER_SYSTEM = """أنت مصنف نية شراء ذكي لبوت تسوق عالمي على واتساب. المستخدم قد يكتب بالعربية أو بأي لغة مدعومة.
صنّف الرسالة بدقة وأجب بكلمة واحدة فقط بدون أي شرح: GENERIC أو SPECIFIC أو SERVICE أو NONE

المبدأ الأساسي:
- لا تحكم حسب نوع الفئة وحدها (طعام/إلكترونيات/ملابس...). افهم هل المستخدم حدّد منتجاً بعينه أم ما زال يطلب فئة عامة.
- GENERIC يعني أن العبارة تصف فئة/نوعاً عاماً ويمكن أن توجد عدة براندات أو منتجات مناسبة، لذلك الأفضل أن نعرض توصيات ذكية أولاً.
- SPECIFIC يعني أن المستخدم حدّد براند أو موديل أو SKU أو اسم منتج تجاري واضح أو وصفاً شديد التحديد يكفي للبحث عن نفس المنتج مباشرة.

GENERIC أمثلة:
شاورما دجاج، برجر دجاج، حليب، رز، ماء، قهوة، شوكولاتة، شامبو، حفاضات، مضرب تنس، حذاء تنس للأطفال، لابتوب للدراسة، سماعة بلوتوث، قلاية هوائية، عطر رجالي، سيارة عائلية، مولد كهرباء.
Chicken shawarma, tennis racket, kids tennis shoes, laptop for university, protein bar, olive oil.
إذا لم توجد ماركة/موديل واضحان وكانت هناك عدة خيارات ومنتجات محتملة، اختر GENERIC.

SPECIFIC أمثلة:
Nabil Chicken Shawarma 400g، حليب المراعي كامل الدسم 1 لتر، Pepsi 330ml، Yonex EZONE 100، Wilson Blade 98 V9، iPhone 16 Pro 256GB، Nike Vapor Pro 2 Junior، Head & Shoulders Classic Clean 400ml.
ذكر ماركة مع نوع المنتج غالباً SPECIFIC حتى لو لم يذكر المقاس، مثل: حليب المراعي، شامبو Pantene، حذاء Adidas.

SERVICE = طلب خدمة أو فني أو تصليح أو صيانة أو عامل وليس شراء منتج.
أمثلة: كهربائي، فني تكييف، سباك، بنشر متنقل، تصليح غسالة، مكافحة حشرات.

NONE = الرسالة ليست طلب شراء ولا خدمة: تحية، شكر، عتاب، مزح، اختبار، أو كلام موجه للبوت.
أمثلة: هلا، شكراً، وينك، ليش ما ترد، تمام، ok، تجربة.

قواعد الحسم:
1) لا تعتبر الطعام أو التموينات SPECIFIC تلقائياً. «شاورما دجاج» GENERIC، بينما «Nabil Chicken Shawarma 400g» SPECIFIC.
2) لا تعتبر كلمة واحدة SPECIFIC تلقائياً. «حليب» GENERIC، بينما «حليب المراعي 1 لتر» SPECIFIC.
3) إذا توجد ماركة/موديل/SKU واضح = SPECIFIC.
4) إذا الطلب فئة عامة بلا ماركة واضحة = GENERIC.
5) إذا شككت بين GENERIC وSPECIFIC ولم توجد هوية تجارية واضحة، اختر GENERIC.
6) أجب بكلمة التصنيف فقط."""

_REQUEST_CLASS_CACHE = {}
_REQUEST_CLASS_LOCK = threading.Lock()

def classify_request_type(query):
    """AI-first semantic request classification with cache and one Gemini call.

    Product intent is decided semantically by Gemini instead of hard-coded category rules.
    Only obvious service detection remains as a fast shortcut.
    """
    q = " ".join(str(query or "").split()).strip()
    if not q:
        return "SPECIFIC"
    key = re.sub(r"\s+", " ", normalize_ar(q))[:150]
    with _REQUEST_CLASS_LOCK:
        hit = _REQUEST_CLASS_CACHE.get(key)
    if hit:
        return hit

    q_norm = normalize_ar(q).lower()

    def _remember(verdict, source):
        with _REQUEST_CLASS_LOCK:
            if len(_REQUEST_CLASS_CACHE) > 3000:
                _REQUEST_CLASS_CACHE.clear()
            _REQUEST_CLASS_CACHE[key] = verdict
        print(f"REQUEST CLASSIFIER ({source}): {q!r} -> {verdict}")
        return verdict

    if is_service_request(q):
        return _remember("SERVICE", "fast-service")

    verdict = ""
    try:
        raw, _ = text77_call_gemini([{"text": q}], system=REQUEST_CLASSIFIER_SYSTEM, use_search=False)
        up = (raw or "").upper()
        for label in ("SERVICE", "GENERIC", "SPECIFIC", "NONE"):
            if re.search(rf"\b{label}\b", up):
                verdict = label
                break
    except Exception as e:
        print(f"REQUEST CLASSIFIER AI ERR: {e}")

    if not verdict:
        # Safe no-network fallback: model/SKU-like numbers usually mean a specific product.
        if re.search(r"\d", q) or len(q.split()) >= 4:
            verdict = "SPECIFIC"
        else:
            verdict = "GENERIC"
    return _remember(verdict, "one-pass-ai" if verdict else "fallback")

# كلمات الخدمة تبقى فقط
# كلمات الخدمة تبقى فقط كشبكة أمان سريعة إذا تعطل المصنف (بدون أي دور في قرار GENERIC).
SERVICE_WORDS = (
    "فني", "كهربائي", "سباك", "نجار", "حداد", "تصليح", "اصلاح", "إصلاح", "صيانه", "صيانة",
    "تركيب", "تمديد", "معلم", "مقاول", "شركه تنظيف", "شركة تنظيف", "مكافحه", "مكافحة",
    "بنشر", "ونش", "سطحه", "سطحة", "غسيل سياره", "غسيل سيارة",
    "technician", "electrician", "plumber", "repair", "maintenance",
    "installation", "cleaning company", "pest control", "towing",
)
def is_service_request(text):
    q = normalize_ar(str(text or ""))
    return any(normalize_ar(w) in q for w in SERVICE_WORDS)

COMPARE_UI = {
    "ar": {"title":"أفضل الخيارات", "overall":"الأفضل عموماً", "quality":"أفضل جودة", "value":"الأرخص", "fourth":"ميزة إضافية"},
    "en": {"title":"Best options", "overall":"Best overall", "quality":"Best quality", "value":"Cheapest", "fourth":"Notable strength"},
    "fr": {"title":"Comparatif des meilleurs choix", "overall":"Meilleur choix global", "quality":"Meilleure qualité", "value":"Meilleur rapport qualité-prix", "fourth":"Autre avantage important"},
    "es": {"title":"Comparativa de las mejores opciones", "overall":"Mejor en general", "quality":"Mejor calidad", "value":"Mejor relación calidad-precio", "fourth":"Otra ventaja importante"},
    "pt": {"title":"Comparação das melhores opções", "overall":"Melhor no geral", "quality":"Melhor qualidade", "value":"Melhor custo-benefício", "fourth":"Outra vantagem importante"},
    "tr": {"title":"En iyi seçeneklerin karşılaştırması", "overall":"Genel olarak en iyi", "quality":"En iyi kalite", "value":"En iyi fiyat-performans", "fourth":"Diğer önemli avantaj"},
    "ru": {"title":"Сравнение лучших вариантов", "overall":"Лучший в целом", "quality":"Лучшее качество", "value":"Лучшее соотношение цены и качества", "fourth":"Другое важное преимущество"},
    "zh": {"title":"最佳选择对比", "overall":"综合最佳", "quality":"品质最佳", "value":"性价比最佳", "fourth":"其他重要优势"},
    "hi": {"title":"सर्वश्रेष्ठ विकल्पों की तुलना", "overall":"कुल मिलाकर सर्वश्रेष्ठ", "quality":"सर्वश्रेष्ठ गुणवत्ता", "value":"पैसे के हिसाब से सर्वोत्तम", "fourth":"एक और महत्वपूर्ण खूबी"},
    "ur": {"title":"بہترین آپشنز کا موازنہ", "overall":"مجموعی طور پر بہترین", "quality":"بہترین معیار", "value":"قیمت کے لحاظ سے بہترین", "fourth":"ایک اور اہم خوبی"},
}

def compare_ui(lang):
    code = str(lang or "en").strip().lower().replace("_", "-").split("-")[0]
    if code in COMPARE_UI:
        return COMPARE_UI[code]
    base = COMPARE_UI["en"]
    return {k: _dynamic_translate_ui(v, code) for k, v in base.items()}


def brand_compare_system(lang):
    """Build comparison prompt in the user's UI language so Arabic labels never leak into other languages."""
    ui = compare_ui(lang)
    lang_name = language_name_en(lang)
    return f"""You are an expert product-comparison assistant similar to professional Best-Of review sites.
The user made a GENERIC product request without a specific brand. Compare 3-4 concrete options (brand + model/type) only.

CRITICAL LANGUAGE RULE:
- ALL human-readable text MUST be written ONLY in {lang_name}.
- Do not use Arabic words unless {lang_name} is Arabic.
- Brand names, model names, sizes and SKUs may remain in their normal original/Latin form.
- Never mix interface languages in the same answer.

Use EXACTLY this visible structure, with these localized labels:
⚖️ {ui['title']} [category]

🏆 {ui['overall']}: [brand + model] — [one short reason]

💎 {ui['quality']}: [brand + model] — [one short reason]

💰 {ui['value']}: [brand + model] — [one short reason]

✨ [localized criterion relevant to this category]: [brand + model] — [one short reason]

OPTIONS: [searchable brand model 1] | [searchable brand model 2] | [searchable brand model 3] | [searchable brand model 4]

Strict rules:
1) Leave one blank line between recommendations.
2) Never output store names, availability, prices or shopping-result bullets here.
3) For food, compare taste, quality, value and reviews.
4) Never repeat the same model.
5) OPTIONS is mandatory and MUST contain clean searchable product identities, preferably brand + exact model in their standard market spelling.
6) No links and no Markdown.
7) The OPTIONS line may stay in Latin script for brand/model names, but all descriptions and labels must be in {lang_name}.
"""

_COMPARE_LINE_RE = re.compile(r"^\s*(🏆|💎|💰|✨)\s*([^:：]*?)\s*[:：]\s*(.+?)(?:\s*(?:—|–|-)\s+(.*))?\s*$")

def _compare_entries_from_text(txt):
    """v105: يحوّل أسطر 🏆💎💰✨ إلى عناصر منظمة: {emoji, label, product, reason}.

    هذه العناصر تُعرض كصفوف قائمة اختيار (نوع التوصية + المنتج) بدل نص المقارنة الطويل."""
    entries = []
    for line in (txt or "").splitlines():
        m = _COMPARE_LINE_RE.match(line.strip())
        if not m:
            continue
        product = " ".join((m.group(3) or "").split()).strip()
        if not product or len(product) < 3:
            continue
        entries.append({
            "emoji": m.group(1),
            "label": " ".join((m.group(2) or "").split()).strip(),
            "product": product,
            "reason": " ".join((m.group(4) or "").split()).strip(),
        })
    return entries[:6]


def _options_from_compare_lines(txt):
    """v74.9: استرجاع ذكي — إذا Gemini نسي سطر OPTIONS نستخرج الخيارات من أسطر

    🏆💎💰✨ نفسها: النص بين النقطتين والشرطة هو (البراند + الموديل)."""
    options = []
    for e in _compare_entries_from_text(txt):
        cand = e["product"]
        if cand not in options:
            options.append(cand)
    return options[:6]


def _compare_entry_for_option(option, entries, index):
    """يطابق خيار OPTIONS مع سطر التوصية المناسب (بالاسم أولاً ثم بالترتيب)."""
    no = normalize_ar(option).lower()
    for e in entries:
        ne = normalize_ar(e["product"]).lower()
        if no and ne and (no in ne or ne in no):
            return e
    if 0 <= index < len(entries):
        return entries[index]
    return None


def _clean_pick_label(value):
    s = re.sub(r"\s+", " ", str(value or "")).strip()
    return s.strip("[](){}<>«»\"' ")


def _short_pick_title(value, max_chars=24):
    s = _clean_pick_label(value)
    if len(s) <= max_chars:
        return s
    out = []
    for word in s.split():
        candidate = " ".join(out + [word])
        if len(candidate) > max_chars:
            break
        out.append(word)
    return " ".join(out) if out else s[:max_chars].rstrip(" -_/.,")


def _recommendation_pick_search_query(original_query, picked):
    original = re.sub(r"\s+", " ", str(original_query or "")).strip()
    choice = _clean_pick_label(picked)
    if not choice:
        return original
    if not original:
        return choice
    cleaned = original
    for pat in (
        r"^\s*(?:ابي|أبي|اريد|أريد|ابغى|أبغى|احتاج|أحتاج)\s+",
        r"^\s*(?:افضل|أفضل)\s+",
        r"^\s*(?:دور لي|دوّر لي|ابحث لي|أبحث لي)\s+(?:عن\s+)?",
        r"^\s*(?:recommend|find|show me|i want|i need|best)\s+",
    ):
        cleaned = re.sub(pat, "", cleaned, flags=re.I).strip()
    if normalize_ar(choice).lower() in normalize_ar(original).lower():
        return original
    return " ".join(f"{cleaned} {choice}".split()[:24])


def ai_recommendation_pick_search_query(original_query, picked, lang="ar"):
    """Turn a recommendation-list pick into one clean product-search identity using Gemini FAST.

    Example: original='टेनिस रैकेट', picked='Yonex EZONE 100'
    -> 'Yonex EZONE 100 tennis racket'

    This is intentionally a plain/non-search AI call, so it is fast and does not perform an extra web search.
    """
    original = re.sub(r"\s+", " ", str(original_query or "")).strip()
    choice = _clean_pick_label(picked)
    if not choice:
        return original
    system = """You normalize a user's selected shopping recommendation into ONE high-precision product search query.
Return ONLY the final search query on one line, no labels, no explanation, no quotes.
Rules:
- The selected option is authoritative. Keep its exact brand and model.
- Add only the minimum product-category/context words from the original request that help shopping search accuracy.
- Remove recommendation/question words such as best, recommend, compare, I want, show me.
- Never turn it into a sentence or question.
- Never add a different model, size, gender, generation or specification unless it was explicitly present in the selected option or original request.
- Prefer the standard international/English product-category wording for search-engine accuracy while preserving brand/model exactly.
Examples:
Original: tennis racket | Pick: Yonex EZONE 100 -> Yonex EZONE 100 tennis racket
Original: chaussures de tennis homme | Pick: ASICS Solution Speed FF 3 -> ASICS Solution Speed FF 3 men's tennis shoes
Original: बच्चों का टेनिस रैकेट | Pick: Babolat Pure Aero Junior 25 -> Babolat Pure Aero Junior 25 junior tennis racket
"""
    user = f"Original generic request: {original}\nSelected recommendation: {choice}"
    try:
        txt, _ = text77_call_gemini([{"text": user}], system=system, use_search=False)
        q = re.sub(r"^[\s\"'`]+|[\s\"'`]+$", "", (txt or "").splitlines()[0].strip()) if txt else ""
        q = re.sub(r"^(?:SEARCH_QUERY|QUERY)\s*:\s*", "", q, flags=re.I).strip()
        if q and len(q) <= 180 and normalize_ar(choice).lower() in normalize_ar(q).lower():
            print(f"SMART PICK QUERY: original={original!r} picked={choice!r} -> {q!r}")
            return q
    except Exception as e:
        print(f"SMART PICK QUERY ERR: {e}")
    fallback = _recommendation_pick_search_query(original, choice)
    print(f"SMART PICK QUERY FALLBACK: {fallback!r}")
    return fallback


def _pick_description(original_query, lang="ar"):
    q = re.sub(r"\s+", " ", str(original_query or "")).strip()
    for pat in (
        r"^\s*(?:ابي|أبي|اريد|أريد|ابغى|أبغى|احتاج|أحتاج)\s+",
        r"^\s*(?:افضل|أفضل)\s+",
        r"^\s*(?:recommend|find|show me|i want|i need|best)\s+",
    ):
        q = re.sub(pat, "", q, flags=re.I).strip()
    return q[:68] or U(lang, "recommended")


def run_brand_comparison(from_number, query, bot_id, lang):
    """v77.2: مقارنة براندات بدون تكرار + مسافة سطر بين المنتجات"""
    send_whatsapp_text(from_number, T(lang, "compare_searching"), bot_id)
    lang_name = language_name_en(lang)
    prompt = (
        f"Generic shopping request: {query}\n"
        f"Current market: {current_market().get('country_name', 'Kuwait')}\n"
        f"Compare 3-4 strong concrete options for this request. Output only in {lang_name}. "
        f"{TEXT77_lang_instr(lang)}"
    )
    txt = ""
    options = []
    for attempt in (1, 2):
        txt, _ = text77_call_gemini([{"text": prompt}], system=brand_compare_system(lang))
        if not txt:
            print(f"BRAND COMPARE ATTEMPT {attempt}: empty")
            continue
        m = re.search(r"(?im)^\s*OPTIONS\s*:\s*(.+)$", txt)
        if m:
            options = [_clean_pick_label(o) for o in m.group(1).split("|") if _clean_pick_label(o)][:6]
            txt = re.sub(r"(?im)^\s*OPTIONS\s*:.*$", "", txt).strip()
        if not options:
            options = [_clean_pick_label(o) for o in _options_from_compare_lines(txt)]
            if options:
                print(f"BRAND COMPARE: OPTIONS recovered from lines -> {options}")
        if options:
            break
        print(f"BRAND COMPARE ATTEMPT {attempt}: no options")

    if not txt or not options:
        print("BRAND COMPARE FAILED -> normal search")
        return False

    # v105: لا نرسل نص المقارنة. نرسل قائمة اختيار واحدة فقط:
    #   عنوان الصف   = نوع التوصية (🏆 الأفضل عموماً / 💰 الأرخص / 💎 أفضل جودة / ✨ ...)
    #   وصف الصف     = البراند + الموديل — سبب قصير
    # هوية المنتج تبقى داخل id الصف (pickq_...) حتى يعمل الاختيار بعد إعادة التشغيل.
    entries = _compare_entries_from_text(txt)
    ui = compare_ui(lang)
    default_labels = [("🏆", ui["overall"]), ("💰", ui["value"]), ("💎", ui["quality"]), ("✨", ui["fourth"])]

    PENDING_BRAND_PICKS[from_number] = {"options": options, "original_query": query, "bot_id": bot_id, "lang": lang, "ts": time.time()}
    rows = []
    used_titles = set()
    for i, o in enumerate(options):
        clean_o = _clean_pick_label(o)
        raw_token = base64.urlsafe_b64encode(clean_o.encode("utf-8")).decode("ascii").rstrip("=")
        row_id = f"pickq_{raw_token}"
        if len(row_id) > 190:
            row_id = f"pick_{i}"
        entry = _compare_entry_for_option(clean_o, entries, i)
        if entry and entry.get("label"):
            emoji, label = entry["emoji"], entry["label"]
        else:
            emoji, label = default_labels[i] if i < len(default_labels) else ("⭐", U(lang, "recommended"))
        title = _short_pick_title(f"{emoji} {label}", 24)
        # WhatsApp لا يقبل عنوانين متطابقين في نفس القائمة.
        if title in used_titles:
            title = _short_pick_title(f"{emoji} {label} {i+1}", 24)
        used_titles.add(title)
        reason = (entry or {}).get("reason") or ""
        description = f"{clean_o} — {reason}" if reason else clean_o
        rows.append({"id": row_id, "title": title, "description": description[:72]})

    header = ""
    for line in (txt or "").splitlines():
        if line.strip().startswith("⚖️"):
            header = line.strip()
            break
    if not header:
        header = f"⚖️ {ui['title']}: {_pick_description(query, lang)}"
    body = f"{header}\n{T(lang, 'pick_prompt')}"
    send_whatsapp_list(from_number, body, rows, bot_id, T(lang, "list_button"))
    print(f"BRAND COMPARE SENT: {options}")
    return True


def run_text_global_search(phone, item):
    activate_market(phone)
    bot_id = item["bot_id"]; lang = item["lang"]; query = item["query"]
    send_whatsapp_text(phone, T(lang, "global_searching"), bot_id)
    market_name = current_market().get("country_name", "Kuwait")
    prompts = [
        f"ابحث عالمياً عن {query} في متاجر خارج {market_name} فقط. استبعد المتاجر داخل {market_name}. "
        f"ابحث في Amazon.com وeBay وAliExpress وTemu وSHEIN وWalmart وغيرها. اعرض حتى {MAX_STORES} نتائج مختلفة بسعر رقمي ورابط منتج مباشر والعملة. {TEXT77_lang_instr(lang)}",
        f"Search worldwide for {english_search_name(query) or query} outside {market_name}. Find up to {MAX_STORES} trusted international store results with numeric price, currency, and direct product page. {TEXT77_lang_instr(lang)}",
    ]
    txt, urls = "", {}
    for prompt in prompts:
        txt, urls = legacy_v26_best_of_search([{"text": prompt}], max_results=MAX_STORES)
        if txt and urls and text77_extract_store_offers(txt):
            break
    if not txt or not text77_extract_store_offers(txt):
        send_whatsapp_text(phone, T(lang, "global_none"), bot_id); return
    if not urls:
        send_whatsapp_text(phone, txt, bot_id); return
    send_product_result(phone, txt, urls, bot_id, lang, query)

def run_text_similar_search(phone, item):
    activate_market(phone)
    bot_id = item["bot_id"]; lang = item["lang"]; query = item["query"]
    send_whatsapp_text(phone, T(lang, "similar_searching"), bot_id)
    base = short_query(re.sub(r"^.*?—\s*", "", query).strip() or query) or short_query(query)
    base_other = english_search_name(base) if re.search(r"[\u0600-\u06FF]", base) else arabic_search_name(base)
    market_name = current_market().get("country_name", "Kuwait")
    prompt = (
        f"المنتج التالي غير متوفر محلياً: {base}. " + (f"الاسم الآخر: {base_other}. " if base_other else "") +
        f"ابحث بعمق في Google عن حتى {MAX_STORES} بدائل حقيقية مختلفة من نفس الفئة والاستخدام ومتوفرة الآن في متاجر {market_name} المحلية فقط. "
        "لكل نتيجة: اسم المتجر فقط — اسم البديل الفعلي — السعر الرقمي. اربط كل متجر بصفحة المنتج المباشرة. رتب الأرخص أولاً. "
        f"{TEXT77_lang_instr(lang)}"
    )
    txt, urls = legacy_v26_best_of_search([{"text": prompt}], max_results=MAX_STORES, merge_offers=True,
                                          merge_title=f"📦 بدائل مشابهة: {base}")
    local_urls = {n:u for n,u in (urls or {}).items() if u and not text77_is_foreign_result({"link":u,"source":n,"title":n})}
    if not txt or not text77_extract_store_offers(txt) or not local_urls:
        send_whatsapp_text(phone, T(lang, "similar_none"), bot_id); return
    result_type = send_product_result(phone, txt, local_urls, bot_id, lang, base)
    if result_type == "none":
        send_whatsapp_text(phone, T(lang, "similar_none"), bot_id)


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
    "bonjour", "salut", "hola", "buenosdias", "olá", "ola", "bomdia", "merhaba",
    "привет", "здравствуйте", "你好", "您好", "नमस्ते", "السلام", "السلامعلیکم",
}
THANKS_ONLY_FORMS = {
    "شكرا", "شكرًا", "شكرالك", "شكرالكم", "مشكور", "مشكورين", "تسلم", "تسلمون", "يعطيكالعافيه",
    "يعطيكمالعافيه", "جزاكاللهخير", "جزاكماللهخير", "اللهيعطيكالعافيه", "ماقصرت", "ماقصرتوا",
    "thanks", "thankyou", "thx", "thanku", "ty", "shukran",
    "merci", "gracias", "obrigado", "obrigada", "teşekkürler", "tesekkurler", "спасибо", "谢谢", "धन्यवाद", "شکریہ",
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
{\"intent\":\"search|service|greeting|thanks|chat\",\"products\":[\"اسم المنتج نظيفاً\"]}

قواعد إلزامية:
- \"search\": المستخدم يريد منتجاً. احذف التحية والدعاء والشكر وعبارات مثل (وين أحصله، أبي أشتري، دلوني). أبقِ اسم المنتج وصفاته فقط.
- افهم التعبير الإنشائي: حتى لو كانت الرسالة قصة أو شرحاً طويلاً أو وصف مشكلة، استنتج المنتج أو الخدمة المطلوبة بذكائك.
  \"عندي صراصير بالمطبخ ومتضايق منهم وايد\" -> {\"intent\":\"search\",\"products\":[\"مبيد صراصير\"]}
  \"ولدي بيدخل الجامعة ومحتار وش أشتري له يذاكر عليه\" -> {\"intent\":\"search\",\"products\":[\"لابتوب للدراسة\"]}
  \"السياره ما تشتغل الصبح وأحس البطارية خلصت\" -> {\"intent\":\"search\",\"products\":[\"خدمة تبديل بطارية سيارة\"]}
- المنتج الواحد = عنصر واحد في products حتى لو كانت الرسالة على عدة أسطر. لا تقسم الجملة الواحدة أبداً.
- عدة منتجات مختلفة فعلاً = عدة عناصر.
- \"service\": طلب فني/سباك/كهربائي/تصليح... ضع وصف الخدمة والمنطقة في products.
- \"greeting\": تحية فقط بلا طلب. products فارغة.
- \"thanks\": شكر فقط بلا طلب جديد. products فارغة.
- \"chat\": فقط إذا لم يكن في الرسالة أي منتج أو خدمة أو حاجة يمكن استنتاجها إطلاقاً.
"""

def strip_pleasantries(text):
    """v77.7: remove greetings/thanks/request filler from conversational text."""
    cleaned = _PLEASANTRY_RE.sub(" ", text or "")
    cleaned = re.sub(r"[،,.!؟?]+", " ", cleaned)
    return " ".join(cleaned.split()).strip()

def parse_user_intent(user_text, lang):
    text = (user_text or "").strip()
    compact = re.sub(r"[^\w\u0600-\u06FF]", "", normalize_ar(text))
    if compact in GREETING_ONLY_FORMS:
        return {"intent": "greeting", "products": []}
    if compact in THANKS_ONLY_FORMS:
        return {"intent": "thanks", "products": []}
    norm = normalize_ar(text)
    conversational = ("؟" in text or "?" in text or any(normalize_ar(h) in norm for h in CONVERSATIONAL_HINTS))
    if not conversational and len(text.split()) <= 7:
        return {"intent": "search", "products": extract_products(text)}
    raw, _ = text77_call_gemini([{"text": text}], system=INTENT_PARSE_SYSTEM, use_search=False)
    try:
        data = json.loads(re.search(r"\{.*\}", raw or "", flags=re.S).group(0))
        intent = str(data.get("intent") or "search").lower().strip()
        products = [str(p).strip() for p in (data.get("products") or []) if str(p).strip()]
        if intent in ("greeting", "thanks", "chat") and not products:
            return {"intent": intent, "products": []}
        if intent in ("search", "service") and products:
            return {"intent": intent, "products": products[:6]}
    except Exception:
        print(f"TEXT77 INTENT PARSE FAIL: {raw!r}")
    cleaned = strip_pleasantries(text)
    if cleaned and len(cleaned) >= 3:
        return {"intent": "search", "products": [cleaned]}
    return {"intent": "greeting" if not compact.strip() or any(g in compact for g in ("سلام", "هلا", "مرحبا")) else "chat", "products": []}

def process_text_message(message,bot_id,onboarding_checked=False):
    from_number = "unknown"
    try:
        from_number=message["from"]
        load_user_preferences(from_number)
        user_text=message["text"]["body"]

        # v105.1: every TEXT message becomes the language signal.
        # A user can move Arabic -> English -> French -> German etc. simply by typing in that language.
        # Brand/model-only text is treated as ambiguous and keeps the previous language (or phone-market default on first use).
        lang, _lang_changed = auto_language_from_text(from_number, user_text, persist=True)

        # v85.2 test command: Market Germany / Market Japan / Market Auto.
        # Handle it BEFORE phone-prefix activation, otherwise the requested override would be reset.
        market_cmd = re.match(r"^\s*market\s+(.+?)\s*$", user_text, flags=re.I)
        if market_cmd:
            target = market_cmd.group(1).strip()
            if _norm_market_name(target) in ("auto", "automatic", "phone", "default", "off"):
                m = clear_market_override(from_number)
                activate_market(from_number)
                send_whatsapp_text(
                    from_number,
                    f"✅ Market Auto — {country_flag_emoji(m.get('country'))} {m.get('country_name')} · {m.get('currency')}",
                    bot_id,
                )
                return
            cc = resolve_market_country(target)
            if not cc:
                send_whatsapp_text(from_number, f"⚠️ Unknown market: {target}. Try: Market Germany, Market Japan, Market France, or Market Auto.", bot_id)
                return
            m = set_market_override(from_number, cc)
            activate_market(from_number)
            send_whatsapp_text(
                from_number,
                f"🧪 Market Test — {country_flag_emoji(cc)} {m.get('country_name')} · {m.get('currency')}\nLocal results will now be tested for this market. Send any product.",
                bot_id,
            )
            return

        ensure_market_from_phone(from_number, persist=True)
        activate_market(from_number)
        cmd=re.sub(r"[^\w\u0600-\u06FF\u0900-\u097F]","",user_text.strip().lower())
        if cmd in ("لغة","اللغة","غيراللغة","language","lang","changelanguage","langue","idioma","mudaridioma","dil","dildeğiştir","dildegistir","язык","сменитьязык","语言","切换语言","भाषा","زبان","زبانبدلیں"):
            send_language_choice(from_number, bot_id); return
        # Language was already detected from this exact text message above.
        # The manual language selector is still available as a fallback/override.
        lang=USER_LANG.get(from_number, lang or "en")
        if is_map_command(user_text):
            send_last_search_map(from_number, bot_id, lang); return
        pend=PENDING_IMAGES.pop(from_number,None)
        if pend and pend["images"]:
            # Keep v79 image/Lens behavior untouched when text is merely a caption for a pending image.
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
            send_whatsapp_text(from_number, T(lang, "welcome_reply"), bot_id); return
        if intent == "thanks":
            send_whatsapp_text(from_number, T(lang, "thanks_reply"), bot_id); return
        if intent == "chat":
            send_whatsapp_text(from_number, T(lang, "welcome_reply"), bot_id); return
        products = [p for p in (parsed.get("products") or []) if p.strip()] or extract_products(user_text)
        if intent == "service" or is_service_request(products[0] if products else user_text):
            execute_service_search(from_number, products[0] if products else user_text, user_text, bot_id, lang); return
        if len(products)==1:
            try:
                rtype = classify_request_type(products[0])
            except Exception as e:
                print(f"TEXT77 CLASSIFY CRASH for {products[0]!r}: {e} -> fallback GENERIC"); rtype = "GENERIC"
            if rtype == "NONE":
                send_whatsapp_text(from_number, T(lang, "chat_redirect"), bot_id); return
            if rtype == "SERVICE":
                execute_service_search(from_number, products[0], user_text, bot_id, lang); return
            if rtype == "GENERIC":
                try:
                    if run_brand_comparison(from_number, products[0], bot_id, lang): return
                except Exception as e:
                    print(f"TEXT77 BRAND COMPARE CRASH: {e}")
            execute_product_search(from_number, products[0], bot_id, lang)
        else:
            run_cart_comparison(products, from_number, bot_id, lang)
    except Exception as e:
        print(f"TEXT77 PROCESS_TEXT_MESSAGE CRASH: {e} for {from_number}")
        try:
            lang = USER_LANG.get(from_number, "ar")
            send_whatsapp_text(from_number, T(lang, "not_found"), bot_id)
        except Exception:
            pass

def process_location_message(message, bot_id):
    """v81: GPS no longer controls the shopping market; phone prefix does."""
    from_number = message["from"]
    load_user_preferences(from_number)
    market = ensure_market_from_phone(from_number, persist=True)
    lang = USER_LANG.get(from_number, "ar")
    country = market.get("country_name") or market.get("country", "").upper()
    send_whatsapp_text(from_number, T(lang, "market_from_phone", country=country), bot_id)
    route_pending_after_location(from_number)


# =============================================================================
# FINDZIA WEB API — Shopify is frontend only; this Railway service remains engine
# Added without changing the existing WhatsApp routes/search behavior.
# =============================================================================

WEB_API_ENABLED = env_bool("WEB_API_ENABLED", True)

# v98 web auto-country detection.
# Prefer trusted country headers when available; otherwise resolve the browser IP once
# through a lightweight GeoIP service and cache it. Search never waits on GPS permission.
WEB_GEO_ENABLED = env_bool("WEB_GEO_ENABLED", True)
WEB_GEO_TIMEOUT_SECONDS = max(0.8, min(4.0, float(os.environ.get("WEB_GEO_TIMEOUT_SECONDS", "2.0"))))
WEB_GEO_CACHE_TTL_SECONDS = max(3600, int(os.environ.get("WEB_GEO_CACHE_TTL_SECONDS", "86400")))
WEB_GEO_PROVIDER_URL = os.environ.get("WEB_GEO_PROVIDER_URL", "https://ipwho.is/{ip}?fields=success,country_code").strip()
WEB_GEO_CACHE = {}
WEB_GEO_CACHE_LOCK = threading.Lock()

# v99: product-card images on the web are now normalized through an image proxy.
# This fixes merchants that block hotlinking and also rescues missing thumbnails
# by reading the product page's og:image/twitter:image when needed.
WEB_IMAGE_PROXY_ENABLED = env_bool("WEB_IMAGE_PROXY_ENABLED", True)
WEB_IMAGE_PROXY_TIMEOUT_SECONDS = max(3.0, min(12.0, float(os.environ.get("WEB_IMAGE_PROXY_TIMEOUT_SECONDS", "8"))))
WEB_IMAGE_PAGE_TIMEOUT_SECONDS = max(2.0, min(8.0, float(os.environ.get("WEB_IMAGE_PAGE_TIMEOUT_SECONDS", "4.5"))))
WEB_IMAGE_CACHE_TTL_SECONDS = max(3600, int(os.environ.get("WEB_IMAGE_CACHE_TTL_SECONDS", "86400")))
WEB_IMAGE_PROXY_MAX_BYTES = max(512000, min(8 * 1024 * 1024, int(os.environ.get("WEB_IMAGE_PROXY_MAX_BYTES", str(4 * 1024 * 1024)))))
WEB_IMAGE_CACHE = {}
WEB_IMAGE_CACHE_LOCK = threading.Lock()

# v101: every web shopping card must resolve to a direct product page and carry a numeric price.
WEB_STRICT_PRODUCT_PAGE = env_bool("WEB_STRICT_PRODUCT_PAGE", True)
WEB_REQUIRE_NUMERIC_PRICE = env_bool("WEB_REQUIRE_NUMERIC_PRICE", True)
WEB_REQUIRE_PRODUCT_IMAGE = env_bool("WEB_REQUIRE_PRODUCT_IMAGE", True)
WEB_VERIFY_PRODUCT_IMAGE = env_bool("WEB_VERIFY_PRODUCT_IMAGE", True)
WEB_PRODUCT_IMAGE_VERIFY_TIMEOUT_SECONDS = max(2.0, min(8.0, float(os.environ.get("WEB_PRODUCT_IMAGE_VERIFY_TIMEOUT_SECONDS", "4.0"))))
WEB_PRODUCT_VERIFY_TIMEOUT_SECONDS = max(2.5, min(8.0, float(os.environ.get("WEB_PRODUCT_VERIFY_TIMEOUT_SECONDS", "5.5"))))
WEB_PRODUCT_VERIFY_CACHE_TTL_SECONDS = max(300, int(os.environ.get("WEB_PRODUCT_VERIFY_CACHE_TTL_SECONDS", "1800")))
WEB_PRODUCT_VERIFY_CACHE = {}
WEB_PRODUCT_VERIFY_LOCK = threading.Lock()

WEB_API_MAX_QUERY_CHARS = max(40, min(500, int(os.environ.get("WEB_API_MAX_QUERY_CHARS", "220"))))
WEB_API_MAX_IMAGE_BYTES = max(512000, min(12 * 1024 * 1024, int(os.environ.get("WEB_API_MAX_IMAGE_BYTES", str(6 * 1024 * 1024)))))
WEB_API_RATE_PER_MINUTE = max(5, min(120, int(os.environ.get("WEB_API_RATE_PER_MINUTE", "30"))))
WEB_STREAM_ENABLED = env_bool("WEB_STREAM_ENABLED", True)
WEB_IMAGE_SUPPLEMENT_WEAK_MARKETS = env_bool("WEB_IMAGE_SUPPLEMENT_WEAK_MARKETS", True)
WEB_IMAGE_TARGET_LOCAL = max(1, min(LENS_DIRECT_LOCAL_MAX, int(os.environ.get("WEB_IMAGE_TARGET_LOCAL", "3"))))
WEB_IMAGE_TARGET_US = max(1, min(LENS_DIRECT_US_MAX, int(os.environ.get("WEB_IMAGE_TARGET_US", "2"))))
WEB_IMAGE_TARGET_CN = max(1, min(LENS_DIRECT_CN_MAX, int(os.environ.get("WEB_IMAGE_TARGET_CN", "2"))))
WEB_STREAM_FAST_WAVE = env_bool("WEB_STREAM_FAST_WAVE", True)
WEB_STREAM_MARKET_TIMEOUT = max(4, min(20, int(os.environ.get("WEB_STREAM_MARKET_TIMEOUT_SECONDS", "8"))))
# v96: stream store probes in true FIFO order across all markets. A fast US/China/local
# merchant can appear immediately; no market has to finish before another market is shown.
WEB_STREAM_STORE_FIFO = env_bool("WEB_STREAM_STORE_FIFO", True)
WEB_STREAM_STORE_TIMEOUT = max(4.0, min(12.0, float(os.environ.get("WEB_STREAM_STORE_TIMEOUT_SECONDS", "8"))))
WEB_STREAM_STORE_HTTP_TIMEOUT = max(3.0, min(WEB_STREAM_STORE_TIMEOUT, float(os.environ.get("WEB_STREAM_STORE_HTTP_TIMEOUT_SECONDS", "7.5"))))
WEB_STREAM_RESULTS_PER_STORE = max(1, min(2, int(os.environ.get("WEB_STREAM_RESULTS_PER_STORE", "1"))))
# v104: marketplaces can legitimately return several distinct listings for the same/similar product.
WEB_STREAM_MARKETPLACE_RESULTS_PER_STORE = max(2, min(6, int(os.environ.get("WEB_STREAM_MARKETPLACE_RESULTS_PER_STORE", "4"))))
WEB_MULTI_LISTING_MARKETPLACES = (
    "etsy.com", "ebay.com", "aliexpress.com", "temu.com", "shein.com",
    "dhgate.com", "amazon.com", "alibaba.com", "made-in-china.com", "banggood.com",
)
WEB_STREAM_IMAGE_FINAL_MIN_RESULTS = max(2, min(10, int(os.environ.get("WEB_STREAM_IMAGE_FINAL_MIN_RESULTS", "5"))))
# v97: Chinese global marketplaces are more important than the US wave on web.
# Their fast probes use normal Google organic site search first because Google Shopping
# often returns few/no cards for AliExpress/Temu/SHEIN/Alibaba-style domains.
WEB_CHINA_ORGANIC_FIRST = env_bool("WEB_CHINA_ORGANIC_FIRST", True)
WEB_CHINA_ORGANIC_TIMEOUT = max(3.0, min(WEB_STREAM_STORE_TIMEOUT, float(os.environ.get("WEB_CHINA_ORGANIC_TIMEOUT_SECONDS", "6.5"))))
WEB_CHINA_GLOBAL_MAX_STORES = max(4, min(9, int(os.environ.get("WEB_CHINA_GLOBAL_MAX_STORES", "7"))))
WEB_CHINA_ORGANIC_NUM = max(3, min(10, int(os.environ.get("WEB_CHINA_ORGANIC_NUM", "8"))))
WEB_RATE_BUCKETS = defaultdict(deque)
WEB_RATE_LOCK = threading.Lock()


def _web_request_ip(request):
    forwarded = str(request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    try:
        return request.client.host or "unknown"
    except Exception:
        return "unknown"


def _web_rate_allowed(request):
    key = _web_request_ip(request)
    now = time.time()
    with WEB_RATE_LOCK:
        q = WEB_RATE_BUCKETS[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= WEB_API_RATE_PER_MINUTE:
            return False
        q.append(now)
        if len(WEB_RATE_BUCKETS) > 5000:
            stale = [k for k, v in WEB_RATE_BUCKETS.items() if not v or now - v[-1] > 300]
            for k in stale[:1000]:
                WEB_RATE_BUCKETS.pop(k, None)
    return True


def _web_language(value):
    lang = str(value or "en").strip().lower().split("-")[0]
    return lang if lang in ("ar", "en", "fr", "es", "pt", "tr", "ru", "zh", "hi", "ur") else "en"


def _web_market(country):
    raw = str(country or "").strip()
    cc = resolve_market_country(raw) if raw else None
    cc = (cc or DEFAULT_COUNTRY).lower()
    currencies = COUNTRY_CURRENCY_CODES.get(cc) or tuple(filter(None, (COUNTRY_CURRENCIES.get(cc, ""),)))
    return {
        "country": cc,
        "country_name": COUNTRY_NAMES.get(cc, cc.upper()),
        "currency": currencies[0] if currencies else "",
        "currencies": list(currencies),
        "search_hl": COUNTRY_SEARCH_HL.get(cc, "en"),
        "tlds": list(country_tlds(cc)),
        "market_source": "web_country",
    }


def _web_market_label(rank):
    return {0: "local", 1: "us", 2: "china"}.get(rank, "other")


def _web_is_http_url(value):
    try:
        u = urllib.parse.urlparse(str(value or "").strip())
        return u.scheme in ("http", "https") and bool(u.netloc)
    except Exception:
        return False


def _web_image_cache_get(key):
    now = time.time()
    with WEB_IMAGE_CACHE_LOCK:
        item = WEB_IMAGE_CACHE.get(key)
        if item and now - float(item.get("ts") or 0) < WEB_IMAGE_CACHE_TTL_SECONDS:
            return item.get("value") or ""
    return ""


def _web_image_cache_set(key, value):
    now = time.time()
    with WEB_IMAGE_CACHE_LOCK:
        WEB_IMAGE_CACHE[key] = {"value": str(value or ""), "ts": now}
        if len(WEB_IMAGE_CACHE) > 5000:
            stale = sorted(WEB_IMAGE_CACHE.items(), key=lambda kv: kv[1].get("ts", 0))[:1000]
            for old_key, _ in stale:
                WEB_IMAGE_CACHE.pop(old_key, None)


def _web_absolute_url(base_url, value):
    raw = str(value or "").strip()
    if not raw or raw.startswith(("data:", "blob:", "javascript:")):
        return ""
    try:
        return urllib.parse.urljoin(base_url or "", raw)
    except Exception:
        return raw if _web_is_http_url(raw) else ""


def _web_extract_product_image_from_html(html, base_url):
    try:
        soup = BeautifulSoup(html or "", "html.parser")
    except Exception:
        return ""

    candidates = []
    for attrs in (
        {"property": "og:image"},
        {"property": "og:image:url"},
        {"name": "twitter:image"},
        {"property": "twitter:image"},
        {"itemprop": "image"},
    ):
        for tag in soup.find_all("meta", attrs=attrs):
            candidates.append(tag.get("content") or "")
    for link in soup.find_all("link", attrs={"rel": True}):
        rel = " ".join(link.get("rel") or []).lower()
        if rel in ("image_src", "preload"):
            href = link.get("href") or ""
            as_attr = str(link.get("as") or "").lower()
            if rel == "image_src" or as_attr == "image":
                candidates.append(href)

    for script in soup.find_all("script", attrs={"type": "application/ld+json"})[:10]:
        text = (script.string or script.get_text() or "").strip()
        if not text or 'image' not in text.lower():
            continue
        try:
            data = json.loads(text)
        except Exception:
            continue
        stack = [data]
        while stack:
            obj = stack.pop()
            if isinstance(obj, dict):
                img = obj.get("image")
                if isinstance(img, str):
                    candidates.append(img)
                elif isinstance(img, list):
                    for x in img:
                        if isinstance(x, str):
                            candidates.append(x)
                        elif isinstance(x, dict):
                            candidates.append(x.get("url") or x.get("contentUrl") or "")
                elif isinstance(img, dict):
                    candidates.append(img.get("url") or img.get("contentUrl") or "")
                stack.extend(obj.values())
            elif isinstance(obj, list):
                stack.extend(obj[:12])

    if not candidates:
        # Conservative fallback: first non-logo real image on the page.
        for img in soup.find_all("img")[:30]:
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or img.get("data-original") or ""
            alt = str(img.get("alt") or "").lower()
            classes = " ".join(img.get("class") or []).lower()
            if any(bad in (src or '').lower() for bad in ("sprite", "icon", "logo", ".svg")):
                continue
            if "logo" in alt or "logo" in classes:
                continue
            candidates.append(src)

    seen = set()
    for raw in candidates:
        url = _web_absolute_url(base_url, raw)
        if not url or url in seen:
            continue
        seen.add(url)
        low = url.lower()
        if any(x in low for x in ("logo", "icon", "sprite")):
            continue
        return url
    return ""


def _web_rescue_product_image(page_url):
    page_url = str(page_url or "").strip()
    if not _web_is_http_url(page_url):
        return ""
    cache_key = 'page:' + page_url
    cached = _web_image_cache_get(cache_key)
    if cached:
        return cached

    try:
        parsed = urllib.parse.urlparse(page_url)
        headers = dict(HEADERS)
        headers.setdefault('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8')
        headers.setdefault('Referer', f'{parsed.scheme}://{parsed.netloc}/')
        resp = requests.get(page_url, headers=headers, timeout=(2.5, WEB_IMAGE_PAGE_TIMEOUT_SECONDS), allow_redirects=True)
        if resp.status_code >= 400:
            _web_image_cache_set(cache_key, '')
            return ''
        content_type = (resp.headers.get('content-type') or '').split(';', 1)[0].strip().lower()
        if content_type.startswith('image/'):
            _web_image_cache_set(cache_key, resp.url or page_url)
            return resp.url or page_url
        html = resp.text[:400000]
        found = _web_extract_product_image_from_html(html, resp.url or page_url)
        _web_image_cache_set(cache_key, found)
        return found
    except Exception as e:
        print(f'WEB IMAGE RESCUE ERR: {page_url[:120]} -> {e.__class__.__name__}')
        _web_image_cache_set(cache_key, '')
        return ''


def _web_public_image_url(raw_url):
    raw_url = str(raw_url or '').strip()
    if not _web_is_http_url(raw_url):
        return ''
    if WEB_IMAGE_PROXY_ENABLED and PUBLIC_BASE_URL:
        return f"{PUBLIC_BASE_URL}/api/img-proxy?u={urllib.parse.quote(raw_url, safe='')}"
    return raw_url


def _web_best_card_image(primary_url='', page_url='', rescue_page=False):
    primary_url = str(primary_url or '').strip()
    page_url = str(page_url or '').strip()
    if _web_is_http_url(primary_url):
        return _web_public_image_url(primary_url)
    if rescue_page and _web_is_http_url(page_url):
        rescued = _web_rescue_product_image(page_url)
        if rescued:
            return _web_public_image_url(rescued)
    return ''


def _web_attach_best_images(rows, rescue_page=False):
    rows = list(rows or [])
    if not rows:
        return rows
    jobs = []
    with ThreadPoolExecutor(max_workers=min(6, len(rows))) as pool:
        for idx, row in enumerate(rows):
            primary = row.get('image') or row.get('thumbnail') or ''
            page_url = row.get('url') or row.get('link') or ''
            jobs.append((idx, pool.submit(_web_best_card_image, primary, page_url, rescue_page)))
        for idx, fut in jobs:
            try:
                rows[idx]['image'] = fut.result() or ''
            except Exception:
                rows[idx]['image'] = rows[idx].get('image') or ''
    return rows


def _web_build_text_items(txt, urls, lang, query):
    """Same typed-search selection logic as WhatsApp, but returns JSON cards instead of sending CTAs."""
    total_cap = max(1, LENS_DIRECT_LOCAL_MAX + LENS_DIRECT_US_MAX + LENS_DIRECT_CN_MAX)
    offers = text77_extract_store_offers(txt or "", limit=max(total_cap * 2, total_cap))
    candidates = []
    for offer in offers:
        item = _text_offer_item(offer, urls)
        if not item["link"] or not item["link"].startswith(("http://", "https://")):
            continue
        rank = result_market_rank(item)
        if rank == 99:
            continue
        item["market_rank"] = rank
        candidates.append(item)

    # Preserve v79 behavior: only supplement a market that is missing.
    candidates = _supplement_missing_markets(candidates, query, "WEB-TEXT")
    for item in candidates:
        item["market_rank"] = result_market_rank(item)
    candidates = [x for x in candidates if x.get("market_rank") in (0, 1, 2)]

    # Preserve the same relevance gate used by the WhatsApp typed flow.
    offer_rows = [{"line": (o.get("title") or ""), "name": (o.get("source") or "")} for o in candidates]
    tmp_urls = {(o.get("source") or ""): (o.get("link") or "") for o in candidates}
    skip_ai = _fast_relevance_confident(query, candidates)
    kept_rows = filter_relevant_offers(query, offer_rows, tmp_urls, use_ai=not skip_ai, mode="exact")
    kept_keys = {(r.get("name") or "", r.get("line") or "") for r in kept_rows}
    candidates = [o for o in candidates if ((o.get("source") or "", o.get("title") or "") in kept_keys)]
    candidates = _filter_confirmed_oos(candidates, "WEB-TEXT")

    caps = {0: LENS_DIRECT_LOCAL_MAX, 1: LENS_DIRECT_US_MAX, 2: LENS_DIRECT_CN_MAX}
    selected, merchant_counts, seen_urls = [], defaultdict(int), set()
    for rank in (0, 1, 2):
        bucket = [x for x in candidates if x.get("market_rank") == rank]
        if rank == 1:
            bucket.sort(key=lambda x: _us_store_priority(x.get("source"), x.get("link")))
        elif rank == 2:
            bucket.sort(key=lambda x: _china_store_priority(x.get("source"), x.get("link")))
        taken = 0
        for item in bucket:
            url = str(item.get("link") or "").strip()
            try:
                host = urllib.parse.urlparse(url).netloc.lower().split(":")[0]
                host = host[4:] if host.startswith("www.") else host
            except Exception:
                host = ""
            merchant = host or normalize_name(item.get("source") or "")
            if not merchant or not url or url in seen_urls:
                continue
            if merchant_counts[merchant] >= RESULTS_PER_STORE_MAX:
                continue
            merchant_counts[merchant] += 1
            seen_urls.add(url)
            selected.append(item)
            taken += 1
            if taken >= caps.get(rank, 0):
                break

    local_cc = (current_market().get("country") or DEFAULT_COUNTRY).lower()
    rank_cc = {0: local_cc, 1: "us", 2: "cn"}
    results = []
    for item in selected:
        rank = item["market_rank"]
        raw_title, raw_price = _text_offer_price_and_title(item.get("title") or "")
        shown_price = _text_price_local(raw_price, rank, lang) if raw_price else ""
        title = _compact_ui_title(raw_title or query)
        store = _ui_plain_store_name(item.get("source") or "", item.get("link") or "") or U(lang, "store")
        results.append({
            "market": _web_market_label(rank),
            "market_rank": rank,
            "country": rank_cc.get(rank, ""),
            "flag": country_flag_emoji(rank_cc.get(rank, "")),
            "store": store,
            "title": title,
            "price": shown_price,
            "url": item.get("link") or "",
            "image": item.get("thumbnail") or item.get("image") or "",
        })
    results = [row for row in results if _web_is_direct_product_page_url(row.get("url") or "", row.get("store") or "")]
    results = _web_attach_best_images(results, rescue_page=True)
    return _web_verify_rows_strict(results, lang)


def _web_brand_comparison(query, lang):
    """WhatsApp generic-request comparison, returned as JSON instead of a list message."""
    lang_name = language_name_en(lang)
    prompt = (
        f"Generic shopping request: {query}\n"
        f"Current market: {current_market().get('country_name', 'Kuwait')}\n"
        f"Compare 3-4 strong concrete options for this request. Output only in {lang_name}. "
        f"{TEXT77_lang_instr(lang)}"
    )
    txt, options = "", []
    for _ in (1, 2):
        txt, _urls = text77_call_gemini([{"text": prompt}], system=brand_compare_system(lang))
        if not txt:
            continue
        m = re.search(r"(?im)^\s*OPTIONS\s*:\s*(.+)$", txt)
        if m:
            options = [_clean_pick_label(o) for o in m.group(1).split("|") if _clean_pick_label(o)][:6]
            txt = re.sub(r"(?im)^\s*OPTIONS\s*:.*$", "", txt).strip()
        if not options:
            options = [_clean_pick_label(o) for o in _options_from_compare_lines(txt)]
        if options:
            break
    if not txt or not options:
        return None

    cleaned = []
    for line in txt.splitlines():
        stripped = line.strip()
        if stripped.startswith("📦") or (stripped.startswith(("✅", "•")) and "متوفر" in stripped):
            continue
        if "متوفر عبر متجر" in stripped or ("متوفر في" in stripped and "📦" in stripped):
            continue
        cleaned.append(line)
    txt = re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned)).strip()
    return {"summary": txt, "options": options}


def _web_build_lens_items(lens, lang, caption=""):
    """Same direct-Lens ranking/caps as WhatsApp, returned as structured JSON."""
    raw_matches = [m for m in (lens.get("matches") or []) if (m.get("title") or "").strip()]
    lens_for_filter = dict(lens or {})
    lens_for_filter["matches"] = raw_matches
    raw_matches = _lens_ai_relevance_filter(lens_for_filter)
    if lens_for_filter.get("relevance_target"):
        lens["relevance_target"] = lens_for_filter["relevance_target"]
    matches = [m for m in raw_matches if result_market_rank(m) != 99]
    if not matches:
        return []

    buckets = {0: [], 1: [], 2: []}
    for m in matches:
        rank = result_market_rank(m)
        if rank in buckets:
            buckets[rank].append(m)
    for rank in buckets:
        buckets[rank].sort(key=lambda m: (
            _us_store_priority(m.get("source"), m.get("link")) if rank == 1
            else (_china_store_priority(m.get("source"), m.get("link")) if rank == 2 else 99),
            0 if _lens_has_price(m) else 1,
            0 if m.get("exact") else 1,
            0 if m.get("section") == "visual_matches" else 1,
            int(m.get("position") or 999),
        ))
        cap = {0: LENS_DIRECT_LOCAL_MAX, 1: LENS_DIRECT_US_MAX, 2: LENS_DIRECT_CN_MAX}.get(rank, 0)
        probe_n = max(cap + 2, cap)
        head = _filter_confirmed_oos(buckets[rank][:probe_n], f"WEB-LENS-{rank}")
        buckets[rank] = head + buckets[rank][probe_n:]

    def merchant_key(m):
        url = (m.get("link") or "").strip()
        source = re.sub(r"\s+", " ", (m.get("source") or "").strip().lower())
        try:
            host = urllib.parse.urlparse(url).netloc.lower().split(":")[0]
            host = host[4:] if host.startswith("www.") else host
        except Exception:
            host = ""
        known = (
            "shein.com", "aliexpress.com", "temu.com", "alibaba.com", "1688.com",
            "taobao.com", "tmall.com", "amazon.com", "ubuy.com", "westelm.com",
            "hm.com", "wayfair.com",
        )
        for d in known:
            if host == d or host.endswith("." + d) or d in source:
                return d
        return host or re.sub(r"[^a-z0-9]+", "", source) or source

    caps = {0: LENS_DIRECT_LOCAL_MAX, 1: LENS_DIRECT_US_MAX, 2: LENS_DIRECT_CN_MAX}
    selected, seen_urls, merchant_counts = [], set(), defaultdict(int)
    for rank in (0, 1, 2):
        taken = 0
        for m in buckets[rank]:
            url = (m.get("link") or "").strip()
            try:
                host = urllib.parse.urlparse(url).netloc.lower()
            except Exception:
                host = ""
            if not (url.startswith("http") and host and "google." not in host):
                continue
            merchant = merchant_key(m)
            if url in seen_urls or merchant_counts[merchant] >= RESULTS_PER_STORE_MAX:
                continue
            selected.append(m)
            seen_urls.add(url)
            merchant_counts[merchant] += 1
            taken += 1
            if taken >= caps.get(rank, 0) or len(selected) >= LENS_DIRECT_MAX_CTA:
                break
        if len(selected) >= LENS_DIRECT_MAX_CTA:
            break

    selected = _fill_prices_from_existing_lens_pool(selected, raw_matches)
    display_titles = translate_ui_titles([(m.get("title") or "").strip() for m in selected], lang)
    local_cc = (current_market().get("country") or DEFAULT_COUNTRY).lower()
    rank_cc = {0: local_cc, 1: "us", 2: "cn"}
    results = []
    for m, display_title in zip(selected, display_titles):
        rank = result_market_rank(m)
        cc = rank_cc.get(rank, "")
        results.append({
            "market": _web_market_label(rank),
            "market_rank": rank,
            "country": cc,
            "flag": country_flag_emoji(cc),
            "store": _ui_plain_store_name(m.get("source") or "", m.get("link") or "") or U(lang, "store"),
            "title": _compact_ui_title(display_title or m.get("title") or ""),
            "price": _lens_price_text_local(m, rank, lang),
            "url": (m.get("link") or "").strip(),
            "image": m.get("thumbnail") or m.get("image") or "",
        })
    results = [row for row in results if _web_is_direct_product_page_url(row.get("url") or "", row.get("store") or "")]
    results = _web_attach_best_images(results, rescue_page=True)
    return _web_verify_rows_strict(results, lang)


def _web_fallback_product_items(txt, urls, lang, query):
    """Fallback for image searches that went through the full Vision/text pipeline."""
    offers = extract_store_offers(txt or "")
    rows = []
    for offer in offers:
        url = match_url(offer.get("name") or "", urls or {})
        if not is_direct_store_url(url):
            continue
        detail = re.sub(r"^(?:✅|🏆|•)\s*", "", offer.get("line") or "").strip()
        name = offer.get("name") or ""
        if name:
            detail = re.sub(rf"^{re.escape(name)}\s*(?:—|–|-)\s*", "", detail, flags=re.I).strip()
        title, raw_price = _text_offer_price_and_title(detail)
        probe = {"source": name, "title": title or detail, "link": url}
        rank = result_market_rank(probe)
        if rank not in (0, 1, 2):
            continue
        cc = (current_market().get("country") or DEFAULT_COUNTRY).lower() if rank == 0 else ("us" if rank == 1 else "cn")
        rows.append({
            "market": _web_market_label(rank),
            "market_rank": rank,
            "country": cc,
            "flag": country_flag_emoji(cc),
            "store": _ui_plain_store_name(name, url) or U(lang, "store"),
            "title": _compact_ui_title(title or query),
            "price": _text_price_local(raw_price, rank, lang) if raw_price else "",
            "url": url,
            "image": "",
        })
    rows = [row for row in rows if _web_is_direct_product_page_url(row.get("url") or "", row.get("store") or "")]
    rows = _web_attach_best_images(rows, rescue_page=True)
    rows.sort(key=lambda x: x["market_rank"])
    caps = {0: LENS_DIRECT_LOCAL_MAX, 1: LENS_DIRECT_US_MAX, 2: LENS_DIRECT_CN_MAX}
    out, counts = [], defaultdict(int)
    for row in rows:
        if counts[row["market_rank"]] >= caps[row["market_rank"]]:
            continue
        out.append(row)
        counts[row["market_rank"]] += 1
    return _web_verify_rows_strict(out, lang)



def _web_stream_event(payload):
    return (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _web_market_candidates_to_items(candidates, rank, lang, query):
    """Convert one market's SerpApi shopping wave to the same JSON card contract as /api/search."""
    seq = []
    for item in list(candidates or []):
        if result_market_rank(item) != rank:
            continue
        url = str(item.get("link") or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        seq.append(item)

    # Keep the same cheap relevance and stock gates; do not add another AI call here.
    if seq:
        offer_rows = [{"line": (x.get("title") or ""), "name": (x.get("source") or "")} for x in seq]
        tmp_urls = {(x.get("source") or ""): (x.get("link") or "") for x in seq}
        try:
            kept_rows = filter_relevant_offers(query, offer_rows, tmp_urls, use_ai=False, mode="exact")
            kept = {(r.get("name") or "", r.get("line") or "") for r in kept_rows}
            seq = [x for x in seq if ((x.get("source") or "", x.get("title") or "") in kept)]
        except Exception:
            pass
    try:
        seq = _filter_confirmed_oos(seq, f"WEB-STREAM-{rank}")
    except Exception:
        pass

    if rank == 1:
        seq.sort(key=lambda x: (_us_store_priority(x.get("source"), x.get("link")), int(x.get("position") or 999)))
    elif rank == 2:
        seq.sort(key=lambda x: (_china_store_priority(x.get("source"), x.get("link")), int(x.get("position") or 999)))
    else:
        seq.sort(key=lambda x: int(x.get("position") or 999))

    cap = {0: LENS_DIRECT_LOCAL_MAX, 1: LENS_DIRECT_US_MAX, 2: LENS_DIRECT_CN_MAX}.get(rank, 4)
    local_cc = (current_market().get("country") or DEFAULT_COUNTRY).lower()
    cc = local_cc if rank == 0 else ("us" if rank == 1 else "cn")
    out, seen_urls, merchant_counts = [], set(), defaultdict(int)
    for item in seq:
        url = str(item.get("link") or "").strip()
        try:
            host = urllib.parse.urlparse(url).netloc.lower().split(":")[0]
            host = host[4:] if host.startswith("www.") else host
        except Exception:
            host = ""
        merchant = host or normalize_name(item.get("source") or "")
        if not merchant or not url or url in seen_urls or merchant_counts[merchant] >= RESULTS_PER_STORE_MAX:
            continue
        seen_urls.add(url)
        merchant_counts[merchant] += 1
        raw_price = str(item.get("price") or "").strip()
        shown_price = _text_price_local(raw_price, rank, lang) if raw_price else ""
        out.append({
            "market": _web_market_label(rank),
            "market_rank": rank,
            "country": cc,
            "flag": country_flag_emoji(cc),
            "store": _ui_plain_store_name(item.get("source") or "", url) or U(lang, "store"),
            "title": _compact_ui_title(item.get("title") or query),
            "price": shown_price,
            "url": url,
            "image": _web_best_card_image(item.get("thumbnail") or item.get("image") or "", "", False),
        })
        if len(out) >= cap:
            break
    return _web_verify_rows_strict(out, lang)


def _web_fast_market_wave_sync(query, country, lang, rank):
    market = _web_market(country)
    MARKET_CTX.value = market
    cap = {0: LENS_DIRECT_LOCAL_MAX, 1: LENS_DIRECT_US_MAX, 2: LENS_DIRECT_CN_MAX}.get(rank, 4)
    candidates = _market_presence_fallback(query, rank, limit=max(cap + 2, cap))
    return _web_market_candidates_to_items(candidates, rank, lang, query)


def _web_stream_store_specs(query, country, rank):
    """Return independent store probes for true FIFO streaming.

    v97 launches Chinese GLOBAL marketplaces first.  Every merchant is still an
    independent task, so the UI receives whichever store actually answers first;
    no country waits for another country to finish.
    """
    market = _web_market(country)
    MARKET_CTX.value = market
    local_cc = (market.get("country") or DEFAULT_COUNTRY).lower()
    q = _shopping_clean_query(query or "")
    if rank == 0:
        specs = [("Local", "", local_cc)]
        try:
            specs.extend((label, domain, local_cc) for label, domain in local_rescue_store_specs(q, LOCAL_STORE_RESCUE_MAX))
        except Exception:
            pass
    elif rank == 1:
        # Keep the US wave intentionally small; the full engine can enrich it later.
        specs = [
            ("Amazon", "amazon.com", "us"),
            ("eBay", "ebay.com", "us"),
            ("Etsy", "etsy.com", "us"),
            ("Walmart", "walmart.com", "us"),
        ]
    else:
        # Global Chinese marketplaces first.  Domestic-China-only stores stay in the
        # slower/full engine so they do not consume the fast first-paint budget.
        specs = [
            ("AliExpress", "aliexpress.com", "us"),
            ("Temu", "temu.com", "us"),
            ("SHEIN", "shein.com", "us"),
            ("DHgate", "dhgate.com", "us"),
            ("Banggood", "banggood.com", "us"),
            ("Alibaba", "alibaba.com", "us"),
            ("Made-in-China", "made-in-china.com", "us"),
        ][:WEB_CHINA_GLOBAL_MAX_STORES]
    out, seen = [], set()
    for label, domain, gl in specs:
        key = (str(domain or "").lower(), str(gl or "").lower())
        if key in seen:
            continue
        seen.add(key)
        out.append((label, domain, gl))
    return out


def _google_organic_price_text(row):
    """Best-effort visible price from Google organic rich snippets; no extra HTTP."""
    if not isinstance(row, dict):
        return ""
    direct = str(row.get("price") or "").strip()
    if direct:
        return direct
    rich = row.get("rich_snippet") or {}
    for side in ("top", "bottom"):
        block = rich.get(side) or {}
        detected = block.get("detected_extensions") or {}
        p = detected.get("price")
        if p not in (None, ""):
            cur = str(detected.get("currency") or "").strip()
            return (f"{cur} {p}" if cur else str(p)).strip()
        ext = block.get("extensions") or []
        if isinstance(ext, list):
            joined = " | ".join(str(x) for x in ext)
            if joined:
                m = re.search(r"(?i)(?:US\$|HK\$|S\$|A\$|C\$|\$|€|£|¥|￥|AED|SAR|KWD|CNY|RMB)\s*\d[\d,.]*(?:\.\d{1,3})?|\d[\d,.]*(?:\.\d{1,3})?\s*(?:USD|CNY|RMB|EUR|GBP|KWD|AED|SAR)", joined)
                if m:
                    return m.group(0).strip()
    hay = " ".join(str(row.get(k) or "") for k in ("title", "snippet"))
    m = re.search(r"(?i)(?:US\$|HK\$|S\$|A\$|C\$|\$|€|£|¥|￥|AED|SAR|KWD|CNY|RMB)\s*\d[\d,.]*(?:\.\d{1,3})?|\d[\d,.]*(?:\.\d{1,3})?\s*(?:USD|CNY|RMB|EUR|GBP|KWD|AED|SAR)", hay)
    return m.group(0).strip() if m else ""


def _china_global_product_url(domain, url):
    """Strict direct-product-page gate for Chinese global marketplaces.

    v100: category/search/store/listing pages are never emitted as shopping cards.
    A merchant-specific positive product-page signature is required.
    """
    try:
        u = urllib.parse.urlparse(str(url or "").strip())
        host = u.netloc.lower().split(":")[0]
        host = host[4:] if host.startswith("www.") else host
        path = (u.path or "").lower()
        query = (u.query or "").lower()
        pathq = path + ("?" + query if query else "")
    except Exception:
        return False

    if not _host_matches_any(host, (domain,)):
        return False
    if not path or path == "/":
        return False

    bad_markers = (
        "/search", "/category", "/categories", "/catalog", "/collections",
        "/store/", "/stores/", "/shop/", "/shops/", "/wholesale/",
        "/products?", "/product-list", "/list/", "/listing/", "/all-products",
        "searchtext=", "searchkey=", "keyword=", "q=", "query=", "search="
    )
    if any(marker in pathq for marker in bad_markers):
        return False

    checks = {
        "aliexpress.com": lambda: bool(re.search(r"/item/(?:\d+)(?:\.html)?", path)),
        "temu.com": lambda: (
            ("/goods.html" in path and ("goods_id=" in query or "goodsid=" in query))
            or bool(re.search(r"-g-\d+", path))
            or bool(re.search(r"/goods/[^/]+", path))
        ),
        "shein.com": lambda: bool(re.search(r"(?:-p-|/product-p-)\d+", path)),
        "dhgate.com": lambda: (
            "/product/" in path
            and bool(re.search(r"(?:/|-)\d{6,}(?:\.html)?$", path))
        ),
        "banggood.com": lambda: bool(re.search(r"(?:-p-|/p-)\d+(?:\.html)?", path)),
        "alibaba.com": lambda: (
            host in ("alibaba.com", "www.alibaba.com")
            and "/product-detail/" in path
            and bool(re.search(r"(?:_|/)\d{6,}(?:\.html)?$", path))
        ),
        "made-in-china.com": lambda: (
            "/product/" in path
            and path.endswith(".html")
            and len(path.strip("/")) >= 18
        ),
    }
    checker = checks.get(domain)
    return bool(checker and checker())


def _web_marketplace_repeat_cap(domain_or_url):
    raw = str(domain_or_url or "").strip().lower()
    try:
        host = urllib.parse.urlparse(raw if "://" in raw else "https://" + raw).netloc.lower().replace("www.", "")
    except Exception:
        host = raw.replace("www.", "").split("/")[0]
    for dom in WEB_MULTI_LISTING_MARKETPLACES:
        if host == dom or host.endswith("." + dom):
            return WEB_STREAM_MARKETPLACE_RESULTS_PER_STORE
    return WEB_STREAM_RESULTS_PER_STORE


def _web_is_direct_product_page_url(url, store_name=""):
    """General web-card gate: reject obvious search/category/listing URLs."""
    raw = str(url or "").strip()
    if not _web_is_http_url(raw):
        return False
    try:
        u = urllib.parse.urlparse(raw)
        host = u.netloc.lower().split(":")[0]
        host = host[4:] if host.startswith("www.") else host
        path = (u.path or "").lower()
        query = (u.query or "").lower()
        pathq = path + ("?" + query if query else "")
    except Exception:
        return False

    china_domains = (
        "aliexpress.com", "temu.com", "shein.com", "dhgate.com",
        "banggood.com", "alibaba.com", "made-in-china.com"
    )
    for dom in china_domains:
        if host == dom or host.endswith("." + dom):
            return _china_global_product_url(dom, raw)

    # Etsy's real product pages use /listing/<numeric-id>/... . Allow those explicitly
    # before the generic listing/category rejection below.
    if host == "etsy.com" or host.endswith(".etsy.com"):
        return bool(re.search(r"/listing/\d{6,}(?:/|$)", path))

    bad = (
        "/search", "/search/", "/category", "/categories", "/collections/",
        "/catalog", "/results", "/browse", "/listing", "/list/",
        "?q=", "&q=", "search=", "query=", "keyword=", "searchterm="
    )
    if any(x in pathq for x in bad):
        return False
    if path in ("", "/"):
        return False

    if host.endswith("amazon.com"):
        return bool(re.search(r"/(?:dp|gp/product)/[a-z0-9]{8,}", path))
    if host.endswith("ebay.com"):
        return bool(re.search(r"/itm/(?:[^/]+/)?\d{8,}", path))
    if host.endswith("walmart.com"):
        return "/ip/" in path

    if len(path.strip("/")) < 6:
        return False
    nav_words = ("category", "collection", "search", "brand", "brands", "shop-all", "all-products")
    if any(word in path for word in nav_words):
        return False
    return True


def _web_market_currency(market_snapshot=None):
    m = market_snapshot or current_market()
    cc = str((m or {}).get("country") or DEFAULT_COUNTRY).lower()
    codes = COUNTRY_CURRENCY_CODES.get(cc) or tuple()
    return str((m or {}).get("currency") or (codes[0] if codes else COUNTRY_CURRENCIES.get(cc, ""))).upper().strip()


def _web_convert_to_market(value, from_currency, market_snapshot=None):
    try:
        val = float(value)
    except Exception:
        return None
    src_cur = str(from_currency or "").upper().strip()
    dst_cur = _web_market_currency(market_snapshot)
    if not src_cur or not dst_cur:
        return None
    if src_cur == dst_cur:
        return val
    rates = get_fx_rates(src_cur)
    rate = rates.get(dst_cur)
    if not rate:
        return None
    return val * float(rate)


def _web_price_local_explicit(raw_price, market_rank, lang, market_snapshot=None):
    raw = str(raw_price or "").strip()
    if not raw:
        return ""
    m = market_snapshot or current_market()
    local_cc = str((m or {}).get("country") or DEFAULT_COUNTRY).lower()
    local_cur = _web_market_currency(m)
    src = detect_currency_code(
        raw,
        local_cur if market_rank == 0 else ("USD" if market_rank == 1 else "CNY" if market_rank == 2 else ""),
        local_cc if market_rank == 0 else ("us" if market_rank == 1 else "cn" if market_rank == 2 else "")
    )
    if not src:
        src = local_cur if market_rank == 0 else ("USD" if market_rank == 1 else "CNY" if market_rank == 2 else "")

    numeric = _extract_numeric_price(raw)
    if numeric is None:
        return raw

    if market_rank == 0 and src == local_cur:
        return f"{format_price(numeric, local_cur)} {local_cur}".strip()

    converted = _web_convert_to_market(numeric, src, m)
    if converted is None:
        return raw

    original = f" ({format_price(numeric, src)} {src})" if src and src != local_cur else ""
    return f"{format_price(converted, local_cur)} {local_cur}{original}"


def _web_price_number_and_currency(text, fallback_currency=""):
    raw = str(text or "").strip()
    if not raw:
        return None, ""
    cur = detect_currency_code(raw, fallback_currency or "") or fallback_currency or ""
    # Prefer a number adjacent to a currency token when possible.
    pats = (
        r"(?:USD|US\\$|EUR|GBP|KWD|KD|SAR|AED|QAR|BHD|OMR|CNY|RMB|JPY|CAD|AUD|CHF|INR|KRW|TRY|RUB|[$€£¥￥₹₩₺₽])\\s*([0-9]+(?:[.,][0-9]{1,3})?)",
        r"([0-9]+(?:[.,][0-9]{1,3})?)\\s*(?:USD|EUR|GBP|KWD|KD|SAR|AED|QAR|BHD|OMR|CNY|RMB|JPY|CAD|AUD|CHF|INR|KRW|TRY|RUB)",
    )
    for pat in pats:
        m = re.search(pat, raw, flags=re.I)
        if m:
            try:
                val = float(m.group(1).replace(",", ""))
                if val > 0:
                    return val, cur
            except Exception:
                pass
    # Last resort only when the string itself is short and price-like.
    if len(raw) <= 50:
        m = re.search(r"(?<!\\d)([0-9]+(?:[.,][0-9]{1,3})?)(?!\\d)", raw.replace(",", ""))
        if m:
            try:
                val = float(m.group(1))
                if val > 0:
                    return val, cur
            except Exception:
                pass
    return None, cur


def _web_verified_page_snapshot(url):
    url = str(url or "").strip()
    if not _web_is_http_url(url):
        return None
    now = time.time()
    with WEB_PRODUCT_VERIFY_LOCK:
        cached = WEB_PRODUCT_VERIFY_CACHE.get(url)
        if cached and now - float(cached.get("ts") or 0) < WEB_PRODUCT_VERIFY_CACHE_TTL_SECONDS:
            return dict(cached.get("data") or {})

    data = {"ok": False, "url": url, "price": None, "currency": "", "image": "", "title": "", "is_product": False}
    try:
        parsed = urllib.parse.urlparse(url)
        headers = dict(HEADERS)
        headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.8",
            "Referer": f"{parsed.scheme}://{parsed.netloc}/",
        })
        r = requests.get(url, headers=headers, timeout=(2.5, WEB_PRODUCT_VERIFY_TIMEOUT_SECONDS), allow_redirects=True)
        final_url = str(r.url or url)
        data["url"] = final_url
        if r.status_code < 400 and r.text:
            html = r.text[:1500000]
            parsed_data = parse_product_data(html, final_url) or {}
            data["price"] = parsed_data.get("price")
            data["currency"] = str(parsed_data.get("currency") or "").upper().strip()
            data["image"] = parsed_data.get("image_url") or _web_extract_product_image_from_html(html, final_url) or ""
            data["title"] = parsed_data.get("title") or ""
            data["is_product"] = bool(parsed_data.get("is_product", True))
            data["ok"] = True

            low = re.sub(r"\\s+", " ", BeautifulSoup(html[:450000], "html.parser").get_text(" ", strip=True).lower())
            host = urllib.parse.urlparse(final_url).netloc.lower().split(":")[0]
            host = host[4:] if host.startswith("www.") else host
            # Alibaba vertical/supplier result pages can look like product URLs but are supplier listings.
            if host.endswith("alibaba.com"):
                if host not in ("alibaba.com", "www.alibaba.com"):
                    data["is_product"] = False
                supplier_listing_markers = (
                    "verified suppliers ·", "verified suppliers", "supplier lists", "results for ",
                    "latest products", "distributor  verified suppliers", "contact supplier"
                )
                marker_hits = sum(1 for x in supplier_listing_markers if x in low)
                if marker_hits >= 2:
                    data["is_product"] = False

            if WEB_STRICT_PRODUCT_PAGE and not _web_is_direct_product_page_url(final_url, ""):
                data["is_product"] = False
    except Exception as e:
        print(f"WEB PRODUCT VERIFY ERR url={url[:120]}: {e.__class__.__name__}")

    with WEB_PRODUCT_VERIFY_LOCK:
        WEB_PRODUCT_VERIFY_CACHE[url] = {"ts": now, "data": dict(data)}
        if len(WEB_PRODUCT_VERIFY_CACHE) > 4000:
            oldest = sorted(WEB_PRODUCT_VERIFY_CACHE.items(), key=lambda kv: kv[1].get("ts", 0))[:800]
            for k, _ in oldest:
                WEB_PRODUCT_VERIFY_CACHE.pop(k, None)
    return data



def _web_unproxy_image_url(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        u = urllib.parse.urlparse(raw)
        if u.path.endswith("/api/img-proxy"):
            q = urllib.parse.parse_qs(u.query)
            inner = (q.get("u") or [""])[0]
            if _web_is_http_url(inner):
                return inner
    except Exception:
        pass
    return raw if _web_is_http_url(raw) else ""


def _web_image_fetchable(value):
    """Verify that a candidate URL actually returns image bytes, not HTML/error."""
    raw = _web_unproxy_image_url(value)
    if not _web_is_http_url(raw):
        return False
    cache_key = "imgok:" + raw
    cached = _web_image_cache_get(cache_key)
    if cached in ("1", "0"):
        return cached == "1"
    ok = False
    try:
        p = urllib.parse.urlparse(raw)
        headers = dict(HEADERS)
        headers["Accept"] = "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
        headers["Referer"] = f"{p.scheme}://{p.netloc}/"
        r = requests.get(
            raw,
            headers=headers,
            timeout=(2.0, WEB_PRODUCT_IMAGE_VERIFY_TIMEOUT_SECONDS),
            stream=True,
            allow_redirects=True,
        )
        ctype = (r.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
        if r.status_code < 400 and ctype.startswith("image/"):
            first = next(r.iter_content(4096), b"")
            ok = bool(first)
    except Exception:
        ok = False
    _web_image_cache_set(cache_key, "1" if ok else "0")
    return ok


def _web_choose_verified_product_image(row, snap):
    """Prefer the actual product page image; fall back to search image only if it loads."""
    candidates = []
    if snap and snap.get("image"):
        candidates.append(str(snap.get("image") or "").strip())
    current = _web_unproxy_image_url(row.get("image") or row.get("thumbnail") or "")
    if current:
        candidates.append(current)

    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if not WEB_VERIFY_PRODUCT_IMAGE or _web_image_fetchable(candidate):
            return _web_public_image_url(candidate)
    return ""


def _web_price_pairs(text):
    """Extract ordered (value,currency) pairs from a display string."""
    raw = str(text or "")
    pairs = []
    pats = (
        r"(?i)(KWD|KD|USD|EUR|GBP|JPY|CNY|RMB|SAR|AED|QAR|BHD|OMR|CAD|AUD|CHF|INR|KRW|TRY|RUB)\s*([0-9]+(?:[.,][0-9]{1,3})?)",
        r"(?i)([0-9]+(?:[.,][0-9]{1,3})?)\s*(KWD|KD|USD|EUR|GBP|JPY|CNY|RMB|SAR|AED|QAR|BHD|OMR|CAD|AUD|CHF|INR|KRW|TRY|RUB)",
    )
    for pat_idx, pat in enumerate(pats):
        for m in re.finditer(pat, raw):
            if pat_idx == 0:
                cur, num = m.group(1), m.group(2)
            else:
                num, cur = m.group(1), m.group(2)
            cur = cur.upper()
            if cur == "KD":
                cur = "KWD"
            if cur == "RMB":
                cur = "CNY"
            try:
                val = float(num.replace(",", ""))
            except Exception:
                continue
            if val > 0:
                pairs.append((m.start(), val, cur))
    # de-duplicate overlapping regex captures and preserve display order
    unique = []
    seen = set()
    for pos, val, cur in sorted(pairs, key=lambda x: x[0]):
        key = (round(val, 6), cur)
        if key in seen:
            continue
        seen.add(key)
        unique.append((val, cur))
    return unique


def _web_normalize_existing_price_to_market(display_price, rank, lang, market_snapshot=None):
    """
    Rebuild every final web price against the CURRENT detected market.
    If a stale converted price exists, e.g. '9.176 KWD (29.99 USD)' while user is in Spain,
    prefer the parenthetical/original foreign price and recalculate EUR.
    """
    raw = str(display_price or "").strip()
    if not raw:
        return ""
    market = market_snapshot or current_market()
    local_cur = _web_market_currency(market)
    pairs = _web_price_pairs(raw)
    if not pairs:
        return raw

    # If the current local currency already exists as the leading/display price, keep
    # normalizing its format and preserve one original source amount if present.
    if pairs[0][1] == local_cur:
        local_value = pairs[0][0]
        original = next(((v, c) for v, c in pairs[1:] if c != local_cur), None)
        suffix = f" ({format_price(original[0], original[1])} {original[1]})" if original else ""
        return f"{format_price(local_value, local_cur)} {local_cur}{suffix}"

    # No local currency in the stale display. Prefer the LAST distinct currency pair;
    # this is normally the original source in parentheses from older Findzia formatting.
    source_value, source_cur = pairs[-1]
    converted = _web_convert_to_market(source_value, source_cur, market)
    if converted is None:
        # fallback to first parseable currency
        source_value, source_cur = pairs[0]
        converted = _web_convert_to_market(source_value, source_cur, market)
    if converted is None:
        return raw

    suffix = "" if source_cur == local_cur else f" ({format_price(source_value, source_cur)} {source_cur})"
    return f"{format_price(converted, local_cur)} {local_cur}{suffix}"


def _web_verify_card_strict(row, rank, lang, market_snapshot=None):
    # v102: restore the originating web market inside this worker thread.
    if market_snapshot:
        MARKET_CTX.value = dict(market_snapshot)
    row = dict(row or {})
    url = str(row.get("url") or row.get("link") or "").strip()
    if not url:
        return None

    # Reject known listing/search URLs before spending network time.
    if WEB_STRICT_PRODUCT_PAGE and not _web_is_direct_product_page_url(url, row.get("store") or row.get("source") or ""):
        print(f"WEB STRICT REJECT URL store={row.get('store') or row.get('source')} url={url[:150]}")
        return None

    snap = _web_verified_page_snapshot(url)
    if snap and snap.get("ok"):
        final_url = snap.get("url") or url
        if WEB_STRICT_PRODUCT_PAGE and not snap.get("is_product"):
            print(f"WEB STRICT REJECT PAGE store={row.get('store') or row.get('source')} url={final_url[:150]}")
            return None
        row["url"] = final_url
        row["image"] = _web_choose_verified_product_image(row, snap)
        if WEB_REQUIRE_PRODUCT_IMAGE and not row.get("image"):
            print(f"WEB STRICT REJECT NO IMAGE store={row.get('store') or row.get('source')} url={final_url[:140]}")
            return None
        if snap.get("title") and not row.get("title"):
            row["title"] = _compact_ui_title(snap.get("title"))

    # Even when the merchant page could not be parsed, never expose a broken/empty card.
    if not (snap and snap.get("ok")):
        row["image"] = _web_choose_verified_product_image(row, snap)
        if WEB_REQUIRE_PRODUCT_IMAGE and not row.get("image"):
            print(f"WEB STRICT REJECT NO IMAGE store={row.get('store') or row.get('source')} url={url[:140]}")
            return None

    # Page price is authoritative when exposed. Otherwise use a structured search/Lens price.
    page_price = snap.get("price") if snap and snap.get("ok") else None
    page_cur = str((snap or {}).get("currency") or "").upper().strip()
    if page_price not in (None, ""):
        try:
            page_price = float(page_price)
        except Exception:
            page_price = None
    if page_price and page_price > 0:
        if not page_cur:
            page_cur = _web_market_currency(market_snapshot) if rank == 0 else ("USD" if rank == 1 else "CNY")
        raw_price = f"{page_price:g} {page_cur}".strip()
        row["price"] = _web_price_local_explicit(raw_price, rank, lang, market_snapshot)
        row["price"] = _web_normalize_existing_price_to_market(row["price"], rank, lang, market_snapshot)
        row["price_verified"] = True
        row["price_source"] = "product_page"
        return row

    existing = str(row.get("price") or "").strip()
    val, cur = _web_price_number_and_currency(existing)
    if val and val > 0:
        row["price"] = _web_normalize_existing_price_to_market(existing, rank, lang, market_snapshot)
        row["price_verified"] = True
        row["price_source"] = row.get("price_source") or "search_structured_rebased"
        return row

    if WEB_REQUIRE_NUMERIC_PRICE:
        print(f"WEB STRICT REJECT NO PRICE store={row.get('store') or row.get('source')} url={url[:140]}")
        return None
    return row


def _web_verify_rows_strict(rows, lang):
    rows = list(rows or [])
    if not rows:
        return []
    market_snapshot = dict(current_market())
    print(f"WEB STRICT MARKET CONTEXT country={market_snapshot.get('country')} currency={market_snapshot.get('currency')} rows={len(rows)}")
    out = [None] * len(rows)
    with ThreadPoolExecutor(max_workers=min(6, len(rows))) as pool:
        jobs = []
        for i, row in enumerate(rows):
            rank = row.get("market_rank")
            if rank not in (0, 1, 2):
                rank = result_market_rank({"link": row.get("url") or row.get("link"), "source": row.get("store") or row.get("source"), "title": row.get("title")})
            jobs.append((i, pool.submit(_web_verify_card_strict, row, rank, lang, market_snapshot)))
        for i, fut in jobs:
            try:
                out[i] = fut.result()
            except Exception:
                out[i] = None
    return [x for x in out if x]


def _serpapi_china_global_site_request(query, label, domain, timeout_seconds=None):
    """One regular Google site-search for a Chinese global marketplace.

    This is deliberately separate per merchant so it preserves true store-level FIFO.
    It is much more tolerant than google_shopping for Chinese global marketplaces.
    """
    params = {
        "engine": "google",
        "q": f"{query} site:{domain}",
        "api_key": SERPAPI_API_KEY,
        "google_domain": "google.com",
        "gl": "us",
        "hl": "en",
        "num": WEB_CHINA_ORGANIC_NUM,
        "output": "json",
    }
    try:
        r = requests.get(
            "https://serpapi.com/search.json",
            params=params,
            timeout=(3.5, timeout_seconds or WEB_CHINA_ORGANIC_TIMEOUT),
        )
        if r.status_code >= 400:
            print(f"WEB CHINA GOOGLE HTTP {r.status_code} store={label}: {r.text[:220]}")
            return []
        data = r.json()
        if data.get("error"):
            print(f"WEB CHINA GOOGLE ERROR store={label}: {data.get('error')}")
            return []
        rows = data.get("organic_results") or []
        out = []
        for pos, row in enumerate(rows, 1):
            link = str(row.get("link") or "").strip()
            if not link or not _china_global_product_url(domain, link):
                if link:
                    print(f"WEB CHINA REJECT NON-PRODUCT store={label} url={link[:160]}")
                continue
            price_text = _google_organic_price_text(row)
            out.append({
                "title": str(row.get("title") or query).strip(),
                "link": link,
                "source": label,
                "position": int(row.get("position") or pos),
                "section": "web_china_global_google",
                "exact": False,
                "thumbnail": str(row.get("thumbnail") or "").strip(),
                "image": str(row.get("thumbnail") or "").strip(),
                "price": price_text,
                "price_value": None,
                "currency": detect_currency_code(price_text, "", "cn") if price_text else "",
                "in_stock": None,
                "condition": "",
                "_lens_country": "cn",
                "_china_fallback": True,
                "_web_global_china": True,
            })
            if len(out) >= _web_marketplace_repeat_cap(domain):
                break
        print(f"WEB CHINA GLOBAL GOOGLE store={label} -> {len(out)} result(s)")
        return out
    except Exception as e:
        print(f"WEB CHINA GLOBAL GOOGLE EXCEPTION store={label}: {e}")
        return []

def _web_store_probe_sync(query, country, lang, rank, label, domain, gl):
    """Probe one merchant and return UI cards; Chinese globals use organic-first in v97."""
    market = _web_market(country)
    MARKET_CTX.value = market
    q = _shopping_clean_query(query or "")
    if not q or not SERPAPI_API_KEY:
        return []

    candidate_cc = (market.get("country") or DEFAULT_COUNTRY).lower() if rank == 0 else ("us" if rank == 1 else "cn")
    candidates = []

    # v97: for Chinese global marketplaces, ordinary Google site search is the fast
    # first path.  Google Shopping site: queries are too sparse for these domains.
    if rank == 2 and domain and WEB_CHINA_ORGANIC_FIRST:
        candidates = _serpapi_china_global_site_request(
            q, label, domain, timeout_seconds=WEB_CHINA_ORGANIC_TIMEOUT
        )
        # Do not chain a second SerpApi request inside the fast FIFO task.  Other China
        # merchants are already running in parallel, and the full engine can enrich later.
        # This prevents timed-out to_thread work from continuing in the background.
        rows = _web_market_candidates_to_items(candidates, rank, lang, q)
        return rows[:_web_marketplace_repeat_cap(domain)]

    # Existing Shopping path remains unchanged for local/US.
    if not candidates:
        search_q = f"{q} site:{domain}" if domain else q
        hl = country_search_hl(gl) if rank == 0 else "en"
        cards = _serpapi_shopping_request(
            search_q,
            gl,
            hl=hl,
            timeout_seconds=WEB_STREAM_STORE_HTTP_TIMEOUT,
        )
        for card in cards or []:
            item = _shopping_card_to_market_item(card, label, candidate_cc)
            if not item:
                continue
            if domain:
                try:
                    host = urllib.parse.urlparse(item.get("link") or "").netloc.lower().replace("www.", "")
                except Exception:
                    host = ""
                if not _host_matches_any(host, (domain,)):
                    continue
            if result_market_rank(item) != rank:
                continue
            candidates.append(item)

    rows = _web_market_candidates_to_items(candidates, rank, lang, q)
    rows = [row for row in rows if _web_is_direct_product_page_url(row.get("url") or "", row.get("store") or label)]
    cap = _web_marketplace_repeat_cap(domain)
    if cap > WEB_STREAM_RESULTS_PER_STORE and rows:
        print(f"WEB MARKETPLACE MULTI store={label} cap={cap} rows={len(rows)}")
    return rows[:cap]

def _web_image_seed_sync(image_b64, mime, caption, country, lang):
    """One fast image-identification pass used before merchant FIFO probes.

    It deliberately does not run the heavy weak-market supplement.  The stream endpoint
    performs merchant probes independently, so the first available store is not held up.
    """
    market = _web_market(country)
    MARKET_CTX.value = market
    caption = re.sub(r"\s+", " ", str(caption or "")).strip()[:WEB_API_MAX_QUERY_CHARS]
    if LENS_DIRECT_MODE and ENABLE_GOOGLE_LENS and SERPAPI_API_KEY and PUBLIC_BASE_URL:
        try:
            lens = google_lens_lookup(image_b64, mime, lang, caption, light=True)
        except Exception as e:
            print(f"WEB IMAGE FIFO LENS SEED ERR: {e}")
            lens = {"matches": [], "query": ""}
        items = _web_build_lens_items(lens, lang, caption) if lens.get("matches") else []
        identity = (lens.get("visual_identity") or lens.get("relevance_target") or lens.get("query") or caption or "").strip()
        if identity or items:
            return {"query": identity or caption, "items": items, "market": market, "source": "lens_seed"}
    try:
        identity = identify_product_with_retry(image_b64, mime, lang) or caption
    except Exception:
        identity = caption
    return {"query": str(identity or caption or "").strip(), "items": [], "market": market, "source": "vision_seed"}


def _web_prepare_stream_query_sync(query, country, lang, selected_option="", original_query="", force_specific=False):
    market = _web_market(country)
    MARKET_CTX.value = market
    q = re.sub(r"\s+", " ", str(query or "")).strip()[:WEB_API_MAX_QUERY_CHARS]
    if selected_option:
        q = ai_recommendation_pick_search_query(original_query or q, selected_option, lang)
        force_specific = True
    if not q:
        return {"ok": False, "error": "empty_query", "market": market, "query": q}
    try:
        parsed = parse_user_intent(q, lang)
        products = [p for p in (parsed.get("products") or []) if str(p).strip()]
        if len(products) == 1:
            q = products[0]
    except Exception:
        pass
    rtype = "SPECIFIC"
    if not force_specific:
        try:
            rtype = classify_request_type(q)
        except Exception:
            rtype = "SPECIFIC"
    return {"ok": True, "query": q, "market": market, "rtype": rtype, "force_specific": force_specific}

def _web_search_text_sync(query, country, lang, selected_option="", original_query="", force_specific=False):
    market = _web_market(country)
    MARKET_CTX.value = market
    q = re.sub(r"\s+", " ", str(query or "")).strip()[:WEB_API_MAX_QUERY_CHARS]
    if selected_option:
        q = ai_recommendation_pick_search_query(original_query or q, selected_option, lang)
        force_specific = True
    if not q:
        return {"ok": False, "error": "empty_query"}

    # Keep the conversational parser so web and WhatsApp understand natural requests similarly.
    try:
        parsed = parse_user_intent(q, lang)
        products = [p for p in (parsed.get("products") or []) if str(p).strip()]
        if len(products) == 1:
            q = products[0]
    except Exception:
        pass

    if not force_specific:
        try:
            rtype = classify_request_type(q)
        except Exception:
            rtype = "SPECIFIC"
        if rtype == "GENERIC":
            comparison = _web_brand_comparison(q, lang)
            if comparison:
                return {
                    "ok": True,
                    "type": "recommendations",
                    "query": q,
                    "market": market,
                    "comparison": comparison["summary"],
                    "options": comparison["options"],
                }
        elif rtype == "SERVICE":
            return {"ok": False, "type": "service", "error": "service_search_not_enabled_on_web_yet", "query": q, "market": market}
        elif rtype == "NONE":
            return {"ok": False, "type": "chat", "error": "not_a_product_query", "query": q, "market": market}

    txt, urls = v26_text_search(q, lang)
    if not txt or not text77_extract_store_offers(txt, limit=30):
        return {"ok": True, "type": "results", "query": q, "market": market, "results": []}
    results = _web_build_text_items(txt, urls, lang, q)
    return {"ok": True, "type": "results", "query": q, "market": market, "results": results}


def _web_search_image_sync(image_b64, mime, caption, country, lang):
    market = _web_market(country)
    MARKET_CTX.value = market
    caption = re.sub(r"\s+", " ", str(caption or "")).strip()[:WEB_API_MAX_QUERY_CHARS]

    # First preserve the exact v79 fast direct-Lens path.
    direct_attempted = False
    if LENS_DIRECT_MODE and ENABLE_GOOGLE_LENS and SERPAPI_API_KEY and PUBLIC_BASE_URL:
        direct_attempted = True
        lens_direct = google_lens_lookup(image_b64, mime, lang, caption, light=True)
        if lens_direct.get("matches"):
            items = _web_build_lens_items(lens_direct, lang, caption)
            if items:
                identity = (lens_direct.get("visual_identity") or lens_direct.get("relevance_target") or lens_direct.get("query") or caption or "").strip()

                # v89: Direct Lens can be excellent but uneven by market.  Do not stop the
                # web search merely because *some* Lens cards exist.  WhatsApp often has a
                # richer pool after its market/rescue layers, so the website now fills weak
                # LOCAL / US / CHINA buckets before returning while preserving Lens first.
                if WEB_IMAGE_SUPPLEMENT_WEAK_MARKETS and identity:
                    target = {0: WEB_IMAGE_TARGET_LOCAL, 1: WEB_IMAGE_TARGET_US, 2: WEB_IMAGE_TARGET_CN}
                    counts = {0: 0, 1: 0, 2: 0}
                    for row in items:
                        r = row.get("market_rank")
                        if r in counts:
                            counts[r] += 1

                    weak = [r for r in (0, 1, 2) if counts[r] < target[r]]
                    if weak:
                        print(f"WEB IMAGE v89 weak markets before supplement counts={counts} target={target} identity={identity[:90]!r}")
                        market_snapshot = dict(market)
                        extra_by_rank = {}

                        def _supp(rank):
                            MARKET_CTX.value = market_snapshot
                            try:
                                return rank, _web_fast_market_wave_sync(identity, country, lang, rank)
                            except Exception as e:
                                print(f"WEB IMAGE SUPPLEMENT ERR rank={rank}: {e}")
                                return rank, []

                        with ThreadPoolExecutor(max_workers=max(1, len(weak))) as ex:
                            futs = [ex.submit(_supp, r) for r in weak]
                            for fut in futs:
                                try:
                                    rank, rows = fut.result(timeout=SERPAPI_TIMEOUT_SECONDS + 5)
                                    extra_by_rank[rank] = rows or []
                                except Exception as e:
                                    print(f"WEB IMAGE SUPPLEMENT FUTURE ERR: {e}")

                        seen_urls = {str(x.get("url") or "").strip() for x in items if str(x.get("url") or "").strip()}
                        seen_sig = {(str(x.get("store") or "").strip().lower(), normalize_name(x.get("title") or "")) for x in items}
                        for rank in (0, 1, 2):
                            need = max(0, target[rank] - counts[rank])
                            if need <= 0:
                                continue
                            for row in extra_by_rank.get(rank, []):
                                url = str(row.get("url") or "").strip()
                                sig = (str(row.get("store") or "").strip().lower(), normalize_name(row.get("title") or ""))
                                if (url and url in seen_urls) or sig in seen_sig:
                                    continue
                                items.append(row)
                                if url:
                                    seen_urls.add(url)
                                seen_sig.add(sig)
                                counts[rank] += 1
                                need -= 1
                                if need <= 0:
                                    break
                        items.sort(key=lambda x: (int(x.get("market_rank", 99)), 0 if x.get("price") else 1))
                        print(f"WEB IMAGE v89 after supplement counts={counts} total={len(items)}")

                return {"ok": True, "type": "results", "query": identity, "market": market, "results": items, "source": "lens_direct_plus_market_supplement"}

    # Full Vision/Lens fusion fallback mirrors process_single_image, but returns JSON.
    lens_future = None
    if (not direct_attempted and LENS_PARALLEL_WITH_VISION and ENABLE_GOOGLE_LENS and SERPAPI_API_KEY and PUBLIC_BASE_URL):
        lens_future = LENS_POOL.submit(_run_with_market, market, google_lens_lookup, image_b64, mime, lang, caption)

    vision_name = identify_product_with_retry(image_b64, mime, lang)
    force_fashion_lens = is_fashion_identity(vision_name, caption)
    use_lens, _route_reason = lens_routing_decision(vision_name, caption)
    use_lens = force_fashion_lens or use_lens
    if direct_attempted:
        use_lens = False

    lens = {"aliases": [], "matches": [], "query": ""}
    if use_lens:
        if lens_future is not None:
            try:
                lens = lens_future.result(timeout=LENS_TOTAL_TIMEOUT_SECONDS + 5) or lens
            except Exception:
                pass
        else:
            lens = google_lens_lookup(image_b64, mime, lang, caption or vision_name)
    elif lens_future is not None:
        lens_future.cancel()

    active_lens = None
    combined_name = vision_name
    lens_title = ((lens.get("chosen") or {}).get("title") or lens.get("query") or "").strip()
    if use_lens:
        if force_fashion_lens and lens_title:
            lens["force_lens_only"] = True
            combined_name = " | ".join(fuse_identity_aliases(lens_title, "", lens.get("aliases")))
            active_lens = lens
        elif lens_title and vision_name:
            if identity_candidates_agree(vision_name, lens_title):
                combined_name = " | ".join(fuse_identity_aliases(lens_title, vision_name))
                active_lens = lens
            else:
                judged_name, active_lens, _identity_source = choose_image_identity(image_b64, mime, lens, vision_name)
                combined_name = " | ".join(fuse_identity_aliases(judged_name, vision_name)) if active_lens else judged_name
        elif lens_title:
            combined_name = " | ".join(fuse_identity_aliases(lens_title, "", lens.get("aliases")))
            active_lens = lens

    if combined_name and caption:
        request_query = f"{caption} — {combined_name}"
        prompt_text = (
            f"هوية المنتج المعتمدة: {combined_name}\n"
            f"طلب المستخدم: {caption}\n"
            "ابحث عن نفس المنتج فقط. لا توسع البحث إلى منتج يشاركه المكون أو اللون أو الفئة. "
            f"{lang_instr(lang)}"
        )
        txt, urls = search_product(request_query, lang, prompt_text=prompt_text, lens_context=active_lens)
        query = request_query
    elif combined_name:
        txt, urls = search_product(combined_name, lang, lens_context=active_lens)
        query = combined_name
    else:
        txt, urls, query = "", {}, caption

    if not txt:
        return {"ok": True, "type": "results", "query": query, "market": market, "results": [], "source": "image_fallback"}
    items = _web_fallback_product_items(txt, urls, lang, query)
    return {"ok": True, "type": "results", "query": query, "market": market, "results": items, "source": "image_fallback"}



def _web_normalize_country_code(value):
    cc = str(value or "").strip().lower()
    if len(cc) == 2 and cc in COUNTRY_META:
        return cc
    return ""


def _web_client_ip(request: Request):
    """Best-effort original browser IP behind Railway/proxies."""
    for header in ("cf-connecting-ip", "true-client-ip", "x-real-ip"):
        value = str(request.headers.get(header) or "").strip()
        if value:
            return value.split(",")[0].strip()
    forwarded = str(request.headers.get("x-forwarded-for") or "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    try:
        return str(request.client.host or "").strip()
    except Exception:
        return ""


def _web_country_from_headers(request: Request):
    """Use a proxy/CDN country header when one exists; this costs zero network time."""
    for header in (
        "cf-ipcountry",
        "x-vercel-ip-country",
        "cloudfront-viewer-country",
        "x-country-code",
        "x-geo-country",
    ):
        cc = _web_normalize_country_code(request.headers.get(header))
        if cc:
            return cc, "header:" + header
    return "", ""


def _web_geo_country_from_ip(ip):
    ip = str(ip or "").strip()
    if not WEB_GEO_ENABLED or not ip:
        return "", "disabled"
    # Ignore obvious local/private addresses.
    if ip in ("127.0.0.1", "::1") or ip.startswith(("10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.", "172.2", "172.30.", "172.31.")):
        return "", "private_ip"

    now = time.time()
    with WEB_GEO_CACHE_LOCK:
        cached = WEB_GEO_CACHE.get(ip)
        if cached and now - cached.get("ts", 0) < WEB_GEO_CACHE_TTL_SECONDS:
            return cached.get("country", ""), "cache"

    cc = ""
    try:
        url = WEB_GEO_PROVIDER_URL.format(ip=urllib.parse.quote(ip, safe=":."))
        r = requests.get(url, timeout=(1.0, WEB_GEO_TIMEOUT_SECONDS), headers=HEADERS)
        if r.ok:
            data = r.json() if r.content else {}
            if data.get("success", True) is not False:
                cc = _web_normalize_country_code(data.get("country_code") or data.get("countryCode"))
    except Exception as e:
        print(f"WEB GEO LOOKUP ERR ip={ip[:32]!r}: {e.__class__.__name__}")

    with WEB_GEO_CACHE_LOCK:
        WEB_GEO_CACHE[ip] = {"country": cc, "ts": now}
        if len(WEB_GEO_CACHE) > 5000:
            # Cheap bounded cache cleanup.
            oldest = sorted(WEB_GEO_CACHE.items(), key=lambda kv: kv[1].get("ts", 0))[:1000]
            for key, _ in oldest:
                WEB_GEO_CACHE.pop(key, None)
    return cc, "ipwhois" if cc else "fallback"


def _web_resolve_request_country(request: Request, supplied_country=""):
    """
    Explicit frontend country wins when valid.
    Otherwise: proxy country header -> IP GeoIP -> DEFAULT_COUNTRY.
    """
    supplied = str(supplied_country or "").strip().lower()
    if supplied and supplied not in ("auto", "detect", "xx"):
        cc = _web_normalize_country_code(supplied)
        if cc:
            return cc, "supplied"

    cc, source = _web_country_from_headers(request)
    if cc:
        return cc, source

    cc, source = _web_geo_country_from_ip(_web_client_ip(request))
    if cc:
        return cc, source

    return _web_normalize_country_code(DEFAULT_COUNTRY) or "kw", "default"


@app.get("/api/geo")
async def web_api_geo(request: Request):
    if not WEB_API_ENABLED:
        return Response(content=json.dumps({"ok": False, "error": "web_api_disabled"}), media_type="application/json", status_code=503)

    header_cc, header_source = _web_country_from_headers(request)
    if header_cc:
        cc, source = header_cc, header_source
    else:
        cc, source = await asyncio.to_thread(_web_geo_country_from_ip, _web_client_ip(request))
        if not cc:
            cc, source = _web_normalize_country_code(DEFAULT_COUNTRY) or "kw", "default"

    currencies = COUNTRY_CURRENCY_CODES.get(cc) or tuple()
    return {
        "ok": True,
        "country": cc.upper(),
        "country_code": cc,
        "country_name": COUNTRY_NAMES.get(cc, cc.upper()),
        "currency": currencies[0] if currencies else COUNTRY_CURRENCIES.get(cc, ""),
        "source": source,
    }


@app.get("/api/img-proxy")
async def web_api_img_proxy(request: Request):
    if not WEB_API_ENABLED or not WEB_IMAGE_PROXY_ENABLED:
        return Response(content=b"", status_code=404)
    raw_url = str(request.query_params.get('u') or '').strip()
    if not _web_is_http_url(raw_url):
        return Response(content=b"", status_code=400)

    def _fetch_image(target_url):
        parsed = urllib.parse.urlparse(target_url)
        headers = dict(HEADERS)
        headers['Accept'] = 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'
        headers['Referer'] = f'{parsed.scheme}://{parsed.netloc}/'
        resp = requests.get(target_url, headers=headers, timeout=(2.5, WEB_IMAGE_PROXY_TIMEOUT_SECONDS), stream=True, allow_redirects=True)
        if resp.status_code >= 400:
            return resp.status_code, '', b'', ''
        content_type = (resp.headers.get('content-type') or '').split(';', 1)[0].strip().lower()
        body = b''
        if content_type.startswith('image/'):
            chunks = []
            total = 0
            for chunk in resp.iter_content(65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > WEB_IMAGE_PROXY_MAX_BYTES:
                    break
                chunks.append(chunk)
            body = b''.join(chunks)
            return 200, content_type or 'image/jpeg', body, ''
        try:
            html = resp.text[:400000]
        except Exception:
            html = ''
        return 200, content_type or 'text/html', b'', html

    try:
        status, content_type, body, html = await asyncio.to_thread(_fetch_image, raw_url)
        if status >= 400:
            return Response(content=b"", status_code=status)
        if content_type.startswith('image/') and body:
            return Response(content=body, media_type=content_type, headers={'Cache-Control': 'public, max-age=86400'})

        rescued = _web_extract_product_image_from_html(html, raw_url) if html else ''
        if rescued and rescued != raw_url:
            status2, content_type2, body2, _ = await asyncio.to_thread(_fetch_image, rescued)
            if status2 < 400 and content_type2.startswith('image/') and body2:
                return Response(content=body2, media_type=content_type2, headers={'Cache-Control': 'public, max-age=86400'})
    except Exception as e:
        print(f'WEB IMG PROXY ERR: {raw_url[:120]} -> {e.__class__.__name__}')
    return Response(content=b"", status_code=404)


@app.get("/api/health")
async def web_api_health():
    return {"ok": True, "web_api": WEB_API_ENABLED, "build": BUILD_ID, "lens": bool(ENABLE_GOOGLE_LENS and SERPAPI_API_KEY)}



@app.post("/api/search/stream")
async def web_api_search_stream(request: Request):
    if not WEB_API_ENABLED or not WEB_STREAM_ENABLED:
        return Response(content=json.dumps({"ok": False, "error": "web_stream_disabled"}), media_type="application/json", status_code=503)
    if not _web_rate_allowed(request):
        return Response(content=json.dumps({"ok": False, "error": "rate_limit"}), media_type="application/json", status_code=429)
    try:
        payload = await request.json()
    except Exception:
        return Response(content=json.dumps({"ok": False, "error": "invalid_json"}), media_type="application/json", status_code=400)

    query = str(payload.get("query") or "").strip()
    if not query and not payload.get("selected_option"):
        return Response(content=json.dumps({"ok": False, "error": "empty_query"}), media_type="application/json", status_code=400)
    lang = _web_language(payload.get("lang"))
    country, country_source = await asyncio.to_thread(_web_resolve_request_country, request, payload.get("country"))
    selected_option = str(payload.get("selected_option") or "").strip()
    original_query = str(payload.get("original_query") or "").strip()
    force_specific = bool(payload.get("force_specific"))

    async def _generator():
        started = time.time()
        yield _web_stream_event({"event": "start", "ok": True, "elapsed_ms": 0})
        try:
            prep = await asyncio.to_thread(
                _web_prepare_stream_query_sync, query, country, lang, selected_option, original_query, force_specific
            )
            if not prep.get("ok"):
                yield _web_stream_event({"event": "error", "error": prep.get("error") or "bad_query"})
                return
            q = prep["query"]
            market = prep["market"]
            rtype = prep.get("rtype") or "SPECIFIC"
            yield _web_stream_event({"event": "query", "query": q, "market": market})

            if rtype == "GENERIC" and not force_specific:
                result = await asyncio.to_thread(_web_search_text_sync, q, country, lang, "", "", False)
                yield _web_stream_event({"event": "recommendations", "data": result, "elapsed_ms": int((time.time()-started)*1000)})
                yield _web_stream_event({"event": "done", "elapsed_ms": int((time.time()-started)*1000)})
                return
            if rtype == "SERVICE":
                yield _web_stream_event({"event": "error", "error": "service_search_not_enabled_on_web_yet"})
                return
            if rtype == "NONE":
                yield _web_stream_event({"event": "error", "error": "not_a_product_query"})
                return

            sent = set()
            final_task = asyncio.create_task(asyncio.to_thread(
                _web_search_text_sync, q, country, lang, "", "", True
            ))

            if WEB_STREAM_STORE_FIFO and WEB_STREAM_FAST_WAVE and SERPAPI_API_KEY:
                store_tasks = []
                task_meta = {}
                rank_remaining = {0: 0, 1: 0, 2: 0}
                for rank in (2, 0, 1):
                    for label, domain, gl in _web_stream_store_specs(q, country, rank):
                        async def _run_store(r=rank, lab=label, dom=domain, search_gl=gl):
                            try:
                                rows = await asyncio.wait_for(
                                    asyncio.to_thread(_web_store_probe_sync, q, country, lang, r, lab, dom, search_gl),
                                    timeout=WEB_STREAM_STORE_TIMEOUT,
                                )
                                return r, lab, rows
                            except Exception as e:
                                print(f"WEB STORE FIFO ERR rank={r} store={lab}: {e}")
                                return r, lab, []
                        task = asyncio.create_task(_run_store())
                        store_tasks.append(task)
                        task_meta[task] = (rank, label)
                        rank_remaining[rank] += 1

                pending = set(store_tasks)
                loop = asyncio.get_running_loop()
                deadline = loop.time() + WEB_STREAM_STORE_TIMEOUT
                while pending:
                    remaining = deadline - loop.time()
                    if remaining <= 0:
                        break
                    done, pending = await asyncio.wait(
                        pending,
                        timeout=min(0.12, remaining),
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in done:
                        rank, label = task_meta.get(task, (99, "Store"))
                        try:
                            r, label, items = await task
                        except Exception:
                            r, items = rank, []
                        market_name = _web_market_label(r)
                        for item in items or []:
                            key = str(item.get("url") or "").strip() or (market_name + "|" + str(item.get("store") or "") + "|" + str(item.get("title") or ""))
                            if key in sent:
                                continue
                            sent.add(key)
                            yield _web_stream_event({
                                "event": "result", "phase": "store_fifo", "market": market_name,
                                "store_probe": label, "item": item,
                                "elapsed_ms": int((time.time()-started)*1000),
                            })
                            await asyncio.sleep(0.015)
                        rank_remaining[r] = max(0, rank_remaining.get(r, 1) - 1)
                        if rank_remaining[r] == 0:
                            yield _web_stream_event({"event": "market_fast_done", "market": market_name, "elapsed_ms": int((time.time()-started)*1000)})

                for task in pending:
                    task.cancel()
                for r in (0, 1, 2):
                    if rank_remaining.get(r, 0) > 0:
                        yield _web_stream_event({"event": "market_fast_done", "market": _web_market_label(r), "elapsed_ms": int((time.time()-started)*1000)})
            else:
                # Compatibility mode: retain the previous market-level fast wave.
                fast_tasks = []
                if WEB_STREAM_FAST_WAVE and SERPAPI_API_KEY:
                    for rank in (0, 1, 2):
                        async def _run_market(r=rank):
                            try:
                                items = await asyncio.wait_for(
                                    asyncio.to_thread(_web_fast_market_wave_sync, q, country, lang, r),
                                    timeout=WEB_STREAM_MARKET_TIMEOUT,
                                )
                                return r, items
                            except Exception as e:
                                print(f"WEB STREAM FAST MARKET ERR rank={r}: {e}")
                                return r, []
                        fast_tasks.append(asyncio.create_task(_run_market()))
                pending_fast = set(fast_tasks)
                while pending_fast:
                    done, pending_fast = await asyncio.wait(pending_fast, timeout=0.15, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        rank, items = await task
                        market_name = _web_market_label(rank)
                        for item in items or []:
                            key = str(item.get("url") or "").strip() or (market_name + "|" + str(item.get("store") or "") + "|" + str(item.get("title") or ""))
                            if key in sent:
                                continue
                            sent.add(key)
                            yield _web_stream_event({"event": "result", "phase": "fast", "market": market_name, "item": item, "elapsed_ms": int((time.time()-started)*1000)})
                            await asyncio.sleep(0.01)
                        yield _web_stream_event({"event": "market_fast_done", "market": market_name, "count": len(items or []), "elapsed_ms": int((time.time()-started)*1000)})
                    if final_task.done():
                        break
                for task in pending_fast:
                    task.cancel()

            # Existing engine remains the authoritative enrichment pass.  Its extra rows
            # are appended after the live FIFO store probes, without changing WhatsApp logic.
            final = await final_task
            if final.get("type") == "recommendations":
                yield _web_stream_event({"event": "recommendations", "data": final, "elapsed_ms": int((time.time()-started)*1000)})
            else:
                for item in final.get("results") or []:
                    market_name = str(item.get("market") or "other")
                    key = str(item.get("url") or "").strip() or (market_name + "|" + str(item.get("store") or "") + "|" + str(item.get("title") or ""))
                    if key in sent:
                        yield _web_stream_event({"event": "upsert", "phase": "final", "market": market_name, "item": item, "elapsed_ms": int((time.time()-started)*1000)})
                    else:
                        sent.add(key)
                        yield _web_stream_event({"event": "result", "phase": "final", "market": market_name, "item": item, "elapsed_ms": int((time.time()-started)*1000)})
                    await asyncio.sleep(0.01)
            yield _web_stream_event({"event": "done", "count": len(sent), "elapsed_ms": int((time.time()-started)*1000)})
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"WEB STORE FIFO STREAM ERROR: {e}")
            yield _web_stream_event({"event": "error", "error": "search_failed", "elapsed_ms": int((time.time()-started)*1000)})

    return StreamingResponse(
        _generator(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.post("/api/search/image/stream")
async def web_api_image_search_stream(request: Request):
    if not WEB_API_ENABLED or not WEB_STREAM_ENABLED:
        return Response(content=json.dumps({"ok": False, "error": "web_stream_disabled"}), media_type="application/json", status_code=503)
    if not _web_rate_allowed(request):
        return Response(content=json.dumps({"ok": False, "error": "rate_limit"}), media_type="application/json", status_code=429)
    try:
        payload = await request.json()
    except Exception:
        return Response(content=json.dumps({"ok": False, "error": "invalid_json"}), media_type="application/json", status_code=400)

    raw = str(payload.get("image_base64") or "").strip()
    if not raw:
        return Response(content=json.dumps({"ok": False, "error": "missing_image"}), media_type="application/json", status_code=400)
    mime = str(payload.get("mime_type") or "image/jpeg").strip().lower()
    if mime not in ("image/jpeg", "image/png", "image/webp"):
        return Response(content=json.dumps({"ok": False, "error": "unsupported_image_type"}), media_type="application/json", status_code=400)
    if "," in raw and raw.lower().startswith("data:image/"):
        raw = raw.split(",", 1)[1]
    try:
        image_bytes = base64.b64decode(raw, validate=True)
    except Exception:
        return Response(content=json.dumps({"ok": False, "error": "invalid_image"}), media_type="application/json", status_code=400)
    if not image_bytes or len(image_bytes) > WEB_API_MAX_IMAGE_BYTES:
        return Response(content=json.dumps({"ok": False, "error": "image_too_large"}), media_type="application/json", status_code=413)
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    lang = _web_language(payload.get("lang"))
    country, country_source = await asyncio.to_thread(_web_resolve_request_country, request, payload.get("country"))
    caption = str(payload.get("caption") or "").strip()

    async def _generator():
        started = time.time()
        sent = set()
        market_counts = {"local": 0, "us": 0, "china": 0}
        yield _web_stream_event({"event": "start", "ok": True, "kind": "image"})
        yield _web_stream_event({"event": "status", "stage": "identify", "elapsed_ms": 0})
        try:
            seed = await asyncio.to_thread(_web_image_seed_sync, image_b64, mime, caption, country, lang)
            identity = str(seed.get("query") or caption or "").strip()
            yield _web_stream_event({"event": "query", "query": identity, "market": seed.get("market")})

            # Lens seed results are useful immediately. Emit them without waiting for any market.
            for item in seed.get("items") or []:
                market_name = str(item.get("market") or "other")
                key = str(item.get("url") or "").strip() or (market_name + "|" + str(item.get("store") or "") + "|" + str(item.get("title") or ""))
                if key in sent:
                    continue
                sent.add(key)
                if market_name in market_counts:
                    market_counts[market_name] += 1
                yield _web_stream_event({"event": "result", "phase": "lens_seed", "market": market_name, "item": item, "elapsed_ms": int((time.time()-started)*1000)})
                await asyncio.sleep(0.015)

            if identity and WEB_STREAM_STORE_FIFO and WEB_STREAM_FAST_WAVE and SERPAPI_API_KEY:
                store_tasks = []
                task_meta = {}
                rank_remaining = {0: 0, 1: 0, 2: 0}
                for rank in (2, 0, 1):
                    for label, domain, gl in _web_stream_store_specs(identity, country, rank):
                        async def _run_store(r=rank, lab=label, dom=domain, search_gl=gl):
                            try:
                                rows = await asyncio.wait_for(
                                    asyncio.to_thread(_web_store_probe_sync, identity, country, lang, r, lab, dom, search_gl),
                                    timeout=WEB_STREAM_STORE_TIMEOUT,
                                )
                                return r, lab, rows
                            except Exception as e:
                                print(f"WEB IMAGE STORE FIFO ERR rank={r} store={lab}: {e}")
                                return r, lab, []
                        task = asyncio.create_task(_run_store())
                        store_tasks.append(task)
                        task_meta[task] = (rank, label)
                        rank_remaining[rank] += 1

                pending = set(store_tasks)
                loop = asyncio.get_running_loop()
                deadline = loop.time() + WEB_STREAM_STORE_TIMEOUT
                while pending:
                    remaining = deadline - loop.time()
                    if remaining <= 0:
                        break
                    done, pending = await asyncio.wait(pending, timeout=min(0.12, remaining), return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        rank, label = task_meta.get(task, (99, "Store"))
                        try:
                            r, label, rows = await task
                        except Exception:
                            r, rows = rank, []
                        market_name = _web_market_label(r)
                        for item in rows or []:
                            key = str(item.get("url") or "").strip() or (market_name + "|" + str(item.get("store") or "") + "|" + str(item.get("title") or ""))
                            if key in sent:
                                continue
                            sent.add(key)
                            if market_name in market_counts:
                                market_counts[market_name] += 1
                            yield _web_stream_event({
                                "event": "result", "phase": "store_fifo", "market": market_name,
                                "store_probe": label, "item": item,
                                "elapsed_ms": int((time.time()-started)*1000),
                            })
                            await asyncio.sleep(0.015)
                        rank_remaining[r] = max(0, rank_remaining.get(r, 1) - 1)
                        if rank_remaining[r] == 0:
                            yield _web_stream_event({"event": "market_fast_done", "market": market_name, "elapsed_ms": int((time.time()-started)*1000)})
                for task in pending:
                    task.cancel()
                for r in (0, 1, 2):
                    if rank_remaining.get(r, 0) > 0:
                        yield _web_stream_event({"event": "market_fast_done", "market": _web_market_label(r), "elapsed_ms": int((time.time()-started)*1000)})

            # Only invoke the heavy original image engine when the live wave is still sparse
            # or local coverage is missing.  The user has already seen FIFO cards by then.
            if len(sent) < WEB_STREAM_IMAGE_FINAL_MIN_RESULTS or market_counts.get("local", 0) == 0:
                final = await asyncio.to_thread(_web_search_image_sync, image_b64, mime, caption, country, lang)
                for item in final.get("results") or []:
                    market_name = str(item.get("market") or "other")
                    key = str(item.get("url") or "").strip() or (market_name + "|" + str(item.get("store") or "") + "|" + str(item.get("title") or ""))
                    if key in sent:
                        yield _web_stream_event({"event": "upsert", "phase": "final", "market": market_name, "item": item, "elapsed_ms": int((time.time()-started)*1000)})
                        continue
                    sent.add(key)
                    yield _web_stream_event({"event": "result", "phase": "final", "market": market_name, "item": item, "elapsed_ms": int((time.time()-started)*1000)})
                    await asyncio.sleep(0.01)

            yield _web_stream_event({"event": "done", "count": len(sent), "elapsed_ms": int((time.time()-started)*1000)})
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"WEB IMAGE STORE FIFO STREAM ERROR: {e}")
            yield _web_stream_event({"event": "error", "error": "image_search_failed", "elapsed_ms": int((time.time()-started)*1000)})

    return StreamingResponse(
        _generator(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.post("/api/search")
async def web_api_search(request: Request):
    if not WEB_API_ENABLED:
        return Response(content=json.dumps({"ok": False, "error": "web_api_disabled"}), media_type="application/json", status_code=503)
    if not _web_rate_allowed(request):
        return Response(content=json.dumps({"ok": False, "error": "rate_limit"}), media_type="application/json", status_code=429)
    try:
        payload = await request.json()
    except Exception:
        return Response(content=json.dumps({"ok": False, "error": "invalid_json"}), media_type="application/json", status_code=400)
    query = str(payload.get("query") or "").strip()
    if not query and not payload.get("selected_option"):
        return Response(content=json.dumps({"ok": False, "error": "empty_query"}), media_type="application/json", status_code=400)
    lang = _web_language(payload.get("lang"))
    country, country_source = await asyncio.to_thread(_web_resolve_request_country, request, payload.get("country"))
    selected_option = str(payload.get("selected_option") or "").strip()
    original_query = str(payload.get("original_query") or "").strip()
    force_specific = bool(payload.get("force_specific"))
    started = time.time()
    result = await asyncio.to_thread(
        _web_search_text_sync, query, country, lang, selected_option, original_query, force_specific
    )
    result["elapsed_ms"] = int((time.time() - started) * 1000)
    return result


@app.post("/api/search/image")
async def web_api_image_search(request: Request):
    if not WEB_API_ENABLED:
        return Response(content=json.dumps({"ok": False, "error": "web_api_disabled"}), media_type="application/json", status_code=503)
    if not _web_rate_allowed(request):
        return Response(content=json.dumps({"ok": False, "error": "rate_limit"}), media_type="application/json", status_code=429)
    try:
        payload = await request.json()
    except Exception:
        return Response(content=json.dumps({"ok": False, "error": "invalid_json"}), media_type="application/json", status_code=400)

    raw = str(payload.get("image_base64") or "").strip()
    if not raw:
        return Response(content=json.dumps({"ok": False, "error": "missing_image"}), media_type="application/json", status_code=400)
    mime = str(payload.get("mime_type") or "image/jpeg").strip().lower()
    if mime not in ("image/jpeg", "image/png", "image/webp"):
        return Response(content=json.dumps({"ok": False, "error": "unsupported_image_type"}), media_type="application/json", status_code=400)
    if "," in raw and raw.lower().startswith("data:image/"):
        raw = raw.split(",", 1)[1]
    try:
        image_bytes = base64.b64decode(raw, validate=True)
    except Exception:
        return Response(content=json.dumps({"ok": False, "error": "invalid_image"}), media_type="application/json", status_code=400)
    if not image_bytes or len(image_bytes) > WEB_API_MAX_IMAGE_BYTES:
        return Response(content=json.dumps({"ok": False, "error": "image_too_large"}), media_type="application/json", status_code=413)
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    lang = _web_language(payload.get("lang"))
    country, country_source = await asyncio.to_thread(_web_resolve_request_country, request, payload.get("country"))
    caption = str(payload.get("caption") or "").strip()
    started = time.time()
    result = await asyncio.to_thread(_web_search_image_sync, image_b64, mime, caption, country, lang)
    result["elapsed_ms"] = int((time.time() - started) * 1000)
    return result


@app.get("/")
async def health(): return {"status":"v85 GLOBAL-GEO + STRONG-LOCAL + MULTI-CURRENCY + 10-LANG + SMART-PICK LOCAL5-US4-CN4-SHEIN", "lens_direct_mode":LENS_DIRECT_MODE, "build":BUILD_ID, "market_source":"phone_prefix", "languages":["ar","en","fr","es","pt","tr","ru","zh","hi","ur"]}
