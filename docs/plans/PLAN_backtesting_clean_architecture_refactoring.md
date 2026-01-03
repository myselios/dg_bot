# 백테스팅 모듈 클린 아키텍처 리팩토링 계획

작성일: 2026-01-03

---

## 1. 현재 구조 분석 (Clean Architecture 관점)

### 1.1 현재 파일 구조 (src/backtesting/)

```
src/backtesting/
├── strategy.py           # Signal, Strategy ABC
├── portfolio.py          # Position, Trade, Portfolio
├── backtester.py         # Backtester 엔진
├── performance.py        # PerformanceAnalyzer
├── rule_based_strategy.py # RuleBasedBreakoutStrategy (1100+ LOC)
├── ai_strategy.py        # AI 기반 전략
├── quick_filter.py       # 빠른 필터링
├── data_provider.py      # 데이터 제공자
└── runner.py             # 실행기
```

### 1.2 클린 아키텍처 위반 사항

| 위반 유형 | 현재 상태 | 문제점 |
|-----------|----------|--------|
| **도메인 중복** | `backtesting/portfolio.py`에 Trade, Position 정의 | `domain/entities/trade.py`에 이미 동일 엔티티 존재 |
| **인프라 의존** | `Backtester`가 직접 pandas DataFrame 사용 | 프레임워크에 종속, 테스트 어려움 |
| **시간 결합** | `datetime.now()` 직접 호출 | 테스트 불가, 시간축 왜곡 원인 |
| **SRP 위반** | `RuleBasedBreakoutStrategy` 1100줄 | 지표계산+포지션관리+슬리피지+분할주문 혼재 |
| **DIP 위반** | `TechnicalIndicators` 직접 호출 | 인프라 계층 직접 참조 |
| **포트 부재** | 체결 로직 하드코딩 | 교체/테스트 불가능 |

---

## 2. 문서(03_backtesting_volatility_breakout.md) 치명적 한계 매핑

### 2.1 시간축 왜곡 (Critical)

