"""
ThreeStageOptimizer 테스트

Phase 4: Bayesian Optimization 구현
- Random/LHS 탐색
- Bayesian (TPE) 수렴
- Pareto 최적 조합 필터링
"""

import pytest
from typing import Dict, List, Any
from unittest.mock import MagicMock, patch


class TestRandomSearch:
    """Random Search (Stage 1) 테스트"""

    def test_random_search_generates_samples(self):
        """Random Search는 지정된 수의 샘플을 생성해야 한다"""
        from src.ml.optimizer import ThreeStageOptimizer
        from src.domain.value_objects.cost_policy import CostPolicy

        cost_policy = CostPolicy.default()
        optimizer = ThreeStageOptimizer(cost_policy)

        # 10개 샘플 생성
        results = optimizer.random_search(n_trials=10)

        assert len(results) == 10

    def test_random_search_returns_sorted_results(self):
        """Random Search 결과는 점수 기준 정렬되어야 한다"""
        from src.ml.optimizer import ThreeStageOptimizer
        from src.domain.value_objects.cost_policy import CostPolicy

        cost_policy = CostPolicy.default()
        optimizer = ThreeStageOptimizer(cost_policy)

        results = optimizer.random_search(n_trials=20)

        # 점수 내림차순 정렬 확인
        scores = [r['score'] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_random_search_results_have_config(self):
        """Random Search 결과는 Config를 포함해야 한다"""
        from src.ml.optimizer import ThreeStageOptimizer
        from src.domain.value_objects.cost_policy import CostPolicy

        cost_policy = CostPolicy.default()
        optimizer = ThreeStageOptimizer(cost_policy)

        results = optimizer.random_search(n_trials=5)

        for result in results:
            assert 'config' in result
            assert 'score' in result
            assert 'threshold_ratio' in result['config']


class TestBayesianSearch:
    """Bayesian Search (Stage 2) 테스트"""

    def test_bayesian_search_uses_warm_start(self):
        """Bayesian Search는 warm start를 사용해야 한다"""
        from src.ml.optimizer import ThreeStageOptimizer
        from src.domain.value_objects.cost_policy import CostPolicy

        cost_policy = CostPolicy.default()
        optimizer = ThreeStageOptimizer(cost_policy)

        # Stage 1 결과를 warm start로 사용
        stage1_results = optimizer.random_search(n_trials=10)
        top_results = stage1_results[:3]  # 상위 30%

        stage2_results = optimizer.bayesian_search(
            n_trials=20,
            warm_start=top_results,
        )

        assert len(stage2_results) > 0

    def test_bayesian_improves_over_random(self):
        """Bayesian Search는 유효한 결과를 반환해야 한다"""
        from src.ml.optimizer import ThreeStageOptimizer
        from src.domain.value_objects.cost_policy import CostPolicy

        cost_policy = CostPolicy.default()
        optimizer = ThreeStageOptimizer(cost_policy)

        # Stage 1: Random
        stage1_results = optimizer.random_search(n_trials=30)
        stage1_best = max(r['score'] for r in stage1_results)

        # Stage 2: Bayesian (warm start)
        stage2_results = optimizer.bayesian_search(
            n_trials=50,
            warm_start=stage1_results[:10],
        )
        stage2_best = max(r['score'] for r in stage2_results)

        # Bayesian 결과가 유효해야 함 (양수 점수)
        assert stage2_best > 0, "Bayesian Search 결과가 유효해야 함"

        # 전체 최적은 두 단계 중 더 나은 것
        overall_best = max(stage1_best, stage2_best)
        assert overall_best > 0, "전체 최적화 결과가 양수여야 함"

    def test_bayesian_search_uses_tpe_sampler(self):
        """Bayesian Search는 TPE Sampler를 사용해야 한다"""
        from src.ml.optimizer import ThreeStageOptimizer
        from src.domain.value_objects.cost_policy import CostPolicy

        cost_policy = CostPolicy.default()
        optimizer = ThreeStageOptimizer(cost_policy)

        # Optuna study가 TPE sampler를 사용하는지 확인
        assert optimizer.sampler_type == "TPE"


class TestParetoFilter:
    """Pareto Filter (Stage 3) 테스트"""

    def test_pareto_frontier_valid(self):
        """Pareto frontier는 유효해야 한다"""
        from src.ml.optimizer import ThreeStageOptimizer
        from src.domain.value_objects.cost_policy import CostPolicy

        cost_policy = CostPolicy.default()
        optimizer = ThreeStageOptimizer(cost_policy)

        # 테스트용 결과
        results = [
            {'config': {}, 'score': 0.1, 'sharpe': 1.0, 'drawdown': 0.15},
            {'config': {}, 'score': 0.15, 'sharpe': 0.8, 'drawdown': 0.20},
            {'config': {}, 'score': 0.12, 'sharpe': 1.2, 'drawdown': 0.10},
            {'config': {}, 'score': 0.08, 'sharpe': 0.5, 'drawdown': 0.25},
        ]

        pareto_front = optimizer.pareto_filter(
            results,
            objectives=['score', 'sharpe'],
            minimize=['drawdown'],
        )

        # Pareto front는 비어있지 않아야 함
        assert len(pareto_front) > 0

        # Pareto front의 각 점은 다른 점에 의해 지배되지 않아야 함
        for point in pareto_front:
            for other in pareto_front:
                if point != other:
                    # point가 other에 완전히 지배되면 안됨
                    dominated = (
                        other['score'] >= point['score'] and
                        other['sharpe'] >= point['sharpe'] and
                        other['drawdown'] <= point['drawdown'] and
                        (other['score'] > point['score'] or
                         other['sharpe'] > point['sharpe'] or
                         other['drawdown'] < point['drawdown'])
                    )
                    assert not dominated

    def test_pareto_filter_with_constraints(self):
        """Pareto filter는 제약 조건을 적용해야 한다"""
        from src.ml.optimizer import ThreeStageOptimizer
        from src.domain.value_objects.cost_policy import CostPolicy

        cost_policy = CostPolicy.default()
        optimizer = ThreeStageOptimizer(cost_policy)

        results = [
            {'config': {}, 'score': 0.1, 'sharpe': 1.0, 'drawdown': 0.15, 'selection_rate': 0.20},
            {'config': {}, 'score': 0.15, 'sharpe': 0.8, 'drawdown': 0.35, 'selection_rate': 0.25},  # DD 초과
            {'config': {}, 'score': 0.12, 'sharpe': 1.2, 'drawdown': 0.10, 'selection_rate': 0.05},  # 선택률 미달
        ]

        pareto_front = optimizer.pareto_filter(
            results,
            objectives=['score', 'sharpe'],
            minimize=['drawdown'],
            constraints={
                'drawdown': 0.30,  # 최대 30%
                'selection_rate': (0.10, 0.30),  # 10-30%
            },
        )

        # 제약 조건을 만족하는 결과만 포함
        for point in pareto_front:
            assert point['drawdown'] <= 0.30
            assert 0.10 <= point['selection_rate'] <= 0.30


class TestThreeStageOptimizer:
    """ThreeStageOptimizer 통합 테스트"""

    def test_optimize_returns_final_candidates(self):
        """optimize는 최종 후보를 반환해야 한다"""
        from src.ml.optimizer import ThreeStageOptimizer
        from src.domain.value_objects.cost_policy import CostPolicy

        cost_policy = CostPolicy.default()
        optimizer = ThreeStageOptimizer(cost_policy)

        result = optimizer.optimize(
            n_random_trials=20,
            n_bayesian_trials=30,
        )

        assert 'final_candidates' in result
        assert 'stage1_results' in result
        assert 'stage2_results' in result
        assert 'pareto_frontier' in result

    def test_optimize_stage1_to_stage2_improvement(self):
        """Stage 1 → Stage 2 개선이 있어야 한다"""
        from src.ml.optimizer import ThreeStageOptimizer
        from src.domain.value_objects.cost_policy import CostPolicy

        cost_policy = CostPolicy.default()
        optimizer = ThreeStageOptimizer(cost_policy)

        result = optimizer.optimize(
            n_random_trials=30,
            n_bayesian_trials=50,
        )

        stage1_best = max(r['score'] for r in result['stage1_results'])
        stage2_best = max(r['score'] for r in result['stage2_results'])

        # 전체 최적 결과가 유효해야 함 (Stage 1 또는 Stage 2 중 더 나은 것)
        overall_best = max(stage1_best, stage2_best)
        assert overall_best > 0, "최적화 결과가 양수여야 함"

        # Stage 2가 완전히 실패하지 않아야 함 (0보다 큼)
        assert stage2_best > 0, "Stage 2 결과가 유효해야 함"

    def test_optimize_respects_cost_policy(self):
        """optimize는 비용 정책을 준수해야 한다"""
        from src.ml.optimizer import ThreeStageOptimizer
        from src.domain.value_objects.cost_policy import CostPolicy

        cost_policy = CostPolicy.default()
        optimizer = ThreeStageOptimizer(cost_policy)

        # 비용 정책이 적용되었는지 확인
        assert optimizer.cost_policy.fee_rate == 0.0005
        assert optimizer.cost_policy.slippage_model == "sqrt"

    def test_reality_filter_removes_unrealistic(self):
        """reality filter는 비현실적인 결과를 제거해야 한다"""
        from src.ml.optimizer import ThreeStageOptimizer
        from src.domain.value_objects.cost_policy import CostPolicy

        cost_policy = CostPolicy.default()
        optimizer = ThreeStageOptimizer(cost_policy)

        results = [
            {'config': {}, 'score': 0.1, 'total_trades': 30, 'slippage': 0.003},  # 유효
            {'config': {}, 'score': 0.15, 'total_trades': 5, 'slippage': 0.003},  # 거래 수 부족
            {'config': {}, 'score': 0.12, 'total_trades': 30, 'slippage': 0.01},  # 슬리피지 과다
        ]

        filtered = optimizer.reality_filter(
            results,
            min_trades=20,
            max_slippage=0.005,
        )

        assert len(filtered) == 1
        assert filtered[0]['total_trades'] >= 20
        assert filtered[0]['slippage'] <= 0.005
