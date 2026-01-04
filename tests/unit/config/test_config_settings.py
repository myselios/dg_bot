"""
설정 유틸리티 함수 테스트
TDD 원칙: 환경 변수 처리 함수를 검증합니다.
"""
import pytest
import os
from src.config.settings import (
    get_env_int, get_env_float, get_env_str,
    TradingConfig, DataConfig, AIConfig, APIConfig
)
from src.exceptions import ConfigurationError


class TestGetEnvFunctions:
    """환경 변수 가져오기 함수 테스트"""
    
    @pytest.mark.unit
    def test_get_env_int_with_default(self):
        """기본값으로 정수 가져오기"""
        # Given
        key = "NON_EXISTENT_KEY_INT"
        default = 42
        
        # When
        result = get_env_int(key, default)
        
        # Then
        assert result == 42
    
    @pytest.mark.unit
    def test_get_env_int_with_value(self, monkeypatch):
        """환경 변수에서 정수 가져오기"""
        # Given
        monkeypatch.setenv("TEST_INT_KEY", "100")
        
        # When
        result = get_env_int("TEST_INT_KEY", 50)
        
        # Then
        assert result == 100
    
    @pytest.mark.unit
    def test_get_env_int_with_min_validation(self, monkeypatch):
        """최소값 검증"""
        # Given
        monkeypatch.setenv("TEST_MIN_KEY", "5")
        
        # Then
        with pytest.raises(ConfigurationError):
            get_env_int("TEST_MIN_KEY", 10, min_value=10)
    
    @pytest.mark.unit
    def test_get_env_int_with_max_validation(self, monkeypatch):
        """최대값 검증"""
        # Given
        monkeypatch.setenv("TEST_MAX_KEY", "100")
        
        # Then
        with pytest.raises(ConfigurationError):
            get_env_int("TEST_MAX_KEY", 50, max_value=50)
    
    @pytest.mark.unit
    def test_get_env_int_invalid_value(self, monkeypatch):
        """잘못된 정수 형식"""
        # Given
        monkeypatch.setenv("TEST_INVALID_INT", "not_a_number")
        
        # Then
        with pytest.raises(ConfigurationError):
            get_env_int("TEST_INVALID_INT", 10)
    
    @pytest.mark.unit
    def test_get_env_float_with_default(self):
        """기본값으로 실수 가져오기"""
        # Given
        key = "NON_EXISTENT_KEY_FLOAT"
        default = 3.14
        
        # When
        result = get_env_float(key, default)
        
        # Then
        assert result == 3.14
    
    @pytest.mark.unit
    def test_get_env_float_with_value(self, monkeypatch):
        """환경 변수에서 실수 가져오기"""
        # Given
        monkeypatch.setenv("TEST_FLOAT_KEY", "2.5")
        
        # When
        result = get_env_float("TEST_FLOAT_KEY", 1.0)
        
        # Then
        assert result == 2.5
    
    @pytest.mark.unit
    def test_get_env_float_with_min_validation(self, monkeypatch):
        """실수 최소값 검증"""
        # Given
        monkeypatch.setenv("TEST_FLOAT_MIN", "0.5")
        
        # Then
        with pytest.raises(ConfigurationError):
            get_env_float("TEST_FLOAT_MIN", 1.0, min_value=1.0)
    
    @pytest.mark.unit
    def test_get_env_float_with_max_validation(self, monkeypatch):
        """실수 최대값 검증"""
        # Given
        monkeypatch.setenv("TEST_FLOAT_MAX", "5.0")
        
        # Then
        with pytest.raises(ConfigurationError):
            get_env_float("TEST_FLOAT_MAX", 2.0, max_value=3.0)
    
    @pytest.mark.unit
    def test_get_env_float_invalid_value(self, monkeypatch):
        """잘못된 실수 형식"""
        # Given
        monkeypatch.setenv("TEST_INVALID_FLOAT", "not_a_float")
        
        # Then
        with pytest.raises(ConfigurationError):
            get_env_float("TEST_INVALID_FLOAT", 1.0)
    
    @pytest.mark.unit
    def test_get_env_str_with_default(self):
        """기본값으로 문자열 가져오기"""
        # Given
        key = "NON_EXISTENT_KEY_STR"
        default = "default_value"
        
        # When
        result = get_env_str(key, default)
        
        # Then
        assert result == "default_value"
    
    @pytest.mark.unit
    def test_get_env_str_with_value(self, monkeypatch):
        """환경 변수에서 문자열 가져오기"""
        # Given
        monkeypatch.setenv("TEST_STR_KEY", "test_value")
        
        # When
        result = get_env_str("TEST_STR_KEY", "default")
        
        # Then
        assert result == "test_value"


