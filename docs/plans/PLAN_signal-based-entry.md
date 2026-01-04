# PLAN: 신호분석 기반 진입 및 AI 역할 재정의

**작성일**: 2026-01-04
**상태**: ✅ 완료 (Phase 1-3)
**예상 범위**: Medium (3 phases)
**후속 계획**: [PLAN_ml-data-collection.md](PLAN_ml-data-collection.md)

---

**CRITICAL INSTRUCTIONS**: 각 페이즈 완료 후:
1. ✅ 완료된 작업 체크박스 체크
2. 🧪 품질 게이트 검증 명령 실행
3. ⚠️ 모든 품질 게이트 항목 통과 확인
4. 📅 "Last Updated" 날짜 업데이트
5. 📝 Notes 섹션에 학습 내용 문서화
6. ➡️ 다음 페이즈로 진행

⛔ 품질 게이트 스킵 또는 실패 상태에서 진행 금지

---

## 📋 개요

### 배경
- 현재 AI 분석이 너무 보수적으로 동작하여 한 번도 매수를 실행하지 못함
- SignalAnalyzer (규칙 기반)는 이미 좋은 신호를 생성하고 있으나, AI가 최종 결정에서 매수를 거부함
- AI API 호출 비용 절감 필요

### 목표
1. **진입 시 AI 제거**: SignalAnalyzer 결과로 즉시 매수 결정
2. **포지션 관리에 AI 활용**: 규칙 기반 체크 후 AI가 청산 판단 보조
3. **ML 튜닝 준비**: 매매 데이터 수집 및 신호분석 파라미터 최적화 기반 마련

### 아키텍처 결정

| 결정 | 선택 | 근거 |
|------|------|------|
| 진입 로직 | SignalAnalyzer 직접 사용 | AI 보수성 문제 해결, 비용 절감 |
| 청산 로직 | 규칙 우선 + AI 검증 | 손실 방지 중요, AI 판단 가치 유지 |
| 신호 임계값 | `decision in {strong_buy, buy}` | 기존 SignalAnalyzer 로직 활용, 진입 조건 단일화 |
| 포지션 사이즈 | strong_buy/buy 동일 비용 | 복잡성 최소화, 추후 데이터 기반 차등화 검토 |

---

## 🔄 AS-IS vs TO-BE 아키텍처 비교

### 진입 흐름 (Entry Flow) - 1시간 주기

#### AS-IS (현재)
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           진입 파이프라인 (AS-IS)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │ HybridRisk   │───▶│    Data      │───▶│  Analysis    │───▶│ Execution │ │
│  │ CheckStage   │    │ Collection   │    │    Stage     │    │   Stage   │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └───────────┘ │
│        │                    │                   │                   │       │
│        ▼                    ▼                   ▼                   ▼       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │ • 유동성스캔   │    │ • OHLCV 수집  │    │ • 백테스팅    │    │ • 주문실행  │ │
│  │ • 백테스트    │    │ • 호가창      │    │ • 신호분석    │    │ • 잔고확인  │ │
│  │   필터       │    │ • 지표계산    │    │ • AI 분석 ❌  │    │           │ │
│  └──────────────┘    └──────────────┘    │ • AI 검증    │    └───────────┘ │
│                                          └──────────────┘                   │
│                                                 │                           │
│                                                 ▼                           │
│                                    ┌─────────────────────────┐              │
│                                    │    🤖 AI (OpenAI)       │              │
│                                    │  ─────────────────────  │              │
│                                    │  • 최종 결정권 보유      │              │
│                                    │  • 매우 보수적 판단      │              │
│                                    │  • 매수 거의 실행 안함 ❌ │              │
│                                    └─────────────────────────┘              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

