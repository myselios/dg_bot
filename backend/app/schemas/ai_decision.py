"""
AI 판단 로그 스키마
API 요청/응답에 사용되는 Pydantic 모델입니다.
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class AIDecisionBase(BaseModel):
    """AI 판단 기본 스키마"""
    symbol: str = Field(..., description="거래 심볼 (예: KRW-BTC)")
    decision: Literal["buy", "sell", "hold"] = Field(..., description="AI 판단")
    confidence: Decimal | None = Field(None, ge=0, le=100, description="신뢰도 (0-100%)")
    reason: str | None = Field(None, description="판단 이유")


class AIDecisionCreate(AIDecisionBase):
    """AI 판단 생성 요청 스키마"""
    market_data: Dict[str, Any] | None = Field(None, description="시장 데이터 (OHLCV, 지표 등)")


class AIDecisionResponse(AIDecisionBase):
    """AI 판단 조회 응답 스키마"""
    id: int
    market_data: Dict[str, Any] | None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class AIDecisionListResponse(BaseModel):
    """AI 판단 목록 응답 스키마"""
    decisions: list[AIDecisionResponse]
    total: int = Field(..., description="전체 판단 수")
    page: int = Field(default=1, description="현재 페이지")
    page_size: int = Field(default=50, description="페이지당 항목 수")
    
    model_config = ConfigDict(from_attributes=True)


class AIDecisionStatistics(BaseModel):
    """AI 판단 통계 스키마"""
    total_decisions: int = Field(..., description="총 판단 수")
    buy_count: int = Field(..., description="매수 판단 수")
    sell_count: int = Field(..., description="매도 판단 수")
    hold_count: int = Field(..., description="관망 판단 수")
    avg_confidence: Decimal | None = Field(None, description="평균 신뢰도")
    buy_accuracy: Decimal | None = Field(None, description="매수 판단 정확도")
    sell_accuracy: Decimal | None = Field(None, description="매도 판단 정확도")
    
    model_config = ConfigDict(from_attributes=True)



