# 백테스팅 필터 개선 계획

**작성일**: 2026-01-03
**Last Updated**: 2026-01-03
**상태**: Phase 0 완료, Phase 1 진행 예정
**예상 범위**: Medium (4-5 phases, 8-12시간)

---

## CRITICAL INSTRUCTIONS

⚠️ **각 Phase 완료 후 반드시**:
1. ✅ 완료된 체크박스 체크
2. 🧪 Quality Gate 검증 명령 실행
3. ⚠️ 모든 Quality Gate 항목 통과 확인
4. 📅 "Last Updated" 날짜 업데이트
5. 📝 Notes 섹션에 학습 내용 기록
6. ➡️ 다음 Phase 진행

⛔ **Quality Gate 실패 시 다음 Phase 진행 금지**

---

## 1. 문제 정의

### 현재 상황
- **증상**: 모든 코인이 백테스팅 필터에서 탈락 (스캔 4개 → 통과 0개)
- **결과**: AI에게 후보가 전달되지 않아 항상 HOLD 결정
- **로그 증거**: `2026-01-03 08:02:00 - 스캔: 3개 → 통과: 0개`

### 근본 원인
| 문제 | 설명 |
|------|------|
| **과도하게 엄격한 기준** | 12개 필터가 전통금융 기관급 기준 (암호화폐 부적합) |
| **논리적 충돌 허용** | 승률 33% + 손익비 1.0 = 기대값 음수 조합 통과 가능 |
| **단위 불일치** | 수수료 0.2%를 R-multiple 기대값에 직접 빼는 오류 |

### 영향 범위
- `src/backtesting/quick_filter.py` - QuickBacktestConfig, QuickBacktestFilter
- `src/config/settings.py` - 새 Config 클래스 추가 필요
- `backend/app/core/scheduler.py` - 필터 결과 로깅

---

## 2. 목표

### Primary Goals
1. **Research Pass**: 느슨한 기준으로 AI에게 전달할 후보 확보 (통과율 30-50% 목표)
2. **Trading Pass**: 엄격한 기준 + 기대값 검증으로 실거래 보호
3. **승률↔손익비 연동**: 기대값 양수 보장하는 수학적 필터

### Success Metrics (P1-8 수정 - 안정성 지표)
- [ ] **안정성**: **최근 24시간 동안 최소 1회 이상** Research Pass 통과 (0% 방지)
- [ ] **상한 제한**: 스캔 10개 중 8개 이상 통과 시 필터 너무 느슨 경고
- [ ] **Trading Pass**: Research 통과 코인 중 기대값 양수만 실거래
- [ ] **기대값 검증**: 승률↔손익비 논리적 충돌 조합 100% 차단

---

## 3. 아키텍처 결정

### 3.1 2단 게이트 구조 (Research / Trading Pass)

```
┌─────────────────────────────────────────────────────────────┐
│                    Coin Scanning (10개)                      │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│               Research Pass (느슨한 필터)                    │
│  - PF ≥ 1.3, Sharpe ≥ 0.4, MDD ≤ 30%                       │
│  - 목표: 후보 풀 확보 (30-50% 통과)                          │
└─────────────────────────┬───────────────────────────────────┘
                          │ 통과: 3-5개
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    AI 분석 (진입 판단)                       │
└─────────────────────────┬───────────────────────────────────┘
                          │ BUY 신호
                          ▼
┌─────────────────────────────────────────────────────────────┐
│               Trading Pass (엄격한 필터)                     │
│  - PF ≥ 1.5, Trades ≥ 50, 기대값 검증                       │
│  - 목표: 실거래 보호                                         │
└─────────────────────────┬───────────────────────────────────┘
                          │ 통과
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      실거래 실행                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 승률↔손익비 연동 필터 (기대값 기반)

**⚠️ 단위 규칙 (P0-3)**:
- **내부 로직**: 모든 비율은 0~1로 통일 (예: 33% → 0.33)
- **설정/표시**: % 단위 사용, 로직 진입 시 `/100` 변환
- **cost_pct**: 시스템 설정(commission + slippage)에서 파생 (P0-4)

**비용 계산 (P0-4)**:
```python
# 시스템 실제 비용에서 파생 (QuickBacktestConfig 기본값 기준)
commission = 0.0005  # 0.05% (편도)
slippage = 0.0001    # 0.01% (편도)
cost_pct = (commission + slippage) * 2  # 왕복 = 0.0012 (0.12%)

# 스트레스 테스트용 (보수적)
stress_cost_pct = 0.002  # 0.2% (슬리피지 악화 시나리오)
```

**⚠️ avg_loss_pct 정의 (P0-7)**:
```python
# avg_loss_pct = 평균 손실 거래의 손실률 (0~1, 예: 1% = 0.01)
# 백테스트 결과에서 계산:
avg_loss_pct = abs(losing_trades['pnl_pct'].mean())

