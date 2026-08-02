# -*- coding: utf-8 -*-
# النسخة الاقتصادية: 1-2 مكالمة Gemini بدل 15-25
# الوفر المتوقع: 85-90% من التكلفة الحالية

import os, re, time, base64, requests, json, asyncio, urllib.parse, hashlib
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Request, Response, BackgroundTasks
from bs4 import BeautifulSoup

app = FastAPI()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_LITE  = os.environ.get("GEMINI_LITE_MODEL", "gemini-2.0-flash-lite")  # للمهام البسيطة
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_COOP_BOT_TOKEN")
VISION_API_KEY = os.environ.get("GOOGLE_VISION_API_KEY", "")

GRAPH_URL = "https://graph.facebook.com/v20.0"
GEMINI_URL_TPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
VISION_URL = "https://vision.googleapis.com/v1/images:annotate"

processed_ids = deque(maxlen=1000)
IMAGE_BUFFER = defaultdict(lambda: {"images": [], "time": 0, "bot_id": ""})
LAST_SEARCH = {}
USER_LANG = {}
PENDING_IMAGES = defaultdict(lambda: {"images": [], "bot_id": ""})

BUFFER_SECONDS = 4
RESOLVER = ThreadPoolExecutor(max_workers=8)
WORKERS  = ThreadPoolExecutor(max_workers=3)
HEADERS  = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

SEARCH_CACHE = {}
CACHE_TTL  = int(os.environ.get("CACHE_TTL_HOURS", "3")) * 3600  # 3 ساعات بدل 2
CACHE_MAX  = 800
TARGET_RESULTS = int(os.environ.get("TARGET_RESULTS", "4"))

VERIFIED_PAGE_CACHE = {}
OOS_PHRASES = ["out of stock","غير متوفر","نفدت الكمية","غير متاح","sold out","نفذت","not available","temporarily unavailable"]
LISTING_URL_PARTS = ["/search","/s?","/category","/categories","/collection","/collections","/shop/category","?q=","/search_results","/shop/","/listing","/c/"]

# ==================== أدوات مشتركة ====================

def format_price(p):
    try:
        pf = float(p)
        return f"{pf:.3f}".rstrip('0').rstrip('.') if pf < 100 else f"{pf:.2f}"
    except: return str(p)

def normalize_ar(text):
    t = (text or "").lower()
    t = re.sub(r"[أإآ]", "ا", t)
    t = t.replace("ة","ه").replace("ى","ي").replace("ئ","ي").replace("ؤ","و")
    return t

def normalize_name(v): return re.sub(r"[^\w\u0600-\u06FF]+","", (v or "").lower())
def clean_domain(dom):
    dom = re.sub(r"^https?://","", (dom or "").strip().lower())
    return dom.replace("www.","").split("/")[0]
def domain_key(dom): return clean_domain(dom).split(".")[0]

def norm_tokens(q):
    t = normalize_ar(q)
    toks = re.findall(r"[\w\u0600-\u06FF]+", t)
    return set(w[2:] if w.startswith("ال") and len(w)>4 else w for w in toks)

def has_model_token(a, b):
    def models(s): return {t for t in s if re.search(r"\d",t) and re.search(r"[a-z\u0600-\u06FF]",t) and len(t)>=4}
    return bool(models(a) & models(b))

def cache_key(query, lang):
    norm = re.sub(r"[^\w\u0600-\u06FF]+","", normalize_ar(query))
    return hashlib.sha256(f"{norm}|{lang}".encode()).hexdigest()

def cache_get(query, lang):
    now = time.time()
    hit = SEARCH_CACHE.get(cache_key(query, lang))
    if hit and (now - hit["ts"]) < CACHE_TTL:
        print(f"CACHE HIT: {query[:50]}")
        return hit["txt"], dict(hit["urls"])
    qt = norm_tokens(query)
    if not qt: return None
    best, best_score = None, 0.0
    for entry in SEARCH_CACHE.values():
        if entry.get("lang") != lang or (now - entry["ts"]) >= CACHE_TTL: continue
        et = entry.get("tokens") or set()
        if not et: continue
        score = len(qt & et) / len(qt | et) if (qt | et) else 0
        if has_model_token(qt, et): score += 0.30
        if score > best_score: best, best_score = entry, score
    if best and best_score >= 0.60:
        return best["txt"], dict(best["urls"])
    return None

def cache_put(query, lang, txt, urls):
    if not txt: return
    if len(SEARCH_CACHE) >= CACHE_MAX:
        SEARCH_CACHE.pop(min(SEARCH_CACHE, key=lambda k: SEARCH_CACHE[k]["ts"]), None)
    SEARCH_CACHE[cache_key(query, lang)] = {
        "txt": txt, "urls": dict(urls), "ts": time.time(),
        "tokens": norm_tokens(query), "query": query, "lang": lang,
    }

# ==================== Gemini — مكالمة وحدة لكل مهمة ====================

