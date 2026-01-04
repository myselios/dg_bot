# CLAUDE.md

**작성일**: 2026-01-04
이 파일은 Claude Code(claude.ai/code)가 이 저장소에서 작업할 때 따라야 할 실용적인 가이드를 제공합니다.

> 목표: 실거래 시스템을 "안전하게" 변경하기 위해
>
> - Clean Architecture 경계 준수
> - Quant-grade 재현성(데이터/파라미터/로그) 확보
> - TDD + 안전 계약(락/중복주문/리스크) 강제

---

## 0) 언어 규칙 (Language Rules)

**⚠️ 중요: 모든 커뮤니케이션과 문서는 한국어로 작성**

1. **Claude의 모든 답변은 한국어로 작성**
   - 사용자와의 대화는 100% 한국어
   - 기술 용어는 영어 병기 가능 (예: "컨테이너(Container)")

2. **문서는 한국어로 작성**
   - 계획 문서 (`docs/plans/`)
   - 가이드 문서 (`docs/guide/`)
   - 아키텍처 결정 기록 (ADR)
   - 변경 로그, 릴리스 노트

3. **코드 주석과 docstring은 한국어 우선**
   - 함수/클래스 docstring: 한국어
   - 복잡한 로직 주석: 한국어
   - 변수명, 함수명: 영어 (PEP 8 준수)

4. **예외 사항**
   - Git 커밋 메시지: 영어 (국제 협업 표준)
   - 코드 식별자(변수명, 함수명, 클래스명): 영어
   - 외부 라이브러리 문서 인용: 원문 유지

---

## 1) Non-Negotiables (실거래 안전 규칙)

1. **주문(매수/매도) 경로는 반드시 BOTH 적용**
   - **Lock** (상호배제) AND
   - **Idempotency** (중복 주문 방지)
2. **금액/비율 계산은 Value Object 또는 Decimal-safe 로직**
   - Money / Percentage / Decimal 기반
3. **PnL/리스크에 영향 있는 변경은 테스트 없이는 금지**
   - contracts/ (불변식)
   - scenarios/ (트레이딩 흐름)
   - scheduler/ (운영 안정성)
4. **Config는 단일 소스**
   - 모든 숫자 설정은 `src/config/settings.py`에만 존재
   - 변경 시 docs/tests까지 grep로 동기화
5. **시크릿 커밋 금지**
   - `.env`, API 키, 토큰 등 절대 커밋 금지

---

## 1) Project Overview

Upbit 기반 멀티코인 자동매매 시스템:

- 스케줄러 기반 주기 실행 (1시간 진입 탐색 + 15분 포지션 관리)
- AI 보조 분석 (AIPort adapter)
- 백테스트/룰 기반 필터로 오탐 및 AI 비용 절감
- FastAPI 백엔드 + PostgreSQL 저장
- Prometheus/Grafana 모니터링 + Telegram 알림

**Tech Stack**: Python 3.11, FastAPI, PostgreSQL, Docker, APScheduler, OpenAI API, TA-Lib

> 모델 표기 규칙:
>
> - 문서/코드는 “GPT-4” 같은 하드코딩 표현을 피하고
> - `AIConfig.MODEL` (config) 기준으로만 서술한다.

---

## 2) Repo Contexts (Bounded Contexts)

이 레포는 큰 맥락이 2개다.

### A) Trading Bot Runtime (Core execution)

- Entry points: `main.py`, `scheduler_main.py`
- Core 로직: `src/`

### B) Backend (API + DB + Scheduler config)

- FastAPI + DB/persistence: `backend/app/`

**Rule**: 트레이딩 비즈니스 규칙은 `src/domain` + `src/application`에 둔다.  
Backend는 관측/오케스트레이션 중심(얇게)으로 유지한다.

---

## 3) Common Commands

### 3.1 Environment Setup

```bash
# Activate virtual environment (venv)
# Windows PowerShell
.\venv\Scripts\Activate.ps1

# Windows CMD
venv\Scripts\activate.bat

# Linux/Mac
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3.2 Running (Development)

```bash
# Run trading cycle once
python main.py

# Run scheduler (automated jobs)
python scheduler_main.py
```

### 3.3 Docker

```bash
# Scheduler only
docker-compose up -d scheduler
docker-compose logs -f scheduler

