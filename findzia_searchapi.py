"""SearchApi primary transport; one bounded SerpApi rescue per logical request.

Provider fields are adapted at the boundary. Product verification stays in main.
No keys, search text, image URLs or upstream error messages enter logs.
"""
import copy
import hashlib
import json
import math
import os
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError, wait, FIRST_COMPLETED

import requests
from findzia_cache import provider_cacheable

SUPPORTED = frozenset(('google', 'google_light', 'google_images',
                       'google_images_light', 'google_shopping', 'google_shopping_light', 'google_lens', 'baidu'))


def _number(name, default, low, high):
    try:
        value = float(os.environ.get(name, default))
        return min(high, max(low, value)) if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def _seconds(timeout):
    values = timeout if isinstance(timeout, (tuple, list)) else (timeout,)
    try:
        total = sum(max(0., float(v)) for v in values if v is not None)
        return total if math.isfinite(total) else 18.
    except (TypeError, ValueError):
        return 18.


def _url(value):
    if isinstance(value, dict):
        value = value.get('link') or value.get('url')
    return value if isinstance(value, str) else ''


def searchapi_params(params):
    """Do not forward SerpApi credentials, tokens, or vendor-only controls."""
    engine = params.get('engine')
    if engine not in SUPPORTED:
        return None
    if engine == 'google_shopping_light':
        engine = 'google_shopping'
    if engine == 'google_lens':
        if not params.get('url'):
            return None  # SerpApi-owned image_id cannot be used at SearchApi.
        allowed = ('url', 'q', 'country', 'hl', 'device', 'crop')
        out = {k: params[k] for k in allowed if params.get(k) is not None}
        out['search_type'] = params.get('type') or 'all'
        if out['search_type'] == 'exact_matches':
            out.pop('q', None)
            out['safe_search'] = params.get('safe', 'active')
        # SearchApi does not expose SerpApi's auto_crop switch. Preserve the
        # original image URL; never silently add a guessed bounding box.
    elif engine == 'baidu':
        out = {k: params[k] for k in ('q', 'ct', 'gpc', 'num', 'page') if params.get(k) is not None}
        if 'ct' in out:
            # SerpApi: 1/all, 2/simplified, 3/traditional; SearchApi: 0/1/2.
            out['ct'] = {1: 0, 2: 1, 3: 2}.get(int(out['ct']), 0)
        if 'pn' in params:
            out['page'] = max(1, int(params['pn']) // max(1, int(params.get('rn', 10))) + 1)
        if 'rn' in params:
            out['num'] = min(50, int(params['rn']))
    else:
        allowed = ('q', 'gl', 'hl', 'location', 'uule', 'device', 'google_domain',
                   'nfpr', 'safe', 'filter', 'tbs', 'cr', 'lr', 'page')
        if engine == 'google_shopping':
            allowed = ('q', 'gl', 'hl', 'location', 'uule', 'page', 'shoprs')
        out = {k: params[k] for k in allowed if params.get(k) is not None}
        if 'start' in params:
            out['page'] = max(1, int(params['start']) // 10 + 1)
        if engine == 'google_shopping' and str(params.get('direct_link')).lower() == 'true':
            out['link'] = 'resolved'
    out['engine'] = engine
    return out


def _row(raw, lens=False):
    row = copy.deepcopy(raw)
    source = row.get('source')
    if isinstance(source, dict):
        row['link'] = row.get('link') or _url(source)
        row['source'] = source.get('name') or ''
    elif not source and isinstance(row.get('seller'), str):
        row['source'] = row['seller']
    for key in ('image', 'original', 'thumbnail'):
        if isinstance(row.get(key), dict):
            row[key] = _url(row[key])
    row['thumbnail'] = row.get('thumbnail') or _url(row.get('image')) or _url(row.get('original'))
    if not row.get('link') and row.get('product_link'):
        row['link'] = row['product_link']  # Still a Google link; existing resolver validates it.
    if row.get('original_price') is not None:
        row.setdefault('old_price', row['original_price'])
        row.pop('original_price', None)  # main uses original_price for the *current* raw price.
    if row.get('extracted_original_price') is not None:
        row.setdefault('extracted_old_price', row['extracted_original_price'])
    if row.get('installment'):
        row['installments_description'] = json.dumps(row['installment'], ensure_ascii=False)
    if lens and not isinstance(row.get('price'), dict) and row.get('price') is not None:
        row['price'] = {'value': row['price'], 'extracted_value': row.get('extracted_price'),
                        'currency': row.get('currency') or ''}
    if 'in_stock' not in row:
        stock = str(row.get('stock_information') or '').strip().lower()
        if stock in ('in stock', 'out of stock'):
            row['in_stock'] = stock == 'in stock'
    return row


def normalize(data, engine):
    if not isinstance(data, dict) or data.get('error') or data.get('errors'):
        return None
    metadata = data.get('search_metadata')
    if isinstance(metadata, dict) and str(metadata.get('status', 'success')).lower() not in ('success', 'completed'):
        return None
    # A metadata-only success is malformed, but an explicit empty array is a
    # legitimate no-result query and must not trigger a paid rescue by itself.
    fields = ('visual_matches', 'exact_matches', 'products') if engine == 'google_lens' else (
        ('images', 'images_results') if engine in ('google_images', 'google_images_light') else (
            ('shopping_results', 'shopping_ads', 'categorized_shopping_results', 'popular_products')
            if engine == 'google_shopping' else ('organic_results', 'shopping_ads', 'ads', 'knowledge_graph', 'answer_box')))
    if not any(isinstance(data.get(k), (list, dict)) for k in fields):
        return None
    out = copy.deepcopy(data)
    # Keep only diagnostic metadata, never echoed credentials/request URLs.
    out['search_metadata'] = {'status': 'Success', 'provider': 'searchapi', 'engine': engine}
    if isinstance(metadata, dict):
        out['search_metadata']['id'] = str(metadata.get('id') or '')
    out.pop('search_parameters', None)
    for field in ('organic_results', 'images_results', 'shopping_results',
                  'inline_shopping_results', 'visual_matches', 'exact_matches', 'products'):
        values = out.get(field)
        if isinstance(values, dict):
            values = values.get('results')
        if isinstance(values, list):
            out[field] = [_row(r, engine == 'google_lens') for r in values if isinstance(r, dict)]
    if engine in ('google_images', 'google_images_light'):
        out['images_results'] = [_row(r) for r in data.get('images', data.get('images_results', [])) if isinstance(r, dict)]
        out.pop('images', None)
    if isinstance(data.get('shopping_ads'), list):
        ads = [_row(r) for r in data['shopping_ads'] if isinstance(r, dict)]
        target = 'shopping_results' if engine == 'google_shopping' else 'inline_shopping_results'
        out[target] = out.get(target, []) + ads
    if engine == 'google_shopping':
        out['shopping_results'] = out.get('shopping_results', []) + [
            _row(r) for r in data.get('popular_products', []) if isinstance(r, dict)]
        for group in out.get('categorized_shopping_results', []):
            if isinstance(group, dict):
                group['shopping_results'] = [_row(r) for r in group.get('shopping_results', []) if isinstance(r, dict)]
    return out


class _BoundedPool:
    def __init__(self, workers, name):
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix=name)
        self.slots = threading.BoundedSemaphore(workers)

    def submit(self, fn, *args):
        if not self.slots.acquire(blocking=False):
            return None
        try:
            future = self.pool.submit(fn, *args)
        except BaseException:
            self.slots.release()
            raise
        future.add_done_callback(lambda _: self.slots.release())
        return future


class SerperTransport:
    """One Serper HTTP call per distinct body, shared across all hybrid lanes.

    There is deliberately no provider fallback here. The Lens router below
    owns the SearchApi -> SerpApi rescue; missing Serper results cannot fan out
    to those more expensive engines. Late paid work is retained in the cache.
    """
    def __init__(self, *, cache_get, cache_put, cost):
        self.cache_get, self.cache_put, self.cost = cache_get, cache_put, cost
        self.total = _number('SERPER_TOTAL_TIMEOUT_SECONDS', 12., .1, 30.)
        self.pool = _BoundedPool(32, 'hybrid-serper')
        self.lock = threading.Lock()
        self.inflight = {}

    def search(self, kind, body, timeout, fetch, normalize, *, bypass=False):
        seconds = min(self.total, _seconds(timeout))
        if seconds <= .01 or kind not in ('search', 'images', 'shopping'):
            return None
        def request_key(value):
            return hashlib.sha256(('serper-hybrid-v2:' + json.dumps(
                [kind, value], sort_keys=True, ensure_ascii=False)).encode()).hexdigest()
        key = request_key(body)
        # A narrow first-page listing lookup can consume an already-paid
        # broader response. Every other parameter must be identical. Do not
        # reuse ten results for a discovery request that needs twenty, or
        # reuse another page/market/language/autocorrect policy.
        wider_key = (request_key(dict(body, num=20)) if kind == 'search'
                     and body.get('num') == 10 and body.get('page', 1) == 1 else None)
        def cached():
            if bypass:
                return None
            hit = self.cache_get(key)
            if not provider_cacheable(hit) and wider_key:
                hit = self.cache_get(wider_key)
                if provider_cacheable(hit):
                    self.cost('serper_wider_cache_hits')
            return hit if provider_cacheable(hit) else None
        hit = cached()
        if isinstance(hit, dict):
            self.cost('serper_cache_hits')
            return copy.deepcopy(hit)
        def run():
            connect = min(1.5, seconds / 4)
            # The future bounds the caller's wall time. Image reads get the full
            # window even when the connection was faster than its allowance.
            raw = fetch(kind, copy.deepcopy(body), (connect, seconds if kind == 'images' else seconds-connect))
            if not isinstance(raw, dict) or raw.get('error'):
                return None
            sections = ('images',) if kind == 'images' else ('organic', 'shopping', 'knowledgeGraph', 'answerBox')
            if not any(isinstance(raw.get(k), (list, dict)) for k in sections):
                return None
            data = normalize(kind, raw)
            field = {'search': 'organic_results', 'images': 'images_results', 'shopping': 'shopping_results'}[kind]
            data.setdefault(field, [])  # Empty success is returned, never persisted.
            data.setdefault('search_metadata', {}).update(provider='serper', engine='serper_'+kind)
            return data
        with self.lock:
            hit = cached()
            if isinstance(hit, dict):
                self.cost('serper_cache_hits')
                return copy.deepcopy(hit)
            future = None if bypass else self.inflight.get(key)
            if future is None and not bypass and wider_key:
                future = self.inflight.get(wider_key)
                if future is not None:
                    self.cost('serper_wider_shared_responses')
            leader = future is None
            if leader:
                future = self.pool.submit(run)
                if future is not None and not bypass:
                    self.inflight[key] = future
        if future is None:
            self.cost('serper_capacity_skipped')
            return None
        if leader:
            def finished(done):
                try:
                    data = done.result()
                    if not bypass and provider_cacheable(data):
                        self.cache_put(key, 'serper_'+kind, data, ttl_seconds=None)
                except Exception:
                    pass
                finally:
                    if not bypass:
                        with self.lock:
                            if self.inflight.get(key) is done:
                                self.inflight.pop(key, None)
            future.add_done_callback(finished)
        else:
            self.cost('serper_shared_responses')
        try:
            data = future.result(timeout=seconds)
            return copy.deepcopy(data) if isinstance(data, dict) else None
        except TimeoutError:
            self.cost('serper_wait_timeouts')
            return None  # Leave the shared HTTP call available for other callers.
        except Exception:
            return None


class SearchApiRouter:
    def __init__(self, *, cache_get, cache_put, cost, http_get=None, log=print):
        self.key = os.environ.get('SEARCHAPI_API_KEY', '').strip()
        self.backup_key = os.environ.get('SERPAPI_API_KEY', '').strip()
        self.enabled = bool(self.key and self.backup_key) and os.environ.get(
            'SEARCHAPI_PRIMARY_ENABLED', 'true').lower() in ('1', 'true', 'yes', 'on')
        self.threshold = _number('SEARCHAPI_FALLBACK_AFTER_SECONDS', 8., .1, 15.)
        self.total = _number('SEARCHAPI_TOTAL_TIMEOUT_SECONDS', 18., 1., 30.)
        self.backup_min = _number('SEARCHAPI_BACKUP_MIN_SECONDS', 4., .1, 15.)
        self.lens_hedge = os.environ.get('FINDZIA_LENS_EARLY_BACKUP', 'true').lower() in ('1', 'true', 'yes', 'on')
        self.lens_hedge_after = _number('FINDZIA_LENS_BACKUP_AFTER_SECONDS', 1.5, .1, 8.)
        self.economy = os.environ.get('SEARCHAPI_ECONOMY_ENABLED', 'true').lower() in ('1', 'true', 'yes', 'on')
        self.cooldown = _number('SEARCHAPI_CIRCUIT_SECONDS', 30., 1., 300.)
        self.workers = int(_number('SEARCHAPI_MAX_INFLIGHT', 32., 2., 64.))
        self.cache_get, self.cache_put, self.cost = cache_get, cache_put, cost
        self.get, self.log = http_get or requests.get, log
        self.primary_pool = _BoundedPool(self.workers, 'searchapi-http')
        self.backup_pool = _BoundedPool(self.workers, 'search-rescue')
        self.lock = threading.Lock()
        self.inflight, self.circuits, self.late = {}, {}, {}

    def snapshot(self):
        with self.lock:
            now = time.monotonic()
            circuits = {k: round(max(0., v[1] - now), 2) for k, v in self.circuits.items() if v[1] > now}
        return {'enabled': self.enabled, 'primary': 'searchapi' if self.enabled else 'legacy',
                'fallback': 'serpapi', 'fallback_after_seconds': self.threshold,
                'total_timeout_seconds': self.total, 'backup_min_seconds': self.backup_min,
                'lens_early_backup': self.lens_hedge, 'lens_backup_after_seconds': self.lens_hedge_after,
                'economy_enabled': self.economy, 'open_circuits': circuits}

    def _health(self, engine, ok, status=0, *, short_deadline=False):
        with self.lock:
            count, until = self.circuits.get(engine, (0, 0.))
            if ok:
                self.circuits[engine] = (0, 0.)
            else:
                # A caller's short enrichment budget and invalid request options
                # are not evidence that the engine is unavailable.
                if status == 400 or (short_deadline and not status):
                    return
                count += 1
                if count >= 3 or status in (401, 402, 403, 429):
                    until = time.monotonic() + self.cooldown
                self.circuits[engine] = (count, until)

    def _primary(self, params, seconds):
        response = None
        started = time.monotonic()
        self.cost('searchapi_http_requests')
        self.cost('searchapi_engine_' + params['engine'])
        self.log('SEARCHAPI REQUEST engine=' + params['engine'] + ' wait_seconds=' + str(round(seconds, 2)))
        try:
            connect = min(1.5, seconds / 4)
            response = self.get('https://www.searchapi.io/api/v1/search', params=params,
                                headers={'Authorization': 'Bearer ' + self.key},
                                timeout=(max(.01, connect), max(.01, seconds)),
                                allow_redirects=False)
            if response.status_code != 200:
                return None, 'http_' + str(response.status_code), response.status_code
            # Count provider HTTP successes, including those arriving after the
            # caller stopped waiting. This is a diagnostic, not a billing claim.
            self.cost('searchapi_http_200')
            data = normalize(response.json(), params['engine'])
            return (data, '', 200) if data is not None else (None, 'invalid_response', 200)
        except requests.exceptions.Timeout:
            return None, 'timeout', 0
        except (ValueError, TypeError, KeyError):
            return None, 'invalid_response', 0
        except Exception:
            return None, 'connection', 0
        finally:
            self.log('SEARCHAPI RESPONSE engine=' + params['engine'] +
                     ' status=' + str(response.status_code if response is not None else 0) +
                     ' elapsed_ms=' + str(round((time.monotonic()-started)*1000)))
            if response is not None:
                response.close()

    def _retain_late(self, key, engine, future, bypass):
        if bypass:
            return
        with self.lock:
            if self.late.get(key) is future:
                return
            self.late[key] = future
        def finished(done):
            try:
                data, _, _ = done.result()
                if provider_cacheable(data):
                    # Save paid work for subsequent requests, without changing
                    # the result already delivered to the current caller.
                    self.cache_put(key, engine, data, ttl_seconds=None)
                    self.cost('searchapi_late_cached')
            except Exception:
                pass
            finally:
                with self.lock:
                    if self.late.get(key) is done:
                        self.late.pop(key, None)
        future.add_done_callback(finished)

    def _race_lens(self, primary, params, mapped, deadline, primary_seconds, fallback, key, bypass, label):
        """One nominated image lane; keep the primary alive while its rescue runs."""
        started = time.monotonic()
        primary_until = min(deadline, started + primary_seconds)
        launch_at = min(primary_until, started + self.lens_hedge_after)
        backup = None
        backup_attempted = False
        empty_result = None
        active_primary = primary
        try:
            while time.monotonic() < deadline:
                now = time.monotonic()
                if active_primary is not None and active_primary.done():
                    try:
                        data, reason, status = active_primary.result()
                    except Exception:
                        data, reason, status = None, 'connection', 0
                    active_primary = None
                    self._health(mapped['engine'], data is not None, status,
                                 short_deadline=primary_seconds < self.threshold - .01)
                    if data is not None:
                        if provider_cacheable(data) or backup is None:
                            self.log('LENS FIRST RESPONSE winner=searchapi elapsed_ms=' + str(round((now-started)*1000)))
                            return data
                        empty_result = data
                    elif status == 400 and backup is None:
                        return None
                    launch_at = now
                if backup is not None and backup.done():
                    try:
                        data = backup.result()
                    except Exception:
                        data = None
                    backup = None
                    if isinstance(data, dict) and not data.get('_serpapi_failure') and normalize(data, 'google_lens') is not None:
                        data = copy.deepcopy(data)
                        data['search_metadata'] = dict(data.get('search_metadata') or {}, provider='serpapi', fallback_from='searchapi')
                        if provider_cacheable(data):
                            self.log('LENS FIRST RESPONSE winner=serpapi elapsed_ms=' + str(round((now-started)*1000)))
                            return data
                        empty_result = empty_result or data
                if active_primary is not None and now >= primary_until:
                    self._retain_late(key, mapped['engine'], active_primary, bypass)
                    active_primary = None
                    self._health(mapped['engine'], False, 0,
                                 short_deadline=primary_seconds < self.threshold - .01)
                if not backup_attempted and (now >= launch_at or active_primary is None):
                    backup_attempted = True
                    remaining = deadline - now
                    if remaining >= self.backup_min:
                        backup_params = dict(params, api_key=self.backup_key)
                        def rescue():
                            left = deadline - time.monotonic()
                            if left <= .01:
                                return None
                            connect = min(1.5, left / 4)
                            return fallback(backup_params, (connect, left-connect), label=label,
                                            return_error=True, retry_connect=False)
                        backup = self.backup_pool.submit(rescue)
                        if backup is not None:
                            self.cost('searchapi_fallback_requests')
                            self.cost('lens_early_backup_requests')
                            self.log('LENS EARLY BACKUP after_ms=' + str(round((now-started)*1000)))
                    else:
                        self.cost('searchapi_rescue_skipped')
                pending = {job for job in (active_primary, backup) if job is not None}
                if not pending:
                    break
                wake = deadline
                if active_primary is not None:
                    wake = min(wake, primary_until)
                if not backup_attempted:
                    wake = min(wake, launch_at)
                wait(pending, timeout=max(0., wake-time.monotonic()), return_when=FIRST_COMPLETED)
            return empty_result
        finally:
            # Purchased primary work is retained for later searches. The losing
            # rescue uses the legacy transport's own cache and never updates UI.
            if primary is not None and (not primary.done() or active_primary is not None):
                self._retain_late(key, mapped['engine'], primary, bypass)
            if backup is not None:
                backup.cancel()

    def search(self, params, timeout, fallback, *, label='', return_error=False, lens_hedge=False):
        mapped = searchapi_params(params)
        if not self.enabled or mapped is None:
            return fallback(params, timeout, label=label, return_error=return_error, retry_connect=False)
        deadline = time.monotonic() + min(self.total, _seconds(timeout))
        bypass = str(params.get('no_cache', '')).lower() in ('1', 'true')
        # auto_crop is not a SearchApi option. Coalesce equivalent full-frame
        # requests, including duplicate image branches with different crop flags.
        key = hashlib.sha256(('searchapi-v1:' + json.dumps(mapped, sort_keys=True, ensure_ascii=False)).encode()).hexdigest()
        cached = None if bypass else self.cache_get(key)
        if provider_cacheable(cached):
            self.cost('searchapi_cache_hits')
            return copy.deepcopy(cached)
        with self.lock:
            shared = None if bypass else self.inflight.get(key)
            leader = shared is None
            if leader:
                shared = Future()
                if not bypass:
                    self.inflight[key] = shared
        if not leader:
            self.cost('searchapi_shared_responses')
            try:
                result = shared.result(timeout=max(0., deadline - time.monotonic()))
                return copy.deepcopy(result) if result is not None else self._failure(return_error)
            except TimeoutError:
                return self._failure(return_error)
        result = None
        try:
            # A previous leader may have just written its result and exited.
            cached = None if bypass else self.cache_get(key)
            if provider_cacheable(cached):
                result = cached
                return copy.deepcopy(result)
            with self.lock:
                circuit = self.circuits.get(mapped['engine'], (0, 0.))[1] > time.monotonic()
            remaining = deadline - time.monotonic()
            # Give short tasks their entire remaining budget, rather than
            # cutting them at 60% and buying a rescue with only 1-2s to run.
            primary_seconds = max(0., min(self.threshold, remaining))
            reason, status = ('circuit_open', 0) if circuit else ('capacity', 0)
            future = None
            if not circuit and primary_seconds > .01:
                with self.lock:
                    future = None if bypass else self.late.get(key)
                if future is not None:
                    self.cost('searchapi_late_reused')
                else:
                    future = self.primary_pool.submit(self._primary, mapped, primary_seconds)
            if lens_hedge and self.lens_hedge and mapped['engine'] == 'google_lens':
                result = self._race_lens(future, params, mapped, deadline, primary_seconds,
                                         fallback, key, bypass, label)
                if not bypass and provider_cacheable(result):
                    ttl = 30 if result.get('search_metadata', {}).get('fallback_from') else None
                    self.cache_put(key, mapped['engine'], result, ttl_seconds=ttl)
                return copy.deepcopy(result) if result is not None else self._failure(return_error)
            if future is not None:
                try:
                    result, reason, status = future.result(timeout=primary_seconds)
                except TimeoutError:
                    reason = 'deadline'
                    self._retain_late(key, mapped['engine'], future, bypass)
                except Exception:
                    reason = 'connection'
                self._health(mapped['engine'], result is not None, status,
                             short_deadline=primary_seconds < self.threshold - .01)
            if result is None:
                remaining = deadline - time.monotonic()
                if status == 400 or remaining < self.backup_min:
                    self.cost('searchapi_rescue_skipped')
                    return self._failure(return_error)
                self.cost('searchapi_fallback_requests')
                self.log('SEARCH FALLBACK primary=searchapi backup=serpapi engine=' + mapped['engine'] + ' reason=' + reason)
                # Keep the original SerpApi engine/options, never SearchApi tokens.
                backup_params = dict(params, api_key=self.backup_key)
                connect = min(1.5, remaining / 4)
                def rescue():
                    return fallback(backup_params, (connect, remaining-connect), label=label,
                                    return_error=True, retry_connect=False)
                rescue_future = self.backup_pool.submit(rescue)
                if rescue_future is not None:
                    try:
                        result = rescue_future.result(timeout=max(0., deadline-time.monotonic()))
                    except TimeoutError:
                        rescue_future.cancel()
                    except Exception:
                        result = None
                if not isinstance(result, dict) or result.get('error') or result.get('_serpapi_failure'):
                    result = None
                    return self._failure(return_error)
                result = copy.deepcopy(result)
                result.setdefault('search_metadata', {})['provider'] = 'serpapi'
                result['search_metadata']['fallback_from'] = 'searchapi'
            if not bypass and provider_cacheable(result):
                # Backup cache is deliberately short; probe the primary again.
                ttl = 30 if result.get('search_metadata', {}).get('fallback_from') else None
                self.cache_put(key, mapped['engine'], result, ttl_seconds=ttl)
            return copy.deepcopy(result)
        finally:
            shared.set_result(copy.deepcopy(result))
            if not bypass:
                with self.lock:
                    if self.inflight.get(key) is shared:
                        self.inflight.pop(key)

    @staticmethod
    def _failure(return_error):
        return {'error': 'search_providers_unavailable', '_serpapi_failure': {'reason': 'providers_unavailable'}} if return_error else None
