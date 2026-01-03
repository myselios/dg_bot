# AI 판단 시스템 리팩토링 계획 (클린 아키텍처)

**작성일**: 2026-01-03
**관련 문서**: [04_ai_decision_volatility_breakout.md](./04_ai_decision_volatility_breakout.md)

---

## 1. 현재 상태 리뷰

### 1.1 문서의 핵심 제안

| 제안 | 설명 | 클린 아키텍처 매핑 |
|------|------|-------------------|
| AI 역할 축소 | 돌파 "허용/차단" 필터로 제한 | Domain Layer 책임 정의 |
| 입력 표준화 | raw OHLC ❌, 요약값만 제공 | DTO/Value Object 설계 |
| 결정 추적성 | prompt_version, model, params, PnL 라벨 DB 저장 | Infrastructure (Persistence) |
| 보안/안정성 | JSON validation, HOLD fallback, rate limit | Port 인터페이스 + Circuit Breaker |

### 1.2 현재 아키텍처 문제점

```
┌─────────────────────────────────────────────────────────────────┐
│  문제 1: God Object (AIService 1,301줄)                         │
│  - 데이터 준비 + 지표 계산 + 프롬프트 + API 호출 + 파싱         │
│  - Single Responsibility 원칙 위반                              │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  문제 2: 프롬프트 산재                                          │
│  - AIService.analyze() (950줄 프롬프트)                         │
│  - EntryAnalyzer.analyze_entry() (별도 프롬프트)                │
│  - PositionAnalyzer.analyze_exit() (별도 프롬프트)              │
│  → 일관성 관리 불가, 버전 관리 어려움                           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  문제 3: Port/Adapter 불완전                                    │
│  - AIPort 인터페이스 정의됨 (좋음)                              │
│  - OpenAIAdapter 구현 미흡 (실제 사용 안됨)                     │
│  - LegacyAIAdapter가 async인데 내부 sync 호출                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  문제 4: 결정 추적성 부재                                       │
│  - prompt_version 관리 없음                                     │
│  - AI 판단 + PnL 라벨링 연결 없음                               │
│  - 판단 근거 재현 불가                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 목표 아키텍처

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Presentation Layer                            │
│  TradingPipeline → HybridStage → AnalysisStage                       │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────────┐
│                         Application Layer                             │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  AnalyzeMarketUseCase                                            │ │
│  │  - 입력: AnalysisRequest (표준화된 DTO)                          │ │
│  │  - 출력: TradingDecision (ALLOW/BLOCK/HOLD)                     │ │
│  │  - 의존성: AIPort, PromptPort, ValidationPort                   │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  RecordDecisionUseCase                                           │ │
│  │  - 판단 기록: prompt_version, model, params, decision           │ │
│  │  - PnL 라벨 연결: 사후 수익률 기록                              │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  Ports (Outbound):                                                    │
│  ├── AIPort (기존)                                                   │
│  ├── PromptPort (신규) - 프롬프트 생성/버전 관리                    │
│  ├── ValidationPort (신규) - 결정 검증                              │
│  └── DecisionRecordPort (신규) - 판단 기록                          │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────────┐
│                        Infrastructure Layer                           │
│                                                                       │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────────┐  │
│  │ OpenAIAdapter    │  │ PromptAdapter    │  │ PostgresDecision   │  │
│  │ - rate limit     │  │ - YAML 템플릿    │  │   RecordAdapter    │  │
│  │ - circuit breaker│  │ - 버전 관리      │  │ - ai_decisions 테이블 │
│  │ - retry logic    │  │ - 검증 규칙      │  │ - pnl 라벨링       │  │
│  └──────────────────┘  └──────────────────┘  └────────────────────┘  │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ ValidationAdapter                                                │ │
│  │ - JSON schema validation                                        │ │
│  │ - 룰 기반 검증 (RSI 모순, 변동성 등)                            │ │
│  │ - HOLD fallback                                                  │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                          Domain Layer                                 │
│                                                                       │
│  Value Objects:                                                       │
│  ├── MarketSummary (regime, ATR, 돌파강도, 리스크예산)              │
│  ├── AIDecisionResult (ALLOW/BLOCK/HOLD + confidence + reason)      │
│  └── PromptVersion (id, version, checksum)                          │
│                                                                       │
│  Domain Services:                                                     │
│  ├── BreakoutFilter (돌파 허용/차단 판정 로직)                      │
│  └── DecisionValidator (AI 결정 검증)                               │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. 리팩토링 체크리스트

### Phase 1: 도메인 모델 정의 (기반 작업) ✅ 완료

| # | 항목 | 설명 | 파일 |
|---|------|------|------|
| 1.1 | [x] MarketSummary Value Object | raw OHLC 대신 요약값만 포함 (regime, ATR%, 돌파강도, 리스크예산) | `src/domain/value_objects/market_summary.py` |
| 1.2 | [x] AIDecisionResult Value Object | ALLOW/BLOCK/HOLD + confidence(0-100) + reason | `src/domain/value_objects/ai_decision_result.py` |
| 1.3 | [x] PromptVersion Value Object | id, version, template_hash | `src/domain/value_objects/prompt_version.py` |
| 1.4 | [x] BreakoutFilter Domain Service | 돌파 허용/차단 규칙 (AI 없이) | `src/domain/services/breakout_filter.py` |
| 1.5 | [x] 단위 테스트 작성 | 위 4개 컴포넌트 TDD (78개 테스트) | `tests/unit/domain/` |

### Phase 2: Port 인터페이스 정의 ✅ 완료

| # | 항목 | 설명 | 파일 |
|---|------|------|------|
| 2.1 | [x] PromptPort 인터페이스 | `get_prompt(type, version)`, `get_current_version()` | `src/application/ports/outbound/prompt_port.py` |
| 2.2 | [x] ValidationPort 인터페이스 | `validate_response(raw)`, `validate_decision(decision, context)` | `src/application/ports/outbound/validation_port.py` |
| 2.3 | [x] DecisionRecordPort 인터페이스 | `record(decision, prompt_version, params)`, `link_pnl(decision_id, pnl)` | `src/application/ports/outbound/decision_record_port.py` |
| 2.4 | [ ] AIPort 수정 | `analyze()` 반환 타입을 `AIDecisionResult`로 변경 | `src/application/ports/outbound/ai_port.py` |
| 2.5 | [x] 인터페이스 테스트 | Mock 기반 계약 테스트 (27개 테스트) | `tests/unit/application/ports/` |

### Phase 3: 프롬프트 분리 및 표준화 ✅ 완료

| # | 항목 | 설명 | 파일 |
|---|------|------|------|
| 3.1 | [x] 프롬프트 템플릿 YAML | entry/exit/general 분리, 버전 관리 | `src/infrastructure/prompts/` |
| 3.2 | [x] PromptAdapter 구현 | YAML 로드, 템플릿 렌더링, 버전 해시 | `src/infrastructure/adapters/prompt/yaml_prompt_adapter.py` |
| 3.3 | [x] 입력 표준화 | `MarketSummary` → 프롬프트 템플릿 매핑 | `src/infrastructure/adapters/prompt/` |
| 3.4 | [x] 기존 프롬프트 마이그레이션 | AIService 950줄 → YAML 템플릿 | `src/infrastructure/prompts/*.yaml` |
| 3.5 | [x] 프롬프트 단위 테스트 | 템플릿 렌더링 검증 (15개 테스트) | `tests/unit/infrastructure/adapters/prompt/` |

### Phase 4: AI 어댑터 강화 ✅ 완료

| # | 항목 | 설명 | 파일 |
|---|------|------|------|
| 4.1 | [x] JSON Schema Validation | 응답 스키마 검증, 실패 시 HOLD | `src/infrastructure/adapters/validation/validation_adapter.py` |
| 4.2 | [x] Rate Limiter | 호출 빈도 제한 (분당 N회), 슬라이딩 윈도우 | `src/infrastructure/adapters/ai/enhanced_openai_adapter.py` |
| 4.3 | [x] Circuit Breaker | 연속 실패 시 차단 (N회 실패 → M초 대기), CLOSED/OPEN/HALF_OPEN 상태 | `src/infrastructure/adapters/ai/enhanced_openai_adapter.py` |
| 4.4 | [x] Retry Logic | 재시도 로직 (exponential backoff) | `src/infrastructure/adapters/ai/enhanced_openai_adapter.py` |
| 4.5 | [x] Timeout 설정 | 요청 타임아웃 (기본 30초) | `src/infrastructure/adapters/ai/enhanced_openai_adapter.py` |
| 4.6 | [x] HOLD Fallback | 모든 에러 상황에서 HOLD 반환 | `src/infrastructure/adapters/ai/enhanced_openai_adapter.py` |
| 4.7 | [x] 어댑터 테스트 | Mock OpenAI 클라이언트로 테스트 (23개 테스트) | `tests/unit/infrastructure/adapters/ai/test_enhanced_openai_adapter.py` |

### Phase 5: 결정 추적성 ✅ 완료

| # | 항목 | 설명 | 파일 |
|---|------|------|------|
| 5.1 | [x] decision_records 테이블 스키마 | prompt_version, model, temperature, params, pnl 연결 | `backend/app/models/decision_record.py` |
| 5.2 | [x] DecisionRecordAdapter 구현 | DB 저장 어댑터, record/link_pnl/get_by_id/get_recent | `src/infrastructure/adapters/persistence/decision_record_adapter.py` |
| 5.3 | [x] PnL 라벨링 | decision_id + pnl_percent + is_profitable 연결 | `backend/app/models/decision_record.py` |
| 5.4 | [x] DecisionRecord 도메인 모델 | record → domain 변환, 조회용 | `src/application/ports/outbound/decision_record_port.py` |
| 5.5 | [x] 단위 테스트 | 어댑터 기능 검증 (15개 테스트) | `tests/unit/infrastructure/persistence/test_decision_record_adapter.py` |

### Phase 6: 검증 로직 통합 ✅ 완료

| # | 항목 | 설명 | 파일 |
|---|------|------|------|
| 6.1 | [x] ValidationAdapter 구현 | 응답 검증, 결정 검증, JSON 스키마 검증 | `src/infrastructure/adapters/validation/validation_adapter.py` |
| 6.2 | [x] 룰 기반 검증 통합 | RSI overbought/oversold 체크, MACD 경고, override to HOLD | `src/infrastructure/adapters/validation/validation_adapter.py` |
| 6.3 | [x] HOLD override 로직 | ALLOW + overbought RSI → 자동 HOLD 전환 | `src/infrastructure/adapters/validation/validation_adapter.py` |
| 6.4 | [x] 검증 테스트 | 응답 검증, 결정 검증, 스키마 검증 (18개 테스트) | `tests/unit/infrastructure/adapters/validation/test_validation_adapter.py` |

### Phase 7: UseCase 및 파이프라인 통합 ✅ 완료

| # | 항목 | 설명 | 파일 |
|---|------|------|------|
| 7.1 | [x] AnalyzeBreakoutUseCase 생성 | 새 Port들 통합 (Prompt, Validation, DecisionRecord, AIClient) | `src/application/use_cases/analyze_breakout.py` |
| 7.2 | [x] Request/Result DTO | BreakoutAnalysisRequest, BreakoutAnalysisResult | `src/application/use_cases/analyze_breakout.py` |
| 7.3 | [x] UseCase exports | `__init__.py`에 export 추가 | `src/application/use_cases/__init__.py` |
| 7.4 | [x] Override 로직 | 검증 실패 시 DecisionType override 적용 | `src/application/use_cases/analyze_breakout.py` |
| 7.5 | [x] UseCase 테스트 | 생성, 실행, 검증, 에러 처리 (10개 테스트) | `tests/unit/application/use_cases/test_analyze_breakout_use_case.py` |

### Phase 8: 레거시 정리 ✅ 완료

| # | 항목 | 설명 | 파일 |
|---|------|------|------|
| 8.1 | [x] 계획 문서 업데이트 | Phase 1-7 완료 상태 반영 | `docs/plans/PLAN_ai_refactoring_clean_architecture.md` |
| 8.2 | [x] 마이그레이션 가이드 작성 | 레거시 → 클린 아키텍처 전환 가이드 | `docs/guide/MIGRATION_AI_CLEAN_ARCHITECTURE.md` |
| 8.3 | [x] ARCHITECTURE.md 업데이트 | 새 컴포넌트 문서화 (v4.4.0) | `docs/guide/ARCHITECTURE.md` |
| 8.4 | [x] Container 통합 | 새 Port/Adapter를 Container에 등록 | `src/container.py` |
| 8.5 | [x] 레거시 코드 Deprecate 마킹 | AIService, EntryAnalyzer, PositionAnalyzer | `src/ai/` |

---

## 4. 설정값 단일 소스 (추가 필요)

```python
# src/config/settings.py

@dataclass
class AIConfig:
    """
    AI 설정값

    ⚠️ 변경 시 업데이트 필요:
    - src/infrastructure/adapters/ai/openai_adapter.py
    - docs/guide/ARCHITECTURE.md
    - docs/plans/PLAN_ai_refactoring_clean_architecture.md
    """
    MODEL: str = "gpt-4-turbo"
    TEMPERATURE: float = 0.2
    TIMEOUT_SECONDS: int = 30
    MAX_RETRIES: int = 3
    RATE_LIMIT_PER_MINUTE: int = 20
    CIRCUIT_BREAKER_THRESHOLD: int = 5
    CIRCUIT_BREAKER_TIMEOUT: int = 60

    # 프롬프트 버전
    PROMPT_VERSION: str = "v2.0.0"
```

---

## 5. 파일 구조 변경 요약

```
src/
├── domain/
│   ├── value_objects/
│   │   ├── market_summary.py          # 🆕
│   │   ├── ai_decision_result.py      # 🆕
│   │   └── prompt_version.py          # 🆕
│   └── services/
│       └── breakout_filter.py         # 🆕
│
├── application/
│   ├── ports/outbound/
│   │   ├── ai_port.py                 # 수정 (반환 타입 변경)
│   │   ├── prompt_port.py             # 🆕
│   │   ├── validation_port.py         # 🆕
│   │   └── decision_record_port.py    # 🆕
│   └── use_cases/
│       ├── analyze_market.py          # 수정
│       └── record_decision.py         # 🆕
│
├── infrastructure/
│   ├── adapters/
│   │   ├── ai/
│   │   │   ├── openai_adapter.py      # 수정 (rate limit, circuit breaker)
│   │   │   └── schema/                # 🆕 (JSON schema)
│   │   ├── prompt/
│   │   │   └── yaml_prompt_adapter.py # 🆕
│   │   ├── validation/
│   │   │   └── rule_validation_adapter.py  # 🆕
│   │   └── persistence/
│   │       └── decision_record_adapter.py  # 🆕
│   └── prompts/                       # 🆕
│       ├── entry.yaml
│       ├── exit.yaml
│       └── general.yaml
│
├── ai/
│   ├── service.py                     # 축소 (1301줄 → ~200줄)
│   ├── entry_analyzer.py              # Deprecated
│   ├── position_analyzer.py           # Deprecated
│   └── validator.py                   # → ValidationAdapter로 이동
│
└── config/
    └── settings.py                    # 수정 (AIConfig 확장)

backend/app/models/
└── ai_decision.py                     # 수정 (prompt_version, pnl_label 추가)

tests/
├── unit/
│   ├── domain/
│   │   ├── test_market_summary.py
│   │   ├── test_ai_decision_result.py
│   │   └── test_breakout_filter.py
│   ├── application/
│   │   └── ports/
│   │       ├── test_prompt_port.py
│   │       └── test_validation_port.py
│   └── infrastructure/
│       └── adapters/
│           ├── test_openai_adapter.py
│           ├── test_yaml_prompt_adapter.py
│           └── test_rule_validation_adapter.py
└── integration/
    └── test_analysis_pipeline.py
```

---

## 6. 구현 우선순위

### 🔴 High Priority (1주차)

1. **MarketSummary Value Object** - 입력 표준화의 기반
2. **PromptPort + YAML 템플릿** - 프롬프트 관리 중앙화
3. **JSON Schema Validation** - 안정성 확보

### 🟡 Medium Priority (2주차)

4. **AIDecisionResult Value Object** - AI 역할 축소 반영
5. **Rate Limiter + Circuit Breaker** - 안정성 강화
6. **DecisionRecordPort + 테이블 확장** - 추적성 확보

### 🟢 Low Priority (3주차 이후)

7. **ValidationAdapter** - 검증 로직 통합
8. **UseCase 수정 + 파이프라인 통합**
9. **레거시 정리**

---

## 7. 성공 기준

| 지표 | 목표 | 달성 |
|------|------|------|
| 프롬프트 버전 관리 | ✅ (YAML + checksum) | ✅ `YAMLPromptAdapter` + `PromptVersion` |
| AI 판단 + PnL 연결 | ✅ (DB 기록) | ✅ `DecisionRecordAdapter` + `link_pnl()` |
| JSON 응답 검증 | ✅ (schema validation) | ✅ `ValidationAdapter.validate_json_schema()` |
| HOLD fallback | ✅ (모든 에러) | ✅ `EnhancedOpenAIAdapter` 모든 에러 → HOLD |
| Rate Limit | ✅ (분당 20회) | ✅ `RateLimiter` 슬라이딩 윈도우 |
| Circuit Breaker | ✅ (5회 실패 → 60초 차단) | ✅ `CircuitBreaker` CLOSED/OPEN/HALF_OPEN |
| 단위 테스트 | ≥70개 | ✅ 643개 (Phase 1-7 완료 시점)

### 구현된 테스트 수 (Phase별)

| Phase | 테스트 수 | 설명 |
|-------|----------|------|
| Phase 1 | 78개 | 도메인 모델 (MarketSummary, AIDecisionResult, PromptVersion, BreakoutFilter) |
| Phase 2 | 27개 | Port 인터페이스 (PromptPort, ValidationPort, DecisionRecordPort) |
| Phase 3 | 15개 | YAMLPromptAdapter |
| Phase 4 | 23개 | EnhancedOpenAIAdapter (RateLimiter, CircuitBreaker) |
| Phase 5 | 15개 | DecisionRecordAdapter |
| Phase 6 | 18개 | ValidationAdapter |
| Phase 7 | 10개 | AnalyzeBreakoutUseCase |
| **합계** | **186개** | 새로 추가된 AI 리팩토링 관련 테스트 |

---

## 8. 핵심 원칙 (문서 결론 반영)

> **"AI는 변동성돌파의 엔진이 아니라 브레이크여야 한다."**

- AI = 돌파 **허용/차단 필터**
- 매수 가격/수량/스탑 = **규칙 기반**
- 상용 목적 = **"덜 똑똑하지만 일관된 AI"**

이 원칙을 코드로 구현:
1. `AIDecisionResult`는 `ALLOW/BLOCK/HOLD`만 반환
2. `BreakoutFilter` Domain Service가 규칙 기반 판단
3. AI는 최종 확인 단계에서만 사용
