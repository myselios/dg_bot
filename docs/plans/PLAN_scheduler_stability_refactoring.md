# 스케줄러 안정성 리팩토링 계획

**작성일**: 2026-01-03
**마지막 업데이트**: 2026-01-03
**상태**: ✅ 완료
**예상 소요 시간**: 6-8시간

---

**CRITICAL INSTRUCTIONS**: 각 Phase 완료 후:
1. 완료된 작업의 체크박스를 체크
2. 품질 게이트 검증 명령 실행
3. 모든 품질 게이트 항목 통과 확인
4. "마지막 업데이트" 날짜 갱신
5. Notes 섹션에 학습 내용 기록
6. 다음 Phase로 진행

DO NOT skip quality gates or proceed with failing checks

---

## 1. 개요

### 1.1 목적
스케줄러의 운영 안정성을 확보하기 위한 리팩토링:
- **P0**: 중복 주문 방지 (Idempotency Key)
- **P0**: 작업 간 상태 충돌 방지 (전역 락)
- **P1**: 캔들 마감 시점 정렬 (CronTrigger)

### 1.2 배경
[docs/plans/02_scheduler_review.md](02_scheduler_review.md) 리뷰에서 식별된 문제:

| 문제 | 리스크 | 현재 상태 |
|------|--------|----------|
| Idempotency 부재 | 동일 캔들 중복 주문 → 자금 손실 | 미구현 |
| 전역 락 부재 | 1H/15m 작업 동시 실행 → 상태 충돌 | 부분 구현 (max_instances=1) |
| IntervalTrigger | 캔들 경계 불일치 → 분석 오류 | IntervalTrigger 사용 중 |

### 1.3 아키텍처 결정

**저장소**: PostgreSQL (기존 인프라 활용)
- Idempotency: `idempotency_keys` 테이블
- Lock: PostgreSQL Advisory Lock (`pg_advisory_lock`)

**버퍼 시간**: 1분
- 캔들 마감 후 데이터 안정화 대기
- 1H: 매시 01분 (:01)
- 15m: :01, :16, :31, :46

---

## 2. Phase 구성

```
Phase 1: Idempotency Port & Adapter (P0) ─────────────────── 1.5h
    │
    ▼
Phase 2: Lock Port & Adapter (P0) ────────────────────────── 1.5h
    │
    ▼
Phase 3: Scheduler Integration (P0) ──────────────────────── 2h
    │
    ▼
Phase 4: CronTrigger Migration (P1) ──────────────────────── 1.5h
```

---

## Phase 1: Idempotency Port & Adapter

**목표**: 동일 캔들에서 중복 주문 방지를 위한 Idempotency 시스템 구축

### 1.1 테스트 전략
- **테스트 유형**: Unit (Port mock), Integration (실제 DB)
- **커버리지 목표**: 90%
- **테스트 파일**: `tests/unit/application/ports/test_idempotency_port.py`

### 1.2 작업 목록

#### RED (실패하는 테스트 작성)
- [ ] `test_idempotency_port.py` 생성 - Port 인터페이스 테스트
- [ ] `test_postgres_idempotency_adapter.py` 생성 - Adapter 테스트
  - [ ] `test_check_key_not_exists_returns_false`
  - [ ] `test_mark_key_creates_record`
  - [ ] `test_check_key_exists_returns_true`
  - [ ] `test_expired_key_returns_false`
  - [ ] `test_cleanup_removes_old_keys`

#### GREEN (최소 구현)
- [ ] `IdempotencyPort` 인터페이스 정의
  ```python
  # src/application/ports/outbound/idempotency_port.py
  class IdempotencyPort(ABC):
      async def check_key(self, key: str) -> bool: ...
      async def mark_key(self, key: str, ttl_hours: int = 24) -> None: ...
      async def cleanup_expired(self) -> int: ...
  ```
- [ ] `IdempotencyKey` 모델 생성
  ```python
  # backend/app/models/idempotency_key.py
  class IdempotencyKey(Base):
      __tablename__ = "idempotency_keys"
      id: int (PK)
      key: str (unique, index)
      created_at: datetime
      expires_at: datetime
  ```
