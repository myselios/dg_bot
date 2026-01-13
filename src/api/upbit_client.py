"""
Upbit API 클라이언트 래퍼
"""
import pyupbit
import time
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
    
    def get_current_price(self, ticker: str, max_retries: int = 3) -> Optional[float]:
        """
        현재가 조회 (재시도 로직 포함)

        Args:
            ticker: 조회할 티커 (예: "KRW-BTC")
            max_retries: 최대 재시도 횟수 (기본 3회)

        Returns:
            현재가 또는 None (모든 재시도 실패 시)

        Raises:
            DataCollectionError: 모든 재시도 실패 후
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                price = pyupbit.get_current_price(ticker)

                # 유효성 검증: 0 또는 None은 실패로 간주
                if price is None or price <= 0:
                    raise ValueError(f"Invalid price: {price}")

                return price

            except Exception as e:
                last_error = e

                # 마지막 시도가 아니면 재시도
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1초, 2초, 4초
                    time.sleep(wait_time)
                    continue

        # 모든 재시도 실패
        raise DataCollectionError(
            "Upbit API",
            f"현재가 조회 실패 (재시도 {max_retries}회): {str(last_error)}"
        )

    def get_orderbook(self, ticker: str) -> Optional[Dict[str, Any]]:
        """호가창 조회"""
        try:
            orderbooks = pyupbit.get_orderbook(ticker)
            # 다양한 응답 형식 처리
            if orderbooks is None:
                return {"orderbook_units": [], "total_ask_size": 0, "total_bid_size": 0}
            if isinstance(orderbooks, list) and len(orderbooks) > 0:
                return orderbooks[0]
            if isinstance(orderbooks, dict):
                return orderbooks
            # 빈 응답 처리
            return {"orderbook_units": [], "total_ask_size": 0, "total_bid_size": 0}
        except Exception as e:
            # 에러 시에도 빈 호가창 반환 (전체 파이프라인 중단 방지)
            return {"orderbook_units": [], "total_ask_size": 0, "total_bid_size": 0}
    
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

