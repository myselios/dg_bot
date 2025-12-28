# PostgreSQL 데이터베이스 상태 리포트

**작성일**: 2025-12-28  
**환경**: Full-Stack Docker Compose  
**데이터베이스**: PostgreSQL 15 (Alpine)

---

## 📊 데이터베이스 연결 정보

- **컨테이너**: `trading_bot_postgres`
- **호스트**: `localhost:5432`
- **데이터베이스**: `trading_bot`
- **사용자**: `postgres`
- **상태**: ✅ **정상 동작 중** (Healthy)

---

## 📋 테이블 현황 요약

총 **6개의 테이블**이 정상적으로 생성되어 있습니다.

| 테이블명                | 레코드 수 | 상태           | 용도              |
| ----------------------- | --------- | -------------- | ----------------- |
| **trades**              | 0         | ⚪ 빈 상태     | 거래 내역 저장    |
| **ai_decisions**        | 0         | ⚪ 빈 상태     | AI 판단 로그      |
| **orders**              | 0         | ⚪ 빈 상태     | 주문 내역 추적    |
| **portfolio_snapshots** | 0         | ⚪ 빈 상태     | 포트폴리오 스냅샷 |
| **system_logs**         | 0         | ⚪ 빈 상태     | 시스템 로그       |
| **bot_config**          | 5         | ✅ 초기화 완료 | 봇 설정           |

**총 레코드 수**: 5개 (초기 설정 데이터)

---

## 🗄️ 테이블 스키마 상세

### 1️⃣ trades (거래 내역)

실제 체결된 거래 내역을 저장합니다.

**컬럼 구조**:

- `id` (INT): 기본 키
- `trade_id` (VARCHAR(100)): 거래소 고유 ID (Unique)
- `symbol` (VARCHAR(20)): 거래 심볼 (예: KRW-BTC)
- `side` (VARCHAR(10)): 매수(buy) / 매도(sell)
- `price` (NUMERIC(20,8)): 체결 가격
- `amount` (NUMERIC(20,8)): 거래 수량
- `total` (NUMERIC(20,8)): 총 거래 금액
- `fee` (NUMERIC(20,8)): 거래 수수료
- `status` (VARCHAR(20)): 거래 상태 (completed, pending, failed)
- `created_at` (TIMESTAMP): 거래 생성 시각
- `updated_at` (TIMESTAMP): 최종 업데이트 시각

**인덱스**:

- PRIMARY KEY: `id`
- UNIQUE INDEX: `trade_id`
- INDEX: `symbol`, `status`, `created_at`
- COMPOSITE INDEX: `(symbol, created_at)` - 심볼별 시계열 조회 최적화

---

### 2️⃣ ai_decisions (AI 판단 로그)

AI의 매매 의사결정 과정과 근거를 기록합니다.

**컬럼 구조**:

- `id` (INT): 기본 키
- `symbol` (VARCHAR(20)): 거래 심볼
- `decision` (VARCHAR(20)): AI 판단 (buy, sell, hold)
- `confidence` (NUMERIC(5,2)): 판단 신뢰도 (0-100%)
- `reason` (TEXT): AI 판단 이유
- `market_data` (JSONB): 당시 시장 데이터 (OHLCV, 기술적 지표 등)
- `created_at` (TIMESTAMP): 판단 시각

**인덱스**:

- PRIMARY KEY: `id`
- INDEX: `symbol`, `decision`, `created_at`
- COMPOSITE INDEX: `(symbol, decision, created_at)` - 심볼별 판단 유형 분석 최적화

**JSONB 컬럼 활용**:

- `market_data` 필드는 OHLCV 데이터, RSI, 볼린저 밴드 등 다양한 지표를 저장
- PostgreSQL의 JSONB 타입으로 빠른 검색과 인덱싱 지원

---

### 3️⃣ orders (주문 내역)

거래소에 제출된 주문의 생명주기를 추적합니다.

**컬럼 구조**:

