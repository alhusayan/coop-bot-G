# -*- coding: utf-8 -*-
"""
بوت واتساب — بحث حي فوري عن أسعار المنتجات في الكويت + قاعدة عروض الجمعيات اليومية
WhatsApp Cloud API (Meta) + FastAPI + Gemini API (Google Search Grounding)
تحديث العروض: جلسة Meta AI يومية → رسالة "تحديث_عروض:" من رقم الأدمن → تُحقن في كل استعلام
Deploy: Railway
"""

import os
import re
import csv
import io
import time
import base64
import sqlite3
import requests
from datetime import datetime, timedelta
from collections import deque
from fastapi import FastAPI, Request, Response, BackgroundTasks

app = FastAPI()

# ========= مفاتيح التشغيل (تنحط في Railway → Variables، مو هنا) =========
GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL    = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
WHATSAPP_TOKEN  = os.environ.get("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "")
VERIFY_TOKEN    = os.environ.get("VERIFY_TOKEN", "MY_SECRET_COOP_BOT_TOKEN")
ADMIN_PHONE     = os.environ.get("ADMIN_PHONE", "")  # رقمك بصيغة دولية بدون + مثل 965XXXXXXXX

GRAPH_URL  = "https://graph.facebook.com/v20.0"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# منع الرد المكرر
processed_ids = deque(maxlen=500)

# ========= قاعدة عروض الجمعيات (SQLite) =========
DB_PATH = "offers.db"


def init_offers_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS offers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coop TEXT, product TEXT, old_price TEXT, new_price TEXT,
        expires TEXT, added_at TEXT)""")
    con.commit()
    con.close()


init_offers_db()


def purge_expired():
    """تنظيف تلقائي: عرض له تاريخ انتهاء مضى، أو بلا تاريخ وعمره تجاوز 4 أيام"""
    today = datetime.now().strftime("%Y-%m-%d")
    limit = (datetime.now() - timedelta(days=4)).isoformat()
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM offers WHERE (expires != '' AND expires < ?) OR (expires = '' AND added_at < ?)",
                (today, limit))
    con.commit()
    con.close()


def normalize_date(s: str) -> str:
    """يحاول توحيد التاريخ إلى YYYY-MM-DD، وإلا يرجعه كما هو"""
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s


def store_offers_csv(csv_text: str) -> int:
    """يخزن سطور CSV القادمة من جلسة Meta AI. يرجع عدد العروض المضافة"""
    added = 0
    now = datetime.now().isoformat()
    con = sqlite3.connect(DB_PATH)
    reader = csv.reader(io.StringIO(csv_text.strip()))
    for row in reader:
        if len(row) < 4:
            continue
        coop, product = row[0].strip(), row[1].strip()
        # تخطي سطر العناوين إن وُجد
        if coop in ("الجمعية", "الجمعيه") or not product:
            continue
        old_p = row[2].strip() if len(row) > 2 else ""
        new_p = row[3].strip() if len(row) > 3 else ""
        expires = normalize_date(row[4]) if len(row) > 4 else ""
        # منع التكرار: نفس الجمعية + المنتج + السعر الجديد
        cur = con.execute("SELECT 1 FROM offers WHERE coop=? AND product=? AND new_price=?",
                          (coop, product, new_p))
        if cur.fetchone():
            continue
        con.execute("INSERT INTO offers (coop, product, old_price, new_price, expires, added_at) VALUES (?,?,?,?,?,?)",
                    (coop, product, old_p, new_p, expires, now))
        added += 1
    con.commit()
    con.close()
    return added


def active_offers_context(max_rows: int = 120) -> str:
    """يرجع العروض السارية كنص سياق يُحقن في استعلام Gemini"""
    purge_expired()
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT coop, product, old_price, new_price, expires FROM offers ORDER BY added_at DESC LIMIT ?",
        (max_rows,)).fetchall()
    con.close()
    if not rows:
        return ""
    lines = []
    for coop, product, old_p, new_p, expires in rows:
        line = f"{coop} | {product} | "
        line += f"{old_p} ← {new_p} د.ك" if old_p else f"{new_p} د.ك"
        if expires:
            line += f" | حتى {expires}"
        lines.append(line)
    return "\n".join(lines)


SYSTEM_PROMPT = """أنت مساعد ذكي متخصص بأسعار المنتجات في دولة الكويت، ترد على عملاء واتساب.

