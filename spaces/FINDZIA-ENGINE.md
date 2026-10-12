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
admission. Public Findzia account, credit and payment admission are unchanged;
preview room searches do not consume a customer's paid search balance.

Old selected rooms migrate to search revision 11 without regenerating images.
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
