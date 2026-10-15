# Apple consumable credits

The optional `findzia_apple` adapter adds verified StoreKit delivery alongside the existing web gateways. It does not change Paddle prices or the website payment provider.

Product IDs: `com.findzia.spaces.credits30`, `.credits80`, `.credits180` map to the existing Space Starter/Plus/Pro plans (30/80/180 flexible credits).

Configuration on the primary account API:

- `FINDZIA_IAP_APP_APPLE_ID`: numeric App Store Connect app ID for `com.findzia.spaces`.
- `FINDZIA_IAP_ENABLED=true`: expose production purchases after product/account setup is complete. Default false.
- `FINDZIA_IAP_SANDBOX_MEMBERS`: explicit comma-separated Findzia member IDs for sandbox/TestFlight/review. Sandbox is denied for all other members, even with production purchases enabled. Arrange reviewer access before submitting an app.

POST `/api/billing/apple/context` and `/transactions` require a first-party Origin and valid account Bearer session. The app uses a server-issued stable UUID as StoreKit appAccountToken. Signed product identity determines credits; price/currency may vary by storefront and is not trusted as a client input. Transaction IDs are unique within their Apple environment. Grant insertion, ledger insertion and refund tombstones use the same SQLite transaction.

Configure App Store Server Notifications V2 (production and sandbox) at `https://api.findzia.com/api/billing/apple/notifications`. The route verifies both outer and nested Apple JWS data; refund/revoke removes the remaining balance of that grant. Configure and test notifications before opening sales. Other notifications do not mint consumable credits. Unfinished app transactions recover on launch/foreground/sign-in; delivery precedes StoreKit finish.

The official Apple Python server library is pinned to 3.1.2 (includes the OCSP freshness fix). Public Apple roots and source URLs/checksums are bundled under `apple-roots`. No client-side receipt trust, API private key or secret in the app. Local Xcode StoreKit test signatures are rejected.

Run `python3 -m unittest test_findzia_apple test_space_credits`. Actual Apple sandbox purchases and notification delivery still require a configured App Store Connect app and device/TestFlight testing.
