"""
ParquetTradeDataAdapter 테스트
"""

import pytest
import tempfile
import shutil
from datetime import datetime
from decimal import Decimal
from pathlib import Path


@pytest.fixture
def temp_data_dir():
    """임시 데이터 디렉토리"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_metadata():
    """샘플 재현성 메타데이터"""
    from src.domain.value_objects.reproducibility_metadata import ReproducibilityMetadata

    return ReproducibilityMetadata.from_current_env(
        data_hash="sha256:abc123",
        cost_policy_version="v1.0.0",
        fee_rate=0.0005,
        slippage_model="sqrt",
    )


@pytest.fixture
def sample_snapshot(sample_metadata):
    """샘플 스냅샷"""
    from src.domain.entities.ml_snapshot import BacktestFilterSnapshot

    return BacktestFilterSnapshot(
        snapshot_id="SNAP001",
        timestamp=datetime.now(),
        ticker="KRW-BTC",
        filter_results={"return": True, "sharpe_ratio": True},
        filter_values={"return": 12.5, "sharpe_ratio": 1.1},
        tier1_passed=True,
        tier1_filters={"return", "sharpe_ratio"},
        weighted_score=6.5,
        threshold_ratio=0.625,
        final_passed=True,
        config_version="v1.0.0",
        filter_weights={"max_drawdown": 2.0},
        thresholds={"min_return": 9.0},
        reproducibility=sample_metadata,
    )


@pytest.fixture
def sample_outcome(sample_metadata):
    """샘플 거래 결과"""
    from src.domain.entities.ml_snapshot import TradeOutcome

    return TradeOutcome(
        outcome_id="OUT001",
        entry_snapshot_id="SNAP001",
        entry_price=Decimal("50000000"),
        exit_price=Decimal("55000000"),
        gross_pnl_pct=0.10,
        fee_paid=Decimal("50000"),
        slippage_pct=0.0005,
        net_pnl_pct=0.098,
        net_pnl_amount=Decimal("4900000"),
        holding_hours=24.0,
        exit_reason="take_profit",
        daily_volume=Decimal("100000000000"),
        label="profit",
        label_score=0.098,
        cost_policy_version="v1.0.0",
        reproducibility=sample_metadata,
    )


class TestParquetTradeDataAdapter:
    """ParquetTradeDataAdapter 테스트"""

    def test_adapter_initialization(self, temp_data_dir):
        """어댑터 초기화 테스트"""
        from src.infrastructure.adapters.persistence.parquet_trade_data_adapter import (
            ParquetTradeDataAdapter,
        )

        adapter = ParquetTradeDataAdapter(base_path=temp_data_dir)

        assert adapter.snapshots_path.exists()
        assert adapter.outcomes_path.exists()

    def test_save_and_get_snapshot(self, temp_data_dir, sample_snapshot):
        """스냅샷 저장 및 조회 테스트"""
        from src.infrastructure.adapters.persistence.parquet_trade_data_adapter import (
            ParquetTradeDataAdapter,
        )

        adapter = ParquetTradeDataAdapter(base_path=temp_data_dir)

        # 저장
        adapter.save_snapshot(sample_snapshot)

        # 조회
        retrieved = adapter.get_snapshot_by_id("SNAP001")

        assert retrieved is not None
        assert retrieved.snapshot_id == "SNAP001"
        assert retrieved.ticker == "KRW-BTC"
        assert retrieved.weighted_score == 6.5

    def test_save_and_get_outcome(self, temp_data_dir, sample_outcome):
        """거래 결과 저장 및 조회 테스트"""
        from src.infrastructure.adapters.persistence.parquet_trade_data_adapter import (
            ParquetTradeDataAdapter,
        )

        adapter = ParquetTradeDataAdapter(base_path=temp_data_dir)

        # 저장
        adapter.save_outcome(sample_outcome)

        # 조회
        outcomes = adapter.get_outcomes_by_snapshot_id("SNAP001")

        assert len(outcomes) == 1
        assert outcomes[0].outcome_id == "OUT001"
        assert outcomes[0].label == "profit"

    def test_save_multiple_snapshots(self, temp_data_dir, sample_metadata):
        """다중 스냅샷 저장 테스트"""
        from src.infrastructure.adapters.persistence.parquet_trade_data_adapter import (
            ParquetTradeDataAdapter,
        )
        from src.domain.entities.ml_snapshot import BacktestFilterSnapshot

        adapter = ParquetTradeDataAdapter(base_path=temp_data_dir)

        # 여러 스냅샷 생성
        snapshots = []
        for i in range(5):
            snapshot = BacktestFilterSnapshot(
                snapshot_id=f"SNAP00{i}",
                timestamp=datetime.now(),
                ticker=f"KRW-{'BTC' if i % 2 == 0 else 'ETH'}",
                filter_results={"return": True},
                filter_values={"return": 10.0 + i},
                tier1_passed=True,
                tier1_filters={"return"},
                weighted_score=5.0 + i * 0.5,
                threshold_ratio=0.625,
                final_passed=True,
                config_version="v1.0.0",
                filter_weights={},
                thresholds={},
                reproducibility=sample_metadata,
            )
            snapshots.append(snapshot)

        # 일괄 저장
        adapter.save_snapshots(snapshots)

        # 검증
        assert adapter.count_snapshots() == 5

        # 종목별 조회
        btc_snapshots = adapter.get_snapshots_by_ticker("KRW-BTC")
        assert len(btc_snapshots) == 3

        eth_snapshots = adapter.get_snapshots_by_ticker("KRW-ETH")
        assert len(eth_snapshots) == 2

    def test_count_methods(self, temp_data_dir, sample_snapshot, sample_outcome):
        """카운트 메서드 테스트"""
        from src.infrastructure.adapters.persistence.parquet_trade_data_adapter import (
            ParquetTradeDataAdapter,
        )

        adapter = ParquetTradeDataAdapter(base_path=temp_data_dir)

        # 초기 상태
        assert adapter.count_snapshots() == 0
        assert adapter.count_outcomes() == 0

        # 저장 후
        adapter.save_snapshot(sample_snapshot)
        adapter.save_outcome(sample_outcome)

        assert adapter.count_snapshots() == 1
        assert adapter.count_outcomes() == 1

    def test_reproducibility_metadata_preserved(self, temp_data_dir, sample_snapshot):
        """재현성 메타데이터 보존 테스트"""
        from src.infrastructure.adapters.persistence.parquet_trade_data_adapter import (
            ParquetTradeDataAdapter,
        )

        adapter = ParquetTradeDataAdapter(base_path=temp_data_dir)

        # 저장
        adapter.save_snapshot(sample_snapshot)

        # 조회
        retrieved = adapter.get_snapshot_by_id("SNAP001")

        # 메타데이터 검증
        assert retrieved.reproducibility.data_hash == "sha256:abc123"
        assert retrieved.reproducibility.cost_policy_version == "v1.0.0"
        assert retrieved.reproducibility.fee_rate == 0.0005
        assert retrieved.reproducibility.slippage_model == "sqrt"
