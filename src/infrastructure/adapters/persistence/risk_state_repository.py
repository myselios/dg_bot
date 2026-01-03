"""
리스크 상태 저장소 (PostgreSQL)

기존 JSON 파일 기반 RiskStateManager를 대체합니다.
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.risk_state import RiskState
from backend.app.schemas.risk_state import RiskStateCreate, RiskStateRead


class RiskStateRepository:
    """
    리스크 상태 저장소

    PostgreSQL을 통해 날짜별 리스크 상태를 관리합니다.
    """

    def __init__(self, session: AsyncSession):
        """
        초기화

        Args:
            session: SQLAlchemy 비동기 세션
        """
        self._session = session

    async def save(self, state_data: RiskStateCreate) -> RiskState:
        """
        상태 저장 (upsert)

        해당 날짜의 레코드가 있으면 업데이트, 없으면 생성합니다.

        Args:
            state_data: 저장할 상태 데이터

        Returns:
            저장된 RiskState 모델
        """
        # 기존 레코드 조회
        existing = await self.load_by_date(state_data.state_date)

        if existing:
            # 업데이트
            existing.daily_pnl = state_data.daily_pnl
            existing.daily_trade_count = state_data.daily_trade_count
            existing.weekly_pnl = state_data.weekly_pnl
            existing.safe_mode = state_data.safe_mode
            existing.safe_mode_reason = state_data.safe_mode_reason
            existing.last_trade_time = state_data.last_trade_time

            await self._session.commit()
            await self._session.refresh(existing)
            return existing
        else:
            # 새로 생성
            new_record = RiskState(
                state_date=state_data.state_date,
                daily_pnl=state_data.daily_pnl,
                daily_trade_count=state_data.daily_trade_count,
                weekly_pnl=state_data.weekly_pnl,
                safe_mode=state_data.safe_mode,
                safe_mode_reason=state_data.safe_mode_reason,
                last_trade_time=state_data.last_trade_time
            )

            self._session.add(new_record)
            await self._session.commit()
            await self._session.refresh(new_record)
            return new_record

    async def load_by_date(self, target_date: date) -> Optional[RiskState]:
        """
        날짜로 상태 조회

        Args:
            target_date: 조회할 날짜

        Returns:
            해당 날짜의 RiskState (없으면 None)
        """
        stmt = select(RiskState).where(RiskState.state_date == target_date)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def load_all(self, days: int = 7) -> List[RiskState]:
        """
        최근 N일간의 상태 조회

        Args:
            days: 조회할 일수 (기본 7일)

        Returns:
            RiskState 목록 (최신순)
        """
        cutoff_date = date.today() - timedelta(days=days)
        stmt = (
            select(RiskState)
            .where(RiskState.state_date >= cutoff_date)
            .order_by(RiskState.state_date.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def calculate_weekly_pnl(self) -> Decimal:
        """
        최근 7일간의 손익률 합계 계산

        Returns:
            주간 손익률 합계
        """
        states = await self.load_all(days=7)
        total_pnl = sum(state.daily_pnl for state in states)
        return Decimal(str(total_pnl))

    async def delete_old_records(self, days: int = 30) -> int:
        """
        오래된 레코드 삭제

        Args:
            days: 보관 일수 (기본 30일)

        Returns:
            삭제된 레코드 수
        """
        from sqlalchemy import delete

        cutoff_date = date.today() - timedelta(days=days)
        stmt = delete(RiskState).where(RiskState.state_date < cutoff_date)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount
