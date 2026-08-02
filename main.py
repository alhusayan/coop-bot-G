# -*- coding: utf-8 -*-
import os, re, time, base64, requests, json, asyncio, urllib.parse, hashlib, sqlite3, threading
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Request, Response, BackgroundTasks
from bs4 import BeautifulSoup

app = FastAPI()

# ===== ENV =====
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite") # ارخص 80% من العادي
GEMINI_IDENTIFY_MODEL = os.environ.get("GEMINI_IDENTIFY_MODEL", "gemini-2.5-flash-lite")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_COOP_BOT_TOKEN")
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "") # اختياري لكن يوفر 95% من التكلفة
GRAPH_URL = "https://graph.facebook.com/v20.0"

# ===== CONFIG =====
MAX_STORES = 5  # بدل 7
BUFFER_SECONDS = 4
CACHE_TTL = int(os.environ.get("CACHE_TTL_HOURS", "24")) * 3600 # 24 ساعة بدل ساعتين
MAX_REQUESTS_PER_USER_PER_DAY = 25

# Pools صغيرة عشان لا تطق Rate Limit
RESOLVER = ThreadPoolExecutor(max_workers=4)
WORKERS = ThreadPoolExecutor(max_workers=3)
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

processed_ids = deque(maxlen=1000)
IMAGE_BUFFER = defaultdict(lambda: {"images": [], "time": 0, "bot_id": ""})
LAST_SEARCH = {}
USER_LANG = {}
PENDING_IMAGES = defaultdict(lambda: {"images": [], "bot_id": ""})
USER_DAILY_COUNT = defaultdict(lambda: {"count": 0, "day": 0})

