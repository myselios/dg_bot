"""
CalculateEntryAmountUseCase - 진입 금액 계산 비즈니스 로직

포트폴리오 상태를 조회하고, PositionSizingPolicy를 적용하여
특정 코인 진입 시 사용할 금액을 계산합니다.

클린 아키텍처 원칙:
- Application 레이어에 위치 (비즈니스 유스케이스)
- Domain의 PositionSizingPolicy 사용 (비즈니스 규칙)
- ExchangePort를 통해 인프라 접근 (의존성 역전)
"""
from decimal import Decimal
from typing import Optional, List

from src.application.ports.outbound.exchange_port import ExchangePort
from src.application.dto.trading import PositionInfo
from src.domain.value_objects.money import Money, Currency
from src.domain.value_objects.position_sizing import PositionSizingPolicy


class CalculateEntryAmountUseCase:
    """
    진입 금액 계산 UseCase

    포트폴리오 상태를 조회하고, 포지션 사이징 정책에 따라
    신규 진입 시 사용할 금액을 계산합니다.

    사용 예시:
        use_case = CalculateEntryAmountUseCase(exchange_port)
        entry_amount = await use_case.execute("KRW-BTC")
        if entry_amount.is_positive():
            # 진입 가능
            await trade_use_case.execute_buy("KRW-BTC", entry_amount)

    Attributes:
        exchange: 거래소 포트 (잔고/포지션 조회)
        policy: 포지션 사이징 정책
    """

    def __init__(
        self,
        exchange: ExchangePort,
        policy: Optional[PositionSizingPolicy] = None,
    ):
        """
        UseCase 초기화

        Args:
            exchange: 거래소 포트 (잔고/포지션 조회)
            policy: 포지션 사이징 정책 (None이면 기본 정책 사용)
        """
        self._exchange = exchange
        self._policy = policy or PositionSizingPolicy.default()

    async def execute(self, ticker: str) -> Money:
        """
        특정 코인 진입 시 매수 금액 계산

        흐름:
        1. KRW 잔고 조회
        2. 모든 포지션 조회
        3. 총 자본 계산 (현금 + 투자금 평가액)
        4. 현재 포지션 수 확인 (해당 티커 제외)
        5. PositionSizingPolicy로 진입 금액 계산

        Args:
            ticker: 진입할 코인 티커 (예: "KRW-BTC")

        Returns:
            진입 가능 금액 (Money). 진입 불가 시 0
        """
        # 1. KRW 잔고 조회
        krw_balance = await self._exchange.get_balance("KRW")
        current_krw = krw_balance.available.amount

        # 2. 모든 포지션 조회
        positions = await self._exchange.get_all_positions()

        # 3. 총 자본 계산
        total_capital = await self._calculate_total_capital(current_krw, positions)

        # 4. 현재 포지션 수 (해당 티커가 이미 있으면 제외하지 않음 - 추가 매수 불가)
        position_count = len(positions)

        # 해당 티커의 포지션이 이미 있는지 확인
        if self._has_position(ticker, positions):
            # 이미 해당 코인 보유 중이면 추가 매수 금액 0
            return Money.zero(Currency.KRW)

        # 5. 정책에 따른 진입 금액 계산
        entry_amount = self._policy.calculate_entry_amount(
            total_capital=total_capital,
            current_krw=current_krw,
            current_position_count=position_count,
        )

        return Money(entry_amount, Currency.KRW)

    async def execute_with_details(self, ticker: str) -> dict:
        """
        진입 금액 계산 + 상세 정보 반환

        디버깅 및 로깅 목적으로 계산 과정의 상세 정보를 함께 반환합니다.

        Args:
            ticker: 진입할 코인 티커

        Returns:
            상세 정보 딕셔너리:
            - entry_amount: Money (진입 금액)
            - current_krw: Decimal (현재 KRW 잔고)
            - total_capital: Decimal (총 자본)
            - position_count: int (현재 포지션 수)
            - remaining_slots: int (남은 슬롯 수)
            - can_enter: bool (진입 가능 여부)
            - policy: PositionSizingPolicy (적용된 정책)
        """
        # KRW 잔고 조회
        krw_balance = await self._exchange.get_balance("KRW")
        current_krw = krw_balance.available.amount

        # 모든 포지션 조회
        positions = await self._exchange.get_all_positions()

        # 총 자본 계산
        total_capital = await self._calculate_total_capital(current_krw, positions)

        # 포지션 수
        position_count = len(positions)
        has_ticker = self._has_position(ticker, positions)

        # 진입 금액 계산
        if has_ticker:
            entry_amount = Decimal("0")
        else:
            entry_amount = self._policy.calculate_entry_amount(
                total_capital=total_capital,
                current_krw=current_krw,
                current_position_count=position_count,
            )

        return {
            "entry_amount": Money(entry_amount, Currency.KRW),
            "current_krw": current_krw,
            "total_capital": total_capital,
            "position_count": position_count,
            "remaining_slots": self._policy.remaining_slots(position_count),
            "can_enter": entry_amount > Decimal("0") and not has_ticker,
            "has_ticker_position": has_ticker,
            "policy": self._policy,
        }

    async def can_open_position(self, ticker: str) -> bool:
        """
        포지션 진입 가능 여부 확인

        Args:
            ticker: 확인할 코인 티커

        Returns:
            진입 가능 여부
        """
        entry_amount = await self.execute(ticker)
        return entry_amount.is_positive()

    async def _calculate_total_capital(
        self,
        current_krw: Decimal,
        positions: List[PositionInfo],
    ) -> Decimal:
        """
        총 자본 계산 (현금 + 투자금 평가액)

        Args:
            current_krw: 현재 KRW 잔고
            positions: 포지션 목록

        Returns:
            총 자본
        """
        total = current_krw

        for position in positions:
            # 포지션의 현재 평가액 계산
            if position.current_value:
                total += position.current_value.amount
            elif position.volume > 0:
                # current_value가 없으면 현재가로 계산
                try:
                    current_price = await self._exchange.get_current_price(
                        position.ticker
                    )
                    total += current_price.amount * position.volume
                except Exception:
                    # 가격 조회 실패 시 매수가로 추정
                    if position.avg_buy_price:
                        total += position.avg_buy_price.amount * position.volume

        return total

    def _has_position(self, ticker: str, positions: List[PositionInfo]) -> bool:
        """
        특정 티커의 포지션 보유 여부 확인

        Args:
            ticker: 확인할 티커
            positions: 포지션 목록

        Returns:
            보유 여부
        """
        for position in positions:
            if position.ticker == ticker and position.volume > Decimal("0"):
                return True
        return False

    @property
    def policy(self) -> PositionSizingPolicy:
        """현재 적용된 정책 반환"""
        return self._policy

    def with_policy(self, policy: PositionSizingPolicy) -> "CalculateEntryAmountUseCase":
        """
        새로운 정책으로 UseCase 복사본 생성

        Args:
            policy: 새로운 정책

        Returns:
            새로운 UseCase 인스턴스
        """
        return CalculateEntryAmountUseCase(
            exchange=self._exchange,
            policy=policy,
        )
