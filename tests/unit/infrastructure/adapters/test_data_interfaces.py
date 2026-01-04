"""
데이터 인터페이스 테스트
TDD 원칙: 인터페이스 정의를 검증합니다.
"""
import pytest
import pandas as pd
from src.data.interfaces import IDataProvider


class TestIDataProvider:
    """데이터 제공자 인터페이스 테스트"""
    
    @pytest.mark.unit
    def test_interface_cannot_be_instantiated(self):
        """추상 클래스는 직접 인스턴스화할 수 없음"""
        # Then
        with pytest.raises(TypeError):
            IDataProvider()
    
    @pytest.mark.unit
    def test_concrete_implementation(self):
        """구체 클래스 구현 테스트"""
        # Given
        class MockDataProvider(IDataProvider):
            """Mock 데이터 제공자"""
            
            def get_ohlcv(self, ticker: str, interval: str, count: int) -> pd.DataFrame:
                """Mock OHLCV 데이터 반환"""
                return pd.DataFrame({
                    'open': [100, 101],
                    'high': [102, 103],
                    'low': [99, 100],
                    'close': [101, 102],
                    'volume': [1000, 1100]
                })
        
        # When
        provider = MockDataProvider()
        result = provider.get_ohlcv("KRW-ETH", "day", 2)
        
        # Then
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert 'close' in result.columns
    
    @pytest.mark.unit
    def test_incomplete_implementation_raises_error(self):
        """추상 메서드를 구현하지 않으면 에러 발생"""
        # Given
        class IncompleteProvider(IDataProvider):
            """불완전한 구현"""
            pass
        
        # Then
        with pytest.raises(TypeError):
            IncompleteProvider()



