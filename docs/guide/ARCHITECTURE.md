# AI 자동매매 시스템 아키텍처

## 📋 시스템 개요

AI 기반 암호화폐 자동매매 시스템으로, **멀티코인 스캐닝 + 적응형 파이프라인 아키텍처**입니다.

**실전 거래**와 **백테스팅** 두 가지 모드를 지원하며, 스케줄러 기반 자동 거래와 Grafana 모니터링 대시보드를 제공합니다.

### 핵심 컴포넌트

1. **Scheduler (scheduler_main.py)** - 듀얼 타임프레임 자동 거래
   - `trading_job` (1시간): 멀티코인 스캔 + AI 분석 + 진입 탐색
   - `position_management_job` (15분): 보유 포지션 손절/익절 관리
2. **Hybrid Trading Pipeline** - 4단계 하이브리드 파이프라인 (HybridRiskCheck → Data → Analysis → Execution)
3. **Multi-Coin Scanner** - 유동성 스캔 → 백테스팅 → AI 분석 → 최적 코인 선택
4. **Portfolio Manager** - 최대 3개 코인 동시 관리, 하이브리드 포지션 관리
5. **PostgreSQL** - 거래 데이터 저장 (Grafana 연동)
6. **Grafana + Prometheus** - 모니터링 및 시각화

## 🏗 전체 아키텍처 다이어그램

```
┌─────────────────────────────────────────────────────────────────────────┐
│          Scheduler (scheduler_main.py) - 듀얼 타임프레임 ⏰               │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  trading_job (1시간)           position_management_job (15분)    │   │
│  │  - 멀티코인 스캔                - 보유 포지션 손절/익절 체크       │   │
│  │  - AI 분석 + 진입 탐색          - 규칙 기반 빠른 처리 (AI 없음)   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │         Adaptive Trading Pipeline (5-Stage Architecture)       │    │
│  │                                                                  │    │
│  │  1. AdaptiveRiskCheckStage - 포트폴리오 상태 확인 & 모드 분기   │    │
│  │     ├─ ENTRY MODE (포지션 없음/추가 가능)                       │    │
│  │     └─ MANAGEMENT MODE (포지션 있음 → 하이브리드 관리)          │    │
│  │                                                                  │    │
│  │  2. CoinScanStage - 멀티코인 스캐닝 (ENTRY MODE에서만)          │    │
│  │     ├─ LiquidityScanner: 상위 10개 유동성 코인                  │    │
│  │     ├─ MultiCoinBacktest: 12가지 퀀트 필터 (병렬 처리)          │    │
│  │     └─ CoinSelector: 최종 2개 코인 선택                         │    │
│  │                                                                  │    │
│  │  3. DataCollectionStage - 데이터 수집                           │    │
│  │  4. AnalysisStage - AI 진입 분석 + 검증                         │    │
│  │  5. ExecutionStage - 거래 실행                                  │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                    Monitoring & Notification                    │    │
│  │  • Telegram Bot (실시간 알림)                                   │    │
│  │  • Sentry (에러 추적)                                           │    │
│  │  • Structured Logging                                           │    │
│  └────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼──────────────────────────────────────┐
│                        Data Layer (PostgreSQL)                          │
│                                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │   Trades    │  │  AI Logs    │  │  Portfolio  │  │  Scan Logs  │   │
│  │   (거래)    │  │ (AI 판단)   │  │ (포트폴리오)│  │ (스캔 결과) │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼──────────────────────────────────────┐
│                          Monitoring Stack                               │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐                                    │
│  │  Prometheus  │  │   Grafana    │                                    │
│  │ (메트릭 수집) │  │ (시각화)     │                                    │
│  └──────────────┘  └──────────────┘                                    │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼──────────────────────────────────────┐
│                          External Services                              │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │ Upbit API    │  │ OpenAI API   │  │ Telegram API │                  │
│  │  (거래소)    │  │   (AI)       │  │   (알림)     │                  │
│  └──────────────┘  └──────────────┘  └──────────────┘                  │
└────────────────────────────────────────────────────────────────────────┘
```

## 🔄 멀티코인 스캐닝 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         매 시간 거래 사이클                              │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                   ┌─────────────────────────┐
                   │  AdaptiveRiskCheckStage │
                   │  (포트폴리오 상태 확인)  │
                   └─────────────────────────┘
                                  │
                   ┌──────────────┴──────────────┐
                   ▼                              ▼
┌─────────────────────────────┐    ┌─────────────────────────────┐
│        ENTRY MODE           │    │      MANAGEMENT MODE        │
│    (포지션 없음/추가가능)    │    │       (포지션 있음)          │
├─────────────────────────────┤    ├─────────────────────────────┤
│                             │    │                             │
│  1. 유동성 스캔 (10개)      │    │  1. 규칙 기반 체크 (무료)   │
│     └─ 100억원+ 거래대금    │    │     ├─ 손절 -5%            │
│     └─ 스테이블코인 제외    │    │     ├─ 익절 +10%           │
│                             │    │     ├─ Fakeout 감지        │
│  2. 병렬 백테스팅 (5개)     │    │     ├─ 타임아웃 (24h)      │
│     └─ 12가지 퀀트 필터     │    │     └─ 트레일링 스탑       │
│     └─ Sharpe/Sortino/Calmar│    │                             │
│                             │    │  2. AI 분석 (애매할 때만)   │
│  3. AI 진입 분석 (2개)      │    │     ├─ 수익 2%~8% 구간     │
│     └─ 리스크 헌터 역할     │    │     ├─ ADX 25-30 구간      │
│                             │    │     └─ 거래량-가격 괴리    │
│  4. 최적 코인 선택          │    │                             │
│     └─ 백테스팅 60%+AI 40%  │    │  → 청산/보유 결정          │
│                             │    │                             │
│  5. 진입 실행               │    │                             │
└─────────────────────────────┘    └─────────────────────────────┘
```

## 📁 프로젝트 구조

### 전체 디렉토리 구조

```
dg_bot/
├── main.py                    # 실전 트레이딩 메인 스크립트
│   ├── execute_trading_cycle()         # 1시간 주기 거래 사이클 (진입 탐색)
│   └── execute_position_management_cycle()  # 15분 주기 포지션 관리
├── scheduler_main.py          # 스케줄러 진입점 (듀얼 타임프레임)
│
├── src/                       # 핵심 소스 코드
│   ├── api/                   # API 클라이언트
│   │   ├── interfaces.py
│   │   └── upbit_client.py    # Upbit API 클라이언트
│   │
│   ├── ai/                    # AI 서비스 (분리된 분석기)
│   │   ├── __init__.py
│   │   ├── service.py         # AIService - 기존 호환성 유지
│   │   ├── entry_analyzer.py  # 🆕 EntryAnalyzer - 진입 전용 분석기
│   │   ├── position_analyzer.py # 🆕 PositionAnalyzer - 하이브리드 포지션 관리
│   │   ├── validator.py       # AI Decision Validator (검증)
│   │   └── market_correlation.py
│   │
│   ├── backtesting/           # 백테스팅 엔진
│   │   ├── data_provider.py   # 과거 데이터 로더 (캐시 우선)
│   │   ├── backtester.py      # 백테스팅 엔진
│   │   ├── runner.py          # 백테스트 실행기
│   │   ├── strategy.py        # 전략 인터페이스
│   │   ├── rule_based_strategy.py  # 룰 기반 전략 (변동성 돌파)
│   │   ├── quick_filter.py    # 빠른 백테스팅 필터링 (12가지 퀀트 기준)
│   │   ├── portfolio.py       # 포트폴리오 관리
│   │   └── performance.py     # 성능 분석
│   │
│   ├── scanner/               # 🆕 멀티코인 스캐닝 모듈
│   │   ├── __init__.py
│   │   ├── liquidity_scanner.py  # 유동성 스캔 (상위 10개)
│   │   ├── data_sync.py          # 과거 데이터 동기화 (Parquet)
│   │   ├── multi_backtest.py     # 병렬 백테스팅 (12가지 퀀트 필터)
│   │   └── coin_selector.py      # 코인 선택 파이프라인
│   │
│   ├── config/                # 설정
│   │   └── settings.py        # 전역 설정 (TradingConfig, DataConfig, AIConfig)
│   │
│   ├── data/                  # 실전 데이터 수집
│   │   ├── collector.py       # 실시간 시장 데이터 수집
│   │   └── interfaces.py
│   │
│   ├── position/              # 포지션 관리
│   │   ├── __init__.py
│   │   ├── service.py         # 포지션 계산 및 관리
│   │   └── portfolio_manager.py # 🆕 PortfolioManager - 멀티코인 포트폴리오 관리
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
│   │   └── pipeline/          # 파이프라인 아키텍처
│   │       ├── __init__.py
│   │       ├── base_stage.py           # 베이스 스테이지 클래스
│   │       ├── trading_pipeline.py     # 파이프라인 오케스트레이터
│   │       ├── risk_check_stage.py     # 리스크 체크 스테이지
│   │       ├── adaptive_stage.py       # AdaptiveRiskCheckStage (포지션 분기)
│   │       ├── hybrid_stage.py         # 🆕 HybridRiskCheckStage (진입/관리 통합)
│   │       ├── coin_scan_stage.py      # CoinScanStage (멀티코인 스캐닝)
│   │       ├── data_collection_stage.py # 데이터 수집 스테이지
│   │       ├── analysis_stage.py       # 분석 스테이지
│   │       └── execution_stage.py      # 실행 스테이지
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
│   ├── minute/                # 분봉 데이터
│   └── parquet/               # 🆕 Parquet 형식 데이터 (멀티코인)
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
│   ├── MULTI_COIN_IMPLEMENTATION.md  # 🆕 멀티코인 구현 가이드
│   ├── USER_GUIDE.md          # 사용자 가이드
│   ├── DOCKER_GUIDE.md        # Docker 실행 가이드
│   ├── SCHEDULER_GUIDE.md     # 스케줄러 가이드
│   └── MONITORING_GUIDE.md    # 모니터링 가이드
│
├── docker-compose.yml         # 기본 Docker Compose (스케줄러)
├── docker-compose.yml  # 전체 스택 (DB + 모니터링)
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
- **Architecture**: Adaptive Pipeline Pattern (5-Stage)
- **AI**: OpenAI GPT-4 API
- **Parallel Processing**: ThreadPoolExecutor, asyncio

