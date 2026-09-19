"""数据真实性策略的回归测试。

这些测试锁死一条项目铁律：**只能展示真实获取到并经过校验的数据。**
拿不到真实数据时必须返回空结果或明确报错，绝不编造、补齐、猜测，
也不用 mock 顶替。

它们同时防止未来把"造假生成器"重新引入生产代码。
"""

import re
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import analysis
from models.fund import FundSummary, Sector
from models.market import NavPeriod
from services import analysis_service, fund_service
from services import market_service

SERVICES_DIR = Path(__file__).resolve().parents[1] / "services"
EMPTY_NAV = pd.DataFrame(columns=["净值日期", "单位净值", "日增长率"])


def stub_fund(code: str = "000001", name: str = "测试基金") -> FundSummary:
    """测试替身（仅存在于测试内，不进入生产数据路径）。"""
    return FundSummary(
        code=code,
        name=name,
        company="测试基金公司",
        type="股票型",
        nav=1.5,
        change_pct=0.5,
        one_year_return=0.1,
        risk_level="中高",
        size="10.0亿",
        heat=50,
    )


# ---------------------------------------------------------------------------
# 后端：数据源失败时不得返回硬编码替代数据
# ---------------------------------------------------------------------------


def test_load_fund_list_returns_empty_when_source_fails():
    """fund_name_em 失败时必须返回空列表，而不是硬编码基金池。"""
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_name_em", side_effect=RuntimeError("offline")
    ):
        assert fund_service._load_fund_list() == []


def test_get_by_code_does_not_invent_unknown_fund():
    """基金不在真实列表中时必须报错，不得编造名称/类型/净值。"""
    with patch.object(fund_service, "_load_fund_list", return_value=[]):
        with pytest.raises(ValueError):
            fund_service.get_by_code("999999")


def test_get_by_code_refuses_to_build_metrics_without_nav():
    """没有真实净值序列时不得生成收益率/波动率/回撤/夏普。"""
    with patch.object(fund_service, "_load_fund_list", return_value=[stub_fund()]), patch.object(
        fund_service, "_fetch_nav_history", return_value=EMPTY_NAV
    ), patch.object(
        fund_service, "_fetch_real_sectors", return_value=None
    ), patch.object(
        fund_service, "_fetch_real_holdings", return_value=None
    ), patch.object(
        fund_service, "_fetch_basic_info", return_value={}
    ):
        with pytest.raises(ValueError):
            fund_service.get_by_code("000001")


def test_rankings_cold_start_is_empty_not_hardcoded():
    """冷启动（无缓存）时排行榜必须为空。"""
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service, "_RANKINGS_RETRY_AT", 0
    ), patch.object(fund_service, "_refresh_rankings", return_value=None):
        assert fund_service.rankings(8) == []


def test_index_list_cold_start_is_empty_not_hardcoded():
    """冷启动时指数列表必须为空，不得返回固定点位。"""
    with patch.dict(market_service._CACHE, {}, clear=True), patch.object(
        market_service, "_INDICES_RETRY_AT", 0
    ), patch.object(market_service, "_refresh_indices", return_value=None):
        assert market_service.indices() == []


def test_rank_df_is_empty_when_rank_sources_fail():
    """排行榜数据源全失败时返回空表，不得用硬编码基金池伪造排名。"""
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        analysis_service, "_call_akshare", side_effect=RuntimeError("offline")
    ):
        assert analysis_service._load_rank_df().empty


# ---------------------------------------------------------------------------
# API：数据源不可用必须与"基金不存在"区分
# ---------------------------------------------------------------------------


def test_analysis_api_returns_503_when_fund_list_unavailable():
    app = FastAPI()
    app.include_router(analysis.router, prefix="/api")
    with patch.object(fund_service, "list_all", return_value=[]):
        with TestClient(app) as client:
            response = client.get("/api/analysis/peers/000001")
    assert response.status_code == 503


