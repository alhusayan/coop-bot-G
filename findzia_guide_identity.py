"""Literal model protection for the optional shopping interview (no network)."""
import re
import unicodedata


def normalize(value):
    text = unicodedata.normalize('NFKC', str(value or '')).casefold()
    text = text.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789'))
    text = re.sub(r'[\u064b-\u065f\u0670\u0640]', '', text)
    for pattern, word in ((r'[اآأإ]ي\s*فون', 'iphone'), (r'ماك\s*بوك', 'macbook'),
                          (r'جالا?كسي|جالكسي', 'galaxy'), (r'بيكسل', 'pixel'),
                          (r'برو', 'pro'), (r'ماكس', 'max'), (r'الترا|ألترا', 'ultra'),
                          (r'بلس', 'plus'), (r'ميني', 'mini')):
        text = re.sub(pattern, word, text)
    return re.sub(r'\s+', ' ', text).strip()


_MODEL = re.compile(r'(?<!\w)([a-z][a-z-]*?)[ -]?(\d{1,4}(?:[a-z]+\d*)?)'
                    r'(?:\s+((?:pro\s+max|pro\s+xl|pro|ultra|plus|mini|fe|edge|xl|mark\s+[ivx]+|[ivx]{2,4})\b))?(?!\w)', re.I)
_IGNORED = {'size', 'pack', 'set', 'box', 'count', 'version', 'bluetooth', 'wifi', 'usb',
            'ram', 'ssd', 'us', 'uk', 'eu', 'usd', 'kwd', 'sar', 'aed', 'qar', 'omr', 'bhd', 'eur', 'gbp', 'cny', 'jpy', 'krw', 'inr', 'rub', 'cad', 'aud', 'nzd', 'chf', 'hdmi', 'ddr', 'under', 'below', 'from', 'for', 'up', 'of', 'step', 'budget', 'inch',
            'gb', 'tb', 'mb', 'cm', 'mm', 'hz', 'khz', 'ghz', 'w', 'mah', 'ml', 'kg', 'pcs'}
_UNITS = re.compile(r'\s*(?:gb|tb|mb|cm|mm|inch(?:es)?|hz|khz|ghz|w|mah|ml|kg|pcs)\b')


def models(value):
    text = normalize(value)
    found = set()
    for match in _MODEL.finditer(text):
        prefix, number, variant = match.groups()
        if prefix in _IGNORED or _UNITS.match(text[match.end():]):
            continue
        found.add(prefix.rstrip('-') + number + re.sub(r'\s+', '', variant or ''))
    for match in re.finditer(r'\b(?:macbook|ipad)\s+(?:air|pro|neo|mini)\b', text):
        found.add(match[0].replace(' ', ''))
    for match in re.finditer(r'\bpure\s+(?:aero|drive|strike)(?:\s+(?:team|lite|tour|vs|plus|98|100))?\b', text):
        found.add(match[0].replace(' ', ''))
    return found


def compatible(base, candidate, require_model=False):
    wanted = models(base)
    if not wanted:
        return True
    actual = models(candidate)
    # Test ALL identities: retaining the original next to an invented second
    # model is just as invalid as replacing the original.
    return not (actual - wanted) and (not require_model or wanted <= actual)


def question_allowed(base, value, fixed=()):
    key = str(value.get('question_key') or '').lower()
    fixed = set(fixed)
    if models(base):
        fixed.update(('model', 'generation', 'release', 'series'))
        question = normalize(value.get('question', ''))
        if re.search(r'\b(?:which|what)\b.{0,35}\b(?:model|generation|series)\b|\bpreferred\s+model\b|(?:اي|أي|شنو|ما)\s+(?:موديل|الموديل|طراز|اصدار|إصدار)', question):
            return False
    if any(re.search(r'(?:^|_)' + re.escape(topic) + r'(?:_|$)', key) for topic in fixed):
        return False
    if not compatible(base, value.get('question', '')):
        return False
    choices = value.get('choices') or []
    if not isinstance(choices, list):
        return False
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        if any(not compatible(base, choice.get(k, '')) for k in ('label', 'answer')):
            return False
    return True
