"""
설정 테스트
"""
import pytest
import os
from src.config.settings import TradingConfig, DataConfig, AIConfig, APIConfig


class TestConfig:
    """설정 클래스 테스트"""
    
    def test_trading_config(self):
        """TradingConfig 테스트"""
        assert TradingConfig.TICKER == "KRW-ETH"
        assert TradingConfig.MIN_ORDER_AMOUNT == 5000
        assert TradingConfig.FEE_RATE == 0.0005
        assert TradingConfig.BUY_PERCENTAGE == 0.3
    
    def test_data_config(self):
        """DataConfig 테스트"""
        assert DataConfig.DAY_CHART_COUNT == 60  # RSI 다이버전스 분석을 위해 60일로 증가
        assert DataConfig.HOUR_CHART_COUNT == 24
        assert DataConfig.ORDERBOOK_DEPTH == 5
    
    def test_ai_config(self):
        """AIConfig 테스트"""
        assert AIConfig.MODEL == "gpt-5.2"  # 최신 모델로 업데이트
        assert AIConfig.TEMPERATURE == 0.7
    
    def test_api_config_validation_without_keys(self):
        """API 키 없이 검증 테스트"""
        from src.exceptions import ConfigurationError
        original_access = APIConfig.UPBIT_ACCESS_KEY
        original_secret = APIConfig.UPBIT_SECRET_KEY
        
        try:
            APIConfig.UPBIT_ACCESS_KEY = None
            APIConfig.UPBIT_SECRET_KEY = None
            
            with pytest.raises(ConfigurationError):
                APIConfig.validate()
        finally:
            APIConfig.UPBIT_ACCESS_KEY = original_access
            APIConfig.UPBIT_SECRET_KEY = original_secret

