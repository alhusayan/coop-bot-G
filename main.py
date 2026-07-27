# -*- coding: utf-8 -*-
import os, re, time, base64, requests, uuid, asyncio, urllib.parse
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import HTMLResponse

app = FastAPI()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_COOP_BOT_TOKEN")

GRAPH_URL = "https://graph.facebook.com/v20.0"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

processed_ids = deque(maxlen=1000)
CARTS = {}
IMAGE_BUFFER = defaultdict(lambda: {"images": [], "time": 0, "bot_id": ""})
LAST_SEARCH = {}

BUFFER_SECONDS = 4
RESOLVER = ThreadPoolExecutor(max_workers=8)
WORKERS = ThreadPoolExecutor(max_workers=3)
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

SYSTEM_PROMPT = """
أنت مساعد تسوق كويتي محترف. وظيفتك الوحيدة هي إيجاد أرخص سعر للمنتج في الكويت.

قواعد صارمة جداً لا تخرج عنها:
1. الرد يكون دائماً بهذا الشكل الحرفي فقط:
📦 [اسم المنتج الكامل الواضح]
✅ [اسم المتجر الأرخص] — [السعر] د.ك
- [المتجر الثاني] — [السعر] د.ك
- [المتجر الثالث] — [السعر] د.ك

2. في السطر الأخير فقط، يجب أن تكتب سطر الروابط بهذا الشكل الحرفي بدون أي https:
LINKS: اسم المتجر الأول=domain.com, اسم المتجر الثاني=domain.com, اسم المتجر الثالث=domain.com
مثال: LINKS: اكسايت=xcite.com, بلينك=blink.com.kw, يوريكا=eureka.com.kw

3. ممنوع تضع أي رابط كامل https:// في الرد. فقط الدومين في سطر LINKS.
4. ممنوع Markdown مثل **.
5. استثناء وحيد: اذا كان المنتج عقار حقيقي او سيارة حقيقية فقط، رد بتقييم متوسط ونطاق سعري مختصر جداً وبدون سطر LINKS.
"""

def get_final_url(url: str):
    if not url: return ""
    try:
        try:
            r = requests.head(url, allow_redirects=True, timeout=10, headers=HEADERS)
            if r.status_code in [405, 403, 999] or not r.url:
                raise Exception("need GET")
            final = r.url
        except:
            r = requests.get(url, allow_redirects=True, timeout=10, headers=HEADERS, stream=True)
            final = r.url
            r.close()

        if "vertexaisearch" in final or "grounding-api-redirect" in final: return url
        return final if len(final) < 700 else url
    except: return url

def resolve_all(uris): return list(RESOLVER.map(get_final_url, uris))
def domain_key(dom): return dom.replace("www.","").split(".")[0].split("/")[0]

