"""回归测试：榜单/名录侧净值必须做正值校验，非正按缺失处理。

条目 2 数据可靠性审计（2026-10-26）发现：`_load_fund_list` 的丰富表、
`_fetch_rankings`、`_etf_registry` 经 `_optional_float` 原样收纳负净值，
列表页可能展示负净值。2026-10-31 用户批准全部修后落地 `_optional_nav`：
净值字段非正 -> None；可正可负的字段（涨跌幅、近一年收益、市价、
折价率）不受影响。
"""

from unittest.mock import patch

import pandas as pd
import pytest

from services import fund_service


@pytest.mark.parametrize(
    "value,expected",
    [
        (-1.5, None),
        (0, None),
        (0.0, None),
        ("-0.25", None),
        (1.2345, 1.2345),
        ("2.5", 2.5),
        (None, None),
        ("abc", None),
    ],
)
def test_optional_nav_drops_non_positive_keeps_positive(value, expected):
    assert fund_service._optional_nav(value) == expected


def test_enrichment_lookup_drops_non_positive_nav():
    frame = pd.DataFrame(
        [
            {"基金代码": "000001", "单位净值": -0.5, "日增长率": 1.0, "近1年": 5.0},
            {"基金代码": "000002", "单位净值": 0.0, "日增长率": 1.0, "近1年": 5.0},
            {"基金代码": "000003", "单位净值": 1.5, "日增长率": -2.0, "近1年": -5.0},
        ]
    )
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service, "_call_akshare", return_value=frame
    ):
        lookup = fund_service._build_enrichment_lookup()
    assert lookup["000001"]["nav"] is None
    assert lookup["000002"]["nav"] is None
    assert lookup["000003"]["nav"] == 1.5
    # 可正可负的字段不受净值校验影响
    assert lookup["000003"]["change_pct"] == -2.0
    assert lookup["000003"]["one_year_return"] == pytest.approx(-0.05)


def test_fetch_rankings_drops_non_positive_nav():
    open_frame = pd.DataFrame(
        [
            {"基金代码": "000001", "基金简称": "脏净值基金", "类型": "股票型", "单位净值": -3.0, "日增长率": 0.5, "近1年": 10.0},
            {"基金代码": "000002", "基金简称": "正常基金", "类型": "股票型", "单位净值": 2.25, "日增长率": 0.5, "近1年": 20.0},
        ]
    )
    with patch.object(fund_service, "_open_rank_frame", return_value=open_frame), patch.object(
        fund_service.ak, "fund_exchange_rank_em", return_value=pd.DataFrame()
    ):
        results = fund_service._fetch_rankings()
    by_code = {f.code: f for f in results}
    assert by_code["000001"].nav is None
    assert by_code["000002"].nav == 2.25


def test_etf_registry_drops_non_positive_navs_but_keeps_price():
    frame = pd.DataFrame(
        [
            {
                "基金代码": "510001", "基金简称": "脏净值ETF", "类型": "指数型-股票",
                "2026-10-30-单位净值": "-0.5", "2026-10-30-累计净值": "0",
                "市价": "4.5800", "折价率": "-0.06%",
            },
            {
                "基金代码": "510002", "基金简称": "正常ETF", "类型": "指数型-股票",
                "2026-10-30-单位净值": "1.5000", "2026-10-30-累计净值": "2.5000",
                "市价": "1.4900", "折价率": "0.10%",
            },
        ]
    )
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service, "_call_akshare", return_value=frame
    ):
        registry = fund_service._etf_registry()
    assert registry["510001"]["unit_nav"] is None
    assert registry["510001"]["cumulative_nav"] is None
    assert registry["510001"]["market_price"] == 4.58  # 市价不是净值，不走净值校验
    assert registry["510002"]["unit_nav"] == 1.5
    assert registry["510002"]["cumulative_nav"] == 2.5