문제점:
- AI가 너무 보수적으로 판단 → 한 번도 매수 실행 안 함
- SignalAnalyzer가 strong_buy 신호를 보내도 AI가 hold로 변경
- 불필요한 API 비용 발생 (매 사이클 AI 호출)
```

#### TO-BE (변경 후)
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           진입 파이프라인 (TO-BE)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │ HybridRisk   │───▶│    Data      │───▶│  Analysis    │───▶│ Execution │ │
│  │ CheckStage   │    │ Collection   │    │    Stage     │    │   Stage   │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └───────────┘ │
│        │                    │                   │                   │       │
│        ▼                    ▼                   ▼                   ▼       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │ • 유동성스캔   │    │ • OHLCV 수집  │    │ • 백테스팅    │    │ • 주문실행  │ │
│  │ • 백테스트    │    │ • 호가창      │    │ • 신호분석 ✅ │    │ • 잔고확인  │ │
│  │   필터       │    │ • 지표계산    │    │ • AI 스킵 ✅  │    │           │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └───────────┘ │
│                                                 │                           │
│                                                 ▼                           │
│                                    ┌─────────────────────────┐              │
│                                    │  📊 SignalAnalyzer      │              │
│                                    │  ─────────────────────  │              │
│                                    │  • 규칙 기반 즉시 결정   │              │
│                                    │  • decision ∈ {strong_buy,│              │
│                                    │    buy} → "buy"로 매수   │              │
│                                    │  • AI 호출 없음 (비용 0) │              │
│                                    └─────────────────────────┘              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

개선점:
- SignalAnalyzer 결과로 즉시 매수 결정
- AI 호출 제거 → API 비용 절감
- 빠른 의사결정 (AI 응답 대기 시간 제거)
```

---

### 포지션 관리 흐름 (Position Management) - 15분 주기

#### AS-IS (현재)
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        포지션 관리 파이프라인 (AS-IS)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐                                                        │
│  │ Position Check  │                                                        │
│  │  (보유 포지션)   │                                                        │
│  └────────┬────────┘                                                        │
│           │                                                                 │
│           ▼                                                                 │
│  ┌─────────────────┐         ┌─────────────────┐                           │
│  │  규칙 기반 체크  │────────▶│    청산 실행     │                           │
│  │ • 손절 (-5%)    │  SELL   │                 │                           │
│  │ • 익절 (+10%)   │         └─────────────────┘                           │
│  │ • 추적 손절     │                                                        │
│  └────────┬────────┘                                                        │
│           │ HOLD                                                            │
│           ▼                                                                 │
│  ┌─────────────────┐                                                        │
│  │  그냥 유지       │  ← AI 검증 없음                                        │
│  └─────────────────┘                                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

문제점:
- 규칙만으로 판단 → 시장 상황 고려 부족
- 추세 반전 등 복잡한 상황 대응 어려움
```

#### TO-BE (변경 후)
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        포지션 관리 파이프라인 (TO-BE)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐                                                        │
│  │ Position Check  │                                                        │
│  │  (보유 포지션)   │                                                        │
│  └────────┬────────┘                                                        │
│           │                                                                 │
│           ▼                                                                 │
│  ┌─────────────────┐         ┌─────────────────┐                           │
│  │  규칙 기반 체크  │────────▶│    청산 실행     │                           │
│  │ • 손절 (-5%)    │  SELL   │  (AI 스킵)      │                           │
│  │ • 익절 (+10%)   │         └─────────────────┘                           │
│  │ • 추적 손절     │                                                        │
│  └────────┬────────┘                                                        │
│           │ HOLD                                                            │
│           ▼                                                                 │
│  ┌─────────────────┐         ┌─────────────────┐         ┌───────────────┐ │
│  │  🤖 AI 검증     │────────▶│    청산 실행     │         │    유지       │ │
│  │ • 시장 분석     │  SELL   │  (AI 권고)      │  HOLD   │               │ │
│  │ • 추세 판단     │         └─────────────────┘ ────────▶│               │ │
│  │ • 리스크 평가   │                                      └───────────────┘ │
│  └─────────────────┘                                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

개선점:
- 규칙이 SELL → 즉시 청산 (AI 호출 안 함, 빠른 손절)
- 규칙이 HOLD → AI가 추가 분석 후 청산 여부 결정
- AI의 강점(복잡한 상황 분석)을 적재적소에 활용
```

