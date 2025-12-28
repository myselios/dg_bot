# AI 자동매매 시스템 아키텍처

## 📋 시스템 개요

AI 기반 암호화폐 자동매매 시스템으로, **Python 백엔드 API + 스케줄러 중심 아키텍처**입니다.

**실전 거래**와 **백테스팅** 두 가지 모드를 지원하며, 스케줄러 기반 자동 거래와 REST API를 통한 거래 내역 조회, Grafana 모니터링 대시보드를 제공합니다.

### 핵심 컴포넌트

1. **Scheduler (scheduler_main.py)** - 1시간 주기 자동 거래 실행
2. **Backend API (FastAPI)** - REST API 서버 (거래 내역 조회, 봇 제어)
3. **PostgreSQL** - 거래 데이터 저장
4. **Grafana + Prometheus** - 모니터링 및 시각화

## 🏗 전체 아키텍처 다이어그램

```
┌─────────────────────────────────────────────────────────────┐
│          Scheduler (scheduler_main.py) - 1시간 주기 ⏰        │
│                                                               │
│  ┌────────────────────────────────────────────────────┐     │
│  │        Trading Engine (APScheduler)                │     │
│  │  • 1시간 주기 자동 실행                             │     │
│  │  • Trading Loop (매매 로직)                        │     │
│  │  • AI Service Integration                          │     │
│  │  • 백테스팅 필터링 (2단계 검증)                     │     │
│  └────────────────────────────────────────────────────┘     │
│                                                               │
│  ┌────────────────────────────────────────────────────┐     │
│  │           Monitoring & Notification                │     │
│  │  • Telegram Bot (실시간 알림)                      │     │
│  │  • Sentry (에러 추적)                              │     │
│  │  • Structured Logging                              │     │
│  └────────────────────────────────────────────────────┘     │
└───────────────────────────────┬─────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────┐
│                  Backend API (FastAPI + Python)              │
│                                                               │
│  ┌────────────────────────────────────────────────────┐     │
│  │           REST API Layer (FastAPI)                 │     │
│  │  • GET /api/v1/trades (거래 내역 조회)             │     │
│  │  • GET /api/v1/bot/status (봇 상태 조회)           │     │
│  │  • POST /api/v1/bot/control (봇 제어)              │     │
│  │  • GET /metrics (Prometheus 메트릭)                │     │
│  └────────────────────────────────────────────────────┘     │
│                                                               │
│  ┌────────────────────────────────────────────────────┐     │
│  │           Services Layer                           │     │
│  │  • TradingEngine (거래 엔진)                       │     │
│  │  • NotificationService (알림 서비스)               │     │
│  │  • MetricsService (메트릭 수집)                    │     │
│  └────────────────────────────────────────────────────┘     │
└───────────────────────────────┬─────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────┐
│                    Data Layer (PostgreSQL)                   │
│                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Trades    │  │  AI Logs    │  │  Portfolio  │         │
│  │   (거래)     │  │ (AI 판단)   │  │  (포트폴리오)│         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Orders    │  │ System Logs │  │ Bot Config  │         │
│  │  (주문내역)  │  │ (시스템로그) │  │  (봇 설정)   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└───────────────────────────────┬─────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────┐
│                  Monitoring Stack                            │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Prometheus  │  │   Grafana    │  │    Redis     │      │
│  │ (메트릭 수집) │  │ (시각화)      │  │   (캐시)      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└───────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────┐
│                  External Services                           │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Upbit API    │  │ OpenAI API   │  │ Telegram API │      │
│  │  (거래소)     │  │   (AI)       │  │   (알림)      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└───────────────────────────────────────────────────────────────┘
```

## 📁 프로젝트 구조

### 전체 디렉토리 구조

