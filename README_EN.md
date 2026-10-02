# Findzia Search Hotfix — 156.7.31

Backend build: `v128.5.42.37-search-hotfix`

Backend-only update based on 156.7.30. It fixes two verified timing regressions inherited from 156.7.29 and improves Bing diagnostics. The supplied production log stops at the image endpoint's OPTIONS request, so it does not establish the cause of the entire reported image-search stall.

## Installation

Keep a backup. This ZIP is an update package, not the complete application.

| File | Action | Destination |
| --- | --- | --- |
| `main.py` | Replace | API repository root |
| `findzia_independent_search.py` | Replace | Beside main.py |
| `findzia_search_quality.py` | Compatible copy included; unchanged | Beside main.py |
| `tests/` | Optional offline regression tests | Repository tests directory |
| `README_EN.md`, `SHA256SUMS.txt` | Reference only | No runtime upload required |

1. Extract the ZIP.
2. Open the API repository in GitHub where `main.py` already exists.
3. Use **Add file → Upload files** to replace `main.py` and `findzia_independent_search.py` together. Keep the quality helper, or upload the included identical copy. Upload the extracted files, not the ZIP or its parent folder.
4. Deploy the Railway **API service**. Confirm `v128.5.42.37-search-hotfix` in its startup log.

No frontend, payment, authentication or DNS files are changed. Do not put these Python files in `/frontend`.

## Changes

**Primary image download:** Previously the three-second allowance was divided among up to three URLs, leaving about 0.67 seconds of read time for the primary. A valid primary taking 1.1 seconds could fail because alternatives existed. The primary now receives approximately the full configured read allowance (three seconds by default), plus up to 0.65 seconds for connecting. Alternatives use only the remaining shared deadline after failure. Three URLs do not create three full timeouts. The collector wait allowance accommodates the restored download budget. Image validation, size limits, host checks and identity rules remain in place.

**Ready shopping candidates:** Previously merchant-link recovery could delay returning already-ready candidates by up to 2.5 seconds. Ready candidates now return immediately; local and selected-market coordinators separately consume recovery results under their existing overall deadline. Empty initial batches retain their recovery job. Recovery retains the three-lookups-per-image/market limit, uses a separate four-worker queue, and inherits search cancellation. The coordinator owns merging; late workers do not change already-published result lists.

**Bing:** Non-200 JSON errors now produce a short redacted explanation, with the HTTP status retained. The complete response, query, image URL and configured API keys are not logged. HTML/non-JSON content is omitted. Successful responses report normalized candidate counts. Bing receives a default eight-second request allowance, capped by the caller's remaining search deadline; Brave retains 4.5 seconds. Bing web requests use documented `engine`, `q`, `cc` and `api_key` parameters; the unlisted text-search `count` parameter was removed. This contract cleanup is not a confirmed explanation for the production HTTP 400.

Existing request caps, cache, singleflight, credit guard and circuit behavior are retained. There are no automatic HTTP retries. Candidates still pass product, market, currency, price and identity checks. Bing shares SerpApi's account/transport; Brave calls its own provider directly. This update does not bypass merchant or provider restrictions.

## Production evidence and limits

The supplied 156.7.30 log shows `brave=False`, `bing=True`, a Kuwait Bing text request rejected with HTTP 400, and two US Bing requests timing out. There is no successful Bing response or Bing reverse-image request in that log. The old client discarded the error body, so the reason for HTTP 400 is unknown.

An enabled provider is not proof of successful retrieval. After deploying, look for `INDEPENDENT SOURCE ... status=returned http=200` and `INDEPENDENT RESULTS ... candidates=...`. If rejection continues, preserve the complete `INDEPENDENT SOURCE ... http=400 ... detail=...` line. These are format examples, not live test results from this update.

If image search still stalls, capture the log from **POST `/api/search/image/stream`** through completion/error, including Lens, independent-source and image-fetch messages. An OPTIONS 200 only confirms preflight; it does not confirm that the photo search ran. Earlier text-search and media-recovery responses cannot diagnose that missing image request by themselves.

## Railway variables

All settings belong in **API service → Variables**, not the frontend service. Keep existing valid keys.

| Variable | Default / action |
| --- | --- |
| `SERPAPI_API_KEY` | Existing key used for Bing and existing SerpApi paths. |
| `BRAVE_SEARCH_API_KEY` | Optional Brave Search API key; empty skips Brave. Obtain it at https://api-dashboard.search.brave.com/ . |
| `FINDZIA_BING_TIMEOUT_SECONDS` | New default: `8`; range 1–12 seconds, capped by the caller deadline. No manual addition needed for the default. |
| `FINDZIA_INDEPENDENT_TIMEOUT_SECONDS` | `4.5`; now controls Brave only, range 1–6. |
| `FINDZIA_INDEPENDENT_SEARCH_ENABLED` | `true`; master switch. |
| `FINDZIA_BING_ENABLED` | `true`; requires SerpApi key. |
| `FINDZIA_INDEPENDENT_HEDGE_SECONDS` | `2`; delay before supplementing insufficient pending primary results. |
| `FINDZIA_INDEPENDENT_MAX_CALLS` | `6`; cap on independent attempts per shared search scope, additional to existing provider budgets. |
| `FINDZIA_INDEPENDENT_MIN_STORES` | `4`; usable-store target. |

## Validation

73 offline regression tests passed, plus Python syntax compilation of all three runtime files. New tests reproduce the 1.1-second primary-image case, bound total alternative-image time, exercise immediate and deferred results in both real coordinator functions, retain recovery for empty batches, test cancellation, and verify redacted Bing errors and caller-limited timeouts. Earlier provider, photo-refinement and quality tests are included.

```bash
python -m unittest discover -s tests -p 'test_*.py' -q
python -m py_compile main.py findzia_independent_search.py findzia_search_quality.py
```

Tests simulate network responses and coordinator dependencies. No paid live provider requests were made. No production files were deployed. Live coverage, search quality and latency have not been verified for this release. Running socket reads may finish after cancellation; canceled results are not published as fresh results.

## Rollback

Restore backed-up `main.py` and `findzia_independent_search.py` together. Keep the independent module while a main file importing it remains deployed. To temporarily disable Bing only, set `FINDZIA_BING_ENABLED=false` in the API service and redeploy.

Provider references: https://serpapi.com/bing-search-api and https://serpapi.com/bing-reverse-image-api .