def call_gemini(parts, system, use_search=True, lite=False):
    """
    lite=True  → gemini-2.0-flash-lite  (أرخص 4x، للتعرف والترجمة والخرائط)
    lite=False → gemini-2.5-flash       (للبحث عن الأسعار فقط)
    """
    model = GEMINI_LITE if lite else GEMINI_MODEL
    url = GEMINI_URL_TPL.format(model=model)
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 2000},
    }
    if use_search and not lite:
        payload["tools"] = [{"google_search": {}}]
    try:
        r = requests.post(url, params={"key": GEMINI_API_KEY}, json=payload, timeout=90)
        if r.status_code >= 400:
            print(f"Gemini {r.status_code}: {r.text[:300]}")
            return "", {}
        data = r.json()
        candidates = data.get("candidates") or []
        if not candidates: return "", {}
        cand = candidates[0]
        text = "".join(p.get("text","") for p in cand.get("content",{}).get("parts",[])).strip()
        pairs = []
        m = re.search(r"(?im)^\s*LINKS\s*:\s*(.+)$", text)
        if m:
            for part in re.split(r"[,،]+", m.group(1)):
                part = part.strip()
                if "=" in part:
                    n, d = part.split("=",1)
                    n, d = n.strip(), clean_domain(d)
                    if n and "." in d: pairs.append((n, d))
            text = re.sub(r"(?im)^\s*LINKS\s*:.*$","", text).strip()
        text = re.sub(r"(?im)^\s*LINKS\s*:?\s*$","", text).strip()
        text = re.sub(r"https?://\S+","", text).replace("**","").strip()
        metadata = cand.get("groundingMetadata",{}) or {}
        chunks = metadata.get("groundingChunks",[]) or []
        uris = [(c.get("web") or {}).get("uri","") for c in chunks]
        finals = list(RESOLVER.map(get_final_url, uris[:15])) if uris else []
        records = []
        for i, chunk in enumerate(chunks[:15]):
            web = chunk.get("web") or {}
            raw = web.get("uri","")
            final = finals[i] if i < len(finals) else raw
            records.append({"title": web.get("title",""), "raw": raw, "url": final or raw})
        urls_map = {}
        used = set()
        stores = extract_store_names(text)
        supports = metadata.get("groundingSupports",[]) or []
        for store in stores:
            sn = normalize_name(store)
            for sup in supports:
                seg = (sup.get("segment") or {}).get("text","")
                if sn and sn in normalize_name(seg):
                    for idx in sup.get("groundingChunkIndices",[]) or []:
                        if 0 <= idx < len(records):
                            u = records[idx]["url"]
                            if u and u not in used:
                                urls_map[store] = u; used.add(u); break
                if store in urls_map: break
        for name, dom in pairs:
            if name in urls_map: continue
            key = domain_key(dom)
            for rec in records:
                hay = f"{rec['title']} {rec['raw']} {rec['url']}".lower()
                if rec["url"] and key and key in hay and rec["url"] not in used:
                    urls_map[name] = rec["url"]; used.add(rec["url"]); break
        for store in stores:
            if store in urls_map: continue
            sn = normalize_name(store)
            for rec in records:
                if rec["url"] and sn and sn in normalize_name(rec["title"]) and rec["url"] not in used:
                    urls_map[store] = rec["url"]; used.add(rec["url"]); break
        for store in stores:
            if store in urls_map: continue
            dom = store_domain(store)
            if not dom: continue
            key = domain_key(dom)
            for rec in records:
                hay = f"{rec['title']} {rec['raw']} {rec['url']}".lower()
                if rec["url"] and key and key in hay and rec["url"] not in used:
                    urls_map[store] = rec["url"]; used.add(rec["url"]); break
        return text, dict(list(urls_map.items())[:8])
    except Exception as e:
        print(f"Gemini err: {e}"); return "", {}

# ==================== Google Lens (Vision API) ====================

def google_lens_search(b64):
    if not VISION_API_KEY: return None
    payload = {"requests": [{"image": {"content": b64}, "features": [{"type":"WEB_DETECTION","maxResults":20}]}]}
    try:
        r = requests.post(f"{VISION_URL}?key={VISION_API_KEY}", json=payload, timeout=15)
        if not r.ok: return None
        ann = r.json()["responses"][0].get("webDetection", {})
        labels = [e["label"] for e in ann.get("bestGuessLabels", [])]
        pages  = [p["url"] for p in ann.get("pagesWithMatchingImages", []) if p.get("url")]
        print(f"LENS: {labels[0] if labels else 'none'} | {len(pages)} pages")
        return {"product_en": labels[0] if labels else "", "page_urls": pages[:15]}
    except Exception as e:
        print(f"Vision err: {e}"); return None

# ==================== التحقق من الصفحات ====================

def get_final_url(url):
    if not url or not url.startswith(("http://","https://")): return ""
    try:
        r = requests.get(url, allow_redirects=True, timeout=10, stream=True, headers=HEADERS)
        final = r.url or url; r.close()
        return final if final.startswith(("http://","https://")) else url
    except: return url

def resolve_all(uris): return list(RESOLVER.map(get_final_url, uris))

def fetch_html(url):
    if not url or not url.startswith("http"): return ""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200 and len(r.text) > 1500: return r.text
    except: pass
    return ""

