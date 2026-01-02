# Clean Architecture Migration Plan

**작성일**: 2026-01-02
**상태**: 계획 수립 완료
**예상 소요**: 약 12-16시간 (5개 Phase)

---

## CRITICAL INSTRUCTIONS

After completing each phase:
1. Check off completed task checkboxes
2. Run all quality gate validation commands
3. Verify ALL quality gate items pass
4. Update "Last Updated" date
5. Document learnings in Notes section
6. Only then proceed to next phase

**DO NOT skip quality gates or proceed with failing checks**

---

## 1. Overview

### 1.1 Problem Statement (Split Brain)

현재 시스템은 **두 개의 완전히 다른 거래 로직**을 가지고 있습니다:

| 구분 | 새로운 아키텍처 (src/application) | 실행 중인 코드 (src/trading/service.py) |
|------|----------------------------------|----------------------------------------|
| Money 처리 | Money 객체 (통화/정밀도 보장) | float 원시 타입 (부동소수점 오차 위험) |
| 의존성 | Container를 통한 주입 (DI) | 직접 생성 및 전달 |
| 인터페이스 | ExchangePort (추상화) | IExchangeClient (레거시) |
| DTO 사용 | OrderResponse (명시적) | dict (암시적) |
| 비동기 | async/await | 동기 |

**문제**: `main.py`는 레거시 `TradingService`를 사용하고, 클린 아키텍처 코드가 **실행되지 않음**.

### 1.2 Goal

- `main.py` → `Container` → `UseCase` → `Port` 경로로 전환
- 파이프라인 스테이지들이 `UseCase`를 사용하도록 마이그레이션
- 레거시 서비스들을 점진적으로 제거

### 1.3 Migration Strategy: Strangler Fig Pattern

기존 코드를 한 번에 교체하지 않고, **새 코드로 점진적으로 감싸서** 레거시를 조금씩 대체합니다.

```
Phase 1: 파이프라인 비동기화 (기반 작업)
Phase 2: Container를 main.py에 도입
Phase 3: ExecutionStage를 UseCase로 마이그레이션
Phase 4: AnalysisStage를 UseCase로 마이그레이션
Phase 5: 레거시 코드 정리 및 제거
```

---

## 2. Architecture Decisions

### ADR-001: Async Pipeline

**결정**: 모든 파이프라인 스테이지를 `async`로 전환

**이유**:
- 새 UseCase들이 모두 async
- I/O 바운드 작업(API 호출)에 적합
- 향후 병렬 처리 가능

### ADR-002: Container-First Approach

**결정**: `main.py` 진입점에서 `Container`를 먼저 초기화

**이유**:
- 의존성 역전 원칙(DIP) 준수
- 테스트 용이성 확보
- 점진적 마이그레이션 가능

### ADR-003: Keep Pipeline Pattern

**결정**: 파이프라인 패턴은 유지, 내부만 UseCase로 교체

**이유**:
- 검증된 실행 흐름
- 스테이지별 관심사 분리
- 롤백 용이

---

## 3. Phase Breakdown

### Phase 1: 파이프라인 비동기화 (2-3시간)

**Goal**: 모든 파이프라인 스테이지를 async로 전환하여 UseCase 호출 준비

**Test Strategy**:
- 테스트 파일: `tests/unit/pipeline/test_async_pipeline.py`
- 커버리지 목표: 80%
- 기존 동작 유지 확인 (회귀 테스트)

**Tasks**:

#### RED Phase
- [ ] `tests/unit/pipeline/test_async_pipeline.py` 생성
- [ ] `BasePipelineStage.execute()` async 테스트 작성
- [ ] `TradingPipeline.execute()` async 테스트 작성
- [ ] 모든 스테이지의 async execute 테스트 작성

#### GREEN Phase
- [ ] `src/trading/pipeline/base_stage.py` - `execute()` → `async def execute()`
- [ ] `src/trading/pipeline/trading_pipeline.py` - `execute()` → `async def execute()`
- [ ] `src/trading/pipeline/execution_stage.py` - async 전환
- [ ] `src/trading/pipeline/analysis_stage.py` - async 전환
- [ ] `src/trading/pipeline/data_collection_stage.py` - async 전환
- [ ] `src/trading/pipeline/hybrid_stage.py` - async 전환

