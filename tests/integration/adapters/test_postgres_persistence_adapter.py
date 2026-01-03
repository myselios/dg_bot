"""
PostgresPersistenceAdapter Integration Tests (TDD - Red Phase).

These tests verify that the PostgresPersistenceAdapter correctly
implements the PersistencePort interface with PostgreSQL.

Requires a running PostgreSQL database for testing.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from src.application.ports.outbound.persistence_port import PersistencePort
from src.domain.entities.trade import Trade, Order, Position, OrderSide, OrderType, OrderStatus, TradeStatus
from src.domain.value_objects.money import Money, Currency
from src.application.dto.analysis import TradingDecision, DecisionType


# Skip tests if no database connection
pytestmark = pytest.mark.integration


class TestPostgresPersistenceAdapterTrade:
    """Test Trade CRUD operations."""

    @pytest.fixture
    def adapter(self, db_session):
        """Create adapter with test database session."""
        from src.infrastructure.adapters.persistence.postgres_persistence_adapter import (
            PostgresPersistenceAdapter
        )
        return PostgresPersistenceAdapter(session_factory=db_session)

    @pytest.fixture
    def sample_trade(self):
        """Create a sample trade for testing with unique ID."""
        return Trade(
            id=uuid4(),  # New unique ID for each test
            ticker="KRW-BTC",
            side=OrderSide.BUY,
            price=Money(Decimal("50000000"), Currency.KRW),
            volume=Decimal("0.001"),
            fee=Money(Decimal("50"), Currency.KRW),
            status=TradeStatus.COMPLETED,
            executed_at=datetime.utcnow(),
        )

    @pytest.mark.asyncio
    async def test_save_trade_and_get_trade(self, adapter, sample_trade):
        """
        Save a trade and retrieve it by ID.

        Given: A trade to save
        When: save_trade is called followed by get_trade
        Then: The retrieved trade matches the saved one
        """
        # When
        saved = await adapter.save_trade(sample_trade)
        retrieved = await adapter.get_trade(sample_trade.id)

        # Then
        assert retrieved is not None
        assert retrieved.id == sample_trade.id
        assert retrieved.ticker == sample_trade.ticker
        assert retrieved.side == sample_trade.side

    @pytest.mark.asyncio
    async def test_get_trades_by_ticker(self, adapter, sample_trade):
        """
        Get trades filtered by ticker.

        Given: Multiple trades for different tickers
        When: get_trades_by_ticker is called
        Then: Only trades for the specified ticker are returned
        """
        # Given
        await adapter.save_trade(sample_trade)

        other_trade = Trade(
            id=uuid4(),
            ticker="KRW-ETH",
            side=OrderSide.BUY,
            price=Money(Decimal("3000000"), Currency.KRW),
            volume=Decimal("0.1"),
            fee=Money(Decimal("30"), Currency.KRW),
            status=TradeStatus.COMPLETED,
            executed_at=datetime.utcnow(),
        )
        await adapter.save_trade(other_trade)

        # When
        btc_trades = await adapter.get_trades_by_ticker("KRW-BTC", limit=10)

        # Then
        assert len(btc_trades) >= 1
        assert all(t.ticker == "KRW-BTC" for t in btc_trades)

    @pytest.mark.asyncio
    async def test_get_trades_in_range(self, adapter, sample_trade):
        """
        Get trades within a date range.

        Given: Trades at different times
        When: get_trades_in_range is called
        Then: Only trades within the range are returned
        """
        # Given
        await adapter.save_trade(sample_trade)

        # When
        start = datetime.utcnow() - timedelta(hours=1)
        end = datetime.utcnow() + timedelta(hours=1)
        trades = await adapter.get_trades_in_range(start, end)

        # Then
        assert len(trades) >= 1


class TestPostgresPersistenceAdapterOrder:
    """Test Order CRUD operations."""

    @pytest.fixture
    def adapter(self, db_session):
        """Create adapter with test database session."""
        from src.infrastructure.adapters.persistence.postgres_persistence_adapter import (
            PostgresPersistenceAdapter
        )
        return PostgresPersistenceAdapter(session_factory=db_session)

    @pytest.fixture
    def sample_order(self):
        """Create a sample order for testing with unique ID."""
        return Order(
            id=uuid4(),  # New unique ID for each test
            ticker="KRW-BTC",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            price=Money(Decimal("50000000"), Currency.KRW),
            volume=Decimal("0.001"),
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

    @pytest.mark.asyncio
    async def test_save_order_and_get_order(self, adapter, sample_order):
        """
        Save an order and retrieve it by ID.
        """
        # When
        saved = await adapter.save_order(sample_order)
        retrieved = await adapter.get_order(sample_order.id)

        # Then
        assert retrieved is not None
        assert retrieved.id == sample_order.id
        assert retrieved.ticker == sample_order.ticker
        assert retrieved.status == OrderStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_open_orders(self, adapter, sample_order):
        """
        Get all open (pending) orders.
        """
        # Given
        await adapter.save_order(sample_order)

        # When
        open_orders = await adapter.get_open_orders()

        # Then
        assert len(open_orders) >= 1
        assert all(o.status in {OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED} for o in open_orders)

    @pytest.mark.asyncio
    async def test_update_order_status(self, adapter, sample_order):
        """
        Update order status.
        """
        # Given
        await adapter.save_order(sample_order)

        # When
        updated = await adapter.update_order_status(sample_order.id, "filled")

        # Then
        assert updated is not None
        assert updated.status == OrderStatus.FILLED


class TestPostgresPersistenceAdapterPosition:
    """Test Position CRUD operations."""

    @pytest.fixture
    def adapter(self, db_session):
        """Create adapter with test database session."""
        from src.infrastructure.adapters.persistence.postgres_persistence_adapter import (
            PostgresPersistenceAdapter
        )
        return PostgresPersistenceAdapter(session_factory=db_session)

    @pytest.fixture
    def sample_position(self):
        """Create a sample position for testing."""
        return Position.create(
            ticker="KRW-BTC",
            symbol="BTC",
            volume=Decimal("0.001"),
            avg_entry_price=Money(Decimal("50000000"), Currency.KRW),
            entry_time=datetime.utcnow(),
        )

    @pytest.mark.asyncio
    async def test_save_position_and_get_position(self, adapter, sample_position):
        """
        Save a position and retrieve it by ticker.
        """
        # When
        saved = await adapter.save_position(sample_position)
        retrieved = await adapter.get_position("KRW-BTC")

        # Then
        assert retrieved is not None
        assert retrieved.ticker == "KRW-BTC"
        assert retrieved.volume == sample_position.volume

    @pytest.mark.asyncio
    async def test_get_all_positions(self, adapter, sample_position):
        """
        Get all open positions.
        """
        # Given
        await adapter.save_position(sample_position)

        # When
        positions = await adapter.get_all_positions()

        # Then
        assert len(positions) >= 1

    @pytest.mark.asyncio
    async def test_close_position(self, adapter, sample_position):
        """
        Close a position.
        """
        # Given
        await adapter.save_position(sample_position)

        # When
        result = await adapter.close_position("KRW-BTC")

        # Then
        assert result is True
        retrieved = await adapter.get_position("KRW-BTC")
        assert retrieved is None


class TestPostgresPersistenceAdapterDecision:
    """Test AI Decision CRUD operations."""

    @pytest.fixture
    def adapter(self, db_session):
        """Create adapter with test database session."""
        from src.infrastructure.adapters.persistence.postgres_persistence_adapter import (
            PostgresPersistenceAdapter
        )
        return PostgresPersistenceAdapter(session_factory=db_session)

    @pytest.fixture
    def sample_decision(self):
        """Create a sample trading decision."""
        return TradingDecision(
            decision=DecisionType.BUY,
            confidence=Decimal("0.85"),
            reasoning="Strong bullish signal",
            risk_assessment="Low risk",
            key_factors=["RSI oversold", "MACD crossover"],
        )

    @pytest.mark.asyncio
    async def test_save_decision_and_get_recent_decisions(self, adapter, sample_decision):
        """
        Save an AI decision and retrieve recent decisions.
        """
        # When
        saved = await adapter.save_decision("KRW-BTC", sample_decision)

        # Then
        assert saved is not None
        assert "id" in saved

        # Get recent decisions
        recent = await adapter.get_recent_decisions("KRW-BTC", limit=10)
        assert len(recent) >= 1
        assert recent[0]["decision"] == "buy"


class TestPostgresPersistenceAdapterPortfolio:
    """Test Portfolio operations."""

    @pytest.fixture
    def adapter(self, db_session):
        """Create adapter with test database session."""
        from src.infrastructure.adapters.persistence.postgres_persistence_adapter import (
            PostgresPersistenceAdapter
        )
        return PostgresPersistenceAdapter(session_factory=db_session)

    @pytest.mark.asyncio
    async def test_save_portfolio_snapshot(self, adapter):
        """
        Save a portfolio snapshot.
        """
        # When
        snapshot = await adapter.save_portfolio_snapshot(
            total_value=Decimal("10000000"),
            positions={"KRW-BTC": {"amount": 0.001, "value": 50000}}
        )

        # Then
        assert snapshot is not None
        assert "id" in snapshot
        assert snapshot["total_value"] == 10000000

    @pytest.mark.asyncio
    async def test_get_portfolio_history(self, adapter):
        """
        Get portfolio history.
        """
        # Given
        await adapter.save_portfolio_snapshot(
            total_value=Decimal("10000000"),
            positions={"KRW-BTC": {"amount": 0.001, "value": 50000}}
        )

        # When
        history = await adapter.get_portfolio_history(days=30)

        # Then
        assert len(history) >= 1


class TestPostgresPersistenceAdapterStatistics:
    """Test Statistics operations."""

    @pytest.fixture
    def adapter(self, db_session):
        """Create adapter with test database session."""
        from src.infrastructure.adapters.persistence.postgres_persistence_adapter import (
            PostgresPersistenceAdapter
        )
        return PostgresPersistenceAdapter(session_factory=db_session)

    @pytest.mark.asyncio
    async def test_get_trade_statistics(self, adapter):
        """
        Get trade statistics.
        """
        # When
        stats = await adapter.get_trade_statistics(days=30)

        # Then
        assert "total_trades" in stats
        assert "win_rate" in stats

    @pytest.mark.asyncio
    async def test_get_daily_pnl(self, adapter):
        """
        Get daily P&L.
        """
        # When
        pnl = await adapter.get_daily_pnl()

        # Then
        assert isinstance(pnl, Decimal)

    @pytest.mark.asyncio
    async def test_get_weekly_pnl(self, adapter):
        """
        Get weekly P&L.
        """
        # When
        pnl = await adapter.get_weekly_pnl()

        # Then
        assert isinstance(pnl, Decimal)


class TestPostgresPersistenceAdapterSystem:
    """Test System operations."""

    @pytest.fixture
    def adapter(self, db_session):
        """Create adapter with test database session."""
        from src.infrastructure.adapters.persistence.postgres_persistence_adapter import (
            PostgresPersistenceAdapter
        )
        return PostgresPersistenceAdapter(session_factory=db_session)

    @pytest.mark.asyncio
    async def test_health_check(self, adapter):
        """
        Health check should return True when database is accessible.
        """
        # When
        healthy = await adapter.health_check()

        # Then
        assert healthy is True

    @pytest.mark.asyncio
    async def test_cleanup_old_data(self, adapter):
        """
        Cleanup old data.
        """
        # When
        deleted = await adapter.cleanup_old_data(days=90)

        # Then
        assert isinstance(deleted, int)
        assert deleted >= 0
