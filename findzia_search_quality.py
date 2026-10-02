"""Cheap, conservative title guards. No network or AI admission dependency."""
import re
import unicodedata


def explicit_text_conflict(query, title):
    def clean(value):
        return unicodedata.normalize('NFKC', str(value or '')).casefold()
    q, t = clean(query), clean(title)
    # Only an explicit accessory-for-product construction is excluded. A device
    # bundled WITH a cable/case remains a device, and accessory searches work.
    parts = r'(?P<part>batter(?:y|ies)|cases?|covers?|chargers?|cables?|straps?|screen protectors?|replacement parts?)'
    for match in re.finditer(r'\b' + parts + r'\b.{0,45}?\b(?:for|compatible with|fits)\b\s+(?P<device>.+)', t):
        part = match['part']
        stem = re.sub(r'ies$', 'y', part).rstrip('s')
        if re.search(r'\b' + re.escape(stem) + r'(?:s|ies)?\b', q):
            continue
        if re.search(r'\b(?:with|includes?|bundle|bundled)\b', t[:match.start()]):
            continue
        words = set(re.findall(r'[\w]+', q)) - {'the', 'a', 'for', 'with', 'buy', 'new', 'best'}
        device = set(re.findall(r'[\w]+', match['device']))
        if words and words <= device:
            return True
    # Compare only the same named family, never unrelated numbers such as
    # wattage, dimensions, price, quantity or Bluetooth versions.
    ignored = {'size', 'pack', 'set', 'box', 'count', 'version', 'bluetooth', 'wifi',
               'usb', 'ram', 'ssd', 'under', 'below', 'from', 'for', 'up', 'of'}
    units = r'\s*(?:gb|tb|mb|cm|mm|inch(?:es)?|hz|khz|ghz|w|mah|ml|kg|pcs)\b'
    def models(text):
        values = {}
        for m in re.finditer(r'(?<!\w)([a-z]+)([ -]?)(\d{1,4})(?![\w.])', text):
            if (len(m[1]) == 1 and m[2]) or m[1] in ignored or re.match(units, text[m.end():]):
                continue
            values.setdefault(m[1], set()).add(m[3])
        return values
    wanted, actual = models(q), models(t)
    return any(wanted[name].isdisjoint(actual[name]) for name in wanted.keys() & actual.keys())
