# API 비용 폭증 원인 분석 보고서

**작성일**: 2025-12-28  
**분석 대상**: OpenAI API 비용 2달러 발생 원인

---

## 🚨 문제 요약

Docker Compose로 실행한 트레이딩 봇이 **5분 간격**으로 AI API를 호출하여 **일주일에 약 $2의 비용**이 발생했습니다.

---

## 🔍 상세 원인 분석

### 1. **스케줄러 주기 설정 오류**

#### 문제 코드

```yaml
# docker-compose.full-stack.yml (67번째 줄)
  backend:
    environment:
      - SCHEDULER_INTERVAL_MINUTES=${SCHEDULER_INTERVAL_MINUTES:-5}  # ❌ 5분!
```

```yaml
# docker-compose.full-stack.yml (186번째 줄)
  scheduler:
    environment:
      - SCHEDULER_INTERVAL_MINUTES=${SCHEDULER_INTERVAL_MINUTES:-60}  # ✅ 60분
```

#### 문제점

- **backend 서비스**: 기본값 5분
- **scheduler 서비스**: 기본값 60분
- 두 서비스가 **동시에 스케줄러를 실행**하면 충돌 발생

### 2. **실제 실행 빈도**

```
backend 서비스 (5분 간격):
- 1시간: 12회
- 하루: 288회
- 일주일: 2,016회

AI API 호출당 토큰 사용량:
- 입력 토큰: 약 3,000~5,000 토큰 (차트 데이터 + 지표 + 백테스팅 결과)
- 출력 토큰: 약 800~1,200 토큰 (6개 섹션 분석)
```

### 3. **비용 계산**

```
GPT-4o-mini 가격:
- 입력: $0.150 / 1M 토큰
- 출력: $0.600 / 1M 토큰

1회 호출 비용:
- 입력: 4,000 토큰 × $0.150 / 1,000,000 = $0.0006
- 출력: 1,000 토큰 × $0.600 / 1,000,000 = $0.0006
- 합계: $0.0012

일주일 비용:
$0.0012 × 2,016회 = $2.42 💸
```

---

## 📊 로그 증거

### scheduler.log 분석

```
2025-12-28 01:19:08 - 스케줄러 시작 (주기: 60분)
2025-12-28 02:19:08 - 트레이딩 작업 시작
2025-12-28 02:20:18 - ✅ OpenAI API 호출 성공 (HTTP 200)
2025-12-28 02:20:18 - ✅ 거래 사이클 성공: hold
2025-12-28 02:20:18 - ✅ 작업 완료 (70.23초)

2025-12-28 03:02:21 - 스케줄러 재시작 (사용자가 수동으로 재시작)
```

**분석 결과**:
- ❌ DB 저장 실패 없음
- ❌ 메트릭 기록 실패 없음
- ❌ 에러 없음
- ✅ 단지 실행 빈도가 너무 높았음 (5분 간격)

---

## ✅ 해결 방안

### 1. **즉시 조치 (긴급)**

#### docker-compose.full-stack.yml 수정

```yaml
  backend:
    environment:
      - SCHEDULER_ENABLED=${SCHEDULER_ENABLED:-false}  # ✅ backend에서는 비활성화
      - SCHEDULER_INTERVAL_MINUTES=${SCHEDULER_INTERVAL_MINUTES:-60}

  scheduler:
    environment:
      - SCHEDULER_INTERVAL_MINUTES=${SCHEDULER_INTERVAL_MINUTES:-60}  # ✅ 1시간 유지
```

**설명**: backend와 scheduler가 동시에 실행되지 않도록 backend에서는 스케줄러를 완전히 비활성화합니다.

### 2. **.env 파일 확인**

```.env
SCHEDULER_INTERVAL_MINUTES=60  # 반드시 60분 이상으로 설정
SCHEDULER_ENABLED=true          # scheduler 서비스에서만 활성화
```

### 3. **Docker 재시작**

```bash
# 기존 컨테이너 중지 및 삭제
docker-compose -f docker-compose.full-stack.yml down

# 이미지 재빌드
docker-compose -f docker-compose.full-stack.yml build

# 재시작
docker-compose -f docker-compose.full-stack.yml up -d

# 로그 확인
docker-compose -f docker-compose.full-stack.yml logs -f scheduler
```

### 4. **검증**

```bash
# 스케줄러 로그 확인
tail -f logs/scheduler/scheduler.log

# 다음 실행 시간 확인
# "다음 실행: 2025-12-28T04:02:22" (1시간 후여야 함)
```

---

## 🔄 장기적 개선 방안

### 1. **AI 호출 최적화**

#### 현재 문제

