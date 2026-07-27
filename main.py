# -*- coding: utf-8 -*-
import os, re, time, base64, requests, uuid, asyncio, urllib.parse
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
CARTS = {}
IMAGE_BUFFER = defaultdict(lambda: {"images": [], "time": 0, "bot_id": ""})
LAST_SEARCH = {} # لحفظ اسم آخر منتج بحث عنه المستخدم

BUFFER_SECONDS = 4
RESOLVER = ThreadPoolExecutor(max_workers=6)
WORKERS = ThreadPoolExecutor(max_workers=3)
HEADERS = {"User-Agent": "Mozilla/5.0"}

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

إذا كان المنتج عقاراً أو سيارة، أعطِ تقييماً متوسطاً ونطاق سعر مختصراً جداً.
"""

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

def extract_store_names(text):
    stores = []
    for line in (text or "").splitlines():
        m = re.match(r"^\s*(?:✅|🏆|•)\s*(.+?)\s*(?:—|–|-)\s*[\d.,]+", line)
        if m:
            name = m.group(1).strip()
            if name and name not in stores:
                stores.append(name)
    return stores[:3]

def source_label(title, url):
    title = (title or "").strip()
    if title:
        return title[:40]
    try:
        host = urllib.parse.urlparse(url).netloc.replace("www.", "")
        return host.split(".")[0] or "المتجر"
    except Exception:
        return "المتجر"

def call_gemini(parts, system=SYSTEM_PROMPT):
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": parts}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2000},
    }
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
                            if url and url not in used_urls:
                                urls_map[store] = url
                                used_urls.add(url)
                                break
                if store in urls_map:
                    break

        # Fallback: match the mandatory LINKS domains against raw/final URLs and titles.
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

        # Last fallback: match store names directly against source titles.
        for store in stores:
            if store in urls_map:
                continue
            store_norm = normalize_name(store)
            for rec in records:
                if rec["url"] and store_norm and store_norm in normalize_name(rec["title"]):
                    if rec["url"] not in used_urls:
                        urls_map[store] = rec["url"]
                        used_urls.add(rec["url"])
                        break

        # If Gemini omitted LINKS/support mapping, still expose up to 3 grounded sources.
        if not urls_map:
            for rec in records:
                url = rec["url"]
                if not url or url in used_urls:
                    continue
                label = source_label(rec["title"], url)
                if label not in urls_map:
                    urls_map[label] = url
                    used_urls.add(url)
                if len(urls_map) == 3:
                    break

        print({
            "stores": stores,
            "links_pairs": pairs,
            "grounding_chunks": len(chunks),
            "resolved_buttons": list(urls_map.keys()),
        })
        return text, dict(list(urls_map.items())[:3])
    except Exception as e:
        print(f"Gemini err {e}"); return "", {}

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

def send_whatsapp_contacts(to, contacts, bot_id):
    """إرسال بطاقات جهات اتصال (يقدر العميل يحفظها أو يتصل مباشرة)"""
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    payload={"messaging_product":"whatsapp","to":to,"type":"contacts","contacts":contacts}
    try:
        r = requests.post(url,json=payload,headers=h,timeout=15)
        if not r.ok:
            print(f"WhatsApp contacts error {r.status_code}: {r.text[:500]}")
        return r.ok
    except Exception as e:
        print(f"WhatsApp contacts exception: {e}")
        return False

def extract_service_contacts(txt):
    """يستخرج (اسم المزود + رقمه) من سطور 🏆 و • إذا كان الرد عن خدمة"""
    contacts=[]
    for line in (txt or "").splitlines():
        m=re.match(r"^\s*(?:🏆|•)\s*(.+?)\s*\(\s*هاتف\s*:\s*([\d\s\-]+)\)",line)
        if not m: continue
        name=m.group(1).strip()[:25]
        num=re.sub(r"\D","",m.group(2))
        # أرقام الكويت: 8 خانات تبدأ بـ 2 أو 5 أو 6 أو 9
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
            IMAGE_BUFFER[from_number]["images"].append(msg); IMAGE_BUFFER[from_number]["time"]=time.time(); IMAGE_BUFFER[from_number]["bot_id"]=bot_id
            if len(IMAGE_BUFFER[from_number]["images"])==1:
                background_tasks.add_task(process_image_buffer,from_number)
        elif msg.get("type")=="text":
            background_tasks.add_task(process_text_message,msg,bot_id)
        elif msg.get("type")=="location":
            background_tasks.add_task(process_location_message,msg,bot_id)
            
    except Exception as e: print(f"webhook err {e}")
    return {"status":"ok"}

async def process_image_buffer(from_number):
    await asyncio.sleep(BUFFER_SECONDS)
    data=IMAGE_BUFFER.pop(from_number,None)
    if not data: return
    if len(data["images"])==1: await asyncio.to_thread(process_single_image,data["images"][0],data["bot_id"])
    else: await asyncio.to_thread(process_multi_images,data["images"],from_number,data["bot_id"])

def process_single_image(message,bot_id):
    from_number=message["from"]
    send_whatsapp_text(from_number,"ثواني بس.. أحدد المنتج وأدور لك الأرخص!",bot_id)
    b64,mime=download_whatsapp_media(message["image"]["id"])
    txt,urls=call_gemini([{"inline_data":{"mime_type":mime,"data":b64}},{"text":"ما هذا المنتج؟ ابحث عن سعره الحالي في الكويت"}])
    if not txt: txt="ما قدرت أحدد المنتج"
    send_whatsapp_text(from_number,txt,bot_id)
    
    name_m = re.search(r"📦\s*(.+)", txt)
    product_name = name_m.group(1).strip() if name_m else "المنتج"
    LAST_SEARCH[from_number] = {"product": product_name}

    for n,u in urls.items():
        if u: send_whatsapp_cta(from_number,f"تسوق من {n} 👇",u,bot_id,f"🛒 {n[:18]}")

    if product_name and product_name != "المنتج":
        send_whatsapp_text(from_number, "تبي أقرب محل يبيعه؟ 📍\n\nسهلة، ٣ خطوات:\n1️⃣ اضغط ➕ (أيفون) أو 📎 (أندرويد) جنب خانة الكتابة\n2️⃣ اختر الموقع Location\n3️⃣ اضغط إرسال موقعك الحالي\n\nوعلى طول أرد لك بأقرب المحلات على الخريطة 👇", bot_id)

def fetch_product_from_image(msg):
    try:
        b64,mime=download_whatsapp_media(msg["image"]["id"])
        txt,urls=call_gemini([{"inline_data":{"mime_type":mime,"data":b64}},{"text":"حدد المنتج وابحث عن سعره"}])
        name_m=re.search(r"📦\s*(.+)",txt); name=(name_m.group(1).strip() if name_m else "منتج")[:50]
        pm=re.search(r"(?:✅|🏆).*?(?:—|-|–)\s*([\d\.]+)",txt); price=float(pm.group(1)) if pm else 0
        curl=list(urls.values())[0] if urls else ""; cstore=list(urls.keys())[0] if urls else "متجر"
        return {"name":name,"store":cstore,"price":price,"url":curl,"all_urls":urls}
    except: return {"name":"منتج","store":"متجر","price":0,"url":"","all_urls":{}}

def fetch_product_from_text(prod):
    try:
        txt,urls=call_gemini([{"text":f"ابحث عن {prod} في الكويت"}])
        m=re.search(r"(?:✅|🏆).*?(?:—|-|–)\s*([\d\.]+)",txt); price=float(m.group(1)) if m else 0
        curl=list(urls.values())[0] if urls else ""; cstore=list(urls.keys())[0] if urls else "متجر"
        return {"name":prod,"store":cstore,"price":price,"url":curl,"all_urls":urls}
    except: return {"name":prod,"store":"متجر","price":0,"url":"","all_urls":{}}

def finalize_cart(from_number,bot_id,items):
    total=sum(it["price"] for it in items); cart_id=uuid.uuid4().hex[:8]
    CARTS[cart_id]={"products":items,"total":total}
    summ="\n".join([f"• {it['name']} - {it['price']} د.ك ({it['store']})" for it in items])
    send_whatsapp_text(from_number,f"🛒 سلتك جاهزة:\n{summ}\n\n💰 الإجمالي: {total:.3f} د.ك",bot_id)
    domain=os.environ.get("RAILWAY_PUBLIC_DOMAIN","fanzia.up.railway.app")
    send_whatsapp_cta(from_number,"افتح السلة",f"https://{domain}/cart/{cart_id}",bot_id,"🛒 افتح السلة")

def process_multi_images(messages,from_number,bot_id):
    send_whatsapp_text(from_number,f"تمام لقطت {len(messages)} منتجات، أسوي سلة...",bot_id)
    items=list(WORKERS.map(fetch_product_from_image,messages)); finalize_cart(from_number,bot_id,items)

def process_text_message(message,bot_id):
    from_number=message["from"]; user_text=message["text"]["body"]; products=extract_products(user_text)
    if len(products)==1:
        send_whatsapp_text(from_number,f"🔍 أدور لك على {products[0]}...",bot_id)
        txt,urls=call_gemini([{"text":f"ابحث عن {products[0]} في الكويت"}])
        send_whatsapp_text(from_number,txt or "ما لقيت",bot_id)
        
        LAST_SEARCH[from_number] = {"product": products[0]}

        # إذا الرد كان عن خدمة وفيه أرقام، نرسلها كبطاقات جهات اتصال جاهزة للحفظ والاتصال
        contacts = extract_service_contacts(txt)
        if contacts:
            send_whatsapp_contacts(from_number, contacts, bot_id)
            
        for n,u in urls.items():
            if u: send_whatsapp_cta(from_number,f"تسوق من {n} 👇",u,bot_id,f"🛒 {n[:18]}")

        send_whatsapp_text(from_number, "📍 تبي تشتري المنتج من مكان قريب منك؟ دز لي موقعك (Location) بالواتساب الحين وأطلع لك أقرب مكان يبيعه بالخريطة!", bot_id)
            
    else:
        LAST_SEARCH[from_number] = {"product": products[0]}
        send_whatsapp_text(from_number,f"تمام لقيت {len(products)} منتجات، أسوي سلة...",bot_id)
        items=list(WORKERS.map(fetch_product_from_text,products)); finalize_cart(from_number,bot_id,items)

def process_location_message(message, bot_id):
    from_number = message["from"]
    lat = message["location"]["latitude"]
    lng = message["location"]["longitude"]

    last_search = LAST_SEARCH.get(from_number)
    if not last_search or not last_search.get("product"):
        send_whatsapp_text(from_number, "ما عندي منتج محفوظ حالياً 😅. ابحث عن منتج أول، وبعدها دز موقعك عشان أدلك على أقرب مكان يبيعه!", bot_id)
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

    # الرابط الجديد بصيغة أنظف
    safe_category = urllib.parse.quote(category)
    maps_url = f"https://www.google.com/maps/search/{safe_category}/@{lat},{lng},15z"
    
    body = f"📍 بحثك الأخير كان عن ({product})\n\nجهزت لك أقرب المحلات اللي تبيعه حولك، اضغط الزر وافتح الخريطة 👇"

    # هذا هو التعديل الجمالي - زر بدل رابط طويل
    send_whatsapp_cta(from_number, body, maps_url, bot_id, "📍 افتح الخريطة")

@app.get("/cart/{cart_id}", response_class=HTMLResponse)
async def cart_page(cart_id: str):
    cart=CARTS.get(cart_id)
    if not cart: return HTMLResponse("<h1>السلة انتهت</h1>",404)
    rows="".join([f"<div class='p-4 border-b flex justify-between'><div><b>{it['name']}</b><br><span class='text-sm text-gray-500'>{it['store']} - {it['price']} د.ك</span></div><a href='{it['url']}' target='_blank' class='bg-black text-white px-4 py-2 rounded'>شراء</a></div>" for it in cart["products"]])
    return HTMLResponse(f"<html dir='rtl'><head><meta name='viewport' content='width=device-width'><script src='https://cdn.tailwindcss.com'></script></head><body><div class='max-w-lg mx-auto bg-white'><div class='p-5 bg-black text-white'><h1>🛒 سلتك</h1></div>{rows}</div></body></html>")

@app.get("/")
async def health(): return {"status":"v12 Best-Rated Recommendations"}
