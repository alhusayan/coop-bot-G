from fastapi import FastAPI, Request, Response
import google.generativeai as genai
import requests
import os

app = FastAPI()

# إعداد مفاتيح التشغيل الخاصة بك
GEMINI_API_KEY = "AQ.Ab8RN6Lv7pFuQMjc3WDieObUmzB7HF9X2tcANBjOG_hYV6LazA"
WHATSAPP_TOKEN = "EAATIdbdihPsBRZCfZA03MpgfqVLYErTjew54aAJTVeZC53v70EU70jYeqRu1d9P33MkuNlbc8fC9ed9CR9YJPiPcV6jTa3980wYbTuQzaEvSaHC4Ye9ZCZBZCZAy0OZCzDzC1OmmbGozrxTvwAG6npuJtVj6G2WeFP6jlOjAobMq1ROnhQb2ZAZBStSQRIwfPBKxTPtQDNZCC1wujxyBeoTz1r5QlZBknMxeqmnhkx4qZAcV5lhAxx3Q29Gv86wEMnBG3yKtX3f92YnoZBmWKD2xQAqSBrbgZDZD"
PHONE_NUMBER_ID = "1228772913651661"
VERIFY_TOKEN = "MY_SECRET_COOP_BOT_TOKEN"

genai.configure(api_key=GEMINI_API_KEY)

@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=403)

@app.post("/webhook")
async def receive_whatsapp_message(request: Request):
    data = await request.json()
    
    try:
        if 'entry' in data and data['entry']:
            changes = data['entry'][0].get('changes', [])
            if changes and 'value' in changes[0]:
                value = changes[0]['value']
                if 'messages' in value:
                    message = value['messages'][0]
                    from_number = message['from']
                    
                    # إذا أرسل المستخدم صورة
                    if message['type'] == 'image':
                        image_id = message['image']['id']
                        
                        # 1. جلب معلومات الميديا والرابط الفعلي من فيسبوك
                        media_res = requests.get(
                            f"https://graph.facebook.com/v20.0/{image_id}",
                            headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
                        ).json()
                        
                        image_url = media_res.get('url')
                        
                        if image_url:
                            # 2. تحميل ملف الصورة الفعلي وحفظه مؤقتاً
                            img_data = requests.get(
                                image_url, 
                                headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
                            ).content
                            
                            with open("temp_prod.jpg", "wb") as f:
                                f.write(img_data)
                            
                            # 3. إرسال الصورة لي مع تفعيل البحث الحي عن أسعار الكويت
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
                            
                            # 4. إرسال الرد النهائي للمستخدم
                            send_whatsapp_text(from_number, reply_text)
                        else:
                            send_whatsapp_text(from_number, "عذراً، لم أتمكن من معالجة الصورة حالياً. جرب إرسالها مرة أخرى!")
                            
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
