# -*- coding: utf-8 -*-
import os, re, time, base64, requests, uuid, asyncio, urllib.parse, hashlib, math, json, html as html_lib
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import HTMLResponse

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
LAST_SEARCH = {} # لحفظ اسم آخر منتج بحث عنه المستخدم

# ===== نظام اللغة: كل رقم تلفون وله لغته =====
USER_LANG = {}       # from_number -> "ar" | "en"
PENDING_IMAGES = defaultdict(lambda: {"images": [], "bot_id": ""})  # صور معلقة بانتظار اختيار اللغة

BUFFER_SECONDS = 4
RESOLVER = ThreadPoolExecutor(max_workers=6)
WORKERS = ThreadPoolExecutor(max_workers=3)
SEARCH_POOL = ThreadPoolExecutor(max_workers=8)  # للبحث المزدوج المتوازي
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PriceBot/1.0)", "Accept-Language": "ar-KW,ar;q=0.9,en;q=0.8"}

# ===== كاش النتائج: نفس المنتج = نفس الجواب واللنكات طوال مدة الكاش =====
SEARCH_CACHE = {}          # key -> {"txt":..., "urls":..., "ts":...}
CACHE_TTL = int(os.environ.get("CACHE_TTL_MINUTES", "15")) * 60  # الأسعار والمخزون يتغيران بسرعة
CACHE_MAX = 500            # حد أقصى للذاكرة

# حارس الجودة: لا نحفظ بالكاش إلا نتيجة قوية (3+ متاجر بأسعار ولنك واحد على الأقل)
CACHE_MIN_STORES = 3
CACHE_MIN_LINKS = 1

def result_quality(txt, urls):
    """(عدد المتاجر بأسعار، عدد اللنكات)"""
    return len(extract_store_names(txt or "")), len(urls or {})

def fallback_search_url(query, store=""):
    """زر مضمون دايماً إذا ما توفر لنك مباشر:
    - متجر معروف بالقاموس؟ بحث داخل موقع المتجر نفسه فقط (site:) — نتائج من صفحاته بس.
    - غير ذلك: بحث جوجل عام عن المنتج بالمتجر."""
    dom = store_domain(store) if store else ""
    if dom:
        return "https://www.google.com/search?q=" + urllib.parse.quote(f"site:{dom} {query}")
    q = f"{query} {store} الكويت اونلاين".strip() if store else f"{query} الكويت اونلاين"
    return "https://www.google.com/search?q=" + urllib.parse.quote(q)

def best_store_name(txt):
    """اسم أفضل متجر من سطر 🏪 إن وجد"""
    m = re.search(r"^\s*🏪\s*[^:：]*[:：]\s*(.+?)\s*$", txt or "", flags=re.M)
    return m.group(1).strip() if m else ""

def normalize_ar(text):
    """توحيد الحروف العربية والمسافات حتى تتطابق الصيغ المختلفة لنفس المنتج"""
    t = (text or "").lower()
    t = re.sub(r"[أإآ]", "ا", t)
    t = t.replace("ة", "ه").replace("ى", "ي").replace("ئ", "ي").replace("ؤ", "و")
    t = t.replace("ري بان", "ريبان").replace("راي بان", "ريبان").replace("ray ban", "rayban").replace("ray-ban", "rayban")
    return t

def norm_tokens(query):
    """كلمات الطلب بعد التوحيد — لقياس التشابه بين طلبين"""
    t = normalize_ar(query)
    toks = re.findall(r"[\w\u0600-\u06FF]+", t)
    # نشيل ال التعريف من بداية الكلمات الطويلة
    toks = [w[2:] if w.startswith("ال") and len(w) > 4 else w for w in toks]
    return set(toks)

def has_model_token(a, b):
    """هل يشترك الطلبان بكلمة موديل (حروف+أرقام مثل rb3721)؟ دليل قوي إنهما نفس المنتج"""
    def models(s): return {t for t in s if re.search(r"\d", t) and re.search(r"[a-z\u0600-\u06FF]", t) and len(t) >= 4}
    return bool(models(a) & models(b))

def cache_key(query, lang):
    norm = re.sub(r"[^\w\u0600-\u06FF]+", "", normalize_ar(query))
    return hashlib.sha256(f"{norm}|{lang}".encode()).hexdigest()

def cache_get(query, lang):
    now = time.time()
    # 1) مطابقة حرفية (بعد التوحيد)
    hit = SEARCH_CACHE.get(cache_key(query, lang))
    if hit and (now - hit["ts"]) < CACHE_TTL:
        print(f"CACHE HIT (exact): {query[:60]}")
        return hit["txt"], dict(hit["urls"])
    # 2) مطابقة ضبابية: تشابه الكلمات + وزن ذهبي لرقم الموديل
    qt = norm_tokens(query)
    if not qt:
        return None
    best, best_score = None, 0.0
    for entry in SEARCH_CACHE.values():
        if entry.get("lang") != lang or (now - entry["ts"]) >= CACHE_TTL:
            continue
        et = entry.get("tokens") or set()
        if not et:
            continue
        inter = len(qt & et)
        score = inter / len(qt | et)
        if has_model_token(qt, et):
            score += 0.30
        if score > best_score:
            best, best_score = entry, score
    if best and best_score >= 0.60:
        print(f"CACHE HIT (fuzzy {best_score:.2f}): {query[:50]} ~ {best.get('query','')[:50]}")
        return best["txt"], dict(best["urls"])
    return None

def cache_put(query, lang, txt, urls):
    if not txt:
        return
    if len(SEARCH_CACHE) >= CACHE_MAX:
        oldest = min(SEARCH_CACHE, key=lambda k: SEARCH_CACHE[k]["ts"])
        SEARCH_CACHE.pop(oldest, None)
    SEARCH_CACHE[cache_key(query, lang)] = {
        "txt": txt, "urls": dict(urls), "ts": time.time(),
        "tokens": norm_tokens(query), "query": query, "lang": lang,
    }

# برومبت تحديد الاسم القياسي للمنتج من الصورة (بدون بحث — سريع ورخيص)
IDENTIFY_SYSTEM = """أنت خبير تعرف على المنتجات. انظر للصورة واكتب الاسم التجاري القياسي للمنتج بصيغة ثابتة دائماً:
[البراند] [نوع المنتج] [رقم الموديل باللاتيني إن ظهر] [اللون/النكهة] [الحجم/الوزن إن ظهر]

رقم الموديل هو أهم عنصر — دور عليه على العبوة أو الذراع أو الملصق (مثل RB3721، SM-S928، MQ2V3).
أمثلة على الصيغة:
- ريبان نظارة شمسية RB3721 اسود 59 مم
- برينجلز كاتشب 200 جرام
سطر واحد فقط. بدون أقواس أو شرح أو مقدمات أو رموز."""

# ===== نصوص البوت بالعربي والإنجليزي =====
MSG = {
    "ar": {
        "identifying": "ثواني بس.. أحدد المنتج وأدور لك الأفضل!",
        "searching": "🔍 أدور لك على {q}...",
        "not_found": "ما لقيت",
        "cant_identify": "ما قدرت أحدد المنتج",
        "shop_from": "تسوق من {n} 👇",
        "approx_note": "~ = سعر تقريبي من البحث (غير مؤكد)",
        "no_verified_offer": "ما لقيت حالياً رابط شراء مباشر بسعر ومخزون مؤكدين. ما راح أعرض لك نتيجة غير موثوقة.",
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
        "not_found": "Couldn't find it",
        "cant_identify": "Couldn't identify the product",
        "shop_from": "Shop from {n} 👇",
        "approx_note": "~ = approximate price from search (unverified)",
        "no_verified_offer": "I couldn't find a direct purchase page with a verified live price and stock. I won't show an unreliable result.",
        "multi_text": "Got it, found {c} products. Building your cart...",
        "multi_images": "Nice, spotted {c} products. Building your cart...",
        "maps_body": "📍 Want the nearest place?\n\nTap the button and the map will open on the closest spots around you 👇",
        "maps_btn": "📍 Open Map",
        "maps_body_loc": "📍 Your last search was ({p})\n\nI've lined up the closest places around you. Tap the button to open the map 👇",
        "no_saved_product": "I don't have a saved product yet 😅. Search for a product first, then I'll point you to the nearest store!",
        "lang_saved": "Great, I'll speak English with you from now on 🇬🇧\nSend a product photo or type its name and I'm on it!",
    },
}

