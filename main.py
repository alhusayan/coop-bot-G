# -*- coding: utf-8 -*-
import os, re, time, base64, requests, uuid, asyncio, hashlib
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import HTMLResponse
from urllib.parse import quote

app = FastAPI()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# تم التعديل إلى أحدث نسخة مستقرة ومناسبة للبحث
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash") 
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_COOP_BOT_TOKEN")

GRAPH_URL = "https://graph.facebook.com/v20.0"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

processed_ids = deque(maxlen=1000)
CARTS = {}
IMAGE_BUFFER = defaultdict(lambda: {"images": [], "time": 0, "bot_id": ""})
BUFFER_SECONDS = 4
WORKERS = ThreadPoolExecutor(max_workers=5)
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ===== كاش النتائج =====
CACHE = {}
CACHE_TTL = 6 * 3600  # 6 ساعات

def cache_key(parts):
    h = hashlib.sha256()
    for p in parts:
        if "text" in p: h.update(p["text"].encode())
        if "inline_data" in p: h.update(p["inline_data"]["data"][:500].encode())
    return h.hexdigest()

def cache_get(key):
    item = CACHE.get(key)
    if item and time.time() - item[0] < CACHE_TTL:
        return item[1], item[2]
    CACHE.pop(key, None)
    return None

def cache_set(key, text, urls):
    if len(CACHE) > 500:
        oldest = min(CACHE, key=lambda k: CACHE[k][0]); CACHE.pop(oldest, None)
    CACHE[key] = (time.time(), text, urls)

# التعديل الأهم: إجبار النموذج على جلب الرابط المباشر
SYSTEM_PROMPT = """
أنت مساعد تسوق كويتي دقيق جداً. تستخدم أداة بحث جوجل المدمجة لك.

التعليمات:
1. حدد المنتج بالاسم الإنجليزي الرسمي الدقيق (مثال: Apple Watch Ultra 2).
2. ابحث في المتاجر الكويتية (مثل xcite, blink, eureka, best, alghanim, lulu, taw9eel) عن السعر الحالي.
3. استخرج السعر ورابط *صفحة المنتج المباشرة* من نتائج البحث. 
4. اختر أرخص 3 أسعار وجدتها فعلياً وموثقة برابط. ممنوع تخمين الأسعار أو الروابط.

يجب أن يكون ردك بهذا الشكل الحرفي (ممنوع استخدام Markdown للروابط):
📦 [اسم المنتج بالعربي] ([الاسم الإنجليزي الرسمي])
✅ [المتجر الأرخص] — [السعر] د.ك
• [المتجر الثاني] — [السعر] د.ك
• [المتجر الثالث] — [السعر] د.ك

LINKS:
[المتجر الأرخص]=[رابط صفحة المنتج المباشر]
[المتجر الثاني]=[رابط صفحة المنتج المباشر]
[المتجر الثالث]=[رابط صفحة المنتج المباشر]
"""

def call_gemini(parts, system=SYSTEM_PROMPT, use_cache=True):
    key = cache_key(parts) if use_cache else None
    if key:
        cached = cache_get(key)
        if cached: return cached
        
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": parts}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1000},
    }
    try:
        r = requests.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload, timeout=45)
        if r.status_code >= 400: 
            print(r.text)
            return "", {}
            
        data = r.json()
        cand = data.get("candidates", [{}])[0]
        text = "".join(p.get("text","") for p in cand.get("content", {}).get("parts", [])).strip()
        
        urls = {}
        # استخراج قسم الروابط الذي أنشأه النموذج
        links_match = re.search(r"LINKS:\s*(.+)", text, re.I | re.DOTALL)
        if links_match:
            raw_links = links_match.group(1).strip().split('\n')
            for line in raw_links:
                if "=" in line:
                    name, link = line.split("=", 1)
                    name, link = name.strip(), link.strip()
                    if link.startswith("http"):
                        urls[name] = link
                        
        # إزالة قسم الروابط من النص ليكون العرض نظيفاً للمستخدم
        clean_text = re.sub(r"\n?LINKS:.*", "", text, flags=re.I | re.DOTALL).strip()
        clean_text = clean_text.replace("**", "")

        # Fallback ذكي: إذا لم يجلب رابط مباشر لأحد المتاجر، نصنع له رابط بحث دقيق
        pname = ""
        nm = re.search(r"📦\s*(.+)", clean_text)
        if nm:
            en = re.search(r"\(([^)]+)\)", nm.group(1))
            pname = (en.group(1) if en else nm.group(1)).strip()

        # استخراج أسماء المتاجر من النص للتأكد أن لها روابط
        stores = re.findall(r"(?:✅|•)\s*(.+?)\s*—", clean_text)
        for store in stores:
            store = store.strip()
            if store not in urls and pname:
                # توليد رابط بحث جوجل دقيق يوجه للمتجر
                q = quote(f"site:{store}.com OR site:{store}.com.kw {pname}")
                urls[store] = f"https://www.google.com/search?q={q}"

        if key and clean_text and urls: 
            cache_set(key, clean_text, urls)
            
        return clean_text, urls
    except Exception as e:
        print(f"Gemini err {e}")
        return "", {}

