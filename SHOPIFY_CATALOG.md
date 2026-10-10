# Live Shopify Catalog supplement

Adds the official Shopify Global Catalog to the existing text and photo search
streams. Purchases still happen at the merchant. This does not copy Shop.com
source code or reproduce its ranking engine, checkout or infrastructure.

The catalog receives the exact selected destination for all 247 country codes
currently registered in `COUNTRY_META`. This is routing coverage, not a promise
of merchant inventory or deliverability in every country. The source's
`ships_to` filter is applied; shipping costs and checkout eligibility still need
confirmation at the merchant. Currency, UI language, country query parameters and search targeting never
establish merchant origin. A concurrent `ships_from` query supplies local candidates. It establishes
positive local-origin evidence only when the returned variant also explicitly
requires physical shipping, independent of price currency. Missing a merchant from
this limited local page never proves it is foreign. Other results use a known
national domain or an unambiguous existing store registry; otherwise they stay
unknown. A national storefront identifies its market, not warehouse location,
shipping cost or delivery speed. Multinational shared domains remain unknown.

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
- Up to 18 products per request (6 local-origin plus 12 broad candidates before deduplication),
  8 concurrent catalog calls per worker; no
  automatic retries. A 429 response pauses this worker's catalog calls for 60
  seconds. Failure or overload leaves the primary stream intact.
- A separate `catalog` NDJSON event feeds the existing public grid/list/cinema cards.
  The private One trial retains its separate supplemental cards.
  URLs are deduplicated against primary results in either arrival order. These
  cards intentionally bypass cached search history, saved products, image
  proxies, image downloading/AI audits and price-history ingestion. Public catalog cards participate in local/global/similar filters and sorting,
  but not Findzia One winner selection. Visual results are labelled similar,
  not exact matches. Unknown merchant countries are visible in All without
  being assigned local/global. Text query matches carry no exact-match claim.
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
  No catalog responses or returned images were saved. The deployed Findzia profile successfully negotiated after adding required
  empty `payment_handlers` and versioning its URL to replace the previously
  cached malformed profile. `FINDZIA_SHOPIFY_PROFILE_URL` in production is
  `https://api.findzia.com/.well-known/ucp?v=20261010-2`.
- Integration update: 30 backend tests plus 18 subtests and 12 frontend tests
  pass. Live Kuwait text and synthetic-image searches render in the public common
  cards, with visible filters and original price currencies. An initial 7.41 s
  probe returned 6 local-filter candidates and 6 broad candidates; origin labels
  were subsequently tightened after discovering digital items bypass that filter.
  Live search, lookup and product-detail responses omitted `requires.shipping`
  for sampled physical products, so those candidates correctly remain unknown
  unless independent storefront evidence exists. No extra lookup calls are added
  to production latency. Unknown countries are never guessed from currencies
  or absence from a limited result page.
- `findzia_market_evidence.py` reclassifies stream output, including cached rows.
  Other publication paths attach the same evidence for the UI to consume.
  Legacy currency-based market guard/admission fallbacks were removed.
- Public catalog rows remain separate in memory from the saved/history/AI row
  collection, join only the common display pipeline, and use direct images.
  Saving/evaluating those live cards is omitted. Deduplication ignores tracking,
  matches an unspecified variant to its offer, and preserves distinct explicit
  variants. Positive origin evidence can enrich a duplicate's live display
  without mutating saved primary data.

Official references:
- https://shopify.dev/docs/agents/catalog
- https://shopify.dev/docs/agents/catalog/global-catalog
- https://shopify.dev/docs/agents/catalog/global-catalog-extension

Catalog terms prohibit caching results and downloading/caching catalog images.
Preserve the ephemeral rendering boundary when extending this integration.

Digital variants (`requires.shipping=false`) can bypass Shopify's origin filter.
They never supply local-origin evidence and are excluded from image-neighbor
results. Missing shipping requirements also cannot establish local origin.
The common public filter buttons are moved out of the legacy hidden header
into a visible row above the integrated cards.