# 바닥값(floor) 적용 - 0으로 나누기 방지 + 극단적 저손실 필터링
AVG_LOSS_PCT_FLOOR = 0.002  # 0.2% 최소 손실 가정
avg_loss_pct = max(avg_loss_pct, AVG_LOSS_PCT_FLOOR)
```

**핵심 공식 (P0-6 통일된 시그니처)**:
```python
# 비용을 R 단위로 환산
cost_R = cost_pct / avg_loss_pct  # avg_loss_pct는 floor 적용 후

# 기대값 계산 (R 단위)
# gross = p × R - (1-p)
# net = gross - cost_R
gross_expectancy_R = (win_rate * avg_win_loss_ratio) - (1 - win_rate)
net_expectancy_R = gross_expectancy_R - cost_R

# 최소 손익비 계산
# R_min = ((1-p) + cost_R + margin_R) / p
R_min = ((1 - win_rate) + cost_R + margin_R) / win_rate
```

**⚠️ 함수 시그니처 규칙 (P0-6)**:
- 모든 함수는 `cost_pct`, `avg_loss_pct`를 입력으로 받음
- `cost_R`은 함수 **내부**에서 계산 (`cost_R = cost_pct / avg_loss_pct`)
- 테스트도 동일 시그니처 사용 (cost_R 직접 전달 금지)

**⚠️ cost_pct 단일 소스 규칙 (P0-12)**:
- expectancy_filter 함수는 cost_pct **기본값을 절대 가지지 않는다**
- cost_pct는 항상 `QuickBacktestConfig`(commission, slippage)에서 파생한 값을 **주입**한다
- 목적: 설정 변경 시 기대값 필터만 과거 비용으로 계산되는 "조용한 버그" 방지
- floor 적용률(몇 % 트레이드에 적용됐는지) 반드시 로그/메트릭으로 모니터링

**예시 검증 (P0-1 수정)**:
```
승률 33% (p=0.33), R=2.5, avg_loss_pct=1%, cost_pct=0.12%

1. cost_R = 0.0012 / 0.01 = 0.12
2. gross = 0.33 × 2.5 - 0.67 = 0.825 - 0.67 = 0.155
3. net = 0.155 - 0.12 = 0.035  ✅ 양수 (margin 충족)

스트레스 테스트 (cost_pct=0.2%):
1. cost_R = 0.002 / 0.01 = 0.2
2. net = 0.155 - 0.2 = -0.045  ❌ 음수 (탈락)
```

**최소 손익비 표 (P0-2 수정)** - avg_loss_pct=1%, margin_R=0.05:

| 승률 | cost_pct | cost_R | R_min 공식 | 최소 손익비 |
|------|----------|--------|------------|------------|
| 30%  | 0.12%    | 0.12   | (0.70+0.12+0.05)/0.30 | **2.90** |
| 35%  | 0.12%    | 0.12   | (0.65+0.12+0.05)/0.35 | **2.34** |
| 40%  | 0.12%    | 0.12   | (0.60+0.12+0.05)/0.40 | **1.93** |
| 50%  | 0.12%    | 0.12   | (0.50+0.12+0.05)/0.50 | **1.34** |

**스트레스 테스트 표** - cost_pct=0.2% (악조건):

| 승률 | cost_R | R_min |
|------|--------|-------|
| 30%  | 0.20   | **3.17** |
| 35%  | 0.20   | **2.57** |
| 40%  | 0.20   | **2.13** |
| 50%  | 0.20   | **1.50** |

### 3.3 필터 값 비교표

| # | 필터 | 현재 | Research | Trading | 근거 |
|---|------|------|----------|---------|------|
| 1 | min_return | 15% | 8% | 12% | 2년간 기준 |
| 2 | min_win_rate | 38% | 30% | 35% | 돌파전략 특성 |
| 3 | min_profit_factor | 1.8 | 1.3 | 1.5 | 3Commas: 1.5=strong |
| 4 | min_sharpe_ratio | 1.0 | 0.4 | 0.7 | 암호화폐 변동성 |
| 5 | min_sortino_ratio | 1.2 | 0.5 | 0.8 | Sharpe × 1.2 |
| 6 | min_calmar_ratio | 0.8 | 0.25 | 0.4 | 수익/MDD |
| 7 | max_drawdown | 15% | 30% | 25% | 업계 기준 20% |
| 8 | max_consecutive_losses | 5 | 8 | 6 | 통계적 런 |
| 9 | max_volatility | 50% | 100% | 80% | BTC 60-80% (P1-7 참조) |
| 10 | min_trades | 20 | 20 | 50 | 통계적 유의성 |
| 11 | min_avg_win_loss_ratio | 1.3 | **연동** | **연동** | 기대값 기반 |
| 12 | max_avg_holding_hours | 168h | 336h | 240h | 스윙 허용 |

### 3.5 Trading Pass 레짐 가드 (P1-9)

**⚠️ 특정 시장 상황에서의 전략 붕괴 방지 + 빈도 낮은 전략 Fallback 포함**

Trading Pass 통과 조건에 **레짐 분할 최소 가드** 추가하되,
월별 분할이 trades 부족으로 무의미해지는 경우를 대비해 **fallback(병합/분기)** 규칙을 포함한다.

#### 레짐 분할 규칙
1) 기본은 **월별 분할**
2) 월별 레짐의 trades가 `min_regime_trades` 미만이면:
   - 인접 월을 합쳐 **2개월/3개월 병합 레짐**으로 재구성 (최대 3개월)
3) 그래도 trades가 부족하면 **분기(Quarter) 단위**로 분할
4) 분기에서도 부족하면 레짐 가드는 "판단 불가"로 표시하고,
   - Trading Pass에서 `min_trades=50`를 더 강하게 신뢰 (또는 보수적으로 FAIL)

#### 실패 허용 규칙
- 기본: `max_failed_regimes = 1` (1개 레짐은 예외 허용)
- 단, **최근 레짐(가장 최신 기간)은 예외 허용 0개**
  - 최근 구간에서 무너지는 전략은 실거래에서 가장 위험

```python
regimes = split_regimes_with_fallback(
    backtest_result,
    base="monthly",
    min_regime_trades=10,
    max_merge_months=3,
    fallback="quarterly",
)

