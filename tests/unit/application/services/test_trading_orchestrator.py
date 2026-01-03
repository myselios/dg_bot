"""
Tests for TradingOrchestrator - TDD Phase 3

RED Phase: 이 테스트들은 TradingOrchestrator 구현 전에 모두 실패해야 합니다.
"""
import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from typing import Dict, Any


def create_mock_container():
    """Create a mock container with properly mocked idempotency port."""
    mock_container = MagicMock()

    # Mock IdempotencyPort - must be properly async
    mock_idempotency_port = MagicMock()
    mock_idempotency_port.check_key = AsyncMock(return_value=False)  # Not a duplicate
    mock_idempotency_port.mark_key = AsyncMock(return_value=None)

    # Use spec to ensure consistent behavior
    mock_container.get_idempotency_port.return_value = mock_idempotency_port

    return mock_container


class TestTradingOrchestratorExists:
    """TradingOrchestrator 클래스 존재 테스트"""

    def test_trading_orchestrator_class_exists(self):
        """TradingOrchestrator 클래스가 존재해야 함"""
        from src.application.services.trading_orchestrator import TradingOrchestrator
        assert TradingOrchestrator is not None

    def test_trading_orchestrator_in_services_init(self):
        """TradingOrchestrator가 services/__init__.py에 등록되어 있어야 함"""
        from src.application.services import TradingOrchestrator
        assert TradingOrchestrator is not None


class TestTradingOrchestratorInit:
    """TradingOrchestrator 초기화 테스트"""

    def test_init_with_container(self):
        """Container를 인자로 받아 초기화해야 함"""
        from src.application.services.trading_orchestrator import TradingOrchestrator

        # Given
        mock_container = MagicMock()

        # When
        orchestrator = TradingOrchestrator(container=mock_container)

        # Then
        assert orchestrator._container is mock_container

    def test_init_without_container_raises_error(self):
        """Container 없이 초기화 시 에러 발생"""
        from src.application.services.trading_orchestrator import TradingOrchestrator

        # When & Then
        with pytest.raises(ValueError, match="Container is required"):
            TradingOrchestrator(container=None)

    def test_has_required_methods(self):
        """필수 메서드가 존재해야 함"""
        from src.application.services.trading_orchestrator import TradingOrchestrator

        assert hasattr(TradingOrchestrator, 'execute_trading_cycle')
        assert hasattr(TradingOrchestrator, 'execute_position_management')

    def test_has_optional_callbacks(self):
        """선택적 콜백 설정 메서드가 있어야 함"""
        from src.application.services.trading_orchestrator import TradingOrchestrator

        assert hasattr(TradingOrchestrator, 'set_on_backtest_complete')


