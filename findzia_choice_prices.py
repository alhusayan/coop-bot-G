"""Conservative sale-price extraction for One's exact-listing recovery only."""
import re
import time
from concurrent.futures import wait, FIRST_COMPLETED


def race_listing_prices(page, start_index, accept, *, timeout=10, grace=.35):
    """Wait for either exact-listing source to yield usable money within one deadline.

    An empty/blocked/invalid result never cancels the other source. A fast page
    avoids the index request altogether; a fast valid index need not wait for a
    blocked page. Running requests still populate their normal shared caches.
    """
    deadline = time.monotonic() + timeout
    pending = {page: 'page'}
    states = {}
    try:
        done, _ = wait([page], timeout=min(grace, timeout))
        while True:
            for future in sorted(done, key=lambda f: pending[f] != 'page'):
                source = pending.pop(future)
                try:
                    update = future.result() or {}
                except Exception:
                    states[source] = 'error'
                    continue
                availability = str(update.get('availability') or '').lower()
                if source == 'page' and any(x in availability for x in ('outofstock', 'out_of_stock', 'discontinued')):
                    states[source] = 'out_of_stock'
                    return None, states
                result = accept(update) if update.get('price') else None
                status = update.get('page_fetch_status')
                states[source] = 'accepted' if result else 'rejected' if update.get('price') else status if status in ('blocked', 'timeout', 'error') else 'price_missing'
                if result:
                    return result, states
            if 'index' not in states and 'index' not in pending.values():
                pending[start_index()] = 'index'
            remaining = deadline - time.monotonic()
            if not pending or remaining <= 0:
                break
            done, _ = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)
            if not done:
                break
        return None, states
    finally:
        for future, source in pending.items():
            states[source] = 'pending'
            future.cancel()


def labelled_current_quote(item, parse_quote, country=''):
    """Read an explicitly labelled current price, never the lowest of many numbers.

    Caller must bind the indexed document to the exact listing and variant first.
    Regular prices, savings, instalments, ranges and conflicting current prices
    cannot become an offer. Currency must be printed beside the amount.
    """
    texts = [item[k] for k in ('snippet', 'description', 'price') if isinstance(item.get(k), str)]
    for side in ('top', 'bottom'):
        texts += [x for x in ((item.get('rich_snippet') or {}).get(side) or {}).get('extensions', [])
                  if isinstance(x, str)]
    label = r'(?:special\s+price|sale\s+price|current\s+price|now|السعر\s+الخاص|سعر\s+العرض|السعر\s+الحالي)'
    currency = r'(?:KWD|K\.?D\.?|USD|US\$|AED|SAR|QAR|BHD|OMR|EUR|GBP|CAD|AUD|د\.?\s?ك\.?|ر\.?\s?س\.?|د\.?\s?إ\.?|[$€£])'
    amount = r'\d[\d,.]*'
    pattern = re.compile(r'(?<!\w)' + label + r'\s*[:：]?\s*(' + currency + r'\s*' + amount + r'|' + amount + r'\s*' + currency + r')(?!\w)', re.I)
    quotes = []
    for text in texts:
        for match in pattern.finditer(text[:1600]):
            vicinity = text[max(0, match.start()-24):match.end()+35]
            if re.search(r'month|instalment|installment|per\s+(?:pack|unit)|coupon|code\b|from\b|starting|up\s+to|/\s*(?:mo|month)|شهري|تقسيط|ابتداء|كوبون', vicinity, re.I):
                continue
            if re.match(r'\s*[-–—~]\s*' + currency + r'?\s*\d', text[match.end():], re.I):
                continue
            quote = parse_quote(match.group(1), '', country)
            if quote and quote.get('kind') == 'exact' and not quote.get('unit'):
                quotes.append(quote)
    if not quotes or len({(q['min'], q['max'], q['currency']) for q in quotes}) != 1:
        return None
    return quotes[0]
