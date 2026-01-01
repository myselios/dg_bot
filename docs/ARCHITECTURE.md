# AI 자동매매 시스템 아키텍처

## 📋 시스템 개요

AI 기반 암호화폐 자동매매 시스템으로, **파이프라인 아키텍처 + 스케줄러 중심 구조**입니다.

**실전 거래**와 **백테스팅** 두 가지 모드를 지원하며, 스케줄러 기반 자동 거래와 Grafana 모니터링 대시보드를 제공합니다.

### 핵심 컴포넌트

1. **Scheduler (scheduler_main.py)** - 1시간 주기 자동 거래 실행
2. **Trading Pipeline** - 4단계 파이프라인 (Risk → Data → Analysis → Execution)
3. **PostgreSQL** - 거래 데이터 저장 (Grafana 연동)
4. **Grafana + Prometheus** - 모니터링 및 시각화

## 🏗 전체 아키텍처 다이어그램

```
┌─────────────────────────────────────────────────────────────┐
│          Scheduler (scheduler_main.py) - 1시간 주기 ⏰        │
│                                                               │
│  ┌────────────────────────────────────────────────────┐     │
│  │        Trading Pipeline (4-Stage Architecture)     │     │
│  │  1. RiskCheckStage - 리스크 체크 (손절/익절/CB)    │     │
│  │  2. DataCollectionStage - 데이터 수집              │     │
│  │  3. AnalysisStage - 백테스팅 + AI 분석 + 검증     │     │
│  │  4. ExecutionStage - 거래 실행                     │     │
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
│                    Data Layer (PostgreSQL)                   │
│                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Trades    │  │  AI Logs    │  │  Portfolio  │         │
│  │   (거래)     │  │ (AI 판단)   │  │  (포트폴리오)│         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└───────────────────────────────┬─────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────┐
│                  Monitoring Stack                            │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │  Prometheus  │  │   Grafana    │                        │
│  │ (메트릭 수집) │  │ (시각화)      │                        │
│  └──────────────┘  └──────────────┘                        │
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
dg_bot/
├── main.py                    # 실전 트레이딩 메인 스크립트 (파이프라인)
├── scheduler_main.py          # 스케줄러 진입점 (1시간 주기)
│
├── src/                       # 핵심 소스 코드
│   ├── api/                   # API 클라이언트
│   │   ├── interfaces.py
│   │   └── upbit_client.py    # Upbit API 클라이언트
│   │
│   ├── ai/                    # AI 서비스
│   │   ├── service.py         # OpenAI 기반 AI 분석 서비스
│   │   ├── validator.py       # AI Decision Validator (검증)
│   │   └── market_correlation.py
│   │
│   ├── backtesting/           # 백테스팅 엔진
│   │   ├── data_provider.py   # 과거 데이터 로더 (캐시 우선)
│   │   ├── backtester.py      # 백테스팅 엔진
│   │   ├── runner.py          # 백테스트 실행기
│   │   ├── strategy.py        # 전략 인터페이스
│   │   ├── rule_based_strategy.py  # 룰 기반 전략 (변동성 돌파)
│   │   ├── quick_filter.py    # 빠른 백테스팅 필터링 (룰 기반)
│   │   ├── portfolio.py       # 포트폴리오 관리
│   │   └── performance.py     # 성능 분석
│   │
│   ├── config/                # 설정
│   │   └── settings.py        # 전역 설정 (TradingConfig, DataConfig, AIConfig)
│   │
│   ├── data/                  # 실전 데이터 수집
│   │   ├── collector.py       # 실시간 시장 데이터 수집
│   │   └── interfaces.py
│   │
│   ├── position/              # 포지션 관리
│   │   └── service.py         # 포지션 계산 및 관리
│   │
│   ├── risk/                  # 리스크 관리 모듈
│   │   ├── manager.py         # RiskManager (Circuit Breaker, 손절/익절)
│   │   └── state_manager.py   # JSON-based state persistence
│   │
│   ├── trading/               # 거래 로직
│   │   ├── service.py         # 거래 실행 서비스
│   │   ├── liquidity_analyzer.py  # Orderbook-based slippage calculation
│   │   ├── indicators.py      # 기술적 지표 (RSI, MACD, BB, ADX, ATR)
│   │   ├── signal_analyzer.py # 신호 분석기
│   │   └── pipeline/          # 🆕 파이프라인 아키텍처
│   │       ├── base_stage.py      # 베이스 스테이지 클래스
│   │       ├── trading_pipeline.py # 파이프라인 오케스트레이터
│   │       ├── risk_stage.py      # 리스크 체크 스테이지
│   │       ├── data_stage.py      # 데이터 수집 스테이지
│   │       ├── analysis_stage.py  # 분석 스테이지
│   │       └── execution_stage.py # 실행 스테이지
│   │
│   ├── utils/                 # 유틸리티
│   │   ├── logger.py          # 로깅 유틸리티
│   │   └── helpers.py         # 헬퍼 함수
│   │
│   └── exceptions.py          # 커스텀 예외
│
├── scripts/                   # 유틸리티 스크립트
│   └── backtesting/           # 백테스팅 데이터 수집
│       ├── data_collector.py  # Upbit 데이터 수집기
│       ├── data_manager.py    # 데이터 관리 및 캐싱
│       └── data_quality.py    # 데이터 품질 검증 및 정제
│
├── backtest_data/             # 백테스팅 데이터 저장소 (자동 생성)
│   ├── daily/                 # 일봉 데이터
│   ├── hourly/                # 시간봉 데이터
│   └── minute/                # 분봉 데이터
│
├── tests/                     # 테스트 코드
│   ├── conftest.py            # pytest 공통 픽스처
│   ├── test_*.py              # 각종 테스트 파일
│   └── ...
│
├── monitoring/                # 모니터링 설정
│   ├── prometheus.yml
│   └── grafana/
│       ├── dashboards/
│       ├── datasources/
│       └── provisioning/
│
├── docs/                      # 문서
│   ├── ARCHITECTURE.md        # 이 문서
│   ├── USER_GUIDE.md          # 사용자 가이드
│   ├── DOCKER_GUIDE.md        # Docker 실행 가이드
│   ├── SCHEDULER_GUIDE.md     # 스케줄러 가이드
│   └── MONITORING_GUIDE.md    # 모니터링 가이드
│
├── docker-compose.yml         # 기본 Docker Compose (스케줄러)
├── docker-compose.full-stack.yml  # 전체 스택 (DB + 모니터링)
├── Dockerfile
├── requirements.txt           # Python 의존성
├── pytest.ini                 # pytest 설정
├── .env.example               # 환경 변수 예시
└── README.md                  # 프로젝트 개요
```

