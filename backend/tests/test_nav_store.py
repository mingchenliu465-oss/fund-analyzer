"""净值最小落库（nav_store）的单元测试。

纪律与被测对象一致：只存累计净值、缺失行丢弃、取不到就返回空帧，
绝不生成替代数据。
"""

import pandas as pd
import pytest

from services import nav_store


def _frame(pairs):
    return pd.DataFrame(
        {
            "净值日期": pd.to_datetime([p[0] for p in pairs]),
            "单位净值": [p[1] for p in pairs],
            "累计净值": [p[2] for p in pairs],
            "日增长率": [0.0] * len(pairs),
        }
    )


def test_save_and_load_roundtrip(tmp_path):
    db = tmp_path / "nav.db"
    frame = _frame([("2024-01-02", 1.0, 1.5), ("2024-01-03", 1.1, 1.65), ("2024-01-04", 1.2, 1.8)])
    assert nav_store.save_nav("000001", frame, db_path=db) == 3
    loaded = nav_store.load_nav("000001", db_path=db)
    assert list(loaded["累计净值"]) == [1.5, 1.65, 1.8]
    assert [d.strftime("%Y-%m-%d") for d in loaded["净值日期"]] == [
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
    ]


def test_load_unknown_code_returns_empty_frame(tmp_path):
    loaded = nav_store.load_nav("999999", db_path=tmp_path / "nav.db")
    assert loaded.empty
    assert list(loaded.columns) == ["净值日期", "累计净值"]


def test_rows_without_cumulative_nav_are_dropped_not_substituted(tmp_path):
    db = tmp_path / "nav.db"
    frame = _frame([("2024-01-02", 1.0, 1.5), ("2024-01-03", 1.1, None), ("2024-01-04", 1.2, 1.8)])
    # 单位净值存在、累计净值缺失的那一行必须被丢弃，绝不回退用单位净值顶替
    assert nav_store.save_nav("000001", frame, db_path=db) == 2
    loaded = nav_store.load_nav("000001", db_path=db)
    assert list(loaded["累计净值"]) == [1.5, 1.8]


def test_save_is_upsert_and_sorted(tmp_path):
    db = tmp_path / "nav.db"
    nav_store.save_nav("000001", _frame([("2024-01-03", 1.1, 1.65), ("2024-01-02", 1.0, 1.5)]), db_path=db)
    nav_store.save_nav("000001", _frame([("2024-01-03", 1.1, 1.66)]), db_path=db)
    loaded = nav_store.load_nav("000001", db_path=db)
    assert list(loaded["累计净值"]) == [1.5, 1.66]


def test_codes_are_isolated(tmp_path):
    db = tmp_path / "nav.db"
    nav_store.save_nav("000001", _frame([("2024-01-02", 1.0, 1.5)]), db_path=db)
    nav_store.save_nav("000002", _frame([("2024-01-02", 2.0, 3.5)]), db_path=db)
    assert list(nav_store.load_nav("000002", db_path=db)["累计净值"]) == [3.5]


def test_missing_columns_raise(tmp_path):
    with pytest.raises(ValueError):
        nav_store.save_nav("000001", pd.DataFrame({"净值日期": [], "单位净值": []}), db_path=tmp_path / "n.db")


def test_get_nav_history_uses_store_then_fetcher(tmp_path):
    db = tmp_path / "nav.db"
    calls = []

    def fetcher(code):
        calls.append(code)
        return _frame([("2024-01-02", 1.0, 1.5), ("2024-01-03", 1.1, 1.65)])

    first = nav_store.get_nav_history("000001", fetcher=fetcher, db_path=db)
    assert list(first["累计净值"]) == [1.5, 1.65]
    assert calls == ["000001"]
    # 第二次必须命中落库，不再调用 fetcher
    second = nav_store.get_nav_history("000001", fetcher=fetcher, db_path=db)
    assert list(second["累计净值"]) == [1.5, 1.65]
    assert calls == ["000001"]


def test_get_nav_history_fetch_failure_returns_empty(tmp_path):
    def failing_fetcher(code):
        return pd.DataFrame(columns=["净值日期", "单位净值", "累计净值", "日增长率"])

    result = nav_store.get_nav_history("000001", fetcher=failing_fetcher, db_path=tmp_path / "nav.db")
    assert result.empty
