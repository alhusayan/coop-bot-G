# Original Findzia shell

The files in `public/findzia/` are vendored from `frontend/source/` on Findzia main commit `739b008f4b419f95cba2f1ed73631bd1967a0398` (UI 156.7.89, account/support 156.7.62).

`original.css` contains the decoded original home stylesheet and its original inline overrides, scoped to the Spaces shell. `fonts.css` is the original hero font stylesheet. Font licenses remain in `frontend/source/fonts/`.

Account and billing components call the existing `https://api.findzia.com` services. No payment prices, credit rules, provider configuration or credentials are duplicated. Spaces' room preview quotas remain independent of Findzia search credits; no new charge is implied by opening or generating a room.

The only account extension is the `openDesigns` destination under activity. It opens the existing browser-owned room grid. Rooms still expire after 24 hours, and this integration does not claim cross-device room sync.

`findzia-shell.js` adapts the original component hooks to Spaces navigation. The original market/language settings remain functional; the market button uses Spaces' existing country bottom sheet. Original translations are embedded in `i18n.js`, with additional Spaces copy. Original support knowledge is embedded in `support.js`.

Shopify catalog products are fetched live for the room's market with both `ships_from` and `ships_to`, physical shipping and available-variant checks. Results are never persisted, cached, used in AI matching or downloaded by the server. They appear as local shopping suggestions, not verified visual matches. See https://shopify.dev/docs/agents/catalog and https://shopify.dev/docs/agents/catalog/global-catalog-extension.
