# -*- coding: utf-8 -*-
"""
WhatsApp Kuwait shopping bot
- Identifies a product from text or image.
- Uses Gemini + Google Search grounding.
- Verifies the price from the actual product page before showing it.
- Sends CTA buttons that open the direct product page only.
- Uses pooled HTTP connections, parallel verification, and TTL caching.

No extra dependency is required beyond the packages already used by the old file:
fastapi, requests, uvicorn.
"""

import asyncio
import base64
import hashlib
import html as html_lib
import json
import os
import re
import threading
import time
import uuid
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from fastapi import BackgroundTasks, FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from requests.adapters import HTTPAdapter

app = FastAPI()

# =============================
# Environment
# =============================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
# Stable Gemini 3 model: structured JSON + Google Search + low-latency thinking.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash").strip()
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "").strip()
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "").strip()
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_SECRET_COOP_BOT_TOKEN").strip()
GRAPH_VERSION = os.environ.get("GRAPH_VERSION", "v20.0").strip()
PUBLIC_DOMAIN = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "fanzia.up.railway.app").strip()

GRAPH_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

BUFFER_SECONDS = float(os.environ.get("IMAGE_BUFFER_SECONDS", "1.8"))
CACHE_TTL = int(os.environ.get("CACHE_TTL_SECONDS", str(3 * 3600)))
CART_TTL = int(os.environ.get("CART_TTL_SECONDS", str(24 * 3600)))
MAX_PRODUCTS = int(os.environ.get("MAX_PRODUCTS", "6"))
MAX_OFFERS = int(os.environ.get("MAX_OFFERS", "3"))
MAX_GROUNDING_URLS = int(os.environ.get("MAX_GROUNDING_URLS", "12"))

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)

# =============================
# Shared state
# =============================
processed_ids: deque = deque(maxlen=5000)
processed_lock = threading.Lock()

IMAGE_BUFFER: Dict[str, Dict[str, Any]] = defaultdict(
    lambda: {"images": [], "time": 0.0, "bot_id": ""}
)
image_buffer_lock = threading.Lock()

CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
cache_lock = threading.Lock()

CARTS: Dict[str, Dict[str, Any]] = {}
cart_lock = threading.Lock()

VERIFY_POOL = ThreadPoolExecutor(max_workers=10)
PRODUCT_POOL = ThreadPoolExecutor(max_workers=5)

_thread_local = threading.local()


def http_session() -> requests.Session:
    """One pooled Session per worker thread."""
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=1)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "ar-KW,ar;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )
        _thread_local.session = session
    return session


# =============================
# Prompt and schema
# =============================
SYSTEM_PROMPT = """
أنت محرك مقارنة أسعار للمتسوق في الكويت.

المطلوب:
1) حدد المنتج والنسخة بدقة شديدة: الشركة، الموديل، السعة/الحجم/الوزن/اللون إن كان ظاهراً.
2) ابحث في المتاجر الكويتية عن نفس النسخة بالضبط.
3) أعد حتى 8 عروض مرشحة كي يتحقق السيرفر منها لاحقاً.

قواعد صارمة:
- لا تخمن أي سعر.
- رابط كل عرض يجب أن يكون رابط صفحة المنتج نفسها، وليس الصفحة الرئيسية أو صفحة بحث أو تصنيف.
- السعر يجب أن يكون سعر الشراء الكامل بالدينار الكويتي، وليس قسطاً شهرياً أو دفعة أولى.
- لا تستخدم سعراً مشروطاً بكوبون غير متاح للجميع.
- طابق السعة والوزن والحجم والعدد والجيل والموديل بدقة. مثال: 128GB ليس 256GB، و2.5kg ليس 6kg.
- لا تذكر العرض إذا كان المنتج مختلفاً أو السعر غير ظاهر.
- أعط أولوية للمتاجر المحلية الكويتية. استخدم مواقع الشحن الدولي فقط إذا لم يوجد عرض محلي.
- لا تكتب شرحاً خارج JSON المطلوب.
""".strip()

RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "product_name_ar": {
            "type": "string",
            "description": "اسم المنتج بالعربية مع النسخة أو الحجم إن أمكن.",
        },
        "product_name_en": {
            "type": "string",
            "description": "الاسم الإنجليزي الرسمي الدقيق للموديل والنسخة.",
        },
        "variant": {
            "type": "string",
            "description": "السعة أو اللون أو الوزن أو رقم الموديل الذي يجب مطابقته.",
        },
        "offers": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "properties": {
                    "store": {"type": "string"},
                    "price_kd": {
                        "type": "number",
                        "minimum": 0.001,
                        "description": "سعر الشراء الكامل بالدينار الكويتي.",
                    },
                    "product_url": {
                        "type": "string",
                        "description": "رابط HTTPS مباشر لصفحة المنتج نفسها.",
                    },
                    "availability": {
                        "type": "string",
                        "enum": ["in_stock", "unknown", "out_of_stock"],
                    },
                },
                "required": ["store", "price_kd", "product_url", "availability"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["product_name_ar", "product_name_en", "variant", "offers"],
    "additionalProperties": False,
}