# تعليمة اللغة اللي تنضاف على كل طلب لـ Gemini
LANG_INSTR = {
    "ar": "رد باللغة العربية فقط.",
    "en": "Respond ONLY in English. Keep the exact same response format and emojis, but translate all labels to English — including writing (Phone: NUMBER) instead of (هاتف: رقم). Keep prices in KWD.",
}

def T(lang, key, **kw):
    return MSG.get(lang, MSG["ar"])[key].format(**kw) if kw else MSG.get(lang, MSG["ar"])[key]

def detect_lang(text):
    """عربي إذا فيه حروف عربية، إنجليزي إذا فيه حروف لاتينية، وإلا None"""
    if re.search(r"[\u0600-\u06FF]", text or ""):
        return "ar"
    if re.search(r"[A-Za-z]", text or ""):
        return "en"
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

🛒 مصدر العروض ClicFlyer — قاعدة إلزامية لمنتجات التموينات:
لأي منتج بقالة أو تموينات (أغذية، مشروبات، منظفات، عناية شخصية، أدوات منزلية استهلاكية)، نفّذ دائماً بحثاً إضافياً في clicflyer.com (استخدم site:clicflyer.com مع اسم المنتج) — فهو يجمع أحدث عروض الهايبرماركتات والجمعيات التعاونية في الكويت.
- إذا وجدت عرضاً سارياً أرخص من الأسعار العادية، حطه في أول المقارنة واكتب اسم المتجر صاحب العرض مع كلمة (عرض)، مثال: ✅ كارفور (عرض) — 0.750 د.ك
- عروض ClicFlyer السارية لها أولوية لأنها الأحدث، ولا تذكر أبداً عرضاً منتهي الصلاحية.

【الحالة 2】طلب عام بدون براند محدد (مثل: قهوة فلات وايت حار، عطر رجالي، لابتوب للدراسة، سماعات للجيم، برجر):
لا تبحث عن الأرخص! ابحث عن الأفضل تقييماً في الكويت بسعر مناسب (أفضل قيمة مقابل السعر).
اعتمد على تقييمات Google والمراجعات الفعلية، ورد بهذا الشكل فقط:
📦 [وصف الطلب]

🏆 [اسم الخيار الأفضل + مكانه/متجره] — [السعر] د.ك ⭐ [التقييم من 5]
• [خيار ثاني قوي] — [السعر] د.ك ⭐ [التقييم من 5]
• [خيار ثالث] — [السعر] د.ك ⭐ [التقييم من 5]
لا تضف أي سطر شرح بعد القائمة.

【الحالة 3】طلب خدمة (فني، بنشر، تبديل بطارية، سباك، كهربائي، تنظيف، صالون، توصيل، ونش...):
ابحث عن أفضل مزودي الخدمة تقييماً في المنطقة المطلوبة، ورد بهذا الشكل فقط:
📦 [وصف الخدمة + المنطقة]

🏆 [اسم المزود] (هاتف: [الرقم]) — [المنطقة] — [السعر التقريبي] د.ك ⭐ [التقييم من 5]
• [مزود ثاني] (هاتف: [الرقم]) — [المنطقة] — [السعر] د.ك ⭐ [التقييم]
• [مزود ثالث] (هاتف: [الرقم]) — [المنطقة] — [السعر] د.ك ⭐ [التقييم]
ثم سطر واحد قصير عن ميزة الخيار الأول (سرعة، خدمة 24 ساعة، كفالة...).
⛔ قاعدة صارمة جداً للأرقام: لا تكتب أي رقم هاتف إلا إذا ظهر الرقم حرفياً في نتائج بحث Google. ممنوع منعاً باتاً تأليف أو تخمين أي رقم. إذا ما لقيت رقم المزود في نتائج البحث اكتب مكانه (الرقم بالرابط) فقط. رقم غلط أسوأ ألف مرة من عدم وجود رقم.

【الحالة 4】سؤال معلوماتي عن منتج (المكونات، السعرات، المواصفات، طريقة الاستخدام، الفرق بين موديلين، هل يناسب كذا، بلد المنشأ، الكفالة...):
أجب على السؤال نفسه مباشرة — لا تعرض مقارنة أسعار إطلاقاً.
رد بهذا الشكل:
📦 [اسم المنتج]

ثم الإجابة المباشرة على السؤال في سطور قصيرة واضحة (يمكن استخدام • للتعداد). اعتمد على نتائج البحث والمصادر الرسمية، وإذا كانت معلومة غير متوفرة قل ذلك بصراحة ولا تخترعها.

في الحالات 1 و2 و3، سطر أخير إلزامي:
LINKS: اسم الأول=رابط صفحة المنتج الكامل أو الدومين, اسم الثاني=رابط صفحة المنتج الكامل أو الدومين
مثال: LINKS: إكسايت=https://www.xcite.com/product/... , بلينك=blink.com.kw
في الحالة 4: سطر LINKS اختياري — أضفه فقط إذا كان هناك رابط مصدر مفيد (مثل صفحة المنتج الرسمية).
قواعد جودة إلزامية لنتائج المنتجات:
- لا تذكر متجراً إلا إذا وجدت صفحة المنتج نفسه، وليس صفحة بحث أو تصنيف أو مجموعة منتجات.
- لا تذكر نتيجة مكتوب عليها Out of Stock / Sold Out / غير متوفر.
- لا تعتمد على سعر مقتطف Google وحده إذا كان يخالف السعر الظاهر في صفحة المنتج.
- رقم الموديل والحجم/الوزن/السعة يجب أن يطابقوا طلب المستخدم حرفياً متى كانوا موجودين.

في LINKS اكتب رابط صفحة المنتج الكامل متى توفر، مثال داخلي سيُحذف قبل الإرسال:
LINKS: إكسايت=https://www.xcite.com/product/... , بلينك=https://www.blink.com.kw/product/...
إذا لم يتوفر الرابط الكامل، اكتب الدومين فقط.
لا تخمّن رابطاً أو دوميناً، ولا تذكر متجراً أو خياراً من دون مصدر بحث.
ممنوع روابط ظاهرة للمستخدم. ممنوع Markdown.

لغة الرد: التزم بلغة الرد المطلوبة في رسالة المستخدم (عربي أو إنجليزي) مع الحفاظ على نفس التنسيق تماماً.

إذا كان المنتج عقاراً أو سيارة، أعطِ تقييماً متوسطاً ونطاق سعر مختصراً جداً.
"""

MAPS_CATEGORY_SYSTEM = """أنت خبير تسوق في السوق الكويتي. 
بناءً على اسم المنتج أو الخدمة، أعطني "عبارة بحث" (Search Term) دقيقة جداً لخرائط جوجل تجلب الأماكن الصحيحة وتستبعد العشوائية.

قواعد هامة:
- للإلكترونيات الذكية (ساعة أبل، جوالات، لابتوب): اكتب أسماء الوكلاء الموثوقين هكذا (Xcite OR Eureka OR Best Al Yousifi) ولا تكتب "محل الكترونيات" أبداً.
- للأجهزة المنزلية (ثلاجة، غسالة): (Xcite OR Eureka).
- للأدوية والمكملات: (صيدلية Pharmacy).
- للمواد الغذائية واللحوم: (جمعية تعاونية Supermarket).
- لألعاب الفيديو: (محل العاب فيديو Video games).
- للكهربائيات الثقيلة والإضاءة: (مواد كهربائية Electrical supply).
- للملابس والمعدات الرياضية (مثل مضارب التنس والبادل): (Intersport OR Go Sport OR محلات رياضية).
- للخدمات (بنشر، تبديل بطارية، سباك، كهربائي، تنظيف، ونش): اكتب نوع الخدمة بالعربي والإنجليزي مثل (بنشر Tyre repair) أو (ونش Towing service).
- للطلبات العامة (قهوة، مطاعم، عطور): اكتب نوع المكان مع كلمة "الأعلى تقييماً" مثل (كافيه specialty coffee) أو (محل عطور perfume shop).
- إذا لم تكن متأكداً، اكتب اسم المنتج نفسه.

أعطني عبارة البحث فقط بدون أي إضافات أو شرح."""

def get_final_url(url: str):
    """Resolve redirects, but keep Gemini's original grounding URL as fallback."""
    if not url or not url.startswith(("http://", "https://")):
        return ""
    try:
        r = requests.get(url, allow_redirects=True, timeout=12, stream=True, headers=HEADERS)
        final = r.url or url
        r.close()
        return final if final.startswith(("http://", "https://")) else url
    except Exception as e:
        print(f"URL resolve err: {e} | {url[:180]}")
        return url

