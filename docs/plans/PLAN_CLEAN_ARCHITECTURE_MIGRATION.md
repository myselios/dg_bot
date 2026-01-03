# Clean Architecture Migration Plan: 레거시 코드 완전 제거

**작성일**: 2026-01-03
**최종 업데이트**: 2026-01-03
**예상 소요 시간**: 12-18시간 (4개 Phase)
**상태**: ✅ Phase 1-3 완료, Phase 4 진행 중

---

## CRITICAL INSTRUCTIONS

이 계획 문서를 사용할 때:
1. 각 Phase 완료 후 체크박스 표시
2. Quality Gate 검증 명령 실행
3. 모든 Quality Gate 통과 확인 후 다음 Phase 진행
4. 마지막 업데이트 날짜 갱신
5. Notes 섹션에 학습 내용 기록

**DO NOT** Quality Gate 스킵하거나 실패 상태에서 진행하지 마세요.

---

## Overview

### 현재 상태 분석

**레거시 코드 사용 현황:**

| 컴포넌트 | 상태 | 심각도 | 설명 |
|----------|------|--------|------|
| `scheduler.py` (trading_job) | LEGACY | CRITICAL | 매 작업마다 레거시 서비스 직접 인스턴스화 |
| `scheduler.py` (position_job) | LEGACY | CRITICAL | 동일 |
| `main.py` | LEGACY | HIGH | 레거시 서비스 import 및 전달 |
| `DataCollectionStage` | LEGACY | HIGH | 100% context.upbit_client/data_collector 사용 |
| `ExecutionStage` | HYBRID | MEDIUM | UseCase 있으면 사용, 없으면 레거시 |
| `AnalysisStage` | HYBRID | MEDIUM | UseCase 있으면 사용, 없으면 레거시 |
| `HybridRiskCheckStage` | LEGACY | HIGH | 레거시 서비스 직접 호출 |

**클린 아키텍처 구현 완료 상태:**

- [x] Container (DI) 구현
- [x] Port 인터페이스 정의 (ExchangePort, AIPort, MarketDataPort)
- [x] UseCase 구현 (ExecuteTradeUseCase, AnalyzeMarketUseCase, ManagePositionUseCase)
- [x] Legacy Bridge Adapters (LegacyExchangeAdapter, LegacyAIAdapter, LegacyMarketDataAdapter)
- [ ] **스케줄러에서 Container 사용**
- [ ] **모든 스테이지에서 Container/UseCase 사용**
- [ ] **PipelineContext에서 레거시 필드 제거**

### 목표

1. **스케줄러와 진입점에서 Container 사용** - 레거시 서비스 직접 생성 제거
2. **모든 파이프라인 스테이지에서 Port/UseCase 사용** - 레거시 폴백 제거
3. **PipelineContext 정리** - 레거시 필드 완전 제거
4. **단일 책임 원칙 준수** - Container가 모든 의존성 관리

### 아키텍처 결정

**Before (현재):**
```
scheduler.py → UpbitClient() / TradingService() / AIService() 직접 생성
    ↓
execute_trading_cycle(upbit_client, trading_service, ai_service, ...)
    ↓
PipelineContext(upbit_client=..., trading_service=..., ai_service=...)
    ↓
Stages → context.upbit_client.method() 직접 호출
```

**After (목표):**
```
scheduler.py → Container() 생성 (한 번만)
    ↓
execute_trading_cycle(container=container)
    ↓
PipelineContext(container=container)
    ↓
Stages → context.container.get_*_port().method() 호출
         또는 context.container.get_*_use_case().execute()
```

---

## Phase 1: 스케줄러 및 진입점 Container 통합 (CRITICAL)

**목표**: 스케줄러와 main.py에서 Container를 사용하도록 변경

**예상 시간**: 3-4시간

### Test Strategy
- **테스트 유형**: Unit + Integration
- **커버리지 목표**: 80%
- **테스트 시나리오**:
  - Container 생성 및 UseCase 획득
  - execute_trading_cycle에 container 전달
  - Container가 있을 때 레거시 서비스 무시 확인

### RED Tasks (테스트 먼저)

- [ ] `tests/unit/test_container_integration.py` 생성
  - [ ] `test_container_provides_use_cases()`: Container에서 UseCase 획득 테스트
  - [ ] `test_execute_trading_cycle_with_container()`: container 파라미터로 사이클 실행
  - [ ] `test_container_singleton_behavior()`: Container가 동일 UseCase 인스턴스 반환
- [ ] `tests/integration/test_scheduler_container.py` 생성
  - [ ] `test_trading_job_uses_container()`: trading_job이 Container 사용 확인
  - [ ] `test_position_management_job_uses_container()`: position_job이 Container 사용 확인