class TestTradingOrchestratorExecuteTradingCycle:
    """TradingOrchestrator.execute_trading_cycle() 테스트"""

    @pytest.mark.asyncio
    async def test_execute_trading_cycle_returns_dict(self):
        """거래 사이클 실행 결과는 Dict를 반환해야 함"""
        from src.application.services.trading_orchestrator import TradingOrchestrator

        # Given
        mock_container = create_mock_container()

        # Mock Pipeline execute result
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value={
            'status': 'success',
            'decision': 'hold',
            'pipeline_status': 'completed'
        })

        with patch('src.application.services.trading_orchestrator.create_hybrid_trading_pipeline',
                   return_value=mock_pipeline):
            orchestrator = TradingOrchestrator(container=mock_container)

            # When
            result = await orchestrator.execute_trading_cycle(
                ticker="KRW-BTC",
                enable_scanning=True
            )

            # Then
            assert isinstance(result, dict)
            assert 'status' in result

    @pytest.mark.asyncio
    async def test_execute_trading_cycle_creates_pipeline(self):
        """거래 사이클 실행 시 파이프라인을 생성해야 함"""
        from src.application.services.trading_orchestrator import TradingOrchestrator

        # Given
        mock_container = create_mock_container()
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value={'status': 'success'})

        with patch('src.application.services.trading_orchestrator.create_hybrid_trading_pipeline',
                   return_value=mock_pipeline) as mock_create:
            orchestrator = TradingOrchestrator(container=mock_container)

            # When
            await orchestrator.execute_trading_cycle(
                ticker="KRW-BTC",
                enable_scanning=True
            )

            # Then
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_trading_cycle_passes_container_to_context(self):
        """거래 사이클 실행 시 Container를 Context에 전달해야 함"""
        from src.application.services.trading_orchestrator import TradingOrchestrator

        # Given
        mock_container = create_mock_container()
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value={'status': 'success'})

        captured_context = None

        async def capture_context(context):
            nonlocal captured_context
            captured_context = context
            return {'status': 'success'}

        mock_pipeline.execute = capture_context

        with patch('src.application.services.trading_orchestrator.create_hybrid_trading_pipeline',
                   return_value=mock_pipeline):
            with patch('src.application.services.trading_orchestrator.PipelineContext') as mock_ctx_class:
                mock_context = MagicMock()
                mock_ctx_class.return_value = mock_context

                orchestrator = TradingOrchestrator(container=mock_container)

                # When
                await orchestrator.execute_trading_cycle(
                    ticker="KRW-BTC",
                    enable_scanning=True
                )

                # Then
                mock_ctx_class.assert_called_once()
                call_kwargs = mock_ctx_class.call_args[1]
                assert call_kwargs.get('container') is mock_container

    @pytest.mark.asyncio
    async def test_execute_trading_cycle_with_scanning_params(self):
        """스캐닝 파라미터를 전달할 수 있어야 함"""
        from src.application.services.trading_orchestrator import TradingOrchestrator

        # Given
        mock_container = create_mock_container()
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value={'status': 'success'})

        with patch('src.application.services.trading_orchestrator.create_hybrid_trading_pipeline',
                   return_value=mock_pipeline) as mock_create:
            orchestrator = TradingOrchestrator(container=mock_container)

            # When
            await orchestrator.execute_trading_cycle(
                ticker="KRW-BTC",
                enable_scanning=True,
                liquidity_top_n=20,
                backtest_top_n=10,
                final_select_n=3
            )

            # Then
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs.get('enable_scanning') is True
            assert call_kwargs.get('liquidity_top_n') == 20
            assert call_kwargs.get('backtest_top_n') == 10
            assert call_kwargs.get('final_select_n') == 3

    @pytest.mark.asyncio
    async def test_execute_trading_cycle_with_risk_params(self):
        """리스크 파라미터를 전달할 수 있어야 함"""
        from src.application.services.trading_orchestrator import TradingOrchestrator

        # Given
        mock_container = create_mock_container()
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value={'status': 'success'})

        with patch('src.application.services.trading_orchestrator.create_hybrid_trading_pipeline',
                   return_value=mock_pipeline) as mock_create:
            orchestrator = TradingOrchestrator(container=mock_container)

            # When
            await orchestrator.execute_trading_cycle(
                ticker="KRW-BTC",
                stop_loss_pct=-3.0,
                take_profit_pct=8.0,
                daily_loss_limit_pct=-7.0
            )

            # Then
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs.get('stop_loss_pct') == -3.0
            assert call_kwargs.get('take_profit_pct') == 8.0
            assert call_kwargs.get('daily_loss_limit_pct') == -7.0


class TestTradingOrchestratorExecutePositionManagement:
    """TradingOrchestrator.execute_position_management() 테스트"""

    @pytest.mark.asyncio
    async def test_execute_position_management_returns_dict(self):
        """포지션 관리 실행 결과는 Dict를 반환해야 함"""
        from src.application.services.trading_orchestrator import TradingOrchestrator

        # Given
        mock_container = MagicMock()
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value={
            'status': 'success',
            'decision': 'hold',
            'positions_checked': 0
        })

        with patch('src.application.services.trading_orchestrator.create_position_management_pipeline',
                   return_value=mock_pipeline):
            orchestrator = TradingOrchestrator(container=mock_container)

            # When
            result = await orchestrator.execute_position_management()

            # Then
            assert isinstance(result, dict)
            assert 'status' in result

    @pytest.mark.asyncio
    async def test_execute_position_management_creates_pipeline(self):
        """포지션 관리 실행 시 포지션 관리 파이프라인을 생성해야 함"""
        from src.application.services.trading_orchestrator import TradingOrchestrator

        # Given
        mock_container = MagicMock()
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value={'status': 'success'})

        with patch('src.application.services.trading_orchestrator.create_position_management_pipeline',
                   return_value=mock_pipeline) as mock_create:
            orchestrator = TradingOrchestrator(container=mock_container)

            # When
            await orchestrator.execute_position_management()

            # Then
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_position_management_adds_cycle_type(self):
        """포지션 관리 결과에 cycle_type이 추가되어야 함"""
        from src.application.services.trading_orchestrator import TradingOrchestrator

        # Given
        mock_container = MagicMock()
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value={'status': 'success'})

        with patch('src.application.services.trading_orchestrator.create_position_management_pipeline',
                   return_value=mock_pipeline):
            orchestrator = TradingOrchestrator(container=mock_container)

            # When
            result = await orchestrator.execute_position_management()

            # Then
            assert result.get('cycle_type') == 'position_management'


