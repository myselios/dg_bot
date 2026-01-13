"""
BulkBacktester 테스트

다양한 Config 조합으로 대량 백테스트를 실행하고 스냅샷을 생성하는 테스트
"""

import pytest
import tempfile
import shutil
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np


@pytest.fixture
def temp_data_dir():
    """임시 데이터 디렉토리"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_ohlcv_data():
    """샘플 OHLCV 데이터"""
    dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
    np.random.seed(42)
    base_price = 50000000

    data = pd.DataFrame({
        "open": base_price + np.random.randn(100).cumsum() * 100000,
        "high": base_price + np.random.randn(100).cumsum() * 100000 + 500000,
        "low": base_price + np.random.randn(100).cumsum() * 100000 - 500000,
        "close": base_price + np.random.randn(100).cumsum() * 100000,
        "volume": np.random.randint(1000, 10000, 100),
    }, index=dates)

    return data


@pytest.fixture
def mock_backtest_result():
    """모의 백테스트 결과"""
    return {
        "total_return": 0.15,
        "sharpe_ratio": 1.2,
        "profit_factor": 1.8,
        "max_drawdown": 0.12,
        "win_rate": 0.55,
        "total_trades": 25,
        "sortino_ratio": 1.5,
        "calmar_ratio": 1.25,
        "avg_win_loss_ratio": 1.6,
        "max_consecutive_losses": 3,
        "volatility": 0.02,
        "avg_holding_hours": 48.0,
        "expectancy": 0.02,
    }


class TestBulkBacktester:
    """BulkBacktester 테스트"""

    def test_bulk_backtester_initialization(self, temp_data_dir):
        """BulkBacktester 초기화 테스트"""
        from src.ml.bulk_backtester import BulkBacktester
        from src.domain.value_objects.cost_policy import CostPolicy

        cost_policy = CostPolicy.default()
        backtester = BulkBacktester(
            data_path=temp_data_dir,
            cost_policy=cost_policy,
        )

        assert backtester.cost_policy == cost_policy

    def test_generate_config_variations(self, temp_data_dir):
        """Config 변형 생성 테스트"""
        from src.ml.bulk_backtester import BulkBacktester
        from src.domain.value_objects.cost_policy import CostPolicy

        backtester = BulkBacktester(
            data_path=temp_data_dir,
            cost_policy=CostPolicy.default(),
        )

        # 10개 Config 변형 생성
        configs = backtester.generate_config_variations(n_variations=10)

        assert len(configs) == 10

        # 각 Config는 필수 필드를 가져야 함
        for config in configs:
            assert "threshold_ratio" in config
            assert "filter_weights" in config
            assert "thresholds" in config
            # min_trades는 가중치에 없어야 함 (정합성 규칙)
            assert "min_trades" not in config["filter_weights"]

    def test_run_single_backtest_generates_snapshot(
        self, temp_data_dir, sample_ohlcv_data, mock_backtest_result
    ):
        """단일 백테스트 실행 시 스냅샷 생성"""
        from src.ml.bulk_backtester import BulkBacktester
        from src.domain.value_objects.cost_policy import CostPolicy

        backtester = BulkBacktester(
            data_path=temp_data_dir,
            cost_policy=CostPolicy.default(),
        )

        # 백테스트 실행을 모킹
        with patch.object(backtester, "_run_backtest", return_value=mock_backtest_result):
            config = {
                "threshold_ratio": 0.625,
                "filter_weights": {"max_drawdown": 2.0, "sortino_ratio": 1.5},
                "thresholds": {"min_return": 9.0, "min_sharpe_ratio": 0.7},
                "tier1_filters": {"return", "sharpe_ratio", "profit_factor", "expectancy"},
            }

            snapshot = backtester.run_single_backtest(
                ticker="KRW-BTC",
                data=sample_ohlcv_data,
                config=config,
            )

        assert snapshot is not None
        assert snapshot.ticker == "KRW-BTC"
        assert snapshot.reproducibility is not None
        assert snapshot.reproducibility.cost_policy_version == "v1.0.0"

    def test_run_bulk_backtest(self, temp_data_dir, sample_ohlcv_data, mock_backtest_result):
        """대량 백테스트 실행"""
        from src.ml.bulk_backtester import BulkBacktester
        from src.domain.value_objects.cost_policy import CostPolicy

        backtester = BulkBacktester(
            data_path=temp_data_dir,
            cost_policy=CostPolicy.default(),
        )

        # 백테스트 실행을 모킹
        with patch.object(backtester, "_run_backtest", return_value=mock_backtest_result):
            snapshots = backtester.run_bulk_backtest(
                tickers=["KRW-BTC", "KRW-ETH"],
                data_dict={"KRW-BTC": sample_ohlcv_data, "KRW-ETH": sample_ohlcv_data},
                n_config_variations=3,
            )

        # 2개 코인 * 3개 Config = 6개 스냅샷
        assert len(snapshots) == 6

    def test_cost_applied_to_metrics(self, temp_data_dir, sample_ohlcv_data):
        """비용이 메트릭에 반영되는지 테스트"""
        from src.ml.bulk_backtester import BulkBacktester
        from src.domain.value_objects.cost_policy import CostPolicy

        cost_policy = CostPolicy.default()
        backtester = BulkBacktester(
            data_path=temp_data_dir,
            cost_policy=cost_policy,
        )

        gross_return = 0.10  # 10%
        order_size = 100_000_000  # 1억
        daily_volume = 100_000_000_000  # 1000억
        volatility = 0.02

        net_return = backtester.apply_costs(
            gross_return=gross_return,
            order_size=order_size,
            daily_volume=daily_volume,
            volatility=volatility,
        )

        # 비용 차감 후 순수익은 총수익보다 작아야 함
        assert net_return < gross_return
        assert net_return > 0  # 여전히 양수

    def test_min_trades_not_in_weights(self, temp_data_dir):
        """min_trades가 가중치에 포함되지 않는지 검증 (정합성 규칙)"""
        from src.ml.bulk_backtester import BulkBacktester
        from src.domain.value_objects.cost_policy import CostPolicy

        backtester = BulkBacktester(
            data_path=temp_data_dir,
            cost_policy=CostPolicy.default(),
        )

        configs = backtester.generate_config_variations(n_variations=20)

        for config in configs:
            # min_trades는 가중치에 없어야 함
            assert "min_trades" not in config["filter_weights"]
            # min_trades는 thresholds에만 있어야 함
            assert "min_trades" in config["thresholds"]


class TestConfigVariationGenerator:
    """Config 변형 생성기 테스트"""

    def test_threshold_ratio_in_valid_range(self, temp_data_dir):
        """threshold_ratio가 유효한 범위 내에 있는지 테스트"""
        from src.ml.bulk_backtester import BulkBacktester
        from src.domain.value_objects.cost_policy import CostPolicy

        backtester = BulkBacktester(
            data_path=temp_data_dir,
            cost_policy=CostPolicy.default(),
        )

        configs = backtester.generate_config_variations(n_variations=50)

        for config in configs:
            # threshold_ratio는 0.50 ~ 0.85 범위
            assert 0.50 <= config["threshold_ratio"] <= 0.85

    def test_filter_weights_in_valid_range(self, temp_data_dir):
        """필터 가중치가 유효한 범위 내에 있는지 테스트"""
        from src.ml.bulk_backtester import BulkBacktester
        from src.domain.value_objects.cost_policy import CostPolicy

        backtester = BulkBacktester(
            data_path=temp_data_dir,
            cost_policy=CostPolicy.default(),
        )

        configs = backtester.generate_config_variations(n_variations=50)

        for config in configs:
            weights = config["filter_weights"]
            # 모든 가중치는 0 이상
            for key, value in weights.items():
                assert value >= 0, f"{key}={value}"

    def test_tier1_filters_include_required(self, temp_data_dir):
        """Tier 1 필터에 필수 필터가 포함되는지 테스트"""
        from src.ml.bulk_backtester import BulkBacktester
        from src.domain.value_objects.cost_policy import CostPolicy

        backtester = BulkBacktester(
            data_path=temp_data_dir,
            cost_policy=CostPolicy.default(),
        )

        configs = backtester.generate_config_variations(n_variations=20)

        for config in configs:
            tier1 = config["tier1_filters"]
            # return과 sharpe_ratio는 필수 포함
            assert "return" in tier1
            assert "sharpe_ratio" in tier1
