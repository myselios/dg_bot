# 백테스팅 가이드

**작성일**: 2026-01-03
**Last Updated**: 2026-01-04

---

## 1. 개요

백테스팅은 과거 데이터를 기반으로 트레이딩 전략의 성능을 검증하는 시스템입니다.
이 프로젝트에서는 **단일 백테스팅 필터(12개 필터 + Expectancy)**를 사용하여 실거래 적합성을 검증합니다.

**2026-01-04 변경**: 기존 2단 게이트 구조(Research/Trading Pass)를 단일 백테스팅 필터로 통합했습니다. AI 진입 분석 단계는 제거되었으며, 백테스팅 통과 후 선택적으로 AI에 문의할 수 있습니다.

---

## 2. 시스템 아키텍처

### 2.1 전체 흐름도

```
┌─────────────────────────────────────────────────────────────────┐
│                    BACKTESTING PIPELINE (단순화)                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     1. 유동성 스캔 (10개)                        │
│  - 유동성 상위 코인 선별                                         │
│  - 거래량, 시가총액 기반 필터링                                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              2. 백테스팅 평가 (12개 필터 + Expectancy)            │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  Backtester.run() - 1회 실행                             │  │
│   │  ├─ prepare_indicators() - 지표 사전 계산                │  │
│   │  ├─ RuleBasedBreakoutStrategy                            │  │
│   │  │   ├─ Gate 0: 추세 필터 (MA50 위)                      │  │
│   │  │   ├─ Gate 1: 응축 확인 (BB squeeze)                   │  │
│   │  │   ├─ Gate 2: 돌파 확인 (Donchian/K-breakout)          │  │
│   │  │   └─ Gate 3: 거래량 확인 (OBV 정배열)                 │  │
│   │  └─ BacktestResult.metrics 반환                          │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│   📊 evaluate_backtest(metrics, BacktestConfig)                  │
│   ✓ 12개 필터 전체 통과 필요                                     │
│   ✓ Expectancy Filter (기대값 양수 검증)                         │
│   ✓ 월별 PF 검증 (레짐 가드)                                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 통과: 0-2개
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     3. 최종 선택                                 │
│  - 백테스팅 통과 코인 중 상위 N개 선택                            │
│  - (선택사항) AI에 문의하여 최종 결정                             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     4. 실거래 실행                               │
│  - Upbit API를 통한 주문 실행                                    │
│  - 포지션 관리 (15분 주기)                                       │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 핵심 컴포넌트

```
src/backtesting/
├── quick_filter.py          # 12가지 필터 + Expectancy
│   ├── BacktestConfig        # 백테스팅 설정 (단일 게이트)
│   ├── QuickBacktestFilter   # 필터 평가 클래스
│   │   ├── evaluate_backtest()         # 단일 백테스팅 평가 (ALL AND)
│   │   └── evaluate_backtest_weighted() # 가중치 기반 평가 (Phase 7)
│
├── backtester.py            # 백테스트 엔진
│   ├── Backtester            # 시뮬레이션 실행
│   └── BacktestResult        # 결과 데이터클래스
│
├── runner.py                # 백테스트 러너
│   └── BacktestRunner        # 실행 + 시각화 + 리포트
│
├── rule_based_strategy.py   # 변동성 돌파 전략
│   └── RuleBasedBreakoutStrategy  # 4단계 관문 로직
│
├── expectancy_filter.py     # 기대값 연동 필터
│   ├── calculate_net_expectancy()  # 순 기대값 계산
│   ├── check_expectancy_filter()   # 기대값 필터 체크
│   └── get_min_win_loss_ratio()    # 최소 손익비 계산
│
├── strategy.py              # 전략 인터페이스
├── portfolio.py             # 포트폴리오 관리
├── performance.py           # 성과 지표 계산
└── data_provider.py         # 과거 데이터 제공
```

---

## 3. 12가지 필터 상세

### 3.1 필터 카테고리 및 역할

| # | 카테고리 | 필터명 | 조건 | 역할 | 중요한 이유 |
|---|----------|--------|------|------|-------------|
| 1 | **수익성** | `return` | >= | 총 수익률 검증 | 수익을 내지 못하는 전략은 무의미 |
| 2 | **수익성** | `win_rate` | >= | 승률 검증 | 너무 낮은 승률은 심리적 압박 |
| 3 | **수익성** | `profit_factor` | >= | 총이익/총손실 비율 | 손익비가 1 미만이면 손실 구조 |
| 4 | **위험조정수익** | `sharpe_ratio` | >= | 위험 대비 수익 | 기관 투자 기준 (1.0 이상 권장) |
| 5 | **위험조정수익** | `sortino_ratio` | >= | 하방 리스크 조정 | 상승 변동성은 좋은 것, 하락만 문제 |
| 6 | **위험조정수익** | `calmar_ratio` | >= | 수익률/최대낙폭 | MDD 대비 수익 효율성 |
| 7 | **리스크관리** | `max_drawdown` | <= | 최대 낙폭 제한 | 15% 초과 시 심리적 압박 큼 |
| 8 | **리스크관리** | `max_consecutive_losses` | <= | 최대 연속 손실 | 5회 초과 시 전략 재검토 필요 |
| 9 | **리스크관리** | `volatility` | <= | 연율 변동성 | 과도한 변동성은 리스크 |
| 10 | **통계유의성** | `min_trades` | >= | 최소 거래 수 | 20회 미만은 통계적 의미 없음 |
| 11 | **거래품질** | `avg_win_loss_ratio` | >= | 평균수익/평균손실 | 돌파전략은 손익비로 승부 |
| 12 | **거래품질** | `avg_holding_hours` | <= | 최대 평균 보유 시간 | 너무 길면 자본 효율 저하 |

### 3.2 필터 타입 구분

| 필터 타입 | 연산자 | 의미 | 대상 필터 |
|-----------|--------|------|-----------|
| **Minimum** | >= | 값이 기준 이상이어야 통과 | return, win_rate, profit_factor, sharpe, sortino, calmar, min_trades, avg_win_loss_ratio |
| **Maximum** | <= | 값이 기준 이하여야 통과 | max_drawdown, max_consecutive_losses, volatility, avg_holding_hours |

### 3.3 현재 임계값 (BacktestConfig 기본값)

| # | 필터 | 임계값 | 비고 |
|---|------|--------|------|
| 1 | min_return | 9.0% | 총 수익률 |
| 2 | min_win_rate | 35.0% | 승률 |
| 3 | min_profit_factor | 1.5 | 총이익/총손실 |
| 4 | min_sharpe_ratio | 0.7 | 위험조정수익 |
| 5 | min_sortino_ratio | 0.9 | 하방리스크조정 |
| 6 | min_calmar_ratio | 0.4 | 수익/MDD |
| 7 | max_drawdown | 25.0% | 최대낙폭 |
| 8 | max_consecutive_losses | 6 | 연속손실 |
| 9 | max_volatility | 80.0% | 연율변동성 |
| 10 | min_trades | 10 | 최소거래수 |
| 11 | min_avg_win_loss_ratio | 1.0 | 평균손익비 |
| 12 | max_avg_holding_hours | 240h | 평균보유시간 |

*avg_win_loss_ratio는 Expectancy 필터에서 승률 기반 동적 검증도 수행

---

## 4. 백테스팅 필터 구조 (단일 게이트)

**2026-01-04 변경**: 기존 2단 게이트(Research/Trading Pass)를 단일 백테스팅 필터로 통합

### 4.1 BacktestConfig (단일 설정)

**목적**: 실거래 적합성 검증 (엄격한 기준)

```python
# BacktestConfig 기본값 (구 TradingPassConfig 기준)
config = BacktestConfig(
    days=730,
    min_return=9.0,
    min_win_rate=35.0,
    min_profit_factor=1.5,
    # ... 12개 필터 임계값
)

