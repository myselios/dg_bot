"""
유틸리티 함수
"""
import json
from typing import Dict, Any
import pandas as pd


def df_to_json_dict(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """
    DataFrame을 JSON 직렬화 가능한 딕셔너리로 변환
    
    Args:
        df: 변환할 DataFrame
        
    Returns:
        인덱스를 문자열 키로 하는 딕셔너리
    """
    return {
        str(idx): {
            col: float(val) if isinstance(val, (int, float)) else str(val)
            for col, val in row.items()
        }
        for idx, row in df.iterrows()
    }


def format_price(price: float) -> str:
    """가격 포맷팅"""
    return f"{price:,.0f}원"


def format_percentage(value: float) -> str:
    """퍼센트 포맷팅"""
    return f"{value:+.2f}%"


def safe_json_dumps(data: Any, **kwargs) -> str:
    """안전한 JSON 직렬화"""
    return json.dumps(data, indent=2, default=str, **kwargs)

