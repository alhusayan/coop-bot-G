# Findzia Spaces — isolated trial

English, touch-first private-invite experimental room redesign and shopping app. New rooms use a single automatic product-first design: required room measurements and visible wishes, local-first discovery, verified store size/stock, automatic product selection and one reference-based room render. Redesign repeats the process without requiring the customer to select products. Legacy rooms retain their original shopping flow.

## Deployment

Deploy this folder as an independent Railway service from branch `experiment/findzia-spaces`, root `/spaces`. The existing Findzia backend and storefront are not changed.

Set `GEMINI_API_KEY`, `SERPER_API_KEY`, `SERPAPI_API_KEY` and `SEARCHAPI_API_KEY` as references to the existing Railway backend variables, not copied into code. Set `SPACES_TRIAL_TOKEN` to a high-entropy random value; opening `/trial/<token>` establishes an HttpOnly signed session and keeps the invitation URL, so moving from an in-app browser to Safari can establish a separate session. Reopening the invitation preserves the current session owner. The client checks access before photo selection and renews an expired session through the invitation on a 401, without replaying timed-out design requests. Set `SPACES_DATA_DIR=/data` on an isolated volume. Set `SPACES_PUBLIC_URL` to the service HTTPS URL. No provider keys are exposed to the browser.

Optional: `SPACES_IMAGE_MODEL` (default `gemini-nano-banana-2.1`), `SPACES_TEXT_MODEL` (default `gemini-3.8-flash`), `SPACES_DAILY_ROOMS` (24), `SPACES_SELF_TEST=true` for startup diagnostics and legacy-data recovery. New example photos use the same measured product-first flow as uploads. Check the `SPACES_SELFTEST_RESULT` log; errors are not hidden. Real provider API calls are billable.

## Verification

`npm test` uses Node's built-in test runner for private trial access, safe retrieval, numeric price handling, market evidence, item modes and relevance filtering. `node --check` checks all JavaScript. Install dependencies with `npm ci` before running tests. Sharp crops item images and resizes store evidence.

## Product boundaries

Generated interiors and object positions are visual concepts, not dimensional plans. Up to 28 distinct items are inventoried with tight crops and detailed visual attributes. Google Lens visual_matches runs first via SerpApi, with SearchApi as provider fallback. Detailed English/native-language Serper queries recover absent local matches. When the same silhouette is found in a different colour/material, a further query searches for the required real variant; store images are never recoloured. Actual candidate product photos are compared to the crop: category, colour, shape, material, configuration and proportions must all pass, with no material differences. Missing images fail closed. This is an AI visual check, not a guarantee of SKU identity or physical dimensions. Store dimensions and unverified room fit are shown separately. Exact size cannot be measured reliably from a single photo.

Products without prices stay visible. Foreign currency is preserved, international sources are labelled, stock status is kept, and no AI-generated price is used. Only local-currency ready-made priced available items enter the partial total. Custom work, materials, delivery and installation are excluded. Previous name-only results are hidden until rechecked under matching version 2. No result is labelled an exact match.

Room uploads are normalized to JPEG in the browser, stripping location/EXIF metadata, then shared with Gemini for the requested design. Item crops are shared with Google Lens providers through scoped signed URLs valid for 20 minutes; those URLs expose only that crop, never the original room. Candidate store photos and crops are sent to Gemini for the visual comparison. The app deletes non-demo rooms after 24 hours (hourly cleanup, also on restart). A dedicated trial invite protects costly endpoints; users should not share it publicly. Provider-side retention follows the provider's own terms. Trial limits are independent of existing Findzia credit/payment data.

The hero (`public/hero.webp`) was created with the built-in image-generation tool. Prompt: warm contemporary architectural living room photography, ivory sofa, travertine coffee table, olive chair, oak cabinetry, natural afternoon light; no people, text or logos.

## Sourcing and room isolation (0.3)

Room navigation has a request epoch and server snapshot revision: late polls, old design selections and old job loads cannot write over a new room. Rebuilt item crops use immutable versioned filenames. The backend acknowledges queued/searching state before responding; UI never turns an idle item into a failure message. Kept pieces require actual customer keep notes. Different cushion colors/shapes are inventoried separately.

