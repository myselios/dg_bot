# 통합 하이브리드 트레이딩 파이프라인 리팩토링 계획

**작성일**: 2026-01-02
**상태**: 계획 검토 중
**예상 소요**: 약 12-18시간 (5개 Phase)
**최종 수정**: 2026-01-02

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

## 1. 개요

### 1.1 목표
Mode 2(적응형 파이프라인)와 Mode 3(멀티코인 파이프라인)를 통합하여:
- 티커가 고정되지 않고 **동적으로 최적 코인을 선택**
- 포지션 유무에 따른 **ENTRY/MANAGEMENT 분기** 유지
- **하이브리드 포지션 관리** (규칙 기반 우선 + AI)
- 코드 중복 제거 및 유지보수성 향상

### 1.2 현재 상태

```
┌─────────────────────────────────────────────────────────────────┐
│                    현재: 3개의 분리된 파이프라인                   │
├─────────────────────────────────────────────────────────────────┤
│ Mode 1: create_spot_trading_pipeline (기존, 단일코인)             │
│ Mode 2: create_adaptive_trading_pipeline (적응형, 단일코인)       │
│ Mode 3: create_multi_coin_trading_pipeline (멀티코인, 동적)       │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 목표 상태

```
┌─────────────────────────────────────────────────────────────────┐
│            목표: 통합 하이브리드 파이프라인                        │
├─────────────────────────────────────────────────────────────────┤
│  create_hybrid_trading_pipeline (단일 진입점)                     │
│  ├── 옵션: enable_scanning=True/False                           │
│  ├── 옵션: max_positions=1~5                                    │
│  └── 옵션: ticker="KRW-ETH" (스캔 비활성화 시 사용)               │
└─────────────────────────────────────────────────────────────────┘
```

### 1.4 아키텍처 변경

```
┌─────────────────────────────────────────────────────────────────┐
│                  HybridRiskCheckStage (신규)                     │
│  AdaptiveRiskCheckStage의 기능 + 동적 티커 지원 통합              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                 ┌─────────────────┐                             │
│                 │ 포트폴리오 체크  │                             │
│                 └────────┬────────┘                             │
│                          │                                      │
│         ┌────────────────┼────────────────┐                     │
│         ▼                ▼                ▼                     │
│   [BLOCKED]       [MANAGEMENT]       [ENTRY]                    │
│   즉시 종료         포지션 관리       코인 스캔                   │
│                          │                │                     │
│                   ┌──────┴──────┐         │                     │
│                   ▼             ▼         ▼                     │
│             규칙 기반       AI 분석   CoinScanStage              │
│             (무료)         (유료)        │                      │
│                   │             │         │                     │
│                   └──────┬──────┘         │                     │
│                          ▼                ▼                     │
│                   청산/유지        context.ticker 업데이트       │
│                          │                │                     │
│                          └────────────────┘                     │
│                                  │                              │
│                                  ▼                              │
│                       DataCollectionStage                       │
│                                  │                              │
│                                  ▼                              │
│                         AnalysisStage                           │
│                                  │                              │
│                                  ▼                              │
│                        ExecutionStage                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Phase 구성

### Phase 1: 테스트 인프라 및 HybridRiskCheckStage 설계 (3-4시간)

**목표**: 통합 스테이지의 핵심 로직과 테스트 기반 구축

#### Test Strategy
- **테스트 타입**: Unit Tests
- **커버리지 목표**: 80%
- **테스트 파일**: `tests/unit/test_hybrid_risk_check_stage.py`

#### Tasks

**RED Phase (테스트 작성)**
- [ ] 1.1 `tests/unit/test_hybrid_risk_check_stage.py` 생성
  - [ ] `test_blocked_mode_returns_exit` - 서킷브레이커 발동 시 exit
  - [ ] `test_management_mode_handles_positions` - 포지션 관리 분기
  - [ ] `test_entry_mode_triggers_scan` - ENTRY 모드에서 스캔 트리거
  - [ ] `test_dynamic_ticker_update` - 스캔 후 ticker 업데이트 검증
  - [ ] `test_scan_disabled_uses_fixed_ticker` - 스캔 비활성화 시 고정 티커
  - [ ] `test_position_management_executes_before_scan` - 관리가 스캔보다 우선

