"""
SearchSpace - 탐색 공간 정의

정합성이 보장된 탐색 공간:
- threshold_ratio만 사용 (절대값 금지)
- min_trades는 가중치에서 제외
- Tier 1 조합은 return, sharpe_ratio 필수 포함
"""

import logging
import random
import itertools
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Any

logger = logging.getLogger(__name__)


@dataclass
class SearchSpace:
    """
    정합성이 보장된 탐색 공간

    정합성 규칙:
    1. WEIGHTED_FILTER_THRESHOLD는 비율만 사용 (절대값 금지)
    2. min_trades는 필터 임계값으로만 사용 (가중치 항목 제외)
    3. Tier 1 조합은 return과 sharpe_ratio 필수 포함
    """

    # Tier 1 필터 후보 (return과 sharpe_ratio는 필수)
    TIER1_CANDIDATES: Set[str] = None

    # 가중치 범위 (min_trades 제외됨)
    WEIGHT_RANGES: Dict[str, Tuple[float, float]] = None

    # 통과 임계값 (비율만 사용)
    THRESHOLD_RATIO_RANGE: Tuple[float, float] = (0.50, 0.85)

    # 필터 임계값 범위
    FILTER_THRESHOLD_RANGES: Dict[str, Tuple[float, float]] = None

    # 필수 Tier 1 필터
    REQUIRED_TIER1: Set[str] = None

    def __post_init__(self):
        """기본값 설정"""
        if self.TIER1_CANDIDATES is None:
            self.TIER1_CANDIDATES = {
                'return', 'profit_factor', 'sharpe_ratio', 'expectancy',
                'max_drawdown', 'sortino_ratio'
            }

        if self.REQUIRED_TIER1 is None:
            self.REQUIRED_TIER1 = {'return', 'sharpe_ratio'}

        if self.WEIGHT_RANGES is None:
            # min_trades는 여기에 없음 (정합성 규칙 2)
            self.WEIGHT_RANGES = {
                'max_drawdown': (0.5, 3.0),
                'sortino_ratio': (0.5, 2.5),
                'win_rate': (0.25, 1.5),
                'calmar_ratio': (0.5, 2.0),
                'avg_win_loss_ratio': (0.25, 1.0),
                'max_consecutive_losses': (0.25, 1.0),
                'volatility': (0.0, 1.0),
                'avg_holding_hours': (0.0, 1.0),
            }

        if self.FILTER_THRESHOLD_RANGES is None:
            # min_trades는 여기에만 존재
            self.FILTER_THRESHOLD_RANGES = {
                'min_return': (5.0, 15.0),
                'min_sharpe_ratio': (0.4, 1.2),
                'min_profit_factor': (1.2, 2.0),
                'min_trades': (15, 50),  # 정수
                'max_drawdown': (15.0, 35.0),
            }

    def generate_tier1_combinations(
        self, min_count: int = 3, max_count: int = 5
    ) -> List[Set[str]]:
        """
        Tier 1 필터 조합 생성 (규칙 기반)

        규칙:
        - return과 sharpe_ratio는 반드시 포함
        - 3-5개 필터로 구성

        Args:
            min_count: 최소 필터 수 (기본 3)
            max_count: 최대 필터 수 (기본 5)

        Returns:
            유효한 Tier 1 조합 리스트
        """
        combinations = []

        for r in range(min_count, max_count + 1):
            for combo in itertools.combinations(self.TIER1_CANDIDATES, r):
                combo_set = set(combo)
                # 필수 포함 규칙: return과 sharpe_ratio는 반드시 포함
                if self.REQUIRED_TIER1.issubset(combo_set):
                    combinations.append(combo_set)

        logger.debug(f"Tier 1 조합 {len(combinations)}개 생성")
        return combinations

    def sample_config(self) -> Dict[str, Any]:
        """
        무작위 Config 샘플링 (정합성 규칙 준수)

        Returns:
            정합성이 보장된 Config 딕셔너리
        """
        # 1. threshold_ratio (비율만 사용)
        threshold_ratio = random.uniform(*self.THRESHOLD_RATIO_RANGE)

        # 2. filter_weights (min_trades 제외)
        filter_weights = {}
        for key, (min_val, max_val) in self.WEIGHT_RANGES.items():
            filter_weights[key] = random.uniform(min_val, max_val)

        # 3. thresholds (min_trades 포함)
        thresholds = {}
        for key, (min_val, max_val) in self.FILTER_THRESHOLD_RANGES.items():
            if key == 'min_trades':
                thresholds[key] = random.randint(int(min_val), int(max_val))
            else:
                thresholds[key] = random.uniform(min_val, max_val)

        # 4. tier1_filters (return, sharpe_ratio 필수 + 추가 1-3개)
        tier1_filters = set(self.REQUIRED_TIER1)
        optional = self.TIER1_CANDIDATES - self.REQUIRED_TIER1
        n_additional = random.randint(1, min(3, len(optional)))
        tier1_filters.update(random.sample(list(optional), n_additional))

        return {
            'threshold_ratio': threshold_ratio,
            'filter_weights': filter_weights,
            'thresholds': thresholds,
            'tier1_filters': tier1_filters,
        }

    def sample_configs(self, n_samples: int = 50) -> List[Dict[str, Any]]:
        """
        여러 Config 샘플링

        Args:
            n_samples: 샘플 수

        Returns:
            Config 리스트
        """
        return [self.sample_config() for _ in range(n_samples)]

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Config 정합성 검증

        Args:
            config: 검증할 Config

        Returns:
            유효 여부

        Raises:
            ValueError: 정합성 위반 시
        """
        # 규칙 1: threshold_ratio 범위 확인
        ratio = config.get('threshold_ratio')
        if ratio is None or not (0.50 <= ratio <= 0.85):
            raise ValueError(f"threshold_ratio는 0.50-0.85 범위여야 함: {ratio}")

        # 규칙 2: min_trades가 가중치에 없어야 함
        weights = config.get('filter_weights', {})
        if 'min_trades' in weights:
            raise ValueError("min_trades는 가중치에 포함될 수 없음")

        # 규칙 3: tier1_filters에 필수 필터 포함
        tier1 = config.get('tier1_filters', set())
        if not self.REQUIRED_TIER1.issubset(tier1):
            raise ValueError(
                f"tier1_filters에 필수 필터 누락: "
                f"필요={self.REQUIRED_TIER1}, 실제={tier1}"
            )

        return True
