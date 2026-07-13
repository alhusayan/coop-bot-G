"""مساعد الجمعية الذكي — بوت واتساب
نسخة محسّنة: مطابقة برمز المنتج أولاً + تعلّم ذاتي للرموز + رد فوري + منع التكرار
"""
import os
import json
from collections import deque

import httpx
from fastapi import FastAPI, Request, Response, BackgroundTasks

from app.db import (init_db, best_prices, log_missed, log_pending_review,
                    get_db, upsert_product, upsert_price)
from app.matcher import match_smart, format_size, make_size
from app.ai import extract_product_from_image, smart_card_online
from app.matcher import normalize

WA_TOKEN = os.environ.get("WA_TOKEN", "")
WA_PHONE_ID = os.environ.get("WA_PHONE_ID", "")
WA_VERIFY_TOKEN = os.environ.get("WA_VERIFY_TOKEN", "coop-secret-123")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "change-me")
ONLINE_FALLBACK = os.environ.get("ONLINE_FALLBACK", "1") == "1"

# عتبات المطابقة
CONFIDENT = 0.60   # فوقها: نرد مباشرة
MAYBE = 0.35       # بينها وبين CONFIDENT: نرد مع "مو متأكد"، وتحتها: "ما لقيت"

app = FastAPI(title="Co-Op Smart Assistant")
init_db()

GRAPH = "https://graph.facebook.com/v21.0"

# منع معالجة نفس الرسالة مرتين (ميتا تعيد الإرسال إذا تأخر الرد)
SEEN_IDS = deque(maxlen=500)

async def send_whatsapp(to: str, text: str):
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            await client.post(
                f"{GRAPH}/{WA_PHONE_ID}/messages",
                headers={"Authorization": f"Bearer {WA_TOKEN}"},
                json={"messaging_product": "whatsapp", "to": to,
                      "type": "text", "text": {"body": text}},
            )
    except Exception as e:
        print("SEND ERROR:", e)


async def download_media(media_id: str):
    async with httpx.AsyncClient(timeout=60) as client:
        meta = await client.get(f"{GRAPH}/{media_id}",
                                headers={"Authorization": f"Bearer {WA_TOKEN}"})
        info = meta.json()
        media = await client.get(info["url"],
                                 headers={"Authorization": f"Bearer {WA_TOKEN}"})
        return media.content, info.get("mime_type", "image/jpeg")


# ---------------------------------------------------------------------------
# صياغة الرد
# ---------------------------------------------------------------------------

def format_reply(product: dict, prices: list, price_seen=None) -> str:
    name = product.get("name_ar") or product.get("name_en") or "المنتج"
    if not prices:
        return f"تعرفت على {name} بس ما عندي أسعاره حالياً — سجلته وبنضيفه قريب 🙏"
    cheapest = prices[0]
    lines = [f"📦 {name}\n"]
    for p in prices:
        offer = " 🏷️ (عرض)" if p["is_offer"] else ""
        lines.append(f"• {p['store']}: {p['price']:.3f} د.ك{offer}")
    if price_seen:
        diff = price_seen - cheapest["price"]
        if diff > 0.010:
            lines.append(f"\n🔴 السعر اللي عندك {price_seen:.3f} — توفر {diff*1000:.0f} فلس في {cheapest['store']}")
        else:
            lines.append("\n🟢 السعر اللي عندك ممتاز — هذا أفضل سعر حالياً")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# منطق المعالجة
# ---------------------------------------------------------------------------

