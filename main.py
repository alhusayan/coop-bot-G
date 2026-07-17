# -*- coding: utf-8 -*-
import os, re, time, base64, requests
from collections import deque
from fastapi import FastAPI, Request, Response, BackgroundTasks

app = FastAPI()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_COOP_BOT_TOKEN")

GRAPH_URL = "https://graph.facebook.com/v20.0"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

processed_ids = deque(maxlen=500)

SYSTEM_PROMPT = """
أنت المساعد الشخصي الذكي لصاحب هذا الرقم. مهمتك هي البحث عن أسعار المنتجات في الكويت بدقة متناهية وبأسلوب كويتي بسيط ومباشر.

التزم بالقواعد التالية حرفياً:
1. الشخصية: أنت لست مجرد بوت، أنت المساعد الشخصي لصاحب الرقم، رد بأسلوب كويتي عفوي ومباشر.
2. التنسيق: لا تستخدم مقدمات ولا خاتمات. ابدأ فوراً بذكر المنتج، ثم قائمة الأسعار.
3. القائمة: استخدم هذا الشكل الإلزامي فقط:

📦 [اسم المنتج]

✅ [اسم المتجر الأرخص] — [السعر] د.ك
- [المتجر الثاني] — [السعر] د.ك
- [المتجر الثالث] — [السعر] د.ك

قواعد ذهبية:
- ممنوع إضافة أي جمل ترحيبية أو توديعية.
- التزم بالأسعار التي تجدها فقط.
- لا تستخدم أي رموز Markdown.

قاعدة الروابط الإلزامية - حل عام:
في النهاية اكتب مصادرك بهذا الشكل الحرفي تماماً، نفس اسم المتجر = الدومين:
LINKS: بست اليوسفي=best.com.kw, يوريكا=eureka.com.kw, بلينك=blink.com.kw

ممنوع تكتب رابط كامل، اكتب دومين فقط ومربوط بالاسم. ينطبق على أي متجر كارفور=carrefourkuwait.com, لولو=luluhypermarket.com وغيرهم.
"""

@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == VERIFY_TOKEN:
        return Response(content=params.get("hub.challenge"), media_type="text/plain")
    return Response(content="Verification failed", status_code=403)

@app.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    try:
        value = data["entry"][0]["changes"][0]["value"]
        if "messages" in value:
            message = value["messages"][0]
            msg_id = message.get("id")
            bot_phone_id = value.get("metadata", {}).get("phone_number_id", PHONE_NUMBER_ID)
            if msg_id and msg_id not in processed_ids:
                processed_ids.append(msg_id)
                background_tasks.add_task(process_message, message, bot_phone_id)
    except Exception as e:
        print(f"Webhook error: {e}")
    return {"status": "ok"}

def process_message(message: dict, bot_phone_id: str):
    from_number = message["from"]
    msg_type = message.get("type")
    try:
        parts = []
        if msg_type == "image":
            send_whatsapp_text(from_number, "ثواني بس.. ابحث واقارن لك الأسعار!", bot_phone_id)
            image_b64, mime = download_whatsapp_media(message["image"]["id"])
            parts.append({"inline_data": {"mime_type": mime, "data": image_b64}})
            parts.append({"text": "تعرف على هذا المنتج وابحث الآن بحثاً حياً عن أسعاره الحالية في الكويت."})
        elif msg_type == "text":
            user_text = message["text"]["body"]
            send_whatsapp_text(from_number, "🔍 ثواني ، أدور لك الأسعار الحالية بالكويت...", bot_phone_id)
            parts.append({"text": f"العميل يسأل: {user_text}\nابحث الآن بحثاً حياً عن الأسعار الحالية في الكويت ورد عليه."})
        else:
            send_whatsapp_text(from_number, "حياك الله 🌟 دز لي صورة المنتج أو اكتب اسمه، وأدور لك أسعاره الحالية بالكويت فوراً 🛒", bot_phone_id)
            return

        reply_text, urls_map = call_gemini(parts)
        if not reply_text:
            reply_text = "ما قدرت ألقى نتيجة واضحة 😅 جرب صورة أوضح أو اكتب اسم المنتج بالنص."

        print(f"FROM {from_number} VIA {bot_phone_id} | URLS: {urls_map}")

        if urls_map:
            send_whatsapp_text(from_number, reply_text, bot_phone_id)
            time.sleep(0.5)
            for store_name, url in urls_map.items():
                if not url: continue
                clean_name = re.sub(r'[^\w\s\u0600-\u06FF]', '', store_name).strip()[:18]
                btn_title = f"🛒 {clean_name}"[:20]
                body = f"تسوق من {store_name} 👇"
                send_whatsapp_cta(from_number, body, url, bot_phone_id, button_title=btn_title)
                time.sleep(0.4)
        else:
            send_whatsapp_text(from_number, reply_text, bot_phone_id)

    except Exception as e:
        print(f"Error processing message: {e}")
        try:
            send_whatsapp_text(from_number, "صار خلل بسيط بالشبكة 🙏 عيد المحاولة بعد شوي غالي.", bot_phone_id)
        except: pass

