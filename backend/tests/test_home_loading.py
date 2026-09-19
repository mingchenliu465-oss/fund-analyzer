"""加载路径与并发刷新行为测试。

本文件中所有基金/指数数据都是**测试替身（stub）**，在本文件内构造，
不进入任何生产数据路径。生产代码（services/）已不再包含硬编码基金池
或默认指数列表。
"""

import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch, MagicMock

from models.fund import FundSummary
from models.market import MarketIndex
from services import fund_service as f, portfolio_service as p, market_service as m


def stub_fund(index: int) -> FundSummary:
    return FundSummary(
        code=f"{index:06d}",
        name=f"测试基金{index}",
        company="测试基金公司",
        type="股票型",
        nav=round(1.0 + index / 100, 4),
        change_pct=round(0.1 * index, 2),
        one_year_return=round(index / 100, 4),
        risk_level="中高",
        size="10.0亿",
        heat=50,
    )


def stub_funds(count: int = 12) -> list[FundSummary]:
    return [stub_fund(i) for i in range(1, count + 1)]


def stub_indices(count: int = 6) -> list[MarketIndex]:
    return [
        MarketIndex(code=f"sh{i:06d}", name=f"测试指数{i}", value="1000.00", change=0.0, up=True)
        for i in range(1, count + 1)
    ]


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
        self.check_snapshot(f, lambda: f.rankings(8), '_fetch_rankings', 'rankings', '_RANKINGS_RETRY_AT', '_RANKINGS_LOCK', stub_funds()[:8])

    def test_indices_concurrent_stale_and_failed_refresh(self):
        self.check_snapshot(m, m.indices, '_fetch_indices', 'market_indices', '_INDICES_RETRY_AT', '_INDICES_REFRESH_LOCK', stub_indices())

    def test_rankings_cold_returns_empty_then_publishes_real_data(self):
        """冷启动（无任何真实快照）必须返回空列表，绝不返回硬编码榜单。

        刷新完成后才对外提供真实数据。
        """
        entered, finish = Event(), Event()
        fresh = stub_funds()[2:12]
        def slow():
            entered.set()
            finish.wait(3)
            return fresh
        with patch.dict(f._CACHE, {}, clear=True), patch.object(f, '_RANKINGS_RETRY_AT', 0), patch.object(f, '_fetch_rankings', side_effect=slow) as loader:
            try:
                self.assertEqual(f.rankings(8), [])
                self.assertTrue(entered.wait(1))
                self.assertEqual(f.rankings(6), [])
                self.assertEqual(loader.call_count, 1)
            finally:
                finish.set()
                self.assertTrue(f._RANKINGS_LOCK.acquire(timeout=4))
                f._RANKINGS_LOCK.release()
            self.assertEqual(f.rankings(8), fresh[:8])
            self.assertEqual(loader.call_count, 1)

    def test_rankings_exception_preserves_cache(self):
        old = stub_funds()[:8]
        with patch.dict(f._CACHE, {'rankings': (old, 0)}, clear=True), patch.object(f, '_RANKINGS_RETRY_AT', 0), patch.object(f, '_fetch_rankings', side_effect=RuntimeError('offline')):
            f._RANKINGS_LOCK.acquire()
            f._refresh_rankings()
            self.assertEqual(f._CACHE['rankings'][0], old)
            self.assertFalse(f._RANKINGS_LOCK.locked())
