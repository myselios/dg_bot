"""
시장 분석 서비스 단위 테스트.

CAPM 기반 베타/알파 계산 로직을 테스트합니다.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class TestMarketAnalysisService:
    """시장 분석 서비스 테스트."""

    @pytest.fixture
    def sample_btc_data(self) -> pd.DataFrame:
        """샘플 BTC 데이터 생성."""
        dates = pd.date_range(start='2024-01-01', periods=60, freq='D')
        # BTC: 상승 추세 (+20% over 60 days)
        prices = np.linspace(50000000, 60000000, 60)
        return pd.DataFrame({
            'close': prices,
        }, index=dates)

    @pytest.fixture
    def sample_eth_data(self) -> pd.DataFrame:
        """샘플 ETH 데이터 생성."""
        dates = pd.date_range(start='2024-01-01', periods=60, freq='D')
        # ETH: 더 높은 상승 (+30% over 60 days) - 베타 > 1
        prices = np.linspace(3000000, 3900000, 60)
        return pd.DataFrame({
            'close': prices,
        }, index=dates)

    def test_calculate_market_beta(self, sample_btc_data, sample_eth_data):
        """베타 계산 테스트 (ETH vs BTC)."""
        from src.domain.services.market_analysis import calculate_market_beta

        beta = calculate_market_beta(
            market_data=sample_btc_data,
            asset_data=sample_eth_data,
            lookback_days=30
        )

        # ETH가 BTC보다 변동성이 크므로 베타 > 1
        assert beta > 0.5
        assert beta < 2.0
        assert isinstance(beta, float)

    def test_calculate_alpha(self, sample_btc_data, sample_eth_data):
        """알파 계산 테스트 (초과 수익률)."""
        from src.domain.services.market_analysis import calculate_alpha

        alpha = calculate_alpha(
            market_data=sample_btc_data,
            asset_data=sample_eth_data,
            lookback_days=30
        )

        # 알파는 양수/음수 모두 가능
        assert isinstance(alpha, float)
        assert -100.0 < alpha < 100.0  # 현실적인 범위

    def test_calculate_correlation(self, sample_btc_data, sample_eth_data):
        """상관계수 계산 테스트."""
        from src.domain.services.market_analysis import calculate_correlation

        corr = calculate_correlation(
            market_data=sample_btc_data,
            asset_data=sample_eth_data,
            lookback_days=30
        )

        # 상관계수는 -1 ~ 1
        assert -1.0 <= corr <= 1.0
        assert isinstance(corr, float)

    def test_calculate_market_risk_high(self):
        """시장 리스크 판단 테스트 - HIGH."""
        from src.domain.services.market_analysis import assess_market_risk

        # BTC 급락 시나리오
        btc_return_1d = -8.0  # -8% in 1 day
        correlation = 0.85

        risk_level = assess_market_risk(
            btc_return_1d=btc_return_1d,
            correlation=correlation
        )

        assert risk_level == "high"

    def test_calculate_market_risk_low(self):
        """시장 리스크 판단 테스트 - LOW."""
        from src.domain.services.market_analysis import assess_market_risk

        # BTC 안정적인 시나리오
        btc_return_1d = 1.5  # +1.5% in 1 day
        correlation = 0.5

        risk_level = assess_market_risk(
            btc_return_1d=btc_return_1d,
            correlation=correlation
        )

        assert risk_level == "low"

    def test_calculate_market_risk_medium(self):
        """시장 리스크 판단 테스트 - MEDIUM."""
        from src.domain.services.market_analysis import assess_market_risk

        # BTC 중간 시나리오
        btc_return_1d = -3.5  # -3.5% in 1 day
        correlation = 0.7

        risk_level = assess_market_risk(
            btc_return_1d=btc_return_1d,
            correlation=correlation
        )

        assert risk_level == "medium"

    def test_empty_data_handling(self):
        """빈 데이터 처리 테스트."""
        from src.domain.services.market_analysis import calculate_market_beta

        empty_df = pd.DataFrame({'close': []})
        valid_df = pd.DataFrame({
            'close': [50000, 51000, 52000]
        }, index=pd.date_range(start='2024-01-01', periods=3, freq='D'))

        with pytest.raises(ValueError, match="데이터 부족"):
            calculate_market_beta(empty_df, valid_df, lookback_days=30)

    def test_insufficient_data(self):
        """불충분한 데이터 처리 테스트."""
        from src.domain.services.market_analysis import calculate_market_beta

        # 5일 데이터만 있지만 30일 lookback 요청
        dates = pd.date_range(start='2024-01-01', periods=5, freq='D')
        short_df = pd.DataFrame({
            'close': [50000, 51000, 52000, 51500, 53000]
        }, index=dates)

        with pytest.raises(ValueError, match="데이터 부족"):
            calculate_market_beta(short_df, short_df, lookback_days=30)

    def test_mismatched_dates(self):
        """날짜 불일치 데이터 처리 테스트."""
        from src.domain.services.market_analysis import calculate_correlation

        # 서로 다른 날짜 범위
        dates1 = pd.date_range(start='2024-01-01', periods=30, freq='D')
        dates2 = pd.date_range(start='2024-02-01', periods=30, freq='D')

        df1 = pd.DataFrame({'close': np.random.randn(30)}, index=dates1)
        df2 = pd.DataFrame({'close': np.random.randn(30)}, index=dates2)

        # 겹치는 날짜가 없으면 에러
        with pytest.raises(ValueError, match="데이터 부족"):
            calculate_correlation(df1, df2, lookback_days=30)

    def test_zero_variance_handling(self):
        """변동성 0 (가격 고정) 처리 테스트."""
        from src.domain.services.market_analysis import calculate_market_beta

        dates = pd.date_range(start='2024-01-01', periods=60, freq='D')

        # BTC 가격 고정 (변동성 0)
        btc_flat = pd.DataFrame({'close': [50000] * 60}, index=dates)
        eth_normal = pd.DataFrame({'close': np.linspace(3000, 3500, 60)}, index=dates)

        # 변동성이 0이면 베타 = 1.0 (기본값)
        beta = calculate_market_beta(btc_flat, eth_normal, lookback_days=30)
        assert beta == 1.0
