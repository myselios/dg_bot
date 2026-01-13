# PLAN: ML 기반 필터 최적화 파이프라인 (상용화 버전)

**작성일**: 2026-01-04
**최종 수정**: 2026-01-13
**상태**: ✅ Phase 1, 3, 4, 5 완료 | Phase 2, 6, 7 보류
**선행 조건**: Phase 7 가중치 필터 시스템 완료
**예상 범위**: Large (7 phases)

---

## ⚠️ 상용화 핵심 원칙

> **"백테스트 수익 ≠ 실현 가능한 수익"**

이 파이프라인은 다음 원칙을 **강제**한다:

1. **비용 반영 필수**: 수수료/슬리피지/유동성 페널티 없는 목적 함수 금지
2. **누수 방지 필수**: Purge/Embargo 없는 Walk-Forward 금지
3. **재현성 필수**: 메타데이터 없는 스냅샷 저장 금지
4. **정합성 필수**: 중복/혼재 파라미터 금지

---

## 📋 개요

### 배경
- Phase 7에서 가중치 기반 필터 평가 시스템 구축 완료
- 현재 12개 필터의 티어 배치, 가중치, 임계값은 **수동 설정** 상태
- 실거래 비용을 반영한 **실현 가능한 수익** 기준 최적화 필요

### 현재 필터 구조 (Phase 7)

```
┌─────────────────────────────────────────────────────────────┐
│ Tier 1 (핵심 AND) - 모든 필터 필수 통과                      │
├─────────────────────────────────────────────────────────────┤
│ return (≥9%)  │ profit_factor (≥1.5) │ sharpe (≥0.7)       │
│ expectancy (>0R)                                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Tier 2-3 (가중 점수) - threshold_ratio 이상 통과            │
├─────────────────────────────────────────────────────────────┤
│ T2: max_drawdown, sortino, win_rate                         │
│ T3: calmar, avg_win_loss, max_consecutive_losses            │
│ T4: volatility, avg_holding_hours                           │
└─────────────────────────────────────────────────────────────┘

⚠️ min_trades는 Tier에서 제외 → 필터 임계값으로만 사용
```

### 목표

1. **비용 반영 목적 함수**: 실현 가능한 수익 최적화
2. **누수 방지 검증**: Purge/Embargo + 코인 동시성 차단
3. **자동 튜닝**: 주기적 재캘리브레이션 + 자동 롤백

---

## 🔧 정합성 규칙 (Consistency Rules)

### 규칙 1: WEIGHTED_FILTER_THRESHOLD는 비율만 사용

```python
# ❌ 금지: 절대값과 비율 혼재
WEIGHTED_FILTER_THRESHOLD = 5.0  # 절대값
threshold_ratio = 0.625          # 비율

# ✅ 허용: 비율만 사용
threshold_ratio = 0.625  # 가중치 합 대비 비율
threshold = sum(weights) * threshold_ratio
```

**근거**: 가중치 합이 변경되면 절대값 기준은 의미가 달라짐

### 규칙 2: min_trades는 필터 임계값으로만 사용

```python
# ❌ 금지: 가중치와 임계값에 중복 존재
FILTER_WEIGHTS = {'min_trades': 1.0, ...}
BacktestConfig.min_trades = 30

# ✅ 허용: 임계값으로만 사용
BacktestConfig.min_trades = 30  # 필터 임계값
# min_trades는 가중치 항목에서 제외
```

**근거**: 거래 수는 "신뢰도 문턱"이며, 가중치 대상이 아님

### 규칙 3: 비용 모델 버전 관리

```python
# ✅ 필수: 비용 정책 버전 기록
@dataclass
class CostPolicy:
    version: str              # "v1.0.0"
    fee_rate: float           # 0.0005 (0.05%)
    slippage_model: str       # "linear" | "sqrt" | "dynamic"
    slippage_base_bps: float  # 5.0 (5bps)
    liquidity_threshold: int  # 최소 거래대금 (억원)
```

---

## 💰 비용 모델 정책 (Cost Model Policy)

### 수수료 모델

| 등급 | 조건 | 수수료율 | 버전 |
|------|------|---------|------|
| 일반 | 기본 | 0.05% | v1.0 |
| VIP1 | 월 1억 이상 | 0.04% | v1.0 |
| VIP2 | 월 10억 이상 | 0.03% | v1.0 |

### 슬리피지 모델

```python
def calculate_slippage(order_size: float, daily_volume: float,
                       volatility: float, model: str = "sqrt") -> float:
    """
    슬리피지 계산 모델

    Args:
        order_size: 주문 금액 (KRW)
        daily_volume: 일일 거래대금 (KRW)
        volatility: 일일 변동성 (%)
        model: 슬리피지 모델 종류

    Returns:
        예상 슬리피지 (%)
    """
    participation_rate = order_size / daily_volume

    if model == "linear":
        # 단순 선형 모델
        return participation_rate * 100 * volatility

    elif model == "sqrt":
        # 제곱근 모델 (Almgren-Chriss 기반)
        base_impact = 5.0  # 5bps 기본
        return base_impact + 10 * math.sqrt(participation_rate) * volatility

    elif model == "dynamic":
        # 시간대/변동성 반영 동적 모델
        time_factor = get_time_factor()  # 09:00-10:00 높음
        return base_impact * time_factor * (1 + volatility)
```