async def handle_query(user_phone: str, query_text: str, price_seen=None,
                       alt_query: str = None, brand_hints: list = None,
                       size_hint=None):
    """المسار الموحّد للنص والصورة — مطابقة بالاسم (عربي و/أو إنجليزي، الأفضل يفوز)"""
    query_text = (query_text or "").translate(AR_DIGITS)
    res = match_smart(query_text, brand_hints, size_hint)
    if alt_query:
        res2 = match_smart(alt_query.translate(AR_DIGITS), brand_hints, size_hint)
        if res2["confidence"] > res["confidence"]:
            res, res2 = res2, res
        if res["variant"] is None and res2["variant"] is not None:
            res["variant"] = res2["variant"]

    product, confidence = res["product"], res["confidence"]
    variant = res["variant"]
    print(f"MATCH: q={query_text!r} alt={alt_query!r} brands={brand_hints} → "
          f"{product['canonical_key'] if product else None} ({confidence}) "
          f"variant={'yes' if variant else 'no'}")

    # بديل الحجم القوي يغلب مطابقة ضعيفة لمنتج ثاني:
    # (اريال 1.5كجم المطلوب مقابل اريال 6كجم عندنا) أفضل من (بحر 1.5كجم بثقة متوسطة)
    strong_variant = variant and variant["name_score"] > max(confidence, 0.55)

    def variant_reply():
        vp = variant["product"]
        q_size, t_size = format_size(variant["q_size"]), format_size(variant["t_size"])
        note = (f"ما لقيت حجم {q_size} بالضبط، "
                f"بس نفس المنتج متوفر بحجم {t_size}:") if q_size and t_size \
               else "ما لقيت هالحجم بالضبط، بس نفس المنتج متوفر بحجم مختلف:"
        log_missed(user_phone, f"{query_text} [variant_shown={vp['canonical_key']}]")
        return f"🔍 {note}\n\n" + format_reply(vp, best_prices(vp["id"]))

    if product and confidence >= CONFIDENT:
        await send_whatsapp(
            user_phone,
            format_reply(product, best_prices(product["id"]), price_seen),
        )
    elif strong_variant:
        # نفس الماركة والمنتج بحجم ثاني — أصدق من اقتراح منتج منافس بثقة متوسطة
        await send_whatsapp(user_phone, variant_reply())
    elif product and confidence >= MAYBE:
        log_pending_review(
            user_phone,
            json.dumps({"query": query_text,
                        "matched": product["canonical_key"]}, ensure_ascii=False),
            confidence,
        )
        reply = "🤔 مو متأكد ١٠٠٪ إن هذا قصدك:\n\n" + format_reply(
            product, best_prices(product["id"]), price_seen)
        await send_whatsapp(user_phone, reply)
    elif variant:
        await send_whatsapp(user_phone, variant_reply())
    else:
        log_missed(user_phone, query_text)
        if ONLINE_FALLBACK:
            online_q = f"{query_text} {alt_query}" if alt_query else query_text
            card = await smart_card_online(online_q, price_seen)
            if card:
                await send_whatsapp(user_phone, format_smart_card(card, price_seen))
                if card.get("prices"):
                    save_online_results(query_text, alt_query, card["prices"])
                return
        await send_whatsapp(
            user_phone,
            "ما لقيت هالمنتج عندي حالياً 🙏\nسجلت طلبك وبنضيفه قريب — جرب منتج ثاني أو اكتب اسمه بشكل أوضح.",
        )


def format_smart_card(card: dict, price_seen=None) -> str:
    """التقرير الاحترافي الموحد: تعريف + حكم + أسعار + مزايا/عيوب + بدائل"""
    lines = []
    if card.get("product_name"):
        lines.append(f"📦 *{card['product_name']}*")
    score = card.get("score")
    if card.get("verdict"):
        stars = f" {'⭐' * round(score / 2)}" if score else ""
        lines.append(f"\n⚖️ *{card['verdict']}*{stars}" + (f" ({score}/10)" if score else ""))
    prices = sorted(card.get("prices") or [], key=lambda r: r["price"])
    if prices:
        lines.append("\n💰 *الأسعار بالكويت:*")
        for i, r in enumerate(prices):
            tag = " 🏆" if i == 0 and len(prices) > 1 else ""
            lines.append(f"• {r['store']}: {r['price']:,.3f} د.ك{tag}")
        if price_seen:
            diff = price_seen - prices[0]["price"]
            if diff > 0.010:
                lines.append(f"🔴 المعروض عليك {price_seen:,.3f} — أرخص عند {prices[0]['store']}")
            else:
                lines.append("🟢 السعر المعروض عليك ممتاز")
    if card.get("pros"):
        lines.append("\n✅ " + " • ".join(card["pros"]))
    if card.get("cons"):
        lines.append("⚠️ " + " • ".join(card["cons"]))
    if card.get("price_opinion"):
        lines.append(f"💡 {card['price_opinion']}")
    if card.get("alternatives"):
        lines.append("\n🔄 *بدائل تستاهل نظرة:* " + " • ".join(card["alternatives"]))
    lines.append("\n_تقرير آلي من بحث مباشر — تأكد من المتجر قبل الشراء_")
    return "\n".join(lines)


def save_online_results(query_ar: str, query_en: str, results: list):
    """حفظ نتائج البحث الحي بالقاعدة — القاعدة تتعلم من كل 'ما لقيت'"""
    try:
        best_name = next((r["product_name"] for r in results if r.get("product_name")), None)
        name_ar = best_name if best_name and any('\u0600' <= c <= '\u06FF' for c in best_name) else (query_ar or best_name)
        name_en = best_name if best_name and not any('\u0600' <= c <= '\u06FF' for c in best_name) else query_en
        key = normalize(name_ar or name_en or query_ar)
        if not key:
            return
        pid = upsert_product(canonical_key=key, name_ar=name_ar, name_en=name_en)
        for r in results:
            upsert_price(pid, r["store"], r["price"])
        print(f"ONLINE LEARNED: {key!r} ← {len(results)} prices")
    except Exception as e:
        print("ONLINE SAVE ERROR:", repr(e))


