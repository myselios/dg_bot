"""
PostgresPersistenceAdapter - PostgreSQL implementation of PersistencePort.

This adapter implements data persistence using PostgreSQL database.
It handles the mapping between Domain entities and DB models.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any, Callable
from uuid import UUID
import logging

from sqlalchemy import select, and_, desc, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.ports.outbound.persistence_port import PersistencePort
from src.domain.entities.trade import Trade, Order, Position, OrderSide, OrderType, OrderStatus, TradeStatus
from src.domain.value_objects.money import Money, Currency
from src.application.dto.analysis import TradingDecision, DecisionType

# DB Models
from backend.app.models.trade import Trade as TradeModel
from backend.app.models.order import Order as OrderModel
from backend.app.models.ai_decision import AIDecision as AIDecisionModel
from backend.app.models.portfolio import PortfolioSnapshot as PortfolioModel

logger = logging.getLogger(__name__)


def _to_naive_utc(dt: datetime) -> datetime:
    """Convert timezone-aware datetime to naive UTC datetime."""
    if dt is None:
        return datetime.utcnow()
    if dt.tzinfo is not None:
        # Convert to UTC and remove timezone info
        utc_dt = dt.astimezone(timezone.utc)
        return utc_dt.replace(tzinfo=None)
    return dt


class PostgresPersistenceAdapter(PersistencePort):
    """
    PostgreSQL persistence adapter implementing PersistencePort.

    Handles CRUD operations for trades, orders, positions, decisions,
    and portfolio snapshots using SQLAlchemy async sessions.
    """

    def __init__(self, session_factory: Callable[[], AsyncSession]):
        """
        Initialize with SQLAlchemy async session factory.

        Args:
            session_factory: Callable that returns an AsyncSession
        """
        self._session_factory = session_factory
        # In-memory position cache (positions are volatile, not stored in DB separately)
        self._positions: Dict[str, Position] = {}

    async def _get_session(self) -> AsyncSession:
        """Get a new async session."""
        return self._session_factory()

    # --- Trade Operations ---

    async def save_trade(self, trade: Trade) -> Trade:
        """Save a trade record."""
        async with self._session_factory() as session:
            try:
                # Map Domain Entity to DB Model
                executed_dt = trade.executed_at or datetime.utcnow()
                db_trade = TradeModel(
                    trade_id=str(trade.id),
                    symbol=trade.ticker,
                    side=trade.side.value,
                    price=trade.price.amount,
                    amount=trade.volume,
                    total=trade.price.amount * trade.volume,
                    fee=trade.fee.amount if trade.fee else Decimal("0"),
                    status=trade.status.value if trade.status else "completed",
                    created_at=_to_naive_utc(executed_dt),
                )

                session.add(db_trade)
                await session.commit()
                await session.refresh(db_trade)

                logger.info(f"Trade saved: {trade.id}")
                return trade

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to save trade: {e}")
                raise

    async def get_trade(self, trade_id: UUID) -> Optional[Trade]:
        """Get a trade by ID."""
        async with self._session_factory() as session:
            try:
                result = await session.execute(
                    select(TradeModel).where(TradeModel.trade_id == str(trade_id))
                )
                db_trade = result.scalar_one_or_none()

                if db_trade is None:
                    return None

                return self._map_db_trade_to_domain(db_trade)

            except Exception as e:
                logger.error(f"Failed to get trade: {e}")
                return None

    async def get_trades_by_ticker(
        self,
        ticker: str,
        limit: int = 100,
    ) -> List[Trade]:
        """Get trades for a specific ticker."""
        async with self._session_factory() as session:
            try:
                result = await session.execute(
                    select(TradeModel)
                    .where(TradeModel.symbol == ticker)
                    .order_by(desc(TradeModel.created_at))
                    .limit(limit)
                )
                db_trades = result.scalars().all()

                return [self._map_db_trade_to_domain(t) for t in db_trades]

            except Exception as e:
                logger.error(f"Failed to get trades by ticker: {e}")
                return []

    async def get_trades_in_range(
        self,
        start_date: datetime,
        end_date: datetime,
        ticker: Optional[str] = None,
    ) -> List[Trade]:
        """Get trades within a date range."""
        async with self._session_factory() as session:
            try:
                query = select(TradeModel).where(
                    and_(
                        TradeModel.created_at >= start_date,
                        TradeModel.created_at <= end_date
                    )
                )

                if ticker:
                    query = query.where(TradeModel.symbol == ticker)

                query = query.order_by(desc(TradeModel.created_at))

                result = await session.execute(query)
                db_trades = result.scalars().all()

                return [self._map_db_trade_to_domain(t) for t in db_trades]

            except Exception as e:
                logger.error(f"Failed to get trades in range: {e}")
                return []

    def _map_db_trade_to_domain(self, db_trade: TradeModel) -> Trade:
        """Map DB Trade model to Domain Trade entity."""
        return Trade(
            id=UUID(db_trade.trade_id),
            ticker=db_trade.symbol,
            side=OrderSide(db_trade.side),
            price=Money(db_trade.price, Currency.KRW),
            volume=db_trade.amount,
            fee=Money(db_trade.fee or Decimal("0"), Currency.KRW),
            status=TradeStatus(db_trade.status) if db_trade.status else TradeStatus.COMPLETED,
            executed_at=db_trade.created_at,
        )

    # --- Order Operations ---

    async def save_order(self, order: Order) -> Order:
        """Save an order record."""
        async with self._session_factory() as session:
            try:
                created_dt = order.created_at or datetime.utcnow()
                db_order = OrderModel(
                    order_id=str(order.id),
                    symbol=order.ticker,
                    side=order.side.value,
                    order_type=order.order_type.value if order.order_type else "market",
                    price=order.price.amount if order.price else None,
                    amount=order.volume,
                    filled_amount=Decimal("0"),
                    status=order.status.value if order.status else "pending",
                    created_at=_to_naive_utc(created_dt),
                )

                session.add(db_order)
                await session.commit()
                await session.refresh(db_order)

                logger.info(f"Order saved: {order.id}")
                return order

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to save order: {e}")
                raise

    async def get_order(self, order_id: UUID) -> Optional[Order]:
        """Get an order by ID."""
        async with self._session_factory() as session:
            try:
                result = await session.execute(
                    select(OrderModel).where(OrderModel.order_id == str(order_id))
                )
                db_order = result.scalar_one_or_none()

                if db_order is None:
                    return None

                return self._map_db_order_to_domain(db_order)

            except Exception as e:
                logger.error(f"Failed to get order: {e}")
                return None

    async def get_open_orders(self, ticker: Optional[str] = None) -> List[Order]:
        """Get all open orders."""
        async with self._session_factory() as session:
            try:
                query = select(OrderModel).where(
                    OrderModel.status.in_(["pending", "open", "partially_filled"])
                )

                if ticker:
                    query = query.where(OrderModel.symbol == ticker)

                result = await session.execute(query)
                db_orders = result.scalars().all()

                return [self._map_db_order_to_domain(o) for o in db_orders]

            except Exception as e:
                logger.error(f"Failed to get open orders: {e}")
                return []

    async def update_order_status(
        self,
        order_id: UUID,
        status: str,
        **kwargs,
    ) -> Optional[Order]:
        """Update order status."""
        async with self._session_factory() as session:
            try:
                result = await session.execute(
                    select(OrderModel).where(OrderModel.order_id == str(order_id))
                )
                db_order = result.scalar_one_or_none()

                if db_order is None:
                    return None

                db_order.status = status
                if "filled_amount" in kwargs:
                    db_order.filled_amount = kwargs["filled_amount"]
                if "error_message" in kwargs:
                    db_order.error_message = kwargs["error_message"]

                await session.commit()
                await session.refresh(db_order)

                return self._map_db_order_to_domain(db_order)

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to update order: {e}")
                return None

    def _map_db_order_to_domain(self, db_order: OrderModel) -> Order:
        """Map DB Order model to Domain Order entity."""
        # Map status string to OrderStatus enum
        status_map = {
            "pending": OrderStatus.PENDING,
            "open": OrderStatus.PENDING,
            "filled": OrderStatus.FILLED,
            "partially_filled": OrderStatus.PARTIALLY_FILLED,
            "cancelled": OrderStatus.CANCELLED,
            "failed": OrderStatus.FAILED,
        }
        status = status_map.get(db_order.status.lower(), OrderStatus.PENDING)

        return Order(
            id=UUID(db_order.order_id),
            ticker=db_order.symbol,
            side=OrderSide(db_order.side),
            order_type=OrderType(db_order.order_type) if db_order.order_type else OrderType.MARKET,
            price=Money(db_order.price, Currency.KRW) if db_order.price else None,
            volume=db_order.amount,
            status=status,
            created_at=db_order.created_at,
            exchange_order_id=db_order.order_id,
        )

    # --- Position Operations ---
    # Note: Positions are stored in memory for now (similar to InMemoryAdapter)
    # A separate positions table could be added for persistence

    async def save_position(self, position: Position) -> Position:
        """Save or update a position."""
        self._positions[position.ticker] = position
        logger.info(f"Position saved: {position.ticker}")
        return position

    async def get_position(self, ticker: str) -> Optional[Position]:
        """Get current position for a ticker."""
        return self._positions.get(ticker)

    async def get_all_positions(self) -> List[Position]:
        """Get all open positions."""
        return list(self._positions.values())

    async def close_position(self, ticker: str) -> bool:
        """Close a position."""
        if ticker in self._positions:
            del self._positions[ticker]
            logger.info(f"Position closed: {ticker}")
            return True
        return False

    # --- AI Decision Operations ---

    async def save_decision(
        self,
        ticker: str,
        decision: TradingDecision,
    ) -> Dict[str, Any]:
        """Save an AI trading decision."""
        async with self._session_factory() as session:
            try:
                db_decision = AIDecisionModel(
                    symbol=ticker,
                    decision=decision.decision.value,
                    confidence=float(decision.confidence) * 100 if decision.confidence else None,
                    reason=decision.reasoning,
                    market_data={
                        "risk_assessment": decision.risk_assessment,
                        "key_factors": decision.key_factors,
                    },
                    created_at=datetime.utcnow(),
                )

                session.add(db_decision)
                await session.commit()
                await session.refresh(db_decision)

                result = {
                    "id": db_decision.id,
                    "ticker": ticker,
                    "decision": decision.decision.value,
                    "confidence": float(decision.confidence) if decision.confidence else None,
                    "reasoning": decision.reasoning,
                    "timestamp": db_decision.created_at,
                }

                logger.info(f"Decision saved: {ticker} -> {decision.decision.value}")
                return result

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to save decision: {e}")
                raise

    async def get_recent_decisions(
        self,
        ticker: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get recent AI decisions for a ticker."""
        async with self._session_factory() as session:
            try:
                result = await session.execute(
                    select(AIDecisionModel)
                    .where(AIDecisionModel.symbol == ticker)
                    .order_by(desc(AIDecisionModel.created_at))
                    .limit(limit)
                )
                db_decisions = result.scalars().all()

                return [
                    {
                        "id": d.id,
                        "ticker": d.symbol,
                        "decision": d.decision,
                        "confidence": float(d.confidence) / 100 if d.confidence else None,
                        "reasoning": d.reason,
                        "risk_assessment": d.market_data.get("risk_assessment") if d.market_data else None,
                        "key_factors": d.market_data.get("key_factors") if d.market_data else None,
                        "timestamp": d.created_at,
                    }
                    for d in db_decisions
                ]

            except Exception as e:
                logger.error(f"Failed to get recent decisions: {e}")
                return []

    # --- Portfolio Operations ---

    async def save_portfolio_snapshot(
        self,
        total_value: Decimal,
        positions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Save a portfolio snapshot."""
        async with self._session_factory() as session:
            try:
                db_snapshot = PortfolioModel(
                    total_value_krw=total_value,
                    positions=positions,
                    created_at=datetime.utcnow(),
                )

                session.add(db_snapshot)
                await session.commit()
                await session.refresh(db_snapshot)

                result = {
                    "id": db_snapshot.id,
                    "total_value": float(db_snapshot.total_value_krw),
                    "positions": db_snapshot.positions,
                    "timestamp": db_snapshot.created_at,
                }

                logger.info(f"Portfolio snapshot saved: {total_value:,.0f} KRW")
                return result

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to save portfolio snapshot: {e}")
                raise

    async def get_portfolio_history(
        self,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get portfolio value history."""
        async with self._session_factory() as session:
            try:
                cutoff = datetime.utcnow() - timedelta(days=days)

                result = await session.execute(
                    select(PortfolioModel)
                    .where(PortfolioModel.created_at >= cutoff)
                    .order_by(desc(PortfolioModel.created_at))
                )
                db_snapshots = result.scalars().all()

                return [
                    {
                        "id": s.id,
                        "total_value": float(s.total_value_krw),
                        "positions": s.positions,
                        "timestamp": s.created_at,
                    }
                    for s in db_snapshots
                ]

            except Exception as e:
                logger.error(f"Failed to get portfolio history: {e}")
                return []

    # --- Statistics ---

    async def get_trade_statistics(
        self,
        ticker: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get trading statistics."""
        async with self._session_factory() as session:
            try:
                cutoff = datetime.utcnow() - timedelta(days=days)

                query = select(TradeModel).where(TradeModel.created_at >= cutoff)
                if ticker:
                    query = query.where(TradeModel.symbol == ticker)

                result = await session.execute(query)
                db_trades = result.scalars().all()

                if not db_trades:
                    return {
                        "total_trades": 0,
                        "win_rate": Decimal("0"),
                        "total_pnl": Decimal("0"),
                        "avg_pnl": Decimal("0"),
                    }

                total_trades = len(db_trades)
                # Note: For proper P&L calculation, we need to track realized P&L per trade
                # This is a simplified version

                return {
                    "total_trades": total_trades,
                    "win_rate": Decimal("0"),  # Needs proper P&L tracking
                    "total_pnl": Decimal("0"),
                    "avg_pnl": Decimal("0"),
                }

            except Exception as e:
                logger.error(f"Failed to get trade statistics: {e}")
                return {
                    "total_trades": 0,
                    "win_rate": Decimal("0"),
                    "total_pnl": Decimal("0"),
                    "avg_pnl": Decimal("0"),
                }

    async def get_daily_pnl(
        self,
        date: Optional[datetime] = None,
    ) -> Decimal:
        """Get daily profit/loss."""
        # For proper P&L calculation, we need to track realized P&L
        # This is a placeholder returning 0
        return Decimal("0")

    async def get_weekly_pnl(self) -> Decimal:
        """Get weekly profit/loss."""
        # For proper P&L calculation, we need to track realized P&L
        # This is a placeholder returning 0
        return Decimal("0")

    # --- System Operations ---

    async def health_check(self) -> bool:
        """Check if persistence layer is healthy."""
        try:
            async with self._session_factory() as session:
                await session.execute(select(1))
                return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def cleanup_old_data(self, days: int = 90) -> int:
        """Clean up old data."""
        async with self._session_factory() as session:
            try:
                cutoff = datetime.utcnow() - timedelta(days=days)
                deleted = 0

                # Delete old trades
                result = await session.execute(
                    delete(TradeModel).where(TradeModel.created_at < cutoff)
                )
                deleted += result.rowcount

                # Delete old orders
                result = await session.execute(
                    delete(OrderModel).where(OrderModel.created_at < cutoff)
                )
                deleted += result.rowcount

                # Delete old decisions
                result = await session.execute(
                    delete(AIDecisionModel).where(AIDecisionModel.created_at < cutoff)
                )
                deleted += result.rowcount

                # Delete old portfolio snapshots
                result = await session.execute(
                    delete(PortfolioModel).where(PortfolioModel.created_at < cutoff)
                )
                deleted += result.rowcount

                await session.commit()

                logger.info(f"Cleaned up {deleted} old records")
                return deleted

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to cleanup old data: {e}")
                return 0
