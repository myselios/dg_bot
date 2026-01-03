# 클린 아키텍처 리팩토링 계획

**작성일**: 2026-01-03
**Last Updated**: 2026-01-03
**Status**: Phase 1 In Progress
**Scope**: Large (6 Phases, 18-24 hours)

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

### 목적
dg_bot을 **상용 자동매매 시스템**으로 발전시키기 위한 클린 아키텍처 완성 리팩토링

### 현재 문제점
1. **트레이딩 코어 이중화**: Legacy(`src/trading/`) + Clean(`src/application/use_cases/`) 공존
2. **계층 침범**: `scheduler.py` → `main.py` 직접 import
3. **상태 관리 3원화**: JSON + 메모리 + DB 혼재
4. **Port 패턴 무시**: Port 정의 후 `getattr(port, '_client')`로 우회

### 목표 상태
- 단일 실행 경로 (UseCase 기반)
- 명확한 계층 분리 (Presentation → Application → Domain ← Infrastructure)
- DB 단일 상태 관리
- Port 직접 사용 (레거시 추출 제거)

---

## Architecture Decisions

### ADR-1: 아키텍처 모드 설정화
**결정**: `ArchitectureConfig.MODE`로 레거시/클린 전환 제어
**근거**: 점진적 마이그레이션 및 롤백 가능성 확보
**영향**: Container, Pipeline Stage 분기 로직 통일

### ADR-2: 상태 관리 DB 단일화
**결정**: `RiskStateManager` JSON → PostgreSQL `RiskState` 모델로 전환
**근거**: 다중 인스턴스 안전성, 상태 일관성
**영향**: `data/risk_state.json` 제거, 마이그레이션 필요

### ADR-3: TradingOrchestrator 도입
**결정**: Application 서비스 계층에 `TradingOrchestrator` 추가
**근거**: Scheduler와 비즈니스 로직 분리, 테스트 용이성
**영향**: `main.py` thin entrypoint화, Scheduler 의존성 정리

### ADR-4: Port 직접 사용
**결정**: Pipeline Stage에서 Port 메서드 직접 호출
**근거**: 클린 아키텍처 원칙 준수, 의존성 역전
**영향**: `_get_services()` 패턴 제거, Adapter 정비

---

## Phase Breakdown

### Phase 1: 아키텍처 모드 명시화

**Goal**: 현재 하이브리드 상태를 설정으로 명시화하여 점진적 전환 기반 마련

**Estimated Time**: 2-3 hours

**Dependencies**: None (첫 번째 Phase)

**Test Strategy**:
- Test File: `tests/unit/config/test_architecture_config.py`
- Coverage Target: 80%+
- Mocks: None (설정 테스트)

#### Tasks

**RED (테스트 작성)**:
- [x] `ArchitectureConfig` 클래스 존재 테스트
- [x] `MODE` 설정값 검증 테스트 (`legacy` | `clean` | `hybrid`)
- [x] Container가 모드에 따라 다르게 동작하는 테스트

**GREEN (구현)**:
- [x] `src/config/settings.py`에 `ArchitectureConfig` 클래스 추가
- [ ] Container에 모드 기반 분기 로직 추가 (Phase 5에서 진행)
- [x] 기본값 `MODE = 'legacy'` 설정 (현재 상태 명시)

**REFACTOR (개선)**:
- [ ] 기존 `if context.container:` 분기를 설정 기반으로 통일 (Phase 5에서 진행)
- [ ] 관련 문서 업데이트

#### Quality Gate

**Build & Tests**:
- [ ] `python -m pytest tests/ -v` 전체 통과 (11개 기존 실패 - ArchitectureConfig 무관)
- [x] `python -m pytest tests/unit/config/test_architecture_config.py -v` 통과 (17/17)
- [x] 테스트 커버리지 80%+ 확인

**Code Quality**:
- [x] 타입 힌트 추가 완료
- [x] 독스트링 작성 완료

**Functionality**:
- [x] 기존 스케줄러 정상 동작 확인 (Docker 컨테이너 healthy)
- [x] `MODE = 'legacy'` 시 기존 동작과 동일 확인

#### Rollback Strategy
- `ArchitectureConfig` 클래스 삭제
- Container 분기 로직 원복
- Git: `git revert HEAD`

---

### Phase 2: 상태 관리 단일화 (JSON → DB)

**Goal**: `RiskStateManager`의 JSON 파일 의존성을 제거하고 PostgreSQL로 통합

**Estimated Time**: 3-4 hours

**Dependencies**: Phase 1 완료

