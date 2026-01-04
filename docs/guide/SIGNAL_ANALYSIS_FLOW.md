# 신호 분석 로직 흐름 가이드

**작성일**: 2026-01-04
**목적**: 트레이딩 파이프라인에서 "신호 분석 결과" 로직의 실행 흐름과 AI 분석과의 관계 파악

---

## 📋 목차

1. [개요](#개요)
2. [신호 분석 로직 흐름](#신호-분석-로직-흐름)
3. [신호 분석 상세 (SignalAnalyzer)](#신호-분석-상세-signalanalyzer)
4. [AI 분석과의 관계](#ai-분석과의-관계)
5. [중요 포인트](#중요-포인트)

---

## 개요

로그에서 확인되는 "신호 분석 결과"는 **규칙 기반(Rule-based) 기술적 지표 분석**입니다.
이는 AI 분석 **이전에** 실행되며, AI에 직접 전달되지 않습니다.

### 실행 순서 (AnalysisStage)

```
1. 시장 상관관계 분석 (market_correlation)
2. 플래시 크래시 감지 (flash_crash)
3. RSI 다이버전스 감지 (rsi_divergence)
4. 백테스팅 필터
5. 신호 분석 ⭐ (SignalAnalyzer.analyze_signals) ← 여기서 매수/매도 점수 계산
6. AI 분석 (OpenAI API 호출)
7. AI 판단 검증
```

**핵심**: 신호 분석(5단계)과 AI 분석(6단계)은 **병렬적**이며, 서로 독립적입니다.

---

## 신호 분석 로직 흐름

### 1. 진입점 (Entry Point)

**파일**: [src/trading/pipeline/analysis_stage.py:256-282](src/trading/pipeline/analysis_stage.py#L256-L282)

```python
def _analyze_signals(self, context: PipelineContext) -> None:
    """
    신호 분석

    Args:
        context: 파이프라인 컨텍스트
    """
    if not context.technical_indicators or not context.current_status.get('current_price'):
        context.signal_analysis = None
        return

    context.signal_analysis = SignalAnalyzer.analyze_signals(
        context.technical_indicators,
        context.current_status['current_price']
    )

    Logger.print_header("📊 신호 분석 결과")
    print(f"결정: {context.signal_analysis['decision']}")
    print(f"매수 점수: {context.signal_analysis['buy_score']:.1f}")
    print(f"매도 점수: {context.signal_analysis['sell_score']:.1f}")
    print(f"총 점수: {context.signal_analysis['total_score']:.1f}")
    print(f"신호 강도: {context.signal_analysis['signal_strength']:.1f}")
    print(f"신뢰도: {context.signal_analysis['confidence']}")
    ...
```

### 2. 신호 분석 실행 (SignalAnalyzer)

**파일**: [src/trading/signal_analyzer.py:13-75](src/trading/signal_analyzer.py#L13-L75)

**입력**:
- `indicators`: 기술적 지표 딕셔너리 (RSI, MACD, 볼린저 밴드 등)
- `current_price`: 현재가

**출력**:
```python
{
    "decision": "strong_buy|buy|hold|sell|strong_sell",
    "buy_score": float,      # 매수 점수 (0~N)
    "sell_score": float,     # 매도 점수 (0~N)
    "total_score": float,    # buy_score - sell_score
    "signal_strength": float,# abs(total_score)
    "signals": list,         # 주요 신호 리스트
    "confidence": str        # "high|medium|low|very_low"
}
```

### 3. 분석 프로세스

```
SignalAnalyzer.analyze_signals()
├─ _analyze_trend()         # 추세 지표 분석
│  ├─ 이동평균선 (MA5, MA20, MA60)
│  ├─ 지수이동평균 (EMA12, EMA26)
│  ├─ MACD / Signal / Histogram
│  └─ ADX (추세 강도)
│
├─ _analyze_momentum()      # 모멘텀 지표 분석
│  ├─ RSI
│  ├─ Stochastic (K, D)
│  ├─ MFI
│  └─ Williams %R
│
├─ _analyze_volatility()    # 변동성 지표 분석
│  ├─ 볼린저 밴드 (상단/중간/하단)
│  ├─ CCI
│  └─ ATR
│
├─ _analyze_volume()        # 거래량 지표 분석
│  └─ OBV
│
└─ 최종 결정 (decision logic)
   ├─ total_score > 3  → strong_buy
   ├─ total_score > 1  → buy
   ├─ total_score < -3 → strong_sell
   ├─ total_score < -1 → sell
   └─ 나머지           → hold
```

---

## 신호 분석 상세 (SignalAnalyzer)

### 매수/매도 점수 계산 로직

각 카테고리별로 매수/매도 점수를 누적합니다.

#### 1. 추세 지표 분석 (`_analyze_trend`)

**파일**: [src/trading/signal_analyzer.py:78-158](src/trading/signal_analyzer.py#L78-L158)

| 조건 | 점수 | 설명 |
|------|------|------|
| MA5 > MA20 | **매수 +1** | 단기 상승 추세 |
| MA5 < MA20 | **매도 +1** | 단기 하락 추세 |
| MA20 > MA60 | **매수 +1** | 중기 상승 추세 |
| MA20 < MA60 | **매도 +1** | 중기 하락 추세 |
| 현재가 > MA20 | **매수 +0.5** | 지지선 위 |
| 현재가 < MA20 | **매도 +0.5** | 저항선 아래 |
| EMA12 > EMA26 | **매수 +1** | EMA 골든크로스 |
| EMA12 < EMA26 | **매도 +1** | EMA 데드크로스 |
| MACD > Signal | **매수 +1.5** | 상승 모멘텀 |
| MACD < Signal | **매도 +1.5** | 하락 모멘텀 |
| MACD Histogram > 0 | **매수 +0.5** | 모멘텀 확인 |
| ADX > 25 | **가중치 +0.5** | 강한 추세 (기존 신호 강화) |

#### 2. 모멘텀 지표 분석 (`_analyze_momentum`)

**파일**: [src/trading/signal_analyzer.py:161-223](src/trading/signal_analyzer.py#L161-L223)

| 조건 | 점수 | 설명 |
|------|------|------|
| RSI < 30 | **매수 +2** | 과매도 구간 |
| RSI < 40 | **매수 +1** | 약한 과매도 |
| RSI > 70 | **매도 +2** | 과매수 구간 |
| RSI > 60 | **매도 +1** | 약한 과매수 |
| Stochastic K < 20 AND D < 20 | **매수 +1.5** | 과매도 |
| Stochastic K > 80 AND D > 80 | **매도 +1.5** | 과매수 |
| Stochastic K > D | **매수 +0.5** | 상승 모멘텀 |
| MFI < 20 | **매수 +1** | 과매도 |
| MFI > 80 | **매도 +1** | 과매수 |
| Williams %R < -80 | **매수 +1** | 과매도 |
| Williams %R > -20 | **매도 +1** | 과매수 |

#### 3. 변동성 지표 분석 (`_analyze_volatility`)

**파일**: [src/trading/signal_analyzer.py:226-273](src/trading/signal_analyzer.py#L226-L273)

| 조건 | 점수 | 설명 |
|------|------|------|
| 현재가 <= BB 하단 | **매수 +2** | 과매도 |
| 현재가 >= BB 상단 | **매도 +2** | 과매수 |
| 현재가 < BB 중간선 | **매수 +0.5** | 하단 근접 |
| 현재가 > BB 중간선 | **매도 +0.5** | 상단 근접 |
| CCI < -100 | **매수 +1** | 과매도 |
| CCI > 100 | **매도 +1** | 과매수 |

#### 4. 거래량 지표 분석 (`_analyze_volume`)

**파일**: [src/trading/signal_analyzer.py:276-294](src/trading/signal_analyzer.py#L276-L294)

| 조건 | 점수 | 설명 |
|------|------|------|
| OBV 변화율 > 5% | **매수 +1** | 거래량 급증 |
| OBV 변화율 < -5% | **매도 +1** | 거래량 급감 |

### 신뢰도 계산 (`_calculate_confidence`)

**파일**: [src/trading/signal_analyzer.py:297-306](src/trading/signal_analyzer.py#L297-L306)

```python
def _calculate_confidence(signal_strength: float, signal_count: int) -> str:
    """신뢰도 계산"""
    if signal_strength >= 5 and signal_count >= 8:
        return "high"
    elif signal_strength >= 3 and signal_count >= 5:
        return "medium"
    elif signal_strength >= 1:
        return "low"
    else:
        return "very_low"
```

### 로그 예시 해석

```
============================================================
📊 신호 분석 결과
============================================================
결정: sell
매수 점수: 4.0
매도 점수: 6.0
총 점수: -2.0
신호 강도: 2.0
신뢰도: low

주요 신호:
• MA5 > MA20 (단기 상승 추세)          → 매수 +1
• MA20 < MA60 (중기 하락 추세)         → 매도 +1
• 현재가 > MA20                        → 매수 +0.5
• EMA12 < EMA26 (EMA 데드크로스)       → 매도 +1
• MACD > Signal (상승 모멘텀)          → 매수 +1.5
• ADX=41.4 (강한 추세)                 → 매도 +0.5 (하락 추세 강화)
• RSI=57.6 (중립)                      → 점수 없음
• Stochastic K=92.6, D=86.0 (과매수)   → 매도 +1.5
• Williams %R=-7.4 (과매수)            → 매도 +1
• 현재가 > 볼린저 중간선               → 매도 +0.5
============================================================

계산:
- 매수 점수 = 1 + 0.5 + 1.5 + 1 = 4.0
- 매도 점수 = 1 + 1 + 1.5 + 1 + 0.5 + 0.5 = 6.0
- 총 점수 = 4.0 - 6.0 = -2.0
- 신호 강도 = abs(-2.0) = 2.0
- 신뢰도 = "low" (신호 강도 2.0 < 3)
- 결정 = "sell" (총 점수 -2.0 < -1)
```

---

## AI 분석과의 관계

### 신호 분석 vs AI 분석

| 구분 | 신호 분석 | AI 분석 |
|------|-----------|---------|
| **타입** | 규칙 기반 (Rule-based) | AI 기반 (GPT-4) |
| **실행 시점** | AI 분석 **이전** | 신호 분석 **이후** |
| **입력** | 기술적 지표 원본값 | 기술적 지표 원본값 + 컨텍스트 |
| **출력** | 매수/매도 점수 + 결정 | buy/sell/hold 결정 + 신뢰도 |
| **용도** | 참고 정보 (로깅) | **최종 거래 결정** |
| **비용** | 없음 (로컬 계산) | 있음 (OpenAI API 호출) |

### AI에 전달되는 정보

**파일**: [src/infrastructure/adapters/ai/openai_adapter.py:236-322](src/infrastructure/adapters/ai/openai_adapter.py#L236-L322)

AI 분석 프롬프트에는 **신호 분석 결과가 직접 포함되지 않습니다**.
대신 다음 정보를 전달합니다:

1. **기술적 지표 원본값** (신호 분석과 동일한 입력)
   - RSI, MACD, MACD Signal
   - 볼린저 밴드 (상단/중간/하단)
   - SMA20, SMA50, EMA12, EMA26
   - ATR

2. **추가 컨텍스트** (신호 분석에는 없는 정보)
   - 백테스팅 결과 (총 수익률, 승률, Sharpe Ratio)
   - 시장 상관관계 (BTC 베타, 상관계수)
   - 플래시 크래시 감지 여부
   - RSI 다이버전스 감지 여부

3. **포지션 정보** (있는 경우)
   - 진입가, 현재 수익률, 보유 수량

### AI 분석 흐름

```
AnalysisStage._perform_ai_analysis()
└─ UseCase 경로 (Container 있을 때)
   ├─ AnalyzeMarketUseCase.analyze()
   │  └─ AIPort.analyze(AnalysisRequest)
   │     └─ OpenAIAdapter.analyze()
   │        ├─ _build_analysis_prompt() ← 여기서 프롬프트 생성
   │        ├─ OpenAI API 호출 (GPT-4)
   │        └─ _parse_decision() → TradingDecision
   │
   └─ TradingDecision 변환 → ai_result dict
```

### AI 프롬프트 시스템 메시지 핵심

**파일**: [src/infrastructure/adapters/ai/openai_adapter.py:189-234](src/infrastructure/adapters/ai/openai_adapter.py#L189-L234)

```
당신은 **리스크 헌터(Risk Hunter)** 역할의 암호화폐 트레이딩 검증자입니다.
당신의 임무는 이 거래를 **막을 이유를 적극적으로 찾는 것**입니다.

핵심 임무: 이 거래를 막을 이유를 찾으세요
1. 시장 국면 변화 (Regime Change)
2. 모멘텀 약화 신호
3. 구조적 위험

판단 기준:
- BUY: 안전 조건 모두 충족 AND 위험 조건 없음 AND 막을 이유 없음
- SELL: 포지션 있을 때만 - 손절/익절 조건 충족 시
- HOLD: 안전 조건 미충족 OR 위험 조건 존재 OR 막을 이유 1개 이상
```

**중요**: AI는 **보수적**으로 판단하며, 신호 분석 결과와 무관하게 독립적으로 결정합니다.

---

## 중요 포인트

### 1. 신호 분석은 참고용입니다

신호 분석 결과는 **최종 거래 결정에 직접 사용되지 않습니다**.
파이프라인에서 로깅 목적으로 출력되며, 개발자가 시스템 동작을 이해하는 데 도움을 줍니다.

### 2. AI는 신호 분석 결과를 모릅니다

AI는 신호 분석의 매수/매도 점수를 **알지 못합니다**.
대신 동일한 기술적 지표 원본값을 받아 **독립적으로 판단**합니다.

### 3. 두 분석의 차이점

- **신호 분석**: 점수 기반 규칙 (빠르고 결정적)
- **AI 분석**: 컨텍스트 기반 추론 (느리고 비용 발생, 리스크 중심)

### 4. 최종 거래 결정 흐름

```
신호 분석 (참고용 로깅)
        ↓
AI 분석 (OpenAI via AIPort) ← 최종 결정
        ↓
AI 판단 검증 (ValidationPort)
        ↓
거래 실행 (ExecutionStage)
```

### 5. 왜 두 개의 분석이 필요한가?

| 목적 | 구현 |
|------|------|
| **빠른 사전 필터링** | 백테스팅 필터 (AI 호출 전) |
| **기계적 신호 확인** | 신호 분석 (로깅 목적) |
| **리스크 중심 판단** | AI 분석 (최종 결정) |
| **검증 레이어** | AI 판단 검증 (안전장치) |

### 6. 파일 위치 정리

```
src/trading/pipeline/analysis_stage.py       # 분석 스테이지 오케스트레이션
├─ _analyze_signals()                        # 신호 분석 호출
└─ _perform_ai_analysis()                    # AI 분석 호출

src/trading/signal_analyzer.py               # 신호 분석 로직
├─ analyze_signals()                         # 메인 진입점
├─ _analyze_trend()                          # 추세 지표
├─ _analyze_momentum()                       # 모멘텀 지표
├─ _analyze_volatility()                     # 변동성 지표
├─ _analyze_volume()                         # 거래량 지표
└─ _calculate_confidence()                   # 신뢰도 계산

src/application/use_cases/analyze_market.py  # AI 분석 UseCase
└─ analyze()                                 # 시장 분석 오케스트레이션

src/infrastructure/adapters/ai/openai_adapter.py  # OpenAI AI Port 구현
├─ analyze()                                 # AI 분석 진입점
├─ _build_analysis_prompt()                  # 프롬프트 생성
└─ _parse_decision()                         # 응답 파싱
```

### 7. 로그 해석 가이드

로그에서 다음 순서로 출력됩니다:

```
1. 📊 시장 상관관계 분석
2. ✅ 플래시 크래시 없음
3. 📉 RSI 다이버전스 분석
4. 📊 스캔에서 이미 필터링 완료 - 백테스팅 스킵
5. ✅ ETH 선택됨 (44.5점) - AI 분석 진행
6. 📊 신호 분석 결과 ← 여기가 규칙 기반 분석 (참고용)
   - 매수 점수: 4.0
   - 매도 점수: 6.0
   - 결정: sell
7. [이후 AI 분석 결과 출력]
   - AI 판단: buy/sell/hold
   - 신뢰도: high/medium/low
```

**핵심**: 6번(신호 분석)과 7번(AI 분석)은 **독립적**이며, 6번은 7번에 영향을 주지 않습니다.

---

## 참고 문서

- [docs/guide/ARCHITECTURE.md](ARCHITECTURE.md) - 전체 아키텍처 개요
- [src/trading/pipeline/analysis_stage.py](../../src/trading/pipeline/analysis_stage.py) - 분석 스테이지 구현
- [src/trading/signal_analyzer.py](../../src/trading/signal_analyzer.py) - 신호 분석 구현
- [src/infrastructure/adapters/ai/openai_adapter.py](../../src/infrastructure/adapters/ai/openai_adapter.py) - OpenAI Adapter 구현