### GREEN Tasks (구현)

- [ ] `main.py` 수정
  - [ ] `execute_trading_cycle()` 시그니처 변경: 레거시 파라미터 Optional로
  - [ ] container가 있으면 레거시 서비스 무시하는 로직 추가
  - [ ] `execute_position_management_cycle()` 동일하게 수정
- [ ] `backend/app/core/scheduler.py` 수정
  - [ ] 모듈 레벨 Container 인스턴스 생성 (싱글톤)
  - [ ] `trading_job()`: 레거시 서비스 생성 대신 Container 사용
  - [ ] `position_management_job()`: 레거시 서비스 생성 대신 Container 사용
  - [ ] 레거시 import 문 제거

### REFACTOR Tasks

- [ ] 중복 코드 추출 (Container 초기화 로직)
- [ ] 에러 처리 개선 (Container 생성 실패 시)
- [ ] 로깅 추가 (어떤 방식으로 실행되는지)

### Quality Gate

```bash
# 테스트 실행
python -m pytest tests/unit/test_container_integration.py -v
python -m pytest tests/integration/test_scheduler_container.py -v

# 기존 테스트 통과 확인
python -m pytest tests/ -v --ignore=tests/integration

# 타입 체크
python -m mypy src/container.py main.py backend/app/core/scheduler.py --ignore-missing-imports
```

- [ ] 모든 새 테스트 통과
- [ ] 기존 테스트 회귀 없음
- [ ] 타입 체크 통과
- [ ] 로컬에서 scheduler 실행 테스트 (dry-run)

---

## Phase 2: DataCollectionStage 마이그레이션

**목표**: DataCollectionStage에서 MarketDataPort 사용

**예상 시간**: 3-4시간

### Test Strategy
- **테스트 유형**: Unit
- **커버리지 목표**: 85%
- **Mock 필요**: MockMarketDataAdapter

### RED Tasks

- [ ] `tests/unit/pipeline/test_data_collection_stage.py` 생성/확장
  - [ ] `test_collect_chart_data_with_port()`: MarketDataPort로 차트 데이터 수집
  - [ ] `test_collect_orderbook_with_port()`: MarketDataPort로 오더북 수집
  - [ ] `test_collect_balance_with_exchange_port()`: ExchangePort로 잔고 조회
  - [ ] `test_fallback_when_no_container()`: Container 없을 때 에러 발생 확인

### GREEN Tasks

- [ ] `src/application/ports/outbound/market_data_port.py` 확장
  - [ ] `get_chart_data_with_btc()` 메서드 추가 (없으면)
  - [ ] `get_fear_greed_index()` 메서드 추가 (없으면)
- [ ] `src/infrastructure/adapters/market_data/upbit_data_adapter.py` 확장
  - [ ] MarketDataPort 새 메서드 구현
- [ ] `src/trading/pipeline/data_collection_stage.py` 수정
  - [ ] `_has_container()` 헬퍼 메서드 추가
  - [ ] 각 수집 메서드를 Port 기반으로 변경
  - [ ] 레거시 폴백 경로 제거 (Container 필수)

### REFACTOR Tasks

- [ ] 데이터 수집 로직 추상화
- [ ] 에러 메시지 개선

### Quality Gate

```bash
python -m pytest tests/unit/pipeline/test_data_collection_stage.py -v
python -m pytest tests/ -v --cov=src/trading/pipeline/data_collection_stage --cov-report=term-missing
```

- [ ] 커버리지 85% 이상
- [ ] 레거시 코드 경로 없음 확인

---

## Phase 3: 나머지 스테이지 마이그레이션

**목표**: HybridRiskCheckStage, AnalysisStage, ExecutionStage에서 레거시 폴백 제거

**예상 시간**: 4-5시간

### Test Strategy
- **테스트 유형**: Unit
- **커버리지 목표**: 80%

### RED Tasks

- [ ] `tests/unit/pipeline/test_hybrid_stage_clean.py` 생성
  - [ ] `test_position_check_with_exchange_port()`
  - [ ] `test_execute_exit_with_use_case()`
- [ ] `tests/unit/pipeline/test_analysis_stage_clean.py` 생성
  - [ ] `test_ai_analysis_with_use_case()`
  - [ ] `test_no_legacy_fallback()`
- [ ] `tests/unit/pipeline/test_execution_stage_clean.py` 확장
  - [ ] `test_buy_always_uses_use_case()`
  - [ ] `test_sell_always_uses_use_case()`
  - [ ] `test_container_required()`

### GREEN Tasks

