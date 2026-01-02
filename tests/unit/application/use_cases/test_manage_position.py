"""
Tests for ManagePositionUseCase.

Following TDD - RED phase: Write failing tests first.
"""
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from src.domain.entities.trade import Position, Trade, OrderSide, TradeStatus
from src.domain.value_objects.money import Money, Currency
from src.domain.value_objects.percentage import Percentage


class TestManagePositionUseCase:
    """Tests for ManagePositionUseCase."""

    @pytest.fixture
    def mock_exchange_port(self):
        """Create mock exchange port."""
        mock = AsyncMock()
        mock.get_position = AsyncMock()
        mock.get_current_price = AsyncMock()
        mock.get_all_positions = AsyncMock()
        return mock

    @pytest.fixture
    def mock_persistence_port(self):
        """Create mock persistence port."""
        mock = AsyncMock()
        mock.get_position = AsyncMock()
        mock.save_position = AsyncMock()
        mock.close_position = AsyncMock()
        mock.get_trades_by_ticker = AsyncMock()
        return mock

    @pytest.fixture
    def use_case(self, mock_exchange_port, mock_persistence_port):
        """Create use case with mock dependencies."""
        from src.application.use_cases.manage_position import ManagePositionUseCase
        return ManagePositionUseCase(
            exchange=mock_exchange_port,
            persistence=mock_persistence_port,
        )

    @pytest.fixture
    def sample_position(self):
        """Create sample position."""
        return Position.create(
            ticker="KRW-BTC",
            symbol="BTC",
            volume=Decimal("0.1"),
            avg_entry_price=Money.krw(Decimal("50000000")),
        )

    # --- Get Position Tests ---

    @pytest.mark.asyncio
    async def test_get_position_returns_position(
        self, use_case, mock_exchange_port, sample_position
    ):
        """Get position returns position with current price info."""
        # Given
        ticker = "KRW-BTC"
        current_price = Money.krw(Decimal("52000000"))

        mock_exchange_port.get_position.return_value = MagicMock(
            ticker=ticker,
            symbol="BTC",
            volume=Decimal("0.1"),
            avg_buy_price=Money.krw(Decimal("50000000")),
            current_price=current_price,
        )
        mock_exchange_port.get_current_price.return_value = current_price

        # When
        result = await use_case.get_position(ticker)

        # Then
        assert result is not None
        assert result["ticker"] == ticker

    @pytest.mark.asyncio
    async def test_get_position_returns_none_when_no_position(
        self, use_case, mock_exchange_port
    ):
        """Get position returns None when no position exists."""
        # Given
        ticker = "KRW-ETH"
        mock_exchange_port.get_position.return_value = None

        # When
        result = await use_case.get_position(ticker)

        # Then
        assert result is None

    # --- P&L Calculation Tests ---

    @pytest.mark.asyncio
    async def test_calculate_pnl_profit(self, use_case, mock_exchange_port):
        """Calculate P&L for profitable position."""
        # Given
        ticker = "KRW-BTC"
        entry_price = Decimal("50000000")
        current_price = Decimal("55000000")
        volume = Decimal("0.1")

        mock_exchange_port.get_position.return_value = MagicMock(
            ticker=ticker,
            volume=volume,
            avg_buy_price=Money.krw(entry_price),
        )
        mock_exchange_port.get_current_price.return_value = Money.krw(current_price)

        # When
        result = await use_case.calculate_pnl(ticker)

        # Then
        expected_pnl = (current_price - entry_price) * volume  # 500000
        assert result["unrealized_pnl"] == expected_pnl
        assert result["profit_rate"] > 0

    @pytest.mark.asyncio
    async def test_calculate_pnl_loss(self, use_case, mock_exchange_port):
        """Calculate P&L for losing position."""
        # Given
        ticker = "KRW-BTC"
        entry_price = Decimal("50000000")
        current_price = Decimal("45000000")
        volume = Decimal("0.1")

        mock_exchange_port.get_position.return_value = MagicMock(
            ticker=ticker,
            volume=volume,
            avg_buy_price=Money.krw(entry_price),
        )
        mock_exchange_port.get_current_price.return_value = Money.krw(current_price)

        # When
        result = await use_case.calculate_pnl(ticker)

        # Then
        expected_pnl = (current_price - entry_price) * volume  # -500000
        assert result["unrealized_pnl"] == expected_pnl
        assert result["profit_rate"] < 0

    @pytest.mark.asyncio
    async def test_calculate_pnl_no_position(self, use_case, mock_exchange_port):
        """Calculate P&L returns zeros when no position."""
        # Given
        ticker = "KRW-BTC"
        mock_exchange_port.get_position.return_value = None

        # When
        result = await use_case.calculate_pnl(ticker)

        # Then
        assert result["unrealized_pnl"] == Decimal("0")
        assert result["profit_rate"] == Decimal("0")

    # --- Stop Loss / Take Profit Tests ---

    @pytest.mark.asyncio
    async def test_should_stop_loss_true(self, use_case, mock_exchange_port):
        """Detect when stop loss should trigger."""
        # Given
        ticker = "KRW-BTC"
        entry_price = Decimal("50000000")
        current_price = Decimal("45000000")  # -10%
        stop_loss_pct = Percentage(Decimal("-0.05"))  # -5%

        mock_exchange_port.get_position.return_value = MagicMock(
            ticker=ticker,
            volume=Decimal("0.1"),
            avg_buy_price=Money.krw(entry_price),
        )
        mock_exchange_port.get_current_price.return_value = Money.krw(current_price)

        # When
        result = await use_case.should_stop_loss(ticker, stop_loss_pct)

        # Then
        assert result is True

    @pytest.mark.asyncio
    async def test_should_stop_loss_false(self, use_case, mock_exchange_port):
        """Stop loss should not trigger when within threshold."""
        # Given
        ticker = "KRW-BTC"
        entry_price = Decimal("50000000")
        current_price = Decimal("49000000")  # -2%
        stop_loss_pct = Percentage(Decimal("-0.05"))  # -5%

        mock_exchange_port.get_position.return_value = MagicMock(
            ticker=ticker,
            volume=Decimal("0.1"),
            avg_buy_price=Money.krw(entry_price),
        )
        mock_exchange_port.get_current_price.return_value = Money.krw(current_price)

        # When
        result = await use_case.should_stop_loss(ticker, stop_loss_pct)

        # Then
        assert result is False

    @pytest.mark.asyncio
    async def test_should_take_profit_true(self, use_case, mock_exchange_port):
        """Detect when take profit should trigger."""
        # Given
        ticker = "KRW-BTC"
        entry_price = Decimal("50000000")
        current_price = Decimal("55000000")  # +10%
        take_profit_pct = Percentage(Decimal("0.05"))  # +5%

        mock_exchange_port.get_position.return_value = MagicMock(
            ticker=ticker,
            volume=Decimal("0.1"),
            avg_buy_price=Money.krw(entry_price),
        )
        mock_exchange_port.get_current_price.return_value = Money.krw(current_price)

        # When
        result = await use_case.should_take_profit(ticker, take_profit_pct)

        # Then
        assert result is True

    # --- Portfolio Summary Tests ---

    @pytest.mark.asyncio
    async def test_get_portfolio_summary(self, use_case, mock_exchange_port):
        """Get summary of all positions."""
        # Given
        mock_exchange_port.get_all_positions.return_value = [
            MagicMock(
                ticker="KRW-BTC",
                volume=Decimal("0.1"),
                avg_buy_price=Money.krw(Decimal("50000000")),
                current_price=Money.krw(Decimal("52000000")),
            ),
            MagicMock(
                ticker="KRW-ETH",
                volume=Decimal("1.0"),
                avg_buy_price=Money.krw(Decimal("3000000")),
                current_price=Money.krw(Decimal("3100000")),
            ),
        ]
        mock_exchange_port.get_current_price.side_effect = [
            Money.krw(Decimal("52000000")),
            Money.krw(Decimal("3100000")),
        ]

        # When
        result = await use_case.get_portfolio_summary()

        # Then
        assert "positions" in result
        assert "total_value" in result
        assert "total_cost" in result
        assert len(result["positions"]) == 2

    @pytest.mark.asyncio
    async def test_portfolio_summary_empty(self, use_case, mock_exchange_port):
        """Portfolio summary for empty portfolio."""
        # Given
        mock_exchange_port.get_all_positions.return_value = []

        # When
        result = await use_case.get_portfolio_summary()

        # Then
        assert result["positions"] == []
        assert result["total_value"] == Decimal("0")
        assert result["total_pnl"] == Decimal("0")

    # --- Update Position Tests ---

    @pytest.mark.asyncio
    async def test_update_position_from_trade(self, use_case, mock_persistence_port):
        """Update position when trade is executed."""
        # Given
        trade = Trade(
            id=MagicMock(),
            ticker="KRW-BTC",
            side=OrderSide.BUY,
            price=Money.krw(Decimal("50000000")),
            volume=Decimal("0.1"),
            fee=Money.krw(Decimal("25000")),
            status=TradeStatus.COMPLETED,
            executed_at=datetime.now(),
        )

        mock_persistence_port.get_position.return_value = None  # New position

        # When
        result = await use_case.update_position_from_trade(trade)

        # Then
        assert result is not None
        mock_persistence_port.save_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_existing_position(self, use_case, mock_persistence_port, sample_position):
        """Update existing position with additional buy."""
        # Given
        trade = Trade(
            id=MagicMock(),
            ticker="KRW-BTC",
            side=OrderSide.BUY,
            price=Money.krw(Decimal("51000000")),
            volume=Decimal("0.05"),
            fee=Money.krw(Decimal("12750")),
            status=TradeStatus.COMPLETED,
            executed_at=datetime.now(),
        )

        mock_persistence_port.get_position.return_value = sample_position

        # When
        result = await use_case.update_position_from_trade(trade)

        # Then
        assert result is not None
        # New volume should be 0.1 + 0.05 = 0.15
        saved_position = mock_persistence_port.save_position.call_args[0][0]
        assert saved_position.volume == Decimal("0.15")

    @pytest.mark.asyncio
    async def test_close_position_on_sell_all(self, use_case, mock_persistence_port, sample_position):
        """Close position when selling entire holding."""
        # Given
        trade = Trade(
            id=MagicMock(),
            ticker="KRW-BTC",
            side=OrderSide.SELL,
            price=Money.krw(Decimal("52000000")),
            volume=Decimal("0.1"),  # Entire position
            fee=Money.krw(Decimal("26000")),
            status=TradeStatus.COMPLETED,
            executed_at=datetime.now(),
        )

        mock_persistence_port.get_position.return_value = sample_position

        # When
        result = await use_case.update_position_from_trade(trade)

        # Then
        mock_persistence_port.close_position.assert_called_once_with("KRW-BTC")


