# -*- coding: utf-8 -*-
import os, re, time, base64, requests, uuid, asyncio
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import HTMLResponse

app = FastAPI()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_COOP_BOT_TOKEN")

GRAPH_URL = "https://graph.facebook.com/v20.0"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

processed_ids = deque(maxlen=1000)
CARTS = {}
IMAGE_BUFFER = defaultdict(lambda: {"images": [], "time": 0, "bot_id": ""})
BUFFER_SECONDS = 4          # كان 10 — أهم مصدر بطء للصورة الواحدة
RESOLVER = ThreadPoolExecutor(max_workers=6)   # فك الروابط بالتوازي
WORKERS = ThreadPoolExecutor(max_workers=3)    # منتجات السلة بالتوازي

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

SYSTEM_PROMPT = """
أنت مساعد تسوق كويتي. رد بهذا الشكل فقط:
📦 [اسم المنتج]
✅ [المتجر الأرخص] — [السعر] د.ك
• [المتجر الثاني] — [السعر] د.ك
• [المتجر الثالث] — [السعر] د.ك
في النهاية سطر واحد إلزامي يربط كل متجر ذكرته بدومين موقعه، بنفس ترتيب القائمة:
LINKS: اسم المتجر الأول=دومينه.com, اسم المتجر الثاني=دومينه.com, اسم المتجر الثالث=دومينه.com
مثال: LINKS: إكسايت=xcite.com, بلينك=blink.com.kw, يوريكا=eureka.com.kw
ممنوع روابط ظاهرة في النص. ممنوع Markdown.
"""


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
    """يفك كل روابط الـgrounding بالتوازي — بدل التسلسلي البطيء"""
    return list(RESOLVER.map(get_final_url, uris))


def call_gemini(parts: list):
    """يرجع (النص, {اسم المتجر: رابطه النهائي}) — المطابقة على الرابط المفكوك وليس التخمين"""
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

        # أزواج (اسم المتجر = الدومين) من سطر LINKS
        pairs = []
        m = re.search(r"LINKS:\s*(.+)", text, re.I)
        if m:
            for part in re.split(r"[,،]+", m.group(1)):
                if "=" in part:
                    name, dom = part.split("=", 1)
                    name, dom = name.strip(), dom.strip().lower()
                    if "." in dom:
                        pairs.append((name, dom))
            text = re.sub(r"\n?LINKS:.*", "", text, flags=re.I).strip()

        text = re.sub(r"https?://\S+", "", text)
        text = text.replace("**", "").replace("*", "")
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        # ===== الإصلاح الجذري للروابط =====
        # روابط الـgrounding هي روابط تحويل مبهمة — الدومين لا يظهر فيها أبداً.
        # الطريقة الصحيحة: نفكها كلها بالتوازي أولاً، ثم نطابق الدومين على الرابط *النهائي*.
        urls_map = {}
        chunks = cand.get("groundingMetadata", {}).get("groundingChunks", [])
        uris = [c.get("web", {}).get("uri") for c in chunks if c.get("web", {}).get("uri")]
        if uris and pairs:
            finals = resolve_all(uris[:8])
            for name, dom in pairs:
                key = dom.replace("www.", "")
                for f in finals:
                    if f and key in f.lower().replace("www.", ""):
                        urls_map[name] = f
                        break
        # لا خطة بديلة بروابط عشوائية — رابط غلط أسوأ من بلا رابط

        return text, dict(list(urls_map.items())[:3])
    except Exception as e:
        print(f"Gemini err {e}")
        return "", {}


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
        requests.post(url, json=payload, headers=h, timeout=15)
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
        requests.post(url, json=payload, headers=h, timeout=15)
    except Exception as e:
        print(f"CTA send err {e}")


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
    send_whatsapp_text(from_number, txt, bot_id)

    for n, u in urls.items():
        if u:
            send_whatsapp_cta(from_number, f"تسوق من {n} 👇", u, bot_id, f"🛒 {n[:18]}")


def fetch_product_from_image(msg):
    """نداء واحد فقط للصورة: تحديد + بحث سعر معاً — كان نداءين متتاليين (أبطأ نقطة بالسلة)"""
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
    # بالتوازي: 3 منتجات بنفس الوقت بدل الواحد ورا الثاني، ونداء واحد لكل منتج بدل اثنين
    items = list(WORKERS.map(fetch_product_from_image, messages))
    finalize_cart(from_number, bot_id, items)


def process_text_message(message, bot_id):
    from_number = message["from"]
    user_text = message["text"]["body"]
    products = extract_products(user_text)

    if len(products) == 1:
        send_whatsapp_text(from_number, f"🔍 أدور لك على {products[0]}...", bot_id)
        txt, urls = call_gemini([{"text": f"ابحث عن سعر {products[0]} في الكويت"}])
        send_whatsapp_text(from_number, txt or "ما لقيت", bot_id)
        for n, u in urls.items():
            if u:
                send_whatsapp_cta(from_number, f"تسوق من {n} 👇", u, bot_id, f"🛒 {n[:18]}")
    else:
        send_whatsapp_text(from_number, f"تمام لقيت {len(products)} منتجات، أسوي لك سلة تخلط أرخص المتاجر...", bot_id)
        items = list(WORKERS.map(fetch_product_from_text, products))
        finalize_cart(from_number, bot_id, items)


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
    return {"status": "v5 fast + accurate links", "number": "5250"}
