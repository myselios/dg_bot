"""
거래 실행자 인터페이스
실전 거래와 백테스팅을 추상화
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class TradeResult:
    """거래 실행 결과"""
    success: bool
    ticker: str
    order_type: str  # 'buy' or 'sell'
    price: float
    volume: Optional[float] = None
    amount: Optional[float] = None
    fee: float = 0.0
    order_id: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: Optional[str] = None


class TradeExecutor(ABC):
    """거래 실행 추상 인터페이스"""
    
    @abstractmethod
    def execute_buy(
        self, 
        ticker: str, 
        amount: float
    ) -> TradeResult:
        """
        매수 실행
        
        Args:
            ticker: 거래 종목
            amount: 매수 금액
            
        Returns:
            TradeResult 객체
        """
        pass
    
    @abstractmethod
    def execute_sell(
        self, 
        ticker: str, 
        volume: float
    ) -> TradeResult:
        """
        매도 실행
        
        Args:
            ticker: 거래 종목
            volume: 매도 수량
            
        Returns:
            TradeResult 객체
        """
        pass
    
    @abstractmethod
    def get_balance(self, currency: str) -> float:
        """
        잔고 조회
        
        Args:
            currency: 통화 (예: 'KRW', 'ETH')
            
        Returns:
            잔고 금액
        """
        pass
    
    @abstractmethod
    def get_current_price(self, ticker: str) -> Optional[float]:
        """
        현재가 조회
        
        Args:
            ticker: 거래 종목
            
        Returns:
            현재가 또는 None
        """
        pass