class TestTradingOrchestratorErrorHandling:
    """TradingOrchestrator 에러 처리 테스트"""

    @pytest.mark.asyncio
    async def test_execute_trading_cycle_handles_exception(self):
        """거래 사이클에서 예외 발생 시 실패 결과 반환"""
        from src.application.services.trading_orchestrator import TradingOrchestrator

        # Given
        mock_container = create_mock_container()
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(side_effect=Exception("Test error"))

        with patch('src.application.services.trading_orchestrator.create_hybrid_trading_pipeline',
                   return_value=mock_pipeline):
            orchestrator = TradingOrchestrator(container=mock_container)

            # When
            result = await orchestrator.execute_trading_cycle(ticker="KRW-BTC")

            # Then
            assert result['status'] == 'failed'
            assert 'error' in result
            assert 'Test error' in result['error']

    @pytest.mark.asyncio
    async def test_execute_position_management_handles_exception(self):
        """포지션 관리에서 예외 발생 시 실패 결과 반환"""
        from src.application.services.trading_orchestrator import TradingOrchestrator

        # Given
        mock_container = MagicMock()
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(side_effect=Exception("Position error"))

        with patch('src.application.services.trading_orchestrator.create_position_management_pipeline',
                   return_value=mock_pipeline):
            orchestrator = TradingOrchestrator(container=mock_container)

            # When
            result = await orchestrator.execute_position_management()

            # Then
            assert result['status'] == 'failed'
            assert 'error' in result
            assert 'Position error' in result['error']

    @pytest.mark.asyncio
    async def test_trading_type_validation(self):
        """지원되지 않는 거래 타입에 대한 검증"""
        from src.application.services.trading_orchestrator import TradingOrchestrator

        # Given
        mock_container = create_mock_container()
        orchestrator = TradingOrchestrator(container=mock_container)

        # When
        result = await orchestrator.execute_trading_cycle(
            ticker="KRW-BTC",
            trading_type='futures'  # 지원되지 않는 타입
        )

        # Then
        assert result['status'] == 'failed'
        assert 'error' in result


class TestTradingOrchestratorCallbacks:
    """TradingOrchestrator 콜백 테스트"""

    def test_set_on_backtest_complete_callback(self):
        """백테스트 완료 콜백을 설정할 수 있어야 함"""
        from src.application.services.trading_orchestrator import TradingOrchestrator

        # Given
        mock_container = MagicMock()
        orchestrator = TradingOrchestrator(container=mock_container)

        callback = MagicMock()

        # When
        orchestrator.set_on_backtest_complete(callback)

        # Then
        assert orchestrator._on_backtest_complete is callback

    @pytest.mark.asyncio
    async def test_callback_passed_to_context(self):
        """콜백이 Context에 전달되어야 함"""
        from src.application.services.trading_orchestrator import TradingOrchestrator

        # Given
        mock_container = create_mock_container()
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value={'status': 'success'})
        callback = MagicMock()

        with patch('src.application.services.trading_orchestrator.create_hybrid_trading_pipeline',
                   return_value=mock_pipeline):
            with patch('src.application.services.trading_orchestrator.PipelineContext') as mock_ctx_class:
                mock_context = MagicMock()
                mock_ctx_class.return_value = mock_context

                orchestrator = TradingOrchestrator(container=mock_container)
                orchestrator.set_on_backtest_complete(callback)

                # When
                await orchestrator.execute_trading_cycle(ticker="KRW-BTC")

                # Then
                mock_ctx_class.assert_called()
                if mock_ctx_class.call_args:
                    call_kwargs = mock_ctx_class.call_args[1]
                    assert call_kwargs.get('on_backtest_complete') is callback


class TestContainerIntegration:
    """Container와의 통합 테스트"""

    def test_container_get_trading_orchestrator_method(self):
        """Container에 get_trading_orchestrator() 메서드가 있어야 함"""
        from src.container import Container

        assert hasattr(Container, 'get_trading_orchestrator')

    def test_container_returns_orchestrator_instance(self):
        """Container.get_trading_orchestrator()가 TradingOrchestrator 인스턴스를 반환해야 함"""
        from src.container import Container
        from src.application.services.trading_orchestrator import TradingOrchestrator

        # Given
        container = Container()

        # When
        orchestrator = container.get_trading_orchestrator()

        # Then
        assert isinstance(orchestrator, TradingOrchestrator)


# 테스트 실행용 fixture
@pytest.fixture(autouse=True)
def reset_imports():
    """각 테스트 후 import 캐시 정리"""
    yield
    import sys
    modules_to_remove = [
        key for key in sys.modules.keys()
        if 'trading_orchestrator' in key or 'services' in key.lower()
    ]
    for module in modules_to_remove:
        sys.modules.pop(module, None)