## 🛠 기술 스택

### Core System

- **Runtime**: Python 3.11+
- **Scheduler**: APScheduler (1시간 주기 자동 거래)
- **Architecture**: Pipeline Pattern (4-Stage)
- **AI**: OpenAI GPT-4 API

### Database

- **Primary DB**: PostgreSQL 15+ (Grafana 연동용)

### Monitoring & Logging

- **Error Tracking**: Sentry
- **Metrics**: Prometheus + Grafana
- **Notification**: Telegram Bot API
- **Logging**: Structured Logging

### Infrastructure

- **Container**: Docker + Docker Compose
- **Cloud** (선택): AWS / GCP / DigitalOcean

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
  - RiskManager (🆕 리스크 관리자)
  - QuickBacktestFilter
    ↓
[0단계: 🛡️ 리스크 체크 (최우선)]
  [RiskManager 체크]
    - 포지션 손익 확인 (손절/익절)
    - Circuit Breaker 체크 (일일/주간 손실 한도)
    - 거래 빈도 제한 (최소 간격, 일일 최대 거래 수)
    - Safe Mode 확인
    ↓
    ├─ [리스크 초과] → ❌ 거래 중단 (Safe Mode 진입)
    └─ [리스크 통과] → ✅ 다음 단계 진행
    ↓
