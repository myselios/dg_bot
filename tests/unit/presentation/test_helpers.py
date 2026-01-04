"""
유틸리티 함수 테스트
"""
import pytest
import pandas as pd
from src.utils.helpers import df_to_json_dict, format_price, format_percentage, safe_json_dumps


class TestHelpers:
    """유틸리티 함수 테스트"""
    
    def test_df_to_json_dict(self, sample_chart_data):
        """DataFrame to JSON dict 변환 테스트"""
        result = df_to_json_dict(sample_chart_data)
        
        assert isinstance(result, dict)
        assert len(result) == len(sample_chart_data)
        # 모든 키는 문자열
        assert all(isinstance(k, str) for k in result.keys())
        # 모든 값은 딕셔너리
        assert all(isinstance(v, dict) for v in result.values())
    
    def test_format_price(self):
        """가격 포맷팅 테스트"""
        assert format_price(1000) == "1,000원"
        assert format_price(1234567) == "1,234,567원"
        assert format_price(0) == "0원"
    
    def test_format_percentage(self):
        """퍼센트 포맷팅 테스트"""
        assert "+5.00%" in format_percentage(5.0)
        assert "-3.50%" in format_percentage(-3.5)
        assert format_percentage(0) == "+0.00%"
    
    def test_safe_json_dumps(self):
        """안전한 JSON 직렬화 테스트"""
        data = {"key": "value", "number": 123}
        result = safe_json_dumps(data)
        
        assert isinstance(result, str)
        assert "key" in result
        assert "value" in result
        
        # datetime 객체도 처리 가능해야 함
        import datetime
        data_with_date = {"date": datetime.datetime.now()}
        result2 = safe_json_dumps(data_with_date)
        assert isinstance(result2, str)

