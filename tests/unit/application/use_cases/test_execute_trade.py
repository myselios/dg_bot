"""
Tests for ExecuteTradeUseCase.

Following TDD - RED phase: Write failing tests first.
"""
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.domain.entities.trade import Trade, Order, OrderSide, OrderStatus, TradeStatus
from src.domain.value_objects.money import Money, Currency
from src.application.dto.trading import OrderRequest, OrderResponse


class TestExecuteTradeUseCase:
    """Tests for ExecuteTradeUseCase."""

    @pytest.fixture
    def mock_exchange_port(self):
        """Create mock exchange port."""
        mock = AsyncMock()
        mock.execute_market_buy = AsyncMock()
        mock.execute_market_sell = AsyncMock()
        mock.get_balance = AsyncMock()
        mock.get_position = AsyncMock()
        mock.get_current_price = AsyncMock()
        return mock

    @pytest.fixture
    def mock_persistence_port(self):
        """Create mock persistence port."""
        mock = AsyncMock()
        mock.save_trade = AsyncMock()
        mock.save_order = AsyncMock()
        mock.get_position = AsyncMock()
        mock.save_position = AsyncMock()
        return mock

    @pytest.fixture
    def use_case(self, mock_exchange_port, mock_persistence_port):
        """Create use case with mock dependencies."""
        from src.application.use_cases.execute_trade import ExecuteTradeUseCase
        return ExecuteTradeUseCase(
            exchange=mock_exchange_port,
            persistence=mock_persistence_port,
        )

    # --- Buy Order Tests ---

    @pytest.mark.asyncio
    async def test_execute_buy_success(self, use_case, mock_exchange_port, mock_persistence_port):
        """Successfully execute a buy order."""
        # Given
        ticker = "KRW-BTC"
        amount = Money.krw(Decimal("100000"))

        mock_exchange_port.execute_market_buy.return_value = OrderResponse.success_response(
            ticker=ticker,
            side=OrderSide.BUY,
            order_id="order-123",
            executed_price=Money.krw(Decimal("50000000")),
            executed_volume=Decimal("0.002"),
            fee=Money.krw(Decimal("50")),
        )
        mock_exchange_port.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("1000000"))
        )

        # When
        result = await use_case.execute_buy(ticker, amount)

        # Then
        assert result.success is True
        assert result.ticker == ticker
        mock_exchange_port.execute_market_buy.assert_called_once_with(ticker, amount)
        mock_persistence_port.save_trade.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_buy_insufficient_balance(self, use_case, mock_exchange_port):
        """Reject buy order when balance is insufficient."""
        # Given
        ticker = "KRW-BTC"
        amount = Money.krw(Decimal("1000000"))

        mock_exchange_port.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("100000"))  # Less than requested
        )

        # When
        result = await use_case.execute_buy(ticker, amount)

        # Then
        assert result.success is False
        assert "insufficient" in result.error_message.lower()
        mock_exchange_port.execute_market_buy.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_buy_below_minimum(self, use_case, mock_exchange_port):
        """Reject buy order below minimum amount."""
        # Given
        ticker = "KRW-BTC"
        amount = Money.krw(Decimal("1000"))  # Below 5000 KRW minimum

        mock_exchange_port.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("1000000"))
        )

        # When
        result = await use_case.execute_buy(ticker, amount)

        # Then
        assert result.success is False
        assert "minimum" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_execute_buy_exchange_failure(self, use_case, mock_exchange_port, mock_persistence_port):
        """Handle exchange failure gracefully."""
        # Given
        ticker = "KRW-BTC"
        amount = Money.krw(Decimal("100000"))

        mock_exchange_port.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("1000000"))
        )
        mock_exchange_port.execute_market_buy.return_value = OrderResponse.failure_response(
            ticker=ticker,
            side=OrderSide.BUY,
            error_message="Exchange API error",
        )

        # When
        result = await use_case.execute_buy(ticker, amount)

        # Then
        assert result.success is False
        mock_persistence_port.save_trade.assert_not_called()

    # --- Sell Order Tests ---

    @pytest.mark.asyncio
    async def test_execute_sell_success(self, use_case, mock_exchange_port, mock_persistence_port):
        """Successfully execute a sell order."""
        # Given
        ticker = "KRW-BTC"
        volume = Decimal("0.01")

        mock_exchange_port.get_position.return_value = MagicMock(
            volume=Decimal("0.1")  # Has enough to sell
        )
        mock_exchange_port.execute_market_sell.return_value = OrderResponse.success_response(
            ticker=ticker,
            side=OrderSide.SELL,
            order_id="order-456",
            executed_price=Money.krw(Decimal("51000000")),
            executed_volume=volume,
            fee=Money.krw(Decimal("255")),
        )

        # When
        result = await use_case.execute_sell(ticker, volume)

        # Then
        assert result.success is True
        mock_exchange_port.execute_market_sell.assert_called_once_with(ticker, volume)
        mock_persistence_port.save_trade.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_sell_insufficient_holdings(self, use_case, mock_exchange_port):
        """Reject sell order when holdings are insufficient."""
        # Given
        ticker = "KRW-BTC"
        volume = Decimal("1.0")

        mock_exchange_port.get_position.return_value = MagicMock(
            volume=Decimal("0.1")  # Less than requested
        )

        # When
        result = await use_case.execute_sell(ticker, volume)

        # Then
        assert result.success is False
        assert "insufficient" in result.error_message.lower()
        mock_exchange_port.execute_market_sell.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_sell_no_position(self, use_case, mock_exchange_port):
        """Reject sell when no position exists."""
        # Given
        ticker = "KRW-BTC"
        volume = Decimal("0.01")

        mock_exchange_port.get_position.return_value = None

        # When
        result = await use_case.execute_sell(ticker, volume)

        # Then
        assert result.success is False
        assert "no position" in result.error_message.lower()

    # --- Trade Recording Tests ---

    @pytest.mark.asyncio
    async def test_trade_recorded_on_success(self, use_case, mock_exchange_port, mock_persistence_port):
        """Trade is recorded to persistence on successful execution."""
        # Given
        ticker = "KRW-BTC"
        amount = Money.krw(Decimal("100000"))

        mock_exchange_port.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("1000000"))
        )
        mock_exchange_port.execute_market_buy.return_value = OrderResponse.success_response(
            ticker=ticker,
            side=OrderSide.BUY,
            order_id="order-123",
            executed_price=Money.krw(Decimal("50000000")),
            executed_volume=Decimal("0.002"),
            fee=Money.krw(Decimal("50")),
        )

        # When
        await use_case.execute_buy(ticker, amount)

        # Then
        mock_persistence_port.save_trade.assert_called_once()
        saved_trade = mock_persistence_port.save_trade.call_args[0][0]
        assert isinstance(saved_trade, Trade)
        assert saved_trade.ticker == ticker
        assert saved_trade.side == OrderSide.BUY

    # --- Sell All Tests ---

    @pytest.mark.asyncio
    async def test_execute_sell_all(self, use_case, mock_exchange_port, mock_persistence_port):
        """Sell entire position."""
        # Given
        ticker = "KRW-BTC"
        position_volume = Decimal("0.5")

        mock_exchange_port.get_position.return_value = MagicMock(
            volume=position_volume
        )
        mock_exchange_port.execute_market_sell.return_value = OrderResponse.success_response(
            ticker=ticker,
            side=OrderSide.SELL,
            order_id="order-789",
            executed_price=Money.krw(Decimal("50000000")),
            executed_volume=position_volume,
            fee=Money.krw(Decimal("12500")),
        )

        # When
        result = await use_case.execute_sell_all(ticker)

        # Then
        assert result.success is True
        mock_exchange_port.execute_market_sell.assert_called_once_with(ticker, position_volume)


