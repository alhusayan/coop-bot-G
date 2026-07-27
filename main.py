# -*- coding: utf-8 -*-
"""
WhatsApp Kuwait Shopping Bot - v13

Main fixes:
1) Store buttons no longer depend only on Gemini's LINKS line.
2) Grounding URLs are mapped using groundingSupports, domains, titles, and safe fallbacks.
3) A second grounded-search attempt is made when Gemini returns prices without sources.
4) The nearby-location CTA request is sent even when store buttons are unavailable.
5) Gemini and WhatsApp API errors are written clearly to Railway logs.
6) Cart HTML is escaped and products without a URL show an unavailable button.
"""

import asyncio
import base64
import html
import logging
import os
import re
import threading
import time
import urllib.parse
import uuid
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from fastapi import BackgroundTasks, FastAPI, Request, Response
from fastapi.responses import HTMLResponse


# -----------------------------------------------------------------------------
# Application and logging
# -----------------------------------------------------------------------------

app = FastAPI(title="Kuwait Shopping WhatsApp Bot", version="13.0")

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("shopping-bot")


# -----------------------------------------------------------------------------
# Environment variables
# -----------------------------------------------------------------------------

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "").strip()
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "").strip()
VERIFY_TOKEN = os.environ.get(
    "VERIFY_TOKEN",
    "MY_SECRET_COOP_BOT_TOKEN",
).strip()

WHATSAPP_GRAPH_VERSION = os.environ.get(
    "WHATSAPP_GRAPH_VERSION",
    "v20.0",
).strip()

RAILWAY_PUBLIC_DOMAIN = os.environ.get(
    "RAILWAY_PUBLIC_DOMAIN",
    "fanzia.up.railway.app",
).strip()

GRAPH_URL = f"https://graph.facebook.com/{WHATSAPP_GRAPH_VERSION}"
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124 Safari/537.36"
    )
}

BUFFER_SECONDS = int(os.environ.get("BUFFER_SECONDS", "4"))
CART_TTL_SECONDS = int(os.environ.get("CART_TTL_SECONDS", "86400"))


# -----------------------------------------------------------------------------
# In-memory state
# -----------------------------------------------------------------------------

processed_ids: deque = deque(maxlen=2000)
CARTS: Dict[str, Dict[str, Any]] = {}
IMAGE_BUFFER: Dict[str, Dict[str, Any]] = defaultdict(
    lambda: {"images": [], "time": 0.0, "bot_id": ""}
)
LAST_SEARCH: Dict[str, Dict[str, str]] = {}

STATE_LOCK = threading.RLock()
RESOLVER = ThreadPoolExecutor(max_workers=6)
WORKERS = ThreadPoolExecutor(max_workers=3)


# -----------------------------------------------------------------------------
# Gemini prompts
# -----------------------------------------------------------------------------

SYSTEM_PROMPT = """
أنت مساعد تسوق واختيارات ذكي داخل الكويت. مهمتك ليست دائماً إيجاد الأرخص؛ اختر طريقة البحث حسب نية المستخدم.

أولاً: حدد نوع الطلب داخلياً من دون أن تشرح التصنيف للمستخدم:

1) طلب محدد أو ببراند/موديل واضح:
مثل: iPhone 16 Pro، عطر Dior Sauvage، غسالة Samsung موديل محدد.
- ابحث عن نفس المنتج بالضبط.
- رتّب النتائج حسب السعر من الأرخص إلى الأعلى.
- لا تستبدل المنتج بمنتج آخر.

2) طلب عام من دون براند أو موديل محدد:
مثل: فلات وايت حار، عطر رجالي، سماعة رياضية، مطعم برغر.
- لا تبحث عن الأرخص فقط.
- ابحث عن أفضل الخيارات تقييماً مع عدد مراجعات كافٍ وحداثة المعلومات.
- وازن بين التقييم، عدد المراجعات، الجودة، السمعة، والسعر المناسب.
- تجنب اختيار نتيجة بتقييم مرتفع مبني على عدد قليل جداً من المراجعات.
- قدّم "أفضل قيمة" وليس الأغلى تلقائياً.
- للمقاهي والمطاعم والخدمات: استخدم تقييمات الأماكن ومراجعاتها داخل الكويت، واذكر السعر التقريبي إن توفر.
- للمنتجات العامة مثل "عطر رجالي": رشّح منتجات محددة مناسبة ومتوفرة في الكويت، مع متجر موثوق وسعر حالي إن توفر.

تعليمات إلزامية:
- استخدم بحث Google الفعلي في كل طلب.
- لا تخمّن السعر أو التقييم أو عدد المراجعات أو اسم المتجر.
- اعرض فقط نتائج لها مصدر بحث حقيقي.
- استخدم الدينار الكويتي عند ذكر الأسعار.
- ممنوع إظهار روابط مباشرة داخل الرد.
- ممنوع Markdown.
- اجعل الرد مختصراً وواضحاً.

تنسيق الطلب المحدد ببراند أو موديل:
📦 [اسم المنتج الدقيق]
✅ [المتجر الأرخص] — [السعر] د.ك
• [المتجر الثاني] — [السعر] د.ك
• [المتجر الثالث] — [السعر] د.ك
LINKS: اسم المتجر الأول=الدومين الحقيقي, اسم المتجر الثاني=الدومين الحقيقي, اسم المتجر الثالث=الدومين الحقيقي

تنسيق الطلب العام من دون براند:
📦 [وصف طلب المستخدم]
🏆 الأفضل قيمة وتقييماً:
✅ [اسم الخيار أو المكان] — [السعر أو متوسط السعر إن توفر] د.ك | ⭐ [التقييم]/5 ([عدد المراجعات])
• [الخيار الثاني] — [السعر إن توفر] د.ك | ⭐ [التقييم]/5 ([عدد المراجعات])
• [الخيار الثالث] — [السعر إن توفر] د.ك | ⭐ [التقييم]/5 ([عدد المراجعات])
💡 الاختيار الأول هو الأفضل لأنه [سبب قصير مبني على التقييم والقيمة].
LINKS: اسم الخيار الأول=الدومين الحقيقي, اسم الخيار الثاني=الدومين الحقيقي, اسم الخيار الثالث=الدومين الحقيقي

إذا لم يتوفر سعر موثوق في الطلب العام، اكتب "السعر غير متوفر" بدلاً من اختراع سعر.
إذا وجدت خياراً أو خيارين موثوقين فقط، اعرض الموجود فقط.

إذا كان الطلب عن عقار أو سيارة:
- أعطِ تقييماً مختصراً جداً.
- اذكر متوسط السعر أو نطاق السعر المتوقع.
- لا تستخدم تنسيق المتاجر السابق إذا لم يكن مناسباً.
""".strip()

