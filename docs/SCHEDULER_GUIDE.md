# 🤖 스케줄러 가이드

> AI 자동매매 시스템의 1시간 주기 자동 거래 스케줄러 완벽 가이드

**작성일**: 2025-12-28  
**상태**: ✅ 구현 완료 및 테스트 검증 완료  
**테스트 통과율**: 100% (16/16 테스트)

---

## 📋 목차

1. [개요](#-개요)
2. [시스템 아키텍처](#-시스템-아키텍처)
3. [구현 내용](#-구현-내용)
4. [실행 방법](#-실행-방법)
5. [테스트 결과](#-테스트-결과)
6. [모니터링](#-모니터링)
7. [문제 해결](#-문제-해결)

---

## 🎯 개요

### 핵심 기능

AI 자동매매 시스템을 **1시간 주기**로 자동 실행하여 완전 자동화된 트레이딩을 제공합니다.

**주요 특징:**
- ⏰ **1시간 주기 실행** - APScheduler 기반 정확한 스케줄링
- 🔄 **자동 복구** - 에러 발생 시 자동 재시도
- 🔔 **실시간 알림** - Telegram으로 거래 결과 전송
- 📊 **메트릭 수집** - Prometheus 통합
- 🐳 **Docker 지원** - 컨테이너 환경 완벽 지원
- 🛡️ **안전한 종료** - Graceful Shutdown 처리

### 달성된 목표

- ✅ 1시간마다 자동 거래 실행
- ✅ 에러 자동 복구 및 재시도
- ✅ 실행 상태 모니터링 및 로깅
- ✅ 수동 시작/중지 기능
- ✅ 안전한 종료 처리
- ✅ 동시 실행 방지
- ✅ Telegram 알림 통합
- ✅ Prometheus 메트릭 기록

---

## 🏗 시스템 아키텍처

### 전체 구조

```
┌────────────────────────────────────────────┐
│      scheduler_main.py (24/7 실행)         │
│                                            │
│  ┌──────────────────────────────────────┐ │
│  │        APScheduler                    │ │
│  │  (Asia/Seoul Timezone)                │ │
│  └──────────────┬───────────────────────┘ │
│                 │                          │
│     ┌───────────▼───────────┐             │
│     │   매 1시간마다         │             │
│     │   (IntervalTrigger)   │             │
│     └───────────┬───────────┘             │
└─────────────────┼────────────────────────┘
                  │
      ┌───────────▼───────────┐
      │    trading_job()      │
      │  (비동기 작업)         │
      └───────────┬───────────┘
                  │
      ┌───────────▼────────────────┐
      │  execute_trading_cycle()   │
      │  (main.py에서 가져옴)       │
      └───────────┬────────────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
┌───▼────┐  ┌────▼────┐  ┌────▼─────┐
│ Data   │  │   AI    │  │ Trading  │
│Collector│  │ Service │  │ Service  │
└────────┘  └─────────┘  └──────────┘
    │             │             │
    └─────────────┼─────────────┘
                  │
         ┌────────▼─────────┐
         │  Upbit Exchange  │
         └──────────────────┘
```

### 데이터 흐름

```
1. 스케줄러 시작
   └─> APScheduler 초기화
       └─> trading_job 등록 (60분 주기)

2. 정각마다 실행
   └─> trading_job() 호출
       └─> 서비스 초기화 (UpbitClient, DataCollector, etc.)
       └─> execute_trading_cycle() 실행
           └─> 차트 데이터 수집
           └─> AI 분석
           └─> 거래 결정 (buy/sell/hold)
           └─> 거래 실행 (매수/매도 시)
       └─> 결과 처리
           └─> Telegram 알림 전송
           └─> Prometheus 메트릭 기록
           └─> 로그 저장

3. 에러 발생 시
   └─> 예외 처리
       └─> Telegram 에러 알림
       └─> 실패 메트릭 기록
       └─> 다음 실행 대기 (복구)
```

---

## 💻 구현 내용

### 파일 구조

```
bitcoin/
├── scheduler_main.py              # ⭐ 스케줄러 메인 진입점
│   ├── APScheduler 설정
│   ├── SIGINT/SIGTERM 처리
│   └── 무한 루프 유지
│
├── main.py                        # ✅ 리팩토링 완료
│   ├── async def main()           # 비동기 변환
│   └── async def execute_trading_cycle()  # 거래 로직 분리
│
├── backend/app/core/
│   ├── scheduler.py               # ✅ 스케줄러 핵심 로직
│   │   ├── async def trading_job()         # 트레이딩 작업
│   │   ├── async def portfolio_snapshot_job()
│   │   ├── start_scheduler()
│   │   ├── stop_scheduler()
│   │   └── get_jobs()
│   │
│   └── config.py                  # ✅ 설정 업데이트
│       └── SCHEDULER_INTERVAL_MINUTES = 60
│
├── start-scheduler.ps1            # Windows 실행 스크립트
├── start-scheduler.sh             # Linux/Mac 실행 스크립트
└── rebuild-scheduler.bat          # Docker 재빌드 스크립트
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
from backend.app.core.scheduler import start_scheduler, stop_scheduler

async def main():
    # 스케줄러 시작
    start_scheduler()
    
    # 무한 루프 유지
    while True:
        await asyncio.sleep(3600)  # 1시간마다 체크

if __name__ == "__main__":
    asyncio.run(main())
```

#### 2. backend/app/core/scheduler.py

```python
async def trading_job():
    """주기적 트레이딩 작업 (1시간마다)"""
    try:
        # 서비스 초기화
        upbit_client = UpbitClient()
        data_collector = DataCollector()
        trading_service = TradingService(upbit_client)
        ai_service = AIService()
        
        # 거래 사이클 실행
        result = await execute_trading_cycle(
            ticker, upbit_client, data_collector,
            trading_service, ai_service
        )
        
        # 결과 처리 (알림, 메트릭)
        if result['status'] == 'success':
            # Telegram 알림
            await notify_trade(...)
            # 메트릭 기록
            record_ai_decision(...)
            
    except Exception as e:
        logger.error(f"에러 발생: {e}")
        await notify_error(...)
```

#### 3. main.py

```python
async def execute_trading_cycle(
    ticker: str,
    upbit_client: UpbitClient,
    data_collector: DataCollector,
    trading_service: TradingService,
    ai_service: AIService
) -> Dict[str, Any]:
    """한 번의 거래 사이클 실행"""
    # 차트 데이터 수집
    chart_data = await data_collector.get_chart_data(ticker)
    
    # AI 분석
    ai_result = await ai_service.analyze(chart_data)
    
    # 거래 실행
    if ai_result['decision'] == 'buy':
        result = await trading_service.buy(...)
    elif ai_result['decision'] == 'sell':
        result = await trading_service.sell(...)
    
    return {
        'status': 'success',
        'decision': ai_result['decision'],
        'confidence': ai_result['confidence'],
        'reason': ai_result['reason']
    }
```

---

## 🚀 실행 방법

### 방법 1: 로컬 실행

#### Windows (PowerShell)

```powershell
# 스케줄러 시작
.\start-scheduler.ps1

# 로그 확인 (별도 터미널)
Get-Content logs\scheduler\scheduler.log -Wait
```

#### Linux/Mac

```bash
# 스케줄러 시작
./start-scheduler.sh

# 로그 확인 (별도 터미널)
tail -f logs/scheduler/scheduler.log
```

**실행 결과:**
```
============================================================
🤖 AI 자동 트레이딩 스케줄러
============================================================
시작 시각: 2025-12-28 01:19:08
실행 주기: 1시간 (60분)
중지 방법: Ctrl + C
============================================================

✅ 스케줄러 시작됨

등록된 작업 목록 (2개):
  - trading_job: 주기적 트레이딩 작업 (1시간)
    다음 실행: 2025-12-28T02:19:08+00:00
  - portfolio_snapshot_job: 포트폴리오 스냅샷 저장
    다음 실행: 2025-12-28T02:19:08+00:00

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
docker-compose -f docker-compose.full-stack.yml up -d

# 스케줄러 로그만 확인
docker-compose -f docker-compose.full-stack.yml logs scheduler -f

# 전체 로그 확인
docker-compose -f docker-compose.full-stack.yml logs -f

# 서비스 상태
docker-compose -f docker-compose.full-stack.yml ps

# 중지
docker-compose -f docker-compose.full-stack.yml down
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

## 📊 테스트 결과

### 단위 테스트

```bash
# 스케줄러 테스트만 실행
python -m pytest tests/backend/app/core/test_scheduler.py -v
```

**결과:**
```
테스트 파일: tests/backend/app/core/test_scheduler.py
총 테스트: 16개
통과: 16개 (100%)
실패: 0개
소요 시간: 0.56초
```

#### 테스트 커버리지

| 테스트 카테고리      | 테스트 수 | 통과율 |
| -------------------- | --------- | ------ |
| 스케줄러 설정        | 3         | 100%   |
| 트레이딩 작업        | 4         | 100%   |
| 포트폴리오 스냅샷    | 1         | 100%   |
| 스케줄러 생명주기    | 4         | 100%   |
| 작업 관리            | 2         | 100%   |
| 통합 기능            | 2         | 100%   |

### 통합 테스트

```bash
# 전체 테스트 실행
python -m pytest tests/ -v --cov=src --cov=backend
```

**결과:**
```
총 테스트: 283개
통과: 278개 (98.2%)
실패: 5개 (스케줄러 무관)
코드 커버리지: 48%
소요 시간: 18.96초
```

### 검증된 기능

- ✅ **1시간 주기 실행** - 정확한 스케줄링 동작
- ✅ **거래 사이클** - buy/sell/hold 결정 및 실행
- ✅ **에러 처리** - 예외 발생 시 안전하게 복구
- ✅ **알림 전송** - Telegram 실시간 알림
- ✅ **메트릭 기록** - Prometheus 메트릭 수집
- ✅ **동시 실행 방지** - max_instances=1 설정
- ✅ **안전한 종료** - Graceful Shutdown

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
ai_decision_total{symbol="KRW-BTC", decision="buy|sell|hold"}
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

---

## 🔧 설정

### 환경 변수 (.env)

```env
# 필수 설정
UPBIT_ACCESS_KEY=your_upbit_access_key
UPBIT_SECRET_KEY=your_upbit_secret_key
OPENAI_API_KEY=sk-your_openai_api_key

# 스케줄러 설정
SCHEDULER_ENABLED=true
SCHEDULER_INTERVAL_MINUTES=60  # 1시간

# Telegram 알림 (선택)
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=123456789

# 거래 설정
TRADING_SYMBOL=KRW-BTC
TRADING_AMOUNT=50000  # 1회 거래 금액 (원)
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

---

## ❓ 문제 해결

### Q1. 스케줄러가 시작되지 않아요

**확인 사항:**
1. `.env` 파일이 존재하는지 확인
2. Python 가상환경이 활성화되어 있는지 확인
3. 필수 패키지가 설치되어 있는지 확인

```bash
# 의존성 재설치
pip install -r requirements.txt
pip install -r requirements-api.txt
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
```

### Q4. Telegram 알림이 오지 않아요

**확인 사항:**
1. `.env` 파일의 Telegram 설정 확인
2. Bot Token이 올바른지 확인
3. Chat ID가 올바른지 확인

```bash
# Telegram 설정 테스트
python -c "from backend.app.services.notification import notify_bot_status; import asyncio; asyncio.run(notify_bot_status('started', 'Test message'))"
```

### Q5. 메모리 사용량이 높아요

**해결 방법:**
1. 로그 파일 정리
2. 오래된 Docker 이미지 삭제
3. 백테스트 데이터 정리

```bash
# 로그 정리
rm -rf logs/scheduler/*.log

# Docker 정리
docker system prune -a
```

---

## 🔗 관련 문서

- **[Docker 스케줄러 가이드](./DOCKER_SCHEDULER_GUIDE.md)** - Docker 실행 상세 가이드
- **[사용자 가이드](./USER_GUIDE.md)** - 전체 시스템 사용법
- **[모니터링 구현 계획](./MONITORING_IMPLEMENTATION_PLAN.md)** - 모니터링 시스템
- **[시스템 아키텍처](./ARCHITECTURE.md)** - 전체 시스템 구조

---

## 📞 지원

문제가 해결되지 않으면:
1. [GitHub Issues](https://github.com/your-repo/bitcoin/issues) 등록
2. 로그 파일 첨부
3. 환경 정보 공유 (OS, Python 버전, Docker 버전)

---

**작성자**: AI Assistant  
**최종 업데이트**: 2025-12-28  
**상태**: ✅ 구현 완료 및 검증 완료



