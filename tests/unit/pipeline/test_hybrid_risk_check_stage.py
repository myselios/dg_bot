"""
HybridRiskCheckStage 단위 테스트

통합 하이브리드 파이프라인의 핵심 스테이지 테스트
- 포트폴리오 체크 및 모드 분기
- 동적 코인 스캔 통합
- 포지션 관리 우선 처리
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional

from src.trading.pipeline.base_stage import PipelineContext, StageResult
from src.position.portfolio_manager import TradingMode, PortfolioPosition


class TestHybridRiskCheckStageInitialization:
    """HybridRiskCheckStage 초기화 테스트"""

    def test_initialization_with_scanning_enabled(self):
        """스캐닝 활성화 초기화 테스트"""
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage

        stage = HybridRiskCheckStage(
            stop_loss_pct=-5.0,
            take_profit_pct=10.0,
            daily_loss_limit_pct=-10.0,
            min_trade_interval_hours=4,
            max_positions=3,
            enable_scanning=True,
            fallback_ticker="KRW-ETH"
        )

        assert stage.name == "HybridRiskCheck"
        assert stage.stop_loss_pct == -5.0
        assert stage.take_profit_pct == 10.0
        assert stage.max_positions == 3
        assert stage.enable_scanning is True
        assert stage.fallback_ticker == "KRW-ETH"

    def test_initialization_with_scanning_disabled(self):
        """스캐닝 비활성화 초기화 테스트"""
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage

        stage = HybridRiskCheckStage(
            enable_scanning=False,
            fallback_ticker="KRW-BTC"
        )

        assert stage.enable_scanning is False
        assert stage.fallback_ticker == "KRW-BTC"

    def test_initialization_default_values(self):
        """기본값 초기화 테스트"""
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage

        stage = HybridRiskCheckStage()

        assert stage.stop_loss_pct == -5.0
        assert stage.take_profit_pct == 10.0
        assert stage.daily_loss_limit_pct == -10.0
        assert stage.min_trade_interval_hours == 4
        assert stage.max_positions == 3
        assert stage.enable_scanning is True
        assert stage.fallback_ticker == "KRW-ETH"

    def test_initialization_with_scanner_config(self):
        """스캐너 설정 초기화 테스트"""
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage

        scanner_config = {
            'liquidity_top_n': 30,
            'min_volume_krw': 20_000_000_000,
            'backtest_top_n': 10,
            'final_select_n': 3
        }

        stage = HybridRiskCheckStage(
            enable_scanning=True,
            scanner_config=scanner_config
        )

        assert stage.scanner_config == scanner_config


class TestHybridRiskCheckStageBlockedMode:
    """BLOCKED 모드 테스트"""

    @pytest.fixture
    def mock_context(self):
        """Mock 컨텍스트"""
        context = MagicMock(spec=PipelineContext)
        context.upbit_client = MagicMock()
        context.data_collector = MagicMock()
        context.trading_service = MagicMock()
        context.ai_service = MagicMock()
        context.ticker = "KRW-ETH"
        return context

    @pytest.fixture
    def mock_portfolio_status_blocked(self):
        """차단 모드 포트폴리오 상태"""
        status = MagicMock()
        status.trading_mode = TradingMode.BLOCKED
        status.positions = []
        status.can_open_new_position = False
        status.available_capital = 0
        return status

    @pytest.mark.asyncio
    async def test_blocked_mode_returns_exit(self, mock_context, mock_portfolio_status_blocked):
        """서킷브레이커 발동 시 exit 반환"""
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage

        stage = HybridRiskCheckStage()

        with patch('src.trading.pipeline.hybrid_stage.PortfolioManager') as MockPM:
            mock_pm_instance = MagicMock()
            mock_pm_instance.get_portfolio_status.return_value = mock_portfolio_status_blocked
            mock_pm_instance.check_portfolio_risk.return_value = {'allowed': True}
            MockPM.return_value = mock_pm_instance

            result = await stage.execute(mock_context)

            assert result.success is True
            assert result.action == 'exit'
            assert result.data['status'] == 'blocked'
            assert result.data['decision'] == 'hold'

    @pytest.mark.asyncio
    async def test_portfolio_risk_exceeded_returns_exit(self, mock_context):
        """포트폴리오 리스크 초과 시 exit 반환"""
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage

        stage = HybridRiskCheckStage()

        status = MagicMock()
        status.trading_mode = TradingMode.ENTRY
        status.positions = []

        with patch('src.trading.pipeline.hybrid_stage.PortfolioManager') as MockPM:
            mock_pm_instance = MagicMock()
            mock_pm_instance.get_portfolio_status.return_value = status
            mock_pm_instance.check_portfolio_risk.return_value = {
                'allowed': False,
                'reason': '일일 손실 한도 초과'
            }
            MockPM.return_value = mock_pm_instance

            result = await stage.execute(mock_context)

            assert result.success is True
            assert result.action == 'exit'
            assert result.data['status'] == 'blocked'


class TestHybridRiskCheckStageManagementMode:
    """MANAGEMENT 모드 테스트"""

    @pytest.fixture
    def mock_context(self):
        """Mock 컨텍스트"""
        context = MagicMock(spec=PipelineContext)
        context.upbit_client = MagicMock()
        context.data_collector = MagicMock()
        context.trading_service = MagicMock()
        context.ai_service = MagicMock()
        context.ticker = "KRW-ETH"
        return context

    @pytest.fixture
    def mock_portfolio_status_management(self):
        """관리 모드 포트폴리오 상태 (최대 포지션)"""
        position = MagicMock(spec=PortfolioPosition)
        position.ticker = "KRW-BTC"
        position.symbol = "BTC"
        position.avg_buy_price = 50000000
        position.current_price = 51000000
        position.amount = 0.01
        position.profit_rate = 2.0
        position.profit_loss = 10000
        position.entry_time = datetime.now()

        status = MagicMock()
        status.trading_mode = TradingMode.MANAGEMENT
        status.positions = [position]
        status.can_open_new_position = False  # 최대 포지션 도달
        status.available_capital = 500000
        return status

    @pytest.fixture
    def mock_portfolio_status_management_with_slots(self):
        """관리 모드 포트폴리오 상태 (추가 슬롯 있음)"""
        position = MagicMock(spec=PortfolioPosition)
        position.ticker = "KRW-BTC"
        position.symbol = "BTC"
        position.avg_buy_price = 50000000
        position.current_price = 51000000
        position.amount = 0.01
        position.profit_rate = 2.0
        position.profit_loss = 10000
        position.entry_time = datetime.now()

        status = MagicMock()
        status.trading_mode = TradingMode.MANAGEMENT
        status.positions = [position]
        status.can_open_new_position = True  # 추가 진입 가능
        status.available_capital = 500000
        return status

    @pytest.mark.asyncio
    async def test_management_mode_handles_positions(self, mock_context, mock_portfolio_status_management):
        """포지션 관리 분기 테스트"""
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage
        from src.ai.position_analyzer import PositionAction, PositionActionType

        stage = HybridRiskCheckStage()

        with patch('src.trading.pipeline.hybrid_stage.PortfolioManager') as MockPM:
            with patch('src.trading.pipeline.hybrid_stage.PositionAnalyzer') as MockPA:
                mock_pm_instance = MagicMock()
                mock_pm_instance.get_portfolio_status.return_value = mock_portfolio_status_management
                mock_pm_instance.check_portfolio_risk.return_value = {'allowed': True}
                MockPM.return_value = mock_pm_instance

                mock_pa_instance = MagicMock()
                mock_pa_instance.analyze.return_value = PositionAction(
                    action=PositionActionType.HOLD,
                    reason="포지션 유지",
                    trigger="규칙 기반",
                    ai_used=False
                )
                MockPA.return_value = mock_pa_instance

                with patch.object(stage, '_collect_position_market_data', return_value={}):
                    result = await stage.execute(mock_context)

                    assert result.success is True
                    # 최대 포지션 도달 + HOLD → skip
                    assert result.action == 'skip'

    @pytest.mark.asyncio
    async def test_position_management_executes_before_scan(
        self, mock_context, mock_portfolio_status_management_with_slots
    ):
        """관리가 스캔보다 우선 실행되는지 테스트"""
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage
        from src.ai.position_analyzer import PositionAction, PositionActionType

        stage = HybridRiskCheckStage(enable_scanning=True)
        execution_order = []

        with patch('src.trading.pipeline.hybrid_stage.PortfolioManager') as MockPM:
            with patch('src.trading.pipeline.hybrid_stage.PositionAnalyzer') as MockPA:
                mock_pm_instance = MagicMock()
                mock_pm_instance.get_portfolio_status.return_value = mock_portfolio_status_management_with_slots
                mock_pm_instance.check_portfolio_risk.return_value = {'allowed': True}
                MockPM.return_value = mock_pm_instance

                def track_position_analysis(*args, **kwargs):
                    execution_order.append('position_management')
                    return PositionAction(
                        action=PositionActionType.HOLD,
                        reason="포지션 유지",
                        trigger="규칙 기반",
                        ai_used=False
                    )

                mock_pa_instance = MagicMock()
                mock_pa_instance.analyze.side_effect = track_position_analysis
                MockPA.return_value = mock_pa_instance

                with patch.object(stage, '_collect_position_market_data', return_value={}):
                    with patch.object(stage, '_execute_coin_scan') as mock_scan:
                        async def track_scan(*args, **kwargs):
                            execution_order.append('coin_scan')
                            return StageResult(
                                success=True,
                                action='continue',
                                message="스캔 완료"
                            )
                        mock_scan.side_effect = track_scan

                        result = await stage.execute(mock_context)

                        # 포지션 관리가 먼저 실행되어야 함
                        assert 'position_management' in execution_order
                        if 'coin_scan' in execution_order:
                            assert execution_order.index('position_management') < execution_order.index('coin_scan')


class TestHybridRiskCheckStageEntryMode:
    """ENTRY 모드 테스트"""

    @pytest.fixture
    def mock_context(self):
        """Mock 컨텍스트"""
        context = MagicMock(spec=PipelineContext)
        context.upbit_client = MagicMock()
        context.data_collector = MagicMock()
        context.trading_service = MagicMock()
        context.ai_service = MagicMock()
        context.ticker = "KRW-ETH"
        return context

    @pytest.fixture
    def mock_portfolio_status_entry(self):
        """진입 모드 포트폴리오 상태"""
        status = MagicMock()
        status.trading_mode = TradingMode.ENTRY
        status.positions = []
        status.can_open_new_position = True
        status.available_capital = 1000000
        return status

    @pytest.mark.asyncio
    async def test_entry_mode_triggers_scan_when_enabled(self, mock_context, mock_portfolio_status_entry):
        """ENTRY 모드에서 스캔 트리거 테스트 (스캔 활성화)"""
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage

        stage = HybridRiskCheckStage(enable_scanning=True)

        with patch('src.trading.pipeline.hybrid_stage.PortfolioManager') as MockPM:
            mock_pm_instance = MagicMock()
            mock_pm_instance.get_portfolio_status.return_value = mock_portfolio_status_entry
            mock_pm_instance.check_portfolio_risk.return_value = {'allowed': True}
            MockPM.return_value = mock_pm_instance

            # _execute_coin_scan은 동기 메서드이므로 MagicMock 사용
            with patch.object(stage, '_execute_coin_scan') as mock_scan:
                mock_scan.return_value = StageResult(
                    success=True,
                    action='continue',
                    message="스캔 완료",
                    data={'selected_coin': {'ticker': 'KRW-XRP', 'symbol': 'XRP'}}
                )

                result = await stage.execute(mock_context)

                # 스캔이 호출되어야 함
                mock_scan.assert_called_once()
                assert result.success is True

    @pytest.mark.asyncio
    async def test_entry_mode_uses_fixed_ticker_when_scan_disabled(
        self, mock_context, mock_portfolio_status_entry
    ):
        """스캔 비활성화 시 고정 티커 사용 테스트"""
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage

        stage = HybridRiskCheckStage(
            enable_scanning=False,
            fallback_ticker="KRW-BTC"
        )

        with patch('src.trading.pipeline.hybrid_stage.PortfolioManager') as MockPM:
            mock_pm_instance = MagicMock()
            mock_pm_instance.get_portfolio_status.return_value = mock_portfolio_status_entry
            mock_pm_instance.check_portfolio_risk.return_value = {'allowed': True}
            MockPM.return_value = mock_pm_instance

            result = await stage.execute(mock_context)

            assert result.success is True
            assert result.action == 'continue'
            # 고정 티커가 사용되어야 함
            assert mock_context.ticker == "KRW-BTC"
            assert mock_context.trading_mode == 'entry'

    @pytest.mark.asyncio
    async def test_dynamic_ticker_update_after_scan(self, mock_context, mock_portfolio_status_entry):
        """스캔 후 ticker 업데이트 검증"""
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage

        stage = HybridRiskCheckStage(enable_scanning=True)

        with patch('src.trading.pipeline.hybrid_stage.PortfolioManager') as MockPM:
            mock_pm_instance = MagicMock()
            mock_pm_instance.get_portfolio_status.return_value = mock_portfolio_status_entry
            mock_pm_instance.check_portfolio_risk.return_value = {'allowed': True}
            MockPM.return_value = mock_pm_instance

            # _execute_coin_scan은 동기 메서드이므로 동기 함수로 side_effect 설정
            with patch.object(stage, '_execute_coin_scan') as mock_scan:
                def update_ticker(context):
                    context.ticker = "KRW-XRP"  # 동적으로 변경
                    context.selected_coin = {'ticker': 'KRW-XRP', 'symbol': 'XRP'}
                    return StageResult(
                        success=True,
                        action='continue',
                        message="스캔 완료"
                    )
                mock_scan.side_effect = update_ticker

                result = await stage.execute(mock_context)

                assert mock_context.ticker == "KRW-XRP"
                assert result.success is True

    @pytest.mark.asyncio
    async def test_scan_no_result_uses_fallback(self, mock_context, mock_portfolio_status_entry):
        """스캔 결과 없을 때 fallback 티커 사용"""
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage

        stage = HybridRiskCheckStage(
            enable_scanning=True,
            fallback_ticker="KRW-ETH"
        )

        with patch('src.trading.pipeline.hybrid_stage.PortfolioManager') as MockPM:
            mock_pm_instance = MagicMock()
            mock_pm_instance.get_portfolio_status.return_value = mock_portfolio_status_entry
            mock_pm_instance.check_portfolio_risk.return_value = {'allowed': True}
            MockPM.return_value = mock_pm_instance

            # _execute_coin_scan은 동기 메서드이므로 MagicMock 사용
            with patch.object(stage, '_execute_coin_scan') as mock_scan:
                # 스캔 결과 없음
                mock_scan.return_value = StageResult(
                    success=True,
                    action='skip',
                    message="스캔 결과 없음",
                    data={'selected_coin': None}
                )

                result = await stage.execute(mock_context)

                # skip 반환되어야 함 (스캔 결과 없음)
                assert result.action == 'skip'


class TestHybridRiskCheckStageInsufficientCapital:
    """자본 부족 테스트"""

    @pytest.fixture
    def mock_context(self):
        """Mock 컨텍스트"""
        context = MagicMock(spec=PipelineContext)
        context.upbit_client = MagicMock()
        context.ticker = "KRW-ETH"
        return context

    @pytest.mark.asyncio
    async def test_insufficient_capital_returns_skip(self, mock_context):
        """자본 부족 시 skip 반환"""
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage

        stage = HybridRiskCheckStage()

        status = MagicMock()
        status.trading_mode = TradingMode.ENTRY
        status.positions = []
        status.can_open_new_position = True
        status.available_capital = 5000  # 1만원 미만

        with patch('src.trading.pipeline.hybrid_stage.PortfolioManager') as MockPM:
            mock_pm_instance = MagicMock()
            mock_pm_instance.get_portfolio_status.return_value = status
            mock_pm_instance.check_portfolio_risk.return_value = {'allowed': True}
            MockPM.return_value = mock_pm_instance

            result = await stage.execute(mock_context)

            assert result.success is True
            assert result.action == 'skip'
            assert '자본 부족' in result.data['reason']


class TestHybridRiskCheckStageErrorHandling:
    """에러 처리 테스트"""

    @pytest.fixture
    def mock_context(self):
        """Mock 컨텍스트"""
        context = MagicMock(spec=PipelineContext)
        context.upbit_client = MagicMock()
        context.ticker = "KRW-ETH"
        return context

    @pytest.mark.asyncio
    async def test_execute_error_handling(self, mock_context):
        """에러 처리 테스트"""
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage

        stage = HybridRiskCheckStage()

        with patch('src.trading.pipeline.hybrid_stage.PortfolioManager') as MockPM:
            MockPM.side_effect = Exception("테스트 오류")

            result = await stage.execute(mock_context)

            assert result.success is False
            assert 'error' in result.metadata

    @pytest.mark.asyncio
    async def test_scan_error_falls_back_gracefully(self, mock_context):
        """스캔 오류 시 graceful fallback"""
        from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage

        stage = HybridRiskCheckStage(
            enable_scanning=True,
            fallback_ticker="KRW-ETH"
        )

        status = MagicMock()
        status.trading_mode = TradingMode.ENTRY
        status.positions = []
        status.can_open_new_position = True
        status.available_capital = 1000000

        with patch('src.trading.pipeline.hybrid_stage.PortfolioManager') as MockPM:
            mock_pm_instance = MagicMock()
            mock_pm_instance.get_portfolio_status.return_value = status
            mock_pm_instance.check_portfolio_risk.return_value = {'allowed': True}
            MockPM.return_value = mock_pm_instance

            with patch.object(stage, '_execute_coin_scan') as mock_scan:
                mock_scan.side_effect = Exception("스캔 오류")

                # 스캔 오류 시에도 fallback으로 진행 가능해야 함
                result = await stage.execute(mock_context)

                # fallback 티커 사용
                assert mock_context.ticker == "KRW-ETH"
                assert result.success is True
                assert result.action == 'continue'