GROUNDING_RETRY_INSTRUCTION = """
نفّذ بحث Google الآن ولا تعتمد على معلومات محفوظة.
أحتاج مصادر Grounding فعلية لكل نتيجة مذكورة.
إذا كان الطلب عاماً بلا براند، تحقّق من التقييم وعدد المراجعات والسعر المناسب، ولا ترتب حسب الأرخص فقط.
التزم بسطر LINKS في النهاية، ولا تذكر أي نتيجة من دون مصدر.
""".strip()

MAP_CATEGORY_PROMPT = """
أنت خبير تسوق في السوق الكويتي.
بناءً على اسم المنتج، أعطني عبارة بحث قصيرة ودقيقة لخرائط Google تجلب الأماكن الصحيحة حول موقع المستخدم.

القواعد:
- الإلكترونيات الذكية والجوالات واللابتوبات: Xcite OR Eureka OR Best Al Yousifi
- الأجهزة المنزلية: Xcite OR Eureka OR Best Al Yousifi
- الأدوية والمكملات: صيدلية OR Pharmacy
- المواد الغذائية واللحوم: جمعية تعاونية OR Supermarket
- ألعاب الفيديو: Video games store OR محل ألعاب فيديو
- الكهرباء والإضاءة: Electrical supply OR مواد كهربائية
- الملابس والمعدات الرياضية: Intersport OR Go Sport OR محل رياضي
- مستحضرات التجميل والعطور: Cosmetics OR Perfume store
- إذا لم تكن متأكداً، استخدم اسم المنتج نفسه.

أعد عبارة البحث فقط من دون شرح أو علامات اقتباس.
""".strip()


# -----------------------------------------------------------------------------
# General helpers
# -----------------------------------------------------------------------------

def valid_http_url(url: str) -> bool:
    if not url:
        return False
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def normalize_public_domain(domain: str) -> str:
    value = (domain or "").strip().rstrip("/")
    value = re.sub(r"^https?://", "", value, flags=re.IGNORECASE)
    return value


def clean_domain(domain: str) -> str:
    value = re.sub(
        r"^https?://",
        "",
        (domain or "").strip().lower(),
        flags=re.IGNORECASE,
    )
    return value.replace("www.", "").split("/")[0].strip()


def domain_key(domain: str) -> str:
    cleaned = clean_domain(domain)
    return cleaned.split(".")[0] if cleaned else ""


def normalize_name(value: str) -> str:
    return re.sub(r"[^\w\u0600-\u06FF]+", "", (value or "").lower())