# 통과 조건 (AND 조건)
result = evaluate_backtest(metrics, config)
passed = result.passed  # 모든 필터 + Expectancy 통과 필요
```

**특징**:
- 12개 필터 전체 통과 필요
- Expectancy Filter 필수 검증
- 레짐 가드 (월별 PF 검증)
- AI 분석 없이 백테스팅만으로 실거래 진입 결정

### 4.2 Expectancy Filter (기대값 연동 필터)

승률과 손익비의 논리적 충돌을 수학적으로 차단합니다.

**핵심 공식**:
```
cost_R = cost_pct / avg_loss_pct
gross = (win_rate × R) - (1 - win_rate)
net = gross - cost_R

통과 조건: net >= margin_R (기본 0.05R)
```

**최소 손익비 표** (avg_loss_pct=1%, margin_R=0.05):

| 승률 | cost_R=0.12 | cost_R=0.20 (스트레스) |
|------|-------------|------------------------|
| 30% | **2.90** | 3.17 |
| 33% | **2.55** | 2.79 |
| 40% | **1.93** | 2.13 |
| 50% | **1.34** | 1.50 |

**예시**:
```
승률 33%, R=2.5, cost_pct=0.12%

1. cost_R = 0.0012 / 0.01 = 0.12
2. gross = 0.33 × 2.5 - 0.67 = 0.155
3. net = 0.155 - 0.12 = 0.035 ✅ 양수 (PASS)

승률 33%, R=1.0 (논리적 충돌)

