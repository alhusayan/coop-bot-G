# Live Shopify Catalog supplement

Adds the official Shopify Global Catalog to the existing text and photo search
streams. Purchases still happen at the merchant. This does not copy Shop.com
source code or reproduce its ranking engine, checkout or infrastructure.

The catalog receives the exact selected destination for all 247 country codes
currently registered in `COUNTRY_META`. This is routing coverage, not a promise
of merchant inventory or deliverability in every country. The source's
`ships_to` filter is applied; shipping costs and checkout eligibility still need
confirmation at the merchant. Currency and shipping destination never establish
merchant origin. Supplemental cards are not labelled as local merchants.

## Rollout

The default is **off**. Deployment alone cannot activate catalog searches.

1. Deploy this branch's backend and rebuilt frontend to the test environment.
2. Verify `https://api.findzia.com/.well-known/ucp` (or the test API equivalent)
   returns the profile. Set `FINDZIA_SHOPIFY_PROFILE_URL` to that publicly
   reachable HTTPS URL if using a different API host.
3. Set `FINDZIA_SHOPIFY_CATALOG_ENABLED=preview` to enable the existing unlisted
   trial page only. Both `catalog_live: true` and `catalog_preview: true` are
   required in this mode. This is a rollout switch, not an authorization gate;
   the existing search admission and credit middleware still apply.
4. After reviewing results, use `FINDZIA_SHOPIFY_CATALOG_ENABLED=true` for all
   supported countries on the public page. Set it to `false` to disable.

The frontend is built from `frontend/source` by its existing Dockerfile. The
tracked `frontend/public` folder predates the current source; do not deploy it
without running `node frontend/scripts/build.mjs`.

## Behavior and limits

- One existing admitted search request and credit reservation; no additional
  search endpoint or double charge. The existing billing observer can recognize
  catalog `items`, including when the primary source returns zero results.
- Existing providers run concurrently and their first cards are never held for
  the supplement. Terminal completion may wait until the catalog's absolute
  12-second budget, measured from the start of the stream.
- Up to 12 products per request, 8 concurrent catalog calls per worker; no
  automatic retries. A 429 response pauses this worker's catalog calls for 60
  seconds. Failure or overload leaves the primary stream intact.
- A separate `catalog` NDJSON event is rendered as additional merchant cards.
  URLs are deduplicated against primary results in either arrival order. These
  cards intentionally bypass cached search history, saved products, image
  proxies, image downloading/AI audits and price-history ingestion. They do not
  participate in the existing local/global filters, sorting or Findzia One
  winner selection yet. Visual results are labelled similar, not exact matches.
- There is no catalog result cache, disk storage, prefetch or product index.
  Images render directly from the returned merchant/CDN URL. A new search or
  page navigation discards the cards. Responses use `Cache-Control: no-store`.
- Original prices use ISO currency minor units, including three decimals for
  KWD/BHD/OMR and zero for JPY/KRW. No inferred currency conversion, shipping
  price, rating, exact-match badge or claim of local merchant origin is added.
- JSON fallback, refinement, more-results, and selected-market searches retain
  their current providers. The new source is integrated in the initial text and
  photo NDJSON search paths only. Pagination is deliberately not auto-fetched.

## Validation (2026-10-10)

- Provider, normalization, cancellation, immediate primary delivery, repeat
  fresh requests, 429, profile, all registered country routing, deduplication,
  preview isolation and credit settlement tests pass.
- Existing credit retry and last-credit regression tests pass.
- Frontend tests cover safe text/URLs, direct images, both duplicate arrival
  orders, search/page reset and visual disclaimers in all 16 interface languages.
- Full backend imports and the frontend build succeed.
- A pre-existing failure remains in `tests/trial-page.test.mjs`: it expects no
  `findzia-choice` asset on the public home, but the unchanged base commit
  `ebdf353` already contains that asset. Reproduced in a clean base worktree.
- Real keyless API probes using Shopify's documented example agent profile:
  Kuwait Arabic perfume query: 10 accepted cards in 4.97 s; Japan running shoes:
  6 in 4.99 s; Saudi Arabia synthetic bag image: 12 in 5.01 s. These measure this
  environment's API round-trip, not production page speed or relevance quality.
  No catalog responses or returned images were saved. The production Findzia
  profile still needs a live negotiation check after deployment.

Official references:
- https://shopify.dev/docs/agents/catalog
- https://shopify.dev/docs/agents/catalog/global-catalog
- https://shopify.dev/docs/agents/catalog/global-catalog-extension

Catalog terms prohibit caching results and downloading/caching catalog images.
Preserve the ephemeral rendering boundary when extending this integration.
