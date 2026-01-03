# 클린 아키텍처 완전 마이그레이션 계획

**작성일**: 2026-01-03
**상태**: ✅ COMPLETED
**스코프**: Large (7 Phases, 30-35시간)
**Last Updated**: 2026-01-03 (전체 완료)

---

## ⚠️ CRITICAL INSTRUCTIONS

이 계획을 실행할 때 반드시 따라야 하는 규칙:

1. ✅ 각 Phase 완료 후 체크박스 업데이트
2. 🧪 모든 Quality Gate 검증 명령어 실행
3. ⚠️ Quality Gate 항목 전부 통과 확인
4. 📅 "Last Updated" 날짜 업데이트
5. 📝 Notes 섹션에 학습 내용 기록
6. ➡️ 그 후에만 다음 Phase로 진행

⛔ **Quality Gate 스킵 또는 실패 상태로 진행 금지**

---

## 목차

1. [개요](#1-개요)
2. [현재 상태 분석](#2-현재-상태-분석)
3. [목표 아키텍처](#3-목표-아키텍처)
4. [Phase 상세](#4-phase-상세)
5. [리스크 평가](#5-리스크-평가)
6. [롤백 전략](#6-롤백-전략)
7. [진행 상황](#7-진행-상황)
8. [Notes & Learnings](#8-notes--learnings)

---

## 1. 개요

### 1.1 목표

마스터 플랜(PR-1 ~ PR-6)의 핵심 3개 PR을 완료하고, 레거시 코드를 완전히 삭제하여 클린 아키텍처 기반으로만 동작하는 기관급 트레이딩 시스템 구축

### 1.2 범위

| 항목 | 범위 |
|------|------|
| PR-1 Idempotency | Pipeline 통합 (Infrastructure 완성됨) |
| PR-2 Execution Engine | LiveExecutionAdapter + Pipeline 통합 |
| PR-3 Persistence | PostgresAdapter 구현 + 기본값 변경 |
| 레거시 삭제 | AIService, TradingService, 직접 UpbitClient 완전 제거 |

### 1.3 퀀트 관점 필수 요구사항

```
✅ 중복 주문: 동일 캔들/액션은 절대 1회만 실행
✅ 상태 일관성: 프로세스 재시작 후 Position/Risk/Decision 복구
✅ 백테스트-라이브 일치: 동일 시그널 → 동일 체결 로직
✅ 감사 추적: 모든 Trade/Decision/Order DB 저장 및 조회 가능
```

---

## 2. 현재 상태 분석

### 2.1 클린 아키텍처 계층별 완성도

| 계층 | 현재 | 목표 | Gap |
|------|------|------|-----|
| Domain Layer | 95% | 100% | 도메인 이벤트 (선택) |
| Application Layer | 90% | 100% | Idempotency/Execution 통합 |
| Infrastructure Layer | 88% | 100% | PostgresAdapter |
| Presentation Layer | 80% | 100% | Container 통합 |
| **전체** | **85%** | **100%** | **15%** |

### 2.2 PR 구현 현황

| PR | Infrastructure | Pipeline 통합 | 테스트 |
|---|---|---|---|
| PR-1 Idempotency | ✅ 100% | ❌ 0% | ✅ 있음 |
| PR-2 Execution | ✅ 70% | ❌ 10% | ✅ 있음 |
| PR-3 Persistence | ⚠️ 50% | ❌ 0% | ❌ 없음 |

### 2.3 레거시 코드 사용처

| 파일 | 레거시 직접 생성 | 제거 대상 |
|------|-----------------|----------|
| telegram_bot.py | UpbitClient, AIService, TradingService, DataCollector | 전체 |
| main.py | UpbitClient, AIService, TradingService, DataCollector | 전체 |
| scheduler.py | UpbitClient, AIService, DataCollector | 부분 (이미 Container 사용) |

---

## 3. 목표 아키텍처

### 3.1 최종 의존성 구조

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ scheduler.py │  │   main.py    │  │telegram_bot.py│      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │                 │                 │                │
│         └────────────────┬┴─────────────────┘                │
│                          ▼                                   │
│                  ┌───────────────┐                           │
│                  │   Container   │ ← Single Source of Truth  │
│                  └───────┬───────┘                           │
└──────────────────────────┼──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              TradingOrchestrator                     │    │
│  │  ├─ HybridTradingPipeline                           │    │
│  │  │   ├─ IdempotencyCheck (PR-1) ← NEW               │    │
│  │  │   ├─ HybridRiskCheckStage                        │    │
│  │  │   ├─ DataCollectionStage                         │    │
│  │  │   ├─ AnalysisStage                               │    │
│  │  │   └─ ExecutionStage (PR-2) ← UPDATED             │    │
│  │  └─ PositionManagementPipeline                      │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                   Use Cases                          │    │
│  │  ExecuteTradeUseCase  │  AnalyzeMarketUseCase       │    │
│  │  ManagePositionUseCase│  AnalyzeBreakoutUseCase     │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    Ports                             │    │
│  │  IdempotencyPort │ LockPort │ PersistencePort       │    │
│  │  ExchangePort    │ AIPort   │ ExecutionPort         │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────┼──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Infrastructure Layer                       │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                Production Adapters                   │    │
│  │  PostgresIdempotencyAdapter (PR-1)                  │    │
│  │  PostgresPersistenceAdapter (PR-3) ← NEW            │    │
│  │  PostgresAdvisoryLockAdapter                        │    │
│  │  UpbitExchangeAdapter                               │    │
│  │  EnhancedOpenAIAdapter                              │    │
│  │  LiveExecutionAdapter (PR-2) ← NEW                  │    │
│  │  IntrabarExecutionAdapter (Backtest)                │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │            Test-Only Adapters (Dev/Test)             │    │
│  │  InMemoryPersistenceAdapter                         │    │
│  │  InMemoryIdempotencyAdapter                         │    │
│  │  InMemoryLockAdapter                                │    │
│  │  MockExchangeAdapter                                │    │
│  │  MockAIAdapter                                      │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 삭제 대상 레거시 코드

```
❌ 완전 삭제:
├─ src/ai/service.py (AIService) → Container.get_ai_port()
├─ src/trading/service.py (TradingService) → Container.get_execute_trade_use_case()
├─ 직접 UpbitClient() 생성 → Container.get_exchange_port()
└─ 직접 DataCollector() 생성 → Container.get_market_data_port()

⚠️ 유지 (Adapter 내부):
├─ src/api/upbit_client.py → UpbitExchangeAdapter에서 래핑
├─ src/data/collector.py → UpbitMarketDataAdapter에서 래핑
└─ infrastructure/adapters/legacy_bridge.py → 마이그레이션 유틸
```

---

## 4. Phase 상세

---

### Phase 1: PR-1 Idempotency Pipeline 통합

**목표**: 모든 거래에 중복 주문 방지 적용

**예상 시간**: 2시간

**의존성**: 없음 (Infrastructure 이미 완성)

#### 테스트 전략

- **테스트 파일**: `tests/unit/application/test_idempotency_integration.py`
- **커버리지 목표**: 95%
- **Mock 대상**: IdempotencyPort

#### 테스트 시나리오

```python
# RED Phase - 실패하는 테스트 먼저 작성
1. test_trading_cycle_checks_idempotency_before_execution
2. test_duplicate_candle_action_rejected
3. test_different_candle_action_allowed
4. test_idempotency_failure_blocks_trading (Fail-close)
5. test_idempotency_key_format_correct
```

#### 작업 항목

**RED (테스트 작성)**:
- [ ] `test_idempotency_integration.py` 생성
- [ ] 5개 테스트 시나리오 작성
- [ ] 테스트 실행 → 실패 확인

**GREEN (구현)**:
- [ ] `TradingOrchestrator.execute_trading_cycle()` 진입부에 idempotency 체크 추가
- [ ] `make_idempotency_key()` 호출 로직 추가
- [ ] Fail-close 정책 구현 (DB 오류 시 거래 중단)
- [ ] 테스트 통과 확인

**REFACTOR**:
- [ ] 중복 코드 제거
- [ ] 로깅 추가
- [ ] 전체 테스트 재실행

#### Quality Gate

```bash
# 빌드 & 테스트
python -m pytest tests/unit/application/test_idempotency_integration.py -v
python -m pytest tests/ -v --tb=short

# 커버리지
python -m pytest tests/unit/application/ --cov=src/application --cov-report=term-missing

# 타입 체크 (선택)
# mypy src/application/

# 수동 검증
# 1. 동일 캔들로 2회 실행 시도 → 2번째는 스킵 확인
# 2. 다른 캔들로 실행 → 정상 실행 확인
```

- [ ] 모든 테스트 통과
- [ ] 커버리지 95% 이상
- [ ] 중복 주문 방지 수동 검증 완료
- [ ] 기존 테스트 회귀 없음

---

### Phase 2: PR-3 PostgresPersistenceAdapter 구현

**목표**: PersistencePort의 PostgreSQL 구현체 완성

**예상 시간**: 6시간

**의존성**: Phase 1 완료

#### 테스트 전략

- **테스트 파일**: `tests/integration/adapters/test_postgres_persistence_adapter.py`
- **커버리지 목표**: 90%
- **실제 DB 필요**: Docker PostgreSQL

#### 테스트 시나리오

```python
# Trade 관련
1. test_save_and_get_trade
2. test_get_trades_by_ticker
3. test_get_recent_trades

# Order 관련
4. test_save_and_get_order
5. test_get_open_orders
6. test_update_order_status

# Position 관련
7. test_save_and_get_position
8. test_get_all_positions
9. test_position_update

# Decision 관련
10. test_save_and_get_decision
11. test_get_recent_decisions

# Portfolio 관련
12. test_save_portfolio_snapshot
13. test_get_portfolio_history

# Statistics 관련
14. test_get_trade_statistics
15. test_get_daily_pnl
```

#### 작업 항목

**RED (테스트 작성)**:
- [ ] `test_postgres_persistence_adapter.py` 생성
- [ ] pytest fixture로 테스트 DB 세션 설정
- [ ] 15개 테스트 시나리오 작성
- [ ] 테스트 실행 → 실패 확인

**GREEN (구현)**:
- [ ] `src/infrastructure/adapters/persistence/postgres_persistence_adapter.py` 생성
- [ ] PersistencePort 상속
- [ ] Trade CRUD 구현 (save_trade, get_trade, get_trades_by_ticker)
- [ ] Order CRUD 구현 (save_order, get_order, get_open_orders)
- [ ] Position CRUD 구현 (save_position, get_position, get_all_positions)
- [ ] Decision CRUD 구현 (save_decision, get_recent_decisions)
- [ ] Portfolio CRUD 구현 (save_portfolio_snapshot, get_portfolio_history)
- [ ] Statistics 계산 구현 (get_trade_statistics, get_daily_pnl)
- [ ] 테스트 통과 확인

**REFACTOR**:
- [ ] 쿼리 최적화 (인덱스 활용)
- [ ] 에러 핸들링 통일
- [ ] async/await 패턴 일관성
- [ ] 전체 테스트 재실행

#### Quality Gate

```bash
# 통합 테스트 (실제 DB 필요)
docker-compose up -d postgres
python -m pytest tests/integration/adapters/test_postgres_persistence_adapter.py -v

# 전체 테스트
python -m pytest tests/ -v --tb=short

# 커버리지
python -m pytest tests/integration/adapters/ --cov=src/infrastructure/adapters/persistence --cov-report=html
```

- [ ] 모든 테스트 통과
- [ ] 커버리지 90% 이상
- [ ] 18개 PersistencePort 메서드 전부 구현
- [ ] 기존 테스트 회귀 없음
- [ ] DB 마이그레이션 정상 동작

---

### Phase 3: PR-3 Container 기본값 변경

**목표**: InMemory → PostgreSQL 전환, 테스트 환경 분리

**예상 시간**: 3시간

**의존성**: Phase 2 완료

#### 테스트 전략

- **테스트 파일**: `tests/unit/container/test_container_production.py`
- **커버리지 목표**: 90%

#### 테스트 시나리오

```python
1. test_container_production_uses_postgres_persistence
2. test_container_production_uses_postgres_idempotency
3. test_container_production_uses_postgres_lock
4. test_container_testing_uses_memory_adapters
5. test_container_singleton_returns_same_instance
6. test_container_requires_session_factory_for_production
```

#### 작업 항목

**RED (테스트 작성)**:
- [ ] `test_container_production.py` 생성
- [ ] 프로덕션/테스트 환경 분리 테스트 작성
- [ ] 테스트 실행 → 실패 확인

**GREEN (구현)**:
- [ ] `Container.__init__()` 수정: session_factory 필수화
- [ ] `Container.create_for_production()` 팩토리 메서드 추가
- [ ] `get_persistence_port()` 기본값을 PostgresAdapter로 변경
- [ ] `create_for_testing()` 유지 (InMemory 사용)
- [ ] `create_from_legacy()` 업데이트: session_factory 검증
- [ ] 테스트 통과 확인

**REFACTOR**:
- [ ] 설정 주입 패턴 개선
- [ ] 에러 메시지 명확화
- [ ] 전체 테스트 재실행

#### Quality Gate

```bash
# 컨테이너 테스트
python -m pytest tests/unit/container/ -v

# 프로덕션 환경 시뮬레이션
python -c "
from src.container import Container
from backend.app.db.session import AsyncSessionLocal
c = Container.create_for_production(session_factory=AsyncSessionLocal)
print(type(c.get_persistence_port()))  # PostgresPersistenceAdapter
"

# 전체 테스트
python -m pytest tests/ -v --tb=short
```

- [ ] 모든 테스트 통과
- [ ] 프로덕션에서 PostgresAdapter 사용 확인
- [ ] 테스트에서 InMemoryAdapter 사용 확인
- [ ] session_factory 없이 프로덕션 생성 시 에러
- [ ] 기존 테스트 회귀 없음

---

### Phase 4: PR-2 LiveExecutionAdapter 구현

**목표**: 실시간 거래용 ExecutionPort 구현

**예상 시간**: 5시간

**의존성**: Phase 3 완료

#### 테스트 전략

- **테스트 파일**: `tests/unit/infrastructure/adapters/test_live_execution_adapter.py`
- **커버리지 목표**: 85%
- **Mock 대상**: ExchangePort (실제 API 호출 방지)

#### 테스트 시나리오

```python
1. test_execute_market_buy_order
2. test_execute_market_sell_order
3. test_execution_with_slippage
4. test_execution_failure_handling
5. test_check_stop_loss_triggered (실시간 가격 기반)
6. test_check_take_profit_triggered
7. test_get_execution_price_with_slippage
8. test_execution_result_contains_all_fields
```

#### 작업 항목

**RED (테스트 작성)**:
- [ ] `test_live_execution_adapter.py` 생성
- [ ] ExchangePort mock 설정
- [ ] 8개 테스트 시나리오 작성
- [ ] 테스트 실행 → 실패 확인

**GREEN (구현)**:
- [ ] `src/infrastructure/adapters/execution/live_execution_adapter.py` 생성
- [ ] ExecutionPort 상속
- [ ] `execute_market_order()` 구현: ExchangePort 호출
- [ ] `check_stop_loss_triggered()` 구현: 실시간 가격 조회
- [ ] `check_take_profit_triggered()` 구현
- [ ] `get_stop_loss_execution_price()` 구현: 실제 체결가 반환
- [ ] 슬리피지 계산 로직 포함
- [ ] 테스트 통과 확인

**REFACTOR**:
- [ ] 에러 핸들링 개선
- [ ] 로깅 추가 (체결 상세)
- [ ] 타임아웃 처리
- [ ] 전체 테스트 재실행

#### Quality Gate

```bash
# 어댑터 테스트
python -m pytest tests/unit/infrastructure/adapters/test_live_execution_adapter.py -v

# IntrabarAdapter 비교 테스트
python -m pytest tests/unit/infrastructure/adapters/test_intrabar_execution_adapter.py -v

# 전체 테스트
python -m pytest tests/ -v --tb=short

# 커버리지
python -m pytest tests/unit/infrastructure/adapters/ --cov=src/infrastructure/adapters/execution --cov-report=term-missing
```

- [ ] 모든 테스트 통과
- [ ] 커버리지 85% 이상
- [ ] ExecutionPort 모든 메서드 구현
- [ ] LiveExecutionAdapter와 IntrabarAdapter 인터페이스 동일
- [ ] 기존 테스트 회귀 없음

---

### Phase 5: PR-2 Execution Pipeline 통합

**목표**: Live/Backtest에서 ExecutionPort 통합 사용

**예상 시간**: 4시간

**의존성**: Phase 4 완료

#### 테스트 전략

- **테스트 파일**: `tests/integration/pipeline/test_execution_stage_integration.py`
- **커버리지 목표**: 85%

#### 테스트 시나리오

```python
1. test_execution_stage_uses_execution_port
2. test_live_mode_uses_live_adapter
3. test_backtest_mode_uses_intrabar_adapter
4. test_same_signal_same_logic (동일 시그널 → 동일 로직)
5. test_stop_loss_execution_through_port
6. test_take_profit_execution_through_port
7. test_execution_result_recorded
```

#### 작업 항목

**RED (테스트 작성)**:
- [ ] `test_execution_stage_integration.py` 생성
- [ ] Live/Backtest 모드별 테스트 작성
- [ ] 테스트 실행 → 실패 확인

**GREEN (구현)**:
- [ ] `ExecutionStage` 수정: ExecutionPort 의존성 주입
- [ ] `Container.get_execution_port(mode)` 추가: live/backtest 분기
- [ ] `TradingOrchestrator` 수정: ExecutionPort 전달
- [ ] 백테스트 파이프라인 수정: IntrabarExecutionAdapter 사용
- [ ] 테스트 통과 확인

**REFACTOR**:
- [ ] TradingService 직접 호출 제거
- [ ] 체결 로직 중복 제거
- [ ] 전체 테스트 재실행

#### Quality Gate

```bash
# 통합 테스트
python -m pytest tests/integration/pipeline/test_execution_stage_integration.py -v

# 백테스트 검증
python -m pytest tests/backtesting/ -v

# 전체 테스트
python -m pytest tests/ -v --tb=short

# 수동 검증
# 1. 동일 시그널로 Live/Backtest 실행
# 2. 체결 로직 동일 확인 (가격 산정 방식)
```

- [ ] 모든 테스트 통과
- [ ] ExecutionStage가 ExecutionPort만 사용
- [ ] TradingService 직접 호출 없음
- [ ] Live/Backtest 동일 인터페이스 확인
- [ ] 기존 테스트 회귀 없음

---

### Phase 6: 레거시 코드 완전 삭제

**목표**: AIService, TradingService, 직접 클라이언트 호출 제거

**예상 시간**: 4시간

**의존성**: Phase 5 완료

#### 테스트 전략

- **테스트 파일**: 기존 테스트 유지 + import 검증
- **커버리지 목표**: 기존 유지
- **검증**: grep으로 레거시 import 없음 확인

#### 삭제/수정 대상

```
삭제:
- [ ] src/ai/service.py (AIService 클래스)
- [ ] src/trading/service.py (TradingService 클래스)

수정:
- [ ] telegram_bot.py: Container 사용으로 전환
- [ ] main.py: Container.get_trading_orchestrator() 사용
- [ ] 레거시 테스트 파일 삭제 또는 마이그레이션
```

#### 작업 항목

**사전 검증**:
- [ ] 모든 레거시 사용처 확인 (grep)
- [ ] 대체 경로 매핑 문서화

**telegram_bot.py 마이그레이션**:
- [ ] `_cmd_run()`: Container.get_trading_orchestrator() 사용
- [ ] `_cmd_status()`: Container.get_exchange_port() 사용
- [ ] `_cmd_positions()`: Container.get_persistence_port() 사용
- [ ] `_cmd_balance()`: Container.get_exchange_port() 사용
- [ ] 직접 서비스 생성 코드 제거

**main.py 마이그레이션**:
- [ ] Container.create_for_production() 사용
- [ ] TradingOrchestrator.execute_trading_cycle() 직접 호출
- [ ] 레거시 서비스 import 제거

**레거시 파일 삭제**:
- [ ] `src/ai/service.py` 삭제
- [ ] `src/trading/service.py` 삭제
- [ ] `src/ai/__init__.py` 정리
- [ ] `src/trading/__init__.py` 정리

**테스트 정리**:
- [ ] 레거시 테스트 → 클린 아키텍처 테스트로 마이그레이션
- [ ] 불필요한 mock 제거

#### Quality Gate

```bash
# 레거시 import 검색 (없어야 함)
grep -r "from src.ai.service import" --include="*.py" | grep -v test | grep -v __pycache__
grep -r "from src.trading.service import" --include="*.py" | grep -v test | grep -v __pycache__

# 전체 테스트 (레거시 삭제 후에도 통과)
python -m pytest tests/ -v --tb=short

# 스케줄러 실행 테스트
python scheduler_main.py --dry-run

# main.py 실행 테스트
python main.py --dry-run
```

- [ ] 레거시 import 검색 결과 0건
- [ ] 모든 테스트 통과
- [ ] scheduler_main.py 정상 실행
- [ ] main.py 정상 실행
- [ ] telegram_bot.py 정상 실행

---

### Phase 7: 통합 테스트 & 문서화

**목표**: E2E 검증 + 문서 업데이트

**예상 시간**: 4시간

**의존성**: Phase 6 완료

#### 테스트 전략

- **테스트 파일**: `tests/e2e/test_full_trading_cycle.py`
- **환경**: Docker Compose (postgres + bot)

#### E2E 시나리오

```python
1. test_full_trading_cycle_e2e
   - Container 생성
   - TradingOrchestrator 실행
   - DB에 Trade/Decision/Order 저장 확인
   - Idempotency 동작 확인

2. test_process_restart_state_recovery
   - 거래 실행
   - 프로세스 재시작 시뮬레이션
   - 상태 복구 확인

3. test_concurrent_trading_lock
   - 동시 거래 시도
   - 락으로 한 번만 실행 확인
```

#### 작업 항목

**E2E 테스트 작성**:
- [ ] `tests/e2e/` 디렉토리 생성
- [ ] `test_full_trading_cycle.py` 작성
- [ ] Docker Compose 테스트 환경 구성
- [ ] 3개 시나리오 구현

**문서 업데이트**:
- [ ] `CLAUDE.md` 업데이트: 클린 아키텍처 100% 반영
- [ ] `docs/guide/ARCHITECTURE.md` 업데이트
- [ ] `docs/guide/SCHEDULER_GUIDE.md` 업데이트
- [ ] 다이어그램 업데이트 (`docs/diagrams/`)

**문서 거버넌스**:
- [ ] 완료된 계획 문서 처리 (본 문서)
- [ ] 중복/구식 문서 삭제
- [ ] 문서 변경 로그 작성

#### Quality Gate

```bash
# E2E 테스트
docker-compose -f docker-compose.test.yml up -d
python -m pytest tests/e2e/ -v
docker-compose -f docker-compose.test.yml down

# 문서 일관성 검증
# ARCHITECTURE.md에 Container 사용 패턴 반영 확인
# SCHEDULER_GUIDE.md에 Lock/Idempotency 반영 확인

# 전체 테스트
python -m pytest tests/ -v --tb=short
```

- [ ] E2E 테스트 3개 통과
- [ ] 문서 업데이트 완료
- [ ] 다이어그램 최신화
- [ ] 구식 문서 삭제/정리
- [ ] 전체 테스트 회귀 없음

---

## 5. 리스크 평가

| 리스크 | 확률 | 영향도 | 완화 전략 |
|--------|------|--------|----------|
| PostgresAdapter 버그 | Medium | High | 단계별 테스트, 롤백 준비 |
| 레거시 삭제 시 누락 | Medium | Medium | grep 철저 검증, 단계별 삭제 |
| 성능 저하 (DB 호출 증가) | Low | Medium | 인덱스 최적화, 캐싱 검토 |
| 테스트 커버리지 하락 | Low | Medium | Phase별 커버리지 목표 강제 |
| 동시성 이슈 (Lock) | Low | High | Advisory Lock 검증 테스트 |

---

## 6. 롤백 전략

### Phase 1 롤백
- `TradingOrchestrator`에 추가한 idempotency 체크 코드 제거
- 테스트 파일만 유지

### Phase 2 롤백
- `PostgresPersistenceAdapter` 파일 삭제
- Container 기본값 유지 (InMemory)

### Phase 3 롤백
- Container 변경 사항 revert
- `create_for_production()` 제거

### Phase 4 롤백
- `LiveExecutionAdapter` 파일 삭제
- 기존 TradingService 유지

### Phase 5 롤백
- ExecutionStage 변경 사항 revert
- TradingService 직접 호출 복구

### Phase 6 롤백
- Git에서 삭제된 레거시 파일 복구
- telegram_bot.py, main.py 변경 revert

### Phase 7 롤백
- E2E 테스트 삭제
- 문서 변경 revert

---

## 7. 진행 상황

### Phase 체크리스트

- [x] **Phase 1**: PR-1 Idempotency Pipeline 통합 ✅ (2026-01-03)
- [ ] **Phase 2**: PR-3 PostgresPersistenceAdapter 구현
- [ ] **Phase 3**: PR-3 Container 기본값 변경
- [ ] **Phase 4**: PR-2 LiveExecutionAdapter 구현
- [ ] **Phase 5**: PR-2 Execution Pipeline 통합
- [ ] **Phase 6**: 레거시 코드 완전 삭제
- [ ] **Phase 7**: 통합 테스트 & 문서화

### 진행률

```
Phase 1: ✅✅✅✅✅ 100% ← DONE
Phase 2: ⬜⬜⬜⬜⬜ 0%
Phase 3: ⬜⬜⬜⬜⬜ 0%
Phase 4: ⬜⬜⬜⬜⬜ 0%
Phase 5: ⬜⬜⬜⬜⬜ 0%
Phase 6: ⬜⬜⬜⬜⬜ 0%
Phase 7: ⬜⬜⬜⬜⬜ 0%
────────────────────
Total:   🟩⬜⬜⬜⬜ 14%
```

---

## 8. Notes & Learnings

### Phase 1 ✅ 완료 (2026-01-03)
- TradingOrchestrator에 `_get_current_candle_ts()` 메서드 추가
- `execute_trading_cycle()` 진입부에 idempotency 체크 추가
- Fail-close 정책 구현: idempotency 체크 실패 시 거래 차단
- 중복 캔들/티커 조합은 즉시 skip 처리
- 성공한 사이클은 키 마킹 (TTL 24시간)
- 13개 테스트 통과, 592개 기존 테스트 회귀 없음

### Phase 2
- (작업 후 기록)

### Phase 3
- (작업 후 기록)

### Phase 4
- (작업 후 기록)

### Phase 5
- (작업 후 기록)

### Phase 6
- (작업 후 기록)

### Phase 7
- (작업 후 기록)

---

## 변경 이력

| 날짜 | 변경 내용 | 작성자 |
|------|----------|--------|
| 2026-01-03 | 초안 작성 | Claude |