#### REFACTOR Phase
- [ ] 중복 코드 제거
- [ ] 타입 힌트 추가

**Quality Gate**:
- [ ] `python -m pytest tests/unit/pipeline/ -v` 통과
- [ ] `python -m pytest tests/ -v` 기존 테스트 통과
- [ ] 파이프라인 로컬 실행 테스트

**Files to Modify**:
- `src/trading/pipeline/base_stage.py`
- `src/trading/pipeline/trading_pipeline.py`
- `src/trading/pipeline/execution_stage.py`
- `src/trading/pipeline/analysis_stage.py`
- `src/trading/pipeline/data_collection_stage.py`
- `src/trading/pipeline/hybrid_stage.py`

---

### Phase 2: Container를 main.py에 도입 (2-3시간)

**Goal**: main.py에서 Container를 통해 서비스 초기화

**Test Strategy**:
- 테스트 파일: `tests/unit/test_main_container.py`
- Container 통합 테스트
- 레거시 호환성 유지 확인

**Tasks**:

#### RED Phase
- [ ] `tests/unit/test_main_container.py` 생성
- [ ] Container.create_from_legacy() 통합 테스트 작성
- [ ] main.py 초기화 흐름 테스트

#### GREEN Phase
- [ ] `main.py`에서 Container 초기화 추가
- [ ] Container.create_from_legacy()로 레거시 서비스 래핑
- [ ] PipelineContext에 use_case 주입 지원 추가

#### REFACTOR Phase
- [ ] 중복 초기화 로직 제거
- [ ] 설정 관리 개선

**Quality Gate**:
- [ ] Container 통합 테스트 통과
- [ ] `python main.py` 정상 실행 (dry-run)
- [ ] 기존 스케줄러 호환성 확인

**Files to Modify**:
- `main.py`
- `src/trading/pipeline/base_stage.py` (PipelineContext 확장)
- `src/container.py` (필요시 개선)

---

### Phase 3: ExecutionStage UseCase 마이그레이션 (3-4시간)

**Goal**: ExecutionStage가 ExecuteTradeUseCase를 사용하도록 전환

**Test Strategy**:
- 테스트 파일: `tests/unit/pipeline/test_execution_stage_usecase.py`
- Mock UseCase로 격리 테스트
- 실제 주문 로직 검증 (dry-run)

**Tasks**:

#### RED Phase
- [ ] ExecutionStage + UseCase 통합 테스트 작성
- [ ] 매수/매도/홀드 시나리오 테스트
- [ ] 에러 핸들링 테스트

#### GREEN Phase
- [ ] ExecutionStage 생성자에 `execute_trade_use_case` 주입
- [ ] `_execute_buy()` → `use_case.execute_buy()` 호출로 변경
- [ ] `_execute_sell()` → `use_case.execute_sell()` 호출로 변경
- [ ] OrderResponse → StageResult 변환 로직 추가
- [ ] Money 값 객체 사용으로 전환

#### REFACTOR Phase
- [ ] TradingService 직접 호출 제거
- [ ] 에러 처리 통일

**Quality Gate**:
- [ ] 단위 테스트 통과
- [ ] 통합 테스트 통과
- [ ] 백테스팅 결과 동일 확인

**Files to Modify**:
- `src/trading/pipeline/execution_stage.py`
- `src/trading/pipeline/__init__.py` (팩토리 함수 수정)
- `main.py` (use case 주입)

---

### Phase 4: AnalysisStage UseCase 마이그레이션 (3-4시간)

**Goal**: AnalysisStage가 AnalyzeMarketUseCase를 사용하도록 전환

**Test Strategy**:
- 테스트 파일: `tests/unit/pipeline/test_analysis_stage_usecase.py`
- AI 분석 로직 보존 확인
- 분석 데이터 일관성 검증

**Tasks**:

#### RED Phase
- [ ] AnalysisStage + UseCase 통합 테스트 작성
- [ ] 시장 분석 결과 검증 테스트
- [ ] AI 응답 파싱 테스트

#### GREEN Phase
- [ ] AnalysisStage 생성자에 `analyze_market_use_case` 주입
- [ ] 시장 분석 로직을 UseCase로 위임
- [ ] AIService의 `prepare_analysis_data()` 로직 통합
- [ ] TradingDecision → ai_result dict 변환

