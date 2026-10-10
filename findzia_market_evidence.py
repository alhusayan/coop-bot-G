"""Display geography with evidence independent of currency and search targeting."""
from urllib.parse import urlsplit

POLICY = 'merchant-evidence-v2'
# These ccTLDs are commonly used as generic domains, not merchant locations.
GENERIC_CCTLDS = {'ai', 'io', 'co', 'me', 'tv', 'cc', 'fm', 'ly', 'to', 'so', 'ws', 'la', 'sh', 'gg', 'tk'}

# Independently verified storefronts, not currency/delivery-country guesses.
# Evidence and review date are recorded in SHOPIFY_CATALOG.md.
VERIFIED_STORES = {'rullart.com': 'kw', 'karazonline.com': 'kw',
                   'prosportskw.com': 'kw', 'thebr.com': 'kw', 'letstango.com': 'ae'}
# Country-specific hosts must be matched exactly: the Kuwait root must never
# turn a different national storefront (or an unreviewed subdomain) into Kuwait.
STOREFRONT_HOSTS = {
    'alnasser.net': {'alnasser.net': 'kw', 'ksa.alnasser.net': 'sa', 'bh.alnasser.net': 'bh'},
    # Official national storefronts, including 6thStreet's AIVI redirect.
    # https://en-kw.6thstreet.com/ -> https://en-kw.aivi.com/
    **{domain: {f'{lang}-{cc}.{domain}': cc
                for lang in ('en', 'ar') for cc in ('kw', 'sa', 'ae', 'bh', 'qa', 'om')}
       for domain in ('6thstreet.com', 'aivi.com')},
    # Country hosts from the official en-kuwait.levelshoes.com hreflang links.
    'levelshoes.com': {'levelshoes.com': 'ae', 'us.levelshoes.com': 'us',
                      **{f'{lang}-{market}.levelshoes.com': cc
                         for market, cc in (('kuwait', 'kw'), ('saudi', 'sa'),
                                            ('bahrain', 'bh'), ('qatar', 'qa'), ('oman', 'om'))
                         for lang in ('en', 'ar')}},
    # https://en-kw.sssports.com/about-us.html
    'sssports.com': {f'{lang}-{cc}.sssports.com': cc
                    for lang in ('en', 'ar') for cc in ('kw', 'sa', 'ae', 'qa')},
}
STOREFRONT_PATHS = {
    # https://www.namshi.com/kuwait-en/ and its national country selector.
    'namshi.com': {f'/{market}-{lang}/': cc for market, cc in
                  (('kuwait', 'kw'), ('saudi', 'sa'), ('uae', 'ae'),
                   ('bahrain', 'bh'), ('qatar', 'qa'), ('oman', 'om'))
                  for lang in ('en', 'ar')},
    # Explicit routes from https://www.birkenstock.com/kw/ hreflang links.
    # /kw-ar is a Kuwait storefront, not a generic Arabic-language route.
    'birkenstock.com': {f'/{route}/': route.split('-')[0] for route in
                       ('ca ca-fr at be be-nl ch ch-fr ch-it de de-en dk dk-en '
                        'es es-en fi-en fr gb gr-en hr-en hu hu-en ie it it-en '
                        'lu lu-de lu-en nl nl-en no no-en pt pt-en se se-en pl '
                        'pl-en cz-en jp kr ae ae-ar bh bh-ar kw kw-ar qa qa-ar '
                        'sa sa-ar om om-ar hk my sg ph us').split()},
    # https://shop.mango.com/kw/en (country first, language second).
    'mango.com': {f'/{cc}/': cc for cc in
                  ('kw', 'sa', 'ae', 'bh', 'qa', 'om', 'us', 'gb', 'fr', 'de', 'es', 'it')},
    'ikea.com': {f'/{cc}/': cc for cc in
                 ('ae', 'at', 'au', 'be', 'ca', 'ch', 'cn', 'cz', 'de', 'dk',
                  'eg', 'es', 'fi', 'fr', 'gb', 'hr', 'hu', 'ie', 'in', 'it',
                  'jo', 'jp', 'kr', 'kw', 'ma', 'my', 'nl', 'no', 'ph', 'pl',
                  'pt', 'qa', 'ro', 'rs', 'sa', 'se', 'sg', 'si', 'sk', 'th',
                  'tr', 'ua', 'us')},
    'homecentre.com': {f'/{cc}/': cc for cc in ('kw', 'sa', 'ae', 'bh', 'qa', 'om', 'eg')},
    'centrepointstores.com': {f'/{cc}/': cc for cc in ('kw', 'sa', 'ae', 'bh', 'qa', 'om')},
    'azadea.com': {**{f'/{cc}/': cc for cc in ('kw', 'lb', 'qa', 'iq')},
                   '/en/': 'ae', '/ar/': 'ae'},
    'luluhypermarket.com': {f'/{lang}-{cc}/': cc
                          for cc in ('kw', 'sa', 'ae', 'bh', 'qa', 'om')
                          for lang in ('en', 'ar')},
    'noon.com': {f'/{market}-{lang}/': cc for market, cc in
                 (('kuwait', 'kw'), ('saudi', 'sa'), ('uae', 'ae'), ('egypt', 'eg'))
                 for lang in ('en', 'ar')},
}