def deduplicate_keep_order(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        key = value.strip()
        if key and key not in seen:
            result.append(key)
            seen.add(key)
    return result


def parse_price(value: str) -> float:
    cleaned = (value or "").replace(",", "").strip()
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return 0.0


def extract_first_price(text: str) -> float:
    pattern = r"✅.*?(?:—|–|-)\s*([0-9][0-9,]*(?:\.[0-9]+)?)"
    match = re.search(pattern, text or "", flags=re.DOTALL)
    return parse_price(match.group(1)) if match else 0.0


def extract_product_name(text: str, fallback: str = "المنتج") -> str:
    match = re.search(r"📦\s*(.+)", text or "")
    if not match:
        return fallback
    return match.group(1).strip()[:100] or fallback


def extract_store_names(text: str) -> List[str]:
    """Extract displayed result names whether a numeric price exists or not."""
    stores: List[str] = []
    for line in (text or "").splitlines():
        match = re.match(
            r"^\s*(?:✅|•)\s*(.+?)\s*(?:—|–|-)\s*",
            line,
        )
        if match:
            stores.append(match.group(1).strip())
    return deduplicate_keep_order(stores)[:3]


def extract_link_pairs(text: str) -> Tuple[str, List[Tuple[str, str]]]:
    pairs: List[Tuple[str, str]] = []
    match = re.search(r"(?im)^\s*LINKS\s*:\s*(.+)$", text or "")

    if match:
        for part in re.split(r"[,،]+", match.group(1)):
            if "=" not in part:
                continue
            name, domain = part.split("=", 1)
            name = name.strip()
            domain = clean_domain(domain)
            if name and "." in domain:
                pairs.append((name, domain))

    cleaned_text = re.sub(
        r"(?im)^\s*LINKS\s*:.*$",
        "",
        text or "",
    ).strip()
    return cleaned_text, pairs


def clean_visible_gemini_text(text: str) -> str:
    value = re.sub(r"https?://\S+", "", text or "")
    value = value.replace("**", "")
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def source_label(title: str, url: str) -> str:
    cleaned_title = re.sub(r"\s+", " ", (title or "").strip())
    if cleaned_title:
        return cleaned_title[:40]

    try:
        host = urllib.parse.urlparse(url).netloc.replace("www.", "")
        return host.split(".")[0] or "المتجر"
    except Exception:
        return "المتجر"


# -----------------------------------------------------------------------------
# URL resolution and grounding mapping
# -----------------------------------------------------------------------------

def get_final_url(url: str) -> str:
    """
    Resolve Gemini's grounding redirect URL when possible.
    Keep the original grounding URL as a fallback instead of deleting it.
    """
    if not valid_http_url(url):
        return ""

    try:
        response = requests.head(
            url,
            allow_redirects=True,
            timeout=10,
            headers=HEADERS,
        )

        if response.status_code in {400, 403, 405}:
            response.close()
            response = requests.get(
                url,
                allow_redirects=True,
                timeout=12,
                stream=True,
                headers=HEADERS,
            )

        final_url = response.url or url
        response.close()

        if valid_http_url(final_url) and len(final_url) <= 2000:
            return final_url
        return url if len(url) <= 2000 else ""

    except requests.RequestException as exc:
        logger.warning("URL resolution failed: %s | %s", exc, url[:200])
        return url if len(url) <= 2000 else ""


def resolve_all(urls: List[str]) -> List[str]:
    if not urls:
        return []
    return list(RESOLVER.map(get_final_url, urls))


def build_grounding_records(metadata: Dict[str, Any]) -> List[Dict[str, str]]:
    chunks = metadata.get("groundingChunks") or []
    raw_urls = [
        ((chunk.get("web") or {}).get("uri") or "").strip()
        for chunk in chunks[:15]
    ]
    resolved_urls = resolve_all(raw_urls)

    records: List[Dict[str, str]] = []
    for index, chunk in enumerate(chunks[:15]):
        web = chunk.get("web") or {}
        raw_url = (web.get("uri") or "").strip()
        resolved_url = (
            resolved_urls[index]
            if index < len(resolved_urls)
            else raw_url
        )
        records.append(
            {
                "title": (web.get("title") or "").strip(),
                "raw_url": raw_url,
                "url": resolved_url or raw_url,
            }
        )
    return records


def add_url_mapping(
    url_map: Dict[str, str],
    used_urls: set,
    label: str,
    url: str,
) -> bool:
    clean_label = re.sub(r"\s+", " ", (label or "").strip())[:40]
    if not clean_label or not valid_http_url(url) or len(url) > 2000:
        return False
    if url in used_urls or clean_label in url_map:
        return False

    url_map[clean_label] = url
    used_urls.add(url)
    return True


def map_grounded_urls(
    visible_text: str,
    link_pairs: List[Tuple[str, str]],
    metadata: Dict[str, Any],
) -> Dict[str, str]:
    records = build_grounding_records(metadata)
    supports = metadata.get("groundingSupports") or []
    stores = extract_store_names(visible_text)

    url_map: Dict[str, str] = {}
    used_urls: set = set()

    # 1) Strongest method: map each displayed store to its grounding support.
    for store in stores:
        normalized_store = normalize_name(store)
        if not normalized_store:
            continue

        for support in supports:
            segment_text = ((support.get("segment") or {}).get("text") or "")
            if normalized_store not in normalize_name(segment_text):
                continue

            for chunk_index in support.get("groundingChunkIndices") or []:
                if not isinstance(chunk_index, int):
                    continue
                if 0 <= chunk_index < len(records):
                    if add_url_mapping(
                        url_map,
                        used_urls,
                        store,
                        records[chunk_index]["url"],
                    ):
                        break

            if store in url_map:
                break

    # 2) Match Gemini's LINKS domains to grounding source URLs/titles.
    for store_name, domain in link_pairs:
        if store_name in url_map:
            continue

        key = domain_key(domain)
        if not key:
            continue

        for record in records:
            searchable = (
                f"{record['title']} {record['raw_url']} {record['url']}"
            ).lower()
            if key in searchable:
                if add_url_mapping(
                    url_map,
                    used_urls,
                    store_name,
                    record["url"],
                ):
                    break

    # 3) Match the displayed store name directly to a source title or hostname.
    for store in stores:
        if store in url_map:
            continue

        normalized_store = normalize_name(store)
        if not normalized_store:
            continue

        for record in records:
            searchable = normalize_name(
                f"{record['title']} {urllib.parse.urlparse(record['url']).netloc}"
            )
            if normalized_store in searchable or searchable in normalized_store:
                if add_url_mapping(
                    url_map,
                    used_urls,
                    store,
                    record["url"],
                ):
                    break

    # 4) Final grounded fallback: expose available search sources.
    if not url_map:
        for record in records:
            add_url_mapping(
                url_map,
                used_urls,
                source_label(record["title"], record["url"]),
                record["url"],
            )
            if len(url_map) >= 3:
                break

    return dict(list(url_map.items())[:3])


# -----------------------------------------------------------------------------
# Gemini API
# -----------------------------------------------------------------------------

def post_gemini(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is missing")
        return None

    try:
        response = requests.post(
            GEMINI_URL,
            params={"key": GEMINI_API_KEY},
            json=payload,
            timeout=90,
        )
    except requests.RequestException as exc:
        logger.exception("Gemini request exception: %s", exc)
        return None

    if not response.ok:
        logger.error(
            "Gemini HTTP %s: %s",
            response.status_code,
            response.text[:1000],
        )
        return None

    try:
        return response.json()
    except ValueError:
        logger.error("Gemini returned invalid JSON: %s", response.text[:500])
        return None


def parse_gemini_candidate(
    data: Dict[str, Any],
) -> Tuple[str, Dict[str, str], int]:
    candidates = data.get("candidates") or []
    if not candidates:
        logger.warning("Gemini returned no candidates: %s", str(data)[:1000])
        return "", {}, 0

    candidate = candidates[0]
    content_parts = (candidate.get("content") or {}).get("parts") or []
    raw_text = "".join(
        part.get("text", "")
        for part in content_parts
        if isinstance(part, dict)
    ).strip()

    visible_text, link_pairs = extract_link_pairs(raw_text)
    visible_text = clean_visible_gemini_text(visible_text)

    metadata = candidate.get("groundingMetadata") or {}
    urls = map_grounded_urls(visible_text, link_pairs, metadata)
    chunks_count = len(metadata.get("groundingChunks") or [])

    logger.info(
        "Gemini result | stores=%s | LINKS=%s | chunks=%s | buttons=%s",
        extract_store_names(visible_text),
        link_pairs,
        chunks_count,
        list(urls.keys()),
    )

    return visible_text, urls, chunks_count


def call_gemini(
    parts: List[Dict[str, Any]],
    system: str = SYSTEM_PROMPT,
    use_search: bool = True,
    max_output_tokens: int = 2000,
) -> Tuple[str, Dict[str, str]]:
    """
    Call Gemini. For price searches, retry once when the answer has no
    grounded source buttons. This prevents intermittent text-only results.
    """
    best_text = ""
    best_urls: Dict[str, str] = {}

    attempts = 2 if use_search else 1

    for attempt in range(attempts):
        attempt_parts = list(parts)
        if attempt == 1:
            attempt_parts.append({"text": GROUNDING_RETRY_INSTRUCTION})

        payload: Dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": attempt_parts}],
            "generationConfig": {
                "temperature": 0.15,
                "maxOutputTokens": max_output_tokens,
            },
        }

        if use_search:
            payload["tools"] = [{"google_search": {}}]

        data = post_gemini(payload)
        if not data:
            continue

        text, urls, chunks_count = parse_gemini_candidate(data)

        if text and not best_text:
            best_text = text
        if urls:
            best_urls = urls
            best_text = text or best_text
            break

        logger.warning(
            "Gemini attempt %s returned no CTA sources; grounding chunks=%s",
            attempt + 1,
            chunks_count,
        )

    return best_text, best_urls


# -----------------------------------------------------------------------------
# WhatsApp API
# -----------------------------------------------------------------------------

def whatsapp_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }


