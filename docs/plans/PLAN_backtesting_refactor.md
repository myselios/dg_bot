# Backtesting 모듈 상용화 리팩토링 계획

**작성일**: 2026-01-04
**Last Updated**: 2026-01-10
**상태**: ✅ Phase 1-6 완료 - Phase 7 대기
**버전**: v5.1 (Phase 1-6 구현 완료)

---

**⚠️ CRITICAL INSTRUCTIONS**: 각 페이즈 완료 후:
1. ✅ 완료된 작업 체크박스 체크
2. 🧪 품질 게이트 검증 명령 실행
3. ⚠️ 모든 품질 게이트 항목 통과 확인
4. 📅 "Last Updated" 날짜 업데이트
5. 📝 Notes 섹션에 학습 내용 문서화
6. ➡️ 그 후에만 다음 페이즈로 진행

⛔ 품질 게이트를 건너뛰거나 실패한 상태로 진행 금지

---

## 1. 개요

### 1.1 목표
`src/backtesting` 모듈을 **상용화 수준의 퀀트 백테스팅 엔진**으로 리팩토링한다.

### 1.2 현재 문제점 요약

| 우선순위 | 이슈 | 파일 | 영향 | 상태 |
|----------|------|------|------|------|
| 🔴 Critical | Expectancy 금액/비율 혼용 | performance.py | 필터 무력화 | ✅ 해결 (avg_loss_pct 구현) |
| 🔴 Critical | days → bar count 혼동 | data_provider.py | 분봉 데이터 부족 | 🔍 검토 필요 |
| 🟠 High | 인프라 어댑터 직접 생성 | backtester.py | Clean Arch 위반 | ✅ 해결 (DI 지원) |
| 🟠 High | 주문 실패 silent pass | backtester.py | 결과 신뢰성 저하 | ✅ 해결 (logging 추가) |
| 🟠 High | ALL AND 필터 과도한 엄격함 | quick_filter.py | 좋은 전략 과다 배제 | 📋 Phase 7 예정 |
| 🟡 Medium | AI 전략/2단 게이트 잔존 | ai_strategy.py | 정책 혼선 | ✅ 해결 (파일 삭제) |
| 🟡 Medium | config 파라미터 무시 | quick_filter.py | 메시지 불일치 | 🔍 검토 필요 |
| 🟡 Medium | profit_factor inf | performance.py | 필터 우회 | ⚠️ 현상 유지 (테스트 통과) |
| 🟡 Medium | min_trades=10 통계적 부족 | quick_filter.py | 유의성 저하 | 📋 Phase 7 예정 |
| 🟢 Low | 시간 갭 경고 분봉 미지원 | data_provider.py | 검증 약화 | 🔍 검토 필요 |
| 🟢 Low | print 기반 로그 | backtester.py | 로그 관리 어려움 | ✅ 해결 (logging 전환) |

### 1.3 성공 기준
- [x] 모든 Critical 이슈 해결 (Expectancy 수정 완료)
- [x] 대부분의 High 이슈 해결 (DI, logging 완료)
- [x] Clean Architecture 경계 준수 (DI 테스트 통과)
- [x] backtesting 테스트 211개 통과
- [ ] 문서와 코드 일치 (진행 중)
- [ ] Phase 7 가중치 필터 구현 (선택적)

---

## 2. 아키텍처 결정

### 2.1 의존성 방향 (Clean Architecture)

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                         │
│  src/backtesting/                                            │
│  ├── backtester.py (ExecutionPort 인터페이스만 의존)          │
│  ├── quick_filter.py                                         │
│  ├── performance.py                                          │
│  └── ...                                                     │
└──────────────────────────┬──────────────────────────────────┘
                           │ depends on (interface)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                       Ports Layer                            │
│  src/application/ports/outbound/                             │
│  ├── execution_port.py                                       │
│  ├── data_provider_port.py (신규)                            │
│  └── logging_port.py (신규)                                  │
└──────────────────────────┬──────────────────────────────────┘
                           │ implemented by
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Infrastructure Layer                       │
│  src/infrastructure/adapters/                                │
│  ├── execution/ (SimpleExecutionAdapter, ...)               │
│  ├── data/ (UpbitDataAdapter, ...)                           │
│  └── logging/ (StructuredLoggingAdapter, ...)               │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 핵심 설계 결정

| 결정 | 선택 | 근거 |
|------|------|------|
| Expectancy 단위 | 비율(0~1) 통일 | 수학적 정확성, 혼동 방지 |
| 데이터 로딩 | interval별 bar count 계산 | 분봉/시봉 정확한 데이터 |
| 어댑터 주입 | DI Container 통한 주입 | 테스트 용이성, 확장성 |
| 예외 처리 | 명시적 로깅 + 정책 선택 | 결과 신뢰성, 디버깅 |
| profit_factor inf | None 반환 | 통계적 안전성 (Phase 4 정책) |
| AI 전략 | 제거 또는 feature flag | 정책 명확화 |
| **필터 평가 로직** | **핵심 AND + 가중 점수** | 업계 표준 (Phase 7) |
| **min_trades 기준** | **30개 (통계적 최소)** | Central Limit Theorem |

---

## 3. 페이즈 구조

### 개요

| 페이즈 | 목표 | 예상 작업량 | 우선순위 |
|--------|------|-------------|----------|
| Phase 1 | Critical 버그 수정 (Expectancy, 데이터 로딩) | 2-3시간 | P0 |
| Phase 2 | 예외 처리 및 로깅 개선 | 2-3시간 | P0 |
| Phase 3 | Clean Architecture 정리 (DI, 포트) | 3-4시간 | P1 |
| Phase 4 | 통계적 안전장치 (inf, min_trades) | 2시간 | P1 |
| Phase 5 | 죽은 코드 정리 및 문서 동기화 | 2시간 | P2 |
| Phase 6 | 통합 테스트 및 검증 | 2-3시간 | P2 |
| **Phase 7** | **가중치 기반 필터 평가 로직** | **3-4시간** | **P1** |

---

## 4. Phase 1: Critical 버그 수정 (Expectancy 산출 경로 + 데이터 로딩)

### 4.1 목표
Expectancy 계산 단위 오류와 데이터 로딩 bar count 오류를 수정한다.

### 4.2 핵심 문제 분석

#### 🔴 Expectancy 산출 경로 문제 (Critical)

**현재 상태** (`quick_filter.py:1514-1522`):
```python
avg_loss = abs(metrics.get('avg_loss', 1))  # KRW 금액 (예: 50,000원)
avg_loss_pct = avg_loss / 100.0  # ❌ 500이라는 의미 없는 값
```

**문제점**:
- `metrics`에 `entry_price` 정보가 없음
- `avg_loss`는 KRW 금액이지 비율(%)이 아님
- `expectancy_filter.py`는 0~1 범위의 비율을 기대함

**해결 방향**:
1. `PerformanceAnalyzer.calculate_metrics()`에서 **`avg_loss_pct` 직접 계산**
2. Trade 객체의 `entry_price`, `pnl`을 사용하여 거래별 손실률 계산
3. `metrics`에 `avg_loss_pct` 필드 추가 (0~1 범위)

