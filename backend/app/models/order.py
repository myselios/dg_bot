"""
주문 내역 모델
거래소에 제출된 주문의 상태를 추적합니다.
"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Numeric, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class Order(Base):
    """주문 내역 테이블"""
    __tablename__ = "orders"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True,
        comment="거래소에서 반환한 고유 주문 ID"
    )
    symbol: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True,
        comment="거래 심볼 (예: KRW-BTC)"
    )
    side: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="매수(buy) 또는 매도(sell)"
    )
    order_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="주문 유형: market, limit"
    )
    price: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 8), nullable=True,
        comment="주문 가격 (지정가의 경우)"
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False,
        comment="주문 수량"
    )
    filled_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), default=Decimal("0"), nullable=False,
        comment="체결된 수량"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True,
        comment="주문 상태: open, filled, cancelled, failed"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="에러 발생 시 메시지"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True,
        comment="주문 생성 시각"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False,
        comment="최종 업데이트 시각"
    )
    
    # 복합 인덱스: 심볼 + 상태 + 생성일시 조회 최적화
    __table_args__ = (
        Index('ix_orders_symbol_status_created_at', 'symbol', 'status', 'created_at'),
    )
    
    def __repr__(self) -> str:
        return f"<Order {self.order_id} {self.side} {self.amount} {self.symbol} ({self.status})>"



