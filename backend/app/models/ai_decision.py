"""
AI 판단 로그 모델
AI의 매매 의사결정 과정을 기록합니다.
"""
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any
from sqlalchemy import String, Numeric, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from backend.app.db.base import Base


class AIDecision(Base):
    """AI 판단 로그 테이블"""
    __tablename__ = "ai_decisions"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True,
        comment="거래 심볼 (예: KRW-BTC)"
    )
    decision: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True,
        comment="AI 판단: buy, sell, hold"
    )
    confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True,
        comment="판단 신뢰도 (0-100%)"
    )
    reason: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="AI 판단 이유"
    )
    market_data: Mapped[Dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True,
        comment="당시 시장 데이터 (OHLCV, 기술적 지표 등)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True,
        comment="판단 시각"
    )
    
    # 복합 인덱스: 심볼 + 판단 + 생성일시 조회 최적화
    __table_args__ = (
        Index('ix_ai_decisions_symbol_decision_created_at', 'symbol', 'decision', 'created_at'),
    )
    
    def __repr__(self) -> str:
        return f"<AIDecision {self.symbol} {self.decision} ({self.confidence}%)>"



