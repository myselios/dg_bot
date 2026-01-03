# 아키텍처 리뷰 보고서 (Architecture Clean Architecture Review)

**작성일:** 2026-01-03
**검토자:** System Architect (AI Agent)
**대상:** `src` 디렉토리 전체 아키텍처 및 `Container` 의존성 주입 구조

---

## 1. 개요 (Executive Summary)

현재 시스템은 **Clean Architecture** 원칙을 도입하여 의존성 역전(DIP), 관심사의 분리(SoC)를 시도한 흔적이 명확합니다. 특히 `Container`를 통한 의존성 주입(DI)과 `Port`를 통한 인프라스트럭처 격리는 매우 훌륭한 출발점입니다.

그러나 **"Strict Clean Architecture"** 기준으로는 Domain Layer의 빈약함과 Use Case Layer의 비대화, 그리고 Backtest와 Live 환경의 아키텍처 불일치(Inconsistency)가 발견되었습니다. 상용화를 위해서는 이 부분이 반드시 보완되어야 합니다.

---

## 2. 상세 분석 (Deep Dive)

### 2.1 장점 (Strengths)

1.  **명확한 의존성 방향성 (Dependency Rule)**
    *   `Source Code Dependency`: Infrastructure(`adapters`) → Application(`ports`) 방향으로 잘 잡혀 있습니다.
    *   `src/container.py`에서 모든 의존성을 조립(Wiring)하는 방식은 메인 비즈니스 로직을 프레임워크로부터 독립시키는 데 성공했습니다.

2.  **포트-어댑터 패턴 (Ports & Adapters)**
    *   `ExchangePort`, `AIPort` 등 외부 시스템 통신을 인터페이스로 추상화하여, `Upbit` 종속성을 비즈니스 로직에서 제거했습니다. 이는 추후 `Binance` 등 타 거래소 확장 시 매우 유리합니다.

3.  **Use Case 중심 설계**
    *   `ExecuteTradeUseCase`와 같이 사용자의 의도(Intent)를 명확히 드러내는 클래스 명명과 구조를 갖추고 있습니다.

---

### 2.2 단점 및 문제점 (Weaknesses & Issues)

1.  **도메인 계층(Domain Layer)의 빈혈 (Anemic Domain Model)**
    *   **현상:** `Trade`, `Order` 등이 단순 데이터 뭉치(Data Class)로 존재하며, 핵심 트레이딩 규칙(예: 진입 유효성 검증, 자금 관리 계산 등)이 `UseCase`나 `Strategy` 클래스에 산재되어 있습니다.
    *   **리스크:** 비즈니스 규칙이 여러 곳(백테스터, 라이브 봇)에 중복 구현되어 로직 불일치 발생 위험이 큽니다.

2.  **UseCase의 책임 과다**
    *   **현상:** `ExecuteTradeUseCase`가 `Trade` 엔티티를 직접 생성(`new Trade(...)`)하고 저장까지 담당합니다.
    *   **개선:** 엔티티 생성과 상태 변화는 도메인 서비스(`TradeFactory` 등)나 엔티티 내부 메서드(`Order.execute() -> Trade`)로 위임해야 합니다.

3.  **Legacy와의 불안한 동거**
    *   **현상:** `src/ai/entry_analyzer.py` (Legacy)와 `AnalyzeBreakoutUseCase` (New)가 공존합니다.
    *   **리스크:** 개발자가 실수로 구형 모듈을 import하여 사용할 경우, 리팩토링된 안전 장치가 작동하지 않을 수 있습니다.

---

## 3. 리팩토링 제안 (Refactoring Roadmap)

### Phase 1: Domain Rich Model 강화
*   `Trade` 엔티티에 `calculate_fee()`, `verify_slippage()` 등의 도메인 로직을 이동시키십시오.
*   "언제 거래할 것인가"에 대한 규칙을 `TradingPolicy`와 같은 도메인 서비스로 캡슐화하십시오.

### Phase 2: Live-Backtest Core 통합
*   현재 `Backtester`는 `ExecuteTradeUseCase`와 별개로 돌아갑니다.
*   **핵심 제안:** `ExecutionPort`의 구현체를 `LiveExecutionAdapter`와 `BacktestExecutionAdapter`로 나누고, **상위 유스케이스는 동일하게 사용**하는 구조로 개편해야 합니다. 이것이 퀀트 시스템 아키텍처의 핵심입니다 (Test what you fly).

---

## 4. 상용화 가능성 분석 (Commercialization Feasibility)

*   **현재 상태:** **B- (조건부 승인)**
*   **상용화 리스크:**
    *   아키텍처적으로는 유연하나, **데이터 무결성(Data Integrity)**을 보장하는 트랜잭션 관리가 UseCase 레벨에서 명시적이지 않습니다 (`ExecuteTradeUseCase` 도중에 서버가 꺼지면?).
    *   DB Transaction 관리(`UnitOfWork` 패턴)가 도입되지 않으면 금전적 사고 시 복구가 어렵습니다.
*   **결론:** 개인 운용용으로는 훌륭하나, 고객 자금을 받는 상용 서비스로는 **Transaction Management**와 **Idempotency(멱등성)** 보강이 필수적입니다.
