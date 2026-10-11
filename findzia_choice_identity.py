"""Positive model evidence for One. A missing model is not a matching model."""
import re
import unicodedata
from urllib.parse import unquote, urlsplit


def normalized(value):
    text = unicodedata.normalize('NFKC', str(value or '')).casefold()
    return ''.join(str(unicodedata.digit(c)) if c.isdecimal() else c for c in text)


_UNITS = (r'gb|tb|mb|kb|kg|mg|ml|cl|cm|mm|mah|wh|kw|hz|mhz|ghz|mp|dpi|'
          r'litres?|liters?|watts?|inches|inch|pcs?|packs?|pieces?|count|'
          r'لتر|واط|وات|كيلو|غرام|جرام|بوصه|بوصة|حبه|حبة|قطعه|قطعة|g|l|w|v|m')


def requirements(query):
    text = normalized(query)
    # Quantities and budgets are constraints, but not product model codes.
    text = re.sub(r'(?<!\w)\d+(?:[.,]\d+)?\s*(?:' + _UNITS + r')(?!\w)', ' ', text)
    currency = r'(?:kwd|kd|usd|sar|aed|eur|gbp|دينار|ريال|درهم|د\.?ك|\$|€|£)'
    text = re.sub(currency + r'\s*\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?\s*' + currency, ' ', text)
    text = re.sub(r'(?<!\w)\d+(?:[.,]\d+)?\s*%', ' ', text)
    # Keep a full SKU, including its suffix: BRI921/60 cannot match BRI921/00.
    codes = re.findall(r'(?<!\w)(?=[a-z0-9/-]*[a-z])(?=[a-z0-9/-]*\d)[a-z0-9]+(?:[-/][a-z0-9]+)*(?!\w)', text)
    codes = [c for c in codes if c not in {'4k', '8k', '5g', '4g', '3d', '2d'}]
    for code in codes:
        text = text.replace(code, ' ')
    numbers = re.findall(r'(?<!\w)\d{1,7}(?!\w)', text)
    return list(dict.fromkeys(codes + numbers))


def contains(value, code):
    # Accept punctuation/spacing variants, never a prefix of another model.
    parts = re.findall(r'[a-z]+|\d+', code)
    pattern = r'[\s/_-]*'.join(map(re.escape, parts))
    return bool(re.search(r'(?<!\w)' + pattern + r'(?!\w)', value))


def model_evidence(query, row):
    """True: proven; False: missing/conflicting; None: no explicit model."""
    wanted = requirements(query)
    if not wanted:
        return None
    primary = normalized(' '.join(str(row.get(k) or '') for k in
                                 ('title', 'raw_title', 'card_model', 'model')))
    # A product slug can retain the series when its SEO title abbreviates it.
    # Query strings, snippets and descriptions may name other products.
    path = normalized(unquote(urlsplit(str(row.get('url') or '')).path)).replace('-', ' ')
    proof = primary + ' ' + path
    if not all(contains(proof, code) for code in wanted):
        return False
    series = r'(?:series|سلسلة|سلسله)\s*[-:]?\s*(\d+)|(\d+)\s*(?:series|سلسلة|سلسله)'
    requested = {a or b for a, b in re.findall(series, normalized(query))}
    observed = {a or b for a, b in re.findall(series, primary)}
    if requested and observed and observed != requested:
        return False
    # Exact SKU suffixes and base/Pro/Ultra variants remain distinct.
    for code in wanted:
        stem = re.match(r'([a-z]+)[-/]?(\d+)', code)
        if not stem:
            continue
        variants = re.findall(r'(?<!\w)' + re.escape(stem[1]) + r'[\s/-]*(\d+[a-z0-9]*(?:\s*[/_-]\s*[a-z0-9]+)*)(?!\w)', primary)
        expected = re.sub(r'[^a-z0-9]', '', code)
        if variants and any(stem[1] + re.sub(r'[^a-z0-9]', '', v) != expected for v in variants):
            return False
    qualifiers = {'ultra', 'pro', 'max', 'plus', 'mini', 'lite', 'fe'}
    requested_qualifiers = set(re.findall(r'\w+', normalized(query))) & qualifiers
    observed_qualifiers = set(re.findall(r'\w+', primary)) & qualifiers
    if requested_qualifiers - observed_qualifiers:
        return False
    qualifier = r'(?:ultra|pro|max|plus|mini|lite|fe)'
    for code in wanted:
        model = r'[\s/_-]*'.join(map(re.escape, re.findall(r'[a-z]+|\d+', code)))
        adjacent = re.findall(r'(?<!\w)' + model + r'\s+(?:series\s+)?(' + qualifier + r'(?:\s+' + qualifier + r')*)(?!\w)', primary)
        if any(set(value.split()) - requested_qualifiers for value in adjacent):
            return False
    return True
