# Findzia usage funnel

The code is ready for GA4 but sends no GA events until the frontend runtime has
`FINDZIA_GA4_MEASUREMENT_ID=G-…` from Findzia's own web stream. Never use the Ads
`AW-…` ID as the GA measurement ID. The existing merchant-click Ads conversion
keeps its own destination and behavior. No search or credit rules change.

## Finish setup

1. Finish the Findzia Analytics account under `info@findzia.com` after the owner
   accepts the applicable Google Analytics and data-processing terms.
2. Create the Findzia Website web stream for `https://findzia.com`, reporting
   timezone Kuwait (UTC+3), currency USD. Turn off enhanced measurement's site
   search, form interactions, and outbound clicks; this integration already
   emits the intended events and deliberately excludes text/retailer URLs.
3. Set the public measurement ID on Railway service `exquisite-mercy` in
   `sweet-wonder` / `production`, then deploy that service. No secrets are needed.
4. Register event-scoped custom dimensions: `theme`, `ui_language`,
   `visit_source`, `search_method`, `search_mode`, `search_outcome`, `error_type`,
   `product_surface`, `cancel_reason`. Register custom metrics `duration_ms`
   (milliseconds) and `result_count` (standard numeric).
5. Build a closed funnel exploration: `fz_visit` → `fz_search_start` →
   `fz_results_view` → `fz_product_click`. Break down by `theme` and compare
   session source/medium. Also inspect `fz_lens_click`, `fz_search_input`, and
   `fz_photo_selected` to see where input stops before an actual search.
6. Verify events in Realtime before calling the integration live. Do not mark
   page visits or search starts as Google Ads conversions. The existing Ads
   conversion is still a merchant click, not a purchase.

## Semantics

- `fz_search_start` fires once per logical search generation, including image
  transport fallback. A pre-request credit gate emits `fz_search_blocked`.
- `fz_results_view` follows actual rendered usable product images; it is not a
  response-headers event. `fz_search_complete` waits for stream completion,
  idle search state, and pending media to settle. An empty result is explicit.
- Terminal errors produce coarse codes only. A failed image transport that
  succeeds through the existing fallback is not counted as a failed search.
- `fz_search_cancel` distinguishes leaving the page or starting another search.
  Browser termination may prevent delivery; this is not a perfect audit log.
- `fz_product_click` is native merchant-link activation. It never redirects or
  delays the link. Analytics event routing explicitly targets only GA4.
- Events include displayed theme, language, coarse campaign source, count and
  elapsed time. They exclude queries, uploaded images, filenames, account IDs,
  raw errors, retailer URLs and arbitrary page query parameters.
- Google click IDs and standard non-search UTM fields remain in the sanitized
  page URL for attribution. `utm_term`, arbitrary query parameters, and referrer
  paths/queries are excluded. GA and Ads reporting can differ due to blockers,
  consent, processing delays and different counting rules.

## Owner tests

Open `https://findzia.com/?fz_test=1` once per browser to exclude that browser
from both GA events and Ads conversions. The flag persists in local storage.
Use `?fz_test=0` to return to normal collection. This does not identify the owner
on other devices. `window.FindziaAnalytics.diagnostics()` exposes the last 40
sanitized local events for validation without sending them externally.

## Validation

`node scripts/build.mjs`

`node --test tests/ads.test.cjs tests/analytics-config.test.mjs`

`NODE_PATH=<Playwright modules> FINDZIA_TEST_CHROME=<Chromium> node tests/analytics.browser.cjs`

The browser test runs the built page and real search handlers against isolated
HTTP, media and Google-transport fixtures. It validates text and photo searches,
image fallback, terminal and credit errors, deduplication, theme, safe campaign
attribution, preserved Ads conversions and persistent owner exclusion. It does
not send events to a real GA property or consume search-provider credits.

The unrelated legacy `launch.test.cjs` suite currently has five failures on the
unchanged base commit too (missing `paymentCopy` fixture and obsolete source
selectors). Those pre-existing tests were not changed as part of analytics.