[1단계: 빠른 백테스팅 필터 (룰 기반)]
  - RuleBasedBreakoutStrategy 사용 (AI 호출 없음)
  - 변동성 돌파 전략 (3단계 관문)
    * 관문 1: 응축(Squeeze) 확인
    * 관문 2: 돌파(Breakout) 발생
    * 관문 3: 거래량(Volume) 확인
  - 최근 2년 데이터로 백테스팅 (로컬 데이터)
  - 필터 조건: 수익률 ≥3%, 승률 ≥35%, 손익비 ≥1.3, Sharpe ≥0.8, MDD ≤20%
    ↓
    ├─ [조건 미달] → ❌ 거래 중단
    └─ [조건 통과] → ✅ 실전 거래 진행
    ↓
[2단계: 시장 데이터 수집]
  - 차트 데이터 (ETH + BTC)
  - 오더북
  - BTC-ETH 상관관계
  - Flash crash 감지
  - RSI divergence 감지
    ↓
[3단계: 기술적 분석]
  - TechnicalIndicators.get_latest_indicators()
    * RSI, MACD, Bollinger Bands
    * ADX (트렌드 강도)
    * ATR (변동성)
    * Volume
  - SignalAnalyzer.analyze_signals()
    ↓
[4단계: AI 분석 (GPT-4)]
  - AIService.analyze()
    * 백테스팅 결과 포함
    * 종합 시장 분석 (6개 섹션)
    * 매수/매도/보유 결정
    ↓
[5단계: 🆕 AI 판단 검증 (AIDecisionValidator)]
  - RSI 모순 체크
  - ATR 변동성 체크
  - Fakeout 감지 (ADX, Volume)
  - 시장 환경 체크 (상관관계, Flash crash)
    ↓
    ├─ [검증 실패] → ❌ 거래 중단 (오버라이드: hold)
    └─ [검증 통과] → ✅ 거래 실행 진행
    ↓
[6단계: 🆕 유동성 분석 (매수 시만)]
  - LiquidityAnalyzer.calculate_slippage()
    * 오더북 기반 슬리피지 계산
    * 유동성 충분성 확인
    ↓
    ├─ [유동성 부족] → ❌ 거래 중단
    └─ [유동성 충분] → ✅ 거래 실행
    ↓
[7단계: 거래 실행]
  - decision에 따라 매수/매도/보유
  - 수수료 계산 및 검증
  - 실제 주문 실행
    ↓
[8단계: 🆕 거래 기록 및 상태 업데이트]
  - RiskManager.record_trade()
  - RiskStateManager.save_state() (JSON 저장)
  - Telegram 알림
  - Prometheus 메트릭 기록
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

### 3. 스케줄러 자동 트레이딩 (scheduler_main.py)

```
APScheduler (1시간 주기)
    ↓
서비스 초기화 (UpbitClient, DataCollector, TradingService, AIService)
    ↓
execute_trading_cycle() 호출
    ↓
Trading Pipeline 실행 (4-Stage)
  1. RiskCheckStage → 리스크 체크
  2. DataCollectionStage → 데이터 수집
  3. AnalysisStage → 백테스팅 + AI 분석 + 검증
  4. ExecutionStage → 거래 실행
    ↓
Telegram 알림 전송
    ↓
Prometheus 메트릭 기록
```

## 🏗 계층 구조

```
┌─────────────────────────────────────────┐
│         Entry Layer (진입점)              │
│  - main.py (실전 거래)                   │
│  - scheduler_main.py (스케줄러)          │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│        Pipeline Layer (파이프라인)         │
│  - RiskCheckStage (리스크 체크)          │
│  - DataCollectionStage (데이터 수집)     │
│  - AnalysisStage (분석)                  │
│  - ExecutionStage (거래 실행)            │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│        Service Layer (비즈니스 로직)       │
│  - AIService (AI 분석)                   │
│  - TradingService (거래 실행)            │
│  - RiskManager (리스크 관리)             │
│  - DataCollector (데이터 수집)           │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│        Data Layer (데이터 계층)            │
│  - UpbitClient (API 클라이언트)          │
│  - HistoricalDataProvider (과거 데이터)   │
│  - TechnicalIndicators (기술적 지표)      │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│    Infrastructure Layer (인프라)          │
│  - Logger (로깅)                         │
│  - Config (설정)                         │
│  - PostgreSQL (Grafana 연동)             │
│  - Prometheus (메트릭)                   │
└─────────────────────────────────────────┘
```