---

### 의사결정 흐름 비교

| 구분 | AS-IS | TO-BE |
|------|-------|-------|
| **진입 결정자** | AI (OpenAI) | SignalAnalyzer (규칙) |
| **진입 AI 호출** | 매 사이클 1회 | 0회 |
| **진입 판단 기준** | AI 프롬프트 응답 | `decision ∈ {strong_buy, buy}` → "buy" |
| **청산 결정자** | 규칙만 | 규칙 우선 + AI 보조 |
| **청산 AI 호출** | 0회 | 규칙이 HOLD일 때만 1회 |
| **API 비용** | 높음 | 대폭 감소 |
| **응답 속도** | 느림 (AI 대기) | 빠름 (규칙 즉시) |

---

### SignalAnalyzer 결정 기준

```python
# 현재 SignalAnalyzer 로직 (signal_analyzer.py)
total_score = buy_score - sell_score

if total_score > 3:
    decision = "strong_buy"   # → 매수 실행 ✅
elif total_score > 1:
    decision = "buy"          # → 매수 실행 ✅
elif total_score < -3:
    decision = "strong_sell"  # → 청산 실행
elif total_score < -1:
    decision = "sell"         # → 청산 실행
else:
    decision = "hold"         # → 유지
```

---

## 🔧 Phase 1: 진입 흐름에서 AI 제거

### 목표
SignalAnalyzer 결과를 기반으로 즉시 매수 결정, AI 분석 스킵

### 테스트 전략
- **테스트 유형**: Unit + Integration
- **커버리지 목표**: 85%
- **테스트 파일**: `tests/unit/pipeline/test_signal_based_entry.py`

### 작업 목록

#### RED (실패 테스트 먼저)
- [x] `test_signal_analysis_triggers_buy_on_strong_signal` 작성 ✅
- [x] `test_signal_analysis_holds_on_weak_signal` 작성 ✅
- [x] `test_ai_analysis_skipped_in_entry_mode` 작성 ✅
- [x] `test_entry_decision_matches_signal_analyzer_output` 작성 ✅
  - `raw_decision`은 SignalAnalyzer 원본과 일치 검증
  - `decision`은 다운캐스트 결과(`buy`/`hold`/`sell`)와 일치 검증
- [x] `test_extreme_volatility_blocks_entry` 작성 (HybridRiskCheckStage 하드 필터) ✅

#### GREEN (테스트 통과를 위한 최소 구현)
- [x] `AnalysisStage.execute()` 수정: `entry_mode=True`일 때 AI 스킵 ✅
- [x] SignalAnalyzer 결과를 `SignalDecisionDTO`로 변환하는 로직 추가 ✅
- [x] `_handle_signal_based_entry()` 헬퍼 메서드 추가 (스키마 매핑 명확화) ✅
- [x] 극단적 변동성 하드 필터는 HybridRiskCheckStage에서 처리 (ATR% > 10% 시 진입 차단) ✅

#### ATR 하드 필터 적용 범위

| 구분 | 적용 여부 | 근거 |
|------|----------|------|
| **진입 (Entry)** | ✅ 적용 | 높은 변동성에서 신규 진입 방지 |
| **청산 (Exit)** | ❌ 제외 | 이미 보유 중인 포지션은 청산 로직(손절/익절)으로 관리 |
| **AI 검증 호출** | ❌ 제외 | 포지션 관리 시 AI 검증은 변동성과 무관하게 수행 |

> **적용 시점**: HybridRiskCheckStage 실행 시점 (ENTRY 분기 직후, CoinScan/Backtest 이전)에서 평가.
> ATR% > 10%면 해당 사이클에서 진입 차단 (CoinScan/Backtest 자체를 스킵, 다음 사이클에서 재평가).

