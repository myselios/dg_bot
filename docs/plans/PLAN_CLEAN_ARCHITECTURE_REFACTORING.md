# Clean Architecture Refactoring Plan

**Project**: DG Trading Bot
**Created**: 2026-01-02
**Last Updated**: 2026-01-02
**Status**: Planning

---

**CRITICAL INSTRUCTIONS**: After completing each phase:
1. Check off completed task checkboxes
2. Run all quality gate validation commands
3. Verify ALL quality gate items pass
4. Update "Last Updated" date
5. Document learnings in Notes section
6. Only then proceed to next phase

DO NOT skip quality gates or proceed with failing checks

---

## Overview

### Objectives
- Transform current monolithic codebase into Clean Architecture (Hexagonal/Ports & Adapters)
- Enable easy testing through dependency inversion
- Improve maintainability and extensibility
- Prepare for multi-exchange and multi-AI support

### Current State
- Mixed responsibilities in large classes (AIService: 1300+ lines)
- Partial interface usage (IExchangeClient exists, but not consistently applied)
- Pipeline pattern exists but tightly coupled to implementations
- Backend (FastAPI) and core logic (src) partially separated

### Target State
```
Presentation → Application → Domain
      ↓              ↓
Infrastructure ─────┘
```

### Scope
- **Large Scope**: 7 phases, estimated 20-30 hours total
- **Risk Level**: Medium (existing tests provide safety net)

---

## Architecture Decisions

### ADR-001: Hexagonal Architecture (Ports & Adapters)
**Decision**: Adopt Hexagonal Architecture
**Rationale**:
- Clear separation between business logic and external systems
- Easy to swap implementations (exchange, AI, database)
- Improved testability through port interfaces
**Consequences**:
- More initial boilerplate
- Need to refactor existing interfaces

### ADR-002: Domain Layer Independence
**Decision**: Domain layer has zero external dependencies
**Rationale**:
- Pure business logic remains testable without mocks
- Domain entities are reusable across different adapters
**Consequences**:
- Some functionality needs to be pushed to infrastructure

### ADR-003: Keep Pipeline Pattern
**Decision**: Maintain existing pipeline orchestration
**Rationale**:
- Pipeline pattern works well for trading workflow
- Already tested and proven
**Consequences**:
- Pipelines will call use cases instead of services directly

---

## Phase Breakdown

### Phase 1: Domain Layer Foundation

**Goal**: Extract pure domain entities and business rules with zero external dependencies

**Test Strategy**:
- Unit tests only
- 100% coverage for domain layer
- No mocking required (pure logic)

**Test File Location**: `tests/unit/domain/`

#### Tasks

**RED Phase** (Write Failing Tests First):
- [ ] Write tests for `Trade` entity (`tests/unit/domain/entities/test_trade.py`)
- [ ] Write tests for `Order` entity
- [ ] Write tests for `Position` entity
- [ ] Write tests for `Money` value object (`tests/unit/domain/value_objects/test_money.py`)
- [ ] Write tests for `Percentage` value object
- [ ] Write tests for `FeeCalculator` domain service (`tests/unit/domain/services/test_fee_calculator.py`)
- [ ] Write tests for `RiskCalculator` domain service

**GREEN Phase** (Implement Minimal Code):
- [ ] Create `src/domain/__init__.py`
- [ ] Implement `src/domain/entities/trade.py` (Trade, Order, Position)
- [ ] Implement `src/domain/entities/market.py` (Candle, Orderbook, Ticker)
- [ ] Implement `src/domain/entities/signal.py` (TradingSignal, Indicator)
- [ ] Implement `src/domain/value_objects/money.py` (Money, Currency)
- [ ] Implement `src/domain/value_objects/percentage.py` (Percentage, Ratio)
- [ ] Implement `src/domain/services/fee_calculator.py`
- [ ] Implement `src/domain/services/risk_calculator.py`
- [ ] Implement `src/domain/exceptions.py`

**REFACTOR Phase**:
- [ ] Extract fee calculation logic from `TradingService`
- [ ] Extract risk calculation logic from existing code
- [ ] Ensure no external imports in domain layer

**Quality Gate**:
- [ ] All domain tests pass: `python -m pytest tests/unit/domain/ -v`
- [ ] No external imports in domain: `grep -r "^from src\." src/domain/ | grep -v domain`
- [ ] No infrastructure imports: `grep -r "import openai\|import pyupbit\|import sqlalchemy" src/domain/`
- [ ] Coverage >= 100%: `python -m pytest tests/unit/domain/ --cov=src/domain --cov-fail-under=100`

**Dependencies**: None