- `id` (INT): 기본 키
- `order_id` (VARCHAR(100)): 거래소 고유 주문 ID (Unique)
- `symbol` (VARCHAR(20)): 거래 심볼
- `side` (VARCHAR(10)): 매수(buy) / 매도(sell)
- `order_type` (VARCHAR(20)): 주문 유형 (market, limit)
- `price` (NUMERIC(20,8)): 주문 가격 (지정가의 경우)
- `amount` (NUMERIC(20,8)): 주문 수량
- `filled_amount` (NUMERIC(20,8)): 체결된 수량
- `status` (VARCHAR(20)): 주문 상태 (open, filled, cancelled, failed)
- `error_message` (TEXT): 에러 발생 시 메시지
- `created_at` (TIMESTAMP): 주문 생성 시각
- `updated_at` (TIMESTAMP): 최종 업데이트 시각

**인덱스**:

- PRIMARY KEY: `id`
- UNIQUE INDEX: `order_id`
- INDEX: `symbol`, `status`, `created_at`
- COMPOSITE INDEX: `(symbol, status, created_at)` - 심볼별 주문 상태 조회 최적화

**주문 추적 흐름**:

1. `open` (주문 제출) → 2. `filled` (체결 완료) / `cancelled` (취소) / `failed` (실패)

---

### 4️⃣ portfolio_snapshots (포트폴리오 스냅샷)

시간대별 포트폴리오 가치를 기록하여 수익률 추적이 가능합니다.

**컬럼 구조**:

- `id` (INT): 기본 키
- `total_value_krw` (NUMERIC(20,2)): 총 자산 가치 (KRW)
- `total_value_usd` (NUMERIC(20,2)): 총 자산 가치 (USD)
- `positions` (JSONB): 포지션 상세 정보
- `created_at` (TIMESTAMP): 스냅샷 생성 시각

**인덱스**:

- PRIMARY KEY: `id`
- INDEX: `created_at` (내림차순 B-tree) - 최신 스냅샷 빠른 조회

**positions JSONB 구조 예시**:

```json
{
  "KRW-BTC": {
    "amount": 0.5,
    "value_krw": 50000000,
    "profit_rate": 15.5
  },
  "KRW-ETH": {
    "amount": 10.0,
    "value_krw": 5000000,
    "profit_rate": -2.3
  },
  "KRW": {
    "amount": 10000000
  }
}
```

---

### 5️⃣ system_logs (시스템 로그)

애플리케이션 실행 중 발생한 모든 이벤트를 기록합니다.

**컬럼 구조**:

- `id` (INT): 기본 키
- `level` (VARCHAR(20)): 로그 레벨 (info, warning, error, critical)
- `message` (TEXT): 로그 메시지
- `context` (JSONB): 추가 컨텍스트 정보
- `created_at` (TIMESTAMP): 로그 생성 시각

**인덱스**:

- PRIMARY KEY: `id`
- INDEX: `level`, `created_at`
- COMPOSITE INDEX: `(level, created_at)` - 로그 레벨별 시계열 조회 최적화

**로그 레벨 활용**:

- `info`: 일반 정보 (트레이딩 실행, API 호출 등)
- `warning`: 경고 (API 제한 임박, 잔고 부족 등)
- `error`: 에러 (API 오류, 주문 실패 등)
- `critical`: 치명적 오류 (DB 연결 끊김, 시스템 중단 등)

---

### 6️⃣ bot_config (봇 설정)

런타임에 변경 가능한 봇 설정을 저장합니다.

**컬럼 구조**:

- `id` (INT): 기본 키
- `key` (VARCHAR(100)): 설정 키 (Unique)
- `value` (JSONB): 설정 값
- `description` (TEXT): 설정 설명
- `updated_at` (TIMESTAMP): 최종 업데이트 시각

**인덱스**:

- PRIMARY KEY: `id`
- UNIQUE INDEX: `key`

**현재 설정 값**:

| 설정 키                    | 값                                    | 설명                         |
| -------------------------- | ------------------------------------- | ---------------------------- |
| `bot_status`               | `{"enabled": false}`                  | 봇 활성화 상태               |
| `trading_interval_minutes` | `{"minutes": 60}`                     | 거래 실행 주기 (1시간)       |
| `max_trade_amount_krw`     | `{"amount": 1000000}`                 | 1회 최대 거래 금액 (100만원) |
| `risk_level`               | `{"level": "medium"}`                 | 리스크 수준 (중간)           |
| `target_symbols`           | `{"symbols": ["KRW-BTC", "KRW-ETH"]}` | 거래 대상 코인               |

