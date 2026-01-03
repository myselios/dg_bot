"""
DecisionRecordPort Interface Tests

TDD - 판단 기록 Port 인터페이스 정의
"""
import pytest
from abc import ABC
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import uuid4

from src.application.ports.outbound.decision_record_port import (
    DecisionRecordPort,
    DecisionRecord,
    PnLLabel,
)
from src.domain.value_objects.ai_decision_result import AIDecisionResult, DecisionType
from src.domain.value_objects.prompt_version import PromptVersion, PromptType


class MockDecisionRecordAdapter(DecisionRecordPort):
    """테스트용 Mock 어댑터"""

    def __init__(self):
        self.records: dict = {}

    async def record(
        self,
        decision: AIDecisionResult,
        prompt_version: PromptVersion,
        params: dict,
    ) -> str:
        record_id = str(uuid4())
        self.records[record_id] = {
            "decision": decision,
            "prompt_version": prompt_version,
            "params": params,
            "pnl_label": None,
        }
        return record_id

    async def link_pnl(
        self,
        record_id: str,
        pnl_label: PnLLabel,
    ) -> bool:
        if record_id in self.records:
            self.records[record_id]["pnl_label"] = pnl_label
            return True
        return False

    async def get_record(self, record_id: str) -> Optional[DecisionRecord]:
        if record_id not in self.records:
            return None
        r = self.records[record_id]
        return DecisionRecord(
            id=record_id,
            decision=r["decision"],
            prompt_version=r["prompt_version"],
            params=r["params"],
            pnl_label=r["pnl_label"],
        )

    async def find_by_ticker(
        self,
        ticker: str,
        limit: int = 10,
    ) -> List[DecisionRecord]:
        return [
            DecisionRecord(
                id=rid,
                decision=r["decision"],
                prompt_version=r["prompt_version"],
                params=r["params"],
                pnl_label=r["pnl_label"],
            )
            for rid, r in self.records.items()
            if r["decision"].ticker == ticker
        ][:limit]

    async def get_accuracy_stats(
        self,
        prompt_version: Optional[str] = None,
        start_date: Optional[datetime] = None,
    ) -> dict:
        return {"accuracy": 0.65, "total": 100, "correct": 65}


class TestDecisionRecordPortInterface:
    """DecisionRecordPort 인터페이스 테스트"""

    def test_is_abstract(self):
        """Given: DecisionRecordPort When: 인스턴스화 시도 Then: TypeError"""
        with pytest.raises(TypeError):
            DecisionRecordPort()

    def test_inherits_abc(self):
        """Given: DecisionRecordPort When: 부모 클래스 확인 Then: ABC"""
        assert issubclass(DecisionRecordPort, ABC)


class TestPnLLabel:
    """PnL 라벨 테스트"""

    def test_create_profit(self):
        """Given: 수익 라벨 When: 생성 Then: 올바른 값"""
        label = PnLLabel(
            pnl_percent=Decimal("5.5"),
            is_profitable=True,
            exit_reason="take_profit",
        )

        assert label.pnl_percent == Decimal("5.5")
        assert label.is_profitable is True

    def test_create_loss(self):
        """Given: 손실 라벨 When: 생성 Then: 올바른 값"""
        label = PnLLabel(
            pnl_percent=Decimal("-3.2"),
            is_profitable=False,
            exit_reason="stop_loss",
        )

        assert label.pnl_percent == Decimal("-3.2")
        assert label.is_profitable is False


class TestDecisionRecord:
    """DecisionRecord 테스트"""

    def test_create_record(self):
        """Given: 기록 데이터 When: 생성 Then: 올바른 값"""
        decision = AIDecisionResult.allow("KRW-BTC", 85, "Strong")
        prompt_version = PromptVersion.current(PromptType.ENTRY)

        record = DecisionRecord(
            id="test-123",
            decision=decision,
            prompt_version=prompt_version,
            params={"temperature": 0.2},
        )

        assert record.id == "test-123"
        assert record.decision.ticker == "KRW-BTC"


class TestDecisionRecordPortMethods:
    """DecisionRecordPort 메서드 테스트 (Mock 사용)"""

    @pytest.fixture
    def adapter(self):
        return MockDecisionRecordAdapter()

    @pytest.mark.asyncio
    async def test_record(self, adapter):
        """Given: 판단 결과 When: record Then: 기록 ID 반환"""
        decision = AIDecisionResult.allow("KRW-BTC", 85, "Strong")
        prompt_version = PromptVersion.current(PromptType.ENTRY)

        record_id = await adapter.record(
            decision=decision,
            prompt_version=prompt_version,
            params={"temperature": 0.2},
        )

        assert isinstance(record_id, str)
        assert len(record_id) > 0

    @pytest.mark.asyncio
    async def test_link_pnl(self, adapter):
        """Given: 기록 ID When: link_pnl Then: PnL 연결"""
        # 먼저 기록 생성
        decision = AIDecisionResult.allow("KRW-BTC", 85, "Strong")
        prompt_version = PromptVersion.current(PromptType.ENTRY)
        record_id = await adapter.record(decision, prompt_version, {})

        # PnL 연결
        pnl = PnLLabel(
            pnl_percent=Decimal("5.5"),
            is_profitable=True,
            exit_reason="take_profit",
        )
        success = await adapter.link_pnl(record_id, pnl)

        assert success is True

        # 확인
        record = await adapter.get_record(record_id)
        assert record.pnl_label is not None
        assert record.pnl_label.pnl_percent == Decimal("5.5")

    @pytest.mark.asyncio
    async def test_get_record(self, adapter):
        """Given: 기록 ID When: get_record Then: 기록 반환"""
        decision = AIDecisionResult.allow("KRW-BTC", 85, "Strong")
        prompt_version = PromptVersion.current(PromptType.ENTRY)
        record_id = await adapter.record(decision, prompt_version, {})

        record = await adapter.get_record(record_id)

        assert record is not None
        assert record.id == record_id

    @pytest.mark.asyncio
    async def test_get_record_not_found(self, adapter):
        """Given: 없는 ID When: get_record Then: None"""
        record = await adapter.get_record("nonexistent-id")
        assert record is None

    @pytest.mark.asyncio
    async def test_find_by_ticker(self, adapter):
        """Given: 티커 When: find_by_ticker Then: 해당 기록들"""
        # 여러 기록 생성
        d1 = AIDecisionResult.allow("KRW-BTC", 85, "Strong")
        d2 = AIDecisionResult.allow("KRW-ETH", 80, "Good")
        pv = PromptVersion.current(PromptType.ENTRY)

        await adapter.record(d1, pv, {})
        await adapter.record(d2, pv, {})

        # BTC만 조회
        records = await adapter.find_by_ticker("KRW-BTC")

        assert len(records) == 1
        assert records[0].decision.ticker == "KRW-BTC"

    @pytest.mark.asyncio
    async def test_get_accuracy_stats(self, adapter):
        """Given: 통계 요청 When: get_accuracy_stats Then: 통계 반환"""
        stats = await adapter.get_accuracy_stats()

        assert "accuracy" in stats
        assert "total" in stats