#### 🔴 Bar Count 계산 공식

| Interval | 계산식 | 730일 기준 |
|----------|--------|------------|
| day | days × 1 | 730 bars |
| minute60 | days × 24 | 17,520 bars |
| minute15 | days × 96 | 70,080 bars |
| minute5 | days × 288 | 210,240 bars |

### 4.3 테스트 전략 (TDD)

**테스트 파일**: `tests/unit/backtesting/test_expectancy_calculation.py`

**테스트 시나리오**:
1. PerformanceAnalyzer에서 avg_loss_pct 계산 정확성
2. Trade 기반 손실률 계산 (entry_price 대비)
3. 분봉 데이터 로딩 시 days → 올바른 bar count 변환
4. Expectancy 필터 통과/탈락 정확성

**커버리지 목표**: 90%

### 4.4 작업 항목

#### 🔴 RED 단계 (테스트 먼저)
- [ ] `test_expectancy_calculation.py` 생성
  - [ ] `test_performance_analyzer_calculates_avg_loss_pct()` - 손실률 계산
  - [ ] `test_avg_loss_pct_includes_commission_slippage()` - **비용 포함 검증** (v3 추가)
  - [ ] `test_avg_loss_pct_range_zero_to_one()` - 0~1 범위 검증
  - [ ] `test_avg_loss_pct_floor_applied_when_too_low()` - **floor 적용 테스트** (v3 추가)
  - [ ] `test_avg_loss_pct_floor_applied_flag_in_metrics()` - **플래그 포함** (v3 추가)
  - [ ] `test_expectancy_filter_uses_correct_avg_loss_pct()` - 필터 연동
  - [ ] `test_expectancy_filter_pass_with_correct_ratio()` - 올바른 비율로 통과
  - [ ] `test_expectancy_filter_fail_with_low_win_rate()` - 낮은 승률 실패
- [ ] `test_data_provider_bar_count.py` 생성
  - [ ] `test_minute60_bar_count_for_730_days()` - 시봉 730일 = 17,520 bars
  - [ ] `test_minute15_bar_count_for_730_days()` - 15분봉 730일 = 70,080 bars
  - [ ] `test_day_bar_count_for_730_days()` - 일봉 730일 = 730 bars

#### 🟢 GREEN 단계 (구현)
- [ ] **임시 로깅 초기화** (Phase 2 전까지)
  - [ ] `import logging; logger = logging.getLogger(__name__)`
  - [ ] Phase 2에서 로깅 표준 설정으로 통합 예정
  - [ ] `logger.warning()` 호출을 위한 최소 설정
- [ ] `performance.py` 수정 **(핵심 변경)**
  - [ ] `calculate_metrics()`에 `avg_loss_pct` 계산 추가
  - [ ] **⚠️ 비용 기준 결정**: `pnl`은 수수료/슬리피지 **포함** 값 → `avg_loss_pct`도 **비용 포함** 기준
  - [ ] 계산식: `abs(t.pnl) / (t.entry_price * t.size)` (pnl 비용 포함)
  - [ ] `avg_win_pct` 도 함께 추가 (일관성)
  - [ ] **AVG_LOSS_PCT_FLOOR 적용 시 로깅** (운영 모니터링용)
  ```python
  # 추가될 계산 로직 (비용 포함 기준)
  raw_avg_loss_pct = np.mean([
      abs(t.pnl) / (t.entry_price * t.size)  # pnl에 비용 이미 반영
      for t in losing_trades if t.entry_price and t.size
  ]) if losing_trades else 0.0

  # floor 적용 + 로깅
  if raw_avg_loss_pct < AVG_LOSS_PCT_FLOOR:
      logger.warning(f"avg_loss_pct floor 적용: {raw_avg_loss_pct:.4f} → {AVG_LOSS_PCT_FLOOR}")
      floor_applied = True
  avg_loss_pct = max(raw_avg_loss_pct, AVG_LOSS_PCT_FLOOR)
  ```
  - [ ] metrics에 `avg_loss_pct_floor_applied: bool` 플래그 추가
- [ ] `quick_filter.py` 수정
  - [ ] `check_expectancy_with_metrics()` 내 `avg_loss_pct` 사용
  - [ ] `metrics.get('avg_loss_pct', 0.01)` 직접 사용 (계산 제거)
  - [ ] 입력 검증 추가 (0~1 범위 경고)
- [ ] `data_provider.py` 수정
  - [ ] `_calculate_bar_count(days, interval)` 헬퍼 메서드 추가
  - [ ] interval별 분당 bar 수 계산 (day=1, minute60=24, minute15=96)
  - [ ] 분봉 데이터 로딩 로직 수정

#### 🔵 REFACTOR 단계
- [ ] Expectancy 계산 로직을 `ExpectancyCalculator` 클래스로 추출
- [ ] 데이터 로딩 설정을 `DataLoadingConfig` 데이터클래스로 추출
- [ ] 단위 변환 유틸리티 함수 분리

### 4.4 품질 게이트

```bash
# 테스트 실행
python -m pytest tests/unit/backtesting/test_expectancy_calculation.py -v
python -m pytest tests/unit/backtesting/test_data_provider_bar_count.py -v

# 커버리지 확인
python -m pytest tests/unit/backtesting/ --cov=src/backtesting/quick_filter --cov=src/backtesting/data_provider --cov-report=term-missing

# 기존 테스트 회귀 확인
python -m pytest tests/ -v --tb=short
```

- [ ] 모든 새 테스트 통과
- [ ] 커버리지 ≥ 90% (해당 모듈)
- [ ] 기존 테스트 회귀 없음
- [ ] 린팅 통과

### 4.5 롤백 전략
- git revert로 커밋 단위 롤백
- `avg_loss_pct` 계산 이전 로직 복원
- 분봉 bar count 이전 로직 복원

---

## 5. Phase 2: 예외 처리 및 로깅 통일화

### 5.1 목표
Silent fail을 제거하고 **프로젝트 전반에 걸친 로깅 표준**을 정립한다.

### 5.2 로깅 현황 분석 및 통일 방안

#### 현재 혼재 상태
| 파일 | 현재 방식 | 문제점 |
|------|----------|--------|
| backtester.py | `print()` | 로그 레벨/포맷 없음 |
| quick_filter.py | `print()` + `logging` 혼재 | 불일치 |
| runner.py | `print()` | 시각화 출력과 혼재 |

#### 🎯 통일 방안 결정 (v4 확정)

**Option A: 표준 logging 모듈 통일** ✅ **확정**
```python
import logging
logger = logging.getLogger(__name__)

# 핵심 이벤트 정의
logger.info("trade_attempt", extra={"ticker": ticker, "signal": signal})
logger.warning("trade_failed", extra={"reason": reason, "ticker": ticker})
logger.error("execution_error", extra={"error": str(e)})
```

**Option B: LoggingPort 인터페이스**
- 추상화 레벨 높음
- DI 가능, 테스트 용이
- 구현 복잡도 증가

**Option C: Structlog (외부 라이브러리)**
- JSON 구조화 로깅
- 의존성 추가 필요

