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
from src.application.ports.outbound.idempotency_port import IdempotencyPort
from src.application.ports.outbound.lock_port import LockPort
from src.application.ports.outbound.prompt_port import PromptPort
from src.application.ports.outbound.validation_port import ValidationPort
from src.application.ports.outbound.decision_record_port import DecisionRecordPort
from src.application.use_cases.execute_trade import ExecuteTradeUseCase
from src.application.use_cases.analyze_market import AnalyzeMarketUseCase
from src.application.use_cases.manage_position import ManagePositionUseCase
from src.application.use_cases.analyze_breakout import AnalyzeBreakoutUseCase


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
        idempotency_port: Optional[IdempotencyPort] = None,
        lock_port: Optional[LockPort] = None,
        prompt_port: Optional[PromptPort] = None,
        validation_port: Optional[ValidationPort] = None,
        decision_record_port: Optional[DecisionRecordPort] = None,
    ):
        """
        Initialize container with optional port overrides.

        Args:
            exchange_port: Exchange port implementation (uses default if None)
            ai_port: AI port implementation (uses default if None)
            market_data_port: Market data port implementation (uses default if None)
            persistence_port: Persistence port implementation (uses default if None)
            idempotency_port: Idempotency port implementation (uses default if None)
            lock_port: Lock port implementation (uses default if None)
            prompt_port: Prompt port implementation (uses default if None)
            validation_port: Validation port implementation (uses default if None)
            decision_record_port: Decision record port implementation (uses default if None)
        """
        self._exchange_port = exchange_port
        self._ai_port = ai_port
        self._market_data_port = market_data_port
        self._persistence_port = persistence_port
        self._idempotency_port = idempotency_port
        self._lock_port = lock_port
        self._prompt_port = prompt_port
        self._validation_port = validation_port
        self._decision_record_port = decision_record_port

        # Cached use cases
        self._execute_trade_use_case: Optional[ExecuteTradeUseCase] = None
        self._analyze_market_use_case: Optional[AnalyzeMarketUseCase] = None
        self._manage_position_use_case: Optional[ManagePositionUseCase] = None
        self._analyze_breakout_use_case: Optional[AnalyzeBreakoutUseCase] = None

    @classmethod
    def create_for_testing(cls) -> "Container":
        """
        Create container with in-memory adapters for testing.

        Returns:
            Container with test adapters
        """
        from src.infrastructure.adapters.persistence.memory_adapter import InMemoryPersistenceAdapter
        from src.infrastructure.adapters.persistence.memory_idempotency_adapter import InMemoryIdempotencyAdapter
        from src.infrastructure.adapters.persistence.memory_lock_adapter import InMemoryLockAdapter
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
            idempotency_port=InMemoryIdempotencyAdapter(),
            lock_port=InMemoryLockAdapter(),
        )

    @classmethod
    def create_from_legacy(
        cls,
        upbit_client=None,
        ai_service=None,
        data_collector=None,
        session_factory=None,
    ) -> "Container":
        """
        Create container by wrapping legacy services.

        This enables gradual migration from old code to new architecture.

        Args:
            upbit_client: Existing UpbitClient instance
            ai_service: Existing AIService instance
            data_collector: Existing DataCollector instance
            session_factory: SQLAlchemy async session factory (for PostgreSQL adapters)

        Returns:
            Container with legacy bridge adapters
        """
        from src.infrastructure.adapters.persistence.memory_adapter import InMemoryPersistenceAdapter
        from src.infrastructure.adapters.persistence.memory_idempotency_adapter import InMemoryIdempotencyAdapter
        from src.infrastructure.adapters.persistence.memory_lock_adapter import InMemoryLockAdapter

        exchange_port = None
        ai_port = None
        market_data_port = None
        idempotency_port = None
        lock_port = None
        decision_record_port = None

        if upbit_client:
            from src.infrastructure.adapters.legacy_bridge import LegacyExchangeAdapter
            exchange_port = LegacyExchangeAdapter(upbit_client)

        if ai_service:
            from src.infrastructure.adapters.legacy_bridge import LegacyAIAdapter
            ai_port = LegacyAIAdapter(ai_service)

        if data_collector:
            from src.infrastructure.adapters.legacy_bridge import LegacyMarketDataAdapter
            market_data_port = LegacyMarketDataAdapter(data_collector)

        # PostgreSQL adapters if session_factory is provided
        if session_factory:
            from src.infrastructure.adapters.persistence.postgres_idempotency_adapter import PostgresIdempotencyAdapter
            from src.infrastructure.adapters.persistence.postgres_lock_adapter import PostgresAdvisoryLockAdapter
            from src.infrastructure.adapters.persistence.decision_record_adapter import DecisionRecordAdapter
            idempotency_port = PostgresIdempotencyAdapter(session_factory)
            lock_port = PostgresAdvisoryLockAdapter(session_factory)
            decision_record_port = DecisionRecordAdapter(session_factory)
        else:
            # Fallback to in-memory adapters
            idempotency_port = InMemoryIdempotencyAdapter()
            lock_port = InMemoryLockAdapter()

        return cls(
            exchange_port=exchange_port,
            ai_port=ai_port,
            market_data_port=market_data_port,
            persistence_port=InMemoryPersistenceAdapter(),
            idempotency_port=idempotency_port,
            lock_port=lock_port,
            decision_record_port=decision_record_port,
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

    def get_idempotency_port(self) -> IdempotencyPort:
        """Get idempotency port implementation."""
        if self._idempotency_port is None:
            from src.infrastructure.adapters.persistence.memory_idempotency_adapter import InMemoryIdempotencyAdapter
            self._idempotency_port = InMemoryIdempotencyAdapter()
        return self._idempotency_port

    def get_lock_port(self) -> LockPort:
        """Get lock port implementation."""
        if self._lock_port is None:
            from src.infrastructure.adapters.persistence.memory_lock_adapter import InMemoryLockAdapter
            self._lock_port = InMemoryLockAdapter()
        return self._lock_port

    def get_prompt_port(self) -> PromptPort:
        """Get prompt port implementation."""
        if self._prompt_port is None:
            from src.infrastructure.adapters.prompt import YAMLPromptAdapter
            self._prompt_port = YAMLPromptAdapter()
        return self._prompt_port

    def get_validation_port(self) -> ValidationPort:
        """Get validation port implementation."""
        if self._validation_port is None:
            from src.infrastructure.adapters.validation import ValidationAdapter
            self._validation_port = ValidationAdapter()
        return self._validation_port

    def get_decision_record_port(self) -> DecisionRecordPort:
        """
        Get decision record port implementation.

        Note: Requires session_factory for production use.
        Returns None if not configured (use create_from_legacy with session_factory).
        """
        return self._decision_record_port

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

    def get_analyze_breakout_use_case(self) -> Optional[AnalyzeBreakoutUseCase]:
        """
        Get AnalyzeBreakoutUseCase with wired dependencies.

        Note: Requires decision_record_port (session_factory) for production use.
        Returns None if DecisionRecordPort is not configured.

        Returns:
            AnalyzeBreakoutUseCase or None if DecisionRecordPort is missing
        """
        if self._analyze_breakout_use_case is None:
            decision_record_port = self.get_decision_record_port()
            if decision_record_port is None:
                return None

            from src.infrastructure.adapters.ai import EnhancedOpenAIAdapter
            from src.config.settings import AIConfig

            # Create AI client with rate limiting and circuit breaker
            ai_client = EnhancedOpenAIAdapter(
                api_key=AIConfig.OPENAI_API_KEY,
                rate_limit_per_minute=AIConfig.RATE_LIMIT_PER_MINUTE,
                circuit_breaker_threshold=AIConfig.CIRCUIT_BREAKER_THRESHOLD,
                recovery_timeout=AIConfig.CIRCUIT_BREAKER_TIMEOUT,
            )

            self._analyze_breakout_use_case = AnalyzeBreakoutUseCase(
                prompt_port=self.get_prompt_port(),
                validation_port=self.get_validation_port(),
                decision_record_port=decision_record_port,
                ai_client=ai_client,
            )
        return self._analyze_breakout_use_case

    # --- Application Services ---

    def get_trading_orchestrator(self) -> "TradingOrchestrator":
        """
        Get TradingOrchestrator with this container.

        TradingOrchestrator는 Application Layer의 서비스로,
        거래 사이클의 비즈니스 로직을 조율합니다.

        Returns:
            TradingOrchestrator instance
        """
        from src.application.services.trading_orchestrator import TradingOrchestrator
        return TradingOrchestrator(container=self)