# =============================
# General helpers
# =============================
def safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if 0 < number < 1_000_000 else None

    text = html_lib.unescape(str(value)).strip()
    text = re.sub(r"[^0-9,.-]", "", text)
    if not text:
        return None

    # Handle 1,075.000 and 1.075,000 safely enough for Kuwait product prices.
    if "," in text and "." in text:
        if text.rfind(".") > text.rfind(","):
            text = text.replace(",", "")
        else:
            text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        right = text.split(",")[-1]
        if len(right) in (1, 2, 3):
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")

    try:
        number = float(text)
        return number if 0 < number < 1_000_000 else None
    except ValueError:
        return None


def format_kd(price: float) -> str:
    # Kuwait prices commonly use three decimal places; trim only unnecessary zeros.
    value = f"{price:,.3f}"
    return value.rstrip("0").rstrip(".")


def normalize_url(url: str) -> str:
    url = html_lib.unescape((url or "").strip())
    url = url.replace("\\/", "/")
    if not url.startswith(("http://", "https://")):
        return ""
    return url[:1500]


def domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().split(":")[0].removeprefix("www.")
    except Exception:
        return ""


def domain_key(url_or_domain: str) -> str:
    dom = domain_of(url_or_domain) if "://" in url_or_domain else url_or_domain.lower()
    dom = dom.removeprefix("www.")
    return dom.split(".")[0]


STORE_NAMES = {
    "xcite.com": "إكسايت",
    "blink.com.kw": "بلينك",
    "eureka.com.kw": "يوريكا",
    "best.com.kw": "بست اليوسفي",
    "alghanim.com": "الغانم",
    "luluwebstore.com": "لولو",
    "carrefourkuwait.com": "كارفور",
    "taw9eel.com": "توصيل",
    "boutiqaat.com": "بوتيكات",
    "dabdoob.com": "دبدوب",
    "noon.com": "نون",
    "amazon.ae": "أمازون الإمارات",
    "ubuy.com.kw": "يو باي",
}


def store_name_from_url(url: str, fallback: str = "") -> str:
    dom = domain_of(url)
    for known_domain, name in STORE_NAMES.items():
        if dom == known_domain or dom.endswith("." + known_domain):
            return name
    if fallback.strip():
        return fallback.strip()[:40]
    return (dom.split(".")[0].replace("-", " ").title() or "متجر")[:40]


def is_local_store(url: str) -> bool:
    dom = domain_of(url)
    if dom.endswith(".kw") or dom.endswith(".com.kw"):
        return True
    local_known = {
        "xcite.com",
        "alghanim.com",
        "luluwebstore.com",
        "carrefourkuwait.com",
        "taw9eel.com",
        "boutiqaat.com",
        "dabdoob.com",
    }
    return any(dom == item or dom.endswith("." + item) for item in local_known)


def is_search_or_category_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        path = parsed.path.strip("/").lower()
        query = parsed.query.lower()
        if not path:
            return True
        blocked_paths = {
            "ar",
            "en",
            "home",
            "shop",
            "store",
            "products",
            "category",
            "categories",
            "search",
            "ar/home",
            "en/home",
            "index.html",
            "index.php",
        }
        if path in blocked_paths:
            return True
        if re.search(r"(^|/)(search|category|categories|collections)(/|$)", path):
            return True
        if any(k in query for k in ("q=", "query=", "search=", "keyword=")):
            return True
        return False
    except Exception:
        return True


