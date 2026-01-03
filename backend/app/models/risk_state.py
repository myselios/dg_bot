"""
리스크 상태 모델
날짜별 리스크 관리 상태를 저장합니다.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from sqlalchemy import Date, Numeric, DateTime, Integer, Boolean, String, Index
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class RiskState(Base):
    """리스크 상태 테이블"""
    __tablename__ = "risk_states"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    state_date: Mapped[date] = mapped_column(
        Date, nullable=False, unique=True, index=True,
        comment="상태 날짜 (YYYY-MM-DD)"
    )

    daily_pnl: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, default=Decimal("0.0"),
        comment="일일 손익률 (%)"
    )

    daily_trade_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="일일 거래 횟수"
    )

    weekly_pnl: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, default=Decimal("0.0"),
        comment="주간 손익률 (%)"
    )

    safe_mode: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="안전 모드 활성화 여부"
    )

    safe_mode_reason: Mapped[str] = mapped_column(
        String(255), nullable=False, default="",
        comment="안전 모드 사유"
    )

    last_trade_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True,
        comment="마지막 거래 시간"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False,
        comment="생성 시각"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False,
        comment="수정 시각"
    )

    # 인덱스: 날짜 기준 조회 최적화
    __table_args__ = (
        Index('ix_risk_states_state_date_desc', 'state_date', postgresql_using='btree'),
        {'extend_existing': True}
    )

    def __repr__(self) -> str:
        return f"<RiskState {self.state_date} pnl={self.daily_pnl}% trades={self.daily_trade_count}>"

    def to_dict(self) -> dict:
        """딕셔너리로 변환 (기존 JSON 형식 호환)"""
        return {
            'daily_pnl': float(self.daily_pnl),
            'daily_trade_count': self.daily_trade_count,
            'weekly_pnl': float(self.weekly_pnl),
            'safe_mode': self.safe_mode,
            'safe_mode_reason': self.safe_mode_reason,
            'last_trade_time': self.last_trade_time.isoformat() if self.last_trade_time else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