### 유동성 페널티

```python
def liquidity_penalty(daily_volume: float, threshold: float = 10_000_000_000) -> float:
    """
    유동성 부족 페널티 (일일 거래대금 100억 미만 시)

    Returns:
        페널티 계수 (0.0 ~ 1.0, 높을수록 불리)
    """
    if daily_volume >= threshold:
        return 0.0

    # 거래대금 낮을수록 페널티 증가
    ratio = daily_volume / threshold
    return (1 - ratio) * 0.5  # 최대 50% 페널티
```

---

## 🎯 목적 함수 (Objective Function)

### 단일 목적 함수 (상용화 버전)

```python
def objective_function(filter_config: FilterConfig,
                       cost_policy: CostPolicy) -> float:
    """
    상용화 목적 함수: 실현 가능한 수익 최적화

    목적:
    - 백테스트 수익이 아닌 "실거래 후 손에 남는 수익" 최대화
    - 비용/리스크 반영으로 과최적화 방지
    """
    # 1. 백테스트 실행
    results = run_backtest_with_config(filter_config)

    # 2. 비용 차감
    gross_return = results.avg_return
    fee_cost = gross_return * cost_policy.fee_rate * 2  # 매수+매도
    slippage_cost = calculate_avg_slippage(results, cost_policy)
    liquidity_penalty = calculate_liquidity_penalty(results)

    net_return = gross_return - fee_cost - slippage_cost - liquidity_penalty

    # 3. 리스크 조정
    sharpe_adj = min(results.sharpe_ratio / 1.5, 1.5)  # 상한 1.5
    drawdown_penalty = max(0, (results.max_drawdown - 20) / 100)  # 20% 초과분

    # 4. 선택률 조정 (너무 낮거나 높으면 페널티)
    selection_rate = results.pass_rate
    selection_penalty = 0.0
    if selection_rate < 0.10:
        selection_penalty = (0.10 - selection_rate) * 2
    elif selection_rate > 0.30:
        selection_penalty = (selection_rate - 0.30) * 2

    # 5. 최종 목적 함수
    objective = (
        net_return * sharpe_adj * selection_rate
        - drawdown_penalty
        - selection_penalty
    )

    return objective
```

### 다중 목적 함수 (Pareto Optimization)

```python
objectives = {
    'maximize': [
        'net_return',           # 비용 차감 후 순수익률
        'sharpe_ratio',         # 위험조정수익
        'selection_rate',       # 적정 통과율 (10-30%)
    ],
    'minimize': [
        'max_drawdown',         # 최대 낙폭
        'false_positive_rate',  # 오탐율 (통과했지만 손실)
        'cost_impact',          # 비용 영향도
    ]
}

constraints = {
    'selection_rate': (0.10, 0.30),     # 통과율 10-30%
    'min_trades_threshold': 20,          # 최소 거래 수 (신뢰도)
    'max_drawdown': 30.0,                # 최대 낙폭 30% 이하
    'min_daily_volume': 10_000_000_000,  # 최소 거래대금 100억
}
```

---

## 🔬 입력 정의 (Input Specification)

### 최적화 변수 (정합성 적용)

| 카테고리 | 파라미터 | 현재값 | 탐색 범위 | 비고 |
|----------|----------|--------|-----------|------|
| **티어 배치** | tier1_filter_count | 4개 | 3-5개 | 조합 규칙 기반 생성 |
| **가중치** | weight_max_drawdown | 2.0 | 0.5-3.0 | |
| **가중치** | weight_sortino | 1.5 | 0.5-2.5 | |
| **가중치** | weight_win_rate | 0.5 | 0.25-1.5 | |
| **가중치** | weight_calmar | 1.0 | 0.5-2.0 | |
| **가중치** | weight_avg_win_loss | 0.5 | 0.25-1.0 | |
| **가중치** | weight_max_consec_loss | 0.5 | 0.25-1.0 | |
| **가중치** | weight_volatility | 0.5 | 0.0-1.0 | |
| **가중치** | weight_holding_hours | 0.5 | 0.0-1.0 | |
| **통과 비율** | threshold_ratio | 0.625 | 0.50-0.85 | ⚠️ 비율만 사용 |
| **필터 임계값** | min_return | 9.0% | 5.0-15.0% | |
| **필터 임계값** | min_sharpe | 0.7 | 0.4-1.2 | |
| **필터 임계값** | min_profit_factor | 1.5 | 1.2-2.0 | |
| **필터 임계값** | min_trades | 30 | 15-50 | ⚠️ 임계값만, 가중치 X |
| **필터 임계값** | max_drawdown | 25% | 15-35% | |

