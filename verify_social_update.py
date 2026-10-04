"""Run offline checks after placing this update in the existing Findzia repo.

Install existing requirements and httpx first. Provider requests are mocked.
Use separate processes so application imports cannot leak across suites.
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    regression = """
from pathlib import Path
import unittest
import test_searchapi, test_hybrid, test_hybrid_quality, test_launch_review
test_launch_review.ROOT = Path.cwd()
suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m)
    for m in (test_searchapi, test_hybrid, test_hybrid_quality, test_launch_review))
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
"""
    commands = [
        [sys.executable, '-c', regression],
        [sys.executable, '-m', 'unittest', '-v', 'test_social'],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
