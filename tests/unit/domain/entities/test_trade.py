"""
Tests for Trade, Order, and Position entities.
TDD RED Phase - These tests should fail until implementation.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from src.domain.entities.trade import (
    Trade,
    Order,
    Position,
    OrderSide,
    OrderType,
    OrderStatus,
    TradeStatus,
)
from src.domain.value_objects.money import Money, Currency
from src.domain.value_objects.percentage import Percentage


class TestOrderSide:
    """Tests for OrderSide enum."""

    def test_buy_side_exists(self):
        """BUY side should be available."""
        assert OrderSide.BUY.value == "buy"

    def test_sell_side_exists(self):
        """SELL side should be available."""
        assert OrderSide.SELL.value == "sell"

    def test_opposite_of_buy_is_sell(self):
        """Opposite of BUY should be SELL."""
        assert OrderSide.BUY.opposite() == OrderSide.SELL

    def test_opposite_of_sell_is_buy(self):
        """Opposite of SELL should be BUY."""
        assert OrderSide.SELL.opposite() == OrderSide.BUY


class TestOrderType:
    """Tests for OrderType enum."""

    def test_market_order_type(self):
        """MARKET order type should be available."""
        assert OrderType.MARKET.value == "market"

    def test_limit_order_type(self):
        """LIMIT order type should be available."""
        assert OrderType.LIMIT.value == "limit"


class TestOrderStatus:
    """Tests for OrderStatus enum."""

    def test_pending_status(self):
        """PENDING status should be available."""
        assert OrderStatus.PENDING.value == "pending"

    def test_filled_status(self):
        """FILLED status should be available."""
        assert OrderStatus.FILLED.value == "filled"

    def test_partially_filled_status(self):
        """PARTIALLY_FILLED status should be available."""
        assert OrderStatus.PARTIALLY_FILLED.value == "partially_filled"

    def test_cancelled_status(self):
        """CANCELLED status should be available."""
        assert OrderStatus.CANCELLED.value == "cancelled"

    def test_failed_status(self):
        """FAILED status should be available."""
        assert OrderStatus.FAILED.value == "failed"

    def test_is_terminal_for_filled(self):
        """FILLED should be terminal status."""
        assert OrderStatus.FILLED.is_terminal()

    def test_is_terminal_for_pending(self):
        """PENDING should not be terminal status."""
        assert not OrderStatus.PENDING.is_terminal()


class TestOrder:
    """Tests for Order entity."""

    @pytest.fixture
    def sample_buy_order(self):
        """Create a sample buy order for testing."""
        return Order.create_market_buy(
            ticker="KRW-BTC",
            amount=Money.krw(100000),
        )

    @pytest.fixture
    def sample_sell_order(self):
        """Create a sample sell order for testing."""
        return Order.create_market_sell(
            ticker="KRW-BTC",
            volume=Decimal("0.001"),
        )

    # --- Creation Tests ---

    def test_create_market_buy_order(self, sample_buy_order):
        """Should create market buy order."""
        assert sample_buy_order.ticker == "KRW-BTC"
        assert sample_buy_order.side == OrderSide.BUY
        assert sample_buy_order.order_type == OrderType.MARKET
        assert sample_buy_order.amount == Money.krw(100000)
        assert sample_buy_order.status == OrderStatus.PENDING
        assert sample_buy_order.volume is None  # Market buy uses amount

    def test_create_market_sell_order(self, sample_sell_order):
        """Should create market sell order."""
        assert sample_sell_order.ticker == "KRW-BTC"
        assert sample_sell_order.side == OrderSide.SELL
        assert sample_sell_order.order_type == OrderType.MARKET
        assert sample_sell_order.volume == Decimal("0.001")
        assert sample_sell_order.amount is None  # Market sell uses volume

    def test_create_limit_buy_order(self):
        """Should create limit buy order with price."""
        order = Order.create_limit_buy(
            ticker="KRW-BTC",
            price=Money.krw(50000000),
            volume=Decimal("0.001"),
        )
        assert order.order_type == OrderType.LIMIT
        assert order.price == Money.krw(50000000)
        assert order.volume == Decimal("0.001")

    def test_order_has_unique_id(self, sample_buy_order):
        """Order should have unique ID."""
        assert isinstance(sample_buy_order.id, UUID)

    def test_order_has_created_at(self, sample_buy_order):
        """Order should have creation timestamp."""
        assert isinstance(sample_buy_order.created_at, datetime)

    # --- State Transition Tests ---

    def test_fill_order(self, sample_buy_order):
        """Should fill order with execution details."""
        filled = sample_buy_order.fill(
            executed_price=Money.krw(50000000),
            executed_volume=Decimal("0.002"),
            fee=Money.krw(50),
            exchange_order_id="upbit-12345",
        )
        assert filled.status == OrderStatus.FILLED
        assert filled.executed_price == Money.krw(50000000)
        assert filled.executed_volume == Decimal("0.002")
        assert filled.fee == Money.krw(50)
        assert filled.exchange_order_id == "upbit-12345"
        assert filled.filled_at is not None

    def test_fill_order_preserves_original(self, sample_buy_order):
        """Filling order should not mutate original (immutable)."""
        original_status = sample_buy_order.status
        sample_buy_order.fill(
            executed_price=Money.krw(50000000),
            executed_volume=Decimal("0.002"),
            fee=Money.krw(50),
        )
        assert sample_buy_order.status == original_status

    def test_cancel_order(self, sample_buy_order):
        """Should cancel pending order."""
        cancelled = sample_buy_order.cancel(reason="User requested")
        assert cancelled.status == OrderStatus.CANCELLED
        assert cancelled.cancel_reason == "User requested"

    def test_fail_order(self, sample_buy_order):
        """Should mark order as failed."""
        failed = sample_buy_order.fail(error="Insufficient balance")
        assert failed.status == OrderStatus.FAILED
        assert failed.error_message == "Insufficient balance"

    def test_cannot_fill_cancelled_order(self, sample_buy_order):
        """Should raise error when filling cancelled order."""
        cancelled = sample_buy_order.cancel()
        with pytest.raises(ValueError, match="terminal"):
            cancelled.fill(
                executed_price=Money.krw(50000000),
                executed_volume=Decimal("0.002"),
                fee=Money.krw(50),
            )

    # --- Computed Properties ---

    def test_executed_total(self, sample_buy_order):
        """Should calculate executed total (price * volume)."""
        filled = sample_buy_order.fill(
            executed_price=Money.krw(50000000),
            executed_volume=Decimal("0.002"),
            fee=Money.krw(50),
        )
        assert filled.executed_total == Money.krw(100000)

    def test_total_cost_includes_fee(self, sample_buy_order):
        """Should calculate total cost including fee."""
        filled = sample_buy_order.fill(
            executed_price=Money.krw(50000000),
            executed_volume=Decimal("0.002"),
            fee=Money.krw(50),
        )
        assert filled.total_cost == Money.krw(100050)


class TestTrade:
    """Tests for Trade entity (completed transaction)."""

    @pytest.fixture
    def sample_trade(self):
        """Create a sample trade for testing."""
        return Trade.create(
            ticker="KRW-BTC",
            side=OrderSide.BUY,
            price=Money.krw(50000000),
            volume=Decimal("0.002"),
            fee=Money.krw(50),
            exchange_trade_id="upbit-trade-123",
        )

    # --- Creation Tests ---

    def test_create_trade(self, sample_trade):
        """Should create trade from execution details."""
        assert sample_trade.ticker == "KRW-BTC"
        assert sample_trade.side == OrderSide.BUY
        assert sample_trade.price == Money.krw(50000000)
        assert sample_trade.volume == Decimal("0.002")
        assert sample_trade.fee == Money.krw(50)
        assert sample_trade.exchange_trade_id == "upbit-trade-123"
        assert sample_trade.status == TradeStatus.COMPLETED

    def test_trade_has_unique_id(self, sample_trade):
        """Trade should have unique ID."""
        assert isinstance(sample_trade.id, UUID)

    def test_trade_has_timestamp(self, sample_trade):
        """Trade should have execution timestamp."""
        assert isinstance(sample_trade.executed_at, datetime)

    # --- Computed Properties ---

    def test_total_amount(self, sample_trade):
        """Should calculate total amount (price * volume)."""
        assert sample_trade.total_amount == Money.krw(100000)

    def test_total_cost_for_buy(self, sample_trade):
        """Buy trade total cost should include fee."""
        assert sample_trade.total_cost == Money.krw(100050)

    def test_net_amount_for_sell(self):
        """Sell trade net amount should subtract fee."""
        sell_trade = Trade.create(
            ticker="KRW-BTC",
            side=OrderSide.SELL,
            price=Money.krw(50000000),
            volume=Decimal("0.002"),
            fee=Money.krw(50),
        )
        assert sell_trade.net_amount == Money.krw(99950)

    # --- Trade from Order ---

    def test_create_trade_from_filled_order(self):
        """Should create Trade from filled Order."""
        order = Order.create_market_buy(
            ticker="KRW-BTC",
            amount=Money.krw(100000),
        )
        filled_order = order.fill(
            executed_price=Money.krw(50000000),
            executed_volume=Decimal("0.002"),
            fee=Money.krw(50),
            exchange_order_id="upbit-12345",
        )
        trade = Trade.from_order(filled_order)
        assert trade.ticker == "KRW-BTC"
        assert trade.side == OrderSide.BUY
        assert trade.price == Money.krw(50000000)
        assert trade.volume == Decimal("0.002")


class TestPosition:
    """Tests for Position entity (current holding)."""

    @pytest.fixture
    def sample_position(self):
        """Create a sample position for testing."""
        return Position.create(
            ticker="KRW-BTC",
            symbol="BTC",
            volume=Decimal("0.005"),
            avg_entry_price=Money.krw(50000000),
            entry_time=datetime.now() - timedelta(hours=2),
        )

    # --- Creation Tests ---

    def test_create_position(self, sample_position):
        """Should create position with entry details."""
        assert sample_position.ticker == "KRW-BTC"
        assert sample_position.symbol == "BTC"
        assert sample_position.volume == Decimal("0.005")
        assert sample_position.avg_entry_price == Money.krw(50000000)
        assert isinstance(sample_position.entry_time, datetime)

    def test_position_has_unique_id(self, sample_position):
        """Position should have unique ID."""
        assert isinstance(sample_position.id, UUID)

    def test_empty_position(self):
        """Should create empty position."""
        pos = Position.empty("KRW-BTC", "BTC")
        assert pos.volume == Decimal("0")
        assert pos.is_empty()

    # --- Computed Properties ---

    def test_total_cost(self, sample_position):
        """Should calculate total cost (avg_price * volume)."""
        # 50,000,000 * 0.005 = 250,000
        assert sample_position.total_cost == Money.krw(250000)

    def test_current_value(self, sample_position):
        """Should calculate current value with market price."""
        current_price = Money.krw(55000000)
        # 55,000,000 * 0.005 = 275,000
        assert sample_position.current_value(current_price) == Money.krw(275000)

    def test_profit_loss(self, sample_position):
        """Should calculate profit/loss."""
        current_price = Money.krw(55000000)
        # 275,000 - 250,000 = 25,000
        assert sample_position.profit_loss(current_price) == Money.krw(25000)

    def test_profit_rate(self, sample_position):
        """Should calculate profit rate as percentage."""
        current_price = Money.krw(55000000)
        # (55M - 50M) / 50M = 0.10 = 10%
        profit_rate = sample_position.profit_rate(current_price)
        assert profit_rate.as_points() == Decimal("10")

    def test_holding_duration(self, sample_position):
        """Should calculate holding duration."""
        duration = sample_position.holding_duration()
        assert duration >= timedelta(hours=2)

    def test_holding_hours(self, sample_position):
        """Should calculate holding hours."""
        hours = sample_position.holding_hours()
        assert hours >= 2.0

    # --- Position Updates ---

    def test_add_to_position(self, sample_position):
        """Should add volume to position (averaging up/down)."""
        updated = sample_position.add(
            volume=Decimal("0.003"),
            price=Money.krw(60000000),
        )
        # New avg = (0.005 * 50M + 0.003 * 60M) / 0.008 = 53,750,000
        assert updated.volume == Decimal("0.008")
        assert updated.avg_entry_price.amount == Decimal("53750000")

    def test_reduce_position(self, sample_position):
        """Should reduce volume from position."""
        updated = sample_position.reduce(Decimal("0.002"))
        assert updated.volume == Decimal("0.003")
        # Average entry price remains unchanged
        assert updated.avg_entry_price == sample_position.avg_entry_price

    def test_reduce_to_zero(self, sample_position):
        """Should reduce position to zero (close)."""
        closed = sample_position.reduce(Decimal("0.005"))
        assert closed.volume == Decimal("0")
        assert closed.is_empty()

    def test_reduce_below_zero_raises_error(self, sample_position):
        """Should raise error when reducing below zero."""
        with pytest.raises(ValueError, match="exceed"):
            sample_position.reduce(Decimal("0.010"))

    def test_close_position(self, sample_position):
        """Should close position completely."""
        closed = sample_position.close()
        assert closed.is_empty()
        assert closed.closed_at is not None

    # --- Status Checks ---

    def test_is_profitable(self, sample_position):
        """Should detect profitable position."""
        assert sample_position.is_profitable(Money.krw(55000000))
        assert not sample_position.is_profitable(Money.krw(45000000))

    def test_is_at_loss(self, sample_position):
        """Should detect position at loss."""
        assert sample_position.is_at_loss(Money.krw(45000000))
        assert not sample_position.is_at_loss(Money.krw(55000000))

    def test_should_stop_loss(self, sample_position):
        """Should detect stop loss trigger."""
        stop_loss_pct = Percentage(Decimal("-0.05"))  # -5%
        # At 47.5M, loss is -5%
        assert sample_position.should_stop_loss(
            Money.krw(47500000), stop_loss_pct
        )
        assert not sample_position.should_stop_loss(
            Money.krw(50000000), stop_loss_pct
        )

    def test_should_take_profit(self, sample_position):
        """Should detect take profit trigger."""
        take_profit_pct = Percentage(Decimal("0.10"))  # +10%
        # At 55M, profit is 10%
        assert sample_position.should_take_profit(
            Money.krw(55000000), take_profit_pct
        )
        assert not sample_position.should_take_profit(
            Money.krw(52000000), take_profit_pct
        )


class TestTradeStatus:
    """Tests for TradeStatus enum."""

    def test_completed_status(self):
        """COMPLETED status should be available."""
        assert TradeStatus.COMPLETED.value == "completed"

    def test_pending_settlement_status(self):
        """PENDING_SETTLEMENT status should be available."""
        assert TradeStatus.PENDING_SETTLEMENT.value == "pending_settlement"

    def test_failed_status(self):
        """FAILED status should be available."""
        assert TradeStatus.FAILED.value == "failed"
