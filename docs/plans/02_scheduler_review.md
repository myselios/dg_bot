# 2. 스케줄러 리뷰 (변동성돌파 관점) 및 리팩토링안

작성일: 2026-01-02

---

## 1. 현재 스케줄 구조
- 1시간 스케줄: 진입(매수) + 스캐닝
- 15분 스케줄: 포지션 관리(sell / hold only)
- APScheduler IntervalTrigger 사용

---

## 2. 장점

### (1) 트레이딩 관점
- 진입(1H)과 관리(15m) 역할 분리 → 과매매 방지
- 15분에서 매수 없음 → 페이크 돌파 리스크 감소

### (2) 시스템 관점
- 관리 잡에서 AI 호출 없음 → 안정성/비용 절감

---

## 3. 단점 및 운영 리스크

### (1) 락 부재
- 1H / 15m / Telegram이 동시에 실행 가능
- 상태 갱신 중 충돌 가능

### (2) Idempotency 부재
- 동일 캔들에서 중복 주문 가능성

### (3) 캔들 마감 정렬 부족
- IntervalTrigger → 캔들 경계와 어긋날 수 있음

---

## 4. 리팩토링안 (상용 필수)

### (1) 전역 락
- DB advisory lock 또는 Redis lock
- 한 시점에 하나의 trading cycle만 허용

### (2) Idempotency Key
- key = ticker-timeframe-candle_ts-action
- 이미 실행된 키는 무시

### (3) 스케줄 정렬
- IntervalTrigger → CronTrigger
- 1H: 매 정각 + 버퍼
- 15m: :00/:15/:30/:45 + 버퍼

---

## 5. 결론
현재 구조는 **의도는 매우 좋으나**
운영 안전장치가 없어 **상용 리스크가 큼**.
락 + idempotency + 마감정렬은 필수.
