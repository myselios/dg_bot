"""
SearchSpace 및 ObjectiveFunction 테스트

Phase 3: 탐색 공간 및 목적 함수 정의
- 정합성 규칙 강제
- 비용 반영 목적 함수
"""

import pytest
from typing import Set, Dict


class TestSearchSpace:
    """SearchSpace 테스트"""

    def test_threshold_ratio_only_no_absolute(self):
        """threshold는 비율만 사용해야 한다 (절대값 금지)"""
        from src.ml.search_space import SearchSpace

        space = SearchSpace()

        # threshold_ratio는 0.50-0.85 범위의 비율
        assert space.THRESHOLD_RATIO_RANGE == (0.50, 0.85)

        # 절대값 threshold 속성이 없어야 함
        assert not hasattr(space, 'ABSOLUTE_THRESHOLD')
        assert not hasattr(space, 'WEIGHTED_FILTER_THRESHOLD')

    def test_min_trades_not_in_weights(self):
        """min_trades는 가중치에 포함되지 않아야 한다"""
        from src.ml.search_space import SearchSpace

        space = SearchSpace()

        # min_trades는 가중치 범위에 없어야 함
        assert 'min_trades' not in space.WEIGHT_RANGES

        # min_trades는 필터 임계값에만 존재
        assert 'min_trades' in space.FILTER_THRESHOLD_RANGES

    def test_tier1_combinations_valid(self):
        """Tier 1 조합은 return과 sharpe_ratio를 필수로 포함해야 한다"""
        from src.ml.search_space import SearchSpace

        space = SearchSpace()
        combinations = space.generate_tier1_combinations()

        # 조합이 생성되어야 함
        assert len(combinations) > 0

        # 모든 조합에 return과 sharpe_ratio 필수
        for combo in combinations:
            assert 'return' in combo, f"return 누락: {combo}"
            assert 'sharpe_ratio' in combo, f"sharpe_ratio 누락: {combo}"

    def test_tier1_combinations_size_range(self):
        """Tier 1 조합은 3-5개 필터로 구성되어야 한다"""
        from src.ml.search_space import SearchSpace

        space = SearchSpace()
        combinations = space.generate_tier1_combinations(min_count=3, max_count=5)

        for combo in combinations:
            assert 3 <= len(combo) <= 5, f"조합 크기 범위 위반: {len(combo)}"

    def test_weight_ranges_valid(self):
        """가중치 범위는 유효해야 한다"""
        from src.ml.search_space import SearchSpace

        space = SearchSpace()

        # 8개 가중치 항목 (min_trades 제외)
        expected_weights = {
            'max_drawdown', 'sortino_ratio', 'win_rate', 'calmar_ratio',
            'avg_win_loss_ratio', 'max_consecutive_losses', 'volatility', 'avg_holding_hours'
        }
        assert set(space.WEIGHT_RANGES.keys()) == expected_weights

        # 모든 범위가 (min, max) 형태
        for key, (min_val, max_val) in space.WEIGHT_RANGES.items():
            assert min_val < max_val, f"{key} 범위 오류: {min_val} >= {max_val}"
            assert min_val >= 0, f"{key} 최소값 음수: {min_val}"

    def test_sample_config_consistency(self):
        """샘플 Config는 정합성 규칙을 따라야 한다"""
        from src.ml.search_space import SearchSpace

        space = SearchSpace()
        config = space.sample_config()

        # threshold_ratio 범위 확인
        assert 0.50 <= config['threshold_ratio'] <= 0.85

        # min_trades가 가중치에 없음
        assert 'min_trades' not in config['filter_weights']

        # min_trades가 thresholds에 있음
        assert 'min_trades' in config['thresholds']

        # tier1_filters에 필수 필터 포함
        assert 'return' in config['tier1_filters']
        assert 'sharpe_ratio' in config['tier1_filters']


