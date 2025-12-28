"""
시스템 로그 모델
애플리케이션 실행 중 발생한 모든 이벤트를 기록합니다.
"""
from datetime import datetime
from typing import Dict, Any
from sqlalchemy import String, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from backend.app.db.base import Base


class SystemLog(Base):
    """시스템 로그 테이블"""
    __tablename__ = "system_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    level: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True,
        comment="로그 레벨: info, warning, error, critical"
    )
    message: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="로그 메시지"
    )
    context: Mapped[Dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True,
        comment="추가 컨텍스트 정보 (JSON)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True,
        comment="로그 생성 시각"
    )
    
    # 복합 인덱스: 레벨 + 생성일시 조회 최적화
    __table_args__ = (
        Index('ix_system_logs_level_created_at', 'level', 'created_at'),
    )
    
    def __repr__(self) -> str:
        return f"<SystemLog [{self.level}] {self.message[:50]}...>"



