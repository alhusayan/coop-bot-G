# Findzia Independent Search — 156.7.30

Backend build: `v128.5.42.36-independent-search`

This is a backend update based on the 156.7.29 image-recovery backend. It adds independent retrieval sources to supplement slow, failed or insufficient Google results. It also fixes a cancellation interaction between text retrieval and image refinement.

## Files and installation

Keep a copy of your current files before replacing them. This ZIP is an update package, not the complete application.

| File in this ZIP | Action | Repository destination |
| --- | --- | --- |
| `main.py` | Replace | Root directory, beside the existing API files |
| `findzia_independent_search.py` | Add | Same directory as `main.py` |
| `findzia_search_quality.py` | Keep the included compatible copy | Same directory as `main.py` |
| `tests/` | Optional regression tests | Repository `tests/` directory |
| `README_EN.md`, `SHA256SUMS.txt` | Reference only | No runtime upload required |

The quality helper is byte-for-byte unchanged from the 156.7.29 base. The two changed runtime files are `main.py` and the new `findzia_independent_search.py`.

1. Extract the ZIP on your computer.
2. In GitHub, open the API repository root, where `main.py` already exists.
3. Choose **Add file → Upload files**, upload the three Python files above, and commit them together. Upload the extracted files, not the ZIP or its parent directory. Do not put them in `/frontend`.
4. In Railway, open the **API service**, then **Variables**. Add `BRAVE_SEARCH_API_KEY` if you want Brave enabled. Obtain a Search API key from https://api-dashboard.search.brave.com/ . Do not put this key in the frontend service.
5. Keep the existing `SERPAPI_API_KEY`; it enables Bing through SerpApi. No separate Microsoft Bing key is used.
6. Deploy the API service. Confirm the build string above in its logs.

No frontend, payment, Apple Pay, Paddle, MyFatoorah or DNS changes are needed for this update. Existing `requests` dependencies are reused.

## Behavior

- Google/Serper remain the primary retrieval paths.
- If a market has fewer than four usable stores after about two seconds, independent requests can run alongside the remaining primary requests. The fallback can start earlier when a primary fails or finishes without enough results.
- Brave directly searches its web index for product and merchant pages. Local English/native-language requests retain the requested country in the query and location header.
- Bing web search adds text discovery through SerpApi. Bing reverse-image search uses the original published product image, through SerpApi.
- Text search, image search, image refinement and selected-market discovery share the integration. Approved US/China export catalogs retain their existing global-market role and store restrictions.
- Image refinement keeps its original photo and requested specifications. Finishing its text sub-search no longer cancels the remaining image retrieval.
- New results pass through the existing product, market, currency, image, price and identity checks. Text-derived image candidates stay classified as alternatives until existing evidence checks justify otherwise. A reverse-image hit does not automatically mean an exact match.
- Only direct merchant-page candidates are admitted. Search-engine intermediary links are not relabeled as merchant offers. Prices are not invented from the query or country.
- Results can stream as they arrive. Independent requests use the existing search deadline; this release does not lengthen the search coordinator's overall deadline.

## Configuration

All settings belong to the API service. Optional settings already have defaults; you only need to supply the missing Brave key.

| Variable | Default | Meaning |
| --- | --- | --- |
| `BRAVE_SEARCH_API_KEY` | Empty | Empty skips Brave; a valid key enables it. |
| `SERPAPI_API_KEY` | Existing value | Used by existing Google paths and the new Bing paths. |
| `FINDZIA_INDEPENDENT_SEARCH_ENABLED` | `true` | Master switch for the new independent retrieval paths. |
| `FINDZIA_BING_ENABLED` | `true` | Enable Bing when the SerpApi key exists. |
| `FINDZIA_INDEPENDENT_HEDGE_SECONDS` | `2` | Delay before supplementing an insufficient pending primary; supported range 0–5. |
| `FINDZIA_INDEPENDENT_TIMEOUT_SECONDS` | `4.5` | Per independent request time allowance, also bounded by the caller deadline; range 1–6. |
| `FINDZIA_INDEPENDENT_MAX_CALLS` | `6` | Maximum new independent request attempts per shared search scope; range 1–8. This is an addition to existing provider budgets, not a cap on all application requests. |
| `FINDZIA_INDEPENDENT_MIN_STORES` | `4` | Minimum usable-store target before considering supplementation; range 1–10. |

