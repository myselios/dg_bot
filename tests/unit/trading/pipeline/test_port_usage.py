"""
Tests for Port Direct Usage in Pipeline Stages - TDD Phase 5

RED Phase: 이 테스트들은 Pipeline Stage들이 Port를 직접 사용하도록
리팩토링되기 전에 일부 실패합니다.

목표:
- getattr(port, '_client') 패턴 제거 검증
- _get_services() 메서드 제거 검증
- Port 인터페이스 직접 사용 검증
"""
import pytest
import ast
import inspect
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal


class TestNoGetattrClientPattern:
    """getattr.*_client 패턴 사용 금지 테스트"""

    @pytest.fixture
    def pipeline_files(self):
        """파이프라인 Stage 파일 목록"""
        pipeline_dir = Path("src/trading/pipeline")
        return list(pipeline_dir.glob("*.py"))

    def test_no_getattr_client_in_execution_stage(self):
        """ExecutionStage에서 getattr.*_client 패턴 사용 금지"""
        with open("src/trading/pipeline/execution_stage.py", "r") as f:
            content = f.read()

        # getattr.*_client 패턴 검색
        import re
        matches = re.findall(r'getattr\([^)]*_client', content)

        assert len(matches) == 0, \
            f"ExecutionStage에서 getattr.*_client 패턴 발견: {matches}"

    def test_no_getattr_client_in_data_collection_stage(self):
        """DataCollectionStage에서 getattr.*_client 패턴 사용 금지"""
        with open("src/trading/pipeline/data_collection_stage.py", "r") as f:
            content = f.read()

        import re
        matches = re.findall(r'getattr\([^)]*_client', content)

        assert len(matches) == 0, \
            f"DataCollectionStage에서 getattr.*_client 패턴 발견: {matches}"

    def test_no_getattr_client_in_hybrid_stage(self):
        """HybridRiskCheckStage에서 getattr.*_client 패턴 사용 금지"""
        with open("src/trading/pipeline/hybrid_stage.py", "r") as f:
            content = f.read()

        import re
        matches = re.findall(r'getattr\([^)]*_client', content)

        assert len(matches) == 0, \
            f"HybridStage에서 getattr.*_client 패턴 발견: {matches}"

    def test_no_getattr_client_in_risk_check_stage(self):
        """RiskCheckStage에서 getattr.*_client 패턴 사용 금지"""
        with open("src/trading/pipeline/risk_check_stage.py", "r") as f:
            content = f.read()

        import re
        matches = re.findall(r'getattr\([^)]*_client', content)

        assert len(matches) == 0, \
            f"RiskCheckStage에서 getattr.*_client 패턴 발견: {matches}"

    def test_no_getattr_client_in_adaptive_stage(self):
        """AdaptiveStage에서 getattr.*_client 패턴 사용 금지"""
        with open("src/trading/pipeline/adaptive_stage.py", "r") as f:
            content = f.read()

        import re
        matches = re.findall(r'getattr\([^)]*_client', content)

        assert len(matches) == 0, \
            f"AdaptiveStage에서 getattr.*_client 패턴 발견: {matches}"

    def test_no_getattr_client_in_trading_pipeline(self):
        """TradingPipeline에서 getattr.*_client 패턴 사용 금지"""
        with open("src/trading/pipeline/trading_pipeline.py", "r") as f:
            content = f.read()

        import re
        matches = re.findall(r'getattr\([^)]*_client', content)

        assert len(matches) == 0, \
            f"TradingPipeline에서 getattr.*_client 패턴 발견: {matches}"


