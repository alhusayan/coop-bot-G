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

SYSTEM_PROMPT = """أنت مساعد ذكي متخصص بأسعار المنتجات في دولة الكويت، ترد على عملاء واتساب.

مهمتك:
1. تعرّف على المنتج من الصورة أو من نص الرسالة.
2. سوّ بحثات Google موجّهة — لا تكتفي ببحث واحد عام. سوّ بحثات منفصلة بإضافة اسم المتجر أو نطاقه لاستعلام البحث. المتاجر الكويتية ذات المتاجر الإلكترونية الفعلية (أسعارها منشورة أونلاين):
   - جمعية دوت كوم: "اسم المنتج jm3eia.com"
   - توصيل: "اسم المنتج taw9eel.com"
   - أونكوست: "اسم المنتج oncost.com"
   - جراند هايبر: "اسم المنتج grandhyper.com"
   - سيتي هايبر: "اسم المنتج cchyper.com"
   - سلطان سنتر: "اسم المنتج sultan-center.com"
   - دروبز: "اسم المنتج Dropz Kuwait"
   - هاي آند باي: "اسم المنتج HiandBuy"
   - سيفكو: "اسم المنتج Saveco Kuwait"
   - مقاضي: "اسم المنتج maqadhe.com"
   - مكاني: "اسم المنتج Makani"
   - وبحث عام: "اسم المنتج سعر الكويت"
   الجمعيات التعاونية (مشرف، الروضة وحولي، العديلية، صباح السالم، سلوى، بيان، الزهراء وغيرها):
   متاجرها الإلكترونية موجودة على منصة طلبات Talabat — ابحث: "اسم المنتج talabat جمعية" أو "اسم المنتج طلبات جمعية مشرف" (أو أي جمعية يطلبها العميل بالاسم). أسعار طلبات هي أسعار فعلية قابلة للطلب من فروع الجمعيات نفسها.
   إذا العميل سأل عن جمعية محددة بالاسم، خصص لها بحث باسمها إلزامياً.
   اختر 5-7 بحثات من الأنسب لنوع المنتج. لولو وكارفور والميرة ومونوبري تظهر غالباً بالبحث العام.
   لعروض وتخفيضات الجمعيات الأسبوعية: ابحث "اسم المنتج عروض جمعيات ilofo" أو "el3rod".
3. اعرض النتائج بشكل مرتب وواضح.

قواعد الرد:
- الأسلوب: كويتي ودّي وسريع، مناسب لمحادثة واتساب.
- ابدأ باسم المنتج اللي تعرفت عليه.
- اعرض الأسعار كقائمة بسيطة: اسم المتجر — السعر بالدينار الكويتي (د.ك).
- رتبها من الأرخص للأغلى، وحط علامة ✅ عند أرخص سعر.
- إذا السعر من نتيجة بحث مو مؤكدة أو قديمة، نبّه إن السعر تقريبي وقد يختلف.
- إذا ما لقيت أسعار بالكويت، قول بصراحة إنك ما حصلت سعر مؤكد واقترح عليه وين يتأكد.
- لا تستخدم جداول Markdown (الواتساب ما يعرضها)، ولا عناوين # ولا ** غامق Markdown — أسطر وإيموجي بسيطة فقط.
- خل الرد مختصر — أقل من 15 سطر.
- لا تكتب أي روابط في ردك إطلاقاً — الروابط تُضاف تلقائياً من النظام.
- لا تستخدم علامات استشهاد أو أقواس مرجعية مثل [1] أو [4.2.6] نهائياً.
- في نهاية ردك أضف سطراً أخيراً منفصلاً بهذا الشكل بالضبط: BEST:<دومين المتجر الأرخص> مثل BEST:luluhypermarket.com — هذا السطر للنظام ولن يراه العميل.
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
        cand = data["candidates"][0]
        out = cand["content"]["parts"]
        text = "".join(p.get("text", "") for p in out).strip()

        # تنظيف احتياطي: حذف أي علامات استشهاد أو روابط تسربت من الموديل
        text = re.sub(r"\[[\d.,\s]+\]", "", text)
        text = re.sub(r"https?://\S+", "", text).strip()

        # استخراج دومين الأرخص من سطر BEST: ثم حذفه من النص
        best_domain = None
        m = re.search(r"BEST:\s*([\w.-]+)", text)
        if m:
            best_domain = m.group(1).lower()
            text = re.sub(r"\n?BEST:.*", "", text).strip()

        # رابط واحد فقط: رابط الـgrounding المطابق للدومين الأرخص، مفكوكاً لرابط نهائي قصير
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
                if len(final) < 200 and "vertexaisearch" not in final:
                    text += f"\n\n🔗 {final}"
        except Exception as e:
            print(f"LINK RESOLVE: {e}")

        return text
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


@app.get("/")
async def health():
    return {"status": "running", "bot": "Kuwait Price Bot 🇰🇼 (Gemini 2.5)"}
