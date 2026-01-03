# AI 로직 및 프롬프트 리뷰 (AI Logic & Prompt Review)

**작성일**: 2026-01-03
**작성자**: Quant Dev Agent (Antigravity)
**대상**: `src/ai` (Prompt Logic, Persona, Validators)

---

## 1. 총평 (Executive Summary)

**[평점: A+]**
대부분의 AI 트레이딩 봇이 저지르는 실수인 "AI에게 예측을 시키는 것"을 피하고, **"AI를 리스크 관리자(Risk Manager)로 활용"**하는 접근 방식이 매우 훌륭합니다. **"Risk Hunter"**라는 페르소나 설정과 **"BRAKE not ENGINE"**이라는 시스템 프롬프트의 지시는 이 시스템의 안정성을 보장하는 핵심입니다. 상용화 시 투자자들에게 가장 어필할 수 있는 "AI가 계좌를 지켜준다"는 내러티브를 완벽하게 기술적으로 구현했습니다.

---

## 2. 세부 분석 (Detailed Analysis)

### 2.1 프롬프트 엔지니어링 (entry.yaml)
- **장점 (Pros)**:
  - **페르소나 명확성**: "Risk Hunter", "Finding reasons NOT to trade"라는 지시는 LLM의 환각과 긍정 편향(Yes-Man bias)을 억제하는 데 매우 효과적입니다.
  - **구조화된 사고 (Chain of Thought)**: ALLOW/BLOCK/HOLD의 조건을 명시하고, JSON으로 `risk_factors`와 `key_metrics`를 뱉어내게 함으로써 AI가 '찍어서' 답하는 것을 방지하고 논리적인 추론을 강제하고 있습니다.
  - **파라미터화**: `max_atr_percent`, `min_volume_ratio` 등을 변수로 처리하여 프롬프트 수정 없이 민감도를 조절할 수 있게 템플릿화한 점은 유지보수성이 매우 높습니다.

- **보완점 (Points for Improvement)**:
  - **상관관계 컨텍스트 강화**: 현재 `Breaking News`나 `Macro Event` 같은 더 넓은 컨텍스트가 주입되는지 불분명합니다. 퀀트 투자자 입장에서 비트코인이 횡보하더라도 나스닥이 폭락 중이면 알트코인 매수를 멈춰야 합니다. 프롬프트의 `Risk Context` 섹션에 `Market Correlation`(나스닥, 달러인덱스 등) 정보를 명시적으로 추가하는 것을 권장합니다.

### 2.2 결정 검증 시스템 (Validation Logic)
- **장점 (Pros)**:
  - **Validator의 역할**: AI가 `ALLOW`를 외쳐도, `ValidationAdapter`가 RSI 과매수(Overbought) 등을 체크하여 `HOLD`로 강제 전환하는 구조는 **"이중 안전장치"**로서 매우 적절합니다. 이는 AI의 불확실성을 deterministic한 코드로 제어하는 모범 사례입니다.

### 2.3 Clean Architecture와의 시너지
- **장점 (Pros)**:
  - 프롬프트를 코드가 아닌 YAML로 분리하고 버전(`v2.0.0`) 관리함으로써, AI 모델(GPT-4 -> GPT-5) 변경이나 프롬프트 최적화 실험(A/B 테스트)이 용이합니다. 이는 상용 서비스 운영 시 다운타임 없는 로직 업데이트를 가능하게 합니다.

---

## 3. 리팩토링 및 개선 체크리스트 (Action Plan)

- [ ] **Negative Confirmation 강화**: 프롬프트의 `reason` 필드 외에 `rejection_reason`을 별도로 요구하여, AI가 왜 이 거래를 거절했는지(또는 거절할 뻔했는지)를 더 구체적으로 수집하십시오. 이는 추후 튜닝에 귀중한 데이터가 됩니다.
- [ ] **Macro Context 주입**: `entry.yaml`의 `Risk Context` 부분에 `major_index_trend` (예: Nasdaq 1H Trend) 항목을 추가하여 거시 경제적 리스크를 반영하십시오.
- [ ] **Self-Correction**: AI가 내린 결정이 `Validation` 단계에서 거절되었을 때, 그 피드백을 다시 AI에게 주어 "왜 틀렸는지" 학습(In-context Learning)하게 하는 루프를 고려해볼 수 있습니다 (고도화 단계).

---

## 4. 상용화 관점 제언

투자자들은 "AI가 돈을 벌어준다"는 말보다 **"AI가 내가 잘 때 손실을 막아주었다"**는 로그에 더 열광합니다.
시스템 UI/UX 상에서, AI가 `BLOCK`한 거래들에 대해 **"AI가 감지한 리스크: 과도한 변동성, 비트코인 하락 동조화"** 와 같이 구체적인 차단 사유를 보여주는 대시보드를 반드시 포함하십시오. 이것이 이 시스템의 핵심 세일즈 포인트(USP)가 될 것입니다.