**GREEN Phase (구현)**
- [ ] 1.2 `src/trading/pipeline/hybrid_stage.py` 생성
  - [ ] `HybridRiskCheckStage` 클래스 구현
  - [ ] `__init__` 파라미터: `enable_scanning`, `scanner_config`, 기존 리스크 파라미터
  - [ ] `execute()` 메서드: 포트폴리오 체크 → 모드 분기
  - [ ] `_handle_entry_with_scan()`: ENTRY 모드에서 코인 스캔 통합
  - [ ] `_handle_entry_without_scan()`: 고정 티커 사용 (기존 방식)

**REFACTOR Phase**
- [ ] 1.3 코드 정리
  - [ ] `AdaptiveRiskCheckStage`와 중복 로직 추출 → `BasePipelineStage` 확장
  - [ ] 포지션 관리 로직 재사용
  - [ ] 타입 힌트 완성

#### Quality Gate
- [ ] `python -m pytest tests/unit/test_hybrid_risk_check_stage.py -v` 통과
- [ ] 커버리지 80% 이상 (`--cov=src/trading/pipeline/hybrid_stage`)
- [ ] 타입 체크 통과 (mypy 또는 pyright)

#### Rollback Strategy
- Phase 1 실패 시: `hybrid_stage.py` 삭제, 테스트 파일 보관

---

### Phase 2: CoinScanStage 리팩토링 및 동기 래퍼 개선 (2-3시간)

**목표**: 비동기 이벤트 루프 문제 해결 및 스캔 스테이지 개선

#### Test Strategy
- **테스트 타입**: Unit + Integration Tests
- **커버리지 목표**: 75%
- **테스트 파일**: `tests/unit/test_coin_scan_stage.py`

#### Tasks

**RED Phase**
- [ ] 2.1 `tests/unit/test_coin_scan_stage.py` 개선
  - [ ] `test_sync_wrapper_no_event_loop` - 이벤트 루프 없을 때 정상 작동
  - [ ] `test_sync_wrapper_with_running_loop` - 실행 중 루프에서 정상 작동
  - [ ] `test_exclude_held_tickers` - 보유 코인 제외 검증
  - [ ] `test_empty_scan_returns_skip` - 스캔 결과 없을 때 skip 액션

**GREEN Phase**
- [ ] 2.2 `CoinScanStage` 리팩토링
  - [ ] `asyncio.get_event_loop()` → `asyncio.get_running_loop()` 패턴 수정
  - [ ] `nest_asyncio` 도입 검토 또는 `run_sync()` 헬퍼 구현
  - [ ] 예외 처리 강화 (네트워크 오류, 타임아웃)

- [ ] 2.3 스캔 결과 캐싱 도입
  - [ ] `ScanCache` 클래스 구현 (TTL 기반)
  - [ ] 동일 사이클 내 중복 스캔 방지

**REFACTOR Phase**
- [ ] 2.4 코드 정리
  - [ ] 불필요한 ThreadPoolExecutor 사용 제거
  - [ ] 로깅 개선

#### Quality Gate
- [ ] `python -m pytest tests/unit/test_coin_scan_stage.py -v` 통과
- [ ] `python -m pytest tests/test_coin_scan_stage.py -v` 통과
- [ ] 이벤트 루프 관련 경고/에러 없음

#### Rollback Strategy
- `coin_scan_stage.py` 백업 후 진행
- 실패 시 백업 파일 복원

---

### Phase 3: 통합 파이프라인 팩토리 함수 구현 (2-3시간)

**목표**: `create_hybrid_trading_pipeline` 팩토리 함수 및 기존 함수 제거

#### Test Strategy
- **테스트 타입**: Unit + Integration Tests
- **커버리지 목표**: 80%
- **테스트 파일**: `tests/test_trading_pipeline.py`

#### Tasks

**RED Phase**
- [ ] 3.1 `tests/test_trading_pipeline.py` 확장
  - [ ] `test_create_hybrid_pipeline_with_scanning` - 스캔 활성화 파이프라인
  - [ ] `test_create_hybrid_pipeline_without_scanning` - 스캔 비활성화 파이프라인
  - [ ] `test_hybrid_pipeline_stage_order` - 스테이지 순서 검증
  - [ ] `test_deprecated_functions_removed` - 기존 함수 제거 확인

**GREEN Phase**
- [ ] 3.2 `trading_pipeline.py` 수정
  - [ ] `create_hybrid_trading_pipeline()` 함수 구현
    ```python
    def create_hybrid_trading_pipeline(
        # 리스크 파라미터
        stop_loss_pct: float = -5.0,
        take_profit_pct: float = 10.0,
        daily_loss_limit_pct: float = -10.0,
        min_trade_interval_hours: int = 4,
        max_positions: int = 3,
        # 스캔 파라미터
        enable_scanning: bool = True,
        fallback_ticker: str = "KRW-ETH",
        liquidity_top_n: int = 20,
        min_volume_krw: float = 10_000_000_000,
        backtest_top_n: int = 5,
        final_select_n: int = 2
    ) -> TradingPipeline:
    ```
  - [ ] 스테이지 조합 로직 구현

