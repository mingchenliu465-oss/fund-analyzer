"""分析数据服务：回撤、同类对比、排名、组合概览、资金流向、AI 解读。"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd

from services.fund_service import _call_akshare

from models.analysis import (
    AICommentary,
    AllocationItem,
    FlowPeriod,
    FundFlow,
    HoldStructure,
    HoldStructurePoint,
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
    global_peak = 0.0
    for bucket, group in df.groupby("bucket", sort=True):
        nav_values = group["单位净值"].values
        bucket_max_dd = 0.0
        for v in nav_values:
            if v > global_peak:
                global_peak = v
            if global_peak > 0:
                dd = (v - global_peak) / global_peak
                if dd < bucket_max_dd:
                    bucket_max_dd = dd
        label = bucket.strftime(date_format)
        points.append(DrawdownPoint(date=label, drawdown=round(bucket_max_dd, 4)))
    return points


def _load_rank_df() -> pd.DataFrame:
    """加载开放式基金与场内 ETF 排名数据。

    两个排行榜接口并行调用（原串行最坏 20s+）；两者都失败时回退默认快照
    构建排名表，保证 peers/ranking 等分析接口不为空。
    """
    cache_key = "rank_df"
    cached = fund_service._get_cache(cache_key)
    if cached is not None:
        return cached

    with ThreadPoolExecutor(max_workers=2) as _ex:
        _f_open = _ex.submit(_call_akshare, ak.fund_open_fund_rank_em, timeout=10)
        _f_etf = _ex.submit(_call_akshare, ak.fund_exchange_rank_em, timeout=10)
        try:
            open_df = _f_open.result()
            open_df = open_df[["基金代码", "基金简称", "近1年"]].copy()
            open_df["source"] = "open"
        except Exception:
            open_df = pd.DataFrame(columns=["基金代码", "基金简称", "近1年", "source"])

        try:
            etf_df = _f_etf.result()
            etf_df = etf_df[["基金代码", "基金简称", "近1年"]].copy()
            etf_df["source"] = "etf"
        except Exception:
            etf_df = pd.DataFrame(columns=["基金代码", "基金简称", "近1年", "source"])

    df = pd.concat([open_df, etf_df], ignore_index=True)
    df["近1年"] = pd.to_numeric(df["近1年"], errors="coerce")
    # 过滤无效收益数据（NaN、0、极端异常值），确保排名基于有效基金
    df = df[df["近1年"].notna() & (df["近1年"] != 0)]
    df = df.drop_duplicates(subset=["基金代码"], keep="first")
    df = df.sort_values("近1年", ascending=False).reset_index(drop=True)

    if df.empty:
        # 排行榜数据源不可用：用默认快照构建排名表，避免分析接口为空
        rows = [
            {"基金代码": f.code, "基金简称": f.name, "近1年": f.one_year_return * 100, "source": "open"}
            for f in fund_service._default_fund_list()
            if f.one_year_return != 0
        ]
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("近1年", ascending=False).reset_index(drop=True)

    fund_service._set_cache(cache_key, df, ttl=1800)
    return df


def _rank_dict() -> dict[str, float]:
    """把排名 DataFrame 转成 code -> 近1年收益(小数) 的字典。排除无效收益。"""
    df = _load_rank_df()
    return {
        str(row["基金代码"]): float(row["近1年"]) / 100
        for _, row in df.iterrows()
        if pd.notna(row["近1年"]) and float(row["近1年"]) != 0
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
    """按近一年收益排名。仅统计有效收益的基金。"""
    upper = code.strip().upper()
    df = _load_rank_df()  # 已过滤 NaN 和零值
    total = len(df)
    if total == 0:
        return ReturnRanking(rank=0, total=0, percentile=0)

    # 使用 index 快速定位（DataFrame 按近1年降序排列）
    positions = df.index[df["基金代码"] == upper].tolist()
    if positions:
        rank = int(positions[0]) + 1
        percentile = round(rank / total * 100)
    else:
        # 基金不在排名列表中（可能是冷门基金或数据缺失）
        return ReturnRanking(rank=0, total=total, percentile=0)
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


def hold_structure() -> HoldStructure:
    """全市场机构/个人持有比例趋势。

    数据来源：akshare fund_hold_structure_em()，为全市场汇总数据，
    非单只基金数据。用于了解整体市场情绪和机构参与度趋势。
    """
    cache_key = "hold_structure"
    cached = fund_service._get_cache(cache_key)
    if cached is not None:
        return cached

    points: list[HoldStructurePoint] = []
    try:
        df = _call_akshare(ak.fund_hold_structure_em, timeout=15)
        logger.info("hold_structure: got %d rows, columns=%s", len(df), list(df.columns))

        # akshare 列名可能使用 "比列"（列）而非 "比例"（例），做列名映射
        col_map: dict[str, str] = {}
        for col in df.columns:
            if "截止日期" in col or "日期" in col:
                col_map["date"] = col
            elif "基金家数" in col or "家数" in col:
                col_map["funds"] = col
            elif "机构" in col and ("持有" in col or "占比" in col):
                col_map["inst"] = col
            elif "个人" in col and ("持有" in col or "占比" in col):
                col_map["indv"] = col
            elif "内部" in col and ("持有" in col or "占比" in col):
                col_map["intl"] = col
            elif "总份额" in col or "份额" in col:
                col_map["shares"] = col

        if len(col_map) < 6:
            logger.warning("hold_structure: column mapping incomplete, found: %s", list(col_map.keys()))

        for _, row in df.iterrows():
            try:
                points.append(HoldStructurePoint(
                    date=str(row.get(col_map.get("date", ""), ""))[:10],
                    fund_count=int(row.get(col_map.get("funds", ""), 0) or 0),
                    institution_pct=float(row.get(col_map.get("inst", ""), 0) or 0),
                    individual_pct=float(row.get(col_map.get("indv", ""), 0) or 0),
                    internal_pct=float(row.get(col_map.get("intl", ""), 0) or 0),
                    total_shares=float(row.get(col_map.get("shares", ""), 0) or 0),
                ))
            except (ValueError, TypeError):
                continue
    except Exception as exc:
        logger.warning("hold_structure fetch failed: %s", exc)

    result = HoldStructure(
        points=points,
        note="全市场汇总数据（非单只基金），用于了解机构/个人持仓趋势。数据来源：天天基金/东方财富。",
    )
    fund_service._set_cache(cache_key, result, ttl=7200)  # 2 小时缓存
    return result


def flow(code: str) -> FundFlow:
    """资金流向：暂无真实数据源，返回空（后续阶段接入）。"""
    return FundFlow(code=code.strip().upper(), periods=[])


def commentary(code: str) -> AICommentary:
    """基于真实指标的数据分析摘要（非 AI 生成）。

    根据基金的实际收益率、回撤、波动率、Sharpe 比率等指标，
    生成结构化的分析文本。所有数据均来自真实计算。
    """
    upper = code.strip().upper()
    try:
        fund = fund_service.get_by_code(upper)
    except Exception:
        return AICommentary(
            performance=f"未找到基金代码 {upper} 的数据。",
            risk_warning="暂无数据",
            suitable_for="暂无数据",
            suggestion="请确认基金代码是否正确。",
        )

    name = fund.name
    ftype = fund.type
    ret_1y = fund.one_year_return
    m = fund.metrics
    ret_str = f"{ret_1y * 100:+.2f}%"
    dd_str = f"{m.max_drawdown * 100:.1f}%"
    vol_str = f"{m.volatility * 100:.1f}%"
    sharpe_str = f"{m.sharpe:.2f}"

    # ── 收益描述 ──
    if ret_1y > 0.20:
        perf = f"{name} 近一年收益率 {ret_str}，表现优异，显著跑赢同类平均。"
    elif ret_1y > 0.05:
        perf = f"{name} 近一年收益率 {ret_str}，处于同类中等水平。"
    elif ret_1y > 0:
        perf = f"{name} 近一年收益率 {ret_str}，收益偏保守。"
    elif ret_1y > -0.10:
        perf = f"{name} 近一年收益率 {ret_str}，短期承压，需关注后续表现。"
    else:
        perf = f"{name} 近一年收益率 {ret_str}，跌幅较大，建议审慎评估。"

    # ── 风险描述 ──
    risks = []
    if m.max_drawdown < -0.30:
        risks.append(f"最大回撤 {dd_str}，回撤幅度较大")
    elif m.max_drawdown < -0.10:
        risks.append(f"最大回撤 {dd_str}，处于可接受范围")
    else:
        risks.append(f"最大回撤仅 {dd_str}，风险控制较好")

    if m.volatility > 0.25:
        risks.append(f"年化波动率 {vol_str}，波动较高")
    elif m.volatility > 0.10:
        risks.append(f"年化波动率 {vol_str}，波动适中")
    else:
        risks.append(f"年化波动率 {vol_str}，波动较低")

    risk_warning = "；".join(risks) + "。"

    # ── 适合人群 ──
    risk_score = m.risk_score
    if risk_score >= 75:
        suitable_for = "适合风险承受能力较强、投资周期 3 年以上的积极型投资者。"
    elif risk_score >= 50:
        suitable_for = "适合风险承受能力中等、投资周期 1-3 年的稳健型投资者。"
    elif risk_score >= 25:
        suitable_for = "适合风险偏好较低、追求稳健收益的保守型投资者。"
    else:
        suitable_for = "适合风险厌恶型投资者，可作为现金管理或短期配置工具。"

    # ── 配置建议 ──
    if ftype == "货币型":
        suggestion = "建议作为组合流动性缓冲，保留 3-6 个月生活费的仓位。"
    elif ftype == "债券型":
        suggestion = "适合作为组合底仓（建议占 30%-50%），与权益基金搭配可降低整体波动。"
    elif sharpe_str and m.sharpe > 0.5:
        suggestion = f"Sharpe 比率 {sharpe_str}，风险调整后收益尚可。建议通过定投方式参与，避免单笔重仓。"
    elif m.sharpe > 0:
        suggestion = f"Sharpe 比率 {sharpe_str}，风险调整后收益偏低。建议控制仓位在组合的 10%-20%。"
    else:
        suggestion = "当前风险收益比较低，建议观望或仅少量配置。"

    return AICommentary(
        performance=perf,
        risk_warning=risk_warning,
        suitable_for=suitable_for,
        suggestion=suggestion,
    )
