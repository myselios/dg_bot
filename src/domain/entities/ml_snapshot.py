"""
ML 파이프라인 스냅샷 엔티티

BacktestFilterSnapshot: 백테스트 시 필터 결과 스냅샷
TradeOutcome: 거래 결과 (비용 상세 포함)
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from decimal import Decimal
from typing import Dict, Set, Optional
import json
import uuid

from src.domain.value_objects.reproducibility_metadata import ReproducibilityMetadata


@dataclass
class BacktestFilterSnapshot:
    """
    백테스트 필터 결과 스냅샷

    백테스트 실행 시점의 필터 상태와 결과를 저장한다.
    재현성 메타데이터를 포함하여 동일한 결과를 재현할 수 있도록 한다.

    Attributes:
        snapshot_id: 고유 식별자 (ULID)
        timestamp: 스냅샷 생성 시각
        ticker: 종목 코드 (e.g., "KRW-BTC")
        filter_results: 필터별 통과 여부 (e.g., {"return": True, "sharpe_ratio": False})
        filter_values: 필터별 실제 값 (e.g., {"return": 13.8, "sharpe_ratio": 0.9})
        tier1_passed: Tier 1 (AND) 필터 통과 여부
        tier1_filters: Tier 1에 포함된 필터 집합
        weighted_score: 가중치 점수 (0 ~ max_weight)
        threshold_ratio: 통과 임계값 비율 (0 ~ 1)
        final_passed: 최종 통과 여부
        config_version: FilterConfig 버전
        filter_weights: 사용된 필터 가중치 (min_trades 제외)
        thresholds: 사용된 필터 임계값
        reproducibility: 재현성 메타데이터
    """

    snapshot_id: str
    timestamp: datetime
    ticker: str
    filter_results: Dict[str, bool]
    filter_values: Dict[str, float]
    tier1_passed: bool
    tier1_filters: Set[str]
    weighted_score: float
    threshold_ratio: float
    final_passed: bool
    config_version: str
    filter_weights: Dict[str, float]
    thresholds: Dict[str, float]
    reproducibility: ReproducibilityMetadata

    def to_dict(self) -> dict:
        """딕셔너리로 변환 (Parquet 저장용)"""
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp.isoformat(),
            "ticker": self.ticker,
            "filter_results": json.dumps(self.filter_results),
            "filter_values": json.dumps(self.filter_values),
            "tier1_passed": self.tier1_passed,
            "tier1_filters": json.dumps(list(self.tier1_filters)),
            "weighted_score": self.weighted_score,
            "threshold_ratio": self.threshold_ratio,
            "final_passed": self.final_passed,
            "config_version": self.config_version,
            "filter_weights": json.dumps(self.filter_weights),
            "thresholds": json.dumps(self.thresholds),
            "reproducibility": self.reproducibility.to_dict(),
        }

    @classmethod
    def create(
        cls,
        ticker: str,
        filter_results: Dict[str, bool],
        filter_values: Dict[str, float],
        tier1_passed: bool,
        tier1_filters: Set[str],
        weighted_score: float,
        threshold_ratio: float,
        final_passed: bool,
        config_version: str,
        filter_weights: Dict[str, float],
        thresholds: Dict[str, float],
        reproducibility: ReproducibilityMetadata,
    ) -> "BacktestFilterSnapshot":
        """스냅샷 생성 팩토리 메서드"""
        return cls(
            snapshot_id=str(uuid.uuid4()).replace("-", "").upper()[:26],
            timestamp=datetime.now(),
            ticker=ticker,
            filter_results=filter_results,
            filter_values=filter_values,
            tier1_passed=tier1_passed,
            tier1_filters=tier1_filters,
            weighted_score=weighted_score,
            threshold_ratio=threshold_ratio,
            final_passed=final_passed,
            config_version=config_version,
            filter_weights=filter_weights,
            thresholds=thresholds,
            reproducibility=reproducibility,
        )


@dataclass
class TradeOutcome:
    """
    거래 결과 (비용 상세 포함)

    청산 시점의 거래 결과를 저장한다.
    비용(수수료, 슬리피지)을 상세히 기록하여 실현 가능한 수익을 계산한다.

    Attributes:
        outcome_id: 고유 식별자
        entry_snapshot_id: 진입 시점 BacktestFilterSnapshot 참조
        entry_price: 진입 가격
        exit_price: 청산 가격
        gross_pnl_pct: 비용 전 수익률
        fee_paid: 실제 수수료 (KRW)
        slippage_pct: 실제 슬리피지 (비율)
        net_pnl_pct: 비용 후 순수익률
        net_pnl_amount: 순수익금 (KRW)
        holding_hours: 보유 시간
        exit_reason: 청산 사유 (stop_loss, take_profit, signal_sell)
        daily_volume: 체결 당시 일일 거래대금
        label: ML 라벨 ("profit", "loss", "break_even")
        label_score: 수익률 기반 연속 점수
        cost_policy_version: 적용된 CostPolicy 버전
        reproducibility: 재현성 메타데이터
    """

    outcome_id: str
    entry_snapshot_id: str
    entry_price: Decimal
    exit_price: Decimal
    gross_pnl_pct: float
    fee_paid: Decimal
    slippage_pct: float
    net_pnl_pct: float
    net_pnl_amount: Decimal
    holding_hours: float
    exit_reason: str
    daily_volume: Decimal
    label: str
    label_score: float
    cost_policy_version: str
    reproducibility: ReproducibilityMetadata

    def to_dict(self) -> dict:
        """딕셔너리로 변환 (Parquet 저장용)"""
        return {
            "outcome_id": self.outcome_id,
            "entry_snapshot_id": self.entry_snapshot_id,
            "entry_price": str(self.entry_price),
            "exit_price": str(self.exit_price),
            "gross_pnl_pct": self.gross_pnl_pct,
            "fee_paid": str(self.fee_paid),
            "slippage_pct": self.slippage_pct,
            "net_pnl_pct": self.net_pnl_pct,
            "net_pnl_amount": str(self.net_pnl_amount),
            "holding_hours": self.holding_hours,
            "exit_reason": self.exit_reason,
            "daily_volume": str(self.daily_volume),
            "label": self.label,
            "label_score": self.label_score,
            "cost_policy_version": self.cost_policy_version,
            "reproducibility": self.reproducibility.to_dict(),
        }

    @classmethod
    def create(
        cls,
        entry_snapshot_id: str,
        entry_price: Decimal,
        exit_price: Decimal,
        fee_paid: Decimal,
        slippage_pct: float,
        holding_hours: float,
        exit_reason: str,
        daily_volume: Decimal,
        cost_policy_version: str,
        reproducibility: ReproducibilityMetadata,
    ) -> "TradeOutcome":
        """
        거래 결과 생성 팩토리 메서드

        수익률과 라벨을 자동 계산한다.
        """
        # Gross PnL 계산
        if entry_price > 0:
            gross_pnl_pct = float((exit_price - entry_price) / entry_price)
        else:
            gross_pnl_pct = 0.0

        # Net PnL 계산 (수수료 + 슬리피지 차감)
        fee_pct = float(fee_paid / entry_price) if entry_price > 0 else 0.0
        net_pnl_pct = gross_pnl_pct - fee_pct - slippage_pct

        # Net PnL 금액
        net_pnl_amount = entry_price * Decimal(str(net_pnl_pct))

        # 라벨 계산
        if net_pnl_pct > 0.001:  # 0.1% 이상 이익
            label = "profit"
        elif net_pnl_pct < -0.001:  # 0.1% 이상 손실
            label = "loss"
        else:
            label = "break_even"

        return cls(
            outcome_id=str(uuid.uuid4()).replace("-", "").upper()[:26],
            entry_snapshot_id=entry_snapshot_id,
            entry_price=entry_price,
            exit_price=exit_price,
            gross_pnl_pct=gross_pnl_pct,
            fee_paid=fee_paid,
            slippage_pct=slippage_pct,
            net_pnl_pct=net_pnl_pct,
            net_pnl_amount=net_pnl_amount,
            holding_hours=holding_hours,
            exit_reason=exit_reason,
            daily_volume=daily_volume,
            label=label,
            label_score=net_pnl_pct,
            cost_policy_version=cost_policy_version,
            reproducibility=reproducibility,
        )
