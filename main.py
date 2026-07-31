# -*- coding: utf-8 -*-
import os, re, time, base64, requests, hashlib, urllib.parse
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import FastAPI, Request, Response, BackgroundTasks

app = FastAPI()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_COOP_BOT_TOKEN")

GRAPH_URL = "https://graph.facebook.com/v20.0"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

processed_ids = deque(maxlen=2000)
IMAGE_BUFFER = defaultdict(lambda: {"images": [], "time": 0, "bot_id": ""})
LAST_SEARCH = {}
USER_LANG = {}
PENDING_IMAGES = defaultdict(lambda: {"images": [], "bot_id": ""})

BUFFER_SECONDS = 1.5 # كان 4
WORKERS = ThreadPoolExecutor(max_workers=8)
HEADERS = {"User-Agent": "Mozilla/5.0"}

SEARCH_CACHE = {}
CACHE_TTL = int(os.environ.get("CACHE_TTL_HOURS", "2")) * 3600
CACHE_MAX = 1000

# === خرائط ذكية LOCAL بدون Gemini - طلقة ===
def get_smart_maps_query_local(product: str) -> str:
    p = (product or "").lower()
    if any(k in p for k in ["ايفون","iphone","سامسونج","samsung","ايباد","لابتوب","macbook","ساعة ابل","airpods","ابل واتش"]):
        return "Xcite OR Eureka OR Best Al Yousifi"
    if any(k in p for k in ["ثلاجة","غسالة","مكيف","فرن","ميكروويف"]):
        return "Xcite OR Eureka"
    if any(k in p for k in ["صيدلية","دواء","فيتامين","مكمل","بروتين","pharmacy","دواء"]):
        return "صيدلية Pharmacy"
    if any(k in p for k in ["جمعية","سوبرماركت","تموينات","خضار","لحم"]):
        return "جمعية تعاونية Supermarket"
    if any(k in p for k in ["كهرباء","اضاءة","سباكة"]):
        return "مواد كهربائية Electrical supply"
    if any(k in p for k in ["رياضة","بادل","تنس","نادي","gym","intresport","go sport"]):
        return "Intersport OR Go Sport OR محل رياضي"
    return product.strip()[:80]

def normalize_ar(text):
    t = (text or "").lower()
    t = re.sub(r"[أإآ]", "ا", t)
    return t.replace("ة","ه").replace("ى","ي")

def norm_tokens(q):
    return set(re.findall(r"[\w\u0600-\u06FF]+", normalize_ar(q)))

def cache_key(query, lang):
    norm = re.sub(r"[^\w\u0600-\u06FF]+", "", normalize_ar(query))
    return hashlib.sha256(f"{norm}|{lang}".encode()).hexdigest()

def cache_get(query, lang):
    hit = SEARCH_CACHE.get(cache_key(query, lang))
    if hit and (time.time() - hit["ts"]) < CACHE_TTL:
        return hit["txt"], dict(hit["urls"])
    return None

def cache_put(query, lang, txt, urls):
    if not txt: return
    if len(SEARCH_CACHE) >= CACHE_MAX:
        oldest = min(SEARCH_CACHE, key=lambda k: SEARCH_CACHE[k]["ts"])
        SEARCH_CACHE.pop(oldest, None)
    SEARCH_CACHE[cache_key(query, lang)] = {"txt": txt, "urls": dict(urls), "ts": time.time()}

MSG = {
    "ar": {
        "identifying": "ثواني بس.. 🚀",
        "searching": "🔍 أدور على {q}...",
        "not_found": "ما لقيت",
        "cant_identify": "ما قدرت أحدد المنتج",
        "multi_text": "تمام لقيت {c} منتجات...",
        "multi_images": "تمام لقطت {c} منتجات...",
        "maps_body": "📍 ({p}) - أقرب المحلات حولك 👇",
        "maps_btn": "📍 افتح الخريطة",
    },
    "en": {
        "identifying": "One sec.. 🚀",
        "searching": "Looking up {q}...",
        "not_found": "Not found",
        "cant_identify": "Can't identify",
        "multi_text": "Got {c} products...",
        "multi_images": "Got {c} products...",
        "maps_body": "📍 ({p}) - nearest stores 👇",
        "maps_btn": "📍 Open Map",
    },
}
LANG_INSTR = {
    "ar": "رد بالعربية فقط.",
    "en": "Respond ONLY in English. Prices in KWD.",
}
def T(lang, key, **kw): return MSG.get(lang, MSG["ar"])[key].format(**kw) if kw else MSG.get(lang, MSG["ar"])[key]
def detect_lang(text):
    if re.search(r"[\u0600-\u06FF]", text or ""): return "ar"
    if re.search(r"[A-Za-z]", text or ""): return "en"
    return None

