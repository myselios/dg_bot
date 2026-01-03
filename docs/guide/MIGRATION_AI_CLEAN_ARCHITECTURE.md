# AI 시스템 클린 아키텍처 마이그레이션 가이드

**작성일**: 2026-01-03
**관련 계획**: [PLAN_ai_refactoring_clean_architecture.md](../plans/PLAN_ai_refactoring_clean_architecture.md)

---

## 1. 개요

이 문서는 레거시 AI 시스템에서 클린 아키텍처 기반 시스템으로 마이그레이션하는 방법을 설명합니다.

### 1.1 마이그레이션 목표

| 레거시 | 클린 아키텍처 |
|--------|--------------|
| `AIService.analyze()` (1,301줄) | `AnalyzeBreakoutUseCase` + Ports |
| 프롬프트 하드코딩 | YAML 템플릿 (`YAMLPromptAdapter`) |
| 판단 추적 없음 | `DecisionRecordAdapter` + DB 저장 |
| 검증 산재 | `ValidationAdapter` 중앙화 |
| Rate limit 없음 | `RateLimiter` + `CircuitBreaker` |

### 1.2 아키텍처 비교

```
레거시:
┌─────────────────────────────────────────────┐
│  AnalysisStage                              │
│  └─ AIService.analyze()                     │
│     ├─ 데이터 준비 (프롬프트 내)            │
│     ├─ OpenAI 호출 (직접)                   │
│     ├─ 응답 파싱 (내장)                     │
│     └─ 검증 (부분적)                        │
└─────────────────────────────────────────────┘

클린 아키텍처:
┌─────────────────────────────────────────────┐
│  AnalysisStage                              │
│  └─ AnalyzeBreakoutUseCase.execute()        │
│     ├─ PromptPort.render_prompt()           │
│     ├─ AIClient.analyze()                   │
│     ├─ ValidationPort.validate_response()   │
│     ├─ ValidationPort.validate_decision()   │
│     └─ DecisionRecordPort.record()          │
└─────────────────────────────────────────────┘
```

---

## 2. 새 컴포넌트 소개

### 2.1 Domain Layer

#### Value Objects

| 클래스 | 설명 | 위치 |
|--------|------|------|
| `MarketSummary` | 시장 요약 (regime, ATR%, 돌파강도) | `src/domain/value_objects/market_summary.py` |
| `AIDecisionResult` | AI 판단 결과 (ALLOW/BLOCK/HOLD) | `src/domain/value_objects/ai_decision_result.py` |
| `PromptVersion` | 프롬프트 버전 (version, hash) | `src/domain/value_objects/prompt_version.py` |

```python
from src.domain.value_objects import (
    MarketSummary, MarketRegime, BreakoutStrength,
    AIDecisionResult, DecisionType,
    PromptVersion, PromptType,
)

# MarketSummary 생성
summary = MarketSummary(
    ticker="KRW-BTC",
    regime=MarketRegime.TRENDING_UP,
    atr_percent=Decimal("2.5"),
    breakout_strength=BreakoutStrength.STRONG,
    risk_budget=Decimal("0.02"),
)

# AIDecisionResult 생성
decision = AIDecisionResult.allow(
    ticker="KRW-BTC",
    confidence=85,
    reason="Strong breakout confirmed",
)

# PromptVersion 조회
version = PromptVersion.current(PromptType.ENTRY)
```

### 2.2 Application Layer

#### Ports (인터페이스)

| Port | 역할 | 메서드 |
|------|------|--------|
| `PromptPort` | 프롬프트 생성/관리 | `get_current_version()`, `render_prompt()` |
| `ValidationPort` | 응답/판단 검증 | `validate_response()`, `validate_decision()` |
| `DecisionRecordPort` | 판단 기록 | `record()`, `link_pnl()`, `get_by_id()` |

#### UseCase

```python
from src.application.use_cases import (
    AnalyzeBreakoutUseCase,
    BreakoutAnalysisRequest,
    BreakoutAnalysisResult,
)

# UseCase 생성 (의존성 주입)
use_case = AnalyzeBreakoutUseCase(
    prompt_port=yaml_prompt_adapter,
    validation_port=validation_adapter,
    decision_record_port=decision_record_adapter,
    ai_client=enhanced_openai_adapter,
)

# 분석 실행
request = BreakoutAnalysisRequest(
    ticker="KRW-BTC",
    current_price=Decimal("50000000"),
    market_summary=summary,
    additional_context={"rsi": 65, "macd_histogram": 0.5},
)

result = await use_case.execute(request)
# result.decision.decision -> DecisionType.ALLOW
# result.record_id -> "abc123" (DB record ID)
# result.validation_passed -> True
```