def whatsapp_messages_url(bot_id: str) -> str:
    return f"{GRAPH_URL}/{bot_id}/messages"


def send_whatsapp_payload(
    bot_id: str,
    payload: Dict[str, Any],
    action_name: str,
) -> bool:
    if not WHATSAPP_TOKEN:
        logger.error("WHATSAPP_TOKEN is missing")
        return False
    if not bot_id:
        logger.error("Phone number ID is missing for %s", action_name)
        return False

    try:
        response = requests.post(
            whatsapp_messages_url(bot_id),
            json=payload,
            headers=whatsapp_headers(),
            timeout=20,
        )
    except requests.RequestException as exc:
        logger.exception("WhatsApp %s exception: %s", action_name, exc)
        return False

    if not response.ok:
        logger.error(
            "WhatsApp %s error %s: %s",
            action_name,
            response.status_code,
            response.text[:1000],
        )
        return False

    logger.info("WhatsApp %s sent successfully", action_name)
    return True


def send_whatsapp_text(to: str, text: str, bot_id: str) -> bool:
    body = (text or "").strip()
    if not body:
        return False

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body[:3900]},
    }
    return send_whatsapp_payload(bot_id, payload, "text")


def send_whatsapp_cta(
    to: str,
    body: str,
    link: str,
    bot_id: str,
    title: str,
) -> bool:
    if not valid_http_url(link):
        logger.warning("CTA skipped because URL is invalid: %s", link[:200])
        return False
    if len(link) > 2000:
        logger.warning("CTA skipped because URL is too long: %s", len(link))
        return False

    display_text = re.sub(r"\s+", " ", (title or "افتح الرابط").strip())[:20]
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": (body or "افتح الرابط")[:1024]},
            "action": {
                "name": "cta_url",
                "parameters": {
                    "display_text": display_text,
                    "url": link,
                },
            },
        },
    }
    return send_whatsapp_payload(bot_id, payload, "CTA")


