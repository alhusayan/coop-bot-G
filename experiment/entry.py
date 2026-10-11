"""Load the byte-exact saved backend with dependencies in its own namespace."""
from pathlib import Path
import re

_path = Path(__file__).with_name('main.py')
_source = _path.read_text()
_source = re.sub(r'(?m)^(\s*from )(findzia_\w+)(\b)', r'\1experiment.\2\3', _source)
_source = re.sub(r'(?m)^(\s*import )(findzia_\w+)(\s+as\b)', r'\1experiment.\2\3', _source)
_source = _source.replace(
    "CACHE_DB_PATH = os.environ.get('CACHE_DB_PATH', '/tmp/coop_search_cache.sqlite3')",
    "CACHE_DB_PATH = os.environ.get('CACHE_DB_PATH', '/tmp/coop_search_cache.sqlite3') + '.test-c18f61f'",
)
exec(compile(_source, str(_path), 'exec'), globals())
