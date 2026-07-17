# -*- coding: utf-8 -*-
import os, re, time, base64, requests, uuid
from collections import deque
from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import HTMLResponse

app = FastAPI()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_COOP_BOT_TOKEN")

GRAPH_URL = "https://graph.facebook.com/v20.0"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

processed_ids = deque(maxlen=500)
CARTS = {} # {cart_id: {products: [], total: float}}

SYSTEM_PROMPT_SINGLE = """
أنت مساعد تسوق كويتي. رد بهذا الشكل فقط:
📦 [اسم المنتج]
✅ [المتجر الأرخص] — [السعر] د.ك
• [المتجر الثاني] — [السعر] د.ك
• [المتجر الثالث] — [السعر] د.ك
في النهاية سطر واحد فقط: LINKS: xcite.com, blink.com.kw, eureka.com.kw
ممنوع روابط ظاهرة.
"""

def extract_products(user_text: str):
    # فصل سريع: +, و \n
    parts = re.split(r'\s*(?:\+|,|\n| و | \+ )\s*', user_text)
    parts = [p.strip() for p in parts if len(p.strip()) > 2]
    # لو كلمة وحدة بس، رجعها كمنتج واحد
    if len(parts) <= 1:
        return [user_text.strip()]
    return parts[:5] # حد أقصى 5 منتجات بالسلة

def get_final_url(url: str):
    try:
        r = requests.get(url, allow_redirects=True, timeout=10, stream=True)
        final = r.url
        r.close()
        if "vertexaisearch" in final or "grounding-api-redirect" in final: return ""
        return final if len(final) < 600 else ""
    except: return ""

def call_gemini(parts: list):
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT_SINGLE}]},
        "contents": [{"role": "user", "parts": parts}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2000},
    }
    r = requests.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload, timeout=90)
    if r.status_code >= 400: return "", {}
    try:
        data = r.json()
        cand = data["candidates"][0]
        text = "".join(p.get("text","") for p in cand["content"]["parts"]).strip()
        text = re.sub(r"https?://\S+", "", text)
        domains = []
        m = re.search(r"LINKS:\s*(.+)", text, re.I)
        if m:
            domains = [d.strip().lower() for d in re.split(r"[,|]+", m.group(1)) if "." in d]
            text = re.sub(r"\n?LINKS:.*", "", text, flags=re.I).strip()
        store_names = re.findall(r"(?:✅|•)\s*([^—\n]+?)\s*—", text)
        chunks = cand.get("groundingMetadata",{}).get("groundingChunks",[])
        temp = {}
        for c in chunks:
            uri = c.get("web",{}).get("uri")
            if not uri: continue
            for d in domains:
                if d.split(".")[0] in uri.lower():
                    if d not in temp: temp[d] = get_final_url(uri)
        if not temp:
            for c in chunks[:3]:
                uri=c.get("web",{}).get("uri")
                if uri: temp[uri]=get_final_url(uri)
        urls_map={}
        vals=list(temp.values())
        for i,s in enumerate(store_names):
            if i < len(vals) and vals[i]: urls_map[s.strip()]=vals[i]
        if not urls_map: urls_map=temp
        return text, dict(list(urls_map.items())[:3])
    except: return "", {}

@app.get("/webhook")
async def verify_webhook(request: Request):
    p=request.query_params
    if p.get("hub.mode")=="subscribe" and p.get("hub.verify_token")==VERIFY_TOKEN:
        return Response(content=p.get("hub.challenge"), media_type="text/plain")
    return Response("fail",403)

@app.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    data=await request.json()
    try:
        value=data["entry"][0]["changes"][0]["value"]
        if "messages" in value:
            msg=value["messages"][0]
            mid=msg.get("id")
            bot_id=value.get("metadata",{}).get("phone_number_id", PHONE_NUMBER_ID)
            if mid and mid not in processed_ids:
                processed_ids.append(mid)
                background_tasks.add_task(process_message, msg, bot_id)
    except: pass
    return {"status":"ok"}

