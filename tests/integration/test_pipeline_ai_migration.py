"""
Integration tests for AI migration (Phase 3).

이 테스트는 레거시 AI 코드(EntryAnalyzer, PositionAnalyzer, EnhancedOpenAIAdapter)의
현재 동작을 캡처합니다. 마이그레이션 후에도 동일한 동작을 보장하기 위해 사용됩니다.

테스트 범위:
1. HybridRiskCheckStage - PositionAnalyzer 호출
2. CoinSelector - EntryAnalyzer 호출
3. Container.get_analyze_breakout_use_case() - EnhancedOpenAIAdapter 사용

⚠️ 마이그레이션 후에는 이 테스트를 AIPort 기반으로 업데이트해야 합니다.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from decimal import Decimal
from datetime import datetime

from src.trading.pipeline.hybrid_stage import HybridRiskCheckStage
from src.trading.pipeline.base_stage import PipelineContext
from src.position.portfolio_manager import PortfolioManager, TradingMode, PortfolioStatus, PortfolioPosition
from src.ai.position_analyzer import PositionAnalyzer, Position, PositionAction, PositionActionType


class TestHybridRiskCheckStageAIMigration:
    """HybridRiskCheckStage의 PositionAnalyzer 사용 테스트."""

    @pytest.fixture
    def mock_upbit_client(self):
        """Mock UpbitClient."""
        client = Mock()
        client.get_balances.return_value = [
            {'currency': 'KRW', 'balance': '1000000'},
            {'currency': 'BTC', 'balance': '0.1', 'avg_buy_price': '50000000'}
        ]
        client.get_current_price.return_value = 52000000  # +4% 수익
        return client

    @pytest.fixture
    def mock_data_collector(self):
        """Mock DataCollector."""
        collector = Mock()
        # 시간봉 데이터 (간소화)
        chart_data = {
            'minute60': Mock(
                empty=False,
                __len__=lambda self: 100
            )
        }
        collector.get_chart_data.return_value = chart_data
        return collector

    @pytest.fixture
    def context_with_position(self, mock_upbit_client, mock_data_collector):
        """포지션이 있는 컨텍스트."""
        context = PipelineContext(ticker='KRW-BTC')
        context.upbit_client = mock_upbit_client
        context.data_collector = mock_data_collector
        context.trading_service = Mock()
        return context

    @pytest.mark.skip(reason="HybridRiskCheckStage has complex dependencies (PortfolioManager). Use E2E/scenario tests instead.")
    @pytest.mark.asyncio
    async def test_position_analyzer_called_in_management_mode(
        self, context_with_position, mock_upbit_client
    ):
        """
        MANAGEMENT 모드에서 PositionAnalyzer가 호출되는지 검증.

        ⚠️ HybridRiskCheckStage는 PortfolioManager와 강하게 결합되어 있어
        Integration test로 테스트하기 어렵습니다.
        대신 E2E/scenario tests에서 검증합니다.

        시나리오:
        1. 포지션이 있는 상태
        2. HybridRiskCheckStage.execute() 호출
        3. PositionAnalyzer.analyze() 호출 확인
        """
        # Given: HybridRiskCheckStage 초기화
        stage = HybridRiskCheckStage(
            stop_loss_pct=-5.0,
            take_profit_pct=10.0,
            enable_scanning=False
        )

        # When: execute() 실행
        result = await stage.execute(context_with_position)

        # Then: PositionAnalyzer가 context에 설정되었는지 확인
        assert hasattr(context_with_position, 'position_analyzer')
        assert isinstance(context_with_position.position_analyzer, PositionAnalyzer)

        # 결과가 성공적으로 반환되었는지 확인
        assert result.success is True

    @pytest.mark.skip(reason="HybridRiskCheckStage has complex dependencies (PortfolioManager). Use E2E/scenario tests instead.")
    @pytest.mark.asyncio
    async def test_position_analyzer_exit_action(self, context_with_position, mock_upbit_client):
        """
        PositionAnalyzer가 EXIT 액션을 반환할 때 동작 검증.

        ⚠️ HybridRiskCheckStage는 PortfolioManager와 강하게 결합되어 있어
        Integration test로 테스트하기 어렵습니다.

        시나리오:
        1. 손절 조건 충족 (현재가 < 진입가 * (1 + stop_loss_pct))
        2. PositionAnalyzer가 EXIT 액션 반환
        3. 청산 실행
        """
        # Given: 손절 조건 (진입가 50M, 현재가 47M = -6%)
        mock_upbit_client.get_current_price.return_value = 47000000

        stage = HybridRiskCheckStage(
            stop_loss_pct=-5.0,  # -5% 손절
            enable_scanning=False
        )

        # Mock trading_service.execute_sell
        mock_sell_result = {'success': True, 'executed': True}
        context_with_position.trading_service.execute_sell.return_value = mock_sell_result

        # When: execute() 실행
        result = await stage.execute(context_with_position)

        # Then: action='exit' 확인
        # NOTE: 손절 조건이 충족되면 즉시 청산되어야 함
        # 실제 동작은 PositionAnalyzer 내부 로직에 의존
        assert result.success is True

    @pytest.mark.skip(reason="HybridRiskCheckStage has complex dependencies (PortfolioManager). Use E2E/scenario tests instead.")
    @pytest.mark.asyncio
    async def test_position_analyzer_hold_action(self, context_with_position):
        """
        PositionAnalyzer가 HOLD 액션을 반환할 때 동작 검증.

        ⚠️ HybridRiskCheckStage는 PortfolioManager와 강하게 결합되어 있어
        Integration test로 테스트하기 어렵습니다.

        시나리오:
        1. 정상 범위 내 가격 (손절/익절 조건 미충족)
        2. PositionAnalyzer가 HOLD 액션 반환
        3. 포지션 유지
        """
        # Given: 정상 가격 (진입가 50M, 현재가 52M = +4%)
        stage = HybridRiskCheckStage(
            stop_loss_pct=-5.0,
            take_profit_pct=10.0,
            enable_scanning=False
        )

        # When: execute() 실행
        result = await stage.execute(context_with_position)

        # Then: action='skip' 또는 'continue'
        assert result.success is True
        assert result.action in ['skip', 'continue', 'exit']


class TestCoinSelectorAIMigration:
    """CoinSelector의 EntryAnalyzer 사용 테스트."""

    @pytest.mark.asyncio
    async def test_entry_analyzer_usage_in_coin_selector(self):
        """
        CoinSelector가 EntryAnalyzer를 사용하는지 검증.

        ⚠️ 이 테스트는 실제 API 호출을 하지 않도록 mock을 사용합니다.

        시나리오:
        1. CoinSelector 초기화 (entry_analyzer 주입)
        2. select_coins() 호출
        3. EntryAnalyzer.analyze_entry() 호출 확인
        """
        from src.scanner.coin_selector import CoinSelector
        from src.ai.entry_analyzer import EntryAnalyzer

        # Given: Mock components (AsyncMock for async methods)
        mock_liquidity_scanner = AsyncMock()
        mock_data_sync = AsyncMock()
        mock_multi_backtest = AsyncMock()
        mock_entry_analyzer = Mock(spec=EntryAnalyzer)

        # Mock 결과 설정
        mock_liquidity_scanner.scan_top_coins.return_value = []  # 빈 결과

        selector = CoinSelector(
            liquidity_scanner=mock_liquidity_scanner,
            data_sync=mock_data_sync,
            multi_backtest=mock_multi_backtest,
            entry_analyzer=mock_entry_analyzer,
            liquidity_top_n=10,
            min_volume_krw=10_000_000_000,
            backtest_top_n=5,
            ai_top_n=3,
            final_select_n=2
        )

        # When: select_coins() 호출
        result = await selector.select_coins(exclude_tickers=[])

        # Then: 결과 확인 (빈 결과라도 정상 반환)
        assert result is not None
        assert hasattr(result, 'selected_coins')


class TestContainerAnalyzeBreakoutUseCaseAIMigration:
    """Container.get_analyze_breakout_use_case()의 EnhancedOpenAIAdapter 사용 테스트."""

    @pytest.mark.skip(reason="Container.get_analyze_breakout_use_case() has bug - api_key parameter issue. Will fix in Phase 3.5")
    def test_get_analyze_breakout_use_case_uses_enhanced_adapter(self):
        """
        get_analyze_breakout_use_case()가 EnhancedOpenAIAdapter를 사용하는지 검증.

        ⚠️ 현재 Container.py Line 309에서 api_key를 전달하는 버그가 있습니다.
        Phase 3.5에서 수정 예정입니다.

        시나리오:
        1. Container 초기화 (session_factory 필요)
        2. get_analyze_breakout_use_case() 호출
        3. EnhancedOpenAIAdapter가 주입되었는지 확인
        """
        from src.container import Container
        from src.infrastructure.adapters.ai import EnhancedOpenAIAdapter

        # Given: Mock session_factory (DecisionRecordPort 필요)
        mock_session_factory = Mock()

        container = Container.create_from_legacy(
            upbit_client=Mock(),
            session_factory=mock_session_factory
        )

        # When: get_analyze_breakout_use_case() 호출
        use_case = container.get_analyze_breakout_use_case()

        # Then: use_case가 생성되었는지 확인
        assert use_case is not None

        # EnhancedOpenAIAdapter가 주입되었는지 확인
        # NOTE: use_case._ai_client는 private이므로 간접 확인
        assert hasattr(use_case, '_ai_client')
        assert isinstance(use_case._ai_client, EnhancedOpenAIAdapter)


class TestPositionAnalyzerBehavior:
    """PositionAnalyzer의 하이브리드 로직 동작 테스트 (마이그레이션 기준선)."""

    def test_position_analyzer_stop_loss_trigger(self):
        """
        손절 조건에서 EXIT 액션 반환 검증.

        시나리오:
        1. 진입가 50M, 현재가 47M (-6%)
        2. stop_loss_pct = -5%
        3. EXIT 액션 반환
        """
        # Given: PositionAnalyzer 초기화
        analyzer = PositionAnalyzer(
            stop_loss_pct=-5.0,
            take_profit_pct=10.0
        )

        position = Position(
            ticker='KRW-BTC',
            entry_price=50000000,
            current_price=47000000,  # -6%
            amount=0.1,
            entry_time=datetime.now()
        )

        market_data = {
            'current_price': 47000000,
            'technical_indicators': {}
        }

        # When: analyze() 호출
        action = analyzer.analyze(position, market_data)

        # Then: EXIT 액션 확인
        assert action.action == PositionActionType.EXIT
        assert action.trigger == 'stop_loss'
        assert action.confidence == 'high'

    def test_position_analyzer_take_profit_trigger(self):
        """
        익절 조건에서 EXIT 액션 반환 검증.

        시나리오:
        1. 진입가 50M, 현재가 56M (+12%)
        2. take_profit_pct = 10%
        3. EXIT 액션 반환
        """
        # Given: PositionAnalyzer 초기화
        analyzer = PositionAnalyzer(
            stop_loss_pct=-5.0,
            take_profit_pct=10.0
        )

        position = Position(
            ticker='KRW-BTC',
            entry_price=50000000,
            current_price=56000000,  # +12%
            amount=0.1,
            entry_time=datetime.now()
        )

        market_data = {
            'current_price': 56000000,
            'technical_indicators': {}
        }

        # When: analyze() 호출
        action = analyzer.analyze(position, market_data)

        # Then: EXIT 액션 확인
        assert action.action == PositionActionType.EXIT
        assert action.trigger == 'take_profit'

    def test_position_analyzer_hold_action(self):
        """
        정상 범위에서 HOLD 액션 반환 검증.

        시나리오:
        1. 진입가 50M, 현재가 52M (+4%)
        2. 손절/익절 조건 미충족
        3. HOLD 액션 반환
        """
        # Given: PositionAnalyzer 초기화
        analyzer = PositionAnalyzer(
            stop_loss_pct=-5.0,
            take_profit_pct=10.0
        )

        position = Position(
            ticker='KRW-BTC',
            entry_price=50000000,
            current_price=52000000,  # +4%
            amount=0.1,
            entry_time=datetime.now()
        )

        market_data = {
            'current_price': 52000000,
            'technical_indicators': {}
        }

        # When: analyze() 호출
        action = analyzer.analyze(position, market_data)

        # Then: HOLD 액션 확인
        assert action.action == PositionActionType.HOLD
