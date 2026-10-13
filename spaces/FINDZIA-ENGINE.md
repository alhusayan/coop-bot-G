# Original Findzia image search

Spaces sends each existing piece crop as bytes, with the room's country and
language, to the main Findzia service. The service calls its existing
`web_api_image_search_stream` route handler unchanged, including its image
preparation, Lens providers, classification, prices and live updates.

`findzia-engine.mjs` only translates that NDJSON stream into room options.
Authoritative snapshots, price updates, removals and sold-out flags are honored.
There is no second visual audit, merchant allow-list, fabricated description or
six-result cap. Similar products remain store options, not claims that a
generated room contains an identifiable retail SKU. Prices retain the original
money contract and currency. Shopify discovery remains separate and live-only.

The dedicated service endpoint requires a server-only HMAC credential,
body signature, short timestamp and one-time nonce. It has concurrency and
per-room/daily request limits in addition to Spaces' existing private-preview
admission. As of 0.5.0, it also requires the customer's existing Findzia account
or guest bearer, allowed origin and idempotent request ID. The original credit
middleware reserves one customer search credit and settles/refunds it through
the existing durable ledger. A service credential cannot bypass the wallet.

Stored rooms retain their saved results without background search migrations.
Overlapping objects retain separate selectable markers. Existing crop images,
room history and 24-hour retention are preserved.


## 0.4.1 client parity and completed visual evidence

`original-client.mjs` contains the original website's verbatim pure price, image,
visibility and stream-state functions. In particular, sparse classifier updates
preserve the last price/image and retrieval sources, snapshots are additive as
in the original photo client, and explicit remove/reject events are applied.
The original SHEIN store-price link exception is preserved without making up a
numeric price. The selected UI language is carried into the room search request;
older English-interface rooms default to English rather than the market language.

Per the owner's follow-up, Spaces waits for completed original visual evidence
before showing a product. Unreviewed previews, conflicting product types/forms,
clearly different colors, and incompatible product forms are held. Original
Similar alternatives additionally require the original approval proof and no
known material/texture/pattern conflict. This is deliberately stricter than the
original site's temporary early preview; retrieval and its prices are unchanged.
A real image comparison is not represented as an exact SKU identification.
Diagnostics report original candidates, candidates with images, displayed rows,
and reasons for withheld rows. Original retrieval variability and image crops
mean independent searches cannot promise a fixed matching result count.


0.4.2: exact-SKU identity scores are not a visual-distance score for generated
furniture: brand/model disagreements alone do not remove a visually consistent
piece. An empty search with still-pending original visual candidates gets at most
one retry of exactly the same original image request. No unchecked preview is
published to turn an empty result into a claimed match. Image-resize experiments
did not reliably improve recall, so production crop pixels remain unchanged.


## 0.4.3 streamed delivery and interactive priority

Transport requests explicitly use `Accept-Encoding: identity` so compression
cannot collect small NDJSON events until the stream closes. Reviewed cards are
forwarded immediately; visual admission and all original retrieval stay unchanged.
Timing separates queue, first byte, first verified card, original event time and
completion.

Two background searches can run at once, with a third slot reserved for an opened
piece. Opening an idle/queued piece promotes the same task without a duplicate
provider call. Existing ownership and quota checks still apply. One original
request is made per piece; 0.4.2's automatic empty-search replay is removed. The
customer can explicitly Search again. Search revision stays 13 because matching
criteria did not change and a deployment must not restart every saved room.

## 0.4.4 saved-design inventory recovery

Inventory now uses a compact native JSON Schema (name, description, mode and
crop box). Legacy generated shopping queries are no longer prerequisites for a
visible object: the original search consumes pixels. The parser accepts the
object list and standard label/box_2d detector shapes, validates real finite
coordinates, and never invents a central fallback crop. One corrective pass is
allowed for valid JSON without usable objects. Logs identify the room/design
and report response shape/counts without dumping the photo or model response.
The API format follows https://ai.google.dev/api/generate-content#v1beta.GenerationConfig.

An explicit SPACES_REPAIR_ROOM / SPACES_REPAIR_DESIGN pair can repair one failed,
empty saved inventory once. It preserves the generated image and checks its
checksum, respects normal task deduplication, and does not enable self-tests or
modify successful inventories. These operational selectors are cleared after use.

## 0.5.0 on-demand points and original customer credits

Generating a design identifies and crops its pieces only. Opening a room,
selecting a design, polling, changing language, restarting a service and
reopening stored merchant options perform no shopping searches.

A new piece search begins only after a point tap and original wallet admission.
The point displays a stationary progress ring; the first visually reviewed
options open the merchant sheet immediately while later verified cards stream in.
Completed points reopen stored prices/options without another debit. An explicit
Search again is labeled 1 credit and uses a new request ID. Per-piece in-flight
deduplication, a persisted client request ID, and the original wallet's atomic
ledger prevent double clicks/network replays from spending twice. Credentials
are forwarded in memory, never written into room state.