- [ ] 3.3 기존 함수 제거
  - [ ] `create_spot_trading_pipeline` 삭제
  - [ ] `create_adaptive_trading_pipeline` → deprecated 경고 + `create_hybrid_trading_pipeline` 호출
  - [ ] `create_multi_coin_trading_pipeline` → deprecated 경고 + `create_hybrid_trading_pipeline` 호출

- [ ] 3.4 `__init__.py` 업데이트
  - [ ] 새 함수 export
  - [ ] 기존 함수 import 제거

**REFACTOR Phase**
- [ ] 3.5 코드 정리
  - [ ] docstring 완성
  - [ ] 파라미터 검증 추가

#### Quality Gate
- [ ] `python -m pytest tests/test_trading_pipeline.py -v` 통과
- [ ] `python -m pytest tests/ -v` 전체 테스트 통과 (regression 없음)
- [ ] import 오류 없음

#### Rollback Strategy
- Git stash로 변경사항 보관
- 실패 시 stash pop으로 복원

---

### Phase 4: main.py 및 execute_trading_cycle 리팩토링 (2-3시간)

**목표**: 진입점 단순화 및 통합 파이프라인 적용

#### Test Strategy
- **테스트 타입**: Integration Tests
- **커버리지 목표**: 70%
- **테스트 파일**: `tests/integration/test_trading_cycle.py`

#### Tasks

**RED Phase**
- [ ] 4.1 `tests/integration/test_trading_cycle.py` 생성
  - [ ] `test_execute_trading_cycle_with_scan` - 스캔 모드 사이클 실행
  - [ ] `test_execute_trading_cycle_fixed_ticker` - 고정 티커 사이클 실행
  - [ ] `test_execute_trading_cycle_mode_transition` - ENTRY → MANAGEMENT 전환
  - [ ] `test_legacy_params_work` - 기존 파라미터 호환성

**GREEN Phase**
- [ ] 4.2 `main.py` 리팩토링
  - [ ] `execute_trading_cycle` 시그니처 단순화
    ```python
    async def execute_trading_cycle(
        upbit_client: UpbitClient,
        data_collector: DataCollector,
        trading_service: TradingService,
        ai_service: AIService,
        # 옵션
        enable_scanning: bool = True,
        fallback_ticker: str = "KRW-ETH",
        max_positions: int = 3,
        **risk_params
    ) -> Dict[str, Any]:
    ```
  - [ ] 기존 `use_adaptive`, `use_multi_coin` 파라미터 제거
  - [ ] `trading_type` 파라미터 유지 (futures 미래 대비)

- [ ] 4.3 `main()` 함수 업데이트
  - [ ] 새 시그니처 적용
  - [ ] 환경변수 기반 설정 지원 추가

**REFACTOR Phase**
- [ ] 4.4 코드 정리
  - [ ] 주석 및 docstring 업데이트
  - [ ] 불필요한 분기 제거

#### Quality Gate
- [ ] `python -m pytest tests/integration/test_trading_cycle.py -v` 통과
- [ ] `python main.py --dry-run` 실행 성공 (dry-run 모드 필요 시 구현)
- [ ] 기존 스케줄러 코드와 호환

#### Rollback Strategy
- `main.py` 백업 후 진행
- Git으로 버전 관리

---

### Phase 5: AnalysisStage 범용화 및 최종 통합 테스트 (3-4시간)

**목표**: ETH 하드코딩 제거 및 E2E 테스트

#### Test Strategy
- **테스트 타입**: Integration + E2E Tests
- **커버리지 목표**: 75%
- **테스트 파일**: `tests/e2e/test_hybrid_pipeline_e2e.py`

#### Tasks

**RED Phase**
- [ ] 5.1 `tests/e2e/test_hybrid_pipeline_e2e.py` 생성
  - [ ] `test_full_pipeline_entry_mode` - 전체 ENTRY 플로우
  - [ ] `test_full_pipeline_management_mode` - 전체 MANAGEMENT 플로우
  - [ ] `test_pipeline_with_different_coins` - 다양한 코인으로 테스트
  - [ ] `test_market_correlation_for_any_coin` - BTC 상관관계 범용화 검증