class MerchantMarkets:
    def __init__(self, countries, stores=None):
        self.countries = {str(c).lower() for c in countries}
        self.stores = {}
        for host, country in VERIFIED_STORES.items():
            if country in self.countries:
                self.stores[host] = {country}
        for country, entries in (stores or {}).items():
            for _, domain in entries:
                host = str(domain).lower().removeprefix('www.').strip('/')
                if '/' not in host:
                    self.stores.setdefault(host, set()).add(country.lower())

    def evidence(self, row):
        # This marker is assigned only by our provider adapter after a successful
        # ships_from filter, not inferred from the selected buyer destination.
        origin = str(row.get('merchant_country') or '').lower()
        if row.get('merchant_country_evidence') == 'shopify_origin_filter' and origin in self.countries:
            return origin, 'shopify_origin_filter'
        try:
            url = urlsplit(row.get('url') or row.get('link') or '')
            host = (url.hostname or '').lower().removeprefix('www.').rstrip('.')
            if url.scheme not in ('http', 'https') or url.username or url.password:
                return '', ''
        except (ValueError, TypeError):
            return '', ''
        for domain, hosts in STOREFRONT_HOSTS.items():
            if host == domain or host.endswith('.' + domain):
                country = hosts.get(host)
                return (country, 'registered_storefront') if country in self.countries else ('', '')
        # Only registered hosts and complete route segments are accepted. A
        # /kw path on an arbitrary domain or ?country=KW never supplies proof.
        for domain, paths in STOREFRONT_PATHS.items():
            if host == domain or host.endswith('.' + domain):
                path = url.path.lower().rstrip('/') + '/'
                for prefix, country in paths.items():
                    if path.startswith(prefix) and country in self.countries:
                        return country, 'registered_storefront'
                return '', ''
        # A registered national storefront can identify its market. Arbitrary
        # country query strings, language paths and subdomains cannot.
        suffix = host.rsplit('.', 1)[-1]
        cc = 'gb' if suffix == 'uk' else suffix
        if cc in self.countries and suffix not in GENERIC_CCTLDS:
            return cc, 'country_domain'
        matches = [(domain, values) for domain, values in self.stores.items()
                   if host == domain or host.endswith('.' + domain)]
        if matches:
            _, values = max(matches, key=lambda x: len(x[0]))
            if len(values) == 1:
                return next(iter(values)), 'registered_storefront'
        return '', ''

    def classify(self, row, destination):
        out = dict(row)
        country, evidence = self.evidence(out)
        scope = ('local' if country == str(destination).lower() else 'global') if country else 'unknown'
        out.update(merchant_country=country.upper() or None, merchant_country_evidence=evidence,
                   market_policy=POLICY, market_scope=scope, market=scope,
                   market_rank=0 if scope == 'local' else 1 if scope == 'global' else 99,
                   country=country, market_country=country,
                   flag=''.join(chr(127397 + ord(c)) for c in country.upper()) if country else '')
        return out

    def event(self, event, destination):
        """Final output boundary, including stale cached/AI-classified rows."""
        out = dict(event)
        if isinstance(out.get('item'), dict):
            out['item'] = self.classify(out['item'], destination)
        for key in ('results', 'all_results', 'items'):
            if isinstance(out.get(key), list):
                out[key] = [self.classify(row, destination) if isinstance(row, dict) else row for row in out[key]]
        return out
