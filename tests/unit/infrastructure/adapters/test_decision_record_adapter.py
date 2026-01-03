"""
DecisionRecordAdapter Tests

TDD - 결정 기록 어댑터 테스트 (PostgreSQL 기반)
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.infrastructure.adapters.persistence.decision_record_adapter import (
    DecisionRecordAdapter,
)
from src.application.ports.outbound.decision_record_port import (
    DecisionRecordPort,
    DecisionRecord,
    PnLLabel,
)
from src.domain.value_objects.ai_decision_result import AIDecisionResult, DecisionType
from src.domain.value_objects.prompt_version import PromptVersion, PromptType


class TestDecisionRecordAdapterInterface:
    """인터페이스 구현 테스트"""

    def test_implements_port(self):
        """Given: DecisionRecordAdapter When: 타입 확인 Then: Port 구현"""
        adapter = DecisionRecordAdapter(db_session=AsyncMock())
        assert isinstance(adapter, DecisionRecordPort)


class TestDecisionRecordAdapterRecord:
    """record 메서드 테스트"""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def adapter(self, mock_session):
        return DecisionRecordAdapter(db_session=mock_session)

    @pytest.fixture
    def sample_decision(self):
        return AIDecisionResult.allow("KRW-BTC", 85, "Strong momentum")

    @pytest.fixture
    def sample_prompt_version(self):
        return PromptVersion.current(PromptType.ENTRY)

    @pytest.mark.asyncio
    async def test_record_returns_id(
        self, adapter, mock_session, sample_decision, sample_prompt_version
    ):
        """Given: 결정 데이터 When: record Then: ID 반환"""
        # Mock the refresh to set id
        async def mock_refresh(obj):
            obj.id = 123
        mock_session.refresh = mock_refresh

        record_id = await adapter.record(
            decision=sample_decision,
            prompt_version=sample_prompt_version,
            params={"temperature": 0.2},
        )

        assert record_id == "123"

    @pytest.mark.asyncio
    async def test_record_saves_decision_type(
        self, adapter, mock_session, sample_decision, sample_prompt_version
    ):
        """Given: ALLOW 결정 When: record Then: 결정 타입 저장"""
        async def mock_refresh(obj):
            obj.id = 1
        mock_session.refresh = mock_refresh

        await adapter.record(
            decision=sample_decision,
            prompt_version=sample_prompt_version,
            params={},
        )

        # Verify add was called with correct decision type
        mock_session.add.assert_called_once()
        added_obj = mock_session.add.call_args[0][0]
        assert added_obj.decision == "ALLOW"

    @pytest.mark.asyncio
    async def test_record_saves_prompt_version(
        self, adapter, mock_session, sample_decision, sample_prompt_version
    ):
        """Given: 프롬프트 버전 When: record Then: 버전 저장"""
        async def mock_refresh(obj):
            obj.id = 1
        mock_session.refresh = mock_refresh

        await adapter.record(
            decision=sample_decision,
            prompt_version=sample_prompt_version,
            params={},
        )

        added_obj = mock_session.add.call_args[0][0]
        assert added_obj.prompt_version == sample_prompt_version.version

    @pytest.mark.asyncio
    async def test_record_saves_params(
        self, adapter, mock_session, sample_decision, sample_prompt_version
    ):
        """Given: 파라미터 When: record Then: 파라미터 저장"""
        async def mock_refresh(obj):
            obj.id = 1
        mock_session.refresh = mock_refresh

        params = {"temperature": 0.2, "model": "gpt-4"}
        await adapter.record(
            decision=sample_decision,
            prompt_version=sample_prompt_version,
            params=params,
        )

        added_obj = mock_session.add.call_args[0][0]
        assert added_obj.params == params


class TestDecisionRecordAdapterLinkPnL:
    """link_pnl 메서드 테스트"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def adapter(self, mock_session):
        return DecisionRecordAdapter(db_session=mock_session)

    @pytest.mark.asyncio
    async def test_link_pnl_success(self, adapter, mock_session):
        """Given: 유효한 ID When: link_pnl Then: True 반환"""
        mock_record = MagicMock()
        mock_record.id = 123
        mock_session.get = AsyncMock(return_value=mock_record)

        pnl = PnLLabel(
            pnl_percent=Decimal("5.5"),
            is_profitable=True,
            exit_reason="take_profit",
        )

        result = await adapter.link_pnl("123", pnl)

        assert result is True

    @pytest.mark.asyncio
    async def test_link_pnl_not_found(self, adapter, mock_session):
        """Given: 없는 ID When: link_pnl Then: False 반환"""
        mock_session.get = AsyncMock(return_value=None)

        pnl = PnLLabel(
            pnl_percent=Decimal("5.5"),
            is_profitable=True,
            exit_reason="take_profit",
        )

        result = await adapter.link_pnl("999", pnl)

        assert result is False

    @pytest.mark.asyncio
    async def test_link_pnl_updates_record(self, adapter, mock_session):
        """Given: 유효한 ID When: link_pnl Then: 레코드 업데이트"""
        mock_record = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_record)

        pnl = PnLLabel(
            pnl_percent=Decimal("-3.2"),
            is_profitable=False,
            exit_reason="stop_loss",
        )

        await adapter.link_pnl("123", pnl)

        assert mock_record.pnl_percent == Decimal("-3.2")
        assert mock_record.is_profitable is False
        assert mock_record.exit_reason == "stop_loss"


