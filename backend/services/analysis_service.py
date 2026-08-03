"""分析数据服务：回撤、同类对比、排名、组合概览、资金流向、AI 解读。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd

from models.analysis import (
    AICommentary,
    AllocationItem,
    FlowPeriod,
    FundFlow,
    PeerComparison,
    PortfolioOverview,
    ReturnRanking,
)
from models.market import DrawdownPoint, NavPeriod
from services import fund_service

logger = logging.getLogger(__name__)


def _period_to_days(period: NavPeriod) -> int:
    return {
        NavPeriod.FIVE_DAY: 7,
        NavPeriod.TEN_DAY: 14,
        NavPeriod.TWENTY_DAY: 30,
        NavPeriod.DAILY: 60,
        NavPeriod.WEEKLY: 180,
        NavPeriod.MONTHLY: 730,
        NavPeriod.YEARLY: 1825,
        NavPeriod.ONE_MONTH: 30,
        NavPeriod.THREE_MONTH: 90,
        NavPeriod.SIX_MONTH: 180,
        NavPeriod.ONE_YEAR: 365,
        NavPeriod.THREE_YEAR: 1095,
    }[period]


def drawdown(code: str, period: NavPeriod = NavPeriod.ONE_YEAR) -> list[DrawdownPoint]:
    """基于净值序列计算滚动回撤，并按 period 聚合展示。"""
    upper = code.strip().upper()
    df = fund_service.nav_history(upper)
    if df.empty:
        return []

    cutoff = datetime.now() - timedelta(days=_period_to_days(period))
    df = df[df["净值日期"] >= cutoff].copy()
    if df.empty:
        return []

    df = df.sort_values("净值日期").reset_index(drop=True)
    df["净值日期"] = pd.to_datetime(df["净值日期"])
    df["单位净值"] = df["单位净值"].astype(float)

    # 按 period 聚合：取每个桶内的最大回撤（最负值）
    if period in (NavPeriod.ONE_YEAR, NavPeriod.THREE_YEAR, NavPeriod.MONTHLY, NavPeriod.YEARLY):
        df["bucket"] = df["净值日期"].dt.to_period("M")
        date_format = "%Y-%m"
    elif period in (NavPeriod.SIX_MONTH, NavPeriod.THREE_MONTH, NavPeriod.WEEKLY):
        df["bucket"] = df["净值日期"].dt.to_period("W")
        date_format = "%Y-%m-%d"
    else:
        df["bucket"] = df["净值日期"].dt.to_period("D")
        date_format = "%Y-%m-%d"

    points: list[DrawdownPoint] = []
    for bucket, group in df.groupby("bucket", sort=True):
        nav_values = group["单位净值"].values
        peak = nav_values[0]
        bucket_max_dd = 0.0
        for v in nav_values:
            if v > peak:
                peak = v
            dd = (v - peak) / peak
            if dd < bucket_max_dd:
                bucket_max_dd = dd
        label = bucket.strftime(date_format)
        points.append(DrawdownPoint(date=label, drawdown=round(bucket_max_dd, 4)))
    return points


def _load_rank_df() -> pd.DataFrame:
    """加载开放式基金与场内 ETF 排名数据。"""
    cache_key = "rank_df"
    cached = fund_service._get_cache(cache_key)
    if cached is not None:
        return cached

    try:
        open_df = ak.fund_open_fund_rank_em()
        open_df = open_df[["基金代码", "基金简称", "近1年"]].copy()
        open_df["source"] = "open"
    except Exception:
        open_df = pd.DataFrame(columns=["基金代码", "基金简称", "近1年", "source"])

    try:
        etf_df = ak.fund_exchange_rank_em()
        etf_df = etf_df[["基金代码", "基金简称", "近1年"]].copy()
        etf_df["source"] = "etf"
    except Exception:
        etf_df = pd.DataFrame(columns=["基金代码", "基金简称", "近1年", "source"])

    df = pd.concat([open_df, etf_df], ignore_index=True)
    df["近1年"] = pd.to_numeric(df["近1年"], errors="coerce")
    df = df.drop_duplicates(subset=["基金代码"], keep="first")
    df = df.sort_values("近1年", ascending=False).reset_index(drop=True)
    fund_service._set_cache(cache_key, df, ttl=1800)
    return df


def _rank_dict() -> dict[str, float]:
    """把排名 DataFrame 转成 code -> 近1年收益(小数) 的字典。"""
    df = _load_rank_df()
    return {
        str(row["基金代码"]): float(row["近1年"]) / 100
        for _, row in df.iterrows()
        if pd.notna(row["近1年"])
    }


def peers(code: str) -> list[PeerComparison]:
    """返回与目标基金同类型的几只基金对比。"""
    upper = code.strip().upper()

    funds = fund_service.list_all()
    target = next((f for f in funds if f.code == upper), None)
    if target is None:
        return []

    rank_map = _rank_dict()
    target_return = rank_map.get(upper, target.one_year_return)

    # 同类候选
    candidates = [
        f
        for f in funds
        if f.code != upper
        and (f.type == target.type or (target.type == "ETF" and "ETF" in f.type))
    ]

    # 选择与目标收益最接近的基金
    candidates_with_return = [(f, rank_map.get(f.code, 0.0)) for f in candidates if rank_map.get(f.code, 0.0) != 0.0]
    candidates_with_return.sort(key=lambda x: abs(x[1] - target_return))
    selected = [f for f, _ in candidates_with_return[:4]]

    # 凑不够 4 只用热门基金补齐
    if len(selected) < 4:
        existing = {f.code for f in selected}
        hot = [f for f in candidates if f.code not in existing]
        hot.sort(key=lambda f: f.heat, reverse=True)
        selected.extend(hot[: 4 - len(selected)])

    results: list[PeerComparison] = []
    for f in selected:
        one_year = rank_map.get(f.code, 0.0)
        vol = fund_service._risk_level_to_volatility(f.risk_level)
        sharpe = one_year / (vol + 0.001) if vol > 0 else 0.0
        results.append(
            PeerComparison(
                code=f.code,
                name=f.name,
                type=f.type,
                one_year_return=one_year,
                volatility=vol,
                sharpe=round(sharpe, 2),
                risk_level=f.risk_level,
            )
        )
    return results


def ranking(code: str) -> ReturnRanking:
    """按近一年收益排名。"""
    upper = code.strip().upper()
    df = _load_rank_df()
    total = len(df)
    if total == 0:
        return ReturnRanking(rank=1, total=1, percentile=100)

    # 使用 index 快速定位
    positions = df.index[df["基金代码"] == upper].tolist()
    if positions:
        rank = int(positions[0]) + 1
    else:
        rank = total
    percentile = round(rank / total * 100)
    return ReturnRanking(rank=rank, total=total, percentile=percentile)


def portfolio() -> PortfolioOverview:
    """组合概览：由 /api/portfolio 提供真实持仓数据，此接口保留但返回空。"""
    return PortfolioOverview(
        total_assets=0,
        today_return=0,
        today_return_pct=0,
        cumulative_return=0,
        cumulative_return_pct=0,
        allocation=[],
        risk_level="暂无",
        risk_score=0,
    )


def flow(code: str) -> FundFlow:
    """资金流向：暂无真实数据源，返回空（后续阶段接入）。"""
    return FundFlow(code=code.strip().upper(), periods=[])


def commentary(code: str) -> AICommentary:
    """基于基金类型的 AI 解读（模拟）。"""
    upper = code.strip().upper()
    try:
        fund = fund_service.get_by_code(upper)
        name = fund.name
        ftype = fund.type
    except ValueError:
        name = upper
        ftype = "基金"

    if ftype == "货币型":
        return AICommentary(
            performance=f"{name} 作为货币型基金，净值波动极低，七日年化收益保持稳定，适合作为现金管理工具。",
            risk_warning="货币基金虽不保本，但历史上极少出现单日亏损，流动性风险较低。",
            suitable_for="风险厌恶型投资者、短期闲置资金打理。",
            suggestion="可作为组合的流动性缓冲，建议保留 3-6 个月生活费的仓位。",
        )
    if ftype == "债券型":
        return AICommentary(
            performance=f"{name} 近期收益曲线平滑，回撤控制优于权益类产品，在利率下行环境中表现稳健。",
            risk_warning="需关注利率上行带来的净值回撤及信用债违约风险。",
            suitable_for="追求稳健收益、能承受小幅波动的投资者。",
            suggestion="适合作为组合底仓，与权益基金搭配可降低整体波动。",
        )
    if ftype == "ETF":
        return AICommentary(
            performance=f"{name} 跟踪指数透明度高，近一年弹性较大，适合作为战术配置工具。",
            risk_warning="ETF 二级市场存在折溢价与波动风险，行业主题 ETF 回撤可能较大。",
            suitable_for="有一定择时能力、希望低成本获取 Beta 收益的投资者。",
            suggestion="建议结合均线或估值水平进行定投或波段操作，避免追高。",
        )
    return AICommentary(
        performance=f"{name} 近期业绩处于同类中等偏上水平，选股或行业配置贡献主要超额收益。",
        risk_warning="权益仓位较高，短期可能面临 15%-25% 的回撤，需评估自身承受能力。",
        suitable_for="能承受中等以上波动、投资周期不少于 3 年的投资者。",
        suggestion="建议通过定投方式平滑成本，避免单笔重仓，并定期审视基金经理稳定性。",
    )
