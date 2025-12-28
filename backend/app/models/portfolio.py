"""
포트폴리오 스냅샷 모델
시간대별 포트폴리오 가치를 기록합니다.
"""
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any
from sqlalchemy import Numeric, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from backend.app.db.base import Base


class PortfolioSnapshot(Base):
    """포트폴리오 스냅샷 테이블"""
    __tablename__ = "portfolio_snapshots"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    total_value_krw: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False,
        comment="총 자산 가치 (KRW)"
    )
    total_value_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2), nullable=True,
        comment="총 자산 가치 (USD)"
    )
    positions: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False,
        comment="포지션 상세 정보 {symbol: {amount, value, profit_rate}}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True,
        comment="스냅샷 생성 시각"
    )
    
    # 인덱스: 생성일시 기준 시계열 조회 최적화
    __table_args__ = (
        Index('ix_portfolio_snapshots_created_at_desc', 'created_at', postgresql_using='btree'),
    )
    
    def __repr__(self) -> str:
        return f"<PortfolioSnapshot {self.total_value_krw:,.0f} KRW @ {self.created_at}>"



