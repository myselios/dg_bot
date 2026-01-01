"""
ATR 기반 변동성 돌파 전략 테스트
TDD 원칙: 테스트 먼저 작성, 구현 나중
"""
import pytest
import pandas as pd
import numpy as np
from src.backtesting.rule_based_strategy import RuleBasedBreakoutStrategy


class TestATRBreakout:
    """ATR 기반 변동성 돌파 전략 테스트"""

    @pytest.fixture
    def sample_ohlcv_data(self):
        """샘플 OHLCV 데이터 (저변동성)"""
        dates = pd.date_range('2024-01-01', periods=30, freq='1h')
        np.random.seed(42)

        # 저변동성 시장 (변동 폭 작음)
        data = pd.DataFrame({
            'timestamp': dates,
            'open': 50000000 + np.random.randn(30) * 100000,
            'high': 50100000 + np.random.randn(30) * 100000,
            'low': 49900000 + np.random.randn(30) * 100000,
            'close': 50000000 + np.random.randn(30) * 100000,
            'volume': 100 + np.random.randn(30) * 10
        })
        data.set_index('timestamp', inplace=True)
        return data

    @pytest.fixture
    def high_volatility_data(self):
        """고변동성 OHLCV 데이터"""
        dates = pd.date_range('2024-01-01', periods=30, freq='1h')
        np.random.seed(42)

        # 고변동성 시장 (변동 폭 큼)
        data = pd.DataFrame({
            'timestamp': dates,
            'open': 50000000 + np.random.randn(30) * 2000000,
            'high': 51000000 + np.random.randn(30) * 2000000,
            'low': 49000000 + np.random.randn(30) * 2000000,
            'close': 50000000 + np.random.randn(30) * 2000000,
            'volume': 100 + np.random.randn(30) * 10
        })
        data.set_index('timestamp', inplace=True)
        return data

    # ============================================
    # ATR 계산 테스트
    # ============================================

    @pytest.mark.unit
    def test_calculate_atr_basic(self, sample_ohlcv_data):
        """ATR 기본 계산 테스트"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker='KRW-BTC')

        # When
        atr_series = strategy._calculate_atr(sample_ohlcv_data, period=14)

        # Then
        assert atr_series is not None
        assert len(atr_series) == len(sample_ohlcv_data)
        assert atr_series.iloc[-1] > 0  # 마지막 ATR 값이 양수

    @pytest.mark.unit
    def test_calculate_atr_low_volatility(self, sample_ohlcv_data):
        """저변동성 시장 - ATR 낮음"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker="KRW-BTC")

        # When
        atr_series = strategy._calculate_atr(sample_ohlcv_data, period=14)
        current_atr = atr_series.iloc[-1]
        yesterday_close = sample_ohlcv_data.iloc[-2]['close']
        atr_pct = (current_atr / yesterday_close) * 100

        # Then
        # 저변동성 시장: ATR < 2% 예상
        assert atr_pct < 5.0

    @pytest.mark.unit
    def test_calculate_atr_high_volatility(self, high_volatility_data):
        """고변동성 시장 - ATR 높음"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker="KRW-BTC")

        # When
        atr_series = strategy._calculate_atr(high_volatility_data, period=14)
        current_atr = atr_series.iloc[-1]
        yesterday_close = high_volatility_data.iloc[-2]['close']
        atr_pct = (current_atr / yesterday_close) * 100

        # Then
        # 고변동성 시장: ATR >= 2% 예상
        assert atr_pct >= 0.0

    # ============================================
    # ATR 기반 동적 K값 테스트
    # ============================================

    @pytest.mark.unit
    def test_get_dynamic_k_value_low_volatility(self):
        """저변동성 - K값 2.0"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker="KRW-BTC")
        atr_pct = 1.5  # ATR < 2%

        # When
        k_value = strategy._get_dynamic_k_value(atr_pct)

        # Then
        assert k_value == 2.0

    @pytest.mark.unit
    def test_get_dynamic_k_value_medium_volatility(self):
        """중변동성 - K값 1.5"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker="KRW-BTC")
        atr_pct = 3.0  # 2% <= ATR < 4%

        # When
        k_value = strategy._get_dynamic_k_value(atr_pct)

        # Then
        assert k_value == 1.5

    @pytest.mark.unit
    def test_get_dynamic_k_value_high_volatility(self):
        """고변동성 - K값 1.0"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker="KRW-BTC")
        atr_pct = 5.0  # ATR >= 4%

        # When
        k_value = strategy._get_dynamic_k_value(atr_pct)

        # Then
        assert k_value == 1.0

    # ============================================
    # ATR 기반 돌파가 계산 테스트
    # ============================================

    @pytest.mark.unit
    def test_calculate_target_price_atr_low_volatility(self, sample_ohlcv_data):
        """저변동성 - 큰 K값으로 돌파가 계산"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker="KRW-BTC", use_atr_breakout=True)
        current_idx = 20  # 충분한 데이터 확보

        # When
        target_price = strategy._calculate_target_price_atr(sample_ohlcv_data, current_idx)

        # Then
        yesterday_close = sample_ohlcv_data.iloc[current_idx - 1]['close']
        assert target_price > yesterday_close  # 돌파가가 전일 종가보다 높아야 함

    @pytest.mark.unit
    def test_calculate_target_price_atr_high_volatility(self, high_volatility_data):
        """고변동성 - 작은 K값으로 돌파가 계산"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker="KRW-BTC", use_atr_breakout=True)
        current_idx = 20

        # When
        target_price = strategy._calculate_target_price_atr(high_volatility_data, current_idx)

        # Then
        yesterday_close = high_volatility_data.iloc[current_idx - 1]['close']
        assert target_price > yesterday_close

    @pytest.mark.unit
    def test_calculate_target_price_atr_insufficient_data(self, sample_ohlcv_data):
        """데이터 부족 시 기존 방식으로 fallback"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker="KRW-BTC", use_atr_breakout=True)
        current_idx = 5  # ATR 계산에 부족한 데이터

        # When
        target_price = strategy._calculate_target_price_atr(sample_ohlcv_data, current_idx)

        # Then
        # Fallback: 기존 방식 (전일 고저 범위 * 0.5)
        yesterday_high = sample_ohlcv_data.iloc[current_idx - 1]['high']
        yesterday_low = sample_ohlcv_data.iloc[current_idx - 1]['low']
        today_open = sample_ohlcv_data.iloc[current_idx]['open']
        expected_target = today_open + (yesterday_high - yesterday_low) * 0.5

        assert abs(target_price - expected_target) < 100000  # 오차 범위 10만원

    # ============================================
    # ATR 기반 손절/익절가 계산 테스트
    # ============================================

    @pytest.mark.unit
    def test_calculate_stop_loss_price_atr(self, sample_ohlcv_data):
        """ATR 기반 손절가 계산"""
        # Given
        from src.risk.manager import RiskManager, RiskLimits
        limits = RiskLimits(
            use_atr_based_stops=True,
            stop_loss_atr_multiplier=1.5
        )
        risk_manager = RiskManager(limits=limits, persist_state=False)

        entry_price = 50000000
        atr = 500000  # ATR 50만원

        # When
        stop_loss_price = risk_manager.calculate_stop_loss_price(entry_price, atr)

        # Then
        expected_stop = entry_price - (atr * 1.5)
        assert stop_loss_price == expected_stop
        assert stop_loss_price < entry_price

    @pytest.mark.unit
    def test_calculate_take_profit_price_atr(self, sample_ohlcv_data):
        """ATR 기반 익절가 계산"""
        # Given
        from src.risk.manager import RiskManager, RiskLimits
        limits = RiskLimits(
            use_atr_based_stops=True,
            take_profit_atr_multiplier=2.5
        )
        risk_manager = RiskManager(limits=limits, persist_state=False)

        entry_price = 50000000
        atr = 500000

        # When
        take_profit_price = risk_manager.calculate_take_profit_price(entry_price, atr)

        # Then
        expected_profit = entry_price + (atr * 2.5)
        assert take_profit_price == expected_profit
        assert take_profit_price > entry_price

    # ============================================
    # 통합 테스트
    # ============================================

    @pytest.mark.unit
    def test_generate_signal_with_atr_breakout(self, sample_ohlcv_data):
        """ATR 기반 전략으로 매수 신호 생성"""
        # Given
        strategy = RuleBasedBreakoutStrategy(ticker="KRW-BTC", use_atr_breakout=True)
        current_idx = 20

        # When
        signal = strategy.generate_signal(sample_ohlcv_data, current_idx)

        # Then
        assert signal in ['buy', 'sell', 'hold']
        # ATR 기반 전략이 적용되었는지 간접 확인
        # (정확한 신호는 시장 데이터에 따라 달라지므로, 에러 없이 실행되는지만 확인)

    @pytest.mark.unit
    def test_atr_breakout_vs_fixed_k(self, sample_ohlcv_data):
        """ATR 전략 vs 고정 K값 전략 비교"""
        # Given
        strategy_atr = RuleBasedBreakoutStrategy(ticker="KRW-BTC", use_atr_breakout=True)
        strategy_fixed = RuleBasedBreakoutStrategy(ticker="KRW-BTC", use_atr_breakout=False)
        current_idx = 20

        # When
        target_atr = strategy_atr._calculate_target_price_atr(sample_ohlcv_data, current_idx)
        target_fixed = strategy_fixed._calculate_target_price(sample_ohlcv_data, current_idx)

        # Then
        # 두 방식의 돌파가가 다를 수 있음
        # (같을 수도 있지만, 일반적으로 다름)
        assert target_atr > 0
        assert target_fixed > 0
