# -*- coding: utf-8 -*-
import os, re, time, base64, requests, uuid, asyncio
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import HTMLResponse

app = FastAPI()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-pro-preview")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_COOP_BOT_TOKEN")

GRAPH_URL = "https://graph.facebook.com/v20.0"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

processed_ids = deque(maxlen=1000)
CARTS = {}
IMAGE_BUFFER = defaultdict(lambda: {"images": [], "time": 0, "bot_id": ""})
BUFFER_SECONDS = 4
RESOLVER = ThreadPoolExecutor(max_workers=6)   # فك الروابط بالتوازي
WORKERS = ThreadPoolExecutor(max_workers=3)    # منتجات السلة بالتوازي

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

SYSTEM_PROMPT = """
أنت مساعد تسوق كويتي. رد بهذا الشكل فقط:
📦 [اسم المنتج]
✅ [المتجر الأرخص] — [السعر] د.ك
• [المتجر الثاني] — [السعر] د.ك
• [المتجر الثالث] — [السعر] د.ك

ثم سطر أخير إلزامي في كل رد فيه أسعار — لا تنسه أبداً:
LINKS: اسم المتجر الأول=دومينه, اسم المتجر الثاني=دومينه, اسم المتجر الثالث=دومينه
مثال حرفي: LINKS: إكسايت=xcite.com, بلينك=blink.com.kw, يوريكا=eureka.com.kw
بنفس ترتيب قائمة الأسعار. الدومين هو موقع المتجر الفعلي الذي وجدت السعر فيه.

ممنوع روابط ظاهرة في النص. ممنوع Markdown أو نجوم.
"""


# ================= عروض الجمعيات من الانستجرام =================
IG_USER_ID = os.environ.get("IG_USER_ID", "")
IG_TOKEN = os.environ.get("IG_TOKEN", "") or WHATSAPP_TOKEN
COOP_ACCOUNTS = [a.strip().lstrip("@") for a in os.environ.get("COOP_ACCOUNTS", "").split(",") if a.strip()]
OFFERS_REFRESH_HOURS = int(os.environ.get("OFFERS_REFRESH_HOURS", "8"))
POSTS_PER_COOP = int(os.environ.get("POSTS_PER_COOP", "3"))

OFFERS = {"text": "", "updated": 0}

EXTRACT_PROMPT = """هذه صورة فلاير عروض من جمعية تعاونية كويتية.
استخرج كل المنتجات وأسعارها، سطر لكل منتج بهذه الصيغة فقط:
اسم المنتج | السعر د.ك
لا تكتب أي شيء آخر ولا مقدمات.
إذا الصورة ليست فلاير عروض فيه منتجات وأسعار (مثل شعار أو تهنئة أو إعلان عام) رد بكلمة واحدة فقط: NONE"""


def call_gemini_raw(parts, temperature=0.1, max_tokens=3000):
    """نداء Gemini بدون بحث جوجل — للاستخراج من الفلايرات والبحث في العروض المخزنة"""
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
    }
    try:
        r = requests.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload, timeout=90)
        if r.status_code >= 400:
            print(f"GEMINI RAW {r.status_code}: {r.text[:200]}")
            return ""
        data = r.json()
        return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]).strip()
    except Exception as e:
        print(f"gemini raw err {e}")
        return ""


def fetch_coop_posts(username: str, limit: int = 3):
    """يجيب آخر منشورات جمعية (حساب Business عام) عبر Business Discovery API"""
    fields = (f"business_discovery.username({username})"
              f"{{media.limit({limit})"
              f"{{media_url,caption,timestamp,media_type,children{{media_url,media_type}}}}}}")
    try:
        r = requests.get(f"{GRAPH_URL}/{IG_USER_ID}",
                         params={"fields": fields, "access_token": IG_TOKEN}, timeout=20)
        data = r.json()
        if "error" in data:
            print(f"IG {username}: {data['error'].get('message', '')[:150]}")
            return []
        media = data.get("business_discovery", {}).get("media", {}).get("data", [])
        posts = []
        for m in media:
            urls = []
            if m.get("media_type") == "CAROUSEL_ALBUM":
                for ch in m.get("children", {}).get("data", []):
                    if ch.get("media_type") == "IMAGE" and ch.get("media_url"):
                        urls.append(ch["media_url"])
            elif m.get("media_type") == "IMAGE" and m.get("media_url"):
                urls.append(m["media_url"])
            if urls:
                posts.append({"urls": urls[:4], "caption": m.get("caption", "")})
        return posts
    except Exception as e:
        print(f"IG fetch err {username}: {e}")
        return []


