# 리팩토링 보고서 (2026-01-01)

## 개요

기존 `main.py`의 800줄 이상 코드를 파이프라인 아키텍처로 리팩토링하여 코드 복잡도를 대폭 감소시키고, 선물 거래 확장을 위한 기반을 마련했습니다.

## 주요 변경 사항

### 1. 파이프라인 아키텍처 도입

**Before (기존 구조)**:
- `main.py`: 800줄 이상의 모놀리식 함수
- `execute_trading_cycle()`: 모든 로직이 하나의 함수에 집중
- 단일 책임 원칙(SRP) 위반
- 테스트 어려움
- 선물 거래 확장 불가능

**After (리팩토링 후)**:
- `main.py`: 175줄로 간소화
- 파이프라인 패턴을 통한 단계별 실행
- 각 스테이지는 독립적으로 테스트 가능
- 선물 거래 확장 기반 마련

### 2. 새로운 디렉토리 구조

```
src/trading/
├── pipeline/                    # 파이프라인 아키텍처
│   ├── __init__.py
│   ├── base_stage.py           # 베이스 스테이지 인터페이스
│   ├── risk_check_stage.py     # 리스크 체크 스테이지
│   ├── data_collection_stage.py # 데이터 수집 스테이지
│   ├── analysis_stage.py       # 분석 스테이지
│   ├── execution_stage.py      # 거래 실행 스테이지
│   └── trading_pipeline.py     # 파이프라인 오케스트레이터
└── types/                       # 거래 타입 추상화
    ├── __init__.py
    ├── base_trader.py          # 트레이더 베이스 클래스
    ├── spot_trader.py          # 현물 트레이더
    └── futures_trader.py       # 선물 트레이더 (스켈레톤)
```

### 3. 파이프라인 스테이지 분리

거래 사이클이 4개의 독립적인 스테이지로 분리되었습니다:

#### 1) RiskCheckStage (리스크 체크)
- **책임**: 거래 실행 전 모든 리스크 조건 체크
- **기능**:
  - 손절/익절 체크
  - Circuit Breaker 체크
  - 거래 빈도 제한 체크
- **Early Exit**: 손절/익절 조건 충족 시 즉시 매도 후 파이프라인 종료

#### 2) DataCollectionStage (데이터 수집)
- **책임**: 거래 판단에 필요한 모든 데이터 수집
- **수집 데이터**:
  - 차트 데이터 (ETH + BTC)
  - 오더북 데이터
  - 기술적 지표
  - 현재 상태 및 포지션 정보
  - 공포탐욕지수

#### 3) AnalysisStage (분석)
- **책임**: 시장 분석, 기술적 분석, AI 분석 수행
- **분석 항목**:
  - 시장 상관관계 분석 (BTC-ETH 베타/알파)
  - 플래시 크래시 감지
  - RSI 다이버전스 감지
  - 백테스팅 필터
  - 신호 분석
  - AI 분석
  - AI 판단 검증

#### 4) ExecutionStage (거래 실행)
- **책임**: AI 분석 결과를 기반으로 실제 거래 실행
- **기능**:
  - 매수/매도/보류 실행
  - 거래 시간 기록
  - 손익 기록

### 4. 선물 거래 확장 기반

#### 트레이더 추상화
- `BaseTrader`: 현물/선물 공통 인터페이스
- `SpotTrader`: 현물 거래 구현
- `FuturesTrader`: 선물 거래 스켈레톤 (미래 구현)

#### 주요 개념
```python
@dataclass
class Position:
    """포지션 정보 (현물/선물 공통)"""
    ticker: str
    position_type: str  # 'spot', 'long', 'short'
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float

@dataclass
class OrderRequest:
    """주문 요청 (현물/선물 공통)"""
    ticker: str
    side: str  # 'buy', 'sell', 'long', 'short', 'close'
    amount: Optional[float] = None
    price: Optional[float] = None
    order_type: str = 'market'
    leverage: int = 1  # 선물 전용
```

### 5. 파이프라인 사용 방법

