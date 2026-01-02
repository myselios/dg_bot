"""
LiquidityScanner 단위 테스트
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

from src.scanner.liquidity_scanner import LiquidityScanner, CoinInfo


class TestCoinInfo:
    """CoinInfo 데이터클래스 테스트"""

    def test_coin_info_creation(self):
        """CoinInfo 객체 생성 테스트"""
        coin = CoinInfo(
            ticker="KRW-BTC",
            symbol="BTC",
            korean_name="비트코인",
            current_price=50000000,
            volume_24h=1000,
            acc_trade_price_24h=50000000000,
            signed_change_rate=2.5,
            high_price=51000000,
            low_price=49000000
        )

        assert coin.ticker == "KRW-BTC"
        assert coin.symbol == "BTC"
        assert coin.current_price == 50000000
        assert coin.acc_trade_price_24h == 50000000000

    def test_volatility_24h_calculation(self):
        """24시간 변동성 계산 테스트"""
        coin = CoinInfo(
            ticker="KRW-ETH",
            symbol="ETH",
            korean_name="이더리움",
            current_price=4000000,
            volume_24h=500,
            acc_trade_price_24h=20000000000,
            signed_change_rate=1.5,
            high_price=4100000,
            low_price=3900000
        )

        # (4100000 - 3900000) / 4000000 * 100 = 5.0%
        assert coin.volatility_24h == 5.0

    def test_volatility_24h_zero_price(self):
        """가격이 0일 때 변동성 계산"""
        coin = CoinInfo(
            ticker="KRW-XRP",
            symbol="XRP",
            korean_name="리플",
            current_price=0,
            volume_24h=0,
            acc_trade_price_24h=0,
            signed_change_rate=0,
            high_price=100,
            low_price=90
        )

        assert coin.volatility_24h == 0.0


class TestLiquidityScanner:
    """LiquidityScanner 클래스 테스트"""

    def test_scanner_initialization(self):
        """스캐너 초기화 테스트"""
        scanner = LiquidityScanner(
            min_volume_krw=5_000_000_000,
            rate_limit_delay=0.2
        )

        assert scanner.min_volume_krw == 5_000_000_000
        assert scanner.rate_limit_delay == 0.2

    def test_excluded_symbols(self):
        """제외 코인 목록 확인"""
        scanner = LiquidityScanner()

        assert 'USDT' in scanner.EXCLUDED_SYMBOLS
        assert 'USDC' in scanner.EXCLUDED_SYMBOLS
        assert 'DAI' in scanner.EXCLUDED_SYMBOLS

    def test_excluded_patterns(self):
        """제외 패턴 목록 확인"""
        scanner = LiquidityScanner()

        assert '2L' in scanner.EXCLUDED_PATTERNS
        assert '3S' in scanner.EXCLUDED_PATTERNS
        assert 'UP' in scanner.EXCLUDED_PATTERNS
        assert 'DOWN' in scanner.EXCLUDED_PATTERNS

    def test_passes_filter_valid_coin(self):
        """유효한 코인 필터 통과 테스트"""
        scanner = LiquidityScanner(min_volume_krw=10_000_000_000)

        coin = CoinInfo(
            ticker="KRW-BTC",
            symbol="BTC",
            korean_name="비트코인",
            current_price=50000000,
            volume_24h=1000,
            acc_trade_price_24h=50_000_000_000,  # 500억
            signed_change_rate=2.5,
            high_price=51000000,
            low_price=49000000
        )

        assert scanner._passes_filter(coin, 10_000_000_000) is True

    def test_passes_filter_low_volume(self):
        """거래대금 부족 코인 필터링 테스트"""
        scanner = LiquidityScanner(min_volume_krw=10_000_000_000)

        coin = CoinInfo(
            ticker="KRW-ABC",
            symbol="ABC",
            korean_name="에이비씨",
            current_price=1000,
            volume_24h=100,
            acc_trade_price_24h=5_000_000_000,  # 50억 (100억 미만)
            signed_change_rate=0.5,
            high_price=1050,
            low_price=950
        )

        assert scanner._passes_filter(coin, 10_000_000_000) is False

    def test_passes_filter_stablecoin(self):
        """스테이블코인 필터링 테스트"""
        scanner = LiquidityScanner()

        coin = CoinInfo(
            ticker="KRW-USDT",
            symbol="USDT",
            korean_name="테더",
            current_price=1300,
            volume_24h=10000000,
            acc_trade_price_24h=100_000_000_000,  # 1000억
            signed_change_rate=0.01,
            high_price=1301,
            low_price=1299
        )

        assert scanner._passes_filter(coin, 10_000_000_000) is False

    def test_passes_filter_leverage_token(self):
        """레버리지 토큰 필터링 테스트"""
        scanner = LiquidityScanner()

        coin = CoinInfo(
            ticker="KRW-BTC2L",
            symbol="BTC2L",
            korean_name="비트코인2배롱",
            current_price=10000,
            volume_24h=1000,
            acc_trade_price_24h=50_000_000_000,
            signed_change_rate=5.0,
            high_price=10500,
            low_price=9500
        )

        assert scanner._passes_filter(coin, 10_000_000_000) is False

    def test_parse_ticker_data_valid(self):
        """유효한 API 응답 파싱 테스트"""
        scanner = LiquidityScanner()

        data = {
            'market': 'KRW-ETH',
            'trade_price': 4000000,
            'acc_trade_volume_24h': 5000,
            'acc_trade_price_24h': 20000000000,
            'signed_change_rate': 0.025,
            'high_price': 4100000,
            'low_price': 3900000
        }

        coin = scanner._parse_ticker_data(data)

        assert coin is not None
        assert coin.ticker == "KRW-ETH"
        assert coin.symbol == "ETH"
        assert coin.current_price == 4000000
        assert coin.signed_change_rate == 2.5  # 0.025 * 100

    def test_parse_ticker_data_non_krw(self):
        """KRW 마켓이 아닌 경우"""
        scanner = LiquidityScanner()

        data = {
            'market': 'BTC-ETH',
            'trade_price': 0.05,
            'acc_trade_volume_24h': 100,
            'acc_trade_price_24h': 5,
            'signed_change_rate': 0.01,
            'high_price': 0.051,
            'low_price': 0.049
        }

        coin = scanner._parse_ticker_data(data)
        assert coin is None

    def test_parse_ticker_data_empty(self):
        """빈 데이터 처리"""
        scanner = LiquidityScanner()

        coin = scanner._parse_ticker_data({})
        assert coin is None


class TestLiquidityScannerAsync:
    """LiquidityScanner 비동기 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_scan_top_coins_empty_tickers(self):
        """빈 티커 목록 처리"""
        scanner = LiquidityScanner()

        with patch.object(scanner, '_get_all_krw_tickers', new_callable=AsyncMock) as mock_tickers:
            mock_tickers.return_value = []

            result = await scanner.scan_top_coins(top_n=10)

            assert result == []

    @pytest.mark.asyncio
    async def test_scan_top_coins_with_data(self):
        """정상적인 스캔 테스트"""
        scanner = LiquidityScanner(min_volume_krw=10_000_000_000)

        mock_ticker_data = [
            {
                'market': 'KRW-BTC',
                'trade_price': 50000000,
                'acc_trade_volume_24h': 1000,
                'acc_trade_price_24h': 100_000_000_000,
                'signed_change_rate': 0.02,
                'high_price': 51000000,
                'low_price': 49000000
            },
            {
                'market': 'KRW-ETH',
                'trade_price': 4000000,
                'acc_trade_volume_24h': 5000,
                'acc_trade_price_24h': 50_000_000_000,
                'signed_change_rate': 0.015,
                'high_price': 4100000,
                'low_price': 3900000
            },
            {
                'market': 'KRW-USDT',  # 스테이블코인 - 제외
                'trade_price': 1300,
                'acc_trade_volume_24h': 10000000,
                'acc_trade_price_24h': 200_000_000_000,
                'signed_change_rate': 0.001,
                'high_price': 1301,
                'low_price': 1299
            },
            {
                'market': 'KRW-XRP',  # 거래대금 부족 - 제외
                'trade_price': 500,
                'acc_trade_volume_24h': 1000000,
                'acc_trade_price_24h': 5_000_000_000,
                'signed_change_rate': 0.01,
                'high_price': 510,
                'low_price': 490
            }
        ]

        with patch.object(scanner, '_get_all_krw_tickers', new_callable=AsyncMock) as mock_get_tickers:
            with patch.object(scanner, '_get_ticker_data', new_callable=AsyncMock) as mock_get_data:
                with patch.object(scanner, '_add_volatility_data', new_callable=AsyncMock) as mock_volatility:
                    mock_get_tickers.return_value = ['KRW-BTC', 'KRW-ETH', 'KRW-USDT', 'KRW-XRP']
                    mock_get_data.return_value = mock_ticker_data
                    mock_volatility.side_effect = lambda x: x

                    result = await scanner.scan_top_coins(top_n=10, include_volatility=True)

                    # BTC, ETH만 통과해야 함 (USDT는 스테이블코인, XRP는 거래대금 부족)
                    assert len(result) == 2
                    assert result[0].symbol == "BTC"  # 거래대금 순 정렬
                    assert result[1].symbol == "ETH"

    @pytest.mark.asyncio
    async def test_get_coin_details(self):
        """특정 코인 상세 정보 조회 테스트"""
        scanner = LiquidityScanner()

        mock_data = [{
            'market': 'KRW-BTC',
            'trade_price': 50000000,
            'acc_trade_volume_24h': 1000,
            'acc_trade_price_24h': 100_000_000_000,
            'signed_change_rate': 0.02,
            'high_price': 51000000,
            'low_price': 49000000
        }]

        with patch.object(scanner, '_get_ticker_data', new_callable=AsyncMock) as mock_get_data:
            mock_get_data.return_value = mock_data

            result = await scanner.get_coin_details("KRW-BTC")

            assert result is not None
            assert result.ticker == "KRW-BTC"
            assert result.current_price == 50000000

    @pytest.mark.asyncio
    async def test_get_coin_details_not_found(self):
        """존재하지 않는 코인 조회"""
        scanner = LiquidityScanner()

        with patch.object(scanner, '_get_ticker_data', new_callable=AsyncMock) as mock_get_data:
            mock_get_data.return_value = []

            result = await scanner.get_coin_details("KRW-NOTEXIST")

            assert result is None
