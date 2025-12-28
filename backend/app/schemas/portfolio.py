"""
포트폴리오 스키마
API 요청/응답에 사용되는 Pydantic 모델입니다.
"""
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class PositionInfo(BaseModel):
    """포지션 정보"""
    amount: Decimal = Field(..., description="보유 수량")
    value_krw: Decimal = Field(..., description="평가 금액 (KRW)")
    avg_buy_price: Decimal | None = Field(None, description="평균 매수가")
    profit_rate: Decimal | None = Field(None, description="수익률 (%)")
    profit_amount: Decimal | None = Field(None, description="수익 금액")


class PortfolioSnapshotBase(BaseModel):
    """포트폴리오 스냅샷 기본 스키마"""
    total_value_krw: Decimal = Field(..., gt=0, description="총 자산 가치 (KRW)")
    total_value_usd: Decimal | None = Field(None, description="총 자산 가치 (USD)")
    positions: Dict[str, PositionInfo] = Field(..., description="포지션별 상세 정보")


class PortfolioSnapshotCreate(PortfolioSnapshotBase):
    """포트폴리오 스냅샷 생성 요청 스키마"""
    pass


class PortfolioSnapshotResponse(PortfolioSnapshotBase):
    """포트폴리오 스냅샷 조회 응답 스키마"""
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class PortfolioSnapshotListResponse(BaseModel):
    """포트폴리오 스냅샷 목록 응답 스키마"""
    snapshots: list[PortfolioSnapshotResponse]
    total: int = Field(..., description="전체 스냅샷 수")
    page: int = Field(default=1, description="현재 페이지")
    page_size: int = Field(default=50, description="페이지당 항목 수")
    
    model_config = ConfigDict(from_attributes=True)


class PortfolioPerformance(BaseModel):
    """포트폴리오 성과 스키마"""
    current_value_krw: Decimal = Field(..., description="현재 총 자산 (KRW)")
    initial_value_krw: Decimal = Field(..., description="초기 투자 금액 (KRW)")
    total_profit_krw: Decimal = Field(..., description="총 수익 (KRW)")
    total_profit_rate: Decimal = Field(..., description="총 수익률 (%)")
    daily_profit: Decimal | None = Field(None, description="일일 수익")
    weekly_profit: Decimal | None = Field(None, description="주간 수익")
    monthly_profit: Decimal | None = Field(None, description="월간 수익")
    max_drawdown: Decimal | None = Field(None, description="최대 낙폭 (%)")
    sharpe_ratio: Decimal | None = Field(None, description="샤프 비율")
    
    model_config = ConfigDict(from_attributes=True)



