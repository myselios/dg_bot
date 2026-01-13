"""
ProductionObjectiveFunction - 상용화 목적 함수

비용 반영 필수:
- 수수료 차감
- 슬리피지 적용
- 유동성 페널티
"""

import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

import numpy as np

from src.domain.value_objects.cost_policy import CostPolicy

logger = logging.getLogger(__name__)


@dataclass
class ProductionObjectiveFunction:
    """
    상용화 목적 함수 (비용 반영 필수)

    목적:
    - 백테스트 수익이 아닌 "실거래 후 손에 남는 수익" 최대화
    - 비용/리스크 반영으로 과최적화 방지

    비용 모델:
    - 수수료 (fee_rate * 2: 매수+매도)
    - 슬리피지 (주문 크기/거래대금/변동성 기반)
    - 유동성 페널티 (거래대금 부족 시)
    """

    cost_policy: CostPolicy
    default_order_size: float = 100_000_000  # 기본 1억

    def calculate_net_return(self, result: Dict[str, Any]) -> float:
        """
        비용 차감 후 순수익률 계산

        Args:
            result: 백테스트 결과
                - gross_return: 비용 전 수익률
                - daily_volume: 일일 거래대금
                - volatility: 일일 변동성
                - order_size: 주문 금액 (선택)

        Returns:
            비용 차감 후 순수익률
        """
        gross_return = result.get('gross_return', 0.0)
        daily_volume = result.get('daily_volume', 100_000_000_000)
        volatility = result.get('volatility', 0.02)
        order_size = result.get('order_size', self.default_order_size)

        # 1. 수수료 차감 (매수 + 매도)
        fee_cost = gross_return * self.cost_policy.fee_rate * 2

        # 2. 슬리피지 계산
        slippage = self.cost_policy.calculate_slippage(
            order_size=order_size,
            daily_volume=daily_volume,
            volatility=volatility,
        )

        # 3. 유동성 페널티
        liquidity_penalty = self.cost_policy.calculate_liquidity_penalty(daily_volume)

        # 4. 순수익률
        net_return = gross_return - fee_cost - slippage - liquidity_penalty

        logger.debug(
            f"비용 계산: gross={gross_return:.4f}, "
            f"fee={fee_cost:.4f}, slippage={slippage:.4f}, "
            f"liquidity={liquidity_penalty:.4f}, net={net_return:.4f}"
        )

        return net_return

    def evaluate(
        self,
        backtest_results: List[Dict[str, Any]],
        total_candidates: Optional[int] = None,
    ) -> float:
        """
        목적 함수 평가

        목적:
        - 순수익률 최대화
        - Sharpe 조정
        - 선택률/드로다운 페널티

        Args:
            backtest_results: 백테스트 결과 리스트
            total_candidates: 전체 후보 수 (선택률 계산용)

        Returns:
            최종 목적 함수 값
        """
        if not backtest_results:
            return float('-inf')

        # 1. 비용 차감 후 순수익률 계산
        net_returns = [
            self.calculate_net_return(result)
            for result in backtest_results
        ]
        avg_net_return = np.mean(net_returns)

        # 2. Sharpe 조정 (상한 1.5)
        sharpe_values = [r.get('sharpe_ratio', 0.0) for r in backtest_results]
        avg_sharpe = np.mean(sharpe_values)
        sharpe_adj = min(avg_sharpe / 1.5, 1.5)

        # 3. 선택률 페널티 (10-30% 목표)
        if total_candidates:
            selection_rate = len(backtest_results) / total_candidates
        else:
            # pass_rate가 있으면 사용
            pass_rates = [r.get('pass_rate', 0.2) for r in backtest_results]
            selection_rate = np.mean(pass_rates)

        selection_penalty = self._calculate_selection_penalty(selection_rate)

        # 4. 드로다운 페널티 (20% 초과분)
        max_drawdowns = [r.get('max_drawdown', 0.0) for r in backtest_results]
        max_dd = max(max_drawdowns) if max_drawdowns else 0.0
        dd_penalty = max(0, (max_dd - 0.20))

        # 5. 최종 목적 함수
        objective = (
            avg_net_return * sharpe_adj * selection_rate
            - dd_penalty
            - selection_penalty
        )

        logger.debug(
            f"목적 함수: net_return={avg_net_return:.4f}, "
            f"sharpe_adj={sharpe_adj:.2f}, selection={selection_rate:.2f}, "
            f"dd_penalty={dd_penalty:.4f}, sel_penalty={selection_penalty:.4f}, "
            f"objective={objective:.4f}"
        )

        return objective

    def _calculate_selection_penalty(self, selection_rate: float) -> float:
        """
        선택률 페널티 계산

        목표: 10-30% 범위 유지

        Args:
            selection_rate: 선택률 (0-1)

        Returns:
            페널티 값
        """
        if selection_rate < 0.10:
            return (0.10 - selection_rate) * 2
        elif selection_rate > 0.30:
            return (selection_rate - 0.30) * 2
        return 0.0

    def calculate_risk_adjusted_return(
        self, result: Dict[str, Any]
    ) -> float:
        """
        리스크 조정 수익률 계산

        Sharpe-like 지표: (순수익률 / 변동성)

        Args:
            result: 백테스트 결과

        Returns:
            리스크 조정 수익률
        """
        net_return = self.calculate_net_return(result)
        volatility = result.get('volatility', 0.02)

        if volatility <= 0:
            return 0.0

        return net_return / volatility
