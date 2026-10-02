# Findzia Prelaunch Review — 156.7.28

This is an incremental patch for the current repository (base commit 924a50f), not a complete standalone project. It has NOT been deployed to production.

## Install

1. Back up your current repository or retain the previous commit for rollback.
2. Extract this ZIP. Merge its files into the existing repository, preserving the exact folder paths. Do not upload the ZIP itself. Do not create a second frontend folder inside frontend.
3. Upload root `findzia_search_quality.py` and replace root `main.py` IN THE SAME COMMIT. If uploading separately, upload the new helper first, then main.py. Both files belong to the API service.
4. Replace the files inside the existing `frontend` folders with the matching files in this patch. Keep every other existing file. `frontend/source/findzia-billing.js` is the source file; do not upload it at repository root or into public.
5. Deploy the API service from repository root and Findzia Web from `/frontend`. No environment-variable changes or database migration are required. Keep your current payment-provider configuration.
6. The frontend Docker build generates public assets. Do not manually copy old public assets over the new build.

## Verify the deployment

- Frontend `/health.json` should report version 156.7.28.
- API startup should report v128.5.42.34-launch-review.
- Run `python3 frontend/scripts/preflight.py --production` from the repository root.
- Run `python3 -m unittest discover -s tests -v` and `npm --prefix frontend test` for offline regression checks. Build first with `npm --prefix frontend run build`.

## Required live acceptance checks before a broad launch

1. On iPhone Safari, search with a real product photo, open the assistant, change colour/size, and search without removing the photo. Confirm the new preferences reach new results. Repeat after a failed request.
2. Test the three plans, including the $9.99 and $19.99 subscriptions, with the account owner: successful checkout, cancelled wallet, declined payment, retry, and purchase restoration. Confirm credits are granted exactly once after a verified successful payment, never after a decline.
3. Check representative countries and local-language searches used by your customers. This review did not exhaustively test all countries or product categories.

If a separate buy.paddle.com Apple Pay page freezes, this patch cannot change that hosted page. It improves handling when Paddle sends a failure event to Findzia; provider-side hosted failures still require Paddle investigation.

## Rollback

Restore the prior versions of the modified files as one commit and redeploy both services. The new helper can remain unused. No database rollback is needed.