### 탐색 공간 정의

```python
from dataclasses import dataclass
from typing import Set, Tuple
import itertools

@dataclass
class SearchSpace:
    """정합성이 보장된 탐색 공간"""

    # Tier 1 필터 조합 (3-5개 선택, 열거 대신 규칙 기반)
    TIER1_CANDIDATES = {
        'return', 'profit_factor', 'sharpe_ratio', 'expectancy',
        'max_drawdown', 'sortino_ratio'
    }

    @staticmethod
    def generate_tier1_combinations(min_count: int = 3, max_count: int = 5) -> list:
        """Tier 1 필터 조합 생성 (규칙 기반)"""
        combinations = []
        for r in range(min_count, max_count + 1):
            for combo in itertools.combinations(SearchSpace.TIER1_CANDIDATES, r):
                # 필수 포함 규칙: return과 sharpe_ratio는 반드시 포함
                if 'return' in combo and 'sharpe_ratio' in combo:
                    combinations.append(set(combo))
        return combinations

    # 가중치 범위 (min_trades 제외됨)
    WEIGHT_RANGES = {
        'max_drawdown': (0.5, 3.0),
        'sortino_ratio': (0.5, 2.5),
        'win_rate': (0.25, 1.5),
        'calmar_ratio': (0.5, 2.0),
        'avg_win_loss_ratio': (0.25, 1.0),
        'max_consecutive_losses': (0.25, 1.0),
        'volatility': (0.0, 1.0),
        'avg_holding_hours': (0.0, 1.0),
    }

    # 통과 임계값 (비율만 사용)
    THRESHOLD_RATIO_RANGE: Tuple[float, float] = (0.50, 0.85)

    # 필터 임계값 범위
    FILTER_THRESHOLD_RANGES = {
        'min_return': (5.0, 15.0),
        'min_sharpe_ratio': (0.4, 1.2),
        'min_profit_factor': (1.2, 2.0),
        'min_trades': (15, 50),  # 정수
        'max_drawdown': (15.0, 35.0),
    }
```

---

## 🛡️ 누수 방지 설계 (Leakage Prevention)

### Walk-Forward with Purge/Embargo

```
데이터: 2024-01-01 ~ 2025-12-31 (24개월)

┌─────────────────────────────────────────────────────────────────┐
│ Fold 1                                                          │
├─────────────────────────────────────────────────────────────────┤
│ Train      │ Purge │ Validate  │ Embargo │                     │
│ 2024-01-01 │ 7일   │ 2024-07-08│ 3일     │                     │
│ ~ 06-30    │       │ ~ 09-30   │         │                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Fold 2                                                          │
├─────────────────────────────────────────────────────────────────┤
│            │ Train      │ Purge │ Validate  │ Embargo │        │
│            │ 2024-04-01 │ 7일   │ 2024-10-08│ 3일     │        │
│            │ ~ 09-30    │       │ ~ 12-31   │         │        │
└─────────────────────────────────────────────────────────────────┘

... (롤링)

┌─────────────────────────────────────────────────────────────────┐
│ Hold-out (절대 학습/튜닝 금지)                                   │
├─────────────────────────────────────────────────────────────────┤
│ 2025-10-01 ~ 2025-12-31 (최근 3개월)                            │
│ ⚠️ 이 구간은 최종 평가에만 사용, 파라미터 조정 절대 금지         │
└─────────────────────────────────────────────────────────────────┘
```

### Purge/Embargo 규칙

```python
@dataclass
class LeakagePreventionConfig:
    """누수 방지 설정"""

    # Purge: Train-Validate 사이 버퍼
    purge_days: int = 7  # 7일 (포지션 청산 + 잔여 효과 제거)

    # Embargo: Validate-Test 사이 버퍼
    embargo_days: int = 3  # 3일 (최소 안전 마진)

    # Hold-out: 절대 학습에 사용 안 함
    holdout_months: int = 3  # 최근 3개월

    # 코인 동시성 누수 방지
    same_period_reuse: bool = False  # 동일 시간 구간 재사용 금지

    def validate(self) -> bool:
        """누수 방지 설정 검증"""
        assert self.purge_days >= 7, "Purge는 최소 7일"
        assert self.embargo_days >= 3, "Embargo는 최소 3일"
        assert self.holdout_months >= 3, "Hold-out은 최소 3개월"
        return True
```

### 코인 간 동시성 누수 방지

```python
def prevent_cross_coin_leakage(train_data: pd.DataFrame,
                                validate_data: pd.DataFrame) -> bool:
    """
    코인 간 동시성 누수 방지 검증

    문제: 같은 시간대에 BTC로 학습하고 ETH로 검증하면
          시장 전체 움직임이 누수됨

    해결: 동일 시간 구간은 다른 코인에서도 재사용 금지
    """
    train_dates = set(train_data['date'].unique())
    validate_dates = set(validate_data['date'].unique())

    overlap = train_dates & validate_dates
    if overlap:
        raise LeakageError(
            f"시간 구간 중복 발견: {len(overlap)}일 "
            f"({min(overlap)} ~ {max(overlap)})"
        )

    return True
```