### Database

- **Primary DB**: PostgreSQL 15+ (Grafana 연동용)
- **Data Storage**: Parquet (멀티코인 백테스팅 데이터)

### Monitoring & Logging

- **Error Tracking**: Sentry
- **Metrics**: Prometheus + Grafana
- **Notification**: Telegram Bot API
- **Logging**: Structured Logging

### Infrastructure

- **Container**: Docker + Docker Compose
- **Cloud** (선택): AWS / GCP / DigitalOcean

## 🎯 주요 컴포넌트

### 1. 🆕 멀티코인 스캐닝 시스템 (`src/scanner/`)

#### LiquidityScanner (`src/scanner/liquidity_scanner.py`)

- **역할**: 업비트 KRW 마켓 전체에서 유동성 상위 코인 추출
- **주요 기능**:
  - 24시간 거래대금 기준 필터링 (100억원+)
  - 스테이블코인 자동 제외 (USDT, USDC, DAI 등)
  - 레버리지 토큰 제외 (2L, 2S, 3L, 3S, UP, DOWN)
  - 7일 변동성 (ATR) 계산
- **출력**: `List[CoinInfo]` (ticker, volume_24h, volatility)

```python
class LiquidityScanner:
    async def scan_top_coins(
        min_volume_krw: float = 10_000_000_000,  # 100억원
        top_n: int = 20,
        include_volatility: bool = True
    ) -> List[CoinInfo]
```

#### HistoricalDataSync (`src/scanner/data_sync.py`)

- **역할**: 과거 데이터 다운로드 및 증분 업데이트
- **저장 형식**: Parquet (효율적인 컬럼 기반 저장)
- **주요 기능**:
  - 2년치 데이터 동기화
  - 증분 업데이트 (마지막 데이터 이후만)
  - 3년 이상 오래된 데이터 자동 정리

```python
class HistoricalDataSync:
    async def sync_coin_data(ticker: str, years: int = 2) -> SyncStatus
    async def sync_multiple_coins(tickers: List[str]) -> List[SyncStatus]
    def load_data(ticker: str, interval: str = "day") -> Optional[pd.DataFrame]
```

#### MultiCoinBacktest (`src/scanner/multi_backtest.py`)

- **역할**: 여러 코인에 대해 병렬 백테스팅 실행
- **주요 기능**:
  - ThreadPoolExecutor 기반 병렬 처리
  - 12가지 퀀트 필터 적용 (QuickBacktestConfig와 동기화)
  - 점수 기반 순위화 (0-100점)
  - 등급 분류 (STRONG PASS / WEAK PASS / FAIL)

```python
@dataclass
class MultiBacktestConfig:
    # 1. 수익성 (Profitability)
    min_return: float = 15.0              # 2년 기준 15%
    min_win_rate: float = 38.0            # 최소 승률
    min_profit_factor: float = 1.8        # 최소 손익비

    # 2. 위험조정 수익률 (Risk-Adjusted Returns)
    min_sharpe_ratio: float = 1.0
    min_sortino_ratio: float = 1.2
    min_calmar_ratio: float = 0.8

    # 3. 리스크 관리 (Risk Management)
    max_drawdown: float = 15.0
    max_consecutive_losses: int = 5
    max_volatility: float = 50.0

    # 4. 통계적 유의성
    min_trades: int = 20

    # 5. 거래 품질
    min_avg_win_loss_ratio: float = 1.3
    max_avg_holding_hours: float = 168.0  # 7일
```

#### CoinSelector (`src/scanner/coin_selector.py`)

- **역할**: 전체 스캐닝 파이프라인 조율
- **5단계 필터링**:
  1. 유동성 스캔 (10개)
  2. 데이터 동기화
  3. 병렬 백테스팅 (5개 통과)
  4. AI 진입 분석
  5. 최종 선택 (2개)
- **최종 점수**: 백테스팅(60%) + AI(40%)

```python
class CoinSelector:
    async def select_coins(
        exclude_tickers: Optional[List[str]] = None,
        force_data_sync: bool = False
    ) -> ScanResult
```

### 2. 🆕 적응형 파이프라인 (`src/trading/pipeline/`)

#### AdaptiveRiskCheckStage (`src/trading/pipeline/adaptive_stage.py`)

- **역할**: 포트폴리오 상태 확인 및 거래 모드 분기
- **거래 모드**:
  - `ENTRY`: 포지션 없음 또는 추가 가능 → 진입 탐색
  - `MANAGEMENT`: 포지션 있음 → 하이브리드 관리
  - `BLOCKED`: 일일/주간 손실 한도 초과

```python
class AdaptiveRiskCheckStage(BasePipelineStage):
    async def execute(self, context: PipelineContext) -> StageResult:
        # 포트폴리오 상태 확인
        portfolio_state = self.portfolio_manager.get_state()

        # 모드 분기
        if portfolio_state.mode == 'ENTRY':
            # → CoinScanStage로 진행
        elif portfolio_state.mode == 'MANAGEMENT':
            # → PositionAnalyzer로 하이브리드 관리
```

#### CoinScanStage (`src/trading/pipeline/coin_scan_stage.py`)

- **역할**: ENTRY 모드에서 멀티코인 스캐닝 실행
- **스킵 조건**: MANAGEMENT 또는 BLOCKED 모드

```python
class CoinScanStage(BasePipelineStage):
    async def execute(self, context: PipelineContext) -> StageResult:
        if context.data.get('trading_mode') != 'ENTRY':
            return StageResult(success=True, data={'skipped': True})

        # 코인 스캔 실행
        scan_result = await self.coin_selector.select_coins(
            exclude_tickers=current_holdings
        )

        # 선택된 코인으로 티커 업데이트
        context.ticker = best_coin.ticker
```

