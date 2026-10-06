"""Bounded non-Google discovery. Returns candidates, never verified offers.

Brave is called directly. Bing uses SerpApi, with the application's shared
SerpApi credit guard but a separate engine-health circuit from Google.
"""
from collections import OrderedDict
from dataclasses import dataclass
import copy
import hashlib
import html
import ipaddress
import json
import os
import re
import threading
import time
from urllib.parse import urlsplit
from weakref import WeakKeyDictionary

import requests
from findzia_cache import provider_cacheable


# Markets and country codes are different contracts: SA is a supported text
# country, but ar-SA is not a reverse-image market. Do not construct mkt by
# concatenating the UI language and country. SerpApi links to this table:
# https://learn.microsoft.com/en-us/previous-versions/bing/search-apis/bing-web-search/reference/market-codes
# Production also confirmed rejection of ar-SA, ar-KW and cc=kw (2026-10-02).
BING_MARKETS = tuple('''es-AR en-AU de-AT nl-BE fr-BE pt-BR en-CA fr-CA
es-CL da-DK fi-FI fr-FR de-DE zh-HK en-IN en-ID it-IT ja-JP ko-KR en-MY
es-MX nl-NL en-NZ no-NO zh-CN pl-PL en-PH ru-RU en-ZA es-ES sv-SE fr-CH
de-CH zh-TW tr-TR en-GB en-US es-US'''.split())
BING_TEXT_COUNTRIES = frozenset(m.split('-')[1].lower() for m in BING_MARKETS) | {'sa', 'pt'}
BING_FALLBACK_SOURCE = 'bing_market_fallback'


def bing_route(country, lang, reverse=False):
    """Choose provider parameters without changing the shopper's market."""
    country = str(country or '').lower()
    if not reverse and country in BING_TEXT_COUNTRIES:
        return {'cc': country}, False
    candidates = [m for m in BING_MARKETS if m.split('-')[1].lower() == country]
    language = str(lang or '').lower().split('-')[0]
    if reverse and candidates:
        market = next((m for m in candidates if m.split('-')[0] == language), candidates[0])
        return {'mkt': market}, False
    return {'mkt': 'en-US'}, True


def _number(env, key, default, low, high):
    try:
        return max(low, min(high, float(env.get(key, default))))
    except (ValueError, TypeError):
        return default


def _enabled(env, key, default=True):
    return str(env.get(key, str(default))).lower() in ('true', '1', 'yes', 'on')


@dataclass
class Hedge:
    started: float
    delay: float = 2.0
    minimum: int = 4
    launched: bool = False

    def take(self, now, ready, primary_pending, deadline, failed=False):
        if self.launched or ready >= self.minimum or deadline - now < 1.0:
            return False
        if primary_pending and not failed and now - self.started < self.delay:
            return False
        self.launched = True
        return True


class Budget:
    def __init__(self, maximum):
        self.maximum = maximum
        self.seen = set()
        self.lock = threading.Lock()

    def claim(self, key):
        with self.lock:
            if key in self.seen or len(self.seen) >= self.maximum:
                return False
            self.seen.add(key)
            return True


class LinkedCancel(threading.Event):
    """Stop one lane without declaring its parent search canceled."""
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

    def is_set(self):
        return super().is_set() or self.parent.is_set()


def _obj(value):
    return value if isinstance(value, dict) else {}


def _rows(value):
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _text(value):
    return html.unescape(re.sub(r'<[^>]+>', '', value)).strip() if isinstance(value, str) else ''


def public_url(value, merchant=False):
    """Reject unsafe URL syntax and search-intermediary URLs, without guessing links."""
    if not isinstance(value, str):
        return ''
    try:
        part = urlsplit(value)
        host = (part.hostname or '').lower().rstrip('.')
        if part.scheme not in ('http', 'https') or not host or part.username or part.password:
            return ''
        if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')):
            return ''
        try:
            if not ipaddress.ip_address(host).is_global:
                return ''
        except ValueError:
            if '.' not in host:
                return ''
        if merchant and (host == 'bing.com' or host.endswith('.bing.com') or
                         host == 'brave.com' or host.endswith('.brave.com') or
                         re.fullmatch(r'(?:[a-z0-9-]+\.)?google\.[a-z.]+', host)):
            return ''
        return value
    except ValueError:
        return ''


