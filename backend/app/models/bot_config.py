"""
봇 설정 모델
런타임에 변경 가능한 봇 설정을 저장합니다.
"""
from datetime import datetime
from typing import Dict, Any
from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from backend.app.db.base import Base


class BotConfig(Base):
    """봇 설정 테이블"""
    __tablename__ = "bot_config"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    key: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True,
        comment="설정 키 (예: trading_enabled, interval_minutes)"
    )
    value: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False,
        comment="설정 값 (JSON 형식으로 다양한 타입 지원)"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="설정 설명"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False,
        comment="최종 업데이트 시각"
    )
    
    def __repr__(self) -> str:
        return f"<BotConfig {self.key}={self.value}>"



