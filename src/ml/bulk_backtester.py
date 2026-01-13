"""
BulkBacktester - 대량 백테스트 실행기

다양한 Config 조합으로 백테스트를 실행하고 ML 학습용 스냅샷을 생성한다.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set, Any
from pathlib import Path
import random
import itertools

import pandas as pd
import numpy as np

from src.domain.value_objects.cost_policy import CostPolicy
from src.domain.value_objects.reproducibility_metadata import ReproducibilityMetadata
from src.domain.entities.ml_snapshot import BacktestFilterSnapshot

logger = logging.getLogger(__name__)


# 탐색 공간 정의 (PLAN 문서 기준)
WEIGHT_RANGES = {
    "max_drawdown": (0.5, 3.0),
    "sortino_ratio": (0.5, 2.5),
    "win_rate": (0.25, 1.5),
    "calmar_ratio": (0.5, 2.0),
    "avg_win_loss_ratio": (0.25, 1.0),
    "max_consecutive_losses": (0.25, 1.0),
    "volatility": (0.0, 1.0),
    "avg_holding_hours": (0.0, 1.0),
}

THRESHOLD_RANGES = {
    "min_return": (5.0, 15.0),
    "min_sharpe_ratio": (0.4, 1.2),
    "min_profit_factor": (1.2, 2.0),
    "min_trades": (15, 50),  # 정수
    "max_drawdown": (15.0, 35.0),
}

THRESHOLD_RATIO_RANGE = (0.50, 0.85)

# Tier 1 필터 후보 (return과 sharpe_ratio는 필수)
TIER1_CANDIDATES = {
    "return",
    "profit_factor",
    "sharpe_ratio",
    "expectancy",
    "max_drawdown",
    "sortino_ratio",
}

REQUIRED_TIER1 = {"return", "sharpe_ratio"}


class BulkBacktester:
    """
    대량 백테스트 실행기

    다양한 FilterConfig 조합으로 백테스트를 실행하고
    ML 학습용 스냅샷을 생성한다.
    """

    def __init__(self, data_path: str, cost_policy: CostPolicy):
        """
        Args:
            data_path: 데이터 저장 경로
            cost_policy: 비용 정책
        """
        self.data_path = Path(data_path)
        self.cost_policy = cost_policy
        self.data_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"BulkBacktester 초기화: {data_path}")

    def generate_config_variations(self, n_variations: int = 50) -> List[Dict]:
        """
        Config 변형 생성 (Latin Hypercube Sampling 기반)

        Args:
            n_variations: 생성할 변형 수

        Returns:
            Config 딕셔너리 리스트
        """
        configs = []

        for _ in range(n_variations):
            config = self._generate_single_config()
            configs.append(config)

        logger.info(f"{n_variations}개 Config 변형 생성 완료")
        return configs

    def _generate_single_config(self) -> Dict:
        """단일 Config 생성"""
        # threshold_ratio (비율만 사용)
        threshold_ratio = random.uniform(*THRESHOLD_RATIO_RANGE)

        # filter_weights (min_trades 제외)
        filter_weights = {}
        for key, (min_val, max_val) in WEIGHT_RANGES.items():
            filter_weights[key] = random.uniform(min_val, max_val)

        # thresholds (min_trades 포함)
        thresholds = {}
        for key, (min_val, max_val) in THRESHOLD_RANGES.items():
            if key == "min_trades":
                thresholds[key] = random.randint(int(min_val), int(max_val))
            else:
                thresholds[key] = random.uniform(min_val, max_val)

        # tier1_filters (return, sharpe_ratio 필수 + 추가 1-3개)
        tier1_filters = set(REQUIRED_TIER1)
        optional = TIER1_CANDIDATES - REQUIRED_TIER1
        n_additional = random.randint(1, 3)
        tier1_filters.update(random.sample(list(optional), min(n_additional, len(optional))))

        return {
            "threshold_ratio": threshold_ratio,
            "filter_weights": filter_weights,
            "thresholds": thresholds,
            "tier1_filters": tier1_filters,
        }

    def run_single_backtest(
        self,
        ticker: str,
        data: pd.DataFrame,
        config: Dict,
    ) -> BacktestFilterSnapshot:
        """
        단일 백테스트 실행 및 스냅샷 생성

        Args:
            ticker: 종목 코드
            data: OHLCV 데이터
            config: 필터 설정

        Returns:
            BacktestFilterSnapshot
        """
        # 백테스트 실행
        metrics = self._run_backtest(data, config)

        # 비용 적용
        if metrics.get("total_return") is not None:
            order_size = 100_000_000  # 기본 1억
            daily_volume = data["volume"].mean() * data["close"].mean() if "volume" in data.columns else 100_000_000_000
            volatility = data["close"].pct_change().std() if len(data) > 1 else 0.02

            net_return = self.apply_costs(
                gross_return=metrics["total_return"],
                order_size=order_size,
                daily_volume=daily_volume,
                volatility=volatility,
            )
            metrics["net_return"] = net_return

        # 필터 평가
        filter_results, filter_values = self._evaluate_filters(metrics, config)

        # Tier 1 평가
        tier1_passed = all(
            filter_results.get(f, False) for f in config["tier1_filters"]
        )

        # 가중치 점수 계산
        weighted_score = self._calculate_weighted_score(filter_results, config)

        # 최종 통과 여부
        weight_sum = sum(config["filter_weights"].values())
        threshold = weight_sum * config["threshold_ratio"]
        final_passed = tier1_passed and weighted_score >= threshold

        # 재현성 메타데이터 생성
        data_hash = ReproducibilityMetadata.calculate_data_hash(data)
        metadata = ReproducibilityMetadata.from_current_env(
            data_hash=data_hash,
            cost_policy_version=self.cost_policy.version,
            fee_rate=self.cost_policy.fee_rate,
            slippage_model=self.cost_policy.slippage_model,
        )

        # 스냅샷 생성
        snapshot = BacktestFilterSnapshot.create(
            ticker=ticker,
            filter_results=filter_results,
            filter_values=filter_values,
            tier1_passed=tier1_passed,
            tier1_filters=config["tier1_filters"],
            weighted_score=weighted_score,
            threshold_ratio=config["threshold_ratio"],
            final_passed=final_passed,
            config_version="v1.0.0",
            filter_weights=config["filter_weights"],
            thresholds=config["thresholds"],
            reproducibility=metadata,
        )

        return snapshot

    def run_bulk_backtest(
        self,
        tickers: List[str],
        data_dict: Dict[str, pd.DataFrame],
        n_config_variations: int = 50,
    ) -> List[BacktestFilterSnapshot]:
        """
        대량 백테스트 실행

        Args:
            tickers: 종목 코드 리스트
            data_dict: 종목별 OHLCV 데이터
            n_config_variations: Config 변형 수

        Returns:
            스냅샷 리스트
        """
        configs = self.generate_config_variations(n_config_variations)
        snapshots = []

        total = len(tickers) * len(configs)
        count = 0

        for ticker in tickers:
            if ticker not in data_dict:
                logger.warning(f"{ticker} 데이터 없음, 건너뜀")
                continue

            data = data_dict[ticker]

            for config in configs:
                try:
                    snapshot = self.run_single_backtest(ticker, data, config)
                    snapshots.append(snapshot)
                    count += 1

                    if count % 100 == 0:
                        logger.info(f"진행: {count}/{total} ({count/total*100:.1f}%)")

                except Exception as e:
                    logger.error(f"{ticker} 백테스트 실패: {e}")

        logger.info(f"대량 백테스트 완료: {len(snapshots)}개 스냅샷 생성")
        return snapshots

    def apply_costs(
        self,
        gross_return: float,
        order_size: float,
        daily_volume: float,
        volatility: float,
    ) -> float:
        """
        비용 적용 (수수료 + 슬리피지 + 유동성 페널티)

        Args:
            gross_return: 비용 전 수익률
            order_size: 주문 금액
            daily_volume: 일일 거래대금
            volatility: 일일 변동성

        Returns:
            비용 차감 후 순수익률
        """
        total_cost = self.cost_policy.calculate_total_cost(
            gross_return=gross_return,
            order_size=order_size,
            daily_volume=daily_volume,
            volatility=volatility,
        )

        return gross_return - total_cost

    def _run_backtest(self, data: pd.DataFrame, config: Dict) -> Dict:
        """
        백테스트 실행 (실제 백테스트 로직)

        Note: 이 메서드는 실제 백테스트 로직으로 교체되어야 함.
              현재는 기본 메트릭을 반환.
        """
        # 기본 메트릭 계산 (단순화된 버전)
        if len(data) < 2:
            return {}

        returns = data["close"].pct_change().dropna()

        total_return = float((data["close"].iloc[-1] / data["close"].iloc[0]) - 1)
        volatility = float(returns.std())
        sharpe = float(total_return / volatility) if volatility > 0 else 0

        return {
            "total_return": total_return,
            "sharpe_ratio": sharpe,
            "profit_factor": 1.5,  # 기본값
            "max_drawdown": abs(min(returns.cumsum().min(), 0)),
            "win_rate": 0.5,
            "total_trades": 20,
            "sortino_ratio": sharpe * 1.2,
            "calmar_ratio": total_return / max(0.01, abs(min(returns.cumsum().min(), 0))),
            "avg_win_loss_ratio": 1.5,
            "max_consecutive_losses": 3,
            "volatility": volatility,
            "avg_holding_hours": 24.0,
            "expectancy": total_return / 20 if total_return > 0 else 0,
        }

    def _evaluate_filters(
        self, metrics: Dict, config: Dict
    ) -> tuple[Dict[str, bool], Dict[str, float]]:
        """필터 평가"""
        filter_results = {}
        filter_values = {}

        thresholds = config["thresholds"]

        # 수익률
        if "total_return" in metrics:
            value = metrics["total_return"] * 100  # %로 변환
            filter_values["return"] = value
            min_return = thresholds.get("min_return", 9.0)
            filter_results["return"] = value >= min_return

        # Sharpe Ratio
        if "sharpe_ratio" in metrics:
            value = metrics["sharpe_ratio"]
            filter_values["sharpe_ratio"] = value
            min_sharpe = thresholds.get("min_sharpe_ratio", 0.7)
            filter_results["sharpe_ratio"] = value >= min_sharpe

        # Profit Factor
        if "profit_factor" in metrics:
            value = metrics["profit_factor"]
            filter_values["profit_factor"] = value
            min_pf = thresholds.get("min_profit_factor", 1.5)
            filter_results["profit_factor"] = value >= min_pf

        # Max Drawdown
        if "max_drawdown" in metrics:
            value = metrics["max_drawdown"] * 100  # %로 변환
            filter_values["max_drawdown"] = value
            max_dd = thresholds.get("max_drawdown", 25.0)
            filter_results["max_drawdown"] = value <= max_dd

        # Expectancy
        if "expectancy" in metrics:
            value = metrics["expectancy"]
            filter_values["expectancy"] = value
            filter_results["expectancy"] = value > 0

        # Win Rate
        if "win_rate" in metrics:
            value = metrics["win_rate"] * 100
            filter_values["win_rate"] = value
            filter_results["win_rate"] = value >= 50.0

        # Sortino Ratio
        if "sortino_ratio" in metrics:
            value = metrics["sortino_ratio"]
            filter_values["sortino_ratio"] = value
            filter_results["sortino_ratio"] = value >= 1.0

        # Calmar Ratio
        if "calmar_ratio" in metrics:
            value = metrics["calmar_ratio"]
            filter_values["calmar_ratio"] = value
            filter_results["calmar_ratio"] = value >= 0.5

        # Min Trades
        if "total_trades" in metrics:
            value = metrics["total_trades"]
            filter_values["min_trades"] = value
            min_trades = thresholds.get("min_trades", 30)
            filter_results["min_trades"] = value >= min_trades

        # Volatility
        if "volatility" in metrics:
            value = metrics["volatility"] * 100
            filter_values["volatility"] = value
            filter_results["volatility"] = value <= 5.0

        # Max Consecutive Losses
        if "max_consecutive_losses" in metrics:
            value = metrics["max_consecutive_losses"]
            filter_values["max_consecutive_losses"] = value
            filter_results["max_consecutive_losses"] = value <= 5

        # Avg Win/Loss Ratio
        if "avg_win_loss_ratio" in metrics:
            value = metrics["avg_win_loss_ratio"]
            filter_values["avg_win_loss_ratio"] = value
            filter_results["avg_win_loss_ratio"] = value >= 1.0

        # Avg Holding Hours
        if "avg_holding_hours" in metrics:
            value = metrics["avg_holding_hours"]
            filter_values["avg_holding_hours"] = value
            filter_results["avg_holding_hours"] = value <= 72.0

        return filter_results, filter_values

    def _calculate_weighted_score(
        self, filter_results: Dict[str, bool], config: Dict
    ) -> float:
        """가중치 점수 계산"""
        weights = config["filter_weights"]
        score = 0.0

        for key, weight in weights.items():
            if filter_results.get(key, False):
                score += weight

        return score
