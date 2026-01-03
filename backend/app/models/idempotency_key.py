"""
Idempotency Key 모델

중복 주문 방지를 위한 idempotency key 저장 테이블
키 형식: {ticker}-{timeframe}-{candle_ts}-{action}
"""
from datetime import datetime
from sqlalchemy import String, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class IdempotencyKey(Base):
    """Idempotency Key 테이블"""
    __tablename__ = "idempotency_keys"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    key: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True,
        comment="Idempotency 키 (ticker-timeframe-candle_ts-action)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now,
        comment="생성 시각"
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True,
        comment="만료 시각"
    )

    # 만료 시각 기준 인덱스 (cleanup 쿼리 최적화)
    __table_args__ = (
        Index('ix_idempotency_keys_expires_at', 'expires_at'),
    )

    def __repr__(self) -> str:
        return f"<IdempotencyKey(key={self.key}, expires_at={self.expires_at})>"

    @property
    def is_expired(self) -> bool:
        """키가 만료되었는지 확인"""
        return datetime.now() >= self.expires_at
