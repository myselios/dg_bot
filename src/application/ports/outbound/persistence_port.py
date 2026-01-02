"""
PersistencePort - Interface for data persistence operations.

This port defines the contract for storing and retrieving trading data.
Adapters implementing this interface handle database operations.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from src.domain.entities.trade import Trade, Order, Position
from src.application.dto.analysis import TradingDecision


class PersistencePort(ABC):
    """
    Port interface for data persistence.

    This interface defines operations for storing and retrieving
    trading data including trades, orders, positions, and AI decisions.
    """

    # --- Trade Operations ---

    @abstractmethod
    async def save_trade(self, trade: Trade) -> Trade:
        """
        Save a trade record.

        Args:
            trade: Trade entity to save

        Returns:
            Saved trade with any generated fields

        Raises:
            PersistenceError: If save fails
        """
        pass

    @abstractmethod
    async def get_trade(self, trade_id: UUID) -> Optional[Trade]:
        """
        Get a trade by ID.

        Args:
            trade_id: Trade unique identifier

        Returns:
            Trade if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_trades_by_ticker(
        self,
        ticker: str,
        limit: int = 100,
    ) -> List[Trade]:
        """
        Get trades for a specific ticker.

        Args:
            ticker: Trading pair
            limit: Maximum number of trades to return

        Returns:
            List of trades (most recent first)
        """
        pass

    @abstractmethod
    async def get_trades_in_range(
        self,
        start_date: datetime,
        end_date: datetime,
        ticker: Optional[str] = None,
    ) -> List[Trade]:
        """
        Get trades within a date range.

        Args:
            start_date: Start of date range
            end_date: End of date range
            ticker: Optional ticker filter

        Returns:
            List of trades in the range
        """
        pass

    # --- Order Operations ---

    @abstractmethod
    async def save_order(self, order: Order) -> Order:
        """
        Save an order record.

        Args:
            order: Order entity to save

        Returns:
            Saved order
        """
        pass

    @abstractmethod
    async def get_order(self, order_id: UUID) -> Optional[Order]:
        """
        Get an order by ID.

        Args:
            order_id: Order unique identifier

        Returns:
            Order if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_open_orders(self, ticker: Optional[str] = None) -> List[Order]:
        """
        Get all open orders.

        Args:
            ticker: Optional ticker filter

        Returns:
            List of open orders
        """
        pass

    @abstractmethod
    async def update_order_status(
        self,
        order_id: UUID,
        status: str,
        **kwargs,
    ) -> Optional[Order]:
        """
        Update order status.

        Args:
            order_id: Order to update
            status: New status
            **kwargs: Additional fields to update

        Returns:
            Updated order if found
        """
        pass

    # --- Position Operations ---

    @abstractmethod
    async def save_position(self, position: Position) -> Position:
        """
        Save or update a position.

        Args:
            position: Position entity to save

        Returns:
            Saved position
        """
        pass

    @abstractmethod
    async def get_position(self, ticker: str) -> Optional[Position]:
        """
        Get current position for a ticker.

        Args:
            ticker: Trading pair

        Returns:
            Position if exists, None otherwise
        """
        pass

    @abstractmethod
    async def get_all_positions(self) -> List[Position]:
        """
        Get all open positions.

        Returns:
            List of open positions
        """
        pass

    @abstractmethod
    async def close_position(self, ticker: str) -> bool:
        """
        Close a position.

        Args:
            ticker: Trading pair

        Returns:
            True if position was closed
        """
        pass

    # --- AI Decision Operations ---

    @abstractmethod
    async def save_decision(
        self,
        ticker: str,
        decision: TradingDecision,
    ) -> Dict[str, Any]:
        """
        Save an AI trading decision.

        Args:
            ticker: Trading pair
            decision: TradingDecision to save

        Returns:
            Saved decision record
        """
        pass

    @abstractmethod
    async def get_recent_decisions(
        self,
        ticker: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get recent AI decisions for a ticker.

        Args:
            ticker: Trading pair
            limit: Maximum number of decisions

        Returns:
            List of decision records
        """
        pass

    # --- Portfolio Operations ---

    @abstractmethod
    async def save_portfolio_snapshot(
        self,
        total_value: Decimal,
        positions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Save a portfolio snapshot.

        Args:
            total_value: Total portfolio value
            positions: Position details

        Returns:
            Saved snapshot record
        """
        pass

    @abstractmethod
    async def get_portfolio_history(
        self,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Get portfolio value history.

        Args:
            days: Number of days of history

        Returns:
            List of portfolio snapshots
        """
        pass

    # --- Statistics ---

    @abstractmethod
    async def get_trade_statistics(
        self,
        ticker: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get trading statistics.

        Args:
            ticker: Optional ticker filter
            days: Number of days to analyze

        Returns:
            Statistics dict (total trades, win rate, PnL, etc.)
        """
        pass

    @abstractmethod
    async def get_daily_pnl(
        self,
        date: Optional[datetime] = None,
    ) -> Decimal:
        """
        Get daily profit/loss.

        Args:
            date: Date to check (default: today)

        Returns:
            Daily PnL as Decimal
        """
        pass

    @abstractmethod
    async def get_weekly_pnl(self) -> Decimal:
        """
        Get weekly profit/loss.

        Returns:
            Weekly PnL as Decimal
        """
        pass

    # --- System Operations ---

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if persistence layer is healthy.

        Returns:
            True if database is accessible
        """
        pass

    @abstractmethod
    async def cleanup_old_data(self, days: int = 90) -> int:
        """
        Clean up old data.

        Args:
            days: Keep data newer than this

        Returns:
            Number of records deleted
        """
        pass