# Full stack
docker-compose up -d
docker-compose logs -f
```

### 3.4 Docker Operations

```bash
docker-compose down
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### 3.5 Database Operations

```bash
# Access PostgreSQL container
docker exec -it dg_bot-postgres-1 psql -U postgres -d trading_bot
```

---


## 4) Architecture (Clean Architecture / Ports & Adapters)

### 4.1 Layering

```
Presentation → Application → Domain
      ↓              ↓
Infrastructure ─────┘
```

- **Domain** (`src/domain/`): entities/value_objects/pure logic
- **Application** (`src/application/`): use cases + port interfaces
- **Infrastructure** (`src/infrastructure/`): adapters (Upbit/OpenAI/Postgres/etc.)
- **Presentation** (`src/presentation/` + entry points): CLI/scheduler wiring

### 4.2 Dependency Rules (강제)

- `domain` must not import any other layer.
- `application` may import `domain`, not `infrastructure`.
- `infrastructure` may import `application` (ports) and `domain`.
- `presentation` can wire dependencies but must remain thin.

### 4.3 DI Container

`src/container.py` factories:

- `Container()` production
- `Container.create_for_testing()` testing wiring
- `Container.create_from_legacy(...)` migration bridge

**Hard rule**: 신규 코드는 레거시 서비스가 아니라 **UseCase + Port**에 의존한다.

---

## 5) Scheduler & Jobs (Operational Safety)

### 5.1 Jobs (Dual timeframe)

1. `trading_job` (1시간): 멀티코인 스캔 + 분석 + 진입 결정
2. `position_management_job` (15분): 보유 포지션 관리 (규칙 기반, AI 호출 없음)
3. `portfolio_snapshot_job` (1시간): 포트폴리오 스냅샷 저장
4. `daily_report_job` (09:00): Telegram 리포트

**Scheduler SSOT**: `backend/app/core/scheduler.py`  
문서의 크론/시각은 반드시 이 파일과 일치해야 한다.

### 5.2 Locking (LockPort)

`src/application/ports/outbound/lock_port.py`

- 동시 실행 방지 (job overlap 차단)
- PostgreSQL Advisory Lock 권장
- 예시 lock IDs:
  - trading_cycle = 1001
  - position_management = 1002

**Failure behavior**:

- lock 획득 실패 시 → 안전하게 종료(부분 실행 금지)

### 5.3 Idempotency (IdempotencyPort)

`src/application/ports/outbound/idempotency_port.py`

- 재시도/재기동 상황에서도 중복 주문 방지
- 키 구성 권장:
  - ticker, timeframe, candle timestamp, action, strategy_version(있으면)

**Rule**: 주문 전 `check` + 성공 시 `mark`는 필수.

---

## 6) Backtesting & Filters (Quant requirements)

백테스트는 반드시:

- 재현 가능(reproducible)
- 감사 가능(auditable)
- 라이브 실행 경로와 최대한 분리

### 6.1 Quick Filter (No AI)

`src/backtesting/quick_filter.py`

- 룰 기반 사전 필터로 AI 호출 비용/오탐 감소

### 6.2 Modes

- Rule-based only: 빠르고 결정적
- AI-based: 비용/지연 큼 → 프롬프트/결과 아티팩트 저장 필수

**Rule**: AI 기반 분석/백테스트는 최소 다음을 기록한다:

- prompt template/version
- model name (config)
- temperature
- structured output schema version

---

## 7) Testing & TDD (Mandatory)

### 7.1 TDD cycle

Red → Green → Refactor (테스트 먼저)

### 7.2 Test taxonomy (risk/behavior driven)

```
tests/
├── contracts/      # 시스템 불변식 (실패 => 거래 중단)
├── scenarios/      # 트레이딩 시나리오 (실패 => 릴리즈 금지)
├── scheduler/      # 운영 안정성 (실패 => 스케줄러 중단)
├── backtesting/    # 백테스트 신뢰성 (실패 => 실거래 금지)
├── unit/           # 계층별 단위 테스트
├── integration/    # DB/외부 연동
└── e2e/            # paper trading / 전체 흐름
```

### 7.3 🔴 테스트 파일 위치 강제 규칙

> **⚠️ tests/ 루트에 test_*.py 파일 직접 생성 금지**

