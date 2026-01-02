"""
거래 실행 스테이지

AI 분석 결과를 기반으로 실제 거래를 실행합니다.
- 매수/매도/보류 결정 실행
- 거래 시간 및 손익 기록
- 거래 결과 반환

마이그레이션 전략:
- Container가 있으면 ExecuteTradeUseCase 사용 (클린 아키텍처)
- Container가 없으면 trading_service 사용 (레거시 호환)
"""
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional

from src.trading.pipeline.base_stage import BasePipelineStage, PipelineContext, StageResult
from src.position.service import PositionService
from src.utils.logger import Logger
from src.config.settings import TradingConfig


class ExecutionStage(BasePipelineStage):
    """
    거래 실행 스테이지

    AI 분석 결과를 기반으로 실제 매수/매도/보류를 실행합니다.

    Container가 있으면 ExecuteTradeUseCase를 사용하고,
    없으면 레거시 trading_service를 사용합니다 (호환성 유지).
    """

    def __init__(self):
        super().__init__(name="Execution")

    async def execute(self, context: PipelineContext) -> StageResult:
        """
        거래 실행 (비동기)

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
                await self._execute_buy(context)
            elif decision == "sell":
                await self._execute_sell(context)
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

    def _has_use_case(self, context: PipelineContext) -> bool:
        """Container와 UseCase 사용 가능 여부 확인"""
        return context.container is not None

    async def _execute_buy(self, context: PipelineContext) -> None:
        """
        매수 실행

        Container가 있으면 UseCase 사용, 없으면 레거시 서비스 사용

        Args:
            context: 파이프라인 컨텍스트
        """
        if self._has_use_case(context):
            await self._execute_buy_with_use_case(context)
        else:
            self._execute_buy_legacy(context)

        # 거래 시간 기록
        if context.risk_manager:
            context.risk_manager.last_trade_time = datetime.now()
            context.risk_manager.daily_trade_count += 1

    async def _execute_buy_with_use_case(self, context: PipelineContext) -> None:
        """UseCase를 통한 매수 실행"""
        from src.domain.value_objects.money import Money, Currency

        use_case = context.container.get_execute_trade_use_case()

        # 매수 금액 결정 (설정값 또는 보유 현금의 일부)
        krw_balance = context.upbit_client.get_balance("KRW")
        buy_amount = self._calculate_buy_amount(krw_balance)

        # Money 객체로 변환
        amount = Money(Decimal(str(buy_amount)), Currency.KRW)

        # UseCase 실행
        response = await use_case.execute_buy(context.ticker, amount)

        # OrderResponse를 레거시 dict 형식으로 변환
        context.trade_result = self._convert_order_response_to_dict(response)

    def _execute_buy_legacy(self, context: PipelineContext) -> None:
        """레거시 서비스를 통한 매수 실행"""
        context.trade_result = context.trading_service.execute_buy(context.ticker)

    def _calculate_buy_amount(self, krw_balance: float) -> float:
        """매수 금액 계산"""
        # TradingConfig에서 매수 비율 또는 고정 금액 사용
        buy_ratio = getattr(TradingConfig, 'BUY_RATIO', 0.95)
        min_order = getattr(TradingConfig, 'MIN_ORDER_AMOUNT', 5000)

        buy_amount = krw_balance * buy_ratio

        # 최소 주문 금액 확인
        if buy_amount < min_order:
            return 0

        return buy_amount

    async def _execute_sell(self, context: PipelineContext) -> None:
        """
        매도 실행

        Container가 있으면 UseCase 사용, 없으면 레거시 서비스 사용

        Args:
            context: 파이프라인 컨텍스트
        """
        if self._has_use_case(context):
            await self._execute_sell_with_use_case(context)
        else:
            self._execute_sell_legacy(context)

        # 손익 기록
        if context.risk_manager and context.position_info:
            self._record_pnl(context)

    async def _execute_sell_with_use_case(self, context: PipelineContext) -> None:
        """UseCase를 통한 매도 실행"""
        use_case = context.container.get_execute_trade_use_case()

        # 전량 매도
        response = await use_case.execute_sell_all(context.ticker)

        # OrderResponse를 레거시 dict 형식으로 변환
        context.trade_result = self._convert_order_response_to_dict(response)

    def _execute_sell_legacy(self, context: PipelineContext) -> None:
        """레거시 서비스를 통한 매도 실행"""
        context.trade_result = context.trading_service.execute_sell(context.ticker)

    def _execute_hold(self, context: PipelineContext) -> None:
        """
        보류 실행

        Args:
            context: 파이프라인 컨텍스트
        """
        if context.trading_service:
            context.trading_service.execute_hold()

    def _convert_order_response_to_dict(self, response) -> Dict[str, Any]:
        """
        OrderResponse를 레거시 dict 형식으로 변환

        Args:
            response: OrderResponse 객체

        Returns:
            레거시 형식의 dict
        """
        result = {
            'success': response.success,
            'trade_id': response.order_id,
        }

        if response.success:
            # 성공 시 추가 정보
            if response.executed_price:
                result['price'] = float(response.executed_price.amount)
            if response.executed_volume:
                result['volume'] = float(response.executed_volume)
            if response.fee:
                result['fee'] = float(response.fee.amount)
        else:
            # 실패 시 에러 정보
            result['error'] = response.error_message or 'Unknown error'

        return result

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
