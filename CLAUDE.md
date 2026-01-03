# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Bitcoin AI automated trading bot that uses OpenAI GPT-4 for trading decisions. The system runs on a 1-hour interval schedule using APScheduler, executing trades on the Upbit exchange based on AI analysis of technical indicators and market data.

**Tech Stack**: Python 3.11, FastAPI, PostgreSQL, Docker, APScheduler, OpenAI GPT-4, TA-Lib

## Common Commands

### Environment Setup
```bash
# Activate virtual environment (venv)
# Windows PowerShell
.\venv\Scripts\Activate.ps1

# Windows CMD
venv\Scripts\activate.bat

# Linux/Mac
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
# requirements-api.txt가 requirements.txt에 통합됨
```

### Testing
```bash
# Run all tests (must be in venv)
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_module_name.py -v

# Run tests with coverage
python -m pytest tests/ --cov=src --cov=backend --cov-report=html

# Run only unit tests
python -m pytest tests/ -m unit -v

# Run only integration tests
python -m pytest tests/ -m integration -v

# Run scheduler tests
python -m pytest tests/backend/app/core/test_scheduler.py -v

# Run a single test
python -m pytest tests/test_module.py::TestClass::test_method -v
```

### Running the Bot

```bash
# Run trading cycle once (development)
python main.py

# Run scheduler (1-hour interval automated trading)
python scheduler_main.py

# Run with Docker (scheduler only)
docker-compose up -d scheduler
docker-compose logs -f scheduler

# Run full stack (DB, API, monitoring)
docker-compose up -d
```

### Docker Operations
```bash
# Build and run scheduler
docker-compose build scheduler
docker-compose up -d scheduler

# View logs
docker-compose logs -f scheduler

# Stop services
docker-compose down

# Clean rebuild
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### Database Operations
```bash
# The database is managed by Docker Compose
# PostgreSQL runs in a container with persistent volume
# Tables are auto-created via SQLAlchemy on first run

# Access PostgreSQL container
docker exec -it dg_bot-postgres-1 psql -U postgres -d trading_bot
```

## Architecture

### System Flow

The bot operates on a **dual-timeframe architecture**:

1. **Trading Job** (1시간): 멀티코인 스캔 + AI 분석 + 진입 탐색
2. **Position Management Job** (15분): 보유 포지션 손절/익절 관리
3. **Portfolio Snapshot Job** (1시간): 포트폴리오 스냅샷 저장
4. **Daily Report Job** (매일 09:00): 일일 리포트 Telegram 전송

**스케줄러 작업 구성:**
| 작업 | 주기 | 설명 |
|------|------|------|
| `trading_job` | 1시간 | `execute_trading_cycle()` → HybridTradingPipeline |
| `position_management_job` | 15분 | `execute_position_management_cycle()` → 규칙 기반 |
| `portfolio_snapshot_job` | 1시간 | DB 저장 |
| `daily_report_job` | 09:00 | Telegram |

**Key Flow** (Clean Architecture - 2026-01-02 마이그레이션 완료):
```
scheduler_main.py
  ├─ trading_job() [1시간]
  │   → execute_trading_cycle()
  │       → HybridTradingPipeline.execute()
  │           → HybridRiskCheckStage (포지션 확인 + 코인 스캔 + 백테스팅)
  │           → DataCollectionStage (데이터 수집)
  │           → AnalysisStage (AI 분석)
  │           → ExecutionStage (거래 실행)
  │
  └─ position_management_job() [15분]
      → execute_position_management_cycle()
          → PositionManagementPipeline.execute()
              → 규칙 기반 손절/익절 체크 (AI 호출 없음)
