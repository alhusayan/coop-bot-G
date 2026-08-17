# -*- coding: utf-8 -*-
import os, re, time, base64, requests, json, asyncio, urllib.parse, hashlib, sqlite3, threading
from collections import deque, defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Request, Response, BackgroundTasks
from bs4 import BeautifulSoup

app = FastAPI()
BUILD_ID = "v81.9-HYBRID-v81FINAL-exact-v81.7-similar-MANDATORY-store-priority-20260817"


# ===== v77.9 TOP GLOBAL SITES KUWAIT BUYS FROM =====
# بناءً على بيانات الجمارك الكويتية + Google Trends + SimilarWeb GCC 2024-2025
AFFILIATE_CONFIG_TOP = {
    # --- الفئة 1: الأقوى عالمياً وتشحن للكويت مباشرة ---
    "amazon.com": {"cat": "كل شي", "comm": "3-8%", "why": "المرجع رقم 1 للإلكترونيات، شحن مباشر للكويت", "network": "amazon", "template": "https://www.amazon.com/dp/{asin}/?tag={tag}&subid={phone}", "tag": "yourtag-20"},
    "amazon.ae": {"cat": "كل شي", "comm": "3-7%", "why": "أرخص شحن للكويت من .com، وصول 3-5 أيام", "network": "amazon", "template": "https://www.amazon.ae/dp/{asin}/?tag={tag}&subid={phone}", "tag": "yourtag_ae-21"},
    "amazon.sa": {"cat": "كل شي", "comm": "3-7%", "why": "بديل أرخص من ae", "network": "amazon", "template": "https://www.amazon.sa/dp/{asin}/?tag={tag}&subid={phone}", "tag": "yourtag_sa-21"},
    "amazon.co.uk": {"cat": "كل شي", "comm": "5-10%", "why": "أزياء وأدوات أرخص من US", "network": "amazon", "template": "https://www.amazon.co.uk/dp/{asin}/?tag={tag}&subid={phone}", "tag": "yourtag_uk-21"},
    "amazon.de": {"cat": "كل شي", "comm": "5-10%", "why": "أدوات ومكاين ألمانية", "network": "amazon", "template": "https://www.amazon.de/dp/{asin}/?tag={tag}&subid={phone}", "tag": "yourtag_de-21"},

    "aliexpress.com": {"cat": "إلكترونيات/عدد/إكسسوارات", "comm": "5-9%", "why": "رقم 1 في الكويت للقطع والإكسسوارات الرخيصة", "network": "impact/awin", "template": "https://s.click.aliexpress.com/e/_Dm{phone}?aff_fcid={phone}&aff_platform=api", "tag": ""},
    "temu.com": {"cat": "كل شي رخيص", "comm": "10-30% (!!)", "why": "الأعلى عمولة حالياً + إدمان الكويتيات", "network": "impact", "template": "https://temu.com/search_result.html?search_key={query}&subid1={phone}&subid2=coop_bot", "tag": ""},
    "shein.com": {"cat": "أزياء نسائية/أطفال", "comm": "10-15%", "why": "رقم 1 أزياء نسائية في الكويت", "network": "impact", "template": "https://www.shein.com/search/?src_identifier=st%3D2%60sc%3D{query}&subid={phone}", "tag": ""},

    # --- الفئة 2: الأزياء والجمال (أعلى عمولة) ---
    "trendyol.com": {"cat": "أزياء تركية", "comm": "8-15%", "why": "انفجر في الكويت والسعودية 2024، شحن مباشر، أرخص من Zara", "network": "awin", "template": "https://trendyol.com/sr?q={query}&subid={phone}&utm_source=coop_bot", "tag": ""},
    "namshi.com": {"cat": "أزياء رياضية", "comm": "10-15%", "why": "Nike, Adidas, Puma - الكويت تشتري منه أكثر من المول", "network": "arabclicks", "template": "https://arw.ad/p/{pid}?url={url}&subid={phone}", "pid": "YOUR_NAMSHI"},
    "ounass.com": {"cat": "لكجري", "comm": "8-12%", "why": "Gucci, Prada - سلة 300 دينار = 36 دينار عمولة", "network": "arabclicks", "template": "https://arw.ad/p/{pid}?url={url}&subid={phone}", "pid": "YOUR_OUNASS"},
    "6thstreet.com": {"cat": "أزياء", "comm": "8-12%", "why": "بديل Namshi", "network": "arabclicks", "template": "https://arw.ad/p/{pid}?url={url}&subid={phone}", "pid": "YOUR_6TH"},
    "farfetch.com": {"cat": "لكجري", "comm": "10-15%", "why": "أغلى سلة في العالم، عمولة 100+ دينار للطلب", "network": "awin/impact", "template": "https://www.farfetch.com/search/items.aspx?q={query}&subid={phone}&utm_source=coop_bot", "tag": ""},
    "asos.com": {"cat": "أزياء شبابية", "comm": "7-12%", "why": "شعبي جداً عند الشباب الكويتي", "network": "awin", "template": "https://www.asos.com/search/?q={query}&affid={phone}", "tag": ""},
    "stockx.com": {"cat": "أحذية نادرة", "comm": "5-8%", "why": "Nike Jordan, Yeezy - الكويت تدفع 200 دينار للحذاء", "network": "impact", "template": "https://stockx.com/search?s={query}&subid={phone}", "tag": ""},

    # --- الفئة 3: الجمال والصحة (متكرر كل شهر = دخل ثابت) ---
    "sephora.com": {"cat": "مكياج", "comm": "5-10%", "why": "كل بنت كويتية تشتري منه", "network": "impact", "template": "https://www.sephora.com/search?keyword={query}&subid={phone}", "tag": ""},
    "sephora.ae": {"cat": "مكياج", "comm": "5-10%", "why": "شحن أرخص للخليج", "network": "arabclicks", "template": "https://arw.ad/p/{pid}?url={url}&subid={phone}", "pid": "YOUR_SEPHORA"},
    "iherb.com": {"cat": "مكملات/فيتامينات", "comm": "10-15%", "why": "رقم 1 مكملات في الكويت، طلب متكرر كل شهر", "network": "impact", "template": "https://www.iherb.com/search?kw={query}&rcode={tag}&subid={phone}", "tag": "YOUR_IHERB"},
    "lookfantastic.com": {"cat": "عناية", "comm": "8-12%", "why": "Dyson, Olaplex - شحن مجاني للكويت", "network": "awin", "template": "https://www.lookfantastic.com/search/?q={query}&subid={phone}", "tag": ""},
    "cultbeauty.com": {"cat": "عناية", "comm": "8-12%", "why": "بديل Lookfantastic", "network": "awin", "template": "https://www.cultbeauty.com/search/?q={query}&subid={phone}", "tag": ""},

    # --- الفئة 4: الإلكترونيات والعدد ---
    "ebay.com": {"cat": "كل شي مستعمل/جديد", "comm": "4-6%", "why": "قطع غيار ومكاين نادرة", "network": "ebay", "template": "https://www.ebay.com/sch/i.html?_nkw={query}&campid={camp}&customid={phone}", "camp": "YOUR_EBAY"},
    "newegg.com": {"cat": "كمبيوتر/قطع", "comm": "2-5%", "why": "لعشاق الـ Gaming PC في الكويت", "network": "impact", "template": "https://www.newegg.com/p/pl?d={query}&subid={phone}", "tag": ""},
    "banggood.com": {"cat": "عدد/إلكترونيات", "comm": "5-9%", "why": "بديل AliExpress للعدد", "network": "impact", "template": "https://www.banggood.com/search/{query}.html?subid={phone}", "tag": ""},

    # --- الفئة 5: المحلي القوي (لازم تربطه) ---
    "noon.com": {"cat": "كل شي خليجي", "comm": "4-9%", "why": "أمازون الخليج", "network": "arabclicks", "template": "https://arw.ad/p/{pid}?url={url}&subid={phone}", "pid": "YOUR_NOON"},
    "xcite.com": {"cat": "إلكترونيات كويت", "comm": "2-4% + بونص", "why": "أكبر متجر إلكترونيات بالكويت", "network": "direct", "template": "{url}?ref=coop_bot&subid={phone}", "pid": ""},
    "boutiqaat.com": {"cat": "عطور/جمال", "comm": "10-20%", "why": "أعلى عمولة محلية", "network": "direct", "template": "{url}?ref=coop_bot&subid={phone}", "pid": ""},
}

# ===== v81.9 MANDATORY STORE PRIORITY =========================================
# طلب المالك: إذا وُجدت نتيجة مطابقة في أحد هذه المتاجر، تظهر قبل أي متجر غير موجود
# في القائمة وبنفس ترتيب القائمة أدناه. فلتر مطابقة المنتج يظل يعمل أولاً دائماً،
# لذلك الأولوية لا تسمح لموديل مختلف/إكسسوار أن يتجاوز نتيجة مطابقة من متجر آخر.
MANDATORY_PRIORITY_STORES = (
    "amazon.com",
    "amazon.ae",
    "amazon.sa",
    "amazon.co.uk",
    "amazon.de",
    "aliexpress.com",
    "temu.com",
    "shein.com",
    "trendyol.com",
    "namshi.com",
    "ounass.com",
    "6thstreet.com",
    "farfetch.com",
    "asos.com",
    "stockx.com",
    "sephora.com",
    "sephora.ae",
    "iherb.com",
    "lookfantastic.com",
    "cultbeauty.com",
    "ebay.com",
    "newegg.com",
    "banggood.com",
    "noon.com",
    "xcite.com",
    "boutiqaat.com",
)
MANDATORY_PRIORITY_INDEX = {domain: i for i, domain in enumerate(MANDATORY_PRIORITY_STORES)}
MANDATORY_PRIORITY_PROMPT = ", ".join(MANDATORY_PRIORITY_STORES)

# دالة تختار أفضل متجر عالمي حسب المنتج
def pick_best_global_stores(query):
    q = query.lower()
    if any(x in q for x in ["فستان","تيشرت","حذاء","شنطة","zara","nike","adidas","dress","shoe","bag"]):
        return ["trendyol.com","namshi.com","shein.com","farfetch.com","asos.com"]
    if any(x in q for x in ["مكياج","عطر","dyson","makeup","perfume","sephora"]):
        return ["sephora.ae","lookfantastic.com","cultbeauty.com","iherb.com","boutiqaat.com"]
    if any(x in q for x in ["مكمل","فيتامين","بروتين","iherb","supplement"]):
        return ["iherb.com","amazon.ae","amazon.com"]
    if any(x in q for x in ["مكينة","مولد","ecoflow","jackery","drill","tool"]):
        return ["amazon.com","amazon.ae","aliexpress.com","ebay.com","banggood.com"]
    # عام
    return ["amazon.ae","temu.com","aliexpress.com","noon.com","trendyol.com"]


# ===== v77.8 AFFILIATE SYSTEM - LOCAL + GLOBAL =====
# شبكات: ArabClicks, Impact.com, Awin, CJ, Amazon Associates
AFFILIATE_CONFIG = {
    # محلي خليجي
    "noon.com": {"network": "arabclicks", "template": "https://arw.ad/p/{pid}?url={url}&subid={phone}&source=coop_bot_global", "pid": "YOUR_NOON_PID"},
    "namshi.com": {"network": "arabclicks", "template": "https://arw.ad/p/{pid}?url={url}&subid={phone}", "pid": "YOUR_NAMSHI_PID"},
    "ounass.com": {"network": "arabclicks", "template": "https://arw.ad/p/{pid}?url={url}&subid={phone}", "pid": "YOUR_OUNASS_PID"},
    "6thstreet.com": {"network": "arabclicks", "template": "https://arw.ad/p/{pid}?url={url}&subid={phone}", "pid": "YOUR_6TH_PID"},
    "xcite.com": {"network": "direct", "template": "{url}?ref=coop_bot&utm_source=whatsapp&subid={phone}", "pid": ""},
    "eureka.com.kw": {"network": "direct", "template": "{url}?ref=coop_bot&subid={phone}", "pid": ""},
    
    # عالمي - Amazon
    "amazon.com": {"network": "amazon", "template": "https://www.amazon.com/dp/{asin}/?tag={tag}&linkCode=ll1&subid={phone}", "tag": "yourtag-20"},
    "amazon.ae": {"network": "amazon", "template": "https://www.amazon.ae/dp/{asin}/?tag={tag}&linkCode=ll1&subid={phone}", "tag": "yourtag_ae-21"},
    "amazon.sa": {"network": "amazon", "template": "https://www.amazon.sa/dp/{asin}/?tag={tag}&linkCode=ll1&subid={phone}", "tag": "yourtag_sa-21"},
    "amazon.co.uk": {"network": "amazon", "template": "https://www.amazon.co.uk/dp/{asin}/?tag={tag}&linkCode=ll1&subid={phone}", "tag": "yourtag_uk-21"},
    
    # عالمي - Impact.com / Awin
    "aliexpress.com": {"network": "impact", "template": "https://aliexpress.com/item/{id}.html?aff_fcid={phone}&aff_fsk={phone}&aff_platform=api&aff_trace_key={phone}&utm_source=coop_bot", "pid": ""},
    "temu.com": {"network": "impact", "template": "https://temu.com/search_result.html?search_key={query}&refer_page_el_sn=200891&refer_page_name=search_result&refer_page_id=10009&tm_ref=search_result&srch_enter_method=top_search&from_share=1&subid1={phone}&subid2=coop_bot", "pid": ""},
    "shein.com": {"network": "impact", "template": "https://www.shein.com/search/?src_identifier=st%3D2%60sc%3D{query}%60sr%3D0%60ps%3D1&subid={phone}", "pid": ""},
    "ebay.com": {"network": "ebay", "template": "https://www.ebay.com/itm/{id}?campid={camp}&customid={phone}&mkcid=1&mkrid=711-53200-19255-0&siteid=0&toolid=10001&mkevt=1", "camp": "YOUR_EBAY_CAMP"},
    "walmart.com": {"network": "impact", "template": "https://www.walmart.com/ip/{id}?irgwc=1&sourceid=imp_{phone}&veh=aff&wmlspartner={phone}", "pid": ""},
    "bestbuy.com": {"network": "impact", "template": "{url}&ref=374&loc=01&irgwc=1&af=coop_bot&subid={phone}", "pid": ""},
}

def extract_asin(url):
    try:
        import re
        m = re.search(r"/dp/([A-Z0-9]{10})|/product/([A-Z0-9]{10})|/gp/product/([A-Z0-9]{10})", url, re.I)
        if m:
            for g in m.groups():
                if g:
                    return g
        # AliExpress ID
        m = re.search(r"/item/(\d+)\.html", url)
        if m:
            return m.group(1)
    except:
        pass
    return ""

def wrap_affiliate_url(original_url, phone, query=""):
    """تحويل أي رابط محلي أو عالمي لرابط أفلييت مع SubID = رقم الزبون"""
    if not original_url or not original_url.startswith("http"):
        return original_url
    try:
        import urllib.parse
        host = _host_of(original_url).lower()
        phone_clean = re.sub(r"[^0-9]", "", str(phone))[-10:]  # آخر 10 أرقام للتتبع
        
        for domain_key, cfg in AFFILIATE_CONFIG.items():
            if domain_key in host or domain_key.replace(".com","") in host:
                template = cfg.get("template","")
                asin = extract_asin(original_url)
                # بناء الرابط
                aff_url = template.format(
                    url=urllib.parse.quote(original_url, safe=""),
                    phone=phone_clean,
                    tag=cfg.get("tag",""),
                    pid=cfg.get("pid",""),
                    camp=cfg.get("camp",""),
                    asin=asin or "",
                    id=asin or "",
                    query=urllib.parse.quote(query or "", safe="")
                )
                # إذا القالب ما فيه asin وكان مطلوب، رجع الأصلي + باراميتر
                if "{asin}" in template and not asin:
                    aff_url = original_url + (f"&tag={cfg.get('tag','')}" if "amazon" in host else f"?subid={phone_clean}")
                print(f"AFFILIATE WRAP: {host} -> {cfg['network']} -> {aff_url[:100]}")
                return aff_url
        
        # إذا المتجر مو في القائمة، أضف باراميتر تتبع عام
        sep = "&" if "?" in original_url else "?"
        return f"{original_url}{sep}ref=coop_bot&subid={phone_clean}&utm_source=whatsapp_global"
    except Exception as e:
        print(f"AFFILIATE WRAP ERR: {e}")
        return original_url

def log_click(phone, query, store_name, original_url, affiliate_url, is_global=False):
    """سجل كل كليك عشان تعرف من وين تجي الفلوس"""
    try:
        # هنا تحفظ في Supabase / Postgres / حتى ملف
        # مثال: supabase.table("clicks").insert({...})
        print(f"CLICK LOG: phone={phone} query={query} store={store_name} global={is_global} url={affiliate_url[:80]}")
    except:
        pass

print("=" * 70)
print(f"STARTING COOP BOT BUILD: {BUILD_ID}")
print("IMAGE -> GOOGLE LENS DIRECT PASSTHROUGH (raw results to user)")
print("TEXT EXACT MATCH -> v81-FINAL | SIMILAR ALTERNATIVES -> v81.7")
print("SERVICES -> AT LEAST 5 PROVIDERS WITH PHONE NUMBERS")
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

def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")

processed_ids = deque(maxlen=1000)
IMAGE_BUFFER = defaultdict(lambda: {"images": [], "time": 0, "bot_id": ""})
LAST_SEARCH = {}
USER_LANG = {}
# اللغة والموقع يُطلبان في أول استخدام. الموقع يُجدَّد كل 3 أيام.
USER_MARKET = {}
USER_LOCATION_TS = {}
PENDING_ONBOARDING = {}
PENDING_GLOBAL_SEARCH = {}
# v72: نتائج Lens الأجنبية تُحفظ هنا ولا تُعرض إلا بعد موافقة المستخدم بزر.
PENDING_LENS_FOREIGN = {}
# v73: نتائج برامج التواصل (انستجرام/تيك توك/سناب...) تُحفظ هنا وتُعرض بعد سؤال منفصل.
PENDING_LENS_SOCIAL = {}
# v81.5: بقية بطاقات اللينز لصفحات «عرض المزيد».
PENDING_LENS_MORE = {}
# v81.5: بقية بطاقات اللينز غير المعروضة — زر «عرض المزيد» يسحب منها دفعة دفعة.
PENDING_LENS_MORE = {}
SOCIAL_HOSTS = (
    "instagram.com", "tiktok.com", "snapchat.com", "youtube.com", "youtu.be",
    "pinterest.", "facebook.com", "fb.com", "fb.watch", "x.com", "twitter.com",
    "threads.net", "reddit.com",
)
# v74: مواقع ليست متاجر أصلاً — تُرفض قبل حتى سؤال الذكاء الاصطناعي.
NON_SHOP_HOSTS = (
    "wikipedia.", "wikihow.", "fandom.com", "quora.com", "medium.com",
    "blogspot.", "wordpress.", "tumblr.", "imdb.com", "tripadvisor.",
    "yelp.", "github.", "stackoverflow.", "stackexchange.", "britannica.",
    "cnn.", "bbc.", "nytimes.", "aljazeera.", "alarabiya.", "reuters.",
    "alraimedia.", "alqabas.", "kooora.", "goal.com", "issuu.com", "scribd.com",
    "slideshare.", "researchgate.", "academia.edu",
)
ENABLE_SHOP_AI_FILTER = env_bool("ENABLE_SHOP_AI_FILTER", True)
# v74: مقارنة البراندات للطلب العام — خيارات المستخدم المعلقة للاختيار من القائمة.
PENDING_BRAND_PICKS = {}
# v75: السلة الموحدة — مقارنة السلة كاملة عبر المتاجر واختيار متجر واحد.
PENDING_CART_PICKS = {}
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

OLD_LAYER_ENABLED = env_bool("OLD_LAYER_ENABLED", True)

# ---- v74.2: محرك v26 القديم (المسار الذكي الكامل) لخيار «بدائل مشابهة» -------
# بطولة داخلية: SEARCH_RUNS بحوث متوازية لنفس الطلب، نقيّمها كلها ونرسل الأقوى،
# واللنكات اتحاد لنكات كل الجولات (أولوية لنكات الجواب الفائز) — طريقة v26 بالضبط.
SEARCH_RUNS = int(os.environ.get("SEARCH_RUNS", "4"))
V26_SEARCH_POOL = ThreadPoolExecutor(max_workers=8)

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
# v81.7: بحث نصي أوفر — 6 محلي + 6 عالمي = 12 مرشحاً؛ أول 8 تظهر والباقي خلف «عرض المزيد».
TEXT_LOCAL_RESULTS = max(4, int(os.environ.get("TEXT_LOCAL_RESULTS", "6")))
TEXT_GLOBAL_RESULTS = max(4, int(os.environ.get("TEXT_GLOBAL_RESULTS", "6")))
TEXT_TOTAL_RESULTS = TEXT_LOCAL_RESULTS + TEXT_GLOBAL_RESULTS
TEXT_FIRST_PAGE = max(6, int(os.environ.get("TEXT_FIRST_PAGE", "8")))
# v76: البدائل المشابهة لها سقف مستقل وأكبر من نتائج المنتج العادية.
SIMILAR_MAX_STORES = max(MAX_STORES, int(os.environ.get("SIMILAR_MAX_STORES", "10")))
SIMILAR_LENS_TITLE_LIMIT = max(8, int(os.environ.get("SIMILAR_LENS_TITLE_LIMIT", "24")))
ENABLE_LENS_CONSENSUS_AI = env_bool("ENABLE_LENS_CONSENSUS_AI", True)
MAX_URLS_MERGED = int(os.environ.get("MAX_URLS_MERGED", "8"))
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
# v71: وضع اللينز المباشر — الصورة تروح لـ Google Lens ونتائجه تُرسل للمستخدم كما هي،
# بدون تحليل Vision ولا حكم هوية ولا طبقات بحث. أطفئه بـ LENS_DIRECT_MODE=false
# لإرجاع المسار الذكي الكامل. عند عدم وجود نتائج، البوت يرجع تلقائياً للمسار الكامل.
LENS_DIRECT_MODE = env_bool("LENS_DIRECT_MODE", True)
LENS_DIRECT_MAX_LINES = max(3, int(os.environ.get("LENS_DIRECT_MAX_LINES", "8")))
# v72.2: تنويع المتاجر في بطاقات CTA — حد أقصى من البطاقات لكل متجر واحد.
LENS_PER_STORE_MAX = max(1, int(os.environ.get("LENS_PER_STORE_MAX", "2")))
# v74.12: عدد بطاقات نتائج العدسة مستقل عن MAX_STORES — افتراضي 8 (يُضبط من Railway).
LENS_MAX_CARDS = max(int(os.environ.get("MAX_STORES", "5")), int(os.environ.get("LENS_MAX_CARDS", "8")))
# v72.3: البطاقات التي بلا سعر من Google نجلب سعرها من صفحة المتجر مباشرة (مجاني).
LENS_PRICE_FETCH_MAX = max(0, int(os.environ.get("LENS_PRICE_FETCH_MAX", "8")))
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
# v81.2: صمود اللينز — تطبيق Lens يلقى المنتج وبوتنا يقول «ما فيه»؟ هذا يمنعه:
# تمريرات بالتوازي + إعادة محاولة عند الصفر + محرك Vision الرسمي احتياط مستقل.
LENS_HTTP_TIMEOUT = max(30, int(os.environ.get("LENS_HTTP_TIMEOUT", "75")))
LENS_PASS_POOL = ThreadPoolExecutor(max_workers=3)
LENS_RETRY_ON_EMPTY = env_bool("LENS_RETRY_ON_EMPTY", True)
# auto = SerpApi أولاً و Vision احتياط | vision = الرسمي فقط | serpapi = القديم فقط
IMAGE_ID_ENGINE = os.environ.get("IMAGE_ID_ENGINE", "auto").strip().lower()
GOOGLE_VISION_API_KEY = (os.environ.get("GOOGLE_VISION_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")).strip()

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

