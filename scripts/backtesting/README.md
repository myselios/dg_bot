# 백테스팅 데이터 수집 스크립트

백테스팅을 위한 과거 데이터를 수집하고 관리하는 스크립트입니다.

## 📁 디렉토리 구조

```
backtest_data/              # 백테스팅 데이터 저장소
├── daily/                  # 일봉 데이터
│   ├── KRW-ETH_2024-01-01_2024-12-31.csv
│   └── ...
├── hourly/                 # 시간봉 데이터
│   ├── KRW-ETH_2024-01-01_2024-12-31.csv
│   └── ...
└── minute/                 # 분봉 데이터
    ├── KRW-ETH_15min_2024-01-01_2024-12-31.csv
    └── ...
```

## 🚀 사용법

### 1. 2024년 이더리움 데이터 수집

```bash
python scripts/backtesting/collect_eth_2024.py
```

이 스크립트는:

- 2024년 1월 1일 ~ 12월 31일 기간의 이더리움 데이터를 수집합니다
- 일봉, 시간봉, 15분봉 데이터를 모두 수집합니다
- 데이터 품질 검증 및 정제를 수행합니다
- `backtest_data/` 디렉토리에 저장합니다

### 2. 다른 종목/기간 데이터 수집

```python
from datetime import datetime
from scripts.backtesting.data_manager import BacktestDataManager

manager = BacktestDataManager(data_dir='backtest_data')

# 비트코인 2023년 데이터 수집
data = manager.collect_and_cache(
    ticker='KRW-BTC',
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2023, 12, 31)
)
```

### 3. 여러 종목 일괄 수집

```python
from datetime import datetime
from scripts.backtesting.data_manager import BacktestDataManager

manager = BacktestDataManager()

major_coins = [
    'KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-SOL',
    'KRW-ADA', 'KRW-DOGE', 'KRW-AVAX', 'KRW-DOT'
]

manager.collect_multiple_tickers(
    tickers=major_coins,
    start_date=datetime(2024, 1, 1)
)
```

## 📊 데이터 품질 검증

```python
from scripts.backtesting.data_quality import DataQualityChecker
import pandas as pd

# 데이터 로드
df = pd.read_csv('backtest_data/daily/KRW-ETH_2024-01-01_2024-12-31.csv',
                 index_col=0, parse_dates=True)

# 품질 검사
checker = DataQualityChecker()
quality_report = checker.check_data_quality(df)
checker.print_quality_report(quality_report)

# 데이터 정제
cleaned_df = checker.clean_data(df)
```

## 🔧 모듈 설명

### `data_collector.py`

- `UpbitDataCollector`: Upbit API를 사용한 과거 데이터 수집
- 페이지네이션을 통한 대량 데이터 수집 지원
- API 레이트 리밋 자동 관리

### `data_manager.py`

- `BacktestDataManager`: 데이터 수집 및 캐싱 관리
- 타임프레임별 디렉토리 자동 생성
- 캐시된 데이터 우선 사용

### `data_quality.py`

- `DataQualityChecker`: 데이터 품질 검증 및 정제
- 결측치, 이상치, 중복 데이터 처리
- OHLC 관계 검증

## ⚠️ 주의사항

1. **API 레이트 리밋**: Upbit API는 초당 요청 수에 제한이 있습니다. 스크립트는 자동으로 딜레이를 추가합니다.

2. **데이터 기간 제한**:

   - 일봉: 제한 없음
   - 시간봉: 최대 30일 권장
   - 15분봉: 최대 7일 권장

3. **캐시 사용**: 이미 수집된 데이터는 자동으로 캐시됩니다. 강제 업데이트가 필요하면 `force_update=True`를 사용하세요.

## 📝 예시

### 전체 워크플로우

```python
from datetime import datetime
from scripts.backtesting.data_manager import BacktestDataManager
from scripts.backtesting.data_quality import DataQualityChecker

# 1. 데이터 수집
manager = BacktestDataManager()
data = manager.collect_and_cache(
    ticker='KRW-ETH',
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 12, 31)
)

# 2. 품질 검증
checker = DataQualityChecker()
for interval, df in data.items():
    if not df.empty:
        report = checker.check_data_quality(df)
        cleaned_df = checker.clean_data(df)
        print(f"{interval}: {len(cleaned_df)} rows")
```

## 🔗 관련 파일

- `backtest.py`: 백테스팅 실행 스크립트
- `src/backtesting/data_provider.py`: 백테스팅용 데이터 로더 (캐시 우선 사용)