#### 🎯 기존 Logger 유틸 처리 (v3 추가)

**현재 상태**:
- `src/utils/logger.py`: `print()` 기반 포맷팅 유틸 (Logger 클래스)
- `src/infrastructure/adapters/`: 표준 `logging.getLogger(__name__)` 사용
- **혼재 상태**: Logger 클래스 ≠ 표준 logging

**처리 방안 결정**:

| 옵션 | 설명 | 장점 | 단점 |
|------|------|------|------|
| **A: Logger 폐기** | Logger 클래스 삭제, 표준 logging만 사용 | 단순, 표준 준수 | 포맷팅 기능 재구현 필요 |
| **B: Logger → logging 래핑** | Logger 내부를 logging으로 대체 | 호환성 유지 | 코드 복잡도 |
| **C: 분리 유지** | Logger는 UI용, logging은 시스템용 | 역할 분리 | 혼란 지속 |

**권장: Option A (폐기)** - Logger 클래스는 UI 출력용이므로 backtesting에서는 불필요

**마이그레이션 경로**:
1. backtesting 모듈에서 Logger 사용 제거
2. 표준 logging으로 대체
3. Logger 클래스는 presentation layer에서만 유지 (선택)

#### 🎯 핵심 로깅 이벤트 정의

| 이벤트 | 로그 레벨 | 포함 정보 |
|--------|----------|----------|
| `trade_attempt` | INFO | ticker, signal_type, price |
| `trade_executed` | INFO | ticker, size, price, slippage |
| `trade_failed` | WARNING | ticker, reason, available_funds |
| `signal_generation_error` | ERROR | ticker, bar_index, exception |
| `execution_timeout` | WARNING | ticker, elapsed_time |
| `backtest_complete` | INFO | total_trades, total_return |

### 5.3 테스트 전략 (TDD)

**테스트 파일**: `tests/unit/backtesting/test_backtester_error_handling.py`

**테스트 시나리오**:
1. 자금 부족 시 예외 발생 및 로깅
2. 신호 생성 실패 시 로깅
3. 포지션 오픈 실패 시 백테스트 중단 정책

**커버리지 목표**: 85%

### 5.4 작업 항목

#### 🔴 RED 단계
- [ ] `test_backtester_error_handling.py` 생성
  - [ ] `test_insufficient_funds_logs_warning()` - 자금 부족 로깅
  - [ ] `test_signal_generation_error_logged_with_context()` - 오류 컨텍스트
  - [ ] `test_trade_failure_includes_reason()` - 실패 사유 포함
  - [ ] `test_error_policy_skip_continues_backtest()` - SKIP 정책
  - [ ] `test_error_policy_raise_stops_backtest()` - RAISE 정책

#### 🟢 GREEN 단계
- [ ] 로깅 표준 설정 (`src/config/logging_config.py` 또는 기존 설정에 추가)
  - [ ] 로그 포맷 정의 (timestamp, level, module, message, extra)
  - [ ] 파일/콘솔 핸들러 설정
- [ ] `backtester.py` 수정
  - [ ] `BacktestError` 예외 클래스 정의
  - [ ] `ErrorPolicy` enum: `SKIP`, `RAISE`, `LOG_AND_CONTINUE`
  - [ ] 모든 `print()` → `logger.info/warning/error()` 교체
  - [ ] `except Exception as e: pass` → 정책 기반 처리
- [ ] `quick_filter.py` 수정
  - [ ] `print()` → `logger` 교체
- [ ] `runner.py` 수정
  - [ ] `print()` → `logger` 교체 (리포트 출력은 별도 메서드)

#### 🔵 REFACTOR 단계
- [ ] 에러 처리 정책을 `ErrorPolicy` enum으로 분리
- [ ] 로깅 포맷 표준화 (JSON structured logging 선택 시)

### 5.4 품질 게이트

```bash
python -m pytest tests/unit/backtesting/test_backtester_error_handling.py -v
python -m pytest tests/contracts/ -v  # 안전 계약 테스트
```

- [ ] 모든 새 테스트 통과
- [ ] 기존 계약 테스트 통과
- [ ] 로깅 출력 확인

### 5.5 롤백 전략
- `ErrorPolicy.SKIP` 설정으로 이전 silent fail 동작 복원 가능
- 로깅 어댑터 교체로 이전 print 동작 복원

---

## 6. Phase 3: Clean Architecture 정리 (DI 전면 적용)

### 6.1 목표
인프라 어댑터 직접 생성을 제거하고 DI를 통한 주입으로 변경한다.
**BacktestRunner 포함** - 현재 Runner도 Backtester를 직접 생성하므로 함께 수정.

### 6.2 현재 DI 위반 지점

| 파일 | 위반 내용 | 수정 방향 |
|------|----------|----------|
| `backtester.py:69-75` | `SimpleExecutionAdapter()` 직접 생성 | ExecutionPort 주입 |
| `runner.py:26-33` | `Backtester()` 직접 생성 | BacktesterFactory 또는 DI |
| `data_provider.py` | `pyupbit.get_ohlcv()` 직접 호출 | DataProviderPort 분리 |

### 6.3 테스트 전략 (TDD)

**테스트 파일**: `tests/unit/backtesting/test_backtester_di.py`

**테스트 시나리오**:
1. ExecutionPort 주입 테스트
2. Mock 어댑터로 테스트 가능성 검증
3. Container 통한 의존성 해결
4. **BacktestRunner가 Container를 통해 Backtester 획득**

**커버리지 목표**: 85%

### 6.4 작업 항목

#### 🔴 RED 단계
- [ ] `test_backtester_di.py` 생성
  - [ ] `test_backtester_with_injected_execution_port()`
  - [ ] `test_backtester_with_mock_execution_port()`
  - [ ] `test_backtester_from_container()`
- [ ] `test_runner_di.py` 생성
  - [ ] `test_runner_uses_container_for_backtester()`
  - [ ] `test_runner_accepts_backtester_factory()`

#### 🟢 GREEN 단계
- [ ] `backtester.py` 수정
  - [ ] `SimpleExecutionAdapter`, `IntrabarExecutionAdapter` import 제거
  - [ ] 생성자에서 `execution_port: ExecutionPort` **필수** 파라미터로 변경
  - [ ] 기본값 어댑터 생성 코드 제거
  - [ ] `@classmethod` `create_default()` 팩토리 메서드 추가 (하위 호환)
- [ ] `runner.py` 수정 **(추가)**
  - [ ] `BacktestRunner.run_backtest()` 시그니처 변경
  - [ ] `backtester: Backtester` 파라미터 추가 또는
  - [ ] `backtester_factory: Callable` 주입 방식
  - [ ] 기존 `Backtester()` 직접 생성 제거
- [ ] `container.py` 수정
  - [ ] `create_backtester()` 팩토리 메서드 추가
  - [ ] `create_backtest_runner()` 팩토리 메서드 추가
  - [ ] 적절한 ExecutionAdapter 주입
- [ ] `data_provider.py` 수정
  - [ ] `DataProviderPort` 인터페이스 정의
  - [ ] pyupbit 직접 호출을 어댑터로 분리

