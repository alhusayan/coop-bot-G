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

# ========= مفاتيح التشغيل (تنحط في Railway → Variables، مو هنا) =========
GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL    = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
WHATSAPP_TOKEN  = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN    = os.environ.get("VERIFY_TOKEN", "MY_SECRET_COOP_BOT_TOKEN")

GRAPH_URL  = "https://graph.facebook.com/v20.0"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# منع الرد المكرر: نحفظ آخر 500 رسالة تمت معالجتها
processed_ids = deque(maxlen=500)

SYSTEM_PROMPT = """
بشكل مختصر جدا وسريع من غير بولدز دورلي احسن سعر بالكويت لافضل سعىرا للشراء
اعمله شكل ترقيم 
اترك مسافة سطر بين كل رقم والثاني
ضع علامة صح على السعر الافضل
حط لنك يشتغل لأفضل سعر تحصل عليه عشان اذا ضغط عليه يحوله مباشرة على المنتج في المتجر الارخص
ابحث عن المنتجات للبيع فقط وليس الايجار
اكتب اسم المنتج باختصار من غير شرح
خلك نصوح
اي سؤال او سالفة ثانية مالها علاقة بتقييم او اسعار المنتجات رد عليه بطريقة جميلة وذكية بانك مخصص فقط لمقارنة و البحث عن افضل اسعار المنتجات والسلع
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
            # رسالة انتظار عشان العميل ما يحس البوت طافي (البحث ياخذ ثواني)
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
        reply_text, best_url = call_gemini(parts)

        if not reply_text:
            reply_text = "ما قدرت ألقى نتيجة واضحة 😅 جرب صورة أوضح أو اكتب اسم المنتج بالنص."

        # ===== سطر التشخيص: طول الرد وهل فيه رابط (يظهر في Deploy Logs) =====
        print(f"REPLY LEN: {len(reply_text)} | URL: {bool(best_url)}")

        # الرابط داخل زر مدمج — بدون رابط ظاهر في النص
        if best_url:
            send_whatsapp_cta(from_number, reply_text, best_url)
        else:
            send_whatsapp_text(from_number, reply_text)

    except Exception as e:
        print(f"Error processing message: {e}")
        try:
            send_whatsapp_text(from_number, "صار خلل بسيط بالشبكة 🙏 عيد المحاولة بعد شوي غالي.")
        except Exception:
            pass


def call_gemini(parts: list):
    """نداء Gemini مع البحث الحي. يرجع (نص الرد, رابط الأرخص أو None)"""
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": parts}],
        "tools": [
            {"google_search": {}}  # أداة البحث الحي والربط بمحرك البحث
        ],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2500},
    }

    for attempt in (1, 2):
        r = requests.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload, timeout=120)
        if r.status_code == 429 and attempt == 1:
            print("GEMINI 429 — free tier rate limit, retrying in 8s")
            time.sleep(8)
            continue
        if r.status_code >= 400:
            print(f"GEMINI error {r.status_code}: {r.text[:400]}")
            return "", None
        break

    try:
        data = r.json()
        cand = data["candidates"][0]
        out = cand["content"]["parts"]
        text = "".join(p.get("text", "") for p in out).strip()

        # تنظيف احتياطي دقيق: استشهادات ملتصقة بنهاية الكلمات فقط + روابط
        text = re.sub(r"(?<=\S)\[[\d]+(?:[.,][\d]+)*\]", "", text)   # مثل كلمة[4.2.6]
        text = re.sub(r"https?://\S+", "", text)
        # ترتيب: حذف أسطر صارت بلا محتوى وأسطر فارغة متكررة
        lines = [l.rstrip() for l in text.splitlines()]
        lines = [l for l in lines if l.strip() not in (".", "-", "•", "*")]
        text = "\n".join(lines)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        # استخراج دومين الأرخص من سطر BEST: ثم حذفه من النص
        best_domain = None
        m = re.search(r"BEST:\s*([\w.-]+)", text)
        if m:
            best_domain = m.group(1).lower()
            text = re.sub(r"\n?BEST:.*", "", text).strip()

        # رابط الأرخص: من نتائج الـgrounding المطابقة للدومين، مفكوكاً لرابط نهائي قصير
        best_url = None
        try:
            chunks = cand.get("groundingMetadata", {}).get("groundingChunks", [])
            target = None
            for c in chunks:
                title = (c.get("web", {}).get("title") or "").lower()
                if best_domain and best_domain.split(".")[0] in title:
                    target = c.get("web", {}).get("uri")
                    break
            if not target and chunks:
                target = chunks[0].get("web", {}).get("uri")
            if target:
                final = requests.head(target, allow_redirects=True, timeout=15).url
                if len(final) < 500 and "vertexaisearch" not in final:
                    best_url = final
        except Exception as e:
            print(f"LINK RESOLVE: {e}")

        return text, best_url
    except (KeyError, IndexError, TypeError, ValueError) as e:
        print(f"GEMINI bad response: {e} — {r.text[:400]}")
        return "", None


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
    """يرسل رد نصي، ويقسم الرسائل الطويلة (حد الواتساب 4096 حرف)"""
    url = f"{GRAPH_URL}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)] or [text]
    for chunk in chunks:
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": chunk},
        }
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code >= 400:
            print(f"WhatsApp send error: {r.status_code} {r.text}")


def send_whatsapp_cta(to_number: str, text: str, url: str, button_title: str = "🛒 شوف أرخص سعر"):
    """رسالة مع زر مدمج. إذا النص أطول من حد الزر (1024): النص كامل برسالة عادية + الزر برسالة قصيرة بعدها — بدون أي قص"""
    if len(text) > 1000:
        send_whatsapp_text(to_number, text)              # النص كامل بلا قص
        body = "اضغط الزر وتوجه لأرخص سعر 👇"            # رسالة الزر القصيرة
    else:
        body = text

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": body},
            "action": {
                "name": "cta_url",
                "parameters": {"display_text": button_title[:25], "url": url},
            },
        },
    }
    r = requests.post(
        f"{GRAPH_URL}/{PHONE_NUMBER_ID}/messages",
        json=payload,
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}",
                 "Content-Type": "application/json"},
        timeout=30,
    )
    if r.status_code >= 400:
        print(f"CTA send error: {r.status_code} {r.text}")
        # احتياط: لو فشل الزر نرسل رسالة عادية بالرابط عشان ما يضيع الرد
        if len(text) <= 1000:
            send_whatsapp_text(to_number, text + f"\n\n🔗 {url}")
        else:
            send_whatsapp_text(to_number, f"🔗 {url}")


@app.get("/")
async def health():
    return {"status": "running", "bot": "Kuwait Price Bot 🇰🇼 (Gemini 2.5)"}