def resolve_all(uris):
    return list(RESOLVER.map(get_final_url, uris))

def clean_domain(dom):
    dom = re.sub(r"^https?://", "", (dom or "").strip().lower())
    return dom.replace("www.", "").split("/")[0]

def domain_key(dom):
    return clean_domain(dom).split(".")[0]

def normalize_name(value):
    return re.sub(r"[^\w\u0600-\u06FF]+", "", (value or "").lower())

# ===== قاموس المتاجر الكويتية: الاسم العربي ↔ الدومين الإنجليزي =====
# يحل مشكلة عدم تطابق الأسماء (اليوسفي ↔ best.com.kw) — قابل للتوسعة بأي وقت
STORE_DOMAINS = {
    "اليوسفي": "best.com.kw",
    "بستاليوسفي": "best.com.kw",
    "بست": "best.com.kw",
    "اكسايت": "xcite.com",
    "اكسايتالغانم": "xcite.com",
    "الغانم": "xcite.com",
    "xcite": "xcite.com",
    "نون": "noon.com",
    "noon": "noon.com",
    "بلينك": "blink.com.kw",
    "blink": "blink.com.kw",
    "يوريكا": "eureka.com.kw",
    "eureka": "eureka.com.kw",
    "جرير": "jarir.com",
    "مكتبهجرير": "jarir.com",
    "كارفور": "carrefourkuwait.com",
    "carrefour": "carrefourkuwait.com",
    "لولو": "luluhypermarket.com",
    "لولوهايبرماركت": "luluhypermarket.com",
    "امازون": "amazon.ae",
    "amazon": "amazon.ae",
    "نمشي": "namshi.com",
    "شيان": "shein.com",
    "هومسنتر": "homecentre.com",
    "سيفكو": "saveco.com",
    "سلطانسنتر": "sultan-center.com",
    "التميمي": "danubeonline.com",
    "بوتيكات": "boutiqaat.com",
    "الدوليللاتصالات": "alkoutint.com",
    "wibi": "wibi.com.kw",
    "ويبي": "wibi.com.kw",
    "اتكير": "itcare-kw.com",
    # تطبيقات التوصيل والبقالة
    "طلبات": "talabat.com",
    "طلباتمارت": "talabat.com",
    "talabat": "talabat.com",
    "توصيل": "taw9eel.com",
    "التوصيل": "taw9eel.com",
    "taw9eel": "taw9eel.com",
    "تريكارت": "trikart.com",
    "trikart": "trikart.com",
    "يوباي": "ubuy.com.kw",
    "ubuy": "ubuy.com.kw",
    "ديزرتكارت": "desertcart.com.kw",
    "desertcart": "desertcart.com.kw",
    "ديليفرو": "deliveroo.com.kw",
    "deliveroo": "deliveroo.com.kw",
    "كريم": "careemnow.com",
    "انستاشوب": "instashop.com",
    "سنابس": "snaps.company",
    "جاهز": "jahez.net",
    # شركات أغذية كويتية
    "مطاحن": "kuwaitflourmills.com",
    "المطاحن": "kuwaitflourmills.com",
    "الميره": "almeera.com.kw",
    "مزاد": "mezzan.com",
    "الوطنيهللاغذيه": "knfc.com.kw",
}

def store_domain(name):
    """يرجع دومين المتجر إذا كان معروفاً بالقاموس (مطابقة بعد توحيد الحروف)"""
    n = normalize_name(normalize_ar(name))
    if not n:
        return ""
    for k, d in STORE_DOMAINS.items():
        if k in n or n in k:
            return d
    return ""

# أسماء "متاجر" خربانة يطلعها Gemini أحياناً — مو متاجر حقيقية فما نسوي لها زر
JUNK_STORE = re.compile(r"^(delivery|اونلاين|أونلاين|online|الموقعالرسمي|official)", re.I)

def is_junk_store(name):
    return bool(JUNK_STORE.match(normalize_name(normalize_ar(name))))

def short_query(q):
    """يختصر جملة البحث للضمانة: بدون أقواس، اللي قبل الشرطة فقط، وأول 6 كلمات.
    الجمل الطويلة (اسم كامل + تغليف + شركة) تخرب بحث جوجل."""
    q = re.sub(r"\([^)]*\)", " ", q or "")
    q = re.split(r"\s+[-—–]\s+", q)[0]
    return " ".join(q.split()[:6]).strip()

def extract_store_names(text):
    stores = []
    for line in (text or "").splitlines():
        # سطر أفضل متجر بالسلة: 🏪 أفضل متجر واحد: X
        m = re.match(r"^\s*🏪\s*[^:：]*[:：]\s*(.+?)\s*$", line)
        if m:
            name = m.group(1).strip()
            if name and name not in stores:
                stores.insert(0, name)  # الأولوية له بالربط
            continue
        m = re.match(r"^\s*(?:✅|🏆|•)\s*(.+?)\s*(?:—|–|-)\s*[\d.,]+", line)
        if m:
            name = m.group(1).strip()
            if name and name not in stores:
                stores.append(name)
    return stores[:5]

def is_service_answer(txt):
    """هل الرد عن خدمة؟ (سطور فيها هاتف: أو Phone:)"""
    return bool(re.search(r"(?:🏆|•)\s*.+?\(\s*(?:هاتف|Phone|phone|Tel|tel)\s*:", txt or ""))

def extract_store_offers(txt):
    """يستخرج سطور المقارنة كاملة: [{'line','name','best'}]
    السطر نفسه (اسم المتجر + السعر) يصير نص رسالة الـCTA — بدون تكرار قائمة."""
    offers = []
    for line in (txt or "").splitlines():
        s = line.strip()
        m = re.match(r"^(✅|🏆|•)\s*(.+?)\s*(?:—|–|-)\s*[\d.,]+", s)
        if not m:
            continue
        if re.search(r"\(\s*(?:هاتف|Phone|phone|Tel|tel)\s*:", s):
            continue  # سطر خدمة مو متجر
        name = m.group(2).strip()
        best = m.group(1) in ("✅", "🏆")
        # نشيل النقطة • من العاديين، ونخلي ✅/🏆 للأفضل
        body = s if best else s.lstrip("•").strip()
        offers.append({"line": body, "name": name, "best": best})
    return offers[:4]

def product_title(txt, fallback=""):
    """سطر اسم المنتج 📦 من الرد — أو من الطلب نفسه كاحتياط"""
    m = re.search(r"^\s*📦\s*(.+)$", txt or "", flags=re.M)
    if m:
        return f"📦 {m.group(1).strip()}"
    return f"📦 {fallback}" if fallback else ""

# ===== التحقق الحي الصارم من صفحات المنتجات: الهوية + السعر + المخزون + الرابط المباشر =====
# لا يخرج زر CTA إلا إذا تحققت الشروط الأربعة معاً:
# 1) صفحة منتج مباشرة، 2) المنتج مطابق، 3) السعر الحالي مقروء، 4) المنتج متوفر.

JINA_KEY = os.environ.get("JINA_API_KEY", "")
SEMANTIC_VERIFY = os.environ.get("SEMANTIC_VERIFY", "1") == "1"
MATCH_CACHE = {}
MATCH_CACHE_TTL = 24 * 3600

OOS_SIGNS = [
    "out of stock", "sold out", "currently unavailable", "outofstock",
    "غير متوفر", "غير متوفرة", "نفدت الكمية", "نفذت الكمية", "انتهى المخزون",
    "اشعاري عند التوفر", "إشعاري عند التوفر", "أعلمني عند التوفر", "notify me when available",
]
IN_STOCK_SIGNS = [
    "schema.org/instock", '"instock"', 'availability":"instock', "availability':'instock",
    "add to cart", "add-to-cart", "buy now", "أضف إلى السلة", "اضف الى السلة", "اشتر الآن", "شراء الآن",
]
BAD_PRODUCT_PATH = re.compile(
    r"/(?:search|category|categories|collection|collections|catalogsearch|brands?|brand|offers?|deals?|flyers?|listing|browse)(?:/|\?|$)|[?&](?:q|query|search|keyword)=",
    re.I,
)
PRODUCT_PATH_HINT = re.compile(r"/(?:product|products|p|item|sku)/|\.html?(?:\?|$)", re.I)

GENERIC_PRODUCT_WORDS = {
    "منتج", "المنتج", "عرض", "سعر", "اسعار", "شراء", "اونلاين", "online", "product", "buy",
    "الكويت", "kuwait", "جديد", "new", "اصلي", "original", "لون", "حجم", "size", "color",
}