### 2.3 Infrastructure Layer

#### Adapters

| Adapter | Port 구현 | 기능 |
|---------|----------|------|
| `YAMLPromptAdapter` | `PromptPort` | YAML 템플릿 로드, 렌더링, 해시 계산 |
| `ValidationAdapter` | `ValidationPort` | 응답 형식 검증, RSI/MACD 검증, HOLD override |
| `DecisionRecordAdapter` | `DecisionRecordPort` | PostgreSQL 저장, PnL 연결 |
| `EnhancedOpenAIAdapter` | `AIClient` | Rate limit, Circuit breaker, Retry |

```python
from src.infrastructure.adapters.prompt import YAMLPromptAdapter
from src.infrastructure.adapters.validation import ValidationAdapter
from src.infrastructure.adapters.persistence import DecisionRecordAdapter
from src.infrastructure.adapters.ai import EnhancedOpenAIAdapter

# Adapter 생성
prompt_adapter = YAMLPromptAdapter(prompts_dir="src/infrastructure/prompts")
validation_adapter = ValidationAdapter(
    rsi_overbought_threshold=75.0,
    rsi_oversold_threshold=30.0,
)
decision_adapter = DecisionRecordAdapter(db_session_factory)
ai_adapter = EnhancedOpenAIAdapter(
    api_key="...",
    rate_limit_per_minute=20,
    circuit_breaker_threshold=5,
)
```

---

## 3. 마이그레이션 단계

### 3.1 단계 1: 새 어댑터 생성

기존 코드를 수정하지 않고 새 어댑터들을 먼저 생성합니다.

```python
# src/container.py 또는 별도 factory

def create_ai_analysis_use_case(db_session_factory, prompts_dir: str) -> AnalyzeBreakoutUseCase:
    """새 클린 아키텍처 UseCase 생성."""
    return AnalyzeBreakoutUseCase(
        prompt_port=YAMLPromptAdapter(prompts_dir),
        validation_port=ValidationAdapter(),
        decision_record_port=DecisionRecordAdapter(db_session_factory),
        ai_client=EnhancedOpenAIAdapter(api_key=settings.OPENAI_API_KEY),
    )
```

### 3.2 단계 2: 점진적 전환 (Feature Flag)

기존 시스템과 새 시스템을 병행 운영합니다.

```python
# src/config/settings.py
USE_CLEAN_ARCHITECTURE_AI = os.getenv("USE_CLEAN_ARCHITECTURE_AI", "false").lower() == "true"

# src/trading/pipeline/analysis_stage.py
class AnalysisStage:
    async def execute(self, context: PipelineContext) -> StageResult:
        if settings.USE_CLEAN_ARCHITECTURE_AI:
            return await self._execute_clean_architecture(context)
        else:
            return await self._execute_legacy(context)

    async def _execute_clean_architecture(self, context: PipelineContext) -> StageResult:
        use_case = container.get_analyze_breakout_use_case()
        request = self._build_request(context)
        result = await use_case.execute(request)
        return self._convert_to_stage_result(result)

    async def _execute_legacy(self, context: PipelineContext) -> StageResult:
        # 기존 AIService 사용
        ...
```

### 3.3 단계 3: 테스트 및 검증

```bash
# 1. 새 컴포넌트 단위 테스트
python -m pytest tests/unit/application/use_cases/test_analyze_breakout_use_case.py -v

# 2. 어댑터 테스트
python -m pytest tests/unit/infrastructure/adapters/ -v

# 3. Feature flag 활성화 후 통합 테스트
USE_CLEAN_ARCHITECTURE_AI=true python -m pytest tests/integration/ -v
```

### 3.4 단계 4: 레거시 제거

모든 테스트가 통과하고 프로덕션에서 안정적으로 동작하면:

1. Feature flag 제거
2. 레거시 코드에 `@deprecated` 마킹
3. 추후 버전에서 레거시 코드 삭제

---

## 4. API 변경 사항

### 4.1 입력 변경

