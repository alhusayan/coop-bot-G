# -*- coding: utf-8 -*-
"""
بوت واتساب — بحث حي فوري عن أسعار المنتجات في الكويت
WhatsApp Cloud API (Meta) + FastAPI + Gemini API (Google Search Grounding)
Deploy: Railway
"""

import os
import time
import base64
import requests
from collections import deque
from fastapi import FastAPI, Request, Response, BackgroundTasks

app = FastAPI()

# ========= مفاتيح التشغيل (تنحط في Railway → Variables، مو هنا) =========
GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL    = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash") # تم ضبطه على النسخة المستقرة المعتمدة لحسابك
WHATSAPP_TOKEN  = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN    = os.environ.get("VERIFY_TOKEN", "MY_SECRET_COOP_BOT_TOKEN")

GRAPH_URL  = "https://graph.facebook.com/v20.0"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# منع الرد المكرر: نحفظ آخر 500 رسالة تمت معالجتها
processed_ids = deque(maxlen=500)

SYSTEM_PROMPT = """أنت "مساعد المشتري وصياد العروض" في دولة الكويت، ترد على عملاء واتساب بأسلوب كويتي ودود وسريع.

مهمتك الأساسية:
1. تعرف على المنتج بدقة من الصورة أو النص (الاسم، الحجم، والوزن إن وجد).
2. ابحث بحثاً حياً بالإنترنت عن أسعاره الحالية والخصومات في الجمعيات التعاونية والهايبرماركتس ومنصات التوصيل الكويتية (مثل talabat, jm3eia.com, taw9eel.com, لولو، كارفور، سيتي هايبر).
3. رتب الأسعار التي عثرت عليها من الأرخص للأعلى بأسطر بسيطة ومتباعدة.

⚠️ قواعد التنسيق الصارمة ومنع الأخطاء:
- ممنوع منعاً باتاً طباعة أو إظهار أي كود برمجي، أو نصوص JSON، أو رموز تقنية داخل ردك (مثل {"google_search_results": ...} أو الأقواس المتعرجة). ردك يجب أن يتكون من لغة عربية ولهجة كويتية صافية ومقروءة للمستخدم العادي فقط.
- لا تستخدم جداول أو خطوط Markdown الثقيلة (** غامق أو # عناوين). اجعل الأسطر متباعدة ومريحة للعين بالواتساب باستخدام الرموز التعبيرية (Emojis) فقط.

طريقة صياغة الرد للعميل:
- ابدأ بترحيب سريع وبشر العميل بالصيد (مثال: "هلا بالصياد! 🎣 لقيت لك الأسعار الحين:").
- اذكر اسم المنتج بوضوح.
- اعرض الأسعار كقائمة بسيطة: اسم المتجر — السعر د.ك.
- ضع علامة ✅ بجانب السعر الأرخص على الإطلاق.
- اذكر بوضوح أي عروض أو مهرجانات أسبوعية نشطة للمنتج إن وجدت.
- 🔗 رابط أفضل سعر: ابحث في نتائج البحث الحية عن رابط الويب الفعلي (URL) المتوفر الخاص بأرخص سعر عثرت عليه، واكتبه بوضوح في نهاية الرسالة على سطر مستقل ليكون قابلاً للنقر (مثال: "رابط أرخص سعر للشراء المباشر: [ضع الرابط هنا]").
- اجعل الرد كله مختصراً وجذاباً (أقل من 12 سطر).
"""


# ========= 1. التحقق من الـ Webhook (يطلبه Meta مرة وحدة عند الربط) =========
@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == VERIFY_TOKEN:
        return Response(content=params.get("hub.challenge"), media_type="text/plain")
    return Response(content="Verification failed", status_code=403)


# ========= 2. استقبال الرسائل — نرجع 200 فوراً والمعالجة بالخلفية =========
@app.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" in entry:
            message = entry["messages"][0]
            msg_id = message.get("id")

            # تجاهل الرسالة إذا سبق عالجناها (Meta أحياناً يعيد الإرسال)
            if msg_id and msg_id not in processed_ids:
                processed_ids.append(msg_id)
                background_tasks.add_task(process_message, message)
    except (KeyError, IndexError):
        pass  # إشعارات statuses وغيرها — نتجاهلها

    return {"status": "ok"}


