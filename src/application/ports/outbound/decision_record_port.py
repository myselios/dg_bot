"""
DecisionRecordPort - Interface for recording AI decisions.

This port defines the contract for recording and tracking AI decisions.
Adapters implementing this interface handle persistence of decisions
and their outcomes for analysis and improvement.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.domain.value_objects.ai_decision_result import AIDecisionResult
from src.domain.value_objects.prompt_version import PromptVersion


@dataclass
class PnLLabel:
    """
    PnL (Profit and Loss) label for a decision.

    Used to track the outcome of AI decisions for performance analysis.

    Attributes:
        pnl_percent: Profit/loss percentage
        is_profitable: Whether the decision resulted in profit
        exit_reason: Reason for exit (take_profit, stop_loss, manual, etc.)
        exit_price: Price at exit
        holding_time_hours: How long position was held
    """

    pnl_percent: Decimal
    is_profitable: bool
    exit_reason: str
    exit_price: Optional[Decimal] = None
    holding_time_hours: Optional[float] = None


@dataclass
class DecisionRecord:
    """
    Complete record of an AI decision.

    Attributes:
        id: Unique record ID
        decision: The AI decision
        prompt_version: Version of prompt used
        params: AI parameters (model, temperature, etc.)
        pnl_label: Outcome label (if known)
        created_at: When decision was made
    """

    id: str
    decision: AIDecisionResult
    prompt_version: PromptVersion
    params: Dict[str, Any]
    pnl_label: Optional[PnLLabel] = None
    created_at: datetime = field(default_factory=datetime.now)


class DecisionRecordPort(ABC):
    """
    Port interface for decision recording.

    This interface defines operations for recording AI decisions,
    linking outcomes, and querying historical data for analysis.
    """

    @abstractmethod
    async def record(
        self,
        decision: AIDecisionResult,
        prompt_version: PromptVersion,
        params: Dict[str, Any],
    ) -> str:
        """
        Record an AI decision.

        Args:
            decision: The AI decision to record
            prompt_version: Version of prompt used
            params: AI parameters (model, temperature, etc.)

        Returns:
            Unique record ID

        Raises:
            PersistenceError: If recording fails
        """
        pass

    @abstractmethod
    async def link_pnl(
        self,
        record_id: str,
        pnl_label: PnLLabel,
    ) -> bool:
        """
        Link PnL outcome to a decision record.

        Args:
            record_id: ID of decision record
            pnl_label: Outcome label

        Returns:
            True if successfully linked

        Raises:
            RecordNotFoundError: If record_id not found
        """
        pass

    @abstractmethod
    async def get_record(self, record_id: str) -> Optional[DecisionRecord]:
        """
        Get a decision record by ID.

        Args:
            record_id: ID of decision record

        Returns:
            DecisionRecord or None if not found
        """
        pass

    @abstractmethod
    async def find_by_ticker(
        self,
        ticker: str,
        limit: int = 10,
    ) -> List[DecisionRecord]:
        """
        Find decision records by ticker.

        Args:
            ticker: Trading pair to search
            limit: Maximum number of records

        Returns:
            List of matching records
        """
        pass

    @abstractmethod
    async def get_accuracy_stats(
        self,
        prompt_version: Optional[str] = None,
        start_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get accuracy statistics for decisions.

        Args:
            prompt_version: Filter by specific prompt version
            start_date: Filter by start date

        Returns:
            Dictionary with accuracy metrics
            Example: {"accuracy": 0.65, "total": 100, "correct": 65}
        """
        pass
