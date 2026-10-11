"""Search cache admission and absolute age limits; no network or app state."""
import math

MAX_CACHE_SECONDS = 86400.0


def search_answer_cacheable(text, urls):
    return (isinstance(text, str) and bool(text.strip()) and isinstance(urls, dict)
            and bool(urls) and all(isinstance(url, str) and url.startswith(('https://','http://'))
                                  for url in urls.values()))


def cache_ttl(requested, default=3600.0):
    value = default if requested is None else requested
    try:
        seconds = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return min(MAX_CACHE_SECONDS, max(0.0, seconds)) if math.isfinite(seconds) else 0.0


def cache_fresh(created, expires, now):
    try:
        created, expires, now = float(created), float(expires), float(now)
        return (all(math.isfinite(v) for v in (created, expires, now))
                and 0 <= now-created < MAX_CACHE_SECONDS and now < expires)
    except (TypeError, ValueError, OverflowError):
        return False


def cache_success(data):
    if not isinstance(data, dict) or not data:
        return False
    if data.get('ok') is False or data.get('partial') or data.get('cancelled'):
        return False
    if any(data.get(k) for k in ('error','errors','review_error','_serpapi_failure',
                                '_findzia_lookup_failed','identity_review_error')):
        return False
    metadata = data.get('search_metadata')
    if isinstance(metadata, dict) and str(metadata.get('status','success')).lower() not in ('success','completed'):
        return False
    return True


def provider_cacheable(data):
    """Successful nonempty evidence only; metadata/empty arrays are not hits."""
    if not cache_success(data):
        return False
    for key in ('organic_results','images_results','shopping_results','inline_shopping_results',
                'visual_matches','exact_matches','products','results','ads','inline_images',
                'local_results','places','sellers_results','related_products','videos_results'):
        rows = data.get(key)
        if isinstance(rows, dict):
            rows = rows.get('results') or rows.get('places')
        if isinstance(rows, list) and any(_evidence_row(row) for row in rows):
            return True
    groups = data.get('categorized_shopping_results')
    if isinstance(groups, list) and any(provider_cacheable(group) for group in groups if isinstance(group,dict)):
        return True
    # Non-search callers sharing the SQLite table use explicit known shapes.
    return bool(_evidence_row(data.get('product_results')) or _evidence_row(data.get('product')) or
                (data.get('domain') and data.get('rating')))


def _evidence_row(row):
    return cache_success(row) and any(row.get(k) for k in (
        'title', 'name', 'link', 'url', 'product_link', 'product_id',
        'image', 'thumbnail', 'original', 'position'))


def analysis_cacheable(data):
    if not cache_success(data):
        return False
    if 'items' in data:
        return bool(isinstance(data['items'],list) and data['items']
                    and all(cache_success(item) for item in data['items']))
    if 'item' in data:
        return cache_success(data['item'])
    return any(data.get(k) for k in ('query','title','identity','reference_profile','product_name','observations','text_facts'))