def extract_offers_from_image(img_url: str) -> str:
    """ينزل صورة الفلاير ويستخرج منها المنتجات والأسعار عبر Gemini vision"""
    try:
        img = requests.get(img_url, timeout=30, headers=HEADERS)
        if img.status_code >= 400 or len(img.content) < 1000:
            return ""
        mime = img.headers.get("Content-Type", "image/jpeg").split(";")[0]
        if not mime.startswith("image/"):
            mime = "image/jpeg"
        b64 = base64.b64encode(img.content).decode()
        txt = call_gemini_raw([
            {"inline_data": {"mime_type": mime, "data": b64}},
            {"text": EXTRACT_PROMPT}
        ])
        if not txt or "NONE" in txt[:10].upper():
            return ""
        return txt
    except Exception as e:
        print(f"extract err {e}")
        return ""


def refresh_offers():
    """يلف على حسابات الجمعيات ويحدّث قاعدة العروض"""
    if not IG_USER_ID or not COOP_ACCOUNTS:
        print("OFFERS SKIP: IG_USER_ID أو COOP_ACCOUNTS غير مضبوطين في المتغيرات")
        return
    print(f"OFFERS: بدء التحديث من {len(COOP_ACCOUNTS)} جمعية...")
    blocks = []
    for coop in COOP_ACCOUNTS:
        posts = fetch_coop_posts(coop, limit=POSTS_PER_COOP)
        coop_lines = []
        for p in posts:
            for u in p["urls"]:
                ext = extract_offers_from_image(u)
                if ext:
                    coop_lines.append(ext)
                time.sleep(1)  # رفق بحصة Gemini المجانية
        if coop_lines:
            blocks.append(f"🏪 {coop}:\n" + "\n".join(coop_lines))
    if blocks:
        OFFERS["text"] = "\n\n".join(blocks)
        OFFERS["updated"] = time.time()
    print(f"OFFERS: انتهى — {len(OFFERS['text'])} حرف من {len(blocks)} جمعية")


async def offers_scheduler():
    while True:
        try:
            await asyncio.to_thread(refresh_offers)
        except Exception as e:
            print(f"scheduler err {e}")
        await asyncio.sleep(OFFERS_REFRESH_HOURS * 3600)


@app.on_event("startup")
async def startup():
    asyncio.create_task(offers_scheduler())


def search_in_offers(query: str) -> str:
    """يدور المنتج داخل عروض الجمعيات المستخرجة من الفلايرات"""
    if not OFFERS["text"]:
        return ""
    prompt = f"""هذه قائمة عروض الجمعيات التعاونية الحالية في الكويت (مستخرجة من فلايراتهم):

{OFFERS['text'][:15000]}

السؤال: هل يوجد "{query}" أو منتج مطابق/مشابه جداً له في القائمة أعلاه؟
إذا موجود، رد بهذا الشكل فقط بدون أي إضافات:
🏪 عروض الجمعيات:
• [اسم الجمعية] — [اسم المنتج] — [السعر] د.ك
(أقصى ثلاثة أسطر، الأرخص أولاً)
إذا غير موجود رد بكلمة واحدة فقط: NONE"""
    txt = call_gemini_raw([{"text": prompt}], max_tokens=500)
    if not txt or "NONE" in txt[:10].upper():
        return ""
    return txt


# ================= أدوات الروابط =================
def get_final_url(url: str):
    try:
        r = requests.head(url, allow_redirects=True, timeout=8, headers=HEADERS)
        if r.status_code == 405:
            r = requests.get(url, allow_redirects=True, timeout=8, stream=True, headers=HEADERS)
            r.close()
        final = r.url
        if "vertexaisearch" in final or "grounding-api-redirect" in final:
            return ""
        return final if len(final) < 700 else ""
    except Exception:
        return ""


def resolve_all(uris: list) -> list:
    return list(RESOLVER.map(get_final_url, uris))


def domain_key(dom: str) -> str:
    """xcite.com -> xcite | blink.com.kw -> blink — مفتاح مرن للمطابقة"""
    return dom.replace("www.", "").split(".")[0]