def parse_product_data(html, url):
    if not html: return None
    soup = BeautifulSoup(html, "lxml")
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
                if isinstance(o, dict) and o.get("@graph"): flat.extend(o["@graph"])
                else: flat.append(o)
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
                    if "outofstock" in av or "soldout" in av: data["available"] = False
                    if not data["title"]:
                        data["title"] = str(obj.get("name",""))[:80]
                        b = obj.get("brand")
                        if isinstance(b, dict): b = b.get("name","")
                        b = str(b or "").strip()
                        if b and b.lower() not in data["title"].lower():
                            data["title"] = f"{b} {data['title']}"[:100]
        except: continue
    if ld_products >= 4: data["is_product"] = False
    low = soup.get_text(" ", strip=True).lower()[:6000]
    if any(ph in low for ph in OOS_PHRASES):
        if low.count("غير متوفر") > 0 or low.count("out of stock") > 0:
            data["available"] = False
    if not data["price"]:
        m = soup.find("meta", property="product:price:amount")
        if m and m.get("content"):
            try: data["price"] = float(m["content"])
            except: pass
    ul = url.lower()
    if any(p in ul for p in LISTING_URL_PARTS):
        if not re.search(r"/product/|/products/[^/]{3,}|/p/|/dp/|/item/|/prod/", ul):
            if ld_products != 1: data["is_product"] = False
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
            if info: VERIFIED_PAGE_CACHE[url] = {"data": info, "ts": time.time()}
        if not info: return None
        if not info["is_product"]: print(f"REJECT LIST: {name}"); return None
        if not info["available"]: print(f"REJECT OOS: {name}"); return None
        if not info["price"] or info["price"] <= 0: print(f"REJECT NO PRICE: {name}"); return None
        return (name, url, info)
    for r in RESOLVER.map(_check, urls_map.items()):
        if r:
            name, url, info = r
            verified[name] = {"url": url, "price": info["price"], "title": info["title"]}
    return verified

# ==================== قاموس المتاجر ====================

STORE_DOMAINS = {
    "اليوسفي":"best.com.kw","بستاليوسفي":"best.com.kw","اكسايت":"xcite.com","الغانم":"xcite.com",
    "نون":"noon.com","بلينك":"blink.com.kw","يوريكا":"eureka.com.kw","جرير":"jarir.com",
    "كارفور":"carrefourkuwait.com","لولو":"luluhypermarket.com","امازون":"amazon.ae",
    "طلبات":"talabat.com","ديليفرو":"deliveroo.com.kw","بوتيكات":"boutiqaat.com",
    "توصيل":"taw9eel.com","تريكارت":"trikart.com","يوباي":"ubuy.com.kw",
    "مطاحن":"kuwaitflourmills.com","ويبي":"wibi.com.kw",
}
DOMAIN_DISPLAY = {
    "luluhypermarket":"لولو هايبرماركت","xcite":"إكسايت","best":"اليوسفي","noon":"نون",
    "blink":"بلينك","eureka":"يوريكا","jarir":"جرير","carrefourkuwait":"كارفور",
    "taw9eel":"توصيل Taw9eel","talabat":"طلبات","trikart":"تريكارت","ubuy":"يوباي",
    "desertcart":"ديزرت كارت","amazon":"أمازون","boutiqaat":"بوتيكات","wibi":"ويبي",
    "kuwaitflourmills":"مطاحن الكويت","deliveroo":"ديليفرو",
}
def store_domain(name):
    n = normalize_name(normalize_ar(name))
    for k,d in STORE_DOMAINS.items():
        if k in n or n in k: return d
    return ""
JUNK_STORE = re.compile(r"^(delivery|اونلاين|أونلاين|online|الموقعالرسمي|official)", re.I)
def is_junk_store(name): return bool(JUNK_STORE.match(normalize_name(normalize_ar(name))))
def is_placeholder_name(name):
    x = normalize_name(normalize_ar(name))
    if not x: return True
    if x.startswith("اسمال") or x.startswith("المتجرال"): return True
    return x in {"اسم","المتجر","متجر","الاول","الثاني","الثالث","storename","store","name"}
def url_host_key(url):
    try: host = urllib.parse.urlparse(url).netloc.replace("www.","").lower()
    except: return ""
    for k in DOMAIN_DISPLAY:
        if k in host: return k
    parts = host.split(".")
    return parts[-2] if len(parts) >= 2 else (parts[0] if parts else "")
def display_store_name(name, url):
    host = url_host_key(url)
    if not name or is_placeholder_name(name) or is_junk_store(name):
        return DOMAIN_DISPLAY.get(host, host.capitalize() if host else "المتجر")
    return name
def short_query(q):
    q = re.sub(r"\([^)]*\)"," ", q or "")
    q = re.split(r"\s+[-—–]\s+", q)[0]
    return " ".join(q.split()[:6]).strip()

# ==================== Prompts ====================

SYSTEM_PROMPT = """
أنت مساعد تسوق كويتي. استخدم بحث Google فعلياً للأسعار الحالية في الكويت.

【الحالة 1】منتج محدد:
📦 [اسم المنتج]
✅ [المتجر الأرخص] — [السعر] د.ك
• [متاجر أخرى] — [السعر] د.ك
(اذكر حتى 6 متاجر مختلفة إن وجدت. متوفر InStock فقط. رابط صفحة منتج مباشر فقط)
ClicFlyer إلزامي لمنتجات البقالة والتموينات.

【الحالة 2】طلب عام بدون براند:
📦 [وصف] — الأفضل تقييماً
🏆 [الخيار الأول] — [السعر] د.ك ⭐ [التقييم]
• [خيارات أخرى]

【الحالة 3】خدمة:
📦 [الخدمة + المنطقة]
🏆 [مزود] (هاتف: [رقم حقيقي من البحث فقط]) — [سعر] ⭐ [تقييم]

【الحالة 4】سؤال معلوماتي: أجب مباشرة.

سطر LINKS إلزامي في 1-2-3: LINKS: إكسايت=xcite.com, نون=noon.com
ممنوع روابط ظاهرة. ممنوع Markdown.
"""