- [ ] `PostgresIdempotencyAdapter` 구현
  ```python
  # src/infrastructure/adapters/persistence/postgres_idempotency_adapter.py
  ```

#### REFACTOR
- [ ] 키 생성 헬퍼 함수 추출
  ```python
  def make_idempotency_key(ticker: str, timeframe: str, candle_ts: int, action: str) -> str:
      return f"{ticker}-{timeframe}-{candle_ts}-{action}"
  ```
- [ ] 인덱스 최적화 확인

### 1.3 품질 게이트

**빌드 & 테스트**:
- [ ] `python -m pytest tests/unit/application/ports/test_idempotency_port.py -v` 통과
- [ ] `python -m pytest tests/integration/test_postgres_idempotency.py -v` 통과

**코드 품질**:
- [ ] Type hints 완료
- [ ] Docstrings 작성

**기능 검증**:
- [ ] 키 생성 → 체크 → True 반환 확인
- [ ] 만료된 키 체크 → False 반환 확인

### 1.4 롤백 전략
- `idempotency_keys` 테이블 DROP
- 관련 파일 삭제

---

## Phase 2: Lock Port & Adapter

**목표**: trading_job과 position_management_job 간 상호 배제를 위한 분산 락 구현

### 2.1 테스트 전략
- **테스트 유형**: Unit (Port mock), Integration (실제 DB)
- **커버리지 목표**: 90%
- **테스트 파일**: `tests/unit/application/ports/test_lock_port.py`

### 2.2 작업 목록

#### RED (실패하는 테스트 작성)
- [ ] `test_lock_port.py` 생성
  - [ ] `test_acquire_lock_returns_true_when_available`
  - [ ] `test_acquire_lock_returns_false_when_held`
  - [ ] `test_release_lock_releases_lock`
  - [ ] `test_context_manager_acquires_and_releases`
  - [ ] `test_lock_timeout_releases_automatically`

#### GREEN (최소 구현)
- [ ] `LockPort` 인터페이스 정의
  ```python
  # src/application/ports/outbound/lock_port.py
  class LockPort(ABC):
      async def acquire(self, lock_name: str, timeout_seconds: int = 300) -> bool: ...
      async def release(self, lock_name: str) -> None: ...
      async def is_locked(self, lock_name: str) -> bool: ...

      @asynccontextmanager
      async def lock(self, lock_name: str, timeout_seconds: int = 300): ...
  ```
- [ ] `PostgresAdvisoryLockAdapter` 구현
  ```python
  # src/infrastructure/adapters/persistence/postgres_lock_adapter.py
  # pg_advisory_lock / pg_advisory_unlock 사용
  LOCK_IDS = {
      "trading_cycle": 1001,
      "position_management": 1002,
  }
  ```

#### REFACTOR
- [ ] Lock ID 상수 분리
- [ ] 에러 핸들링 개선 (데드락 방지)

### 2.3 품질 게이트

**빌드 & 테스트**:
- [ ] `python -m pytest tests/unit/application/ports/test_lock_port.py -v` 통과
- [ ] `python -m pytest tests/integration/test_postgres_lock.py -v` 통과

**코드 품질**:
- [ ] Context manager 정상 동작
- [ ] 예외 발생 시에도 락 해제 보장

**기능 검증**:
- [ ] 동시 락 획득 시도 → 하나만 성공
- [ ] 타임아웃 후 자동 해제

### 2.4 롤백 전략
- Advisory lock은 세션 종료 시 자동 해제
- 관련 파일 삭제

---

## Phase 3: Scheduler Integration

**목표**: 스케줄러에 Idempotency와 Lock 통합

### 3.1 테스트 전략
- **테스트 유형**: Unit (mock), Integration (실제 스케줄러)
- **커버리지 목표**: 80%
- **테스트 파일**: `tests/unit/backend/app/core/test_scheduler_safety.py`

### 3.2 작업 목록