def test_analysis_api_returns_404_for_unknown_fund():
    app = FastAPI()
    app.include_router(analysis.router, prefix="/api")
    with patch.object(fund_service, "list_all", return_value=[stub_fund()]):
        with TestClient(app) as client:
            response = client.get("/api/analysis/peers/999999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 假净值 → 假指标 整条链必须不存在
# ---------------------------------------------------------------------------


def nav_frame(values):
    return pd.DataFrame(
        {
            "净值日期": pd.to_datetime([f"2026-01-{i + 1:02d}" for i in range(len(values))]),
            "单位净值": values,
            "日增长率": [0.0] * len(values),
        }
    )


@pytest.mark.parametrize("rows", [0, 1, 2])
def test_metrics_refuse_to_invent_values_without_enough_nav(rows):
    """净值样本不足时必须报错，不得返回 volatility/beta 之类的设定值。"""
    with pytest.raises(ValueError):
        fund_service._metrics_from_nav(nav_frame([1.0] * rows), "股票型")


@pytest.mark.parametrize("rows", [0, 1])
def test_returns_refuse_to_invent_values_without_enough_nav(rows):
    with pytest.raises(ValueError):
        fund_service._returns_from_nav(nav_frame([1.0] * rows))


def test_get_by_code_refuses_insufficient_nav_series():
    """净值只有 2 条时无法算波动率，详情接口必须报错而不是编造指标。"""
    with patch.object(fund_service, "_load_fund_list", return_value=[stub_fund()]), patch.object(
        fund_service, "_fetch_nav_history", return_value=nav_frame([1.0, 1.1])
    ), patch.object(fund_service, "_fetch_real_sectors", return_value=None), patch.object(
        fund_service, "_fetch_real_holdings", return_value=None
    ), patch.object(fund_service, "_fetch_basic_info", return_value={}):
        with pytest.raises(ValueError):
            fund_service.get_by_code("000001")


def test_get_by_code_computes_metrics_from_real_nav_only():
    """有足够真实净值时，指标必须来自这条真实序列，且不编造从业天数。"""
    values = [1.0, 1.1, 1.2, 1.15, 1.3]
    with patch.object(fund_service, "_load_fund_list", return_value=[stub_fund()]), patch.object(
        fund_service, "_fetch_nav_history", return_value=nav_frame(values)
    ), patch.object(
        fund_service, "_fetch_real_sectors", return_value=None
    ), patch.object(
        fund_service, "_fetch_real_holdings", return_value=None
    ), patch.object(
        fund_service, "_fetch_basic_info", return_value={}
    ):
        detail = fund_service.get_by_code("000001")

    assert detail.nav == round(values[-1], 4)
    assert detail.metrics.volatility > 0
    assert detail.metrics.max_drawdown <= 0
    # 数据源不提供任职起始日 → 必须是 None，而不是用成立日期估算的数字
    assert detail.manager_days is None
    # 未取到行业/重仓数据 → 留空，而不是填充默认持仓
    assert detail.sectors == []
    assert detail.top_holdings == []


def test_get_by_code_keeps_real_sectors_when_available():
    sectors = [Sector(name="金融", weight=30.0, color="#0071e3")]
    with patch.object(fund_service, "_load_fund_list", return_value=[stub_fund()]), patch.object(
        fund_service, "_fetch_nav_history", return_value=nav_frame([1.0, 1.1, 1.2])
    ), patch.object(
        fund_service, "_fetch_real_sectors", return_value=sectors
    ), patch.object(
        fund_service, "_fetch_real_holdings", return_value=None
    ), patch.object(
        fund_service, "_fetch_basic_info", return_value={}
    ):
        detail = fund_service.get_by_code("000001")
    assert [s.name for s in detail.sectors] == ["金融"]


def test_drawdown_is_empty_when_nav_source_returns_nothing():
    with patch.object(fund_service, "nav_history", return_value=EMPTY_NAV):
        assert analysis_service.drawdown("000001", NavPeriod.ONE_YEAR) == []


def test_market_kline_is_empty_when_nav_source_returns_nothing():
    with patch.object(fund_service, "_fetch_nav_history", return_value=EMPTY_NAV):
        assert market_service.kline("000001", NavPeriod.DAILY, "1Y") == []


# ---------------------------------------------------------------------------
# 源码守卫：禁止把造假生成器重新引入 services/
# ---------------------------------------------------------------------------

FORBIDDEN_PATTERNS = {
    r"math\.sin": "禁止用三角函数生成曲线数据",
    r"\brandom\b": "禁止用随机数生成金融数据",
    r"seededRandom|seed_random": "禁止用种子随机数生成金融数据",
    r"_default_fund_list": "禁止硬编码基金池",
    r"_fallback_nav_history": "禁止生成兜底净值序列",
    r"_default_sectors|_default_top_holdings": "禁止硬编码行业/重仓股",
    r"_DEFAULT_INDICES|_DEFAULT_FUND_CODES": "禁止硬编码指数/基金代码兜底",
}


@pytest.mark.parametrize("pattern,reason", sorted(FORBIDDEN_PATTERNS.items()))
def test_services_contain_no_fabricated_data_generators(pattern, reason):
    offenders = []
    for path in sorted(SERVICES_DIR.glob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(pattern, line):
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not offenders, f"{reason} —— 发现: {offenders}"