**Rollback Strategy**: Delete `src/domain/` directory

---

### Phase 2: Application Ports Definition

**Goal**: Define port interfaces for dependency inversion

**Test Strategy**:
- Mock-based unit tests for ports
- Verify interface compliance

**Test File Location**: `tests/unit/application/ports/`

#### Tasks

**RED Phase**:
- [ ] Write tests for `ExchangePort` interface
- [ ] Write tests for `AIPort` interface
- [ ] Write tests for `MarketDataPort` interface
- [ ] Write tests for `PersistencePort` interface

**GREEN Phase**:
- [ ] Create `src/application/__init__.py`
- [ ] Implement `src/application/ports/__init__.py`
- [ ] Implement `src/application/ports/outbound/exchange_port.py`
  ```python
  class ExchangePort(ABC):
      @abstractmethod
      def get_balance(self, currency: str) -> Money: ...
      @abstractmethod
      def execute_market_buy(self, ticker: str, amount: Money) -> Order: ...
      @abstractmethod
      def execute_market_sell(self, ticker: str, volume: Decimal) -> Order: ...
  ```
- [ ] Implement `src/application/ports/outbound/ai_port.py`
  ```python
  class AIPort(ABC):
      @abstractmethod
      def analyze(self, data: AnalysisData) -> TradingDecision: ...
  ```
- [ ] Implement `src/application/ports/outbound/market_data_port.py`
- [ ] Implement `src/application/ports/outbound/persistence_port.py`
- [ ] Implement `src/application/ports/inbound/trading_use_case.py`
- [ ] Implement `src/application/dto/` (AnalysisData, TradingDecision DTOs)

**REFACTOR Phase**:
- [ ] Extend existing `IExchangeClient` to new `ExchangePort`
- [ ] Ensure all ports use domain entities, not primitives

**Quality Gate**:
- [ ] All port tests pass
- [ ] All ports are abstract (ABC)
- [ ] All port methods have type hints using domain entities
- [ ] No implementation details in ports

**Dependencies**: Phase 1 (Domain Layer)

**Rollback Strategy**: Delete `src/application/` directory

---

### Phase 3: Infrastructure Adapters Migration

**Goal**: Implement adapters that fulfill port contracts

**Test Strategy**:
- Integration tests with mocked external APIs
- Adapter compliance tests

**Test File Location**: `tests/integration/adapters/`

#### Tasks

**RED Phase**:
- [ ] Write adapter compliance tests
- [ ] Write integration tests for `UpbitExchangeAdapter`
- [ ] Write integration tests for `OpenAIAdapter`

**GREEN Phase**:
- [ ] Create `src/infrastructure/__init__.py`
- [ ] Implement `src/infrastructure/adapters/exchange/upbit_adapter.py`
  - Wrap existing `UpbitClient`
  - Implement `ExchangePort` interface
  - Convert between Upbit responses and domain entities
- [ ] Implement `src/infrastructure/adapters/ai/openai_adapter.py`
  - Extract API call logic from `AIService`
  - Implement `AIPort` interface
- [ ] Implement `src/infrastructure/adapters/market_data/upbit_data_adapter.py`
  - Wrap existing `DataCollector`
- [ ] Implement `src/infrastructure/adapters/persistence/postgres_adapter.py`
  - Wrap existing SQLAlchemy models
- [ ] Implement `src/infrastructure/adapters/persistence/memory_adapter.py`
  - In-memory implementation for testing
- [ ] Move `src/trading/indicators.py` to `src/infrastructure/technical/indicators.py`
- [ ] Move `src/config/settings.py` to `src/infrastructure/config/settings.py`

**REFACTOR Phase**:
- [ ] Update existing code to use adapters through ports
- [ ] Ensure backward compatibility during migration

**Quality Gate**:
- [ ] All adapter tests pass
- [ ] All adapters implement correct ports
- [ ] Existing functionality preserved: `python -m pytest tests/ -v`
- [ ] No direct external API calls outside adapters

**Dependencies**: Phase 2 (Ports)

**Rollback Strategy**: Keep original classes, remove adapter layer

---

### Phase 4: Use Cases Implementation

**Goal**: Implement business use cases with injected dependencies

**Test Strategy**:
- Unit tests with mock adapters
- Focus on business logic correctness

**Test File Location**: `tests/unit/application/use_cases/`

#### Tasks

**RED Phase**:
- [ ] Write tests for `ExecuteTradeUseCase`
- [ ] Write tests for `AnalyzeMarketUseCase`
- [ ] Write tests for `ManagePositionUseCase`
- [ ] Write tests for `RunBacktestUseCase`

