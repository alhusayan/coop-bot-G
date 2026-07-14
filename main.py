# -*- coding: utf-8 -*-
import os, re, base64, requests
from collections import deque
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import Response

app = FastAPI()

# ========= المتغيرات من Railway =========
GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL    = "gemini-1.5-flash"
WHATSAPP_TOKEN  = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN    = os.environ.get("VERIFY_TOKEN", "MY_SECRET_COOP_BOT_TOKEN")
GRAPH_URL       = "https://graph.facebook.com/v20.0"
GEMINI_URL      = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

processed_ids = deque(maxlen=500)

SYSTEM_PROMPT = """أنت "مساعد الصياد الذكي" لأسعار الكويت. مهمتك:
1. تعرف على المنتج.
2. ابحث عن أرخص سعر في الجمعيات والمتاجر.
3. اعرض الأسعار بنقاط: ✅ الأرخص، • الثاني، • الثالث.
4. في نهاية الرد، اكتب الرابط المباشر للمتجر الأرخص بهذا الشكل الإلزامي: URL:https://... (رابط كامل)."""

@app.get("/webhook")
async def verify(req: Request):
    if req.query_params.get("hub.verify_token") == VERIFY_TOKEN:
        return Response(content=req.query_params.get("hub.challenge"), media_type="text/plain")
    return Response(status_code=403)

@app.post("/webhook")
async def handle(req: Request, bt: BackgroundTasks):
    data = await req.json()
    try:
        msg = data["entry"][0]["changes"][0]["value"]["messages"][0]
        if msg["id"] not in processed_ids:
            processed_ids.append(msg["id"])
            bt.add_task(process_message, msg)
    except: pass
    return {"status": "ok"}

def process_message(msg):
    from_num = msg["from"]
    # معالجة الصور
    if msg.get("type") == "image":
        send_text(from_num, "🔍 ثواني.. قاعد أصيد لك أرخص سعر!")
        media_id = msg["image"]["id"]
        # سحب الصورة
        meta = requests.get(f"{GRAPH_URL}/{media_id}", headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}).json()
        img = requests.get(meta["url"], headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}).content
        img_b64 = base64.standard_b64encode(img).decode("utf-8")
        parts = [{"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}, {"text": "سعر المنتج؟"}]
    else:
        parts = [{"text": f"سعر المنتج في الكويت: {msg['text']['body']}"}]

    # نداء Gemini
    payload = {"systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]}, "contents": [{"role": "user", "parts": parts}], "tools": [{"google_search": {}}]}
    res = requests.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload).json()
    text = "".join(p["text"] for p in res["candidates"][0]["content"]["parts"])
    
    # استخراج الرابط
    url_match = re.search(r"URL:(https?://[^\s]+)", text)
    url = url_match.group(1) if url_match else None
    text = text.replace(url_match.group(0), "").strip() if url_match else text

    # الإرسال
    if url: send_cta(from_num, text, url)
    else: send_text(from_num, text)

def send_text(to, text):
    requests.post(f"{GRAPH_URL}/{PHONE_NUMBER_ID}/messages", json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}}, headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"})

def send_cta(to, text, url):
    payload = {
        "messaging_product": "whatsapp", "to": to, "type": "interactive",
        "interactive": {
            "type": "cta_url", "body": {"text": text},
            "action": {"name": "cta_url", "parameters": {"display_text": "🛒 شوف أرخص سعر", "url": url}}
        }
    }
    requests.post(f"{GRAPH_URL}/{PHONE_NUMBER_ID}/messages", json=payload, headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"})
