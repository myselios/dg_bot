"""
거래 내역 스키마
API 요청/응답에 사용되는 Pydantic 모델입니다.
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class TradeBase(BaseModel):
    """거래 기본 스키마"""
    symbol: str = Field(..., description="거래 심볼 (예: KRW-BTC)")
    side: Literal["buy", "sell"] = Field(..., description="매수 또는 매도")
    price: Decimal = Field(..., gt=0, description="체결 가격")
    amount: Decimal = Field(..., gt=0, description="거래 수량")
    total: Decimal = Field(..., gt=0, description="총 거래 금액")
    fee: Decimal = Field(default=Decimal("0"), ge=0, description="거래 수수료")


class TradeCreate(TradeBase):
    """거래 생성 요청 스키마"""
    trade_id: str = Field(..., description="거래소 거래 ID")
    status: Literal["completed", "pending", "failed"] = Field(
        default="completed",
        description="거래 상태"
    )


class TradeUpdate(BaseModel):
    """거래 업데이트 요청 스키마"""
    status: Literal["completed", "pending", "failed"] | None = None
    fee: Decimal | None = Field(None, ge=0)
    
    model_config = ConfigDict(from_attributes=True)


class TradeResponse(TradeBase):
    """거래 조회 응답 스키마"""
    id: int
    trade_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class TradeListResponse(BaseModel):
    """거래 목록 응답 스키마"""
    trades: list[TradeResponse]
    total: int = Field(..., description="전체 거래 수")
    page: int = Field(default=1, description="현재 페이지")
    page_size: int = Field(default=50, description="페이지당 항목 수")
    
    model_config = ConfigDict(from_attributes=True)


class TradeStatistics(BaseModel):
    """거래 통계 스키마"""
    total_trades: int = Field(..., description="총 거래 수")
    total_buy: int = Field(..., description="매수 거래 수")
    total_sell: int = Field(..., description="매도 거래 수")
    total_volume_krw: Decimal = Field(..., description="총 거래 금액 (KRW)")
    total_fee: Decimal = Field(..., description="총 수수료")
    avg_buy_price: Decimal | None = Field(None, description="평균 매수가")
    avg_sell_price: Decimal | None = Field(None, description="평균 매도가")
    
    model_config = ConfigDict(from_attributes=True)