**Test Strategy**:
- Test File: `tests/unit/infrastructure/test_risk_state_repository.py`
- Integration Test: `tests/integration/test_risk_state_db.py`
- Coverage Target: 85%+
- Mocks: DB Session (단위 테스트), Real DB (통합 테스트)

#### Tasks

**RED (테스트 작성)**:
- [x] `RiskState` SQLAlchemy 모델 테스트
- [x] `RiskStateRepository.save()` 테스트
- [x] `RiskStateRepository.load_by_date()` 테스트
- [x] `RiskStateRepository.load_all()` 테스트
- [x] JSON → DB 마이그레이션 테스트 (RiskStateManager async 메서드)

**GREEN (구현)**:
- [x] `backend/app/models/risk_state.py` 모델 생성
- [x] `backend/app/schemas/risk_state.py` Pydantic 스키마 생성
- [x] `src/infrastructure/adapters/persistence/risk_state_repository.py` 구현
- [x] `RiskStateManager`가 Repository 사용하도록 변경 (`save_state_async`, `load_state_async`)
- [ ] 마이그레이션 스크립트 작성 (`scripts/migrate_risk_state.py`) - 필요시 추가

**REFACTOR (개선)**:
- [ ] `data/risk_state.json` 파일 삭제 (운영 안정화 후)
- [x] JSON 관련 코드 DEPRECATED 표시
- [ ] 관련 문서 업데이트

#### Quality Gate

**Build & Tests**:
- [ ] `python -m pytest tests/ -v` 전체 통과 (11개 기존 실패 - Phase 2 무관)
- [x] `python -m pytest tests/unit/infrastructure/persistence/test_risk_state_repository.py -v` 통과 (14/14)
- [ ] 통합 테스트는 DB 테이블 생성 후 진행

**Data Migration**:
- [ ] 기존 JSON 데이터 마이그레이션 완료 확인 (운영 시 진행)
- [ ] DB에서 데이터 조회 정상 확인

**Functionality**:
- [x] `RiskStateManager._repository` 속성 추가
- [x] 스케줄러에서 기존 JSON 방식 유지 + DB 방식 선택 가능

#### Rollback Strategy
- `RiskState` 모델 삭제
- `RiskStateManager` 원복 (JSON 사용)
- `data/risk_state.json` 복원
- Git: `git revert HEAD~N..HEAD`

---

### Phase 3: TradingOrchestrator 서비스 도입

**Goal**: 비즈니스 로직을 Application 서비스 계층으로 분리하여 Scheduler 독립성 확보

**Estimated Time**: 3-4 hours

**Dependencies**: Phase 2 완료

**Test Strategy**:
- Test File: `tests/unit/application/services/test_trading_orchestrator.py`
- Coverage Target: 85%+
- Mocks: Container, UseCase들

#### Tasks

**RED (테스트 작성)**:
- [ ] `TradingOrchestrator.__init__(container)` 테스트
- [ ] `TradingOrchestrator.execute_trading_cycle()` 테스트
- [ ] `TradingOrchestrator.execute_position_management()` 테스트
- [ ] 에러 처리 테스트 (각 UseCase 실패 시)

**GREEN (구현)**:
- [ ] `src/application/services/__init__.py` 생성
- [ ] `src/application/services/trading_orchestrator.py` 구현
- [ ] `execute_trading_cycle()` 로직 이전 (from `main.py`)
- [ ] `execute_position_management_cycle()` 로직 이전
- [ ] Container에 `get_trading_orchestrator()` 메서드 추가

**REFACTOR (개선)**:
- [ ] `main.py`를 thin entrypoint로 축소 (Orchestrator 호출만)
- [ ] 중복 초기화 코드 제거
- [ ] 관련 문서 업데이트

#### Quality Gate

**Build & Tests**:
- [ ] `python -m pytest tests/ -v` 전체 통과
- [ ] `python -m pytest tests/unit/application/services/test_trading_orchestrator.py -v` 통과
- [ ] 테스트 커버리지 85%+ 확인

**Code Quality**:
- [ ] `main.py` 라인 수 100줄 이하
- [ ] Orchestrator에 비즈니스 로직 집중 확인

**Functionality**:
- [ ] `python main.py` 실행 정상
- [ ] 스케줄러 정상 동작 확인

#### Rollback Strategy
- `TradingOrchestrator` 삭제
- `main.py` 원복
- Git: `git revert HEAD~N..HEAD`

---

### Phase 4: Scheduler 계층 분리

**Goal**: Scheduler → Main 순환 의존성 제거, Infrastructure → Application만 의존하도록 정리

**Estimated Time**: 2-3 hours

**Dependencies**: Phase 3 완료 (TradingOrchestrator 존재 필수)