# ================= Gemini =================
def call_gemini(parts: list):
    """يرجع (النص, {اسم المتجر: رابطه النهائي})"""
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": parts}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2000},
    }
    try:
        r = requests.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload, timeout=90)
        if r.status_code >= 400:
            print(f"GEMINI {r.status_code}: {r.text[:200]}")
            return "", {}

        data = r.json()
        cand = data["candidates"][0]
        text = "".join(p.get("text", "") for p in cand["content"]["parts"]).strip()

        # ===== أزواج (اسم المتجر = الدومين) — يقبل صيغة الأزواج والصيغة القديمة (دومينات فقط) =====
        pairs = []
        m = re.search(r"LINKS:\s*(.+)", text, re.I)
        if m:
            raw = m.group(1)
            print(f"LINKS RAW: {raw[:200]}")
            for part in re.split(r"[,،]+", raw):
                part = part.strip()
                if not part:
                    continue
                if "=" in part:
                    name, dom = part.split("=", 1)
                    name, dom = name.strip(), dom.strip().lower()
                else:
                    dom = part.lower()
                    name = domain_key(dom)
                if "." in dom:
                    pairs.append((name, dom))
            text = re.sub(r"\n?LINKS:.*", "", text, flags=re.I).strip()
        else:
            print("LINKS RAW: <missing>")

        # تنظيف النص
        text = re.sub(r"https?://\S+", "", text)
        text = text.replace("**", "").replace("*", "")
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        # ===== الروابط: فك متوازٍ ثم مطابقة الدومين على الرابط النهائي =====
        urls_map = {}
        chunks = cand.get("groundingMetadata", {}).get("groundingChunks", [])
        uris = [c.get("web", {}).get("uri") for c in chunks if c.get("web", {}).get("uri")]
        if uris and pairs:
            finals = resolve_all(uris[:8])
            print(f"PAIRS: {pairs} | CHUNKS: {len(uris)} | FINALS: {[f[:60] for f in finals if f]}")
            for name, dom in pairs:
                key = domain_key(dom)
                for f in finals:
                    if f and key in f.lower().replace("www.", ""):
                        urls_map[name] = f
                        break
        else:
            print(f"LINK SKIP: uris={len(uris)} pairs={len(pairs)}")
        # لا خطة بديلة بروابط عشوائية — رابط غلط أسوأ من بلا رابط

        return text, dict(list(urls_map.items())[:3])
    except Exception as e:
        print(f"Gemini err {e}")
        return "", {}


# ================= أدوات عامة =================
def extract_products(text: str):
    text = re.sub(r'^[•\-\*\d\.\)\s]+', '', text, flags=re.M)
    parts = re.split(r'\s*(?:\n+|\+|,|،| و | & )\s*', text.strip())
    parts = [p.strip() for p in parts if len(p.strip()) > 2]
    if len(parts) <= 1:
        return [text.strip()]
    return parts[:6]


def download_whatsapp_media(media_id: str):
    h = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    meta = requests.get(f"{GRAPH_URL}/{media_id}", headers=h, timeout=20).json()
    url = meta["url"]
    mime = meta.get("mime_type", "image/jpeg")
    img = requests.get(url, headers=h, timeout=30)
    return base64.b64encode(img.content).decode(), mime


def send_whatsapp_text(to, text, bot_id):
    url = f"{GRAPH_URL}/{bot_id}/messages"
    h = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text[:3900]}}
    try:
        r = requests.post(url, json=payload, headers=h, timeout=15)
        if r.status_code >= 400:
            print(f"TEXT ERROR {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"send err {e}")


def send_whatsapp_cta(to, body, link, bot_id, title):
    url = f"{GRAPH_URL}/{bot_id}/messages"
    h = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": body[:1024]},
            "action": {"name": "cta_url", "parameters": {"display_text": title[:20], "url": link}}
        }
    }
    try:
        r = requests.post(url, json=payload, headers=h, timeout=15)
        if r.status_code >= 400:
            print(f"CTA ERROR {r.status_code}: {r.text[:300]}")
            # احتياط: لا نخلي الرابط يضيع
            send_whatsapp_text(to, f"{body}\n🔗 {link}", bot_id)
    except Exception as e:
        print(f"CTA send err {e}")


# ================= Webhook =================
@app.get("/webhook")
async def verify(request: Request):
    p = request.query_params
    if p.get("hub.mode") == "subscribe" and p.get("hub.verify_token") == VERIFY_TOKEN:
        return Response(content=p.get("hub.challenge"), media_type="text/plain")
    return Response("fail", 403)