SYSTEM_PROMPT = """
أنت مساعد تسوق كويتي سريع. استخدم بحث Google للأسعار في الكويت.
📦 [اسم المنتج]
✅ [المتجر الأرخص] — [السعر] د.ك
- [الثاني] — [السعر] د.ك
- [الثالث] — [السعر] د.ك
آخر سطر الزامي: LINKS: اسم=domain.com, اسم=domain.com, اسم=domain.com
ممنوع https. ممنوع Markdown.
"""

def clean_domain(dom): return re.sub(r"^https?://", "", (dom or "").lower()).replace("www.","").split("/")[0]
def normalize_name(v): return re.sub(r"[^\w\u0600-\u06FF]+", "", (v or "").lower())
def extract_store_names(text):
    stores=[]
    for line in (text or "").splitlines():
        m=re.match(r"^\s*(?:✅|🏆|•)\s*(.+?)\s*(?:—|–|-)\s*[\d.,]+", line)
        if m:
            name=m.group(1).strip()
            if name not in stores: stores.append(name)
    return stores[:4]

# === TURBO GEMINI - بدون resolve_all ===
def call_gemini_turbo(parts, system=SYSTEM_PROMPT):
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": parts}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 900},
    }
    try:
        r = requests.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload, timeout=25)
        if r.status_code >= 400: return "", {}
        data = r.json()
        cand = (data.get("candidates") or [None])[0]
        if not cand: return "", {}
        text = "".join(p.get("text","") for p in cand.get("content",{}).get("parts",[])).strip()

        pairs=[]
        m=re.search(r"(?im)^\s*LINKS\s*:\s*(.+)$", text)
        if m:
            raw=m.group(1)
            for part in re.split(r"[,،]+", raw):
                if "=" in part:
                    name,dom=part.split("=",1)
                    name,dom=name.strip(), clean_domain(dom)
                    if name and "." in dom: pairs.append((name,dom))
            text=re.sub(r"(?im)^\s*LINKS\s*:.*$", "", text).strip()

        text=re.sub(r"https?://\S+","",text).replace("**","").strip()

        # بناء الروابط INSTANT بدون ما نفتحها
        metadata=cand.get("groundingMetadata",{}) or {}
        chunks=metadata.get("groundingChunks",[]) or []
        urls_map={}
        for name,dom in pairs[:4]:
            # حاول تلقى رابط خام يطابق الدومين، اذا ما لقيت استخدم الدومين مباشر
            found=""
            for c in chunks[:8]:
                raw=(c.get("web") or {}).get("uri","")
                if dom.split(".")[0] in raw.lower():
                    found=raw; break
            urls_map[name]=found or f"https://{dom}"

        return text, urls_map
    except Exception as e:
        print(f"turbo err {e}"); return "", {}

def search_product_turbo(query, lang, b64=None, mime=None):
    # كاش سريع للكلام فقط
    if not b64:
        hit=cache_get(query, lang)
        if hit: return hit

    parts=[]
    if b64:
        parts.append({"inline_data":{"mime_type":mime,"data":b64}})
        parts.append({"text": f"ما هذا؟ ابحث عن سعر {query} في الكويت. {LANG_INSTR[lang]}"})
    else:
        parts.append({"text": f"ابحث عن سعر {query} في الكويت. {LANG_INSTR[lang]}"})

    txt,urls=call_gemini_turbo(parts)

    if not b64 and txt:
        # احفظ فقط اذا النتيجة قوية
        if len(extract_store_names(txt))>=2:
            cache_put(query, lang, txt, urls)
    return txt,urls

