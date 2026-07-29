# -*- coding: utf-8 -*-
import os, re, time, base64, requests, uuid, asyncio, urllib.parse, hashlib
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
SEARCH_POOL = ThreadPoolExecutor(max_workers=4)  # للبحث المزدوج المتوازي
HEADERS = {"User-Agent": "Mozilla/5.0"}

# ===== كاش النتائج: نفس المنتج = نفس الجواب واللنكات طوال مدة الكاش =====
SEARCH_CACHE = {}          # key -> {"txt":..., "urls":..., "ts":...}
CACHE_TTL = int(os.environ.get("CACHE_TTL_HOURS", "2")) * 3600  # قابلة للتعديل من Railway بدون كود
CACHE_MAX = 500            # حد أقصى للذاكرة

# حارس الجودة: لا نحفظ بالكاش إلا نتيجة قوية (3+ متاجر بأسعار ولنك واحد على الأقل)
CACHE_MIN_STORES = 3
CACHE_MIN_LINKS = 1

def result_quality(txt, urls):
    """(عدد المتاجر بأسعار، عدد اللنكات)"""
    return len(extract_store_names(txt or "")), len(urls or {})

def fallback_search_url(query):
    """زر مضمون دايماً: بحث جوجل عن المتجر/المنتج إذا ما توفر لنك مباشر"""
    return "https://www.google.com/search?q=" + urllib.parse.quote(f"{query} الكويت اونلاين")

def best_store_name(txt):
    """اسم أفضل متجر إن وجد"""
    stores = extract_store_names(txt)
    return stores[0] if stores else ""

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
    hit = SEARCH_CACHE.get(cache_key(query, lang))
    if hit and (now - hit["ts"]) < CACHE_TTL:
        print(f"CACHE HIT (exact): {query[:60]}")
        return hit["txt"], dict(hit["urls"])
    
    qt = norm_tokens(query)
    if not qt: return None
    
    best, best_score = None, 0.0
    for entry in SEARCH_CACHE.values():
        if entry.get("lang") != lang or (now - entry["ts"]) >= CACHE_TTL: continue
        et = entry.get("tokens") or set()
        if not et: continue
        inter = len(qt & et)
        score = inter / len(qt | et)
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

# برومبت تحديد الاسم القياسي للمنتج من الصورة (بدون بحث — سريع ورخيص)
IDENTIFY_SYSTEM = """أنت خبير تعرف على المنتجات. انظر للصورة واكتب الاسم التجاري القياسي للمنتج بصيغة ثابتة دائماً:
[البراند] [نوع المنتج] [رقم الموديل باللاتيني إن ظهر] [اللون/النكهة] [الحجم/الوزن إن ظهر]

رقم الموديل هو أهم عنصر — دور عليه على العبوة أو الذراع أو الملصق (مثل RB3721، SM-S928، MQ2V3).
أمثلة على الصيغة:
- ريبان نظارة شمسية RB3721 اسود 59 مم
- برينجلز كاتشب 200 جرام
سطر واحد فقط. بدون أقواس أو شرح أو مقدمات أو رموز."""

# برومبت السلة الذكية: تجميع المنتجات في المتاجر المناسبة لها
CART_SYSTEM = """أنت مساعد تسوق كويتي عبقري. ستستلم قائمة منتجات (سلة).
استخدم بحث Google فعلياً لتجد أفضل سعر لكل منتج في الكويت.

مهمتك: "جمّع ولا تجبر". 
لا تحاول وضع كل المنتجات في متجر واحد إذا كانت من فئات مختلفة. بدلاً من ذلك، جمّع المنتجات المتشابهة في أفضل متجر لها (مثلاً الإكترونيات معاً، والمواد الغذائية معاً)، بحيث يطلب المستخدم من أقل عدد ممكن من المتاجر وبأفضل الأسعار.

رد بهذا الشكل والتنسيق فقط:
🛒 تفاصيل سلتك ([العدد] منتجات):

🏪 [اسم المتجر الأول]
• [المنتج] — [السعر] د.ك
• [المنتج] — [السعر] د.ك
(إجمالي المتجر: [المجموع] د.ك)

🏪 [اسم المتجر الثاني] (إن وجد)
• [المنتج] — [السعر] د.ك
(إجمالي المتجر: [المجموع] د.ك)

==================
💰 الإجمالي الكلي للسلة: [المجموع الكلي] د.ك

سطر أخير إلزامي:
LINKS: اسم المتجر الأول=[الدومين الحقيقي], اسم المتجر الثاني=[الدومين الحقيقي]
لا تخمّن الدومين ولا الأسعار. ممنوع روابط ظاهرة. ممنوع Markdown."""

