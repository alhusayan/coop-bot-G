# -*- coding: utf-8 -*-
import os, time, base64, uuid, asyncio, hashlib, json
from collections import deque, defaultdict
from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import HTMLResponse
import httpx # ✅ استخدام httpx بدلاً من requests للسرعة

app = FastAPI()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# ✅ التحديث للنسخة الصحيحة والأسرع
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash") 
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_COOP_BOT_TOKEN")

GRAPH_URL = "https://graph.facebook.com/v20.0"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

processed_ids = deque(maxlen=1000)
CARTS = {}
IMAGE_BUFFER = defaultdict(lambda: {"images": [], "time": 0, "bot_id": ""})
BUFFER_SECONDS = 4
HEADERS = {"User-Agent": "Mozilla/5.0"}
CACHE = {}
CACHE_TTL = 6 * 3600

# ✅ تعديل الـ Prompt لإرجاع JSON فقط
SYSTEM_PROMPT = """
أنت مساعد تسوق كويتي دقيق جداً.
خطوات إلزامية:
1. حدد المنتج بالاسم الإنجليزي الرسمي الدقيق (مثال: Wilson Clash 25 V2 وليس "مضرب تنس").
2. ابحث بالاسم الإنجليزي + Kuwait price في المتاجر الكويتية (مثل xcite, blink, eureka, وغيرها).
3. استخرج أرخص 3 أسعار حقيقية مع روابطها المباشرة.

يجب أن يكون ردك بصيغة JSON فقط، بهذا الشكل تماماً (بدون أي نصوص إضافية):
{
  "product_arabic": "اسم المنتج بالعربي",
  "product_english": "الاسم الإنجليزي",
  "results": [
    {"store": "اسم المتجر", "price": 15.5, "url": "الرابط المباشر للمنتج"}
  ]
}
"""

def cache_key(parts):
    h = hashlib.sha256()
    for p in parts:
        if "text" in p: h.update(p["text"].encode())
        if "inline_data" in p: h.update(p["inline_data"]["data"][:200].encode())
    return h.hexdigest()

async def call_gemini_async(parts, system=SYSTEM_PROMPT):
    key = cache_key(parts)
    if key in CACHE and time.time() - CACHE[key][0] < CACHE_TTL:
        return CACHE[key][1]

    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": parts}],
        "tools": [{"google_search": {}}],
        "generationConfig": {
            "temperature": 0.0, 
            "responseMimeType": "application/json" # ✅ إجبار الموديل على JSON
        },
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            r = await client.post(f"{GEMINI_URL}?key={GEMINI_API_KEY}", json=payload)
            if r.status_code >= 400: return None
            
            data = r.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            
            # تحويل النص إلى قاموس بايثون
            result_dict = json.loads(text)
            
            # تنظيف الروابط من أدوات قوقل للتتبع إن وجدت
            for item in result_dict.get("results", []):
                if "vertexaisearch" in item["url"]:
                    item["url"] = "" 
            
            CACHE[key] = (time.time(), result_dict)
            return result_dict
        except Exception as e:
            print(f"Gemini err {e}")
            return None

async def download_whatsapp_media_async(mid):
    h = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        meta_res = await client.get(f"{GRAPH_URL}/{mid}", headers=h)
        meta = meta_res.json()
        img_res = await client.get(meta["url"], headers=h)
        return base64.b64encode(img_res.content).decode(), meta.get("mime_type","image/jpeg")

async def send_whatsapp_text_async(to, text, bot_id):
    url = f"{GRAPH_URL}/{bot_id}/messages"
    h = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text[:3900]}}
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload, headers=h)

# ... (دالة send_whatsapp_cta_async مشابهة للدالة السابقة ولكن باستخدام httpx) ...

async def fetch_product_from_text_async(prod):
    data = await call_gemini_async([{"text": f"ابحث عن سعر {prod} في الكويت"}])
    if data and data.get("results"):
        best = data["results"][0]
        return {"name": data["product_arabic"], "store": best["store"], "price": best["price"], "url": best["url"]}
    return {"name": prod, "store": "غير متوفر", "price": 0, "url": ""}

@app.post("/webhook")
async def receive(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    try:
        value = data["entry"][0]["changes"][0]["value"]
        if "messages" not in value: return {"status": "ok"}
        msg = value["messages"][0]
        mid = msg.get("id")
        
        if mid in processed_ids: return {"status": "dup"}
        processed_ids.append(mid)
        
        bot_id = value.get("metadata", {}).get("phone_number_id", PHONE_NUMBER_ID)
        from_number = msg["from"]
        
        if msg.get("type") == "text":
            # تشغيل المعالجة في الخلفية بدون حجب الاستجابة للواتساب
            background_tasks.add_task(process_text_message_async, msg, bot_id)
            
    except Exception as e: 
        print(f"webhook err {e}")
    return {"status": "ok"}

async def process_text_message_async(message, bot_id):
    from_number = message["from"]
    user_text = message["text"]["body"]
    
    # افتراضياً للتبسيط: استخراج المنتجات (يمكنك إبقاء دالة extract_products كما هي)
    products = [user_text] 
    
    await send_whatsapp_text_async(from_number, f"🔍 جاري البحث عن {products[0]}...", bot_id)
    
    data = await call_gemini_async([{"text": f"ابحث عن سعر {products[0]} في الكويت"}])
    
    if data and data.get("results"):
        reply = f"📦 {data['product_arabic']}\n\n"
        for i, res in enumerate(data["results"]):
            mark = "✅" if i == 0 else "•"
            reply += f"{mark} {res['store']} — {res['price']} د.ك\n"
        
        await send_whatsapp_text_async(from_number, reply, bot_id)
        # إرسال أزرار الروابط هنا...
    else:
        await send_whatsapp_text_async(from_number, "عذراً، لم أتمكن من العثور على أسعار دقيقة.", bot_id)
