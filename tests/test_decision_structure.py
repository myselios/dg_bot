"""
의사결정 구조 테스트
TDD 원칙: 파이프라인 아키텍처 기반 의사결정 구조를 테스트합니다.
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime


class TestPipelineDecisionStructure:
    """파이프라인 기반 의사결정 구조 테스트"""

    @pytest.fixture
    def sample_chart_data(self):
        """샘플 차트 데이터"""
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        prices = 100 + np.random.randn(50).cumsum()

        return {
            'day': pd.DataFrame({
                'open': prices * 0.99,
                'high': prices * 1.01,
                'low': prices * 0.98,
                'close': prices,
                'volume': np.random.randint(1000, 2000, 50)
            }, index=dates)
        }

    @pytest.fixture
    def mock_upbit_client(self):
        """Mock Upbit 클라이언트"""
        client = Mock()
        client.get_balance.return_value = 1000000.0
        client.get_current_price.return_value = 50000000.0
        return client

    @pytest.fixture
    def mock_data_collector(self):
        """Mock 데이터 수집기"""
        return Mock()

    @pytest.fixture
    def mock_trading_service(self):
        """Mock 거래 서비스"""
        return Mock()

    @pytest.fixture
    def mock_ai_service(self):
        """Mock AI 서비스"""
        return Mock()

    # ==================== 파이프라인 생성 테스트 ====================

    @pytest.mark.unit
    def test_create_spot_trading_pipeline_exists(self):
        """create_spot_trading_pipeline 함수가 존재하는지 테스트"""
        try:
            from src.trading.pipeline import create_spot_trading_pipeline
            assert callable(create_spot_trading_pipeline)
        except ImportError as e:
            pytest.fail(f"create_spot_trading_pipeline import 실패: {e}")

    @pytest.mark.unit
    def test_create_adaptive_trading_pipeline_exists(self):
        """create_adaptive_trading_pipeline 함수가 존재하는지 테스트"""
        try:
            from src.trading.pipeline import create_adaptive_trading_pipeline
            assert callable(create_adaptive_trading_pipeline)
        except ImportError as e:
            pytest.fail(f"create_adaptive_trading_pipeline import 실패: {e}")

    @pytest.mark.unit
    def test_pipeline_context_exists(self):
        """PipelineContext 클래스가 존재하는지 테스트"""
        try:
            from src.trading.pipeline import PipelineContext
            assert PipelineContext is not None
        except ImportError as e:
            pytest.fail(f"PipelineContext import 실패: {e}")

    @pytest.mark.unit
    def test_spot_pipeline_has_four_stages(self):
        """현물 파이프라인이 4개의 스테이지를 가지는지 테스트"""
        from src.trading.pipeline import create_spot_trading_pipeline

        pipeline = create_spot_trading_pipeline()

        assert len(pipeline.stages) == 4

    @pytest.mark.unit
    def test_adaptive_pipeline_has_four_stages(self):
        """적응형 파이프라인이 4개의 스테이지를 가지는지 테스트"""
        from src.trading.pipeline import create_adaptive_trading_pipeline

        pipeline = create_adaptive_trading_pipeline()

        assert len(pipeline.stages) == 4

    # ==================== execute_trading_cycle 테스트 ====================

    @pytest.mark.unit
    def test_execute_trading_cycle_exists(self):
        """execute_trading_cycle 함수가 존재하는지 테스트"""
        try:
            from main import execute_trading_cycle
            assert callable(execute_trading_cycle)
        except ImportError as e:
            pytest.fail(f"execute_trading_cycle import 실패: {e}")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_trading_cycle_returns_dict(
        self,
        mock_upbit_client,
        mock_data_collector,
        mock_trading_service,
        mock_ai_service
    ):
        """execute_trading_cycle이 Dict를 반환하는지 테스트"""
        from main import execute_trading_cycle
        from unittest.mock import MagicMock

        # Clean Architecture: TradingOrchestrator 모킹
        mock_result = {
            'status': 'success',
            'decision': 'hold',
            'pipeline_status': 'completed'
        }

        mock_orchestrator = MagicMock()
        mock_orchestrator.execute_trading_cycle = AsyncMock(return_value=mock_result)
        mock_orchestrator.set_on_backtest_complete = MagicMock()

        with patch('src.application.services.trading_orchestrator.TradingOrchestrator', return_value=mock_orchestrator):
            result = await execute_trading_cycle(
                ticker='KRW-BTC',
                upbit_client=mock_upbit_client,
                data_collector=mock_data_collector,
                enable_scanning=False  # 테스트용으로 스캔 비활성화
            )

            assert isinstance(result, dict)
            assert 'status' in result or 'decision' in result

    # ==================== AI Validator 테스트 ====================

    @pytest.mark.unit
    def test_ai_decision_validator_exists(self):
        """AIDecisionValidator 클래스가 존재하는지 테스트"""
        try:
            from src.ai.validator import AIDecisionValidator
            assert AIDecisionValidator is not None
        except ImportError as e:
            pytest.fail(f"AIDecisionValidator import 실패: {e}")

    @pytest.mark.unit
    def test_ai_validator_validate_decision_method(self):
        """AIDecisionValidator.validate_decision 메서드 테스트"""
        from src.ai.validator import AIDecisionValidator

        decision = {'decision': 'hold', 'confidence': 'medium', 'reason': '관망'}
        indicators = {'rsi': 50.0, 'atr_percent': 3.0, 'volume_ratio': 1.5, 'adx': 30.0}

        is_valid, reason, override = AIDecisionValidator.validate_decision(
            decision, indicators, None
        )

        assert isinstance(is_valid, bool)
        assert isinstance(reason, str)

    # ==================== RuleBasedBreakoutStrategy 테스트 ====================

    @pytest.mark.unit
    def test_rule_based_breakout_strategy_exists(self):
        """RuleBasedBreakoutStrategy 클래스가 존재하는지 테스트"""
        try:
            from src.backtesting.rule_based_strategy import RuleBasedBreakoutStrategy
            assert RuleBasedBreakoutStrategy is not None
        except ImportError as e:
            pytest.fail(f"RuleBasedBreakoutStrategy import 실패: {e}")

    @pytest.mark.unit
    def test_rule_based_strategy_generate_signal(self, sample_chart_data):
        """RuleBasedBreakoutStrategy.generate_signal 메서드 테스트"""
        from src.backtesting.rule_based_strategy import RuleBasedBreakoutStrategy

        strategy = RuleBasedBreakoutStrategy(
            ticker='KRW-BTC',
            risk_per_trade=0.02,
            max_position_size=0.3
        )

        signal = strategy.generate_signal(sample_chart_data['day'], None)

        # 신호는 TradingSignal 또는 None이어야 함
        if signal is not None:
            assert hasattr(signal, 'action')
            assert signal.action in ['buy', 'sell', 'hold']

    # ==================== QuickBacktestFilter 테스트 ====================

    @pytest.mark.unit
    def test_quick_backtest_filter_exists(self):
        """QuickBacktestFilter 클래스가 존재하는지 테스트"""
        try:
            from src.backtesting.quick_filter import QuickBacktestFilter
            assert QuickBacktestFilter is not None
        except ImportError as e:
            pytest.fail(f"QuickBacktestFilter import 실패: {e}")

    @pytest.mark.unit
    def test_quick_backtest_config_defaults(self):
        """QuickBacktestConfig 기본값 테스트"""
        from src.backtesting.quick_filter import QuickBacktestConfig

        config = QuickBacktestConfig()

        # 퀀트/헤지펀드 기준 강화된 설정
        assert config.min_return == 15.0
        assert config.min_win_rate == 38.0
        assert config.min_sharpe_ratio == 1.0
        assert config.max_drawdown == 15.0


class TestAIDecisionValidatorIntegration:
    """AIDecisionValidator 통합 테스트"""

    @pytest.fixture
    def sample_indicators(self):
        """샘플 기술적 지표"""
        return {
            'rsi': 50.0,
            'atr_percent': 3.0,
            'volume_ratio': 2.0,
            'adx': 30.0,
            'bb_width_pct': 5.0
        }

    @pytest.fixture
    def sample_buy_decision(self):
        """샘플 매수 판단"""
        return {
            'decision': 'buy',
            'confidence': 'high',
            'reason': '상승 추세 확인'
        }

    @pytest.mark.unit
    def test_validate_decision_hold_always_valid(self, sample_indicators):
        """HOLD 판단은 항상 유효"""
        from src.ai.validator import AIDecisionValidator

        decision = {'decision': 'hold', 'confidence': 'medium', 'reason': '관망'}

        is_valid, reason, override = AIDecisionValidator.validate_decision(
            decision, sample_indicators, None
        )

        assert is_valid is True

    @pytest.mark.unit
    def test_validate_decision_rsi_overbought(self, sample_buy_decision, sample_indicators):
        """RSI 과매수 시 매수 차단"""
        from src.ai.validator import AIDecisionValidator

        sample_indicators['rsi'] = 75.0  # 과매수

        is_valid, reason, override = AIDecisionValidator.validate_decision(
            sample_buy_decision, sample_indicators, None
        )

        assert is_valid is False
        assert override == 'hold'

    @pytest.mark.unit
    def test_validate_decision_high_volatility(self, sample_buy_decision, sample_indicators):
        """고변동성 시 매수 차단"""
        from src.ai.validator import AIDecisionValidator

        sample_indicators['atr_percent'] = 7.0  # 고변동성

        is_valid, reason, override = AIDecisionValidator.validate_decision(
            sample_buy_decision, sample_indicators, None
        )

        assert is_valid is False
        assert override == 'hold'

    @pytest.mark.unit
    def test_validate_decision_low_confidence(self, sample_indicators):
        """낮은 신뢰도 시 매수 차단"""
        from src.ai.validator import AIDecisionValidator

        decision = {'decision': 'buy', 'confidence': 'low', 'reason': ''}

        is_valid, reason, override = AIDecisionValidator.validate_decision(
            decision, sample_indicators, None
        )

        assert is_valid is False
        assert override == 'hold'

    @pytest.mark.unit
    def test_validate_decision_market_risk_high(self, sample_buy_decision, sample_indicators):
        """BTC 시장 리스크 높음 시 매수 차단"""
        from src.ai.validator import AIDecisionValidator

        market_conditions = {
            'market_correlation': {
                'market_risk': 'high',
                'risk_reason': 'BTC 급락 중'
            },
            'flash_crash': {'detected': False},
            'rsi_divergence': {'type': 'none'}
        }

        is_valid, reason, override = AIDecisionValidator.validate_decision(
            sample_buy_decision, sample_indicators, market_conditions
        )

        assert is_valid is False
        assert override == 'hold'

    @pytest.mark.unit
    def test_validate_decision_flash_crash(self, sample_buy_decision, sample_indicators):
        """플래시 크래시 감지 시 매수 차단"""
        from src.ai.validator import AIDecisionValidator

        market_conditions = {
            'market_correlation': {'market_risk': 'low'},
            'flash_crash': {
                'detected': True,
                'description': '5분 내 -10% 급락'
            },
            'rsi_divergence': {'type': 'none'}
        }

        is_valid, reason, override = AIDecisionValidator.validate_decision(
            sample_buy_decision, sample_indicators, market_conditions
        )

        assert is_valid is False
        assert override == 'hold'

    @pytest.mark.unit
    def test_validate_decision_bearish_divergence(self, sample_buy_decision, sample_indicators):
        """RSI 하락 다이버전스 시 매수 차단"""
        from src.ai.validator import AIDecisionValidator

        market_conditions = {
            'market_correlation': {'market_risk': 'low'},
            'flash_crash': {'detected': False},
            'rsi_divergence': {
                'type': 'bearish_divergence',
                'description': '가격 상승하나 RSI 하락'
            }
        }

        is_valid, reason, override = AIDecisionValidator.validate_decision(
            sample_buy_decision, sample_indicators, market_conditions
        )

        assert is_valid is False
        assert override == 'hold'
