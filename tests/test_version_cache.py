"""The ASGI entry point must initialize every schema on its actual cache file."""
import ast
import os
from pathlib import Path
import runpy
import sqlite3
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch


class VersionCacheTests(unittest.TestCase):
    def test_isolated_cache_has_real_schemas_before_serving_requests(self):
        source = ast.parse(Path('main.py').read_text())
        names = {'_cache_db_connect', '_cache_db_init', '_serpapi_cache_db_init',
                 '_web_ai_classifier_db_init', '_ai_db_init'}
        nodes = [node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in names]
        with tempfile.TemporaryDirectory() as folder:
            original = types.ModuleType('main')
            original.__dict__.update(os=os, sqlite3=sqlite3, time=time,
                CACHE_DB_PATH=str(Path(folder) / 'cache.sqlite3'), CACHE_DB_LOCK=threading.RLock(),
                SERPAPI_RESULT_CACHE_ENABLED=True, WEB_AI_CLASSIFIER_ENABLED=True, app=object())
            exec(compile(ast.Module(body=nodes, type_ignores=[]), 'real-cache-schemas', 'exec'), original.__dict__)
            with sqlite3.connect(original.CACHE_DB_PATH) as db:
                db.execute('CREATE TABLE previous_cache_marker (value TEXT)')
            base_path = original.CACHE_DB_PATH
            with patch.dict(sys.modules, {'main': original}):
                runpy.run_path('findzia_versions.py')
            self.assertEqual(original.CACHE_DB_PATH, base_path + '.original-a332321')
            with sqlite3.connect(original.CACHE_DB_PATH) as db:
                tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue({'search_cache', 'user_preferences', 'serpapi_response_cache',
                'ai_result_classification_cache', 'ai_price_history', 'ai_price_alerts'} <= tables)
            self.assertNotIn('previous_cache_marker', tables)
            with sqlite3.connect(base_path) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM previous_cache_marker').fetchone()[0], 0)
