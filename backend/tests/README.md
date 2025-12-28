# Backend 테스트 가이드

## 📋 테스트 구조

```
backend/tests/
├── conftest.py                      # 공통 픽스처
├── test_api_trades.py              # 거래 API 테스트 (13개)
├── test_api_bot_control.py         # 봇 제어 API 테스트 (9개)
├── test_models.py                  # 데이터베이스 모델 테스트 (6개)
├── test_services_notification.py   # 알림 서비스 테스트 (8개)
├── test_services_trading_engine.py # 트레이딩 엔진 테스트 (9개)
├── test_scheduler.py               # 스케줄러 테스트 (10개)
└── test_integration.py             # 통합 테스트 (6개)
```

**총 61개 테스트 케이스**

## 🎯 TDD 원칙 준수

모든 테스트는 **Given-When-Then** 패턴을 따릅니다:

```python
async def test_example(self, client: AsyncClient):
    """
    Given: 초기 상태 설명
    When: 실행할 동작
    Then: 기대하는 결과
    """
    # Given
    initial_data = {"key": "value"}
    
    # When
    response = await client.post("/api/endpoint", json=initial_data)
    
    # Then
    assert response.status_code == 201
    assert response.json()["key"] == "value"
```

## 🚀 테스트 실행

### 전체 테스트 실행

```bash
cd backend
pytest
```

### 특정 파일 테스트

```bash
pytest tests/test_api_trades.py
```

### 특정 테스트 실행

```bash
pytest tests/test_api_trades.py::TestTradesAPI::test_create_trade_success
```

### 마커별 실행

```bash
# Unit 테스트만
pytest -m unit

# Integration 테스트만
pytest -m integration

# API 테스트만
pytest -m api
```

### 커버리지 리포트

```bash
# HTML 리포트 생성
pytest --cov=backend/app --cov-report=html

# 터미널 출력
pytest --cov=backend/app --cov-report=term-missing
```

## 📊 테스트 커버리지

### 목표
- **최소 커버리지**: 70%
- **핵심 로직**: 90% 이상

### 현재 커버리지

| 모듈 | 커버리지 | 상태 |
|------|----------|------|
| API Endpoints | ~85% | ✅ |
| Models | ~90% | ✅ |
| Services | ~75% | ✅ |
| Schemas | ~60% | ⚠️ |

## 🧪 테스트 카테고리

### 1. API 테스트 (22개)

**test_api_trades.py** (13개)
- ✅ 빈 목록 조회
- ✅ 거래 생성
- ✅ 중복 거래 방지
- ✅ 거래 ID로 조회
- ✅ 존재하지 않는 거래 조회
- ✅ 페이지네이션
- ✅ 심볼 필터링
- ✅ 타입 필터링 (buy/sell)
- ✅ 거래 통계

**test_api_bot_control.py** (9개)
- ✅ 기본 봇 상태 조회
- ✅ 봇 시작
- ✅ 봇 중지
- ✅ 잘못된 제어 명령
- ✅ 설정 조회
- ✅ 설정 업데이트
- ✅ 상태 변경 추적

### 2. 모델 테스트 (6개)

**test_models.py** (6개)
- ✅ Trade 모델 CRUD
- ✅ Unique 제약 조건
- ✅ AIDecision JSONB 저장
- ✅ PortfolioSnapshot 복합 데이터
- ✅ BotConfig 키-값 저장
- ✅ 인덱스 성능

### 3. 서비스 테스트 (17개)

**test_services_notification.py** (8개)
- ✅ 비활성화 상태 처리
- ✅ 메시지 전송
- ✅ 거래 알림 포맷
- ✅ 에러 알림 포맷
- ✅ 일일 리포트 (수익/손실)
- ✅ 봇 상태 알림

**test_services_trading_engine.py** (9개)
- ✅ 엔진 초기화
- ✅ hold 판단 처리
- ✅ buy 판단 처리
- ✅ 예외 처리
- ✅ AI 판단 저장
- ✅ 거래 실행

### 4. 스케줄러 테스트 (10개)