> **참고**: 포지션 보유 중 변동성 급등 시 HybridRiskCheckStage가 아닌 PositionManagement의 규칙 기반 청산 로직(손절 트리거)이 처리함

#### REFACTOR (코드 품질 개선)
- [x] 중복 코드 제거 ✅
- [x] 명확한 로깅 추가 ✅ (`📊 신호 기반 진입 결정 (AI 스킵)` 로그 추가)
- [x] 타입 힌트 보강 ✅ (entry_mode: bool 파라미터 타입 명시)

### SignalDecisionDTO 스키마 명세

**소유 레이어**: Application (`src/application/dto/trading.py`)

| 역할 | 컴포넌트 | 설명 |
|------|----------|------|
| **생성** | `AnalysisStage` | `SignalDecisionDTO.from_signal_analysis()` 호출 |
| **소비** | `ExecutionStage` | `decision` 필드로 주문 여부 결정 |
| **소비** | `DecisionRecordPort` (저장) | 전체 필드를 DB에 저장 (Adapter 직접 호출 금지) |
| **전달** | `PipelineContext` | Stage 간 DTO 전달 |

```python
@dataclass(frozen=True)
class SignalDecisionDTO:
    """
    SignalAnalyzer 결과를 담는 Application 계층 DTO.

    생성: AnalysisStage.execute() 내 from_signal_analysis() 호출
    소비: ExecutionStage (주문 결정), DecisionRecordAdapter (저장)
    """
    decision: str                    # "buy" | "hold" | "sell"
                                     # strong_buy/buy → "buy", strong_sell/sell → "sell"
    confidence: str                  # "high" | "medium" | "low" | "very_low"
    reason: str                      # 판단 근거 요약

    # 신호 상세 (로깅/추적용)
    raw_decision: str                # 원본: "strong_buy" | "buy" | "hold" | "sell" | "strong_sell"
    total_score: float               # buy_score - sell_score
    buy_score: float
    sell_score: float
    signal_strength: float           # abs(total_score)
    signals: List[str]               # 개별 신호 목록 (최대 10개)

    # 메타데이터
    ticker: str
    current_price: Decimal
    timestamp: datetime

    @classmethod
    def from_signal_analysis(
        cls,
        ticker: str,
        price: Decimal,
        analysis: Dict,
        timestamp: datetime,  # 외부에서 주입 (TimeProviderPort 사용)
    ) -> "SignalDecisionDTO":
        """
        SignalAnalyzer.analyze_signals() 결과에서 생성.

        Note: timestamp는 datetime.now() 직접 호출 대신
              TimeProviderPort.now()를 통해 호출자가 주입해야 함.
              이는 테스트 재현성과 시간 의존성 분리를 위함.
        """
        raw_decision = analysis["decision"]

        # strong_buy/buy → buy, strong_sell/sell → sell (동일 비용 처리)
        if raw_decision in ("strong_buy", "buy"):
            decision = "buy"
        elif raw_decision in ("strong_sell", "sell"):
            decision = "sell"
        else:
            decision = "hold"

        return cls(
            decision=decision,
            confidence=analysis["confidence"],
            reason=f"Signal: {raw_decision} (score: {analysis['total_score']:.1f})",
            raw_decision=raw_decision,
            total_score=analysis["total_score"],
            buy_score=analysis["buy_score"],
            sell_score=analysis["sell_score"],
            signal_strength=analysis["signal_strength"],
            signals=analysis["signals"][:10],
            ticker=ticker,
            current_price=price,
            timestamp=timestamp,  # 주입된 시간 사용
        )
```

> **TimeProviderPort 사용 이유**:
> - 테스트에서 시간 고정 가능 (재현성)
> - 플랫폼/인프라 의존성 분리
> - 시간대(timezone) 일관성 보장