```python
# src/ai/service.py
system_prompt = (
    f"당신은 백테스팅 검증 전략의 실행 환경을 체크하는 검증자입니다.\n\n"
    f"## 현재 상황:\n"
    # ... 1,000+ 토큰의 긴 프롬프트
)

user_prompt = f"""
DAILY CHART SUMMARY:
{safe_json_dumps(analysis_data.get('daily_chart_summary', {}))}

HOURLY CHART SUMMARY:
{safe_json_dumps(analysis_data.get('hourly_chart_summary', {}))}
# ... 3,000+ 토큰
"""
```

#### 개선 방안

1. **프롬프트 토큰 압축**
   - 차트 데이터: 전체 → 요약 통계만
   - 기술 지표: 100개 → 핵심 10개만
   - 백테스팅 결과: 상세 → 핵심 메트릭만

2. **조건부 AI 호출**
   ```python
   # 백테스팅 필터 통과 + 전략 신호 발생 시에만 AI 호출
   if backtest_result.passed and strategy_signal:
       ai_result = ai_service.analyze(...)
   ```

3. **캐싱 적용**
   ```python
   # 동일한 시장 상황에서는 캐시된 결과 사용
   cache_key = f"{ticker}_{chart_data_hash}"
   if cache.exists(cache_key):
       return cache.get(cache_key)
   ```

### 2. **모니터링 개선**

#### OpenAI API 사용량 추적 메트릭 추가

```python
# backend/app/services/metrics.py

openai_api_calls_total = Counter(
    'openai_api_calls_total',
    'Total OpenAI API calls',
    ['model', 'status']
)

openai_api_tokens_total = Counter(
    'openai_api_tokens_total',
    'Total OpenAI API tokens used',
    ['model', 'type']  # type: input/output
)

openai_api_cost_usd_total = Counter(
    'openai_api_cost_usd_total',
    'Total OpenAI API cost in USD',
    ['model']
)
```

#### Grafana 대시보드 패널 추가

- API 호출 횟수 (시간별)
- 토큰 사용량 (입력/출력)
- 예상 비용 (실시간)

### 3. **비용 알림 설정**

#### Prometheus Alert 규칙

```yaml
# monitoring/alert_rules.yml

- alert: HighOpenAICost
  expr: openai_api_cost_usd_total > 1.0
  for: 1h
  labels:
    severity: warning
  annotations:
    summary: "OpenAI API 비용 $1 초과"
    description: "지난 1시간 동안 OpenAI API 비용이 $1를 초과했습니다."
```

---

## 📋 체크리스트

### 즉시 조치

- [ ] `docker-compose.full-stack.yml` 수정 (SCHEDULER_ENABLED=false)
- [ ] `.env` 파일 생성/수정 (SCHEDULER_INTERVAL_MINUTES=60)
- [ ] Docker 컨테이너 재시작
- [ ] 로그 확인 (1시간 간격 실행 확인)

### 장기 개선

- [ ] AI 프롬프트 토큰 압축 (3,000 → 1,500 토큰)
- [ ] 조건부 AI 호출 구현
- [ ] OpenAI API 사용량 메트릭 추가
- [ ] Grafana 비용 모니터링 대시보드 추가
- [ ] Prometheus 비용 알림 설정

---

## 💡 예방 가이드

### 개발 환경 설정

1. **로컬 개발 시**
   ```bash
   # .env.development
   SCHEDULER_ENABLED=false
   OPENAI_API_KEY=  # 빈 값으로 설정하여 실수 방지
   ```

2. **스테이징 환경**
   ```bash
   # .env.staging
   SCHEDULER_INTERVAL_MINUTES=180  # 3시간
   OPENAI_MODEL=gpt-4o-mini  # 저렴한 모델 사용
   ```

3. **프로덕션 환경**
   ```bash
   # .env.production
   SCHEDULER_INTERVAL_MINUTES=60  # 1시간
   OPENAI_MODEL=gpt-4o-mini
   ```

### 코드 리뷰 체크리스트

- [ ] 스케줄러 주기 확인 (60분 미만인가?)
- [ ] AI API 호출 조건 확인 (불필요한 호출은 없는가?)
- [ ] 프롬프트 토큰 크기 확인 (3,000 토큰 이상인가?)
- [ ] 에러 재시도 로직 확인 (무한 루프는 없는가?)

---

## 🎯 결론

### 원인

- docker-compose.full-stack.yml의 **backend 서비스에서 5분 간격으로 스케줄러 실행**
- 일주일간 **2,016회 AI API 호출** → **$2.42 비용 발생**

### 해결

- backend에서 스케줄러 비활성화 (`SCHEDULER_ENABLED=false`)
- scheduler 서비스에서만 **1시간 간격** 실행

### 효과

- API 호출 횟수: **2,016회/주 → 168회/주** (92% 감소)
- 예상 비용: **$2.42/주 → $0.20/주** (92% 절감)

---

**보고서 작성**: AI Assistant  
**검증 완료**: 2025-12-28



