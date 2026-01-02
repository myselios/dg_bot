"""
적응형 리스크 체크 스테이지 (Adaptive Risk Check Stage)

포지션 유무에 따라 거래 로직을 분기하는 핵심 스테이지입니다.

거래 흐름:
1. 포트폴리오 상태 확인
2. 거래 모드 결정 (ENTRY / MANAGEMENT / BLOCKED)
3. 모드에 따른 분기 처리

ENTRY 모드 (포지션 없음 또는 추가 가능):
- 유동성 스캔 → 백테스팅 → AI 진입 분석 → 실행

MANAGEMENT 모드 (포지션 있음):
- 규칙 기반 체크 → 필요시 AI 분석 → 청산/유지/조정
"""
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.trading.pipeline.base_stage import BasePipelineStage, PipelineContext, StageResult
from src.position.portfolio_manager import PortfolioManager, TradingMode, PortfolioPosition
from src.ai.position_analyzer import PositionAnalyzer, Position, PositionAction, PositionActionType
from src.utils.logger import Logger


class AdaptiveRiskCheckStage(BasePipelineStage):
    """
    적응형 리스크 체크 스테이지

    포지션 상태에 따라 ENTRY/MANAGEMENT 모드로 분기합니다.
    """

    def __init__(
        self,
        stop_loss_pct: float = -5.0,
        take_profit_pct: float = 10.0,
        daily_loss_limit_pct: float = -10.0,
        min_trade_interval_hours: int = 4,
        max_positions: int = 3
    ):
        """
        Args:
            stop_loss_pct: 손절 비율 (%)
            take_profit_pct: 익절 비율 (%)
            daily_loss_limit_pct: 일일 최대 손실 비율 (%)
            min_trade_interval_hours: 최소 거래 간격 (시간)
            max_positions: 최대 동시 포지션 수
        """
        super().__init__(name="AdaptiveRiskCheck")
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.daily_loss_limit_pct = daily_loss_limit_pct
        self.min_trade_interval_hours = min_trade_interval_hours
        self.max_positions = max_positions

    async def execute(self, context: PipelineContext) -> StageResult:
        """
        적응형 리스크 체크 실행 (비동기)

        Args:
            context: 파이프라인 컨텍스트

        Returns:
            StageResult: 실행 결과
        """
        try:
            Logger.print_header("🔄 적응형 리스크 체크")

            # 1. 포트폴리오 매니저 초기화
            portfolio_manager = PortfolioManager(
                exchange_client=context.upbit_client,
                max_positions=self.max_positions
            )
            context.portfolio_manager = portfolio_manager

            # 2. 포트폴리오 상태 확인
            portfolio_status = portfolio_manager.get_portfolio_status()
            context.portfolio_status = portfolio_status

            # 포트폴리오 요약 출력
            portfolio_manager.print_portfolio_summary()

            # 3. 포트폴리오 레벨 리스크 체크
            risk_check = portfolio_manager.check_portfolio_risk()
            if not risk_check['allowed']:
                Logger.print_error(f"⛔ 포트폴리오 서킷 브레이커: {risk_check['reason']}")
                return StageResult(
                    success=True,
                    action='exit',
                    data={
                        'status': 'blocked',
                        'decision': 'hold',
                        'reason': risk_check['reason'],
                        'risk_checks': {'portfolio_risk': risk_check}
                    },
                    message="포트폴리오 서킷 브레이커 발동"
                )

            # 4. 거래 모드 확인 및 분기
            trading_mode = portfolio_status.trading_mode
            Logger.print_info(f"📊 거래 모드: {trading_mode.value}")

            # 컨텍스트에 모드 저장
            context.trading_mode = trading_mode.value

            if trading_mode == TradingMode.BLOCKED:
                return self._handle_blocked_mode(context, portfolio_status)

            elif trading_mode == TradingMode.MANAGEMENT or len(portfolio_status.positions) > 0:
                # 포지션이 있으면 먼저 관리 로직 실행
                management_result = self._handle_management_mode(context, portfolio_status)

                # 청산 실행된 경우
                if management_result.action == 'exit':
                    return management_result

                # 추가 진입 가능한 경우
                if portfolio_status.can_open_new_position:
                    Logger.print_info("📈 추가 진입 가능 - ENTRY 모드로 전환")
                    context.trading_mode = 'entry'
                    return StageResult(
                        success=True,
                        action='continue',
                        message="포지션 관리 완료, 추가 진입 탐색"
                    )
                else:
                    return StageResult(
                        success=True,
                        action='skip',
                        data={
                            'status': 'success',
                            'decision': 'hold',
                            'reason': '포지션 관리 완료, 추가 진입 불가'
                        },
                        message="최대 포지션 도달"
                    )

            else:
                # ENTRY 모드
                return self._handle_entry_mode(context, portfolio_status)

        except Exception as e:
            return self.handle_error(context, e)

    def _handle_blocked_mode(
        self,
        context: PipelineContext,
        portfolio_status
    ) -> StageResult:
        """
        BLOCKED 모드 처리 (서킷 브레이커 발동)
        """
        Logger.print_error("⛔ 거래 차단 상태")
        return StageResult(
            success=True,
            action='exit',
            data={
                'status': 'blocked',
                'decision': 'hold',
                'reason': '서킷 브레이커 발동으로 거래 중단'
            },
            message="거래 차단 상태"
        )

    def _handle_management_mode(
        self,
        context: PipelineContext,
        portfolio_status
    ) -> StageResult:
        """
        MANAGEMENT 모드 처리 (포지션 관리)

        하이브리드 방식:
        1. 규칙 기반 청산 조건 체크 (무료, 즉시)
        2. 애매한 상황에서만 AI 분석 (유료)
        """
        Logger.print_info(f"📋 포지션 관리 모드: {len(portfolio_status.positions)}개 포지션")

        # 포지션 분석기 초기화
        position_analyzer = PositionAnalyzer(
            stop_loss_pct=self.stop_loss_pct,
            take_profit_pct=self.take_profit_pct
        )
        context.position_analyzer = position_analyzer

        actions_taken = []
        exit_performed = False

        for portfolio_pos in portfolio_status.positions:
            Logger.print_info(f"\n  [{portfolio_pos.symbol}] 분석 중...")

            # PortfolioPosition → Position 변환
            position = Position(
                ticker=portfolio_pos.ticker,
                entry_price=portfolio_pos.avg_buy_price,
                current_price=portfolio_pos.current_price,
                amount=portfolio_pos.amount,
                entry_time=portfolio_pos.entry_time or datetime.now()
            )

            # 시장 데이터 수집 (간소화된 버전)
            market_data = self._collect_position_market_data(context, portfolio_pos.ticker)

            # 포지션 분석 (하이브리드)
            action = position_analyzer.analyze(position, market_data)

            # 액션 실행
            if action.action == PositionActionType.EXIT:
                Logger.print_warning(f"  → 청산 실행: {action.reason}")
                sell_result = self._execute_exit(context, portfolio_pos, action)
                actions_taken.append({
                    'ticker': portfolio_pos.ticker,
                    'action': 'exit',
                    'reason': action.reason,
                    'result': sell_result
                })
                exit_performed = True

            elif action.action == PositionActionType.PARTIAL_EXIT:
                Logger.print_info(f"  → 부분 청산: {action.exit_ratio*100:.0f}%")
                partial_result = self._execute_partial_exit(context, portfolio_pos, action)
                actions_taken.append({
                    'ticker': portfolio_pos.ticker,
                    'action': 'partial_exit',
                    'ratio': action.exit_ratio,
                    'result': partial_result
                })

            elif action.action == PositionActionType.ADJUST_STOP:
                Logger.print_info(f"  → 스탑 조정: {action.new_stop_loss:,.0f}")
                # 스탑 조정 로직 (실제 구현 필요)
                actions_taken.append({
                    'ticker': portfolio_pos.ticker,
                    'action': 'adjust_stop',
                    'new_stop': action.new_stop_loss
                })

            else:
                Logger.print_success(f"  → 포지션 유지")
                actions_taken.append({
                    'ticker': portfolio_pos.ticker,
                    'action': 'hold'
                })

        # 결과 반환
        if exit_performed:
            return StageResult(
                success=True,
                action='exit',
                data={
                    'status': 'success',
                    'decision': 'sell',
                    'reason': '포지션 청산 실행',
                    'actions': actions_taken
                },
                message="포지션 청산 완료"
            )

        return StageResult(
            success=True,
            action='continue',
            data={'actions': actions_taken},
            message="포지션 관리 완료"
        )

    def _handle_entry_mode(
        self,
        context: PipelineContext,
        portfolio_status
    ) -> StageResult:
        """
        ENTRY 모드 처리 (신규 진입 탐색)

        이 스테이지에서는 진입 가능 여부만 확인하고,
        실제 진입 분석은 다음 스테이지(AnalysisStage)에서 수행합니다.
        """
        Logger.print_info("🔍 진입 모드: 신규 진입 탐색")

        # 진입 가능 자본 확인
        available_capital = portfolio_status.available_capital
        Logger.print_info(f"  가용 자본: {available_capital:,.0f} KRW")

        if available_capital < 10000:  # 최소 1만원
            return StageResult(
                success=True,
                action='skip',
                data={
                    'status': 'success',
                    'decision': 'hold',
                    'reason': f'가용 자본 부족: {available_capital:,.0f} KRW'
                },
                message="가용 자본 부족"
            )

        # 진입 자본을 컨텍스트에 저장
        context.entry_capital = available_capital
        context.trading_mode = 'entry'

        return StageResult(
            success=True,
            action='continue',
            message="진입 모드 - 다음 스테이지에서 분석 진행"
        )

    def _collect_position_market_data(
        self,
        context: PipelineContext,
        ticker: str
    ) -> Dict[str, Any]:
        """
        포지션 관리용 시장 데이터 수집 (간소화)

        Args:
            context: 파이프라인 컨텍스트
            ticker: 코인 티커

        Returns:
            시장 데이터 딕셔너리
        """
        market_data = {}

        try:
            # 현재가 조회
            current_price = context.upbit_client.get_current_price(ticker)
            market_data['current_price'] = current_price

            # 차트 데이터 (시간봉)
            if context.data_collector:
                chart_data = context.data_collector.get_chart_data(ticker)
                if chart_data:
                    # 기술적 지표 계산
                    from src.trading.indicators import TechnicalIndicators
                    hourly = chart_data.get('minute60') or chart_data.get('hourly')
                    if hourly is not None and len(hourly) > 0:
                        indicators = TechnicalIndicators.get_latest_indicators(hourly)
                        market_data['technical_indicators'] = indicators

                        # 거래량 분석
                        volume_indicators = TechnicalIndicators.calculate_volume_indicators(hourly)
                        market_data['volume_analysis'] = volume_indicators

                        # 보유 캔들 수 (시간봉 기준 대략 계산)
                        market_data['holding_candles'] = 1  # 기본값

        except Exception as e:
            Logger.print_warning(f"시장 데이터 수집 실패: {str(e)}")

        return market_data

    def _execute_exit(
        self,
        context: PipelineContext,
        position: PortfolioPosition,
        action: PositionAction
    ) -> Dict[str, Any]:
        """
        청산 실행

        Args:
            context: 파이프라인 컨텍스트
            position: 포지션 정보
            action: 액션 정보

        Returns:
            실행 결과
        """
        try:
            if context.trading_service:
                result = context.trading_service.execute_sell(position.ticker)

                # 손익 기록
                if context.portfolio_manager:
                    context.portfolio_manager.record_trade_result(
                        position.ticker,
                        position.profit_loss,
                        position.profit_rate
                    )

                return {
                    'success': True,
                    'ticker': position.ticker,
                    'amount': position.amount,
                    'price': position.current_price,
                    'pnl': position.profit_loss,
                    'pnl_pct': position.profit_rate,
                    'trigger': action.trigger,
                    'ai_used': action.ai_used
                }
            else:
                return {'success': False, 'error': 'trading_service not available'}

        except Exception as e:
            Logger.print_error(f"청산 실행 실패: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _execute_partial_exit(
        self,
        context: PipelineContext,
        position: PortfolioPosition,
        action: PositionAction
    ) -> Dict[str, Any]:
        """
        부분 청산 실행

        Args:
            context: 파이프라인 컨텍스트
            position: 포지션 정보
            action: 액션 정보 (exit_ratio 포함)

        Returns:
            실행 결과
        """
        try:
            sell_amount = position.amount * action.exit_ratio

            if context.trading_service:
                # 부분 매도 (수량 지정)
                result = context.trading_service.execute_sell(
                    position.ticker,
                    amount=sell_amount
                )

                return {
                    'success': True,
                    'ticker': position.ticker,
                    'sold_amount': sell_amount,
                    'remaining_amount': position.amount - sell_amount,
                    'exit_ratio': action.exit_ratio,
                    'ai_used': action.ai_used
                }
            else:
                return {'success': False, 'error': 'trading_service not available'}

        except Exception as e:
            Logger.print_error(f"부분 청산 실패: {str(e)}")
            return {'success': False, 'error': str(e)}