def normalize_brave(data):
    rows = []
    for raw in _rows(_obj(data.get('web')).get('results')):
        link, title = public_url(raw.get('url'), merchant=True), _text(raw.get('title'))
        if not link or not title:
            continue
        image = public_url(_obj(raw.get('thumbnail')).get('original')) or public_url(_obj(raw.get('thumbnail')).get('src'))
        # Snippet stays attached to this listing; no invented price/currency.
        rows.append(dict(title=title, link=link, snippet=_text(raw.get('description')),
                         thumbnail=image, source=urlsplit(link).hostname,
                         position=len(rows)+1))
    return {'organic_results': rows, 'search_metadata': {'engine': 'brave_search'}}


def normalize_bing(data, reverse=False, market_fallback=False):
    rows, seen = [], set()
    records = (_rows(data.get('related_content')) + _rows(data.get('pages_with_this_image'))
               if reverse else _rows(data.get('organic_results')))
    for raw in records:
        # In reverse-image replies `link` opens Bing; `source` is the page.
        link = public_url(raw.get('source') if reverse else raw.get('link'), merchant=True)
        title = _text(raw.get('title'))
        if not link or not title or link in seen:
            continue
        seen.add(link)
        pictures = list(dict.fromkeys(p for p in (
            public_url(raw.get('original')), public_url(raw.get('thumbnail')),
            public_url(_obj(raw.get('thumbnail')).get('src'))) if p))
        row = dict(title=title, link=link, source=urlsplit(link).hostname,
                   snippet=_text(raw.get('snippet')), position=len(rows)+1,
                   thumbnail=next(iter(pictures), ''), image_candidates=pictures,
                   retrieval_sources=['bing_reverse_image' if reverse else 'bing_search'])
        if market_fallback:
            row['retrieval_sources'].append(BING_FALLBACK_SOURCE)
        if not reverse and isinstance(raw.get('rich_snippet'), dict):
            row['rich_snippet'] = copy.deepcopy(raw['rich_snippet'])
        if reverse:
            row.update(image=row['thumbnail'], section='visual_matches', exact=False,
                       search_origin='image', image_query_result=True, reference_search_kind='image', price='',
                       price_value=None, currency='', in_stock=None, condition='')
        rows.append(row)
    return {'visual_matches' if reverse else 'organic_results': rows,
            'search_metadata': {'engine': 'bing_reverse_image' if reverse else 'bing_search'}}


