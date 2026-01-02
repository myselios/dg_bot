"""
멀티코인 스캐닝 모듈

업비트 KRW 마켓에서 유동성 상위 코인을 스캔하고,
백테스팅 및 AI 분석을 통해 진입 후보를 선별합니다.

구성요소:
- LiquidityScanner: 유동성 기반 코인 스캔
- HistoricalDataSync: 과거 데이터 동기화
- MultiCoinBacktest: 병렬 백테스팅
- CoinSelector: 최종 코인 선택

사용 예시:
    from src.scanner import CoinSelector

    selector = CoinSelector()
    result = await selector.select_coins()

    for coin in result.selected_coins:
        print(f"{coin.symbol}: {coin.final_score:.1f}점")
"""
from src.scanner.liquidity_scanner import (
    LiquidityScanner,
    CoinInfo
)
from src.scanner.data_sync import (
    HistoricalDataSync,
    SyncStatus
)
from src.scanner.multi_backtest import (
    MultiCoinBacktest,
    MultiBacktestConfig,
    BacktestScore
)
from src.scanner.coin_selector import (
    CoinSelector,
    CoinCandidate,
    ScanResult
)

__all__ = [
    # 유동성 스캐너
    'LiquidityScanner',
    'CoinInfo',
    # 데이터 동기화
    'HistoricalDataSync',
    'SyncStatus',
    # 백테스팅
    'MultiCoinBacktest',
    'MultiBacktestConfig',
    'BacktestScore',
    # 코인 선택기
    'CoinSelector',
    'CoinCandidate',
    'ScanResult',
]