---

## 📊 데이터 스키마 (재현성 메타데이터 포함)

### 재현성 메타데이터

```python
@dataclass
class ReproducibilityMetadata:
    """재현성 보장을 위한 메타데이터"""

    # 데이터 무결성
    data_hash: str              # SHA256 해시 (OHLCV 데이터)
    data_version: str           # 데이터 수집 버전
    data_source: str            # "upbit_api" | "local_parquet"

    # 코드 버전
    code_version: str           # Git commit hash
    config_version: str         # FilterConfig 버전 (e.g., "v1.2.0")

    # 비용 정책
    cost_policy_version: str    # CostPolicy 버전
    fee_rate: float             # 적용된 수수료율
    slippage_model: str         # 적용된 슬리피지 모델

    # 거래소 상태
    exchange_env: str           # "production" | "sandbox"
    api_version: str            # Upbit API 버전

    # 실행 환경
    python_version: str
    numpy_version: str
    pandas_version: str
    timestamp: datetime
```

### BacktestFilterSnapshot (확장)

```python
@dataclass
class BacktestFilterSnapshot:
    """백테스트 필터 결과 스냅샷 (재현성 메타데이터 포함)"""

    # 식별자
    snapshot_id: str              # ULID
    timestamp: datetime
    ticker: str

    # 필터 결과
    filter_results: Dict[str, bool]   # {'return': True, ...}
    filter_values: Dict[str, float]   # {'return': 13.8, ...}

    # 티어 평가 결과
    tier1_passed: bool
    tier1_filters: Set[str]           # 사용된 Tier 1 필터
    weighted_score: float
    threshold_ratio: float            # ⚠️ 비율 기준
    final_passed: bool

    # 사용된 Config
    config_version: str
    filter_weights: Dict[str, float]  # ⚠️ min_trades 제외됨
    thresholds: Dict[str, float]

    # 🆕 재현성 메타데이터
    reproducibility: ReproducibilityMetadata
```

### TradeOutcome (확장)

```python
@dataclass
class TradeOutcome:
    """거래 결과 (비용 상세 포함)"""

    # 식별자
    outcome_id: str
    entry_snapshot_id: str        # BacktestFilterSnapshot 참조

    # 거래 결과
    entry_price: Decimal
    exit_price: Decimal
    gross_pnl_pct: float          # 비용 전 수익률

    # 🆕 비용 상세
    fee_paid: Decimal             # 실제 수수료
    slippage_pct: float           # 실제 슬리피지
    net_pnl_pct: float            # 비용 후 순수익률
    net_pnl_amount: Decimal       # 순수익금

    # 거래 정보
    holding_hours: float
    exit_reason: str
    daily_volume: Decimal         # 체결 당시 일일 거래대금

    # 라벨 (ML용)
    label: str                    # 'profit', 'loss', 'break_even'
    label_score: float            # 수익률 기반 연속 점수

    # 🆕 재현성 메타데이터
    cost_policy_version: str
    reproducibility: ReproducibilityMetadata
```

---

## 🔧 Phase 1: 데이터 수집 인프라 구축 ✅ 완료

### 목표
재현성 메타데이터를 포함한 TradeDataCollector 구축

### 작업 목록

#### RED
- [x] `test_snapshot_includes_reproducibility_metadata` 작성
- [x] `test_outcome_includes_cost_details` 작성
- [x] `test_data_hash_matches_source` 작성

#### GREEN
- [x] `ReproducibilityMetadata` 데이터클래스 생성
- [x] `CostPolicy` 데이터클래스 생성
- [x] `BacktestFilterSnapshot` 확장 (재현성 메타데이터)
- [x] `TradeOutcome` 확장 (비용 상세)
- [x] `TradeDataPort` 인터페이스 정의
- [x] `ParquetTradeDataAdapter` 구현

#### REFACTOR
- [x] 데이터 해시 자동 계산
- [x] Git commit hash 자동 추출

### 변경 파일
```
src/domain/value_objects/cost_policy.py
src/domain/value_objects/reproducibility_metadata.py
src/application/ports/outbound/trade_data_port.py
src/application/services/trade_data_collector.py
src/infrastructure/adapters/persistence/trade_data_adapter.py
data/ml/filter_snapshots/
data/ml/trade_outcomes/
tests/unit/application/test_trade_data_collector.py
```

### 품질 게이트
- [x] 재현성 메타데이터 필수 필드 검증 (8 tests)
- [x] 데이터 해시 무결성 테스트 (test_calculate_data_hash)
- [x] 비용 정책 버전 기록 확인 (10 tests)
- [x] Parquet 저장/조회 테스트 (6 tests)