---

## ✅ 데이터베이스 상태 진단

### 🟢 정상 항목

1. ✅ **PostgreSQL 컨테이너 정상 실행 중** (Healthy)
2. ✅ **6개 테이블 모두 정상 생성됨**
3. ✅ **인덱스 전략 잘 구성됨** (시계열, 복합 인덱스 포함)
4. ✅ **JSONB 타입 활용** (유연한 데이터 구조)
5. ✅ **초기 설정 데이터 정상 로드됨** (bot_config 5개 레코드)
6. ✅ **한글 주석 정상 표시** (PostgreSQL UTF-8 인코딩)

### 🟡 주의 항목

1. ⚪ **거래 데이터 없음** (trades, orders 테이블 빈 상태)

   - **원인**: 봇이 아직 실행되지 않았거나 `bot_status.enabled = false`
   - **해결**: 봇을 활성화하고 스케줄러 실행 필요

2. ⚪ **AI 판단 로그 없음** (ai_decisions 테이블 빈 상태)

   - **원인**: AI 서비스가 아직 실행되지 않음
   - **해결**: 스케줄러가 실행되면 자동으로 AI 판단이 기록됨

3. ⚪ **포트폴리오 스냅샷 없음** (portfolio_snapshots 테이블 빈 상태)

   - **원인**: 주기적인 스냅샷 수집이 시작되지 않음
   - **해결**: 스케줄러가 실행되면 1시간마다 자동 기록

4. ⚪ **시스템 로그 없음** (system_logs 테이블 빈 상태)
   - **원인**: 백엔드 서비스의 로그가 DB에 기록되도록 설정 필요
   - **해결**: 현재는 파일 로그만 사용 중, DB 로깅 활성화 고려

### ⚠️ 권장 사항

1. **봇 활성화**:

   ```sql
   UPDATE bot_config
   SET value = '{"enabled": true}'
   WHERE key = 'bot_status';
   ```

2. **스케줄러 실행 확인**:

   ```bash
   docker ps --filter "name=trading_bot_scheduler"
   ```

3. **데이터 쌓임 모니터링**:
   - 1시간 후 다시 레코드 수 확인
   - AI 판단이 정상적으로 기록되는지 확인
   - 포트폴리오 스냅샷 생성 확인

---

## 🔍 데이터베이스 확인 명령어

### Docker exec로 PostgreSQL 직접 접근

```bash
# 테이블 목록 조회
docker exec trading_bot_postgres psql -U postgres -d trading_bot -c "\dt"

# 특정 테이블 스키마 확인
docker exec trading_bot_postgres psql -U postgres -d trading_bot -c "\d+ trades"

# 레코드 수 조회
docker exec trading_bot_postgres psql -U postgres -d trading_bot -c "SELECT COUNT(*) FROM trades;"

# 최근 거래 내역 조회
docker exec trading_bot_postgres psql -U postgres -d trading_bot -c "SELECT * FROM trades ORDER BY created_at DESC LIMIT 10;"

# 최근 AI 판단 조회
docker exec trading_bot_postgres psql -U postgres -d trading_bot -c "SELECT symbol, decision, confidence, reason, created_at FROM ai_decisions ORDER BY created_at DESC LIMIT 5;"

# 봇 설정 확인
docker exec trading_bot_postgres psql -U postgres -d trading_bot -c "SELECT key, value, description FROM bot_config ORDER BY key;"

# 포트폴리오 최신 스냅샷 조회
docker exec trading_bot_postgres psql -U postgres -d trading_bot -c "SELECT total_value_krw, positions, created_at FROM portfolio_snapshots ORDER BY created_at DESC LIMIT 1;"
```

### Python 스크립트로 확인 (생성된 파일 사용)

프로젝트 루트에 `check_db_status.py` 스크립트가 생성되어 있습니다.

