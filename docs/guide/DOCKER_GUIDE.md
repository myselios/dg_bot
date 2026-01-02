# 🐳 Docker 실행 가이드

## 📋 목차

- [사전 준비사항](#-사전-준비사항)
- [빠른 시작](#-빠른-시작)
- [실행 방법](#-실행-방법)
- [컨테이너 관리](#-컨테이너-관리)
- [모니터링](#-모니터링)
- [고급 설정](#-고급-설정)
- [트러블슈팅](#-트러블슈팅)
- [보안](#-보안-고려사항)
- [백업 및 복구](#-백업-및-복구)
- [프로덕션 배포](#-프로덕션-배포)

---

## 📋 사전 준비사항

### 1. Docker 설치 확인

```powershell
docker --version
docker-compose --version
```

### 2. .env 파일 생성

프로젝트 루트 디렉토리에 `.env` 파일을 생성하세요:

```bash
# Windows
Copy-Item env.example .env

# Linux/Mac
cp env.example .env
```

**.env 파일 필수 항목:**

```env
# Upbit API Keys (필수)
UPBIT_ACCESS_KEY=your_upbit_access_key_here
UPBIT_SECRET_KEY=your_upbit_secret_key_here

# OpenAI API Key (필수)
OPENAI_API_KEY=sk-your_openai_api_key_here

# Trading Configuration (선택적)
TICKER=KRW-ETH
BUY_PERCENTAGE=0.95
SELL_PERCENTAGE=0.95

# AI Configuration (선택적)
AI_MODEL=gpt-4-turbo-preview

# Logging Level (선택적)
LOG_LEVEL=INFO

# Scheduler Configuration (선택적)
SCHEDULER_INTERVAL_MINUTES=60  # 1시간

# Telegram 알림 (선택적)
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=123456789
```

---

## 🚀 빠른 시작

### 최소 실행 (트레이딩 봇만)

```powershell
# 1. 프로젝트 디렉토리로 이동
cd "C:\Users\user\OneDrive\문서\git\bitcoin"

# 2. 도커 이미지 빌드
docker-compose build

# 3. 컨테이너 실행
docker-compose up -d

# 4. 로그 확인
docker-compose logs -f trading-bot
```

### 전체 스택 실행 (권장)

```powershell
# 전체 스택 실행 (PostgreSQL, Backend, Scheduler, Grafana 등)
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

**포함 서비스:**

- 📊 **PostgreSQL** - 데이터베이스
- 🚀 **Backend API** - FastAPI 서버
- ⏰ **Scheduler** - 자동 거래 스케줄러
- 📈 **Prometheus** - 메트릭 수집
- 📊 **Grafana** - 대시보드
- 🖥️ **Frontend** - Next.js UI
- 🔄 **Nginx** - Reverse Proxy

**접속 정보:**

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Grafana: http://localhost:3001 (admin/admin)
- Prometheus: http://localhost:9090

---

## 🎯 실행 방법

### 1. 기본 트레이딩 봇 실행

```powershell
# 도커 이미지 빌드
docker-compose build

# 컨테이너 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f trading-bot
```

**사용 시나리오:**

- 가장 간단한 방법
- 리소스 사용 최소화
- 빠른 테스트

**포함 기능:**
- ✅ 리스크 관리 시스템 (손절/익절, Circuit Breaker)
- ✅ AI 의사결정 검증 (2단계 validation)
- ✅ 유동성 분석 (orderbook 기반)
- ✅ Telegram 4단계 알림

---

### 2. 스케줄러 실행

```powershell
# 스케줄러만 실행
docker-compose up -d scheduler

# 로그 확인
docker-compose logs -f scheduler
```

**사용 시나리오:**

- 이미 Backend API가 실행 중일 때
- 스케줄러만 독립적으로 실행하고 싶을 때
- 1시간 주기 자동 거래

**스케줄러 작업 흐름:**
1. 🛡️ **리스크 체크** (최우선) - 손절/익절, Circuit Breaker, 거래 빈도
2. 📊 **백테스트 필터** - Rule-based 전략으로 사전 필터링
3. 📈 **시장 데이터 수집** - 차트, 오더북, BTC 상관관계
4. 🤖 **AI 분석** - GPT-4 기반 매매 결정
5. 🔍 **AI 검증** - RSI/ATR/ADX 기반 2단계 검증
6. 💱 **거래 실행** - 유동성 분석 후 주문 체결
7. 📱 **알림 전송** - Telegram 4단계 구조화 알림

---

### 3. 백테스팅 실행

```powershell
# 백테스팅 프로파일로 실행
docker-compose --profile backtest up backtest

# 로그 확인
docker-compose logs -f backtest
```

**사용 시나리오:**

- 과거 데이터로 전략 검증
- 성능 분석
- 최적화 테스트

---

### 4. 데이터 수집 실행

```powershell
# 데이터 수집 프로파일로 실행
docker-compose --profile collect up data-collector

# 로그 확인
docker-compose logs -f data-collector
```

**사용 시나리오:**

- 백테스팅용 데이터 수집
- 과거 차트 데이터 저장

---

### 5. 전체 스택 실행 (권장)

```powershell
# 전체 스택 실행
docker-compose up -d

# 스케줄러 로그 확인
docker-compose logs -f scheduler

# 전체 서비스 상태 확인
docker-compose ps
```

**사용 시나리오:**

- 프로덕션 환경
- 모니터링 필요
- 웹 UI 사용
- 완전한 시스템 구축

---

## 📊 컨테이너 관리

### 상태 확인

```powershell
# 실행 중인 컨테이너 확인
docker ps

# 모든 컨테이너 확인 (중지된 것 포함)
docker ps -a

# 특정 컨테이너 상태 확인
docker ps | grep scheduler

# 상세 정보 확인
docker inspect bitcoin-trading-bot
docker inspect bitcoin-scheduler
```

### 로그 확인

```powershell
# 실시간 로그 확인
docker-compose logs -f trading-bot
docker-compose logs -f scheduler

# 최근 100줄 로그 확인
docker-compose logs --tail=100 trading-bot

# 타임스탬프 포함
docker-compose logs -f -t scheduler

# 모든 서비스 로그 확인
docker-compose logs -f
```

### 컨테이너 재시작

```powershell
# 특정 컨테이너 재시작
docker-compose restart trading-bot
docker-compose restart scheduler

# 전체 스택 재시작
docker-compose restart

# 코드 변경 후 재시작
docker-compose restart trading-bot
```

### 컨테이너 중지 및 제거

```powershell
# 컨테이너 중지
docker-compose stop

# 특정 컨테이너만 중지
docker-compose stop scheduler

# 컨테이너 중지 및 제거
docker-compose down

# 전체 스택 중지
docker-compose down

# 볼륨까지 제거 (데이터 삭제 주의!)
docker-compose down -v

# 이미지까지 제거
docker-compose down --rmi all
```

### 컨테이너 내부 접속

```powershell
# 컨테이너 쉘 접속
docker exec -it bitcoin-trading-bot /bin/bash
docker exec -it bitcoin-scheduler /bin/bash

# Python 인터프리터 실행
docker exec -it bitcoin-trading-bot python

# 수동 스크립트 실행
docker exec -it bitcoin-scheduler python scheduler_main.py
```

---

## 📈 모니터링

### 리소스 사용량 확인

```powershell
# 실시간 리소스 모니터링
docker stats

# 특정 컨테이너만
docker stats bitcoin-trading-bot
docker stats bitcoin-scheduler

# 전체 컨테이너 리소스
docker stats
```

### 헬스체크 확인

```powershell
# 컨테이너 상세 정보
docker inspect bitcoin-trading-bot

# 헬스체크 상태만
docker inspect --format='{{.State.Health.Status}}' bitcoin-trading-bot
docker inspect --format='{{.State.Health.Status}}' bitcoin-scheduler

# 로그로 작동 확인
docker-compose logs scheduler | grep "트레이딩 작업"
```

### Grafana 대시보드

전체 스택 실행 시 Grafana에서 실시간 모니터링 가능:

- URL: http://localhost:3001
- 기본 로그인: admin/admin
- 대시보드에서 거래 성과, 시스템 리소스 확인

---

## ⚙️ 고급 설정

### 실행 주기 변경

**.env 파일 수정:**

```env
# 30분마다 실행
SCHEDULER_INTERVAL_MINUTES=30

# 2시간마다 실행
SCHEDULER_INTERVAL_MINUTES=120
```

**적용:**

```bash
docker-compose restart scheduler
```

---

### 리소스 제한 설정

**docker-compose.yml 수정:**

```yaml
scheduler:
  # ... 기존 설정 ...
  deploy:
    resources:
      limits:
        cpus: "0.5" # CPU 50%
        memory: 512M # 메모리 512MB
      reservations:
        cpus: "0.25"
        memory: 256M
```

**적용:**

```bash
docker-compose up -d --build scheduler
```

---

### 볼륨 마운트 (개발 모드)

로컬 코드 변경사항을 즉시 반영하려면:

```yaml
scheduler:
  volumes:
    - ./src:/app/src # 소스 코드
    - ./backend:/app/backend # Backend 코드
    - ./main.py:/app/main.py
    - ./scheduler_main.py:/app/scheduler_main.py
    - ./logs:/app/logs # 로그
```

**주의:** 프로덕션에서는 권장하지 않음

**적용:**

```bash
# 볼륨 마운트로 실행 (docker-compose.yml에 이미 설정됨)
docker-compose up -d

# 코드 변경 후 컨테이너 재시작
docker-compose restart trading-bot
```

---

### 테스트 실행

```powershell
# 컨테이너 내에서 테스트 실행
docker exec -it bitcoin-trading-bot pytest

# 커버리지 포함
docker exec -it bitcoin-trading-bot pytest --cov=src --cov-report=html

# 특정 테스트만 실행
docker exec -it bitcoin-trading-bot pytest tests/test_trading_service.py
```

---

## 🔧 트러블슈팅

### 1. 컨테이너가 시작 후 바로 종료됨

**증상:**

```bash
$ docker ps
# bitcoin-scheduler가 목록에 없음
```

**원인:** .env 파일 누락 또는 API 키 오류

**해결:**

```bash
# 로그 확인
docker-compose logs scheduler

# .env 파일 확인
cat .env

# API 키 검증
docker-compose run --rm scheduler python -c "
from src.config.settings import TradingConfig
print(f'TICKER: {TradingConfig.TICKER}')
print(f'API Key exists: {bool(TradingConfig.UPBIT_ACCESS_KEY)}')
"
```

---

### 2. 이미지 빌드 실패

**증상:** `docker-compose build` 실패

**해결:**

```powershell
# 캐시 없이 재빌드
docker-compose build --no-cache

# 특정 서비스만 재빌드
docker-compose build trading-bot

# 빌드 후 재시작
docker-compose up -d --build scheduler
```

---

### 3. TA-Lib 설치 오류

Dockerfile에서 TA-Lib 설치가 실패하는 경우:

```dockerfile
# Dockerfile 수정 (이미 포함되어 있음)
RUN wget https://github.com/TA-Lib/ta-lib/releases/download/v0.4.0/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/usr && \
    make && \
    make install
```

---

### 4. PostgreSQL 연결 실패

**증상:**

```
sqlalchemy.exc.OperationalError: could not connect to server
```

**원인:** PostgreSQL 컨테이너가 준비되지 않음

**해결:**

```bash
# PostgreSQL 상태 확인
docker-compose ps postgres

# 전체 스택으로 실행 (depends_on 설정)
docker-compose up -d

# 또는 PostgreSQL 먼저 시작
docker-compose up -d postgres
sleep 10
docker-compose up -d scheduler
```

---

### 5. 포트 충돌

**증상:** `port is already allocated` 에러

**해결:**

```powershell
# 사용 중인 포트 확인 (8000번 포트)
netstat -ano | findstr :8000

# 프로세스 종료 (PID 확인 후)
taskkill /PID <PID> /F

# 또는 docker-compose.yml에서 포트 변경
```

---

### 6. 로그에 한글이 깨짐

**원인:** 인코딩 문제 (Windows)

**해결:**

```bash
# Docker 로그를 UTF-8로 확인
docker-compose logs scheduler | iconv -f UTF-8 -t UTF-8

# 또는 VS Code 터미널 사용
# 또는 PowerShell에서 인코딩 설정
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

---

### 7. 스케줄러가 실행되지 않음

**증상:** 로그에 아무것도 없음

**디버깅:**

```bash
# 컨테이너 내부 접속
docker exec -it bitcoin-scheduler /bin/bash

# 수동 실행 테스트
python scheduler_main.py

# Python 경로 확인
which python
python --version

# 모듈 import 테스트
python -c "from backend.app.core.scheduler import start_scheduler"

# 환경변수 확인
docker-compose config
```

---

### 8. 컨테이너 실행 실패

**해결:**

```powershell
# 로그 확인
docker-compose logs trading-bot

# 환경변수 확인
docker-compose config

# 컨테이너 재생성
docker-compose down
docker-compose up -d
```

---

## 🔒 보안 고려사항

### 1. .env 파일 보호

```bash
# .env 파일 권한 설정 (Linux/Mac)
chmod 600 .env

# Git에서 제외 확인
git check-ignore .env

# .gitignore에 추가 확인
echo ".env" >> .gitignore
```

**주의사항:**

- ❌ .env 파일을 Git에 커밋하지 마세요
- ✅ env.example 템플릿만 커밋하세요
- ✅ API 키는 절대 공개하지 마세요

---

### 2. Docker Secrets (프로덕션)

프로덕션에서는 Docker Secrets 사용:

```bash
# Secret 생성
echo "your_api_key" | docker secret create upbit_access_key -

# docker-compose.yml에서 사용
secrets:
  - upbit_access_key
```

---

### 3. 네트워크 격리

```yaml
networks:
  trading_network:
    driver: bridge
    internal: true # 외부 접근 차단
```

---

## 📦 백업 및 복구

### 로그 백업

```bash
# 로그 디렉토리 백업
docker cp bitcoin-scheduler:/app/logs ./logs_backup

# 또는 볼륨 마운트 사용 (이미 설정됨)
tar -czf logs_backup_$(date +%Y%m%d).tar.gz ./logs

# Windows PowerShell
Compress-Archive -Path .\logs -DestinationPath "logs_backup_$(Get-Date -Format 'yyyyMMdd').zip"
```

### 데이터베이스 백업

```bash
# PostgreSQL 백업
docker exec bitcoin-postgres pg_dump -U trading_user trading_db > backup.sql

# 복원
docker exec -i bitcoin-postgres psql -U trading_user trading_db < backup.sql
```

### 컨테이너 이미지 백업

```bash
# 이미지 저장
docker save bitcoin-scheduler:latest | gzip > scheduler_image.tar.gz

# 이미지 복원
docker load < scheduler_image.tar.gz
```

---

## 🚀 프로덕션 배포

### 배포 전 체크리스트

- [ ] **.env 파일 설정 완료**
- [ ] **API 키 검증 완료**
- [ ] **Telegram 알림 테스트 완료**
- [ ] **로그 로테이션 설정**
- [ ] **모니터링 대시보드 설정 (Grafana)**
- [ ] **자동 재시작 설정 (`restart: unless-stopped`)**
- [ ] **리소스 제한 설정**
- [ ] **백업 전략 수립**
- [ ] **알림 규칙 설정 (Prometheus AlertManager)**
- [ ] **보안 검토 완료**
- [ ] **방화벽 설정 확인**
- [ ] **SSL 인증서 설정 (HTTPS)**

### 프로덕션 배포 명령

```bash
# 전체 스택 배포
docker-compose up -d

# 상태 확인
docker-compose ps

# 로그 모니터링
docker-compose logs -f

# 헬스체크
docker inspect --format='{{.State.Health.Status}}' bitcoin-scheduler
```

---

## 📚 추가 명령어

### 전체 정리

```bash
# 모든 컨테이너 중지 및 제거
docker-compose down

# 전체 스택 중지 및 제거
docker-compose down

# 이미지까지 제거
docker-compose down --rmi all

# 볼륨까지 제거 (데이터 삭제 주의!)
docker-compose down -v --rmi all
```

### 디스크 정리

```bash
# 사용하지 않는 컨테이너/이미지/볼륨 정리
docker system prune -a

# 볼륨만 정리
docker volume prune

# 네트워크 정리
docker network prune
```

---

## 📝 환경변수 설명

| 변수명                       | 설명                    | 필수 여부 | 기본값              |
| ---------------------------- | ----------------------- | --------- | ------------------- |
| `UPBIT_ACCESS_KEY`           | Upbit API 액세스 키     | ✅ 필수   | -                   |
| `UPBIT_SECRET_KEY`           | Upbit API 시크릿 키     | ✅ 필수   | -                   |
| `OPENAI_API_KEY`             | OpenAI API 키           | ✅ 필수   | -                   |
| `TICKER`                     | 거래 종목 (예: KRW-ETH) | ⭕ 선택   | KRW-ETH             |
| `BUY_PERCENTAGE`             | 매수 비율 (0~1)         | ⭕ 선택   | 0.95                |
| `SELL_PERCENTAGE`            | 매도 비율 (0~1)         | ⭕ 선택   | 0.95                |
| `AI_MODEL`                   | AI 모델명               | ⭕ 선택   | gpt-4-turbo-preview |
| `LOG_LEVEL`                  | 로그 레벨               | ⭕ 선택   | INFO                |
| `SCHEDULER_INTERVAL_MINUTES` | 스케줄러 실행 주기 (분) | ⭕ 선택   | 60                  |
| `TELEGRAM_ENABLED`           | Telegram 알림 사용 여부 | ⭕ 선택   | false               |
| `TELEGRAM_BOT_TOKEN`         | Telegram 봇 토큰        | ⭕ 선택   | -                   |
| `TELEGRAM_CHAT_ID`           | Telegram 채팅 ID        | ⭕ 선택   | -                   |

---

## 🆘 지원

문제가 발생하면:

1. **로그 확인**: `docker-compose logs -f`
2. **트러블슈팅 섹션 참고**: 위 문제 해결 가이드 확인
3. **GitHub Issues**: 문제 보고
4. **Telegram 알림**: 에러 알림 확인
5. **Grafana 대시보드**: 메트릭 확인

---

## 🔗 관련 문서

- [README.md](../README.md) - 프로젝트 개요
- [ARCHITECTURE.md](./ARCHITECTURE.md) - 아키텍처 설명
- [USER_GUIDE.md](./USER_GUIDE.md) - 사용자 가이드
- [SCHEDULER_GUIDE.md](./SCHEDULER_GUIDE.md) - 스케줄러 가이드

---

**작성일**: 2026-01-02
**최종 업데이트**: 2026-01-01
**버전**: 2.1.0
**상태**: 프로덕션 준비 완료 ✅