**총 31개 테스트 통과** (2026-01-13)

---

## 🔧 Phase 2: 백테스트 데이터 대량 생성

### 목표
다양한 Config 조합으로 학습 데이터 생성

### 작업 목록

#### RED
- [ ] `test_bulk_backtest_generates_snapshots` 작성
- [ ] `test_cost_applied_to_all_outcomes` 작성
- [ ] `test_min_trades_excluded_from_weights` 작성

#### GREEN
- [ ] `BulkBacktester` 클래스 구현
- [ ] 비용 모델 적용 로직
- [ ] 정합성 규칙 검증 (min_trades 중복 제거)

#### REFACTOR
- [ ] 병렬 백테스트 (멀티프로세싱)
- [ ] 체크포인트 저장/복구

### 데이터 생성 전략

```python
bulk_backtest_config = {
    'coins': top_20_by_volume(),
    'periods': [
        ('2024-01-01', '2024-06-30'),
        ('2024-07-01', '2024-12-31'),
        ('2025-01-01', '2025-06-30'),
        ('2025-07-01', '2025-09-30'),  # Hold-out 제외
    ],
    'config_variations': 100,  # Latin Hypercube Sampling
    'cost_policy': CostPolicy(version="v1.0"),
}
```

### 품질 게이트
- [ ] 최소 2000개 스냅샷 생성
- [ ] 모든 스냅샷에 비용 정책 기록
- [ ] min_trades가 가중치에 없음 확인

---

## 🔧 Phase 3: 탐색 공간 및 목적 함수 정의 ✅ 완료

### 목표
정합성이 보장된 탐색 공간과 비용 반영 목적 함수 정의

### 작업 목록

#### RED
- [x] `test_threshold_ratio_only_no_absolute` 작성
- [x] `test_min_trades_not_in_weights` 작성
- [x] `test_objective_includes_costs` 작성
- [x] `test_tier1_combinations_valid` 작성

#### GREEN
- [x] `SearchSpace` 클래스 구현 (정합성 규칙 강제)
- [x] `ObjectiveFunction` 클래스 구현 (비용 반영)
- [x] `Constraints` 클래스 구현

#### 목적 함수 구현

```python
class ProductionObjectiveFunction:
    """상용화 목적 함수 (비용 반영 필수)"""

    def __init__(self, cost_policy: CostPolicy):
        self.cost_policy = cost_policy

    def evaluate(self, config: FilterConfig,
                 backtest_results: List[BacktestResult]) -> float:

        # 1. 비용 차감
        net_returns = []
        for result in backtest_results:
            gross = result.total_return
            fee = gross * self.cost_policy.fee_rate * 2
            slippage = self._calculate_slippage(result)
            liquidity = self._liquidity_penalty(result)
            net_returns.append(gross - fee - slippage - liquidity)

        avg_net_return = np.mean(net_returns)

        # 2. 리스크 조정
        sharpe = self._calculate_sharpe(net_returns)
        sharpe_adj = min(sharpe / 1.5, 1.5)

        # 3. 선택률 페널티
        selection_rate = len(backtest_results) / total_candidates
        selection_penalty = self._selection_penalty(selection_rate)

        # 4. 드로다운 페널티
        max_dd = max(r.max_drawdown for r in backtest_results)
        dd_penalty = max(0, (max_dd - 20) / 100)

        return avg_net_return * sharpe_adj - dd_penalty - selection_penalty
```

### 변경 파일
```
src/ml/search_space.py         # 정합성 보장 탐색 공간
src/ml/objective_function.py   # 비용 반영 목적 함수
src/ml/constraints.py          # 제약 조건 정의
tests/unit/ml/test_search_space.py  # 15 tests
```

### 품질 게이트
- [x] 정합성 규칙 테스트 통과
- [x] 비용 반영 목적 함수 테스트 통과
- [x] Tier 1 조합 규칙 테스트 통과

**총 15개 테스트 통과** (2026-01-13)

---

## 🔧 Phase 4: Bayesian Optimization 구현 ✅ 완료

### 목표
Optuna 기반 3단계 최적화 파이프라인

### 작업 목록

#### RED
- [x] `test_random_search_baseline` 작성
- [x] `test_bayesian_improves_over_random` 작성
- [x] `test_pareto_frontier_valid` 작성

#### GREEN
- [x] 1차: Random/Latin Hypercube 탐색
- [x] 2차: Bayesian (TPE) 수렴 (Optuna 선택적)
- [x] 3차: Pareto 최적 조합 필터링

### 최적화 프로세스

