# Findzia Spaces — isolated trial

Private-invite experimental room redesign and shopping app. Supports all room types, three real photo edits, retained furniture preferences, budget/market selection, detected item hotspots, localized product-price searches, alternatives, quantities, partial totals, export and temporary history.

## Deployment

Deploy this folder as an independent Railway service from branch `experiment/findzia-spaces`, root `/spaces`. The existing Findzia backend and storefront are not changed.

Set `GEMINI_API_KEY` and `SERPER_API_KEY` as references to the existing Railway backend variables, not copied into code. Set `SPACES_TRIAL_TOKEN` to a high-entropy random value; opening `/trial/<token>` establishes an HttpOnly signed session and redirects to `/`. Set `SPACES_DATA_DIR=/data` on an isolated volume. No provider keys are exposed to the browser.

Optional: `SPACES_IMAGE_MODEL` (default `gemini-nano-banana-2.1`), `SPACES_TEXT_MODEL` (default `gemini-3.8-flash`), `SPACES_DAILY_ROOMS` (24), `SPACES_SELF_TEST=true` to create one real example with three variants and a shoppable first design. Check the `SPACES_SELFTEST_RESULT` log; errors are not hidden. Real provider API calls are billable.

## Verification

`npm test` uses Node's built-in test runner for private trial access, safe retrieval, numeric price handling, market evidence, item modes and relevance filtering. `node --check` checks all JavaScript. No browser or package installation is necessary for the test suite.

## Product boundaries

Generated interiors and object positions are visual concepts, not dimensional plans. Product matches are labeled similar; generated objects are never claimed to be exact SKUs. Prices come exclusively from a matching-currency Product/Offer on the product page or a country-scoped indexed shopping offer, clearly distinguished in the UI. No AI-generated prices. Indexed prices and availability may change. Shipping and installation are excluded. Measure/quote/retained items never enter the ready-made product total. Search returns an honest empty state when a price cannot be established.

Room uploads are normalized to JPEG in the browser, stripping location/EXIF metadata, then shared with Gemini for the requested design. The app deletes non-demo rooms after 24 hours (hourly cleanup, also on restart). A dedicated trial invite protects costly endpoints; users should not share it publicly. Provider-side retention follows the provider's own terms. Trial limits are independent of existing Findzia credit/payment data.

The hero (`public/hero.webp`) was created with the built-in image-generation tool. Prompt: warm contemporary architectural living room photography, ivory sofa, travertine coffee table, olive chair, oak cabinetry, natural afternoon light; no people, text or logos.
