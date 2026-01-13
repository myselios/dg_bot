"""
BacktestFilterSnapshot 및 TradeOutcome 테스트

ML 파이프라인의 핵심 데이터 구조 테스트
"""

import pytest
from datetime import datetime
from decimal import Decimal


class TestBacktestFilterSnapshot:
    """BacktestFilterSnapshot 테스트"""

    def test_snapshot_has_required_fields(self):
        """스냅샷은 필수 필드를 가져야 한다"""
        from src.domain.entities.ml_snapshot import BacktestFilterSnapshot
        from src.domain.value_objects.reproducibility_metadata import (
            ReproducibilityMetadata,
        )

        metadata = ReproducibilityMetadata(
            data_hash="sha256:abc123",
            data_version="v1.0.0",
            data_source="local_parquet",
            code_version="abc1234",
            config_version="v1.2.0",
            cost_policy_version="v1.0.0",
            fee_rate=0.0005,
            slippage_model="sqrt",
            exchange_env="production",
            api_version="v1",
            python_version="3.11.0",
            numpy_version="1.24.0",
            pandas_version="2.0.0",
            timestamp=datetime.now(),
        )

        snapshot = BacktestFilterSnapshot(
            snapshot_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
            timestamp=datetime.now(),
            ticker="KRW-BTC",
            filter_results={"return": True, "sharpe_ratio": True, "profit_factor": False},
            filter_values={"return": 13.8, "sharpe_ratio": 1.2, "profit_factor": 1.3},
            tier1_passed=True,
            tier1_filters={"return", "sharpe_ratio", "profit_factor", "expectancy"},
            weighted_score=6.5,
            threshold_ratio=0.625,
            final_passed=True,
            config_version="v1.0.0",
            filter_weights={"max_drawdown": 2.0, "sortino_ratio": 1.5},
            thresholds={"min_return": 9.0, "min_sharpe_ratio": 0.7},
            reproducibility=metadata,
        )

        assert snapshot.snapshot_id is not None
        assert snapshot.ticker == "KRW-BTC"
        assert snapshot.tier1_passed is True
        assert snapshot.weighted_score == 6.5
        assert snapshot.reproducibility.data_hash == "sha256:abc123"

    def test_snapshot_filter_results_validation(self):
        """필터 결과는 bool 값이어야 한다"""
        from src.domain.entities.ml_snapshot import BacktestFilterSnapshot
        from src.domain.value_objects.reproducibility_metadata import (
            ReproducibilityMetadata,
        )

        metadata = ReproducibilityMetadata.from_current_env(
            data_hash="sha256:abc123",
            cost_policy_version="v1.0.0",
            fee_rate=0.0005,
            slippage_model="sqrt",
        )

        # 유효한 필터 결과
        snapshot = BacktestFilterSnapshot(
            snapshot_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
            timestamp=datetime.now(),
            ticker="KRW-BTC",
            filter_results={"return": True, "sharpe_ratio": False},
            filter_values={"return": 10.0, "sharpe_ratio": 0.5},
            tier1_passed=True,
            tier1_filters={"return", "sharpe_ratio"},
            weighted_score=5.0,
            threshold_ratio=0.625,
            final_passed=True,
            config_version="v1.0.0",
            filter_weights={},
            thresholds={},
            reproducibility=metadata,
        )
        assert snapshot.filter_results["return"] is True

    def test_snapshot_to_dict(self):
        """스냅샷을 딕셔너리로 변환할 수 있어야 한다"""
        from src.domain.entities.ml_snapshot import BacktestFilterSnapshot
        from src.domain.value_objects.reproducibility_metadata import (
            ReproducibilityMetadata,
        )

        metadata = ReproducibilityMetadata.from_current_env(
            data_hash="sha256:abc123",
            cost_policy_version="v1.0.0",
            fee_rate=0.0005,
            slippage_model="sqrt",
        )

        snapshot = BacktestFilterSnapshot(
            snapshot_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
            timestamp=datetime.now(),
            ticker="KRW-BTC",
            filter_results={"return": True},
            filter_values={"return": 10.0},
            tier1_passed=True,
            tier1_filters={"return"},
            weighted_score=5.0,
            threshold_ratio=0.625,
            final_passed=True,
            config_version="v1.0.0",
            filter_weights={},
            thresholds={},
            reproducibility=metadata,
        )

        data = snapshot.to_dict()
        assert data["snapshot_id"] == "01ARZ3NDEKTSV4RRFFQ69G5FAV"
        assert data["ticker"] == "KRW-BTC"
        assert "reproducibility" in data


