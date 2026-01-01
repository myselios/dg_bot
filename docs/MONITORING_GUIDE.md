# 📊 모니터링 시스템 가이드

> AI 자동매매 시스템의 프로덕션 레벨 모니터링 완벽 가이드

**최종 업데이트**: 2026-01-01
**버전**: 2.1.0
**상태**: ✅ 구현 완료 및 운영 중

---

## 📋 목차

1. [개요](#-개요)
2. [시스템 아키텍처](#-시스템-아키텍처)
3. [구성 요소](#-구성-요소)
4. [실행 방법](#-실행-방법)
5. [Grafana 대시보드](#-grafana-대시보드)
6. [Alert Rules](#-alert-rules)
7. [Telegram 알림](#-telegram-알림)
8. [PostgreSQL 모니터링](#-postgresql-모니터링)
9. [문제 해결](#-문제-해결)

---

## 🎯 개요

### 구현된 기능

AI 트레이딩 봇의 모든 운영 지표를 실시간으로 모니터링하고, 이상 상황 발생 시 즉시 알림을 전송합니다.

**핵심 기능:**

- 📊 **실시간 메트릭 수집** - Prometheus를 통한 시계열 데이터 수집
- 📈 **시각화 대시보드** - Grafana를 통한 직관적인 데이터 시각화
- 🔔 **즉시 알림** - Telegram을 통한 실시간 거래/에러 알림
- ⚠️ **자동 경고** - Prometheus Alert Rules로 이상 감지
- 💾 **데이터베이스 모니터링** - PostgreSQL 성능 추적

### 모니터링 범위

| 카테고리         | 메트릭                    | 설명                        |
| ---------------- | ------------------------- | --------------------------- |
| **스케줄러**     | 작업 성공/실패 횟수       | 자동 거래 실행 통계         |
| **스케줄러**     | 작업 실행 시간            | 평균/최대 실행 시간 추적    |
| **AI 판단**      | 결정 분포 (Buy/Sell/Hold) | AI의 거래 결정 통계         |
| **AI 검증**      | 검증 거부 횟수            | AI 의사결정 검증 거부 통계  |
| **거래**         | 거래 횟수 및 거래량       | 실제 체결된 거래 추적       |
| **리스크 관리**  | Circuit Breaker 발동      | 일일/주간 손실 한도 초과    |
| **리스크 관리**  | 손절/익절 실행 횟수       | 자동 손절/익절 발동 통계    |
| **리스크 관리**  | 거래 빈도 제한 발동       | 최소 거래 간격 위반 차단    |
| **포트폴리오**   | 자산 가치 추이            | 실시간 포트폴리오 가치 변화 |
| **포트폴리오**   | 일일/주간 P&L             | 손익 추이 모니터링          |
| **시스템**       | API 응답 시간             | Backend 성능 모니터링       |
| **시스템**       | 에러 발생 건수            | 시스템 안정성 추적          |
| **데이터베이스** | 활성 연결 수              | PostgreSQL 리소스 사용률    |
| **데이터베이스** | 쿼리 실행 시간            | 데이터베이스 성능           |

---

## 🏗 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                  Trading Bot Application                     │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   main.py    │  │   Backend    │  │  Scheduler   │      │
│  │   (거래)      │  │    (API)     │  │  (자동실행)   │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │              │
│         │     ┌───────────┴──────────┐       │              │
│         │     │   메트릭 수집         │       │              │
│         └─────┤  (prometheus_client) ├───────┘              │
│               └───────────┬──────────┘                       │
└───────────────────────────┼──────────────────────────────────┘
                            │ :8000/metrics
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │ Prometheus  │  │  Telegram   │  │ PostgreSQL  │
    │ (메트릭)     │  │   (알림)     │  │  Exporter   │
    │  :9090      │  │             │  │  :9187      │
    └──────┬──────┘  └─────────────┘  └──────┬──────┘
           │                                  │
           │         ┌────────────────────────┘
           │         │
           ▼         ▼
    ┌─────────────────────┐
    │     Grafana         │
    │   (대시보드)         │
    │      :3001          │
    └─────────────────────┘
```

### 데이터 흐름

1. **메트릭 수집**: Backend, Scheduler, PostgreSQL이 메트릭 생성
2. **저장**: Prometheus가 10초마다 scrape하여 시계열 DB에 저장
3. **시각화**: Grafana가 Prometheus 데이터를 쿼리하여 대시보드 표시
4. **알림**:
   - Prometheus Alert Rules가 조건 감지
   - Telegram Bot이 실시간 알림 전송

---

## 🔧 구성 요소

### 1. Prometheus (메트릭 수집 & 저장)

**역할**: 시계열 메트릭 수집 및 저장

**설정 파일**: `monitoring/prometheus.yml`

```yaml
global:
  scrape_interval: 10s # 10초마다 수집
  evaluation_interval: 10s # Alert 규칙 평가 주기

# 메트릭 수집 대상
scrape_configs:
  - job_name: "backend"
    static_configs:
      - targets: ["backend:8000"] # Backend API

  - job_name: "postgres"
    static_configs:
      - targets: ["postgres-exporter:9187"] # PostgreSQL

# Alert 규칙 파일
rule_files:
  - "alert_rules.yml"
```

**접속 정보**:

- URL: http://localhost:9090
- Targets: http://localhost:9090/targets
- Alerts: http://localhost:9090/alerts

**주요 메트릭**:

```promql
# 스케줄러 작업 성공/실패
scheduler_job_success_total{job_name="trading_job"}
scheduler_job_failure_total{job_name="trading_job"}

# 작업 실행 시간
scheduler_job_duration_seconds{job_name="trading_job"}

# AI 판단
ai_decision_total{symbol="KRW-ETH", decision="buy"}

# 거래
trades_total{symbol="KRW-ETH"}

# 포트폴리오
portfolio_value_krw

# API 성능
http_request_duration_seconds
```

---

### 2. Grafana (시각화 대시보드)

**역할**: 메트릭 시각화 및 대시보드 제공

**설정 파일**:

- 데이터소스: `monitoring/grafana/datasources/prometheus.yml`
- 대시보드: `monitoring/grafana/dashboards/trading-bot-dashboard.json`

**접속 정보**:

- URL: http://localhost:3001
- 계정: `admin` / `admin`

**자동 프로비저닝**:

Docker Compose 실행 시 자동으로:

1. Prometheus 데이터소스 연결
2. "AI Trading Bot - 실시간 모니터링" 대시보드 로드

---

### 3. Telegram Bot (실시간 알림)

**역할**: 거래 실행 및 에러 발생 시 즉시 알림

**알림 종류**:

1. **거래 실행 알림** (매수/매도)

```
🤖 거래 실행
━━━━━━━━━━━━━━━━━━━━
종목: KRW-ETH
거래: 매수 (BUY)
가격: 4,350,000원
수량: 0.0115 ETH
총액: 50,000원
판단 근거: RSI 과매도 구간 진입, MACD 골든크로스 임박
━━━━━━━━━━━━━━━━━━━━
신뢰도: HIGH
시각: 2025-12-28 14:30:15
```

2. **에러 알림**

```
⚠️ 시스템 에러 발생
━━━━━━━━━━━━━━━━━━━━
에러 타입: APIConnectionError
메시지: Upbit API 연결 실패
컨텍스트: {"ticker": "KRW-ETH"}
시각: 2025-12-28 14:32:10
```

3. **봇 상태 알림**

```
✅ 봇 시작됨
━━━━━━━━━━━━━━━━━━━━
상태: 스케줄러 시작
메시지: 스케줄러가 시작되었습니다. (주기: 1시간)
시각: 2025-12-28 14:00:00
```

4. **일일 리포트** (매일 오전 9시)

```
📊 일일 거래 리포트
━━━━━━━━━━━━━━━━━━━━
📅 기간: 2025-12-27 ~ 2025-12-28

**AI 판단 통계**
• 총 판단 횟수: 24회
• 매수 (BUY): 3회
• 매도 (SELL): 2회
• 관망 (HOLD): 19회

**수익 현황**
• 손익: +15,000원 (+1.50%)
• 현재 포트폴리오: 1,015,000원
```

**설정 방법**: [Telegram 설정 가이드](./TELEGRAM_SETUP_GUIDE.md) 참조

---

### 4. PostgreSQL Exporter (DB 모니터링)

**역할**: PostgreSQL 성능 지표 수집

**메트릭**:

- `pg_up`: 데이터베이스 연결 상태
- `pg_stat_database_numbackends`: 활성 연결 수
- `pg_stat_database_tup_inserted`: 삽입된 튜플 수
- `pg_stat_database_tup_updated`: 업데이트된 튜플 수
- `pg_locks_count`: 락 개수
- `pg_database_size_bytes`: 데이터베이스 크기

**Grafana 패널**:

- 활성 연결 수
- 데이터베이스 크기 추이
- 쿼리 실행 통계
- 락 상태

**설정**: [PostgreSQL 모니터링 설정](./GRAFANA_POSTGRES_SETUP.md) 참조

---

## 🚀 실행 방법

### 전체 스택 실행 (권장)

```bash
# 모든 서비스 시작 (PostgreSQL, Backend, Scheduler, Prometheus, Grafana)
docker-compose -f docker-compose.full-stack.yml up -d

# 로그 확인
docker-compose -f docker-compose.full-stack.yml logs -f

# 특정 서비스 로그만
docker-compose -f docker-compose.full-stack.yml logs grafana -f
```

**접속 URL**:

- Backend API: http://localhost:8000/docs
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001 (admin/admin)

### 개별 서비스 실행

```bash
# Prometheus만
docker-compose up -d prometheus

# Grafana만
docker-compose up -d grafana

# 모니터링 스택 (Prometheus + Grafana)
docker-compose up -d prometheus grafana
```

### 환경 변수 설정 (.env)

```env
# Telegram 알림 (필수)
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Sentry 에러 추적 (선택)
SENTRY_ENABLED=false
SENTRY_DSN=https://your_dsn@sentry.io/project_id
SENTRY_ENVIRONMENT=production

# PostgreSQL (데이터베이스)
POSTGRES_USER=trading_user
POSTGRES_PASSWORD=trading_password
POSTGRES_DB=trading_db
```

---

## 📊 Grafana 대시보드

### "AI Trading Bot - 실시간 모니터링" 대시보드

**파일**: `monitoring/grafana/dashboards/trading-bot-dashboard.json`

#### 패널 구성 (10개)

##### Row 1: 스케줄러 상태

1. **스케줄러 작업 성공/실패** (Pie Chart)

   - 메트릭: `scheduler_job_success_total`, `scheduler_job_failure_total`
   - 설명: 작업 성공/실패 비율 시각화

2. **작업 실행 시간 추이** (Time Series)
   - 메트릭: `scheduler_job_duration_seconds`
   - 임계값: 300초 (5분)
   - 설명: 작업 실행 시간 추적 (지연 감지)

##### Row 2: AI 판단 분석

3. **AI 판단 분포** (Donut Chart)

   - 메트릭: `sum by (decision) (ai_decision_total)`
   - 설명: Buy/Sell/Hold 결정 분포

4. **AI 판단 추이** (Time Series)
   - 메트릭: `rate(ai_decision_total[5m])`
   - 설명: 시간별 AI 결정 빈도

##### Row 3: 시스템 상태

5. **Backend 상태** (Stat)

   - 메트릭: `up{job="backend"}`
   - 설명: Backend 실행 여부 (1=UP, 0=DOWN)

6. **총 에러 건수** (Stat)

   - 메트릭: `sum(bot_errors_total)`
   - 설명: 누적 에러 횟수

7. **API 응답 시간 (p95)** (Stat)
   - 메트릭: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))`
   - 설명: 95 백분위 응답 시간

##### Row 4: 거래 & 포트폴리오

8. **총 거래 횟수** (Stat)

   - 메트릭: `sum(trades_total)`
   - 설명: 누적 거래 횟수

9. **포트폴리오 가치 추이** (Time Series)

   - 메트릭: `portfolio_value_krw`
   - 설명: 실시간 자산 가치 변화

10. **시간별 스케줄러 성공/실패** (Time Series)
    - 메트릭: `increase(scheduler_job_success_total[1h])`, `increase(scheduler_job_failure_total[1h])`
    - 설명: 1시간 단위 성공/실패 추이

#### 대시보드 접속

1. http://localhost:3001 접속
2. `admin` / `admin` 로그인
3. 좌측 메뉴 → Dashboards
4. "AI Trading Bot - 실시간 모니터링" 선택

---

## ⚠️ Alert Rules

**파일**: `monitoring/alert_rules.yml`

### 설정된 경고 규칙 (7개)

| Alert 이름              | 조건                 | 심각도   | 설명                    |
| ----------------------- | -------------------- | -------- | ----------------------- |
| **SchedulerJobFailed**  | 10분 내 실패 > 0     | Critical | 스케줄러 작업 실패 감지 |
| **SchedulerJobSlow**    | 실행 시간 > 5분      | Warning  | 작업 실행 지연          |
| **HighErrorRate**       | 에러율 > 0.1/초      | Warning  | 에러 발생률 증가        |
| **SlowAPIResponse**     | p95 > 2초            | Warning  | API 응답 지연           |
| **MetricsNotCollected** | Backend UP == 0      | Critical | 메트릭 수집 중단        |
| **SchedulerDown**       | 메트릭 없음 (5분)    | Critical | 스케줄러 중단           |
| **AIDecisionStalled**   | 2시간 동안 판단 없음 | Warning  | AI 판단 중단            |

### Alert 확인

```bash
# Prometheus Alerts 페이지
http://localhost:9090/alerts

# Alert Rules 확인
http://localhost:9090/rules

# Alert 테스트 (스케줄러 중지)
docker-compose -f docker-compose.full-stack.yml stop scheduler

# 5분 후 "SchedulerDown" Alert 발생 확인
```

### Alert 규칙 예시

```yaml
groups:
  - name: trading_bot_alerts
    interval: 30s
    rules:
      - alert: SchedulerJobFailed
        expr: increase(scheduler_job_failure_total{job_name="trading_job"}[10m]) > 0
        for: 1m
        labels:
          severity: critical
          component: scheduler
        annotations:
          summary: "스케줄러 작업 실패 감지"
          description: "{{ $labels.job_name }} 작업이 실패했습니다."
```

---

## 🔔 Telegram 알림

### 설정 방법

**상세 가이드**: [Telegram 설정 가이드](./TELEGRAM_SETUP_GUIDE.md)

**빠른 설정 (10분)**:

1. **Telegram 봇 생성**:

   - @BotFather 검색
   - `/newbot` 입력
   - 봇 이름 및 사용자명 설정
   - Bot Token 복사

2. **Chat ID 확인**:

   - 봇에게 `/start` 전송
   - `https://api.telegram.org/bot<TOKEN>/getUpdates` 접속
   - `chat.id` 값 복사

3. **환경 변수 설정** (`.env`):

```env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=987654321
```

4. **스케줄러 재시작**:

```bash
docker-compose -f docker-compose.full-stack.yml restart scheduler
```

### 알림 테스트

```bash
# 로그 확인 (Telegram 전송 메시지 확인)
docker-compose -f docker-compose.full-stack.yml logs scheduler -f | grep Telegram

# 출력 예시:
# "✅ Telegram 시작 알림 전송 완료"
```

---

## 💾 PostgreSQL 모니터링

### PostgreSQL Exporter 설정

**docker-compose.full-stack.yml**에 이미 포함됨:

```yaml
postgres-exporter:
  image: prometheuscommunity/postgres-exporter:latest
  container_name: bitcoin-postgres-exporter
  environment:
    DATA_SOURCE_NAME: "postgresql://trading_user:trading_password@postgres:5432/trading_db?sslmode=disable"
  ports:
    - "9187:9187"
  networks:
    - trading-network
```

### Grafana 대시보드

**PostgreSQL 전용 패널**:

1. 활성 연결 수
2. 데이터베이스 크기
3. 쿼리 실행 통계
4. 락 상태

**메트릭 예시**:

```promql
# 활성 연결 수
pg_stat_database_numbackends{datname="trading_db"}

# 데이터베이스 크기
pg_database_size_bytes{datname="trading_db"}

# 삽입/업데이트 통계
rate(pg_stat_database_tup_inserted[5m])
```

**상세 가이드**: [PostgreSQL 모니터링 설정](./GRAFANA_POSTGRES_SETUP.md)

---

## 🛠 문제 해결

### Q1. Prometheus에서 메트릭이 수집되지 않아요

**증상**: http://localhost:9090/targets 에서 Backend가 DOWN 상태

**해결 방법**:

1. **Backend 실행 확인**:

```bash
docker-compose -f docker-compose.full-stack.yml ps backend
```

2. **Backend 메트릭 엔드포인트 확인**:

```bash
curl http://localhost:8000/metrics
```

3. **Prometheus 설정 확인**:

```yaml
# monitoring/prometheus.yml
scrape_configs:
  - job_name: "backend"
    static_configs:
      - targets: ["backend:8000"] # Docker 네트워크 내부 주소
```

4. **Prometheus 재시작**:

```bash
docker-compose -f docker-compose.full-stack.yml restart prometheus
```

---

### Q2. Grafana 데이터소스 연결이 안 돼요

**증상**: "Data source is not working"

**해결 방법**:

1. **Prometheus URL 확인**:

   - Docker: `http://prometheus:9090`
   - 로컬: `http://localhost:9090`

2. **Prometheus 실행 확인**:

```bash
docker-compose -f docker-compose.full-stack.yml logs prometheus
```

3. **네트워크 연결 테스트**:

```bash
docker exec -it bitcoin-grafana ping prometheus
```

4. **수동 데이터소스 추가**:
   - Configuration → Data Sources → Add data source
   - Prometheus 선택
   - URL: `http://prometheus:9090`
   - Save & Test

---

### Q3. Telegram 알림이 오지 않아요

**증상**: 로그에 "Telegram 알림 전송 실패"

**해결 방법**:

1. **Bot Token 확인**:

```bash
cat .env | grep TELEGRAM_BOT_TOKEN
```

2. **Chat ID 확인**:

```bash
curl https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
```

3. **수동 테스트**:

```python
import requests

token = "YOUR_BOT_TOKEN"
chat_id = "YOUR_CHAT_ID"
message = "Test message"

url = f"https://api.telegram.org/bot{token}/sendMessage"
response = requests.post(url, json={
    "chat_id": chat_id,
    "text": message
})
print(response.json())
```

4. **`.env` 파일 형식 확인**:

```env
# 따옴표 없이 입력
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=123456:ABC-DEF
TELEGRAM_CHAT_ID=987654321
```

---

### Q4. Alert Rules가 작동하지 않아요

**증상**: Prometheus에서 알림이 발생하지 않음

**해결 방법**:

1. **Alert Rules 파일 확인**:

```bash
cat monitoring/alert_rules.yml
```

2. **Prometheus 설정 확인**:

```yaml
# monitoring/prometheus.yml
rule_files:
  - "alert_rules.yml" # 주석 해제되어 있어야 함
```

3. **Prometheus 재시작**:

```bash
docker-compose -f docker-compose.full-stack.yml restart prometheus
```

4. **Rules 로드 확인**:

   - http://localhost:9090/rules 접속
   - 등록된 규칙 목록 확인

5. **Alert 상태 확인**:
   - http://localhost:9090/alerts 접속
   - Firing/Pending 상태 확인

---

### Q5. 대시보드가 자동 로드되지 않아요

**증상**: Grafana 접속 시 대시보드가 비어 있음

**해결 방법**:

1. **프로비저닝 설정 확인**:

```yaml
# monitoring/grafana/dashboards/dashboard.yml
apiVersion: 1
providers:
  - name: "Bitcoin Trading Bot"
    orgId: 1
    folder: ""
    type: file
    options:
      path: /var/lib/grafana/dashboards
```

2. **대시보드 파일 확인**:

```bash
ls -la monitoring/grafana/dashboards/trading-bot-dashboard.json
```

3. **Grafana 재시작**:

```bash
docker-compose -f docker-compose.full-stack.yml restart grafana
```

4. **수동 Import**:
   - Grafana → Create → Import
   - `monitoring/grafana/dashboards/trading-bot-dashboard.json` 파일 업로드

---

## 📈 성능 및 리소스

### Docker 컨테이너 리소스

| 컨테이너            | CPU       | 메모리     | 디스크           |
| ------------------- | --------- | ---------- | ---------------- |
| Prometheus          | ~50MB     | ~200MB     | ~1GB (15일 보관) |
| Grafana             | ~30MB     | ~150MB     | ~500MB           |
| PostgreSQL Exporter | ~10MB     | ~50MB      | -                |
| **합계**            | **~90MB** | **~400MB** | **~1.5GB**       |

### 네트워크 사용

- Prometheus scrape: 10초마다 ~10KB
- Telegram 알림: 메시지당 ~1KB
- Grafana 대시보드: 페이지 로드당 ~100KB

### 보관 정책

**Prometheus**:

- 기본 보관 기간: 15일
- 변경: `--storage.tsdb.retention.time=30d` (Docker 명령)

**Grafana**:

- 대시보드 설정은 영구 보관
- 사용자 설정은 Docker 볼륨에 저장

---

## 🔧 운영 가이드

### 일일 체크리스트

- [ ] Grafana 대시보드 확인 (http://localhost:3001)
- [ ] 스케줄러 작업 성공/실패 횟수 확인
- [ ] Telegram 알림 정상 수신 확인
- [ ] 로그 파일 용량 확인 (`logs/scheduler/`)

### 주간 체크리스트

- [ ] 성능 추이 분석 (작업 실행 시간)
- [ ] 에러 패턴 분석
- [ ] 알림 규칙 조정 필요 여부 확인
- [ ] Docker 컨테이너 상태 확인
- [ ] 디스크 용량 확인

### 로그 관리

```bash
# 로그 정리 (30일 이상 된 파일 삭제)
find logs/ -name "*.log" -mtime +30 -delete

# 로그 아카이빙
tar -czf logs_backup_$(date +%Y%m%d).tar.gz logs/
```

---

## 📚 관련 문서

- **[시스템 기능명세서](./SYSTEM_SPECIFICATION.md)** - 전체 시스템 동작 방식
- **[스케줄러 가이드](./SCHEDULER_GUIDE.md)** - 자동 거래 스케줄링
- **[거래 기록 저장 흐름도](./TRADE_RECORDING_FLOW.md)** - PostgreSQL 거래 내역 저장 프로세스 ✨ NEW
- **[Telegram 설정 가이드](./TELEGRAM_SETUP_GUIDE.md)** - Telegram 알림 설정
- **[Docker 가이드](./DOCKER_GUIDE.md)** - Docker 실행 방법
- **[사용자 가이드](./USER_GUIDE.md)** - 전체 사용법

---

**작성일**: 2025-12-28  
**최종 업데이트**: 2025-12-28  
**작성자**: AI Assistant  
**상태**: ✅ 구현 완료 및 운영 중
