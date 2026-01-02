"""
AnalysisStage UseCase 통합 테스트

TDD RED Phase: AnalysisStage가 AnalyzeMarketUseCase를 사용하도록 마이그레이션

테스트 시나리오:
1. AnalysisStage가 Container에서 UseCase를 받을 수 있는지 확인
2. AI 분석 시 UseCase.analyze() 호출 확인
3. TradingDecision → ai_result dict 변환 확인
4. 레거시 호환성 테스트 (Container 없을 때)
5. 에러 핸들링 테스트
"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from src.trading.pipeline.analysis_stage import AnalysisStage
from src.trading.pipeline.base_stage import PipelineContext, StageResult
from src.container import Container
from src.application.use_cases.analyze_market import AnalyzeMarketUseCase
from src.application.dto.analysis import TradingDecision, DecisionType


class TestAnalysisStageWithUseCase:
    """AnalysisStage + UseCase 통합 테스트"""

    @pytest.fixture
    def mock_container(self):
        """Container with mock UseCase"""
        mock_use_case = MagicMock(spec=AnalyzeMarketUseCase)
        mock_use_case.analyze = AsyncMock()
        mock_use_case.analyze_entry = AsyncMock()
        mock_use_case.analyze_exit = AsyncMock()

        container = MagicMock(spec=Container)
        container.get_analyze_market_use_case.return_value = mock_use_case

        return container, mock_use_case

    @pytest.fixture
    def mock_context(self, mock_container):
        """PipelineContext with Container and required data"""
        container, _ = mock_container

        context = PipelineContext(
            ticker="KRW-BTC",
            trading_type="spot",
            container=container,
            upbit_client=MagicMock(),
            data_collector=MagicMock(),
            ai_service=MagicMock(),
        )

        # 필수 데이터 설정
        context.chart_data = {
            'day': MagicMock(to_dict=lambda: {'close': [50000000]}),
            'hour': MagicMock(to_dict=lambda: {'close': [50000000]})
        }
        context.btc_chart_data = {
            'day': MagicMock(to_dict=lambda: {'close': [50000000]})
        }
        context.orderbook_summary = {'bid_ask_ratio': 1.0}
        context.current_status = {'current_price': 50000000}
        context.technical_indicators = {'rsi': 50, 'macd': 0}
        context.position_info = None
        context.fear_greed_index = {'value': 50}

        return context

    @pytest.mark.asyncio
    async def test_analysis_stage_uses_container_use_case(
        self, mock_context, mock_container
    ):
        """AI 분석 시 Container의 UseCase를 사용하는지 확인"""
        _, mock_use_case = mock_container

        # UseCase 응답 설정
        mock_use_case.analyze.return_value = TradingDecision(
            decision=DecisionType.BUY,
            confidence=Decimal("0.85"),
            reasoning="강력한 상승 신호"
        )

        # 백테스팅 결과 Mock
        with patch.object(AnalysisStage, '_run_backtest_filter') as mock_backtest:
            mock_backtest.return_value = StageResult(
                success=True,
                action='continue',
                message="백테스팅 통과"
            )

            # 검증 Mock
            with patch.object(AnalysisStage, '_validate_ai_decision') as mock_validate:
                mock_validate.return_value = StageResult(
                    success=True,
                    action='continue',
                    message="검증 완료"
                )

                # When: AnalysisStage 실행
                stage = AnalysisStage()
                result = await stage.execute(mock_context)

                # Then: UseCase.analyze()가 호출되어야 함
                mock_use_case.analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_trading_decision_converted_to_ai_result(
        self, mock_context, mock_container
    ):
        """TradingDecision이 ai_result dict로 변환되는지 확인"""
        _, mock_use_case = mock_container

        # UseCase 응답 설정
        mock_use_case.analyze.return_value = TradingDecision(
            decision=DecisionType.BUY,
            confidence=Decimal("0.85"),
            reasoning="강력한 상승 신호"
        )

        with patch.object(AnalysisStage, '_run_backtest_filter') as mock_backtest:
            mock_backtest.return_value = StageResult(
                success=True, action='continue', message=""
            )

            with patch.object(AnalysisStage, '_validate_ai_decision') as mock_validate:
                mock_validate.return_value = StageResult(
                    success=True, action='continue', message=""
                )

                stage = AnalysisStage()
                await stage.execute(mock_context)

                # Then: context.ai_result가 dict 형식으로 설정되어야 함
                assert mock_context.ai_result is not None
                assert mock_context.ai_result['decision'] == 'buy'
                assert mock_context.ai_result['confidence'] == 'high'
                assert '강력한 상승 신호' in mock_context.ai_result['reason']

    @pytest.mark.asyncio
    async def test_decision_type_mapping(self, mock_context, mock_container):
        """DecisionType이 올바르게 문자열로 변환되는지 확인"""
        _, mock_use_case = mock_container

        test_cases = [
            (DecisionType.BUY, 'buy'),
            (DecisionType.SELL, 'sell'),
            (DecisionType.HOLD, 'hold'),
        ]

        for decision_type, expected_str in test_cases:
            mock_use_case.analyze.return_value = TradingDecision(
                decision=decision_type,
                confidence=Decimal("0.5"),
                reasoning="테스트"
            )

            with patch.object(AnalysisStage, '_run_backtest_filter') as mock_backtest:
                mock_backtest.return_value = StageResult(
                    success=True, action='continue', message=""
                )

                with patch.object(AnalysisStage, '_validate_ai_decision') as mock_validate:
                    mock_validate.return_value = StageResult(
                        success=True, action='continue', message=""
                    )

                    stage = AnalysisStage()
                    await stage.execute(mock_context)

                    assert mock_context.ai_result['decision'] == expected_str

    @pytest.mark.asyncio
    async def test_confidence_level_mapping(self, mock_context, mock_container):
        """Decimal confidence가 올바르게 문자열 레벨로 변환되는지 확인"""
        _, mock_use_case = mock_container

        test_cases = [
            (Decimal("0.9"), 'high'),
            (Decimal("0.7"), 'high'),
            (Decimal("0.5"), 'medium'),
            (Decimal("0.3"), 'low'),
            (Decimal("0.1"), 'low'),
        ]

        for confidence_decimal, expected_level in test_cases:
            mock_use_case.analyze.return_value = TradingDecision(
                decision=DecisionType.HOLD,
                confidence=confidence_decimal,
                reasoning="테스트"
            )

            with patch.object(AnalysisStage, '_run_backtest_filter') as mock_backtest:
                mock_backtest.return_value = StageResult(
                    success=True, action='continue', message=""
                )

                with patch.object(AnalysisStage, '_validate_ai_decision') as mock_validate:
                    mock_validate.return_value = StageResult(
                        success=True, action='continue', message=""
                    )

                    stage = AnalysisStage()
                    await stage.execute(mock_context)

                    assert mock_context.ai_result['confidence'] == expected_level, \
                        f"Expected {expected_level} for confidence {confidence_decimal}"


class TestAnalysisStageBackwardCompatibility:
    """레거시 호환성 테스트"""

    @pytest.fixture
    def legacy_context(self):
        """Container 없는 레거시 PipelineContext"""
        mock_ai_service = MagicMock()
        mock_ai_service.prepare_analysis_data.return_value = {}
        mock_ai_service.analyze.return_value = {
            'decision': 'hold',
            'confidence': 'medium',
            'reason': '관망 필요'
        }

        context = PipelineContext(
            ticker="KRW-BTC",
            trading_type="spot",
            container=None,  # Container 없음
            upbit_client=MagicMock(),
            ai_service=mock_ai_service,
        )

        # 필수 데이터 설정
        context.chart_data = {
            'day': MagicMock(to_dict=lambda: {'close': [50000000]})
        }
        context.btc_chart_data = {
            'day': MagicMock(to_dict=lambda: {'close': [50000000]})
        }
        context.orderbook_summary = {}
        context.current_status = {'current_price': 50000000}
        context.technical_indicators = {'rsi': 50}
        context.fear_greed_index = {}
        context.position_info = {}

        # backtest_result Mock 설정 (레거시 코드에서 필요)
        mock_backtest_result = MagicMock()
        mock_backtest_result.passed = True
        mock_backtest_result.metrics = {}
        mock_backtest_result.filter_results = {}
        mock_backtest_result.reason = 'Test passed'
        context.backtest_result = mock_backtest_result

        return context

    @pytest.mark.asyncio
    async def test_analysis_stage_falls_back_to_ai_service(self, legacy_context):
        """Container 없으면 레거시 ai_service 사용"""
        with patch.object(AnalysisStage, '_run_backtest_filter') as mock_backtest:
            mock_backtest.return_value = StageResult(
                success=True, action='continue', message=""
            )

            with patch.object(AnalysisStage, '_validate_ai_decision') as mock_validate:
                mock_validate.return_value = StageResult(
                    success=True, action='continue', message=""
                )

                stage = AnalysisStage()
                result = await stage.execute(legacy_context)

                # Then: 레거시 ai_service가 호출되어야 함
                legacy_context.ai_service.analyze.assert_called_once()
                assert legacy_context.ai_result['decision'] == 'hold'


class TestAnalysisStageErrorHandling:
    """에러 핸들링 테스트"""

    @pytest.fixture
    def error_container(self):
        """에러를 발생시키는 UseCase"""
        mock_use_case = MagicMock(spec=AnalyzeMarketUseCase)
        mock_use_case.analyze = AsyncMock(
            return_value=TradingDecision(
                decision=DecisionType.HOLD,
                confidence=Decimal("0"),
                reasoning="Analysis failed: 네트워크 오류"
            )
        )

        container = MagicMock(spec=Container)
        container.get_analyze_market_use_case.return_value = mock_use_case

        return container

    @pytest.mark.asyncio
    async def test_analysis_stage_handles_use_case_error(self, error_container):
        """UseCase 실패 시 적절히 처리"""
        context = PipelineContext(
            ticker="KRW-BTC",
            trading_type="spot",
            container=error_container,
            upbit_client=MagicMock(),
        )

        context.chart_data = {'day': MagicMock(to_dict=lambda: {})}
        context.btc_chart_data = {'day': MagicMock(to_dict=lambda: {})}
        context.orderbook_summary = {}
        context.current_status = {'current_price': 50000000}
        context.technical_indicators = {}
        context.fear_greed_index = {}

        with patch.object(AnalysisStage, '_run_backtest_filter') as mock_backtest:
            mock_backtest.return_value = StageResult(
                success=True, action='continue', message=""
            )

            with patch.object(AnalysisStage, '_validate_ai_decision') as mock_validate:
                mock_validate.return_value = StageResult(
                    success=True, action='continue', message=""
                )

                stage = AnalysisStage()
                result = await stage.execute(context)

                # Then: 에러 상태이면 hold로 처리
                assert context.ai_result['decision'] == 'hold'

    @pytest.mark.asyncio
    async def test_analysis_stage_handles_use_case_exception(self):
        """UseCase 예외 발생 시 적절히 처리"""
        mock_use_case = MagicMock(spec=AnalyzeMarketUseCase)
        mock_use_case.analyze = AsyncMock(side_effect=Exception("API 오류"))

        container = MagicMock(spec=Container)
        container.get_analyze_market_use_case.return_value = mock_use_case

        context = PipelineContext(
            ticker="KRW-BTC",
            trading_type="spot",
            container=container,
            upbit_client=MagicMock(),
        )

        context.chart_data = {'day': MagicMock(to_dict=lambda: {})}
        context.btc_chart_data = {'day': MagicMock(to_dict=lambda: {})}
        context.orderbook_summary = {}
        context.current_status = {'current_price': 50000000}
        context.technical_indicators = {}
        context.fear_greed_index = {}

        with patch.object(AnalysisStage, '_run_backtest_filter') as mock_backtest:
            mock_backtest.return_value = StageResult(
                success=True, action='continue', message=""
            )

            stage = AnalysisStage()
            result = await stage.execute(context)

            # Then: handle_error가 호출되어 실패 결과 반환
            assert result.success is False
            assert 'error' in result.metadata


class TestAnalysisStagePreserveExistingLogic:
    """기존 분석 로직 보존 테스트"""

    @pytest.fixture
    def full_context(self):
        """전체 분석 로직 테스트용 컨텍스트"""
        mock_use_case = MagicMock(spec=AnalyzeMarketUseCase)
        mock_use_case.analyze = AsyncMock(return_value=TradingDecision(
            decision=DecisionType.BUY,
            confidence=Decimal("0.8"),
            reasoning="테스트"
        ))

        container = MagicMock(spec=Container)
        container.get_analyze_market_use_case.return_value = mock_use_case

        context = PipelineContext(
            ticker="KRW-BTC",
            trading_type="spot",
            container=container,
            upbit_client=MagicMock(),
        )

        context.chart_data = {'day': MagicMock(to_dict=lambda: {'close': [1, 2, 3]})}
        context.btc_chart_data = {'day': MagicMock(to_dict=lambda: {'close': [1, 2, 3]})}
        context.orderbook_summary = {}
        context.current_status = {'current_price': 50000000}
        context.technical_indicators = {'rsi': 50}
        context.fear_greed_index = {}

        return context

    @pytest.mark.asyncio
    async def test_market_correlation_still_calculated(self, full_context):
        """시장 상관관계 분석이 여전히 수행되는지 확인"""
        with patch('src.trading.pipeline.analysis_stage.calculate_market_risk') as mock_calc:
            mock_calc.return_value = {'beta': 1.0, 'correlation': 0.8}

            with patch.object(AnalysisStage, '_run_backtest_filter') as mock_backtest:
                mock_backtest.return_value = StageResult(
                    success=True, action='continue', message=""
                )

                with patch.object(AnalysisStage, '_validate_ai_decision') as mock_validate:
                    mock_validate.return_value = StageResult(
                        success=True, action='continue', message=""
                    )

                    stage = AnalysisStage()
                    await stage.execute(full_context)

                    # Then: 시장 상관관계가 계산되어야 함
                    mock_calc.assert_called_once()
                    assert full_context.market_correlation is not None

    @pytest.mark.asyncio
    async def test_flash_crash_detection_still_works(self, full_context):
        """플래시 크래시 감지가 여전히 수행되는지 확인"""
        with patch('src.trading.pipeline.analysis_stage.TechnicalIndicators.detect_flash_crash') as mock_detect:
            mock_detect.return_value = {'detected': False}

            with patch.object(AnalysisStage, '_run_backtest_filter') as mock_backtest:
                mock_backtest.return_value = StageResult(
                    success=True, action='continue', message=""
                )

                with patch.object(AnalysisStage, '_validate_ai_decision') as mock_validate:
                    mock_validate.return_value = StageResult(
                        success=True, action='continue', message=""
                    )

                    stage = AnalysisStage()
                    await stage.execute(full_context)

                    # Then: 플래시 크래시 감지가 수행되어야 함
                    mock_detect.assert_called_once()
                    assert full_context.flash_crash is not None

    @pytest.mark.asyncio
    async def test_rsi_divergence_detection_still_works(self, full_context):
        """RSI 다이버전스 감지가 여전히 수행되는지 확인"""
        with patch('src.trading.pipeline.analysis_stage.TechnicalIndicators.detect_rsi_divergence') as mock_detect:
            mock_detect.return_value = {'type': 'none'}

            with patch.object(AnalysisStage, '_run_backtest_filter') as mock_backtest:
                mock_backtest.return_value = StageResult(
                    success=True, action='continue', message=""
                )

                with patch.object(AnalysisStage, '_validate_ai_decision') as mock_validate:
                    mock_validate.return_value = StageResult(
                        success=True, action='continue', message=""
                    )

                    stage = AnalysisStage()
                    await stage.execute(full_context)

                    # Then: RSI 다이버전스 감지가 수행되어야 함
                    mock_detect.assert_called_once()
                    assert full_context.rsi_divergence is not None

    @pytest.mark.asyncio
    async def test_validation_still_performed(self, full_context):
        """AI 판단 검증이 여전히 수행되는지 확인"""
        with patch.object(AnalysisStage, '_run_backtest_filter') as mock_backtest:
            mock_backtest.return_value = StageResult(
                success=True, action='continue', message=""
            )

            with patch('src.trading.pipeline.analysis_stage.AIDecisionValidator.validate_decision') as mock_validate:
                mock_validate.return_value = (True, "검증 통과", None)

                with patch('src.trading.pipeline.analysis_stage.AIDecisionValidator.generate_validation_report') as mock_report:
                    mock_report.return_value = "검증 보고서"

                    stage = AnalysisStage()
                    await stage.execute(full_context)

                    # Then: 검증이 수행되어야 함
                    mock_validate.assert_called_once()
