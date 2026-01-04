# PLAN: ML 튜닝을 위한 매매 데이터 수집

**작성일**: 2026-01-04
**상태**: 📋 계획 필요
**선행 조건**: PLAN_signal-based-entry.md Phase 1-3 완료
**예상 범위**: Medium (2-3 phases)

---

**CRITICAL INSTRUCTIONS**: 각 페이즈 완료 후:
1. ✅ 완료된 작업 체크박스 체크
2. 🧪 품질 게이트 검증 명령 실행
3. ⚠️ 모든 품질 게이트 항목 통과 확인
4. 📅 "Last Updated" 날짜 업데이트
5. 📝 Notes 섹션에 학습 내용 문서화
6. ➡️ 다음 페이즈로 진행

⛔ 품질 게이트 스킵 또는 실패 상태에서 진행 금지

---

## 📋 개요

### 배경
- PLAN_signal-based-entry.md에서 신호 기반 진입 시스템 구축 완료 (Phase 1-3)
- 현재 SignalAnalyzer 파라미터는 수동 설정된 상태
- 실제 매매 데이터를 수집하여 파라미터 최적화 기반 마련 필요

### 목표
1. **매매 데이터 수집 파이프라인**: 진입/청산 시점의 신호 스냅샷 저장
2. **진입-청산 연결**: 각 거래의 전체 라이프사이클 추적
3. **ML 분석 준비**: 피처 정규화 및 스키마 표준화

### 아키텍처 결정 (TODO)

> ⚠️ 이 섹션은 구현 전 아키텍처 검토 필요

| 결정 | 선택 | 근거 |
|------|------|------|
| 저장소 | TBD | PostgreSQL vs 파일 기반 |
| ID 체계 | ULID | 시간순 정렬 + UUID 호환 |
| 스키마 버전 | v1 | 초기 스키마 |

---

## 🏗️ 아키텍처 설계 (TODO)

### Clean Architecture 배치

```
src/
├── domain/
│   └── (순수 비즈니스 로직, 이 기능에서는 사용 안 함)
│
├── application/
│   ├── ports/outbound/
│   │   └── trade_data_port.py    # 저장 포트 인터페이스
│   └── services/
│       └── trade_data_collector.py  # 수집 서비스
│
└── infrastructure/
    └── adapters/persistence/
        └── trade_data_adapter.py  # 실제 저장 구현
```

### 데이터 흐름

```
[진입 시]
ExecutionStage._execute_buy()
    → TradeDataCollector.save_entry_snapshot()
        → TradeDataPort.save_signal_snapshot()
            → TradeDataAdapter (DB/파일)

[청산 시]
HybridRiskCheckStage._execute_position_exit()
    → TradeDataCollector.save_exit_outcome()
        → TradeDataPort.save_trade_outcome()
            → TradeDataAdapter (DB/파일)
```

---

## 📊 데이터 스키마 명세

### ID 설계

| ID | 형식 | 생성 시점 | 용도 |
|----|------|----------|------|
| `snapshot_id` | ULID | SignalSnapshot 생성 시 | 스냅샷 고유 식별, 시간순 정렬 가능 |
| `decision_id` | ULID | DecisionRecord 저장 시 | 개별 결정 추적, 분석용 |
| `entry_snapshot_id` | 참조 | TradeOutcome 생성 시 | 진입-청산 연결 |

> **ID 관계 정의**:
> - `DecisionRecord.decision_id`는 `SignalSnapshot.snapshot_id`와 1:1 매핑
> - `TradeOutcome`에는 `decision_id`를 함께 저장하여 결정-결과 추적 가능
> - 쿼리: `TradeOutcome.decision_id → DecisionRecord → SignalSnapshot`

```python
# ID 생성 예시
import ulid

snapshot_id = str(ulid.new())  # e.g., "01ARZ3NDEKTSV4RRFFQ69G5FAV"
# ULID 장점: UUID 호환 + 시간순 정렬 + URL-safe
```

### 진입-청산 연결 흐름

```
1. 진입 시: SignalSnapshot 생성 → snapshot_id 발급
2. 주문 실행: ExecutionStage가 snapshot_id를 Position에 저장
3. 청산 시: Position.snapshot_id로 TradeOutcome.entry_snapshot_id 설정
4. ML 분석: entry_snapshot_id로 진입 조건과 결과를 JOIN
```

### 스키마 정의