def safe_float(value):
    try:
        if value is None or isinstance(value, bool):
            return None
        x = float(str(value).replace(",", "").strip())
        return x if 0.05 <= x <= 50000 else None
    except Exception:
        return None


def clean_visible_text(value):
    value = html_lib.unescape(value or "")
    value = re.sub(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def url_is_direct_candidate(url):
    if not url or not url.startswith(("http://", "https://")):
        return False
    u = url.lower()
    if BAD_PRODUCT_PATH.search(u):
        return False
    if any(x in u for x in ("/cart", "/checkout", "/login", "/account", "javascript:")):
        return False
    return True


def fetch_page_text(url):
    """يرجع النص، نوع المصدر، والرابط النهائي بعد التحويلات."""
    final_url = url
    direct_html = ""
    try:
        r = requests.get(url, timeout=10, headers=HEADERS, allow_redirects=True)
        final_url = r.url or url
        if r.ok and len(r.text) > 500:
            direct_html = r.text[:800000]
            low = direct_html.lower()
            # HTML الحقيقي الذي يحتوي بيانات المنتج أفضل وأسرع من المصيّر.
            if re.search(r'application/ld\+json|itemprop=["\']price|product:price|og:type["\']?\s+content=["\']product', low):
                return direct_html, "direct", final_url
    except Exception as e:
        print(f"fetch direct err {e} | {url[:100]}")
    try:
        h = {"User-Agent": HEADERS["User-Agent"], "Accept-Language": HEADERS.get("Accept-Language", "")}
        if JINA_KEY:
            h["Authorization"] = f"Bearer {JINA_KEY}"
        rr = requests.get("https://r.jina.ai/" + final_url, timeout=18, headers=h)
        if rr.ok and len(rr.text) > 300:
            return rr.text[:400000], "jina", final_url
    except Exception as e:
        print(f"fetch jina err {e} | {url[:100]}")
    if direct_html:
        return direct_html, "direct", final_url
    return "", "", final_url


def canonical_url(base_url, html):
    patterns = [
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)',
        r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']',
        r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)',
    ]
    for pat in patterns:
        m = re.search(pat, html or "", re.I)
        if m:
            u = urllib.parse.urljoin(base_url, html_lib.unescape(m.group(1).strip()))
            if url_is_direct_candidate(u):
                return u
    return base_url


def walk_json(value):
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from walk_json(v)
    elif isinstance(value, list):
        for v in value:
            yield from walk_json(v)


def jsonld_products(html):
    products = []
    for raw in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html or "", re.I | re.S):
        raw = html_lib.unescape(raw).strip().strip("\ufeff")
        try:
            data = json.loads(raw)
        except Exception:
            # بعض المواقع تضع فاصلة زائدة أو تعليقاً بسيطاً.
            cleaned = re.sub(r"/\*.*?\*/|^\s*//.*?$", "", raw, flags=re.S | re.M)
            cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
            try:
                data = json.loads(cleaned)
            except Exception:
                continue
        for obj in walk_json(data):
            typ = obj.get("@type")
            types = typ if isinstance(typ, list) else [typ]
            if any(str(t).lower() == "product" for t in types if t):
                products.append(obj)
    return products


def meta_content(html, key):
    esc = re.escape(key)
    pats = [
        rf'<meta[^>]+(?:property|name|itemprop)=["\']{esc}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name|itemprop)=["\']{esc}["\']',
    ]
    for pat in pats:
        m = re.search(pat, html or "", re.I)
        if m:
            return clean_visible_text(m.group(1))
    return ""


def page_identity(html, url, products=None):
    products = products if products is not None else jsonld_products(html)
    vals = []
    for p in products[:5]:
        for k in ("name", "sku", "mpn", "gtin", "gtin8", "gtin12", "gtin13", "gtin14", "model"):
            v = p.get(k)
            if v and not isinstance(v, (dict, list)):
                vals.append(str(v))
    for key in ("og:title", "twitter:title"):
        v = meta_content(html, key)
        if v:
            vals.append(v)
    for pat in (r"<h1\b[^>]*>(.*?)</h1>", r"<title\b[^>]*>(.*?)</title>"):
        m = re.search(pat, html or "", re.I | re.S)
        if m:
            vals.append(clean_visible_text(m.group(1)))
    # Jina يعيد Markdown: Title: ... أو أول عنوان # ...
    m = re.search(r"(?im)^Title:\s*(.+)$", html or "") or re.search(r"(?m)^#\s+(.+)$", html or "")
    if m:
        vals.append(clean_visible_text(m.group(1)))
    try:
        vals.append(urllib.parse.unquote(urllib.parse.urlparse(url).path).replace("-", " ").replace("_", " "))
    except Exception:
        pass
    # منع تضخم النص من تكرار نفس العنوان.
    seen, out = set(), []
    for v in vals:
        k = normalize_name(normalize_ar(v))
        if v and k and k not in seen:
            seen.add(k); out.append(v)
    return " | ".join(out[:10])


def model_tokens(text):
    """موديلات حقيقية مثل RB3721 وSM-S928؛ لا نعامل 330ml أو 256GB كموديل."""
    out = set()
    toks = re.findall(r"[A-Za-z\u0600-\u06FF0-9-]+", text or "")
    unit_suffix = re.compile(r"^\d+(?:\.\d+)?(?:kg|g|gr|gram|ml|l|mm|cm|tb|gb|جم|جرام|مل|لتر|مم|سم)$", re.I)
    for tok in toks:
        norm = re.sub(r"[^a-z0-9\u0600-\u06FF]", "", normalize_ar(tok))
        if len(norm) < 4 or unit_suffix.match(norm):
            continue
        if re.search(r"\d", norm) and re.search(r"[a-z\u0600-\u06FF]", norm):
            out.add(norm)
    return out


def quantity_tokens(text):
    """يوحّد 0.5 kg و500 g، و1 L و1000 ml، والسعات GB/TB."""
    out = set()
    t = normalize_ar(text or "")
    unit_map = {
        "kg": ("weight", 1000), "كيلو": ("weight", 1000), "كيلوجرام": ("weight", 1000),
        "g": ("weight", 1), "gr": ("weight", 1), "gram": ("weight", 1), "grams": ("weight", 1), "جم": ("weight", 1), "جرام": ("weight", 1),
        "l": ("volume", 1000), "liter": ("volume", 1000), "litre": ("volume", 1000), "لتر": ("volume", 1000),
        "ml": ("volume", 1), "مل": ("volume", 1), "مليلتر": ("volume", 1),
        "tb": ("storage", 1024), "تيرا": ("storage", 1024),
        "gb": ("storage", 1), "جيجا": ("storage", 1),
        "mm": ("length_mm", 1), "مم": ("length_mm", 1),
        "cm": ("length_mm", 10), "سم": ("length_mm", 10),
    }
    pat = r"(?<!\d)(\d+(?:\.\d+)?)\s*(kg|كيلوجرام|كيلو|grams?|gram|gr|g|جرام|جم|liters?|litres?|liter|litre|l|لتر|ml|مل|مليلتر|tb|تيرا|gb|جيجا|mm|مم|cm|سم)\b"
    for n, u in re.findall(pat, t, re.I):
        key = u.lower()
        dim, mul = unit_map.get(key, ("", 1))
        if dim:
            out.add((dim, round(float(n) * mul, 3)))
    return out


def lexical_match_score(expected, identity):
    e = norm_tokens(expected) - GENERIC_PRODUCT_WORDS
    i = norm_tokens(identity) - GENERIC_PRODUCT_WORDS
    if not e or not i:
        return 0.0
    em, im = model_tokens(expected), model_tokens(identity)
    if em:
        if em & im:
            return 1.0
        # وجود موديل مختلف في الصفحة دليل رفض قوي.
        if im:
            return -1.0
    eq, iq = quantity_tokens(expected), quantity_tokens(identity)
    if eq:
        dims = {d for d, _ in eq}
        conflicting = any(any(d == d2 for d2, _ in iq) and not any(d == d2 and abs(v-v2) < 0.01 for d2, v2 in iq) for d, v in eq)
        if conflicting:
            return -1.0
    overlap = e & i
    distinctive = {x for x in overlap if len(x) >= 4 or re.search(r"\d", x)}
    score = len(overlap) / max(1, min(len(e), len(i)))
    score += min(0.35, 0.12 * len(distinctive))
    if eq and eq & iq:
        score += 0.25
    return min(score, 0.95)


