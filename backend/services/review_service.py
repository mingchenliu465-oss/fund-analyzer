"""AI 每日复盘服务。

MVP 阶段使用规则引擎（基于真实数据：收益归因/资产快照/持仓结构）生成
结构化复盘文案。接口采用 provider 模式，为未来接入 DeepSeek/OpenAI 预留
扩展点：任何 LLM 只要实现 `_generate_segments(context)` 语义即可替换规则引擎，
不改变前端契约（segments + summary 结构）。
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Callable

from services import portfolio_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM 扩展点（本轮用规则引擎，未来接入真 LLM 替换即可）
# ---------------------------------------------------------------------------

def _generate_with_llm(context: dict, provider: str) -> list[dict]:
    """未来接入 DeepSeek/OpenAI 时在此调用 LLM，返回与规则引擎同构的 segments。

    context 已包含：
      attribution：今日归因（summary + contributions）
      snapshots  ：资产历史快照
      structure  ：持仓类型占比
    接入方式示例（后续实现）：
        import os, openai
        client = openai.OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url=os.environ.get("DEEPSEEK_BASE_URL"))
        resp = client.chat.completions.create(model="deepseek-chat", messages=[...])
        ... parse to [ {type, text}, ... ]

    当前阶段未配置 API key，抛错并回退规则引擎。
    """
    raise NotImplementedError(
        f"LLM provider '{provider}' 尚未接入；当前使用规则引擎生成。"
    )


# ---------------------------------------------------------------------------
# 规则引擎
# ---------------------------------------------------------------------------

def _round_asset(v: float) -> str:
    return f"¥{round(v, 2):,.2f}"


def _seg(type_: str, text: str) -> dict:
    return {"type": type_, "text": text}


def _build_segments(context: dict) -> list[dict]:
    segments: list[dict] = []
    a = context.get("attribution")
    structure = context.get("structure", {})

    # ── 收益与贡献 ──
    has_holding = bool(a and a.get("contributions"))
    if has_holding and a.get("today_return") is not None:
        tr = a["today_return"]
        pct = a.get("today_return_pct", 0.0)
        up = tr >= 0
        perf = (
            f"今日组合收益 {'+' if up else ''}{_round_asset(tr)}"
            f"（{'+' if up else ''}{pct:.2f}%），整体表现"
            f"{'上涨' if up else '下跌'}。"
        )
        segments.append(_seg("收益", perf))

        summary = a.get("summary", {})
        gainer = summary.get("top_gainer_name")
        loser = summary.get("top_loser_name")
        if gainer:
            segments.append(_seg("贡献", f"主要贡献来自 {gainer}。"))
        if loser:
            segments.append(_seg("拖累", f"拖累来自 {loser}。"))
    elif not has_holding:
        segments.append(_seg("提示", "暂无持仓，今日无收益数据。前往“我的组合”录入持仓后即可生成复盘。"))

    if has_holding and a.get("summary", {}).get("has_stale_nav"):
        segments.append(_seg("提示", "部分行情待更新，当前收益仅包含可用行情。"))

    # ── 配置与风险（有持仓时）──
    if has_holding:
        equity = structure.get("equity_pct", 0.0)
        bond = structure.get("bond_pct", 0.0)
        if equity > 0 or bond > 0:
            if equity > 80:
                segments.append(
                    _seg("配置", f"权益类占比约 {equity:.0f}%，集中度较高，建议增加债券类配置以降低波动。")
                )
            elif bond > 80:
                segments.append(
                    _seg("配置", f"固收类占比约 {bond:.0f}%，偏保守；若投资期限较长，可适度增加权益类配置。")
                )
            else:
                segments.append(
                    _seg("配置", f"权益 {equity:.0f}% / 固收 {bond:.0f}%，配置较为均衡，建议坚持定投、定期再平衡。")
                )

        if structure.get("risk_level"):
            segments.append(
                _seg(
                    "风险",
                    f"组合风险等级为 {structure['risk_level']}（评分 {structure.get('risk_score', 0)}），"
                    f"请结合自身风险承受能力评估。",
                )
            )

    return segments


def generate_daily_review(provider: str = "llm") -> dict:
    """生成今日复盘。

    provider 参数：
      - "llm"：优先尝试 LLM，未配置 API key 时自动回退规则引擎（默认）
      - "rules"：强制使用规则引擎
    返回结构：{ date, provider, segments, summary }
    """
    today = date.today().isoformat()

    # ── 收集上下文（全部来自现有真实数据）──
    attribution = None
    structure = {"equity_pct": 0.0, "bond_pct": 0.0, "risk_level": None, "risk_score": 0}
    try:
        attribution = portfolio_service.attribution()
        if attribution and attribution.get("contributions"):
            contributions = attribution["contributions"]
            total = sum(c["current_value"] for c in contributions)
            equity = 0.0
            bond = 0.0
            for c in contributions:
                ft = c.get("fund_type") or _portfolio_fund_type(c["fund_code"])
                if ft in ("股票型", "ETF", "ETF联接"):
                    equity += c["current_value"]
                elif ft in ("债券型", "货币型"):
                    bond += c["current_value"]
            # 配置权重以持仓市值为基数，不能使用当日盈亏。
            equity_pct = round((equity / total * 100), 1) if total else 0.0
            bond_pct = round((bond / total * 100), 1) if total else 0.0
            structure = {
                "equity_pct": equity_pct,
                "bond_pct": bond_pct,
                "risk_level": _derive_risk_level(equity_pct),
                "risk_score": _derive_risk_score(equity_pct),
            }
    except Exception as exc:
        logger.warning("Daily review data collection failed: %s", exc)
        attribution = None

    context = {
        "attribution": attribution,
        "snapshots": _load_recent_snapshots(),
        "structure": structure,
    }

    # ── 生成 ──
    actual_provider = provider
    if provider == "llm":
        try:
            segments = _generate_with_llm(context, "llm")
            actual_provider = "llm"
        except NotImplementedError:
            logger.info("LLM 未接入，回退规则引擎")
            segments = _build_segments(context)
            actual_provider = "rules"
        except Exception as exc:
            logger.warning("LLM 生成失败，回退规则引擎: %s", exc)
            segments = _build_segments(context)
            actual_provider = "rules"
    else:
        segments = _build_segments(context)
        actual_provider = "rules"

    if not segments:
        segments = [
            _seg("提示", "暂无持仓，今日无复盘内容。前往“我的组合”录入持仓后即可生成复盘。")
        ]

    summary = segments[0]["text"] if segments else ""
    return {
        "date": today,
        "provider": actual_provider,
        "segments": segments,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def _load_recent_snapshots() -> list[dict]:
    try:
        return portfolio_service.portfolio_history("1M")
    except Exception:
        return []


def _portfolio_fund_type(code: str) -> str:
    """从持仓或基金列表取基金类型（用于权重估算）。"""
    try:
        from services import fund_service

        funds = fund_service._load_fund_list()
        f = next((f for f in funds if f.code == code), None)
        return f.type if f else ""
    except Exception:
        return ""


def _derive_risk_level(equity_pct: float) -> str:
    if equity_pct >= 70:
        return "高"
    if equity_pct >= 40:
        return "中高"
    if equity_pct >= 20:
        return "中"
    if equity_pct > 0:
        return "中低"
    return "低"


def _derive_risk_score(equity_pct: float) -> int:
    if equity_pct >= 70:
        return 80
    if equity_pct >= 40:
        return 60
    if equity_pct >= 20:
        return 40
    if equity_pct > 0:
        return 20
    return 10