IDENTIFY_SYSTEM = """أنت محرك بحث بصري. انظر للصورة وأعطني:
سطر 1 عربي: [براند] [نوع المنتج الدقيق] [موديل إن ظهر] [لون] [حجم]
سطر 2 إنجليزي: نفسه للبحث
⚠️ فرّق: mules≠sneakers، بخاخ≠رول أون، ساعة الترا 3≠الترا 2
سطران فقط."""

MAPS_SYSTEM = """أعطني عبارة بحث دقيقة لخرائط جوجل:
إلكترونيات: (Xcite OR Eureka OR Best Al Yousifi)
أدوية: (صيدلية Pharmacy)
غذاء: (جمعية تعاونية Supermarket)
خدمات: نوع الخدمة عربي+إنجليزي
سطر واحد فقط."""

LANG_INSTR = {
    "ar": "رد باللغة العربية فقط.",
    "en": "Respond ONLY in English. Keep prices in KWD.",
}

# ==================== رسائل البوت ====================

MSG = {
    "ar": {
        "identifying": "ثواني بس.. أحدد المنتج وأدور لك الأفضل!",
        "searching": "🔍 أدور لك على {q}...",
        "not_found": "ما لقيت المنتج متوفر حالياً 😅 جرب صياغة ثانية.",
        "cant_identify": "ما قدرت أحدد المنتج، دز صورة أوضح",
        "multi_text": "تمام لقيت {c} منتجات، أسوي سلة...",
        "multi_images": "تمام لقطت {c} منتجات، أسوي سلة...",
        "maps_body": "📍 تبي أقرب مكان؟ اضغط الزر والخريطة بتفتح على أقرب الأماكن حولك 👇",
        "maps_btn": "📍 افتح الخريطة",
        "maps_body_loc": "📍 ({p}) — جهزت لك أقرب الأماكن حولك 👇",
        "no_saved_product": "ما عندي منتج محفوظ، ابحث عن منتج أول!",
        "lang_saved": "تمام، بكلمك عربي 🇰🇼 دز صورة منتج أو اكتب اسمه!",
        "approx_note": "(~ سعر تقريبي غير مؤكد)",
        "alt_ask": "😕 هذا المنتج غير متوفر حالياً.\n\nتبي أدور لك أقرب بديل؟ 👇",
        "alt_yes_btn": "نعم دور بديل ✅",
        "alt_no_btn": "لا شكراً",
        "alt_searching": "🔍 أدور لك أقرب بديل...",
        "alt_found": "🔁 هذا أقرب بديل متوفر:",
        "alt_ok": "تمام 👍",
    },
    "en": {
        "identifying": "One sec.. identifying and finding the best deal!",
        "searching": "🔍 Looking up {q}...",
        "not_found": "Couldn't find it in-stock 😅 try another phrasing.",
        "cant_identify": "Couldn't identify the product, try a clearer photo",
        "multi_text": "Got it, found {c} products. Building your cart...",
        "multi_images": "Nice, spotted {c} products. Building your cart...",
        "maps_body": "📍 Want the nearest place? Tap the button and the map opens 👇",
        "maps_btn": "📍 Open Map",
        "maps_body_loc": "📍 ({p}) — closest places around you 👇",
        "no_saved_product": "No saved product yet — search first!",
        "lang_saved": "Great, English from now on 🇬🇧 Send a photo or product name!",
        "approx_note": "(~ approximate price, unverified)",
        "alt_ask": "😕 This product isn't currently available.\n\nWant me to find the closest alternative? 👇",
        "alt_yes_btn": "Yes, find one ✅",
        "alt_no_btn": "No thanks",
        "alt_searching": "🔍 Looking for the closest alternative...",
        "alt_found": "🔁 Here's the closest available alternative:",
        "alt_ok": "Got it 👍",
    },
}
PENDING_ALT = {}

def T(lang, key, **kw):
    return MSG.get(lang, MSG["ar"])[key].format(**kw) if kw else MSG.get(lang, MSG["ar"])[key]
def detect_lang(text):
    if re.search(r"[\u0600-\u06FF]", text or ""): return "ar"
    if re.search(r"[A-Za-z]", text or ""): return "en"
    return None

# ==================== استخراج البيانات من النص ====================

def extract_store_names(text):
    stores = []
    for line in (text or "").splitlines():
        m = re.match(r"^\s*(?:✅|🏆|•)\s*(.+?)\s*(?:—|–|-)\s*[\d.,]+", line.strip())
        if m:
            name = m.group(1).strip()
            if name and name not in stores: stores.append(name)
    return stores[:8]

