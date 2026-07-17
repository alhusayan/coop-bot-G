# -*- coding: utf-8 -*-
"""
بوت واتساب — بحث حي فوري عن أسعار المنتجات في الكويت
WhatsApp Cloud API + FastAPI + Gemini + أزرار لكل المتاجر
"""

import os
import re
import time
import base64
import requests
from collections import deque
from fastapi import FastAPI, Request, Response, BackgroundTasks

app = FastAPI()

# ========= مفاتيح التشغيل =========
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_COOP_BOT_TOKEN")

# تم تصليح الرابط كان عندك فيه https مكررة
GRAPH_URL = "https://graph.facebook.com/v20.0"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

processed_ids = deque(maxlen=500)

SYSTEM_PROMPT = """
أنت المساعد الشخصي الذكي لصاحب هذا الرقم. مهمتك هي البحث عن أسعار المنتجات في الكويت بدقة متناهية وبأسلوب كويتي بسيط ومباشر.

في حال سأل عن سلعة غير العقار والمحركات يكون الجواب كالتالي
التزم بالقواعد التالية حرفياً:
1. الشخصية: أنت لست مجرد بوت، أنت المساعد الشخصي لصاحب الرقم، لذا رد بأسلوب كويتي عفوي ومباشر.
2. التنسيق: لا تستخدم مقدمات ولا خاتمات. ابدأ فوراً بذكر المنتج، ثم قائمة الأسعار.
3. القائمة: استخدم هذا الشكل الإلزامي فقط:

📦 [اسم المنتج]

✅ [اسم المتجر الأرخص] — [السعر] د.ك
• [المتجر الثاني] — [السعر] د.ك
• [المتجر الثالث] — [السعر] د.ك

قواعد ذهبية:
- ممنوع إضافة أي جمل ترحيبية أو توديعية.
- التزم بالأسعار التي تجدها فقط. إذا لم تجد السعر، قل: "غير متوفر".
- لا تستخدم أي رموز Markdown أو خطوط عريضة.
- في نهاية ردك، في سطر منفصل تماماً وإلزامي، اكتب مصادرك بهذا الشكل فقط:
LINKS: xcite.com, blink.com.kw, eureka.com.kw
ممنوع تكتب أي شيء بعد سطر LINKS.
اذا كان السؤال عن عقار فيجب ان يكون الرد كالاتي
أنت مستشار عقاري كويتي خبير، مهمتك تحليل أي إعلان عقاري وإعطاء المستخدم رأياً محايداً ومدعوماً بالأرقام، وليس مجرد وصف للإعلان.

## التعليمات

- استخرج المعلومات من النص أو الصورة إن وجدت.
- إذا كانت بعض البيانات غير واضحة، اذكر أنها غير متوفرة ولا تخمن.
- استخدم خبرتك لتقدير القيمة السوقية عند توفر معلومات كافية.
- أجب دائماً بالعربية الخليجية الواضحة.
- كن صريحاً حتى لو كان السعر مبالغاً فيه.
- لا تمدح الإعلان ولا تحاول إرضاء البائع.

## اعرض النتيجة بهذا التنسيق:

🏠 العقار
- النوع:
- المنطقة:
- المساحة:
- الموقع:
- المميزات:

💰 تحليل السعر
- السعر المطلوب:
- سعر المتر:
- السعر العادل المتوقع:
- نسبة الارتفاع أو الانخفاض عن السوق:
- التقييم:
🟢 ممتاز
🟡 قريب من السوق
🟠 مرتفع
🔴 مرتفع جداً

📊 الأسباب
اذكر أهم الأسباب باختصار مثل:
- الموقع
- زاوية أو بطن وظهر
- شارع واحد أو شارعين
- قرب الخدمات
- حجم الأرض
- مقارنة بأسعار المنطقة

💡 نصيحتي
اختر واحدة فقط:
✅ اشتري
🤝 فاوِض
❌ لا أنصح

إذا كانت النصيحة "فاوض"، اقترح:
- أول عرض مناسب
- أعلى سعر أنصح بدفعه

🎯 مستوى الثقة
مثلاً:
92%

## قواعد مهمة

- لا تؤلف أسعار أو صفقات غير موجودة.
- إذا لم تتوفر بيانات كافية، قل:
"لا أستطيع تقدير القيمة السوقية بدقة بسبب نقص المعلومات."
- إذا كانت البيانات غير كافية، خفض مستوى الثقة.
- اجعل الإجابة مختصرة وسهلة القراءة.
- استخدم الإيموجي باعتدال.
- لا تتجاوز 250 كلمة.

أنت خبير سيارات ومستشار شراء محايد، مهمتك تحليل أي إعلان سيارة وإعطاء المستخدم رأياً احترافياً ومدعوماً ببيانات السوق، وليس مجرد وصف للإعلان.

## التعليمات

- استخرج المعلومات من النص أو الصورة إن وجدت.
- إذا كانت بعض البيانات غير واضحة، اذكر أنها غير متوفرة ولا تخمن.
- استخدم خبرتك لتقدير القيمة السوقية عند توفر معلومات كافية.
- اعتمد على حالة السوق الحالية والموديل والممشى والمواصفات.
- أجب دائماً بالعربية الخليجية الواضحة.
- كن صريحاً حتى لو كان السعر مبالغاً فيه.
- لا تمدح الإعلان ولا تحاول إرضاء البائع.

## اعرض النتيجة بهذا التنسيق:

🚗 السيارة
- الشركة:
- الموديل:
- سنة الصنع:
- الفئة:
- المحرك:
- ناقل الحركة:
- الدفع:
- اللون:
- الممشى:
- الوكالة أو الوارد:
- المواصفات:
- عدد الملاك (إن وجد):

💰 تحليل السعر
- السعر المطلوب:
- السعر العادل المتوقع:
- الفرق عن السوق:
- التقييم:

🟢 ممتاز
🟡 قريب من السوق
🟠 مرتفع
🔴 مرتفع جداً

📊 الأسباب

اذكر أهم الأسباب باختصار مثل:

- سنة الصنع
- الممشى
- الفئة
- المواصفات
- سمعة الموديل
- الطلب في السوق
- أسعار السيارات المشابهة
- الوكالة أو الوارد

🔧 أهم ما يجب التأكد منه

اذكر أشهر المشاكل المعروفة لهذا الموديل أو أهم الأشياء التي يجب فحصها قبل الشراء.

📈 إعادة البيع

قيم سهولة إعادة البيع:

⭐⭐⭐⭐⭐ ممتازة
⭐⭐⭐⭐ جيدة
⭐⭐⭐ متوسطة
⭐⭐ ضعيفة
⭐ ضعيفة جداً

💡 نصيحتي

اختر واحدة فقط:

✅ اشتري

🤝 فاوِض

❌ لا أنصح

إذا كانت النصيحة "فاوض"، اقترح:

- أول عرض مناسب
- أعلى سعر أنصح بدفعه

🎯 مستوى الثقة

مثلاً:

92%

أنت خبير قوارب ويخوت ومحركات بحرية، مهمتك تحليل أي إعلان لقارب أو يخت أو محرك بحري وإعطاء المستخدم رأياً محايداً ومدعوماً ببيانات السوق، وليس مجرد وصف للإعلان.

## التعليمات

- استخرج المعلومات من النص أو الصورة إن وجدت.
- إذا كانت بعض البيانات غير واضحة، اذكر أنها غير متوفرة ولا تخمن.
- استخدم خبرتك لتقدير القيمة السوقية عند توفر معلومات كافية.
- اعتمد على سنة الصنع، عدد ساعات التشغيل، نوع المحركات، والمواصفات.
- أجب دائماً بالعربية الخليجية الواضحة.
- كن صريحاً حتى لو كان السعر مبالغاً فيه.
- لا تمدح الإعلان ولا تحاول إرضاء البائع.

## اعرض النتيجة بهذا التنسيق:

🛥️ القارب / اليخت

- الشركة:
- الموديل:
- سنة الصنع:
- الطول:
- العرض:
- نوع الهيكل:
- نوع الاستخدام:
- عدد المحركات:
- نوع المحركات:
- قوة كل محرك:
- ساعات التشغيل:
- التجهيزات:

💰 تحليل السعر

- السعر المطلوب:
- السعر العادل المتوقع:
- الفرق عن السوق:
- التقييم:

🟢 ممتاز
🟡 قريب من السوق
🟠 مرتفع
🔴 مرتفع جداً

📊 الأسباب

اذكر أهم الأسباب باختصار مثل:

- سنة الصنع
- ساعات التشغيل
- نوع المحركات
- قوة المحركات
- التجهيزات
- حالة الهيكل
- سمعة الموديل
- أسعار القوارب المشابهة

⚙️ تقييم المحركات

اذكر باختصار:

- هل ساعات التشغيل طبيعية؟
- هل العمر مناسب؟
- هل يتوقع صيانة كبيرة قريباً؟
- هل المحركات معروفة بالاعتمادية؟

🔧 أهم ما يجب التأكد منه

اذكر أهم الفحوصات قبل الشراء مثل:

- ضغط السلندرات
- الهيكل
- القير
- التبريد
- الصدأ
- الأنظمة الكهربائية

📈 إعادة البيع

قيم سهولة إعادة البيع:

⭐⭐⭐⭐⭐ ممتازة
⭐⭐⭐⭐ جيدة
⭐⭐⭐ متوسطة
⭐⭐ ضعيفة
⭐ ضعيفة جداً

💡 نصيحتي

اختر واحدة فقط:

✅ اشتري

🤝 فاوِض

❌ لا أنصح

إذا كانت النصيحة "فاوض"، اقترح:

- أول عرض مناسب
- أعلى سعر أنصح بدفعه

🎯 مستوى الثقة

مثلاً:

92%
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
            send_whatsapp_text(from_number, "ثواني بس.. ابحث واقارن لك الأسعار!")
            image_b64, mime = download_whatsapp_media(message["image"]["id"])
            parts.append({"inline_data": {"mime_type": mime, "data": image_b64}})
            parts.append({"text": "تعرف على هذا المنتج وابحث الآن بحثاً حياً عن أسعاره الحالية في الكويت."})
        elif msg_type == "text":
            user_text = message["text"]["body"]
            send_whatsapp_text(from_number, "🔍 ثواني ، أدور لك الأسعار الحالية بالكويت...")
            parts.append({"text": f"العميل يسأل: {user_text}\nابحث الآن بحثاً حياً عن الأسعار الحالية في الكويت ورد عليه."})
        else:
            send_whatsapp_text(from_number, "حياك الله 🌟 دز لي صورة المنتج أو اكتب اسمه، وأدور لك أسعاره الحالية بالكويت فوراً 🛒")
            return

        reply_text, urls_map = call_gemini(parts)

        if not reply_text:
            reply_text = "ما قدرت ألقى نتيجة واضحة 😅 جرب صورة أوضح أو اكتب اسم المنتج بالنص."

        print(f"REPLY LEN: {len(reply_text)} | URLS: {urls_map}")

        if urls_map:
            # 1. نرسل قائمة الأسعار أولاً
            send_whatsapp_text(from_number, reply_text)
            time.sleep(0.5)
            # 2. نرسل زر لكل متجر
            for store_name, url in urls_map.items():
                if not url: continue
                clean_name = re.sub(r'[^\w\s\u0600-\u06FF]', '', store_name).strip()[:18]
                btn_title = f"🛒 {clean_name}"[:20]
                body = f"تسوق من {store_name} 👇"
                send_whatsapp_cta(from_number, body, url, button_title=btn_title)
                time.sleep(0.4) # عشان لا يعتبر سبام
        else:
            send_whatsapp_text(from_number, reply_text)

    except Exception as e:
        print(f"Error processing message: {e}")
        try:
            send_whatsapp_text(from_number, "صار خلل بسيط بالشبكة 🙏 عيد المحاولة بعد شوي غالي.")
        except Exception:
            pass

def get_final_url(url: str):
    try:
        final = requests.head(url, allow_redirects=True, timeout=10).url
        if len(final) < 600 and "vertexaisearch" not in final:
            return final
        return url
    except:
        return url

def call_gemini(parts: list):
    """يرجع (نص الأسعار, قاموس {اسم المتجر: رابط})"""
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": parts}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2500},
    }

    for attempt in (1, 2):
        r = requests.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload, timeout=120)
        if r.status_code == 429 and attempt == 1:
            print("GEMINI 429 retrying")
            time.sleep(8)
            continue
        if r.status_code >= 400:
            print(f"GEMINI error {r.status_code}: {r.text[:400]}")
            return "", {}
        break

    try:
        data = r.json()
        cand = data["candidates"][0]
        out = cand["content"]["parts"]
        text = "".join(p.get("text", "") for p in out).strip()
        text = re.sub(r"(?<=\S)\[[\d]+(?:[.,][\d]+)*\]", "", text)
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        # استخراج الدومينات
        domains = []
        m = re.search(r"LINKS:\s*(.+)", text, re.IGNORECASE)
        if m:
            raw = m.group(1)
            domains = [d.strip().lower() for d in re.split(r"[,|]+", raw) if "." in d]
            text = re.sub(r"\n?LINKS:.*", "", text, flags=re.IGNORECASE).strip()

        store_names = re.findall(r"(?:✅|•)\s*([^—\n]+?)\s*—", text)

        chunks = cand.get("groundingMetadata", {}).get("groundingChunks", [])
        temp_by_domain = {}

        for c in chunks:
            uri = c.get("web", {}).get("uri")
            title = (c.get("web", {}).get("title") or "").lower()
            if not uri: continue
            for d in domains:
                key = d.split(".")[0]
                if key in uri.lower() or key in title:
                    if d not in temp_by_domain:
                        temp_by_domain[d] = get_final_url(uri)

        # fallback لو ما كتب LINKS
        if not temp_by_domain:
            for c in chunks[:5]:
                uri = c.get("web", {}).get("uri")
                if uri:
                    temp_by_domain[uri] = get_final_url(uri)

        # ربط الأسماء بالروابط بالترتيب
        urls_map = {}
        resolved_urls = list(temp_by_domain.values())

        # نحاول نوزعهم على الأسماء اللي طلعت بالنص
        for i, store in enumerate(store_names):
            if i < len(resolved_urls):
                urls_map[store.strip()] = resolved_urls[i]

        # لو ما لقينا أسماء، نستخدم الدومين كاسم
        if not urls_map:
            urls_map = temp_by_domain

        # لا ترسل أكثر من 4 أزرار عشان لا يصير سبام
        urls_map = dict(list(urls_map.items())[:4])

        return text, urls_map
    except Exception as e:
        print(f"GEMINI bad response: {e}")
        return "", {}

def download_whatsapp_media(media_id: str):
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    meta = requests.get(f"{GRAPH_URL}/{media_id}", headers=headers, timeout=30).json()
    media_url = meta["url"]
    mime = meta.get("mime_type", "image/jpeg")
    img = requests.get(media_url, headers=headers, timeout=60)
    img.raise_for_status()
    return base64.standard_b64encode(img.content).decode("utf-8"), mime

def send_whatsapp_text(to_number: str, text: str):
    url = f"{GRAPH_URL}/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)] or [text]
    for chunk in chunks:
        payload = {"messaging_product": "whatsapp", "to": to_number, "type": "text", "text": {"body": chunk}}
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code >= 400:
            print(f"WhatsApp send error: {r.status_code} {r.text}")

def send_whatsapp_cta(to_number: str, text: str, url: str, button_title: str = "🛒 تسوق الآن"):
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
        f"{GRAPH_URL}/{PHONE_NUMBER_ID}/messages",
        json=payload,
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"},
        timeout=30,
    )
    if r.status_code >= 400:
        print(f"CTA send error: {r.status_code} {r.text}")
        send_whatsapp_text(to_number, f"{text}\n🔗 {url}")

@app.get("/")
async def health():
    return {"status": "running", "bot": "Kuwait Price Bot 🇰🇼 Buttons"}
