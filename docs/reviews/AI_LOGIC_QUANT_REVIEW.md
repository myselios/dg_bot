# AI 로직 및 프롬프트 리뷰 보고서 (AI Logic Quant Review)

**작성일:** 2026-01-03
**검토자:** Quantitative Analyst (AI Agent)
**대상:** `src/ai/entry_analyzer.py`, `src/infrastructure/prompts/entry.yaml`, `OpenAIAdapter`

---

## 1. 개요 (Executive Summary)

현재 AI 로직은 단순한 예측이 아닌 **"Risk Hunter(리스크 감시자)"** 페르소나를 부여하여 보수적인 진입 결정을 유도하도록 설계된 점이 매우 인상적입니다. 또한, 프롬프트를 YAML로 분리하고 버전을 관리하는 체계(`v2.0.0`)는 MLOps 관점에서 훌륭한 접근입니다.

그러나 **Legacy Code (`entry_analyzer.py`)**가 여전히 메인 로직처럼 남아있어 구조적 혼란을 주며, AI 판단의 **재현성(Reproducibility)**과 **결정론적(Deterministic)** 특성이 부족하여 상용 운용 시 불확실성을 초래할 수 있습니다.

---

## 2. 상세 분석 (Deep Dive)

### 2.1 장점 (Strengths)

1.  **Risk Hunter Persona**
    *   **내용:** "You are a Risk Hunter... act as a BRAKE, not an ENGINE." (`entry.yaml`)
    *   **평가:** AI에게 "돈을 벌어라"라고 하면 환각(Hallucination)을 보이며 무리한 진입을 권장하기 쉽습니다. 반대로 "막을 이유를 찾아라"라고 지시한 것은 퀀트 관점에서 매우 현명한 프롬프트 엔지니어링입니다.

2.  **Explicit Protocol (JSON Output)**
    *   **내용:** 응답 포맷을 엄격한 JSON으로 강제하고, `decision`, `confidence`, `risk_factors` 등 필수 필드를 정의했습니다.
    *   **평가:** 비정형 텍스트를 정형 데이터로 변환하여 시스템이 후처리(Post-processing)할 수 있게 만든 점은 자동화 시스템의 기본을 잘 지켰습니다.

3.  **Prompt Separation & Configuration**
    *   프롬프트를 코드와 분리하여 YAML로 관리함으로써, 코드 배포 없이도 AI의 '성격'을 튜닝할 수 있는 유연성을 확보했습니다.

---

### 2.2 단점 및 리스크 (Weaknesses & Risks)

1.  **Legacy Module Risk**
    *   **현상:** `src/ai/entry_analyzer.py`에는 프롬프트 구성 로직과 OpenAI 호출 로직이 혼재되어 있습니다. 반면 새로운 Clean Architecture 구조는 `AnalyzeBreakoutUseCase`와 `PromptPort`를 사용합니다.
    *   **리스크:** 유지보수자가 `entry_analyzer.py`를 수정하면서 시스템이 개선되었다고 착각할 수 있습니다. (Dead Code가 살아있는 좀비 코드가 될 위험)

2.  **정량적 근거의 부족 (Heuristic Scoring)**
    *   **현상:** `_calculate_entry_score` 메서드에서 `score += 15`, `score -= 20` 등 마법의 숫자(Magic Numbers)가 사용됩니다.
    *   **리스크:** 이 점수 체계는 통계적 근거가 없으므로 시장 상황이 바뀌면 무용지물이 될 수 있습니다. 65점과 70점의 차이가 실질적인 수익률 차이(Edge)를 의미하는지 검증되지 않았습니다.

3.  **Third-Party Dependency & Latency**
    *   **현상:** 매 봉 마감(Candle Close) 직후 OpenAI API를 호출해야 합니다. 응답이 3초 이상 지연되거나 503 에러가 발생하면?
    *   **리스크:** "좋은 자리"를 놓치거나, 타임아웃 처리 로직 미비로 인해 프로세스가 블로킹(Blocking)될 수 있습니다.

---

## 3. 리팩토링 및 개선 제안 (Recommendations)

### Phase 1: Code Cleanup
*   `src/ai/entry_analyzer.py`를 과감히 삭제하거나 `deprecated` 폴더로 이동시키고, `AnalyzeBreakoutUseCase`로 로직을 완전히 이관하십시오.

### Phase 2: Hybrid Decision Model
*   AI 점수(`score`)를 단독 진입 결정 요인으로 쓰지 마십시오.
*   **Hard Rule(필수 조건) + AI Veto(거부권)** 구조로 가야 합니다.
    *   *Rule:* RSI < 70, 거래량 > 200% (Pass)
    *   *AI:* "뉴스 악재가 있어 보입니다. 진입 금지." (Veto)
    *   AI는 오직 "진입을 막는 역할"에만 집중시켜 그 효용을 극대화하십시오.

### Phase 3: Fail-over Policy
*   AI API 호출 실패 시의 기본 행동(Default Behavior)을 정의하십시오. (권장: `BLOCK` / 무조건 진입 포기). 안전이 최우선입니다.

---

## 4. 상용화 가능성 분석 (Commercialization Feasibility)

*   **현재 상태:** **B (비용/속도 이슈)**
*   **상용화 리스크:**
    *   **비용(Cost):** 모든 종목/모든 캔들마다 GPT-4를 호출하면 API 비용이 알파(초과수익)를 잠식할 수 있습니다. 1차 필터(Rule-based)를 통과한 상위 5% 종목에 대해서만 AI를 호출하는 **"Funnel 구조"**가 필수입니다.
    *   **속도(Latency):** 1분봉이나 5분봉 등 짧은 타임프레임에서는 AI 호출 지연이 치명적입니다. 최소 15분봉 이상, 권장 1시간봉 이상의 전략에만 적합합니다.
*   **결론:** AI를 "알파 생성기"가 아닌 "리스크 매니저"로 사용하는 현재 방향성은 상용화에 적합하나, 호출 빈도 최적화(Cost Efficiency)가 선행되어야 합니다.