```python
# Before (레거시)
result = ai_service.analyze(
    ticker="KRW-BTC",
    df=ohlcv_dataframe,      # raw OHLC 데이터 전달
    indicators=indicator_dict,
    signal_info=signal_info,
)

# After (클린 아키텍처)
request = BreakoutAnalysisRequest(
    ticker="KRW-BTC",
    current_price=Decimal("50000000"),
    market_summary=MarketSummary(     # 요약 정보만 전달
        ticker="KRW-BTC",
        regime=MarketRegime.TRENDING_UP,
        atr_percent=Decimal("2.5"),
        breakout_strength=BreakoutStrength.MODERATE,
        risk_budget=Decimal("0.02"),
    ),
    additional_context={"rsi": 65},   # 필요한 지표만
)
result = await use_case.execute(request)
```

### 4.2 출력 변경

```python
# Before (레거시)
result = {
    "decision": "buy",     # 문자열
    "confidence": 85,
    "reason": "...",
    # 구조화되지 않음
}

# After (클린 아키텍처)
result = BreakoutAnalysisResult(
    decision=AIDecisionResult(
        decision=DecisionType.ALLOW,   # Enum
        confidence=Confidence(85),      # Value Object
        reason="...",
        ticker="KRW-BTC",
    ),
    record_id="abc123",                # DB 추적 가능
    prompt_version=PromptVersion(...), # 프롬프트 버전 추적
    validation_passed=True,
    is_override=False,
)
```

### 4.3 DecisionType 매핑

| 레거시 | 클린 아키텍처 | 설명 |
|--------|--------------|------|
| `"buy"` | `DecisionType.ALLOW` | 진입 허용 |
| `"sell"` | `DecisionType.BLOCK` | 진입 차단 (또는 청산) |
| `"hold"` / `"wait"` | `DecisionType.HOLD` | 대기 |

---

## 5. 프롬프트 마이그레이션

### 5.1 YAML 템플릿 구조

```yaml
# src/infrastructure/prompts/entry.yaml
name: entry_decision
version: "2.0.0"
description: "돌파 진입 허용/차단 판단"

template: |
  당신은 암호화폐 트레이딩 AI입니다.

  ## 시장 상황
  - 티커: {{ ticker }}
  - 현재가: {{ current_price }}
  - 시장 상태: {{ market_regime }}
  - ATR%: {{ atr_percent }}

  ## 결정
  돌파 진입을 허용할지 판단하세요.
  응답은 JSON 형식으로:
  {
    "decision": "allow" | "block" | "hold",
    "confidence": 0-100,
    "reason": "판단 근거"
  }

variables:
  - ticker
  - current_price
  - market_regime
  - atr_percent
```

### 5.2 렌더링

```python
prompt_adapter = YAMLPromptAdapter()

# 프롬프트 렌더링
prompt = await prompt_adapter.render_prompt(
    prompt_type=PromptType.ENTRY,
    context={
        "ticker": "KRW-BTC",
        "current_price": "50000000",
        "market_regime": "trending_up",
        "atr_percent": "2.5",
    },
)

# 버전 조회
version = await prompt_adapter.get_current_version(PromptType.ENTRY)
# version.version -> "2.0.0"
# version.template_hash -> "a1b2c3..."
```

---

## 6. 검증 로직

### 6.1 응답 검증

```python
validation_adapter = ValidationAdapter()

# AI 응답 검증
result = await validation_adapter.validate_response({
    "decision": "allow",
    "confidence": 85,
    "reason": "Strong momentum",
})
# result.valid -> True

# 잘못된 응답
result = await validation_adapter.validate_response({
    "decision": "maybe",  # 잘못된 값
    "confidence": 150,    # 범위 초과
})
# result.valid -> False
# result.message -> "Invalid decision value..."
```

### 6.2 결정 검증 (시장 컨텍스트)

```python
decision = AIDecisionResult.allow(ticker="KRW-BTC", confidence=85, reason="...")

# RSI가 너무 높은 경우
result = await validation_adapter.validate_decision(
    decision,
    market_context={"rsi": 80},  # overbought
)
# result.valid -> False
# result.override_decision -> DecisionType.HOLD
# result.message -> "ALLOW with overbought RSI (80) - override to HOLD"
```

---

## 7. 결정 추적성

### 7.1 판단 기록

```python
decision_adapter = DecisionRecordAdapter(session_factory)

# 판단 기록
record_id = await decision_adapter.record(
    decision=decision,
    prompt_version=prompt_version,
    params={"model": "gpt-4", "temperature": 0.2},
)

# 조회
record = await decision_adapter.get_by_id(record_id)
```

