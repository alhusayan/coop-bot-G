Run Python regressions from the extracted ZIP or repository root:
python3 -m unittest discover -s verification -p 'test_*.py'

Expected: 116 tests. Production functions are loaded by AST with simulated
provider/HTTP boundaries. The full ASGI application was not imported locally.
The unchanged media module is provided as a fixture when absent at root.

Browser checks require the complete repository frontend, Playwright and Chromium:
node frontend/scripts/build.mjs
NODE_PATH=<node_modules> FINDZIA_TEST_CHROME=<chromium> node frontend/tests/media-routing.cjs
Expected: 43 assertions, including real page text/camera flows and first-card metrics.
All external services/payments are mocked. No live paid provider tests were run.

The optional photo-upload-69.cjs helper suite is unchanged; its previous report
is not claimed as a rerun for this release. The camera flow was tested end to end
in media-routing.cjs, including actual canvas preparation and submitted bytes.

Only four runtime files are replacements. Keep all other repository files.
Unchanged credit middleware was compared to the current GitHub blob and its
explicit charged-path set excludes /api/search/metrics.

changes.patch is relative to commit abc1ecaf7c40bdd535bb1da0f7b8b304933c41a5.
Client rendering telemetry is observational, untrusted and allowlisted. It does
not authorize products, affect billing, or prove pixel/price/identity quality.