def extract_store_offers(txt):
    offers = []
    for line in (txt or "").splitlines():
        s = line.strip()
        m = re.match(r"^(✅|🏆|•)\s*(.+?)\s*(?:—|–|-)\s*[\d.,]+", s)
        if not m: continue
        if re.search(r"\(\s*(?:هاتف|Phone|phone|Tel|tel)\s*:", s): continue
        offers.append({"line": s if m.group(1) in ("✅","🏆") else s.lstrip("•").strip(),
                        "name": m.group(2).strip(), "best": m.group(1) in ("✅","🏆")})
    return offers[:8]

def is_service_answer(txt):
    return bool(re.search(r"(?:🏆|•)\s*.+?\(\s*(?:هاتف|Phone|phone|Tel|tel)\s*:", txt or ""))

UNAVAIL_RX = re.compile(r"(غير متوفر|غير متاح|لم أجد|لم اجد|ما لقيت|لا يتوفر|not available|couldn't find|out of stock|no stock)", re.I)
def is_unavailable_answer(txt):
    return bool(txt) and not extract_store_offers(txt) and bool(UNAVAIL_RX.search(txt))

def product_title(txt, fallback=""):
    m = re.search(r"^\s*📦\s*(.+)$", txt or "", flags=re.M)
    if m: return f"📦 {m.group(1).strip()}"
    return f"📦 {fallback}" if fallback else ""

def match_url(name, urls):
    if not urls: return ""
    if name in urls: return urls[name]
    nn = normalize_name(name)
    for k,v in urls.items():
        kk = normalize_name(k)
        if nn and kk and (nn in kk or kk in nn): return v
    dom = store_domain(name)
    if dom:
        key = domain_key(dom)
        for k,v in urls.items():
            if key and (key in (v or "").lower() or key in normalize_name(k)): return v
    return ""

def fallback_search_url(query, store=""):
    dom = store_domain(store) if store else ""
    if dom: return "https://www.google.com/search?q=" + urllib.parse.quote(f"site:{dom} {query}")
    q = f"{query} {store} الكويت".strip() if store else f"{query} الكويت"
    return "https://www.google.com/search?q=" + urllib.parse.quote(q)

def result_quality(txt, urls):
    return len(extract_store_names(txt or "")), len(urls or {})

# ==================== البحث الرئيسي — مكالمة وحدة ====================

def search_product(query, lang, prompt_text=None):
    """
    مكالمة Gemini وحدة مع Google Search — بدل 6-8 مكالمات.
    الكاش يمنع تكرار البحث لنفس المنتج.
    """
    cached = cache_get(query, lang)
    if cached: return cached

    prompt = prompt_text or (
        f"ابحث عن {query} في الكويت. متوفر InStock فقط. رابط منتج مباشر. "
        f"اذكر حتى 6 متاجر مختلفة (Xcite, Eureka, Blink, Noon, Jarir, Lulu, Carrefour, Amazon, Best Al-Yousifi). "
        f"{LANG_INSTR[lang]}"
    )

    txt, urls = call_gemini([{"text": prompt}], system=SYSTEM_PROMPT, use_search=True, lite=False)
    if not txt: return "", {}

    # خدمة أو معلوماتي: احفظ وأرجع مباشرة
    if is_service_answer(txt) or not extract_store_offers(txt):
        if len(txt) >= 80: cache_put(query, lang, txt, urls)
        return txt, urls

    # تحقق من الأسعار والتوفر
    verified = verify_offers(urls, query)

    # جولة استكمال واحدة إذا أقل من TARGET_RESULTS
    if len(verified) < TARGET_RESULTS and urls:
        exclude = "، ".join(list(urls.keys())[:8])
        extra = call_gemini([{"text":
            f"ابحث عن {query} في الكويت في متاجر مختلفة عن ({exclude}). "
            f"InStock فقط. رابط صفحة منتج مباشر. حتى 5 متاجر. {LANG_INSTR[lang]}"
        }], system=SYSTEM_PROMPT, use_search=True, lite=False)
        if extra[1]:
            have = {v["url"] for v in verified.values()} | set(urls.values())
            pool = {n:u for n,u in extra[1].items() if u and u not in have}
            if pool:
                more = verify_offers(pool, query)
                for n,info in more.items():
                    if n not in verified and info["url"] not in {v["url"] for v in verified.values()}:
                        verified[n] = info

    if verified:
        cur = "د.ك" if lang == "ar" else "KWD"
        # دمج التكرار لكل دومين
        by_dom = {}
        for name, info in verified.items():
            dom = url_host_key(info["url"]) or info["url"]
            if dom not in by_dom or info["price"] < by_dom[dom][1]["price"]:
                by_dom[dom] = (name, info)
        sorted_v = sorted(by_dom.values(), key=lambda x: x[1]["price"])[:TARGET_RESULTS]
        title = product_title(txt, query)
        lines = [title, ""]
        new_urls = {}
        for i, (name, info) in enumerate(sorted_v):
            disp = display_store_name(name, info["url"])
            if disp in new_urls: disp = f"{disp} 2"
            lines.append(f"{'✅' if i==0 else '•'} {disp} — {format_price(info['price'])} {cur}")
            new_urls[disp] = info["url"]
        # تكملة تقريبية
        need = TARGET_RESULTS - len(sorted_v)
        approx = []
        if need > 0:
            seen = {normalize_name(normalize_ar(n)) for n in new_urls}
            for o in extract_store_offers(txt):
                if is_placeholder_name(o["name"]) or is_junk_store(o["name"]): continue
                nn = normalize_name(normalize_ar(o["name"]))
                if not nn or any((nn in s or s in nn) for s in seen if s): continue
                line = re.sub(r"^\s*(?:✅|🏆)\s*","", o["line"])
                line = re.sub(r"(\d+(?:\.\d+)?)(\s*(?:د\.?\s*ك|KWD|KD))", r"~\1\2", line, count=1)
                approx.append(f"• {line}"); seen.add(nn)
                if len(approx) >= need: break
            if approx: lines.extend(["", *approx, T(lang,"approx_note")])
        final_txt = "\n".join(lines)
        cache_put(query, lang, final_txt, new_urls)
        return final_txt, new_urls
    else:
        # فشل التحقق: أرجع النص الخام بدون كاش
        return txt, urls

