"""
Integration tests for infrastructure adapters.

These tests verify that adapters correctly implement their port interfaces.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from src.application.ports.outbound.persistence_port import PersistencePort
from src.application.ports.outbound.exchange_port import ExchangePort
from src.application.ports.outbound.ai_port import AIPort
from src.application.ports.outbound.market_data_port import MarketDataPort

from src.infrastructure.adapters.persistence.memory_adapter import InMemoryPersistenceAdapter

from src.domain.entities.trade import (
    Trade, Order, Position,
    OrderSide, OrderType, OrderStatus, TradeStatus,
)
from src.domain.value_objects.money import Money, Currency
from src.application.dto.analysis import TradingDecision, DecisionType


class TestInMemoryPersistenceAdapter:
    """Tests for InMemoryPersistenceAdapter."""

    @pytest.fixture
    def adapter(self):
        """Create fresh adapter for each test."""
        return InMemoryPersistenceAdapter()

    @pytest.fixture
    def sample_trade(self):
        """Create sample trade for testing."""
        return Trade(
            id=uuid4(),
            ticker="KRW-BTC",
            side=OrderSide.BUY,
            price=Money.krw(Decimal("50000000")),
            volume=Decimal("0.1"),
            fee=Money.krw(Decimal("25000")),
            status=TradeStatus.COMPLETED,
            executed_at=datetime.now(),
        )

    @pytest.fixture
    def sample_order(self):
        """Create sample order for testing."""
        return Order(
            id=uuid4(),
            ticker="KRW-BTC",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            price=Money.krw(Decimal("50000000")),
            volume=Decimal("0.1"),
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )

    @pytest.fixture
    def sample_position(self):
        """Create sample position for testing."""
        return Position.create(
            ticker="KRW-BTC",
            symbol="BTC",
            volume=Decimal("0.5"),
            avg_entry_price=Money.krw(Decimal("50000000")),
        )

    # --- Interface Compliance ---

    def test_implements_persistence_port(self, adapter):
        """Adapter implements PersistencePort interface."""
        assert isinstance(adapter, PersistencePort)

    # --- Trade Operations ---

    @pytest.mark.asyncio
    async def test_save_and_get_trade(self, adapter, sample_trade):
        """Can save and retrieve a trade."""
        # Save trade
        saved = await adapter.save_trade(sample_trade)
        assert saved.id == sample_trade.id

        # Retrieve trade
        retrieved = await adapter.get_trade(sample_trade.id)
        assert retrieved is not None
        assert retrieved.id == sample_trade.id
        assert retrieved.ticker == sample_trade.ticker
        assert retrieved.volume == sample_trade.volume

    @pytest.mark.asyncio
    async def test_get_nonexistent_trade(self, adapter):
        """Returns None for nonexistent trade."""
        result = await adapter.get_trade(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_trades_by_ticker(self, adapter):
        """Can filter trades by ticker."""
        # Create trades for different tickers
        btc_trade = Trade(
            id=uuid4(),
            ticker="KRW-BTC",
            side=OrderSide.BUY,
            price=Money.krw(Decimal("50000000")),
            volume=Decimal("0.1"),
            fee=Money.krw(Decimal("25000")),
            status=TradeStatus.COMPLETED,
            executed_at=datetime.now(),
        )
        eth_trade = Trade(
            id=uuid4(),
            ticker="KRW-ETH",
            side=OrderSide.BUY,
            price=Money.krw(Decimal("3000000")),
            volume=Decimal("1.0"),
            fee=Money.krw(Decimal("1500")),
            status=TradeStatus.COMPLETED,
            executed_at=datetime.now(),
        )

        await adapter.save_trade(btc_trade)
        await adapter.save_trade(eth_trade)

        # Filter by ticker
        btc_trades = await adapter.get_trades_by_ticker("KRW-BTC")
        assert len(btc_trades) == 1
        assert btc_trades[0].ticker == "KRW-BTC"

    @pytest.mark.asyncio
    async def test_get_trades_in_range(self, adapter):
        """Can filter trades by date range."""
        now = datetime.now()

        old_trade = Trade(
            id=uuid4(),
            ticker="KRW-BTC",
            side=OrderSide.BUY,
            price=Money.krw(Decimal("50000000")),
            volume=Decimal("0.1"),
            fee=Money.krw(Decimal("25000")),
            status=TradeStatus.COMPLETED,
            executed_at=now - timedelta(days=10),
        )
        recent_trade = Trade(
            id=uuid4(),
            ticker="KRW-BTC",
            side=OrderSide.SELL,
            price=Money.krw(Decimal("51000000")),
            volume=Decimal("0.1"),
            fee=Money.krw(Decimal("25500")),
            status=TradeStatus.COMPLETED,
            executed_at=now - timedelta(days=2),
        )

        await adapter.save_trade(old_trade)
        await adapter.save_trade(recent_trade)

        # Get trades from last 5 days
        trades = await adapter.get_trades_in_range(
            start_date=now - timedelta(days=5),
            end_date=now,
        )
        assert len(trades) == 1
        assert trades[0].id == recent_trade.id

    # --- Order Operations ---

    @pytest.mark.asyncio
    async def test_save_and_get_order(self, adapter, sample_order):
        """Can save and retrieve an order."""
        saved = await adapter.save_order(sample_order)
        assert saved.id == sample_order.id

        retrieved = await adapter.get_order(sample_order.id)
        assert retrieved is not None
        assert retrieved.ticker == sample_order.ticker

    @pytest.mark.asyncio
    async def test_get_open_orders(self, adapter):
        """Can get open orders."""
        pending_order = Order(
            id=uuid4(),
            ticker="KRW-BTC",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Money.krw(Decimal("49000000")),
            volume=Decimal("0.1"),
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
        )
        filled_order = Order(
            id=uuid4(),
            ticker="KRW-BTC",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            price=Money.krw(Decimal("50000000")),
            volume=Decimal("0.1"),
            status=OrderStatus.FILLED,
            created_at=datetime.now(),
        )

        await adapter.save_order(pending_order)
        await adapter.save_order(filled_order)

        open_orders = await adapter.get_open_orders()
        assert len(open_orders) == 1
        assert open_orders[0].status == OrderStatus.PENDING

    @pytest.mark.asyncio
    async def test_update_order_status(self, adapter, sample_order):
        """Can update order status."""
        await adapter.save_order(sample_order)

        updated = await adapter.update_order_status(
            sample_order.id,
            "filled",
        )
        assert updated is not None
        assert updated.status == OrderStatus.FILLED

    # --- Position Operations ---

    @pytest.mark.asyncio
    async def test_save_and_get_position(self, adapter, sample_position):
        """Can save and retrieve a position."""
        saved = await adapter.save_position(sample_position)
        assert saved.ticker == sample_position.ticker

        retrieved = await adapter.get_position(sample_position.ticker)
        assert retrieved is not None
        assert retrieved.volume == sample_position.volume

    @pytest.mark.asyncio
    async def test_get_all_positions(self, adapter):
        """Can get all positions."""
        btc_position = Position.create(
            ticker="KRW-BTC",
            symbol="BTC",
            volume=Decimal("0.5"),
            avg_entry_price=Money.krw(Decimal("50000000")),
        )
        eth_position = Position.create(
            ticker="KRW-ETH",
            symbol="ETH",
            volume=Decimal("2.0"),
            avg_entry_price=Money.krw(Decimal("3000000")),
        )

        await adapter.save_position(btc_position)
        await adapter.save_position(eth_position)

        all_positions = await adapter.get_all_positions()
        assert len(all_positions) == 2

    @pytest.mark.asyncio
    async def test_close_position(self, adapter, sample_position):
        """Can close a position."""
        await adapter.save_position(sample_position)

        result = await adapter.close_position(sample_position.ticker)
        assert result is True

        # Position should be gone
        retrieved = await adapter.get_position(sample_position.ticker)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_close_nonexistent_position(self, adapter):
        """Closing nonexistent position returns False."""
        result = await adapter.close_position("KRW-FAKE")
        assert result is False

    # --- AI Decision Operations ---

    @pytest.mark.asyncio
    async def test_save_and_get_decisions(self, adapter):
        """Can save and retrieve AI decisions."""
        decision = TradingDecision(
            decision=DecisionType.BUY,
            confidence=Decimal("0.85"),
            reasoning="Strong bullish signals",
            risk_assessment="medium",
            key_factors=["RSI oversold", "MACD crossover"],
        )

        saved = await adapter.save_decision("KRW-BTC", decision)
        assert saved["ticker"] == "KRW-BTC"
        assert saved["decision"] == "buy"

        recent = await adapter.get_recent_decisions("KRW-BTC", limit=5)
        assert len(recent) == 1
        assert recent[0]["confidence"] == 0.85

    # --- Portfolio Operations ---

    @pytest.mark.asyncio
    async def test_save_portfolio_snapshot(self, adapter):
        """Can save portfolio snapshot."""
        snapshot = await adapter.save_portfolio_snapshot(
            total_value=Decimal("10000000"),
            positions={"KRW-BTC": {"volume": "0.1", "value": "5000000"}},
        )
        assert snapshot["total_value"] == 10000000.0

    @pytest.mark.asyncio
    async def test_get_portfolio_history(self, adapter):
        """Can get portfolio history."""
        await adapter.save_portfolio_snapshot(
            total_value=Decimal("10000000"),
            positions={},
        )
        await adapter.save_portfolio_snapshot(
            total_value=Decimal("10500000"),
            positions={},
        )

        history = await adapter.get_portfolio_history(days=30)
        assert len(history) == 2

    # --- Statistics ---

    @pytest.mark.asyncio
    async def test_get_trade_statistics(self, adapter):
        """Can calculate trade statistics."""
        # Create trades
        trade1 = Trade(
            id=uuid4(),
            ticker="KRW-BTC",
            side=OrderSide.SELL,
            price=Money.krw(Decimal("51000000")),
            volume=Decimal("0.1"),
            fee=Money.krw(Decimal("25500")),
            status=TradeStatus.COMPLETED,
            executed_at=datetime.now(),
        )
        trade2 = Trade(
            id=uuid4(),
            ticker="KRW-BTC",
            side=OrderSide.SELL,
            price=Money.krw(Decimal("49000000")),
            volume=Decimal("0.1"),
            fee=Money.krw(Decimal("24500")),
            status=TradeStatus.COMPLETED,
            executed_at=datetime.now(),
        )

        await adapter.save_trade(trade1)
        await adapter.save_trade(trade2)

        stats = await adapter.get_trade_statistics()
        # In-memory adapter tracks trade count
        assert stats["total_trades"] == 2

    @pytest.mark.asyncio
    async def test_get_daily_pnl(self, adapter):
        """Can calculate daily PnL."""
        today_trade = Trade(
            id=uuid4(),
            ticker="KRW-BTC",
            side=OrderSide.SELL,
            price=Money.krw(Decimal("51000000")),
            volume=Decimal("0.1"),
            fee=Money.krw(Decimal("25500")),
            status=TradeStatus.COMPLETED,
            executed_at=datetime.now(),
        )

        await adapter.save_trade(today_trade)

        # In-memory adapter returns 0 for PnL (not tracked)
        daily_pnl = await adapter.get_daily_pnl()
        assert daily_pnl == Decimal("0")

    # --- System Operations ---

    @pytest.mark.asyncio
    async def test_health_check(self, adapter):
        """Health check returns True by default."""
        result = await adapter.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_can_fail(self, adapter):
        """Health check can be set to fail for testing."""
        adapter.set_health(False)
        result = await adapter.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_old_data(self, adapter):
        """Can cleanup old data."""
        now = datetime.now()

        # Create old trade
        old_trade = Trade(
            id=uuid4(),
            ticker="KRW-BTC",
            side=OrderSide.BUY,
            price=Money.krw(Decimal("50000000")),
            volume=Decimal("0.1"),
            fee=Money.krw(Decimal("25000")),
            status=TradeStatus.COMPLETED,
            executed_at=now - timedelta(days=100),
        )
        # Create recent trade
        recent_trade = Trade(
            id=uuid4(),
            ticker="KRW-BTC",
            side=OrderSide.BUY,
            price=Money.krw(Decimal("50000000")),
            volume=Decimal("0.1"),
            fee=Money.krw(Decimal("25000")),
            status=TradeStatus.COMPLETED,
            executed_at=now - timedelta(days=10),
        )

        await adapter.save_trade(old_trade)
        await adapter.save_trade(recent_trade)

        deleted = await adapter.cleanup_old_data(days=90)
        assert deleted >= 1
        assert adapter.trade_count == 1

    # --- Data Isolation ---

    @pytest.mark.asyncio
    async def test_clear_removes_all_data(self, adapter, sample_trade, sample_order, sample_position):
        """Clear method removes all stored data."""
        await adapter.save_trade(sample_trade)
        await adapter.save_order(sample_order)
        await adapter.save_position(sample_position)

        adapter.clear()

        assert adapter.trade_count == 0
        assert adapter.order_count == 0
        assert adapter.position_count == 0

    @pytest.mark.asyncio
    async def test_data_is_copied_not_referenced(self, adapter, sample_trade):
        """Saved data is copied, not referenced."""
        await adapter.save_trade(sample_trade)

        retrieved = await adapter.get_trade(sample_trade.id)
        # Should be a different object
        assert retrieved is not sample_trade


class TestAdapterInterfaces:
    """Tests verifying adapter interface compliance."""

    def test_exchange_port_is_abstract(self):
        """ExchangePort is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            ExchangePort()

    def test_ai_port_is_abstract(self):
        """AIPort is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            AIPort()

    def test_market_data_port_is_abstract(self):
        """MarketDataPort is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            MarketDataPort()

    def test_persistence_port_is_abstract(self):
        """PersistencePort is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            PersistencePort()
