# 아키텍처 리뷰 리포트

**날짜**: 2026-01-02
**리뷰어**: Antigravity (Google Deepmind)
**범위**: 시스템 아키텍처 및 클린 아키텍처 준수 여부

## 1. 강점 (Pros)

### ✅ 탁월한 클린 아키텍처 구현
이 코드베이스는 클린 아키텍처 원칙을 교과서적으로 구현하고 있습니다.
- **순수 도메인 계층 (Pure Domain Layer)**: `src/domain/services/risk_calculator.py`가 외부 의존성이나 인프라 코드 없이 오직 `entities`와 `value_objects`에만 의존함을 확인했습니다.
- **명확한 계층 분리**:
    - `src/domain`: 비즈니스 규칙 및 엔티티
    - `src/application`: 유스케이스 및 워크플로우 로직
    - `src/infrastructure`: 외부 구현 (DB, API, 로깅)
    - `src/presentation`: 진입점 (스케줄러, Main)
- **의존성 역전 (Dependency Inversion)**: `container.py`를 사용한 DI(의존성 주입) 패턴을 통해 상위 모듈이 하위 모듈에 의존하지 않도록 잘 설계되었습니다.

### ✅ 적응형 파이프라인 설계
`ARCHITECTURE.md`에 기술된 **5단계 적응형 트레이딩 파이프라인(Barrier-Based Adaptive Pipeline)**은 확장성이 매우 뛰어난 구조입니다.
- **"진입(Entry)" vs "관리(Management)" 분리**: 이는 초보적인 봇들이 자주 놓치는 핵심적인 구분입니다. 이미 보유한 포지션을 관리하는 로직은 신규 진입 로직과는 완전히 달라야 합니다.
- **멀티 코인 지원**: 파이프라인이 '스캐닝' -> '필터링' -> '선택' 과정을 명시적으로 처리하고 있어, 단일 종목이 아닌 전체 자산 유니버스를 대상으로 운영하기에 적합합니다.

### ✅ 회복 탄력성 (Resilience) 기능
- **서킷 브레이커 (Circuit Breakers)**: `RiskManager`가 일일/주간 손실 한도를 철저히 관리합니다.
- **세이프 모드 (Safe Mode)**: 치명적인 오류나 리스크 한도 초과 시 자동으로 거래를 차단하는 안전장치가 마련되어 있습니다.

## 2. 약점 (Cons)

### ⚠️ 파일 기반 상태 관리
`RiskManager`가 영속성을 위해 로컬 JSON 파일(`data/risk_state.json`)을 사용하는 `src/risk/state_manager.py`에 의존하고 있습니다.
- **동시성 위험 (Concurrency Risk)**: 스케줄러가 중복 실행되거나 웹 대시보드 등 다른 인스턴스가 동시에 실행될 경우, 데이터 손상이나 레이스 컨디션(경합 조건)이 발생할 가능성이 높습니다.
- **데이터 무결성**: JSON 파일은 ACID 트랜잭션을 지원하지 않습니다. 쓰기 작업 중 시스템이 비정상 종료되면 리스크 상태 전체가 손상되어, 중요한 손실 한도 카운터가 초기화될 위험이 있습니다.

### ⚠️ 복잡성 오버헤드
단일 사용자 시스템치고는 전체 클린 아키텍처 계층(DTO, Value Objects, Domain Services 등)이 다소 과도한 보일러플레이트(상용구 코드)를 유발합니다.
- **개발 마찰**: 간단한 기능 하나를 추가하려 해도 4~5개 계층(Entity -> Repository Interface -> Repository Impl -> Service -> Controller)을 모두 수정해야 합니다.
- **과도한 추상화**: 일부 간단한 로직이 추상화 계층 깊숙이 숨어 있어, 강력한 IDE 없이는 디버깅 흐름을 따라가기 어려울 수 있습니다.

## 3. 개선 사항 및 제언

### 🔧 1. 리스크 상태를 DB로 이관 (마이그레이션)
**우선순위**: 높음
**조치**: `RiskStateManager` (JSON 방식)를 SQLite 또는 PostgreSQL 구현체로 교체하세요.
- 이미 스택에 포함된 `SQLAlchemy` ORM을 활용하십시오.
- 시스템 충돌 후에도 "손실 기록 초기화(Free Ride)"가 발생하지 않도록 PnL(손익) 업데이트 시 원자적(Atomic) 트랜잭션을 보장해야 합니다.

### 🔧 2. 아키텍처 규칙 강제화
**우선순위**: 중간
**조치**: CI/CD 파이프라인에 아키텍처 검사 도구를 추가하세요.
- `import-linter`나 `mypy` 설정을 사용하여 `src.domain`이 `src.infrastructure`를 import하는 것을 엄격히 금지해야 합니다. 이는 시간이 지나면서 아키텍처가 무너지는 것을 방지합니다.
- 예시 규칙: "`src.domain` 내부에서는 `src.infrastructure.*` 모듈을 import 할 수 없다."

### 🔧 3. 이벤트 기반 결합도 완화 (Decoupling)
**우선순위**: 낮음 (향후 과제)
**조치**: 내부 이벤트 버스(Event Bus)를 구현하세요.
- 파이프라인이 `RiskManager`를 직접 호출하는 대신, `OrderFilled`(주문 체결됨)와 같은 이벤트를 발행(Emit)하는 방식입니다.
- 이렇게 하면 핵심 트레이딩 로직을 수정하지 않고도 새로운 기능(예: 별도의 알림 서비스, 특화된 로깅 모듈 등)을 플러그인처럼 추가할 수 있습니다.
