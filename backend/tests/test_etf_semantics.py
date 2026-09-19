"""P0-2 回归测试：ETF / LOF / 场外基金的数据语义必须分开。

背景（实测，2026-09-19）：
  1. 原 `_is_etf_code()` 用代码前缀 `51/56/58/15/16` 判断 ETF。实测错误：
     519066（汇添富蓝筹稳健，场外混合型）以 51 开头；
     162411/160632/161725（LOF）以 16 开头 —— 全部被误判成 ETF。
     前缀法在 fund_name_em 上命中 2,473 只，而真实场内 ETF 只有 1,660 只
     （fund_etf_fund_daily_em）—— 33% 是误判。
     `基金类型` 字段也无法区分：159915（真 ETF）与 161725/160632（LOF）
     在 fund_name_em 里同为"指数型-股票"。
  2. 原 `_fetch_etf_history()` 把二级市场收盘价写进 `单位净值` 列：
     `df["单位净值"] = df["close"]`。实测 510300 在 2025-12-31
     收盘价 4.630、单位净值 4.7536 —— 两个不同的金融事实被合并成一个字段。
  3. 新浪源返回不复权行情，东方财富备用源用 `adjust="qfq"`（前复权）——
     主备源切换时同一天的收盘价含义不同，序列基准跳变。

这里锁定三条不可退让的语义边界：
    NAV 就是 NAV，market close 就是 market close，两者不允许互相冒充。
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from models.market import NavPeriod
from services import fund_service, market_service, portfolio_service

# 真实 ETF（在 fund_etf_fund_daily_em 名录里）
ETF_CODE = "510300"
# 真实 LOF（16 开头，但**不是** ETF）
LOF_CODE = "161725"
# 场外混合型基金（51 开头，但**不是** ETF）
OPEN_CODE = "519066"


def _recent_dates(count: int) -> list[str]:
    today = datetime.now().date()
    return [(today - timedelta(days=offset)).isoformat() for offset in reversed(range(count))]


def nav_frame(unit, cumulative):
    """与 _fetch_nav_history 真实输出同构的净值帧。"""
    return pd.DataFrame(
        {
            "净值日期": pd.to_datetime(_recent_dates(len(unit))),
            "单位净值": unit,
            "累计净值": cumulative,
            "日增长率": [0.0] * len(unit),
        }
    )


def price_frame(closes):
    """与 _fetch_etf_price_history 真实输出同构的市价帧（无任何净值列）。"""
    return pd.DataFrame(
        {
            "净值日期": pd.to_datetime(_recent_dates(len(closes))),
            "open": [c - 0.01 for c in closes],
            "high": [c + 0.02 for c in closes],
            "low": [c - 0.02 for c in closes],
            "close": closes,
            "volume": [1_000_000] * len(closes),
            "turnover": [5_000_000.0] * len(closes),
        }
    )


def registry(*codes):
    return {code: {"name": code, "type": "指数型-股票", "nav_date": "2026-09-18"} for code in codes}


# ---------------------------------------------------------------------------
# 1. ETF 身份必须来自真实名录，不能靠代码前缀
# ---------------------------------------------------------------------------


def test_etf_identity_comes_from_registry_not_code_prefix():
    with patch.object(fund_service, "_etf_registry", return_value=registry(ETF_CODE)):
        assert fund_service._is_etf_code(ETF_CODE) is True
        # 这三个都带"像 ETF"的前缀，但都不是 ETF。
        assert fund_service._is_etf_code(OPEN_CODE) is False
        assert fund_service._is_etf_code(LOF_CODE) is False
        assert fund_service._is_etf_code("162411") is False


def test_etf_identity_is_false_when_registry_is_unavailable():
    """名录不可用时保守返回 False，绝不退回前缀猜测。"""
    with patch.object(fund_service, "_etf_registry", return_value={}):
        assert fund_service._is_etf_code(ETF_CODE) is False
        assert fund_service._is_etf_code(LOF_CODE) is False


def test_etf_registry_parses_date_prefixed_columns_and_separates_concepts():
    """源数据所有列都是字符串，且折价率带 '%' —— 必须正确解析，不能丢成 None。"""
    upstream = pd.DataFrame(
        [
            {
                "基金代码": "510300",
                "基金简称": "沪深300ETF华泰",
                "类型": "指数型-股票",
                "2026-09-18-单位净值": "4.5793",
                "2026-09-18-累计净值": "2.0251",
                "2026-09-17-单位净值": "4.5310",
                "2026-09-17-累计净值": "2.0072",
                "市价": "4.5820",
                "折价率": "-0.06%",
            }
        ]
    )

    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_etf_fund_daily_em", return_value=upstream
    ):
        result = fund_service._etf_registry()

    entry = result["510300"]
    assert entry["nav_date"] == "2026-09-18"
    # 净值、市价、折溢价是三个不同的字段，必须各归各位。
    assert entry["unit_nav"] == pytest.approx(4.5793)
    assert entry["cumulative_nav"] == pytest.approx(2.0251)
    assert entry["market_price"] == pytest.approx(4.5820)
    # '-0.06%' → -0.06 百分数；不能是 None（静默丢弃真实折溢价信息）。
    assert entry["discount_rate"] == pytest.approx(-0.06)
    assert entry["unit_nav"] != entry["market_price"]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("-0.06%", -0.06),
        ("0.00%", 0.0),
        ("1.07%", 1.07),
        ("-1.5", -1.5),
        ("", None),
        ("--", None),
        ("nan", None),
        (None, None),
        ("abc", None),
    ],
)
def test_percent_parser_keeps_real_values_and_leaves_missing_missing(raw, expected):
    result = fund_service._optional_percent(raw)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)


def test_etf_registry_is_empty_when_source_fails():
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_etf_fund_daily_em", side_effect=RuntimeError("offline")
    ):
        assert fund_service._etf_registry() == {}


# ---------------------------------------------------------------------------
# 2. 市价帧绝不允许携带净值字段
# ---------------------------------------------------------------------------


def test_price_history_never_exposes_a_unit_nav_column():
    """核心断言：市价帧里不能出现 `单位净值`，否则下游会拿它算收益。"""
    closes = [4.60, 4.62, 4.63]
    upstream = pd.DataFrame(
        {
            "date": _recent_dates(3),
            "open": [4.59, 4.61, 4.62],
            "high": [4.61, 4.63, 4.64],
            "low": [4.58, 4.60, 4.61],
            "close": closes,
            "volume": [1, 2, 3],
            "amount": [10.0, 20.0, 30.0],
        }
    )

    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_etf_hist_sina", return_value=upstream
    ):
        df = fund_service._fetch_etf_price_history(ETF_CODE)

    assert not df.empty
    assert "单位净值" not in df.columns
    assert "累计净值" not in df.columns
    assert list(df["close"]) == closes


def test_price_history_falls_back_to_unadjusted_eastmoney():
    """备用源必须用不复权（adjust=""），与新浪源口径一致。"""
    eastmoney = pd.DataFrame(
        {
            "日期": _recent_dates(2),
            "开盘": [4.59, 4.61],
            "收盘": [4.60, 4.62],
            "最高": [4.61, 4.63],
            "最低": [4.58, 4.60],
            "成交量": [100, 200],
            "成交额": [1000.0, 2000.0],
        }
    )

    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_etf_hist_sina", side_effect=RuntimeError("sina down")
    ), patch.object(
        fund_service.ak, "fund_etf_hist_em", return_value=eastmoney
    ) as em:
        df = fund_service._fetch_etf_price_history(ETF_CODE)

    assert em.call_args.kwargs["adjust"] == ""
    assert "单位净值" not in df.columns


def test_price_history_is_empty_not_fabricated_when_all_sources_fail():
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_etf_hist_sina", side_effect=RuntimeError("offline")
    ), patch.object(
        fund_service.ak, "fund_etf_hist_em", side_effect=RuntimeError("offline")
    ):
        df = fund_service._fetch_etf_price_history(ETF_CODE)

    assert df.empty
    assert "单位净值" not in df.columns


# ---------------------------------------------------------------------------
# 3. 总收益基准：只认累计净值，绝不接受市价
# ---------------------------------------------------------------------------


def test_total_return_series_rejects_a_market_price_frame():
    """市价帧不能作为收益基准 —— 拿市场价算基金收益就是制造假收益。"""
    frame = price_frame([4.60, 4.62])

    with pytest.raises(ValueError):
        fund_service.total_return_series(frame)
    with pytest.raises(ValueError):
        fund_service._returns_from_nav(frame)
    with pytest.raises(ValueError):
        fund_service._metrics_from_nav(frame, "ETF")


def test_total_return_series_uses_cumulative_nav_for_etf_share_conversion():
    """份额折算场景：单位净值跳空，只有累计净值是真实的连续收益序列。

    510300 实测：2012-05-04 单位净值 1.007 → 2012-05-11 跳到 2.637（份额折算），
    同期累计净值 1.007 → 0.978（与该日"日增长率 -2.86%"一致）。
    """
    frame = nav_frame([1.007, 2.637, 2.574], [1.007, 0.978, 0.955])

    basis = fund_service.total_return_series(frame)
    assert list(basis) == [1.007, 0.978, 0.955]

    metrics = fund_service._metrics_from_nav(frame, "ETF")
    # 累计净值口径：(0.955 - 1.007) / 1.007 ≈ -5.16%
    assert metrics.max_drawdown == pytest.approx(-0.0516, abs=0.0005)

    # 反向确认：单位净值口径会得到 -2.39%（并凭空产生 +161% 的假涨幅）。
    unit_peak_to_last = (2.574 - 2.637) / 2.637
    assert metrics.max_drawdown != pytest.approx(unit_peak_to_last, abs=0.005)


# ---------------------------------------------------------------------------
# 4. 路径分流：净值走净值，K 线走市价
# ---------------------------------------------------------------------------


def test_nav_history_returns_nav_not_market_price():
    nav = nav_frame([4.75, 4.76], [2.03, 2.04])
    price = price_frame([4.60, 4.62])

    with patch.object(fund_service, "_fetch_nav_history", return_value=nav), patch.object(
        fund_service, "_fetch_etf_price_history", return_value=price
    ):
        result = fund_service.nav_history(ETF_CODE)

    assert "累计净值" in result.columns
    assert list(result["单位净值"]) == [4.75, 4.76]


def test_kline_routes_etf_to_price_and_lof_to_nav():
    """ETF → 市价 K 线；LOF → 没有 OHLC，返回空而不是把净值画成 K 线。"""
    price = price_frame([4.60, 4.62, 4.63])
    nav = nav_frame([4.75, 4.76, 4.77], [2.03, 2.04, 2.05])

    with patch.object(fund_service, "_etf_registry", return_value=registry(ETF_CODE)), patch.object(
        fund_service, "_fetch_etf_price_history", return_value=price
    ), patch.object(fund_service, "_fetch_nav_history", return_value=nav):
        etf_points = market_service.kline(ETF_CODE, NavPeriod.DAILY, "1Y")
        lof_points = market_service.kline(LOF_CODE, NavPeriod.DAILY, "1Y")

    assert etf_points, "ETF 应返回真实市价 K 线"
    assert etf_points[-1].close == pytest.approx(4.63)

    assert lof_points == [], "LOF 没有 OHLC，不得用净值伪造 K 线"


def test_market_service_etf_detection_delegates_to_registry():
    with patch.object(fund_service, "_etf_registry", return_value=registry(ETF_CODE)):
        assert market_service._is_etf(ETF_CODE) is True
        assert market_service._is_etf(LOF_CODE) is False
        assert market_service._is_etf(OPEN_CODE) is False


# ---------------------------------------------------------------------------
# 5. 收益归因用净值，不用市价
# ---------------------------------------------------------------------------


def test_etf_attribution_uses_nav_not_market_price():
    """市价与净值刻意取不同值：归因结果必须来自净值。"""
    nav = nav_frame([4.70, 4.75], [2.03, 2.045])
    price = price_frame([4.00, 5.00])  # 市价涨 25%，净值只涨约 1.06%

    with patch.object(fund_service, "_fetch_nav_history", return_value=nav), patch.object(
        fund_service, "_fetch_etf_price_history", return_value=price
    ):
        latest, prev, change_pct = portfolio_service._etf_nav_change(ETF_CODE)

    assert latest == pytest.approx(2.045)
    assert prev == pytest.approx(2.03)
    assert change_pct == pytest.approx(0.7389, abs=0.01)
    assert change_pct != pytest.approx(25.0)