## 🎯 주요 컴포넌트

### 1. 🆕 리스크 관리 시스템 (`src/risk/`)

#### RiskManager (`src/risk/manager.py`)

- **역할**: 실전 투자의 핵심 - 리스크 통제 및 손실 방지
- **주요 기능**:
  - **손절/익절**: 고정 비율 또는 ATR 기반 동적 설정
  - **Circuit Breaker**: 일일/주간 손실 한도 (-10%/-15%)
  - **거래 빈도 제한**: 최소 간격 (4시간), 일일 최대 거래 수 (5회)
  - **포지션 사이징**: Kelly Criterion 기반 동적 계산
  - **Safe Mode**: 손실 한도 초과 시 자동 거래 차단
  - **트레일링 스탑** (선택): ATR 기반 동적 손절가 조정
  - **분할 익절** (선택): 1차 익절 (+5%, 50% 매도), 2차 익절 (+10%, 100% 매도)

#### RiskStateManager (`src/risk/state_manager.py`)

- **역할**: 리스크 상태 영속성 관리 (프로그램 재시작 시 유지)
- **저장 방식**: JSON 파일 (`data/risk_state.json`)
- **저장 데이터**:
  - `daily_pnl`: 일일 손익 (%)
  - `daily_trade_count`: 일일 거래 횟수
  - `last_trade_time`: 마지막 거래 시간
  - `weekly_pnl`: 주간 손익 (%)
  - `safe_mode`: Safe Mode 활성화 여부
  - `safe_mode_reason`: Safe Mode 진입 사유
- **데이터 관리**: 7일 이상 된 데이터 자동 삭제

### 2. AI 분석 시스템 (`src/ai/`)

#### AIService (`src/ai/service.py`)

- **역할**: 종합 시장 데이터를 분석하여 매수/매도/보유 결정 생성
- **입력**: 차트 데이터, 오더북, 기술적 지표, 포지션 정보, 백테스팅 결과
- **처리**: 10가지 이상의 고급 지표 계산 및 분석
- **출력**: decision (buy/sell/hold), confidence, reason (6개 섹션)

#### AIDecisionValidator (`src/ai/validator.py`)  🆕

- **역할**: AI 판단의 논리적 정합성 검증 ("Trust, but Verify")
- **검증 항목**:
  1. **RSI 모순 체크**: AI가 buy인데 RSI > 70 (과매수) → 차단
  2. **ATR 변동성 체크**: 급격한 변동성 증가 시 거래 차단
  3. **Fakeout 감지**: ADX < 20 (트렌드 부재) + 거래량 < 1.3배 → 차단
  4. **시장 환경 체크**:
     - BTC-ETH 상관관계 급변 → 차단
     - Flash crash 감지 → 차단
     - 시장 불안정 시 → 차단
- **출력**: (유효 여부, 검증 메시지, 오버라이드 결정)

### 3. 거래 실행 시스템 (`src/trading/`)

#### TradingService (`src/trading/service.py`)

- **역할**: 실제 거래 주문 실행
- **특징**:
  - IExchangeClient 인터페이스 사용 (의존성 역전 원칙)
  - 수수료 계산 및 최소 주문 금액 검증
  - 리스크 관리 (매수 비율, 매도 비율 설정)
  - 슬리피지 계산 및 분할 주문

#### LiquidityAnalyzer (`src/trading/liquidity_analyzer.py`)  🆕

- **역할**: 오더북 기반 실시간 슬리피지 계산 및 유동성 분석
- **기능**:
  - **슬리피지 계산**: 호가창 데이터로 예상 평균 체결가 계산
  - **유동성 체크**: 주문 금액에 대한 충분한 유동성 확인
  - **경고 시스템**: 슬리피지 > 0.3% 또는 호가 단계 > 5 시 경고
  - **분할 주문 추천**: 대량 주문 시 분할 매수 권장
- **입력**: orderbook, order_side ('buy'/'sell'), order_krw_amount
- **출력**:
  - `expected_slippage_pct`: 예상 슬리피지 비율
  - `expected_avg_price`: 예상 평균 체결가
  - `liquidity_available`: 유동성 충분 여부
  - `required_levels`: 필요한 호가 단계 수
  - `warning`: 경고 메시지