```

### Directory Structure

```
dg_bot/
├── main.py                    # Main trading cycle (standalone execution)
├── scheduler_main.py          # Scheduler entry point (automated mode)
├── src/
│   ├── container.py           # DI Container (Clean Architecture)
│   │
│   ├── domain/                # 🆕 Domain Layer (Pure Business Logic)
│   │   ├── entities/          # Trade, Order, Position entities
│   │   ├── value_objects/     # Money, Percentage value objects
│   │   ├── services/          # FeeCalculator, RiskCalculator
│   │   └── exceptions.py
│   │
│   ├── application/           # 🆕 Application Layer (Use Cases)
│   │   ├── ports/outbound/    # Port interfaces (ExchangePort, AIPort, etc.)
│   │   ├── use_cases/         # ExecuteTradeUseCase, AnalyzeMarketUseCase
│   │   └── dto/               # Data Transfer Objects
│   │
│   ├── infrastructure/        # 🆕 Infrastructure Layer (Adapters)
│   │   └── adapters/
│   │       ├── exchange/      # UpbitExchangeAdapter
│   │       ├── ai/            # OpenAIAdapter
│   │       ├── market_data/   # UpbitMarketDataAdapter
│   │       ├── persistence/   # InMemoryPersistenceAdapter
│   │       └── legacy_bridge.py  # Legacy service wrappers
│   │
│   ├── presentation/          # 🆕 Presentation Layer
│   │   └── cli/               # TradingRunner CLI
│   │
│   ├── ai/                    # AI decision making (GPT-4) - Legacy
│   │   ├── service.py         # AIService - main AI analysis
│   │   └── market_correlation.py
│   ├── api/                   # Exchange API clients - Legacy
│   │   └── upbit_client.py    # Upbit exchange integration
│   ├── backtesting/           # Backtesting engine
│   │   ├── backtester.py      # Main backtesting engine
│   │   ├── quick_filter.py    # Fast rule-based filtering
│   │   ├── rule_based_strategy.py  # Rule-based strategy
│   │   └── ai_strategy.py     # AI-based strategy
│   ├── data/                  # Data collection
│   │   └── collector.py       # Market data collector
│   ├── trading/               # Trading execution
│   │   ├── service.py         # TradingService - order execution
│   │   ├── indicators.py      # Technical indicators (RSI, MACD, etc.)
│   │   └── signal_analyzer.py # Signal analysis
│   ├── position/              # Position management
│   └── config/                # Configuration
│       └── settings.py        # All configuration classes
├── backend/                   # FastAPI backend + database
│   ├── app/
│   │   ├── main.py           # FastAPI application entry
│   │   ├── api/v1/           # REST API endpoints
│   │   │   └── endpoints/
│   │   │       ├── bot_control.py  # Bot control API
│   │   │       └── trades.py       # Trade history API
│   │   ├── core/
│   │   │   ├── config.py     # Backend settings
│   │   │   └── scheduler.py  # APScheduler configuration
│   │   ├── db/               # Database setup
│   │   │   ├── base.py       # SQLAlchemy base
│   │   │   ├── session.py    # DB session management
│   │   │   └── init_db.py    # DB initialization
│   │   ├── models/           # SQLAlchemy ORM models
│   │   │   ├── trade.py      # Trade records
│   │   │   ├── ai_decision.py # AI decision logs
│   │   │   ├── order.py      # Order records
│   │   │   ├── portfolio.py  # Portfolio snapshots
│   │   │   ├── bot_config.py # Bot configuration
│   │   │   └── system_log.py # System logs
│   │   ├── schemas/          # Pydantic schemas
│   │   └── services/
│   │       ├── trading_engine.py  # Trading logic integration
│   │       ├── notification.py    # Telegram notifications
│   │       └── metrics.py         # Prometheus metrics
│   └── tests/                # Backend tests
├── tests/                    # Main tests directory
├── scripts/backtesting/      # Data collection scripts
├── monitoring/               # Prometheus + Grafana configs
└── docs/                     # Documentation (ALL .md files go here)
```

### Key Components

#### Clean Architecture (권장)

**Container** (`src/container.py`):
- DI Container for dependency injection
- Factory methods: `create_from_legacy()`, `create_for_testing()`
- Provides UseCase instances with injected dependencies
- Ports: `get_idempotency_port()`, `get_lock_port()` (스케줄러 안정성)

**IdempotencyPort** (`src/application/ports/outbound/idempotency_port.py`):
- 중복 주문 방지를 위한 Idempotency Key 관리
- `make_idempotency_key(ticker, timeframe, candle_ts, action)` 헬퍼 함수
- PostgreSQL 어댑터: `idempotency_keys` 테이블 사용
- Methods: `check_key()`, `mark_key()`, `cleanup_expired()`

**LockPort** (`src/application/ports/outbound/lock_port.py`):
- 작업 간 상호 배제를 위한 분산 락
- PostgreSQL Advisory Lock 사용 (`LOCK_IDS`: trading_cycle=1001, position_management=1002)
- Methods: `acquire()`, `release()`, `is_locked()`, `lock()` (context manager)

**ExecuteTradeUseCase** (`src/application/use_cases/execute_trade.py`):
- 거래 실행 비즈니스 로직
- Money 값 객체로 정확한 금액 처리
- ExchangePort를 통한 주문 실행
- Methods: `execute_buy()`, `execute_sell()`, `execute_sell_all()`

**AnalyzeMarketUseCase** (`src/application/use_cases/analyze_market.py`):
- AI 분석 비즈니스 로직
- TradingDecision DTO 반환
- AIPort를 통한 AI 서비스 호출
- Methods: `analyze()`

**TradingPipeline** (`src/trading/pipeline/trading_pipeline.py`):
- Async 파이프라인으로 스테이지 순차 실행
- Container가 있으면 UseCase 사용, 없으면 레거시 서비스 사용
- Methods: `execute()`

#### Legacy (하위 호환성 - DEPRECATED)

**AIService** (`src/ai/service.py`) - DEPRECATED:
- Uses OpenAI GPT-4 for trading decisions
- ⚠️ Container.get_analyze_market_use_case() 사용 권장
- Methods: `analyze()`, `prepare_analysis_data()`

**TradingService** (`src/trading/service.py`) - DEPRECATED:
- Executes buy/sell orders via Upbit API
- ⚠️ Container.get_execute_trade_use_case() 사용 권장
- Methods: `buy()`, `sell()`, `calculate_fee()`, `calculate_slippage()`

#### Shared Components

**QuickBacktestFilter** (`src/backtesting/quick_filter.py`):
- Fast rule-based filtering WITHOUT AI calls
- Uses rule-based strategy to pre-filter trading opportunities
- Significantly reduces AI API costs

**Scheduler** (`backend/app/core/scheduler.py`):
- APScheduler with CronTrigger (캔들 마감 정렬)
- `trading_job()` [매시 01분]: 멀티코인 스캔 + AI 분석 + 진입 탐색 (Lock 적용)
- `position_management_job()` [:01,:16,:31,:46]: 보유 포지션 손절/익절 관리 (Lock 적용)
- `portfolio_snapshot_job()` [매시 01분]: 포트폴리오 스냅샷 DB 저장
- `daily_report_job()` [09:00]: 일일 리포트 Telegram 전송
- Lock/Idempotency로 중복 실행 및 중복 주문 방지
- 설정: `SchedulerConfig` (src/config/settings.py)

**Database Models** (`backend/app/models/`):
- `Trade`: Executed trades
- `AIDecision`: AI analysis logs
- `Order`: Order details
- `Portfolio`: Portfolio snapshots
- `IdempotencyKey`: 중복 주문 방지용 키 (TTL 기반 만료)
- All use SQLAlchemy ORM with async sessions

### Data Flow

1. **Data Collection**: `DataCollector` fetches OHLCV data from Upbit
2. **Technical Analysis**: `TechnicalIndicators` calculates RSI, MACD, Bollinger Bands
3. **Quick Filter**: `QuickBacktestFilter` applies rule-based strategy (no AI cost)
4. **Signal Analysis**: `SignalAnalyzer` analyzes buy/sell signals
5. **AI Decision**: `AIService` makes final decision via GPT-4
6. **Order Execution**: `TradingService` executes trade on Upbit
7. **Database Recording**: Models store trade, decision, and portfolio data
8. **Notifications**: Telegram alerts sent via `notification.py`
9. **Metrics**: Prometheus metrics recorded via `metrics.py`

### Clean Architecture (Hexagonal/Ports & Adapters)

The project implements Clean Architecture for better testability and maintainability:

```
Presentation → Application → Domain
      ↓              ↓
