"""
분석 스테이지

시장 분석, 기술적 분석, AI 분석 및 검증을 수행합니다.
- 시장 상관관계 분석
- 플래시 크래시 감지
- RSI 다이버전스 감지
- 백테스팅 필터
- 신호 분석
- AI 분석
- AI 판단 검증
"""
from typing import Dict, Optional
from src.trading.pipeline.base_stage import BasePipelineStage, PipelineContext, StageResult
from src.trading.indicators import TechnicalIndicators
from src.trading.signal_analyzer import SignalAnalyzer
from src.ai.market_correlation import calculate_market_risk
from src.ai.validator import AIDecisionValidator
from src.backtesting import QuickBacktestFilter
from src.utils.logger import Logger


class AnalysisStage(BasePipelineStage):
    """
    분석 스테이지

    시장 분석, 기술적 분석, AI 분석을 수행하고 결과를 검증합니다.
    """

    def __init__(self):
        super().__init__(name="Analysis")

    def execute(self, context: PipelineContext) -> StageResult:
        """
        분석 실행

        Args:
            context: 파이프라인 컨텍스트

        Returns:
            StageResult: 실행 결과
        """
        try:
            # 1. 시장 상관관계 분석
            self._analyze_market_correlation(context)

            # 2. 플래시 크래시 감지
            self._detect_flash_crash(context)

            # 3. RSI 다이버전스 감지
            self._detect_rsi_divergence(context)

            # 4. 백테스팅 필터
            backtest_result = self._run_backtest_filter(context)
            if not backtest_result.success or backtest_result.action == 'exit':
                return backtest_result

            # 5. 신호 분석
            self._analyze_signals(context)

            # 6. AI 분석
            ai_result = self._perform_ai_analysis(context)
            if not ai_result.success:
                return ai_result

            # 7. AI 판단 검증
            validation_result = self._validate_ai_decision(context)
            if validation_result.action == 'continue':
                Logger.print_success("✅ 분석 완료 - 거래 실행 단계로 진행")

            return validation_result

        except Exception as e:
            return self.handle_error(context, e)

    def _analyze_market_correlation(self, context: PipelineContext) -> None:
        """
        시장 상관관계 분석 (BTC vs 현재 코인)

        Args:
            context: 파이프라인 컨텍스트
        """
        context.market_correlation = calculate_market_risk(
            context.btc_chart_data['day'],
            context.chart_data['day']
        )

        # 현재 코인 심볼 추출 (KRW-ETH -> ETH)
        coin_symbol = context.ticker.replace('KRW-', '') if context.ticker else 'COIN'

        Logger.print_header("📊 시장 상관관계 분석")
        print(f"BTC-{coin_symbol} 베타: {context.market_correlation.get('beta', 1.0):.2f}")
        print(f"BTC-{coin_symbol} 알파: {context.market_correlation.get('alpha', 0.0):.4f}")
        print(f"상관계수: {context.market_correlation.get('correlation', 0.0):.2f}")
        print(f"시장 리스크: {context.market_correlation.get('market_risk', 'unknown')}")
        print(f"판단 근거: {context.market_correlation.get('risk_reason', 'N/A')}")
        print(Logger._separator() + "\n")

    def _detect_flash_crash(self, context: PipelineContext) -> None:
        """
        플래시 크래시 감지

        Args:
            context: 파이프라인 컨텍스트
        """
        context.flash_crash = TechnicalIndicators.detect_flash_crash(
            context.chart_data['day']
        )

        if context.flash_crash['detected']:
            Logger.print_warning(
                f"⚠️ 플래시 크래시 감지: {context.flash_crash['description']}"
            )
        else:
            Logger.print_success("✅ 플래시 크래시 없음")

    def _detect_rsi_divergence(self, context: PipelineContext) -> None:
        """
        RSI 다이버전스 감지

        Args:
            context: 파이프라인 컨텍스트
        """
        context.rsi_divergence = TechnicalIndicators.detect_rsi_divergence(
            context.chart_data['day']
        )

        Logger.print_header("📉 RSI 다이버전스 분석")
        print(f"다이버전스 타입: {context.rsi_divergence.get('type', 'none')}")
        print(f"신뢰도: {context.rsi_divergence.get('confidence', 'low')}")
        print(f"설명: {context.rsi_divergence.get('description', 'N/A')}")
        print(Logger._separator() + "\n")

    def _run_backtest_filter(self, context: PipelineContext) -> StageResult:
        """
        백테스팅 필터 실행

        Args:
            context: 파이프라인 컨텍스트

        Returns:
            StageResult: 필터 결과
        """
        quick_filter = QuickBacktestFilter()
        context.backtest_result = quick_filter.run_quick_backtest(
            context.ticker,
            chart_data=None
        )

        if not context.backtest_result.passed:
            Logger.print_error(
                f"백테스팅 필터링 조건 미달: {context.backtest_result.reason}"
            )
            Logger.print_warning("거래를 중단합니다. 보유 포지션을 유지합니다.")

            return StageResult(
                success=True,
                action='exit',
                data={
                    'decision': 'hold',
                    'confidence': 'medium',
                    'reason': f'백테스팅 필터링 실패: {context.backtest_result.reason}',
                    'price': 0,
                    'amount': 0,
                    'total': 0
                },
                message="백테스팅 필터링 실패 - 거래 중단"
            )

        Logger.print_success("✅ 백테스팅 필터링 조건 통과 - AI 심화 분석 진행")

        return StageResult(
            success=True,
            action='continue',
            message="백테스팅 필터 통과"
        )

    def _analyze_signals(self, context: PipelineContext) -> None:
        """
        신호 분석

        Args:
            context: 파이프라인 컨텍스트
        """
        if not context.technical_indicators or not context.current_status.get('current_price'):
            context.signal_analysis = None
            return

        context.signal_analysis = SignalAnalyzer.analyze_signals(
            context.technical_indicators,
            context.current_status['current_price']
        )

        Logger.print_header("📊 신호 분석 결과")
        print(f"결정: {context.signal_analysis['decision']}")
        print(f"매수 점수: {context.signal_analysis['buy_score']:.1f}")
        print(f"매도 점수: {context.signal_analysis['sell_score']:.1f}")
        print(f"총 점수: {context.signal_analysis['total_score']:.1f}")
        print(f"신호 강도: {context.signal_analysis['signal_strength']:.1f}")
        print(f"신뢰도: {context.signal_analysis['confidence']}")
        print("\n주요 신호:")
        for signal in context.signal_analysis['signals'][:10]:
            print(f"  • {signal}")
        print(Logger._separator() + "\n")

    def _perform_ai_analysis(self, context: PipelineContext) -> StageResult:
        """
        AI 분석 수행

        Args:
            context: 파이프라인 컨텍스트

        Returns:
            StageResult: 분석 결과
        """
        # 백테스팅 결과 요약
        backtest_summary = {
            'passed': context.backtest_result.passed,
            'metrics': context.backtest_result.metrics,
            'filter_results': context.backtest_result.filter_results,
            'reason': context.backtest_result.reason
        }

        # AI 분석 데이터 준비
        analysis_data = context.ai_service.prepare_analysis_data(
            context.chart_data,
            context.orderbook_summary,
            context.current_status,
            context.technical_indicators,
            context.position_info,
            context.fear_greed_index,
            backtest_result=backtest_summary,
            market_correlation=context.market_correlation,
            flash_crash=context.flash_crash,
            rsi_divergence=context.rsi_divergence
        )

        # AI 분석 수행
        context.ai_result = context.ai_service.analyze(context.ticker, analysis_data)

        if context.ai_result is None:
            Logger.print_error("AI 분석을 수행할 수 없습니다.")
            return StageResult(
                success=False,
                action='stop',
                message="AI 분석 실패",
                metadata={'error': 'AI 분석을 수행할 수 없습니다'}
            )

        # AI 판단 결과 출력
        Logger.print_decision(
            context.ai_result["decision"],
            context.ai_result["confidence"],
            context.ai_result["reason"]
        )

        return StageResult(
            success=True,
            action='continue',
            message="AI 분석 완료"
        )

    def _validate_ai_decision(self, context: PipelineContext) -> StageResult:
        """
        AI 판단 검증

        Args:
            context: 파이프라인 컨텍스트

        Returns:
            StageResult: 검증 결과
        """
        Logger.print_header("🔍 AI 판단 검증")

        # 시장 환경 정보 수집
        market_conditions = {
            'market_correlation': context.market_correlation,
            'flash_crash': context.flash_crash,
            'rsi_divergence': context.rsi_divergence
        }

        # AI 판단 검증
        context.validation_result = AIDecisionValidator.validate_decision(
            context.ai_result,
            context.technical_indicators,
            market_conditions
        )

        is_valid, validation_reason, override_decision = context.validation_result

        # 검증 결과 출력
        validation_report = AIDecisionValidator.generate_validation_report(
            context.validation_result,
            context.ai_result,
            context.technical_indicators
        )
        print(validation_report)

        # 검증 실패 시 AI 판단 오버라이드
        if not is_valid and override_decision:
            Logger.print_warning(f"⚠️ AI 판단 거부: {validation_reason}")
            context.ai_result['decision'] = override_decision
            context.ai_result['reason'] += f"\n[검증 레이어] {validation_reason}"
            context.ai_result['confidence'] = 'low'

        return StageResult(
            success=True,
            action='continue',
            message="AI 판단 검증 완료",
            data={'validation_reason': validation_reason}
        )
