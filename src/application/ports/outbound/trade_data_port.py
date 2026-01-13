"""
TradeDataPort - ML 데이터 저장 포트

백테스트 필터 스냅샷 및 거래 결과를 저장하는 포트 인터페이스
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime

from src.domain.entities.ml_snapshot import BacktestFilterSnapshot, TradeOutcome


class TradeDataPort(ABC):
    """
    ML 데이터 저장 포트

    BacktestFilterSnapshot과 TradeOutcome을 저장하고 조회하는 인터페이스.
    구현체는 Parquet, PostgreSQL 등 다양한 저장소를 사용할 수 있다.
    """

    @abstractmethod
    def save_snapshot(self, snapshot: BacktestFilterSnapshot) -> None:
        """
        백테스트 필터 스냅샷 저장

        Args:
            snapshot: 저장할 스냅샷
        """
        pass

    @abstractmethod
    def save_snapshots(self, snapshots: List[BacktestFilterSnapshot]) -> None:
        """
        백테스트 필터 스냅샷 일괄 저장

        Args:
            snapshots: 저장할 스냅샷 리스트
        """
        pass

    @abstractmethod
    def save_outcome(self, outcome: TradeOutcome) -> None:
        """
        거래 결과 저장

        Args:
            outcome: 저장할 거래 결과
        """
        pass

    @abstractmethod
    def save_outcomes(self, outcomes: List[TradeOutcome]) -> None:
        """
        거래 결과 일괄 저장

        Args:
            outcomes: 저장할 거래 결과 리스트
        """
        pass

    @abstractmethod
    def get_snapshot_by_id(self, snapshot_id: str) -> Optional[BacktestFilterSnapshot]:
        """
        스냅샷 ID로 조회

        Args:
            snapshot_id: 스냅샷 ID

        Returns:
            스냅샷 또는 None
        """
        pass

    @abstractmethod
    def get_snapshots_by_ticker(
        self, ticker: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> List[BacktestFilterSnapshot]:
        """
        종목별 스냅샷 조회

        Args:
            ticker: 종목 코드
            start_date: 시작일 (선택)
            end_date: 종료일 (선택)

        Returns:
            스냅샷 리스트
        """
        pass

    @abstractmethod
    def get_outcomes_by_snapshot_id(self, snapshot_id: str) -> List[TradeOutcome]:
        """
        스냅샷 ID로 연결된 거래 결과 조회

        Args:
            snapshot_id: 스냅샷 ID

        Returns:
            거래 결과 리스트
        """
        pass

    @abstractmethod
    def get_all_snapshots(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> List[BacktestFilterSnapshot]:
        """
        전체 스냅샷 조회

        Args:
            start_date: 시작일 (선택)
            end_date: 종료일 (선택)

        Returns:
            스냅샷 리스트
        """
        pass

    @abstractmethod
    def get_all_outcomes(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> List[TradeOutcome]:
        """
        전체 거래 결과 조회

        Args:
            start_date: 시작일 (선택)
            end_date: 종료일 (선택)

        Returns:
            거래 결과 리스트
        """
        pass

    @abstractmethod
    def count_snapshots(self) -> int:
        """스냅샷 총 개수 조회"""
        pass

    @abstractmethod
    def count_outcomes(self) -> int:
        """거래 결과 총 개수 조회"""
        pass