def cache_key(parts: List[Dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for part in parts:
        if "text" in part:
            digest.update(part["text"].encode("utf-8", errors="ignore"))
        inline = part.get("inline_data") or part.get("inlineData")
        if inline and inline.get("data"):
            raw = inline["data"]
            digest.update(str(len(raw)).encode())
            # JPEG headers are similar; hash both beginning and end for a safer fast key.
            digest.update(raw[:65536].encode())
            digest.update(raw[-65536:].encode())
    digest.update(GEMINI_MODEL.encode())
    return digest.hexdigest()


def cache_get(key: str) -> Optional[Dict[str, Any]]:
    now = time.time()
    with cache_lock:
        item = CACHE.get(key)
        if item and now - item[0] < CACHE_TTL:
            return item[1]
        CACHE.pop(key, None)
    return None


def cache_set(key: str, result: Dict[str, Any]) -> None:
    with cache_lock:
        if len(CACHE) >= 750:
            oldest = min(CACHE, key=lambda item_key: CACHE[item_key][0])
            CACHE.pop(oldest, None)
        CACHE[key] = (time.time(), result)


def parse_json_response(text: str) -> Dict[str, Any]:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if not match:
            return {}
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}


# =============================
# Gemini search
# =============================
def _gemini_payload(parts: List[Dict[str, Any]], structured: bool = True) -> Dict[str, Any]:
    generation_config: Dict[str, Any] = {
        "thinkingConfig": {"thinkingLevel": "MINIMAL"},
        "maxOutputTokens": 1800,
    }
    if structured:
        generation_config["responseFormat"] = {
            "text": {"mimeType": "application/json", "schema": RESPONSE_SCHEMA}
        }

    return {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": parts}],
        "tools": [{"googleSearch": {}}],
        "generationConfig": generation_config,
    }


def gemini_search(parts: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[str]]:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing")

    session = http_session()
    headers = {"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"}

    response = session.post(
        GEMINI_URL,
        json=_gemini_payload(parts, structured=True),
        headers=headers,
        timeout=(5, 45),
    )

    # Compatibility fallback if a non-Gemini-3 model is selected in the environment.
    if response.status_code == 400:
        fallback_parts = list(parts) + [
            {
                "text": (
                    "أعد النتيجة JSON فقط بالمفاتيح product_name_ar, product_name_en, "
                    "variant, offers. وكل offer يحتوي store, price_kd, product_url, availability."
                )
            }
        ]
        response = session.post(
            GEMINI_URL,
            json=_gemini_payload(fallback_parts, structured=False),
            headers=headers,
            timeout=(5, 45),
        )

    response.raise_for_status()
    data = response.json()
    candidates = data.get("candidates") or []
    if not candidates:
        return {}, []

    candidate = candidates[0]
    text = "".join(
        part.get("text", "")
        for part in candidate.get("content", {}).get("parts", [])
        if isinstance(part, dict)
    ).strip()
    result = parse_json_response(text)

    grounding = candidate.get("groundingMetadata", {}) or {}
    grounding_urls: List[str] = []
    for chunk in grounding.get("groundingChunks", []) or []:
        url = normalize_url((chunk.get("web") or {}).get("uri", ""))
        if url:
            grounding_urls.append(url)

    return result, grounding_urls[:MAX_GROUNDING_URLS]


# =============================
# Direct URL and page verification
# =============================
def resolve_final_url(url: str) -> str:
    url = normalize_url(url)
    if not url:
        return ""

    try:
        session = http_session()
        response = session.head(url, allow_redirects=True, timeout=(3, 7))
        if response.status_code in (403, 405) or response.status_code >= 500:
            response = session.get(
                url,
                allow_redirects=True,
                timeout=(3, 8),
                stream=True,
            )
            final = response.url
            response.close()
        else:
            final = response.url

        final = normalize_url(final)
        if not final:
            return ""
        if any(
            bad in final.lower()
            for bad in (
                "vertexaisearch",
                "grounding-api-redirect",
                "google.com/search",
                "duckduckgo.com",
            )
        ):
            return ""
        return final
    except requests.RequestException:
        return ""


def fetch_page(url: str) -> Tuple[str, str, int]:
    try:
        response = http_session().get(
            url,
            allow_redirects=True,
            timeout=(3, 9),
            headers={"Accept": "text/html,application/xhtml+xml"},
        )
        final_url = normalize_url(response.url)
        status = response.status_code
        content_type = response.headers.get("Content-Type", "").lower()
        if status >= 400 or "text/html" not in content_type:
            return final_url, "", status
        # Limit parsing work and memory; product metadata is normally near the top.
        return final_url, response.text[:2_500_000], status
    except requests.RequestException:
        return "", "", 0


def strip_tags(value: str) -> str:
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html_lib.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def meta_content(page_html: str, key: str) -> str:
    escaped = re.escape(key)
    patterns = [
        rf'<meta[^>]+(?:property|name|itemprop)=["\']{escaped}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name|itemprop)=["\']{escaped}["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, page_html, flags=re.I)
        if match:
            return html_lib.unescape(match.group(1)).strip()
    return ""


def walk_json(value: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


def jsonld_objects(page_html: str) -> Iterable[Dict[str, Any]]:
    scripts = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        page_html,
        flags=re.I | re.S,
    )
    for raw in scripts[:30]:
        raw = html_lib.unescape(raw).strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            # Common trailing-comma cleanup.
            cleaned = re.sub(r",\s*([}\]])", r"\1", raw)
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError:
                continue
        yield from walk_json(parsed)


def availability_value(raw: Any) -> str:
    text = str(raw or "").lower()
    if any(item in text for item in ("outofstock", "out_of_stock", "soldout", "sold out")):
        return "out_of_stock"
    if any(item in text for item in ("instock", "in_stock", "in stock", "limitedavailability")):
        return "in_stock"
    return "unknown"


def extract_structured_product(page_html: str) -> Dict[str, Any]:
    best: Dict[str, Any] = {
        "title": "",
        "price": None,
        "currency": "",
        "availability": "unknown",
        "is_product": False,
    }

    for obj in jsonld_objects(page_html):
        obj_type = obj.get("@type", "")
        types = obj_type if isinstance(obj_type, list) else [obj_type]
        lower_types = {str(item).lower() for item in types}
        if "product" in lower_types:
            best["is_product"] = True
            if not best["title"]:
                best["title"] = str(obj.get("name") or "").strip()

            offers = obj.get("offers")
            offer_list = offers if isinstance(offers, list) else [offers]
            for offer in offer_list:
                if not isinstance(offer, dict):
                    continue
                price = safe_float(
                    offer.get("price")
                    or offer.get("lowPrice")
                    or (offer.get("priceSpecification") or {}).get("price")
                )
                currency = str(
                    offer.get("priceCurrency")
                    or (offer.get("priceSpecification") or {}).get("priceCurrency")
                    or ""
                ).upper()
                availability = availability_value(offer.get("availability"))
                if price and (currency in ("", "KWD", "KD")):
                    # Prefer an available offer over an unavailable one.
                    if best["price"] is None or (
                        best["availability"] == "out_of_stock"
                        and availability != "out_of_stock"
                    ):
                        best["price"] = price
                        best["currency"] = currency or "KWD"
                        best["availability"] = availability

        # Some shops expose Offer objects outside Product.
        if "offer" in lower_types or "aggregateoffer" in lower_types:
            price = safe_float(
                obj.get("price")
                or obj.get("lowPrice")
                or (obj.get("priceSpecification") or {}).get("price")
            )
            currency = str(
                obj.get("priceCurrency")
                or (obj.get("priceSpecification") or {}).get("priceCurrency")
                or ""
            ).upper()
            if price and currency in ("KWD", "KD") and best["price"] is None:
                best["price"] = price
                best["currency"] = "KWD"
                best["availability"] = availability_value(obj.get("availability"))

    return best


def extract_kwd_prices(page_html: str) -> List[float]:
    """Fallback: prices explicitly adjacent to KWD/KD/د.ك only."""
    text = strip_tags(page_html[:1_500_000])
    patterns = [
        r"(?:KWD|KD)\s*([0-9][0-9,.]{0,15})",
        r"([0-9][0-9,.]{0,15})\s*(?:KWD|KD)",
        r"([0-9][0-9,.]{0,15})\s*د\s*\.?\s*ك",
        r"د\s*\.?\s*ك\s*([0-9][0-9,.]{0,15})",
    ]
    output: List[float] = []
    for pattern in patterns:
        for raw in re.findall(pattern, text, flags=re.I)[:80]:
            price = safe_float(raw)
            if price and price not in output:
                output.append(price)
    return output


def extract_page_info(page_html: str) -> Dict[str, Any]:
    structured = extract_structured_product(page_html)

    title = (
        structured.get("title")
        or meta_content(page_html, "og:title")
        or meta_content(page_html, "twitter:title")
    )
    if not title:
        match = re.search(r"<title[^>]*>(.*?)</title>", page_html, flags=re.I | re.S)
        title = strip_tags(match.group(1)) if match else ""

    price = structured.get("price")
    currency = str(structured.get("currency") or "").upper()

    if price is None:
        for price_key, currency_key in (
            ("product:price:amount", "product:price:currency"),
            ("og:price:amount", "og:price:currency"),
            ("price", "priceCurrency"),
        ):
            raw_price = meta_content(page_html, price_key)
            raw_currency = meta_content(page_html, currency_key).upper()
            parsed_price = safe_float(raw_price)
            if parsed_price and raw_currency in ("", "KWD", "KD"):
                price = parsed_price
                currency = raw_currency or "KWD"
                break

    return {
        "title": title[:300],
        "price": price,
        "currency": currency,
        "availability": structured.get("availability", "unknown"),
        "is_product": bool(structured.get("is_product")),
        "fallback_prices": extract_kwd_prices(page_html) if price is None else [],
    }


STOP_TOKENS = {
    "the",
    "and",
    "with",
    "for",
    "new",
    "original",
    "official",
    "product",
    "kuwait",
    "online",
    "buy",
    "shop",
}


def tokens(text: str) -> List[str]:
    values = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [value for value in values if value not in STOP_TOKENS and len(value) > 1]


def critical_tokens(product_name: str, variant: str) -> List[str]:
    combined = f"{product_name} {variant}".lower()
    critical: List[str] = []
    # Model codes containing both letters and digits: A55, WH-1000XM5, S24.
    for token in re.findall(r"[a-z0-9-]+", combined):
        if re.search(r"[a-z]", token) and re.search(r"\d", token):
            critical.append(token.replace("-", ""))
    # Capacity / size / weight variants.
    for number, unit in re.findall(
        r"(\d+(?:\.\d+)?)\s*(gb|tb|mb|kg|g|mg|ml|l|inch|in|cm|mm|pack|pcs)",
        combined,
    ):
        critical.extend([number.replace(".", ""), unit])
    return list(dict.fromkeys(critical))


def product_matches(product_name: str, variant: str, page_title: str, url: str) -> bool:
    query_tokens = set(tokens(f"{product_name} {variant}"))
    haystack = f"{page_title} {url}".lower().replace("-", "")
    page_tokens = set(tokens(haystack))

    if not query_tokens:
        return True

    overlap = len(query_tokens & page_tokens) / max(1, min(len(query_tokens), 8))
    required = critical_tokens(product_name, variant)
    if required and any(token not in haystack for token in required):
        return False

    # Strong model/variant match can compensate for a short shop title.
    if required and all(token in haystack for token in required):
        return overlap >= 0.25
    return overlap >= 0.40


def closest_price(target: Optional[float], prices: List[float]) -> Optional[float]:
    if not prices:
        return None
    if target is None:
        return min(prices)
    candidate = min(prices, key=lambda value: abs(value - target))
    tolerance = max(0.005, target * 0.001)
    return candidate if abs(candidate - target) <= tolerance else None


def validate_offer(
    candidate: Dict[str, Any], product_name: str, variant: str
) -> Optional[Dict[str, Any]]:
    raw_url = normalize_url(str(candidate.get("product_url") or candidate.get("url") or ""))
    if not raw_url:
        return None

    resolved = resolve_final_url(raw_url)
    if not resolved:
        return None

    final_url, page_html, status = fetch_page(resolved)
    if status >= 400 or not page_html or not final_url:
        return None

    info = extract_page_info(page_html)
    # Product JSON-LD is the strongest signal; otherwise reject clear search/category pages.
    if not info["is_product"] and is_search_or_category_url(final_url):
        return None

    if not product_matches(product_name, variant, info["title"], final_url):
        return None

    model_price = safe_float(candidate.get("price_kd"))
    page_price = safe_float(info.get("price"))
    if page_price is None:
        page_price = closest_price(model_price, info.get("fallback_prices", []))

    # The server shows a price only when the actual product page confirms it.
    if page_price is None:
        return None

    currency = str(info.get("currency") or "KWD").upper()
    if currency not in ("KWD", "KD", ""):
        return None

    availability = info.get("availability", "unknown")
    if availability == "out_of_stock" or candidate.get("availability") == "out_of_stock":
        return None

    return {
        "store": store_name_from_url(final_url, str(candidate.get("store") or "")),
        "price": round(page_price, 3),
        "url": final_url,
        "title": info.get("title") or product_name,
        "local": is_local_store(final_url),
    }


def dedupe_offers(offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    seen_urls = set()
    seen_store_price = set()
    for offer in sorted(offers, key=lambda item: item["price"]):
        canonical = re.sub(r"[?#].*$", "", offer["url"]).rstrip("/").lower()
        store_price = (domain_of(offer["url"]), round(offer["price"], 3))
        if canonical in seen_urls or store_price in seen_store_price:
            continue
        seen_urls.add(canonical)
        seen_store_price.add(store_price)
        output.append(offer)
    return output


def build_result(parts: List[Dict[str, Any]], use_cache: bool = True) -> Dict[str, Any]:
    key = cache_key(parts)
    if use_cache:
        cached = cache_get(key)
        if cached:
            return cached

    raw, grounding_urls = gemini_search(parts)
    product_ar = str(raw.get("product_name_ar") or "المنتج").strip()
    product_en = str(raw.get("product_name_en") or product_ar).strip()
    variant = str(raw.get("variant") or "").strip()

    candidates: List[Dict[str, Any]] = []
    for offer in raw.get("offers") or []:
        if not isinstance(offer, dict):
            continue
        url = normalize_url(str(offer.get("product_url") or ""))
        if url:
            candidates.append({**offer, "product_url": url})

    # Grounding pages are also verified. They can rescue a direct shop URL even if
    # the model did not include it in the JSON offers list.
    known_urls = {item["product_url"] for item in candidates}
    for url in grounding_urls:
        if url not in known_urls:
            candidates.append(
                {
                    "store": "",
                    "price_kd": None,
                    "product_url": url,
                    "availability": "unknown",
                }
            )
            known_urls.add(url)

    # Keep verification bounded for predictable latency.
    candidates = candidates[:16]
    verified = list(
        VERIFY_POOL.map(
            lambda item: validate_offer(item, product_en, variant),
            candidates,
        )
    )
    offers = dedupe_offers([item for item in verified if item])

    # Local Kuwait stores first. If local offers exist, foreign shipping sites are omitted.
    local_offers = [item for item in offers if item["local"]]
    if local_offers:
        offers = local_offers
    offers = sorted(offers, key=lambda item: item["price"])[:MAX_OFFERS]

    result = {
        "product_name_ar": product_ar,
        "product_name_en": product_en,
        "variant": variant,
        "offers": offers,
    }
    if offers:
        cache_set(key, result)
    return result


def format_result(result: Dict[str, Any]) -> str:
    product_ar = result.get("product_name_ar") or "المنتج"
    product_en = result.get("product_name_en") or ""
    title = f"📦 {product_ar}"
    if product_en and product_en.lower() != str(product_ar).lower():
        title += f" ({product_en})"

    offers = result.get("offers") or []
    if not offers:
        return (
            f"{title}\n"
            "ما لقيت حالياً سعراً مؤكداً مع رابط مباشر لنفس المنتج. "
            "ما راح أعطيك سعراً تخمينياً أو رابط بحث عام."
        )

    lines = [title]
    for index, offer in enumerate(offers):
        marker = "✅" if index == 0 else "•"
        lines.append(f"{marker} {offer['store']} — {format_kd(offer['price'])} د.ك")
    lines.append("🔎 الأسعار مأخوذة من صفحات المنتجات مباشرة وقت البحث.")
    return "\n".join(lines)


# =============================
# WhatsApp helpers
# =============================
def download_whatsapp_media(media_id: str) -> Tuple[str, str]:
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    session = http_session()
    meta = session.get(
        f"{GRAPH_URL}/{media_id}", headers=headers, timeout=(4, 15)
    )
    meta.raise_for_status()
    meta_data = meta.json()
    media_url = meta_data.get("url")
    if not media_url:
        raise RuntimeError("WhatsApp media URL is missing")

    image = session.get(media_url, headers=headers, timeout=(4, 25))
    image.raise_for_status()
    mime_type = meta_data.get("mime_type") or image.headers.get("Content-Type") or "image/jpeg"
    return base64.b64encode(image.content).decode("ascii"), mime_type


def send_whatsapp_text(to: str, text: str, bot_id: str) -> bool:
    if not text:
        return False
    url = f"{GRAPH_URL}/{bot_id}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text[:3900]},
    }
    try:
        response = http_session().post(
            url, json=payload, headers=headers, timeout=(4, 12)
        )
        if response.status_code >= 400:
            print("WhatsApp text error", response.status_code, response.text[:500])
            return False
        return True
    except requests.RequestException as exc:
        print("WhatsApp text exception", exc)
        return False


def send_whatsapp_cta(
    to: str, body: str, link: str, bot_id: str, title: str
) -> bool:
    link = normalize_url(link)
    if not link:
        return False
    url = f"{GRAPH_URL}/{bot_id}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": body[:1024]},
            "action": {
                "name": "cta_url",
                "parameters": {
                    "display_text": title[:20],
                    "url": link,
                },
            },
        },
    }
    try:
        response = http_session().post(
            url, json=payload, headers=headers, timeout=(4, 12)
        )
        if response.status_code >= 400:
            print("WhatsApp CTA error", response.status_code, response.text[:500])
            return False
        return True
    except requests.RequestException as exc:
        print("WhatsApp CTA exception", exc)
        return False


