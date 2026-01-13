# 🤖 스케줄러 가이드

> AI 자동매매 시스템의 **듀얼 타임프레임 (1시간 + 15분)** 자동 거래 스케줄러 완벽 가이드

**작성일**: 2026-01-02
**마지막 업데이트**: 2026-01-03
**버전**: 4.5.0
**상태**: ✅ 구현 완료 (CronTrigger + Lock/Idempotency 완전 적용)

---

## 📋 목차

1. [개요](#-개요)
2. [시스템 아키텍처](#-시스템-아키텍처)
3. [파이프라인 스테이지](#-파이프라인-스테이지)
4. [구현 내용](#-구현-내용)
5. [실행 방법](#-실행-방법)
6. [모니터링](#-모니터링)
7. [설정](#-설정)
8. [문제 해결](#-문제-해결)

---

## 🎯 개요

### 핵심 기능

AI 자동매매 시스템을 **듀얼 타임프레임 (1시간 + 15분)**으로 자동 실행하여 완전 자동화된 트레이딩을 제공합니다.

**스케줄러 작업 구성 (CronTrigger 기반):**

| 작업 | 실행 시점 | 설명 |
|------|----------|------|
| `trading_job` | **매시 01분** | 멀티코인 스캔 + 진입 탐색 (Lock 적용) |
| `position_management_job` | **:01,:16,:31,:46** | 보유 포지션 손절/익절 관리 (Lock 적용) |
| `portfolio_snapshot_job` | 매시 01분 | 포트폴리오 스냅샷 저장 |
| `daily_report_job` | 매일 09:00 | 일일 리포트 Telegram 전송 |

> **캔들 마감 정렬**: 캔들 마감(정각) 후 1분 버퍼를 두어 데이터 안정성 확보

**주요 특징:**
- ⏰ **CronTrigger** - 캔들 마감 시점에 정렬된 실행 (IntervalTrigger에서 전환)
- 🔒 **분산 락** - PostgreSQL Advisory Lock으로 작업 간 상호 배제
- 🔑 **Idempotency Key** - 동일 캔들 중복 주문 방지
- 🏭 **하이브리드 파이프라인** - HybridRiskCheckStage 기반 통합 아키텍처
- 🛡️ **리스크 관리 통합** - 손절/익절, Circuit Breaker, 거래 빈도 제어
- 🔍 **AI 분석 및 검증** - GPT-4 기반 시장 분석 및 의사결정
- 🔄 **자동 복구** - 에러 발생 시 자동 재시도
- 📱 **5단계 구조화 알림** - Telegram으로 상세한 거래 정보 전송
- 📊 **메트릭 수집** - Prometheus 통합 + PostgreSQL 저장
- 🐳 **Docker 지원** - 컨테이너 환경 완벽 지원
- 🛡️ **안전한 종료** - Graceful Shutdown 처리
- 📈 **일일 리포트** - 매일 오전 9시 자동 전송

### 달성된 목표

- ✅ 1시간마다 멀티코인 스캔 및 진입 탐색 (CronTrigger: 매시 01분)
- ✅ 15분마다 포지션 관리 (CronTrigger: :01,:16,:31,:46)
- ✅ 하이브리드 파이프라인 아키텍처 기반 거래 사이클
- ✅ **분산 락 (PostgreSQL Advisory Lock)** - 작업 간 상호 배제
- ✅ **Idempotency Key** - 동일 캔들 중복 주문 방지
- ✅ 에러 자동 복구 및 재시도
- ✅ 실행 상태 모니터링 및 로깅
- ✅ 수동 시작/중지 기능
- ✅ 안전한 종료 처리
- ✅ 동시 실행 방지 (max_instances=1 + Lock)
- ✅ Telegram 알림 통합 (5단계)
- ✅ Prometheus 메트릭 기록
- ✅ PostgreSQL DB 저장 (AI 결정, 거래 내역, Idempotency)
- ✅ 일일 리포트 자동 전송
- ✅ Sentry 에러 추적 통합

---

## 🏗 시스템 아키텍처

### 전체 구조

```
┌────────────────────────────────────────────────────────────┐
│       scheduler_main.py (24/7 실행)                         │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │        APScheduler (CronTrigger + Asia/Seoul)         │ │
│  │  - trading_job: 매시 01분 (1시간봉 마감 + 1분 버퍼)   │ │
│  │  - position_management_job: :01,:16,:31,:46 (15분봉)  │ │
│  │  - portfolio_snapshot_job: 매시 01분                  │ │
│  │  - daily_report_job: 매일 09:00                       │ │
│  └──────────────────┬───────────────────────────────────┘ │
└─────────────────────┼────────────────────────────────────┘
                      │
     ┌────────────────┴────────────────┐
     │                                 │
     ▼                                 ▼
┌─────────────────────────┐     ┌──────────────────────────┐
│    trading_job()        │     │  position_mgmt_job()     │
│  (매시 01분, Lock 적용) │     │  (:01,:16,:31,:46, Lock) │
│  - Lock 획득            │     │  - Lock 획득             │
│  - 멀티코인 스캔        │     │  - 손절/익절 체크        │
│  - 진입 분석            │     │  - 규칙 기반             │
│  - AI 분석              │     │  - Lock 해제             │
│  - Lock 해제            │     └──────────────────────────┘
└────────────┬────────────┘
             │
             ▼
┌───────────────────────────┐
│   execute_trading_cycle() │
│   (TradingOrchestrator)   │
└───────────┬───────────────┘
            │
    ┌─────────────────▼─────────────────┐
    │  Hybrid Trading Pipeline (4 Stage)│
    │                                   │
    │  ┌─────────────────────────────┐  │
    │  │ 1. HybridRiskCheckStage     │  │
    │  │    - 포지션 상태 확인        │  │
    │  │    - 모드 분기:             │  │
    │  │      ├─ ENTRY: 코인 스캔    │  │
    │  │      ├─ MGMT: 포지션 관리   │  │
    │  │      └─ BLOCKED: 리스크 초과│  │
    │  │    - 유동성 스캔 (10개)     │  │
    │  │    - 병렬 백테스팅          │  │
    │  │    - 최적 코인 선택         │  │
    │  └──────────────┬──────────────┘  │
    │                 │                  │
    │  ┌──────────────▼──────────────┐  │
    │  │ 2. DataCollectionStage      │  │
    │  │    - 차트 데이터 (멀티코인)  │  │
    │  │    - 오더북 분석             │  │
    │  │    - 기술적 지표 계산        │  │
    │  │    - 포지션 정보             │  │
    │  └──────────────┬──────────────┘  │
    │                 │                  │
    │  ┌──────────────▼──────────────┐  │
    │  │ 3. AnalysisStage            │  │
    │  │    - AI 분석 (GPT-4)        │  │
    │  │    - AI 검증 (RSI/ATR/ADX)  │  │
    │  └──────────────┬──────────────┘  │
    │                 │                  │
    │  ┌──────────────▼──────────────┐  │
    │  │ 4. ExecutionStage           │  │
    │  │    - 유동성 분석             │  │
    │  │    - 거래 실행               │  │
    │  │    - 결과 처리               │  │
    │  └─────────────────────────────┘  │
    └───────────────────────────────────┘
                      │
         ┌────────────▼─────────────┐
         │    Upbit Exchange API    │
         └──────────────────────────┘
```

### 데이터 흐름

```
1. 스케줄러 시작 (scheduler_main.py)
   └─> 환경변수 검증 (UPBIT, DATABASE_URL, OPENAI_API_KEY)
   └─> 데이터베이스 초기화
   └─> APScheduler 초기화 & 작업 등록
       ├─> trading_job (60분 주기, 즉시 실행)
       ├─> portfolio_snapshot_job (60분 주기)
       └─> daily_report_job (매일 09:00)

2. 매 1시간마다 trading_job() 실행
   └─> 📱 1단계 알림: 사이클 시작
   └─> 서비스 초기화 (UpbitClient, DataCollector, etc.)
   └─> 시장 데이터 수집 (현재가, RSI, MA 등)
   └─> execute_trading_cycle() 실행
       └─> HybridTradingPipeline.execute()
           └─> Stage 1: HybridRiskCheckStage
               ├─> 포지션 상태 확인 (ENTRY/MGMT/BLOCKED)
               ├─> ENTRY 모드: 유동성 스캔 (10개 코인)
               ├─> 병렬 백테스팅 (12가지 퀀트 필터)
               └─> 최적 코인 선택 (점수 기반)
           └─> Stage 2: DataCollectionStage
               ├─> 차트 데이터 수집 (선택된 코인)
               ├─> 오더북 분석
               └─> 기술적 지표 계산
           └─> Stage 3: AnalysisStage
               ├─> AI 분석 (GPT-4)
               └─> AI 검증 (RSI/ATR/ADX)
           └─> Stage 4: ExecutionStage
               ├─> 유동성 분석
               └─> 거래 실행

3. 결과 처리 (trading_job)
   └─> Prometheus 메트릭 기록
   └─> PostgreSQL DB 저장
       ├─> AIDecision 테이블 (모든 결정)
       └─> Trade 테이블 (매수/매도 시)
   └─> 📱 2단계 알림: 백테스팅 및 시장 분석
   └─> 📱 3단계 알림: AI 의사결정 상세
   └─> 📱 4단계 알림: 포트폴리오 현황

4. 에러 발생 시
   └─> 예외 처리
       └─> Sentry 에러 전송
       └─> Telegram 에러 알림
       └─> 실패 메트릭 기록
       └─> 다음 실행 대기 (자동 복구)
```

---

## 🏭 파이프라인 스테이지

### Stage 1: HybridRiskCheckStage

포지션 상태 확인 및 모드 분기 + 코인 스캔을 통합 처리합니다.

```python
# 파라미터 (기본값)
stop_loss_pct=-12.0       # 손절 비율
take_profit_pct=15.0      # 익절 비율
daily_loss_limit_pct=-10.0  # 일일 최대 손실
max_positions=2           # 최대 동시 포지션 수
liquidity_top_n=10        # 유동성 스캔 코인 수
min_volume_krw=10_000_000_000  # 최소 거래대금 (100억원)
```

**체크 항목:**
- 포지션 상태 확인 및 모드 결정 (ENTRY/MANAGEMENT/BLOCKED)
- ENTRY 모드: 유동성 스캔 → 백테스팅 → 최적 코인 선택
- MANAGEMENT 모드: 규칙 기반 손절/익절 + 하이브리드 AI 관리
- BLOCKED 모드: 리스크 초과 시 즉시 종료

### Stage 2: DataCollectionStage

거래 결정에 필요한 데이터를 수집합니다.

**수집 데이터:**
- 차트 데이터 (ETH, BTC 60일 일봉)
- 오더북 정보 및 요약
- 기술적 지표 (RSI, MACD, MA, BB 등)
- 현재 포지션 정보
- Fear & Greed Index

### Stage 3: AnalysisStage

수집된 데이터를 분석합니다.

**분석 항목:**
- 시장 상관관계 분석 (ETH-BTC)
- Flash Crash 감지
- RSI Divergence 분석
- 백테스팅 필터 (Rule-based)
- AI 분석 (GPT-4)
- AI 검증 (RSI/ATR/ADX 기반)

### Stage 4: ExecutionStage

분석 결과를 바탕으로 거래를 실행합니다.

**실행 로직:**
- 유동성 분석
- 슬리피지 계산
- 주문 실행 (매수/매도)
- 결과 처리

---

## 💻 구현 내용

### 파일 구조

```
dg_bot/
├── scheduler_main.py              # ⭐ 스케줄러 메인 진입점
│   ├── GracefulKiller (SIGINT/SIGTERM 처리)
│   ├── validate_environment_variables()
│   ├── main() - 스케줄러 루프
│   └── Sentry 초기화
│
├── main.py                        # ✅ 거래 사이클 정의
│   ├── execute_trading_cycle()    # 파이프라인 기반 거래 사이클
│   ├── main()                     # 단독 실행용
│   └── print_final_balance()
│
├── src/trading/pipeline/          # ✅ 파이프라인 모듈
│   ├── __init__.py               # 모듈 exports
│   ├── base_stage.py             # PipelineContext, StageResult, BasePipelineStage
│   ├── trading_pipeline.py       # TradingPipeline, create_spot_trading_pipeline()
│   ├── risk_check_stage.py       # RiskCheckStage
│   ├── data_collection_stage.py  # DataCollectionStage
│   ├── analysis_stage.py         # AnalysisStage
│   └── execution_stage.py        # ExecutionStage
│
├── backend/app/core/
│   ├── scheduler.py              # ✅ APScheduler 설정 및 작업 정의
│   │   ├── trading_job()         # 트레이딩 작업 (1시간)
│   │   ├── portfolio_snapshot_job()
│   │   ├── daily_report_job()    # 일일 리포트 (09:00)
│   │   ├── start_scheduler()
│   │   ├── stop_scheduler()
│   │   ├── pause_job() / resume_job()
│   │   └── get_jobs()
│   │
│   └── config.py                 # ✅ 설정
│       ├── SCHEDULER_INTERVAL_MINUTES = 60
│       └── SCHEDULER_ENABLED = True
│
├── start-scheduler.ps1           # Windows 실행 스크립트
├── start-scheduler.sh            # Linux/Mac 실행 스크립트
└── rebuild-scheduler.bat         # Docker 재빌드 스크립트
```

### 핵심 코드

#### 1. scheduler_main.py

```python
"""
스케줄러 전용 실행 파일
main.py 로직을 1시간마다 자동 실행합니다.
"""
import asyncio
import signal
from backend.app.core.scheduler import start_scheduler, stop_scheduler, get_jobs
from backend.app.services.notification import notify_bot_status
from backend.app.services.metrics import set_bot_running

class GracefulKiller:
    """Graceful Shutdown 핸들러"""
    kill_now = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        self.kill_now = True

async def main():
    killer = GracefulKiller()

    # 환경변수 검증 후 진행
    # 데이터베이스 초기화
    await init_db()

    # 봇 상태 업데이트 & Telegram 알림
    set_bot_running(True)
    await notify_bot_status(status="started", message="스케줄러가 시작되었습니다.")

    # 스케줄러 시작
    start_scheduler()

    # 무한 루프 (10초마다 상태 체크)
    while not killer.kill_now:
        await asyncio.sleep(10)

    # 종료 처리
    set_bot_running(False)
    await notify_bot_status(status="stopped", message="사용자가 스케줄러를 중지했습니다.")
    stop_scheduler()

def validate_environment_variables():
    """필수 환경변수 검증"""
    required_vars = {
        'UPBIT_ACCESS_KEY': 'Upbit API 액세스 키',
        'UPBIT_SECRET_KEY': 'Upbit API 시크릿 키',
        'DATABASE_URL': '데이터베이스 연결 URL',
        'OPENAI_API_KEY': 'OpenAI API 키'
    }
    # 누락된 변수 체크 후 False 반환 시 종료
```

#### 2. backend/app/core/scheduler.py

```python
# APScheduler 설정
scheduler = AsyncIOScheduler(
    timezone="Asia/Seoul",
    job_defaults={
        "coalesce": True,       # 누락된 작업 병합
        "max_instances": 1,     # 동시 실행 방지
        "misfire_grace_time": 60,  # 지연 허용 시간 (초)
    }
)

async def trading_job():
    """주기적 트레이딩 작업 (1시간마다)"""
    # 1. 서비스 초기화
    ticker = TradingConfig.TICKER
    upbit_client = UpbitClient()
    data_collector = DataCollector()
    trading_service = TradingService(upbit_client)
    ai_service = AIService()

    # 📱 1) 사이클 시작 알림
    await notify_cycle_start(symbol=ticker, status="started")

    # 2. 시장 데이터 수집 (텔레그램 로그용)
    market_data = collect_market_data()

    # 3. 거래 사이클 실행 (파이프라인)
    result = await execute_trading_cycle(
        ticker, upbit_client, data_collector,
        trading_service, ai_service
    )

    # 4. 결과 처리
    if result['status'] == 'success':
        # Prometheus 메트릭 기록
        record_ai_decision(symbol=ticker, decision=result['decision'], confidence=...)

        # PostgreSQL에 AI 판단 저장
        db_ai_decision = AIDecision(**ai_decision_data.model_dump())
        await db.commit()

        # PostgreSQL에 거래 기록 저장 (매수/매도 시)
        if result['decision'] in ['buy', 'sell']:
            await create_trade(trade_data, db)

        # 📱 2) 백테스팅 및 신호 분석 알림
        await notify_backtest_and_signals(...)

        # 📱 3) AI 의사결정 상세 알림
        await notify_ai_decision(...)

        # 📱 4) 포트폴리오 현황 알림
        await notify_portfolio_status(...)

async def daily_report_job():
    """일일 리포트 작업 (매일 오전 9시)"""
    await notify_daily_report(
        total_trades=24,
        profit_loss=profit_loss,
        profit_rate=profit_rate,
        current_value=current_value
    )

def add_jobs():
    """스케줄러에 작업 추가"""
    # 1. 트레이딩 작업 (1시간마다, 즉시 실행)
    scheduler.add_job(
        trading_job,
        trigger=IntervalTrigger(minutes=60, start_date=now),
        id="trading_job",
        name="주기적 트레이딩 작업 (1시간)",
    )

    # 2. 포트폴리오 스냅샷 (1시간마다)
    scheduler.add_job(
        portfolio_snapshot_job,
        trigger=IntervalTrigger(hours=1, start_date=now),
        id="portfolio_snapshot_job",
    )

    # 3. 일일 리포트 (매일 09:00)
    scheduler.add_job(
        daily_report_job,
        trigger=CronTrigger(hour=9, minute=0, timezone="Asia/Seoul"),
        id="daily_report_job",
    )
```

#### 3. main.py (파이프라인 기반)

```python
async def execute_trading_cycle(
    ticker: str,
    upbit_client: UpbitClient,
    data_collector: DataCollector,
    trading_service: TradingService,
    ai_service: AIService,
    trading_type: str = 'spot'
) -> Dict[str, Any]:
    """
    한 번의 거래 사이클 실행 (파이프라인 아키텍처)

    파이프라인 스테이지:
    1. RiskCheckStage: 리스크 체크 (손절/익절, Circuit Breaker, 거래 빈도)
    2. DataCollectionStage: 데이터 수집 (차트, 오더북, 기술적 지표)
    3. AnalysisStage: 분석 (시장 분석, 백테스팅, AI 분석, 검증)
    4. ExecutionStage: 거래 실행 (매수/매도/보류)

    Returns:
        {
            'status': 'success' | 'failed' | 'blocked' | 'skipped',
            'decision': 'buy' | 'sell' | 'hold',
            'confidence': float,
            'reason': str,
            'validation': str,
            'risk_checks': Dict,
            'pipeline_status': 'completed' | 'failed'
        }
    """
    # 파이프라인 생성
    pipeline = create_spot_trading_pipeline(
        stop_loss_pct=-12.0,
        take_profit_pct=15.0,
        daily_loss_limit_pct=-10.0,
        min_trade_interval_hours=4
    )

    # 컨텍스트 생성
    context = PipelineContext(
        ticker=ticker,
        trading_type=trading_type,
        upbit_client=upbit_client,
        data_collector=data_collector,
        trading_service=trading_service,
        ai_service=ai_service
    )

    # 파이프라인 실행
    result = await pipeline.execute(context)
    return result
```

---

## 🚀 실행 방법

### 방법 1: 로컬 실행

#### Windows (PowerShell)

```powershell
# 가상환경 활성화
.\venv\Scripts\Activate.ps1

# 스케줄러 시작
python scheduler_main.py

# 또는 스크립트 사용
.\start-scheduler.ps1

# 로그 확인 (별도 터미널)
Get-Content logs\scheduler\scheduler.log -Wait
```

#### Linux/Mac

```bash
# 가상환경 활성화
source venv/bin/activate

# 스케줄러 시작
python scheduler_main.py

# 또는 스크립트 사용
./start-scheduler.sh

# 로그 확인 (별도 터미널)
tail -f logs/scheduler/scheduler.log
```

**실행 결과:**
```
============================================================
🤖 AI 자동 트레이딩 스케줄러
============================================================
시작 시각: 2026-01-01 01:19:08
실행 주기: 1시간 (60분)
중지 방법: Ctrl + C
============================================================

✅ 데이터베이스 초기화 완료
✅ Telegram 시작 알림 전송 완료
✅ 스케줄러 시작됨
🚀 트레이딩 작업 즉시 실행 중...
✅ 트레이딩 작업이 즉시 실행되도록 예약됨

등록된 작업 목록 (3개):
  - trading_job: 주기적 트레이딩 작업 (1시간)
    다음 실행: 2026-01-01T01:19:08+09:00
  - portfolio_snapshot_job: 포트폴리오 스냅샷 저장
    다음 실행: 2026-01-01T01:19:08+09:00
  - daily_report_job: 일일 리포트 전송
    다음 실행: 2026-01-01T09:00:00+09:00

⏰ 스케줄러가 실행 중입니다... (Ctrl+C로 종료)
```

---

### 방법 2: Docker 실행 (권장)

#### 스케줄러만 실행

```bash
# 스케줄러 컨테이너 시작
docker-compose up -d scheduler

# 로그 확인
docker-compose logs scheduler -f

# 컨테이너 상태 확인
docker-compose ps

# 중지
docker-compose down
```

#### 전체 스택 실행

```bash
# 전체 서비스 시작 (PostgreSQL, Backend, Scheduler, Grafana 등)
docker-compose up -d

# 스케줄러 로그만 확인
docker-compose logs scheduler -f

# 전체 로그 확인
docker-compose logs -f

# 서비스 상태
docker-compose ps

# 중지
docker-compose down
```

**접속 정보:**
- Backend API: http://localhost:8000/docs
- Grafana: http://localhost:3001 (admin/admin)
- Prometheus: http://localhost:9090

---

### 방법 3: Docker 재빌드

코드 수정 후 이미지를 다시 빌드해야 할 때:

```bash
# Windows
.\rebuild-scheduler.bat

# Linux/Mac
docker-compose build scheduler
docker-compose up -d scheduler
```

---

## 📈 모니터링

### 로그 확인

#### 로컬 실행 시

```bash
# Windows
Get-Content logs\scheduler\scheduler.log -Wait

# Linux/Mac
tail -f logs/scheduler/scheduler.log
```

#### Docker 실행 시

```bash
# 실시간 로그
docker-compose logs scheduler -f

# 최근 100줄
docker-compose logs scheduler --tail 100

# 타임스탬프 포함
docker-compose logs scheduler -f --timestamps
```

### Prometheus 메트릭

스케줄러는 다음 메트릭을 수집합니다:

```
# 작업 성공 횟수
scheduler_job_success_total{job_name="trading_job"}

# 작업 실패 횟수
scheduler_job_failure_total{job_name="trading_job"}

# 작업 실행 시간 (초)
scheduler_job_duration_seconds{job_name="trading_job"}

# AI 결정 메트릭
ai_decision_total{symbol="KRW-ETH", decision="buy|sell|hold"}

# 거래 메트릭 (매수/매도 성공 시)
trade_total{symbol="KRW-ETH", side="buy|sell"}

# 봇 실행 상태
bot_running{status="true|false"}
```

**Prometheus 접속**: http://localhost:9090

### Grafana 대시보드

**접속**: http://localhost:3001
**계정**: admin / admin

**주요 패널:**
- 트레이딩 작업 실행 횟수
- 성공/실패 비율
- 평균 실행 시간
- AI 결정 분포 (buy/sell/hold)
- 포트폴리오 가치 변화

### PostgreSQL 저장 데이터

```sql
-- AI 판단 로그 조회
SELECT * FROM ai_decisions ORDER BY created_at DESC LIMIT 10;

-- 거래 내역 조회
SELECT * FROM trades ORDER BY created_at DESC LIMIT 10;

-- 포트폴리오 스냅샷
SELECT * FROM portfolio_snapshots ORDER BY created_at DESC LIMIT 10;
```

---

## 🔧 설정

### 환경 변수 (.env)

```env
# 필수 설정
UPBIT_ACCESS_KEY=your_upbit_access_key
UPBIT_SECRET_KEY=your_upbit_secret_key
OPENAI_API_KEY=sk-your_openai_api_key
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/trading_bot

# 스케줄러 설정
SCHEDULER_ENABLED=true
SCHEDULER_INTERVAL_MINUTES=60  # 1시간

# Telegram 알림 (선택)
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=123456789

# Sentry 에러 추적 (선택)
SENTRY_ENABLED=true
SENTRY_DSN=https://xxx@sentry.io/xxx
SENTRY_ENVIRONMENT=production

# 거래 설정
TRADING_SYMBOL=KRW-ETH
TRADING_MIN_ORDER_AMOUNT=5000  # 최소 주문 금액 (원)
TRADING_MAX_POSITION_RATIO=0.95  # 최대 포지션 비율

# 데이터베이스 설정 (Docker용)
POSTGRES_SERVER=postgres
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=trading_bot

# 모니터링
PROMETHEUS_ENABLED=true
```

### 실행 주기 변경

`.env` 파일에서 수정:

```env
# 30분마다 실행
SCHEDULER_INTERVAL_MINUTES=30

# 2시간마다 실행
SCHEDULER_INTERVAL_MINUTES=120

# 6시간마다 실행
SCHEDULER_INTERVAL_MINUTES=360
```

### 리스크 관리 파라미터

`main.py`의 `create_spot_trading_pipeline()` 호출 시 수정:

```python
pipeline = create_spot_trading_pipeline(
    stop_loss_pct=-12.0,          # 손절 비율 (-12%)
    take_profit_pct=15.0,         # 익절 비율 (+15%)
    daily_loss_limit_pct=-10.0,   # 일일 최대 손실 (-10%)
    min_trade_interval_hours=4     # 최소 거래 간격 (4시간)
)
```

---

## ❓ 문제 해결

### Q1. 스케줄러가 시작되지 않아요

**확인 사항:**
1. `.env` 파일이 존재하는지 확인
2. 필수 환경변수 설정 확인
3. Python 가상환경이 활성화되어 있는지 확인
4. 필수 패키지가 설치되어 있는지 확인

```bash
# 환경변수 누락 시 에러 메시지
❌ 필수 환경변수가 누락되었습니다
  - UPBIT_ACCESS_KEY: Upbit API 액세스 키
  - DATABASE_URL: 데이터베이스 연결 URL

# 의존성 재설치
pip install -r requirements.txt
# requirements-api.txt가 requirements.txt에 통합됨
```

### Q2. Docker에서 에러가 발생해요

**해결 방법:**

```bash
# 1. 로그 확인
docker-compose logs scheduler

# 2. 컨테이너 재시작
docker-compose restart scheduler

# 3. 이미지 재빌드
docker-compose build scheduler --no-cache
docker-compose up -d scheduler
```

### Q3. 1시간마다 실행되지 않아요

**확인 사항:**
1. `.env` 파일의 `SCHEDULER_INTERVAL_MINUTES` 확인
2. 스케줄러 로그에서 작업 등록 확인
3. 시스템 시간이 정확한지 확인

```bash
# 스케줄러 로그에서 확인
docker-compose logs scheduler | grep "등록된 작업"

# 다음 실행 시간 확인
docker-compose logs scheduler | grep "다음 실행"
```

### Q4. Telegram 알림이 오지 않아요

**확인 사항:**
1. `.env` 파일의 Telegram 설정 확인
2. `TELEGRAM_ENABLED=true` 확인
3. Bot Token이 올바른지 확인
4. Chat ID가 올바른지 확인

```bash
# Telegram 설정 테스트
python -c "
from backend.app.services.notification import notify_bot_status
import asyncio
asyncio.run(notify_bot_status('started', 'Test message'))
"
```

### Q5. 파이프라인 스테이지에서 에러가 발생해요

**확인 사항:**
1. 로그에서 어떤 스테이지에서 에러가 발생했는지 확인
2. Sentry 대시보드에서 상세 에러 정보 확인

```bash
# 스테이지별 에러 확인
docker-compose logs scheduler | grep "스테이지"

# 예시 에러 메시지
❌ RiskCheckStage 스테이지 실패: 손절 라인 도달
⏭️ DataCollectionStage 스테이지 스킵 (pre_execute 실패)
```

### Q6. 메모리 사용량이 높아요

**해결 방법:**
1. 로그 파일 정리
2. 오래된 Docker 이미지 삭제
3. PostgreSQL 데이터 정리

```bash
# 로그 정리
rm -rf logs/scheduler/*.log

# Docker 정리
docker system prune -a

# 오래된 AI 결정 삭제 (30일 이상)
docker exec -it dg_bot-postgres-1 psql -U postgres -d trading_bot -c "
DELETE FROM ai_decisions WHERE created_at < NOW() - INTERVAL '30 days';
"
```

---

## 🔗 관련 문서

- **[Docker 스케줄러 가이드](./DOCKER_SCHEDULER_GUIDE.md)** - Docker 실행 상세 가이드
- **[사용자 가이드](./USER_GUIDE.md)** - 전체 시스템 사용법
- **[모니터링 구현 계획](./MONITORING_IMPLEMENTATION_PLAN.md)** - 모니터링 시스템
- **[시스템 아키텍처](./ARCHITECTURE.md)** - 전체 시스템 구조
- **[리팩토링 리포트](./REFACTORING_REPORT_2026-01-01.md)** - 파이프라인 아키텍처 도입

---

## 📞 지원

문제가 해결되지 않으면:
1. [GitHub Issues](https://github.com/your-repo/bitcoin/issues) 등록
2. 로그 파일 첨부
3. 환경 정보 공유 (OS, Python 버전, Docker 버전)

---

## 🔄 변경 이력

### v4.5.0 (2026-01-03)
- **스케줄러 안정성 완전 구현**
  - `IdempotencyPort`/`PostgresIdempotencyAdapter`: 동일 캔들 중복 주문 방지
  - `LockPort`/`PostgresLockAdapter`: PostgreSQL Advisory Lock 기반 분산 락
  - `CronTrigger` 전환 완료: 캔들 마감 시점 정렬 (01분 실행)
- Container에서 Lock/Idempotency Port 제공
- TradingOrchestrator에서 Lock/Idempotency 통합 사용

### v4.1.0 (2026-01-02)
- Clean Architecture 마이그레이션 완료
- 파이프라인 스테이지 async/await 전환
- Container 기반 DI 도입
- UseCase 패턴 적용 (ExecuteTradeUseCase, AnalyzeMarketUseCase)

### v4.0.0 (2026-01-02)
- 멀티코인 스캐닝 시스템
- 적응형 파이프라인 도입

### v3.2.0 (2026-01-01)
- 파이프라인 아키텍처 적용
- 리스크 관리 시스템 통합

---

**작성자**: AI Assistant
**최종 업데이트**: 2026-01-03
**상태**: ✅ 스케줄러 안정성 완전 구현 (Lock + Idempotency)