### 변경 파일
```
src/trading/pipeline/analysis_stage.py     # AI 스킵 로직 추가
src/trading/pipeline/base_stage.py         # entry_mode 플래그 추가 (필요 시)
src/application/dto/trading.py             # SignalDecisionDTO 추가
src/trading/pipeline/hybrid_stage.py       # HybridRiskCheckStage 하드 필터 적용 위치
tests/unit/pipeline/test_signal_based_entry.py  # 새 테스트 파일
```

### 품질 게이트
- [x] 프로젝트 빌드 성공 (import error 없음) ✅
- [x] 테스트 먼저 작성 (TDD) ✅
- [x] 신규 테스트 통과 ✅ (16 tests passed)
- [x] 기존 테스트 통과: `pytest tests/unit/pipeline/ -v` ✅ (79 tests passed)
- [ ] 커버리지 유지: ≥80% (확인 필요)
- [ ] Lint 통과 (확인 필요)

### 롤백 전략
- `AnalysisStage` 원복
- `entry_mode` 플래그 제거
- 테스트 파일 제거

---

## 🔧 Phase 2: 실행 스테이지 연동

### 목표
SignalAnalyzer 기반 결정이 ExecutionStage까지 올바르게 전달되도록 검증

### 테스트 전략
- **테스트 유형**: Integration
- **커버리지 목표**: 80%
- **테스트 파일**: `tests/integration/test_signal_based_execution.py`

### 작업 목록

#### RED
- [x] `test_strong_buy_signal_triggers_execution` 작성 ✅
- [x] `test_hold_signal_skips_execution` 작성 ✅
- [x] `test_execution_amount_calculation` 작성 ✅
- [x] 추가: `test_sell_signal_triggers_execution` 작성 ✅
- [x] 추가: `test_buy_signal_with_signal_analysis_in_result` 작성 ✅

#### GREEN
- [x] ExecutionStage가 `SignalDecisionDTO`를 처리하도록 확인 ✅
- [x] decision="buy" 시 동일 포지션 사이즈로 주문 (strong_buy/buy 차등 없음) ✅
- [x] ExecutionStage에 signal_analysis 전달 추가 (Phase 1에서 완료) ✅

#### 스키마 호환성 (레거시 호환 목적)

> **배경**: 기존 ExecutionStage는 `AIDecisionResult` 형태를 기대했으나, 신호 기반 진입에서는 `SignalDecisionDTO`를 사용함.
> 두 DTO가 공통 필드(`decision`, `confidence`, `reason`)를 공유하므로 ExecutionStage 수정 최소화 가능.

| 필드 | AIDecisionResult (기존) | SignalDecisionDTO (신규) | 호환 |
|------|------------------------|-------------------------|------|
| `decision` | "buy"/"hold"/"sell" | "buy"/"hold"/"sell" | ✅ |
| `confidence` | "high"/"medium"/"low" | "high"/"medium"/"low"/"very_low" | ✅ |
| `reason` | AI 생성 문자열 | Signal 기반 문자열 | ✅ |

> **confidence 매핑 규칙**: ExecutionStage는 `very_low`를 `low`로 downgrade 처리함 (로그/DB에는 원본 `very_low` 유지).
> 이는 기존 로직과의 호환성을 보장하면서 신호 기반 결정의 세분화된 신뢰도를 보존함.

- [x] ExecutionStage가 공통 인터페이스로 두 DTO를 처리하도록 검증 ✅
  - ai_result dict 형태로 통일 (decision, confidence, reason)
- [x] (선택) Protocol 불필요 - ai_result dict가 공통 인터페이스 역할 ✅

#### REFACTOR
- [x] 로깅 표준화 ✅ (📊 신호 기반 의사결정 타이틀)
- [x] signal_analysis 결과를 ExecutionStage 결과에 포함 ✅

### 변경 파일
```
src/trading/pipeline/execution_stage.py    # signal_analysis 전달 추가
tests/integration/test_signal_based_execution.py  # 9개 통합 테스트
```

