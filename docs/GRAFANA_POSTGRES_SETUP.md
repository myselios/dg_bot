# Grafana에서 PostgreSQL 모니터링 설정 가이드

**작성일**: 2025-12-28  
**환경**: Full-Stack Docker Compose

---

## 📊 개요

Grafana에서 PostgreSQL 데이터베이스를 데이터소스로 추가하여 거래 내역, AI 판단, 포트폴리오 등을 실시간으로 모니터링할 수 있습니다.

---

## 🔌 1. Grafana 접속

### 접속 정보

- **URL**: http://localhost:3001
- **기본 계정**:
  - 사용자명: `admin`
  - 비밀번호: `admin` (최초 로그인 시 변경 요청)

```bash
# 브라우저에서 접속
start http://localhost:3001
```

---

## 🗄️ 2. PostgreSQL 데이터소스 추가

### Step 1: 데이터소스 추가 화면 이동

1. Grafana 왼쪽 메뉴에서 **⚙️ Configuration** → **Data Sources** 클릭
2. **Add data source** 버튼 클릭
3. **PostgreSQL** 선택

### Step 2: 연결 설정

다음 정보를 입력합니다:

| 항목             | 값                       | 설명                          |
| ---------------- | ------------------------ | ----------------------------- |
| **Name**         | `Trading Bot PostgreSQL` | 데이터소스 이름               |
| **Host**         | `postgres:5432`          | Docker 네트워크 내부 호스트명 |
| **Database**     | `trading_bot`            | 데이터베이스 이름             |
| **User**         | `postgres`               | 사용자명                      |
| **Password**     | `postgres`               | 비밀번호 (.env 파일 참조)     |
| **TLS/SSL Mode** | `disable`                | 로컬 개발 환경                |
| **Version**      | `15.0`                   | PostgreSQL 버전               |

**⚠️ 중요**: Host는 `localhost`가 아니라 `postgres`입니다!  
(Docker 네트워크 내부에서는 서비스 이름으로 접근)

### Step 3: 연결 테스트

1. **Save & test** 버튼 클릭
2. ✅ "Database Connection OK" 메시지 확인

**문제 해결**:

```sql
-- 연결 실패 시 PostgreSQL 컨테이너에서 직접 확인
docker exec -it trading_bot_postgres psql -U postgres -d trading_bot -c "\dt"
```

---

## 📈 3. 대시보드 생성

### 3-1. 새 대시보드 생성

1. 왼쪽 메뉴에서 **+ Create** → **Dashboard** 클릭
2. **Add visualization** 클릭
3. 데이터소스에서 **Trading Bot PostgreSQL** 선택

---

### 3-2. 패널 예제

#### 📊 패널 1: 총 거래 수 (Stat)

**쿼리**:

```sql
SELECT COUNT(*) as "거래 수"
FROM trades
WHERE status = 'completed'
```

**패널 설정**:

- Visualization: **Stat**
- Title: `총 거래 수`
- Unit: `short`
- Color mode: `Value`

---

#### 📉 패널 2: 시간대별 거래 추이 (Time series)

**쿼리**:

```sql
SELECT
  created_at as "time",
  COUNT(*) as "거래 수"
FROM trades
WHERE
  created_at >= NOW() - INTERVAL '7 days'
  AND status = 'completed'
GROUP BY
  DATE_TRUNC('hour', created_at)
ORDER BY time
```

**패널 설정**:

- Visualization: **Time series**
- Title: `시간대별 거래 추이`
- Legend: `Show`
- Tooltip mode: `All`

---

#### 💰 패널 3: 수익/손실 추이 (Time series)

**쿼리**:

```sql
SELECT
  created_at as "time",
  CASE
    WHEN side = 'buy' THEN -total
    WHEN side = 'sell' THEN total
  END as "수익/손실"
FROM trades
WHERE
  created_at >= NOW() - INTERVAL '30 days'
  AND status = 'completed'
ORDER BY time
```

**패널 설정**:

- Visualization: **Time series**
- Title: `누적 수익/손실`
- Unit: `currency (KRW)`
- Color scheme: `Green-Yellow-Red (by value)`

---

#### 🤖 패널 4: AI 판단 분포 (Pie chart)

**쿼리**:

```sql
SELECT
  decision as "판단",
  COUNT(*) as "횟수"
FROM ai_decisions
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY decision
ORDER BY "횟수" DESC
```

**패널 설정**:

- Visualization: **Pie chart**
- Title: `AI 판단 분포 (최근 7일)`
- Legend: `Right` with `Value`

---

#### 📊 패널 5: 최근 거래 내역 (Table)

**쿼리**:

```sql
SELECT
  created_at as "시각",
  symbol as "심볼",
  side as "구분",
  price as "가격",
  amount as "수량",
  total as "거래금액",
  status as "상태"
FROM trades
ORDER BY created_at DESC
LIMIT 20
```

**패널 설정**:

- Visualization: **Table**
- Title: `최근 거래 내역`
- Column alignment: 숫자는 우측 정렬

---

#### 💼 패널 6: 포트폴리오 가치 추이 (Time series)

**쿼리**:

```sql
SELECT
  created_at as "time",
  total_value_krw as "총 자산 (KRW)",
  total_value_usd as "총 자산 (USD)"
FROM portfolio_snapshots
WHERE created_at >= NOW() - INTERVAL '30 days'
ORDER BY time
```

**패널 설정**:

- Visualization: **Time series**
- Title: `포트폴리오 가치 추이`
- Unit: `currency (KRW)`
- Y-axis: `Auto min/max`

---

#### 🎯 패널 7: AI 신뢰도 평균 (Gauge)

**쿼리**:

```sql
SELECT
  AVG(confidence) as "평균 신뢰도"
FROM ai_decisions
WHERE
  created_at >= NOW() - INTERVAL '7 days'
  AND confidence IS NOT NULL
```

**패널 설정**:

- Visualization: **Gauge**
- Title: `AI 평균 신뢰도 (최근 7일)`
- Min: `0`, Max: `100`
- Unit: `percent (0-100)`
- Thresholds:
  - 🔴 0-50 (Red)
  - 🟡 50-70 (Yellow)
  - 🟢 70-100 (Green)

---

#### ⚠️ 패널 8: 시스템 로그 (Logs)

**쿼리**:

```sql
SELECT
  created_at as "time",
  level as "레벨",
  message as "메시지"
FROM system_logs
WHERE
  created_at >= NOW() - INTERVAL '1 day'
  AND level IN ('error', 'warning', 'critical')
ORDER BY time DESC
LIMIT 100
```

**패널 설정**:

- Visualization: **Logs**
- Title: `시스템 로그 (경고/에러)`
- Show time: `Yes`

---

## 🎨 4. 대시보드 레이아웃 예시

```
┌─────────────────────────────────────────────────────────────┐
│                  Bitcoin Trading Bot Dashboard               │
├──────────────┬──────────────┬──────────────┬────────────────┤
│ 총 거래 수   │ 총 수익률    │ AI 평균      │ 현재 포트폴리오 │
│   (Stat)     │   (Stat)     │ 신뢰도(Gauge)│    가치(Stat)   │
├──────────────┴──────────────┴──────────────┴────────────────┤
│                시간대별 거래 추이 (Time series)               │
├───────────────────────────────────────────────────────────────┤
│               누적 수익/손실 추이 (Time series)               │
├──────────────┬────────────────────────────────────────────────┤
│ AI 판단 분포 │           포트폴리오 가치 추이                 │
│ (Pie chart)  │           (Time series)                        │
├──────────────┴────────────────────────────────────────────────┤
│                  최근 거래 내역 (Table)                        │
├───────────────────────────────────────────────────────────────┤
│              시스템 로그 - 경고/에러 (Logs)                    │
└───────────────────────────────────────────────────────────────┘
```

---

## 🔄 5. 실시간 업데이트 설정

### 자동 새로고침 설정

1. 대시보드 우측 상단의 **🕐 Time picker** 옆 ⏱️ 아이콘 클릭
2. **Auto refresh** 설정:
   - `5s` - 5초마다 (실시간 모니터링)
   - `30s` - 30초마다 (권장)
   - `1m` - 1분마다
   - `5m` - 5분마다

**권장 설정**: `30s` - 데이터베이스 부하와 실시간성의 균형

---

## 📊 6. 고급 쿼리 예제

### 승률 계산

```sql
SELECT
  COUNT(CASE WHEN (
    SELECT price FROM trades t2
    WHERE t2.symbol = t1.symbol
      AND t2.side = 'sell'
      AND t2.created_at > t1.created_at
    ORDER BY t2.created_at ASC LIMIT 1
  ) > t1.price THEN 1 END) * 100.0 / COUNT(*) as "승률 (%)"
FROM trades t1
WHERE
  side = 'buy'
  AND status = 'completed'
  AND created_at >= NOW() - INTERVAL '30 days'
```

### 시간대별 수익률

```sql
SELECT
  DATE_TRUNC('day', created_at) as "일자",
  SUM(CASE
    WHEN side = 'sell' THEN total - fee
    WHEN side = 'buy' THEN -(total + fee)
  END) as "일일 수익"
FROM trades
WHERE
  status = 'completed'
  AND created_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE_TRUNC('day', created_at)
ORDER BY "일자"
```

