# Findzia Spaces — isolated trial

English, touch-first private-invite experimental room redesign and shopping app. Supports all room types, three real photo edits, retained furniture preferences, budget/market selection, detected item hotspots, localized product-price searches, alternatives, quantities, partial totals, export and temporary history.

## Deployment

Deploy this folder as an independent Railway service from branch `experiment/findzia-spaces`, root `/spaces`. The existing Findzia backend and storefront are not changed.

Set `GEMINI_API_KEY`, `SERPER_API_KEY`, `SERPAPI_API_KEY` and `SEARCHAPI_API_KEY` as references to the existing Railway backend variables, not copied into code. Set `SPACES_TRIAL_TOKEN` to a high-entropy random value; opening `/trial/<token>` establishes an HttpOnly signed session and keeps the invitation URL, so moving from an in-app browser to Safari can establish a separate session. Reopening the invitation preserves the current session owner. The client checks access before photo selection and renews an expired session through the invitation on a 401, without replaying timed-out design requests. Set `SPACES_DATA_DIR=/data` on an isolated volume. Set `SPACES_PUBLIC_URL` to the service HTTPS URL. No provider keys are exposed to the browser.

Optional: `SPACES_IMAGE_MODEL` (default `gemini-nano-banana-2.1`), `SPACES_TEXT_MODEL` (default `gemini-3.8-flash`), `SPACES_DAILY_ROOMS` (24), `SPACES_SELF_TEST=true` to create one real example with three variants and a shoppable first design. Check the `SPACES_SELFTEST_RESULT` log; errors are not hidden. Real provider API calls are billable.

## Verification

`npm test` uses Node's built-in test runner for private trial access, safe retrieval, numeric price handling, market evidence, item modes and relevance filtering. `node --check` checks all JavaScript. Install dependencies with `npm ci` before running tests. Sharp crops item images and resizes store evidence.

## Product boundaries

Generated interiors and object positions are visual concepts, not dimensional plans. Up to 28 distinct items are inventoried with tight crops and detailed visual attributes. Google Lens visual_matches runs first via SerpApi, with SearchApi as provider fallback. Detailed English/native-language Serper queries recover absent local matches. When the same silhouette is found in a different colour/material, a further query searches for the required real variant; store images are never recoloured. Actual candidate product photos are compared to the crop: category, colour, shape, material, configuration and proportions must all pass, with no material differences. Missing images fail closed. This is an AI visual check, not a guarantee of SKU identity or physical dimensions. Store dimensions and unverified room fit are shown separately. Exact size cannot be measured reliably from a single photo.

Products without prices stay visible. Foreign currency is preserved, international sources are labelled, stock status is kept, and no AI-generated price is used. Only local-currency ready-made priced available items enter the partial total. Custom work, materials, delivery and installation are excluded. Previous name-only results are hidden until rechecked under matching version 2. No result is labelled an exact match.

Room uploads are normalized to JPEG in the browser, stripping location/EXIF metadata, then shared with Gemini for the requested design. Item crops are shared with Google Lens providers through scoped signed URLs valid for 20 minutes; those URLs expose only that crop, never the original room. Candidate store photos and crops are sent to Gemini for the visual comparison. The app deletes non-demo rooms after 24 hours (hourly cleanup, also on restart). A dedicated trial invite protects costly endpoints; users should not share it publicly. Provider-side retention follows the provider's own terms. Trial limits are independent of existing Findzia credit/payment data.

The hero (`public/hero.webp`) was created with the built-in image-generation tool. Prompt: warm contemporary architectural living room photography, ivory sofa, travertine coffee table, olive chair, oak cabinetry, natural afternoon light; no people, text or logos.

## Sourcing and room isolation (0.3)

Room navigation has a request epoch and server snapshot revision: late polls, old design selections and old job loads cannot write over a new room. Rebuilt item crops use immutable versioned filenames. The backend acknowledges queued/searching state before responding; UI never turns an idle item into a failure message. Kept pieces require actual customer keep notes. Different cushion colors/shapes are inventoried separately.

Lens starts first. After at most 1.8 seconds, local/native and global US/China image sources run alongside it. Approved global discovery includes Amazon, Wayfair, Walmart, AliExpress, Temu, SHEIN, Alibaba, Made-in-China, 1688 and Taobao. Sources publish audited results independently; indexed product photos are checked before optional page enrichment. Provider calls and candidate batches are bounded. Selecting a queued piece prioritizes it without duplicate work. No product is discarded merely because its price is absent. Original currencies remain separate. Store availability, delivery and measurements need confirmation.

Strict visual matches remain separate from replacements. A replacement requires the same category, color family and material, with concrete differences shown. The visitor may choose **Use in my design**: the server edits the room using that exact store photo, checks room preservation, locates the placed item and visually verifies it against the store photo. An unverified placement does not replace the design. Dimensions are never inferred or claimed verified. This does not guarantee every generated item has an exact manufactured equivalent.