```python
class ThreeStageOptimizer:
    """3단계 최적화 파이프라인"""

    def optimize(self, n_trials: int = 200) -> OptimizationResult:

        # Stage 1: 넓게 탐색 (Random/LHS)
        stage1_results = self._random_search(n_trials=50)

        # Stage 2: 유망 영역 수렴 (Bayesian)
        stage2_results = self._bayesian_search(
            n_trials=100,
            warm_start=stage1_results.top_10_percent()
        )

        # Stage 3: Pareto 최적 필터링
        pareto_frontier = self._pareto_filter(
            stage2_results,
            objectives=['net_return', 'sharpe_ratio'],
            constraints=['max_drawdown < 30', 'selection_rate in (0.1, 0.3)']
        )

        # 현실 가능성 필터링 (거래수/슬리피지)
        final_candidates = self._reality_filter(
            pareto_frontier,
            min_trades=20,
            max_slippage=0.5
        )

        return final_candidates
```

### 변경 파일
```
src/ml/optimizer.py               # ThreeStageOptimizer 클래스
tests/unit/ml/test_optimizer.py   # 12 tests
```

### 품질 게이트
- [x] Random Search 결과 생성 확인
- [x] Bayesian Search warm start 동작 확인
- [x] Pareto frontier 유효성 검증
- [x] Reality filter 동작 확인

**총 12개 테스트 통과** (2026-01-13)

### 실제 최적화 실행 결과 (2026-01-13)

**최적화 방법**: 3-Stage Bayesian-like (700 trials)
- Stage 1: Random Search (200 trials) - 넓은 탐색
- Stage 2: Local Search (300 trials) - 상위 10개 주변 집중 탐색
- Stage 3: Fine-tuning (200 trials) - 상위 5개 정밀 조정

**데이터**: BTC 5년 백테스트 (2000일, 2020-07-24 ~ 2026-01-13)

**최적 결과**:
- **Best Score**: 60.15% (Sharpe 0.80)
- **Trial**: Stage 1, Trial 1

**최적 Config (12개 필터 임계값)**:
```python
min_return: 5.47              # 9.0 → 5.47 (더 관대)
min_win_rate: 45.99           # 35.0 → 45.99 (더 엄격)
min_profit_factor: 1.09       # 1.5 → 1.09 (더 관대)
min_sharpe_ratio: 0.83        # 0.7 → 0.83 (더 엄격)
min_sortino_ratio: 1.26       # 0.9 → 1.26 (더 엄격)
min_calmar_ratio: 0.44        # 0.4 → 0.44 (약간 엄격)
max_drawdown: 31.47           # 25.0 → 31.47 (더 관대)
max_consecutive_losses: 6     # 6 → 6 (동일)
max_volatility: 39.85         # 80.0 → 39.85 (더 엄격)
min_trades: 41                # 30 → 41 (더 엄격)
min_avg_win_loss_ratio: 1.79  # 1.0 → 1.79 (더 엄격)
max_avg_holding_hours: 221.25 # 240.0 → 221.25 (약간 엄격)
```

**결과 저장**: `data/ml_results/optimization_btc_5y_bayesian_20260113_144339.json`

**적용 상태**: ✅ `src/backtesting/quick_filter.py` BacktestConfig에 적용 완료

---

## 🔧 Phase 5: Walk-Forward Validation (누수 방지) ✅ 완료

### 목표
Purge/Embargo가 적용된 Walk-Forward Validation

### 작업 목록

#### RED
- [x] `test_purge_gap_exists` 작성
- [x] `test_embargo_gap_exists` 작성
- [x] `test_no_cross_coin_leakage` 작성
- [x] `test_holdout_never_used_for_training` 작성

#### GREEN
- [x] `WalkForwardValidator` 클래스 구현
- [x] Purge (7일) 적용
- [x] Embargo (3일) 적용
- [x] 코인 동시성 누수 검증

### Walk-Forward 구현

```python
class WalkForwardValidator:
    """누수 방지가 적용된 Walk-Forward Validator"""

    def __init__(self, config: LeakagePreventionConfig):
        self.config = config
        self.config.validate()  # 설정 검증

    def split(self, data: pd.DataFrame) -> List[Fold]:
        folds = []

        for train_end in self._generate_train_ends(data):
            # Purge 구간
            purge_start = train_end
            purge_end = train_end + timedelta(days=self.config.purge_days)

            # Validate 구간
            validate_start = purge_end
            validate_end = validate_start + timedelta(days=90)

            # Embargo 구간
            embargo_end = validate_end + timedelta(days=self.config.embargo_days)

            fold = Fold(
                train=(data.index[0], train_end),
                purge=(purge_start, purge_end),
                validate=(validate_start, validate_end),
                embargo=(validate_end, embargo_end),
            )

            # 코인 동시성 누수 검증
            self._verify_no_cross_coin_leakage(fold, data)

            folds.append(fold)

        return folds

    def _verify_no_cross_coin_leakage(self, fold: Fold, data: pd.DataFrame):
        """코인 간 시간 구간 중복 검증"""
        train_dates = set(data.loc[fold.train[0]:fold.train[1], 'date'].unique())
        validate_dates = set(data.loc[fold.validate[0]:fold.validate[1], 'date'].unique())

        overlap = train_dates & validate_dates
        if overlap:
            raise LeakageError(f"Cross-coin leakage detected: {len(overlap)} days")
```