# ========= 3. معالجة الرسالة: بحث حي + رد =========
def process_message(message: dict):
    from_number = message["from"]
    msg_type = message.get("type")

    try:
        parts = []

        if msg_type == "image":
            # رسالة انتظار عشان العميل ما يحس البوت طافي
            send_whatsapp_text(from_number, "ثواني بس.. قاعد أحوس بمواقع الكويت الحين عشان أطلع لك أقوى صيدة وأرخص سعر!")

            image_b64, mime = download_whatsapp_media(message["image"]["id"])
            parts.append({"inline_data": {"mime_type": mime, "data": image_b64}})
            parts.append({"text": "تعرف على هذا المنتج وابحث الآن بحثاً حياً عن أسعاره الحالية في الكويت لترد على العميل."})

        elif msg_type == "text":
            user_text = message["text"]["body"]
            send_whatsapp_text(from_number, "🔍 ثواني يا خوي، أدور لك الأسعار الحالية بالكويت...")
            parts.append({"text": f"العميل يسأل: {user_text}\nابحث الآن بحثاً حياً عن الأسعار الحالية في الكويت ورد عليه."})

        else:
            send_whatsapp_text(from_number, "حياك الله 🌟 دز لي صورة المنتج أو اكتب اسمه، وأدور لك أسعاره الحالية بالكويت فوراً 🛒")
            return

        # ===== استدعاء Gemini مع البحث الحي =====
        reply_text = call_gemini(parts)

        if not reply_text:
            reply_text = "ما قدرت ألقى نتيجة واضحة 😅 جرب صورة أوضح أو اكتب اسم المنتج بالنص."

        send_whatsapp_text(from_number, reply_text)

    except Exception as e:
        print(f"Error processing message: {e}")
        try:
            send_whatsapp_text(from_number, "صار خلل بسيط بالشبكة 🙏 عيد المحاولة بعد شوي غالي.")
        except Exception:
            pass


def call_gemini(parts: list) -> str:
    """نداء Gemini مع أدوات البحث الحي وإعادة المحاولة عند حدوث ضغط 429"""
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": parts}],
        "tools": [
            {"google_search": {}}  # أداة البحث الحي والربط بمحرك البحث
        ],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1500},
    }

    for attempt in (1, 2):
        r = requests.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload, timeout=120)
        if r.status_code == 429 and attempt == 1:
            print("GEMINI 429 — free tier rate limit, retrying in 8s")
            time.sleep(8)
            continue
        if r.status_code >= 400:
            print(f"GEMINI error {r.status_code}: {r.text[:400]}")
            return ""
        break

    try:
        data = r.json()
        out = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in out).strip()
    except (KeyError, IndexError, TypeError, ValueError) as e:
        print(f"GEMINI bad response: {e} — {r.text[:400]}")
        return ""


# ========= أدوات مساعدة للواتساب =========
def download_whatsapp_media(media_id: str):
    """يجيب الصورة من سيرفرات Meta ويرجعها base64 مع نوعها"""
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}

    meta = requests.get(f"{GRAPH_URL}/{media_id}", headers=headers, timeout=30).json()
    media_url = meta["url"]
    mime = meta.get("mime_type", "image/jpeg")

    img = requests.get(media_url, headers=headers, timeout=60)
    img.raise_for_status()

    return base64.standard_b64encode(img.content).decode("utf-8"), mime


def send_whatsapp_text(to_number: str, text: str):
    """يرسل رد نصي، ويضمن تنظيف رقم الهاتف وإرساله بالصيغة الصحيحة"""
    url = f"{GRAPH_URL}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    # تنظيف رقم التليفون (إزالة أي علامات زائد أو مسافات إن وجدت)
    clean_number = str(to_number).replace("+", "").strip()

    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)] or [text]
    for chunk in chunks:
        payload = {
            "messaging_product": "whatsapp",
            "to": clean_number,
            "type": "text",
            "text": {"body": chunk},
        }
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code >= 400:
            print(f"WhatsApp send error: {r.status_code} {r.text}")


@app.get("/")
async def health():
    return {"status": "running", "bot": "Kuwait Price Bot 🇰🇼 (Gemini)"}