def semantic_same_product(expected, identity):
    """فحص دلالي احتياطي فقط عندما تكون العربية/الإنجليزية مختلفة ولا توجد قرينة حاسمة."""
    if not SEMANTIC_VERIFY or not expected or not identity:
        return False
    key = hashlib.sha256(f"{normalize_ar(expected)}|{normalize_ar(identity)}".encode()).hexdigest()
    now = time.time()
    hit = MATCH_CACHE.get(key)
    if hit and now - hit[1] < MATCH_CACHE_TTL:
        return hit[0]
    system = """أنت مدقق منتجات صارم. قارن طلب المستخدم بعنوان صفحة متجر. أجب بكلمة MATCH فقط إذا كانا نفس المنتج ونفس الموديل والحجم/الوزن/السعة. إذا كان هناك شك أو اختلاف اكتب MISMATCH فقط."""
    prompt = f"طلب المستخدم: {expected}\nهوية صفحة المتجر: {identity}"
    try:
        out, _ = call_gemini([{"text": prompt}], system=system, use_search=False)
        ok = out.strip().upper().startswith("MATCH") and "MISMATCH" not in out.strip().upper()
    except Exception:
        ok = False
    MATCH_CACHE[key] = (ok, now)
    if len(MATCH_CACHE) > 1000:
        oldest = min(MATCH_CACHE, key=lambda k: MATCH_CACHE[k][1])
        MATCH_CACHE.pop(oldest, None)
    return ok


def offer_rows(product):
    offers = product.get("offers") if isinstance(product, dict) else None
    if not offers:
        return []
    if not isinstance(offers, list):
        offers = [offers]
    rows = []
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        # AggregateOffer يستخدم lowPrice كسعر البداية الحالي.
        price = safe_float(offer.get("price")) or safe_float(offer.get("lowPrice"))
        if price is None and isinstance(offer.get("priceSpecification"), dict):
            price = safe_float(offer["priceSpecification"].get("price"))
        currency = str(offer.get("priceCurrency") or "").upper().strip()
        availability = str(offer.get("availability") or "").lower()
        url = str(offer.get("url") or "")
        rows.append({"price": price, "currency": currency, "availability": availability, "url": url})
    return rows


def structured_product_result(products, expected, page_url):
    best = None
    for p in products:
        ident = " ".join(str(p.get(k) or "") for k in ("name", "sku", "mpn", "gtin13", "model"))
        score = lexical_match_score(expected, ident)
        if score < 0:
            continue
        rows = offer_rows(p)
        for row in rows:
            if row["currency"] and row["currency"] not in ("KWD", "KD"):
                continue
            avail = row["availability"]
            is_oos = any(x in avail for x in ("outofstock", "soldout", "discontinued"))
            is_in = any(x in avail for x in ("instock", "limitedavailability", "preorder"))
            candidate = {
                "score": score, "price": row["price"], "in_stock": is_in,
                "out_of_stock": is_oos, "url": urllib.parse.urljoin(page_url, row["url"]) if row["url"] else page_url,
                "identity": ident,
            }
            same_url_bonus = 0.20 if row["url"] and urllib.parse.urlparse(candidate["url"]).path.rstrip("/") == urllib.parse.urlparse(page_url).path.rstrip("/") else 0
            rank = (score + same_url_bonus, 1 if is_in else 0, 1 if row["price"] is not None else 0)
            if best is None or rank > best[0]:
                best = (rank, candidate)
    return best[1] if best else None


def page_stock_status(html, structured=None):
    if structured:
        if structured.get("in_stock"):
            return "in"
        if structured.get("out_of_stock"):
            return "out"
    low = (html or "").lower()
    # بيانات المخزون البرمجية أوثق من كلمات قد تظهر في منتجات مقترحة.
    if re.search(r'"(?:stock_status|availability)"\s*:\s*"(?:outofstock|out_of_stock|soldout)"|"(?:is_in_stock|available)"\s*:\s*false', low):
        return "out"
    if re.search(r'"(?:stock_status|availability)"\s*:\s*"(?:instock|in_stock|available)"|"(?:is_in_stock|available)"\s*:\s*true', low):
        return "in"
    positive = any(s in low[:120000] for s in IN_STOCK_SIGNS)
    negative = any(s in low[:120000] for s in OOS_SIGNS)
    # إذا ظهرت الإشارتان معاً غالباً توجد منتجات مقترحة؛ لا نخاطر.
    if positive and negative:
        return "unknown"
    if negative:
        return "out"
    if positive:
        return "in"
    return "unknown"


def fallback_meta_price(html):
    for key in ("product:price:amount", "og:price:amount", "price"):
        v = safe_float(meta_content(html, key))
        if v is not None:
            cur = (meta_content(html, "product:price:currency") or meta_content(html, "priceCurrency") or "").upper()
            if not cur or cur in ("KWD", "KD"):
                return v
    # Microdata exact content attribute.
    for m in re.finditer(r'itemprop=["\']price["\'][^>]*content=["\']([\d.,]+)', html or "", re.I):
        v = safe_float(m.group(1))
        if v is not None:
            return v
    return None


def fallback_visible_price(html, claimed=None):
    """آخر حل فقط: سعر ظاهر قريب من أعلى الصفحة، ولا نقبله إن تعددت الأسعار بشكل يوحي بقائمة منتجات."""
    text = clean_visible_text((html or "")[:100000])
    vals = []
    pats = [
        r'(?:KWD|KD|د\.?\s*ك)\s*:?\s*(\d+(?:\.\d+)?)',
        r'(\d+(?:\.\d+)?)\s*(?:د\.?\s*ك|KWD|KD)',
    ]
    for pat in pats:
        vals.extend(safe_float(x) for x in re.findall(pat, text, re.I))
    vals = [x for x in vals if x is not None]
    uniq = []
    for x in vals:
        if all(abs(x-y) > 0.001 for y in uniq):
            uniq.append(x)
    if not uniq or len(uniq) > 6:
        return None
    if claimed:
        # مقتطف البحث مجرد مرشد لا مصدر حقيقة.
        return min(uniq, key=lambda x: abs(math.log((x + 1e-9) / claimed)))
    return uniq[0] if len(uniq) == 1 else None


def looks_like_product_page(url, html, products=None):
    if not url_is_direct_candidate(url):
        return False
    products = products if products is not None else jsonld_products(html)
    low = (html or "").lower()
    has_product_meta = bool(re.search(r'og:type["\']?\s+content=["\']product|itemprop=["\']price', low))
    has_h1 = bool(re.search(r"<h1\b", low))
    has_buy = any(s in low for s in IN_STOCK_SIGNS)
    if len(products) == 1:
        return True
    # بعض صفحات المنتج تحمل JSON-LD لمنتجات مقترحة أيضاً، لكن og:type + H1 يحسمان أنها صفحة منتج.
    if has_product_meta and has_h1:
        return True
    if len(products) > 3:
        return False
    # دعم نص Jina المصيّر لصفحات JavaScript.
    is_markdown = "<html" not in low and (re.search(r"(?im)^title:\s*.+", html or "") or re.search(r"(?m)^#\s+.+", html or ""))
    price_hits = len(re.findall(r"(?:kwd|kd|د\.?\s*ك)\s*:?\s*\d|\d\s*(?:د\.?\s*ك|kwd|kd)", low))
    if is_markdown and has_buy and 1 <= price_hits <= 8:
        return True
    return has_product_meta and has_h1 and has_buy


def extract_candidate_product_links(base_url, html, expected):
    """إذا أعطانا البحث صفحة مجموعة، نحاول استخراج رابط المنتج المطابق منها تلقائياً."""
    candidates = []
    patterns = [
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        r'\[([^\]]{2,160})\]\((https?://[^)\s]+)\)',  # Jina markdown
    ]
    base_host = urllib.parse.urlparse(base_url).netloc.lower().replace("www.", "")
    # HTML pattern: href, anchor. Markdown pattern: anchor, href.
    for idx, pat in enumerate(patterns):
        for m in re.finditer(pat, html or "", re.I | re.S):
            if idx == 0:
                href, label = m.group(1), clean_visible_text(m.group(2))
            else:
                label, href = clean_visible_text(m.group(1)), m.group(2)
            u = urllib.parse.urljoin(base_url, html_lib.unescape(href))
            try:
                host = urllib.parse.urlparse(u).netloc.lower().replace("www.", "")
            except Exception:
                continue
            if host != base_host or not url_is_direct_candidate(u):
                continue
            identity = f"{label} {urllib.parse.unquote(urllib.parse.urlparse(u).path)}"
            score = lexical_match_score(expected, identity)
            if score < 0:
                continue
            if PRODUCT_PATH_HINT.search(u):
                score += 0.25
            if score >= 0.30:
                candidates.append((score, u))
    out, seen = [], set()
    for _, u in sorted(candidates, reverse=True):
        clean = u.split("#")[0]
        if clean not in seen:
            seen.add(clean); out.append(clean)
        if len(out) >= 3:
            break
    return out


