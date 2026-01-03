# 테스트 구조 리팩토링 계획

**작성일**: 2026-01-03
**상태**: Completed
**완료일**: 2026-01-03

---

## 1. 클린 아키텍처 관점 현재 구조 리뷰

### 1.1 현재 테스트 구조

```
tests/
├── backend/                     # 백엔드 테스트 (scheduler, models)
│   └── app/core/test_scheduler.py  # ⚠️ 책임 과다
├── unit/
│   ├── domain/                  # ✅ 순수 도메인 로직 - 잘 구성됨
│   ├── application/             # ✅ UseCase, Port 테스트 - 잘 구성됨
│   ├── infrastructure/          # ✅ 어댑터 테스트 - 잘 구성됨
│   ├── presentation/            # ✅ CLI, Container 테스트
│   ├── pipeline/                # 파이프라인 스테이지 테스트
│   ├── container/               # DI 컨테이너 테스트
│   └── config/                  # 설정 테스트
├── integration/                 # DB/외부 연동 테스트
├── e2e/                         # ❌ 비어 있음
└── test_*.py (루트)             # ⚠️ 레거시 - 분류 필요
```

### 1.2 클린 아키텍처 준수 현황

| 계층 | 현재 상태 | 평가 |
|------|----------|------|
| **Domain Layer** | `tests/unit/domain/` (entities, services, value_objects) | ✅ 우수 |
| **Application Layer** | `tests/unit/application/` (use_cases, ports, services) | ✅ 우수 |
| **Infrastructure Layer** | `tests/unit/infrastructure/` (adapters, persistence) | ✅ 양호 |
| **Presentation Layer** | `tests/unit/presentation/` | ✅ 양호 |

### 1.3 현재 구조의 장점

1. **클린 아키텍처 계층 충실히 반영**
   - Domain, Application, Infrastructure, Presentation 분리
   - Port/Adapter 패턴 테스트 가능
   - DI Container 테스트 존재

2. **테스트 양과 품질이 우수**
   - 약 80개 이상의 테스트 파일
   - Given-When-Then 패턴 사용
   - Async 테스트 지원

3. **TDD 흔적이 있음**
   - `TDD Red Phase` 주석이 있는 테스트 존재
   - 실패 케이스 테스트 포함

### 1.4 현재 구조의 한계 (기관/상용 기준)

1. **'무엇을 보장하는 테스트인지' 불명확**
   - 폴더 기준이 "계층"이지 "위험/행위" 기준이 아님
   - 테스트 실패 시 비즈니스 영향도 파악 어려움

2. **같은 비즈니스 행위가 여러 폴더에 분산**
   - 트레이딩 사이클: unit/ + backend/ + integration/
   - 백테스팅: unit/backtesting/ + integration/

3. **test_scheduler.py 책임 과다**
   - 약 150줄 이상의 테스트
   - Unit + Integration + 운영 시나리오 혼합
   - 유지보수 시 가장 먼저 무너질 위험

4. **루트 레거시 테스트 미분류**
   - `tests/test_*.py` 약 15개 파일
   - 테스트 부채로 누적

5. **E2E 테스트 부재**
   - 실제 운용 흐름 검증 없음
   - Paper trading 테스트 불가

---

## 2. 신규 테스트 구조 설계

### 2.1 핵심 철학

> **"테스트를 보면, 이 시스템이 어떤 위험을 막고 있는지 바로 알 수 있게 만들 것"**

1. **테스트 폴더 = 위험/행위 단위**
2. **한 테스트 파일 = 하나의 책임**
3. **'돈이 새는 지점'은 계약(Contract)으로 고정**
4. **백테스트·실거래·스케줄러를 명확히 분리**

### 2.2 신규 구조

```
tests/
├── contracts/              # ❗ 반드시 지켜야 할 시스템 계약
│   ├── test_idempotency.py       # 중복 주문 방지 계약
│   ├── test_stop_loss.py         # 손절 계약
│   ├── test_position_limit.py    # 포지션 제한 계약
│   ├── test_fee_calculation.py   # 수수료 계산 정확성
│   └── test_order_validation.py  # 주문 검증 계약
│
├── scenarios/              # 트레이더 관점 핵심 시나리오
│   ├── test_entry_flow.py        # 진입 시나리오
│   ├── test_exit_flow.py         # 청산 시나리오
│   ├── test_hold_decision.py     # 홀드 결정 시나리오
│   └── test_multi_coin_flow.py   # 멀티코인 스캔 시나리오
│
├── backtesting/            # 체결/비용/인트라바 모델
│   ├── test_execution_model.py   # 체결 모델
│   ├── test_cost_model.py        # 비용 모델
│   ├── test_quick_filter.py      # 빠른 필터
│   └── test_backtest_accuracy.py # 백테스트 정확도
│
├── scheduler/              # 운영 안정성
│   ├── test_job_isolation.py     # 작업 격리
│   ├── test_lock_mechanism.py    # 락 메커니즘
│   ├── test_graceful_shutdown.py # 우아한 종료
│   └── test_recovery.py          # 장애 복구
│
├── unit/                   # 순수 로직 (기존 유지)
│   ├── domain/
│   ├── application/
│   ├── infrastructure/
│   └── presentation/
│
├── integration/            # DB/외부 연동 (기존 유지)
│   ├── adapters/
│   └── ...
│
└── e2e/                    # 실제 운용 흐름
    ├── test_paper_trading.py     # Paper trading 흐름
    └── test_full_cycle.py        # 전체 사이클 검증
```

