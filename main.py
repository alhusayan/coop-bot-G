# -*- coding: utf-8 -*-
"""
بوت واتساب — بحث حي فوري عن أسعار المنتجات في الكويت
WhatsApp Cloud API (Meta) + FastAPI + Gemini API (Google Search Grounding)
Deploy: Railway
"""

import os
import re
import time
import base64
import requests
from collections import deque
from fastapi import FastAPI, Request, Response, BackgroundTasks

app = FastAPI()

# ========= مفاتيح التشغيل (تنحط في Railway → Variables) =========
GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL    = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
WHATSAPP_TOKEN  = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN    = os.environ.get("VERIFY_TOKEN", "MY_SECRET_COOP_BOT_TOKEN")

GRAPH_URL  = "https://graph.facebook.com/v20.0"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

processed_ids = deque(maxlen=500)

SYSTEM_PROMPT = """أنت مساعد ذكي متخصص بأسعار المنتجات في دولة الكويت، ترد على عملاء واتساب.

مهمتك:
1. تعرّف على المنتج من الصورة أو من نص الرسالة.
2. سوّ بحثات Google موجّهة للمتاجر الكويتية (مثل: jm3eia.com, taw9eel.com, oncost.com, lulu, carrefour, talabat الجمعيات).
3. اعرض النتائج بشكل مرتب وواضح.

قواعد الرد:
- لا مقدمات ولا ترحيب — ابدأ مباشرة بسطر 📦 اسم المنتج (إلا إذا العميل سلم عليك).
- اعرض الأسعار بهذا الشكل الإلزامي بالضبط:
📦 اسم المنتج
✅ المتجر الأرخص — السعر د.ك
• المتجر الثاني — السعر د.ك
• المتجر الثالث — السعر د.ك
- إذا فيه أحجام، اذكر الحجم داخل سطر المتجر.
- لا تستخدم جداول أو عناوين غامقة (Markdown).
- خل الرد مختصر جداً.
- **مهم جداً جداً:** في نهاية ردك تماماً (بسطر منفصل)، يجب أن تكتب الرابط المباشر لأرخص متجر بهذا الشكل الإلزامي لكي يتم تحويله لزر:
LINK: https://www.example.com
(لا تكتب أي شيء آخر بعد الرابط).
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
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" in entry:
            message = entry["messages"][0]
            msg_id = message.get("id")

            if msg_id and msg_id not in processed_ids:
                processed_ids.append(msg_id)
                background_tasks.add_task(process_message, message)
    except (KeyError, IndexError):
        pass

    return {"status": "ok"}


def process_message(message: dict):
    from_number = message["from"]
    msg_type = message.get("type")

    try:
        parts = []

        if msg_type == "image":
            send_whatsapp_text(from_number, "🔍 ثواني يا بطل.. قاعد أصيد لك أرخص سعر بالكويت!")
            image_b64, mime = download_whatsapp_media(message["image"]["id"])
            parts.append({"inline_data": {"mime_type": mime, "data": image_b64}})
            parts.append({"text": "تعرف على هذا المنتج وابحث الآن بحثاً حياً عن أسعاره الحالية في الكويت."})

        elif msg_type == "text":
            user_text = message["text"]["body"]
            send_whatsapp_text(from_number, "🔍 ثواني يا خوي، أدور لك الأسعار الحالية بالكويت...")
            parts.append({"text": f"العميل يسأل: {user_text}\nابحث الآن بحثاً حياً عن الأسعار الحالية في الكويت."})

        else:
            send_whatsapp_text(from_number, "حياك الله 🌟 دز لي صورة المنتج أو اكتب اسمه وأبشر.")
            return

        reply_text, best_url = call_gemini(parts)

        if not reply_text:
            reply_text = "ما قدرت ألقى نتيجة واضحة 😅 جرب صورة أوضح أو اكتب اسم المنتج بالنص."

        print(f"REPLY LEN: {len(reply_text)} | URL EXTRACTED: {best_url}")

        if best_url:
            send_whatsapp_cta(from_number, reply_text, best_url)
        else:
            send_whatsapp_text(from_number, reply_text)

    except Exception as e:
        print(f"Error processing message: {e}")
        try:
            send_whatsapp_text(from_number, "صار خلل بالشبكة 🙏 عيد المحاولة بعد شوي.")
        except Exception:
            pass


def call_gemini(parts: list):
    """نداء Gemini وصيد الرابط السريع بدون فحص يسبب بلوك"""
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": parts}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1500},
    }

    for attempt in (1, 2):
        r = requests.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload, timeout=120)
        if r.status_code == 429 and attempt == 1:
            time.sleep(8)
            continue
        if r.status_code >= 400:
            return "", None
        break

    try:
        data = r.json()
        cand = data["candidates"][0]
        out = cand["content"]["parts"]
        text = "".join(p.get("text", "") for p in out).strip()

        # تنظيف من المراجع المزعجة
        text = re.sub(r"(?<=\S)\[[\d]+(?:[.,][\d]+)*\]", "", text)

        best_url = None
        # 1. صيد الرابط المكتوب صراحة بالنص (LINK: http...)
        match = re.search(r"LINK:\s*(https?://[^\s]+)", text, re.IGNORECASE)
        if match:
            best_url = match.group(1).strip()
            # إخفاء الرابط من النص لكي لا يظهر للعميل (لأنه سيكون داخل الزر)
            text = re.sub(r"LINK:\s*https?://[^\s]+", "", text, flags=re.IGNORECASE).strip()

        # 2. خطة إنقاذ: إذا ما كتبه بالنص، نسحبه من بيانات البحث الخفية فوراً
        if not best_url:
            chunks = cand.get("groundingMetadata", {}).get("groundingChunks", [])
            for c in chunks:
                uri = c.get("web", {}).get("uri", "")
                # ناخذ أول رابط حقيقي مو محرك بحث
                if uri and uri.startswith("http") and "google.com" not in uri:
                    best_url = uri
                    break
        
        # تنظيف نهائي للأسطر الفارغة
        lines = [l.rstrip() for l in text.splitlines()]
        text = "\n".join([l for l in lines if l])

        return text, best_url
    except Exception as e:
        print(f"GEMINI PARSE ERROR: {e}")
        return "", None


def download_whatsapp_media(media_id: str):
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    meta = requests.get(f"{GRAPH_URL}/{media_id}", headers=headers, timeout=30).json()
    img = requests.get(meta["url"], headers=headers, timeout=60)
    return base64.standard_b64encode(img.content).decode("utf-8"), meta.get("mime_type", "image/jpeg")


def send_whatsapp_text(to_number: str, text: str):
    url = f"{GRAPH_URL}/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    clean_number = str(to_number).replace("+", "").strip()

    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)] or [text]
    for chunk in chunks:
        requests.post(url, json={"messaging_product": "whatsapp", "to": clean_number, "type": "text", "text": {"body": chunk}}, headers=headers, timeout=30)


def send_whatsapp_cta(to_number: str, text: str, url: str):
    """إرسال النص مع زر انتقال، وإذا فشل الزر يعوض برابط نصي"""
    clean_number = str(to_number).replace("+", "").strip()
    
    if len(text) > 1000:
        send_whatsapp_text(clean_number, text)
        body = "اضغط الزر تحت لزيارة أرخص متجر 👇"
    else:
        body = text

    payload = {
        "messaging_product": "whatsapp",
        "to": clean_number,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": body},
            "action": {
                "name": "cta_url",
                "parameters": {"display_text": "🛒 شوف أرخص سعر", "url": url},
            },
        },
    }
    r = requests.post(
        f"{GRAPH_URL}/{PHONE_NUMBER_ID}/messages",
        json=payload,
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"},
        timeout=30,
    )
    # إذا رفض فيسبوك الرابط لسبب ما، نحطه كرابط عادي للعميل عشان ما يخسره
    if r.status_code >= 400:
        if len(text) <= 1000:
            send_whatsapp_text(clean_number, text + f"\n\n🔗 رابط الشراء:\n{url}")
        else:
            send_whatsapp_text(clean_number, f"🔗 رابط الشراء:\n{url}")


@app.get("/")
async def health():
    return {"status": "running", "bot": "Kuwait Price Bot 🇰🇼 (Gemini 1.5 - No Reset Error)"}
