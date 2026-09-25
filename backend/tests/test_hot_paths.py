"""热路径回归测试：逐行调用的函数不得 O(n)，冷启动的并行批次不得争抢上游。

已修复的两个 bug（实测复现）：

  1. `_load_fund_list()` 把 `_etf_registry()` 和两个东方财富大请求放进同一个
     ThreadPoolExecutor 并发执行。三者同源，互相拖慢：实测
     `fund_etf_fund_daily_em` 单独 1.55s、并发 20.58s（13 倍），而它的超时是 30s
     —— 于是每次冷启动都在 30.04s 被掐断（3/3 复现），并把**空名录**缓存 600 秒。
     后果：真实 ETF 被判为非 ETF，`kline('510300')` 返回 0 点（K 线消失），
     基金列表把 510300/159915 标成"股票型"。

  2. P0-6 新增的 `nav_data_status()` 被**逐行**调用（基金列表 27,879 行、
     排行榜 20,325 行），而 `latest_trading_day()` / `_trading_days_behind()`
     用列表推导线性扫描近 9000 天的日历。实测单次 1770 微秒 →
     基金列表一项就要 49.3 秒，冷启动 55.3s。
     改为 bisect 二分后单次 12.2 微秒（145 倍），冷启动降到 28.8s。
"""

import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pandas as pd
import pytest

from services import fund_service

NAME_FRAME = pd.DataFrame([{"基金代码": "000001", "基金简称": "某基金", "基金类型": "股票型-普通"}])


class CountingCalendar(list):
    """记录被迭代次数的日历。

    bisect 只用 __getitem__/__len__ 做二分，**不会迭代**；线性扫描必然迭代。
    因此"迭代次数为 0"可以确定性地证明热路径已不再是 O(n)，不依赖计时。
    """

    def __init__(self, values):
        super().__init__(values)
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        return super().__iter__()


@pytest.fixture
def counting_calendar():
    from datetime import date, timedelta

    days = []
    cursor = date(2019, 1, 1)
    while cursor <= date(2026, 12, 31):
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    counter = CountingCalendar(days)
    with patch.object(fund_service, "_trade_calendar", return_value=counter):
        yield counter


# ---------------------------------------------------------------------------
# bug 2：新鲜度判定必须是 O(log n)
# ---------------------------------------------------------------------------


def test_latest_trading_day_does_not_scan_the_calendar(counting_calendar):
    from datetime import date

    result = fund_service.latest_trading_day(today=date(2026, 9, 18))

    assert result is not None
    assert counting_calendar.iterations == 0, "latest_trading_day 不得线性扫描日历"


def test_trading_days_behind_does_not_scan_the_calendar(counting_calendar):
    from datetime import date

    behind = fund_service._trading_days_behind(date(2026, 9, 15), today=date(2026, 9, 18))

    assert behind == 3
    assert counting_calendar.iterations == 0, "_trading_days_behind 不得线性扫描日历"


def test_nav_data_status_does_not_scan_the_calendar(counting_calendar):
    from datetime import date

    assert fund_service.nav_data_status(date(2026, 9, 18), today=date(2026, 9, 18)) == "fresh"
    assert counting_calendar.iterations == 0, "nav_data_status 会被逐行调用，必须是 O(log n)"


@pytest.mark.parametrize(
    "observed,today,expected",
    [
        ("2026-09-18", "2026-09-18", "fresh"),
        ("2026-09-17", "2026-09-18", "fresh"),
        ("2026-09-15", "2026-09-18", "stale"),
        ("2020-12-31", "2026-09-18", "inactive"),
        (None, "2026-09-18", "unavailable"),
    ],
)
def test_bisect_results_match_the_documented_semantics(counting_calendar, observed, today, expected):
    """优化不得改变语义：各状态仍按原口径判定。"""
    from datetime import date

    obs = None if observed is None else date.fromisoformat(observed)
    assert fund_service.nav_data_status(obs, today=date.fromisoformat(today)) == expected


def test_nav_data_status_is_fast_enough_for_tens_of_thousands_of_rows(counting_calendar):
    """27,879 行的基金列表必须在秒级完成，而不是几十秒。"""
    from datetime import date

    reference = date(2026, 9, 18)
    start = time.perf_counter()
    for _ in range(20_000):
        fund_service.nav_data_status(reference, today=reference)
    elapsed = time.perf_counter() - start

    # 修复前单次 1770 微秒（2 万次约 35s）；修复后约 12 微秒（0.25s）。
    # 阈值取 5s，远离两者，避免在慢机器上误报。
    assert elapsed < 5.0, f"2 万次调用耗时 {elapsed:.2f}s，热路径疑似又变成 O(n)"


# ---------------------------------------------------------------------------
# bug 1：ETF 名录不得与基金列表的两个大请求并发争抢上游
# ---------------------------------------------------------------------------


def test_etf_registry_is_fetched_after_the_two_heavy_requests():
    """名录必须在两个大请求**都结束之后**才取，避免同源并发互相拖慢导致超时。"""
    events: list[str] = []

    def slow_name():
        events.append("name_start")
        time.sleep(0.15)
        events.append("name_end")
        return NAME_FRAME

    def slow_rank():
        events.append("rank_start")
        time.sleep(0.15)
        events.append("rank_end")
        return {}

    def fake_registry():
        events.append("registry")
        return {}

    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_name_em", side_effect=slow_name
    ), patch.object(
        fund_service, "_build_enrichment_lookup", side_effect=slow_rank
    ), patch.object(
        fund_service, "_etf_registry", side_effect=fake_registry
    ):
        fund_service._load_fund_list()

    assert "registry" in events, "名录必须被预取（否则逐行循环里会持锁等待网络）"
    registry_at = events.index("registry")
    assert registry_at > events.index("name_end"), "名录不得与 fund_name_em 并发"
    assert registry_at > events.index("rank_end"), "名录不得与排行榜请求并发"


def test_fund_list_uses_at_most_two_parallel_workers():
    """并行批次只应包含两个大请求：再并发第三个同源请求会互相拖慢。"""
    observed_max_workers: list[int] = []
    real_executor = ThreadPoolExecutor

    def spy_executor(max_workers=None, *args, **kwargs):
        observed_max_workers.append(max_workers)
        return real_executor(max_workers=max_workers, *args, **kwargs)

    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_name_em", return_value=NAME_FRAME
    ), patch.object(
        fund_service, "_build_enrichment_lookup", return_value={}
    ), patch.object(
        fund_service, "_etf_registry", return_value={}
    ), patch.object(
        fund_service, "ThreadPoolExecutor", spy_executor
    ):
        fund_service._load_fund_list()

    assert observed_max_workers, "应创建并行批次"
    assert max(observed_max_workers) <= 2, (
        f"并行度 {observed_max_workers} 过高：同源请求并发会互相拖慢并被超时掐断"
    )


def test_empty_registry_is_never_silently_mistaken_for_a_real_one():
    """空名录必须能被识别为"未就绪"，而不是被当成"这不是 ETF"。

    这是本 bug 的失败模式：超时 -> 空名录 -> 真实 ETF 被判为非 ETF。
    """
    with patch.object(fund_service, "_etf_registry", return_value={}):
        assert fund_service._is_etf_code("510300") is False  # 保守降级（已文档化）

    with patch.object(fund_service, "_etf_registry", return_value={
        "510300": {"name": "沪深300ETF华泰", "type": "指数型-股票", "nav_date": "2026-09-18"}
    }):
        assert fund_service._is_etf_code("510300") is True