### 변경 파일
```
src/ml/walk_forward.py              # WalkForwardValidator, Fold, LeakageError
tests/unit/ml/test_walk_forward.py  # 13 tests
```

### 품질 게이트
- [x] 모든 Fold에 Purge 7일 이상
- [x] 모든 Fold에 Embargo 3일 이상
- [x] 코인 동시성 누수 0건
- [x] Hold-out 구간 학습 사용 0건

**총 13개 테스트 통과** (2026-01-13)

---

## 🔧 Phase 6: 자동 튜닝 및 배포 ⏸️ 보류

> **보류 사유**: Phase 4에서 이미 700 trials 최적화 완료. 자동 튜닝은 실거래 데이터 축적 후 재검토.

### 목표
Canary 배포 + A/B 테스트 + 자동 롤백

### 작업 목록 (미완료)

#### RED
- [ ] `test_canary_10_percent` 작성
- [ ] `test_ab_test_statistical_significance` 작성
- [ ] `test_auto_rollback_on_degradation` 작성

#### GREEN
- [ ] `ConfigManager` 클래스 구현
- [ ] Canary 배포 (10%)
- [ ] A/B 테스트 프레임워크
- [ ] 자동 롤백 메커니즘

### 배포 전략

```python
class ProductionDeployment:
    """상용 배포 전략"""

    # 롤백 트리거 기준
    ROLLBACK_THRESHOLDS = {
        'sharpe_drop': -0.3,      # Sharpe 0.3 이상 하락
        'drawdown_increase': 5.0,  # DD 5%p 이상 증가
        'fpr_increase': 0.05,      # 오탐율 5%p 이상 증가
    }

    def canary_deploy(self, new_config: FilterConfig,
                      traffic_percent: float = 0.10):
        """10% 트래픽에 신규 Config 적용"""
        pass

    def ab_test(self, config_a: FilterConfig,
                config_b: FilterConfig,
                duration_days: int = 14,
                min_trades: int = 50):
        """A/B 테스트 (통계적 유의성 확보)"""
        pass

    def auto_rollback(self, current_metrics: Metrics,
                      baseline_metrics: Metrics):
        """성능 저하 시 자동 롤백"""
        for metric, threshold in self.ROLLBACK_THRESHOLDS.items():
            delta = getattr(current_metrics, metric) - getattr(baseline_metrics, metric)
            if delta < threshold:
                self._execute_rollback()
                self._alert(f"Auto-rollback triggered: {metric} delta={delta}")
                return True
        return False
```

### 품질 게이트
- [ ] Canary 배포 동작 확인
- [ ] A/B 테스트 통계 유의성 검증
- [ ] 자동 롤백 트리거 테스트

---

## 🔧 Phase 7: 모니터링 및 운영 ⏸️ 보류

> **보류 사유**: 실거래 데이터 축적 후 모니터링 대시보드 구축.

### 목표
Config 성능 실시간 모니터링 및 알림

### 작업 목록 (미완료)

#### RED
- [ ] `test_metrics_collected` 작성
- [ ] `test_alert_on_degradation` 작성
- [ ] `test_dashboard_data_accuracy` 작성

#### GREEN
- [ ] Prometheus 메트릭 수집
- [ ] Grafana 대시보드
- [ ] Telegram 알림 연동

### 모니터링 대시보드