**GREEN Phase**:
- [ ] Implement `src/application/use_cases/__init__.py`
- [ ] Implement `src/application/use_cases/execute_trade.py`
  ```python
  class ExecuteTradeUseCase:
      def __init__(self, exchange: ExchangePort, persistence: PersistencePort):
          self.exchange = exchange
          self.persistence = persistence

      def execute_buy(self, ticker: str, amount: Money) -> TradeResult:
          # Business logic here
          pass
  ```
- [ ] Implement `src/application/use_cases/analyze_market.py`
  - Extract analysis logic from `AIService.prepare_analysis_data`
  - Coordinate between data port and AI port
- [ ] Implement `src/application/use_cases/manage_position.py`
  - Position tracking, P&L calculation
- [ ] Implement `src/application/use_cases/run_backtest.py`
  - Extract from existing backtesting module

**REFACTOR Phase**:
- [ ] Update pipeline stages to call use cases
- [ ] Remove business logic from infrastructure adapters

**Quality Gate**:
- [ ] All use case tests pass with 80% coverage
- [ ] Use cases only depend on ports, not concrete implementations
- [ ] Single Responsibility: each use case does one thing

**Dependencies**: Phase 3 (Adapters)

**Rollback Strategy**: Keep pipeline stages calling services directly

---

### Phase 5: Presentation Layer Consolidation

**Goal**: Unify API, CLI, and scheduler under presentation layer

**Test Strategy**:
- E2E tests for API endpoints
- Integration tests for scheduler

**Test File Location**: `tests/e2e/`

#### Tasks

**RED Phase**:
- [ ] Write E2E tests for trading API
- [ ] Write tests for scheduler job execution

**GREEN Phase**:
- [ ] Create `src/presentation/__init__.py`
- [ ] Move `backend/app/api/` to `src/presentation/api/`
- [ ] Implement `src/presentation/cli/main.py`
  - Refactor `main.py` to use dependency injection
- [ ] Implement `src/presentation/scheduler/trading_scheduler.py`
  - Refactor `scheduler_main.py`
- [ ] Implement DI container (`src/container.py`)
  ```python
  class Container:
      def __init__(self, config: Config):
          self.exchange = UpbitExchangeAdapter(config)
          self.ai = OpenAIAdapter(config)
          # ... wire up dependencies

      def get_execute_trade_use_case(self) -> ExecuteTradeUseCase:
          return ExecuteTradeUseCase(self.exchange, self.persistence)
  ```

**REFACTOR Phase**:
- [ ] Remove duplicate entry points
- [ ] Ensure all presentation code only calls use cases

**Quality Gate**:
- [ ] All E2E tests pass
- [ ] Single container wires all dependencies
- [ ] No business logic in presentation layer

**Dependencies**: Phase 4 (Use Cases)

**Rollback Strategy**: Keep original `main.py` and `scheduler_main.py`

---

### Phase 6: Legacy Migration

**Goal**: Remove old code structure and finalize migration

**Test Strategy**:
- Full regression test suite
- Compare behavior before/after

**Test File Location**: `tests/`

#### Tasks

**Migration Tasks**:
- [ ] Replace `src/trading/service.py` usage with `ExecuteTradeUseCase`
- [ ] Replace `src/ai/service.py` with `AnalyzeMarketUseCase` + `OpenAIAdapter`
- [ ] Consolidate `backend/` into `src/presentation/api/`
- [ ] Update pipeline stages to be orchestrators only
- [ ] Remove deprecated code paths

**Cleanup Tasks**:
- [ ] Delete unused files from old structure
- [ ] Update all import statements
- [ ] Fix circular dependency issues if any
- [ ] Update `requirements.txt` if needed

**Quality Gate**:
- [ ] All existing tests pass: `python -m pytest tests/ -v`
- [ ] No deprecated imports remain
- [ ] Application runs successfully: `python main.py`
- [ ] Scheduler runs successfully: `python scheduler_main.py`

**Dependencies**: Phase 5 (Presentation)

**Rollback Strategy**: Git revert to pre-migration commit

---

### Phase 7: Documentation and Final Validation

**Goal**: Document architecture and ensure quality

**Test Strategy**:
- Code coverage analysis
- Performance benchmarking

#### Tasks

**Documentation**:
- [ ] Update `docs/ARCHITECTURE.md` with new structure
- [ ] Create dependency diagram (ASCII or Mermaid)
- [ ] Document each layer's responsibilities
- [ ] Update `CLAUDE.md` with new conventions
- [ ] Add ADR (Architecture Decision Records) to docs

