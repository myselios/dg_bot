"""
데이터 수집 스테이지

거래 판단에 필요한 모든 데이터를 수집합니다.
- 차트 데이터 (ETH + BTC)
- 오더북 데이터
- 기술적 지표
- 현재 상태
- 포지션 정보
- 공포탐욕지수
"""
from typing import Dict, Optional
from src.trading.pipeline.base_stage import BasePipelineStage, PipelineContext, StageResult
from src.trading.indicators import TechnicalIndicators
from src.position.service import PositionService
from src.utils.logger import Logger


class DataCollectionStage(BasePipelineStage):
    """
    데이터 수집 스테이지

    거래 판단에 필요한 모든 시장 데이터 및 기술적 지표를 수집합니다.
    """

    def __init__(self):
        super().__init__(name="DataCollection")

    def execute(self, context: PipelineContext) -> StageResult:
        """
        데이터 수집 실행

        Args:
            context: 파이프라인 컨텍스트

        Returns:
            StageResult: 실행 결과
        """
        try:
            # 1. 투자 상태 조회
            self._collect_investment_status(context)

            # 2. 차트 데이터 수집 (ETH + BTC)
            chart_result = self._collect_chart_data(context)
            if not chart_result.success:
                return chart_result

            # 3. 오더북 데이터 수집
            self._collect_orderbook_data(context)

            # 4. 현재 상태 수집
            self._collect_current_status(context)

            # 5. 공포탐욕지수 수집
            self._collect_fear_greed_index(context)

            # 6. 기술적 지표 계산
            self._calculate_technical_indicators(context)

            # 7. 포지션 정보 수집
            self._collect_position_info(context)

            Logger.print_success("✅ 데이터 수집 완료")

            return StageResult(
                success=True,
                action='continue',
                message="데이터 수집 완료"
            )

        except Exception as e:
            return self.handle_error(context, e)

    def _collect_investment_status(self, context: PipelineContext) -> None:
        """
        현재 투자 상태 조회 및 출력

        Args:
            context: 파이프라인 컨텍스트
        """
        balances = context.upbit_client.get_balances()
        if balances:
            target_currency = context.ticker.split('-')[1] if '-' in context.ticker else None
            Logger.print_investment_status(
                balances,
                context.upbit_client,
                target_currency=target_currency
            )

    def _collect_chart_data(self, context: PipelineContext) -> StageResult:
        """
        차트 데이터 수집 (ETH + BTC)

        Args:
            context: 파이프라인 컨텍스트

        Returns:
            StageResult: 수집 결과
        """
        chart_data_with_btc = context.data_collector.get_chart_data_with_btc(context.ticker)

        if chart_data_with_btc is None:
            Logger.print_error("차트 데이터를 가져올 수 없어 프로그램을 종료합니다.")
            return StageResult(
                success=False,
                action='stop',
                message="차트 데이터 조회 실패",
                metadata={'error': '차트 데이터를 가져올 수 없습니다'}
            )

        context.chart_data = chart_data_with_btc['eth']
        context.btc_chart_data = chart_data_with_btc['btc']

        Logger.print_success(
            f"✅ BTC 데이터 수집 완료 (일봉: {len(context.btc_chart_data['day'])}일)"
        )

        return StageResult(
            success=True,
            action='continue',
            message="차트 데이터 수집 완료"
        )

    def _collect_orderbook_data(self, context: PipelineContext) -> None:
        """
        오더북 데이터 수집

        Args:
            context: 파이프라인 컨텍스트
        """
        context.orderbook = context.data_collector.get_orderbook(context.ticker)
        context.orderbook_summary = context.data_collector.get_orderbook_summary(
            context.orderbook
        )

    def _collect_current_status(self, context: PipelineContext) -> None:
        """
        현재 상태 정보 수집

        Args:
            context: 파이프라인 컨텍스트
        """
        context.current_status = {
            "krw_balance": context.upbit_client.get_balance("KRW"),
            "coin_balance": context.upbit_client.get_balance(context.ticker),
            "current_price": context.upbit_client.get_current_price(context.ticker)
        }

    def _collect_fear_greed_index(self, context: PipelineContext) -> None:
        """
        공포탐욕지수 조회

        Args:
            context: 파이프라인 컨텍스트
        """
        fear_greed_index = context.data_collector.get_fear_greed_index()

        if fear_greed_index:
            Logger.print_header("😨😍 공포탐욕지수")
            print(f"지수: {fear_greed_index['value']}/100")
            print(f"분류: {fear_greed_index['classification']}")
            print(Logger._separator() + "\n")

        context.fear_greed_index = fear_greed_index

    def _calculate_technical_indicators(self, context: PipelineContext) -> None:
        """
        기술적 지표 계산

        Args:
            context: 파이프라인 컨텍스트
        """
        context.technical_indicators = TechnicalIndicators.get_latest_indicators(
            context.chart_data['day']
        )

    def _collect_position_info(self, context: PipelineContext) -> None:
        """
        포지션 정보 수집

        Args:
            context: 파이프라인 컨텍스트
        """
        position_service = PositionService(context.upbit_client)
        context.position_info = position_service.get_detailed_position(context.ticker)
