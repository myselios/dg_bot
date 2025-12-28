# RSI 다이버전스 "none" 문제 해결 리포트

## 📋 문제 상황

**증상**: RSI 다이버전스 분석이 항상 "none"으로 나옴
```
다이버전스 타입: none
신뢰도: low
설명: 다이버전스 없음
```

## 🔍 원인 분석

### 1. **prominence 파라미터가 너무 큼**

#### 기존 코드 (문제점)
```python
# scipy 사용
price_peaks, _ = find_peaks(recent_high, prominence=2)
rsi_peaks, _ = find_peaks(recent_rsi, prominence=2)

# 자체 구현
left_higher = data[i] >= data[i-1] + prominence  # prominence=2
right_higher = data[i] >= data[i+1] + prominence
```

**문제점**:
- `prominence=2`는 양옆보다 2 이상 높아야만 고점으로 인정
- 실제 ETH 가격은 400만원대로 큰 숫자이지만, 일일 변동폭은 작을 수 있음
- RSI는 0-100 범위이므로 prominence=2는 적절하지만, 가격에는 너무 작음

**예시**:
```
가격: [4,290,000, 4,291,000, 4,289,000]
      → prominence=2 조건: 4,291,000 >= 4,290,000 + 2 (OK)
      → 하지만 실제 차이는 1,000원 (0.02%)로 미미함
```

### 2. **최소 2개의 고점/저점 필요**

```python
if len(price_peaks) >= 2 and len(rsi_peaks) >= 2:
    # 다이버전스 체크
```

- 고점이 1개만 발견되면 다이버전스 감지 불가
- 최근 20일 내에 명확한 고점/저점이 없으면 "none"

### 3. **lookback=20일로 제한**

- 최근 20일 데이터만 분석
- 더 긴 기간의 다이버전스는 감지 못함

## ✅ 해결 방법

### 수정 1: **가격의 prominence 완화**

```python
# scipy 사용
price_peaks, _ = find_peaks(recent_high, prominence=0.5)  # 2 → 0.5
rsi_peaks, _ = find_peaks(recent_rsi, prominence=2)       # 유지
price_troughs, _ = find_peaks(-recent_low, prominence=0.5) # 2 → 0.5
rsi_troughs, _ = find_peaks(-recent_rsi, prominence=2)     # 유지
```

**이유**:
- 가격 변동은 작아도 의미 있을 수 있음
- RSI는 0-100 범위로 prominence=2가 적절
- 더 많은 고점/저점 감지 가능

### 수정 2: **_find_peaks_simple 조건 완화**

#### 기존 코드
```python
left_higher = data[i] >= data[i-1] + prominence  # prominence=2
right_higher = data[i] >= data[i+1] + prominence
```

#### 수정 코드
```python
left_higher = data[i] >= data[i-1]  # prominence 조건 제거
right_higher = data[i] >= data[i+1]
```

**이유**:
- scipy 없는 환경에서도 다이버전스 감지 가능
- 단순 비교로 더 민감하게 고점/저점 감지

### 수정 3: **디버깅 로그 추가**

```python
logger.info(f"🔍 다이버전스 분석: price_peaks={len(price_peaks)}, rsi_peaks={len(rsi_peaks)}, price_troughs={len(price_troughs)}, rsi_troughs={len(rsi_troughs)}")
```

**효과**:
- 실제로 몇 개의 고점/저점이 감지되는지 확인 가능
- 추가 튜닝을 위한 데이터 수집

## 📊 예상 효과

### Before (수정 전)
```
다이버전스 타입: none
신뢰도: low
설명: 다이버전스 없음
```
- 고점/저점이 거의 감지되지 않음
- 실제 다이버전스가 있어도 놓침

### After (수정 후)
```
🔍 다이버전스 분석: price_peaks=3, rsi_peaks=2, price_troughs=4, rsi_troughs=3
다이버전스 타입: bearish_divergence
신뢰도: high
설명: 가격 고점 4,285,000→4,291,000, RSI 고점 68.5→64.2
```
- 더 많은 고점/저점 감지
- 실제 다이버전스 패턴 포착 가능

## 🔄 추가 개선 사항 (향후)

### 1. **동적 prominence 계산**
```python
# 가격 변동성 기반 prominence 자동 조정
price_volatility = df['close'].pct_change().std()
price_prominence = max(0.1, price_volatility * 10)
```

### 2. **lookback 기간 조정**
```python
# 변동성에 따라 lookback 기간 조정
if volatility > 0.05:  # 변동성 높음
    lookback = 30  # 더 긴 기간
else:
    lookback = 20  # 기본값
```

### 3. **신뢰도 계산 개선**
```python
# 다이버전스 강도에 따라 신뢰도 세분화
divergence_strength = abs(price_change - rsi_change)
if divergence_strength > 20:
    confidence = 'very_high'
elif divergence_strength > 10:
    confidence = 'high'
# ...
```

## 🚀 적용 방법

### 1. 빌드 및 재시작
```batch
restart-full-stack.bat
```

### 2. 로그 확인
```batch
docker-compose -f docker-compose.full-stack.yml logs -f trading_bot_scheduler
```

다음 로그 확인:
- "🔍 다이버전스 분석: price_peaks=X, rsi_peaks=Y..."
- "다이버전스 타입: bearish_divergence" 또는 "bullish_divergence"

### 3. 효과 검증
- 3-5회 실행 후 다이버전스 감지 여부 확인
- PostgreSQL에서 AI 결정 데이터 확인:
```sql
SELECT decision, confidence, reason, created_at 
FROM ai_decisions 
WHERE reason LIKE '%다이버전스%'
ORDER BY created_at DESC 
LIMIT 10;
```

## 📝 변경 파일

- `src/trading/indicators.py`
  - `detect_rsi_divergence()` 메서드: prominence 조정
  - `_find_peaks_simple()` 메서드: 조건 완화
  - 디버깅 로그 추가

## ⚠️ 주의사항

1. **false positive 증가 가능**
   - prominence를 낮추면 노이즈도 증가
   - 신뢰도(confidence)를 함께 확인해야 함

2. **백테스팅 결과 확인 필요**
   - 수정 후 백테스팅으로 효과 검증 권장
   - 과도한 다이버전스 감지는 거래 빈도 증가 → 수수료 증가

3. **시장 상황에 따른 조정**
   - 변동성 큰 시장: prominence 높이기
   - 변동성 작은 시장: prominence 낮추기 (현재 설정)

## 🎯 결론

**근본 원인**: prominence=2가 실제 시장 변동에 비해 너무 커서 고점/저점을 감지하지 못함

**해결책**: 
- 가격 prominence를 0.5로 완화
- _find_peaks_simple 조건 완화
- 디버깅 로그 추가

**기대 효과**:
- 실제 다이버전스 패턴 감지 가능
- AI 거래 판단의 정확도 향상
- 시장 모멘텀 변화 조기 포착

---

**작성일**: 2025-12-28  
**작성자**: AI Trading Bot Development Team