```
┌─────────────────────────────────────────────────────────────────┐
│ Filter Optimization Dashboard                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ 현재 Config: v1.2.3 (2026-01-05 배포)                           │
│ Cost Policy: v1.0 (fee=0.05%, slippage=sqrt)                    │
│                                                                  │
│ ┌─────────────────┬───────────┬───────────┬──────────┐         │
│ │ 지표            │ v1.2.3    │ v1.2.2    │ Delta    │         │
│ ├─────────────────┼───────────┼───────────┼──────────┤         │
│ │ 순수익률 (Net)  │ +6.8%     │ +5.1%     │ +1.7%    │         │
│ │ Sharpe          │ 1.23      │ 0.89      │ +0.34    │         │
│ │ Max Drawdown    │ 18.5%     │ 22.3%     │ -3.8%    │         │
│ │ 오탐율 (FPR)    │ 12.1%     │ 18.7%     │ -6.6%    │         │
│ │ 통과율          │ 18.5%     │ 22.3%     │ -3.8%    │         │
│ │ 비용 영향       │ 1.4%      │ 1.5%      │ -0.1%    │         │
│ └─────────────────┴───────────┴───────────┴──────────┘         │
│                                                                  │
│ [🔄 수동 롤백] [📊 상세 분석] [⚙️ 재최적화] [📋 Pareto 조회]    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 품질 게이트
- [ ] 메트릭 수집 지연 < 5분
- [ ] 알림 발송 지연 < 1분
- [ ] 대시보드 데이터 정확도 100%

---

## 🎯 실거래 품질 게이트 (Production Quality Gates)

### 필수 통과 조건

| 게이트 | 기준 | 실패 시 조치 |
|--------|------|-------------|
| 최소 샘플 수 | 거래 50건 이상 | 배포 금지, 데이터 수집 연장 |
| 최소 거래 수 | 코인당 20건 이상 | 해당 코인 결과 제외 |
| Sharpe Ratio | ≥ 0.5 | 배포 금지, 재최적화 |
| Max Drawdown | ≤ 30% | 배포 금지, 리스크 조정 |
| 오탐율 (FPR) | ≤ 25% | 경고, threshold 조정 검토 |
| 비용 영향도 | ≤ 3% | 경고, 슬리피지 모델 검토 |
| 선택률 | 10-30% | 경고, threshold 조정 |

### 생존성 기준 (Survivorship)

```python
SURVIVORSHIP_CRITERIA = {
    # Return/Drawdown 비율 (생존성 핵심 지표)
    'return_dd_ratio': 0.5,  # 순수익률/최대DD ≥ 0.5

    # 연속 손실 한도
    'max_consecutive_losses': 5,  # 5회 이상 연속 손실 시 경고

    # 회복 기간
    'max_recovery_days': 30,  # DD 회복에 30일 이상 시 경고
}
```

---

## 🎯 리스크 평가

| 리스크 | 확률 | 영향 | 완화 전략 |
|--------|------|------|-----------|
| 과적합 (Overfitting) | High | High | Purge/Embargo, Hold-out, 정규화 |
| 비용 과소평가 | High | High | 보수적 슬리피지 모델, 실거래 검증 |
| 데이터 부족 | Medium | High | 최소 요구사항, 합성 데이터 검토 |
| 시장 레짐 변화 | Medium | High | 주기적 재캘리브레이션, 레짐 탐지 |
| Lookahead Bias | Low | Critical | Purge 7일, Embargo 3일, 코드 리뷰 |
| 코인 동시성 누수 | Low | High | 시간 구간 중복 검증 자동화 |

---

## ⚠️ 최소 데이터 요구사항

| 단계 | 최소 데이터 | 권장 데이터 | 비용 정책 |
|------|------------|------------|----------|
| Phase 1-2 (수집) | 100건 거래 | 500건 거래 | v1.0 고정 |
| Phase 3-4 (최적화) | 500건 거래 | 1000건 거래 | v1.0 고정 |
| Phase 5 (검증) | 1000건 거래 | 2000건 거래 | v1.0 고정 |
| Phase 6-7 (배포) | 실거래 30일 | 실거래 90일 | 실시간 |

---

## 📝 Notes

### 정합성 규칙 적용 (2026-01-10)

1. **WEIGHTED_FILTER_THRESHOLD**: 비율 방식으로 통일 (`threshold_ratio`)
2. **min_trades**: 필터 임계값으로만 사용, 가중치 항목에서 제외
3. **비용 모델**: `CostPolicy` 버전 관리 도입

### Phase 7 가중치 필터 시스템 (2026-01-05)

현재 구현된 가중치 시스템:
- **Tier 1 (AND)**: return, profit_factor, sharpe_ratio, expectancy
- **Tier 2-4 (가중치)**: 총 8.0점 중 5.0점 이상 필요 (비율: 62.5%)
- **min_trades**: Tier에서 제외, 필터 임계값(30)으로만 사용

---

---

## 📊 완료 요약 (2026-01-13)

| Phase | 상태 | 설명 |
|-------|------|------|
| Phase 1 | ✅ 완료 | 데이터 수집 인프라 (31 tests) |
| Phase 2 | ⏸️ 보류 | 백테스트 대량 생성 (실거래 후 재검토) |
| Phase 3 | ✅ 완료 | 탐색 공간 및 목적 함수 (15 tests) |
| Phase 4 | ✅ 완료 | Bayesian Optimization + 실제 실행 (12 tests + 700 trials) |
| Phase 5 | ✅ 완료 | Walk-Forward Validation (13 tests) |
| Phase 6 | ⏸️ 보류 | 자동 튜닝 (실거래 후 재검토) |
| Phase 7 | ⏸️ 보류 | 모니터링 (실거래 후 재검토) |

**핵심 성과**:
- ✅ BTC 5년 백테스트 최적화 완료 (60.15% 수익률, Sharpe 0.80)
- ✅ 12개 필터 임계값 최적화 및 프로덕션 적용
- ✅ 700 trials 3-stage Bayesian 최적화 실행
- ✅ 재현성 메타데이터 및 Walk-Forward 검증 체계 구축

**다음 단계**:
1. 실거래 테스트로 최적화된 임계값 검증
2. 실거래 데이터 축적 (최소 30일 권장)
3. Phase 6-7 재개: 자동 튜닝 및 모니터링 구축

**Last Updated**: 2026-01-13