class TestTradeOutcome:
    """TradeOutcome 테스트"""

    def test_outcome_has_required_fields(self):
        """거래 결과는 필수 필드를 가져야 한다"""
        from src.domain.entities.ml_snapshot import TradeOutcome
        from src.domain.value_objects.reproducibility_metadata import (
            ReproducibilityMetadata,
        )

        metadata = ReproducibilityMetadata.from_current_env(
            data_hash="sha256:abc123",
            cost_policy_version="v1.0.0",
            fee_rate=0.0005,
            slippage_model="sqrt",
        )

        outcome = TradeOutcome(
            outcome_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
            entry_snapshot_id="01ARZ3NDEKTSV4RRFFQ69G5FAW",
            entry_price=Decimal("50000000"),
            exit_price=Decimal("55000000"),
            gross_pnl_pct=0.10,
            fee_paid=Decimal("50000"),
            slippage_pct=0.0005,
            net_pnl_pct=0.098,
            net_pnl_amount=Decimal("4900000"),
            holding_hours=24.5,
            exit_reason="take_profit",
            daily_volume=Decimal("100000000000"),
            label="profit",
            label_score=0.098,
            cost_policy_version="v1.0.0",
            reproducibility=metadata,
        )

        assert outcome.outcome_id is not None
        assert outcome.gross_pnl_pct == 0.10
        assert outcome.net_pnl_pct == 0.098
        assert outcome.label == "profit"

    def test_outcome_cost_details(self):
        """거래 결과는 비용 상세를 포함해야 한다"""
        from src.domain.entities.ml_snapshot import TradeOutcome
        from src.domain.value_objects.reproducibility_metadata import (
            ReproducibilityMetadata,
        )

        metadata = ReproducibilityMetadata.from_current_env(
            data_hash="sha256:abc123",
            cost_policy_version="v1.0.0",
            fee_rate=0.0005,
            slippage_model="sqrt",
        )

        outcome = TradeOutcome(
            outcome_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
            entry_snapshot_id="01ARZ3NDEKTSV4RRFFQ69G5FAW",
            entry_price=Decimal("50000000"),
            exit_price=Decimal("45000000"),  # 손실
            gross_pnl_pct=-0.10,
            fee_paid=Decimal("45000"),
            slippage_pct=0.0008,
            net_pnl_pct=-0.102,
            net_pnl_amount=Decimal("-5100000"),
            holding_hours=12.0,
            exit_reason="stop_loss",
            daily_volume=Decimal("50000000000"),
            label="loss",
            label_score=-0.102,
            cost_policy_version="v1.0.0",
            reproducibility=metadata,
        )

        assert outcome.fee_paid == Decimal("45000")
        assert outcome.slippage_pct == 0.0008
        assert outcome.label == "loss"

    def test_outcome_label_calculation(self):
        """라벨은 수익률 기반으로 계산되어야 한다"""
        from src.domain.entities.ml_snapshot import TradeOutcome
        from src.domain.value_objects.reproducibility_metadata import (
            ReproducibilityMetadata,
        )

        metadata = ReproducibilityMetadata.from_current_env(
            data_hash="sha256:abc123",
            cost_policy_version="v1.0.0",
            fee_rate=0.0005,
            slippage_model="sqrt",
        )

        # 이익
        outcome_profit = TradeOutcome.create(
            entry_snapshot_id="snap1",
            entry_price=Decimal("50000000"),
            exit_price=Decimal("55000000"),
            fee_paid=Decimal("50000"),
            slippage_pct=0.0005,
            holding_hours=24.0,
            exit_reason="take_profit",
            daily_volume=Decimal("100000000000"),
            cost_policy_version="v1.0.0",
            reproducibility=metadata,
        )
        assert outcome_profit.label == "profit"

        # 손실
        outcome_loss = TradeOutcome.create(
            entry_snapshot_id="snap2",
            entry_price=Decimal("50000000"),
            exit_price=Decimal("45000000"),
            fee_paid=Decimal("45000"),
            slippage_pct=0.0005,
            holding_hours=12.0,
            exit_reason="stop_loss",
            daily_volume=Decimal("100000000000"),
            cost_policy_version="v1.0.0",
            reproducibility=metadata,
        )
        assert outcome_loss.label == "loss"

    def test_outcome_to_dict(self):
        """거래 결과를 딕셔너리로 변환할 수 있어야 한다"""
        from src.domain.entities.ml_snapshot import TradeOutcome
        from src.domain.value_objects.reproducibility_metadata import (
            ReproducibilityMetadata,
        )

        metadata = ReproducibilityMetadata.from_current_env(
            data_hash="sha256:abc123",
            cost_policy_version="v1.0.0",
            fee_rate=0.0005,
            slippage_model="sqrt",
        )

        outcome = TradeOutcome(
            outcome_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
            entry_snapshot_id="01ARZ3NDEKTSV4RRFFQ69G5FAW",
            entry_price=Decimal("50000000"),
            exit_price=Decimal("55000000"),
            gross_pnl_pct=0.10,
            fee_paid=Decimal("50000"),
            slippage_pct=0.0005,
            net_pnl_pct=0.098,
            net_pnl_amount=Decimal("4900000"),
            holding_hours=24.5,
            exit_reason="take_profit",
            daily_volume=Decimal("100000000000"),
            label="profit",
            label_score=0.098,
            cost_policy_version="v1.0.0",
            reproducibility=metadata,
        )

        data = outcome.to_dict()
        assert data["outcome_id"] == "01ARZ3NDEKTSV4RRFFQ69G5FAV"
        assert data["label"] == "profit"
        assert "reproducibility" in data
