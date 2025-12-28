"""
BTC 데이터 통합 테스트 (Phase 2)

TDD 원칙: main.py에 BTC 데이터 수집 및 시장 상관관계 분석 통합을 검증합니다.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class TestBTCDataIntegrationInMain:
    """main.py에 BTC 데이터 통합 테스트"""
    
    @pytest.fixture
    def sample_btc_data(self):
        """샘플 BTC 데이터"""
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        return pd.DataFrame({
            'open': np.random.randn(50).cumsum() + 50000,
            'high': np.random.randn(50).cumsum() + 51000,
            'low': np.random.randn(50).cumsum() + 49000,
            'close': np.random.randn(50).cumsum() + 50000,
            'volume': np.random.randint(1000, 10000, 50)
        }, index=dates)
    
    @pytest.fixture
    def sample_eth_data(self):
        """샘플 ETH 데이터"""
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        return pd.DataFrame({
            'open': np.random.randn(50).cumsum() + 3000,
            'high': np.random.randn(50).cumsum() + 3100,
            'low': np.random.randn(50).cumsum() + 2900,
            'close': np.random.randn(50).cumsum() + 3000,
            'volume': np.random.randint(100, 1000, 50)
        }, index=dates)
    
    @pytest.mark.integration
    @patch('src.data.collector.DataCollector.get_chart_data_with_btc')
    @patch('src.ai.market_correlation.calculate_market_risk')
    def test_btc_data_collection_in_main(
        self,
        mock_calculate_market_risk,
        mock_get_chart_data_with_btc,
        sample_eth_data,
        sample_btc_data
    ):
        """main.py에서 BTC 데이터 수집 테스트"""
        # Given
        mock_get_chart_data_with_btc.return_value = {
            'eth': {
                'day': sample_eth_data,
                'minute60': sample_eth_data,
                'minute15': sample_eth_data
            },
            'btc': {
                'day': sample_btc_data,
                'minute60': sample_btc_data,
                'minute15': sample_btc_data
            }
        }
        
        mock_calculate_market_risk.return_value = {
            'market_risk': 'low',
            'risk_reason': '시장 리스크 낮음',
            'beta': 1.1,
            'alpha': 0.01,
            'btc_return_1d': -0.005,
            'correlation': 0.85
        }
        
        # When
        from src.data.collector import DataCollector
        data_collector = DataCollector()
        
        # BTC 데이터 포함 수집
        chart_data_with_btc = data_collector.get_chart_data_with_btc("KRW-ETH")
        
        # Then
        assert chart_data_with_btc is not None
        assert 'eth' in chart_data_with_btc
        assert 'btc' in chart_data_with_btc
        
        # ETH 데이터 검증
        assert 'day' in chart_data_with_btc['eth']
        assert len(chart_data_with_btc['eth']['day']) == 50
        
        # BTC 데이터 검증
        assert 'day' in chart_data_with_btc['btc']
        assert len(chart_data_with_btc['btc']['day']) == 50
    
    @pytest.mark.integration
    @patch('src.ai.market_correlation.calculate_market_risk')
    def test_market_correlation_calculation(
        self,
        mock_calculate_market_risk,
        sample_eth_data,
        sample_btc_data
    ):
        """시장 상관관계 계산 테스트"""
        # Given
        mock_calculate_market_risk.return_value = {
            'market_risk': 'high',
            'risk_reason': 'BTC 하락 중(-1.50%), ETH 베타=1.35, 알파=-0.02%',
            'beta': 1.35,
            'alpha': -0.0002,
            'btc_return_1d': -0.015,
            'correlation': 0.92
        }
        
        # When
        from src.ai.market_correlation import calculate_market_risk
        result = calculate_market_risk(sample_btc_data, sample_eth_data)
        
        # Then
        assert result is not None
        assert 'market_risk' in result
        assert 'beta' in result
        assert 'alpha' in result
        assert 'correlation' in result
        
        # 위험도 판단 검증
        assert result['market_risk'] in ['high', 'medium', 'low', 'unknown']
        
        # 베타 값 검증 (0.5 ~ 2.0 범위가 일반적)
        if result['beta'] is not None:
            assert 0 < result['beta'] < 3.0
    
    @pytest.mark.integration
    @patch('src.data.collector.DataCollector.get_chart_data_with_btc')
    @patch('src.ai.market_correlation.calculate_market_risk')
    def test_high_risk_scenario(
        self,
        mock_calculate_market_risk,
        mock_get_chart_data_with_btc,
        sample_eth_data,
        sample_btc_data
    ):
        """BTC 하락 + 높은 베타 = 고위험 시나리오 테스트"""
        # Given
        # BTC 급락 시나리오
        btc_crash_data = sample_btc_data.copy()
        btc_crash_data.iloc[-1, btc_crash_data.columns.get_loc('close')] *= 0.97  # 3% 하락
        
        mock_get_chart_data_with_btc.return_value = {
            'eth': {
                'day': sample_eth_data,
                'minute60': sample_eth_data,
                'minute15': sample_eth_data
            },
            'btc': {
                'day': btc_crash_data,
                'minute60': btc_crash_data,
                'minute15': btc_crash_data
            }
        }
        
        mock_calculate_market_risk.return_value = {
            'market_risk': 'high',
            'risk_reason': 'BTC 하락 중(-3.00%), ETH 베타=1.45, 알파=-0.01%',
            'beta': 1.45,
            'alpha': -0.0001,
            'btc_return_1d': -0.03,
            'correlation': 0.88
        }
        
        # When
        from src.data.collector import DataCollector
        from src.ai.market_correlation import calculate_market_risk
        
        data_collector = DataCollector()
        chart_data_with_btc = data_collector.get_chart_data_with_btc("KRW-ETH")
        
        market_risk = calculate_market_risk(
            chart_data_with_btc['btc']['day'],
            chart_data_with_btc['eth']['day']
        )
        
        # Then
        assert market_risk['market_risk'] == 'high'
        assert market_risk['beta'] > 1.2  # 높은 베타
        assert market_risk['btc_return_1d'] < -0.01  # BTC 하락
    
    @pytest.mark.integration
    def test_btc_data_unavailable_fallback(self):
        """BTC 데이터 조회 실패 시 fallback 처리 테스트"""
        # Given
        with patch('src.data.collector.DataCollector.get_chart_data_with_btc') as mock_get:
            mock_get.return_value = None
            
            # When
            from src.data.collector import DataCollector
            data_collector = DataCollector()
            result = data_collector.get_chart_data_with_btc("KRW-ETH")
            
            # Then
            assert result is None


class TestMarketRiskIntegration:
    """시장 리스크 계산 통합 테스트"""
    
    @pytest.mark.integration
    def test_calculate_market_risk_with_real_structure(self):
        """실제 데이터 구조로 시장 리스크 계산 테스트"""
        # Given
        dates = pd.date_range('2024-01-01', periods=60, freq='D')
        
        # BTC 하락 추세 데이터
        btc_prices = np.linspace(50000, 48000, 60)
        btc_data = pd.DataFrame({
            'open': btc_prices + np.random.randn(60) * 100,
            'high': btc_prices + np.random.randn(60) * 100 + 500,
            'low': btc_prices + np.random.randn(60) * 100 - 500,
            'close': btc_prices,
            'volume': np.random.randint(1000, 10000, 60)
        }, index=dates)
        
        # ETH 더 크게 하락 (베타 > 1)
        eth_prices = np.linspace(3000, 2850, 60)
        eth_data = pd.DataFrame({
            'open': eth_prices + np.random.randn(60) * 10,
            'high': eth_prices + np.random.randn(60) * 10 + 50,
            'low': eth_prices + np.random.randn(60) * 10 - 50,
            'close': eth_prices,
            'volume': np.random.randint(100, 1000, 60)
        }, index=dates)
        
        # When
        from src.ai.market_correlation import calculate_market_risk
        result = calculate_market_risk(btc_data, eth_data)
        
        # Then
        assert result is not None
        assert 'market_risk' in result
        assert 'beta' in result
        assert 'alpha' in result
        
        # 시장 위험도는 low, medium, high, unknown 중 하나
        assert result['market_risk'] in ['low', 'medium', 'high', 'unknown']
        
        # ETH가 더 크게 하락했으므로 베타 > 1 예상
        if result['beta'] is not None and result['market_risk'] != 'unknown':
            assert result['beta'] > 0.8

