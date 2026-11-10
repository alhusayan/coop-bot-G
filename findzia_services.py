"""Local service discovery using published business listings, never invented contacts.

The original account/credit middleware owns admission and empty/error refunds.
This module does not change the product search or send messages to businesses.
"""
import asyncio
import re
import time
import phonenumbers
from html.parser import HTMLParser
from urllib.parse import urlencode, urlsplit, parse_qs, urljoin
from findzia_service_photo import normalize_photo, photo_suggestions

from fastapi import Request
from fastapi.responses import JSONResponse

PATH = '/api/services/search'


def service_areas(area, country, country_name):
    """Keep the user's area, plus one wider scope; never infer a kilometre radius."""
    if country == 'kw':
        # Home trades commonly serve customers across Kuwait, not just one district.
        wider = country_name
    else:
        parts = [part.strip() for part in re.split('[,،]', area) if part.strip()]
        country_labels = {country.casefold(), country_name.casefold()}
        country_labels.update({'gb': {'uk', 'united kingdom'},
                               'us': {'usa', 'united states', 'united states of america'}}.get(country, set()))
        while len(parts) > 1 and parts[-1].casefold() in country_labels:
            parts.pop()
        wider = parts[-1] if len(parts) > 1 or len(parts) == 1 and parts[0] != area else area
        # Avoid treating a postcode/state abbreviation as a wider city search.
        if len(wider) < 3 or any(char.isdigit() for char in wider):
            wider = area
    return [area] if wider.casefold() == area.casefold() else [area, wider]


async def discover_services(provider, query, area, country, country_name, language):
    areas = service_areas(area, country, country_name)

    async def discover(scope):
        location = scope if scope.casefold() == country_name.casefold() else f'{scope}, {country_name}'
        body = {'q': f'{query}, {location}', 'gl': country, 'hl': language}
        try:
            data = await asyncio.wait_for(asyncio.to_thread(provider, 'places', body, (4, 18)), timeout=24)
            return data if isinstance(data, dict) and isinstance(data.get('places'), list) else None
        except Exception:
            return None

    # Two bounded calls share one request/credit, and run together rather than sequentially.
    responses = await asyncio.gather(*(discover(scope) for scope in areas))
    valid = [(scope, data) for scope, data in zip(areas, responses) if data is not None]
    if not valid:
        raise RuntimeError('services_unavailable')
    # Keep the local provider ordering first; append wider matches and deduplicate below.
    places = [place for _, data in valid for place in data['places'][:30]]
    return listings({'places': places}, country), valid[-1][0]


def whatsapp_link(value):
    """Accept explicit published click-to-chat links, never derive one from a phone."""
    try:
        url = urlsplit(value)
        if url.scheme != 'https' or url.username or url.password or url.port not in (None, 443):
            return ''
        if url.hostname in {'wa.me', 'www.wa.me'}:
            number = url.path.strip('/')
        elif url.hostname in {'api.whatsapp.com', 'www.whatsapp.com', 'whatsapp.com', 'web.whatsapp.com'} and url.path.rstrip('/') == '/send':
            number = parse_qs(url.query).get('phone', [''])[0]
        else:
            return ''
        return 'https://wa.me/' + number if re.fullmatch(r'[1-9]\d{6,14}', number) else ''
    except (TypeError, ValueError):
        return ''


PLATFORM_HANDLES = {'whatsapp', 'whatsappbusiness', 'instagram', 'facebook', 'meta',
                    'google', 'youtube', 'tiktok', 'wix', 'wordpress', 'squarespace',
                    'webflow', 'godaddy', 'linktree'}


def platform_contact_page(value):
    """A platform's own navigation/footer is not the listed business's identity."""
    try:
        host = (urlsplit(value).hostname or '').lower()
        domains = {'whatsapp.com', 'wa.me', 'wa.link', 'facebook.com', 'fb.com',
                   'messenger.com', 'm.me', 'instagram.com', 'tiktok.com',
                   'google.com', 'maps.app.goo.gl', 'youtube.com', 'youtu.be'}
        return any(host == domain or host.endswith('.' + domain) for domain in domains)
    except (ValueError, TypeError, AttributeError):
        return True


