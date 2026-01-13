# 백테스팅 시스템 리뷰 및 리팩토링 계획

**날짜**: 2026-01-13
**검운자**: Antigravity (Agentic AI)
**범위**: `docs/guide/BACKTESTING_GUIDE.md`, `src/backtesting/`

---

## 1. 클린 아키텍처 리뷰 (Clean Architecture Review)

### 1.1. 의존성 규칙 위반 (Dependency Rule Violations)
클린 아키텍처의 가장 핵심적인 규칙은 소스 코드 의존성이 오직 내부(고수준 정책)를 향해야 한다는 것입니다.

-   **`Backtester`에서의 위반:** `Backtester` 클래스(도메인 서비스 또는 애플리케이션 유스케이스 역할)가 인프라 계층의 구현 세부 사항을 직접 임포트하고 있습니다.
    ```python
    # src/backtesting/backtester.py
    from src.infrastructure.adapters.execution import (
        SimpleExecutionAdapter,
        IntrabarExecutionAdapter,
    )
    ```
    **수정 방안:** `Backtester`는 오직 `ExecutionPort` 인터페이스에만 의존해야 합니다. 구체적인 어댑터는 의존성 주입(Dependency Injection, 주로 생성자 주입)을 통해 주입받아야 하며, 이를 통해 핵심 로직이 인프라 세부 사항으로부터 독립적으로 유지되도록 해야 합니다.

-   **`QuickBacktestFilter`에서의 위반:** 이 클래스는 고수준 서비스 역할을 하지만 `HistoricalDataProvider` (인프라/데이터)를 직접 인스턴스화하고 있습니다.
    ```python
    # src/backtesting/quick_filter.py
    self.data_provider = HistoricalDataProvider()
    ```
    **수정 방안:** `DataProvider` 포트/인터페이스에 의존하도록 변경해야 합니다.

### 1.2. 관심사의 분리 (Separation of Concerns)
-   **최적화된 로직 vs 클린 로직 (`RuleBasedBreakoutStrategy`):** 전략 클래스가 "캐시된/벡터화된" 데이터 처리 로직과 "일반적인" 경로 의존적 체크 로직을 중복해서 포함하고 있습니다.
    -   *예시:* `_check_gate1_squeeze` 메서드는 거의 동일한 작업을 수행하는 두 개의 서로 다른 로직 블록(하나는 `_cached_indicators` 용, 하나는 실시간 계산 용)을 가지고 있습니다.
    -   **리팩토링:** "Indicator Provider" 개념을 캡슐화해야 합니다. 전략은 `IndicatorService`에 값(예: `indicators.get_bb_width(index)`)을 요청하기만 하고, 서비스가 미리 계산된 벡터에서 가져올지 실시간으로 계산할지를 처리하도록 해야 합니다.

-   **갓 클래스 (God Class - `QuickBacktestFilter`):**
    -   이 클래스는 설정(Configuration), 데이터 로드, 백테스트 실행, 지표 계산, 필터링 로직, *그리고* 결과 출력까지 모두 처리하고 있습니다.
    -   이는 **단일 책임 원칙(SRP)**을 위반합니다.
    -   **리팩토링:** 다음과 같이 분리해야 합니다:
        -   `BacktestService` (오케스트레이션/조정)
        -   `BacktestFilter` (순수 필터링 로직)
        -   `BacktestConsolePresenter` (출력 형식 지정 및 프린트)

### 1.3. 빈약한 도메인 모델 (Domain Model Anemicity)
-   `BacktestConfig`는 단순한 데이터 클래스이지만, 이 설정을 검증하거나 해석하는 로직은 `QuickBacktestFilter`에 분산되어 있습니다. 일부 "비즈니스 규칙"(예: 무엇이 "통과"를 정의하는가)은 도메인 엔티티에 더 가깝게 위치해야 합니다.

---

## 2. 퀀트 트레이딩 및 백테스팅 리뷰 (Quantitative Trading & Backtesting Review)

### 2.1. 미래 참조 편향 (Look-Ahead Bias)
-   **처리는 대체로 정확함:** `execute_on_next_open=True` 기능은 매우 훌륭하며 필수적입니다. 현재 봉의 *종가*에 신호가 발생하면 *다음* 봉의 시가에 거래를 시뮬레이션하는 것을 올바르게 처리하고 있습니다.
-   **전략 내의 미세한 잠재적 문제:** `_check_trend_filter`에서 `current_price > ma`를 사용하고 있습니다. 만약 `ma`가 *현재* 봉의 종가를 포함하여 계산된다면(pandas `rolling().mean()`의 기본 동작), `ma`는 현재 가격 정보를 "알고 있는" 상태가 됩니다. 실행이 다음 시가로 지연된다면 큰 문제는 아니지만, 엄밀한 의미의 추세 필터는 보통 "신호 발생 *이전*에 확립된 추세"를 의미합니다.
    -   *권장 사항:* `ma`를 1만큼 shift하여 사용하거나, `current_price` 비교가 오직 종가 마감 시점의 "셋업 확인" 용도로만 사용되도록 명확히 해야 합니다.