def process_message(message: dict, bot_phone_id: str):
    from_number=message["from"]
    mtype=message.get("type")
    if mtype!="text":
        send_whatsapp_text(from_number,"دز لي أسماء المنتجات مع بعض مثل: ايفون 15 + ساعة ابل + شاحن", bot_phone_id)
        return
    user_text=message["text"]["body"]
    products=extract_products(user_text)

    if len(products)==1:
        # حالة منتج واحد - نفس كودك القديم
        send_whatsapp_text(from_number, f"🔍 أدور لك على {products[0]}...", bot_phone_id)
        txt, urls = call_gemini([{"text": f"ابحث عن {products[0]} في الكويت"}])
        if urls:
            send_whatsapp_text(from_number, txt, bot_phone_id)
            for n,u in urls.items():
                if u: send_whatsapp_cta(from_number, f"تسوق من {n} 👇", u, bot_phone_id, f"🛒 {n[:18]}")
        else:
            send_whatsapp_text(from_number, txt or "ما لقيت", bot_phone_id)
        return

    # حالة سلة متعددة - تسمح بالخلط
    send_whatsapp_text(from_number, f"تمام 👌 لقيت {len(products)} منتجات بسويلك سلة بأرخص أسعار (أخلط متاجر)...", bot_phone_id)
    cart_items=[]
    total=0.0
    for prod in products:
        txt, urls = call_gemini([{"text": f"ابحث عن سعر {prod} في الكويت"}])
        # اختر أرخص واحد (أول واحد ✅)
        cheapest_name, cheapest_url, cheapest_price = "غير متوفر", "", 0
        m = re.search(r"✅\s*([^—\n]+?)\s*—\s*([\d\.]+)", txt)
        if m:
            cheapest_name=m.group(1).strip()
            cheapest_price=float(m.group(2))
            cheapest_url=list(urls.values())[0] if urls else ""
        cart_items.append({"name":prod, "store":cheapest_name, "price":cheapest_price, "url":cheapest_url, "all_urls":urls})
        total+=cheapest_price
        time.sleep(0.6)

    cart_id=uuid.uuid4().hex[:8]
    CARTS[cart_id]={"products":cart_items, "total":total}

    summary="\n".join([f"• {it['name']} - {it['price']} د.ك ({it['store']})" for it in cart_items])
    msg=f"🛒 سلتك جاهزة ({len(cart_items)} منتجات)\n{summary}\n\n💰 الإجمالي بأرخص خلطة متاجر: *{total:.3f} د.ك*"
    send_whatsapp_text(from_number, msg, bot_phone_id)
    time.sleep(0.5)
    cart_url = f"https://{os.environ.get('RAILWAY_PUBLIC_DOMAIN','your-app.up.railway.app')}/cart/{cart_id}"
    send_whatsapp_cta(from_number, "اضغط لفتح السلة وتكمل الشراء", cart_url, bot_phone_id, "🛒 افتح السلة")

def send_whatsapp_text(to,text,bot_id):
    url=f"{GRAPH_URL}/{bot_id}/messages"
    h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    payload={"messaging_product":"whatsapp","to":to,"type":"text","text":{"body":text[:3900]}}
    requests.post(url,json=payload,headers=h,timeout=20)

def send_whatsapp_cta(to,text,url_link,bot_id,title):
    url=f"{GRAPH_URL}/{bot_id}/messages"
    h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    payload={"messaging_product":"whatsapp","to":to,"type":"interactive","interactive":{"type":"cta_url","body":{"text":text[:1024]},"action":{"name":"cta_url","parameters":{"display_text":title[:20],"url":url_link}}}}
    requests.post(url,json=payload,headers=h,timeout=20)

@app.get("/cart/{cart_id}", response_class=HTMLResponse)
async def cart_page(cart_id: str):
    cart=CARTS.get(cart_id)
    if not cart: return HTMLResponse("<h1>السلة منتهية</h1>",404)
    rows=""
    for it in cart["products"]:
        btns="".join([f"<a href='{u}' target='_blank' class='text-xs bg-gray-100 px-2 py-1 rounded mr-1'>{n}</a>" for n,u in it['all_urls'].items() if u])
        rows+=f"<div class='p-4 border-b flex justify-between'><div><b>{it['name']}</b><br><span class='text-sm text-gray-500'>{it['store']} - {it['price']} د.ك</span><div class='mt-1'>{btns}</div></div><a href='{it['url']}' target='_blank' class='bg-black text-white px-4 py-2 rounded h-fit'>شراء</a></div>"
    html=f"""<html dir='rtl'><head><meta name='viewport' content='width=device-width'><script src='https://cdn.tailwindcss.com'></script></head><body class='bg-gray-50'><div class='max-w-lg mx-auto bg-white min-h-screen'><div class='p-5 bg-black text-white'><h1 class='text-xl font-bold'>🛒 سلتك</h1><p>أرخص خلطة متاجر</p></div>{rows}<div class='p-5'><div class='flex justify-between text-lg font-bold'><span>الإجمالي</span><span>{cart['total']:.3f} د.ك</span></div><p class='text-xs text-gray-400 mt-3'>* كل زر يوديك مباشرة لصفحة المنتج في المتجر الأرخص له. تقدر تخلط متاجر براحتك.</p></div></div></body></html>"""
    return HTMLResponse(html)

@app.get("/")
async def health(): return {"status":"cart bot running"}
