"""
API v1 라우터
모든 엔드포인트를 통합합니다.
"""
from fastapi import APIRouter

from backend.app.api.v1.endpoints import trades, bot_control

api_router = APIRouter()

# 각 엔드포인트 등록
api_router.include_router(
    trades.router,
    prefix="/trades",
    tags=["trades"]
)

api_router.include_router(
    bot_control.router,
    prefix="/bot",
    tags=["bot-control"]
)

# TODO: 추가 엔드포인트
# api_router.include_router(
#     ai_decisions.router,
#     prefix="/ai",
#     tags=["ai-decisions"]
# )
# api_router.include_router(
#     portfolio.router,
#     prefix="/portfolio",
#     tags=["portfolio"]
# )



