# 1. 클린 아키텍처 관점 전체 시스템 리뷰 및 리팩토링안

작성일: 2026-01-02
목적: dg_bot을 **상용 자동매매 시스템**으로 만들기 위한 구조적 평가

---

## 1. 현재 구조 요약
- 클린 아키텍처 계층 존재: Domain / Application / Infrastructure / Container
- 실제 실행 경로는 레거시(main.py, src/trading/*)와 혼재
- Backend(FastAPI)는 운영/모니터링 중심, 트레이딩 코어 소유 X

---

## 2. 장점

### (1) 아키텍처적 장점
- 의존성 역전 구조 존재 → 테스트/확장 잠재력 큼
- Port/Adapter 개념 도입 완료
- 레거시 브리지로 점진적 이전 가능

### (2) 상용화에 유리한 점
- 운영 스택(DB, API, Monitoring) 이미 존재
- 도메인 모델 분리 가능성 확보

---

## 3. 단점 (상용 관점 리스크)

### (1) 트레이딩 코어가 2개
- 레거시 실행 경로 vs 클린 유스케이스
- 상태/AI/퍼시스턴스 중복

### (2) 실행 책임 불명확
- backend scheduler → main 직접 import
- 계층 침범으로 배포/테스트 리스크 증가

### (3) 상태 단일성 붕괴
- JSON/메모리/DB 혼재
- 다중 인스턴스에서 사고 위험

---

## 4. 리팩토링 제안 (우선순위)

### Phase 1: 코어 단일화
- 트레이딩 코어를 Application UseCase로 고정
- main.py는 thin entrypoint로 축소
- backend/scheduler는 Container 통해 UseCase 호출

### Phase 2: 상태 단일화
- Risk/Position/Order 상태 → DB 단일화
- 파일 기반 상태 제거

### Phase 3: 아키텍처 정리
- Legacy Bridge 단계적 제거
- 테스트는 UseCase 단위 중심으로 재편

---

## 5. 결론
현재 구조는 **데모/MVP에는 충분**하나,
상용 서비스에는 **구조적 정합성 부족**.
클린 아키텍처를 “완성”시키는 리팩토링이 필요.
