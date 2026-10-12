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