**현물 거래 파이프라인 생성**:
```python
from src.trading.pipeline import create_spot_trading_pipeline, PipelineContext

# 파이프라인 생성
pipeline = create_spot_trading_pipeline(
    stop_loss_pct=-5.0,
    take_profit_pct=10.0,
    daily_loss_limit_pct=-10.0,
    min_trade_interval_hours=4
)

# 컨텍스트 생성
context = PipelineContext(
    ticker="KRW-ETH",
    trading_type="spot",
    upbit_client=upbit_client,
    data_collector=data_collector,
    trading_service=trading_service,
    ai_service=ai_service
)

# 실행
result = await pipeline.execute(context)
```

**선물 거래 파이프라인 (미래)**:
```python
# TODO: 선물 거래 파이프라인 구현 후
pipeline = create_futures_trading_pipeline(
    leverage=5,
    stop_loss_pct=-3.0,
    take_profit_pct=15.0
)
```

## 코드 메트릭 개선

| 메트릭 | Before | After | 개선 |
|--------|--------|-------|------|
| main.py 라인 수 | 800+ | 175 | **-78%** |
| execute_trading_cycle 라인 수 | 400+ | 50 | **-87%** |
| 최대 함수 복잡도 | 매우 높음 | 낮음 | **대폭 개선** |
| 단일 책임 원칙 준수 | ❌ | ✅ | **개선** |
| 테스트 용이성 | 어려움 | 쉬움 | **개선** |
| 선물 거래 확장성 | 불가능 | 가능 | **개선** |

## 장점

### 1. 코드 가독성 향상
- 각 스테이지가 명확한 책임을 가짐
- 파이프라인 흐름이 직관적
- 새로운 개발자도 쉽게 이해 가능

### 2. 테스트 용이성
- 각 스테이지를 독립적으로 테스트 가능
- Mock 객체를 사용한 단위 테스트 작성 용이
- 통합 테스트도 파이프라인 단위로 수행 가능

### 3. 유지보수성 향상
- 단일 책임 원칙 준수로 변경 영향 범위 최소화
- 스테이지별 독립적 수정 가능
- 버그 추적 및 디버깅 용이

### 4. 확장성
- 새로운 스테이지 추가 용이
- 선물 거래 지원을 위한 기반 마련
- 다른 거래소 API 통합 용이

### 5. 재사용성
- 스테이지를 다른 파이프라인에서도 재사용 가능
- 거래 타입(현물/선물)에 따라 스테이지 조합 가능

## 향후 개선 사항

### 1. 선물 거래 구현
- [ ] FuturesTrader 구현
- [ ] FuturesRiskCheckStage 구현 (레버리지 고려)
- [ ] FuturesDataCollectionStage 구현 (펀딩비, 미결제약정 등)
- [ ] FuturesExecutionStage 구현 (롱/숏 포지션 관리)

### 2. 파이프라인 고도화
- [ ] 스테이지 간 데이터 의존성 자동 검증
- [ ] 스테이지 실행 시간 모니터링
- [ ] 스테이지별 재시도 로직
- [ ] 파이프라인 상태 저장 및 복구

### 3. 테스트 커버리지 확대
- [ ] 각 스테이지별 단위 테스트 작성
- [ ] 파이프라인 통합 테스트 작성
- [ ] 엣지 케이스 테스트 추가

### 4. 성능 최적화
- [ ] 스테이지 병렬 실행 (독립적인 스테이지)
- [ ] 데이터 캐싱 전략
- [ ] 비동기 처리 최적화

## 마이그레이션 가이드

기존 코드와 완벽하게 호환됩니다:

```python
# 기존 방식 (여전히 작동)
result = await execute_trading_cycle(
    ticker,
    upbit_client,
    data_collector,
    trading_service,
    ai_service
)

# 새로운 방식 (권장)
result = await execute_trading_cycle(
    ticker,
    upbit_client,
    data_collector,
    trading_service,
    ai_service,
    trading_type='spot'  # 선택적 파라미터
)
```

반환값도 동일하므로 기존 코드 변경 불필요.

## 결론

이번 리팩토링을 통해:

1. **코드 복잡도 78% 감소** (800줄 → 175줄)
2. **단일 책임 원칙 준수**로 유지보수성 향상
3. **선물 거래 확장 기반** 마련
4. **테스트 용이성** 대폭 개선
5. **파이프라인 패턴**을 통한 직관적인 구조

선물 거래 지원을 위한 견고한 아키텍처가 완성되었으며, 향후 확장 및 유지보수가 용이한 구조로 발전했습니다.

---

**작성일**: 2026-01-01
**작성자**: Claude Code Refactoring Assistant
