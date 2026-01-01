"""
리스크 체크 스테이지

거래 실행 전 모든 리스크 조건을 체크합니다.
- 손절/익절 체크
- Circuit Breaker 체크
- 거래 빈도 제한 체크
"""
from typing import Dict, Any
from src.trading.pipeline.base_stage import BasePipelineStage, PipelineContext, StageResult
from src.risk.manager import RiskManager, RiskLimits
from src.position.service import PositionService
from src.utils.logger import Logger


class RiskCheckStage(BasePipelineStage):
    """
    리스크 관리 체크 스테이지

    이 스테이지는 거래 실행 전 모든 리스크 조건을 체크합니다.
    손절/익절 조건 충족 시 즉시 매도하고 파이프라인을 종료합니다.
    """

    def __init__(
        self,
        stop_loss_pct: float = -5.0,
        take_profit_pct: float = 10.0,
        daily_loss_limit_pct: float = -10.0,
        min_trade_interval_hours: int = 4
    ):
        """
        Args:
            stop_loss_pct: 손절 비율 (%)
            take_profit_pct: 익절 비율 (%)
            daily_loss_limit_pct: 일일 최대 손실 비율 (%)
            min_trade_interval_hours: 최소 거래 간격 (시간)
        """
        super().__init__(name="RiskCheck")
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.daily_loss_limit_pct = daily_loss_limit_pct
        self.min_trade_interval_hours = min_trade_interval_hours

    def execute(self, context: PipelineContext) -> StageResult:
        """
        리스크 체크 실행

        Args:
            context: 파이프라인 컨텍스트

        Returns:
            StageResult: 실행 결과
        """
        try:
            Logger.print_header("🛡️ 리스크 관리 체크")

            # 리스크 관리자 초기화
            context.risk_manager = RiskManager(
                limits=RiskLimits(
                    stop_loss_pct=self.stop_loss_pct,
                    take_profit_pct=self.take_profit_pct,
                    daily_loss_limit_pct=self.daily_loss_limit_pct,
                    min_trade_interval_hours=self.min_trade_interval_hours,
                )
            )

            # 1. 포지션 손익 체크
            position_result = self._check_position_limits(context)
            if position_result.action == 'exit':
                return position_result

            # 2. Circuit Breaker 체크
            circuit_result = self._check_circuit_breaker(context)
            if circuit_result.action == 'exit':
                return circuit_result

            # 3. 거래 빈도 제한 체크
            frequency_result = self._check_trade_frequency(context)
            if frequency_result.action == 'skip':
                return frequency_result

            Logger.print_success("✅ 모든 리스크 체크 통과 - 거래 진행")

            return StageResult(
                success=True,
                action='continue',
                message="리스크 체크 통과"
            )

        except Exception as e:
            return self.handle_error(context, e)

    def _check_position_limits(self, context: PipelineContext) -> StageResult:
        """
        포지션 손익 체크 (손절/익절)

        Args:
            context: 파이프라인 컨텍스트

        Returns:
            StageResult: 체크 결과
        """
        position_service = PositionService(context.upbit_client)
        position_info = position_service.get_detailed_position(context.ticker)
        current_price = context.upbit_client.get_current_price(context.ticker)

        position_check = context.risk_manager.check_position_limits(
            position_info, current_price
        )
        context.position_check = position_check

        # 손절 발동
        if position_check['action'] == 'stop_loss':
            Logger.print_error(f"🚨 손절 발동: {position_check['reason']}")
            sell_result = context.trading_service.execute_sell(context.ticker)
            context.risk_manager.record_trade(position_check['pnl_pct'])

            return StageResult(
                success=True,
                action='exit',
                data={
                    'decision': 'sell',
                    'reason': position_check['reason'],
                    'trigger': 'stop_loss',
                    'trade_result': sell_result,
                    'risk_checks': {'position_check': position_check}
                },
                message="손절 발동 - 거래 실행 후 종료"
            )

        # 익절 발동
        elif position_check['action'] == 'take_profit':
            Logger.print_success(f"💰 익절 발동: {position_check['reason']}")
            sell_result = context.trading_service.execute_sell(context.ticker)
            context.risk_manager.record_trade(position_check['pnl_pct'])

            return StageResult(
                success=True,
                action='exit',
                data={
                    'decision': 'sell',
                    'reason': position_check['reason'],
                    'trigger': 'take_profit',
                    'trade_result': sell_result,
                    'risk_checks': {'position_check': position_check}
                },
                message="익절 발동 - 거래 실행 후 종료"
            )

        return StageResult(
            success=True,
            action='continue',
            message="포지션 손익 체크 통과"
        )

    def _check_circuit_breaker(self, context: PipelineContext) -> StageResult:
        """
        Circuit Breaker 체크 (일일/주간 손실 한도)

        Args:
            context: 파이프라인 컨텍스트

        Returns:
            StageResult: 체크 결과
        """
        circuit_check = context.risk_manager.check_circuit_breaker()
        context.circuit_check = circuit_check

        if not circuit_check['allowed']:
            Logger.print_error(f"⛔ Circuit Breaker 발동: {circuit_check['reason']}")

            return StageResult(
                success=True,
                action='exit',
                data={
                    'decision': 'hold',
                    'reason': circuit_check['reason'],
                    'daily_pnl': circuit_check['daily_pnl'],
                    'weekly_pnl': circuit_check['weekly_pnl'],
                    'risk_checks': {'circuit_breaker': circuit_check}
                },
                message="Circuit Breaker 발동 - 거래 중단"
            )

        return StageResult(
            success=True,
            action='continue',
            message="Circuit Breaker 체크 통과"
        )

    def _check_trade_frequency(self, context: PipelineContext) -> StageResult:
        """
        거래 빈도 제한 체크

        Args:
            context: 파이프라인 컨텍스트

        Returns:
            StageResult: 체크 결과
        """
        frequency_check = context.risk_manager.check_trade_frequency()
        context.frequency_check = frequency_check

        if not frequency_check['allowed']:
            Logger.print_warning(f"⏭️ 거래 스킵: {frequency_check['reason']}")

            return StageResult(
                success=True,
                action='skip',
                data={
                    'decision': 'hold',
                    'reason': frequency_check['reason'],
                    'hours_since_last_trade': frequency_check['hours_since_last_trade'],
                    'risk_checks': {'frequency_check': frequency_check}
                },
                message="거래 빈도 제한 - 거래 스킵"
            )

        return StageResult(
            success=True,
            action='continue',
            message="거래 빈도 체크 통과"
        )