def extract_products(text):
    text=re.sub(r'^[•\-\*\d\.\)\s]+','',text,flags=re.M)
    parts=re.split(r'\s*(?:\n+|\+|,|،| و | & )\s*',text.strip())
    parts=[p.strip() for p in parts if len(p.strip())>2]
    return parts[:6] if len(parts)>1 else [text.strip()]

def download_whatsapp_media(mid):
    h={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    meta=requests.get(f"{GRAPH_URL}/{mid}",headers=h,timeout=20).json()
    img=requests.get(meta["url"],headers=h,timeout=30)
    return base64.b64encode(img.content).decode(), meta.get("mime_type","image/jpeg")

def send_whatsapp_text(to,text,bot_id):
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    payload={"messaging_product":"whatsapp","to":to,"type":"text","text":{"body":text[:3900]}}
    try: requests.post(url,json=payload,headers=h,timeout=15)
    except: pass

def send_whatsapp_cta(to,body,link,bot_id,title):
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    payload={"messaging_product":"whatsapp","to":to,"type":"interactive","interactive":{"type":"cta_url","body":{"text":body[:1024]},"action":{"name":"cta_url","parameters":{"display_text":title[:20],"url":link}}}}
    try: requests.post(url,json=payload,headers=h,timeout=15)
    except: pass

@app.get("/webhook")
async def verify(request: Request):
    p=request.query_params
    if p.get("hub.mode")=="subscribe" and p.get("hub.verify_token")==VERIFY_TOKEN:
        return Response(content=p.get("hub.challenge"), media_type="text/plain")
    return Response("fail",403)

@app.post("/webhook")
async def receive(request: Request, background_tasks: BackgroundTasks):
    data=await request.json()
    try:
        value=data["entry"][0]["changes"][0]["value"]
        if "messages" not in value: return {"status":"ok"}
        msg=value["messages"][0]; mid=msg.get("id")
        if mid in processed_ids: return {"status":"dup"}
        processed_ids.append(mid)
        bot_id=value.get("metadata",{}).get("phone_number_id",PHONE_NUMBER_ID)
        from_number=msg["from"]
        
        if msg.get("type")=="image":
            IMAGE_BUFFER[from_number]["images"].append(msg); IMAGE_BUFFER[from_number]["time"]=time.time(); IMAGE_BUFFER[from_number]["bot_id"]=bot_id
            if len(IMAGE_BUFFER[from_number]["images"])==1:
                background_tasks.add_task(process_image_buffer,from_number)
        elif msg.get("type")=="text":
            background_tasks.add_task(process_text_message,msg,bot_id)
    except Exception as e: print(f"webhook err {e}")
    return {"status":"ok"}

async def process_image_buffer(from_number):
    await asyncio.sleep(BUFFER_SECONDS)
    data=IMAGE_BUFFER.pop(from_number,None)
    if not data: return
    if len(data["images"])==1: await asyncio.to_thread(process_single_image,data["images"][0],data["bot_id"])
    else: await asyncio.to_thread(process_multi_images,data["images"],from_number,data["bot_id"])

def process_single_image(message,bot_id):
    from_number=message["from"]
    send_whatsapp_text(from_number,"ثواني بس.. أحدد المنتج وأدور لك الأرخص! 🔎",bot_id)
    b64,mime=download_whatsapp_media(message["image"]["id"])
    txt,urls=call_gemini([{"inline_data":{"mime_type":mime,"data":b64}},{"text":"ما هذا المنتج؟ حدد اسمه الإنجليزي الرسمي ثم ابحث عن سعره الحالي في المتاجر الكويتية"}])
    if not txt: txt="عذراً، لم أتمكن من تحديد المنتج بوضوح."
    send_whatsapp_text(from_number,txt,bot_id)
    for n,u in urls.items():
        if u: send_whatsapp_cta(from_number,f"تسوق من {n} 👇",u,bot_id,f"🛒 {n[:18]}")

def fetch_product_from_image(msg):
    try:
        b64,mime=download_whatsapp_media(msg["image"]["id"])
        txt,urls=call_gemini([{"inline_data":{"mime_type":mime,"data":b64}},{"text":"حدد المنتج باسمه الإنجليزي الرسمي وابحث عن سعره في المتاجر الكويتية"}])
        name_m=re.search(r"📦\s*(.+)",txt); name=(name_m.group(1).strip() if name_m else "منتج غير معروف")[:50]
        pm=re.search(r"✅.*?(?:—|-|–)\s*([\d\.]+)",txt); price=float(pm.group(1)) if pm else 0
        curl=list(urls.values())[0] if urls else ""; cstore=list(urls.keys())[0] if urls else "متجر"
        return {"name":name,"store":cstore,"price":price,"url":curl,"all_urls":urls}
    except: return {"name":"منتج","store":"متجر","price":0,"url":"","all_urls":{}}

def fetch_product_from_text(prod):
    try:
        txt,urls=call_gemini([{"text":f"ابحث عن سعر {prod} في المتاجر الكويتية"}])
        name_m=re.search(r"📦\s*(.+)",txt); name=(name_m.group(1).strip() if name_m else prod)[:50]
        m=re.search(r"✅.*?(?:—|-|–)\s*([\d\.]+)",txt); price=float(m.group(1)) if m else 0
        curl=list(urls.values())[0] if urls else ""; cstore=list(urls.keys())[0] if urls else "متجر"
        return {"name":name,"store":cstore,"price":price,"url":curl,"all_urls":urls}
    except: return {"name":prod,"store":"متجر","price":0,"url":"","all_urls":{}}

def finalize_cart(from_number,bot_id,items):
    total=sum(it["price"] for it in items); cart_id=uuid.uuid4().hex[:8]
    CARTS[cart_id]={"products":items,"total":total}
    summ="\n".join([f"• {it['name']} - {it['price']} د.ك ({it['store']})" for it in items])
    send_whatsapp_text(from_number,f"🛒 سلتك جاهزة:\n{summ}\n\n💰 الإجمالي: {total:.3f} د.ك",bot_id)
    domain=os.environ.get("RAILWAY_PUBLIC_DOMAIN","fanzia.up.railway.app")
    send_whatsapp_cta(from_number,"افتح السلة",f"https://{domain}/cart/{cart_id}",bot_id,"🛒 افتح السلة")

def process_multi_images(messages,from_number,bot_id):
    send_whatsapp_text(from_number,f"تمام لقطت {len(messages)} منتجات، جاري تجهيز السلة...",bot_id)
    items=list(WORKERS.map(fetch_product_from_image,messages)); finalize_cart(from_number,bot_id,items)

def process_text_message(message,bot_id):
    from_number=message["from"]; user_text=message["text"]["body"]; products=extract_products(user_text)
    if len(products)==1:
        send_whatsapp_text(from_number,f"🔍 جاري البحث عن {products[0]}...",bot_id)
        txt,urls=call_gemini([{"text":f"ابحث عن سعر {products[0]} في الكويت"}])
        send_whatsapp_text(from_number,txt or "لم أتمكن من العثور على المنتج في المتاجر.",bot_id)
        for n,u in urls.items():
            if u: send_whatsapp_cta(from_number,f"تسوق من {n} 👇",u,bot_id,f"🛒 {n[:18]}")
    else:
        send_whatsapp_text(from_number,f"تمام لقيت {len(products)} منتجات، جاري تجهيز السلة...",bot_id)
        items=list(WORKERS.map(fetch_product_from_text,products)); finalize_cart(from_number,bot_id,items)

@app.get("/cart/{cart_id}", response_class=HTMLResponse)
async def cart_page(cart_id: str):
    cart=CARTS.get(cart_id)
    if not cart: return HTMLResponse("<h1>السلة غير موجودة أو انتهت صلاحيتها</h1>",404)
    rows="".join([f"<div class='p-4 border-b flex justify-between'><div><b>{it['name']}</b><br><span class='text-sm text-gray-500'>{it['store']} - {it['price']} د.ك</span></div><a href='{it['url']}' target='_blank' class='bg-black text-white px-4 py-2 rounded'>شراء</a></div>" for it in cart["products"]])
    return HTMLResponse(f"<html dir='rtl'><head><meta name='viewport' content='width=device-width'><title>سلة المشتريات</title><script src='https://cdn.tailwindcss.com'></script></head><body class='bg-gray-100'><div class='max-w-lg mx-auto bg-white min-h-screen'><div class='p-5 bg-black text-white text-center text-xl font-bold'>🛒 سلة المشتريات</div>{rows}<div class='p-5 text-left text-lg font-bold'>الإجمالي: {cart['total']} د.ك</div></div></body></html>")

@app.get("/")
async def health(): return {"status":"v13 Advanced Gemini Search"}