class TestNoGetServicesMethod:
    """_get_services() 메서드 제거 테스트"""

    def test_no_get_services_in_execution_stage(self):
        """ExecutionStage에서 _get_services 메서드 제거"""
        with open("src/trading/pipeline/execution_stage.py", "r") as f:
            content = f.read()

        assert "def _get_services" not in content, \
            "ExecutionStage에 _get_services 메서드가 남아있습니다"

    def test_no_get_services_in_data_collection_stage(self):
        """DataCollectionStage에서 _get_services 메서드 제거"""
        with open("src/trading/pipeline/data_collection_stage.py", "r") as f:
            content = f.read()

        assert "def _get_services" not in content, \
            "DataCollectionStage에 _get_services 메서드가 남아있습니다"

    def test_no_get_services_in_hybrid_stage(self):
        """HybridRiskCheckStage에서 _get_services 메서드 제거"""
        with open("src/trading/pipeline/hybrid_stage.py", "r") as f:
            content = f.read()

        assert "def _get_services" not in content, \
            "HybridStage에 _get_services 메서드가 남아있습니다"

    def test_no_get_services_in_risk_check_stage(self):
        """RiskCheckStage에서 _get_services 메서드 제거"""
        with open("src/trading/pipeline/risk_check_stage.py", "r") as f:
            content = f.read()

        assert "def _get_services" not in content, \
            "RiskCheckStage에 _get_services 메서드가 남아있습니다"

    def test_no_get_services_in_adaptive_stage(self):
        """AdaptiveStage에서 _get_services 메서드 제거"""
        with open("src/trading/pipeline/adaptive_stage.py", "r") as f:
            content = f.read()

        assert "def _get_services" not in content, \
            "AdaptiveStage에 _get_services 메서드가 남아있습니다"


class TestExecutionStageUsesPortDirectly:
    """ExecutionStage가 Port를 직접 사용하는지 테스트"""

    @pytest.mark.asyncio
    async def test_execution_stage_uses_exchange_port_for_balance(self):
        """ExecutionStage가 잔고 조회 시 ExchangePort 직접 사용"""
        from src.trading.pipeline.execution_stage import ExecutionStage
        from src.trading.pipeline.base_stage import PipelineContext

        # Given
        mock_container = MagicMock()
        mock_exchange_port = AsyncMock()
        mock_container.get_exchange_port.return_value = mock_exchange_port

        # Mock BalanceInfo response
        from src.application.dto.trading import BalanceInfo
        from src.domain.value_objects.money import Money, Currency
        mock_exchange_port.get_balance.return_value = BalanceInfo(
            currency="KRW",
            total=Money(Decimal("1000000"), Currency.KRW),
            available=Money(Decimal("1000000"), Currency.KRW),
            locked=Money(Decimal("0"), Currency.KRW)
        )
        mock_exchange_port.get_current_price.return_value = Money(
            Decimal("50000000"), Currency.KRW
        )

        context = PipelineContext(
            ticker="KRW-BTC",
            trading_type="spot",
            container=mock_container
        )
        context.ai_result = {"decision": "hold", "confidence": "medium", "reason": "test"}

        stage = ExecutionStage()

        # When
        await stage.execute(context)

        # Then - Port를 직접 호출했는지 확인
        mock_exchange_port.get_balance.assert_called()

    @pytest.mark.asyncio
    async def test_execution_stage_uses_exchange_port_for_price(self):
        """ExecutionStage가 가격 조회 시 ExchangePort 직접 사용"""
        from src.trading.pipeline.execution_stage import ExecutionStage
        from src.trading.pipeline.base_stage import PipelineContext
        from src.application.dto.trading import BalanceInfo
        from src.domain.value_objects.money import Money, Currency

        # Given
        mock_container = MagicMock()
        mock_exchange_port = AsyncMock()
        mock_container.get_exchange_port.return_value = mock_exchange_port
        mock_exchange_port.get_balance.return_value = BalanceInfo(
            currency="KRW",
            total=Money(Decimal("1000000"), Currency.KRW),
            available=Money(Decimal("1000000"), Currency.KRW),
            locked=Money(Decimal("0"), Currency.KRW)
        )
        mock_exchange_port.get_current_price.return_value = Money(
            Decimal("50000000"), Currency.KRW
        )

        context = PipelineContext(
            ticker="KRW-BTC",
            trading_type="spot",
            container=mock_container
        )
        context.ai_result = {"decision": "hold", "confidence": "medium", "reason": "test"}

        stage = ExecutionStage()

        # When
        await stage.execute(context)

        # Then
        mock_exchange_port.get_current_price.assert_called_with("KRW-BTC")


