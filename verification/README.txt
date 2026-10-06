Run from the extracted ZIP or from the repository root:

python3 -m unittest discover -s verification -p 'test_*.py' -v

These tests run production functions loaded by AST. Network/provider classes
are simulated; they do not start the complete ASGI app or call paid services.
The unchanged .67 media module is included as a verification-only fixture.
An existing root findzia_product_media.py takes precedence when present.

Expected: 80 tests pass. Eighteen tests are new for .68.
baseline-regression.txt records three actual failures on the .67 main.py.
Those failures concern simulated error shapes; the original production error
body was not retained, so these are not proof of its exact upstream cause.

Only main.py is a runtime replacement. Do not upload verification to deploy.
