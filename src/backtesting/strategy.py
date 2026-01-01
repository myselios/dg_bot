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

    def prepare_indicators(self, data: pd.DataFrame) -> None:
        """
        지표 사전 계산 (Vectorization)

        백테스트 시작 전에 한 번만 호출되어 전체 데이터에 대해 지표를 계산합니다.
        이렇게 하면 루프 안에서 매번 지표를 재계산하는 O(N²) 비효율을 방지합니다.

        Args:
            data: 전체 과거 데이터

        Note:
            기본 구현은 빈 메서드입니다.
            하위 클래스에서 필요에 따라 오버라이드하세요.
        """
        pass  # 기본 구현: 아무것도 하지 않음

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