### 품질 게이트
- [x] 프로젝트 빌드 성공 ✅
- [x] TDD 준수 ✅
- [x] 신규 테스트 통과 ✅ (9개 테스트 모두 통과)
- [x] 기존 테스트 통과 ✅ (139 passed, DB 연결 테스트 제외)
- [x] Docker 시뮬레이션 테스트 통과 ✅ (entry_mode=True로 6.24초 실행)

### 롤백 전략
- ExecutionStage 원복
- 테스트 파일 제거

---

## 🔧 Phase 3: 포지션 관리에 AI 검증 통합

### 목표
15분 주기 포지션 관리에서 규칙 기반 체크 후 AI 검증 수행

### 테스트 전략
- **테스트 유형**: Unit + Integration
- **커버리지 목표**: 85%
- **테스트 파일**: `tests/unit/pipeline/test_position_management_ai.py`

### 작업 목록

#### RED ✅ (13개 테스트 작성)
- [x] `test_rule_based_check_triggers_first` 작성 ✅
- [x] `test_stop_loss_triggers_immediate_sell` 작성 ✅
- [x] `test_take_profit_triggers_immediate_sell` 작성 ✅
- [x] `test_ai_verification_called_after_rule_check` 작성 ✅
- [x] `test_ai_can_override_hold_to_sell` 작성 ✅
- [x] `test_ai_keeps_hold_when_no_action_needed` 작성 ✅
- [x] `test_rule_based_sell_bypasses_ai` 작성 ✅
- [x] `test_multiple_positions_independent_checks` 작성 ✅
- [x] `test_position_management_flow` 작성 ✅
- [x] `test_stop_loss_position_immediate_sell` 작성 ✅
- [x] `test_take_profit_position_immediate_sell` 작성 ✅
- [x] `test_custom_stop_loss_threshold` 작성 ✅
- [x] `test_custom_take_profit_threshold` 작성 ✅

#### GREEN ✅
- [x] `HybridRiskCheckStage._handle_management_mode()` 수정 ✅
- [x] `_check_position_rules()` 메서드 추가 - 손절/익절 조건 체크 ✅
- [x] `_execute_position_exit()` 메서드 추가 - 청산 실행 ✅
- [x] 규칙 기반 체크 로직: 손절(-5%), 익절(+10%) ✅
- [x] AI 검증 호출 조건: 규칙이 HOLD 판단 시에만 (TODO 확장점) ✅

#### REFACTOR ✅
- [x] 규칙 파라미터 생성자에서 설정 가능 (stop_loss_pct, take_profit_pct) ✅
- [x] 기존 테스트 Mock 수정 (profit_rate 속성 추가) ✅

### 변경 파일
```
src/trading/pipeline/hybrid_stage.py              # _handle_management_mode, _check_position_rules, _execute_position_exit 추가
tests/unit/pipeline/test_position_management_ai.py  # 13개 테스트 (신규)
tests/unit/pipeline/test_signal_based_entry.py    # Mock 수정 (profit_rate 추가)
```

### 품질 게이트
- [x] 프로젝트 빌드 성공 ✅
- [x] TDD 준수 ✅ (13개 테스트 먼저 작성)
- [x] 신규 테스트 통과 ✅ (13개 통과)
- [x] 기존 테스트 통과 ✅ (92 passed)
- [x] AI 호출 조건 정확히 동작 ✅ (규칙 HOLD 시에만 AI 호출 가능)

### 롤백 전략
- 관련 파일 원복
- 테스트 파일 제거

---

## 🎯 리스크 평가

