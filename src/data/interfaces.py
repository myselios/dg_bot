"""
데이터 제공자 인터페이스 정의
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict
import pandas as pd


class IDataProvider(ABC):
    """데이터 제공자 인터페이스"""
    
    @abstractmethod
    def get_ohlcv(
        self, 
        ticker: str, 
        interval: str, 
        count: int
    ) -> Optional[pd.DataFrame]:
        """
        OHLCV 데이터 조회
        
        Args:
            ticker: 거래 종목
            interval: 시간 간격 ('day', 'minute60', 'minute15' 등)
            count: 조회할 개수
            
        Returns:
            OHLCV DataFrame 또는 None
        """
        pass




