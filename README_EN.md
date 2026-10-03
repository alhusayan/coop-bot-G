# Findzia Bing Alternatives — 156.7.32

Backend build: `v128.5.42.38-bing-alternatives`

Backend-only update based on 156.7.31. Unsupported-country Bing photo results now use a valid fallback market and enter **Alternatives only after passing the existing Serper visual-accuracy check**.

## Files to replace

This is an update package, not the complete application. Keep a backup before replacing files.

| File | Action | Destination |
| --- | --- | --- |
| `main.py` | Replace | API repository root |
| `findzia_independent_search.py` | Replace together with main.py | API repository root |
| `findzia_search_quality.py` | Unchanged compatible copy included; keep the existing copy | API repository root |
| `tests/` | Offline regression tests; optional to upload | Repository tests directory |
| `README_EN.md`, `SHA256SUMS.txt` | Reference only | No runtime upload required |

1. Extract the ZIP.
2. In the API GitHub repository, open the directory containing the current `main.py`.
3. Use **Add file → Upload files** and upload the extracted `main.py` and `findzia_independent_search.py`. Replace both in the same commit. Do not upload the ZIP or create an extra parent folder.
4. Deploy the Railway **API service** and confirm `v128.5.42.38-bing-alternatives` in the startup log.

No frontend files or new Railway variables are required. Do not put these files in `/frontend`. Payment and account files are not included or changed.

## Behavior

### Supported country versus fallback market

Bing text search and reverse-image search have different market contracts. The supplied production log showed successful Saudi text results but rejected `ar-SA` and `ar-KW` reverse-image markets, and rejected the Kuwait text country `kw`.

The adapter now chooses a valid route before making a request:

| Requested country | Bing text route | Bing reverse-image route |
| --- | --- | --- |
| Saudi Arabia | Native `cc=sa` | Fallback `mkt=en-US` |
| Kuwait | Fallback `mkt=en-US` | Fallback `mkt=en-US` |
| Germany | Native `cc=de` | Native `mkt=de-DE`, even with an English interface |
| France | Native `cc=fr` | Native `mkt=fr-FR` |
| Other countries | Native country when supported; otherwise `en-US` | Native market when listed; otherwise `en-US` |

The request never sends both `cc` and `mkt`. UI language is not blindly combined with the country. The original photo and search wording are preserved. A fallback search market is not evidence of merchant location: existing URL, country, currency and price checks still apply. It does not label US merchants as local or convert their prices into local currency.

### Alternatives and accuracy

- In photo searches, rows retrieved through a fallback Bing market carry provenance through ingestion, collection expansion, merging and price updates. Their display group is **Alternatives**, even if their merchant is local.
- They use the **same visual admission function and configured threshold as Serper**. No separate weaker Bing threshold is introduced. The existing default minimum alternative confidence is 70/100, together with reference/candidate visual evidence and category agreement. Conflicting category, function, role or compatibility is rejected.
- Pending, uncertain, rejected or unavailable visual reviews do not appear in public results or counts. A successful provider response alone does not admit a result.
- Approval is bound to the listing, title and image. A price-only update preserves approval; a different listing, title or image requires review again.
- Fallback candidates cannot change the inferred photo identity through majority product titles.
- Native supported Bing reverse-image results retain their existing grouping. Typed text searches retain their normal grouping. Existing photo-description alternatives from Serper, Brave and Bing text remain alternatives.
- If Google Lens independently retrieved the same listing, existing duplicate resolution preserves that Lens result's primary grouping. Merely adding a price or a Serper duplicate cannot promote a Bing fallback result into Local.

## Timing and request limits

This release retains the 156.7.31 image-download budget restoration and asynchronous shopping-link recovery. It adds no HTTP retries or extra provider requests. Existing cache, singleflight, cancellation, shared call cap, credit guard and circuit breaker remain in place. Bing's eight-second default allowance is still capped by the active search deadline; Brave retains its separate 4.5-second allowance.

Keep existing API service keys and settings. Bing uses `SERPAPI_API_KEY`; Brave remains optional through `BRAVE_SEARCH_API_KEY`.

## Deployment checks

The following are expected log formats, not claims of live test results:

```text
INDEPENDENT ROUTE engine=bing_reverse_image country=sa provider_market=en-US market_fallback=True
INDEPENDENT SOURCE engine=bing_reverse_image country=sa status=returned http=200 ...
INDEPENDENT RESULTS engine=bing_reverse_image country=sa candidates=...
```

For Saudi text, the route should show `provider_market=sa market_fallback=False`. Candidate counts report retrieval, not the final number of approved cards.

After deployment, search by photo in Kuwait or Saudi Arabia. Eligible Bing fallback results should appear only in Alternatives after review. Google Lens results should retain their existing sections. Repeat with photo details from the assistant and verify that unapproved results do not flash in Local while prices load.

## Validation

**89 offline regression tests passed**, plus Python syntax compilation of the three runtime files. Tests cover actual request parameters, country-specific cache isolation, supported-market routing, fallback provenance, the shared Serper admission function, withheld public counts, price/image updates, duplicate arrival order, collection children and photo identity. The earlier image-recovery, photo-refinement, scheduling and search-quality regression tests are included.

```bash
python -m unittest discover -s tests -p 'test_*.py' -q
python -m py_compile main.py findzia_independent_search.py findzia_search_quality.py
```

Use the application's Python environment, including `requests` and Pillow. Transport responses and coordinator dependencies are simulated; application startup is not run. No paid live provider calls were made and no production deployment was performed. Live provider availability, relevance and latency still need to be checked after deployment.

## Rollback

Restore the backed-up `main.py` and `findzia_independent_search.py` together. Keep the independent helper while `main.py` imports it. To temporarily disable Bing only, set `FINDZIA_BING_ENABLED=false` in the API service and redeploy.

## Provider references

- https://serpapi.com/bing-search-api
- https://serpapi.com/bing-reverse-image-api
- https://learn.microsoft.com/en-us/previous-versions/bing/search-apis/bing-web-search/reference/market-codes
- https://learn.microsoft.com/en-us/previous-versions/bing/search-apis/bing-image-search/reference/market-codes
