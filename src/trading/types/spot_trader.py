"""
현물 트레이더

현물 거래 로직 구현
"""
from typing import Dict, Optional
from src.trading.types.base_trader import (
    BaseTrader,
    Position,
    OrderRequest,
    OrderResult
)
from src.api.upbit_client import UpbitClient
from src.position.service import PositionService


class SpotTrader(BaseTrader):
    """
    현물 트레이더

    Upbit 현물 거래를 위한 트레이더 구현
    """

    def __init__(self, upbit_client: UpbitClient):
        """
        Args:
            upbit_client: Upbit 클라이언트
        """
        super().__init__(trading_type='spot')
        self.client = upbit_client
        self.position_service = PositionService(upbit_client)

    def get_position(self, ticker: str) -> Optional[Position]:
        """
        현재 포지션 조회

        Args:
            ticker: 거래 종목

        Returns:
            Position: 포지션 정보 (포지션 없으면 None)
        """
        position_info = self.position_service.get_detailed_position(ticker)

        if not position_info or position_info.get('balance', 0) <= 0:
            return None

        current_price = self.client.get_current_price(ticker)
        avg_buy_price = position_info.get('avg_buy_price', 0)
        balance = position_info.get('balance', 0)

        if avg_buy_price > 0 and current_price:
            unrealized_pnl = (current_price - avg_buy_price) * balance
            unrealized_pnl_pct = ((current_price - avg_buy_price) / avg_buy_price) * 100
        else:
            unrealized_pnl = 0.0
            unrealized_pnl_pct = 0.0

        return Position(
            ticker=ticker,
            position_type='spot',
            size=balance,
            entry_price=avg_buy_price,
            current_price=current_price or 0.0,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_pct=unrealized_pnl_pct
        )

    def execute_order(self, order: OrderRequest) -> OrderResult:
        """
        주문 실행

        Args:
            order: 주문 요청

        Returns:
            OrderResult: 주문 결과
        """
        # 주문 유효성 검증
        is_valid, error_msg = self.validate_order(order)
        if not is_valid:
            return OrderResult(
                success=False,
                error=error_msg
            )

        try:
            # 현물은 buy/sell만 지원
            if order.side == 'buy':
                return self._execute_buy(order)
            elif order.side == 'sell':
                return self._execute_sell(order)
            else:
                return OrderResult(
                    success=False,
                    error=f"현물 거래는 '{order.side}' 주문을 지원하지 않습니다."
                )

        except Exception as e:
            return OrderResult(
                success=False,
                error=f"주문 실행 오류: {str(e)}"
            )

    def _execute_buy(self, order: OrderRequest) -> OrderResult:
        """
        매수 실행

        Args:
            order: 주문 요청

        Returns:
            OrderResult: 주문 결과
        """
        # TradingService의 execute_buy 로직 사용
        # 간단한 구현 (실제로는 TradingService와 통합 필요)
        krw_balance = self.client.get_balance("KRW")
        current_price = self.client.get_current_price(order.ticker)

        if not current_price:
            return OrderResult(
                success=False,
                error="현재 가격을 가져올 수 없습니다."
            )

        # 최소 거래 금액 체크
        min_trade_amount = 5000
        if krw_balance < min_trade_amount:
            return OrderResult(
                success=False,
                error=f"잔고 부족: {krw_balance:,.0f}원 (최소 {min_trade_amount:,}원 필요)"
            )

        # 수수료 계산
        fee = self.calculate_fee(krw_balance, current_price)
        buy_amount = (krw_balance - fee) / current_price

        # 실제 주문 실행 (여기서는 시뮬레이션)
        # TODO: 실제 Upbit API 호출로 교체
        return OrderResult(
            success=True,
            order_id="simulated_order_id",
            ticker=order.ticker,
            side='buy',
            amount=buy_amount,
            price=current_price,
            fee=fee,
            total=krw_balance
        )

    def _execute_sell(self, order: OrderRequest) -> OrderResult:
        """
        매도 실행

        Args:
            order: 주문 요청

        Returns:
            OrderResult: 주문 결과
        """
        coin_balance = self.client.get_balance(order.ticker)
        current_price = self.client.get_current_price(order.ticker)

        if not current_price:
            return OrderResult(
                success=False,
                error="현재 가격을 가져올 수 없습니다."
            )

        if coin_balance <= 0:
            return OrderResult(
                success=False,
                error="보유한 코인이 없습니다."
            )

        # 수수료 계산
        total = coin_balance * current_price
        fee = self.calculate_fee(coin_balance, current_price)

        # 실제 주문 실행 (여기서는 시뮬레이션)
        # TODO: 실제 Upbit API 호출로 교체
        return OrderResult(
            success=True,
            order_id="simulated_order_id",
            ticker=order.ticker,
            side='sell',
            amount=coin_balance,
            price=current_price,
            fee=fee,
            total=total - fee
        )

    def calculate_fee(self, amount: float, price: float) -> float:
        """
        수수료 계산 (Upbit 현물 거래 수수료: 0.05%)

        Args:
            amount: 수량
            price: 가격

        Returns:
            float: 수수료
        """
        fee_rate = 0.0005  # 0.05%
        return amount * price * fee_rate

    def get_available_balance(self, ticker: str) -> Dict[str, float]:
        """
        사용 가능한 잔고 조회

        Args:
            ticker: 거래 종목

        Returns:
            Dict: 잔고 정보
        """
        krw_balance = self.client.get_balance("KRW")
        coin_balance = self.client.get_balance(ticker)

        return {
            'krw': krw_balance,
            'coin': coin_balance,
            'available_krw': krw_balance,
            'available_coin': coin_balance
        }

    def validate_order(self, order: OrderRequest) -> tuple[bool, str]:
        """
        주문 유효성 검증

        Args:
            order: 주문 요청

        Returns:
            tuple: (유효 여부, 오류 메시지)
        """
        # 현물은 레버리지 사용 불가
        if order.leverage != 1:
            return False, "현물 거래는 레버리지를 사용할 수 없습니다."

        # 주문 방향 체크
        if order.side not in ['buy', 'sell']:
            return False, f"현물 거래는 '{order.side}' 주문을 지원하지 않습니다."

        # 매수 시 잔고 체크
        if order.side == 'buy':
            balance = self.get_available_balance(order.ticker)
            if balance['available_krw'] < 5000:
                return False, "매수 가능 잔고 부족 (최소 5,000원 필요)"

        # 매도 시 보유 코인 체크
        if order.side == 'sell':
            balance = self.get_available_balance(order.ticker)
            if balance['available_coin'] <= 0:
                return False, "매도할 코인이 없습니다."

        return True, ""
