"""
거래 전략 인터페이스 및 신호 클래스
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime
import pandas as pd

if TYPE_CHECKING:
    from .portfolio import Portfolio


class Signal:
    """거래 신호"""
    
    def __init__(
        self,
        action: str,           # 'buy', 'sell', 'close'
        price: float,
        size: float = None,
        stop_loss: float = None,
        take_profit: float = None,
        reason: Dict[str, Any] = None,
        split_recommendation: Dict[str, Any] = None,  # 분할 주문 권장사항
        expected_slippage: float = None  # 예상 슬리피지 비율
    ):
        self.action = action
        self.price = price
        self.size = size
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.reason = reason or {}
        self.split_recommendation = split_recommendation
        self.expected_slippage = expected_slippage
        self.timestamp = datetime.now()


class Strategy(ABC):
    """
    거래 전략 추상 클래스
    """
    
    @abstractmethod
    def generate_signal(self, data: pd.DataFrame, portfolio: Optional['Portfolio'] = None) -> Optional[Signal]:
        """
        거래 신호 생성
        
        Args:
            data: 현재 시점까지의 차트 데이터
            portfolio: 포트폴리오 객체 (선택적, 백테스팅에서 전달됨)
            
        Returns:
            Signal 객체 또는 None
        """
        pass
    
    @abstractmethod
    def calculate_position_size(
        self, 
        signal: Signal, 
        portfolio: 'Portfolio'
    ) -> float:
        """
        포지션 크기 계산
        
        Args:
            signal: 거래 신호
            portfolio: 포트폴리오 객체
            
        Returns:
            포지션 크기 (코인 수량)
        """
        pass


