"""Offline credit admission regressions; no provider or production DB calls."""
import asyncio
import tempfile
import time
import unittest
import uuid
from pathlib import Path

from fastapi import HTTPException
from findzia_accounts import Accounts
from findzia_billing import Credits


class CreditRetries(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.accounts = Accounts({
            'FINDZIA_ACCOUNT_DB': str(Path(self.tmp.name) / 'accounts.sqlite'),
            'FINDZIA_ACCOUNT_API_URL': 'https://api.findzia.com',
        })
        self.assertTrue(self.accounts.available)
        self.credits = Credits(self.accounts, {})
        self.addCleanup(lambda: asyncio.run(self.credits.runtime.close()))

    def member(self, kind='pack', quantity=10):
        member = uuid.uuid4().hex
        now = int(time.time())
        with self.accounts.connect() as db:
            db.execute('INSERT INTO fz_members(id,provider,subject,email,name,created) VALUES(?,?,?,?,?,?)',
                       (member, 'google', member, '', '', now))
            db.execute('INSERT INTO fz_credit_grants VALUES(?,?,?,?,?,?,?,?,0)',
                       ('grant:' + member, member, kind, kind, quantity, quantity, now, None))
        return member

    def reserve(self, member, path='/api/search/stream', rid=None):
        rid = rid or uuid.uuid4().hex
        self.credits.reserve(member, rid, path)
        return rid

    def expect_error(self, code, detail, action):
        with self.assertRaises(HTTPException) as caught:
            action()
        self.assertEqual((caught.exception.status_code, caught.exception.detail), (code, detail))

    def test_more_than_five_refunds_allow_text_and_photo_retry(self):
        for kind in ('trial', 'pack', 'subscription'):
            for path in ('/api/search/stream', '/api/search/image/stream'):
                with self.subTest(kind=kind, path=path):
                    member = self.member(kind)
                    for _ in range(8):
                        rid = self.reserve(member, path)
                        self.credits.finish(member, rid, False)
                    self.assertEqual(self.credits.status(member)['remaining'], 10)
                    self.credits.finish(member, self.reserve(member, path), True)
                    self.assertEqual(self.credits.status(member)['remaining'], 9)

    def test_duplicate_request_and_duplicate_refund_do_not_grant_credit(self):
        member = self.member()
        rid = self.reserve(member)
        self.credits.finish(member, rid, False)
        self.credits.finish(member, rid, False)
        self.expect_error(409, 'search_already_processed', lambda: self.reserve(member, rid=rid))
        self.assertEqual(self.credits.status(member)['remaining'], 10)

    def test_two_active_searches_still_block_third_until_completion(self):
        member = self.member()
        first = self.reserve(member)
        self.reserve(member)
        self.expect_error(429, 'search_in_progress', lambda: self.reserve(member))
        self.assertEqual(self.credits.status(member)['remaining'], 8)
        self.credits.finish(member, first, False)
        self.reserve(member)
        self.assertEqual(self.credits.status(member)['remaining'], 8)

    def test_successful_searches_still_spend_and_exhaust_credit(self):
        member = self.member(quantity=2)
        for _ in range(2):
            self.credits.finish(member, self.reserve(member), True)
        self.expect_error(402, 'credits_exhausted', lambda: self.reserve(member))
        self.assertEqual(self.credits.status(member)['remaining'], 0)

    def test_existing_refund_history_does_not_require_database_reset(self):
        member = self.member()
        for _ in range(5):
            self.credits.finish(member, self.reserve(member), False)
        # Recreate the service as a deployment would, keeping the same ledger.
        replacement = Credits(self.accounts, {})
        self.addCleanup(lambda: asyncio.run(replacement.runtime.close()))
        rid = uuid.uuid4().hex
        replacement.reserve(member, rid, '/api/search/image/stream')
        replacement.finish(member, rid, True)
        self.assertEqual(replacement.status(member)['remaining'], 9)


if __name__ == '__main__':
    unittest.main()