def call_gemini(parts, system=SYSTEM_PROMPT, use_search=True):
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2000},
    }
    if use_search:
        payload["tools"] = [{"google_search": {}}]

    try:
        r = requests.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload, timeout=90)
        if r.status_code >= 400:
            print(f"Gemini HTTP {r.status_code}: {r.text[:500]}")
            return "", {}
        data = r.json()
        cand = data["candidates"][0]
        text = "".join(p.get("text","") for p in cand["content"]["parts"]).strip()

        pairs=[]
        m = re.search(r"(?:LINKS|الروابط)\s*[:=]\s*(.+)", text, re.I | re.S)
        if m:
            raw = m.group(1).split("\n")[0]
            for part in re.split(r'[,،;]+', raw):
                part=part.strip()
                if "=" in part:
                    name,dom = part.split("=",1)
                    name,dom = name.strip(), dom.strip().lower().replace("https://","").replace("http://","").split("/")[0]
                    if "." in dom and len(dom) > 3:
                        pairs.append((name,dom))
            text = re.sub(r"\n?LINKS:.*", "", text, flags=re.I).strip()
            text = re.sub(r"\n?الروابط:.*", "", text, flags=re.I).strip()

        text = re.sub(r"https?://\S+","",text).replace("**","").strip()

        urls_map={}
        if use_search and pairs:
            chunks = cand.get("groundingMetadata",{}).get("groundingChunks",[])
            uris = [c.get("web",{}).get("uri") for c in chunks if c.get("web",{}).get("uri")]
            if uris:
                finals = resolve_all(uris[:10])
                for name,dom in pairs:
                    key = domain_key(dom)
                    for f in finals:
                        if f and key in f.lower():
                            urls_map[name]=f
                            break
                    if name not in urls_map:
                        urls_map[name] = f"https://{dom}"

        return text, dict(list(urls_map.items())[:3])
    except Exception as e:
        print(f"Gemini err {e}"); return "", {}

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
        elif msg.get("type")=="location":
            background_tasks.add_task(process_location_message,msg,bot_id)

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
    send_whatsapp_text(from_number,"ثواني بس.. أحدد المنتج وأدور لك الأرخص!",bot_id)
    b64,mime=download_whatsapp_media(message["image"]["id"])
    txt,urls=call_gemini([{"inline_data":{"mime_type":mime,"data":b64}},{"text":"ما هذا المنتج؟ ابحث عن سعره الحالي في الكويت"}])
    if not txt: txt="ما قدرت أحدد المنتج"
    send_whatsapp_text(from_number,txt,bot_id)

    name_m = re.search(r"📦\s*(.+)", txt)
    product_name = name_m.group(1).strip() if name_m else "المنتج"
    LAST_SEARCH[from_number] = {"product": product_name}

    for n,u in urls.items():
        if u: send_whatsapp_cta(from_number,f"تسوق من {n} 👇",u,bot_id,f"🛒 {n[:18]}")

    send_whatsapp_text(from_number, "📍 تبي تشتري المنتج من مكان قريب منك؟ دز لي موقعك (Location) بالواتساب الحين وأطلع لك أقرب مكان يبيعه بالخريطة!", bot_id)

def fetch_product_from_image(msg):
    try:
        b64,mime=download_whatsapp_media(msg["image"]["id"])
        txt,urls=call_gemini([{"inline_data":{"mime_type":mime,"data":b64}},{"text":"حدد المنتج وابحث عن سعره"}])
        name_m=re.search(r"📦\s*(.+)",txt); name=(name_m.group(1).strip() if name_m else "منتج")[:50]
        pm=re.search(r"✅.*?(?:—|-|–)\s*([\d\.]+)",txt); price=float(pm.group(1)) if pm else 0
        curl=list(urls.values())[0] if urls else ""; cstore=list(urls.keys())[0] if urls else "متجر"
        return {"name":name,"store":cstore,"price":price,"url":curl,"all_urls":urls}
    except: return {"name":"منتج","store":"متجر","price":0,"url":"","all_urls":{}}

def fetch_product_from_text(prod):
    try:
        txt,urls=call_gemini([{"text":f"ابحث عن سعر {prod} في الكويت"}])
        m=re.search(r"✅.*?(?:—|-|–)\s*([\d\.]+)",txt); price=float(m.group(1)) if m else 0
        curl=list(urls.values())[0] if urls else ""; cstore=list(urls.keys())[0] if urls else "متجر"
        return {"name":prod,"store":cstore,"price":price,"url":curl,"all_urls":urls}
    except: return {"name":prod,"store":"متجر","price":0,"url":"","all_urls":{}}

def finalize_cart(from_number,bot_id,items):
    total=sum(it["price"] for it in items); cart_id=uuid.uuid4().hex[:8]
    CARTS[cart_id]={"products":items,"total":total}
    summ="\n".join([f"• {it['name']} - {it['price']} د.ك ({it['store']})" for it in items])
    send_whatsapp_text(from_number,f"🛒 سلتك جاهزة:\n{summ}\n\n💰 الإجمالي: {total:.3f} د.ك",bot_id)
    domain=os.environ.get("RAILWAY_PUBLIC_DOMAIN","fanzia.up.railway.app")
    send_whatsapp_cta(from_number,"افتح السلة",f"https://{domain}/cart/{cart_id}",bot_id,"🛒 افتح السلة")
    send_whatsapp_text(from_number, "📍 تبي أقرب محل يبيع منتجات سلتك؟ دز موقعك الحين!", bot_id)

