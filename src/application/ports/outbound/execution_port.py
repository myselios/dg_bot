"""
ExecutionPort - 백테스팅 체결 포트 인터페이스

Clean Architecture: Application Layer (Outbound Port)

이 포트를 통해 다양한 체결 모델을 교체할 수 있습니다:
- SimpleExecutionAdapter: 기존 방식 (시가/종가 체결)
- IntrabarExecutionAdapter: 봉 내 스탑/익절 체결 (현실적)

주요 책임:
1. 시장가 주문 체결 시뮬레이션
2. 스탑로스/익절 트리거 확인
3. 실제 체결 가격 계산 (갭, 슬리피지 반영)
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from src.domain.entities import OrderSide
from src.domain.value_objects import Money, Currency


@dataclass(frozen=True)
class CandleData:
    """
    캔들 데이터 DTO

    백테스팅에서 사용되는 OHLCV 캔들 데이터.
    pandas DataFrame 의존성 제거를 위한 도메인 DTO.

    Attributes:
        timestamp: 캔들 시작 시간
        open: 시가
        high: 고가
        low: 저가
        close: 종가
        volume: 거래량
    """
    timestamp: datetime
    open: Money
    high: Money
    low: Money
    close: Money
    volume: Decimal

    @property
    def range(self) -> Money:
        """캔들 범위 (고가 - 저가)"""
        return self.high - self.low

    @property
    def body(self) -> Money:
        """캔들 몸통 (종가 - 시가의 절대값)"""
        diff = self.close.amount - self.open.amount
        return Money(abs(diff), self.close.currency)

    @property
    def is_bullish(self) -> bool:
        """상승 캔들 여부 (종가 > 시가)"""
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        """하락 캔들 여부 (종가 < 시가)"""
        return self.close < self.open

    @property
    def is_doji(self) -> bool:
        """도지 캔들 여부 (시가 ≈ 종가)"""
        return self.open == self.close

    @classmethod
    def from_dict(cls, data: dict, timestamp: datetime) -> CandleData:
        """딕셔너리에서 CandleData 생성"""
        return cls(
            timestamp=timestamp,
            open=Money.krw(data.get("open", 0)),
            high=Money.krw(data.get("high", 0)),
            low=Money.krw(data.get("low", 0)),
            close=Money.krw(data.get("close", 0)),
            volume=Decimal(str(data.get("volume", 0)))
        )

    @classmethod
    def from_pandas_row(cls, row, timestamp_col: str = "index") -> CandleData:
        """
        pandas Series (행)에서 CandleData 생성

        Args:
            row: pandas Series (df.iloc[i] 또는 df.iterrows()의 row)
            timestamp_col: 타임스탬프 컬럼명 또는 'index'

        Returns:
            CandleData 객체
        """
        if timestamp_col == "index":
            ts = row.name  # pandas index
        else:
            ts = row[timestamp_col]

        return cls(
            timestamp=ts,
            open=Money.krw(row["open"]),
            high=Money.krw(row["high"]),
            low=Money.krw(row["low"]),
            close=Money.krw(row["close"]),
            volume=Decimal(str(row["volume"]))
        )


@dataclass
class ExecutionResult:
    """
    체결 결과 DTO

    시장가 주문 또는 스탑/익절 체결 결과.

    Attributes:
        success: 체결 성공 여부
        executed_price: 실제 체결 가격
        executed_size: 체결 수량
        slippage: 슬리피지 금액
        timestamp: 체결 시간 (캔들 시간)
        failure_reason: 실패 이유 (실패 시)
    """
    success: bool
    executed_price: Optional[Money]
    executed_size: Optional[Decimal]
    slippage: Optional[Money]
    timestamp: datetime
    failure_reason: Optional[str] = None

    @classmethod
    def failed(cls, timestamp: datetime, reason: str) -> ExecutionResult:
        """실패한 체결 결과 생성"""
        return cls(
            success=False,
            executed_price=None,
            executed_size=None,
            slippage=None,
            timestamp=timestamp,
            failure_reason=reason
        )

    @classmethod
    def success_at(
        cls,
        price: Money,
        size: Decimal,
        slippage: Money,
        timestamp: datetime
    ) -> ExecutionResult:
        """성공한 체결 결과 생성"""
        return cls(
            success=True,
            executed_price=price,
            executed_size=size,
            slippage=slippage,
            timestamp=timestamp
        )


class ExecutionPort(ABC):
    """
    백테스팅 체결 포트 인터페이스

    다양한 체결 모델을 구현할 수 있는 추상 인터페이스.

    구현체:
    - SimpleExecutionAdapter: 기존 방식 (시가/종가 체결)
    - IntrabarExecutionAdapter: 봉 내 스탑/익절 체결

    사용 예:
    ```python
    class IntrabarExecutionAdapter(ExecutionPort):
        def check_stop_loss_triggered(self, stop_price, candle):
            # 캔들 저점이 스탑 가격 이하면 트리거
            return candle.low <= stop_price
    ```
    """

    @abstractmethod
    def execute_market_order(
        self,
        side: OrderSide,
        size: Decimal,
        expected_price: Money,
        candle: CandleData,
        slippage_pct: Decimal = Decimal("0.0001")
    ) -> ExecutionResult:
        """
        시장가 주문 체결 시뮬레이션

        Args:
            side: 주문 방향 (BUY/SELL)
            size: 주문 수량
            expected_price: 예상 체결가
            candle: 체결 시점 캔들 데이터
            slippage_pct: 슬리피지 비율 (기본 0.01%)

        Returns:
            ExecutionResult: 체결 결과
        """
        pass

    @abstractmethod
    def check_stop_loss_triggered(
        self,
        stop_price: Money,
        candle: CandleData
    ) -> bool:
        """
        스탑로스 트리거 확인

        캔들 내에서 스탑로스 가격에 도달했는지 확인.
        Intrabar 체결의 핵심 - 봉 마감 전에 스탑에 걸릴 수 있음.

        Args:
            stop_price: 스탑로스 가격
            candle: 현재 캔들 데이터

        Returns:
            bool: 트리거 여부
        """
        pass

    @abstractmethod
    def check_take_profit_triggered(
        self,
        take_profit_price: Money,
        candle: CandleData
    ) -> bool:
        """
        익절 트리거 확인

        캔들 내에서 익절 가격에 도달했는지 확인.

        Args:
            take_profit_price: 익절 가격
            candle: 현재 캔들 데이터

        Returns:
            bool: 트리거 여부
        """
        pass

    @abstractmethod
    def get_stop_loss_execution_price(
        self,
        stop_price: Money,
        candle: CandleData
    ) -> Money:
        """
        스탑로스 체결 가격 계산

        갭 하락 시 더 나쁜 가격(시가)으로 체결될 수 있음.

        Args:
            stop_price: 스탑로스 가격
            candle: 현재 캔들 데이터

        Returns:
            Money: 실제 체결 가격
        """
        pass

    @abstractmethod
    def get_take_profit_execution_price(
        self,
        take_profit_price: Money,
        candle: CandleData
    ) -> Money:
        """
        익절 체결 가격 계산

        갭 상승 시 더 좋은 가격(시가)으로 체결될 수 있음.

        Args:
            take_profit_price: 익절 가격
            candle: 현재 캔들 데이터

        Returns:
            Money: 실제 체결 가격
        """
        pass
