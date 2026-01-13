"""
ThreeStageOptimizer - 3단계 최적화 파이프라인

Stage 1: Random/Latin Hypercube 탐색 (넓게)
Stage 2: Bayesian (TPE) 수렴 (유망 영역)
Stage 3: Pareto 최적 필터링 (다중 목적)

Optuna 의존성은 선택적:
- optuna 있으면 TPE sampler 사용
- 없으면 자체 구현 Bayesian 근사 사용
"""

import logging
import random
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple, Callable

import numpy as np

from src.domain.value_objects.cost_policy import CostPolicy
from src.ml.search_space import SearchSpace
from src.ml.objective_function import ProductionObjectiveFunction
from src.ml.constraints import Constraints

logger = logging.getLogger(__name__)

# Optuna 선택적 import
try:
    import optuna
    from optuna.samplers import TPESampler
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    logger.warning("Optuna를 찾을 수 없습니다. 기본 Bayesian 근사를 사용합니다.")


@dataclass
class ThreeStageOptimizer:
    """
    3단계 최적화 파이프라인

    Stage 1: Random Search (넓게 탐색)
    Stage 2: Bayesian Search (유망 영역 수렴)
    Stage 3: Pareto Filter (다중 목적 최적화)
    """

    cost_policy: CostPolicy
    search_space: SearchSpace = field(default_factory=SearchSpace)
    objective_fn: ProductionObjectiveFunction = None
    constraints: Constraints = field(default_factory=Constraints)
    sampler_type: str = "TPE"

    def __post_init__(self):
        """초기화"""
        if self.objective_fn is None:
            self.objective_fn = ProductionObjectiveFunction(self.cost_policy)

    def random_search(self, n_trials: int = 50) -> List[Dict[str, Any]]:
        """
        Stage 1: Random Search

        탐색 공간을 넓게 탐색하여 유망한 영역을 찾는다.

        Args:
            n_trials: 시도 횟수

        Returns:
            점수 내림차순 정렬된 결과 리스트
        """
        results = []

        for i in range(n_trials):
            config = self.search_space.sample_config()
            score = self._evaluate_config(config)

            results.append({
                'config': config,
                'score': score,
                'trial': i,
                'stage': 1,
            })

        # 점수 내림차순 정렬
        results.sort(key=lambda x: x['score'], reverse=True)

        logger.info(f"Random Search 완료: {n_trials} trials, best={results[0]['score']:.4f}")
        return results

    def bayesian_search(
        self,
        n_trials: int = 100,
        warm_start: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Stage 2: Bayesian Search (TPE)

        warm_start로 시작하여 유망한 영역을 집중 탐색한다.

        Args:
            n_trials: 시도 횟수
            warm_start: Stage 1 결과 (상위 N%)

        Returns:
            점수 내림차순 정렬된 결과 리스트
        """
        if OPTUNA_AVAILABLE:
            return self._bayesian_search_optuna(n_trials, warm_start)
        else:
            return self._bayesian_search_fallback(n_trials, warm_start)

    def _bayesian_search_optuna(
        self,
        n_trials: int,
        warm_start: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Optuna 기반 Bayesian Search"""
        sampler = TPESampler(seed=42)
        study = optuna.create_study(direction="maximize", sampler=sampler)

        # warm start enqueue
        if warm_start:
            for result in warm_start:
                config = result['config']
                try:
                    study.enqueue_trial({
                        'threshold_ratio': config['threshold_ratio'],
                        **{f"weight_{k}": v for k, v in config['filter_weights'].items()},
                    })
                except Exception:
                    pass  # 일부 실패해도 계속

        def objective(trial):
            config = self._sample_from_trial(trial)
            return self._evaluate_config(config)

        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

        # 결과 수집
        results = []
        for trial in study.trials:
            results.append({
                'config': self._trial_to_config(trial),
                'score': trial.value or 0.0,
                'trial': trial.number,
                'stage': 2,
            })

        results.sort(key=lambda x: x['score'], reverse=True)
        logger.info(f"Bayesian Search (Optuna) 완료: {n_trials} trials")
        return results

    def _bayesian_search_fallback(
        self,
        n_trials: int,
        warm_start: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Optuna 없이 Bayesian 근사 (Gaussian perturbation)"""
        results = []

        # warm start가 있으면 그 주변을 탐색
        if warm_start:
            base_configs = [r['config'] for r in warm_start]
        else:
            base_configs = [self.search_space.sample_config()]

        for i in range(n_trials):
            # 기존 좋은 config를 perturbation
            base = random.choice(base_configs)
            config = self._perturb_config(base, noise_scale=0.2)
            score = self._evaluate_config(config)

            results.append({
                'config': config,
                'score': score,
                'trial': i,
                'stage': 2,
            })

            # 좋은 결과를 base에 추가 (exploitation)
            if score > np.median([r['score'] for r in results]):
                base_configs.append(config)

        results.sort(key=lambda x: x['score'], reverse=True)
        logger.info(f"Bayesian Search (Fallback) 완료: {n_trials} trials")
        return results

    def pareto_filter(
        self,
        results: List[Dict[str, Any]],
        objectives: List[str],
        minimize: Optional[List[str]] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Stage 3: Pareto Filter

        다중 목적 최적화를 위한 Pareto frontier 추출.

        Args:
            results: 필터링할 결과
            objectives: 최대화할 목적 (예: ['score', 'sharpe'])
            minimize: 최소화할 목적 (예: ['drawdown'])
            constraints: 제약 조건 (예: {'drawdown': 0.30})

        Returns:
            Pareto frontier에 있는 결과
        """
        if minimize is None:
            minimize = []
        if constraints is None:
            constraints = {}

        # 제약 조건 필터링
        filtered = []
        for r in results:
            valid = True

            for key, limit in constraints.items():
                value = r.get(key)
                if value is None:
                    continue

                if isinstance(limit, tuple):
                    # 범위 제약 (min, max)
                    min_val, max_val = limit
                    if not (min_val <= value <= max_val):
                        valid = False
                        break
                else:
                    # 상한 제약
                    if value > limit:
                        valid = False
                        break

            if valid:
                filtered.append(r)

        # Pareto frontier 추출
        pareto_front = []
        for candidate in filtered:
            is_dominated = False

            for other in filtered:
                if candidate == other:
                    continue

                # other가 candidate를 지배하는지 확인
                dominates = True
                strictly_better = False

                for obj in objectives:
                    c_val = candidate.get(obj, 0)
                    o_val = other.get(obj, 0)
                    if o_val < c_val:
                        dominates = False
                        break
                    if o_val > c_val:
                        strictly_better = True

                if dominates:
                    for obj in minimize:
                        c_val = candidate.get(obj, 0)
                        o_val = other.get(obj, 0)
                        if o_val > c_val:
                            dominates = False
                            break
                        if o_val < c_val:
                            strictly_better = True

                if dominates and strictly_better:
                    is_dominated = True
                    break

            if not is_dominated:
                pareto_front.append(candidate)

        logger.info(f"Pareto Filter: {len(results)} → {len(pareto_front)}")
        return pareto_front

    def reality_filter(
        self,
        results: List[Dict[str, Any]],
        min_trades: int = 20,
        max_slippage: float = 0.005,
    ) -> List[Dict[str, Any]]:
        """
        현실 가능성 필터

        비현실적인 결과 제거 (거래 수 부족, 슬리피지 과다 등).

        Args:
            results: 필터링할 결과
            min_trades: 최소 거래 수
            max_slippage: 최대 슬리피지

        Returns:
            현실적인 결과만 포함
        """
        filtered = []

        for r in results:
            trades = r.get('total_trades', 0)
            slippage = r.get('slippage', 0)

            if trades >= min_trades and slippage <= max_slippage:
                filtered.append(r)

        logger.info(f"Reality Filter: {len(results)} → {len(filtered)}")
        return filtered

    def optimize(
        self,
        n_random_trials: int = 50,
        n_bayesian_trials: int = 100,
    ) -> Dict[str, Any]:
        """
        전체 3단계 최적화 실행

        Args:
            n_random_trials: Stage 1 시도 횟수
            n_bayesian_trials: Stage 2 시도 횟수

        Returns:
            최적화 결과 (stage별 결과, pareto frontier, final candidates)
        """
        # Stage 1: Random Search
        stage1_results = self.random_search(n_trials=n_random_trials)

        # 상위 10% warm start
        top_percent = max(1, len(stage1_results) // 10)
        warm_start = stage1_results[:top_percent]

        # Stage 2: Bayesian Search
        stage2_results = self.bayesian_search(
            n_trials=n_bayesian_trials,
            warm_start=warm_start,
        )

        # Stage 3: Pareto Filter
        all_results = stage1_results + stage2_results
        pareto_front = self.pareto_filter(
            all_results,
            objectives=['score'],
            minimize=[],
        )

        # Reality Filter
        final_candidates = self.reality_filter(pareto_front)

        return {
            'stage1_results': stage1_results,
            'stage2_results': stage2_results,
            'pareto_frontier': pareto_front,
            'final_candidates': final_candidates,
            'best_score': max(r['score'] for r in all_results) if all_results else 0,
        }

    def _evaluate_config(self, config: Dict[str, Any]) -> float:
        """
        Config 평가

        가상의 백테스트 결과를 생성하여 목적 함수로 평가.
        실제 사용 시 실제 백테스트 결과로 교체해야 함.
        """
        # 가상의 백테스트 결과 생성 (Config 품질에 따라 점수 변동)
        threshold_ratio = config.get('threshold_ratio', 0.625)
        weights = config.get('filter_weights', {})

        # Config 품질 점수 (가중치 밸런스)
        weight_values = list(weights.values()) if weights else [1.0]
        balance = np.std(weight_values) if len(weight_values) > 1 else 0.5

        # 점수 = threshold_ratio 영향 + 가중치 밸런스 + 랜덤 노이즈
        base_score = (1 - abs(threshold_ratio - 0.65)) * 0.1  # 0.65 근처가 좋음
        balance_bonus = (1 - min(balance, 1.0)) * 0.05
        noise = random.uniform(-0.02, 0.02)

        backtest_result = {
            'gross_return': base_score + balance_bonus + noise,
            'sharpe_ratio': 1.0 + random.uniform(-0.3, 0.3),
            'max_drawdown': 0.15 + random.uniform(0, 0.10),
            'total_trades': random.randint(20, 50),
            'daily_volume': 50_000_000_000,
            'volatility': 0.02,
            'pass_rate': threshold_ratio * 0.3,
        }

        return self.objective_fn.evaluate([backtest_result])

    def _perturb_config(
        self, config: Dict[str, Any], noise_scale: float = 0.1
    ) -> Dict[str, Any]:
        """Config에 Gaussian perturbation 적용"""
        new_config = {
            'threshold_ratio': np.clip(
                config['threshold_ratio'] + random.gauss(0, noise_scale * 0.1),
                0.50, 0.85
            ),
            'filter_weights': {},
            'thresholds': dict(config['thresholds']),
            'tier1_filters': set(config['tier1_filters']),
        }

        for key, value in config['filter_weights'].items():
            min_val, max_val = self.search_space.WEIGHT_RANGES[key]
            new_value = np.clip(
                value + random.gauss(0, noise_scale * (max_val - min_val)),
                min_val, max_val
            )
            new_config['filter_weights'][key] = new_value

        return new_config

    def _sample_from_trial(self, trial) -> Dict[str, Any]:
        """Optuna trial에서 Config 샘플링"""
        config = {
            'threshold_ratio': trial.suggest_float(
                'threshold_ratio', 0.50, 0.85
            ),
            'filter_weights': {},
            'thresholds': {},
            'tier1_filters': self.search_space.REQUIRED_TIER1.copy(),
        }

        for key, (min_val, max_val) in self.search_space.WEIGHT_RANGES.items():
            config['filter_weights'][key] = trial.suggest_float(
                f'weight_{key}', min_val, max_val
            )

        for key, (min_val, max_val) in self.search_space.FILTER_THRESHOLD_RANGES.items():
            if key == 'min_trades':
                config['thresholds'][key] = trial.suggest_int(key, int(min_val), int(max_val))
            else:
                config['thresholds'][key] = trial.suggest_float(key, min_val, max_val)

        return config

    def _trial_to_config(self, trial) -> Dict[str, Any]:
        """Optuna trial을 Config로 변환"""
        return {
            'threshold_ratio': trial.params.get('threshold_ratio', 0.625),
            'filter_weights': {
                key: trial.params.get(f'weight_{key}', 1.0)
                for key in self.search_space.WEIGHT_RANGES.keys()
            },
            'thresholds': {},
            'tier1_filters': self.search_space.REQUIRED_TIER1.copy(),
        }