# v71.2: اسم البلد بالعربي — يُرسل كنص مع الصورة إلى Google Lens (نفس حركة كتابة
# «الكويت» في مربع بحث Lens) فترجّح النتائج متاجرَ نفس البلد.
COUNTRY_NAMES_AR = {
    "kw": "الكويت", "sa": "السعودية", "ae": "الإمارات", "bh": "البحرين", "qa": "قطر",
    "om": "عمان", "iq": "العراق", "jo": "الأردن", "lb": "لبنان", "eg": "مصر",
    "sy": "سوريا", "ye": "اليمن", "ps": "فلسطين", "ma": "المغرب", "dz": "الجزائر",
    "tn": "تونس", "ly": "ليبيا", "sd": "السودان", "tr": "تركيا",
}

def country_hint_word(lang="ar"):
    """كلمة البلد التي تُلحق بطلب Lens: عربية للمستخدم العربي، وإلا الاسم الإنجليزي."""
    m = current_market()
    cc = (m.get("country") or DEFAULT_COUNTRY).lower()
    if lang == "ar":
        return COUNTRY_NAMES_AR.get(cc) or m.get("country_name") or ""
    return m.get("country_name") or ""

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
    f"google_shopping={ENABLE_GOOGLE_SHOPPING} immersive_max={IMMERSIVE_LOOKUPS_MAX} "
    f"similar_v26_runs={SEARCH_RUNS} similar_max={SIMILAR_MAX_STORES} "
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
    return hashlib.sha256(f"v81.9-priority-stores|{market}|{norm}|{lang}".encode()).hexdigest()

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
        "cart_comparing": "🧺 لقيت {c} أصناف.. أقارن لك السلة كاملة في المتاجر وأشوف وين تطلع أوفر وأسهل!",
        "cart_summary_header": "🧺 مقارنة سلتك ({c} أصناف) حسب المتجر — الأشمل ثم الأوفر:",
        "cart_pick_prompt": "اختر متجراً وأرسل لك كل أصنافك بروابطها المباشرة داخله — طلبية وحدة وسلة وحدة 👇",
        "cart_store_button": "اختر متجر",
        "cart_from_store": "🧺 سلتك من {s}:",
        "cart_total": "💰 مجموع السلة: {t}",
        "cart_missing": "⚠️ غير متوفر في هذا المتجر: {items}",
        "cart_expired": "قائمة السلة قدمت 😅 دز قائمة الأصناف من جديد وأجهزها لك على طول.",
        "cart_session_tip": "💡 المهم: أضف الصنف الأول من الزر، وبعدها دوّر باقي الأصناف من بحث المتجر *بنفس الصفحة* — لا ترجع لواتساب بين كل صنف عشان تتراكم كلها في سلة وحدة.",
        "cart_checklist": "📋 أصنافك في {s} — انسخ أو دوّر عليها داخل المتجر:",
        "cart_complete_from": "🧩 تكملة الأصناف الناقصة من {s}:",
        "cart_plan_total": "💰 مجموع الخطة كاملة: {t}",
        "cart_not_anywhere": "⛔ ما لقيتها في أي متجر بالقائمة: {items}",
        "multi_images": "تمام لقطت {c} منتجات، أسوي سلة...",
        "maps_body": "📍 تبي أقرب مكان؟\n\nاضغط الزر والخريطة بتفتح على أقرب الأماكن حولك 👇",
        "maps_btn": "📍 افتح الخريطة",
        "maps_body_loc": "📍 بحثك الأخير كان عن ({p})\n\nجهزت لك أقرب الأماكن حولك، اضغط الزر وافتح الخريطة 👇",
        "no_saved_product": "ما عندي منتج محفوظ حالياً 😅. ابحث عن منتج أول، وبعدها أدلك على أقرب مكان يبيعه!",
        "lang_saved": "تمام، بكلمك عربي من هني ورايح 🇰🇼\nدز صورة منتج أو اكتب اسمه وأنا حاضر!",
        "ask_global": "ما لقيت نتيجة محلية مؤكدة لهذا المنتج في موقعك الحالي. تبي أدور لك في المتاجر العالمية؟ 🌍",
        "ask_global_after_local": "لقيت لك النتائج المحلية فوق 👆\nتبي أدور لك نفس المنتج في المتاجر العالمية أيضاً؟ 🌍",
        "ask_global_after_local_en": "Found local results above 👆 Want me to also search international stores for the same product? 🌍",
        "global_yes": "نعم، ابحث عالميًا 🌍",
        "global_no": "لا، محلي فقط",
        "global_searching": "🌍 أدور لك عالميًا على أفضل النتائج المطابقة...",
        "global_none": "حتى بالبحث العالمي ما لقيت نتيجة مؤكدة ومباشرة لهذا المنتج.",
        "ask_not_found": "ما لقيت نفس المنتج بالضبط متوفر عندك محلياً 😅\n\nشرايك، وش تبيني أسوي؟ 👇",
        "opt_global": "🌍 دوّر لي عالمياً",
        "opt_similar": "🔄 أبي بدائل مشابهة",
        "opt_no": "لا شكراً 🙏",
        "similar_searching": "🔄 أدور لك على أفضل البدائل المشابهة المتوفرة عندك...",
        "similar_none": "ما لقيت بدائل مشابهة بسعر مؤكد حالياً 😅 جرب صياغة ثانية.",
        "declined_ok": "تمام 🙏 إذا احتجت شي ثاني أنا حاضر!",
        "more_results_body": "عندي {n} نتائج إضافية 👇",
        "more_results_btn": "➕ عرض المزيد ({n})",
        "more_results_done": "هذي كل النتائج ✅",
        "more_results_expired": "النتائج القديمة قدمت 😅 أعد البحث من جديد.",
        "welcome_reply": "هلا والله! 🌟\nدز صورة المنتج أو اكتب اسمه، وأدور لك أفضل الأسعار والمتاجر القريبة منك 🛒",
        "thanks_reply": "العفو! 🌹 في الخدمة دايماً.. أي منتج ثاني تبيه أنا حاضر!",
        "lens_header": "🔍 هذا اللي طلع من Google عن صورتك:",
        "lens_local_header": "🔍 نتائج {country} من Google لصورتك:",
        "lens_foreign_ask": "🌍 عندي {c} نتائج إضافية من متاجر خارج {country}.\nتبي أعرضها لك؟ 👇",
        "lens_no_local": "ما لقيت نتائج من متاجر داخل {country} لهالصورة 😅\nعندي {c} نتائج من متاجر عالمية 🌍.\nوش تبي؟ 👇",
        "lens_social_ask": "📱 لقيت للمنتج نتائج في برامج التواصل (انستجرام، تيك توك، سناب...).\nتبي أعرضها لك؟ 👇",
        "ls_show": "اعرضها 📱",
        "ls_skip": "لا شكراً 🙏",
        "opt_social": "📱 عروض التواصل",
        "opt_map": "📍 وين أقرب محل؟",
        "options_button": "خيارات إضافية",
        "more_options_ask": "تبي شي ثاني؟ عندي لك خيارات إضافية 👇",
        "social_none": "ما لقيت عروض للمنتج في برامج التواصل حالياً 😅",
        "no_local_generic": "ما لقيت نتائج من متاجر محلية لهالصورة 😅 وش تبي أسوي؟ 👇",
        "compare_searching": "⚖️ طلبك عام بدون ماركة محددة.. أسوي لك مقارنة بين أفضل البراندات المتوفرة!",
        "pick_prompt": "اختر منتجاً من القائمة وأدور لك أفضل الأسعار المتوفرة 👇",
        "list_button": "اختر منتج",
        "lens_foreign_header": "🌍 النتائج العالمية (الأسعار محوّلة لعملتك عند الإمكان):",
        "lf_show": "اعرضها 🌍",
        "lf_skip": "لا شكراً 🙏",
        "lens_none": "Google ما رجّع نتائج للصورة 😅 أكمل البحث بطريقتي...",
        "more_results_body": "عندي {n} نتائج إضافية لنفس الصورة 👇",
        "more_results_btn": "➕ عرض المزيد ({n})",
        "more_results_done": "هذي كل النتائج ✅",
        "more_results_expired": "النتائج قدمت 😅 دز الصورة من جديد وأجيبها لك على طول.",
        "chat_redirect": "أنا حاضر ومعك! 🙌\nدز اسم المنتج أو صورته وأدور لك أفضل الأسعار، أو اكتب طلب الخدمة اللي تحتاجها 🛒",
    },
    "en": {
        "identifying": "One sec.. identifying the product and finding you the best deal!",
        "searching": "🔍 Looking up {q}...",
        "not_found": "Couldn't find it in-stock with a verified price 😅 try another phrasing or a clearer photo.",
        "identified_not_found": "I identified the product ({p}) but couldn't find a verified price right now 😅 try typing its name differently.",
        "cant_identify": "I searched several times but couldn’t identify the product or find a verified result. Send a clearer photo or type the product name.",
        "image_error": "Something went wrong while loading the image 😅 please send it again.",
        "multi_text": "Got it, found {c} products. Building your cart...",
        "cart_comparing": "🧺 Found {c} items.. comparing your full basket across stores to find the cheapest one-stop option!",
        "cart_summary_header": "🧺 Your basket ({c} items) by store — best coverage then cheapest:",
        "cart_pick_prompt": "Pick a store and I'll send all your items with direct links inside it — one order, one cart 👇",
        "cart_store_button": "Pick store",
        "cart_from_store": "🧺 Your cart from {s}:",
        "cart_total": "💰 Basket total: {t}",
        "cart_missing": "⚠️ Not available at this store: {items}",
        "cart_expired": "That basket list expired 😅 send your items again and I'll rebuild it right away.",
        "cart_session_tip": "💡 Important: add the first item from the button, then find the rest via the store's own search *in the same page* — don't switch back to WhatsApp between items so everything stacks in one cart.",
        "cart_checklist": "📋 Your items at {s} — copy or search them inside the store:",
        "cart_complete_from": "🧩 Completing the missing items from {s}:",
        "cart_plan_total": "💰 Full plan total: {t}",
        "cart_not_anywhere": "⛔ Not found in any listed store: {items}",
        "multi_images": "Nice, spotted {c} products. Building your cart...",
        "maps_body": "📍 Want the nearest place?\n\nTap the button and the map will open on the closest spots around you 👇",
        "maps_btn": "📍 Open Map",
        "maps_body_loc": "📍 Your last search was ({p})\n\nI've lined up the closest places around you. Tap the button to open the map 👇",
        "no_saved_product": "I don't have a saved product yet 😅. Search for a product first, then I'll point you to the nearest store!",
        "lang_saved": "Great, I'll speak English with you from now on 🇬🇧\nSend a product photo or type its name and I'm on it!",
        "ask_global": "I couldn't find a verified local result in your current market. Search international stores instead? 🌍",
        "ask_global_after_local": "Found local results above 👆 Want me to also search international stores for the same product? 🌍",
        "global_yes": "Yes, search globally 🌍",
        "global_no": "No, local only",
        "global_searching": "🌍 Searching international stores for the closest matches...",
        "global_none": "I still couldn't find a verified direct result globally.",
        "ask_not_found": "I couldn't find this exact product available locally 😅\n\nWhat would you like me to do? 👇",
        "opt_global": "🌍 Search worldwide",
        "opt_similar": "🔄 Show similar options",
        "opt_no": "No thanks 🙏",
        "similar_searching": "🔄 Looking for the best similar alternatives available near you...",
        "similar_none": "I couldn't find similar alternatives with a verified price right now 😅 try another phrasing.",
        "declined_ok": "No problem 🙏 I'm here whenever you need me!",
        "more_results_body": "I have {n} more results 👇",
        "more_results_btn": "➕ Show more ({n})",
        "more_results_done": "That's all the results ✅",
        "more_results_expired": "Those results expired 😅 search again.",
        "welcome_reply": "Hello! 🌟\nSend a product photo or type its name, and I'll find you the best prices and nearby stores 🛒",
        "thanks_reply": "You're welcome! 🌹 Anytime.. just send me the next product!",
        "lens_header": "🔍 Here's what Google returned for your photo:",
        "lens_local_header": "🔍 {country} results from Google for your photo:",
        "lens_foreign_ask": "🌍 I also have {c} results from stores outside {country}.\nWant me to show them? 👇",
        "lens_no_local": "No results from stores inside {country} for this photo 😅\nI have {c} international results 🌍.\nWhat would you like? 👇",
        "lens_social_ask": "📱 I also found results for this product on social media (Instagram, TikTok, Snapchat...).\nWant me to show them? 👇",
        "ls_show": "Show them 📱",
        "ls_skip": "No thanks 🙏",
        "opt_social": "📱 Social offers",
        "opt_map": "📍 Nearest store?",
        "options_button": "More options",
        "more_options_ask": "Anything else? I have more options 👇",
        "social_none": "No social media offers found for this product right now 😅",
        "no_local_generic": "No local store results for this photo 😅 What would you like me to do? 👇",
        "compare_searching": "⚖️ Your request is generic with no brand.. building a comparison of the best available brands!",
        "pick_prompt": "Pick a product from the list and I'll find the best available prices 👇",
        "list_button": "Choose",
        "lens_foreign_header": "🌍 International results (prices converted to your currency when possible):",
        "lf_show": "Show them 🌍",
        "lf_skip": "No thanks 🙏",
        "lens_none": "Google returned no results for the photo 😅 continuing with my own search...",
        "more_results_body": "I have {n} more results for the same photo 👇",
        "more_results_btn": "➕ Show more ({n})",
        "more_results_done": "That's all the results ✅",
        "more_results_expired": "Those results expired 😅 resend the photo and I'll fetch them right away.",
        "chat_redirect": "I'm here with you! 🙌\nSend a product name or photo and I'll find the best prices, or type the service you need 🛒",
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
أنت مساعد تسوق كويتي. استخدم بحث Google فعلياً للأسعار والتقييمات الحالية في الكويت.

أولاً حدد نوع الطلب:

【الحالة 1】منتج محدد بعلامة تجارية واضحة (مثل: آيفون 15 برو، بيبسي، ساعة أبل الترا، بلايستيشن 5):
قارن الأسعار ورتب النتائج دائماً من الأرخص إلى الأغلى، ورد بهذا الشكل فقط:
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
ابحث بعمق وأعطني 5 مزودي خدمة على الأقل (وأكثر إذا وجدت)، مرتبين من الأعلى تقييماً إلى الأقل، بهذا الشكل المرتب بالضبط:
📦 [وصف الخدمة + المنطقة]

🏆 [اسم أفضل مزود] (هاتف: [الرقم]) — [المنطقة] — [السعر إن وجد] د.ك ⭐ [التقييم]
• [مزود ثاني] (هاتف: [الرقم]) — [المنطقة] — [السعر إن وجد] ⭐ [التقييم]
• [مزود ثالث] (هاتف: [الرقم]) — [المنطقة] ⭐ [التقييم]
• [مزود رابع] (هاتف: [الرقم]) — [المنطقة] ⭐ [التقييم]
• [مزود خامس] (هاتف: [الرقم]) — [المنطقة] ⭐ [التقييم]
⛔ قاعدة صارمة جداً للأرقام: لا تكتب أي رقم هاتف إلا إذا ظهر حرفياً في نتائج البحث. لا تخترع أرقاماً أبداً.
- أعط الأولوية للمزودين الذين وجدت أرقام هواتفهم فعلاً في نتائج البحث؛ ضعهم أولاً في القائمة.
- إذا كان المزود قوياً لكن رقمه لم يظهر في النتائج، أضفه في آخر القائمة واكتب (الرقم بالرابط) مكان الرقم.
- إذا لم تجد 5 مزودين فعلاً، اذكر كل الموجود ولا تخترع أسماء أو أرقاماً.

【الحالة 4】سؤال معلوماتي عن منتج (المكونات، السعرات، المواصفات...):
أجب على السؤال نفسه مباشرة — لا تعرض مقارنة أسعار.

قواعد جودة صارمة جداً:
- اذكر فقط المنتجات المتوفرة فعلاً. لا تكتب كلمة InStock أو متوفر مكان السعر.
- أي متجر لا يظهر له سعر رقمي واضح بعملة السوق الحالي احذفه من النتيجة.
- اكتب السعر بالفلوس كاملة دائماً: 1.950 وليس 1.95، و0.750 وليس 0.75.
- قارن نفس المواصفات فقط: نفس الحجم/السعة/الوزن، ونفس اللون إذا كان اللون يغيّر السعر. اذكر المواصفة بجانب كل سعر (مثل: 256GB، 1 لتر، أحمر) ولا تدخل نسخة مختلفة المواصفات في نفس المقارنة.
- اعرض المتاجر المحلية فقط التي تبيع أو توصل داخل بلد المستخدم الحالي؛ لا تعرض متجراً أجنبياً في هذا البحث.
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
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=LENS_HTTP_TIMEOUT)
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


def _self_url_reachable(public_url):
    """v81.2: نتأكد أن رابط صورتنا العام يفتح فعلاً قبل حرق تمريرات SerpApi عليه.

    فشل الوصول (سيرفر بارد/رابط خاطئ) كان يسبب «ما فيه نتائج» رغم أن Lens يعرف المنتج."""
    try:
        r = requests.get(public_url, headers=HEADERS, timeout=8, stream=True)
        ok = r.status_code == 200
        r.close()
        if not ok:
            print(f"LENS SELF-URL HTTP {r.status_code}: {public_url[:80]}")
        return ok
    except Exception as e:
        print(f"LENS SELF-URL UNREACHABLE: {e.__class__.__name__}")
        return False


def google_vision_web_detect(image_b64, mime_type):
    """v81.2: محرك التعرف الرسمي (Google Cloud Vision WEB_DETECTION) — احتياط مستقل.

    يرسل الصورة base64 مباشرة (لا يحتاج رابطاً عاماً إطلاقاً) فيتجاوز كل أعطال
    SerpApi والرابط العام. يعيد نتائج بشكل نتائج Lens نفسها حتى يمر كل ما بعدها
    (العرض، الخيارات، ترتيب العمولة) بدون أي تعديل.
    يتطلب تفعيل Cloud Vision API في نفس مشروع Google Cloud حق مفتاح Gemini.
    """
    if not GOOGLE_VISION_API_KEY or not image_b64:
        return []
    try:
        body = {"requests": [{
            "image": {"content": image_b64},
            "features": [{"type": "WEB_DETECTION", "maxResults": 30}],
        }]}
        r = requests.post(
            f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_API_KEY}",
            json=body, timeout=25,
        )
        if r.status_code >= 400:
            print(f"VISION WEB HTTP {r.status_code}: {r.text[:200]}")
            return []
        web = (((r.json().get("responses") or [{}])[0]).get("webDetection") or {})
        best_guess = ""
        for g in (web.get("bestGuessLabels") or []):
            if g.get("label"):
                best_guess = g["label"].strip()
                break
        entities = [e.get("description", "").strip() for e in (web.get("webEntities") or [])
                    if e.get("description") and float(e.get("score") or 0) >= 0.5]
        items, seen = [], set()
        pos = 0
        for page in (web.get("pagesWithMatchingImages") or []):
            title = re.sub(r"<[^>]+>", "", str(page.get("pageTitle") or "")).strip()
            link = str(page.get("url") or "").strip()
            if not title or not link:
                continue
            sig = (title.lower(), link.lower())
            if sig in seen:
                continue
            seen.add(sig)
            pos += 1
            try:
                host = urllib.parse.urlparse(link).netloc.replace("www.", "")
            except Exception:
                host = ""
            items.append({
                "title": title, "link": link, "source": host or "web",
                "position": pos, "section": "vision_pages", "exact": True,
                "thumbnail": "", "image": "", "price": "", "price_value": None,
                "currency": "", "in_stock": None, "condition": "",
            })
        chosen_title = best_guess or (entities[0] if entities else "")
        if chosen_title and items:
            # نرفع النتيجة الأقرب لعنوان أفضل تخمين لتتصدر الاختيار.
            for it in items:
                if normalize_ar(chosen_title).lower() in normalize_ar(it["title"]).lower():
                    it["position"] = 0
                    break
        print(f"VISION WEB DETECT: pages={len(items)} best_guess={chosen_title!r} entities={entities[:3]}")
        if not items and chosen_title:
            # حتى بدون صفحات: أفضل تخمين وحده يكفي ليكمل البوت بحثه النصي بالاسم الصحيح.
            items = [{"title": chosen_title, "link": "", "source": "google-vision",
                      "position": 1, "section": "vision_pages", "exact": True,
                      "thumbnail": "", "image": "", "price": "", "price_value": None,
                      "currency": "", "in_stock": None, "condition": ""}]
        return items
    except Exception as e:
        print(f"VISION WEB EXCEPTION: {e}")
        return []


def google_lens_lookup(image_b64, mime_type, lang="ar", query_hint="", light=False):
    """تعرف بصري متعدد التمريرات ليقترب من قوة تطبيق Google Lens نفسه.

    light=True (وضع اللينز المباشر v71): يعيد نتائج Lens الخام فوراً بدون استدعاء
    Gemini لوصف الصورة — أسرع وأرخص لأن النتائج ستُرسل للمستخدم كما هي.

    التمريرات بالترتيب (نتوقف بمجرد الحصول على نتائج كافية):
      1) type=products + دولة المستخدم + auto_crop -> بطاقات منتجات فيها أسعار.
      2) type=all + دولة المستخدم + auto_crop      -> visual_matches و exact_matches (التعرف الأقوى).
      3) type=all بدون قيد الدولة وبدون auto_crop   -> أوسع بحث، مثل تطبيق Lens تماماً.
    ثم ندمج النتائج (بدون تكرار) ونختار أفضل عنوان، ونستخرج التوقيع الشكلي من الصورة الأصلية.
    """
    serpapi_possible = bool(ENABLE_GOOGLE_LENS and SERPAPI_API_KEY and PUBLIC_BASE_URL and IMAGE_ID_ENGINE in ("auto", "serpapi"))
    vision_possible = bool(GOOGLE_VISION_API_KEY and IMAGE_ID_ENGINE in ("auto", "vision"))
    if not serpapi_possible and not vision_possible:
        print("GOOGLE LENS SKIPPED: no visual engine available (SerpApi keys/URL missing and Vision key missing)")
        return {"aliases": [], "matches": [], "query": ""}

    public_url = publish_image_for_lens(image_b64, mime_type) if serpapi_possible else ""
    if serpapi_possible and not public_url:
        print("GOOGLE LENS: could not publish image -> Vision-only path")

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

        serpapi_ok = serpapi_possible and bool(public_url)
        # v81.2: الرابط العام لازم يفتح قبل حرق تمريرات SerpApi عليه (سيرفر بارد = صفر نتائج).
        if serpapi_ok and not _self_url_reachable(public_url):
            print("LENS: public image URL unreachable -> skipping SerpApi passes")
            serpapi_ok = False

        if serpapi_ok:
            # v81.2: الموجة الأولى (products + all) بالتوازي بدل التتابع — أسرع وأصمد.
            wave = [
                LENS_PASS_POOL.submit(_serpapi_lens_request, public_url, "products", user_country, True, query_hint),
                LENS_PASS_POOL.submit(_serpapi_lens_request, public_url, "all", user_country, True, query_hint),
            ]
            for f in wave:
                try:
                    _merge(f.result(timeout=LENS_HTTP_TIMEOUT + 10))
                except Exception as e:
                    print(f"LENS WAVE ERR: {e.__class__.__name__}")
            has_exact = any(m.get("exact") for m in merged)
            has_local = any(is_local_lens_result(m) for m in merged)
            if ENABLE_LENS_WIDE_FALLBACK and (len(merged) < LENS_MIN_MATCHES or not (has_exact or has_local)):
                _merge(_serpapi_lens_request(public_url, "all", "", False, query_hint))
            # v81.2: صفر نتائج غالباً عثرة مؤقتة (ضغط SerpApi) — محاولة ثانية وحدة تنقذها.
            if not merged and LENS_RETRY_ON_EMPTY:
                print("LENS RETRY: all passes empty -> one retry after 2s")
                time.sleep(2)
                retry_wave = [
                    LENS_PASS_POOL.submit(_serpapi_lens_request, public_url, "all", user_country, True, query_hint),
                    LENS_PASS_POOL.submit(_serpapi_lens_request, public_url, "all", "", False, query_hint),
                ]
                for f in retry_wave:
                    try:
                        _merge(f.result(timeout=LENS_HTTP_TIMEOUT + 10))
                    except Exception as e:
                        print(f"LENS RETRY ERR: {e.__class__.__name__}")

        # v81.2: محرك Vision الرسمي — احتياط مستقل تماماً (base64 مباشرة، بلا رابط عام).
        if not merged and IMAGE_ID_ENGINE in ("auto", "vision"):
            print("LENS FALLBACK: trying official Google Vision WEB_DETECTION")
            _merge(google_vision_web_detect(image_b64, mime_type))

        matches = merged[:LENS_RESULT_LIMIT]
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
            if is_local_lens_result(m):
                score += 1500
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


