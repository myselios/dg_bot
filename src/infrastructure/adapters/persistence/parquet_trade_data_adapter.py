"""
ParquetTradeDataAdapter - Parquet 기반 ML 데이터 저장 어댑터

백테스트 필터 스냅샷 및 거래 결과를 Parquet 파일로 저장
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime

import pandas as pd

from src.application.ports.outbound.trade_data_port import TradeDataPort
from src.domain.entities.ml_snapshot import BacktestFilterSnapshot, TradeOutcome
from src.domain.value_objects.reproducibility_metadata import ReproducibilityMetadata

logger = logging.getLogger(__name__)


class ParquetTradeDataAdapter(TradeDataPort):
    """
    Parquet 기반 ML 데이터 저장 어댑터

    백테스트 필터 스냅샷과 거래 결과를 Parquet 파일로 저장한다.
    파티셔닝: 연/월 기준으로 저장하여 조회 성능 최적화
    """

    def __init__(self, base_path: str = "data/ml"):
        """
        Args:
            base_path: 데이터 저장 기본 경로
        """
        self.base_path = Path(base_path)
        self.snapshots_path = self.base_path / "filter_snapshots"
        self.outcomes_path = self.base_path / "trade_outcomes"

        # 디렉토리 생성
        self.snapshots_path.mkdir(parents=True, exist_ok=True)
        self.outcomes_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"ParquetTradeDataAdapter 초기화: {self.base_path}")

    def save_snapshot(self, snapshot: BacktestFilterSnapshot) -> None:
        """백테스트 필터 스냅샷 저장"""
        self.save_snapshots([snapshot])

    def save_snapshots(self, snapshots: List[BacktestFilterSnapshot]) -> None:
        """백테스트 필터 스냅샷 일괄 저장"""
        if not snapshots:
            return

        # DataFrame으로 변환
        records = [self._snapshot_to_record(s) for s in snapshots]
        df = pd.DataFrame(records)

        # 파티션 키 생성 (연/월)
        df["_year"] = pd.to_datetime(df["timestamp"]).dt.year
        df["_month"] = pd.to_datetime(df["timestamp"]).dt.month

        # 파티션별로 저장
        for (year, month), group in df.groupby(["_year", "_month"]):
            partition_path = self.snapshots_path / f"year={year}" / f"month={month:02d}"
            partition_path.mkdir(parents=True, exist_ok=True)

            file_path = partition_path / f"snapshots_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"

            # 파티션 키 컬럼 제거
            group_to_save = group.drop(columns=["_year", "_month"])

            # 기존 파일이 있으면 병합
            existing_files = list(partition_path.glob("*.parquet"))
            if existing_files:
                existing_df = pd.concat([pd.read_parquet(f) for f in existing_files])
                group_to_save = pd.concat([existing_df, group_to_save]).drop_duplicates(
                    subset=["snapshot_id"], keep="last"
                )
                # 기존 파일 삭제
                for f in existing_files:
                    f.unlink()

            group_to_save.to_parquet(file_path, index=False)
            logger.debug(f"스냅샷 저장: {file_path} ({len(group_to_save)}개)")

    def save_outcome(self, outcome: TradeOutcome) -> None:
        """거래 결과 저장"""
        self.save_outcomes([outcome])

    def save_outcomes(self, outcomes: List[TradeOutcome]) -> None:
        """거래 결과 일괄 저장"""
        if not outcomes:
            return

        # DataFrame으로 변환
        records = [self._outcome_to_record(o) for o in outcomes]
        df = pd.DataFrame(records)

        # 파티션 키 생성 (스냅샷 ID 기준)
        timestamp = datetime.now()
        partition_path = self.outcomes_path / f"year={timestamp.year}" / f"month={timestamp.month:02d}"
        partition_path.mkdir(parents=True, exist_ok=True)

        file_path = partition_path / f"outcomes_{timestamp.strftime('%Y%m%d_%H%M%S')}.parquet"

        # 기존 파일이 있으면 병합
        existing_files = list(partition_path.glob("*.parquet"))
        if existing_files:
            existing_df = pd.concat([pd.read_parquet(f) for f in existing_files])
            df = pd.concat([existing_df, df]).drop_duplicates(subset=["outcome_id"], keep="last")
            for f in existing_files:
                f.unlink()

        df.to_parquet(file_path, index=False)
        logger.debug(f"거래 결과 저장: {file_path} ({len(df)}개)")

    def get_snapshot_by_id(self, snapshot_id: str) -> Optional[BacktestFilterSnapshot]:
        """스냅샷 ID로 조회"""
        all_snapshots = self.get_all_snapshots()
        for snapshot in all_snapshots:
            if snapshot.snapshot_id == snapshot_id:
                return snapshot
        return None

    def get_snapshots_by_ticker(
        self, ticker: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> List[BacktestFilterSnapshot]:
        """종목별 스냅샷 조회"""
        all_snapshots = self.get_all_snapshots(start_date, end_date)
        return [s for s in all_snapshots if s.ticker == ticker]

    def get_outcomes_by_snapshot_id(self, snapshot_id: str) -> List[TradeOutcome]:
        """스냅샷 ID로 연결된 거래 결과 조회"""
        all_outcomes = self.get_all_outcomes()
        return [o for o in all_outcomes if o.entry_snapshot_id == snapshot_id]

    def get_all_snapshots(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> List[BacktestFilterSnapshot]:
        """전체 스냅샷 조회"""
        parquet_files = list(self.snapshots_path.glob("**/*.parquet"))
        if not parquet_files:
            return []

        df = pd.concat([pd.read_parquet(f) for f in parquet_files])

        # 날짜 필터링
        if start_date or end_date:
            df["_ts"] = pd.to_datetime(df["timestamp"])
            if start_date:
                df = df[df["_ts"] >= start_date]
            if end_date:
                df = df[df["_ts"] <= end_date]
            df = df.drop(columns=["_ts"])

        return [self._record_to_snapshot(row) for _, row in df.iterrows()]

    def get_all_outcomes(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> List[TradeOutcome]:
        """전체 거래 결과 조회"""
        parquet_files = list(self.outcomes_path.glob("**/*.parquet"))
        if not parquet_files:
            return []

        df = pd.concat([pd.read_parquet(f) for f in parquet_files])
        return [self._record_to_outcome(row) for _, row in df.iterrows()]

    def count_snapshots(self) -> int:
        """스냅샷 총 개수 조회"""
        parquet_files = list(self.snapshots_path.glob("**/*.parquet"))
        if not parquet_files:
            return 0
        return sum(len(pd.read_parquet(f)) for f in parquet_files)

    def count_outcomes(self) -> int:
        """거래 결과 총 개수 조회"""
        parquet_files = list(self.outcomes_path.glob("**/*.parquet"))
        if not parquet_files:
            return 0
        return sum(len(pd.read_parquet(f)) for f in parquet_files)

    def _snapshot_to_record(self, snapshot: BacktestFilterSnapshot) -> dict:
        """스냅샷을 레코드로 변환"""
        return {
            "snapshot_id": snapshot.snapshot_id,
            "timestamp": snapshot.timestamp.isoformat(),
            "ticker": snapshot.ticker,
            "filter_results": json.dumps(snapshot.filter_results),
            "filter_values": json.dumps(snapshot.filter_values),
            "tier1_passed": snapshot.tier1_passed,
            "tier1_filters": json.dumps(list(snapshot.tier1_filters)),
            "weighted_score": snapshot.weighted_score,
            "threshold_ratio": snapshot.threshold_ratio,
            "final_passed": snapshot.final_passed,
            "config_version": snapshot.config_version,
            "filter_weights": json.dumps(snapshot.filter_weights),
            "thresholds": json.dumps(snapshot.thresholds),
            # 재현성 메타데이터
            "data_hash": snapshot.reproducibility.data_hash,
            "data_version": snapshot.reproducibility.data_version,
            "data_source": snapshot.reproducibility.data_source,
            "code_version": snapshot.reproducibility.code_version,
            "config_version_meta": snapshot.reproducibility.config_version,
            "cost_policy_version": snapshot.reproducibility.cost_policy_version,
            "fee_rate": snapshot.reproducibility.fee_rate,
            "slippage_model": snapshot.reproducibility.slippage_model,
            "exchange_env": snapshot.reproducibility.exchange_env,
            "api_version": snapshot.reproducibility.api_version,
            "python_version": snapshot.reproducibility.python_version,
            "numpy_version": snapshot.reproducibility.numpy_version,
            "pandas_version": snapshot.reproducibility.pandas_version,
            "meta_timestamp": snapshot.reproducibility.timestamp.isoformat(),
        }

    def _record_to_snapshot(self, row: pd.Series) -> BacktestFilterSnapshot:
        """레코드를 스냅샷으로 변환"""
        metadata = ReproducibilityMetadata(
            data_hash=row["data_hash"],
            data_version=row["data_version"],
            data_source=row["data_source"],
            code_version=row["code_version"],
            config_version=row["config_version_meta"],
            cost_policy_version=row["cost_policy_version"],
            fee_rate=row["fee_rate"],
            slippage_model=row["slippage_model"],
            exchange_env=row["exchange_env"],
            api_version=row["api_version"],
            python_version=row["python_version"],
            numpy_version=row["numpy_version"],
            pandas_version=row["pandas_version"],
            timestamp=datetime.fromisoformat(row["meta_timestamp"]),
        )

        return BacktestFilterSnapshot(
            snapshot_id=row["snapshot_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            ticker=row["ticker"],
            filter_results=json.loads(row["filter_results"]),
            filter_values=json.loads(row["filter_values"]),
            tier1_passed=row["tier1_passed"],
            tier1_filters=set(json.loads(row["tier1_filters"])),
            weighted_score=row["weighted_score"],
            threshold_ratio=row["threshold_ratio"],
            final_passed=row["final_passed"],
            config_version=row["config_version"],
            filter_weights=json.loads(row["filter_weights"]),
            thresholds=json.loads(row["thresholds"]),
            reproducibility=metadata,
        )

    def _outcome_to_record(self, outcome: TradeOutcome) -> dict:
        """거래 결과를 레코드로 변환"""
        return {
            "outcome_id": outcome.outcome_id,
            "entry_snapshot_id": outcome.entry_snapshot_id,
            "entry_price": str(outcome.entry_price),
            "exit_price": str(outcome.exit_price),
            "gross_pnl_pct": outcome.gross_pnl_pct,
            "fee_paid": str(outcome.fee_paid),
            "slippage_pct": outcome.slippage_pct,
            "net_pnl_pct": outcome.net_pnl_pct,
            "net_pnl_amount": str(outcome.net_pnl_amount),
            "holding_hours": outcome.holding_hours,
            "exit_reason": outcome.exit_reason,
            "daily_volume": str(outcome.daily_volume),
            "label": outcome.label,
            "label_score": outcome.label_score,
            "cost_policy_version": outcome.cost_policy_version,
            # 재현성 메타데이터
            "data_hash": outcome.reproducibility.data_hash,
            "data_version": outcome.reproducibility.data_version,
            "data_source": outcome.reproducibility.data_source,
            "code_version": outcome.reproducibility.code_version,
            "config_version": outcome.reproducibility.config_version,
            "cost_policy_version_meta": outcome.reproducibility.cost_policy_version,
            "fee_rate": outcome.reproducibility.fee_rate,
            "slippage_model": outcome.reproducibility.slippage_model,
            "exchange_env": outcome.reproducibility.exchange_env,
            "api_version": outcome.reproducibility.api_version,
            "python_version": outcome.reproducibility.python_version,
            "numpy_version": outcome.reproducibility.numpy_version,
            "pandas_version": outcome.reproducibility.pandas_version,
            "meta_timestamp": outcome.reproducibility.timestamp.isoformat(),
        }

    def _record_to_outcome(self, row: pd.Series) -> TradeOutcome:
        """레코드를 거래 결과로 변환"""
        from decimal import Decimal

        metadata = ReproducibilityMetadata(
            data_hash=row["data_hash"],
            data_version=row["data_version"],
            data_source=row["data_source"],
            code_version=row["code_version"],
            config_version=row["config_version"],
            cost_policy_version=row["cost_policy_version_meta"],
            fee_rate=row["fee_rate"],
            slippage_model=row["slippage_model"],
            exchange_env=row["exchange_env"],
            api_version=row["api_version"],
            python_version=row["python_version"],
            numpy_version=row["numpy_version"],
            pandas_version=row["pandas_version"],
            timestamp=datetime.fromisoformat(row["meta_timestamp"]),
        )

        return TradeOutcome(
            outcome_id=row["outcome_id"],
            entry_snapshot_id=row["entry_snapshot_id"],
            entry_price=Decimal(row["entry_price"]),
            exit_price=Decimal(row["exit_price"]),
            gross_pnl_pct=row["gross_pnl_pct"],
            fee_paid=Decimal(row["fee_paid"]),
            slippage_pct=row["slippage_pct"],
            net_pnl_pct=row["net_pnl_pct"],
            net_pnl_amount=Decimal(row["net_pnl_amount"]),
            holding_hours=row["holding_hours"],
            exit_reason=row["exit_reason"],
            daily_volume=Decimal(row["daily_volume"]),
            label=row["label"],
            label_score=row["label_score"],
            cost_policy_version=row["cost_policy_version"],
            reproducibility=metadata,
        )
