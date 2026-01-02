"""
유동성 기반 코인 스캐너 (Liquidity Scanner)

업비트 KRW 마켓에서 유동성 상위 코인을 스캔합니다.

주요 기능:
- 24시간 거래대금 기준 상위 코인 추출
- 최소 유동성 필터링 (기본: 100억원/일)
- 7일 변동성 계산
- 스테이블코인/레버리지 토큰 제외
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pyupbit

from src.utils.logger import Logger


@dataclass
class CoinInfo:
    """코인 정보 데이터클래스"""
    ticker: str                          # 예: KRW-BTC
    symbol: str                          # 예: BTC
    korean_name: str                     # 예: 비트코인
    current_price: float                 # 현재가
    volume_24h: float                    # 24시간 거래량 (코인 수량)
    acc_trade_price_24h: float           # 24시간 거래대금 (KRW)
    signed_change_rate: float            # 24시간 변동률
    high_price: float                    # 고가
    low_price: float                     # 저가
    volatility_7d: Optional[float] = None  # 7일 변동성 (ATR 기준)
    avg_volume_7d: Optional[float] = None  # 7일 평균 거래대금
    scan_time: datetime = field(default_factory=datetime.now)

    @property
    def volatility_24h(self) -> float:
        """24시간 변동성 (고가-저가 범위)"""
        if self.current_price > 0:
            return (self.high_price - self.low_price) / self.current_price * 100
        return 0.0


class LiquidityScanner:
    """
    유동성 기반 코인 스캐너

    업비트 KRW 마켓에서 거래대금 상위 코인을 스캔합니다.

    사용 예시:
        scanner = LiquidityScanner()
        top_coins = await scanner.scan_top_coins(min_volume_krw=10_000_000_000, top_n=20)
        for coin in top_coins:
            print(f"{coin.symbol}: {coin.acc_trade_price_24h:,.0f} KRW")
    """

    # 제외할 코인 목록
    EXCLUDED_SYMBOLS = {
        'USDT', 'USDC', 'DAI', 'BUSD',  # 스테이블코인
        'TUSD', 'PAXG', 'UST',          # 스테이블코인
    }

    # 제외할 패턴 (레버리지, 숏 등)
    EXCLUDED_PATTERNS = ['2L', '2S', '3L', '3S', 'UP', 'DOWN']

    def __init__(
        self,
        min_volume_krw: float = 10_000_000_000,  # 100억원
        rate_limit_delay: float = 0.1  # API 호출 간격 (초)
    ):
        """
        Args:
            min_volume_krw: 최소 24시간 거래대금 (KRW)
            rate_limit_delay: API 호출 간 지연 시간 (초)
        """
        self.min_volume_krw = min_volume_krw
        self.rate_limit_delay = rate_limit_delay
        self._coin_names: Dict[str, str] = {}  # ticker -> korean_name 캐시

    async def scan_top_coins(
        self,
        min_volume_krw: Optional[float] = None,
        top_n: int = 20,
        include_volatility: bool = True
    ) -> List[CoinInfo]:
        """
        유동성 상위 코인 스캔

        Args:
            min_volume_krw: 최소 24시간 거래대금 (None이면 초기 설정값 사용)
            top_n: 반환할 최대 코인 수
            include_volatility: 7일 변동성 계산 여부 (API 호출 증가)

        Returns:
            CoinInfo 리스트 (거래대금 순 정렬)
        """
        min_vol = min_volume_krw or self.min_volume_krw
        Logger.print_info(f"🔍 유동성 스캔 시작 (최소 거래대금: {min_vol/1e8:.0f}억원)")

        try:
            # 1. 전체 KRW 마켓 조회
            all_tickers = await self._get_all_krw_tickers()
            Logger.print_info(f"  전체 KRW 마켓: {len(all_tickers)}개")

            # 2. 시세 데이터 조회
            ticker_data = await self._get_ticker_data(all_tickers)

            # 3. 필터링 및 정렬
            filtered_coins = []
            for data in ticker_data:
                coin_info = self._parse_ticker_data(data)
                if coin_info and self._passes_filter(coin_info, min_vol):
                    filtered_coins.append(coin_info)

            # 거래대금 순 정렬
            filtered_coins.sort(key=lambda x: x.acc_trade_price_24h, reverse=True)

            # 상위 N개 추출
            top_coins = filtered_coins[:top_n]
            Logger.print_info(f"  필터 통과: {len(filtered_coins)}개 → 상위 {len(top_coins)}개 선정")

            # 4. 7일 변동성 계산 (옵션)
            if include_volatility and top_coins:
                top_coins = await self._add_volatility_data(top_coins)

            return top_coins

        except Exception as e:
            Logger.print_error(f"유동성 스캔 실패: {str(e)}")
            return []

    async def get_coin_details(self, ticker: str) -> Optional[CoinInfo]:
        """
        특정 코인 상세 정보 조회

        Args:
            ticker: 코인 티커 (예: KRW-BTC)

        Returns:
            CoinInfo 또는 None
        """
        try:
            ticker_data = await self._get_ticker_data([ticker])
            if ticker_data:
                return self._parse_ticker_data(ticker_data[0])
            return None
        except Exception as e:
            Logger.print_error(f"코인 정보 조회 실패 ({ticker}): {str(e)}")
            return None

    async def _get_all_krw_tickers(self) -> List[str]:
        """전체 KRW 마켓 티커 목록 조회"""
        loop = asyncio.get_event_loop()
        tickers = await loop.run_in_executor(None, pyupbit.get_tickers, "KRW")
        return tickers or []

    async def _get_ticker_data(self, tickers: List[str]) -> List[Dict[str, Any]]:
        """티커 시세 데이터 조회"""
        if not tickers:
            return []

        loop = asyncio.get_event_loop()

        # pyupbit.get_current_price에서 상세 정보 가져오기
        # 여러 티커 한번에 조회 가능
        try:
            import requests
            url = "https://api.upbit.com/v1/ticker"
            params = {"markets": ",".join(tickers)}
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(url, params=params)
            )

            if response.status_code == 200:
                return response.json()
            else:
                Logger.print_warning(f"API 응답 오류: {response.status_code}")
                return []

        except Exception as e:
            Logger.print_error(f"시세 데이터 조회 실패: {str(e)}")
            return []

    def _parse_ticker_data(self, data: Dict[str, Any]) -> Optional[CoinInfo]:
        """API 응답 데이터를 CoinInfo로 변환"""
        try:
            ticker = data.get('market', '')
            if not ticker.startswith('KRW-'):
                return None

            symbol = ticker.replace('KRW-', '')

            return CoinInfo(
                ticker=ticker,
                symbol=symbol,
                korean_name=self._coin_names.get(ticker, symbol),
                current_price=float(data.get('trade_price', 0)),
                volume_24h=float(data.get('acc_trade_volume_24h', 0)),
                acc_trade_price_24h=float(data.get('acc_trade_price_24h', 0)),
                signed_change_rate=float(data.get('signed_change_rate', 0)) * 100,
                high_price=float(data.get('high_price', 0)),
                low_price=float(data.get('low_price', 0))
            )
        except Exception as e:
            Logger.print_warning(f"데이터 파싱 실패: {str(e)}")
            return None

    def _passes_filter(self, coin: CoinInfo, min_volume: float) -> bool:
        """필터 조건 통과 여부 확인"""
        # 거래대금 조건
        if coin.acc_trade_price_24h < min_volume:
            return False

        # 제외 코인 목록
        if coin.symbol in self.EXCLUDED_SYMBOLS:
            return False

        # 제외 패턴 (레버리지 토큰 등)
        for pattern in self.EXCLUDED_PATTERNS:
            if pattern in coin.symbol:
                return False

        return True

    async def _add_volatility_data(self, coins: List[CoinInfo]) -> List[CoinInfo]:
        """7일 변동성 데이터 추가"""
        Logger.print_info("  7일 변동성 계산 중...")

        loop = asyncio.get_event_loop()

        for coin in coins:
            try:
                # 7일간 일봉 데이터
                df = await loop.run_in_executor(
                    None,
                    lambda t=coin.ticker: pyupbit.get_ohlcv(t, interval="day", count=8)
                )

                if df is not None and len(df) >= 7:
                    # ATR 기반 변동성 계산
                    high = df['high'].values
                    low = df['low'].values
                    close = df['close'].values

                    # True Range 계산
                    tr_list = []
                    for i in range(1, len(df)):
                        tr = max(
                            high[i] - low[i],
                            abs(high[i] - close[i-1]),
                            abs(low[i] - close[i-1])
                        )
                        tr_list.append(tr)

                    # ATR (7일 평균 TR)
                    if tr_list:
                        atr = sum(tr_list) / len(tr_list)
                        coin.volatility_7d = (atr / close[-1]) * 100

                    # 7일 평균 거래대금
                    if 'value' in df.columns:
                        coin.avg_volume_7d = df['value'].mean()

                # Rate limit 방지
                await asyncio.sleep(self.rate_limit_delay)

            except Exception as e:
                Logger.print_warning(f"  변동성 계산 실패 ({coin.symbol}): {str(e)}")

        return coins

    async def load_coin_names(self) -> None:
        """코인 한글명 캐시 로드"""
        try:
            loop = asyncio.get_event_loop()

            import requests
            url = "https://api.upbit.com/v1/market/all"
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(url, params={"isDetails": "false"})
            )

            if response.status_code == 200:
                for item in response.json():
                    market = item.get('market', '')
                    if market.startswith('KRW-'):
                        self._coin_names[market] = item.get('korean_name', '')

        except Exception as e:
            Logger.print_warning(f"코인명 로드 실패: {str(e)}")

    def print_scan_result(self, coins: List[CoinInfo]) -> None:
        """스캔 결과 출력"""
        Logger.print_header("📊 유동성 스캔 결과")
        print(f"{'순위':>4} {'심볼':>8} {'현재가':>15} {'거래대금(억)':>12} {'변동률':>8} {'변동성':>8}")
        print("-" * 65)

        for i, coin in enumerate(coins, 1):
            vol_str = f"{coin.acc_trade_price_24h/1e8:.0f}"
            change_str = f"{coin.signed_change_rate:+.2f}%"
            volatility_str = f"{coin.volatility_7d:.2f}%" if coin.volatility_7d else "-"

            print(f"{i:>4} {coin.symbol:>8} {coin.current_price:>15,.0f} {vol_str:>12} {change_str:>8} {volatility_str:>8}")