#### REFACTOR Phase
- [ ] AIService 직접 호출 제거
- [ ] 분석 데이터 준비 로직 정리

**Quality Gate**:
- [ ] 단위 테스트 통과
- [ ] AI 분석 결과 일관성 확인
- [ ] 전체 파이프라인 통합 테스트

**Files to Modify**:
- `src/trading/pipeline/analysis_stage.py`
- `src/application/use_cases/analyze_market.py` (분석 데이터 로직 통합)
- `src/infrastructure/adapters/ai/openai_adapter.py` (프롬프트 강화)

---

### Phase 5: 레거시 코드 정리 (2시간)

**Goal**: 사용하지 않는 레거시 코드 제거 및 문서화

**Tasks**:

- [ ] PipelineContext에서 `trading_service`, `ai_service` 필드 deprecated 처리
- [ ] `src/trading/service.py`에서 사용되지 않는 메서드 정리
- [ ] `src/ai/service.py`에서 사용되지 않는 메서드 정리
- [ ] CLAUDE.md 아키텍처 문서 업데이트
- [ ] Migration 완료 표시

**Quality Gate**:
- [ ] 전체 테스트 스위트 통과
- [ ] 린터/타입 체크 통과
- [ ] 실제 거래 테스트 (소액)

**Files to Modify**:
- `src/trading/pipeline/base_stage.py`
- `src/trading/service.py`
- `src/ai/service.py`
- `CLAUDE.md`

---

## 4. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| 비동기 전환 시 버그 | Medium | High | 단계별 테스트, 롤백 준비 |
| AI 분석 결과 불일치 | Low | High | 기존 로직 100% 보존 후 점진 개선 |
| 거래 실패 | Low | Critical | Dry-run 모드 먼저 테스트 |
| 테스트 커버리지 부족 | Medium | Medium | 각 Phase에서 80% 이상 목표 |

---

## 5. Rollback Strategy

각 Phase는 독립적으로 롤백 가능:

- **Phase 1**: git revert로 async 변경 취소
- **Phase 2**: Container 초기화 제거, 레거시 초기화 복구
- **Phase 3**: ExecutionStage에서 TradingService 직접 호출 복구
- **Phase 4**: AnalysisStage에서 AIService 직접 호출 복구
- **Phase 5**: deprecated 표시 제거

---

## 6. Progress Tracking

| Phase | Status | Started | Completed |
|-------|--------|---------|-----------|
| Phase 1: 파이프라인 비동기화 | ⏳ Pending | - | - |
| Phase 2: Container 도입 | ⏳ Pending | - | - |
| Phase 3: ExecutionStage 마이그레이션 | ⏳ Pending | - | - |
| Phase 4: AnalysisStage 마이그레이션 | ⏳ Pending | - | - |
| Phase 5: 레거시 정리 | ⏳ Pending | - | - |

---

## 7. Notes & Learnings

*(각 Phase 완료 후 기록)*

---

## 8. Critical Files Summary

### 수정 대상 파일
- `main.py` - Container 도입
- `src/trading/pipeline/base_stage.py` - async 전환, Context 확장
- `src/trading/pipeline/trading_pipeline.py` - async 전환
- `src/trading/pipeline/execution_stage.py` - UseCase 마이그레이션
- `src/trading/pipeline/analysis_stage.py` - UseCase 마이그레이션
- `src/trading/pipeline/data_collection_stage.py` - async 전환
- `src/trading/pipeline/hybrid_stage.py` - async 전환
- `src/container.py` - 필요시 개선
- `src/application/use_cases/analyze_market.py` - 분석 로직 통합

### 참조 파일 (변경 없음)
- `src/domain/entities/trade.py` - 도메인 모델
- `src/domain/value_objects/money.py` - 값 객체
- `src/application/ports/outbound/exchange_port.py` - 포트 인터페이스
- `src/infrastructure/adapters/exchange/upbit_adapter.py` - 어댑터

### 정리 대상 파일
- `src/trading/service.py` - 레거시 (점진적 제거)
- `src/ai/service.py` - 레거시 (점진적 제거)
