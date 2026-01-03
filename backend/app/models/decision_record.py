"""
DecisionRecord Model - 확장된 AI 판단 기록

프롬프트 버전 추적 및 PnL 연동을 위한 확장 모델
"""
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional
from sqlalchemy import String, Numeric, DateTime, Text, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from backend.app.db.base import Base


class DecisionRecordModel(Base):
    """확장된 AI 판단 기록 테이블"""
    __tablename__ = "decision_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # 기본 결정 정보
    symbol: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True,
        comment="거래 심볼 (예: KRW-BTC)"
    )
    decision: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True,
        comment="AI 판단: ALLOW, BLOCK, HOLD"
    )
    confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True,
        comment="판단 신뢰도 (0-100)"
    )
    reason: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="AI 판단 이유"
    )

    # 프롬프트 버전 추적
    prompt_version: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True,
        comment="프롬프트 버전 (예: 1.0.0)"
    )
    prompt_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="프롬프트 타입: ENTRY, EXIT, GENERAL"
    )
    params: Mapped[Dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True,
        comment="AI 호출 파라미터 (temperature, model 등)"
    )

    # PnL 연동
    pnl_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True,
        comment="손익률 (%)"
    )
    is_profitable: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True,
        comment="수익 여부"
    )
    exit_reason: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="청산 이유: take_profit, stop_loss, manual 등"
    )

    # 시간 정보
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True,
        comment="판단 시각"
    )
    pnl_linked_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
        comment="PnL 연동 시각"
    )

    # 인덱스
    __table_args__ = (
        Index('ix_decision_records_symbol_created', 'symbol', 'created_at'),
        Index('ix_decision_records_version_created', 'prompt_version', 'created_at'),
        Index('ix_decision_records_profitable', 'is_profitable', 'created_at'),
    )

    def __repr__(self) -> str:
        return f"<DecisionRecord {self.symbol} {self.decision} v{self.prompt_version}>"