# ==================== معالجة الصور ====================

def parse_ident(ident):
    lines = [l.strip() for l in (ident or "").strip().splitlines() if l.strip()]
    if not lines: return "", ""
    ar = lines[0]; en = lines[1] if len(lines) > 1 else ""
    return ar, f"{ar} {en}".strip()

def translate_to_arabic(text_en):
    if not text_en: return ""
    # Flash Lite للترجمة السريعة — أرخص 4x
    txt, _ = call_gemini(
        [{"text": f"ترجم للعربي (سطر واحد: براند + نوع المنتج الدقيق): {text_en}"}],
        system="أجب بسطر عربي واحد فقط.",
        use_search=False, lite=True
    )
    return (txt or "").strip().splitlines()[0].strip() or text_en

def maps_search_url(product, lat=None, lng=None):
    # Flash Lite لتصنيف الخريطة — أرخص 4x
    cat_txt, _ = call_gemini([{"text": f"المنتج: {product}"}], system=MAPS_SYSTEM, use_search=False, lite=True)
    cat = cat_txt.strip().splitlines()[0].strip() if cat_txt else product
    safe = urllib.parse.quote(cat)
    if lat is not None and lng is not None:
        return f"https://www.google.com/maps/search/{safe}/@{lat},{lng},15z"
    return f"https://www.google.com/maps/search/{safe}"

def send_maps_button(from_number, product, bot_id, lang):
    url = maps_search_url(product)
    send_whatsapp_cta(from_number, T(lang,"maps_body"), url, bot_id, T(lang,"maps_btn"))

# ==================== عرض النتائج ====================

def offer_alternative(from_number, product, bot_id, lang):
    if (product or "").startswith("بديل "):
        send_whatsapp_text(from_number, T(lang,"not_found"), bot_id); return
    PENDING_ALT[from_number] = {"product": product}
    send_whatsapp_buttons(from_number, T(lang,"alt_ask"), [
        {"id":"alt_yes","title":T(lang,"alt_yes_btn")},
        {"id":"alt_no","title":T(lang,"alt_no_btn")},
    ], bot_id)

def run_alternative_search(from_number, product, bot_id, lang):
    send_whatsapp_text(from_number, T(lang,"alt_searching"), bot_id)
    alt_q = f"بديل {product}"
    prompt = (f"المنتج ({product}) غير متوفر في الكويت. "
              f"ابحث عن أقرب بديل متوفر InStock — نفس النوع والاستخدام. "
              f"رد بتنسيق المقارنة المعتاد. {LANG_INSTR[lang]}")
    txt, urls = search_product(alt_q, lang, prompt_text=prompt)
    if txt and extract_store_offers(txt):
        send_whatsapp_text(from_number, T(lang,"alt_found"), bot_id)
    LAST_SEARCH[from_number] = {"product": alt_q}
    need_map = send_product_result(from_number, txt, urls, bot_id, lang, alt_q)
    if need_map: send_maps_button(from_number, alt_q, bot_id, lang)

def send_product_result(from_number, txt, urls, bot_id, lang, query, best_only=False):
    if not txt:
        offer_alternative(from_number, query, bot_id, lang); return False
    if is_service_answer(txt):
        send_whatsapp_text(from_number, txt, bot_id); return True
    offers = extract_store_offers(txt)
    if not offers:
        if is_unavailable_answer(txt):
            offer_alternative(from_number, query, bot_id, lang); return False
        send_whatsapp_text(from_number, txt, bot_id); return False
    # الرسالة: اسم المنتج + سطور التقريب
    title = product_title(txt, query)
    approx_lines = [l.strip() for l in txt.splitlines() if "~" in l]
    head = title or f"📦 {query}"
    if approx_lines and not best_only: head += "\n\n" + "\n".join(approx_lines)
    send_whatsapp_text(from_number, head, bot_id)
    fq = short_query(title[2:].strip() if title.startswith("📦") else query)
    if best_only:
        best = next((o for o in offers if o["best"]), offers[0])
        offers = [best]
    for o in offers:
        url = match_url(o["name"], urls) or (None if is_junk_store(o["name"]) else fallback_search_url(fq, o["name"]))
        if not url: continue
        send_whatsapp_cta(from_number, o["line"], url, bot_id, f"🛒 {o['name'][:18]}")
    return True

# ==================== واتساب ====================