### 2.3 신규 구조의 핵심 장점

| 카테고리 | 실패 시 의미 | 조치 |
|----------|-------------|------|
| `contracts/` | **시스템 계약 위반** | 거래 즉시 중단 |
| `scenarios/` | **비즈니스 로직 오류** | 배포 금지 |
| `backtesting/` | **백테스트 신뢰도 하락** | 실거래 금지 |
| `scheduler/` | **운영 안정성 위협** | 운영 중단 |
| `unit/` | **단위 로직 오류** | 해당 기능 점검 |
| `integration/` | **연동 오류** | 외부 시스템 확인 |
| `e2e/` | **전체 흐름 오류** | 전체 점검 |

---

## 3. 리팩토링 페이즈 계획

### Phase 1: contracts/ 폴더 생성 및 핵심 계약 승격 (2-3시간)

**목표**: 시스템의 핵심 계약을 명시적으로 정의

**TDD 전략**:
- 기존 테스트에서 "돈이 새는 지점" 관련 테스트 식별
- contracts/ 폴더로 복사 후 네이밍 정규화

**태스크**:
- [ ] `tests/contracts/` 폴더 생성
- [ ] `tests/contracts/__init__.py` 생성
- [ ] `tests/contracts/conftest.py` 생성 (공통 픽스처)
- [ ] Idempotency 계약 테스트 승격 (`test_idempotency_port.py` → `contracts/test_idempotency.py`)
- [ ] Stop-loss 계약 테스트 생성 (위험 관리 관련)
- [ ] Fee 계산 계약 테스트 승격 (`test_fee_calculator.py` → 계약으로)
- [ ] Position limit 계약 테스트 생성

**Quality Gate**:
- [ ] 모든 contracts/ 테스트 통과
- [ ] 기존 테스트 유지 (삭제 없음)
- [ ] 테스트 커버리지 유지

---

### Phase 2: scenarios/ 폴더 생성 및 비즈니스 시나리오 구성 (2-3시간)

**목표**: 트레이더 관점의 핵심 시나리오 정의

**TDD 전략**:
- 기존 pipeline, trading 테스트에서 시나리오 추출
- Given-When-Then 패턴 강화

**태스크**:
- [ ] `tests/scenarios/` 폴더 생성
- [ ] `tests/scenarios/__init__.py` 생성
- [ ] `tests/scenarios/conftest.py` 생성
- [ ] Entry flow 시나리오 테스트 구성
- [ ] Exit flow 시나리오 테스트 구성
- [ ] Hold decision 시나리오 테스트 구성
- [ ] Multi-coin flow 시나리오 통합

**Quality Gate**:
- [ ] 모든 scenarios/ 테스트 통과
- [ ] 시나리오당 최소 3개 케이스
- [ ] 기존 테스트 유지

---

### Phase 3: scheduler/ 폴더 분리 및 test_scheduler.py 분해 (2-3시간)

**목표**: test_scheduler.py 책임 분리로 유지보수성 향상

**TDD 전략**:
- 기존 test_scheduler.py 분석
- 책임별로 분리: job isolation, lock, shutdown, recovery

**태스크**:
- [ ] `tests/scheduler/` 폴더 생성
- [ ] `tests/scheduler/__init__.py` 생성
- [ ] `tests/scheduler/conftest.py` 생성
- [ ] TestSchedulerConfiguration → `scheduler/test_configuration.py`
- [ ] TestTradingJob → `scheduler/test_trading_job.py`
- [ ] Lock 관련 테스트 → `scheduler/test_lock_mechanism.py`
- [ ] 기존 `backend/app/core/test_scheduler.py`는 import redirect만 유지

**Quality Gate**:
- [ ] 분리된 모든 테스트 통과
- [ ] 기존 테스트 경로로도 실행 가능
- [ ] 테스트 커버리지 유지

---

### Phase 4: backtesting/ 폴더 정리 및 통합 (1-2시간)

**목표**: 백테스팅 관련 테스트를 한 곳으로 통합

**TDD 전략**:
- 기존 unit/backtesting/, integration/ 백테스트 테스트 통합
- 체결 모델, 비용 모델 분리

**태스크**:
- [ ] `tests/backtesting/` 폴더 정리 (기존 unit/backtesting/ 이동)
- [ ] `tests/backtesting/__init__.py` 확인/생성
- [ ] `tests/backtesting/conftest.py` 생성
- [ ] execution model 테스트 정리
- [ ] cost model 테스트 정리
- [ ] quick filter 테스트 통합

**Quality Gate**:
- [ ] 모든 backtesting/ 테스트 통과
- [ ] 백테스트 정확도 테스트 포함
- [ ] 기존 테스트 유지

---