LENS_CONSENSUS_SYSTEM = """أنت مستخرج هوية منتج من نتائج Google Lens فقط.
سأعطيك عناوين نتائج Lens لنفس الصورة من متاجر محلية وعالمية.
استخرج الاسم التجاري/القابل للبحث الذي تتفق عليه أغلبية العناوين.
القواعد:
1) اعتمد فقط على الكلمات والبراند والموديل ونوع المنتج المتكررة في العناوين؛ لا تخترع أي معلومة.
2) تجاهل أسماء المتاجر والأسعار وكلمات البيع مثل Buy/Sale/Online/Free shipping.
3) إذا تكرر براند + موديل فاحتفظ بهما بالتهجئة الأصلية.
4) إذا اختلفت تفاصيل ثانوية مثل اللون أو المقاس فلا تجعلها جزءاً من الاسم إلا إذا كانت متكررة بوضوح.
5) أرجع عبارة بحث واحدة فقط، بدون شرح وبدون علامات اقتباس، بطول لا يتجاوز 120 حرفاً.
"""

_LENS_CONSENSUS_STOP = {
    "buy","shop","online","sale","sales","price","prices","offer","offers","discount","new",
    "authentic","original","free","shipping","delivery","available","stock","in","at","from","for",
    "the","and","with","official","store","stores","kuwait","ksa","uae","qatar","bahrain","oman",
    "شراء","اشتر","اونلاين","أونلاين","عرض","عروض","خصم","سعر","اسعار","أسعار","متجر","متاجر",
    "الكويت","كويت","السعوديه","السعودية","الامارات","الإمارات","قطر","البحرين","عمان","توصيل",
}


def _clean_lens_identity_title(title):
    t = str(title or "").strip()
    if not t:
        return ""
    t = re.sub(r"https?://\\S+", " ", t, flags=re.I)
    # prices/currencies are not product identity
    t = re.sub(r"(?:KWD|KD|USD|EUR|GBP|AED|SAR|QAR|BHD|OMR)\\s*\\d+(?:[.,]\\d+)?", " ", t, flags=re.I)
    t = re.sub(r"\\d+(?:[.,]\\d+)?\\s*(?:KWD|KD|USD|EUR|GBP|AED|SAR|QAR|BHD|OMR)\\b", " ", t, flags=re.I)
    t = re.sub(r"[$€£]\\s*\\d+(?:[.,]\\d+)?", " ", t)
    t = re.sub(r"\\s+", " ", t).strip(" -—–|•·:;,،")
    return t[:180]


def _lens_consensus_tokens(title):
    t = normalize_ar(_clean_lens_identity_title(title)).lower()
    toks = re.findall(r"[a-z0-9\\u0600-\\u06ff]+", t)
    out = []
    for tok in toks:
        if len(tok) < 2 or tok in _LENS_CONSENSUS_STOP:
            continue
        if tok not in out:
            out.append(tok)
    return out


def _lens_title_representatives(matches, limit=None):
    """Pick diverse Lens titles from local + global results for identity consensus."""
    cap = SIMILAR_LENS_TITLE_LIMIT if limit is None else max(3, int(limit))
    rows, seen = [], set()
    for m in (matches or []):
        title = _clean_lens_identity_title(m.get("title"))
        key = normalize_ar(title).lower()
        if not title or not key or key in seen:
            continue
        seen.add(key)
        weight = 1.0
        if m.get("exact"):
            weight += 1.0
        if m.get("section") == "visual_matches":
            weight += 0.25
        pos = int(m.get("position") or 99)
        weight += max(0.0, (20 - min(pos, 20)) / 40.0)
        rows.append({"title": title, "tokens": set(_lens_consensus_tokens(title)), "weight": weight, "raw": m})
        if len(rows) >= cap:
            break
    return rows


def _lens_medoid_title(rows):
    """Deterministic fallback: title with the greatest weighted token agreement."""
    if not rows:
        return ""
    if len(rows) == 1:
        return rows[0]["title"]
    best_title, best_score = rows[0]["title"], -1.0
    for i, row in enumerate(rows):
        a = row["tokens"]
        if not a:
            continue
        score = 0.0
        for j, other in enumerate(rows):
            if i == j or not other["tokens"]:
                continue
            b = other["tokens"]
            union = a | b
            overlap = len(a & b) / len(union) if union else 0.0
            score += overlap * other["weight"]
        # Exact Lens and early-ranked titles win ties, but never dominate the majority.
        score += row["weight"] * 0.12
        if score > best_score:
            best_title, best_score = row["title"], score
    return best_title