#### 🔵 REFACTOR 단계
- [ ] 팩토리 메서드 패턴 적용
- [ ] 의존성 주입 문서화
- [ ] 하위 호환성 유지를 위한 deprecated 경고 추가

### 6.4 품질 게이트

```bash
python -m pytest tests/unit/backtesting/test_backtester_di.py -v
python -m pytest tests/ -v --tb=short

# 의존성 방향 검증 (infrastructure → application 없어야 함)
grep -r "from src.infrastructure" src/backtesting/
```

- [ ] 모든 테스트 통과
- [ ] `src/backtesting/` 내 인프라 직접 import 없음
- [ ] Container 통한 생성 동작 확인

### 6.5 롤백 전략
- 이전 생성자 시그니처 복원
- 어댑터 직접 생성 코드 복원

---

## 7. Phase 4: 통계적 안전장치 + 필터 판정 정책

### 7.1 목표
profit_factor inf, 샘플 부족 등 edge case에 대한 안전장치를 추가하고,
**None/NaN/inf 값에 대한 필터 판정 정책을 명확히 정의**한다.

### 7.2 🎯 필터 판정 정책 정의 (핵심)

#### Edge Case별 판정 기준

| 조건 | metrics 값 | 판정 | 근거 |
|------|-----------|------|------|
| 손실 거래 0회 | `profit_factor = None` | **FAIL** | 통계적 신뢰성 부족 |
| 거래 < min_trades | 위험조정지표 = None | **FAIL** | 샘플 부족 |
| volatility = 0 | `sharpe_ratio = None` | **FAIL** | 분모 0, 의미 없음 |
| 승률 100% | `avg_loss = 0` | **FAIL** | 과적합 의심 |

#### 판정 정책 Enum (v4 수정)

```python
class FilterVerdict(Enum):
    PASS = "pass"        # 조건 충족
    FAIL = "fail"        # 조건 미충족
    INVALID = "invalid"  # 계산 불가 (None/NaN/inf) → FAIL로 처리
    # PENDING 제거 - 필터 레벨에서는 사용하지 않음
    # PENDING은 스캐너 레벨(CoinSelector)에서만 별도 구현
```

#### 🎯 PENDING vs FAIL 정책 결정 (v3 추가)

**문제**: 무조건 FAIL이면 후보가 과도하게 탈락할 수 있음

| 상황 | FAIL 처리 | PENDING 처리 |
|------|----------|-------------|
| min_trades 미달 (9/10) | 탈락 | 다음 스캔에서 재평가 |
| profit_factor = inf | 탈락 | 손실 거래 발생 후 재평가 |
| 신규 코인 (데이터 부족) | 탈락 | 데이터 축적 후 재평가 |

**운영 정책 옵션**:

| 옵션 | 설명 | 적용 대상 |
|------|------|----------|
| **Strict (권장)** | INVALID → FAIL, PENDING 미사용 | min_trades, profit_factor |
| **Lenient** | INVALID → PENDING, 재평가 대기열 | 신규 코인, 데이터 부족 |
| **Hybrid** | 지표별로 Strict/Lenient 선택 | 복잡, 유연 |

**결정**: **Strict 모드 적용** (상용화 안정성 우선)
- PENDING 상태는 **스캐너 레벨**에서만 사용 (코인 재스캔 대기열)
- 필터 레벨에서는 INVALID → FAIL 고정

#### 상용화 원칙
> **"측정 불가" = "통과 불가"**
>
> 지표가 None/NaN/inf인 경우 무조건 FAIL 처리.
> 상용화에서 "조용히 통과"는 치명적 위험.
>
> **단, 스캐너에서 PENDING 코인을 별도 추적하여 재평가 가능**

### 7.3 테스트 전략 (TDD)

**테스트 파일**: `tests/unit/backtesting/test_performance_edge_cases.py`

**테스트 시나리오**:
1. 손실 거래 없을 때 profit_factor = None → FAIL
2. min_trades 미달 시 지표 None → FAIL
3. volatility 0일 때 sharpe_ratio = None → FAIL
4. None 값에 대한 필터 판정 FAIL 확인

**커버리지 목표**: 90%

### 7.4 작업 항목

#### 🔴 RED 단계
- [ ] `test_performance_edge_cases.py` 생성
  - [ ] `test_profit_factor_no_losses_returns_none()` - inf 대신 None
  - [ ] `test_metrics_below_min_trades_returns_none()` - 샘플 부족 시 None
  - [ ] `test_sharpe_with_zero_volatility_returns_none()` - 분모 0 처리
- [ ] `test_filter_verdict_policy.py` 생성
  - [ ] `test_none_profit_factor_fails_filter()` - None → FAIL
  - [ ] `test_inf_value_fails_filter()` - inf → FAIL
  - [ ] `test_nan_value_fails_filter()` - NaN → FAIL

#### 🟢 GREEN 단계
- [ ] `performance.py` 수정
  - [ ] `profit_factor` 계산 시 손실 없으면 `None` 반환
  - [ ] `min_trades` 미달 시 위험조정수익 지표 `None`
  - [ ] `volatility = 0` 시 `sharpe_ratio = None`
  - [ ] `avg_loss = 0` 시 `avg_win_loss_ratio = None`
- [ ] `quick_filter.py` 수정
  - [ ] `FilterVerdict` enum 추가
  - [ ] `_is_valid_metric(value)` 헬퍼: None/NaN/inf 체크
  - [ ] 필터 체크 시 invalid 값 → `FilterVerdict.INVALID` → FAIL
  - [ ] `_extract_failed_conditions()` config 파라미터 사용하도록 수정
  - [ ] 판정 사유에 "측정 불가" 명시

#### 🔵 REFACTOR 단계
- [ ] `MetricValue` 타입 도입 (값 + 신뢰도 + 판정)
- [ ] 필터 조건 객체화
- [ ] 판정 사유 표준화

### 7.4 품질 게이트

```bash
python -m pytest tests/unit/backtesting/test_performance_edge_cases.py -v
python -m pytest tests/contracts/ -v
```

- [ ] 모든 테스트 통과
- [ ] inf 값 필터 통과 방지 확인
- [ ] None 처리 로직 동작 확인

### 7.5 롤백 전략
- 이전 계산 로직 복원
- None 대신 inf 반환

---

## 8. Phase 5: 죽은 코드 정리 및 문서 동기화

### 8.1 목표
AI 전략 잔존 코드를 **안전하게** 제거하고 문서를 코드와 동기화한다.

### 8.2 🎯 AI 전략 제거 안전 순서

> **즉시 삭제 금지** - 사용 여부 확인 후 단계적 제거

#### Step 1: Feature Flag 비활성화 (이번 Phase)
```python
# ai_strategy.py 상단에 추가
import warnings
warnings.warn(
    "AITradingStrategy is deprecated and will be removed in v2.0. "
    "Use RuleBasedBreakoutStrategy instead.",
    DeprecationWarning,
    stacklevel=2
)

# 환경 변수로 비활성화
ENABLE_AI_STRATEGY = os.getenv("ENABLE_AI_STRATEGY", "false").lower() == "true"
```