def send_result(to: str, bot_id: str, result: Dict[str, Any]) -> None:
    send_whatsapp_text(to, format_result(result), bot_id)
    for offer in result.get("offers") or []:
        store = offer["store"]
        send_whatsapp_cta(
            to,
            f"{store} — {format_kd(offer['price'])} د.ك 👇",
            offer["url"],
            bot_id,
            f"شراء من {store}"[:20],
        )


# =============================
# Message processing
# =============================
def extract_products(text: str) -> List[str]:
    cleaned = re.sub(r"^[•\-*\d.\)\s]+", "", text or "", flags=re.M).strip()
    if not cleaned:
        return []

    # Do not split on the Arabic word "و"; it is often part of a product name.
    parts = re.split(r"\s*(?:\n+|[;,،]+|\s+\+\s+)\s*", cleaned)
    parts = [part.strip() for part in parts if len(part.strip()) > 2]
    return parts[:MAX_PRODUCTS] if parts else [cleaned]


def text_parts(product: str) -> List[Dict[str, Any]]:
    return [
        {
            "text": (
                f"ابحث الآن عن هذا المنتج في الكويت: {product}\n"
                "طابق النسخة بدقة وأعد أرخص الروابط المباشرة المتاحة."
            )
        }
    ]


def image_parts(image_b64: str, mime_type: str) -> List[Dict[str, Any]]:
    return [
        {"inline_data": {"mime_type": mime_type, "data": image_b64}},
        {
            "text": (
                "حدد المنتج الظاهر في الصورة بالاسم والموديل والنسخة بدقة، "
                "ثم ابحث عن أرخص سعر متاح في الكويت بروابط صفحات المنتج المباشرة."
            )
        },
    ]


