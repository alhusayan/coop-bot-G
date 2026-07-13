# -*- coding: utf-8 -*-
"""
بوت واتساب — بحث حي فوري عن أسعار المنتجات في الكويت
WhatsApp Cloud API (Meta) + FastAPI + Claude API (Live Web Search)
Deploy: Railway
"""

import os
import base64
import requests
from collections import deque
from fastapi import FastAPI, Request, Response, BackgroundTasks
import anthropic

app = FastAPI()

# ========= مفاتيح التشغيل (تنحط في Railway → Variables، مو هنا) =========
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
WHATSAPP_TOKEN    = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID   = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN      = os.environ.get("VERIFY_TOKEN", "MY_SECRET_COOP_BOT_TOKEN")

GRAPH_URL = "https://graph.facebook.com/v23.0"

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# منع الرد المكرر: نحفظ آخر 500 رسالة تمت معالجتها
processed_ids = deque(maxlen=500)

# حد يومي لكل رقم (حماية الرصيد من الاستخدام المفرط)
DAILY_LIMIT = 15
daily_usage = {}  # {"9655xxxxxxx": {"date": "2026-07-13", "count": 3}}

def check_daily_limit(number: str) -> bool:
    """True = مسموح، False = تجاوز الحد اليومي"""
    from datetime import date
    today = str(date.today())
    record = daily_usage.get(number)
    if not record or record["date"] != today:
        daily_usage[number] = {"date": today, "count": 1}
        return True
    if record["count"] >= DAILY_LIMIT:
        return False
    record["count"] += 1
    return True

SYSTEM_PROMPT = """أنت مساعد ذكي متخصص بأسعار المنتجات في دولة الكويت، ترد على عملاء واتساب.

مهمتك:
1. تعرّف على المنتج من الصورة أو من نص الرسالة.
2. سوّ بحثات حية (Live Web Search) موجّهة — لا تكتفي ببحث واحد عام. سوّ بحثات منفصلة بإضافة اسم المتجر أو نطاقه لاستعلام البحث. المتاجر الكويتية ذات المتاجر الإلكترونية الفعلية (أسعارها منشورة أونلاين):
   - جمعية دوت كوم: "اسم المنتج jm3eia.com"
   - توصيل: "اسم المنتج taw9eel.com"
   - أونكوست: "اسم المنتج oncost.com"
   - جراند هايبر: "اسم المنتج grandhyper.com"
   - سيتي هايبر: "اسم المنتج cchyper.com"
   - سلطان سنتر: "اسم المنتج sultan-center.com"
   - دروبز: "اسم المنتج Dropz Kuwait"
   - هاي آند باي: "اسم المنتج HiandBuy"
   - سيفكو: "اسم المنتج Saveco Kuwait"
   - وبحث عام: "اسم المنتج سعر الكويت"
   الجمعيات التعاونية (مشرف، الروضة وحولي، العديلية، صباح السالم، سلوى، بيان، الزهراء وغيرها):
   متاجرها الإلكترونية موجودة على منصة طلبات Talabat — ابحث: "اسم المنتج talabat جمعية" أو "اسم المنتج طلبات جمعية مشرف" (أو أي جمعية يطلبها العميل بالاسم). أسعار طلبات هي أسعار فعلية قابلة للطلب من فروع الجمعيات نفسها.
   إذا العميل سأل عن جمعية محددة بالاسم، خصص لها بحث باسمها إلزامياً.
   اختر 3-4 بحثات فقط — الأنسب لنوع المنتج (عندك ميزانية 4 بحثات، استغلها بذكاء). لولو وكارفور والميرة ومونوبري تظهر غالباً بالبحث العام.
   لعروض وتخفيضات الجمعيات الأسبوعية: ابحث "اسم المنتج عروض جمعيات ilofo" أو "el3rod".
3. مهم جداً: إذا لقيت المنتج في نتيجة بحث لكن السعر ما ظهر في المقتطف، افتح صفحة المنتج نفسها (web_fetch) واقرأ السعر منها مباشرة قبل ما ترد. لا تقول "السعر يظهر عند الدخول للموقع" إلا بعد ما تحاول تفتح الصفحة فعلياً.
4. اعرض النتائج بشكل مرتب وواضح.

قواعد الرد:
- الأسلوب: كويتي ودّي وسريع، مناسب لمحادثة واتساب.
- ابدأ باسم المنتج اللي تعرفت عليه.
- اعرض الأسعار كقائمة بسيطة: اسم المتجر — السعر بالدينار الكويتي (د.ك).
- رتبها من الأرخص للأغلى، وحط علامة ✅ عند أرخص سعر.
- إذا السعر من نتيجة بحث مو مؤكدة أو قديمة، نبّه إن السعر تقريبي وقد يختلف.
- إذا ما لقيت أسعار بالكويت، قول بصراحة إنك ما حصلت سعر مؤكد واقترح عليه وين يتأكد.
- لا تستخدم جداول Markdown (الواتساب ما يعرضها)، استخدم أسطر وإيموجي بسيطة.
- خل الرد مختصر — أقل من 15 سطر.
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

    # فحص الحد اليومي قبل أي معالجة مكلفة
    if msg_type in ("image", "text") and not check_daily_limit(from_number):
        send_whatsapp_text(from_number, "وصلت الحد اليومي للاستعلامات (15) 🙏 عاود باچر وحياك الله!")
        return

    try:
        content_blocks = []

        if msg_type == "image":
            # رسالة انتظار عشان العميل ما يحس البوت طافي (البحث ياخذ ثواني)
            send_whatsapp_text(from_number, "🔍 لحظة، قاعد أتعرف على المنتج وأدور أسعاره بالكويت...")

            image_b64, mime = download_whatsapp_media(message["image"]["id"])
            content_blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": mime, "data": image_b64},
            })
            content_blocks.append({
                "type": "text",
                "text": "تعرف على هذا المنتج وابحث الآن بحثاً حياً عن أسعاره الحالية في الكويت.",
            })

        elif msg_type == "text":
            user_text = message["text"]["body"]
            send_whatsapp_text(from_number, "🔍 ثواني، أدور لك الأسعار الحالية بالكويت...")
            content_blocks.append({
                "type": "text",
                "text": f"العميل يسأل: {user_text}\nابحث الآن بحثاً حياً عن الأسعار الحالية في الكويت ورد عليه.",
            })

        else:
            send_whatsapp_text(from_number, "حياك الله 🌟 دز لي صورة المنتج أو اكتب اسمه، وأدور لك أسعاره الحالية بالكويت فوراً 🛒")
            return

        # ===== استدعاء Claude مع البحث الحي المدمج =====
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content_blocks}],
            tools=[
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 4,
                },
                {
                    "type": "web_fetch_20250910",
                    "name": "web_fetch",
                    "max_uses": 2,
                    "max_content_tokens": 8000,
                },
            ],
            extra_headers={"anthropic-beta": "web-fetch-2025-09-10"},
        )

        # نجمع كل النصوص من الرد (البحث يرجع عدة أجزاء)
        reply_text = "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()

        if not reply_text:
            reply_text = "ما قدرت ألقى نتيجة واضحة 😅 جرب صورة أوضح أو اكتب اسم المنتج بالنص."

        send_whatsapp_text(from_number, reply_text)

    except Exception as e:
        print(f"Error processing message: {e}")
        try:
            send_whatsapp_text(from_number, "صار خلل بسيط 🙏 عيد المحاولة بعد شوي.")
        except Exception:
            pass


# ========= أدوات مساعدة =========
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
    return {"status": "running", "bot": "Kuwait Price Bot 🇰🇼"}