### 4. 백테스팅 시스템 (`src/backtesting/`)

- **Backtester**: 백테스팅 엔진 (순회하며 전략 시뮬레이션)
- **QuickBacktestFilter**: 빠른 백테스팅 필터링 (룰 기반만)
  - RuleBasedBreakoutStrategy 사용 (AI 호출 없음)
  - 필터 조건: 수익률, 승률, 손익비, Sharpe Ratio, Max Drawdown
- **RuleBasedBreakoutStrategy**: 변동성 돌파 전략 (3단계 관문)
- **Portfolio**: 포트폴리오 관리 (자산, 포지션, 손익)
- **PerformanceAnalyzer**: 성능 분석 및 리포트 생성

### 5. 데이터 수집 시스템

- **DataCollector** (`src/data/collector.py`): 실시간 데이터 수집 (실전 거래용)
- **HistoricalDataProvider** (`src/backtesting/data_provider.py`): 과거 데이터 로드 (백테스팅용, 캐시 우선)
- **UpbitDataCollector** (`scripts/backtesting/data_collector.py`): 백테스팅용 데이터 수집 (CSV 저장)

### 6. Scheduler 시스템 (`scheduler_main.py`)

- **APScheduler**: 1시간 주기 자동 거래 실행
- **Job 설정**:
  - `max_instances=1`: 동시 실행 방지
  - `misfire_grace_time=60`: 지연 허용 시간 60초
  - `coalesce=True`: 누락된 작업 병합
- **Trading Loop**:
  1. 서비스 초기화 (UpbitClient, DataCollector, TradingService, AIService)
  2. execute_trading_cycle() 호출 (리스크 체크 → 백테스팅 → AI 분석 → 거래 실행)
  3. 4-Stage Telegram 알림 (사이클 시작, 백테스팅 결과, AI 판단, 포트폴리오 현황)
  4. Prometheus 메트릭 기록
- **Error Handling**: try-except로 에러 포착, Sentry 전송, Telegram 알림
- **Graceful Shutdown**: SIGINT/SIGTERM 시그널 처리

## 📊 모니터링 메트릭

### 트레이딩 메트릭

```python
trades_total                  # 총 거래 수 (buy/sell 구분)
trade_volume_krw_total        # 총 거래 금액 (KRW)
trade_fee_krw_total           # 총 수수료 (KRW)
slippage_pct                  # 🆕 슬리피지 비율 (%)
```

### AI 메트릭

```python
ai_decisions_total            # AI 판단 수 (buy/sell/hold 구분)
ai_confidence                 # AI 신뢰도 (high/medium/low)
ai_validation_failures_total  # 🆕 AI 검증 실패 횟수
```

### 🆕 리스크 관리 메트릭

```python
risk_circuit_breaker_triggers_total  # Circuit Breaker 발동 횟수
risk_stop_loss_triggers_total       # 손절 발동 횟수
risk_take_profit_triggers_total     # 익절 발동 횟수
risk_daily_pnl_pct                  # 일일 손익률 (%)
risk_weekly_pnl_pct                 # 주간 손익률 (%)
risk_safe_mode_active               # Safe Mode 활성 상태 (0/1)
```

### 포트폴리오 메트릭

```python
portfolio_value_krw           # 포트폴리오 총 가치 (KRW)
portfolio_profit_rate         # 수익률 (%)
```

### 봇 상태

```python
bot_running                   # 봇 실행 상태 (0/1)
bot_errors_total              # 에러 총 횟수
```

### 스케줄러

```python
scheduler_job_duration_seconds     # 작업 실행 시간 (초)
scheduler_job_success_total        # 성공 횟수
scheduler_job_failure_total        # 실패 횟수
```

## 🔐 보안 고려사항

1. **환경 변수**: `.env` 파일로 민감 정보 관리
2. **API 키 보안**: Upbit/OpenAI API 키 암호화 저장
3. **Secrets Management**: AWS Secrets Manager / HashiCorp Vault (선택)

## 📈 확장성 고려사항

