"""Run inside the configured environment; prints sanitized JSON, never keys.

Examples (from the ZIP/repository root):
 PYTHONPATH=. python verification/live_price_probe.py --query "STAEDTLER Noris 122 HB" --country sa --language ar
 PYTHONPATH=. python verification/live_price_probe.py --shein-url '<an observed supported SHEIN product URL>'

Query mode: one Serper Shopping request + up to two SearchAPI product pages.
URL mode: at most one SearchAPI request; unsupported markets cost zero.
Does not start/import the application or alter service configuration.
"""
import argparse
import hashlib
import io
import json
import os
import re
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from findzia_prices import StructuredPrices, shein_params, shopping_params


def run(args):
    if not os.environ.get('SEARCHAPI_API_KEY', '').strip():
        return {'status':'missing_SEARCHAPI_API_KEY', 'requests':0}
    client = StructuredPrices(enabled=True)
    report = {'status':'completed', 'live_probe':True, 'application_search_tested':False,
              'country':args.country, 'language':args.language, 'cases':[]}
    if args.shein_url:
        params = shein_params({'url':args.shein_url})
        if not params:
            return {'status':'unsupported_storefront_or_variant', 'requests':0,
                    'note':'No country substitution; this probe cannot confirm this SHEIN price.'}
        cases = [('shein', {'url':args.shein_url})]
    else:
        key = os.environ.get('SERPER_API_KEY', '').strip()
        if not key:
            return {'status':'missing_SERPER_API_KEY', 'requests':0}
        response = None
        try:
            response = requests.post('https://google.serper.dev/shopping',
                headers={'X-API-KEY':key,'Content-Type':'application/json'},
                json={'q':args.query[:220],'gl':args.country,'hl':args.language,'num':10},
                timeout=(2,10), allow_redirects=False)
            if response.status_code != 200:
                return {'status':'discovery_http_'+str(response.status_code),'requests':1}
            data = response.json()
        except Exception as exc:
            return {'status':type(exc).__name__,'stage':'discovery','requests':1}
        finally:
            if response is not None: response.close()
        seen, cases = set(), []
        for card in data.get('shopping') or []:
            if not isinstance(card,dict) or not card.get('title'):
                continue
            params = shopping_params(card,args.country,args.language)
            if not params or json.dumps(params,sort_keys=True) in seen: continue
            seen.add(json.dumps(params,sort_keys=True)); cases.append(('shopping',card))
            if len(cases) == 2: break
        report['discovery_rows'] = len(data.get('shopping') or [])
        report['query_hash'] = hashlib.sha256(args.query.encode()).hexdigest()[:12]
    for kind, row in cases:
        began = time.monotonic()
        with redirect_stdout(io.StringIO()) as trace:
            result = (client.shein(row,10) if kind == 'shein' else
                      client.shopping(row,args.country,args.language,3.5))
        offers = (result or {}).get('organic_results') or []
        report['cases'].append({'kind':kind, 'elapsed_ms':int((time.monotonic()-began)*1000),
            'provider_rows':len(offers), 'failed':bool((result or {}).get('_findzia_lookup_failed')),
            'skipped':result is None,
            'trace':trace.getvalue().strip(),
            'offers':[{'host':urlsplit(r['link']).hostname, 'title':r['title'][:160],
                       'price':r['price'],'currency':r.get('currency','')} for r in offers[:12]]})
    report['note'] = ('These are provider observations using the 3.5-second Shopping production '
                      'request budget. Final identity/market/image gates and visible cards still require app measurement.')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--query'); group.add_argument('--shein-url')
    parser.add_argument('--country',default='sa'); parser.add_argument('--language',default='ar')
    args=parser.parse_args()
    if not re.fullmatch(r'[a-z]{2}',args.country) or not re.fullmatch(r'[a-zA-Z-]{2,10}',args.language):
        parser.error('Use valid explicit country/language codes.')
    print(json.dumps(run(args),ensure_ascii=False,indent=2))


if __name__ == '__main__': main()
