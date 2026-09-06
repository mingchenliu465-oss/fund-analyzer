import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch, MagicMock
from services import fund_service as f, portfolio_service as p, market_service as m

class LoadingTests(unittest.TestCase):
    def test_empty_portfolio_skips_nav(self):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []
        with patch.object(p, 'get_connection', return_value=conn), patch.object(p, '_build_nav_map') as nav:
            self.assertEqual(p.list_holdings(), [])
            nav.assert_not_called()
            conn.close.assert_called_once()

    def check_snapshot(self, module, entrypoint, fetch, key, retry, lock, snapshot):
        entered, finish = Event(), Event()
        def slow():
            entered.set()
            finish.wait(3)
            return []
        with patch.dict(module._CACHE, {key: (snapshot, 0)}, clear=True), patch.object(module, retry, 0), patch.object(module, fetch, side_effect=slow) as loader:
            try:
                with ThreadPoolExecutor(max_workers=12) as pool:
                    results = list(pool.map(lambda _: entrypoint(), range(24)))
                self.assertTrue(entered.wait(1))
                self.assertTrue(all(result == snapshot for result in results))
                self.assertEqual(loader.call_count, 1)
            finally:
                finish.set()
                self.assertTrue(getattr(module, lock).acquire(timeout=4))
                getattr(module, lock).release()
            self.assertEqual(module._CACHE[key][0], snapshot)
            entrypoint()
            self.assertEqual(loader.call_count, 1)

    def test_rankings_concurrent_stale_and_failed_refresh(self):
        self.check_snapshot(f, lambda: f.rankings(8), '_fetch_rankings', 'rankings', '_RANKINGS_RETRY_AT', '_RANKINGS_LOCK', f._default_fund_list()[:8])

    def test_indices_concurrent_stale_and_failed_refresh(self):
        self.check_snapshot(m, m.indices, '_fetch_indices', 'market_indices', '_INDICES_RETRY_AT', '_INDICES_REFRESH_LOCK', m._DEFAULT_INDICES)

    def test_rankings_cold_returns_default_then_publishes(self):
        entered, finish = Event(), Event()
        fresh = f._default_fund_list()[2:12]
        def slow():
            entered.set()
            finish.wait(3)
            return fresh
        with patch.dict(f._CACHE, {}, clear=True), patch.object(f, '_RANKINGS_RETRY_AT', 0), patch.object(f, '_fetch_rankings', side_effect=slow) as loader:
            try:
                self.assertEqual(len(f.rankings(8)), 8)
                self.assertTrue(entered.wait(1))
                self.assertEqual(len(f.rankings(6)), 6)
                self.assertEqual(loader.call_count, 1)
            finally:
                finish.set()
                self.assertTrue(f._RANKINGS_LOCK.acquire(timeout=4))
                f._RANKINGS_LOCK.release()
            self.assertEqual(f.rankings(8), fresh[:8])
            self.assertEqual(loader.call_count, 1)

    def test_rankings_exception_preserves_cache(self):
        old = f._default_fund_list()[:8]
        with patch.dict(f._CACHE, {'rankings': (old, 0)}, clear=True), patch.object(f, '_RANKINGS_RETRY_AT', 0), patch.object(f, '_fetch_rankings', side_effect=RuntimeError('offline')):
            f._RANKINGS_LOCK.acquire()
            f._refresh_rankings()
            self.assertEqual(f._CACHE['rankings'][0], old)
            self.assertFalse(f._RANKINGS_LOCK.locked())