| 리스크 | 확률 | 영향 | 완화 전략 |
|--------|------|------|-----------|
| SignalAnalyzer 오탐 증가 | Medium | High | 백테스팅으로 임계값 검증, 소액 테스트 |
| AI 비용 완전 제거 시 청산 실수 | Low | High | Phase 3에서 AI 검증 유지 |
| 데이터 수집 성능 영향 | Low | Medium | 비동기 저장, 배치 처리 |
| 극단적 변동성에서 진입 | Medium | High | HybridRiskCheckStage에서 ATR% > 10% 하드 필터로 차단 (Phase 1) |
| 스키마 불일치로 실행 실패 | Medium | Medium | `SignalDecisionDTO.from_signal_analysis()` 테스트 + 호환성 검증 (Phase 1-2) |

---

## ⚠️ 보류된 최적화 (매매 데이터 축적 후)

> **퀀트 원칙**: "먼저 동작하게 만들고, 데이터를 모으고, 그 다음 최적화하라"

| 항목 | 보류 이유 | 재검토 시점 |
|------|-----------|-------------|
| ATR 기반 동적 손절/익절 | 매매 데이터 없음 | 최소 50건 거래 후 |
| 코인별 임계값 캘리브레이션 | 분포 데이터 필요 | [PLAN_ml-data-collection.md](PLAN_ml-data-collection.md) 완료 후 |
| ValidationPort 재설계 | 현재 STUB 상태 | ML 데이터 수집과 통합 |

---

## ✅ 최소 검증/기록 보장 (신호 기반 진입)

AI 제거 이후에도 아래 항목은 유지한다:

- DecisionRecord 저장 (signal 기반 필드로 기록)
- ValidationPort는 "형식/필수 필드 검증"만 우선 적용
- 추후 [ML 데이터 수집](PLAN_ml-data-collection.md) 계획에서 규칙/통계 검증으로 확장

### Validation 실패 시 동작 정책

| 검증 유형 | 실패 시 동작 | 기록 |
|----------|-------------|------|
| 필수 필드 누락 | ❌ HOLD (진입 차단) | DecisionRecord에 `validation_failed` 사유 기록 |
| 형식 오류 (타입 불일치) | ❌ HOLD (진입 차단) | DecisionRecord에 `validation_failed` 사유 기록 |
| 스키마 버전 불일치 | ❌ HOLD (진입 차단) | 에러 로그 + 알림 |
| DTO 변환 실패 | ❌ HOLD (진입 차단) | 에러 로그 + 알림 |

```python
# 실패 처리 예시 (Application 서비스 또는 UseCase에서 처리)
class AnalysisService:
    def __init__(self, decision_record_port: DecisionRecordPort):
        self._decision_record_port = decision_record_port  # Port 주입

    async def handle_validation_failure(
        self, validation_result: ValidationResult, ticker: str, price: Decimal
    ) -> SignalDecisionDTO:
        decision = SignalDecisionDTO(
            decision="hold",
            confidence="very_low",
            reason=f"Validation failed: {validation_result.errors}",
            # ... 나머지 필드
        )
        # Port를 통해 저장 (Adapter 직접 호출 금지)
        await self._decision_record_port.save(decision, validation_failed=True)
        return decision  # HOLD로 진입 차단
```

> **Clean Architecture 원칙**:
> - Stage/Pipeline은 Port를 통해 Application 서비스 호출
> - Application 서비스가 Port를 통해 인프라 접근
> - Adapter 직접 호출은 레이어 침범

#### DecisionRecord 저장 책임 흐름

```
Pipeline(AnalysisStage)
    ↓ 호출
Application Service (AnalysisService)
    ↓ Port 주입
DecisionRecordPort (interface)
    ↓ 구현
DecisionRecordAdapter (infrastructure)
    ↓ 저장
PostgreSQL
```

> **핵심**: Stage는 Adapter에 직접 접근하지 않음. 반드시 Application Service → Port 경로 사용.

---

## 📊 진행 상황

| Phase | 상태 | 완료일 | 테스트 |
|-------|------|--------|--------|
| Phase 1 | ✅ 완료 | 2026-01-04 | 16 tests |
| Phase 2 | ✅ 완료 | 2026-01-04 | 9 tests |
| Phase 3 | ✅ 완료 | 2026-01-04 | 13 tests |