def download_whatsapp_media(mid):
    h={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    meta=requests.get(f"{GRAPH_URL}/{mid}",headers=h,timeout=10).json()
    img=requests.get(meta["url"],headers=h,timeout=10)
    return base64.b64encode(img.content).decode(), meta.get("mime_type","image/jpeg")

def send_whatsapp_text(to,text,bot_id):
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    payload={"messaging_product":"whatsapp","to":to,"type":"text","text":{"body":text[:3900]}}
    try: requests.post(url,json=payload,headers=h,timeout=5)
    except: pass

def send_whatsapp_cta(to,body,link,bot_id,title):
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    payload={"messaging_product":"whatsapp","to":to,"type":"interactive","interactive":{"type":"cta_url","body":{"text":body[:1024]},"action":{"name":"cta_url","parameters":{"display_text":title[:20],"url":link}}}}
    try: requests.post(url,json=payload,headers=h,timeout=5)
    except: pass

def send_whatsapp_buttons(to, body, buttons, bot_id):
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    btns=[{"type":"reply","reply":{"id":b["id"],"title":b["title"][:20]}} for b in buttons[:3]]
    payload={"messaging_product":"whatsapp","to":to,"type":"interactive","interactive":{"type":"button","body":{"text":body[:1024]},"action":{"buttons":btns}}}
    try: requests.post(url,json=payload,headers=h,timeout=5)
    except: pass

def send_language_choice(to, bot_id):
    send_whatsapp_buttons(to, "🌐 لغتك؟ / Language?", [{"id":"lang_ar","title":"العربية 🇰🇼"},{"id":"lang_en","title":"English 🇬🇧"}], bot_id)

def extract_products(text):
    text=re.sub(r'^[•\-\*\d\.\)\s]+','',text,flags=re.M)
    parts=re.split(r'\s*(?:\n+|\+|,|،| و | & )\s*',text.strip())
    parts=[p.strip() for p in parts if len(p.strip())>2]
    return parts[:6] if len(parts)>1 else [text.strip()]

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
            caption=(msg.get("image",{}) or {}).get("caption","").strip()
            if detect_lang(caption): USER_LANG[from_number]=detect_lang(caption)
            if from_number not in USER_LANG:
                PENDING_IMAGES[from_number]["images"].append(msg); PENDING_IMAGES[from_number]["bot_id"]=bot_id
                if len(PENDING_IMAGES[from_number]["images"])==1:
                    background_tasks.add_task(send_language_choice, from_number, bot_id)
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
    btn_id=(message.get("interactive") or {}).get("button_reply",{}).get("id","")
    if btn_id not in ("lang_ar","lang_en"): return
    lang="ar" if btn_id=="lang_ar" else "en"
    USER_LANG[from_number]=lang
    pend=PENDING_IMAGES.pop(from_number,None)
    if pend and pend["images"]:
        if len(pend["images"])==1: process_single_image(pend["images"][0], pend["bot_id"], lang)
        else: process_multi_images(pend["images"], from_number, pend["bot_id"], lang)

async def process_image_buffer(from_number):
    import asyncio
    await asyncio.sleep(BUFFER_SECONDS)
    data=IMAGE_BUFFER.pop(from_number,None)
    if not data: return
    lang=USER_LANG.get(from_number,"ar")
    if len(data["images"])==1:
        await asyncio.to_thread(process_single_image,data["images"][0],data["bot_id"],lang)
    else:
        await asyncio.to_thread(process_multi_images,data["images"],from_number,data["bot_id"],lang)

def parse_and_send(from_number, bot_id, lang, txt, urls, product_for_map):
    if not txt: return
    # ارسل النص فوراً
    send_whatsapp_text(from_number, txt, bot_id)
    # ارسل ازرار المتاجر
    for name,link in list(urls.items())[:3]:
        if link: send_whatsapp_cta(from_number, f"تسوق من {name} 👇", link, bot_id, f"🛒 {name[:18]}")
    # زر الخريطة الذكي LOCAL - بدون API
    smart_q=get_smart_maps_query_local(product_for_map)
    maps_url=f"https://www.google.com/maps/search/{urllib.parse.quote(smart_q)}"
    send_whatsapp_cta(from_number, T(lang,"maps_body",p=product_for_map), maps_url, bot_id, T(lang,"maps_btn"))

def process_single_image(message, bot_id, lang="ar"):
    from_number=message["from"]
    caption=(message.get("image",{}) or {}).get("caption","").strip()
    send_whatsapp_text(from_number, T(lang,"identifying"), bot_id)
    b64,mime=download_whatsapp_media(message["image"]["id"])
    q=caption or "هذا المنتج"
    txt,urls=search_product_turbo(q, lang, b64=b64, mime=mime)
    if not txt:
        send_whatsapp_text(from_number, T(lang,"cant_identify"), bot_id); return
    # استخرج اسم المنتج من الرد للخريطة
    m=re.search(r"📦\s*(.+)", txt)
    pname=m.group(1).strip() if m else q
    LAST_SEARCH[from_number]={"product": pname}
    parse_and_send(from_number, bot_id, lang, txt, urls, pname)

def process_multi_images(messages, from_number, bot_id, lang="ar"):
    send_whatsapp_text(from_number, T(lang,"multi_images",c=len(messages)), bot_id)
    # كل صورة بحث منفصل بالتوازي، وكل ما يخلص واحد ندزه فوراً
    def job(msg):
        b64,mime=download_whatsapp_media(msg["image"]["id"])
        txt,urls=search_product_turbo("هذا المنتج", lang, b64=b64, mime=mime)
        return txt,urls
    futs={WORKERS.submit(job, m): m for m in messages}
    for fut in as_completed(futs):
        txt,urls=fut.result()
        if txt:
            m=re.search(r"📦\s*(.+)", txt)
            pname=m.group(1).strip() if m else "منتج"
            parse_and_send(from_number, bot_id, lang, txt, urls, pname)

def process_text_message(message, bot_id):
    from_number=message["from"]; user_text=message["text"]["body"]
    if user_text.strip().lower() in ("لغة","language","lang"):
        send_language_choice(from_number, bot_id); return
    if detect_lang(user_text): USER_LANG[from_number]=detect_lang(user_text)
    lang=USER_LANG.get(from_number,"ar")
    pend=PENDING_IMAGES.pop(from_number,None)
    if pend and pend["images"]:
        if len(pend["images"])==1: process_single_image(pend["images"][0], pend["bot_id"], lang)
        else: process_multi_images(pend["images"], from_number, pend["bot_id"], lang)

    products=extract_products(user_text)
    if len(products)==1:
        send_whatsapp_text(from_number, T(lang,"searching",q=products[0]), bot_id)
        txt,urls=search_product_turbo(products[0], lang)
        if not txt:
            send_whatsapp_text(from_number, T(lang,"not_found"), bot_id); return
        LAST_SEARCH[from_number]={"product": products[0]}
        parse_and_send(from_number, bot_id, lang, txt, urls, products[0])
    else:
        send_whatsapp_text(from_number, T(lang,"multi_text",c=len(products)), bot_id)
        def job(p): return p, *search_product_turbo(p, lang)
        futs=[WORKERS.submit(job, p) for p in products]
        for fut in as_completed(futs):
            p,txt,urls=fut.result()
            if txt: parse_and_send(from_number, bot_id, lang, txt, urls, p)

def process_location_message(message, bot_id):
    from_number=message["from"]; lat=message["location"]["latitude"]; lng=message["location"]["longitude"]
    lang=USER_LANG.get(from_number,"ar")
    last=LAST_SEARCH.get(from_number)
    if not last: return
    product=last.get("product")
    smart_q=get_smart_maps_query_local(product)
    maps_url=f"https://www.google.com/maps/search/{urllib.parse.quote(smart_q)}/@{lat},{lng},15z"
    send_whatsapp_cta(from_number, T(lang,"maps_body",p=product), maps_url, bot_id, T(lang,"maps_btn"))

@app.get("/")
async def health(): return {"status":"v30 TURBO - طلقة"}