def process_single_image(message: Dict[str, Any], bot_id: str) -> None:
    from_number = message["from"]
    send_whatsapp_text(from_number, "🔍 أحدد المنتج وأتحقق من الأسعار...", bot_id)
    try:
        image_b64, mime_type = download_whatsapp_media(message["image"]["id"])
        result = build_result(image_parts(image_b64, mime_type))
        send_result(from_number, bot_id, result)
    except Exception as exc:
        print("single image error", exc)
        send_whatsapp_text(
            from_number,
            "ما قدرت أقرأ الصورة أو أتحقق من السعر حالياً. جرّب صورة أوضح أو اكتب اسم المنتج.",
            bot_id,
        )


def cheapest_item(result: Dict[str, Any], fallback_name: str) -> Dict[str, Any]:
    offers = result.get("offers") or []
    if not offers:
        return {
            "name": result.get("product_name_ar") or fallback_name,
            "store": "غير متوفر",
            "price": 0.0,
            "url": "",
        }
    best = offers[0]
    return {
        "name": result.get("product_name_ar") or fallback_name,
        "store": best["store"],
        "price": best["price"],
        "url": best["url"],
    }


def fetch_product_from_image(message: Dict[str, Any]) -> Dict[str, Any]:
    try:
        image_b64, mime_type = download_whatsapp_media(message["image"]["id"])
        result = build_result(image_parts(image_b64, mime_type))
        return cheapest_item(result, "منتج")
    except Exception as exc:
        print("multi image item error", exc)
        return {"name": "منتج", "store": "غير متوفر", "price": 0.0, "url": ""}


