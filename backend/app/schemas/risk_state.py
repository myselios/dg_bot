"""
리스크 상태 스키마
Pydantic 모델로 요청/응답 데이터 검증
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class RiskStateBase(BaseModel):
    """리스크 상태 기본 스키마"""
    state_date: date = Field(..., description="상태 날짜")
    daily_pnl: Decimal = Field(default=Decimal("0.0"), description="일일 손익률 (%)")
    daily_trade_count: int = Field(default=0, ge=0, description="일일 거래 횟수")
    weekly_pnl: Decimal = Field(default=Decimal("0.0"), description="주간 손익률 (%)")
    safe_mode: bool = Field(default=False, description="안전 모드 활성화 여부")
    safe_mode_reason: str = Field(default="", max_length=255, description="안전 모드 사유")
    last_trade_time: Optional[datetime] = Field(default=None, description="마지막 거래 시간")


class RiskStateCreate(RiskStateBase):
    """리스크 상태 생성 스키마"""
    pass


class RiskStateUpdate(BaseModel):
    """리스크 상태 업데이트 스키마 (부분 업데이트)"""
    daily_pnl: Optional[Decimal] = None
    daily_trade_count: Optional[int] = None
    weekly_pnl: Optional[Decimal] = None
    safe_mode: Optional[bool] = None
    safe_mode_reason: Optional[str] = None
    last_trade_time: Optional[datetime] = None


class RiskStateRead(RiskStateBase):
    """리스크 상태 조회 스키마"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RiskStateDict(BaseModel):
    """기존 JSON 형식 호환 스키마"""
    daily_pnl: float = 0.0
    daily_trade_count: int = 0
    weekly_pnl: float = 0.0
    safe_mode: bool = False
    safe_mode_reason: str = ""
    last_trade_time: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_model(cls, model) -> "RiskStateDict":
        """RiskState 모델에서 변환"""
        return cls(
            daily_pnl=float(model.daily_pnl),
            daily_trade_count=model.daily_trade_count,
            weekly_pnl=float(model.weekly_pnl),
            safe_mode=model.safe_mode,
            safe_mode_reason=model.safe_mode_reason,
            last_trade_time=model.last_trade_time.isoformat() if model.last_trade_time else None,
            updated_at=model.updated_at.isoformat() if model.updated_at else None
        )