def get_final_url(url: str):
    try:
        r = requests.get(url, allow_redirects=True, timeout=10, stream=True)
        final = r.url
        # اذا الصفحة مو موجودة لا ترسلها
        if r.status_code >= 400: return ""
        if "vertexaisearch" in final: return ""
        r.close()
        return final if len(final) < 700 else ""
    except: return ""

def call_gemini(parts: list):
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": parts}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2500},
    }
    r = requests.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload, timeout=120)
    if r.status_code >= 400: return "", {}
    try:
        data = r.json()
        cand = data["candidates"][0]
        raw = "".join(p.get("text","") for p in cand["content"]["parts"]).strip()

        m = re.search(r"LINKS:\s*(.+)", raw, re.I | re.DOTALL)
        links_raw = m.group(1).strip() if m else ""
        text = re.sub(r"LINKS:.*", "", raw, flags=re.I).strip()
        text = re.sub(r"https?://\S+", "", text)

        # فك LINKS: اسم=دومين
        pairs = [] # [(بست اليوسفي, best.com.kw),...]
        if links_raw:
            for chunk in re.split(r"[,|\n]+", links_raw):
                if "=" in chunk:
                    n,d = chunk.split("=",1)
                    n=n.strip(" ✅•-"); d=d.strip().lower()
                    if "." in d: pairs.append((n,d))

        chunks = cand.get("groundingMetadata",{}).get("groundingChunks",[])
        urls_map = {}
        for store_name, domain in pairs:
            key = domain.split(".")[0] # best, eureka, carrefour
            real_url = ""
            for c in chunks:
                uri = c.get("web",{}).get("uri","")
                title = (c.get("web",{}).get("title") or "").lower()
                if key in uri.lower() or key in title:
                    real_url = get_final_url(uri)
                    if real_url: break
            # اذا ما لقينا رابط حقيقي، لا ترسل رابط مزيف، سوي رابط بحث بدل 404
            if not real_url:
                real_url = f"https://{domain}/search?q={store_name}" # fallback آمن ما يعطي 404
            urls_map[store_name] = real_url

        return text, urls_map
    except Exception as e:
        print(f"err {e}"); return "", {}

def download_whatsapp_media(media_id: str):
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    meta = requests.get(f"{GRAPH_URL}/{media_id}", headers=headers, timeout=30).json()
    media_url = meta["url"]
    mime = meta.get("mime_type", "image/jpeg")
    img = requests.get(media_url, headers=headers, timeout=60)
    img.raise_for_status()
    return base64.standard_b64encode(img.content).decode("utf-8"), mime

def send_whatsapp_text(to_number: str, text: str, bot_phone_id: str):
    url = f"{GRAPH_URL}/{bot_phone_id}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)] or [text]
    for chunk in chunks:
        payload = {"messaging_product": "whatsapp", "to": to_number, "type": "text", "text": {"body": chunk}}
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code >= 400:
            print(f"WhatsApp send error: {r.status_code} {r.text}")

def send_whatsapp_cta(to_number: str, text: str, url: str, bot_phone_id: str, button_title: str = "🛒 تسوق الآن"):
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": text[:1024]},
            "action": {"name": "cta_url", "parameters": {"display_text": button_title[:20], "url": url}},
        },
    }
    r = requests.post(
        f"{GRAPH_URL}/{bot_phone_id}/messages",
        json=payload,
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"},
        timeout=30,
    )
    if r.status_code >= 400:
        print(f"CTA send error: {r.status_code} {r.text}")
        send_whatsapp_text(to_number, f"{text}\n🔗 {url}", bot_phone_id)

@app.get("/")
async def health():
    return {"status": "running", "bot": "Kuwait Price Bot Fixed"}