class TestTradingConfigValidation:
    """TradingConfig 검증 테스트"""
    
    @pytest.mark.unit
    def test_validate_success(self):
        """정상적인 설정 검증"""
        # Given - 기본 설정은 유효함
        
        # When & Then - 에러가 발생하지 않아야 함
        TradingConfig.validate()
    
    @pytest.mark.unit
    def test_validate_invalid_min_order_amount(self, monkeypatch):
        """잘못된 최소 주문 금액"""
        # Given
        original = TradingConfig.MIN_ORDER_AMOUNT
        try:
            monkeypatch.setattr(TradingConfig, 'MIN_ORDER_AMOUNT', -1000)
            
            # Then
            with pytest.raises(ConfigurationError):
                TradingConfig.validate()
        finally:
            monkeypatch.setattr(TradingConfig, 'MIN_ORDER_AMOUNT', original)
    
    @pytest.mark.unit
    def test_validate_invalid_fee_rate(self, monkeypatch):
        """잘못된 수수료율"""
        # Given
        original = TradingConfig.FEE_RATE
        try:
            monkeypatch.setattr(TradingConfig, 'FEE_RATE', 0.02)  # 2% (너무 높음)
            
            # Then
            with pytest.raises(ConfigurationError):
                TradingConfig.validate()
        finally:
            monkeypatch.setattr(TradingConfig, 'FEE_RATE', original)


class TestDataConfigValidation:
    """DataConfig 검증 테스트"""
    
    @pytest.mark.unit
    def test_validate_success(self):
        """정상적인 데이터 설정 검증"""
        # Given - 기본 설정은 유효함
        
        # When & Then - 에러가 발생하지 않아야 함
        DataConfig.validate()
    
    @pytest.mark.unit
    def test_validate_invalid_day_chart_count(self, monkeypatch):
        """잘못된 일봉 조회 개수"""
        # Given
        original = DataConfig.DAY_CHART_COUNT
        try:
            monkeypatch.setattr(DataConfig, 'DAY_CHART_COUNT', 0)
            
            # Then
            with pytest.raises(ConfigurationError):
                DataConfig.validate()
        finally:
            monkeypatch.setattr(DataConfig, 'DAY_CHART_COUNT', original)


class TestAIConfigValidation:
    """AIConfig 검증 테스트"""
    
    @pytest.mark.unit
    def test_validate_success(self):
        """정상적인 AI 설정 검증"""
        # Given - 기본 설정은 유효함
        
        # When & Then - 에러가 발생하지 않아야 함
        AIConfig.validate()
    
    @pytest.mark.unit
    def test_validate_invalid_model(self, monkeypatch):
        """지원하지 않는 모델"""
        # Given
        original = AIConfig.MODEL
        try:
            monkeypatch.setattr(AIConfig, 'MODEL', 'invalid-model')
            
            # Then
            with pytest.raises(ConfigurationError):
                AIConfig.validate()
        finally:
            monkeypatch.setattr(AIConfig, 'MODEL', original)
    
    @pytest.mark.unit
    def test_validate_invalid_temperature(self, monkeypatch):
        """잘못된 Temperature 값"""
        # Given
        original = AIConfig.TEMPERATURE
        try:
            monkeypatch.setattr(AIConfig, 'TEMPERATURE', 3.0)  # 너무 높음
            
            # Then
            with pytest.raises(ConfigurationError):
                AIConfig.validate()
        finally:
            monkeypatch.setattr(AIConfig, 'TEMPERATURE', original)


class TestAPIConfigValidation:
    """APIConfig 검증 테스트"""
    
    @pytest.mark.unit
    def test_validate_upbit_only_success(self, monkeypatch):
        """Upbit API 키만 검증 (성공)"""
        # Given
        monkeypatch.setattr(APIConfig, 'UPBIT_ACCESS_KEY', 'test_access_key')
        monkeypatch.setattr(APIConfig, 'UPBIT_SECRET_KEY', 'test_secret_key')
        
        # When & Then - 에러가 발생하지 않아야 함
        APIConfig.validate_upbit_only()
    
    @pytest.mark.unit
    def test_validate_upbit_only_missing_keys(self, monkeypatch):
        """Upbit API 키 누락"""
        # Given
        monkeypatch.setattr(APIConfig, 'UPBIT_ACCESS_KEY', None)
        monkeypatch.setattr(APIConfig, 'UPBIT_SECRET_KEY', None)
        
        # Then
        with pytest.raises(ConfigurationError):
            APIConfig.validate_upbit_only()