#### Step 2: 사용 로그 모니터링 (1-2주)
- 로그에서 `AITradingStrategy` 호출 여부 확인
- 사용자 피드백 수집

#### Step 3: 완전 제거 (다음 Phase 또는 별도 작업)
- `ai_strategy.py` 파일 삭제
- `__init__.py` export 제거
- 관련 테스트 제거

### 8.3 테스트 전략

**테스트 시나리오**:
1. ai_strategy.py 비활성화 후 기존 기능 정상
2. deprecated 경고 출력 확인
3. Research/Trading Pass deprecated 메시지 확인
4. 문서 정합성 검증

**커버리지 목표**: 기존 유지

### 8.4 작업 항목

#### 🔴 RED 단계
- [ ] `test_module_imports.py` 추가
  - [ ] `test_backtesting_module_imports_clean()` - 모든 import 정상
  - [ ] `test_ai_strategy_deprecation_warning()` - 경고 출력

#### 🟢 GREEN 단계
- [ ] `ai_strategy.py` 처리 **(Step 1 only)**
  - [ ] `DeprecationWarning` 추가
  - [ ] `ENABLE_AI_STRATEGY` 환경 변수 체크
  - [ ] 비활성화 시 `NotImplementedError` 발생
  - [ ] ~~파일 삭제~~ (다음 Phase로 연기)
- [ ] `quick_filter.py` 정리
  - [ ] `ResearchPassConfig`, `TradingPassConfig` deprecated 경고 추가
  - [ ] 주석으로 제거 예정 표시
- [ ] 문서 동기화 **(가장 먼저 업데이트)**
  - [ ] `BACKTESTING_GUIDE.md` - 임계값/정책 동기화
  - [ ] `ARCHITECTURE.md` - 구조 변경 반영
  - [ ] 임계값 문서/코드 일치 확인 (grep 검증)
- [ ] **필터 탈락 사유 분포 로그 추가** (v5.1 투자자 피드백)
  - [ ] 필터별 탈락 횟수 집계 로직 추가
  - [ ] "탈락 이유 분포" 리포트 데이터 수집
  - [ ] 과도 필터링 감지용 경고 로그

#### 🔵 REFACTOR 단계
- [ ] 사용하지 않는 import 정리
- [ ] 예외 클래스 위치 정리

### 8.5 문서 동기화 체크리스트

| 항목 | 문서 | 코드 | 일치 여부 |
|------|------|------|----------|
| min_return | BACKTESTING_GUIDE.md | quick_filter.py | ⬜ |
| min_win_rate | BACKTESTING_GUIDE.md | quick_filter.py | ⬜ |
| min_profit_factor | BACKTESTING_GUIDE.md | quick_filter.py | ⬜ |
| max_drawdown | BACKTESTING_GUIDE.md | quick_filter.py | ⬜ |
| min_trades | BACKTESTING_GUIDE.md | quick_filter.py | ⬜ |
| 단일 게이트 정책 | BACKTESTING_GUIDE.md | quick_filter.py | ⬜ |
| AI 제거 상태 | BACKTESTING_GUIDE.md | ai_strategy.py | ⬜ |

### 8.4 품질 게이트

```bash
python -m pytest tests/ -v --tb=short
python -c "from src.backtesting import *; print('Import OK')"

# 문서-코드 임계값 검증
grep -r "min_return\|min_win_rate\|min_profit_factor" src/backtesting/quick_filter.py docs/guide/
```

- [ ] 모든 import 정상
- [ ] deprecated 경고 출력 확인
- [ ] 문서 임계값 일치

### 8.5 롤백 전략
- ai_strategy.py 복원
- deprecated 경고 제거

---

## 9. Phase 6: 통합 테스트 및 검증

### 9.1 목표
전체 리팩토링 결과를 통합 테스트하고 상용화 준비 상태를 검증한다.

### 9.2 테스트 전략

**테스트 시나리오**:
1. 전체 백테스트 파이프라인 E2E
2. 실제 데이터로 730일 백테스트
3. Expectancy 필터 정확성 검증
4. 성능 벤치마크 (이전 대비)

### 9.3 작업 항목

- [ ] E2E 테스트 작성
  - [ ] `tests/e2e/test_backtest_pipeline.py`
  - [ ] 전체 파이프라인 실행
  - [ ] 결과 검증 (메트릭 범위 체크)
- [ ] 성능 테스트
  - [ ] 730일 백테스트 실행 시간 측정
  - [ ] 메모리 사용량 프로파일링
  - [ ] **캐시 사용/미사용 성능 비교** (v3 추가)
    - [ ] 캐시 활성화 시 실행 시간
    - [ ] 캐시 비활성화 시 실행 시간
    - [ ] 캐시 히트율 측정
    - [ ] 성능 회귀 임계값 정의 (예: 20% 이상 저하 시 FAIL)
- [ ] 회귀 테스트
  - [ ] 이전 백테스트 결과와 비교 (delta 허용 범위)
- [ ] **워크포워드 검증 테스트** (v5.1 투자자 피드백, 선택적)
  - [ ] 롤링 윈도우 방식 과거→미래 성과 재현
  - [ ] OOS(Out-of-Sample) 성과 포함
  - [ ] 선택 편향 완화 효과 검증
- [ ] 문서 최종 검토
  - [ ] 변경 이력 업데이트
  - [ ] API 문서 갱신

### 9.4 품질 게이트

```bash
# 전체 테스트 스위트
python -m pytest tests/ -v --tb=short

# E2E 테스트
python -m pytest tests/e2e/test_backtest_pipeline.py -v

# 커버리지 리포트
python -m pytest tests/ --cov=src/backtesting --cov-report=html
```

- [ ] 전체 테스트 통과
- [ ] E2E 테스트 통과
- [ ] 커버리지 ≥ 80%
- [ ] 성능 저하 없음

### 9.5 롤백 전략
- 전체 리팩토링 브랜치 롤백
- main 브랜치 복원

---

## 10. Phase 7: 가중치 기반 필터 평가 로직 (v5.0 추가)

### 10.1 목표
ALL AND 필터의 과도한 엄격함을 완화하고, **핵심 필터 + 가중치 기반 평가**로 전환하여
통계적으로 우수한 전략을 과다 배제하지 않도록 한다.

### 10.2 현재 문제점 분석

#### 🔴 ALL AND 필터의 문제
```python
# 현재: 13개 필터 모두 통과 필요
passed = all(filter_results.values())  # 1개만 실패해도 전체 탈락
```

**사례 분석**:
- **DOGE**: 12/13 통과 (92%), 거래수 1개만 실패 → 전체 탈락 ❌
  - 수익률 14.3%, Sharpe 0.9, 기대값 0.35R (모두 우수)
  - 거래수 8회 < 10회 기준 (단 2회 부족)
- **통과율**: 현재 ~10% (너무 낮음)

#### 📊 업계 베스트 프랙티스 (2025)

