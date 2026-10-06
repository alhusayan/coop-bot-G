"""Findzia 156.7.44: isolated credit work and durable search completion.

A credit is reserved BEFORE retrieval. An observed outcome is fsynced beside
the account database BEFORE the final response is sent. SQLite settlement may
then retry without keeping the browser stream open. The journal is private,
server-authored, and replayed after restart; it cannot grant purchases.
"""
import asyncio
import functools
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor


class SettlementJournal:
    def __init__(self, accounts):
        filename = getattr(accounts, 'db_path', None) or getattr(accounts, 'path', None)
        self.directory = Path(str(filename) + '.settlements') if filename else None

    def path(self, member, request):
        if self.directory is None:
            raise OSError('settlement_storage_unavailable')
        key = hashlib.sha256((member + '\0' + request).encode()).hexdigest()
        return self.directory / (key + '.json')

    def read(self, member, request):
        try:
            data = json.loads(self.path(member, request).read_text())
        except FileNotFoundError:
            return None
        if (not isinstance(data, dict) or data.get('member') != member or data.get('request') != request or
            type(data.get('success')) is not bool or data.get('version') != 1):
            raise ValueError('invalid_settlement_record')
        return data

    def save(self, member, request, success):
        path = self.path(member, request)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        existing = self.read(member, request)
        if existing is not None:
            return existing
        data = dict(version=1, member=member, request=request, success=bool(success))
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=self.directory, prefix='.pending-', delete=False) as out:
                temporary = out.name
                json.dump(data, out, separators=(',', ':'))
                out.flush()
                os.fsync(out.fileno())
            os.replace(temporary, path)
            temporary = None
            # Persist the directory entry as well as its contents before replying.
            fd = os.open(self.directory, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            if temporary:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass
        return data

    def remove(self, member, request):
        # A surviving journal after a crash is harmless: settlement is idempotent.
        self.path(member, request).unlink(missing_ok=True)

    def pending(self, limit=64):
        if self.directory is None or not self.directory.exists():
            return []
        rows = []
        for path in self.directory.glob('*.json'):
            try:
                data = json.loads(path.read_text())
                member, request = data['member'], data['request']
                if path != self.path(member, request):
                    raise ValueError('invalid_settlement_path')
                rows.append(self.read(member, request))
            except FileNotFoundError:
                continue  # Another worker just committed and removed this record.
            except (ValueError, KeyError, TypeError):
                print('CREDITS_SETTLEMENT journal_invalid', flush=True)
            if len(rows) >= limit:
                break
        return [row for row in rows if row is not None]


class CreditRuntime:
    def __init__(self, credits):
        self.credits = credits
        self.journal = SettlementJournal(credits.accounts)
        # Provider/AI jobs must not starve admission, balance reads, or completion.
        self.read_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='credits-read')
        self.write_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='credits-write')
        self.tasks = set()
        self.worker_task = None

    async def run(self, function, *args, write=False):
        return await asyncio.get_running_loop().run_in_executor(
            self.write_pool if write else self.read_pool, functools.partial(function, *args))

    def track(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        def finished(done):
            self.tasks.discard(done)
            if not done.cancelled():
                error = done.exception()
                if error is not None and getattr(error, 'status_code', 500) >= 500:
                    print('CREDITS_TASK failed kind=%s' % type(error).__name__, flush=True)
        task.add_done_callback(finished)
        return task

    async def complete(self, member, request, success):
        try:
            record = await self.run(self.journal.save, member, request, success)
        except (OSError, ValueError, TypeError):
            # If durable storage fails, commit synchronously. Never acknowledge
            # an unrecorded outcome and later refund a successful search.
            await self.run(self.credits.finish, member, request, success, write=True)
            return
        self.track(self.apply(record))

    async def apply(self, record):
        try:
            await self.run(self.credits.finish, record['member'], record['request'], record['success'], write=True)
            await self.run(self.journal.remove, record['member'], record['request'])
        except (OSError, sqlite3.Error):
            # Reservation still owns the credit, and its outcome is durable.
            # Startup/maintenance retries; the browser need not wait on the lock.
            print('CREDITS_SETTLEMENT deferred_retry', flush=True)

    async def replay(self):
        for record in await self.run(self.journal.pending):
            await self.apply(record)

    async def worker(self):
        last_recovery = 0
        while True:
            try:
                await self.replay()
                if time.monotonic() - last_recovery >= 30:
                    await self.run(self.credits.recover_expired, write=True)
                    last_recovery = time.monotonic()
            except (OSError, sqlite3.Error, ValueError):
                print('CREDITS_MAINTENANCE retry_pending', flush=True)
            await asyncio.sleep(2)

    def start(self):
        if self.worker_task is None and self.credits.available:
            self.worker_task = asyncio.create_task(self.worker())

    async def close(self):
        if self.worker_task:
            self.worker_task.cancel()
            await asyncio.gather(self.worker_task, return_exceptions=True)
        if self.tasks:
            _, pending = await asyncio.wait(tuple(self.tasks), timeout=2)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
        # Persisted records will replay on startup if a write is still blocked.
        self.read_pool.shutdown(wait=False)
        self.write_pool.shutdown(wait=False)