1. **다중 코인 지원**: 심볼별 독립적인 스케줄러 인스턴스
2. **다중 거래소**: 추상화된 거래소 인터페이스 (`IExchangeClient`)
3. **알고리즘 A/B 테스트**: 여러 전략 동시 실행 및 비교
4. **클라우드 확장**: Kubernetes로 수평 확장

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

- **테스트** (`tests/`): 백테스팅, AI, 거래 로직, 파이프라인 등
- **목표 커버리지**: 70% 이상 (핵심 로직 90% 이상)

## 📚 관련 문서

- **사용자 가이드**: [USER_GUIDE.md](./USER_GUIDE.md) - 설치부터 운영까지
- **Docker 가이드**: [DOCKER_GUIDE.md](./DOCKER_GUIDE.md) - Docker 실행 및 관리
- **스케줄러 가이드**: [SCHEDULER_GUIDE.md](./SCHEDULER_GUIDE.md) - 1시간 주기 자동 거래
- **모니터링 가이드**: [MONITORING_GUIDE.md](./MONITORING_GUIDE.md) - Grafana + Prometheus 설정
- **Telegram 설정**: [TELEGRAM_SETUP_GUIDE.md](./TELEGRAM_SETUP_GUIDE.md) - 알림 설정
- **리스크 관리 설정**: [RISK_MANAGEMENT_CONFIG.md](./RISK_MANAGEMENT_CONFIG.md) - 🆕 리스크 관리 시스템 완벽 가이드

---

## 🔄 변경 이력

### v3.1.0 (2026-01-01) - 리스크 관리 시스템 통합 🆕

**주요 변경사항**:
1. **리스크 관리 모듈 추가** (`src/risk/`)
   - RiskManager: Circuit Breaker, 손절/익절, 포지션 사이징
   - RiskStateManager: JSON 기반 상태 영속성

2. **AI 검증 레이어 강화** (`src/ai/validator.py`)
   - 2-stage 검증: AI 판단 → 룰 기반 검증
   - RSI, ATR, ADX, Volume 기반 Fakeout 감지

3. **유동성 분석 모듈 추가** (`src/trading/liquidity_analyzer.py`)
   - 오더북 기반 슬리피지 실시간 계산
   - 유동성 부족 시 거래 차단

4. **트레이딩 플로우 재구조화**
   - 0단계: 리스크 체크 (최우선)
   - 5단계: AI 검증
   - 6단계: 유동성 분석
   - 8단계: 상태 저장 (JSON)

5. **Telegram 알림 고도화**
   - 4-Stage 구조화된 알림 (사이클 시작, 백테스팅, AI 판단, 포트폴리오)
   - 리스크 이벤트 알림 (Circuit Breaker, 손절/익절)

6. **Prometheus 메트릭 추가**
   - 리스크 관리 메트릭 (Circuit Breaker, 손절/익절 발동 횟수)
   - AI 검증 실패 메트릭
   - 슬리피지 메트릭

### v3.2.0 (2026-01-01) - 파이프라인 아키텍처 전환

**주요 변경사항**:
1. **파이프라인 아키텍처 도입** (`src/trading/pipeline/`)
   - 4-Stage 파이프라인: Risk → Data → Analysis → Execution
   - 각 스테이지 독립적 테스트 가능

2. **FastAPI Backend 제거**
   - REST API 서버 제거 (Grafana 직접 PostgreSQL 연동으로 대체)
   - 스케줄러 중심 단순화된 아키텍처

3. **백테스팅 필터 단순화**
   - AI 기반 백테스팅 제거 (룰 기반만 사용)
   - API 비용 절감

### v3.1.0 (2025-12-31)
- 리스크 관리 시스템 통합
- AI 검증 레이어 강화
- 유동성 분석 모듈 추가

### v3.0.0 (2025-12-28)
- Scheduler 중심 아키텍처로 전환
- APScheduler 통합

---

**현재 버전**: 3.2.0
**마지막 업데이트**: 2026-01-01
**아키텍처**: Pipeline + Scheduler + Risk Management
**상태**: 프로덕션 준비 완료 ✅
**문서 상태**: ✨ 파이프라인 아키텍처 전환 완료
