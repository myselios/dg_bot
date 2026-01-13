"""
Constraints - 제약 조건 정의

최적화 결과의 유효성을 검증하는 제약 조건:
- 선택률 범위 (10-30%)
- 최소 거래 수 (20건)
- 최대 낙폭 (30%)
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Constraints:
    """
    최적화 제약 조건

    모든 제약 조건은 배포 전 품질 게이트로 작용한다.
    """

    # 선택률 범위 (10-30%)
    selection_rate_range: Tuple[float, float] = (0.10, 0.30)

    # 최소 거래 수 (신뢰도 확보)
    min_trades_threshold: int = 20

    # 최대 낙폭 제한
    max_drawdown_limit: float = 0.30

    # 최소 일일 거래대금 (유동성 확보)
    min_daily_volume: float = 10_000_000_000  # 100억

    # Sharpe Ratio 최소값
    min_sharpe_ratio: float = 0.5

    # 오탐율 최대값 (통과했지만 손실)
    max_false_positive_rate: float = 0.25

    def is_valid_selection_rate(self, rate: float) -> bool:
        """
        선택률 유효성 검증

        Args:
            rate: 선택률 (0-1)

        Returns:
            유효 여부
        """
        min_rate, max_rate = self.selection_rate_range
        return min_rate <= rate <= max_rate

    def is_valid_min_trades(self, trades: int) -> bool:
        """
        최소 거래 수 검증

        Args:
            trades: 거래 수

        Returns:
            유효 여부
        """
        return trades >= self.min_trades_threshold

    def is_valid_max_drawdown(self, drawdown: float) -> bool:
        """
        최대 낙폭 검증

        Args:
            drawdown: 최대 낙폭 (0-1)

        Returns:
            유효 여부
        """
        return drawdown <= self.max_drawdown_limit

    def is_valid_sharpe_ratio(self, sharpe: float) -> bool:
        """
        Sharpe Ratio 검증

        Args:
            sharpe: Sharpe Ratio

        Returns:
            유효 여부
        """
        return sharpe >= self.min_sharpe_ratio

    def is_valid_daily_volume(self, volume: float) -> bool:
        """
        일일 거래대금 검증

        Args:
            volume: 일일 거래대금 (KRW)

        Returns:
            유효 여부
        """
        return volume >= self.min_daily_volume

    def is_valid_false_positive_rate(self, fpr: float) -> bool:
        """
        오탐율 검증

        Args:
            fpr: 오탐율 (0-1)

        Returns:
            유효 여부
        """
        return fpr <= self.max_false_positive_rate

    def validate_all(self, result: Dict[str, Any]) -> bool:
        """
        전체 제약 조건 검증

        Args:
            result: 검증할 결과
                - selection_rate: 선택률
                - total_trades: 거래 수
                - max_drawdown: 최대 낙폭

        Returns:
            모든 조건 충족 여부
        """
        # 필수 필드 검증
        selection_rate = result.get('selection_rate')
        total_trades = result.get('total_trades')
        max_drawdown = result.get('max_drawdown')

        validations = []

        # 선택률
        if selection_rate is not None:
            validations.append(
                ('selection_rate', self.is_valid_selection_rate(selection_rate))
            )

        # 거래 수
        if total_trades is not None:
            validations.append(
                ('total_trades', self.is_valid_min_trades(total_trades))
            )

        # 최대 낙폭
        if max_drawdown is not None:
            validations.append(
                ('max_drawdown', self.is_valid_max_drawdown(max_drawdown))
            )

        # Sharpe (선택적)
        sharpe = result.get('sharpe_ratio')
        if sharpe is not None:
            validations.append(
                ('sharpe_ratio', self.is_valid_sharpe_ratio(sharpe))
            )

        # 거래대금 (선택적)
        volume = result.get('daily_volume')
        if volume is not None:
            validations.append(
                ('daily_volume', self.is_valid_daily_volume(volume))
            )

        # 오탐율 (선택적)
        fpr = result.get('false_positive_rate')
        if fpr is not None:
            validations.append(
                ('false_positive_rate', self.is_valid_false_positive_rate(fpr))
            )

        # 모든 검증 결과 확인
        all_valid = all(valid for _, valid in validations)

        if not all_valid:
            failed = [name for name, valid in validations if not valid]
            logger.warning(f"제약 조건 위반: {failed}")

        return all_valid

    def get_violation_details(self, result: Dict[str, Any]) -> Dict[str, str]:
        """
        제약 조건 위반 상세 정보

        Args:
            result: 검증할 결과

        Returns:
            위반된 제약 조건과 이유
        """
        violations = {}

        selection_rate = result.get('selection_rate')
        if selection_rate is not None and not self.is_valid_selection_rate(selection_rate):
            min_r, max_r = self.selection_rate_range
            violations['selection_rate'] = (
                f"범위 위반: {selection_rate:.2%} (허용: {min_r:.0%}-{max_r:.0%})"
            )

        total_trades = result.get('total_trades')
        if total_trades is not None and not self.is_valid_min_trades(total_trades):
            violations['total_trades'] = (
                f"최소 미달: {total_trades}건 (최소: {self.min_trades_threshold}건)"
            )

        max_drawdown = result.get('max_drawdown')
        if max_drawdown is not None and not self.is_valid_max_drawdown(max_drawdown):
            violations['max_drawdown'] = (
                f"한도 초과: {max_drawdown:.1%} (한도: {self.max_drawdown_limit:.0%})"
            )

        sharpe = result.get('sharpe_ratio')
        if sharpe is not None and not self.is_valid_sharpe_ratio(sharpe):
            violations['sharpe_ratio'] = (
                f"최소 미달: {sharpe:.2f} (최소: {self.min_sharpe_ratio:.1f})"
            )

        volume = result.get('daily_volume')
        if volume is not None and not self.is_valid_daily_volume(volume):
            violations['daily_volume'] = (
                f"최소 미달: {volume/1e9:.1f}억 (최소: {self.min_daily_volume/1e9:.0f}억)"
            )

        fpr = result.get('false_positive_rate')
        if fpr is not None and not self.is_valid_false_positive_rate(fpr):
            violations['false_positive_rate'] = (
                f"한도 초과: {fpr:.1%} (한도: {self.max_false_positive_rate:.0%})"
            )

        return violations