class TestExecuteTradeUseCaseValidation:
    """Validation tests for ExecuteTradeUseCase."""

    @pytest.fixture
    def mock_exchange_port(self):
        """Create mock exchange port."""
        mock = AsyncMock()
        mock.get_balance = AsyncMock()
        mock.get_position = AsyncMock()
        return mock

    @pytest.fixture
    def mock_persistence_port(self):
        """Create mock persistence port."""
        return AsyncMock()

    @pytest.fixture
    def use_case(self, mock_exchange_port, mock_persistence_port):
        """Create use case with mock dependencies."""
        from src.application.use_cases.execute_trade import ExecuteTradeUseCase
        return ExecuteTradeUseCase(
            exchange=mock_exchange_port,
            persistence=mock_persistence_port,
        )

    @pytest.mark.asyncio
    async def test_buy_validates_ticker_format(self, use_case, mock_exchange_port):
        """Validate ticker format for buy orders."""
        # Given
        invalid_ticker = "BTCKRW"  # Wrong format
        amount = Money.krw(Decimal("100000"))

        mock_exchange_port.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("1000000"))
        )

        # When
        result = await use_case.execute_buy(invalid_ticker, amount)

        # Then
        assert result.success is False
        assert "ticker" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_sell_validates_positive_volume(self, use_case):
        """Validate volume is positive for sell orders."""
        # Given
        ticker = "KRW-BTC"
        volume = Decimal("-0.01")  # Negative

        # When
        result = await use_case.execute_sell(ticker, volume)

        # Then
        assert result.success is False
        assert "volume" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_buy_validates_positive_amount(self, use_case, mock_exchange_port):
        """Validate amount is positive for buy orders."""
        # Given
        ticker = "KRW-BTC"
        amount = Money.krw(Decimal("-100000"))  # Negative

        mock_exchange_port.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("1000000"))
        )

        # When
        result = await use_case.execute_buy(ticker, amount)

        # Then
        assert result.success is False