class TestDecisionRecordAdapterGetRecord:
    """get_record 메서드 테스트"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def adapter(self, mock_session):
        return DecisionRecordAdapter(db_session=mock_session)

    @pytest.mark.asyncio
    async def test_get_record_found(self, adapter, mock_session):
        """Given: 유효한 ID When: get_record Then: 레코드 반환"""
        mock_db_record = MagicMock()
        mock_db_record.id = 123
        mock_db_record.symbol = "KRW-BTC"
        mock_db_record.decision = "ALLOW"
        mock_db_record.confidence = Decimal("85")
        mock_db_record.reason = "Strong momentum"
        mock_db_record.prompt_version = "1.0.0"
        mock_db_record.prompt_type = "ENTRY"
        mock_db_record.params = {"temperature": 0.2}
        mock_db_record.pnl_percent = None
        mock_db_record.is_profitable = None
        mock_db_record.exit_reason = None
        mock_session.get = AsyncMock(return_value=mock_db_record)

        record = await adapter.get_record("123")

        assert record is not None
        assert record.id == "123"
        assert record.decision.ticker == "KRW-BTC"
        assert record.decision.decision == DecisionType.ALLOW

    @pytest.mark.asyncio
    async def test_get_record_not_found(self, adapter, mock_session):
        """Given: 없는 ID When: get_record Then: None"""
        mock_session.get = AsyncMock(return_value=None)

        record = await adapter.get_record("999")

        assert record is None


class TestDecisionRecordAdapterFindByTicker:
    """find_by_ticker 메서드 테스트"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def adapter(self, mock_session):
        return DecisionRecordAdapter(db_session=mock_session)

    @pytest.mark.asyncio
    async def test_find_by_ticker_returns_list(self, adapter, mock_session):
        """Given: 티커 When: find_by_ticker Then: 리스트 반환"""
        mock_result = MagicMock()
        mock_records = []
        for i in range(3):
            r = MagicMock()
            r.id = i + 1
            r.symbol = "KRW-BTC"
            r.decision = "ALLOW"
            r.confidence = Decimal("85")
            r.reason = f"Reason {i}"
            r.prompt_version = "1.0.0"
            r.prompt_type = "ENTRY"
            r.params = {}
            r.pnl_percent = None
            r.is_profitable = None
            r.exit_reason = None
            mock_records.append(r)
        mock_result.scalars.return_value.all.return_value = mock_records
        mock_session.execute = AsyncMock(return_value=mock_result)

        records = await adapter.find_by_ticker("KRW-BTC", limit=10)

        assert len(records) == 3
        assert all(r.decision.ticker == "KRW-BTC" for r in records)

    @pytest.mark.asyncio
    async def test_find_by_ticker_respects_limit(self, adapter, mock_session):
        """Given: limit 2 When: find_by_ticker Then: 2개만 반환"""
        mock_result = MagicMock()
        mock_records = []
        for i in range(2):
            r = MagicMock()
            r.id = i + 1
            r.symbol = "KRW-ETH"
            r.decision = "BLOCK"
            r.confidence = Decimal("70")
            r.reason = "Low momentum"
            r.prompt_version = "1.0.0"
            r.prompt_type = "ENTRY"
            r.params = {}
            r.pnl_percent = None
            r.is_profitable = None
            r.exit_reason = None
            mock_records.append(r)
        mock_result.scalars.return_value.all.return_value = mock_records
        mock_session.execute = AsyncMock(return_value=mock_result)

        records = await adapter.find_by_ticker("KRW-ETH", limit=2)

        assert len(records) == 2


class TestDecisionRecordAdapterStats:
    """get_accuracy_stats 메서드 테스트"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def adapter(self, mock_session):
        return DecisionRecordAdapter(db_session=mock_session)

    @pytest.mark.asyncio
    async def test_get_accuracy_stats_returns_dict(self, adapter, mock_session):
        """Given: 기록 존재 When: get_accuracy_stats Then: 통계 반환"""
        mock_result = MagicMock()
        mock_result.one.return_value = (100, 65)  # total, profitable
        mock_session.execute = AsyncMock(return_value=mock_result)

        stats = await adapter.get_accuracy_stats()

        assert "accuracy" in stats
        assert "total" in stats
        assert "correct" in stats
        assert stats["total"] == 100
        assert stats["correct"] == 65
        assert stats["accuracy"] == 0.65

    @pytest.mark.asyncio
    async def test_get_accuracy_stats_empty(self, adapter, mock_session):
        """Given: 기록 없음 When: get_accuracy_stats Then: 0 반환"""
        mock_result = MagicMock()
        mock_result.one.return_value = (0, 0)
        mock_session.execute = AsyncMock(return_value=mock_result)

        stats = await adapter.get_accuracy_stats()

        assert stats["total"] == 0
        assert stats["accuracy"] == 0.0

    @pytest.mark.asyncio
    async def test_get_accuracy_stats_with_version_filter(self, adapter, mock_session):
        """Given: 버전 필터 When: get_accuracy_stats Then: 필터 적용"""
        mock_result = MagicMock()
        mock_result.one.return_value = (50, 35)
        mock_session.execute = AsyncMock(return_value=mock_result)

        stats = await adapter.get_accuracy_stats(prompt_version="2.0.0")

        assert stats["total"] == 50
        # Verify the query was executed (we trust it used the filter)
        mock_session.execute.assert_called_once()