مهمتك:
1. تعرّف على المنتج من الصورة أو من نص الرسالة.
2. إذا وُجد قسم "عروض الجمعيات السارية" في الرسالة: افحصه أولاً — إن كان المنتج المطلوب (أو مشابه له) ضمنه، ابدأ ردك بسطر العرض بعلامة 🏷️ قبل نتائج البحث.
3. سوّ بحثات Google موجّهة — لا تكتفي ببحث واحد عام. سوّ بحثات منفصلة بإضافة اسم المتجر أو نطاقه لاستعلام البحث. المتاجر الكويتية ذات المتاجر الإلكترونية الفعلية:
   - جمعية دوت كوم: "اسم المنتج jm3eia.com"
   - توصيل: "اسم المنتج taw9eel.com"
   - أونكوست: "اسم المنتج oncost.com"
   - جراند هايبر: "اسم المنتج grandhyper.com"
   - سيتي هايبر: "اسم المنتج cchyper.com"
   - سلطان سنتر: "اسم المنتج sultan-center.com"
   - دروبز: "اسم المنتج Dropz Kuwait"
   - هاي آند باي: "اسم المنتج HiandBuy"
   - سيفكو: "اسم المنتج Saveco Kuwait"
   - مقاضي: "اسم المنتج maqadhe.com"
   - مكاني: "اسم المنتج Makani"
   - وبحث عام: "اسم المنتج سعر الكويت"
   الجمعيات التعاونية (مشرف، الروضة وحولي، العديلية، صباح السالم، سلوى، بيان، الزهراء وغيرها):
   متاجرها الإلكترونية على منصة طلبات Talabat — ابحث: "اسم المنتج talabat جمعية" أو باسم الجمعية التي يطلبها العميل.
   اختر 5-7 بحثات من الأنسب لنوع المنتج.
4. اعرض النتائج بشكل مرتب وواضح.

