"""
거래 실행 스테이지

AI 분석 결과를 기반으로 실제 거래를 실행합니다.
- 매수/매도/보류 결정 실행
- 거래 시간 및 손익 기록
- 거래 결과 반환
"""
from datetime import datetime
from src.trading.pipeline.base_stage import BasePipelineStage, PipelineContext, StageResult
from src.position.service import PositionService
from src.utils.logger import Logger


class ExecutionStage(BasePipelineStage):
    """
    거래 실행 스테이지

    AI 분석 결과를 기반으로 실제 매수/매도/보류를 실행합니다.
    """

    def __init__(self):
        super().__init__(name="Execution")

    def execute(self, context: PipelineContext) -> StageResult:
        """
        거래 실행

        Args:
            context: 파이프라인 컨텍스트

        Returns:
            StageResult: 실행 결과
        """
        try:
            # 현재 가격 및 잔고 출력
            self._print_current_status(context)

            # AI 결정에 따라 거래 실행
            decision = context.ai_result.get("decision", "hold")

            if decision == "buy":
                self._execute_buy(context)
            elif decision == "sell":
                self._execute_sell(context)
            elif decision == "hold":
                self._execute_hold(context)
            else:
                Logger.print_error(
                    f"알 수 없는 판단: '{decision}' - 아무 작업도 수행하지 않습니다."
                )

            # 거래 결과 생성
            return self._create_result(context)

        except Exception as e:
            return self.handle_error(context, e)

    def _print_current_status(self, context: PipelineContext) -> None:
        """
        현재 가격 및 잔고 출력

        Args:
            context: 파이프라인 컨텍스트
        """
        current_price = context.upbit_client.get_current_price(context.ticker)
        krw_balance = context.upbit_client.get_balance("KRW")
        coin_balance = context.upbit_client.get_balance(context.ticker)

        if current_price:
            print(f"현재 {context.ticker} 가격: {current_price:,.0f}원")
        print(f"보유 현금: {krw_balance:,.0f}원")
        print(f"보유 {context.ticker}: {coin_balance:.8f}\n")

    def _execute_buy(self, context: PipelineContext) -> None:
        """
        매수 실행

        Args:
            context: 파이프라인 컨텍스트
        """
        context.trade_result = context.trading_service.execute_buy(context.ticker)

        # 거래 시간 기록
        if context.risk_manager:
            context.risk_manager.last_trade_time = datetime.now()
            context.risk_manager.daily_trade_count += 1

    def _execute_sell(self, context: PipelineContext) -> None:
        """
        매도 실행

        Args:
            context: 파이프라인 컨텍스트
        """
        context.trade_result = context.trading_service.execute_sell(context.ticker)

        # 손익 기록
        if context.risk_manager and context.position_info:
            self._record_pnl(context)

    def _execute_hold(self, context: PipelineContext) -> None:
        """
        보류 실행

        Args:
            context: 파이프라인 컨텍스트
        """
        context.trading_service.execute_hold()

    def _record_pnl(self, context: PipelineContext) -> None:
        """
        손익률 기록

        Args:
            context: 파이프라인 컨텍스트
        """
        avg_buy_price = context.position_info.get('avg_buy_price', 0)
        current_price = context.upbit_client.get_current_price(context.ticker)

        if avg_buy_price > 0 and current_price:
            pnl_pct = ((current_price - avg_buy_price) / avg_buy_price) * 100
            context.risk_manager.record_trade(pnl_pct)

    def _create_result(self, context: PipelineContext) -> StageResult:
        """
        거래 결과 생성

        Args:
            context: 파이프라인 컨텍스트

        Returns:
            StageResult: 거래 결과
        """
        current_price = context.upbit_client.get_current_price(context.ticker)
        coin_balance = context.upbit_client.get_balance(context.ticker)

        # 검증 결과 추출
        validation_reason = ""
        if context.validation_result:
            _, validation_reason, _ = context.validation_result

        result_data = {
            'status': 'success',
            'decision': context.ai_result.get('decision', 'hold'),
            'confidence': context.ai_result.get('confidence', 'medium'),
            'reason': context.ai_result.get('reason', ''),
            'validation': validation_reason,
            'risk_checks': {
                'position_check': context.position_check,
                'circuit_breaker': context.circuit_check,
                'frequency_check': context.frequency_check
            },
            'price': current_price,
            'amount': coin_balance,
            'total': current_price * coin_balance if current_price and coin_balance else 0,
            'flash_crash': context.flash_crash,
            'rsi_divergence': context.rsi_divergence,
            'backtest_result': context.backtest_result,
        }

        # 거래 실행 결과 추가
        if context.trade_result:
            result_data.update({
                'trade_id': context.trade_result.get('trade_id'),
                'trade_success': context.trade_result.get('success', False),
                'fee': context.trade_result.get('fee', 0),
            })
            if 'error' in context.trade_result:
                result_data['trade_error'] = context.trade_result['error']

        return StageResult(
            success=True,
            action='exit',
            data=result_data,
            message="거래 실행 완료"
        )
