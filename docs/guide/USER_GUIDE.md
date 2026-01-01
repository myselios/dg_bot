# AI 자동매매 시스템 사용 가이드

## 📋 목차

1. [빠른 시작 (5분)](#빠른-시작-5분)
2. [Docker로 전체 스택 실행](#docker로-전체-스택-실행)
3. [로컬 개발 환경 설정](#로컬-개발-환경-설정)
4. [백테스팅 실행](#백테스팅-실행)
5. [실전 거래 실행](#실전-거래-실행)
6. **[자동 거래 스케줄러 (1시간 주기)](#자동-거래-스케줄러)** ⭐
7. **[리스크 관리 시스템](#리스크-관리-시스템)** 🛡️ NEW!
8. [대시보드 사용법](#대시보드-사용법)
9. [알림 설정 (Telegram)](#알림-설정-telegram)
10. [모니터링 (Grafana)](#모니터링-grafana)
11. [설정 변경](#설정-변경)
12. [트러블슈팅](#트러블슈팅)
13. [운영 가이드](#운영-가이드)
14. [프로덕션 배포](#프로덕션-배포)

---

## 빠른 시작 (5분)

### 사전 준비

1. **Docker & Docker Compose 설치**

   ```bash
   # Docker 설치 확인
   docker --version
   docker-compose --version
   ```

2. **API 키 준비**
   - Upbit API 키 (필수): https://upbit.com/mypage/open_api_management
   - OpenAI API 키 (필수): https://platform.openai.com/api-keys
   - Telegram Bot 토큰 (선택): @BotFather를 통해 생성

### 3단계 실행

#### 1️⃣ 환경 변수 설정

```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# Linux/Mac
cp .env.example .env
```

`.env` 파일을 열고 최소 필수 설정을 입력하세요:

```bash
# 필수 설정
UPBIT_ACCESS_KEY=your_upbit_access_key
UPBIT_SECRET_KEY=your_upbit_secret_key
OPENAI_API_KEY=sk-your_openai_api_key

# 선택 설정
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=123456789
TELEGRAM_ENABLED=true
```

#### 2️⃣ 전체 스택 실행

```bash
# 모든 서비스 시작 (PostgreSQL, Backend, Scheduler, Prometheus, Grafana)
docker-compose -f docker-compose.full-stack.yml up -d
```

#### 3️⃣ 대시보드 접속

- **메인 대시보드**: http://localhost:3000
- **API 문서**: http://localhost:8000/api/v1/docs
- **Grafana 모니터링**: http://localhost:3001 (admin/admin)

### 작동 확인

```bash
# Backend API 헬스 체크
curl http://localhost:8000/health

# 봇 상태 확인
curl http://localhost:8000/api/v1/bot/status

# 거래 내역 조회
curl http://localhost:8000/api/v1/trades/
```

---

## Docker로 전체 스택 실행

### 서비스 구성

```yaml
services:
  postgres      # PostgreSQL 데이터베이스
  backend       # FastAPI 백엔드
  scheduler     # 자동 거래 스케줄러
  prometheus    # 메트릭 수집
  grafana       # 모니터링 대시보드
```

### 포트 매핑

| 서비스      | 포트 | 용도              |
| ----------- | ---- | ----------------- |
| Backend API | 8000 | REST API          |
| Grafana     | 3001 | 모니터링 대시보드 |
| Prometheus  | 9090 | 메트릭 조회       |
| PostgreSQL  | 5432 | 데이터베이스      |

### 기본 명령어

```bash
# 전체 스택 시작
docker-compose -f docker-compose.full-stack.yml up -d

# 특정 서비스만 시작
docker-compose -f docker-compose.full-stack.yml up -d backend frontend

# 서비스 중지
docker-compose -f docker-compose.full-stack.yml down

# 볼륨 포함 완전 삭제
docker-compose -f docker-compose.full-stack.yml down -v

# 로그 확인
docker-compose -f docker-compose.full-stack.yml logs -f

# Backend 로그만
docker-compose -f docker-compose.full-stack.yml logs -f backend

# 재시작
docker-compose -f docker-compose.full-stack.yml restart backend

# 재빌드 및 재시작
docker-compose -f docker-compose.full-stack.yml up -d --build
```

### 봇 제어

```bash
# 봇 시작
curl -X POST http://localhost:8000/api/v1/bot/control \
  -H "Content-Type: application/json" \
  -d '{"action": "start", "reason": "Manual start"}'

# 봇 중지
curl -X POST http://localhost:8000/api/v1/bot/control \
  -H "Content-Type: application/json" \
  -d '{"action": "stop", "reason": "Manual stop"}'
```

### Docker 없이 실행하기

각 서비스를 개별적으로 실행할 수도 있습니다:

```bash
# Backend만 실행
docker-compose up -d postgres
cd backend
uvicorn app.main:app --reload

# 스케줄러만 실행
python scheduler_main.py

# 트레이딩 봇만 실행 (로컬)
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
python main.py
```

---

## 로컬 개발 환경 설정

### 1. 가상환경 생성 및 활성화

```bash
# 가상환경 생성
python -m venv venv

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Windows (CMD)
venv\Scripts\activate.bat

# Linux/Mac
source venv/bin/activate
```

### 2. 의존성 설치

```bash
# 실전 거래 및 백테스팅용
pip install -r requirements.txt

# Backend API용 (추가)
pip install -r requirements-api.txt
```

### 3. 환경 변수 설정

`.env` 파일을 생성하고 다음 내용을 추가:

```bash
# Upbit API (필수)
UPBIT_ACCESS_KEY=your_access_key
UPBIT_SECRET_KEY=your_secret_key

# OpenAI API (필수)
OPENAI_API_KEY=sk-your_openai_api_key
OPENAI_MODEL=gpt-4o-mini

# Trading Config
TRADING_SYMBOL=KRW-ETH
TRADING_MIN_ORDER_AMOUNT=5000.0
TRADING_BUY_PERCENTAGE=0.3
TRADING_SELL_PERCENTAGE=1.0

# Database (Backend용)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/trading_bot

# Scheduler (Backend용)
SCHEDULER_ENABLED=true
SCHEDULER_INTERVAL_MINUTES=5

# Telegram (선택)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
TELEGRAM_ENABLED=false

# Sentry (선택)
SENTRY_DSN=your_sentry_dsn
SENTRY_ENABLED=false

# Logging
LOG_LEVEL=INFO
```

---

## 백테스팅 실행

### 1. 백테스팅 데이터 수집

백테스팅을 위해서는 먼저 과거 데이터를 수집해야 합니다.

```bash
# 가상환경 활성화
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate  # Linux/Mac

# 2024년 이더리움 데이터 수집
python scripts/backtesting/collect_eth_2024.py
```

수집되는 데이터:

- 일봉 데이터 (daily/)
- 시간봉 데이터 (hourly/)
- 15분봉 데이터 (minute/)

데이터는 `backtest_data/` 디렉토리에 CSV 파일로 저장됩니다.

### 2. 백테스팅 실행

```bash
# 수집된 데이터로 백테스팅 실행
python backtest.py
```

### 3. 백테스팅 결과 확인

백테스팅 실행 후 다음과 같은 성과 지표가 출력됩니다:

- 총 수익률
- 승률
- 최대 낙폭 (Max Drawdown)
- Sharpe Ratio
- Sortino Ratio
- 평균 손익
- Profit Factor
- 거래 통계

### 4. 다른 종목/기간 백테스팅

```python
from datetime import datetime
from scripts.backtesting.data_manager import BacktestDataManager

manager = BacktestDataManager(data_dir='backtest_data')

# 비트코인 2024년 데이터 수집
data = manager.collect_and_cache(
    ticker='KRW-BTC',
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 12, 31)
)

# 백테스팅 실행
# backtest.py의 ticker 설정을 'KRW-BTC'로 변경 후 실행
```

### 5. 여러 종목 일괄 수집

```python
from datetime import datetime
from scripts.backtesting.data_manager import BacktestDataManager

manager = BacktestDataManager()

major_coins = [
    'KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-SOL',
    'KRW-ADA', 'KRW-DOGE', 'KRW-AVAX', 'KRW-DOT'
]

manager.collect_multiple_tickers(
    tickers=major_coins,
    start_date=datetime(2024, 1, 1)
)
```

---

## 실전 거래 실행

⚠️ **경고**: 실전 거래는 실제 자금을 사용합니다. 반드시 백테스팅을 충분히 수행하고, 소액으로 테스트한 후 진행하세요.

### 1. 백테스팅 검증 (필수)

실전 거래 전에 최근 데이터로 백테스팅을 수행하여 전략 성능을 검증하세요.

```bash
# 최근 30일 데이터로 빠른 백테스팅
python main.py  # 자동으로 빠른 백테스팅 필터 실행
```

### 2. 실전 거래 실행

```bash
# 가상환경 활성화
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate  # Linux/Mac

# 실전 거래 실행
python main.py
```

### 3. 실전 거래 플로우

```
1. 리스크 체크 (최우선) 🛡️
   - 손절/익절 자동 발동 체크
   - Circuit Breaker (일일/주간 손실 한도)
   - 거래 빈도 제한 (최소 간격)
   ↓
2. 빠른 백테스팅 필터
   - 룰 기반 전략으로 사전 필터링 (AI 호출 없음)
   ↓
3. 시장 데이터 수집
   - 차트 데이터, 오더북, BTC 상관관계
   - 플래시 크래시 감지, RSI 다이버전스
   ↓
4. 기술적 지표 계산
   - RSI, MACD, Bollinger Bands, ADX, ATR
   ↓
5. AI 분석 (GPT-4)
   - 시장 환경 종합 분석
   - 매매 결정 (buy/sell/hold)
   ↓
6. AI 판단 검증 (2-Stage Validation) 🔍
   - RSI 모순 체크
   - 변동성 체크 (ATR)
   - Fakeout 감지 (ADX + 거래량)
   - 시장 환경 체크 (BTC 리스크, 플래시 크래시)
   ↓
7. 거래 실행
   - 유동성 분석 (슬리피지 계산)
   - 주문 실행 (분할 주문 지원)
   - 리스크 상태 업데이트
   ↓
8. 결과 기록 및 알림
   - PostgreSQL 저장
   - Telegram 알림 (4단계 구조)
   - Prometheus 메트릭
```

### 4. 주기적 실행 (스케줄러) - 1시간 주기 자동 거래

⏰ **새로운 기능**: main.py를 1시간마다 자동 실행하는 전용 스케줄러가 추가되었습니다!

#### 방법 1: 전용 스케줄러 사용 (권장) ⭐

**Windows PowerShell:**

```powershell
# 스케줄러 시작
.\start-scheduler.ps1

# 또는 수동 실행
python scheduler_main.py
```

**Linux/Mac:**

```bash
# 스크립트 실행 권한 부여
chmod +x start-scheduler.sh

# 스케줄러 시작
./start-scheduler.sh

# 또는 수동 실행
python scheduler_main.py
```

**스케줄러 특징:**

- ✅ 1시간(60분) 주기로 자동 실행
- ✅ Telegram 실시간 알림 (시작/거래/에러)
- ✅ Prometheus 메트릭 자동 수집
- ✅ Graceful Shutdown (Ctrl+C로 안전 종료)
- ✅ 에러 발생 시 자동 복구
- ✅ 로그 파일 자동 저장 (`logs/scheduler/`)

**중지 방법:**

- Ctrl + C 키를 눌러 안전하게 종료합니다.
- 현재 실행 중인 거래가 완료된 후 종료됩니다.

#### 방법 2: Backend API 사용

```bash
# docker-compose로 실행 (자동 스케줄링)
docker-compose -f docker-compose.full-stack.yml up -d backend
```

Backend는 APScheduler를 사용하여 기본 5분마다 자동으로 거래를 실행합니다.

**로컬 실행 시**:

Windows 작업 스케줄러 또는 Linux cron을 사용하여 주기적으로 실행할 수 있습니다.

```bash
# cron 예시 (5분마다 실행)
*/5 * * * * cd /path/to/bitcoin && /path/to/venv/bin/python main.py >> logs/trading.log 2>&1
```

---

## 자동 거래 스케줄러

⏰ **1시간 주기 자동 거래**: main.py를 1시간마다 자동으로 실행하는 전용 스케줄러입니다.

### 스케줄러 시작

#### Windows PowerShell

```powershell
# 방법 1: 전용 스크립트 사용 (권장)
.\start-scheduler.ps1

# 방법 2: 수동 실행
.\venv\Scripts\Activate.ps1
python scheduler_main.py
```

#### Linux/Mac

```bash
# 방법 1: 전용 스크립트 사용 (권장)
chmod +x start-scheduler.sh
./start-scheduler.sh

# 방법 2: 수동 실행
source venv/bin/activate
python scheduler_main.py
```

### 스케줄러 중지

- **Ctrl + C**를 눌러 안전하게 종료합니다.
- 현재 실행 중인 거래가 완료된 후 종료됩니다.
- Telegram으로 종료 알림이 전송됩니다.

### 로그 확인

#### 실시간 로그 확인

**Windows PowerShell:**

```powershell
# 스케줄러 로그
Get-Content logs\scheduler\scheduler.log -Wait

# 최근 50줄 확인
Get-Content logs\scheduler\scheduler.log -Tail 50
```

**Linux/Mac:**

```bash
# 스케줄러 로그
tail -f logs/scheduler/scheduler.log

# 최근 50줄 확인
tail -n 50 logs/scheduler/scheduler.log
```

#### 로그 파일 위치

- `logs/scheduler/scheduler.log` - 스케줄러 실행 로그
- `logs/trading.log` - 거래 실행 로그 (JSON 형식)

### 실행 주기 변경

`.env` 파일에서 주기를 변경할 수 있습니다:

```env
# 1시간 (기본값)
SCHEDULER_INTERVAL_MINUTES=60

# 30분마다 실행하려면
SCHEDULER_INTERVAL_MINUTES=30

# 2시간마다 실행하려면
SCHEDULER_INTERVAL_MINUTES=120
```

**변경 후 스케줄러 재시작 필요**

### 주의사항

#### ✅ 권장 사항

- 백테스팅 검증 후 실행
- 충분한 원화 잔고 확보
- Telegram 알림 설정 (에러 감지용)
- 24시간 실행 시 컴퓨터 절전 모드 해제

#### ⚠️ 주의사항

- 인터넷 연결 안정성 확인
- API 키 유효성 확인
- 로그 파일 용량 주기적 확인
- 백업 전략 수립

### Telegram 알림 종류

스케줄러는 다음 상황에서 자동으로 알림을 전송합니다:

1. **시작 알림**: 스케줄러 시작 시
2. **거래 알림**: 매수/매도 실행 시
3. **에러 알림**: 오류 발생 시
4. **종료 알림**: 스케줄러 중지 시

### 모니터링

#### Prometheus 메트릭

스케줄러는 다음 메트릭을 자동으로 수집합니다:

- `scheduler_job_duration_seconds` - 작업 실행 시간
- `scheduler_job_success_total` - 성공 횟수
- `scheduler_job_failure_total` - 실패 횟수
- `trades_total` - 총 거래 수
- `ai_decisions_total` - AI 판단 수
- `portfolio_value_krw` - 포트폴리오 가치

Grafana 대시보드에서 실시간 모니터링이 가능합니다: http://localhost:3001

### 트러블슈팅

#### 문제: 스케줄러가 시작되지 않음

**원인**: 필수 패키지 미설치

**해결**:

```bash
# requirements-api.txt 설치
pip install -r requirements-api.txt
```

#### 문제: .env 파일 없음 에러

**원인**: 환경 변수 파일 미생성

**해결**:

```bash
# Windows
Copy-Item env.example .env

# Linux/Mac
cp env.example .env

# .env 파일에 API 키 입력
```

#### 문제: 거래가 실행되지 않음

**원인**: 백테스팅 필터링 조건 미달

**해결**:

- 로그에서 백테스팅 결과 확인
- 전략 성능이 기준에 미달하는 경우 정상 동작
- `quick_backtest_result.passed == False` 상태

#### 문제: Telegram 알림이 오지 않음

**원인**: Telegram 설정 미완료

**해결**:

```env
# .env 파일 확인
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Docker로 스케줄러 실행 🐳

#### 방법 1: 스케줄러 단독 실행 (간단)

```bash
# 스케줄러만 실행
docker-compose up -d scheduler

# 로그 확인
docker-compose logs -f scheduler

# 중지
docker-compose stop scheduler
```

#### 방법 2: 전체 스택 실행 (권장)

```bash
# 전체 스택 실행 (PostgreSQL, Backend, Scheduler, Grafana 등)
docker-compose -f docker-compose.full-stack.yml up -d

# 스케줄러 로그 확인
docker-compose -f docker-compose.full-stack.yml logs -f scheduler

# 중지
docker-compose -f docker-compose.full-stack.yml down
```

#### 포함 서비스

- ⏰ **Scheduler** - 1시간 주기 자동 거래
- 📊 **PostgreSQL** - 거래 데이터 저장
- 🚀 **Backend API** - REST API 서버
- 📈 **Prometheus** - 메트릭 수집
- 📊 **Grafana** - 실시간 대시보드
- 🖥️ **Frontend** - Next.js UI

#### 접속 정보

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000/docs
- **Grafana**: http://localhost:3001 (admin/admin)
- **Prometheus**: http://localhost:9090

#### 상세 가이드

자세한 Docker 설정, 컨테이너 관리 및 트러블슈팅은 [Docker 가이드](./DOCKER_GUIDE.md)를 참고하세요.

---

## 리스크 관리 시스템

🛡️ **NEW**: 실전 투자를 위한 종합 리스크 관리 시스템이 통합되었습니다.

### 개요

리스크 관리 시스템은 거래 사이클의 **최우선 단계**로 실행되어 자본 손실을 방지합니다.

#### 주요 기능

1. **손절/익절 자동 발동** (Stop Loss / Take Profit)
   - 고정 비율 방식: 손절 -5%, 익절 +10%
   - ATR 기반 동적 방식: 변동성에 따라 자동 조정

2. **Circuit Breaker** (손실 한도 차단)
   - 일일 최대 손실: -10%
   - 주간 최대 손실: -15%
   - 한도 초과 시 자동 거래 중단

3. **거래 빈도 제한**
   - 최소 거래 간격: 4시간
   - 일일 최대 거래 횟수: 5회
   - 과도한 매매 방지

4. **포지션 사이징** (Kelly Criterion)
   - 승률 기반 최적 포지션 크기 계산
   - 자본 관리 자동화

5. **트레일링 스탑** (선택사항)
   - 수익 보호 메커니즘
   - ATR 기반 동적 손절가 상승

6. **분할 익절** (선택사항)
   - 1차 익절 +5%: 50% 매도
   - 2차 익절 +10%: 나머지 50% 매도

### 설정 방법

#### 기본 설정 (main.py)

`main.py`의 `execute_trading_cycle()` 함수에서 리스크 한도를 설정합니다:

```python
risk_manager = RiskManager(
    limits=RiskLimits(
        stop_loss_pct=-5.0,          # 손절: -5%
        take_profit_pct=10.0,        # 익절: +10%
        daily_loss_limit_pct=-10.0,  # 일일 최대 손실: -10%
        min_trade_interval_hours=4,  # 최소 거래 간격: 4시간
    )
)
```

**파일 위치**: `/home/selios/dg_bot/main.py` (120-127번째 줄)

#### 리스크 프로필별 추천 설정

**보수적 프로필** (초보자, 안정 추구):

```python
limits=RiskLimits(
    stop_loss_pct=-3.0,          # 손절 타이트
    take_profit_pct=8.0,         # 빠른 이익 실현
    daily_loss_limit_pct=-5.0,   # 일일 손실 한도 엄격
    min_trade_interval_hours=6,  # 신중한 거래
)
```

**균형 프로필** (권장) ⭐:

```python
limits=RiskLimits(
    stop_loss_pct=-5.0,          # 손절: -5%
    take_profit_pct=10.0,        # 익절: +10% (R:R 2:1)
    daily_loss_limit_pct=-10.0,  # 일일 손실 한도
    min_trade_interval_hours=4,  # 적절한 거래 빈도
)
```

**공격적 프로필** (경험자, 고수익 추구):

```python
limits=RiskLimits(
    stop_loss_pct=-7.0,          # 변동성 허용
    take_profit_pct=15.0,        # 큰 수익 목표
    daily_loss_limit_pct=-15.0,  # 느슨한 한도
    min_trade_interval_hours=2,  # 빈번한 거래
)
```

### 상태 영속성 (JSON 기반)

리스크 관리 상태는 프로그램 재시작 후에도 유지됩니다.

**저장 위치**: `data/risk_state.json`

**저장 내용**:
```json
{
  "2026-01-01": {
    "daily_pnl": -3.5,
    "daily_trade_count": 2,
    "last_trade_time": "2026-01-01T14:30:00",
    "weekly_pnl": -5.2,
    "safe_mode": false,
    "safe_mode_reason": "",
    "updated_at": "2026-01-01T16:00:00"
  }
}
```

**자동 관리**:
- 최근 7일간 데이터 유지 (주간 손실 계산용)
- 7일 이전 데이터 자동 삭제
- 거래 시마다 자동 저장

### 작동 원리

#### 1. 손절/익절 자동 발동

포지션 보유 시 매 사이클마다 손익률을 체크합니다:

```
현재가: 105만원
평균 매수가: 100만원
손익률: +5%

- 손절 기준 -5% 미만: ❌ (정상)
- 익절 기준 +10% 이상: ❌ (아직)
→ 포지션 유지
```

**익절 발동 예시**:

```
현재가: 111만원
평균 매수가: 100만원
손익률: +11%

→ ✅ 익절 발동 (+10% 초과)
→ 즉시 전량 매도
→ 손익 기록 (+11%)
```

#### 2. Circuit Breaker

일일/주간 누적 손실이 한도를 초과하면 거래가 차단됩니다:

```
일일 누적 손실: -12%
일일 한도: -10%

→ ⛔ Circuit Breaker 발동
→ 안전 모드 활성화
→ 오늘 거래 중단 (다음 날 자정 해제)
```

#### 3. 거래 빈도 제한

마지막 거래 이후 최소 간격이 지나야 새 거래가 허용됩니다:

```
마지막 거래: 14:00
현재 시각: 16:00
경과 시간: 2시간

최소 간격: 4시간
→ ⏭️ 거래 스킵 (2시간 부족)
```

### 모니터링

#### 로그 확인

리스크 체크 결과는 로그에 실시간으로 기록됩니다:

```bash
# 손절 발동 로그
🚨 손절 발동: -5.2% <= -5.0%

# Circuit Breaker 로그
⛔ Circuit Breaker 발동: 일일 손실 한도 초과 (-10.5% <= -10.0%)

# 거래 빈도 제한 로그
⏭️ 거래 스킵: 최소 거래 간격 미달 (2.0시간 < 4.0시간)
```

#### Telegram 알림

리스크 이벤트는 Telegram으로 즉시 알림됩니다:

- 손절/익절 발동 시
- Circuit Breaker 발동 시
- 거래 빈도 제한 시

### 주의사항

#### ⚠️ 백테스팅 필수

리스크 설정 변경 후 반드시 백테스팅을 수행하세요:

```bash
python backtest.py
```

**최소 검증 기준**:
- MDD (Maximum Drawdown) < 15%
- Win Rate > 50%
- Sharpe Ratio > 1.0
- 리스크-리워드 비율 ≥ 1.5

#### ⚠️ 리스크-리워드 비율

손절과 익절 비율을 적절히 설정하세요:

| 손절 | 익절 | 비율 | 평가 |
|------|------|------|------|
| -5% | +5% | 1.0 | ❌ 너무 낮음 |
| -5% | +7.5% | 1.5 | ⚠️ 최소 허용 |
| -5% | +10% | 2.0 | ✅ 권장 |
| -5% | +15% | 3.0 | ✅ 이상적 |

#### ⚠️ 상태 파일 관리

`data/risk_state.json` 파일을 주기적으로 백업하세요:

```bash
# 백업
cp data/risk_state.json backups/risk_state_$(date +%Y%m%d).json

# 복원
cp backups/risk_state_20260101.json data/risk_state.json
```

### 상세 가이드

더 자세한 리스크 관리 설정 및 고급 기능은 다음 문서를 참고하세요:

- **[리스크 관리 설정 가이드](./RISK_MANAGEMENT_CONFIG.md)** - 완벽한 설정 가이드
- **[아키텍처 문서](./ARCHITECTURE.md)** - 리스크 관리 시스템 구조
- **리스크 관리자 코드**: `src/risk/manager.py`
- **상태 관리자 코드**: `src/risk/state_manager.py`

---

## 대시보드 사용법

### 메인 대시보드 (http://localhost:3000)

#### 1. 현재 상태 확인

- **봇 상태**: 실행 중 / 중지 / 에러
- **포트폴리오 가치**: 현재 총 자산 (KRW)
- **수익률**: 일일/주간/월간 수익률
- **최근 거래**: 최근 5개 거래 내역

#### 2. 거래 내역 조회

- 모든 매수/매도 거래 기록
- 필터링: 심볼, 타입(buy/sell), 날짜
- 정렬: 날짜, 가격, 금액
- 통계: 총 거래 수, 평균 수익률, 승률

#### 3. AI 판단 내역

- AI 의사결정 히스토리
- 판단 신뢰도 (high/medium/low)
- 판단 사유 (6개 섹션)
- 시장 데이터 (차트, 지표, 오더북)

#### 4. 봇 제어

- **시작**: 자동 거래 시작
- **중지**: 자동 거래 중지
- **설정**: 거래 파라미터 변경 (심볼, 주문 금액, 주기 등)

### API 문서 (http://localhost:8000/api/v1/docs)

FastAPI의 자동 생성된 Swagger UI를 통해 모든 API 엔드포인트를 확인하고 테스트할 수 있습니다.

---

## 알림 설정 (Telegram)

### 1. Telegram Bot 생성

1. Telegram에서 @BotFather 검색
2. `/newbot` 명령어 입력
3. 봇 이름 설정 (예: My Trading Bot)
4. 봇 사용자명 설정 (예: my_trading_bot)
5. Bot Token 복사 (예: `123456:ABC-DEF...`)

### 2. Chat ID 확인

1. Telegram에서 @userinfobot 검색
2. `/start` 명령어 입력
3. Chat ID 복사 (예: `123456789`)

### 3. 환경 변수 설정

`.env` 파일에 다음 내용 추가:

```bash
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=123456789
TELEGRAM_ENABLED=true
```

### 4. Backend 재시작

```bash
docker-compose -f docker-compose.full-stack.yml restart backend
```

### 5. 알림 타입

스케줄러는 **4단계 구조화된 알림**을 전송합니다:

#### 1단계: 사이클 시작 알림
- 거래 사이클 시작 시각
- 거래 심볼 (KRW-ETH)
- 상태 메시지

#### 2단계: 백테스팅 및 시장 분석
- 백테스팅 결과 (승률, MDD, Sharpe Ratio)
- 기술적 지표 (RSI, MA, 거래량)
- 시장 이상 감지 (플래시 크래시, RSI 다이버전스)
- BTC-ETH 상관관계

#### 3단계: AI 의사결정 상세
- AI 판단 (buy/sell/hold)
- 신뢰도 (high/medium/low)
- 판단 근거 (전체 텍스트)
- 소요 시간

#### 4단계: 포트폴리오 현황
- 현재 잔고 (KRW, 코인)
- 총 자산 가치
- 거래 결과 (매수/매도 시)
  - 거래 ID
  - 체결가, 수량, 총액
  - 수수료

#### 추가 알림:
- **에러 알림**: 시스템 에러 발생 시
- **일일 리포트**: 하루 거래 요약 (매일 오전 9시)
- **봇 상태 알림**: 봇 시작/중지 시
- **리스크 알림**: 손절/익절, Circuit Breaker 발동 시

---

## 모니터링 (Grafana)

### 1. Grafana 접속

http://localhost:3001 (기본 계정: admin/admin)

### 2. 대시보드 구성

#### Trading Bot Dashboard

- **포트폴리오 가치**: 실시간 자산 추이
- **거래 통계**: 매수/매도 횟수, 거래량
- **AI 판단**: 매수/매도/보유 비율
- **수익률**: 일일/주간/월간 수익률
- **에러율**: 시스템 에러 추이
- **API 성능**: 응답 시간, 요청 수

### 3. 알림 설정

Grafana에서 임계값을 설정하여 알림을 받을 수 있습니다:

1. Dashboard → Panel → Alert 탭
2. 조건 설정 (예: 포트폴리오 가치 < 1,000,000)
3. 알림 채널 설정 (Email, Slack, Telegram 등)

---

## 설정 변경

### 트레이딩 주기 변경

```bash
# .env 파일 수정
SCHEDULER_INTERVAL_MINUTES=10  # 5분 → 10분으로 변경

# Backend 재시작
docker-compose -f docker-compose.full-stack.yml restart backend
```

### 거래 심볼 변경

```bash
# .env 파일 수정
TRADING_SYMBOL=KRW-BTC  # ETH → BTC로 변경

# Backend 재시작
docker-compose -f docker-compose.full-stack.yml restart backend
```

### 최소 주문 금액 변경

```bash
# .env 파일 수정
TRADING_MIN_ORDER_AMOUNT=10000.0  # 5,000원 → 10,000원

# Backend 재시작
docker-compose -f docker-compose.full-stack.yml restart backend
```

### AI 모델 변경

```bash
# .env 파일 수정
OPENAI_MODEL=gpt-4  # gpt-4o-mini → gpt-4 (더 정확하지만 비용 증가)

# Backend 재시작
docker-compose -f docker-compose.full-stack.yml restart backend
```

---

## 트러블슈팅

### Backend가 시작되지 않음

```bash
# 로그 확인
docker logs trading_bot_backend

# 환경 변수 확인
docker exec trading_bot_backend env | grep -E "UPBIT|OPENAI"

# 재시작
docker-compose -f docker-compose.full-stack.yml restart backend
```

### PostgreSQL 연결 오류

```bash
# PostgreSQL 상태 확인
docker ps | grep postgres

# 헬스 체크
docker exec trading_bot_postgres pg_isready -U postgres

# 재시작
docker-compose -f docker-compose.full-stack.yml restart postgres
```

### Frontend가 Backend를 찾지 못함

```bash
# 네트워크 확인
docker network ls
docker network inspect bitcoin_trading_network

# Frontend 환경 변수 확인
docker exec trading_bot_frontend env | grep NEXT_PUBLIC

# Backend API 직접 테스트
curl http://backend:8000/health  # 컨테이너 내부에서
curl http://localhost:8000/health  # 호스트에서
```

### API 키 오류

```bash
# .env 파일 확인
cat .env | grep -E "UPBIT|OPENAI"

# 공백, 따옴표 제거 확인
UPBIT_ACCESS_KEY=your_key  # ✅ 올바름
UPBIT_ACCESS_KEY="your_key"  # ❌ 따옴표 제거
UPBIT_ACCESS_KEY= your_key  # ❌ 공백 제거
```

### 로그 확인

```bash
# 전체 로그
docker-compose -f docker-compose.full-stack.yml logs -f

# Backend 로그만
docker-compose -f docker-compose.full-stack.yml logs -f backend

# 에러만 필터링
docker-compose -f docker-compose.full-stack.yml logs -f backend | grep ERROR

# 최근 100줄
docker-compose -f docker-compose.full-stack.yml logs --tail=100 backend
```

---

## 운영 가이드

### 데이터베이스 접근

```bash
# PostgreSQL 접속
docker exec -it trading_bot_postgres psql -U postgres -d trading_bot

# SQL 쿼리 예시
SELECT * FROM trades ORDER BY created_at DESC LIMIT 10;
SELECT * FROM ai_decisions ORDER BY created_at DESC LIMIT 10;
SELECT * FROM portfolio_snapshots ORDER BY created_at DESC LIMIT 1;
```

### 데이터베이스 백업

```bash
# 백업 생성
docker exec trading_bot_postgres pg_dump -U postgres trading_bot > backup_$(date +%Y%m%d_%H%M%S).sql

# 백업 복원
cat backup_20251228_120000.sql | docker exec -i trading_bot_postgres psql -U postgres trading_bot
```

### 로그 관리

```bash
# 로그 파일 위치 (컨테이너 내부)
docker exec trading_bot_backend ls -la /app/logs

# 로그 파일 다운로드
docker cp trading_bot_backend:/app/logs/trading.log ./local_logs/

# 로그 로테이션 (권장)
# docker-compose.yml에 logging 설정 추가:
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

### 성능 모니터링

```bash
# 컨테이너 리소스 사용량
docker stats

# 특정 컨테이너만
docker stats trading_bot_backend

# PostgreSQL 쿼리 성능
docker exec -it trading_bot_postgres psql -U postgres -d trading_bot
EXPLAIN ANALYZE SELECT * FROM trades WHERE symbol = 'KRW-ETH' ORDER BY created_at DESC LIMIT 10;
```

---

## 프로덕션 배포

### 1. 서버 준비

#### 최소 요구사항

- **CPU**: 2 cores
- **RAM**: 4 GB
- **Storage**: 20 GB
- **OS**: Ubuntu 20.04+ / CentOS 7+ / Amazon Linux 2

#### 권장 사양

- **CPU**: 4 cores
- **RAM**: 8 GB
- **Storage**: 50 GB SSD
- **OS**: Ubuntu 22.04 LTS

### 2. Docker 설치

```bash
# Ubuntu
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Docker Compose 설치
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 3. 프로젝트 배포

```bash
# 레포지토리 클론
git clone https://github.com/yourusername/bitcoin-trading-bot.git
cd bitcoin-trading-bot

# 환경 변수 설정
cp .env.example .env
nano .env  # API 키 및 설정 입력

# 프로덕션 모드로 실행
docker-compose -f docker-compose.full-stack.yml up -d --build
```

### 4. SSL 인증서 설정 (Let's Encrypt)

```bash
# Certbot 설치
sudo apt-get update
sudo apt-get install certbot python3-certbot-nginx

# 인증서 발급
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# 자동 갱신 설정
sudo crontab -e
0 0 1 * * certbot renew --quiet
```

### 5. Nginx 리버스 프록시 설정

`nginx.conf` 파일 수정:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    # HTTP -> HTTPS 리다이렉트
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Frontend
    location / {
        proxy_pass http://frontend:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Backend API
    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 6. 방화벽 설정

```bash
# UFW (Ubuntu)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw enable

# firewalld (CentOS)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### 7. 자동 시작 설정

```bash
# systemd 서비스 생성
sudo nano /etc/systemd/system/trading-bot.service
```

```ini
[Unit]
Description=Trading Bot Docker Compose
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/path/to/bitcoin-trading-bot
ExecStart=/usr/local/bin/docker-compose -f docker-compose.full-stack.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.full-stack.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

```bash
# 서비스 활성화
sudo systemctl enable trading-bot
sudo systemctl start trading-bot

# 상태 확인
sudo systemctl status trading-bot
```

### 8. 모니터링 및 알림 설정

#### Sentry (에러 추적)

```bash
# .env 파일에 추가
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
SENTRY_ENABLED=true

# Backend 재시작
docker-compose -f docker-compose.full-stack.yml restart backend
```

#### Grafana 알림

1. Grafana 접속 (https://yourdomain.com:3001)
2. Configuration → Notification channels
3. Telegram / Email / Slack 설정
4. Dashboard에서 Alert 규칙 설정

### 9. 백업 자동화

```bash
# 백업 스크립트 생성
nano /usr/local/bin/backup-trading-bot.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/backup/trading-bot"
DATE=$(date +%Y%m%d_%H%M%S)

# PostgreSQL 백업
docker exec trading_bot_postgres pg_dump -U postgres trading_bot > $BACKUP_DIR/db_backup_$DATE.sql

# 로그 백업
docker cp trading_bot_backend:/app/logs $BACKUP_DIR/logs_$DATE

# 7일 이상된 백업 삭제
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "logs_*" -mtime +7 -delete
```

```bash
# 실행 권한 부여
sudo chmod +x /usr/local/bin/backup-trading-bot.sh

# Cron 등록 (매일 새벽 2시)
sudo crontab -e
0 2 * * * /usr/local/bin/backup-trading-bot.sh
```

### 10. 보안 강화

```bash
# 환경 변수 파일 권한 제한
chmod 600 .env

# Docker 소켓 권한 제한
sudo chmod 660 /var/run/docker.sock

# fail2ban 설치 (SSH 보호)
sudo apt-get install fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# 정기 업데이트
sudo apt-get update && sudo apt-get upgrade -y
```

---

## 📚 추가 정보

### 관련 문서

- **Docker 가이드**: `docs/DOCKER_GUIDE.md` - Docker 실행 및 관리 완벽 가이드
- **스케줄러 가이드**: `docs/SCHEDULER_GUIDE.md` - 자동화 시스템 완벽 가이드
- **아키텍처**: `docs/ARCHITECTURE.md` - 시스템 구조 및 설계
- **모니터링 계획**: `docs/MONITORING_IMPLEMENTATION_PLAN.md` - 모니터링 시스템 구현
- **Backend 테스트**: `backend/tests/README.md` - Backend 테스트 가이드 (61개)
- **백테스팅 데이터**: `scripts/backtesting/README.md` - 데이터 수집 스크립트
- **Frontend 가이드**: `frontend/README.md` - Next.js 개발 가이드

### 테스트 실행

```bash
# 루트 테스트 (백테스팅, AI, 거래 등)
pytest

# Backend 테스트 (API, 모델, 서비스)
cd backend
pytest

# 커버리지 포함
pytest --cov=src --cov-report=html
pytest --cov=backend/app --cov-report=html
```

### 개발 모드

```bash
# 자동 거래 비활성화 (테스트용)
SCHEDULER_ENABLED=false

# 로그 레벨 변경 (디버깅)
LOG_LEVEL=DEBUG

# AI 모델 변경 (비용 절감)
OPENAI_MODEL=gpt-4o-mini
```

---

## ⚠️ 주의사항

1. **실제 거래 전 백테스팅 필수**

   - 최소 30일 이상의 데이터로 검증
   - 승률, 손익비, Max Drawdown 확인

2. **소액으로 시작**

   - 최소 주문 금액으로 테스트
   - 충분한 검증 후 금액 증액

3. **정기적인 모니터링**

   - Grafana 대시보드 확인 (일 1회 이상)
   - Telegram 알림 확인
   - 에러 로그 추적

4. **데이터 백업**

   - 매일 자동 백업 설정
   - 주기적으로 복원 테스트

5. **API 키 보안**

   - `.env` 파일 권한 제한 (chmod 600)
   - Git에 커밋하지 않기 (.gitignore 확인)
   - 정기적으로 키 교체

6. **시스템 업데이트**
   - 정기적으로 Docker 이미지 재빌드
   - 의존성 업데이트 (pip, npm)
   - 보안 패치 적용

---

**마지막 업데이트**: 2026-01-01
**버전**: 2.1.0
**문서 상태**: ✨ 리스크 관리 시스템 통합 완료

**Happy Trading! 📈💰**