def fetch_product_from_text(product: str) -> Dict[str, Any]:
    try:
        result = build_result(text_parts(product))
        return cheapest_item(result, product)
    except Exception as exc:
        print("multi text item error", exc)
        return {"name": product, "store": "غير متوفر", "price": 0.0, "url": ""}


def cleanup_carts() -> None:
    now = time.time()
    with cart_lock:
        expired = [
            cart_id
            for cart_id, cart in CARTS.items()
            if now - cart.get("created_at", now) > CART_TTL
        ]
        for cart_id in expired:
            CARTS.pop(cart_id, None)


def finalize_cart(from_number: str, bot_id: str, items: List[Dict[str, Any]]) -> None:
    cleanup_carts()
    valid_items = [item for item in items if item.get("price", 0) > 0 and item.get("url")]
    missing_items = [item for item in items if item not in valid_items]

    if not valid_items:
        send_whatsapp_text(
            from_number,
            "ما لقيت أسعاراً مؤكدة بروابط منتجات مباشرة للمنتجات المرسلة.",
            bot_id,
        )
        return

    total = round(sum(float(item["price"]) for item in valid_items), 3)
    cart_id = uuid.uuid4().hex[:10]
    with cart_lock:
        CARTS[cart_id] = {
            "products": valid_items,
            "total": total,
            "created_at": time.time(),
        }

    summary_lines = [
        f"• {item['name']} — {format_kd(item['price'])} د.ك ({item['store']})"
        for item in valid_items
    ]
    if missing_items:
        summary_lines.append(f"⚠️ لم أجد سعراً مؤكداً لـ {len(missing_items)} منتج.")

    send_whatsapp_text(
        from_number,
        "🛒 سلتك جاهزة:\n"
        + "\n".join(summary_lines)
        + f"\n\n💰 الإجمالي: {format_kd(total)} د.ك",
        bot_id,
    )
    send_whatsapp_cta(
        from_number,
        "افتح السلة وروح مباشرة لصفحات المنتجات",
        f"https://{PUBLIC_DOMAIN}/cart/{cart_id}",
        bot_id,
        "🛒 افتح السلة",
    )