**현재 코드 위치**: [portfolio.py:122-128](src/backtesting/portfolio.py#L122-L128)

```python
# 문제: datetime.now() 사용 → 백테스트 시간이 아닌 실행 시간 기록
position = Position(
    entry_time=datetime.now(),  # ❌ 캔들 시간이 아님
    ...
)
```

**영향**:
- 보유기간 계산 왜곡
- 월별 성과 분석 불가능
- Walk-forward 테스트 신뢰도 저하

### 2.2 스탑/익절 체결 비현실적 (Critical)

**현재 코드 위치**: [backtester.py:101-108](src/backtesting/backtester.py#L101-L108)

```python
# 문제: 봉 마감가로만 체결 → Intrabar 스탑 미반영
if self.execute_on_next_open and pending_signal is not None:
    self._execute_order(pending_signal, current_bar_data, use_open_price=True)
    # ❌ 봉 중간에 스탑로스 가격 도달해도 체결 안 됨
```

**영향**:
- 실제보다 손실이 작게 측정됨
- 변동성돌파 전략의 리스크 과소평가
- 샤프비율/MDD 과대평가

### 2.3 거래비용 과소평가 (Medium)

**현재 코드 위치**: [backtester.py:32-34](src/backtesting/backtester.py#L32-L34)

```python
commission: float = 0.0005,   # 0.05% 고정
slippage: float = 0.0001,     # 0.01% 고정 (너무 낙관적)
# ❌ 유동성 기반 동적 슬리피지 미흡
# ❌ 체결 실패/부분체결 미구현
```

---

## 3. 목표 아키텍처 (Clean Architecture)

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ BacktestRunner (CLI) / BacktestController (API)      │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                         │
│  ┌─────────────┐  ┌─────────────────┐  ┌────────────────┐  │
│  │ RunBacktest │  │ SimulateExecution│  │CalculateMetrics│  │
│  │   UseCase   │  │     UseCase      │  │    UseCase     │  │
│  └─────────────┘  └─────────────────┘  └────────────────┘  │
│                              │                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                 Outbound Ports                       │   │
│  │  ExecutionPort │ MarketDataPort │ TimeProviderPort  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Domain Layer                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Entities: BacktestTrade, BacktestPosition, Signal     │  │
│  │ Value Objects: Money, Percentage, ExecutionPrice      │  │
│  │ Domain Services: PositionSizer, StopLossCalculator    │  │
│  │ Strategy Interface: BacktestStrategy (ABC)            │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Infrastructure Layer                       │
│  ┌────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │ SimulatedExec  │  │ CandleDataAdapter│  │ FixedTime    │ │
│  │    Adapter     │  │                  │  │   Adapter    │ │
│  └────────────────┘  └─────────────────┘  └──────────────┘ │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ IntrabarExecutionAdapter (스탑/익절 현실화)           │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 리팩토링 체크리스트

### Phase 1: 도메인 계층 정리 (우선순위: 높음)

#### 1.1 엔티티 통합
- [ ] `backtesting/portfolio.py`의 `Trade` → `domain/entities/backtest_trade.py`로 이동
- [ ] `backtesting/portfolio.py`의 `Position` → 기존 `domain/entities/trade.py` 확장
- [x] `backtesting/strategy.py`의 `Signal` → `domain/entities/signal.py`로 이동 ✅ (2026-01-03)
- [ ] 백테스트 전용 Trade 확장 (`entry_time`, `exit_time`은 캔들 시간 사용)

#### 1.2 값 객체 활용
- [ ] `Money` 값 객체로 금액 처리 (`pnl`, `commission`)
- [ ] `Percentage` 값 객체로 수익률 처리 (`pnl_percent`, `slippage_pct`)
- [ ] `ExecutionPrice` 값 객체 (시가/종가/스탑가 구분)

#### 1.3 도메인 서비스 분리
- [ ] `PositionSizer` 도메인 서비스 (현재 전략 클래스에 있음)
- [ ] `StopLossCalculator` 도메인 서비스 (ATR 기반 계산)
- [ ] `SlippageCalculator` 도메인 서비스 (오더북 기반)

### Phase 2: 포트 인터페이스 정의 (우선순위: 높음)

#### 2.1 ExecutionPort (체결 시뮬레이션)
```python
# src/application/ports/outbound/execution_port.py
class ExecutionPort(ABC):
    @abstractmethod
    def execute_market_order(
        self,
        side: OrderSide,
        size: Decimal,
        expected_price: Money,
        candle: CandleData
    ) -> ExecutionResult: ...

    @abstractmethod
    def check_stop_loss_triggered(
        self,
        stop_price: Money,
        candle: CandleData
    ) -> bool: ...

    @abstractmethod
    def check_take_profit_triggered(
        self,
        take_profit_price: Money,
        candle: CandleData
    ) -> bool: ...
```
- [x] `ExecutionPort` 인터페이스 정의 ✅ (2026-01-03)
- [x] `SimpleExecutionAdapter` 구현 (현재 로직) ✅ (2026-01-03)
- [x] `IntrabarExecutionAdapter` 구현 (봉 중 스탑/익절) ✅ (2026-01-03)

#### 2.2 TimeProviderPort (테스트 가능한 시간)
```python
# src/application/ports/outbound/time_provider_port.py
class TimeProviderPort(ABC):
    @abstractmethod
    def now(self) -> datetime: ...

    @abstractmethod
    def from_candle(self, candle: CandleData) -> datetime: ...
```
- [x] `TimeProviderPort` 인터페이스 정의 ✅ (2026-01-03)
- [x] `CandleTimeAdapter` 구현 (캔들 시간 사용) ✅ (2026-01-03)
- [x] `FixedTimeAdapter` 구현 (테스트용) ✅ (2026-01-03)

#### 2.3 MarketDataPort (데이터 제공)
- [ ] `MarketDataPort` 인터페이스 정의
- [ ] `PandasMarketDataAdapter` 구현
- [x] 캔들 데이터 DTO 정의 (`CandleData`) ✅ (2026-01-03)

### Phase 3: 체결 모델 고도화 (우선순위: 최고 - 치명적 한계 해결)

#### 3.1 Intrabar 시뮬레이션
- [x] 봉 내 가격 경로 추정 (OHLC 순서 가정) ✅ (2026-01-03)
- [x] 스탑로스 체결: `candle.low <= stop_price` 시 스탑 체결 ✅ (2026-01-03)
- [x] 익절 체결: `candle.high >= take_profit` 시 익절 체결 ✅ (2026-01-03)
- [x] 스탑/익절 동시 도달 시 worst-case 가정 (스탑 우선) ✅ (2026-01-03)

#### 3.2 체결 가격 현실화
```python
# 스탑로스 체결 가격 계산
if candle.low <= stop_price:
    # 갭 하락 시: open 가격으로 체결 (더 나쁜 가격)
    if candle.open < stop_price:
        execution_price = candle.open
    else:
        execution_price = stop_price
```
- [x] 갭 하락 시 더 나쁜 가격으로 체결 ✅ (2026-01-03)
- [ ] 슬리피지 동적 계산 (거래량 기반)
- [ ] 부분 체결 시뮬레이션 (선택적)

#### 3.3 시간축 정상화
- [ ] Trade.entry_time = 캔들 시간 사용
- [ ] Trade.exit_time = 캔들 시간 사용
- [ ] 보유기간 정확한 계산

### Phase 4: 유스케이스 분리 (우선순위: 중간)

#### 4.1 RunBacktestUseCase
```python
class RunBacktestUseCase:
    def __init__(
        self,
        execution_port: ExecutionPort,
        market_data_port: MarketDataPort,
        time_provider: TimeProviderPort
    ): ...

    def execute(self, request: BacktestRequest) -> BacktestResult: ...
```
- [ ] `RunBacktestUseCase` 구현
- [ ] 의존성 주입으로 포트 교체 가능
- [ ] 현재 Backtester 로직 이전

#### 4.2 CalculatePerformanceUseCase
- [ ] PerformanceAnalyzer → UseCase로 변환
- [ ] 메트릭 계산 로직 분리

#### 4.3 SimulateExecutionUseCase
- [ ] 슬리피지 시뮬레이션 로직 분리
- [ ] 분할 주문 시뮬레이션 분리

### Phase 5: 전략 클래스 리팩토링 (우선순위: 중간)

#### 5.1 책임 분리 (SRP)
현재 `RuleBasedBreakoutStrategy` (1100줄):
- [ ] **지표 계산**: `VolatilityBreakoutIndicators` 클래스로 분리
- [ ] **Gate 체크**: `GateChecker` 도메인 서비스로 분리
- [ ] **포지션 사이징**: `PositionSizer` 도메인 서비스로 분리
- [ ] **슬리피지 계산**: `SlippageCalculator` → ExecutionPort로 이동

#### 5.2 캐싱 최적화 유지
- [ ] `prepare_indicators()` 패턴 유지
- [ ] 캐싱된 지표 인프라 어댑터로 이동

### Phase 6: 검증 프로토콜 추가 (우선순위: 낮음)

#### 6.1 Walk-forward 테스트
- [ ] 데이터 분할 (train/test) 유틸리티
- [ ] Out-of-sample 검증 로직
- [ ] 오버피팅 감지

#### 6.2 파라미터 민감도 테스트
- [ ] K값 변화에 따른 성과 변화
- [ ] 스탑로스 배수 변화에 따른 성과 변화

---

## 5. 테스트 전략

### 5.1 도메인 계층 테스트
```bash
# 순수 로직 테스트 (mock 불필요)
python -m pytest tests/unit/domain/backtest/ -v
```
- [x] Signal 엔티티 테스트 ✅ (2026-01-03)
- [ ] PositionSizer 도메인 서비스 테스트
- [ ] StopLossCalculator 테스트

### 5.2 포트 인터페이스 테스트
```bash
# Mock을 사용한 유스케이스 테스트
python -m pytest tests/unit/application/backtest/ -v
```
- [x] ExecutionPort Mock 테스트 ✅ (2026-01-03)
- [x] IntrabarExecutionAdapter 통합 테스트 ✅ (2026-01-03)

### 5.3 시간축 정상화 검증
- [ ] 보유기간 정확성 테스트
- [ ] 월별 성과 정확성 테스트

---

## 6. 마이그레이션 전략

### 6.1 하위 호환성 유지
```python
# 기존 코드 호환 유지
from src.backtesting import Backtester  # 기존 import 유지

# 내부적으로 새 아키텍처 사용
class Backtester:
    def __init__(self, ...):
        # 레거시 파라미터 → 새 아키텍처 어댑터로 변환
        self._use_case = RunBacktestUseCase(
            execution_port=SimpleExecutionAdapter(...),
            ...
        )
```

### 6.2 점진적 마이그레이션
1. **Phase 1-2**: 포트/어댑터 도입 (기존 동작 유지) ✅ (2026-01-03)
2. **Phase 3**: Intrabar 체결 어댑터 추가 (옵션으로) ✅ (2026-01-03)
3. **Phase 4-5**: 유스케이스/전략 분리
4. **Phase 6**: 검증 프로토콜 추가

### 6.3 Backtester 통합 완료 (2026-01-03)
- [x] `use_intrabar_stops` 옵션 추가
- [x] ExecutionPort 어댑터 자동 선택 (옵션에 따라)
- [x] 봉 내 스탑/익절 체크 로직 추가
- [x] 하위 호환성 유지 (기존 API 동작)
- [x] 통합 테스트 38개 통과

---

## 7. 완료 기준

- [ ] 도메인 엔티티 중복 제거 (backtesting ↔ domain)
- [x] ExecutionPort로 체결 모델 교체 가능 ✅ (2026-01-03)
- [x] Intrabar 스탑/익절 체결 지원 ✅ (2026-01-03)
- [x] Backtester `use_intrabar_stops` 옵션 통합 ✅ (2026-01-03)
- [ ] 시간축 왜곡 해결 (캔들 시간 사용)
- [ ] 기존 백테스트 결과와 비교 검증
- [ ] 테스트 커버리지 80% 이상

---

## 9. 구현 완료 요약 (2026-01-03)

### 완료된 작업

| 구분 | 파일 | 설명 |
|------|------|------|
| **Domain Entity** | `src/domain/entities/signal.py` | Signal 엔티티 (datetime.now() 제거) |
| **Port Interface** | `src/application/ports/outbound/execution_port.py` | ExecutionPort, CandleData, ExecutionResult |
| **Port Interface** | `src/application/ports/outbound/time_provider_port.py` | TimeProviderPort 및 어댑터들 |
| **Adapter** | `src/infrastructure/adapters/execution/simple_execution_adapter.py` | 기존 방식 (종가 기준) |
| **Adapter** | `src/infrastructure/adapters/execution/intrabar_execution_adapter.py` | Intrabar 체결 (고가/저가 기준) |
| **Integration** | `src/backtesting/backtester.py` | `use_intrabar_stops` 옵션 추가 |

### 테스트 현황

- **총 38개 테스트 통과**:
  - Signal 엔티티: 12개
  - ExecutionPort: 9개
  - IntrabarExecutionAdapter: 12개
  - Backtester 통합: 5개

### 사용 방법

```python
# 기존 방식 (하위 호환)
backtester = Backtester(
    strategy=strategy,
    data=data,
    ticker="KRW-BTC",
    initial_capital=10000000
)
result = backtester.run()

# 새 방식 (Intrabar 스탑/익절 활성화)
backtester = Backtester(
    strategy=strategy,
    data=data,
    ticker="KRW-BTC",
    initial_capital=10000000,
    use_intrabar_stops=True  # 핵심 옵션
)
result = backtester.run()
```

### 해결된 "치명적 한계"

1. **스탑/익절 체결 비현실적** → IntrabarExecutionAdapter로 해결
   - 봉 저점이 스탑가 이하면 스탑 트리거
   - 봉 고점이 익절가 이상이면 익절 트리거
   - 갭 발생 시 더 나쁜/좋은 가격으로 체결
   - 스탑/익절 동시 도달 시 worst-case (스탑 우선)

---

## 8. 참고 문서

- [03_backtesting_volatility_breakout.md](03_backtesting_volatility_breakout.md): 치명적 한계 분석
- [ARCHITECTURE.md](../guide/ARCHITECTURE.md): 전체 아키텍처
- [CLAUDE.md](../../CLAUDE.md): 프로젝트 가이드라인