### 3. 🆕 포지션 분리 시스템 (`src/ai/`, `src/position/`)

#### EntryAnalyzer (`src/ai/entry_analyzer.py`)

- **역할**: 포지션 없을 때 사용하는 진입 전용 분석기
- **특징**:
  - **리스크 헌터 역할**: 거래를 막을 이유 탐색
  - 백테스팅 등급 평가 (STRONG PASS / WEAK PASS / FAIL)
  - 진입 신호 점수 계산 (0-100)

#### PositionAnalyzer (`src/ai/position_analyzer.py`)

- **역할**: 포지션 있을 때 하이브리드 방식 관리
- **규칙 기반 청산 조건** (무료):
  - 손절: -5%
  - 익절: +10%
  - Fakeout: 3봉 내 -2%
  - 타임아웃: 24시간 + 수익률 < 2%
  - ADX 약화: < 20 (6시간 이후)
  - 트레일링 스탑: +5% 이상 시 조정
- **AI 분석 조건** (유료, 30% 케이스):
  - 애매한 수익 구간 (2% ~ 8%)
  - 추세 약화 조짐 (ADX 25-30)
  - 거래량-가격 괴리

```python
class PositionAnalyzer:
    # 규칙 기반 설정
    DEFAULT_STOP_LOSS_PCT = -5.0
    DEFAULT_TAKE_PROFIT_PCT = 10.0
    FAKEOUT_THRESHOLD_PCT = -2.0
    FAKEOUT_MAX_CANDLES = 3
    TIMEOUT_HOURS = 24
    TRAILING_STOP_TRIGGER_PCT = 5.0
```

#### PortfolioManager (`src/position/portfolio_manager.py`)

- **역할**: 멀티코인 포트폴리오 레벨 관리
- **설정**:
  - 최대 3개 코인 동시 보유
  - 코인당 최대 자본 40%
  - 예비 자금 10%
  - 일일 손실 한도 -10%
  - 주간 손실 한도 -15%
- **거래 모드**: ENTRY / MANAGEMENT / BLOCKED

```python
class PortfolioManager:
    MAX_POSITIONS = 3
    MAX_ALLOCATION_PER_COIN = 0.4  # 40%
    MIN_POSITION_VALUE = 10000     # 1만원
    RESERVE_RATIO = 0.1            # 10%
    PORTFOLIO_DAILY_LOSS_LIMIT = -0.10
    PORTFOLIO_WEEKLY_LOSS_LIMIT = -0.15
```

### 4. 리스크 관리 시스템 (`src/risk/`)

#### RiskManager (`src/risk/manager.py`)

- **역할**: 실전 투자의 핵심 - 리스크 통제 및 손실 방지
- **주요 기능**:
  - **손절/익절**: 고정 비율 또는 ATR 기반 동적 설정
  - **Circuit Breaker**: 일일/주간 손실 한도 (-10%/-15%)
  - **거래 빈도 제한**: 최소 간격 (4시간), 일일 최대 거래 수 (5회)
  - **포지션 사이징**: Kelly Criterion 기반 동적 계산
  - **Safe Mode**: 손실 한도 초과 시 자동 거래 차단

#### RiskStateManager (`src/risk/state_manager.py`)

- **역할**: 리스크 상태 영속성 관리 (프로그램 재시작 시 유지)
- **저장 방식**: JSON 파일 (`data/risk_state.json`)

### 5. 🆕 AI 클린 아키텍처 (`src/application/`, `src/infrastructure/`)

AI 판단 시스템이 클린 아키텍처로 리팩토링되었습니다 (v4.4.0).

#### 5.1 도메인 Value Objects (`src/domain/value_objects/`)

| Value Object | 역할 | 주요 속성 |
|-------------|------|----------|
| `MarketSummary` | 시장 요약 정보 | regime, atr_percent, breakout_strength |
| `AIDecisionResult` | AI 판단 결과 | decision (ALLOW/BLOCK/HOLD), confidence, reason |
| `PromptVersion` | 프롬프트 버전 | version, template_hash, prompt_type |

```python
from src.domain.value_objects import (
    MarketSummary, MarketRegime, BreakoutStrength,
    AIDecisionResult, DecisionType,
    PromptVersion, PromptType,
)

# 시장 요약 생성
summary = MarketSummary(
    ticker="KRW-BTC",
    regime=MarketRegime.TRENDING_UP,
    atr_percent=Decimal("2.5"),
    breakout_strength=BreakoutStrength.STRONG,
    risk_budget=Decimal("0.02"),
)

# AI 결정 - ALLOW/BLOCK/HOLD만 (BUY/SELL 아님)
decision = AIDecisionResult.allow(
    ticker="KRW-BTC",
    confidence=85,
    reason="Strong breakout confirmed",
)
```

#### 5.2 Port 인터페이스 (`src/application/ports/outbound/`)

| Port | 역할 | 주요 메서드 |
|------|------|------------|
| `PromptPort` | 프롬프트 생성/관리 | `get_current_version()`, `render_prompt()` |
| `ValidationPort` | 응답/판단 검증 | `validate_response()`, `validate_decision()` |
| `DecisionRecordPort` | 판단 기록 | `record()`, `link_pnl()`, `get_by_id()` |
| `IdempotencyPort` | 중복 주문 방지 | `check_key()`, `mark_key()`, `cleanup_expired()` |
| `LockPort` | 분산 락 관리 | `acquire()`, `release()`, `is_locked()`, `lock()` |
| `ExecutionPort` | 거래 체결 추상화 | `execute()`, `supports_intrabar()` |
| `TimeProviderPort` | 시간 추상화 | `now()`, `current_candle_time()` |

#### 5.3 UseCase (`src/application/use_cases/`)

**AnalyzeBreakoutUseCase** - 돌파 분석 통합 유스케이스

```python
from src.application.use_cases import (
    AnalyzeBreakoutUseCase,
    BreakoutAnalysisRequest,
    BreakoutAnalysisResult,
)

# UseCase 생성
use_case = AnalyzeBreakoutUseCase(
    prompt_port=yaml_prompt_adapter,
    validation_port=validation_adapter,
    decision_record_port=decision_record_adapter,
    ai_client=enhanced_openai_adapter,
)

# 분석 실행
result = await use_case.execute(BreakoutAnalysisRequest(
    ticker="KRW-BTC",
    current_price=Decimal("50000000"),
    market_summary=summary,
))

# result.decision.decision -> DecisionType.ALLOW
# result.record_id -> DB 기록 ID
# result.is_override -> 검증에 의해 override 되었는지
```

#### 5.4 Adapter 구현 (`src/infrastructure/adapters/`)

| Adapter | Port | 기능 |
|---------|------|------|
| `YAMLPromptAdapter` | PromptPort | YAML 템플릿 로드, Jinja2 렌더링, 해시 계산 |
| `ValidationAdapter` | ValidationPort | 응답 형식 검증, RSI/MACD 검증, HOLD override |
| `DecisionRecordAdapter` | DecisionRecordPort | PostgreSQL 저장, PnL 연결 |
| `EnhancedOpenAIAdapter` | AIClient | Rate limit, Circuit breaker, Retry, HOLD fallback |
| `PostgresIdempotencyAdapter` | IdempotencyPort | PostgreSQL `idempotency_keys` 테이블 기반 중복 방지 |
| `MemoryIdempotencyAdapter` | IdempotencyPort | In-Memory 기반 (테스트용) |
| `PostgresLockAdapter` | LockPort | PostgreSQL Advisory Lock (`pg_advisory_lock`) |
| `MemoryLockAdapter` | LockPort | In-Memory 기반 (테스트용) |
| `IntrabarExecutionAdapter` | ExecutionPort | 봉 중간 체결 시뮬레이션 (high/low 기반 스탑) |
| `SimpleExecutionAdapter` | ExecutionPort | 단순 체결 (봉 마감가) |
| `RiskStateRepository` | - | 리스크 상태 PostgreSQL 영속성 |