قواعد الرد:
- الأسلوب: كويتي ودّي وسريع، مناسب لمحادثة واتساب.
- لا مقدمات ولا ترحيب — ابدأ مباشرة بسطر 📦 اسم المنتج (أو 🏷️ العرض إن وُجد). التحية فقط إذا العميل حياك بدون سؤال.
- اعرض الأسعار بهذا الشكل الإلزامي بالضبط، سطر لكل متجر، بدون ترقيم وبدون أقواس مربعة:
📦 اسم المنتج
✅ المتجر الأرخص — السعر د.ك
• المتجر الثاني — السعر د.ك
• المتجر الثالث — السعر د.ك
- إذا فيه أحجام مختلفة، اذكر الحجم داخل سطر المتجر نفسه، ولا تسوّ أقساماً منفصلة لكل حجم.
- إذا السعر تقريبي أو غير مؤكد، نبّه بسطر واحد.
- إذا ما لقيت أسعار بالكويت، قول بصراحة إنك ما حصلت سعر مؤكد.
- ممنوع منعاً باتاً: أي رابط، أي صيغة [نص](رابط)، أي عبارة "رابط الشراء" أو "اضغط هنا"، أي نجوم * أو ** أو جداول Markdown أو عناوين #. مثال خاطئ يجب ألا تكرره أبداً: "سوق زمزم بسعر 0.950 | [رابط الشراء من سوق زمزم](...)". الصحيح فقط: "• سوق زمزم — 0.950 د.ك". زر الشراء يضيفه النظام تلقائياً.
- لا تستخدم علامات استشهاد أو أقواس مرجعية مثل [1] أو [4.2.6] نهائياً.
- خل الرد مختصر — أقل من 12 سطر، وأنهِ ردك دائماً بجملة مكتملة.
- في نهاية ردك أضف سطراً أخيراً منفصلاً بهذا الشكل بالضبط: BEST:<دومين المتجر الأرخص> مثل BEST:luluhypermarket.com — هذا السطر للنظام ولن يراه العميل.
"""


# ========= 1. التحقق من الـ Webhook =========
@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == VERIFY_TOKEN:
        return Response(content=params.get("hub.challenge"), media_type="text/plain")
    return Response(content="Verification failed", status_code=403)


# ========= 2. استقبال الرسائل — 200 فوراً والمعالجة بالخلفية =========
@app.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" in entry:
            message = entry["messages"][0]
            msg_id = message.get("id")
            if msg_id and msg_id not in processed_ids:
                processed_ids.append(msg_id)
                background_tasks.add_task(process_message, message)
    except (KeyError, IndexError):
        pass
    return {"status": "ok"}


# ========= 3. معالجة الرسالة =========
def process_message(message: dict):
    from_number = message["from"]
    msg_type = message.get("type")

    try:
        # ===== أمر الأدمن: تحديث عروض الجمعيات (من رقمك فقط) =====
        if msg_type == "text":
            body = message["text"]["body"]
            if body.strip().startswith("تحديث_عروض:"):
                if ADMIN_PHONE and from_number.endswith(ADMIN_PHONE[-8:]):
                    csv_part = body.split(":", 1)[1]
                    added = store_offers_csv(csv_part)
                    purge_expired()
                    send_whatsapp_text(from_number, f"✅ خزنت {added} عرض جديد. القاعدة محدثة ونظيفة.")
                else:
                    send_whatsapp_text(from_number, "هذا الأمر للإدارة فقط 🙏")
                return

        parts = []

        if msg_type == "image":
            send_whatsapp_text(from_number, "ثواني بس.. قاعد أحوس بمواقع الكويت الحين عشان أطلع لك أقوى صيدة وأرخص سعر!")
            image_b64, mime = download_whatsapp_media(message["image"]["id"])
            parts.append({"inline_data": {"mime_type": mime, "data": image_b64}})
            user_task = "تعرف على هذا المنتج وابحث الآن بحثاً حياً عن أسعاره الحالية في الكويت لترد على العميل."

        elif msg_type == "text":
            user_text = message["text"]["body"]
            send_whatsapp_text(from_number, "🔍 ثواني يا خوي، أدور لك الأسعار الحالية بالكويت...")
            user_task = f"العميل يسأل: {user_text}\nابحث الآن بحثاً حياً عن الأسعار الحالية في الكويت ورد عليه."

        else:
            send_whatsapp_text(from_number, "حياك الله 🌟 دز لي صورة المنتج أو اكتب اسمه، وأدور لك أسعاره الحالية بالكويت فوراً 🛒")
            return

        # ===== حقن عروض الجمعيات السارية في سياق الاستعلام =====
        offers_ctx = active_offers_context()
        if offers_ctx:
            user_task += ("\n\n[عروض الجمعيات السارية — من نشرات انستغرام الرسمية، موثوقة وحديثة:]\n"
                          + offers_ctx)
        parts.append({"text": user_task})

        # ===== استدعاء Gemini مع البحث الحي =====
        reply_text, best_url = call_gemini(parts)

        if not reply_text:
            reply_text = "ما قدرت ألقى نتيجة واضحة 😅 جرب صورة أوضح أو اكتب اسم المنتج بالنص."

        print(f"REPLY LEN: {len(reply_text)} | URL: {bool(best_url)}")

        if best_url:
            send_whatsapp_cta(from_number, reply_text, best_url)
        else:
            send_whatsapp_text(from_number, reply_text)

    except Exception as e:
        print(f"Error processing message: {e}")
        try:
            send_whatsapp_text(from_number, "صار خلل بسيط بالشبكة 🙏 عيد المحاولة بعد شوي غالي.")
        except Exception:
            pass


def call_gemini(parts: list):
    """نداء Gemini مع البحث الحي. يرجع (نص الرد, رابط الأرخص أو None)"""
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": parts}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2500},
    }

    for attempt in (1, 2):
        r = requests.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload, timeout=120)
        if r.status_code == 429 and attempt == 1:
            print("GEMINI 429 — free tier rate limit, retrying in 8s")
            time.sleep(8)
            continue
        if r.status_code >= 400:
            print(f"GEMINI error {r.status_code}: {r.text[:400]}")
            return "", None
        break

    try:
        data = r.json()
        cand = data["candidates"][0]
        out = cand["content"]["parts"]
        text = "".join(p.get("text", "") for p in out).strip()

        # ===== تنظيف قسري شامل (الموديل أحياناً يتجاهل التعليمات) =====
        text = re.sub(r"(?<=\S)\[[\d]+(?:[.,][\d]+)*\]", "", text)
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"\[[^\]]*\]\([^)]*\)", "", text)          # [نص](رابط)
        text = re.sub(r"\|?\s*\[[^\]]*\]\(?", "", text)           # [نص]( يتيمة
        text = re.sub(r"(مع )?روابط الشراء المباشرة:?", "", text)
        text = re.sub(r"\|?\s*رابط الشراء[^\n|]*", "", text)
        text = text.replace("**", "").replace("*", "")
        text = re.sub(r"[\(\)\[\]\|]+\s*$", "", text, flags=re.MULTILINE)
        lines = [l.rstrip() for l in text.splitlines()]
        lines = [l for l in lines if l.strip() not in (".", "-", "•", "|", "(", ")")]
        text = "\n".join(lines)
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        # استخراج دومين الأرخص من سطر BEST: ثم حذفه
        best_domain = None
        m = re.search(r"BEST:\s*([\w.-]+)", text)
        if m:
            best_domain = m.group(1).lower()
            text = re.sub(r"\n?BEST:.*", "", text).strip()

        # رابط الأرخص من الـgrounding، مفكوكاً لرابط نهائي قصير
        best_url = None
        try:
            chunks = cand.get("groundingMetadata", {}).get("groundingChunks", [])
            target = None
            for c in chunks:
                title = (c.get("web", {}).get("title") or "").lower()
                if best_domain and best_domain.split(".")[0] in title:
                    target = c.get("web", {}).get("uri")
                    break
            if not target and chunks:
                target = chunks[0].get("web", {}).get("uri")
            if target:
                final = requests.head(target, allow_redirects=True, timeout=15).url
                if len(final) < 500 and "vertexaisearch" not in final:
                    best_url = final
        except Exception as e:
            print(f"LINK RESOLVE: {e}")

        return text, best_url
    except (KeyError, IndexError, TypeError, ValueError) as e:
        print(f"GEMINI bad response: {e} — {r.text[:400]}")
        return "", None


# ========= أدوات مساعدة للواتساب =========
def download_whatsapp_media(media_id: str):
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    meta = requests.get(f"{GRAPH_URL}/{media_id}", headers=headers, timeout=30).json()
    media_url = meta["url"]
    mime = meta.get("mime_type", "image/jpeg")
    img = requests.get(media_url, headers=headers, timeout=60)
    img.raise_for_status()
    return base64.standard_b64encode(img.content).decode("utf-8"), mime


def send_whatsapp_text(to_number: str, text: str):
    url = f"{GRAPH_URL}/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}",
               "Content-Type": "application/json"}
    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)] or [text]
    for chunk in chunks:
        payload = {"messaging_product": "whatsapp", "to": to_number,
                   "type": "text", "text": {"body": chunk}}
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code >= 400:
            print(f"WhatsApp send error: {r.status_code} {r.text}")


def send_whatsapp_cta(to_number: str, text: str, url: str, button_title: str = "🛒 شوف أرخص سعر"):
    """رسالة مع زر مدمج. النص الطويل يُرسل كاملاً برسالة + زر برسالة قصيرة — بدون قص"""
    if len(text) > 1000:
        send_whatsapp_text(to_number, text)
        body = "اضغط الزر وتوجه لأرخص سعر 👇"
    else:
        body = text

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": body},
            "action": {"name": "cta_url",
                       "parameters": {"display_text": button_title[:25], "url": url}},
        },
    }
    r = requests.post(f"{GRAPH_URL}/{PHONE_NUMBER_ID}/messages", json=payload,
                      headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}",
                               "Content-Type": "application/json"}, timeout=30)
    if r.status_code >= 400:
        print(f"CTA send error: {r.status_code} {r.text}")
        if len(text) <= 1000:
            send_whatsapp_text(to_number, text + f"\n\n🔗 {url}")
        else:
            send_whatsapp_text(to_number, f"🔗 {url}")


@app.get("/")
async def health():
    return {"status": "running", "bot": "Kuwait Price Bot 🇰🇼 (Gemini + Daily Coop Offers)"}
