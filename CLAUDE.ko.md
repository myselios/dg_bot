# CLAUDE.md

이 파일은 Claude Code (claude.ai/code)가 이 저장소의 코드를 작업할 때 참고하는 가이드입니다.

## 프로젝트 개요

OpenAI GPT-4를 활용한 비트코인 AI 자동매매 봇입니다. APScheduler를 사용하여 1시간 간격으로 실행되며, 기술적 지표와 시장 데이터의 AI 분석을 기반으로 Upbit 거래소에서 거래를 실행합니다.

**기술 스택**: Python 3.11, FastAPI, PostgreSQL, Docker, APScheduler, OpenAI GPT-4, TA-Lib

## 주요 명령어

### 환경 설정
```bash
# 가상환경(venv) 활성화
# Windows PowerShell
.\venv\Scripts\Activate.ps1

# Windows CMD
venv\Scripts\activate.bat

# Linux/Mac
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
# requirements-api.txt가 requirements.txt에 통합됨
```

### 테스트
```bash
# 전체 테스트 실행 (반드시 venv 환경에서)
python -m pytest tests/ -v

# 특정 테스트 파일 실행
python -m pytest tests/test_module_name.py -v

# 커버리지 포함 테스트
python -m pytest tests/ --cov=src --cov=backend --cov-report=html

# 단위 테스트만 실행
python -m pytest tests/ -m unit -v

# 통합 테스트만 실행
python -m pytest tests/ -m integration -v

# 스케줄러 테스트
python -m pytest tests/backend/app/core/test_scheduler.py -v

# 단일 테스트 실행
python -m pytest tests/test_module.py::TestClass::test_method -v
```

### 봇 실행

```bash
# 거래 사이클 1회 실행 (개발용)
python main.py

# 스케줄러 실행 (1시간 간격 자동 거래)
python scheduler_main.py

# Docker로 실행 (스케줄러만)
docker-compose up -d scheduler
docker-compose logs -f scheduler

# 전체 스택 실행 (DB, API, 모니터링)
docker-compose up -d
```

### Docker 작업
```bash
# 스케줄러 빌드 및 실행
docker-compose build scheduler
docker-compose up -d scheduler

# 로그 확인
docker-compose logs -f scheduler

# 서비스 중지
docker-compose down

# 완전 재빌드
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### 데이터베이스 작업
```bash
# 데이터베이스는 Docker Compose로 관리됨
# PostgreSQL은 영구 볼륨이 있는 컨테이너에서 실행됨
# 테이블은 첫 실행 시 SQLAlchemy를 통해 자동 생성됨

# PostgreSQL 컨테이너 접속
docker exec -it dg_bot-postgres-1 psql -U postgres -d trading_bot
```

## 아키텍처

### 시스템 흐름

봇은 **이중 모드 아키텍처**로 동작합니다:

1. **단독 모드** (`main.py`): 거래 사이클 1회 실행
2. **스케줄러 모드** (`scheduler_main.py`): 1시간 간격 자동 실행

**주요 흐름**:
```
scheduler_main.py
  → backend/app/core/scheduler.py (APScheduler 설정)
    → trading_job()이 main.execute_trading_cycle() 호출
      → QuickBacktestFilter (룰 기반 필터링, AI 미사용)
      → SignalAnalyzer (기술적 분석)
      → AIService (GPT-4 의사결정)
      → TradingService (주문 실행)
      → 데이터베이스 기록 (backend 모델 사용)
      → Telegram 알림