### Phase 5: 루트 레거시 테스트 분류 및 승격 (2-3시간)

**목표**: tests/test_*.py 레거시 테스트를 적절한 위치로 이동

**TDD 전략**:
- 각 레거시 테스트 분석
- 적절한 카테고리로 승격 또는 unit/으로 이동

**태스크**:
- [ ] 레거시 테스트 목록 작성 및 분류
- [ ] 계약 관련 → contracts/로 승격
- [ ] 시나리오 관련 → scenarios/로 승격
- [ ] 순수 단위 테스트 → unit/으로 이동
- [ ] 통합 테스트 → integration/으로 이동
- [ ] 중복 테스트 정리 (deprecated 표시)

**Quality Gate**:
- [ ] 모든 이동된 테스트 통과
- [ ] 레거시 폴더 최소화
- [ ] 테스트 커버리지 유지

---

### Phase 6: e2e/ 폴더 활성화 및 Paper Trading 테스트 추가 (2-3시간)

**목표**: 실제 운용 흐름 검증 테스트 추가

**TDD 전략**:
- Paper trading 모드 테스트 작성
- Full cycle 검증 테스트 작성

**태스크**:
- [ ] `tests/e2e/__init__.py` 업데이트
- [ ] `tests/e2e/conftest.py` 생성 (Paper trading 픽스처)
- [ ] Paper trading flow 테스트 작성
- [ ] Full cycle 테스트 작성 (Mock 사용)
- [ ] E2E 테스트 마커 설정

**Quality Gate**:
- [ ] e2e/ 테스트 통과
- [ ] Paper trading 시나리오 최소 3개
- [ ] 전체 테스트 통과

---

### Phase 7: CLAUDE.md TDD 룰 업데이트 및 문서화 (1-2시간)

**목표**: 새 테스트 구조에 맞는 TDD 가이드라인 추가

**태스크**:
- [ ] CLAUDE.md에 신규 테스트 구조 반영
- [ ] 테스트 파일 생성 위치 가이드 추가
- [ ] 카테고리별 테스트 작성 가이드 추가
- [ ] 테스트 마커 규칙 업데이트
- [ ] conftest.py 픽스처 가이드 추가

**Quality Gate**:
- [ ] 문서 검토 완료
- [ ] 예시 코드 포함
- [ ] 전체 테스트 통과

---

## 4. 레거시 테스트 → 신규 구조 매핑 테이블

| 현재 위치 | 신규 위치 | 이동 방식 |
|-----------|----------|----------|
| `unit/application/ports/test_idempotency_port.py` | `contracts/test_idempotency.py` | 복사 후 승격 |
| `unit/application/ports/test_lock_port.py` | `scheduler/test_lock_mechanism.py` | 복사 후 승격 |
| `unit/domain/services/test_fee_calculator.py` | `contracts/test_fee_calculation.py` | 복사 후 승격 |
| `unit/domain/services/test_risk_calculator.py` | `contracts/test_risk_limits.py` | 복사 후 승격 |
| `unit/pipeline/*` | `scenarios/*` | 복사 후 시나리오화 |
| `backend/app/core/test_scheduler.py` | `scheduler/*` | 분해 후 이동 |
| `test_trading_service.py` (루트) | `unit/trading/test_service.py` | 이동 |
| `test_backtesting_*.py` (루트) | `backtesting/*` | 이동 |
| `integration/test_trading_flow.py` | `scenarios/test_trading_flow.py` | 복사 후 승격 |

---

## 5. 리스크 평가

| 리스크 | 확률 | 영향도 | 완화 전략 |
|--------|------|--------|----------|
| 테스트 실패 증가 | 낮음 | 중간 | 기존 테스트 삭제 없이 복사 방식 사용 |
| 중복 테스트 발생 | 중간 | 낮음 | 마이그레이션 완료 후 정리 |
| Import 경로 변경 | 중간 | 중간 | 기존 경로에 redirect 유지 |
| 커버리지 하락 | 낮음 | 높음 | 각 페이즈 후 커버리지 확인 |

---

## 6. 롤백 전략

각 페이즈는 **추가(additive)** 방식으로 진행:
- 기존 테스트 삭제 없음
- 새 폴더에 복사 후 승격
- 문제 발생 시 새 폴더만 삭제

---

## 7. 예상 소요 시간

| 페이즈 | 예상 시간 |
|--------|----------|
| Phase 1: contracts/ | 2-3시간 |
| Phase 2: scenarios/ | 2-3시간 |
| Phase 3: scheduler/ | 2-3시간 |
| Phase 4: backtesting/ | 1-2시간 |
| Phase 5: 레거시 분류 | 2-3시간 |
| Phase 6: e2e/ | 2-3시간 |
| Phase 7: CLAUDE.md | 1-2시간 |
| **총계** | **12-19시간** |

---

## 8. 다음 단계

사용자 승인 후:
1. Phase 1부터 순차적으로 진행
2. 각 페이즈 완료 시 Quality Gate 확인
3. 전체 테스트 실행 확인
4. CLAUDE.md 업데이트

---

**승인 대기 중**: 이 계획을 진행할까요?