### 2.2. 과적합 위험 (Overfitting Risks)
-   **"12개 필터"의 경직성:** 샤프 지수 > 0.7, 승률 > 35% 등 하드코딩된 임계값을 가진 12개 필터를 *모두* 통과해야 한다는 조건은 선택 기준에 대한 파라미터 최적화(또는 "커브 피팅")의 형태가 될 수 있습니다.
    -   *위험요소:* 특정 타임프레임이나 자산 조합에서 우연히 통과하는 전략이 선택될 수 있습니다.
    -   *완화 방안:* 가이드에 언급된 "가중치 필터(Weighted Filter)" (Phase 7)가 엄격한 "AND" 게이트보다 더 나은 접근 방식입니다. 트레이드 오프를 허용해야 합니다(예: 승률이 조금 낮더라도 평균 손익비가 매우 높다면 통과).
-   **표본 크기:** `min_trades` 필터(현재 30, 일부 문서는 10으로 기재)는 매우 낮습니다. n=30에서의 통계적 유의성은 약합니다.
    -   *권장 사항:* 신뢰할 수 있는 통계를 위해 `min_trades`를 최소 50-100으로 늘리거나, "부트스트래핑(Bootstrapping)"을 사용하여 견고성을 테스트해야 합니다.

### 2.3. 거래 비용 및 현실성 (Transaction Costs & Realism)
-   **슬리피지 모델:** 코드가 `orderbook` 기반 슬리피지를 지원하는 것은 매우 진보적이고 훌륭합니다. 기본 퍼센트 모델(`0.01%`)은 유동성이 풍부한 페어에는 합리적이지만 알트코인에는 낙관적일 수 있습니다.
-   **시장 충격(Market Impact):** 자본금(`initial_capital` 기본 1,000만 원)이 작을 때는 시장 충격이 무시할 만하지만, 확장 가능한 시스템은 이를 고려해야 합니다.

### 2.4. 봉 내 로직 (`use_intrabar_stops`)
-   이것은 매우 가치 있는 기능입니다. 현재 구현은 봉의 `High/Low`를 보고 스탑로스(SL)나 테이크프로핏(TP)이 도달했는지 판단합니다.
-   **모호성 처리:** 단일 봉의 High-Low 범위 내에 SL과 TP가 모두 존재하는 경우, OHLC 데이터만으로는 무엇이 먼저 도달했는지 알 수 없습니다. 코드는 "스탑로스 우선(Stop Loss First)"(최악의 상황 가정)을 기본값으로 하고 있는데, 이는 신중하고 보수적인 접근 방식입니다. **잘 하셨습니다.**

---

## 3. 리팩토링 계획 (Refactoring Plan)

### Phase 1: 클린 아키텍처 복원
1.  **의존성 주입(DI):** `Backtester`가 `__init__`에서 `ExecutionPort`를 주입받도록 리팩토링합니다. `backtester.py` 내부의 `SimpleExecutionAdapter` 임포트를 제거합니다.
2.  **프레젠터 분리:** `src/interface/console/backtest_presenter.py`를 생성합니다. `QuickBacktestFilter`에 있는 모든 `print` 및 `Logger` 포맷팅 로직을 이 프레젠터로 이동시킵니다.
3.  **인터페이스 분리:** `Strategy` 인터페이스를 깔끔하게 유지합니다. `prepare_indicators` 최적화 메서드는 모든 전략이 아닌 특정 전략 타입(`VectorizedStrategy` 등)의 구현 세부 사항이어야 합니다.

### Phase 2: 로직 중복 제거
1.  **지표 접근 추상화:** `RuleBasedBreakoutStrategy`를 위한 헬퍼나 믹스인을 생성하여 지표 접근 방식을 통일합니다.
    ```python
    def get_indicator(self, name: str, index: int, df: pd.DataFrame = None):
        if self._cached_indicators is not None:
             return self._cached_indicators.iloc[index][name]
        return calculate_indicator_on_fly(...)
    ```
2.  **필터 통합:** `QuickBacktestFilter`는 "레거시" 필터와 "가중치" 필터 로직을 모두 포함하고 있습니다. 이를 단일 `FilterEvaluationService`로 단순화합니다.

### Phase 3: 퀀트 기능 강화
1.  **견고성 체크:** 백테스터에 "전진 분석(Walk-Forward Analysis)" 또는 "몬테카를로 시뮬레이션(Monte Carlo Simulation)" 기능을 추가하여, 단일 실행 성과가 아닌 지표의 안정성을 검증할 수 있도록 합니다.
2.  **로깅 및 아티팩트:** `stdout`에 출력하는 대신, `Backtester`가 구조화된 아티팩트(JSON/HTML)를 생성하여 저장하고 나중에 볼 수 있도록 합니다(예: `reports/backtest_{timestamp}.html`).

## 4. 문서 업데이트
-   `docs/guide/BACKTESTING_GUIDE.md`를 업데이트하여 AI 로직 제거(이미 가이드에 언급됨) 및 새로운 아키텍처 구조를 반영합니다.