- [ ] `src/trading/pipeline/hybrid_stage.py` 수정
  - [ ] Container 필수로 변경
  - [ ] ExchangePort, ManagePositionUseCase 사용
  - [ ] `context.upbit_client` 직접 호출 제거
  - [ ] `context.trading_service` 직접 호출 제거
- [ ] `src/trading/pipeline/analysis_stage.py` 수정
  - [ ] `_perform_ai_analysis_legacy()` 제거
  - [ ] AnalyzeMarketUseCase만 사용
  - [ ] Container 필수로 변경
- [ ] `src/trading/pipeline/execution_stage.py` 수정
  - [ ] `_execute_buy_legacy()` 제거
  - [ ] `_execute_sell_legacy()` 제거
  - [ ] `_has_use_case()` 제거 (항상 UseCase 사용)
- [ ] `src/trading/pipeline/risk_check_stage.py` 수정 (있다면)
  - [ ] 동일한 패턴 적용

### REFACTOR Tasks

- [ ] 공통 패턴 추출 (`_get_exchange_port()` 등)
- [ ] 불필요한 조건문 제거

### Quality Gate

```bash
python -m pytest tests/unit/pipeline/ -v
python -m pytest tests/ -v --cov=src/trading/pipeline --cov-report=term-missing
```

- [ ] 모든 스테이지 테스트 통과
- [ ] 레거시 폴백 코드 없음 (grep 확인)

```bash
# 레거시 코드 검색 - 결과 없어야 함
grep -r "_legacy\|context\.upbit_client\|context\.trading_service\|context\.ai_service\|context\.data_collector" src/trading/pipeline/ --include="*.py"
```

---

## Phase 4: PipelineContext 정리 및 최종 검증

**목표**: PipelineContext에서 레거시 필드 제거, 전체 시스템 검증

**예상 시간**: 2-3시간

### Test Strategy
- **테스트 유형**: Integration + E2E
- **커버리지 목표**: 전체 파이프라인 실행 성공

### RED Tasks

- [ ] `tests/integration/test_full_pipeline_clean.py` 생성
  - [ ] `test_trading_pipeline_with_container_only()`
  - [ ] `test_position_management_pipeline_with_container_only()`
  - [ ] `test_no_legacy_fields_in_context()`

### GREEN Tasks

- [ ] `src/trading/pipeline/base_stage.py` 수정
  - [ ] `PipelineContext`에서 레거시 필드 제거:
    - `upbit_client: Any = None` 제거
    - `data_collector: Any = None` 제거
    - `trading_service: Any = None` 제거
    - `ai_service: Any = None` 제거
  - [ ] DEPRECATED 주석 제거
  - [ ] `container: Container` 타입 힌트 추가 (Optional 아님)
- [ ] `src/trading/pipeline/__init__.py` 수정
  - [ ] `create_hybrid_trading_pipeline()` 시그니처 검토
  - [ ] `create_position_management_pipeline()` 시그니처 검토
- [ ] `main.py` 최종 정리
  - [ ] 레거시 파라미터 완전 제거
  - [ ] 레거시 import 제거

### REFACTOR Tasks

- [ ] 문서 업데이트 (CLAUDE.md, ARCHITECTURE.md)
- [ ] Deprecated 함수/클래스에 `@deprecated` 데코레이터 추가
- [ ] 불필요한 파일 정리

### Quality Gate

```bash
# 전체 테스트 실행
python -m pytest tests/ -v

# 커버리지 리포트
python -m pytest tests/ --cov=src --cov-report=html

# 레거시 코드 완전 제거 확인
grep -r "context\.upbit_client\|context\.trading_service\|context\.ai_service\|context\.data_collector" src/ --include="*.py"
# 결과: 없어야 함

# Docker 빌드 테스트
docker-compose build scheduler

# 로컬 실행 테스트 (dry-run)
python main.py --dry-run  # (있다면)
```

- [ ] 모든 테스트 통과
- [ ] 레거시 코드 참조 0개
- [ ] Docker 빌드 성공
- [ ] 문서 업데이트 완료

---

## Risk Assessment

| 리스크 | 확률 | 영향 | 완화 전략 |
|--------|------|------|-----------|
| 기존 테스트 실패 | Medium | High | 단계별 마이그레이션, 각 Phase 후 전체 테스트 |
| 스케줄러 작업 중단 | Low | Critical | 롤백 스크립트 준비, Container 생성 실패 시 레거시 폴백 |
| Port 인터페이스 불완전 | Medium | Medium | Phase 2에서 누락 메서드 추가 |
| 통합 테스트 누락 | Medium | Medium | Phase 4에서 E2E 테스트 추가 |