Infrastructure ─────┘
```

**Key Concepts**:
- **Domain Layer**: Pure business logic (Trade, Order, Position, Money, Percentage)
- **Application Layer**: Use cases and port interfaces (ExchangePort, AIPort, etc.)
- **Infrastructure Layer**: Adapters for external systems (Upbit, OpenAI, PostgreSQL)
- **Presentation Layer**: CLI runner and schedulers

**DI Container Usage**:
```python
from src.container import Container

# Production
container = Container()
execute_trade = container.get_execute_trade_use_case()

# Testing with mocks
container = Container.create_for_testing()

# Legacy service migration
container = Container.create_from_legacy(
    upbit_client=existing_upbit,
    ai_service=existing_ai
)
```

**Testing by Layer**:
```bash
# Domain layer only (no mocks needed)
python -m pytest tests/unit/domain/ -v

# Use cases (with port mocks)
python -m pytest tests/unit/application/ -v

# Adapters (integration tests)
python -m pytest tests/unit/infrastructure/ -v
```

## Development Guidelines

### ⚠️ TDD (Test-Driven Development) - 필수 준수사항

**이 프로젝트는 TDD를 엄격히 준수합니다. 모든 코드 작성 전 테스트를 먼저 작성해야 합니다.**

#### TDD 사이클 (Red-Green-Refactor)

1. **Red (실패하는 테스트 작성)**
   - 구현할 기능의 테스트를 먼저 작성
   - 테스트 실행하여 실패 확인 (반드시 실패해야 함)
   - 테스트가 명확한 요구사항을 정의해야 함

2. **Green (최소한의 코드로 테스트 통과)**
   - 테스트를 통과시키는 최소한의 코드만 작성
   - 완벽한 코드가 아니어도 됨 - 테스트만 통과하면 됨
   - `python -m pytest tests/해당_테스트.py -v` 로 확인

3. **Refactor (코드 개선)**
   - 테스트가 통과하는 상태에서 코드 품질 개선
   - 중복 제거, 가독성 향상, 성능 최적화
   - 리팩토링 후에도 모든 테스트 통과 확인

#### TDD 필수 체크리스트

```markdown
새 기능 개발 시:
[ ] 테스트 파일 생성 (tests/test_기능명.py)
[ ] 실패하는 테스트 작성
[ ] 테스트 실행하여 실패 확인
[ ] 최소 코드 작성하여 테스트 통과
[ ] 리팩토링 및 추가 테스트 케이스 작성
[ ] 전체 테스트 실행 (python -m pytest tests/ -v)

