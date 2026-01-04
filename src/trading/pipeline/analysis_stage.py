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

Clean Architecture Migration (2026-01-03):
- Container가 있으면 AnalyzeMarketUseCase 사용 (클린 아키텍처)
- Container가 없으면 Port를 통해 레거시 서비스 사용 (하위 호환성)
"""
from decimal import Decimal
from typing import Dict, Optional, Any, Tuple

from src.trading.pipeline.base_stage import BasePipelineStage, PipelineContext, StageResult
from src.trading.indicators import TechnicalIndicators
from src.trading.signal_analyzer import SignalAnalyzer
# market_correlation, validator 제거됨 - Clean Architecture 마이그레이션 완료
# TODO: AnalysisStage deprecated - HybridRiskCheckStage 사용
from src.backtesting import QuickBacktestFilter, QuickBacktestResult
from src.utils.logger import Logger


class AnalysisStage(BasePipelineStage):
    """
    분석 스테이지

    시장 분석, 기술적 분석, AI 분석을 수행하고 결과를 검증합니다.

    Container가 있으면 AnalyzeMarketUseCase를 사용하고,
    없으면 레거시 ai_service를 사용합니다 (호환성 유지).
    """

    def __init__(self):
        super().__init__(name="Analysis")

    def _get_ai_service(self, context: PipelineContext) -> Any:
        """
        Container 또는 context에서 AI 서비스 인스턴스 획득

        Container가 있으면 AIPort에서 추출,
        없으면 context의 레거시 서비스 사용 (하위 호환성)

        Returns:
            ai_service 인스턴스
        """
        if context.container:
            # Container에서 AIPort 획득 후 내부 레거시 서비스 추출
            ai_port = context.container.get_ai_port()
            return getattr(ai_port, '_service', context.ai_service)
        else:
            # 레거시 방식 (하위 호환성)
            return context.ai_service

    async def execute(self, context: PipelineContext) -> StageResult:
        """
        분석 실행 (비동기)

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
            ai_result = await self._perform_ai_analysis(context)
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

        ⚠️ DEPRECATED: calculate_market_risk 제거됨
        TODO: MarketAnalysisService (domain/services/market_analysis.py) 사용

        Args:
            context: 파이프라인 컨텍스트
        """
        # Stub: 레거시 AI 함수 제거됨 - 기본값 반환
        context.market_correlation = {
            'beta': 1.0,
            'alpha': 0.0,
            'correlation': 0.0,
            'market_risk': 'unknown',
            'risk_reason': 'Legacy calculate_market_risk removed - use MarketAnalysisService'
        }

        # 현재 코인 심볼 추출 (KRW-ETH -> ETH)
        coin_symbol = context.ticker.replace('KRW-', '') if context.ticker else 'COIN'

        Logger.print_header("📊 시장 상관관계 분석 (STUB)")
        print(f"⚠️ Legacy calculate_market_risk 제거됨")
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

        HybridRiskCheckStage에서 이미 스캔/선택된 코인은 스킵합니다.
        (CoinSelector가 이미 ResearchPass + TradingPass 필터를 적용했음)

        Args:
            context: 파이프라인 컨텍스트

        Returns:
            StageResult: 필터 결과
        """
        # 스캔으로 선택된 코인이면 중복 백테스팅 스킵
        if hasattr(context, 'selected_coin') and context.selected_coin is not None:
            Logger.print_info("📊 스캔에서 이미 필터링 완료 - 백테스팅 스킵")

            # 선택된 코인의 백테스트 결과 활용
            selected = context.selected_coin
            if hasattr(selected, 'backtest_score') and selected.backtest_score:
                # QuickBacktestResult 형태로 변환
                context.backtest_result = QuickBacktestResult(
                    passed=True,
                    result=None,
                    metrics=selected.backtest_score.metrics or {},
                    filter_results=selected.backtest_score.filter_results or {},
                    reason=f"스캔에서 선택됨 (점수: {selected.final_score:.1f}점)"
                )
            else:
                # 백테스트 정보 없으면 기본값
                context.backtest_result = QuickBacktestResult(
                    passed=True,
                    result=None,
                    metrics={},
                    filter_results={},
                    reason=f"스캔에서 선택됨 (점수: {selected.final_score:.1f}점)"
                )

            Logger.print_success(f"✅ {selected.symbol} 선택됨 ({selected.final_score:.1f}점) - AI 분석 진행")

            return StageResult(
                success=True,
                action='continue',
                message=f"스캔에서 선택된 코인: {selected.symbol}"
            )

        # 고정 티커 사용 시 기존 백테스팅 수행
        quick_filter = QuickBacktestFilter()
        context.backtest_result = quick_filter.run_quick_backtest(
            context.ticker,
            chart_data=None
        )

        if not context.backtest_result.passed:
            Logger.print_error(
                f"❌ 백테스팅 필터링 조건 미달: {context.backtest_result.reason}"
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

        # 백테스팅 완료 콜백 데이터를 컨텍스트에 저장 (파이프라인에서 await 처리)
        context.pending_backtest_callback_data = {
            'ticker': context.ticker,
            'backtest_result': {
                'passed': context.backtest_result.passed,
                'metrics': context.backtest_result.metrics,
                'filter_results': context.backtest_result.filter_results,
                'reason': context.backtest_result.reason
            },
            'flash_crash': context.flash_crash,
            'rsi_divergence': context.rsi_divergence,
            'technical_indicators': context.technical_indicators
        }

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

    def _has_use_case(self, context: PipelineContext) -> bool:
        """Container와 UseCase 사용 가능 여부 확인"""
        return context.container is not None

    async def _perform_ai_analysis(self, context: PipelineContext) -> StageResult:
        """
        AI 분석 수행

        Container가 있으면 UseCase 사용, 없으면 레거시 서비스 사용

        Args:
            context: 파이프라인 컨텍스트

        Returns:
            StageResult: 분석 결과
        """
        if self._has_use_case(context):
            return await self._perform_ai_analysis_with_use_case(context)
        else:
            return self._perform_ai_analysis_legacy(context)

    async def _perform_ai_analysis_with_use_case(self, context: PipelineContext) -> StageResult:
        """UseCase를 통한 AI 분석 수행"""
        use_case = context.container.get_analyze_market_use_case()

        # context에서 현재가 추출
        current_price = None
        if context.current_status:
            current_price = context.current_status.get('current_price')

        # 추가 컨텍스트 구성 (백테스팅 결과, 시장 상관관계 등)
        additional_context = {}
        if context.backtest_result:
            additional_context['backtest_result'] = {
                'passed': context.backtest_result.passed,
                'metrics': context.backtest_result.metrics,
                'reason': context.backtest_result.reason,
            }
        if context.market_correlation:
            additional_context['market_correlation'] = context.market_correlation
        if context.flash_crash:
            additional_context['flash_crash'] = context.flash_crash
        if context.rsi_divergence:
            additional_context['rsi_divergence'] = context.rsi_divergence

        # UseCase 실행 (context 데이터 전달)
        trading_decision = await use_case.analyze(
            ticker=context.ticker,
            chart_data=context.chart_data,
            technical_indicators=context.technical_indicators,
            current_price=current_price,
            additional_context=additional_context if additional_context else None,
        )

        # TradingDecision → ai_result dict 변환
        context.ai_result = self._convert_trading_decision_to_dict(trading_decision)

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

    def _perform_ai_analysis_legacy(self, context: PipelineContext) -> StageResult:
        """레거시 서비스를 통한 AI 분석 수행"""
        # AI 서비스 획득
        ai_service = self._get_ai_service(context)

        # 백테스팅 결과 요약
        backtest_summary = {
            'passed': context.backtest_result.passed,
            'metrics': context.backtest_result.metrics,
            'filter_results': context.backtest_result.filter_results,
            'reason': context.backtest_result.reason
        }

        # AI 분석 데이터 준비
        analysis_data = ai_service.prepare_analysis_data(
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
        context.ai_result = ai_service.analyze(context.ticker, analysis_data)

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

    def _convert_trading_decision_to_dict(self, trading_decision) -> Dict[str, Any]:
        """
        TradingDecision을 레거시 ai_result dict 형식으로 변환

        Args:
            trading_decision: TradingDecision 객체

        Returns:
            레거시 형식의 dict
        """
        from src.application.dto.analysis import DecisionType

        # DecisionType → 문자열 변환
        decision_map = {
            DecisionType.BUY: 'buy',
            DecisionType.SELL: 'sell',
            DecisionType.HOLD: 'hold',
        }

        decision_str = decision_map.get(trading_decision.decision, 'hold')

        # Decimal confidence → 문자열 레벨 변환
        confidence_level = self._convert_confidence_to_level(trading_decision.confidence)

        return {
            'decision': decision_str,
            'confidence': confidence_level,
            'reason': trading_decision.reasoning,
        }

    def _convert_confidence_to_level(self, confidence: Decimal) -> str:
        """
        Decimal confidence를 문자열 레벨로 변환

        Args:
            confidence: 0-1 사이의 Decimal 값

        Returns:
            'high', 'medium', 'low' 중 하나
        """
        if confidence >= Decimal("0.7"):
            return 'high'
        elif confidence >= Decimal("0.4"):
            return 'medium'
        else:
            return 'low'

    def _validate_ai_decision(self, context: PipelineContext) -> StageResult:
        """
        AI 판단 검증

        Args:
            context: 파이프라인 컨텍스트

        Returns:
            StageResult: 검증 결과
        """
        Logger.print_header("🔍 AI 판단 검증 (STUB)")
        print("⚠️ Legacy AIDecisionValidator 제거됨 - ValidationPort 사용 권장")

        # Stub: 레거시 AI validator 제거됨 - 기본값 반환 (항상 유효)
        is_valid = True
        validation_reason = "Legacy AIDecisionValidator removed - use ValidationPort"
        override_decision = None

        context.validation_result = (is_valid, validation_reason, override_decision)

        # 검증 결과 출력
        validation_report = f"""
[AI 판단 검증 결과 - STUB]
- 유효성: {is_valid}
- 사유: {validation_reason}
- 오버라이드: {override_decision}
"""
        print(validation_report)

        # 검증 실패 시 AI 판단 오버라이드 (현재는 항상 통과)
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
