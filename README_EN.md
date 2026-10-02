# Findzia Image Recovery — 156.7.29

Backend build: v128.5.42.35-image-recovery
Based on the 156.7.28 prelaunch patch / backend v128.5.42.34-launch-review observed in the supplied logs.
This is an incremental backend patch, not a full project. It has not been deployed.

## Files to upload

Upload BOTH of these files to the repository ROOT (next to the existing main.py) in one commit:

- main.py — replace the existing file.
- findzia_search_quality.py — add/replace it; this dependency was introduced in 156.7.28.

If uploading separately, upload findzia_search_quality.py first, then main.py.
Keep every other project file. Deploy the existing API Railway service. No frontend file, environment-variable change, or database migration is needed. The frontend release remains 156.7.28.

The tests folder contains optional developer regression tests, not production configuration.
Do not paste file contents, rename main.py, upload this ZIP directly, or place these files inside frontend.

## What changed

1. Candidate-image auditing tries up to three observed images belonging to the same offer, sharing the existing image-fetch budget. Blocked/invalid primary thumbnails can fall back to another real image without granting visual approval to an unreadable image. The displayed audit image follows the image actually read.
2. Image-search Serper Shopping lanes can recover merchant product links using the existing targeted merchant lookup. Recovery is limited to three selected cards per image/market, at most two per invocation, within up to 2.5 seconds of the existing lane deadline. Queries stay in the selected country. Prices are copied from a shopping card only under the existing same-merchant/exact-normalized-title rule.
3. Photo candidate admission accepts a salient product term without requiring multiple decorative terms. Added multilingual rug and ceiling-light vocabulary addresses examples in the logs. Brand/colour/marketing words alone are insufficient. Final visual approval, product-form checks, numeric specifications and country checks still apply.
4. Assistant-selected changes travel to the visual auditor separately from observed photo/OCR facts. They also enter the proof cache identity, preventing a previous colour request's proof from being reused as the new request's proof. The original photo remains intact.
5. For photo refinement, if a listing omits colour, a sufficiently clear audited candidate-image colour can be used. This colour evidence is bound to the current offer/title/image; changing the image invalidates it. Listing colour takes precedence. Missing evidence remains unconfirmed.
6. New diagnostic lines distinguish image download/decode failures, recovered images, recovered merchant links, and missing local evidence versus explicit foreign signals.

## Verify after deployment

The API startup log must show: v128.5.42.35-image-recovery

Repeat the same rug, pendant-light and shoe photos in Saudi Arabia and Kuwait. Then test one European market and US/China. From an image result, open the assistant and change a colour without removing the photo. Repeat the request with a different colour. Check new results, the actual merchant product page and its price.

Useful log prefixes:
- PHOTO SHOPPING RECOVERY: attempted merchant recovery and accepted rows.
- VISUAL IMAGE FETCH: recovered alternative image or the failure types.
- LOCAL GEO REJECT: host and rejection reason (no full customer URL).

Do not use raw provider counts as the number of display-ready offers. Use the final priced, image-available, visually admitted results.

## Validation and limits

24 offline regression tests passed (15 new image-recovery tests plus 9 existing prelaunch tests). They cover image fallback/decoding/cancellation/deadlines, unchanged original-photo transport, colour proof cache separation, stale colour proof rejection, merchant/variant price separation, and bounded recovery for sa/kw/fr/de/us/cn. Python compilation and whitespace checks passed.

Run: python3 -m unittest discover -s tests -v
Pillow is used for real image decoding in the tests and is already a project dependency.

External provider responses are controlled fixtures in these tests. This is not a live provider or iPhone end-to-end benchmark. No claim is made that every market now returns offers, or that every provider outage is resolved. Shopping recovery adds bounded provider requests when needed; it is not cost-free. More eligible photo candidates may reach the existing bounded AI audit. Broad launch should follow the live checks above.

The existing SerpApi merchant-store expansion is retained. Official schema reference reviewed: https://serpapi.com/google-immersive-product-stores . A Google catalog link is still not presented as a direct merchant product URL.

## Rollback

Restore the previous main.py (v128.5.42.34-launch-review) and redeploy the API service. Keep its findzia_search_quality.py dependency. No database rollback is needed.
