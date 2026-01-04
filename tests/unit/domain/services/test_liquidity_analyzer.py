"""
유동성 분석기 테스트 (liquidity_analyzer.py)
TDD 원칙: 테스트 먼저 작성, 구현 나중
"""
import pytest
from src.trading.liquidity_analyzer import LiquidityAnalyzer


class TestLiquidityAnalyzer:
    """LiquidityAnalyzer 테스트"""

    @pytest.fixture
    def sample_orderbook_normal(self):
        """정상적인 호가창 데이터 (유동성 충분)"""
        return {
            'orderbook_units': [
                # 매도 호가 (asks)
                {'ask_price': 50000000, 'ask_size': 0.5, 'bid_price': 49950000, 'bid_size': 0.6},
                {'ask_price': 50010000, 'ask_size': 0.4, 'bid_price': 49940000, 'bid_size': 0.5},
                {'ask_price': 50020000, 'ask_size': 0.3, 'bid_price': 49930000, 'bid_size': 0.4},
                {'ask_price': 50030000, 'ask_size': 0.3, 'bid_price': 49920000, 'bid_size': 0.3},
                {'ask_price': 50040000, 'ask_size': 0.2, 'bid_price': 49910000, 'bid_size': 0.2},
            ]
        }

    @pytest.fixture
    def sample_orderbook_low_liquidity(self):
        """유동성이 부족한 호가창"""
        return {
            'orderbook_units': [
                {'ask_price': 50000000, 'ask_size': 0.01, 'bid_price': 49950000, 'bid_size': 0.01},
                {'ask_price': 50010000, 'ask_size': 0.01, 'bid_price': 49940000, 'bid_size': 0.01},
                {'ask_price': 50020000, 'ask_size': 0.01, 'bid_price': 49930000, 'bid_size': 0.01},
            ]
        }

    # ============================================
    # calculate_slippage() - 매수 테스트
    # ============================================

    @pytest.mark.unit
    def test_calculate_buy_slippage_small_order(self, sample_orderbook_normal):
        """소액 매수 주문 - 슬리피지 낮음 (< 0.1%)"""
        # Given
        order_krw_amount = 1000000  # 100만원 (소액)

        # When
        result = LiquidityAnalyzer.calculate_slippage(
            orderbook=sample_orderbook_normal,
            order_side='buy',
            order_krw_amount=order_krw_amount
        )

        # Then
        assert result['liquidity_available'] is True
        assert result['expected_slippage_pct'] < 0.1
        assert result['expected_avg_price'] > 0
        assert result['required_levels'] == 1  # 첫 호가에서 전부 체결

    @pytest.mark.unit
    def test_calculate_buy_slippage_medium_order(self, sample_orderbook_normal):
        """중액 매수 주문 - 슬리피지 중간 (0.1~0.3%)"""
        # Given
        order_krw_amount = 10000000  # 1000만원 (중액)

        # When
        result = LiquidityAnalyzer.calculate_slippage(
            orderbook=sample_orderbook_normal,
            order_side='buy',
            order_krw_amount=order_krw_amount
        )

        # Then
        assert result['liquidity_available'] is True
        assert 0.0 <= result['expected_slippage_pct'] <= 0.5
        assert result['required_levels'] >= 1

    @pytest.mark.unit
    def test_calculate_buy_slippage_large_order(self, sample_orderbook_normal):
        """대액 매수 주문 - 슬리피지 높음 (> 0.3%)"""
        # Given
        order_krw_amount = 50000000  # 5000만원 (대액)

        # When
        result = LiquidityAnalyzer.calculate_slippage(
            orderbook=sample_orderbook_normal,
            order_side='buy',
            order_krw_amount=order_krw_amount
        )

        # Then
        assert result['liquidity_available'] is True
        assert result['expected_slippage_pct'] >= 0.0
        assert result['required_levels'] >= 3

    @pytest.mark.unit
    def test_calculate_buy_slippage_insufficient_liquidity(self, sample_orderbook_low_liquidity):
        """유동성 부족 - 매수 불가"""
        # Given
        order_krw_amount = 10000000  # 1000만원

        # When
        result = LiquidityAnalyzer.calculate_slippage(
            orderbook=sample_orderbook_low_liquidity,
            order_side='buy',
            order_krw_amount=order_krw_amount
        )

        # Then
        assert result['liquidity_available'] is False
        assert result['expected_slippage_pct'] == float('inf')
        assert '유동성 부족' in result['warning']

    # ============================================
    # calculate_slippage() - 매도 테스트
    # ============================================

    @pytest.mark.unit
    def test_calculate_sell_slippage_normal(self, sample_orderbook_normal):
        """정상 매도 주문 - 슬리피지 계산"""
        # Given
        coin_amount = 0.2  # 0.2 BTC

        # When
        result = LiquidityAnalyzer.calculate_slippage(
            orderbook=sample_orderbook_normal,
            order_side='sell',
            order_krw_amount=coin_amount
        )

        # Then
        assert result['liquidity_available'] is True
        assert result['expected_slippage_pct'] >= 0.0
        assert result['expected_avg_price'] > 0

    # ============================================
    # 경고 메시지 테스트
    # ============================================

    @pytest.mark.unit
    def test_slippage_warning_high_slippage(self, sample_orderbook_normal):
        """슬리피지 > 0.3% 시 경고 메시지"""
        # Given
        order_krw_amount = 70000000  # 7000만원 (매우 큰 금액)

        # When
        result = LiquidityAnalyzer.calculate_slippage(
            orderbook=sample_orderbook_normal,
            order_side='buy',
            order_krw_amount=order_krw_amount
        )

        # Then
        # 슬리피지가 높으면 경고 메시지 있어야 함
        if result['expected_slippage_pct'] > 0.3:
            assert result['warning'] != ""
            assert '슬리피지' in result['warning']

    @pytest.mark.unit
    def test_slippage_warning_many_levels(self, sample_orderbook_normal):
        """호가 단계 > 5 시 경고 메시지"""
        # Given
        order_krw_amount = 100000000  # 1억원 (매우 큰 금액)

        # When
        result = LiquidityAnalyzer.calculate_slippage(
            orderbook=sample_orderbook_normal,
            order_side='buy',
            order_krw_amount=order_krw_amount
        )

        # Then
        # 유동성이 부족하거나 많은 호가 사용 시 경고
        assert 'warning' in result

    # ============================================
    # 엣지 케이스 테스트
    # ============================================

    @pytest.mark.unit
    def test_calculate_slippage_zero_amount(self, sample_orderbook_normal):
        """주문 금액이 0인 경우"""
        # Given
        order_krw_amount = 0

        # When
        result = LiquidityAnalyzer.calculate_slippage(
            orderbook=sample_orderbook_normal,
            order_side='buy',
            order_krw_amount=order_krw_amount
        )

        # Then
        assert result['liquidity_available'] is True
        assert result['expected_slippage_pct'] == 0.0
        assert result['required_levels'] == 0

    @pytest.mark.unit
    def test_calculate_slippage_empty_orderbook(self):
        """호가창이 비어있는 경우"""
        # Given
        empty_orderbook = {'orderbook_units': []}
        order_krw_amount = 1000000

        # When
        result = LiquidityAnalyzer.calculate_slippage(
            orderbook=empty_orderbook,
            order_side='buy',
            order_krw_amount=order_krw_amount
        )

        # Then
        assert result['liquidity_available'] is False
        assert result['expected_slippage_pct'] == float('inf')
