"""Request-only Shopify evidence for the private One experience.

Shares the existing UCP client, admission and profile. Catalog listings stay
outside retrieval caches, history, image downloaders and merchant scraping.
"""
import asyncio
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from experiment.findzia_shopify_catalog import ShopifyCatalog, normalize_products, plain, url_key
from experiment.findzia_market_evidence import MerchantMarkets


def one_products(products, country, visual=False, origin_country=''):
    batches = []
    for product in products[:50]:
        if not isinstance(product, dict) or not isinstance(product.get('variants'), list):
            continue
        batch = []
        for variant in product['variants'][:50]:
            if not isinstance(variant, dict):
                continue
            requires = variant.get('requires') or {}
            if not isinstance(requires, dict) or requires.get('selling_plan') or requires.get('components'):
                continue
            rows = normalize_products([dict(product, variants=[variant])], country, visual, origin_country)
            if not rows or rows[0]['money']['amount_minor'] <= 0:
                continue
            row = rows[0]
            # A base product link must select the variant whose price we show.
            if not variant.get('url'):
                variant_id = re.fullmatch(r'gid://shopify/ProductVariant/(\d+)', str(variant.get('id') or ''))
                parsed = urlsplit(row['url'])
                if not variant_id or '/products/' not in parsed.path:
                    continue
                query = [(k, v) for k, v in parse_qsl(parsed.query) if k != 'variant']
                row['url'] = urlunsplit(parsed._replace(query=urlencode(query + [('variant', variant_id[1])])))
            options = variant.get('options') or []
            specs = [dict(key=plain(o.get('name'), 40), value=plain(o.get('label'), 140))
                     for o in options[:8] if isinstance(o, dict) and o.get('name') and o.get('label')]
            variant_title = plain(variant.get('title'), 160)
            if variant_title.lower() in ('default title', 'default'):
                variant_title = ''
            details = '; '.join(s['key'] + ': ' + s['value'] for s in specs)
            row.update(title=plain(' — '.join(filter(None, [row['title'], variant_title, details])), 550),
                       key_specs=specs, variant_title=variant_title,
                       currency=row['money']['currency'], price_amount=float(row['money']['value']),
                       price_kind='exact', price_status='confirmed', price_verified=True,
                       price_source='shopify_catalog', price_source_url=row['url'],
                       in_stock=True, stock_status='in_stock')
            # Inferred descriptions/specs are not merchant-verified model facts.
            batch.append(row)
        batches.append(batch)
    # Preserve multiple sizes/sellers without one large cluster taking every slot.
    return [batch[i] for i in range(50) for batch in batches if len(batch) > i][:72]


class OneMarkets(MerchantMarkets):
    def event(self, event, destination):
        # The primary engine keeps its existing signed market evidence.
        return event


class OneCatalog(ShopifyCatalog):
    normalize_products = staticmethod(one_products)
    deadline = 10

    def __init__(self, countries, signer, *, transport=None, stores=None):
        super().__init__(countries, transport=transport, markets=OneMarkets(countries, stores))
        self.signer = signer

    async def search(self, query, country, lang='en', *, image_b64='', mime='image/jpeg'):
        # Also obtain a positively identified overseas origin. General results
        # with no country evidence never become local or international by guess.
        foreign = 'US' if str(country).upper() != 'US' else 'GB'
        origins = list(dict.fromkeys((str(country).upper(), '', foreign)))
        tasks = [asyncio.create_task(self._search(query, country, lang, image_b64=image_b64,
                  mime=mime, origin_country=origin)) for origin in origins]
        try:
            done, _ = await asyncio.wait(tasks, timeout=self.deadline)
            pools = {'local': [], 'global': []}
            seen, statuses = set(), []
            for task in tasks:
                if task not in done:
                    continue
                try:
                    result = task.result()
                except Exception:
                    continue
                statuses.append(result['status'])
                for item in result['items']:
                    row = self.markets.classify(item, country)
                    scope, key = row['market_scope'], url_key(row['url'])
                    if scope not in pools or key in seen:
                        continue
                    token = self.signer(row)
                    if token:
                        pools[scope].append(dict(row, evaluation_token=token))
                        seen.add(key)
            rows = pools['local'][:9] + pools['global'][:9]
            status = ('ok' if rows or 'ok' in statuses else 'timeout' if len(done) < len(tasks)
                      else statuses[-1] if statuses else 'provider_error')
            # Operational counts only; never retain catalog titles, URLs or images.
            print('ONE CATALOG ' + json.dumps(dict(status=status,
                  local=len(pools['local']), global_count=len(pools['global']), ready=len(done))), flush=True)
            return dict(status=status, items=rows)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
