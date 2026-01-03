"""
TimeProviderPort - 시간 제공자 포트 인터페이스

Clean Architecture: Application Layer (Outbound Port)

백테스팅에서 datetime.now() 대신 캔들 시간을 사용하여
시간축 왜곡을 방지합니다.

구현체:
- CandleTimeAdapter: 캔들 시간 사용 (백테스팅용)
- SystemTimeAdapter: 시스템 시간 사용 (실거래용)
- FixedTimeAdapter: 고정 시간 (테스트용)
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.application.ports.outbound.execution_port import CandleData


class TimeProviderPort(ABC):
    """
    시간 제공자 포트 인터페이스

    datetime.now() 직접 호출을 제거하고, 의존성 주입으로
    시간 소스를 교체할 수 있게 합니다.
    """

    @abstractmethod
    def now(self) -> datetime:
        """현재 시간 반환"""
        pass

    @abstractmethod
    def from_candle(self, candle: CandleData) -> datetime:
        """캔들 데이터에서 시간 추출"""
        pass


class CandleTimeAdapter(TimeProviderPort):
    """
    캔들 시간 어댑터 (백테스팅용)

    현재 처리 중인 캔들의 시간을 반환합니다.
    datetime.now() 대신 캔들 시간을 사용하여 시간축 왜곡 방지.
    """

    def __init__(self):
        self._current_candle: Optional[CandleData] = None

    def set_current_candle(self, candle: CandleData) -> None:
        """현재 처리 중인 캔들 설정"""
        self._current_candle = candle

    def now(self) -> datetime:
        """
        현재 시간 반환

        현재 처리 중인 캔들의 시간을 반환합니다.
        캔들이 설정되지 않았으면 ValueError 발생.
        """
        if self._current_candle is None:
            raise ValueError("No candle set. Call set_current_candle() first.")
        return self._current_candle.timestamp

    def from_candle(self, candle: CandleData) -> datetime:
        """캔들 데이터에서 시간 추출"""
        return candle.timestamp


class SystemTimeAdapter(TimeProviderPort):
    """
    시스템 시간 어댑터 (실거래용)

    실제 시스템 시간을 반환합니다.
    """

    def now(self) -> datetime:
        """현재 시스템 시간 반환"""
        return datetime.now()

    def from_candle(self, candle: CandleData) -> datetime:
        """캔들 데이터에서 시간 추출"""
        return candle.timestamp


class FixedTimeAdapter(TimeProviderPort):
    """
    고정 시간 어댑터 (테스트용)

    테스트에서 예측 가능한 시간을 반환합니다.
    """

    def __init__(self, fixed_time: datetime):
        self._fixed_time = fixed_time

    def set_time(self, new_time: datetime) -> None:
        """시간 변경"""
        self._fixed_time = new_time

    def now(self) -> datetime:
        """고정된 시간 반환"""
        return self._fixed_time

    def from_candle(self, candle: CandleData) -> datetime:
        """캔들 데이터에서 시간 추출"""
        return candle.timestamp
