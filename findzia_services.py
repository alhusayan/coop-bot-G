"""Local service discovery using published business listings, never invented contacts.

The original account/credit middleware owns admission and empty/error refunds.
This module does not change the product search or send messages to businesses.
"""
import asyncio
import re
from urllib.parse import urlencode, urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse

PATH = '/api/services/search'


def clean(value, limit=240):
    return re.sub(r'\s+', ' ', value).strip()[:limit] if isinstance(value, str) else ''


def website(value):
    value = clean(value, 2000)
    try:
        parsed = urlsplit(value)
        if parsed.scheme in ('https', 'http') and parsed.hostname and not parsed.username:
            return value
    except ValueError:
        pass
    return ''


def phone(value):
    value = clean(value, 60).translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789'))
    # Some provider rows accidentally put an address in phoneNumber. Reject it.
    if not re.fullmatch(r'\+?[0-9 ().\-]+', value):
        return '', ''
    digits = re.sub(r'\D', '', value)
    if not 7 <= len(digits) <= 15:
        return '', ''
    return value, 'tel:' + ('+' if value.startswith('+') else '') + digits


def listings(data):
    rows, seen = [], set()
    for place in data.get('places', [])[:30]:
        if not isinstance(place, dict):
            continue
        title, address = clean(place.get('title')), clean(place.get('address'), 400)
        category = clean(place.get('category') or place.get('type'), 160)
        # Local packs sometimes mix tradespeople with shops selling their tools.
        # Do not present a retail-only listing as a service provider.
        if category.casefold() in {'hardware store', 'electrical supply store',
                'plumbing supply store', 'building materials store', 'furniture store',
                'electronics store', 'متجر أدوات', 'متجر أجهزة', 'متجر مواد بناء'}:
            continue
        cid = str(place.get('cid') or '')
        if not title or not address:
            continue
        maps = 'https://www.google.com/maps?' + urlencode({'cid': cid}) if re.fullmatch(r'\d{5,25}', cid) else 'https://www.google.com/maps/search/?' + urlencode({'api': 1, 'query': title + ' ' + address})
        key = (title.casefold(), address.casefold())
        if key in seen:
            continue
        seen.add(key)
        number, tel = phone(place.get('phoneNumber'))
        rating = place.get('rating')
        count = place.get('ratingCount')
        rows.append(dict(title=title, address=address, category=category,
                         phone=number, tel=tel, website=website(place.get('website')), link=maps,
                         rating=rating if type(rating) in (int, float) and 0 < rating <= 5 else None,
                         reviews=count if type(count) is int and count >= 0 else None))
        if len(rows) == 12:
            break
    return rows


def install_services(app, provider, countries, configured):
    @app.post(PATH)
    async def search_services(request: Request):
        def reply(payload, code=200):
            return JSONResponse(payload, status_code=code, headers={'Cache-Control': 'no-store'})
        try:
            raw = bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw) > 4096:
                    return reply({'error': 'invalid_service_search'}, 413)
            import json
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError()
        except (ValueError, TypeError):
            return reply({'error': 'invalid_service_search'}, 400)
        query, area = clean(payload.get('query'), 200), clean(payload.get('area'), 120)
        country = clean(payload.get('country'), 2).lower()
        language = 'ar' if payload.get('language') == 'ar' else 'en'
        if len(query) < 2 or len(area) < 2 or country not in countries:
            return reply({'error': 'invalid_service_search'}, 400)
        if not configured():
            return reply({'error': 'services_unavailable'}, 503)
        # Explicit area and country keep a Kuwait search in Kuwait, not its shopping fallback market.
        body = {'q': f'{query}, {area}, {countries[country]}', 'gl': country, 'hl': language}
        try:
            data = await asyncio.wait_for(asyncio.to_thread(provider, 'places', body, (4, 18)), timeout=24)
        except Exception:
            return reply({'error': 'services_unavailable'}, 503)
        if not isinstance(data, dict) or not isinstance(data.get('places'), list):
            return reply({'error': 'services_unavailable'}, 503)
        return reply({'ok': True, 'items': listings(data), 'query': query, 'area': area,
                      'country': country.upper(), 'source': 'Google Maps'})