class SearchClient:
    def __init__(self, env=None, get=None, clock=None, log=None,
                 reserve=None, finish=None, cost=None):
        env = os.environ if env is None else env
        self.enabled = _enabled(env, 'FINDZIA_INDEPENDENT_SEARCH_ENABLED')
        self.brave_key = env.get('BRAVE_SEARCH_API_KEY', '').strip()
        self.serpapi_key = env.get('SERPAPI_API_KEY', '').strip()
        self.bing_enabled = _enabled(env, 'FINDZIA_BING_ENABLED')
        self.delay = _number(env, 'FINDZIA_INDEPENDENT_HEDGE_SECONDS', 2., 0., 5.)
        self.timeout = _number(env, 'FINDZIA_INDEPENDENT_TIMEOUT_SECONDS', 4.5, 1., 6.)
        self.bing_timeout = _number(env, 'FINDZIA_BING_TIMEOUT_SECONDS', 8., 1., 12.)
        self.maximum = int(_number(env, 'FINDZIA_INDEPENDENT_MAX_CALLS', 6, 1, 8))
        self.minimum = int(_number(env, 'FINDZIA_INDEPENDENT_MIN_STORES', 4, 1, 10))
        self.get = get or requests.get
        self.clock = clock or time.monotonic
        self.log = log or print
        self.reserve = reserve or (lambda: True)
        self.finish = finish or (lambda success: None)
        self.cost = cost or (lambda name: None)
        self.lock = threading.Lock()
        self.cache = OrderedDict()
        self.inflight = {}
        self.health = {}
        self.budgets = WeakKeyDictionary()

    def available(self, engine):
        return self.enabled and (bool(self.brave_key) if engine == 'brave_search' else
               self.bing_enabled and bool(self.serpapi_key) if engine in ('bing_search', 'bing_reverse_image') else False)

    def healthy(self, engine):
        with self.lock:
            return self.health.get(engine, (0, 0))[1] <= self.clock()

    def hedge(self, started):
        return Hedge(started, self.delay, self.minimum)

    def budget(self, cancel):
        with self.lock:
            if cancel not in self.budgets:
                self.budgets[cancel] = Budget(self.maximum)
            return self.budgets[cancel]

    def share_budget(self, parent, child):
        budget = self.budget(parent)
        with self.lock:
            self.budgets[child] = budget

    def text_specs(self, country, languages):
        specs = []
        if self.available('brave_search') and self.healthy('brave_search'):
            for lang in list(dict.fromkeys(languages))[:2]:
                specs.append(dict(country=country, role='local', engine='brave_search', hl=lang, _independent=True))
        if self.available('bing_search') and self.healthy('bing_search'):
            specs.append(dict(country=country, role='local', engine='bing_search', hl=languages[0], _independent=True))
        return specs

    def _record(self, engine, success, severe=False):
        with self.lock:
            failures = 0 if success else self.health.get(engine, (0, 0))[0] + 1
            self.health[engine] = (failures, self.clock() + (60. if severe or failures >= 2 else 0.))

    def _request(self, engine, params, headers, deadline, cancel):
        response = None
        remaining = min(self.timeout if engine == 'brave_search' else self.bing_timeout,
                        deadline-self.clock())
        if remaining < .1 or cancel.is_set():
            return None, 0
        url = ('https://api.search.brave.com/res/v1/web/search' if engine == 'brave_search'
               else 'https://serpapi.com/search')
        connect = min(.8, remaining*.2)
        try:
            response = self.get(url, params=params, headers=headers,
                timeout=(connect, max(.05, remaining-connect)), allow_redirects=False, stream=True)
            status = response.status_code
            body = bytearray()
            for chunk in response.iter_content(16384):
                if cancel.is_set() or self.clock() >= deadline:
                    return None, 0
                body.extend(chunk)
                if len(body) > (2*1024*1024 if status == 200 else 65536):
                    return {'error': 'Response exceeded size limit'}, status
            try:
                data = json.loads(body)
            except (ValueError, UnicodeError):
                return {'error': 'Non-JSON provider response'}, status
            return (data if isinstance(data, dict) else {'error': 'Unexpected response format'}), status
        finally:
            if response is not None:
                response.close()

    def _error_detail(self, raw, query, image_url):
        """Only a bounded, redacted provider error; never the response body."""
        error = _obj(raw).get('error')
        if isinstance(error, dict):
            error = error.get('message') or error.get('code')
        if not isinstance(error, str):
            return ''
        # Some providers echo the failing URL, query, or credential in errors.
        for private in (self.brave_key, self.serpapi_key, str(query or ''), image_url):
            if private:
                error = error.replace(private, '[redacted]')
        error = re.sub(r'https?://\S+', '[url]', error)
        error = re.sub(r'(?i)(api[_-]?key|token|authorization)\s*[=:]\s*\S+', r'\1=[redacted]', error)
        error = re.sub(r'[A-Za-z0-9_+/=.-]{24,}', '[redacted]', error)
        error = ' '.join(error.split())[:240]
        return ' detail=' + json.dumps(error, ensure_ascii=True)

    def search(self, engine, query, country, lang, deadline, cancel, image_url=''):
        if not self.available(engine) or cancel.is_set() or deadline-self.clock() < .1:
            return None
        reverse = engine == 'bing_reverse_image'
        if reverse and not public_url(image_url):
            return None
        if not reverse and not str(query or '').strip():
            return None
        route, market_fallback = bing_route(country, lang, reverse) if engine != 'brave_search' else ({}, False)
        # Include language, market, query/image in deduplication; never store keys.
        cache_key = hashlib.sha256(json.dumps([engine, query, country, lang, image_url, route], ensure_ascii=False).encode()).hexdigest()
        timeout = self.timeout if engine == 'brave_search' else self.bing_timeout
        deadline = min(deadline, self.clock()+timeout)
        with self.lock:
            cached = self.cache.get(cache_key)
            if cached and cached[0] > self.clock() and provider_cacheable(cached[1]):
                return copy.deepcopy(cached[1])
            if not self.health.get(engine, (0, 0))[1] <= self.clock():
                return None
            event = self.inflight.get(cache_key)
            leader = event is None
            if leader:
                event = threading.Event()
                self.inflight[cache_key] = event
        if not leader:
            while not cancel.is_set() and self.clock() < deadline:
                if event.wait(min(.05, max(0., deadline-self.clock()))):
                    return copy.deepcopy(getattr(event, 'result', None))
            return None
        reserved, success = False, False
        try:
            if not self.budget(cancel).claim(cache_key):
                return None
            if engine != 'brave_search':
                reserved = self.reserve()
                if not reserved:
                    return None
            headers = {'Accept': 'application/json'}
            # ALL avoids sending unsupported country enumerations (e.g. KW).
            # Actual locality is retained in the query, the header and downstream
            # merchant/currency evidence; never relabel US offers as local.
            if engine == 'brave_search':
                supported = {'en', 'ar', 'de', 'fr', 'es', 'it', 'pt', 'nl', 'hi', 'ur', 'ru', 'tr', 'ja', 'ko', 'zh-hans', 'zh-hant'}
                lang = {'zh': 'zh-hans', 'zh-cn': 'zh-hans', 'zh-tw': 'zh-hant'}.get(lang, lang)
                headers['X-Subscription-Token'] = self.brave_key
                if re.fullmatch(r'[a-zA-Z]{2}', country):
                    headers['X-Loc-Country'] = country.upper()
                params = dict(q=' '.join(str(query).split()[:50])[:400], country='ALL',
                              search_lang=lang if lang in supported else 'en', count=20,
                              spellcheck='false', text_decorations='false')
            else:
                params = dict(engine='bing_reverse_image' if reverse else 'bing', api_key=self.serpapi_key)
                if reverse:
                    params.update(image_url=image_url, count=35)
                else:
                    params.update(q=str(query)[:400])
                params.update(route)
                self.log(f'INDEPENDENT ROUTE engine={engine} country={country} '
                         f'provider_market={route.get("mkt") or route.get("cc")} market_fallback={market_fallback}')
            self.cost('independent_'+engine)
            began = self.clock()
            raw, status = self._request(engine, params, headers, deadline, cancel)
            success = isinstance(raw, dict) and not raw.get('error') and status == 200
            if not cancel.is_set():
                self._record(engine, success, severe=status in (401, 403, 429))
            detail = '' if success else self._error_detail(raw, query, image_url)
            self.log(f'INDEPENDENT SOURCE engine={engine} country={country} status={"returned" if success else "unavailable"} http={status} elapsed_ms={int((self.clock()-began)*1000)}{detail}')
            if not success or cancel.is_set() or self.clock() >= deadline:
                return None
            data = normalize_brave(raw) if engine == 'brave_search' else normalize_bing(raw, reverse, market_fallback)
            self.log(f'INDEPENDENT RESULTS engine={engine} country={country} candidates={len(data.get("visual_matches" if reverse else "organic_results", []))}')
            event.result = copy.deepcopy(data)
            if provider_cacheable(data):
                with self.lock:
                    self.cache[cache_key] = (self.clock()+300., copy.deepcopy(data))
                    self.cache.move_to_end(cache_key)
                    while len(self.cache) > 256:
                        self.cache.popitem(last=False)
            return data
        except Exception as exc:
            if not cancel.is_set():
                self._record(engine, False)
            self.log(f'INDEPENDENT SOURCE engine={engine} country={country} status=unavailable reason={type(exc).__name__}')
            return None
        finally:
            if reserved:
                self.finish(success)
            with self.lock:
                self.inflight.pop(cache_key, None)
                event.set()