REGIME_MIN_PF = 1.0
MAX_FAILED_REGIMES = 1

failed = 0
for r in regimes:
    if r.profit_factor < REGIME_MIN_PF:
        # ⚠️ 최근 레짐은 예외 0개 - 즉시 실패
        if r.is_most_recent:
            return TradingPassResult(
                False,
                f"최근 레짐 붕괴: {r.name} PF {r.profit_factor:.2f} < {REGIME_MIN_PF}"
            )

        failed += 1
        if failed > MAX_FAILED_REGIMES:
            return TradingPassResult(
                False,
                f"레짐 실패 {failed}개 초과 (PF<{REGIME_MIN_PF})"
            )

return TradingPassResult(True, "레짐 가드 통과")
```

| 항목 | 값 | 설명 |
|------|-----|------|
| **분할 기준** | 월별 → (병합) → 분기 | trades 부족 시 자동 fallback |
| **최소 거래 수** | 10 | 레짐당 유의성 |
| **레짐 최소 PF** | 1.0 | 최소 방어선 |
| **최대 실패 레짐** | 1개 | **단, 최근 레짐은 0개** |

**예시**:
- 백테스트 기간: 2024.01 ~ 2024.12 (12개월)
- 레짐 분할: 월별 12개 레짐
- 결과: 11개월 PF > 1.0, 1개월(3월) PF = 0.8 → **통과** (1개 예외 허용, 최근 아님)
- 결과: 11개월 PF > 1.0, **12월(최근)** PF = 0.8 → **실패** (최근 레짐 예외 0개)
- 결과: 10개월 PF > 1.0, 2개월 PF < 1.0 → **실패** (실패 2개 > 1개)

### 3.6 Volatility 정의 (P1-7, P1-10)

**⚠️ volatility 지표 산출 방식 명확화**

**P1-10: Equity Curve 기반 (가격 기반 아님)**

| 구분 | Equity Curve 기반 ✅ | 가격(Price) 기반 ❌ |
|------|---------------------|---------------------|
| **의미** | 전략 수익률 변동성 | 자산 자체 변동성 |
| **용도** | 전략 리스크 평가 | 시장 환경 분류 |
| **우리 사용** | ✅ 백테스트 필터 | 참고용 |

현재 코드(`BacktestResult.metrics['volatility']`) 산출 방식:
```python
# ⚠️ equity_curve 기반 (가격 아님!)
# equity_curve = 전략 실행 시 계좌 잔고 변화
daily_returns = equity_curve.pct_change().dropna()  # 전략 수익률
daily_std = daily_returns.std()
annualized_volatility = daily_std * sqrt(365)  # 암호화폐 24/7 거래
```

| 항목 | 값 |
|------|-----|
| **데이터 소스** | **equity_curve** (계좌 잔고) |
| **기준** | 일간 수익률(daily returns) |
| **계산** | 표준편차(std) |
| **연율화** | × √365 (암호화폐 24/7 거래) |
| **단위** | % (0~100 범위) |

**예시**:
- 일간 std = 2% → 연율 volatility = 2% × √365 ≈ **38.2%**
- 일간 std = 4% → 연율 volatility ≈ **76.4%**

**BTC 참고값**: 연율 가격 변동성 60-80% (2020-2024 평균)
- 전략 volatility가 BTC 가격 volatility보다 높으면 → 레버리지/과잉 거래 의심

---

## 4. Phase 계획

### Phase 0: 현재 탈락 사유 분석 (1시간) ✅ COMPLETED

**목표**: 12개 필터 중 어디서 가장 많이 탈락하는지 + **임계값 대비 거리(gap)** 파악

**테스트 전략**:
- 단위 테스트: 필터별 탈락 카운트 + gap 집계 함수
- 커버리지 목표: 80%

**Tasks**:

#### RED (테스트 먼저)
- [x] `tests/unit/backtesting/test_filter_analysis.py` 생성
- [x] 필터별 탈락 카운트 + gap 테스트 케이스 작성
- [x] 테스트 실패 확인

#### GREEN (구현)
- [x] `QuickBacktestFilter`에 필터별 통계 수집 메서드 추가
- [x] **P1-6 반영**: 각 필터별 `metric_value`, `threshold`, `gap` 수집
  ```python
  # 예시 출력 포맷
  {
      "sharpe_ratio": {
          "fail_count": 8,
          "pass_count": 2,
          "avg_value": 0.65,      # 실제 평균값
          "threshold": 1.0,        # 현재 기준
          "avg_gap": -0.35,        # value - threshold (음수=미달)
          "verdict": "완화 시 개선 가능"  # gap이 작으면
      }
  }
  ```
- [x] 최근 백테스트 결과에서 탈락 사유 집계
- [x] 로그에서 필터별 통과/실패 비율 추출

#### REFACTOR
- [x] 통계 출력 포맷 정리
- [x] 분석 결과 문서화

**Quality Gate**:
- [x] 테스트 통과 (12 tests passed)
- [x] 12개 필터별 탈락률 + **평균 gap** 파악 완료
- [x] 가장 많이 탈락하는 필터 Top 3 식별 (`get_top_failing_filters`)
- [x] **gap 분석**: 완화로 개선 가능한 필터 vs 전략 자체 문제 구분 (`verdict` 필드)

**산출물**: 필터별 탈락 분석 리포트 (fail_count + gap 포함)

**구현된 클래스/메서드**:
- `FilterStatistics` - 개별 필터 통계 dataclass
- `FilterAnalysisResult` - 분석 결과 dataclass
- `analyze_filter_results()` - 단일 코인 분석
- `aggregate_filter_statistics()` - 다중 코인 집계
- `get_top_failing_filters()` - Top N 탈락 필터
- `generate_filter_analysis_report()` - 리포트 생성

---

### Phase 1: Research Pass Config 구현 (2시간)

**목표**: 느슨한 필터 설정으로 후보 생성 확인

**테스트 전략**:
- 단위 테스트: ResearchPassConfig 값 검증
- 통합 테스트: 실제 백테스트 통과율 확인
- 커버리지 목표: 85%

**Tasks**:

#### RED (테스트 먼저)
- [x] `tests/unit/backtesting/test_research_pass.py` 생성
- [x] ResearchPassConfig 기본값 테스트
- [x] Research Pass 필터 적용 테스트 (mock 데이터)
- [x] 테스트 실패 확인

#### GREEN (구현)
- [x] `src/backtesting/quick_filter.py`에 Config 클래스 추가
  ```python
  class BacktestFilterConfig:
      """2단 게이트 필터 설정"""
      # Research Pass (후보 생성용)
      RESEARCH_MIN_RETURN = 8.0
      RESEARCH_MIN_WIN_RATE = 30.0
      RESEARCH_MIN_PROFIT_FACTOR = 1.3
      RESEARCH_MIN_SHARPE = 0.4
      RESEARCH_MAX_DRAWDOWN = 30.0
      RESEARCH_MIN_TRADES = 20

      # Trading Pass (실거래용)
      TRADING_MIN_RETURN = 12.0
      TRADING_MIN_WIN_RATE = 35.0
      TRADING_MIN_PROFIT_FACTOR = 1.5
      TRADING_MIN_SHARPE = 0.7
      TRADING_MAX_DRAWDOWN = 25.0
      TRADING_MIN_TRADES = 50
  ```
- [x] `ResearchPassConfig`, `TradingPassConfig` 클래스 구현
- [x] `PassResult` 데이터클래스 구현

#### REFACTOR
- [x] 기존 하드코딩 값 제거
- [ ] 환경변수 오버라이드 지원 추가 (선택적)

**Quality Gate**:
- [x] 모든 테스트 통과
- [x] Research Pass로 최소 1개 이상 코인 통과 확인
- [x] 기존 테스트 회귀 없음

**Dependencies**: Phase 0 완료

---

### Phase 2: 승률↔손익비 연동 필터 구현 (2시간)

**목표**: 기대값 음수 조합 차단

**테스트 전략**:
- 단위 테스트: 기대값 계산 함수, 최소 손익비 계산 함수
- 경계값 테스트: 승률 30%, 50% 등 임계값
- 커버리지 목표: 90% (핵심 비즈니스 로직)

**Tasks**:

#### RED (테스트 먼저)
- [x] `tests/contracts/test_expectancy_filter.py` 생성 (계약 테스트)
- [x] 기대값 계산 정확성 테스트 **(P0-1, P0-6, P0-7 반영)**
  ```python
  def test_expectancy_positive_case():
      """승률 33%, R=2.5 → 양수 기대값 (P0-6: 통일 시그니처)"""
      # avg_loss_pct=0.01(1%), cost_pct=0.0012(0.12%) → cost_R = 0.12
      # gross = 0.33 × 2.5 - 0.67 = 0.155
      # net = 0.155 - 0.12 = 0.035
      result = calculate_net_expectancy(
          win_rate=0.33,
          avg_win_loss_ratio=2.5,
          avg_loss_pct=0.01,  # 1%
          cost_pct=0.0012     # 0.12%
      )
      assert abs(result - 0.035) < 0.001
      assert result > 0  # 양수여야 함

  def test_expectancy_negative_stress():
      """승률 33%, R=2.5, stress cost → 음수 기대값"""
      # cost_pct=0.002(0.2%) → cost_R = 0.2
      # gross = 0.155, net = 0.155 - 0.2 = -0.045
      result = calculate_net_expectancy(
          win_rate=0.33,
          avg_win_loss_ratio=2.5,
          avg_loss_pct=0.01,  # 1%
          cost_pct=0.002      # 0.2% (stress)
      )
      assert abs(result - (-0.045)) < 0.001
      assert result < 0  # 음수 → 탈락

  def test_min_r_calculation():
      """최소 손익비 계산 검증 (P0-2, P0-6 통일 시그니처)"""
      # avg_loss_pct=0.01, cost_pct=0.0012 → cost_R = 0.12
      # R_min = (0.67 + 0.12 + 0.05) / 0.33 = 2.55
      result = get_min_win_loss_ratio(
          win_rate=0.33,
          avg_loss_pct=0.01,
          cost_pct=0.0012,
          margin_R=0.05
      )
      assert abs(result - 2.55) < 0.01

  def test_avg_loss_pct_floor():
      """avg_loss_pct floor 적용 (P0-7)"""
      # 극단적으로 낮은 avg_loss_pct → floor 적용
      result = apply_avg_loss_floor(avg_loss_pct=0.0001)  # 0.01%
      assert result == 0.002  # floor = 0.2%

  def test_cost_pct_required():
      """cost_pct 누락 시 TypeError (P0-12)"""
      import pytest
      with pytest.raises(TypeError):
          # cost_pct 없이 호출 → 실패해야 함
          calculate_net_expectancy(
              win_rate=0.33,
              avg_win_loss_ratio=2.5,
              avg_loss_pct=0.01
          )
  ```
- [x] 최소 손익비 계산 테스트 (표와 일치 확인)
- [x] 논리적 충돌 조합 차단 테스트 (승률 33% + R=1.0 → 실패)
- [x] 테스트 실패 확인

#### GREEN (구현)
- [x] `src/backtesting/expectancy_filter.py` 생성
  ```python
  # 상수 정의 (P0-7)
  AVG_LOSS_PCT_FLOOR = 0.002  # 0.2% 최소 손실 (안전장치)
  # NOTE: floor는 운영 중 적용률(몇 % 트레이드에 적용됐는지) 반드시 로그/메트릭으로 모니터링

  def apply_avg_loss_floor(avg_loss_pct: float) -> float:
      """avg_loss_pct에 바닥값 적용 (P0-7)"""
      return max(avg_loss_pct, AVG_LOSS_PCT_FLOOR)

  def calculate_cost_R(cost_pct: float, avg_loss_pct: float) -> float:
      """비용을 R 단위로 환산 (P0-12: cost_pct는 항상 외부에서 주입)"""
      avg_loss_pct = apply_avg_loss_floor(avg_loss_pct)
      return cost_pct / avg_loss_pct

  def calculate_net_expectancy(
      win_rate: float,
      avg_win_loss_ratio: float,
      avg_loss_pct: float,
      cost_pct: float,  # ⚠️ P0-12: 기본값 없음 - 반드시 Config에서 주입
  ) -> float:
      """순 기대값 계산 (R 단위)

      Args:
          win_rate: 승률 (0~1)
          avg_win_loss_ratio: 평균 손익비 (R)
          avg_loss_pct: 평균 손실률 (0~1), floor 적용됨
          cost_pct: 왕복 비용 (0~1) - 반드시 Config에서 파생하여 주입
      """
      cost_R = calculate_cost_R(cost_pct, avg_loss_pct)
      gross = (win_rate * avg_win_loss_ratio) - (1 - win_rate)
      return gross - cost_R

  def check_expectancy_filter(
      win_rate: float,
      avg_win_loss_ratio: float,
      avg_loss_pct: float,
      cost_pct: float,  # ⚠️ P0-12: 기본값 없음
      margin_R: float = 0.05
  ) -> tuple[bool, float]:
      """R-multiple 기반 기대값 필터 (P0-6, P0-12)"""
      net_expectancy_R = calculate_net_expectancy(
          win_rate, avg_win_loss_ratio, avg_loss_pct, cost_pct
      )
      return net_expectancy_R >= margin_R, net_expectancy_R

  def get_min_win_loss_ratio(
      win_rate: float,
      avg_loss_pct: float,
      cost_pct: float,  # ⚠️ P0-12: 기본값 없음
      margin_R: float = 0.05
  ) -> float:
      """승률에 따른 최소 손익비 계산 (P0-6, P0-12)"""
      cost_R = calculate_cost_R(cost_pct, avg_loss_pct)
      return ((1 - win_rate) + cost_R + margin_R) / win_rate
  ```
- [x] `QuickBacktestFilter._check_filters()`에 연동 필터 통합
- [x] 독립 필터(min_avg_win_loss_ratio) → 연동 필터로 교체

#### REFACTOR
- [x] avg_loss_pct 계산 로직 추출 (백테스트 결과에서)
- [x] 에러 핸들링 추가 (0으로 나누기 방지)

**Quality Gate**:
- [x] 모든 테스트 통과 (특히 계약 테스트)
- [x] 승률 33% + R=1.0 조합이 100% 차단됨
- [x] 기존 통과 케이스 영향 없음

**Dependencies**: Phase 1 완료

---

### Phase 3: 2단 게이트 통합 (2시간)

**목표**: Research → AI → Trading 파이프라인 완성

**⚠️ P0-5 핵심 설계: 1 Backtest, 2 Evaluations**
```
┌─────────────────────────────────────────────────────────────┐
│  백테스트 1회 실행 → metrics 캐싱                            │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
┌─────────────────────┐       ┌─────────────────────┐
│ Research Evaluation │       │ Trading Evaluation  │
│ (느슨한 임계값)      │       │ (엄격한 임계값)      │
└─────────────────────┘       └─────────────────────┘
```
- 백테스트는 **1회만** 실행 (비용/시간 절약)
- Research/Trading은 **같은 metrics**에 다른 임계값 적용
- 이중 백테스트 실행 절대 금지

**테스트 전략**:
- 통합 테스트: 전체 파이프라인 흐름
- 시나리오 테스트: Research 통과 → AI BUY → Trading 통과/실패
- **캐싱 검증**: 백테스트가 1회만 호출되는지 확인
- 커버리지 목표: 80%

**Tasks**:

#### RED (테스트 먼저)
- [x] `tests/scenarios/test_two_gate_pipeline.py` 생성
- [x] Research Pass 통과 시나리오 테스트
- [x] Trading Pass 차단 시나리오 테스트
- [ ] **캐싱 테스트**: 동일 ticker에 대해 백테스트 1회만 호출 확인 (선택적)
- [ ] **캐시 오염 방지 테스트 (P0-13)**: quick_config 파라미터 변경 시 캐시 재사용 방지 (선택적)
- [x] 전체 파이프라인 흐름 테스트
- [x] 테스트 작성 확인

#### GREEN (구현)
- [ ] `QuickBacktestFilter`에 **캐시 메커니즘** 추가 **(P0-8, P0-13 개선된 키 설계)**
  ```python
  from dataclasses import dataclass
  from typing import Dict, Optional, Any
  import uuid
  import json
  import hashlib

  def stable_hash(obj: dict) -> str:
      """설정 해시 (P0-13): 파라미터 변경 시 캐시 오염 방지"""
      payload = json.dumps(obj, sort_keys=True, separators=(",", ":"))
      return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10]

  @dataclass(frozen=True)
  class CacheKey:
      """캐시 키 (P0-13: ticker만으론 부족)"""
      ticker: str
      timeframe: str
      run_id: str
      config_hash: str  # ⚠️ 백테스트 파라미터/비용/룩백 등 포함

  class QuickBacktestFilter:
      def __init__(self):
          self._metrics_cache: Dict[CacheKey, Dict] = {}
          self._current_run_id: Optional[str] = None
          self._current_timeframe: str = "1h"
          self._current_config_hash: Optional[str] = None

      def start_scan_cycle(self, quick_config: Any) -> str:
          """스캔 사이클 시작 - 새 run_id 발급, 이전 캐시 정리"""
          self._current_run_id = str(uuid.uuid4())[:8]
          self._current_timeframe = getattr(quick_config, "timeframe", "1h")

          # ⚠️ 캐시에 영향을 주는 핵심 파라미터를 해시에 포함 (P0-13)
          cfg = {
              "timeframe": self._current_timeframe,
              "lookback": getattr(quick_config, "lookback", None),
              "strategy_version": getattr(quick_config, "strategy_version", None),
              "commission": getattr(quick_config, "commission", None),
              "slippage": getattr(quick_config, "slippage", None),
              "cost_pct": getattr(quick_config, "cost_pct", None),
          }
          self._current_config_hash = stable_hash(cfg)

          self._metrics_cache.clear()
          return self._current_run_id

      def _make_cache_key(self, ticker: str) -> CacheKey:
          if not self._current_run_id or not self._current_config_hash:
              raise RuntimeError("Must call start_scan_cycle(quick_config) first")
          return CacheKey(
              ticker=ticker,
              timeframe=self._current_timeframe,
              run_id=self._current_run_id,
              config_hash=self._current_config_hash,
          )

      def _get_or_run_backtest(self, ticker: str) -> Dict:
          key = self._make_cache_key(ticker)
          if key not in self._metrics_cache:
              result = self._run_backtest(ticker, self._current_timeframe)
              self._metrics_cache[key] = result.metrics
          return self._metrics_cache[key]
  ```
- [x] `evaluate_research_pass(metrics)`, `evaluate_trading_pass(metrics)` 분리
  ```python
  def evaluate_research_pass(self, metrics: Dict) -> PassResult:
      """Research 임계값으로 metrics 평가 (백테스트 미실행)"""
      return self._evaluate_with_thresholds(metrics, self.research_config)

  def evaluate_trading_pass(self, metrics: Dict) -> PassResult:
      """Trading 임계값으로 metrics 평가 (백테스트 미실행)"""
      return self._evaluate_with_thresholds(metrics, self.trading_config)
  ```
- [x] 파이프라인 스테이지에서 2단 게이트 호출
  ```python
  # HybridRiskCheckStage에서
  metrics = filter._get_or_run_backtest(ticker)  # 1회만 실행
  research_result = filter.evaluate_research_pass(metrics)
  if not research_result.passed:
      continue  # 후보 탈락

  # AI 분석 후, 실거래 전
  if ai_decision == 'buy':
      trading_result = filter.evaluate_trading_pass(metrics)  # 캐시된 metrics 사용
      if not trading_result.passed:
          log.warning(f"Trading Pass 실패: {trading_result.reason}")
          return  # 실거래 차단
  ```
- [x] 각 단계별 로깅 추가

#### REFACTOR
- [ ] 캐시 TTL/만료 정책 추가 (선택적)
- [x] 결과 객체 통합 (PassResult 사용)

**Quality Gate**:
- [x] 모든 테스트 통과
- [x] 로그에서 2단 게이트 흐름 확인 가능
- [x] 기존 스케줄러 동작 유지

**Dependencies**: Phase 2 완료

---

### Phase 4: 검증 및 모니터링 (2시간)

**목표**: 실제 운영 환경에서 검증

**테스트 전략**:
- E2E 테스트: 페이퍼 트레이딩 모드
- 모니터링: Prometheus 메트릭 추가

**Tasks**:

#### RED (테스트 먼저)
- [ ] `tests/e2e/test_filter_improvement.py` 생성
- [ ] 페이퍼 트레이딩 시뮬레이션 테스트
- [ ] 테스트 실패 확인

#### GREEN (구현)
- [ ] Prometheus 메트릭 추가
  - `backtest_research_pass_total` (Counter)
  - `backtest_trading_pass_total` (Counter)
  - `backtest_expectancy_value` (Gauge)
- [ ] Telegram 알림에 2단 게이트 결과 포함
- [ ] 1시간 동안 스케줄러 실행하여 결과 수집

#### REFACTOR
- [ ] 불필요한 로그 정리
- [ ] 성능 최적화 (필요 시)

**Quality Gate** (P1-11 수정 - 중복 제거, 구체적 지표):
- [ ] **안정성 확인**: 1시간 테스트 중 최소 1개 코인 Research Pass 통과
- [ ] **상한 확인**: 단일 스캔에서 80% 이상 통과 시 경고 발생 확인
- [ ] **기대값 검증**: 승률 33% + R=1.0 조합 Trading Pass에서 100% 차단
- [ ] **레짐 가드**: 2개 이상 레짐 실패 시 Trading Pass 차단 확인
- [ ] 기존 기능 회귀 없음
- [ ] Grafana 대시보드에서 메트릭 확인:
  - `backtest_research_pass_total` 카운터 증가 확인
  - `backtest_expectancy_value` 게이지 값 합리적 범위 (-0.5 ~ 0.5)

**Dependencies**: Phase 3 완료

---

## 5. 리스크 평가

| 리스크 | 확률 | 영향 | 완화 전략 |
|--------|------|------|----------|
| Research Pass가 너무 느슨 | Medium | Medium | 통과율 모니터링, 필요시 조정 |
| 기대값 계산 오류 | Low | High | 수학적 검증, 계약 테스트 |
| 기존 테스트 회귀 | Medium | Medium | 전체 테스트 스위트 실행 |
| 성능 저하 (이중 백테스트) | Low | Low | 캐싱 적용 |

---

## 6. 롤백 전략

### Phase별 롤백
- **Phase 1**: `BacktestFilterConfig` 삭제, 기존 Config 복원
- **Phase 2**: `expectancy_filter.py` 삭제, 기존 독립 필터 복원
- **Phase 3**: 파이프라인 호출 원복
- **Phase 4**: 메트릭 제거

### 긴급 롤백
```bash
git revert HEAD~N  # N = 롤백할 커밋 수
docker-compose restart scheduler
```

---

## 7. 진행 상황

| Phase | 상태 | 시작일 | 완료일 |
|-------|------|--------|--------|
| Phase 0 | ✅ 완료 | 2026-01-03 | 2026-01-03 |
| Phase 1 | ✅ 완료 | 2026-01-03 | 2026-01-03 |
| Phase 2 | ✅ 완료 | 2026-01-03 | 2026-01-03 |
| Phase 3 | ✅ 완료 | 2026-01-03 | 2026-01-03 |
| Phase 4 | ⬜ 대기 | - | - |

**Last Updated**: 2026-01-03 (Phase 0-3 구현 완료 확인)

---

## 8. 레퍼런스

### 외부 자료
- [3Commas: AI Trading Bot Performance](https://3commas.io/blog/ai-trading-bot-performance-analysis) - PF > 1.5 = strong
- [Coin Bureau: Backtest Guide 2025](https://coinbureau.com/guides/how-to-backtest-your-crypto-trading-strategy/) - 50-100 trades 권장
- [Freqtrade 백테스트 결과](https://www.freqtrade.io/en/stable/backtesting/) - 실제 PF/승률 사례

### 내부 파일
- `src/backtesting/quick_filter.py` - 현재 필터 구현
- `src/config/settings.py` - 설정 클래스
- `backend/app/core/scheduler.py` - 스케줄러 통합

---

## 9. Notes & Learnings

### 논의 중 발견된 핵심 인사이트

1. **승률↔손익비 연동 필수**
   - 승률 33% + 손익비 1.0 = 기대값 음수 (수수료 전에도)
   - 돌파전략(승률 30-35%)은 손익비 2.0 이상 필수

2. **수수료 단위 환산**
   - cost_R = cost_pct / avg_loss_pct
   - 예: 0.12% / 1% = 0.12R (시스템 기본값 기준)

3. **12개 동시 변경 위험**
   - 원인 추적 불가
   - Phase별 점진적 적용 필요

### 리뷰 결과 반영 (2026-01-03)

**1차 리뷰 - P0 (치명적 수정)**:
- [x] **P0-1**: 기대값 예시 수정 (0.155 - 0.2 = -0.045, 음수임)
- [x] **P0-2**: 최소 손익비 표 재계산 (공식과 일치)
- [x] **P0-3**: 단위 규칙 명시 (내부 0~1, 설정 %)
- [x] **P0-4**: cost_pct를 시스템 설정에서 파생 (0.12% 기본, 0.2% 스트레스)
- [x] **P0-5**: 1 Backtest, 2 Evaluations 구조 명시 (캐싱)

**1차 리뷰 - P1 (품질 보강)**:
- [x] **P1-6**: 탈락 분석에 gap(value - threshold) 추가
- [x] **P1-7**: volatility 정의 명확화 (일간 std × √365)
- [x] **P1-8**: Success Metrics를 안정성 지표로 변경

**2차 리뷰 - P0 (치명적 수정)**:
- [x] **P0-6**: 함수 시그니처 통일 (테스트/구현 모두 cost_pct, avg_loss_pct 사용)
- [x] **P0-7**: avg_loss_pct 정의 + floor 값 추가 (max(avg_loss_pct, 0.002))
- [x] **P0-8**: 캐시 키 설계 개선 (ticker + timeframe + run_id)

**2차 리뷰 - P1 (품질 보강)**:
- [x] **P1-9**: Trading Pass 레짐 가드 추가 (월별 PF 검증)
- [x] **P1-10**: volatility 기준 명확화 (equity curve 기반, 가격 아님)
- [x] **P1-11**: Phase 4 Quality Gate 중복 제거 및 구체화

**3차 리뷰 - P0 (치명적 수정)**:
- [x] **P0-12**: cost_pct 단일 소스 규칙 (기본값 제거, Config에서만 파생)
- [x] **P0-13**: 캐시 키에 config_hash 추가 (파라미터 변경 시 캐시 오염 방지)

**3차 리뷰 - P1 (품질 보강)**:
- [x] **P1-9 강화**: 레짐 가드 fallback(월별→병합→분기) + 최근 레짐 예외 0개
- [x] **문구 수정**: "24회=1일" → "최근 24시간 동안"

### 수학 검증 체크리스트 (Phase 2 진입 전 필수)

- [ ] 기대값 공식: `net = p×R - (1-p) - cost_R`
- [ ] 최소 손익비 공식: `R_min = ((1-p) + cost_R + margin_R) / p`
- [ ] 단위 통일: 모든 비율 0~1, % 변환은 I/O에서만
- [ ] cost_pct 파생: `(commission + slippage) × 2`

---

## Definition of Done

- [ ] 모든 Phase 완료
- [ ] 모든 Quality Gate 통과
- [ ] 테스트 커버리지 80% 이상
- [ ] Research Pass 통과율 30-50% 달성
- [ ] 기대값 음수 조합 100% 차단
- [ ] 문서 업데이트 완료