버그 수정 시:
[ ] 버그를 재현하는 테스트 작성
[ ] 테스트 실행하여 실패 확인 (버그 재현)
[ ] 버그 수정 코드 작성
[ ] 테스트 통과 확인
[ ] 회귀 테스트로 유지
```
#### 🧯 Test Debt Recovery Protocol

If any of the following occurs:
- Test coverage drops
- TDD is not followed during development
- Large refactors are required
- Confidence in changes degrades

You MUST follow:
- `.claude/skills/test-debt-recovery/TEST_DEBT_RECOVERY.md`

And record the recovery outcome in:
- `docs/CHANGELOG_TEST_DEBT.md`


#### 테스트 구조 (위험/행위 기반)

> **"테스트를 보면, 이 시스템이 어떤 위험을 막고 있는지 바로 알 수 있게 만들 것"**

```
tests/
├── contracts/              # ❗ 시스템 핵심 계약 (실패 시 → 거래 즉시 중단)
│   ├── test_idempotency.py      # 중복 주문 방지
│   ├── test_stop_loss.py        # 손절 보장
│   ├── test_fee_calculation.py  # 수수료 정확성
│   └── test_position_limit.py   # 포지션 제한
│
├── scenarios/              # 트레이더 관점 시나리오 (실패 시 → 배포 금지)
│   ├── test_entry_flow.py       # 진입 시나리오
│   ├── test_exit_flow.py        # 청산 시나리오
│   ├── test_hold_decision.py    # 홀드 결정
│   └── test_multi_coin_flow.py  # 멀티코인 스캔
│
├── scheduler/              # 운영 안정성 (실패 시 → 운영 중단)
│   ├── test_configuration.py    # 스케줄러 설정
│   ├── test_trading_job.py      # 트레이딩 작업
│   ├── test_lifecycle.py        # 스케줄러 생명주기
│   └── test_lock_mechanism.py   # Lock 메커니즘
│
├── backtesting/            # 백테스트 신뢰성 (실패 시 → 실거래 금지)
│   └── ...                      # 체결/비용 모델
│
├── unit/                   # 순수 로직 (클린 아키텍처 계층별)
│   ├── domain/                  # 도메인 계층
│   ├── application/             # 유스케이스
│   ├── infrastructure/          # 어댑터
│   └── presentation/            # CLI
│
├── integration/            # DB/외부 연동
│   └── adapters/
│
└── e2e/                    # 실제 운용 흐름
    └── test_paper_trading.py