1. gross = 0.33 × 1.0 - 0.67 = -0.34
2. net = -0.34 - 0.12 = -0.46 ❌ 음수 (FAIL)
```

---

## 5. 백테스트 엔진 상세

### 5.1 Backtester 클래스

```python
class Backtester:
    def __init__(
        self,
        strategy: Strategy,           # 거래 전략
        data: pd.DataFrame,           # 과거 데이터
        ticker: str,                  # 거래 종목
        initial_capital: float,       # 초기 자본
        commission: float = 0.0005,   # 수수료 (0.05%)
        slippage: float = 0.0001,     # 슬리피지 (0.01%)
        execute_on_next_open: bool = True,  # Look-Ahead Bias 방지
        use_intrabar_stops: bool = False,   # 봉 내 스탑/익절
    ):
```

**주요 옵션**:

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `execute_on_next_open` | True | Look-Ahead Bias 방지 (권장) |
| `use_intrabar_stops` | False | 봉 내 스탑/익절 시뮬레이션 |
| `commission` | 0.0005 | 편도 수수료 (0.05%) |
| `slippage` | 0.0001 | 편도 슬리피지 (0.01%) |

### 5.2 체결 모드

| 모드 | execute_on_next_open | 설명 |
|------|---------------------|------|
| **현실적** | True (기본) | t시점 신호 → t+1시점 시가 체결 |
| **빠른 테스트** | False | t시점 신호 → t시점 종가 체결 (과대평가 위험) |

### 5.3 백테스트 실행 흐름

```
for each bar in data:
    │
    ├─ 1. 봉 내 스탑/익절 체크 (use_intrabar_stops)
    │      └─ 스탑/익절 트리거 시 즉시 청산
    │
    ├─ 2. 대기 신호 실행 (execute_on_next_open)
    │      └─ 전날 신호를 오늘 시가로 체결
    │
    ├─ 3. 전략 신호 생성
    │      └─ strategy.generate_signal(data, portfolio)
    │
    ├─ 4. 신호 처리
    │      ├─ execute_on_next_open=True → 대기열에 저장
    │      └─ execute_on_next_open=False → 즉시 체결
    │
    └─ 5. 포트폴리오 업데이트
           └─ equity_curve 기록
```

---

## 6. 변동성 돌파 전략 (4단계 관문)

### 6.1 Gate 0: 추세 필터 (Trend Filter)

**목적**: 하락장 가짜 돌파(데드캣 바운스) 차단

```python
# 현재 가격이 MA50 위에 있어야 상승 추세
passed = current_price > MA(50)
```

### 6.2 Gate 1: 응축 확인 (Squeeze)

**목적**: 돌파 전 에너지 축적 확인

```python
# 볼린저 밴드 폭이 평균보다 좁아야 함 (직전 캔들 기준)
bb_width = (upper - lower) / MA20
passed = prev_bb_width < avg_bb_width * 0.8

# 또는 ADX가 25 미만 (횡보)
passed = prev_adx < 25
```

### 6.3 Gate 2: 돌파 확인 (Breakout)

**목적**: 실제 돌파 발생 확인

```python
# 방법 1: Donchian Channel (20일 고점 돌파)
passed = current_price > highest_high_20d

# 방법 2: 래리 윌리엄스 변동성 돌파
breakout_level = prev_close + (prev_range * K)
passed = current_price > breakout_level
```

**동적 K값**: 노이즈 비율에 따라 0.3~0.7 자동 조정

### 6.4 Gate 3: 거래량 확인 (Volume)

**목적**: 매수세 유입 확인

```python
# 거래량 폭발
passed = current_volume > avg_volume * 1.5

# 또는 OBV 정배열
passed = current_obv > obv_ma20 and obv_ma5 > obv_ma20
```

### 6.5 매도 조건 (5가지)

| 우선순위 | 조건 | 설명 |
|----------|------|------|
| 1 | **스탑로스** | 손실 보호 최우선 |
| 2 | **Fakeout** | 진입 후 3봉 내 2% 하락 시 즉시 청산 |
| 3 | **타겟가** | 익절 실현 |
| 4 | **ADX 약화** | 추세 반전 감지 |
| 5 | **타임아웃** | 24봉 경과 후 수익 2% 미만 시 청산 |

---

## 7. 성능 최적화

### 7.1 지표 사전 계산 (Vectorization)

```python
# O(N²) → O(N) 최적화
strategy.prepare_indicators(data)  # 백테스트 시작 전 1회 호출

# 이후 generate_signal()에서는 캐싱된 지표 참조만 수행
```

### 7.2 캐싱 메커니즘

```python
# 같은 스캔 사이클 내에서 ticker별 백테스트 1회만 실행
run_id = filter.start_scan_cycle()
metrics = filter.get_or_run_backtest(ticker)  # 캐시 활용