# ===== PERSISTENT CACHE (SQLite) =====
DB_LOCK = threading.Lock()
DB_PATH = "cache.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.execute("""CREATE TABLE IF NOT EXISTS search_cache 
(key TEXT PRIMARY KEY, txt TEXT, urls TEXT, ts REAL, lang TEXT, query TEXT)""")
conn.commit()

def cache_key(query, lang):
    norm = re.sub(r"[^\w\u0600-\u06FF]+", "", (query or "").lower())
    return hashlib.sha256(f"{norm}|{lang}".encode()).hexdigest()

def cache_get(query, lang):
    key = cache_key(query, lang)
    with DB_LOCK:
        cur = conn.execute("SELECT txt, urls, ts FROM search_cache WHERE key=?", (key,))
        row = cur.fetchone()
    if row:
        txt, urls_json, ts = row
        if time.time() - ts < CACHE_TTL:
            print(f"CACHE HIT DB: {query[:50]}")
            return txt, json.loads(urls_json)
    return None

def cache_put(query, lang, txt, urls):
    if not txt: return
    key = cache_key(query, lang)
    with DB_LOCK:
        conn.execute("INSERT OR REPLACE INTO search_cache VALUES (?,?,?,?,?,?)",
                     (key, txt, json.dumps(urls), time.time(), lang, query))
        conn.commit()

# ===== Helpers =====
def format_price(p):
    try:
        pf = float(p)
        return f"{pf:.3f}".rstrip('0').rstrip('.') if pf < 100 else f"{pf:.2f}".rstrip('0').rstrip('.')
    except: return str(p)

def clean_domain(dom):
    dom = re.sub(r"^https?://", "", (dom or "").strip().lower())
    return dom.replace("www.", "").split("/")[0]

def domain_key(dom): return clean_domain(dom).split(".")[0]

STORE_DOMAINS = {
    "xcite": "xcite.com", "اكسايت": "xcite.com",
    "eureka": "eureka.com.kw", "يوريكا": "eureka.com.kw",
    "blink": "blink.com.kw", "بلينك": "blink.com.kw",
    "best": "best.com.kw", "اليوسفي": "best.com.kw",
    "jarir": "jarir.com", "جرير": "jarir.com",
    "lulu": "luluhypermarket.com", "لولو": "luluhypermarket.com",
    "carrefour": "carrefourkuwait.com", "كارفور": "carrefourkuwait.com",
    "noon": "noon.com", "نون": "noon.com",
    "amazon": "amazon.ae", "امازون": "amazon.ae",
    "clicflyer": "clicflyer.com",
}

def store_name_from_url(url):
    d = clean_domain(url)
    for name, dom in STORE_DOMAINS.items():
        if dom in d: return name.capitalize() if name.isascii() else name
    try: return d.split(".")[0].capitalize()
    except: return "المتجر"

OOS_PHRASES = ["out of stock","غير متوفر","نفدت الكمية","غير متاح","sold out","temporarily unavailable"]
LISTING_URL_PARTS = ["/search","/s?","/category","/categories","/collection","/collections","/shop/category","?q="]

def fetch_html(url):
    if not url or not url.startswith("http"): return ""
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200 and len(r.text) > 1500: return r.text
    except: pass
    return ""

def parse_product_data(html, url):
    if not html: return None
    soup = BeautifulSoup(html, 'lxml')
    data = {"price": None, "available": True, "is_product": True, "title": ""}
    try:
        for script in soup.find_all("script", type="application/ld+json"):
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
                if "Product" in t:
                    offers = obj.get("offers") or {}
                    if isinstance(offers, list): offers = offers[0] if offers else {}
                    p = offers.get("price") or offers.get("lowPrice")
                    if p:
                        try: data["price"] = float(str(p).replace(",",""))
                        except: pass
                    av = str(offers.get("availability","")).lower()
                    if "outofstock" in av or "soldout" in av: data["available"] = False
    except: pass
    low = soup.get_text(" ", strip=True).lower()[:4000]
    if any(ph in low for ph in OOS_PHRASES): data["available"] = False
    ul = url.lower()
    if any(p in ul for p in LISTING_URL_PARTS):
        if not re.search(r"/product/|/products/|/p/|/dp/|/item/", ul):
            data["is_product"] = False
    return data

def verify_offers(urls_map):
    if not urls_map: return {}
    verified = {}
    def _check(item):
        name, url = item
        html = fetch_html(url)
        info = parse_product_data(html, url)
        if not info or not info["is_product"] or not info["available"] or not info["price"]: return None
        return (name, url, info)
    results = list(RESOLVER.map(_check, urls_map.items()))
    for r in results:
        if r: name, url, info = r; verified[name] = {"url": url, "price": info["price"]}
    return verified

# ===== SEARCH =====
def brave_search(query, count=10):
    if not BRAVE_API_KEY: return []
    try:
        r = requests.get("https://api.search.brave.com/res/v1/web/search",
            headers={"X-Subscription-Token": BRAVE_API_KEY, "Accept": "application/json"},
            params={"q": query, "count": count, "country": "kw", "search_lang": "ar"},
            timeout=10)
        if r.status_code == 200:
            data = r.json()
            results = data.get("web", {}).get("results", [])
            return [{"title": x.get("title",""), "url": x.get("url","")} for x in results if x.get("url")]
    except Exception as e:
        print(f"Brave err {e}")
    return []

def call_gemini_single(parts, model=None, system="", use_search=False):
    model = model or GEMINI_MODEL
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1200},
    }
    if use_search: payload["tools"] = [{"google_search": {}}]
    try:
        r = requests.post(url, params={"key": GEMINI_API_KEY}, json=payload, timeout=30)
        if r.status_code != 200:
            print(f"Gemini {model} {r.status_code}: {r.text[:300]}")
            return "", {}
        data = r.json()
        cand = (data.get("candidates") or [{}])[0]
        text = "".join(p.get("text","") for p in cand.get("content",{}).get("parts",[])).strip()
        # Extract LINKS if exists
        urls = {}
        m = re.search(r"(?im)^\s*LINKS\s*:\s*(.+)$", text)
        if m:
            raw = m.group(1)
            for part in re.split(r"[,،]+", raw):
                if "=" in part:
                    n,d = part.split("=",1)
                    n,d = n.strip(), clean_domain(d)
                    if n and "." in d: urls[n] = f"https://{d}"
            text = re.sub(r"(?im)^\s*LINKS\s*:.*$", "", text).strip()
        # grounding urls
        meta = cand.get("groundingMetadata",{}) or {}
        for ch in (meta.get("groundingChunks") or [])[:5]:
            uri = (ch.get("web") or {}).get("uri")
            title = (ch.get("web") or {}).get("title","")
            if uri and len(urls) < 5:
                label = title[:30] if title else store_name_from_url(uri)
                if label not in urls: urls[label] = uri
        text = re.sub(r"https?://\S+", "", text).replace("**","").strip()
        return text, urls
    except Exception as e:
        print(f"Gemini call err {e}")
        return "", {}

# ===== CORE LOGIC (NEW - 1 call only) =====
def search_product(query, lang):
    # 1. Rate limit + cache
    today = int(time.time() // 86400)
    # cache check
    hit = cache_get(query, lang)
    if hit: return hit

    # 2. Search via Brave (رخيص) - اذا مافي مفتاح نستخدم Gemini مرة واحدة فقط مع بحث
    urls_map = {}
    if BRAVE_API_KEY:
        # نبني كويري ذكي لمحلات الكويت
        stores_q = " OR ".join([f"site:{d}" for d in set(STORE_DOMAINS.values())])
        brave_q = f"{query} ({stores_q}) الكويت"
        results = brave_search(brave_q, count=12)
        for r in results:
            u = r["url"]
            if any(p in u.lower() for p in LISTING_URL_PARTS): continue
            label = store_name_from_url(u)
            if label not in urls_map and u not in urls_map.values():
                urls_map[label] = u
            if len(urls_map) >= 8: break
    else:
        # Fallback: مكالمة واحدة فقط مع Google Search (بدل 8)
        sys = "انت مساعد تسوق كويتي. اعطني اسعار حقيقية InStock فقط مع LINKS."
        txt, urls = call_gemini_single([{"text": f"{query} افضل سعر الكويت Xcite Eureka Blink Noon Jarir - {lang}"}], system=sys, use_search=True)
        if txt:
            cache_put(query, lang, txt, urls)
            return txt, urls
        return "", {}

    # 3. تحقق من الصفحات (مجاني - بدون AI)
    verified = verify_offers(urls_map)
    
    # 4. تنسيق بدون AI اذا لقينا اسعار (0 تكلفة)
    if verified:
        sorted_v = sorted(verified.items(), key=lambda x: x[1]["price"])
        lines = [f"📦 {query}", ""]
        new_urls = {}
        for i, (name, info) in enumerate(sorted_v[:MAX_STORES]):
            prefix = "✅" if i==0 else "•"
            lines.append(f"{prefix} {name} — {format_price(info['price'])} د.ك")
            new_urls[name] = info["url"]
        final_txt = "\n".join(lines)
        cache_put(query, lang, final_txt, new_urls)
        print(f"VERIFIED OK (no LLM): {query} -> {len(new_urls)} stores")
        return final_txt, new_urls
    
    # 5. اذا ما لقينا شي، نستخدم Gemini مرة واحدة للتنسيق (Fallback)
    print(f"Fallback to LLM for {query}")
    sys = "انت مساعد تسوق كويتي. اذا ما لقيت سعر لا تخترع."
    txt, urls = call_gemini_single([{"text": f"ابحث عن {query} في الكويت. {lang}"}], system=sys, use_search=True)
    if txt: cache_put(query, lang, txt, urls)
    return txt, urls

# ===== WhatsApp helpers (نفسها) =====
def download_whatsapp_media(mid):
    h={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    meta=requests.get(f"{GRAPH_URL}/{mid}",headers=h,timeout=20).json()
    img=requests.get(meta["url"],headers=h,timeout=20)
    return base64.b64encode(img.content).decode(), meta.get("mime_type","image/jpeg")

def send_whatsapp_text(to,text,bot_id):
    url=f"{GRAPH_URL}/{bot_id}/messages"
    h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    payload={"messaging_product":"whatsapp","to":to,"type":"text","text":{"body":text[:3900]}}
    try: requests.post(url,json=payload,headers=h,timeout=10)
    except: pass

def send_whatsapp_cta(to,body,link,bot_id,title):
    url=f"{GRAPH_URL}/{bot_id}/messages"
    h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    payload={"messaging_product":"whatsapp","to":to,"type":"interactive","interactive":{"type":"cta_url","body":{"text":body[:1024]},"action":{"name":"cta_url","parameters":{"display_text":title[:20],"url":link}}}}
    try: requests.post(url,json=payload,headers=h,timeout=10)
    except: pass

def send_whatsapp_buttons(to, body, buttons, bot_id):
    url=f"{GRAPH_URL}/{bot_id}/messages"
    h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    btns=[{"type":"reply","reply":{"id":b["id"],"title":b["title"][:20]}} for b in buttons[:3]]
    payload={"messaging_product":"whatsapp","to":to,"type":"interactive","interactive":{"type":"button","body":{"text":body[:1024]},"action":{"buttons":btns}}}
    try: requests.post(url,json=payload,headers=h,timeout=10)
    except: pass

def send_language_choice(to, bot_id):
    send_whatsapp_buttons(to, "🌐 اختر لغتك / Choose language", [{"id": "lang_ar", "title": "العربية 🇰🇼"},{"id": "lang_en", "title": "English 🇬🇧"}], bot_id)

def detect_lang(text):
    if re.search(r"[\u0600-\u06FF]", text or ""): return "ar"
    if re.search(r"[A-Za-z]", text or ""): return "en"
    return None

IDENTIFY_SYSTEM = "انت خبير تعرف على المنتجات. اكتب اسم المنتج التجاري فقط بصيغة [البراند] [النوع] [الموديل] [اللون] - سطر واحد."

MSG = {
    "ar": {"identifying":"ثواني بس.. أحدد المنتج!","searching":"🔍 أدور لك على {q}...","not_found":"ما لقيته متوفر حالياً 😅 جرب صياغة ثانية.","cant_identify":"ما قدرت أحدد المنتج، دز صورة أوضح","multi_text":"تمام لقيت {c} منتجات...","multi_images":"تمام لقطت {c} منتجات...","maps_body":"📍 تبي أقرب مكان؟ اضغط الزر 👇","maps_btn":"📍 افتح الخريطة","maps_body_loc":"📍 بحثك الأخير ({p}) - افتح الخريطة 👇","no_saved_product":"ما عندي منتج محفوظ حالياً 😅","lang_saved":"تمام، بكلمك عربي 🇰🇼"},
    "en": {"identifying":"One sec.. identifying!","searching":"🔍 Looking up {q}...","not_found":"Couldn't find it in-stock 😅","cant_identify":"Couldn't identify","multi_text":"Got {c} products...","multi_images":"Got {c} products from images...","maps_body":"📍 Want nearest place? Tap 👇","maps_btn":"📍 Open Map","maps_body_loc":"📍 Last search ({p}) - Open map 👇","no_saved_product":"No saved product yet","lang_saved":"Got it, English from now 🇬🇧"},
}
def T(lang,key,**kw): return MSG.get(lang,MSG["ar"])[key].format(**kw) if kw else MSG.get(lang,MSG["ar"])[key]

def fallback_search_url(query, store=""):
    return "https://www.google.com/search?q=" + urllib.parse.quote(f"{query} {store} الكويت")

def match_url(name, urls):
    if not urls: return ""
    if name in urls: return urls[name]
    for k,v in urls.items():
        if name.lower() in k.lower() or k.lower() in name.lower(): return v
    return ""

def send_product_result(from_number, txt, urls, bot_id, lang, query, best_only=False):
    if not txt:
        send_whatsapp_text(from_number, T(lang,"not_found"), bot_id); return False
    # استخراج العروض
    offers=[]
    for line in txt.splitlines():
        m=re.match(r"^\s*(?:✅|•)\s*(.+?)\s*[—-]\s*[\d.,]+", line)
        if m: offers.append({"line":line.strip(),"name":m.group(1).strip(),"best":"✅" in line})
    if not offers:
        send_whatsapp_text(from_number, txt, bot_id); return True
    title_m=re.search(r"^\s*📦\s*(.+)$", txt, flags=re.M)
    if title_m: send_whatsapp_text(from_number, f"📦 {title_m.group(1)}", bot_id)
    if best_only: offers=[next((o for o in offers if o["best"]), offers[0])]
    for o in offers[:MAX_STORES]:
        url=match_url(o["name"], urls) or fallback_search_url(query, o["name"])
        send_whatsapp_cta(from_number, o["line"], url, bot_id, f"🛒 {o['name'][:18]}")
    return True

def call_gemini_identify(b64,mime):
    # مكالمة رخيصة جداً بدون بحث
    txt,_=call_gemini_single([{"inline_data":{"mime_type":mime,"data":b64}},{"text":"ما اسم المنتج؟"}], model=GEMINI_IDENTIFY_MODEL, system=IDENTIFY_SYSTEM, use_search=False)
    return txt.strip().splitlines()[0] if txt else ""

def maps_search_url(product, lat=None, lng=None):
    q=urllib.parse.quote(product[:60])
    if lat and lng: return f"https://www.google.com/maps/search/{q}/@{lat},{lng},15z"
    return f"https://www.google.com/maps/search/{q}"

def send_maps_button(from_number, product, bot_id, lang):
    send_whatsapp_cta(from_number, T(lang,"maps_body"), maps_search_url(product), bot_id, T(lang,"maps_btn"))

# ===== Handlers =====
def check_rate_limit(from_number):
    today=int(time.time()//86400)
    rec=USER_DAILY_COUNT[from_number]
    if rec["day"]!=today: rec["day"]=today; rec["count"]=0
    rec["count"]+=1
    return rec["count"] > MAX_REQUESTS_PER_USER_PER_DAY

def process_single_image(message,bot_id,lang="ar"):
    from_number=message["from"]
    if check_rate_limit(from_number):
        send_whatsapp_text(from_number, "وصلت الحد اليومي، تعال باجر 😅" if lang=="ar" else "Daily limit reached", bot_id); return
    send_whatsapp_text(from_number,T(lang,"identifying"),bot_id)
    b64,mime=download_whatsapp_media(message["image"]["id"])
    product_name=call_gemini_identify(b64,mime)
    if not product_name:
        send_whatsapp_text(from_number,T(lang,"cant_identify"),bot_id); return
    txt,urls=search_product(product_name, lang)
    LAST_SEARCH[from_number]={"product":product_name}
    if send_product_result(from_number, txt, urls, bot_id, lang, product_name):
        send_maps_button(from_number, product_name, bot_id, lang)

def process_text_message(message,bot_id):
    from_number=message["from"]; user_text=message["text"]["body"]
    if re.sub(r"[^\w\u0600-\u06FF]","",user_text.lower()) in ("لغة","اللغة","language","lang"):
        send_language_choice(from_number, bot_id); return
    detected=detect_lang(user_text)
    if detected: USER_LANG[from_number]=detected
    lang=USER_LANG.get(from_number,"ar")
    if check_rate_limit(from_number):
        send_whatsapp_text(from_number, "وصلت الحد اليومي" if lang=="ar" else "Limit reached", bot_id); return
    # سلة اذا فيه + او ،
    products=[p.strip() for p in re.split(r"\s*(?:\+|,|،| و )\s*", user_text) if len(p.strip())>2]
    if len(products)==1:
        send_whatsapp_text(from_number,T(lang,"searching",q=products[0]),bot_id)
        txt,urls=search_product(products[0], lang)
        LAST_SEARCH[from_number]={"product":products[0]}
        if send_product_result(from_number, txt, urls, bot_id, lang, products[0]):
            send_maps_button(from_number, products[0], bot_id, lang)
    else:
        send_whatsapp_text(from_number,T(lang,"multi_text",c=len(products)),bot_id)
        for p in products[:4]: # حد اقصى 4 منتجات بالسلة
            txt,urls=search_product(p, lang)
            send_product_result(from_number, txt, urls, bot_id, lang, p, best_only=True)

async def process_image_buffer(from_number):
    await asyncio.sleep(BUFFER_SECONDS)
    data=IMAGE_BUFFER.pop(from_number,None)
    if not data: return
    lang=USER_LANG.get(from_number,"ar")
    if len(data["images"])==1: await asyncio.to_thread(process_single_image,data["images"][0],data["bot_id"],lang)

def process_interactive_message(message, bot_id):
    from_number=message["from"]
    btn_id=((message.get("interactive") or {}).get("button_reply") or {}).get("id","")
    if btn_id not in ("lang_ar","lang_en"): return
    lang="ar" if btn_id=="lang_ar" else "en"
    USER_LANG[from_number]=lang
    pend=PENDING_IMAGES.pop(from_number,None)
    if pend and pend["images"]:
        process_single_image(pend["images"][0], pend["bot_id"], lang)
    else:
        send_whatsapp_text(from_number, T(lang,"lang_saved"), bot_id)

def process_location_message(message, bot_id):
    from_number=message["from"]; lat=message["location"]["latitude"]; lng=message["location"]["longitude"]
    lang=USER_LANG.get(from_number,"ar")
    last=LAST_SEARCH.get(from_number)
    if not last: send_whatsapp_text(from_number,T(lang,"no_saved_product"),bot_id); return
    product=last["product"]
    url=maps_search_url(product, lat, lng)
    send_whatsapp_cta(from_number, T(lang,"maps_body_loc",p=product), url, bot_id, T(lang,"maps_btn"))

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
            cap=(msg.get("image",{}) or {}).get("caption","").strip()
            if detect_lang(cap): USER_LANG[from_number]=detect_lang(cap)
            if from_number not in USER_LANG:
                PENDING_IMAGES[from_number]["images"].append(msg); PENDING_IMAGES[from_number]["bot_id"]=bot_id
                if len(PENDING_IMAGES[from_number]["images"])==1:
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

@app.get("/")
async def health(): return {"status":"v2-optimized - 1 call + persistent cache"}
