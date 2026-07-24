# -*- coding: utf-8 -*-
import os, re, time, base64, requests, uuid, asyncio
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import HTMLResponse

app = FastAPI()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_COOP_BOT_TOKEN")

# الجديد
FB_IG_TOKEN = os.environ.get("FB_IG_TOKEN", "") # توكن الانستغرام الجديد
IG_USER_ID = os.environ.get("IG_USER_ID", "") # 1784xxxx

GRAPH_URL = "https://graph.facebook.com/v25.0" # حدثناه نفس اللي عندك
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

processed_ids = deque(maxlen=1000)
CARTS = {}
IMAGE_BUFFER = defaultdict(lambda: {"images": [], "time": 0, "bot_id": ""})
PENDING_IG = {}
BUFFER_SECONDS = 4
RESOLVER = ThreadPoolExecutor(max_workers=6)
WORKERS = ThreadPoolExecutor(max_workers=3)
HEADERS = {"User-Agent": "Mozilla/5.0"}

SYSTEM_PROMPT = """
أنت مساعد تسوق كويتي. رد بهذا الشكل فقط:
📦 [اسم المنتج]
✅ [المتجر الأرخص] — [السعر] د.ك
- [المتجر الثاني] — [السعر] د.ك
- [المتجر الثالث] — [السعر] د.ك
ثم سطر أخير إلزامي:
LINKS: اسم المتجر الأول=دومينه, اسم المتجر الثاني=دومينه, اسم المتجر الثالث=دومينه
مثال: LINKS: إكسايت=xcite.com, بلينك=blink.com.kw, يوريكا=eureka.com.kw
ممنوع روابط ظاهرة. ممنوع Markdown.
"""

def get_final_url(url: str):
    try:
        r = requests.head(url, allow_redirects=True, timeout=8, headers=HEADERS)
        if r.status_code == 405:
            r = requests.get(url, allow_redirects=True, timeout=8, stream=True, headers=HEADERS); r.close()
        final = r.url
        if "vertexaisearch" in final or "grounding-api-redirect" in final: return ""
        return final if len(final) < 700 else ""
    except: return ""

def resolve_all(uris): return list(RESOLVER.map(get_final_url, uris))
def domain_key(dom): return dom.replace("www.","").split(".")[0]

def call_gemini(parts, system=SYSTEM_PROMPT):
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": parts}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2000},
    }
    try:
        r = requests.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload, timeout=90)
        if r.status_code >= 400: return "", {}
        data = r.json(); cand = data["candidates"][0]
        text = "".join(p.get("text","") for p in cand["content"]["parts"]).strip()
        pairs=[]
        m=re.search(r"LINKS:\s*(.+)", text, re.I)
        if m:
            raw=m.group(1)
            for part in re.split(r"[,،]+", raw):
                part=part.strip()
                if "=" in part:
                    name,dom=part.split("=",1); name,dom=name.strip(),dom.strip().lower()
                    if "." in dom: pairs.append((name,dom))
            text=re.sub(r"\n?LINKS:.*","",text,flags=re.I).strip()
        text=re.sub(r"https?://\S+","",text).replace("**","").strip()
        urls_map={}; chunks=cand.get("groundingMetadata",{}).get("groundingChunks",[])
        uris=[c.get("web",{}).get("uri") for c in chunks if c.get("web",{}).get("uri")]
        if uris and pairs:
            finals=resolve_all(uris[:8])
            for name,dom in pairs:
                key=domain_key(dom)
                for f in finals:
                    if f and key in f.lower(): urls_map[name]=f; break
        return text, dict(list(urls_map.items())[:3])
    except Exception as e:
        print(f"Gemini err {e}"); return "", {}

# ===== الجديد: بحث انستغرام عن طريق Meta API الحقيقي =====
def search_instagram_via_meta(product: str):
    if not FB_IG_TOKEN or not IG_USER_ID:
        return None, {}
    headers = {"Authorization": f"Bearer {FB_IG_TOKEN}"}

    # حسابات متاجر الكويت الحقيقية على انستغرام
    STORES = ["xcitealghanim", "eureka.kw", "blink.com.kw", "bestalkw", "luluhyperkw"]

    found_urls = {}
    try:
        for username in STORES[:4]: # نبحث في 4 متاجر عشان ما نبطئ
            url = f"{GRAPH_URL}/{IG_USER_ID}"
            params = {
                "fields": f"business_discovery.username({username}){{media{{caption,permalink,like_count,timestamp}} }}",
            }
            r = requests.get(url, params=params, headers=headers, timeout=15)
            if r.status_code!= 200:
                print(f"{username} err {r.text[:200]}")
                continue

            media = r.json().get("business_discovery", {}).get("media", {}).get("data", [])
            for m in media:
                cap = (m.get("caption") or "").lower()
                # اذا اسم المنتج موجود في كابشن البوست
                if product.split()[0].lower() in cap or product.split()[-1].lower() in cap:
                    title = f"{username} - {cap[:25]}"
                    found_urls[title] = m.get("permalink")
                    if len(found_urls) >= 3:
                        break
            if len(found_urls) >= 3:
                break

        if found_urls:
            txt = f"📸 عروض انستغرام لنفس المنتج {product} من متاجر الكويت:\n"
            return txt, found_urls
        else:
            return f"دورت في {', '.join(STORES)} وما لقيت {product} بالضبط، بس تقدر تشوف حساباتهم", {}

    except Exception as e:
        print(f"IG discovery err {e}")
        return None, {}

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