def download_whatsapp_media(media_id: str) -> Tuple[str, str]:
    if not media_id:
        raise ValueError("WhatsApp media ID is missing")

    auth_header = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}

    metadata_response = requests.get(
        f"{GRAPH_URL}/{media_id}",
        headers=auth_header,
        timeout=20,
    )
    metadata_response.raise_for_status()
    metadata = metadata_response.json()

    media_url = metadata.get("url")
    if not media_url:
        raise ValueError("WhatsApp media URL is missing")

    media_response = requests.get(
        media_url,
        headers=auth_header,
        timeout=40,
    )
    media_response.raise_for_status()

    encoded = base64.b64encode(media_response.content).decode("ascii")
    mime_type = metadata.get("mime_type", "image/jpeg")
    return encoded, mime_type


# -----------------------------------------------------------------------------
# Product and cart helpers
# -----------------------------------------------------------------------------

def extract_products(text: str) -> List[str]:
    value = re.sub(
        r"^[•\-*\d.\)\s]+",
        "",
        (text or "").strip(),
        flags=re.MULTILINE,
    )
    parts = re.split(r"\s*(?:\n+|\+|,|،|\sو\s|\s&\s)\s*", value)
    products = [part.strip() for part in parts if len(part.strip()) > 2]
    products = deduplicate_keep_order(products)
    return products[:6] if len(products) > 1 else [value]


def remember_last_search(from_number: str, product: str) -> None:
    clean_product = (product or "").strip()[:150]
    if not clean_product:
        return
    with STATE_LOCK:
        LAST_SEARCH[from_number] = {"product": clean_product}


def get_last_search(from_number: str) -> Optional[str]:
    with STATE_LOCK:
        record = LAST_SEARCH.get(from_number) or {}
        return record.get("product")


def send_store_buttons(
    from_number: str,
    urls: Dict[str, str],
    bot_id: str,
) -> int:
    sent = 0
    for store_name, url in list(urls.items())[:3]:
        if send_whatsapp_cta(
            from_number,
            f"عرض {store_name} 👇",
            url,
            bot_id,
            f"🔗 {store_name}",
        ):
            sent += 1
    return sent


def send_nearby_location_prompt(from_number: str, bot_id: str) -> None:
    # This prompt is deliberately independent from the presence of store URLs.
    send_whatsapp_text(
        from_number,
        "📍 تبي أشوف لك أقرب مكان مناسب حولك؟ "
        "دز لي موقعك (Location) بالواتساب الحين "
        "وأفتح لك النتائج القريبة بالخريطة!",
        bot_id,
    )