**GREEN Phase**
- [ ] 5.2 `AnalysisStage` 수정
  - [ ] `_analyze_market_correlation` 메서드 수정
    - 하드코딩된 'eth' 참조 제거
    - `context.ticker` 기반 동적 분석
  - [ ] BTC-{coin} 상관관계 계산 범용화
  - [ ] 차트 데이터 키 동적 처리

- [ ] 5.3 `DataCollectionStage` 수정
  - [ ] `_collect_chart_data` 범용화
    - `get_chart_data_with_btc(context.ticker)` 이미 동적이지만 결과 키 확인

- [ ] 5.4 문서 업데이트
  - [ ] `CLAUDE.md` 아키텍처 섹션 업데이트
  - [ ] `docs/guide/ARCHITECTURE.md` 업데이트

**REFACTOR Phase**
- [ ] 5.5 최종 정리
  - [ ] `RiskCheckStage` 제거 (더 이상 사용 안함)
  - [ ] 불필요한 import 정리
  - [ ] 전체 코드 린팅

#### Quality Gate
- [ ] `python -m pytest tests/ -v` 전체 테스트 통과
- [ ] `python -m pytest tests/ --cov=src --cov-report=term-missing` 커버리지 70% 이상
- [ ] 린트 통과: `flake8 src/trading/pipeline/`
- [ ] 수동 테스트: 실제 환경에서 1회 사이클 실행

#### Rollback Strategy
- Git tag로 Phase 4 완료 시점 표시
- 실패 시 tag로 복원

---

## 3. 파일 변경 요약

### 신규 파일
| 파일 경로 | 설명 |
|-----------|------|
| `src/trading/pipeline/hybrid_stage.py` | HybridRiskCheckStage 구현 |
| `tests/unit/test_hybrid_risk_check_stage.py` | 유닛 테스트 |
| `tests/integration/test_trading_cycle.py` | 통합 테스트 |
| `tests/e2e/test_hybrid_pipeline_e2e.py` | E2E 테스트 |

### 수정 파일
| 파일 경로 | 변경 내용 |
|-----------|-----------|
| `src/trading/pipeline/trading_pipeline.py` | `create_hybrid_trading_pipeline` 추가, 기존 함수 제거 |
| `src/trading/pipeline/coin_scan_stage.py` | 동기 래퍼 개선 |
| `src/trading/pipeline/analysis_stage.py` | ETH 하드코딩 제거 |
| `src/trading/pipeline/__init__.py` | export 업데이트 |
| `main.py` | `execute_trading_cycle` 단순화 |

### 삭제 파일
| 파일 경로 | 사유 |
|-----------|------|
| `src/trading/pipeline/risk_check_stage.py` | HybridStage로 대체 |

---

## 4. 리스크 평가

| 리스크 | 확률 | 영향 | 완화 전략 |
|--------|------|------|-----------|
| 이벤트 루프 호환성 | 중 | 고 | nest_asyncio 도입, 철저한 테스트 |
| 기존 스케줄러 호환성 깨짐 | 중 | 고 | 시그니처 호환 래퍼 유지 |
| 포지션 관리 로직 regression | 저 | 고 | 기존 테스트 유지 및 확장 |
| AI 비용 증가 | 저 | 중 | 스캔 빈도 제한, 캐싱 도입 |

---

## 5. 성공 지표

1. **단일 진입점**: `create_hybrid_trading_pipeline` 하나로 모든 사용 케이스 커버
2. **동적 티커**: 스캔 결과에 따라 자동 코인 선택
3. **테스트 커버리지**: 전체 75% 이상
4. **Regression 없음**: 기존 테스트 100% 통과
5. **문서화 완료**: 아키텍처 문서 업데이트

---

## 6. Progress Tracking

| Phase | 상태 | 시작일 | 완료일 | 비고 |
|-------|------|--------|--------|------|
| Phase 1 | ⬜ 대기 | - | - | - |
| Phase 2 | ⬜ 대기 | - | - | - |
| Phase 3 | ⬜ 대기 | - | - | - |
| Phase 4 | ⬜ 대기 | - | - | - |
| Phase 5 | ⬜ 대기 | - | - | - |

---

## 7. Notes & Learnings

_각 Phase 완료 후 배운 점, 예상치 못한 이슈, 개선 아이디어를 기록합니다._

### Phase 1
- (작성 예정)

### Phase 2
- (작성 예정)

### Phase 3
- (작성 예정)

### Phase 4
- (작성 예정)

### Phase 5
- (작성 예정)