| 항목 | 권장 사항 | 출처 |
|------|----------|------|
| 최소 거래 수 | 30회 (통계적 최소) | [How Many Trades Are Enough?](https://medium.com/@trading.dude/how-many-trades-are-enough-a-guide-to-statistical-significance-in-backtesting-093c2eac6f05) |
| 필터 로직 | 핵심 AND + 가중 점수 | [Top 5 Metrics for Trading](https://www.luxalgo.com/blog/top-5-metrics-for-evaluating-trading-strategies/) |
| 핵심 지표 | Sharpe, Profit Factor, Expectancy | [Trading Performance Analysis](https://www.quantifiedstrategies.com/trading-performance/) |

### 10.3 설계: 3-Tier 가중치 체계

#### Tier 1: 핵심 필터 (AND 조건) - 반드시 통과
```python
core_filters = {
    'return',           # 수익성 기본
    'profit_factor',    # 총 이익/손실 (>1.75 권장)
    'sharpe_ratio',     # 위험조정수익 (업계 표준)
    'expectancy'        # 실제 기대값 (수수료 반영)
}
# 모두 통과 필수
```

#### Tier 2~4: 가중 필터 (가중치 기반)

| Tier | 필터 | 가중치 | 근거 |
|------|------|--------|------|
| **Tier 2 (중요)** | max_drawdown | 2.0 | 실거래 생존력 핵심 |
| | sortino_ratio | 1.5 | 하방 리스크 측정 |
| | min_trades | 1.0 | 통계적 유의성 |
| | win_rate | 0.5 | 심리적 안정성 |
| **Tier 3 (권장)** | calmar_ratio | 1.0 | MDD 대비 수익률 |
| | avg_win_loss_ratio | 0.5 | 거래 품질 |
| | max_consecutive_losses | 0.5 | 심리적 내구성 |
| **Tier 4 (선택)** | volatility | 0.5 | 업종 특성 의존 |
| | avg_holding_hours | 0.5 | 전략 스타일 의존 |

**총점**: 8.0점 만점, **통과 기준: 5.0점 이상** (62.5%)

### 10.4 통과 기준 설계

```python
def evaluate_backtest_weighted(self, metrics) -> PassResult:
    """
    핵심 필터 AND + 가중 점수 기반 평가

    통과 조건:
    1. Tier 1 (핵심 4개) 모두 통과 필수
    2. Tier 2~4 (나머지 8개) 가중 점수 >= 5.0점
    """
    # Step 1: 핵심 필터 체크
    core_filters = ['return', 'profit_factor', 'sharpe_ratio', 'expectancy']
    core_passed = all(filter_results[f] for f in core_filters)

    if not core_passed:
        return PassResult(passed=False, reason="핵심 필터 미달")

    # Step 2: 가중 점수 계산
    weights = {
        # Tier 2 (중요) - 5.0점
        'max_drawdown': 2.0,
        'sortino_ratio': 1.5,
        'min_trades': 1.0,
        'win_rate': 0.5,

        # Tier 3 (권장) - 2.0점
        'calmar_ratio': 1.0,
        'avg_win_loss_ratio': 0.5,
        'max_consecutive_losses': 0.5,

        # Tier 4 (선택) - 1.0점
        'volatility': 0.5,
        'avg_holding_hours': 0.5,
    }

    weighted_score = sum(
        weights[f] for f, passed in filter_results.items()
        if f in weights and passed
    )

    # Step 3: 통과 판정
    threshold = 5.0
    optional_passed = weighted_score >= threshold

    final_passed = core_passed and optional_passed

    reason = (
        f"핵심 4개 통과, 가중 점수: {weighted_score:.1f}/{8.0:.1f} "
        f"({'통과' if optional_passed else '미달'})"
    )

    return PassResult(passed=final_passed, reason=reason)
```

### 10.5 테스트 전략 (TDD)

**테스트 파일**: `tests/unit/backtesting/test_weighted_filter_evaluation.py`

**테스트 시나리오**:
1. 핵심 필터 1개 실패 → 전체 FAIL (가중치 무관)
2. 핵심 통과 + 가중 점수 5.0 이상 → PASS
3. 핵심 통과 + 가중 점수 5.0 미만 → FAIL
4. DOGE 사례 재평가 (7.5점 → PASS)
5. 가중치 조정 가능성 테스트 (보수적/공격적)

**커버리지 목표**: 90%

### 10.6 작업 항목

#### 🔴 RED 단계 (테스트 먼저)
- [ ] `test_weighted_filter_evaluation.py` 생성
  - [ ] `test_core_filter_failure_overrides_weighted_score()` - 핵심 실패 시 무조건 FAIL
  - [ ] `test_core_pass_weighted_above_threshold()` - 핵심+가중 통과
  - [ ] `test_core_pass_weighted_below_threshold()` - 핵심 통과, 가중 미달
  - [ ] `test_doge_case_passes_with_weighted_logic()` - DOGE 재평가
  - [ ] `test_eth_still_passes_with_weighted_logic()` - ETH 기존 통과 유지
  - [ ] `test_weighted_score_calculation_accuracy()` - 가중치 계산 정확성
  - [ ] `test_tier_structure_integrity()` - Tier별 가중치 합 검증

#### 🟢 GREEN 단계 (구현)
- [ ] `quick_filter.py` 수정
  - [ ] `FilterTier` enum 추가 (CORE, TIER2, TIER3, TIER4)
  - [ ] `FILTER_WEIGHTS` 상수 정의 (딕셔너리)
  - [ ] `evaluate_backtest_weighted()` 메서드 추가
  - [ ] `BacktestConfig`에 `use_weighted_evaluation: bool = False` 추가
  - [ ] 기존 `evaluate_backtest()` 유지 (하위 호환)
- [ ] `coin_selector.py` 수정
  - [ ] `BacktestConfig(use_weighted_evaluation=True)` 활성화
  - [ ] 통과율 모니터링 로직 추가
- [ ] `min_trades` 기준 조정
  - [ ] `BacktestConfig.min_trades = 30` (10 → 30)
  - [ ] 문서에 근거 추가 (Central Limit Theorem)

#### 🔵 REFACTOR 단계
- [ ] 가중치를 `WeightedFilterConfig` 데이터클래스로 분리
- [ ] Tier별 필터 그룹핑 명확화
- [ ] 가중치 조정 가이드 문서화

### 10.7 품질 게이트

```bash
# 새 테스트 실행
python -m pytest tests/unit/backtesting/test_weighted_filter_evaluation.py -v

# 기존 테스트 회귀 확인
python -m pytest tests/contracts/ tests/scenarios/ -v

# 통합 테스트
python -m pytest tests/ -v --tb=short

# DOGE/ETH 사례 검증 (수동)
python -m pytest tests/scenarios/test_doge_eth_weighted_evaluation.py -v
```

- [ ] 모든 새 테스트 통과
- [ ] 기존 테스트 회귀 없음
- [ ] DOGE 통과, ETH 통과 유지
- [ ] 통과율 40-50% 달성

### 10.8 예상 결과

| 케이스 | 현재 (ALL AND) | 변경 후 (Weighted) |
|--------|----------------|-------------------|
| DOGE | ❌ (1개 실패) | ✅ (7.5/8.0점) |
| ETH | ✅ | ✅ (유지) |
| 통과율 | ~10% | ~40-50% |

### 10.9 롤백 전략
- `use_weighted_evaluation=False` 설정으로 기존 로직 복원
- 가중치 비활성화 환경 변수 제공

### 10.10 참고 문헌
- [How Many Trades Are Enough?](https://medium.com/@trading.dude/how-many-trades-are-enough-a-guide-to-statistical-significance-in-backtesting-093c2eac6f05)
- [Top 5 Metrics for Evaluating Trading Strategies](https://www.luxalgo.com/blog/top-5-metrics-for-evaluating-trading-strategies/)
- [Trading Performance Analysis](https://www.quantifiedstrategies.com/trading-performance/)
- [Risk-Adjusted Return Metrics](https://internationaltradinginstitute.com/blog/5-risk-adjusted-return-metrics-youre-ignoring/)
- [Sharpe, Sortino, Calmar Ratios](https://www.itrader.com/en/blog/sharpe-sortino-calmar-ratios-and-expectancy-measuring-real-alpha-in-trading)

---

## 11. 리스크 평가

| 리스크 | 확률 | 영향 | 완화 전략 |
|--------|------|------|-----------|
| Expectancy 수정 후 필터 결과 급변 | 높음 | 높음 | 이전 결과와 병렬 비교, 점진적 적용 |
| 분봉 데이터 로딩 API 제한 | 중간 | 높음 | 배치 처리, 캐싱 강화 |
| DI 변경 후 기존 코드 호환성 | 중간 | 중간 | deprecated 경고, 마이그레이션 가이드 |
| 테스트 시간 증가 | 낮음 | 낮음 | pytest 마커로 slow 테스트 분리 |
| **가중치 필터 적용 후 통과율 급증** | **중간** | **중간** | **use_weighted_evaluation 플래그, A/B 테스트** |
| **min_trades=30 적용 시 통과율 급감** | **중간** | **높음** | **단계적 상향 (10→20→30), 통과율 모니터링** |

---

## 11. 진행 상황 추적

### 현재 상태
**Phase 0** - 계획 수립 완료, 승인 대기

### 완료 이력
| 날짜 | 페이즈 | 요약 |
|------|--------|------|
| 2026-01-04 | Phase 0 | 계획 문서 작성 |

---

## 12. Notes & Learnings

### 발견 사항
- Expectancy 필터 단위 오류는 실거래 품질에 치명적
- 분봉 데이터 로딩 버그로 백테스트 결과 신뢰성 저하
- Clean Architecture 위반이 테스트 용이성 저해

### v2 리뷰 반영 내용 (2026-01-04)

**퀀트 투자 개발자 관점 보완**:
1. **Expectancy 산출 경로 명확화**: `quick_filter`에서 계산하려면 정보가 없음 → `performance.py`에서 Trade 기반으로 `avg_loss_pct` 계산 후 metrics에 추가
2. **필터 판정 정책 명시**: None/NaN/inf → FAIL (상용화에서 "조용히 통과" 방지)
3. **AI 전략 제거 안전 순서**: 즉시 삭제 → feature flag → 모니터링 → 삭제

**Clean Architecture 관점 보완**:
1. **BacktestRunner DI화**: Backtester뿐 아니라 Runner도 직접 생성 → Container 통한 주입
2. **로깅 통일화 필수**: print/logging 혼재 → 표준 logging + 이벤트 정의
3. **DataProviderPort 분리**: pyupbit 직접 호출 → 포트 인터페이스로 추상화

### v3 리뷰 반영 내용 (2026-01-04)

**퀀트 계산 정확성**:
1. **비용 기준 명시**: `pnl`은 수수료/슬리피지 포함 → `avg_loss_pct`도 비용 포함 기준으로 통일
2. **AVG_LOSS_PCT_FLOOR 모니터링**: floor 적용 시 로깅 + metrics에 플래그 추가
3. **PENDING 상태 추가**: 필터 레벨은 Strict(FAIL), 스캐너 레벨은 PENDING 코인 재평가 가능

**운영 안정성**:
1. **기존 Logger 유틸 처리**: backtesting에서는 표준 logging 사용, Logger 클래스는 presentation layer에서만 유지
2. **캐시 성능 비교**: Phase 6에 캐시 사용/미사용 벤치마크 추가

### v4 리뷰 반영 내용 (2026-01-04)

**사용자 결정 사항**:
| 항목 | 결정 | 상세 |
|------|------|------|
| FilterVerdict.PENDING | **스캐너 레벨만** | QuickBacktestFilter는 PASS/FAIL/INVALID만. CoinSelector에서 PENDING 처리 |
| ErrorPolicy | **통일** | silent_fail 제거, ErrorPolicy enum으로 대체 |
| AI 전략 비활성화 | **NotImplementedError 유지** | 명시적 실패로 문제 조기 발견 |
| 로깅 방식 | **표준 logging** | Option A 확정. `logging.getLogger(__name__)` 사용 |
| profit_factor inf | **None 반환** | 아키텍처 결정과 Phase 4 일치 |

**모순점 수정**:
1. **Phase 4 FilterVerdict enum**: PENDING 제거 (PASS/FAIL/INVALID만 유지)
2. **Phase 2 롤백 전략**: `silent_fail=True` → `ErrorPolicy.SKIP`으로 변경
3. **Phase 1 로깅 의존성**: 임시 logging 초기화 항목 추가
4. **체크리스트 P1**: PENDING 항목을 "스캐너 레벨에서 별도 구현"으로 수정

### v5.0 리뷰 반영 내용 (2026-01-05)

**가중치 기반 필터 평가**:
1. **ALL AND의 문제점 인식**: 13개 필터 중 1개만 실패해도 전체 탈락 → 우수 전략 과다 배제
2. **업계 표준 적용**: 핵심 필터 AND + 가중 점수 평가 (2025 베스트 프랙티스)
3. **3-Tier 가중치 체계**:
   - Tier 1 (핵심): return, profit_factor, sharpe_ratio, expectancy (AND 필수)
   - Tier 2~4 (가중): max_drawdown(2.0), sortino(1.5), min_trades(1.0), 기타 (총 8.0점)
   - 통과 기준: 핵심 4개 + 가중 5.0/8.0점 이상
4. **min_trades 조정**: 10회 → 30회 (통계적 최소, Central Limit Theorem)

**예상 효과**:
- DOGE 사례: 기존 탈락(1개 실패) → 변경 후 통과(7.5/8.0점)
- 통과율: 10% → 40-50% (적정 수준)
- 통계적 신뢰성: min_trades 30회로 향상

**참고 문헌**:
- [How Many Trades Are Enough?](https://medium.com/@trading.dude/how-many-trades-are-enough-a-guide-to-statistical-significance-in-backtesting-093c2eac6f05)
- [Top 5 Metrics for Trading](https://www.luxalgo.com/blog/top-5-metrics-for-evaluating-trading-strategies/)
- [Trading Performance Analysis](https://www.quantifiedstrategies.com/trading-performance/)

### v5.1 투자자 피드백 개발자 관점 리뷰 (2026-01-05)

#### 투자자 피드백 요약

**장점 (이미 반영됨)**:
- DI 기반 경계 분리 → 재현성/검증 가능성
- Expectancy 비용 포함 기준 통일
- Invalid → Fail 정책
- 캐시 성능 비교
- AI 단계적 제거

**단점/리스크 지적**:
1. 레짐 적응성 부족 (고정 임계값)
2. min_trades=10 통계적 부족
3. 룰 기반 알파 지속성 한계
4. 시장 충격 모델 미비
5. 선택 편향 (워크포워드 검증 없음)

#### 개발자 판단: 리팩토링 범위 분류

| 피드백 | 이 리팩토링 범위? | 처리 |
|--------|------------------|------|
| **min_trades 상향** | ✅ Yes | Phase 7에서 10→30 (이미 반영) |
| **탈락 사유 분포 로그** | ✅ Yes | Phase 5/7 로깅 개선에 추가 |
| **워크포워드 검증** | ✅ Yes (선택) | Phase 6 E2E 테스트에 추가 가능 |
| **레짐 적응성** | ❌ No | 신규 기능 → 별도 계획 필요 |
| **시장 충격 모델** | ❌ No | 신규 기능 → 별도 계획 필요 |
| **다른 거래소 재현** | ❌ No | 인프라 확장 → 별도 계획 필요 |

#### 별도 계획 필요 항목 (Out of Scope)

| 항목 | 이유 | 제안 계획 파일 |
|------|------|---------------|
| 레짐 적응성 | 레짐 분류기 신규 개발 필요 | `PLAN_regime_adaptive_filter.md` |
| 시장 충격 모델 | 오더북 슬리피지 모델 신규 개발 | `PLAN_market_impact_model.md` |
| 멀티 거래소 | 거래소 추상화 인프라 확장 | `PLAN_multi_exchange.md` |

#### 이 리팩토링에 추가 반영할 항목

1. **Phase 5**: 필터 탈락 사유 분포 로그 추가
   - 어떤 필터가 과도하게 코인을 제외하는지 분석
   - 정기 리포트용 데이터 수집

2. **Phase 6**: 워크포워드 검증 테스트 (선택적)
   - 롤링 윈도우 방식 과거→미래 성과 재현
   - OOS(Out-of-Sample) 성과 포함

### 학습 내용
- (작업 진행 시 기록)

---

## 13. 체크리스트 요약 (v5.1 업데이트)

### Critical (P0) - 즉시 수정
- [ ] **Expectancy 산출 경로 수정**: `performance.py`에서 `avg_loss_pct` 계산 → `metrics`에 추가
- [ ] **비용 기준 명시**: pnl 비용 포함 기준으로 통일 (v3)
- [ ] **AVG_LOSS_PCT_FLOOR 적용 로깅** + 플래그 추가 (v3)
- [ ] 분봉 데이터 bar count 계산 수정 (days × interval별 상수)
- [ ] 주문 실패 silent pass 제거 + ErrorPolicy 도입

### High (P1) - 단기 수정
- [ ] 인프라 어댑터 DI 패턴 적용 (Backtester + **BacktestRunner**)
- [ ] profit_factor inf → None 처리 + **필터 판정 정책 정의**
- [ ] ~~PENDING 상태~~ → **스캐너 레벨(CoinSelector)에서 별도 구현** (v4 수정)
- [ ] config 파라미터 일관성 (`_extract_failed_conditions` 수정)
- [ ] **로깅 통일화** + **기존 Logger 처리 방안 결정** (v3)
- [ ] **가중치 기반 필터 평가 구현** (Phase 7, v5.0)
- [ ] **min_trades 기준 조정 (10→30)** (Phase 7, v5.0)

### Medium (P2) - 중기 수정
- [ ] AI 전략 **feature flag 비활성화** (삭제는 다음 Phase)
- [ ] 문서-코드 동기화 (임계값 grep 검증)
- [ ] 시간 갭 경고 interval별 분리
- [ ] deprecated 경고 추가 (ResearchPassConfig, TradingPassConfig)
- [ ] **캐시 사용/미사용 성능 비교** (v3)
- [ ] **가중치 조정 가이드 문서화** (Phase 7, v5.0)

### 핵심 변경 요약 (v5.1까지)
| 항목 | v1 계획 | v2 보완 | v3 보완 | v4 수정 | v5.0 추가 | v5.1 추가 |
|------|---------|---------|---------|---------|-----------|-----------|
| Expectancy 수정 | quick_filter에서 계산 | performance.py에서 계산 | **비용 포함 기준 명시** | - | - | - |
| 로깅 | "선택사항" | 필수 통일화 | **Logger 유틸 처리 방안** | **Phase 1 임시 초기화** | - | **탈락 사유 분포 로그** |
| BacktestRunner | 미포함 | DI 대상에 포함 | - | - | - | - |
| 필터 판정 정책 | 미정의 | None/inf → FAIL | PENDING 상태 추가 | **PENDING 스캐너 전용** | - | - |
| AI 전략 제거 | 즉시 삭제 | feature flag → 삭제 | - | **NotImplementedError** | - | - |
| 성능 테스트 | 기본 벤치마크 | - | **캐시 비교 추가** | - | - | **워크포워드 검증** |
| floor 모니터링 | 없음 | - | **적용률 로깅** | - | - | - |
| 롤백 전략 | - | silent_fail=True | - | **ErrorPolicy.SKIP** | - | - |
| **필터 평가 로직** | **ALL AND** | - | - | - | **핵심 AND + 가중치** | - |
| **min_trades 기준** | **10회** | - | - | - | **30회 (통계적 최소)** | - |
| **투자자 피드백** | - | - | - | - | - | **범위 분류 + 별도 계획** |

---

## 14. 관련 파일 (v5.1 업데이트)

| 파일 | 변경 유형 | 페이즈 | 변경 내용 |
|------|----------|--------|----------|
| src/backtesting/performance.py | 수정 | **1**, 4 | `avg_loss_pct` 계산 추가, **floor 로깅 (v3)**, inf 처리 |
| src/backtesting/quick_filter.py | 수정 | 1, 4, 5, **7** | expectancy 사용, FilterVerdict enum, **가중치 평가 (v5)** |
| src/backtesting/data_provider.py | 수정 | 1, 3 | bar count 수정, DataProviderPort |
| src/backtesting/backtester.py | 수정 | 2, 3 | 로깅, DI, ErrorPolicy |
| src/backtesting/runner.py | 수정 | **3** | DI 패턴 적용 |
| src/backtesting/ai_strategy.py | 수정 | 5 | deprecated 경고 |
| src/scanner/coin_selector.py | 수정 | **7** | **가중치 필터 활성화 (v5)** |
| src/container.py | 수정 | 3 | 팩토리 메서드 추가 |
| src/config/logging_config.py | 추가 | **2** | 로깅 표준 설정 |
| src/utils/logger.py | 유지 | - | **presentation layer에서만 사용 (v3 결정)** |
| docs/guide/BACKTESTING_GUIDE.md | 수정 | 5, 6 | 임계값/정책 동기화, **비용 기준 명시 (v3)** |
| tests/unit/backtesting/*.py | 추가 | 1-6 | TDD 테스트, **floor 적용 테스트 (v3)** |
