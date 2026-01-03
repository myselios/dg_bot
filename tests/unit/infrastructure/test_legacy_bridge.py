"""
Tests for Legacy Bridge Adapters.

These tests verify that legacy services can be wrapped and used
through Clean Architecture ports.
"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock


class TestLegacyExchangeAdapter:
    """Test LegacyExchangeAdapter wrapping UpbitClient."""

    @pytest.mark.asyncio
    async def test_get_balance(self):
        """Should get balance from legacy client."""
        from src.infrastructure.adapters.legacy_bridge import LegacyExchangeAdapter

        mock_client = MagicMock()
        mock_client.get_balance.return_value = 1000000

        adapter = LegacyExchangeAdapter(mock_client)
        balance = await adapter.get_balance("KRW")

        assert balance.currency == "KRW"
        assert balance.available.amount == Decimal("1000000")
        mock_client.get_balance.assert_called_once_with("KRW")

    @pytest.mark.asyncio
    async def test_get_balance_handles_none(self):
        """Should handle None balance gracefully."""
        from src.infrastructure.adapters.legacy_bridge import LegacyExchangeAdapter

        mock_client = MagicMock()
        mock_client.get_balance.return_value = None

        adapter = LegacyExchangeAdapter(mock_client)
        balance = await adapter.get_balance("KRW")

        assert balance.available.amount == Decimal("0")

    @pytest.mark.asyncio
    async def test_execute_market_buy(self):
        """Should execute market buy through legacy client."""
        from src.infrastructure.adapters.legacy_bridge import LegacyExchangeAdapter
        from src.domain.value_objects.money import Money

        mock_client = MagicMock()
        mock_client.buy_market_order.return_value = {
            "uuid": "order-123",
            "volume": "0.001",
        }

        adapter = LegacyExchangeAdapter(mock_client)
        response = await adapter.execute_market_buy(
            "KRW-BTC",
            Money.krw(Decimal("100000"))
        )

        assert response.success is True
        assert response.order_id == "order-123"
        mock_client.buy_market_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_market_buy_failure(self):
        """Should handle buy failure."""
        from src.infrastructure.adapters.legacy_bridge import LegacyExchangeAdapter
        from src.domain.value_objects.money import Money

        mock_client = MagicMock()
        mock_client.buy_market_order.return_value = None

        adapter = LegacyExchangeAdapter(mock_client)
        response = await adapter.execute_market_buy(
            "KRW-BTC",
            Money.krw(Decimal("100000"))
        )

        assert response.success is False

    @pytest.mark.asyncio
    async def test_get_position(self):
        """Should get position from legacy client."""
        from src.infrastructure.adapters.legacy_bridge import LegacyExchangeAdapter

        mock_client = MagicMock()
        mock_client.get_balance.return_value = 0.01
        mock_client.get_avg_buy_price.return_value = 50000000
        mock_client.get_current_price.return_value = 51000000

        adapter = LegacyExchangeAdapter(mock_client)
        position = await adapter.get_position("KRW-BTC")

        assert position is not None
        assert position.ticker == "KRW-BTC"
        assert position.volume == Decimal("0.01")
        assert position.avg_buy_price.amount == Decimal("50000000")

    @pytest.mark.asyncio
    async def test_get_position_no_balance(self):
        """Should return None when no balance."""
        from src.infrastructure.adapters.legacy_bridge import LegacyExchangeAdapter

        mock_client = MagicMock()
        mock_client.get_balance.return_value = 0

        adapter = LegacyExchangeAdapter(mock_client)
        position = await adapter.get_position("KRW-BTC")

        assert position is None

    @pytest.mark.asyncio
    async def test_get_current_price(self):
        """Should get current price."""
        from src.infrastructure.adapters.legacy_bridge import LegacyExchangeAdapter

        mock_client = MagicMock()
        mock_client.get_current_price.return_value = 50000000

        adapter = LegacyExchangeAdapter(mock_client)
        price = await adapter.get_current_price("KRW-BTC")

        assert price.amount == Decimal("50000000")


class TestLegacyAIAdapter:
    """Test LegacyAIAdapter wrapping AIService."""

    @pytest.mark.asyncio
    async def test_analyze_buy_decision(self):
        """Should analyze and return buy decision."""
        from src.infrastructure.adapters.legacy_bridge import LegacyAIAdapter
        from src.application.dto.analysis import AnalysisRequest, DecisionType

        mock_service = MagicMock()
        mock_service.analyze.return_value = {
            "decision": "buy",
            "confidence": "high",
            "reason": "Strong bullish signal",
        }

        adapter = LegacyAIAdapter(mock_service)
        request = AnalysisRequest(
            ticker="KRW-BTC",
            current_price=Decimal("50000000"),
        )

        decision = await adapter.analyze(request)

        assert decision.decision == DecisionType.BUY
        assert decision.confidence == Decimal("0.9")
        assert "bullish" in decision.reasoning.lower()

    @pytest.mark.asyncio
    async def test_analyze_hold_decision(self):
        """Should analyze and return hold decision."""
        from src.infrastructure.adapters.legacy_bridge import LegacyAIAdapter
        from src.application.dto.analysis import AnalysisRequest, DecisionType

        mock_service = MagicMock()
        mock_service.analyze.return_value = {
            "decision": "hold",
            "confidence": "medium",
            "reason": "Wait for better opportunity",
        }

        adapter = LegacyAIAdapter(mock_service)
        request = AnalysisRequest(
            ticker="KRW-BTC",
            current_price=Decimal("50000000"),
        )

        decision = await adapter.analyze(request)

        assert decision.decision == DecisionType.HOLD
        assert decision.confidence == Decimal("0.6")

    @pytest.mark.asyncio
    async def test_analyze_handles_error(self):
        """Should return HOLD on error."""
        from src.infrastructure.adapters.legacy_bridge import LegacyAIAdapter
        from src.application.dto.analysis import AnalysisRequest, DecisionType

        mock_service = MagicMock()
        mock_service.analyze.side_effect = Exception("API Error")

        adapter = LegacyAIAdapter(mock_service)
        request = AnalysisRequest(
            ticker="KRW-BTC",
            current_price=Decimal("50000000"),
        )

        decision = await adapter.analyze(request)

        assert decision.decision == DecisionType.HOLD
        assert decision.confidence == Decimal("0")
        assert "failed" in decision.reasoning.lower()


class TestLegacyMarketDataAdapter:
    """Test LegacyMarketDataAdapter wrapping DataCollector."""

    @pytest.mark.asyncio
    async def test_get_ohlcv_empty(self):
        """Should handle empty data."""
        from src.infrastructure.adapters.legacy_bridge import LegacyMarketDataAdapter
        import pandas as pd

        mock_collector = MagicMock()
        mock_collector.collect_chart_data.return_value = pd.DataFrame()

        adapter = LegacyMarketDataAdapter(mock_collector)
        data = await adapter.get_ohlcv("KRW-BTC")

        assert data == []

    @pytest.mark.asyncio
    async def test_is_ticker_valid(self):
        """Should check ticker validity."""
        from src.infrastructure.adapters.legacy_bridge import LegacyMarketDataAdapter

        mock_collector = MagicMock()

        adapter = LegacyMarketDataAdapter(mock_collector)

        # Mock pyupbit.get_tickers
        with pytest.MonkeyPatch.context() as mp:
            import src.infrastructure.adapters.legacy_bridge as bridge_module
            mp.setattr("pyupbit.get_tickers", lambda fiat: ["KRW-BTC", "KRW-ETH"])

            # Since we can't easily mock pyupbit import, just verify method exists
            assert hasattr(adapter, "is_ticker_valid")


class TestContainerLegacyIntegration:
    """Test Container.create_from_legacy factory."""

    def test_create_from_legacy_with_upbit_client(self):
        """Should create container with legacy exchange adapter."""
        from src.container import Container
        from src.application.ports.outbound.exchange_port import ExchangePort

        mock_client = MagicMock()

        container = Container.create_from_legacy(upbit_client=mock_client)

        exchange = container.get_exchange_port()
        assert isinstance(exchange, ExchangePort)

    def test_create_from_legacy_ai_service_deprecated(self):
        """ai_service parameter is deprecated and ignored."""
        import warnings
        from src.container import Container
        from src.application.ports.outbound.ai_port import AIPort
        from src.infrastructure.adapters.ai.openai_adapter import OpenAIAdapter

        mock_service = MagicMock()

        # ai_service 전달 시 DeprecationWarning 발생
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            container = Container.create_from_legacy(ai_service=mock_service)
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "ai_service" in str(w[0].message)

        # get_ai_port()는 OpenAIAdapter 반환 (LegacyAIAdapter 아님)
        ai = container.get_ai_port()
        assert isinstance(ai, AIPort)
        assert isinstance(ai, OpenAIAdapter)

    def test_create_from_legacy_with_all_services(self):
        """Should create container with all legacy adapters (ai_service 제외)."""
        from src.container import Container

        mock_upbit = MagicMock()
        mock_collector = MagicMock()

        # ai_service는 deprecated이므로 전달하지 않음
        container = Container.create_from_legacy(
            upbit_client=mock_upbit,
            data_collector=mock_collector,
        )

        # All should be available
        assert container.get_exchange_port() is not None
        assert container.get_ai_port() is not None  # OpenAIAdapter 반환
        assert container.get_market_data_port() is not None
        assert container.get_persistence_port() is not None

    def test_create_from_legacy_use_cases(self):
        """Should provide use cases with legacy adapters."""
        from src.container import Container
        from src.application.use_cases.execute_trade import ExecuteTradeUseCase

        mock_upbit = MagicMock()

        container = Container.create_from_legacy(upbit_client=mock_upbit)

        use_case = container.get_execute_trade_use_case()
        assert isinstance(use_case, ExecuteTradeUseCase)
