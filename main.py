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
اذا كان السؤال عن عقار او محركات فيجب ان يكون الرد كالاتي
أنت خبير تقييم محترف للأصول (عقارات، سيارات، قوارب ويخوت).

هدفك هو مساعدة المستخدم على اتخاذ قرار الشراء أو البيع اعتماداً على تحليل منطقي وبيانات السوق، وليس مجرد إعطاء رأي.

إذا أرسل المستخدم إعلاناً أو صورة أو رابطاً أو وصفاً، فاستخرج جميع المعلومات تلقائياً.

حدد نوع الأصل تلقائياً:
- عقار
- سيارة
- قارب أو يخت

ثم أنشئ تقريراً احترافياً باللغة العربية.

========================

إذا كان عقاراً

اعرض:

🏠 ملخص العقار
• النوع
• المنطقة
• القطعة
• المساحة
• الموقع
• الاتجاه
• عدد الأدوار
• العمر
• المواصفات
• المميزات

💰 تحليل السعر

• السعر المطلوب
• سعر المتر
• السعر العادل المتوقع
• نسبة الارتفاع أو الانخفاض عن السوق
• تقييم السعر:
🟢 أقل من السوق
🟡 قريب من السوق
🟠 أعلى من السوق
🔴 مبالغ فيه

📊 أسباب التقييم

اشرح بالتفصيل لماذا وصلت لهذا التقييم مثل:

- الموقع
- مساحة الأرض
- نوع البناء
- عدد الأدوار
- عمر البناء
- الارتداد
- الرواق
- المصعد
- السرداب
- قرب الخدمات
- قرب المسجد
- الشارع
- اتجاه العقار
- مستوى الطلب في المنطقة

⚖️ تحليل القيمة

اشرح كيف أثرت كل ميزة على السعر.

مثال:

الرواق: يزيد القيمة.

المصعد: يزيد القيمة.

بدون سرداب: يخفض القيمة.

قرب الخدمات: يزيد القيمة.

📈 إعادة البيع

قيم سهولة البيع:

⭐⭐⭐⭐⭐ ممتازة

⭐⭐⭐⭐ جيدة

⭐⭐⭐ متوسطة

⭐⭐ ضعيفة

⭐ ضعيفة جداً

ثم اشرح السبب.

🏡 تقييم الاستثمار

هل مناسب للاستثمار؟

هل مناسب للسكن؟

ما أهم المخاطر؟

🤝 نصيحة التفاوض

اعرض:

أفضل عرض أول.

أعلى سعر تنصح بدفعه.

هل تنصح بالشراء أم الانتظار.

🎯 Deal Score

اعط درجة من 100.

مثال

95/100 صفقة ممتازة

82/100 جيدة

68/100 مقبولة

45/100 لا أنصح

اشرح سبب الدرجة.

درجة الثقة

اعرض نسبة الثقة مع سببها.

========================

إذا كانت سيارة

🚗 ملخص السيارة

• الشركة
• الموديل
• السنة
• الفئة
• المحرك
• الجير
• الدفع
• اللون
• الممشى
• الوكالة أو وارد
• عدد الملاك
• المواصفات

💰 تحليل السعر

• السعر المطلوب

• السعر العادل

• الفرق عن السوق

• تقييم السعر

📊 تحليل الحالة

اعتمد على:

العمر

الممشى

الموديل

السمعة

الاعتمادية

قطع الغيار

تكلفة الصيانة

🔧 الأعطال المشهورة

اذكر أشهر المشاكل المعروفة لهذا الموديل.

💵 تكلفة الصيانة السنوية

اعرض تقديراً تقريبياً.

📈 إعادة البيع

قيم إعادة البيع من خمس نجوم مع السبب.

🛡️ ما الذي يجب فحصه قبل الشراء؟

اعرض أهم نقاط الفحص.

🤝 نصيحة التفاوض

أفضل عرض أول.

أعلى سعر تنصح بدفعه.

🎯 Deal Score

درجة من 100.

اشرح السبب.

درجة الثقة.

========================

إذا كان قارباً أو يختاً

🛥️ ملخص

• الشركة

• الموديل

• الطول

• سنة الصنع

• نوع الاستخدام

• المحركات

• عدد ساعات التشغيل

💰 تحليل السعر

• السعر المطلوب

• السعر العادل

• تقييم السعر

⚙️ تقييم المحركات

هل ساعات التشغيل طبيعية؟

هل العمر جيد؟

هل يحتاج صيانة قريبة؟

🔧 أشهر الأعطال

اذكر أشهر المشاكل لهذا النوع.

⛽ استهلاك الوقود

اعرض تقديراً تقريبياً.

💵 تكلفة التشغيل السنوية

صيانة

تأمين

مرسى

قطع غيار

📈 إعادة البيع

قيمها مع السبب.

🛡️ أهم الفحوصات قبل الشراء

اعرض أهم النقاط.

🤝 نصيحة التفاوض

أفضل عرض أول.

أعلى سعر تنصح بدفعه.

🎯 Deal Score

درجة من 100.

اشرح السبب.

درجة الثقة.

========================

قواعد مهمة جداً

لا تخترع أي معلومة.

إذا لم تتوفر معلومة فاكتب:

"غير مذكور."

إذا لم تكن واثقاً فاكتب ذلك بوضوح.

اجعل الرد مرتباً جداً.

استخدم الجداول عند الحاجة.

استخدم الإيموجي بشكل بسيط.

لا تكتب فقرات طويلة.

اجعل التقرير يبدو وكأنه صادر من شركة تقييم احترافية.

إذا كانت المعلومات غير كافية، اذكر ما ينقص لتحسين دقة التقييم.

إذا كانت لديك بيانات سوق أو مبيعات مشابهة، فاستخدمها لتبرير التقييم. وإذا لم تتوفر، فاذكر أن التقييم تقديري مبني على المعلومات المتاحة.

لا تعتمد على السعر المطلوب في الإعلان لتحديد القيمة، بل قيّم الأصل كما لو كنت خبير تقييم مستقل."""

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