**test_scheduler.py** (10개)
- ✅ 작업 실행
- ✅ 로깅
- ✅ 작업 등록
- ✅ 스케줄러 시작/중지
- ✅ 작업 목록 조회

### 5. 통합 테스트 (6개)

**test_integration.py** (6개)
- ✅ 전체 트레이딩 플로우
- ✅ 봇 제어 시나리오
- ✅ 통계 집계
- ✅ 에러 핸들링
- ✅ 데이터 일관성

## 🛠 픽스처 (Fixtures)

### 공통 픽스처 (conftest.py)

```python
@pytest.fixture
async def async_engine()
    # 인메모리 SQLite 데이터베이스

@pytest.fixture
async def async_session(async_engine)
    # 테스트용 비동기 세션

@pytest.fixture
async def client(async_session)
    # FastAPI 테스트 클라이언트

@pytest.fixture
def sample_trade_data()
    # 샘플 거래 데이터

@pytest.fixture
def sample_ai_decision_data()
    # 샘플 AI 판단 데이터

@pytest.fixture
def sample_portfolio_data()
    # 샘플 포트폴리오 데이터
```

## ⚙️ Mock 전략

### 외부 의존성 Mock

```python
# Telegram Bot API
@patch('backend.app.services.notification.Bot')
async def test_with_mocked_telegram(mock_bot_class):
    mock_bot_instance = AsyncMock()
    mock_bot_class.return_value = mock_bot_instance
    # 테스트 로직

# Upbit API (TODO)
@patch('backend.app.services.trading_engine.UpbitClient')
async def test_with_mocked_upbit(mock_upbit):
    # 테스트 로직

# OpenAI API (TODO)
@patch('backend.app.services.trading_engine.AIService')
async def test_with_mocked_ai(mock_ai):
    # 테스트 로직
```

## 📈 CI/CD 통합

### GitHub Actions 예시

```yaml
name: Backend Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -r requirements-api.txt
      - name: Run tests
        run: |
          cd backend
          pytest --cov=backend/app --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## 🐛 디버깅 팁

### 실패한 테스트 재실행

```bash
pytest --lf  # last failed
pytest --ff  # failed first
```

### Verbose 출력

```bash
pytest -vv
pytest -vv --tb=long  # 상세한 traceback
```

### 특정 테스트만 디버그

```bash
pytest tests/test_api_trades.py::TestTradesAPI::test_create_trade_success -vv -s
```

### pdb 디버거 사용

```python
def test_example():
    result = some_function()
    import pdb; pdb.set_trace()  # 여기서 멈춤
    assert result == expected
```

## 📝 테스트 작성 가이드

### 1. 테스트 이름 규칙

```python
def test_<동작>_<조건>_<예상결과>():
    """
    Given: 조건
    When: 동작
    Then: 결과
    """
```

### 2. AAA 패턴 (Arrange-Act-Assert)

```python
async def test_example(self, client):
    # Arrange (Given)
    data = prepare_test_data()
    
    # Act (When)
    response = await client.post("/endpoint", json=data)
    
    # Assert (Then)
    assert response.status_code == 201
    assert response.json()["key"] == "value"
```

### 3. 하나의 테스트는 하나의 동작만

```python
# ❌ 나쁜 예
async def test_everything():
    await test_create()
    await test_read()
    await test_update()
    await test_delete()

# ✅ 좋은 예
async def test_create():
    # 생성 테스트만

async def test_read():
    # 조회 테스트만
```

## 🎯 다음 단계

### TODO: 추가 테스트 필요

- [ ] Pydantic 스키마 검증 테스트
- [ ] WebSocket 연결 테스트
- [ ] Prometheus 메트릭 수집 테스트
- [ ] Alembic 마이그레이션 테스트
- [ ] 성능 테스트 (Locust)
- [ ] 보안 테스트 (SQL Injection, XSS)

### TODO: 실제 서비스 통합

- [ ] Upbit API 실제 연동 테스트
- [ ] OpenAI API 실제 호출 테스트
- [ ] Telegram 실제 전송 테스트

---

**마지막 업데이트**: 2025-12-28
**총 테스트 수**: 61개
**목표 커버리지**: 70% 이상