**허용:**
```
tests/
├── __init__.py      ✅ 패키지 초기화
├── conftest.py      ✅ 공유 fixture
├── contracts/       ✅ 테스트 파일 위치
├── scenarios/       ✅ 테스트 파일 위치
├── scheduler/       ✅ 테스트 파일 위치
├── backtesting/     ✅ 테스트 파일 위치
├── unit/            ✅ 테스트 파일 위치
├── integration/     ✅ 테스트 파일 위치
├── e2e/             ✅ 테스트 파일 위치
├── backend/         ✅ 테스트 파일 위치
└── test_*.py        ❌ 금지!
```

**테스트 위치 결정 체크리스트:**
1. 돈이 새는 위험(수수료/손절/중복주문)? → `contracts/`
2. 트레이딩 흐름 시나리오? → `scenarios/`
3. 스케줄러/운영 안정성? → `scheduler/`
4. 백테스팅 로직? → `backtesting/`
5. 순수 단위 테스트? → `unit/{layer}/`
6. DB/외부 API 통합? → `integration/`
7. 전체 E2E 흐름? → `e2e/`

**unit/ 세부 구조:**
```
tests/unit/
├── domain/           # entities, value_objects, services
├── application/      # ports, use_cases, services
├── infrastructure/   # adapters, persistence
├── presentation/     # CLI, telegram
├── pipeline/         # 파이프라인 스테이지
├── config/           # 설정 관련
└── container/        # DI 컨테이너
```

**위반 시**: 코드 리뷰 거절, 올바른 폴더로 이동 후 재제출

### 7.4 Markers

```python
@pytest.mark.contract
@pytest.mark.scenario
@pytest.mark.scheduler
@pytest.mark.unit
@pytest.mark.integration
@pytest.mark.e2e
@pytest.mark.slow
```

### 7.5 Execution priority

```bash
python -m pytest tests/contracts/ -v --tb=short
python -m pytest tests/scenarios/ -v
python -m pytest tests/scheduler/ -v
python -m pytest tests/ -v
```

### 7.6 Test Debt Recovery Protocol

If any of these occur:

- coverage drops
- TDD skipped
- large refactor without confidence

Follow:

- `.claude/skills/test-debt-recovery/TEST_DEBT_RECOVERY.md`

Record outcome in:

- `docs/CHANGELOG_TEST_DEBT.md`

---

## 8) Documentation Rules (Single Source of Truth)

### 8.1 Document hierarchy

```
docs/guide/ARCHITECTURE.md  (SSOT)
├── BACKTESTING_GUIDE.md
├── SCHEDULER_GUIDE.md
├── USER_GUIDE.md
└── 기타 상세 가이드
```

### 8.2 Documentation DoD (Done Definition)

다음 변경은 문서 업데이트가 “필수”다:

- 전략 로직/진입·청산 규칙
- 스케줄러 타이밍/크론
- 리스크 파라미터
- AI 프롬프트/스키마
- 숫자 설정값(config)

업데이트 범위:

- `ARCHITECTURE.md` (개요)
- 관련 상세 가이드 (디테일)
- 필요 시 `docs/diagrams/` 다이어그램

### 8.3 Config change sync (grep required)

커밋 전 반드시 grep로 참조 동기화:

```bash
grep -r "liquidity_top_n\|backtest_top_n\|stop_loss" --include="*.py" --include="*.md" --include="*.mmd" .
```

---

## 9) Configuration

### 9.1 Environment Variables (.env)

Required:

- `UPBIT_ACCESS_KEY`
- `UPBIT_SECRET_KEY`
- `OPENAI_API_KEY`

Recommended:

- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- `SENTRY_DSN`
- `POSTGRES_*`
- `PROMETHEUS_ENABLED`, `GRAFANA_*`

### 9.2 Single source config

- Trading/backtest/AI params: `src/config/settings.py`
- Backend config: `backend/app/core/config.py`

**Rule**: 비즈니스 로직에 매직 넘버 금지.

---

## 10) Common Commands (Testing)

```bash
python -m pytest tests/ -v
python -m pytest tests/test_module_name.py -v
python -m pytest tests/ --cov=src --cov=backend --cov-report=html
python -m pytest tests/ -m unit -v
python -m pytest tests/ -m integration -v
python -m pytest tests/backend/app/core/test_scheduler.py -v
python -m pytest tests/test_module.py::TestClass::test_method -v
```

---

## 10.1) 🔴 테스트 환경 의존성 관리 (절대 규칙)

### 원칙: 의존성 문제로 테스트 스킵 금지

