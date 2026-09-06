"""AI 每日复盘 REST API。"""

from fastapi import APIRouter, Query

from services import review_service

router = APIRouter(prefix="/review", tags=["review"])


@router.get("/daily")
def get_daily_review(
    provider: str = Query(
        default="llm",
        description="生成方式：llm（优先 LLM，未配置则回退规则引擎）或 rules（强制规则引擎）",
    ),
):
    """AI 每日复盘（MVP：规则引擎生成，预留 LLM 接口）。"""
    return review_service.generate_daily_review(provider=provider)
