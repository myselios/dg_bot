"""
DecisionRecordAdapter - PostgreSQL 기반 결정 기록 어댑터

AI 결정 기록 저장 및 PnL 연동을 담당합니다.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.ports.outbound.decision_record_port import (
    DecisionRecordPort,
    DecisionRecord,
    PnLLabel,
)
from src.domain.value_objects.ai_decision_result import AIDecisionResult, DecisionType
from src.domain.value_objects.prompt_version import PromptVersion, PromptType

# Import backend model - lazy to avoid circular imports
_DecisionRecordModel = None


def _get_model():
    """Lazy import of DecisionRecordModel."""
    global _DecisionRecordModel
    if _DecisionRecordModel is None:
        from backend.app.models.decision_record import DecisionRecordModel
        _DecisionRecordModel = DecisionRecordModel
    return _DecisionRecordModel


class DecisionRecordAdapter(DecisionRecordPort):
    """
    PostgreSQL 기반 결정 기록 어댑터.

    AI 결정을 저장하고 나중에 PnL 결과와 연동합니다.
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize adapter.

        Args:
            db_session: Async SQLAlchemy session
        """
        self._session = db_session

    async def record(
        self,
        decision: AIDecisionResult,
        prompt_version: PromptVersion,
        params: dict,
    ) -> str:
        """
        Record AI decision.

        Args:
            decision: AI decision result
            prompt_version: Prompt version used
            params: AI call parameters

        Returns:
            Record ID as string
        """
        Model = _get_model()

        db_record = Model(
            symbol=decision.ticker,
            decision=decision.decision.value.upper(),  # Store as uppercase (ALLOW/BLOCK/HOLD)
            confidence=decision.confidence.value,  # Extract int from DecisionConfidence
            reason=decision.reason,
            prompt_version=prompt_version.version,
            prompt_type=prompt_version.prompt_type.value,
            params=params,
        )

        self._session.add(db_record)
        await self._session.flush()
        await self._session.refresh(db_record)

        return str(db_record.id)

    async def link_pnl(
        self,
        record_id: str,
        pnl_label: PnLLabel,
    ) -> bool:
        """
        Link PnL result to decision record.

        Args:
            record_id: Decision record ID
            pnl_label: PnL label with profit/loss info

        Returns:
            True if linked successfully, False if record not found
        """
        Model = _get_model()

        db_record = await self._session.get(Model, int(record_id))
        if db_record is None:
            return False

        db_record.pnl_percent = pnl_label.pnl_percent
        db_record.is_profitable = pnl_label.is_profitable
        db_record.exit_reason = pnl_label.exit_reason
        db_record.pnl_linked_at = datetime.utcnow()

        return True

    async def get_record(self, record_id: str) -> Optional[DecisionRecord]:
        """
        Get decision record by ID.

        Args:
            record_id: Decision record ID

        Returns:
            DecisionRecord or None if not found
        """
        Model = _get_model()

        db_record = await self._session.get(Model, int(record_id))
        if db_record is None:
            return None

        return self._to_domain(db_record)

    async def find_by_ticker(
        self,
        ticker: str,
        limit: int = 10,
    ) -> List[DecisionRecord]:
        """
        Find decision records by ticker.

        Args:
            ticker: Trading pair symbol
            limit: Maximum number of records

        Returns:
            List of DecisionRecord
        """
        Model = _get_model()

        stmt = (
            select(Model)
            .where(Model.symbol == ticker)
            .order_by(Model.created_at.desc())
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        db_records = result.scalars().all()

        return [self._to_domain(r) for r in db_records]

    async def get_accuracy_stats(
        self,
        prompt_version: Optional[str] = None,
        start_date: Optional[datetime] = None,
    ) -> dict:
        """
        Get accuracy statistics.

        Args:
            prompt_version: Filter by prompt version
            start_date: Filter by start date

        Returns:
            Dict with accuracy, total, correct counts
        """
        Model = _get_model()

        # Build query for records with PnL linked
        conditions = [Model.is_profitable.isnot(None)]

        if prompt_version:
            conditions.append(Model.prompt_version == prompt_version)

        if start_date:
            conditions.append(Model.created_at >= start_date)

        stmt = select(
            func.count(Model.id),
            func.sum(func.cast(Model.is_profitable, type_=None)),
        ).where(*conditions)

        result = await self._session.execute(stmt)
        total, profitable = result.one()

        total = total or 0
        profitable = int(profitable or 0)

        accuracy = profitable / total if total > 0 else 0.0

        return {
            "accuracy": accuracy,
            "total": total,
            "correct": profitable,
        }

    def _to_domain(self, db_record: Any) -> DecisionRecord:
        """
        Convert DB record to domain object.

        Args:
            db_record: SQLAlchemy model instance

        Returns:
            DecisionRecord domain object
        """
        # Import DecisionConfidence
        from src.domain.value_objects.ai_decision_result import DecisionConfidence

        # Convert decision type (DB stores uppercase, enum uses lowercase)
        decision_type = DecisionType(db_record.decision.lower())

        # Create AIDecisionResult using factory method for proper construction
        confidence_value = int(db_record.confidence) if db_record.confidence else 0
        reason = db_record.reason or ""

        if decision_type == DecisionType.ALLOW:
            ai_decision = AIDecisionResult.allow(db_record.symbol, confidence_value, reason)
        elif decision_type == DecisionType.BLOCK:
            ai_decision = AIDecisionResult.block(db_record.symbol, confidence_value, reason)
        else:
            ai_decision = AIDecisionResult.hold(db_record.symbol, reason, confidence_value)

        # Create PromptVersion (DB may store uppercase, enum uses lowercase)
        prompt_type = PromptType(db_record.prompt_type.lower())
        prompt_version = PromptVersion(
            version=db_record.prompt_version,
            prompt_type=prompt_type,
            template_hash="from_db",  # Reconstructed from DB, hash not available
        )

        # Create PnL label if available
        pnl_label = None
        if db_record.pnl_percent is not None:
            pnl_label = PnLLabel(
                pnl_percent=db_record.pnl_percent,
                is_profitable=db_record.is_profitable,
                exit_reason=db_record.exit_reason,
            )

        return DecisionRecord(
            id=str(db_record.id),
            decision=ai_decision,
            prompt_version=prompt_version,
            params=db_record.params or {},
            pnl_label=pnl_label,
        )