@app.post("/webhook")
async def receive(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    try:
        value = data["entry"][0]["changes"][0]["value"]
        if "messages" not in value:
            return {"status": "ok"}

        msg = value["messages"][0]
        mid = msg.get("id")
        if mid in processed_ids:
            return {"status": "dup"}

        processed_ids.append(mid)
        bot_id = value.get("metadata", {}).get("phone_number_id", PHONE_NUMBER_ID)
        from_number = msg["from"]

        if msg.get("type") == "image":
            IMAGE_BUFFER[from_number]["images"].append(msg)
            IMAGE_BUFFER[from_number]["time"] = time.time()
            IMAGE_BUFFER[from_number]["bot_id"] = bot_id
            if len(IMAGE_BUFFER[from_number]["images"]) == 1:
                background_tasks.add_task(process_image_buffer, from_number)
        else:
            background_tasks.add_task(process_text_message, msg, bot_id)

    except Exception as e:
        print(f"webhook err {e}")
    return {"status": "ok"}


# ================= معالجة الصور =================
async def process_image_buffer(from_number: str):
    await asyncio.sleep(BUFFER_SECONDS)
    data = IMAGE_BUFFER.pop(from_number, None)
    if not data:
        return
    images = data["images"]
    bot_id = data["bot_id"]

    if len(images) == 1:
        await asyncio.to_thread(process_single_image, images[0], bot_id)
    else:
        await asyncio.to_thread(process_multi_images, images, from_number, bot_id)


def process_single_image(message, bot_id):
    from_number = message["from"]
    send_whatsapp_text(from_number, "ثواني بس.. أحدد المنتج وأدور لك الأرخص!", bot_id)
    b64, mime = download_whatsapp_media(message["image"]["id"])
    txt, urls = call_gemini([
        {"inline_data": {"mime_type": mime, "data": b64}},
        {"text": "ما هذا المنتج؟ ابحث عن سعره الحالي في الكويت"}
    ])

    if not txt:
        txt = "ما قدرت أحدد المنتج، جرب صورة أوضح"
    else:
        # نستخرج اسم المنتج من رد Gemini وندور عليه في عروض الجمعيات
        name_m = re.search(r"📦\s*(.+)", txt)
        if name_m:
            coop = search_in_offers(name_m.group(1).strip())
            if coop:
                txt += f"\n\n{coop}"

    send_whatsapp_text(from_number, txt, bot_id)

    for n, u in urls.items():
        if u:
            send_whatsapp_cta(from_number, f"تسوق من {n} 👇", u, bot_id, f"🛒 {n[:18]}")


def fetch_product_from_image(msg):
    """نداء واحد للصورة: تحديد + بحث سعر معاً"""
    try:
        b64, mime = download_whatsapp_media(msg["image"]["id"])
        txt, urls = call_gemini([
            {"inline_data": {"mime_type": mime, "data": b64}},
            {"text": "حدد المنتج في الصورة وابحث عن سعره الحالي في الكويت في نفس الرد."}
        ])
        name_m = re.search(r"📦\s*(.+)", txt)
        name = (name_m.group(1).strip() if name_m else "منتج")[:50]
        price_m = re.search(r"✅.*?(?:—|-|–)\s*([\d\.]+)", txt)
        price = float(price_m.group(1)) if price_m else 0
        curl = list(urls.values())[0] if urls else ""
        cstore = list(urls.keys())[0] if urls else "متجر"
        return {"name": name, "store": cstore, "price": price, "url": curl, "all_urls": urls}
    except Exception as e:
        print(f"img item err {e}")
        return {"name": "منتج", "store": "متجر", "price": 0, "url": "", "all_urls": {}}


def fetch_product_from_text(prod):
    try:
        txt, urls = call_gemini([{"text": f"ابحث عن سعر {prod} في الكويت"}])
        m = re.search(r"✅.*?(?:—|-|–)\s*([\d\.]+)", txt)
        price = float(m.group(1)) if m else 0
        curl = list(urls.values())[0] if urls else ""
        cstore = list(urls.keys())[0] if urls else "متجر"
        return {"name": prod, "store": cstore, "price": price, "url": curl, "all_urls": urls}
    except Exception as e:
        print(f"txt item err {e}")
        return {"name": prod, "store": "متجر", "price": 0, "url": "", "all_urls": {}}


def finalize_cart(from_number, bot_id, items):
    total = sum(it["price"] for it in items)
    cart_id = uuid.uuid4().hex[:8]
    CARTS[cart_id] = {"products": items, "total": total}
    summ = "\n".join([f"• {it['name']} - {it['price']} د.ك ({it['store']})" for it in items])
    send_whatsapp_text(from_number, f"🛒 سلتك جاهزة:\n{summ}\n\n💰 الإجمالي بأرخص خلطة: {total:.3f} د.ك", bot_id)
    domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "fanzia.up.railway.app")
    send_whatsapp_cta(from_number, "افتح السلة وكمّل الشراء", f"https://{domain}/cart/{cart_id}", bot_id, "🛒 افتح السلة")