**Rate Limiter & Circuit Breaker**:
```python
from src.infrastructure.adapters.ai import (
    EnhancedOpenAIAdapter,
    RateLimiter,
    CircuitBreaker,
    CircuitState,
)

# 분당 20회 제한, 5회 연속 실패 시 60초 차단
adapter = EnhancedOpenAIAdapter(
    api_key="...",
    rate_limit_per_minute=20,
    circuit_breaker_threshold=5,
    recovery_timeout=60.0,
)

# Circuit 상태 확인
if adapter.circuit_breaker.state == CircuitState.OPEN:
    # 모든 요청 HOLD 반환
    ...
```

**검증 & Override**:
```python
# ALLOW + overbought RSI → 자동 HOLD 전환
validation_result = await validation_adapter.validate_decision(
    decision=AIDecisionResult.allow(...),
    market_context={"rsi": 80},  # > 75 threshold
)
# validation_result.override_decision == DecisionType.HOLD
```

#### 5.5 프롬프트 템플릿 (`src/infrastructure/prompts/`)

YAML 기반 버전 관리:

```yaml
# entry.yaml
name: entry_decision
version: "2.0.0"
description: "돌파 진입 허용/차단 판단"

template: |
  티커: {{ ticker }}
  현재가: {{ current_price }}
  시장 상태: {{ market_regime }}
  ATR%: {{ atr_percent }}

  JSON 형식으로 응답:
  {"decision": "allow|block|hold", "confidence": 0-100, "reason": "..."}

variables:
  - ticker
  - current_price
  - market_regime
  - atr_percent
```

**마이그레이션 가이드**: [MIGRATION_AI_CLEAN_ARCHITECTURE.md](./MIGRATION_AI_CLEAN_ARCHITECTURE.md)

---

### 6. AI 분석 시스템 레거시 (`src/ai/`) - DEPRECATED

> ⚠️ **DEPRECATED**: 새 코드는 `AnalyzeBreakoutUseCase` 사용 권장

#### AIService (`src/ai/service.py`)

- **역할**: 종합 시장 데이터를 분석하여 매수/매도/보유 결정 생성
- **입력**: 차트 데이터, 오더북, 기술적 지표, 포지션 정보, 백테스팅 결과
- **출력**: decision (buy/sell/hold), confidence, reason, regime_analysis, rejection_reasons

**🎯 리스크 헌터(Risk Hunter) 페르소나**:
- AI의 임무: "이 거래를 막을 이유를 적극적으로 찾는 것"
- 설득력 있는 이유가 없을 때만 거래 승인
- 확증 편향 방지를 위한 비판적 시각 유지

**Regime 분석 (핵심 질문)**:
> "현재의 변동성(ATR), 거래량, 오더북 상태가 지난 30일간 성과를 냈던 시장 환경과 유사합니까?"

**안전 조건 (5가지, 모두 충족 필요)**:
| 조건 | 설명 |
|------|------|
| 오더북 안전 | 매도벽 비율 < 5% (현재가 위 큰 매도벽 없음) |
| 추세 명확 | ADX > 25 (강한 추세 존재) |
| 거래량 확인 | 현재 거래량 > 평균의 1.5배 AND 가격 방향 일치 |
| BB 패턴 | 상단 터치 후 즉시 하락 패턴 아님 |
| Regime 일관성 | 현재 시장 환경이 최근 30일과 유사 |

**위험 조건 (6가지, 하나라도 있으면 중단)**:
| 조건 | 설명 |
|------|------|
| BTC 급락 위험 | 베타 > 1.2, 알파 < 0, BTC 하락 중 |
| RSI 다이버전스 | 가격 상승하지만 RSI 고점 하락 |
| 플래시 크래시 | 비정상적 급락 (ATR 대비 2배 이상) |
| 극단적 탐욕 | 공포탐욕지수 > 75 (과열 시장) |
| Price-Volume 괴리 | 가격 상승하지만 거래량 감소 |
| Alpha 음수 | BTC 대비 성과가 마이너스 |

**판단 기준**:
- **BUY**: 안전 조건 모두 충족 + 위험 조건 없음 + 막을 이유 못 찾음
- **HOLD**: 안전 조건 미충족 또는 위험 조건 1개 이상
- **SELL**: 위험 조건 2개 이상 또는 명백한 플래시 크래시

#### AIDecisionValidator (`src/ai/validator.py`)

- **역할**: AI 판단의 논리적 정합성 검증 ("Trust, but Verify")
- **검증 항목**:
  1. RSI 모순 체크
  2. ATR 변동성 체크
  3. Fakeout 감지
  4. 시장 환경 체크

### 6. 거래 실행 시스템 (`src/trading/`)

#### TradingService (`src/trading/service.py`)

- 실제 거래 주문 실행
- IExchangeClient 인터페이스 사용 (의존성 역전)
- 수수료 계산, 슬리피지 처리, 분할 주문

#### LiquidityAnalyzer (`src/trading/liquidity_analyzer.py`)

- 오더북 기반 실시간 슬리피지 계산
- 유동성 부족 시 거래 차단

### 7. 백테스팅 시스템 (`src/backtesting/`)

#### Backtester (`src/backtesting/backtester.py`)

- **역할**: 백테스팅 엔진 (과거 데이터 기반 전략 시뮬레이션)
- **주요 특징**:
  - **Look-Ahead Bias 방지**: `execute_on_next_open=True`로 t시점 종가 신호 → t+1시점 시가 체결
  - 슬리피지 모델: 퍼센트 기반 또는 오더북 기반
  - 분할 주문 지원
  - 성과 지표 연율화 (`data_interval` 파라미터)

#### QuickBacktestFilter (`src/backtesting/quick_filter.py`)

- **역할**: AI 호출 없이 12가지 퀀트 필터로 빠른 전략 검증
- **12가지 필터 조건** (모두 통과해야 실전 거래 진행):

| 카테고리 | 필터 | 기준값 | 설명 |
|---------|------|--------|------|
| **수익성** | 수익률 | ≥ 15% | 2년간 15% (연 7.5%) |
| | 승률 | ≥ 38% | 돌파 전략 특성상 낮지만 손익비로 보완 |
| | 손익비 (Profit Factor) | ≥ 1.8 | 수수료/슬리피지 고려 |
| **위험조정수익** | Sharpe Ratio | ≥ 1.0 | 기관 기준 1.0 미만은 투자 부적격 |
| | Sortino Ratio | ≥ 1.2 | 하방 리스크 고려 |
| | Calmar Ratio | ≥ 0.8 | 수익률/최대낙폭 |
| **리스크관리** | 최대 낙폭 (MDD) | ≤ 15% | 15% 초과 시 심리적 압박 |
| | 연속 손실 | ≤ 5회 | 5회 초과 시 전략 재검토 |
| | 연율 변동성 | ≤ 50% | 너무 높으면 위험 |
| **통계유의성** | 최소 거래 수 | ≥ 20 | 20회 이상이어야 통계적 의미 |
| **거래품질** | 평균 손익비 | ≥ 1.3 | 평균 수익/평균 손실 |
| | 평균 보유 시간 | ≤ 168h | 7일 초과 시 자본 효율 저하 |

#### RuleBasedBreakoutStrategy (`src/backtesting/rule_based_strategy.py`)

- **역할**: 변동성 돌파 전략 (AI 호출 없이 **4단계 관문** 룰 기반)
- **최신 퀀트 트렌드 반영**:

**진입 조건 (4단계 관문)**:
| Gate | 이름 | 조건 | 설명 |
|------|------|------|------|
| Gate 0 | 추세 필터 | 현재가 > MA(50) | 하락장 가짜 돌파(데드캣 바운스) 차단 |
| Gate 1 | 응축 확인 | BB 폭 < 평균 또는 ADX < 25 | 볼린저 밴드 폭 축소 확인 |
| Gate 2 | 돌파 발생 | 20일 고점 돌파 또는 래리 윌리엄스 | 동적 K값 지원 (노이즈 비율 기반) |
| Gate 3 | 거래량 확인 | Volume > 평균 × 1.5 또는 OBV 정배열 | 매수세 유입 확인 |

