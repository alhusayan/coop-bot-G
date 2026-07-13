from fastapi import FastAPI, Request, Response
import google.generativeai as genai
import requests
import os

app = FastAPI()

# إعداد مفاتيح التشغيل (يفضل وضعها في أرقام البيئة بـ Railway لاحقاً)
GEMINI_API_KEY = "ضع_هنا_مفتاح_جيميني_الخاص_بك"
WHATSAPP_TOKEN = "EAATIdbdhPsBR9pvRn9o1IBDTP3yrLaREQTfGmZaFa4OC6E6ZC1JaC0udX1Hobs83IHXw1wlU0EugfH72fBMVZB6ATi05yvCrL9Rb2omEmJwXW574zqu4xqzg787W9QngFZAYbYY9EpHIeWYJuaubLHyatZCzMh802Jt" # التوكن الظاهر بصورتك
PHONE_NUMBER_ID = "1228772913651661" # المعرف الظاهر بصورتك
VERIFY_TOKEN = "MY_SECRET_COOP_BOT_TOKEN" # كلمة سر من اختيارك لتأكيد الربط مع فيسبوك

genai.configure(api_key=GEMINI_API_KEY)

# 1. كود التحقق الأول لربط الـ Webhook مع Meta
@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=403)

# 2. كود استقبال الرسائل والصور من المستخدمين
@app.post("/webhook")
async def receive_whatsapp_message(request: Request):
    data = await request.json()
    
    try:
        # التأكد من أن الرسالة تحتوي على ميديا (صورة)
        entry = data['entry'][0]['changes'][0]['value']
        if 'messages' in entry:
            message = entry['messages'][0]
            from_number = message['from']
            
            if message['type'] == 'image':
                image_id = message['image']['id']
                
                # أ: جلب رابط تحميل الصورة من سيرفرات فيسبوك
                media_url_res = requests.get(
                    f"https://graph.facebook.com/v20.0/{image_id}",
                    headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
                ).json()
                
                image_url = media_url_res.get('url')
                
                # ب: تحميل الصورة مؤقتاً بالسيرفر
                img_data = requests.get(image_url, headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}).content
                with open("temp_prod.jpg", "wb") as f:
                    f.write(img_data)
                
                # ج: إرسال الصورة لي مع تفعيل البحث الحي عن أسعار الكويت
                uploaded_file = genai.upload_file(path="temp_prod.jpg")
                model = genai.GenerativeModel(
                    model_name="gemini-1.5-flash",
                    tools=[{"google_search": {}}]
                )
                
                prompt = """
                تعرف على هذا المنتج المتوفر في السوق الكويتي من الصورة.
                قم بعمل بحث فوري وحي (Live Web Search) على الإنترنت لمعرفة أسعاره الحالية في الجمعيات التعاونية والمنصات الإلكترونية داخل دولة الكويت (مثل لولو، سيتي هايبر، كارفور، جمعية دوت كوم، توصيل).
                رتب الأسعار في جدول واضح واذكر الروابط إن وجدت.
                اجعل الأسلوب كويتي سريع ومناسب لمحادثة واتساب.
                """
                
                response = model.generate_content([uploaded_file, prompt])
                reply_text = response.text
                
                # د: إرسال الرد النهائي للمستخدم على الواتساب
                send_whatsapp_text(from_number, reply_text)
                
    except Exception as e:
        print(f"Error processing message: {e}")
        
    return {"status": "success"}

def send_whatsapp_text(to_number, text):
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text}
    }
    requests.post(url, json=payload, headers=headers)