```

#### 테스트 파일 생성 위치 가이드

| 테스트 유형 | 폴더 | 예시 |
|------------|------|------|
| 돈이 새는 지점 (수수료, 손절, 중복주문) | `contracts/` | `test_fee_calculation.py` |
| 트레이딩 비즈니스 흐름 | `scenarios/` | `test_entry_flow.py` |
| 스케줄러/운영 안정성 | `scheduler/` | `test_lock_mechanism.py` |
| 백테스트 로직 | `backtesting/` | `test_execution_model.py` |
| 순수 도메인 로직 (Money, Percentage) | `unit/domain/` | `test_money.py` |
| UseCase 비즈니스 로직 | `unit/application/` | `test_execute_trade.py` |
| 외부 시스템 어댑터 | `unit/infrastructure/` | `test_upbit_adapter.py` |
| DB/API 통합 테스트 | `integration/` | `test_postgres_adapter.py` |
| 전체 흐름 검증 | `e2e/` | `test_paper_trading.py` |

#### 테스트 마커

```python
@pytest.mark.contract       # 시스템 계약 테스트 (최우선)
@pytest.mark.scenario       # 비즈니스 시나리오 테스트
@pytest.mark.scheduler      # 스케줄러 테스트
@pytest.mark.unit           # 단위 테스트
@pytest.mark.integration    # 통합 테스트
@pytest.mark.e2e            # End-to-End 테스트
@pytest.mark.slow           # 느린 테스트
```

#### 테스트 실행 우선순위

```bash
# 1. 계약 테스트 (가장 먼저 실행 - 실패 시 즉시 중단)
python -m pytest tests/contracts/ -v --tb=short

# 2. 시나리오 테스트
python -m pytest tests/scenarios/ -v

# 3. 스케줄러 테스트
python -m pytest tests/scheduler/ -v

# 4. 전체 테스트
python -m pytest tests/ -v
```

#### Given-When-Then 패턴

```python
def test_buy_order_execution():
    # Given (준비)
    upbit_client = Mock()
    trading_service = TradingService(upbit_client)

    # When (실행)
    result = trading_service.buy("KRW-BTC", 100000)

    # Then (검증)
    assert result.success is True
    assert result.amount > 0
```

**⚠️ TDD 없이 작성된 코드는 리뷰에서 거절됩니다.**

### 📝 문서 업데이트 - 필수 준수사항

**모든 코드 변경 후에는 반드시 관련 문서를 업데이트해야 합니다.**

#### 문서 업데이트 체크리스트

```markdown
코드 변경 후:
[ ] 변경된 기능이 docs/에 반영되었는가?
[ ] ARCHITECTURE.md에 구조 변경이 반영되었는가?
[ ] 다이어그램(docs/diagrams/)이 최신 상태인가?
[ ] CLAUDE.md에 새 컴포넌트가 반영되었는가?
[ ] 관련 가이드 문서가 업데이트되었는가?
```

#### 문서 업데이트가 필요한 경우

1. **새 파일/모듈 추가**: ARCHITECTURE.md, CLAUDE.md 디렉토리 구조 업데이트
2. **파이프라인 스테이지 변경**: SCHEDULER_GUIDE.md, 다이어그램 업데이트
3. **스케줄러 작업 변경**: SCHEDULER_GUIDE.md 업데이트
4. **AI 프롬프트 변경**: AI 관련 문서 업데이트
5. **설정값 변경**: 관련 가이드 문서 업데이트
6. **API 변경**: API 문서 업데이트

#### ⚠️ 설정값 변경 시 필수 동기화 절차

**설정값(숫자, 비율, 개수 등)을 변경할 때 반드시 아래 절차를 따르세요:**

```bash
# 1. grep으로 해당 값의 모든 참조 확인
grep -r "변경할값\|관련키워드" --include="*.py" --include="*.md" --include="*.mmd"