Lens and local retrieval start together. Local-only visual checks and a bounded local recovery pass finish before international sourcing starts. Global discovery is restricted by the owner-approved allowlist in `sourcing.mjs`, including the verified furniture specialists described below. Wayfair remains local-only in its listed markets; Taobao and 1688 are not approved global sources. Inventory is prepared alongside the three image previews. At most eight visual audits run together using the existing model with low reasoning latency. Sources publish audited results independently; indexed product photos are checked before optional page enrichment. Provider calls and candidate batches are bounded. Selecting a queued piece prioritizes it without duplicate work. No product is discarded merely because its price is absent. Original currencies remain separate. Store availability, delivery and measurements need confirmation.

Strict visual matches remain separate from replacements. A replacement requires the same category, color family and material, with concrete differences shown. The visitor may choose **Use in my design**: the server edits the room using that exact store photo, checks room preservation, locates the placed item and visually verifies it against the store photo. An unverified placement does not replace the design. Dimensions are never inferred or claimed verified. This does not guarantee every generated item has an exact manufactured equivalent.

### 0.3.1 — continuous sourcing and stable updates
- Empty or failed first searches receive one automatic second pass with wider candidate coverage and unchanged visual acceptance rules. Successful options remain visible during a manual retry.
- Keyed DOM updates preserve decoded images, expanded details, focus and sheet scroll position. Room crops remain on the grid; actual store photos are in the product sheet.
- Per-piece activity and a real checked-piece counter show queued, searching, checking and second-pass states. No simulated completion percentage.
- Room detection is automatic; the broken room selector is removed. Detailed replacement differences are expandable.
- Regression coverage includes provisional empty states, bounded retries, retained options, DOM identity and out-of-order image loads.

### 0.3.2 — product identity across views and room function
- A room-level visual identity check groups repeated identical products into one purchase entry with the actual quantity. Different shapes, finishes, configurations, uncertain identities and overlapping detections cannot be merged.
- All grouped crop locations remain available. Searches use up to three angles, combine checked results without duplicate URLs and rank eligible local options before international ones, then visual strength within each market. Existing matching/alternative distinctions remain intact.
- Replacing a grouped item edits every copy, verifies each store-product match and commits the scene only when all copies and the other room contents pass.
- Room detection preserves functional evidence and mixed-use zones. Every generated concept must pass a post-generation function check; an office cannot be silently converted into a lounge. One corrective generation is allowed before a clear retry error.

### 0.3.3 — approved international sources
- `sourcing.mjs` is the single source of approved Findzia global stores, local-only store mappings and specialist furniture policies. Local store evidence remains supported. Unapproved foreign stores are rejected before image auditing, after page redirects, from saved results, from retry seeds, and before applying a replacement.
- Preserves the previous general Findzia approvals: Amazon, eBay, Walmart, AliExpress, Temu, Alibaba, SHEIN, Made-in-China, Target, Best Buy, Newegg, Macy’s, Nordstrom, iHerb, Pottery Barn, Etsy, Home Depot, Chewy, Carter’s, RockAuto, Decathlon; LightInTheBox and DHgate are fallback sources. Only category-relevant sites receive description searches; the full allowlist is eligible for Lens.
- Adds a bounded parallel furniture search lane for Finnish Design Shop, MOHD and Archiproducts. eBay and Etsy direct product paths are supported. Archiproducts catalogue-only pages require actual purchase evidence before admission. Price is optional.
- Shipping-policy sources checked 2026-10-12: https://www.finnishdesignshop.com/en-ch/customer-service/delivery ; https://shop.mohd.it/en/shipping-worldwide ; https://www.archiproducts.com/en/faq-shop . All describe international delivery with product/address restrictions. Retailer-level coverage never verifies delivery of a specific SKU. International alternatives explicitly ask the customer to confirm delivery to their address.
- Search/image verification limits stay bounded; strict visual matching and grouped-item ranking are unchanged. Saved disallowed offers are removed; pieces left without any options are queued for a new search when reopened.

### 0.3.4 — local first, international only as fallback
- Local Lens hits and English/native local queries are checked first. Foreign Lens hits are held without auditing or publishing. A second local pass uses simpler item names and explicit local furniture storefronts before global search is allowed.
- Suitable, visually checked local replacements count as a successful local result. Out-of-stock locals do not block global recovery. Visual thresholds, differences, purchase unit and room-fit disclosures remain unchanged.
- A common ranking function covers initial results, retries, grouped items and saved results. Local options cannot be displaced by higher-scoring global options before truncation. Cached foreign matches cannot hide suitable local alternatives in the product sheet.
- Search revision 7 rechecks older items with no local options when reopened. The latest selected room is refreshed once on deployment. New logs include local check counts, global-fallback events and actual resulting store names for diagnosis.
- Activity labels distinguish local discovery, local recovery and international fallback. Existing keyed image/scroll preservation is retained.

