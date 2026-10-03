# Findzia 156.7.39 — search transition, expanding composer and price integrity

This is a replacement-file update for the existing Findzia repository. It includes the seven-item main menu from 156.7.38. Frontend release: **156.7.39**. API build: **v128.5.42.41-price-integrity**.

## What changed

### A smoother first search

The home form used to blur (and collapse) its editor before switching screens. The next step immediately hid the homepage and animated three separate result-header elements with blur and staggered delays. This exposed two layout changes.

The home editor now stays intact until the page transition owns the switch. Supported browsers capture the outgoing screen and crossfade once, with no moving/scaling search controls or blurred fixed headers. Keyboard resizing and older browsers use a short coordinated fade. The API request starts independently of the animation; it does not wait for products, fonts or animation completion. Reduced-motion preferences switch immediately. A quick return home cancels the previous transition.

### A composer that opens on focus

Tapping or clicking the text area opens it immediately, including an empty field or a short query. It grows as more lines are typed, up to a bounded height, then scrolls internally. A separate hidden measuring element avoids repeatedly collapsing the real editor to measure it. The results header spacer follows the editor height. Action buttons stay below the expanded text. When focus leaves, the field collapses to a one-line preview; the full query remains intact. The clear button still removes text and keeps an attached photo.

### Product pages, original currencies and suspicious prices

The reported Kolshzin URL is a WooCommerce product category, not one monitor offer. The backend and frontend now reject this route type, including encoded paths and pagination. A parent category price or store logo cannot become an individual product card.

Currency validation uses the merchant's original currency, even when a separate display amount has been converted. An Iraqi-dinar offer without evidence of a Kuwait storefront cannot be admitted as a local Kuwait offer. Explicit currency conflicts, token prices on complete devices, and detected outliers are held for verification. Cheap everyday goods and accessories have no general minimum-price rule.

Only the suspect offer waits. Normal offers continue streaming. Verification reuses fresh page evidence when available; otherwise it uses a separate pool with at most three active reviews, at most six attempted reviews per search, and a 3.5-second await budget per review. A confirmed product-page price can replace the suspect amount. A blocked page, timeout or missing evidence leaves that offer hidden. Late indexed duplicates cannot restore the rejected amount. Batch outliers are checked before that batch is published.

These checks detect evidence conflicts and known anomaly patterns; they cannot guarantee that every merchant's published price is accurate. No guessed price or invented currency is used to repair an offer.

## Replace these 11 application files

Paths are relative to the existing repository root (the level containing `main.py` and `frontend`).

| File in this ZIP | Replace at this repository path | Railway service |
| --- | --- | --- |
| `main.py` | `main.py` | API |
| `frontend/package.json` | `frontend/package.json` | Findzia Web |
| `frontend/scripts/build.mjs` | `frontend/scripts/build.mjs` | Findzia Web |
| `frontend/source/findzia-home.liquid` | `frontend/source/findzia-home.liquid` | Findzia Web |
| `frontend/source/findzia-shell.js` | `frontend/source/findzia-shell.js` | Findzia Web |
| `frontend/source/findzia-account.js` | `frontend/source/findzia-account.js` | Findzia Web |
| `frontend/source/findzia-billing.js` | `frontend/source/findzia-billing.js` | Findzia Web |
| `frontend/source/findzia-subscriptions.js` | `frontend/source/findzia-subscriptions.js` | Findzia Web |
| `frontend/source/findzia-filters.js` | `frontend/source/findzia-filters.js` | Findzia Web |
| `frontend/source/findzia-motion.js` | `frontend/source/findzia-motion.js` | Findzia Web |
| `frontend/source/findzia-motion.css` | `frontend/source/findzia-motion.css` | Findzia Web |

The release marker in every listed frontend source matches the build. Upload all ten frontend files together, including those changed only for the release marker. The build rejects a mixed upload before replacing the existing built site.

## Upload and deploy

1. Extract the ZIP on your computer.
2. Open the existing repository at its root. Replace `main.py` at the root. Replace the contents supplied inside `frontend` at their matching paths. If using GitHub's file-upload screen, drag the extracted `main.py` file and `frontend` folder from the ZIP root, and review the paths before committing.
3. Confirm that the changed application files match the 11 paths above. Do not create `frontend/frontend`, and do not place the JavaScript files beside root `main.py`.
4. Commit the files together. Suggested message: `Fix search transition, focused composer and price integrity (156.7.39)`.
5. Let Railway deploy both API and Findzia Web from that commit. If one service does not start a deployment, redeploy that service. Findzia Web continues using its existing `/frontend` root directory.
6. Open `https://findzia.com/healthz`. `version` and all eight `sourceReleases` entries should be `156.7.39`.
7. Open `https://api.findzia.com/api/health`. `build` should be `v128.5.42.41-price-integrity`.
8. Reload Findzia after both deployments complete, then try a fresh first search on your iPhone.

No environment-variable changes are required. Keep existing secrets, payment configuration, database and volume settings. The Apple Pay verification file is unchanged: 9094 bytes, SHA-256 `c15558d3e155e2031ef39b32775050c283b545d8575643181af3c3b9f03d46a3`.

## Quick acceptance check

- On a fresh homepage, tap the empty search field. It should open smoothly before you type. Try a short word, multiple lines and clearing the text.
- Search once from the homepage with the keyboard open. The editor should no longer collapse separately before the page changes.
- On results, tap the field again. Its buttons should remain below the text, and the camera/results should move with the header rather than being covered.
- Search for `ASUS screen` in Kuwait. A product-category card such as the reported Kolshzin page must not appear as a 1 KWD product. Actual available offers vary by provider and merchant.
- Test photo-only search, then add words manually or through the assistant. Only the added-word flow should use text refinement; clearing words should retain the photo.

## Validation and limits

The packaged regression fixtures use mocked merchants, search APIs and payment providers. Chromium checks cover English/light, Arabic/dark, 320px screens and reduced motion, plus cold first navigation under 4x CPU throttling, simulated keyboard resizing, an older-browser fallback and rapid return navigation. Focus height is sampled across animation frames to check that it grows progressively without bouncing. The native iPhone keyboard and real Safari compositor still need the post-deployment acceptance check above; Chromium emulation is not a device test.

Backend fixtures cover category rejection, Iraqi/Kuwaiti currency conflicts (including converted displays), fresh cached page evidence, valid cheap goods, outlier batches, immediate healthy offers while a suspect is held, bounded workers/timeouts, and late duplicate/snapshot protection. Existing decimal-price and stock fixtures are retained.

For optional developer checks, copy `verification/tests/` into the repository's `tests/` directory and `verification/frontend-tests/` into `frontend/tests/`, then run these commands from the complete repository:

```sh
python3 -m unittest discover -s tests -p 'test_price_stock_36.py'
python3 -m unittest discover -s tests -p 'test_price_integrity_39.py'
cd frontend
npm run build
npm test
node tests/photo-browser.cjs
node tests/transition-browser.cjs
```

The Python fixtures need Beautiful Soup. Browser checks need Playwright and `FINDZIA_TEST_CHROME` set to a Chromium executable. Browser screenshots use fixture products, not live merchant offers. `verification/`, `README_EN.md` and `SHA256SUMS.txt` are supporting material; they are not additional application replacements. This package has not been pushed or deployed automatically.