**청산 조건 (5가지)**:
| 조건 | 기준 | 설명 |
|------|------|------|
| 스탑로스 | ATR × 1.0 | 손실 보호 최우선 |
| Fakeout | 3봉 내 -2% | 진입 직후 급락 시 즉시 탈출 |
| 타겟가 | ATR × 1.5 | 손익비 1:1.5 익절 |
| ADX 약화 | ADX < 20 (급락) | 추세 반전 감지 |
| 타임아웃 | 24봉 + 수익률 < 2% | 모멘텀 부족 |

- **성능 최적화**: `prepare_indicators()`로 지표 사전 계산 (O(N²) → O(N))

## 🔄 시스템 워크플로우

### 1. 멀티코인 파이프라인 플로우 (use_multi_coin=True)

```
[scheduler_main.py / main.py 시작]
    ↓
[서비스 초기화]
  - UpbitClient, DataCollector
  - TradingService, AIService
  - PortfolioManager, CoinSelector
    ↓
[1단계: AdaptiveRiskCheckStage]
  [PortfolioManager 상태 확인]
    - 현재 포지션 수 확인
    - 일일/주간 손실 한도 체크
    - 거래 모드 결정
    ↓
    ├─ [BLOCKED] → ❌ 거래 중단 (Safe Mode)
    ├─ [MANAGEMENT] → 하이브리드 포지션 관리 (규칙 + AI)
    └─ [ENTRY] → ✅ 코인 스캐닝 진행
    ↓
[2단계: CoinScanStage] (ENTRY 모드에서만)
  [LiquidityScanner]
    - 업비트 KRW 마켓 전체 스캔
    - 거래대금 100억원+ 필터링
    - 상위 10개 코인 추출
    ↓
  [HistoricalDataSync]
    - 2년치 데이터 동기화
    - Parquet 형식 저장
    ↓
  [MultiCoinBacktest]
    - ThreadPoolExecutor 병렬 백테스팅
    - 12가지 퀀트 필터 적용
    - 상위 5개 코인 선택
    ↓
  [CoinSelector]
    - 최종 2개 코인 선택
    - 컨텍스트 티커 업데이트
    ↓
    ├─ [코인 없음] → ❌ 거래 중단 (조건 미달)
    └─ [코인 선택] → ✅ 데이터 수집 진행
    ↓
[3단계: DataCollectionStage]
  - 선택된 코인 차트 데이터 (+ BTC)
  - 오더북
  - BTC-코인 상관관계
    ↓
[4단계: AnalysisStage]
  [EntryAnalyzer]
    - 리스크 헌터 역할
    - 진입 신호 점수 계산
    - AI 판단 + 검증
    ↓
    ├─ [검증 실패] → ❌ 거래 중단
    └─ [검증 통과] → ✅ 거래 실행
    ↓
[5단계: ExecutionStage]
  - LiquidityAnalyzer 유동성 확인
  - 실제 주문 실행
  - 거래 기록 및 알림
```

### 2. 하이브리드 포지션 관리 플로우 (MANAGEMENT 모드)

```
[AdaptiveRiskCheckStage에서 MANAGEMENT 모드 분기]
    ↓
[PositionAnalyzer 실행]
    ↓
[규칙 기반 체크 (무료)]
  - 손절 체크: 수익률 <= -5%
  - 익절 체크: 수익률 >= +10%
  - Fakeout 체크: 3봉 내 -2%
  - 타임아웃 체크: 24시간 + 수익률 < 2%
  - ADX 약화 체크: < 20 (6시간 이후)
  - 트레일링 스탑: +5% 이상 시 조정
    ↓
    ├─ [규칙 발동] → 즉시 청산/보유 결정 ($0)
    └─ [애매한 상황] → AI 분석 필요
    ↓
[AI 분석 필요 조건 체크]
  - 수익 2% ~ 8% 구간
  - ADX 25-30 구간
  - 거래량-가격 괴리
    ↓
    ├─ [AI 불필요] → 규칙 기반 결정 ($0)
    └─ [AI 필요] → AIService 호출 (~$0.09)
    ↓
[청산/보류 실행]
```

### 3. 스케줄러 자동 트레이딩 (scheduler_main.py)

```
APScheduler (듀얼 타임프레임)
    │
    ├─ [매 1시간] trading_job()
    │       ↓
    │   서비스 초기화
    │       ↓
    │   execute_trading_cycle(enable_scanning=True) 호출
    │       ↓
    │   멀티코인 스캔 + AI 분석 + 진입 탐색
    │       ↓
    │   Telegram 5단계 알림
    │     1. 사이클 시작
    │     2. 스캔 진행 상황
    │     3. 백테스팅 결과
    │     4. AI 판단
    │     5. 포트폴리오 현황
    │       ↓
    │   Prometheus 메트릭 기록
    │
    └─ [매 15분] position_management_job()
            ↓
        보유 포지션 확인
            ↓
        execute_position_management_cycle() 호출
            ↓
        규칙 기반 손절/익절 체크 (AI 없음)
            ↓
        청산 시 Telegram 알림
```

**스케줄러 작업 목록**:
| 작업 | 주기 | 설명 | 안정성 |
|------|------|------|--------|
| `trading_job` | 매시 01분 | 멀티코인 스캔 + AI 분석 + 진입 탐색 | Lock + Idempotency |
| `position_management_job` | :01/:16/:31/:46 | 보유 포지션 손절/익절 관리 | Lock |
| `portfolio_snapshot_job` | 매시 01분 | 포트폴리오 스냅샷 DB 저장 | - |
| `daily_report_job` | 매일 09:00 | 일일 리포트 텔레그램 발송 | - |

**스케줄러 안정성 메커니즘**:
- **CronTrigger**: 캔들 마감 정렬 (IntervalTrigger 대체)
- **PostgreSQL Advisory Lock**: 작업 간 상호 배제 (`LOCK_IDS`: trading=1001, position=1002)
- **Idempotency Key**: 동일 캔들 중복 주문 방지 (`ticker-timeframe-candle_ts-action`)

## 🏗 계층 구조

```
┌─────────────────────────────────────────────────┐
│              Entry Layer (진입점)                 │
│  - main.py (실전 거래)                           │
│  - scheduler_main.py (스케줄러)                  │
└─────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│          Pipeline Layer (적응형 파이프라인)        │
│  - AdaptiveRiskCheckStage (포지션 분기)          │
│  - CoinScanStage (멀티코인 스캐닝)               │
│  - DataCollectionStage (데이터 수집)             │
│  - AnalysisStage (분석)                          │
│  - ExecutionStage (거래 실행)                    │
└─────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│           Service Layer (비즈니스 로직)            │
│  - EntryAnalyzer (진입 분석)                     │
│  - PositionAnalyzer (포지션 관리)                │
│  - PortfolioManager (포트폴리오 관리)            │
│  - CoinSelector (코인 선택)                      │
│  - TradingService (거래 실행)                    │
│  - RiskManager (리스크 관리)                     │
└─────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│           Scanner Layer (스캐닝 시스템)            │
│  - LiquidityScanner (유동성 스캔)                │
│  - HistoricalDataSync (데이터 동기화)            │
│  - MultiCoinBacktest (병렬 백테스팅)             │
└─────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│             Data Layer (데이터 계층)               │
│  - UpbitClient (API 클라이언트)                  │
│  - DataCollector (실시간 데이터)                 │
│  - HistoricalDataProvider (과거 데이터)          │
│  - TechnicalIndicators (기술적 지표)             │
└─────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│         Infrastructure Layer (인프라)             │
│  - Logger (로깅)                                 │
│  - Config (설정)                                 │
│  - PostgreSQL (Grafana 연동)                     │
│  - Parquet Storage (백테스팅 데이터)             │
│  - Prometheus (메트릭)                           │
└─────────────────────────────────────────────────┘
```

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
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### AI Decisions (AI 판단 로그)

