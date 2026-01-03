# 백테스팅 로직 리뷰 보고서 (Backtest Quant Logic Review)

**작성일:** 2026-01-03
**검토자:** Quantitative Researcher (AI Agent)
**대상:** `src/backtesting/backtester.py`, `PerformanceAnalyzer`, `SlippageModel`

---

## 1. 개요 (Executive Summary)

현재 백테스팅 엔진은 **Look-Ahead Bias(미래 참조 편향)**를 방지하기 위한 장치(`execute_on_next_open`)와 현실적인 스탑로스 시뮬레이션(`use_intrabar_stops`)을 갖추고 있어 개인 레벨에서는 준수한 수준입니다.

그러나 **기관/상용 레벨** 기준으로는 **"Live 엔진과 Backtest 엔진의 이중 구현(Duplication)"**이라는 치명적인 결함이 존재합니다. 이는 백테스트 수익률과 실제 운용 수익률의 괴리(Sim-Real Gap)를 유발하는 가장 큰 원인입니다.

---

## 2. 상세 분석 (Deep Dive)

### 2.1 장점 (Strengths)

1.  **미래 참조 편향 방지 (Avoidance of Look-Ahead Bias)**
    *   `execute_on_next_open=True` 옵션을 기본값으로 하여, 시그널 발생(종가) 후 다음 봉 시가(Open)에 진입하는 현실적 로직을 구현했습니다. 이는 과적합된 승률을 방지하는 필수 요소입니다.

2.  **Intrabar Stop-Loss Simulation**
    *   일반적인 백테스터가 종가(Close) 기준으로만 손절을 체크하는 것과 달리, 봉 내부의 High/Low를 체크하여 장중 손절(`IntrabarExecutionAdapter`)을 구현했습니다. 이는 MDD(최대 낙폭)를 과소평가하는 흔한 실수를 막아줍니다.

3.  **슬리피지 통계 (Slippage Audit)**
    *   슬리피지 발생 내역을 별도로 기록(`slippage_statistics`)하여 사후 분석할 수 있게 한 점은 훌륭합니다.

---

### 2.2 단점 및 리스크 (Weaknesses & Risks)

1.  **Execution Logic Duplication (Critical)**
    *   **현상:** Live Bot은 `ExecuteTradeUseCase`를 통해 `ExchangePort`를 호출하지만, Backtester는 자체적인 `Portfolio` 클래스와 `_execute_order` 메서드를 사용합니다.
    *   **리스크:** Live 봇의 체결 로직(예: 재시도, 부분 체결 처리, 호가창 분석)이 수정되어도, 백테스터에는 자동으로 반영되지 않습니다. **"테스트한 대로 매매하지 않음(You don't trade what you test)"** 위반입니다.

2.  **단순화된 비용 모델 (Simplified Cost Model)**
    *   **현상:** `commission=0.0005`와 같이 고정 수수료만 적용합니다.
    *   **개선:** 실제 기관 트레이딩에서는 **Funding Fee(펀딩비)**, **Maker/Taker 구분**, **Market Implact**에 따른 가변 슬리피지 모델링이 필수적입니다.

3.  **Loop-Based Iteration의 한계**
    *   **현상:** `for i in range(total_bars)` 루프 방식은 이벤트 처리 지연(Latency)이나 비동기 동시성 문제를 시뮬레이션할 수 없습니다.

---

## 3. 리팩토링 및 개선 제안 (Recommendations)

### Phase 1: Engine Unification (엔진 통합)
*   백테스터가 `ExecuteTradeUseCase`를 그대로 호출하도록 변경하십시오.
*   이를 위해 `ExchangePort`의 Mock 구현체인 `BacktestExchangeAdapter`를 만들고, 여기에 과거 데이터를 주입(Feed)하는 방식으로 구조를 바꿔야 합니다.
    *   *Current:* `Backtester` -> `Portfolio` -> `Calculation`
    *   *Target:* `Backtester` -> `TradingOrchestrator` -> `ExecuteTradeUseCase` -> `BacktestExchangeAdapter`

### Phase 2: Enhanced Reporting
*   백테스트 결과 리포트에 다음 항목을 추가하십시오:
    *   **Sim-Real Gap Analysis:** 실제 매매 기록과 백테스트 기록을 겹쳐서 보여주는 차트.
    *   **Monte Carlo Simulation:** 파라미터를 미세하게 흔들었을 때 수익률이 얼마나 망가지는지(Robustness Test).

---

## 4. 상용화 가능성 분석 (Commercialization Feasibility)

*   **현재 상태:** **C+ (보완 필요)**
*   **퀀트 관점 평가:**
    *   현재 구조로는 투자자에게 "이 백테스트 결과가 실제 수익으로 이어질 것"이라고 확신을 주기 어렵습니다. 엔진이 다르기 때문입니다.
    *   상용 펀드/서비스 런칭을 위해서는 **Engine Unification**이 선행되어야 하며, 최소 3개월 이상의 Forward Testing(실전 검증) 데이터와 백테스트 데이터의 오차율(Tracking Error)이 5% 이내임이 증명되어야 합니다.