class TestObjectiveFunction:
    """ObjectiveFunction 테스트"""

    def test_objective_includes_costs(self):
        """목적 함수는 비용을 반영해야 한다"""
        from src.ml.objective_function import ProductionObjectiveFunction
        from src.domain.value_objects.cost_policy import CostPolicy

        cost_policy = CostPolicy.default()
        objective = ProductionObjectiveFunction(cost_policy)

        # 비용 정책이 설정되어야 함
        assert objective.cost_policy is not None
        assert objective.cost_policy.fee_rate == 0.0005

    def test_objective_net_return_lower_than_gross(self):
        """순수익률은 총수익률보다 낮아야 한다 (비용 차감)"""
        from src.ml.objective_function import ProductionObjectiveFunction
        from src.domain.value_objects.cost_policy import CostPolicy

        cost_policy = CostPolicy.default()
        objective = ProductionObjectiveFunction(cost_policy)

        # 테스트용 백테스트 결과
        backtest_result = {
            'gross_return': 0.10,  # 10% 수익
            'sharpe_ratio': 1.2,
            'max_drawdown': 0.15,
            'total_trades': 30,
            'daily_volume': 100_000_000_000,  # 1000억
            'volatility': 0.02,
        }

        net_return = objective.calculate_net_return(backtest_result)

        # 비용 차감으로 순수익률 < 총수익률
        assert net_return < backtest_result['gross_return']

    def test_objective_slippage_applied(self):
        """슬리피지가 적용되어야 한다"""
        from src.ml.objective_function import ProductionObjectiveFunction
        from src.domain.value_objects.cost_policy import CostPolicy

        cost_policy = CostPolicy.default()
        objective = ProductionObjectiveFunction(cost_policy)

        # 큰 주문 사이즈 (높은 슬리피지)
        high_slippage_result = {
            'gross_return': 0.10,
            'sharpe_ratio': 1.2,
            'max_drawdown': 0.15,
            'total_trades': 30,
            'order_size': 1_000_000_000,  # 10억 (큰 주문)
            'daily_volume': 10_000_000_000,  # 100억 (작은 거래대금)
            'volatility': 0.05,  # 높은 변동성
        }

        # 작은 주문 사이즈 (낮은 슬리피지)
        low_slippage_result = {
            'gross_return': 0.10,
            'sharpe_ratio': 1.2,
            'max_drawdown': 0.15,
            'total_trades': 30,
            'order_size': 10_000_000,  # 1천만 (작은 주문)
            'daily_volume': 100_000_000_000,  # 1000억 (큰 거래대금)
            'volatility': 0.01,  # 낮은 변동성
        }

        high_slippage_net = objective.calculate_net_return(high_slippage_result)
        low_slippage_net = objective.calculate_net_return(low_slippage_result)

        # 높은 슬리피지 환경에서 순수익률이 더 낮아야 함
        assert high_slippage_net < low_slippage_net

    def test_objective_liquidity_penalty(self):
        """유동성 페널티가 적용되어야 한다"""
        from src.ml.objective_function import ProductionObjectiveFunction
        from src.domain.value_objects.cost_policy import CostPolicy

        cost_policy = CostPolicy.default()
        objective = ProductionObjectiveFunction(cost_policy)

        # 낮은 유동성
        low_liquidity = {
            'gross_return': 0.10,
            'sharpe_ratio': 1.2,
            'max_drawdown': 0.15,
            'total_trades': 30,
            'daily_volume': 1_000_000_000,  # 10억 (낮음)
            'volatility': 0.02,
        }

        # 높은 유동성
        high_liquidity = {
            'gross_return': 0.10,
            'sharpe_ratio': 1.2,
            'max_drawdown': 0.15,
            'total_trades': 30,
            'daily_volume': 100_000_000_000,  # 1000억 (높음)
            'volatility': 0.02,
        }

        low_liq_net = objective.calculate_net_return(low_liquidity)
        high_liq_net = objective.calculate_net_return(high_liquidity)

        # 낮은 유동성에서 순수익률이 더 낮아야 함
        assert low_liq_net < high_liq_net

    def test_objective_evaluate_returns_score(self):
        """evaluate는 최종 점수를 반환해야 한다"""
        from src.ml.objective_function import ProductionObjectiveFunction
        from src.domain.value_objects.cost_policy import CostPolicy

        cost_policy = CostPolicy.default()
        objective = ProductionObjectiveFunction(cost_policy)

        backtest_results = [
            {
                'gross_return': 0.12,
                'sharpe_ratio': 1.3,
                'max_drawdown': 0.15,
                'total_trades': 35,
                'daily_volume': 50_000_000_000,
                'volatility': 0.02,
                'pass_rate': 0.20,
            }
        ]

        score = objective.evaluate(backtest_results)

        # 점수는 숫자여야 함
        assert isinstance(score, float)


class TestConstraints:
    """Constraints 테스트"""

    def test_constraints_selection_rate_range(self):
        """선택률은 10-30% 범위여야 한다"""
        from src.ml.constraints import Constraints

        constraints = Constraints()

        # 유효 범위
        assert constraints.is_valid_selection_rate(0.15) is True
        assert constraints.is_valid_selection_rate(0.10) is True
        assert constraints.is_valid_selection_rate(0.30) is True

        # 범위 초과
        assert constraints.is_valid_selection_rate(0.05) is False
        assert constraints.is_valid_selection_rate(0.35) is False

    def test_constraints_min_trades(self):
        """최소 거래 수 제약"""
        from src.ml.constraints import Constraints

        constraints = Constraints()

        assert constraints.is_valid_min_trades(25) is True
        assert constraints.is_valid_min_trades(20) is True
        assert constraints.is_valid_min_trades(15) is False

    def test_constraints_max_drawdown(self):
        """최대 낙폭 제약"""
        from src.ml.constraints import Constraints

        constraints = Constraints()

        assert constraints.is_valid_max_drawdown(0.25) is True
        assert constraints.is_valid_max_drawdown(0.30) is True
        assert constraints.is_valid_max_drawdown(0.35) is False

    def test_constraints_all_validation(self):
        """전체 제약 조건 검증"""
        from src.ml.constraints import Constraints

        constraints = Constraints()

        # 유효한 결과
        valid_result = {
            'selection_rate': 0.20,
            'total_trades': 30,
            'max_drawdown': 0.20,
        }
        assert constraints.validate_all(valid_result) is True

        # 무효한 결과 (낙폭 초과)
        invalid_result = {
            'selection_rate': 0.20,
            'total_trades': 30,
            'max_drawdown': 0.40,
        }
        assert constraints.validate_all(invalid_result) is False