def download_whatsapp_media(mid):
    h={"Authorization":f"Bearer {WHATSAPP_TOKEN}"}
    meta=requests.get(f"{GRAPH_URL}/{mid}",headers=h,timeout=20).json()
    img=requests.get(meta["url"],headers=h,timeout=30)
    return base64.b64encode(img.content).decode(), meta.get("mime_type","image/jpeg")

def send_whatsapp_text(to,text,bot_id):
    url=f"{GRAPH_URL}/{bot_id}/messages"
    h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    payload={"messaging_product":"whatsapp","to":to,"type":"text","text":{"body":text[:3900]}}
    try: return requests.post(url,json=payload,headers=h,timeout=15).ok
    except: return False

def send_whatsapp_cta(to,body,link,bot_id,title):
    url=f"{GRAPH_URL}/{bot_id}/messages"
    h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    payload={"messaging_product":"whatsapp","to":to,"type":"interactive","interactive":{"type":"cta_url","body":{"text":body[:1024]},"action":{"name":"cta_url","parameters":{"display_text":title[:20],"url":link}}}}
    try: return requests.post(url,json=payload,headers=h,timeout=15).ok
    except: return False

def send_whatsapp_buttons(to, body, buttons, bot_id):
    url=f"{GRAPH_URL}/{bot_id}/messages"
    h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    btns=[{"type":"reply","reply":{"id":b["id"],"title":b["title"][:20]}} for b in buttons[:3]]
    payload={"messaging_product":"whatsapp","to":to,"type":"interactive","interactive":{"type":"button","body":{"text":body[:1024]},"action":{"buttons":btns}}}
    try: return requests.post(url,json=payload,headers=h,timeout=15).ok
    except: return False

def send_language_choice(to, bot_id):
    send_whatsapp_buttons(to, "🌐 اختر لغتك المفضلة\nChoose your preferred language", [
        {"id":"lang_ar","title":"العربية 🇰🇼"},{"id":"lang_en","title":"English 🇬🇧"}
    ], bot_id)

# ==================== Webhook ====================

@app.get("/webhook")
async def verify_wh(request: Request):
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
            caption=(msg.get("image",{}) or {}).get("caption","").strip()
            cap_lang=detect_lang(caption) if caption else None
            if cap_lang: USER_LANG[from_number]=cap_lang
            if from_number not in USER_LANG:
                pend=PENDING_IMAGES[from_number]; pend["images"].append(msg); pend["bot_id"]=bot_id
                if len(pend["images"])==1:
                    background_tasks.add_task(asyncio.to_thread, send_language_choice, from_number, bot_id)
            else:
                IMAGE_BUFFER[from_number]["images"].append(msg)
                IMAGE_BUFFER[from_number]["time"]=time.time()
                IMAGE_BUFFER[from_number]["bot_id"]=bot_id
                if len(IMAGE_BUFFER[from_number]["images"])==1:
                    background_tasks.add_task(process_image_buffer, from_number)
        elif msg.get("type")=="text":
            background_tasks.add_task(process_text_message, msg, bot_id)
        elif msg.get("type")=="interactive":
            background_tasks.add_task(process_interactive_message, msg, bot_id)
        elif msg.get("type")=="location":
            background_tasks.add_task(process_location_message, msg, bot_id)
    except Exception as e: print(f"webhook err {e}")
    return {"status":"ok"}

def process_interactive_message(message, bot_id):
    from_number=message["from"]
    reply=(message.get("interactive") or {}).get("button_reply") or {}
    btn_id=reply.get("id","")
    if btn_id in ("alt_yes","alt_no"):
        pend=PENDING_ALT.pop(from_number,None)
        lang=USER_LANG.get(from_number,"ar")
        if btn_id=="alt_no" or not pend:
            send_whatsapp_text(from_number,T(lang,"alt_ok"),bot_id); return
        run_alternative_search(from_number,pend["product"],bot_id,lang); return
    if btn_id not in ("lang_ar","lang_en"): return
    lang="ar" if btn_id=="lang_ar" else "en"
    USER_LANG[from_number]=lang
    pend=PENDING_IMAGES.pop(from_number,None)
    if pend and pend["images"]:
        if len(pend["images"])==1: process_single_image(pend["images"][0],pend["bot_id"],lang)
        else: process_multi_images(pend["images"],from_number,pend["bot_id"],lang)
    else: send_whatsapp_text(from_number,T(lang,"lang_saved"),bot_id)

async def process_image_buffer(from_number):
    await asyncio.sleep(BUFFER_SECONDS)
    data=IMAGE_BUFFER.pop(from_number,None)
    if not data: return
    lang=USER_LANG.get(from_number,"ar")
    if len(data["images"])==1: await asyncio.to_thread(process_single_image,data["images"][0],data["bot_id"],lang)
    else: await asyncio.to_thread(process_multi_images,data["images"],from_number,data["bot_id"],lang)