def fetch_product_from_image(message: Dict[str, Any]) -> Dict[str, Any]:
    try:
        image = message.get("image") or {}
        encoded, mime_type = download_whatsapp_media(image.get("id", ""))
        text, urls = call_gemini(
            [
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": encoded,
                    }
                },
                {
                    "text": (
                        "حدد اسم المنتج بدقة. إذا كان البراند أو الموديل واضحاً فابحث عن أرخص سعر لنفس المنتج داخل الكويت، وإلا فاختر أفضل الخيارات تقييماً والأفضل قيمة."
                    )
                },
            ]
        )

        product_name = extract_product_name(text, "منتج")[:80]
        price = extract_first_price(text)
        cheapest_url = next(iter(urls.values()), "")
        cheapest_store = next(iter(urls.keys()), "متجر")

        return {
            "name": product_name,
            "store": cheapest_store,
            "price": price,
            "url": cheapest_url,
            "all_urls": urls,
        }
    except Exception as exc:
        logger.exception("fetch_product_from_image failed: %s", exc)
        return {
            "name": "منتج",
            "store": "غير متوفر",
            "price": 0.0,
            "url": "",
            "all_urls": {},
        }


def fetch_product_from_text(product: str) -> Dict[str, Any]:
    try:
        text, urls = call_gemini(
            [{"text": f"حلل الطلب أولاً: إذا كان محدداً ببراند أو موديل فابحث عن الأرخص لنفس المنتج، وإذا كان عاماً بلا براند فاختر الأفضل تقييماً والأفضل قيمة داخل الكويت. الطلب: {product}"}]
        )
        price = extract_first_price(text)
        cheapest_url = next(iter(urls.values()), "")
        cheapest_store = next(iter(urls.keys()), "متجر")

        return {
            "name": extract_product_name(text, product)[:80],
            "store": cheapest_store,
            "price": price,
            "url": cheapest_url,
            "all_urls": urls,
        }
    except Exception as exc:
        logger.exception("fetch_product_from_text failed: %s", exc)
        return {
            "name": product,
            "store": "غير متوفر",
            "price": 0.0,
            "url": "",
            "all_urls": {},
        }


def cleanup_expired_carts() -> None:
    cutoff = time.time() - CART_TTL_SECONDS
    with STATE_LOCK:
        expired = [
            cart_id
            for cart_id, cart in CARTS.items()
            if cart.get("created_at", 0) < cutoff
        ]
        for cart_id in expired:
            CARTS.pop(cart_id, None)


def create_cart(items: List[Dict[str, Any]]) -> Tuple[str, float]:
    cleanup_expired_carts()
    cart_id = uuid.uuid4().hex[:10]
    total = sum(float(item.get("price") or 0) for item in items)

    with STATE_LOCK:
        CARTS[cart_id] = {
            "products": items,
            "total": total,
            "created_at": time.time(),
        }

    return cart_id, total


def finalize_cart(
    from_number: str,
    bot_id: str,
    items: List[Dict[str, Any]],
) -> None:
    cart_id, total = create_cart(items)

    lines = []
    for item in items:
        name = item.get("name") or "منتج"
        store = item.get("store") or "غير متوفر"
        price = float(item.get("price") or 0)

        price_text = f"{price:.3f} د.ك" if price > 0 else "السعر غير متوفر"
        lines.append(f"• {name} — {price_text} ({store})")

    summary = "\n".join(lines)
    send_whatsapp_text(
        from_number,
        f"🛒 سلتك جاهزة:\n{summary}\n\n💰 الإجمالي المعروف: {total:.3f} د.ك",
        bot_id,
    )

    public_domain = normalize_public_domain(RAILWAY_PUBLIC_DOMAIN)
    cart_url = f"https://{public_domain}/cart/{cart_id}"
    send_whatsapp_cta(
        from_number,
        "افتح السلة وشاهد روابط الشراء المتوفرة 👇",
        cart_url,
        bot_id,
        "🛒 افتح السلة",
    )


# -----------------------------------------------------------------------------
# Webhook routes
# -----------------------------------------------------------------------------

@app.get("/webhook")
async def verify_webhook(request: Request) -> Response:
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == VERIFY_TOKEN
    ):
        return Response(
            content=params.get("hub.challenge", ""),
            media_type="text/plain",
        )
    return Response(content="fail", status_code=403)