#### RED (실패하는 테스트 작성)
- [ ] `test_scheduler_safety.py` 생성
  - [ ] `test_trading_job_acquires_lock_before_execution`
  - [ ] `test_trading_job_skips_if_lock_unavailable`
  - [ ] `test_trading_job_checks_idempotency_before_order`
  - [ ] `test_trading_job_marks_idempotency_after_order`
  - [ ] `test_position_job_waits_for_trading_job_lock`

#### GREEN (최소 구현)
- [ ] `Container`에 Port 추가
  ```python
  # src/container.py
  def get_idempotency_port(self) -> IdempotencyPort: ...
  def get_lock_port(self) -> LockPort: ...
  ```
- [ ] `scheduler.py` 수정 - `trading_job`
  ```python
  async def trading_job():
      lock_port = container.get_lock_port()
      async with lock_port.lock("trading_cycle"):
          # 기존 로직
          ...
          # 주문 실행 전
          idempotency = container.get_idempotency_port()
          key = make_idempotency_key(ticker, "1h", candle_ts, "buy")
          if await idempotency.check_key(key):
              logger.info(f"⏭️ 중복 주문 스킵: {key}")
              return
          # 주문 실행 후
          await idempotency.mark_key(key)
  ```
- [ ] `scheduler.py` 수정 - `position_management_job`
  ```python
  async def position_management_job():
      lock_port = container.get_lock_port()
      # trading_cycle 락이 해제될 때까지 대기
      async with lock_port.lock("trading_cycle", timeout_seconds=60):
          # 기존 로직
  ```

#### REFACTOR
- [ ] 락 획득 실패 시 알림 전송
- [ ] Idempotency 체크 로직 UseCase로 분리 (선택)

### 3.3 품질 게이트

**빌드 & 테스트**:
- [ ] `python -m pytest tests/unit/backend/app/core/test_scheduler_safety.py -v` 통과
- [ ] `python -m pytest tests/ -v` 전체 테스트 통과

**코드 품질**:
- [ ] 기존 테스트 회귀 없음
- [ ] 로깅 추가 (락 획득/해제, idempotency 체크)

**기능 검증**:
- [ ] 수동 테스트: 동시 실행 시 하나만 진행
- [ ] 수동 테스트: 동일 캔들 재실행 시 주문 스킵

### 3.4 롤백 전략
- `scheduler.py`의 락/idempotency 코드 제거
- Container 메서드 제거

---

## Phase 4: CronTrigger Migration

**목표**: IntervalTrigger → CronTrigger 전환으로 캔들 마감 정렬

### 4.1 테스트 전략
- **테스트 유형**: Unit (트리거 설정 검증)
- **커버리지 목표**: 70%
- **테스트 파일**: `tests/unit/backend/app/core/test_scheduler_triggers.py`

### 4.2 작업 목록

#### RED (실패하는 테스트 작성)
- [ ] `test_scheduler_triggers.py` 생성
  - [ ] `test_trading_job_runs_at_01_minutes`
  - [ ] `test_position_job_runs_at_01_16_31_46`
  - [ ] `test_jobs_aligned_to_candle_close`

#### GREEN (최소 구현)
- [ ] `add_jobs()` 수정
  ```python
  # 기존 IntervalTrigger
  # trigger=IntervalTrigger(minutes=60)

  # 변경: CronTrigger
  scheduler.add_job(
      trading_job,
      trigger=CronTrigger(
          minute=1,  # 매시 01분
          timezone="Asia/Seoul"
      ),
      id="trading_job",
      ...
  )

  scheduler.add_job(
      position_management_job,
      trigger=CronTrigger(
          minute="1,16,31,46",  # 매 15분 + 1분 버퍼
          timezone="Asia/Seoul"
      ),
      id="position_management_job",
      ...
  )
  ```
- [ ] `start_scheduler()` 수정 - 즉시 실행 옵션 유지
  ```python
  # 시작 시 즉시 실행 (개발/테스트용)
  if settings.SCHEDULER_RUN_IMMEDIATELY:
      scheduler.modify_job('trading_job', next_run_time=datetime.now())
  ```

