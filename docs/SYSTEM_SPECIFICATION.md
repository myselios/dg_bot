# 🤖 AI 자동매매 시스템 기능명세서

> 전체 시스템 아키텍처 및 모듈별 상세 기능 명세

**최종 업데이트**: 2025-12-28  
**버전**: 2.0  
**상태**: ✅ 프로덕션 운영 중

---

## 📋 목차

1. [시스템 개요](#-시스템-개요)
2. [아키텍처](#-아키텍처)
3. [주요 모듈](#-주요-모듈)
4. [실행 흐름](#-실행-흐름)
5. [데이터 흐름](#-데이터-흐름)
6. [모니터링 시스템](#-모니터링-시스템)
7. [배포 구조](#-배포-구조)

---

## 🎯 시스템 개요

### 핵심 기능

AI 기반 암호화폐 자동매매 시스템으로, 업비트 거래소에서 ETH/BTC를 대상으로 1시간 주기로 자동 거래를 수행합니다.

**주요 특징:**
- 🤖 **AI 기반 의사결정** - OpenAI GPT-4를 활용한 시장 분석
- ⏰ **완전 자동화** - 1시간 주기 무인 거래 실행
- 📊 **실시간 모니터링** - Prometheus + Grafana 대시보드
- 🔔 **즉시 알림** - Telegram을 통한 거래/에러 알림
- 🛡️ **리스크 관리** - 백테스팅 필터 + 환경 안전성 체크
- 💾 **데이터 기록** - PostgreSQL 거래 이력 저장

### 거래 전략

1. **빠른 백테스팅 필터링**
   - 로컬 1년치 데이터 사용
   - 룰 기반 돌파 전략 검증
   - 승률 55% 이상, 최대 손실 -30% 이하만 통과

2. **AI 심화 분석**
   - 차트 데이터 (일봉/시간봉/분봉)
   - 기술적 지표 (RSI, MACD, 볼린저밴드 등)
   - 오더북 분석
   - 공포탐욕지수
   - BTC 시장 상관관계

3. **안전성 검증**
   - BTC 시장 리스크 체크
   - 플래시 크래시 감지
   - RSI 다이버전스 확인

---

## 🏗 아키텍처

### 전체 시스템 구조

```
┌─────────────────────────────────────────────────────────────────────┐
│                        사용자 / 운영자                                │
└─────────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────┼───────────┐
                    │           │           │
            ┌───────▼───┐  ┌────▼─────┐  ┌─▼──────────┐
            │  Grafana  │  │ Telegram │  │  Frontend  │
            │ (대시보드) │  │  (알림)   │  │   (UI)     │
            │   :3001   │  │          │  │   :3000    │
            └───────┬───┘  └──────────┘  └────────────┘
                    │
            ┌───────▼──────────────────────────────────┐
            │          Prometheus (메트릭 수집)          │
            │              :9090                        │
            └───────┬──────────────────────────────────┘
                    │
    ┌───────────────┼───────────────┐
    │               │               │
┌───▼────┐  ┌──────▼───────┐  ┌───▼──────┐
│Backend │  │  Scheduler   │  │PostgreSQL│
│ (API)  │  │ (자동거래)    │  │   (DB)   │
│ :8000  │  │              │  │  :5432   │
└───┬────┘  └──────┬───────┘  └────┬─────┘
    │              │               │
    └──────────────┼───────────────┘
                   │
           ┌───────▼────────┐
           │   main.py      │
           │ (거래 로직)     │
           └───────┬────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───▼────┐  ┌─────▼─────┐  ┌─────▼──────┐
│ Upbit  │  │ OpenAI    │  │ Alternative│
│  API   │  │  GPT-4    │  │    .me     │
└────────┘  └───────────┘  └────────────┘
```

### 레이어 구조

```
┌─────────────────────────────────────────────┐
│          Presentation Layer                  │
│  (Grafana, Telegram, Frontend)              │
└─────────────────────────────────────────────┘
                    ↕
┌─────────────────────────────────────────────┐
│          Application Layer                   │
│  (Backend API, Scheduler)                   │
└─────────────────────────────────────────────┘
                    ↕
┌─────────────────────────────────────────────┐
│          Business Logic Layer                │
│  (Trading Engine, AI Service)               │
└─────────────────────────────────────────────┘
                    ↕
┌─────────────────────────────────────────────┐
│          Data Layer                          │
│  (PostgreSQL, Prometheus)                   │
└─────────────────────────────────────────────┘
                    ↕
┌─────────────────────────────────────────────┐
│          External Services                   │
│  (Upbit API, OpenAI API)                    │
└─────────────────────────────────────────────┘
```

---

## 📦 주요 모듈

### 1. Main 모듈 (`main.py`)

**역할**: 핵심 거래 로직 실행

**위치**: `main.py`

**주요 함수**:

#### `execute_trading_cycle()`

**목적**: 한 번의 완전한 거래 사이클 실행

**입력**:
```python
ticker: str                      # 거래 종목 (예: "KRW-ETH")
upbit_client: UpbitClient       # Upbit API 클라이언트
data_collector: DataCollector    # 데이터 수집기
trading_service: TradingService  # 거래 서비스
ai_service: AIService           # AI 분석 서비스
```

**출력**:
```python
{
    'status': 'success' | 'failed',
    'decision': 'buy' | 'sell' | 'hold',
    'confidence': 'high' | 'medium' | 'low',
    'reason': str,
    'price': float,
    'amount': float,
    'total': float
}
```

**실행 단계**:

```
1. 투자 상태 조회
   └─> upbit_client.get_balances()
   └─> 보유 현금 및 코인 잔고 확인

2. 데이터 수집
   ├─> 오더북 정보 (data_collector.get_orderbook)
   ├─> ETH 차트 데이터 (일봉/시간봉/분봉)
   └─> BTC 차트 데이터 (Phase 2)

3. 시장 분석
   ├─> BTC-ETH 상관관계 (calculate_market_risk)
   ├─> 플래시 크래시 감지 (detect_flash_crash)
   └─> RSI 다이버전스 (detect_rsi_divergence)

4. 백테스팅 필터
   └─> QuickBacktestFilter.run_quick_backtest()
       ├─> 로컬 1년치 데이터 로드
       ├─> 룰 기반 전략 시뮬레이션
       └─> 승률/손실률 체크
       
5. 필터링 통과 시 AI 분석
   ├─> ai_service.prepare_analysis_data()
   └─> ai_service.analyze() (OpenAI GPT-4 호출)
       ├─> 프롬프트 생성 (차트 + 지표 + 오더북)
       └─> AI 판단 (buy/sell/hold)

6. 거래 실행
   ├─> decision == 'buy' → trading_service.execute_buy()
   ├─> decision == 'sell' → trading_service.execute_sell()
   └─> decision == 'hold' → trading_service.execute_hold()

7. 결과 반환
   └─> 거래 결과 딕셔너리
```

#### `main()` (비동기)

**목적**: 단독 실행용 메인 함수

**동작**:
1. 서비스 초기화 (UpbitClient, DataCollector, etc.)
2. `execute_trading_cycle()` 호출
3. 결과 출력 및 로깅
4. 최종 잔고 출력

**사용 예**:
```bash
# 단독 실행 (1회 거래 사이클)
python main.py
```

---

### 2. Scheduler 모듈

#### 2.1. `scheduler_main.py`

**역할**: 스케줄러 전용 실행 파일 (24/7 실행)

**위치**: `scheduler_main.py` (프로젝트 루트)

**주요 함수**:

##### `main()` (비동기)

**목적**: 스케줄러 초기화 및 무한 루프 유지

**실행 순서**:

```
1. 프로그램 시작 배너 출력
   └─> 시작 시각, 실행 주기 표시

2. 데이터베이스 초기화
   └─> init_db() 호출 (테이블 생성)

3. 봇 상태 업데이트
   ├─> set_bot_running(True) → Prometheus 메트릭
   └─> notify_bot_status("started") → Telegram 알림

4. 스케줄러 시작
   └─> start_scheduler() 호출
       └─> APScheduler 초기화
       └─> 작업 등록 (trading_job, portfolio_snapshot_job, daily_report_job)

5. 등록된 작업 확인
   └─> get_jobs() → 작업 목록 출력

6. 무한 루프 (유지)
   └─> while not killer.kill_now:
       └─> await asyncio.sleep(10)  # 10초마다 상태 체크

7. 종료 시그널 수신 (Ctrl+C)
   ├─> set_bot_running(False)
   ├─> notify_bot_status("stopped") → Telegram
   ├─> stop_scheduler()
   └─> 안전 종료
```

**실행 방법**:
```bash
# 로컬 실행
python scheduler_main.py

# Docker 실행
docker-compose -f docker-compose.full-stack.yml up -d scheduler
```

**Graceful Shutdown**:
- SIGINT (Ctrl+C) / SIGTERM 시그널 처리
- 스케줄러 안전 종료
- Telegram 종료 알림 전송

---

#### 2.2. `backend/app/core/scheduler.py`

**역할**: APScheduler 설정 및 작업 정의

**위치**: `backend/app/core/scheduler.py`

**주요 컴포넌트**:

##### APScheduler 인스턴스

```python
scheduler = AsyncIOScheduler(
    timezone="Asia/Seoul",
    job_defaults={
        "coalesce": True,         # 누락된 작업 병합
        "max_instances": 1,        # 동시 실행 방지
        "misfire_grace_time": 60,  # 지연 허용 시간 (초)
    }
)
```

##### 작업 1: `trading_job()` (비동기)

**목적**: 주기적 트레이딩 작업 (1시간마다)

**실행 주기**: `IntervalTrigger(minutes=60)` (1시간)

**동작**:

```
1. 서비스 초기화
   ├─> UpbitClient()
   ├─> DataCollector()
   ├─> TradingService()
   └─> AIService()

2. 거래 사이클 실행
   └─> await execute_trading_cycle(...)
       └─> main.py의 함수 호출

3. 결과 처리
   ├─> 성공 시
   │   ├─> record_ai_decision() → Prometheus 메트릭
   │   ├─> notify_trade() → Telegram 알림 (매수/매도만)
   │   └─> scheduler_job_success_total.inc()
   │
   └─> 실패 시
       ├─> notify_error() → Telegram 에러 알림
       ├─> sentry_sdk.capture_exception() → Sentry 전송
       └─> scheduler_job_failure_total.inc()

4. 실행 시간 기록
   └─> scheduler_job_duration_seconds.observe(duration)
```

**메트릭 수집**:
- `scheduler_job_success_total`: 성공 횟수
- `scheduler_job_failure_total`: 실패 횟수
- `scheduler_job_duration_seconds`: 실행 시간
- `ai_decision_total`: AI 판단 통계

---

##### 작업 2: `portfolio_snapshot_job()` (비동기)

**목적**: 포트폴리오 스냅샷 저장 (1시간마다)

**실행 주기**: `IntervalTrigger(hours=1)`

**동작**:
```
1. 현재 포트폴리오 조회
   ├─> upbit_client.get_balances()
   └─> 현재 가격 조회

2. 스냅샷 저장 (DB)
   └─> save_portfolio_snapshot()
       └─> PostgreSQL INSERT

3. 메트릭 업데이트
   └─> portfolio_value_krw.set(total_value)
```

**TODO**: DB 연동 필요

---

##### 작업 3: `daily_report_job()` (비동기)

**목적**: 일일 리포트 전송 (매일 오전 9시)

**실행 주기**: `CronTrigger(hour=9, minute=0, timezone="Asia/Seoul")`

**동작**:

```
1. 전날 통계 조회 (DB)
   ├─> 총 거래 횟수
   ├─> 수익/손실 금액
   └─> 수익률

2. Telegram 리포트 전송
   └─> notify_daily_report(
       total_trades=24,
       profit_loss=15000,
       profit_rate=1.5,
       current_value=1015000
   )

3. 에러 처리
   └─> Sentry + Telegram 에러 알림
```

**TODO**: DB 통계 조회 구현 필요 (현재는 임시 데이터)

---

##### 스케줄러 제어 함수

```python
def start_scheduler():
    """스케줄러 시작"""
    add_jobs()           # 작업 등록
    scheduler.start()    # 스케줄러 시작

def stop_scheduler():
    """스케줄러 중지"""
    scheduler.shutdown(wait=True)  # 안전 종료

def pause_job(job_id: str):
    """특정 작업 일시 정지"""
    scheduler.pause_job(job_id)

def resume_job(job_id: str):
    """특정 작업 재개"""
    scheduler.resume_job(job_id)

def get_jobs():
    """현재 등록된 작업 조회"""
    return scheduler.get_jobs()
```

---

### 3. Backend API 모듈

**역할**: REST API 제공 및 웹 인터페이스

**위치**: `backend/app/`

**기술 스택**: FastAPI + SQLAlchemy + PostgreSQL

#### 주요 엔드포인트

##### 3.1. 봇 제어 API

```
GET  /api/bot/status          # 봇 상태 조회
POST /api/bot/start           # 봇 시작
POST /api/bot/stop            # 봇 중지
POST /api/bot/pause           # 봇 일시정지
POST /api/bot/resume          # 봇 재개
```

**예시**:
```bash
# 봇 상태 조회
curl http://localhost:8000/api/bot/status

# 응답
{
  "status": "running",
  "uptime_seconds": 3600,
  "last_trade_time": "2025-12-28T14:00:00",
  "jobs": [
    {"id": "trading_job", "next_run": "2025-12-28T15:00:00"}
  ]
}
```

##### 3.2. 거래 이력 API

```
GET /api/trades               # 거래 이력 조회
GET /api/trades/{trade_id}    # 특정 거래 상세
GET /api/trades/stats         # 거래 통계
```

**예시**:
```bash
# 최근 10개 거래 조회
curl http://localhost:8000/api/trades?limit=10

# 응답
{
  "trades": [
    {
      "id": 1,
      "symbol": "KRW-ETH",
      "side": "buy",
      "price": 4350000,
      "amount": 0.0115,
      "total": 50000,
      "created_at": "2025-12-28T14:00:00"
    }
  ],
  "total": 125
}
```

##### 3.3. 메트릭 API

```
GET /metrics                  # Prometheus 메트릭 엔드포인트
GET /health                   # 헬스 체크
```

**예시**:
```bash
# 메트릭 조회 (Prometheus 포맷)
curl http://localhost:8000/metrics

# 출력 (Prometheus 텍스트 포맷)
# HELP scheduler_job_success_total 스케줄러 작업 성공 횟수
# TYPE scheduler_job_success_total counter
scheduler_job_success_total{job_name="trading_job"} 120.0

# HELP ai_decision_total AI 판단 횟수
# TYPE ai_decision_total counter
ai_decision_total{symbol="KRW-ETH",decision="buy"} 45.0
ai_decision_total{symbol="KRW-ETH",decision="sell"} 38.0
ai_decision_total{symbol="KRW-ETH",decision="hold"} 37.0
```

---

### 4. 모니터링 시스템

#### 4.1. Prometheus

**역할**: 메트릭 수집 및 저장

**위치**: Docker 컨테이너 (`prometheus:9090`)

**설정 파일**: `monitoring/prometheus.yml`

**수집 주기**: 10초 (`scrape_interval: 10s`)

**수집 대상**:

```yaml
scrape_configs:
  - job_name: 'backend'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/metrics'
    scrape_interval: 10s
  
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']
```

**저장소**: 시계열 데이터베이스 (TSDB)
- 보관 기간: 15일
- 압축: 자동 (블록 단위)
- 디스크 사용량: ~1GB

**Alert 규칙 평가**: 10초마다 (`evaluation_interval: 10s`)

---

#### 4.2. Grafana

**역할**: 대시보드 시각화

**위치**: Docker 컨테이너 (`grafana:3001`)

**데이터소스**: Prometheus (`http://prometheus:9090`)

**대시보드**: "AI Trading Bot - 실시간 모니터링"

**패널 구성** (10개):

| 패널 번호 | 패널 이름 | 타입 | 메트릭 |
|----------|----------|------|--------|
| 1 | 스케줄러 작업 성공/실패 | Pie Chart | `scheduler_job_success_total`, `scheduler_job_failure_total` |
| 2 | 작업 실행 시간 추이 | Time Series | `scheduler_job_duration_seconds` |
| 3 | AI 판단 분포 | Donut Chart | `sum by (decision) (ai_decision_total)` |
| 4 | AI 판단 추이 | Time Series | `rate(ai_decision_total[5m])` |
| 5 | Backend 상태 | Stat | `up{job="backend"}` |
| 6 | 총 에러 건수 | Stat | `sum(bot_errors_total)` |
| 7 | API 응답 시간 (p95) | Stat | `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))` |
| 8 | 총 거래 횟수 | Stat | `sum(trades_total)` |
| 9 | 포트폴리오 가치 추이 | Time Series | `portfolio_value_krw` |
| 10 | 시간별 성공/실패 | Time Series | `increase(scheduler_job_success_total[1h])` |

**자동 새로고침**: 30초

---

#### 4.3. Telegram Bot

**역할**: 실시간 알림 전송

**구현**: `backend/app/services/notification.py`

**알림 함수**:

##### `notify_trade()` (비동기)

```python
async def notify_trade(
    symbol: str,
    side: str,          # "buy" | "sell"
    price: float,
    amount: float,
    total: float,
    reason: str
):
    """거래 실행 알림"""
```

**메시지 포맷**:
```
🤖 거래 실행
━━━━━━━━━━━━━━━━━━━━
종목: KRW-ETH
거래: 매수 (BUY)
가격: 4,350,000원
수량: 0.0115 ETH
총액: 50,000원
판단 근거: RSI 과매도 구간 진입
━━━━━━━━━━━━━━━━━━━━
시각: 2025-12-28 14:00:15
```

##### `notify_error()` (비동기)

```python
async def notify_error(
    error_type: str,
    error_message: str,
    context: dict
):
    """에러 발생 알림"""
```

##### `notify_bot_status()` (비동기)

```python
async def notify_bot_status(
    status: str,       # "started" | "stopped"
    message: str
):
    """봇 상태 변경 알림"""
```

##### `notify_daily_report()` (비동기)

```python
async def notify_daily_report(
    total_trades: int,
    profit_loss: Decimal,
    profit_rate: Decimal,
    current_value: Decimal
):
    """일일 리포트 알림 (매일 09:00)"""
```

---

### 5. 데이터베이스 모듈

**역할**: 거래 이력 및 통계 저장

**위치**: Docker 컨테이너 (`postgres:5432`)

**DBMS**: PostgreSQL 15

#### 데이터베이스 스키마

##### Table: `trades`

```sql
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,           -- 거래 종목 (예: "KRW-ETH")
    side VARCHAR(10) NOT NULL,             -- buy | sell
    price DECIMAL(20, 8) NOT NULL,         -- 체결 가격
    amount DECIMAL(20, 8) NOT NULL,        -- 수량
    total_krw DECIMAL(20, 2) NOT NULL,     -- 총액 (KRW)
    fee DECIMAL(20, 2),                    -- 수수료
    ai_decision TEXT,                      -- AI 판단 근거
    ai_confidence VARCHAR(10),             -- high | medium | low
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 인덱스
CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_created_at ON trades(created_at);
```

##### Table: `portfolio_snapshots`

```sql
CREATE TABLE portfolio_snapshots (
    id SERIAL PRIMARY KEY,
    krw_balance DECIMAL(20, 2) NOT NULL,   -- 보유 현금
    coin_balance DECIMAL(20, 8) NOT NULL,  -- 보유 코인
    coin_price DECIMAL(20, 2) NOT NULL,    -- 코인 현재가
    total_value_krw DECIMAL(20, 2) NOT NULL, -- 총 자산 가치
    created_at TIMESTAMP DEFAULT NOW()
);

-- 인덱스
CREATE INDEX idx_snapshots_created_at ON portfolio_snapshots(created_at);
```

##### Table: `bot_status`

```sql
CREATE TABLE bot_status (
    id SERIAL PRIMARY KEY,
    status VARCHAR(20) NOT NULL,           -- running | stopped | paused
    last_trade_time TIMESTAMP,
    total_trades INT DEFAULT 0,
    uptime_seconds BIGINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## 🔄 실행 흐름

### 1. 스케줄러 자동 실행 모드 (프로덕션)

```
1. 시스템 시작
   └─> docker-compose -f docker-compose.full-stack.yml up -d
       ├─> PostgreSQL 시작
       ├─> Backend API 시작 (:8000)
       ├─> Scheduler 시작 (scheduler_main.py)
       ├─> Prometheus 시작 (:9090)
       ├─> Grafana 시작 (:3001)
       └─> PostgreSQL Exporter 시작 (:9187)

2. Scheduler 초기화
   └─> scheduler_main.py
       ├─> APScheduler 초기화 (Asia/Seoul)
       ├─> 작업 등록
       │   ├─> trading_job (1시간마다)
       │   ├─> portfolio_snapshot_job (1시간마다)
       │   └─> daily_report_job (매일 09:00)
       ├─> Telegram 시작 알림
       └─> 무한 루프 (10초마다 상태 체크)

3. 정각마다 trading_job 실행
   └─> backend/app/core/scheduler.py::trading_job()
       └─> main.py::execute_trading_cycle()
           ├─> 데이터 수집 (Upbit API)
           ├─> 백테스팅 필터
           ├─> AI 분석 (OpenAI API)
           ├─> 거래 실행
           └─> 결과 반환
       ├─> Telegram 알림 전송 (매수/매도만)
       ├─> Prometheus 메트릭 기록
       └─> DB 저장 (TODO)

4. Prometheus 메트릭 수집
   └─> 10초마다 scrape
       ├─> http://backend:8000/metrics
       └─> http://postgres-exporter:9187/metrics

5. Grafana 대시보드 업데이트
   └─> 30초마다 자동 새로고침
       └─> Prometheus 쿼리 실행
           └─> 패널 데이터 업데이트

6. Alert 규칙 평가
   └─> Prometheus (10초마다)
       ├─> 조건 충족 시 Alert 발생
       └─> http://localhost:9090/alerts에서 확인

7. 사용자 모니터링
   └─> Grafana 대시보드 접속 (:3001)
   └─> Telegram 알림 수신
```

---

### 2. 수동 실행 모드 (개발/테스트)

```bash
# 단독 실행 (1회 거래)
python main.py

# 실행 흐름
1. main() 함수 호출
   └─> 서비스 초기화
       ├─> UpbitClient()
       ├─> DataCollector()
       ├─> TradingService()
       └─> AIService()

2. execute_trading_cycle() 호출
   └─> (위와 동일한 거래 로직)

3. 결과 출력
   └─> Logger.print_success() / Logger.print_error()

4. 최종 잔고 출력
   └─> print_final_balance()

5. 프로그램 종료
```

---

## 📊 데이터 흐름

### 1. 거래 데이터 흐름

```
┌──────────────┐
│  Upbit API   │
└──────┬───────┘
       │ 1. 차트 데이터 요청
       ▼
┌──────────────────┐
│ DataCollector    │
│ (data_collector) │
└──────┬───────────┘
       │ 2. 데이터 전처리
       ▼
┌──────────────────┐
│  AIService       │
│ (ai_service)     │
└──────┬───────────┘
       │ 3. AI 분석 요청
       ▼
┌──────────────────┐
│  OpenAI API      │
│  (GPT-4)         │
└──────┬───────────┘
       │ 4. 판단 결과 (buy/sell/hold)
       ▼
┌──────────────────┐
│ TradingService   │
│(trading_service) │
└──────┬───────────┘
       │ 5. 거래 실행
       ▼
┌──────────────────┐
│  Upbit API       │
│  (주문 체결)      │
└──────┬───────────┘
       │ 6. 체결 결과
       ▼
┌──────────────────────────────┐
│         결과 처리              │
├──────────────────────────────┤
│ • PostgreSQL (DB 저장)        │
│ • Prometheus (메트릭 기록)     │
│ • Telegram (알림 전송)        │
└──────────────────────────────┘
```

---

### 2. 메트릭 데이터 흐름

```
┌──────────────────────────────────────┐
│         Application Layer             │
│  (Backend, Scheduler)                │
└──────────────┬───────────────────────┘
               │ 메트릭 생성
               │ (prometheus_client)
               ▼
┌──────────────────────────────────────┐
│      /metrics 엔드포인트              │
│  (Prometheus 텍스트 포맷)             │
└──────────────┬───────────────────────┘
               │ 10초마다 scrape
               ▼
┌──────────────────────────────────────┐
│         Prometheus TSDB              │
│  (시계열 데이터베이스)                 │
└──────────────┬───────────────────────┘
               │ PromQL 쿼리
               ▼
┌──────────────────────────────────────┐
│          Grafana                     │
│  (시각화 대시보드)                     │
└──────────────────────────────────────┘
```

**메트릭 생성 예시**:

```python
# backend/app/services/metrics.py

from prometheus_client import Counter, Gauge, Histogram

# 카운터 메트릭
ai_decision_total = Counter(
    'ai_decision_total',
    'AI 판단 횟수',
    ['symbol', 'decision']
)

# 게이지 메트릭
portfolio_value_krw = Gauge(
    'portfolio_value_krw',
    '포트폴리오 가치 (KRW)'
)

# 히스토그램 메트릭
http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP 요청 소요 시간',
    ['method', 'endpoint']
)

# 사용
ai_decision_total.labels(symbol='KRW-ETH', decision='buy').inc()
portfolio_value_krw.set(1015000)
```

---

### 3. 알림 데이터 흐름

```
┌──────────────────────────────────────┐
│     Application Event                │
│  (거래 체결, 에러 발생 등)             │
└──────────────┬───────────────────────┘
               │ 이벤트 발생
               ▼
┌──────────────────────────────────────┐
│  notification.py                     │
│  (notify_trade, notify_error)        │
└──────────────┬───────────────────────┘
               │ Telegram Bot API 호출
               ▼
┌──────────────────────────────────────┐
│   Telegram Bot API                   │
│   (api.telegram.org)                 │
└──────────────┬───────────────────────┘
               │ 메시지 전송
               ▼
┌──────────────────────────────────────┐
│      사용자 Telegram 앱               │
│      (실시간 알림 수신)                │
└──────────────────────────────────────┘
```

---

## 🔍 모니터링 시스템

### Prometheus 메트릭 목록

#### 스케줄러 메트릭

```promql
# 작업 성공 횟수 (Counter)
scheduler_job_success_total{job_name="trading_job"}

# 작업 실패 횟수 (Counter)
scheduler_job_failure_total{job_name="trading_job"}

# 작업 실행 시간 (Histogram)
scheduler_job_duration_seconds{job_name="trading_job"}
```

#### AI 판단 메트릭

```promql
# AI 판단 횟수 (Counter)
ai_decision_total{symbol="KRW-ETH", decision="buy"}
ai_decision_total{symbol="KRW-ETH", decision="sell"}
ai_decision_total{symbol="KRW-ETH", decision="hold"}
```

#### 거래 메트릭

```promql
# 거래 횟수 (Counter)
trades_total{symbol="KRW-ETH"}

# 거래 금액 (Counter)
trade_volume_krw{symbol="KRW-ETH"}
```

#### 포트폴리오 메트릭

```promql
# 포트폴리오 가치 (Gauge)
portfolio_value_krw
```

#### 시스템 메트릭

```promql
# Backend 상태 (Gauge)
up{job="backend"}

# API 응답 시간 (Histogram)
http_request_duration_seconds{method="POST", endpoint="/api/trades"}

# 에러 발생 횟수 (Counter)
bot_errors_total
```

#### PostgreSQL 메트릭

```promql
# 데이터베이스 연결 상태 (Gauge)
pg_up

# 활성 연결 수 (Gauge)
pg_stat_database_numbackends{datname="trading_db"}

# 데이터베이스 크기 (Gauge)
pg_database_size_bytes{datname="trading_db"}
```

---

### Grafana 쿼리 예시

#### 스케줄러 작업 성공률

```promql
(
  sum(scheduler_job_success_total{job_name="trading_job"})
  /
  (
    sum(scheduler_job_success_total{job_name="trading_job"})
    +
    sum(scheduler_job_failure_total{job_name="trading_job"})
  )
) * 100
```

#### AI 판단 분포 (Pie Chart)

```promql
sum by (decision) (ai_decision_total{symbol="KRW-ETH"})
```

#### 평균 작업 실행 시간 (최근 1시간)

```promql
rate(scheduler_job_duration_seconds_sum{job_name="trading_job"}[1h])
/
rate(scheduler_job_duration_seconds_count{job_name="trading_job"}[1h])
```

#### API 응답 시간 95 백분위

```promql
histogram_quantile(
  0.95,
  rate(http_request_duration_seconds_bucket[5m])
)
```

---

## 🐳 배포 구조

### Docker Compose 서비스 구성

**파일**: `docker-compose.full-stack.yml`

```yaml
services:
  # 1. 데이터베이스
  postgres:
    image: postgres:15
    ports: ["5432:5432"]
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  # 2. Backend API
  backend:
    build: ./backend
    ports: ["8000:8000"]
    depends_on: [postgres]
  
  # 3. Scheduler
  scheduler:
    build: .
    command: python scheduler_main.py
    depends_on: [postgres, backend]
  
  # 4. Prometheus
  prometheus:
    image: prom/prometheus:latest
    ports: ["9090:9090"]
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./monitoring/alert_rules.yml:/etc/prometheus/alert_rules.yml
  
  # 5. Grafana
  grafana:
    image: grafana/grafana:latest
    ports: ["3001:3000"]
    volumes:
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
      - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards
  
  # 6. PostgreSQL Exporter
  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:latest
    ports: ["9187:9187"]
    depends_on: [postgres]
```

### 네트워크 구성

```
trading-network (bridge)
├─ postgres (5432)
├─ backend (8000)
├─ scheduler
├─ prometheus (9090)
├─ grafana (3001)
└─ postgres-exporter (9187)
```

**외부 접속 포트**:
- Backend API: `localhost:8000`
- Prometheus: `localhost:9090`
- Grafana: `localhost:3001`
- PostgreSQL: `localhost:5432` (개발용)
- PostgreSQL Exporter: `localhost:9187`

**내부 통신**:
- Prometheus → Backend: `http://backend:8000/metrics`
- Prometheus → PostgreSQL Exporter: `http://postgres-exporter:9187/metrics`
- Grafana → Prometheus: `http://prometheus:9090`
- Backend/Scheduler → PostgreSQL: `postgres:5432`

---

## 📝 환경 변수

**파일**: `.env`

```env
# ===== 거래소 API =====
UPBIT_ACCESS_KEY=your_upbit_access_key
UPBIT_SECRET_KEY=your_upbit_secret_key

# ===== AI 서비스 =====
OPENAI_API_KEY=sk-your_openai_api_key

# ===== 스케줄러 설정 =====
SCHEDULER_ENABLED=true
SCHEDULER_INTERVAL_MINUTES=60  # 1시간

# ===== 거래 설정 =====
TRADING_SYMBOL=KRW-ETH
TRADING_AMOUNT=50000  # 1회 거래 금액 (원)

# ===== Telegram 알림 =====
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=987654321

# ===== 데이터베이스 =====
POSTGRES_USER=trading_user
POSTGRES_PASSWORD=trading_password
POSTGRES_DB=trading_db
DATABASE_URL=postgresql://trading_user:trading_password@postgres:5432/trading_db

# ===== Sentry (에러 추적) =====
SENTRY_ENABLED=false
SENTRY_DSN=https://your_dsn@sentry.io/project_id
SENTRY_ENVIRONMENT=production

# ===== 로깅 =====
LOG_LEVEL=INFO
```

---

## 🚀 시작 가이드

### 1. 전체 스택 시작

```bash
# 모든 서비스 시작
docker-compose -f docker-compose.full-stack.yml up -d

# 로그 확인
docker-compose -f docker-compose.full-stack.yml logs -f

# 상태 확인
docker-compose -f docker-compose.full-stack.yml ps
```

### 2. 접속 확인

```bash
# Backend API
curl http://localhost:8000/health

# Prometheus
curl http://localhost:9090/-/healthy

# Grafana
curl http://localhost:3001/api/health
```

### 3. 대시보드 접속

- Grafana: http://localhost:3001 (admin/admin)
- Prometheus: http://localhost:9090
- Backend API Docs: http://localhost:8000/docs

---

## 📚 관련 문서

- **[모니터링 가이드](./MONITORING_GUIDE.md)** - 모니터링 시스템 상세 가이드
- **[스케줄러 가이드](./SCHEDULER_GUIDE.md)** - 스케줄러 사용법
- **[Telegram 설정 가이드](./TELEGRAM_SETUP_GUIDE.md)** - Telegram 알림 설정
- **[Docker 가이드](./DOCKER_GUIDE.md)** - Docker 실행 방법
- **[사용자 가이드](./USER_GUIDE.md)** - 전체 사용법

---

**작성일**: 2025-12-28  
**최종 업데이트**: 2025-12-28  
**작성자**: AI Assistant  
**상태**: ✅ 완료