**Validation**:
- [ ] Run full test suite with coverage
- [ ] Verify coverage >= 80%: `python -m pytest tests/ --cov=src --cov-fail-under=80`
- [ ] Performance test: compare execution time with baseline
- [ ] Code review: check for SRP, DIP violations

**Final Cleanup**:
- [ ] Remove any remaining TODO comments
- [ ] Ensure consistent code style
- [ ] Update README with new project structure

**Quality Gate**:
- [ ] All documentation complete
- [ ] Test coverage >= 80%
- [ ] No performance regression (< 10% slower)
- [ ] All ADRs documented

**Dependencies**: Phase 6 (Migration)

**Rollback Strategy**: N/A (documentation only)

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Breaking existing functionality | Medium | High | Comprehensive test coverage, incremental migration |
| Circular dependencies | Medium | Medium | Strict layer boundaries, dependency direction checks |
| Performance degradation | Low | Medium | Benchmark before/after, optimize if needed |
| Extended timeline | Medium | Low | Phase-based approach allows partial completion |
| Learning curve for team | Low | Low | Clear documentation, consistent patterns |

---

## Progress Tracking

### Current Phase: Phase 1 - Domain Layer Foundation

### Completed Phases
- [x] Planning and Design

### Phase Status

| Phase | Status | Started | Completed |
|-------|--------|---------|-----------|
| 1. Domain Layer | Not Started | - | - |
| 2. Application Ports | Not Started | - | - |
| 3. Infrastructure Adapters | Not Started | - | - |
| 4. Use Cases | Not Started | - | - |
| 5. Presentation Layer | Not Started | - | - |
| 6. Legacy Migration | Not Started | - | - |
| 7. Documentation | Not Started | - | - |

---

## Notes & Learnings

### Planning Phase
- Existing `IExchangeClient` provides good foundation for port pattern
- Pipeline pattern should be preserved as orchestration layer
- `AIService` is the largest refactoring target (1300+ lines)

### Phase 1
_To be filled during implementation_

### Phase 2
_To be filled during implementation_

---

## Appendix

### File Mapping (Old → New)

| Old Location | New Location |
|-------------|--------------|
| `src/trading/service.py` | `src/application/use_cases/execute_trade.py` |
| `src/ai/service.py` | `src/infrastructure/adapters/ai/openai_adapter.py` + `src/application/use_cases/analyze_market.py` |
| `src/api/upbit_client.py` | `src/infrastructure/adapters/exchange/upbit_adapter.py` |
| `src/api/interfaces.py` | `src/application/ports/outbound/exchange_port.py` |
| `src/data/collector.py` | `src/infrastructure/adapters/market_data/upbit_data_adapter.py` |
| `backend/app/api/` | `src/presentation/api/` |
| `backend/app/models/` | `src/infrastructure/adapters/persistence/` |
| `main.py` | `src/presentation/cli/main.py` |
| `scheduler_main.py` | `src/presentation/scheduler/trading_scheduler.py` |

### Target Directory Structure

```
src/
├── domain/                    # Pure business logic
│   ├── entities/
│   │   ├── trade.py
│   │   ├── market.py
│   │   ├── signal.py
│   │   └── portfolio.py
│   ├── value_objects/
│   │   ├── money.py
│   │   └── percentage.py
│   ├── services/
│   │   ├── fee_calculator.py
│   │   └── risk_calculator.py
│   └── exceptions.py
├── application/               # Use cases and ports
│   ├── ports/
│   │   ├── inbound/
│   │   │   └── trading_use_case.py
│   │   └── outbound/
│   │       ├── exchange_port.py
│   │       ├── ai_port.py
│   │       ├── market_data_port.py
│   │       └── persistence_port.py
│   ├── use_cases/
│   │   ├── execute_trade.py
│   │   ├── analyze_market.py
│   │   ├── manage_position.py
│   │   └── run_backtest.py
│   └── dto/
├── infrastructure/            # External system adapters
│   ├── adapters/
│   │   ├── exchange/
│   │   │   └── upbit_adapter.py
│   │   ├── ai/
│   │   │   └── openai_adapter.py
│   │   ├── market_data/
│   │   │   └── upbit_data_adapter.py
│   │   └── persistence/
│   │       ├── postgres_adapter.py
│   │       └── memory_adapter.py
│   ├── technical/
│   │   └── indicators.py
│   └── config/
│       └── settings.py
├── presentation/              # UI/API layer
│   ├── api/
│   │   └── v1/
│   ├── cli/
│   │   └── main.py
│   └── scheduler/
│       └── trading_scheduler.py
├── shared/                    # Shared utilities
│   ├── logger.py
│   └── helpers.py
└── container.py               # Dependency injection
```
