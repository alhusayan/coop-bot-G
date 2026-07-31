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
LAST_SEARCH = {}
USER_LANG = {}
PENDING_IMAGES = defaultdict(lambda: {"images": [], "bot_id": ""})

BUFFER_SECONDS = 4
RESOLVER = ThreadPoolExecutor(max_workers=6)
WORKERS = ThreadPoolExecutor(max_workers=3)
SEARCH_POOL = ThreadPoolExecutor(max_workers=8)
HEADERS = {"User-Agent": "Mozilla/5.0"}

SEARCH_CACHE = {}
CACHE_TTL = int(os.environ.get("CACHE_TTL_HOURS", "2")) * 3600
CACHE_MAX = 500
CACHE_MIN_STORES = 3
CACHE_MIN_LINKS = 1

# === طريقة البحث الذكية في الخريطة - نفسها القديمة بالضبط ===
PROMPT_CATEGORY = """أنت خبير تسوق في السوق الكويتي.
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

def result_quality(txt, urls):
    return len(extract_store_names(txt or "")), len(urls or {})

def fallback_search_url(query):
    return "https://www.google.com/search?q=" + urllib.parse.quote(f"{query} الكويت اونلاين")

def parse_answer_lines(txt):
    name_line = ""
    offers = []
    for line in (txt or "").splitlines():
        line = line.strip()
        if not line: continue
        if line.startswith("📦") and not name_line:
            name_line = line
            continue
        m = re.match(r"^(?:✅|🏆|•)\s*(.+?)\s*(?:—|–|-)\s*[\d.,]", line)
        if m:
            offers.append((line, m.group(1).strip()))
    return name_line, offers

def url_for_store(store, urls, product):
    url = (urls or {}).get(store)
    if url: return url
    sn = normalize_name(store)
    for k, v in (urls or {}).items():
        if v and sn and (sn in normalize_name(k) or normalize_name(k) in sn):
            return v
    return fallback_search_url(f"{product} {store}")

def send_product_answer(from_number, bot_id, lang, txt, urls, product, best_only=False):
    name_line, offers = parse_answer_lines(txt)
    send_whatsapp_text(from_number, name_line or txt.splitlines()[0], bot_id)
    if not offers:
        if txt and txt!= name_line:
            send_whatsapp_text(from_number, txt, bot_id)
        return
    for line, store in (offers[:1] if best_only else offers[:4]):
        send_whatsapp_cta(from_number, line, url_for_store(store, urls, product), bot_id, f"🛒 {store[:18]}")

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
    return hashlib.sha256(f"{norm}|{lang}".encode()).hexdigest()

def cache_get(query, lang):
    now = time.time()
    hit = SEARCH_CACHE.get(cache_key(query, lang))
    if hit and (now - hit["ts"]) < CACHE_TTL:
        return hit["txt"], dict(hit["urls"])
    qt = norm_tokens(query)
    if not qt: return None
    best, best_score = None, 0.0
    for entry in SEARCH_CACHE.values():
        if entry.get("lang")!= lang or (now - entry["ts"]) >= CACHE_TTL: continue
        et = entry.get("tokens") or set()
        if not et: continue
        inter = len(qt & et)
        score = inter / len(qt | et) if (qt | et) else 0
        if has_model_token(qt, et): score += 0.30
        if score > best_score: best, best_score = entry, score
    if best and best_score >= 0.60:
        return best["txt"], dict(best["urls"])
    return None

def cache_put(query, lang, txt, urls):
    if not txt: return
    if len(SEARCH_CACHE) >= CACHE_MAX:
        oldest = min(SEARCH_CACHE, key=lambda k: SEARCH_CACHE[k]["ts"])
        SEARCH_CACHE.pop(oldest, None)
    SEARCH_CACHE[cache_key(query, lang)] = {"txt": txt, "urls": dict(urls), "ts": time.time(), "tokens": norm_tokens(query), "query": query, "lang": lang}

IDENTIFY_SYSTEM = """أنت خبير تعرف على المنتجات. انظر للصورة واكتب الاسم التجاري القياسي للمنتج بصيغة ثابتة دائماً:
[البراند] [نوع المنتج] [رقم الموديل باللاتيني إن ظهر] [اللون/النكهة] [الحجم/الوزن إن ظهر]
رقم الموديل هو أهم عنصر — دور عليه على العبوة أو الذراع أو الملصق (مثل RB3721، SM-S928، MQ2V3).
سطر واحد فقط."""

MSG = {
    "ar": {
        "identifying": "ثواني بس.. أحدد المنتج وأدور لك الأفضل!",
        "searching": "🔍 أدور لك على {q}...",
        "not_found": "ما لقيت",
        "cant_identify": "ما قدرت أحدد المنتج",
        "multi_text": "تمام لقيت {c} منتجات، أسوي سلة...",
        "multi_images": "تمام لقطت {c} منتجات، أسوي سلة...",
        "maps_body": "📍 بحثك الأخير كان عن ({p})\n\nجهزت لك أقرب المحلات اللي تبيعه حولك، اضغط الزر وافتح الخريطة 👇",
        "maps_btn": "📍 افتح الخريطة",
        "service_maps_body": "📍 أقرب مزودي هالخدمة حولك على الخريطة 👇",
        "lang_saved": "تمام، بكلمك عربي من هني ورايح 🇰🇼",
    },
    "en": {
        "identifying": "One sec.. identifying the product!",
        "searching": "🔍 Looking up {q}...",
        "not_found": "Couldn't find it",
        "cant_identify": "Couldn't identify the product",
        "multi_text": "Got it, found {c} products...",
        "multi_images": "Nice, spotted {c} products...",
        "maps_body": "📍 Your last search was ({p})\n\nClosest stores around you on map 👇",
        "maps_btn": "📍 Open Map",
        "service_maps_body": "📍 Nearest providers on map 👇",
        "lang_saved": "Great, I'll speak English from now on 🇬🇧",
    },
}

LANG_INSTR = {
    "ar": "رد باللغة العربية فقط.",
    "en": "Respond ONLY in English. Keep format and emojis, translate labels. Prices in KWD.",
}

def T(lang, key, **kw):
    return MSG.get(lang, MSG["ar"])[key].format(**kw) if kw else MSG.get(lang, MSG["ar"])[key]

def detect_lang(text):
    if re.search(r"[\u0600-\u06FF]", text or ""): return "ar"
    if re.search(r"[A-Za-z]", text or ""): return "en"
    return None

SYSTEM_PROMPT = """
أنت مساعد تسوق كويتي. استخدم بحث Google فعلياً للأسعار والتقييمات الحالية في الكويت.
📦 [اسم المنتج]
✅ [المتجر الأرخص] — [السعر] د.ك
• [المتجر الثاني] — [السعر] د.ك
• [المتجر الثالث] — [السعر] د.ك
🛒 مصدر العروض ClicFlyer — قاعدة إلزامية لمنتجات التموينات
في النهاية: LINKS: اسم=domain.com, اسم=domain.com
ممنوع روابط ظاهرة. ممنوع Markdown.
"""

def get_final_url(url: str):
    if not url or not url.startswith(("http://", "https://")): return ""
    try:
        r = requests.get(url, allow_redirects=True, timeout=12, stream=True, headers=HEADERS)
        final = r.url or url
        r.close()
        return final if final.startswith(("http://", "https://")) else url
    except: return url

def resolve_all(uris): return list(RESOLVER.map(get_final_url, uris))
def clean_domain(dom): return re.sub(r"^https?://", "", (dom or "").strip().lower()).replace("www.", "").split("/")[0]
def domain_key(dom): return clean_domain(dom).split(".")[0]
def normalize_name(value): return re.sub(r"[^\w\u0600-\u06FF]+", "", (value or "").lower())

def extract_store_names(text):
    stores = []
    for line in (text or "").splitlines():
        m = re.match(r"^\s*🏪\s*[^:：]*[:：]\s*(.+?)\s*$", line)
        if m:
            name = m.group(1).strip()
            if name and name not in stores: stores.insert(0, name)
            continue
        m = re.match(r"^\s*(?:✅|🏆|•)\s*(.+?)\s*(?:—|–|-)\s*[\d.,]+", line)
        if m:
            name = m.group(1).strip()
            if name and name not in stores: stores.append(name)
    return stores[:5]

def source_label(title, url):
    title = (title or "").strip()
    if title: return title[:40]
    try: return urllib.parse.urlparse(url).netloc.replace("www.", "").split(".")[0] or "المتجر"
    except: return "المتجر"

def call_gemini(parts, system=SYSTEM_PROMPT, use_search=True):
    payload = {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": parts}], "generationConfig": {"temperature": 0, "maxOutputTokens": 2000}}
    if use_search: payload["tools"] = [{"google_search": {}}]
    try:
        r = requests.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload, timeout=90)
        if r.status_code >= 400: return "", {}
        data = r.json()
        cand = (data.get("candidates") or [None])[0]
        if not cand: return "", {}
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
                    if name and "." in dom: pairs.append((name, dom))
            text = re.sub(r"(?im)^\s*LINKS\s*:.*$", "", text).strip()
        text = re.sub(r"https?://\S+", "", text).replace("**", "").strip()
        metadata = cand.get("groundingMetadata", {}) or {}
        chunks = metadata.get("groundingChunks", []) or []
        uris = [(c.get("web") or {}).get("uri", "") for c in chunks]
        finals = resolve_all(uris[:15]) if uris else []
        records = []
        for i, chunk in enumerate(chunks[:15]):
            web = chunk.get("web") or {}
            records.append({"title": web.get("title", ""), "raw": web.get("uri", ""), "url": finals[i] if i < len(finals) else web.get("uri", "")})
        urls_map = {}; used_urls = set(); stores = extract_store_names(text)
        supports = metadata.get("groundingSupports", []) or []
        for store in stores:
            sn = normalize_name(store)
            for sup in supports:
                seg = (sup.get("segment") or {}).get("text", "")
                if sn and sn in normalize_name(seg):
                    for idx in sup.get("groundingChunkIndices", []) or []:
                        if 0 <= idx < len(records):
                            url = records[idx]["url"]
                            if url and url not in used_urls:
                                urls_map[store] = url; used_urls.add(url); break
                if store in urls_map: break
        for name, dom in pairs:
            if name in urls_map: continue
            key = domain_key(dom)
            for rec in records:
                if rec["url"] and key in f"{rec['title']} {rec['raw']} {rec['url']}".lower() and rec["url"] not in used_urls:
                    urls_map[name] = rec["url"]; used_urls.add(rec["url"]); break
        if not urls_map:
            for rec in records:
                if not rec["url"] or rec["url"] in used_urls: continue
                label = source_label(rec["title"], rec["url"])
                if label not in urls_map:
                    urls_map[label] = rec["url"]; used_urls.add(rec["url"])
                if len(urls_map) == 3: break
        return text, dict(list(urls_map.items())[:4])
    except Exception as e:
        print(f"Gemini err {e}"); return "", {}

SEARCH_RUNS = int(os.environ.get("SEARCH_RUNS", "2"))
def answer_score(txt, urls):
    s, l = result_quality(txt, urls)
    return s*2 + l*3 + (1 if txt and "📦" in txt else 0)

def best_of_search(parts, lang):
    try:
        futs = [SEARCH_POOL.submit(call_gemini, parts) for _ in range(SEARCH_RUNS)]
        results = [f.result() for f in futs]
    except: return call_gemini(parts)
    results = [(t,u) for t,u in results if t]
    if not results: return "", {}
    scored = sorted(results, key=lambda r: answer_score(r[0], r[1]), reverse=True)
    best_txt, best_urls = scored[0]
    merged = dict(best_urls)
    for _, u in scored[1:]:
        for n, link in u.items():
            if n not in merged and link not in merged.values(): merged[n] = link
    return best_txt, dict(list(merged.items())[:4])

def search_product(query, lang, prompt_text=None):
    cached = cache_get(query, lang)
    if cached: return cached
    text_part = prompt_text or f"ابحث عن {query} في الكويت. {LANG_INSTR[lang]}"
    txt, urls = best_of_search([{"text": text_part}], lang)
    s, l = result_quality(txt, urls)
    if (s >= CACHE_MIN_STORES and l >= CACHE_MIN_LINKS) or (s==0 and txt and len(txt)>=120):
        cache_put(query, lang, txt, urls)
    return txt, urls

def get_smart_maps_query(product):
    """نفس طريقتك القديمة بالضبط لاختيار عبارة الخريطة الذكية"""
    try:
        cat_text, _ = call_gemini([{"text": f"المنتج: {product}"}], system=PROMPT_CATEGORY, use_search=False)
        cat = cat_text.strip().splitlines()[0].strip() if cat_text else product
        return cat if cat else product
    except:
        return product

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
    try: requests.post(url,json=payload,headers=h,timeout=15)
    except: pass

def send_whatsapp_cta(to,body,link,bot_id,title):
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    payload={"messaging_product":"whatsapp","to":to,"type":"interactive","interactive":{"type":"cta_url","body":{"text":body[:1024]},"action":{"name":"cta_url","parameters":{"display_text":title[:20],"url":link}}}}
    try: requests.post(url,json=payload,headers=h,timeout=15)
    except: pass

def send_whatsapp_buttons(to, body, buttons, bot_id):
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    btns=[{"type":"reply","reply":{"id":b["id"],"title":b["title"][:20]}} for b in buttons[:3]]
    payload={"messaging_product":"whatsapp","to":to,"type":"interactive","interactive":{"type":"button","body":{"text":body[:1024]},"action":{"buttons":btns}}}
    try: requests.post(url,json=payload,headers=h,timeout=15)
    except: pass

def send_language_choice(to, bot_id):
    body = "🌐 اختر لغتك المفضلة\nChoose your preferred language"
    send_whatsapp_buttons(to, body, [{"id": "lang_ar", "title": "العربية 🇰🇼"}, {"id": "lang_en", "title": "English 🇬🇧"}], bot_id)

def extract_service_contacts(txt):
    contacts=[]
    for line in (txt or "").splitlines():
        m=re.match(r"^\s*(?:🏆|•)\s*(.+?)\s*\(\s*(?:هاتف|Phone|phone|Tel|tel)\s*:\s*([\d\s\-]+)\)",line)
        if not m: continue
        name=m.group(1).strip()[:25]
        num=re.sub(r"\D","",m.group(2))
        if len(num)==8 and num[0] in "2569":
            contacts.append({"name":{"formatted_name":name,"first_name":name},"phones":[{"phone":f"+965{num}","type":"WORK","wa_id":f"965{num}"}]})
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
            caption = (msg.get("image",{}) or {}).get("caption","").strip()
            cap_lang = detect_lang(caption) if caption else None
            if cap_lang: USER_LANG[from_number] = cap_lang
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
        if len(pend["images"])==1: process_single_image(pend["images"][0], pend["bot_id"], lang)
        else: process_multi_images(pend["images"], from_number, pend["bot_id"], lang)
    else: send_whatsapp_text(from_number, T(lang,"lang_saved"), bot_id)

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
    ident,_=call_gemini([{"inline_data":{"mime_type":mime,"data":b64}},{"text":"ما اسم هذا المنتج؟"}], system=IDENTIFY_SYSTEM, use_search=False)
    product_name = ident.strip().splitlines()[0].strip() if ident else ""
    if product_name and caption:
        request_query = f"{caption} — {product_name}"
        prompt_text = f"المنتج في الصورة: {product_name}\nطلب المستخدم عنه: {caption}\n{LANG_INSTR[lang]}"
        txt,urls=search_product(request_query, lang, prompt_text=prompt_text)
        LAST_SEARCH[from_number] = {"product": request_query}
    elif product_name:
        txt,urls=search_product(product_name, lang)
        LAST_SEARCH[from_number] = {"product": product_name}
    else:
        req = caption if caption else "ما هذا المنتج؟ ابحث عن سعره الحالي في الكويت."
        txt,urls=best_of_search([{"inline_data":{"mime_type":mime,"data":b64}},{"text":f"{req} {LANG_INSTR[lang]}"}], lang)
        name_m = re.search(r"📦\s*(.+)", txt or "")
        product_name = name_m.group(1).strip() if name_m else "المنتج"
        LAST_SEARCH[from_number] = {"product": f"{caption} — {product_name}" if caption else product_name}
    if not txt:
        send_whatsapp_text(from_number, T(lang,"cant_identify"), bot_id); return
    request_for_maps = (LAST_SEARCH.get(from_number) or {}).get("product") or product_name
    if extract_service_contacts(txt):
        send_whatsapp_text(from_number, txt, bot_id)
        smart_q = get_smart_maps_query(request_for_maps)
        maps_url = f"https://www.google.com/maps/search/{urllib.parse.quote(smart_q)}"
        send_whatsapp_cta(from_number, T(lang,"service_maps_body"), maps_url, bot_id, T(lang,"maps_btn"))
        return
    if not extract_store_names(txt):
        send_whatsapp_text(from_number, txt, bot_id); return
    send_product_answer(from_number, bot_id, lang, txt, urls, product_name)
    # زر الخريطة مباشرة بنفس طريقة البحث الذكية القديمة - بدون طلب لوكيشن
    if product_name and product_name!= "المنتج":
        smart_q = get_smart_maps_query(product_name)
        maps_url = f"https://www.google.com/maps/search/{urllib.parse.quote(smart_q)}"
        send_whatsapp_cta(from_number, T(lang,"maps_body",p=product_name), maps_url, bot_id, T(lang,"maps_btn"))

def identify_image_product(msg):
    try:
        b64,mime=download_whatsapp_media(msg["image"]["id"])
        ident,_=call_gemini([{"inline_data":{"mime_type":mime,"data":b64}},{"text":"ما اسم هذا المنتج؟"}], system=IDENTIFY_SYSTEM, use_search=False)
        return ident.strip().splitlines()[0].strip() if ident else ""
    except: return ""

def process_cart(products, from_number, bot_id, lang="ar"):
    results = list(WORKERS.map(lambda p: (p, *search_product(p, lang)), products))
    any_ok = False
    for p, txt, urls in results:
        if not txt: continue
        any_ok = True
        send_product_answer(from_number, bot_id, lang, txt, urls, p, best_only=True)
    if not any_ok:
        send_whatsapp_text(from_number, T(lang, "not_found"), bot_id); return
    LAST_SEARCH[from_number] = {"product": products[0]}
    smart_q = get_smart_maps_query(products[0])
    maps_url = f"https://www.google.com/maps/search/{urllib.parse.quote(smart_q)}"
    send_whatsapp_cta(from_number, T(lang,"maps_body",p=products[0]), maps_url, bot_id, T(lang,"maps_btn"))

def process_multi_images(messages,from_number,bot_id,lang="ar"):
    send_whatsapp_text(from_number,T(lang,"multi_images",c=len(messages)),bot_id)
    names=[n for n in WORKERS.map(identify_image_product,messages) if n]
    if not names:
        send_whatsapp_text(from_number,T(lang,"cant_identify"),bot_id); return
    process_cart(names, from_number, bot_id, lang)

def process_text_message(message,bot_id):
    from_number=message["from"]; user_text=message["text"]["body"]
    cmd=re.sub(r"[^\w\u0600-\u06FF]","",user_text.strip().lower())
    if cmd in ("لغة","اللغة","غيراللغة","language","lang","changelanguage"):
        send_language_choice(from_number, bot_id); return
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
        LAST_SEARCH[from_number] = {"product": products[0]}
        if not txt:
            send_whatsapp_text(from_number, T(lang,"not_found"), bot_id); return
        if extract_service_contacts(txt):
            send_whatsapp_text(from_number, txt, bot_id)
            smart_q = get_smart_maps_query(products[0])
            maps_url = f"https://www.google.com/maps/search/{urllib.parse.quote(smart_q)}"
            send_whatsapp_cta(from_number, T(lang,"service_maps_body"), maps_url, bot_id, T(lang,"maps_btn"))
            return
        if not extract_store_names(txt):
            send_whatsapp_text(from_number, txt, bot_id); return
        send_product_answer(from_number, bot_id, lang, txt, urls, products[0])
        # زر الخريطة مباشرة بنفس طريقة البحث الذكية القديمة - بدون طلب لوكيشن
        smart_q = get_smart_maps_query(products[0])
        maps_url = f"https://www.google.com/maps/search/{urllib.parse.quote(smart_q)}"
        send_whatsapp_cta(from_number, T(lang,"maps_body",p=products[0]), maps_url, bot_id, T(lang,"maps_btn"))
    else:
        send_whatsapp_text(from_number,T(lang,"multi_text",c=len(products)),bot_id)
        process_cart(products, from_number, bot_id, lang)

def process_location_message(message, bot_id):
    # يبقى شغال لو واحد دز لوكيشن بنفسه - بنفس طريقتك القديمة مع الاحداثيات
    from_number = message["from"]
    lat = message["location"]["latitude"]
    lng = message["location"]["longitude"]
    lang = USER_LANG.get(from_number, "ar")
    last_search = LAST_SEARCH.get(from_number)
    if not last_search or not last_search.get("product"):
        send_whatsapp_text(from_number, T(lang,"no_saved_product"), bot_id); return
    product = last_search["product"]
    smart_q = get_smart_maps_query(product)
    maps_url = f"https://www.google.com/maps/search/{urllib.parse.quote(smart_q)}/@{lat},{lng},15z"
    send_whatsapp_cta(from_number, T(lang,"maps_body",p=product), maps_url, bot_id, T(lang,"maps_btn"))

@app.get("/")
async def health(): return {"status":"v29 Smart Maps Without Location Request"}