def verify_product_page(url, claimed=None, expected="", allow_repair=True):
    """يرجع level=2 فقط عند تطابق المنتج + سعر حي + توفر حي + صفحة مباشرة، وإلا level=0."""
    result = {"level": 0, "price": None, "url": url, "reason": "unknown"}
    if not url:
        result["reason"] = "empty_url"; return result
    html, src, final_url = fetch_page_text(url)
    result["url"] = final_url or url
    if not html:
        result["reason"] = "unreadable"; return result

    final_url = canonical_url(final_url or url, html)
    result["url"] = final_url
    products = jsonld_products(html)

    if not looks_like_product_page(final_url, html, products):
        if allow_repair:
            for candidate in extract_candidate_product_links(final_url, html, expected):
                fixed = verify_product_page(candidate, claimed=claimed, expected=expected, allow_repair=False)
                if fixed["level"] == 2:
                    fixed["reason"] = "repaired_from_listing"
                    return fixed
        result["reason"] = "not_product_page"; return result

    identity = page_identity(html, final_url, products)
    score = lexical_match_score(expected, identity) if expected else 0.8
    if score < 0:
        result["reason"] = "variant_mismatch"; return result
    if expected and score < 0.42 and not semantic_same_product(expected, identity):
        result["reason"] = "product_mismatch"; return result

    structured = structured_product_result(products, expected, final_url) if products else None
    stock = page_stock_status(html, structured)
    if stock != "in":
        result["reason"] = "out_of_stock" if stock == "out" else "stock_unconfirmed"
        return result

    price = structured.get("price") if structured else None
    if price is None:
        price = fallback_meta_price(html)
    if price is None:
        price = fallback_visible_price(html, claimed)
    if price is None:
        result["reason"] = "price_unconfirmed"; return result

    if structured and structured.get("url") and url_is_direct_candidate(structured["url"]):
        result["url"] = structured["url"]
    result.update({"level": 2, "price": price, "reason": "verified", "source": src, "identity": identity})
    return result


def line_claimed_price(line):
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:د\.?\s*ك|KWD|KD)', line or "")
    return float(m.group(1)) if m else None


def line_set_price(line, price):
    return re.sub(r'(\d+(?:\.\d+)?)(?=\s*(?:د\.?\s*ك|KWD|KD))', f"{price:.3f}", line, count=1)


def match_url(name, urls):
    """يربط اسم المتجر بلنكه، لكن لا ينشئ رابط بحث بديل إطلاقاً."""
    if not urls:
        return ""
    if name in urls:
        return urls[name]
    nn = normalize_name(normalize_ar(name))
    for k, v in urls.items():
        kk = normalize_name(normalize_ar(k))
        if nn and kk and (nn in kk or kk in nn):
            return v
    dom = store_domain(name)
    if dom:
        key = domain_key(dom)
        for k, v in urls.items():
            if key and (key in (v or "").lower() or key in normalize_name(k)):
                return v
    return ""


def url_matches_store(store, url, title=""):
    if not url:
        return False
    host = urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
    dom = store_domain(store)
    if dom:
        return domain_key(dom) in host
    sn = normalize_name(normalize_ar(store))
    hay = normalize_name(normalize_ar(f"{host} {title}"))
    return bool(sn and (sn in hay or hay in sn))

def maps_search_url(product, lat=None, lng=None):
    """رابط خرائط جوجل عن الفئة الصح. بدون إحداثيات = جوجل ماب يفتح على موقع المستخدم تلقائياً."""
    category_text, _ = call_gemini([{"text": f"المنتج: {product}"}], system=MAPS_CATEGORY_SYSTEM, use_search=False)
    category = category_text.strip().splitlines()[0].strip() if category_text else product
    safe_category = urllib.parse.quote(category)
    if lat is not None and lng is not None:
        return f"https://www.google.com/maps/search/{safe_category}/@{lat},{lng},15z"
    return f"https://www.google.com/maps/search/{safe_category}"

def send_maps_button(from_number, product, bot_id, lang):
    """زر الخريطة المباشر — بدون طلب لوكيشن، جوجل ماب هو اللي يحدد موقع المستخدم"""
    url = maps_search_url(product)
    send_whatsapp_cta(from_number, T(lang, "maps_body"), url, bot_id, T(lang, "maps_btn"))

def send_product_result(from_number, txt, urls, bot_id, lang, query, best_only=False, allow_refresh=True):
    """يرسل فقط عروضاً موثقة من صفحة المنتج نفسها. لا أسعار تقريبية ولا صفحات تصنيف."""
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
    expected = re.sub(r"^📦\s*", "", title or query).strip()

    linked, used = [], set()
    for o in offers:
        u = match_url(o["name"], urls)
        if u and u not in used:
            linked.append((o, u)); used.add(u)

    verified = []
    if linked:
        checks = list(RESOLVER.map(
            lambda t: verify_product_page(t[1], line_claimed_price(t[0]["line"]), expected), linked
        ))
        for (o, original_url), c in zip(linked, checks):
            if c["level"] != 2:
                print(f"DROPPED ({c.get('reason')}): {o['name']} | {original_url[:120]}")
                continue
            o = dict(o)
            claimed = line_claimed_price(o["line"])
            if claimed is None or abs(c["price"] - claimed) > 0.001:
                print(f"PRICE FIXED: {o['name']} {claimed} -> {c['price']}")
            o["line"] = line_set_price(o["line"], c["price"])
            o["price"] = c["price"]
            verified.append((o, c["url"]))

    # روابط إضافية لا تُستخدم إلا إذا كانت من نفس المتجر ومثبتة بالكامل.
    if len(verified) < 4:
        attached_urls = {u for _, u in linked}
        extras = [(n, u) for n, u in urls.items() if u and u not in attached_urls and not is_junk_store(n)]
        if extras:
            extra_checks = list(RESOLVER.map(lambda t: verify_product_page(t[1], None, expected), extras))
            cur = "د.ك" if lang == "ar" else "KWD"
            for (n, _), c in zip(extras, extra_checks):
                if c["level"] != 2:
                    continue
                body = f"{n} — {c['price']:.3f} {cur}"
                verified.append(({"line": body, "name": n, "best": False, "price": c["price"]}, c["url"]))
                if len(verified) >= 4:
                    break

    # لو كانت نتيجة الكاش قديمة أو كل الروابط فشلت، نعيد البحث مرة واحدة بدون كاش قبل الرد.
    if not verified and allow_refresh:
        fresh_txt, fresh_urls = search_product(query, lang, force_refresh=True)
        if fresh_txt and (fresh_txt != txt or fresh_urls != urls):
            return send_product_result(from_number, fresh_txt, fresh_urls, bot_id, lang, query, best_only, allow_refresh=False)

    if not verified:
        send_whatsapp_text(from_number, f"{title or f'📦 {query}'}\n\n{T(lang, 'no_verified_offer')}", bot_id)
        return True

    # السعر الموثق من الصفحة هو المصدر الوحيد للترتيب وعلامة ✅.
    if "⭐" not in txt:
        for o, _ in verified:
            o["line"] = re.sub(r"^\s*(?:✅|🏆|•)\s*", "", o["line"])
        verified.sort(key=lambda t: t[0]["price"])
        verified[0][0]["line"] = "✅ " + verified[0][0]["line"]

    send_whatsapp_text(from_number, title or f"📦 {query}", bot_id)
    limit = 1 if best_only else 4
    for o, u in verified[:limit]:
        send_whatsapp_cta(from_number, o["line"], u, bot_id, f"🛒 {o['name'][:18]}")
    return True

