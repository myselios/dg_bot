"""
InMemoryPersistenceAdapter - In-memory implementation of PersistencePort.

This adapter provides an in-memory storage for testing purposes.
All data is lost when the adapter is destroyed.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID
import copy

from src.application.ports.outbound.persistence_port import PersistencePort
from src.domain.entities.trade import Trade, Order, Position, OrderStatus, TradeStatus
from src.application.dto.analysis import TradingDecision


class InMemoryPersistenceAdapter(PersistencePort):
    """
    In-memory persistence adapter implementing PersistencePort.

    Useful for testing without database dependencies.
    """

    def __init__(self):
        """Initialize empty storage."""
        self._trades: Dict[UUID, Trade] = {}
        self._orders: Dict[UUID, Order] = {}
        self._positions: Dict[str, Position] = {}  # keyed by ticker
        self._decisions: List[Dict[str, Any]] = []
        self._portfolio_snapshots: List[Dict[str, Any]] = []
        self._is_healthy = True

    def clear(self):
        """Clear all stored data. Useful for test cleanup."""
        self._trades.clear()
        self._orders.clear()
        self._positions.clear()
        self._decisions.clear()
        self._portfolio_snapshots.clear()

    # --- Trade Operations ---

    async def save_trade(self, trade: Trade) -> Trade:
        """Save a trade record."""
        self._trades[trade.id] = copy.deepcopy(trade)
        return trade

    async def get_trade(self, trade_id: UUID) -> Optional[Trade]:
        """Get a trade by ID."""
        trade = self._trades.get(trade_id)
        return copy.deepcopy(trade) if trade else None

    async def get_trades_by_ticker(
        self,
        ticker: str,
        limit: int = 100,
    ) -> List[Trade]:
        """Get trades for a specific ticker."""
        trades = [
            copy.deepcopy(t)
            for t in self._trades.values()
            if t.ticker == ticker
        ]
        # Sort by executed_at descending (most recent first)
        trades.sort(key=lambda t: t.executed_at, reverse=True)
        return trades[:limit]

    async def get_trades_in_range(
        self,
        start_date: datetime,
        end_date: datetime,
        ticker: Optional[str] = None,
    ) -> List[Trade]:
        """Get trades within a date range."""
        trades = []
        for trade in self._trades.values():
            if start_date <= trade.executed_at <= end_date:
                if ticker is None or trade.ticker == ticker:
                    trades.append(copy.deepcopy(trade))
        trades.sort(key=lambda t: t.executed_at, reverse=True)
        return trades

    # --- Order Operations ---

    async def save_order(self, order: Order) -> Order:
        """Save an order record."""
        self._orders[order.id] = copy.deepcopy(order)
        return order

    async def get_order(self, order_id: UUID) -> Optional[Order]:
        """Get an order by ID."""
        order = self._orders.get(order_id)
        return copy.deepcopy(order) if order else None

    async def get_open_orders(self, ticker: Optional[str] = None) -> List[Order]:
        """Get all open orders."""
        open_statuses = {OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED}
        orders = [
            copy.deepcopy(o)
            for o in self._orders.values()
            if o.status in open_statuses and (ticker is None or o.ticker == ticker)
        ]
        return orders

    async def update_order_status(
        self,
        order_id: UUID,
        status: str,
        **kwargs,
    ) -> Optional[Order]:
        """Update order status."""
        order = self._orders.get(order_id)
        if order is None:
            return None

        # Create updated order with new status
        try:
            new_status = OrderStatus(status.lower())
        except ValueError:
            new_status = order.status

        updated_order = Order(
            id=order.id,
            ticker=order.ticker,
            side=order.side,
            order_type=order.order_type,
            price=kwargs.get('price', order.price),
            volume=kwargs.get('volume', order.volume),
            status=new_status,
            created_at=order.created_at,
            exchange_order_id=kwargs.get('exchange_order_id', order.exchange_order_id),
        )

        self._orders[order_id] = updated_order
        return copy.deepcopy(updated_order)

    # --- Position Operations ---

    async def save_position(self, position: Position) -> Position:
        """Save or update a position."""
        self._positions[position.ticker] = copy.deepcopy(position)
        return position

    async def get_position(self, ticker: str) -> Optional[Position]:
        """Get current position for a ticker."""
        position = self._positions.get(ticker)
        return copy.deepcopy(position) if position else None

    async def get_all_positions(self) -> List[Position]:
        """Get all open positions."""
        return [copy.deepcopy(p) for p in self._positions.values()]

    async def close_position(self, ticker: str) -> bool:
        """Close a position."""
        if ticker in self._positions:
            del self._positions[ticker]
            return True
        return False

    # --- AI Decision Operations ---

    async def save_decision(
        self,
        ticker: str,
        decision: TradingDecision,
    ) -> Dict[str, Any]:
        """Save an AI trading decision."""
        record = {
            "id": len(self._decisions) + 1,
            "ticker": ticker,
            "decision": decision.decision.value,
            "confidence": float(decision.confidence),
            "reasoning": decision.reasoning,
            "risk_assessment": decision.risk_assessment,
            "key_factors": decision.key_factors,
            "timestamp": datetime.now(),
        }
        self._decisions.append(record)
        return record

    async def get_recent_decisions(
        self,
        ticker: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get recent AI decisions for a ticker."""
        filtered = [d for d in self._decisions if d["ticker"] == ticker]
        # Sort by timestamp descending
        filtered.sort(key=lambda d: d["timestamp"], reverse=True)
        return filtered[:limit]

    # --- Portfolio Operations ---

    async def save_portfolio_snapshot(
        self,
        total_value: Decimal,
        positions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Save a portfolio snapshot."""
        snapshot = {
            "id": len(self._portfolio_snapshots) + 1,
            "total_value": float(total_value),
            "positions": positions,
            "timestamp": datetime.now(),
        }
        self._portfolio_snapshots.append(snapshot)
        return snapshot

    async def get_portfolio_history(
        self,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get portfolio value history."""
        cutoff = datetime.now() - timedelta(days=days)
        filtered = [
            s for s in self._portfolio_snapshots
            if s["timestamp"] >= cutoff
        ]
        filtered.sort(key=lambda s: s["timestamp"], reverse=True)
        return filtered

    # --- Statistics ---

    async def get_trade_statistics(
        self,
        ticker: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get trading statistics."""
        cutoff = datetime.now() - timedelta(days=days)

        trades = [
            t for t in self._trades.values()
            if t.executed_at >= cutoff and (ticker is None or t.ticker == ticker)
        ]

        if not trades:
            return {
                "total_trades": 0,
                "win_rate": Decimal("0"),
                "total_pnl": Decimal("0"),
                "avg_pnl": Decimal("0"),
            }

        # Calculate statistics (using fee as a simple proxy for P&L calculation)
        # In a real implementation, realized P&L would be tracked per trade
        total_trades = len(trades)
        # For in-memory adapter, we don't track P&L, return placeholders
        win_rate = Decimal("0")
        total_pnl = Decimal("0")
        avg_pnl = Decimal("0")

        return {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "avg_pnl": avg_pnl,
        }

    async def get_daily_pnl(
        self,
        date: Optional[datetime] = None,
    ) -> Decimal:
        """Get daily profit/loss."""
        target_date = date or datetime.now()
        start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        trades = [
            t for t in self._trades.values()
            if start <= t.executed_at < end
        ]

        # In-memory adapter doesn't track realized P&L
        return Decimal("0")

    async def get_weekly_pnl(self) -> Decimal:
        """Get weekly profit/loss."""
        now = datetime.now()
        week_ago = now - timedelta(days=7)

        trades = [
            t for t in self._trades.values()
            if t.executed_at >= week_ago
        ]

        # In-memory adapter doesn't track realized P&L
        return Decimal("0")

    # --- System Operations ---

    async def health_check(self) -> bool:
        """Check if persistence layer is healthy."""
        return self._is_healthy

    def set_health(self, healthy: bool):
        """Set health status (for testing failure scenarios)."""
        self._is_healthy = healthy

    async def cleanup_old_data(self, days: int = 90) -> int:
        """Clean up old data."""
        cutoff = datetime.now() - timedelta(days=days)
        deleted = 0

        # Clean old trades
        old_trade_ids = [
            tid for tid, trade in self._trades.items()
            if trade.executed_at < cutoff
        ]
        for tid in old_trade_ids:
            del self._trades[tid]
            deleted += 1

        # Clean old orders
        old_order_ids = [
            oid for oid, order in self._orders.items()
            if order.created_at < cutoff
        ]
        for oid in old_order_ids:
            del self._orders[oid]
            deleted += 1

        # Clean old decisions
        old_decision_count = len(self._decisions)
        self._decisions = [
            d for d in self._decisions
            if d["timestamp"] >= cutoff
        ]
        deleted += old_decision_count - len(self._decisions)

        # Clean old snapshots
        old_snapshot_count = len(self._portfolio_snapshots)
        self._portfolio_snapshots = [
            s for s in self._portfolio_snapshots
            if s["timestamp"] >= cutoff
        ]
        deleted += old_snapshot_count - len(self._portfolio_snapshots)

        return deleted

    # --- Test Helpers ---

    @property
    def trade_count(self) -> int:
        """Get total number of trades stored."""
        return len(self._trades)

    @property
    def order_count(self) -> int:
        """Get total number of orders stored."""
        return len(self._orders)

    @property
    def position_count(self) -> int:
        """Get total number of positions stored."""
        return len(self._positions)

    @property
    def decision_count(self) -> int:
        """Get total number of decisions stored."""
        return len(self._decisions)
