"""
Container와 main.py 통합 테스트

TDD RED Phase: Container를 통한 main.py 초기화 흐름 테스트

테스트 시나리오:
1. Container.create_from_legacy() 통합 테스트
2. PipelineContext에 UseCase 주입 지원 확인
3. main.py 초기화 흐름 테스트
4. 레거시 서비스와의 호환성 확인
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, Any

from src.container import Container
from src.trading.pipeline.base_stage import PipelineContext


class TestContainerCreateFromLegacy:
    """Container.create_from_legacy() 테스트"""

    def test_create_from_legacy_with_all_services(self):
        """모든 레거시 서비스로 Container 생성"""
        # Given: 레거시 서비스들
        mock_upbit = MagicMock()
        mock_ai = MagicMock()
        mock_data_collector = MagicMock()

        # When: Container 생성
        container = Container.create_from_legacy(
            upbit_client=mock_upbit,
            ai_service=mock_ai,
            data_collector=mock_data_collector
        )

        # Then: Container가 생성되어야 함
        assert container is not None
        assert isinstance(container, Container)

    def test_create_from_legacy_with_partial_services(self):
        """일부 레거시 서비스만으로 Container 생성"""
        # Given: upbit_client만 제공
        mock_upbit = MagicMock()

        # When: Container 생성
        container = Container.create_from_legacy(upbit_client=mock_upbit)

        # Then: Container가 생성되어야 함
        assert container is not None
        assert container._exchange_port is not None

    def test_create_from_legacy_returns_usable_use_cases(self):
        """레거시 서비스로 생성한 Container가 UseCase 반환"""
        # Given: 레거시 서비스들
        mock_upbit = MagicMock()
        mock_ai = MagicMock()
        mock_data_collector = MagicMock()

        container = Container.create_from_legacy(
            upbit_client=mock_upbit,
            ai_service=mock_ai,
            data_collector=mock_data_collector
        )

        # When: UseCase 요청
        execute_trade = container.get_execute_trade_use_case()
        analyze_market = container.get_analyze_market_use_case()

        # Then: UseCase가 반환되어야 함
        assert execute_trade is not None
        assert analyze_market is not None


class TestPipelineContextWithUseCase:
    """PipelineContext에 UseCase 주입 테스트"""

    def test_context_supports_container_field(self):
        """PipelineContext에 container 필드 지원 확인"""
        # Given: Container
        container = Container.create_for_testing()

        # When: PipelineContext 생성 시 container 전달
        context = PipelineContext(
            ticker="KRW-BTC",
            trading_type="spot",
            container=container
        )

        # Then: container가 저장되어야 함
        assert context.container is container

    def test_context_provides_use_cases_via_container(self):
        """PipelineContext에서 Container를 통해 UseCase 접근"""
        # Given: Container가 포함된 PipelineContext
        container = Container.create_for_testing()
        context = PipelineContext(
            ticker="KRW-BTC",
            trading_type="spot",
            container=container
        )

        # When: UseCase 접근
        execute_trade = context.container.get_execute_trade_use_case()

        # Then: UseCase가 반환되어야 함
        assert execute_trade is not None

    def test_context_backward_compatible_without_container(self):
        """Container 없이도 PipelineContext 생성 가능 (호환성)"""
        # When: container 없이 PipelineContext 생성
        context = PipelineContext(
            ticker="KRW-BTC",
            trading_type="spot"
        )

        # Then: container가 None이어야 함
        assert context.container is None


class TestMainInitializationWithContainer:
    """main.py 초기화 흐름 테스트"""

    @pytest.mark.asyncio
    async def test_execute_trading_cycle_accepts_container(self):
        """execute_trading_cycle()이 container 인자를 받을 수 있어야 함"""
        # Given: Container와 레거시 서비스들
        from main import execute_trading_cycle
        from src.application.services.trading_orchestrator import TradingOrchestrator

        container = Container.create_for_testing()

        mock_upbit = MagicMock()
        mock_upbit.get_balance.return_value = 1000000
        mock_upbit.get_orderbook.return_value = {}
        mock_upbit.get_ohlcv.return_value = []
        mock_upbit.get_current_price.return_value = 50000000

        mock_data_collector = MagicMock()
        mock_data_collector.get_chart_data.return_value = MagicMock(to_dict=lambda: {})
        mock_data_collector.get_full_orderbook.return_value = {}
        mock_data_collector.get_orderbook_summary.return_value = {}

        mock_trading_service = MagicMock()
        mock_ai_service = MagicMock()

        # When: container 인자와 함께 호출
        # TradingOrchestrator.execute_trading_cycle을 패치
        with patch.object(TradingOrchestrator, 'execute_trading_cycle', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {
                'pipeline_status': 'completed',
                'status': 'success',
                'decision': 'hold'
            }

            result = await execute_trading_cycle(
                ticker="KRW-BTC",
                upbit_client=mock_upbit,
                data_collector=mock_data_collector,
                trading_service=mock_trading_service,
                ai_service=mock_ai_service,
                container=container  # 새로운 인자
            )

        # Then: 정상 실행되어야 함
        assert result is not None
        assert result.get('pipeline_status') == 'completed'

    @pytest.mark.asyncio
    async def test_pipeline_context_receives_container(self):
        """TradingOrchestrator가 container를 받아야 함"""
        from main import execute_trading_cycle
        from src.application.services.trading_orchestrator import TradingOrchestrator

        container = Container.create_for_testing()

        mock_upbit = MagicMock()
        mock_data_collector = MagicMock()
        mock_trading_service = MagicMock()
        mock_ai_service = MagicMock()

        # TradingOrchestrator.__init__을 패치하여 container 주입 확인
        with patch.object(TradingOrchestrator, '__init__', return_value=None) as mock_init, \
             patch.object(TradingOrchestrator, 'execute_trading_cycle', new_callable=AsyncMock) as mock_execute, \
             patch.object(TradingOrchestrator, 'set_on_backtest_complete'):

            mock_execute.return_value = {
                'pipeline_status': 'completed',
                'status': 'success'
            }

            await execute_trading_cycle(
                ticker="KRW-BTC",
                upbit_client=mock_upbit,
                data_collector=mock_data_collector,
                trading_service=mock_trading_service,
                ai_service=mock_ai_service,
                container=container
            )

            # Then: TradingOrchestrator.__init__이 container를 받아야 함
            mock_init.assert_called_once()
            call_kwargs = mock_init.call_args.kwargs
            assert 'container' in call_kwargs
            assert call_kwargs['container'] is container


class TestLegacyCompatibility:
    """레거시 서비스와의 호환성 테스트"""

    @pytest.mark.asyncio
    async def test_execute_trading_cycle_works_without_container(self):
        """container 없이도 execute_trading_cycle() 동작 (호환성)"""
        from main import execute_trading_cycle
        from src.application.services.trading_orchestrator import TradingOrchestrator

        mock_upbit = MagicMock()
        mock_data_collector = MagicMock()
        mock_trading_service = MagicMock()
        mock_ai_service = MagicMock()

        # TradingOrchestrator.execute_trading_cycle을 패치
        with patch.object(TradingOrchestrator, 'execute_trading_cycle', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {
                'pipeline_status': 'completed',
                'status': 'success',
                'decision': 'hold'
            }

            # When: container 없이 호출 (기존 방식)
            result = await execute_trading_cycle(
                ticker="KRW-BTC",
                upbit_client=mock_upbit,
                data_collector=mock_data_collector,
                trading_service=mock_trading_service,
                ai_service=mock_ai_service
                # container 인자 없음
            )

        # Then: 정상 실행되어야 함
        assert result is not None
        assert result.get('pipeline_status') == 'completed'

    def test_container_uses_legacy_adapters_correctly(self):
        """Container가 레거시 어댑터를 올바르게 사용하는지 확인"""
        # Given: 레거시 서비스들 with 특정 동작
        mock_upbit = MagicMock()
        mock_upbit.get_balance.return_value = 500000

        # When: Container 생성 후 exchange_port 사용
        container = Container.create_from_legacy(upbit_client=mock_upbit)
        exchange_port = container.get_exchange_port()

        # Then: exchange_port가 LegacyExchangeAdapter여야 함
        from src.infrastructure.adapters.legacy_bridge import LegacyExchangeAdapter
        assert isinstance(exchange_port, LegacyExchangeAdapter)


class TestContainerDependencyInjection:
    """Container 의존성 주입 테스트"""

    def test_container_caches_use_cases(self):
        """Container가 UseCase 인스턴스를 캐싱하는지 확인"""
        # Given: Container
        container = Container.create_for_testing()

        # When: 같은 UseCase를 두 번 요청
        use_case_1 = container.get_execute_trade_use_case()
        use_case_2 = container.get_execute_trade_use_case()

        # Then: 같은 인스턴스여야 함
        assert use_case_1 is use_case_2

    def test_container_injects_correct_ports_to_use_cases(self):
        """Container가 UseCase에 올바른 Port를 주입하는지 확인"""
        # Given: 커스텀 Port로 Container 생성
        mock_exchange = MagicMock()
        mock_persistence = MagicMock()

        container = Container(
            exchange_port=mock_exchange,
            persistence_port=mock_persistence
        )

        # When: UseCase 요청
        use_case = container.get_execute_trade_use_case()

        # Then: UseCase가 커스텀 Port를 사용해야 함
        assert use_case.exchange is mock_exchange
        assert use_case.persistence is mock_persistence