async def process_image(user: str, media_id: str):
    """تعمل في الخلفية بعد الرد على ميتا"""
    try:
        image_bytes, mime = await download_media(media_id)
        extraction = await extract_product_from_image(image_bytes, mime)
        print("IMG EXTRACT:", json.dumps(extraction, ensure_ascii=False))

        if extraction.get("error"):
            await send_whatsapp(user, "ما قدرت أتعرف على منتج بالصورة — جرب صورة أوضح أو اكتب اسم المنتج.")
            return

        query_ar = " ".join(str(x) for x in [
            extraction.get("brand"), extraction.get("product_name_ar"),
            extraction.get("size_value"), extraction.get("size_unit")] if x)
        query_en = extraction.get("product_name_en") or None

        # الماركة بأي لغة: حقل brand + أول كلمة من كل اسم
        # (العبوة إنجليزية "Ariel" لكن القاعدة عربية "اريال" — نحتاج الاثنين)
        brand_hints = [h for h in [
            extraction.get("brand"),
            (extraction.get("product_name_ar") or "").split()[0] if extraction.get("product_name_ar") else None,
            (extraction.get("product_name_en") or "").split()[0] if extraction.get("product_name_en") else None,
        ] if h]

        # الحجم من الاستخراج ينطبق على المطابقة باللغتين — يسد ثغرة
        # الاستعلام الإنجليزي بدون حجم اللي يتهرب من عقوبة التعارض
        size_hint = make_size(extraction.get("size_value"), extraction.get("size_unit")) \
            if extraction.get("size_value") and extraction.get("size_unit") else None

        await handle_query(
            user, query_ar or query_en or "",
            price_seen=extraction.get("price_seen"),
            alt_query=query_en if query_ar else None,
            brand_hints=brand_hints,
            size_hint=size_hint,
        )
    except Exception as e:
        print("IMAGE ERROR:", repr(e))
        await send_whatsapp(user, "صار خلل بسيط وأنا أحلل الصورة 🙏 جرب مرة ثانية أو اكتب اسم المنتج.")


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------

@app.get("/webhook")
async def verify(request: Request):
    params = request.query_params
    if params.get("hub.verify_token") == WA_VERIFY_TOKEN:
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    return Response(status_code=403)


@app.post("/webhook")
async def receive(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" not in entry:
            return {"ok": True}
        msg = entry["messages"][0]

        # تجاهل الرسائل المكررة (إعادة إرسال من ميتا)
        msg_id = msg.get("id")
        if msg_id in SEEN_IDS:
            return {"ok": True}
        SEEN_IDS.append(msg_id)

        user = msg["from"]
        if msg["type"] == "text":
            background_tasks.add_task(handle_query, user, msg["text"]["body"])
        elif msg["type"] == "image":
            background_tasks.add_task(send_whatsapp, user, "🔍 لحظة، قاعد أتعرف على المنتج وأجهز لك تقريره...")
            background_tasks.add_task(process_image, user, msg["image"]["id"])
    except (KeyError, IndexError):
        pass
    return {"ok": True}


# ---------------------------------------------------------------------------
# لوحة الأدمن
# ---------------------------------------------------------------------------

@app.get("/admin/pending")
async def pending(key: str):
    if key != ADMIN_KEY:
        return Response(status_code=403)
    with get_db() as db:
        rows = db.execute("SELECT * FROM pending_reviews WHERE resolved = 0 ORDER BY id DESC LIMIT 50").fetchall()
        return [dict(r) for r in rows]


@app.get("/admin/missed")
async def missed(key: str):
    if key != ADMIN_KEY:
        return Response(status_code=403)
    with get_db() as db:
        rows = db.execute("SELECT query, COUNT(*) as cnt FROM missed_queries GROUP BY query ORDER BY cnt DESC LIMIT 50").fetchall()
        return [dict(r) for r in rows]


@app.get("/admin/find")
async def find(key: str, q: str):
    """تشخيص: هل المنتج موجود بالقاعدة؟ بحث جزئي + نتيجة المطابقة الذكية"""
    if key != ADMIN_KEY:
        return Response(status_code=403)
    from app.matcher import normalize
    tokens = normalize(q).split()
    if not tokens:
        return {"error": "empty query"}
    where = " AND ".join(["name_norm LIKE ?"] * len(tokens))
    with get_db() as db:
        rows = db.execute(
            f"SELECT id, name_ar, name_en FROM products WHERE {where} LIMIT 20",
            [f"%{t}%" for t in tokens],
        ).fetchall()
    smart = match_smart(q)
    return {
        "query_tokens": tokens,
        "substring_hits": [dict(r) for r in rows],
        "smart_best": {
            "name": (smart["product"] or {}).get("name_ar") or (smart["product"] or {}).get("name_en"),
            "confidence": smart["confidence"],
        },
        "total_products": db_count(),
    }


def db_count():
    with get_db() as db:
        return db.execute("SELECT COUNT(*) c FROM products").fetchone()["c"]


@app.get("/admin/scrape_now")
async def scrape_now(key: str):
    """تشغيل السكرابر فوراً بدل انتظار الدورة — يرجع عدد المنتجات أو الخطأ"""
    if key != ADMIN_KEY:
        return Response(status_code=403)
    import asyncio
    try:
        from scraper.jm3eia_scraper import run as scrape_run
        await asyncio.to_thread(scrape_run)
        with get_db() as db:
            c = db.execute("SELECT COUNT(*) c FROM products").fetchone()["c"]
        return {"ok": True, "products": c}
    except Exception as e:
        return {"ok": False, "error": repr(e)}


@app.get("/")
async def health():
    return {"status": "ok", "service": "coop-smart-assistant"}