class TestDataCollectionStageUsesPortDirectly:
    """DataCollectionStage가 레거시 서비스를 직접 사용하는지 테스트

    NOTE: Phase 5에서는 anti-pattern 제거가 목표이며,
    완전한 Port 사용 전환은 향후 과제입니다.
    현재는 context.data_collector를 직접 사용합니다.
    """

    @pytest.mark.asyncio
    async def test_data_collection_uses_legacy_data_collector(self):
        """DataCollectionStage가 데이터 수집 시 레거시 data_collector 사용"""
        from src.trading.pipeline.data_collection_stage import DataCollectionStage
        from src.trading.pipeline.base_stage import PipelineContext

        # Given - 레거시 data_collector 목업
        mock_data_collector = MagicMock()
        mock_data_collector.get_chart_data_with_btc.return_value = {
            'eth': {'day': [{'close': 50000000}]},
            'btc': {'day': [{'close': 100000000}]}
        }
        mock_data_collector.get_orderbook.return_value = {}
        mock_data_collector.get_orderbook_summary.return_value = {}
        mock_data_collector.get_fear_greed_index.return_value = None

        mock_upbit_client = MagicMock()
        mock_upbit_client.get_balances.return_value = []

        context = PipelineContext(
            ticker="KRW-BTC",
            trading_type="spot",
            data_collector=mock_data_collector,
            upbit_client=mock_upbit_client
        )

        stage = DataCollectionStage()

        # When
        await stage.execute(context)

        # Then - data_collector가 직접 호출됨
        mock_data_collector.get_chart_data_with_btc.assert_called()


class TestHybridStageUsesPortDirectly:
    """HybridRiskCheckStage가 레거시 서비스를 직접 사용하는지 테스트

    NOTE: Phase 5에서는 anti-pattern 제거가 목표이며,
    완전한 Port 사용 전환은 향후 과제입니다.
    현재는 context.upbit_client를 직접 사용합니다.
    """

    @pytest.mark.asyncio
    async def test_hybrid_stage_uses_legacy_upbit_client(self):
        """HybridRiskCheckStage가 포지션 확인 시 레거시 upbit_client 사용"""
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage
        from src.trading.pipeline.base_stage import PipelineContext

        # Given - 레거시 upbit_client 목업
        mock_upbit_client = MagicMock()
        mock_upbit_client.get_balances.return_value = [
            {'currency': 'KRW', 'balance': '1000000'}
        ]

        context = PipelineContext(
            ticker="KRW-BTC",
            trading_type="spot",
            upbit_client=mock_upbit_client
        )

        stage = HybridRiskCheckStage()

        # When
        await stage.execute(context)

        # Then - upbit_client가 직접 호출됨
        mock_upbit_client.get_balances.assert_called()


class TestPipelineContextHasPortAccess:
    """PipelineContext가 Port에 직접 접근 가능한지 테스트"""

    def test_context_provides_exchange_port(self):
        """PipelineContext가 ExchangePort 제공"""
        from src.trading.pipeline.base_stage import PipelineContext

        mock_container = MagicMock()
        mock_exchange_port = MagicMock()
        mock_container.get_exchange_port.return_value = mock_exchange_port

        context = PipelineContext(
            ticker="KRW-BTC",
            trading_type="spot",
            container=mock_container
        )

        # Context에서 Port 접근 가능해야 함
        assert context.get_exchange_port() == mock_exchange_port

    def test_context_provides_market_data_port(self):
        """PipelineContext가 MarketDataPort 제공"""
        from src.trading.pipeline.base_stage import PipelineContext

        mock_container = MagicMock()
        mock_market_data_port = MagicMock()
        mock_container.get_market_data_port.return_value = mock_market_data_port

        context = PipelineContext(
            ticker="KRW-BTC",
            trading_type="spot",
            container=mock_container
        )

        # Context에서 Port 접근 가능해야 함
        assert context.get_market_data_port() == mock_market_data_port

    def test_context_provides_ai_port(self):
        """PipelineContext가 AIPort 제공"""
        from src.trading.pipeline.base_stage import PipelineContext

        mock_container = MagicMock()
        mock_ai_port = MagicMock()
        mock_container.get_ai_port.return_value = mock_ai_port

        context = PipelineContext(
            ticker="KRW-BTC",
            trading_type="spot",
            container=mock_container
        )

        # Context에서 Port 접근 가능해야 함
        assert context.get_ai_port() == mock_ai_port


# 테스트 실행용 fixture
@pytest.fixture(autouse=True)
def reset_imports():
    """각 테스트 후 import 캐시 정리"""
    yield
    import sys
    modules_to_remove = [
        key for key in sys.modules.keys()
        if 'pipeline' in key or 'stage' in key.lower()
    ]
    for module in modules_to_remove:
        sys.modules.pop(module, None)