def call_gemini(parts, system=SYSTEM_PROMPT, use_search=True):
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 2000},
    }
    if use_search:
        payload["tools"] = [{"google_search": {}}]
    try:
        r = requests.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload, timeout=90)
        if r.status_code >= 400:
            print(f"Gemini HTTP {r.status_code}: {r.text[:500]}")
            return "", {}

        data = r.json()
        candidates = data.get("candidates") or []
        if not candidates:
            print(f"Gemini returned no candidates: {str(data)[:500]}")
            return "", {}

        cand = candidates[0]
        text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", [])).strip()

        # LINKS is helpful, but URL extraction no longer depends on it alone.
        pairs = []
        m = re.search(r"(?im)^\s*LINKS\s*:\s*(.+)$", text)
        if m:
            raw = m.group(1)
            for part in re.split(r"[,،]+", raw):
                part = part.strip()
                if "=" in part:
                    name, target = part.split("=", 1)
                    name, target = name.strip(), target.strip()
                    if target.startswith(("http://", "https://")):
                        pairs.append((name, target))
                    else:
                        dom = clean_domain(target)
                        if name and "." in dom:
                            pairs.append((name, dom))
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
            records.append({
                "title": web.get("title", ""),
                "raw": raw_uri,
                "url": final_uri or raw_uri,
            })

        urls_map = {}
        used_urls = set()
        stores = extract_store_names(text)

        # Best mapping: connect each displayed store to groundingSupports.
        supports = metadata.get("groundingSupports", []) or []
        for store in stores:
            store_norm = normalize_name(store)
            for support in supports:
                segment = (support.get("segment") or {}).get("text", "")
                if store_norm and store_norm in normalize_name(segment):
                    for idx in support.get("groundingChunkIndices", []) or []:
                        if 0 <= idx < len(records):
                            url = records[idx]["url"]
                            title = records[idx].get("title", "")
                            if url and url not in used_urls and url_matches_store(store, url, title):
                                urls_map[store] = url
                                used_urls.add(url)
                                break
                if store in urls_map:
                    break

        # LINKS قد يحتوي رابط المنتج الكامل. لا نثق به حتى يمر لاحقاً بفحص الصفحة الحي.
        for name, target in pairs:
            if name in urls_map:
                continue
            if target.startswith(("http://", "https://")):
                resolved = get_final_url(target)
                if resolved and resolved not in used_urls and url_matches_store(name, resolved):
                    urls_map[name] = resolved
                    used_urls.add(resolved)
                continue
            key = domain_key(target)
            for rec in records:
                haystack = f"{rec['title']} {rec['raw']} {rec['url']}".lower()
                if rec["url"] and key and key in haystack and rec["url"] not in used_urls and url_matches_store(name, rec["url"], rec["title"]):
                    urls_map[name] = rec["url"]
                    used_urls.add(rec["url"])
                    break

        # Last fallback: match store names directly against source titles.
        for store in stores:
            if store in urls_map:
                continue
            store_norm = normalize_name(store)
            for rec in records:
                if rec["url"] and store_norm and store_norm in normalize_name(rec["title"]):
                    if rec["url"] not in used_urls and url_matches_store(store, rec["url"], rec["title"]):
                        urls_map[store] = rec["url"]
                        used_urls.add(rec["url"])
                        break

        # Alias fallback: Arabic store names ↔ English domains (اليوسفي ↔ best.com.kw).
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

        # لا نستخدم مصادر عامة كأزرار شراء؛ غياب رابط موثوق أفضل من رابط خاطئ.

        print({
            "stores": stores,
            "links_pairs": pairs,
            "grounding_chunks": len(chunks),
            "resolved_buttons": list(urls_map.keys()),
        })
        return text, dict(list(urls_map.items())[:4])
    except Exception as e:
        print(f"Gemini err {e}"); return "", {}

def source_label(title, url):
    title = (title or "").strip()
    if title:
        return title[:40]
    try:
        host = urllib.parse.urlparse(url).netloc.replace("www.", "")
        return host.split(".")[0] or "المتجر"
    except Exception:
        return "المتجر"

# عدد جولات البحث المتوازية لكل طلب — قابل للتعديل من Railway
SEARCH_RUNS = int(os.environ.get("SEARCH_RUNS", "4"))

def answer_score(txt, urls):
    """نفضل جواباً متماسكاً بروابط من نفس الجولة، ونخفض تقييم صفحات البحث/التصنيف."""
    stores, links = result_quality(txt, urls)
    score = stores * 2 + links * 3
    if txt and "📦" in txt:
        score += 1
    for u in (urls or {}).values():
        if not url_is_direct_candidate(u):
            score -= 4
        elif PRODUCT_PATH_HINT.search(u):
            score += 1
    return score


def best_of_search(parts, lang):
    """عدة جولات مستقلة؛ نختار أفضل جواب كامل ولا نخلط روابط جولة مع جواب جولة ثانية."""
    try:
        futs = [SEARCH_POOL.submit(call_gemini, parts) for _ in range(SEARCH_RUNS)]
        results = [f.result() for f in futs]
    except Exception as e:
        print(f"best_of_search err {e}")
        return call_gemini(parts)

    results = [(t, u) for (t, u) in results if t]
    if not results:
        return "", {}
    scored = sorted(results, key=lambda r: answer_score(r[0], r[1]), reverse=True)
    best_txt, best_urls = scored[0]
    print({"tournament": [answer_score(t, u) for t, u in scored], "winner_stores": result_quality(best_txt, best_urls)[0], "winner_links": len(best_urls)})
    return best_txt, dict(list(best_urls.items())[:4])

def search_product(query, lang, prompt_text=None, force_refresh=False):
    """البوابة الموحدة للبحث: كاش أولاً، وإلا بطولة 4 بحوث ونرسل الأقوى.
    prompt_text: صياغة مخصصة للطلب (مثل صورة + سؤال) — الافتراضي بحث سعر عادي.
    لا نحفظ بالكاش إلا نتيجة قوية: مقارنة فيها متاجر ولنكات، أو إجابة معلوماتية وافية."""
    if not force_refresh:
        cached = cache_get(query, lang)
        if cached:
            return cached

    text_part = prompt_text or f"ابحث عن {query} في الكويت. {LANG_INSTR[lang]}"
    txt, urls = best_of_search([{"text": text_part}], lang)
    stores, links = result_quality(txt, urls)

    if stores >= CACHE_MIN_STORES and links >= CACHE_MIN_LINKS:
        cache_put(query, lang, txt, urls)
    elif stores == 0 and txt and len(txt) >= 120:
        # إجابة معلوماتية (حالة 4) وافية — تستاهل الكاش بعد
        cache_put(query, lang, txt, urls)
    else:
        print(f"NOT CACHED (quality low): stores={stores} links={links} | {query[:60]}")
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
    try:
        r = requests.post(url,json=payload,headers=h,timeout=15)
        if not r.ok:
            print(f"WhatsApp text error {r.status_code}: {r.text[:500]}")
        return r.ok
    except Exception as e:
        print(f"WhatsApp text exception: {e}")
        return False

def send_whatsapp_cta(to,body,link,bot_id,title):
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    payload={"messaging_product":"whatsapp","to":to,"type":"interactive","interactive":{"type":"cta_url","body":{"text":body[:1024]},"action":{"name":"cta_url","parameters":{"display_text":title[:20],"url":link}}}}
    try:
        r = requests.post(url,json=payload,headers=h,timeout=15)
        if not r.ok:
            print(f"WhatsApp CTA error {r.status_code}: {r.text[:500]} | {link[:180]}")
        return r.ok
    except Exception as e:
        print(f"WhatsApp CTA exception: {e} | {link[:180]}")
        return False

def send_whatsapp_buttons(to, body, buttons, bot_id):
    """أزرار رد سريعة (Reply Buttons) — حد أقصى 3 أزرار"""
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    btns=[{"type":"reply","reply":{"id":b["id"],"title":b["title"][:20]}} for b in buttons[:3]]
    payload={"messaging_product":"whatsapp","to":to,"type":"interactive","interactive":{"type":"button","body":{"text":body[:1024]},"action":{"buttons":btns}}}
    try:
        r = requests.post(url,json=payload,headers=h,timeout=15)
        if not r.ok:
            print(f"WhatsApp buttons error {r.status_code}: {r.text[:500]}")
        return r.ok
    except Exception as e:
        print(f"WhatsApp buttons exception: {e}")
        return False

