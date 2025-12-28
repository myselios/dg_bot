"""
API 인터페이스 정의
의존성 역전 원칙(DIP)을 위한 추상 인터페이스
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List


class IExchangeClient(ABC):
    """거래소 클라이언트 인터페이스"""
    
    @abstractmethod
    def get_balances(self) -> Optional[List[Dict[str, Any]]]:
        """전체 잔고 조회"""
        pass
    
    @abstractmethod
    def get_balance(self, currency: str) -> float:
        """특정 화폐 잔고 조회"""
        pass
    
    @abstractmethod
    def get_current_price(self, ticker: str) -> Optional[float]:
        """현재가 조회"""
        pass
    
    @abstractmethod
    def buy_market_order(self, ticker: str, amount: float) -> Optional[Dict[str, Any]]:
        """시장가 매수 주문"""
        pass
    
    @abstractmethod
    def sell_market_order(self, ticker: str, volume: float) -> Optional[Dict[str, Any]]:
        """시장가 매도 주문"""
        pass




