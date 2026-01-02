"""
AdaptiveRiskCheckStage 단위 테스트
"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime

from src.trading.pipeline.adaptive_stage import AdaptiveRiskCheckStage
from src.trading.pipeline.base_stage import PipelineContext, StageResult
from src.position.portfolio_manager import TradingMode, PortfolioPosition


class TestAdaptiveRiskCheckStage:
    """AdaptiveRiskCheckStage 클래스 테스트"""

    def test_initialization(self):
        """초기화 테스트"""
        stage = AdaptiveRiskCheckStage(
            stop_loss_pct=-5.0,
            take_profit_pct=10.0,
            daily_loss_limit_pct=-10.0,
            min_trade_interval_hours=4,
            max_positions=3
        )

        assert stage.name == "AdaptiveRiskCheck"
        assert stage.stop_loss_pct == -5.0
        assert stage.take_profit_pct == 10.0
        assert stage.daily_loss_limit_pct == -10.0
        assert stage.min_trade_interval_hours == 4
        assert stage.max_positions == 3

    def test_initialization_default(self):
        """기본값 초기화 테스트"""
        stage = AdaptiveRiskCheckStage()

        assert stage.stop_loss_pct == -5.0
        assert stage.take_profit_pct == 10.0
        assert stage.max_positions == 3

    @pytest.fixture
    def mock_context(self):
        """Mock 컨텍스트"""
        context = MagicMock(spec=PipelineContext)
        context.upbit_client = MagicMock()
        context.data_collector = MagicMock()
        context.trading_service = MagicMock()
        context.ai_service = MagicMock()
        context.ticker = "KRW-BTC"
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

    @pytest.fixture
    def mock_portfolio_status_management(self):
        """관리 모드 포트폴리오 상태"""
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
        status.can_open_new_position = False
        status.available_capital = 500000
        return status

    @pytest.fixture
    def mock_portfolio_status_blocked(self):
        """차단 모드 포트폴리오 상태"""
        status = MagicMock()
        status.trading_mode = TradingMode.BLOCKED
        status.positions = []
        status.can_open_new_position = False
        status.available_capital = 0
        return status

    def test_execute_entry_mode(self, mock_context, mock_portfolio_status_entry):
        """ENTRY 모드 실행 테스트"""
        stage = AdaptiveRiskCheckStage()

        with patch('src.trading.pipeline.adaptive_stage.PortfolioManager') as MockPM:
            mock_pm_instance = MagicMock()
            mock_pm_instance.get_portfolio_status.return_value = mock_portfolio_status_entry
            mock_pm_instance.check_portfolio_risk.return_value = {'allowed': True}
            MockPM.return_value = mock_pm_instance

            result = stage.execute(mock_context)

            assert result.success is True
            assert result.action == 'continue'
            assert mock_context.trading_mode == 'entry'

    def test_execute_blocked_mode(self, mock_context, mock_portfolio_status_blocked):
        """BLOCKED 모드 실행 테스트"""
        stage = AdaptiveRiskCheckStage()

        with patch('src.trading.pipeline.adaptive_stage.PortfolioManager') as MockPM:
            mock_pm_instance = MagicMock()
            mock_pm_instance.get_portfolio_status.return_value = mock_portfolio_status_blocked
            mock_pm_instance.check_portfolio_risk.return_value = {'allowed': True}
            MockPM.return_value = mock_pm_instance

            result = stage.execute(mock_context)

            assert result.success is True
            assert result.action == 'exit'
            assert result.data['status'] == 'blocked'

    def test_execute_portfolio_risk_blocked(self, mock_context, mock_portfolio_status_entry):
        """포트폴리오 리스크 초과 테스트"""
        stage = AdaptiveRiskCheckStage()

        with patch('src.trading.pipeline.adaptive_stage.PortfolioManager') as MockPM:
            mock_pm_instance = MagicMock()
            mock_pm_instance.get_portfolio_status.return_value = mock_portfolio_status_entry
            mock_pm_instance.check_portfolio_risk.return_value = {
                'allowed': False,
                'reason': '일일 손실 한도 초과'
            }
            MockPM.return_value = mock_pm_instance

            result = stage.execute(mock_context)

            assert result.success is True
            assert result.action == 'exit'
            assert result.data['status'] == 'blocked'
            assert '손실 한도' in result.data['reason']

    def test_execute_management_mode_hold(self, mock_context, mock_portfolio_status_management):
        """MANAGEMENT 모드 - HOLD 테스트"""
        stage = AdaptiveRiskCheckStage()

        from src.ai.position_analyzer import PositionAction, PositionActionType

        with patch('src.trading.pipeline.adaptive_stage.PortfolioManager') as MockPM:
            with patch('src.trading.pipeline.adaptive_stage.PositionAnalyzer') as MockPA:
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

                # 시장 데이터 수집 모킹
                with patch.object(stage, '_collect_position_market_data', return_value={}):
                    result = stage.execute(mock_context)

                    assert result.success is True
                    # 최대 포지션 도달이면 skip
                    assert result.action in ['skip', 'continue']

    def test_execute_management_mode_exit(self, mock_context, mock_portfolio_status_management):
        """MANAGEMENT 모드 - 청산 테스트"""
        stage = AdaptiveRiskCheckStage()

        from src.ai.position_analyzer import PositionAction, PositionActionType

        with patch('src.trading.pipeline.adaptive_stage.PortfolioManager') as MockPM:
            with patch('src.trading.pipeline.adaptive_stage.PositionAnalyzer') as MockPA:
                mock_pm_instance = MagicMock()
                mock_pm_instance.get_portfolio_status.return_value = mock_portfolio_status_management
                mock_pm_instance.check_portfolio_risk.return_value = {'allowed': True}
                MockPM.return_value = mock_pm_instance

                mock_pa_instance = MagicMock()
                mock_pa_instance.analyze.return_value = PositionAction(
                    action=PositionActionType.EXIT,
                    reason="손절 도달",
                    trigger="stop_loss",
                    ai_used=False
                )
                MockPA.return_value = mock_pa_instance

                # 시장 데이터 수집 모킹
                with patch.object(stage, '_collect_position_market_data', return_value={}):
                    with patch.object(stage, '_execute_exit', return_value={'success': True}):
                        result = stage.execute(mock_context)

                        assert result.success is True
                        assert result.action == 'exit'
                        assert result.data['decision'] == 'sell'

    def test_execute_insufficient_capital(self, mock_context):
        """자본 부족 테스트"""
        stage = AdaptiveRiskCheckStage()

        status = MagicMock()
        status.trading_mode = TradingMode.ENTRY
        status.positions = []
        status.can_open_new_position = True
        status.available_capital = 5000  # 1만원 미만

        with patch('src.trading.pipeline.adaptive_stage.PortfolioManager') as MockPM:
            mock_pm_instance = MagicMock()
            mock_pm_instance.get_portfolio_status.return_value = status
            mock_pm_instance.check_portfolio_risk.return_value = {'allowed': True}
            MockPM.return_value = mock_pm_instance

            result = stage.execute(mock_context)

            assert result.success is True
            assert result.action == 'skip'
            assert '자본 부족' in result.data['reason']

    def test_handle_blocked_mode(self, mock_context, mock_portfolio_status_blocked):
        """_handle_blocked_mode 테스트"""
        stage = AdaptiveRiskCheckStage()

        result = stage._handle_blocked_mode(mock_context, mock_portfolio_status_blocked)

        assert result.success is True
        assert result.action == 'exit'
        assert result.data['status'] == 'blocked'
        assert result.data['decision'] == 'hold'

    def test_handle_entry_mode_success(self, mock_context, mock_portfolio_status_entry):
        """_handle_entry_mode 성공 테스트"""
        stage = AdaptiveRiskCheckStage()

        result = stage._handle_entry_mode(mock_context, mock_portfolio_status_entry)

        assert result.success is True
        assert result.action == 'continue'
        assert mock_context.entry_capital == 1000000
        assert mock_context.trading_mode == 'entry'

    def test_handle_entry_mode_insufficient_capital(self, mock_context):
        """_handle_entry_mode 자본 부족 테스트"""
        stage = AdaptiveRiskCheckStage()

        status = MagicMock()
        status.available_capital = 100  # 1만원 미만

        result = stage._handle_entry_mode(mock_context, status)

        assert result.success is True
        assert result.action == 'skip'

    def test_execute_error_handling(self, mock_context):
        """에러 처리 테스트"""
        stage = AdaptiveRiskCheckStage()

        with patch('src.trading.pipeline.adaptive_stage.PortfolioManager') as MockPM:
            MockPM.side_effect = Exception("테스트 오류")

            result = stage.execute(mock_context)

            assert result.success is False
            # 에러 정보는 metadata에 저장
            assert 'error' in result.metadata

    def test_collect_position_market_data(self, mock_context):
        """시장 데이터 수집 테스트"""
        stage = AdaptiveRiskCheckStage()

        mock_context.upbit_client.get_current_price.return_value = 50000000
        mock_context.data_collector.get_chart_data.return_value = None

        market_data = stage._collect_position_market_data(mock_context, "KRW-BTC")

        assert 'current_price' in market_data
        assert market_data['current_price'] == 50000000

    def test_execute_exit(self, mock_context):
        """청산 실행 테스트"""
        stage = AdaptiveRiskCheckStage()

        position = MagicMock()
        position.ticker = "KRW-BTC"
        position.amount = 0.01
        position.current_price = 50000000
        position.profit_loss = 10000
        position.profit_rate = 2.0

        from src.ai.position_analyzer import PositionAction, PositionActionType
        action = PositionAction(
            action=PositionActionType.EXIT,
            reason="손절",
            trigger="stop_loss",
            ai_used=False
        )

        mock_context.trading_service.execute_sell.return_value = {'success': True}
        mock_context.portfolio_manager = MagicMock()

        result = stage._execute_exit(mock_context, position, action)

        assert result['success'] is True
        assert result['ticker'] == "KRW-BTC"

    def test_execute_partial_exit(self, mock_context):
        """부분 청산 실행 테스트"""
        stage = AdaptiveRiskCheckStage()

        position = MagicMock()
        position.ticker = "KRW-BTC"
        position.amount = 0.1

        from src.ai.position_analyzer import PositionAction, PositionActionType
        action = PositionAction(
            action=PositionActionType.PARTIAL_EXIT,
            reason="부분 익절",
            trigger="trailing_stop",
            ai_used=False,
            exit_ratio=0.5
        )

        mock_context.trading_service.execute_sell.return_value = {'success': True}

        result = stage._execute_partial_exit(mock_context, position, action)

        assert result['success'] is True
        assert result['sold_amount'] == 0.05  # 0.1 * 0.5
        assert result['exit_ratio'] == 0.5
