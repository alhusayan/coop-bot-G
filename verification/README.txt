Run Python regressions from the extracted ZIP or repository root:
python3 -m unittest discover -s verification -p 'test_*.py' -v

Expected: 95 tests. Python uses AST-loaded production code with simulated HTTP
providers; it does not import the complete application's ASGI startup.
The unchanged .67 media module is a fixture if no root module is present.

Browser tests require the complete existing frontend, Playwright, and Chromium:
node frontend/scripts/build.mjs
NODE_PATH=<node_modules> FINDZIA_TEST_CHROME=<chromium> node frontend/tests/photo-upload-69.cjs
NODE_PATH=<node_modules> FINDZIA_TEST_CHROME=<chromium> node frontend/tests/media-routing.cjs

Expected: 12 upload checks and 26 full-page checks. External services are mocked.
The ZIP includes only changed frontend runtime files; apply it to the repository
before building. Browser test fixture sources are included for reproducibility.

No live Gemini comparison was possible: Railway's OAuth connection redacts the
API key and runtime tracing is off. .69 makes one conditional comparison during
an already authorized search after a specific invalid-argument/schema rejection.
It must be verified after the user deploys the prepared update.