def process_multi_images(messages,from_number,bot_id):
    send_whatsapp_text(from_number,f"تمام لقطت {len(messages)} منتجات، أسوي سلة...",bot_id)
    items=list(WORKERS.map(fetch_product_from_image,messages)); finalize_cart(from_number,bot_id,items)

def process_text_message(message,bot_id):
    from_number=message["from"]; user_text=message["text"]["body"]; products=extract_products(user_text)
    if len(products)==1:
        send_whatsapp_text(from_number,f"🔍 أدور لك على {products[0]}...",bot_id)
        txt,urls=call_gemini([{"text":f"ابحث عن سعر {products[0]} في الكويت"}])
        send_whatsapp_text(from_number,txt or "ما لقيت",bot_id)
        LAST_SEARCH[from_number] = {"product": products[0]}
        for n,u in urls.items():
            if u: send_whatsapp_cta(from_number,f"تسوق من {n} 👇",u,bot_id,f"🛒 {n[:18]}")
        send_whatsapp_text(from_number, "📍 تبي تشتري المنتج من مكان قريب منك؟ دز لي موقعك (Location) بالواتساب الحين وأطلع لك أقرب مكان يبيعه بالخريطة!", bot_id)
    else:
        LAST_SEARCH[from_number] = {"product": products[0]}
        send_whatsapp_text(from_number,f"تمام لقيت {len(products)} منتجات، أسوي سلة...",bot_id)
        items=list(WORKERS.map(fetch_product_from_text,products)); finalize_cart(from_number,bot_id,items)

def process_location_message(message, bot_id):
    from_number = message["from"]
    lat = message["location"]["latitude"]
    lng = message["location"]["longitude"]
    last_search = LAST_SEARCH.get(from_number)
    if not last_search or not last_search.get("product"):
        send_whatsapp_text(from_number, "ما عندي منتج محفوظ حالياً 😅. ابحث عن منتج أول، وبعدها دز موقعك عشان أدلك على أقرب مكان يبيعه!", bot_id)
        return
    product = last_search["product"]
    prompt_category = """أنت خبير خرائط في الكويت. اعطني عبارة بحث واحدة فقط لخرائط جوجل.
- للإلكترونيات: Xcite OR Eureka OR Best
- للصيدليات: Pharmacy صيدلية
- للسوبرماركت: Cooperative Supermarket جمعية
- للرياضة: Intersport OR Go Sport
- للباقي: اسم المنتج نفسه
عبارة البحث فقط بدون شرح."""
    category_text, _ = call_gemini([{"text": f"المنتج: {product}"}], system=prompt_category, use_search=False)
    category = category_text.strip().split("\n")[0] if category_text else product
    safe_category = urllib.parse.quote(category)
    maps_url = f"https://www.google.com/maps/search/{safe_category}/@{lat},{lng},15z"
    body = f"📍 بحثك الأخير كان عن ({product})\n\nجهزت لك أقرب المحلات اللي تبيعه حولك، اضغط الزر وافتح الخريطة 👇"
    send_whatsapp_cta(from_number, body, maps_url, bot_id, "📍 افتح الخريطة")

@app.get("/cart/{cart_id}", response_class=HTMLResponse)
async def cart_page(cart_id: str):
    cart=CARTS.get(cart_id)
    if not cart: return HTMLResponse("<h1>السلة انتهت</h1>",404)
    rows="".join([f"<div class='p-4 border-b flex justify-between'><div><b>{it['name']}</b><br><span class='text-sm text-gray-500'>{it['store']} - {it['price']} د.ك</span></div><a href='{it['url']}' target='_blank' class='bg-black text-white px-4 py-2 rounded'>شراء</a></div>" for it in cart["products"]])
    return HTMLResponse(f"<html dir='rtl'><head><meta name='viewport' content='width=device-width'><script src='https://cdn.tailwindcss.com'></script></head><body><div class='max-w-lg mx-auto bg-white'><div class='p-5 bg-black text-white'><h1>🛒 سلتك</h1></div>{rows}</div></body></html>")

@app.get("/")
async def health(): return {"status":"v12 fixed links & map CTA"}