def instagram_link(value):
    """Only a published profile URL, never a guessed handle or a post/share link."""
    if not isinstance(value, str) or re.search(r'\s', value):
        return ''
    try:
        url = urlsplit(value)
        if (url.scheme not in {'http', 'https'} or url.username or url.password
                or url.port not in (None, 80, 443)
                or url.hostname not in {'instagram.com', 'www.instagram.com'}):
            return ''
        handle = url.path.strip('/')
        reserved = {'p', 'reel', 'reels', 'stories', 'explore', 'accounts', 'direct',
                    'about', 'legal', 'privacy', 'terms', 'developer', 'developers',
                    'web', 'share', 'sharing', 'tv', 'directory', 'challenge', 'oauth'}
        if (not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.]{0,29}', handle)
                or handle.endswith('.') or '..' in handle or handle.lower() in reserved | PLATFORM_HANDLES):
            return ''
        return f'https://www.instagram.com/{handle}/'
    except ValueError:
        return ''


class ContactLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.whatsapp = ''
        self.instagram = ''

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            href = urljoin('https://placeholder.invalid/', dict(attrs).get('href') or '')
            self.whatsapp = self.whatsapp or whatsapp_link(href)
            self.instagram = self.instagram or instagram_link(href)


def published_contacts(url, safe_get):
    direct = {key: value for key, value in
              [('whatsapp', whatsapp_link(url)), ('instagram', instagram_link(url))] if value}
    if direct:
        return direct
    if not url or not safe_get or platform_contact_page(url):
        return {}
    response = None
    try:
        # Reuses the main application's DNS, connected-peer and redirect checks.
        response = safe_get(url, timeout=(1, 2), max_redirects=1)
        # Some listings call a WhatsApp contact page their website, including
        # shortened links. Never scrape its corporate Instagram/footer links.
        destination = getattr(response, 'url', None)
        if isinstance(destination, str) and platform_contact_page(destination):
            return {}
        if response.status_code != 200 or 'html' not in response.headers.get('content-type', '').lower():
            return {}
        parser, raw, deadline = ContactLinks(), bytearray(), time.monotonic() + 2
        for chunk in response.iter_content(16384):
            raw.extend(chunk)
            if len(raw) > 262144 or time.monotonic() > deadline:
                break
        parser.feed(bytes(raw[:262144]).decode('utf-8', 'replace'))
        return {key: value for key, value in
                [('whatsapp', parser.whatsapp), ('instagram', parser.instagram)] if value}
    except Exception:
        return {}
    finally:
        if response is not None:
            response.close()
            session = getattr(response, '_findzia_session', None)
            if session is not None:
                session.close()


def published_whatsapp(url, safe_get):
    return published_contacts(url, safe_get).get('whatsapp', '')


async def add_published_contacts(rows, safe_get):
    async def contact(row):
        values = await asyncio.to_thread(published_contacts, row['website'], safe_get)
        return {**values, **{key + '_source': row['website'] for key in values}}
    tasks = [asyncio.create_task(contact(row)) for row in rows]
    # Contacts enrich existing results; an unavailable website never blocks search.
    done, pending = await asyncio.wait(tasks, timeout=5) if tasks else (set(), set())
    for row, task in zip(rows, tasks):
        if task in done and not task.cancelled() and not task.exception():
            row.update(task.result())
    for task in pending:
        task.cancel()
    return rows


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


def phone(value, country=None):
    value = clean(value, 60).translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789'))
    # Some provider rows accidentally put an address in phoneNumber. Reject it.
    if not re.fullmatch(r'\+?[0-9 ().\-]+', value):
        return '', ''
    digits = re.sub(r'\D', '', value)
    if not 7 <= len(digits) <= 15:
        return '', ''
    try:
        number = phonenumbers.parse(value, country.upper() if country else None)
        if not phonenumbers.is_possible_number(number):
            return '', ''
        return (phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
                'tel:' + phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164))
    except phonenumbers.NumberParseException:
        # Without a reliable country, never guess a dialling prefix.
        return '', ''