# ===== نصوص البوت بالعربي والإنجليزي =====
MSG = {
    "ar": {
        "identifying": "ثواني بس.. أحدد المنتج وأدور لك الأفضل!",
        "searching": "🔍 أدور لك على {q}...",
        "not_found": "ما لقيت",
        "cant_identify": "ما قدرت أحدد المنتج",
        "shop_from": "تسوق من {n} 👇",
        "location_prompt": "تبي أقرب محل يبيعه؟ 📍\n\nاضغط الزر تحت ودز موقعك، وعلى طول أرد لك بأقرب المحلات على الخريطة 👇",
        "multi_text": "تمام لقيت {c} منتجات، أسوي سلة...",
        "multi_images": "تمام لقطت {c} منتجات، أسوي سلة...",
        "no_saved_product": "ما عندي منتج محفوظ حالياً 😅. ابحث عن منتج أول، وبعدها دز موقعك عشان أدلك على أقرب مكان يبيعه!",
        "maps_body": "📍 بحثك الأخير كان عن ({p})\n\nجهزت لك أقرب المحلات اللي تبيعه حولك، اضغط الزر وافتح الخريطة 👇",
        "maps_btn": "📍 افتح الخريطة",
        "lang_saved": "تمام، بكلمك عربي من هني ورايح 🇰🇼\nدز صورة منتج أو اكتب اسمه وأنا حاضر!",
    },
    "en": {
        "identifying": "One sec.. identifying the product and finding you the best deal!",
        "searching": "🔍 Looking up {q}...",
        "not_found": "Couldn't find it",
        "cant_identify": "Couldn't identify the product",
        "shop_from": "Shop from {n} 👇",
        "location_prompt": "Want the nearest store that sells it? 📍\n\nTap the button below to share your location, and I'll instantly send you the closest stores on a map 👇",
        "multi_text": "Got it, found {c} products. Building your cart...",
        "multi_images": "Nice, spotted {c} products. Building your cart...",
        "no_saved_product": "I don't have a saved product yet 😅. Search for a product first, then share your location and I'll point you to the nearest store!",
        "maps_body": "📍 Your last search was ({p})\n\nI've lined up the closest stores around you. Tap the button to open the map 👇",
        "maps_btn": "📍 Open Map",
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

【الحالة 2】طلب عام بدون براند محدد (مثل: قهوة فلات وايت حار، عطر رجالي، لابتوب للدراسة، سماعات للجيم، برجر):
لا تبحث عن الأرخص! ابحث عن الأفضل تقييماً في الكويت بسعر مناسب (أفضل قيمة مقابل السعر).
اعتمد على تقييمات Google والمراجعات الفعلية، ورد بهذا الشكل فقط:
📦 [وصف الطلب]

🏆 [اسم الخيار الأفضل + مكانه/متجره] — [السعر] د.ك ⭐ [التقييم من 5]
• [خيار ثاني قوي] — [السعر] د.ك ⭐ [التقييم من 5]
• [خيار ثالث] — [السعر] د.ك ⭐ [التقييم من 5]
ثم سطر واحد قصير يشرح ليش الخيار الأول هو الأفضل (تقييم عالي + سعر مناسب).

【الحالة 3】طلب خدمة (فني، بنشر، تبديل بطارية، سباك، كهربائي، تنظيف، صالون، توصيل، ونش...):
ابحث عن أفضل مزودي الخدمة تقييماً في المنطقة المطلوبة، ورد بهذا الشكل فقط:
📦 [وصف الخدمة + المنطقة]

🏆 [اسم المزود] (هاتف: [الرقم]) — [المنطقة] — [السعر التقريبي] د.ك ⭐ [التقييم من 5]
• [مزود ثاني] (هاتف: [الرقم]) — [المنطقة] — [السعر] د.ك ⭐ [التقييم]
• [مزود ثالث] (هاتف: [الرقم]) — [المنطقة] — [السعر] د.ك ⭐ [التقييم]
ثم سطر واحد قصير عن ميزة الخيار الأول (سرعة، خدمة 24 ساعة، كفالة...).
⛔ قاعدة صارمة جداً للأرقام: لا تكتب أي رقم هاتف إلا إذا ظهر الرقم حرفياً في نتائج بحث Google. ممنوع منعاً باتاً تأليف أو تخمين أي رقم. إذا ما لقيت رقم المزود في نتائج البحث اكتب مكانه (الرقم بالرابط) فقط. رقم غلط أسوأ ألف مرة من عدم وجود رقم.

في كل الحالات، سطر أخير إلزامي:
LINKS: اسم الأول=الدومين الحقيقي, اسم الثاني=الدومين الحقيقي, اسم الثالث=الدومين الحقيقي
مثال: LINKS: إكسايت=xcite.com, بلينك=blink.com.kw, يوريكا=eureka.com.kw
لا تخمّن الدومين، ولا تذكر متجراً أو خياراً من دون مصدر بحث.
ممنوع روابط ظاهرة. ممنوع Markdown.

لغة الرد: التزم بلغة الرد المطلوبة في رسالة المستخدم (عربي أو إنجليزي) مع الحفاظ على نفس التنسيق تماماً.

إذا كان المنتج عقاراً أو سيارة، أعطِ تقييماً متوسطاً ونطاق سعر مختصراً جداً.
"""

def get_final_url(url: str):
    if not url or not url.startswith(("http://", "https://")): return ""
    try:
        r = requests.get(url, allow_redirects=True, timeout=12, stream=True, headers=HEADERS)
        final = r.url or url
        r.close()
        return final if final.startswith(("http://", "https://")) else url
    except Exception as e:
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

def extract_store_names(text):
    stores = []
    for line in (text or "").splitlines():
        # المتاجر تبدأ بـ 🏪 في السلة أو ✅ أو 🏆 أو • في المنتج الواحد
        m = re.match(r"^\s*🏪\s*(.+?)\s*(?:\(|$)", line)
        if m:
            name = m.group(1).strip()
            name = re.sub(r"أفضل متجر واحد.*?:", "", name).strip()
            if name and name not in stores:
                stores.append(name)
            continue
        m = re.match(r"^\s*(?:✅|🏆|•)\s*(.+?)\s*(?:—|–|-)\s*[\d.,]+", line)
        if m:
            name = m.group(1).strip()
            if name and name not in stores:
                stores.append(name)
    return stores[:5]

def source_label(title, url):
    title = (title or "").strip()
    if title: return title[:40]
    try:
        host = urllib.parse.urlparse(url).netloc.replace("www.", "")
        return host.split(".")[0] or "المتجر"
    except Exception: return "المتجر"

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
        if r.status_code >= 400: return "", {}

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

SEARCH_RUNS = int(os.environ.get("SEARCH_RUNS", "4"))

def answer_score(txt, urls):
    stores, links = result_quality(txt, urls)
    score = stores * 2 + links * 3
    if txt and "📦" in txt: score += 1
    return score

def best_of_search(parts, lang, system_prompt=SYSTEM_PROMPT):
    """بطولة داخلية: SEARCH_RUNS بحوث متوازية لنفس الطلب، نقيّمها كلها ونرسل الأقوى."""
    try:
        futs = [SEARCH_POOL.submit(call_gemini, parts, system=system_prompt) for _ in range(SEARCH_RUNS)]
        results = [f.result() for f in futs]
    except Exception as e:
        print(f"best_of_search err {e}")
        return call_gemini(parts, system=system_prompt)

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

    print({"tournament": [answer_score(t, u) for t, u in scored], "winner_stores": result_quality(best_txt, best_urls)[0], "total_links": len(merged_urls)})
    return best_txt, merged_urls

def search_product(query, lang):
    cached = cache_get(query, lang)
    if cached: return cached

    txt, urls = best_of_search([{"text": f"ابحث عن {query} في الكويت. {LANG_INSTR[lang]}"}], lang)
    stores, links = result_quality(txt, urls)

    if stores >= CACHE_MIN_STORES and links >= CACHE_MIN_LINKS:
        cache_put(query, lang, txt, urls)
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
        return r.ok
    except: return False

def send_whatsapp_cta(to,body,link,bot_id,title):
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    payload={"messaging_product":"whatsapp","to":to,"type":"interactive","interactive":{"type":"cta_url","body":{"text":body[:1024]},"action":{"name":"cta_url","parameters":{"display_text":title[:20],"url":link}}}}
    try:
        r = requests.post(url,json=payload,headers=h,timeout=15)
        return r.ok
    except: return False

def send_whatsapp_location_request(to, body, bot_id):
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    payload={"messaging_product":"whatsapp","to":to,"type":"interactive","interactive":{"type":"location_request_message","body":{"text":body[:1024]},"action":{"name":"send_location"}}}
    try:
        r = requests.post(url,json=payload,headers=h,timeout=15)
        return r.ok
    except: return False

def send_whatsapp_buttons(to, body, buttons, bot_id):
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    btns=[{"type":"reply","reply":{"id":b["id"],"title":b["title"][:20]}} for b in buttons[:3]]
    payload={"messaging_product":"whatsapp","to":to,"type":"interactive","interactive":{"type":"button","body":{"text":body[:1024]},"action":{"buttons":btns}}}
    try:
        r = requests.post(url,json=payload,headers=h,timeout=15)
        return r.ok
    except: return False

def send_language_choice(to, bot_id):
    body = "🌐 اختر لغتك المفضلة\nChoose your preferred language"
    send_whatsapp_buttons(to, body, [
        {"id": "lang_ar", "title": "العربية 🇰🇼"},
        {"id": "lang_en", "title": "English 🇬🇧"},
    ], bot_id)

def send_whatsapp_contacts(to, contacts, bot_id):
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    payload={"messaging_product":"whatsapp","to":to,"type":"contacts","contacts":contacts}
    try:
        r = requests.post(url,json=payload,headers=h,timeout=15)
        return r.ok
    except: return False

def extract_service_contacts(txt):
    contacts=[]
    for line in (txt or "").splitlines():
        m=re.match(r"^\s*(?:🏆|•)\s*(.+?)\s*\(\s*(?:هاتف|Phone|phone|Tel|tel)\s*:\s*([\d\s\-]+)\)",line)
        if not m: continue
        name=m.group(1).strip()[:25]
        num=re.sub(r"\D","",m.group(2))
        if len(num)==8 and num[0] in "2569":
            contacts.append({
                "name":{"formatted_name":name,"first_name":name},
                "phones":[{"phone":f"+965{num}","type":"WORK","wa_id":f"965{num}"}]
            })
        if len(contacts)==3: break
    return contacts

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
    send_whatsapp_text(from_number,T(lang,"identifying"),bot_id)
    b64,mime=download_whatsapp_media(message["image"]["id"])

    ident,_=call_gemini([{"inline_data":{"mime_type":mime,"data":b64}},{"text":"ما اسم هذا المنتج؟"}], system=IDENTIFY_SYSTEM, use_search=False)
    product_name = ident.strip().splitlines()[0].strip() if ident else ""

    if product_name:
        txt,urls=search_product(product_name, lang)
    else:
        txt,urls=best_of_search([{"inline_data":{"mime_type":mime,"data":b64}},{"text":f"ما هذا المنتج؟ ابحث عن سعره الحالي في الكويت. {LANG_INSTR[lang]}"}], lang)
        name_m = re.search(r"📦\s*(.+)", txt or "")
        product_name = name_m.group(1).strip() if name_m else "المنتج"

    if not txt: txt=T(lang,"cant_identify")
    send_whatsapp_text(from_number,txt,bot_id)

    LAST_SEARCH[from_number] = {"product": product_name or "المنتج"}

    sent_any=False
    for n,u in urls.items():
        if u:
            send_whatsapp_cta(from_number,T(lang,"shop_from",n=n),u,bot_id,f"🛒 {n[:18]}")
            sent_any=True
    if not sent_any and txt and product_name and product_name != "المنتج":
        stores=extract_store_names(txt)
        target=stores[0] if stores else product_name
        send_whatsapp_cta(from_number,T(lang,"shop_from",n=target),fallback_search_url(f"{product_name} {target}" if stores else product_name),bot_id,f"🛒 {target[:18]}")

    if product_name and product_name != "المنتج":
        send_whatsapp_location_request(from_number, T(lang,"location_prompt"), bot_id)

def identify_image_product(msg):
    try:
        b64,mime=download_whatsapp_media(msg["image"]["id"])
        ident,_=call_gemini([{"inline_data":{"mime_type":mime,"data":b64}},{"text":"ما اسم هذا المنتج؟"}], system=IDENTIFY_SYSTEM, use_search=False)
        return ident.strip().splitlines()[0].strip() if ident else ""
    except: return ""

def process_cart(products, from_number, bot_id, lang="ar"):
    """السلة الذكية: تبحث عن المنتجات وتجمعها، وترسل أزراراً للمتاجر المعنية"""
    cart_query = "cart:" + "،".join(sorted(p.strip() for p in products if p.strip()))

    cached = cache_get(cart_query, lang)
    if cached:
        txt, urls = cached
    else:
        listing = "\n".join(f"- {p}" for p in products)
        parts = [{"text": f"سلة المنتجات:\n{listing}\n\nنظمها في متاجر كما هو مطلوب. {LANG_INSTR[lang]}"}]
        
        # استخدام بطولة البحث للسلة لضمان أقوى وأدق إجابة للأسعار
        txt, urls = best_of_search(parts, lang, system_prompt=CART_SYSTEM)
        
        stores, links = result_quality(txt, urls)
        if txt and links > 0:
            cache_put(cart_query, lang, txt, urls)

    if not txt:
        send_whatsapp_text(from_number, T(lang,"not_found"), bot_id)
        return

    # إرسال رسالة السلة (النصية)
    send_whatsapp_text(from_number, txt, bot_id)
    LAST_SEARCH[from_number] = {"product": products[0]}

    # إرسال أزرار مستقلة لكل متجر ظهر في السلة
    sent_any = False
    for store_name, store_url in urls.items():
        if store_url:
            send_whatsapp_cta(
                from_number, 
                T(lang, "shop_from", n=store_name), 
                store_url, 
                bot_id, 
                f"🛒 {store_name[:18]}"
            )
            sent_any = True
            
    # كفالة احتياطية: إذا لم يتمكن من جلب روابط مباشرة، يرسل زر بحث جوجل لأول متجر
    if not sent_any:
        stores = extract_store_names(txt)
        fallback_target = stores[0] if stores else "أفضل المتاجر"
        search_query = f"{' '.join(products[:2])} {fallback_target}"
        send_whatsapp_cta(
            from_number, 
            T(lang, "shop_from", n=fallback_target), 
            fallback_search_url(search_query), 
            bot_id, 
            f"🛒 {fallback_target[:18]}"
        )

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
        send_language_choice(from_number, bot_id)
        return

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
        send_whatsapp_text(from_number,txt or T(lang,"not_found"),bot_id)
        
        LAST_SEARCH[from_number] = {"product": products[0]}

        contacts = extract_service_contacts(txt)
        if contacts: send_whatsapp_contacts(from_number, contacts, bot_id)
            
        sent_any=False
        for n,u in urls.items():
            if u:
                send_whatsapp_cta(from_number,T(lang,"shop_from",n=n),u,bot_id,f"🛒 {n[:18]}")
                sent_any=True
        if not sent_any and txt:
            stores=extract_store_names(txt)
            target=stores[0] if stores else products[0]
            send_whatsapp_cta(from_number,T(lang,"shop_from",n=target),fallback_search_url(f"{products[0]} {target}" if stores else products[0]),bot_id,f"🛒 {target[:18]}")

        send_whatsapp_location_request(from_number, T(lang,"location_prompt"), bot_id)
            
    else:
        send_whatsapp_text(from_number,T(lang,"multi_text",c=len(products)),bot_id)
        process_cart(products, from_number, bot_id, lang)

def process_location_message(message, bot_id):
    from_number = message["from"]
    lat = message["location"]["latitude"]
    lng = message["location"]["longitude"]
    lang = USER_LANG.get(from_number, "ar")

    last_search = LAST_SEARCH.get(from_number)
    if not last_search or not last_search.get("product"):
        send_whatsapp_text(from_number, T(lang,"no_saved_product"), bot_id)
        return

    product = last_search["product"]
    
    prompt_category = """أنت خبير تسوق في السوق الكويتي. 
بناءً على اسم المنتج، أعطني "عبارة بحث" (Search Term) دقيقة جداً لخرائط جوجل تجلب المتاجر الصحيحة وتستبعد العشوائية.

قواعد هامة:
- للإلكترونيات الذكية (ساعة أبل، جوالات، لابتوب): اكتب أسماء الوكلاء الموثوقين هكذا (Xcite OR Eureka OR Best Al Yousifi) ولا تكتب "محل الكترونيات" أبداً.
- للأجهزة المنزلية (ثلاجة، غسالة): (Xcite OR Eureka).
- للأدوية والمكملات: (صيدلية Pharmacy).
- للمواد الغذائية واللحوم: (جمعية تعاونية Supermarket).
- لألعاب الفيديو: (محل العاب فيديو Video games).
- للكهربائيات الثقيلة والإضاءة: (مواد كهربائية Electrical supply).
- للملابس والمعدات الرياضية (مثل مضارب التنس والبادل): (Intersport OR Go Sport OR محلات رياضية).
- للطلبات العامة (قهوة، مطاعم، عطور): اكتب نوع المكان مع كلمة "الأعلى تقييماً" مثل (كافيه specialty coffee) أو (محل عطور perfume shop).
- إذا لم تكن متأكداً، اكتب اسم المنتج نفسه.

أعطني عبارة البحث فقط بدون أي إضافات أو شرح."""

    category_text, _ = call_gemini([{"text": f"المنتج: {product}"}], system=prompt_category)
    category = category_text.strip() if category_text else product

    safe_category = urllib.parse.quote(category)
    maps_url = f"https://www.google.com/maps/search/{safe_category}/@{lat},{lng},15z"
    
    body = T(lang,"maps_body",p=product)
    send_whatsapp_cta(from_number, body, maps_url, bot_id, T(lang,"maps_btn"))

@app.get("/")
async def health(): return {"status":"v23 Smart Cart with Best-of-4 Tournament"}