```python
# 신호 스냅샷 (진입 시점)
SignalSnapshot = {
    "snapshot_id": str,              # ULID (신규)
    "timestamp": datetime,           # UTC 기준
    "ticker": str,                   # e.g., "KRW-BTC"
    "current_price": Decimal,
    "signal_decision": str,          # strong_buy, buy, hold, sell, strong_sell
    "total_score": float,
    "buy_score": float,
    "sell_score": float,
    "signal_strength": float,
    "confidence": str,               # high, medium, low, very_low
    "indicators": {
        "rsi": float,
        "macd": float,
        "macd_signal": float,
        "bb_position": float,        # 현재가의 BB 내 위치 (0-1)
        "atr_pct": float,            # ATR / 현재가 * 100
        "volume_ratio": float,       # 현재 거래량 / 평균 거래량
        # ... 기타 지표
    },
    "signals": List[str],            # 개별 신호 목록
}

# 거래 결과 (청산 시점)
TradeOutcome = {
    "entry_snapshot_id": str,        # SignalSnapshot 참조
    "decision_id": str,              # DecisionRecord 참조 (결정-결과 추적용)
    "exit_timestamp": datetime,
    "exit_price": Decimal,
    "pnl_pct": float,                # 수익률 (%)
    "holding_hours": float,          # 보유 시간
    "exit_reason": str,              # rule_stop_loss, rule_take_profit, ai_sell, manual
    "slippage_pct": float,           # 예상가 vs 실제가 차이 (%)
    "fee_pct": float,                # 수수료율
}
```

---

## 🔧 Phase 1: 데이터 수집 인프라 구축

### 목표
TradeDataCollector 및 저장 인프라 구축

### 테스트 전략
- **테스트 유형**: Unit + Integration
- **커버리지 목표**: 80%
- **테스트 파일**: `tests/unit/application/test_trade_data_collector.py`

### 작업 목록

#### RED
- [ ] `test_trade_data_logged_on_execution` 작성
- [ ] `test_signal_snapshot_saved` 작성
- [ ] `test_outcome_recorded_on_position_close` 작성

#### GREEN
- [ ] `TradeDataPort` 인터페이스 정의
- [ ] `TradeDataCollector` 클래스 생성
- [ ] 매매 실행 시 신호 스냅샷 저장 로직

#### REFACTOR
- [ ] 저장소 선택 결정 (PostgreSQL vs 파일)
- [ ] `TradeDataAdapter` 구현

### 변경 파일
```
src/application/ports/outbound/trade_data_port.py  # 저장 포트 (새 파일)
src/application/services/trade_data_collector.py   # Application 서비스
src/infrastructure/adapters/persistence/trade_data_adapter.py  # 저장 어댑터
tests/unit/application/test_trade_data_collector.py
```

### 품질 게이트
- [ ] 프로젝트 빌드 성공
- [ ] TDD 준수
- [ ] 신규 테스트 통과
- [ ] 기존 테스트 통과

### 롤백 전략
- 수집 로직 비활성화
- 관련 파일 제거

---

## 🔧 Phase 2: 진입-청산 연결

### 목표
진입 시 snapshot_id를 Position에 저장하고, 청산 시 TradeOutcome과 연결

### 작업 목록

#### RED
- [ ] `test_snapshot_id_saved_on_entry` 작성
- [ ] `test_outcome_linked_to_entry_snapshot` 작성

#### GREEN
- [ ] Position에 snapshot_id 필드 추가
- [ ] ExecutionStage에서 snapshot_id 저장
- [ ] HybridRiskCheckStage 청산 시 TradeOutcome 생성

#### REFACTOR
- [ ] 쿼리 최적화
- [ ] 연결 무결성 검증

### 품질 게이트
- [ ] 프로젝트 빌드 성공
- [ ] TDD 준수
- [ ] 신규 테스트 통과
- [ ] 진입-청산 연결 검증

---

## 🔧 Phase 3: 피처 정규화 및 분석 준비

### 목표
수집된 데이터를 ML 분석에 적합한 형태로 정규화

### 작업 목록

#### RED
- [ ] `test_indicators_normalized` 작성
- [ ] `test_export_to_dataframe` 작성

#### GREEN
- [ ] 지표 정규화 로직 (0-1 스케일링 등)
- [ ] DataFrame 변환 유틸리티

#### REFACTOR
- [ ] 피처 정규화 방식 문서화
- [ ] 스키마 버전 관리

### 품질 게이트
- [ ] 프로젝트 빌드 성공
- [ ] TDD 준수
- [ ] 데이터 저장 검증 (수동 확인)

---

## 🎯 리스크 평가

| 리스크 | 확률 | 영향 | 완화 전략 |
|--------|------|------|-----------|
| 데이터 수집 성능 영향 | Low | Medium | 비동기 저장, 배치 처리 |
| 저장소 선택 실패 | Medium | Low | 추상화된 Port로 교체 용이 |
| 스키마 변경 필요 | Medium | Medium | 스키마 버전 관리 |

---

## ⚠️ 보류된 최적화 (데이터 축적 후)

> **퀀트 원칙**: "먼저 동작하게 만들고, 데이터를 모으고, 그 다음 최적화하라"

| 항목 | 보류 이유 | 재검토 시점 |
|------|-----------|-------------|
| ATR 기반 동적 손절/익절 | 매매 데이터 없음 | 최소 50건 거래 후 |
| 코인별 임계값 캘리브레이션 | 분포 데이터 필요 | 데이터 축적 후 |
| ValidationPort 재설계 | 현재 STUB 상태 | 이 계획과 통합 |

---

## 📝 Notes

*(진행 시 학습 내용 기록)*

---

**Last Updated**: 2026-01-04