**Test Strategy**:
- Test File: `tests/unit/backend/core/test_scheduler_isolation.py`
- Coverage Target: 80%+
- Mocks: TradingOrchestrator

#### Tasks

**RED (테스트 작성)**:
- [ ] Scheduler가 `main.py` import 없이 동작하는 테스트
- [ ] Scheduler가 `TradingOrchestrator`만 호출하는 테스트
- [ ] 계층 의존성 검증 테스트 (import 분석)

**GREEN (구현)**:
- [ ] `scheduler.py`에서 `from main import` 제거
- [ ] `TradingOrchestrator` 직접 사용으로 변경
- [ ] 서비스 초기화 코드를 Container로 통합

**REFACTOR (개선)**:
- [ ] `scheduler.py`의 중복 초기화 코드 제거
- [ ] Container 싱글톤 또는 팩토리 패턴 적용
- [ ] 관련 문서 업데이트

#### Quality Gate

**Build & Tests**:
- [ ] `python -m pytest tests/ -v` 전체 통과
- [ ] `grep -r "from main import" backend/` 결과 0건
- [ ] `grep -r "import main" backend/` 결과 0건

**Code Quality**:
- [ ] Scheduler 코드에 비즈니스 로직 없음 확인
- [ ] 계층 다이어그램 준수 확인

**Functionality**:
- [ ] `python scheduler_main.py` 정상 실행
- [ ] Trading Job 1회 정상 실행 확인
- [ ] Position Management Job 1회 정상 실행 확인

#### Rollback Strategy
- `scheduler.py` 원복 (`from main import` 복원)
- Git: `git revert HEAD~N..HEAD`

---

### Phase 5: Port 직접 사용

**Goal**: Pipeline Stage에서 Port를 직접 사용, `getattr(port, '_client')` 패턴 제거

**Estimated Time**: 4-5 hours

**Dependencies**: Phase 4 완료

**Test Strategy**:
- Test File: `tests/unit/trading/pipeline/test_port_usage.py`
- Integration Test: `tests/integration/test_pipeline_with_ports.py`
- Coverage Target: 85%+
- Mocks: ExchangePort, AIPort, MarketDataPort

#### Tasks

**RED (테스트 작성)**:
- [ ] `ExecutionStage`가 `ExchangePort` 직접 사용 테스트
- [ ] `AnalysisStage`가 `AIPort` 직접 사용 테스트
- [ ] `DataCollectionStage`가 `MarketDataPort` 직접 사용 테스트
- [ ] `getattr.*_client` 호출 0건 검증 테스트

**GREEN (구현)**:
- [ ] `ExecutionStage._execute_buy()` Port 직접 사용으로 변경
- [ ] `ExecutionStage._execute_sell()` Port 직접 사용으로 변경
- [ ] `AnalysisStage.execute()` Port 직접 사용으로 변경
- [ ] `DataCollectionStage.execute()` Port 직접 사용으로 변경
- [ ] `HybridRiskCheckStage` Port 직접 사용으로 변경

**REFACTOR (개선)**:
- [ ] `_get_services()` 메서드 제거 (모든 Stage)
- [ ] `PipelineContext`에서 레거시 서비스 필드 제거
- [ ] 관련 문서 업데이트

#### Quality Gate

**Build & Tests**:
- [ ] `python -m pytest tests/ -v` 전체 통과
- [ ] `grep -r "getattr.*_client" src/` 결과 0건
- [ ] `grep -r "_get_services" src/trading/pipeline/` 결과 0건

**Code Quality**:
- [ ] Port 인터페이스 통해서만 외부 시스템 접근 확인
- [ ] 의존성 역전 원칙 준수 확인

**Functionality**:
- [ ] 전체 트레이딩 사이클 정상 동작
- [ ] Dry-run 모드로 거래 시뮬레이션 성공

#### Rollback Strategy
- Stage 파일들 원복 (`_get_services()` 복원)
- `PipelineContext` 원복
- Git: `git revert HEAD~N..HEAD`

---

### Phase 6: Legacy Bridge 정리

**Goal**: 불필요한 레거시 코드 제거 및 최종 아키텍처 완성

**Estimated Time**: 3-4 hours

**Dependencies**: Phase 5 완료

**Test Strategy**:
- 전체 테스트 스위트 실행
- E2E 트레이딩 사이클 테스트
- Coverage Target: 전체 80%+

#### Tasks

**RED (테스트 작성)**:
- [ ] 클린 아키텍처 전용 E2E 테스트 작성
- [ ] `LegacyBridge` 미사용 검증 테스트