def process_multi_images(
    messages: List[Dict[str, Any]], from_number: str, bot_id: str
) -> None:
    send_whatsapp_text(
        from_number,
        f"🔍 أتحقق من {len(messages)} منتجات بالتوازي...",
        bot_id,
    )
    items = list(PRODUCT_POOL.map(fetch_product_from_image, messages))
    finalize_cart(from_number, bot_id, items)


def process_text_message(message: Dict[str, Any], bot_id: str) -> None:
    from_number = message["from"]
    user_text = message.get("text", {}).get("body", "")
    products = extract_products(user_text)
    if not products:
        return

    if len(products) == 1:
        send_whatsapp_text(from_number, f"🔍 أتحقق من سعر {products[0]}...", bot_id)
        try:
            result = build_result(text_parts(products[0]))
            send_result(from_number, bot_id, result)
        except Exception as exc:
            print("text search error", exc)
            send_whatsapp_text(
                from_number,
                "صار خطأ أثناء البحث. جرّب كتابة اسم المنتج والموديل بشكل أدق.",
                bot_id,
            )
    else:
        send_whatsapp_text(
            from_number,
            f"🔍 أتحقق من {len(products)} منتجات بالتوازي...",
            bot_id,
        )
        items = list(PRODUCT_POOL.map(fetch_product_from_text, products))
        finalize_cart(from_number, bot_id, items)