def listings(data, country=None):
    rows, seen, seen_cids = [], set(), set()
    for place in data.get('places', [])[:60]:
        if not isinstance(place, dict):
            continue
        title, address = clean(place.get('title')), clean(place.get('address'), 400)
        category = clean(place.get('category') or place.get('type'), 160)
        # Local packs sometimes mix tradespeople with shops selling their tools.
        # Do not present a retail-only listing as a service provider.
        if category.casefold() in {'hardware store', 'electrical supply store',
                'plumbing supply store', 'building materials store', 'furniture store',
                'electronics store', 'متجر أدوات', 'متجر خردوات', 'متجر أجهزة', 'متجر مواد بناء'}:
            continue
        cid = str(place.get('cid') or '')
        if not title or not address:
            continue
        maps = 'https://www.google.com/maps?' + urlencode({'cid': cid}) if re.fullmatch(r'\d{5,25}', cid) else 'https://www.google.com/maps/search/?' + urlencode({'api': 1, 'query': title + ' ' + address})
        key = (title.casefold(), address.casefold())
        valid_cid = cid if re.fullmatch(r'\d{5,25}', cid) else ''
        if key in seen or valid_cid and valid_cid in seen_cids:
            continue
        seen.add(key)
        if valid_cid:
            seen_cids.add(valid_cid)
        number, tel = phone(place.get('phoneNumber'), country)
        rating = place.get('rating')
        count = place.get('ratingCount')
        rows.append(dict(title=title, address=address, category=category,
                         phone=number, tel=tel, website=website(place.get('website')), link=maps,
                         rating=rating if type(rating) in (int, float) and 0 < rating <= 5 else None,
                         reviews=count if type(count) is int and count >= 0 else None))
        if len(rows) == 24:
            break
    return rows


def install_services(app, provider, countries, configured, *, vision=None, safe_get=None):
    @app.post(PATH)
    async def search_services(request: Request):
        def reply(payload, code=200):
            return JSONResponse(payload, status_code=code, headers={'Cache-Control': 'no-store'})
        try:
            raw = bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw) > 2_050_000:
                    return reply({'error': 'invalid_service_search'}, 413)
            import json
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError()
        except (ValueError, TypeError):
            return reply({'error': 'invalid_service_search'}, 400)
        query, area = clean(payload.get('query'), 200), clean(payload.get('area'), 120)
        has_photo = 'image' in payload
        country = clean(payload.get('country'), 2).lower()
        language = 'ar' if payload.get('language') == 'ar' else 'en'
        if (not has_photo and len(query) < 2) or len(area) < 2 or country not in countries:
            return reply({'error': 'invalid_service_search'}, 400)
        if not configured():
            return reply({'error': 'services_unavailable'}, 503)
        photo = None
        if has_photo:
            try:
                image = await asyncio.to_thread(normalize_photo, payload['image'])
            except ValueError:
                return reply({'error': 'invalid_service_photo'}, 400)
            if not vision:
                return reply({'error': 'service_photo_unavailable'}, 503)
            try:
                photo = photo_suggestions(await asyncio.wait_for(asyncio.to_thread(vision, image), timeout=28))
            except Exception:
                return reply({'error': 'service_photo_unavailable'}, 503)
            # Ambiguity and unknown images are refunded by the existing middleware.
            # The user selects a suggested service before a normal paid search.
            if photo['status'] != 'clear':
                return reply({'ok': True, 'items': [], 'photo': photo, 'area': area, 'country': country.upper()})
            query = photo['options'][0][language]
        try:
            rows, search_area = await discover_services(provider, query, area, country, countries[country], language)
        except Exception:
            return reply({'error': 'services_unavailable'}, 503)
        rows = await add_published_contacts(rows, safe_get)
        return reply({'ok': True, 'items': rows, 'query': query, 'area': area,
                      'search_area': search_area,
                      'country': country.upper(), 'source': 'Google Maps', 'photo': photo})

