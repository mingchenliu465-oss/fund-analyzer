from fastapi import APIRouter, HTTPException

from services import backtest_service, fund_service

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.get("/{code}")
def get_backtest(code: str):
    """诚实回测：对单只基金跑全部 6 种预设组合，返回引擎的结构化报告。

    报告 dict 即接口契约（字段由 services/backtest_service.py 定义，
    tests/test_backtest_report.py 守住其完整性），此处不做二次加工：
    结论规则、费用口径与披露文本全部以引擎为准，接口层只负责取数与
    把"取不到/不满足纪律"的情况翻译成可读的 HTTP 错误。
    """
    code = code.strip().upper()
    fund = _ensure_exists(code)
    nav = fund_service.nav_history(code)
    if nav is None or nav.empty:
        raise HTTPException(
            status_code=503,
            detail="未取到该基金的历史净值数据，请稍后重试",
        )
    try:
        return backtest_service.run_backtest(nav, code, fund.name)
    except ValueError as exc:
        # 引擎在累计净值缺失/不足时抛 ValueError 并自带可读原因
        # （绝不回退单位净值口径），原样转达给前端展示。
        raise HTTPException(status_code=422, detail=str(exc))


def _ensure_exists(code: str):
    """校验基金存在并返回其摘要。语义与 api/analysis.py 一致：
    基金列表为空说明外部数据源失败，返回 503 而不是误报 404。
    """
    funds = fund_service.list_all()
    if not funds:
        raise HTTPException(
            status_code=503,
            detail="基金列表数据暂时不可用，请稍后重试",
        )
    for fund in funds:
        if fund.code == code:
            return fund
    raise HTTPException(status_code=404, detail=f"Fund {code} not found")