#### REFACTOR
- [ ] 설정값 `settings.py`로 이동
  ```python
  # src/config/settings.py
  class SchedulerConfig:
      TRADING_JOB_MINUTE = 1
      POSITION_JOB_MINUTES = "1,16,31,46"
      BUFFER_MINUTES = 1
  ```

### 4.3 품질 게이트

**빌드 & 테스트**:
- [ ] `python -m pytest tests/unit/backend/app/core/test_scheduler_triggers.py -v` 통과
- [ ] 전체 테스트 통과

**코드 품질**:
- [ ] 설정값 중앙화 완료

**기능 검증**:
- [ ] 로그로 실행 시점 확인 (정각+1분)
- [ ] 캔들 데이터와 실행 시점 정합성 확인

### 4.4 롤백 전략
- CronTrigger → IntervalTrigger 복원
- 설정값 롤백

---

## 3. 리스크 평가

| 리스크 | 확률 | 영향 | 완화 전략 |
|--------|------|------|----------|
| DB 연결 실패 시 락 획득 불가 | 중 | 높음 | 폴백: 락 없이 진행 + 경고 알림 |
| Advisory Lock 데드락 | 낮음 | 높음 | 타임아웃 설정, 세션 종료 시 자동 해제 |
| Idempotency 키 충돌 | 낮음 | 중 | unique constraint + 재시도 로직 |
| CronTrigger 설정 오류 | 낮음 | 중 | 로그 모니터링, 알림 설정 |

---

## 4. 문서 업데이트 체크리스트

Phase 완료 후 업데이트 필요:
- [ ] `CLAUDE.md` - 새 Port/Adapter 설명 추가
- [ ] `docs/guide/ARCHITECTURE.md` - 락/idempotency 레이어 추가
- [ ] `docs/guide/SCHEDULER_GUIDE.md` - CronTrigger 설정 업데이트
- [ ] `docs/plans/02_scheduler_review.md` - 완료 상태로 업데이트

---

## 5. Notes & Learnings

### Phase 1: Idempotency
- `IdempotencyPort` 인터페이스와 `make_idempotency_key()` 헬퍼 함수 구현
- PostgreSQL 어댑터: `idempotency_keys` 테이블 사용 (TTL 기반 만료)
- InMemory 어댑터: 테스트용 구현
- 키 형식: `{ticker}-{timeframe}-{candle_ts}-{action}`

### Phase 2: Lock
- `LockPort` 인터페이스와 `LOCK_IDS` 상수 정의 (trading_cycle: 1001, position_management: 1002)
- PostgreSQL Advisory Lock 사용 (`pg_try_advisory_lock`, `pg_advisory_unlock`)
- Context manager (`async with lock_port.lock()`) 패턴 지원
- Lock 획득 실패 시 graceful 스킵 처리

### Phase 3: Scheduler Integration
- `Container.create_from_legacy()`에 `session_factory` 파라미터 추가
- `trading_job()`과 `position_management_job()`에 Lock 적용
- try/finally 패턴으로 Lock 해제 보장
- Lock 획득 실패 시 경고 로그 + 메트릭 기록

### Phase 4: CronTrigger Migration
- IntervalTrigger → CronTrigger 전환
- `SchedulerConfig` 클래스 추가 (버퍼 시간, 실행 분 설정)
- 캔들 마감 + 1분 버퍼로 데이터 안정성 확보
- `SCHEDULER_RUN_IMMEDIATELY` 설정으로 개발/프로덕션 모드 분리

---

## 6. 진행 상황

| Phase | 상태 | 시작일 | 완료일 |
|-------|------|--------|--------|
| Phase 1: Idempotency | ✅ 완료 | 2026-01-03 | 2026-01-03 |
| Phase 2: Lock | ✅ 완료 | 2026-01-03 | 2026-01-03 |
| Phase 3: Integration | ✅ 완료 | 2026-01-03 | 2026-01-03 |
| Phase 4: CronTrigger | ✅ 완료 | 2026-01-03 | 2026-01-03 |