def send_language_choice(to, bot_id):
    """رسالة اختيار اللغة — تُرسل مرة واحدة فقط لمن يبدأ بصورة"""
    body = "🌐 اختر لغتك المفضلة\nChoose your preferred language"
    send_whatsapp_buttons(to, body, [
        {"id": "lang_ar", "title": "العربية 🇰🇼"},
        {"id": "lang_en", "title": "English 🇬🇧"},
    ], bot_id)

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
            # الكابشن (النص المرفق مع الصورة) يحدد اللغة تلقائياً — ما نحتاج نسأل
            caption = (msg.get("image",{}) or {}).get("caption","").strip()
            cap_lang = detect_lang(caption) if caption else None
            if cap_lang:
                USER_LANG[from_number] = cap_lang
            if from_number not in USER_LANG:
                # أول تعامل معنا وبدأ بصورة بدون نص: نعلق الصور ونسأله عن لغته مرة وحدة بس
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
    """يعالج ضغطات الأزرار — حالياً أزرار اختيار اللغة"""
    from_number=message["from"]
    reply=(message.get("interactive") or {}).get("button_reply") or {}
    btn_id=reply.get("id","")
    if btn_id not in ("lang_ar","lang_en"):
        return
    lang = "ar" if btn_id=="lang_ar" else "en"
    USER_LANG[from_number]=lang
    pend=PENDING_IMAGES.pop(from_number,None)
    if pend and pend["images"]:
        # نكمل معالجة الصور اللي كانت بالانتظار بلغته المختارة
        if len(pend["images"])==1:
            process_single_image(pend["images"][0], pend["bot_id"], lang)
        else:
            process_multi_images(pend["images"], from_number, pend["bot_id"], lang)
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

    # الخطوة 1: تحديد الاسم القياسي للمنتج (مكالمة سريعة بدون بحث)
    ident,_=call_gemini([{"inline_data":{"mime_type":mime,"data":b64}},{"text":"ما اسم هذا المنتج؟"}], system=IDENTIFY_SYSTEM, use_search=False)
    product_name = ident.strip().splitlines()[0].strip() if ident else ""

    if product_name and caption:
        # صورة + طلب مكتوب: أي سؤال عن المنتج (سعر، تصليح، مكونات، مواصفات...)
        request_query = f"{caption} — {product_name}"
        prompt_text = f"المنتج في الصورة: {product_name}\nطلب المستخدم عنه: {caption}\nصنّف الطلب (مقارنة سعر / توصية / خدمة / سؤال معلوماتي) وأجب عليه مباشرة بالتنسيق المناسب. {LANG_INSTR[lang]}"
        txt,urls=search_product(request_query, lang, prompt_text=prompt_text)
        LAST_SEARCH[from_number] = {"product": request_query}
        query = request_query
    elif product_name:
        # صورة بدون نص: السلوك المعتاد — مقارنة أسعار
        txt,urls=search_product(product_name, lang)
        LAST_SEARCH[from_number] = {"product": product_name}
        query = product_name
    else:
        # ما قدرنا نحدد الاسم؟ نرجع لبحث الصورة المباشر (بدون كاش)
        req = caption if caption else "ما هذا المنتج؟ ابحث عن سعره الحالي في الكويت."
        txt,urls=best_of_search([{"inline_data":{"mime_type":mime,"data":b64}},{"text":f"{req} {LANG_INSTR[lang]}"}], lang)
        name_m = re.search(r"📦\s*(.+)", txt or "")
        product_name = name_m.group(1).strip() if name_m else "المنتج"
        query = f"{caption} — {product_name}" if caption else product_name
        LAST_SEARCH[from_number] = {"product": query}

    if not txt:
        send_whatsapp_text(from_number,T(lang,"cant_identify"),bot_id)
        return

    # التنسيق: اسم المنتج ثم اللنكات مباشرة (أو خدمة: رسالة الأرقام)
    need_map = send_product_result(from_number, txt, urls, bot_id, lang, query)
    if need_map and product_name and product_name != "المنتج":
        # زر الخريطة المباشر — جوجل ماب يحدد الموقع بنفسه
        send_maps_button(from_number, query, bot_id, lang)

def identify_image_product(msg):
    """يحدد الاسم القياسي لمنتج من صورة (بدون بحث — سريع)"""
    try:
        b64,mime=download_whatsapp_media(msg["image"]["id"])
        ident,_=call_gemini([{"inline_data":{"mime_type":mime,"data":b64}},{"text":"ما اسم هذا المنتج؟"}], system=IDENTIFY_SYSTEM, use_search=False)
        return ident.strip().splitlines()[0].strip() if ident else ""
    except Exception as e:
        print(f"identify err {e}")
        return ""

def process_cart(products, from_number, bot_id, lang="ar"):
    """السلة: كل منتج ياخذ بحثه الكامل (كاش ← بطولة)،
    ورده = رسالة اسم المنتج + CTA واحد فقط للخيار الأفضل (اسمه وسعره داخل الرسالة)."""
    results = list(WORKERS.map(lambda p: (p, *search_product(p, lang)), products))

    any_ok = False
    for p, txt, urls in results:
        if not txt:
            continue
        any_ok = True
        send_product_result(from_number, txt, urls, bot_id, lang, p, best_only=True)

    if not any_ok:
        send_whatsapp_text(from_number, T(lang, "not_found"), bot_id)
        return
    LAST_SEARCH[from_number] = {"product": products[0]}

def process_multi_images(messages,from_number,bot_id,lang="ar"):
    send_whatsapp_text(from_number,T(lang,"multi_images",c=len(messages)),bot_id)
    # نحدد أسماء كل الصور بالتوازي (مكالمات سريعة بدون بحث)، ثم بحث سلة واحد
    names=[n for n in WORKERS.map(identify_image_product,messages) if n]
    if not names:
        send_whatsapp_text(from_number,T(lang,"cant_identify"),bot_id)
        return
    process_cart(names, from_number, bot_id, lang)

def process_text_message(message,bot_id):
    from_number=message["from"]; user_text=message["text"]["body"]

    # أمر تغيير اللغة — يشتغل أي وقت: "لغة" / "language" / "lang" / "/lang" ...
    cmd=re.sub(r"[^\w\u0600-\u06FF]","",user_text.strip().lower())
    if cmd in ("لغة","اللغة","غيراللغة","language","lang","changelanguage"):
        send_language_choice(from_number, bot_id)
        return

    # كشف اللغة من الرسالة النصية — النص دايماً يحدّث لغة المستخدم بالاتجاهين
    detected=detect_lang(user_text)
    if detected:
        USER_LANG[from_number]=detected
    lang=USER_LANG.get(from_number,"ar")
    # إذا كان عنده صور معلقة بانتظار اختيار اللغة، نعالجها الحين بنفس لغة رسالته
    pend=PENDING_IMAGES.pop(from_number,None)
    if pend and pend["images"]:
        if len(pend["images"])==1:
            process_single_image(pend["images"][0], pend["bot_id"], lang)
        else:
            process_multi_images(pend["images"], from_number, pend["bot_id"], lang)

    products=extract_products(user_text)
    if len(products)==1:
        send_whatsapp_text(from_number,T(lang,"searching",q=products[0]),bot_id)
        # البوابة الموحدة: كاش ← وإلا بطولة بحوث + دمج
        txt,urls=search_product(products[0], lang)
        LAST_SEARCH[from_number] = {"product": products[0]}

        # التنسيق: اسم المنتج ثم اللنكات مباشرة (أو خدمة: رسالة الأرقام)
        need_map = send_product_result(from_number, txt, urls, bot_id, lang, products[0])
        if need_map:
            # زر الخريطة المباشر — جوجل ماب يحدد الموقع بنفسه
            send_maps_button(from_number, products[0], bot_id, lang)
            
    else:
        send_whatsapp_text(from_number,T(lang,"multi_text",c=len(products)),bot_id)
        process_cart(products, from_number, bot_id, lang)

def process_location_message(message, bot_id):
    """احتياط: إذا المستخدم دز موقعه بنفسه، نفتح الخريطة على إحداثياته بالضبط"""
    from_number = message["from"]
    lat = message["location"]["latitude"]
    lng = message["location"]["longitude"]
    lang = USER_LANG.get(from_number, "ar")

    last_search = LAST_SEARCH.get(from_number)
    if not last_search or not last_search.get("product"):
        send_whatsapp_text(from_number, T(lang,"no_saved_product"), bot_id)
        return

    product = last_search["product"]
    maps_url = maps_search_url(product, lat, lng)
    body = T(lang,"maps_body_loc",p=product)
    send_whatsapp_cta(from_number, body, maps_url, bot_id, T(lang,"maps_btn"))

@app.get("/")
async def health(): return {"status":"v34 Direct Product + Live Stock + Verified Price"}