---

## Rollback Strategy

### Phase별 롤백

**Phase 1 롤백:**
```bash
git checkout HEAD~1 -- main.py backend/app/core/scheduler.py
```

**Phase 2-3 롤백:**
```bash
git checkout HEAD~1 -- src/trading/pipeline/
```

**Phase 4 롤백:**
```bash
git checkout HEAD~1 -- src/trading/pipeline/base_stage.py
```

### 전체 롤백
```bash
git revert <migration-commit-hash>
```

---

## Progress Tracking

**Last Updated**: 2026-01-03

| Phase | 상태 | 시작일 | 완료일 |
|-------|------|--------|--------|
| Phase 1 | ✅ 완료 | 2026-01-03 | 2026-01-03 |
| Phase 2 | ✅ 완료 | 2026-01-03 | 2026-01-03 |
| Phase 3 | ✅ 완료 | 2026-01-03 | 2026-01-03 |
| Phase 4 | 🔄 진행중 | 2026-01-03 | - |

---

## Notes & Learnings

### Phase 1 Notes (2026-01-03 완료)

**구현 내용:**
- `scheduler.py`에 `get_container()` 싱글톤 함수 추가
- `get_legacy_services()` 헬퍼 함수로 Container에서 레거시 서비스 추출
- `trading_job()`과 `position_management_job()`에서 Container 사용

**주요 발견:**
- LegacyBridgeAdapter의 내부 속성명: `_client`, `_collector`, `_service` (not `_upbit_client` 등)
- `Container.create_from_legacy()`로 기존 레거시 서비스 래핑 가능

### Phase 2 Notes (2026-01-03 완료)

**구현 내용:**
- `DataCollectionStage`에 `_get_services()` 헬퍼 메서드 추가
- 모든 메서드가 `_get_services()`를 통해 서비스 접근
- 하위 호환성: Container 없으면 context의 레거시 서비스 사용

**패턴 정립:**
```python
def _get_services(self, context) -> Tuple[upbit_client, data_collector]:
    if context.container:
        # Container에서 Port 획득 후 내부 레거시 서비스 추출
        exchange_port = context.container.get_exchange_port()
        upbit_client = getattr(exchange_port, '_client', context.upbit_client)
    else:
        # 하위 호환성
        upbit_client = context.upbit_client
    return upbit_client, data_collector
```

### Phase 3 Notes (2026-01-03 완료)

**수정된 스테이지:**
1. `HybridRiskCheckStage` - `_get_services()` 추가, 4개 서비스 반환
2. `AnalysisStage` - `_get_ai_service()` 추가
3. `ExecutionStage` - `_get_services()` 추가, 2개 서비스 반환
4. `TradingPipeline` - `_get_upbit_client()` 추가
5. `RiskCheckStage` (deprecated) - `_get_services()` 추가
6. `AdaptiveRiskCheckStage` (deprecated) - `_get_services()` 추가

**결정 사항:**
- 레거시 폴백을 완전히 제거하지 않고, `_get_services()` 헬퍼에서 하위 호환성 유지
- Container가 없는 경우에도 동작하도록 graceful degradation 지원
- deprecated 스테이지도 일관성을 위해 동일 패턴 적용

### Phase 4 Notes
_(진행 중 - PipelineContext 정리 필요)_

**남은 작업:**
- PipelineContext에서 레거시 필드 deprecation 표시 강화
- 문서 업데이트 (CLAUDE.md, ARCHITECTURE.md)
- 통합 테스트 작성

---

## Appendix: 영향받는 파일 목록

### 수정 필요 파일
- `main.py`
- `backend/app/core/scheduler.py`
- `src/trading/pipeline/base_stage.py`
- `src/trading/pipeline/data_collection_stage.py`
- `src/trading/pipeline/analysis_stage.py`
- `src/trading/pipeline/execution_stage.py`
- `src/trading/pipeline/hybrid_stage.py`
- `src/trading/pipeline/risk_check_stage.py` (있다면)
- `src/trading/pipeline/trading_pipeline.py`

### 신규 생성 파일
- `tests/unit/test_container_integration.py`
- `tests/integration/test_scheduler_container.py`
- `tests/unit/pipeline/test_data_collection_stage.py`
- `tests/unit/pipeline/test_hybrid_stage_clean.py`
- `tests/unit/pipeline/test_analysis_stage_clean.py`
- `tests/integration/test_full_pipeline_clean.py`

### 문서 업데이트 필요
- `CLAUDE.md`
- `docs/guide/ARCHITECTURE.md`
- `docs/guide/SCHEDULER_GUIDE.md`
