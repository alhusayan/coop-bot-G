# -*- coding: utf-8 -*-
"""
بوت واتساب — الصياد الذكي للأسعار بالكويت
مُحدث بأفضل ممارسات استخراج الروابط المباشرة ومنع الهلوسة
"""

import os, re, base64, requests, urllib.parse
from collections import deque
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import Response

app = FastAPI()

# ========= المتغيرات =========
GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL    = "gemini-1.5-flash"
WHATSAPP_TOKEN  = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN    = os.environ.get("VERIFY_TOKEN", "MY_SECRET_COOP_BOT_TOKEN")
GRAPH_URL       = "https://graph.facebook.com/v20.0"
GEMINI_URL      = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

processed_ids = deque(maxlen=500)

SYSTEM_PROMPT = """أنت المساعد الشخصي الذكي لصاحب هذا الرقم. مهمتك البحث عن أسعار المنتجات في الكويت بدقة وبأسلوب كويتي مباشر.

القواعد:
1. الشخصية: كويتي عفوي، مباشر، بدون ترحيب أو وداع.
2. التنسيق: 
📦 [اسم المنتج]
✅ [المتجر الأرخص] — [السعر] د.ك
• [المتجر الثاني] — [السعر] د.ك
• [المتجر الثالث] — [السعر] د.ك
3. في نهاية الرد، يجب أن تضع الرابط المباشر للمتجر الأرخص حصراً بهذا الشكل المشفر: URL_START:https://...:URL_END
(لا تكتب أي كلمة أخرى بجانب هذا الرابط، التزم بهذا الشكل حرفياً)."""

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
    # معالجة الصور والنصوص
    if msg.get("type") == "image":
        send_text(from_num, "🔍 ثواني.. قاعد أصيد لك أرخص سعر!")
        media_id = msg["image"]["id"]
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
    
    # استخراج الرابط "المشفر" بدقة
    url_match = re.search(r"URL_START:(https?://[^\s:]+):URL_END", text)
    url = url_match.group(1) if url_match else None
    if url_match: text = text.replace(url_match.group(0), "").strip()

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
    r = requests.post(f"{GRAPH_URL}/{PHONE_NUMBER_ID}/messages", json=payload, headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"})
    if r.status_code >= 400: send_text(to, text + f"\n\n🔗 {url}")