def process_single_image(message, bot_id, lang="ar"):
    from_number=message["from"]
    caption=(message.get("image",{}) or {}).get("caption","").strip()
    send_whatsapp_text(from_number, T(lang,"identifying"), bot_id)
    b64, mime=download_whatsapp_media(message["image"]["id"])

    # Google Lens أولاً (مكالمة Vision API رخيصة جداً)
    lens=google_lens_search(b64)
    if lens and lens["product_en"]:
        product_ar=translate_to_arabic(lens["product_en"])  # Flash Lite
        product_full=f"{product_ar} {lens['product_en']}".strip()
    else:
        # Fallback: Gemini Flash Lite للتعرف (بدون بحث)
        ident,_=call_gemini(
            [{"inline_data":{"mime_type":mime,"data":b64}},{"text":"ما اسم هذا المنتج؟ سطرين: عربي ثم إنجليزي"}],
            system=IDENTIFY_SYSTEM, use_search=False, lite=True
        )
        product_ar, product_full=parse_ident(ident)

    if not product_ar:
        send_whatsapp_text(from_number, T(lang,"cant_identify"), bot_id); return

    query=f"{caption} — {product_full}" if caption else product_full
    LAST_SEARCH[from_number]={"product": query}

    if caption:
        prompt=(f"المنتج في الصورة: {product_full}\nطلب المستخدم: {caption}\n"
                f"صنّف وأجب. {LANG_INSTR[lang]}")
        txt, urls=search_product(query, lang, prompt_text=prompt)
    else:
        txt, urls=search_product(product_full, lang)

    if not txt:
        send_whatsapp_text(from_number, T(lang,"cant_identify"), bot_id); return
    need_map=send_product_result(from_number, txt, urls, bot_id, lang, query)
    if need_map and product_ar:
        send_maps_button(from_number, query, bot_id, lang)

def identify_image_product(msg):
    try:
        b64, mime=download_whatsapp_media(msg["image"]["id"])
        lens=google_lens_search(b64)
        if lens and lens["product_en"]:
            ar=translate_to_arabic(lens["product_en"])
            return f"{ar} {lens['product_en']}".strip()
        ident,_=call_gemini(
            [{"inline_data":{"mime_type":mime,"data":b64}},{"text":"ما اسم هذا المنتج؟ سطرين: عربي ثم إنجليزي"}],
            system=IDENTIFY_SYSTEM, use_search=False, lite=True
        )
        _, full=parse_ident(ident)
        return full
    except Exception as e: print(f"identify err {e}"); return ""

def process_cart(products, from_number, bot_id, lang="ar"):
    results=list(WORKERS.map(lambda p: (p, *search_product(p, lang)), products))
    any_ok=False
    for p, txt, urls in results:
        if not txt: continue
        any_ok=True
        send_product_result(from_number, txt, urls, bot_id, lang, p, best_only=True)
    if not any_ok: send_whatsapp_text(from_number, T(lang,"not_found"), bot_id)
    else: LAST_SEARCH[from_number]={"product": products[0]}

def process_multi_images(messages, from_number, bot_id, lang="ar"):
    send_whatsapp_text(from_number, T(lang,"multi_images",c=len(messages)), bot_id)
    names=[n for n in WORKERS.map(identify_image_product, messages) if n]
    if not names: send_whatsapp_text(from_number, T(lang,"cant_identify"), bot_id); return
    process_cart(names, from_number, bot_id, lang)

def process_text_message(message, bot_id):
    from_number=message["from"]; user_text=message["text"]["body"]
    cmd=re.sub(r"[^\w\u0600-\u06FF]","",user_text.strip().lower())
    if cmd in ("لغة","اللغة","غيراللغة","language","lang","changelanguage"):
        send_language_choice(from_number, bot_id); return
    detected=detect_lang(user_text)
    if detected: USER_LANG[from_number]=detected
    lang=USER_LANG.get(from_number,"ar")
    pend=PENDING_IMAGES.pop(from_number,None)
    if pend and pend["images"]:
        if len(pend["images"])==1: process_single_image(pend["images"][0],pend["bot_id"],lang)
        else: process_multi_images(pend["images"],from_number,pend["bot_id"],lang)
    products=extract_products(user_text)
    if len(products)==1:
        send_whatsapp_text(from_number, T(lang,"searching",q=products[0]), bot_id)
        txt, urls=search_product(products[0], lang)
        LAST_SEARCH[from_number]={"product": products[0]}
        need_map=send_product_result(from_number, txt, urls, bot_id, lang, products[0])
        if need_map: send_maps_button(from_number, products[0], bot_id, lang)
    else:
        send_whatsapp_text(from_number, T(lang,"multi_text",c=len(products)), bot_id)
        process_cart(products, from_number, bot_id, lang)

def extract_products(text):
    text=re.sub(r'^[•\-\*\d\.\)\s]+','',text,flags=re.M)
    parts=re.split(r'\s*(?:\n+|\+|,|،| و | & )\s*',text.strip())
    parts=[p.strip() for p in parts if len(p.strip())>2]
    return parts[:6] if len(parts)>1 else [text.strip()]

def process_location_message(message, bot_id):
    from_number=message["from"]
    lat=message["location"]["latitude"]; lng=message["location"]["longitude"]
    lang=USER_LANG.get(from_number,"ar")
    last=LAST_SEARCH.get(from_number)
    if not last or not last.get("product"):
        send_whatsapp_text(from_number, T(lang,"no_saved_product"), bot_id); return
    product=last["product"]
    maps_url=maps_search_url(product, lat, lng)
    send_whatsapp_cta(from_number, T(lang,"maps_body_loc",p=product), maps_url, bot_id, T(lang,"maps_btn"))

@app.get("/")
async def health(): return {"status":"v37 lean — 1-2 Gemini calls per query"}