```
bitcoin/
├── main.py                    # 실전 트레이딩 메인 스크립트
├── backtest.py                # 백테스팅 메인 스크립트
│
├── src/                       # 공통 소스 코드
│   ├── api/                   # API 클라이언트
│   │   ├── __init__.py
│   │   ├── interfaces.py
│   │   └── upbit_client.py    # Upbit API 클라이언트
│   │
│   ├── ai/                    # AI 서비스
│   │   ├── __init__.py
│   │   ├── service.py         # OpenAI 기반 AI 분석 서비스
│   │   └── market_correlation.py
│   │
│   ├── backtesting/           # 백테스팅 엔진
│   │   ├── __init__.py
│   │   ├── data_provider.py   # 과거 데이터 로더 (캐시 우선)
│   │   ├── backtester.py      # 백테스팅 엔진
│   │   ├── runner.py          # 백테스트 실행기
│   │   ├── strategy.py        # 전략 인터페이스
│   │   ├── ai_strategy.py     # AI 기반 전략
│   │   ├── rule_based_strategy.py  # 룰 기반 전략 (변동성 돌파)
│   │   ├── quick_filter.py    # 빠른 백테스팅 필터링 (2단계 검증)
│   │   ├── portfolio.py       # 포트폴리오 관리
│   │   └── performance.py     # 성능 분석
│   │
│   ├── config/                # 설정
│   │   ├── __init__.py
│   │   └── settings.py        # 전역 설정 (TradingConfig, DataConfig, AIConfig)
│   │
│   ├── data/                  # 실전 데이터 수집
│   │   ├── __init__.py
│   │   ├── collector.py       # 실시간 시장 데이터 수집
│   │   └── interfaces.py
│   │
│   ├── position/              # 포지션 관리
│   │   ├── __init__.py
│   │   └── service.py         # 포지션 계산 및 관리
│   │
│   ├── trading/               # 거래 로직
│   │   ├── __init__.py
│   │   ├── service.py         # 거래 실행 서비스
│   │   ├── executor.py
│   │   ├── indicators.py      # 기술적 지표 (MA, RSI, MACD, 볼린저 밴드 등)
│   │   └── signal_analyzer.py # 신호 분석기
│   │
│   ├── utils/                 # 유틸리티
│   │   ├── __init__.py
│   │   ├── logger.py          # 로깅 유틸리티
│   │   └── helpers.py         # 헬퍼 함수
│   │
│   └── exceptions.py          # 커스텀 예외
│
├── backend/                   # FastAPI 백엔드
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI 애플리케이션
│   │   ├── api/               # REST API 엔드포인트
│   │   │   └── v1/
│   │   │       ├── api.py
│   │   │       └── endpoints/
│   │   │           ├── trades.py       # 거래 API
│   │   │           └── bot_control.py  # 봇 제어 API
│   │   ├── core/              # 핵심 설정
│   │   │   ├── config.py
│   │   │   └── scheduler.py   # APScheduler 통합
│   │   ├── db/                # 데이터베이스
│   │   │   ├── base.py
│   │   │   ├── session.py     # 비동기 세션
│   │   │   └── init_db.py
│   │   ├── models/            # SQLAlchemy 모델
│   │   │   ├── trade.py
│   │   │   ├── ai_decision.py
│   │   │   ├── portfolio.py
│   │   │   ├── order.py
│   │   │   ├── system_log.py
│   │   │   └── bot_config.py
│   │   ├── schemas/           # Pydantic 스키마
│   │   │   ├── trade.py
│   │   │   ├── ai_decision.py
│   │   │   └── portfolio.py
│   │   └── services/          # 비즈니스 로직
│   │       ├── trading_engine.py  # 트레이딩 엔진
│   │       ├── notification.py    # Telegram 알림
│   │       └── metrics.py         # Prometheus 메트릭
│   ├── tests/                 # Backend 테스트 (61개)
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── README.md
│   │   ├── test_api_trades.py
│   │   ├── test_api_bot_control.py
│   │   ├── test_models.py
│   │   ├── test_services_notification.py
│   │   ├── test_services_trading_engine.py
│   │   ├── test_scheduler.py
│   │   └── test_integration.py
│   ├── pytest.ini
│   └── run_tests.sh
│
├── scripts/                   # 유틸리티 스크립트
│   └── backtesting/           # 백테스팅 데이터 수집
│       ├── __init__.py
│       ├── README.md
│       ├── data_collector.py  # Upbit 데이터 수집기
│       ├── data_manager.py    # 데이터 관리 및 캐싱
│       ├── data_quality.py    # 데이터 품질 검증 및 정제
│       └── collect_eth_2024.py # 2024년 이더리움 데이터 수집
│
├── backtest_data/             # 백테스팅 데이터 저장소 (자동 생성)
│   ├── daily/                 # 일봉 데이터
│   ├── hourly/                # 시간봉 데이터
│   └── minute/                # 분봉 데이터
│
├── tests/                     # 루트 테스트 코드 (백테스팅, AI, 거래 등)
│   ├── __init__.py
│   ├── conftest.py            # pytest 공통 픽스처
│   ├── test_config.py
│   ├── test_ai_service.py
│   ├── test_backtesting_*.py  # 백테스팅 관련 테스트
│   ├── test_data_collector.py
│   ├── test_helpers.py
│   ├── test_indicators.py
│   ├── test_logger.py
│   ├── test_signal_analyzer.py
│   └── test_trading_service.py
│
├── monitoring/                # 모니터링 설정
│   ├── prometheus.yml
│   └── grafana/
│       ├── dashboards/
│       └── datasources/
│
├── docs/                      # 문서
│   ├── ARCHITECTURE.md        # 이 문서
│   ├── USER_GUIDE.md          # 사용자 가이드
│   ├── DOCKER_GUIDE.md        # Docker 실행 가이드 (통합)
│   ├── SCHEDULER_GUIDE.md     # 스케줄러 가이드
│   └── MONITORING_IMPLEMENTATION_PLAN.md  # 모니터링 구현 계획
│
├── docker-compose.yml         # 기본 Docker Compose (스케줄러)
├── docker-compose.full-stack.yml  # 전체 스택 (API + DB + 모니터링)
├── Dockerfile
├── requirements.txt           # Python 의존성 (실전/백테스팅)
├── requirements-api.txt       # Backend API 의존성
├── pytest.ini                 # pytest 설정
├── .env.example               # 환경 변수 예시
├── restart-full-stack.bat     # 전체 스택 재시작 스크립트
├── restart-scheduler-only.bat # 스케줄러만 재시작 스크립트
└── README.md                  # 프로젝트 개요
```