### 0.3.5 — headboardless bed retrieval
- Local recovery expands a platform/headboardless bed to the retailer purchase unit `bed base` / `mattress base`, including Arabic `قاعدة سرير`, while preserving any explicitly described single/twin/double/queen/king configuration. No dimensions are inferred. Candidate acceptance still uses the full original visual evidence.

### 0.3.6 — Stock before recommendations

Every visually accepted piece has a bounded product-page stock check before publication, independently of gallery-image equality. Sold-out matches and replacements are removed, and do not terminate local recovery or international fallback. Product schema, SKU-scoped hydration and English/Arabic purchase controls supply availability; ambiguous or inaccessible pages remain explicitly unconfirmed. Unknown stock cannot be placed into a design. Saved room results are rechecked on the stock migration and on reopen after ten minutes; placement rechecks stock immediately. Prices may still be absent without implying sold-out status.

### 0.3.8 — Conflicting stock evidence

Observed Home Centre schema and product meta both report InStock for the user’s sold-out examples. Landmark positive SEO availability is therefore unconfirmed unless actual purchase controls or SKU-scoped product state confirm stock; explicit negative evidence still excludes the listing. Confirmed local stock ranks first, then confirmed global stock, followed by unconfirmed listings. Unknown availability cannot crowd real purchasable options out of the capped result set.


## 0.4.0 — Measured product recommendations and room preview

Finish my room asks for measured room width/length and optionally a maximum space per item. Store dimensions are parsed only with explicit axes and units. Only approved, listed-in-stock products with complete width/depth/height qualify for automatic selection. Every repeated occurrence must pass the space check; eligible local products precede international ones. The stylist cannot introduce URLs outside the screened set. Missing dimensions, uncertain scale and custom work remain unchanged for review.

The image edit uses actual store photos and dimensions, checks room preservation and verifies every repeated product against the final preview. Preview creation does not modify the saved design. Keep this design rechecks stock and publishes the image, choices and all occurrence crops together. Change a piece regenerates from the saved source.

**Accuracy limits:** Photo-based scale and clearances are estimates, even with room width/length. Entered per-item limits check a rectangular envelope, not full 3D collisions, installation, delivery access or exact colour under different lighting. No output is labelled size_verified. Curtains, built-ins and products missing any required dimension need manual measurement; no dimensions are invented. This feature does not certify an installation plan.


## 0.4.1 — Clear room-size step

Room width and length are required immediately after photo upload, before paid generation or store search. These measurements initialize all three designs and are reused by Finish my room. Starting another room clears the previous dimensions. Older rooms can add room size during store search, including while the inventory is being identified. Saving measurements is independent of search and does not trigger a paid preview. Finish my room remains disabled until dimensions are saved and search completes. Existing measured attempts retain their room size. Empty recommendations now distinguish missing store dimensions, unconfirmed stock and a failed space check; finishing the search never claims that sizes have been checked. Editing measurements invalidates an older preview.

## 0.5 — automatic product-first rooms

`catalog-first.mjs` detects the room function, creates a grouped shopping brief, searches locally (including a recovery pass), then falls back to approved international sources only when suitable local products cannot be verified. Products must have confirmed stock and published dimensions. Flat items can use two explicit dimensions; furniture requires width, depth and height. The AI selects supplied products automatically. Numeric floor footprints are checked for room bounds and overlap; repeated copies use one product.

Only then does the renderer receive the room photo and actual store product photos. It produces one design, with a bounded corrective attempt. Room preservation, quantities, visual scale and product appearance are checked before publishing the image and shopping list atomically. Unverified essential pieces or failed render checks produce a retry state, never fabricated products or dimensions. Redesign keeps the previous result until a new one passes. Store measurements are evidence; room placement remains an approximate visual preview.

Run `npm test` for catalog sequencing, source priority, footprint/quantity validation, failed stock/visual checks, the single-design UI and idempotent redesign, alongside legacy regressions.