```

### 디렉토리 구조

```
dg_bot/
├── main.py                    # 메인 거래 사이클 (단독 실행)
├── scheduler_main.py          # 스케줄러 진입점 (자동화 모드)
├── src/                       # 핵심 거래 로직
│   ├── ai/                    # AI 의사결정 (GPT-4)
│   │   ├── service.py         # AIService - 메인 AI 분석
│   │   └── market_correlation.py
│   ├── api/                   # 거래소 API 클라이언트
│   │   └── upbit_client.py    # Upbit 거래소 연동
│   ├── backtesting/           # 백테스팅 엔진
│   │   ├── backtester.py      # 메인 백테스팅 엔진
│   │   ├── quick_filter.py    # 빠른 룰 기반 필터링
│   │   ├── rule_based_strategy.py  # 룰 기반 전략
│   │   └── ai_strategy.py     # AI 기반 전략
│   ├── data/                  # 데이터 수집
│   │   └── collector.py       # 시장 데이터 수집기
│   ├── trading/               # 거래 실행
│   │   ├── service.py         # TradingService - 주문 실행
│   │   ├── indicators.py      # 기술적 지표 (RSI, MACD 등)
│   │   └── signal_analyzer.py # 신호 분석
│   ├── position/              # 포지션 관리
│   └── config/                # 설정
│       └── settings.py        # 모든 설정 클래스
├── backend/                   # FastAPI 백엔드 + 데이터베이스
│   ├── app/
│   │   ├── main.py           # FastAPI 애플리케이션 진입점
│   │   ├── api/v1/           # REST API 엔드포인트
│   │   │   └── endpoints/
│   │   │       ├── bot_control.py  # 봇 제어 API
│   │   │       └── trades.py       # 거래 내역 API
│   │   ├── core/
│   │   │   ├── config.py     # 백엔드 설정
│   │   │   └── scheduler.py  # APScheduler 설정
│   │   ├── db/               # 데이터베이스 설정
│   │   │   ├── base.py       # SQLAlchemy base
│   │   │   ├── session.py    # DB 세션 관리
│   │   │   └── init_db.py    # DB 초기화
│   │   ├── models/           # SQLAlchemy ORM 모델
│   │   │   ├── trade.py      # 거래 기록
│   │   │   ├── ai_decision.py # AI 결정 로그
│   │   │   ├── order.py      # 주문 기록
│   │   │   ├── portfolio.py  # 포트폴리오 스냅샷
│   │   │   ├── bot_config.py # 봇 설정
│   │   │   └── system_log.py # 시스템 로그
│   │   ├── schemas/          # Pydantic 스키마
│   │   └── services/
│   │       ├── trading_engine.py  # 거래 로직 통합
│   │       ├── notification.py    # Telegram 알림
│   │       └── metrics.py         # Prometheus 메트릭
│   └── tests/                # 백엔드 테스트
├── tests/                    # 메인 테스트 디렉토리
├── scripts/backtesting/      # 데이터 수집 스크립트
├── monitoring/               # Prometheus + Grafana 설정
└── docs/                     # 문서 (모든 .md 파일은 여기에)
```

### 주요 컴포넌트

**AIService** (`src/ai/service.py`):
- OpenAI GPT-4를 사용한 거래 의사결정
- 기술적 지표, 시장 동향, 차트 패턴 분석
- 신뢰도 점수와 근거를 포함한 결정 반환
- 주요 메서드: `analyze()`, `prepare_analysis_data()`

**TradingService** (`src/trading/service.py`):
- Upbit API를 통한 매수/매도 주문 실행
- 수수료 계산, 슬리피지, 분할 주문 처리
- 주요 메서드: `buy()`, `sell()`, `calculate_fee()`, `calculate_slippage()`

**QuickBacktestFilter** (`src/backtesting/quick_filter.py`):
- AI 호출 없이 빠른 룰 기반 필터링
- 룰 기반 전략을 사용하여 거래 기회 사전 필터링
- AI API 비용을 크게 절감

**Scheduler** (`backend/app/core/scheduler.py`):
- 1시간 간격 작업을 위한 APScheduler 설정
- `trading_job()`: 메인 스케줄 작업
- 오류 복구, 중복 실행 방지 처리 (max_instances=1)

**데이터베이스 모델** (`backend/app/models/`):
- `Trade`: 실행된 거래
- `AIDecision`: AI 분석 로그
- `Order`: 주문 상세 정보
- `Portfolio`: 포트폴리오 스냅샷
- 모두 비동기 세션과 함께 SQLAlchemy ORM 사용

### 데이터 흐름

1. **데이터 수집**: `DataCollector`가 Upbit에서 OHLCV 데이터 가져오기
2. **기술적 분석**: `TechnicalIndicators`가 RSI, MACD, 볼린저 밴드 계산
3. **빠른 필터링**: `QuickBacktestFilter`가 룰 기반 전략 적용 (AI 비용 없음)
4. **신호 분석**: `SignalAnalyzer`가 매수/매도 신호 분석
5. **AI 의사결정**: `AIService`가 GPT-4를 통해 최종 결정
6. **주문 실행**: `TradingService`가 Upbit에서 거래 실행
7. **데이터베이스 기록**: 모델이 거래, 결정, 포트폴리오 데이터 저장
8. **알림**: `notification.py`를 통한 Telegram 알림 발송
9. **메트릭**: `metrics.py`를 통한 Prometheus 메트릭 기록

## 개발 가이드라인

### TDD (테스트 주도 개발)

이 프로젝트는 TDD 원칙을 엄격히 따릅니다 (`.cursorrules` 참조):

1. **Red**: 실패하는 테스트를 먼저 작성
2. **Green**: 테스트를 통과하는 최소한의 코드 작성
3. **Refactor**: 테스트를 통과한 상태에서 코드 최적화

**테스트 구조**:
- 모든 테스트는 `tests/` 디렉토리에 위치
- 단위 테스트에는 `@pytest.mark.unit` 사용
- 통합 테스트에는 `@pytest.mark.integration` 사용
- Fixture는 `conftest.py`에 정의
- Given-When-Then 패턴 따르기

### 가상환경 (venv)

**중요**: 항상 venv를 사용하여 Python 명령 실행
- 위치: `venv/` (프로젝트 루트)
- Python 명령 실행 전에 활성화 필수
- venv 외부에서는 절대 Python 명령 실행 금지

### 파일 구조 규칙

`.cursorrules`에서:

1. **문서**: 모든 `.md` 파일은 반드시 `docs/`에 위치 (루트의 `README.md` 제외)
2. **리포트**: 분석/성능 리포트는 `docs/reports/`에 위치
3. **스크립트**: 개발 스크립트는 프로젝트 루트, 데이터 스크립트는 `scripts/`에 위치
4. **임시 파일**: 사용 후 임시 테스트 스크립트 삭제

### Windows 인코딩 (PowerShell)

Windows에서 실행 시, PowerShell 스크립트는 UTF-8 인코딩 설정 필요:

```powershell
# .ps1 파일 시작 부분에 추가
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
```

가능한 경우 Windows 스크립트는 `.ps1`보다 `.bat` 파일 선호.

## 설정

### 환경 변수

모든 설정은 `.env` 파일에 있음 (`env.example`에서 복사):

**필수**:
- `UPBIT_ACCESS_KEY`: Upbit API 액세스 키
- `UPBIT_SECRET_KEY`: Upbit API 시크릿 키
- `OPENAI_API_KEY`: OpenAI API 키

**선택 사항이지만 권장**:
- `TELEGRAM_BOT_TOKEN`: Telegram 봇 토큰
- `TELEGRAM_CHAT_ID`: Telegram 채팅 ID
- `SENTRY_DSN`: Sentry 에러 추적 DSN
- `POSTGRES_*`: 데이터베이스 설정 (Docker용)
- `PROMETHEUS_ENABLED`: Prometheus 메트릭 활성화
- `GRAFANA_*`: Grafana 설정

### 설정 클래스

모두 `src/config/settings.py`에 위치:
- `TradingConfig`: 거래 파라미터 (수수료율, 최소 거래금액 등)
- `AIConfig`: AI 모델 설정 (GPT-4, temperature 등)
- `DataConfig`: 데이터 수집 설정 (간격, 개수 등)
- `BacktestConfig`: 백테스팅 파라미터
- 백엔드 설정은 `backend/app/core/config.py`에 위치

## 중요 사항

### 거래 안전성

1. **소액으로 시작**: 최소 금액으로 먼저 테스트
2. **면밀히 모니터링**: 로그와 Telegram 알림 확인
3. **API 키 보안**: 절대 `.env` 파일 커밋 금지
4. **드라이런**: 실거래 전 백테스팅 실행 (`python backtest.py`)

### 스케줄러 동작

- 1시간마다 실행 (`scheduler.py`에서 설정 가능)
- `max_instances=1`로 동시 실행 방지
- SIGINT/SIGTERM 시 우아한 종료
- 오류 시 자동 복구 (Sentry 활성화 시 로그 기록)

### 데이터베이스

- 프로덕션에는 PostgreSQL 필요 (Docker 사용)
- 첫 실행 시 SQLAlchemy를 통해 테이블 자동 생성
- 백엔드 전체에서 비동기 세션 사용
- 마이그레이션 미구현 (declarative_base 자동 생성 사용)

### AI 비용

- 각 AI 의사결정 호출마다 비용 발생 (GPT-4 API)
- `QuickBacktestFilter`가 룰 기반 사전 필터링으로 AI 호출 감소
- OpenAI 대시보드에서 사용량 모니터링

### 백테스팅

두 가지 모드:
1. **룰 기반만**: AI 호출 없음, 빠르고 무료
2. **AI 기반**: GPT-4 분석 포함, 느리고 비용 발생

과거 데이터 수집은 `scripts/backtesting/` 사용.

## 일반적인 문제

### Import 에러
- venv가 활성화되었는지 확인
- `PYTHONPATH`에 프로젝트 루트 포함 확인
- `scheduler_main.py`가 프로젝트 루트를 `sys.path`에 추가함

### 데이터베이스 연결
- PostgreSQL이 실행 중인지 확인 (`docker-compose ps`)
- `.env`의 `DATABASE_URL` 확인
- 비동기 드라이버 사용 확인: `postgresql+asyncpg://...`

### API 에러
- `.env`의 API 키 확인
- Upbit/OpenAI 속도 제한 확인
- `logs/` 디렉토리의 로그 검토

### 스케줄러 미실행
- `logs/scheduler/`의 `scheduler.log` 확인
- 다른 인스턴스가 실행 중이지 않은지 확인
- 시스템 시간 확인 (스케줄러는 Asia/Seoul 시간대 사용)

## 유용한 참고 자료

- [사용자 가이드](docs/USER_GUIDE.md): 전체 사용자 문서
- [스케줄러 가이드](docs/SCHEDULER_GUIDE.md): 스케줄러 상세 가이드
- [Docker 가이드](docs/DOCKER_GUIDE.md): Docker 설정 및 배포
- [아키텍처](docs/ARCHITECTURE.md): 시스템 아키텍처 상세 정보
- [거래 흐름](docs/TRADING_SEQUENCE_FLOW.md): 완전한 거래 시퀀스