# 단일 백테스팅 평가
result = filter.evaluate_backtest(metrics, BacktestConfig())
print(f"통과: {result.passed}, 사유: {result.reason}")
```

---

## 8. 사용 예시

### 8.1 기본 백테스트 실행

```python
from src.backtesting.quick_filter import QuickBacktestFilter, BacktestConfig

# 필터 생성
qf = QuickBacktestFilter()

# 백테스트 실행
result = qf.run_quick_backtest(ticker="KRW-BTC")

# 결과 확인
print(f"통과: {result.passed}")
print(f"수익률: {result.metrics['total_return']:.2f}%")
print(f"Sharpe: {result.metrics['sharpe_ratio']:.2f}")
```

### 8.2 백테스팅 평가 (단일 게이트)

```python
# 스캔 사이클 시작
run_id = qf.start_scan_cycle()

# 백테스트 실행 (1회)
metrics = qf.get_or_run_backtest("KRW-BTC")

# 단일 백테스팅 평가 (12개 필터 + Expectancy)
config = BacktestConfig()  # 기본값 사용
result = qf.evaluate_backtest(metrics, config)
print(f"백테스팅 통과: {result.passed} ({result.reason})")

# Expectancy 상세 체크 (선택사항)
exp = qf.check_expectancy_with_metrics(metrics)
print(f"기대값: {exp['net_expectancy']:.3f}R (통과: {exp['passed']})")
```

### 8.3 필터 분석 리포트

```python
# 여러 코인 분석
tickers = ["KRW-BTC", "KRW-ETH", "KRW-XRP"]
metrics_list = [filter.run_quick_backtest(t).metrics for t in tickers]

# 필터별 통계 집계
aggregated = filter.aggregate_filter_statistics(metrics_list)

# 리포트 생성
report = filter.generate_filter_analysis_report(aggregated)

print(f"Summary: {report['summary']}")
print(f"Top Failing: {report['top_failing_filters']}")
print(f"Verdict: {report['verdict']}")  # 필터 조정 필요 여부
```

---

## 9. 관련 파일

| 파일 | 설명 |
|------|------|
| [src/backtesting/quick_filter.py](../../src/backtesting/quick_filter.py) | 12가지 필터 + 단일 게이트 |
| [src/backtesting/backtester.py](../../src/backtesting/backtester.py) | 백테스트 엔진 |
| [src/backtesting/rule_based_strategy.py](../../src/backtesting/rule_based_strategy.py) | 변동성 돌파 전략 |
| [src/backtesting/expectancy_filter.py](../../src/backtesting/expectancy_filter.py) | 기대값 연동 필터 |
| [tests/contracts/test_expectancy_filter.py](../../tests/contracts/test_expectancy_filter.py) | 기대값 계약 테스트 |

---

## 10. 레퍼런스

- [3Commas: AI Trading Bot Performance](https://3commas.io/blog/ai-trading-bot-performance-analysis) - PF > 1.5 = strong
- [Coin Bureau: Backtest Guide 2025](https://coinbureau.com/guides/how-to-backtest-your-crypto-trading-strategy/) - 50-100 trades 권장
- [Freqtrade 백테스트 결과](https://www.freqtrade.io/en/stable/backtesting/) - 실제 PF/승률 사례

---

## 11. 변경 이력

| 날짜 | 변경 내용 |
|------|----------|
| 2026-01-05 | **🔥 DEPRECATED 코드 완전 삭제**: ResearchPassConfig, TradingPassConfig, QuickBacktestConfig 삭제. evaluate_research_pass(), evaluate_trading_pass(), 3단 비교 분석 함수 삭제. BacktestConfig + evaluate_backtest_weighted()가 단일 표준. |
| 2026-01-05 | **Phase 7 가중치 필터**: Tier 1 (핵심 AND 4개) + Tier 2-4 (가중 점수) 2단계 평가. min_trades 충족 못해도 가중 점수로 통과 가능. |
| 2026-01-04 | **단일 게이트로 통합**: 2단 게이트(Research/Trading Pass) → BacktestConfig로 통합. AI 진입 분석 단계 완전 제거. |
| 2026-01-04 | **evaluate_backtest() 메서드 추가**: 단일 백테스팅 평가 메서드. 12개 필터 + Expectancy 통합 검증. |
| 2026-01-04 | **CoinSelector AI 코드 제거**: entry_signal, ai_analyzed 필드 제거. _apply_backtest()로 메서드명 변경. |
| 2026-01-04 | **min_trades 조정**: Trading Pass `min_trades` 50 → 25로 완화. 상위 20개 코인 분석 결과 최대 거래 수 28회 (BTC 기준). |
| 2026-01-04 | **메트릭 버그 수정**: `avg_win_loss_ratio`, `avg_holding_period_hours`가 0으로 계산되던 문제 해결. |
| 2026-01-03 | 문서 최초 작성 |