async def process_image_buffer(from_number: str) -> None:
    await asyncio.sleep(BUFFER_SECONDS)
    with image_buffer_lock:
        data = IMAGE_BUFFER.pop(from_number, None)
    if not data:
        return

    images = data["images"]
    bot_id = data["bot_id"]
    if len(images) == 1:
        await asyncio.to_thread(process_single_image, images[0], bot_id)
    else:
        await asyncio.to_thread(process_multi_images, images, from_number, bot_id)


# =============================
# FastAPI routes
# =============================
@app.get("/webhook")
async def verify(request: Request) -> Response:
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == VERIFY_TOKEN
    ):
        return Response(
            content=params.get("hub.challenge", ""), media_type="text/plain"
        )
    return Response("fail", status_code=403)


@app.post("/webhook")
async def receive(request: Request, background_tasks: BackgroundTasks) -> Dict[str, str]:
    data = await request.json()
    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                bot_id = value.get("metadata", {}).get("phone_number_id") or PHONE_NUMBER_ID

                for message in value.get("messages", []):
                    message_id = message.get("id")
                    if not message_id:
                        continue
                    with processed_lock:
                        if message_id in processed_ids:
                            continue
                        processed_ids.append(message_id)

                    from_number = message.get("from", "")
                    message_type = message.get("type")
                    if message_type == "image":
                        with image_buffer_lock:
                            buffer = IMAGE_BUFFER[from_number]
                            buffer["images"].append(message)
                            buffer["time"] = time.time()
                            buffer["bot_id"] = bot_id
                            first_image = len(buffer["images"]) == 1
                        if first_image:
                            background_tasks.add_task(process_image_buffer, from_number)
                    elif message_type == "text":
                        background_tasks.add_task(process_text_message, message, bot_id)
    except Exception as exc:
        print("webhook error", exc)

    return {"status": "ok"}


@app.get("/cart/{cart_id}", response_class=HTMLResponse)
async def cart_page(cart_id: str) -> HTMLResponse:
    cleanup_carts()
    with cart_lock:
        cart = CARTS.get(cart_id)
    if not cart:
        return HTMLResponse("<h1>السلة انتهت أو غير موجودة</h1>", status_code=404)

    rows = []
    for item in cart["products"]:
        name = html_lib.escape(str(item["name"]))
        store = html_lib.escape(str(item["store"]))
        price = html_lib.escape(format_kd(float(item["price"])))
        url = html_lib.escape(str(item["url"]), quote=True)
        rows.append(
            "<div class='p-4 border-b flex items-center justify-between gap-3'>"
            f"<div><b>{name}</b><br>"
            f"<span class='text-sm text-gray-500'>{store} — {price} د.ك</span></div>"
            f"<a href='{url}' target='_blank' rel='noopener noreferrer' "
            "class='bg-black text-white px-4 py-2 rounded-lg whitespace-nowrap'>شراء</a>"
            "</div>"
        )

    total = html_lib.escape(format_kd(float(cart["total"])))
    page = f"""
    <!doctype html>
    <html lang="ar" dir="rtl">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>سلتك</title>
        <script src="https://cdn.tailwindcss.com"></script>
      </head>
      <body class="bg-gray-100">
        <main class="max-w-lg mx-auto min-h-screen bg-white shadow">
          <header class="p-5 bg-black text-white">
            <h1 class="text-xl font-bold">🛒 سلتك</h1>
            <p class="text-sm mt-1">روابط مباشرة إلى صفحات المنتجات</p>
          </header>
          {''.join(rows)}
          <footer class="p-5 text-lg font-bold">الإجمالي: {total} د.ك</footer>
        </main>
      </body>
    </html>
    """
    return HTMLResponse(page)


@app.get("/")
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "version": "v13-direct-verified",
        "model": GEMINI_MODEL,
        "buffer_seconds": BUFFER_SECONDS,
    }

