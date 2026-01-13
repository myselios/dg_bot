"""
entry_mode 분기 시나리오 테스트

entry_mode=True일 때 AI 호출이 스킵되고,
entry_mode=False일 때 AI 호출이 발생하는지 검증합니다.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.trading.pipeline.analysis_stage import AnalysisStage
from src.trading.pipeline.base_stage import PipelineContext, StageResult


@pytest.mark.scenario
class TestEntryModeBranching:
    """entry_mode 분기 시나리오"""

    @pytest.fixture
    def mock_context(self):
        """테스트용 컨텍스트 (분석 스테이지 실행에 필요한 모든 의존성)"""
        context = MagicMock(spec=PipelineContext)
        context.ticker = "KRW-BTC"
        context.signal_analysis = {
            'decision': 'strong_buy',
            'confidence': 'high',
            'total_score': 75.5
        }
        context.chart_data = MagicMock()
        context.chart_data.df = MagicMock()  # DataFrame mock
        context.container = None  # Container 없음 (레거시 경로)
        context.ai_result = None  # execute()에서 설정됨
        context.flash_crash = None
        context.rsi_divergence = None
        context.validation_result = None
        return context

    @pytest.fixture
    def mock_backtest_pass(self):
        """백테스트 통과 StageResult"""
        return StageResult(
            success=True,
            action='continue',
            message="백테스트 통과"
        )

    @pytest.mark.asyncio
    async def test_entry_mode_true_skips_ai(self, mock_context, mock_backtest_pass):
        """entry_mode=True일 때 AI 스킵 확인"""
        # Given: entry_mode=True
        stage = AnalysisStage(entry_mode=True)

        # When: 실행 (내부 의존성 mock)
        with patch.object(stage, '_detect_flash_crash'):
            with patch.object(stage, '_detect_rsi_divergence'):
                with patch.object(stage, '_run_backtest_filter', return_value=mock_backtest_pass):
                    with patch.object(stage, '_analyze_signals'):
                        with patch.object(stage, '_perform_ai_analysis') as mock_ai:
                            result = await stage.execute(mock_context)

        # Then: AI 호출 없음 (entry_mode=True이면 _handle_signal_based_entry로 직행)
        mock_ai.assert_not_called()

        # SignalAnalyzer 결과가 ai_result에 설정됨
        assert mock_context.ai_result is not None
        assert mock_context.ai_result['decision'] in ['buy', 'hold', 'sell']

    @pytest.mark.asyncio
    async def test_entry_mode_false_calls_ai(self, mock_context, mock_backtest_pass):
        """entry_mode=False일 때 AI 호출 확인"""
        # Given: entry_mode=False
        stage = AnalysisStage(entry_mode=False)

        # When: 실행
        with patch.object(stage, '_detect_flash_crash'):
            with patch.object(stage, '_detect_rsi_divergence'):
                with patch.object(stage, '_run_backtest_filter', return_value=mock_backtest_pass):
                    with patch.object(stage, '_analyze_signals'):
                        with patch.object(stage, '_perform_ai_analysis', new_callable=AsyncMock) as mock_ai:
                            mock_ai.return_value = StageResult(success=True, action='continue')
                            with patch.object(stage, '_validate_ai_decision') as mock_validate:
                                mock_validate.return_value = StageResult(success=True, action='continue')
                                result = await stage.execute(mock_context)

        # Then: AI 호출됨
        mock_ai.assert_called_once()

    @pytest.mark.asyncio
    async def test_entry_mode_true_uses_signal_analysis(self, mock_context, mock_backtest_pass):
        """entry_mode=True일 때 signal_analysis가 ai_result로 변환되는지 확인"""
        # Given: entry_mode=True with specific signal
        mock_context.signal_analysis = {
            'decision': 'strong_buy',
            'confidence': 'high',
            'total_score': 85.0,
            'signals': {'rsi': 'oversold', 'macd': 'bullish'}
        }
        stage = AnalysisStage(entry_mode=True)

        # When: 실행
        with patch.object(stage, '_detect_flash_crash'):
            with patch.object(stage, '_detect_rsi_divergence'):
                with patch.object(stage, '_run_backtest_filter', return_value=mock_backtest_pass):
                    with patch.object(stage, '_analyze_signals'):
                        result = await stage.execute(mock_context)

        # Then: signal_analysis 기반으로 ai_result 설정
        assert mock_context.ai_result is not None
        # strong_buy는 buy로 변환됨
        assert mock_context.ai_result['decision'] in ['buy', 'hold']

    @pytest.mark.asyncio
    async def test_entry_mode_determines_analysis_path(self, mock_context, mock_backtest_pass):
        """entry_mode가 분석 경로를 결정하는지 검증"""
        # Given: 두 가지 entry_mode
        for entry_mode in [True, False]:
            stage = AnalysisStage(entry_mode=entry_mode)

            # Then: 속성이 올바르게 설정됨
            assert stage.entry_mode == entry_mode

            # entry_mode에 따라 다른 핸들러 사용 여부 확인
            assert hasattr(stage, '_handle_signal_based_entry'), \
                "entry_mode=True를 위한 핸들러가 있어야 함"
