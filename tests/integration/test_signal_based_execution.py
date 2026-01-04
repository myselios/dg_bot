"""
Phase 2: 신호 기반 실행 통합 테스트

SignalAnalyzer 기반 결정이 ExecutionStage까지 올바르게 전달되는지 검증합니다.

테스트 범위:
- AnalysisStage(entry_mode=True) → ExecutionStage 연동
- buy/sell/hold 결정에 따른 거래 실행 여부
- 실행 금액 계산 로직

TDD Phase: RED → GREEN → REFACTOR
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
import pandas as pd

from src.trading.pipeline.analysis_stage import AnalysisStage
from src.trading.pipeline.execution_stage import ExecutionStage
from src.trading.pipeline.base_stage import PipelineContext


class TestSignalBasedExecution:
    """신호 기반 결정이 ExecutionStage까지 전달되는지 검증"""

    @pytest.fixture
    def mock_context(self):
        """통합 테스트용 컨텍스트 생성"""
        context = MagicMock(spec=PipelineContext)
        context.ticker = "KRW-ETH"
        context.trading_type = "spot"
        context.container = MagicMock()

        # Exchange Port 모킹
        exchange_port = AsyncMock()
        exchange_port.get_current_price = AsyncMock(
            return_value=MagicMock(amount=Decimal("4500000"))
        )
        exchange_port.get_balance = AsyncMock(
            return_value=MagicMock(available=MagicMock(amount=Decimal("100000")))
        )
        context.get_exchange_port = MagicMock(return_value=exchange_port)

        # 기본 컨텍스트 속성
        context.ai_result = None
        context.trade_result = None
        context.validation_result = None
        context.position_check = True
        context.circuit_check = True
        context.frequency_check = True
        context.flash_crash = None
        context.rsi_divergence = None
        context.backtest_result = None
        context.signal_analysis = None
        context.position_info = None
        context.risk_manager = None
        context.trading_service = MagicMock()

        return context

    @pytest.fixture
    def buy_signal_context(self, mock_context):
        """매수 신호가 설정된 컨텍스트"""
        # SignalAnalyzer 결과 (buy 결정)
        mock_context.signal_analysis = {
            'decision': 'buy',
            'total_score': 3.5,
            'buy_score': 5.0,
            'sell_score': 1.5,
            'confidence': 'medium',
            'signals': ['MA5 > MA20', 'RSI=35.0 (약한 과매도)']
        }

        # AnalysisStage._handle_signal_based_entry()가 설정하는 ai_result
        mock_context.ai_result = {
            'decision': 'buy',
            'confidence': 'medium',
            'reason': 'Signal: buy (score: 3.5)'
        }

        return mock_context

    @pytest.fixture
    def hold_signal_context(self, mock_context):
        """홀드 신호가 설정된 컨텍스트"""
        mock_context.signal_analysis = {
            'decision': 'hold',
            'total_score': 0.5,
            'buy_score': 2.5,
            'sell_score': 2.0,
            'confidence': 'low',
            'signals': ['RSI=50.0 (중립)']
        }

        mock_context.ai_result = {
            'decision': 'hold',
            'confidence': 'low',
            'reason': 'Signal: hold (score: 0.5)'
        }

        return mock_context

    @pytest.fixture
    def sell_signal_context(self, mock_context):
        """매도 신호가 설정된 컨텍스트"""
        mock_context.signal_analysis = {
            'decision': 'sell',
            'total_score': -2.0,
            'buy_score': 2.0,
            'sell_score': 4.0,
            'confidence': 'low',
            'signals': ['RSI=75.0 (과매수)', 'Stochastic K=85, D=80 (과매수)']
        }

        mock_context.ai_result = {
            'decision': 'sell',
            'confidence': 'low',
            'reason': 'Signal: sell (score: -2.0)'
        }

        return mock_context


class TestBuySignalExecution(TestSignalBasedExecution):
    """매수 신호 실행 테스트"""

    @pytest.mark.asyncio
    async def test_strong_buy_signal_triggers_execution(self, buy_signal_context):
        """
        strong_buy 또는 buy 신호가 ExecutionStage에서 매수로 처리되는지 검증

        검증 항목:
        1. ai_result.decision = 'buy'일 때 _execute_buy() 호출됨
        2. 결과 status = 'success'
        3. 결과 decision = 'buy'
        """
        stage = ExecutionStage()

        with patch.object(stage, '_execute_buy', new_callable=AsyncMock) as mock_buy:
            result = await stage.execute(buy_signal_context)

        # 매수 실행 호출 확인
        mock_buy.assert_called_once_with(buy_signal_context)

        # 결과 검증
        assert result.success is True
        assert result.action == 'exit'
        assert result.data['status'] == 'success'
        assert result.data['decision'] == 'buy'
        assert result.data['reason'] == 'Signal: buy (score: 3.5)'

    @pytest.mark.asyncio
    async def test_buy_signal_with_signal_analysis_in_result(self, buy_signal_context):
        """
        ExecutionStage 결과에 signal_analysis가 포함되는지 검증

        Phase 1에서 추가된 signal_analysis 필드가 결과에 전달되어야 함
        """
        stage = ExecutionStage()

        with patch.object(stage, '_execute_buy', new_callable=AsyncMock):
            result = await stage.execute(buy_signal_context)

        # signal_analysis가 결과에 포함됨
        assert 'signal_analysis' in result.data
        assert result.data['signal_analysis'] is not None
        assert result.data['signal_analysis']['decision'] == 'buy'
        assert result.data['signal_analysis']['total_score'] == 3.5


class TestHoldSignalExecution(TestSignalBasedExecution):
    """홀드 신호 실행 테스트"""

    @pytest.mark.asyncio
    async def test_hold_signal_skips_execution(self, hold_signal_context):
        """
        hold 신호일 때 ExecutionStage가 거래를 스킵하는지 검증

        검증 항목:
        1. ai_result.decision = 'hold'일 때 _execute_hold() 호출됨
        2. _execute_buy()와 _execute_sell()은 호출되지 않음
        3. 결과 decision = 'hold'
        """
        stage = ExecutionStage()

        with patch.object(stage, '_execute_buy', new_callable=AsyncMock) as mock_buy, \
             patch.object(stage, '_execute_sell', new_callable=AsyncMock) as mock_sell, \
             patch.object(stage, '_execute_hold') as mock_hold:
            result = await stage.execute(hold_signal_context)

        # hold 실행 확인
        mock_hold.assert_called_once_with(hold_signal_context)

        # buy/sell은 호출되지 않음
        mock_buy.assert_not_called()
        mock_sell.assert_not_called()

        # 결과 검증
        assert result.success is True
        assert result.data['decision'] == 'hold'
        assert result.data['reason'] == 'Signal: hold (score: 0.5)'


class TestSellSignalExecution(TestSignalBasedExecution):
    """매도 신호 실행 테스트"""

    @pytest.mark.asyncio
    async def test_sell_signal_triggers_execution(self, sell_signal_context):
        """
        sell 신호가 ExecutionStage에서 매도로 처리되는지 검증
        """
        stage = ExecutionStage()

        with patch.object(stage, '_execute_sell', new_callable=AsyncMock) as mock_sell:
            result = await stage.execute(sell_signal_context)

        # 매도 실행 호출 확인
        mock_sell.assert_called_once_with(sell_signal_context)

        # 결과 검증
        assert result.success is True
        assert result.data['decision'] == 'sell'


class TestExecutionAmountCalculation(TestSignalBasedExecution):
    """실행 금액 계산 테스트"""

    @pytest.mark.asyncio
    async def test_execution_amount_calculation(self, buy_signal_context):
        """
        매수 금액이 올바르게 계산되는지 검증

        - 가용 잔고의 95%를 매수 (TradingConfig.BUY_RATIO)
        - 최소 주문 금액(5000원) 이상이어야 함
        """
        stage = ExecutionStage()

        # 잔고 100,000원 설정
        exchange_port = buy_signal_context.get_exchange_port()
        exchange_port.get_balance = AsyncMock(
            return_value=MagicMock(available=MagicMock(amount=Decimal("100000")))
        )

        # _calculate_buy_amount 직접 테스트
        calculated = stage._calculate_buy_amount(100000)

        # 95% = 95,000원
        assert calculated == 95000.0

    @pytest.mark.asyncio
    async def test_minimum_order_amount_check(self, buy_signal_context):
        """
        최소 주문 금액 미만일 때 매수가 발생하지 않는지 검증
        """
        stage = ExecutionStage()

        # 잔고가 너무 적을 때 (5000원 미만의 95% = 4750원)
        calculated = stage._calculate_buy_amount(5000)

        # 최소 주문 금액(5000원) 미만이면 0 반환
        assert calculated == 0


class TestDecisionTypeCompatibility(TestSignalBasedExecution):
    """DTO 호환성 테스트 - SignalDecisionDTO와 AIDecisionResult 호환"""

    @pytest.mark.asyncio
    async def test_confidence_levels_handled_correctly(self, mock_context):
        """
        confidence 레벨이 올바르게 처리되는지 검증

        - very_low는 low로 다운그레이드하지 않고 원본 유지
        - ExecutionStage는 confidence를 그대로 전달
        """
        # very_low confidence 설정
        mock_context.ai_result = {
            'decision': 'hold',
            'confidence': 'very_low',
            'reason': 'Signal: hold (score: 0.2)'
        }
        mock_context.signal_analysis = {
            'decision': 'hold',
            'confidence': 'very_low',
            'total_score': 0.2
        }

        stage = ExecutionStage()

        with patch.object(stage, '_execute_hold'):
            result = await stage.execute(mock_context)

        # very_low가 그대로 유지됨
        assert result.data['confidence'] == 'very_low'

    @pytest.mark.asyncio
    async def test_reason_format_from_signal_analyzer(self, buy_signal_context):
        """
        신호 기반 reason 포맷이 올바르게 전달되는지 검증

        예상 포맷: "Signal: {raw_decision} (score: {total_score})"
        """
        stage = ExecutionStage()

        with patch.object(stage, '_execute_buy', new_callable=AsyncMock):
            result = await stage.execute(buy_signal_context)

        # reason 포맷 검증
        reason = result.data['reason']
        assert reason.startswith('Signal:')
        assert 'score:' in reason
        assert '3.5' in reason


class TestIntegrationAnalysisToExecution:
    """AnalysisStage → ExecutionStage 통합 흐름 테스트"""

    @pytest.fixture
    def full_context(self):
        """전체 파이프라인 테스트용 컨텍스트"""
        context = MagicMock(spec=PipelineContext)
        context.ticker = "KRW-ETH"
        context.trading_type = "spot"
        context.container = MagicMock()

        # Exchange Port
        exchange_port = AsyncMock()
        exchange_port.get_current_price = AsyncMock(
            return_value=MagicMock(amount=Decimal("4500000"))
        )
        exchange_port.get_balance = AsyncMock(
            return_value=MagicMock(available=MagicMock(amount=Decimal("100000")))
        )
        context.get_exchange_port = MagicMock(return_value=exchange_port)

        # 데이터 수집 결과
        context.chart_data = {'day': pd.DataFrame({'close': [100, 101, 102]})}
        context.current_status = {'current_price': 4500000}
        context.technical_indicators = {
            'rsi': 35.0,
            'ma5': 4600000,
            'ma20': 4400000,
            'ma60': 4300000,
            'ema12': 4550000,
            'ema26': 4500000,
            'macd': 50000,
            'macd_signal': 40000,
            'macd_histogram': 10000,
            'stoch_k': 25,
            'stoch_d': 22,
            'bb_upper': 4700000,
            'bb_middle': 4500000,
            'bb_lower': 4300000,
        }
        context.market_correlation = None
        context.flash_crash = {'detected': False}
        context.rsi_divergence = {'type': 'none'}
        context.backtest_result = MagicMock(passed=True, metrics={}, filter_results={}, reason='')
        context.selected_coin = MagicMock(
            ticker='KRW-ETH',
            symbol='ETH',
            final_score=50.0,
            backtest_score=MagicMock(metrics={}, filter_results={})
        )
        context.pending_backtest_callback_data = None
        context.on_backtest_complete = None

        # 실행 관련
        context.ai_result = None
        context.signal_analysis = None
        context.trade_result = None
        context.validation_result = None
        context.position_check = True
        context.circuit_check = True
        context.frequency_check = True
        context.position_info = None
        context.risk_manager = None
        context.trading_service = MagicMock()

        return context

    @pytest.mark.asyncio
    async def test_analysis_to_execution_flow(self, full_context):
        """
        AnalysisStage(entry_mode=True) 결과가 ExecutionStage로 전달되는 전체 흐름 검증

        1. AnalysisStage가 entry_mode=True로 실행됨
        2. SignalAnalyzer 결과로 ai_result가 설정됨
        3. ExecutionStage가 ai_result를 읽어 거래 실행
        """
        # 1. AnalysisStage 실행 (entry_mode=True)
        analysis_stage = AnalysisStage(entry_mode=True)
        analysis_result = await analysis_stage.execute(full_context)

        # AnalysisStage 결과 검증
        assert analysis_result.success is True
        assert analysis_result.action == 'continue'  # ExecutionStage로 진행

        # ai_result가 설정되었는지 확인
        assert full_context.ai_result is not None
        assert full_context.ai_result['decision'] in ['buy', 'hold', 'sell']

        # signal_analysis도 설정됨
        assert full_context.signal_analysis is not None

        # 2. ExecutionStage 실행
        execution_stage = ExecutionStage()

        with patch.object(execution_stage, '_execute_buy', new_callable=AsyncMock), \
             patch.object(execution_stage, '_execute_sell', new_callable=AsyncMock), \
             patch.object(execution_stage, '_execute_hold'):
            execution_result = await execution_stage.execute(full_context)

        # ExecutionStage 결과 검증
        assert execution_result.success is True
        assert execution_result.action == 'exit'

        # 결과에 decision, reason, signal_analysis 포함
        assert execution_result.data['decision'] == full_context.ai_result['decision']
        assert 'Signal:' in execution_result.data['reason']
        assert execution_result.data['signal_analysis'] is not None
