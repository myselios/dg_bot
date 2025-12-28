"""
Upbit API 클라이언트 래퍼
"""
import pyupbit
from typing import Optional, Dict, Any, List
from ..config.settings import APIConfig
from .interfaces import IExchangeClient
from ..exceptions import (
    APIError, AuthenticationError, RateLimitError, 
    OrderExecutionError, DataCollectionError
)


class UpbitClient(IExchangeClient):
    """Upbit API 래퍼 클래스"""
    
    def __init__(self):
        """Upbit 클라이언트 초기화"""
        try:
            APIConfig.validate()
            self.client = pyupbit.Upbit(
                APIConfig.UPBIT_ACCESS_KEY,
                APIConfig.UPBIT_SECRET_KEY
            )
        except Exception as e:
            raise AuthenticationError("Upbit", f"인증 정보 설정 실패: {str(e)}")
    
    def get_balances(self) -> Optional[List[Dict[str, Any]]]:
        """전체 잔고 조회"""
        try:
            return self.client.get_balances()
        except Exception as e:
            error_str = str(e).lower()
            if 'rate limit' in error_str or 'too many' in error_str or 'limit' in error_str:
                raise RateLimitError("Upbit", retry_after=getattr(e, 'retry_after', None))
            if 'unauthorized' in error_str or 'invalid' in error_str:
                raise AuthenticationError("Upbit", str(e))
            raise APIError("Upbit", reason=f"잔고 조회 실패: {str(e)}")
    
    def get_balance(self, currency: str) -> float:
        """특정 화폐 잔고 조회"""
        try:
            return self.client.get_balance(currency)
        except Exception as e:
            error_str = str(e).lower()
            if 'rate limit' in error_str or 'too many' in error_str or 'limit' in error_str:
                raise RateLimitError("Upbit", retry_after=getattr(e, 'retry_after', None))
            return 0.0
    
    def get_current_price(self, ticker: str) -> Optional[float]:
        """현재가 조회"""
        try:
            return pyupbit.get_current_price(ticker)
        except Exception as e:
            raise DataCollectionError("Upbit API", f"현재가 조회 실패: {str(e)}")
    
    def buy_market_order(self, ticker: str, amount: float) -> Optional[Dict[str, Any]]:
        """시장가 매수 주문"""
        try:
            return self.client.buy_market_order(ticker, amount)
        except Exception as e:
            error_msg = str(e).lower()
            if 'rate limit' in error_msg or 'too many' in error_msg or 'limit' in error_msg:
                raise RateLimitError("Upbit", retry_after=getattr(e, 'retry_after', None))
            if 'insufficient' in error_msg or 'balance' in error_msg:
                raise OrderExecutionError(ticker, "buy", "잔고 부족")
            raise OrderExecutionError(ticker, "buy", str(e))
    
    def sell_market_order(self, ticker: str, volume: float) -> Optional[Dict[str, Any]]:
        """시장가 매도 주문"""
        try:
            return self.client.sell_market_order(ticker, volume)
        except Exception as e:
            error_msg = str(e).lower()
            if 'rate limit' in error_msg or 'too many' in error_msg or 'limit' in error_msg:
                raise RateLimitError("Upbit", retry_after=getattr(e, 'retry_after', None))
            if 'insufficient' in error_msg or 'balance' in error_msg:
                raise OrderExecutionError(ticker, "sell", "보유량 부족")
            raise OrderExecutionError(ticker, "sell", str(e))

