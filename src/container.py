"""
Dependency Injection Container.

This module provides a central container for wiring dependencies
following the Dependency Inversion Principle.

Usage:
    # Production
    container = Container()
    execute_trade = container.get_execute_trade_use_case()

    # Testing
    container = Container.create_for_testing()
    # or with custom mocks
    container = Container(exchange_port=mock_exchange)
"""
from typing import Optional

from src.application.ports.outbound.exchange_port import ExchangePort
from src.application.ports.outbound.ai_port import AIPort
from src.application.ports.outbound.market_data_port import MarketDataPort
from src.application.ports.outbound.persistence_port import PersistencePort
from src.application.use_cases.execute_trade import ExecuteTradeUseCase
from src.application.use_cases.analyze_market import AnalyzeMarketUseCase
from src.application.use_cases.manage_position import ManagePositionUseCase


class Container:
    """
    Dependency Injection Container.

    Manages the creation and wiring of application dependencies.
    Implements singleton pattern for port instances.
    """

    def __init__(
        self,
        exchange_port: Optional[ExchangePort] = None,
        ai_port: Optional[AIPort] = None,
        market_data_port: Optional[MarketDataPort] = None,
        persistence_port: Optional[PersistencePort] = None,
    ):
        """
        Initialize container with optional port overrides.

        Args:
            exchange_port: Exchange port implementation (uses default if None)
            ai_port: AI port implementation (uses default if None)
            market_data_port: Market data port implementation (uses default if None)
            persistence_port: Persistence port implementation (uses default if None)
        """
        self._exchange_port = exchange_port
        self._ai_port = ai_port
        self._market_data_port = market_data_port
        self._persistence_port = persistence_port

        # Cached use cases
        self._execute_trade_use_case: Optional[ExecuteTradeUseCase] = None
        self._analyze_market_use_case: Optional[AnalyzeMarketUseCase] = None
        self._manage_position_use_case: Optional[ManagePositionUseCase] = None

    @classmethod
    def create_for_testing(cls) -> "Container":
        """
        Create container with in-memory adapters for testing.

        Returns:
            Container with test adapters
        """
        from src.infrastructure.adapters.persistence.memory_adapter import InMemoryPersistenceAdapter
        from tests.unit.presentation.mock_adapters import (
            MockExchangeAdapter,
            MockAIAdapter,
            MockMarketDataAdapter,
        )

        return cls(
            exchange_port=MockExchangeAdapter(),
            ai_port=MockAIAdapter(),
            market_data_port=MockMarketDataAdapter(),
            persistence_port=InMemoryPersistenceAdapter(),
        )

    @classmethod
    def create_from_legacy(
        cls,
        upbit_client=None,
        ai_service=None,
        data_collector=None,
    ) -> "Container":
        """
        Create container by wrapping legacy services.

        This enables gradual migration from old code to new architecture.

        Args:
            upbit_client: Existing UpbitClient instance
            ai_service: Existing AIService instance
            data_collector: Existing DataCollector instance

        Returns:
            Container with legacy bridge adapters
        """
        from src.infrastructure.adapters.persistence.memory_adapter import InMemoryPersistenceAdapter

        exchange_port = None
        ai_port = None
        market_data_port = None

        if upbit_client:
            from src.infrastructure.adapters.legacy_bridge import LegacyExchangeAdapter
            exchange_port = LegacyExchangeAdapter(upbit_client)

        if ai_service:
            from src.infrastructure.adapters.legacy_bridge import LegacyAIAdapter
            ai_port = LegacyAIAdapter(ai_service)

        if data_collector:
            from src.infrastructure.adapters.legacy_bridge import LegacyMarketDataAdapter
            market_data_port = LegacyMarketDataAdapter(data_collector)

        return cls(
            exchange_port=exchange_port,
            ai_port=ai_port,
            market_data_port=market_data_port,
            persistence_port=InMemoryPersistenceAdapter(),
        )

    # --- Port Getters ---

    def get_exchange_port(self) -> ExchangePort:
        """Get exchange port implementation."""
        if self._exchange_port is None:
            from src.infrastructure.adapters.exchange.upbit_adapter import UpbitExchangeAdapter
            self._exchange_port = UpbitExchangeAdapter()
        return self._exchange_port

    def get_ai_port(self) -> AIPort:
        """Get AI port implementation."""
        if self._ai_port is None:
            from src.infrastructure.adapters.ai.openai_adapter import OpenAIAdapter
            self._ai_port = OpenAIAdapter()
        return self._ai_port

    def get_market_data_port(self) -> MarketDataPort:
        """Get market data port implementation."""
        if self._market_data_port is None:
            from src.infrastructure.adapters.market_data.upbit_data_adapter import UpbitMarketDataAdapter
            self._market_data_port = UpbitMarketDataAdapter()
        return self._market_data_port

    def get_persistence_port(self) -> PersistencePort:
        """Get persistence port implementation."""
        if self._persistence_port is None:
            from src.infrastructure.adapters.persistence.memory_adapter import InMemoryPersistenceAdapter
            self._persistence_port = InMemoryPersistenceAdapter()
        return self._persistence_port

    # --- Use Case Getters ---

    def get_execute_trade_use_case(self) -> ExecuteTradeUseCase:
        """Get ExecuteTradeUseCase with wired dependencies."""
        if self._execute_trade_use_case is None:
            self._execute_trade_use_case = ExecuteTradeUseCase(
                exchange=self.get_exchange_port(),
                persistence=self.get_persistence_port(),
            )
        return self._execute_trade_use_case

    def get_analyze_market_use_case(self) -> AnalyzeMarketUseCase:
        """Get AnalyzeMarketUseCase with wired dependencies."""
        if self._analyze_market_use_case is None:
            self._analyze_market_use_case = AnalyzeMarketUseCase(
                market_data=self.get_market_data_port(),
                ai=self.get_ai_port(),
            )
        return self._analyze_market_use_case

    def get_manage_position_use_case(self) -> ManagePositionUseCase:
        """Get ManagePositionUseCase with wired dependencies."""
        if self._manage_position_use_case is None:
            self._manage_position_use_case = ManagePositionUseCase(
                exchange=self.get_exchange_port(),
                persistence=self.get_persistence_port(),
            )
        return self._manage_position_use_case