@app.post("/webhook")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Dict[str, str]:
    try:
        data = await request.json()
        value = data["entry"][0]["changes"][0]["value"]
        messages = value.get("messages") or []

        if not messages:
            return {"status": "ok"}

        message = messages[0]
        message_id = message.get("id")

        with STATE_LOCK:
            if message_id and message_id in processed_ids:
                return {"status": "duplicate"}
            if message_id:
                processed_ids.append(message_id)

        bot_id = (
            (value.get("metadata") or {}).get("phone_number_id")
            or PHONE_NUMBER_ID
        )
        from_number = message.get("from", "")
        message_type = message.get("type")

        if message_type == "image":
            with STATE_LOCK:
                image_state = IMAGE_BUFFER[from_number]
                image_state["images"].append(message)
                image_state["time"] = time.time()
                image_state["bot_id"] = bot_id
                is_first_image = len(image_state["images"]) == 1

            if is_first_image:
                background_tasks.add_task(
                    process_image_buffer,
                    from_number,
                )

        elif message_type == "text":
            background_tasks.add_task(
                process_text_message,
                message,
                bot_id,
            )

        elif message_type == "location":
            background_tasks.add_task(
                process_location_message,
                message,
                bot_id,
            )

        else:
            logger.info("Unsupported WhatsApp message type: %s", message_type)

    except Exception as exc:
        logger.exception("Webhook processing error: %s", exc)

    return {"status": "ok"}


# -----------------------------------------------------------------------------
# Message processing
# -----------------------------------------------------------------------------

async def process_image_buffer(from_number: str) -> None:
    await asyncio.sleep(BUFFER_SECONDS)

    with STATE_LOCK:
        data = IMAGE_BUFFER.pop(from_number, None)

    if not data:
        return

    images = data.get("images") or []
    bot_id = data.get("bot_id") or PHONE_NUMBER_ID

    if len(images) == 1:
        await asyncio.to_thread(
            process_single_image,
            images[0],
            bot_id,
        )
    else:
        await asyncio.to_thread(
            process_multi_images,
            images,
            from_number,
            bot_id,
        )


def process_single_image(message: Dict[str, Any], bot_id: str) -> None:
    from_number = message.get("from", "")

    try:
        send_whatsapp_text(
            from_number,
            "ثواني بس.. أحدد طلبك وأدور لك أفضل الخيارات!",
            bot_id,
        )

        image = message.get("image") or {}
        encoded, mime_type = download_whatsapp_media(image.get("id", ""))

        text, urls = call_gemini(
            [
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": encoded,
                    }
                },
                {
                    "text": (
                        "ما هذا المنتج؟ حدده بدقة. إذا ظهر براند أو موديل واضح فابحث عن أرخص سعر لنفس المنتج في الكويت، وإلا فاختر أفضل الخيارات تقييماً والأفضل قيمة."
                    )
                },
            ]
        )

        if not text:
            text = "ما قدرت أحدد المنتج أو أجد سعر موثوق حالياً."

        send_whatsapp_text(from_number, text, bot_id)

        product_name = extract_product_name(text, "المنتج")
        remember_last_search(from_number, product_name)

        buttons_sent = send_store_buttons(from_number, urls, bot_id)
        logger.info("Single image store buttons sent: %s", buttons_sent)

        # Always offer the location flow, even when Gemini returns no links.
        send_nearby_location_prompt(from_number, bot_id)

    except Exception as exc:
        logger.exception("Single image processing failed: %s", exc)
        send_whatsapp_text(
            from_number,
            "صار خطأ أثناء قراءة الصورة. جرّب إرسالها مرة ثانية أو اكتب اسم المنتج.",
            bot_id,
        )


def process_multi_images(
    messages: List[Dict[str, Any]],
    from_number: str,
    bot_id: str,
) -> None:
    send_whatsapp_text(
        from_number,
        f"تمام، لقطت {len(messages)} منتجات. أجهز لك السلة...",
        bot_id,
    )

    items = list(WORKERS.map(fetch_product_from_image, messages))
    finalize_cart(from_number, bot_id, items)


def process_text_message(message: Dict[str, Any], bot_id: str) -> None:
    from_number = message.get("from", "")
    text_data = message.get("text") or {}
    user_text = (text_data.get("body") or "").strip()

    if not user_text:
        send_whatsapp_text(from_number, "اكتب اسم المنتج اللي تبيه.", bot_id)
        return

    products = extract_products(user_text)

    if len(products) == 1:
        product = products[0]
        send_whatsapp_text(
            from_number,
            f"🔍 أبحث لك عن أفضل خيار مناسب لـ {product}...",
            bot_id,
        )

        text, urls = call_gemini(
            [{"text": f"حلل الطلب أولاً: إذا كان محدداً ببراند أو موديل فابحث عن الأرخص لنفس المنتج، وإذا كان عاماً بلا براند فاختر الأفضل تقييماً والأفضل قيمة داخل الكويت. الطلب: {product}"}]
        )

        send_whatsapp_text(
            from_number,
            text or "ما لقيت سعراً موثوقاً حالياً.",
            bot_id,
        )

        detected_product = extract_product_name(text, product)
        remember_last_search(from_number, detected_product)

        buttons_sent = send_store_buttons(from_number, urls, bot_id)
        logger.info("Text search store buttons sent: %s", buttons_sent)

        # This is intentionally unconditional.
        send_nearby_location_prompt(from_number, bot_id)
        return

    remember_last_search(from_number, products[0])
    send_whatsapp_text(
        from_number,
        f"تمام، لقيت {len(products)} منتجات. أجهز لك السلة...",
        bot_id,
    )

    items = list(WORKERS.map(fetch_product_from_text, products))
    finalize_cart(from_number, bot_id, items)