class TestManagePositionUseCaseValidation:
    """Validation tests for ManagePositionUseCase."""

    @pytest.fixture
    def mock_exchange_port(self):
        """Create mock exchange port."""
        return AsyncMock()

    @pytest.fixture
    def mock_persistence_port(self):
        """Create mock persistence port."""
        return AsyncMock()

    @pytest.fixture
    def use_case(self, mock_exchange_port, mock_persistence_port):
        """Create use case with mock dependencies."""
        from src.application.use_cases.manage_position import ManagePositionUseCase
        return ManagePositionUseCase(
            exchange=mock_exchange_port,
            persistence=mock_persistence_port,
        )

    @pytest.mark.asyncio
    async def test_validates_ticker_format(self, use_case):
        """Validate ticker format."""
        # Given
        invalid_ticker = "INVALID"

        # When
        result = await use_case.get_position(invalid_ticker)

        # Then
        assert result is None

    @pytest.mark.asyncio
    async def test_validates_stop_loss_percentage(self, use_case, mock_exchange_port):
        """Validate stop loss percentage is negative."""
        # Given
        ticker = "KRW-BTC"
        invalid_stop_loss = Percentage(Decimal("0.05"))  # Positive (should be negative)

        mock_exchange_port.get_position.return_value = MagicMock(
            ticker=ticker,
            volume=Decimal("0.1"),
            avg_buy_price=Money.krw(Decimal("50000000")),
        )
        mock_exchange_port.get_current_price.return_value = Money.krw(Decimal("45000000"))

        # When
        result = await use_case.should_stop_loss(ticker, invalid_stop_loss)

        # Then
        # Should handle gracefully (always return False for invalid input)
        assert result is False

    @pytest.mark.asyncio
    async def test_validates_take_profit_percentage(self, use_case, mock_exchange_port):
        """Validate take profit percentage is positive."""
        # Given
        ticker = "KRW-BTC"
        invalid_take_profit = Percentage(Decimal("-0.05"))  # Negative (should be positive)

        mock_exchange_port.get_position.return_value = MagicMock(
            ticker=ticker,
            volume=Decimal("0.1"),
            avg_buy_price=Money.krw(Decimal("50000000")),
        )
        mock_exchange_port.get_current_price.return_value = Money.krw(Decimal("55000000"))

        # When
        result = await use_case.should_take_profit(ticker, invalid_take_profit)

        # Then
        # Should handle gracefully (always return False for invalid input)
        assert result is False