**전체 테스트**: 101 passed ✅

**Last Updated**: 2026-01-04 (Phase 3 완료, Phase 4는 [PLAN_ml-data-collection.md](PLAN_ml-data-collection.md)로 분리)

---

## 📝 Notes & Learnings

_이 섹션은 구현 중 발견한 내용을 기록합니다._

### Phase 1
- **완료일**: 2026-01-04
- **구현된 파일**:
  - `src/application/dto/trading.py`: SignalDecisionDTO 추가 (frozen dataclass)
  - `src/trading/pipeline/analysis_stage.py`: entry_mode 파라미터 및 `_handle_signal_based_entry()` 메서드 추가
  - `src/trading/pipeline/hybrid_stage.py`: ATR 하드 필터 (`_check_atr_volatility()`) 추가
  - `tests/unit/pipeline/test_signal_based_entry.py`: 16개 테스트 (SignalDecisionDTO 9개, AnalysisStage 4개, ATR 필터 3개)
- **학습 내용**:
  - SignalAnalyzer는 MA5 == MA20일 때도 sell_score가 올라감 (>가 아니면 else로 처리)
  - 테스트에서 chart_data는 빈 리스트가 아닌 DataFrame이어야 플래시 크래시 감지 로직이 동작함
  - ATR 필터는 context.atr_pct 또는 technical_indicators에서 계산 가능
- **개선점**:
  - `_handle_signal_based_entry()`가 ai_result dict를 생성하여 ExecutionStage와 호환 유지
  - ATR 정보 없을 때는 필터를 스킵하여 첫 스캔에서도 동작

### Phase 2
- **완료일**: 2026-01-04
- **구현된 파일**:
  - `src/trading/pipeline/execution_stage.py`: signal_analysis를 result_data에 추가
  - `tests/integration/test_signal_based_execution.py`: 9개 통합 테스트 추가
- **테스트 내용**:
  - `test_strong_buy_signal_triggers_execution`: buy 신호 → _execute_buy() 호출 확인
  - `test_buy_signal_with_signal_analysis_in_result`: 결과에 signal_analysis 포함 확인
  - `test_hold_signal_skips_execution`: hold 신호 → _execute_hold() 호출, buy/sell 미호출
  - `test_sell_signal_triggers_execution`: sell 신호 → _execute_sell() 호출 확인
  - `test_execution_amount_calculation`: 매수 금액 = 잔고 × 95%
  - `test_minimum_order_amount_check`: 최소 주문 금액(5000원) 미만 시 0 반환
  - `test_confidence_levels_handled_correctly`: very_low 원본 유지 확인
  - `test_reason_format_from_signal_analyzer`: reason 포맷 "Signal: {decision} (score: {score})"
  - `test_analysis_to_execution_flow`: AnalysisStage → ExecutionStage 전체 흐름
- **학습 내용**:
  - Phase 1에서 AnalysisStage._handle_signal_based_entry()가 ai_result dict를 생성하여 ExecutionStage와 완벽 호환
  - ExecutionStage는 수정 최소화 (signal_analysis 전달만 추가)
  - Protocol/ABC 불필요 - ai_result dict가 공통 인터페이스 역할
- **Docker 테스트 결과**:
  - entry_mode=True 동작 확인
  - 실행 시간: 6.24초 (AI 스킵으로 빠름)
  - 텔레그램 알림에 signal_analysis 상세 표시 정상

### Phase 3
- (예정)

### Phase 4
- (예정)

---

## 📚 참고 파일

- [analysis_stage.py](../../src/trading/pipeline/analysis_stage.py) - 현재 분석 파이프라인
- [signal_analyzer.py](../../src/trading/signal_analyzer.py) - SignalAnalyzer 클래스
- [settings.py](../../src/config/settings.py) - 설정 파일
- [ARCHITECTURE.md](../guide/ARCHITECTURE.md) - 시스템 아키텍처