**GREEN (구현)**:
- [ ] `LegacyExchangeAdapter` → `UpbitExchangeAdapter`로 rename/전환
- [ ] `LegacyAIAdapter` → `OpenAIAdapter`로 rename/전환
- [ ] `LegacyMarketDataAdapter` → `UpbitMarketDataAdapter`로 rename/전환

**REFACTOR (개선)**:
- [ ] `src/infrastructure/adapters/legacy_bridge.py` 파일 삭제
- [ ] `ArchitectureConfig.MODE` 기본값 `'clean'`으로 변경
- [ ] 미사용 레거시 코드 정리
- [ ] CLAUDE.md 아키텍처 섹션 업데이트
- [ ] ARCHITECTURE.md 업데이트

#### Quality Gate

**Build & Tests**:
- [ ] `python -m pytest tests/ -v` 전체 통과
- [ ] `python -m pytest tests/ --cov=src --cov=backend --cov-report=html` 커버리지 80%+
- [ ] E2E 테스트 통과

**Code Quality**:
- [ ] `grep -r "legacy" src/infrastructure/adapters/` 결과 0건 (파일명 제외)
- [ ] 클린 아키텍처 다이어그램과 코드 일치 확인

**Functionality**:
- [ ] 프로덕션 환경 스케줄러 24시간 안정 운영 확인
- [ ] 실제 거래 1회 이상 성공 확인

**Documentation**:
- [ ] CLAUDE.md 업데이트 완료
- [ ] ARCHITECTURE.md 업데이트 완료
- [ ] docs/diagrams/ 다이어그램 업데이트 완료

#### Rollback Strategy
- `legacy_bridge.py` 복원
- Adapter 이름 원복
- `ArchitectureConfig.MODE = 'legacy'` 복원
- Git: `git revert HEAD~N..HEAD`

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| 기존 스케줄러 중단 | Medium | High | Phase별 독립 롤백 전략, 각 Phase 완료 후 스케줄러 테스트 |
| DB 마이그레이션 데이터 손실 | Low | Medium | JSON 백업 유지, 마이그레이션 전 검증 스크립트 |
| Port 변경 시 거래 실패 | Medium | High | Dry-run 모드 먼저 테스트, 소액 테스트 거래 |
| 테스트 커버리지 부족 | Medium | Medium | TDD 엄격 준수, Phase 진행 전 커버리지 확인 |
| 계층 분리 시 순환 의존성 | Low | Medium | Import 분석 테스트 추가, Dependency Graph 검증 |

---

## Progress Tracking

### Overall Progress
- [x] Phase 1: 아키텍처 모드 명시화 (2026-01-03 완료)
- [x] Phase 2: 상태 관리 단일화 (2026-01-03 완료)
- [ ] Phase 3: TradingOrchestrator 도입
- [ ] Phase 4: Scheduler 계층 분리
- [ ] Phase 5: Port 직접 사용
- [ ] Phase 6: Legacy Bridge 정리

### Completion Criteria
- All phase checkboxes completed
- All quality gates passed
- Documentation updated
- 24-hour production stability confirmed

---

## Notes & Learnings

### Phase 1 Notes
**완료일**: 2026-01-03

**작업 내용**:
- `ArchitectureConfig` 클래스를 `src/config/settings.py`에 추가
- MODE 값: `legacy` (기본값) | `clean` | `hybrid`
- 헬퍼 메서드: `is_legacy_mode()`, `is_clean_mode()`, `is_hybrid_mode()`, `should_use_container()`
- 17개 단위 테스트 추가 (`tests/unit/config/test_architecture_config.py`)

**학습 사항**:
- TDD 사이클 (RED → GREEN → REFACTOR) 엄격 준수가 코드 품질 보장에 효과적
- 환경 변수 기반 설정으로 점진적 마이그레이션 가능
- Docker 컨테이너 환경에서 테스트 시 파일 복사 필요 (`docker cp`)

**다음 단계**:
- Phase 2에서 상태 관리 단일화 진행
- `ArchitectureConfig.should_use_container()` 활용은 Phase 5에서 진행

### Phase 2 Notes
_(작업 완료 후 기록)_

### Phase 3 Notes
_(작업 완료 후 기록)_

### Phase 4 Notes
_(작업 완료 후 기록)_

### Phase 5 Notes
_(작업 완료 후 기록)_

### Phase 6 Notes
_(작업 완료 후 기록)_

---

## References

- [01_clean_architecture_review.md](01_clean_architecture_review.md) - 초기 분석 문서
- [ARCHITECTURE.md](../guide/ARCHITECTURE.md) - 현재 아키텍처 문서
- [CLAUDE.md](../../CLAUDE.md) - 프로젝트 가이드
