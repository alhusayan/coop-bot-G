import os, re, requests, base64
from flask import Flask, request

app = Flask(__name__)

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "offer-u-verify")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GRAPH_URL = "https://graph.facebook.com/v25.0"

PENDING_IG = {} # يحفظ اسم المنتج لما يضغط زر انستغرام

# ---------- GEMINI WITH GOOGLE SEARCH ----------
def call_gemini(parts, system=""):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": parts}],
        "tools": [{"google_search": {}}] # هذا اللي يخليه يجيب روابط انستغرام حقيقية مثل Meta AI
    }
    r = requests.post(url, json=payload, timeout=30)
    data = r.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except:
        print(data)
        return "ما لقيت عروض حاليا", {}

    # نستخرج الروابط اللي على شكل LINKS: اسم=رابط
    urls = {}
    m = re.search(r"LINKS:(.*)", text, re.DOTALL | re.IGNORECASE)
    if m:
        links_part = m.group(1)
        for line in re.findall(r"([^=\n]+)=([^\s,]+)", links_part):
            name = line[0].strip()[:30]
            link = line[1].strip()
            if not link.startswith("http"): link = "https://" + link
            urls[name] = link
        # نشيل سطر LINKS من النص
        text = text.split("LINKS:")[0].strip()

    # لو ما كتب LINKS بس حاط روابط داخل النص
    if not urls:
        for u in re.findall(r"https?://(?:www\.)?instagram\.com/[^\s]+", text):
            urls[u.split("/")[-2][:20]] = u

    return text, urls

def extract_product_from_image(image_bytes):
    b64 = base64.b64encode(image_bytes).decode()
    system = "استخرج اسم المنتج الكامل والماركة والموديل من الصورة. رجع فقط اسم المنتج."
    parts = [{"inline_data": {"mime_type": "image/jpeg", "data": b64}}, {"text": "ما هذا المنتج؟"}]
    txt, _ = call_gemini(parts, system)
    return txt.strip()

def search_all_offers(product):
    system = "انت خبير تسعير في الكويت. ابحث عن 5 عروض لنفس المنتج في مواقع كويتية. اذكر السعر بالدينار. بالاخير LINKS: اسم المتجر=الرابط"
    return call_gemini([{"text": f"{product} سعر الكويت"}], system=system)

# هذه الدالة الجديدة اللي تبحث في كل انستغرام - مو متاجر محددة
def search_instagram_offers(product):
    system = """
    انت باحث عروض انستغرام في الكويت.
    ابحث عن 5 عروض انستغرام حقيقية لنفس اسم المنتج المطلوب فقط، اي منتج كان (مزيل عرق، ساعة، جوتي).
    لا تحصر البحث في Xcite او Eureka.
    الصيغة المطلوبة:
    📸 اسم المحل - الموديل ب السعر د.ك
    ثم سطر اخير الزامي: LINKS: اسم المحل=instagram.com/p/xxxx
    """
    return call_gemini([{"text": f"{product} عروض انستغرام الكويت site:instagram.com"}], system=system)

# ---------- WHATSAPP SEND ----------
def send_whatsapp_text(to, body, bot_id):
    url = f"{GRAPH_URL}/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    data = {"messaging_product": "whatsapp", "to": to, "text": {"body": body[:3500]}}
    requests.post(url, json=data, headers=headers)

def send_whatsapp_cta(to, body, link, bot_id, btn_text):
    url = f"{GRAPH_URL}/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    data = {
        "messaging_product": "whatsapp", "to": to,
        "interactive": {
            "type": "cta_url",
            "body": {"text": body[:500]},
            "action": {"name": "cta_url", "parameters": {"display_text": btn_text, "url": link}}
        }
    }
    requests.post(url, json=data, headers=headers)

def send_whatsapp_buttons(to, body, buttons, bot_id):
    url = f"{GRAPH_URL}/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    btns = [{"type": "reply", "reply": {"id": b[0], "title": b[1]}} for b in buttons]
    data = {"messaging_product": "whatsapp", "to": to, "type": "interactive",
            "interactive": {"type": "button", "body": {"text": body}, "action": {"buttons": btns}}}
    requests.post(url, json=data, headers=headers)

# ---------- WEBHOOK ----------
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "verify failed", 403

    data = request.json
    try:
        msg = data["entry"][0]["changes"][0]["value"]["messages"][0]
        from_number = msg["from"]
        bot_id = data["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"]

        if msg.get("type") == "image":
            img_id = msg["image"]["id"]
            # تحميل الصورة
            meta = requests.get(f"{GRAPH_URL}/{img_id}", headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}).json()
            img_url = meta.get("url")
            img_bytes = requests.get(img_url, headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}).content

            send_whatsapp_text(from_number, "📸 استلمت الصورة، قاعد أحدد المنتج...", bot_id)
            product = extract_product_from_image(img_bytes)
            PENDING_IG[from_number] = product

            txt, urls = search_all_offers(product)
            send_whatsapp_text(from_number, txt, bot_id)
            for name, link in urls.items():
                if link: send_whatsapp_cta(from_number, f"عرض {name}", link, bot_id, f"🛒 {name[:18]}")

            send_whatsapp_buttons(from_number, f"تبي أدور لك إعلانات نفس المنتج في انستغرام؟\n{product}",
                                  [("ig_yes_"+product[:20], "إيه دور 📸"), ("ig_no", "لا شكرا")], bot_id)

        elif msg.get("type") == "interactive":
            process_interactive(msg, bot_id)

    except Exception as e:
        print("ERR", e)
    return "ok", 200

def process_interactive(message, bot_id):
    from_number = message["from"]
    bid = message["interactive"].get("button_reply",{}).get("id","")
    if bid.startswith("ig_yes"):
        product = PENDING_IG.get(from_number, bid.replace("ig_yes_", ""))
        send_whatsapp_text(from_number, f"🔍 أدور لك عروض انستغرام لـ {product} (نفس طريقة Meta AI)...", bot_id)
        txt, urls = search_instagram_offers(product)
        if urls:
            send_whatsapp_text(from_number, txt, bot_id)
            for name, link in urls.items():
                send_whatsapp_cta(from_number, f"شوف عرض {name} 👇", link, bot_id, f"📸 {name[:18]}")
        else:
            send_whatsapp_text(from_number, txt, bot_id)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