class TestExecuteTradeUseCaseFeeCalculation:
    """Fee calculation tests for ExecuteTradeUseCase."""

    @pytest.fixture
    def mock_exchange_port(self):
        """Create mock exchange port."""
        mock = AsyncMock()
        mock.execute_market_buy = AsyncMock()
        mock.get_balance = AsyncMock()
        return mock

    @pytest.fixture
    def mock_persistence_port(self):
        """Create mock persistence port."""
        mock = AsyncMock()
        mock.save_trade = AsyncMock()
        return mock

    @pytest.fixture
    def use_case(self, mock_exchange_port, mock_persistence_port):
        """Create use case with mock dependencies."""
        from src.application.use_cases.execute_trade import ExecuteTradeUseCase
        return ExecuteTradeUseCase(
            exchange=mock_exchange_port,
            persistence=mock_persistence_port,
        )

    @pytest.mark.asyncio
    async def test_fee_included_in_trade(self, use_case, mock_exchange_port, mock_persistence_port):
        """Verify fee is correctly included in trade record."""
        # Given
        ticker = "KRW-BTC"
        amount = Money.krw(Decimal("100000"))
        expected_fee = Money.krw(Decimal("50"))

        mock_exchange_port.get_balance.return_value = MagicMock(
            available=Money.krw(Decimal("1000000"))
        )
        mock_exchange_port.execute_market_buy.return_value = OrderResponse.success_response(
            ticker=ticker,
            side=OrderSide.BUY,
            order_id="order-123",
            executed_price=Money.krw(Decimal("50000000")),
            executed_volume=Decimal("0.002"),
            fee=expected_fee,
        )

        # When
        await use_case.execute_buy(ticker, amount)

        # Then
        saved_trade = mock_persistence_port.save_trade.call_args[0][0]
        assert saved_trade.fee == expected_fee
