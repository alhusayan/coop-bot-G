Run from this ZIP root with the application's dependencies:
PYTHONPATH=.:verification python3 -m unittest discover -s verification -p 'test_*.py'
Expected: 257 tests. Network/provider boundaries are simulated. SQLite persistence,
cache admission, expiry and the actual production functions/adapters run locally.
Only the five Python files at the ZIP root belong in the deployment.
Fixtures under verification are not replacements for runtime account/billing files.
25 new tests: test_cache_policy_81.py. Previous failed-price-cache expectation now
requires one new request on the next search; circuit/rate-limit tests remain intact.
