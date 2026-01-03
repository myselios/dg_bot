"""
Tests for Dependency Injection Container.

RED Phase: These tests define the expected behavior of the DI container.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestContainer:
    """Test DI Container creation and dependency wiring."""

    def test_container_creation(self):
        """Container should be creatable with config."""
        from src.container import Container

        container = Container()
        assert container is not None

    def test_container_provides_exchange_port(self):
        """Container should provide ExchangePort implementation."""
        from src.container import Container
        from src.application.ports.outbound.exchange_port import ExchangePort

        container = Container()
        exchange = container.get_exchange_port()

        assert exchange is not None
        assert isinstance(exchange, ExchangePort)

    def test_container_provides_ai_port(self):
        """Container should provide AIPort implementation."""
        from src.container import Container
        from src.application.ports.outbound.ai_port import AIPort

        container = Container()
        ai = container.get_ai_port()

        assert ai is not None
        assert isinstance(ai, AIPort)

    def test_container_provides_market_data_port(self):
        """Container should provide MarketDataPort implementation."""
        from src.container import Container
        from src.application.ports.outbound.market_data_port import MarketDataPort

        container = Container()
        market_data = container.get_market_data_port()

        assert market_data is not None
        assert isinstance(market_data, MarketDataPort)

    def test_container_provides_persistence_port(self):
        """Container should provide PersistencePort implementation."""
        from src.container import Container
        from src.application.ports.outbound.persistence_port import PersistencePort

        container = Container()
        persistence = container.get_persistence_port()

        assert persistence is not None
        assert isinstance(persistence, PersistencePort)

    def test_container_provides_execute_trade_use_case(self):
        """Container should provide ExecuteTradeUseCase with dependencies."""
        from src.container import Container
        from src.application.use_cases.execute_trade import ExecuteTradeUseCase

        container = Container()
        use_case = container.get_execute_trade_use_case()

        assert use_case is not None
        assert isinstance(use_case, ExecuteTradeUseCase)

    def test_container_provides_analyze_market_use_case(self):
        """Container should provide AnalyzeMarketUseCase with dependencies."""
        from src.container import Container
        from src.application.use_cases.analyze_market import AnalyzeMarketUseCase

        container = Container()
        use_case = container.get_analyze_market_use_case()

        assert use_case is not None
        assert isinstance(use_case, AnalyzeMarketUseCase)

    def test_container_provides_manage_position_use_case(self):
        """Container should provide ManagePositionUseCase with dependencies."""
        from src.container import Container
        from src.application.use_cases.manage_position import ManagePositionUseCase

        container = Container()
        use_case = container.get_manage_position_use_case()

        assert use_case is not None
        assert isinstance(use_case, ManagePositionUseCase)

    def test_container_singleton_ports(self):
        """Container should return same port instances (singleton pattern)."""
        from src.container import Container

        container = Container()

        exchange1 = container.get_exchange_port()
        exchange2 = container.get_exchange_port()

        assert exchange1 is exchange2

    def test_container_use_case_gets_correct_dependencies(self):
        """Use cases should receive correct port implementations."""
        from src.container import Container

        container = Container()

        execute_trade = container.get_execute_trade_use_case()

        # Use case should have exchange and persistence ports
        assert hasattr(execute_trade, 'exchange')
        assert hasattr(execute_trade, 'persistence')


class TestContainerWithMocks:
    """Test Container with mock adapters for testing."""

    def test_container_accepts_mock_adapters(self):
        """Container should accept mock adapters for testing."""
        from src.container import Container
        from src.application.ports.outbound.exchange_port import ExchangePort

        mock_exchange = MagicMock(spec=ExchangePort)

        container = Container(exchange_port=mock_exchange)

        assert container.get_exchange_port() is mock_exchange

    def test_container_test_mode(self):
        """Container should have test mode with in-memory adapters."""
        from src.container import Container

        container = Container.create_for_testing()

        # Should not raise and provide all ports
        assert container.get_exchange_port() is not None
        assert container.get_ai_port() is not None
        assert container.get_market_data_port() is not None
        assert container.get_persistence_port() is not None

    def test_container_all_ports_injectable(self):
        """All ports should be injectable for testing."""
        from src.container import Container
        from src.application.ports.outbound.exchange_port import ExchangePort
        from src.application.ports.outbound.ai_port import AIPort
        from src.application.ports.outbound.market_data_port import MarketDataPort
        from src.application.ports.outbound.persistence_port import PersistencePort

        mock_exchange = MagicMock(spec=ExchangePort)
        mock_ai = MagicMock(spec=AIPort)
        mock_market_data = MagicMock(spec=MarketDataPort)
        mock_persistence = MagicMock(spec=PersistencePort)

        container = Container(
            exchange_port=mock_exchange,
            ai_port=mock_ai,
            market_data_port=mock_market_data,
            persistence_port=mock_persistence,
        )

        assert container.get_exchange_port() is mock_exchange
        assert container.get_ai_port() is mock_ai
        assert container.get_market_data_port() is mock_market_data
        assert container.get_persistence_port() is mock_persistence


class TestContainerPersistenceSelection:
    """Test Container selects correct PersistencePort based on session_factory."""

    def test_container_uses_inmemory_without_session_factory(self):
        """Without session_factory, Container should use InMemoryPersistenceAdapter."""
        from src.container import Container
        from src.infrastructure.adapters.persistence.memory_adapter import InMemoryPersistenceAdapter

        container = Container()  # No session_factory
        persistence = container.get_persistence_port()

        assert isinstance(persistence, InMemoryPersistenceAdapter)

    def test_container_uses_postgres_with_session_factory(self):
        """With session_factory, Container should use PostgresPersistenceAdapter."""
        from src.container import Container
        from src.infrastructure.adapters.persistence.postgres_persistence_adapter import PostgresPersistenceAdapter

        mock_session_factory = MagicMock()

        container = Container(session_factory=mock_session_factory)
        persistence = container.get_persistence_port()

        assert isinstance(persistence, PostgresPersistenceAdapter)

    def test_create_from_legacy_uses_postgres_with_session_factory(self):
        """create_from_legacy should use PostgresPersistenceAdapter when session_factory is provided."""
        from src.container import Container
        from src.infrastructure.adapters.persistence.postgres_persistence_adapter import PostgresPersistenceAdapter

        mock_session_factory = MagicMock()

        container = Container.create_from_legacy(session_factory=mock_session_factory)
        persistence = container.get_persistence_port()

        assert isinstance(persistence, PostgresPersistenceAdapter)

    def test_create_from_legacy_uses_inmemory_without_session_factory(self):
        """create_from_legacy should use InMemoryPersistenceAdapter without session_factory."""
        from src.container import Container
        from src.infrastructure.adapters.persistence.memory_adapter import InMemoryPersistenceAdapter

        container = Container.create_from_legacy()  # No session_factory
        persistence = container.get_persistence_port()

        assert isinstance(persistence, InMemoryPersistenceAdapter)


class TestContainerExecutionPort:
    """Test Container.get_execution_port() for live/backtest mode selection."""

    def test_get_execution_port_live_mode_returns_live_adapter(self):
        """Live mode should return LiveExecutionAdapter."""
        from src.container import Container
        from src.infrastructure.adapters.execution.live_execution_adapter import LiveExecutionAdapter

        container = Container()
        execution_port = container.get_execution_port(mode="live")

        assert isinstance(execution_port, LiveExecutionAdapter)

    def test_get_execution_port_backtest_mode_returns_intrabar_adapter(self):
        """Backtest mode should return IntrabarExecutionAdapter."""
        from src.container import Container
        from src.infrastructure.adapters.execution.intrabar_execution_adapter import IntrabarExecutionAdapter

        container = Container()
        execution_port = container.get_execution_port(mode="backtest")

        assert isinstance(execution_port, IntrabarExecutionAdapter)

    def test_get_execution_port_invalid_mode_raises_error(self):
        """Invalid mode should raise ValueError."""
        from src.container import Container
        import pytest

        container = Container()

        with pytest.raises(ValueError) as exc_info:
            container.get_execution_port(mode="invalid")

        assert "Unknown execution mode" in str(exc_info.value)

    def test_get_execution_port_default_is_live(self):
        """Default mode should be 'live'."""
        from src.container import Container
        from src.infrastructure.adapters.execution.live_execution_adapter import LiveExecutionAdapter

        container = Container()
        execution_port = container.get_execution_port()  # No mode specified

        assert isinstance(execution_port, LiveExecutionAdapter)

    def test_live_adapter_has_exchange_port(self):
        """LiveExecutionAdapter should have access to ExchangePort."""
        from src.container import Container

        container = Container()
        execution_port = container.get_execution_port(mode="live")

        # LiveExecutionAdapter stores exchange_port as _exchange
        assert hasattr(execution_port, '_exchange')
        assert execution_port._exchange is not None