One customer credit is the retail price of one search, not one upstream provider
API call. Original provider costs and completed visual-admission rules remain
unchanged. The full-room automatic queue and all startup/demo searches are gone.

## 0.5.1 unobstructed photo and visible search state

All numbered markers are removed. A photo tap selects the smallest detected
foreground box at that location, without a search or debit. Only the selected
occurrence is outlined. Its crop and a labeled one-credit search button confirm
the selection; All pieces provides a thumbnail list and keyboard access for
small or overlapping objects. Existing merchant results open free.

Loading is visible before wallet admission starts: an in-photo status pill,
selected-area scan, elapsed seconds and a moving status track below the image.
No percentage or provider progress is invented. Reduced-motion users keep text,
elapsed time and a static indicator. Pending searches regain visible focus on
room reopen; interrupted GET polling reconnects with bounded backoff and never
replays the paid POST. Original retrieval and wallet accounting are unchanged.
# 0.6.0 — live original results layer

The active Spaces UI now opens the complete live Findzia home/results document
inside a private same-origin dialog frame. `original-page.mjs` fetches only
`https://findzia.com/` and resolves its versioned asset URLs to that origin.
Inline scripts, search handling, billing, media validation, result groups,
ranking, prices and cards are not copied or modified. The original site's
existing `fzRefineBridge.searchPhoto(File)` receives the room's crop bytes.
The Spaces `/focus` and `/search` paths are not called by this UI.

The frame has the same origin as Spaces to share its existing account/guest
wallet. No credentials are passed to an iframe URL or postMessage. Only the
private frame route permits same-origin framing and original inline scripts;
public Findzia and all other Spaces route headers remain unchanged.

Each piece retains its live frame while the layer is closed. Reopening cannot
start another search. The original page's view is saved under the owned room,
without photo bytes or wallet credentials, and restored through the original
view API. Legacy saved options remain a labeled previous search; a new original
search requires an explicit one-credit action. Saving/restoring views never
calls the search API or changes trusted inventory/prices for design adaptation.

The older adapter documentation below describes the retired Spaces-rendered
search flow; it no longer controls customer searches from this interface.


## 0.6.1 results-only frame

The embedded live page receives a frame-only stylesheet that hides the original
site navigation, search composer, camera and footer, and removes the fixed
header spacer. Original result groups, cards, Save/Info controls, status/error
messages and payment dialogs are retained. All original inline scripts remain
byte-for-byte unchanged. Spaces has only a compact title, close action, explicit
new-search action and an animated search status above the frame.

## 0.6.2 design bookmarks and complete saved views

Original result-card bookmarks now save to the current room/design/piece.
The frame capture handler redirects only the bookmark destination; retrieval,
ranking, cards and product details remain the original implementation. Owned
rooms persist picks in their existing private state; demo picks stay in the
current browser. Selected store cards appear below the room photo. These UI
snapshots never become trusted inventory or inputs to generation/billing.

Only nonempty original views qualify as saved results. Legacy completion flags,
old adapted offers and demo status no longer create a fabricated blank Saved
search. A first search is labelled as one credit and launches on the first
explicit click. Views are persisted only after completion with visible cards.
Reopening restores through the original media validator without a new search.
Demo views persist privately in the browser for up to 24 hours.

The active Spaces market now controls photo searches immediately, independently
of the room creation market. Frame sessions and saved original views are keyed
by room/design/piece/market. Switching markets never starts a paid search by
itself and cannot restore another country’s results. Design picks remain the
customer’s explicit selections with their displayed store flag and currency.

## 0.6.3 verified Similar cards

At the customer's request, Similar cards now wait for the original engine's
completed visual review before they can appear in the Spaces frame. A card
requires the engine's alternative visual proof, an audited image, matching
category and positive shape evidence, with no known conflicting shape,
function, material, texture, pattern or color axis. Preview-only, unreviewed,
rejected and unrelated products remain hidden from first paint.

This is a display gate over the existing original search response: no added
search, model request or wallet charge. Local and global groups retain their
original handling. Similar counts reflect displayed cards. If no close
Similar survives and no other card is present, a clear no-confirmed-match
message replaces a blank area. Saved results pass through the same gate.

Original bookmarks still target the room's design picks. Price text is
normalized to keep fractional digits joined to the displayed amount.

## 0.6.4 durable saved-product photos

Design picks retain the source photo from the selected original result rather
than the API's expiring verified-media cache URL. Existing picks recover the
source from their own saved original views, matched by product URL. Store
images use the original renderer's no-referrer policy. This does not run a
search or alter product matching.