def send_instagram_choice(to,bot_id,product):
    PENDING_IG[to]=product
    url=f"{GRAPH_URL}/{bot_id}/messages"; h={"Authorization":f"Bearer {WHATSAPP_TOKEN}","Content-Type":"application/json"}
    payload={
        "messaging_product":"whatsapp","to":to,"type":"interactive",
        "interactive":{
            "type":"button",
            "body":{"text":f"تبي أدور لك إعلانات نفس المنتج في انستغرام؟\n{product}"},
            "action":{"buttons":[
                {"type":"reply","reply":{"id":f"ig_yes:{product[:20]}","title":"📸 إيه دور"}},
                {"type":"reply","reply":{"id":"ig_no","title":"لا شكرا"}}
            ]}
        }
    }
    requests.post(url,json=payload,headers=h,timeout=15)

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
        elif msg.get("type")=="interactive":
            background_tasks.add_task(process_interactive,msg,bot_id)
        else:
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
    send_whatsapp_text(from_number,"ثواني بس.. أحدد المنتج وأدور لك الأرخص!",bot_id)
    b64,mime=download_whatsapp_media(message["image"]["id"])
    txt,urls=call_gemini([{"inline_data":{"mime_type":mime,"data":b64}},{"text":"ما هذا المنتج؟ ابحث عن سعره الحالي في الكويت"}])
    if not txt: txt="ما قدرت أحدد المنتج"
    send_whatsapp_text(from_number,txt,bot_id)
    for n,u in urls.items():
        if u: send_whatsapp_cta(from_number,f"تسوق من {n} 👇",u,bot_id,f"🛒 {n[:18]}")
    m=re.search(r"📦\s*(.+)",txt); pname=(m.group(1).strip() if m else "المنتج")[:30]
    send_instagram_choice(from_number,bot_id,pname)

def process_interactive(message,bot_id):
    from_number=message["from"]
    bid=message["interactive"].get("button_reply",{}).get("id","")
    if bid.startswith("ig_yes"):
        product=PENDING_IG.get(from_number,"المنتج")
        send_whatsapp_text(from_number,f"🔍 أدور لك إعلانات انستغرام لـ {product} عن طريق Meta API...",bot_id)
        txt,urls=search_instagram_via_meta(product)
        if urls:
            send_whatsapp_text(from_number,txt,bot_id)
            for n,u in urls.items():
                send_whatsapp_cta(from_number,f"شوف عرض {n} 👇",u,bot_id,f"📸 {n[:18]}")
        else:
            send_whatsapp_text(from_number,txt or f"ما لقيت عروض انستغرام لـ {product} حالياً",bot_id)

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

def process_multi_images(messages,from_number,bot_id):
    send_whatsapp_text(from_number,f"تمام لقطت {len(messages)} منتجات، أسوي سلة...",bot_id)
    items=list(WORKERS.map(fetch_product_from_image,messages)); finalize_cart(from_number,bot_id,items)

def process_text_message(message,bot_id):
    from_number=message["from"]; user_text=message["text"]["body"]; products=extract_products(user_text)
    if len(products)==1:
        send_whatsapp_text(from_number,f"🔍 أدور لك على {products[0]}...",bot_id)
        txt,urls=call_gemini([{"text":f"ابحث عن سعر {products[0]} في الكويت"}])
        send_whatsapp_text(from_number,txt or "ما لقيت",bot_id)
        for n,u in urls.items():
            if u: send_whatsapp_cta(from_number,f"تسوق من {n} 👇",u,bot_id,f"🛒 {n[:18]}")
        send_instagram_choice(from_number,bot_id,products[0])
    else:
        send_whatsapp_text(from_number,f"تمام لقيت {len(products)} منتجات، أسوي سلة...",bot_id)
        items=list(WORKERS.map(fetch_product_from_text,products)); finalize_cart(from_number,bot_id,items)

@app.get("/cart/{cart_id}", response_class=HTMLResponse)
async def cart_page(cart_id: str):
    cart=CARTS.get(cart_id)
    if not cart: return HTMLResponse("<h1>السلة انتهت</h1>",404)
    rows="".join([f"<div class='p-4 border-b flex justify-between'><div><b>{it['name']}</b><br><span class='text-sm text-gray-500'>{it['store']} - {it['price']} د.ك</span></div><a href='{it['url']}' target='_blank' class='bg-black text-white px-4 py-2 rounded'>شراء</a></div>" for it in cart["products"]])
    return HTMLResponse(f"<html dir='rtl'><head><meta name='viewport' content='width=device-width'><script src='https://cdn.tailwindcss.com'></script></head><body><div class='max-w-lg mx-auto bg-white'><div class='p-5 bg-black text-white'><h1>🛒 سلتك</h1></div>{rows}</div></body></html>")

@app.get("/")
async def health(): return {"status":"v9 IG via Meta Hashtag API - Ready"}