The six-call allowance covers local/native text, local reverse-image and approved global catalogs. Not every search uses all six calls. There are no automatic HTTP retries in the independent client. Requests for the same engine, query/image, country and language are coalesced when simultaneous, with a five-minute in-memory result cache. A temporary per-engine circuit stops repeated failures. Bing also respects the existing SerpApi credit guard.

Startup example, when both credentials are present:

```text
INDEPENDENT CONFIG enabled=True brave=True bing=True hedge=2.0s timeout=4.5s max_calls=6
```

Individual source logs use `INDEPENDENT SOURCE engine=brave_search`, `engine=bing_search` or `engine=bing_reverse_image`. They include status, country and elapsed time, without API keys or provider response bodies. Cache hits and coalesced requests do not issue a new paid call.

## Verification performed

61 offline regression tests passed, plus Python syntax compilation of all three runtime files. Tests cover adapter contracts, safe candidate URLs, query/country preservation, deadlines, cancellation, request caps, cache separation, simultaneous-request coalescing, circuit behavior, mocked primary failures and slow responses, image-refinement cancellation, selected markets, approved global catalogs, and earlier quality/image recovery behavior.

Run locally after installing the application's existing dependencies:

```bash
python -m unittest discover -s tests -p 'test_*.py' -q
python -m py_compile main.py findzia_independent_search.py findzia_search_quality.py
```

No paid live provider searches were performed while preparing this release. The tests simulate provider responses and coordinator dependencies; they do not establish live store coverage, real-world latency or matching accuracy.

## Live rollout checks

After deployment and key activation:

1. Search for a specific product and a generic category in your selected local market. Confirm that displayed stores and currencies match that market.
2. Search with an image, then use the assistant to change one attribute. Confirm that the requested attribute stays in the search and is reflected in matching results.
3. Check `INDEPENDENT SOURCE` logs on a sparse search. A healthy primary with enough results may correctly skip the fallback.
4. Compare Saudi Arabia, Kuwait, Germany and France using representative products. Check global catalog results separately from local results.
5. Check provider usage dashboards before raising any call limits.

Do not remove working production keys to simulate an outage. Use the bundled offline tests or an isolated staging service for failure testing.

## Limits and rollback

- Bing uses a non-Google search engine but shares SerpApi's transport/account. A SerpApi-wide outage can affect both Bing and Google retrieval. Brave calls its provider directly and supplies a separate text-discovery path.
- This release adds retrieval redundancy. It does not replace Gemini/Google Vision where those services are still used for product understanding or visual verification. It does not bypass merchant challenges or identity checks.
- Different engines have different coverage. Country hints are not proof of local availability; existing downstream market/currency checks remain necessary.
- Per-request socket timeouts and cancellation bound work, but an already running network read may finish after the UI stops waiting. Canceled results are not published as fresh results.
- To disable the new providers, set `FINDZIA_INDEPENDENT_SEARCH_ENABLED=false` in the API service and redeploy. To disable only Bing, set `FINDZIA_BING_ENABLED=false`. To restore the old backend completely, restore the previous `main.py` and matching quality helper. Do not delete `findzia_independent_search.py` while the new `main.py` is deployed.

## Provider contracts

- Brave Web Search: https://api-dashboard.search.brave.com/api-reference/web/search/get
- Bing search through SerpApi: https://serpapi.com/bing-search-api
- Bing reverse-image search through SerpApi: https://serpapi.com/bing-reverse-image-api

The package contains no API keys or environment-variable exports.
