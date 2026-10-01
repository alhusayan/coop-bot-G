"""Read-only check before/after the domain cutover. No payments or registration POSTs."""
import argparse
import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request

EXPECTED = 'c15558d3e155e2031ef39b32775050c283b545d8575643181af3c3b9f03d46a3'
FILE = '/.well-known/apple-developer-merchantid-domain-association'
API = 'https://api.findzia.com'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def get(url, headers=None):
    request = urllib.request.Request(url, headers={'User-Agent':'Findzia-Preflight/156.7.19', **(headers or {})})
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=20) as response:
        return response.status, response.headers, response.read()

def check(site):
    failures = []
    def run(name, fn):
        try:
            fn()
            print('PASS', name)
        except Exception as exc:
            failures.append(name)
            print('FAIL', name, '-', str(exc)[:200])
    def file_check():
        status, headers, body = get(site+FILE)
        assert status == 200 and len(body) == 9094 and hashlib.sha256(body).hexdigest() == EXPECTED, 'Wrong verification file'
        assert headers.get('Cache-Control') == 'no-store', 'File must not be cached'
    def home_check():
        _, _, body = get(site+'/')
        assert b'findzia-home-' in body and b'{{' not in body, 'Standalone homepage missing'
        assert b'/cdn/shop/' not in body, 'Homepage still depends on Shopify assets'
    def health_check():
        _, _, body = get(site+'/healthz')
        assert json.loads(body).get('version') == '156.7.19', 'Wrong frontend build'
    def api_check():
        _, headers, body = get(API+'/api/account/config', {'Origin':site})
        assert headers.get('Access-Control-Allow-Origin') == site, 'Add this exact origin to WEB_ALLOWED_ORIGINS on the API service'
        assert json.loads(body).get('ok') is True, 'Account API unavailable'
    run(site+' verification file', file_check)
    run(site+' homepage', home_check)
    run(site+' frontend version', health_check)
    run(site+' API CORS', api_check)
    for slug in ('terms-of-service','privacy-policy','refund-policy'):
        run(site+'/policies/'+slug, lambda slug=slug: get(site+'/policies/'+slug))
    return failures

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('origin', nargs='?', default='https://findzia.com')
    parser.add_argument('--production', action='store_true', help='Check both production storefront origins')
    args=parser.parse_args()
    sites=['https://findzia.com','https://www.findzia.com'] if args.production else [args.origin.rstrip('/')]
    for site in sites:
        parts=urllib.parse.urlsplit(site)
        if parts.scheme != 'https' or not parts.hostname or parts.path or parts.query or parts.fragment or parts.username or parts.password:
            parser.error('Use an HTTPS origin without a path or credentials')
    failed=[]
    for site in sites:
        failed.extend(check(site))
    print('These checks do not verify merchant registration or a real Apple Pay transaction.')
    raise SystemExit(1 if failed else 0)