## 🛠 기술 스택

### Core System

- **Runtime**: Python 3.11+
- **Scheduler**: APScheduler (1시간 주기 자동 거래)
- **API Framework**: FastAPI (비동기 REST API)
- **Database ORM**: SQLAlchemy 2.0 (async)
- **Migration**: Alembic
- **Task Queue** (선택): Celery + Redis (확장성)

### Database

- **Primary DB**: PostgreSQL 15+
- **Cache** (선택): Redis
- **Connection Pool**: asyncpg

### Monitoring & Logging

- **Error Tracking**: Sentry
- **Metrics**: Prometheus + Grafana
- **Notification**: Telegram Bot API
- **Logging**: Structlog + Loguru

### Infrastructure

- **Container**: Docker + Docker Compose
- **Cloud** (선택): AWS / GCP / DigitalOcean
- **CI/CD** (선택): GitHub Actions / GitLab CI

## 📊 데이터베이스 스키마

### Trades (거래 내역)

```sql
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    trade_id VARCHAR(100) UNIQUE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,  -- 'buy' or 'sell'
    price DECIMAL(20, 8) NOT NULL,
    amount DECIMAL(20, 8) NOT NULL,
    total DECIMAL(20, 8) NOT NULL,
    fee DECIMAL(20, 8) DEFAULT 0,
    status VARCHAR(20) NOT NULL,  -- 'completed', 'pending', 'failed'
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_created_at ON trades(created_at DESC);
```

### AI Decisions (AI 판단 로그)

```sql
CREATE TABLE ai_decisions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    decision VARCHAR(20) NOT NULL,  -- 'buy', 'sell', 'hold'
    confidence DECIMAL(5, 2),
    reason TEXT,
    market_data JSONB,  -- 당시 시장 데이터 (OHLCV, 지표 등)
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ai_decisions_symbol ON ai_decisions(symbol);
CREATE INDEX idx_ai_decisions_created_at ON ai_decisions(created_at DESC);
```

### Portfolio (포트폴리오 스냅샷)

```sql
CREATE TABLE portfolio_snapshots (
    id SERIAL PRIMARY KEY,
    total_value_krw DECIMAL(20, 2) NOT NULL,
    total_value_usd DECIMAL(20, 2),
    positions JSONB NOT NULL,  -- {symbol: {amount, value, profit_rate}}
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### Orders (주문 내역)

```sql
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(100) UNIQUE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    order_type VARCHAR(20) NOT NULL,  -- 'market', 'limit'
    price DECIMAL(20, 8),
    amount DECIMAL(20, 8) NOT NULL,
    filled_amount DECIMAL(20, 8) DEFAULT 0,
    status VARCHAR(20) NOT NULL,  -- 'open', 'filled', 'cancelled', 'failed'
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### System Logs (시스템 로그)

