# 트레이딩 봇 시퀀스 흐름도

## 목차

1. [전체 시스템 흐름도](#1-전체-시스템-흐름도)
2. [스케줄러 모듈 흐름](#2-스케줄러-모듈-흐름)
3. [거래 실행 모듈 흐름](#3-거래-실행-모듈-흐름)
4. [데이터베이스 저장 흐름](#4-데이터베이스-저장-흐름)
5. [모니터링 및 알림 흐름](#5-모니터링-및-알림-흐름)
6. [에러 처리 흐름](#6-에러-처리-흐름)

---

## 1. 전체 시스템 흐름도

전체 거래 사이클의 엔드-투-엔드 흐름을 보여줍니다.

```mermaid
sequenceDiagram
    participant Scheduler as 스케줄러<br/>(scheduler_main.py)
    participant BackendScheduler as Backend Scheduler<br/>(core/scheduler.py)
    participant Main as main.py<br/>(execute_trading_cycle)
    participant TradingService as TradingService<br/>(src/trading/service.py)
    participant Upbit as Upbit API<br/>(거래소)
    participant DB as PostgreSQL<br/>(trades 테이블)
    participant API as Backend API<br/>(POST /trades/)
    participant Metrics as Prometheus<br/>(메트릭)
    participant Telegram as Telegram<br/>(알림)

    Scheduler->>BackendScheduler: 1시간마다 trading_job() 실행
    BackendScheduler->>Main: execute_trading_cycle() 호출

    Note over Main: 1. 현재 투자 상태 조회<br/>2. 차트 데이터 수집<br/>3. 시장 분석<br/>4. 백테스팅 필터링

    Main->>Main: AI 분석 수행
    Main->>TradingService: execute_buy() 또는<br/>execute_sell() 호출

    TradingService->>Upbit: 매수/매도 주문 전송
    Upbit-->>TradingService: 주문 결과 반환<br/>(uuid, price, volume, fee)

    TradingService-->>Main: 거래 실행 결과
    Main-->>BackendScheduler: result 반환<br/>{status, decision, price, amount, trade_id}

    alt 거래 성공 (buy 또는 sell)
        BackendScheduler->>API: POST /trades/ 호출
        Note over BackendScheduler,API: TradeCreate 스키마<br/>{trade_id, symbol, side,<br/>price, amount, total, fee, status}
        API->>DB: Trade 레코드 INSERT
        DB-->>API: 저장 완료
        API-->>BackendScheduler: TradeResponse

        BackendScheduler->>Metrics: 거래 메트릭 기록<br/>record_trade()
        BackendScheduler->>Metrics: AI 판단 메트릭 기록<br/>record_ai_decision()
        BackendScheduler->>Telegram: 거래 알림 전송<br/>notify_trade()
    else 거래 실패 또는 hold
        BackendScheduler->>Metrics: AI 판단만 기록
        BackendScheduler->>Telegram: 에러 알림 (실패 시)
    end
```

### 주요 컴포넌트 설명

| 컴포넌트              | 파일 경로                       | 역할                               |
| --------------------- | ------------------------------- | ---------------------------------- |
| **Scheduler**         | `scheduler_main.py`             | 1시간 주기로 거래 작업 스케줄링    |
| **Backend Scheduler** | `backend/app/core/scheduler.py` | 거래 사이클 실행 및 후처리 관리    |
| **Main**              | `main.py`                       | 거래 로직 실행 (AI 분석, 의사결정) |
| **TradingService**    | `src/trading/service.py`        | 실제 거래소 API 호출               |
| **Upbit API**         | 외부 API                        | 업비트 거래소                      |
| **PostgreSQL**        | Docker 컨테이너                 | 거래 데이터 저장                   |
| **Backend API**       | `backend/app/api/trades.py`     | REST API 엔드포인트                |
| **Prometheus**        | Docker 컨테이너                 | 메트릭 수집                        |
| **Telegram**          | 외부 API                        | 알림 전송                          |

---

## 2. 스케줄러 모듈 흐름

스케줄러가 어떻게 주기적으로 거래 작업을 실행하는지 보여줍니다.

```mermaid
sequenceDiagram
    participant User as 사용자/시스템
    participant Scheduler as Scheduler<br/>(scheduler_main.py)
    participant APScheduler as APScheduler<br/>(BackgroundScheduler)
    participant BackendScheduler as Backend Scheduler<br/>(core/scheduler.py)
    participant Logger as Logger

    User->>Scheduler: 애플리케이션 시작
    Scheduler->>Scheduler: load_dotenv()<br/>.env 파일 로드
    Scheduler->>Scheduler: 환경변수 검증<br/>(API_KEY, SECRET, DB_URL)

    alt 환경변수 누락
        Scheduler->>Logger: ERROR 로그 기록
        Scheduler->>User: 프로그램 종료 (exit 1)
    end

    Scheduler->>APScheduler: 스케줄러 생성<br/>BackgroundScheduler()
    Scheduler->>APScheduler: add_job(<br/>trading_job,<br/>trigger='cron',<br/>hour='*'<br/>)

    Note over Scheduler,APScheduler: 매시 정각에 실행되도록 설정

    Scheduler->>APScheduler: start()
    APScheduler->>Logger: INFO: 스케줄러 시작됨

    loop 매 시간 정각
        APScheduler->>BackendScheduler: trading_job() 실행
        BackendScheduler->>Logger: INFO: 거래 작업 시작
        BackendScheduler->>BackendScheduler: 거래 로직 실행<br/>(다음 섹션 참조)
        BackendScheduler-->>APScheduler: 작업 완료
        APScheduler->>Logger: INFO: 거래 작업 완료
    end

    User->>Scheduler: Ctrl+C (중단 신호)
    Scheduler->>APScheduler: shutdown()
    APScheduler->>Logger: INFO: 스케줄러 종료됨
    Scheduler->>User: 프로그램 정상 종료
```

### 스케줄러 설정 상세

#### Cron 트리거 설정

```python
# scheduler_main.py
scheduler.add_job(
    trading_job,
    trigger='cron',
    hour='*',        # 매 시간 정각
    minute='0',      # 0분에 실행
    timezone='Asia/Seoul'
)
```

#### 주요 로그 포인트

1. **스케줄러 시작**: `Scheduler started. Waiting for trading jobs...`
2. **작업 실행**: `[INFO] Trading job started at {timestamp}`
3. **작업 완료**: `[INFO] Trading job completed at {timestamp}`
4. **에러 발생**: `[ERROR] Trading job failed: {error_message}`

---

## 3. 거래 실행 모듈 흐름

실제 거래가 어떻게 실행되는지 상세 흐름을 보여줍니다.

```mermaid
sequenceDiagram
    participant BackendScheduler as Backend Scheduler<br/>(core/scheduler.py)
    participant Main as main.py<br/>(execute_trading_cycle)
    participant PositionService as PositionService<br/>(src/position/service.py)
    participant DataCollector as DataCollector<br/>(src/data/collector.py)
    participant AIService as AIService<br/>(src/ai/service.py)
    participant BacktestRunner as BacktestRunner<br/>(src/backtesting/runner.py)
    participant TradingService as TradingService<br/>(src/trading/service.py)
    participant Upbit as Upbit API

    BackendScheduler->>Main: execute_trading_cycle()

    Note over Main: Phase 1: 데이터 수집
    Main->>PositionService: get_current_position()
    PositionService->>Upbit: GET /v1/accounts
    Upbit-->>PositionService: 계좌 정보<br/>(잔고, 평가금액)
    PositionService-->>Main: Position 객체

    Main->>DataCollector: collect_chart_data()<br/>(symbol, interval, count)
    DataCollector->>Upbit: GET /v1/candles/minutes/60
    Upbit-->>DataCollector: 차트 데이터<br/>(OHLCV)
    DataCollector-->>Main: DataFrame (차트)

    Note over Main: Phase 2: AI 분석
    Main->>AIService: analyze_market(<br/>chart_data,<br/>position,<br/>context<br/>)
    AIService->>AIService: 기술적 지표 계산<br/>(RSI, MACD, BB, etc.)
    AIService->>AIService: GPT-4 API 호출<br/>시장 분석 및 판단
    AIService-->>Main: Decision<br/>(action, confidence, reason)

    Note over Main: Phase 3: 백테스팅 필터링
    alt decision == 'buy'
        Main->>BacktestRunner: quick_filter_strategy()
        BacktestRunner->>BacktestRunner: 최근 데이터로<br/>전략 검증
        BacktestRunner-->>Main: is_passed (True/False)

        alt is_passed == False
            Main-->>BackendScheduler: {status: 'hold',<br/>reason: 'backtest_filter_failed'}
        end
    end

    Note over Main: Phase 4: 거래 실행
    alt decision == 'buy' and backtest_passed
        Main->>TradingService: execute_buy(<br/>symbol,<br/>amount,<br/>price<br/>)
        TradingService->>Upbit: POST /v1/orders<br/>(side=bid)
        Upbit-->>TradingService: Order Response<br/>(uuid, executed_volume, price, fee)
        TradingService-->>Main: TradeResult<br/>(success, trade_id, details)
    else decision == 'sell'
        Main->>TradingService: execute_sell(<br/>symbol,<br/>volume<br/>)
        TradingService->>Upbit: POST /v1/orders<br/>(side=ask)
        Upbit-->>TradingService: Order Response
        TradingService-->>Main: TradeResult
    else decision == 'hold'
        Main-->>BackendScheduler: {status: 'hold',<br/>reason: ai_reason}
    end

    Main-->>BackendScheduler: Final Result<br/>{status, decision, price, amount, trade_id}
```

### 거래 실행 Phase별 상세

#### Phase 1: 데이터 수집

- **현재 포지션 조회**

  - KRW 잔고
  - ETH 보유량
  - 평균 매수가
  - 평가 손익

- **차트 데이터 수집**
  - 1시간봉 기준
  - 최근 200개 캔들
  - OHLCV 데이터

#### Phase 2: AI 분석

- **기술적 지표**

  - RSI (14)
  - MACD (12, 26, 9)
  - Bollinger Bands (20, 2)
  - Moving Averages (MA20, MA50, MA200)
  - Volume Profile

- **AI 판단**
  - GPT-4 API 호출
  - 컨텍스트: 차트 데이터 + 지표 + 포지션 정보
  - 응답: action (buy/sell/hold), confidence, reason

#### Phase 3: 백테스팅 필터링

- **Quick Filter**
  - 최근 1개월 데이터로 전략 검증
  - 승률 50% 이상
  - MDD -10% 이내
  - Sharpe Ratio 0.5 이상

#### Phase 4: 거래 실행

- **매수 주문**

  - 시장가 주문 (ord_type=price)
  - 수수료: 0.05%
  - 최소 주문 금액: 5,000 KRW

- **매도 주문**
  - 시장가 주문 (ord_type=market)
  - 수수료: 0.05%
  - 보유 수량 전체 매도

---

## 4. 데이터베이스 저장 흐름

거래 결과가 어떻게 데이터베이스에 저장되는지 보여줍니다.

```mermaid
sequenceDiagram
    participant BackendScheduler as Backend Scheduler<br/>(core/scheduler.py)
    participant API as Backend API<br/>(POST /trades/)
    participant TradeService as TradeService<br/>(backend/services/trade.py)
    participant DB as PostgreSQL<br/>(trades 테이블)
    participant Schema as Pydantic Schema<br/>(TradeCreate)

    BackendScheduler->>Schema: TradeCreate 객체 생성
    Note over Schema: trade_id: str<br/>symbol: str<br/>side: "buy" | "sell"<br/>price: float<br/>amount: float<br/>total: float<br/>fee: float<br/>status: "completed"

    BackendScheduler->>API: POST /api/v1/trades/
    API->>API: Validation<br/>(Pydantic 자동 검증)

    alt Validation Failed
        API-->>BackendScheduler: 422 Unprocessable Entity<br/>{detail: validation_errors}
    end

    API->>TradeService: create_trade(db, trade_create)
    TradeService->>TradeService: Trade 모델 인스턴스 생성

    Note over TradeService: db_trade = Trade(<br/>  id=uuid4(),<br/>  trade_id=trade_create.trade_id,<br/>  symbol=trade_create.symbol,<br/>  side=trade_create.side,<br/>  price=trade_create.price,<br/>  amount=trade_create.amount,<br/>  total=trade_create.total,<br/>  fee=trade_create.fee,<br/>  status=trade_create.status,<br/>  created_at=datetime.now()<br/>)

    TradeService->>DB: INSERT INTO trades
    DB->>DB: Commit Transaction

    alt Database Error
        DB-->>TradeService: IntegrityError /<br/>DatabaseError
        TradeService-->>API: 500 Internal Server Error
        API-->>BackendScheduler: Error Response
    end

    DB-->>TradeService: Row Inserted
    TradeService->>TradeService: Refresh 객체<br/>(DB 생성 필드 로드)
    TradeService-->>API: Trade 객체 반환
    API->>API: TradeResponse 스키마 변환
    API-->>BackendScheduler: 201 Created<br/>TradeResponse

    BackendScheduler->>BackendScheduler: 응답 확인 및 로깅
```

### 데이터베이스 스키마

#### trades 테이블 구조

```sql
CREATE TABLE trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('buy', 'sell')),
    price DECIMAL(20, 8) NOT NULL,
    amount DECIMAL(20, 8) NOT NULL,
    total DECIMAL(20, 8) NOT NULL,
    fee DECIMAL(20, 8) NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'completed',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    INDEX idx_trades_created_at (created_at),
    INDEX idx_trades_symbol (symbol),
    INDEX idx_trades_side (side)
);
```

#### 제약 조건

- `trade_id`: Upbit API가 반환한 고유 거래 ID
- `side`: 'buy' 또는 'sell'만 허용
- `price`, `amount`, `total`: 양수 값
- `fee`: 거래 수수료 (기본값: 0)
- `status`: 'completed', 'pending', 'failed' 중 하나

### API 엔드포인트 상세

#### POST /api/v1/trades/

**Request Body (TradeCreate)**

```json
{
  "trade_id": "uuid-from-upbit",
  "symbol": "KRW-ETH",
  "side": "buy",
  "price": 3500000.0,
  "amount": 0.01,
  "total": 35000.0,
  "fee": 17.5,
  "status": "completed"
}
```

**Response (TradeResponse)**

```json
{
  "id": "uuid-generated-by-db",
  "trade_id": "uuid-from-upbit",
  "symbol": "KRW-ETH",
  "side": "buy",
  "price": 3500000.0,
  "amount": 0.01,
  "total": 35000.0,
  "fee": 17.5,
  "status": "completed",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

---

## 5. 모니터링 및 알림 흐름

거래 완료 후 메트릭 기록과 알림 전송 흐름을 보여줍니다.

```mermaid
sequenceDiagram
    participant BackendScheduler as Backend Scheduler<br/>(core/scheduler.py)
    participant MetricsService as MetricsService<br/>(backend/services/metrics.py)
    participant Prometheus as Prometheus<br/>(메트릭 저장소)
    participant NotificationService as NotificationService<br/>(backend/services/notification.py)
    participant Telegram as Telegram Bot API
    participant Grafana as Grafana<br/>(대시보드)

    Note over BackendScheduler: 거래 실행 완료 후

    par 병렬 처리: 메트릭 기록
        BackendScheduler->>MetricsService: record_trade(<br/>symbol,<br/>side,<br/>price,<br/>amount<br/>)
        MetricsService->>MetricsService: trade_counter.labels(<br/>symbol=symbol,<br/>side=side<br/>).inc()
        MetricsService->>MetricsService: trade_amount.labels(<br/>symbol=symbol<br/>).observe(amount)
        MetricsService->>MetricsService: trade_value.labels(<br/>symbol=symbol<br/>).observe(total)
        MetricsService->>Prometheus: Push Metrics<br/>(HTTP /metrics)

        BackendScheduler->>MetricsService: record_ai_decision(<br/>decision,<br/>confidence,<br/>reason<br/>)
        MetricsService->>MetricsService: ai_decision_counter.labels(<br/>decision=decision<br/>).inc()
        MetricsService->>MetricsService: ai_confidence.observe(<br/>confidence<br/>)
        MetricsService->>Prometheus: Push Metrics
    and 병렬 처리: 알림 전송
        BackendScheduler->>NotificationService: notify_trade(<br/>trade_data<br/>)
        NotificationService->>NotificationService: 메시지 포맷팅

        Note over NotificationService: 📊 거래 알림<br/>━━━━━━━━━━━━━━━<br/>🔹 종목: KRW-ETH<br/>🔹 거래: 매수 ✅<br/>🔹 가격: 3,500,000 KRW<br/>🔹 수량: 0.01 ETH<br/>🔹 총액: 35,000 KRW<br/>🔹 수수료: 17.5 KRW<br/>━━━━━━━━━━━━━━━<br/>⏰ 2024-01-15 10:30:00

        NotificationService->>Telegram: POST /sendMessage
        Telegram-->>NotificationService: Message Sent

        alt 알림 실패
            NotificationService->>NotificationService: 재시도 (최대 3회)
            alt 재시도 실패
                NotificationService->>BackendScheduler: Warning Log<br/>(알림 실패)
            end
        end
    end

    Prometheus->>Grafana: Scrape Metrics<br/>(15초마다)
    Grafana->>Grafana: 대시보드 업데이트

    Note over Grafana: 실시간 차트:<br/>- 거래 횟수<br/>- 거래 금액<br/>- AI 판단 분포<br/>- 신뢰도 추이
```

### Prometheus 메트릭 상세

#### 거래 관련 메트릭

1. **trade_counter** (Counter)

   - 라벨: `symbol`, `side`
   - 설명: 거래 실행 횟수

   ```python
   trade_counter = Counter(
       'trading_bot_trades_total',
       'Total number of trades executed',
       ['symbol', 'side']
   )
   ```

2. **trade_amount** (Histogram)

   - 라벨: `symbol`
   - 설명: 거래 수량 분포
   - 버킷: [0.001, 0.01, 0.1, 1.0, 10.0]

3. **trade_value** (Histogram)
   - 라벨: `symbol`
   - 설명: 거래 금액 분포 (KRW)
   - 버킷: [10000, 50000, 100000, 500000, 1000000]

#### AI 판단 관련 메트릭

1. **ai_decision_counter** (Counter)

   - 라벨: `decision`
   - 설명: AI 판단 분포 (buy/sell/hold)

2. **ai_confidence** (Histogram)

   - 설명: AI 신뢰도 분포 (0.0 ~ 1.0)
   - 버킷: [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

3. **trading_cycle_duration** (Histogram)
   - 설명: 거래 사이클 실행 시간 (초)

#### 시스템 메트릭

1. **upbit_api_calls** (Counter)

   - 라벨: `endpoint`, `method`
   - 설명: Upbit API 호출 횟수

2. **upbit_api_errors** (Counter)
   - 라벨: `endpoint`, `error_type`
   - 설명: Upbit API 에러 횟수

### Telegram 알림 포맷

#### 거래 성공 알림 (매수)

```
📊 거래 알림
━━━━━━━━━━━━━━━
🔹 종목: KRW-ETH
🔹 거래: 매수 ✅
🔹 가격: 3,500,000 KRW
🔹 수량: 0.01 ETH
🔹 총액: 35,000 KRW
🔹 수수료: 17.5 KRW
━━━━━━━━━━━━━━━
💡 AI 판단
  - 결정: BUY
  - 신뢰도: 0.85
  - 이유: RSI 과매도 구간 진입, MACD 골든크로스 형성
━━━━━━━━━━━━━━━
⏰ 2024-01-15 10:30:00
```

#### 거래 성공 알림 (매도)

```
📊 거래 알림
━━━━━━━━━━━━━━━
🔹 종목: KRW-ETH
🔹 거래: 매도 ✅
🔹 가격: 3,600,000 KRW
🔹 수량: 0.01 ETH
🔹 총액: 36,000 KRW
🔹 수수료: 18.0 KRW
━━━━━━━━━━━━━━━
💰 수익 정보
  - 매수가: 3,500,000 KRW
  - 수익: +100,000 KRW (+2.86%)
━━━━━━━━━━━━━━━
💡 AI 판단
  - 결정: SELL
  - 신뢰도: 0.90
  - 이유: 목표가 도달, RSI 과매수 구간
━━━━━━━━━━━━━━━
⏰ 2024-01-15 14:30:00
```

#### 거래 보류 알림 (Hold)

```
⏸️ 거래 보류
━━━━━━━━━━━━━━━
🔹 종목: KRW-ETH
🔹 결정: HOLD
━━━━━━━━━━━━━━━
💡 AI 판단
  - 신뢰도: 0.65
  - 이유: 시장 변동성 높음, 관망 필요
━━━━━━━━━━━━━━━
⏰ 2024-01-15 11:30:00
```

#### 에러 알림

```
🚨 거래 에러
━━━━━━━━━━━━━━━
🔹 종목: KRW-ETH
🔹 에러: API 호출 실패
━━━━━━━━━━━━━━━
📝 상세 정보
  - 에러 코드: 429
  - 메시지: Too Many Requests
  - 재시도: 3/3 실패
━━━━━━━━━━━━━━━
⚠️ 시스템 관리자에게 문의하세요.
⏰ 2024-01-15 12:30:00
```

---

## 6. 에러 처리 흐름

시스템의 에러 처리 및 복구 메커니즘을 보여줍니다.

```mermaid
sequenceDiagram
    participant Scheduler as Scheduler<br/>(any module)
    participant ErrorHandler as ErrorHandler<br/>(예외 처리)
    participant Logger as Logger<br/>(logs/)
    participant Metrics as Prometheus<br/>(error_counter)
    participant Telegram as Telegram<br/>(에러 알림)
    participant Retry as Retry Logic<br/>(재시도)

    Scheduler->>Scheduler: 거래 작업 실행

    alt Upbit API Error
        Scheduler->>ErrorHandler: UpbitAPIException
        ErrorHandler->>Logger: ERROR 로그 기록<br/>(api_call.log)
        ErrorHandler->>Metrics: upbit_api_errors.inc(<br/>error_type='rate_limit'<br/>)

        alt Retryable Error (429, 503)
            ErrorHandler->>Retry: exponential_backoff()
            Retry->>Retry: wait(2^attempt seconds)
            Retry->>Scheduler: 재시도 (최대 3회)

            alt 재시도 성공
                Scheduler->>Logger: INFO: 재시도 성공
            else 재시도 실패
                ErrorHandler->>Telegram: 에러 알림 전송
                ErrorHandler->>Scheduler: raise Exception
            end
        else Non-Retryable Error (400, 401)
            ErrorHandler->>Telegram: 긴급 알림 전송
            ErrorHandler->>Scheduler: raise Exception
        end

    else Database Error
        Scheduler->>ErrorHandler: DatabaseException
        ErrorHandler->>Logger: ERROR 로그 기록<br/>(database.log)
        ErrorHandler->>Metrics: db_errors.inc()

        alt Connection Error
            ErrorHandler->>Retry: reconnect()
            Retry->>Retry: wait(5 seconds)
            Retry->>Scheduler: 재연결 시도
        else Integrity Error
            ErrorHandler->>Logger: CRITICAL: 데이터 무결성 오류
            ErrorHandler->>Telegram: 긴급 알림
            ErrorHandler->>Scheduler: raise Exception
        end

    else AI Service Error
        Scheduler->>ErrorHandler: AIServiceException
        ErrorHandler->>Logger: WARNING 로그 기록
        ErrorHandler->>Metrics: ai_errors.inc()

        alt GPT API Timeout
            ErrorHandler->>Retry: retry_with_timeout()
            Retry->>Scheduler: 타임아웃 연장 재시도
        else GPT API Rate Limit
            ErrorHandler->>Scheduler: fallback_decision()<br/>(규칙 기반 판단)
            ErrorHandler->>Telegram: AI 서비스 다운 알림
        end

    else Network Error
        Scheduler->>ErrorHandler: NetworkException
        ErrorHandler->>Logger: ERROR 로그 기록
        ErrorHandler->>Metrics: network_errors.inc()
        ErrorHandler->>Retry: exponential_backoff()
        Retry->>Scheduler: 재시도

    else Unknown Error
        Scheduler->>ErrorHandler: Exception
        ErrorHandler->>Logger: CRITICAL 로그 기록<br/>(전체 스택 트레이스)
        ErrorHandler->>Metrics: unknown_errors.inc()
        ErrorHandler->>Telegram: 긴급 알림 전송<br/>(관리자 호출)
        ErrorHandler->>Scheduler: 안전 모드 전환<br/>(거래 중단)
    end
```

### 에러 유형별 처리 전략

#### 1. Upbit API 에러

| 에러 코드 | 설명        | 재시도   | 알림        | 조치                |
| --------- | ----------- | -------- | ----------- | ------------------- |
| 400       | 잘못된 요청 | ❌       | 즉시        | 요청 파라미터 검증  |
| 401       | 인증 실패   | ❌       | 긴급        | API 키 재확인       |
| 429       | Rate Limit  | ✅ (3회) | 3회 실패 시 | Exponential Backoff |
| 500       | 서버 에러   | ✅ (3회) | 3회 실패 시 | 재시도 후 보고      |
| 503       | 서비스 불가 | ✅ (5회) | 5회 실패 시 | 장기 재시도         |

**재시도 전략**

```python
def exponential_backoff(attempt: int) -> float:
    """지수 백오프 계산"""
    return min(2 ** attempt, 60)  # 최대 60초

# 예시: 1초 -> 2초 -> 4초 -> 8초 -> 16초 -> 32초 -> 60초
```

#### 2. 데이터베이스 에러

| 에러 유형        | 설명          | 재시도   | 알림        | 조치             |
| ---------------- | ------------- | -------- | ----------- | ---------------- |
| Connection Error | DB 연결 실패  | ✅ (5회) | 3회 실패 시 | 재연결 시도      |
| Timeout          | 쿼리 타임아웃 | ✅ (3회) | 즉시        | 쿼리 최적화 검토 |
| Integrity Error  | 데이터 무결성 | ❌       | 긴급        | 데이터 검증      |
| Deadlock         | 교착 상태     | ✅ (3회) | -           | 트랜잭션 재시도  |

**재연결 로직**

```python
async def reconnect_db(max_attempts=5):
    for attempt in range(max_attempts):
        try:
            await db.connect()
            return True
        except ConnectionError:
            await asyncio.sleep(5 * (attempt + 1))
    return False
```

#### 3. AI 서비스 에러

| 에러 유형        | 설명             | 재시도   | 알림 | Fallback       |
| ---------------- | ---------------- | -------- | ---- | -------------- |
| Timeout          | GPT API 타임아웃 | ✅ (2회) | -    | 규칙 기반 판단 |
| Rate Limit       | API 한도 초과    | ✅ (3회) | 즉시 | 규칙 기반 판단 |
| Invalid Response | 응답 파싱 실패   | ✅ (1회) | -    | 재요청         |
| Service Down     | 서비스 불가      | ❌       | 긴급 | 규칙 기반 판단 |

**Fallback 전략**

```python
def fallback_decision(chart_data, position):
    """AI 서비스 다운 시 규칙 기반 판단"""
    rsi = calculate_rsi(chart_data)

    if rsi < 30 and position.cash > 10000:
        return Decision(action='buy', confidence=0.6, reason='RSI oversold')
    elif rsi > 70 and position.crypto > 0:
        return Decision(action='sell', confidence=0.6, reason='RSI overbought')
    else:
        return Decision(action='hold', confidence=0.5, reason='No clear signal')
```

#### 4. 네트워크 에러

| 에러 유형          | 설명          | 재시도   | 알림        | 조치                |
| ------------------ | ------------- | -------- | ----------- | ------------------- |
| Connection Timeout | 연결 타임아웃 | ✅ (3회) | 3회 실패 시 | Exponential Backoff |
| Read Timeout       | 읽기 타임아웃 | ✅ (3회) | 3회 실패 시 | 타임아웃 연장       |
| DNS Error          | DNS 해석 실패 | ✅ (2회) | 즉시        | DNS 설정 확인       |
| SSL Error          | SSL 인증 실패 | ❌       | 긴급        | 인증서 확인         |

### 로깅 전략

#### 로그 레벨별 기록

1. **DEBUG**: 상세한 디버깅 정보

   ```
   [DEBUG] Chart data collected: 200 candles, last_price=3500000
   ```

2. **INFO**: 일반 작업 정보

   ```
   [INFO] Trading cycle started at 2024-01-15 10:00:00
   [INFO] AI decision: BUY, confidence=0.85
   ```

3. **WARNING**: 경고 (작업은 계속)

   ```
   [WARNING] AI service timeout, using fallback decision
   [WARNING] Telegram notification failed (1/3)
   ```

4. **ERROR**: 에러 (재시도 가능)

   ```
   [ERROR] Upbit API error: 429 Too Many Requests
   [ERROR] Database connection failed (attempt 2/5)
   ```

5. **CRITICAL**: 치명적 에러 (시스템 중단)
   ```
   [CRITICAL] Database integrity error: duplicate trade_id
   [CRITICAL] Unknown exception: {full_stack_trace}
   ```

#### 로그 파일 구조

```
logs/
├── scheduler/
│   └── scheduler.log          # 스케줄러 로그
├── trading/
│   ├── trading.log            # 거래 실행 로그
│   └── api_call.log           # API 호출 로그
├── database/
│   └── database.log           # DB 관련 로그
└── errors/
    └── errors.log             # 에러 전용 로그
```

### 안전 모드 (Safe Mode)

치명적 에러 발생 시 시스템은 안전 모드로 전환됩니다.

#### 안전 모드 트리거 조건

1. 연속 3회 거래 실패
2. 데이터 무결성 오류
3. API 키 인증 실패
4. 알 수 없는 치명적 에러

#### 안전 모드 동작

```python
class SafeMode:
    def __init__(self):
        self.enabled = False
        self.trigger_time = None
        self.reason = None

    def enable(self, reason: str):
        self.enabled = True
        self.trigger_time = datetime.now()
        self.reason = reason

        # 모든 거래 중단
        # 관리자에게 긴급 알림
        # 로그 기록
        logger.critical(f"Safe mode enabled: {reason}")
        notify_admin_urgent(f"🚨 안전 모드 활성화\n이유: {reason}")

    def can_trade(self) -> bool:
        return not self.enabled
```

---

## 7. 부록: 주요 설정 값

### 환경 변수 (.env)

```bash
# Upbit API
UPBIT_ACCESS_KEY=your_access_key
UPBIT_SECRET_KEY=your_secret_key

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/trading_bot

# AI Service
OPENAI_API_KEY=your_openai_api_key
GPT_MODEL=gpt-4-turbo-preview

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Trading Settings
TRADING_SYMBOL=KRW-ETH
TRADING_AMOUNT=10000              # 매수 금액 (KRW)
MAX_POSITION_SIZE=0.1             # 최대 포지션 크기 (ETH)
STOP_LOSS_PERCENT=5               # 손절 비율 (%)
TAKE_PROFIT_PERCENT=10            # 익절 비율 (%)

# Backtest Settings
BACKTEST_MIN_WIN_RATE=50          # 최소 승률 (%)
BACKTEST_MAX_MDD=-10              # 최대 MDD (%)
BACKTEST_MIN_SHARPE=0.5           # 최소 샤프 비율

# Monitoring
PROMETHEUS_PORT=9090
GRAFANA_PORT=3001

# Logging
LOG_LEVEL=INFO
LOG_FILE_MAX_BYTES=10485760       # 10MB
LOG_FILE_BACKUP_COUNT=5
```

### 주요 타임아웃 설정

```python
# API 호출 타임아웃
UPBIT_API_TIMEOUT = 10            # 10초
GPT_API_TIMEOUT = 30              # 30초
DATABASE_QUERY_TIMEOUT = 5        # 5초

# 재시도 설정
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY_BASE = 2              # 2초 (exponential)

# 거래 제한
MIN_ORDER_AMOUNT = 5000           # 5,000 KRW
MAX_ORDER_AMOUNT = 1000000        # 1,000,000 KRW
ORDER_FEE_RATE = 0.0005           # 0.05%
```

---

## 8. 참고 문서

- [시스템 아키텍처](./ARCHITECTURE.md)
- [Docker 설정 가이드](./DOCKER_GUIDE.md)
- [모니터링 가이드](./MONITORING_GUIDE.md)
- [데이터베이스 상태 리포트](./reports/DATABASE_STATUS_REPORT.md)
- [백엔드 API 문서](../backend/tests/README.md)

---

**작성일**: 2024-12-28  
**버전**: 1.0.0  
**작성자**: Bitcoin Trading Bot Team