```sql
CREATE TABLE ai_decisions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    decision VARCHAR(20) NOT NULL,
    confidence DECIMAL(5, 2),
    reason TEXT,
    analyzer_type VARCHAR(20),  -- 'entry' or 'position'
    market_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### Portfolio (포트폴리오 스냅샷)

```sql
CREATE TABLE portfolio_snapshots (
    id SERIAL PRIMARY KEY,
    total_value_krw DECIMAL(20, 2) NOT NULL,
    positions JSONB NOT NULL,  -- {symbol: {amount, value, profit_rate}}
    position_count INTEGER DEFAULT 0,
    trading_mode VARCHAR(20),  -- 'ENTRY', 'MANAGEMENT', 'BLOCKED'
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### Scan Results (스캔 결과) 🆕

```sql
CREATE TABLE scan_results (
    id SERIAL PRIMARY KEY,
    scan_type VARCHAR(20) NOT NULL,  -- 'liquidity', 'backtest', 'final'
    coins_scanned INTEGER,
    coins_passed INTEGER,
    selected_coins JSONB,  -- [{ticker, score, grade}]
    scan_duration_seconds DECIMAL(10, 2),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

## 💰 비용 분석

### 하이브리드 포지션 관리

| 상황 | AI 호출 | 비용 |
|------|--------|------|
| 손절/익절 발동 | ❌ 규칙 기반 | $0 |
| 명확한 HOLD | ❌ 규칙 기반 | $0 |
| 애매한 상황 (30%) | ✅ AI 분석 | ~$0.09 |
| **월 예상** | | **~$10** |

### 멀티코인 스캐닝

| 단계 | 호출 수 | 비용 |
|------|--------|------|
| 유동성 스캔 | 무료 (API) | $0 |
| 백테스팅 | 무료 (로컬) | $0 |
| AI 진입 분석 (5개/시간) | 720 * 5 = 3,600/월 | ~$32 |
| **총 월 예상** | | **~$42** |

## 📊 모니터링 메트릭

### 트레이딩 메트릭

```python
trades_total                  # 총 거래 수 (buy/sell 구분)
trade_volume_krw_total        # 총 거래 금액 (KRW)
trade_fee_krw_total           # 총 수수료 (KRW)
slippage_pct                  # 슬리피지 비율 (%)
```

### AI 메트릭

```python
ai_decisions_total            # AI 판단 수 (buy/sell/hold 구분)
ai_confidence                 # AI 신뢰도
ai_validation_failures_total  # AI 검증 실패 횟수
entry_analyzer_calls_total    # 진입 분석기 호출 수
position_analyzer_calls_total # 포지션 분석기 호출 수
```

### 🆕 멀티코인 스캐닝 메트릭

```python
coin_scan_total               # 코인 스캔 횟수
coins_scanned_total           # 스캔된 코인 수
coins_passed_backtest_total   # 백테스팅 통과 코인 수
coins_selected_total          # 최종 선택 코인 수
scan_duration_seconds         # 스캔 소요 시간
```

### 포트폴리오 메트릭

```python
portfolio_value_krw           # 포트폴리오 총 가치 (KRW)
portfolio_profit_rate         # 수익률 (%)
portfolio_position_count      # 현재 포지션 수
portfolio_trading_mode        # 거래 모드 (ENTRY/MANAGEMENT/BLOCKED)
```

### 리스크 관리 메트릭

```python
risk_circuit_breaker_triggers_total  # Circuit Breaker 발동 횟수
risk_stop_loss_triggers_total       # 손절 발동 횟수
risk_take_profit_triggers_total     # 익절 발동 횟수
risk_daily_pnl_pct                  # 일일 손익률 (%)
risk_safe_mode_active               # Safe Mode 활성 상태
```

## 🔐 보안 고려사항

1. **환경 변수**: `.env` 파일로 민감 정보 관리
2. **API 키 보안**: Upbit/OpenAI API 키 암호화 저장
3. **Rate Limiting**: Upbit API 분당 600회 제한 준수

## 📈 확장성 고려사항

1. **멀티코인 지원**: 최대 3개 코인 동시 거래 (확장 가능)
2. **다중 거래소**: 추상화된 거래소 인터페이스 (`IExchangeClient`)
3. **병렬 처리**: ThreadPoolExecutor로 백테스팅 병렬화
4. **클라우드 확장**: Kubernetes로 수평 확장

## 🎨 설계 원칙

### 1. 적응형 파이프라인 (Adaptive Pipeline)

- 포지션 유무에 따라 자동으로 다른 경로 실행
- ENTRY 모드: 스캐닝 → 진입 분석
- MANAGEMENT 모드: 하이브리드 포지션 관리

### 2. 비용 최적화 (Cost Optimization)

- 규칙 기반 우선: 70% 케이스 무료 처리
- AI는 애매한 상황에서만 호출 (30%)
- 월 $42 예상 비용

### 3. 퀀트 기준 필터링

- 12가지 필터 조건 (Sharpe, Sortino, Calmar 등)
- 통계적 유의성 확보 (최소 20회 거래)
- 리스크 관리 내장 (MDD 15%, 연속손실 5회)

### 4. 의존성 역전 원칙 (DIP)

- `TradingService`는 `IExchangeClient` 인터페이스에 의존
- 구체 구현체 교체 가능 (테스트 용이)

## 🏛 Clean Architecture (Hexagonal/Ports & Adapters)

### 아키텍처 다이어그램

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Presentation Layer                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │  CLI Runner     │  │   Scheduler     │  │   API (Future)  │         │
│  │ (trading_runner)│  │(scheduler_main) │  │                 │         │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘         │
└───────────┼─────────────────────┼─────────────────────┼─────────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Application Layer (Use Cases)                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │ExecuteTradeUseCase│ │AnalyzeMarketUseCase│ │ManagePositionUseCase│    │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘         │
│           │                    │                    │                   │
│           ▼                    ▼                    ▼                   │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │                        Ports (Interfaces)                    │       │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │       │
│  │  │ExchangePort│ │  AIPort   │ │MarketDataPort│ │PersistencePort│    │       │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │       │
│  └─────────────────────────────────────────────────────────────┘       │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────┐
│                            Domain Layer                                  │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │                     Entities                                  │       │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │       │
│  │  │  Trade   │  │  Order   │  │ Position │                   │       │
│  │  └──────────┘  └──────────┘  └──────────┘                   │       │
│  └─────────────────────────────────────────────────────────────┘       │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │                   Value Objects                               │       │
│  │  ┌──────────┐  ┌──────────┐                                  │       │
│  │  │  Money   │  │Percentage│                                  │       │
│  │  └──────────┘  └──────────┘                                  │       │
│  └─────────────────────────────────────────────────────────────┘       │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │                  Domain Services                              │       │
│  │  ┌──────────────┐  ┌──────────────┐                          │       │
│  │  │FeeCalculator │  │RiskCalculator│                          │       │
│  │  └──────────────┘  └──────────────┘                          │       │
│  └─────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────┘
                                    ▲
┌───────────────────────────────────┴─────────────────────────────────────┐
│                        Infrastructure Layer                              │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │                        Adapters                               │       │
│  │  ┌──────────────────┐  ┌──────────────────┐                  │       │
│  │  │UpbitExchangeAdapter│ │  OpenAIAdapter   │                  │       │
│  │  └──────────────────┘  └──────────────────┘                  │       │
│  │  ┌──────────────────┐  ┌──────────────────┐                  │       │
│  │  │UpbitMarketDataAdapter│ │InMemoryPersistence│                │       │
│  │  └──────────────────┘  └──────────────────┘                  │       │
│  └─────────────────────────────────────────────────────────────┘       │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │                   Legacy Bridge Adapters                      │       │
│  │  ┌──────────────────┐  ┌──────────────────┐                  │       │
│  │  │LegacyExchangeAdapter│ │ LegacyAIAdapter  │                  │       │
│  │  └──────────────────┘  └──────────────────┘                  │       │
│  │  ┌──────────────────┐                                        │       │
│  │  │LegacyMarketDataAdapter│                                      │       │
│  │  └──────────────────┘                                        │       │
│  └─────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────┘
```

### 레이어 설명

| 레이어 | 역할 | 의존성 방향 |
|--------|------|-------------|
| **Presentation** | 사용자 인터페이스 (CLI, Scheduler, API) | → Application |
| **Application** | 유즈케이스 오케스트레이션 | → Domain, ← Infrastructure (via Ports) |
| **Domain** | 순수 비즈니스 로직 (외부 의존성 없음) | 없음 |
| **Infrastructure** | 외부 시스템 어댑터 (Exchange, AI, DB) | → Application (Ports 구현) |

### 주요 컴포넌트

#### Domain Layer (`src/domain/`)
```
src/domain/
├── entities/
│   ├── trade.py           # Trade, Order, Position 엔티티
│   └── signal.py          # Signal 엔티티 (진입/청산 신호)
├── value_objects/
│   ├── money.py           # Money, Currency 값 객체
│   ├── percentage.py      # Percentage, Ratio 값 객체
│   ├── market_summary.py  # MarketSummary (regime, ATR%, 돌파강도)
│   ├── ai_decision_result.py  # AIDecisionResult (ALLOW/BLOCK/HOLD)
│   └── prompt_version.py  # PromptVersion (version, hash)
├── services/
│   ├── fee_calculator.py  # 수수료 계산 도메인 서비스
│   ├── risk_calculator.py # 리스크 평가 도메인 서비스
│   └── breakout_filter.py # BreakoutFilter (돌파 신호 필터링)
└── exceptions.py          # 도메인 예외
```

#### Application Layer (`src/application/`)
```
src/application/
├── ports/
│   └── outbound/
│       ├── exchange_port.py     # 거래소 포트 인터페이스
│       ├── ai_port.py           # AI 분석 포트 인터페이스
│       ├── market_data_port.py  # 시장 데이터 포트 인터페이스
│       ├── persistence_port.py  # 영속성 포트 인터페이스
│       ├── idempotency_port.py  # 중복 방지 포트 인터페이스
│       ├── lock_port.py         # 분산 락 포트 인터페이스
│       ├── prompt_port.py       # 프롬프트 관리 포트 인터페이스
│       ├── validation_port.py   # 검증 포트 인터페이스
│       ├── execution_port.py    # 체결 추상화 포트 인터페이스
│       ├── decision_record_port.py  # 판단 기록 포트 인터페이스
│       └── time_provider_port.py    # 시간 추상화 포트 인터페이스
├── use_cases/
│   ├── execute_trade.py    # 거래 실행 유즈케이스
│   ├── analyze_market.py   # 시장 분석 유즈케이스
│   ├── manage_position.py  # 포지션 관리 유즈케이스
│   └── analyze_breakout.py # 돌파 분석 유즈케이스 (통합)
├── services/
│   └── trading_orchestrator.py  # TradingOrchestrator (워크플로우 조율)
└── dto/
    ├── analysis.py         # 분석 관련 DTO
    └── trading.py          # 거래 관련 DTO
```

#### Infrastructure Layer (`src/infrastructure/`)
```
src/infrastructure/
├── adapters/
│   ├── exchange/
│   │   └── upbit_adapter.py           # Upbit ExchangePort 구현
│   ├── ai/
│   │   ├── openai_adapter.py          # OpenAI AIPort 구현
│   │   └── enhanced_openai_adapter.py # EnhancedOpenAI (Rate limit, Circuit breaker)
│   ├── market_data/
│   │   └── upbit_data_adapter.py      # Upbit MarketDataPort 구현
│   ├── persistence/
│   │   ├── memory_adapter.py          # In-Memory PersistencePort 구현
│   │   ├── memory_idempotency_adapter.py   # In-Memory IdempotencyPort
│   │   ├── memory_lock_adapter.py          # In-Memory LockPort
│   │   ├── postgres_idempotency_adapter.py # PostgreSQL IdempotencyPort
│   │   ├── postgres_lock_adapter.py        # PostgreSQL Advisory Lock
│   │   ├── decision_record_adapter.py      # DecisionRecordPort 구현
│   │   └── risk_state_repository.py        # RiskState PostgreSQL 저장소
│   ├── execution/
│   │   ├── simple_execution_adapter.py     # 단순 체결 (봉 마감가)
│   │   └── intrabar_execution_adapter.py   # Intrabar 체결 시뮬레이션
│   ├── prompt/
│   │   └── yaml_prompt_adapter.py     # YAML 프롬프트 관리
│   ├── validation/
│   │   └── validation_adapter.py      # 검증 로직 구현
│   └── legacy_bridge.py               # 레거시 서비스 브릿지 어댑터
└── prompts/
    ├── entry.yaml                     # 진입 판단 프롬프트
    ├── exit.yaml                      # 청산 판단 프롬프트
    └── general.yaml                   # 일반 분석 프롬프트
```

#### Presentation Layer (`src/presentation/`)
```
src/presentation/
└── cli/
    └── trading_runner.py   # CLI 트레이딩 러너
```

### DI Container (`src/container.py`)

의존성 주입 컨테이너가 모든 레이어를 연결합니다:

```python
from src.container import Container

# 프로덕션 사용
container = Container()
execute_trade = container.get_execute_trade_use_case()

# 테스트 사용 (Mock 어댑터)
container = Container.create_for_testing()

# 레거시 서비스 마이그레이션
container = Container.create_from_legacy(
    upbit_client=existing_upbit_client,
    ai_service=existing_ai_service,
    data_collector=existing_data_collector
)
```

### 레거시 마이그레이션 전략

기존 코드에서 Clean Architecture로 점진적 마이그레이션:

```python
# 기존 코드 (before)
from src.api.upbit_client import UpbitClient
upbit = UpbitClient()
result = upbit.buy_market_order("KRW-BTC", 100000)

# Clean Architecture (after)
from src.container import Container
container = Container.create_from_legacy(upbit_client=upbit)
execute_trade = container.get_execute_trade_use_case()
result = await execute_trade.execute_buy("KRW-BTC", Money.krw(100000))
```

### 테스트 전략

| 레이어 | 테스트 유형 | Mock 사용 |
|--------|-------------|-----------|
| Domain | Unit Test | 없음 (순수 로직) |
| Application | Unit Test | Port Interface Mock |
| Infrastructure | Integration Test | 외부 API Mock |
| Presentation | E2E Test | Container Mock |

```bash
# 전체 테스트 실행
python -m pytest tests/ -v

# 도메인 레이어만 테스트
python -m pytest tests/unit/domain/ -v

# 커버리지 확인
python -m pytest tests/ --cov=src --cov-report=html
```

## 📚 관련 문서

- **멀티코인 구현 가이드**: [MULTI_COIN_IMPLEMENTATION.md](./MULTI_COIN_IMPLEMENTATION.md) - 🆕 멀티코인 스캐닝 시스템 완벽 가이드
- **사용자 가이드**: [USER_GUIDE.md](./USER_GUIDE.md) - 설치부터 운영까지
- **Docker 가이드**: [DOCKER_GUIDE.md](./DOCKER_GUIDE.md) - Docker 실행 및 관리
- **스케줄러 가이드**: [SCHEDULER_GUIDE.md](./SCHEDULER_GUIDE.md) - 1시간 주기 자동 거래
- **모니터링 가이드**: [MONITORING_GUIDE.md](./MONITORING_GUIDE.md) - Grafana + Prometheus 설정
- **리스크 관리 설정**: [RISK_MANAGEMENT_CONFIG.md](./RISK_MANAGEMENT_CONFIG.md) - 리스크 관리 시스템 가이드

---

## 🔄 변경 이력

### v4.5.0 (2026-01-03) - 스케줄러 안정성 및 완전 마이그레이션 🆕

**주요 변경사항**:

1. **스케줄러 안정성 강화**
   - `IdempotencyPort`/`PostgresIdempotencyAdapter`: 동일 캔들 중복 주문 방지
   - `LockPort`/`PostgresLockAdapter`: PostgreSQL Advisory Lock 기반 분산 락
   - `CronTrigger` 전환: 캔들 마감 시점 정렬 (01분 실행)

2. **새 Port 인터페이스**
   - `IdempotencyPort`: 중복 방지 키 관리 (`check_key()`, `mark_key()`)
   - `LockPort`: 분산 락 (`acquire()`, `release()`, `lock()` context manager)
   - `ExecutionPort`: 체결 추상화 (`execute()`, `supports_intrabar()`)
   - `TimeProviderPort`: 시간 추상화 (테스트 용이성)

3. **새 Adapter 구현**
   - `PostgresIdempotencyAdapter`: `idempotency_keys` 테이블 기반
   - `PostgresLockAdapter`: `pg_advisory_lock` 사용
   - `MemoryIdempotencyAdapter`/`MemoryLockAdapter`: 테스트용
   - `IntrabarExecutionAdapter`: 봉 중간 체결 시뮬레이션
   - `RiskStateRepository`: 리스크 상태 PostgreSQL 저장

4. **Domain Layer 확장**
   - `Signal` 엔티티: 진입/청산 신호 모델
   - `BreakoutFilter` 서비스: 돌파 신호 필터링 로직

5. **Application Layer 확장**
   - `TradingOrchestrator`: 전체 거래 워크플로우 조율
   - `AnalyzeBreakoutUseCase`: 돌파 분석 통합 유즈케이스

6. **Container 확장**
   - `get_idempotency_port()`: IdempotencyPort 제공
   - `get_lock_port()`: LockPort 제공
   - 스케줄러에서 Container 완전 사용

**테스트**: 16,000+ 라인 추가, TDD 엄격 준수

---

### v4.4.0 (2026-01-03) - AI 클린 아키텍처 리팩토링

**주요 변경사항**:

1. **도메인 모델 정의**
   - `MarketSummary`: 시장 요약 Value Object (regime, ATR%, 돌파강도)
   - `AIDecisionResult`: AI 판단 결과 (ALLOW/BLOCK/HOLD)
   - `PromptVersion`: 프롬프트 버전 관리 (version, hash)

2. **Port 인터페이스**
   - `PromptPort`: 프롬프트 생성/렌더링
   - `ValidationPort`: 응답 검증, 결정 검증
   - `DecisionRecordPort`: 판단 기록, PnL 연결

3. **프롬프트 분리 및 표준화**
   - YAML 템플릿 기반 프롬프트 관리
   - `YAMLPromptAdapter`: Jinja2 렌더링, 해시 계산

4. **AI 어댑터 강화**
   - `EnhancedOpenAIAdapter`: Rate limit, Circuit breaker, Retry
   - `RateLimiter`: 슬라이딩 윈도우 방식 호출 제한
   - `CircuitBreaker`: CLOSED/OPEN/HALF_OPEN 상태 관리
   - 모든 에러 → HOLD fallback

5. **결정 추적성**
   - `DecisionRecordAdapter`: PostgreSQL 저장
   - `decision_records` 테이블: prompt_version, params, pnl 연결

6. **검증 로직 통합**
   - `ValidationAdapter`: 응답 형식, RSI/MACD 검증
   - ALLOW + overbought RSI → 자동 HOLD override

7. **UseCase 통합**
   - `AnalyzeBreakoutUseCase`: 돌파 분석 워크플로우 통합
   - `BreakoutAnalysisRequest/Result`: 표준화된 DTO

**마이그레이션 가이드**: [MIGRATION_AI_CLEAN_ARCHITECTURE.md](./MIGRATION_AI_CLEAN_ARCHITECTURE.md)

---

### v4.2.0 (2026-01-02) - 백테스팅 콜백 시스템

**주요 변경사항**:

1. **백테스팅 콜백 시스템**
   - `PipelineContext`에 `pending_backtest_callback_data` 필드 추가
   - `on_backtest_complete` 콜백 함수 지원 (비동기 처리)
   - 스캔 결과 없어도 최고 점수 코인 정보 텔레그램 전송

2. **HybridRiskCheckStage 개선**
   - 선택된 코인이 없어도 백테스팅 콜백 호출
   - `all_backtest_results`에서 최고 점수 코인 추출
   - 스캔 요약 정보 (liquidity_scanned, backtest_passed, best_score) 포함

3. **TradingPipeline 콜백 처리**
   - 스테이지 실행 후 `pending_backtest_callback_data` 자동 처리
   - 코루틴 콜백 await 지원
   - 파이프라인 종료/스킵 전 미처리 콜백 실행

4. **텔레그램 알림 개선**
   - AI 분석 전 백테스팅 결과 알림 전송
   - 멀티코인 스캐닝 상태 메시지
   - 실제 선택된 코인 정보로 알림 통합

---

### v4.1.0 (2026-01-02) - Clean Architecture 파이프라인 마이그레이션

**주요 변경사항**:

1. **파이프라인 비동기화**
   - 모든 파이프라인 스테이지를 async/await 패턴으로 전환
   - `BasePipelineStage.execute()` → `async def execute()`
   - UseCase들과 일관된 비동기 처리

2. **Container 기반 DI 도입**
   - `main.py`에서 `Container.create_from_legacy()` 초기화
   - `PipelineContext`에 `container` 필드 추가
   - 레거시 서비스와 UseCase 브릿지 연결

3. **ExecutionStage UseCase 마이그레이션**
   - Container 있으면 `ExecuteTradeUseCase` 사용
   - `Money` 값 객체로 정확한 금액 처리
   - `OrderResponse` → 레거시 dict 변환

4. **AnalysisStage UseCase 마이그레이션**
   - Container 있으면 `AnalyzeMarketUseCase` 사용
   - `TradingDecision` → `ai_result` dict 변환
   - 기존 분석 로직 (시장 상관관계, 플래시 크래시 등) 보존

5. **레거시 코드 Deprecated 처리**
   - `trading_service`, `ai_service` 필드에 DEPRECATED 표시
   - 향후 완전 제거 예정

**테스트**: 918개 통과, 0개 실패

---

### v4.0.0 (2026-01-02) - 멀티코인 스캐닝 시스템

**주요 변경사항**:

1. **멀티코인 스캐닝 모듈 추가** (`src/scanner/`)
   - LiquidityScanner: 업비트 유동성 상위 코인 스캔
   - HistoricalDataSync: Parquet 기반 데이터 동기화
   - MultiCoinBacktest: 12가지 퀀트 필터 병렬 백테스팅
   - CoinSelector: 5단계 코인 선택 파이프라인

2. **적응형 파이프라인 도입** (`src/trading/pipeline/`)
   - AdaptiveRiskCheckStage: 포지션 상태 기반 모드 분기
   - CoinScanStage: ENTRY 모드 멀티코인 스캐닝

3. **포지션 분리 시스템** (`src/ai/`, `src/position/`)
   - EntryAnalyzer: 진입 전용 분석기 (리스크 헌터)
   - PositionAnalyzer: 하이브리드 포지션 관리 (규칙 70% + AI 30%)
   - PortfolioManager: 최대 3개 코인 동시 관리

4. **퀀트 기준 강화**
   - 12가지 필터 조건 (Sharpe, Sortino, Calmar 등)
   - QuickBacktestConfig와 MultiBacktestConfig 동기화

5. **비용 최적화**
   - 규칙 기반 우선 처리 (70% 무료)
   - 월 예상 비용 ~$42

### v3.2.0 (2026-01-01) - 파이프라인 아키텍처 전환

- 4-Stage 파이프라인: Risk → Data → Analysis → Execution
- FastAPI Backend 제거 (Grafana 직접 PostgreSQL 연동)

### v3.1.0 (2025-12-31)

- 리스크 관리 시스템 통합
- AI 검증 레이어 강화
- 유동성 분석 모듈 추가

---

**현재 버전**: 4.5.0
**마지막 업데이트**: 2026-01-03
**아키텍처**: Clean Architecture + Scheduler Stability + Multi-Coin Scanning + Dual-Timeframe Pipeline
**상태**: 프로덕션 준비 완료 ✅
**문서 상태**: ✨ 스케줄러 안정성 및 완전 마이그레이션 완료