```sql
CREATE TABLE system_logs (
    id SERIAL PRIMARY KEY,
    level VARCHAR(20) NOT NULL,  -- 'info', 'warning', 'error', 'critical'
    message TEXT NOT NULL,
    context JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### Bot Config (봇 설정)

```sql
CREATE TABLE bot_config (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

## 🔄 시스템 워크플로우

### 1. 실전 거래 플로우 (main.py)

```
[main.py 시작]
    ↓
[서비스 초기화]
  - UpbitClient, DataCollector
  - TradingService, AIService
  - QuickBacktestFilter
    ↓
[1단계: 빠른 백테스팅 필터 (2단계 검증)]
  [1-1. 룰 기반 백테스팅 (AI 호출 없음)]
    - RuleBasedBreakoutStrategy 사용
    - 변동성 돌파 전략 (3단계 관문)
      * 관문 1: 응축(Squeeze) 확인
      * 관문 2: 돌파(Breakout) 발생
      * 관문 3: 거래량(Volume) 확인
    - 최근 30일 데이터로 백테스팅
    ↓
    ├─ [조건 미달] → ❌ 거래 중단
    └─ [조건 통과] → ✅ 1-2단계로 진행
    ↓
  [1-2. AI 기반 백테스팅 (룰 통과 시에만)]
    - AITradingStrategy 사용
    - AI 분석을 통한 최종 검증
    ↓
    ├─ [조건 미달] → ❌ 거래 중단
    └─ [조건 통과] → ✅ 실전 거래 진행
    ↓
[2단계: 시장 데이터 수집]
  - 오더북, 차트 데이터
  - 공포탐욕지수
    ↓
[3단계: 기술적 분석]
  - TechnicalIndicators.get_latest_indicators()
  - SignalAnalyzer.analyze_signals()
    ↓
[4단계: AI 분석 (GPT-4)]
  - 백테스팅 결과 포함
  - 종합 시장 분석
  - 매수/매도/보유 결정
    ↓
[5단계: 거래 실행]
  - decision에 따라 매수/매도/보유
  - 수수료 계산 및 검증
  - 실제 주문 실행
```

### 2. 백테스팅 플로우 (backtest.py)

```
[backtest.py 시작]
    ↓
[1단계: 과거 데이터 로드]
  - HistoricalDataProvider.load_historical_data()
  - 캐시된 CSV 파일 우선 사용
    ↓
[2단계: 전략 초기화]
  - AITradingStrategy 또는 RuleBasedBreakoutStrategy
    ↓
[3단계: 백테스트 실행]
  - Backtester.run() 루프
    for each bar in data:
      [1] 전략 신호 생성
      [2] 주문 실행 시뮬레이션
      [3] 포트폴리오 업데이트
      [4] 자산 곡선 업데이트
    ↓
[4단계: 성능 분석]
  - PerformanceAnalyzer.analyze()
    * 총 수익률, 승률
    * Sharpe Ratio, Max Drawdown
    * 거래 통계
    ↓
[5단계: 결과 출력]
  - 성능 리포트 생성
  - 최근 거래 내역 출력
  - 결과 시각화 (선택)
```

### 3. 자동 트레이딩 사이클 (Backend Scheduler)

```
APScheduler (매 5분)
    ↓
시장 데이터 수집 (Upbit API)
    ↓
기술적 지표 계산 (RSI, MACD, 볼린저밴드)
    ↓
AI 판단 요청 (OpenAI API)
    ↓
판단 결과 DB 저장 (ai_decisions)
    ↓
거래 실행 (매수/매도/홀드)
    ↓
거래 결과 DB 저장 (trades, orders)
    ↓
Telegram 알림 전송
    ↓
WebSocket으로 대시보드 업데이트
    ↓
Prometheus 메트릭 기록
```

### 4. API 호출 플로우 (거래 내역 조회)

```
외부 클라이언트 (curl, Postman, Grafana 등)
    ↓
REST API 호출 (FastAPI)
    ↓
비즈니스 로직 처리 (services/)
    ↓
PostgreSQL CRUD (models/)
    ↓
응답 반환 (schemas/)
    ↓
JSON 응답
```

## 🏗 계층 구조

```
┌─────────────────────────────────────────┐
│         Entry Layer (진입점)              │
│  - main.py (실전 거래)                   │
│  - backtest.py (백테스팅)                │
│  - backend/app/main.py (API 서버)       │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│        Service Layer (비즈니스 로직)       │
│  - AIService (AI 분석)                   │
│  - TradingService (거래 실행)            │
│  - PositionService (포지션 관리)         │
│  - DataCollector (데이터 수집)           │
│  - TradingEngine (Backend 엔진)          │
│  - NotificationService (알림)            │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│        Data Layer (데이터 계층)            │
│  - UpbitClient (API 클라이언트)          │
│  - HistoricalDataProvider (과거 데이터)   │
│  - TechnicalIndicators (기술적 지표)      │
│  - SQLAlchemy Models (DB 모델)           │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│    Infrastructure Layer (인프라)          │
│  - Logger (로깅)                         │
│  - Config (설정)                         │
│  - Utils (유틸리티)                      │
│  - PostgreSQL (데이터베이스)             │
│  - Prometheus (메트릭)                   │
└─────────────────────────────────────────┘
```

## 🎯 주요 컴포넌트

### 1. AI 분석 시스템 (`src/ai/service.py`)

- **역할**: 종합 시장 데이터를 분석하여 매수/매도/보유 결정 생성
- **입력**: 차트 데이터, 오더북, 기술적 지표, 포지션 정보, 백테스팅 결과
- **처리**: 10가지 이상의 고급 지표 계산 및 분석
- **출력**: decision (buy/sell/hold), confidence, reason

### 2. 거래 실행 시스템 (`src/trading/service.py`)

- **역할**: 실제 거래 주문 실행
- **특징**:
  - IExchangeClient 인터페이스 사용 (의존성 역전 원칙)
  - 수수료 계산 및 최소 주문 금액 검증
  - 리스크 관리 (매수 비율, 매도 비율 설정)

### 3. 백테스팅 시스템 (`src/backtesting/`)

- **Backtester**: 백테스팅 엔진 (순회하며 전략 시뮬레이션)
- **QuickBacktestFilter**: 빠른 백테스팅 필터링 (2단계 검증)
  - 1단계: 룰 기반 백테스팅 (AI 호출 없음)
  - 2단계: AI 기반 백테스팅 (룰 통과 시에만)
- **RuleBasedBreakoutStrategy**: 변동성 돌파 전략 (3단계 관문)
- **AITradingStrategy**: AI 기반 전략 구현
- **Portfolio**: 포트폴리오 관리 (자산, 포지션, 손익)
- **PerformanceAnalyzer**: 성능 분석 및 리포트 생성

### 4. 데이터 수집 시스템

- **DataCollector** (`src/data/collector.py`): 실시간 데이터 수집 (실전 거래용)
- **HistoricalDataProvider** (`src/backtesting/data_provider.py`): 과거 데이터 로드 (백테스팅용, 캐시 우선)
- **UpbitDataCollector** (`scripts/backtesting/data_collector.py`): 백테스팅용 데이터 수집 (CSV 저장)

### 5. Backend API 시스템 (`backend/app/`)

- **FastAPI Application**: REST API 서버 (거래 내역 조회, 봇 제어)
- **SQLAlchemy**: 비동기 ORM
- **Prometheus**: 메트릭 수집 (`/metrics` 엔드포인트)
- **주요 엔드포인트**:
  - `GET /api/v1/trades` - 거래 내역 조회
  - `GET /api/v1/bot/status` - 봇 상태 조회
  - `POST /api/v1/bot/control` - 봇 제어 (시작/중지)
  - `GET /metrics` - Prometheus 메트릭

### 6. Scheduler 시스템 (`scheduler_main.py`)

- **APScheduler**: 1시간 주기 자동 거래 실행
- **Trading Loop**: 시장 데이터 수집 → AI 분석 → 거래 실행
- **Telegram Bot**: 실시간 거래 알림
- **Error Handling**: 자동 재시도 및 에러 로깅

## 📊 모니터링 메트릭

### HTTP 메트릭

```python
http_requests_total
http_request_duration_seconds
```

### 트레이딩 메트릭

```python
trades_total
trade_volume_krw_total
trade_fee_krw_total
```

### AI 메트릭

```python
ai_decisions_total
ai_confidence
```

### 포트폴리오 메트릭

```python
portfolio_value_krw
portfolio_profit_rate
```

### 봇 상태

```python
bot_running
bot_errors_total
```

### 스케줄러

```python
scheduler_job_duration_seconds
scheduler_job_success_total
scheduler_job_failure_total
```

## 🔐 보안 고려사항

1. **API 인증**: JWT 토큰 기반 인증 (선택적 구현)
2. **환경 변수**: `.env` 파일로 민감 정보 관리
3. **CORS**: Grafana, Prometheus 등 모니터링 도구 접근 허용
4. **Rate Limiting**: API 요청 제한 (FastAPI middleware)
5. **Secrets Management**: AWS Secrets Manager / HashiCorp Vault (선택)
6. **Database**: 암호화된 연결 (SSL)

## 📈 확장성 고려사항

1. **다중 코인 지원**: 심볼별 독립적인 스케줄러 인스턴스
2. **다중 거래소**: 추상화된 거래소 인터페이스 (`IExchangeClient`)
3. **백테스팅 통합**: API를 통한 백테스트 실행 및 결과 조회
4. **알고리즘 A/B 테스트**: 여러 전략 동시 실행 및 비교
5. **클라우드 확장**: Kubernetes로 수평 확장
6. **Web Dashboard**: React/Vue.js 기반 대시보드 추가 (선택적)

## 🎨 설계 원칙

### 1. 의존성 역전 원칙 (DIP)

- `TradingService`는 `IExchangeClient` 인터페이스에 의존
- 구체 구현체(`UpbitClient`)가 아닌 추상화에 의존하여 테스트 가능성 향상

### 2. 전략 패턴 (Strategy Pattern)

- `Strategy` 추상 클래스로 전략 인터페이스 정의
- `AITradingStrategy`, `RuleBasedBreakoutStrategy`가 구체 전략 구현
- 새로운 전략 추가 시 확장 용이

### 3. 단일 책임 원칙 (SRP)

- 각 클래스가 명확한 단일 책임을 가짐
- `TradingService`: 거래 실행만
- `AIService`: AI 분석만
- `DataCollector`: 데이터 수집만

### 4. 캐시 우선 전략

- 백테스팅 데이터는 캐시된 CSV 파일 우선 사용
- API 호출 최소화로 성능 및 비용 절감

## 🎯 성능 지표

### 목표 KPI

1. **시스템 가동률**: 99.5% 이상
2. **API 응답 시간**: 평균 200ms 이하
3. **거래 실행 시간**: 1초 이내
4. **에러율**: 0.1% 이하
5. **알림 지연**: 5초 이내

### 백테스팅 성능 지표

- 총 수익률 (Total Return)
- 승률 (Win Rate)
- 최대 낙폭 (Max Drawdown)
- Sharpe Ratio, Sortino Ratio, Calmar Ratio
- 평균 손익 (Average Win/Loss)
- Profit Factor
- 평균 보유 기간

## 🎓 테스트 전략

### TDD (Test-Driven Development)

- 모든 기능은 테스트 먼저 작성 (Red → Green → Refactor)
- Given-When-Then 패턴 사용
- AAA (Arrange-Act-Assert) 패턴 준수

### 테스트 커버리지

- **루트 테스트** (`tests/`): 백테스팅, AI, 거래 로직 등
- **Backend 테스트** (`backend/tests/`): API, 모델, 서비스 등 (61개)
- **목표 커버리지**: 70% 이상 (핵심 로직 90% 이상)

## 📚 관련 문서

- **사용자 가이드**: `docs/USER_GUIDE.md` - 설치부터 운영까지
- **Docker 가이드**: `docs/DOCKER_GUIDE.md` - Docker 실행 및 관리 완벽 가이드
- **스케줄러 가이드**: `docs/SCHEDULER_GUIDE.md` - 자동화 시스템 완벽 가이드
- **모니터링 계획**: `docs/MONITORING_IMPLEMENTATION_PLAN.md` - 모니터링 시스템 구현 계획
- **Backend 테스트**: `backend/tests/README.md` - Backend 테스트 가이드 (61개)
- **백테스팅 데이터**: `scripts/backtesting/README.md` - 데이터 수집 스크립트 사용법

---

**마지막 업데이트**: 2025-12-28
**버전**: 3.0.0
**아키텍처**: Backend API + Scheduler 중심 (프론트엔드 제거)
**상태**: 프로덕션 준비 완료 ✅
**문서 상태**: ✨ 백엔드 중심 아키텍처로 리팩토링 완료
