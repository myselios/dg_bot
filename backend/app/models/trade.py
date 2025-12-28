"""
거래 내역 모델
모든 매수/매도 거래 기록을 저장합니다.
"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Numeric, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class Trade(Base):
    """거래 내역 테이블"""
    __tablename__ = "trades"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    trade_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True,
        comment="거래소에서 반환한 고유 거래 ID"
    )
    symbol: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True,
        comment="거래 심볼 (예: KRW-BTC)"
    )
    side: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="매수(buy) 또는 매도(sell)"
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False,
        comment="체결 가격"
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False,
        comment="거래 수량"
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False,
        comment="총 거래 금액 (price * amount)"
    )
    fee: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), default=Decimal("0"), nullable=False,
        comment="거래 수수료"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True,
        comment="거래 상태: completed, pending, failed"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True,
        comment="거래 생성 시각"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False,
        comment="최종 업데이트 시각"
    )
    
    # 복합 인덱스: 심볼 + 생성일시 조회 최적화
    __table_args__ = (
        Index('ix_trades_symbol_created_at', 'symbol', 'created_at'),
    )
    
    def __repr__(self) -> str:
        return f"<Trade {self.trade_id} {self.side} {self.amount} {self.symbol} @ {self.price}>"



