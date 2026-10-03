# Findzia 156.7.35 — Manage subscription inside Findzia

This patch replaces the **Manage subscription** redirect with a native Findzia screen. Subscription and payment data come from Paddle through your authenticated Findzia API.

Apply it to the existing Findzia project with the 156.7.34 frontend. This is a patch, not a replacement repository. Keep the other project files.

## What customers can do

- See their plan, status, start date, monthly search allowance and remaining searches.
- See the next payment date, amount, products, discount and tax breakdown.
- Browse Paddle payments, including one-time packs and subscription renewals, with older-payment pagination.
- Open payment details, billing information and available payment-method details.
- Download an available invoice PDF and correct eligible invoice details.
- Cancel renewal at the end of the current billing period, with an explicit confirmation.
- Undo a scheduled cancellation before it takes effect, when Paddle permits it.
- Update the payment method using Paddle's secure inline checkout inside the Findzia screen.

The interface follows Findzia's light/dark appearance and supports English and Arabic, including right-to-left layout. Amounts, currencies and taxes are read from Paddle; they are not hardcoded from the screenshots.

## Files to install

There are **8 application files**. Preserve these exact paths:

| Railway service | Repository path | Action |
| --- | --- | --- |
| API | `findzia_paddle.py` | Replace |
| API | `findzia_subscription_manager.py` | Add — new file |
| Findzia Web | `frontend/source/findzia-home.liquid` | Replace |
| Findzia Web | `frontend/source/findzia-shell.js` | Replace |
| Findzia Web | `frontend/source/findzia-billing.js` | Replace |
| Findzia Web | `frontend/source/findzia-subscriptions.js` | Add — new file |
| Findzia Web | `frontend/scripts/build.mjs` | Replace |
| Findzia Web | `frontend/package.json` | Replace |

The test files included under `tests/` and `frontend/tests/` are for verification. They are not additional production services.

### GitHub and Railway steps

1. Extract the ZIP on your computer.
2. In the existing GitHub repository, upload the two API Python files to the repository root, beside the current `findzia_paddle.py`. Commit them together. Let the **API** service deploy successfully.
3. Upload the frontend files into their matching folders. In GitHub, open `frontend/source` before uploading the four source files; open `frontend/scripts` for `build.mjs`; put `package.json` directly in `frontend`. Commit these six frontend files together.
4. Deploy **Findzia Web**, keeping its Root Directory as `/frontend`. Its existing Dockerfile runs the updated build script automatically.
5. Open `https://findzia.com/healthz`. The `version` must be `156.7.35`, and `sourceReleases.home`, `shell`, `billing` and `subscriptions` must all be `156.7.35`.
6. Reload Findzia, sign in, then open **Account → Subscription → Manage subscription**. Compare the plan, next payment and payment history with the corresponding Paddle account.

If the frontend is in a separate repository, its root already represents `frontend`: upload `source/...`, `scripts/build.mjs` and `package.json` there, and keep that service's Root Directory as `/`.

Upload the extracted files, not the ZIP. Do not create a second nested `frontend/frontend` folder. The build deliberately rejects mixed versions of the six frontend application files.

## Configuration

The patch uses the existing Paddle environment, API key, client token and webhook configuration in the **API service**. Keep payment secrets out of the frontend service.

No new environment variable is required. In particular, this patch does not require changing `FINDZIA_MYFATOORAH_ENABLED` or the current choice of purchase provider.

The Paddle API key must allow:

- Reading and writing subscriptions, for subscription details and renewal changes.
- Reading and writing transactions, for payment history, invoices and invoice corrections.
- Reading customers, addresses and businesses, for expanded billing details.

If the screen reports that billing access needs attention, check the existing key's permissions in Paddle. Provider authorization errors are reported as `management_permission_required`; secret values are never returned to the browser.

Existing live customers can manage their subscriptions even if `FINDZIA_PADDLE_LIVE_OPEN=false` temporarily closes new purchases. Sandbox management retains the configured test-email restriction.

## Supported behavior and provider limits

**Payment-method update:** an active subscription uses Paddle's zero-value method-update transaction. It does not create a new Findzia purchase or grant search credits. For an overdue subscription, Paddle may collect the existing overdue transaction; the amount is disclosed before the secure form. Completion is checked on the server, not inferred from a browser event. Card and wallet availability still follows Paddle and the customer's device. Bank or wallet authentication may open its own system flow.

**Cancellation:** the app requests cancellation at the next billing period. It does not issue refunds or cancel an active paid period immediately. Removing a scheduled cancellation resumes the existing renewal schedule. Ended subscriptions cannot be reinstated through this action. Paddle restricts changes for overdue subscriptions and close to the next billing time; the provider remains authoritative.

**Invoices:** the correction form is available only for eligible, unrevised invoices. Paddle permits one revision. Customers can correct names, business/tax information and supported address fields; this flow does not change the email, country, postal code or purchase amount. Adding a valid tax identifier can trigger a tax refund calculated by Paddle. A tax-only refund preserves the purchased search credits. The existing handling of product refunds and chargebacks remains in place.

**Downloads:** invoice PDFs use Paddle's short-lived download URL. Downloading a file may open a browser PDF view; it does not redirect the subscription-management screen to Paddle's portal.

**Account matching:** history is limited to Paddle checkouts and subscriptions already mapped to the signed-in Findzia account. Email alone is never treated as proof of ownership. MyFatoorah purchases are not included in this Paddle history.

## Data and deployment notes

- The new module adds two small tables to the existing account database for action locks and method-update transaction ownership. It does not replace or clear the database.
- Existing webhook processing remains responsible for credit reconciliation. The UI cannot grant credits by itself.
- No API `main.py` change is needed. `install_paddle()` registers the new management routes.
- The 156.7.34 photo/text search code is preserved. `findzia-shell.js` changes only its release marker so the frontend build stays consistent.
- The Apple Pay verification file, DNS, frontend server, account module and search-provider configuration are not replaced by this patch.

## Verification

The update was tested locally with fake Paddle responses and disposable SQLite databases. No live payment, cancellation, invoice revision or customer-account change was performed.

Passed checks include 22 subscription-management tests, 17 applicable checkout regression tests, 32 frontend/build tests, English/light and Arabic/dark mobile management flows, and the existing mobile photo-refinement flows. See `TEST_REPORT.txt` for scope and limits.

After applying the patch to the full repository, the included API tests can be run with:

```bash
python3 -m unittest discover -s tests -p test_subscription_manager.py -v
python3 -m unittest discover -s tests -p test_paddle_checkout_regression.py -v
```

The management tests use the project's existing FastAPI/requests dependencies and `httpx` for the local test client.

Frontend checks:

```bash
cd frontend
npm run build
npm test
```

The additional browser test requires Playwright and Chromium:

```bash
FINDZIA_TEST_CHROME=/path/to/chromium node tests/subscriptions-browser.cjs
```

## Official Paddle references

- [Get subscription details](https://developer.paddle.com/api-reference/subscriptions/get-subscription/)
- [Update subscription payment details](https://developer.paddle.com/build/subscriptions/update-payment-details/)
- [Cancel subscriptions](https://developer.paddle.com/build/subscriptions/cancel-subscriptions/)
- [List transactions](https://developer.paddle.com/api-reference/transactions/list-transactions/)
- [Download an invoice](https://developer.paddle.com/api-reference/transactions/get-transaction-invoice/)
- [Revise an invoice](https://developer.paddle.com/api-reference/transactions/revise-transaction/)
