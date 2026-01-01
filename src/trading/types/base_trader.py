"""
트레이더 베이스 클래스

현물/선물 거래를 위한 추상 인터페이스

이 인터페이스를 통해 현물과 선물 거래의 공통 로직을 정의하고,
각 거래 타입별 특화 로직을 구현할 수 있습니다.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class Position:
    """
    포지션 정보

    Attributes:
        ticker: 거래 종목
        position_type: 포지션 타입 ('spot', 'long', 'short')
        size: 포지션 크기
        entry_price: 진입 가격
        current_price: 현재 가격
        unrealized_pnl: 미실현 손익
        unrealized_pnl_pct: 미실현 손익률 (%)
    """
    ticker: str
    position_type: str  # 'spot', 'long', 'short'
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


@dataclass
class OrderRequest:
    """
    주문 요청

    Attributes:
        ticker: 거래 종목
        side: 주문 방향 ('buy', 'sell', 'long', 'short', 'close')
        amount: 주문 수량 (선택)
        price: 주문 가격 (선택, 시장가는 None)
        order_type: 주문 타입 ('market', 'limit')
        leverage: 레버리지 (선물만, 기본 1)
    """
    ticker: str
    side: str  # 'buy', 'sell', 'long', 'short', 'close'
    amount: Optional[float] = None
    price: Optional[float] = None
    order_type: str = 'market'
    leverage: int = 1


@dataclass
class OrderResult:
    """
    주문 결과

    Attributes:
        success: 성공 여부
        order_id: 주문 ID
        ticker: 거래 종목
        side: 주문 방향
        amount: 체결 수량
        price: 체결 가격
        fee: 수수료
        total: 총 금액
        error: 에러 메시지 (실패 시)
    """
    success: bool
    order_id: Optional[str] = None
    ticker: Optional[str] = None
    side: Optional[str] = None
    amount: float = 0.0
    price: float = 0.0
    fee: float = 0.0
    total: float = 0.0
    error: Optional[str] = None


class BaseTrader(ABC):
    """
    트레이더 베이스 클래스

    현물/선물 거래를 위한 공통 인터페이스를 정의합니다.
    """

    @abstractmethod
    def get_position(self, ticker: str) -> Optional[Position]:
        """
        현재 포지션 조회

        Args:
            ticker: 거래 종목

        Returns:
            Position: 포지션 정보 (포지션 없으면 None)
        """
        pass

    @abstractmethod
    def execute_order(self, order: OrderRequest) -> OrderResult:
        """
        주문 실행

        Args:
            order: 주문 요청

        Returns:
            OrderResult: 주문 결과
        """
        pass

    @abstractmethod
    def calculate_fee(self, amount: float, price: float) -> float:
        """
        수수료 계산

        Args:
            amount: 수량
            price: 가격

        Returns:
            float: 수수료
        """
        pass

    @abstractmethod
    def get_available_balance(self, ticker: str) -> Dict[str, float]:
        """
        사용 가능한 잔고 조회

        Args:
            ticker: 거래 종목

        Returns:
            Dict: 잔고 정보
                - krw: 원화 잔고
                - coin: 코인 잔고
                - available_krw: 사용 가능 원화
                - available_coin: 사용 가능 코인
        """
        pass

    @abstractmethod
    def validate_order(self, order: OrderRequest) -> tuple[bool, str]:
        """
        주문 유효성 검증

        Args:
            order: 주문 요청

        Returns:
            tuple: (유효 여부, 오류 메시지)
        """
        pass

    def get_trading_type(self) -> str:
        """
        거래 타입 반환

        Returns:
            str: 'spot' 또는 'futures'
        """
        return self._trading_type

    def __init__(self, trading_type: str):
        """
        Args:
            trading_type: 거래 타입 ('spot' 또는 'futures')
        """
        self._trading_type = trading_type
