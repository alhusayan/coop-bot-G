# Findzia Photo Search Update — 156.7.33

API build: `v128.5.42.39-photo-text`  
Web version: `156.7.33`

This is a patch for the existing Findzia application. It includes the API changes from 156.7.32 and updates the current standalone frontend. Merge the included files into their existing paths; do not replace the entire repository or delete the existing `frontend` directory.

## Which files do I replace?

Replace these seven runtime files together:

| File inside this ZIP | Destination in GitHub | Purpose |
| --- | --- | --- |
| `main.py` | Repository root, beside the current `main.py` | Search routing, early photo results, Bing grouping, product links and prices |
| `findzia_independent_search.py` | Repository root | Compatible provider adapter from 156.7.32 |
| `findzia_search_quality.py` | Repository root | Compatible shared search-quality helper |
| `frontend/source/findzia-home.liquid` | `frontend/source/` | Photo customization, result counting, image loading and card eligibility |
| `frontend/source/findzia-shell.js` | `frontend/source/` | Correct result counter during and after streaming |
| `frontend/scripts/build.mjs` | `frontend/scripts/` | Version and frontend asset build |
| `frontend/package.json` | `frontend/` | Web release version and existing commands |

The two Python helper modules are unchanged from 156.7.32 and are included to keep the API files compatible. The `tests/` and `frontend/tests/` files are regression tests, not extra runtime files. `README_EN.md` and `SHA256SUMS.txt` are reference files.

## Installation

1. Extract the ZIP and retain the currently deployed version for rollback.
2. In GitHub, open the repository root and use **Add file → Upload files** to replace the three Python runtime files listed above.
3. Open `frontend/source/` and replace only `findzia-home.liquid` and `findzia-shell.js` there.
4. Open `frontend/scripts/` and replace `build.mjs` there.
5. Open `frontend/` and replace `package.json` there. Commit all changes before testing the deployment.
6. Deploy both Railway services after the files are committed. The API service keeps its existing root directory. **Findzia Web** keeps **Root Directory = `/frontend`**. If the frontend has a separate repository, copy the contents of this ZIP's `frontend/` into that repository's root instead.
7. Verify the API startup log contains `v128.5.42.39-photo-text`. Open `https://findzia.com/healthz` and verify the web version is `156.7.33`, then reload the site.

Upload the extracted files, not the ZIP. Do not put the two frontend source files beside `main.py`, and do not create `frontend/frontend/`. Existing payment, account, Dockerfile, server, policy and Apple Pay verification files stay in place. No Railway variable changes are required.

## Photo search and customization

The switch to text search happens **only after the customer adds a word or customization**, either manually or through the AI Shopping Assistant.

| Customer action | Search behavior |
| --- | --- |
| Upload a photo with no added details | Original visual search, including Lens |
| Add a word or specification to that photo | Pure text search built from the retained photo description plus the customer's details |
| Choose specifications in the AI assistant | The same text route, with the original product identity retained |
| Remove all added details and search again | Original visual search again |
| Type a normal search without a photo | Existing text search |

The photo chip represents the retained base description. The search input shows the customer's additions. The base identity is kept across successive refinements, including an empty refinement response. Refinements do not rerun Lens or the original-photo visual comparison. Existing text-search relevance, product-link, price and requested-specification checks still apply.

## Earlier photo results

- Direct product matches can enter the existing verification pipeline as soon as Lens returns them, without waiting for slower category-page expansion. Remaining work continues within the existing bounded search budget.
- Candidate images start loading while prices are being resolved. Cards still require the existing display checks before appearing.
- Provider caps, visual admission requirements and the final collection-expansion path are retained. This change removes unnecessary serial waiting; it does not promise a fixed response time from external providers.

## Bing photo results

Every photo result with Bing provenance is assigned to **Alternatives**, including supported-country searches, fallback markets, Bing text supplements and products expanded from Bing collection pages. A duplicate independently found by Lens still remains in Alternatives when the merged result carries Bing provenance.

These results pass the same visual-admission function used for Serper alternatives. Pending or rejected candidates are not displayed or counted. Bing candidates do not influence the inferred identity of the original photo. Ordinary typed-text searches retain their normal grouping.

## Prices, product links and counts

- Miinto category/listing URLs are not accepted as individual product cards. Collection expansion must supply a separate product URL, image and price. A product URL that redirects to a collection is also rejected.
- The price parser prefers a readable displayed price over internal DOM price attributes. For example, visible `£514.50` with `data-price="51450"` is read as `514.50`. It does not blindly divide every large price by 100.
- The frontend also rejects stale Miinto collection cards already present in a result stream or local state.
- The top result count comes from the same eligible visible cards as the grid. Progress messages cannot reset it to zero while cards remain visible, and completion keeps the count visible.

The screenshot alone does not establish how the original incorrect upstream price was produced. The included tests cover the decimal/minor-unit ambiguity and the collection-page acceptance failure separately.

## Validation completed

- **99 offline backend regression tests passed.** These include photo-only versus customized-photo routing, composition using the retained product identity, manual/assistant details, early direct-result delivery before blocked collection expansion, final result retention, all Bing photo groups, collection redirects and price parsing.
- **31 frontend/server regression tests passed**, covering the existing build, server, motion and billing behavior.
- **Two mobile browser flows passed** at 390px: English/light and Arabic/dark. They cover initial photo search, manual details, AI details, repeated refinements, clearing details, Bing approval/grouping, a matching visible counter, collection-card rejection and a simulated cancelled checkout.

All search-provider and checkout responses in these tests were simulated. No paid provider calls, live card charges or production deployment were performed. These tests verify routing and earlier delivery order; they are not a production latency benchmark or a real-device Apple Pay test.

Run backend tests in the existing application Python environment:

```bash
python -m unittest discover -s tests -p 'test_*.py' -q
```

Run frontend tests from `frontend/`:

```bash
npm test
```

The optional `frontend/tests/photo-browser.cjs` flow also needs Playwright available and a Chromium executable supplied through `FINDZIA_TEST_CHROME`.

## After deployment

1. Search with a photo alone and confirm normal visual results.
2. Add one detail, such as a color. Confirm the thumbnail remains, the input shows the addition and fresh results use the retained product identity.
3. Repeat through the AI assistant, then remove all details and confirm photo-only search works again.
4. Check that the top number matches visible eligible cards and that Bing photo matches appear only in Alternatives.
5. Open a displayed product and check its exact product page and current price. Measure real search timings with the deployed providers before making a speed claim.

## Rollback

Restore the previous versions of the seven runtime files to their same paths and redeploy both services. This patch changes no database schema, payment configuration or account credentials.
