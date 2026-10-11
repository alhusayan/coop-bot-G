"""Conservative sale-price extraction for One's exact-listing recovery only."""
import re


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