# 2. 예시: liquidity_top_n을 20에서 10으로 변경할 때
grep -r "liquidity_top_n\|20개\|상위 20" --include="*.py" --include="*.md" --include="*.mmd"
```

**확인해야 할 위치:**

| 설정값 | 확인 파일 |
|--------|----------|
| `liquidity_top_n` | settings.py, main.py, trading_pipeline.py, coin_scan_stage.py, coin_selector.py, ARCHITECTURE.md, 08-multi-coin-scanning.mmd, test_coin_scan_stage.py, test_scanner_coin_selector.py |
| `backtest_top_n` | 동일 |
| `final_select_n` | 동일 |
| `stop_loss_pct` | settings.py, RISK_MANAGEMENT_CONFIG.md, ARCHITECTURE.md |
| `take_profit_pct` | 동일 |

**설정값의 단일 소스 (Single Source of Truth):**
- 모든 설정값은 `src/config/settings.py`에 정의되어야 합니다
- 각 Config 클래스에는 변경 시 업데이트해야 할 파일 목록이 주석으로 명시되어 있습니다
- 예: `ScannerConfig` 클래스 docstring 참조

```python
# src/config/settings.py에서 설정값 import
from src.config.settings import ScannerConfig

# 사용
liquidity_top_n = ScannerConfig.LIQUIDITY_TOP_N
```

**⚠️ 설정값 변경 후 grep 확인 없이 커밋하지 마세요.**

#### 문서 위치 규칙

```
docs/
├── guide/          # 사용자 가이드 (HOW-TO)
├── plans/          # 구현 계획 (PLAN_*.md)
├── diagrams/       # Mermaid 다이어그램 (.mmd)
└── reviews/        # 코드 리뷰 결과
```

**⚠️ 문서 업데이트 없이 PR/커밋하지 마세요.**

### Virtual Environment (venv)

**CRITICAL**: Always use venv for Python commands
- Location: `venv/` (project root)
- Activate before running any Python commands
- Never run Python commands outside venv

### File Organization Rules

From `.cursorrules`:

1. **Documentation**: ALL `.md` files MUST go in `docs/` (except root `README.md`, `CLAUDE.md`)
2. **Scripts**: Development scripts in project root, data scripts in `scripts/`
3. **Temporary Files**: Delete temporary test scripts after use

### Documentation Structure (IMPORTANT)

문서는 반드시 아래 구조를 따라야 합니다:

```
docs/
├── guide/                     # 가이드 문서 (사용법, 설정법)
│   ├── ARCHITECTURE.md        # 시스템 아키텍처
│   ├── DOCKER_GUIDE.md        # Docker 실행 가이드
│   ├── MONITORING_GUIDE.md    # Grafana/Prometheus 모니터링
│   ├── RISK_MANAGEMENT_CONFIG.md  # 리스크 관리 설정
│   ├── SCHEDULER_GUIDE.md     # 스케줄러 가이드
│   ├── TELEGRAM_SETUP_GUIDE.md    # Telegram 알림 설정
│   └── USER_GUIDE.md          # 사용자 가이드
├── plans/                     # 계획/체크리스트 문서
│   └── PLAN_*.md              # 구현 계획, 리팩토링 계획 등
└── diagrams/                  # 다이어그램 파일
```

**문서 관리 규칙**:
- 새 가이드 문서 → `docs/guide/`에 생성
- 구현 계획, 체크리스트 → `docs/plans/`에 생성
- 일회성 보고서 (리팩토링 보고서, 변경 로그 등) → 생성하지 않음
- 모든 문서는 `**작성일**: YYYY-MM-DD` 형식의 날짜 포함 필수
- 문서 수정 시 날짜 업데이트 필수

### Windows Encoding (PowerShell)

If running on Windows, PowerShell scripts need UTF-8 encoding setup:

```powershell
# Add to start of .ps1 files
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
```

Prefer `.bat` files over `.ps1` for Windows scripts when possible.

## Configuration

### Environment Variables

All configuration is in `.env` file (copy from `env.example`):

**Required**:
- `UPBIT_ACCESS_KEY`: Upbit API access key
- `UPBIT_SECRET_KEY`: Upbit API secret key
- `OPENAI_API_KEY`: OpenAI API key

**Optional but Recommended**:
- `TELEGRAM_BOT_TOKEN`: Telegram bot token
- `TELEGRAM_CHAT_ID`: Telegram chat ID
- `SENTRY_DSN`: Sentry error tracking DSN
- `POSTGRES_*`: Database configuration (for Docker)
- `PROMETHEUS_ENABLED`: Enable Prometheus metrics
- `GRAFANA_*`: Grafana configuration

### Configuration Classes

All in `src/config/settings.py`:
- `TradingConfig`: Trading parameters (fee rate, min trade, etc.)
- `AIConfig`: AI model settings (GPT-4, temperature, etc.)
- `DataConfig`: Data collection settings (intervals, counts)
- `BacktestConfig`: Backtesting parameters
- Backend config in `backend/app/core/config.py`

## Important Notes

### Trading Safety

1. **Start Small**: Test with minimal amounts first
2. **Monitor Closely**: Check logs and Telegram notifications
3. **API Key Security**: NEVER commit `.env` file
4. **Dry Run**: Use backtesting (`python backtest.py`) before live trading

### Scheduler Behavior

**듀얼 타임프레임 구조:**
- `trading_job`: 매 1시간 (진입 탐색)
- `position_management_job`: 매 15분 (포지션 관리)
- `portfolio_snapshot_job`: 매 1시간 (포트폴리오 스냅샷)
- `daily_report_job`: 매일 09:00 (일일 리포트)

**안정성:**
- `max_instances=1` prevents concurrent executions
- Graceful shutdown on SIGINT/SIGTERM
- Auto-recovery on errors (logs to Sentry if enabled)

### Database

- PostgreSQL required for production (via Docker)
- Tables auto-created on first run via SQLAlchemy
- Async sessions throughout backend
- Migrations not implemented (using declarative_base auto-create)

### AI Costs

- Each AI decision call costs money (GPT-4 API)
- `QuickBacktestFilter` reduces AI calls by pre-filtering with rules
- Monitor usage via OpenAI dashboard

### Backtesting

Two modes:
1. **Rule-based only**: No AI calls, fast and free
2. **AI-based**: Includes GPT-4 analysis, slower and costly

Use `scripts/backtesting/` for historical data collection.

## Common Issues

### Import Errors
- Ensure venv is activated
- Check `PYTHONPATH` includes project root
- `scheduler_main.py` adds project root to `sys.path`

### Database Connection
- Verify PostgreSQL is running (`docker-compose ps`)
- Check `DATABASE_URL` in `.env`
- Ensure async driver: `postgresql+asyncpg://...`

### API Errors
- Verify API keys in `.env`
- Check Upbit/OpenAI rate limits
- Review logs in `logs/` directory

### Scheduler Not Running
- Check `scheduler.log` in `logs/scheduler/`
- Verify no other instance is running
- Check system time (scheduler uses Asia/Seoul timezone)

## Useful References

- [User Guide](docs/guide/USER_GUIDE.md): Complete user documentation
- [Scheduler Guide](docs/guide/SCHEDULER_GUIDE.md): Scheduler detailed guide
- [Docker Guide](docs/guide/DOCKER_GUIDE.md): Docker setup and deployment
- [Architecture](docs/guide/ARCHITECTURE.md): System architecture details
- [Risk Management](docs/guide/RISK_MANAGEMENT_CONFIG.md): Risk management configuration
- [Monitoring Guide](docs/guide/MONITORING_GUIDE.md): Grafana/Prometheus setup
- [Telegram Setup](docs/guide/TELEGRAM_SETUP_GUIDE.md): Telegram notifications