def process_location_message(
    message: Dict[str, Any],
    bot_id: str,
) -> None:
    from_number = message.get("from", "")
    location = message.get("location") or {}
    latitude = location.get("latitude")
    longitude = location.get("longitude")

    if latitude is None or longitude is None:
        send_whatsapp_text(
            from_number,
            "ما قدرت أقرأ الموقع. أرسله مرة ثانية من زر Location.",
            bot_id,
        )
        return

    product = get_last_search(from_number)
    if not product:
        send_whatsapp_text(
            from_number,
            "ما عندي منتج محفوظ حالياً 😅. "
            "ابحث عن منتج أول، وبعدها دز موقعك.",
            bot_id,
        )
        return

    category_text, _ = call_gemini(
        [{"text": f"المنتج: {product}"}],
        system=MAP_CATEGORY_PROMPT,
        use_search=False,
        max_output_tokens=150,
    )

    category = re.sub(r"[\r\n]+", " ", category_text or product).strip()
    if not category:
        category = product

    safe_category = urllib.parse.quote(category, safe="")
    maps_url = (
        f"https://www.google.com/maps/search/{safe_category}/"
        f"@{latitude},{longitude},15z"
    )

    body = (
        f"📍 بحثك الأخير كان عن ({product})\n\n"
        "جهزت لك بحثاً عن أقرب الأماكن المناسبة حولك. "
        "اضغط الزر وافتح الخريطة 👇"
    )

    send_whatsapp_cta(
        from_number,
        body,
        maps_url,
        bot_id,
        "📍 افتح الخريطة",
    )


# -----------------------------------------------------------------------------
# Cart page and health check
# -----------------------------------------------------------------------------

def render_cart_item(item: Dict[str, Any]) -> str:
    name = html.escape(str(item.get("name") or "منتج"))
    store = html.escape(str(item.get("store") or "غير متوفر"))
    price = float(item.get("price") or 0)
    price_text = f"{price:.3f} د.ك" if price > 0 else "السعر غير متوفر"
    price_text = html.escape(price_text)

    raw_url = str(item.get("url") or "")
    if valid_http_url(raw_url):
        safe_url = html.escape(raw_url, quote=True)
        button = (
            f"<a href='{safe_url}' target='_blank' rel='noopener noreferrer' "
            "class='bg-black text-white px-4 py-2 rounded-lg whitespace-nowrap'>"
            "شراء</a>"
        )
    else:
        button = (
            "<span class='bg-gray-200 text-gray-500 px-4 py-2 "
            "rounded-lg whitespace-nowrap'>الرابط غير متوفر</span>"
        )

    return (
        "<div class='p-4 border-b flex items-center justify-between gap-4'>"
        f"<div><b>{name}</b><br>"
        f"<span class='text-sm text-gray-500'>{store} — {price_text}</span>"
        f"</div>{button}</div>"
    )


@app.get("/cart/{cart_id}", response_class=HTMLResponse)
async def cart_page(cart_id: str) -> HTMLResponse:
    cleanup_expired_carts()

    with STATE_LOCK:
        cart = CARTS.get(cart_id)

    if not cart:
        return HTMLResponse(
            "<html dir='rtl'><meta name='viewport' "
            "content='width=device-width,initial-scale=1'>"
            "<body style='font-family:Arial;padding:30px'>"
            "<h2>السلة انتهت أو غير موجودة</h2></body></html>",
            status_code=404,
        )

    rows = "".join(render_cart_item(item) for item in cart["products"])
    total = float(cart.get("total") or 0)

    page = f"""
    <!doctype html>
    <html lang="ar" dir="rtl">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>سلتك</title>
        <script src="https://cdn.tailwindcss.com"></script>
      </head>
      <body class="bg-gray-100 min-h-screen">
        <main class="max-w-lg mx-auto bg-white min-h-screen shadow-sm">
          <header class="p-5 bg-black text-white">
            <h1 class="text-2xl font-bold">🛒 سلتك</h1>
            <p class="text-sm text-gray-300 mt-1">
              الإجمالي المعروف: {total:.3f} د.ك
            </p>
          </header>
          {rows}
        </main>
      </body>
    </html>
    """
    return HTMLResponse(page)


@app.get("/")
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "version": "v13",
        "gemini_model": GEMINI_MODEL,
        "graph_version": WHATSAPP_GRAPH_VERSION,
    }