```bash
# Windows (가상환경 사용)
.\venv\Scripts\python.exe check_db_status.py

# Linux/Mac
python check_db_status.py
```

---

## 📈 데이터베이스 성능 최적화

### 인덱스 전략

각 테이블에 다음과 같은 인덱스가 설정되어 있습니다:

1. **기본 인덱스** (모든 테이블):

   - Primary Key (id)
   - created_at (시계열 조회)

2. **복합 인덱스** (조회 패턴 최적화):

   - trades: `(symbol, created_at)` - 코인별 거래 이력
   - ai_decisions: `(symbol, decision, created_at)` - 코인별 AI 판단 분석
   - orders: `(symbol, status, created_at)` - 코인별 주문 상태 추적

3. **JSONB 인덱스** (필요 시 추가 가능):
   ```sql
   -- market_data 내 특정 필드 검색 속도 향상
   CREATE INDEX idx_ai_decisions_market_data_rsi
   ON ai_decisions USING GIN ((market_data->'rsi'));
   ```

### 쿼리 성능 모니터링

```sql
-- 느린 쿼리 확인
SELECT * FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;

-- 인덱스 사용률 확인
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;
```

---

## 🔒 보안 및 백업

### 현재 설정

- ✅ **비밀번호 설정**: 환경 변수로 관리 (.env)
- ✅ **네트워크 격리**: Docker 내부 네트워크 (`trading_network`)
- ✅ **데이터 영속성**: Docker Volume (`postgres_data`)

### 권장 보안 설정

1. **프로덕션 환경에서 비밀번호 변경**:

   ```env
   POSTGRES_PASSWORD=강력한_비밀번호로_변경
   ```

2. **정기 백업 설정**:

   ```bash
   # 수동 백업
   docker exec trading_bot_postgres pg_dump -U postgres trading_bot > backup_$(date +%Y%m%d).sql

   # 복원
   docker exec -i trading_bot_postgres psql -U postgres trading_bot < backup_20251228.sql
   ```

3. **SSL 연결 활성화** (프로덕션 환경):
   - PostgreSQL 설정에 SSL 인증서 추가
   - 연결 문자열에 `?sslmode=require` 추가

---

## 🎯 다음 단계

### 즉시 실행 가능한 작업

1. ✅ **데이터베이스 확인 완료** (현재 문서)

2. 🔄 **봇 활성화 및 테스트**:

   - Frontend에서 봇 활성화
   - 또는 직접 SQL로 설정 변경
   - 1시간 후 데이터 쌓임 확인

3. 📊 **Grafana 대시보드 설정**:

   - PostgreSQL을 데이터소스로 추가
   - 거래 내역, AI 판단 등 시각화

4. 🔔 **알림 설정**:
   - 거래 체결 시 Telegram 알림
   - 에러 발생 시 알림

### 장기 개선 사항

1. **데이터 파티셔닝**:

   - 거래량이 많아지면 월별/주별 파티션 고려
   - 오래된 데이터 아카이빙

2. **읽기 전용 복제본**:

   - 분석용 읽기 전용 DB 추가
   - 메인 DB 부하 분산

3. **연결 풀링**:
   - PgBouncer 추가
   - 동시 연결 수 최적화

---

## 📚 참고 자료

### 프로젝트 문서

- [아키텍처 가이드](../ARCHITECTURE.md)
- [Docker 가이드](../DOCKER_GUIDE.md)
- [모니터링 설정](../MONITORING_SETUP_COMPLETE.md)

### PostgreSQL 공식 문서

- [JSONB 타입](https://www.postgresql.org/docs/15/datatype-json.html)
- [인덱스 최적화](https://www.postgresql.org/docs/15/indexes.html)
- [백업 및 복구](https://www.postgresql.org/docs/15/backup.html)

### SQLAlchemy 문서

- [비동기 지원](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [ORM 모델](https://docs.sqlalchemy.org/en/20/orm/mapping_styles.html)

---

**리포트 작성**: AI Assistant  
**검증 완료**: 2025-12-28  
**다음 업데이트**: 봇 활성화 후 데이터 쌓임 확인