### 7.2 PnL 연결

```python
# 거래 완료 후 PnL 연결
await decision_adapter.link_pnl(
    decision_id=record_id,
    pnl_percent=Decimal("3.5"),
    exit_reason="take_profit",
)

# 이제 record.is_profitable = True, record.pnl_percent = 3.5
```

---

## 8. Rate Limiting & Circuit Breaker

### 8.1 Rate Limiter

```python
from src.infrastructure.adapters.ai import RateLimiter

limiter = RateLimiter(max_calls=20, period_seconds=60.0)

if limiter.acquire():
    # API 호출 가능
    ...
else:
    # 제한 초과 - HOLD 반환
    ...
```

### 8.2 Circuit Breaker

```python
from src.infrastructure.adapters.ai import CircuitBreaker, CircuitState

breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60.0,
)

# 상태 확인
if breaker.allow_request():
    try:
        result = await call_api()
        breaker.record_success()
    except Exception:
        breaker.record_failure()
        # 5회 연속 실패 시 OPEN 상태로 전환
else:
    # Circuit OPEN - HOLD 반환
    ...

# 상태 조회
state = breaker.state  # CircuitState.CLOSED / OPEN / HALF_OPEN
```

---

## 9. 테스트 작성 가이드

### 9.1 UseCase 테스트 (Mock 사용)

```python
@pytest.fixture
def mock_ports():
    return {
        "prompt_port": AsyncMock(spec=PromptPort),
        "validation_port": AsyncMock(spec=ValidationPort),
        "decision_record_port": AsyncMock(spec=DecisionRecordPort),
        "ai_client": AsyncMock(),
    }

@pytest.mark.asyncio
async def test_execute_returns_allow(mock_ports):
    """AI가 ALLOW 반환 시 정상 처리."""
    mock_ports["ai_client"].analyze.return_value = {
        "decision": "allow",
        "confidence": 90,
        "reason": "Perfect setup",
    }
    mock_ports["validation_port"].validate_response.return_value = ValidationResult(valid=True)
    mock_ports["validation_port"].validate_decision.return_value = ValidationResult(valid=True)

    use_case = AnalyzeBreakoutUseCase(**mock_ports)
    result = await use_case.execute(sample_request)

    assert result.decision.decision == DecisionType.ALLOW
```

---

## 10. 체크리스트

### 마이그레이션 전

- [ ] 모든 단위 테스트 통과 확인
- [ ] 새 컴포넌트 코드 리뷰 완료
- [ ] DB 마이그레이션 준비 (decision_records 테이블)
- [ ] 환경 변수 설정 (`USE_CLEAN_ARCHITECTURE_AI`)

### 마이그레이션 중

- [ ] Feature flag 활성화
- [ ] 로그 모니터링 (에러, 성능)
- [ ] 판단 결과 비교 (레거시 vs 신규)
- [ ] Rate limit / Circuit breaker 동작 확인

### 마이그레이션 후

- [ ] Feature flag 제거
- [ ] 레거시 코드 deprecation 마킹
- [ ] 문서 업데이트 (ARCHITECTURE.md, CLAUDE.md)
- [ ] 모니터링 대시보드 업데이트

---

## 11. 문제 해결

### Q: AI 호출이 모두 HOLD로 반환됩니다

**A**: Circuit breaker가 OPEN 상태일 수 있습니다.
```python
# 상태 확인
print(ai_adapter.circuit_breaker.state)

# 수동 리셋 (테스트용)
ai_adapter.circuit_breaker._state = CircuitState.CLOSED
ai_adapter.circuit_breaker.failure_count = 0
```

### Q: 프롬프트 버전이 변경되지 않습니다

**A**: YAML 파일의 `version` 필드를 업데이트하세요.
```yaml
# src/infrastructure/prompts/entry.yaml
version: "2.1.0"  # 버전 증가
```

### Q: DB에 기록이 저장되지 않습니다

**A**: `decision_records` 테이블이 생성되었는지 확인하세요.
```sql
SELECT * FROM decision_records LIMIT 1;
```

---

## 관련 문서

- [아키텍처 가이드](./ARCHITECTURE.md)
- [리팩토링 계획](../plans/PLAN_ai_refactoring_clean_architecture.md)
- [스케줄러 가이드](./SCHEDULER_GUIDE.md)