def process_multi_images(messages, from_number, bot_id):
    send_whatsapp_text(from_number, f"تمام لقطت {len(messages)} منتجات، قاعد أسوي لك سلة بأرخص خلطة...", bot_id)
    items = list(WORKERS.map(fetch_product_from_image, messages))
    finalize_cart(from_number, bot_id, items)


def process_text_message(message, bot_id):
    from_number = message["from"]
    user_text = message["text"]["body"]
    t = user_text.strip()

    # ===== أوامر عروض الجمعيات =====
    if t in ("العروض", "عروض", "عروض الجمعيات"):
        if not OFFERS["text"]:
            send_whatsapp_text(from_number, "ما في عروض محدثة حالياً، جرب بعد شوي أو اكتب: تحديث_العروض", bot_id)
        else:
            age_h = int((time.time() - OFFERS["updated"]) / 3600)
            send_whatsapp_text(from_number, f"🏪 عروض الجمعيات (آخر تحديث قبل {age_h} ساعة):\n\n{OFFERS['text'][:3700]}", bot_id)
        return

    if t == "تحديث_العروض":
        send_whatsapp_text(from_number, "قاعد أسحب أحدث الفلايرات من انستجرام الجمعيات وأستخرج العروض... تاخذ دقيقة تقريباً", bot_id)
        refresh_offers()
        if OFFERS["text"]:
            send_whatsapp_text(from_number, f"تم التحديث ✅ اكتب (العروض) عشان تشوفها", bot_id)
        else:
            send_whatsapp_text(from_number, "ما قدرت أجيب عروض — تأكد من IG_USER_ID و COOP_ACCOUNTS في Railway", bot_id)
        return

    # ===== البحث العادي =====
    products = extract_products(user_text)

    if len(products) == 1:
        send_whatsapp_text(from_number, f"🔍 أدور لك على {products[0]}...", bot_id)
        txt, urls = call_gemini([{"text": f"ابحث عن سعر {products[0]} في الكويت"}])
        body = txt or "ما لقيت"

        # نضيف نتيجة عروض الجمعيات من الفلايرات إن وجدت
        coop = search_in_offers(products[0])
        if coop:
            body += f"\n\n{coop}"

        send_whatsapp_text(from_number, body, bot_id)
        for n, u in urls.items():
            if u:
                send_whatsapp_cta(from_number, f"تسوق من {n} 👇", u, bot_id, f"🛒 {n[:18]}")
    else:
        send_whatsapp_text(from_number, f"تمام لقيت {len(products)} منتجات، أسوي لك سلة تخلط أرخص المتاجر...", bot_id)
        items = list(WORKERS.map(fetch_product_from_text, products))
        finalize_cart(from_number, bot_id, items)


# ================= صفحة السلة =================
@app.get("/cart/{cart_id}", response_class=HTMLResponse)
async def cart_page(cart_id: str):
    cart = CARTS.get(cart_id)
    if not cart:
        return HTMLResponse("<h1>السلة انتهت</h1>", 404)

    rows = ""
    for it in cart["products"]:
        btns = "".join([f"<a href='{u}' target='_blank' class='text-xs bg-gray-100 px-2 py-1 rounded mr-1'>{n}</a>" for n, u in it['all_urls'].items() if u])
        rows += f"<div class='p-4 border-b flex justify-between items-start'><div><b>{it['name']}</b><br><span class='text-sm text-gray-500'>{it['store']} - {it['price']} د.ك</span><div class='mt-2 flex flex-wrap gap-1'>{btns}</div></div><a href='{it['url']}' target='_blank' class='bg-black text-white px-4 py-2 rounded'>شراء</a></div>"

    html = f"""<html dir='rtl'><head><meta name='viewport' content='width=device-width,initial-scale=1'><script src='https://cdn.tailwindcss.com'></script></head><body class='bg-gray-50'><div class='max-w-lg mx-auto bg-white min-h-screen'><div class='p-5 bg-black text-white'><h1 class='text-xl font-bold'>🛒 سلتك</h1><p class='text-sm opacity-70'>أرخص خلطة متاجر - تسمح بالخلط</p></div>{rows}<div class='p-5'><div class='flex justify-between text-lg font-bold'><span>الإجمالي</span><span>{cart['total']:.3f} د.ك</span></div></div></div></body></html>"""

    return HTMLResponse(html)


@app.get("/")
async def health():
    return {
        "status": "v7 instagram coop offers",
        "number": "5250",
        "coops": COOP_ACCOUNTS,
        "offers_chars": len(OFFERS["text"]),
        "offers_updated": OFFERS["updated"],
    }