### AI 판단 정확도 (매수 신호 후 실제 상승률)

```sql
SELECT
  decision as "AI 판단",
  AVG(confidence) as "평균 신뢰도",
  COUNT(*) as "판단 횟수"
FROM ai_decisions
WHERE
  created_at >= NOW() - INTERVAL '7 days'
GROUP BY decision
ORDER BY "판단 횟수" DESC
```

---

## ⚙️ 7. 데이터 수집 확인

### PostgreSQL에 데이터가 쌓이고 있는지 확인

```bash
# 테이블별 레코드 수 확인
docker exec trading_bot_postgres psql -U postgres -d trading_bot -c \
"SELECT 'trades' as table_name, COUNT(*) FROM trades
UNION ALL SELECT 'ai_decisions', COUNT(*) FROM ai_decisions
UNION ALL SELECT 'portfolio_snapshots', COUNT(*) FROM portfolio_snapshots
ORDER BY table_name;"

# 최근 AI 판단 조회
docker exec trading_bot_postgres psql -U postgres -d trading_bot -c \
"SELECT symbol, decision, confidence, created_at
FROM ai_decisions
ORDER BY created_at DESC
LIMIT 5;"
```

### 봇 상태 확인 (API)

```bash
# Windows (curl.exe 사용)
curl.exe -X GET http://localhost:8000/api/v1/bot/status

# 또는 PowerShell 스크립트 사용
.\api-call.ps1 -Method GET -Url "http://localhost:8000/api/v1/bot/status"
```

---

## 🔧 8. 문제 해결

### 문제 1: "Database Connection Failed"

**원인**: Grafana가 PostgreSQL에 연결할 수 없음

**해결 방법**:

1. Host를 `postgres:5432`로 설정했는지 확인 (`localhost` 아님!)
2. PostgreSQL 컨테이너가 실행 중인지 확인:
   ```bash
   docker ps | findstr postgres
   ```
3. 비밀번호가 `.env` 파일과 일치하는지 확인

### 문제 2: "No data" 또는 빈 패널

**원인**: PostgreSQL에 데이터가 없음

**해결 방법**:

1. 봇이 활성화되어 있는지 확인:
   ```bash
   curl.exe -X GET http://localhost:8000/api/v1/bot/status
   ```
2. 스케줄러가 실행 중인지 확인:
   ```bash
   docker logs trading_bot_scheduler --tail 20
   ```
3. 데이터가 쌓이기까지 스케줄러 주기(기본 1시간) 대기
4. 수동으로 봇 실행 (테스트용):
   ```bash
   curl.exe -X POST http://localhost:8000/api/v1/bot/control \
     -H "Content-Type: application/json" \
     -d '{\"action\":\"start\"}'
   ```

### 문제 3: 쿼리 오류

**원인**: SQL 문법 오류 또는 테이블 구조 불일치

**해결 방법**:

1. PostgreSQL에서 직접 쿼리 테스트:
   ```bash
   docker exec -it trading_bot_postgres psql -U postgres -d trading_bot
   ```
2. 테이블 스키마 확인:
   ```sql
   \d+ trades
   \d+ ai_decisions
   \d+ portfolio_snapshots
   ```
3. Grafana Query Inspector 사용 (패널 → Inspect → Query)

---

## 📚 9. 추가 리소스

### 관련 문서

- [데이터베이스 상태 리포트](./DATABASE_STATUS_REPORT.md)
- [모니터링 설정 가이드](../MONITORING_SETUP_COMPLETE.md)
- [사용자 가이드](../USER_GUIDE.md)

### Grafana 공식 문서

- [PostgreSQL 데이터소스](https://grafana.com/docs/grafana/latest/datasources/postgres/)
- [패널 및 시각화](https://grafana.com/docs/grafana/latest/panels/)
- [대시보드 모범 사례](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/best-practices/)

### SQL 참고자료

- [PostgreSQL 날짜/시간 함수](https://www.postgresql.org/docs/15/functions-datetime.html)
- [PostgreSQL 집계 함수](https://www.postgresql.org/docs/15/functions-aggregate.html)

---

## 🎯 다음 단계

1. ✅ **PostgreSQL 데이터소스 추가 완료**
2. 📊 **대시보드 패널 생성**
3. 🎨 **레이아웃 조정 및 저장**
4. ⏱️ **자동 새로고침 설정 (30초 권장)**
5. 🔔 **알림 규칙 설정** (선택적)
6. 📤 **대시보드 공유 또는 내보내기** (선택적)

---

**작성**: AI Assistant  
**업데이트**: 2025-12-28  
**버전**: 1.0
