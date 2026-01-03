# dg_bot 리팩토링 종합 리뷰 & PR 단위 작업 계획 (기관/상용 기준)

작성일: 2026-01-03

본 문서는 **최근 리팩토링 반영 코드(zip 기준)**를 대상으로,
퀀트 전문 트레이더 + 기관 시스템 개발자 관점에서
1) 냉정한 상태 판정
2) 남아있는 구조적 리스크
3) 상용 통과를 위한 **PR 단위 작업 순서**
를 명확히 정리한 문서다.

---

## 0. 현재 상태 한 줄 요약 (Executive Summary)

> **“방향은 맞았고, 위험한 부분은 상당히 줄었지만  
아직 ‘기관 자금/상용 서비스’ 기준에서는 통과선 아래.”**

- 락, 크론 정렬, 인트라바 백테스트, AI 프롬프트 분리 → **큰 진전**
- 그러나  
  **Idempotency 미완성**,  
  **백테스트–라이브 엔진 분리**,  
  **퍼시스턴스 단일화 미흡**  
  이 3가지가 남아 있음

---

## 1. 리팩토링 반영 사항 총정리 (팩트)

### 1.1 스케줄러/운영
- CronTrigger 기반 캔들 정렬 ✅
- PostgreSQL Advisory Lock 도입 ✅
- 1H(진입) / 15m(관리) 역할 분리 유지 ✅

### 1.2 백테스팅
- IntrabarExecutionAdapter 도입 ✅
- Worst-case 스탑 체결 가정 가능 ✅

### 1.3 AI 판단
- YAML 프롬프트 분리 + 버전 명시 ✅
- AI 역할을 “Risk Hunter(브레이크)”로 정의 ✅

---

## 2. 남아있는 핵심 리스크 (기관 기준)

### R1. Idempotency 미완성 (High Risk)
- Lock은 “동시 실행”만 막음
- 재시도/부분 실패/네트워크 오류 시
  동일 주문/결정이 다시 실행될 수 있음

**기관 판정:** ❌ Fail  
**사고 유형:** 중복 주문, 중복 기록, 계좌 왜곡

---

### R2. Backtest ↔ Live 엔진 분리 (High Risk)
- Live: Orchestrator/Pipeline
- Backtest: 별도 Strategy/Portfolio 세계관
- 동일 전략이라도 체결/비용/시간축이 다름

**기관 판정:** ❌ Fail  
**사고 유형:** 성과 착시, 실전 손실

---

### R3. 퍼시스턴스 단일성 부족 (Medium–High Risk)
- InMemoryPersistenceAdapter 기본 사용
- 프로세스 재시작/다중 인스턴스 시 상태 유실

**기관 판정:** ⚠️ Conditional Fail  
**사고 유형:** 리스크 한도 무력화

---

### R4. AI 호출 안정성/재현성 (Medium Risk)
- 단일 호출 정책/서킷브레이커 부족
- 백테스트 요약 입력의 메타데이터 불명확

**기관 판정:** ⚠️ Conditional Fail  
**사고 유형:** 판단 변동성, 비용 폭증

---

## 3. PR 단위 리팩토링 작업 순서 (강제 권장)

> ⚠️ **중요 원칙**  
> - PR 하나당 “위험요소 1개만 제거”
> - PR은 항상 **Fail → Pass** 기준으로 검증 가능해야 함

---

## PR-1. Idempotency Core 도입 (최우선, 필수)

### 목표
- “같은 캔들/같은 액션/같은 종목”은 **절대 1회만 실행**

### 작업 내용
- `IdempotencyPort` 정의
- DB 기반 `PostgresIdempotencyAdapter` 구현
- Key 규칙:
  ```
  {symbol}-{timeframe}-{candle_close_ts}-{action}
  ```
- Trading Orchestrator 시작부에서:
  - 이미 처리된 key면 즉시 return

### 통과 기준
- 네트워크 오류/재시도 상황에서도
  동일 주문 1회만 발생

---

## PR-2. Live/Backtest 공통 Execution Engine 분리

### 목표
- 체결/비용/스탑 로직 **단일 엔진화**

### 작업 내용
- `ExecutionEngine` 인터페이스 정의
- LiveExecutionEngine / BacktestExecutionEngine 분리
- IntrabarExecutionAdapter를 BacktestEngine에 포함
- Live에서도 동일 stop/TP 규칙 사용

### 통과 기준
- 같은 시그널 → Live/Backtest에서
  **논리적으로 동일한 포지션 흐름**

---

## PR-3. 퍼시스턴스 단일화 (DB Only)

### 목표
- 상태의 Single Source of Truth 확립

### 작업 내용
- `PersistencePort` 기본 구현을 Postgres로 변경
- InMemory/JSON Adapter는 dev/test 전용으로 격하
- Position / Risk / Decision / Order 상태 DB 저장

### 통과 기준
- 프로세스 재시작 후에도
  포지션/리스크/결정 상태 일관

---

## PR-4. AI 호출 정책 강제 & 안정화

### 목표
- “덜 똑똑하지만 절대 흔들리지 않는 AI”

### 작업 내용
- AI 호출 단일 어댑터 강제
- 파라미터 고정:
  - temperature ≤ 0.3
  - timeout / retry / backoff
- 실패 시 정책:
  - HOLD + 알림
  - 자동 재시도 제한
- Prompt 메타데이터 저장:
  - version / model / params / input hash

### 통과 기준
- 동일 입력 → 동일 결정
- 장애 시 거래 차단

---

## PR-5. 백테스트 신뢰도 강화 (상용 기준)

### 목표
- 백테스트 숫자를 “의사결정에 사용 가능” 수준으로

### 작업 내용
- entry/exit time → candle timestamp 기반
- 비용 분해 리포트:
  - gross / fee / slippage / net
- 성과 지표:
  - MDD, Calmar, Turnover
- Walk-forward / OOS 스캐폴딩

### 통과 기준
- 실전과의 괴리 “설명 가능” 수준 확보

---

## PR-6. 운영/감사(Audit) 마무리

### 목표
- “왜 이 주문이 나갔는지” 1시간 내 재구성 가능

### 작업 내용
- Correlation ID(trade_id) 전 구간 전파
- Decision → Order → Fill → PnL 연결
- Alert 기준 명확화

### 통과 기준
- 장애/손실 발생 시
  원인 추적 가능

---

## 4. 최종 판정 기준 (기관/상용)

| 항목 | 현재 | PR 완료 후 |
|---|---|---|
| 중복 주문 방지 | ❌ | ✅ |
| 백테스트 신뢰성 | ⚠️ | ✅ |
| 상태 일관성 | ⚠️ | ✅ |
| AI 안정성 | ⚠️ | ✅ |
| 운영 감사 | ⚠️ | ✅ |

> **PR-1 ~ PR-3 완료 시점부터  
“개인 프로젝트 → 준상용 시스템”으로 격상 가능**

---

## 5. 마지막 한마디 (냉정)

지금 구조는  
**“아무 생각 없이 만든 봇”이 아니라  
‘돈을 잃지 않기 위해 설계한 시스템’으로 가는 중**이다.

하지만 기관 기준은 잔인하다.
> *“잘 작동할 것 같다”* 는 의미가 없다.  
> *“절대 두 번 실행되지 않는다”*  
> *“실패하면 멈춘다”*  
> *“결과를 재현할 수 있다”*  
이 3개가 증명돼야 통과다.

이 문서 기준으로 PR 하나씩 밟아가면,
이 시스템은 **실제 돈을 오래 굴릴 수 있는 구조**까지 갈 수 있다.