def _consensus_name_supported(name, rows):
    """Reject an AI canonical name if its meaningful tokens are not backed by Lens titles."""
    tokens = _lens_consensus_tokens(name)
    if not tokens:
        return False
    corpus = [set(r["tokens"]) for r in rows if r.get("tokens")]
    if not corpus:
        return False
    support = Counter()
    for tok in tokens:
        support[tok] = sum(1 for c in corpus if tok in c)
    # A model/number token must occur literally somewhere in Lens evidence.
    for tok in tokens:
        if any(ch.isdigit() for ch in tok) and support[tok] == 0:
            return False
    repeated = [tok for tok in tokens if support[tok] >= 2]
    if len(corpus) == 1:
        return any(support[tok] for tok in tokens)
    return len(repeated) >= min(2, len(tokens)) or max(support.values(), default=0) >= max(2, len(corpus) // 2)


def build_lens_consensus_identity(lens, matches=None):
    """v76: identify the product from the majority of Lens local+global titles.

    Returns a canonical query plus a few representative titles. This is used ONLY
    for «similar alternatives»; exact Lens cards and the global-results button keep
    their existing behavior.
    """
    evidence = list(matches if matches is not None else (lens.get("matches") or []))
    rows = _lens_title_representatives(evidence)
    chosen_title = _clean_lens_identity_title(((lens.get("chosen") or {}).get("title") or lens.get("query") or ""))
    fallback = _lens_medoid_title(rows) or chosen_title
    aliases = [r["title"] for r in rows[:5]]
    if not rows:
        return {"query": chosen_title, "aliases": [chosen_title] if chosen_title else [], "count": 0, "source": "chosen"}

    canonical = ""
    if ENABLE_LENS_CONSENSUS_AI and len(rows) >= 2:
        title_lines = []
        for i, r in enumerate(rows, 1):
            flags = []
            raw = r.get("raw") or {}
            if raw.get("exact"):
                flags.append("exact")
            if is_local_lens_result(raw):
                flags.append("local")
            flag_text = f" [{' '.join(flags)}]" if flags else ""
            title_lines.append(f"{i}. {r['title']}{flag_text}")
        raw, _ = call_gemini(
            [{"text": "Google Lens result titles:\\n" + "\\n".join(title_lines)}],
            system=LENS_CONSENSUS_SYSTEM,
            use_search=False,
        )
        candidate = _clean_lens_identity_title((raw or "").splitlines()[0] if raw else "")[:120]
        if candidate and _consensus_name_supported(candidate, rows):
            canonical = candidate
        elif candidate:
            print(f"LENS CONSENSUS AI REJECT unsupported={candidate!r}")

    canonical = canonical or fallback
    print(f"LENS CONSENSUS IDENTITY: {canonical!r} from={len(rows)} titles fallback={fallback!r}")
    return {
        "query": canonical,
        "aliases": aliases,
        "count": len(rows),
        "source": "ai_consensus" if canonical and canonical != fallback else "medoid",
    }

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
    "كارفور": "carrefourkuwait.com", "carrefour": "carrefourkuwait.com", "لولو": "luluhypermarket.com", "lulu": "luluhypermarket.com", "امازون": "amazon.ae",
    "صفاة هوم": "safathome.com", "صفاه هوم": "safathome.com", "safat home": "safathome.com", "safat": "safathome.com",
    "ابيات": "abyat.com", "أبيات": "abyat.com", "abyat": "abyat.com",
    "هوم بوكس": "homeboxstores.com", "home box": "homeboxstores.com", "homebox": "homeboxstores.com",
    "هوم سنتر": "homecentre.com", "هوم سنتر الكويت": "homecentre.com", "home centre": "homecentre.com", "homecenter": "homecentre.com",
    "ايكيا": "ikea.com", "إيكيا": "ikea.com", "ايكيا الكويت": "ikea.com", "ikea": "ikea.com",
    "ميداس": "midasfurniture.com", "midas": "midasfurniture.com",
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
        "شاشه", "شاشة", "مونيتور", "طابعه", "طابعة", "راوتر", "مودم", "سبيكر", "مكبر صوت",
        "بروجكتر", "داتا شو", "هارد", "فلاش", "ميموري",
        "iphone", "samsung", "laptop", "tablet", "ipad", "television", "tv", "phone",
        "smartwatch", "airpods", "earbuds", "camera", "charger", "power bank", "drone",
        "monitor", "screen", "display", "printer", "router", "modem", "speaker",
        "projector", "hard drive", "ssd", "flash drive",
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
    # v76.1: normalize BOTH the incoming store name and dictionary aliases.
    # Previously only ``name`` was normalized, so Arabic spaces/ة->ه changes
    # made aliases such as «صفاة هوم» fail to resolve, disabling the domain guard.
    n = normalize_name(normalize_ar(name))
    if not n:
        return ""
    for k, d in STORE_DOMAINS.items():
        kn = normalize_name(normalize_ar(k))
        if kn and (kn in n or n in kn):
            return d
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
def _clean_store_name(name):
    """v74.5: تنظيف اسم المتجر من أقواس Gemini الزائدة: «[إكسايت] (» -> «إكسايت»."""
    n = re.sub(r"[\[\]«»\"']+", "", str(name or ""))
    n = re.sub(r"\(\s*[^)]*\)?\s*$", "", n)  # قوس مفتوح أو فاضي بنهاية الاسم
    return " ".join(n.split()).strip(" -—–:،") or str(name or "").strip()

def extract_store_offers(txt, limit=None):
    """Extract priced store lines.

    v76: ``limit`` lets the similar-alternatives path return more cards without
    changing the normal product-search cap. Existing callers keep MAX_STORES.
    """
    offers = []
    for line in (txt or "").splitlines():
        s = line.strip()
        # Price may appear before or after KWD and may include an asterisk from Lens.
        m = re.match(r"^(✅|🏆|•)\s*(.+?)\s*(?:—|–|-)\s*(.+)$", s)
        if not m or not re.search(r"\d", m.group(3)):
            continue
        if re.search(r"\(\s*(?:هاتف|Phone|phone|Tel|tel)\s*:", s):
            continue
        name = _clean_store_name(m.group(2))
        # v74.5: السطر المعروض للمستخدم يُعاد بناؤه بالاسم النظيف نفسه.
        s = f"{m.group(1)} {name} — {m.group(3).strip()}"
        # "توصيل" و"أونلاين" وأمثالها ليست متاجر؛ غالباً سطر رسوم توصيل التقطه النموذج كعرض.
        if is_junk_store(name):
            print(f"SKIP JUNK STORE LINE: {s[:80]}")
            continue
        best = m.group(1) in ("✅", "🏆")
        body = s if best else s.lstrip("•").strip()
        offers.append({"line": body, "name": name, "best": best})
    cap = MAX_STORES if limit is None else max(1, int(limit))
    return offers[:cap]

def product_title(txt, fallback=""):
    m = re.search(r"^\s*📦\s*(.+)$", txt or "", flags=re.M)
    if m: return f"📦 {m.group(1).strip()}"
    return f"📦 {fallback}" if fallback else ""

def _url_host(url):
    try:
        return clean_domain(urllib.parse.urlparse(str(url or "")).netloc)
    except Exception:
        return ""

def store_url_matches_store(name, url):
    """v76.1 hard guard: known store names may only open their own domain.

    Prevents a merged Gemini/v26 URL such as a Safat Home CTA accidentally
    pointing at jarir.com. Unknown stores are allowed through because there is
    no canonical domain to compare against.
    """
    if not url or not str(url).startswith(("http://", "https://")):
        return False
    expected = clean_domain(store_domain(name))
    if not expected:
        return True
    host = _url_host(url)
    ok = bool(host and (host == expected or host.endswith("." + expected)))
    if not ok:
        print(f"STORE/URL MISMATCH DROP: store={name!r} expected={expected} got={host or url}")
    return ok

def match_url(name, urls):
    """Match a CTA URL to a store without ever crossing known store domains."""
    if not urls:
        return ""

    # 1) Exact key first, but only if the URL belongs to that store.
    if name in urls and store_url_matches_store(name, urls[name]):
        return urls[name]

    nn = normalize_name(name)

    # 2) If this is a canonical/known store, host-domain evidence is stronger
    # than Gemini's label. Search every collected URL for the correct domain.
    dom = store_domain(name)
    if dom:
        for _k, v in urls.items():
            if store_url_matches_store(name, v):
                return v

    # 3) Fuzzy-name matching is allowed only after the same domain guard.
    for k, v in urls.items():
        kk = normalize_name(k)
        if nn and kk and (nn in kk or kk in nn) and store_url_matches_store(name, v):
            return v
    return ""

def _similar_store_candidates_from_line(line, urls):
    """Infer the real store name from a similar-alternative line.

    Similar search models sometimes emit:
        PRODUCT — STORE — PRICE
    while the CTA pipeline expects STORE to be the first segment.  Recover the
    store using canonical store aliases and the URL-map keys, without changing
    the user-facing product description.
    """
    raw = re.sub(r"^(?:✅|🏆|•)\s*", "", str(line or "")).strip()
    if not raw:
        return []
    parts = [x.strip() for x in re.split(r"\s*(?:—|–|\|)\s*", raw) if x.strip()]
    # Price is normally the last part and is not useful for store detection.
    searchable = parts[:-1] if len(parts) > 1 else parts
    url_keys = [str(k).strip() for k in (urls or {}).keys() if str(k).strip()]
    out = []

    def add(name, score):
        name = _clean_store_name(name)
        if not name:
            return
        # A product title can accidentally contain a store word; prefer shorter,
        # cleaner store labels over a full product title.
        token_count = len(name.split())
        score -= max(0, token_count - 4) * 2
        cur = next((x for x in out if normalize_name(normalize_ar(x[0])) == normalize_name(normalize_ar(name))), None)
        if cur:
            if score > cur[1]:
                cur[1] = score
            return
        out.append([name, score])

    for seg_i, seg in enumerate(searchable):
        seg_norm = normalize_name(normalize_ar(seg))
        if not seg_norm:
            continue
        # Canonical known store found inside a segment.
        dom = store_domain(seg)
        if dom:
            # Prefer a matching URL-map key on the same canonical domain so the
            # CTA label stays natural (e.g. "صفاة هوم" instead of a product title).
            matched_key = None
            for k in url_keys:
                if clean_domain(store_domain(k)) == clean_domain(dom):
                    matched_key = k
                    break
            add(matched_key or seg, 120 - seg_i * 5)

        # URL-map keys are strong evidence.  This also supports stores that are
        # not yet in STORE_DOMAINS.
        for k in url_keys:
            kn = normalize_name(normalize_ar(k))
            if not kn:
                continue
            if kn in seg_norm or seg_norm in kn:
                add(k, 100 + min(len(kn), 30) - seg_i * 5)

    return [x[0] for x in sorted(out, key=lambda z: z[1], reverse=True)]


def repair_similar_offer_store_names(offers, urls):
    """Relabel similar-search offers with the actual store before CTA matching."""
    repaired = []
    for o in (offers or []):
        item = dict(o)
        current = item.get("name", "")
        cands = _similar_store_candidates_from_line(item.get("line", ""), urls or {})
        if cands:
            best = cands[0]
            cur_norm = normalize_name(normalize_ar(current))
            best_norm = normalize_name(normalize_ar(best))
            # Even if a product-title prefix contains a store word (e.g.
            # "Home Box Edmond 2"), relabel it to the clean URL/store key.
            if best_norm and best_norm != cur_norm:
                old = current
                item["name"] = best
                print(f"SIMILAR CTA STORE REPAIR: {old!r} -> {item['name']!r}")
        repaired.append(item)
    return repaired


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
    # v74.15: بدون إحداثيات محفوظة — خرائط Google تفتح على موقع الجهاز الحالي بنفسها
    # (الموقع المحفوظ من التسجيل قد يكون قديماً بأيام).
    url = maps_search_url(product)
    send_whatsapp_cta(from_number, T(lang, "maps_body"), url, bot_id, T(lang, "maps_btn"))

ENABLE_RELEVANCE_FILTER = env_bool("ENABLE_RELEVANCE_FILTER", True)
# كلمات نتائج «حول المنتج» وليست المنتج نفسه — تُرفض فوراً إلا إذا طلبها المستخدم بنفسه.
_NON_PRODUCT_WORDS = (
    "owners manual", "owner's manual", "service manual", "workshop manual",
    "repair manual", "manual pdf", "handbook", "wiring diagram", "parts catalog",
    "parts catalogue", "spare part", "spare parts", "دليل المالك", "دليل الاستخدام",
    "كتيب", "دليل الصيانه", "دليل الصيانة", "قطع غيار", "مخطط",
    # v74.15: قطع ومستلزمات — «مروحة المكينة» ليست «المكينة»، و«متوافق مع» = قطعة بديلة.
    "متوافق مع", "compatible with", "replacement for", "يناسب موديل", "fits yamaha",
    "fits suzuki", "fits mercury", "fits tohatsu", "fits honda",
    "مروحه", "مروحة", "propeller", "impeller", "ستارتر", "starter motor", "self starter",
    "كاربريتر", "carburetor", "carburettor", "بواجي", "spark plug", "gasket", "جوان",
    "فلتر زيت", "oil filter", "فلتر هواء", "air filter", "طرمبه", "water pump kit",
    "حساس", "sensor for", "غطاء المحرك", "engine cover", "sticker", "decal", "ملصق",
)

RELEVANCE_FILTER_SYSTEM = """أنت مدقق نتائج لبوت تسوق. المستخدم طلب منتجاً، وسأعطيك قائمة مرقمة بنتائج البحث (اسم المتجر — العنوان/الرابط).
أعد فقط أرقام النتائج التي تبيع المنتج المطلوب نفسه كاملاً (أو نسخة/موديل منه).
ارفض بلا تردد: كتيبات ودلائل الاستخدام (Manuals/PDF)، قطع الغيار ومكونات المنتج (مروحة، ستارتر، كاربريتر، فلتر، حساس...)، أي نتيجة فيها "متوافق مع" أو "Compatible with" أو "Replacement for" فهي قطعة وليست المنتج، الإكسسوارات والأغطية، المجسمات والألعاب المصغرة، الملصقات، الخدمات والتأجير — إلا إذا كان طلب المستخدم نفسه عنها.
مثال 1: المستخدم طلب "Sea Ray Sundancer 320" (يخت) والنتيجة "Sea Ray 320 Owners Manual PDF" -> ارفضها.
مثال 2: المستخدم طلب "محرك Suzuki DF25AES5" والنتيجة "Starter Motor Compatible with Suzuki 25HP" -> ارفضها، هذه قطعة وليست المحرك.
أرجع JSON فقط بدون شرح: {"keep":[1,3]}"""

SIMILAR_RELEVANCE_FILTER_SYSTEM = """أنت مدقق نتائج لميزة «بدائل مشابهة» في بوت تسوق.
المستخدم أعطانا منتجاً مرجعياً، والنتائج المطلوبة يجب أن تكون بدائل حقيقية له لا نفس الموديل بالضرورة.
أبقِ المنتج إذا كان من نفس الفئة الرئيسية ونفس الاستخدام ونفس شكل/مستوى المواصفات تقريباً، حتى لو اختلف البراند أو الموديل.
لا تشترط وجود اسم البراند الأصلي. ارفض المنتج الأصلي نفسه إذا كان واضحاً أنه نفس الموديل، وارفض الفئات البعيدة.
ارفض دائماً الكتيبات وPDF وقطع الغيار والملحقات والأغطية والخدمات والتأجير وعبارات Compatible with / Replacement for، إلا إذا كان المرجع نفسه من هذه الفئة.
أرجع JSON فقط بدون شرح: {"keep":[1,3]}"""

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
    raw, _ = call_gemini([{"text": prompt}], system=relevance_system, use_search=False)
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

# ---- v74.15: فاحص حياة الروابط — يمنع الروابط الميتة والدومينات المخترعة -----
_URL_ALIVE_CACHE = {}
_URL_ALIVE_LOCK = threading.Lock()

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

# ---- v74.10: حلّال الصفحة الرئيسية للمتجر — عشان كل عرض يحصل زر CTA ----------
_STORE_HOME_CACHE = {}
_STORE_HOME_LOCK = threading.Lock()
STORE_DOMAIN_SYSTEM = """أنت خبير متاجر التجزئة في الخليج. سأعطيك اسم متجر وبلد المستخدم.
أرجع دومين الموقع الرسمي للمتجر فقط (مثل: safathome.com أو abyat.com) بدون https وبدون أي شرح.
إذا لم تكن متأكداً من الدومين الصحيح 100% أرجع كلمة NONE فقط. لا تخمن أبداً."""

def resolve_store_homepage(name):
    """رابط للمتجر عندما لا يوجد رابط منتج: القاموس أولاً، ثم ذكاء اصطناعي (كاش)."""
    name = str(name or "").strip()
    if not name:
        return ""
    dom = store_domain(name)
    if dom:
        return f"https://{dom}"
    key = normalize_name(normalize_ar(name))[:80]
    if not key:
        return ""
    with _STORE_HOME_LOCK:
        if key in _STORE_HOME_CACHE:
            return _STORE_HOME_CACHE[key]
    raw, _ = call_gemini(
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



def _similar_offer_product_name(offer):
    """Extract the actual alternative product name from STORE — PRODUCT — PRICE."""
    line = re.sub(r"^(?:✅|🏆|•)\s*", "", str((offer or {}).get("line", ""))).strip()
    store = str((offer or {}).get("name", "")).strip()
    # remove the store prefix if present, then remove the final price segment
    if store and normalize_ar(line).startswith(normalize_ar(store)):
        line = line[len(store):].lstrip(" —–-:،")
    parts = [p.strip() for p in re.split(r"\s+(?:—|–)\s+|\s+-\s+", line) if p.strip()]
    if not parts:
        return line[:160]
    # Last part normally contains the numeric price; everything before it is the product name.
    if len(parts) >= 2 and re.search(r"\d", parts[-1]):
        return " — ".join(parts[:-1]).strip()[:180]
    return parts[0][:180]


def resolve_direct_product_page(store_name, product_name, candidate_url=""):
    """v76.3: Resolve a real product-page URL for similar alternatives only.

    Homepages/category/search pages are never accepted.  The store/domain guard is
    enforced both before and after the grounded Google lookup.
    """
    store_name = str(store_name or "").strip()
    product_name = str(product_name or "").strip()
    if not store_name or not product_name:
        return ""

    # If Gemini already grounded a true direct page from the right store, keep it.
    if candidate_url and store_url_matches_store(store_name, candidate_url) and is_direct_store_url(candidate_url):
        return candidate_url

    expected = expected_store_domain(store_name)
    if not expected:
        # We still allow a known/verified homepage resolver only to discover the domain,
        # never as the CTA itself.
        hp = resolve_store_homepage(store_name) or ""
        expected = _host_of(hp)
    if not expected:
        print(f"SIMILAR DIRECT RESOLVE: no known domain for {store_name!r}")
        return ""

    market_name = current_market().get("country_name", "Kuwait")
    prompt = (
        f"Find the exact direct product page for this product in this store.\n"
        f"Store: {store_name}\nProduct: {product_name}\nMarket: {market_name}\n"
        f"Required domain: {expected}\n"
        "Use Google search deeply. Return only this store's actual product-detail page; "
        "do NOT return the homepage, category, collection, search results, brand page, or another store. "
        "If there is no direct product page, say NOT_FOUND."
    )
    try:
        txt, urls = call_gemini([{"text": prompt}])
    except Exception as e:
        print(f"SIMILAR DIRECT RESOLVE ERR {store_name}: {e}")
        return ""

    candidates = []
    if candidate_url:
        candidates.append(candidate_url)
    candidates.extend((urls or {}).values())
    # Gemini sometimes prints a raw URL in text even when grounding map is sparse.
    candidates.extend(re.findall(r"https?://[^\s)\]}>]+", txt or ""))

    seen = set()
    product_tokens = [t for t in _meaningful_lens_tokens(product_name) if len(t) >= 3][:8]
    ranked = []
    for u in candidates:
        u = str(u or "").strip().rstrip(".,؛،")
        if not u or u in seen:
            continue
        seen.add(u)
        if not store_url_matches_store(store_name, u):
            continue
        if not is_direct_store_url(u):
            print(f"SIMILAR DIRECT DROP NON-PRODUCT: {store_name} -> {u}")
            continue
        hay = normalize_ar(urllib.parse.unquote(u)).lower()
        token_hits = sum(1 for t in product_tokens if normalize_ar(t) in hay)
        # Direct-page structure is mandatory; token hits only rank several valid pages.
        ranked.append((token_hits, len(u), u))
    if not ranked:
        print(f"SIMILAR DIRECT RESOLVE MISS: {store_name} | {product_name[:90]}")
        return ""
    ranked.sort(key=lambda x: (x[0], x[1]), reverse=True)
    chosen = ranked[0][2]
    print(f"SIMILAR DIRECT RESOLVED: {store_name} | {product_name[:70]} -> {chosen}")
    return chosen


def _price_sanity_filter(offers, query="", lang="ar"):
    """v81.1: سعر شاذ عن الوسيط بشكل صارخ = منتج مختلف غالباً (قطعة/إكسسوار/نسخة أخرى).

    مدرك للعملات: النتائج المدموجة (محلي + عالمي) تُجمّع حسب عملة كل سطر، والقاعدة
    (أكثر من 8× الوسيط أو أقل من وسيطه/8) تُطبق داخل كل مجموعة فيها 3 أسعار فأكثر.
    """
    local_code = (current_market().get("currency") or "KWD").upper()
    groups = defaultdict(list)
    for o in offers:
        code = detect_currency_code(o.get("line", ""), local_code) or local_code
        groups[code].append(o)
    kept = []
    for code, grp in groups.items():
        priced = [(o, _extract_numeric_price(o.get("line", ""))) for o in grp]
        nums = sorted(p for _o, p in priced if p is not None and p > 0)
        if len(nums) < 3:
            kept.extend(grp)
            continue
        median = nums[len(nums) // 2]
        if median <= 0:
            kept.extend(grp)
            continue
        for o, p in priced:
            if p is not None and p > 0 and (p > median * 8 or p < median / 8):
                print(f"PRICE SANITY DROP [{code}] ({str(query)[:40]!r}): {o.get('line','')[:80]} (median={median})")
                continue
            kept.append(o)
    # الحفاظ على الترتيب الأصلي (محلي أولاً ثم عالمي).
    order = {id(o): i for i, o in enumerate(offers)}
    kept.sort(key=lambda o: order.get(id(o), 10**9))
    return kept if kept else offers


def _dedup_offers_by_store(offers, urls):
    """v81.1: توحيد كانوني — «لولو» و«لولو هايبرماركت» بنفس النتيجة يظهران مرة (الأرخص)."""
    best = {}
    order = []
    for o in offers:
        try:
            key = canonical_store_key(o.get("name", ""), match_url(o.get("name", ""), urls or {}))
        except Exception:
            key = ""
        if not key:
            key = normalize_name(normalize_ar(o.get("name", ""))) or o.get("name", "")
        p = _extract_numeric_price(o.get("line", ""))
        cur = best.get(key)
        if cur is None:
            best[key] = (o, p)
            order.append(key)
        else:
            _co, cp = cur
            if p is not None and (cp is None or p < cp):
                best[key] = (o, p)
    deduped = [best[k][0] for k in order]
    if len(deduped) != len(offers):
        print(f"STORE DEDUP: {len(offers)} -> {len(deduped)} offers")
    return deduped


def _mandatory_priority_domain(store_name, urls):
    """Return the configured priority domain for an offer, preferring its grounded URL."""
    name = str(store_name or "").strip()
    url = ""
    try:
        url = match_url(name, urls or {}) or ""
    except Exception:
        url = ""
    try:
        host = _host_of(url).lower() if url else ""
    except Exception:
        try:
            host = urllib.parse.urlparse(url).netloc.lower() if url else ""
        except Exception:
            host = ""

    # URL is authoritative, especially for Amazon country domains.
    if host:
        for domain in MANDATORY_PRIORITY_STORES:
            if host == domain or host.endswith("." + domain) or domain in host:
                return domain

    # Fallback when Gemini gave the store name but the URL map is missing/weak.
    n = normalize_name(name)
    aliases = {
        "amazon.com": ("amazon", "amazoncom"),
        "amazon.ae": ("amazonae",),
        "amazon.sa": ("amazonsa",),
        "amazon.co.uk": ("amazonuk", "amazoncouk"),
        "amazon.de": ("amazonde",),
        "aliexpress.com": ("aliexpress",),
        "temu.com": ("temu",),
        "shein.com": ("shein",),
        "trendyol.com": ("trendyol",),
        "namshi.com": ("namshi", "نمشي"),
        "ounass.com": ("ounass", "اوناس", "أوناس"),
        "6thstreet.com": ("6thstreet", "sixthstreet", "6th", "سيكثستريت"),
        "farfetch.com": ("farfetch",),
        "asos.com": ("asos",),
        "stockx.com": ("stockx",),
        "sephora.com": ("sephora", "سيفورا"),
        "sephora.ae": ("sephoraae",),
        "iherb.com": ("iherb", "ايهيرب", "آيهيرب"),
        "lookfantastic.com": ("lookfantastic",),
        "cultbeauty.com": ("cultbeauty",),
        "ebay.com": ("ebay",),
        "newegg.com": ("newegg",),
        "banggood.com": ("banggood",),
        "noon.com": ("noon", "نون"),
        "xcite.com": ("xcite", "x-cite", "إكسايت", "اكسايت"),
        "boutiqaat.com": ("boutiqaat", "بوتيكات"),
    }
    # Country-specific Amazon / Sephora names first so generic aliases don't steal them.
    for domain in ("amazon.ae", "amazon.sa", "amazon.co.uk", "amazon.de", "sephora.ae"):
        if any(normalize_name(a) and normalize_name(a) in n for a in aliases.get(domain, ())):
            return domain
    for domain in MANDATORY_PRIORITY_STORES:
        if any(normalize_name(a) and normalize_name(a) in n for a in aliases.get(domain, ())):
            return domain
    return ""

def prioritize_mandatory_store_offers(offers, urls):
    """Stable mandatory ranking: listed stores first, in owner-defined order."""
    if not offers:
        return offers
    decorated = []
    hits = []
    for original_index, offer in enumerate(offers):
        domain = _mandatory_priority_domain(offer.get("name", ""), urls or {})
        rank = MANDATORY_PRIORITY_INDEX.get(domain, len(MANDATORY_PRIORITY_STORES) + 1000)
        decorated.append((rank, original_index, offer))
        if domain:
            hits.append((domain, offer.get("name", "")))
    decorated.sort(key=lambda x: (x[0], x[1]))
    if hits:
        print("MANDATORY STORE PRIORITY:", hits)
    return [x[2] for x in decorated]


def send_product_result(from_number, txt, urls, bot_id, lang, query, best_only=False, max_stores=None, relevance_mode="exact"):
    if not txt:
        send_whatsapp_text(from_number, T(lang, "not_found"), bot_id)
        return "none"
    if is_service_answer(txt):
        # الخدمات: رسالة واحدة فيها الاسم والرقم، وبعدها الخريطة بدون روابط متاجر.
        send_whatsapp_text(from_number, txt, bot_id)
        return "service"
    store_limit = MAX_STORES if max_stores is None else max(1, int(max_stores))
    candidate_limit = max(store_limit, min(60, store_limit * 5))
    offers = extract_store_offers(txt, limit=candidate_limit)
    if not offers:
        send_whatsapp_text(from_number, txt, bot_id)
        return "info"
    # v76.3: بدائل Gemini قد تأتي PRODUCT — STORE — PRICE. أصلح اسم المتجر
    # قبل فلتر الصلة ومطابقة CTA حتى لا تتحول النتائج إلى نص بلا أزرار.
    if relevance_mode == "similar":
        offers = repair_similar_offer_store_names(offers, urls)
    # v74.9: فلتر الصلة — كتيب اليخت ليس اليخت. إذا ما بقي شي، النتيجة تعتبر غير موجودة.
    offers = filter_relevant_offers(query, offers, urls, mode=relevance_mode)
    if not offers:
        print("RELEVANCE: all offers dropped -> treat as not found")
        send_whatsapp_text(from_number, T(lang, "not_found"), bot_id)
        return "none"
    # v81.9: mandatory affiliate/store priority is applied ONLY after relevance filtering.
    # This guarantees exact-match quality wins first; then preferred stores win presentation order.
    offers = prioritize_mandatory_store_offers(offers, urls)
    title = product_title(txt, query)
    if title:
        send_whatsapp_text(from_number, title, bot_id)
    core = title[2:].strip() if title.startswith("📦") else query
    fq = short_query(core) or short_query(query)
    if best_only:
        best = next((o for o in offers if o["best"]), offers[0])
        offers = [best]
    sent = 0
    fallback_ctas = []
    for o in offers[:store_limit]:
        url = match_url(o["name"], urls)
        # v77.8 AFFILIATE WRAP
        try:
            original_url = url
            url = wrap_affiliate_url(url, from_number, query)
            log_click(from_number, query, o["name"], original_url, url, is_global=(relevance_mode!="exact" or "global" in str(query).lower()))
        except Exception as e:
            print(f"AFF WRAP ERR in send_result: {e}")
        # v76.1: دفاع أخير قبل CTA — حتى لو تغيّر match_url مستقبلاً،
        # ممنوع اسم متجر يفتح دومين متجر آخر.
        if url and not store_url_matches_store(o["name"], url):
            print(f"CTA STORE DOMAIN GUARD DROP: {o['name']} -> {url}")
            url = ""
        # v76.3: For similar alternatives, NEVER use homepage/category/search fallbacks.
        # Resolve the alternative's actual product page inside the same store instead.
        if relevance_mode == "similar":
            product_name = _similar_offer_product_name(o)
            if not is_direct_store_url(url):
                url = resolve_direct_product_page(o["name"], product_name, url)
            if not url or not is_direct_store_url(url) or not store_url_matches_store(o["name"], url):
                print(f"SIMILAR CTA DROP — NO DIRECT PRODUCT PAGE: {o['name']} | {product_name} -> {url}")
                continue
            send_whatsapp_cta(from_number, o["line"], url, bot_id, f"🛒 {o['name'][:18]}")
            sent += 1
            continue

        # Normal exact-product searches keep the legacy safe fallback behavior.
        if not is_direct_store_url(url):
            try:
                host = urllib.parse.urlparse(url or "").netloc.lower()
            except Exception:
                host = ""
            if url and url.startswith("http") and host and "google." not in host and "bing." not in host:
                fallback_ctas.append((o, url))
            else:
                hp = resolve_store_homepage(o["name"])
                if hp:
                    fallback_ctas.append((o, hp))
            print(f"SKIP NON-DIRECT CTA: {o['name']} -> {url}")
            continue
        send_whatsapp_cta(from_number, o["line"], url, bot_id, f"🛒 {o['name'][:18]}")
        sent += 1
    if relevance_mode != "similar" and fallback_ctas and sent < store_limit:
        # v76.3: لا نخفي CTAs الاحتياطية لمجرد أن نتيجة واحدة كان لها رابط مباشر.
        # نرسلها بعد المباشرة حتى يصل كل بديل ممكن إلى زر، مع توضيح إذا كان الزر يفتح المتجر.
        remaining = max(0, store_limit - sent)
        checked = list(RESOLVER.map(lambda ou: (ou[0], ou[1], url_is_alive(ou[1])), fallback_ctas[:remaining]))
        for o, url, alive in checked:
            if not alive:
                print(f"FALLBACK CTA DEAD — DROPPED: {o['name']} -> {url}")
                continue
            print(f"FALLBACK STORE CTA: {o['name']} -> {url}")
            # نوضح أن الزر يفتح المتجر (مو صفحة المنتج) حتى ما يتفاجأ المستخدم بصفحة عامة.
            note = "\n🔎 الزر يفتح المتجر — ادور المنتج داخله" if lang == "ar" else "\n🔎 Button opens the store — search the product inside"
            send_whatsapp_cta(from_number, (o["line"] + note)[:1024], url, bot_id, f"🛒 {o['name'][:18]}")
            sent += 1
    if sent == 0:
        if relevance_mode == "similar":
            print("SIMILAR: zero verified direct product CTAs -> treat as none")
            return "none"
        # v74.8: عندنا أسعار حقيقية بدون أي روابط صالحة: نعرض الأسعار نصاً —
        # ممنوع نقول «ما لقيت» والنتيجة موجودة بأيدينا.
        # v74.9: مرتبة من الأرخص إلى الأغلى و✅ للأرخص دائماً.
        ranked = offers[:store_limit]  # already filtered + mandatory-priority ranked above
        lines_out = []
        for i, o in enumerate(ranked):
            body_line = re.sub(r"^(?:✅|🏆|•)\s*", "", o.get("line", "")).strip()
            lines_out.append(f"{'✅' if i == 0 else '•'} {body_line}")
        body = "\n".join(lines_out).strip()
        if body:
            send_whatsapp_text(from_number, body, bot_id)
            return "product"
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


# ---- v74.2: محرك v26 القديم بالضبط — البطولة الداخلية للبحوث المتوازية --------
# هذا هو «المسار الذكي الكامل القديم» من v26: نفس دالة answer_score ونفس منطق
# best_of_search (بطولة SEARCH_RUNS بحوث متوازية + اتحاد لنكات كل الجولات).
# يُستخدم حالياً في خيار «🔄 بدائل مشابهة» فقط، مع إبقاء طريقة العرض الحالية.

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
        for offer in extract_store_offers(txt or "", limit=max_results):
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


# v81.1: خروج مبكر من البطولات — نتيجة قوية مبكرة = ما ننتظر الجولة العالقة (توفير 30-60%).
V26_EARLY_EXIT_SCORE = int(os.environ.get("V26_EARLY_EXIT_SCORE", "14"))
V26_EARLY_EXIT_MIN_RUNS = max(1, int(os.environ.get("V26_EARLY_EXIT_MIN_RUNS", "2")))

def _tournament_collect(futs, merge_offers, deadline_seconds=120):
    """يجمع نتائج الجولات فور اكتمالها مع خروج مبكر ذكي.

    وضع الدمج (merge_offers=True) يستفيد من كل الجولات للوفرة، فنقص فقط آخر جولة
    عالقة (بعد اكتمال SEARCH_RUNS-1). الوضع العادي يخرج بعد جولتين ونتيجة قوية.
    """
    from concurrent.futures import as_completed as _as_completed
    results = []
    min_runs = max(V26_EARLY_EXIT_MIN_RUNS, len(futs) - 1) if merge_offers else V26_EARLY_EXIT_MIN_RUNS
    deadline = time.time() + deadline_seconds
    best_score = -1
    try:
        for f in _as_completed(futs, timeout=deadline_seconds + 5):
            try:
                t, u = f.result(timeout=max(1.0, deadline - time.time()))
            except Exception as e:
                print(f"tournament run err: {e.__class__.__name__}")
                continue
            if t:
                results.append((t, u))
                best_score = max(best_score, v26_answer_score(t, u))
                if len(results) >= min_runs and best_score >= V26_EARLY_EXIT_SCORE:
                    pending = sum(1 for x in futs if not x.done())
                    if pending:
                        print(f"TOURNAMENT EARLY EXIT: score={best_score} after {len(results)} runs, skipping {pending} pending")
                    break
            if time.time() >= deadline:
                break
    except Exception as e:
        print(f"tournament collect err: {e.__class__.__name__}")
    return results


def v26_best_of_search(parts, max_results=None, merge_offers=False, merge_title=""):
    """v26 tournament with an optional v76 union mode for similar alternatives.

    Normal callers are unchanged. For alternatives, ``merge_offers=True`` unions
    different stores/products discovered across SEARCH_RUNS instead of throwing
    away everything except the winning text.
    v81.1: as_completed + early exit — الجولة العالقة ما توقف الرد.
    """
    limit = MAX_STORES if max_results is None else max(1, int(max_results))
    market_snapshot = current_market()
    try:
        futs = [V26_SEARCH_POOL.submit(_run_with_market, market_snapshot, call_gemini, parts)
                for _ in range(SEARCH_RUNS)]
        results = _tournament_collect(futs, merge_offers)
    except Exception as e:
        print(f"v26 best_of_search err {e}")
        return call_gemini(parts)

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
           "winner_stores": len(extract_store_offers(best_txt, limit=limit)),
           "total_links": len(merged_urls),
           "merged_offers": bool(merge_offers)})
    return best_txt, merged_urls


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


# v72.3: ترجمة عناوين نتائج Lens للعربية — دفعة واحدة باتصال سريع رخيص + كاش.
TRANSLATE_TITLES_SYSTEM = """ترجم أسماء المنتجات التالية إلى العربية بأسلوب متجر واضح ومختصر.
- أبقِ البراند والموديل والأرقام والأحجام لاتينية كما هي (Mountain Dew, iPhone 15 Pro, 250ml, 1.5L).
- Pack of 30 تصير: عبوة 30. Carbonated Drink تصير: مشروب غازي.
- سطر واحد لكل منتج وبنفس الترقيم تماماً. بدون أي شرح أو إضافات."""

AR_TITLE_CACHE = {}
AR_TITLE_LOCK = threading.Lock()

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
        raw, _ = call_gemini([{"text": numbered}], system=TRANSLATE_TITLES_SYSTEM, use_search=False)
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

    # v72.3: اسم دولة أخرى صريح في المتجر/العنوان (Carrefour Qatar، Amazon India...)
    # = ليس محلياً مهما انطبقت تلميحات أخرى، إلا إذا ذُكر بلد المستخدم نفسه أيضاً.
    current_names = {
        str(m.get("country_name") or "").lower(),
        COUNTRY_NAMES_AR.get(cc, "").strip(),
    }
    foreign_name_hit = False
    for cc2, name2 in COUNTRY_NAMES.items():
        if cc2 == cc or not name2:
            continue
        if re.search(rf"\b{re.escape(name2.lower())}\b", hay):
            foreign_name_hit = True
            break
    if not foreign_name_hit:
        for cc2, name2 in COUNTRY_NAMES_AR.items():
            if cc2 == cc or not name2:
                continue
            if name2 in hay:
                foreign_name_hit = True
                break
    if foreign_name_hit and not any(n and n.lower() in hay for n in current_names if n):
        return False

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


# ---- v74.13: ترتيب النتائج العالمية جغرافياً --------------------------------
# العرض للمستخدم الخليجي: دول الخليج أولاً (شحن أسرع وأرخص وضمانات أقرب)،
# ثم أمريكا، ثم الصين، ثم أوروبا، ثم بقية العالم — وداخل كل منطقة الأرخص أولاً.
_GCC_CCS = {"sa", "ae", "bh", "qa", "om", "kw"}
_EU_CCS = {"gb", "de", "fr", "it", "es", "pt", "nl", "be", "ch", "at", "se", "dk", "no", "fi", "ie", "pl", "cz", "gr"}
_GCC_HOST_HINTS = ("amazon.ae", "amazon.sa", "noon.", "namshi", "sharafdg", "luluhypermarket",
                   "jarir", "extra.com", "xcite", "eureka", "boutiqaat", "sssports", "ounass", "dubaistore")
_US_HOST_HINTS = ("amazon.com", "ebay.com", "walmart", "bestbuy", "target.com", "homedepot",
                  "newegg", "bhphotovideo", "macys", "nordstrom", "gamestop")
_CN_HOST_HINTS = ("aliexpress", "alibaba", "temu.", "shein", "dhgate", "banggood",
                  "taobao", "tmall", "jd.com", "made-in-china", "1688.com", "lightinthebox")
_EU_HOST_HINTS = ("amazon.co.uk", "amazon.de", "amazon.fr", "amazon.it", "amazon.es",
                  "zalando", "argos", "currys", "mediamarkt", "fnac", "otto.de", "asos", "johnlewis")

def global_region_rank(item):
    """0=خليج، 1=أمريكا، 2=الصين، 3=أوروبا، 4=غير محدد/بقية العالم."""
    hay = " ".join(str(item.get(k) or "") for k in ("title", "source", "link", "domain", "snippet", "price", "currency")).lower()
    link = str(item.get("link") or "").lower()
    try:
        host = urllib.parse.urlparse(link).netloc.lower().replace("www.", "")
    except Exception:
        host = ""
    if any(h in host for h in _CN_HOST_HINTS):
        return 2
    if any(h in host for h in _GCC_HOST_HINTS):
        return 0
    if any(h in host for h in _US_HOST_HINTS):
        return 1
    if any(h in host for h in _EU_HOST_HINTS):
        return 3
    # نطاقات الدول
    for cc, tlds in COUNTRY_TLDS.items():
        if any(tld in host for tld in tlds):
            if cc in _GCC_CCS:
                return 0
            if cc == "us":
                return 1
            if cc == "cn":
                return 2
            if cc in _EU_CCS:
                return 3
            return 4
    if host.endswith(".cn"):
        return 2
    # عملات صريحة
    if any(c in hay for c in ("sar", "aed", "qar", "omr", "bhd", "ر.س", "د.إ", "ر.ق", "ر.ع", "د.ب")):
        return 0
    if any(c in hay for c in ("cny", "rmb", "yuan", "¥")):
        return 2
    if any(c in hay for c in ("eur", "gbp", "€", "£")):
        return 3
    if "usd" in hay or "us$" in hay or re.search(r"(?<![a-z])\$", hay):
        return 1
    return 4

def reorder_global_offers_text(txt, urls):
    """يعيد بناء نص النتائج العالمية بالترتيب الجغرافي (وداخل كل منطقة الأرخص أولاً)."""
    offers = extract_store_offers(txt)
    if len(offers) < 2:
        return txt
    lines = (txt or "").splitlines()
    offer_line_set = set()
    for line in lines:
        m = re.match(r"^(✅|🏆|•)\s*(.+?)\s*(?:—|–|-)\s*(.+)$", line.strip())
        if m and re.search(r"\d", m.group(3)):
            offer_line_set.add(line)
    header = [l for l in lines if l not in offer_line_set]
    ranked = []
    for o in offers:
        u = match_url(o.get("name", ""), urls or {})
        rank = global_region_rank({"link": u, "source": o.get("name", ""), "title": o.get("line", ""), "price": o.get("line", "")})
        price = _extract_numeric_price(o.get("line", "")) or 10**9
        ranked.append((rank, price, o))
    ranked.sort(key=lambda x: (x[0], x[1]))
    region_names = {0: "🇰🇼🇸🇦🇦🇪", 1: "🇺🇸", 2: "🇨🇳", 3: "🇪🇺", 4: "🌍"}
    out = [l for l in header if l.strip()]
    if out and not out[-1] == "":
        out.append("")
    for i, (rank, _price, o) in enumerate(ranked):
        body = re.sub(r"^(?:✅|🏆|•)\s*", "", o.get("line", "")).strip()
        flag = region_names.get(rank, "")
        out.append(f"{'✅' if i == 0 else '•'} {flag} {body}".replace("  ", " "))
    print(f"GLOBAL REGION ORDER: {[(region_names.get(r,''), o.get('name','')) for r,_p,o in ranked]}")
    return "\n".join(out)

# ---- v74.14: فلتر الثقة — حماية المستخدم من مواقع النصب والاحتيال ------------
ENABLE_TRUST_FILTER = env_bool("ENABLE_TRUST_FILTER", True)
_SUSPICIOUS_TLDS = (".tk", ".ml", ".ga", ".cf", ".gq", ".buzz", ".click", ".loan", ".rest", ".icu", ".cyou")

def is_suspicious_url(url):
    """علامات نصب قاطعة: بدون https، دومين رقمي (IP)، punycode، نطاقات مجانية مشبوهة،

    دومينات طويلة محشوة بالشرطات والأرقام (best-cheap-sale-2024...)."""
    u = str(url or "").strip()
    if not u:
        return False
    if u.startswith("http://"):
        return True
    try:
        host = urllib.parse.urlparse(u).netloc.lower().replace("www.", "")
    except Exception:
        return True
    if not host:
        return True
    if re.fullmatch(r"[0-9.:]+", host):
        return True
    if "xn--" in host:
        return True
    if any(host.endswith(t) for t in _SUSPICIOUS_TLDS):
        return True
    main = host.split(".")[0]
    if main.count("-") >= 3 or (len(main) > 30 and sum(c.isdigit() for c in main) >= 4):
        return True
    return False

_ALL_KNOWN_HOST_HINTS = _GCC_HOST_HINTS + _US_HOST_HINTS + _CN_HOST_HINTS + _EU_HOST_HINTS
_DOMAIN_TRUST_CACHE = {}
_DOMAIN_TRUST_LOCK = threading.Lock()
TRUST_FILTER_SYSTEM = """أنت خبير أمان تسوق إلكتروني تحمي المستخدمين من مواقع النصب.
سأعطيك قائمة مرقمة بدومينات ظهرت في نتائج بحث تسوق عالمية.
أعد فقط أرقام الدومينات لمتاجر أو منصات معروفة وموثوقة (عالمية أو خليجية أو إقليمية مشهورة).
استبعد: الدومينات المجهولة، مواقع النسخ المقلدة، المتاجر الوهمية، أي دومين لا تعرفه بثقة.
عند الشك استبعد — حماية المستخدم أهم من نتيجة إضافية.
أرجع JSON فقط: {"trusted":[1,3]}"""

def _host_of(url):
    try:
        return urllib.parse.urlparse(str(url or "")).netloc.lower().replace("www.", "")
    except Exception:
        return ""

def is_known_trusted_host(host):
    if not host:
        return False
    if host in set(STORE_DOMAINS.values()):
        return True
    if any(h in host for h in _ALL_KNOWN_HOST_HINTS):
        return True
    # نطاقات دول الخليج المحلية تمر (الحارس المحلي يضبطها أصلاً).
    if any(host.endswith(t) for tlds in (COUNTRY_TLDS.get(c, []) for c in _GCC_CCS) for t in tlds):
        return True
    return False

def trusted_hosts_verdict(hosts):
    """حكم ثقة ذكي (كاش لكل دومين) على الدومينات المجهولة — دفعة واحدة."""
    unknown = []
    verdicts = {}
    with _DOMAIN_TRUST_LOCK:
        for h in hosts:
            if h in _DOMAIN_TRUST_CACHE:
                verdicts[h] = _DOMAIN_TRUST_CACHE[h]
            elif h not in unknown:
                unknown.append(h)
    if unknown and ENABLE_TRUST_FILTER:
        numbered = "\n".join(f"{i}. {h}" for i, h in enumerate(unknown, 1))
        raw, _ = call_gemini([{"text": numbered}], system=TRUST_FILTER_SYSTEM, use_search=False)
        trusted_idx = set()
        try:
            data = json.loads(re.search(r"\{.*\}", raw or "", flags=re.S).group(0))
            trusted_idx = {int(x) for x in (data.get("trusted") or [])}
        except Exception:
            # فشل الحكم = نسمح (الفحوصات القاطعة فوقنا تحمي من الواضح).
            trusted_idx = set(range(1, len(unknown) + 1))
            print(f"TRUST AI PARSE FAIL — allowing batch: {raw!r}")
        with _DOMAIN_TRUST_LOCK:
            if len(_DOMAIN_TRUST_CACHE) > 3000:
                _DOMAIN_TRUST_CACHE.clear()
            for i, h in enumerate(unknown, 1):
                _DOMAIN_TRUST_CACHE[h] = i in trusted_idx
                verdicts[h] = i in trusted_idx
        dropped = [h for h in unknown if not verdicts.get(h)]
        if dropped:
            print(f"TRUST AI-DROP domains: {dropped}")
    else:
        for h in unknown:
            verdicts[h] = True
    return verdicts

def filter_trusted_global_matches(matches):
    """v74.14: للنتائج العالمية — يشيل الروابط المشبوهة والدومينات غير الموثوقة."""
    kept, unknown_hosts = [], []
    for m in matches:
        url = str(m.get("link") or "")
        if is_suspicious_url(url):
            print(f"TRUST HARD-DROP (suspicious url): {url[:90]}")
            continue
        host = _host_of(url)
        if not is_known_trusted_host(host):
            unknown_hosts.append(host)
        kept.append(m)
    if not unknown_hosts:
        return kept
    verdicts = trusted_hosts_verdict(unknown_hosts)
    final = []
    for m in kept:
        host = _host_of(m.get("link"))
        if is_known_trusted_host(host) or verdicts.get(host, True):
            final.append(m)
        else:
            print(f"TRUST DROP: {host} | {str(m.get('title',''))[:60]}")
    return final

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
    """v78: تم إلغاء الفلتر - نعرض الكل محلي+عالمي
    DISABLED FOR v78 - return all
    """
    return verified or {}

def filter_local_market_only_OLD_DISABLED(verified):
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
        # في الوضع المحلي: نبقي بطاقات عملة السوق فقط. في الوضع العالمي كل العملات مقبولة
        # لأنها ستُحوَّل إلى العملة المحلية قبل العرض.
        if not exclude_local:
            price_hay = f"{price_text} {currency}".lower()
            expected_currency = (current_market().get("currency") or "").lower()
            currency_aliases = {expected_currency}
            if expected_currency == "kwd": currency_aliases.update({"د.ك", "kd"})
            if expected_currency and price_hay.strip() and not any(x and x in price_hay for x in currency_aliases):
                if price_value in (None, ""):
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
        if exclude_local:
            # عالمي: السعر يُحوَّل دائماً إلى عملة المستخدم المحلية بالفلوس (1.950 د.ك) مع الأصل بين قوسين.
            shown, converted = display_global_price(price_value, price_text, currency, lang)
            if converted is not None:
                numeric = converted
        else:
            shown = format_lens_price(price_text, price_value, lang)
        offers[name] = {
            "url": url,
            "price": numeric,
            "price_text": shown,
            "is_local": is_local_lens_result(item),
            "title": title,
            "position": int(item.get("position") or i),
            "exact": bool(item.get("exact")),
            "section": item.get("section") or "",
            "image_url": item.get("image") or item.get("thumbnail") or "",
        }
        used_urls.add(url)
    # نفس المواصفات فقط: بطاقة عبوة أصغر أو سعة أقل ليست سعراً أرخص لنفس المنتج.
    offers = filter_same_size(offers, ((lens_context.get("chosen") or {}).get("title") or ""))
    # المتاجر المحلية أولاً حتى لو رتبها Google متأخرة؛ ثم exact ثم visual ثم ترتيب Lens.
    ranked = sorted(
        offers.items(),
        key=lambda kv: (
            0 if kv[1].get("is_local") else 1,
            0 if kv[1].get("exact") else 1,
            0 if kv[1].get("section") == "visual_matches" else 1,
            kv[1].get("position", 999),
        ),
    )
    # الاختيار بالجودة، لكن العرض النهائي دائماً من الأرخص للأغلى و✅ للأرخص.
    top = ranked[:MAX_STORES]
    top.sort(key=lambda kv: kv[1].get("price") if kv[1].get("price") is not None else 10**9)
    return dict(top)


def verify_lens_direct_matches(lens_context, local_only=True, exclude_local=False):
    """Fallback verifier for Lens URLs that had no price card. Exact matches get priority."""
    if not lens_context:
        return {}
    candidates = {}
    ordered = sorted(
        (lens_context.get("matches") or [])[:16],
        key=lambda m: (0 if m.get("exact") else 1, 0 if is_local_lens_result(m) else 1, int(m.get("position") or 99)),
    )
    for i, m in enumerate(ordered[:8], 1):
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
            lens_verified = filter_local_market_only(lens_verified)
            for info in lens_verified.values():
                info["shown"] = f"{format_price(info['price'])} {currency_label(lang)}"
            sorted_v = sorted(lens_verified.items(), key=lambda x: x[1]["price"])
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

        # v68: المتاجر الشهيرة نقطة انطلاق فقط — البحث مفتوح لأي متجر محلي منذ المحاولة الأولى.
        priority_stores = priority_stores_for(search_term)
        stores_hint = "، ".join(priority_stores)
        market_name = current_market().get("country_name", "Kuwait")
        if attempt == 1:
            search_scope = (
                f"ابدأ بأشهر المتاجر المحلية في {market_name} (مثل: {stores_hint}) لكن لا تحصر البحث فيها إطلاقاً: "
                f"اقبل أي متجر محلي آخر في {market_name} يبيع المنتج بسعر موثق ورابط صفحة منتج مباشر حتى لو لم يكن مشهوراً. "
                "إذا لم تجد فلا تكتب اعتذاراً مطولاً؛ أرجع بلا نتائج لننتقل لمحاولة أوسع. "
            )
        else:
            search_scope = (
                f"لم توجد نتيجة كافية في المحاولة السابقة. "
                f"اعمل الآن بحثاً عاماً واسعاً في جميع متاجر {market_name} التي تبيع المنتج، بما فيها المتاجر المتخصصة والصغيرة، "
                "مع تجنب الإعلانات المبوبة فقط مثل OpenSooq. لا تستبعد المتجر لمجرد أنه غير مشهور. "
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
            f"أعطني حتى {MAX_STORES} متاجر مختلفة مرتبة من الأرخص إلى الأغلى، وكل نتيجة يجب أن تحتوي سعراً رقمياً بعملة السوق الحالي "
            "ورابط صفحة المنتج المباشرة داخل المتجر. ممنوع روابط Google وصفحات البحث والتصنيف، وممنوع أي متجر أجنبي لا يبيع محلياً. "
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
            if not allow_global:
                # v68: البحث المحلي لا يعرض مواقع عالمية أبداً — تظهر فقط بعد زر «دوّر عالمياً».
                verified = filter_local_market_only(verified)
            if verified:
                # Google Lens استُخدم قبل البحث لتحديد المنتج. لا نحذف نتائج الأسعار بسبب تقييم بصري تخميني.
                sorted_v = sorted(verified.items(), key=lambda x: x[1]["price"])
                # v70: العنوان المعروض عربي؛ الاسم الإنجليزي للبحث فقط.
                title = product_title(txt, (ar_hint if lang == "ar" and ar_hint else search_term))
                lines = [title, ""]
                new_urls = {}
                for i, (name, info) in enumerate(sorted_v[:MAX_STORES]):
                    prefix = "✅" if i == 0 else "•"
                    currency = currency_label(lang)
                    size_note = format_pack_size(extract_pack_size(info.get("title", "")))
                    size_suffix = f" ({size_note})" if size_note else ""
                    lines.append(f"{prefix} {name} — {format_price(info['price'])} {currency}{size_suffix}")
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
                if not allow_global and is_foreign_lens_result({"link": matched, "source": offer["name"], "title": offer["line"]}):
                    # v68: نفس الحارس المحلي حتى للعروض التي تعذّر فحص صفحتها.
                    print(f"LOCAL MODE REJECT FOREIGN (unverified): {offer['name']} -> {matched}")
                    continue
                kept.append(offer)
            # v68: الترتيب من الأرخص للأغلى حتى في المسار غير المفحوص.
            kept.sort(key=lambda o: _extract_numeric_price(o.get("line", "")) or 10**9)
            if kept:
                title = product_title(txt, (ar_hint if lang == "ar" and ar_hint else search_term))
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


def _old_layer_search(query, lang, prompt_text=None, lens_context=None, allow_global=False, english_name=""):
    """Second layer: the broad multi-query search logic from the older bot.

    v70: صيغ البحث بالاسم الإنجليزي أولاً (فهرسة المتاجر به أدق)، مع إبقاء صيغة عربية واحدة كاحتياط.
    """
    if not OLD_LAYER_ENABLED:
        return "", {}
    search_name = english_name or query
    if allow_global:
        base_prompt = (
            f"ابحث عالميًا عن {search_name}. استبعد تمامًا أي متجر داخل {current_market().get('country_name', 'بلد المستخدم')}, لأن البحث المحلي انتهى بالفعل. اقبل المتاجر الأجنبية الموثوقة فقط، مع سعر رقمي واضح ورابط صفحة المنتج المباشر، واذكر العملة الأصلية. {LANG_INSTR[lang]}"
        )
    else:
        base_prompt = prompt_text or (
            f"ابحث عن {search_name} في {current_market().get('country_name', 'Kuwait')} في أي متجر محلي يبيعه — المشهور وغير المشهور. متوفر فقط وبسعر رقمي واضح ورابط صفحة منتج مباشر. {LANG_INSTR[lang]}"
        )
    market_name = current_market().get("country_name", "Kuwait")
    if allow_global:
        variants = [
            base_prompt,
            f"{search_name} buy online worldwide exact product direct page price {LANG_INSTR[lang]}",
            f"{search_name} international stores exact visual match direct product link {LANG_INSTR[lang]}",
        ]
    elif current_market().get("country") == "kw":
        variants = [
            base_prompt,
            f"{search_name} price Kuwait buy online Xcite Eureka Blink Noon Jarir Lulu Carrefour Best Al Yousifi Pro Sports Intersport Decathlon 3RoodQ8 Tigro or any Kuwaiti store - compare prices {LANG_INSTR[lang]}",
            f"{query} شراء اونلاين الكويت سعر متوفر متجر كويتي صفحة المنتج مباشرة {LANG_INSTR[lang]}",
        ]
    else:
        variants = [
            base_prompt,
            f"{search_name} best price in {market_name} local stores direct product page {LANG_INSTR[lang]}",
            f"{search_name} buy online {market_name} local delivery price in {current_market().get('currency','local currency')} {LANG_INSTR[lang]}",
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
    verified = filter_same_size(verified, query)
    if not allow_global:
        # v68: البحث المحلي لا يعرض مواقع عالمية أبداً — تظهر فقط بعد موافقة المستخدم.
        verified = filter_local_market_only(verified)
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

    offers = list(dedup.values())
    def rank(o):
        quality = 0
        quality += 100 if o.get("exact") else 0
        quality += 40 if o.get("is_local") else 0
        # v69: أولوية الفئة — متخصص الفئة يسبق المنصات العامة.
        quality += _store_priority_value(o.get("name", ""), o.get("url", ""), query) * 2
        quality += {"shopping": 15, "new": 12, "old": 8}.get(o.get("layer"), 8)
        quality += max(0, 20 - min(int(o.get("lens_position", 999)), 20))
        return (-quality, o.get("price", 10**9))
    offers.sort(key=rank)
    chosen = offers[:MAX_STORES]
    # الجودة تُستخدم لاختيار المرشحين فقط؛ العرض النهائي دائماً من الأرخص للأغلى و✅ للأرخص.
    chosen.sort(key=lambda o: o.get("price") if o.get("price") is not None else 10**9)

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
    بترتيب فئة المنتج ثم من الأرخص إلى الأغلى.
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

def send_whatsapp_list(to, body, rows, bot_id, button_title="اختر"):
    """v74: رسالة قائمة تفاعلية (حتى 10 صفوف) — لاختيار منتج من مقارنة البراندات."""
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    clean_rows=[]
    for r in rows[:10]:
        row={"id":r["id"],"title":str(r.get("title",""))[:24]}
        desc=str(r.get("description","") or "")[:72]
        if desc: row["description"]=desc
        clean_rows.append(row)
    payload={"messaging_product":"whatsapp","to":to,"type":"interactive","interactive":{
        "type":"list","body":{"text":body[:1024]},
        "action":{"button":button_title[:20],"sections":[{"title":button_title[:24],"rows":clean_rows}]}}}
    try:
        r=requests.post(url,json=payload,headers=h,timeout=15)
        if not r.ok: print(f"LIST MSG ERR {r.status_code}: {r.text[:200]}")
        return r.ok
    except Exception as e:
        print(f"LIST MSG ERR: {e}"); return False

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
    """v76: Lens-consensus -> broad local alternative search.

    For image-origin searches, ``item['query']`` is now the canonical identity agreed
    by the majority of Lens local + global titles. The v26 tournament then searches
    for alternatives and unions discoveries across its parallel runs.
    """
    activate_market(phone)
    bot_id = item["bot_id"]; lang = item["lang"]; query = item["query"]
    send_whatsapp_text(phone, T(lang, "similar_searching"), bot_id)

    base = short_query(re.sub(r"^.*?—\s*", "", query).strip() or query) or short_query(query)
    if re.search(r"[\u0600-\u06FF]", base):
        base_other = english_search_name(base)
    else:
        base_other = arabic_search_name(base)

    evidence_aliases = []
    for x in (item.get("aliases") or []):
        x = _clean_lens_identity_title(x)
        if x and normalize_ar(x) != normalize_ar(base) and x not in evidence_aliases:
            evidence_aliases.append(x)
    evidence_aliases = evidence_aliases[:4]
    evidence_text = " | ".join(evidence_aliases)

    market_name = current_market().get("country_name", "Kuwait")
    limit = max(MAX_STORES, int(item.get("max_results") or SIMILAR_MAX_STORES))
    title_line = f"📦 بدائل مشابهة: {base}"

    prompts = [
        (f"Google Lens تعرّف على المنتج من أغلبية نتائجه المحلية والعالمية بهذا الاسم: {base}. "
         + (f"الاسم/المرادف الآخر: {base_other}. " if base_other and base_other != base else "")
         + (f"ومن عناوين Lens الممثلة للهوية: {evidence_text}. " if evidence_text else "")
         + f"استخدم هذه المعلومات فقط لفهم هوية المنتج، ثم ابحث بعمق في Google عن حتى {limit} بدائل حقيقية مختلفة عن نفس الموديل الأصلي، "
         f"من نفس الفئة والاستخدام وبمواصفات ومستوى جودة قريب، ومتوفرة الآن في متاجر {market_name} المحلية فقط. "
         "لا تقيد البحث بالبراند الأصلي: جرّب البراندات المنافسة والمرادفات العربية والإنجليزية ونتائج Google المتأخرة. "
         "تنسيق كل نتيجة إلزامي ولا تغيّره: ✅ [اسم المتجر فقط] — [اسم البديل الفعلي] — [السعر الرقمي بعملة السوق]. "
         "المقطع الأول بعد ✅ أو • يجب أن يكون اسم المتجر حصراً، وليس اسم المنتج. اربط كل متجر بصفحة المنتج المباشرة من نفس دومين المتجر. "
         f"رتب الأرخص أولاً. لا تعرض المنتج الأصلي نفسه ولا أي إكسسوار/قطعة غيار. اجعل سطر 📦 بالضبط: بدائل مشابهة: {base}. "
         f"{LANG_INSTR[lang]}"),
        (f"Google Lens majority identity for the reference product: {base}. "
         + (f"Alternate-language identity: {base_other}. " if base_other and base_other != base else "")
         + (f"Representative Lens titles: {evidence_text}. " if evidence_text else "")
         + f"Find up to {limit} genuinely different but closely comparable alternatives in {market_name} local online stores. "
         "Search competitor brands, synonyms, and deeper Google results. Match the same main category, purpose, form factor and nearby specification/quality tier. "
         "Exclude the exact original model, accessories, spare parts, manuals and foreign stores. "
         "MANDATORY line format: ✅ [STORE NAME ONLY] — [ACTUAL ALTERNATIVE PRODUCT NAME] — [NUMERIC LOCAL PRICE]. "
         "The first field after ✅/• MUST be the store name, never the product name. Ground each store to that same store's direct product-page URL; sort cheapest first. "
         f"Write the 📦 line exactly as: بدائل مشابهة: {base}. {LANG_INSTR[lang]}"),
    ]

    # Usually the first prompt is enough. If it fails, the English formulation is a second independent chance.
    for prompt in prompts:
        txt, urls = legacy_v26_best_of_search(
            [{"text": prompt}],
            max_results=limit,
            merge_offers=True,
            merge_title=title_line,
        )
        # v76.3: keep the full grounded URL map here. send_product_result will prefer
        # direct product pages, guard store/domain identity, then safely fall back.
        if not txt or is_no_result_answer(txt) or not extract_store_offers(txt, limit=limit):
            continue

        kept_urls = {}
        for n, u in urls.items():
            if is_foreign_lens_result({"link": u, "source": n, "title": n}):
                print(f"SIMILAR v76 REJECT FOREIGN: {n} -> {u}")
                continue
            kept_urls[n] = u

        result_type = send_product_result(
            phone, txt, kept_urls, bot_id, lang, base,
            max_stores=limit,
            relevance_mode="similar",
        )
        if result_type != "none":
            return
    send_whatsapp_text(phone, T(lang, "similar_none"), bot_id)


def run_global_search(phone, item):
    activate_market(phone)
    bot_id = item["bot_id"]; lang = item["lang"]; query = item["query"]
    send_whatsapp_text(phone, T(lang, "global_searching"), bot_id)

    txt, urls = "", {}
    # v77.7: للبحث النصي، جرب المحرك العالمي المباشر أولاً (أكثر تسامحاً)
    is_text_search = not item.get("lens_context")

    if is_text_search:
        try:
            market_name = current_market().get("country_name", "Kuwait")
            global_prompt = (
                f"ابحث عالمياً عن {query} في متاجر خارج {market_name} فقط. "
                f"استبعد أي متجر داخل {market_name}. أولوية البحث والعرض إلزامياً بهذا الترتيب: {MANDATORY_PRIORITY_PROMPT}. "
                "إذا كان نفس المنتج المطابق موجوداً في متجر مفضل، قدّمه على أي متجر غير مفضل. لا تستخدم موديل مختلف/إكسسوار لإجبار الأولوية. "
                f"اعرض حتى 5 نتائج مختلفة بسعر رقمي واضح ورابط صفحة منتج مباشر. اذكر السعر والعملة. {LANG_INSTR[lang]}"
            )
            txt, urls = legacy_v26_best_of_search([{"text": global_prompt}], max_results=MAX_STORES)
            print(f"GLOBAL TEXT DIRECT V26: txt={bool(txt)} urls={len(urls) if urls else 0}")
        except Exception as e:
            print(f"GLOBAL TEXT DIRECT CRASH: {e}")

    # إذا فشل المباشر، جرب المحرك الثلاثي
    if not txt or not urls or not extract_store_offers(txt):
        try:
            t2, u2 = search_product(
                query, lang, prompt_text=item.get("prompt_text"),
                lens_context=item.get("lens_context"), allow_global=True,
            )
            if t2 and u2 and extract_store_offers(t2):
                txt, urls = t2, u2
                print(f"GLOBAL THREE-LAYER SUCCESS: {query}")
        except Exception as e:
            print(f"GLOBAL THREE-LAYER CRASH: {e}")

    # إذا فشل الاثنين، جرب مرة ثالثة ببروميت إنجليزي
    if not txt or not urls or not extract_store_offers(txt):
        try:
            en_q = english_search_name(query) or query
            global_prompt_en = (
                f"Search worldwide for {en_q} outside {current_market().get('country_name','Kuwait')}. "
                f"Find 5 different results from trusted international stores (Amazon.com, Amazon.ae, eBay, AliExpress, Temu, Walmart) with numeric price and direct product page link. Sort cheapest first. {LANG_INSTR[lang]}"
            )
            txt3, urls3 = legacy_v26_best_of_search([{"text": global_prompt_en}], max_results=MAX_STORES)
            if txt3 and urls3 and extract_store_offers(txt3):
                txt, urls = txt3, urls3
                print(f"GLOBAL EN FALLBACK SUCCESS: {en_q}")
        except Exception as e:
            print(f"GLOBAL EN FALLBACK CRASH: {e}")

    if not txt:
        send_whatsapp_text(phone, T(lang, "global_none"), bot_id)
        return

    # تنظيف وفلترة متساهلة جداً للنص
    filtered_urls = {}
    for name, url in (urls or {}).items():
        if not url or not url.startswith("http"):
            continue
        # للصور فقط نرفض المحلي، للنص نقبل الكل (حتى لو محلي بالخطأ) لتجنب "ما لقيت نتيجة"
        if item.get("lens_context"):
            if is_local_lens_result({"link": url, "source": name, "title": name}):
                print(f"GLOBAL FINAL GUARD REJECT LOCAL (image): {name} -> {url}")
                continue
        if is_suspicious_url(url):
            print(f"GLOBAL TRUST HARD-DROP: {name} -> {url}")
            continue
        filtered_urls[name] = url

    # فلتر الثقة: للنص نتساهل أكثر - لا نحذف إلا المشبوه جداً
    if filtered_urls and ENABLE_TRUST_FILTER and not is_text_search:
        try:
            hosts = {n: _host_of(u) for n, u in filtered_urls.items()}
            unknown = [h for h in hosts.values() if h and not is_known_trusted_host(h)]
            if unknown:
                verdicts = trusted_hosts_verdict(unknown)
                for n in list(filtered_urls):
                    h = hosts.get(n, "")
                    if h and not is_known_trusted_host(h) and not verdicts.get(h, True):
                        print(f"GLOBAL TRUST DROP: {n} -> {filtered_urls[n]}")
                        filtered_urls.pop(n, None)
        except Exception as e:
            print(f"TRUST VERDICT CRASH: {e}")

    # إذا بقي لدينا نص لكن الروابط فلترت كلها، نحاول إرسال النص كما هو مع روابط الصفحة الرئيسية للمتاجر
    if not filtered_urls and txt:
        print(f"GLOBAL NO URLS LEFT BUT TXT EXISTS - TRYING FALLBACK URLS")
        # استخرج أسماء المتاجر من النص وحاول جلب صفحتها الرئيسية
        offers = extract_store_offers(txt, limit=MAX_STORES)
        for o in offers:
            hp = resolve_store_homepage(o.get("name",""))
            if hp:
                filtered_urls[o.get("name","")] = hp
        if not filtered_urls:
            filtered_urls = urls  # أرجع الأصلي كملاذ أخير

    if not txt or not extract_store_offers(txt):
        send_whatsapp_text(phone, T(lang, "global_none"), bot_id)
        return

    if not filtered_urls:
        # أرسل النص فقط بدون أزرار إذا فشلت الروابط كلها
        send_whatsapp_text(phone, txt, bot_id)
        return

    # نظف أسطر العروض التي حذفت روابطها
    if len(filtered_urls) != len(urls or {}):
        kept_names = {normalize_name(n) for n in filtered_urls}
        kept_lines = []
        for line in (txt or "").splitlines():
            offer_match = re.match(r"^(?:✅|🏆|•)\s*(.+?)\s*(?:—|–|-)\s*", line.strip())
            if offer_match and normalize_name(offer_match.group(1)) not in kept_names:
                continue
            kept_lines.append(line)
        txt = "\n".join(kept_lines).strip()
        urls = filtered_urls
    else:
        urls = filtered_urls

    if not txt:
        send_whatsapp_text(phone, T(lang, "global_none"), bot_id)
        return

    try:
        txt = reorder_global_offers_text(txt, urls)
    except Exception as e:
        print(f"REORDER GLOBAL CRASH: {e}")

    send_product_result(phone, txt, urls, bot_id, lang, query)

def _peek_pending(store, phone):
    """v74: قراءة الطلب المعلق دون حذفه — حتى يقدر المستخدم يضغط أكثر من خيار (مشابه ثم عالمي...)."""
    item = store.get(phone)
    if not item or time.time() - item.get("ts", 0) > GLOBAL_PENDING_TTL:
        store.pop(phone, None)
        return None
    return item


def process_interactive_message(message, bot_id):
    from_number=message["from"]
    inter=(message.get("interactive") or {})
    # v74: دعم القوائم (list_reply) إضافة إلى الأزرار.
    reply=inter.get("button_reply") or inter.get("list_reply") or {}
    btn_id=reply.get("id","")
    if btn_id.startswith("pick_"):
        # v74.9: الاختيار من قائمة المقارنة يشتغل دائماً حتى بعد انتهاء صلاحية القائمة —
        # عنوان الخيار موجود في الضغطة نفسها (list_reply.title) فلا نعتمد على المخزّن.
        item = _peek_pending(PENDING_BRAND_PICKS, from_number) or {}
        idx = int(btn_id[5:]) if btn_id[5:].isdigit() else -1
        opts = item.get("options") or []
        picked = opts[idx] if 0 <= idx < len(opts) else ""
        if not picked:
            # v74.10: الوصف يحمل الاسم الأصلي الكامل (العنوان قد يكون ترجمة مختصرة).
            picked = (reply.get("description") or "").strip() or (reply.get("title") or "").strip()
        if picked:
            activate_market(from_number)
            lang_ = item.get("lang") or USER_LANG.get(from_number, "ar")
            try:
                execute_product_search(from_number, picked, item.get("bot_id") or bot_id, lang_)
            except Exception as e:
                print(f"PICK SEARCH ERR: {e}")
                send_whatsapp_text(from_number, T(lang_, "not_found"), bot_id)
        else:
            # لا صمت أبداً: ما قدرنا نحدد الخيار — نطلب كتابته نصاً.
            lang_ = USER_LANG.get(from_number, "ar")
            send_whatsapp_text(from_number, ("اكتب اسم المنتج اللي تبيه وأدور لك عليه 👍" if lang_ == "ar" else "Type the product name and I'll search it for you 👍"), bot_id)
        return
    if btn_id.startswith("cart_"):
        # v75: المستخدم اختار متجراً لسلته الموحدة — نرسل كل أصنافه بروابطها داخله.
        item = _peek_pending(PENDING_CART_PICKS, from_number)
        lang_ = (item or {}).get("lang", USER_LANG.get(from_number, "ar"))
        idx = int(btn_id[5:]) if btn_id[5:].isdigit() else -1
        if item and 0 <= idx < len(item.get("stores") or []):
            activate_market(from_number)
            try:
                send_cart_from_store(from_number, idx, item["stores"], item.get("products") or [], item.get("bot_id") or bot_id, lang_)
            except Exception as e:
                print(f"CART PICK ERR: {e}")
                send_whatsapp_text(from_number, T(lang_, "not_found"), bot_id)
        else:
            # القائمة انتهت صلاحيتها — ما نقدر نسترجع أسعار الأصناف من الضغطة وحدها.
            send_whatsapp_text(from_number, T(lang_, "cart_expired"), bot_id)
        return
    if btn_id == "map_open":
        # v74.14: خيار الخريطة من قائمة «تبي أكثر» — خريطة آخر بحث محفوظ.
        activate_market(from_number)
        send_last_search_map(from_number, bot_id, USER_LANG.get(from_number, "ar"))
        return
    if btn_id == "lf_yes":
        # عرض نتائج Lens العالمية؛ وإذا ما فيه نتائج مخزنة نشغل البحث العالمي النصي الجديد.
        item = _peek_pending(PENDING_LENS_FOREIGN, from_number)
        activate_market(from_number)
        if item and item.get("matches"):
            _send_lens_match_batch(
                from_number, item["matches"], item.get("bot_id") or bot_id,
                item.get("lang", "ar"), convert_prices=True,
            )
        elif item and item.get("query"):
            run_global_search(from_number, {
                "bot_id": item.get("bot_id") or bot_id,
                "lang": item.get("lang", "ar"), "query": item["query"],
            })
        return
    if btn_id == "lens_more":
        # v81.5: الدفعة التالية من بطاقات اللينز المؤجلة — وزر جديد إذا باقي أكثر.
        item = _peek_pending(PENDING_LENS_MORE, from_number)
        lang_ = (item or {}).get("lang", USER_LANG.get(from_number, "ar"))
        activate_market(from_number)
        cards = (item or {}).get("cards") or []
        if not cards:
            send_whatsapp_text(from_number, T(lang_, "more_results_expired"), bot_id)
            return
        card_cap = max(MAX_STORES, 8)
        batch, remaining = cards[:card_cap], cards[card_cap:]
        _send_lens_card_batch_v815(from_number, batch, item.get("bot_id") or bot_id, lang_, item.get("query") or "")
        if remaining:
            _offer_lens_more(from_number, item.get("bot_id") or bot_id, lang_, item.get("query") or "", remaining)
        else:
            PENDING_LENS_MORE.pop(from_number, None)
            send_whatsapp_text(from_number, T(lang_, "more_results_done"), bot_id)
        return
    if btn_id == "lf_similar":
        # v76: البدائل تبدأ من هوية Lens المتفق عليها عبر النتائج المحلية + العالمية.
        item = _peek_pending(PENDING_LENS_FOREIGN, from_number)
        query = ((item or {}).get("similar_query") or (item or {}).get("query")
                 or (LAST_SEARCH.get(from_number) or {}).get("product"))
        if query:
            activate_market(from_number)
            run_similar_search(from_number, {
                "bot_id": (item or {}).get("bot_id") or bot_id,
                "lang": (item or {}).get("lang", USER_LANG.get(from_number, "ar")),
                "query": query,
                "aliases": (item or {}).get("similar_aliases") or [],
                "max_results": SIMILAR_MAX_STORES,
            })
        return
    if btn_id == "ls_yes":
        # عرض عروض برامج التواصل.
        item = _peek_pending(PENDING_LENS_SOCIAL, from_number)
        lang_ = (item or {}).get("lang", USER_LANG.get(from_number, "ar"))
        activate_market(from_number)
        if item and item.get("matches"):
            _send_lens_match_batch(
                from_number, item["matches"], item.get("bot_id") or bot_id,
                lang_, convert_prices=False, per_store_max=LENS_MAX_CARDS,
            )
        else:
            send_whatsapp_text(from_number, T(lang_, "social_none"), bot_id)
        return
    if btn_id == "ls_no":
        PENDING_LENS_SOCIAL.pop(from_number, None)
        send_whatsapp_text(from_number, T(USER_LANG.get(from_number, "ar"), "declined_ok"), bot_id)
        return
    if btn_id == "lf_no":
        PENDING_LENS_FOREIGN.pop(from_number, None)
        send_whatsapp_text(from_number, T(USER_LANG.get(from_number, "ar"), "declined_ok"), bot_id)
        return
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

_LENS_TITLE_JUNK_RE = re.compile(
    r"(?i)\b(online at best price|at best price|best price|shop online|buy online|order online|online)\b"
)

def _clean_lens_title(title):
    """v72.2: تنظيف عنوان النتيجة من حشو SEO (Online at Best Price | Lu ...) ليصير مقروءاً."""
    t = str(title or "").split("|")[0]
    t = _LENS_TITLE_JUNK_RE.sub(" ", t)
    t = re.sub(r"^\s*(buy|shop|order|اشتري|شراء)\s+", "", t, flags=re.I)
    t = " ".join(t.split())
    t = re.sub(r"[\-–—:،,.|]+\s*$", "", t).strip()
    # عناوين Google المقصوصة تترك حرفاً يتيماً بالنهاية ("... Online a") — نشيله،
    # لكن نحافظ على وحدات الحجم بعد الأرقام مثل "1.5 L".
    t = re.sub(r"(?<=[A-Za-z])\s+[A-Za-z]{1,2}$", "", t).strip()
    return t


def _lens_store_label(m):
    source = (m.get("source") or "").strip()
    if source:
        return source[:40]
    try:
        host = urllib.parse.urlparse(m.get("link") or "").netloc.replace("www.", "")
        return (host.split(".")[0] or "Store").title()
    except Exception:
        return "Store"


def _send_lens_match_batch(from_number, matches, bot_id, lang, header="", convert_prices=False, per_store_max=None):
    """v72.2: بدون رسالة قائمة — بطاقات CTA مباشرة، كل بطاقة: اسم نظيف + سعر بارز + متجر.

    التنويع: round-robin على المتاجر — متجر مختلف لكل بطاقة أولاً، ثم نكمل من نفس
    المتاجر بحد أقصى LENS_PER_STORE_MAX لكل متجر (حتى لا تكون كل البطاقات من لولو).
    v73: الترتيب النهائي — المسعّر أولاً من الأرخص إلى الأغلى، ثم غير المسعّر.
    """
    per_store = per_store_max if per_store_max else LENS_PER_STORE_MAX
    # v74.14: النتائج العالمية تمر أولاً على فلتر الثقة (حماية من مواقع النصب).
    if convert_prices:
        matches = filter_trusted_global_matches(matches)
    # 1) تجميع المرشحين أصحاب الروابط الصالحة حسب المتجر (host) مع الحفاظ على ترتيب Google.
    by_host, host_order = {}, []
    for m in matches:
        title = _clean_lens_title(m.get("title"))
        url = (m.get("link") or "").strip()
        try:
            host = urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
        except Exception:
            host = ""
        if not title or not url.startswith("http") or not host or "google." in host:
            continue
        if host not in by_host:
            by_host[host] = []
            host_order.append(host)
        if len(by_host[host]) < per_store:
            by_host[host].append((m, title, url))
    if not by_host:
        return False

    # 2) round-robin: الجولة الأولى بطاقة من كل متجر مختلف، ثم الجولة الثانية تكمل الفراغ.
    picked, used_urls = [], set()
    for round_i in range(per_store):
        for host in host_order:
            if len(picked) >= LENS_MAX_CARDS:
                break
            items = by_host[host]
            if round_i < len(items):
                m, title, url = items[round_i]
                if url in used_urls:
                    continue
                picked.append((m, title, url))
                used_urls.add(url)
        if len(picked) >= LENS_MAX_CARDS:
            break

    # 3) v72.3: البطاقات التي بلا سعر من Google — نجلب السعر من صفحة المتجر نفسها (مجاني وسريع).
    def _fetch_page_price(url):
        cached = VERIFIED_PAGE_CACHE.get(url)
        if cached and (time.time() - cached["ts"] < 600):
            return cached["data"]
        info = parse_product_data(fetch_html(url), url)
        if info:
            VERIFIED_PAGE_CACHE[url] = {"data": info, "ts": time.time()}
        return info

    final_picked = picked[:LENS_MAX_CARDS]
    # v74: السعر الحقيقي بلا تقريب — Google أحياناً يقرّب (1.000 بدل 1.250)، لذلك نقرأ
    # سعر صفحة المتجر نفسها لكل البطاقات (ضمن السقف) ونعتمده فوق سعر Google عند وجوده.
    to_verify = [(i, url) for i, (_m, _t, url) in enumerate(final_picked)][:LENS_PRICE_FETCH_MAX]
    if to_verify:
        for i, info in RESOLVER.map(lambda x: (x[0], _fetch_page_price(x[1])), to_verify):
            if info and info.get("price"):
                m = final_picked[i][0]
                old_val = m.get("price_value")
                m["price_value"] = info["price"]
                m["price"] = ""  # نص Google القديم قد يكون مقرّباً — نعتمد سعر الصفحة.
                if info.get("currency"):
                    m["currency"] = info["currency"]
                try:
                    if old_val not in (None, "") and abs(float(old_val) - float(info["price"])) >= 0.001:
                        print(f"PRICE CORRECTED (Google {old_val} -> page {info['price']}): {final_picked[i][2][:70]}")
                except Exception:
                    pass

    # v73: الفرز النهائي — البطاقات المسعّرة أولاً من الأرخص إلى الأغلى، ثم غير المسعّرة
    # (بترتيب Google بينها). التحويل للعملة المحلية يدخل في المقارنة للنتائج العالمية.
    def _numeric_price_of(m):
        raw = str(m.get("price") or "").strip()
        num = None
        try:
            num = float(m.get("price_value")) if m.get("price_value") not in (None, "") else None
        except Exception:
            num = None
        if num is None:
            num = _extract_numeric_price(raw)
        if num is None:
            return None
        if convert_prices:
            _shown, conv = display_global_price(num, raw, m.get("currency") or "", lang)
            return conv if conv is not None else num
        return num

    if convert_prices:
        # v74.13: عالمي — ترتيب جغرافي أولاً (خليج -> أمريكا -> الصين -> أوروبا -> الباقي)،
        # ثم داخل كل منطقة: المسعّر أولاً من الأرخص إلى الأغلى.
        final_picked.sort(key=lambda x: (
            global_region_rank(x[0]),
            (0, p) if (p := _numeric_price_of(x[0])) is not None else (1, 0.0),
        ))
    else:
        final_picked.sort(key=lambda x: ((0, p) if (p := _numeric_price_of(x[0])) is not None else (1, 0.0)))

    # 4) v72.3: للمستخدم العربي نترجم العناوين دفعة واحدة (كاش)؛ البراند يبقى لاتيني.
    title_map = {}
    if lang == "ar":
        title_map = arabic_titles([t for _m, t, _u in final_picked])

    # 5) بطاقة CTA لكل عرض: الاسم + سطر سعر بارز فقط — اسم المتجر يظهر على الزر بدون تكرار.
    sent = 0
    for m, title, url in final_picked:
        shown_title = title_map.get(title, title) if lang == "ar" else title
        raw_price = str(m.get("price") or "").strip()
        price_txt = ""
        if raw_price or m.get("price_value") not in (None, ""):
            if convert_prices:
                price_txt, _ = display_global_price(m.get("price_value"), raw_price, m.get("currency") or "", lang)
            else:
                price_txt = format_lens_price(raw_price, m.get("price_value"), lang, m.get("currency") or None)
        store = _lens_store_label(m)
        body_lines = [f"🛍️ {shown_title[:130]}"]
        if price_txt:
            body_lines.append("")
            body_lines.append(f"💰 السعر: *{price_txt}*" if lang == "ar" else f"💰 Price: *{price_txt}*")
        send_whatsapp_cta(from_number, "\n".join(body_lines)[:1024], url, bot_id, f"🛒 {store[:18]}")
        sent += 1
    print(f"LENS CTA BATCH: {sent} cards from {len({urllib.parse.urlparse(u).netloc for _, _, u in final_picked})} stores")
    return sent > 0


def _store_pending_lens_foreign(phone, bot_id, lang, matches):
    PENDING_LENS_FOREIGN[phone] = {
        "bot_id": bot_id, "lang": lang,
        "matches": matches[:LENS_RESULT_LIMIT], "ts": time.time(),
    }


def _pop_pending_lens_foreign(phone):
    item = PENDING_LENS_FOREIGN.pop(phone, None)
    if not item or time.time() - item.get("ts", 0) > GLOBAL_PENDING_TTL:
        return None
    return item


def is_local_social_result(m):
    """v74.15: بوست تواصل يخص بلد المستخدم فقط: اسم البلد، العملة المحلية، مفتاح

    الاتصال (+965)، أو رموز البلد الدارجة في الحسابات (q8/kwt/kw للكويت)."""
    market = current_market()
    cc = (market.get("country") or DEFAULT_COUNTRY).lower()
    hay = " ".join(str(m.get(k) or "") for k in ("title", "source", "link", "snippet", "price", "currency")).lower()
    hay_norm = normalize_ar(hay)
    names = [str(market.get("country_name") or "").lower(), (COUNTRY_NAMES_AR.get(cc) or "")]
    if any(n and normalize_ar(n) in hay_norm for n in names):
        return True
    if any(mk in hay for mk in COUNTRY_CURRENCY_MARKERS.get(cc, ())):
        return True
    # مفتاح الاتصال الدولي (+965 للكويت...) — إعلانات التواصل عادة تحط رقم واتساب.
    calling = next((code for code, c in CALLING_CODE_TO_COUNTRY.items() if c == cc and len(code) == 3), "")
    if calling and (f"+{calling}" in hay or f"00{calling}" in hay):
        return True
    # رموز دارجة في أسماء الحسابات والهاشتاقات.
    cc_tokens = {"kw": ("q8", "kwt", "_kw", "kw_", ".kw", "kuwaitcity", "kuwait")}.get(cc, ())
    if any(t in hay for t in cc_tokens):
        return True
    return False


def is_social_result(m):
    """v73: نتيجة من برامج التواصل (انستجرام/تيك توك/سناب/يوتيوب...)."""
    try:
        host = urllib.parse.urlparse(str(m.get("link") or "")).netloc.lower()
    except Exception:
        return False
    return bool(host) and any(h in host for h in SOCIAL_HOSTS)


# ---- v74: فلتر مواقع البيع فقط -----------------------------------------------
SHOP_FILTER_SYSTEM = """أنت مصنف صفحات ويب لبوت تسوق.
سأعطيك قائمة مرقمة: عنوان الصفحة — الدومين.
أعد فقط أرقام الصفحات التي هي صفحات منتج للبيع في متجر إلكتروني (فيها إمكانية شراء).
استبعد: المقالات، الأخبار، المدونات، المراجعات، الشروحات، المنتديات، الموسوعات، صفحات الشركات التعريفية.
أرجع JSON فقط بهذا الشكل بدون أي شرح: {"keep":[1,3,5]}"""

def filter_shopping_results(matches):
    """v74: يبقي فقط نتائج المتاجر التي تبيع المنتج فعلاً.

    ثلاث طبقات: قبول تلقائي (سعر/متجر معروف)، رفض تلقائي (مواقع ليست متاجر)،
    ثم حكم ذكاء اصطناعي سريع رخيص واحد للدفعة الغامضة المتبقية.
    """
    if not matches:
        return matches
    known_store_hosts = tuple(set(STORE_DOMAINS.values()))
    auto_keep, ambiguous = [], []
    for m in matches:
        link = str(m.get("link") or "").lower()
        try:
            host = urllib.parse.urlparse(link).netloc.lower().replace("www.", "")
        except Exception:
            host = ""
        if not host:
            continue
        if any(b in host for b in NON_SHOP_HOSTS):
            print(f"SHOP FILTER AUTO-DROP: {host} | {str(m.get('title',''))[:60]}")
            continue
        has_price = bool(str(m.get("price") or "").strip()) or m.get("price_value") not in (None, "")
        looks_store = any(d in host for d in known_store_hosts) or m.get("in_stock") is not None
        if has_price or looks_store or m.get("section") == "products":
            auto_keep.append(m)
        else:
            ambiguous.append(m)
    if not ambiguous or not ENABLE_SHOP_AI_FILTER:
        return auto_keep + ambiguous
    # حكم ذكاء اصطناعي: اتصال سريع واحد (بدون بحث) للدفعة الغامضة كلها.
    batch = ambiguous[:20]
    numbered = []
    for i, m in enumerate(batch, 1):
        try:
            host = urllib.parse.urlparse(str(m.get("link") or "")).netloc.replace("www.", "")
        except Exception:
            host = ""
        numbered.append(f"{i}. {str(m.get('title',''))[:90]} — {host}")
    raw, _ = call_gemini([{"text": "\n".join(numbered)}], system=SHOP_FILTER_SYSTEM, use_search=False)
    kept_ambiguous = batch
    try:
        data = json.loads(re.search(r"\{.*\}", raw or "", flags=re.S).group(0))
        keep_idx = {int(x) for x in (data.get("keep") or [])}
        kept_ambiguous = [m for i, m in enumerate(batch, 1) if i in keep_idx]
        dropped = [str(m.get('title',''))[:50] for i, m in enumerate(batch, 1) if i not in keep_idx]
        if dropped:
            print(f"SHOP FILTER AI-DROP ({len(dropped)}): {dropped[:5]}")
    except Exception:
        print(f"SHOP FILTER AI PARSE FAIL — keeping ambiguous as-is: {raw!r}")
    result = auto_keep + kept_ambiguous + ambiguous[20:]
    print(f"SHOP FILTER: {len(matches)} -> {len(result)} shopping results")
    return result


def _store_pending_lens_social(phone, bot_id, lang, matches):
    PENDING_LENS_SOCIAL[phone] = {
        "bot_id": bot_id, "lang": lang,
        "matches": matches[:LENS_RESULT_LIMIT], "ts": time.time(),
    }


def _pop_pending_lens_social(phone):
    item = PENDING_LENS_SOCIAL.pop(phone, None)
    if not item or time.time() - item.get("ts", 0) > GLOBAL_PENDING_TTL:
        return None
    return item



# ===== v81 HIGH COMMISSION TARGETING =====
HIGH_COMMISSION_STORES = {
    "temu.com": {"comm": "10-30%", "priority": 1},
    "shein.com": {"comm": "10-15%", "priority": 2},
    "trendyol.com": {"comm": "8-15%", "priority": 3},
    "namshi.com": {"comm": "10-15%", "priority": 4},
    "ounass.com": {"comm": "8-12%", "priority": 5},
    "6thstreet.com": {"comm": "8-12%", "priority": 6},
    "farfetch.com": {"comm": "10-15%", "priority": 7},
    "amazon.ae": {"comm": "3-7%", "priority": 8},
    "amazon.sa": {"comm": "3-7%", "priority": 9},
    "amazon.com": {"comm": "3-8%", "priority": 10},
    "noon.com": {"comm": "4-9%", "priority": 11},
    "aliexpress.com": {"comm": "5-9%", "priority": 12},
    "sephora.ae": {"comm": "5-10%", "priority": 13},
    "iherb.com": {"comm": "10-15%", "priority": 14},
}

def is_high_commission_store(url_or_host):
    try:
        import urllib.parse
        host = url_or_host if "." in url_or_host and "/" not in url_or_host else urllib.parse.urlparse(str(url_or_host)).netloc.lower()
        if not host:
            host = str(url_or_host).lower()
        for domain in HIGH_COMMISSION_STORES:
            if domain in host:
                return True
        return False
    except:
        return False

def prioritize_high_commission(matches):
    """رتب النتائج: متاجر العمولة العالية أولاً"""
    def score(m):
        try:
            url = (m.get("link") or "").lower()
            for domain, info in HIGH_COMMISSION_STORES.items():
                if domain in url:
                    return info["priority"]
            return 99
        except:
            return 99
    return sorted(matches, key=score)

def filter_and_prioritize_for_affiliate(matches, max_results=8):
    """فلتر للمتاجر المستهدفة فقط + ترتيب حسب العمولة"""
    # أولاً: المتاجر المستهدفة
    targeted = [m for m in matches if is_high_commission_store(m.get("link",""))]
    # ثانياً: الباقي
    others = [m for m in matches if not is_high_commission_store(m.get("link",""))]
    # رتب المستهدفة حسب العمولة
    targeted = prioritize_high_commission(targeted)
    # ادمج: المستهدفة أولاً ثم الباقي
    combined = targeted + others
    return combined[:max_results]


# ---- v81.4: بطاقة المتجر الرسمي للبراند — Lens يعرف الاسم لكن نتائجه البصرية ---
# غالباً مواقع إعادة بيع؛ نستخرج البراند من العنوان ونبني رابط متجره الرسمي بأنفسنا.
BRAND_EXTRACT_SYSTEM = """أنت خبير علامات تجارية. سأعطيك عنوان منتج من نتائج بحث.
أرجع اسم البراند/الماركة فقط كما يُكتب رسمياً (مثل: west elm أو IKEA أو Bottega Veneta أو Nike).
تجاهل أسماء المتاجر البائعة (John Lewis, Etsy, Amazon...) وكلمات المنتج والألوان والمقاسات.
إذا لا يوجد براند واضح في العنوان أرجع كلمة NONE فقط. سطر واحد بدون شرح."""
_BRAND_EXTRACT_CACHE = {}
_BRAND_EXTRACT_LOCK = threading.Lock()

def extract_brand_from_title(title):
    t = " ".join(str(title or "").split())[:150]
    if not t:
        return ""
    key = normalize_ar(t).lower()[:120]
    with _BRAND_EXTRACT_LOCK:
        if key in _BRAND_EXTRACT_CACHE:
            return _BRAND_EXTRACT_CACHE[key]
    raw, _ = call_gemini([{"text": t}], system=BRAND_EXTRACT_SYSTEM, use_search=False)
    brand = (raw or "").strip().splitlines()[0].strip(" .،-—\"'") if raw else ""
    if brand.upper() == "NONE" or len(brand) < 2 or len(brand) > 40:
        brand = ""
    with _BRAND_EXTRACT_LOCK:
        if len(_BRAND_EXTRACT_CACHE) > 2000:
            _BRAND_EXTRACT_CACHE.clear()
        _BRAND_EXTRACT_CACHE[key] = brand
    print(f"BRAND EXTRACT: {t[:60]!r} -> {brand!r}")
    return brand


def official_brand_card(chosen_title):
    """يعيد (البراند، رابط متجره الرسمي الحي) أو ("", "").

    الرابط: نتائج بحث المتجر الرسمي عن المنتج نفسه (يوصلك للمنتج مباشرة)،
    وإلا الصفحة الرئيسية — وكلها مفحوصة حياً قبل الإرسال.
    """
    brand = extract_brand_from_title(chosen_title)
    if not brand:
        return "", ""
    url = ""
    try:
        url = store_search_url(brand, chosen_title) or ""
    except Exception as e:
        print(f"OFFICIAL SEARCH URL ERR: {e.__class__.__name__}")
    if not url:
        try:
            url = resolve_store_homepage(brand) or ""
        except Exception as e:
            print(f"OFFICIAL HOMEPAGE ERR: {e.__class__.__name__}")
    if url:
        print(f"OFFICIAL BRAND CARD: {brand!r} -> {url}")
    return brand, url


def _send_lens_card_batch_v815(from_number, batch, bot_id, lang, exact_query):
    """يرسل دفعة بطاقات: التغليف بالأفلييت وتسجيل النقرة يتمان لحظة الإرسال فقط."""
    sent = 0
    for body, original_url, src_name, is_local in batch:
        url = original_url
        try:
            url = wrap_affiliate_url(original_url, from_number, exact_query)
            log_click(from_number, exact_query, src_name or body[:30], original_url, url, is_global=not is_local)
        except Exception as e:
            print(f"LENS AFF WRAP ERR: {e}")
        send_whatsapp_cta(from_number, body[:1000], url, bot_id, f"🛒 {(src_name or 'Store')[:18]}")
        sent += 1
    return sent


def _offer_lens_more(from_number, bot_id, lang, exact_query, remaining):
    """يخزن البقية ويرسل زر «عرض المزيد (N)» — الدقة ما تنرمي، تتأجل خلف زر."""
    PENDING_LENS_MORE[from_number] = {
        "bot_id": bot_id, "lang": lang, "query": exact_query,
        "cards": remaining, "ts": time.time(),
    }
    n = len(remaining)
    send_whatsapp_buttons(
        from_number,
        T(lang, "more_results_body", n=n),
        [{"id": "lens_more", "title": T(lang, "more_results_btn", n=n)[:20]}],
        bot_id,
    )


def send_lens_direct_results(from_number, lens, bot_id, lang, caption=""):
    """v81.6: نتائج Google Lens **كما هي** — بدون أي إضافة أو اختراع من عندنا.

    الترتيب فقط: متاجر بلد المستخدم (حسب لوكيشنه) أولاً ثم العالمية، وداخل كل
    مجموعة ترتيب Google الأصلي محفوظ حرفياً. المستبعد الوحيد: التواصل الاجتماعي
    وروابط النصب. الزائد عن الدفعة الأولى خلف زر «➕ عرض المزيد (N)».
    """
    matches = [m for m in (lens.get("matches") or []) if (m.get("title") or "").strip()]
    if not matches:
        return False
    chosen_title = ((lens.get("chosen") or {}).get("title") or matches[0]["title"]).strip()
    exact_query = (caption or chosen_title).strip()

    # v81.6: بدون بطاقة «المتجر الرسمي» — التجربة أثبتت أنها تهلوس مع نتائج الصور
    # العامة (استخرجت براند غلط وربطت موقعاً لا علاقة له). نعرض ما يطلعه Lens فقط.
    # بناء كل البطاقات: dedup + حارس النصب + استبعاد التواصل الاجتماعي فقط.
    local_cards, global_cards, seen_urls = [], [], set()
    for m in matches:
        if is_social_result(m):
            continue
        title = m["title"].strip()[:80]
        source = (m.get("source") or "").strip()
        local = is_local_lens_result(m)
        price_txt = ""
        raw_price = str(m.get("price") or "").strip()
        if raw_price or m.get("price_value") not in (None, ""):
            if local:
                price_txt = format_lens_price(raw_price, m.get("price_value"), lang, m.get("currency") or None)
            else:
                shown, _conv = display_global_price(m.get("price_value"), raw_price, m.get("currency") or "", lang)
                price_txt = shown or raw_price
        body = title
        if price_txt:
            body += f" — {price_txt}"
        if source:
            body += f" ({source}{' 🇰🇼' if local else ' 🌍'})"
        url = (m.get("link") or "").strip()
        try:
            host = urllib.parse.urlparse(url).netloc.lower()
        except Exception:
            host = ""
        if not (url.startswith("http") and host and "google." not in host and not is_suspicious_url(url)):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        card = (body, url, source or ("المتجر" if lang == "ar" else "Store"), local)
        # v81.5: تقسيم مستقر — بلد المستخدم أولاً، والترتيب داخل كل مجموعة كما رتبه Google.
        (local_cards if local else global_cards).append(card)

    all_cards = local_cards + global_cards
    if not all_cards:
        return False

    card_cap = max(MAX_STORES, 8)
    first_batch, remaining = all_cards[:card_cap], all_cards[card_cap:]
    _send_lens_card_batch_v815(from_number, first_batch, bot_id, lang, exact_query)
    if remaining:
        _offer_lens_more(from_number, bot_id, lang, exact_query, remaining)

    # النتائج كلها تبقى مخزنة وقوداً للبدائل (المعالج موجود) — بدون قائمة خيارات.
    try:
        identity = build_lens_consensus_identity(lens, matches)
        PENDING_LENS_FOREIGN[from_number] = {
            "bot_id": bot_id, "lang": lang,
            "matches": matches[:LENS_RESULT_LIMIT], "ts": time.time(),
            "query": exact_query,
            "similar_query": (identity.get("query") or exact_query),
            "similar_aliases": identity.get("aliases") or [],
        }
    except Exception as e:
        print(f"LENS PENDING STORE ERR: {e}")

    LAST_SEARCH[from_number] = {"product": exact_query}
    print(f"LENS DIRECT v81.6 RAW: sent={len(first_batch)} (local_first={len(local_cards)}) remaining={len(remaining)} social_removed")
    return True


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

    # v71.2: نفس حركة تطبيق Lens — نرفق اسم بلد المستخدم كنص مع الصورة
    # («الكويت») فيرجّح Google نتائج متاجر نفس البلد.
    country_word = country_hint_word(lang)
    lens_hint = " ".join(x for x in (caption, country_word) if x).strip()

    # v71: وضع اللينز المباشر — الصورة تروح لـ Google Lens ونتائجه تُرسل كما هي.
    # بدون Vision ولا حكم هوية ولا طبقات بحث. إذا Google ما رجع شي، نكمل بالمسار الكامل.
    if LENS_DIRECT_MODE and ((ENABLE_GOOGLE_LENS and SERPAPI_API_KEY and PUBLIC_BASE_URL) or GOOGLE_VISION_API_KEY):
        print(f"LENS DIRECT HINT: {lens_hint!r}")
        lens_direct = google_lens_lookup(b64, mime, lang, lens_hint, light=True)
        if lens_direct.get("matches"):
            if send_lens_direct_results(from_number, lens_direct, bot_id, lang, caption):
                # v74.14: الخريطة صارت الخيار الرابع داخل قائمة «تبي أكثر» — لا رسالة منفصلة.
                return
        print("LENS DIRECT MODE: no Google results -> full pipeline fallback")
        send_whatsapp_text(from_number, T(lang, "lens_none"), bot_id)

    # FUSION ROUTER (قوة الخلط):
    # 1) Lens و Vision يشتغلان بالتوازي — لا ننتظر أحدهما ليبدأ الآخر.
    # 2) Lens متعدد التمريرات (products -> all -> wide) = نفس قوة تطبيق Lens.
    # 3) الهوية النهائية = دمج عنوان Lens الدقيق + الاسم العربي/الإنجليزي من Vision،
    #    فيبحث النص بكل المرادفات ويغطي الفهرسة العربية والإنجليزية معاً.
    lens_future = None
    if LENS_PARALLEL_WITH_VISION and ((ENABLE_GOOGLE_LENS and SERPAPI_API_KEY and PUBLIC_BASE_URL) or GOOGLE_VISION_API_KEY):
        lens_future = LENS_POOL.submit(_run_with_market, market, google_lens_lookup, b64, mime, lang, lens_hint)

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
            lens = google_lens_lookup(b64, mime, lang, " ".join(x for x in ((caption or vision_name), country_word) if x).strip())
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
    if query and (result_type == "service" or (result_type == "product" and AUTO_SEND_PRODUCT_MAPS)):
        send_maps_button(from_number, query, bot_id, lang)

def identify_image_product(msg):
    try:
        b64,mime=download_whatsapp_media(msg["image"]["id"])
        return identify_product_with_retry(b64, mime, "ar")
    except: return ""

_STORE_GENERIC_TOKENS = {
    "هايبر", "هاير", "ماركت", "هايبرماركت", "هايرماركت", "سوبرماركت", "سوبر", "مول", "اسواق", "سوق",
    "مركز", "سنتر", "center", "centre",
    "اونلاين", "اون", "لاين", "الكويت", "كويت", "متجر", "محل", "شركه", "شركة",
    "hyper", "market", "hypermarket", "supermarket", "super", "store", "shop",
    "online", "kuwait", "kw", "mall", "co", "company", "the",
}

def canonical_store_key(name, url=""):
    """v75.3: هوية موحدة للمتجر — «لولو هايبر ماركت» و«لولو هايبرماركت» و«لولو الكويت»

    كلها متجر واحد: الدومين أولاً، ثم قاموس المتاجر، ثم الاسم بعد إزالة الكلمات العامة."""
    host = _host_of(url)
    if host:
        return domain_key(host)
    dom = store_domain(name)
    if dom:
        return domain_key(dom)
    n = normalize_ar(str(name or ""))
    toks = [t for t in re.findall(r"[\w\u0600-\u06FF]+", n) if t not in _STORE_GENERIC_TOKENS]
    core = " ".join(toks).strip()
    if core:
        dom = store_domain(core)
        if dom:
            return domain_key(dom)
    key = normalize_name("".join(toks))
    return key or normalize_name(n)


# ---- v75.5: موحّد أسماء المتاجر الذكي + رابط بحث المتجر عن الصنف --------------
STORE_UNIFY_SYSTEM = """أنت موحّد أسماء متاجر. سأعطيك قائمة مرقمة بأسماء متاجر كما وردت من نتائج بحث.
جمّع الأرقام التي تعود لنفس المتجر الفعلي حتى لو اختلف الإملاء أو اللغة أو الصياغة
(مثل: لولو هاير ماركت = لولو هايبرماركت = Lulu Hypermarket، مركز سلطان = Sultan Center = TSC).
المتاجر المختلفة فعلاً تبقى في مجموعات منفصلة.
أرجع JSON فقط بدون شرح: {"groups":[[1,3],[2],[4,5]]} بحيث يظهر كل رقم مرة واحدة بالضبط."""

_STORE_UNIFY_CACHE = {}
_STORE_UNIFY_LOCK = threading.Lock()

def unify_store_groups(names):
    """يرجع مجموعات فهارس الأسماء المتطابقة فعلياً — حكم ذكي واحد سريع (كاش)."""
    if len(names) < 2:
        return [[i] for i in range(len(names))]
    key = "|".join(sorted(normalize_name(normalize_ar(n)) for n in names))[:400]
    with _STORE_UNIFY_LOCK:
        if key in _STORE_UNIFY_CACHE:
            return _STORE_UNIFY_CACHE[key]
    numbered = "\n".join(f"{i}. {n}" for i, n in enumerate(names, 1))
    raw, _ = call_gemini([{"text": numbered}], system=STORE_UNIFY_SYSTEM, use_search=False)
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


# روابط بحث المتاجر المعروفة — الزر يفتح نتائج الصنف داخل المتجر بدل الرئيسية.
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
_GENERIC_SEARCH_PATTERNS = (
    "https://{d}/catalogsearch/result/?q={q}",
    "https://{d}/search?q={q}",
    "https://{d}/en/search?q={q}",
)
_SEARCH_TMPL_CACHE = {}
_SEARCH_TMPL_LOCK = threading.Lock()

def store_search_url(store_name, query):
    """رابط نتائج بحث المتجر عن الصنف — أفضل بكثير من الرئيسية. يُفحص حياً ويُكاش القالب."""
    dom = store_domain(store_name)
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


CART_ITEM_DEADLINE = max(60, int(os.environ.get("CART_DEADLINE_SECONDS", "240")))
# v75.4: كم صنفاً يدخل البطولة بالتزامن — كل صنف = SEARCH_RUNS بحوث متوازية،
# فنحدد الموجة حتى لا تتزاحم عشرات الاتصالات وتعلّق (سبب تعليق v75.0).
CART_CONCURRENCY = max(1, int(os.environ.get("CART_CONCURRENCY", "2")))

def cart_item_search(product, lang):
    """v75.4: بحث صنف السلة بالمسار الذكي الكامل القديم (بطولة v26) — بطلب من خالد.

    بطولة SEARCH_RUNS بحوث Gemini متوازية لنفس الصنف، الأقوى يفوز واللنكات اتحاد
    الجولات (نفس محرك البحث النصي والبدائل حرفياً). العرض يبقى بتنسيق v75.3.
    عند فشل البطولة: محاولة موسعة باتصال واحد كشبكة أمان. الكاش يخدم التكرار.
    """
    cached = cache_get(product, lang)
    if cached:
        return cached
    txt, urls = v26_best_of_search([{"text": bilingual_search_instruction(product, lang)}])
    urls = direct_urls_only(urls)
    if txt and extract_store_offers(txt) and not is_no_result_answer(txt):
        cache_put(product, lang, txt, urls)
        return txt, urls
    market_name = current_market().get("country_name", "Kuwait")
    txt, urls = call_gemini([{"text": (
        f"ابحث عن {product} في أي متجر محلي في {market_name} يبيعه بسعر رقمي واضح "
        f"ورابط صفحة منتج مباشر. حتى {MAX_STORES} متاجر من الأرخص للأغلى. {LANG_INSTR[lang]}"
    )}])
    urls = direct_urls_only(urls)
    if txt and extract_store_offers(txt) and not is_no_result_answer(txt):
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
            offers = filter_relevant_offers(p, extract_store_offers(txt), urls, use_ai=False)
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

    unit = "أصناف" if lang == "ar" else "items"
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
    unit = "أصناف" if lang == "ar" else "items"
    if is_main:
        header = f"🧺 {store_name} — {len(ordered)} {unit} — {format_price(total)} {currency_label(lang)}"
    else:
        header = (f"🧩 {store_name} — يكمل {len(ordered)} {unit} — {format_price(total)} {currency_label(lang)}"
                  if lang == "ar" else
                  f"🧩 {store_name} — completes {len(ordered)} {unit} — {format_price(total)} {currency_label(lang)}")
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
            joiner = "، " if lang == "ar" else ", "
            tail += "\n" + T(lang, "cart_not_anywhere", items=joiner.join(still_missing))
    else:
        tail = T(lang, "cart_total", t=f"{format_price(plan_total)} {currency_label(lang)}")
    tail += "\n\n" + T(lang, "cart_session_tip")
    send_whatsapp_text(from_number, tail, bot_id)
    return True


def process_cart(products, from_number, bot_id, lang="ar"):
    # v75.2: احتياط قديم (غير مستخدم في المسارات) — على البحث الخفيف هو أيضاً.
    market = market_for_user(from_number)
    results = list(WORKERS.map(lambda p: (p, *_run_with_market(market, cart_item_search, p, lang)), products))
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
    # v75: صور متعددة = سلة موحدة أيضاً — نفس مقارنة المتاجر.
    run_cart_comparison(names, from_number, bot_id, lang)

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
- افهم التعبير الإنشائي: حتى لو كانت الرسالة قصة أو شرحاً طويلاً أو وصف مشكلة، استنتج المنتج أو الخدمة المطلوبة بذكائك. أمثلة:
  "عندي صراصير بالمطبخ ومتضايق منهم وايد" -> {"intent":"search","products":["مبيد صراصير"]}
  "ولدي بيدخل الجامعة ومحتار وش أشتري له يذاكر عليه" -> {"intent":"search","products":["لابتوب للدراسة"]}
  "السياره ما تشتغل الصبح وأحس البطارية خلصت" -> {"intent":"search","products":["خدمة تبديل بطارية سيارة"]}
- المنتج الواحد = عنصر واحد في products حتى لو كانت الرسالة على عدة أسطر. لا تقسم الجملة الواحدة أبداً.
- عدة منتجات مختلفة فعلاً (مفصولة بفواصل أو "و") = عدة عناصر.
- "service": طلب فني/سباك/كهربائي/تصليح... ضع وصف الخدمة والمنطقة في products.
- "greeting": تحية فقط بلا أي طلب. products فارغة.
- "thanks": شكر فقط بلا طلب جديد. products فارغة.
- "chat": فقط إذا لم يكن في الرسالة أي منتج أو خدمة أو حاجة يمكن استنتاجها إطلاقاً. إذا كان في الرسالة أي مشكلة أو حاجة، استنتج المطلوب وأرجع search بدل chat.
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
            # v74.4: نية الخدمة تبقى service — لا تتحول search حتى لا تدخل مقارنة البراندات.
            return {"intent": intent, "products": products[:6]}
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


# ---- v76.4: محرك البحث القديم المرفق من المستخدم — للنص + البدائل فقط ---------
# مهم: هذا المحرك لا يُستدعى من مسار الصور/Lens إطلاقاً. طريقة العرض تبقى عبر
# send_product_result الحالية كما هي؛ الذي تغيّر هنا هو البحث + ربط Grounding فقط.

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
ممنوع روابط ظاهرة في النص. ممنوع Markdown.
"""


def _legacy_extract_store_names(text, limit=None):
    """نسخة متوافقة مع عرض v76: تستخرج اسم المتجر من سطور العرض الحالية."""
    cap = MAX_STORES if limit is None else max(1, int(limit))
    names=[]
    for o in extract_store_offers(text or "", limit=cap):
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
        "systemInstruction": {"parts": [{"text": system + market_instruction()}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 2000},
        "tools": [{"google_search": {}}],
    }
    try:
        with GEMINI_STATS_LOCK:
            GEMINI_STATS["search_calls"] += 1
            print(f"LEGACY V26 CALL model={model} totals={GEMINI_STATS}")
        r = requests.post(gemini_url, params={"key": GEMINI_API_KEY}, json=payload, timeout=90)
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
        finals=resolve_all(uris[:30]) if uris else []
        records=[]
        for i,chunk in enumerate(chunks[:30]):
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
    """HYBRID routing.

    Exact product search (merge_offers=False): use v81-FINAL tournament behavior exactly:
    wait for all SEARCH_RUNS, score them, choose the strongest answer, then union grounded URLs.

    Similar alternatives (merge_offers=True): keep v81.7 behavior via _tournament_collect,
    including its faster collection and union of alternative offers across runs.
    """
    limit=MAX_STORES if max_results is None else max(1,int(max_results))
    market_snapshot=current_market()
    try:
        futs=[V26_SEARCH_POOL.submit(_run_with_market, market_snapshot,
                                     legacy_v26_call_gemini, parts,
                                     LEGACY_TEXT_SEARCH_SYSTEM, limit)
              for _ in range(SEARCH_RUNS)]
        if merge_offers:
            # v81.7 path — used by run_similar_search(..., merge_offers=True).
            results=_tournament_collect(futs, True)
        else:
            # v81-FINAL exact path.
            results=[f.result(timeout=120) for f in futs]
            results=[(tt,uu) for tt,uu in results if tt]
    except Exception as e:
        print(f"LEGACY V26 HYBRID best_of_search err {e}")
        return legacy_v26_call_gemini(parts, max_results=limit)
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
    print({"legacy_v26_hybrid_tournament":[v26_answer_score(tt,uu,limit) for tt,uu in scored],
           "mode":"similar-v81.7" if merge_offers else "exact-v81-FINAL",
           "winner_stores":len(extract_store_offers(best_txt,limit=limit)),
           "total_links":len(merged_urls),"merged_offers":bool(merge_offers)})
    return best_txt,merged_urls


def legacy_text_product_search(product, lang):
    """v78: بحث موحد 8 نتائج - محلي أولاً ثم عالمي - بدون فلتر"""
    cached=cache_get(product,lang)
    if cached: 
        # حتى لو كاش، نزيد العدد لـ 8 إذا كان أقل
        return cached

    is_ar=bool(re.search(r"[\u0600-\u06FF]",str(product or "")))
    alt=(english_search_name(product) if is_ar else arabic_search_name(product)) or ""
    if alt.strip().lower()==str(product).strip().lower(): alt=""
    market_name=current_market().get("country_name","Kuwait")
    
    # --- المرحلة 1: بحث محلي 4 نتائج ---
    local_txt, local_urls = "", {}
    attempts=[(product,alt)] + ([(alt,product)] if alt else [])
    for primary,secondary in attempts:
        extra=(f" وابحث أيضاً بالاسم الآخر لنفس المنتج: {secondary}." if secondary else "")
        prompt=(f"ابحث عن {primary} في {market_name}. قارن أسعار نفس المنتج بالضبط في المتاجر المحلية الحالية."
                f"{extra} أولوية إلزامية إذا كانت النتيجة المطابقة موجودة في أي متجر من هذه القائمة: {MANDATORY_PRIORITY_PROMPT}. "
                "ابدأ بالبحث فيها أولاً، ثم أكمل بباقي المتاجر. لا تُدخل موديل مختلف أو إكسسوار فقط لفرض متجر مفضل. "
                f"أظهر المتاجر التي لديها سعر حالي ومصدر Google حقيقي. {LANG_INSTR[lang]}")
        txt,urls=legacy_v26_best_of_search([{"text":prompt}],max_results=4)
        if txt and urls and extract_store_offers(txt):
            local_txt, local_urls = txt, urls
            break
    
    # --- المرحلة 2: بحث عالمي 4 نتائج ---
    global_txt, global_urls = "", {}
    try:
        en_q = english_search_name(product) or product
        global_prompt = (
            f"ابحث عالمياً عن {en_q} في متاجر خارج {market_name} فقط. "
            f"أولوية البحث والعرض إلزامياً بهذا الترتيب: {MANDATORY_PRIORITY_PROMPT}. "
            "إذا وجدت نفس المنتج المطابق في متجر من القائمة، يجب أن يسبق أي متجر غير موجود فيها. "
            "لا تعرض موديل مختلف أو إكسسوار فقط لإجبار متجر مفضل؛ المطابقة التامة شرط أول. "
            f"اعرض 4 نتائج مختلفة بسعر رقمي واضح ورابط صفحة منتج مباشر. {LANG_INSTR[lang]}"
        )
        txt_g, urls_g = legacy_v26_best_of_search([{"text": global_prompt}], max_results=4)
        if txt_g and urls_g and extract_store_offers(txt_g):
            global_txt, global_urls = txt_g, urls_g
    except Exception as e:
        print(f"GLOBAL PART IN COMBINED SEARCH ERR: {e}")

    # --- دمج: محلي أولاً ثم عالمي = 8 نتائج ---
    if not local_txt and not global_txt:
        return "", {}

    # ادمج النصوص
    combined_lines = []
    combined_urls = {}
    
    if local_txt:
        # خذ أول 4 أسطر عروض من المحلي
        local_offers = [l for l in local_txt.splitlines() if l.strip().startswith(("✅","•","🏆"))]
        combined_lines.extend(local_offers[:4])
        combined_urls.update(local_urls)
    
    if global_txt:
        global_offers = [l for l in global_txt.splitlines() if l.strip().startswith(("✅","•","🏆"))]
        # إذا فيه محلي، أضف فاصل
        if combined_lines and global_offers:
            combined_lines.append("")
            combined_lines.append("🌍 من المتاجر العالمية:")
            combined_lines.append("")
        combined_lines.extend(global_offers[:4])
        combined_urls.update(global_urls)

    # عنوان المنتج
    title = f"📦 {product}"
    final_txt = title + "\n\n" + "\n".join(combined_lines) if combined_lines else ""
    
    if final_txt:
        cache_put(product,lang,final_txt,combined_urls)
    
    return final_txt, combined_urls

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
        f"{LANG_INSTR[lang]}"
    )
    txt, urls = "", {}
    try:
        txt, urls = v26_best_of_search([{"text": prompt}])
        if not txt or is_no_result_answer(txt):
            # محاولة أخيرة باتصال مباشر قبل الاعتذار.
            txt, urls = call_gemini([{"text": prompt}])
    except Exception as e:
        print(f"SERVICE SEARCH CRASH: {e}")
        txt = ""
    if not txt or is_no_result_answer(txt):
        send_whatsapp_text(from_number, T(lang, "not_found"), bot_id)
        return
    send_whatsapp_text(from_number, txt, bot_id)
    send_maps_button(from_number, service_desc, bot_id, lang)



def execute_product_search(from_number, product, bot_id, lang):
    """v79 FINAL: 8 نتائج موحدة محلي أولاً ثم عالمي - بدون زر دور عالميا"""
    send_whatsapp_text(from_number, T(lang, "searching", q=product), bot_id)
    try:
        txt, urls = v26_text_search(product, lang)
    except Exception as e:
        print(f"TEXT SEARCH CRASH: {e}")
        txt, urls = "", {}
    LAST_SEARCH[from_number] = {"product": product}
    if not txt or (not extract_store_offers(txt) and not is_service_answer(txt) and not is_informational_answer(txt)):
        send_whatsapp_text(from_number, T(lang, "not_found"), bot_id)
        return
    # عرض 8 نتائج مباشرة
    result_type = send_product_result(from_number, txt, urls, bot_id, lang, product, max_stores=8)
    if result_type == "product" and AUTO_SEND_PRODUCT_MAPS:
        send_maps_button(from_number, product, bot_id, lang)



# ---- v74.6: مصنّف الطلبات — ذكاء اصطناعي خالص، بدون أي قاموس -----------------
# القاموس الثابت مستحيل يغطي ملايين المنتجات (يخت، موطور مخيمات، مكينة بر...).
# القرار كله لنموذج سريع رخيص (بدون بحث + كاش + إعادة محاولة) بتعريفات وأمثلة قوية.
REQUEST_CLASSIFIER_SYSTEM = """أنت مصنف طلبات خبير لبوت تسوق كويتي على واتساب. المستخدم كتب رسالة قصيرة بالعامية.
صنّفها بدقة وأجب بكلمة واحدة فقط بدون أي شرح: GENERIC أو SPECIFIC أو SERVICE أو NONE

GENERIC = اسم فئة منتج بدون ذكر ماركة محددة، والمستخدم يستفيد من مقارنة أفضل البراندات والأسعار قبل الشراء.
ينطبق على أي فئة بما فيها الملابس والأحذية والشنط والساعات والرياضة والإلكترونيات والأجهزة المنزلية والمكائن والمولدات والعدد والأثاث والمركبات والقوارب ومعدات البر والمخيمات وأدوات المطبخ وأجهزة التجميل...
أمثلة GENERIC: شاشه كمبيوتر، مكينه بر، موطور مخيمات، مولد كهرباء، يخت، جت سكي، دراجه هوائيه، مضخة مسبح، غساله، مكواة بخار، سشوار، خيمه رحلات، ثلاجة سياره، قلاية هوائية، كاميرا مراقبه، سماعة بلوتوث، طباخ غاز، سيارة عائليه، لابتوب للدراسة، حذاء تنس للاطفال، حذاء رياضي للاطفال، تيشرت اطفال، فستان سهرة، شنطة ظهر مدرسية، ساعة ذكية

SPECIFIC = المستخدم حدد ماركة أو موديل أو منتجاً بعينه، أو طلب سلعة استهلاكية يومية يبي سعرها مباشرة (أكل، مشروبات، تموينات، منظفات يومية، أدوية، مستلزمات شخصية استهلاكية).
أمثلة SPECIFIC: ايفون 15 برو، مكينة بر EcoFlow، حذاء تنس نايك للاطفال، حذاء اديداس اطفال، شنطة قوتشي، ساعة ابل، بيبسي، حليب المراعي، حليب، رز بسمتي، بنادول، شامبو هيد اند شولدرز، مناديل، ماء قوارير

SERVICE = طلب خدمة أو فني أو تصليح أو صيانة أو عامل، وليس شراء منتج.
أمثلة SERVICE: كهربائي حمام سباحه، فني تكييف، سباك، بنشر متنقل، تصليح غسالات، شركة تنظيف، ونش، مكافحة حشرات

NONE = الرسالة ليست طلب منتج ولا خدمة إطلاقاً: عتاب أو استعجال أو سب أو مزح أو تجربة أو كلام عام موجه للبوت نفسه.
أمثلة NONE: رد علي، ليش ما ترد، وينك، تأخرت، يا حمار، يا حماااار، هلا فيك، شفيك، تجربة، اختبار، ok، تمام، خلاص، ايه، لا

قواعد الحسم المحدثة (مهم جداً):
- ذكر ماركة (Nike, Adidas, Puma, Zara, Gucci, Apple, Samsung, EcoFlow, Honda, نايك، اديداس، قوتشي...) حتى مع فئة عامة = SPECIFIC فوراً. مثال: مكينة بر هوندا = SPECIFIC، حذاء تنس نايك للاطفال = SPECIFIC، شنطة ظهر نايك = SPECIFIC.
- كلمة فني/تصليح/صيانة/معلم/تركيب مع أي شيء = SERVICE حتى لو ذكر جهازاً.
- أكل وتموينات ومشروبات ومنظفات استهلاكية وأدوية ومستلزمات استهلاكية يومية = SPECIFIC دائماً حتى بدون ماركة، لأن المستخدم يبي السعر مباشرة.
- ملابس وأحذية وشنط وساعات ورياضة وإلكترونيات وأجهزة منزلية وأثاث ومعدات وعدد ومكائن ومركبات بدون ماركة = GENERIC دائماً، لأن المستخدم يستفيد من مقارنة أفضل الماركات. مثال: حذاء تنس للاطفال بدون ماركة = GENERIC، تيشرت اطفال = GENERIC، شنطة ظهر = GENERIC.
- إذا الرسالة كلام موجه للبوت أو تعليق بلا أي سلعة أو خدمة = NONE دائماً. لا تخترع منتجاً من رسالة عتاب أبداً.
- إذا شككت بين GENERIC و SPECIFIC لمنتج غير استهلاكي بدون ماركة، اختر GENERIC دائماً."""

_REQUEST_CLASS_CACHE = {}
_REQUEST_CLASS_LOCK = threading.Lock()

def classify_request_type(query):
    """v77.5: تمييز عام vs محدد - آمن حتى لو انقطع النت - كلمة واحدة مثل جبن = GENERIC"""
    q = " ".join(str(query or "").split()).strip()
    if not q:
        return "SPECIFIC"
    key = re.sub(r"\s+", " ", normalize_ar(q))[:150]
    with _REQUEST_CLASS_LOCK:
        if key in _REQUEST_CLASS_CACHE:
            return _REQUEST_CLASS_CACHE[key]

    q_norm = normalize_ar(q).lower()
    single_word_generics = ("جبن", "حليب", "لبن", "رز", "عيش", "خبز", "ماء", "بيض", "لحم", "دجاج", "شاي", "قهوه", "قهوة", "سكر", "ملح", "زيت", "حذاء", "تيشرت", "بنطلون", "قميص", "فستان", "شنطه", "شنطة", "ساعه", "ساعة")
    if len(q.split()) == 1 and q_norm in single_word_generics:
        verdict = "GENERIC"
        with _REQUEST_CLASS_LOCK:
            if len(_REQUEST_CLASS_CACHE) > 3000:
                _REQUEST_CLASS_CACHE.clear()
            _REQUEST_CLASS_CACHE[key] = verdict
        print(f"REQUEST CLASSIFIER (fast single generic): {q!r} -> {verdict}")
        return verdict

    if is_service_request(q):
        verdict = "SERVICE"
        with _REQUEST_CLASS_LOCK:
            if len(_REQUEST_CLASS_CACHE) > 3000:
                _REQUEST_CLASS_CACHE.clear()
            _REQUEST_CLASS_CACHE[key] = verdict
        print(f"REQUEST CLASSIFIER (fast SERVICE): {q!r} -> {verdict}")
        return verdict

    has_brand = None
    try:
        for attempt in (1, 2):
            raw, _ = call_gemini([{"text": f"النص: {q}"}], system=BRAND_DETECTION_SYSTEM, use_search=False)
            up = (raw or "").strip().upper()
            if "YES" in up:
                has_brand = True
                break
            if "NO" in up:
                has_brand = False
                break
            print(f"BRAND DETECTION RETRY {attempt}: {raw!r}")
    except Exception as e:
        print(f"BRAND DETECTION CRASH: {e}")

    if has_brand is True:
        verdict = "SPECIFIC"
        with _REQUEST_CLASS_LOCK:
            if len(_REQUEST_CLASS_CACHE) > 3000:
                _REQUEST_CLASS_CACHE.clear()
            _REQUEST_CLASS_CACHE[key] = verdict
        print(f"REQUEST CLASSIFIER (brand YES): {q!r} -> {verdict}")
        return verdict
    elif has_brand is False:
        verdict = "GENERIC"
        with _REQUEST_CLASS_LOCK:
            if len(_REQUEST_CLASS_CACHE) > 3000:
                _REQUEST_CLASS_CACHE.clear()
            _REQUEST_CLASS_CACHE[key] = verdict
        print(f"REQUEST CLASSIFIER (brand NO): {q!r} -> {verdict}")
        return verdict

    try:
        verdict = ""
        for attempt in (1, 2):
            raw, _ = call_gemini([{"text": q}], system=REQUEST_CLASSIFIER_SYSTEM, use_search=False)
            up = (raw or "").upper()
            for label in ("SERVICE", "GENERIC", "SPECIFIC", "NONE"):
                if label in up:
                    verdict = label
                    break
            if verdict:
                break
            print(f"REQUEST CLASSIFIER RETRY {attempt}: empty/unclear -> {raw!r}")
    except Exception as e:
        print(f"CLASSIFIER FALLBACK CRASH: {e}")
        verdict = ""

    if not verdict:
        if len(q.split()) <= 2:
            verdict = "GENERIC"
        else:
            verdict = "SPECIFIC"

    with _REQUEST_CLASS_LOCK:
        if len(_REQUEST_CLASS_CACHE) > 3000:
            _REQUEST_CLASS_CACHE.clear()
        _REQUEST_CLASS_CACHE[key] = verdict
    print(f"REQUEST CLASSIFIER (fallback): {q!r} -> {verdict}")
    return verdict

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

BRAND_COMPARE_SYSTEM = """أنت خبير مقارنات منتجات مثل مواقع «أفضل 10» ومواقع المراجعات، وخبير أحذية وملابس أطفال وتغذية أيضاً.
المستخدم طلب منتجاً عاماً بدون ماركة — لأي فئة كانت (إلكترونيات، أحذية، ملابس، رياضة، أثاث، أكل، جبن، حليب، رز، معدات...). ابحث في Google عن مقارنات ومراجعات حديثة لهذه الفئة
واصنع مقارنة قصيرة جداً بين 3-4 خيارات (براند + موديل/نوع) فقط.

الشكل الإلزامي بالضبط — لا تخرج عنه أبداً:
⚖️ مقارنة أفضل [الفئة]

🏆 الأفضل عموماً: [براند + موديل] — [سبب في سطر واحد فقط]

💎 أفضل جودة: [براند + موديل] — [سبب في سطر واحد فقط]

💰 أفضل قيمة مقابل السعر: [براند + موديل] — [سبب في سطر واحد فقط]

✨ [معيار رابع يهم هذه الفئة]: [براند + موديل] — [سبب في سطر واحد فقط]

OPTIONS: [براند موديل 1] | [براند موديل 2] | [براند موديل 3] | [براند موديل 4]

قواعد صارمة جداً - ممنوع مخالفتها:
1- اترك سطر فارغ بين كل توصية والتالية.
2- ممنوع تماماً كتابة أي سطر يبدأ بـ 📦 أو ✅ أو • أو كلمة "متوفر" أو ذكر متجر أو سعر. فقط المقارنة.
3- ممنوع كتابة تفاصيل المتاجر أو الأسعار في هذه الرسالة.
4- للمواد الغذائية (جبن، حليب، رز...): استخدم معايير الطعم، الجودة، القيمة، التقييمات، والتوفر المحلي.
5- لا تكرر نفس الموديل مرتين.
6- سطر OPTIONS إلزامي وبأسماء قابلة للبحث (مثل: Kraft Cheddar, Almarai Cheese, Puck Cheese | أو Nike Court Borough, Adidas Tensaur...).
7- بدون روابط، بدون Markdown.
لغة الرد: حسب تعليمات رسالة المستخدم."""

def _options_from_compare_lines(txt):
    """v74.9: استرجاع ذكي — إذا Gemini نسي سطر OPTIONS نستخرج الخيارات من أسطر

    🏆💎💰✨ نفسها: النص بين النقطتين والشرطة هو (البراند + الموديل)."""
    options = []
    for line in (txt or "").splitlines():
        m = re.match(r"^\s*(?:🏆|💎|💰|✨)\s*[^:：]*[:：]\s*(.+?)\s*(?:—|–|-)\s", line.strip())
        if m:
            cand = " ".join(m.group(1).split()).strip()
            if cand and len(cand) >= 3 and cand not in options:
                options.append(cand)
    return options[:6]


def run_brand_comparison(from_number, query, bot_id, lang):
    """v77.2: مقارنة براندات بدون تكرار + مسافة سطر بين المنتجات"""
    send_whatsapp_text(from_number, T(lang, "compare_searching"), bot_id)
    en = english_search_name(query)
    prompt = (
        f"الطلب العام: {query}" + (f" ({en})" if en and en != query else "") +
        f". قارن أفضل الخيارات المتوفرة الآن في {current_market().get('country_name', 'Kuwait')}. "
        f"{LANG_INSTR[lang]}"
    )
    txt = ""
    options = []
    for attempt in (1, 2):
        txt, _ = call_gemini([{"text": prompt}], system=BRAND_COMPARE_SYSTEM)
        if not txt:
            print(f"BRAND COMPARE ATTEMPT {attempt}: empty")
            continue
        m = re.search(r"(?im)^\s*OPTIONS\s*:\s*(.+)$", txt)
        if m:
            options = [o.strip() for o in m.group(1).split("|") if o.strip()][:6]
            txt = re.sub(r"(?im)^\s*OPTIONS\s*:.*$", "", txt).strip()
        if not options:
            options = _options_from_compare_lines(txt)
            if options:
                print(f"BRAND COMPARE: OPTIONS recovered from lines -> {options}")
        if options:
            break
        print(f"BRAND COMPARE ATTEMPT {attempt}: no options")

    if not txt or not options:
        print("BRAND COMPARE FAILED -> normal search")
        return False

    # v77.2: تنظيف التكرار - احذف أي سطر يبدأ بـ 📦 أو ✅ أو • فيه كلمة متوفر/متجر/سعر - هذه من بقايا بحث قديم
    cleaned_lines = []
    for line in (txt or "").splitlines():
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
        # احذف أسطر التوفر التي تسبب التكرار في الصورة
        if stripped.startswith("📦") or (stripped.startswith("✅") and "متوفر" in stripped) or (stripped.startswith("•") and "متوفر" in stripped):
            print(f"BRAND COMPARE CLEANUP DROP: {stripped[:80]}")
            continue
        if "متوفر عبر متجر" in stripped or "متوفر في" in stripped and "📦" in stripped:
            continue
        cleaned_lines.append(line)

    txt = "\n".join(cleaned_lines).strip()

    # v77.2: اجعل مسافة سطر بين منتج واللي بعده - تأكد من سطر فارغ بعد كل سطر توصية
    # نحول أي سطر يبدأ بـ 🏆💎💰✨ إلى سطر + سطر فارغ بعده
    formatted = []
    for line in txt.splitlines():
        formatted.append(line)
        if re.match(r"^\s*(?:🏆|💎|💰|✨)", line):
            # إذا السطر التالي ليس فارغاً أصلاً، أضف سطر فارغ
            if not (formatted and len(formatted)>=2 and formatted[-2]==""):
                # نضيف سطر فارغ لكن نتجنب التكرار
                if len(formatted)==0 or formatted[-1].strip()!="":
                    formatted.append("")

    # إزالة الأسطر الفارغة المكررة أكثر من واحد
    final_lines = []
    prev_empty = False
    for l in formatted:
        is_empty = not l.strip()
        if is_empty and prev_empty:
            continue
        final_lines.append(l)
        prev_empty = is_empty

    txt = "\n".join(final_lines).strip()

    send_whatsapp_text(from_number, txt, bot_id)
    PENDING_BRAND_PICKS[from_number] = {"options": options, "bot_id": bot_id, "lang": lang, "ts": time.time()}
    # v74.10: عناوين القائمة بالعربي للمستخدم العربي (ترجمة دفعة + كاش)،
    # والاسم الأصلي يبقى في سطر الوصف — وهو المعتمد للبحث عند الاختيار.
    title_map = arabic_titles(options) if lang == "ar" else {}
    rows = []
    for i, o in enumerate(options):
        shown = title_map.get(o, o) if lang == "ar" else o
        desc = o if (shown != o) else (o[24:96] if len(o) > 24 else "")
        rows.append({"id": f"pick_{i}", "title": shown[:24], "description": desc[:72]})
    send_whatsapp_list(from_number, T(lang, "pick_prompt"), rows, bot_id, T(lang, "list_button"))
    print(f"BRAND COMPARE SENT: {options}")
    return True


def process_text_message(message,bot_id,onboarding_checked=False):
    from_number = "unknown"
    try:
        from_number=message["from"]
        load_user_preferences(from_number)
        if not onboarding_checked:
            if from_number not in USER_LANG:
                cache_pending_message(from_number, message, bot_id); send_language_choice(from_number, bot_id); return
            if not location_is_valid(from_number):
                cache_pending_message(from_number, message, bot_id); send_location_request(from_number, bot_id, USER_LANG.get(from_number,"ar"), bool(USER_LOCATION_TS.get(from_number,0))); return
        activate_market(from_number)
        user_text=message["text"]["body"]
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
            send_whatsapp_text(from_number, T(lang, "welcome_reply"), bot_id)
            return
        products = [p for p in (parsed.get("products") or []) if p.strip()] or extract_products(user_text)
        if intent == "service" or is_service_request(products[0] if products else user_text):
            execute_service_search(from_number, products[0] if products else user_text, user_text, bot_id, lang)
            return
        if len(products)==1:
            try:
                rtype = classify_request_type(products[0])
            except Exception as e:
                print(f"CLASSIFY CRASH for {products[0]!r}: {e} -> fallback GENERIC")
                rtype = "GENERIC"
            if rtype == "NONE":
                send_whatsapp_text(from_number, T(lang, "chat_redirect"), bot_id)
                return
            if rtype == "SERVICE":
                execute_service_search(from_number, products[0], user_text, bot_id, lang)
                return
            if rtype == "GENERIC":
                try:
                    if run_brand_comparison(from_number, products[0], bot_id, lang):
                        return
                except Exception as e:
                    print(f"BRAND COMPARE CRASH: {e}")
            try:
                execute_product_search(from_number, products[0], bot_id, lang)
            except Exception as e:
                print(f"PRODUCT SEARCH CRASH: {e}")
                send_whatsapp_text(from_number, T(lang, "not_found"), bot_id)
        else:
            run_cart_comparison(products, from_number, bot_id, lang)
    except Exception as e:
        print(f"PROCESS_TEXT_MESSAGE CRASH: {e} for {from_number}")
        try:
            lang = USER_LANG.get(from_number, "ar") if 'from_number' in locals() else "ar"
            b_id = bot_id if 'bot_id' in locals() else PHONE_NUMBER_ID
            send_whatsapp_text(from_number, T(lang, "not_found"), b_id)
        except:
            pass

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
async def health(): return {"status":"HYBRID v81.9: EXACT = v81-FINAL | SIMILAR = v81.7 | MANDATORY preferred-store ranking after relevance filter | v81.7 Lens/resilience/pagination retained", "lens_direct_mode":LENS_DIRECT_MODE, "build":BUILD_ID, "v26_runs":SEARCH_RUNS, "location_ttl_hours":LOCATION_TTL_SECONDS//3600}