**⚠️ 테스트 실행 전 환경 검증은 필수입니다.**

의존성 문제로 인해 테스트를 스킵하는 것은 **절대 금지**입니다.
테스트 실패는 코드 문제를 발견하는 유일한 방법이며, 환경 문제로 테스트를 건너뛰면 실거래에서 치명적 버그가 발생할 수 있습니다.

### 테스트 실행 전 체크리스트

작업 시작 시 반드시 다음을 확인:

```bash
# 1. Python 버전 및 SSL 모듈 확인
python3 --version
python3 -c "import ssl; print('SSL:', ssl.OPENSSL_VERSION)"

# 2. 핵심 의존성 import 테스트
python3 -c "import pyupbit, pytest, pandas, numpy; print('✅ 핵심 의존성 OK')"

# 3. 테스트 프레임워크 동작 확인
python -m pytest --version
```

### 의존성 문제 발생 시 즉시 해결

**절대 스킵하지 말고, 즉시 수정:**

#### 1. SSL/OpenSSL 문제
```bash
# 증상: ImportError: No module named '_ssl'
# 해결: OpenSSL 설치 + Python 재설치

brew install openssl@1.1
LDFLAGS="-L/opt/homebrew/opt/openssl@1.1/lib" \
CPPFLAGS="-I/opt/homebrew/opt/openssl@1.1/include" \
pyenv install --force $(python3 --version | awk '{print $2}')

# 검증
python3 -c "import ssl; print('✅ SSL OK:', ssl.OPENSSL_VERSION)"
```

#### 2. 패키지 누락
```bash
# 증상: ModuleNotFoundError: No module named 'pyupbit'
# 해결: requirements.txt 재설치

pip3 install -r requirements.txt

# 검증
python3 -c "import pyupbit; print('✅ pyupbit OK')"
```

#### 3. pytest 실행 불가
```bash
# 증상: pytest: command not found
# 해결: pytest 재설치

pip3 install pytest pytest-cov pytest-mock pytest-asyncio

# 검증
python -m pytest --version
```

### 의존성 문제 예방

**작업 시작 시 항상 실행:**

```bash
# 환경 검증 스크립트 (프로젝트 루트에 저장)
./scripts/verify_env.sh
```

**환경 변경 후 재검증:**
- Python 버전 변경 시
- 새로운 패키지 추가 시
- 시스템 라이브러리 업데이트 시

### Definition of Done에 추가

모든 작업 완료 조건에 다음 추가:

- [ ] 테스트 환경 검증 완료 (`python -m pytest tests/ -v`)
- [ ] 의존성 문제 없음 (import 테스트 통과)
- [ ] 환경 문제로 스킵한 테스트 없음

---

## 11) Common Issues (Debug checklist)

### Import errors

- venv 활성화 확인
- project root가 PYTHONPATH에 포함되는지 확인
- 계층 경계 위반/순환 import 점검

### Database connection

- `docker-compose ps`로 postgres 확인
- `DATABASE_URL` 및 async driver 확인: `postgresql+asyncpg://...`

### Scheduler not running

- `logs/` 확인
- Asia/Seoul timezone 확인
- lock을 다른 인스턴스가 잡고 있는지 확인

### AI failures / cost spikes

- Quick Filter 동작 여부 확인
- rate limit / retry 확인
- prompt/response 메타데이터 로깅 확인

---

## 12) Definition of Done (PR/Commit gate)

변경 완료 조건:

- [ ] 테스트 추가/수정 (TDD evidence)
- [ ] 영향 범위에 따라 contracts/scenarios/scheduler 통과
- [ ] 주문 경로에서 lock + idempotency 보존
- [ ] config 변경 시 grep로 docs/tests 동기화
- [ ] 문서 업데이트 (ARCHITECTURE + 관련 가이드)
- [ ] 리스크 파라미터 변경 시 명시적 리뷰 기록

---

## 13) References

- docs/guide/USER_GUIDE.md
- docs/guide/SCHEDULER_GUIDE.md
- docs/guide/DOCKER_GUIDE.md
- docs/guide/ARCHITECTURE.md
- docs/guide/BACKTESTING_GUIDE.md
- docs/guide/RISK_MANAGEMENT_CONFIG.md
- docs/guide/MONITORING_GUIDE.md
- docs/guide/TELEGRAM_SETUP_GUIDE.md
