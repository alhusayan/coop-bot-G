# -*- coding: utf-8 -*-
import os, re, time, base64, requests, json, asyncio, urllib.parse, hashlib, hmac, sqlite3, threading, io, ast
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from bs4 import BeautifulSoup
try:
    from PIL import Image as PILImage
    from pillow_heif import register_heif_opener
    register_heif_opener()
    WEB_HEIC_ENABLED = True
except Exception:
    PILImage = None
    WEB_HEIC_ENABLED = False
app = FastAPI()
_WEB_CORS_ORIGINS = [x.strip() for x in os.environ.get('WEB_ALLOWED_ORIGINS', 'https://findzia.com,https://www.findzia.com').split(',') if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_WEB_CORS_ORIGINS, allow_origin_regex=os.environ.get('WEB_ALLOWED_ORIGIN_REGEX', '^https://[a-z0-9-]+\\.myshopify\\.com$'), allow_credentials=False, allow_methods=['GET', 'POST', 'OPTIONS'], allow_headers=['Content-Type', 'Accept'], max_age=86400)
BUILD_ID = 'v107.26-serpapi-cost-saver-no-regression'
print('=' * 70)
print(f'STARTING COOP BOT BUILD: {BUILD_ID}')
print('GLOBAL GEO + IMAGE PROXY/RESCUE -> STRONG LOCAL + US + CHINA | 10 LANGS | WORLD CURRENCIES')
print('=' * 70)
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
GEMINI_SEARCH_MODEL = os.environ.get('GEMINI_SEARCH_MODEL', GEMINI_MODEL)
GEMINI_FAST_MODEL = os.environ.get('GEMINI_FAST_MODEL', GEMINI_MODEL)
WHATSAPP_TOKEN = os.environ.get('WHATSAPP_TOKEN', '')
PHONE_NUMBER_ID = os.environ.get('PHONE_NUMBER_ID', '')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', 'MY_SECRET_COOP_BOT_TOKEN')
GRAPH_URL = 'https://graph.facebook.com/v20.0'
GEMINI_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta/models'
processed_ids = deque(maxlen=1000)
PROCESSED_IDS_LOCK = threading.Lock()
IMAGE_BUFFER = defaultdict(lambda: {'images': [], 'time': 0, 'bot_id': ''})
LAST_SEARCH = {}
USER_LANG = {}
USER_MARKET = {}
USER_LOCATION_TS = {}
PENDING_ONBOARDING = {}
PENDING_GLOBAL_SEARCH = {}
PENDING_MORE_RESULTS = {}
GLOBAL_PENDING_TTL = max(300, int(os.environ.get('GLOBAL_PENDING_TTL_SECONDS', '900')))
BRAND_PICK_TTL = max(3600, int(os.environ.get('BRAND_PICK_TTL_HOURS', '6')) * 3600)
LOCATION_TTL_SECONDS = max(3600, int(os.environ.get('LOCATION_TTL_HOURS', '72')) * 3600)
MARKET_CTX = threading.local()
DEFAULT_COUNTRY = os.environ.get('DEFAULT_COUNTRY', 'kw').strip().lower() or 'kw'
PENDING_IMAGES = defaultdict(lambda: {'images': [], 'bot_id': ''})
IMAGE_BUFFER_IDLE_SECONDS = max(0.35, float(os.environ.get('IMAGE_BUFFER_IDLE_SECONDS', '0.6')))
IMAGE_BUFFER_MAX_WAIT_SECONDS = max(IMAGE_BUFFER_IDLE_SECONDS, float(os.environ.get('IMAGE_BUFFER_MAX_WAIT_SECONDS', '1.5')))
GEMINI_SEARCH_TIMEOUT_SECONDS = max(15, int(os.environ.get('GEMINI_SEARCH_TIMEOUT_SECONDS', '28')))
GEMINI_PLAIN_TIMEOUT_SECONDS = max(8, int(os.environ.get('GEMINI_PLAIN_TIMEOUT_SECONDS', '22')))
SERPAPI_TIMEOUT_SECONDS = max(8, int(os.environ.get('SERPAPI_TIMEOUT_SECONDS', '13')))
MARKET_FALLBACK_TIMEOUT_SECONDS = max(4, int(os.environ.get('MARKET_FALLBACK_TIMEOUT_SECONDS', '6')))
WHATSAPP_TIMEOUT_SECONDS = max(5, int(os.environ.get('WHATSAPP_TIMEOUT_SECONDS', '10')))
RESOLVE_TIMEOUT_SECONDS = max(3, int(os.environ.get('RESOLVE_TIMEOUT_SECONDS', '7')))
FINAL_URL_CACHE_TTL = max(300, int(os.environ.get('FINAL_URL_CACHE_TTL_SECONDS', '3600')))
FINAL_URL_CACHE = {}
FINAL_URL_CACHE_LOCK = threading.Lock()
RESOLVER = ThreadPoolExecutor(max_workers=8)
WORKERS = ThreadPoolExecutor(max_workers=5)
OLD_SEARCH_POOL = ThreadPoolExecutor(max_workers=8)
LENS_POOL = ThreadPoolExecutor(max_workers=4)
LENS_HTTP_POOL = ThreadPoolExecutor(max_workers=12)
MARKET_SUPPLEMENT_POOL = ThreadPoolExecutor(max_workers=3)
OLD_LAYER_DUPLICATES = max(1, min(2, int(os.environ.get('OLD_LAYER_DUPLICATES', '1'))))
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')
OLD_LAYER_ENABLED = env_bool('OLD_LAYER_ENABLED', True)
# v107.19: the proven v106.5 result-extraction path is authoritative again.
# Keep the newer UI, AI and "more stores" endpoints, but do not let their
# enrichment work enter the critical path of the first search.
USE_V106_5_RESULT_PIPELINE = env_bool('USE_V106_5_RESULT_PIPELINE', True)
# The old Lens flow still launched seven requests and two Gemini validators.
# This switch makes first useful Lens evidence authoritative immediately.
USE_FAST_LENS_PIPELINE = env_bool('USE_FAST_LENS_PIPELINE', True)
LENS_OVERLAP_MARKET_FALLBACK = env_bool('LENS_OVERLAP_MARKET_FALLBACK', True)
ANDROID_IMAGE_PROGRESSIVE = env_bool('ANDROID_IMAGE_PROGRESSIVE', True)
ANDROID_IMAGE_PROGRESSIVE_MIN_RESULTS = max(1, min(6, int(os.environ.get('ANDROID_IMAGE_PROGRESSIVE_MIN_RESULTS', '2'))))
ANDROID_IMAGE_PROGRESSIVE_MIN_LOCAL = max(0, min(4, int(os.environ.get('ANDROID_IMAGE_PROGRESSIVE_MIN_LOCAL', '1'))))
SEARCH_CACHE = {}
_PRODUCT_CACHE_CONFIG = int(os.environ.get('CACHE_TTL_HOURS', '12')) * 3600
_GROCERY_CACHE_CONFIG = int(os.environ.get('GROCERY_CACHE_TTL_HOURS', '4')) * 3600
CACHE_TTL = min(_PRODUCT_CACHE_CONFIG, max(300, int(os.environ.get('PRODUCT_PRICE_CACHE_MINUTES', '30')) * 60))
GROCERY_CACHE_TTL = min(_GROCERY_CACHE_CONFIG, max(300, int(os.environ.get('GROCERY_PRICE_CACHE_MINUTES', '15')) * 60))
SERVICE_CACHE_TTL = int(os.environ.get('SERVICE_CACHE_TTL_HOURS', '168')) * 3600
CACHE_MAX = int(os.environ.get('CACHE_MAX', '3000'))
CACHE_DB_PATH = os.environ.get('CACHE_DB_PATH', '/tmp/coop_search_cache.sqlite3')
CACHE_DB_LOCK = threading.Lock()
MAX_STORES = int(os.environ.get('MAX_STORES', '5'))
MAX_URLS_MERGED = int(os.environ.get('MAX_URLS_MERGED', '8'))
if USE_V106_5_RESULT_PIPELINE:
    # Clamp Railway overrides too; otherwise old MAX_STORES=14/24 variables can
    # silently bring the slow v107 candidate volume back after deployment.
    MAX_STORES = min(MAX_STORES, 5)
    MAX_URLS_MERGED = min(MAX_URLS_MERGED, 8)
ENABLE_SEARCH_RETRY = env_bool('ENABLE_SEARCH_RETRY', True)
MAX_SEARCH_ATTEMPTS = max(2, int(os.environ.get('MAX_SEARCH_ATTEMPTS', '3')))
MAX_IDENTIFY_ATTEMPTS = max(2, int(os.environ.get('MAX_IDENTIFY_ATTEMPTS', '3')))
AUTO_SEND_PRODUCT_MAPS = env_bool('AUTO_SEND_PRODUCT_MAPS', False)
SERPAPI_API_KEY = os.environ.get('SERPAPI_API_KEY', '').strip()
SERPAPI_RESULT_CACHE_ENABLED = env_bool('SERPAPI_RESULT_CACHE_ENABLED', True)
SERPAPI_RESULT_CACHE_TTL_SECONDS = max(60, min(86400, int(os.environ.get('SERPAPI_RESULT_CACHE_TTL_SECONDS', '3600'))))
SERPAPI_SINGLEFLIGHT_ENABLED = env_bool('SERPAPI_SINGLEFLIGHT_ENABLED', True)
SERPAPI_SINGLEFLIGHT_WAIT_SECONDS = max(3.0, min(30.0, float(os.environ.get('SERPAPI_SINGLEFLIGHT_WAIT_SECONDS', '20'))))
SERPAPI_CACHE_MAX_ROWS = max(500, min(50000, int(os.environ.get('SERPAPI_CACHE_MAX_ROWS', '10000'))))
SERPAPI_INFLIGHT = {}
SERPAPI_INFLIGHT_LOCK = threading.Lock()
PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', '').strip().rstrip('/')
if not PUBLIC_BASE_URL:
    _railway_domain = (os.environ.get('RAILWAY_PUBLIC_DOMAIN', '') or os.environ.get('RAILWAY_STATIC_URL', '')).strip()
    if _railway_domain:
        _railway_domain = _railway_domain.replace('https://', '').replace('http://', '').rstrip('/')
        PUBLIC_BASE_URL = f'https://{_railway_domain}'
        print(f'PUBLIC_BASE_URL auto-derived from Railway: {PUBLIC_BASE_URL}')
ENABLE_GOOGLE_LENS = env_bool('ENABLE_GOOGLE_LENS', True)
LENS_DIRECT_MODE = env_bool('LENS_DIRECT_MODE', True)
LENS_DIRECT_MAX_LINES = max(3, min(10, int(os.environ.get('LENS_DIRECT_MAX_LINES', '10'))))
LENS_DIRECT_LOCAL_MAX = max(0, min(4, int(os.environ.get('LENS_DIRECT_LOCAL_MAX', '4'))))
LENS_DIRECT_US_MAX = max(0, min(3, int(os.environ.get('LENS_DIRECT_US_MAX', '3'))))
LENS_DIRECT_CN_MAX = max(0, min(3, int(os.environ.get('LENS_DIRECT_CN_MAX', '3'))))
if USE_V106_5_RESULT_PIPELINE:
    LENS_DIRECT_MAX_LINES = min(LENS_DIRECT_MAX_LINES, 10)
    LENS_DIRECT_LOCAL_MAX = min(LENS_DIRECT_LOCAL_MAX, 4)
    LENS_DIRECT_US_MAX = min(LENS_DIRECT_US_MAX, 3)
    LENS_DIRECT_CN_MAX = min(LENS_DIRECT_CN_MAX, 3)
LENS_DIRECT_MAX_CTA = max(1, int(os.environ.get('LENS_DIRECT_MAX_CTA', str(LENS_DIRECT_LOCAL_MAX + LENS_DIRECT_US_MAX + LENS_DIRECT_CN_MAX))))
RESULT_CANDIDATE_SCAN_MAX = max(10, int(os.environ.get('RESULT_CANDIDATE_SCAN_MAX', '12')))
if USE_V106_5_RESULT_PIPELINE:
    RESULT_CANDIDATE_SCAN_MAX = min(RESULT_CANDIDATE_SCAN_MAX, 12)
MORE_LOCAL_MAX = max(0, int(os.environ.get('MORE_LOCAL_MAX', '3')))
MORE_US_MAX = max(0, int(os.environ.get('MORE_US_MAX', '2')))
MORE_CN_MAX = max(0, int(os.environ.get('MORE_CN_MAX', '2')))
MORE_TOTAL_MAX = max(1, MORE_LOCAL_MAX + MORE_US_MAX + MORE_CN_MAX)
WEB_MORE_TOTAL_MAX = max(1, min(5, int(os.environ.get('WEB_MORE_TOTAL_MAX', '5'))))
LENS_PRIMARY_MODE = env_bool('LENS_PRIMARY_MODE', True)
LENS_PRIMARY_EXCEPT_TEXT_HEAVY = env_bool('LENS_PRIMARY_EXCEPT_TEXT_HEAVY', True)
ENABLE_LENS_WIDE_FALLBACK = env_bool('ENABLE_LENS_WIDE_FALLBACK', True)
LENS_MIN_MATCHES = max(3, min(5, int(os.environ.get('LENS_MIN_MATCHES', '5'))))
LENS_PARALLEL_WITH_VISION = env_bool('LENS_PARALLEL_WITH_VISION', True)
LENS_RESULT_LIMIT = max(12, int(os.environ.get('LENS_RESULT_LIMIT', '40')))
LENS_HTTP_TIMEOUT_SECONDS = max(6, int(os.environ.get('LENS_HTTP_TIMEOUT_SECONDS', '13')))
LENS_TOTAL_TIMEOUT_SECONDS = max(8, int(os.environ.get('LENS_TOTAL_TIMEOUT_SECONDS', '12')))
LENS_TURBO_MAX_WAIT_SECONDS = max(2.5, min(6.0, float(os.environ.get('LENS_TURBO_MAX_WAIT_SECONDS', '4.5'))))
LENS_TURBO_EMPTY_GRACE_SECONDS = max(1.0, min(5.0, float(os.environ.get('LENS_TURBO_EMPTY_GRACE_SECONDS', '3.5'))))
LENS_TURBO_SPARSE_GRACE_SECONDS = max(0.5, min(2.5, float(os.environ.get('LENS_TURBO_SPARSE_GRACE_SECONDS', '1.5'))))
LENS_TURBO_STRONG_RESULT_TARGET = max(5, min(10, int(os.environ.get('LENS_TURBO_STRONG_RESULT_TARGET', '8'))))
LENS_LOCAL_LANE_TARGET = max(1, min(LENS_DIRECT_LOCAL_MAX or 1, int(os.environ.get('LENS_LOCAL_LANE_TARGET', str(LENS_DIRECT_LOCAL_MAX or 1)))))
LENS_LOCAL_LANE_GRACE_SECONDS = max(1.5, min(5.0, float(os.environ.get('LENS_LOCAL_LANE_GRACE_SECONDS', '3.5'))))
LENS_LOCAL_RESCUE_AFTER_SECONDS = max(1.0, min(LENS_TURBO_MAX_WAIT_SECONDS, float(os.environ.get('LENS_LOCAL_RESCUE_AFTER_SECONDS', '2.5'))))
LENS_LOCAL_LANE_RESCUE = env_bool('LENS_LOCAL_LANE_RESCUE', True)
LENS_IMAGE_TTL = max(120, int(os.environ.get('LENS_IMAGE_TTL_SECONDS', '600')))
LENS_IMAGE_STORE = {}
LENS_IMAGE_LOCK = threading.Lock()
ENABLE_GOOGLE_SHOPPING = env_bool('ENABLE_GOOGLE_SHOPPING', True)
GOOGLE_SHOPPING_SUPPORTED_GL = frozenset({'ai', 'ar', 'aw', 'au', 'at', 'be', 'bm', 'br', 'io', 'ca', 'ky', 'cl', 'cx', 'cc', 'co', 'cz', 'dk', 'fk', 'fi', 'fr', 'gf', 'pf', 'tf', 'de', 'gr', 'gp', 'hm', 'hk', 'hu', 'in', 'id', 'ie', 'il', 'it', 'jp', 'kr', 'my', 'mq', 'yt', 'mx', 'ms', 'nl', 'nc', 'nz', 'nf', 'no', 'ph', 'pl', 'pt', 're', 'ro', 'ru', 'pm', 'sa', 'sg', 'sk', 'za', 'gs', 'es', 'se', 'ch', 'tw', 'th', 'tk', 'tr', 'tc', 'ua', 'ae', 'uk', 'gb', 'us', 'vn', 'vg', 'wf'})
SHOPPING_GEO_GUARD = env_bool('SHOPPING_GEO_GUARD', True)
SHOPPING_UNSUPPORTED_ORGANIC_FALLBACK = env_bool('SHOPPING_UNSUPPORTED_ORGANIC_FALLBACK', True)
_SHOPPING_UNSUPPORTED_LOGGED = set()
_SHOPPING_UNSUPPORTED_LOG_LOCK = threading.Lock()
SHOPPING_RESULT_LIMIT = max(5, int(os.environ.get('SHOPPING_RESULT_LIMIT', '20')))
IMMERSIVE_LOOKUPS_MAX = max(0, int(os.environ.get('IMMERSIVE_LOOKUPS_MAX', '3')))
IMMERSIVE_MORE_STORES = env_bool('IMMERSIVE_MORE_STORES', True)
SHOPPING_POOL = ThreadPoolExecutor(max_workers=4)
LOCAL_SHOPPING_POOL = ThreadPoolExecutor(max_workers=max(4, int(os.environ.get('LOCAL_SHOPPING_WORKERS', '6'))))
LOCAL_SHOPPING_PRIMARY_PASSES = max(1, min(3, int(os.environ.get('LOCAL_SHOPPING_PRIMARY_PASSES', '2'))))
LOCAL_RESULTS_TARGET = max(2, int(os.environ.get('LOCAL_RESULTS_TARGET', '4')))
if USE_V106_5_RESULT_PIPELINE:
    LOCAL_RESULTS_TARGET = min(LOCAL_RESULTS_TARGET, 4)
LOCAL_STORE_RESCUE_MAX = max(0, min(4, int(os.environ.get('LOCAL_STORE_RESCUE_MAX', '3'))))
LOCAL_COUNTRY_RESCUE_ENABLED = env_bool('LOCAL_COUNTRY_RESCUE_ENABLED', True)
LOCAL_COUNTRY_RESCUE_PASSES = max(1, min(2, int(os.environ.get('LOCAL_COUNTRY_RESCUE_PASSES', '1'))))
LOCAL_AI_QUERY_RESCUE_ENABLED = env_bool('LOCAL_AI_QUERY_RESCUE_ENABLED', True)
LOCAL_QUERY_CACHE = {}
LOCAL_QUERY_CACHE_LOCK = threading.Lock()
COUNTRY_META = {'ae': ('United Arab Emirates', ('AED',), 'en'), 'af': ('Afghanistan', ('AFN',), 'ps'), 'ag': ('Antigua and Barbuda', ('XCD',), 'en'), 'ai': ('Anguilla', ('XCD',), 'en'), 'al': ('Albania', ('ALL',), 'sq'), 'am': ('Armenia', ('AMD',), 'hy'), 'ao': ('Angola', ('AOA',), 'pt'), 'ar': ('Argentina', ('ARS',), 'es'), 'as': ('American Samoa', ('USD',), 'en'), 'at': ('Austria', ('EUR',), 'de'), 'au': ('Australia', ('AUD',), 'en'), 'aw': ('Aruba', ('AWG',), 'nl'), 'az': ('Azerbaijan', ('AZN',), 'az'), 'ba': ('Bosnia and Herzegovina', ('BAM',), 'bs'), 'bb': ('Barbados', ('BBD',), 'en'), 'bd': ('Bangladesh', ('BDT',), 'en'), 'be': ('Belgium', ('EUR',), 'nl'), 'bf': ('Burkina Faso', ('XOF',), 'fr'), 'bg': ('Bulgaria', ('BGN',), 'bg'), 'bh': ('Bahrain', ('BHD',), 'ar'), 'bi': ('Burundi', ('BIF',), 'fr'), 'bj': ('Benin', ('XOF',), 'fr'), 'bm': ('Bermuda', ('BMD',), 'en'), 'bn': ('Brunei Darussalam', ('BND',), 'ms'), 'bo': ('Bolivia, Plurinational State of', ('BOB',), 'es'), 'br': ('Brazil', ('BRL',), 'pt'), 'bs': ('Bahamas', ('BSD',), 'en'), 'bt': ('Bhutan', ('INR', 'BTN'), 'dz'), 'bw': ('Botswana', ('BWP',), 'en'), 'by': ('Belarus', ('BYN',), 'ru'), 'bz': ('Belize', ('BZD',), 'en'), 'ca': ('Canada', ('CAD',), 'en'), 'cc': ('Cocos (Keeling) Islands', ('AUD',), 'en'), 'cd': ('Congo, The Democratic Republic of the', ('CDF',), 'fr'), 'cf': ('Central African Republic', ('XAF',), 'fr'), 'cg': ('Congo', ('XAF',), 'fr'), 'ch': ('Switzerland', ('CHF',), 'de'), 'ci': ("Côte d'Ivoire", ('XOF',), 'fr'), 'ck': ('Cook Islands', ('NZD',), 'en'), 'cl': ('Chile', ('CLP',), 'es'), 'cm': ('Cameroon', ('XAF',), 'en'), 'cn': ('China', ('CNY',), 'zh'), 'co': ('Colombia', ('COP',), 'es'), 'cr': ('Costa Rica', ('CRC',), 'es'), 'cu': ('Cuba', ('CUP',), 'es'), 'cv': ('Cabo Verde', ('CVE',), 'pt'), 'cx': ('Christmas Island', ('AUD',), 'en'), 'cy': ('Cyprus', ('EUR',), 'el'), 'cz': ('Czechia', ('CZK',), 'cs'), 'de': ('Germany', ('EUR',), 'de'), 'dj': ('Djibouti', ('DJF',), 'fr'), 'dk': ('Denmark', ('DKK',), 'da'), 'dm': ('Dominica', ('XCD',), 'en'), 'do': ('Dominican Republic', ('DOP',), 'es'), 'dz': ('Algeria', ('DZD',), 'fr'), 'ec': ('Ecuador', ('USD',), 'es'), 'ee': ('Estonia', ('EUR',), 'et'), 'eg': ('Egypt', ('EGP',), 'ar'), 'eh': ('Western Sahara', ('MAD',), 'es'), 'er': ('Eritrea', ('ERN',), 'ti'), 'es': ('Spain', ('EUR',), 'es'), 'et': ('Ethiopia', ('ETB',), 'am'), 'fi': ('Finland', ('EUR',), 'fi'), 'fj': ('Fiji', ('FJD',), 'en'), 'fk': ('Falkland Islands (Malvinas)', ('FKP',), 'en'), 'fm': ('Micronesia, Federated States of', ('USD',), 'en'), 'fo': ('Faroe Islands', ('DKK',), 'fo'), 'fr': ('France', ('EUR',), 'fr'), 'ga': ('Gabon', ('XAF',), 'fr'), 'gb': ('United Kingdom', ('GBP',), 'en'), 'gd': ('Grenada', ('XCD',), 'en'), 'ge': ('Georgia', ('GEL',), 'ka'), 'gf': ('French Guiana', ('EUR',), 'fr'), 'gg': ('Guernsey', ('GBP',), 'en'), 'gh': ('Ghana', ('GHS',), 'en'), 'gi': ('Gibraltar', ('GIP',), 'en'), 'gl': ('Greenland', ('DKK',), 'kl'), 'gm': ('Gambia', ('GMD',), 'en'), 'gn': ('Guinea', ('GNF',), 'fr'), 'gp': ('Guadeloupe', ('EUR',), 'fr'), 'gq': ('Equatorial Guinea', ('XAF',), 'es'), 'gr': ('Greece', ('EUR',), 'el'), 'gs': ('South Georgia and the South Sandwich Islands', ('GBP',), 'en'), 'gt': ('Guatemala', ('GTQ',), 'es'), 'gu': ('Guam', ('USD',), 'en'), 'gw': ('Guinea-Bissau', ('XOF',), 'pt'), 'gy': ('Guyana', ('GYD',), 'en'), 'hk': ('Hong Kong', ('HKD',), 'en'), 'hm': ('Heard Island and McDonald Islands', ('AUD',), 'en'), 'hn': ('Honduras', ('HNL',), 'es'), 'hr': ('Croatia', ('EUR',), 'hr'), 'ht': ('Haiti', ('HTG', 'USD'), 'fr'), 'hu': ('Hungary', ('HUF',), 'hu'), 'id': ('Indonesia', ('IDR',), 'id'), 'ie': ('Ireland', ('EUR',), 'en'), 'il': ('Israel', ('ILS',), 'he'), 'im': ('Isle of Man', ('GBP',), 'en'), 'in': ('India', ('INR',), 'en'), 'io': ('British Indian Ocean Territory', ('USD',), 'en'), 'iq': ('Iraq', ('IQD',), 'ar'), 'ir': ('Iran, Islamic Republic of', ('IRR',), 'fa'), 'is': ('Iceland', ('ISK',), 'is'), 'it': ('Italy', ('EUR',), 'it'), 'je': ('Jersey', ('GBP',), 'en'), 'jm': ('Jamaica', ('JMD',), 'en'), 'jo': ('Jordan', ('JOD',), 'ar'), 'jp': ('Japan', ('JPY',), 'ja'), 'ke': ('Kenya', ('KES',), 'en'), 'kg': ('Kyrgyzstan', ('KGS',), 'ky'), 'kh': ('Cambodia', ('KHR',), 'km'), 'ki': ('Kiribati', ('AUD',), 'en'), 'km': ('Comoros', ('KMF',), 'ar'), 'kn': ('Saint Kitts and Nevis', ('XCD',), 'en'), 'kp': ("Korea, Democratic People's Republic of", ('KPW',), 'ko'), 'kr': ('Korea, Republic of', ('KRW',), 'ko'), 'kw': ('Kuwait', ('KWD',), 'ar'), 'ky': ('Cayman Islands', ('KYD',), 'en'), 'kz': ('Kazakhstan', ('KZT',), 'ru'), 'la': ("Lao People's Democratic Republic", ('LAK',), 'lo'), 'lb': ('Lebanon', ('LBP',), 'ar'), 'lc': ('Saint Lucia', ('XCD',), 'en'), 'li': ('Liechtenstein', ('CHF',), 'de'), 'lk': ('Sri Lanka', ('LKR',), 'si'), 'lr': ('Liberia', ('LRD',), 'en'), 'ls': ('Lesotho', ('ZAR', 'LSL'), 'en'), 'lt': ('Lithuania', ('EUR',), 'lt'), 'lu': ('Luxembourg', ('EUR',), 'fr'), 'lv': ('Latvia', ('EUR',), 'lv'), 'ly': ('Libya', ('LYD',), 'ar'), 'ma': ('Morocco', ('MAD',), 'fr'), 'mc': ('Monaco', ('EUR',), 'fr'), 'md': ('Moldova, Republic of', ('MDL',), 'ro'), 'mg': ('Madagascar', ('MGA',), 'fr'), 'mh': ('Marshall Islands', ('USD',), 'en'), 'mk': ('North Macedonia', ('MKD',), 'mk'), 'ml': ('Mali', ('XOF',), 'fr'), 'mn': ('Mongolia', ('MNT',), 'mn'), 'mo': ('Macao', ('MOP',), 'zh'), 'mp': ('Northern Mariana Islands', ('USD',), 'en'), 'mq': ('Martinique', ('EUR',), 'fr'), 'mr': ('Mauritania', ('MRU',), 'ar'), 'ms': ('Montserrat', ('XCD',), 'en'), 'mt': ('Malta', ('EUR',), 'mt'), 'mu': ('Mauritius', ('MUR',), 'en'), 'mv': ('Maldives', ('MVR',), 'dv'), 'mw': ('Malawi', ('MWK',), 'en'), 'mx': ('Mexico', ('MXN',), 'es'), 'my': ('Malaysia', ('MYR',), 'en'), 'mz': ('Mozambique', ('MZN',), 'pt'), 'na': ('Namibia', ('ZAR', 'NAD'), 'en'), 'nc': ('New Caledonia', ('XPF',), 'fr'), 'ne': ('Niger', ('XOF',), 'fr'), 'nf': ('Norfolk Island', ('AUD',), 'en'), 'ng': ('Nigeria', ('NGN',), 'en'), 'ni': ('Nicaragua', ('NIO',), 'es'), 'nl': ('Netherlands', ('EUR',), 'nl'), 'no': ('Norway', ('NOK',), 'no'), 'np': ('Nepal', ('NPR',), 'ne'), 'nr': ('Nauru', ('AUD',), 'en'), 'nu': ('Niue', ('NZD',), 'en'), 'nz': ('New Zealand', ('NZD',), 'en'), 'om': ('Oman', ('OMR',), 'ar'), 'pa': ('Panama', ('PAB', 'USD'), 'es'), 'pe': ('Peru', ('PEN',), 'es'), 'pf': ('French Polynesia', ('XPF',), 'fr'), 'pg': ('Papua New Guinea', ('PGK',), 'en'), 'ph': ('Philippines', ('PHP',), 'en'), 'pk': ('Pakistan', ('PKR',), 'en'), 'pl': ('Poland', ('PLN',), 'pl'), 'pm': ('Saint Pierre and Miquelon', ('EUR',), 'fr'), 'pn': ('Pitcairn', ('NZD',), 'en'), 'pr': ('Puerto Rico', ('USD',), 'es'), 'pt': ('Portugal', ('EUR',), 'pt'), 'pw': ('Palau', ('USD',), 'en'), 'py': ('Paraguay', ('PYG',), 'es'), 'qa': ('Qatar', ('QAR',), 'ar'), 're': ('Réunion', ('EUR',), 'fr'), 'ro': ('Romania', ('RON',), 'ro'), 'rs': ('Serbia', ('RSD',), 'rs'), 'ru': ('Russian Federation', ('RUB',), 'ru'), 'rw': ('Rwanda', ('RWF',), 'rw'), 'sa': ('Saudi Arabia', ('SAR',), 'ar'), 'sb': ('Solomon Islands', ('SBD',), 'en'), 'sc': ('Seychelles', ('SCR',), 'fr'), 'sd': ('Sudan', ('SDG',), 'ar'), 'se': ('Sweden', ('SEK',), 'sv'), 'sg': ('Singapore', ('SGD',), 'en'), 'sh': ('Saint Helena, Ascension and Tristan da Cunha', ('SHP',), 'en'), 'si': ('Slovenia', ('EUR',), 'sl'), 'sj': ('Svalbard and Jan Mayen', ('NOK',), 'no'), 'sk': ('Slovakia', ('EUR',), 'sk'), 'sl': ('Sierra Leone', ('SLE',), 'en'), 'sm': ('San Marino', ('EUR',), 'it'), 'sn': ('Senegal', ('XOF',), 'fr'), 'so': ('Somalia', ('SOS',), 'so'), 'sr': ('Suriname', ('SRD',), 'nl'), 'ss': ('South Sudan', ('SSP',), 'en'), 'st': ('Sao Tome and Principe', ('STN',), 'pt'), 'sv': ('El Salvador', ('USD',), 'es'), 'sy': ('Syrian Arab Republic', ('SYP',), 'ar'), 'sz': ('Eswatini', ('SZL',), 'en'), 'td': ('Chad', ('XAF',), 'fr'), 'tf': ('French Southern Territories', ('EUR',), 'fr'), 'tg': ('Togo', ('XOF',), 'fr'), 'th': ('Thailand', ('THB',), 'th'), 'tj': ('Tajikistan', ('TJS',), 'tg'), 'tk': ('Tokelau', ('NZD',), 'en'), 'tl': ('Timor-Leste', ('USD',), 'pt'), 'tm': ('Turkmenistan', ('TMT',), 'tk'), 'tn': ('Tunisia', ('TND',), 'fr'), 'to': ('Tonga', ('TOP',), 'en'), 'tr': ('Türkiye', ('TRY',), 'tr'), 'tt': ('Trinidad and Tobago', ('TTD',), 'en'), 'tv': ('Tuvalu', ('AUD',), 'en'), 'tw': ('Taiwan, Province of China', ('TWD',), 'zh'), 'tz': ('Tanzania, United Republic of', ('TZS',), 'en'), 'ua': ('Ukraine', ('UAH',), 'uk'), 'ug': ('Uganda', ('UGX',), 'en'), 'us': ('United States', ('USD',), 'en'), 'uy': ('Uruguay', ('UYU',), 'es'), 'uz': ('Uzbekistan', ('UZS',), 'uz'), 'vc': ('Saint Vincent and the Grenadines', ('XCD',), 'en'), 've': ('Venezuela, Bolivarian Republic of', ('VES',), 'es'), 'vn': ('Viet Nam', ('VND',), 'vi'), 'vu': ('Vanuatu', ('VUV',), 'bi'), 'wf': ('Wallis and Futuna', ('XPF',), 'fr'), 'ws': ('Samoa', ('WST',), 'sm'), 'xk': ('Kosovo', ('EUR',), 'sq'), 'ye': ('Yemen', ('YER',), 'ar'), 'yt': ('Mayotte', ('EUR',), 'fr'), 'za': ('South Africa', ('ZAR',), 'en'), 'zm': ('Zambia', ('ZMW',), 'en'), 'zw': ('Zimbabwe', ('USD', 'ZWG'), 'en')}
CALLING_CODE_TO_COUNTRY = {'1': 'us', '7': 'ru', '20': 'eg', '27': 'za', '30': 'gr', '31': 'nl', '32': 'be', '33': 'fr', '34': 'es', '36': 'hu', '39': 'it', '40': 'ro', '41': 'ch', '43': 'at', '44': 'gb', '45': 'dk', '46': 'se', '47': 'no', '48': 'pl', '49': 'de', '51': 'pe', '52': 'mx', '53': 'cu', '54': 'ar', '55': 'br', '56': 'cl', '57': 'co', '58': 've', '60': 'my', '61': 'au', '62': 'id', '63': 'ph', '64': 'nz', '65': 'sg', '66': 'th', '76': 'kz', '77': 'kz', '81': 'jp', '82': 'kr', '84': 'vn', '86': 'cn', '90': 'tr', '91': 'in', '92': 'pk', '93': 'af', '94': 'lk', '98': 'ir', '211': 'ss', '212': 'ma', '213': 'dz', '216': 'tn', '218': 'ly', '220': 'gm', '221': 'sn', '222': 'mr', '223': 'ml', '224': 'gn', '225': 'ci', '226': 'bf', '227': 'ne', '228': 'tg', '229': 'bj', '230': 'mu', '231': 'lr', '232': 'sl', '233': 'gh', '234': 'ng', '235': 'td', '236': 'cf', '237': 'cm', '238': 'cv', '239': 'st', '240': 'gq', '241': 'ga', '242': 'cg', '243': 'cd', '244': 'ao', '245': 'gw', '246': 'io', '248': 'sc', '249': 'sd', '250': 'rw', '251': 'et', '252': 'so', '253': 'dj', '254': 'ke', '255': 'tz', '256': 'ug', '257': 'bi', '258': 'mz', '260': 'zm', '261': 'mg', '262': 're', '263': 'zw', '264': 'na', '265': 'mw', '266': 'ls', '267': 'bw', '268': 'sz', '269': 'km', '290': 'sh', '291': 'er', '297': 'aw', '298': 'fo', '299': 'gl', '350': 'gi', '351': 'pt', '352': 'lu', '353': 'ie', '354': 'is', '355': 'al', '356': 'mt', '357': 'cy', '358': 'fi', '359': 'bg', '370': 'lt', '371': 'lv', '372': 'ee', '373': 'md', '374': 'am', '375': 'by', '377': 'mc', '378': 'sm', '380': 'ua', '381': 'rs', '385': 'hr', '386': 'si', '387': 'ba', '389': 'mk', '420': 'cz', '421': 'sk', '423': 'li', '500': 'fk', '501': 'bz', '502': 'gt', '503': 'sv', '504': 'hn', '505': 'ni', '506': 'cr', '507': 'pa', '508': 'pm', '509': 'ht', '590': 'gp', '591': 'bo', '592': 'gy', '593': 'ec', '594': 'gf', '595': 'py', '596': 'mq', '597': 'sr', '598': 'uy', '670': 'tl', '672': 'nf', '673': 'bn', '674': 'nr', '675': 'pg', '676': 'to', '677': 'sb', '678': 'vu', '679': 'fj', '680': 'pw', '681': 'wf', '682': 'ck', '683': 'nu', '685': 'ws', '686': 'ki', '687': 'nc', '688': 'tv', '689': 'pf', '690': 'tk', '691': 'fm', '692': 'mh', '850': 'kp', '852': 'hk', '853': 'mo', '855': 'kh', '856': 'la', '880': 'bd', '886': 'tw', '960': 'mv', '961': 'lb', '962': 'jo', '963': 'sy', '964': 'iq', '965': 'kw', '966': 'sa', '967': 'ye', '968': 'om', '971': 'ae', '972': 'il', '973': 'bh', '974': 'qa', '975': 'bt', '976': 'mn', '977': 'np', '992': 'tj', '993': 'tm', '994': 'az', '995': 'ge', '996': 'kg', '998': 'uz', '1242': 'bs', '1246': 'bb', '1264': 'ai', '1268': 'ag', '1345': 'ky', '1441': 'bm', '1473': 'gd', '1664': 'ms', '1670': 'mp', '1671': 'gu', '1684': 'as', '1758': 'lc', '1767': 'dm', '1784': 'vc', '1787': 'pr', '1809': 'do', '1829': 'do', '1849': 'do', '1868': 'tt', '1869': 'kn', '1876': 'jm', '1939': 'pr', '4779': 'sj'}
NANP_CANADA_AREA_CODES = {'204', '226', '236', '249', '250', '257', '263', '289', '306', '343', '354', '365', '367', '368', '382', '403', '416', '418', '428', '431', '437', '438', '450', '468', '474', '506', '514', '519', '548', '579', '581', '584', '587', '604', '613', '639', '647', '672', '683', '705', '709', '742', '753', '778', '780', '782', '807', '819', '825', '867', '873', '879', '902', '905'}
COUNTRY_META.update({'ad': ('Andorra', ('EUR',), 'ca'), 'ax': ('Åland Islands', ('EUR',), 'sv'), 'bq': ('Bonaire, Sint Eustatius and Saba', ('USD',), 'nl'), 'bl': ('Saint Barthélemy', ('EUR',), 'fr'), 'cw': ('Curaçao', ('XCG',), 'nl'), 'mf': ('Saint Martin', ('EUR',), 'fr'), 'mm': ('Myanmar', ('MMK',), 'my'), 'me': ('Montenegro', ('EUR',), 'sr'), 'ps': ('Palestine', ('ILS', 'JOD'), 'ar'), 'sx': ('Sint Maarten', ('XCG',), 'nl'), 'tc': ('Turks and Caicos Islands', ('USD',), 'en'), 'va': ('Vatican City', ('EUR',), 'it'), 'vg': ('British Virgin Islands', ('USD',), 'en'), 'vi': ('U.S. Virgin Islands', ('USD',), 'en')})
CALLING_CODE_TO_COUNTRY.update({'376': 'ad', '95': 'mm', '382': 'me', '970': 'ps', '383': 'xk', '5999': 'cw', '5997': 'bq', '5994': 'bq', '5993': 'bq', '599': 'bq', '1721': 'sx', '1649': 'tc', '1284': 'vg', '1340': 'vi', '3906698': 'va', '441481': 'gg', '441534': 'je', '441624': 'im', '35818': 'ax', '262269': 'yt', '262639': 'yt', '59059027': 'bl', '59059029': 'mf'})
COUNTRY_NAMES = {cc: meta[0] for cc, meta in COUNTRY_META.items()}
COUNTRY_CURRENCY_CODES = {cc: tuple(meta[1]) for cc, meta in COUNTRY_META.items()}
COUNTRY_CURRENCIES = {cc: meta[1][0] if meta[1] else '' for cc, meta in COUNTRY_META.items()}
COUNTRY_SEARCH_HL = {cc: meta[2] or 'en' for cc, meta in COUNTRY_META.items()}
COUNTRY_TLDS = {cc: ('.uk',) if cc == 'gb' else (f'.{cc}',) for cc in COUNTRY_META}
COUNTRY_TLDS['gb'] = ('.uk', '.co.uk')
COUNTRY_TLDS['us'] = ('.us',)
CURRENCY_DECIMALS = {'AFN': 0, 'ALL': 0, 'BHD': 3, 'BIF': 0, 'CLP': 0, 'DJF': 0, 'GNF': 0, 'IQD': 0, 'IRR': 0, 'ISK': 0, 'JOD': 3, 'JPY': 0, 'KMF': 0, 'KPW': 0, 'KRW': 0, 'KWD': 3, 'LAK': 0, 'LBP': 0, 'LYD': 3, 'MGA': 0, 'OMR': 3, 'PYG': 0, 'RSD': 0, 'RWF': 0, 'SOS': 0, 'SYP': 0, 'TND': 3, 'UGX': 0, 'VND': 0, 'VUV': 0, 'XAF': 0, 'XOF': 0, 'XPF': 0, 'YER': 0}
THREE_DECIMAL_CURRENCIES = {code for code, digits in CURRENCY_DECIMALS.items() if digits == 3}
ZERO_DECIMAL_CURRENCIES = {code for code, digits in CURRENCY_DECIMALS.items() if digits == 0}
FX_CACHE = {}
FX_CACHE_LOCK = threading.Lock()
FX_CACHE_TTL = max(3600, int(os.environ.get('FX_CACHE_TTL_HOURS', '12')) * 3600)
FX_API_URL = os.environ.get('FX_API_URL', 'https://open.er-api.com/v6/latest/{base}')
CURRENCY_SYMBOL_MAP = {'us$': 'USD', '€': 'EUR', '₹': 'INR', '₩': 'KRW', '₺': 'TRY', '₽': 'RUB', 'r$': 'BRL', 'a$': 'AUD', 'c$': 'CAD', 'hk$': 'HKD', 's$': 'SGD', 'nz$': 'NZD', 'nt$': 'TWD', 'د.إ': 'AED', 'ر.س': 'SAR', 'ر.ق': 'QAR', 'ر.ع': 'OMR', 'د.ب': 'BHD', 'د.ك': 'KWD', 'ج.م': 'EGP', 'د.أ': 'JOD', '₪': 'ILS', '₴': 'UAH', '₸': 'KZT', '₾': 'GEL', '₼': 'AZN', '฿': 'THB', '₫': 'VND', '₱': 'PHP', '₦': 'NGN', '₵': 'GHS', '৳': 'BDT', '₲': 'PYG', '₭': 'LAK', '₮': 'MNT', 'zł': 'PLN', 'kč': 'CZK', 'ft': 'HUF'}
KNOWN_CURRENCY_CODES = set((code for codes in COUNTRY_CURRENCY_CODES.values() for code in codes)) | {'USD', 'EUR', 'GBP', 'JPY', 'CNY', 'INR', 'AED', 'SAR', 'QAR', 'OMR', 'BHD', 'KWD', 'TRY', 'EGP', 'JOD', 'AUD', 'CAD', 'CHF', 'SEK', 'NOK', 'DKK', 'PLN', 'RUB', 'BRL', 'MXN', 'ZAR', 'KRW', 'SGD', 'MYR', 'THB', 'IDR', 'PHP', 'VND', 'PKR', 'HKD', 'NZD', 'TWD'}
DOLLAR_LIKE_CODES = {'USD', 'CAD', 'AUD', 'NZD', 'SGD', 'HKD', 'TWD', 'MXN', 'ARS', 'CLP', 'COP', 'UYU', 'BMD', 'BBD', 'BSD', 'BZD', 'BND', 'FJD', 'GYD', 'JMD', 'KYD', 'LRD', 'NAD', 'SBD', 'SRD', 'TTD', 'XCD'}
YEN_LIKE_CODES = {'JPY', 'CNY'}
POUND_LIKE_CODES = {'GBP', 'EGP', 'FKP', 'GIP', 'SHP', 'SSP', 'SYP'}

def get_fx_rates(base):
    base = (base or '').upper().strip()
    if not base:
        return {}
    now = time.time()
    with FX_CACHE_LOCK:
        hit = FX_CACHE.get(base)
        if hit and now - hit['ts'] < FX_CACHE_TTL:
            return hit['rates']
    try:
        r = requests.get(FX_API_URL.format(base=base), timeout=10)
        if r.ok:
            j = r.json()
            rates = j.get('rates') or j.get('conversion_rates') or {}
            if rates:
                with FX_CACHE_LOCK:
                    FX_CACHE[base] = {'rates': rates, 'ts': now}
                print(f'FX RATES LOADED base={base} count={len(rates)}')
                return rates
        print(f'FX HTTP {r.status_code} base={base}')
    except Exception as e:
        print(f'FX FETCH ERR base={base}: {e}')
    with FX_CACHE_LOCK:
        hit = FX_CACHE.get(base)
        return hit['rates'] if hit else {}

def convert_to_local(value, from_currency):
    try:
        val = float(value)
    except Exception:
        return None
    src = (from_currency or '').upper().strip()
    dst = (current_market().get('currency') or '').upper().strip()
    if not src or not dst:
        return None
    if src == dst:
        return val
    rates = get_fx_rates(src)
    rate = rates.get(dst)
    if not rate:
        return None
    return val * float(rate)

def detect_currency_code(text, fallback='', country_code=None):
    hay = str(text or '').strip()
    fallback = (fallback or '').upper().strip()
    if not hay:
        return fallback
    m = re.search('\\b([A-Z]{3})\\b', hay.upper())
    if m and m.group(1) in KNOWN_CURRENCY_CODES:
        return m.group(1)
    low = hay.lower()
    for sym in sorted(CURRENCY_SYMBOL_MAP, key=len, reverse=True):
        if sym in low or sym in hay:
            return CURRENCY_SYMBOL_MAP[sym]
    cc = (country_code or (current_market().get('country') if 'current_market' in globals() else '') or '').lower()
    local_codes = set(COUNTRY_CURRENCY_CODES.get(cc, ()))
    preferred = fallback or (next(iter(local_codes)) if len(local_codes) == 1 else '')
    if '$' in hay:
        if preferred in DOLLAR_LIKE_CODES:
            return preferred
        for code in COUNTRY_CURRENCY_CODES.get(cc, ()):
            if code in DOLLAR_LIKE_CODES:
                return code
        return 'USD'
    if '¥' in hay or '￥' in hay:
        if preferred in YEN_LIKE_CODES:
            return preferred
        if 'CNY' in local_codes:
            return 'CNY'
        if 'JPY' in local_codes:
            return 'JPY'
        return 'JPY'
    if '£' in hay:
        if preferred in POUND_LIKE_CODES:
            return preferred
        for code in COUNTRY_CURRENCY_CODES.get(cc, ()):
            if code in POUND_LIKE_CODES:
                return code
        return 'GBP'
    return fallback

def display_global_price(price_value, price_text, currency_code, lang='ar'):
    src = detect_currency_code(f"{currency_code or ''} {price_text or ''}", currency_code, current_market().get('country'))
    numeric = _authoritative_price_value(price_value, price_text, currency_code)
    if numeric is None:
        return (str(price_text or '').strip(), None)
    converted = convert_to_local(numeric, src) if src else None
    local_code = (current_market().get('currency') or '').upper()
    if converted is not None:
        label = currency_label(lang)
        original = f' ({format_price(numeric, src)} {src})' if src and src != local_code else ''
        return (f'{format_price(converted, local_code)} {label}{original}', converted)
    shown = str(price_text or '').strip() or f'{format_price(numeric, src)} {src}'.strip()
    return (shown, None)

def country_currency_codes(cc=None):
    cc = (cc or current_market().get('country') or DEFAULT_COUNTRY).lower()
    return COUNTRY_CURRENCY_CODES.get(cc, tuple(filter(None, (COUNTRY_CURRENCIES.get(cc, ''),))))

def country_search_hl(cc=None):
    cc = (cc or current_market().get('country') or DEFAULT_COUNTRY).lower()
    return COUNTRY_SEARCH_HL.get(cc, 'en') or 'en'

def country_tlds(cc=None):
    cc = (cc or current_market().get('country') or DEFAULT_COUNTRY).lower()
    return COUNTRY_TLDS.get(cc, (f'.{cc}',) if len(cc) == 2 else ())

def infer_country_from_phone(phone):
    digits = re.sub('\\D', '', phone or '')
    if digits.startswith('00'):
        digits = digits[2:]
    if digits.startswith('1') and len(digits) >= 4:
        full4 = digits[:4]
        if full4 in CALLING_CODE_TO_COUNTRY and full4 != '1':
            return CALLING_CODE_TO_COUNTRY[full4]
        if digits[1:4] in NANP_CANADA_AREA_CODES:
            return 'ca'
        return 'us'
    if digits.startswith(('76', '77')):
        return 'kz'
    for prefix in sorted(CALLING_CODE_TO_COUNTRY, key=len, reverse=True):
        if digits.startswith(prefix):
            return CALLING_CODE_TO_COUNTRY[prefix]
    return DEFAULT_COUNTRY
MARKET_NAME_ALIASES = {'usa': 'us', 'unitedstates': 'us', 'america': 'us', 'uk': 'gb', 'unitedkingdom': 'gb', 'britain': 'gb', 'greatbritain': 'gb', 'uae': 'ae', 'emirates': 'ae', 'unitedarabemirates': 'ae', 'saudi': 'sa', 'saudiarabia': 'sa', 'korea': 'kr', 'southkorea': 'kr', 'russia': 'ru', 'turkiye': 'tr', 'turkey': 'tr', 'czechia': 'cz', 'czechrepublic': 'cz'}

def _norm_market_name(value):
    import unicodedata
    t = unicodedata.normalize('NFKD', str(value or '').strip().casefold())
    t = ''.join((ch for ch in t if not unicodedata.combining(ch)))
    return re.sub('[^a-z0-9]', '', t)

def resolve_market_country(value):
    raw = str(value or '').strip()
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
    market['market_override'] = cc.lower()
    market['market_source'] = 'manual_test'
    USER_MARKET[phone] = market
    save_user_preferences(phone)
    return market_for_user(phone)

def clear_market_override(phone):
    load_user_preferences(phone)
    market = dict(USER_MARKET.get(phone) or {})
    market.pop('market_override', None)
    market['market_source'] = 'phone_prefix'
    USER_MARKET[phone] = market
    save_user_preferences(phone)
    return market_for_user(phone)

def market_for_user(from_number):
    market = dict(USER_MARKET.get(from_number) or {})
    override = str(market.get('market_override') or '').strip().lower()
    cc = override if override in COUNTRY_NAMES else (infer_country_from_phone(from_number) or DEFAULT_COUNTRY).lower()
    currencies = COUNTRY_CURRENCY_CODES.get(cc) or tuple(filter(None, (COUNTRY_CURRENCIES.get(cc, ''),)))
    market['country'] = cc
    market['country_name'] = COUNTRY_NAMES.get(cc, cc.upper())
    market['currency'] = currencies[0] if currencies else ''
    market['currencies'] = list(currencies)
    market['search_hl'] = COUNTRY_SEARCH_HL.get(cc, 'en')
    market['tlds'] = list(country_tlds(cc))
    market['market_source'] = 'manual_test' if override else 'phone_prefix'
    market.pop('lat', None)
    market.pop('lng', None)
    market.pop('city', None)
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
    changed = any((before.get(k) != market.get(k) for k in ('country', 'country_name', 'currency', 'market_source')))
    if persist and changed:
        save_user_preferences(from_number)
    return market

def current_market():
    base_cc = DEFAULT_COUNTRY
    base_codes = COUNTRY_CURRENCY_CODES.get(base_cc) or (COUNTRY_CURRENCIES.get(base_cc, 'KWD'),)
    return getattr(MARKET_CTX, 'value', None) or {'country': base_cc, 'country_name': COUNTRY_NAMES.get(base_cc, 'Kuwait'), 'currency': base_codes[0] if base_codes else 'KWD', 'currencies': list(base_codes), 'search_hl': COUNTRY_SEARCH_HL.get(base_cc, 'ar'), 'tlds': list(country_tlds(base_cc))}

def _run_with_market(market, fn, *args, **kwargs):
    MARKET_CTX.value = market
    return fn(*args, **kwargs)

def currency_label(lang='ar'):
    code = current_market().get('currency') or ''
    if lang == 'ar' and code == 'KWD':
        return 'د.ك'
    return code or ''

def market_instruction():
    m = current_market()
    cc = (m.get('country') or DEFAULT_COUNTRY).lower()
    country = m.get('country_name') or COUNTRY_NAMES.get(cc, cc.upper())
    currency = m.get('currency') or 'local currency'
    currencies = ', '.join(m.get('currencies') or country_currency_codes(cc)) or currency
    hl = m.get('search_hl') or country_search_hl(cc)
    tlds = ', '.join(country_tlds(cc))
    priority = priority_stores_for('') if 'priority_stores_for' in globals() else []
    stores = ', '.join(priority[:6]) if priority else 'the strongest local specialist retailers and marketplaces'
    kuwait_extra = ''
    if cc == 'kw':
        kuwait_extra = ' Kuwait premium local discovery: actively check Pro Sports, Intersport, Decathlon, Sun & Sand Sports for sports; Xcite, Eureka Kuwait, Best Al-Yousifi, Blink, Jarir and 3RoodQ8 for electronics/gaming; Tigro and Toys R Us for toys; Jm3eia, Lulu, Carrefour and Taw9eel for grocery, plus any smaller Kuwait merchant indexed by Google Shopping.'
    return f"\nIMPORTANT CURRENT USER MARKET: {country} (ISO country {cc.upper()}, Google gl={cc}, preferred hl={hl}). Accepted local currencies: {currencies}; primary display currency: {currency}; local ccTLD evidence: {tlds}. LOCAL RESULTS ARE THE CORE PRODUCT: exhaust the local market before relying on foreign results. Search the product using the user's wording, its commercial English name, and when useful the main local commerce language ({hl}). Prioritize {stores}, but never limit discovery to a fixed list: include small genuine local merchants indexed in Google Shopping/Search. Use geography in this exact order: (1) the user's local country, (2) United States, (3) China only. Reject every fourth country. Do not move a cheaper US/China offer above a genuine local offer. Foreign stores do not need to ship locally. Treat Heureka/heureka.cz/heureka.sk as blocked comparison sites in every market; do NOT confuse them with Eureka Kuwait. A local .com merchant is valid when Google local targeting, local currency, country text/path, or merchant evidence clearly ties it to the user's market. " + kuwait_extra + '\n'
GROCERY_WORDS = ['بيبسي', 'شيبس', 'حليب', 'قهوه', 'قهوة', 'شاي', 'سكر', 'رز', 'زيت', 'صابون', 'شامبو', 'برينجلز', 'كيتكات', 'نسكافيه', 'تونه', 'ماء', 'عصير', 'بسكوت', 'منظف', 'معجون', 'حفاض']
print(f"ECONOMIC CONFIG search_model={GEMINI_SEARCH_MODEL} fast_model={GEMINI_FAST_MODEL} max_stores={MAX_STORES} search_attempts={MAX_SEARCH_ATTEMPTS} identify_attempts={MAX_IDENTIFY_ATTEMPTS} auto_maps={AUTO_SEND_PRODUCT_MAPS} lens_wide_fallback={ENABLE_LENS_WIDE_FALLBACK} lens_parallel={LENS_PARALLEL_WITH_VISION} google_shopping={ENABLE_GOOGLE_SHOPPING} immersive_max={IMMERSIVE_LOOKUPS_MAX} public_base_url={('SET' if PUBLIC_BASE_URL else 'MISSING')}")
VERIFIED_PAGE_CACHE = {}
VERIFIED_PAGE_CACHE_MAX = int(os.environ.get('VERIFIED_PAGE_CACHE_MAX', '600'))
OOS_PHRASES = ['out of stock', 'غير متوفر', 'نفدت الكمية', 'غير متاح', 'sold out', 'غير متوفر حاليا', 'نفذت', 'not available', 'temporarily unavailable']
RESULTS_PER_STORE_MAX = max(1, int(os.environ.get('RESULTS_PER_STORE_MAX', '1')))
ENABLE_RESULT_STOCK_CHECK = env_bool('ENABLE_RESULT_STOCK_CHECK', True)
ENABLE_LIVE_STOCK_NETWORK_CHECK = env_bool('ENABLE_LIVE_STOCK_NETWORK_CHECK', False)
ENABLE_LIVE_PAGE_VERIFICATION = env_bool('ENABLE_LIVE_PAGE_VERIFICATION', False)
LISTING_URL_PARTS = ['/search', '/s?', '/category', '/categories', '/collection', '/collections', '/shop/category', '?q=', '/search_results', '/shop/', '/listing', '/c/']
BLOCKED_STORE_DOMAINS = ('heureka.cz', 'heureka.sk', 'heureka.group')
BLOCKED_STORE_NAME_TOKENS = ('heureka',)

def is_blocked_store(name='', url=''):
    name_norm = re.sub('[^a-z0-9]+', '', str(name or '').lower())
    if any((tok in name_norm for tok in BLOCKED_STORE_NAME_TOKENS)):
        return True
    try:
        host = urllib.parse.urlparse(str(url or '')).netloc.lower().split(':')[0]
        host = host[4:] if host.startswith('www.') else host
    except Exception:
        host = ''
    return any((host == d or host.endswith('.' + d) for d in BLOCKED_STORE_DOMAINS))

def format_price(p, currency=None):
    try:
        pf = float(p)
    except Exception:
        return str(p)
    code = (currency or current_market().get('currency') or 'KWD').upper().strip()
    digits = int(CURRENCY_DECIMALS.get(code, 2))
    return f'{pf:.{digits}f}'

def format_lens_price(price_text, price_value, lang='ar', currency_code=None):
    numeric = _authoritative_price_value(price_value, price_text, currency_code)
    if numeric is None:
        return str(price_text or '').strip()
    label = currency_label(lang)
    return f'{format_price(numeric, currency_code)} {label}'

def is_direct_store_url(url):
    if not url or not url.startswith(('http://', 'https://')):
        return False
    if is_blocked_store('', url):
        print(f'BLOCKED STORE URL: {url[:120]}')
        return False
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc.lower().replace('www.', '')
        path_q = (parsed.path + ('?' + parsed.query if parsed.query else '')).lower()
    except Exception:
        return False
    blocked_hosts = ('google.com', 'google.com.kw', 'googleusercontent.com', 'gstatic.com', 'bing.com', 'yahoo.com')
    if any((host == h or host.endswith('.' + h) for h in blocked_hosts)):
        return False
    if not parsed.path or parsed.path == '/':
        return False
    if any((part in path_q for part in LISTING_URL_PARTS)):
        if not re.search('/product/|/products/[^/]{3,}|/p/|/dp/|/item/|/prod/', path_q):
            return False
    collection_patterns = ('/designers/[^/]+/shoes/?$', '/designers/[^/]+/[^/]+/?$', '/brand/[^/]+/?$', '/brands/[^/]+/?$', '/mules/?$', '/shoes/?$', '/women/?$', '/men/?$')
    if any((re.search(p, parsed.path.lower()) for p in collection_patterns)):
        return False
    return True

def is_lens_product_url(url, item=None):
    if not url or not url.startswith(('http://', 'https://')):
        return False
    try:
        p = urllib.parse.urlparse(url)
        host = p.netloc.lower().replace('www.', '')
        path_q = (p.path + ('?' + p.query if p.query else '')).lower()
    except Exception:
        return False
    if any((host == h or host.endswith('.' + h) for h in ('google.com', 'google.com.kw', 'googleusercontent.com', 'gstatic.com', 'bing.com', 'yahoo.com'))):
        return False
    if not p.path or p.path == '/':
        return False
    hard_listing = ('/search', '?q=', '/category/', '/categories/', '/collections/', '/listing')
    if any((x in path_q for x in hard_listing)):
        return False
    collection_patterns = ('/designers/[^/]+/shoes/?$', '/designers/[^/]+/[^/]+/?$', '/brand/[^/]+/?$', '/brands/[^/]+/?$', '/mules/?$', '/shoes/?$', '/women/?$', '/men/?$', '/pyjamas/?$', '/pajamas/?$')
    if any((re.search(x, p.path.lower()) for x in collection_patterns)):
        return False
    if item:
        if not (str(item.get('title') or '').strip() and str(item.get('source') or '').strip()):
            return False
    return True

def direct_urls_only(urls):
    return {name: url for name, url in (urls or {}).items() if not is_blocked_store(name, url) and is_direct_store_url(url)}

def normalize_ar(text):
    t = (text or '').lower()
    t = re.sub('[أإآ]', 'ا', t)
    t = t.replace('ة', 'ه').replace('ى', 'ي').replace('ئ', 'ي').replace('ؤ', 'و')
    t = t.replace('ري بان', 'ريبان').replace('راي بان', 'ريبان').replace('ray ban', 'rayban').replace('ray-ban', 'rayban')
    return t
SIZE_RE = re.compile('(?:(\\d+(?:[.,]\\d+)?)\\s*[x×*]\\s*)?(\\d+(?:[.,]\\d+)?)\\s*(مل|ملي لتر|ملل|ml|لتر|ليتر|l|ltr|liter|litre|كجم|كغم|كغ|كيلو جرام|كيلو غرام|كيلو|kg|جرام|غرام|جم|غم|gm|gr|g|تيرا بايت|تيرابايت|تيرا|tb|جيجا بايت|جيجابايت|جيجا|غيغا|قيقا|gb)\\b', re.I)
_VOL_UNITS = {'مل', 'ملي لتر', 'ملل', 'ml'}
_VOL_BIG_UNITS = {'لتر', 'ليتر', 'l', 'ltr', 'liter', 'litre'}
_WT_BIG_UNITS = {'كجم', 'كغم', 'كغ', 'كيلو جرام', 'كيلو غرام', 'كيلو', 'kg'}
_CAP_UNITS = {'جيجا بايت', 'جيجابايت', 'جيجا', 'غيغا', 'قيقا', 'gb'}
_CAP_BIG_UNITS = {'تيرا بايت', 'تيرابايت', 'تيرا', 'tb'}

def extract_pack_size(text):
    t = normalize_ar(str(text or ''))
    for m in SIZE_RE.finditer(t):
        try:
            count = float((m.group(1) or '1').replace(',', '.'))
            qty = float(m.group(2).replace(',', '.'))
        except Exception:
            continue
        unit = m.group(3).lower()
        if unit in _CAP_BIG_UNITS:
            cls, base = ('cap', qty * 1000.0)
        elif unit in _CAP_UNITS:
            cls, base = ('cap', qty)
        elif unit in _VOL_BIG_UNITS:
            cls, base = ('vol', qty * 1000.0)
        elif unit in _VOL_UNITS:
            cls, base = ('vol', qty)
        elif unit in _WT_BIG_UNITS:
            cls, base = ('wt', qty * 1000.0)
        else:
            cls, base = ('wt', qty)
        total = count * base
        if total > 0:
            return (cls, total)
    return None

def format_pack_size(sig):
    if not sig:
        return ''
    cls, total = sig
    if cls == 'cap':
        return f'{total / 1000:g} تيرا' if total >= 1000 else f'{int(total)} جيجا'
    if cls == 'vol':
        return f'{total / 1000:g} لتر' if total >= 1000 else f'{int(total)} مل'
    return f'{total / 1000:g} كجم' if total >= 1000 else f'{int(total)} جم'

def sizes_compatible(a, b):
    if not a or not b:
        return True
    if a[0] != b[0]:
        return False
    lo, hi = sorted((a[1], b[1]))
    return hi <= lo * 1.15

def filter_same_size(offers_dict, reference_text):
    if not offers_dict:
        return offers_dict
    ref = extract_pack_size(reference_text)
    sized = {n: extract_pack_size(str(i.get('title', ''))) for n, i in offers_dict.items()}
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
            print(f"SIZE MISMATCH REJECT: {name} -> {info.get('title', '')} (want~{format_pack_size(ref)}, got {format_pack_size(sized.get(name))})")
    return kept

def _measurement_numeric_values(text):
    out = []
    t = normalize_ar(str(text or ''))
    for m in SIZE_RE.finditer(t):
        try:
            count = float((m.group(1) or '1').replace(',', '.'))
            qty = float(m.group(2).replace(',', '.'))
        except Exception:
            continue
        if qty > 0:
            out.append(qty)
            if count > 1:
                out.append(count * qty)
    return out

def _price_collides_with_measurement(value, *texts):
    try:
        val = float(value)
    except Exception:
        return False
    if val <= 0:
        return False
    for text in texts:
        for qty in _measurement_numeric_values(text):
            if qty < 8:
                continue
            tol = max(0.001, abs(qty) * 0.001)
            if abs(val - qty) <= tol:
                return True
    return False

# Product specifications such as 1440p, 180Hz, 27-inch, 65W, 5000mAh
# are common false positives when a retailer page exposes loose numeric metadata.
_SPEC_NUMBER_RE = re.compile(r'(?<![A-Za-z0-9])([0-9]{2,5}(?:[.,][0-9]+)?)\s*(?:p\b|hz\b|khz\b|mhz\b|ghz\b|inch(?:es)?\b|in\b|["”″]|w\b|watt(?:s)?\b|mah\b|dpi\b|ppi\b|nits?\b|rpm\b)', re.I)

def _product_spec_numeric_values(text):
    out = []
    t = normalize_ar(str(text or ''))
    for m in _SPEC_NUMBER_RE.finditer(t):
        try:
            out.append(float(str(m.group(1)).replace(',', '.')))
        except Exception:
            pass
    return out

def _price_collides_with_product_spec(value, *texts):
    try:
        val = float(value)
    except Exception:
        return False
    if val <= 0:
        return False
    if _price_collides_with_measurement(val, *texts):
        return True
    for text in texts:
        for spec in _product_spec_numeric_values(text):
            tol = max(0.01, abs(spec) * 0.001)
            if abs(val - spec) <= tol:
                return True
    return False

def _number_overlaps_measurement_span(text, start, end):
    t = normalize_ar(str(text or ''))
    for m in SIZE_RE.finditer(t):
        if start < m.end() and end > m.start():
            return True
    return False

def norm_tokens(query):
    t = normalize_ar(query)
    toks = re.findall('[\\w\\u0600-\\u06FF]+', t)
    toks = [w[2:] if w.startswith('ال') and len(w) > 4 else w for w in toks]
    return set(toks)

def has_model_token(a, b):

    def models(s):
        return {t for t in s if re.search('\\d', t) and re.search('[a-z\\u0600-\\u06FF]', t) and (len(t) >= 4)}
    return bool(models(a) & models(b))

def cache_key(query, lang):
    norm = re.sub('[^\\w\\u0600-\\u06FF]+', '', normalize_ar(query))
    market = current_market().get('country', DEFAULT_COUNTRY)
    return hashlib.sha256(f'v85-global-geo|{market}|{norm}|{lang}'.encode()).hexdigest()

def cache_ttl_for(query, txt=''):
    q_norm = normalize_ar(query)
    if txt and re.search('(?:🏆|•)\\s*.+?\\(\\s*(?:هاتف|Phone|phone|Tel|tel)\\s*:', txt):
        return SERVICE_CACHE_TTL
    if any((w in q_norm for w in GROCERY_WORDS)):
        return GROCERY_CACHE_TTL
    return CACHE_TTL

def _cache_db_connect():
    parent = os.path.dirname(CACHE_DB_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(CACHE_DB_PATH, timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    return conn

def _cache_db_init():
    try:
        with CACHE_DB_LOCK, _cache_db_connect() as conn:
            conn.execute('\n                CREATE TABLE IF NOT EXISTS search_cache (\n                    cache_key TEXT PRIMARY KEY,\n                    query TEXT NOT NULL,\n                    lang TEXT NOT NULL,\n                    txt TEXT NOT NULL,\n                    urls_json TEXT NOT NULL,\n                    ts REAL NOT NULL,\n                    expires_at REAL NOT NULL\n                )\n            ')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_search_cache_expiry ON search_cache(expires_at)')
            conn.execute('DELETE FROM search_cache WHERE expires_at <= ?', (time.time(),))
            conn.execute("\n                CREATE TABLE IF NOT EXISTS user_preferences (\n                    phone TEXT PRIMARY KEY,\n                    lang TEXT,\n                    market_json TEXT NOT NULL DEFAULT '{}',\n                    location_ts REAL NOT NULL DEFAULT 0,\n                    updated_at REAL NOT NULL\n                )\n            ")
    except Exception as e:
        print(f'CACHE DB INIT ERR: {e}')

def _cache_db_get(key):
    try:
        with CACHE_DB_LOCK, _cache_db_connect() as conn:
            row = conn.execute('SELECT query, lang, txt, urls_json, ts, expires_at FROM search_cache WHERE cache_key=?', (key,)).fetchone()
            if not row:
                return None
            query, lang, txt, urls_json, ts, expires_at = row
            if expires_at <= time.time():
                conn.execute('DELETE FROM search_cache WHERE cache_key=?', (key,))
                return None
            return {'query': query, 'lang': lang, 'txt': txt, 'urls': json.loads(urls_json or '{}'), 'ts': ts, 'expires_at': expires_at, 'tokens': norm_tokens(query)}
    except Exception as e:
        print(f'CACHE DB GET ERR: {e}')
        return None

def _cache_db_put(key, entry):
    try:
        with CACHE_DB_LOCK, _cache_db_connect() as conn:
            conn.execute('\n                INSERT INTO search_cache(cache_key, query, lang, txt, urls_json, ts, expires_at)\n                VALUES(?,?,?,?,?,?,?)\n                ON CONFLICT(cache_key) DO UPDATE SET\n                    query=excluded.query,\n                    lang=excluded.lang,\n                    txt=excluded.txt,\n                    urls_json=excluded.urls_json,\n                    ts=excluded.ts,\n                    expires_at=excluded.expires_at\n                ', (key, entry['query'], entry['lang'], entry['txt'], json.dumps(entry['urls'], ensure_ascii=False), entry['ts'], entry['expires_at']))
    except Exception as e:
        print(f'CACHE DB PUT ERR: {e}')
_cache_db_init()

# -----------------------------------------------------------------------------
# SerpApi cost guard
#
# SerpApi serves an identical request from its one-hour cache for free.  Keep a
# local persistent copy as well, and coalesce concurrent requests from WhatsApp,
# web and mobile so only one worker can spend a credit for a given request.
# This layer never changes the query, result order, market, or number of passes.
# -----------------------------------------------------------------------------
def _serpapi_cache_db_init():
    if not SERPAPI_RESULT_CACHE_ENABLED:
        return
    try:
        with CACHE_DB_LOCK, _cache_db_connect() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS serpapi_response_cache (
                    cache_key TEXT PRIMARY KEY,
                    engine TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_serpapi_cache_expiry ON serpapi_response_cache(expires_at)')
            conn.execute('DELETE FROM serpapi_response_cache WHERE expires_at <= ?', (time.time(),))
    except Exception as e:
        print(f'SERPAPI CACHE INIT ERR: {e}')

def _serpapi_cache_key(params):
    safe = {str(k): str(v) for k, v in (params or {}).items() if k not in ('api_key',)}
    canonical = json.dumps(safe, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

def _serpapi_cache_get(key):
    if not SERPAPI_RESULT_CACHE_ENABLED:
        return None
    try:
        now = time.time()
        with CACHE_DB_LOCK, _cache_db_connect() as conn:
            row = conn.execute(
                'SELECT response_json, expires_at FROM serpapi_response_cache WHERE cache_key=?',
                (key,),
            ).fetchone()
            if not row:
                return None
            if float(row[1] or 0) <= now:
                conn.execute('DELETE FROM serpapi_response_cache WHERE cache_key=?', (key,))
                return None
        data = json.loads(row[0] or '{}')
        return data if isinstance(data, dict) else None
    except Exception as e:
        print(f'SERPAPI CACHE GET ERR: {e}')
        return None

def _serpapi_cache_put(key, engine, data, ttl_seconds=None):
    if not SERPAPI_RESULT_CACHE_ENABLED or not isinstance(data, dict):
        return
    now = time.time()
    ttl = float(ttl_seconds or SERPAPI_RESULT_CACHE_TTL_SECONDS)
    try:
        with CACHE_DB_LOCK, _cache_db_connect() as conn:
            conn.execute('''
                INSERT INTO serpapi_response_cache(cache_key, engine, response_json, created_at, expires_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    engine=excluded.engine,
                    response_json=excluded.response_json,
                    created_at=excluded.created_at,
                    expires_at=excluded.expires_at
            ''', (key, engine or '', json.dumps(data, ensure_ascii=False, separators=(',', ':')), now, now + ttl))
            count_row = conn.execute('SELECT COUNT(*) FROM serpapi_response_cache').fetchone()
            if count_row and int(count_row[0] or 0) > SERPAPI_CACHE_MAX_ROWS:
                trim = max(100, int(SERPAPI_CACHE_MAX_ROWS * 0.1))
                conn.execute('''
                    DELETE FROM serpapi_response_cache WHERE cache_key IN (
                        SELECT cache_key FROM serpapi_response_cache ORDER BY expires_at ASC LIMIT ?
                    )
                ''', (trim,))
    except Exception as e:
        print(f'SERPAPI CACHE PUT ERR: {e}')

def _serpapi_cached_json(params, timeout, label='SERPAPI'):
    """Return the exact SerpApi JSON while avoiding duplicate paid requests."""
    engine = str((params or {}).get('engine') or 'unknown')
    key = _serpapi_cache_key(params)
    cached = _serpapi_cache_get(key)
    if cached is not None:
        print(f'SERPAPI CACHE HIT engine={engine} label={label} key={key[:10]}')
        return cached

    leader = True
    event = None
    if SERPAPI_SINGLEFLIGHT_ENABLED:
        with SERPAPI_INFLIGHT_LOCK:
            event = SERPAPI_INFLIGHT.get(key)
            if event is None:
                event = threading.Event()
                SERPAPI_INFLIGHT[key] = event
            else:
                leader = False
        if not leader:
            print(f'SERPAPI SINGLEFLIGHT WAIT engine={engine} label={label} key={key[:10]}')
            event.wait(SERPAPI_SINGLEFLIGHT_WAIT_SECONDS)
            cached = _serpapi_cache_get(key)
            if cached is not None:
                print(f'SERPAPI SINGLEFLIGHT HIT engine={engine} label={label} key={key[:10]}')
                return cached
            # The leader failed or exceeded the wait budget. Preserve the old
            # behavior by attempting the live request instead of returning less.

    try:
        print(f'SERPAPI LIVE REQUEST engine={engine} label={label} key={key[:10]}')
        response = requests.get('https://serpapi.com/search.json', params=params, timeout=timeout)
        if response.status_code >= 400:
            print(f'{label} HTTP {response.status_code}: {response.text[:300]}')
            return None
        data = response.json()
        if not isinstance(data, dict):
            print(f'{label} INVALID JSON TYPE: {type(data).__name__}')
            return None
        if data.get('error'):
            print(f"{label} ERROR: {data.get('error')}")
            return None
        _serpapi_cache_put(key, engine, data)
        return data
    except Exception as e:
        print(f'{label} EXCEPTION: {e}')
        return None
    finally:
        if SERPAPI_SINGLEFLIGHT_ENABLED and leader and event is not None:
            with SERPAPI_INFLIGHT_LOCK:
                current = SERPAPI_INFLIGHT.get(key)
                if current is event:
                    SERPAPI_INFLIGHT.pop(key, None)
                    event.set()

_serpapi_cache_db_init()
print(f'SERPAPI COST GUARD cache={SERPAPI_RESULT_CACHE_ENABLED} ttl={SERPAPI_RESULT_CACHE_TTL_SECONDS}s singleflight={SERPAPI_SINGLEFLIGHT_ENABLED} wait={SERPAPI_SINGLEFLIGHT_WAIT_SECONDS}s stable_lens_url=True')

def load_user_preferences(phone):
    if phone in USER_LANG or phone in USER_MARKET or phone in USER_LOCATION_TS:
        return
    try:
        with CACHE_DB_LOCK, _cache_db_connect() as conn:
            row = conn.execute('SELECT lang, market_json, location_ts FROM user_preferences WHERE phone=?', (phone,)).fetchone()
        if not row:
            return
        lang, market_json, location_ts = row
        if lang:
            USER_LANG[phone] = lang
        try:
            market = json.loads(market_json or '{}')
            if market:
                USER_MARKET[phone] = market
        except Exception:
            pass
        USER_LOCATION_TS[phone] = float(location_ts or 0)
    except Exception as e:
        print(f'USER PREF GET ERR: {e}')

def save_user_preferences(phone):
    try:
        with CACHE_DB_LOCK, _cache_db_connect() as conn:
            conn.execute('\n                INSERT INTO user_preferences(phone, lang, market_json, location_ts, updated_at)\n                VALUES(?,?,?,?,?)\n                ON CONFLICT(phone) DO UPDATE SET\n                    lang=excluded.lang,\n                    market_json=excluded.market_json,\n                    location_ts=excluded.location_ts,\n                    updated_at=excluded.updated_at\n                ', (phone, USER_LANG.get(phone), json.dumps(USER_MARKET.get(phone) or {}, ensure_ascii=False), float(USER_LOCATION_TS.get(phone, 0)), time.time()))
    except Exception as e:
        print(f'USER PREF PUT ERR: {e}')

def cache_pending_message(phone, message, bot_id):
    PENDING_ONBOARDING[phone] = {'message': message, 'bot_id': bot_id, 'ts': time.time()}

def cache_get(query, lang):
    now = time.time()
    key = cache_key(query, lang)
    hit = SEARCH_CACHE.get(key)
    if not hit:
        hit = _cache_db_get(key)
        if hit:
            SEARCH_CACHE[key] = hit
    if hit and now < hit.get('expires_at', 0):
        print(f'CACHE HIT (exact): {query[:60]}')
        return (hit['txt'], dict(hit['urls']))
    qt = norm_tokens(query)
    if not qt:
        return None
    best, best_score = (None, 0.0)
    for entry in SEARCH_CACHE.values():
        if entry.get('lang') != lang or now >= entry.get('expires_at', 0):
            continue
        et = entry.get('tokens') or set()
        if not et:
            continue
        inter = len(qt & et)
        score = inter / len(qt | et) if qt | et else 0
        if has_model_token(qt, et):
            score += 0.3
        if score > best_score:
            best, best_score = (entry, score)
    if best and best_score >= 0.68:
        print(f"CACHE HIT (fuzzy {best_score:.2f}): {query[:50]} ~ {best.get('query', '')[:50]}")
        return (best['txt'], dict(best['urls']))
    return None

def cache_put(query, lang, txt, urls):
    if not txt:
        return
    if len(SEARCH_CACHE) >= CACHE_MAX:
        oldest = min(SEARCH_CACHE, key=lambda k: SEARCH_CACHE[k].get('ts', 0))
        SEARCH_CACHE.pop(oldest, None)
    now = time.time()
    ttl = cache_ttl_for(query, txt)
    key = cache_key(query, lang)
    entry = {'txt': txt, 'urls': dict(urls), 'ts': now, 'expires_at': now + ttl, 'tokens': norm_tokens(query), 'query': query, 'lang': lang}
    SEARCH_CACHE[key] = entry
    _cache_db_put(key, entry)
IDENTIFY_SYSTEM = 'أنت خبير تعرف على المنتجات من الصور.\nأرجع دائماً اسمين قابلين للبحث بهذا الشكل فقط:\n[الاسم التجاري بالعربية] | [commercial product name in English]\nضع البراند ورقم الموديل إن ظهر. إذا ظهر حجم أو وزن أو سعة على العبوة (مثل 1 لتر، 500 مل، 250 جم، 256GB) أدخله في الاسمين، فهو جزء من هوية المنتج.\nاستنتج نوع المنتج من الشعار والشكل والنص الظاهر.\nلا ترفض التحديد لمجرد أن الصورة غير كاملة؛ أعطِ أقرب اسم تجاري مفيد للبحث.\nمثال: حليب المراعي كامل الدسم 1 لتر | Almarai Full Fat Milk 1L\nسطر واحد فقط، بدون شرح.'
MSG = {'ar': {'identifying': '✨ ثواني.. أحدد المنتج وأدور لك أفضل الخيارات.', 'searching': '🔎 أدور لك على {q}...', 'not_found': 'ما لقيت المنتج متوفر حالياً بسعر مؤكد 😅 جرب صياغة ثانية أو دز صورة أوضح.', 'identified_not_found': 'حددت المنتج ({p}) بس ما لقيت له سعر مؤكد حالياً 😅 جرب تكتب اسمه بصيغة ثانية.', 'cant_identify': 'بحثت أكثر من مرة، لكن ما قدرت أحدد المنتج أو ألقى له نتيجة مؤكدة. دز صورة أوضح أو اكتب اسم المنتج.', 'image_error': 'صار خلل بسيط وأنا أحمّل الصورة 😅 عيد إرسالها مرة ثانية.', 'multi_text': 'تمام لقيت {c} منتجات، أسوي سلة...', 'multi_images': 'تمام لقطت {c} منتجات، أسوي سلة...', 'maps_body': '📍 تبي أقرب مكان؟\n\nاضغط الزر والخريطة بتفتح على أقرب الأماكن حولك 👇', 'maps_btn': '📍 افتح الخريطة', 'maps_body_loc': '📍 بحثك الأخير كان عن ({p})\n\nجهزت لك أقرب الأماكن حولك، اضغط الزر وافتح الخريطة 👇', 'no_saved_product': 'ما عندي منتج محفوظ حالياً 😅. ابحث عن منتج أول، وبعدها أدلك على أقرب مكان يبيعه!', 'lang_saved': 'تمام، بكلمك عربي من هني ورايح 🇰🇼\nدز صورة منتج أو اكتب اسمه وأنا حاضر!', 'ask_global': 'ما لقيت نتيجة محلية مؤكدة لهذا المنتج في موقعك الحالي. تبي أدور لك في المتاجر العالمية؟ 🌍', 'global_yes': 'نعم، ابحث عالميًا 🌍', 'global_no': 'لا، محلي فقط', 'global_searching': '🌍 أدور لك عالميًا على أفضل النتائج المطابقة...', 'global_none': 'حتى بالبحث العالمي ما لقيت نتيجة مؤكدة ومباشرة لهذا المنتج.', 'ask_not_found': 'ما لقيت نفس المنتج بالضبط متوفر عندك محلياً 😅\n\nشرايك، وش تبيني أسوي؟ 👇', 'opt_global': '🌍 دوّر عالمياً', 'opt_similar': '🔄 بدائل مشابهة', 'opt_no': 'لا شكراً 🙏', 'similar_searching': '🔄 أدور لك على أفضل البدائل المشابهة المتوفرة عندك...', 'similar_none': 'ما لقيت بدائل مشابهة بسعر مؤكد حالياً 😅 جرب صياغة ثانية.', 'declined_ok': 'تمام 🙏 إذا احتجت شي ثاني أنا حاضر!', 'welcome_reply': 'هلا والله! 🌟\nدز صورة المنتج أو اكتب اسمه، وأدور لك أفضل الأسعار والمتاجر القريبة منك 🛒', 'thanks_reply': 'العفو! 🌹 في الخدمة دايماً.. أي منتج ثاني تبيه أنا حاضر!', 'lens_header': '✨ لقيت لك هالنتائج المطابقة:', 'lens_none': '🔎 ما لقيت نتائج كافية من الصورة، بجرب لك طريقة ثانية...', 'market_from_phone': '✅ تم تحديد بلدك من رقم WhatsApp: {country}'}, 'en': {'identifying': '✨ One moment.. identifying the product and finding the best options.', 'searching': '🔎 Looking for {q}...', 'not_found': "Couldn't find it in-stock with a verified price 😅 try another phrasing or a clearer photo.", 'identified_not_found': "I identified the product ({p}) but couldn't find a verified price right now 😅 try typing its name differently.", 'cant_identify': 'I searched several times but couldn’t identify the product or find a verified result. Send a clearer photo or type the product name.', 'image_error': 'Something went wrong while loading the image 😅 please send it again.', 'multi_text': 'Got it, found {c} products. Building your cart...', 'multi_images': 'Nice, spotted {c} products. Building your cart...', 'maps_body': '📍 Want the nearest place?\n\nTap the button and the map will open on the closest spots around you 👇', 'maps_btn': '📍 Open Map', 'maps_body_loc': "📍 Your last search was ({p})\n\nI've lined up the closest places around you. Tap the button to open the map 👇", 'no_saved_product': "I don't have a saved product yet 😅. Search for a product first, then I'll point you to the nearest store!", 'lang_saved': "Great, I'll speak English with you from now on 🇬🇧\nSend a product photo or type its name and I'm on it!", 'ask_global': "I couldn't find a verified local result in your current market. Search international stores instead? 🌍", 'global_yes': 'Yes, search globally 🌍', 'global_no': 'No, local only', 'global_searching': '🌍 Searching international stores for the closest matches...', 'global_none': "I still couldn't find a verified direct result globally.", 'ask_not_found': "I couldn't find this exact product available locally 😅\n\nWhat would you like me to do? 👇", 'opt_global': '🌍 Search globally', 'opt_similar': '🔄 Similar items', 'opt_no': 'No thanks 🙏', 'similar_searching': '🔄 Looking for the best similar alternatives available near you...', 'similar_none': "I couldn't find similar alternatives with a verified price right now 😅 try another phrasing.", 'declined_ok': "No problem 🙏 I'm here whenever you need me!", 'welcome_reply': "Hello! 🌟\nSend a product photo or type its name, and I'll find you the best prices and nearby stores 🛒", 'thanks_reply': "You're welcome! 🌹 Anytime.. just send me the next product!", 'lens_header': '✨ Here are the matching results I found:', 'lens_none': '🔎 I didn’t find enough results from the image, trying another method...', 'market_from_phone': '✅ Your country is set from your WhatsApp number: {country}'}}
MSG['hi'] = {'identifying': '✨ एक पल... प्रोडक्ट पहचान रहा हूँ और सबसे अच्छे विकल्प ढूँढ रहा हूँ।', 'searching': '🔎 {q} ढूँढ रहा हूँ...', 'not_found': 'अभी पक्की कीमत के साथ उपलब्ध नतीजा नहीं मिला 😅 नाम थोड़ा अलग लिखें या साफ़ फोटो भेजें।', 'identified_not_found': 'मैंने प्रोडक्ट ({p}) पहचान लिया, लेकिन अभी पक्की कीमत नहीं मिली 😅 नाम दूसरी तरह लिखकर देखें।', 'cant_identify': 'कई बार कोशिश की, लेकिन प्रोडक्ट ठीक से पहचान नहीं पाया या पक्का नतीजा नहीं मिला। साफ़ फोटो भेजें या प्रोडक्ट का नाम लिखें।', 'image_error': 'फोटो लोड करते समय छोटी-सी समस्या हुई 😅 कृपया फोटो दोबारा भेजें।', 'multi_text': 'ठीक है, {c} प्रोडक्ट मिले। कार्ट बना रहा हूँ...', 'multi_images': 'अच्छा, {c} प्रोडक्ट पहचान लिए। कार्ट बना रहा हूँ...', 'maps_body': '📍 आस-पास कहाँ मिलता है देखना है? नीचे बटन दबाकर मैप खोलें 👇', 'maps_btn': '📍 मैप खोलें', 'maps_body_loc': '📍 आपकी पिछली खोज ({p}) थी। नीचे बटन दबाकर आस-पास के स्टोर देखें 👇', 'no_saved_product': 'अभी कोई प्रोडक्ट सेव नहीं है 😅 पहले किसी प्रोडक्ट की खोज करें।', 'lang_saved': 'ठीक है, अब से मैं हिंदी में बात करूँगा 🇮🇳\nप्रोडक्ट की फोटो भेजें या नाम लिखें।', 'ask_global': 'आपके देश में पक्का नतीजा नहीं मिला। क्या अंतरराष्ट्रीय स्टोर में खोजूँ? 🌍', 'global_yes': 'हाँ, दुनिया भर में खोजें 🌍', 'global_no': 'नहीं, केवल स्थानीय', 'global_searching': '🌍 अंतरराष्ट्रीय स्टोर में सबसे मिलते-जुलते नतीजे ढूँढ रहा हूँ...', 'global_none': 'अंतरराष्ट्रीय खोज में भी पक्का सीधा नतीजा नहीं मिला।', 'ask_not_found': 'यह बिल्कुल वही प्रोडक्ट स्थानीय रूप से नहीं मिला 😅\n\nआप क्या करना चाहेंगे? 👇', 'opt_global': '🌍 दुनिया भर में खोजें', 'opt_similar': '🔄 मिलते-जुलते विकल्प', 'opt_no': 'नहीं धन्यवाद 🙏', 'similar_searching': '🔄 आपके लिए सबसे अच्छे मिलते-जुलते विकल्प ढूँढ रहा हूँ...', 'similar_none': 'अभी पक्की कीमत के साथ मिलते-जुलते विकल्प नहीं मिले 😅 दूसरी तरह लिखकर देखें।', 'declined_ok': 'ठीक है 🙏 जब चाहें मैं यहाँ हूँ!', 'welcome_reply': 'नमस्ते! 🌟\nप्रोडक्ट की फोटो भेजें या नाम लिखें, मैं कीमतें और अच्छे स्टोर ढूँढ दूँगा 🛒', 'thanks_reply': 'आपका स्वागत है! 🌹 अगला प्रोडक्ट भेज दीजिए।', 'lens_header': '✨ ये मिलते-जुलते नतीजे मिले:', 'lens_none': '🔎 फोटो से पर्याप्त नतीजे नहीं मिले, दूसरी विधि आज़मा रहा हूँ...', 'market_from_phone': '✅ आपका देश WhatsApp नंबर से तय कर दिया गया है: {country}'}
MSG['ur'] = {'identifying': '✨ ایک لمحہ... پروڈکٹ پہچان رہا ہوں اور بہترین آپشنز تلاش کر رہا ہوں۔', 'searching': '🔎 {q} تلاش کر رہا ہوں...', 'not_found': 'ابھی تصدیق شدہ قیمت کے ساتھ دستیاب نتیجہ نہیں ملا 😅 نام مختلف انداز میں لکھیں یا صاف تصویر بھیجیں۔', 'identified_not_found': 'میں نے پروڈکٹ ({p}) پہچان لیا، مگر ابھی تصدیق شدہ قیمت نہیں ملی 😅 نام دوسری طرح لکھ کر دیکھیں۔', 'cant_identify': 'کئی بار کوشش کی، مگر پروڈکٹ درست طور پر پہچان نہیں سکا یا پکا نتیجہ نہیں ملا۔ صاف تصویر بھیجیں یا پروڈکٹ کا نام لکھیں۔', 'image_error': 'تصویر لوڈ کرتے وقت معمولی مسئلہ ہوا 😅 براہِ کرم دوبارہ بھیجیں۔', 'multi_text': 'ٹھیک ہے، {c} پروڈکٹس مل گئے۔ کارٹ بنا رہا ہوں...', 'multi_images': 'اچھا، {c} پروڈکٹس پہچان لیے۔ کارٹ بنا رہا ہوں...', 'maps_body': '📍 قریب کہاں ملتا ہے؟ نیچے بٹن دبا کر نقشہ کھولیں 👇', 'maps_btn': '📍 نقشہ کھولیں', 'maps_body_loc': '📍 آپ کی آخری تلاش ({p}) تھی۔ نیچے بٹن دبا کر قریب کے اسٹور دیکھیں 👇', 'no_saved_product': 'ابھی کوئی پروڈکٹ محفوظ نہیں 😅 پہلے کسی پروڈکٹ کی تلاش کریں۔', 'lang_saved': 'ٹھیک ہے، اب سے میں اردو میں بات کروں گا 🇵🇰\nپروڈکٹ کی تصویر بھیجیں یا نام لکھیں۔', 'ask_global': 'آپ کے ملک میں تصدیق شدہ نتیجہ نہیں ملا۔ کیا بین الاقوامی اسٹورز میں تلاش کروں؟ 🌍', 'global_yes': 'ہاں، دنیا بھر میں تلاش کریں 🌍', 'global_no': 'نہیں، صرف مقامی', 'global_searching': '🌍 بین الاقوامی اسٹورز میں قریب ترین نتائج تلاش کر رہا ہوں...', 'global_none': 'بین الاقوامی تلاش میں بھی تصدیق شدہ براہِ راست نتیجہ نہیں ملا۔', 'ask_not_found': 'یہ بالکل وہی پروڈکٹ مقامی طور پر نہیں ملا 😅\n\nآپ کیا کرنا چاہیں گے؟ 👇', 'opt_global': '🌍 دنیا بھر میں تلاش کریں', 'opt_similar': '🔄 ملتے جلتے متبادل', 'opt_no': 'نہیں شکریہ 🙏', 'similar_searching': '🔄 آپ کے لیے بہترین ملتے جلتے متبادل تلاش کر رہا ہوں...', 'similar_none': 'ابھی تصدیق شدہ قیمت کے ساتھ ملتے جلتے متبادل نہیں ملے 😅 دوسری طرح لکھ کر دیکھیں۔', 'declined_ok': 'ٹھیک ہے 🙏 جب چاہیں میں حاضر ہوں!', 'welcome_reply': 'السلام علیکم! 🌟\nپروڈکٹ کی تصویر بھیجیں یا نام لکھیں، میں بہترین قیمتیں اور اسٹورز تلاش کر دوں گا 🛒', 'thanks_reply': 'خوش آمدید! 🌹 اگلا پروڈکٹ بھیج دیں۔', 'lens_header': '✨ یہ ملتے جلتے نتائج ملے:', 'lens_none': '🔎 تصویر سے کافی نتائج نہیں ملے، دوسرا طریقہ آزما رہا ہوں...', 'market_from_phone': '✅ آپ کا ملک WhatsApp نمبر سے طے کیا گیا ہے: {country}'}
MSG['fr'] = {'identifying': '✨ Un instant… j’identifie le produit et je cherche les meilleures options.', 'searching': '🔎 Je cherche {q}…', 'not_found': 'Je n’ai pas trouvé de résultat disponible avec un prix fiable 😅 essayez une autre formulation ou une photo plus nette.', 'identified_not_found': 'J’ai identifié le produit ({p}), mais je n’ai pas trouvé de prix fiable pour le moment 😅 essayez d’écrire son nom autrement.', 'cant_identify': 'J’ai essayé plusieurs fois, mais je n’ai pas pu identifier le produit ni trouver un résultat fiable. Envoyez une photo plus nette ou écrivez le nom du produit.', 'image_error': 'Un petit problème est survenu pendant le chargement de l’image 😅 renvoyez-la s’il vous plaît.', 'multi_text': 'Parfait, j’ai trouvé {c} produits. Je prépare le panier…', 'multi_images': 'Parfait, j’ai repéré {c} produits. Je prépare le panier…', 'maps_body': '📍 Vous voulez voir où le trouver à proximité ? Ouvrez la carte ci-dessous 👇', 'maps_btn': '📍 Ouvrir la carte', 'maps_body_loc': '📍 Votre dernière recherche était ({p}). Ouvrez la carte pour voir les magasins à proximité 👇', 'no_saved_product': 'Je n’ai aucun produit enregistré pour le moment 😅 recherchez d’abord un produit.', 'lang_saved': 'Parfait, je vous répondrai désormais en français 🇫🇷\nEnvoyez une photo du produit ou écrivez son nom.', 'ask_global': 'Je n’ai pas trouvé de résultat local fiable. Voulez-vous que je cherche dans les boutiques internationales ? 🌍', 'global_yes': 'Oui, chercher à l’international 🌍', 'global_no': 'Non, local uniquement', 'global_searching': '🌍 Je cherche les meilleures correspondances dans les boutiques internationales…', 'global_none': 'Je n’ai pas trouvé non plus de résultat international direct et fiable.', 'ask_not_found': 'Je n’ai pas trouvé exactement ce produit localement 😅\n\nQue voulez-vous faire ? 👇', 'opt_global': '🌍 Chercher à l’international', 'opt_similar': '🔄 Alternatives similaires', 'opt_no': 'Non merci 🙏', 'similar_searching': '🔄 Je cherche les meilleures alternatives similaires disponibles…', 'similar_none': 'Je n’ai pas trouvé d’alternative similaire avec un prix fiable pour le moment 😅 essayez une autre formulation.', 'declined_ok': 'Très bien 🙏 je reste disponible si vous avez besoin d’autre chose !', 'welcome_reply': 'Bonjour ! 🌟\nEnvoyez une photo du produit ou écrivez son nom, et je trouverai les meilleurs prix et magasins 🛒', 'thanks_reply': 'Avec plaisir ! 🌹 Envoyez-moi le prochain produit quand vous voulez.', 'lens_header': '✨ Voici les résultats correspondants que j’ai trouvés :', 'lens_none': '🔎 Je n’ai pas trouvé assez de résultats à partir de l’image, j’essaie une autre méthode…', 'market_from_phone': '✅ Votre pays a été défini à partir de votre numéro WhatsApp : {country}'}
MSG['es'] = {'identifying': '✨ Un momento… estoy identificando el producto y buscando las mejores opciones.', 'searching': '🔎 Buscando {q}…', 'not_found': 'No encontré un resultado disponible con un precio fiable 😅 prueba otra forma de escribirlo o envía una foto más clara.', 'identified_not_found': 'Identifiqué el producto ({p}), pero ahora mismo no encontré un precio fiable 😅 prueba a escribir el nombre de otra forma.', 'cant_identify': 'Lo intenté varias veces, pero no pude identificar el producto ni encontrar un resultado fiable. Envía una foto más clara o escribe el nombre del producto.', 'image_error': 'Hubo un pequeño problema al cargar la imagen 😅 vuelve a enviarla, por favor.', 'multi_text': 'Perfecto, encontré {c} productos. Preparando el carrito…', 'multi_images': 'Perfecto, detecté {c} productos. Preparando el carrito…', 'maps_body': '📍 ¿Quieres ver dónde encontrarlo cerca? Abre el mapa de abajo 👇', 'maps_btn': '📍 Abrir mapa', 'maps_body_loc': '📍 Tu última búsqueda fue ({p}). Abre el mapa para ver tiendas cercanas 👇', 'no_saved_product': 'Todavía no tengo ningún producto guardado 😅 busca un producto primero.', 'lang_saved': 'Perfecto, a partir de ahora te responderé en español 🇪🇸\nEnvía una foto del producto o escribe su nombre.', 'ask_global': 'No encontré un resultado local fiable. ¿Quieres que busque en tiendas internacionales? 🌍', 'global_yes': 'Sí, buscar internacionalmente 🌍', 'global_no': 'No, solo local', 'global_searching': '🌍 Buscando las mejores coincidencias en tiendas internacionales…', 'global_none': 'Tampoco encontré un resultado internacional directo y fiable.', 'ask_not_found': 'No encontré exactamente este producto a nivel local 😅\n\n¿Qué quieres hacer? 👇', 'opt_global': '🌍 Buscar internacionalmente', 'opt_similar': '🔄 Alternativas similares', 'opt_no': 'No, gracias 🙏', 'similar_searching': '🔄 Buscando las mejores alternativas similares disponibles…', 'similar_none': 'Ahora mismo no encontré alternativas similares con un precio fiable 😅 prueba otra forma de buscar.', 'declined_ok': 'Perfecto 🙏 aquí estoy cuando necesites algo más.', 'welcome_reply': '¡Hola! 🌟\nEnvía una foto del producto o escribe su nombre y buscaré los mejores precios y tiendas 🛒', 'thanks_reply': '¡De nada! 🌹 Envíame el siguiente producto cuando quieras.', 'lens_header': '✨ Estos son los resultados coincidentes que encontré:', 'lens_none': '🔎 No encontré suficientes resultados con la imagen; probaré otro método…', 'market_from_phone': '✅ Tu país se ha definido a partir de tu número de WhatsApp: {country}'}
MSG['pt'] = {'identifying': '✨ Um momento… estou identificando o produto e procurando as melhores opções.', 'searching': '🔎 Procurando {q}…', 'not_found': 'Não encontrei um resultado disponível com preço confiável 😅 tente escrever de outra forma ou envie uma foto mais nítida.', 'identified_not_found': 'Identifiquei o produto ({p}), mas não encontrei um preço confiável agora 😅 tente escrever o nome de outra forma.', 'cant_identify': 'Tentei várias vezes, mas não consegui identificar o produto nem encontrar um resultado confiável. Envie uma foto mais nítida ou escreva o nome do produto.', 'image_error': 'Houve um pequeno problema ao carregar a imagem 😅 envie-a novamente, por favor.', 'multi_text': 'Perfeito, encontrei {c} produtos. Montando o carrinho…', 'multi_images': 'Perfeito, identifiquei {c} produtos. Montando o carrinho…', 'maps_body': '📍 Quer ver onde encontrar perto de você? Abra o mapa abaixo 👇', 'maps_btn': '📍 Abrir mapa', 'maps_body_loc': '📍 Sua última busca foi ({p}). Abra o mapa para ver lojas próximas 👇', 'no_saved_product': 'Ainda não tenho nenhum produto salvo 😅 pesquise um produto primeiro.', 'lang_saved': 'Perfeito, a partir de agora vou responder em português 🇵🇹\nEnvie uma foto do produto ou escreva o nome.', 'ask_global': 'Não encontrei um resultado local confiável. Quer que eu pesquise em lojas internacionais? 🌍', 'global_yes': 'Sim, pesquisar internacionalmente 🌍', 'global_no': 'Não, apenas local', 'global_searching': '🌍 Procurando as melhores correspondências em lojas internacionais…', 'global_none': 'Também não encontrei um resultado internacional direto e confiável.', 'ask_not_found': 'Não encontrei exatamente este produto localmente 😅\n\nO que você gostaria de fazer? 👇', 'opt_global': '🌍 Pesquisar internacionalmente', 'opt_similar': '🔄 Alternativas semelhantes', 'opt_no': 'Não, obrigado 🙏', 'similar_searching': '🔄 Procurando as melhores alternativas semelhantes disponíveis…', 'similar_none': 'Não encontrei alternativas semelhantes com preço confiável agora 😅 tente outra busca.', 'declined_ok': 'Tudo certo 🙏 estou aqui quando precisar.', 'welcome_reply': 'Olá! 🌟\nEnvie uma foto do produto ou escreva o nome e eu encontro os melhores preços e lojas 🛒', 'thanks_reply': 'De nada! 🌹 Envie o próximo produto quando quiser.', 'lens_header': '✨ Estes são os resultados correspondentes que encontrei:', 'lens_none': '🔎 Não encontrei resultados suficientes pela imagem; vou tentar outro método…', 'market_from_phone': '✅ Seu país foi definido a partir do seu número do WhatsApp: {country}'}
MSG['tr'] = {'identifying': '✨ Bir saniye… ürünü tanımlıyor ve en iyi seçenekleri arıyorum.', 'searching': '🔎 {q} aranıyor…', 'not_found': 'Doğrulanabilir fiyatı olan uygun bir sonuç bulamadım 😅 farklı bir ifadeyle deneyin veya daha net bir fotoğraf gönderin.', 'identified_not_found': 'Ürünü ({p}) tanımladım ancak şu anda güvenilir bir fiyat bulamadım 😅 adını farklı şekilde yazmayı deneyin.', 'cant_identify': 'Birkaç kez denedim ancak ürünü tanımlayamadım veya güvenilir bir sonuç bulamadım. Daha net bir fotoğraf gönderin ya da ürün adını yazın.', 'image_error': 'Görsel yüklenirken küçük bir sorun oluştu 😅 lütfen tekrar gönderin.', 'multi_text': 'Tamam, {c} ürün buldum. Sepeti hazırlıyorum…', 'multi_images': 'Tamam, {c} ürün tespit ettim. Sepeti hazırlıyorum…', 'maps_body': '📍 Yakında nerede bulabileceğinizi görmek ister misiniz? Aşağıdaki haritayı açın 👇', 'maps_btn': '📍 Haritayı aç', 'maps_body_loc': '📍 Son aramanız ({p}) idi. Yakındaki mağazaları görmek için haritayı açın 👇', 'no_saved_product': 'Henüz kayıtlı bir ürün yok 😅 önce bir ürün arayın.', 'lang_saved': 'Harika, bundan sonra Türkçe yanıt vereceğim 🇹🇷\nÜrünün fotoğrafını gönderin veya adını yazın.', 'ask_global': 'Yerel olarak güvenilir bir sonuç bulamadım. Uluslararası mağazalarda arayayım mı? 🌍', 'global_yes': 'Evet, dünya çapında ara 🌍', 'global_no': 'Hayır, yalnızca yerel', 'global_searching': '🌍 Uluslararası mağazalarda en iyi eşleşmeleri arıyorum…', 'global_none': 'Uluslararası aramada da güvenilir ve doğrudan bir sonuç bulamadım.', 'ask_not_found': 'Bu ürünün tam aynısını yerel olarak bulamadım 😅\n\nNe yapmak istersiniz? 👇', 'opt_global': '🌍 Dünya çapında ara', 'opt_similar': '🔄 Benzer alternatifler', 'opt_no': 'Hayır, teşekkürler 🙏', 'similar_searching': '🔄 Mevcut en iyi benzer alternatifleri arıyorum…', 'similar_none': 'Şu anda güvenilir fiyatı olan benzer bir alternatif bulamadım 😅 farklı bir arama deneyin.', 'declined_ok': 'Tamamdır 🙏 ihtiyacınız olduğunda buradayım.', 'welcome_reply': 'Merhaba! 🌟\nÜrünün fotoğrafını gönderin veya adını yazın; en iyi fiyatları ve mağazaları bulayım 🛒', 'thanks_reply': 'Rica ederim! 🌹 Sıradaki ürünü istediğiniz zaman gönderin.', 'lens_header': '✨ Bulduğum eşleşen sonuçlar:', 'lens_none': '🔎 Görselden yeterli sonuç bulamadım, başka bir yöntem deniyorum…', 'market_from_phone': '✅ Ülkeniz WhatsApp numaranızdan belirlendi: {country}'}
MSG['ru'] = {'identifying': '✨ Один момент… определяю товар и ищу лучшие варианты.', 'searching': '🔎 Ищу {q}…', 'not_found': 'Не удалось найти доступный вариант с надежной ценой 😅 попробуйте другую формулировку или отправьте более четкое фото.', 'identified_not_found': 'Я определил товар ({p}), но сейчас не нашел надежную цену 😅 попробуйте написать название иначе.', 'cant_identify': 'Я попробовал несколько раз, но не смог определить товар или найти надежный результат. Отправьте более четкое фото или напишите название товара.', 'image_error': 'При загрузке изображения возникла небольшая ошибка 😅 отправьте его еще раз.', 'multi_text': 'Готово, найдено товаров: {c}. Собираю корзину…', 'multi_images': 'Готово, распознано товаров: {c}. Собираю корзину…', 'maps_body': '📍 Хотите посмотреть, где найти товар поблизости? Откройте карту ниже 👇', 'maps_btn': '📍 Открыть карту', 'maps_body_loc': '📍 Ваш последний поиск: ({p}). Откройте карту, чтобы увидеть ближайшие магазины 👇', 'no_saved_product': 'Пока нет сохраненного товара 😅 сначала выполните поиск товара.', 'lang_saved': 'Отлично, теперь я буду отвечать по-русски 🇷🇺\nОтправьте фото товара или напишите его название.', 'ask_global': 'Не удалось найти надежный локальный результат. Поискать в международных магазинах? 🌍', 'global_yes': 'Да, искать по всему миру 🌍', 'global_no': 'Нет, только локально', 'global_searching': '🌍 Ищу лучшие совпадения в международных магазинах…', 'global_none': 'В международном поиске также не найден надежный прямой результат.', 'ask_not_found': 'Точно такой товар локально не найден 😅\n\nЧто вы хотите сделать? 👇', 'opt_global': '🌍 Искать по всему миру', 'opt_similar': '🔄 Похожие варианты', 'opt_no': 'Нет, спасибо 🙏', 'similar_searching': '🔄 Ищу лучшие доступные похожие варианты…', 'similar_none': 'Сейчас не удалось найти похожие варианты с надежной ценой 😅 попробуйте другой запрос.', 'declined_ok': 'Хорошо 🙏 я здесь, когда понадоблюсь.', 'welcome_reply': 'Здравствуйте! 🌟\nОтправьте фото товара или напишите его название — я найду лучшие цены и магазины 🛒', 'thanks_reply': 'Пожалуйста! 🌹 Отправляйте следующий товар, когда захотите.', 'lens_header': '✨ Вот найденные совпадающие результаты:', 'lens_none': '🔎 По изображению недостаточно результатов, пробую другой способ…', 'market_from_phone': '✅ Ваша страна определена по номеру WhatsApp: {country}'}
MSG['zh'] = {'identifying': '✨ 稍等一下…正在识别商品并查找最佳选项。', 'searching': '🔎 正在查找 {q}…', 'not_found': '暂时没有找到带可靠价格的可购结果 😅 请换一种写法，或发送更清晰的图片。', 'identified_not_found': '已识别商品（{p}），但暂时没有找到可靠价格 😅 请尝试换一种名称搜索。', 'cant_identify': '我尝试了多次，但仍无法准确识别商品或找到可靠结果。请发送更清晰的图片，或直接输入商品名称。', 'image_error': '加载图片时出现了小问题 😅 请重新发送。', 'multi_text': '好的，找到 {c} 件商品，正在整理购物车…', 'multi_images': '好的，识别到 {c} 件商品，正在整理购物车…', 'maps_body': '📍 想看看附近哪里可以买到吗？请打开下方地图 👇', 'maps_btn': '📍 打开地图', 'maps_body_loc': '📍 您上次搜索的是（{p}）。打开地图即可查看附近商店 👇', 'no_saved_product': '目前还没有保存的商品 😅 请先搜索一个商品。', 'lang_saved': '好的，接下来我会用中文为您服务 🇨🇳\n发送商品图片或直接输入商品名称即可。', 'ask_global': '本地没有找到可靠结果。需要我继续搜索国际商店吗？ 🌍', 'global_yes': '是，搜索全球商店 🌍', 'global_no': '否，仅搜索本地', 'global_searching': '🌍 正在国际商店中查找最佳匹配结果…', 'global_none': '国际搜索中也没有找到可靠的直接购买结果。', 'ask_not_found': '本地没有找到完全相同的商品 😅\n\n您希望我接下来怎么做？ 👇', 'opt_global': '🌍 搜索全球商店', 'opt_similar': '🔄 查看相似替代品', 'opt_no': '不用了，谢谢 🙏', 'similar_searching': '🔄 正在查找最佳相似替代品…', 'similar_none': '暂时没有找到带可靠价格的相似替代品 😅 请尝试其他搜索方式。', 'declined_ok': '好的 🙏 随时需要都可以找我。', 'welcome_reply': '您好！🌟\n发送商品图片或输入商品名称，我会帮您查找最佳价格和商店 🛒', 'thanks_reply': '不客气！🌹 随时发送下一个商品。', 'lens_header': '✨ 找到以下匹配结果：', 'lens_none': '🔎 图片结果不足，正在尝试其他方式…', 'market_from_phone': '✅ 已根据您的 WhatsApp 号码确定国家/地区：{country}'}
MSG['fr'].update({'cart_comparing': '🧺 {c} articles trouvés… je compare le panier complet entre les boutiques pour trouver l’option la plus simple et avantageuse !', 'cart_expired': 'Cette liste de panier a expiré 😅 renvoyez les articles et je la reconstruirai.', 'cart_not_anywhere': '⛔ Introuvable dans les boutiques listées : {items}', 'cart_pick_prompt': 'Choisissez une boutique et je vous enverrai tous les articles avec leurs liens directs — une seule commande, un seul panier 👇', 'cart_plan_total': '💰 Total du plan : {t}', 'cart_session_tip': '💡 Ajoutez le premier article avec le bouton, puis cherchez les autres dans la même boutique afin de tout garder dans un seul panier.', 'cart_store_button': 'Choisir boutique', 'cart_total': '💰 Total du panier : {t}', 'chat_redirect': 'Je suis là 🙌 Envoyez le nom ou la photo d’un produit pour comparer les prix, ou indiquez le service recherché 🛒', 'compare_searching': '⚖️ Votre demande est générale ; je compare d’abord les meilleures marques et options !', 'list_button': 'Choisir produit', 'pick_prompt': 'Choisissez un produit dans la liste et je chercherai les meilleurs prix disponibles 👇'})
MSG['es'].update({'cart_comparing': '🧺 Encontré {c} artículos… comparo la cesta completa entre tiendas para encontrar la opción más práctica y conveniente.', 'cart_expired': 'Esa lista de cesta caducó 😅 envía los artículos de nuevo y la reconstruyo.', 'cart_not_anywhere': '⛔ No encontrado en ninguna tienda de la lista: {items}', 'cart_pick_prompt': 'Elige una tienda y te enviaré todos los artículos con sus enlaces directos — un pedido, una sola cesta 👇', 'cart_plan_total': '💰 Total del plan: {t}', 'cart_session_tip': '💡 Añade el primer artículo desde el botón y luego busca los demás en la misma tienda para mantenerlos en una sola cesta.', 'cart_store_button': 'Elegir tienda', 'cart_total': '💰 Total de la cesta: {t}', 'chat_redirect': 'Estoy aquí 🙌 Envía el nombre o la foto de un producto para comparar precios, o escribe el servicio que necesitas 🛒', 'compare_searching': '⚖️ Tu solicitud es general; primero compararé las mejores marcas y opciones.', 'list_button': 'Elegir producto', 'pick_prompt': 'Elige un producto de la lista y buscaré los mejores precios disponibles 👇'})
MSG['pt'].update({'cart_comparing': '🧺 Encontrei {c} itens… estou comparando o carrinho completo entre lojas para achar a opção mais prática e vantajosa!', 'cart_expired': 'Essa lista do carrinho expirou 😅 envie os itens novamente e eu refaço.', 'cart_not_anywhere': '⛔ Não encontrado em nenhuma loja da lista: {items}', 'cart_pick_prompt': 'Escolha uma loja e enviarei todos os itens com links diretos — um pedido, um único carrinho 👇', 'cart_plan_total': '💰 Total do plano: {t}', 'cart_session_tip': '💡 Adicione o primeiro item pelo botão e depois procure os demais na mesma loja para manter tudo em um único carrinho.', 'cart_store_button': 'Escolher loja', 'cart_total': '💰 Total do carrinho: {t}', 'chat_redirect': 'Estou aqui 🙌 Envie o nome ou a foto de um produto para comparar preços, ou escreva o serviço de que precisa 🛒', 'compare_searching': '⚖️ Seu pedido é geral; primeiro vou comparar as melhores marcas e opções!', 'list_button': 'Escolher produto', 'pick_prompt': 'Escolha um produto da lista e eu buscarei os melhores preços disponíveis 👇'})
MSG['tr'].update({'cart_comparing': '🧺 {c} ürün buldum… en kolay ve avantajlı seçeneği bulmak için tüm sepeti mağazalar arasında karşılaştırıyorum!', 'cart_expired': 'Bu sepet listesi artık geçerli değil 😅 ürünleri yeniden gönderin, tekrar hazırlayayım.', 'cart_not_anywhere': '⛔ Listelenen mağazaların hiçbirinde bulunamadı: {items}', 'cart_pick_prompt': 'Bir mağaza seçin; tüm ürünleri doğrudan bağlantılarıyla tek sipariş ve tek sepet halinde göndereyim 👇', 'cart_plan_total': '💰 Plan toplamı: {t}', 'cart_session_tip': '💡 İlk ürünü düğmeden ekleyin, ardından diğerlerini aynı mağazada arayın; böylece hepsi tek sepette kalır.', 'cart_store_button': 'Mağaza seç', 'cart_total': '💰 Sepet toplamı: {t}', 'chat_redirect': 'Buradayım 🙌 Fiyat karşılaştırması için ürün adı/fotoğrafı gönderin veya ihtiyacınız olan hizmeti yazın 🛒', 'compare_searching': '⚖️ İsteğiniz genel; önce en iyi marka ve seçenekleri karşılaştırıyorum!', 'list_button': 'Ürün seç', 'pick_prompt': 'Listeden bir ürün seçin, mevcut en iyi fiyatları arayayım 👇'})
MSG['ru'].update({'cart_comparing': '🧺 Найдено товаров: {c}. Сравниваю всю корзину по магазинам, чтобы найти самый удобный и выгодный вариант!', 'cart_expired': 'Срок этой корзины истёк 😅 отправьте список товаров ещё раз, и я соберу её заново.', 'cart_not_anywhere': '⛔ Не найдено ни в одном магазине из списка: {items}', 'cart_pick_prompt': 'Выберите магазин — я отправлю все товары с прямыми ссылками, чтобы оформить один заказ и одну корзину 👇', 'cart_plan_total': '💰 Общая сумма плана: {t}', 'cart_session_tip': '💡 Добавьте первый товар кнопкой, затем найдите остальные в том же магазине, чтобы всё осталось в одной корзине.', 'cart_store_button': 'Выбрать магазин', 'cart_total': '💰 Сумма корзины: {t}', 'chat_redirect': 'Я здесь 🙌 Отправьте название/фото товара для сравнения цен или напишите, какая услуга вам нужна 🛒', 'compare_searching': '⚖️ Запрос общий — сначала сравню лучшие бренды и варианты!', 'list_button': 'Выбрать товар', 'pick_prompt': 'Выберите товар из списка, и я найду лучшие доступные цены 👇'})
MSG['zh'].update({'cart_comparing': '🧺 找到 {c} 件商品…正在对比不同商店的整份购物清单，帮您找更省事、更划算的方案！', 'cart_expired': '这份购物清单已过期 😅 请重新发送商品，我会马上重新整理。', 'cart_not_anywhere': '⛔ 以下商品在所列商店中都未找到：{items}', 'cart_pick_prompt': '请选择一家商店，我会把全部商品的直接链接发给您 — 一次下单，一个购物车 👇', 'cart_plan_total': '💰 整体方案总计：{t}', 'cart_session_tip': '💡 先通过按钮加入第一件商品，再在同一家商店里搜索其余商品，这样可以保留在同一个购物车中。', 'cart_store_button': '选择商店', 'cart_total': '💰 购物车总计：{t}', 'chat_redirect': '我在这里 🙌 发送商品名称/图片即可比较价格，也可以直接告诉我您需要的服务 🛒', 'compare_searching': '⚖️ 您的需求比较宽泛，我会先比较最合适的品牌和选项！', 'list_button': '选择商品', 'pick_prompt': '请从列表中选择一件商品，我会继续查找最佳可用价格 👇'})
LANGUAGE_NAMES_EN = {'ar': 'Arabic', 'en': 'English', 'fr': 'French', 'es': 'Spanish', 'pt': 'Portuguese', 'tr': 'Turkish', 'ru': 'Russian', 'zh': 'Simplified Chinese', 'hi': 'Hindi', 'ur': 'Urdu', 'de': 'German', 'it': 'Italian', 'nl': 'Dutch', 'pl': 'Polish', 'ja': 'Japanese', 'ko': 'Korean', 'fa': 'Persian', 'uk': 'Ukrainian', 'el': 'Greek', 'he': 'Hebrew', 'th': 'Thai', 'vi': 'Vietnamese', 'id': 'Indonesian', 'ms': 'Malay', 'bn': 'Bengali', 'ta': 'Tamil', 'te': 'Telugu', 'mr': 'Marathi', 'ne': 'Nepali', 'sv': 'Swedish', 'no': 'Norwegian', 'da': 'Danish', 'fi': 'Finnish', 'cs': 'Czech', 'sk': 'Slovak', 'hu': 'Hungarian', 'ro': 'Romanian', 'bg': 'Bulgarian', 'hr': 'Croatian', 'sr': 'Serbian', 'sl': 'Slovenian', 'lt': 'Lithuanian', 'lv': 'Latvian', 'et': 'Estonian', 'ca': 'Catalan', 'sw': 'Swahili', 'af': 'Afrikaans', 'sq': 'Albanian', 'hy': 'Armenian', 'ka': 'Georgian', 'az': 'Azerbaijani', 'kk': 'Kazakh', 'uz': 'Uzbek', 'tl': 'Filipino', 'fil': 'Filipino'}
LANGUAGE_SELECTION = {'lang_ar': ('ar', 'العربية 🇰🇼'), 'lang_en': ('en', 'English 🇬🇧'), 'lang_fr': ('fr', 'Français 🇫🇷'), 'lang_es': ('es', 'Español 🇪🇸'), 'lang_pt': ('pt', 'Português 🇵🇹'), 'lang_tr': ('tr', 'Türkçe 🇹🇷'), 'lang_ru': ('ru', 'Русский 🇷🇺'), 'lang_zh': ('zh', '中文 🇨🇳'), 'lang_hi': ('hi', 'हिन्दी 🇮🇳'), 'lang_ur': ('ur', 'اردو 🇵🇰')}
LANG_INSTR = {'ar': 'رد باللغة العربية فقط حتى لو كان اسم البحث بالإنجليزية: اكتب سطر 📦 ووصف المنتج بالعربية، مع إبقاء اسم البراند والموديل اللاتيني كما هو. أسماء المتاجر تُكتب بأشهر صيغة متداولة لها.', 'en': "Respond ONLY in English. Keep the exact response format and emojis. Keep brand/model names unchanged when appropriate. Keep local prices in the user's local currency.", 'fr': 'Répondez UNIQUEMENT en français pour l’interface et les descriptions. Conservez les marques, modèles, tailles et références dans leur forme d’origine si nécessaire. Gardez exactement le même format et les mêmes emojis.', 'es': 'Responde ÚNICAMENTE en español para la interfaz y las descripciones. Mantén marcas, modelos, tallas y referencias en su forma original cuando corresponda. Conserva exactamente el mismo formato y emojis.', 'pt': 'Responda SOMENTE em português para a interface e descrições. Mantenha marcas, modelos, tamanhos e referências na forma original quando apropriado. Preserve exatamente o mesmo formato e emojis.', 'tr': 'Arayüz ve açıklama metinlerinde SADECE Türkçe yanıt ver. Marka/model, beden ve referans kodlarını gerektiğinde özgün biçiminde tut. Aynı formatı ve emojileri koru.', 'ru': 'Отвечайте ТОЛЬКО на русском языке в интерфейсе и описаниях. Названия брендов, моделей, размеров и артикулов при необходимости сохраняйте в исходном виде. Сохраняйте тот же формат и эмодзи.', 'zh': '界面和描述文字仅使用简体中文。品牌名、型号、尺寸和 SKU 等必要信息保持原样。严格保留相同的输出格式和表情符号。', 'hi': "Respond ONLY in Hindi (Devanagari) for all UI and descriptive text. Keep brand/model names in their normal Latin form when appropriate. Keep the exact response format and emojis. Keep local prices in the user's local currency.", 'ur': "Respond ONLY in Urdu for all UI and descriptive text. Keep brand/model names in their normal Latin form when appropriate. Keep the exact response format and emojis. Keep local prices in the user's local currency."}
DYNAMIC_UI_TRANSLATION_CACHE = {}
DYNAMIC_UI_TRANSLATION_LOCK = threading.Lock()
DYNAMIC_UI_TRANSLATION_MAX = 4000

def language_name_en(lang):
    code = str(lang or 'en').strip().lower().replace('_', '-').split('-')[0]
    return LANGUAGE_NAMES_EN.get(code) or f'language code {code}'

def lang_instr(lang):
    code = str(lang or 'en').strip().lower().replace('_', '-').split('-')[0]
    if code in LANG_INSTR:
        return LANG_INSTR[code]
    name = language_name_en(code)
    return f'Respond ONLY in {name}. Keep the exact response format and emojis. Do not translate or alter brand names, model names, SKUs, sizes, URLs, phone numbers, or currency codes unless normal grammar requires surrounding words to change.'

def _dynamic_translate_ui(text, lang):
    code = str(lang or 'en').strip().lower().replace('_', '-').split('-')[0]
    source = str(text or '')
    if not source or code in MSG or code == 'en':
        return source
    key = (code, source)
    with DYNAMIC_UI_TRANSLATION_LOCK:
        hit = DYNAMIC_UI_TRANSLATION_CACHE.get(key)
    if hit:
        return hit
    name = language_name_en(code)
    system = f'Translate the following WhatsApp bot UI text into {name}. Return ONLY the translated text, no quotes and no explanation. Preserve emojis, line breaks, URLs, phone numbers, prices, currency codes, brand names, model names, SKUs and product names exactly when appropriate. Do not add information.'
    try:
        raw, _ = call_gemini([{'text': source}], system=system, use_search=False)
        translated = (raw or '').strip()
        translated = re.sub('^["“”]+|["“”]+$', '', translated).strip()
        if not translated:
            translated = source
    except Exception as e:
        print(f'DYNAMIC UI TRANSLATE ERR lang={code}: {e}')
        translated = source
    with DYNAMIC_UI_TRANSLATION_LOCK:
        if len(DYNAMIC_UI_TRANSLATION_CACHE) >= DYNAMIC_UI_TRANSLATION_MAX:
            DYNAMIC_UI_TRANSLATION_CACHE.clear()
        DYNAMIC_UI_TRANSLATION_CACHE[key] = translated
    return translated

def T(lang, key, **kw):
    code = str(lang or 'en').strip().lower().replace('_', '-').split('-')[0]
    table = MSG.get(code)
    if table:
        value = table.get(key, MSG['en'].get(key, MSG['ar'].get(key, key)))
        return value.format(**kw) if kw else value
    value = MSG['en'].get(key, MSG['ar'].get(key, key))
    rendered = value.format(**kw) if kw else value
    return _dynamic_translate_ui(rendered, code)
UI_TEXT = {'price_at_store': {'ar': '💰 السعر عند المتجر', 'en': '💰 Price at store', 'fr': '💰 Prix en boutique', 'es': '💰 Precio en tienda', 'pt': '💰 Preço na loja', 'tr': '💰 Fiyat mağazada', 'ru': '💰 Цена в магазине', 'zh': '💰 商店价格', 'hi': '💰 कीमत स्टोर पर', 'ur': '💰 قیمت اسٹور پر'}, 'similar_to': {'ar': 'بدائل مشابهة: {base}', 'en': 'Similar to: {base}', 'fr': 'Similaire à : {base}', 'es': 'Similar a: {base}', 'pt': 'Semelhante a: {base}', 'tr': 'Benzeri: {base}', 'ru': 'Похожие варианты: {base}', 'zh': '相似商品：{base}', 'hi': 'मिलते-जुलते विकल्प: {base}', 'ur': 'ملتے جلتے متبادل: {base}'}, 'more_store_q': {'ar': '✨ تبي أشوف لك متاجر إضافية لنفس المنتج؟', 'en': '✨ Want more stores for the same product?', 'fr': '✨ Voir d’autres boutiques pour le même produit ?', 'es': '✨ ¿Quieres ver más tiendas para el mismo producto?', 'pt': '✨ Quer ver mais lojas para o mesmo produto?', 'tr': '✨ Aynı ürün için daha fazla mağaza bulayım mı?', 'ru': '✨ Найти еще магазины с этим товаром?', 'zh': '✨ 要继续查找更多销售同款商品的商店吗？', 'hi': '✨ इसी प्रोडक्ट के लिए और स्टोर खोजूँ?', 'ur': '✨ اسی پروڈکٹ کے لیے مزید اسٹورز تلاش کروں؟'}, 'search_more': {'ar': '🔎 ابحث أكثر', 'en': '🔎 Search more', 'fr': '🔎 Plus de résultats', 'es': '🔎 Buscar más', 'pt': '🔎 Buscar mais', 'tr': '🔎 Daha fazla ara', 'ru': '🔎 Найти еще', 'zh': '🔎 查找更多', 'hi': '🔎 और खोजें', 'ur': '🔎 مزید تلاش'}, 'looking_more': {'ar': '🔎 أدور لك على متاجر إضافية...', 'en': '🔎 Looking for more stores...', 'fr': '🔎 Recherche d’autres boutiques…', 'es': '🔎 Buscando más tiendas…', 'pt': '🔎 Procurando mais lojas…', 'tr': '🔎 Daha fazla mağaza aranıyor…', 'ru': '🔎 Ищу дополнительные магазины…', 'zh': '🔎 正在查找更多商店…', 'hi': '🔎 और स्टोर ढूँढ रहा हूँ...', 'ur': '🔎 مزید اسٹورز تلاش کر رہا ہوں...'}, 'all_results': {'ar': '✅ هذي تقريباً كل النتائج المطابقة اللي قدرت ألقاها حالياً.', 'en': "✅ That's about all the matching store results I could find right now.", 'fr': '✅ C’est à peu près tout ce que j’ai pu trouver pour le moment.', 'es': '✅ Estos son prácticamente todos los resultados coincidentes que pude encontrar ahora.', 'pt': '✅ Estes são praticamente todos os resultados correspondentes que encontrei agora.', 'tr': '✅ Şimdilik bulabildiğim eşleşen mağaza sonuçları bunlar.', 'ru': '✅ Это почти все подходящие результаты, которые удалось найти сейчас.', 'zh': '✅ 目前能找到的匹配商店结果基本都在这里了。', 'hi': '✅ अभी लगभग इतने ही मिलते-जुलते स्टोर नतीजे मिले।', 'ur': '✅ فی الحال تقریباً یہی تمام ملتے جلتے اسٹور نتائج مل سکے۔'}, 'expired': {'ar': 'انتهت صلاحية البحث 😅 ابحث عن المنتج مرة ثانية.', 'en': 'That search expired 😅 search for the product again.', 'fr': 'Cette recherche a expiré 😅 relancez la recherche du produit.', 'es': 'Esa búsqueda caducó 😅 vuelve a buscar el producto.', 'pt': 'Essa busca expirou 😅 pesquise o produto novamente.', 'tr': 'Bu aramanın süresi doldu 😅 ürünü tekrar arayın.', 'ru': 'Срок этого поиска истек 😅 выполните поиск товара снова.', 'zh': '这次搜索已过期 😅 请重新搜索商品。', 'hi': 'यह खोज समाप्त हो गई 😅 प्रोडक्ट दोबारा खोजें।', 'ur': 'یہ تلاش ختم ہو گئی 😅 پروڈکٹ دوبارہ تلاش کریں۔'}, 'store': {'ar': 'المتجر', 'en': 'Store', 'fr': 'Boutique', 'es': 'Tienda', 'pt': 'Loja', 'tr': 'Mağaza', 'ru': 'Магазин', 'zh': '商店', 'hi': 'स्टोर', 'ur': 'اسٹور'}, 'items': {'ar': 'أصناف', 'en': 'items', 'fr': 'articles', 'es': 'artículos', 'pt': 'itens', 'tr': 'ürün', 'ru': 'товаров', 'zh': '件商品', 'hi': 'आइटम', 'ur': 'آئٹمز'}, 'completes': {'ar': 'يكمل', 'en': 'completes', 'fr': 'complète', 'es': 'completa', 'pt': 'completa', 'tr': 'tamamlar', 'ru': 'дополняет', 'zh': '补全', 'hi': 'पूरा करता है', 'ur': 'مکمل کرتا ہے'}, 'recommended': {'ar': 'منتج مقترح', 'en': 'Recommended option', 'fr': 'Option recommandée', 'es': 'Opción recomendada', 'pt': 'Opção recomendada', 'tr': 'Önerilen seçenek', 'ru': 'Рекомендуемый вариант', 'zh': '推荐选项', 'hi': 'सुझाया गया विकल्प', 'ur': 'تجویز کردہ آپشن'}}

def U(lang, key, **kw):
    code = str(lang or 'en').strip().lower().replace('_', '-').split('-')[0]
    table = UI_TEXT.get(key) or {}
    if code in table:
        value = table[code]
        return value.format(**kw) if kw else value
    value = table.get('en') or key
    rendered = value.format(**kw) if kw else value
    return _dynamic_translate_ui(rendered, code)
_LANG_DETECT_CACHE = {}
_LANG_DETECT_LOCK = threading.Lock()

def _normalize_lang_code(code):
    code = str(code or '').strip().lower().replace('_', '-')
    if not code:
        return None
    code = code.split('-')[0]
    aliases = {'iw': 'he', 'in': 'id', 'fil': 'tl', 'zh-cn': 'zh', 'zh-tw': 'zh'}
    return aliases.get(code, code) if re.fullmatch('[a-z]{2,3}', code) else None

def _fast_language_hint(text):
    t = str(text or '').strip()
    low = t.casefold()
    if not t:
        return None
    if re.search('[\\u3040-\\u30FF]', t):
        return 'ja'
    if re.search('[\\uAC00-\\uD7AF]', t):
        return 'ko'
    if re.search('[\\u4E00-\\u9FFF]', t):
        return 'zh'
    if re.search('[\\u0590-\\u05FF]', t):
        return 'he'
    if re.search('[\\u0E00-\\u0E7F]', t):
        return 'th'
    if re.search('[\\u0370-\\u03FF]', t):
        return 'el'
    if re.search('[\\u10A0-\\u10FF]', t):
        return 'ka'
    if re.search('[\\u0530-\\u058F]', t):
        return 'hy'
    if re.search('[іїєґІЇЄҐ]', t):
        return 'uk'
    if re.search('[\\u0400-\\u04FF]', t):
        return 'ru'
    if re.search('[\\u0980-\\u09FF]', t):
        return 'bn'
    if re.search('[\\u0B80-\\u0BFF]', t):
        return 'ta'
    if re.search('[\\u0C00-\\u0C7F]', t):
        return 'te'
    if re.search('[\\u0600-\\u06FF]', t):
        if re.search('[ٹڈڑںھہءے]', t) or re.search('\\b(ہے|میں|کے|کی|کو|اور|چاہیے|قیمت)\\b', t):
            return 'ur'
        if re.search('\\b(است|برای|می|قیمت|کجا|لطفا|لطفاً)\\b', t) or re.search('[ژگپ]', t):
            return 'fa'
        if re.search('\\b(ابي|أبي|ابغى|اريد|أريد|ابحث|بحث|سعر|وين|مرحبا|السلام|شكرا|شكراً|خدمة|منتج)\\b', low):
            return 'ar'
    if '¿' in t or '¡' in t or 'ñ' in low:
        return 'es'
    if re.search('[ãõ]', low):
        return 'pt'
    if re.search('[ğış]', low):
        return 'tr'
    if 'ß' in low:
        return 'de'
    tokens = re.findall('[A-Za-zÀ-ÖØ-öø-ÿİıĞğŞşÇç]+', low)
    if not tokens:
        return None
    sets = {'en': {'hello', 'hi', 'please', 'find', 'search', 'price', 'store', 'service', 'want', 'need', 'thanks', 'thank', 'where', 'best', 'for', 'with'}, 'fr': {'bonjour', 'salut', 'merci', 'cherche', 'chercher', 'trouve', 'trouver', 'prix', 'magasin', 'service', 'je', 'veux', 'pour', 'avec', 'où'}, 'es': {'hola', 'gracias', 'busco', 'buscar', 'encuentra', 'encontrar', 'precio', 'tienda', 'servicio', 'quiero', 'para', 'con', 'donde', 'dónde'}, 'pt': {'olá', 'ola', 'obrigado', 'obrigada', 'procuro', 'buscar', 'encontrar', 'preço', 'preco', 'loja', 'serviço', 'servico', 'quero', 'para', 'com', 'onde'}, 'tr': {'merhaba', 'teşekkür', 'tesekkur', 'ara', 'arıyorum', 'ariyorum', 'fiyat', 'mağaza', 'magaza', 'hizmet', 'istiyorum', 'için', 'icin', 'ile'}, 'de': {'hallo', 'danke', 'suche', 'finden', 'preis', 'laden', 'geschäft', 'geschaft', 'service', 'ich', 'möchte', 'mochte', 'für', 'fur', 'mit', 'wo'}, 'it': {'ciao', 'grazie', 'cerco', 'cerca', 'trovare', 'prezzo', 'negozio', 'servizio', 'voglio', 'vorrei', 'per', 'con', 'dove'}, 'nl': {'hallo', 'dank', 'zoek', 'vinden', 'prijs', 'winkel', 'dienst', 'wil', 'voor', 'met', 'waar'}, 'pl': {'cześć', 'czesc', 'dziękuję', 'dziekuje', 'szukam', 'znajdź', 'znajdz', 'cena', 'sklep', 'usługa', 'usluga', 'chcę', 'chce', 'gdzie'}, 'id': {'halo', 'terima', 'kasih', 'cari', 'harga', 'toko', 'layanan', 'saya', 'ingin', 'untuk', 'dengan', 'dimana'}, 'ms': {'hai', 'terima', 'kasih', 'cari', 'harga', 'kedai', 'perkhidmatan', 'saya', 'mahu', 'untuk', 'dengan', 'di mana'}}
    scores = {code: sum((1 for tok in tokens if tok in words)) for code, words in sets.items()}
    best = max(scores, key=scores.get)
    if scores[best] >= 2:
        return best
    if len(tokens) <= 2 and scores[best] == 1 and (tokens[0] in sets[best]):
        return best
    return None

def detect_lang(text, current_lang=None):
    raw_text = str(text or '').strip()
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
        words = re.findall('[^\\W\\d_]+', raw_text, flags=re.UNICODE)
        alpha_chars = sum((ch.isalpha() for ch in raw_text))
        if alpha_chars < 2:
            result = None
        else:
            system = 'Detect the dominant NATURAL LANGUAGE of the user\'s WhatsApp text.\nReturn ONLY compact JSON:\n{"code":"xx","name":"English language name","confidence":0.00,"natural":true}\nRules:\n- code = ISO 639-1 two-letter code when available.\n- Detect the language of the user\'s actual wording/instructions, not brand names, model names, SKUs, URLs or store names.\n- If the text is only a brand/model/SKU/product code and has no meaningful natural-language wording, set natural=false.\n- For mixed text, choose the dominant language used to address the bot.\n- Do not translate or answer the message.'
            try:
                out, _ = call_gemini([{'text': raw_text[:500]}], system=system, use_search=False)
                m = re.search('\\{.*\\}', out or '', flags=re.S)
                data = json.loads(m.group(0)) if m else {}
                code = _normalize_lang_code(data.get('code'))
                name = str(data.get('name') or '').strip()
                confidence = float(data.get('confidence') or 0)
                natural = bool(data.get('natural'))
                if code and name:
                    LANGUAGE_NAMES_EN.setdefault(code, name)
                result = code if code and natural and (confidence >= 0.6) else None
            except Exception as e:
                print(f'LANG DETECT ERR: {e}')
                result = None
    with _LANG_DETECT_LOCK:
        if len(_LANG_DETECT_CACHE) > 3000:
            _LANG_DETECT_CACHE.clear()
        _LANG_DETECT_CACHE[key] = result or ''
    return result

def auto_language_from_text(phone, text, persist=True):
    previous = USER_LANG.get(phone)
    detected = detect_lang(text, previous)
    if not detected:
        if previous:
            return (previous, False)
        market = market_for_user(phone)
        detected = _normalize_lang_code(market.get('search_hl')) or 'en'
    changed = previous != detected
    USER_LANG[phone] = detected
    if persist and changed:
        save_user_preferences(phone)
    if changed:
        print(f"AUTO LANGUAGE: {phone} {previous or '-'} -> {detected} ({language_name_en(detected)})")
    return (detected, changed)
SYSTEM_PROMPT = '\nأنت مساعد تسوق عالمي يعتمد سوق المستخدم المحلي الحالي. السوق المحلي هو أهم جزء في الخدمة ويجب البحث فيه بقوة قبل النتائج الأجنبية.\n\nأولاً حدد نوع الطلب:\n\n【الحالة 1】منتج محدد بعلامة/موديل واضح:\nقارن نفس المنتج ونفس المواصفات. رتب جغرافياً دائماً: بلد المستخدم المحلي أولاً، ثم الولايات المتحدة، ثم الصين فقط. داخل كل سوق رتب من الأرخص إلى الأغلى.\n📦 [اسم المنتج]\n✅ [المتجر] — [السعر الرقمي + العملة]\n• [المتجر] — [السعر الرقمي + العملة]\n\nقاعدة المحلي: ابحث في المتاجر المتخصصة القوية في بلد المستخدم ثم المنصات العامة، ووسّع لأي متجر محلي حقيقي مفهرس في Google Shopping/Search. لا تحصر البحث في قائمة ثابتة، ولا تفترض أن .com يعني متجر أمريكي؛ قد يكون متجراً محلياً.\n\n【الحالة 2】طلب عام بدون براند/موديل محدد:\nلا تبحث عن الأرخص فقط. اقترح أفضل الخيارات المناسبة والمتاحة في سوق المستخدم المحلي، وباللغة التي طلبها المستخدم، ثم اسمح له باختيار منتج للبحث عن أسعاره.\n\n【الحالة 3】طلب خدمة:\nابحث محلياً في بلد المستخدم. لا تكتب رقم هاتف إلا إذا ظهر حرفياً في نتائج البحث.\n\n【الحالة 4】سؤال معلوماتي عن منتج:\nأجب عن السؤال مباشرة ولا تعرض مقارنة أسعار إلا إذا طلب المستخدم ذلك.\n\nقواعد جودة صارمة:\n- السوق المحلي أولاً دائماً، وبعده الولايات المتحدة ثم الصين فقط؛ ارفض أي دولة رابعة.\n- لا تجعل السعر الأرخص في أمريكا/الصين يتقدم على عرض محلي صحيح.\n- قارن نفس المواصفات فقط: الحجم/السعة/الوزن/الموديل واللون إذا كان يؤثر في السعر.\n- كل رابط شراء يجب أن يكون صفحة منتج مباشرة، وليس Google ولا صفحة بحث/تصنيف.\n- لا تخترع سعراً أو متجراً. استخدم السعر الموجود في نتيجة البحث الحالية.\n- اكتب السعر بالعملة الصحيحة للسوق كما تظهر، والتطبيق يتولى التنسيق والتحويل عند الحاجة.\n- استبعد Heureka / heureka.cz / heureka.sk دائماً لأنه موقع مقارنة وليس متجراً مباشراً. لا تستبعد Eureka الكويتية.\n- لا تفترض أن رمز $ يعني USD دائماً؛ احترم سياق بلد المستخدم والعملة التي يحددها التطبيق.\n- في البحث المحلي استخدم اسم المنتج بصياغة المستخدم + الاسم التجاري الإنجليزي + لغة التجارة المحلية عندما تفيد الفهرسة.\n\nفي نتائج المتاجر أضف سطر LINKS داخلياً لربط أسماء المتاجر بالمصادر، ولا تعرض روابط خام للمستخدم.\nلغة الرد: التزم حصراً بلغة المستخدم المحددة في الواجهة.\n'

def fetch_html(url):
    if not url or not url.startswith('http'):
        return ''
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200 and len(r.text) > 1500:
            return r.text
    except Exception as e:
        print(f'fetch err {e} {url[:80]}')
    return ''

def parse_product_data(html, url):
    if not html:
        return None
    soup = BeautifulSoup(html, 'lxml')
    data = {'price': None, 'available': True, 'is_product': True, 'title': '', 'image_url': '', 'currency': ''}
    ld_products = 0
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            raw = script.string
            if not raw:
                continue
            j = json.loads(raw)
            objs = j if isinstance(j, list) else [j]
            flat = []
            for o in objs:
                if isinstance(o, dict) and o.get('@graph'):
                    flat.extend(o['@graph'])
                else:
                    flat.append(o)
            for obj in flat:
                if not isinstance(obj, dict):
                    continue
                t = str(obj.get('@type', ''))
                if 'Product' in t or 'ProductGroup' in t:
                    ld_products += 1
                    offers = obj.get('offers') or {}
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    p = offers.get('price') or offers.get('lowPrice') or offers.get('highPrice')
                    if p:
                        try:
                            data['price'] = _normalize_price_token(str(p), str(offers.get('priceCurrency') or data.get('currency') or ''))
                        except Exception:
                            pass
                    if not data['currency']:
                        cur = str(offers.get('priceCurrency') or '').upper().strip()
                        if cur in KNOWN_CURRENCY_CODES:
                            data['currency'] = cur
                    av = str(offers.get('availability', '')).lower()
                    if 'outofstock' in av or 'discontinued' in av or 'soldout' in av:
                        data['available'] = False
                    if not data['title']:
                        data['title'] = str(obj.get('name', ''))[:80]
                    if not data['image_url']:
                        image = obj.get('image')
                        if isinstance(image, list) and image:
                            image = image[0]
                        if isinstance(image, dict):
                            image = image.get('url') or image.get('contentUrl')
                        if isinstance(image, str) and image.startswith('http'):
                            data['image_url'] = image
        except Exception:
            continue
    if ld_products >= 4:
        data['is_product'] = False
    low_text = soup.get_text(' ', strip=True).lower()[:6000]
    if any((ph in low_text for ph in OOS_PHRASES)):
        if low_text.count('غير متوفر') > 0 or low_text.count('out of stock') > 0:
            data['available'] = False
    if not data['price']:
        m = soup.find('meta', property='product:price:amount')
        if m and m.get('content'):
            try:
                data['price'] = float(m['content'])
            except Exception:
                pass
    if not data['currency']:
        m = soup.find('meta', property='product:price:currency')
        if m and m.get('content'):
            cur = str(m['content']).upper().strip()
            if cur in KNOWN_CURRENCY_CODES:
                data['currency'] = cur
    if not data['price']:
        price_candidates = []
        selectors = [('meta[itemprop="price"]', 'content'), ('meta[name="price"]', 'content'), ('meta[property="og:price:amount"]', 'content'), ('meta[name="twitter:data1"]', 'content')]
        for sel, attr in selectors:
            node = soup.select_one(sel)
            if node and node.get(attr):
                price_candidates.append(str(node.get(attr)))
        for sel in ('.a-price .a-offscreen', '.a-price-whole', '[itemprop="price"]', '.x-price-primary span'):
            node = soup.select_one(sel)
            if node:
                price_candidates.append(node.get_text(' ', strip=True))
        raw_html = html[:1200000]
        for pat in ('"priceAmount"\\s*:\\s*"?(\\d+(?:\\.\\d{1,3})?)', '"salePrice"\\s*:\\s*"?(\\d+(?:\\.\\d{1,3})?)', '"currentPrice"\\s*:\\s*"?(\\d+(?:\\.\\d{1,3})?)', '"price"\\s*:\\s*"(\\d+(?:\\.\\d{1,3})?)"'):
            mm = re.search(pat, raw_html, flags=re.I)
            if mm:
                price_candidates.append(mm.group(1))
                break
        for cand in price_candidates:
            cand_text = _normalize_price_chars(str(cand))
            mm = re.search(r'(?<!\d)(\d+(?:[.,]\d{1,3})?)(?!\d)', cand_text)
            if not mm:
                continue
            cand_cur = detect_currency_code(cand_text, data.get('currency') or '')
            val = _normalize_price_token(mm.group(1), cand_cur)
            if val is None:
                continue
            if val > 0:
                data['price'] = val
                if not data['currency']:
                    data['currency'] = detect_currency_code(str(cand), '')
                break
    if not data['currency']:
        raw_head = html[:250000]
        mm = re.search('"priceCurrency"\\s*:\\s*"([A-Z]{3})"', raw_head, flags=re.I)
        if mm and mm.group(1).upper() in KNOWN_CURRENCY_CODES:
            data['currency'] = mm.group(1).upper()
        elif data['price']:
            host = urllib.parse.urlparse(url).netloc.lower()
            if any((d in host for d in ('amazon.com', 'ebay.com', 'walmart.com', 'bestbuy.com', 'newegg.com', 'aliexpress.com', 'temu.com'))):
                data['currency'] = 'USD'
            elif any((d in host for d in ('1688.com', 'taobao.com', 'tmall.com'))):
                data['currency'] = 'CNY'
    if not data['image_url']:
        for attrs in ({'property': 'og:image'}, {'name': 'twitter:image'}, {'property': 'twitter:image'}):
            m = soup.find('meta', attrs=attrs)
            if m and m.get('content') and str(m.get('content')).startswith('http'):
                data['image_url'] = str(m.get('content'))
                break
    ul = url.lower()
    if any((p in ul for p in LISTING_URL_PARTS)):
        if not re.search('/product/|/products/[^/]{3,}|/p/|/dp/|/item/|/prod/', ul):
            if ld_products != 1:
                data['is_product'] = False
    return data

def _prune_verified_page_cache():
    if len(VERIFIED_PAGE_CACHE) <= VERIFIED_PAGE_CACHE_MAX:
        return
    items = sorted(VERIFIED_PAGE_CACHE.items(), key=lambda kv: kv[1].get('ts', 0))
    for k, _ in items[:len(items) - VERIFIED_PAGE_CACHE_MAX // 2]:
        VERIFIED_PAGE_CACHE.pop(k, None)

def _result_confirmed_out_of_stock(item):
    if not ENABLE_RESULT_STOCK_CHECK:
        return False
    if isinstance(item, dict) and item.get('in_stock') is False:
        return True
    url = (item.get('link') or item.get('url') or '').strip() if isinstance(item, dict) else str(item or '').strip()
    if not url.startswith(('http://', 'https://')):
        return False
    try:
        cached = VERIFIED_PAGE_CACHE.get(url)
        if cached and time.time() - cached.get('ts', 0) < 600:
            info = cached.get('data')
            return bool(info and info.get('available') is False)
        if not ENABLE_LIVE_STOCK_NETWORK_CHECK:
            return False
        html = fetch_html(url)
        if not html:
            return False
        info = parse_product_data(html, url)
        if info:
            VERIFIED_PAGE_CACHE[url] = {'data': info, 'ts': time.time()}
            _prune_verified_page_cache()
        return bool(info and info.get('available') is False)
    except Exception as e:
        print(f'STOCK CHECK UNKNOWN: {url[:90]} -> {e}')
        return False

def _filter_confirmed_oos(items, label='RESULT'):
    seq = list(items or [])
    if not seq or not ENABLE_RESULT_STOCK_CHECK:
        return seq
    try:
        if ENABLE_LIVE_STOCK_NETWORK_CHECK:
            flags = list(RESOLVER.map(_result_confirmed_out_of_stock, seq))
        else:
            flags = [_result_confirmed_out_of_stock(item) for item in seq]
    except Exception as e:
        print(f'{label} STOCK FILTER ERR: {e}')
        return seq
    kept = []
    for item, is_oos in zip(seq, flags):
        if is_oos:
            url = item.get('link') or item.get('url') or '' if isinstance(item, dict) else ''
            title = item.get('title') or item.get('source') or '' if isinstance(item, dict) else ''
            print(f'{label} OOS SKIP: {title[:70]} -> {url[:100]}')
            continue
        kept.append(item)
    return kept

def verify_offers(urls_map, query):
    if not urls_map:
        return {}
    verified = {}

    def _check(item):
        name, url = item
        if is_blocked_store(name, url):
            print(f'REJECT BLOCKED STORE: {name} -> {url}')
            return None
        cached = VERIFIED_PAGE_CACHE.get(url)
        if cached and time.time() - cached['ts'] < 600:
            info = cached['data']
        elif ENABLE_LIVE_PAGE_VERIFICATION:
            html = fetch_html(url)
            info = parse_product_data(html, url)
            if info:
                VERIFIED_PAGE_CACHE[url] = {'data': info, 'ts': time.time()}
        else:
            return None
        if not info:
            return None
        if not info['is_product']:
            print(f'REJECT LISTING: {name} -> {url}')
            return None
        if not info['available']:
            print(f'REJECT OOS: {name} -> {url}')
            return None
        if not info['price'] or info['price'] <= 0:
            print(f'REJECT NO PRICE: {name} -> {url}')
            return None
        return (name, url, info)
    results = list(RESOLVER.map(_check, urls_map.items()))
    _prune_verified_page_cache()
    for r in results:
        if r:
            name, url, info = r
            verified[name] = {'url': url, 'price': info['price'], 'title': info['title'], 'image_url': info.get('image_url', ''), 'currency': info.get('currency', '')}
    return verified

def _cleanup_lens_images():
    now = time.time()
    with LENS_IMAGE_LOCK:
        expired = [k for k, v in LENS_IMAGE_STORE.items() if v.get('expires_at', 0) <= now]
        for k in expired:
            LENS_IMAGE_STORE.pop(k, None)

def publish_image_for_lens(image_b64, mime_type):
    if not PUBLIC_BASE_URL or not image_b64:
        return ''
    try:
        raw = base64.b64decode(image_b64)
    except Exception:
        return ''
    if not raw or len(raw) > 15 * 1024 * 1024:
        return ''
    _cleanup_lens_images()
    # Content-addressed and signed: the same uploaded bytes now produce the
    # same Lens URL across WhatsApp, web and mobile.  This is required for
    # SerpApi's free exact-request cache; the previous random salt guaranteed a
    # different URL (and therefore a paid cache miss) on every retry.
    signing_secret = (os.environ.get('LENS_URL_SIGNING_SECRET') or VERIFY_TOKEN or SERPAPI_API_KEY or 'findzia-lens').encode('utf-8')
    raw_digest = hashlib.sha256(raw).digest()
    token = hmac.new(signing_secret, raw_digest, hashlib.sha256).hexdigest()[:32]
    with LENS_IMAGE_LOCK:
        LENS_IMAGE_STORE[token] = {
            'content': raw,
            'mime': mime_type or 'image/jpeg',
            'content_sha256': raw_digest.hex(),
            'expires_at': time.time() + LENS_IMAGE_TTL,
        }
    return f'{PUBLIC_BASE_URL}/lens-image/{token}'

def _collect_lens_items(data, items, seen):
    for key in ('exact_matches', 'visual_matches', 'products'):
        values = data.get(key) or []
        if isinstance(values, dict):
            values = values.get('results') or []
        for x in values:
            if not isinstance(x, dict):
                continue
            title = (x.get('title') or '').strip()
            link = (x.get('link') or '').strip()
            source = (x.get('source') or '').strip()
            sig = (title.lower(), link.lower())
            if not title or sig in seen:
                continue
            if is_blocked_store(source, link):
                print(f'LENS BLOCKED STORE SKIP: {source} -> {link}')
                continue
            seen.add(sig)
            items.append({'title': title, 'link': link, 'source': source, 'position': int(x.get('position') or len(items) + 1), 'section': key, 'exact': key == 'exact_matches' or bool(x.get('exact_match')), 'thumbnail': (x.get('thumbnail') or x.get('image') or '').strip(), 'image': (x.get('image') or x.get('thumbnail') or '').strip(), 'price': (x.get('price') or {}).get('value') if isinstance(x.get('price'), dict) else str(x.get('price') or ''), 'price_value': (x.get('price') or {}).get('extracted_value') if isinstance(x.get('price'), dict) else x.get('extracted_price'), 'currency': (x.get('price') or {}).get('currency') if isinstance(x.get('price'), dict) else '', 'in_stock': x.get('in_stock'), 'condition': (x.get('condition') or '').strip()})
    return items

def _serpapi_lens_request(public_url, lens_type, country, auto_crop, query_hint):
    params = {'engine': 'google_lens', 'url': public_url, 'api_key': SERPAPI_API_KEY, 'hl': 'en', 'safe': 'active', 'output': 'json'}
    if lens_type:
        params['type'] = lens_type
    if country:
        params['country'] = country
    if auto_crop:
        params['auto_crop'] = 'true'
    if query_hint and lens_type in (None, '', 'all', 'visual_matches', 'products'):
        params['q'] = query_hint[:120]
    try:
        lens_read_timeout = min(float(LENS_HTTP_TIMEOUT_SECONDS), max(6.0, float(LENS_TOTAL_TIMEOUT_SECONDS) - 0.5))
        data = _serpapi_cached_json(
            params,
            timeout=(5, lens_read_timeout),
            label=f"GOOGLE LENS type={lens_type or 'all'} country={country or '-'}",
        )
        if data is None:
            return []
        items, seen = ([], set())
        _collect_lens_items(data, items, seen)
        for item in items:
            item['_lens_country'] = (country or '').lower()
        print(f"GOOGLE LENS PASS type={lens_type or 'all'} country={country or '-'} auto_crop={auto_crop} -> {len(items)} items")
        return items
    except Exception as e:
        print(f"GOOGLE LENS PASS EXCEPTION type={lens_type or 'all'}: {e}")
        return []

def _china_store_search_fallback(base_query, limit=8):
    if not SERPAPI_API_KEY:
        return []
    q = _shopping_clean_query(base_query or '')
    if not q:
        return []
    targets = [('AliExpress', 'aliexpress.com'), ('Temu', 'temu.com'), ('Alibaba', 'alibaba.com'), ('1688', '1688.com'), ('Taobao', 'taobao.com'), ('SHEIN', 'shein.com')]

    def _one(label, domain):
        cards = _serpapi_shopping_request(f'{q} site:{domain}', 'us', hl='en', timeout_seconds=MARKET_FALLBACK_TIMEOUT_SECONDS)
        out = []
        for pos, card in enumerate(cards or [], 1):
            link = (card.get('link') or '').strip()
            if not link:
                continue
            direct = _shopping_direct_url(link) or link
            try:
                host = urllib.parse.urlparse(direct).netloc.lower().replace('www.', '')
            except Exception:
                host = ''
            if not _host_matches_any(host, (domain,)):
                continue
            title = (card.get('title') or '').strip()
            source = (card.get('source') or label).strip() or label
            price_text = str(card.get('price') or '').strip()
            price_value = card.get('extracted_price')
            currency = detect_currency_code(price_text, 'CNY', 'cn')
            out.append({'title': title or q, 'link': direct, 'source': source, 'position': pos, 'section': 'china_store_fallback', 'exact': False, 'thumbnail': (card.get('thumbnail') or '').strip(), 'image': (card.get('thumbnail') or '').strip(), 'price': price_text, 'price_value': price_value, 'currency': currency, 'in_stock': None, 'condition': '', '_lens_country': 'cn', '_china_fallback': True})
        return out
    futures = {LENS_HTTP_POOL.submit(_one, label, domain): (label, domain) for label, domain in targets}
    merged, seen = ([], set())
    done, not_done = wait(list(futures), timeout=MARKET_FALLBACK_TIMEOUT_SECONDS)
    for fut in done:
        label, domain = futures[fut]
        try:
            for it in fut.result() or []:
                sig = ((it.get('title') or '').lower(), (it.get('link') or '').lower())
                if sig in seen or not is_china_market_result(it):
                    continue
                seen.add(sig)
                merged.append(it)
                if len(merged) >= limit:
                    break
        except Exception as e:
            print(f'CHINA FALLBACK ERR {label}/{domain}: {e}')
        if len(merged) >= limit:
            break
    for fut in not_done:
        fut.cancel()
    print(f'CHINA STORE FALLBACK: query={q[:70]!r} -> {len(merged)} results')
    return merged[:limit]

def _shopping_card_to_market_item(card, fallback_source='', lens_country=''):
    link = (card.get('link') or '').strip()
    if not link:
        return None
    direct = _shopping_direct_url(link) or link
    source = (card.get('source') or fallback_source or '').strip()
    if not direct.startswith(('http://', 'https://')):
        return None
    if is_blocked_store(source, direct):
        print(f'SHOPPING BLOCKED STORE SKIP: {source} -> {direct}')
        return None
    price_text = str(card.get('price') or '').strip()
    return {'title': (card.get('title') or '').strip(), 'link': direct, 'source': source, 'position': int(card.get('position') or 999), 'section': 'market_presence_fallback', 'exact': False, 'thumbnail': (card.get('thumbnail') or '').strip(), 'image': (card.get('thumbnail') or '').strip(), 'price': price_text, 'price_value': card.get('extracted_price'), 'currency': detect_currency_code(price_text, '', lens_country), '_offer_meta': ' '.join((str(card.get(k) or '') for k in ('installment', 'monthly_payment', 'payment', 'price_description', 'snippet', 'extensions', 'badge', 'tag', 'delivery'))), 'in_stock': None, 'condition': '', '_lens_country': lens_country, '_market_presence_fallback': True}

def _market_presence_fallback(base_query, rank, limit=6):
    if not SERPAPI_API_KEY:
        return []
    q = _shopping_clean_query(base_query or '')
    if not q:
        return []
    if rank == 2:
        return _china_store_search_fallback(q, limit=limit)
    local_cc = (current_market().get('country') or DEFAULT_COUNTRY).lower()
    if rank == 0:
        specs = [('Local', '', local_cc)]
        specs.extend(((label, domain, local_cc) for label, domain in local_rescue_store_specs(q, LOCAL_STORE_RESCUE_MAX)))
    else:
        specs = [('Amazon', 'amazon.com', 'us'), ('eBay', 'ebay.com', 'us'), ('Walmart', 'walmart.com', 'us'), ('US', '', 'us')]

    def _one(label, domain, gl):
        hl = country_search_hl(gl) if rank == 0 else 'en'
        if rank == 0 and SHOPPING_GEO_GUARD and (not _shopping_gl_supported(gl)):
            if not SHOPPING_UNSUPPORTED_ORGANIC_FALLBACK:
                _log_unsupported_shopping_gl(gl)
                return []
            return [item for item in _serpapi_google_organic_market_request(q, gl, hl=hl, domain=domain, timeout_seconds=MARKET_FALLBACK_TIMEOUT_SECONDS, limit=6) if result_market_rank(item) == rank]
        search_q = f'{q} site:{domain}' if domain else q
        cards = _serpapi_shopping_request(search_q, gl, hl=hl, timeout_seconds=MARKET_FALLBACK_TIMEOUT_SECONDS)
        out = []
        for card in cards or []:
            item = _shopping_card_to_market_item(card, label, gl)
            if not item:
                continue
            if domain:
                try:
                    host = urllib.parse.urlparse(item['link']).netloc.lower().replace('www.', '')
                except Exception:
                    host = ''
                if not _host_matches_any(host, (domain,)):
                    continue
            if result_market_rank(item) != rank:
                continue
            out.append(item)
        return out
    futures = {LENS_HTTP_POOL.submit(_one, label, domain, gl): (label, domain) for label, domain, gl in specs}
    merged, seen = ([], set())
    done, pending = wait(list(futures), timeout=MARKET_FALLBACK_TIMEOUT_SECONDS)
    gathered = []
    for fut in done:
        try:
            gathered.extend(fut.result() or [])
        except Exception as e:
            print(f'MARKET PRESENCE FALLBACK ERR rank={rank}: {e}')
    for fut in pending:
        fut.cancel()
    if rank == 1:
        gathered.sort(key=lambda x: (_us_store_priority(x.get('source'), x.get('link')), int(x.get('position') or 999)))
    else:
        gathered.sort(key=lambda x: int(x.get('position') or 999))
    for item in gathered:
        sig = ((item.get('title') or '').lower(), (item.get('link') or '').lower())
        if sig in seen:
            continue
        seen.add(sig)
        merged.append(item)
        if len(merged) >= limit:
            break
    print(f'MARKET PRESENCE FALLBACK rank={rank} query={q[:70]!r} -> {len(merged)}')
    return merged

def _single_local_lane_rescue(base_query, timeout_seconds=3.5, limit=6):
    """One quota-bounded local request used only while foreign rows are visible."""
    if not SERPAPI_API_KEY:
        return []
    q = _shopping_clean_query(base_query or '')
    if not q:
        return []
    local_cc = (current_market().get('country') or DEFAULT_COUNTRY).lower()
    local_hl = country_search_hl(local_cc)
    out = []
    if SHOPPING_GEO_GUARD and (not _shopping_gl_supported(local_cc)):
        if SHOPPING_UNSUPPORTED_ORGANIC_FALLBACK:
            out = _serpapi_google_organic_market_request(q, local_cc, hl=local_hl, domain='', timeout_seconds=timeout_seconds, limit=limit)
    else:
        cards = _serpapi_shopping_request(q, local_cc, hl=local_hl, timeout_seconds=timeout_seconds)
        for card in cards or []:
            item = _shopping_card_to_market_item(card, 'Local', local_cc)
            if item and result_market_rank(item) == 0:
                out.append(item)
                if len(out) >= limit:
                    break
    local_only = [item for item in out if result_market_rank(item) == 0]
    print(f'LENS LOCAL LANE RESCUE country={local_cc} query={q[:70]!r} -> {len(local_only)} result(s)')
    return local_only[:limit]

def _lens_missing_market_ranks(candidates):
    seq = list(candidates or [])
    counts = {r: sum((1 for x in seq if result_market_rank(x) == r)) for r in (0, 1, 2)}
    local_target = min(LENS_DIRECT_LOCAL_MAX, LOCAL_RESULTS_TARGET)
    missing = []
    if counts[0] < local_target:
        missing.append(0)
    if counts[1] == 0:
        missing.append(1)
    if counts[2] == 0:
        missing.append(2)
    return (counts, missing)

def _delayed_china_store_fallback(query, limit, delay_seconds=0.9):
    if delay_seconds > 0:
        time.sleep(delay_seconds)
    return _china_store_search_fallback(query, limit=limit)

def _start_lens_market_prefetch(candidates, query):
    if not LENS_OVERLAP_MARKET_FALLBACK or not SERPAPI_API_KEY:
        return None
    q = (query or '').strip()
    if not q:
        return None
    counts, missing = _lens_missing_market_ranks(candidates)
    if not missing:
        return None
    market_snapshot = dict(current_market())
    futures = {}
    for rank in missing:
        futures[rank] = MARKET_SUPPLEMENT_POOL.submit(_run_with_market, market_snapshot, _market_presence_fallback, q, rank, 6)
    china_retry = None
    if 2 in missing:
        china_retry = MARKET_SUPPLEMENT_POOL.submit(_run_with_market, market_snapshot, _delayed_china_store_fallback, q, max(LENS_DIRECT_CN_MAX * 2, 8), 0.9)
    print(f'LENS SPEED PREFETCH START missing={missing} counts={counts} query={q[:80]!r}')
    return {'query': q, 'started': time.monotonic(), 'futures': futures, 'china_retry': china_retry}

def _prefetch_query_matches(prefetch, query):
    if not prefetch:
        return False
    return _shopping_clean_query(prefetch.get('query') or '').lower() == _shopping_clean_query(query or '').lower()

def _supplement_missing_markets(candidates, query, label='FIRST', prefetch=None):
    seq = list(candidates or [])
    existing = {((x.get('title') or '').lower(), (x.get('link') or '').lower()) for x in seq}
    counts, missing = _lens_missing_market_ranks(seq)
    if not missing or not SERPAPI_API_KEY:
        return seq
    gathered = {}
    market_snapshot = dict(current_market())
    prefetched_by_future = {}
    if _prefetch_query_matches(prefetch, query):
        for rank in missing:
            fut = (prefetch.get('futures') or {}).get(rank)
            if fut is not None:
                prefetched_by_future[fut] = rank
    if prefetched_by_future:
        elapsed = max(0.0, time.monotonic() - float(prefetch.get('started') or time.monotonic()))
        remaining = max(0.0, MARKET_FALLBACK_TIMEOUT_SECONDS + 1.0 - elapsed)
        done, pending = wait(list(prefetched_by_future), timeout=remaining)
        for fut in done:
            rank = prefetched_by_future[fut]
            try:
                gathered[rank] = fut.result() or []
                print(f'LENS SPEED PREFETCH HIT rank={rank} saved_wait~{elapsed:.1f}s')
            except Exception as e:
                print(f'{label}: prefetched market supplement error rank={rank}: {e}')
        for fut in pending:
            rank = prefetched_by_future[fut]
            fut.cancel()
            print(f'LENS SPEED PREFETCH TIMEOUT rank={rank} elapsed={elapsed:.1f}s')
    fresh_ranks = [r for r in missing if r not in gathered and r not in set(prefetched_by_future.values())]
    if fresh_ranks:
        fresh = {MARKET_SUPPLEMENT_POOL.submit(_run_with_market, market_snapshot, _market_presence_fallback, query, rank, 6): rank for rank in fresh_ranks}
        done, pending = wait(list(fresh), timeout=MARKET_FALLBACK_TIMEOUT_SECONDS + 1)
        for fut in done:
            rank = fresh[fut]
            try:
                gathered[rank] = fut.result() or []
            except Exception as e:
                print(f'{label}: market supplement error rank={rank}: {e}')
        for fut in pending:
            fut.cancel()
    for rank in (0, 1, 2):
        extra = gathered.get(rank) or []
        for item in extra:
            sig = ((item.get('title') or '').lower(), (item.get('link') or '').lower())
            if sig in existing:
                continue
            seq.append(item)
            existing.add(sig)
        if extra:
            print(f'{label}: supplemented weak/missing market rank={rank} with {len(extra)} candidate(s)')
    return seq

def google_lens_lookup(image_b64, mime_type, lang='ar', query_hint='', light=False, progress_callback=None):
    if not ENABLE_GOOGLE_LENS or not SERPAPI_API_KEY or (not PUBLIC_BASE_URL):
        print('GOOGLE LENS SKIPPED: missing SERPAPI_API_KEY or PUBLIC_BASE_URL')
        return {'aliases': [], 'matches': [], 'query': ''}
    public_url = publish_image_for_lens(image_b64, mime_type)
    if not public_url:
        print('GOOGLE LENS SKIPPED: could not publish image')
        return {'aliases': [], 'matches': [], 'query': ''}
    try:
        user_country = current_market().get('country', DEFAULT_COUNTRY)
        merged, seen = ([], set())
        merged_by_sig = {}

        def _merge(new_items):
            for it in new_items:
                sig = (it['title'].lower(), it['link'].lower())
                if sig in seen:
                    prev = merged_by_sig.get(sig)
                    if prev is not None:
                        if not _lens_has_price(prev) and _lens_has_price(it):
                            for k in ('price', 'price_value', 'currency', 'in_stock', 'condition'):
                                if it.get(k) not in (None, ''):
                                    prev[k] = it.get(k)
                            prev['price_source'] = 'lens_duplicate_pass'
                            print(f"LENS DUP PRICE MERGE: {(prev.get('source') or '')[:35]} -> {prev.get('price') or prev.get('price_value')}")
                        if prev.get('in_stock') is None and it.get('in_stock') is not None:
                            prev['in_stock'] = it.get('in_stock')
                    continue
                seen.add(sig)
                merged.append(it)
                merged_by_sig[sig] = it
        if USE_FAST_LENS_PIPELINE:
            # Four broad passes are enough for the first screen. The previous
            # seven-pass fan-out mostly duplicated the same 60 Lens cards.
            passes = [('products', user_country, True), ('all', user_country, True)]
            for cc in ('us', 'cn'):
                if cc != user_country:
                    passes.append(('all', cc, True))
        else:
            country_order = []
            for cc in (user_country, 'us', 'cn'):
                if cc and cc not in country_order:
                    country_order.append(cc)
            passes = []
            for cc in country_order:
                passes.extend([('products', cc, True), ('all', cc, True)])
        future_map = {LENS_HTTP_POOL.submit(_serpapi_lens_request, public_url, lens_type, country, auto_crop, query_hint): (lens_type, country, auto_crop) for lens_type, country, auto_crop in passes}
        if not USE_FAST_LENS_PIPELINE:
            cn_hint = (query_hint or '').strip()
            cn_hint = (cn_hint + ' site:aliexpress.com OR site:temu.com OR site:alibaba.com OR site:1688.com OR site:taobao.com OR site:shein.com').strip()
            cn_future = LENS_HTTP_POOL.submit(_serpapi_lens_request, public_url, 'all', 'cn', True, cn_hint)
            future_map[cn_future] = ('all-cn-stores', 'cn', True)
        all_futures = set(future_map)
        pending = set(all_futures)
        done_fast = set()
        lens_market_snapshot = dict(current_market())
        local_rescue_future = None
        local_rescue_started = False
        fast_started = time.monotonic()
        fast_deadline = fast_started + (LENS_TURBO_MAX_WAIT_SECONDS if USE_FAST_LENS_PIPELINE else min(LENS_FAST_READY_SECONDS, LENS_TOTAL_TIMEOUT_SECONDS))
        enough_fast = False
        last_progress_size = 0

        def _emit_progress_snapshot(reason, allow_foreign_first=False):
            """Publish usable Lens rows regardless of which fast-path produced them."""
            nonlocal last_progress_size
            if not (light and progress_callback):
                return False
            preview_allowed = [dict(x) for x in merged if result_market_rank(x) != 99]
            if len(preview_allowed) <= last_progress_size:
                return False
            preview_counts = {r: sum((1 for x in preview_allowed if result_market_rank(x) == r)) for r in (0, 1, 2)}
            if len(preview_allowed) < ANDROID_IMAGE_PROGRESSIVE_MIN_RESULTS:
                return False
            if (not allow_foreign_first) and preview_counts[0] < ANDROID_IMAGE_PROGRESSIVE_MIN_LOCAL:
                return False
            try:
                preview_allowed.sort(key=lambda m: (result_market_rank(m), 0 if m.get('exact') else 1, 0 if m.get('section') == 'visual_matches' else 1, int(m.get('position') or 999)))
                progress_callback({'aliases': [], 'matches': preview_allowed, 'query': (query_hint or (preview_allowed[0].get('title') if preview_allowed else '') or '').strip(), 'visual_identity': '', 'chosen': preview_allowed[0] if preview_allowed else {}, 'signature': {}, 'progressive': True})
                last_progress_size = len(preview_allowed)
                print(f'LENS PROGRESSIVE SNAPSHOT reason={reason} raw={len(preview_allowed)} counts={preview_counts} elapsed={time.monotonic() - fast_started:.1f}s')
                return True
            except Exception as e:
                print(f'LENS PROGRESSIVE CALLBACK ERR reason={reason}: {e}')
                return False

        def _start_local_rescue_if_needed(force=False):
            nonlocal local_rescue_future, local_rescue_started
            if local_rescue_started or (not LENS_LOCAL_LANE_RESCUE):
                return local_rescue_future
            local_count = sum(1 for x in merged if result_market_rank(x) == 0)
            if local_count or not merged:
                return local_rescue_future
            elapsed = time.monotonic() - fast_started
            if (not force) and elapsed < LENS_LOCAL_RESCUE_AFTER_SECONDS:
                return local_rescue_future
            rescue_query = (query_hint or (merged[0].get('title') if merged else '') or '').strip()
            if not rescue_query:
                return local_rescue_future
            local_rescue_started = True
            local_rescue_future = MARKET_SUPPLEMENT_POOL.submit(
                _run_with_market,
                lens_market_snapshot,
                _single_local_lane_rescue,
                rescue_query,
                LENS_LOCAL_LANE_GRACE_SECONDS,
                max(LENS_LOCAL_LANE_TARGET + 2, LENS_LOCAL_LANE_TARGET),
            )
            print(f'LENS LOCAL LANE RESCUE START elapsed={elapsed:.1f}s country={user_country}')
            return local_rescue_future

        while pending and time.monotonic() < fast_deadline:
            remaining_fast = max(0.0, fast_deadline - time.monotonic())
            just_done, pending = wait(pending, timeout=min(0.35, remaining_fast), return_when=FIRST_COMPLETED)
            if not just_done:
                continue
            done_fast |= set(just_done)
            for fut in just_done:
                lens_type, country, auto_crop = future_map[fut]
                try:
                    _merge(fut.result())
                except Exception as e:
                    print(f'GOOGLE LENS FUTURE ERR type={lens_type} country={country}: {e}')
            rank_counts = {r: sum((1 for x in merged if result_market_rank(x) == r)) for r in (0, 1, 2)}
            if USE_FAST_LENS_PIPELINE:
                # Do not hold 60 useful cards hostage because one market bucket
                # is missing. The separate "more stores" action can deepen it.
                useful = sum(rank_counts.values())
                enough_fast = useful >= max(6, LENS_MIN_MATCHES)
            else:
                enough_fast = rank_counts[0] >= 2 and rank_counts[1] >= 1 and (rank_counts[2] >= 1) and (len(merged) >= max(5, LENS_MIN_MATCHES))
            # First paint is never held back by a slow local market. The local
            # lane below remains alive and will replace/reorder the snapshot.
            _emit_progress_snapshot('fast_pass', allow_foreign_first=True)
            if rank_counts[0] == 0:
                _start_local_rescue_if_needed()
            if USE_FAST_LENS_PIPELINE and enough_fast:
                print(f'LENS TURBO EARLY RETURN READY useful={sum(rank_counts.values())} elapsed={time.monotonic() - fast_started:.2f}s')
                break
        # Race guard: Railway can finish the SerpApi responses a fraction after
        # the 4.5s fast deadline. Previously we cancelled all four futures with
        # merged=0, then paid for the much slower Vision/Shopping fallback even
        # though Lens printed 60 results immediately afterwards. When the pool is
        # completely empty, wait only for the first real Lens response.
        if USE_FAST_LENS_PIPELINE and not merged and pending:
            rescue_started = time.monotonic()
            rescue_deadline = rescue_started + LENS_TURBO_EMPTY_GRACE_SECONDS
            while pending and not merged and time.monotonic() < rescue_deadline:
                rescue_left = max(0.0, rescue_deadline - time.monotonic())
                just_done, pending = wait(pending, timeout=rescue_left, return_when=FIRST_COMPLETED)
                if not just_done:
                    break
                done_fast |= set(just_done)
                for fut in just_done:
                    lens_type, country, auto_crop = future_map[fut]
                    try:
                        _merge(fut.result())
                    except Exception as e:
                        print(f'GOOGLE LENS RESCUE FUTURE ERR type={lens_type} country={country}: {e}')
            if merged:
                rank_counts = {r: sum((1 for x in merged if result_market_rank(x) == r)) for r in (0, 1, 2)}
                enough_fast = sum(rank_counts.values()) >= max(1, LENS_MIN_MATCHES)
                print(f'LENS ZERO-RACE RESCUED useful={sum(rank_counts.values())} grace_elapsed={time.monotonic() - rescue_started:.2f}s')
                _emit_progress_snapshot('zero_race', allow_foreign_first=True)
            else:
                print(f'LENS ZERO-RACE EMPTY after_grace={LENS_TURBO_EMPTY_GRACE_SECONDS}s')

        # Foreign rows are allowed to paint immediately, but they cannot cancel
        # a slower local Lens pass. Keep only the local lane alive inside one
        # shared post-fast budget, then rebalance the authoritative snapshot.
        post_fast_deadline = min(
            fast_started + LENS_TOTAL_TIMEOUT_SECONDS,
            time.monotonic() + max(LENS_LOCAL_LANE_GRACE_SECONDS, LENS_TURBO_SPARSE_GRACE_SECONDS),
        )
        sparse_useful = sum(1 for x in merged if result_market_rank(x) in (0, 1, 2))
        if USE_FAST_LENS_PIPELINE and sparse_useful:
            _emit_progress_snapshot('pre_local_lane', allow_foreign_first=True)

        local_count = sum(1 for x in merged if result_market_rank(x) == 0)
        if USE_FAST_LENS_PIPELINE and merged and local_count < LENS_LOCAL_LANE_TARGET:
            local_lane_started = time.monotonic()
            rescue_due_at = fast_started + LENS_LOCAL_RESCUE_AFTER_SECONDS
            print(f'LENS LOCAL LANE START local={local_count}/{LENS_LOCAL_LANE_TARGET} pending={len(pending)}')
            while local_count < LENS_LOCAL_LANE_TARGET and time.monotonic() < post_fast_deadline:
                local_lens_pending = {fut for fut in pending if future_map[fut][1] == user_country}
                _start_local_rescue_if_needed(force=(local_count == 0 and not local_lens_pending))
                waiters = set(local_lens_pending)
                if local_rescue_future is not None:
                    waiters.add(local_rescue_future)
                if not waiters:
                    break
                wait_deadline = post_fast_deadline
                if local_count == 0 and not local_rescue_started:
                    wait_deadline = min(wait_deadline, rescue_due_at)
                wait_seconds = max(0.0, wait_deadline - time.monotonic())
                if wait_seconds <= 0:
                    _start_local_rescue_if_needed()
                    continue
                just_done, _ = wait(waiters, timeout=wait_seconds, return_when=FIRST_COMPLETED)
                if not just_done:
                    _start_local_rescue_if_needed()
                    continue
                for fut in just_done:
                    if fut is local_rescue_future:
                        try:
                            _merge(fut.result() or [])
                        except Exception as e:
                            print(f'LENS LOCAL LANE RESCUE ERR: {e}')
                        local_rescue_future = None
                        continue
                    pending.discard(fut)
                    done_fast.add(fut)
                    lens_type, country, auto_crop = future_map[fut]
                    try:
                        _merge(fut.result() or [])
                    except Exception as e:
                        print(f'LENS LOCAL LANE FUTURE ERR type={lens_type} country={country}: {e}')
                local_count = sum(1 for x in merged if result_market_rank(x) == 0)
                _emit_progress_snapshot('local_lane', allow_foreign_first=True)
            print(f'LENS LOCAL LANE DONE local={local_count}/{LENS_LOCAL_LANE_TARGET} elapsed={time.monotonic() - local_lane_started:.2f}s rescue={local_rescue_started}')

        sparse_useful = sum(1 for x in merged if result_market_rank(x) in (0, 1, 2))
        if USE_FAST_LENS_PIPELINE and 0 < sparse_useful < LENS_TURBO_STRONG_RESULT_TARGET and pending:
            sparse_started = time.monotonic()
            sparse_deadline = min(post_fast_deadline, sparse_started + LENS_TURBO_SPARSE_GRACE_SECONDS)
            before_sparse = sparse_useful
            while pending and time.monotonic() < sparse_deadline:
                sparse_left = max(0.0, sparse_deadline - time.monotonic())
                just_done, pending = wait(pending, timeout=sparse_left, return_when=FIRST_COMPLETED)
                if not just_done:
                    break
                done_fast |= set(just_done)
                for fut in just_done:
                    lens_type, country, auto_crop = future_map[fut]
                    try:
                        _merge(fut.result())
                    except Exception as e:
                        print(f'GOOGLE LENS SPARSE FUTURE ERR type={lens_type} country={country}: {e}')
                sparse_useful = sum(1 for x in merged if result_market_rank(x) in (0, 1, 2))
                _emit_progress_snapshot('sparse_fill', allow_foreign_first=True)
                if sparse_useful >= LENS_TURBO_STRONG_RESULT_TARGET:
                    break
            print(f'LENS SPARSE FILL useful={before_sparse}->{sparse_useful} grace_elapsed={time.monotonic() - sparse_started:.2f}s')
        rank_counts = {r: sum((1 for x in merged if result_market_rank(x) == r)) for r in (0, 1, 2)}
        market_prefetch = None
        prefetch_query = (query_hint or '').strip()
        if not prefetch_query and merged:
            prefetch_query = (merged[0].get('title') or '').strip()
        if (not USE_FAST_LENS_PIPELINE) and light and pending and (not enough_fast) and prefetch_query:
            market_prefetch = _start_lens_market_prefetch(merged, prefetch_query)
        done = set(done_fast)
        if (not USE_FAST_LENS_PIPELINE) and pending and (not enough_fast):
            fast_elapsed = max(0.0, time.monotonic() - fast_started)
            remaining = max(0.0, LENS_TOTAL_TIMEOUT_SECONDS - fast_elapsed)
            done_more, pending = wait(pending, timeout=remaining)
            done |= done_more
            for fut in done_more:
                lens_type, country, auto_crop = future_map[fut]
                try:
                    _merge(fut.result())
                except Exception as e:
                    print(f'GOOGLE LENS FUTURE ERR type={lens_type} country={country}: {e}')
        if local_rescue_future is not None:
            if local_rescue_future.done():
                try:
                    _merge(local_rescue_future.result() or [])
                    _emit_progress_snapshot('local_rescue_deadline', allow_foreign_first=True)
                except Exception as e:
                    print(f'LENS LOCAL LANE RESCUE DEADLINE ERR: {e}')
            else:
                local_rescue_future.cancel()
                print('LENS LOCAL LANE RESCUE LEFT RUNNING AFTER DISPLAY DEADLINE')
            local_rescue_future = None
        for fut in pending:
            lens_type, country, _ = future_map[fut]
            fut.cancel()
            print(f'GOOGLE LENS PASS SKIPPED AFTER FAST/TOTAL TIMEOUT type={lens_type} country={country}')
        print(f'GOOGLE LENS PARALLEL DONE completed={len(done)}/{len(future_map)} fast_ready={enough_fast} max_wait={(LENS_TURBO_MAX_WAIT_SECONDS if USE_FAST_LENS_PIPELINE else LENS_TOTAL_TIMEOUT_SECONDS)}s')
        allowed = [m for m in merged if result_market_rank(m) != 99]
        fallback_query = (query_hint or '').strip()
        if not fallback_query and merged:
            fallback_query = (merged[0].get('title') or '').strip()
        if not USE_FAST_LENS_PIPELINE:
            allowed = _supplement_missing_markets(allowed, fallback_query, 'FIRST-LENS', prefetch=market_prefetch)
        if (not USE_FAST_LENS_PIPELINE) and not any((result_market_rank(m) == 2 for m in allowed)):
            fallback_query = (query_hint or '').strip()
            if not fallback_query and merged:
                fallback_query = (merged[0].get('title') or '').strip()
            cn_extra = None
            if _prefetch_query_matches(market_prefetch, fallback_query):
                retry_fut = market_prefetch.get('china_retry')
                if retry_fut is not None:
                    elapsed = max(0.0, time.monotonic() - float(market_prefetch.get('started') or time.monotonic()))
                    retry_budget = 2.0 * MARKET_FALLBACK_TIMEOUT_SECONDS + 2.0
                    remaining = max(0.0, retry_budget - elapsed)
                    try:
                        cn_extra = retry_fut.result(timeout=remaining) or []
                        print(f'LENS SPEED CHINA RETRY HIT saved_wait~{elapsed:.1f}s results={len(cn_extra)}')
                    except Exception as e:
                        retry_fut.cancel()
                        cn_extra = []
                        print(f'LENS SPEED CHINA RETRY TIMEOUT/ERR elapsed={elapsed:.1f}s err={e}')
            if cn_extra is None:
                cn_extra = _china_store_search_fallback(fallback_query, limit=max(LENS_DIRECT_CN_MAX * 2, 8))
            if cn_extra:
                existing = {((m.get('title') or '').lower(), (m.get('link') or '').lower()) for m in allowed}
                for m in cn_extra:
                    sig = ((m.get('title') or '').lower(), (m.get('link') or '').lower())
                    if sig not in existing and result_market_rank(m) == 2:
                        allowed.append(m)
                        existing.add(sig)
        allowed.sort(key=lambda m: (result_market_rank(m), 0 if m.get('exact') else 1, 0 if m.get('section') == 'visual_matches' else 1, int(m.get('position') or 999)))
        keep_caps = {0: max(LENS_DIRECT_LOCAL_MAX * 3, LENS_DIRECT_LOCAL_MAX), 1: max(LENS_DIRECT_US_MAX * 3, LENS_DIRECT_US_MAX), 2: max(LENS_DIRECT_CN_MAX * 3, LENS_DIRECT_CN_MAX)}
        matches = []
        for rank in (0, 1, 2):
            market_rows = [m for m in allowed if result_market_rank(m) == rank]
            matches.extend(market_rows[:keep_caps[rank]])
        matches = matches[:max(LENS_RESULT_LIMIT, sum(keep_caps.values()))]
        if not matches:
            print('GOOGLE LENS: no visual matches after all passes')
            return {'aliases': [], 'matches': [], 'query': ''}
        for i, m in enumerate(matches[:5], 1):
            print(f"LENS MATCH {i}: {m.get('title', '')} | {m.get('source', '')} | section={m.get('section', '')} exact={m.get('exact', False)}")
        generic = re.compile('^(mules?|shoes?|slippers?|sandals?|footwear|بوتيغا فينيتا|bottega veneta)$', re.I)
        ranked = []
        for m in matches:
            title = (m.get('title') or '').strip()
            if not title or generic.match(title):
                continue
            score = 4000 if m.get('exact') else 0
            if m.get('section') == 'visual_matches':
                score += 900
            score += max(0, 700 - int(m.get('position') or 99) * 20)
            score += min(len(title), 120) / 12
            if m.get('thumbnail') or m.get('image'):
                score += 20
            ranked.append((score, m))
        chosen = max(ranked, key=lambda x: x[0])[1] if ranked else matches[0]
        chosen_title = (chosen.get('title') or '').strip()
        if light:
            if USE_FAST_LENS_PIPELINE:
                # Lens already identified and ranked the product. Returning its
                # commercial title avoids the extra image-Gemini round trip.
                return {'aliases': [chosen_title] if chosen_title else [], 'matches': matches, 'query': chosen_title, 'visual_identity': '', 'chosen': chosen, 'signature': {}, 'source': 'lens_turbo'}
            visual_identity = ''
            try:
                id_system = 'Identify the physical product in the image for shopping search. Return one concise English commercial identity only: product type + brand/model if visibly supported. Do not guess a brand/model. Do not mention colors unless identity-critical. No explanation.'
                visual_identity, _ = call_gemini([{'inline_data': {'mime_type': mime_type, 'data': image_b64}}, {'text': f'Lens hint only (may be wrong): {chosen_title}'}], system=id_system, use_search=False)
                visual_identity = re.sub('\\s+', ' ', (visual_identity or '').strip()).strip(' .-|')[:180]
                print(f'LENS VISUAL IDENTITY: {visual_identity}')
            except Exception as e:
                print(f'LENS VISUAL IDENTITY FAIL: {e}')
            return {'aliases': [x for x in (visual_identity, chosen_title) if x], 'matches': matches, 'query': visual_identity or chosen_title, 'visual_identity': visual_identity, 'chosen': chosen, 'signature': {}}
        sig_system = 'أنت خبير منتجات. الصورة هي المرجع الوحيد. استخرج اسماً عربياً وإنجليزياً ووصفاً شكلياً محافظاً. لا تخترع رقم موديل. حدد اللون الأساسي، النقشة أو الخامة الظاهرة، وهل المنتج مسطح أو بكعب. الرد سطر واحد فقط: Arabic name | English name | COLOR | PATTERN | HEEL | TYPE. HEEL واحدة من FLAT, LOW, HIGH, NONE, UNKNOWN. TYPE مثل MULES, SLIPPERS, SHOES, BAG, ELECTRONICS.'
        sig_txt, _ = call_gemini([{'inline_data': {'mime_type': mime_type, 'data': image_b64}}, {'text': f'Google Lens title hint: {chosen_title}'}], system=sig_system, use_search=False)
        fields = [x.strip() for x in ((sig_txt or '').strip().splitlines()[0] if sig_txt else '').split('|')]
        ar_name = fields[0] if len(fields) > 0 else ''
        en_name = fields[1] if len(fields) > 1 else ''
        signature = {'color': fields[2].lower() if len(fields) > 2 else '', 'pattern': fields[3].lower() if len(fields) > 3 else '', 'heel': fields[4].upper() if len(fields) > 4 else 'UNKNOWN', 'type': fields[5].upper() if len(fields) > 5 else ''}
        aliases = []
        for value in (chosen_title, en_name, ar_name):
            value = (value or '').strip()
            if value and value.upper() not in ('NONE', 'UNKNOWN') and (value not in aliases):
                aliases.append(value)
        query = ' | '.join(aliases[:3])
        print(f'GOOGLE LENS DIRECT MATCH: {query}')
        print(f'GOOGLE LENS SIGNATURE: {signature}')
        return {'aliases': aliases[:3], 'matches': matches, 'query': query, 'chosen': chosen, 'signature': signature}
    except Exception as e:
        print(f'GOOGLE LENS EXCEPTION: {e}')
        return {'aliases': [], 'matches': [], 'query': ''}

def _meaningful_lens_tokens(text):
    raw = normalize_ar(text or '').lower()
    toks = re.findall('[a-z0-9\u0600-ۿ]+', raw)
    stop = {'women', 'woman', 'men', 'man', 'size', 'new', 'used', 'authentic', 'leather', 'جلد', 'mules', 'mule', 'shoes', 'shoe', 'slippers', 'slipper', 'sandals', 'sandal', 'shirt', 'blouse', 'top', 'dress', 'pajama', 'pajamas', 'pyjama', 'pyjamas', 'nightwear', 'sleepwear', 'set', "women's", 'womens', 'ملابس', 'قميص', 'بيجامه', 'بيجامة', 'for', 'the', 'and', 'in', 'with', 'kw', 'kuwait', 'uae', 'كويت', 'نسائي', 'رجالي'}
    out = []
    for t in toks:
        if t in stop or t.isdigit() or len(t) < 3:
            continue
        if t not in out:
            out.append(t)
    return out

def _lens_offer_compatible(info, url, lens_context):
    if not lens_context:
        return True
    sig = lens_context.get('signature') or {}
    chosen = lens_context.get('chosen') or {}
    candidate = ' '.join([str(info.get('title', '')), str(url or '')])
    chosen_title = str(chosen.get('title', '') or lens_context.get('visual_identity', ''))
    if chosen_title and _findzia_hard_product_mismatch(chosen_title, candidate):
        return False
    desired = _meaningful_lens_tokens(chosen_title)
    cand_tokens = norm_tokens(candidate)
    matched = [t for t in desired if t in cand_tokens]
    fashion_words = {'shirt', 'blouse', 'dress', 'pajama', 'pyjama', 'nightwear', 'sleepwear', 'satin', 'printed', 'striped', 'قميص', 'فستان', 'بيجامه', 'بيجامة', 'ساتان', 'مخطط'}
    is_fashion = bool(norm_tokens(chosen_title) & fashion_words)
    if desired:
        needed = 2 if is_fashion and len(desired) >= 2 else 1
        if len(matched) < needed:
            print(f'LENS TOKEN REJECT: wanted={desired} matched={matched} candidate={candidate[:180]}')
            return False
    heel = (sig.get('heel') or 'UNKNOWN').upper()
    cand_norm = normalize_ar(candidate).lower()
    if heel in ('FLAT', 'NONE') and any((normalize_ar(w) in cand_norm for w in ('high heel', 'high heels', 'stiletto', 'kitten heel', 'heeled', 'pump', 'كعب عالي', 'كعب ذهبي'))):
        return False
    pattern = normalize_ar(sig.get('pattern') or '').lower()
    if pattern and pattern not in ('unknown', 'none', 'غير معروف'):
        groups = {'woven': ('woven', 'intrecciato', 'weave', 'handwoven', 'منسوج', 'ضفيره'), 'intrecciato': ('woven', 'intrecciato', 'weave', 'handwoven', 'منسوج', 'ضفيره'), 'braided': ('braided', 'woven', 'intrecciato', 'مضفر', 'منسوج')}
        keys = groups.get(pattern)
        if keys and (not any((normalize_ar(k) in cand_norm for k in keys))):
            return False
    color = normalize_ar(sig.get('color') or '').lower()
    if color and color not in ('unknown', 'none', 'غير معروف'):
        cmap = {'brown': ('brown', 'tan', 'cognac', 'camel', 'burgundy', 'بني', 'جملي'), 'black': ('black', 'اسود'), 'green': ('green', 'اخضر'), 'white': ('white', 'ivory', 'cream', 'ابيض')}
        wanted = {normalize_ar(x) for x in cmap.get(color, (color,))}
        all_colors = {normalize_ar(x) for x in ('black', 'green', 'white', 'red', 'blue', 'silver', 'gold', 'pink', 'purple', 'اسود', 'اخضر', 'ابيض', 'احمر', 'ازرق', 'ذهبي', 'وردي', 'بنفسجي')}
        explicit = cand_tokens & all_colors
        if explicit and (not explicit & wanted):
            return False
    return True

def filter_verified_with_lens(verified, lens_context):
    if not lens_context:
        return verified
    kept = {}
    for name, info in (verified or {}).items():
        if _lens_offer_compatible(info, info.get('url', ''), lens_context):
            kept[name] = info
        else:
            print(f"LENS PRICE REJECT: {name} -> {info.get('title', '')} -> {info.get('url', '')}")
    return kept

def get_final_url(url: str):
    if not url or not url.startswith(('http://', 'https://')):
        return ''
    now = time.time()
    with FINAL_URL_CACHE_LOCK:
        hit = FINAL_URL_CACHE.get(url)
        if hit and now - hit['ts'] < FINAL_URL_CACHE_TTL:
            return hit['url']
    final = url
    try:
        r = requests.get(url, allow_redirects=True, timeout=(3, RESOLVE_TIMEOUT_SECONDS), stream=True, headers=HEADERS)
        final = r.url or url
        r.close()
    except Exception as e:
        print(f'resolve err {e} {url[:80]}')
    with FINAL_URL_CACHE_LOCK:
        if len(FINAL_URL_CACHE) >= 2000:
            oldest = sorted(FINAL_URL_CACHE.items(), key=lambda kv: kv[1].get('ts', 0))[:1000]
            for key, _ in oldest:
                FINAL_URL_CACHE.pop(key, None)
        FINAL_URL_CACHE[url] = {'url': final, 'ts': now}
    return final

def resolve_all(uris):
    return list(RESOLVER.map(get_final_url, uris))

def clean_domain(dom):
    dom = re.sub('^https?://', '', (dom or '').strip().lower())
    return dom.replace('www.', '').split('/')[0]

def domain_key(dom):
    return clean_domain(dom).split('.')[0]

def normalize_name(value):
    return re.sub('[^\\w\\u0600-\\u06FF]+', '', (value or '').lower())
STORE_DOMAINS = {'اليوسفي': 'best.com.kw', 'بستاليوسفي': 'best.com.kw', 'اكسايت': 'xcite.com', 'الغانم': 'xcite.com', 'نون': 'noon.com', 'بلينك': 'blink.com.kw', 'يوريكا': 'eureka.com.kw', 'جرير': 'jarir.com', 'كارفور': 'carrefourkuwait.com', 'لولو': 'luluhypermarket.com', 'امازون': 'amazon.ae', 'طلبات': 'talabat.com', 'ديليفرو': 'deliveroo.com.kw', 'بوتيكات': 'boutiqaat.com', 'جمعية دوت كوم': 'jm3eia.com', 'جمعيه دوت كوم': 'jm3eia.com', 'جميعة': 'jm3eia.com', 'jm3eia': 'jm3eia.com', 'كيتا': 'mykeeta.com', 'keeta': 'mykeeta.com', 'توصيل': 'taw9eel.com', 'التوصيل': 'taw9eel.com', 'taw9eel': 'taw9eel.com', 'taw9el': 'taw9eel.com', 'انترسبورت': 'intersport.com.kw', 'إنترسبورت': 'intersport.com.kw', 'intersport': 'intersport.com.kw', 'ديكاثلون': 'decathlon.com.kw', 'decathlon': 'decathlon.com.kw', 'بروسبورتس': 'prosportskw.com', 'برو سبورتس': 'prosportskw.com', 'prosports': 'prosportskw.com', 'pro sports': 'prosportskw.com', 'تيجرو': 'tigro.app', 'تيغرو': 'tigro.app', 'tigro': 'tigro.app', 'عروض كيو ايت': '3roodq8.com', 'عروضكيوايت': '3roodq8.com', '3roodq8': '3roodq8.com', '3rstore': '3roodq8.com', 'سن اند ساند': 'sssports.com', 'sun and sand': 'sssports.com', 'sunandsand': 'sssports.com', 'sssports': 'sssports.com', 'فوت لوكر': 'footlocker.com.kw', 'footlocker': 'footlocker.com.kw', 'نمشي': 'namshi.com', 'namshi': 'namshi.com'}
GENERAL_MARKETPLACES = ['جمعية دوت كوم', 'طلبات', 'كيتا', 'نون', 'لولو', 'كارفور']
CATEGORY_KEYWORDS = {'sports': ('كره سله', 'كره قدم', 'كره طايره', 'كره تنس', 'كره', 'مضرب', 'تنس', 'بادل', 'سكواش', 'ريشه', 'بادمنتون', 'جيم', 'لياقه', 'دمبل', 'اثقال', 'بار حديد', 'سير كهربائي', 'دراجه هوائيه', 'دراجه ثابته', 'سباحه', 'نظاره سباحه', 'حبل قفز', 'سجاده يوغا', 'يوغا', 'بروتين رياضي', 'جوتي رياضي', 'حذاء رياضي', 'ملابس رياضيه', 'basketball', 'football', 'soccer', 'volleyball', 'tennis', 'padel', 'racket', 'squash', 'badminton', 'gym', 'fitness', 'dumbbell', 'barbell', 'kettlebell', 'treadmill', 'bike', 'bicycle', 'cycling', 'swimming', 'goggles', 'jump rope', 'yoga', 'sneaker', 'running shoe', 'sportswear', 'cricket', 'darts'), 'gaming': ('بلايستيشن', 'اكس بوكس', 'نينتندو', 'سويتش', 'يد تحكم', 'لعبه فيديو', 'العاب فيديو', 'قير', 'شاشه قيمنق', 'كرسي قيمنق', 'سماعه قيمنق', 'كيبورد', 'ماوس', 'playstation', 'ps5', 'ps4', 'xbox', 'nintendo', 'switch', 'controller', 'gaming', 'gamepad', 'headset', 'keyboard', 'mouse', 'steam deck', 'video game'), 'electronics': ('ايفون', 'سامسونج', 'لابتوب', 'تابلت', 'ايباد', 'تلفزيون', 'الكترون', 'هاتف', 'جوال', 'ساعه ابل', 'ساعه ذكيه', 'سماعه', 'ايربودز', 'كاميرا', 'شاحن', 'باور بانك', 'iphone', 'samsung', 'laptop', 'tablet', 'ipad', 'television', 'tv', 'phone', 'smartwatch', 'airpods', 'earbuds', 'camera', 'charger', 'power bank', 'drone'), 'appliances': ('ثلاجه', 'غساله', 'فرن', 'مكيف', 'جلايه', 'مكنسه', 'قلايه', 'ميكرويف', 'fridge', 'refrigerator', 'washer', 'washing machine', 'oven', 'air conditioner', 'dishwasher', 'vacuum', 'air fryer', 'microwave'), 'beauty': ('عطر', 'عطور', 'برفان', 'مكياج', 'روج', 'فاونديشن', 'ماسكرا', 'كريم', 'سيروم', 'عنايه', 'شامبو', 'واقي شمس', 'perfume', 'makeup', 'foundation', 'mascara', 'cream', 'serum', 'skincare', 'shampoo', 'sunscreen', 'cosmetic'), 'pharmacy': ('دواء', 'صيدليه', 'فيتامين', 'مكمل', 'حفاض', 'حفاظ', 'بروتين', 'medicine', 'pharmacy', 'vitamin', 'supplement', 'diaper'), 'grocery': ('بيبسي', 'شيبس', 'حليب', 'قهوه', 'شاي', 'سكر', 'رز', 'زيت', 'ماء', 'عصير', 'بسكوت', 'منظف', 'صابون', 'معجون', 'تونه', 'نسكافيه', 'برينجلز', 'كيتكات', 'grocery', 'milk', 'coffee', 'tea', 'rice', 'detergent'), 'food_delivery': ('مطعم', 'وجبه', 'برجر', 'بيتزا', 'فلات وايت', 'شاورما', 'دجاج مقلي', 'restaurant', 'burger', 'pizza', 'shawarma', 'meal'), 'fashion': ('ملابس', 'قميص', 'بنطلون', 'فستان', 'جاكيت', 'كاب', 'قبعه', 'شنطه', 'حقيبه', 'حذاء', 'جوتي', 'عبايه', 'بيجامه', 'clothing', 'shirt', 'pants', 'dress', 'jacket', 'cap', 'bag', 'shoe', 'abaya'), 'furniture': ('اثاث', 'كرسي', 'طاوله', 'سرير', 'كنب', 'صوفا', 'مرتبه', 'دولاب', 'furniture', 'chair', 'table', 'bed', 'sofa', 'mattress', 'wardrobe'), 'kids_toys': ('لعبه اطفال', 'العاب اطفال', 'لعبه', 'العاب', 'دميه', 'ليغو', 'ليجو', 'مكعبات', 'عربانه', 'عربه اطفال', 'رضاعه', 'كرسي طفل', 'بزل', 'toy', 'toys', 'doll', 'lego', 'puzzle', 'stroller', 'baby'), 'auto': ('سياره', 'بطاريه سياره', 'اطار', 'تواير', 'زيت محرك', 'اكسسوارات سياره', 'قطع غيار', 'car battery', 'tyre', 'tire', 'engine oil', 'car accessories', 'auto parts')}
CATEGORY_SPECIALISTS = {'sports': ['Pro Sports Kuwait (prosportskw.com)', 'Intersport Kuwait', 'Decathlon Kuwait', 'Sun & Sand Sports', 'Foot Locker Kuwait'], 'gaming': ['3RoodQ8 (3roodq8.com)', 'Xcite', 'Eureka', 'Blink', 'Jarir'], 'electronics': ['Xcite', 'Eureka', 'Best Al-Yousifi', 'Blink', 'Jarir', '3RoodQ8 (3roodq8.com)'], 'appliances': ['Xcite', 'Eureka', 'Best Al-Yousifi', 'Blink'], 'beauty': ['Boutiqaat', 'Faces', 'Sephora Kuwait', "Bloomingdale's Kuwait"], 'pharmacy': ['Boots Kuwait', 'YIACO', 'Royal Pharmacy'], 'grocery': ['جمعية دوت كوم', 'Lulu', 'Carrefour', 'Taw9eel'], 'food_delivery': ['Keeta', 'Talabat', 'Deliveroo'], 'fashion': ['Namshi', 'Sun & Sand Sports', 'Foot Locker Kuwait', 'Centrepoint', 'H&M Kuwait'], 'furniture': ['IKEA Kuwait', 'The One', 'Home Centre', 'Midas'], 'kids_toys': ['Tigro (tigro.app)', 'Toys R Us Kuwait', '3RoodQ8 (3roodq8.com)', 'Mothercare', 'Babyshop'], 'auto': ['AlMailem Tires', 'Tires Plus', 'Xcite']}
COUNTRY_MAJOR_STORE_DOMAINS = {'us': [('Amazon', 'amazon.com'), ('Walmart', 'walmart.com'), ('Target', 'target.com'), ('Best Buy', 'bestbuy.com'), ('eBay', 'ebay.com')], 'ca': [('Amazon Canada', 'amazon.ca'), ('Walmart Canada', 'walmart.ca'), ('Best Buy Canada', 'bestbuy.ca'), ('Canadian Tire', 'canadiantire.ca')], 'gb': [('Amazon UK', 'amazon.co.uk'), ('Argos', 'argos.co.uk'), ('Currys', 'currys.co.uk'), ('John Lewis', 'johnlewis.com')], 'fr': [('Amazon France', 'amazon.fr'), ('Fnac', 'fnac.com'), ('Darty', 'darty.com'), ('Cdiscount', 'cdiscount.com'), ('Carrefour', 'carrefour.fr')], 'de': [('Amazon Germany', 'amazon.de'), ('MediaMarkt', 'mediamarkt.de'), ('Saturn', 'saturn.de'), ('Otto', 'otto.de')], 'es': [('Amazon Spain', 'amazon.es'), ('El Corte Inglés', 'elcorteingles.es'), ('MediaMarkt', 'mediamarkt.es'), ('Carrefour', 'carrefour.es')], 'it': [('Amazon Italy', 'amazon.it'), ('MediaWorld', 'mediaworld.it'), ('Unieuro', 'unieuro.it')], 'nl': [('bol', 'bol.com'), ('Coolblue', 'coolblue.nl'), ('MediaMarkt', 'mediamarkt.nl'), ('Amazon Netherlands', 'amazon.nl')], 'be': [('bol', 'bol.com'), ('Coolblue', 'coolblue.be'), ('MediaMarkt', 'mediamarkt.be'), ('Amazon Belgium', 'amazon.com.be')], 'ch': [('Galaxus', 'galaxus.ch'), ('Digitec', 'digitec.ch'), ('Brack', 'brack.ch'), ('Manor', 'manor.ch')], 'at': [('MediaMarkt', 'mediamarkt.at'), ('Amazon Germany', 'amazon.de'), ('Otto Austria', 'ottoversand.at')], 'ie': [('Currys Ireland', 'currys.ie'), ('Harvey Norman', 'harveynorman.ie'), ('Amazon UK', 'amazon.co.uk')], 'pt': [('Worten', 'worten.pt'), ('Fnac Portugal', 'fnac.pt'), ('Continente', 'continente.pt')], 'pl': [('Allegro', 'allegro.pl'), ('Media Expert', 'mediaexpert.pl'), ('RTV Euro AGD', 'euro.com.pl')], 'cz': [('Alza', 'alza.cz'), ('Datart', 'datart.cz'), ('Mall', 'mall.cz')], 'se': [('Amazon Sweden', 'amazon.se'), ('Elgiganten', 'elgiganten.se'), ('CDON', 'cdon.se')], 'no': [('Elkjøp', 'elkjop.no'), ('Komplett', 'komplett.no'), ('Power', 'power.no')], 'dk': [('Elgiganten', 'elgiganten.dk'), ('Proshop', 'proshop.dk'), ('Power', 'power.dk')], 'fi': [('Verkkokauppa', 'verkkokauppa.com'), ('Gigantti', 'gigantti.fi'), ('Power', 'power.fi')], 'tr': [('Trendyol', 'trendyol.com'), ('Hepsiburada', 'hepsiburada.com'), ('Amazon Turkey', 'amazon.com.tr'), ('n11', 'n11.com')], 'ru': [('Ozon', 'ozon.ru'), ('Wildberries', 'wildberries.ru'), ('Yandex Market', 'market.yandex.ru')], 'ua': [('Rozetka', 'rozetka.com.ua'), ('Prom', 'prom.ua'), ('Epicentr', 'epicentrk.ua')], 'sa': [('Amazon Saudi', 'amazon.sa'), ('Noon', 'noon.com'), ('Jarir', 'jarir.com'), ('eXtra', 'extra.com'), ('Carrefour', 'carrefourksa.com')], 'ae': [('Amazon UAE', 'amazon.ae'), ('Noon', 'noon.com'), ('Carrefour UAE', 'carrefouruae.com'), ('Sharaf DG', 'sharafdg.com'), ('Jumbo', 'jumbo.ae')], 'eg': [('Amazon Egypt', 'amazon.eg'), ('Noon', 'noon.com'), ('B.TECH', 'btech.com'), ('Carrefour Egypt', 'carrefouregypt.com')], 'in': [('Amazon India', 'amazon.in'), ('Flipkart', 'flipkart.com'), ('Croma', 'croma.com'), ('Reliance Digital', 'reliancedigital.in'), ('Myntra', 'myntra.com')], 'pk': [('Daraz', 'daraz.pk'), ('PriceOye', 'priceoye.pk')], 'bd': [('Daraz Bangladesh', 'daraz.com.bd'), ('Pickaboo', 'pickaboo.com')], 'cn': [('JD', 'jd.com'), ('Tmall', 'tmall.com'), ('Taobao', 'taobao.com'), ('Suning', 'suning.com')], 'jp': [('Amazon Japan', 'amazon.co.jp'), ('Rakuten', 'rakuten.co.jp'), ('Yodobashi', 'yodobashi.com'), ('Bic Camera', 'biccamera.com')], 'kr': [('Coupang', 'coupang.com'), ('Gmarket', 'gmarket.co.kr'), ('11st', '11st.co.kr')], 'sg': [('Shopee Singapore', 'shopee.sg'), ('Lazada Singapore', 'lazada.sg'), ('Amazon Singapore', 'amazon.sg'), ('Courts', 'courts.com.sg')], 'my': [('Shopee Malaysia', 'shopee.com.my'), ('Lazada Malaysia', 'lazada.com.my'), ('Harvey Norman', 'harveynorman.com.my')], 'id': [('Tokopedia', 'tokopedia.com'), ('Shopee Indonesia', 'shopee.co.id'), ('Blibli', 'blibli.com'), ('Lazada Indonesia', 'lazada.co.id')], 'ph': [('Shopee Philippines', 'shopee.ph'), ('Lazada Philippines', 'lazada.com.ph')], 'th': [('Shopee Thailand', 'shopee.co.th'), ('Lazada Thailand', 'lazada.co.th'), ('Central', 'central.co.th'), ('Power Buy', 'powerbuy.co.th')], 'vn': [('Shopee Vietnam', 'shopee.vn'), ('Lazada Vietnam', 'lazada.vn'), ('Tiki', 'tiki.vn')], 'au': [('Amazon Australia', 'amazon.com.au'), ('JB Hi-Fi', 'jbhifi.com.au'), ('Harvey Norman', 'harveynorman.com.au'), ('Kmart', 'kmart.com.au')], 'nz': [('The Warehouse', 'thewarehouse.co.nz'), ('Noel Leeming', 'noelleeming.co.nz'), ('Mighty Ape', 'mightyape.co.nz'), ('Harvey Norman', 'harveynorman.co.nz')], 'br': [('Mercado Livre', 'mercadolivre.com.br'), ('Amazon Brazil', 'amazon.com.br'), ('Magazine Luiza', 'magazineluiza.com.br')], 'mx': [('Mercado Libre', 'mercadolibre.com.mx'), ('Amazon Mexico', 'amazon.com.mx'), ('Walmart Mexico', 'walmart.com.mx'), ('Liverpool', 'liverpool.com.mx')], 'ar': [('Mercado Libre', 'mercadolibre.com.ar'), ('Frávega', 'fravega.com')], 'cl': [('Mercado Libre', 'mercadolibre.cl'), ('Falabella', 'falabella.com'), ('Paris', 'paris.cl')], 'co': [('Mercado Libre', 'mercadolibre.com.co'), ('Falabella', 'falabella.com.co'), ('Éxito', 'exito.com')], 'pe': [('Mercado Libre', 'mercadolibre.com.pe'), ('Falabella', 'falabella.com.pe'), ('Ripley', 'ripley.com.pe')], 'za': [('Takealot', 'takealot.com'), ('Makro', 'makro.co.za'), ('Woolworths', 'woolworths.co.za')], 'ng': [('Jumia Nigeria', 'jumia.com.ng'), ('Konga', 'konga.com')], 'ke': [('Jumia Kenya', 'jumia.co.ke'), ('Carrefour Kenya', 'carrefour.ke')], 'ma': [('Jumia Morocco', 'jumia.ma'), ('Marjane', 'marjane.ma')], 'il': [('KSP', 'ksp.co.il'), ('Ivory', 'ivory.co.il')]}

def country_major_store_specs(cc=None):
    cc = (cc or current_market().get('country') or DEFAULT_COUNTRY).lower()
    return list(COUNTRY_MAJOR_STORE_DOMAINS.get(cc, ()))

def detect_category(query):
    q = normalize_ar(query)
    for cat in ('gaming', 'sports', 'kids_toys', 'appliances', 'pharmacy', 'beauty', 'auto', 'furniture', 'food_delivery', 'grocery', 'electronics', 'fashion'):
        if any((normalize_ar(w) in q for w in CATEGORY_KEYWORDS.get(cat, ()))):
            return cat
    return ''

def priority_stores_for(query):
    cc = (current_market().get('country') or DEFAULT_COUNTRY).lower()
    if cc == 'kw':
        cat = detect_category(query)
        specialists = list(CATEGORY_SPECIALISTS.get(cat, []))
        tail = [m for m in GENERAL_MARKETPLACES if m not in specialists]
        ordered = specialists + tail
        return ordered[:9] if ordered else list(GENERAL_MARKETPLACES)
    return [label for label, _ in country_major_store_specs(cc)][:9]

def store_domain(name):
    mm = re.search('\\(([a-z0-9.-]+\\.[a-z]{2,})\\)', str(name or ''), flags=re.I)
    if mm:
        return mm.group(1).lower()
    cc = (current_market().get('country') or DEFAULT_COUNTRY).lower()
    n = normalize_name(normalize_ar(name))
    if cc != 'kw':
        for label, domain in country_major_store_specs(cc):
            key = normalize_name(normalize_ar(label))
            if key and (key in n or n in key):
                return domain
        return ''
    for k, d in STORE_DOMAINS.items():
        if k in n or n in k:
            return d
    return ''

def local_rescue_store_specs(query, max_count=None):
    max_count = LOCAL_STORE_RESCUE_MAX if max_count is None else max_count
    if max_count <= 0:
        return []
    seen, out = (set(), [])
    for label in priority_stores_for(query):
        domain = store_domain(label)
        if not domain:
            continue
        key = domain.lower().replace('www.', '')
        if key in seen:
            continue
        seen.add(key)
        out.append((label, key))
        if len(out) >= max_count:
            break
    if len(out) < max_count:
        for label, domain in country_major_store_specs():
            key = domain.lower().replace('www.', '')
            if key in seen:
                continue
            seen.add(key)
            out.append((label, key))
            if len(out) >= max_count:
                break
    return out
JUNK_STORE = re.compile('^(اونلاين|أونلاين|online|الموقعالرسمي|official)$', re.I)

def is_junk_store(name):
    return bool(JUNK_STORE.match(normalize_name(normalize_ar(name))))

def short_query(q):
    q = re.sub('\\([^)]*\\)', ' ', q or '')
    q = re.split('\\s+[-—–]\\s+', q)[0]
    return ' '.join(q.split()[:6]).strip()

def extract_store_names(text):
    stores = []
    for line in (text or '').splitlines():
        m = re.match('^\\s*🏪\\s*[^:：]*[:：]\\s*(.+?)\\s*$', line)
        if m:
            name = m.group(1).strip()
            if name and name not in stores:
                stores.insert(0, name)
            continue
        m = re.match('^\\s*(?:✅|🏆|•)\\s*(.+?)\\s*(?:—|–|-)\\s*(.+)$', line)
        if m and re.search('\\d', m.group(2)):
            name = m.group(1).strip()
            if name and name not in stores:
                stores.append(name)
    return stores[:MAX_STORES]

def is_service_answer(txt):
    return bool(re.search('(?:🏆|•)\\s*.+?\\(\\s*(?:هاتف|Phone|phone|Tel|tel)\\s*:', txt or ''))

def extract_store_offers(txt):
    offers = []
    for line in (txt or '').splitlines():
        s = line.strip()
        m = re.match('^(✅|🏆|•)\\s*(.+?)\\s*(?:—|–|-)\\s*(.+)$', s)
        if not m or not re.search('\\d', m.group(3)):
            continue
        if re.search('\\(\\s*(?:هاتف|Phone|phone|Tel|tel)\\s*:', s):
            continue
        name = m.group(2).strip()
        if is_blocked_store(name, ''):
            print(f'SKIP BLOCKED STORE LINE: {name}')
            continue
        if is_junk_store(name):
            print(f'SKIP JUNK STORE LINE: {s[:80]}')
            continue
        best = m.group(1) in ('✅', '🏆')
        body = s if best else s.lstrip('•').strip()
        offers.append({'line': body, 'name': name, 'best': best})
    return offers[:RESULT_CANDIDATE_SCAN_MAX]

def product_title(txt, fallback=''):
    m = re.search('^\\s*📦\\s*(.+)$', txt or '', flags=re.M)
    if m:
        return f'📦 {m.group(1).strip()}'
    return f'📦 {fallback}' if fallback else ''

def match_url(name, urls):
    if not urls:
        return ''
    if is_blocked_store(name, ''):
        return ''
    if name in urls:
        return '' if is_blocked_store(name, urls[name]) else urls[name]
    nn = normalize_name(name)
    for k, v in urls.items():
        kk = normalize_name(k)
        if nn and kk and (nn in kk or kk in nn):
            return '' if is_blocked_store(k, v) else v
    dom = store_domain(name)
    if dom:
        key = domain_key(dom)
        for k, v in urls.items():
            if key and (key in (v or '').lower() or key in normalize_name(k)):
                return '' if is_blocked_store(k, v) else v
    return ''

def maps_category_for(product):
    q = normalize_ar(product)
    service_intent = any((w in q for w in ('فني', 'تصليح', 'صيانه', 'صيانة', 'تركيب', 'عطل', 'خدمه', 'خدمة', 'repair', 'service', 'installation', 'technician')))
    service_rules = [(('بنشر', 'اطارات', 'إطارات', 'تبديل بطاريه', 'تبديل بطارية', 'tyre', 'tire', 'car battery'), 'محل إطارات وبطاريات سيارات Tyre and car battery shop'), (('سباك', 'plumber', 'plumbing'), 'سباك Plumbing service'), (('كهربائي', 'electrician'), 'كهربائي Electrician'), (('فني زجاج', 'فني مرايا', 'glass repair'), 'فني زجاج ومرايا Glass repair'), (('نجار', 'carpenter'), 'نجار Carpenter'), (('غسيل سياره', 'غسيل سيارة', 'تلميع سياره', 'car wash', 'detailing'), 'Car wash detailing'), (('مفتاح', 'اقفال', 'أقفال', 'locksmith'), 'محل مفاتيح وأقفال Locksmith'), (('مكافحة حشرات', 'pest control'), 'مكافحة حشرات Pest control')]
    for words, category in service_rules:
        if any((w in q for w in words)):
            return category
    if service_intent:
        if any((w in q for w in ('تكييف', 'مكيف', 'سنترال', 'air condition'))):
            return 'فني تكييف Air conditioning repair'
        if any((w in q for w in ('زجاج', 'مرايا', 'المنيوم', 'الومنيوم', 'aluminium'))):
            return 'فني زجاج وألمنيوم Glass and aluminium repair'
        if any((w in q for w in ('كهرباء', 'افياش', 'إنارة', 'اناره', 'electrical'))):
            return 'كهربائي Electrician'
        if any((w in q for w in ('غساله', 'ثلاجه', 'فرن', 'جلايه', 'مكنسه', 'appliance'))):
            return 'صيانة أجهزة منزلية Home appliance repair'
    category_rules = [(('عطر', 'عطور', 'برفان', 'perfume', 'eau de parfum', 'eau de toilette'), 'محل عطور Perfume store'), (('مكياج', 'روج', 'فاونديشن', 'ماسكرا', 'كونسيلر', 'مستحضرات تجميل', 'cosmetic', 'makeup'), 'متجر مستحضرات تجميل Cosmetics store'), (('كريم', 'سيروم', 'واقي شمس', 'عناية بالبشره', 'عناية بالبشرة', 'skincare'), 'صيدلية أو متجر عناية بالبشرة Pharmacy skincare store'), (('دواء', 'صيدليه', 'صيدلية', 'فيتامين', 'مكمل', 'حفاض', 'حفاظ', 'pharmacy', 'medicine'), 'صيدلية Pharmacy'), (('نظاره', 'نظارة', 'عدسات', 'sunglasses', 'eyeglasses', 'contact lens'), 'محل نظارات Optician'), (('ساعه', 'ساعة', 'رولكس', 'watch'), 'محل ساعات Watch store'), (('ذهب', 'مجوهرات', 'خاتم', 'سلسله', 'سلسلة', 'jewelry', 'jewellery'), 'محل مجوهرات Jewelry store'), (('ملابس', 'تيشيرت', 'قميص', 'بنطلون', 'فستان', 'جاكيت', 'قبعه', 'قبعة', 'كاب', 'shirt', 'dress', 'cap', 'clothing'), 'Intersport OR Decathlon OR Sun and Sand Sports OR متجر ملابس Fashion store'), (('حذاء', 'جوتي', 'سنيكر', 'shoe', 'sneaker'), 'Intersport OR Decathlon OR Foot Locker OR متجر أحذية Shoe store'), (('مضرب', 'كره', 'كرة', 'تنس', 'بادل', 'جيم', 'رياضه', 'رياضة', 'under armour', 'nike', 'adidas', 'sports', 'basketball'), 'Intersport OR Decathlon OR Sun and Sand Sports OR متجر رياضي Sports store'), (('ايفون', 'آيفون', 'سامسونج', 'لابتوب', 'بلايستيشن', 'تلفزيون', 'الكترون', 'هاتف', 'جوال', 'كاميرا', 'iphone', 'samsung', 'laptop', 'playstation', 'television', 'electronics'), 'متجر إلكترونيات Electronics store'), (('ثلاجه', 'ثلاجة', 'غساله', 'غسالة', 'فرن', 'مكيف', 'جلايه', 'جلاية', 'مكنسه', 'مكنسة'), 'متجر أجهزة منزلية Home appliances store'), (('كنب', 'صوفا', 'طاولة', 'كرسي', 'اثاث', 'أثاث', 'مرتبه', 'مرتبة', 'furniture', 'mattress'), 'متجر أثاث Furniture store'), (('ادوات منزليه', 'أدوات منزلية', 'صحون', 'قدور', 'مطبخ', 'kitchenware', 'homeware'), 'متجر أدوات منزلية Homeware store'), (('العاب اطفال', 'ألعاب أطفال', 'لعبه', 'لعبة', 'toy'), 'متجر ألعاب أطفال Toy store'), (('عربانه', 'عربة أطفال', 'كرسي طفل', 'رضاعه', 'رضاعة', 'baby'), 'متجر مستلزمات أطفال Baby store'), (('قطع غيار', 'زيت محرك', 'اكسسوارات سياره', 'إكسسوارات سيارة', 'car accessories', 'auto parts'), 'متجر قطع غيار وإكسسوارات سيارات Auto parts store'), (('دريل', 'عدد', 'ادوات', 'أدوات', 'مسمار', 'صبغ', 'دهان', 'hardware', 'tools'), 'متجر عدد وأدوات Hardware store'), (('اكل قطط', 'أكل قطط', 'اكل كلاب', 'أكل كلاب', 'حيوانات', 'pet'), 'متجر مستلزمات حيوانات أليفة Pet store'), (('كتاب', 'روايه', 'رواية', 'قرطاسيه', 'قرطاسية', 'book', 'stationery'), 'مكتبة Bookstore stationery')]
    for words, category in category_rules:
        if any((w in q for w in words)):
            return category
    if any((w in q for w in GROCERY_WORDS)) or any((w in q for w in ('مياه', 'مشروب', 'اغذيه', 'أغذية', 'طعام', 'شوكولاته', 'شوكولاتة', 'مناديل', 'منظف', 'غسيل', 'grocery', 'food', 'beverage'))):
        return 'جمعية تعاونية أو سوبرماركت Supermarket'
    return f"متجر يبيع {product} {current_market().get('country_name', '')}"

def maps_search_url(product, lat=None, lng=None):
    category = maps_category_for(product)
    safe_category = urllib.parse.quote(category)
    if lat is not None and lng is not None:
        return f'https://www.google.com/maps/search/{safe_category}/@{lat},{lng},15z'
    return f'https://www.google.com/maps/search/{safe_category}'

def send_maps_button(from_number, product, bot_id, lang):
    m = market_for_user(from_number)
    url = maps_search_url(product, m.get('lat'), m.get('lng')) if m.get('lat') is not None and m.get('lng') is not None else maps_search_url(product)
    send_whatsapp_cta(from_number, T(lang, 'maps_body'), url, bot_id, T(lang, 'maps_btn'))
_SERVICE_LINE_RE = re.compile('^\\s*(🏆|✅|•)\\s*(.+?)\\s*\\(\\s*(?:هاتف|Phone|phone|Tel|tel)\\s*[:：]\\s*([^)]+?)\\s*\\)\\s*(?:(?:—|–|-|:|،|,)\\s*)?(.*)$')
SERVICE_REQUEST_MSG = {'ar': 'السلام عليكم 👋\nأحتاج {service}\nمتى ممكن؟', 'en': 'Hello 👋\nI need {service}\nWhen are you available?', 'fr': 'Bonjour 👋\nJ’ai besoin de : {service}\nQuand êtes-vous disponible ?', 'es': 'Hola 👋\nNecesito: {service}\n¿Cuándo está disponible?', 'pt': 'Olá 👋\nPreciso de: {service}\nQuando está disponível?', 'tr': 'Merhaba 👋\n{service} lazım\nNe zaman müsaitsiniz?', 'ru': 'Здравствуйте 👋\nНужно: {service}\nКогда вы доступны?', 'zh': '您好 👋\n我需要：{service}\n什么时候方便？', 'hi': 'नमस्ते 👋\nमुझे चाहिए: {service}\nआप कब उपलब्ध हैं?', 'ur': 'السلام علیکم 👋\nمجھے چاہیے: {service}\nآپ کب دستیاب ہیں؟'}
SERVICE_REQUEST_BUTTON = {'ar': '📲 اطلب الخدمة', 'en': '📲 Request service', 'fr': '📲 Demander', 'es': '📲 Solicitar', 'pt': '📲 Solicitar', 'tr': '📲 Talep gönder', 'ru': '📲 Запросить', 'zh': '📲 预约服务', 'hi': '📲 सेवा मांगें', 'ur': '📲 سروس مانگیں'}

def _market_dial_code(cc=None):
    cc = (cc or current_market().get('country') or DEFAULT_COUNTRY or 'kw').lower()
    codes = [code for code, c in CALLING_CODE_TO_COUNTRY.items() if c == cc]
    if not codes:
        return '965' if cc == 'kw' else ''
    return sorted(codes, key=len)[0]

def _service_phone_intl(raw_phone, dial=None):
    digits = re.sub('\\D', '', str(raw_phone or ''))
    if digits.startswith('00'):
        digits = digits[2:]
    if len(digits) < 6:
        return ''
    dial = dial if dial is not None else _market_dial_code()
    if dial and digits.startswith(dial) and (len(digits) >= len(dial) + 6):
        return digits
    return f"{dial}{digits.lstrip('0')}" if dial else digits

def _service_request_link(intl_phone, service_desc, lang='ar'):
    template = SERVICE_REQUEST_MSG.get(lang) or _dynamic_translate_ui(SERVICE_REQUEST_MSG['en'], lang)
    service = re.sub('\\s+', ' ', str(service_desc or '')).strip()[:120]
    msg = template.format(service=service) if service else template.split('\n')[0]
    return f'https://wa.me/{intl_phone}?text={urllib.parse.quote(msg)}'

def parse_service_providers(txt):
    intro, providers = ([], [])
    for line in (txt or '').splitlines():
        s = line.strip()
        if not s:
            continue
        if re.match('(?im)^\\s*LINKS\\s*:', s):
            continue
        m = _SERVICE_LINE_RE.match(s)
        if m:
            providers.append({'emoji': m.group(1), 'name': m.group(2).strip(' -—–:'), 'phone': m.group(3).strip(), 'detail': (m.group(4) or '').strip(' -—–')})
        elif not providers:
            intro.append(s)
    return ('\n'.join(intro).strip(), providers)

def send_service_result(from_number, txt, bot_id, lang, service_desc):
    intro, providers = parse_service_providers(txt)
    if not providers:
        send_whatsapp_text(from_number, txt, bot_id)
        return 0
    if intro:
        send_whatsapp_text(from_number, intro, bot_id)
    dial = _market_dial_code()
    sent = 0
    button = (SERVICE_REQUEST_BUTTON.get(lang) or _dynamic_translate_ui(SERVICE_REQUEST_BUTTON['en'], lang))[:20]
    for p in providers[:MAX_STORES]:
        body = f"{p['emoji']} {p['name']}\n📞 {p['phone']}"
        if p.get('detail'):
            body += f"\n{p['detail']}"
        intl = _service_phone_intl(p['phone'], dial)
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
        send_whatsapp_text(from_number, T(lang, 'not_found'), bot_id)
        return 'none'
    if is_service_answer(txt):
        send_service_result(from_number, txt, bot_id, lang, query)
        return 'service'
    offers = extract_store_offers(txt)
    if not offers:
        send_whatsapp_text(from_number, txt, bot_id)
        return 'info'
    title = product_title(txt, query)
    if title:
        send_whatsapp_text(from_number, title, bot_id)
    core = title[2:].strip() if title.startswith('📦') else query
    fq = short_query(core) or short_query(query)
    if best_only:
        best = next((o for o in offers if o['best']), offers[0])
        offers = [best]
    sent = 0
    for o in offers[:MAX_STORES]:
        url = match_url(o['name'], urls)
        if not is_direct_store_url(url):
            print(f"SKIP NON-DIRECT CTA: {o['name']} -> {url}")
            continue
        send_whatsapp_cta(from_number, o['line'], url, bot_id, f"🛒 {o['name'][:18]}")
        sent += 1
    if sent == 0:
        send_whatsapp_text(from_number, T(lang, 'not_found'), bot_id)
        return 'none'
    return 'product'
GEMINI_STATS = {'search_calls': 0, 'plain_calls': 0}
GEMINI_STATS_LOCK = threading.Lock()

def call_gemini(parts, system=SYSTEM_PROMPT, use_search=True):
    model = GEMINI_SEARCH_MODEL if use_search else GEMINI_FAST_MODEL
    gemini_url = f'{GEMINI_BASE_URL}/{model}:generateContent'
    payload = {'systemInstruction': {'parts': [{'text': system + (market_instruction() if use_search else '')}]}, 'contents': [{'role': 'user', 'parts': parts}], 'generationConfig': {'temperature': 0, 'maxOutputTokens': 1000 if use_search else 300}}
    if use_search:
        payload['tools'] = [{'google_search': {}}]
    with GEMINI_STATS_LOCK:
        key = 'search_calls' if use_search else 'plain_calls'
        GEMINI_STATS[key] += 1
        print(f'GEMINI CALL model={model} search={use_search} totals={GEMINI_STATS}')
    try:
        r = requests.post(gemini_url, params={'key': GEMINI_API_KEY}, json=payload, timeout=(5, GEMINI_SEARCH_TIMEOUT_SECONDS if use_search else GEMINI_PLAIN_TIMEOUT_SECONDS))
        if r.status_code >= 400:
            print(f'Gemini HTTP {r.status_code}: {r.text[:500]}')
            return ('', {})
        data = r.json()
        candidates = data.get('candidates') or []
        if not candidates:
            return ('', {})
        cand = candidates[0]
        text = ''.join((p.get('text', '') for p in cand.get('content', {}).get('parts', []))).strip()
        pairs = []
        m = re.search('(?im)^\\s*LINKS\\s*:\\s*(.+)$', text)
        if m:
            raw = m.group(1)
            for part in re.split('[,،]+', raw):
                part = part.strip()
                if '=' in part:
                    name, dom = part.split('=', 1)
                    name, dom = (name.strip(), clean_domain(dom))
                    if name and '.' in dom:
                        pairs.append((name, dom))
            text = re.sub('(?im)^\\s*LINKS\\s*:.*$', '', text).strip()
        text = re.sub('https?://\\S+', '', text).replace('**', '').strip()
        metadata = cand.get('groundingMetadata', {}) or {}
        chunks = metadata.get('groundingChunks', []) or []
        uris = [(c.get('web') or {}).get('uri', '') for c in chunks]
        finals = resolve_all(uris[:12]) if uris else []
        records = []
        for i, chunk in enumerate(chunks[:12]):
            web = chunk.get('web') or {}
            raw_uri = web.get('uri', '')
            final_uri = finals[i] if i < len(finals) else raw_uri
            records.append({'title': web.get('title', ''), 'raw': raw_uri, 'url': final_uri or raw_uri})
        urls_map = {}
        used_urls = set()
        stores = extract_store_names(text)
        supports = metadata.get('groundingSupports', []) or []
        for store in stores:
            store_norm = normalize_name(store)
            for support in supports:
                segment = (support.get('segment') or {}).get('text', '')
                if store_norm and store_norm in normalize_name(segment):
                    for idx in support.get('groundingChunkIndices', []) or []:
                        if 0 <= idx < len(records):
                            url = records[idx]['url']
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
                if rec['url'] and key and (key in haystack) and (rec['url'] not in used_urls):
                    urls_map[name] = rec['url']
                    used_urls.add(rec['url'])
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
                if rec['url'] and key and (key in haystack) and (rec['url'] not in used_urls):
                    urls_map[store] = rec['url']
                    used_urls.add(rec['url'])
                    break
        if len(urls_map) < RESULT_CANDIDATE_SCAN_MAX:
            for rec in records:
                url = rec['url']
                if not url or url in used_urls:
                    continue
                label = source_label(rec['title'], url)
                if label not in urls_map:
                    urls_map[label] = url
                    used_urls.add(url)
                if len(urls_map) >= RESULT_CANDIDATE_SCAN_MAX:
                    break
        return (text, dict(list(urls_map.items())[:RESULT_CANDIDATE_SCAN_MAX]))
    except Exception as e:
        print(f'Gemini err {e}')
        return ('', {})

def source_label(title, url):
    title = (title or '').strip()
    if title:
        return title[:40]
    try:
        host = urllib.parse.urlparse(url).netloc.replace('www.', '')
        return host.split('.')[0] or 'المتجر'
    except Exception:
        return 'المتجر'

def split_product_aliases(product_name):
    parts = [p.strip() for p in re.split('\\s*[|｜]\\s*', product_name or '') if p.strip()]
    unique = []
    for part in parts:
        if part not in unique:
            unique.append(part)
    return unique[:2]

def fuse_identity_aliases(lens_title, vision_name, extra_aliases=None):
    aliases = []

    def _add(value):
        value = (value or '').strip()
        if value and value.upper() not in ('NONE', 'UNKNOWN') and (value not in aliases):
            aliases.append(value)
    _add(lens_title)
    for part in split_product_aliases(vision_name):
        _add(part)
    for extra in extra_aliases or []:
        _add(extra)
    return aliases[:4]
TRANSLATE_NAME_SYSTEM = 'أنت مترجم أسماء منتجات تجارية للبحث في المتاجر.\nحوّل اسم المنتج إلى الاسم التجاري الإنجليزي الأدق كما يُكتب في صفحات المتاجر.\n- أبقِ البراند والموديل والأرقام كما هي (iPhone 15 Pro, 256GB, PS5, Spalding).\n- ترجم الوصف والفئة والحجم (كرة سلة -> basketball، 1 لتر -> 1L، حليب كامل الدسم -> full fat milk).\n- إذا كان البراند مكتوباً بالعربي حوّله لتهجئته اللاتينية الرسمية (سبولدينج -> Spalding، المراعي -> Almarai).\n- لا تشرح ولا تضف خيارات. أرجع سطراً واحداً فقط بالإنجليزية.'
EN_NAME_CACHE = {}
EN_NAME_LOCK = threading.Lock()

def english_search_name(query):
    q = ' '.join(str(query or '').split()).strip()
    if not q:
        return ''
    if not re.search('[\\u0600-\\u06FF\\u0900-\\u097F\\u3040-\\u30FF\\u3400-\\u9FFF\\u0400-\\u04FF]', q):
        return q
    if re.search('[A-Za-z]', q):
        parts = [x.strip() for x in re.split('\\s*[|｜]\\s*', q) if x.strip()]
        latin = next((x for x in parts if re.search('[A-Za-z]', x) and (not re.search('[\\u0600-\\u06FF\\u0900-\\u097F\\u3040-\\u30FF\\u3400-\\u9FFF\\u0400-\\u04FF]', x))), '')
        if latin and len(latin) <= 100:
            return latin
    key = re.sub('\\s+', ' ', normalize_ar(q))[:150]
    with EN_NAME_LOCK:
        if key in EN_NAME_CACHE:
            return EN_NAME_CACHE[key]
    raw, _ = call_gemini([{'text': q}], system=TRANSLATE_NAME_SYSTEM, use_search=False)
    name = (raw or '').strip().splitlines()[0].strip().strip('"').strip("'")
    if not re.search('[A-Za-z]', name) or re.search('[\\u0600-\\u06FF\\u0900-\\u097F\\u3040-\\u30FF\\u3400-\\u9FFF\\u0400-\\u04FF]', name) or len(name) > 90:
        name = ''
    with EN_NAME_LOCK:
        if len(EN_NAME_CACHE) > 3000:
            EN_NAME_CACHE.clear()
        EN_NAME_CACHE[key] = name
    print(f'EN SEARCH NAME: {q!r} -> {name!r}')
    return name

def _query_candidates(query, english_name=''):
    raw_parts = [p.strip() for p in re.split('\\s*[|｜]\\s*', query or '') if p.strip()]
    ar_parts = [p for p in raw_parts if re.search('[\\u0600-\\u06FF]', p)]
    en_parts = [p for p in raw_parts if re.search('[A-Za-z]', p) and (not re.search('[\\u0600-\\u06FF]', p))]
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
    t = normalize_ar(txt or '')
    phrases = ('لم يتم العثور', 'لم اعثر', 'ما لقيت', 'تعذر العثور', 'لا توجد نتائج', 'غير موجود ضمن نتائج البحث', 'لم اجد', 'عذرا', 'could not find', "couldn't find", 'no results', 'not found', 'unable to find', 'was not found', 'couldn’t find')
    return any((normalize_ar(p) in t for p in phrases))

def is_informational_answer(txt):
    if not txt or is_no_result_answer(txt):
        return False
    if extract_store_offers(txt) or is_service_answer(txt) or '📦' in txt:
        return False
    return len(txt.strip()) >= 80

def _lens_source_name(item, index):
    source = (item.get('source') or '').strip()
    if source:
        return source[:40]
    try:
        host = urllib.parse.urlparse(item.get('link') or '').netloc.replace('www.', '')
        return (host.split('.')[0] or f'Lens {index}')[:40]
    except Exception:
        return f'Lens {index}'
KUWAIT_STORE_HINTS = ('.com.kw', '.kw', 'kuwait', 'الكويت', 'xcite', 'eureka', 'best al yousifi', 'best alyousifi', 'jarir', 'level shoes', 'future store', 'blink', 'noon kuwait', 'carrefour kuwait', 'lulu kuwait', 'jm3eia', 'جمعية', 'taw9eel', 'توصيل', 'intersport kuwait', 'decathlon kuwait', 'boutiqaat', 'boots kuwait', 'yiaco', 'royal pharmacy', 'talabat kuwait', 'keeta kuwait')
US_STORE_HINTS = ('amazon.com', 'walmart.com', 'target.com', 'bestbuy.com', 'costco.com', 'homedepot.com', 'lowes.com', 'macys.com', 'nordstrom.com', 'zappos.com', 'bhphotovideo.com', 'newegg.com', 'rei.com', 'dickssportinggoods.com', 'ebay.com')
CHINA_STORE_HINTS = ('aliexpress.com', 'alibaba.com', '1688.com', 'taobao.com', 'tmall.com', 'shein.com', 'temu.com', 'dhgate.com', 'made-in-china.com', 'banggood.com', 'gearbest.com', 'jd.com', 'pinduoduo.com')

def _result_hay_host(item):
    hay = ' '.join((str(item.get(k) or '') for k in ('title', 'source', 'link', 'domain', 'snippet', 'price', 'price_text', 'currency', 'country', 'market_country', '_lens_country', '_shopping_gl'))).lower()
    try:
        host = urllib.parse.urlparse(str(item.get('link') or item.get('url') or '')).netloc.lower().replace('www.', '')
    except Exception:
        host = ''
    return (hay, host)

def _host_matches_any(host, domains):
    host = (host or '').lower().strip('.')
    for domain in domains:
        d = str(domain or '').lower().strip('.')
        if host == d or host.endswith('.' + d):
            return True
    return False

def _explicit_market_country(item):
    for key in ('market_country', 'country'):
        value = str((item or {}).get(key) or '').lower().strip()
        if len(value) == 2 and value in COUNTRY_META:
            return value
    return ''

def _search_geo_country(item):
    for key in ('_shopping_gl', '_lens_country'):
        value = str((item or {}).get(key) or '').lower().strip()
        if len(value) == 2 and value in COUNTRY_META:
            return value
    return ''

def _host_country_code(host):
    host = (host or '').lower().split(':', 1)[0]
    if not host:
        return ''
    for cc in COUNTRY_META:
        for tld in country_tlds(cc):
            if host == tld.lstrip('.') or host.endswith(tld):
                return cc
    return ''

def _dynamic_country_url_hit(cc, link, host):
    cc = (cc or '').lower()
    if not cc or len(cc) != 2:
        return False
    text = f'{host} {link}'.lower()
    tokens = (f'/{cc}/', f'-{cc}/', f'-{cc}.', f'_{cc}', f'{cc}-en', f'{cc}-ar', f'{cc}-fr', f'{cc}-es')
    return any((t in text for t in tokens))

def _explicit_currency_codes(item):
    hay, _ = _result_hay_host(item)
    return set(re.findall('\\b[A-Z]{3}\\b', hay.upper())) & KNOWN_CURRENCY_CODES

def is_us_market_result(item):
    explicit = _explicit_market_country(item)
    if explicit:
        return explicit == 'us'
    hay, host = _result_hay_host(item)
    if host.endswith('.us') or _host_matches_any(host, US_STORE_HINTS):
        return True
    if _host_matches_any(host, CHINA_STORE_HINTS):
        return False
    local_codes = set(country_currency_codes())
    if 'USD' in _explicit_currency_codes(item) and 'USD' not in local_codes:
        return True
    return False

def is_china_market_result(item):
    explicit = _explicit_market_country(item)
    if explicit:
        return explicit == 'cn'
    hay, host = _result_hay_host(item)
    if host.endswith('.cn') or _host_matches_any(host, CHINA_STORE_HINTS):
        return True
    local_codes = set(country_currency_codes())
    if 'CNY' in _explicit_currency_codes(item) and 'CNY' not in local_codes or bool(re.search('\\bRMB\\b|人民币|中国|china', hay, flags=re.I)):
        return True
    return False

def is_local_lens_result(item):
    m = current_market()
    cc = (m.get('country') or DEFAULT_COUNTRY).lower()
    explicit = _explicit_market_country(item)
    if explicit:
        return explicit == cc
    hay, host = _result_hay_host(item)
    link = str((item or {}).get('link') or (item or {}).get('url') or '').lower()
    host_cc = _host_country_code(host)
    if host_cc:
        return host_cc == cc
    if _dynamic_country_url_hit(cc, link, host):
        return True
    country_name = str(m.get('country_name') or '').lower()
    if country_name and country_name in hay:
        return True
    if cc == 'kw' and any((h in hay for h in KUWAIT_STORE_HINTS)):
        return True
    for label, domain in country_major_store_specs(cc):
        if _host_matches_any(host, (domain,)) or normalize_name(label) in normalize_name(hay):
            return True
    return False

def is_foreign_lens_result(item):
    if is_local_lens_result(item):
        return False
    cc = (current_market().get('country') or DEFAULT_COUNTRY).lower()
    explicit = _explicit_market_country(item)
    if explicit and explicit != cc:
        return True
    _, host = _result_hay_host(item)
    host_cc = _host_country_code(host)
    if host_cc and host_cc != cc:
        return True
    codes = _explicit_currency_codes(item)
    local_codes = set(country_currency_codes(cc))
    if codes and (not codes & local_codes):
        return True
    return bool(host and (_host_matches_any(host, US_STORE_HINTS) or _host_matches_any(host, CHINA_STORE_HINTS)))

def result_market_rank(item):
    cc = (current_market().get('country') or DEFAULT_COUNTRY).lower()
    url = str((item or {}).get('link') or (item or {}).get('url') or '')
    source = str((item or {}).get('source') or (item or {}).get('name') or '')
    if is_blocked_store(source, url):
        return 99
    explicit = _explicit_market_country(item)
    if explicit == cc:
        return 0
    if explicit == 'us':
        return 0 if cc == 'us' else 1
    if explicit == 'cn':
        return 0 if cc == 'cn' else 1 if cc == 'us' else 2
    if explicit and explicit not in {cc, 'us', 'cn'}:
        return 99
    if cc != 'us' and is_us_market_result(item):
        return 1
    if cc != 'cn' and is_china_market_result(item):
        return 1 if cc == 'us' else 2
    if is_local_lens_result(item):
        return 0
    if is_us_market_result(item):
        return 0 if cc == 'us' else 1
    if is_china_market_result(item):
        return 0 if cc == 'cn' else 1 if cc == 'us' else 2
    _, host = _result_hay_host(item)
    host_cc = _host_country_code(host)
    if host_cc and host_cc not in {cc, 'us', 'cn'}:
        return 99
    codes = _explicit_currency_codes(item)
    local_codes = set(country_currency_codes(cc))
    if codes:
        if 'USD' in codes and cc != 'us':
            return 1
        if 'CNY' in codes and cc != 'cn':
            return 1 if cc == 'us' else 2
        if codes & local_codes:
            search_cc = _search_geo_country(item)
            if cc in {'us', 'cn'} and search_cc == cc:
                return 0
            return 99
        return 99
    return 99

def filter_allowed_market_results(verified, exclude_local=False):
    kept = {}
    for name, info in (verified or {}).items():
        item = {'link': info.get('url', ''), 'source': name, 'title': info.get('title', ''), 'currency': info.get('currency', ''), 'price': info.get('price_text', '') or info.get('price', ''), 'market_country': info.get('market_country', '') or info.get('country', '')}
        rank = result_market_rank(item)
        if rank == 99 or (exclude_local and rank == 0):
            print(f"MARKET FILTER REJECT rank={rank}: {name} -> {info.get('url', '')}")
            continue
        info['market_rank'] = rank
        kept[name] = info
    return kept

def prepare_market_offer(info, name, lang='ar'):
    item = {'link': info.get('url', ''), 'source': name, 'title': info.get('title', ''), 'currency': info.get('currency', ''), 'price': info.get('price_text', '') or info.get('price', ''), 'market_country': info.get('market_country', '') or info.get('country', '')}
    rank = info.get('market_rank')
    if rank is None:
        rank = result_market_rank(item)
    if rank == 99:
        return None
    try:
        numeric = float(info.get('price'))
    except Exception:
        numeric = None
    if numeric is None:
        return None
    if rank == 0:
        return (rank, numeric, f'{format_price(numeric)} {currency_label(lang)}')
    src = (info.get('currency') or '').upper().strip()
    if not src:
        src = 'USD' if rank == 1 else 'CNY'
    shown, converted = display_global_price(numeric, '', src, lang)
    return (rank, converted if converted is not None else numeric, shown)

def filter_local_market_only(verified):
    kept = {}
    for name, info in (verified or {}).items():
        item = {'link': info.get('url', ''), 'source': name, 'title': info.get('title', ''), 'currency': info.get('currency', ''), 'price': info.get('price_text', '') or info.get('price', ''), 'market_country': info.get('market_country', '') or info.get('country', '')}
        if result_market_rank(item) != 0:
            print(f"LOCAL MODE REJECT FOREIGN/UNKNOWN: {name} -> {info.get('url', '')}")
            continue
        kept[name] = info
    return kept

def lens_priced_offers(lens_context, lang='ar', local_only=True, exclude_local=False):
    if not lens_context:
        return {}
    offers = {}
    used_urls = set()
    for i, item in enumerate(lens_context.get('matches') or [], 1):
        url = (item.get('link') or '').strip()
        title = (item.get('title') or '').strip()
        price_text = (item.get('price') or '').strip()
        price_value = item.get('price_value')
        currency = (item.get('currency') or '').strip()
        in_stock = item.get('in_stock')
        if not title or not is_lens_product_url(url, item) or url in used_urls:
            continue
        market_rank = result_market_rank(item)
        if market_rank == 99:
            print(f'LENS REJECT OTHER COUNTRY: {title} -> {url}')
            continue
        if local_only and market_rank != 0:
            continue
        if exclude_local and market_rank == 0:
            print(f'GLOBAL EXCLUDE LOCAL LENS: {title} -> {url}')
            continue
        if in_stock is False:
            print(f'LENS PRODUCT OOS SKIP: {title} -> {url}')
            continue
        if not price_text and price_value in (None, ''):
            continue
        name = _lens_source_name(item, i)
        base = name
        n = 2
        while name in offers:
            name = f'{base} {n}'
            n += 1
        numeric = None
        try:
            numeric = _authoritative_price_value(price_value, price_text, currency)
        except Exception:
            numeric = None
        if market_rank == 0:
            shown = format_lens_price(price_text, price_value, lang, currency or None)
        else:
            src_currency = (currency or '').upper().strip()
            if not src_currency:
                src_currency = 'USD' if is_us_market_result(item) else 'CNY' if is_china_market_result(item) else ''
            shown, converted = display_global_price(price_value, price_text, src_currency, lang)
            if converted is not None:
                numeric = converted
        offers[name] = {'url': url, 'price': numeric, 'price_text': shown, 'is_local': market_rank == 0, 'market_rank': market_rank, 'title': title, 'position': int(item.get('position') or i), 'exact': bool(item.get('exact')), 'section': item.get('section') or '', 'image_url': item.get('image') or item.get('thumbnail') or ''}
        used_urls.add(url)
    offers = filter_same_size(offers, (lens_context.get('chosen') or {}).get('title') or '')
    ranked = sorted(offers.items(), key=lambda kv: (kv[1].get('market_rank', 99), 0 if kv[1].get('exact') else 1, 0 if kv[1].get('section') == 'visual_matches' else 1, kv[1].get('position', 999)))
    top = ranked[:MAX_STORES]
    top.sort(key=lambda kv: (kv[1].get('market_rank', 99), kv[1].get('price') if kv[1].get('price') is not None else 10 ** 9))
    return dict(top)

def verify_lens_direct_matches(lens_context, local_only=True, exclude_local=False):
    if not lens_context:
        return {}
    candidates = {}
    ordered = sorted((lens_context.get('matches') or [])[:24], key=lambda m: (result_market_rank(m), 0 if m.get('exact') else 1, int(m.get('position') or 99)))
    for i, m in enumerate(ordered[:8], 1):
        url = (m.get('link') or '').strip()
        title = (m.get('title') or '').strip()
        source = (m.get('source') or f'Lens {i}').strip()
        if not title or not is_lens_product_url(url, m):
            continue
        market_rank = result_market_rank(m)
        if market_rank == 99:
            continue
        if local_only and market_rank != 0:
            continue
        if exclude_local and market_rank == 0:
            print(f'GLOBAL EXCLUDE LOCAL VERIFY: {title} -> {url}')
            continue
        candidates[source] = url
    verified = verify_offers(candidates, (lens_context.get('chosen') or {}).get('title', ''))
    verified = filter_same_size(verified, (lens_context.get('chosen') or {}).get('title', ''))
    if verified:
        print(f'LENS HTML VERIFIED: {list(verified)}')
    return verified

def _shopping_clean_query(query):
    q = re.sub('^.*?—\\s*', '', str(query or '')).strip() or str(query or '')
    q = q.split('|')[0].strip()
    return ' '.join(q.split()[:10])

def _shopping_gl_supported(gl):
    cc = str(gl or '').strip().lower()
    return not cc or cc in GOOGLE_SHOPPING_SUPPORTED_GL

def _log_unsupported_shopping_gl(gl):
    cc = str(gl or '').strip().lower() or '-'
    with _SHOPPING_UNSUPPORTED_LOG_LOCK:
        if cc in _SHOPPING_UNSUPPORTED_LOGGED:
            return
        _SHOPPING_UNSUPPORTED_LOGGED.add(cc)
    print(f'GOOGLE SHOPPING SKIP unsupported_gl={cc}; fallback=google_search+lens')

def _serpapi_shopping_request(query, gl, hl='en', timeout_seconds=None):
    if SHOPPING_GEO_GUARD and gl and (not _shopping_gl_supported(gl)):
        _log_unsupported_shopping_gl(gl)
        return []
    params = {'engine': 'google_shopping', 'q': query, 'api_key': SERPAPI_API_KEY, 'hl': hl, 'output': 'json'}
    if gl:
        params['gl'] = gl
    try:
        data = _serpapi_cached_json(
            params,
            timeout=(4, timeout_seconds or SERPAPI_TIMEOUT_SECONDS),
            label=f"GOOGLE SHOPPING gl={gl or '-'}",
        )
        if data is None:
            return []
        results = data.get('shopping_results') or []
        print(f"GOOGLE SHOPPING: q={query[:60]!r} gl={gl or '-'} -> {len(results)} cards")
        return results[:SHOPPING_RESULT_LIMIT]
    except Exception as e:
        print(f'GOOGLE SHOPPING EXCEPTION: {e}')
        return []

def _serpapi_google_organic_market_request(query, gl, hl='en', domain='', timeout_seconds=None, limit=8):
    if not SERPAPI_API_KEY:
        return []
    q = _shopping_clean_query(query or '')
    if not q:
        return []
    search_q = f'{q} site:{domain}' if domain else q
    params = {'engine': 'google', 'q': search_q, 'api_key': SERPAPI_API_KEY, 'google_domain': 'google.com', 'gl': (gl or 'us').lower(), 'hl': hl or 'en', 'num': max(3, min(10, int(limit or 8))), 'output': 'json'}
    try:
        data = _serpapi_cached_json(
            params,
            timeout=(3.5, timeout_seconds or MARKET_FALLBACK_TIMEOUT_SECONDS),
            label=f"LOCAL GOOGLE SEARCH gl={gl or '-'} domain={domain or '-'}",
        )
        if data is None:
            return []
        rows = data.get('organic_results') or []
        out = []
        for pos, row in enumerate(rows, 1):
            link = str(row.get('link') or '').strip()
            if not link.startswith(('http://', 'https://')):
                continue
            try:
                host = urllib.parse.urlparse(link).netloc.lower().replace('www.', '')
            except Exception:
                host = ''
            if domain and (not _host_matches_any(host, (domain,))):
                continue
            source = str(row.get('source') or row.get('displayed_link') or '').strip()
            if not source:
                source = host.split('.')[0].replace('-', ' ').title() if host else 'Google'
            price_text = _google_organic_price_text(row)
            out.append({'title': str(row.get('title') or q).strip(), 'link': link, 'source': source, 'position': int(row.get('position') or pos), 'section': 'local_google_organic_fallback', 'exact': False, 'thumbnail': str(row.get('thumbnail') or '').strip(), 'image': str(row.get('thumbnail') or '').strip(), 'price': price_text, 'price_value': _extract_numeric_price(price_text) if price_text else None, 'currency': detect_currency_code(price_text, '', (gl or '').lower()) if price_text else '', 'in_stock': None, 'condition': '', '_lens_country': (gl or '').lower(), '_market_presence_fallback': True, '_google_organic_fallback': True})
            if len(out) >= limit:
                break
        print(f"LOCAL GOOGLE SEARCH gl={gl or '-'} domain={domain or '-'} -> {len(out)} result(s)")
        return out
    except Exception as e:
        print(f"LOCAL GOOGLE SEARCH EXCEPTION gl={gl or '-'} domain={domain or '-'}: {e}")
        return []

def _immersive_product_stores(page_token):
    params = {'engine': 'google_immersive_product', 'page_token': page_token, 'api_key': SERPAPI_API_KEY}
    if IMMERSIVE_MORE_STORES:
        params['more_stores'] = 'true'
    try:
        data = _serpapi_cached_json(
            params,
            timeout=(4, SERPAPI_TIMEOUT_SECONDS),
            label='IMMERSIVE PRODUCT',
        )
        if data is None:
            return []
        stores = (data.get('product_results') or {}).get('stores') or []
        print(f'IMMERSIVE PRODUCT: {len(stores)} store offers')
        return stores
    except Exception as e:
        print(f'IMMERSIVE EXCEPTION: {e}')
        return []

def _shopping_direct_url(url):
    url = (url or '').strip()
    if not url.startswith(('http://', 'https://')):
        return ''
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return ''
    if 'google.' in host:
        url = get_final_url(url)
    return url if is_direct_store_url(url) else ''

def _ai_local_market_search_query(query, english_name=''):
    if not LOCAL_AI_QUERY_RESCUE_ENABLED:
        return ''
    m = current_market()
    cc = (m.get('country') or DEFAULT_COUNTRY).lower()
    country_name = m.get('country_name') or cc.upper()
    local_hl = m.get('search_hl') or country_search_hl(cc)
    base = _shopping_clean_query(english_name or query) or _shopping_clean_query(query)
    if not base or not local_hl or local_hl == 'en':
        return ''
    key = (cc, normalize_ar(base).lower())
    now = time.time()
    with LOCAL_QUERY_CACHE_LOCK:
        hit = LOCAL_QUERY_CACHE.get(key)
        if hit and now - hit[0] < 86400:
            return hit[1]
    system = f'You create ONE high-precision shopping search query for the local retail market in {country_name}.\nReturn ONLY the query, one line, no explanation.\nUse the dominant language/wording that shoppers and local stores in {country_name} commonly use.\nPreserve every brand, model, SKU, capacity, size and number exactly. Never invent specifications.\nTranslate only generic product/category words when that improves local merchant discovery.\nIf the original international/English wording is already what local stores use, return it unchanged.'
    try:
        raw, _ = text77_call_gemini([{'text': base}], system=system, use_search=False)
        candidate = re.sub('^[\\s\\"\'`]+|[\\s\\"\'`]+$', '', (raw or '').splitlines()[0].strip()) if raw else ''
        candidate = re.sub('^(?:QUERY|SEARCH_QUERY)\\s*:\\s*', '', candidate, flags=re.I).strip()
        must_keep = {t.lower() for t in re.findall('[A-Za-z0-9][A-Za-z0-9._/-]*', base) if re.search('\\d', t)}
        cand_low = candidate.lower()
        if not candidate or len(candidate) > 180 or any((tok not in cand_low for tok in must_keep)):
            candidate = ''
    except Exception as e:
        print(f'LOCAL AI QUERY ERR {cc}: {e}')
        candidate = ''
    with LOCAL_QUERY_CACHE_LOCK:
        if len(LOCAL_QUERY_CACHE) > 2000:
            LOCAL_QUERY_CACHE.clear()
        LOCAL_QUERY_CACHE[key] = (now, candidate)
    if candidate and candidate.lower() != base.lower():
        print(f'LOCAL AI QUERY market={cc}: {base!r} -> {candidate!r}')
    return candidate

def google_shopping_offers(query, lang='ar', allow_global=False, lens_context=None, english_name=''):
    if not ENABLE_GOOGLE_SHOPPING or not SERPAPI_API_KEY:
        return {}
    raw_q = _shopping_clean_query(query)
    en_q = _shopping_clean_query(english_name or query)
    if not (raw_q or en_q):
        return {}
    m = current_market()
    local_cc = (m.get('country') or DEFAULT_COUNTRY).lower()
    local_hl = (m.get('search_hl') or country_search_hl(local_cc) or 'en').lower()
    if allow_global:
        specs = [(en_q or raw_q, 'us', 'en')]
    else:
        specs = [(en_q or raw_q, local_cc, 'en')]
        local_query = raw_q or en_q
        if (local_query, local_cc, local_hl) not in specs:
            specs.append((local_query, local_cc, local_hl))
        if LOCAL_SHOPPING_PRIMARY_PASSES >= 3 and en_q and (local_hl != 'en') and ((en_q, local_cc, local_hl) not in specs):
            specs.append((en_q, local_cc, local_hl))
        specs = specs[:LOCAL_SHOPPING_PRIMARY_PASSES]

    def _fetch_spec(spec):
        q, gl, hl = spec
        cards = _serpapi_shopping_request(q, gl, hl=hl)
        out = []
        for card in cards or []:
            c = dict(card)
            c['_shopping_gl'] = gl
            c['_shopping_hl'] = hl
            c['_shopping_query'] = q
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
                print(f'LOCAL SHOPPING PASS ERR spec={spec}: {e}')
    dedup_cards, seen_cards = ([], set())
    for card in cards:
        sig = (str(card.get('link') or '').split('?')[0].lower(), str(card.get('title') or '').lower(), str(card.get('source') or '').lower(), str(card.get('price') or '').lower())
        if sig in seen_cards:
            continue
        seen_cards.add(sig)
        dedup_cards.append(card)
    cards = dedup_cards
    if not cards:
        print(f'SHOPPING PRIMARY EMPTY market={local_cc} allow_global={allow_global}; continuing to rescue layers')
    offers, used_urls, immersive_tokens = ({}, set(), [])

    def _add(store_name, url, price_text, price_value, title, position, market_country=''):
        url = _shopping_direct_url(url)
        if not url or url in used_urls:
            return
        if is_blocked_store(store_name, url):
            print(f'SHOPPING BLOCKED STORE REJECT: {store_name} -> {url}')
            return
        search_gl = (market_country or ('us' if allow_global else local_cc)).lower()
        item = {'link': url, 'source': store_name, 'title': title, 'price': str(price_text or ''), 'currency': '', 'market_country': '', '_shopping_gl': search_gl}
        market_rank = result_market_rank(item)
        if allow_global:
            expected_rank = 1 if search_gl == 'us' else 2 if search_gl == 'cn' else None
            if market_rank == 0 or market_rank == 99 or (expected_rank is not None and market_rank != expected_rank):
                print(f'SHOPPING GLOBAL MARKET REJECT rank={market_rank} gl={search_gl}: {store_name} -> {url}')
                return
        elif market_rank != 0:
            print(f'SHOPPING LOCAL REJECT rank={market_rank} gl={search_gl}: {store_name} -> {url}')
            return
        resolved_market_country = local_cc if market_rank == 0 else 'us' if market_rank == 1 else 'cn' if market_rank == 2 else ''
        try:
            numeric = _authoritative_price_value(price_value, price_text, currency)
        except Exception:
            numeric = None
        if numeric is None:
            numeric = _extract_numeric_price(str(price_text or ''))
        if numeric is None or numeric <= 0:
            return
        if allow_global:
            fallback_cur = 'USD' if search_gl == 'us' else 'CNY' if search_gl == 'cn' else ''
            src_currency = detect_currency_code(str(price_text or ''), fallback_cur, search_gl)
            shown, converted = display_global_price(numeric, str(price_text or ''), src_currency, lang)
            sort_price = converted if converted is not None else numeric
        else:
            accepted = set(country_currency_codes(local_cc))
            local_primary = (m.get('currency') or '').upper()
            src_currency = detect_currency_code(str(price_text or ''), local_primary, local_cc)
            if src_currency and accepted and (src_currency not in accepted):
                print(f'SHOPPING LOCAL CURRENCY REJECT: {store_name} {price_text} detected={src_currency}')
                return
            src_currency = src_currency or local_primary
            if src_currency and src_currency != local_primary:
                converted = convert_to_local(numeric, src_currency)
                sort_price = converted if converted is not None else numeric
                shown = f'{format_price(numeric, src_currency)} {src_currency}'
            else:
                sort_price = numeric
                shown = f'{format_price(numeric, local_primary)} {currency_label(lang)}'
        name = (store_name or '').strip()[:40] or f'Store {len(offers) + 1}'
        base, n = (name, 2)
        while name in offers:
            name = f'{base} {n}'
            n += 1
        offers[name] = {'url': url, 'price': sort_price, 'price_text': shown, 'title': (title or '').strip(), 'currency': src_currency, 'position': position, 'source_layer': 'shopping', 'market_country': resolved_market_country, 'search_gl': search_gl}
        used_urls.add(url)
    for i, card in enumerate(cards, 1):
        title = (card.get('title') or '').strip()
        source = (card.get('source') or '').strip()
        direct = (card.get('link') or '').strip()
        gl = (card.get('_shopping_gl') or ('us' if allow_global else local_cc)).lower()
        added_before = len(offers)
        if direct:
            _add(source or title, direct, card.get('price'), card.get('extracted_price'), title, i, gl)
        token = (card.get('immersive_product_page_token') or '').strip()
        if token and len(offers) == added_before:
            immersive_tokens.append((i, title, token, gl))
    if immersive_tokens and IMMERSIVE_LOOKUPS_MAX > 0 and (len(offers) < MAX_STORES):
        picked = immersive_tokens[:IMMERSIVE_LOOKUPS_MAX]
        market_snapshot = current_market()
        futures = {SHOPPING_POOL.submit(_run_with_market, market_snapshot, _immersive_product_stores, token): (pos, title, gl) for pos, title, token, gl in picked}
        for future, (pos, title, gl) in futures.items():
            try:
                stores = future.result(timeout=SERPAPI_TIMEOUT_SECONDS + 5) or []
            except Exception as e:
                print(f'IMMERSIVE FUTURE ERR: {e}')
                continue
            for store in stores:
                _add(store.get('name') or '', store.get('link') or '', store.get('price') or store.get('total') or '', store.get('extracted_price') if store.get('extracted_price') not in (None, '') else store.get('extracted_total'), title, pos, gl)
    if not allow_global and SHOPPING_GEO_GUARD and (not _shopping_gl_supported(local_cc)) and SHOPPING_UNSUPPORTED_ORGANIC_FALLBACK and (len(offers) < LOCAL_RESULTS_TARGET):
        organic_specs = [('Local', '')]
        organic_specs.extend(local_rescue_store_specs(en_q or raw_q, LOCAL_STORE_RESCUE_MAX))
        futures = {LOCAL_SHOPPING_POOL.submit(_serpapi_google_organic_market_request, en_q or raw_q, local_cc, local_hl, domain, MARKET_FALLBACK_TIMEOUT_SECONDS, 6): (label, domain) for label, domain in organic_specs}
        for fut, (label, domain) in futures.items():
            try:
                rows = fut.result(timeout=MARKET_FALLBACK_TIMEOUT_SECONDS + 2) or []
            except Exception as e:
                print(f'LOCAL ORGANIC PRICE RESCUE ERR {label}: {e}')
                continue
            for row in rows:
                if result_market_rank(row) != 0:
                    continue
                _add(row.get('source') or label, row.get('link') or '', row.get('price') or '', row.get('price_value'), row.get('title') or '', int(row.get('position') or 999), local_cc)
                if len(offers) >= LOCAL_RESULTS_TARGET:
                    break
            if len(offers) >= LOCAL_RESULTS_TARGET:
                break
    if not allow_global and len(offers) < LOCAL_RESULTS_TARGET and (LOCAL_STORE_RESCUE_MAX > 0) and (not SHOPPING_GEO_GUARD or _shopping_gl_supported(local_cc)):
        rescue_specs = local_rescue_store_specs(query, LOCAL_STORE_RESCUE_MAX)

        def _rescue(label, domain):
            q = en_q or raw_q
            rs = _serpapi_shopping_request(f'{q} site:{domain}', local_cc, hl=local_hl, timeout_seconds=MARKET_FALLBACK_TIMEOUT_SECONDS)
            return (label, domain, rs)
        futures = {LOCAL_SHOPPING_POOL.submit(_rescue, label, domain): (label, domain) for label, domain in rescue_specs}
        for fut, (label, domain) in futures.items():
            try:
                _, _, rs = fut.result(timeout=MARKET_FALLBACK_TIMEOUT_SECONDS + 4)
            except Exception as e:
                print(f'LOCAL STORE RESCUE ERR {label}: {e}')
                continue
            for card in rs or []:
                link = (card.get('link') or '').strip()
                direct = _shopping_direct_url(link) or link
                try:
                    host = urllib.parse.urlparse(direct).netloc.lower().replace('www.', '')
                except Exception:
                    host = ''
                if not _host_matches_any(host, (domain,)):
                    continue
                _add(card.get('source') or label, direct, card.get('price'), card.get('extracted_price'), card.get('title') or '', int(card.get('position') or 999), local_cc)
    if not allow_global and LOCAL_COUNTRY_RESCUE_ENABLED and (len(offers) < LOCAL_RESULTS_TARGET) and (not SHOPPING_GEO_GUARD or _shopping_gl_supported(local_cc)):
        country_name = str(m.get('country_name') or '').strip()
        rescue_queries = []
        base = en_q or raw_q
        if country_name and base:
            rescue_queries.append(f'{base} {country_name}')
        if LOCAL_COUNTRY_RESCUE_PASSES >= 2 and raw_q and (raw_q.lower() != base.lower()) and country_name:
            rescue_queries.append(f'{raw_q} {country_name}')
        for rq in rescue_queries[:LOCAL_COUNTRY_RESCUE_PASSES]:
            try:
                rs = _serpapi_shopping_request(rq, local_cc, hl=local_hl, timeout_seconds=MARKET_FALLBACK_TIMEOUT_SECONDS)
            except Exception as e:
                print(f'LOCAL COUNTRY RESCUE ERR {local_cc}/{rq[:70]}: {e}')
                rs = []
            for card in rs or []:
                _add(card.get('source') or country_name or 'Local', card.get('link') or '', card.get('price') or '', card.get('extracted_price'), card.get('title') or '', int(card.get('position') or 999), local_cc)
                if len(offers) >= LOCAL_RESULTS_TARGET:
                    break
            if len(offers) >= LOCAL_RESULTS_TARGET:
                break
    if not allow_global and LOCAL_AI_QUERY_RESCUE_ENABLED and (len(offers) < LOCAL_RESULTS_TARGET) and (not SHOPPING_GEO_GUARD or _shopping_gl_supported(local_cc)):
        localized_q = _ai_local_market_search_query(raw_q or query, en_q or english_name)
        if localized_q and localized_q.lower() not in {str(en_q or '').lower(), str(raw_q or '').lower()}:
            try:
                rs = _serpapi_shopping_request(localized_q, local_cc, hl=local_hl, timeout_seconds=MARKET_FALLBACK_TIMEOUT_SECONDS)
            except Exception as e:
                print(f'LOCAL AI SHOPPING RESCUE ERR {local_cc}: {e}')
                rs = []
            for card in rs or []:
                _add(card.get('source') or (m.get('country_name') or 'Local'), card.get('link') or '', card.get('price') or '', card.get('extracted_price'), card.get('title') or '', int(card.get('position') or 999), local_cc)
                if len(offers) >= LOCAL_RESULTS_TARGET:
                    break
    offers = filter_same_size(offers, en_q or raw_q)
    if lens_context:
        offers = filter_verified_with_lens(offers, lens_context)
    if offers:
        print(f"SHOPPING OFFERS FINAL market={local_cc} passes={specs}: {[(n, o['price']) for n, o in offers.items()]}")
    return offers

def _shopping_layer_search(query, lang, allow_global=False, lens_context=None, english_name=''):
    offers = google_shopping_offers(query, lang, allow_global=allow_global, lens_context=lens_context, english_name=english_name)
    if not offers:
        return ('', {})
    sorted_v = sorted(offers.items(), key=lambda x: x[1].get('price') if x[1].get('price') is not None else 10 ** 9)
    arabic_display = _shopping_clean_query(query)
    if lang == 'ar' and (not re.search('[\\u0600-\\u06FF]', arabic_display)) and re.search('[\\u0600-\\u06FF]', str(query or '')):
        arabic_display = str(query).strip()
    display = arabic_display or _shopping_clean_query(english_name or query)
    lines = [f'📦 {display}', '']
    urls = {}
    for i, (name, info) in enumerate(sorted_v[:max(MAX_STORES * 2, 6)]):
        prefix = '✅' if i == 0 else '•'
        size_note = format_pack_size(extract_pack_size(info.get('title', '')))
        size_suffix = f' ({size_note})' if size_note else ''
        lines.append(f"{prefix} {name} — {info.get('price_text') or format_price(info.get('price'))}{size_suffix}")
        urls[name] = info['url']
    return ('\n'.join(lines), urls)

def _new_layer_search(query, lang, prompt_text=None, source_image_b64=None, source_image_mime=None, lens_context=None, allow_global=False, english_name=''):
    cached = None if source_image_b64 else cache_get(query, lang)
    if cached:
        return cached
    lens_cards = lens_priced_offers(lens_context, lang, local_only=False, exclude_local=allow_global)
    if lens_cards:
        display_name = (lens_context.get('chosen') or {}).get('title') or query
        lines = [f'📦 {display_name}', '']
        new_urls = {}
        for i, (name, info) in enumerate(lens_cards.items()):
            prefix = '✅' if i == 0 else '•'
            shown_price = info.get('price_text') or format_price(info.get('price'))
            lines.append(f'{prefix} {name} — {shown_price}')
            new_urls[name] = info['url']
        print(f'LENS EXACT/VISUAL CARDS USED: {list(new_urls)}')
        return ('\n'.join(lines), new_urls)
    lens_verified = verify_lens_direct_matches(lens_context, local_only=False, exclude_local=allow_global)
    if lens_verified:
        lens_verified = filter_allowed_market_results(lens_verified, exclude_local=allow_global)
        prepared = []
        for name, info in lens_verified.items():
            ready = prepare_market_offer(info, name, lang)
            if not ready:
                continue
            market_rank, sort_price, shown = ready
            info['shown'] = shown
            info['sort_price'] = sort_price
            info['market_rank'] = market_rank
            prepared.append((name, info))
        sorted_v = sorted(prepared, key=lambda x: (x[1].get('market_rank', 99), x[1].get('sort_price', 10 ** 9)))
        if sorted_v:
            display_name = (lens_context.get('chosen') or {}).get('title') or query
            lines = [f'📦 {display_name}', '']
            new_urls = {}
            for i, (name, info) in enumerate(sorted_v[:MAX_STORES]):
                prefix = '✅' if i == 0 else '•'
                lines.append(f"{prefix} {name} — {info['shown']}")
                new_urls[name] = info['url']
            return ('\n'.join(lines), new_urls)
    candidates = _query_candidates(query, english_name=english_name)
    print(f'SEARCH CANDIDATES (EN-FIRST): {candidates}')
    best_txt, best_urls = ('', {})
    for attempt in range(1, MAX_SEARCH_ATTEMPTS + 1):
        search_term = candidates[(attempt - 1) % len(candidates)]
        ar_hint = ''
        for part in re.split('\\s*[|｜]\\s*', str(query or '')):
            if re.search('[\\u0600-\\u06FF]', part):
                ar_hint = re.sub('^.*?—\\s*', '', part).strip()
                break
        if attempt == 1 and prompt_text:
            context = f'{prompt_text}\n'
        else:
            context = ''
        priority_stores = priority_stores_for(search_term)
        stores_hint = '، '.join(priority_stores)
        market_name = current_market().get('country_name', 'Kuwait')
        if attempt == 1:
            _stores_phrase = f'ابدأ بالمتاجر المحلية القوية مثل: {stores_hint}، ثم وسّع لأي متجر محلي موثوق. ' if stores_hint else 'ابدأ بأقوى المتاجر المتخصصة والمنصات المحلية، ثم وسّع لأي متجر محلي موثوق. '
            search_scope = _stores_phrase + f"ابحث محلياً أيضاً بصياغة لغة السوق {country_search_hl()} وبالعملة/العملات المحلية {', '.join(country_currency_codes())}. " + 'بعد استنفاد المحلي ابحث في الولايات المتحدة، ثم الصين فقط. ' + f'ارفض أي دولة أخرى غير {market_name} والولايات المتحدة والصين. '
        else:
            search_scope = f'اعمل بحثاً أوسع لنفس المنتج مع الحفاظ على هذا الترتيب الإجباري: {market_name} أولاً، ثم الولايات المتحدة، ثم الصين فقط. لا تسمح لأي دولة رابعة، ولا ترفع نتيجة أمريكية أو صينية فوق نتيجة محلية بسبب السعر. '
        current_prompt = f'{context}ابحث في {market_name} عن هذا الاسم تحديداً: {search_term}. ' + (f'المقابل العربي لنفس المنتج (استخدمه أيضاً عند البحث في المتاجر ذات الفهرسة العربية): {ar_hint}. ' if ar_hint and (not re.search('[\\u0600-\\u06FF]', search_term)) else '') + (f"الاسم المختار من Google Lens هو: {(lens_context.get('chosen') or {}).get('title', '')}. لا توسع البحث إلى موديلات أخرى من نفس البراند، ولا تقبل اختلافاً واضحاً في اللون أو النقشة أو وجود الكعب. " if lens_context else '') + f'{search_scope}استخدم الاسم كما هو، ويمكن تجربة تهجئات قريبة لنفس المنتج فقط. قارن نفس المنتج بنفس المواصفات فقط (الحجم/السعة/الوزن، واللون إذا كان يغيّر السعر): عبوة أصغر أو أكبر أو سعة تخزين مختلفة تعتبر منتجاً مختلفاً ولا تدخل المقارنة. اذكر المواصفة بجانب كل سعر إذا كانت معروفة (مثل: 1 لتر أو 256GB). أعطني حتى {MAX_STORES} متاجر مختلفة. الترتيب الإجباري حسب السوق أولاً: {market_name} ثم الولايات المتحدة ثم الصين فقط؛ وداخل كل سوق فقط رتب من الأرخص إلى الأغلى. كل نتيجة يجب أن تحتوي سعراً رقمياً ورابط صفحة المنتج المباشرة داخل المتجر. ممنوع روابط Google وصفحات البحث والتصنيف، وممنوع أي متجر من دولة غير هذه الأسواق الثلاثة. لا تكتب متوفر أو InStock بدلاً من السعر. حافظ على السعر الرقمي والعملة كما في المصدر؛ التطبيق ينسق عدد الخانات حسب العملة. {lang_instr(lang)}'
        txt, urls = call_gemini([{'text': current_prompt}])
        urls = direct_urls_only(urls)
        offers = extract_store_offers(txt)
        if is_service_answer(txt):
            if len(txt) >= 40:
                cache_put(query, lang, txt, urls)
            return (txt, urls)
        if is_informational_answer(txt):
            return (txt, urls)
        if is_no_result_answer(txt) or (txt and (not offers)):
            print(f'SEARCH ATTEMPT {attempt} NO RESULT: {search_term}')
            continue
        if txt and offers and urls:
            verified = verify_offers(urls, search_term)
            verified = filter_verified_with_lens(verified, lens_context)
            verified = filter_same_size(verified, query)
            verified = filter_allowed_market_results(verified, exclude_local=allow_global)
            if verified:
                prepared = []
                for name, info in verified.items():
                    ready = prepare_market_offer(info, name, lang)
                    if not ready:
                        continue
                    market_rank, sort_price, shown = ready
                    info['market_rank'] = market_rank
                    info['sort_price'] = sort_price
                    info['shown'] = shown
                    prepared.append((name, info))
                sorted_v = sorted(prepared, key=lambda x: (x[1].get('market_rank', 99), x[1].get('sort_price', 10 ** 9)))
                title = product_title(txt, ar_hint if lang == 'ar' and ar_hint else search_term)
                lines = [title, '']
                new_urls = {}
                for i, (name, info) in enumerate(sorted_v[:MAX_STORES]):
                    prefix = '✅' if i == 0 else '•'
                    size_note = format_pack_size(extract_pack_size(info.get('title', '')))
                    size_suffix = f' ({size_note})' if size_note else ''
                    lines.append(f"{prefix} {name} — {info['shown']}{size_suffix}")
                    new_urls[name] = info['url']
                final_txt = '\n'.join(lines)
                if not source_image_b64:
                    cache_put(query, lang, final_txt, new_urls)
                return (final_txt, new_urls)
            if lens_context:
                print('LENS STRICT: no verified exact product; skipping unverified CTA fallback')
                continue
            kept = []
            for offer in offers:
                matched = match_url(offer['name'], urls)
                if not (matched and is_direct_store_url(matched)):
                    continue
                item = {'link': matched, 'source': offer['name'], 'title': offer['line'], 'price': offer['line']}
                market_rank = result_market_rank(item)
                if market_rank == 99 or (allow_global and market_rank == 0):
                    print(f"UNVERIFIED MARKET REJECT rank={market_rank}: {offer['name']} -> {matched}")
                    continue
                numeric = _extract_numeric_price(offer.get('line', ''))
                if numeric is None:
                    continue
                if market_rank == 0:
                    shown = f'{format_price(numeric)} {currency_label(lang)}'
                    sort_price = numeric
                else:
                    src = detect_currency_code(offer.get('line', ''), 'USD' if market_rank == 1 else 'CNY')
                    shown, converted = display_global_price(numeric, offer.get('line', ''), src, lang)
                    sort_price = converted if converted is not None else numeric
                kept.append({'offer': offer, 'url': matched, 'market_rank': market_rank, 'sort_price': sort_price, 'shown': shown})
            kept.sort(key=lambda x: (x['market_rank'], x['sort_price']))
            if kept:
                title = product_title(txt, ar_hint if lang == 'ar' and ar_hint else search_term)
                lines = [title, '']
                clean_urls = {}
                for i, rec in enumerate(kept[:MAX_STORES]):
                    prefix = '✅' if i == 0 else '•'
                    offer = rec['offer']
                    lines.append(f"{prefix} {offer['name']} — {rec['shown']}")
                    clean_urls[offer['name']] = rec['url']
                final_txt = '\n'.join(lines)
                if not source_image_b64:
                    cache_put(query, lang, final_txt, clean_urls)
                return (final_txt, clean_urls)
        best_txt, best_urls = (txt or best_txt, urls or best_urls)
        print(f'SEARCH ATTEMPT {attempt} FAILED term={search_term}')
    return ('', {})
_PRICE_CHAR_TRANSLATION = str.maketrans({**{ord(a): b for a, b in zip('٠١٢٣٤٥٦٧٨٩', '0123456789')}, **{ord(a): b for a, b in zip('۰۱۲۳۴۵۶۷۸۹', '0123456789')}, ord('٫'): '.', ord('٬'): ','})

def _normalize_price_chars(value):
    return str(value or '').translate(_PRICE_CHAR_TRANSLATION)

def _normalize_price_token(token, currency_code=''):
    t = _normalize_price_chars(token).replace('\xa0', ' ').replace('\u202f', ' ').strip()
    t = re.sub('\\s+', '', t)
    if not t:
        return None
    t = re.sub('[^0-9,.-]', '', t)
    if not re.search('\\d', t):
        return None
    neg = t.startswith('-')
    t = t.lstrip('-')
    dots, commas = (t.count('.'), t.count(','))
    decimals = CURRENCY_DECIMALS.get((currency_code or '').upper(), 2)
    if dots and commas:
        last_dot, last_comma = (t.rfind('.'), t.rfind(','))
        dec_sep = '.' if last_dot > last_comma else ','
        tail = len(t) - max(last_dot, last_comma) - 1
        if tail in ({decimals} if decimals in (0, 3) else {1, 2}):
            thou = ',' if dec_sep == '.' else '.'
            t = t.replace(thou, '').replace(dec_sep, '.')
        else:
            t = t.replace('.', '').replace(',', '')
    elif commas:
        pos = t.rfind(',')
        tail = len(t) - pos - 1
        if decimals == 3 and tail == 3 or (decimals == 2 and tail in (1, 2)):
            t = t[:pos].replace(',', '') + '.' + t[pos + 1:]
        else:
            t = t.replace(',', '')
    elif dots:
        pos = t.rfind('.')
        tail = len(t) - pos - 1
        if t.count('.') > 1:
            if decimals == 3 and tail == 3 or (decimals == 2 and tail in (1, 2)):
                t = t[:pos].replace('.', '') + '.' + t[pos + 1:]
            else:
                t = t.replace('.', '')
        elif decimals == 0 and tail == 3:
            t = t.replace('.', '')
    try:
        val = float(t)
        return -val if neg else val
    except Exception:
        return None

def _extract_numeric_price(line):
    text = _normalize_price_chars(line).replace('\xa0', ' ').replace('\u202f', ' ')
    cur = detect_currency_code(text, '')
    parts = re.split('\\s+(?:—|–|-)\\s+', text)
    zones = [parts[-1]] if len(parts) > 1 else []
    zones.append(text)
    number_re = re.compile("(?<!\\w)(\\d{1,3}(?:,\\d{2})+,\\d{3}(?:\\.\\d{1,3})?|\\d{1,3}(?:[ .,'’]\\d{3})+(?:[.,]\\d{1,3})?|\\d+(?:[.,]\\d{1,3})?)(?!\\w)")
    for zone in zones:
        matches = list(number_re.finditer(zone))
        if not matches:
            continue
        ranked = []
        for mm in matches:
            if _number_overlaps_measurement_span(zone, mm.start(), mm.end()):
                continue
            context = zone[max(0, mm.start() - 12):min(len(zone), mm.end() + 12)]
            has_cur = bool(re.search('\\b[A-Z]{3}\\b|US\\$|A\\$|C\\$|S\\$|HK\\$|NZ\\$|NT\\$|[$€£¥￥₹₩₺₽₪₴₸₾₼฿₫₱₦₵৳₲₭₮]|د\\.ك|ر\\.س|د\\.إ|ر\\.ق|ر\\.ع|د\\.ب|KD\\b|RMB\\b', context, re.I))
            ranked.append((1 if has_cur else 0, mm.start(), mm.group(1)))
        ranked.sort(reverse=True)
        for _, _, token in ranked:
            val = _normalize_price_token(token, cur)
            if val is not None and val > 0:
                return val
    return None



def _authoritative_price_value(price_value, price_text='', currency_code=''):
    """Prefer an explicit displayed retail price over upstream extracted_price.

    Some providers parse European decimal commas incorrectly (80,00€ -> 8000).
    When the visible price text contains an explicit currency, our locale-aware parser
    is authoritative. Otherwise retain the structured numeric value as fallback.
    """
    raw = _normalize_price_chars(price_text).replace('\xa0', ' ').replace('\u202f', ' ').strip()
    explicit_currency = bool(re.search(
        r'\b(?:USD|EUR|GBP|KWD|KD|SAR|AED|QAR|BHD|OMR|CNY|RMB|JPY|CAD|AUD|CHF|INR|KRW|TRY|RUB)\b|US\$|A\$|C\$|S\$|HK\$|NZ\$|NT\$|[$€£¥￥₹₩₺₽₪]|د\.ك|ر\.س|د\.إ|ر\.ق|ر\.ع|د\.ب',
        raw, re.I
    ))
    if raw and explicit_currency:
        parsed = _extract_numeric_price(raw)
        if parsed is not None and parsed > 0:
            try:
                upstream = float(price_value) if price_value not in (None, '') else None
            except Exception:
                upstream = None
            if upstream is not None and upstream > 0 and abs(upstream - parsed) > max(0.01, parsed * 0.02):
                print(f'PRICE TEXT OVERRIDE upstream={upstream} visible={parsed} raw={raw[:80]!r}')
            return parsed
    try:
        upstream = float(price_value) if price_value not in (None, '') else None
    except Exception:
        upstream = None
    if upstream is not None and upstream > 0:
        return upstream
    parsed = _extract_numeric_price(raw) if raw else None
    return parsed if parsed is not None and parsed > 0 else None

def _result_offers(txt, urls, layer, lens_context=None):
    out = []
    if not txt:
        return out
    title = product_title(txt, '').replace('📦', '').strip()
    for offer in extract_store_offers(txt):
        url = match_url(offer.get('name', ''), urls or {})
        if not is_direct_store_url(url):
            continue
        price = _extract_numeric_price(offer.get('line', ''))
        if price is None or price <= 0:
            continue
        host = urllib.parse.urlparse(url).netloc.lower().replace('www.', '')
        market_item = {'link': url, 'source': offer.get('name', ''), 'title': title, 'price': offer.get('line', '')}
        market_rank = result_market_rank(market_item)
        if market_rank == 99:
            continue
        item = {'name': offer.get('name', '').strip(), 'url': url, 'price': price, 'title': title, 'line': offer.get('line', ''), 'layer': layer, 'host': host, 'is_local': market_rank == 0, 'market_rank': market_rank, 'exact': False, 'lens_position': 999}
        if lens_context:
            for m in lens_context.get('matches') or []:
                if (m.get('link') or '').strip() == url:
                    item['exact'] = bool(m.get('exact'))
                    item['lens_position'] = int(m.get('position') or 999)
                    break
        out.append(item)
    return out

def _old_layer_search(query, lang, prompt_text=None, lens_context=None, allow_global=False, english_name=''):
    if not OLD_LAYER_ENABLED:
        return ('', {})
    search_name = english_name or query
    market_name = current_market().get('country_name', 'Kuwait')
    if allow_global:
        base_prompt = f'ابحث عن {search_name} في الولايات المتحدة ثم الصين فقط. استبعد بلد المستخدم {market_name} واستبعد كل الدول الأخرى. سعر رقمي واضح ورابط صفحة المنتج المباشر مع العملة الأصلية. {lang_instr(lang)}'
        variants = [base_prompt, f'{search_name} United States buy online exact product direct page price USD {lang_instr(lang)}', f'{search_name} China buy online exact product direct page price CNY RMB AliExpress Alibaba 1688 Taobao SHEIN JD {lang_instr(lang)}']
    else:
        variants = [prompt_text or f"ابحث عن {search_name} في {market_name} فقط. استخدم الاسم التجاري الإنجليزي ولغة السوق {country_search_hl()}، وافحص المتاجر المتخصصة والمحلية الصغيرة. السعر يجب أن يكون رقمياً بعملة محلية مقبولة ({', '.join(country_currency_codes())}) ورابط صفحة منتج مباشر. {lang_instr(lang)}", f'{search_name} United States buy online exact product direct product page current price USD; US stores only. {lang_instr(lang)}', f'{search_name} China buy online exact product direct product page current price CNY RMB; Chinese stores only such as AliExpress Alibaba 1688 Taobao SHEIN Tmall JD DHgate. {lang_instr(lang)}']
    market_snapshot = current_market()
    futures = []
    for variant in variants:
        for _ in range(OLD_LAYER_DUPLICATES):
            futures.append(OLD_SEARCH_POOL.submit(_run_with_market, market_snapshot, call_gemini, [{'text': variant}]))
    results = []
    for future in futures:
        try:
            txt, urls = future.result(timeout=GEMINI_SEARCH_TIMEOUT_SECONDS + 5)
            urls = direct_urls_only(urls)
            if txt and urls and extract_store_offers(txt):
                results.append((txt, urls))
        except Exception as exc:
            print(f'OLD LAYER FUTURE ERR: {exc}')
    if not results:
        print('OLD LAYER: no usable result')
        return ('', {})
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
        print(f'GLOBAL OLD LAYER US/CN ONLY: {list(verified)}')
    if not verified:
        print('OLD LAYER: no verified direct offers')
        return ('', {})
    prepared = []
    for name, info in verified.items():
        ready = prepare_market_offer(info, name, lang)
        if not ready:
            continue
        market_rank, sort_price, shown = ready
        info['market_rank'] = market_rank
        info['sort_price'] = sort_price
        info['shown'] = shown
        prepared.append((name, info))
    sorted_v = sorted(prepared, key=lambda x: (x[1].get('market_rank', 99), x[1].get('sort_price', 10 ** 9)))
    title = product_title(best_txt, query)
    lines = [title, '']
    new_urls = {}
    for i, (name, info) in enumerate(sorted_v[:max(MAX_STORES * 2, 6)]):
        prefix = '✅' if i == 0 else '•'
        size_note = format_pack_size(extract_pack_size(info.get('title', '')))
        size_suffix = f' ({size_note})' if size_note else ''
        lines.append(f"{prefix} {name} — {info['shown']}{size_suffix}")
        new_urls[name] = info['url']
    print(f'OLD LAYER VERIFIED: {list(new_urls)}')
    return ('\n'.join(lines), new_urls)

def _store_priority_value(name, url, query=''):
    text = normalize_name(normalize_ar(f'{name} {url}'))
    raw_text = f'{name} {url}'.lower()
    if query:
        ranked_stores = priority_stores_for(query)
        for i, store in enumerate(ranked_stores):
            label = re.sub('\\([^)]*\\)', '', store).strip()
            key = normalize_name(normalize_ar(label))
            dom = store_domain(label)
            dom_key = domain_key(dom) if dom else ''
            if key and key in text or (dom and dom.replace('www.', '') in raw_text) or (dom_key and dom_key in raw_text):
                return 120 - i * 8
    if (current_market().get('country') or DEFAULT_COUNTRY).lower() == 'kw':
        priorities = ('prosportskw', 'tigro', '3roodq8', 'intersport', 'decathlon', 'sssports', 'jm3eia', 'جمعية', 'xcite', 'eureka', 'best', 'yousifi', 'blink', 'jarir', 'lulu', 'carrefour', 'noon', 'taw9eel', 'توصيل', 'boutiqaat', 'boots', 'yiaco', 'levelshoes', 'future', 'talabat', 'keeta')
        for i, token in enumerate(priorities):
            if token in raw_text:
                return len(priorities) - i
    return 0

def _merge_two_layers(query, lang, new_result, old_result, lens_context=None, shopping_result=None):
    new_txt, new_urls = new_result
    old_txt, old_urls = old_result
    shop_txt, shop_urls = shopping_result or ('', {})
    new_offers = _result_offers(new_txt, new_urls, 'new', lens_context)
    old_offers = _result_offers(old_txt, old_urls, 'old', lens_context)
    shop_offers = _result_offers(shop_txt, shop_urls, 'shopping', lens_context)
    all_offers = new_offers + old_offers + shop_offers
    if not all_offers:
        if new_txt:
            return new_result
        if shop_txt:
            return (shop_txt, shop_urls)
        return old_result
    layer_pref = {'shopping': 2, 'new': 1, 'old': 0}
    dedup = {}
    for offer in all_offers:
        key = offer['url'].split('?')[0].rstrip('/').lower()
        previous = dedup.get(key)
        if previous is None or layer_pref.get(offer['layer'], 0) > layer_pref.get(previous['layer'], 0):
            dedup[key] = offer
    offers = [o for o in dedup.values() if o.get('market_rank', 99) != 99]

    def rank(o):
        quality = 0
        quality += 100 if o.get('exact') else 0
        quality += _store_priority_value(o.get('name', ''), o.get('url', ''), query) * 2
        quality += {'shopping': 15, 'new': 12, 'old': 8}.get(o.get('layer'), 8)
        quality += max(0, 20 - min(int(o.get('lens_position', 999)), 20))
        return (o.get('market_rank', 99), -quality, o.get('price', 10 ** 9))
    offers.sort(key=rank)
    chosen = offers[:MAX_STORES]
    chosen.sort(key=lambda o: (o.get('market_rank', 99), o.get('price') if o.get('price') is not None else 10 ** 9))
    lens_display = ((lens_context or {}).get('chosen') or {}).get('title') or ''
    title_candidates = [product_title(new_txt, '').replace('📦', '').strip(), product_title(old_txt, '').replace('📦', '').strip(), re.sub('^.*?—\\s*', '', str(query or '')).strip(), str(query or '').strip()]
    display_title = ''
    if lang == 'ar':
        for cand in title_candidates:
            if cand and re.search('[\\u0600-\\u06FF]', cand):
                display_title = cand
                break
    else:
        display_title = next((c for c in title_candidates if c), '')
    if not display_title:
        display_title = lens_display or str(query or '')
    currency = currency_label(lang)
    lines = [f'📦 {display_title}', '']
    urls = {}
    for i, offer in enumerate(chosen):
        prefix = '✅' if i == 0 else '•'
        lines.append(f"{prefix} {offer['name']} — {format_price(offer['price'])} {currency}")
        urls[offer['name']] = offer['url']
    print('TWO LAYER FINAL:', [(o['layer'], o['name'], o['price']) for o in chosen])
    return ('\n'.join(lines), urls)

def search_product(query, lang, prompt_text=None, source_image_b64=None, source_image_mime=None, lens_context=None, allow_global=False):
    cached = None if source_image_b64 or lens_context else cache_get(query, lang)
    if cached:
        return cached
    english_name = english_search_name(query)
    market_snapshot = current_market()
    shopping_future = None
    if ENABLE_GOOGLE_SHOPPING and SERPAPI_API_KEY:
        shopping_future = SHOPPING_POOL.submit(_run_with_market, market_snapshot, _shopping_layer_search, query, lang, allow_global, lens_context, english_name)
    new_result = _new_layer_search(query, lang, prompt_text=prompt_text, source_image_b64=source_image_b64, source_image_mime=source_image_mime, lens_context=lens_context, allow_global=allow_global, english_name=english_name)
    print(f'NEW LAYER DONE offers={(len(extract_store_offers(new_result[0])) if new_result[0] else 0)}')
    if new_result[0] and (is_service_answer(new_result[0]) or is_informational_answer(new_result[0])):
        if shopping_future:
            shopping_future.cancel()
        return new_result

    def _collect_shopping():
        if not shopping_future:
            return ('', {})
        try:
            return shopping_future.result(timeout=SERPAPI_TIMEOUT_SECONDS + 8) or ('', {})
        except Exception as e:
            print(f'SHOPPING LAYER ERR: {e}')
            return ('', {})
    if lens_context and lens_context.get('force_lens_only'):
        mode = 'GLOBAL' if allow_global else 'LOCAL'
        print(f'OLD LAYER SKIPPED: FASHION LENS-ONLY {mode} MODE')
        shopping_result = _collect_shopping()
        if shopping_result[0]:
            return _merge_two_layers(query, lang, new_result, ('', {}), lens_context, shopping_result)
        return new_result
    old_result = _old_layer_search(query, lang, prompt_text=prompt_text, lens_context=lens_context, allow_global=allow_global, english_name=english_name)
    print(f'OLD LAYER DONE offers={(len(extract_store_offers(old_result[0])) if old_result[0] else 0)}')
    shopping_result = _collect_shopping()
    print(f'SHOPPING LAYER DONE offers={(len(extract_store_offers(shopping_result[0])) if shopping_result[0] else 0)}')
    final_txt, final_urls = _merge_two_layers(query, lang, new_result, old_result, lens_context, shopping_result)
    if final_txt and (not source_image_b64) and (not lens_context):
        cache_put(query, lang, final_txt, final_urls)
    return (final_txt, final_urls)

def extract_products(text):
    text = re.sub('^[•\\-\\*\\d\\.\\)\\s]+', '', text, flags=re.M)
    parts = re.split('\\s*(?:\\n+|\\+|,|،| و | & )\\s*', text.strip())
    parts = [p.strip() for p in parts if len(p.strip()) > 2]
    return parts[:6] if len(parts) > 1 else [text.strip()]

def download_whatsapp_media(mid):
    h = {'Authorization': f'Bearer {WHATSAPP_TOKEN}'}
    meta = _whatsapp_http_session().get(f'{GRAPH_URL}/{mid}', headers=h, timeout=(3, WHATSAPP_TIMEOUT_SECONDS)).json()
    img = _whatsapp_http_session().get(meta['url'], headers=h, timeout=(3, max(WHATSAPP_TIMEOUT_SECONDS, 15)))
    return (base64.b64encode(img.content).decode(), meta.get('mime_type', 'image/jpeg'))
_UI_STORE_ALIASES = {'amazon.com': 'Amazon', 'amazon.sa': 'Amazon', 'amazon.ae': 'Amazon', 'ebay.com': 'eBay', 'walmart.com': 'Walmart', 'aliexpress.com': 'AliExpress', 'alibaba.com': 'Alibaba', 'temu.com': 'Temu', 'shein.com': 'SHEIN', 'underarmour.sa': 'Under Armour', 'underarmour.com': 'Under Armour', 'theathletesfoot.com.kw': "The Athlete's Foot", 'theathletesfoot.com': "The Athlete's Foot", 'sunandsandsports.com': 'Sun & Sand Sports', 'next.sa': 'Next', 'next.com': 'Next', 'made-in-china.com': 'Made-in-China', 'whizzcart.com': 'Whizzcart', 'q8supply.com': 'Q8Supply'}

def _ui_plain_store_name(source='', link=''):
    raw = re.sub('\\s+', ' ', str(source or '')).strip()
    try:
        host = urllib.parse.urlparse(str(link or '')).netloc.lower().split(':')[0]
        host = host[4:] if host.startswith('www.') else host
    except Exception:
        host = ''
    for dom, label in _UI_STORE_ALIASES.items():
        if host == dom or host.endswith('.' + dom):
            return label
    low = raw.lower().replace('www.', '').strip()
    for dom, label in _UI_STORE_ALIASES.items():
        if dom in low:
            return label
    if re.fullmatch('(?:www\\.)?[a-z0-9][a-z0-9.-]*\\.[a-z]{2,}(?:\\.[a-z]{2,})?', low, flags=re.I):
        stem = low.split('.')[0].replace('-', ' ').replace('_', ' ')
        return ' '.join((w.capitalize() for w in stem.split())) or 'المتجر'
    cleaned = re.sub('\\.(?:com|net|org|co|sa|ae|kw|qa|bh|om|uk|de|fr|es|cn)(?:\\.[a-z]{2})?\\b', '', raw, flags=re.I)
    cleaned = re.sub('^www\\.', '', cleaned, flags=re.I)
    return cleaned.strip(' .-/') or 'المتجر'

def _compact_ui_title(value, max_len=68):
    s = re.sub('\\s+', ' ', str(value or '')).strip()
    latin_chars = len(re.findall('[A-Za-z]', s))
    arabic_chars = len(re.findall('[\\u0600-\\u06FF]', s))
    mostly_english = latin_chars > arabic_chars
    if mostly_english:
        parts = [p.strip() for p in re.split('\\s*[|｜]\\s*', s) if p.strip()]
        if parts:
            s = parts[0]
        s = re.sub('^(?:buy|shop|order|get|find)\\s+', '', s, flags=re.I)
        s = re.sub('\\b(?:online|for sale|free shipping|fast delivery|new arrival|best seller|hot sale|official store)\\b', ' ', s, flags=re.I)
        s = re.sub("\\b(?:for women|for men|for girls|for boys|women'?s|men'?s|girl'?s|boy'?s)\\b", ' ', s, flags=re.I)
        s = re.sub('\\b(?:large[- ]capacity|casual|lightweight|fashion|stylish|premium)\\b', ' ', s, flags=re.I)
        s = re.sub('\\b(?:in|from|at)\\s+(?:Kuwait|Saudi Arabia|UAE|United Arab Emirates|USA|United States|UK|United Kingdom)\\b', ' ', s, flags=re.I)
        s = re.sub('\\s*[-–—]\\s*(?:Amazon|eBay|Walmart|SHEIN|AliExpress|Alibaba|Temu|Kuwait|Saudi Arabia|UAE).*$', '', s, flags=re.I)
        s = re.sub('\\s*[,;:]\\s*', ' ', s)
        s = re.sub('\\s{2,}', ' ', s).strip(' ,-|–—')
        words = s.split()
        if len(words) > 8:
            s = ' '.join(words[:8]).rstrip(' ,-|–—') + '…'
        elif len(s) > 58:
            cut = s[:59]
            if ' ' in cut:
                cut = cut.rsplit(' ', 1)[0]
            s = cut.rstrip(' ,-|–—') + '…'
        return s
    s = re.sub('^(?:اشتر(?:ي|ِ)?|اشتري|تسوق|تسوّق|اطلب|شراء)\\s+', '', s, flags=re.I)
    s = re.sub('\\b(?:أونلاين|اونلاين)\\s+(?:في|من)\\s+[^|،,\\-–—]{2,25}\\b', '', s, flags=re.I)
    s = re.sub('\\b(?:في|من)\\s+(?:الكويت|السعودية|الإمارات|الامارات|قطر|البحرين|عمان|بريطانيا|ألمانيا|المانيا|فرنسا|إسبانيا|اسبانيا)\\b', '', s, flags=re.I)
    parts = [p.strip() for p in re.split('\\s*[|｜]\\s*', s) if p.strip()]
    if parts:
        s = parts[0]
    s = re.sub('\\s*[-–—]\\s*(?:تسوق|تسوّق|متوفر|اونلاين|أونلاين).*$', '', s, flags=re.I)
    s = re.sub('\\s{2,}', ' ', s).strip(' ,-|–—')
    if len(s) > max_len:
        cut = s[:max_len + 1]
        if ' ' in cut:
            cut = cut.rsplit(' ', 1)[0]
        s = cut.rstrip(' ,-|–—') + '…'
    return s

def _script_class(token):
    t = str(token or '')
    if re.search('[\\u0600-\\u06FF]', t):
        return 'ar'
    if re.search('[A-Za-z]', t):
        return 'en'
    if re.search('\\d', t):
        return 'num'
    return 'neutral'

def _single_direction_lines(text_value, lang='ar', max_groups=3):
    s = re.sub('\\s+', ' ', str(text_value or '')).strip()
    if not s:
        return []
    tokens = s.split()
    groups, current = ([], [])
    current_cls = None
    default_cls = 'ar' if lang in ('ar', 'ur') else 'en'
    for tok in tokens:
        cls = _script_class(tok)
        if cls in ('num', 'neutral'):
            cls = current_cls or default_cls
        if current and cls != current_cls:
            groups.append(' '.join(current).strip())
            current = [tok]
            current_cls = cls
        else:
            current.append(tok)
            current_cls = cls if current_cls is None else current_cls
    if current:
        groups.append(' '.join(current).strip())
    groups = [g for g in groups if g]
    if len(groups) > max_groups:
        groups = groups[:max_groups - 1] + [' '.join(groups[max_groups - 1:]).strip()]
    return groups

def _split_price_display(price_text):
    s = re.sub('\\s+', ' ', str(price_text or '')).strip()
    if not s:
        return ('', '')
    m = re.match('^(.*?)\\s*\\(([^()]+)\\)\\s*$', s)
    if m:
        return (m.group(1).strip(), m.group(2).strip())
    return (s, '')

def _build_compact_card_body(flag, store, title, price_text, lang='ar'):
    lines = []
    if str(flag or '').strip():
        lines.append(str(flag).strip())
    title_lines = _single_direction_lines(_compact_ui_title(title or ''), lang, max_groups=3)
    for tline in title_lines:
        if tline.strip():
            lines.append(tline.strip())
    price_main, price_secondary = _split_price_display(price_text or '')
    if price_main and re.search('\\d', price_main):
        lines.append(f'*💰 {price_main}*')
        if price_secondary:
            lines.append(f'_({price_secondary})_')
    else:
        lines.append(U(lang, 'price_at_store'))
    return '\n'.join(lines).strip()

def _break_numeric_autolinks(value):
    s = str(value or '')
    pat = re.compile('(?<![\\d.])((?:\\d[\\s-]?){7,}\\d?)(?![\\d.])')

    def repl(m):
        token = m.group(1)
        digit_positions = [i for i, ch in enumerate(token) if ch.isdigit()]
        if len(digit_positions) < 7:
            return token
        pos = digit_positions[min(2, len(digit_positions) - 1)] + 1
        return token[:pos] + '\u2060' + token[pos:]
    return pat.sub(repl, s)

def _remove_ui_autolinks(value):
    s = str(value or '')
    s = re.sub('https?://\\S+', '', s, flags=re.I)
    domain_re = re.compile('\\b(?:www\\.)?([a-z0-9][a-z0-9-]*(?:\\.[a-z0-9-]+)+\\.(?:com|net|org|co|sa|ae|kw|qa|bh|om|uk|de|fr|es|cn|app))\\b', flags=re.I)

    def repl(m):
        dom = m.group(1).lower().replace('www.', '')
        if dom in _UI_STORE_ALIASES:
            return _UI_STORE_ALIASES[dom]
        for known, label in _UI_STORE_ALIASES.items():
            if dom.endswith('.' + known):
                return label
        stem = dom.split('.')[0].replace('-', ' ').replace('_', ' ')
        return ' '.join((w.capitalize() for w in stem.split()))
    s = domain_re.sub(repl, s)
    s = re.sub('\\b([A-Za-z][A-Za-z0-9-]{1,40})\\.(com|sa|ae|kw|qa|bh|om|uk|de|fr|es|cn)\\b', lambda m: _UI_STORE_ALIASES.get(f'{m.group(1).lower()}.{m.group(2).lower()}', m.group(1).replace('-', ' ').title()), s, flags=re.I)
    s = _break_numeric_autolinks(s)
    return re.sub('[ \\t]{2,}', ' ', s).strip()
_WHATSAPP_HTTP_CTX = threading.local()
_TYPING_GRAPH_URL = os.environ.get('WHATSAPP_TYPING_GRAPH_URL', 'https://graph.facebook.com/v26.0')
_TYPING_REFRESH_SECONDS = max(6.0, min(15.0, float(os.environ.get('WHATSAPP_TYPING_REFRESH_SECONDS', '9'))))
_TYPING_MAX_SECONDS = max(10.0, min(30.0, float(os.environ.get('WHATSAPP_TYPING_MAX_SECONDS', '20'))))
_TYPING_BETWEEN_MESSAGES_DELAY = max(0.0, min(0.5, float(os.environ.get('WHATSAPP_TYPING_BETWEEN_MESSAGES_DELAY', '0.18'))))
_TYPING_STATE = {}
_TYPING_LOCK = threading.Lock()
_LAST_INCOMING_MESSAGE_ID = {}
_LAST_INCOMING_LOCK = threading.Lock()

def _remember_incoming_message_id(phone, message_id):
    phone = str(phone or '').strip()
    message_id = str(message_id or '').strip()
    if not phone or not message_id:
        return
    with _LAST_INCOMING_LOCK:
        if len(_LAST_INCOMING_MESSAGE_ID) > 5000:
            _LAST_INCOMING_MESSAGE_ID.clear()
        _LAST_INCOMING_MESSAGE_ID[phone] = message_id

def _latest_incoming_message_id(phone):
    with _LAST_INCOMING_LOCK:
        return _LAST_INCOMING_MESSAGE_ID.get(str(phone or '').strip(), '')

def _typing_api_once(bot_id, message_id):
    if not bot_id or not message_id or (not WHATSAPP_TOKEN):
        return False
    url = f'{_TYPING_GRAPH_URL}/{bot_id}/messages'
    headers = {'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'}
    payload = {'messaging_product': 'whatsapp', 'status': 'read', 'message_id': message_id, 'typing_indicator': {'type': 'text'}}
    try:
        r = _whatsapp_http_session().post(url, json=payload, headers=headers, timeout=(2.0, min(5, WHATSAPP_TIMEOUT_SECONDS)))
        if not r.ok:
            print(f'TYPING ERR {r.status_code}: {r.text[:180]}')
        return r.ok
    except Exception as e:
        print(f'TYPING ERR: {e}')
        return False

def stop_live_typing(phone):
    phone = str(phone or '').strip()
    with _TYPING_LOCK:
        state = _TYPING_STATE.pop(phone, None)
    if state:
        try:
            state['stop'].set()
        except Exception:
            pass

def start_live_typing(phone, bot_id, message_id):
    phone = str(phone or '').strip()
    message_id = str(message_id or '').strip()
    if not phone or not message_id:
        return False
    _remember_incoming_message_id(phone, message_id)
    stop_live_typing(phone)
    stop_event = threading.Event()
    state = {'stop': stop_event, 'bot_id': bot_id, 'message_id': message_id, 'started': time.monotonic()}
    with _TYPING_LOCK:
        _TYPING_STATE[phone] = state

    def _loop():
        started = time.monotonic()
        while not stop_event.is_set():
            if time.monotonic() - started >= _TYPING_MAX_SECONDS:
                break
            _typing_api_once(bot_id, message_id)
            remaining = _TYPING_MAX_SECONDS - (time.monotonic() - started)
            if remaining <= 0:
                break
            if stop_event.wait(min(_TYPING_REFRESH_SECONDS, remaining)):
                break
        stop_event.set()
        with _TYPING_LOCK:
            current = _TYPING_STATE.get(phone)
            if current is state:
                _TYPING_STATE.pop(phone, None)
    threading.Thread(target=_loop, daemon=True, name=f'findzia-typing-{phone[-6:]}').start()
    return True

def _typing_before_outgoing(to, bot_id):
    phone = str(to or '').strip()
    with _TYPING_LOCK:
        active = phone in _TYPING_STATE
    if active:
        stop_live_typing(phone)
        return
    message_id = _latest_incoming_message_id(phone)
    if message_id and _typing_api_once(bot_id, message_id):
        if _TYPING_BETWEEN_MESSAGES_DELAY:
            time.sleep(_TYPING_BETWEEN_MESSAGES_DELAY)

def _whatsapp_http_session():
    session = getattr(_WHATSAPP_HTTP_CTX, 'session', None)
    if session is None:
        session = requests.Session()
        _WHATSAPP_HTTP_CTX.session = session
    return session

def send_whatsapp_text(to, text, bot_id):
    _typing_before_outgoing(to, bot_id)
    url = f'{GRAPH_URL}/{bot_id}/messages'
    h = {'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'}
    safe_text = _remove_ui_autolinks(text)
    payload = {'messaging_product': 'whatsapp', 'to': to, 'type': 'text', 'text': {'body': safe_text[:3900]}}
    try:
        return _whatsapp_http_session().post(url, json=payload, headers=h, timeout=(3, WHATSAPP_TIMEOUT_SECONDS)).ok
    except Exception:
        return False

def send_whatsapp_cta(to, body, link, bot_id, title):
    _typing_before_outgoing(to, bot_id)
    url = f'{GRAPH_URL}/{bot_id}/messages'
    h = {'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'}
    safe_body = _remove_ui_autolinks(body)
    safe_title = _remove_ui_autolinks(title)
    payload = {'messaging_product': 'whatsapp', 'to': to, 'type': 'interactive', 'interactive': {'type': 'cta_url', 'body': {'text': safe_body[:1024]}, 'action': {'name': 'cta_url', 'parameters': {'display_text': safe_title[:20], 'url': link}}}}
    try:
        return _whatsapp_http_session().post(url, json=payload, headers=h, timeout=(3, WHATSAPP_TIMEOUT_SECONDS)).ok
    except Exception:
        return False

def send_whatsapp_buttons(to, body, buttons, bot_id):
    _typing_before_outgoing(to, bot_id)
    url = f'{GRAPH_URL}/{bot_id}/messages'
    h = {'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'}
    btns = [{'type': 'reply', 'reply': {'id': b['id'], 'title': _remove_ui_autolinks(b['title'])[:20]}} for b in buttons[:3]]
    payload = {'messaging_product': 'whatsapp', 'to': to, 'type': 'interactive', 'interactive': {'type': 'button', 'body': {'text': _remove_ui_autolinks(body)[:1024]}, 'action': {'buttons': btns}}}
    try:
        return _whatsapp_http_session().post(url, json=payload, headers=h, timeout=(3, WHATSAPP_TIMEOUT_SECONDS)).ok
    except Exception:
        return False

def send_language_choice(to, bot_id):
    body = '🌐 Choose your language\n\nTip: you can also just type in any language and Findzia will automatically reply in that language.'
    rows = [{'id': btn_id, 'title': title} for btn_id, (_code, title) in LANGUAGE_SELECTION.items()]
    return send_whatsapp_list(to, body, rows, bot_id, 'Languages')

def route_pending_after_location(phone):
    pending = PENDING_ONBOARDING.pop(phone, None)
    if not pending:
        return
    msg = pending.get('message') or {}
    bot_id = pending.get('bot_id') or PHONE_NUMBER_ID
    typ = msg.get('type')
    if typ == 'image':
        IMAGE_BUFFER[phone]['images'].append(msg)
        IMAGE_BUFFER[phone]['time'] = time.time()
        IMAGE_BUFFER[phone]['bot_id'] = bot_id
        asyncio.run(process_image_buffer(phone))
    elif typ == 'text':
        process_text_message(msg, bot_id, onboarding_checked=True)

@app.get('/lens-image/{token}')
async def lens_image(token: str):
    _cleanup_lens_images()
    with LENS_IMAGE_LOCK:
        item = LENS_IMAGE_STORE.get(token)
    if not item:
        return Response('not found', status_code=404)
    return Response(content=item['content'], media_type=item.get('mime', 'image/jpeg'), headers={'Cache-Control': 'no-store'})

@app.get('/webhook')
async def verify(request: Request):
    p = request.query_params
    if p.get('hub.mode') == 'subscribe' and p.get('hub.verify_token') == VERIFY_TOKEN:
        return Response(content=p.get('hub.challenge'), media_type='text/plain')
    return Response('fail', 403)

@app.post('/webhook')
async def receive(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    try:
        value = data['entry'][0]['changes'][0]['value']
        if 'messages' not in value:
            return {'status': 'ok'}
        msg = value['messages'][0]
        mid = msg.get('id')
        if mid:
            with PROCESSED_IDS_LOCK:
                if mid in processed_ids:
                    return {'status': 'dup'}
                processed_ids.append(mid)
        bot_id = value.get('metadata', {}).get('phone_number_id', PHONE_NUMBER_ID)
        from_number = msg['from']
        _remember_incoming_message_id(from_number, mid)
        start_live_typing(from_number, bot_id, mid)
        load_user_preferences(from_number)
        ensure_market_from_phone(from_number, persist=True)
        typ = msg.get('type')
        if typ == 'interactive':
            background_tasks.add_task(process_interactive_message, msg, bot_id)
            return {'status': 'ok'}
        if typ == 'location':
            background_tasks.add_task(process_location_message, msg, bot_id)
            return {'status': 'ok'}
        if typ == 'text':
            background_tasks.add_task(process_text_message, msg, bot_id, True)
            return {'status': 'ok'}
        if from_number not in USER_LANG:
            cache_pending_message(from_number, msg, bot_id)
            background_tasks.add_task(asyncio.to_thread, send_language_choice, from_number, bot_id)
            return {'status': 'ok'}
        if typ == 'image':
            IMAGE_BUFFER[from_number]['images'].append(msg)
            IMAGE_BUFFER[from_number]['time'] = time.time()
            IMAGE_BUFFER[from_number]['bot_id'] = bot_id
            if len(IMAGE_BUFFER[from_number]['images']) == 1:
                background_tasks.add_task(process_image_buffer, from_number)
    except Exception as e:
        print(f'webhook err {e}')
    return {'status': 'ok'}

def _store_pending_global(phone, bot_id, lang, query, lens_context, prompt_text=None):
    PENDING_GLOBAL_SEARCH[phone] = {'bot_id': bot_id, 'lang': lang, 'query': query, 'lens_context': lens_context or {}, 'prompt_text': prompt_text, 'ts': time.time()}

def _pop_pending_global(phone):
    item = PENDING_GLOBAL_SEARCH.pop(phone, None)
    if not item:
        return None
    if time.time() - item.get('ts', 0) > GLOBAL_PENDING_TTL:
        return None
    return item

def send_not_found_choice(phone, bot_id, lang):
    send_whatsapp_buttons(phone, T(lang, 'ask_not_found'), [{'id': 'nf_global', 'title': T(lang, 'opt_global')[:20]}, {'id': 'nf_similar', 'title': T(lang, 'opt_similar')[:20]}, {'id': 'nf_no', 'title': T(lang, 'opt_no')[:20]}], bot_id)

def run_similar_search(phone, item):
    activate_market(phone)
    bot_id = item['bot_id']
    lang = item['lang']
    query = item['query']
    send_whatsapp_text(phone, T(lang, 'similar_searching'), bot_id)
    base = short_query(re.sub('^.*?—\\s*', '', query).strip() or query) or short_query(query)
    base_en = english_search_name(base)
    market_name = current_market().get('country_name', 'Kuwait')
    prompts = [f'المنتج التالي غير متوفر محلياً: {base}' + (f' ({base_en})' if base_en and base_en != base else '') + f'. اقترح حتى {MAX_STORES} بدائل مشابهة له فعلياً — نفس الفئة ونفس الاستخدام ومستوى جودة قريب — متوفرة الآن في متاجر {market_name} فقط، من أي متجر محلي كان. لكل بديل: اسم البديل الفعلي (وليس اسم المنتج الأصلي)، سعر رقمي واضح بعملة السوق، ورابط صفحة المنتج المباشرة داخل المتجر. رتب من الأرخص إلى الأغلى واكتب السعر بالفلوس كاملة مثل 1.950. {lang_instr(lang)}', f"{MAX_STORES} best in-stock alternatives similar to {base_en or base} in {market_name} local online stores, each with the alternative's own name, a numeric price, and a direct product page link, sorted cheapest first. {lang_instr(lang)}"]
    for prompt in prompts:
        txt, urls = call_gemini([{'text': prompt}])
        urls = direct_urls_only(urls)
        offers = extract_store_offers(txt)
        if not txt or not offers or (not urls):
            continue
        verified = verify_offers(urls, base)
        verified = filter_local_market_only(verified)
        if verified:
            sorted_v = sorted(verified.items(), key=lambda x: x[1]['price'])
            title = product_title(txt, U(lang, 'similar_to', base=base))
            lines = [title, '']
            new_urls = {}
            for i, (name, info) in enumerate(sorted_v[:MAX_STORES]):
                prefix = '✅' if i == 0 else '•'
                alt_title = (info.get('title') or '').strip()
                label = f'{name}: {alt_title[:45]}' if alt_title else name
                lines.append(f"{prefix} {label} — {format_price(info['price'])} {currency_label(lang)}")
                new_urls[name] = info['url']
            send_product_result(phone, '\n'.join(lines), new_urls, bot_id, lang, base)
            return
        kept = []
        for offer in offers:
            matched = match_url(offer['name'], urls)
            if not (matched and is_direct_store_url(matched)):
                continue
            if is_foreign_lens_result({'link': matched, 'source': offer['name'], 'title': offer['line']}):
                print(f"SIMILAR LOCAL REJECT FOREIGN: {offer['name']} -> {matched}")
                continue
            kept.append((offer, matched))
        kept.sort(key=lambda om: _extract_numeric_price(om[0].get('line', '')) or 10 ** 9)
        if kept:
            title = product_title(txt, U(lang, 'similar_to', base=base))
            lines = [title, '']
            new_urls = {}
            for i, (offer, matched) in enumerate(kept[:MAX_STORES]):
                prefix = '✅' if i == 0 else '•'
                body = re.sub('^(?:✅|🏆|•)\\s*', '', offer['line']).strip()
                lines.append(f'{prefix} {body}')
                new_urls[offer['name']] = matched
            send_product_result(phone, '\n'.join(lines), new_urls, bot_id, lang, base)
            return
    send_whatsapp_text(phone, T(lang, 'similar_none'), bot_id)

def run_global_search(phone, item):
    activate_market(phone)
    bot_id = item['bot_id']
    lang = item['lang']
    query = item['query']
    send_whatsapp_text(phone, T(lang, 'global_searching'), bot_id)
    txt, urls = search_product(query, lang, prompt_text=item.get('prompt_text'), lens_context=item.get('lens_context'), allow_global=True)
    if txt and urls:
        filtered_urls = {}
        for name, url in urls.items():
            local = is_local_lens_result({'link': url, 'source': name, 'title': name})
            if local:
                print(f'GLOBAL FINAL GUARD REJECT LOCAL: {name} -> {url}')
            else:
                filtered_urls[name] = url
        if len(filtered_urls) != len(urls):
            kept_names = {normalize_name(n) for n in filtered_urls}
            kept_lines = []
            for line in (txt or '').splitlines():
                offer_match = re.match('^(?:✅|🏆|•)\\s*(.+?)\\s*(?:—|–|-)\\s*', line.strip())
                if offer_match and normalize_name(offer_match.group(1)) not in kept_names:
                    continue
                kept_lines.append(line)
            txt = '\n'.join(kept_lines).strip()
            urls = filtered_urls
    if not txt or not extract_store_offers(txt) or (not urls):
        send_whatsapp_text(phone, T(lang, 'global_none'), bot_id)
        return
    send_product_result(phone, txt, urls, bot_id, lang, query)

def _more_result_domain(url):
    try:
        host = urllib.parse.urlparse(str(url or '')).netloc.lower().split(':')[0]
        return host[4:] if host.startswith('www.') else host
    except Exception:
        return ''

def _send_more_results_choice(phone, bot_id, lang='ar'):
    body = U(lang, 'more_store_q')
    title = U(lang, 'search_more')
    return send_whatsapp_buttons(phone, body, [{'id': 'more_results', 'title': title}], bot_id)

def _save_more_results_state(phone, query, bot_id, lang, origin, shown_items, image_b64='', image_mime='', visual_identity='', reset=False):
    prev = {} if reset else PENDING_MORE_RESULTS.get(phone) or {}
    seen_domains = set(prev.get('seen_domains') or [])
    seen_urls = set(prev.get('seen_urls') or [])
    for item in shown_items or []:
        url = str((item or {}).get('link') or '').strip()
        if url:
            seen_urls.add(_canonical_result_url(url))
            dom = _more_result_domain(url)
            if dom:
                seen_domains.add(dom)
    PENDING_MORE_RESULTS[phone] = {'query': re.sub('\\s+', ' ', str(query or '')).strip(), 'bot_id': bot_id, 'lang': lang, 'origin': origin, 'image_b64': image_b64 if origin == 'lens' else '', 'image_mime': image_mime if origin == 'lens' else '', 'visual_identity': visual_identity if origin == 'lens' else '', 'seen_domains': sorted(seen_domains), 'seen_urls': sorted(seen_urls), 'ts': time.time()}

def _more_exclusion_instruction(seen_domains):
    domains = [d for d in sorted(set(seen_domains or [])) if d][:18]
    return ' استبعد هذه المواقع لأنها ظهرت سابقاً: ' + ', '.join(domains) + '.' if domains else ''

def legacy_text_product_search_more(product, lang, seen_domains):
    market_name = current_market().get('country_name', 'Kuwait')
    total_cap = MORE_TOTAL_MAX
    exclusion = _more_exclusion_instruction(seen_domains)
    alt = english_search_name(product) if re.search('[\\u0600-\\u06FF]', str(product or '')) else arabic_search_name(product)
    alt = (alt or '').strip()
    extra_name = f' والاسم الآخر لنفس المنتج هو {alt}.' if alt and alt.lower() != str(product).strip().lower() else ''
    prompt = f'ابحث مرة أخرى بعمق عن نفس المنتج بالضبط: {product}.{extra_name} المستخدم شاهد نتائج سابقة ويريد متاجر إضافية جديدة فقط.{exclusion} نفس ترتيب البحث الأصلي لكن بحدود الدفعة الإضافية: أولاً متاجر {market_name} المحلية حتى {MORE_LOCAL_MAX}، ثم الولايات المتحدة حتى {MORE_US_MAX}، ثم الصين حتى {MORE_CN_MAX}. لا تعرض دولة رابعة. لا تكرر أي متجر أو دومين ظهر سابقاً. كل نتيجة يجب أن تكون نفس المنتج والموديل/الحجم، بسعر رقمي ورابط صفحة منتج مباشر. {TEXT77_lang_instr(lang)}'
    return legacy_v26_best_of_search([{'text': prompt}], total_cap, True, product)

def run_more_results_search(phone, item):
    activate_market(phone)
    bot_id = item.get('bot_id') or PHONE_NUMBER_ID
    lang = item.get('lang') or USER_LANG.get(phone, 'ar')
    query = (item.get('query') or '').strip()
    seen_domains = set(item.get('seen_domains') or [])
    seen_urls = set(item.get('seen_urls') or [])
    if not query:
        return False
    send_whatsapp_text(phone, U(lang, 'looking_more'), bot_id)
    if item.get('origin') == 'lens' and item.get('image_b64') and item.get('image_mime'):
        exclude_q = ' '.join((f'-site:{d}' for d in list(seen_domains)[:5]))
        q_hint = re.sub('\\s+', ' ', f'{query} buy shop other retailers {exclude_q}').strip()[:120]
        lens = google_lens_lookup(item['image_b64'], item['image_mime'], lang, q_hint, light=True)
        if lens.get('matches') and send_lens_direct_results(phone, lens, bot_id, lang, caption=query, image_b64=item.get('image_b64') or '', image_mime=item.get('image_mime') or '', exclude_domains=seen_domains, exclude_urls=seen_urls, more_mode=True):
            return True
    else:
        txt, urls = legacy_text_product_search_more(query, lang, seen_domains)
        if txt and urls and send_text_lens_style_results(phone, txt, urls, bot_id, lang, query, exclude_domains=seen_domains, exclude_urls=seen_urls, more_mode=True):
            return True
    PENDING_MORE_RESULTS.pop(phone, None)
    send_whatsapp_text(phone, U(lang, 'all_results'), bot_id)
    return False

def process_interactive_message(message, bot_id):
    from_number = message['from']
    inter = message.get('interactive') or {}
    reply = inter.get('button_reply') or inter.get('list_reply') or {}
    btn_id = reply.get('id', '')
    if btn_id == 'more_results':
        item = PENDING_MORE_RESULTS.get(from_number) or {}
        lang_ = item.get('lang') or USER_LANG.get(from_number, 'ar')
        if item and time.time() - float(item.get('ts') or 0) <= GLOBAL_PENDING_TTL:
            item['ts'] = time.time()
            PENDING_MORE_RESULTS[from_number] = item
            run_more_results_search(from_number, item)
        else:
            PENDING_MORE_RESULTS.pop(from_number, None)
            send_whatsapp_text(from_number, U(lang_, 'expired'), bot_id)
        return
    if btn_id == 'region_gcc' or btn_id.startswith('gcc_') or btn_id in ('region_uk', 'region_eu'):
        return
    if btn_id.startswith('cart_'):
        item = PENDING_CART_PICKS.get(from_number)
        if item and time.time() - item.get('ts', 0) > GLOBAL_PENDING_TTL:
            item = None
        lang_ = (item or {}).get('lang', USER_LANG.get(from_number, 'ar'))
        idx = int(btn_id[5:]) if btn_id[5:].isdigit() else -1
        if item and 0 <= idx < len(item.get('stores') or []):
            activate_market(from_number)
            send_cart_from_store(from_number, idx, item['stores'], item.get('products') or [], item.get('bot_id') or bot_id, lang_)
        else:
            send_whatsapp_text(from_number, T(lang_, 'cart_expired'), bot_id)
        return
    if btn_id.startswith('pickq_') or btn_id.startswith('pick_'):
        item = PENDING_BRAND_PICKS.get(from_number) or {}
        lang_ = item.get('lang') or USER_LANG.get(from_number, 'ar')
        picked = ''
        if btn_id.startswith('pickq_'):
            token = btn_id[6:]
            try:
                pad = '=' * ((4 - len(token) % 4) % 4)
                picked = base64.urlsafe_b64decode((token + pad).encode('ascii')).decode('utf-8', 'ignore')
            except Exception as e:
                print(f'PICK TOKEN DECODE ERR: {e}')
                picked = ''
        else:
            raw_idx = btn_id[5:]
            pick_idx = int(raw_idx) if raw_idx.isdigit() else -1
            options = item.get('options') or []
            if 0 <= pick_idx < len(options):
                picked = options[pick_idx]
        if not picked:
            desc = str(reply.get('description') or '')
            desc_product = re.split('\\s+(?:—|–|-)\\s+', desc, maxsplit=1)[0].strip()
            title = str(reply.get('title') or '')
            title_is_label = bool(re.match('^\\s*(?:🏆|💎|💰|✨|⭐)', title))
            picked = (desc_product if title_is_label or not title else title) or desc_product or title
        picked = _clean_pick_label(picked)
        if not picked:
            send_whatsapp_text(from_number, U(lang_, 'expired'), bot_id)
            return
        if item and time.time() - float(item.get('ts') or 0) <= BRAND_PICK_TTL:
            original = item.get('original_query') or ''
            target_bot_id = item.get('bot_id') or bot_id
        else:
            original = ''
            target_bot_id = bot_id
        activate_market(from_number)
        search_query = ai_recommendation_pick_search_query(original, picked, lang_)
        LAST_SEARCH[from_number] = {'product': search_query}
        PENDING_BRAND_PICKS.pop(from_number, None)
        execute_product_search(from_number, search_query, target_bot_id, lang_)
        return
    if btn_id in ('global_yes', 'nf_global'):
        item = _pop_pending_global(from_number)
        if item:
            if item.get('origin') == 'text77':
                run_text_global_search(from_number, item)
            else:
                run_global_search(from_number, item)
        return
    if btn_id == 'nf_similar':
        item = _pop_pending_global(from_number)
        if item:
            if item.get('origin') == 'text77':
                run_text_similar_search(from_number, item)
            else:
                run_similar_search(from_number, item)
        return
    if btn_id in ('global_no', 'nf_no'):
        PENDING_GLOBAL_SEARCH.pop(from_number, None)
        send_whatsapp_text(from_number, T(USER_LANG.get(from_number, 'ar'), 'declined_ok'), bot_id)
        return
    if btn_id not in LANGUAGE_SELECTION:
        return
    lang = LANGUAGE_SELECTION[btn_id][0]
    USER_LANG[from_number] = lang
    market = ensure_market_from_phone(from_number, persist=False)
    save_user_preferences(from_number)
    send_whatsapp_text(from_number, T(lang, 'lang_saved'), bot_id)
    print(f"LANGUAGE SAVED: {from_number} -> {lang}; MARKET FROM PHONE -> {market.get('country')}")
    route_pending_after_location(from_number)

async def process_image_buffer(from_number):
    started = time.monotonic()
    while True:
        data = IMAGE_BUFFER.get(from_number)
        if not data:
            return
        idle = max(0.0, time.time() - float(data.get('time') or 0))
        elapsed = time.monotonic() - started
        if idle >= IMAGE_BUFFER_IDLE_SECONDS or elapsed >= IMAGE_BUFFER_MAX_WAIT_SECONDS:
            break
        await asyncio.sleep(min(0.25, max(0.05, IMAGE_BUFFER_IDLE_SECONDS - idle)))
    data = IMAGE_BUFFER.pop(from_number, None)
    if not data:
        return
    lang = USER_LANG.get(from_number, 'ar')
    if len(data['images']) == 1:
        await asyncio.to_thread(process_single_image, data['images'][0], data['bot_id'], lang)
    else:
        await asyncio.to_thread(process_multi_images, data['images'], from_number, data['bot_id'], lang)

def identify_product_with_retry(b64, mime, lang='ar'):
    prompts = ['حدد المنتج من الشعار والشكل والنص. اكتب الاسم العربي ثم الإنجليزي مفصولين بـ |.', 'افحص الصورة بدقة أكبر، خصوصاً الشعار والأزرار ورقم الموديل. اكتب Arabic name | English name.', 'استنتج أقرب اسم تجاري قابل للبحث حتى لو الصورة جزئية. Arabic | English only.']
    bad_phrases = ('ما قدرت', 'لا استطيع', 'لا أستطيع', 'غير واضح', 'لا يمكن تحديد', "couldn't identify", 'cannot identify', "can't identify", 'unable to identify', 'unknown product', 'not sure')
    for attempt in range(MAX_IDENTIFY_ATTEMPTS):
        ident, _ = call_gemini([{'inline_data': {'mime_type': mime, 'data': b64}}, {'text': prompts[min(attempt, len(prompts) - 1)]}], system=IDENTIFY_SYSTEM, use_search=False)
        candidate = ident.strip().splitlines()[0].strip() if ident else ''
        if candidate and (not any((p in candidate.lower() for p in bad_phrases))):
            if '|' not in candidate:
                candidate = candidate.strip()
            print(f'IMAGE IDENTIFIED attempt={attempt + 1}: {candidate}')
            return candidate
        print(f'IMAGE IDENTIFY ATTEMPT {attempt + 1} FAILED')
    return ''

def _identity_tokens(text):
    t = normalize_ar(text or '')
    return {x for x in re.findall('[a-z0-9\\u0600-\\u06ff]+', t) if len(x) > 2}

def identity_candidates_agree(vision_name, lens_title):
    if _findzia_hard_product_mismatch(vision_name, lens_title):
        return False
    a, b = (_identity_tokens(vision_name), _identity_tokens(lens_title))
    if not a or not b:
        return False
    ma, mb = (_findzia_model_tokens(vision_name), _findzia_model_tokens(lens_title))
    if ma or mb:
        return bool(ma & mb)
    inter = {x for x in a & b if not x.isdigit()}
    return len(inter) >= 2 and len(inter) / max(1, min(len(a), len(b))) >= 0.45

def is_fashion_identity(vision_name, caption=''):
    q = normalize_ar(f"{vision_name or ''} {caption or ''}")
    fashion_terms = ('ملابس', 'قميص', 'قميص نسائي', 'بلوزه', 'بلوزة', 'توب', 'فستان', 'بنطلون', 'تنوره', 'تنورة', 'جاكيت', 'معطف', 'عبايه', 'عباية', 'بيجامه', 'بيجامة', 'بجامه', 'بجامة', 'ملابس نوم', 'روب', 'طقم نسائي', 'ساتان', 'مخطط', 'مخططه', 'مخططة', 'مطبوع', 'موضة', 'ازياء', 'أزياء', 'حذاء', 'شبشب', 'صندل', 'نعال', 'سنيكر', 'شنطه', 'شنطة', 'حقيبه', 'حقيبة', 'shirt', "women's shirt", 'womens shirt', 'blouse', 'top', 'dress', 'skirt', 'pants', 'trousers', 'jacket', 'coat', 'abaya', 'pajama', 'pajamas', 'pyjama', 'pyjamas', 'nightwear', 'sleepwear', 'robe', 'satin', 'printed', 'striped', 'fashion', 'apparel', 'clothing', 'shoe', 'mule', 'slipper', 'sandal', 'sneaker', 'bag', 'handbag', 'co-ord', 'coord')
    return any((term in q for term in fashion_terms))

def is_generic_commodity(vision_name, caption=''):
    raw = f"{vision_name or ''} {caption or ''}".strip()
    if not raw:
        return False
    if re.search('\\b(?=[a-z0-9-]{3,}\\b)(?=[a-z0-9-]*[a-z])(?=[a-z0-9-]*\\d)[a-z0-9-]+\\b', raw, re.I):
        return False
    q = normalize_ar(raw)
    known_brands = ('نايك', 'nike', 'اديداس', 'adidas', 'سبولدينج', 'spalding', 'ويلسون', 'wilson', 'مولتن', 'molten', 'ميكاسا', 'mikasa', 'بوما', 'puma', 'ريبوك', 'reebok', 'اندر ارمور', 'under armour', 'اسيكس', 'asics', 'ابل', 'apple', 'سامسونج', 'samsung', 'سوني', 'sony')
    if any((normalize_ar(b) in q for b in known_brands)):
        return False
    generic_terms = ('كره سله', 'basketball', 'كره قدم', 'football', 'soccer ball', 'كره طايره', 'volleyball', 'كره تنس', 'tennis ball', 'كره يد', 'handball', 'حبل قفز', 'jump rope', 'دمبل', 'dumbbell', 'سجاده يوغا', 'yoga mat', 'مطاره ماء', 'water bottle', 'قاروره ماء', 'شنطه رياضيه', 'gym bag')
    return any((normalize_ar(t) in q for t in generic_terms))

def _legacy_should_use_google_lens(vision_name, caption=''):
    raw = f"{vision_name or ''} {caption or ''}".strip()
    q = normalize_ar(raw)
    if not vision_name:
        return True
    if is_fashion_identity(vision_name, caption):
        return True
    uncertain = ('غير معروف', 'منتج غير', 'unknown', 'unidentified', 'possibly', 'ربما', 'قد يكون', 'عام', 'generic', 'لا استطيع', 'لا أستطيع')
    if any((x in q for x in uncertain)) or len(_identity_tokens(vision_name)) < 2:
        return True
    has_model = bool(re.search('\\b(?=[a-z0-9-]{4,}\\b)(?=[a-z0-9-]*[a-z])(?=[a-z0-9-]*\\d)[a-z0-9-]+\\b', raw, re.I))
    packaged = ('كرتون', 'علبه', 'عبوه', 'جرام', 'كيلو', 'مل', 'لتر', 'حليب', 'عصير', 'شيبس', 'بسكوت', 'كيك', 'قهوه', 'شاي', 'دواء', 'كريم', 'شامبو', 'حبوب', 'مكمل', 'صلصه', 'بهارات', 'زعفران', 'هيل', 'منظف', 'bottle', 'pack', 'box', 'gram', 'kg', 'ml', 'liter', 'medicine', 'shampoo', 'cream', 'snack', 'cake', 'coffee', 'tea', 'spice')
    if has_model or any((x in q for x in packaged)):
        return False
    visual_categories = ('حذاء', 'شبشب', 'صندل', 'نعال', 'ملابس', 'قميص', 'بنطلون', 'فستان', 'جاكيت', 'قبعه', 'شنطه', 'حقيبه', 'نظاره', 'ساعه', 'خاتم', 'قلاده', 'اثاث', 'كرسي', 'طاوله', 'ديكور', 'لعبه', 'سياره', 'قطعه غيار', 'shoe', 'mule', 'slipper', 'sandal', 'sneaker', 'dress', 'shirt', 'jacket', 'cap', 'hat', 'bag', 'handbag', 'glasses', 'sunglasses', 'watch', 'ring', 'necklace', 'furniture', 'chair', 'table', 'decor', 'بيجامه', 'بيجامة', 'بجامه', 'بجامة', 'ملابس نوم', 'روب', 'بلوزه', 'بلوزة', 'توب', 'طقم نسائي', 'قميص نسائي', 'ساتان', 'مخطط', 'مخططه', 'مخططة', 'pajama', 'pajamas', 'pyjama', 'pyjamas', 'nightwear', 'sleepwear', 'blouse', 'top', 'co-ord', 'coord', 'satin', 'printed', 'striped')
    return any((x in q for x in visual_categories))

def _is_text_heavy_packaged_product(vision_name, caption=''):
    raw = f"{vision_name or ''} {caption or ''}".strip()
    q = normalize_ar(raw)
    if not q:
        return False
    package_terms = ('كرتون', 'علبه', 'علبة', 'عبوه', 'عبوة', 'جرام', 'غرام', 'كيلو', 'جم', 'mg', 'مل', 'لتر', 'حليب', 'عصير', 'شيبس', 'بسكوت', 'كيك', 'قهوه', 'قهوة', 'شاي', 'دواء', 'كريم', 'شامبو', 'حبوب', 'مكمل', 'صلصه', 'صلصة', 'بهارات', 'زعفران', 'هيل', 'منظف', 'صابون', 'bottle', 'pack', 'box', 'gram', 'kg', 'g ', ' g', 'ml', 'liter', 'medicine', 'tablet', 'capsule', 'shampoo', 'cream', 'snack', 'cake', 'coffee', 'tea', 'spice', 'detergent', 'soap')
    text_strength = sum((1 for x in package_terms if x in q))
    has_model = bool(re.search('\\b(?=[a-z0-9-]{4,}\\b)(?=[a-z0-9-]*[a-z])(?=[a-z0-9-]*\\d)[a-z0-9-]+\\b', raw, re.I))
    has_numbers = bool(re.search('\\d', raw))
    token_count = len(_identity_tokens(vision_name))
    return has_model or (text_strength >= 1 and (has_numbers or token_count >= 3))

def lens_routing_decision(vision_name, caption=''):
    raw = f"{vision_name or ''} {caption or ''}".strip()
    q = normalize_ar(raw)
    if not ENABLE_GOOGLE_LENS:
        return (False, 'LENS_DISABLED')
    if not vision_name:
        return (True, 'NO_VISION_IDENTITY')
    if is_fashion_identity(vision_name, caption):
        return (True, 'FASHION_ALWAYS_LENS')
    if is_generic_commodity(vision_name, caption):
        return (False, 'GENERIC_COMMODITY_VISION_FIRST')
    uncertain = ('غير معروف', 'منتج غير', 'unknown', 'unidentified', 'possibly', 'ربما', 'قد يكون', 'عام', 'generic', 'لا استطيع', 'لا أستطيع')
    if any((x in q for x in uncertain)) or len(_identity_tokens(vision_name)) < 2:
        return (True, 'UNCERTAIN_IDENTITY')
    if LENS_PRIMARY_MODE:
        if LENS_PRIMARY_EXCEPT_TEXT_HEAVY and _is_text_heavy_packaged_product(vision_name, caption):
            return (False, 'TEXT_HEAVY_PACKAGE_VISION_FIRST')
        return (True, 'LENS_PRIMARY_DEFAULT')
    return (_legacy_should_use_google_lens(vision_name, caption), 'LEGACY_ROUTER')

def choose_image_identity(image_b64, mime_type, lens, vision_name):
    lens_title = ((lens.get('chosen') or {}).get('title') or lens.get('query') or '').strip()
    vision_name = (vision_name or '').strip()
    if not lens_title:
        return (vision_name, None, 'VISION_ONLY')
    if not vision_name:
        return (lens_title, lens, 'LENS_ONLY')
    judge_system = 'أنت حكم دقيق لهوية المنتجات. الصورة هي المرجع النهائي.\nقارن بين اقتراح Google Lens واقتراح قارئ النص/الملصق.\nقواعد إلزامية:\n1) إذا كانت الصورة لعبوة أو منتج عليه ملصق واضح، فاسم البراند والنص المطبوع ونوع المنتج والوزن أقوى من التشابه الشكلي.\n2) لا تعتبر منتجين متطابقين لمجرد اشتراكهما في مكون مثل الزعفران أو اللون أو الفئة.\n3) إذا قال اقتراح إن المنتج كيك/حلويات والآخر زعفران خام أو بهارات فهما مختلفان قطعاً.\n4) للملابس والأحذية والحقائب غير المعلّمة بوضوح، أعط Lens وزناً أكبر.\n5) اختر MERGE فقط إذا كان الاقتراحان لنفس المنتج فعلاً ولا يوجد تعارض.\nأرجع JSON فقط بهذا الشكل:\n{"winner":"VISION"|"LENS"|"MERGE","confidence":0-100,"final_name":"اسم بحث دقيق بالعربي | English","reason":"سبب قصير"}\n'
    prompt = f'Google Lens candidate: {lens_title}\nDirect vision/OCR candidate: {vision_name}\nاحكم بالاعتماد على الصورة نفسها، وليس على ترتيب Lens.'
    raw, _ = call_gemini([{'inline_data': {'mime_type': mime_type, 'data': image_b64}}, {'text': prompt}], system=judge_system, use_search=False)
    try:
        data = json.loads(re.search('\\{.*\\}', raw or '', flags=re.S).group(0))
    except Exception:
        print(f'IDENTITY JUDGE PARSE FAIL: {raw}')
        return (vision_name, None, 'VISION_SAFE_FALLBACK')
    winner = str(data.get('winner', 'VISION')).upper()
    confidence = int(float(data.get('confidence', 0) or 0))
    final_name = str(data.get('final_name') or '').strip()
    reason = str(data.get('reason') or '').strip()
    print(f'IDENTITY JUDGE: winner={winner} confidence={confidence} reason={reason}')
    if winner == 'LENS' and confidence >= 78:
        return (final_name or lens_title, lens, 'LENS')
    if winner == 'MERGE' and confidence >= 82:
        return (final_name or f'{vision_name} | {lens_title}', lens, 'MERGE')
    return (final_name or vision_name, None, 'VISION')

def country_flag_emoji(cc):
    cc = str(cc or '').strip().upper()
    if len(cc) == 2 and cc.isalpha():
        try:
            return ''.join((chr(127397 + ord(ch)) for ch in cc))
        except Exception:
            pass
    return '🌐'

def _lens_has_price(m):
    if not isinstance(m, dict):
        return False
    raw = str(m.get('price') or '').strip()
    try:
        _pv = _authoritative_price_value(m.get('price_value'), raw, str(m.get('currency') or ''))
        if _pv is not None and _pv > 0 and (not _price_collides_with_measurement(_pv, m.get('title'), m.get('snippet'))):
            return True
    except Exception:
        pass
    if not raw:
        return False
    numeric = _extract_numeric_price(raw)
    if numeric is not None and numeric > 0:
        return True
    if len(raw) <= 24 and re.fullmatch('\\s*[$€£¥￥]?\\s*\\d+(?:[.,]\\d{1,3})?\\s*(?:[A-Z]{3}|د\\.ك|KD|RMB)?\\s*', raw, flags=re.I):
        try:
            mm = re.search(r'\d+(?:[.,]\d{1,3})?', _normalize_price_chars(raw))
            cur = detect_currency_code(raw, str(m.get('currency') or ''))
            val = _normalize_price_token(mm.group(0), cur) if mm else None
            return bool(val is not None and val > 0)
        except Exception:
            return False
    return False

def _safe_embedded_price(item):
    if not isinstance(item, dict) or _lens_has_price(item):
        return item
    text_blob = ' '.join((str(item.get(k) or '') for k in ('price', 'title', 'snippet', 'extensions')))
    text_blob = re.sub('\\s+', ' ', text_blob).strip()
    if not text_blob:
        return item
    currency_pat = '(?:KWD|KD|د\\.ك|دينار|USD|US\\$|\\$|SAR|ر\\.س|AED|د\\.إ|QAR|OMR|BHD|CNY|RMB|¥|￥|EUR|€|GBP|£)'
    pat = re.compile(f'(?:(?P<c1>{currency_pat})\\s*(?P<n1>[0-9]+(?:[.,][0-9]{{1,3}})?)|(?P<n2>[0-9]+(?:[.,][0-9]{{1,3}})?)\\s*(?P<c2>{currency_pat}))', re.I)
    bad_before = re.compile('(?:save|saving|discount|coupon|off|خصم|وفر|توفير)\\s*$', re.I)
    bad_after = re.compile('^\\s*(?:/\\s*(?:mo|month|yr|year)|per\\s+(?:month|year)|monthly|installment|قسط|شهري|بالشهر)', re.I)
    candidates = []
    for m in pat.finditer(text_blob):
        before = text_blob[max(0, m.start() - 28):m.start()]
        after = text_blob[m.end():m.end() + 28]
        if bad_before.search(before) or bad_after.search(after):
            continue
        num_token = m.group('n1') or m.group('n2')
        cur_token = m.group('c1') or m.group('c2')
        try:
            val = _normalize_price_token(num_token, detect_currency_code(cur_token, ''))
        except Exception:
            continue
        if val is None or val <= 0:
            continue
        if _price_collides_with_measurement(val, item.get('title'), item.get('snippet')):
            print(f"LENS SIZE-AS-PRICE BLOCK value={val} title={(item.get('title') or '')[:90]}")
            continue
        candidates.append((m.start(), val, cur_token, m.group(0)))
    if not candidates:
        return item
    _, num, cur_token, raw = candidates[0]
    cur = detect_currency_code(cur_token, '')
    out = dict(item)
    rank = result_market_rank(out)
    if not cur:
        cur = (current_market().get('currency') or 'KWD').upper() if rank == 0 else 'USD' if rank == 1 else 'CNY'
    out['price_value'] = num
    out['currency'] = cur
    out['price'] = raw or f'{format_price(num, cur)} {cur}'
    out['price_source'] = 'embedded_lens_text'
    return out

def _price_identity_score(a, b):
    if _findzia_hard_product_mismatch(a, b):
        return 0.0
    ta, tb = (_identity_tokens(a or ''), _identity_tokens(b or ''))
    if not ta or not tb:
        return 0.0
    ma, mb = (_findzia_model_tokens(a), _findzia_model_tokens(b))
    if (ma or mb) and (not ma & mb):
        return 0.0
    inter = len(ta & tb)
    score = inter / max(1, min(len(ta), len(tb)))
    if ma & mb:
        score += 0.5
    na, nb = (_findzia_pure_numbers(a), _findzia_pure_numbers(b))
    if na and nb and na & nb:
        score += 0.1
    return score

def _fill_prices_from_existing_lens_pool(selected, pool):
    out = [dict(x) for x in selected or []]
    pool = [_safe_embedded_price(dict(x)) for x in pool or []]
    for i, item in enumerate(out):
        item = _safe_embedded_price(item)
        if _lens_has_price(item):
            out[i] = item
            continue
        merchant = _lens_merchant_key(item.get('source'), item.get('link'))
        title = str(item.get('title') or '')
        sig = extract_pack_size(title)
        best = None
        best_score = 0.0
        for cand in pool:
            if not _lens_has_price(cand):
                continue
            if _lens_merchant_key(cand.get('source'), cand.get('link')) != merchant:
                continue
            if not sizes_compatible(sig, extract_pack_size(cand.get('title') or '')):
                continue
            score = _price_identity_score(title, cand.get('title') or '')
            if score >= 0.72 and score > best_score:
                best, best_score = (cand, score)
        if best:
            for k in ('price', 'price_value', 'currency'):
                if best.get(k) not in (None, ''):
                    item[k] = best.get(k)
            item['price_source'] = 'existing_lens_pool'
            print(f"LENS PRICE REUSE: {(item.get('source') or '')[:35]} score={best_score:.2f} -> {item.get('price') or item.get('price_value')}")
        out[i] = item
    return out

def _lens_price_text_local(m, market_rank, lang):
    raw_price = str(m.get('price') or '').strip()
    price_value = m.get('price_value')
    currency = (m.get('currency') or '').upper().strip()
    if not raw_price and price_value in (None, ''):
        return ''
    if market_rank == 0:
        local_cur = (current_market().get('currency') or '').upper().strip()
        src_local = currency or detect_currency_code(raw_price, local_cur)
        if src_local and local_cur and (src_local != local_cur):
            shown, _ = display_global_price(price_value, raw_price, src_local, lang)
            return shown
        return format_lens_price(raw_price, price_value, lang, local_cur or currency or None)
    src = currency or detect_currency_code(raw_price, '')
    if not src:
        src = 'USD' if market_rank == 1 else 'CNY'
    shown, _ = display_global_price(price_value, raw_price, src, lang)
    return shown
UI_TRANSLATE_CACHE = {}
UI_TRANSLATE_LOCK = threading.Lock()

def translate_ui_titles(titles, lang):
    clean = [re.sub('\\s+', ' ', str(t or '')).strip() for t in titles]
    if not clean or lang == 'en':
        return clean
    target = language_name_en(lang)
    result = [None] * len(clean)
    missing_idx, missing = ([], [])
    with UI_TRANSLATE_LOCK:
        for i, t in enumerate(clean):
            key = (lang, t)
            if key in UI_TRANSLATE_CACHE:
                result[i] = UI_TRANSLATE_CACHE[key]
            else:
                missing_idx.append(i)
                missing.append(t)
    if missing:
        system = f'You translate shopping UI text into {target}.\nTranslate ONLY the human-readable product description for display.\nDo not translate, alter, or localize brand names, model names, SKU codes, sizes, numbers, or store names.\nKeep only the product identity and the few attributes needed to distinguish it (brand/model/type/color/size).\nRemove shopping/SEO filler such as buy, shop, online, available in, for men/women, city/country/store wording unless essential to identify the product.\nAim for 3-8 words and at most 65 characters.\nReturn ONLY a JSON array of strings in the same order, no markdown.'
        raw, _ = call_gemini([{'text': json.dumps(missing, ensure_ascii=False)}], system=system, use_search=False)
        translated = []
        try:
            m = re.search('\\[.*\\]', raw or '', flags=re.S)
            parsed = json.loads(m.group(0)) if m else []
            if isinstance(parsed, list):
                translated = [str(x or '').strip() for x in parsed]
        except Exception as e:
            print(f'UI TITLE TRANSLATE PARSE ERR: {e}')
        if len(translated) != len(missing):
            translated = missing
        with UI_TRANSLATE_LOCK:
            if len(UI_TRANSLATE_CACHE) > 5000:
                UI_TRANSLATE_CACHE.clear()
            for idx, original, trans in zip(missing_idx, missing, translated):
                shown = trans or original
                result[idx] = shown
                UI_TRANSLATE_CACHE[lang, original] = shown
    return [r or c for r, c in zip(result, clean)]

def _lens_ai_relevance_filter(lens):
    matches = list((lens or {}).get('matches') or [])
    if not ENABLE_RELEVANCE_FILTER or len(matches) < 3:
        return matches
    sample = matches[:30]
    anchor = str((lens or {}).get('visual_identity') or (lens or {}).get('relevance_target') or ((lens or {}).get('chosen') or {}).get('title') or '').strip()
    deterministic = sample
    if anchor:
        deterministic = [m for m in sample if not _findzia_hard_product_mismatch(anchor, m.get('title') or '') and _findzia_match_score(anchor, m.get('title') or '') >= 0.28]
        if not deterministic:
            deterministic = [m for m in sample if not _findzia_hard_product_mismatch(anchor, m.get('title') or '')]
    rows = [f"{i}. {(m.get('title') or '')[:180]} | store={(m.get('source') or '')[:50]} | exact={bool(m.get('exact'))}" for i, m in enumerate(sample, 1)]
    system = 'You are a strict visual-shopping result validator.\nInfer the ONE physical product type/model from the original-image identity and Lens consensus.\nKeep only direct sales of that same product or clearly compatible variant. Reject accessories, manuals, neighboring models/types and unrelated products.\nNever use price, merchant fame or country as relevance evidence.\nReturn JSON only: {"target":"short identity","keep":[1,2,4]}'
    prompt = f"Visual/original-image identity: {anchor or 'UNKNOWN'}\n\nLens candidates:\n" + '\n'.join(rows)
    try:
        raw, _ = call_gemini([{'text': prompt}], system=system, use_search=False)
        mobj = re.search('\\{.*\\}', raw or '', flags=re.S)
        data = json.loads(mobj.group(0)) if mobj else {}
        keep = {int(x) for x in data.get('keep') or [] if str(x).isdigit()}
        filtered = [m for i, m in enumerate(sample, 1) if i in keep]
        if filtered:
            target = str(data.get('target') or '').strip()
            if target:
                lens['relevance_target'] = target
            return filtered
        print('LENS AI RELEVANCE: empty keep -> deterministic fallback')
    except Exception as e:
        print(f'LENS AI RELEVANCE FAIL: {e}')
    return deterministic

def _lens_merchant_key(name, url=''):
    try:
        host = urllib.parse.urlparse(str(url or '')).netloc.lower().split(':')[0]
        host = host[4:] if host.startswith('www.') else host
    except Exception:
        host = ''
    aliases = ('amazon.com', 'ebay.com', 'walmart.com', 'aliexpress.com', 'temu.com', 'alibaba.com', 'shein.com', '1688.com', 'taobao.com', 'tmall.com', 'made-in-china.com', 'newegg.com', 'bestbuy.com')
    hay = f"{name or ''} {host}".lower()
    for dom in aliases:
        label = dom.split('.')[0]
        if dom in hay or normalize_name(label) in normalize_name(hay):
            return dom
    return host or normalize_name(str(name or ''))

def send_lens_direct_results(from_number, lens, bot_id, lang, caption='', image_b64='', image_mime='', exclude_domains=None, exclude_urls=None, more_mode=False):
    exclude_domains = {str(x).lower() for x in exclude_domains or [] if x}
    exclude_urls = {str(x).strip() for x in exclude_urls or [] if x}
    raw_matches = [m for m in lens.get('matches') or [] if (m.get('title') or '').strip()]
    if exclude_domains or exclude_urls:
        raw_matches = [m for m in raw_matches if str(m.get('link') or '').strip() not in exclude_urls and _more_result_domain(m.get('link')) not in exclude_domains]
    if not USE_FAST_LENS_PIPELINE:
        lens_for_filter = dict(lens or {})
        lens_for_filter['matches'] = raw_matches
        raw_matches = _lens_ai_relevance_filter(lens_for_filter)
        if lens_for_filter.get('relevance_target'):
            lens['relevance_target'] = lens_for_filter['relevance_target']
    matches = [m for m in raw_matches if result_market_rank(m) != 99]
    if not matches:
        return False
    buckets = {0: [], 1: [], 2: []}
    for m in matches:
        rank = result_market_rank(m)
        if rank in buckets:
            buckets[rank].append(m)
    for rank in buckets:
        _anchor = str(lens.get('visual_identity') or lens.get('relevance_target') or (lens.get('chosen') or {}).get('title') or '')
        buckets[rank].sort(key=lambda m: (0 if m.get('exact') else 1, 0 if m.get('section') == 'visual_matches' else 1, -_findzia_match_score(_anchor, m.get('title') or '') if _anchor else 0, 0 if _lens_has_price(m) else 1, int(m.get('position') or 999), _us_store_priority(m.get('source'), m.get('link')) if rank == 1 else _china_store_priority(m.get('source'), m.get('link')) if rank == 2 else 99))
        _active_probe_caps = {0: MORE_LOCAL_MAX, 1: MORE_US_MAX, 2: MORE_CN_MAX} if more_mode else {0: LENS_DIRECT_LOCAL_MAX, 1: LENS_DIRECT_US_MAX, 2: LENS_DIRECT_CN_MAX}
        _cap = _active_probe_caps.get(rank, 0)
        _probe_n = max(_cap + 2, _cap)
        _head = _filter_confirmed_oos(buckets[rank][:_probe_n], f'LENS-{rank}')
        buckets[rank] = _head + buckets[rank][_probe_n:]

    def _merchant_key(m):
        url = (m.get('link') or '').strip()
        source = re.sub('\\s+', ' ', (m.get('source') or '').strip().lower())
        try:
            host = urllib.parse.urlparse(url).netloc.lower().split(':')[0]
            host = host[4:] if host.startswith('www.') else host
        except Exception:
            host = ''
        known = ('shein.com', 'aliexpress.com', 'temu.com', 'alibaba.com', '1688.com', 'taobao.com', 'tmall.com', 'amazon.com', 'ubuy.com', 'westelm.com', 'hm.com', 'wayfair.com')
        for d in known:
            if host == d or host.endswith('.' + d) or d in source:
                return d
        if host:
            return host
        return re.sub('[^a-z0-9]+', '', source) or source
    market_caps = {0: MORE_LOCAL_MAX, 1: MORE_US_MAX, 2: MORE_CN_MAX} if more_mode else {0: LENS_DIRECT_LOCAL_MAX, 1: LENS_DIRECT_US_MAX, 2: LENS_DIRECT_CN_MAX}
    selected = []
    seen_urls = set()
    merchant_counts = defaultdict(int)
    for rank in (0, 1, 2):
        taken = 0
        cap = market_caps.get(rank, 0)
        if cap <= 0:
            continue
        for m in buckets[rank]:
            url = (m.get('link') or '').strip()
            try:
                host = urllib.parse.urlparse(url).netloc.lower()
            except Exception:
                host = ''
            if not (url.startswith('http') and host and ('google.' not in host)):
                continue
            merchant = _merchant_key(m)
            if _canonical_result_url(url) in seen_urls:
                print(f"LENS DUP URL SKIP: merchant={merchant} title={(m.get('title') or '')[:70]}")
                continue
            if merchant_counts[merchant] >= RESULTS_PER_STORE_MAX:
                print(f'LENS STORE CAP SKIP: merchant={merchant} cap={RESULTS_PER_STORE_MAX}')
                continue
            selected.append(m)
            seen_urls.add(_canonical_result_url(url))
            merchant_counts[merchant] += 1
            taken += 1
            if taken >= cap or len(selected) >= LENS_DIRECT_MAX_CTA:
                break
        if len(selected) >= LENS_DIRECT_MAX_CTA:
            break
    if not selected:
        return False
    selected = _fill_prices_from_existing_lens_pool(selected, raw_matches)
    missing_prices = sum((1 for m in selected if not _lens_has_price(m)))
    if missing_prices:
        print(f'LENS PRICE-SMART: preserved {missing_prices} card(s) with no safely extracted numeric price')
    display_titles = ([(m.get('title') or '').strip() for m in selected] if USE_FAST_LENS_PIPELINE else translate_ui_titles([(m.get('title') or '').strip() for m in selected], lang))
    for m, display_title in zip(selected, display_titles):
        m['_display_title'] = display_title
    local_cc = (current_market().get('country') or DEFAULT_COUNTRY).lower()
    market_cc = {0: local_cc, 1: 'us', 2: 'cn'}
    sent = 0
    market_counts = {0: 0, 1: 0, 2: 0}
    for m in selected:
        market_rank = result_market_rank(m)
        flag = country_flag_emoji(market_cc.get(market_rank, ''))
        source = _ui_plain_store_name((m.get('source') or '').strip(), (m.get('link') or '').strip())
        title = _compact_ui_title(m.get('_display_title') or m.get('title') or '')
        price_txt = _lens_price_text_local(m, market_rank, lang)
        body = _build_compact_card_body(flag, source, title, price_txt, lang)
        if not body:
            continue
        url = (m.get('link') or '').strip()
        button_source = source or U(lang, 'store')
        send_whatsapp_cta(from_number, body[:1000], url, bot_id, button_source)
        market_counts[market_rank] += 1
        sent += 1
    chosen_title = ((lens.get('chosen') or {}).get('title') or selected[0]['title']).strip()
    expansion_query = (lens.get('relevance_target') or '').strip() or chosen_title or (caption or '').strip()
    LAST_SEARCH[from_number] = {'product': caption or expansion_query or chosen_title}
    print(f'LENS DIRECT SENT v79: {sent} CTA; merchants={len(merchant_counts)}; per_store_cap={RESULTS_PER_STORE_MAX}; buckets={market_counts}; caps={LENS_DIRECT_LOCAL_MAX}/{LENS_DIRECT_US_MAX}/{LENS_DIRECT_CN_MAX}; order=local->us->cn')
    if market_counts[2] == 0:
        print('V77 WARNING: no Chinese-store Lens result survived filters')
    if sent > 0 and expansion_query:
        _save_more_results_state(from_number, expansion_query, bot_id, lang, 'lens', selected, image_b64=image_b64, image_mime=image_mime, visual_identity=lens.get('visual_identity') or lens.get('relevance_target') or expansion_query, reset=not more_mode)
        _send_more_results_choice(from_number, bot_id, lang)
    return sent > 0

def process_single_image(message, bot_id, lang='ar'):
    from_number = message['from']
    market = activate_market(from_number)
    caption = (message.get('image', {}) or {}).get('caption', '').strip()
    WORKERS.submit(send_whatsapp_text, from_number, T(lang, 'identifying'), bot_id)
    try:
        b64, mime = download_whatsapp_media(message['image']['id'])
    except Exception as e:
        print(f'MEDIA DOWNLOAD ERR: {e}')
        send_whatsapp_text(from_number, T(lang, 'image_error'), bot_id)
        return
    lens_direct_attempted = False
    if LENS_DIRECT_MODE and ENABLE_GOOGLE_LENS and SERPAPI_API_KEY and PUBLIC_BASE_URL:
        lens_direct_attempted = True
        lens_direct = google_lens_lookup(b64, mime, lang, caption, light=True)
        if lens_direct.get('matches'):
            if send_lens_direct_results(from_number, lens_direct, bot_id, lang, caption, image_b64=b64, image_mime=mime):
                return
        print('LENS DIRECT MODE: no Google results -> full pipeline fallback')
        send_whatsapp_text(from_number, T(lang, 'lens_none'), bot_id)
    lens_future = None
    if not lens_direct_attempted and LENS_PARALLEL_WITH_VISION and ENABLE_GOOGLE_LENS and SERPAPI_API_KEY and PUBLIC_BASE_URL:
        lens_future = LENS_POOL.submit(_run_with_market, market, google_lens_lookup, b64, mime, lang, caption)
    vision_name = identify_product_with_retry(b64, mime, lang)
    force_fashion_lens = is_fashion_identity(vision_name, caption)
    use_lens, route_reason = lens_routing_decision(vision_name, caption)
    use_lens = force_fashion_lens or use_lens
    if lens_direct_attempted:
        use_lens = False
        route_reason = 'LENS_DIRECT_ALREADY_ATTEMPTED'
    lens = {'aliases': [], 'matches': [], 'query': ''}
    if use_lens:
        if lens_future is not None:
            try:
                lens = lens_future.result(timeout=LENS_TOTAL_TIMEOUT_SECONDS + 5) or lens
            except Exception as e:
                print(f'LENS PARALLEL ERR: {e}')
        else:
            lens = google_lens_lookup(b64, mime, lang, caption or vision_name)
    elif lens_future is not None:
        lens_future.cancel()
    active_lens = None
    identity_source = 'VISION'
    combined_name = vision_name
    lens_title = ((lens.get('chosen') or {}).get('title') or lens.get('query') or '').strip()
    print(f'SMART ROUTER: vision={vision_name!r} use_lens={use_lens} force_fashion={force_fashion_lens} reason={route_reason}')
    if use_lens:
        if force_fashion_lens and lens_title:
            lens['force_lens_only'] = True
            combined_name = ' | '.join(fuse_identity_aliases(lens_title, '', lens.get('aliases')))
            active_lens = lens
            identity_source = 'LENS_FASHION_FORCED'
            print(f'FASHION LENS FORCED: {lens_title}')
        elif lens_title and vision_name:
            if identity_candidates_agree(vision_name, lens_title):
                combined_name = ' | '.join(fuse_identity_aliases(lens_title, vision_name))
                active_lens = lens
                identity_source = 'VISION+LENS_AGREE_FUSED'
                print('IDENTITY JUDGE SKIPPED: candidates already agree -> fused aliases')
            else:
                judged_name, active_lens, identity_source = choose_image_identity(b64, mime, lens, vision_name)
                if active_lens:
                    combined_name = ' | '.join(fuse_identity_aliases(judged_name, vision_name))
                else:
                    combined_name = judged_name
        elif lens_title:
            combined_name = ' | '.join(fuse_identity_aliases(lens_title, '', lens.get('aliases')))
            active_lens, identity_source = (lens, 'LENS_ONLY')
        else:
            combined_name, active_lens, identity_source = (vision_name, None, 'VISION_LENS_EMPTY')
    else:
        print('GOOGLE LENS SKIPPED BY SMART ROUTER')
    print(f'FINAL IMAGE IDENTITY [{identity_source}]: {combined_name}')
    if combined_name and caption:
        request_query = f'{caption} — {combined_name}'
        prompt_text = f'هوية المنتج المعتمدة: {combined_name}\nطلب المستخدم: {caption}\nابحث عن نفس المنتج فقط. لا توسع البحث إلى منتج يشاركه المكون أو اللون أو الفئة. {lang_instr(lang)}'
        txt, urls = search_product(request_query, lang, prompt_text=prompt_text, lens_context=active_lens)
        query = request_query
    elif combined_name:
        txt, urls = search_product(combined_name, lang, lens_context=active_lens)
        query = combined_name
    else:
        txt, urls = ('', {})
        query = caption
    if query:
        LAST_SEARCH[from_number] = {'product': query}
    if not txt or not extract_store_offers(txt):
        if txt and (is_service_answer(txt) or is_informational_answer(txt)):
            send_product_result(from_number, txt, urls, bot_id, lang, query)
            return
        if query:
            _store_pending_global(from_number, bot_id, lang, query, active_lens, prompt_text if combined_name and caption else None)
            send_not_found_choice(from_number, bot_id, lang)
        else:
            send_whatsapp_text(from_number, T(lang, 'cant_identify'), bot_id)
        return
    result_type = send_product_result(from_number, txt, urls, bot_id, lang, query)
    if result_type == 'none' and query:
        _store_pending_global(from_number, bot_id, lang, query, active_lens, prompt_text if combined_name and caption else None)
        send_not_found_choice(from_number, bot_id, lang)
        return

def identify_image_product(msg):
    try:
        b64, mime = download_whatsapp_media(msg['image']['id'])
        return identify_product_with_retry(b64, mime, 'ar')
    except Exception:
        return ''

def process_cart(products, from_number, bot_id, lang='ar'):
    market = market_for_user(from_number)
    results = list(WORKERS.map(lambda p: (p, *_run_with_market(market, search_product, p, lang)), products))
    any_ok = False
    for p, txt, urls in results:
        if not txt:
            continue
        any_ok = True
        send_product_result(from_number, txt, urls, bot_id, lang, p, best_only=True)
    if not any_ok:
        send_whatsapp_text(from_number, T(lang, 'not_found'), bot_id)
        return
    LAST_SEARCH[from_number] = {'product': products[0]}

def process_multi_images(messages, from_number, bot_id, lang='ar'):
    activate_market(from_number)
    send_whatsapp_text(from_number, T(lang, 'multi_images', c=len(messages)), bot_id)
    names = [n for n in WORKERS.map(identify_image_product, messages) if n]
    if not names:
        send_whatsapp_text(from_number, T(lang, 'cant_identify'), bot_id)
        return
    process_cart(names, from_number, bot_id, lang)

def is_map_command(text):
    compact = re.sub('[^\\w\\u0600-\\u06FF]', '', normalize_ar(text))
    exact = {'الخريطه', 'خريطه', 'الموقع', 'موقع', 'اللوكيشن', 'لوكيشن', 'الاقرب', 'اقربمكان', 'وينه', 'ويناحصله', 'وينالاقيه', 'map', 'location', 'nearest', 'closest'}
    return compact in exact

def send_last_search_map(from_number, bot_id, lang):
    last_search = LAST_SEARCH.get(from_number)
    if not last_search or not last_search.get('product'):
        send_whatsapp_text(from_number, T(lang, 'no_saved_product'), bot_id)
        return
    send_maps_button(from_number, last_search['product'], bot_id, lang)
PENDING_BRAND_PICKS = {}
PENDING_CART_PICKS = {}
SEARCH_RUNS = max(1, min(3, int(os.environ.get('SEARCH_RUNS', '2'))))
TOURNAMENT_GRACE_SECONDS = max(0.25, float(os.environ.get('TOURNAMENT_GRACE_SECONDS', '1.2')))
LENS_FAST_READY_SECONDS = max(3.0, min(5.0, float(os.environ.get('LENS_FAST_READY_SECONDS', '5.0'))))
V26_SEARCH_POOL = ThreadPoolExecutor(max_workers=8)
SIMILAR_MAX_STORES = max(MAX_STORES, int(os.environ.get('SIMILAR_MAX_STORES', '10')))
MSG['ar'].update({'ask_global_after_local': 'لقيت لك النتائج المحلية فوق 👆\nتبي أدور لك نفس المنتج في المتاجر العالمية أيضاً؟ 🌍', 'compare_searching': '⚖️ طلبك عام بدون ماركة محددة.. أسوي لك مقارنة بين أفضل البراندات المتوفرة!', 'pick_prompt': 'اختر منتجاً من القائمة وأدور لك أفضل الأسعار المتوفرة 👇', 'list_button': 'اختر منتج', 'cart_comparing': '🧺 لقيت {c} أصناف.. أقارن لك السلة كاملة في المتاجر وأشوف وين تطلع أوفر وأسهل!', 'cart_pick_prompt': 'اختر متجراً وأرسل لك كل أصنافك بروابطها المباشرة داخله — طلبية وحدة وسلة وحدة 👇', 'cart_store_button': 'اختر متجر', 'cart_total': '💰 مجموع السلة: {t}', 'cart_expired': 'قائمة السلة قدمت 😅 دز قائمة الأصناف من جديد وأجهزها لك على طول.', 'cart_session_tip': '💡 المهم: أضف الصنف الأول من الزر، وبعدها دوّر باقي الأصناف من بحث المتجر بنفس الصفحة — لا ترجع لواتساب بين كل صنف عشان تتراكم كلها في سلة وحدة.', 'cart_plan_total': '💰 مجموع الخطة كاملة: {t}', 'cart_not_anywhere': '⛔ ما لقيتها في أي متجر بالقائمة: {items}', 'chat_redirect': 'أنا حاضر ومعك! 🙌\nدز اسم المنتج أو صورته وأدور لك أفضل الأسعار، أو اكتب طلب الخدمة اللي تحتاجها 🛒'})
MSG['en'].update({'ask_global_after_local': 'Found local results above 👆 Want me to also search international stores for the same product? 🌍', 'compare_searching': '⚖️ Your request is generic, so I’m comparing the best brands/options first!', 'pick_prompt': 'Pick a product and I’ll search the best available prices 👇', 'list_button': 'Pick product', 'cart_comparing': '🧺 Found {c} items.. comparing your full basket across stores to find the easiest best-value option!', 'cart_pick_prompt': 'Pick a store and I’ll send all your items with direct links inside it — one order, one cart 👇', 'cart_store_button': 'Pick store', 'cart_total': '💰 Basket total: {t}', 'cart_expired': 'That basket list expired 😅 send your items again and I’ll rebuild it.', 'cart_session_tip': '💡 Add the first item from the button, then find the rest using the store search in the same page so they stay in one cart.', 'cart_plan_total': '💰 Full plan total: {t}', 'cart_not_anywhere': '⛔ Not found in any listed store: {items}', 'chat_redirect': 'I’m here 🙌 Send a product name/photo for prices, or type the service you need 🛒'})
MSG['fr']['ask_global_after_local'] = 'J’ai trouvé les résultats locaux ci-dessus 👆 Voulez-vous que je cherche aussi le même produit dans les boutiques internationales ? 🌍'
MSG['es']['ask_global_after_local'] = 'Encontré los resultados locales arriba 👆 ¿Quieres que busque también el mismo producto en tiendas internacionales? 🌍'
MSG['pt']['ask_global_after_local'] = 'Encontrei os resultados locais acima 👆 Quer que eu procure o mesmo produto também em lojas internacionais? 🌍'
MSG['tr']['ask_global_after_local'] = 'Yerel sonuçları yukarıda buldum 👆 Aynı ürünü uluslararası mağazalarda da aramamı ister misiniz? 🌍'
MSG['ru']['ask_global_after_local'] = 'Локальные результаты уже выше 👆 Искать этот же товар также в международных магазинах? 🌍'
MSG['zh']['ask_global_after_local'] = '上面已经找到本地结果 👆 要不要继续在国际商店中搜索同一商品？🌍'
MSG['hi'].update({'ask_global_after_local': 'स्थानीय नतीजे ऊपर हैं 👆 क्या इसी प्रोडक्ट के लिए अंतरराष्ट्रीय स्टोर भी खोजूँ? 🌍', 'compare_searching': '⚖️ आपका अनुरोध सामान्य है, इसलिए पहले सबसे अच्छे ब्रांड/विकल्पों की तुलना कर रहा हूँ!', 'pick_prompt': 'कोई प्रोडक्ट चुनें, फिर मैं उसकी सबसे अच्छी उपलब्ध कीमतें खोजूँगा 👇', 'list_button': 'प्रोडक्ट चुनें', 'cart_comparing': '🧺 {c} आइटम मिले.. पूरी कार्ट की अलग-अलग स्टोर में तुलना कर रहा हूँ!', 'cart_pick_prompt': 'स्टोर चुनें और मैं सभी आइटम के सीधे लिंक एक ही जगह भेज दूँगा 👇', 'cart_store_button': 'स्टोर चुनें', 'cart_total': '💰 कार्ट कुल: {t}', 'cart_expired': 'यह कार्ट सूची समाप्त हो गई 😅 आइटम दोबारा भेजें।', 'cart_session_tip': '💡 पहले आइटम को बटन से जोड़ें, फिर उसी स्टोर में बाकी आइटम खोजें ताकि एक ही कार्ट रहे।', 'cart_plan_total': '💰 पूरी योजना का कुल: {t}', 'cart_not_anywhere': '⛔ किसी सूचीबद्ध स्टोर में नहीं मिला: {items}', 'chat_redirect': 'मैं यहाँ हूँ 🙌 कीमत के लिए प्रोडक्ट का नाम/फोटो भेजें या अपनी ज़रूरत की सेवा लिखें 🛒'})
MSG['ur'].update({'ask_global_after_local': 'مقامی نتائج اوپر ہیں 👆 کیا اسی پروڈکٹ کے لیے بین الاقوامی اسٹورز بھی تلاش کروں؟ 🌍', 'compare_searching': '⚖️ آپ کی درخواست عمومی ہے، اس لیے پہلے بہترین برانڈز/آپشنز کا موازنہ کر رہا ہوں!', 'pick_prompt': 'ایک پروڈکٹ منتخب کریں، پھر میں اس کی بہترین دستیاب قیمتیں تلاش کروں گا 👇', 'list_button': 'پروڈکٹ منتخب کریں', 'cart_comparing': '🧺 {c} آئٹمز مل گئے.. پوری کارٹ کا مختلف اسٹورز میں موازنہ کر رہا ہوں!', 'cart_pick_prompt': 'اسٹور منتخب کریں اور میں تمام آئٹمز کے براہِ راست لنکس ایک جگہ بھیج دوں گا 👇', 'cart_store_button': 'اسٹور منتخب کریں', 'cart_total': '💰 کارٹ کا کل: {t}', 'cart_expired': 'یہ کارٹ فہرست ختم ہو گئی 😅 آئٹمز دوبارہ بھیجیں۔', 'cart_session_tip': '💡 پہلا آئٹم بٹن سے شامل کریں، پھر اسی اسٹور میں باقی آئٹمز تلاش کریں تاکہ ایک ہی کارٹ رہے۔', 'cart_plan_total': '💰 مکمل منصوبے کا کل: {t}', 'cart_not_anywhere': '⛔ کسی درج شدہ اسٹور میں نہیں ملا: {items}', 'chat_redirect': 'میں حاضر ہوں 🙌 قیمت کے لیے پروڈکٹ کا نام/تصویر بھیجیں یا مطلوبہ سروس لکھیں 🛒'})
COUNTRY_NAMES_AR = {'kw': 'الكويت', 'sa': 'السعودية', 'ae': 'الإمارات', 'bh': 'البحرين', 'qa': 'قطر', 'om': 'عمان', 'iq': 'العراق', 'jo': 'الأردن', 'lb': 'لبنان', 'eg': 'مصر', 'sy': 'سوريا', 'ye': 'اليمن', 'ps': 'فلسطين', 'ma': 'المغرب', 'dz': 'الجزائر', 'tn': 'تونس', 'ly': 'ليبيا', 'sd': 'السودان'}
TEXT77_LANG_INSTR = {'ar': 'رد باللغة العربية فقط في نصوص الواجهة، لكن لا تحوّل أسعار المتاجر الأجنبية. أبقِ السعر والعملة الأصلية كما ظهرا في المصدر: متاجر أمريكا USD، والمتاجر الصينية USD أو CNY/RMB حسب المصدر. الأسعار المحلية فقط بعملة بلد المستخدم. يجب أن يحتوي كل سطر متجر على السعر الرقمي والعملة الأصلية صراحةً.', 'en': "Respond in English for UI text, but NEVER convert foreign-store prices. Preserve the exact source currency: US stores in USD; China stores in USD or CNY/RMB as shown by the source. Only local-store prices use the user's local currency. Every store line must explicitly include numeric price plus original currency.", 'fr': 'Répondez en français pour l’interface, mais ne convertissez JAMAIS les prix des boutiques étrangères. Conservez la devise exacte de la source : USD pour les boutiques américaines ; USD ou CNY/RMB pour les boutiques chinoises. Seuls les prix locaux utilisent la devise locale de l’utilisateur.', 'es': 'Responde en español para la interfaz, pero NUNCA conviertas los precios de tiendas extranjeras. Conserva la moneda exacta de la fuente: USD para tiendas de EE. UU.; USD o CNY/RMB para tiendas chinas. Solo los precios locales usan la moneda local del usuario.', 'pt': 'Responda em português para a interface, mas NUNCA converta preços de lojas estrangeiras. Preserve a moeda exata da fonte: USD para lojas dos EUA; USD ou CNY/RMB para lojas chinesas. Apenas os preços locais usam a moeda local do usuário.', 'tr': 'Arayüz metinlerinde Türkçe yanıt ver, ancak yabancı mağaza fiyatlarını ASLA dönüştürme. Kaynaktaki para birimini aynen koru: ABD mağazaları USD; Çin mağazaları kaynakta göründüğü gibi USD veya CNY/RMB. Yalnızca yerel mağaza fiyatları kullanıcının yerel para biriminde olsun.', 'ru': 'Для интерфейса отвечайте по-русски, но НИКОГДА не конвертируйте цены зарубежных магазинов. Сохраняйте валюту источника: магазины США — USD; китайские магазины — USD или CNY/RMB, как указано в источнике. Только локальные цены используют местную валюту пользователя.', 'zh': '界面文字使用简体中文，但绝不要转换海外商店的价格。保留来源中的原始货币：美国商店使用 USD；中国商店按来源保留 USD 或 CNY/RMB。只有本地商店价格使用用户所在国家/地区的本地货币。', 'hi': 'UI टेक्स्ट हिंदी में दें, लेकिन विदेशी स्टोर की कीमतों को कभी कन्वर्ट न करें। स्रोत की मूल मुद्रा रखें: US स्टोर USD में; चीन के स्टोर स्रोत के अनुसार USD या CNY/RMB में। केवल स्थानीय स्टोर की कीमत उपयोगकर्ता की स्थानीय मुद्रा में हो।', 'ur': 'UI متن اردو میں دیں، مگر غیر ملکی اسٹور کی قیمت کبھی تبدیل نہ کریں۔ اصل ماخذ کی کرنسی برقرار رکھیں: امریکی اسٹور USD میں؛ چینی اسٹور ماخذ کے مطابق USD یا CNY/RMB میں۔ صرف مقامی اسٹور کی قیمت صارف کی مقامی کرنسی میں ہو۔'}

def text77_lang_instr(lang):
    code = str(lang or 'en').strip().lower().replace('_', '-').split('-')[0]
    if code in TEXT77_LANG_INSTR:
        return TEXT77_LANG_INSTR[code]
    name = language_name_en(code)
    return f"Respond in {name} for all user-facing UI and descriptive text, but NEVER convert foreign-store prices. Preserve the exact source currency: US stores in USD; China stores in USD or CNY/RMB exactly as shown by the source. Only local-store prices use the user's local currency. Every store line must explicitly include a numeric price and currency. Keep brand names, model names, SKUs, sizes, URLs and currency codes unchanged."
TEXT77_lang_instr = text77_lang_instr
TEXT77_SYSTEM_PROMPT = SYSTEM_PROMPT + "\n\nIMPORTANT OVERRIDE FOR TYPED-TEXT SEARCH ONLY:\nIgnore any earlier instruction that forces all prices into KWD or the user's local currency.\nFor LOCAL stores, return the source price in the user's local currency.\nFor UNITED STATES stores, return the source price in USD, never converted.\nFor CHINA stores, return the source price exactly as listed by the store, normally USD or CNY/RMB, never converted.\nThe application will perform FX conversion after retrieval. Therefore preserving the original numeric price and original currency is mandatory.\nDo not output a converted local-currency value for a foreign store.\n"

def text77_market_instruction():
    m = current_market()
    cc = (m.get('country') or DEFAULT_COUNTRY).lower()
    place = m.get('country_name') or COUNTRY_NAMES.get(cc, cc.upper())
    currency = m.get('currency') or 'local currency'
    currencies = ', '.join(country_currency_codes(cc)) or currency
    hl = m.get('search_hl') or country_search_hl(cc)
    tlds = ', '.join(country_tlds(cc))
    local_stores = priority_stores_for('')
    stores_hint = ', '.join(local_stores[:6]) if local_stores else 'strong local specialist stores and marketplaces'
    return f"\nIMPORTANT TYPED-TEXT GEO RULE: local market is {place} (gl={cc}, hl={hl}, ccTLD={tlds}). Accepted local currencies: {currencies}; primary display currency: {currency}. LOCAL IS THE MAIN PRODUCT: search it deeply before foreign markets. Use the user's wording, commercial English name, and local-commerce wording when useful. Check {stores_hint}, then broaden to smaller genuine local merchants indexed by Google; this is not a whitelist. Return in strict order: up to {LENS_DIRECT_LOCAL_MAX} LOCAL {place} results, then up to {LENS_DIRECT_US_MAX} US, then up to {LENS_DIRECT_CN_MAX} China. Reject every fourth country. Heureka/heureka.cz/heureka.sk is blocked globally as a comparison site; Eureka Kuwait is allowed. Local prices use a valid local source currency ({currencies}); US stays USD; China stays source USD or CNY/RMB. Never convert foreign prices in the AI response. A .com domain can still be local when Google local targeting, local currency, country path/text, or merchant identity ties it to the local market. For SERVICES keep providers local only.\n"

def text77_store_domain(name):
    return store_domain(name)

def text77_extract_store_offers(txt, limit=None):
    offers = []
    for line in (txt or '').splitlines():
        s = line.strip()
        m = re.match('^(✅|🏆|•)\\s*(.+?)\\s*(?:—|–|-)\\s*(.+)$', s)
        if not m or not re.search('\\d', m.group(3)):
            continue
        if re.search('\\(\\s*(?:هاتف|Phone|phone|Tel|tel)\\s*:', s):
            continue
        name = _clean_store_name(m.group(2)) if '_clean_store_name' in globals() else m.group(2).strip()
        if is_blocked_store(name, ''):
            print(f'TEXT77 BLOCKED STORE LINE SKIP: {name}')
            continue
        s = f'{m.group(1)} {name} — {m.group(3).strip()}'
        if is_junk_store(name):
            continue
        best = m.group(1) in ('✅', '🏆')
        body = s if best else s.lstrip('•').strip()
        offers.append({'line': body, 'name': name, 'best': best})
    cap = MAX_STORES if limit is None else max(1, int(limit))
    return offers[:cap]

def text77_call_gemini(parts, system=TEXT77_SYSTEM_PROMPT, use_search=True):
    model = GEMINI_SEARCH_MODEL if use_search else GEMINI_FAST_MODEL
    gemini_url = f'{GEMINI_BASE_URL}/{model}:generateContent'
    payload = {'systemInstruction': {'parts': [{'text': system + (text77_market_instruction() if use_search else '')}]}, 'contents': [{'role': 'user', 'parts': parts}], 'generationConfig': {'temperature': 0, 'maxOutputTokens': 1000 if use_search else 300}}
    if use_search:
        payload['tools'] = [{'google_search': {}}]
    with GEMINI_STATS_LOCK:
        key = 'search_calls' if use_search else 'plain_calls'
        GEMINI_STATS[key] += 1
        print(f'TEXT77 GEMINI CALL model={model} search={use_search} totals={GEMINI_STATS}')
    try:
        r = requests.post(gemini_url, params={'key': GEMINI_API_KEY}, json=payload, timeout=(5, GEMINI_SEARCH_TIMEOUT_SECONDS if use_search else GEMINI_PLAIN_TIMEOUT_SECONDS))
        if r.status_code >= 400:
            print(f'TEXT77 Gemini HTTP {r.status_code}: {r.text[:500]}')
            return ('', {})
        data = r.json()
        candidates = data.get('candidates') or []
        if not candidates:
            return ('', {})
        cand = candidates[0]
        text = ''.join((p.get('text', '') for p in cand.get('content', {}).get('parts', []))).strip()
        pairs = []
        m = re.search('(?im)^\\s*LINKS\\s*:\\s*(.+)$', text)
        if m:
            for part in re.split('[,،]+', m.group(1)):
                part = part.strip()
                if '=' in part:
                    name, dom = part.split('=', 1)
                    name, dom = (name.strip(), clean_domain(dom))
                    if name and '.' in dom:
                        pairs.append((name, dom))
            text = re.sub('(?im)^\\s*LINKS\\s*:.*$', '', text).strip()
        text = re.sub('https?://\\S+', '', text).replace('**', '').strip()
        metadata = cand.get('groundingMetadata', {}) or {}
        chunks = metadata.get('groundingChunks', []) or []
        uris = [(c.get('web') or {}).get('uri', '') for c in chunks]
        finals = resolve_all(uris[:12]) if uris else []
        records = []
        for i, chunk in enumerate(chunks[:12]):
            web = chunk.get('web') or {}
            raw_uri = web.get('uri', '')
            final_uri = finals[i] if i < len(finals) else raw_uri
            records.append({'title': web.get('title', ''), 'raw': raw_uri, 'url': final_uri or raw_uri})
        urls_map, used_urls = ({}, set())
        stores = extract_store_names(text)
        supports = metadata.get('groundingSupports', []) or []
        for store in stores:
            store_norm = normalize_name(store)
            for support in supports:
                segment = (support.get('segment') or {}).get('text', '')
                if store_norm and store_norm in normalize_name(segment):
                    for idx in support.get('groundingChunkIndices', []) or []:
                        if 0 <= idx < len(records):
                            url = records[idx]['url']
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
                if rec['url'] and key and (key in haystack) and (rec['url'] not in used_urls):
                    urls_map[name] = rec['url']
                    used_urls.add(rec['url'])
                    break
        for store in stores:
            if store in urls_map:
                continue
            dom = text77_store_domain(store)
            if not dom:
                continue
            key = domain_key(dom)
            for rec in records:
                haystack = f"{rec['title']} {rec['raw']} {rec['url']}".lower()
                if rec['url'] and key and (key in haystack) and (rec['url'] not in used_urls):
                    urls_map[store] = rec['url']
                    used_urls.add(rec['url'])
                    break
        if len(urls_map) < MAX_STORES:
            for rec in records:
                url = rec['url']
                if not url or url in used_urls:
                    continue
                label = source_label(rec['title'], url)
                if label not in urls_map:
                    urls_map[label] = url
                    used_urls.add(url)
                if len(urls_map) >= MAX_STORES:
                    break
        return (text, dict(list(urls_map.items())[:MAX_STORES]))
    except Exception as e:
        print(f'TEXT77 Gemini err {e}')
        return ('', {})

def text77_bilingual_search_instruction(query, lang):
    m = current_market()
    market_name = m.get('country_name', 'Kuwait')
    hl = m.get('search_hl') or country_search_hl()
    return f"Search this exact product deeply in the LOCAL market {market_name}: {query}. Use the original wording, English commercial name, and local commerce language {hl}. Do not stop at famous stores; inspect smaller genuine {market_name} merchants indexed by Google. Local prices must be numeric and use an accepted local currency ({', '.join(country_currency_codes())}). Then US and China only if needed. {TEXT77_lang_instr(lang)}"

def text77_is_foreign_result(item):
    return is_foreign_lens_result(item)
BRAND_DETECTION_SYSTEM = "Decide whether the user's product request explicitly contains a specific brand or model name.\nReturn exactly YES or NO. Do not explain. A category without a brand/model is NO."
ENABLE_RELEVANCE_FILTER = env_bool('ENABLE_RELEVANCE_FILTER', True)
_NON_PRODUCT_WORDS = ('owners manual', "owner's manual", 'service manual', 'workshop manual', 'repair manual', 'manual pdf', 'handbook', 'wiring diagram', 'parts catalog', 'parts catalogue', 'spare part', 'spare parts', 'دليل المالك', 'دليل الاستخدام', 'كتيب', 'دليل الصيانه', 'دليل الصيانة', 'قطع غيار', 'مخطط', 'متوافق مع', 'compatible with', 'replacement for', 'مروحه', 'مروحة', 'propeller', 'impeller', 'ستارتر', 'starter motor', 'كاربريتر', 'carburetor', 'carburettor', 'بواجي', 'spark plug', 'gasket', 'فلتر زيت', 'oil filter', 'فلتر هواء', 'air filter', 'sensor for', 'sticker', 'decal')
RELEVANCE_FILTER_SYSTEM = 'أنت مدقق نتائج لبوت تسوق. أعد فقط أرقام النتائج التي تبيع المنتج المطلوب نفسه كاملاً.\nارفض الكتيبات وPDF وقطع الغيار والإكسسوارات والخدمات والتأجير إلا إذا كان طلب المستخدم نفسه عنها.\nأرجع JSON فقط: {"keep":[1,3]}'
SIMILAR_RELEVANCE_FILTER_SYSTEM = 'أنت مدقق نتائج لبدائل مشابهة. أبقِ البدائل الحقيقية من نفس الفئة والاستخدام،\nوارفض المنتج الأصلي نفسه والكتيبات وقطع الغيار والملحقات والخدمات. أرجع JSON فقط: {"keep":[1,3]}'
_URL_ALIVE_CACHE = {}
_URL_ALIVE_LOCK = threading.Lock()
_STORE_HOME_CACHE = {}
_STORE_HOME_LOCK = threading.Lock()
STORE_DOMAIN_SYSTEM = 'أرجع دومين الموقع الرسمي للمتجر فقط بدون https وبدون شرح. إذا لم تكن متأكداً 100% أرجع NONE.'
TRANSLATE_TITLES_SYSTEM = 'ترجم أسماء المنتجات التالية إلى العربية بأسلوب متجر واضح ومختصر. أبقِ البراند والموديل والأرقام كما هي.\nسطر واحد لكل منتج وبنفس الترقيم. بدون شرح.'
AR_TITLE_CACHE = {}
AR_TITLE_LOCK = threading.Lock()
_STORE_GENERIC_TOKENS = {'هايبر', 'هاير', 'ماركت', 'هايبرماركت', 'هايرماركت', 'سوبرماركت', 'سوبر', 'مول', 'اسواق', 'سوق', 'مركز', 'سنتر', 'center', 'centre', 'اونلاين', 'اون', 'لاين', 'الكويت', 'كويت', 'متجر', 'محل', 'شركه', 'شركة', 'hyper', 'market', 'hypermarket', 'supermarket', 'super', 'store', 'shop', 'online', 'kuwait', 'kw', 'mall', 'co', 'company', 'the'}
STORE_UNIFY_SYSTEM = 'أنت موحّد أسماء متاجر. جمّع الأرقام التي تعود لنفس المتجر الفعلي حتى لو اختلف الإملاء أو اللغة.\nأرجع JSON فقط: {"groups":[[1,3],[2],[4,5]]} بحيث يظهر كل رقم مرة واحدة بالضبط.'
_STORE_UNIFY_CACHE = {}
_STORE_UNIFY_LOCK = threading.Lock()
KNOWN_SEARCH_TEMPLATES = {'luluhypermarket': 'https://gcc.luluhypermarket.com/en-kw/search?text={q}', 'carrefourkuwait': 'https://www.carrefourkuwait.com/mafkwt/en/v4/search?keyword={q}', 'taw9eel': 'https://www.taw9eel.com/en/catalogsearch/result/?q={q}', 'sultan-center': 'https://www.sultan-center.com/catalogsearch/result/?q={q}', 'jm3eia': 'https://www.jm3eia.com/en/search?q={q}', 'safathome': 'https://www.safathome.com/catalogsearch/result/?q={q}', 'xcite': 'https://www.xcite.com/search?text={q}', 'abyat': 'https://www.abyat.com/kw/en/search/{q}'}
_GENERIC_SEARCH_PATTERNS = ('https://{d}/catalogsearch/result/?q={q}', 'https://{d}/search?q={q}', 'https://{d}/en/search?q={q}')
_SEARCH_TMPL_CACHE = {}
_SEARCH_TMPL_LOCK = threading.Lock()
CART_ITEM_DEADLINE = max(60, int(os.environ.get('CART_DEADLINE_SECONDS', '240')))
CART_CONCURRENCY = max(1, int(os.environ.get('CART_CONCURRENCY', '2')))

def _clean_store_name(name):
    n = re.sub('[\\[\\]«»\\"\']+', '', str(name or ''))
    n = re.sub('\\(\\s*[^)]*\\)?\\s*$', '', n)
    return ' '.join(n.split()).strip(' -—–:،') or str(name or '').strip()
_FINDZIA_ACCESSORY_TOKENS = {'case', 'cover', 'protector', 'guard', 'skin', 'sticker', 'decal', 'cable', 'cord', 'charger', 'adapter', 'adaptor', 'dock', 'stand', 'mount', 'holder', 'strap', 'band', 'sleeve', 'pouch', 'bag', 'lace', 'laces', 'shoelace', 'shoelaces', 'insole', 'insoles', 'sock', 'socks', 'replacement', 'spare', 'part', 'parts', 'accessory', 'accessories', 'manual', 'handbook', 'pdf', 'كفر', 'غطاء', 'حمايه', 'حماية', 'شاحن', 'كيبل', 'كابل', 'وصله', 'وصلة', 'حامل', 'سوار', 'رباط', 'اربطة', 'أربطة', 'جوارب', 'نعل', 'قطع', 'غيار', 'اكسسوار', 'اكسسوارات'}
_FINDZIA_CONFLICT_GROUPS = (({'tennis', 'تنس'}, {'running', 'runner', 'jogging', 'basketball', 'soccer', 'football', 'golf', 'hiking', 'trail', 'padel', 'تنس', 'جري', 'ركض', 'سله', 'سلة', 'قدم', 'جولف', 'بادل'}), ({'running', 'runner', 'jogging', 'جري', 'ركض'}, {'tennis', 'basketball', 'soccer', 'football', 'golf', 'hiking', 'padel', 'تنس', 'سله', 'سلة', 'قدم', 'جولف', 'بادل'}), ({'padel', 'بادل'}, {'tennis', 'running', 'basketball', 'soccer', 'football', 'golf', 'hiking', 'تنس', 'جري', 'سله', 'سلة', 'قدم', 'جولف'}))
_FINDZIA_QUERY_FILLER = {'buy', 'best', 'price', 'cheap', 'cheapest', 'online', 'shop', 'shopping', 'for', 'the', 'a', 'an', 'of', 'in', 'with', 'new', 'original', 'ابي', 'أبي', 'اريد', 'أريد', 'افضل', 'أفضل', 'ارخص', 'أرخص', 'سعر', 'شراء', 'اونلاين', 'أونلاين'}
_FINDZIA_SPEC_UNITS = {'gb', 'tb', 'mb', 'kb', 'kg', 'g', 'mg', 'lb', 'lbs', 'oz', 'ml', 'l', 'cl', 'cm', 'mm', 'm', 'inch', 'inches', 'in', 'ft', 'w', 'kw', 'mah', 'hz', 'khz', 'mhz', 'ghz', 'mp', 'mm', 'pcs', 'pc', 'pack', 'packs', 'set', 'sets'}
_FINDZIA_PRICE_WORDS = {'kwd', 'kd', 'usd', 'sar', 'aed', 'qar', 'omr', 'bhd', 'cny', 'rmb', 'eur', 'gbp', 'دينار', 'ريال', 'درهم'}

def _findzia_model_tokens(value):
    toks = norm_tokens(value)
    out = set()
    for tok in toks:
        if len(tok) < 3 or not any((c.isdigit() for c in tok)) or (not any((c.isalpha() for c in tok))):
            continue
        low = tok.lower()
        if any((re.fullmatch(f'\\d+(?:\\.\\d+)?{re.escape(unit)}', low) for unit in _FINDZIA_SPEC_UNITS)):
            continue
        if low in _FINDZIA_PRICE_WORDS:
            continue
        out.add(low)
    return out

def _findzia_pure_numbers(value):
    raw = normalize_ar(str(value or '')).lower()
    currency = '(?:kwd|kd|usd|sar|aed|qar|omr|bhd|cny|rmb|eur|gbp|د\\.ك|دك|ر\\.س|ر\\.س|د\\.إ|دإ|ر\\.ق|ر\\.ع|د\\.ب|دينار|ريال|درهم|\\$|€|£|¥|￥)'
    raw = re.sub(f'{currency}\\s*\\d+(?:[.,]\\d+)?|\\d+(?:[.,]\\d+)?\\s*{currency}', ' ', raw, flags=re.I)
    raw = re.sub('\\b\\d+(?:[.,]\\d+)?\\s*%', ' ', raw)
    raw = re.sub('\\b\\d(?:[.,]\\d)?\\s*(?:/\\s*5|stars?|نجوم?)\\b', ' ', raw, flags=re.I)
    return set(re.findall('(?<![a-z\\u0600-\\u06ff])\\d{2,5}(?![a-z\\u0600-\\u06ff])', raw))

def _findzia_lexical_tokens(value):
    return {x for x in norm_tokens(value) - _FINDZIA_QUERY_FILLER if not x.isdigit() and x.lower() not in _FINDZIA_PRICE_WORDS}

def _canonical_result_url(url):
    u = str(url or '').strip()
    if not u.startswith(('http://', 'https://')):
        return u
    try:
        p = urllib.parse.urlsplit(u)
        drop = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'utm_id', 'gclid', 'fbclid', 'msclkid', 'mc_cid', 'mc_eid', 'ref', 'ref_', 'tag', 'affid', 'affiliate', 'aff', 'source', 'campaign'}
        q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True) if k.lower() not in drop]
        path = re.sub('/{2,}', '/', p.path or '/')
        return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), path.rstrip('/') or '/', urllib.parse.urlencode(q, doseq=True), ''))
    except Exception:
        return u.split('#', 1)[0]

def _findzia_hard_product_mismatch(query, title):
    q_raw = normalize_ar(str(query or ''))
    t_raw = normalize_ar(str(title or ''))
    q = norm_tokens(q_raw)
    t = norm_tokens(t_raw)
    if not q or not t:
        return False
    q_acc = q & _FINDZIA_ACCESSORY_TOKENS
    t_acc = t & _FINDZIA_ACCESSORY_TOKENS
    if t_acc - q_acc:
        return True
    for wanted, alternatives in _FINDZIA_CONFLICT_GROUPS:
        if not q & wanted:
            continue
        other = set(alternatives) - set(wanted)
        if t & other and (not t & wanted):
            return True
    q_models = _findzia_model_tokens(q_raw)
    t_models = _findzia_model_tokens(t_raw)
    if q_models and t_models and (not q_models & t_models):
        return True
    q_nums = _findzia_pure_numbers(q_raw)
    t_nums = _findzia_pure_numbers(t_raw)
    shared_lex = _findzia_lexical_tokens(q_raw) & _findzia_lexical_tokens(t_raw)
    if q_nums and t_nums and (len(shared_lex) >= 2):
        shared_nums = q_nums & t_nums
        if not shared_nums:
            return True
        if q_nums - t_nums and t_nums - q_nums:
            return True
    return False

def _findzia_match_score(query, title):
    if _findzia_hard_product_mismatch(query, title):
        return 0.0
    q = _findzia_lexical_tokens(query)
    t = _findzia_lexical_tokens(title)
    if not q or not t:
        return 0.0
    overlap = len(q & t) / max(1, len(q))
    q_models = _findzia_model_tokens(query)
    t_models = _findzia_model_tokens(title)
    model_bonus = 0.38 if q_models and q_models & t_models else 0.0
    q_nums = _findzia_pure_numbers(query)
    t_nums = _findzia_pure_numbers(title)
    numeric_bonus = 0.12 if q_nums and q_nums & t_nums else 0.0
    return min(0.99, overlap * (0.5 if model_bonus else 0.78) + model_bonus + numeric_bonus)

def _findzia_stream_candidate_ok(query, item):
    title = str((item or {}).get('title') or (item or {}).get('line') or '')
    if not title or _findzia_hard_product_mismatch(query, title):
        if title:
            print(f'FINDZIA GUARD HARD-DROP: {title[:100]}')
        return False
    score = _findzia_match_score(query, title)
    strong_model = bool(_findzia_model_tokens(query) & _findzia_model_tokens(title))
    threshold = 0.46 if strong_model else 0.56
    if score < threshold:
        print(f'FINDZIA GUARD HOLD score={score:.2f}: {title[:100]}')
        return False
    return True

def _fast_relevance_confident(query, candidates):
    seq = list(candidates or [])
    q_models = _findzia_model_tokens(query)
    if not seq or not q_models:
        return False
    considered = confident = 0
    for item in seq:
        title = str(item.get('title') or item.get('line') or '')
        if not title:
            continue
        considered += 1
        if _findzia_hard_product_mismatch(query, title):
            continue
        if q_models & _findzia_model_tokens(title):
            confident += 1
    return considered >= 2 and confident / considered >= 0.8

def filter_relevant_offers(query, offers, urls, use_ai=True, mode='exact'):
    if not offers:
        return offers
    q_norm = normalize_ar(str(query or ''))
    wants_non_product = any((normalize_ar(w) in q_norm for w in _NON_PRODUCT_WORDS))
    kept = []
    for o in offers:
        hay = normalize_ar(f"{o.get('line', '')} {match_url(o.get('name', ''), urls or {})}")
        if not wants_non_product and any((normalize_ar(w) in hay for w in _NON_PRODUCT_WORDS)):
            print(f"RELEVANCE HARD-DROP: {o.get('line', '')[:80]}")
            continue
        if _findzia_hard_product_mismatch(query, o.get('line', '')):
            print(f"FINDZIA RELEVANCE HARD-DROP: {o.get('line', '')[:90]}")
            continue
        kept.append(o)
    if not use_ai or not ENABLE_RELEVANCE_FILTER or (not kept) or (len(kept) == 0):
        return kept
    numbered = []
    for i, o in enumerate(kept, 1):
        u = match_url(o.get('name', ''), urls or {})
        try:
            host = urllib.parse.urlparse(u or '').netloc.replace('www.', '')
        except Exception:
            host = ''
        numbered.append(f"{i}. {o.get('line', '')[:100]} — {host}")
    prompt_label = 'المنتج المرجعي للبدائل' if mode == 'similar' else 'طلب المستخدم'
    prompt = f'{prompt_label}: {query}\n\nالنتائج:\n' + '\n'.join(numbered)
    relevance_system = SIMILAR_RELEVANCE_FILTER_SYSTEM if mode == 'similar' else RELEVANCE_FILTER_SYSTEM
    raw, _ = text77_call_gemini([{'text': prompt}], system=relevance_system, use_search=False)
    try:
        data = json.loads(re.search('\\{.*\\}', raw or '', flags=re.S).group(0))
        keep_idx = {int(x) for x in data.get('keep') or []}
        ai_kept = [o for i, o in enumerate(kept, 1) if i in keep_idx]
        dropped = [o.get('line', '')[:60] for i, o in enumerate(kept, 1) if i not in keep_idx]
        if dropped:
            print(f'RELEVANCE AI-DROP ({len(dropped)}): {dropped[:4]}')
        if ai_kept:
            return ai_kept
        deterministic = [o for o in kept if _findzia_match_score(query, o.get('line', '')) >= 0.42]
        print(f'RELEVANCE AI EMPTY -> deterministic fallback {len(deterministic)}/{len(kept)}')
        return deterministic
    except Exception:
        deterministic = [o for o in kept if _findzia_match_score(query, o.get('line', '')) >= 0.42]
        print(f'RELEVANCE AI PARSE FAIL -> deterministic fallback {len(deterministic)}/{len(kept)}: {raw!r}')
        return deterministic

def url_is_alive(url):
    u = str(url or '').strip()
    if not u.startswith('http'):
        return False
    key = u.split('?')[0][:200]
    with _URL_ALIVE_LOCK:
        hit = _URL_ALIVE_CACHE.get(key)
        if hit and time.time() - hit['ts'] < 21600:
            return hit['ok']
    ok = False
    try:
        r = requests.head(u, headers=HEADERS, timeout=6, allow_redirects=True)
        ok = r.status_code < 400
        if not ok and r.status_code in (403, 405, 501):
            r = requests.get(u, headers=HEADERS, timeout=8, stream=True)
            ok = r.status_code < 400
            r.close()
    except Exception as e:
        print(f'URL ALIVE FAIL: {u[:80]} -> {e.__class__.__name__}')
        ok = False
    with _URL_ALIVE_LOCK:
        if len(_URL_ALIVE_CACHE) > 3000:
            _URL_ALIVE_CACHE.clear()
        _URL_ALIVE_CACHE[key] = {'ok': ok, 'ts': time.time()}
    return ok

def resolve_store_homepage(name):
    name = str(name or '').strip()
    if not name:
        return ''
    dom = text77_store_domain(name)
    if dom:
        return f'https://{dom}'
    key = normalize_name(normalize_ar(name))[:80]
    if not key:
        return ''
    with _STORE_HOME_LOCK:
        if key in _STORE_HOME_CACHE:
            return _STORE_HOME_CACHE[key]
    raw, _ = text77_call_gemini([{'text': f"المتجر: {name}\nالبلد: {current_market().get('country_name', 'Kuwait')}"}], system=STORE_DOMAIN_SYSTEM, use_search=False)
    ans = (raw or '').strip().splitlines()[0].strip().lower() if raw else ''
    ans = ans.replace('https://', '').replace('http://', '').strip('/ ')
    url = ''
    if ans and ans != 'none' and re.fullmatch('[a-z0-9][a-z0-9.-]{2,60}\\.[a-z]{2,10}', ans):
        candidate = f'https://{ans}'
        if url_is_alive(candidate):
            url = candidate
        else:
            print(f'STORE HOMEPAGE DEAD — REJECTED: {ans}')
    with _STORE_HOME_LOCK:
        if len(_STORE_HOME_CACHE) > 2000:
            _STORE_HOME_CACHE.clear()
        _STORE_HOME_CACHE[key] = url
    print(f"STORE HOMEPAGE RESOLVED: {name!r} -> {url or 'NONE'}")
    return url

def v26_answer_score(txt, urls, max_results=None):
    stores = len(extract_store_names(txt or ''))
    links = len(urls or {})
    score = stores * 2 + links * 3
    if txt and '📦' in txt:
        score += 1
    return score

def _merge_v26_offer_text(results, title_line, max_results):
    picked = {}
    for txt, urls in results:
        for offer in text77_extract_store_offers(txt or '', limit=max_results):
            key = normalize_name(offer.get('name', ''))
            if not key:
                continue
            price = _extract_numeric_price(offer.get('line', ''))
            prev = picked.get(key)
            if prev is None or (price is not None and (prev[0] is None or price < prev[0])):
                picked[key] = (price, offer)
    if not picked:
        return results[0][0] if results else ''
    ordered = sorted((v for v in picked.values()), key=lambda x: (x[0] is None, x[0] if x[0] is not None else 10 ** 12))[:max_results]
    lines = []
    for i, (_, offer) in enumerate(ordered):
        body = re.sub('^(?:✅|🏆|•)\\s*', '', offer.get('line', '')).strip()
        if body:
            lines.append(f"{('✅' if i == 0 else '•')} {body}")
    return (title_line.strip() + '\n' + '\n'.join(lines)).strip()

def _fast_tournament_results(futs, limit, timeout_seconds):
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
            print(f'TOURNAMENT FIRST ERR: {e}')

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
                print(f'TOURNAMENT PEER ERR: {e}')
        for f in pending2:
            f.cancel()
    return results

def v26_best_of_search(parts, max_results=None, merge_offers=False, merge_title=''):
    limit = MAX_STORES if max_results is None else max(1, int(max_results))
    market_snapshot = current_market()
    try:
        futs = [V26_SEARCH_POOL.submit(_run_with_market, market_snapshot, text77_call_gemini, parts) for _ in range(SEARCH_RUNS)]
        results = _fast_tournament_results(futs, limit, GEMINI_SEARCH_TIMEOUT_SECONDS + 5)
    except Exception as e:
        print(f'v26 best_of_search err {e}')
        return text77_call_gemini(parts)
    results = [(t, u) for t, u in results if t]
    if not results:
        return ('', {})
    scored = sorted(results, key=lambda r: v26_answer_score(r[0], r[1], limit), reverse=True)
    best_txt, best_urls = scored[0]
    merged_urls = dict(best_urls)
    for _, u in scored[1:]:
        for n, link in u.items():
            if n not in merged_urls and link not in merged_urls.values():
                merged_urls[n] = link
    merged_urls = dict(list(merged_urls.items())[:max(limit, 4)])
    if merge_offers:
        best_txt = _merge_v26_offer_text(scored, merge_title or product_title(best_txt, ''), limit)
    print({'v26_tournament': [v26_answer_score(t, u, limit) for t, u in scored], 'winner_stores': len(text77_extract_store_offers(best_txt, limit=limit)), 'total_links': len(merged_urls), 'merged_offers': bool(merge_offers)})
    return (best_txt, merged_urls)

def arabic_titles(titles):
    out, todo = ({}, [])
    for t in titles:
        t = (t or '').strip()
        if not t:
            continue
        key = t.lower()
        with AR_TITLE_LOCK:
            cached = AR_TITLE_CACHE.get(key)
        if cached:
            out[t] = cached
        elif re.search('[\\u0600-\\u06FF]', t):
            out[t] = t
        elif t not in todo:
            todo.append(t)
    if todo:
        numbered = '\n'.join((f'{i + 1}. {t}' for i, t in enumerate(todo)))
        raw, _ = text77_call_gemini([{'text': numbered}], system=TRANSLATE_TITLES_SYSTEM, use_search=False)
        lines = [re.sub('^\\s*\\d+[\\.\\)\\-]\\s*', '', l).strip() for l in (raw or '').splitlines() if l.strip()]
        with AR_TITLE_LOCK:
            if len(AR_TITLE_CACHE) > 3000:
                AR_TITLE_CACHE.clear()
            for i, t in enumerate(todo):
                tr = lines[i] if i < len(lines) and re.search('[\\u0600-\\u06FF]', lines[i]) else t
                out[t] = tr
                AR_TITLE_CACHE[t.lower()] = tr
        print(f'AR TITLES TRANSLATED: {len(todo)}')
    return out

def arabic_search_name(query):
    q = ' '.join(str(query or '').split()).strip()
    if not q or re.search('[\\u0600-\\u06FF]', q):
        return ''
    translated = arabic_titles([q]).get(q, '')
    return translated if translated and translated != q else ''

def send_whatsapp_list(to, body, rows, bot_id, button_title='اختر'):
    _typing_before_outgoing(to, bot_id)
    'v74: رسالة قائمة تفاعلية (حتى 10 صفوف) — لاختيار منتج من مقارنة البراندات.'
    url = f'{GRAPH_URL}/{bot_id}/messages'
    h = {'Authorization': f'Bearer {WHATSAPP_TOKEN}', 'Content-Type': 'application/json'}
    clean_rows = []
    for r in rows[:10]:
        row = {'id': r['id'], 'title': _remove_ui_autolinks(str(r.get('title', '')))[:24]}
        desc = _remove_ui_autolinks(str(r.get('description', '') or ''))[:72]
        if desc:
            row['description'] = desc
        clean_rows.append(row)
    payload = {'messaging_product': 'whatsapp', 'to': to, 'type': 'interactive', 'interactive': {'type': 'list', 'body': {'text': _remove_ui_autolinks(body)[:1024]}, 'action': {'button': _remove_ui_autolinks(button_title)[:20], 'sections': [{'title': _remove_ui_autolinks(button_title)[:24], 'rows': clean_rows}]}}}
    try:
        r = _whatsapp_http_session().post(url, json=payload, headers=h, timeout=(3, WHATSAPP_TIMEOUT_SECONDS))
        if not r.ok:
            print(f'LIST MSG ERR {r.status_code}: {r.text[:200]}')
        return r.ok
    except Exception as e:
        print(f'LIST MSG ERR: {e}')
        return False

def _host_of(url):
    try:
        return urllib.parse.urlparse(str(url or '')).netloc.lower().replace('www.', '')
    except Exception:
        return ''

def canonical_store_key(name, url=''):
    host = _host_of(url)
    if host:
        return domain_key(host)
    dom = text77_store_domain(name)
    if dom:
        return domain_key(dom)
    n = normalize_ar(str(name or ''))
    toks = [t for t in re.findall('[\\w\\u0600-\\u06FF]+', n) if t not in _STORE_GENERIC_TOKENS]
    core = ' '.join(toks).strip()
    if core:
        dom = text77_store_domain(core)
        if dom:
            return domain_key(dom)
    key = normalize_name(''.join(toks))
    return key or normalize_name(n)

def unify_store_groups(names):
    if len(names) < 2:
        return [[i] for i in range(len(names))]
    key = '|'.join(sorted((normalize_name(normalize_ar(n)) for n in names)))[:400]
    with _STORE_UNIFY_LOCK:
        if key in _STORE_UNIFY_CACHE:
            return _STORE_UNIFY_CACHE[key]
    numbered = '\n'.join((f'{i}. {n}' for i, n in enumerate(names, 1)))
    raw, _ = text77_call_gemini([{'text': numbered}], system=STORE_UNIFY_SYSTEM, use_search=False)
    groups = None
    try:
        data = json.loads(re.search('\\{.*\\}', raw or '', flags=re.S).group(0))
        cand = [[int(x) - 1 for x in g] for g in data.get('groups') or [] if g]
        seen = sorted((i for g in cand for i in g))
        if seen == list(range(len(names))):
            groups = cand
        else:
            print(f'STORE UNIFY INVALID GROUPS (missing/dup idx): {raw!r}')
    except Exception:
        print(f'STORE UNIFY PARSE FAIL: {raw!r}')
    if groups is None:
        groups = [[i] for i in range(len(names))]
    with _STORE_UNIFY_LOCK:
        if len(_STORE_UNIFY_CACHE) > 500:
            _STORE_UNIFY_CACHE.clear()
        _STORE_UNIFY_CACHE[key] = groups
    return groups

def merge_store_matrix_ai(stores):
    entries = list(stores.values())
    if len(entries) < 2:
        return stores
    names = [e['name'] for e in entries]
    groups = unify_store_groups(names)
    if all((len(g) == 1 for g in groups)):
        return stores
    merged = {}
    for gi, group in enumerate(groups):
        base = min((entries[i] for i in group), key=lambda e: len(e['name']))
        bucket = {'name': base['name'], 'items': {}}
        for i in group:
            for p, inf in entries[i]['items'].items():
                prev = bucket['items'].get(p)
                if prev is None or inf['price'] < prev['price']:
                    bucket['items'][p] = inf
        merged[f'g{gi}'] = bucket
    if len(merged) != len(entries):
        print(f"STORE UNIFY MERGED: {len(entries)} -> {len(merged)} stores: {[m['name'] for m in merged.values()]}")
    return merged

def store_search_url(store_name, query):
    dom = text77_store_domain(store_name)
    host = clean_domain(dom) if dom else _host_of(resolve_store_homepage(store_name))
    if not host:
        return ''
    q = urllib.parse.quote(' '.join(str(query or '').split())[:80])
    with _SEARCH_TMPL_LOCK:
        cached_tmpl = _SEARCH_TMPL_CACHE.get(host)
    candidates = [cached_tmpl] if cached_tmpl else []
    if not candidates:
        dkey = host.split('.')[0]
        if dkey in KNOWN_SEARCH_TEMPLATES:
            candidates.append(KNOWN_SEARCH_TEMPLATES[dkey])
        candidates += [p.replace('{d}', host) for p in _GENERIC_SEARCH_PATTERNS]
    for tmpl in candidates:
        url = tmpl.replace('{q}', q)
        if url_is_alive(url):
            with _SEARCH_TMPL_LOCK:
                if len(_SEARCH_TMPL_CACHE) > 500:
                    _SEARCH_TMPL_CACHE.clear()
                _SEARCH_TMPL_CACHE[host] = tmpl
            return url
    return ''

def cart_item_search(product, lang):
    cached = cache_get(product, lang)
    if cached:
        return cached
    txt, urls = v26_best_of_search([{'text': text77_bilingual_search_instruction(product, lang)}])
    urls = direct_urls_only(urls)
    if txt and text77_extract_store_offers(txt) and (not is_no_result_answer(txt)):
        cache_put(product, lang, txt, urls)
        return (txt, urls)
    market_name = current_market().get('country_name', 'Kuwait')
    txt, urls = text77_call_gemini([{'text': f'ابحث عن {product} في أي متجر محلي في {market_name} يبيعه بسعر رقمي واضح ورابط صفحة منتج مباشر. حتى {MAX_STORES} متاجر من الأرخص للأغلى. {TEXT77_lang_instr(lang)}'}])
    urls = direct_urls_only(urls)
    if txt and text77_extract_store_offers(txt) and (not is_no_result_answer(txt)):
        cache_put(product, lang, txt, urls)
        return (txt, urls)
    return ('', {})

def run_cart_comparison(products, from_number, bot_id, lang='ar'):
    market = market_for_user(from_number)
    send_whatsapp_text(from_number, T(lang, 'cart_comparing', c=len(products)), bot_id)
    results = []
    try:
        deadline = time.time() + CART_ITEM_DEADLINE
        for start in range(0, len(products), CART_CONCURRENCY):
            wave = products[start:start + CART_CONCURRENCY]
            futures = {WORKERS.submit(_run_with_market, market, cart_item_search, p, lang): p for p in wave}
            for future, p in futures.items():
                remain = max(5.0, deadline - time.time())
                try:
                    txt, urls = future.result(timeout=remain)
                except Exception as e:
                    print(f'CART ITEM TIMEOUT/ERR ({p}): {e.__class__.__name__}')
                    txt, urls = ('', {})
                results.append((p, txt, urls))
            if time.time() >= deadline:
                for p in products[start + CART_CONCURRENCY:]:
                    print(f'CART DEADLINE SKIP: {p}')
                    results.append((p, '', {}))
                break
    except Exception as e:
        print(f'CART GATHER CRASH: {e}')
        send_whatsapp_text(from_number, T(lang, 'not_found'), bot_id)
        return
    stores = {}
    try:
        for p, txt, urls in results:
            if not txt:
                continue
            offers = filter_relevant_offers(p, text77_extract_store_offers(txt), urls, use_ai=False)
            for o in offers:
                url = match_url(o.get('name', ''), urls or {})
                price = _extract_numeric_price(o.get('line', ''))
                if price is None or price <= 0:
                    continue
                host = _host_of(url)
                key = canonical_store_key(o.get('name', ''), url)
                if not key:
                    continue
                display = _clean_store_name(o.get('name', '')) or key
                s = stores.setdefault(key, {'name': display, 'items': {}})
                if display and len(display) < len(s['name']):
                    s['name'] = display
                prev = s['items'].get(p)
                if prev is None or price < prev['price']:
                    s['items'][p] = {'price': price, 'url': url}
    except Exception as e:
        print(f'CART MATRIX CRASH: {e}')
        stores = {}
    try:
        stores = merge_store_matrix_ai(stores)
    except Exception as e:
        print(f'STORE UNIFY CRASH (keeping as-is): {e}')
    if not stores:
        any_ok = False
        for p, txt, urls in results:
            if not txt:
                continue
            any_ok = True
            send_product_result(from_number, txt, urls, bot_id, lang, p, best_only=True)
        if not any_ok:
            send_whatsapp_text(from_number, T(lang, 'not_found'), bot_id)
        return
    n = len(products)
    ranked = sorted(stores.values(), key=lambda s: (-len(s['items']), sum((i['price'] for i in s['items'].values()))))[:6]
    unit = U(lang, 'items')
    rows = []
    for i, s in enumerate(ranked):
        cov = len(s['items'])
        total = sum((x['price'] for x in s['items'].values()))
        rows.append({'id': f'cart_{i}', 'title': s['name'][:24], 'description': f'{cov}/{n} {unit} — {format_price(total)} {currency_label(lang)}'[:72]})
    PENDING_CART_PICKS[from_number] = {'stores': [(s['name'], s['items']) for s in ranked], 'products': list(products), 'bot_id': bot_id, 'lang': lang, 'ts': time.time()}
    send_whatsapp_list(from_number, T(lang, 'cart_pick_prompt'), rows, bot_id, T(lang, 'cart_store_button'))
    LAST_SEARCH[from_number] = {'product': products[0]}
    print(f"CART COMPARISON SENT: {[(s['name'], len(s['items'])) for s in ranked]}")

def _greedy_cart_completion(remaining, stores_list, used_idx):
    plans, rem, used = ([], set(remaining), set(used_idx))
    while rem:
        best = None
        for i, (nm, items) in enumerate(stores_list):
            if i in used:
                continue
            cover = [p for p in rem if p in items]
            if not cover:
                continue
            total = sum((items[p]['price'] for p in cover))
            score = (len(cover), -total)
            if best is None or score > best[0]:
                best = (score, i, nm, cover, total)
        if best is None:
            break
        _score, i, nm, cover, _total = best
        used.add(i)
        rem -= set(cover)
        plans.append((i, nm, {p: stores_list[i][1][p] for p in cover}))
    return (plans, sorted(rem))

def _send_store_cart_block(from_number, store_name, items_map, products_order, bot_id, lang, is_main):
    ordered = [p for p in products_order if p in items_map]
    if not ordered:
        return 0.0
    total = sum((items_map[p]['price'] for p in ordered))
    unit = U(lang, 'items')
    if is_main:
        header = f'🧺 {store_name} — {len(ordered)} {unit} — {format_price(total)} {currency_label(lang)}'
    else:
        verb = U(lang, 'completes')
        header = f'🧩 {store_name} — {verb} {len(ordered)} {unit} — {format_price(total)} {currency_label(lang)}'
    send_whatsapp_text(from_number, header, bot_id)
    store_home = None
    for i, p in enumerate(ordered, 1):
        inf = items_map[p]
        body = f"{i}. {p} — {format_price(inf['price'])} {currency_label(lang)}"
        url = inf.get('url') or ''
        if not (url and is_direct_store_url(url)):
            search_link = store_search_url(store_name, p)
            if search_link:
                url = search_link
            else:
                if store_home is None:
                    store_home = resolve_store_homepage(store_name) or ''
                url = url if url and url.startswith('http') and ('google.' not in _host_of(url)) else store_home
        if url:
            send_whatsapp_cta(from_number, body, url, bot_id, f'🛒 {store_name[:18]}')
        else:
            send_whatsapp_text(from_number, body, bot_id)
    return total

def send_cart_from_store(from_number, chosen_idx, stores_list, products, bot_id, lang):
    store_name, items = stores_list[chosen_idx]
    plan_total = _send_store_cart_block(from_number, store_name, items, products, bot_id, lang, is_main=True)
    remaining = [p for p in products if p not in items]
    if remaining:
        plans, still_missing = _greedy_cart_completion(remaining, stores_list, {chosen_idx})
        for _i, nm, cover_items in plans:
            plan_total += _send_store_cart_block(from_number, nm, cover_items, products, bot_id, lang, is_main=False)
        tail = T(lang, 'cart_plan_total', t=f'{format_price(plan_total)} {currency_label(lang)}')
        if still_missing:
            joiner = '، ' if lang in ('ar', 'ur') else ', '
            tail += '\n' + T(lang, 'cart_not_anywhere', items=joiner.join(still_missing))
    else:
        tail = T(lang, 'cart_total', t=f'{format_price(plan_total)} {currency_label(lang)}')
    tail += '\n\n' + T(lang, 'cart_session_tip')
    send_whatsapp_text(from_number, tail, bot_id)
    return True
LEGACY_TEXT_SEARCH_SYSTEM = '\nأنت مساعد تسوق. استخدم بحث Google فعلياً للأسعار والتقييمات الحالية في سوق المستخدم المحلي.\n\nأولاً حدد نوع الطلب:\n\n【الحالة 1】منتج محدد بعلامة تجارية واضحة:\nقارن الأسعار واختر الأرخص، ورد بهذا الشكل فقط:\n📦 [اسم المنتج]\n\n✅ [المتجر الأرخص] — [السعر بعملة السوق]\n• [المتجر الثاني] — [السعر بعملة السوق]\n• [المتجر الثالث] — [السعر بعملة السوق]\n\n【الحالة 2】طلب عام بدون براند محدد:\nابحث عن أفضل الخيارات المتوفرة محلياً بسعر مناسب، مع الالتزام بالتنسيق الذي يطلبه المستخدم في الرسالة.\n\n【الحالة 3】طلب خدمة:\nابحث عن أفضل مزودي الخدمة محلياً، ولا تكتب رقم هاتف إلا إذا ظهر حرفياً في نتائج Google.\n\n【الحالة 4】سؤال معلوماتي:\nأجب على السؤال نفسه مباشرة ولا تعرض مقارنة أسعار إلا إذا طلبها المستخدم.\n\nفي نتائج التسوق التي تحتوي متاجر، سطر أخير إلزامي:\nLINKS: اسم الأول=الدومين الحقيقي, اسم الثاني=الدومين الحقيقي, اسم الثالث=الدومين الحقيقي\nلا تخمّن الدومين، ولا تذكر متجراً أو خياراً من دون مصدر بحث.\nاستبعد Heureka / heureka.cz / heureka.sk نهائياً من نتائج التسوق؛ لا تخلطه مع Eureka الكويتية.\nممنوع روابط ظاهرة في النص. ممنوع Markdown.\n'

def _legacy_extract_store_names(text, limit=None):
    cap = MAX_STORES if limit is None else max(1, int(limit))
    names = []
    for o in text77_extract_store_offers(text or '', limit=cap):
        n = str(o.get('name') or '').strip()
        if n and n not in names:
            names.append(n)
    return names[:cap]

def legacy_v26_call_gemini(parts, system=LEGACY_TEXT_SEARCH_SYSTEM, max_results=None):
    limit = MAX_STORES if max_results is None else max(1, int(max_results))
    model = GEMINI_SEARCH_MODEL
    gemini_url = f'{GEMINI_BASE_URL}/{model}:generateContent'
    payload = {'systemInstruction': {'parts': [{'text': system + text77_market_instruction()}]}, 'contents': [{'role': 'user', 'parts': parts}], 'generationConfig': {'temperature': 0, 'maxOutputTokens': 2000}, 'tools': [{'google_search': {}}]}
    try:
        with GEMINI_STATS_LOCK:
            GEMINI_STATS['search_calls'] += 1
            print(f'LEGACY V26 CALL model={model} totals={GEMINI_STATS}')
        r = requests.post(gemini_url, params={'key': GEMINI_API_KEY}, json=payload, timeout=(5, GEMINI_SEARCH_TIMEOUT_SECONDS))
        if r.status_code >= 400:
            print(f'LEGACY V26 Gemini HTTP {r.status_code}: {r.text[:500]}')
            return ('', {})
        data = r.json()
        candidates = data.get('candidates') or []
        if not candidates:
            print(f'LEGACY V26 no candidates: {str(data)[:500]}')
            return ('', {})
        cand = candidates[0]
        text = ''.join((p.get('text', '') for p in cand.get('content', {}).get('parts', []))).strip()
        pairs = []
        m = re.search('(?im)^\\s*LINKS\\s*:\\s*(.+)$', text)
        if m:
            for part in re.split('[,،]+', m.group(1)):
                part = part.strip()
                if '=' in part:
                    name, dom = part.split('=', 1)
                    name, dom = (name.strip(), clean_domain(dom))
                    if name and '.' in dom:
                        pairs.append((name, dom))
            text = re.sub('(?im)^\\s*LINKS\\s*:.*$', '', text).strip()
        text = re.sub('https?://\\S+', '', text).replace('**', '').strip()
        metadata = cand.get('groundingMetadata', {}) or {}
        chunks = metadata.get('groundingChunks', []) or []
        uris = [(c.get('web') or {}).get('uri', '') for c in chunks]
        finals = resolve_all(uris[:16]) if uris else []
        records = []
        for i, chunk in enumerate(chunks[:16]):
            web = chunk.get('web') or {}
            raw_uri = web.get('uri', '')
            final_uri = finals[i] if i < len(finals) else raw_uri
            records.append({'title': web.get('title', ''), 'raw': raw_uri, 'url': final_uri or raw_uri})
        urls_map = {}
        used_urls = set()
        stores = _legacy_extract_store_names(text, limit)
        supports = metadata.get('groundingSupports', []) or []
        for store in stores:
            store_norm = normalize_name(store)
            for support in supports:
                segment = (support.get('segment') or {}).get('text', '')
                if store_norm and store_norm in normalize_name(segment):
                    for cidx in support.get('groundingChunkIndices', []) or []:
                        if 0 <= cidx < len(records):
                            url = records[cidx]['url']
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
                hay = f"{rec['title']} {rec['raw']} {rec['url']}".lower()
                if rec['url'] and key and (key in hay) and (rec['url'] not in used_urls):
                    urls_map[name] = rec['url']
                    used_urls.add(rec['url'])
                    break
        for store in stores:
            if store in urls_map:
                continue
            sn = normalize_name(store)
            for rec in records:
                if rec['url'] and sn and (sn in normalize_name(rec['title'])) and (rec['url'] not in used_urls):
                    urls_map[store] = rec['url']
                    used_urls.add(rec['url'])
                    break
        print({'legacy_stores': stores, 'legacy_links_pairs': pairs, 'grounding_chunks': len(chunks), 'resolved_buttons': list(urls_map)})
        return (text, dict(list(urls_map.items())[:max(limit, 4)]))
    except Exception as e:
        print(f'LEGACY V26 Gemini err {e}')
        return ('', {})

def legacy_v26_best_of_search(parts, max_results=None, merge_offers=False, merge_title=''):
    limit = MAX_STORES if max_results is None else max(1, int(max_results))
    market_snapshot = current_market()
    try:
        futs = [V26_SEARCH_POOL.submit(_run_with_market, market_snapshot, legacy_v26_call_gemini, parts, LEGACY_TEXT_SEARCH_SYSTEM, limit) for _ in range(SEARCH_RUNS)]
        results = _fast_tournament_results(futs, limit, GEMINI_SEARCH_TIMEOUT_SECONDS + 5)
    except Exception as e:
        print(f'LEGACY V26 best_of_search err {e}')
        return legacy_v26_call_gemini(parts, max_results=limit)
    results = [(tt, uu) for tt, uu in results if tt]
    if not results:
        return ('', {})
    scored = sorted(results, key=lambda x: v26_answer_score(x[0], x[1], limit), reverse=True)
    best_txt, best_urls = scored[0]
    merged_urls = dict(best_urls)
    for _, u in scored[1:]:
        for n, link in u.items():
            if n not in merged_urls and link not in merged_urls.values():
                merged_urls[n] = link
    merged_urls = dict(list(merged_urls.items())[:max(limit, 4)])
    if merge_offers:
        best_txt = _merge_v26_offer_text(scored, merge_title or product_title(best_txt, ''), limit)
    print({'legacy_v26_tournament': [v26_answer_score(tt, uu, limit) for tt, uu in scored], 'winner_stores': len(text77_extract_store_offers(best_txt, limit=limit)), 'total_links': len(merged_urls), 'merged_offers': bool(merge_offers)})
    return (best_txt, merged_urls)
US_STORE_PRIORITY = (('amazon.com', 'Amazon'), ('ebay.com', 'eBay'), ('walmart.com', 'Walmart'))
CHINA_STORE_PRIORITY = (('aliexpress.com', 'AliExpress'), ('temu.com', 'Temu'), ('alibaba.com', 'Alibaba'), ('shein.com', 'SHEIN'), ('dhgate.com', 'DHgate'), ('made-in-china.com', 'Made-in-China'), ('banggood.com', 'Banggood'), ('1688.com', '1688'), ('taobao.com', 'Taobao'), ('tmall.com', 'Tmall'), ('jd.com', 'JD'))

def _us_store_priority(name, url):
    hay = f"{name or ''} {url or ''}".lower()
    for idx, (domain, label) in enumerate(US_STORE_PRIORITY):
        if domain in hay or normalize_name(label) in normalize_name(hay):
            return idx
    return 99

def _china_store_priority(name, url):
    hay = f"{name or ''} {url or ''}".lower()
    for idx, (domain, label) in enumerate(CHINA_STORE_PRIORITY):
        if domain in hay or normalize_name(label) in normalize_name(hay):
            return idx
    return 99

def legacy_text_product_search(product, lang):
    cache_query = f'__TEXT79_MARKET_COVERAGE__::{product}'
    cached = cache_get(cache_query, lang)
    if cached:
        return cached
    m = current_market()
    market_name = m.get('country_name', 'Kuwait')
    local_cc = (m.get('country') or DEFAULT_COUNTRY).lower()
    local_hl = m.get('search_hl') or country_search_hl(local_cc)
    local_currencies = ', '.join(country_currency_codes(local_cc))
    local_tlds = ', '.join(country_tlds(local_cc))
    local_stores = priority_stores_for(product)
    local_store_hint = ', '.join(local_stores[:7]) if local_stores else 'the strongest specialist and marketplace stores in the country'
    total_cap = max(1, LENS_DIRECT_LOCAL_MAX + LENS_DIRECT_US_MAX + LENS_DIRECT_CN_MAX)
    soft = None

    def _attempt(primary, secondary=''):
        extra = f' وابحث أيضاً بالاسم الآخر لنفس المنتج: {secondary}.' if secondary else ''
        prompt = f'ابحث عن نفس المنتج بالضبط: {primary}.{extra} إذا كان اسم المنتج مكتوباً بلغة غير لغة المتجر، افهم الاسم التجاري المكافئ تلقائياً أثناء بحث Google. LOCAL SEARCH BOOST: في {market_name} ابحث بصياغة المستخدم + الاسم التجاري الإنجليزي + صياغة لغة السوق {local_hl}. استخدم إشارات السوق gl={local_cc} و ccTLD={local_tlds} والعملات المحلية {local_currencies}. ابدأ بالمتاجر القوية مثل {local_store_hint} ثم وسّع للمتاجر المحلية الصغيرة المفهرسة؛ القائمة ليست whitelist. ابحث تلقائياً في ثلاث مجموعات فقط وبالترتيب الإلزامي: أولاً متاجر {market_name} المحلية حتى {LENS_DIRECT_LOCAL_MAX}، ثم متاجر الولايات المتحدة حتى {LENS_DIRECT_US_MAX}، ثم المتاجر الصينية حتى {LENS_DIRECT_CN_MAX}. بالنسبة لأمريكا: ابحث بشكل طبيعي في المتاجر الأمريكية، وإذا ظهرت نتائج مطابقة فرتبها داخل القسم الأمريكي بهذه الأولوية فقط: Amazon ثم eBay ثم Walmart ثم باقي المتاجر الأمريكية. لا تفرض ظهور أي متجر إذا لم توجد نتيجة مطابقة. بالنسبة للصين ابحث مباشرة في AliExpress وTemu وAlibaba وSHEIN عندما توجد نتيجة مطابقة، ويمكن استخدام متاجر صينية أخرى. لا تعرض أي دولة رابعة. استبعد Heureka/heureka.cz/heureka.sk نهائياً ولا تعتبره متجراً محلياً. لا تجعل الأعداد حصصاً إلزامية؛ اعرض الموجود المطابق فقط. مهم جداً: لا تنه البحث قبل فحص الأسواق الثلاثة كلها. إذا كان نفس المنتج المطابق موجوداً في السوق المحلي أو أمريكا أو الصين فيجب أن يظهر على الأقل متجر واحد من ذلك السوق؛ لا تحذف سوقاً كاملاً بسبب أن سوقاً آخر أعاد نتائج أكثر أو أسرع. لكل نتيجة اذكر اسم المتجر، اسم المنتج المطابق، السعر الرقمي والعملة، واربطه بصفحة المنتج المباشرة. {TEXT77_lang_instr(lang)}'
        return legacy_v26_best_of_search([{'text': prompt}], total_cap, True, product)
    txt, urls = _attempt(product)
    if txt and (not is_no_result_answer(txt)) and text77_extract_store_offers(txt, limit=total_cap):
        if urls:
            cache_put(cache_query, lang, txt, urls)
            return (txt, urls)
        soft = (txt, {})
    _nonlatin = bool(re.search('[\\u0600-\\u06FF\\u0900-\\u097F\\u3040-\\u30FF\\u3400-\\u9FFF\\u0400-\\u04FF]', str(product or '')))
    if _nonlatin:
        alt = english_search_name(product) or ''
    elif local_hl == 'ar':
        alt = arabic_search_name(product) or ''
    else:
        alt = ''
    if alt and alt.strip().lower() != str(product).strip().lower():
        txt2, urls2 = _attempt(alt, product)
        if txt2 and (not is_no_result_answer(txt2)) and text77_extract_store_offers(txt2, limit=total_cap):
            if urls2:
                cache_put(cache_query, lang, txt2, urls2)
                return (txt2, urls2)
            if soft is None:
                soft = (txt2, {})
    return soft or ('', {})

def v26_text_search(product, lang):
    return legacy_text_product_search(product, lang)

def execute_service_search(from_number, service_desc, original_text, bot_id, lang):
    send_whatsapp_text(from_number, T(lang, 'searching', q=service_desc), bot_id)
    LAST_SEARCH[from_number] = {'product': service_desc}
    market_name = current_market().get('country_name', 'Kuwait')
    has_question = bool(re.search('[؟?]|هل |ليش |وش سبب|why |does |is it', original_text or ''))
    question_part = 'رسالة المستخدم الكاملة:\n' + str(original_text or '').strip()[:600] + '\n\nأولاً: إذا في رسالته سؤال فني (مثل: هل الطفح يخرب المكينة؟) أجب عنه بإيجاز في 2-3 أسطر قبل القائمة. ' if has_question and original_text and (original_text.strip() != service_desc.strip()) else ''
    prompt = f'{question_part}هذا طلب خدمة وليس منتجاً: {service_desc}. طبق الحالة 3 بالضبط: ابحث في Google وأعطني 5 مزودي خدمة على الأقل في {market_name} مع أرقام هواتفهم الظاهرة فعلاً في نتائج البحث، مرتبين من الأعلى تقييماً. اكتب كل مزود في سطر واحد فقط بهذا الشكل الحرفي بدون أي إضافات:\n🏆 [اسم المزود] (هاتف: [الرقم]) — [المنطقة أو التقييم باختصار]\n• [اسم المزود] (هاتف: [الرقم]) — [المنطقة أو التقييم باختصار]\nبدون روابط، بدون Markdown، بدون فقرات شرح بعد القائمة. {TEXT77_lang_instr(lang)}'
    txt, urls = ('', {})
    try:
        txt, urls = v26_best_of_search([{'text': prompt}])
        if not txt or is_no_result_answer(txt):
            txt, urls = text77_call_gemini([{'text': prompt}])
    except Exception as e:
        print(f'SERVICE SEARCH CRASH: {e}')
        txt = ''
    if not txt or is_no_result_answer(txt):
        send_whatsapp_text(from_number, T(lang, 'not_found'), bot_id)
        return
    send_service_result(from_number, txt, bot_id, lang, service_desc)

def _text_offer_item(offer, urls):
    name = str(offer.get('name') or '').strip()
    line = str(offer.get('line') or '').strip()
    url = match_url(name, urls or {}) or ''
    detail = re.sub('^(?:✅|🏆|•)\\s*', '', line).strip()
    if name:
        detail = re.sub(f'^{re.escape(name)}\\s*(?:—|–|-)\\s*', '', detail, flags=re.I).strip()
    return {'source': name, 'title': detail, 'link': url, 'price': detail}

def _text_offer_price_and_title(detail):
    text = re.sub('\\s+', ' ', str(detail or '')).strip()
    parts = re.split('\\s+(?:—|–|-)\\s+', text)
    if len(parts) >= 2 and _extract_numeric_price(parts[-1]) is not None:
        return (' — '.join(parts[:-1]).strip(), parts[-1].strip())
    has_currency = bool(re.search('\\b[A-Z]{3}\\b|US\\$|A\\$|C\\$|S\\$|HK\\$|NZ\\$|[$€£¥￥₹₩₺₽₪₴₸₾₼฿₫₱₦₵৳₲₭₮]|د\\.ك|ر\\.س|د\\.إ|ر\\.ق|ر\\.ع|د\\.ب|KD\\b|RMB\\b', text, re.I))
    if has_currency and _extract_numeric_price(text) is not None:
        return ('', text)
    return (text, '')

def _text_price_local(raw_price, market_rank, lang):
    raw = str(raw_price or '').strip()
    if not raw:
        return ''
    local_cur = (current_market().get('currency') or '').upper().strip()
    src = detect_currency_code(raw, local_cur if market_rank == 0 else 'USD' if market_rank == 1 else 'CNY' if market_rank == 2 else '', current_market().get('country') if market_rank == 0 else 'us' if market_rank == 1 else 'cn' if market_rank == 2 else '')
    if not src:
        if market_rank == 0:
            src = local_cur
        elif market_rank == 1:
            src = 'USD'
        elif market_rank == 2:
            src = 'CNY'
    if market_rank == 0 and (not src or src == local_cur):
        return format_lens_price(raw, None, lang, local_cur or src or None)
    numeric = None
    m = re.search(r'(?<!\d)(\d+(?:[.,]\d{1,3})?)(?!\d)', _normalize_price_chars(raw))
    if m:
        numeric = _normalize_price_token(m.group(1), src)
    if numeric is None:
        return raw
    converted = convert_to_local(numeric, src) if src else None
    if converted is None:
        return raw
    local_label = currency_label(lang)
    original = f'{format_price(numeric, src)} {src}'
    return f'{format_price(converted, local_cur)} {local_label} ({original})'

def send_text_lens_style_results(from_number, txt, urls, bot_id, lang, query, exclude_domains=None, exclude_urls=None, more_mode=False):
    exclude_domains = {str(x).lower() for x in exclude_domains or [] if x}
    exclude_urls = {str(x).strip() for x in exclude_urls or [] if x}
    total_cap = MORE_TOTAL_MAX if more_mode else max(1, LENS_DIRECT_LOCAL_MAX + LENS_DIRECT_US_MAX + LENS_DIRECT_CN_MAX)
    offers = text77_extract_store_offers(txt or '', limit=max(total_cap * 2, total_cap))
    candidates = []
    for offer in offers:
        item = _text_offer_item(offer, urls)
        if not item['link'] or not item['link'].startswith(('http://', 'https://')):
            continue
        _url = str(item.get('link') or '').strip()
        _dom = _more_result_domain(_url)
        if _url in exclude_urls or (_dom and _dom in exclude_domains):
            continue
        rank = result_market_rank(item)
        if rank == 99:
            print(f"TEXT UI MARKET REJECT: {item['source']} -> {item['link']}")
            continue
        item['market_rank'] = rank
        candidates.append(item)
    if not more_mode:
        candidates = _supplement_missing_markets(candidates, query, 'FIRST-TEXT')
        for _c in candidates:
            _c['market_rank'] = result_market_rank(_c)
    _offer_rows = [{'line': o.get('title') or '', 'name': o.get('source') or ''} for o in candidates]
    _tmp_urls = {o.get('source') or '': o.get('link') or '' for o in candidates}
    _skip_ai_relevance = _fast_relevance_confident(query, candidates)
    _kept_rows = filter_relevant_offers(query, _offer_rows, _tmp_urls, use_ai=not _skip_ai_relevance, mode='exact')
    if _skip_ai_relevance:
        print('TEXT RELEVANCE: strong exact-token evidence -> AI filter skipped')
    _kept_keys = {(r.get('name') or '', r.get('line') or '') for r in _kept_rows}
    candidates = [o for o in candidates if (o.get('source') or '', o.get('title') or '') in _kept_keys]
    candidates = _filter_confirmed_oos(candidates, 'TEXT')
    caps = {0: MORE_LOCAL_MAX, 1: MORE_US_MAX, 2: MORE_CN_MAX} if more_mode else {0: LENS_DIRECT_LOCAL_MAX, 1: LENS_DIRECT_US_MAX, 2: LENS_DIRECT_CN_MAX}
    selected, merchant_counts, seen_urls = ([], defaultdict(int), set())
    for rank in (0, 1, 2):
        taken = 0
        bucket = [x for x in candidates if x['market_rank'] == rank]
        if rank == 1:
            bucket.sort(key=lambda x: (-_findzia_match_score(query, x.get('title') or ''), _us_store_priority(x.get('source'), x.get('link')), int(x.get('position') or 999)))
        elif rank == 2:
            bucket.sort(key=lambda x: (-_findzia_match_score(query, x.get('title') or ''), _china_store_priority(x.get('source'), x.get('link')), int(x.get('position') or 999)))
        else:
            bucket.sort(key=lambda x: (-_findzia_match_score(query, x.get('title') or ''), int(x.get('position') or 999)))
        for item in bucket:
            try:
                host = urllib.parse.urlparse(item['link']).netloc.lower().split(':')[0]
                host = host[4:] if host.startswith('www.') else host
            except Exception:
                host = ''
            merchant = host or normalize_name(item['source'])
            url = (item.get('link') or '').strip()
            if not merchant or _canonical_result_url(url) in seen_urls:
                continue
            if merchant_counts[merchant] >= RESULTS_PER_STORE_MAX:
                continue
            merchant_counts[merchant] += 1
            seen_urls.add(_canonical_result_url(url))
            selected.append(item)
            taken += 1
            if taken >= caps.get(rank, 0):
                break
    if not selected:
        return False
    priced_rows = []
    for item in selected:
        raw_title, raw_price = _text_offer_price_and_title(item['title'])
        shown_price = _text_price_local(raw_price, item['market_rank'], lang) if raw_price else ''
        priced_rows.append((item, raw_title, shown_price))
    display_titles = [raw_title or query for _, raw_title, _ in priced_rows]
    translated = display_titles
    local_cc = (current_market().get('country') or DEFAULT_COUNTRY).lower()
    rank_cc = {0: local_cc, 1: 'us', 2: 'cn'}
    counts = {0: 0, 1: 0, 2: 0}
    sent_items = []
    for (item, _raw_title, shown_price), shown_title in zip(priced_rows, translated):
        rank = item['market_rank']
        flag = country_flag_emoji(rank_cc.get(rank, ''))
        store = _ui_plain_store_name(item['source'] or '', item.get('link') or '') or U(lang, 'store')
        title = _compact_ui_title(shown_title or query)
        body = _build_compact_card_body(flag, store, title, shown_price, lang)
        if not body:
            continue
        send_whatsapp_cta(from_number, body[:1000], item['link'], bot_id, store)
        counts[rank] += 1
        sent_items.append(item)
    if not sent_items:
        return False
    LAST_SEARCH[from_number] = {'product': query}
    print(f'TEXT LENS-STYLE SENT: {len(sent_items)} CTA; per_store_cap={RESULTS_PER_STORE_MAX}; buckets={counts}; caps={LENS_DIRECT_LOCAL_MAX}/{LENS_DIRECT_US_MAX}/{LENS_DIRECT_CN_MAX}; order=local->us->cn')
    _save_more_results_state(from_number, query, bot_id, lang, 'text', sent_items, reset=not more_mode)
    _send_more_results_choice(from_number, bot_id, lang)
    return True

def execute_product_search(from_number, product, bot_id, lang):
    WORKERS.submit(send_whatsapp_text, from_number, T(lang, 'searching', q=product), bot_id)
    try:
        txt, urls = v26_text_search(product, lang)
        if not txt:
            print('TEXT LEGACY V26 PATH EMPTY — no current-engine fallback by design')
    except Exception as e:
        print(f'TEXT SEARCH CRASH: {e}')
        txt, urls = ('', {})
    LAST_SEARCH[from_number] = {'product': product}
    if not txt or not text77_extract_store_offers(txt, limit=30):
        send_whatsapp_text(from_number, T(lang, 'not_found'), bot_id)
        return
    if not send_text_lens_style_results(from_number, txt, urls, bot_id, lang, product):
        send_whatsapp_text(from_number, T(lang, 'not_found'), bot_id)
        return
REQUEST_CLASSIFIER_SYSTEM = 'أنت مصنف نية شراء ذكي لبوت تسوق عالمي على واتساب. المستخدم قد يكتب بالعربية أو بأي لغة مدعومة.\nصنّف الرسالة بدقة وأجب بكلمة واحدة فقط بدون أي شرح: GENERIC أو SPECIFIC أو SERVICE أو NONE\n\nالمبدأ الأساسي:\n- لا تحكم حسب نوع الفئة وحدها (طعام/إلكترونيات/ملابس...). افهم هل المستخدم حدّد منتجاً بعينه أم ما زال يطلب فئة عامة.\n- GENERIC يعني أن العبارة تصف فئة/نوعاً عاماً ويمكن أن توجد عدة براندات أو منتجات مناسبة، لذلك الأفضل أن نعرض توصيات ذكية أولاً.\n- SPECIFIC يعني أن المستخدم حدّد براند أو موديل أو SKU أو اسم منتج تجاري واضح أو وصفاً شديد التحديد يكفي للبحث عن نفس المنتج مباشرة.\n\nGENERIC أمثلة:\nشاورما دجاج، برجر دجاج، حليب، رز، ماء، قهوة، شوكولاتة، شامبو، حفاضات، مضرب تنس، حذاء تنس للأطفال، لابتوب للدراسة، سماعة بلوتوث، قلاية هوائية، عطر رجالي، سيارة عائلية، مولد كهرباء.\nChicken shawarma, tennis racket, kids tennis shoes, laptop for university, protein bar, olive oil.\nإذا لم توجد ماركة/موديل واضحان وكانت هناك عدة خيارات ومنتجات محتملة، اختر GENERIC.\n\nSPECIFIC أمثلة:\nNabil Chicken Shawarma 400g، حليب المراعي كامل الدسم 1 لتر، Pepsi 330ml، Yonex EZONE 100، Wilson Blade 98 V9، iPhone 16 Pro 256GB، Nike Vapor Pro 2 Junior، Head & Shoulders Classic Clean 400ml.\nذكر ماركة مع نوع المنتج غالباً SPECIFIC حتى لو لم يذكر المقاس، مثل: حليب المراعي، شامبو Pantene، حذاء Adidas.\n\nSERVICE = طلب خدمة أو فني أو تصليح أو صيانة أو عامل وليس شراء منتج.\nأمثلة: كهربائي، فني تكييف، سباك، بنشر متنقل، تصليح غسالة، مكافحة حشرات.\n\nNONE = الرسالة ليست طلب شراء ولا خدمة: تحية، شكر، عتاب، مزح، اختبار، أو كلام موجه للبوت.\nأمثلة: هلا، شكراً، وينك، ليش ما ترد، تمام، ok، تجربة.\n\nقواعد الحسم:\n1) لا تعتبر الطعام أو التموينات SPECIFIC تلقائياً. «شاورما دجاج» GENERIC، بينما «Nabil Chicken Shawarma 400g» SPECIFIC.\n2) لا تعتبر كلمة واحدة SPECIFIC تلقائياً. «حليب» GENERIC، بينما «حليب المراعي 1 لتر» SPECIFIC.\n3) إذا توجد ماركة/موديل/SKU واضح = SPECIFIC.\n4) إذا الطلب فئة عامة بلا ماركة واضحة = GENERIC.\n5) إذا شككت بين GENERIC وSPECIFIC ولم توجد هوية تجارية واضحة، اختر GENERIC.\n6) أجب بكلمة التصنيف فقط.'
_REQUEST_CLASS_CACHE = {}
_REQUEST_CLASS_LOCK = threading.Lock()

def classify_request_type(query):
    q = ' '.join(str(query or '').split()).strip()
    if not q:
        return 'SPECIFIC'
    key = re.sub('\\s+', ' ', normalize_ar(q))[:150]
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
        print(f'REQUEST CLASSIFIER ({source}): {q!r} -> {verdict}')
        return verdict
    if is_service_request(q):
        return _remember('SERVICE', 'fast-service')
    verdict = ''
    try:
        raw, _ = text77_call_gemini([{'text': q}], system=REQUEST_CLASSIFIER_SYSTEM, use_search=False)
        up = (raw or '').upper()
        for label in ('SERVICE', 'GENERIC', 'SPECIFIC', 'NONE'):
            if re.search(f'\\b{label}\\b', up):
                verdict = label
                break
    except Exception as e:
        print(f'REQUEST CLASSIFIER AI ERR: {e}')
    if not verdict:
        if re.search('\\d', q) or len(q.split()) >= 4:
            verdict = 'SPECIFIC'
        else:
            verdict = 'GENERIC'
    return _remember(verdict, 'one-pass-ai' if verdict else 'fallback')
SERVICE_WORDS = ('فني', 'كهربائي', 'سباك', 'نجار', 'حداد', 'تصليح', 'اصلاح', 'إصلاح', 'صيانه', 'صيانة', 'تركيب', 'تمديد', 'معلم', 'مقاول', 'شركه تنظيف', 'شركة تنظيف', 'مكافحه', 'مكافحة', 'بنشر', 'ونش', 'سطحه', 'سطحة', 'غسيل سياره', 'غسيل سيارة', 'technician', 'electrician', 'plumber', 'repair', 'maintenance', 'installation', 'cleaning company', 'pest control', 'towing')

def is_service_request(text):
    q = normalize_ar(str(text or ''))
    return any((normalize_ar(w) in q for w in SERVICE_WORDS))
COMPARE_UI = {'ar': {'title': 'أفضل الخيارات', 'overall': 'الأفضل عموماً', 'quality': 'أفضل جودة', 'value': 'الأرخص', 'fourth': 'ميزة إضافية'}, 'en': {'title': 'Best options', 'overall': 'Best overall', 'quality': 'Best quality', 'value': 'Cheapest', 'fourth': 'Notable strength'}, 'fr': {'title': 'Comparatif des meilleurs choix', 'overall': 'Meilleur choix global', 'quality': 'Meilleure qualité', 'value': 'Meilleur rapport qualité-prix', 'fourth': 'Autre avantage important'}, 'es': {'title': 'Comparativa de las mejores opciones', 'overall': 'Mejor en general', 'quality': 'Mejor calidad', 'value': 'Mejor relación calidad-precio', 'fourth': 'Otra ventaja importante'}, 'pt': {'title': 'Comparação das melhores opções', 'overall': 'Melhor no geral', 'quality': 'Melhor qualidade', 'value': 'Melhor custo-benefício', 'fourth': 'Outra vantagem importante'}, 'tr': {'title': 'En iyi seçeneklerin karşılaştırması', 'overall': 'Genel olarak en iyi', 'quality': 'En iyi kalite', 'value': 'En iyi fiyat-performans', 'fourth': 'Diğer önemli avantaj'}, 'ru': {'title': 'Сравнение лучших вариантов', 'overall': 'Лучший в целом', 'quality': 'Лучшее качество', 'value': 'Лучшее соотношение цены и качества', 'fourth': 'Другое важное преимущество'}, 'zh': {'title': '最佳选择对比', 'overall': '综合最佳', 'quality': '品质最佳', 'value': '性价比最佳', 'fourth': '其他重要优势'}, 'hi': {'title': 'सर्वश्रेष्ठ विकल्पों की तुलना', 'overall': 'कुल मिलाकर सर्वश्रेष्ठ', 'quality': 'सर्वश्रेष्ठ गुणवत्ता', 'value': 'पैसे के हिसाब से सर्वोत्तम', 'fourth': 'एक और महत्वपूर्ण खूबी'}, 'ur': {'title': 'بہترین آپشنز کا موازنہ', 'overall': 'مجموعی طور پر بہترین', 'quality': 'بہترین معیار', 'value': 'قیمت کے لحاظ سے بہترین', 'fourth': 'ایک اور اہم خوبی'}}

def compare_ui(lang):
    code = str(lang or 'en').strip().lower().replace('_', '-').split('-')[0]
    if code in COMPARE_UI:
        return COMPARE_UI[code]
    base = COMPARE_UI['en']
    return {k: _dynamic_translate_ui(v, code) for k, v in base.items()}

def brand_compare_system(lang):
    ui = compare_ui(lang)
    lang_name = language_name_en(lang)
    return f"You are an expert product-comparison assistant similar to professional Best-Of review sites.\nThe user made a GENERIC product request without a specific brand. Compare 3-4 concrete options (brand + model/type) only.\n\nCRITICAL LANGUAGE RULE:\n- ALL human-readable text MUST be written ONLY in {lang_name}.\n- Do not use Arabic words unless {lang_name} is Arabic.\n- Brand names, model names, sizes and SKUs may remain in their normal original/Latin form.\n- Never mix interface languages in the same answer.\n\nUse EXACTLY this visible structure, with these localized labels:\n⚖️ {ui['title']} [category]\n\n🏆 {ui['overall']}: [brand + model] — [one short reason]\n\n💎 {ui['quality']}: [brand + model] — [one short reason]\n\n💰 {ui['value']}: [brand + model] — [one short reason]\n\n✨ [localized criterion relevant to this category]: [brand + model] — [one short reason]\n\nOPTIONS: [searchable brand model 1] | [searchable brand model 2] | [searchable brand model 3] | [searchable brand model 4]\n\nStrict rules:\n1) Leave one blank line between recommendations.\n2) Never output store names, availability, prices or shopping-result bullets here.\n3) For food, compare taste, quality, value and reviews.\n4) Never repeat the same model.\n5) OPTIONS is mandatory and MUST contain clean searchable product identities, preferably brand + exact model in their standard market spelling.\n6) No links and no Markdown.\n7) The OPTIONS line may stay in Latin script for brand/model names, but all descriptions and labels must be in {lang_name}.\n"
_COMPARE_LINE_RE = re.compile('^\\s*(🏆|💎|💰|✨)\\s*([^:：]*?)\\s*[:：]\\s*(.+?)(?:\\s*(?:—|–|-)\\s+(.*))?\\s*$')

def _compare_entries_from_text(txt):
    entries = []
    for line in (txt or '').splitlines():
        m = _COMPARE_LINE_RE.match(line.strip())
        if not m:
            continue
        product = ' '.join((m.group(3) or '').split()).strip()
        if not product or len(product) < 3:
            continue
        entries.append({'emoji': m.group(1), 'label': ' '.join((m.group(2) or '').split()).strip(), 'product': product, 'reason': ' '.join((m.group(4) or '').split()).strip()})
    return entries[:6]

def _options_from_compare_lines(txt):
    options = []
    for e in _compare_entries_from_text(txt):
        cand = e['product']
        if cand not in options:
            options.append(cand)
    return options[:6]

def _compare_entry_for_option(option, entries, index):
    no = normalize_ar(option).lower()
    for e in entries:
        ne = normalize_ar(e['product']).lower()
        if no and ne and (no in ne or ne in no):
            return e
    if 0 <= index < len(entries):
        return entries[index]
    return None

def _clean_pick_label(value):
    s = re.sub('\\s+', ' ', str(value or '')).strip()
    return s.strip('[](){}<>«»"\' ')

def _short_pick_title(value, max_chars=24):
    s = _clean_pick_label(value)
    if len(s) <= max_chars:
        return s
    out = []
    for word in s.split():
        candidate = ' '.join(out + [word])
        if len(candidate) > max_chars:
            break
        out.append(word)
    return ' '.join(out) if out else s[:max_chars].rstrip(' -_/.,')

def _recommendation_pick_search_query(original_query, picked):
    original = re.sub('\\s+', ' ', str(original_query or '')).strip()
    choice = _clean_pick_label(picked)
    if not choice:
        return original
    if not original:
        return choice
    cleaned = original
    for pat in ('^\\s*(?:ابي|أبي|اريد|أريد|ابغى|أبغى|احتاج|أحتاج)\\s+', '^\\s*(?:افضل|أفضل)\\s+', '^\\s*(?:دور لي|دوّر لي|ابحث لي|أبحث لي)\\s+(?:عن\\s+)?', '^\\s*(?:recommend|find|show me|i want|i need|best)\\s+'):
        cleaned = re.sub(pat, '', cleaned, flags=re.I).strip()
    if normalize_ar(choice).lower() in normalize_ar(original).lower():
        return original
    return ' '.join(f'{cleaned} {choice}'.split()[:24])

def ai_recommendation_pick_search_query(original_query, picked, lang='ar'):
    original = re.sub('\\s+', ' ', str(original_query or '')).strip()
    choice = _clean_pick_label(picked)
    if not choice:
        return original
    system = "You normalize a user's selected shopping recommendation into ONE high-precision product search query.\nReturn ONLY the final search query on one line, no labels, no explanation, no quotes.\nRules:\n- The selected option is authoritative. Keep its exact brand and model.\n- Add only the minimum product-category/context words from the original request that help shopping search accuracy.\n- Remove recommendation/question words such as best, recommend, compare, I want, show me.\n- Never turn it into a sentence or question.\n- Never add a different model, size, gender, generation or specification unless it was explicitly present in the selected option or original request.\n- Prefer the standard international/English product-category wording for search-engine accuracy while preserving brand/model exactly.\nExamples:\nOriginal: tennis racket | Pick: Yonex EZONE 100 -> Yonex EZONE 100 tennis racket\nOriginal: chaussures de tennis homme | Pick: ASICS Solution Speed FF 3 -> ASICS Solution Speed FF 3 men's tennis shoes\nOriginal: बच्चों का टेनिस रैकेट | Pick: Babolat Pure Aero Junior 25 -> Babolat Pure Aero Junior 25 junior tennis racket\n"
    user = f'Original generic request: {original}\nSelected recommendation: {choice}'
    try:
        txt, _ = text77_call_gemini([{'text': user}], system=system, use_search=False)
        q = re.sub('^[\\s\\"\'`]+|[\\s\\"\'`]+$', '', (txt or '').splitlines()[0].strip()) if txt else ''
        q = re.sub('^(?:SEARCH_QUERY|QUERY)\\s*:\\s*', '', q, flags=re.I).strip()
        if q and len(q) <= 180 and (normalize_ar(choice).lower() in normalize_ar(q).lower()):
            print(f'SMART PICK QUERY: original={original!r} picked={choice!r} -> {q!r}')
            return q
    except Exception as e:
        print(f'SMART PICK QUERY ERR: {e}')
    fallback = _recommendation_pick_search_query(original, choice)
    print(f'SMART PICK QUERY FALLBACK: {fallback!r}')
    return fallback

def _pick_description(original_query, lang='ar'):
    q = re.sub('\\s+', ' ', str(original_query or '')).strip()
    for pat in ('^\\s*(?:ابي|أبي|اريد|أريد|ابغى|أبغى|احتاج|أحتاج)\\s+', '^\\s*(?:افضل|أفضل)\\s+', '^\\s*(?:recommend|find|show me|i want|i need|best)\\s+'):
        q = re.sub(pat, '', q, flags=re.I).strip()
    return q[:68] or U(lang, 'recommended')

def run_brand_comparison(from_number, query, bot_id, lang):
    send_whatsapp_text(from_number, T(lang, 'compare_searching'), bot_id)
    lang_name = language_name_en(lang)
    prompt = f"Generic shopping request: {query}\nCurrent market: {current_market().get('country_name', 'Kuwait')}\nCompare 3-4 strong concrete options for this request. Output only in {lang_name}. {TEXT77_lang_instr(lang)}"
    txt = ''
    options = []
    for attempt in (1, 2):
        txt, _ = text77_call_gemini([{'text': prompt}], system=brand_compare_system(lang))
        if not txt:
            print(f'BRAND COMPARE ATTEMPT {attempt}: empty')
            continue
        m = re.search('(?im)^\\s*OPTIONS\\s*:\\s*(.+)$', txt)
        if m:
            options = [_clean_pick_label(o) for o in m.group(1).split('|') if _clean_pick_label(o)][:6]
            txt = re.sub('(?im)^\\s*OPTIONS\\s*:.*$', '', txt).strip()
        if not options:
            options = [_clean_pick_label(o) for o in _options_from_compare_lines(txt)]
            if options:
                print(f'BRAND COMPARE: OPTIONS recovered from lines -> {options}')
        if options:
            break
        print(f'BRAND COMPARE ATTEMPT {attempt}: no options')
    if not txt or not options:
        print('BRAND COMPARE FAILED -> normal search')
        return False
    entries = _compare_entries_from_text(txt)
    ui = compare_ui(lang)
    default_labels = [('🏆', ui['overall']), ('💰', ui['value']), ('💎', ui['quality']), ('✨', ui['fourth'])]
    PENDING_BRAND_PICKS[from_number] = {'options': options, 'original_query': query, 'bot_id': bot_id, 'lang': lang, 'ts': time.time()}
    rows = []
    used_titles = set()
    for i, o in enumerate(options):
        clean_o = _clean_pick_label(o)
        raw_token = base64.urlsafe_b64encode(clean_o.encode('utf-8')).decode('ascii').rstrip('=')
        row_id = f'pickq_{raw_token}'
        if len(row_id) > 190:
            row_id = f'pick_{i}'
        entry = _compare_entry_for_option(clean_o, entries, i)
        if entry and entry.get('label'):
            emoji, label = (entry['emoji'], entry['label'])
        else:
            emoji, label = default_labels[i] if i < len(default_labels) else ('⭐', U(lang, 'recommended'))
        title = _short_pick_title(f'{emoji} {label}', 24)
        if title in used_titles:
            title = _short_pick_title(f'{emoji} {label} {i + 1}', 24)
        used_titles.add(title)
        reason = (entry or {}).get('reason') or ''
        description = f'{clean_o} — {reason}' if reason else clean_o
        rows.append({'id': row_id, 'title': title, 'description': description[:72]})
    header = ''
    for line in (txt or '').splitlines():
        if line.strip().startswith('⚖️'):
            header = line.strip()
            break
    if not header:
        header = f"⚖️ {ui['title']}: {_pick_description(query, lang)}"
    body = f"{header}\n{T(lang, 'pick_prompt')}"
    send_whatsapp_list(from_number, body, rows, bot_id, T(lang, 'list_button'))
    print(f'BRAND COMPARE SENT: {options}')
    return True

def run_text_global_search(phone, item):
    activate_market(phone)
    bot_id = item['bot_id']
    lang = item['lang']
    query = item['query']
    send_whatsapp_text(phone, T(lang, 'global_searching'), bot_id)
    market_name = current_market().get('country_name', 'Kuwait')
    prompts = [f'ابحث عالمياً عن {query} في متاجر خارج {market_name} فقط. استبعد المتاجر داخل {market_name}. ابحث في Amazon.com وeBay وAliExpress وTemu وSHEIN وWalmart وغيرها. اعرض حتى {MAX_STORES} نتائج مختلفة بسعر رقمي ورابط منتج مباشر والعملة. {TEXT77_lang_instr(lang)}', f'Search worldwide for {english_search_name(query) or query} outside {market_name}. Find up to {MAX_STORES} trusted international store results with numeric price, currency, and direct product page. {TEXT77_lang_instr(lang)}']
    txt, urls = ('', {})
    for prompt in prompts:
        txt, urls = legacy_v26_best_of_search([{'text': prompt}], max_results=MAX_STORES)
        if txt and urls and text77_extract_store_offers(txt):
            break
    if not txt or not text77_extract_store_offers(txt):
        send_whatsapp_text(phone, T(lang, 'global_none'), bot_id)
        return
    if not urls:
        send_whatsapp_text(phone, txt, bot_id)
        return
    send_product_result(phone, txt, urls, bot_id, lang, query)

def run_text_similar_search(phone, item):
    activate_market(phone)
    bot_id = item['bot_id']
    lang = item['lang']
    query = item['query']
    send_whatsapp_text(phone, T(lang, 'similar_searching'), bot_id)
    base = short_query(re.sub('^.*?—\\s*', '', query).strip() or query) or short_query(query)
    base_other = english_search_name(base) if re.search('[\\u0600-\\u06FF]', base) else arabic_search_name(base)
    market_name = current_market().get('country_name', 'Kuwait')
    prompt = f'المنتج التالي غير متوفر محلياً: {base}. ' + (f'الاسم الآخر: {base_other}. ' if base_other else '') + f'ابحث بعمق في Google عن حتى {MAX_STORES} بدائل حقيقية مختلفة من نفس الفئة والاستخدام ومتوفرة الآن في متاجر {market_name} المحلية فقط. لكل نتيجة: اسم المتجر فقط — اسم البديل الفعلي — السعر الرقمي. اربط كل متجر بصفحة المنتج المباشرة. رتب الأرخص أولاً. {TEXT77_lang_instr(lang)}'
    txt, urls = legacy_v26_best_of_search([{'text': prompt}], max_results=MAX_STORES, merge_offers=True, merge_title=f'📦 بدائل مشابهة: {base}')
    local_urls = {n: u for n, u in (urls or {}).items() if u and (not text77_is_foreign_result({'link': u, 'source': n, 'title': n}))}
    if not txt or not text77_extract_store_offers(txt) or (not local_urls):
        send_whatsapp_text(phone, T(lang, 'similar_none'), bot_id)
        return
    result_type = send_product_result(phone, txt, local_urls, bot_id, lang, base)
    if result_type == 'none':
        send_whatsapp_text(phone, T(lang, 'similar_none'), bot_id)
GREETING_ONLY_FORMS = {'السلامعليكم', 'سلامعليكم', 'السلامعليكمورحمهاللهوبركاته', 'السلامعليكمورحمهالله', 'هلا', 'هلاوالله', 'اهلين', 'اهلا', 'اهلاوسهلا', 'مرحبا', 'مراحب', 'حياكم', 'حياكالله', 'صباحالخير', 'صباحالنور', 'مساءالخير', 'مساءالنور', 'شلونكم', 'شخباركم', 'شلونك', 'شخبارك', 'hi', 'hello', 'hey', 'goodmorning', 'goodevening', 'salam', 'assalamualaikum', 'hii', 'helloo', 'bonjour', 'salut', 'hola', 'buenosdias', 'olá', 'ola', 'bomdia', 'merhaba', 'привет', 'здравствуйте', '你好', '您好', 'नमस्ते', 'السلام', 'السلامعلیکم'}
THANKS_ONLY_FORMS = {'شكرا', 'شكرًا', 'شكرالك', 'شكرالكم', 'مشكور', 'مشكورين', 'تسلم', 'تسلمون', 'يعطيكالعافيه', 'يعطيكمالعافيه', 'جزاكاللهخير', 'جزاكماللهخير', 'اللهيعطيكالعافيه', 'ماقصرت', 'ماقصرتوا', 'thanks', 'thankyou', 'thx', 'thanku', 'ty', 'shukran', 'merci', 'gracias', 'obrigado', 'obrigada', 'teşekkürler', 'tesekkurler', 'спасибо', '谢谢', 'धन्यवाद', 'شکریہ'}
CONVERSATIONAL_HINTS = ('السلام', 'عليكم', 'صباح', 'مساء', 'هلا', 'مرحبا', 'حياك', 'لو سمحت', 'لوسمحت', 'شلون', 'شخبار', 'عساك', 'عساكم', 'كيفك', 'كيف الحال', 'اخبارك', 'عزكم الله', 'اعزكم الله', 'أعزكم الله', 'اكرمكم', 'أكرمكم', 'حشاكم', 'بلا مواخذه', 'بلا مؤاخذة', 'شكرا', 'مشكور', 'تسلم', 'يعطيك', 'جزاك', 'ما قصرت', 'وين', 'أين', 'اين', 'احصل', 'أحصل', 'القى', 'ألقى', 'الاقي', 'ألاقي', 'ابي', 'أبي', 'ابغى', 'أبغى', 'اريد', 'أريد', 'محتاج', 'ودي', 'تكفى', 'تكفون', 'ممكن', 'عندكم', 'عندك', 'بكم', 'كم سعر', 'وش سعر', 'شكم', 'دلوني', 'دلني', 'ساعدني', 'ساعدوني', 'ابحث لي', 'دور لي', 'دورلي', 'اشتري', 'أشتري', 'please', 'where', 'can i', 'could you', 'i need', 'i want', 'looking for', 'how much', 'help me', 'find me', 'thanks', 'thank', 'how are you', 'good morning', 'good evening')
PLEASANTRY_PATTERNS = ['السلام عليكم(?:\\s*ورحمة الله(?:\\s*وبركاته)?)?', 'و?عليكم السلام(?:\\s*ورحمة الله(?:\\s*وبركاته)?)?', 'صباح الخير', 'صباح النور', 'مساء الخير', 'مساء النور', 'هلا(?:\\s*والله)?', 'ا?هلا(?:\\s*وسهلا)?', 'مرحبا', 'حياكم?(?:\\s*الله)?', 'شلونك(?:م)?', 'شخبارك(?:م)?', '[أا]?عزكم الله', '[أا]كرمكم الله', 'حشاكم', 'بلا م[ؤو]اخذة?ه?', 'مع الشكر(?:\\s*الجزيل)?', 'و?شكرا(?:\\s*جزيلا)?(?:\\s*لكم?)?', 'مشكورين?', 'تسلمون?', 'يعطيكم?\\s*العافيه?ة?', 'جزاكم?\\s*الله\\s*خيرا?', 'الله يخليكم?', 'ما قصرتو?ا?', 'لو سمحتو?ا?', 'من فضلكم?', 'تكفون', 'تكفى', 'ممكن', 'ارجوكم?', 'أرجوكم?', 'رجاء', 'وين\\s*[أا]?حصله?ا?', 'وين\\s*[أا]?لقاه?ا?', 'وين\\s*[أا]لاقيه?ا?', 'وين\\s*موجوده?', '[أا]ين\\s*[أا]جده?ا?', '[أا]بي\\s*[أا]عرف\\s*وين', 'دلوني\\s*عليه?ا?', 'دلني\\s*عليه?ا?', '[أا]بي\\s*[أا]شتري', '[أا]بغى\\s*[أا]شتري', '[أا]ريد\\s*شراء', '[أا]ريد', '[أا]بغى', '[أا]بي', 'محتاجه?', 'دور\\s*لي', 'ابحثو?ا?\\s*لي', 'ساعدو?ني', '\\bhi\\b', '\\bhello\\b', '\\bhey\\b', '\\bplease\\b', '\\bthanks?(?:\\s*you)?\\b', '\\bthank\\s*you\\b', 'where\\s*(?:can|do)\\s*i\\s*(?:find|get|buy)\\s*(?:it|this)?', 'i\\s*(?:need|want)', 'looking\\s*for', 'can\\s*you\\s*(?:find|get)\\s*me', 'help\\s*me\\s*find']
_PLEASANTRY_RE = re.compile('|'.join(PLEASANTRY_PATTERNS), flags=re.IGNORECASE)
INTENT_PARSE_SYSTEM = 'أنت محلل طلبات لبوت تسوق على واتساب. المستخدم يكتب أحياناً جملة كاملة فيها تحية ودعاء وشكر مع طلبه.\nمهمتك استخراج المطلوب الحقيقي فقط.\nأرجع JSON فقط بدون أي شرح وبدون Markdown:\n{"intent":"search|service|greeting|thanks|chat","products":["اسم المنتج نظيفاً"]}\n\nقواعد إلزامية:\n- "search": المستخدم يريد منتجاً. احذف التحية والدعاء والشكر وعبارات مثل (وين أحصله، أبي أشتري، دلوني). أبقِ اسم المنتج وصفاته فقط.\n- افهم التعبير الإنشائي: حتى لو كانت الرسالة قصة أو شرحاً طويلاً أو وصف مشكلة، استنتج المنتج أو الخدمة المطلوبة بذكائك.\n  "عندي صراصير بالمطبخ ومتضايق منهم وايد" -> {"intent":"search","products":["مبيد صراصير"]}\n  "ولدي بيدخل الجامعة ومحتار وش أشتري له يذاكر عليه" -> {"intent":"search","products":["لابتوب للدراسة"]}\n  "السياره ما تشتغل الصبح وأحس البطارية خلصت" -> {"intent":"search","products":["خدمة تبديل بطارية سيارة"]}\n- المنتج الواحد = عنصر واحد في products حتى لو كانت الرسالة على عدة أسطر. لا تقسم الجملة الواحدة أبداً.\n- عدة منتجات مختلفة فعلاً = عدة عناصر.\n- "service": طلب فني/سباك/كهربائي/تصليح... ضع وصف الخدمة والمنطقة في products.\n- "greeting": تحية فقط بلا طلب. products فارغة.\n- "thanks": شكر فقط بلا طلب جديد. products فارغة.\n- "chat": فقط إذا لم يكن في الرسالة أي منتج أو خدمة أو حاجة يمكن استنتاجها إطلاقاً.\n'

def strip_pleasantries(text):
    cleaned = _PLEASANTRY_RE.sub(' ', text or '')
    cleaned = re.sub('[،,.!؟?]+', ' ', cleaned)
    return ' '.join(cleaned.split()).strip()

def parse_user_intent(user_text, lang):
    text = (user_text or '').strip()
    compact = re.sub('[^\\w\\u0600-\\u06FF]', '', normalize_ar(text))
    if compact in GREETING_ONLY_FORMS:
        return {'intent': 'greeting', 'products': []}
    if compact in THANKS_ONLY_FORMS:
        return {'intent': 'thanks', 'products': []}
    norm = normalize_ar(text)
    conversational = '؟' in text or '?' in text or any((normalize_ar(h) in norm for h in CONVERSATIONAL_HINTS))
    if not conversational and len(text.split()) <= 7:
        return {'intent': 'search', 'products': extract_products(text)}
    raw, _ = text77_call_gemini([{'text': text}], system=INTENT_PARSE_SYSTEM, use_search=False)
    try:
        data = json.loads(re.search('\\{.*\\}', raw or '', flags=re.S).group(0))
        intent = str(data.get('intent') or 'search').lower().strip()
        products = [str(p).strip() for p in data.get('products') or [] if str(p).strip()]
        if intent in ('greeting', 'thanks', 'chat') and (not products):
            return {'intent': intent, 'products': []}
        if intent in ('search', 'service') and products:
            return {'intent': intent, 'products': products[:6]}
    except Exception:
        print(f'TEXT77 INTENT PARSE FAIL: {raw!r}')
    cleaned = strip_pleasantries(text)
    if cleaned and len(cleaned) >= 3:
        return {'intent': 'search', 'products': [cleaned]}
    return {'intent': 'greeting' if not compact.strip() or any((g in compact for g in ('سلام', 'هلا', 'مرحبا'))) else 'chat', 'products': []}

def process_text_message(message, bot_id, onboarding_checked=False):
    from_number = 'unknown'
    try:
        from_number = message['from']
        load_user_preferences(from_number)
        user_text = message['text']['body']
        lang, _lang_changed = auto_language_from_text(from_number, user_text, persist=True)
        market_cmd = re.match('^\\s*market\\s+(.+?)\\s*$', user_text, flags=re.I)
        if market_cmd:
            target = market_cmd.group(1).strip()
            if _norm_market_name(target) in ('auto', 'automatic', 'phone', 'default', 'off'):
                m = clear_market_override(from_number)
                activate_market(from_number)
                send_whatsapp_text(from_number, f"✅ Market Auto — {country_flag_emoji(m.get('country'))} {m.get('country_name')} · {m.get('currency')}", bot_id)
                return
            cc = resolve_market_country(target)
            if not cc:
                send_whatsapp_text(from_number, f'⚠️ Unknown market: {target}. Try: Market Germany, Market Japan, Market France, or Market Auto.', bot_id)
                return
            m = set_market_override(from_number, cc)
            activate_market(from_number)
            send_whatsapp_text(from_number, f"🧪 Market Test — {country_flag_emoji(cc)} {m.get('country_name')} · {m.get('currency')}\nLocal results will now be tested for this market. Send any product.", bot_id)
            return
        ensure_market_from_phone(from_number, persist=True)
        activate_market(from_number)
        cmd = re.sub('[^\\w\\u0600-\\u06FF\\u0900-\\u097F]', '', user_text.strip().lower())
        if cmd in ('لغة', 'اللغة', 'غيراللغة', 'language', 'lang', 'changelanguage', 'langue', 'idioma', 'mudaridioma', 'dil', 'dildeğiştir', 'dildegistir', 'язык', 'сменитьязык', '语言', '切换语言', 'भाषा', 'زبان', 'زبانبدلیں'):
            send_language_choice(from_number, bot_id)
            return
        lang = USER_LANG.get(from_number, lang or 'en')
        if is_map_command(user_text):
            send_last_search_map(from_number, bot_id, lang)
            return
        pend = PENDING_IMAGES.pop(from_number, None)
        if pend and pend['images']:
            if len(pend['images']) == 1:
                img_msg = pend['images'][0]
                img = img_msg.setdefault('image', {})
                if not (img.get('caption') or '').strip():
                    img['caption'] = user_text.strip()
                process_single_image(img_msg, pend['bot_id'], lang)
            else:
                process_multi_images(pend['images'], from_number, pend['bot_id'], lang)
            return
        parsed = parse_user_intent(user_text, lang)
        intent = parsed.get('intent', 'search')
        if intent == 'greeting':
            send_whatsapp_text(from_number, T(lang, 'welcome_reply'), bot_id)
            return
        if intent == 'thanks':
            send_whatsapp_text(from_number, T(lang, 'thanks_reply'), bot_id)
            return
        if intent == 'chat':
            send_whatsapp_text(from_number, T(lang, 'welcome_reply'), bot_id)
            return
        products = [p for p in parsed.get('products') or [] if p.strip()] or extract_products(user_text)
        if intent == 'service' or is_service_request(products[0] if products else user_text):
            execute_service_search(from_number, products[0] if products else user_text, user_text, bot_id, lang)
            return
        if len(products) == 1:
            try:
                rtype = classify_request_type(products[0])
            except Exception as e:
                print(f'TEXT77 CLASSIFY CRASH for {products[0]!r}: {e} -> fallback GENERIC')
                rtype = 'GENERIC'
            if rtype == 'NONE':
                send_whatsapp_text(from_number, T(lang, 'chat_redirect'), bot_id)
                return
            if rtype == 'SERVICE':
                execute_service_search(from_number, products[0], user_text, bot_id, lang)
                return
            if rtype == 'GENERIC':
                try:
                    if run_brand_comparison(from_number, products[0], bot_id, lang):
                        return
                except Exception as e:
                    print(f'TEXT77 BRAND COMPARE CRASH: {e}')
            execute_product_search(from_number, products[0], bot_id, lang)
        else:
            run_cart_comparison(products, from_number, bot_id, lang)
    except Exception as e:
        print(f'TEXT77 PROCESS_TEXT_MESSAGE CRASH: {e} for {from_number}')
        try:
            lang = USER_LANG.get(from_number, 'ar')
            send_whatsapp_text(from_number, T(lang, 'not_found'), bot_id)
        except Exception:
            pass

def process_location_message(message, bot_id):
    from_number = message['from']
    load_user_preferences(from_number)
    market = ensure_market_from_phone(from_number, persist=True)
    lang = USER_LANG.get(from_number, 'ar')
    country = market.get('country_name') or market.get('country', '').upper()
    send_whatsapp_text(from_number, T(lang, 'market_from_phone', country=country), bot_id)
    route_pending_after_location(from_number)
WEB_API_ENABLED = env_bool('WEB_API_ENABLED', True)
WEB_GEO_ENABLED = env_bool('WEB_GEO_ENABLED', True)
WEB_GEO_TIMEOUT_SECONDS = max(0.8, min(4.0, float(os.environ.get('WEB_GEO_TIMEOUT_SECONDS', '2.0'))))
WEB_GEO_CACHE_TTL_SECONDS = max(3600, int(os.environ.get('WEB_GEO_CACHE_TTL_SECONDS', '86400')))
WEB_GEO_PROVIDER_URL = os.environ.get('WEB_GEO_PROVIDER_URL', 'https://ipwho.is/{ip}?fields=success,country_code').strip()
WEB_GEO_CACHE = {}
WEB_GEO_CACHE_LOCK = threading.Lock()
WEB_IMAGE_PROXY_ENABLED = env_bool('WEB_IMAGE_PROXY_ENABLED', True)
WEB_IMAGE_PROXY_TIMEOUT_SECONDS = max(3.0, min(12.0, float(os.environ.get('WEB_IMAGE_PROXY_TIMEOUT_SECONDS', '8'))))
WEB_IMAGE_PAGE_TIMEOUT_SECONDS = max(2.0, min(8.0, float(os.environ.get('WEB_IMAGE_PAGE_TIMEOUT_SECONDS', '4.5'))))
WEB_IMAGE_CACHE_TTL_SECONDS = max(3600, int(os.environ.get('WEB_IMAGE_CACHE_TTL_SECONDS', '86400')))
WEB_IMAGE_PROXY_MAX_BYTES = max(512000, min(8 * 1024 * 1024, int(os.environ.get('WEB_IMAGE_PROXY_MAX_BYTES', str(4 * 1024 * 1024)))))
WEB_IMAGE_CACHE = {}
WEB_IMAGE_CACHE_LOCK = threading.Lock()
WEB_STRICT_PRODUCT_PAGE = env_bool('WEB_STRICT_PRODUCT_PAGE', True)
WEB_REQUIRE_NUMERIC_PRICE = env_bool('WEB_REQUIRE_NUMERIC_PRICE', True)
WEB_REQUIRE_PRODUCT_IMAGE = env_bool('WEB_REQUIRE_PRODUCT_IMAGE', True)
WEB_VERIFY_PRODUCT_IMAGE = env_bool('WEB_VERIFY_PRODUCT_IMAGE', True)
WEB_PRODUCT_IMAGE_VERIFY_TIMEOUT_SECONDS = max(2.0, min(8.0, float(os.environ.get('WEB_PRODUCT_IMAGE_VERIFY_TIMEOUT_SECONDS', '4.0'))))
WEB_PRODUCT_VERIFY_TIMEOUT_SECONDS = max(2.5, min(8.0, float(os.environ.get('WEB_PRODUCT_VERIFY_TIMEOUT_SECONDS', '5.5'))))
WEB_PRODUCT_VERIFY_CACHE_TTL_SECONDS = max(300, int(os.environ.get('WEB_PRODUCT_VERIFY_CACHE_TTL_SECONDS', '1800')))
WEB_PRODUCT_VERIFY_CACHE = {}
WEB_PRODUCT_VERIFY_LOCK = threading.Lock()
WEB_MATCH_WHATSAPP_EXACT = env_bool('WEB_MATCH_WHATSAPP_EXACT', True)
# Text search parity is independent from the heavier image pipeline switches.
# Keep it on by default so a future Railway override cannot silently send web
# or iOS through a weaker text-only expansion path.
TEXT_SEARCH_WHATSAPP_PARITY = env_bool('TEXT_SEARCH_WHATSAPP_PARITY', True)
# Dense web parity keeps the authoritative WhatsApp final set, but also streams store probes in parallel.
WEB_TEXT_DENSE_PARITY = env_bool('WEB_TEXT_DENSE_PARITY', True)
WEB_TEXT_IMAGE_ENRICH_ENABLED = env_bool('WEB_TEXT_IMAGE_ENRICH_ENABLED', True)
WEB_TEXT_IMAGE_ENRICH_MAX_ROWS = max(1, min(20, int(os.environ.get('WEB_TEXT_IMAGE_ENRICH_MAX_ROWS', '14'))))
WEB_LOCAL_MAX = LENS_DIRECT_LOCAL_MAX
WEB_US_MAX = LENS_DIRECT_US_MAX
WEB_CN_MAX = LENS_DIRECT_CN_MAX
WEB_RESULT_CAPS = {0: WEB_LOCAL_MAX, 1: WEB_US_MAX, 2: WEB_CN_MAX}
WEB_LOCAL_STORE_PROBES = max(0, min(9, int(os.environ.get('WEB_LOCAL_STORE_PROBES', '6'))))
WEB_FAST_SKIP_PRODUCT_PAGE_VERIFY = env_bool('WEB_FAST_SKIP_PRODUCT_PAGE_VERIFY', True)
WEB_KEEP_PRICELESS_RESULTS = env_bool('WEB_KEEP_PRICELESS_RESULTS', True)
WEB_PRICE_ENRICH_ENABLED = env_bool('WEB_PRICE_ENRICH_ENABLED', True)
WEB_ASYNC_PRICE_ENRICH_ENABLED = env_bool('WEB_ASYNC_PRICE_ENRICH_ENABLED', True)
WEB_PRICE_ENRICH_MAX_ROWS = max(2, min(24, int(os.environ.get('WEB_PRICE_ENRICH_MAX_ROWS', '14'))))
WEB_PRICE_ENRICH_MAX_WAIT_SECONDS = max(2.0, min(12.0, float(os.environ.get('WEB_PRICE_ENRICH_MAX_WAIT_SECONDS', '6.5'))))
WEB_PRICE_ENRICH_SHOPPING_FALLBACK = env_bool('WEB_PRICE_ENRICH_SHOPPING_FALLBACK', True)
WEB_PRICE_ENRICH_SHOPPING_MAX = max(0, min(10, int(os.environ.get('WEB_PRICE_ENRICH_SHOPPING_MAX', '6'))))
WEB_ASYNC_PRICE_PAGE_WINDOW_SECONDS = max(1.0, min(WEB_PRICE_ENRICH_MAX_WAIT_SECONDS, float(os.environ.get('WEB_ASYNC_PRICE_PAGE_WINDOW_SECONDS', '3.5'))))
WEB_ASYNC_PRICE_SHARED_MARKETS = max(0, min(3, int(os.environ.get('WEB_ASYNC_PRICE_SHARED_MARKETS', '2'))))
WEB_ASYNC_PRICE_CACHE_TTL_SECONDS = max(30, min(1800, int(os.environ.get('WEB_ASYNC_PRICE_CACHE_TTL_SECONDS', '300'))))
WEB_ASYNC_PRICE_CACHE = {}
WEB_ASYNC_PRICE_CACHE_LOCK = threading.Lock()
if USE_V106_5_RESULT_PIPELINE:
    # Exact v106.5 extraction: return the engine winners immediately. Product
    # page image fetches, market expansion and price repair remain available to
    # the separate "more stores" flow, never to the initial search response.
    WEB_TEXT_DENSE_PARITY = False
    WEB_TEXT_IMAGE_ENRICH_ENABLED = False
    # Blocking price verification stays disabled. The separate asynchronous
    # hydrator may update already-visible cards without delaying first paint.
    WEB_PRICE_ENRICH_ENABLED = False
    WEB_REQUIRE_PRODUCT_IMAGE = False
WEB_API_MAX_QUERY_CHARS = max(40, min(500, int(os.environ.get('WEB_API_MAX_QUERY_CHARS', '220'))))
WEB_API_MAX_IMAGE_BYTES = max(512000, min(12 * 1024 * 1024, int(os.environ.get('WEB_API_MAX_IMAGE_BYTES', str(6 * 1024 * 1024)))))
# Raw iPhone HEIC uploads may be larger before server-side JPEG conversion.
WEB_API_RAW_IMAGE_MAX_BYTES = max(WEB_API_MAX_IMAGE_BYTES, min(20 * 1024 * 1024, int(os.environ.get('WEB_API_RAW_IMAGE_MAX_BYTES', str(16 * 1024 * 1024)))))
WEB_API_RATE_PER_MINUTE = max(5, min(120, int(os.environ.get('WEB_API_RATE_PER_MINUTE', '30'))))
WEB_STREAM_ENABLED = env_bool('WEB_STREAM_ENABLED', True)
WEB_IMAGE_SUPPLEMENT_WEAK_MARKETS = env_bool('WEB_IMAGE_SUPPLEMENT_WEAK_MARKETS', True)
WEB_IMAGE_TARGET_LOCAL = max(1, min(WEB_LOCAL_MAX, int(os.environ.get('WEB_IMAGE_TARGET_LOCAL', '3'))))
WEB_IMAGE_TARGET_US = max(1, min(WEB_US_MAX, int(os.environ.get('WEB_IMAGE_TARGET_US', '2'))))
WEB_IMAGE_TARGET_CN = max(1, min(WEB_CN_MAX, int(os.environ.get('WEB_IMAGE_TARGET_CN', '2'))))
WEB_STREAM_FAST_WAVE = env_bool('WEB_STREAM_FAST_WAVE', True)
WEB_STREAM_MARKET_TIMEOUT = max(3, min(12, int(os.environ.get('WEB_STREAM_MARKET_TIMEOUT_SECONDS', '6'))))
WEB_STREAM_STORE_FIFO = env_bool('WEB_STREAM_STORE_FIFO', True)
WEB_STREAM_STORE_TIMEOUT = max(3.5, min(9.0, float(os.environ.get('WEB_STREAM_STORE_TIMEOUT_SECONDS', '5.8'))))
WEB_STREAM_STORE_HTTP_TIMEOUT = max(3.0, min(WEB_STREAM_STORE_TIMEOUT, float(os.environ.get('WEB_STREAM_STORE_HTTP_TIMEOUT_SECONDS', '5.0'))))
WEB_STREAM_RESULTS_PER_STORE = max(1, min(2, int(os.environ.get('WEB_STREAM_RESULTS_PER_STORE', '1'))))
WEB_STREAM_MARKETPLACE_RESULTS_PER_STORE = max(1, min(4, int(os.environ.get('WEB_STREAM_MARKETPLACE_RESULTS_PER_STORE', '3'))))
WEB_MULTI_LISTING_MARKETPLACES = ('etsy.com', 'ebay.com', 'aliexpress.com', 'temu.com', 'shein.com', 'dhgate.com', 'amazon.com', 'alibaba.com', 'made-in-china.com', 'banggood.com')
WEB_STREAM_IMAGE_FINAL_MIN_RESULTS = max(2, min(10, int(os.environ.get('WEB_STREAM_IMAGE_FINAL_MIN_RESULTS', '5'))))
WEB_CHINA_ORGANIC_FIRST = env_bool('WEB_CHINA_ORGANIC_FIRST', True)
WEB_CHINA_ORGANIC_TIMEOUT = max(3.0, min(WEB_STREAM_STORE_TIMEOUT, float(os.environ.get('WEB_CHINA_ORGANIC_TIMEOUT_SECONDS', '4.8'))))
WEB_CHINA_GLOBAL_MAX_STORES = max(4, min(9, int(os.environ.get('WEB_CHINA_GLOBAL_MAX_STORES', '7'))))
WEB_CHINA_ORGANIC_NUM = max(3, min(10, int(os.environ.get('WEB_CHINA_ORGANIC_NUM', '8'))))
WEB_RATE_BUCKETS = defaultdict(deque)
WEB_RATE_LOCK = threading.Lock()
print(f'ANDROID/WEB PARITY exact={WEB_MATCH_WHATSAPP_EXACT} v106_pipeline={USE_V106_5_RESULT_PIPELINE} fast_lens={USE_FAST_LENS_PIPELINE} lens_wait={LENS_TURBO_MAX_WAIT_SECONDS}s empty_grace={LENS_TURBO_EMPTY_GRACE_SECONDS}s sparse_grace={LENS_TURBO_SPARSE_GRACE_SECONDS}s local_lane={LENS_LOCAL_LANE_TARGET}@{LENS_LOCAL_LANE_GRACE_SECONDS}s rescue_after={LENS_LOCAL_RESCUE_AFTER_SECONDS}s live_prices={WEB_ASYNC_PRICE_ENRICH_ENABLED} price_page_window={WEB_ASYNC_PRICE_PAGE_WINDOW_SECONDS}s shared_price_markets={WEB_ASYNC_PRICE_SHARED_MARKETS} strong_target={LENS_TURBO_STRONG_RESULT_TARGET} caps local/us/cn={WEB_LOCAL_MAX}/{WEB_US_MAX}/{WEB_CN_MAX} legacy_turbo_available={WEB_STREAM_FAST_WAVE} store_timeout={WEB_STREAM_STORE_TIMEOUT}s progressive={ANDROID_IMAGE_PROGRESSIVE} shopping_geo_guard={SHOPPING_GEO_GUARD}')

def _web_request_ip(request):
    forwarded = str(request.headers.get('x-forwarded-for') or '').split(',')[0].strip()
    if forwarded:
        return forwarded
    try:
        return request.client.host or 'unknown'
    except Exception:
        return 'unknown'

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
    lang = str(value or 'en').strip().lower().split('-')[0]
    return lang if lang in ('ar', 'en', 'de', 'fr', 'it', 'es', 'pt', 'tr', 'ru', 'ja', 'zh', 'ko', 'hi', 'ur', 'id', 'ms') else 'en'

def _web_market(country):
    raw = str(country or '').strip()
    cc = resolve_market_country(raw) if raw else None
    cc = (cc or DEFAULT_COUNTRY).lower()
    currencies = COUNTRY_CURRENCY_CODES.get(cc) or tuple(filter(None, (COUNTRY_CURRENCIES.get(cc, ''),)))
    return {'country': cc, 'country_name': COUNTRY_NAMES.get(cc, cc.upper()), 'currency': currencies[0] if currencies else '', 'currencies': list(currencies), 'search_hl': COUNTRY_SEARCH_HL.get(cc, 'en'), 'tlds': list(country_tlds(cc)), 'market_source': 'web_country'}

def _web_market_label(rank):
    return {0: 'local', 1: 'us', 2: 'china'}.get(rank, 'other')

def _web_is_http_url(value):
    try:
        u = urllib.parse.urlparse(str(value or '').strip())
        return u.scheme in ('http', 'https') and bool(u.netloc)
    except Exception:
        return False

def _web_image_cache_get(key):
    now = time.time()
    with WEB_IMAGE_CACHE_LOCK:
        item = WEB_IMAGE_CACHE.get(key)
        if item and now - float(item.get('ts') or 0) < WEB_IMAGE_CACHE_TTL_SECONDS:
            return item.get('value') or ''
    return ''

def _web_image_cache_set(key, value):
    now = time.time()
    with WEB_IMAGE_CACHE_LOCK:
        WEB_IMAGE_CACHE[key] = {'value': str(value or ''), 'ts': now}
        if len(WEB_IMAGE_CACHE) > 5000:
            stale = sorted(WEB_IMAGE_CACHE.items(), key=lambda kv: kv[1].get('ts', 0))[:1000]
            for old_key, _ in stale:
                WEB_IMAGE_CACHE.pop(old_key, None)

def _web_absolute_url(base_url, value):
    raw = str(value or '').strip()
    if not raw or raw.startswith(('data:', 'blob:', 'javascript:')):
        return ''
    try:
        return urllib.parse.urljoin(base_url or '', raw)
    except Exception:
        return raw if _web_is_http_url(raw) else ''

def _web_extract_product_image_from_html(html, base_url):
    try:
        soup = BeautifulSoup(html or '', 'html.parser')
    except Exception:
        return ''
    candidates = []
    for attrs in ({'property': 'og:image'}, {'property': 'og:image:url'}, {'name': 'twitter:image'}, {'property': 'twitter:image'}, {'itemprop': 'image'}):
        for tag in soup.find_all('meta', attrs=attrs):
            candidates.append(tag.get('content') or '')
    for link in soup.find_all('link', attrs={'rel': True}):
        rel = ' '.join(link.get('rel') or []).lower()
        if rel in ('image_src', 'preload'):
            href = link.get('href') or ''
            as_attr = str(link.get('as') or '').lower()
            if rel == 'image_src' or as_attr == 'image':
                candidates.append(href)
    for script in soup.find_all('script', attrs={'type': 'application/ld+json'})[:10]:
        text = (script.string or script.get_text() or '').strip()
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
                img = obj.get('image')
                if isinstance(img, str):
                    candidates.append(img)
                elif isinstance(img, list):
                    for x in img:
                        if isinstance(x, str):
                            candidates.append(x)
                        elif isinstance(x, dict):
                            candidates.append(x.get('url') or x.get('contentUrl') or '')
                elif isinstance(img, dict):
                    candidates.append(img.get('url') or img.get('contentUrl') or '')
                stack.extend(obj.values())
            elif isinstance(obj, list):
                stack.extend(obj[:12])
    if not candidates:
        for img in soup.find_all('img')[:30]:
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src') or img.get('data-original') or ''
            alt = str(img.get('alt') or '').lower()
            classes = ' '.join(img.get('class') or []).lower()
            if any((bad in (src or '').lower() for bad in ('sprite', 'icon', 'logo', '.svg'))):
                continue
            if 'logo' in alt or 'logo' in classes:
                continue
            candidates.append(src)
    seen = set()
    for raw in candidates:
        url = _web_absolute_url(base_url, raw)
        if not url or url in seen:
            continue
        seen.add(url)
        low = url.lower()
        if any((x in low for x in ('logo', 'icon', 'sprite'))):
            continue
        return url
    return ''

def _web_rescue_product_image(page_url):
    page_url = str(page_url or '').strip()
    if not _web_is_http_url(page_url):
        return ''
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

def _web_enrich_text_result_image(row):
    row = dict(row or {})
    existing = str(row.get('image') or '').strip()
    if existing and (not WEB_VERIFY_PRODUCT_IMAGE or _web_image_fetchable(existing)):
        row['image'] = _web_public_image_url(_web_unproxy_image_url(existing)) if _web_is_http_url(_web_unproxy_image_url(existing)) else existing
        return row
    url = str(row.get('url') or row.get('link') or '').strip()
    if not _web_is_http_url(url):
        return row
    try:
        snap = _web_verified_page_snapshot(url)
        image = _web_choose_verified_product_image(row, snap)
        if not image:
            image = _web_best_card_image('', url, rescue_page=True)
        if image:
            row['image'] = image
    except Exception as e:
        print(f"WEB TEXT IMAGE ENRICH ERR store={row.get('store')}: {e.__class__.__name__}")
    return row

def _web_enrich_text_result_images(rows):
    rows = [dict(x or {}) for x in (rows or [])]
    if not WEB_TEXT_IMAGE_ENRICH_ENABLED or not rows:
        return rows
    upto = min(len(rows), WEB_TEXT_IMAGE_ENRICH_MAX_ROWS)
    out = list(rows)
    with ThreadPoolExecutor(max_workers=min(8, upto)) as pool:
        jobs = [(i, pool.submit(_web_enrich_text_result_image, rows[i])) for i in range(upto)]
        for i, fut in jobs:
            try:
                out[i] = fut.result()
            except Exception:
                pass
    return out

def _web_has_product_image(row):
    raw = _web_unproxy_image_url(str((row or {}).get('image') or '').strip())
    return _web_is_http_url(raw)

def _web_require_product_image_rows(rows):
    rows = [dict(x or {}) for x in (rows or [])]
    if not WEB_REQUIRE_PRODUCT_IMAGE:
        return rows
    kept = [row for row in rows if _web_has_product_image(row)]
    dropped = len(rows) - len(kept)
    if dropped:
        print(f'WEB PRODUCT IMAGE REQUIRED: dropped={dropped} kept={len(kept)}')
    return kept

def _web_build_text_items(txt, urls, lang, query):
    total_cap = max(1, WEB_LOCAL_MAX + WEB_US_MAX + WEB_CN_MAX)
    offers = text77_extract_store_offers(txt or '', limit=max(total_cap * 2, total_cap))
    candidates = []
    for offer in offers:
        item = _text_offer_item(offer, urls)
        if not item['link'] or not item['link'].startswith(('http://', 'https://')):
            continue
        rank = result_market_rank(item)
        if rank == 99:
            continue
        item['market_rank'] = rank
        candidates.append(item)
    candidates = _supplement_missing_markets(candidates, query, 'WEB-TEXT')
    for item in candidates:
        item['market_rank'] = result_market_rank(item)
    candidates = [x for x in candidates if x.get('market_rank') in (0, 1, 2)]
    offer_rows = [{'line': o.get('title') or '', 'name': o.get('source') or ''} for o in candidates]
    tmp_urls = {o.get('source') or '': o.get('link') or '' for o in candidates}
    skip_ai = _fast_relevance_confident(query, candidates)
    kept_rows = filter_relevant_offers(query, offer_rows, tmp_urls, use_ai=not skip_ai, mode='exact')
    kept_keys = {(r.get('name') or '', r.get('line') or '') for r in kept_rows}
    candidates = [o for o in candidates if (o.get('source') or '', o.get('title') or '') in kept_keys]
    candidates = _filter_confirmed_oos(candidates, 'WEB-TEXT')
    caps = {0: WEB_LOCAL_MAX, 1: WEB_US_MAX, 2: WEB_CN_MAX}
    selected, merchant_counts, seen_urls = ([], defaultdict(int), set())
    for rank in (0, 1, 2):
        bucket = [x for x in candidates if x.get('market_rank') == rank]
        if rank == 1:
            bucket.sort(key=lambda x: (-_findzia_match_score(query, x.get('title') or ''), _us_store_priority(x.get('source'), x.get('link')), int(x.get('position') or 999)))
        elif rank == 2:
            bucket.sort(key=lambda x: (-_findzia_match_score(query, x.get('title') or ''), _china_store_priority(x.get('source'), x.get('link')), int(x.get('position') or 999)))
        else:
            bucket.sort(key=lambda x: (-_findzia_match_score(query, x.get('title') or ''), int(x.get('position') or 999)))
        taken = 0
        for item in bucket:
            url = str(item.get('link') or '').strip()
            try:
                host = urllib.parse.urlparse(url).netloc.lower().split(':')[0]
                host = host[4:] if host.startswith('www.') else host
            except Exception:
                host = ''
            merchant = host or normalize_name(item.get('source') or '')
            if not merchant or not url or _canonical_result_url(url) in seen_urls:
                continue
            if merchant_counts[merchant] >= RESULTS_PER_STORE_MAX:
                continue
            merchant_counts[merchant] += 1
            seen_urls.add(_canonical_result_url(url))
            selected.append(item)
            taken += 1
            if taken >= caps.get(rank, 0):
                break
    local_cc = (current_market().get('country') or DEFAULT_COUNTRY).lower()
    rank_cc = {0: local_cc, 1: 'us', 2: 'cn'}
    results = []
    for item in selected:
        rank = item['market_rank']
        raw_title, raw_price = _text_offer_price_and_title(item.get('title') or '')
        shown_price = _text_price_local(raw_price, rank, lang) if raw_price else ''
        title = _compact_ui_title(raw_title or query)
        store = _ui_plain_store_name(item.get('source') or '', item.get('link') or '') or U(lang, 'store')
        results.append({'market': _web_market_label(rank), 'market_rank': rank, 'country': rank_cc.get(rank, ''), 'flag': country_flag_emoji(rank_cc.get(rank, '')), 'store': store, 'title': title, 'price': shown_price, 'url': item.get('link') or '', 'image': item.get('thumbnail') or item.get('image') or '', 'match_score': round(_findzia_match_score(query, raw_title or title or query), 3)})
    if USE_V106_5_RESULT_PIPELINE or TEXT_SEARCH_WHATSAPP_PARITY:
        # Exact stopping point from main_v106.5: do not reopen product pages,
        # do not wait for image downloads, and do not remove valid winners just
        # because a retailer blocks image scraping.
        return results
    results = _web_enrich_text_result_images(results)
    return _web_require_product_image_rows(results)

def _web_brand_comparison(query, lang):
    lang_name = language_name_en(lang)
    prompt = f"Generic shopping request: {query}\nCurrent market: {current_market().get('country_name', 'Kuwait')}\nCompare 3-4 strong concrete options for this request. Output only in {lang_name}. {TEXT77_lang_instr(lang)}"
    txt, options = ('', [])
    for _ in (1, 2):
        txt, _urls = text77_call_gemini([{'text': prompt}], system=brand_compare_system(lang))
        if not txt:
            continue
        m = re.search('(?im)^\\s*OPTIONS\\s*:\\s*(.+)$', txt)
        if m:
            options = [_clean_pick_label(o) for o in m.group(1).split('|') if _clean_pick_label(o)][:6]
            txt = re.sub('(?im)^\\s*OPTIONS\\s*:.*$', '', txt).strip()
        if not options:
            options = [_clean_pick_label(o) for o in _options_from_compare_lines(txt)]
        if options:
            break
    if not txt or not options:
        return None
    cleaned = []
    for line in txt.splitlines():
        stripped = line.strip()
        if stripped.startswith('📦') or (stripped.startswith(('✅', '•')) and 'متوفر' in stripped):
            continue
        if 'متوفر عبر متجر' in stripped or ('متوفر في' in stripped and '📦' in stripped):
            continue
        cleaned.append(line)
    txt = re.sub('\\n{3,}', '\n\n', '\n'.join(cleaned)).strip()
    return {'summary': txt, 'options': options}

def _web_build_lens_items(lens, lang, caption=''):
    raw_matches = [m for m in lens.get('matches') or [] if (m.get('title') or '').strip()]
    if not USE_FAST_LENS_PIPELINE:
        lens_for_filter = dict(lens or {})
        lens_for_filter['matches'] = raw_matches
        raw_matches = _lens_ai_relevance_filter(lens_for_filter)
        if lens_for_filter.get('relevance_target'):
            lens['relevance_target'] = lens_for_filter['relevance_target']
    matches = [m for m in raw_matches if result_market_rank(m) != 99]
    if not matches:
        return []
    buckets = {0: [], 1: [], 2: []}
    for m in matches:
        rank = result_market_rank(m)
        if rank in buckets:
            buckets[rank].append(m)
    for rank in buckets:
        _anchor = str(lens.get('visual_identity') or lens.get('relevance_target') or (lens.get('chosen') or {}).get('title') or '')
        buckets[rank].sort(key=lambda m: (0 if m.get('exact') else 1, 0 if m.get('section') == 'visual_matches' else 1, -_findzia_match_score(_anchor, m.get('title') or '') if _anchor else 0, 0 if _lens_has_price(m) else 1, int(m.get('position') or 999), _us_store_priority(m.get('source'), m.get('link')) if rank == 1 else _china_store_priority(m.get('source'), m.get('link')) if rank == 2 else 99))
        cap = {0: WEB_LOCAL_MAX, 1: WEB_US_MAX, 2: WEB_CN_MAX}.get(rank, 0)
        probe_n = max(cap + 2, cap)
        head = _filter_confirmed_oos(buckets[rank][:probe_n], f'WEB-LENS-{rank}')
        buckets[rank] = head + buckets[rank][probe_n:]

    def merchant_key(m):
        url = (m.get('link') or '').strip()
        source = re.sub('\\s+', ' ', (m.get('source') or '').strip().lower())
        try:
            host = urllib.parse.urlparse(url).netloc.lower().split(':')[0]
            host = host[4:] if host.startswith('www.') else host
        except Exception:
            host = ''
        known = ('shein.com', 'aliexpress.com', 'temu.com', 'alibaba.com', '1688.com', 'taobao.com', 'tmall.com', 'amazon.com', 'ubuy.com', 'westelm.com', 'hm.com', 'wayfair.com')
        for d in known:
            if host == d or host.endswith('.' + d) or d in source:
                return d
        return host or re.sub('[^a-z0-9]+', '', source) or source
    caps = {0: WEB_LOCAL_MAX, 1: WEB_US_MAX, 2: WEB_CN_MAX}
    selected, seen_urls, merchant_counts = ([], set(), defaultdict(int))
    for rank in (0, 1, 2):
        taken = 0
        for m in buckets[rank]:
            url = (m.get('link') or '').strip()
            try:
                host = urllib.parse.urlparse(url).netloc.lower()
            except Exception:
                host = ''
            if not (url.startswith('http') and host and ('google.' not in host)):
                continue
            merchant = merchant_key(m)
            if _canonical_result_url(url) in seen_urls or merchant_counts[merchant] >= RESULTS_PER_STORE_MAX:
                continue
            selected.append(m)
            seen_urls.add(_canonical_result_url(url))
            merchant_counts[merchant] += 1
            taken += 1
            if taken >= caps.get(rank, 0) or len(selected) >= LENS_DIRECT_MAX_CTA:
                break
        if len(selected) >= LENS_DIRECT_MAX_CTA:
            break
    if USE_FAST_LENS_PIPELINE:
        # Market caps are priorities, not a reason to throw away good cards.
        # If China (or another market) has no result, backfill its unused slots
        # from the remaining LOCAL/US Lens matches up to the same total cap.
        target_total = min(LENS_DIRECT_MAX_CTA, sum(caps.values()))
        before_backfill = len(selected)
        if len(selected) < target_total:
            for rank in (0, 1, 2):
                for m in buckets[rank]:
                    url = (m.get('link') or '').strip()
                    try:
                        host = urllib.parse.urlparse(url).netloc.lower()
                    except Exception:
                        host = ''
                    if not (url.startswith('http') and host and ('google.' not in host)):
                        continue
                    merchant = merchant_key(m)
                    canonical = _canonical_result_url(url)
                    if canonical in seen_urls or merchant_counts[merchant] >= RESULTS_PER_STORE_MAX:
                        continue
                    selected.append(m)
                    seen_urls.add(canonical)
                    merchant_counts[merchant] += 1
                    if len(selected) >= target_total:
                        break
                if len(selected) >= target_total:
                    break
        if len(selected) > before_backfill:
            print(f'LENS UNUSED-MARKET BACKFILL results={before_backfill}->{len(selected)} target={target_total}')
    selected = _fill_prices_from_existing_lens_pool(selected, raw_matches)
    display_titles = ([(m.get('title') or '').strip() for m in selected] if USE_FAST_LENS_PIPELINE else translate_ui_titles([(m.get('title') or '').strip() for m in selected], lang))
    local_cc = (current_market().get('country') or DEFAULT_COUNTRY).lower()
    rank_cc = {0: local_cc, 1: 'us', 2: 'cn'}
    results = []
    for m, display_title in zip(selected, display_titles):
        rank = result_market_rank(m)
        cc = rank_cc.get(rank, '')
        shown_price = _lens_price_text_local(m, rank, lang)
        results.append({'market': _web_market_label(rank), 'market_rank': rank, 'country': cc, 'flag': country_flag_emoji(cc), 'store': _ui_plain_store_name(m.get('source') or '', m.get('link') or '') or U(lang, 'store'), 'title': _compact_ui_title(display_title or m.get('title') or ''), 'price': shown_price, 'price_pending': not bool(shown_price), 'price_verified': bool(shown_price), 'url': (m.get('link') or '').strip(), 'image': m.get('thumbnail') or m.get('image') or ''})
    return results

_WEB_CLASSIFICATION_LABELS = {
    'ar': ('مطابق للمنتج', 'منتجات مشابهة'),
    'en': ('Exact matches', 'Similar products'),
    'de': ('Exakte Treffer', 'Ähnliche Produkte'),
    'fr': ('Correspondances exactes', 'Produits similaires'),
    'it': ('Corrispondenze esatte', 'Prodotti simili'),
    'es': ('Coincidencias exactas', 'Productos similares'),
    'pt': ('Correspondências exatas', 'Produtos semelhantes'),
    'tr': ('Tam eşleşmeler', 'Benzer ürünler'),
    'ru': ('Точные совпадения', 'Похожие товары'),
    'ja': ('完全一致', '類似商品'),
    'zh': ('完全匹配', '相似商品'),
    'ko': ('정확히 일치', '유사 상품'),
    'hi': ('सटीक मिलान', 'मिलते-जुलते उत्पाद'),
    'ur': ('بالکل مماثل', 'ملتے جلتے مصنوعات'),
    'id': ('Kecocokan persis', 'Produk serupa'),
    'ms': ('Padanan tepat', 'Produk serupa'),
}

_WEB_CLASSIFICATION_SEO_TAIL = re.compile(
    r'\b(?:order|buy|shop|available|sale|price|prices|offers?)\s+(?:it\s+)?(?:now\s+)?(?:online|in)\b.*$',
    re.I,
)
_WEB_CLASSIFICATION_COUNTRY_TAIL = re.compile(
    r'\s+(?:(?:in|at|from|for\s+sale\s+in)\s+)?(?:kuwait|ksa|saudi\s+arabia|saudi|uae|united\s+arab\s+emirates|qatar|oman|bahrain|kw)\s*$',
    re.I,
)
_WEB_CLASSIFICATION_MERCHANT_PREFIX = re.compile(
    r'^\s*(?:amazon(?:\.[a-z.]+)?|walmart|ebay|noon|ubuy(?:\s+kuwait)?|aliexpress|temu|etsy|best\s*buy|xcite(?:\s+alghanim)?)\s*[:\-–—]\s*',
    re.I,
)
_WEB_CLASSIFICATION_MEASUREMENT = re.compile(
    r'(?<![a-z\u0600-\u06ff])\d+(?:[.,]\d+)?\s*(?:gb|tb|mb|kb|kg|mg|g|lb|lbs|oz|ml|cl|cm|mm|inch|inches|ft|mah|hz|khz|mhz|ghz|mp|pcs|pc|مل|مم|سم|غرام|جرام|كجم|كيلو)(?![a-z\u0600-\u06ff])',
    re.I,
)
_WEB_CLASSIFICATION_GENERIC_CLUSTER = {
    'product', 'products', 'item', 'items', 'original', 'new', 'women', 'woman', 'men', 'man',
    'body', 'spray', 'mist', 'perfume', 'shoes', 'shoe', 'watch', 'watches', 'phone', 'phones',
    'online', 'shop', 'store', 'buy', 'best', 'price', 'sale', 'for', 'with', 'the', 'and',
    'منتج', 'منتجات', 'اصلي', 'أصلي', 'جديد', 'بخاخ', 'جسم', 'عطر', 'حذاء', 'احذية', 'أحذية',
    'ساعة', 'ساعات', 'هاتف', 'هواتف', 'شراء', 'متجر', 'سعر',
}

def _web_clean_classification_identity(value):
    """Remove merchant/location SEO decoration from captured product text."""
    text = re.sub(r'\s+', ' ', str(value or '')).strip(' \t\r\n-|•–—')
    if not text:
        return ''
    # Lens identities frequently arrive as ``product | merchant | section``.
    # Only the product segment is useful for Exact/Similar classification.
    text = next((part.strip() for part in re.split(r'\s*[|•]\s*', text) if part.strip()), text)
    text = _WEB_CLASSIFICATION_MERCHANT_PREFIX.sub('', text).strip(' \t\r\n-|•–—')
    text = _WEB_CLASSIFICATION_SEO_TAIL.sub('', text).strip(' \t\r\n-|•–—')
    text = _WEB_CLASSIFICATION_COUNTRY_TAIL.sub('', text).strip(' \t\r\n-|•–—')
    return re.sub(r'\s+', ' ', text).strip()

def _web_classification_numbers(value):
    """Keep standalone generation/size numbers, including one-digit models."""
    raw = normalize_ar(str(value or '')).lower()
    raw = re.sub(r'\b\d+(?:[.,]\d+)?\s*(?:kwd|kd|usd|sar|aed|qar|omr|bhd|cny|rmb|eur|gbp)\b', ' ', raw, flags=re.I)
    # Measurements describe capacity/size, not a product generation.  Removing
    # them keeps ``Ultra 2`` significant while preventing ``125 ml`` from
    # turning a genuine match into Similar merely because spacing differs.
    raw = _WEB_CLASSIFICATION_MEASUREMENT.sub(' ', raw)
    return set(re.findall(r'(?<![a-z\u0600-\u06ff])\d{1,5}(?![a-z\u0600-\u06ff])', raw))

def _web_classification_comparable(value):
    """Normalize measurement formatting before existing mismatch checks."""
    return re.sub(r'\s+', ' ', _WEB_CLASSIFICATION_MEASUREMENT.sub(' ', str(value or ''))).strip()

def _web_classification_script(value):
    text = str(value or '')
    arabic = len(re.findall(r'[\u0600-\u06ff]', text))
    latin = len(re.findall(r'[a-z]', text, flags=re.I))
    if arabic > latin:
        return 'arabic'
    if latin > arabic:
        return 'latin'
    return 'mixed'

def _web_classification_peer_score(left, right):
    left_cmp = _web_classification_comparable(left)
    right_cmp = _web_classification_comparable(right)
    if not left_cmp or not right_cmp or _findzia_hard_product_mismatch(left_cmp, right_cmp):
        return 0.0
    left_tokens = _findzia_lexical_tokens(left_cmp)
    right_tokens = _findzia_lexical_tokens(right_cmp)
    distinctive = (left_tokens & right_tokens) - _WEB_CLASSIFICATION_GENERIC_CLUSTER
    model_overlap = _findzia_model_tokens(left) & _findzia_model_tokens(right)
    if not distinctive and not model_overlap:
        return 0.0
    return max(_findzia_match_score(left_cmp, right_cmp), _findzia_match_score(right_cmp, left_cmp))

def _web_classification_anchor(identity, results):
    """Choose a clean identity, or the strongest repeated result cluster."""
    clean_identity = _web_clean_classification_identity(identity)
    titles = [_web_clean_classification_identity((row or {}).get('title') or '') for row in (results or [])]
    titles = [title for title in titles if title]
    if not titles:
        return clean_identity

    identity_script = _web_classification_script(clean_identity)
    title_scripts = [_web_classification_script(title) for title in titles]
    same_script = sum(1 for script in title_scripts if script == identity_script)
    clean_identity_cmp = _web_classification_comparable(clean_identity)
    direct_scores = [_findzia_match_score(clean_identity_cmp, _web_classification_comparable(title)) for title in titles] if clean_identity_cmp else []
    # Trust the cleaned Lens identity when the cards use the same language and
    # at least one card actually supports it.  This is the normal fast path.
    if clean_identity and same_script and max(direct_scores or [0.0]) >= 0.50:
        return clean_identity

    # If Lens supplied a generic Arabic identity while cards are English (or
    # vice versa), use the most cohesive repeated product cluster as the anchor.
    best_title = titles[0]
    best_rank = (-1, -1.0, -1, 0)
    for index, title in enumerate(titles):
        peers = []
        for other in titles:
            score = _web_classification_peer_score(title, other)
            if score >= 0.50:
                peers.append(score)
        rank = (len(peers), sum(peers), len(_findzia_model_tokens(title)), -index)
        if rank > best_rank:
            best_rank = rank
            best_title = title
    # A single uncorroborated title must not replace a usable Lens identity.
    if best_rank[0] < 2 and clean_identity:
        return clean_identity
    return best_title

def _web_captured_result_is_exact(identity, title):
    """Classify one already-captured card without filtering or doing I/O."""
    identity = _web_clean_classification_identity(identity)
    title = _web_clean_classification_identity(title)
    identity_cmp = _web_classification_comparable(identity)
    title_cmp = _web_classification_comparable(title)
    if not identity_cmp or not title_cmp or _findzia_hard_product_mismatch(identity_cmp, title_cmp):
        return False
    identity_models = _findzia_model_tokens(identity)
    title_models = _findzia_model_tokens(title)
    if identity_models:
        # A model-bearing photographed identity is exact only when the card
        # explicitly carries that same model.  Other models remain visible in
        # Similar; nothing is discarded.
        return bool(identity_models & title_models)
    identity_numbers = _web_classification_numbers(identity)
    title_numbers = _web_classification_numbers(title)
    if identity_numbers and (not title_numbers or not identity_numbers & title_numbers):
        return False
    # Without a model number, require strong coverage of the post-capture
    # identity/consensus anchor.  The result list itself is never changed.
    return _findzia_match_score(identity_cmp, title_cmp) >= 0.52

def _web_attach_captured_result_sections(payload, lang):
    """Add Exact/Similar views while preserving ``results`` byte-for-byte."""
    out = dict(payload or {})
    original_results = out.get('results')
    results = list(original_results or [])
    identity = str(out.get('query') or '').strip()
    classification_anchor = _web_classification_anchor(identity, results)
    exact_results = []
    similar_results = []
    classified_results = []
    for original in results:
        row = dict(original or {})
        if _web_captured_result_is_exact(classification_anchor, row.get('title') or ''):
            row['match_type'] = 'exact'
            row['result_section'] = 'exact'
            row['best_price_eligible'] = True
            exact_results.append(row)
        else:
            row['match_type'] = 'similar'
            row['result_section'] = 'similar'
            row['best_price_eligible'] = False
            similar_results.append(row)
        classified_results.append(row)
    exact_label, similar_label = _WEB_CLASSIFICATION_LABELS.get(lang, _WEB_CLASSIFICATION_LABELS['en'])
    # Keep the exact same original object/list under the legacy key so old web
    # and app clients continue to receive every card in the original order.
    out['results'] = original_results if original_results is not None else []
    out['exact_results'] = exact_results
    out['similar_results'] = similar_results
    out['all_results'] = classified_results
    out['result_sections'] = [
        {'id': 'exact', 'title': exact_label, 'collapsed': False, 'best_price_eligible': True, 'count': len(exact_results), 'results': exact_results},
        {'id': 'similar', 'title': similar_label, 'collapsed': bool(exact_results), 'best_price_eligible': False, 'count': len(similar_results), 'results': similar_results},
    ]
    out['exact_count'] = len(exact_results)
    out['similar_count'] = len(similar_results)
    out['classification_anchor'] = classification_anchor
    print(f'WEB POST-CAPTURE CLASSIFICATION total={len(results)} exact={len(exact_results)} similar={len(similar_results)} anchor={classification_anchor[:90]!r}')
    return out

def _web_fallback_product_items(txt, urls, lang, query):
    offers = extract_store_offers(txt or '')
    rows = []
    for offer in offers[:MAX_STORES]:
        name = offer.get('name') or ''
        url = match_url(name, urls or {})
        if not is_direct_store_url(url):
            continue
        detail = re.sub('^(?:✅|🏆|•)\\s*', '', offer.get('line') or '').strip()
        if name:
            detail = re.sub(f'^{re.escape(name)}\\s*(?:—|–|-)\\s*', '', detail, flags=re.I).strip()
        title, raw_price = _text_offer_price_and_title(detail)
        probe = {'source': name, 'title': title or detail, 'link': url}
        rank = result_market_rank(probe)
        if rank == 0:
            cc = (current_market().get('country') or DEFAULT_COUNTRY).lower()
        elif rank == 1:
            cc = 'us'
        elif rank == 2:
            cc = 'cn'
        else:
            cc = ''
        rows.append({'market': _web_market_label(rank), 'market_rank': rank, 'country': cc, 'flag': country_flag_emoji(cc) if cc else '', 'store': _ui_plain_store_name(name, url) or U(lang, 'store'), 'title': _compact_ui_title(title or query), 'price': _text_price_local(raw_price, rank, lang) if raw_price and rank in (0, 1, 2) else raw_price, 'url': url, 'image': ''})
    return rows

def _web_stream_event(payload):
    return (json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
_WEB_BAD_PRICE_TERMS = ('per month', 'monthly', 'month plan', 'installment', 'instalment', 'pay monthly', 'monthly payment', 'emi', 'finance payment', 'قسطي', 'قسط', 'اقساط', 'أقساط', 'شهري')
_WEB_WHOLESALE_TERMS = ('minimum order', 'min order', 'moq', 'wholesale', 'bulk order', 'fob', 'per piece', '/piece', 'piece price', 'sample price', 'supplier', 'حد ادنى للطلب', 'الحد الأدنى للطلب', 'جملة', 'بالجملة')

def _web_fast_price_guard(row):
    row = dict(row or {})
    blob = ' '.join((str(row.get(k) or '') for k in ('title', 'price', '_offer_meta', 'store', 'source'))).lower()
    if any((term in blob for term in _WEB_BAD_PRICE_TERMS)):
        return False
    if any((term in blob for term in _WEB_WHOLESALE_TERMS)):
        return False
    return True

def _web_fast_finalize_rows(rows, lang):
    market_snapshot = dict(current_market())
    out = []
    for row in list(rows or []):
        row = dict(row or {})
        url = str(row.get('url') or row.get('link') or '').strip()
        if not url or not _web_is_direct_product_page_url(url, row.get('store') or row.get('source') or ''):
            continue
        if not _web_fast_price_guard(row):
            print(f"WEB FAST PRICE-GUARD BLANK store={row.get('store') or row.get('source')} title={(row.get('title') or '')[:90]}")
            row['price'] = ''
        rank = row.get('market_rank')
        if rank not in (0, 1, 2):
            rank = result_market_rank({'link': url, 'source': row.get('store') or row.get('source'), 'title': row.get('title')})
        row['market_rank'] = rank
        existing = str(row.get('price') or '').strip()
        val, _cur = _web_price_number_and_currency(existing)
        if val and _price_collides_with_product_spec(val, row.get('title'), row.get('_offer_meta')):
            print(f"WEB SIZE-AS-PRICE BLOCK store={row.get('store') or row.get('source')} value={val} title={(row.get('title') or '')[:90]}")
            val = None
            row['price'] = ''
        if val and val > 0:
            row['price'] = _web_normalize_existing_price_to_market(existing, rank, lang, market_snapshot)
            row['price_verified'] = False
            row['price_source'] = row.get('price_source') or 'search_structured_fast'
        else:
            row['price'] = ''
            row['price_verified'] = False
            row['price_pending'] = True
            row['price_source'] = 'pending_page_price'
        row.pop('_offer_meta', None)
        out.append(row)
    return out

def _web_market_candidates_to_items(candidates, rank, lang, query):
    seq = []
    for item in list(candidates or []):
        if result_market_rank(item) != rank:
            continue
        url = str(item.get('link') or '').strip()
        if not url.startswith(('http://', 'https://')):
            continue
        seq.append(item)
    if seq:
        seq = [x for x in seq if _findzia_stream_candidate_ok(query, x)]
    if seq:
        offer_rows = [{'line': x.get('title') or '', 'name': x.get('source') or ''} for x in seq]
        tmp_urls = {x.get('source') or '': x.get('link') or '' for x in seq}
        try:
            kept_rows = filter_relevant_offers(query, offer_rows, tmp_urls, use_ai=False, mode='exact')
            kept = {(r.get('name') or '', r.get('line') or '') for r in kept_rows}
            seq = [x for x in seq if (x.get('source') or '', x.get('title') or '') in kept]
        except Exception:
            pass
    try:
        seq = _filter_confirmed_oos(seq, f'WEB-STREAM-{rank}')
    except Exception:
        pass
    if rank == 1:
        seq.sort(key=lambda x: (-_findzia_match_score(query, x.get('title') or ''), _us_store_priority(x.get('source'), x.get('link')), int(x.get('position') or 999)))
    elif rank == 2:
        seq.sort(key=lambda x: (-_findzia_match_score(query, x.get('title') or ''), _china_store_priority(x.get('source'), x.get('link')), int(x.get('position') or 999)))
    else:
        seq.sort(key=lambda x: (-_findzia_match_score(query, x.get('title') or ''), int(x.get('position') or 999)))
    cap = {0: WEB_LOCAL_MAX, 1: WEB_US_MAX, 2: WEB_CN_MAX}.get(rank, 4)
    local_cc = (current_market().get('country') or DEFAULT_COUNTRY).lower()
    cc = local_cc if rank == 0 else 'us' if rank == 1 else 'cn'
    out, seen_urls, merchant_counts = ([], set(), defaultdict(int))
    for item in seq:
        url = str(item.get('link') or '').strip()
        try:
            host = urllib.parse.urlparse(url).netloc.lower().split(':')[0]
            host = host[4:] if host.startswith('www.') else host
        except Exception:
            host = ''
        merchant = host or normalize_name(item.get('source') or '')
        if not merchant or not url or url in seen_urls or (merchant_counts[merchant] >= RESULTS_PER_STORE_MAX):
            continue
        seen_urls.add(_canonical_result_url(url))
        merchant_counts[merchant] += 1
        raw_price = str(item.get('price') or '').strip()
        shown_price = _text_price_local(raw_price, rank, lang) if raw_price else ''
        out.append({'market': _web_market_label(rank), 'market_rank': rank, 'country': cc, 'flag': country_flag_emoji(cc), 'store': _ui_plain_store_name(item.get('source') or '', url) or U(lang, 'store'), 'title': _compact_ui_title(item.get('title') or query), 'price': shown_price, 'url': url, 'image': _web_best_card_image(item.get('thumbnail') or item.get('image') or '', '', False), 'match_score': round(_findzia_match_score(query, item.get('title') or query), 3), '_offer_meta': item.get('_offer_meta') or ''})
        if len(out) >= cap:
            break
    if WEB_FAST_SKIP_PRODUCT_PAGE_VERIFY:
        return _web_fast_finalize_rows(out, lang)
    return _web_verify_rows_strict(out, lang)

def _web_fast_market_wave_sync(query, country, lang, rank):
    market = _web_market(country)
    MARKET_CTX.value = market
    cap = {0: WEB_LOCAL_MAX, 1: WEB_US_MAX, 2: WEB_CN_MAX}.get(rank, 4)
    candidates = _market_presence_fallback(query, rank, limit=max(cap + 2, cap))
    rows = _web_market_candidates_to_items(candidates, rank, lang, query)
    return _web_require_product_image_rows(rows)

def _web_stream_store_specs(query, country, rank):
    market = _web_market(country)
    MARKET_CTX.value = market
    local_cc = (market.get('country') or DEFAULT_COUNTRY).lower()
    q = _shopping_clean_query(query or '')
    if rank == 0:
        specs = [('Local', '', local_cc)]
        try:
            specs.extend(((label, domain, local_cc) for label, domain in local_rescue_store_specs(q, WEB_LOCAL_STORE_PROBES)))
        except Exception:
            pass
    elif rank == 1:
        specs = [('Amazon', 'amazon.com', 'us'), ('eBay', 'ebay.com', 'us'), ('Etsy', 'etsy.com', 'us'), ('Walmart', 'walmart.com', 'us')]
    else:
        specs = [('AliExpress', 'aliexpress.com', 'us'), ('Temu', 'temu.com', 'us'), ('SHEIN', 'shein.com', 'us'), ('DHgate', 'dhgate.com', 'us'), ('Banggood', 'banggood.com', 'us'), ('Alibaba', 'alibaba.com', 'us'), ('Made-in-China', 'made-in-china.com', 'us')][:WEB_CHINA_GLOBAL_MAX_STORES]
    out, seen = ([], set())
    for label, domain, gl in specs:
        key = (str(domain or '').lower(), str(gl or '').lower())
        if key in seen:
            continue
        seen.add(key)
        out.append((label, domain, gl))
    return out

def _google_organic_price_text(row):
    if not isinstance(row, dict):
        return ''
    direct = str(row.get('price') or '').strip()
    if direct:
        return direct
    rich = row.get('rich_snippet') or {}
    for side in ('top', 'bottom'):
        block = rich.get(side) or {}
        detected = block.get('detected_extensions') or {}
        p = detected.get('price')
        if p not in (None, ''):
            cur = str(detected.get('currency') or '').strip()
            return (f'{cur} {p}' if cur else str(p)).strip()
        ext = block.get('extensions') or []
        if isinstance(ext, list):
            joined = ' | '.join((str(x) for x in ext))
            if joined:
                m = re.search('(?i)(?:US\\$|HK\\$|S\\$|A\\$|C\\$|\\$|€|£|¥|￥|AED|SAR|KWD|CNY|RMB)\\s*\\d[\\d,.]*(?:\\.\\d{1,3})?|\\d[\\d,.]*(?:\\.\\d{1,3})?\\s*(?:USD|CNY|RMB|EUR|GBP|KWD|AED|SAR)', joined)
                if m:
                    return m.group(0).strip()
    hay = ' '.join((str(row.get(k) or '') for k in ('title', 'snippet')))
    m = re.search('(?i)(?:US\\$|HK\\$|S\\$|A\\$|C\\$|\\$|€|£|¥|￥|AED|SAR|KWD|CNY|RMB)\\s*\\d[\\d,.]*(?:\\.\\d{1,3})?|\\d[\\d,.]*(?:\\.\\d{1,3})?\\s*(?:USD|CNY|RMB|EUR|GBP|KWD|AED|SAR)', hay)
    return m.group(0).strip() if m else ''

def _china_global_product_url(domain, url):
    try:
        u = urllib.parse.urlparse(str(url or '').strip())
        host = u.netloc.lower().split(':')[0]
        host = host[4:] if host.startswith('www.') else host
        path = (u.path or '').lower()
        query = (u.query or '').lower()
        pathq = path + ('?' + query if query else '')
    except Exception:
        return False
    if not _host_matches_any(host, (domain,)):
        return False
    if not path or path == '/':
        return False
    bad_markers = ('/search', '/category', '/categories', '/catalog', '/collections', '/store/', '/stores/', '/shop/', '/shops/', '/wholesale/', '/products?', '/product-list', '/list/', '/listing/', '/all-products', 'searchtext=', 'searchkey=', 'keyword=', 'q=', 'query=', 'search=')
    if any((marker in pathq for marker in bad_markers)):
        return False
    checks = {'aliexpress.com': lambda: bool(re.search('/item/(?:\\d+)(?:\\.html)?', path)), 'temu.com': lambda: '/goods.html' in path and ('goods_id=' in query or 'goodsid=' in query) or bool(re.search('-g-\\d+', path)) or bool(re.search('/goods/[^/]+', path)), 'shein.com': lambda: bool(re.search('(?:-p-|/product-p-)\\d+', path)), 'dhgate.com': lambda: '/product/' in path and bool(re.search('(?:/|-)\\d{6,}(?:\\.html)?$', path)), 'banggood.com': lambda: bool(re.search('(?:-p-|/p-)\\d+(?:\\.html)?', path)), 'alibaba.com': lambda: host in ('alibaba.com', 'www.alibaba.com') and '/product-detail/' in path and bool(re.search('(?:_|/)\\d{6,}(?:\\.html)?$', path)), 'made-in-china.com': lambda: '/product/' in path and path.endswith('.html') and (len(path.strip('/')) >= 18)}
    checker = checks.get(domain)
    return bool(checker and checker())

def _web_marketplace_repeat_cap(domain_or_url):
    raw = str(domain_or_url or '').strip().lower()
    try:
        host = urllib.parse.urlparse(raw if '://' in raw else 'https://' + raw).netloc.lower().replace('www.', '')
    except Exception:
        host = raw.replace('www.', '').split('/')[0]
    for dom in WEB_MULTI_LISTING_MARKETPLACES:
        if host == dom or host.endswith('.' + dom):
            return WEB_STREAM_MARKETPLACE_RESULTS_PER_STORE
    return WEB_STREAM_RESULTS_PER_STORE

def _web_is_direct_product_page_url(url, store_name=''):
    raw = str(url or '').strip()
    if not _web_is_http_url(raw):
        return False
    try:
        u = urllib.parse.urlparse(raw)
        host = u.netloc.lower().split(':')[0]
        host = host[4:] if host.startswith('www.') else host
        path = (u.path or '').lower()
        query = (u.query or '').lower()
        pathq = path + ('?' + query if query else '')
    except Exception:
        return False
    china_domains = ('aliexpress.com', 'temu.com', 'shein.com', 'dhgate.com', 'banggood.com', 'alibaba.com', 'made-in-china.com')
    for dom in china_domains:
        if host == dom or host.endswith('.' + dom):
            return _china_global_product_url(dom, raw)
    if host == 'etsy.com' or host.endswith('.etsy.com'):
        return bool(re.search('/listing/\\d{6,}(?:/|$)', path))
    bad = ('/search', '/search/', '/category', '/categories', '/collections/', '/catalog', '/results', '/browse', '/listing', '/list/', '?q=', '&q=', 'search=', 'query=', 'keyword=', 'searchterm=')
    if any((x in pathq for x in bad)):
        return False
    if path in ('', '/'):
        return False
    if host.endswith('amazon.com'):
        return bool(re.search('/(?:dp|gp/product)/[a-z0-9]{8,}', path))
    if host.endswith('ebay.com'):
        return bool(re.search('/itm/(?:[^/]+/)?\\d{8,}', path))
    if host.endswith('walmart.com'):
        return '/ip/' in path
    if len(path.strip('/')) < 6:
        return False
    nav_words = ('category', 'collection', 'search', 'brand', 'brands', 'shop-all', 'all-products')
    if any((word in path for word in nav_words)):
        return False
    return True

def _web_market_currency(market_snapshot=None):
    m = market_snapshot or current_market()
    cc = str((m or {}).get('country') or DEFAULT_COUNTRY).lower()
    codes = COUNTRY_CURRENCY_CODES.get(cc) or tuple()
    return str((m or {}).get('currency') or (codes[0] if codes else COUNTRY_CURRENCIES.get(cc, ''))).upper().strip()

def _web_convert_to_market(value, from_currency, market_snapshot=None):
    try:
        val = float(value)
    except Exception:
        return None
    src_cur = str(from_currency or '').upper().strip()
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
    raw = str(raw_price or '').strip()
    if not raw:
        return ''
    m = market_snapshot or current_market()
    local_cc = str((m or {}).get('country') or DEFAULT_COUNTRY).lower()
    local_cur = _web_market_currency(m)
    src = detect_currency_code(raw, local_cur if market_rank == 0 else 'USD' if market_rank == 1 else 'CNY' if market_rank == 2 else '', local_cc if market_rank == 0 else 'us' if market_rank == 1 else 'cn' if market_rank == 2 else '')
    if not src:
        src = local_cur if market_rank == 0 else 'USD' if market_rank == 1 else 'CNY' if market_rank == 2 else ''
    numeric = _extract_numeric_price(raw)
    if numeric is None:
        return raw
    if market_rank == 0 and src == local_cur:
        return f'{format_price(numeric, local_cur)} {local_cur}'.strip()
    converted = _web_convert_to_market(numeric, src, m)
    if converted is None:
        return raw
    original = f' ({format_price(numeric, src)} {src})' if src and src != local_cur else ''
    return f'{format_price(converted, local_cur)} {local_cur}{original}'

def _web_price_token_to_float(token, currency_code=''):
    return _normalize_price_token(token, currency_code)
_WEB_PRICE_CUR_WORDS = 'USD|US\\$|EUR|GBP|KWD|KD|SAR|AED|QAR|BHD|OMR|CNY|RMB|JPY|CAD|AUD|CHF|INR|KRW|TRY|RUB'
_WEB_PRICE_CUR_SYMS = '[$€£¥￥₹₩₺₽]|د\\.ك|ر\\.س|د\\.إ|ر\\.ق|د\\.ب|ر\\.ع'
_WEB_PRICE_NUM = '([0-9]{1,3}(?:,[0-9]{3})+(?:\\.[0-9]{1,3})?|[0-9]+(?:[.,][0-9]{1,3})?)'
_WEB_PRICE_PATS = (re.compile('(?:%s|%s)\\s*%s' % (_WEB_PRICE_CUR_WORDS, _WEB_PRICE_CUR_SYMS, _WEB_PRICE_NUM), re.I), re.compile('%s\\s*(?:%s|%s)' % (_WEB_PRICE_NUM, _WEB_PRICE_CUR_WORDS, _WEB_PRICE_CUR_SYMS), re.I))

def _web_price_number_and_currency(text, fallback_currency=''):
    raw = str(text or '').strip()
    if not raw:
        return (None, '')
    cur = detect_currency_code(raw, fallback_currency or '') or fallback_currency or ''
    for pat in _WEB_PRICE_PATS:
        m = pat.search(raw)
        if m:
            val = _web_price_token_to_float(m.group(1), cur)
            if val and val > 0:
                return (val, cur)
    if extract_pack_size(raw) and (not re.search('\\b(?:USD|EUR|GBP|KWD|KD|SAR|AED|QAR|BHD|OMR|CNY|RMB|JPY|CAD|AUD|CHF|INR|KRW|TRY|RUB)\\b|[$€£¥￥₹₩₺₽]|د\\.ك|ر\\.س|د\\.إ|ر\\.ق|د\\.ب|ر\\.ع', raw, re.I)):
        return (None, cur)
    if len(raw) <= 50:
        m = re.search(r'(?<![0-9])([0-9]+(?:[.,][0-9]{1,3})?)(?![0-9])', _normalize_price_chars(raw))
        if m:
            val = _normalize_price_token(m.group(1), cur)
            if val is not None and val > 0:
                return (val, cur)
    return (None, cur)
_WEB_DEEP_PRICE_SPECIFIC_PATS = (re.compile('"(?:salePrice|sale_price|specialPrice|special_price|sellingPrice|selling_price|offerPrice|offer_price|finalPrice|final_price|currentPrice|current_price|discountedPrice|discounted_price)"\\s*:\\s*\\{[^{}]{0,140}?"(?:amount|value|raw)"\\s*:\\s*"?([0-9]+(?:\\.[0-9]{1,4})?)', re.I), re.compile('"(?:salePrice|specialPrice|sellingPrice|offerPrice|finalPrice|currentPrice|discountedPrice|price_amount|priceAmount|priceValue|price_value)"\\s*:\\s*"?([0-9]+(?:\\.[0-9]{1,4})?)"?', re.I), re.compile('"price"\\s*:\\s*\\{[^{}]{0,140}?"(?:amount|value|raw)"\\s*:\\s*"?([0-9]+(?:\\.[0-9]{1,4})?)', re.I))
_WEB_DEEP_PRICE_GENERIC_PAT = re.compile('"price"\\s*:\\s*"?([0-9]+(?:\\.[0-9]{1,4})?)"?', re.I)
_WEB_DEEP_CURRENCY_PAT = re.compile('"(?:currency|currencyCode|currency_code|priceCurrency|currencyIsoCode)"\\s*:\\s*"([A-Za-z]{3})"', re.I)
_WEB_URL_CURRENCY_HINTS = ((('kuwait', '/kw/', '/kw-', '-kw/', '.kw/'), 'KWD'), (('saudi', '/sa/', '/sa-', '-sa/', '.sa/'), 'SAR'), (('/uae', 'uae/', '/ae/', '/ae-', '.ae/'), 'AED'), (('qatar', '/qa/', '.qa/'), 'QAR'), (('bahrain', '/bh/', '.bh/'), 'BHD'), (('oman', '/om/', '.om/'), 'OMR'), (('egypt', '/eg/', '.eg/'), 'EGP'))

def _web_currency_from_url(url):
    low = str(url or '').lower()
    for needles, code in _WEB_URL_CURRENCY_HINTS:
        if any((n in low for n in needles)):
            return code
    return ''

def _web_deep_json_price_scan(html, url=''):
    if not html:
        return (None, '')
    blob = html[:1200000]
    price = None
    for pat in _WEB_DEEP_PRICE_SPECIFIC_PATS:
        m = pat.search(blob)
        if m:
            try:
                v = float(m.group(1))
            except Exception:
                continue
            if 0.05 <= v <= 1000000:
                price = v
                break
    if price is None:
        votes = {}
        for m in _WEB_DEEP_PRICE_GENERIC_PAT.finditer(blob):
            try:
                v = float(m.group(1))
            except Exception:
                continue
            if 0.05 <= v <= 1000000:
                votes[v] = votes.get(v, 0) + 1
        if votes:
            best = max(votes.items(), key=lambda kv: (kv[1], -kv[0]))
            if best[1] >= 2:
                price = best[0]
    cur = ''
    m = _WEB_DEEP_CURRENCY_PAT.search(blob)
    if m and m.group(1).upper() in KNOWN_CURRENCY_CODES:
        cur = m.group(1).upper()
    if not cur:
        cur = _web_currency_from_url(url)
    return (price, cur)
_WEB_MOBILE_HEADERS = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8'}

def _web_verified_page_snapshot(url):
    url = str(url or '').strip()
    if not _web_is_http_url(url):
        return None
    now = time.time()
    with WEB_PRODUCT_VERIFY_LOCK:
        cached = WEB_PRODUCT_VERIFY_CACHE.get(url)
        if cached and now - float(cached.get('ts') or 0) < WEB_PRODUCT_VERIFY_CACHE_TTL_SECONDS:
            return dict(cached.get('data') or {})
    data = {'ok': False, 'url': url, 'price': None, 'currency': '', 'image': '', 'title': '', 'is_product': False}
    try:
        parsed = urllib.parse.urlparse(url)
        headers = dict(HEADERS)
        headers.update({'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.8', 'Referer': f'{parsed.scheme}://{parsed.netloc}/'})
        r = requests.get(url, headers=headers, timeout=(2.5, WEB_PRODUCT_VERIFY_TIMEOUT_SECONDS), allow_redirects=True)
        if (r.status_code >= 400 or not r.text) and r.status_code != 404:
            try:
                alt = dict(_WEB_MOBILE_HEADERS)
                alt['Referer'] = f'{parsed.scheme}://{parsed.netloc}/'
                r2 = requests.get(url, headers=alt, timeout=(2.5, WEB_PRODUCT_VERIFY_TIMEOUT_SECONDS), allow_redirects=True)
                if r2.status_code < 400 and r2.text:
                    print(f'WEB PAGE MOBILE-UA RESCUE host={parsed.netloc} status={r.status_code}->{r2.status_code}')
                    r = r2
            except Exception as e2:
                print(f'WEB PAGE MOBILE-UA RETRY ERR host={parsed.netloc}: {e2.__class__.__name__}')
        final_url = str(r.url or url)
        data['url'] = final_url
        if r.status_code < 400 and r.text:
            html = r.text[:1500000]
            parsed_data = parse_product_data(html, final_url) or {}
            data['price'] = parsed_data.get('price')
            data['currency'] = str(parsed_data.get('currency') or '').upper().strip()
            if not data['price']:
                deep_price, deep_cur = _web_deep_json_price_scan(html, final_url)
                if deep_price and deep_price > 0:
                    data['price'] = deep_price
                    if not data['currency'] and deep_cur:
                        data['currency'] = deep_cur
                    host_l = urllib.parse.urlparse(final_url).netloc
                    print(f"WEB DEEP PRICE SCAN HIT host={host_l} -> {deep_price} {data['currency'] or '?'}")
            if data['price'] and (not data['currency']):
                data['currency'] = _web_currency_from_url(final_url)
            data['image'] = parsed_data.get('image_url') or _web_extract_product_image_from_html(html, final_url) or ''
            data['title'] = parsed_data.get('title') or ''
            data['is_product'] = bool(parsed_data.get('is_product', True))
            data['ok'] = True
            low = re.sub('\\s+', ' ', BeautifulSoup(html[:450000], 'html.parser').get_text(' ', strip=True).lower())
            host = urllib.parse.urlparse(final_url).netloc.lower().split(':')[0]
            host = host[4:] if host.startswith('www.') else host
            if host.endswith('alibaba.com'):
                if host not in ('alibaba.com', 'www.alibaba.com'):
                    data['is_product'] = False
                supplier_listing_markers = ('verified suppliers ·', 'verified suppliers', 'supplier lists', 'results for ', 'latest products', 'distributor  verified suppliers', 'contact supplier')
                marker_hits = sum((1 for x in supplier_listing_markers if x in low))
                if marker_hits >= 2:
                    data['is_product'] = False
            if WEB_STRICT_PRODUCT_PAGE and (not _web_is_direct_product_page_url(final_url, '')):
                data['is_product'] = False
    except Exception as e:
        print(f'WEB PRODUCT VERIFY ERR url={url[:120]}: {e.__class__.__name__}')
    with WEB_PRODUCT_VERIFY_LOCK:
        WEB_PRODUCT_VERIFY_CACHE[url] = {'ts': now, 'data': dict(data)}
        if len(WEB_PRODUCT_VERIFY_CACHE) > 4000:
            oldest = sorted(WEB_PRODUCT_VERIFY_CACHE.items(), key=lambda kv: kv[1].get('ts', 0))[:800]
            for k, _ in oldest:
                WEB_PRODUCT_VERIFY_CACHE.pop(k, None)
    return data

def _web_unproxy_image_url(value):
    raw = str(value or '').strip()
    if not raw:
        return ''
    try:
        u = urllib.parse.urlparse(raw)
        if u.path.endswith('/api/img-proxy'):
            q = urllib.parse.parse_qs(u.query)
            inner = (q.get('u') or [''])[0]
            if _web_is_http_url(inner):
                return inner
    except Exception:
        pass
    return raw if _web_is_http_url(raw) else ''

def _web_image_fetchable(value):
    raw = _web_unproxy_image_url(value)
    if not _web_is_http_url(raw):
        return False
    cache_key = 'imgok:' + raw
    cached = _web_image_cache_get(cache_key)
    if cached in ('1', '0'):
        return cached == '1'
    ok = False
    try:
        p = urllib.parse.urlparse(raw)
        headers = dict(HEADERS)
        headers['Accept'] = 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'
        headers['Referer'] = f'{p.scheme}://{p.netloc}/'
        r = requests.get(raw, headers=headers, timeout=(2.0, WEB_PRODUCT_IMAGE_VERIFY_TIMEOUT_SECONDS), stream=True, allow_redirects=True)
        ctype = (r.headers.get('content-type') or '').split(';', 1)[0].strip().lower()
        if r.status_code < 400 and ctype.startswith('image/'):
            first = next(r.iter_content(4096), b'')
            ok = bool(first)
    except Exception:
        ok = False
    _web_image_cache_set(cache_key, '1' if ok else '0')
    return ok

def _web_choose_verified_product_image(row, snap):
    candidates = []
    if snap and snap.get('image'):
        candidates.append(str(snap.get('image') or '').strip())
    current = _web_unproxy_image_url(row.get('image') or row.get('thumbnail') or '')
    if current:
        candidates.append(current)
    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if not WEB_VERIFY_PRODUCT_IMAGE or _web_image_fetchable(candidate):
            return _web_public_image_url(candidate)
    return ''

def _web_price_pairs(text):
    raw = str(text or '')
    pairs = []
    pats = ('(?i)(KWD|KD|USD|EUR|GBP|JPY|CNY|RMB|SAR|AED|QAR|BHD|OMR|CAD|AUD|CHF|INR|KRW|TRY|RUB)\\s*([0-9]+(?:[.,][0-9]{1,3})?)', '(?i)([0-9]+(?:[.,][0-9]{1,3})?)\\s*(KWD|KD|USD|EUR|GBP|JPY|CNY|RMB|SAR|AED|QAR|BHD|OMR|CAD|AUD|CHF|INR|KRW|TRY|RUB)')
    for pat_idx, pat in enumerate(pats):
        for m in re.finditer(pat, raw):
            if pat_idx == 0:
                cur, num = (m.group(1), m.group(2))
            else:
                num, cur = (m.group(1), m.group(2))
            cur = cur.upper()
            if cur == 'KD':
                cur = 'KWD'
            if cur == 'RMB':
                cur = 'CNY'
            try:
                val = _normalize_price_token(num, cur)
            except Exception:
                continue
            if val is not None and val > 0:
                pairs.append((m.start(), val, cur))
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
    raw = str(display_price or '').strip()
    if not raw:
        return ''
    market = market_snapshot or current_market()
    local_cur = _web_market_currency(market)
    pairs = _web_price_pairs(raw)
    if not pairs:
        return raw
    if pairs[0][1] == local_cur:
        local_value = pairs[0][0]
        original = next(((v, c) for v, c in pairs[1:] if c != local_cur), None)
        suffix = f' ({format_price(original[0], original[1])} {original[1]})' if original else ''
        return f'{format_price(local_value, local_cur)} {local_cur}{suffix}'
    source_value, source_cur = pairs[-1]
    converted = _web_convert_to_market(source_value, source_cur, market)
    if converted is None:
        source_value, source_cur = pairs[0]
        converted = _web_convert_to_market(source_value, source_cur, market)
    if converted is None:
        return raw
    suffix = '' if source_cur == local_cur else f' ({format_price(source_value, source_cur)} {source_cur})'
    return f'{format_price(converted, local_cur)} {local_cur}{suffix}'

def _web_verify_card_strict(row, rank, lang, market_snapshot=None):
    if market_snapshot:
        MARKET_CTX.value = dict(market_snapshot)
    row = dict(row or {})
    url = str(row.get('url') or row.get('link') or '').strip()
    if not url:
        return None
    if WEB_STRICT_PRODUCT_PAGE and (not _web_is_direct_product_page_url(url, row.get('store') or row.get('source') or '')):
        print(f"WEB STRICT REJECT URL store={row.get('store') or row.get('source')} url={url[:150]}")
        return None
    snap = _web_verified_page_snapshot(url)
    if snap and snap.get('ok'):
        final_url = snap.get('url') or url
        if WEB_STRICT_PRODUCT_PAGE and (not snap.get('is_product')):
            print(f"WEB STRICT REJECT PAGE store={row.get('store') or row.get('source')} url={final_url[:150]}")
            return None
        row['url'] = final_url
        row['image'] = _web_choose_verified_product_image(row, snap)
        if WEB_REQUIRE_PRODUCT_IMAGE and (not row.get('image')):
            print(f"WEB STRICT REJECT NO IMAGE store={row.get('store') or row.get('source')} url={final_url[:140]}")
            return None
        if snap.get('title') and (not row.get('title')):
            row['title'] = _compact_ui_title(snap.get('title'))
    if not (snap and snap.get('ok')):
        row['image'] = _web_choose_verified_product_image(row, snap)
        if WEB_REQUIRE_PRODUCT_IMAGE and (not row.get('image')):
            print(f"WEB STRICT REJECT NO IMAGE store={row.get('store') or row.get('source')} url={url[:140]}")
            return None
    page_price = snap.get('price') if snap and snap.get('ok') else None
    page_cur = str((snap or {}).get('currency') or '').upper().strip()
    if page_price not in (None, ''):
        try:
            page_price = float(page_price)
        except Exception:
            page_price = None
    if page_price and page_price > 0:
        if not page_cur:
            page_cur = _web_market_currency(market_snapshot) if rank == 0 else 'USD' if rank == 1 else 'CNY'
        raw_price = f'{page_price:g} {page_cur}'.strip()
        row['price'] = _web_price_local_explicit(raw_price, rank, lang, market_snapshot)
        row['price'] = _web_normalize_existing_price_to_market(row['price'], rank, lang, market_snapshot)
        row['price_verified'] = True
        row['price_source'] = 'product_page'
        return row
    existing = str(row.get('price') or '').strip()
    val, cur = _web_price_number_and_currency(existing)
    if val and val > 0:
        row['price'] = _web_normalize_existing_price_to_market(existing, rank, lang, market_snapshot)
        row['price_verified'] = True
        row['price_source'] = row.get('price_source') or 'search_structured_rebased'
        return row
    if WEB_REQUIRE_NUMERIC_PRICE and (not WEB_KEEP_PRICELESS_RESULTS):
        print(f"WEB STRICT REJECT NO PRICE store={row.get('store') or row.get('source')} url={url[:140]}")
        return None
    print(f"WEB STRICT KEEP PRICELESS store={row.get('store') or row.get('source')} url={url[:140]}")
    row['price'] = ''
    row['price_verified'] = False
    row['price_pending'] = True
    row['price_source'] = 'pending_page_price'
    return row

def _web_row_has_numeric_price(row):
    val, _cur = _web_price_number_and_currency(str((row or {}).get('price') or ''))
    if not (val and val > 0):
        return False
    if _price_collides_with_product_spec(val, (row or {}).get('title'), (row or {}).get('_offer_meta')):
        return False
    return True

def _web_enrich_price_via_shopping(row, rank, market_snapshot):
    if not (WEB_PRICE_ENRICH_SHOPPING_FALLBACK and SERPAPI_API_KEY):
        return (None, '')
    url = str(row.get('url') or '').strip()
    title = str(row.get('title') or '').strip()
    if not url or not title:
        return (None, '')
    try:
        host = urllib.parse.urlparse(url).netloc.lower().split(':')[0]
        host = host[4:] if host.startswith('www.') else host
    except Exception:
        return (None, '')
    if not host:
        return (None, '')
    if rank == 0:
        gl = ((market_snapshot or {}).get('country') or DEFAULT_COUNTRY).lower()
        if SHOPPING_GEO_GUARD and (not _shopping_gl_supported(gl)):
            return (None, '')
        cc = gl
    else:
        gl, cc = ('us', 'us')
    cards = None
    for attempt in (1, 2):
        try:
            cards = _serpapi_shopping_request(f'{title} site:{host}', gl, hl='en', timeout_seconds=WEB_STREAM_STORE_HTTP_TIMEOUT)
            break
        except Exception as e:
            print(f'WEB PRICE FALLBACK SHOPPING ERR host={host} attempt={attempt}: {e}')
            if attempt == 2:
                return (None, '')
    for card in cards or []:
        item = _shopping_card_to_market_item(card, row.get('store') or '', cc)
        if not item:
            continue
        try:
            item_host = urllib.parse.urlparse(item.get('link') or '').netloc.lower().split(':')[0]
            item_host = item_host[4:] if item_host.startswith('www.') else item_host
        except Exception:
            item_host = ''
        if not (item_host == host or item_host.endswith('.' + host) or host.endswith('.' + item_host)):
            continue
        pv = item.get('price_value')
        try:
            pv = float(pv) if pv not in (None, '') else None
        except Exception:
            pv = None
        raw = str(item.get('price') or '').strip()
        if not pv or pv <= 0:
            pv, _c = _web_price_number_and_currency(raw)
        if pv and pv > 0:
            cur = str(item.get('currency') or '').upper().strip()
            if not cur:
                cur = _web_market_currency(market_snapshot) if rank == 0 else 'USD'
            return (pv, raw or f'{pv:g} {cur}')
    return (None, '')

def _web_enrich_row_price_sync(row, lang, market_snapshot, allow_shopping=True):
    try:
        if market_snapshot:
            MARKET_CTX.value = dict(market_snapshot)
        row = dict(row or {})
        url = str(row.get('url') or '').strip()
        store = row.get('store') or row.get('source') or '?'
        if not url:
            print(f'WEB PRICE ENRICH MISS store={store} reason=no_url')
            return None
        rank = row.get('market_rank')
        if rank not in (0, 1, 2):
            rank = result_market_rank({'link': url, 'source': row.get('store') or row.get('source'), 'title': row.get('title')})
        snap = _web_verified_page_snapshot(url)
        page_ok = bool((snap or {}).get('ok'))
        page_price = (snap or {}).get('price')
        page_cur = str((snap or {}).get('currency') or '').upper().strip()
        try:
            page_price = float(page_price) if page_price not in (None, '') else None
        except Exception:
            page_price = None
        raw_price = ''
        source_tag = ''
        if page_price and page_price > 0:
            if not page_cur:
                page_cur = _web_market_currency(market_snapshot) if rank == 0 else 'USD' if rank == 1 else 'CNY'
            raw_price = f'{page_price:g} {page_cur}'.strip()
            source_tag = 'product_page'
        elif allow_shopping:
            fb_val, fb_raw = _web_enrich_price_via_shopping(row, rank, market_snapshot)
            if fb_val and fb_val > 0:
                raw_price = fb_raw
                source_tag = 'google_shopping_fallback'
        if not raw_price:
            print(f"WEB PRICE ENRICH MISS store={store} page_ok={page_ok} shopping_fallback={('tried' if allow_shopping else 'off')} url={url[:120]}")
            return None
        row['price'] = _web_price_local_explicit(raw_price, rank, lang, market_snapshot)
        row['price'] = _web_normalize_existing_price_to_market(row['price'], rank, lang, market_snapshot)
        row['price_verified'] = True
        row['price_source'] = source_tag
        row.pop('price_pending', None)
        if (snap or {}).get('title') and (not row.get('title')):
            row['title'] = _compact_ui_title(snap.get('title'))
        print(f"WEB PRICE ENRICH OK store={store} via={source_tag} -> {row.get('price')}")
        return row
    except Exception as e:
        print(f'WEB PRICE ENRICH ERR: {e}')
        return None

def _web_price_host(url):
    try:
        host = urllib.parse.urlparse(str(url or '')).netloc.lower().split(':')[0]
        return host[4:] if host.startswith('www.') else host
    except Exception:
        return ''

def _web_shared_price_candidates(query, rank, market_snapshot):
    """One cached Shopping/Search request for every missing market, not every card."""
    q = _shopping_clean_query(query or '')
    if not q:
        return []
    local_cc = str((market_snapshot or {}).get('country') or DEFAULT_COUNTRY).lower()
    gl = local_cc if rank == 0 else 'us'
    cache_key = f'{rank}|{gl}|{q.casefold()}'
    now = time.time()
    with WEB_ASYNC_PRICE_CACHE_LOCK:
        cached = WEB_ASYNC_PRICE_CACHE.get(cache_key)
        if cached and now - float(cached.get('ts') or 0) < WEB_ASYNC_PRICE_CACHE_TTL_SECONDS:
            print(f'WEB LIVE PRICE CACHE HIT rank={rank} query={q[:65]!r}')
            return [dict(x) for x in cached.get('items') or []]
    if rank == 0 and SHOPPING_GEO_GUARD and (not _shopping_gl_supported(gl)):
        rows = _serpapi_google_organic_market_request(q, gl, hl=country_search_hl(gl), domain='', timeout_seconds=WEB_STREAM_STORE_HTTP_TIMEOUT, limit=10) if SHOPPING_UNSUPPORTED_ORGANIC_FALLBACK else []
    else:
        search_q = q
        if rank == 2:
            search_q = f'{q} site:aliexpress.com OR site:temu.com OR site:shein.com'
        cards = _serpapi_shopping_request(search_q, gl, hl=country_search_hl(gl) if rank == 0 else 'en', timeout_seconds=WEB_STREAM_STORE_HTTP_TIMEOUT)
        lens_cc = local_cc if rank == 0 else 'us' if rank == 1 else 'cn'
        rows = []
        for card in cards or []:
            item = _shopping_card_to_market_item(card, card.get('source') or '', lens_cc)
            if item and result_market_rank(item) == rank:
                rows.append(item)
    with WEB_ASYNC_PRICE_CACHE_LOCK:
        WEB_ASYNC_PRICE_CACHE[cache_key] = {'ts': now, 'items': [dict(x) for x in rows]}
        if len(WEB_ASYNC_PRICE_CACHE) > 1000:
            oldest = sorted(WEB_ASYNC_PRICE_CACHE.items(), key=lambda kv: kv[1].get('ts', 0))[:200]
            for old_key, _ in oldest:
                WEB_ASYNC_PRICE_CACHE.pop(old_key, None)
    print(f'WEB LIVE PRICE POOL rank={rank} query={q[:65]!r} -> {len(rows)} candidate(s)')
    return rows

def _web_shared_price_market_sync(entries, rank, lang, market_snapshot):
    if market_snapshot:
        MARKET_CTX.value = dict(market_snapshot)
    rows = {key: dict(row) for key, row in (entries or {}).items() if int((row or {}).get('market_rank', 99)) == rank}
    if not rows:
        return {}
    representative = max(rows.values(), key=lambda row: len(_identity_tokens(row.get('title') or '')))
    candidates = _web_shared_price_candidates(representative.get('title') or '', rank, market_snapshot)
    enriched = {}
    for key, row in rows.items():
        row_host = _web_price_host(row.get('url'))
        row_title = str(row.get('title') or '')
        row_size = extract_pack_size(row_title)
        best = None
        best_score = 0.0
        for cand in candidates:
            cand_host = _web_price_host(cand.get('link'))
            if not row_host or not cand_host or not (row_host == cand_host or row_host.endswith('.' + cand_host) or cand_host.endswith('.' + row_host)):
                continue
            cand_title = str(cand.get('title') or '')
            if _findzia_hard_product_mismatch(row_title, cand_title) or not sizes_compatible(row_size, extract_pack_size(cand_title)):
                continue
            score = _price_identity_score(row_title, cand_title)
            if score < 0.62 or score <= best_score:
                continue
            raw = str(cand.get('price') or '').strip()
            value = cand.get('price_value')
            try:
                value = float(value) if value not in (None, '') else None
            except Exception:
                value = None
            if not value or value <= 0:
                value, _ = _web_price_number_and_currency(raw)
            if not value or value <= 0:
                continue
            currency = str(cand.get('currency') or '').upper().strip()
            if not raw:
                currency = currency or (_web_market_currency(market_snapshot) if rank == 0 else 'USD' if rank == 1 else 'CNY')
                raw = f'{value:g} {currency}'
            best = (raw, score)
            best_score = score
        if not best:
            continue
        row['price'] = _web_price_local_explicit(best[0], rank, lang, market_snapshot)
        row['price'] = _web_normalize_existing_price_to_market(row['price'], rank, lang, market_snapshot)
        row['price_verified'] = True
        row['price_source'] = 'shared_market_price_pool'
        row.pop('price_pending', None)
        enriched[key] = row
        print(f"WEB LIVE PRICE OK store={row.get('store')} rank={rank} score={best[1]:.2f} -> {row.get('price')}")
    return enriched

def _web_spawn_price_enrich_task(price_tasks, key, item, lang, market_snapshot):
    if not ((WEB_PRICE_ENRICH_ENABLED or WEB_ASYNC_PRICE_ENRICH_ENABLED) and WEB_KEEP_PRICELESS_RESULTS):
        return
    if key in price_tasks or len(price_tasks) >= WEB_PRICE_ENRICH_MAX_ROWS:
        return
    if _web_row_has_numeric_price(item):
        return
    if not str((item or {}).get('url') or '').strip():
        return
    # The live path reads the product page only. Google fallback is shared by
    # market later, preventing one paid request per missing card.
    allow_shopping = bool(WEB_PRICE_ENRICH_ENABLED and (not WEB_ASYNC_PRICE_ENRICH_ENABLED) and len(price_tasks) < WEB_PRICE_ENRICH_SHOPPING_MAX)
    try:
        task = asyncio.create_task(asyncio.to_thread(_web_enrich_row_price_sync, dict(item), lang, market_snapshot, allow_shopping))
        task._findzia_price_row = dict(item)
        task._findzia_price_lang = lang
        task._findzia_price_market = dict(market_snapshot or {})
        price_tasks[key] = task
        print(f"WEB PRICE ENRICH SPAWN store={item.get('store') or item.get('source')} fallback={('on' if allow_shopping else 'quota_off')} url={str(item.get('url'))[:110]}")
    except Exception as e:
        print(f'WEB PRICE ENRICH SPAWN ERR: {e}')

async def _web_drain_price_enrich_events(price_tasks, priced_keys, started):
    if not price_tasks:
        return
    loop = asyncio.get_running_loop()
    deadline = loop.time() + WEB_PRICE_ENRICH_MAX_WAIT_SECONDS
    page_deadline = min(deadline, loop.time() + WEB_ASYNC_PRICE_PAGE_WINDOW_SECONDS)
    pending = {task: key for key, task in list(price_tasks.items())}
    missing = {}
    while pending and loop.time() < page_deadline:
        done, _ = await asyncio.wait(set(pending), timeout=max(0.0, page_deadline - loop.time()), return_when=asyncio.FIRST_COMPLETED)
        if not done:
            break
        for task in done:
            key = pending.pop(task)
            source_row = dict(getattr(task, '_findzia_price_row', {}) or {})
            try:
                enriched = task.result()
            except asyncio.CancelledError:
                enriched = None
            except Exception:
                enriched = None
            if enriched and key not in priced_keys:
                priced_keys.add(key)
                yield _web_stream_event({'event': 'upsert', 'phase': 'price_enrich', 'market': str(enriched.get('market') or 'other'), 'item': enriched, 'elapsed_ms': int((time.time() - started) * 1000)})
            elif source_row and key not in priced_keys:
                missing[key] = source_row
    for task, key in list(pending.items()):
        source_row = dict(getattr(task, '_findzia_price_row', {}) or {})
        if source_row and key not in priced_keys:
            missing[key] = source_row
        task.cancel()
    market_snapshot = dict(next((getattr(task, '_findzia_price_market', {}) for task in price_tasks.values() if getattr(task, '_findzia_price_market', None)), {}) or {})
    lang = next((getattr(task, '_findzia_price_lang', '') for task in price_tasks.values() if getattr(task, '_findzia_price_lang', '')), 'en')
    if WEB_ASYNC_PRICE_ENRICH_ENABLED and WEB_PRICE_ENRICH_SHOPPING_FALLBACK and missing and WEB_ASYNC_PRICE_SHARED_MARKETS > 0:
        ranks = [rank for rank in (0, 1, 2) if any((int((row or {}).get('market_rank', 99)) == rank for row in missing.values()))][:WEB_ASYNC_PRICE_SHARED_MARKETS]
        shared_tasks = {
            asyncio.create_task(asyncio.to_thread(_web_shared_price_market_sync, missing, rank, lang, market_snapshot)): rank
            for rank in ranks
        }
        while shared_tasks and loop.time() < deadline:
            done, _ = await asyncio.wait(set(shared_tasks), timeout=max(0.0, deadline - loop.time()), return_when=asyncio.FIRST_COMPLETED)
            if not done:
                break
            for task in done:
                rank = shared_tasks.pop(task)
                try:
                    updates = task.result() or {}
                except Exception as e:
                    print(f'WEB LIVE PRICE MARKET ERR rank={rank}: {e}')
                    updates = {}
                for key, enriched in updates.items():
                    if key in priced_keys:
                        continue
                    priced_keys.add(key)
                    yield _web_stream_event({'event': 'upsert', 'phase': 'shared_market_price', 'market': str(enriched.get('market') or 'other'), 'item': enriched, 'elapsed_ms': int((time.time() - started) * 1000)})
        for task in shared_tasks:
            task.cancel()
    for key, row in missing.items():
        if key in priced_keys:
            continue
        unresolved = dict(row)
        unresolved['price'] = ''
        unresolved['price_pending'] = False
        unresolved['price_unavailable'] = True
        unresolved['price_status'] = 'store_only'
        priced_keys.add(key)
        yield _web_stream_event({'event': 'upsert', 'phase': 'price_unavailable', 'market': str(unresolved.get('market') or 'other'), 'item': unresolved, 'elapsed_ms': int((time.time() - started) * 1000)})

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
            rank = row.get('market_rank')
            if rank not in (0, 1, 2):
                rank = result_market_rank({'link': row.get('url') or row.get('link'), 'source': row.get('store') or row.get('source'), 'title': row.get('title')})
            jobs.append((i, pool.submit(_web_verify_card_strict, row, rank, lang, market_snapshot)))
        for i, fut in jobs:
            try:
                out[i] = fut.result()
            except Exception:
                out[i] = None
    return [x for x in out if x]

def _serpapi_china_global_site_request(query, label, domain, timeout_seconds=None):
    params = {'engine': 'google', 'q': f'{query} site:{domain}', 'api_key': SERPAPI_API_KEY, 'google_domain': 'google.com', 'gl': 'us', 'hl': 'en', 'num': WEB_CHINA_ORGANIC_NUM, 'output': 'json'}
    try:
        data = _serpapi_cached_json(
            params,
            timeout=(3.5, timeout_seconds or WEB_CHINA_ORGANIC_TIMEOUT),
            label=f'WEB CHINA GOOGLE store={label}',
        )
        if data is None:
            return []
        rows = data.get('organic_results') or []
        out = []
        for pos, row in enumerate(rows, 1):
            link = str(row.get('link') or '').strip()
            if not link or not _china_global_product_url(domain, link):
                if link:
                    print(f'WEB CHINA REJECT NON-PRODUCT store={label} url={link[:160]}')
                continue
            price_text = _google_organic_price_text(row)
            out.append({'title': str(row.get('title') or query).strip(), 'link': link, 'source': label, 'position': int(row.get('position') or pos), 'section': 'web_china_global_google', 'exact': False, 'thumbnail': str(row.get('thumbnail') or '').strip(), 'image': str(row.get('thumbnail') or '').strip(), 'price': price_text, 'price_value': None, 'currency': detect_currency_code(price_text, '', 'cn') if price_text else '', 'in_stock': None, 'condition': '', '_lens_country': 'cn', '_china_fallback': True, '_web_global_china': True})
            if len(out) >= _web_marketplace_repeat_cap(domain):
                break
        print(f'WEB CHINA GLOBAL GOOGLE store={label} -> {len(out)} result(s)')
        return out
    except Exception as e:
        print(f'WEB CHINA GLOBAL GOOGLE EXCEPTION store={label}: {e}')
        return []

def _web_store_probe_sync(query, country, lang, rank, label, domain, gl):
    market = _web_market(country)
    MARKET_CTX.value = market
    q = _shopping_clean_query(query or '')
    if not q or not SERPAPI_API_KEY:
        return []
    candidate_cc = (market.get('country') or DEFAULT_COUNTRY).lower() if rank == 0 else 'us' if rank == 1 else 'cn'
    candidates = []
    if rank == 2 and domain and WEB_CHINA_ORGANIC_FIRST:
        candidates = _serpapi_china_global_site_request(q, label, domain, timeout_seconds=WEB_CHINA_ORGANIC_TIMEOUT)
        rows = _web_market_candidates_to_items(candidates, rank, lang, q)
        return _web_require_product_image_rows(rows[:_web_marketplace_repeat_cap(domain)])
    if not candidates:
        hl = country_search_hl(gl) if rank == 0 else 'en'
        if rank == 0 and SHOPPING_GEO_GUARD and (not _shopping_gl_supported(gl)):
            if SHOPPING_UNSUPPORTED_ORGANIC_FALLBACK:
                candidates = [item for item in _serpapi_google_organic_market_request(q, gl, hl=hl, domain=domain, timeout_seconds=WEB_STREAM_STORE_HTTP_TIMEOUT, limit=max(WEB_STREAM_RESULTS_PER_STORE, 4)) if result_market_rank(item) == rank]
            else:
                _log_unsupported_shopping_gl(gl)
        else:
            search_q = f'{q} site:{domain}' if domain else q
            cards = _serpapi_shopping_request(search_q, gl, hl=hl, timeout_seconds=WEB_STREAM_STORE_HTTP_TIMEOUT)
            for card in cards or []:
                item = _shopping_card_to_market_item(card, label, candidate_cc)
                if not item:
                    continue
                if domain:
                    try:
                        host = urllib.parse.urlparse(item.get('link') or '').netloc.lower().replace('www.', '')
                    except Exception:
                        host = ''
                    if not _host_matches_any(host, (domain,)):
                        continue
                if result_market_rank(item) != rank:
                    continue
                candidates.append(item)
    rows = _web_market_candidates_to_items(candidates, rank, lang, q)
    rows = [row for row in rows if _web_is_direct_product_page_url(row.get('url') or '', row.get('store') or label)]
    cap = _web_marketplace_repeat_cap(domain)
    if cap > WEB_STREAM_RESULTS_PER_STORE and rows:
        print(f'WEB MARKETPLACE MULTI store={label} cap={cap} rows={len(rows)}')
    return _web_require_product_image_rows(rows[:cap])

def _web_image_seed_sync(image_b64, mime, caption, country, lang):
    market = _web_market(country)
    MARKET_CTX.value = market
    caption = re.sub('\\s+', ' ', str(caption or '')).strip()[:WEB_API_MAX_QUERY_CHARS]
    if LENS_DIRECT_MODE and ENABLE_GOOGLE_LENS and SERPAPI_API_KEY and PUBLIC_BASE_URL:
        try:
            lens = google_lens_lookup(image_b64, mime, lang, caption, light=True)
        except Exception as e:
            print(f'WEB IMAGE FIFO LENS SEED ERR: {e}')
            lens = {'matches': [], 'query': ''}
        items = _web_build_lens_items(lens, lang, caption) if lens.get('matches') else []
        identity = (lens.get('visual_identity') or lens.get('relevance_target') or lens.get('query') or caption or '').strip()
        if identity or items:
            return {'query': identity or caption, 'items': items, 'market': market, 'source': 'lens_seed'}
    try:
        identity = identify_product_with_retry(image_b64, mime, lang) or caption
    except Exception:
        identity = caption
    return {'query': str(identity or caption or '').strip(), 'items': [], 'market': market, 'source': 'vision_seed'}

def _web_prepare_stream_query_sync(query, country, lang, selected_option='', original_query='', force_specific=False):
    market = _web_market(country)
    MARKET_CTX.value = market
    q = re.sub('\\s+', ' ', str(query or '')).strip()[:WEB_API_MAX_QUERY_CHARS]
    if selected_option:
        q = ai_recommendation_pick_search_query(original_query or q, selected_option, lang)
        force_specific = True
    if not q:
        return {'ok': False, 'error': 'empty_query', 'market': market, 'query': q}
    try:
        parsed = parse_user_intent(q, lang)
        products = [p for p in parsed.get('products') or [] if str(p).strip()]
        if len(products) == 1:
            q = products[0]
    except Exception:
        pass
    rtype = 'SPECIFIC'
    if not force_specific:
        try:
            rtype = classify_request_type(q)
        except Exception:
            rtype = 'SPECIFIC'
    return {'ok': True, 'query': q, 'market': market, 'rtype': rtype, 'force_specific': force_specific}

def _web_repair_text_price_outliers(rows, lang, market):
    """Verify obvious same-product price outliers against the retailer page.

    This specifically prevents product specs (e.g. 1440p) or stale metadata from
    showing as a price. Only strong outliers are re-fetched, so normal search speed
    is preserved.
    """
    rows = [dict(r or {}) for r in (rows or [])]
    groups = defaultdict(list)
    for idx, row in enumerate(rows):
        val, cur = _web_price_number_and_currency(str(row.get('price') or ''))
        rank = row.get('market_rank')
        if rank not in (0, 1, 2):
            rank = {'local': 0, 'us': 1, 'china': 2}.get(str(row.get('market') or '').lower(), 99)
        if val and val > 0:
            groups[(rank, cur or '')].append((idx, float(val)))
    suspects = set()
    for _key, seq in groups.items():
        if len(seq) < 2:
            continue
        vals = sorted(v for _, v in seq)
        mid = len(vals)//2
        median = vals[mid] if len(vals)%2 else (vals[mid-1]+vals[mid])/2.0
        if median <= 0:
            continue
        for idx, val in seq:
            if val > median * 4.0 or val < median / 4.0:
                suspects.add(idx)
    # Always verify values that collide with an explicit product specification.
    for idx, row in enumerate(rows):
        val, _cur = _web_price_number_and_currency(str(row.get('price') or ''))
        if val and _price_collides_with_product_spec(val, row.get('title'), row.get('_offer_meta')):
            suspects.add(idx)
    if not suspects:
        return rows
    market_snapshot = dict(market or current_market())
    with ThreadPoolExecutor(max_workers=min(4, len(suspects))) as pool:
        futs = {pool.submit(_web_enrich_row_price_sync, rows[i], lang, market_snapshot, True): i for i in suspects}
        for fut, idx in list(futs.items()):
            try:
                fixed = fut.result(timeout=WEB_PRODUCT_VERIFY_TIMEOUT_SECONDS + 2.5)
            except Exception:
                fixed = None
            if fixed and _web_row_has_numeric_price(fixed):
                rows[idx] = fixed
            else:
                # Better to say "price at store" than publish a clearly impossible number.
                rows[idx]['price'] = ''
                rows[idx]['price_verified'] = False
                rows[idx]['price_pending'] = True
    return rows

def _web_expand_text_results(query, country, lang, rows):
    """Fill weak typed searches from direct Shopping market waves.

    The AI text answer remains the relevance anchor, while structured Shopping
    results add genuine local/US/China product cards with images when a market
    came back sparse.
    """
    rows = _web_require_product_image_rows(rows)
    caps = {0: WEB_LOCAL_MAX, 1: WEB_US_MAX, 2: WEB_CN_MAX}
    counts = defaultdict(int)
    for row in rows:
        rank = row.get('market_rank')
        if rank in caps:
            counts[rank] += 1
    wanted = [rank for rank in (0, 1, 2) if counts[rank] < caps[rank]]
    if not wanted or not SERPAPI_API_KEY:
        return rows

    supplements = {}
    with ThreadPoolExecutor(max_workers=len(wanted)) as pool:
        futures = {
            pool.submit(_web_fast_market_wave_sync, query, country, lang, rank): rank
            for rank in wanted
        }
        for future, rank in list(futures.items()):
            try:
                supplements[rank] = future.result(timeout=WEB_STREAM_MARKET_TIMEOUT + 3) or []
            except Exception as exc:
                print(f'WEB TEXT EXPAND ERR rank={rank}: {exc.__class__.__name__}')
                supplements[rank] = []

    out = list(rows)
    seen_urls = {
        _canonical_result_url(str(row.get('url') or ''))
        for row in out
        if str(row.get('url') or '').strip()
    }
    merchant_counts = defaultdict(int)
    for row in out:
        try:
            host = urllib.parse.urlparse(str(row.get('url') or '')).netloc.lower().replace('www.', '')
        except Exception:
            host = ''
        if host:
            merchant_counts[host] += 1

    for rank in (0, 1, 2):
        for row in supplements.get(rank, []):
            if counts[rank] >= caps[rank]:
                break
            url = str(row.get('url') or '').strip()
            canonical = _canonical_result_url(url)
            try:
                host = urllib.parse.urlparse(url).netloc.lower().replace('www.', '')
            except Exception:
                host = ''
            if not canonical or canonical in seen_urls or not host:
                continue
            if merchant_counts[host] >= RESULTS_PER_STORE_MAX:
                continue
            if not _web_has_product_image(row):
                continue
            out.append(row)
            seen_urls.add(canonical)
            merchant_counts[host] += 1
            counts[rank] += 1

    out.sort(key=lambda row: (
        int(row.get('market_rank', 99)),
        -float(row.get('match_score') or 0),
        0 if _web_row_has_numeric_price(row) else 1,
    ))
    return out[:sum(caps.values())]

def _web_search_text_sync(query, country, lang, selected_option='', original_query='', force_specific=False):
    market = _web_market(country)
    MARKET_CTX.value = market
    q = re.sub('\\s+', ' ', str(query or '')).strip()[:WEB_API_MAX_QUERY_CHARS]
    if selected_option:
        q = ai_recommendation_pick_search_query(original_query or q, selected_option, lang)
        force_specific = True
    if not q:
        return {'ok': False, 'error': 'empty_query'}
    try:
        parsed = parse_user_intent(q, lang)
        products = [p for p in parsed.get('products') or [] if str(p).strip()]
        if len(products) == 1:
            q = products[0]
    except Exception:
        pass
    if not force_specific:
        try:
            rtype = classify_request_type(q)
        except Exception:
            rtype = 'SPECIFIC'
        if rtype == 'GENERIC':
            comparison = _web_brand_comparison(q, lang)
            if comparison:
                return {'ok': True, 'type': 'recommendations', 'query': q, 'market': market, 'comparison': comparison['summary'], 'options': comparison['options']}
        elif rtype == 'SERVICE':
            return {'ok': False, 'type': 'service', 'error': 'service_search_not_enabled_on_web_yet', 'query': q, 'market': market}
        elif rtype == 'NONE':
            return {'ok': False, 'type': 'chat', 'error': 'not_a_product_query', 'query': q, 'market': market}
    txt, urls = v26_text_search(q, lang)
    if USE_V106_5_RESULT_PIPELINE or TEXT_SEARCH_WHATSAPP_PARITY:
        # Copied execution order from main_v106.5: one authoritative extraction
        # pass, convert it to cards, return. No empty-market expansion, page
        # verification, price repair or image enrichment in the critical path.
        if not txt or not text77_extract_store_offers(txt, limit=30):
            return {'ok': True, 'type': 'results', 'query': q, 'market': market, 'results': [], 'source': 'whatsapp_text_engine', 'authoritative': True}
        results = _web_build_text_items(txt, urls, lang, q)
        return {
            'ok': True,
            'type': 'results',
            'query': q,
            'market': market,
            'results': results,
            # The web and app must treat this list as the same authoritative
            # winner set that the WhatsApp sender consumes. Client-side image
            # availability is presentation only and must never remove a row.
            'source': 'whatsapp_text_engine',
            'authoritative': True,
        }
    if not txt or not text77_extract_store_offers(txt, limit=30):
        results = _web_expand_text_results(q, country, lang, [])
        return {'ok': True, 'type': 'results', 'query': q, 'market': market, 'results': results, 'source': 'direct_market_fallback'}
    results = _web_build_text_items(txt, urls, lang, q)
    results = _web_repair_text_price_outliers(results, lang, market)
    results = _web_expand_text_results(q, country, lang, results)
    return {'ok': True, 'type': 'results', 'query': q, 'market': market, 'results': results}

def _web_more_seen_domain(value):
    raw = str(value or '').strip().lower()
    if not raw:
        return ''
    if '://' in raw:
        return _more_result_domain(raw)
    raw = raw.split('/', 1)[0].split(':', 1)[0]
    return raw[4:] if raw.startswith('www.') else raw

def _web_more_request_image(payload):
    raw = str((payload or {}).get('image_base64') or '').strip()
    if not raw:
        return ('', '')
    mime = str((payload or {}).get('mime_type') or 'image/jpeg').strip().lower()
    if ',' in raw and raw.lower().startswith('data:image/'):
        raw = raw.split(',', 1)[1]
    try:
        image_bytes = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError('invalid_image') from exc
    if not image_bytes or len(image_bytes) > WEB_API_RAW_IMAGE_MAX_BYTES:
        raise ValueError('image_too_large')
    image_bytes, mime = _web_normalize_uploaded_image_bytes(image_bytes, mime)
    if len(image_bytes) > WEB_API_MAX_IMAGE_BYTES:
        raise ValueError('image_too_large_after_convert')
    return (base64.b64encode(image_bytes).decode('ascii'), mime)

def _web_more_stores_sync(query, country, lang, shown_urls=None, shown_domains=None, image_b64='', image_mime=''):
    """WhatsApp-parity expansion for new merchants selling the same product.

    This is deliberately not a fresh broad search: it preserves the resolved
    product identity, excludes every merchant already displayed, and returns at
    most five additional stores from the selected local market, the US and China.
    """
    market = _web_market(country)
    MARKET_CTX.value = market
    q = re.sub('\\s+', ' ', str(query or '')).strip()[:WEB_API_MAX_QUERY_CHARS]
    seen_urls = {
        _canonical_result_url(str(url or '').strip())
        for url in list(shown_urls or [])[:80]
        if str(url or '').strip()
    }
    seen_domains = {
        _web_more_seen_domain(domain)
        for domain in list(shown_domains or [])[:80]
        if _web_more_seen_domain(domain)
    }
    for url in list(shown_urls or [])[:80]:
        domain = _more_result_domain(url)
        if domain:
            seen_domains.add(domain)

    candidates = []
    source = 'whatsapp_more_text'
    if image_b64 and image_mime:
        source = 'whatsapp_more_lens'
        exclusion = ' '.join((f'-site:{domain}' for domain in sorted(seen_domains)[:7]))
        hint = re.sub('\\s+', ' ', f'{q} buy shop other retailers {exclusion}').strip()[:220]
        try:
            lens = google_lens_lookup(image_b64, image_mime, lang, hint, light=True)
        except Exception as exc:
            print(f'WEB MORE LENS ERR: {exc.__class__.__name__}')
            lens = {'matches': []}
        if lens.get('matches'):
            filtered_lens = dict(lens)
            filtered_lens['matches'] = [
                item for item in lens.get('matches') or []
                if _canonical_result_url(str(item.get('link') or '')) not in seen_urls
                and _more_result_domain(item.get('link') or '') not in seen_domains
            ]
            candidates.extend(_web_build_lens_items(filtered_lens, lang, q))
    else:
        try:
            txt, urls = legacy_text_product_search_more(q, lang, seen_domains)
        except Exception as exc:
            print(f'WEB MORE TEXT ENGINE ERR: {exc.__class__.__name__}')
            txt, urls = ('', {})
        if txt and urls:
            candidates.extend(_web_build_text_items(txt, urls, lang, q))

    # The same exact query is also checked against structured market sources.
    # This supplies image-backed cards when the conversational engine found a
    # valid store but its page did not expose a usable product image.
    if len(candidates) < WEB_MORE_TOTAL_MAX and SERPAPI_API_KEY:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {
                pool.submit(_web_fast_market_wave_sync, q, country, lang, rank): rank
                for rank in (0, 1, 2)
            }
            for future, rank in list(futures.items()):
                try:
                    candidates.extend(future.result(timeout=WEB_STREAM_MARKET_TIMEOUT + 3) or [])
                except Exception as exc:
                    print(f'WEB MORE MARKET ERR rank={rank}: {exc.__class__.__name__}')

    selected = []
    new_domains = set()
    new_urls = set()
    for row in sorted(
        (dict(item or {}) for item in candidates),
        key=lambda item: (
            int(item.get('market_rank', 99)),
            -float(item.get('match_score') or 0),
            0 if _web_row_has_numeric_price(item) else 1,
        ),
    ):
        url = str(row.get('url') or row.get('link') or '').strip()
        canonical = _canonical_result_url(url)
        domain = _more_result_domain(url)
        if not canonical or not domain:
            continue
        if canonical in seen_urls or canonical in new_urls:
            continue
        if domain in seen_domains or domain in new_domains:
            continue
        if not _web_is_direct_product_page_url(url, row.get('store') or row.get('source') or ''):
            continue
        if not _web_has_product_image(row):
            continue
        selected.append(row)
        new_urls.add(canonical)
        new_domains.add(domain)
        if len(selected) >= WEB_MORE_TOTAL_MAX:
            break

    return {
        'ok': True,
        'type': 'results',
        'query': q,
        'market': market,
        'results': selected,
        'source': source,
        'excluded_store_count': len(seen_domains),
        'exhausted': not bool(selected),
    }

def _web_search_image_sync(image_b64, mime, caption, country, lang, progress_callback=None):
    market = _web_market(country)
    MARKET_CTX.value = market
    caption = re.sub('\\s+', ' ', str(caption or '')).strip()[:WEB_API_MAX_QUERY_CHARS]
    direct_attempted = False
    if LENS_DIRECT_MODE and ENABLE_GOOGLE_LENS and SERPAPI_API_KEY and PUBLIC_BASE_URL:
        direct_attempted = True
        lens_direct = google_lens_lookup(image_b64, mime, lang, caption, light=True, progress_callback=progress_callback)
        if lens_direct.get('matches'):
            items = _web_build_lens_items(lens_direct, lang, caption)
            if items:
                identity = (lens_direct.get('visual_identity') or lens_direct.get('relevance_target') or lens_direct.get('query') or caption or '').strip()
                if USE_V106_5_RESULT_PIPELINE or (WEB_MATCH_WHATSAPP_EXACT and (not WEB_TEXT_DENSE_PARITY)):
                    print(f'ANDROID IMAGE TRUE PARITY: direct WhatsApp Lens set -> {len(items)} result(s); no WEB v89 supplement')
                    return _web_attach_captured_result_sections({'ok': True, 'type': 'results', 'query': identity, 'market': market, 'results': items, 'source': 'whatsapp_direct_lens_exact'}, lang)
                if WEB_IMAGE_SUPPLEMENT_WEAK_MARKETS and identity:
                    target = {0: WEB_IMAGE_TARGET_LOCAL, 1: WEB_IMAGE_TARGET_US, 2: WEB_IMAGE_TARGET_CN}
                    counts = {0: 0, 1: 0, 2: 0}
                    for row in items:
                        r = row.get('market_rank')
                        if r in counts:
                            counts[r] += 1
                    weak = [r for r in (0, 1, 2) if counts[r] < target[r]]
                    if weak:
                        print(f'WEB IMAGE v89 weak markets before supplement counts={counts} target={target} identity={identity[:90]!r}')
                        market_snapshot = dict(market)
                        extra_by_rank = {}

                        def _supp(rank):
                            MARKET_CTX.value = market_snapshot
                            try:
                                return (rank, _web_fast_market_wave_sync(identity, country, lang, rank))
                            except Exception as e:
                                print(f'WEB IMAGE SUPPLEMENT ERR rank={rank}: {e}')
                                return (rank, [])
                        with ThreadPoolExecutor(max_workers=max(1, len(weak))) as ex:
                            futs = [ex.submit(_supp, r) for r in weak]
                            for fut in futs:
                                try:
                                    rank, rows = fut.result(timeout=SERPAPI_TIMEOUT_SECONDS + 5)
                                    extra_by_rank[rank] = rows or []
                                except Exception as e:
                                    print(f'WEB IMAGE SUPPLEMENT FUTURE ERR: {e}')
                        seen_urls = {str(x.get('url') or '').strip() for x in items if str(x.get('url') or '').strip()}
                        seen_sig = {(str(x.get('store') or '').strip().lower(), normalize_name(x.get('title') or '')) for x in items}
                        for rank in (0, 1, 2):
                            need = max(0, target[rank] - counts[rank])
                            if need <= 0:
                                continue
                            for row in extra_by_rank.get(rank, []):
                                url = str(row.get('url') or '').strip()
                                sig = (str(row.get('store') or '').strip().lower(), normalize_name(row.get('title') or ''))
                                if url and url in seen_urls or sig in seen_sig:
                                    continue
                                items.append(row)
                                if url:
                                    seen_urls.add(_canonical_result_url(url))
                                seen_sig.add(sig)
                                counts[rank] += 1
                                need -= 1
                                if need <= 0:
                                    break
                        items.sort(key=lambda x: (int(x.get('market_rank', 99)), 0 if x.get('price') else 1))
                        print(f'WEB IMAGE v89 after supplement counts={counts} total={len(items)}')
                return _web_attach_captured_result_sections({'ok': True, 'type': 'results', 'query': identity, 'market': market, 'results': items, 'source': 'lens_direct_plus_market_supplement'}, lang)
    lens_future = None
    if not direct_attempted and LENS_PARALLEL_WITH_VISION and ENABLE_GOOGLE_LENS and SERPAPI_API_KEY and PUBLIC_BASE_URL:
        lens_future = LENS_POOL.submit(_run_with_market, market, google_lens_lookup, image_b64, mime, lang, caption)
    vision_name = identify_product_with_retry(image_b64, mime, lang)
    force_fashion_lens = is_fashion_identity(vision_name, caption)
    use_lens, _route_reason = lens_routing_decision(vision_name, caption)
    use_lens = force_fashion_lens or use_lens
    if direct_attempted:
        use_lens = False
    lens = {'aliases': [], 'matches': [], 'query': ''}
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
    lens_title = ((lens.get('chosen') or {}).get('title') or lens.get('query') or '').strip()
    if use_lens:
        if force_fashion_lens and lens_title:
            lens['force_lens_only'] = True
            combined_name = ' | '.join(fuse_identity_aliases(lens_title, '', lens.get('aliases')))
            active_lens = lens
        elif lens_title and vision_name:
            if identity_candidates_agree(vision_name, lens_title):
                combined_name = ' | '.join(fuse_identity_aliases(lens_title, vision_name))
                active_lens = lens
            else:
                judged_name, active_lens, _identity_source = choose_image_identity(image_b64, mime, lens, vision_name)
                combined_name = ' | '.join(fuse_identity_aliases(judged_name, vision_name)) if active_lens else judged_name
        elif lens_title:
            combined_name = ' | '.join(fuse_identity_aliases(lens_title, '', lens.get('aliases')))
            active_lens = lens
    if combined_name and caption:
        request_query = f'{caption} — {combined_name}'
        prompt_text = f'هوية المنتج المعتمدة: {combined_name}\nطلب المستخدم: {caption}\nابحث عن نفس المنتج فقط. لا توسع البحث إلى منتج يشاركه المكون أو اللون أو الفئة. {lang_instr(lang)}'
        txt, urls = search_product(request_query, lang, prompt_text=prompt_text, lens_context=active_lens)
        query = request_query
    elif combined_name:
        txt, urls = search_product(combined_name, lang, lens_context=active_lens)
        query = combined_name
    else:
        txt, urls, query = ('', {}, caption)
    if not txt:
        return _web_attach_captured_result_sections({'ok': True, 'type': 'results', 'query': query, 'market': market, 'results': [], 'source': 'image_fallback'}, lang)
    items = _web_fallback_product_items(txt, urls, lang, query)
    return _web_attach_captured_result_sections({'ok': True, 'type': 'results', 'query': query, 'market': market, 'results': items, 'source': 'image_fallback'}, lang)

def _web_normalize_country_code(value):
    cc = str(value or '').strip().lower()
    if len(cc) == 2 and cc in COUNTRY_META:
        return cc
    return ''

def _web_client_ip(request: Request):
    for header in ('cf-connecting-ip', 'true-client-ip', 'x-real-ip'):
        value = str(request.headers.get(header) or '').strip()
        if value:
            return value.split(',')[0].strip()
    forwarded = str(request.headers.get('x-forwarded-for') or '').strip()
    if forwarded:
        return forwarded.split(',')[0].strip()
    try:
        return str(request.client.host or '').strip()
    except Exception:
        return ''

def _web_country_from_headers(request: Request):
    for header in ('cf-ipcountry', 'x-vercel-ip-country', 'cloudfront-viewer-country', 'x-country-code', 'x-geo-country'):
        cc = _web_normalize_country_code(request.headers.get(header))
        if cc:
            return (cc, 'header:' + header)
    return ('', '')

def _web_geo_country_from_ip(ip):
    ip = str(ip or '').strip()
    if not WEB_GEO_ENABLED or not ip:
        return ('', 'disabled')
    if ip in ('127.0.0.1', '::1') or ip.startswith(('10.', '192.168.', '172.16.', '172.17.', '172.18.', '172.19.', '172.2', '172.30.', '172.31.')):
        return ('', 'private_ip')
    now = time.time()
    with WEB_GEO_CACHE_LOCK:
        cached = WEB_GEO_CACHE.get(ip)
        if cached and now - cached.get('ts', 0) < WEB_GEO_CACHE_TTL_SECONDS:
            return (cached.get('country', ''), 'cache')
    cc = ''
    try:
        url = WEB_GEO_PROVIDER_URL.format(ip=urllib.parse.quote(ip, safe=':.'))
        r = requests.get(url, timeout=(1.0, WEB_GEO_TIMEOUT_SECONDS), headers=HEADERS)
        if r.ok:
            data = r.json() if r.content else {}
            if data.get('success', True) is not False:
                cc = _web_normalize_country_code(data.get('country_code') or data.get('countryCode'))
    except Exception as e:
        print(f'WEB GEO LOOKUP ERR ip={ip[:32]!r}: {e.__class__.__name__}')
    with WEB_GEO_CACHE_LOCK:
        WEB_GEO_CACHE[ip] = {'country': cc, 'ts': now}
        if len(WEB_GEO_CACHE) > 5000:
            oldest = sorted(WEB_GEO_CACHE.items(), key=lambda kv: kv[1].get('ts', 0))[:1000]
            for key, _ in oldest:
                WEB_GEO_CACHE.pop(key, None)
    return (cc, 'ipwhois' if cc else 'fallback')

def _web_resolve_request_country(request: Request, supplied_country=''):
    supplied = str(supplied_country or '').strip().lower()
    if supplied and supplied not in ('auto', 'detect', 'xx'):
        cc = _web_normalize_country_code(supplied)
        if cc:
            return (cc, 'supplied')
    cc, source = _web_country_from_headers(request)
    if cc:
        return (cc, source)
    cc, source = _web_geo_country_from_ip(_web_client_ip(request))
    if cc:
        return (cc, source)
    return (_web_normalize_country_code(DEFAULT_COUNTRY) or 'kw', 'default')

@app.get('/api/geo')
async def web_api_geo(request: Request):
    if not WEB_API_ENABLED:
        return Response(content=json.dumps({'ok': False, 'error': 'web_api_disabled'}), media_type='application/json', status_code=503)
    header_cc, header_source = _web_country_from_headers(request)
    if header_cc:
        cc, source = (header_cc, header_source)
    else:
        cc, source = await asyncio.to_thread(_web_geo_country_from_ip, _web_client_ip(request))
        if not cc:
            cc, source = (_web_normalize_country_code(DEFAULT_COUNTRY) or 'kw', 'default')
    currencies = COUNTRY_CURRENCY_CODES.get(cc) or tuple()
    return {'ok': True, 'country': cc.upper(), 'country_code': cc, 'country_name': COUNTRY_NAMES.get(cc, cc.upper()), 'currency': currencies[0] if currencies else COUNTRY_CURRENCIES.get(cc, ''), 'source': source}

@app.get('/api/img-proxy')
async def web_api_img_proxy(request: Request):
    if not WEB_API_ENABLED or not WEB_IMAGE_PROXY_ENABLED:
        return Response(content=b'', status_code=404)
    raw_url = str(request.query_params.get('u') or '').strip()
    if not _web_is_http_url(raw_url):
        return Response(content=b'', status_code=400)

    def _fetch_image(target_url):
        parsed = urllib.parse.urlparse(target_url)
        headers = dict(HEADERS)
        headers['Accept'] = 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'
        headers['Referer'] = f'{parsed.scheme}://{parsed.netloc}/'
        resp = requests.get(target_url, headers=headers, timeout=(2.5, WEB_IMAGE_PROXY_TIMEOUT_SECONDS), stream=True, allow_redirects=True)
        if resp.status_code >= 400:
            return (resp.status_code, '', b'', '')
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
            return (200, content_type or 'image/jpeg', body, '')
        try:
            html = resp.text[:400000]
        except Exception:
            html = ''
        return (200, content_type or 'text/html', b'', html)
    try:
        status, content_type, body, html = await asyncio.to_thread(_fetch_image, raw_url)
        if status >= 400:
            return Response(content=b'', status_code=status)
        if content_type.startswith('image/') and body:
            return Response(content=body, media_type=content_type, headers={'Cache-Control': 'public, max-age=86400'})
        rescued = _web_extract_product_image_from_html(html, raw_url) if html else ''
        if rescued and rescued != raw_url:
            status2, content_type2, body2, _ = await asyncio.to_thread(_fetch_image, rescued)
            if status2 < 400 and content_type2.startswith('image/') and body2:
                return Response(content=body2, media_type=content_type2, headers={'Cache-Control': 'public, max-age=86400'})
    except Exception as e:
        print(f'WEB IMG PROXY ERR: {raw_url[:120]} -> {e.__class__.__name__}')
    return Response(content=b'', status_code=404)


# =============================================================================
# FINDZIA AI FOR SHOPPING · WEB COPILOT v107.16
# Product-aware Q&A, similar-item comparison, observed price history, price alerts.
# =============================================================================
AI_SHOPPING_ENABLED = env_bool('AI_SHOPPING_ENABLED', True)
AI_SHOPPING_TIMEOUT_SECONDS = max(8.0, min(35.0, float(os.environ.get('AI_SHOPPING_TIMEOUT_SECONDS', '32'))))

AI_SHOPPING_MAX_OFFERS = max(3, min(12, int(os.environ.get('AI_SHOPPING_MAX_OFFERS', '8'))))
AI_SHOPPING_MAX_HISTORY_DAYS = max(30, min(730, int(os.environ.get('AI_SHOPPING_MAX_HISTORY_DAYS', '365'))))
AI_SHOPPING_RATE_PER_MINUTE = max(5, min(60, int(os.environ.get('AI_SHOPPING_RATE_PER_MINUTE', '20'))))
AI_RATE_BUCKETS = defaultdict(deque)
AI_RATE_LOCK = threading.Lock()

def _ai_rate_allowed(request):
    key = _web_request_ip(request)
    now = time.time()
    with AI_RATE_LOCK:
        q = AI_RATE_BUCKETS[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= AI_SHOPPING_RATE_PER_MINUTE:
            return False
        q.append(now)
        if len(AI_RATE_BUCKETS) > 5000:
            stale = [k for k, v in AI_RATE_BUCKETS.items() if not v or now - v[-1] > 300]
            for k in stale[:1000]:
                AI_RATE_BUCKETS.pop(k, None)
    return True

_AI_LANG_NAMES = {
    'en': 'English', 'ar': 'Arabic', 'de': 'German', 'fr': 'French', 'it': 'Italian', 'es': 'Spanish', 'pt': 'Portuguese',
    'tr': 'Turkish', 'ru': 'Russian', 'ja': 'Japanese', 'zh': 'Chinese', 'hi': 'Hindi', 'ur': 'Urdu'
}

def _ai_product_identity_text(product):
    product = product or {}
    title = str(product.get('title') or product.get('raw_title') or product.get('query') or '').strip()
    title = re.sub(r'\s+', ' ', title)
    return title[:260]

def _ai_product_key(product):
    title = _ai_product_identity_text(product)
    norm = normalize_ar(title).lower()
    norm = re.sub(r'https?://\S+', ' ', norm)
    norm = re.sub(r'\b(?:buy|shop|online|price|offer|best|sale|discount|amazon|noon|ebay)\b', ' ', norm, flags=re.I)
    norm = re.sub(r'[^\w\u0600-\u06FF]+', ' ', norm)
    norm = re.sub(r'\s+', ' ', norm).strip()
    if not norm:
        norm = str(product.get('url') or product.get('store') or 'product').strip().lower()
    return hashlib.sha256(norm.encode('utf-8')).hexdigest()[:32]

def _ai_db_init():
    try:
        with CACHE_DB_LOCK, _cache_db_connect() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS ai_price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_key TEXT NOT NULL,
                    product_title TEXT NOT NULL,
                    store TEXT NOT NULL DEFAULT '',
                    price REAL NOT NULL,
                    currency TEXT NOT NULL,
                    country TEXT NOT NULL DEFAULT '',
                    url TEXT NOT NULL DEFAULT '',
                    ts REAL NOT NULL,
                    day TEXT NOT NULL,
                    UNIQUE(product_key, store, currency, price, day)
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_ai_price_history_lookup ON ai_price_history(product_key, currency, ts)')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS ai_price_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT NOT NULL,
                    product_key TEXT NOT NULL,
                    product_title TEXT NOT NULL,
                    target_price REAL NOT NULL,
                    currency TEXT NOT NULL,
                    country TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    last_seen_price REAL,
                    triggered_at REAL,
                    UNIQUE(client_id, product_key, target_price, currency)
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_ai_price_alerts_lookup ON ai_price_alerts(client_id, active, product_key)')
    except Exception as e:
        print(f'AI DB INIT ERR: {e}')

_ai_db_init()

def _ai_price_value_currency(row, fallback_currency=''):
    row = row or {}
    raw = str(row.get('price') or '').strip()
    cur = str(row.get('currency') or '').strip().upper() or fallback_currency
    n, detected = _web_price_number_and_currency(raw, cur)
    cur = (detected or cur or '').upper()
    if n is None:
        try:
            n = float(row.get('price_value')) if row.get('price_value') not in (None, '') else None
        except Exception:
            n = None
    return (float(n) if n is not None and n > 0 else None, cur)

def _ai_record_observations(product, offers, country=''):
    product = product or {}
    offers = list(offers or [])[:AI_SHOPPING_MAX_OFFERS]
    key = _ai_product_key(product)
    title = _ai_product_identity_text(product)
    market = _web_market(country)
    fallback_cur = str(product.get('currency') or market.get('currency') or '').upper()
    rows = []
    now = time.time()
    day = time.strftime('%Y-%m-%d', time.gmtime(now))
    for offer in offers:
        price, cur = _ai_price_value_currency(offer, fallback_cur)
        if price is None or not cur:
            continue
        rows.append((key, title, str(offer.get('store') or '').strip()[:120], float(price), cur,
                     market.get('country') or '', str(offer.get('url') or '').strip()[:800], now, day))
    if not rows:
        price, cur = _ai_price_value_currency(product, fallback_cur)
        if price is not None and cur:
            rows.append((key, title, str(product.get('store') or '').strip()[:120], float(price), cur,
                         market.get('country') or '', str(product.get('url') or '').strip()[:800], now, day))
    if not rows:
        return {'ok': True, 'recorded': 0, 'product_key': key}
    try:
        with CACHE_DB_LOCK, _cache_db_connect() as conn:
            conn.executemany('''
                INSERT OR IGNORE INTO ai_price_history
                (product_key, product_title, store, price, currency, country, url, ts, day)
                VALUES(?,?,?,?,?,?,?,?,?)
            ''', rows)
            by_cur = {}
            for row in rows:
                by_cur[row[4]] = min(by_cur.get(row[4], row[3]), row[3])
            for cur, current_price in by_cur.items():
                conn.execute('''
                    UPDATE ai_price_alerts
                    SET last_seen_price=?,
                        triggered_at=CASE WHEN active=1 AND ?<=target_price THEN ? ELSE triggered_at END,
                        active=CASE WHEN active=1 AND ?<=target_price THEN 0 ELSE active END
                    WHERE product_key=? AND currency=?
                ''', (current_price, current_price, now, current_price, key, cur))
        return {'ok': True, 'recorded': len(rows), 'product_key': key}
    except Exception as e:
        print(f'AI OBSERVE ERR: {e}')
        return {'ok': False, 'recorded': 0, 'product_key': key}

def _ai_history(product, window_days, country=''):
    key = _ai_product_key(product)
    market = _web_market(country)
    fallback_cur = str(product.get('currency') or market.get('currency') or '').upper()
    current_price, detected_cur = _ai_price_value_currency(product, fallback_cur)
    cur = detected_cur or fallback_cur
    days = max(1, min(AI_SHOPPING_MAX_HISTORY_DAYS, int(window_days or 30)))
    cutoff = time.time() - days * 86400
    points = []
    try:
        with CACHE_DB_LOCK, _cache_db_connect() as conn:
            if cur:
                rows = conn.execute('''
                    SELECT day, MIN(price) FROM ai_price_history
                    WHERE product_key=? AND currency=? AND ts>=?
                    GROUP BY day ORDER BY day ASC
                ''', (key, cur, cutoff)).fetchall()
            else:
                rows = conn.execute('''
                    SELECT day, MIN(price), currency FROM ai_price_history
                    WHERE product_key=? AND ts>=?
                    GROUP BY day, currency ORDER BY day ASC
                ''', (key, cutoff)).fetchall()
                if rows and not cur:
                    cur = str(rows[-1][2] or '')
                    rows = [r[:2] for r in rows if str(r[2] or '') == cur]
        points = [{'date': r[0], 'price': round(float(r[1]), 4)} for r in rows]
    except Exception as e:
        print(f'AI HISTORY ERR: {e}')
    if current_price is None and points:
        current_price = points[-1]['price']
    summary = ''
    if len(points) >= 2:
        first, last = points[0]['price'], points[-1]['price']
        if first > 0:
            pct = ((last - first) / first) * 100
            if abs(pct) < 0.8:
                summary = f'Price has been steady over the last {days} days.'
            elif pct < 0:
                summary = f'Price is down {abs(pct):.1f}% over the last {days} days.'
            else:
                summary = f'Price is up {pct:.1f}% over the last {days} days.'
    elif points:
        summary = 'Findzia has started tracking this product.'
    return {'ok': True, 'product_key': key, 'currency': cur, 'current_price': current_price,
            'points': points, 'summary': summary, 'window_days': days}

def _ai_json_object(raw):
    """Parse Gemini JSON defensively without ever exposing raw JSON to the UI."""
    text = str(raw or '').strip()
    if not text:
        return {}

    def _strip_fences(s):
        s = str(s or '').strip().lstrip('\ufeff')
        s = re.sub(r'^```(?:json|javascript|js)?\s*', '', s, flags=re.I | re.S)
        s = re.sub(r'\s*```$', '', s, flags=re.I | re.S).strip()
        return s

    def _candidate_variants(s):
        s = _strip_fences(s)
        out = [s]
        first, last = s.find('{'), s.rfind('}')
        if first >= 0 and last > first:
            out.append(s[first:last + 1])
        out += [re.sub(r',\s*([}\]])', r'\1', x) for x in list(out)]
        seen, unique = set(), []
        for x in out:
            x = x.strip()
            if x and x not in seen:
                seen.add(x)
                unique.append(x)
        return unique

    def _load_object(s):
        for candidate in _candidate_variants(s):
            try:
                value = json.loads(candidate)
                if isinstance(value, dict):
                    return value
                if isinstance(value, str):
                    nested = _load_object(value)
                    if nested:
                        return nested
            except Exception:
                pass

            if candidate.startswith('{') and candidate.endswith('}'):
                try:
                    value = ast.literal_eval(candidate)
                    if isinstance(value, dict):
                        return value
                except Exception:
                    pass
        return {}

    def _coerce(value, depth=0):
        if depth > 3 or not isinstance(value, dict):
            return {}
        value = dict(value)
        ans = value.get('answer')
        if isinstance(ans, str):
            nested = _load_object(ans)
            if nested:
                merged = dict(value)
                merged.update(_coerce(nested, depth + 1) or nested)
                value = merged
            else:
                value['answer'] = _strip_fences(ans)
        return value

    parsed = _load_object(text)
    if parsed:
        return _coerce(parsed)

    # A nearly-valid model object must never be sent to the UI as visible JSON.
    # Recover only its quoted answer; otherwise the normal safe fallback runs.
    match = re.search(r'["\']answer["\']\s*:\s*"((?:\\.|[^"\\])*)"', text, flags=re.I | re.S)
    if match:
        try:
            answer = json.loads('"' + match.group(1) + '"')
        except Exception:
            answer = match.group(1).replace('\\n', '\n').replace('\\"', '"')
        if str(answer or '').strip():
            return {
                'answer': str(answer).strip(),
                'bullets': [],
                'comparison': [],
                'ratings': {},
                'suggested_questions': [],
            }
    return {}

def _ai_shopping_prompt(product, offers, question, lang, action):
    target = _AI_LANG_NAMES.get(lang, 'English')
    language_rule = (
        'Use clear Modern Standard Arabic (العربية الفصحى المبسطة). '
        'Never use Kuwaiti, Gulf, or colloquial Arabic wording.'
        if lang == 'ar' else ''
    )
    product_text = json.dumps(product or {}, ensure_ascii=False)
    offer_text = json.dumps(list(offers or [])[:AI_SHOPPING_MAX_OFFERS], ensure_ascii=False)
    action = action or 'qa'
    system = f'''You are Findzia AI for shopping, a product-aware shopping copilot.
Answer in {target}. {language_rule}
Be concise, practical, and specific to the exact product context supplied. Think like a senior shopping expert: first identify the user's decision, then answer only what helps that decision.
Never invent compatibility, warranty, customer sentiment, price history, availability, specifications, review scores, or review counts. Distinguish facts from inference. If current web evidence is uncertain, say so briefly. Use CURRENT FINDZIA OFFERS as the authoritative live price context and never replace a Findzia-observed price with an unrelated web price.
Brand/model/SKU names must not be translated. Do not output markdown tables.
Return ONLY valid JSON. Do not wrap JSON in markdown or quotes. Do not add trailing commas.
Use this exact shape:
{{"answer":"direct answer in 1-3 compact paragraphs, usually under 120 words","bullets":["0-5 concise bullets"],"comparison":[{{"name":"product","why":"key difference / best use","best_for":"short","price_note":"optional"}}],"ratings":{{"expert_score":null,"expert_source":"","customer_score":null,"customer_count":null,"customer_source":""}},"suggested_questions":["3-6 short follow-up shopping questions"]}}
Rating rules:
- All scores are on a 0-5 scale.
- expert_score is allowed ONLY when an established professional/editorial review explicitly provides a numeric rating or score. Normalize that explicit score to 5. Otherwise return null.
- expert_source must be the exact publication/site name tied to that explicit professional score.
- customer_score is allowed ONLY when a reliable aggregate customer rating is visible in grounded evidence. Otherwise return null.
- customer_count must be a verified review count when visible; otherwise null.
- Never convert general positive/negative prose into stars.
For action=suggestions, answer and bullets may be empty and suggested_questions must contain 5-7 useful questions tailored to this product.
For action=compare, compare the current product with 2-4 genuinely similar products or variants, prioritizing the same brand/ecosystem when relevant. Each comparison.name MUST be a clean, searchable commercial product name (brand + model/variant), with no commentary appended, because the UI turns it into a Findzia search link.
For action=reviews, use grounded web evidence, summarize recurring customer themes, and include a verified expert/customer star rating only when the rules above are satisfied.'''
    user = f'''ACTION: {action}
CURRENT PRODUCT: {product_text}
CURRENT FINDZIA OFFERS: {offer_text}
USER QUESTION: {question or 'Generate the most useful shopping questions for this exact product.'}'''
    return system, user

def _ai_shopping_fallback(product, offers, question, lang, action):
    title = _ai_product_identity_text(product) or 'this product'
    price = str((product or {}).get('price') or '').strip()
    q = str(question or '').lower()
    is_ar = lang == 'ar'
    if action == 'compare':
        if is_ar:
            answer = f'تعذر التحقق من بدائل موثوقة لـ {title} الآن. لن أذكر طرازات غير مؤكدة. حاول مرة أخرى بعد قليل.'
        else:
            answer = f'I could not verify reliable alternatives for {title} right now, so I will not invent models. Please try again shortly.'
    elif action == 'reviews' or re.search(r'customer|review|rating|reviews|عملاء|مراجعات|تقييم', q, re.I):
        if is_ar:
            answer = f'تعذر التحقق من آراء العملاء أو تقييمات الخبراء الموثوقة عن {title} الآن، لذلك لن أعرض تقييمًا أو عدد مراجعات غير مؤكد.'
        else:
            answer = f'I could not verify reliable customer feedback or expert ratings for {title} right now, so I will not guess ratings or review counts.'
    else:
        if is_ar:
            answer = f'{title}' + (f' معروض حاليًا في Findzia بسعر {price}.' if price else '.') + ' قبل الشراء، تأكد من الطراز أو المقاس أو التوافق المطلوب. يمكنني إعادة فحص التفاصيل عندما يصبح البحث الخارجي متاحًا.'
        else:
            answer = f'{title}' + (f' is currently shown by Findzia at {price}.' if price else '.') + ' Before buying, confirm the exact model, size, or compatibility you need. I can re-check the product details when external lookup is available.'
    return {
        'ok': True,
        'answer': answer,
        'bullets': [],
        'comparison': [],
        'ratings': {
            'expert_score': None,
            'expert_source': '',
            'customer_score': None,
            'customer_count': None,
            'customer_source': '',
        },
        'suggested_questions': [],
        'sources': [],
        'fallback': True,
    }

def _ai_shopping_call_sync(product, offers, question, lang, country, action):
    system, prompt = _ai_shopping_prompt(product, offers, question, lang, action)
    market = _web_market(country)
    qlow = str(question or '').lower()

    use_search = (
        action in ('compare', 'reviews')
        or bool(re.search(r'customer|review|rating|reviews|عملاء|مراجعات|تقييم|alternative|similar|بديل|مشابه', qlow, re.I))
    )

    raw, urls = ('', {})
    try:
        raw, urls = _run_with_market(
            market,
            call_gemini,
            [{'text': prompt}],
            system=system,
            use_search=use_search,
        )
    except Exception as e:
        print(f'AI SHOPPING GEMINI ERR search={use_search}: {e}')

    if not str(raw or '').strip() and use_search and action != 'reviews':
        try:
            raw, urls = _run_with_market(
                market,
                call_gemini,
                [{'text': prompt}],
                system=system,
                use_search=False,
            )
        except Exception as e:
            print(f'AI SHOPPING GEMINI FALLBACK ERR: {e}')
            raw, urls = ('', {})

    data = _ai_json_object(raw)

    raw_text = str(raw or '').strip()
    if not data and raw_text:
        looks_structured = (
            raw_text.startswith('{')
            or bool(re.search(r'["\'](?:answer|bullets|comparison|ratings)["\']\s*:', raw_text, re.I))
        )
        if not looks_structured:
            data = {
                'answer': raw_text[:1800],
                'bullets': [],
                'comparison': [],
                'ratings': {},
                'suggested_questions': [],
            }

    if not data:
        return _ai_shopping_fallback(product, offers, question, lang, action)

    data['answer'] = str(data.get('answer') or '').strip()[:2200]
    data['bullets'] = [
        str(x).strip()[:360]
        for x in (data.get('bullets') or [])
        if str(x).strip()
    ][:6]

    comp = []
    for x in (data.get('comparison') or [])[:5]:
        if not isinstance(x, dict):
            continue
        comp.append({
            'name': str(x.get('name') or '').strip()[:140],
            'why': str(x.get('why') or '').strip()[:500],
            'best_for': str(x.get('best_for') or '').strip()[:180],
            'price_note': str(x.get('price_note') or '').strip()[:120],
        })
    data['comparison'] = comp

    def _score5(value):
        try:
            n = float(value)
        except Exception:
            return None
        if not (0 < n <= 5):
            return None
        return round(n, 2)

    ratings_raw = data.get('ratings') if isinstance(data.get('ratings'), dict) else {}
    grounded_reviews = bool(urls)
    expert_score = _score5(ratings_raw.get('expert_score')) if grounded_reviews else None
    customer_score = _score5(ratings_raw.get('customer_score')) if grounded_reviews else None

    customer_count = ratings_raw.get('customer_count')
    try:
        customer_count = int(str(customer_count).replace(',', '').strip()) if customer_count not in (None, '') else None
        if customer_count is not None and customer_count < 0:
            customer_count = None
    except Exception:
        customer_count = None

    data['ratings'] = {
        'expert_score': expert_score,
        'expert_source': str(ratings_raw.get('expert_source') or '').strip()[:120] if expert_score is not None else '',
        'customer_score': customer_score,
        'customer_count': customer_count if customer_score is not None else None,
        'customer_source': str(ratings_raw.get('customer_source') or '').strip()[:120] if customer_score is not None else '',
    }

    data['suggested_questions'] = []
    data['sources'] = list(dict.fromkeys([
        u for u in (urls or {}).values() if _web_is_http_url(u)
    ]))[:5]
    data['ok'] = True

    if not data['answer'] and not data['bullets'] and not data['comparison'] and not any(
        data['ratings'].get(k) is not None for k in ('expert_score', 'customer_score')
    ):
        return _ai_shopping_fallback(product, offers, question, lang, action)

    return data

@app.post('/api/ai/observe-prices')
async def web_ai_observe_prices(request: Request):
    if not AI_SHOPPING_ENABLED:
        return Response(content=json.dumps({'ok': False, 'error': 'ai_shopping_disabled'}), media_type='application/json', status_code=503)
    try:
        payload = await request.json()
    except Exception:
        return Response(content=json.dumps({'ok': False, 'error': 'invalid_json'}), media_type='application/json', status_code=400)
    product = payload.get('product') if isinstance(payload.get('product'), dict) else {}
    offers = payload.get('offers') if isinstance(payload.get('offers'), list) else []
    country = str(payload.get('country') or DEFAULT_COUNTRY)
    return await asyncio.to_thread(_ai_record_observations, product, offers, country)

@app.post('/api/ai/price-intelligence')
async def web_ai_price_intelligence(request: Request):
    if not AI_SHOPPING_ENABLED:
        return Response(content=json.dumps({'ok': False, 'error': 'ai_shopping_disabled'}), media_type='application/json', status_code=503)
    try:
        payload = await request.json()
    except Exception:
        return Response(content=json.dumps({'ok': False, 'error': 'invalid_json'}), media_type='application/json', status_code=400)
    product = payload.get('product') if isinstance(payload.get('product'), dict) else {}
    offers = payload.get('offers') if isinstance(payload.get('offers'), list) else []
    country = str(payload.get('country') or DEFAULT_COUNTRY)
    market = _web_market(country)
    fallback_cur = str(product.get('currency') or market.get('currency') or '').upper()
    values = []
    for offer in offers[:AI_SHOPPING_MAX_OFFERS]:
        val, cur = _ai_price_value_currency(offer, fallback_cur)
        if val is None or val <= 0 or not cur:
            continue
        # Product offers passed by the UI are normalized to the visitor's display currency.
        if fallback_cur and cur != fallback_cur:
            converted = _web_convert_to_market(val, cur, market)
            if converted is None:
                continue
            val, cur = converted, fallback_cur
        values.append({'price': float(val), 'currency': cur, 'store': str(offer.get('store') or '').strip(), 'market': str(offer.get('market') or '').strip()})
    if not values:
        val, cur = _ai_price_value_currency(product, fallback_cur)
        if val is not None and val > 0 and cur:
            values.append({'price': float(val), 'currency': cur, 'store': str(product.get('store') or '').strip(), 'market': str(product.get('market') or '').strip()})
    if not values:
        return {'ok': True, 'count': 0, 'currency': fallback_cur, 'min': None, 'max': None, 'average': None, 'median': None, 'best_store': ''}
    cur = values[0]['currency']
    nums = sorted(v['price'] for v in values if v['currency'] == cur and v['price'] > 0)
    if not nums:
        return {'ok': True, 'count': 0, 'currency': cur, 'min': None, 'max': None, 'average': None, 'median': None, 'best_store': ''}
    mid = len(nums)//2
    median = nums[mid] if len(nums)%2 else (nums[mid-1]+nums[mid])/2.0
    minimum, maximum = min(nums), max(nums)
    average = sum(nums)/len(nums)
    best = min((v for v in values if v['currency']==cur), key=lambda x:x['price'])
    spread_pct = ((maximum-minimum)/average*100.0) if average > 0 and len(nums)>1 else 0.0
    saving_vs_avg = ((average-minimum)/average*100.0) if average > 0 else 0.0
    return {'ok': True, 'count': len(nums), 'currency': cur, 'min': round(minimum,4), 'max': round(maximum,4), 'average': round(average,4), 'median': round(median,4), 'best_store': best.get('store') or '', 'spread_percent': round(spread_pct,1), 'saving_vs_average_percent': round(max(0.0,saving_vs_avg),1)}

@app.post('/api/ai/price-history')
async def web_ai_price_history(request: Request):
    if not AI_SHOPPING_ENABLED:
        return Response(content=json.dumps({'ok': False, 'error': 'ai_shopping_disabled'}), media_type='application/json', status_code=503)
    try:
        payload = await request.json()
    except Exception:
        return Response(content=json.dumps({'ok': False, 'error': 'invalid_json'}), media_type='application/json', status_code=400)
    product = payload.get('product') if isinstance(payload.get('product'), dict) else {}
    country = str(payload.get('country') or DEFAULT_COUNTRY)
    try:
        days = int(payload.get('window') or 30)
    except Exception:
        days = 30
    return await asyncio.to_thread(_ai_history, product, days, country)

@app.post('/api/ai/price-alert')
async def web_ai_price_alert(request: Request):
    if not AI_SHOPPING_ENABLED:
        return Response(content=json.dumps({'ok': False, 'error': 'ai_shopping_disabled'}), media_type='application/json', status_code=503)
    try:
        payload = await request.json()
    except Exception:
        return Response(content=json.dumps({'ok': False, 'error': 'invalid_json'}), media_type='application/json', status_code=400)
    client_id = re.sub(r'[^A-Za-z0-9_.:-]+', '', str(payload.get('client_id') or ''))[:100]
    product = payload.get('product') if isinstance(payload.get('product'), dict) else {}
    country = str(payload.get('country') or DEFAULT_COUNTRY)
    try:
        target = float(payload.get('target_price'))
    except Exception:
        target = 0.0
    if not client_id or target <= 0:
        return Response(content=json.dumps({'ok': False, 'error': 'invalid_alert'}), media_type='application/json', status_code=400)
    market = _web_market(country)
    current, cur = _ai_price_value_currency(product, str(product.get('currency') or market.get('currency') or '').upper())
    cur = (cur or market.get('currency') or '').upper()
    key = _ai_product_key(product)
    title = _ai_product_identity_text(product)
    try:
        with CACHE_DB_LOCK, _cache_db_connect() as conn:
            conn.execute('''
                INSERT INTO ai_price_alerts(client_id, product_key, product_title, target_price, currency, country, created_at, active, last_seen_price)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(client_id, product_key, target_price, currency) DO UPDATE SET
                    active=1, created_at=excluded.created_at, last_seen_price=excluded.last_seen_price, triggered_at=NULL
            ''', (client_id, key, title, target, cur, market.get('country') or '', time.time(), 1, current))
        lang = _web_language(payload.get('lang'))
        msg = 'تم حفظ تنبيه السعر. سيقارن Findzia السعر المستهدف بالأسعار التي يرصدها لاحقاً.' if lang == 'ar' else 'Price alert saved. Findzia will compare your target with future observed prices.'
        return {'ok': True, 'message': msg, 'target_price': target, 'currency': cur, 'current_price': current}
    except Exception as e:
        print(f'AI ALERT ERR: {e}')
        return Response(content=json.dumps({'ok': False, 'error': 'alert_save_failed'}), media_type='application/json', status_code=500)

@app.post('/api/ai/shopping')
async def web_ai_shopping(request: Request):
    if not AI_SHOPPING_ENABLED:
        return Response(content=json.dumps({'ok': False, 'error': 'ai_shopping_disabled'}), media_type='application/json', status_code=503)
    if not _ai_rate_allowed(request):
        return Response(content=json.dumps({'ok': False, 'error': 'ai_rate_limit'}), media_type='application/json', status_code=429)
    try:
        payload = await request.json()
    except Exception:
        return Response(content=json.dumps({'ok': False, 'error': 'invalid_json'}), media_type='application/json', status_code=400)
    product = payload.get('product') if isinstance(payload.get('product'), dict) else {}
    if not _ai_product_identity_text(product):
        return Response(content=json.dumps({'ok': False, 'error': 'missing_product'}), media_type='application/json', status_code=400)
    offers = payload.get('offers') if isinstance(payload.get('offers'), list) else []
    question = str(payload.get('question') or '').strip()[:1200]
    action = str(payload.get('action') or 'qa').strip().lower()
    if action not in ('suggestions', 'qa', 'compare', 'reviews'):
        action = 'qa'
    lang = _web_language(payload.get('lang'))
    country = str(payload.get('country') or DEFAULT_COUNTRY)
    await asyncio.to_thread(_ai_record_observations, product, offers, country)
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_ai_shopping_call_sync, product, offers, question, lang, country, action),
            timeout=AI_SHOPPING_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        return Response(content=json.dumps({'ok': False, 'error': 'ai_timeout'}), media_type='application/json', status_code=504)
    result['product_key'] = _ai_product_key(product)
    return result



@app.get('/api/health')
async def web_api_health():
    return {'ok': True, 'web_api': WEB_API_ENABLED, 'build': BUILD_ID, 'lens': bool(ENABLE_GOOGLE_LENS and SERPAPI_API_KEY)}

@app.post('/api/search/more')
async def web_api_search_more(request: Request):
    if not WEB_API_ENABLED:
        return Response(content=json.dumps({'ok': False, 'error': 'web_api_disabled'}), media_type='application/json', status_code=503)
    if not _web_rate_allowed(request):
        return Response(content=json.dumps({'ok': False, 'error': 'rate_limit'}), media_type='application/json', status_code=429)
    try:
        payload = await request.json()
    except Exception:
        return Response(content=json.dumps({'ok': False, 'error': 'invalid_json'}), media_type='application/json', status_code=400)
    query = re.sub('\\s+', ' ', str(payload.get('query') or '')).strip()[:WEB_API_MAX_QUERY_CHARS]
    if not query:
        return Response(content=json.dumps({'ok': False, 'error': 'empty_query'}), media_type='application/json', status_code=400)
    shown_urls = payload.get('shown_urls') if isinstance(payload.get('shown_urls'), list) else []
    shown_domains = payload.get('shown_domains') if isinstance(payload.get('shown_domains'), list) else []
    try:
        image_b64, image_mime = _web_more_request_image(payload)
    except ValueError as exc:
        error = str(exc)
        status = 413 if error.startswith('image_too_large') else 400
        return Response(content=json.dumps({'ok': False, 'error': error}), media_type='application/json', status_code=status)
    lang = _web_language(payload.get('lang'))
    country, country_source = await asyncio.to_thread(_web_resolve_request_country, request, payload.get('country'))
    started = time.time()
    result = await asyncio.to_thread(
        _web_more_stores_sync,
        query,
        country,
        lang,
        shown_urls,
        shown_domains,
        image_b64,
        image_mime,
    )
    result['elapsed_ms'] = int((time.time() - started) * 1000)
    result['country_source'] = country_source
    return result

@app.post('/api/search/more/stream')
async def web_api_search_more_stream(request: Request):
    if not WEB_API_ENABLED or not WEB_STREAM_ENABLED:
        return Response(content=json.dumps({'ok': False, 'error': 'web_stream_disabled'}), media_type='application/json', status_code=503)
    if not _web_rate_allowed(request):
        return Response(content=json.dumps({'ok': False, 'error': 'rate_limit'}), media_type='application/json', status_code=429)
    try:
        payload = await request.json()
    except Exception:
        return Response(content=json.dumps({'ok': False, 'error': 'invalid_json'}), media_type='application/json', status_code=400)
    query = re.sub('\\s+', ' ', str(payload.get('query') or '')).strip()[:WEB_API_MAX_QUERY_CHARS]
    if not query:
        return Response(content=json.dumps({'ok': False, 'error': 'empty_query'}), media_type='application/json', status_code=400)
    shown_urls = payload.get('shown_urls') if isinstance(payload.get('shown_urls'), list) else []
    shown_domains = payload.get('shown_domains') if isinstance(payload.get('shown_domains'), list) else []
    try:
        image_b64, image_mime = _web_more_request_image(payload)
    except ValueError as exc:
        error = str(exc)
        status = 413 if error.startswith('image_too_large') else 400
        return Response(content=json.dumps({'ok': False, 'error': error}), media_type='application/json', status_code=status)
    lang = _web_language(payload.get('lang'))
    country, country_source = await asyncio.to_thread(_web_resolve_request_country, request, payload.get('country'))

    async def _generator():
        started = time.time()
        yield _web_stream_event({'event': 'start', 'ok': True, 'mode': 'same_product_more_stores', 'elapsed_ms': 0})
        yield _web_stream_event({'event': 'query', 'query': query, 'market': _web_market(country)})
        task = asyncio.create_task(asyncio.to_thread(
            _web_more_stores_sync,
            query,
            country,
            lang,
            shown_urls,
            shown_domains,
            image_b64,
            image_mime,
        ))
        try:
            while not task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=1.8)
                except asyncio.TimeoutError:
                    yield _web_stream_event({
                        'event': 'status',
                        'stage': 'same_product_more_stores',
                        'elapsed_ms': int((time.time() - started) * 1000),
                    })
            result = await task
            for item in result.get('results') or []:
                yield _web_stream_event({
                    'event': 'result',
                    'phase': 'same_product_more_stores',
                    'market': str(item.get('market') or 'other'),
                    'item': item,
                    'elapsed_ms': int((time.time() - started) * 1000),
                })
                await asyncio.sleep(0.012)
            yield _web_stream_event({
                'event': 'done',
                'count': len(result.get('results') or []),
                'exhausted': bool(result.get('exhausted')),
                'country_source': country_source,
                'elapsed_ms': int((time.time() - started) * 1000),
            })
        except asyncio.CancelledError:
            task.cancel()
            raise
        except Exception as exc:
            print(f'WEB MORE STREAM ERR: {exc}')
            yield _web_stream_event({
                'event': 'error',
                'error': 'more_stores_failed',
                'elapsed_ms': int((time.time() - started) * 1000),
            })

    return StreamingResponse(
        _generator(),
        media_type='application/x-ndjson',
        headers={
            'Cache-Control': 'no-cache, no-transform',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        },
    )

@app.post('/api/search/stream')
async def web_api_search_stream(request: Request):
    if not WEB_API_ENABLED or not WEB_STREAM_ENABLED:
        return Response(content=json.dumps({'ok': False, 'error': 'web_stream_disabled'}), media_type='application/json', status_code=503)
    if not _web_rate_allowed(request):
        return Response(content=json.dumps({'ok': False, 'error': 'rate_limit'}), media_type='application/json', status_code=429)
    try:
        payload = await request.json()
    except Exception:
        return Response(content=json.dumps({'ok': False, 'error': 'invalid_json'}), media_type='application/json', status_code=400)
    query = str(payload.get('query') or '').strip()
    if not query and (not payload.get('selected_option')):
        return Response(content=json.dumps({'ok': False, 'error': 'empty_query'}), media_type='application/json', status_code=400)
    lang = _web_language(payload.get('lang'))
    country, country_source = await asyncio.to_thread(_web_resolve_request_country, request, payload.get('country'))
    selected_option = str(payload.get('selected_option') or '').strip()
    original_query = str(payload.get('original_query') or '').strip()
    force_specific = bool(payload.get('force_specific'))
    client_name = re.sub('[^a-z0-9_-]+', '', str(payload.get('client') or 'web').strip().lower())[:24] or 'web'

    async def _generator():
        started = time.time()
        yield _web_stream_event({'event': 'start', 'ok': True, 'elapsed_ms': 0})
        try:
            prep = await asyncio.to_thread(_web_prepare_stream_query_sync, query, country, lang, selected_option, original_query, force_specific)
            if not prep.get('ok'):
                yield _web_stream_event({'event': 'error', 'error': prep.get('error') or 'bad_query'})
                return
            q = prep['query']
            market = prep['market']
            rtype = prep.get('rtype') or 'SPECIFIC'
            yield _web_stream_event({'event': 'query', 'query': q, 'market': market})
            if rtype == 'GENERIC' and (not force_specific):
                result = await asyncio.to_thread(_web_search_text_sync, q, country, lang, '', '', False)
                yield _web_stream_event({'event': 'recommendations', 'data': result, 'elapsed_ms': int((time.time() - started) * 1000)})
                yield _web_stream_event({'event': 'done', 'elapsed_ms': int((time.time() - started) * 1000)})
                return
            if rtype == 'SERVICE':
                yield _web_stream_event({'event': 'error', 'error': 'service_search_not_enabled_on_web_yet'})
                return
            if rtype == 'NONE':
                yield _web_stream_event({'event': 'error', 'error': 'not_a_product_query'})
                return
            if TEXT_SEARCH_WHATSAPP_PARITY or USE_V106_5_RESULT_PIPELINE or (WEB_MATCH_WHATSAPP_EXACT and (not WEB_TEXT_DENSE_PARITY)):
                final_task = asyncio.create_task(asyncio.to_thread(_web_search_text_sync, q, country, lang, '', '', True))
                while not final_task.done():
                    try:
                        await asyncio.wait_for(asyncio.shield(final_task), timeout=2.0)
                    except asyncio.TimeoutError:
                        yield _web_stream_event({'event': 'status', 'stage': 'whatsapp_engine', 'elapsed_ms': int((time.time() - started) * 1000)})
                final = await final_task
                if final.get('type') == 'recommendations':
                    yield _web_stream_event({'event': 'recommendations', 'data': final, 'elapsed_ms': int((time.time() - started) * 1000)})
                else:
                    exact_rows = final.get('results') or []
                    for item in exact_rows:
                        yield _web_stream_event({'event': 'result', 'phase': 'whatsapp_exact', 'market': str(item.get('market') or 'other'), 'item': item, 'elapsed_ms': int((time.time() - started) * 1000)})
                        await asyncio.sleep(0.005)
                    # One canonical final list prevents browser/app state,
                    # provisional events or client-side de-duplication from
                    # producing a weaker set than WhatsApp.
                    yield _web_stream_event({
                        'event': 'snapshot',
                        'phase': 'whatsapp_text_final',
                        'authoritative': True,
                        'source': 'whatsapp_text_engine',
                        'query': final.get('query') or q,
                        'market': final.get('market') or market,
                        'results': exact_rows,
                        'count': len(exact_rows),
                        'elapsed_ms': int((time.time() - started) * 1000),
                    })
                    _market_counts = Counter(str(row.get('market') or 'other') for row in exact_rows)
                    print(f'TEXT PARITY FINAL client={client_name} count={len(exact_rows)} markets={dict(_market_counts)} engine=whatsapp_text_engine')
                yield _web_stream_event({'event': 'done', 'count': len(final.get('results') or []), 'elapsed_ms': int((time.time() - started) * 1000)})
                return
            sent = set()
            price_tasks, priced_keys = ({}, set())
            final_task = asyncio.create_task(asyncio.to_thread(_web_search_text_sync, q, country, lang, '', '', True))
            if WEB_STREAM_STORE_FIFO and WEB_STREAM_FAST_WAVE and SERPAPI_API_KEY:
                store_tasks = []
                task_meta = {}
                rank_remaining = {0: 0, 1: 0, 2: 0}
                for rank in (0, 2, 1):
                    for label, domain, gl in _web_stream_store_specs(q, country, rank):

                        async def _run_store(r=rank, lab=label, dom=domain, search_gl=gl):
                            try:
                                rows = await asyncio.wait_for(asyncio.to_thread(_web_store_probe_sync, q, country, lang, r, lab, dom, search_gl), timeout=WEB_STREAM_STORE_TIMEOUT)
                                return (r, lab, rows)
                            except Exception as e:
                                print(f'WEB STORE FIFO ERR rank={r} store={lab}: {e}')
                                return (r, lab, [])
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
                        rank, label = task_meta.get(task, (99, 'Store'))
                        try:
                            r, label, items = await task
                        except Exception:
                            r, items = (rank, [])
                        market_name = _web_market_label(r)
                        for item in items or []:
                            key = str(item.get('url') or '').strip() or market_name + '|' + str(item.get('store') or '') + '|' + str(item.get('title') or '')
                            if key in sent:
                                continue
                            sent.add(key)
                            yield _web_stream_event({'event': 'result', 'phase': 'store_fifo', 'market': market_name, 'store_probe': label, 'item': item, 'elapsed_ms': int((time.time() - started) * 1000)})
                            if _web_row_has_numeric_price(item):
                                priced_keys.add(key)
                            else:
                                _web_spawn_price_enrich_task(price_tasks, key, item, lang, market)
                            await asyncio.sleep(0.015)
                        rank_remaining[r] = max(0, rank_remaining.get(r, 1) - 1)
                        if rank_remaining[r] == 0:
                            yield _web_stream_event({'event': 'market_fast_done', 'market': market_name, 'elapsed_ms': int((time.time() - started) * 1000)})
                for task in pending:
                    task.cancel()
                for r in (0, 1, 2):
                    if rank_remaining.get(r, 0) > 0:
                        yield _web_stream_event({'event': 'market_fast_done', 'market': _web_market_label(r), 'elapsed_ms': int((time.time() - started) * 1000)})
            else:
                fast_tasks = []
                if WEB_STREAM_FAST_WAVE and SERPAPI_API_KEY:
                    for rank in (0, 1, 2):

                        async def _run_market(r=rank):
                            try:
                                items = await asyncio.wait_for(asyncio.to_thread(_web_fast_market_wave_sync, q, country, lang, r), timeout=WEB_STREAM_MARKET_TIMEOUT)
                                return (r, items)
                            except Exception as e:
                                print(f'WEB STREAM FAST MARKET ERR rank={r}: {e}')
                                return (r, [])
                        fast_tasks.append(asyncio.create_task(_run_market()))
                pending_fast = set(fast_tasks)
                while pending_fast:
                    done, pending_fast = await asyncio.wait(pending_fast, timeout=0.15, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        rank, items = await task
                        market_name = _web_market_label(rank)
                        for item in items or []:
                            key = str(item.get('url') or '').strip() or market_name + '|' + str(item.get('store') or '') + '|' + str(item.get('title') or '')
                            if key in sent:
                                continue
                            sent.add(key)
                            yield _web_stream_event({'event': 'result', 'phase': 'fast', 'market': market_name, 'item': item, 'elapsed_ms': int((time.time() - started) * 1000)})
                            if _web_row_has_numeric_price(item):
                                priced_keys.add(key)
                            else:
                                _web_spawn_price_enrich_task(price_tasks, key, item, lang, market)
                            await asyncio.sleep(0.01)
                        yield _web_stream_event({'event': 'market_fast_done', 'market': market_name, 'count': len(items or []), 'elapsed_ms': int((time.time() - started) * 1000)})
                    if final_task.done():
                        break
                for task in pending_fast:
                    task.cancel()
            final = await final_task
            if final.get('type') == 'recommendations':
                yield _web_stream_event({'event': 'recommendations', 'data': final, 'elapsed_ms': int((time.time() - started) * 1000)})
            else:
                for item in final.get('results') or []:
                    market_name = str(item.get('market') or 'other')
                    key = str(item.get('url') or '').strip() or market_name + '|' + str(item.get('store') or '') + '|' + str(item.get('title') or '')
                    if _web_row_has_numeric_price(item):
                        priced_keys.add(key)
                        t = price_tasks.pop(key, None)
                        if t:
                            t.cancel()
                    else:
                        _web_spawn_price_enrich_task(price_tasks, key, item, lang, market)
                    if key in sent:
                        yield _web_stream_event({'event': 'upsert', 'phase': 'final', 'market': market_name, 'item': item, 'elapsed_ms': int((time.time() - started) * 1000)})
                    else:
                        sent.add(key)
                        yield _web_stream_event({'event': 'result', 'phase': 'final', 'market': market_name, 'item': item, 'elapsed_ms': int((time.time() - started) * 1000)})
                    await asyncio.sleep(0.01)
            async for _ev in _web_drain_price_enrich_events(price_tasks, priced_keys, started):
                yield _ev
            yield _web_stream_event({'event': 'done', 'count': len(sent), 'elapsed_ms': int((time.time() - started) * 1000)})
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f'WEB STORE FIFO STREAM ERROR: {e}')
            if 'sent' in locals() and sent:
                yield _web_stream_event({'event': 'done', 'count': len(sent), 'partial': True, 'elapsed_ms': int((time.time() - started) * 1000)})
            else:
                yield _web_stream_event({'event': 'error', 'error': 'search_failed', 'elapsed_ms': int((time.time() - started) * 1000)})
    return StreamingResponse(_generator(), media_type='application/x-ndjson', headers={'Cache-Control': 'no-cache, no-transform', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'})

def _web_normalize_uploaded_image_bytes(image_bytes, mime):
    mime = str(mime or 'image/jpeg').strip().lower()
    if mime in ('image/jpeg', 'image/png', 'image/webp'):
        return image_bytes, mime
    if mime in ('image/heic', 'image/heif') or mime.endswith('/heic') or mime.endswith('/heif'):
        if not WEB_HEIC_ENABLED or PILImage is None:
            raise ValueError('heic_support_unavailable')
        with PILImage.open(io.BytesIO(image_bytes)) as im:
            im = im.convert('RGB')
            # iPhone HEIC files can be very large. Resize before JPEG encoding so
            # Lens receives a fast, web-sized image rather than the full camera original.
            max_side = 1800
            if max(im.size) > max_side:
                im.thumbnail((max_side, max_side))
            out = io.BytesIO()
            im.save(out, format='JPEG', quality=90, optimize=True)
            return out.getvalue(), 'image/jpeg'
    raise ValueError('unsupported_image_type')

@app.post('/api/search/image/stream')
async def web_api_image_search_stream(request: Request):
    if not WEB_API_ENABLED or not WEB_STREAM_ENABLED:
        return Response(content=json.dumps({'ok': False, 'error': 'web_stream_disabled'}), media_type='application/json', status_code=503)
    if not _web_rate_allowed(request):
        return Response(content=json.dumps({'ok': False, 'error': 'rate_limit'}), media_type='application/json', status_code=429)
    try:
        payload = await request.json()
    except Exception:
        return Response(content=json.dumps({'ok': False, 'error': 'invalid_json'}), media_type='application/json', status_code=400)
    raw = str(payload.get('image_base64') or '').strip()
    if not raw:
        return Response(content=json.dumps({'ok': False, 'error': 'missing_image'}), media_type='application/json', status_code=400)
    mime = str(payload.get('mime_type') or 'image/jpeg').strip().lower()
    if ',' in raw and raw.lower().startswith('data:image/'):
        raw = raw.split(',', 1)[1]
    try:
        image_bytes = base64.b64decode(raw, validate=True)
    except Exception:
        return Response(content=json.dumps({'ok': False, 'error': 'invalid_image'}), media_type='application/json', status_code=400)
    if not image_bytes or len(image_bytes) > WEB_API_RAW_IMAGE_MAX_BYTES:
        return Response(content=json.dumps({'ok': False, 'error': 'image_too_large'}), media_type='application/json', status_code=413)
    try:
        image_bytes, mime = _web_normalize_uploaded_image_bytes(image_bytes, mime)
    except ValueError as e:
        return Response(content=json.dumps({'ok': False, 'error': str(e)}), media_type='application/json', status_code=400)
    if len(image_bytes) > WEB_API_MAX_IMAGE_BYTES:
        return Response(content=json.dumps({'ok': False, 'error': 'image_too_large_after_convert'}), media_type='application/json', status_code=413)
    image_b64 = base64.b64encode(image_bytes).decode('ascii')
    lang = _web_language(payload.get('lang'))
    country, country_source = await asyncio.to_thread(_web_resolve_request_country, request, payload.get('country'))
    caption = str(payload.get('caption') or '').strip()

    async def _generator():
        started = time.time()
        sent = set()
        price_tasks, priced_keys = ({}, set())
        enrich_market = _web_market(country)
        market_counts = {'local': 0, 'us': 0, 'china': 0}
        yield _web_stream_event({'event': 'start', 'ok': True, 'kind': 'image'})
        yield _web_stream_event({'event': 'status', 'stage': 'identify', 'elapsed_ms': 0})
        try:
            if WEB_MATCH_WHATSAPP_EXACT:
                progress_queue = asyncio.Queue()
                loop = asyncio.get_running_loop()
                market_snapshot = _web_market(country)

                def _lens_progress_callback(partial_lens):
                    if not ANDROID_IMAGE_PROGRESSIVE:
                        return
                    try:
                        loop.call_soon_threadsafe(progress_queue.put_nowait, partial_lens)
                    except Exception as e:
                        print(f'ANDROID PROGRESSIVE QUEUE ERR: {e}')
                final_task = asyncio.create_task(asyncio.to_thread(_web_search_image_sync, image_b64, mime, caption, country, lang, _lens_progress_callback if ANDROID_IMAGE_PROGRESSIVE else None))
                preview_keys = set()
                query_sent = False
                progress_get_task = None
                while True:
                    if final_task.done():
                        break
                    if progress_get_task is None:
                        progress_get_task = asyncio.create_task(progress_queue.get())
                    ready, _ = await asyncio.wait(
                        {final_task, progress_get_task},
                        timeout=1.0,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if not ready:
                        yield _web_stream_event({'event': 'status', 'stage': 'whatsapp_image_engine', 'elapsed_ms': int((time.time() - started) * 1000)})
                        continue
                    final_ready = final_task in ready
                    if progress_get_task not in ready:
                        if final_ready:
                            progress_get_task.cancel()
                            await asyncio.gather(progress_get_task, return_exceptions=True)
                            progress_get_task = None
                            break
                        continue
                    try:
                        partial_lens = progress_get_task.result()
                    finally:
                        progress_get_task = None
                    try:
                        preview_items = await asyncio.to_thread(_run_with_market, market_snapshot, _web_build_lens_items, partial_lens, lang, caption)
                    except Exception as e:
                        print(f'ANDROID PROGRESSIVE BUILD ERR: {e}')
                        preview_items = []
                    if preview_items:
                        preview_query = str(partial_lens.get('relevance_target') or partial_lens.get('query') or caption or '').strip()
                        if preview_query and (not query_sent):
                            yield _web_stream_event({'event': 'query', 'query': preview_query, 'market': market_snapshot})
                            query_sent = True
                        emitted_now = 0
                        for item in preview_items:
                            market_name = str(item.get('market') or 'other')
                            key = str(item.get('url') or '').strip() or market_name + '|' + str(item.get('store') or '') + '|' + str(item.get('title') or '')
                            if key in preview_keys:
                                continue
                            preview_keys.add(key)
                            sent.add(key)
                            emitted_now += 1
                            yield _web_stream_event({'event': 'result', 'phase': 'progressive_preview', 'provisional': True, 'market': market_name, 'item': item, 'elapsed_ms': int((time.time() - started) * 1000)})
                            if _web_row_has_numeric_price(item):
                                priced_keys.add(key)
                            else:
                                _web_spawn_price_enrich_task(price_tasks, key, item, lang, market_snapshot)
                            await asyncio.sleep(0.003)
                        if emitted_now:
                            print(f'ANDROID PROGRESSIVE PREVIEW sent={emitted_now} total_preview={len(preview_keys)} elapsed={time.time() - started:.1f}s')
                    if final_ready:
                        break
                if progress_get_task is not None:
                    progress_get_task.cancel()
                    await asyncio.gather(progress_get_task, return_exceptions=True)
                final = await final_task
                identity = str(final.get('query') or caption or '').strip()
                if identity and (not query_sent):
                    yield _web_stream_event({'event': 'query', 'query': identity, 'market': final.get('market')})
                final_results = list(final.get('results') or [])
                final_exact_results = list(final.get('exact_results') or [])
                final_similar_results = list(final.get('similar_results') or [])
                final_classified_results = list(final.get('all_results') or final_results)
                final_sections = list(final.get('result_sections') or [])
                yield _web_stream_event({'event': 'snapshot', 'phase': 'whatsapp_exact_final', 'authoritative': True, 'layout': 'exact_and_similar_v1', 'classification': 'post_capture_only', 'query': identity, 'market': final.get('market'), 'results': final_results, 'exact_results': final_exact_results, 'similar_results': final_similar_results, 'all_results': final_classified_results, 'result_sections': final_sections, 'exact_count': len(final_exact_results), 'similar_count': len(final_similar_results), 'elapsed_ms': int((time.time() - started) * 1000)})
                print(f'ANDROID PROGRESSIVE FINAL SNAPSHOT results={len(final_results)} exact={len(final_exact_results)} similar={len(final_similar_results)} preview={len(preview_keys)} elapsed={time.time() - started:.1f}s')
                sent = {str(item.get('url') or '').strip() or str(item.get('market') or 'other') + '|' + str(item.get('store') or '') + '|' + str(item.get('title') or '') for item in final_results}
                for item in final_results:
                    key = str(item.get('url') or '').strip() or str(item.get('market') or 'other') + '|' + str(item.get('store') or '') + '|' + str(item.get('title') or '')
                    if _web_row_has_numeric_price(item):
                        priced_keys.add(key)
                        t = price_tasks.pop(key, None)
                        if t:
                            t.cancel()
                    else:
                        _web_spawn_price_enrich_task(price_tasks, key, item, lang, market_snapshot)
                async for _ev in _web_drain_price_enrich_events(price_tasks, priced_keys, started):
                    yield _ev
                yield _web_stream_event({'event': 'done', 'count': len(sent), 'exact_count': len(final_exact_results), 'similar_count': len(final_similar_results), 'elapsed_ms': int((time.time() - started) * 1000)})
                return
            seed = await asyncio.to_thread(_web_image_seed_sync, image_b64, mime, caption, country, lang)
            identity = str(seed.get('query') or caption or '').strip()
            yield _web_stream_event({'event': 'query', 'query': identity, 'market': seed.get('market')})
            for item in seed.get('items') or []:
                market_name = str(item.get('market') or 'other')
                key = str(item.get('url') or '').strip() or market_name + '|' + str(item.get('store') or '') + '|' + str(item.get('title') or '')
                if key in sent:
                    continue
                sent.add(key)
                if market_name in market_counts:
                    market_counts[market_name] += 1
                yield _web_stream_event({'event': 'result', 'phase': 'lens_seed', 'market': market_name, 'item': item, 'elapsed_ms': int((time.time() - started) * 1000)})
                if _web_row_has_numeric_price(item):
                    priced_keys.add(key)
                else:
                    _web_spawn_price_enrich_task(price_tasks, key, item, lang, enrich_market)
                await asyncio.sleep(0.015)
            if identity and WEB_STREAM_STORE_FIFO and WEB_STREAM_FAST_WAVE and SERPAPI_API_KEY:
                store_tasks = []
                task_meta = {}
                rank_remaining = {0: 0, 1: 0, 2: 0}
                for rank in (0, 2, 1):
                    for label, domain, gl in _web_stream_store_specs(identity, country, rank):

                        async def _run_store(r=rank, lab=label, dom=domain, search_gl=gl):
                            try:
                                rows = await asyncio.wait_for(asyncio.to_thread(_web_store_probe_sync, identity, country, lang, r, lab, dom, search_gl), timeout=WEB_STREAM_STORE_TIMEOUT)
                                return (r, lab, rows)
                            except Exception as e:
                                print(f'WEB IMAGE STORE FIFO ERR rank={r} store={lab}: {e}')
                                return (r, lab, [])
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
                        rank, label = task_meta.get(task, (99, 'Store'))
                        try:
                            r, label, rows = await task
                        except Exception:
                            r, rows = (rank, [])
                        market_name = _web_market_label(r)
                        for item in rows or []:
                            key = str(item.get('url') or '').strip() or market_name + '|' + str(item.get('store') or '') + '|' + str(item.get('title') or '')
                            if key in sent:
                                continue
                            sent.add(key)
                            if market_name in market_counts:
                                market_counts[market_name] += 1
                            yield _web_stream_event({'event': 'result', 'phase': 'store_fifo', 'market': market_name, 'store_probe': label, 'item': item, 'elapsed_ms': int((time.time() - started) * 1000)})
                            if _web_row_has_numeric_price(item):
                                priced_keys.add(key)
                            else:
                                _web_spawn_price_enrich_task(price_tasks, key, item, lang, enrich_market)
                            await asyncio.sleep(0.015)
                        rank_remaining[r] = max(0, rank_remaining.get(r, 1) - 1)
                        if rank_remaining[r] == 0:
                            yield _web_stream_event({'event': 'market_fast_done', 'market': market_name, 'elapsed_ms': int((time.time() - started) * 1000)})
                for task in pending:
                    task.cancel()
                for r in (0, 1, 2):
                    if rank_remaining.get(r, 0) > 0:
                        yield _web_stream_event({'event': 'market_fast_done', 'market': _web_market_label(r), 'elapsed_ms': int((time.time() - started) * 1000)})
            if len(sent) < WEB_STREAM_IMAGE_FINAL_MIN_RESULTS or market_counts.get('local', 0) == 0:
                final = await asyncio.to_thread(_web_search_image_sync, image_b64, mime, caption, country, lang)
                for item in final.get('results') or []:
                    market_name = str(item.get('market') or 'other')
                    key = str(item.get('url') or '').strip() or market_name + '|' + str(item.get('store') or '') + '|' + str(item.get('title') or '')
                    if _web_row_has_numeric_price(item):
                        priced_keys.add(key)
                        t = price_tasks.pop(key, None)
                        if t:
                            t.cancel()
                    else:
                        _web_spawn_price_enrich_task(price_tasks, key, item, lang, enrich_market)
                    if key in sent:
                        yield _web_stream_event({'event': 'upsert', 'phase': 'final', 'market': market_name, 'item': item, 'elapsed_ms': int((time.time() - started) * 1000)})
                        continue
                    sent.add(key)
                    yield _web_stream_event({'event': 'result', 'phase': 'final', 'market': market_name, 'item': item, 'elapsed_ms': int((time.time() - started) * 1000)})
                    await asyncio.sleep(0.01)
            async for _ev in _web_drain_price_enrich_events(price_tasks, priced_keys, started):
                yield _ev
            yield _web_stream_event({'event': 'done', 'count': len(sent), 'elapsed_ms': int((time.time() - started) * 1000)})
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f'WEB IMAGE STORE FIFO STREAM ERROR: {e}')
            if 'sent' in locals() and sent:
                yield _web_stream_event({'event': 'done', 'count': len(sent), 'partial': True, 'elapsed_ms': int((time.time() - started) * 1000)})
            else:
                yield _web_stream_event({'event': 'error', 'error': 'image_search_failed', 'elapsed_ms': int((time.time() - started) * 1000)})
    return StreamingResponse(_generator(), media_type='application/x-ndjson', headers={'Cache-Control': 'no-cache, no-transform', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'})

@app.post('/api/search')
async def web_api_search(request: Request):
    if not WEB_API_ENABLED:
        return Response(content=json.dumps({'ok': False, 'error': 'web_api_disabled'}), media_type='application/json', status_code=503)
    if not _web_rate_allowed(request):
        return Response(content=json.dumps({'ok': False, 'error': 'rate_limit'}), media_type='application/json', status_code=429)
    try:
        payload = await request.json()
    except Exception:
        return Response(content=json.dumps({'ok': False, 'error': 'invalid_json'}), media_type='application/json', status_code=400)
    query = str(payload.get('query') or '').strip()
    if not query and (not payload.get('selected_option')):
        return Response(content=json.dumps({'ok': False, 'error': 'empty_query'}), media_type='application/json', status_code=400)
    lang = _web_language(payload.get('lang'))
    country, country_source = await asyncio.to_thread(_web_resolve_request_country, request, payload.get('country'))
    selected_option = str(payload.get('selected_option') or '').strip()
    original_query = str(payload.get('original_query') or '').strip()
    force_specific = bool(payload.get('force_specific'))
    started = time.time()
    result = await asyncio.to_thread(_web_search_text_sync, query, country, lang, selected_option, original_query, force_specific)
    result['elapsed_ms'] = int((time.time() - started) * 1000)
    return result

@app.post('/api/search/image')
async def web_api_image_search(request: Request):
    if not WEB_API_ENABLED:
        return Response(content=json.dumps({'ok': False, 'error': 'web_api_disabled'}), media_type='application/json', status_code=503)
    if not _web_rate_allowed(request):
        return Response(content=json.dumps({'ok': False, 'error': 'rate_limit'}), media_type='application/json', status_code=429)
    try:
        payload = await request.json()
    except Exception:
        return Response(content=json.dumps({'ok': False, 'error': 'invalid_json'}), media_type='application/json', status_code=400)
    raw = str(payload.get('image_base64') or '').strip()
    if not raw:
        return Response(content=json.dumps({'ok': False, 'error': 'missing_image'}), media_type='application/json', status_code=400)
    mime = str(payload.get('mime_type') or 'image/jpeg').strip().lower()
    if ',' in raw and raw.lower().startswith('data:image/'):
        raw = raw.split(',', 1)[1]
    try:
        image_bytes = base64.b64decode(raw, validate=True)
    except Exception:
        return Response(content=json.dumps({'ok': False, 'error': 'invalid_image'}), media_type='application/json', status_code=400)
    if not image_bytes or len(image_bytes) > WEB_API_RAW_IMAGE_MAX_BYTES:
        return Response(content=json.dumps({'ok': False, 'error': 'image_too_large'}), media_type='application/json', status_code=413)
    try:
        image_bytes, mime = _web_normalize_uploaded_image_bytes(image_bytes, mime)
    except ValueError as e:
        return Response(content=json.dumps({'ok': False, 'error': str(e)}), media_type='application/json', status_code=400)
    if len(image_bytes) > WEB_API_MAX_IMAGE_BYTES:
        return Response(content=json.dumps({'ok': False, 'error': 'image_too_large_after_convert'}), media_type='application/json', status_code=413)
    image_b64 = base64.b64encode(image_bytes).decode('ascii')
    lang = _web_language(payload.get('lang'))
    country, country_source = await asyncio.to_thread(_web_resolve_request_country, request, payload.get('country'))
    caption = str(payload.get('caption') or '').strip()
    started = time.time()
    result = await asyncio.to_thread(_web_search_image_sync, image_b64, mime, caption, country, lang)
    result['elapsed_ms'] = int((time.time() - started) * 1000)
    return result

@app.get('/')
async def health():
    return {'status': 'v107.26 SERPAPI COST SAVER NO REGRESSION', 'lens_direct_mode': LENS_DIRECT_MODE, 'fast_lens': USE_FAST_LENS_PIPELINE, 'v106_pipeline': USE_V106_5_RESULT_PIPELINE, 'text_search_whatsapp_parity': TEXT_SEARCH_WHATSAPP_PARITY, 'serpapi_cache': SERPAPI_RESULT_CACHE_ENABLED, 'serpapi_singleflight': SERPAPI_SINGLEFLIGHT_ENABLED, 'build': BUILD_ID, 'market_source': 'phone_prefix_or_explicit_client_country', 'languages': ['ar','en','de','fr','it','es','pt','tr','ru','ja','zh','ko','hi','ur','id','ms']}
