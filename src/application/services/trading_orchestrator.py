"""
트레이딩 오케스트레이터

Application Layer의 서비스로서, 거래 사이클의 비즈니스 로직을 조율합니다.
main.py에서 분리되어 Scheduler와 독립적으로 테스트 및 실행 가능합니다.

주요 책임:
- 거래 사이클 실행 조율 (HybridTradingPipeline)
- 포지션 관리 사이클 실행 조율 (PositionManagementPipeline)
- Idempotency 체크 (중복 주문 방지)
- Container를 통한 의존성 관리
- 에러 처리 및 결과 표준화
"""
from typing import Dict, Any, Optional, Callable, TYPE_CHECKING
from datetime import datetime, timezone

if TYPE_CHECKING:
    from src.container import Container

from src.trading.pipeline import (
    create_hybrid_trading_pipeline,
    create_position_management_pipeline,
    PipelineContext
)
from src.application.ports.outbound.idempotency_port import (
    IdempotencyPort,
    make_idempotency_key
)
from src.utils.logger import Logger


class IdempotencyError(Exception):
    """Idempotency check failure exception."""
    pass


class TradingOrchestrator:
    """
    트레이딩 오케스트레이터

    Container를 통해 의존성을 주입받고, 파이프라인을 통해
    거래 사이클을 실행합니다.

    Usage:
        from src.container import Container

        container = Container()
        orchestrator = TradingOrchestrator(container=container)

        # 거래 사이클 실행
        result = await orchestrator.execute_trading_cycle(
            ticker="KRW-BTC",
            enable_scanning=True
        )

        # 포지션 관리 실행
        result = await orchestrator.execute_position_management()
    """

    def __init__(self, container: 'Container') -> None:
        """
        초기화

        Args:
            container: 의존성 컨테이너 (필수)

        Raises:
            ValueError: container가 None인 경우
        """
        if container is None:
            raise ValueError("Container is required")
        self._container = container
        self._on_backtest_complete: Optional[Callable] = None

    def set_on_backtest_complete(self, callback: Callable) -> None:
        """
        백테스트 완료 콜백 설정

        Args:
            callback: 백테스트 완료 시 호출될 콜백 함수
        """
        self._on_backtest_complete = callback

    async def execute_trading_cycle(
        self,
        ticker: str = "KRW-BTC",
        trading_type: str = 'spot',
        enable_scanning: bool = True,
        max_positions: int = 2,
        # 리스크 관리 파라미터
        stop_loss_pct: float = -12.0,
        take_profit_pct: float = 15.0,
        daily_loss_limit_pct: float = -10.0,
        min_trade_interval_hours: int = 4,
        # 스캐너 파라미터
        liquidity_top_n: int = 10,
        min_volume_krw: float = 10_000_000_000,
        backtest_top_n: int = 5,
        final_select_n: int = 2
    ) -> Dict[str, Any]:
        """
        거래 사이클 실행 (하이브리드 파이프라인)

        단일 파이프라인으로 모든 거래 시나리오를 처리합니다:
        1. HybridRiskCheckStage: 포지션 상태 확인 및 모드 분기 + 코인 스캔 (옵션)
        2. DataCollectionStage: 데이터 수집
        3. AnalysisStage: 분석 (진입 모드에서만)
        4. ExecutionStage: 거래 실행

        Args:
            ticker: 거래 종목 (스캔 활성화 시 fallback 티커로 사용)
            trading_type: 거래 타입 ('spot' 또는 'futures')
            enable_scanning: 멀티코인 스캐닝 활성화 여부 (기본 True)
            max_positions: 최대 동시 포지션 수 (기본 2)
            stop_loss_pct: 손절 비율 (기본 -12%)
            take_profit_pct: 익절 비율 (기본 +15%)
            daily_loss_limit_pct: 일일 최대 손실 비율 (기본 -10%)
            min_trade_interval_hours: 최소 거래 간격 (기본 4시간)
            liquidity_top_n: 유동성 스캔 상위 N개 (기본 10)
            min_volume_krw: 최소 거래대금 (기본 100억원)
            backtest_top_n: 백테스팅 통과 상위 N개 (기본 5)
            final_select_n: 최종 선택 N개 (기본 2)

        Returns:
            {
                'status': 'success' | 'failed' | 'blocked' | 'skipped',
                'decision': 'buy' | 'sell' | 'hold',
                'confidence': float,
                'reason': str,
                'validation': str,
                'risk_checks': Dict,
                'price': float (optional),
                'amount': float (optional),
                'total': float (optional),
                'error': str (optional),
                'pipeline_status': str
            }
        """
        try:
            # 1. Idempotency 체크 (Fail-close 정책)
            # 동일 캔들/티커/액션은 1회만 실행
            try:
                candle_ts = self._get_current_candle_ts()
                idempotency_key = make_idempotency_key(
                    ticker=ticker,
                    timeframe="1h",
                    candle_ts=candle_ts,
                    action="trading_cycle"
                )

                idempotency_port = self._container.get_idempotency_port()
                is_duplicate = await idempotency_port.check_key(idempotency_key)

                if is_duplicate:
                    Logger.print_info(f"🔄 중복 거래 사이클 스킵: {idempotency_key}")
                    return {
                        'status': 'skipped',
                        'decision': 'hold',
                        'reason': f'Duplicate idempotency key: {idempotency_key}',
                        'idempotency_key': idempotency_key,
                        'pipeline_status': 'skipped'
                    }
            except IdempotencyError as e:
                # Idempotency 체크 실패 시 거래 차단 (Fail-close)
                Logger.print_error(f"Idempotency 체크 실패 - 거래 차단: {e}")
                return {
                    'status': 'blocked',
                    'decision': 'hold',
                    'reason': f'Idempotency check failed: {e}',
                    'error': f'Idempotency error: {e}',
                    'pipeline_status': 'blocked'
                }
            except Exception as e:
                # 기타 예외도 Fail-close
                Logger.print_error(f"Idempotency 체크 중 예외 - 거래 차단: {e}")
                return {
                    'status': 'blocked',
                    'decision': 'hold',
                    'reason': f'Idempotency check exception: {e}',
                    'error': f'Idempotency error: {e}',
                    'pipeline_status': 'blocked'
                }

            # 2. 거래 타입 검증
            if trading_type != 'spot':
                raise NotImplementedError(
                    f"거래 타입 '{trading_type}'는 아직 지원되지 않습니다."
                )

            # 3. 하이브리드 파이프라인 생성
            pipeline = create_hybrid_trading_pipeline(
                # 리스크 관리 파라미터
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct,
                daily_loss_limit_pct=daily_loss_limit_pct,
                min_trade_interval_hours=min_trade_interval_hours,
                max_positions=max_positions,
                # 스캔 파라미터
                enable_scanning=enable_scanning,
                fallback_ticker=ticker,
                liquidity_top_n=liquidity_top_n,
                min_volume_krw=min_volume_krw,
                backtest_top_n=backtest_top_n,
                final_select_n=final_select_n
            )

            # Container에서 레거시 서비스 추출 (점진적 마이그레이션용)
            upbit_client = self._get_legacy_client('upbit')
            data_collector = self._get_legacy_client('data_collector')
            trading_service = self._get_legacy_client('trading_service')
            ai_service = self._get_legacy_client('ai_service')

            # 컨텍스트 생성
            context = PipelineContext(
                ticker=ticker,
                trading_type=trading_type,
                container=self._container,
                upbit_client=upbit_client,
                data_collector=data_collector,
                trading_service=trading_service,
                ai_service=ai_service,
                on_backtest_complete=self._on_backtest_complete
            )

            # 4. 파이프라인 실행
            result = await pipeline.execute(context)

            # 5. 성공 시 idempotency 키 마킹
            if result.get('status') in ['success', 'skipped']:
                try:
                    await idempotency_port.mark_key(idempotency_key, ttl_hours=24)
                    result['idempotency_key'] = idempotency_key
                except Exception as mark_error:
                    # 마킹 실패는 경고만 (거래는 이미 실행됨)
                    Logger.print_warning(f"Idempotency 키 마킹 실패 (거래는 완료됨): {mark_error}")

            return result

        except Exception as e:
            Logger.print_error(f"거래 사이클 오류: {str(e)}")
            import traceback
            traceback.print_exc()

            return {
                'status': 'failed',
                'decision': 'hold',
                'error': str(e),
                'pipeline_status': 'failed'
            }

    async def execute_position_management(
        self,
        # 리스크 관리 파라미터
        stop_loss_pct: float = -12.0,
        take_profit_pct: float = 15.0,
        max_positions: int = 2
    ) -> Dict[str, Any]:
        """
        포지션 관리 전용 사이클 실행 (15분 주기용)

        기존 포지션의 손절/익절만 관리합니다.
        포지션이 없으면 즉시 종료합니다 (진입 로직 없음).

        Args:
            stop_loss_pct: 손절 비율 (기본 -12%)
            take_profit_pct: 익절 비율 (기본 +15%)
            max_positions: 최대 동시 포지션 수 (기본 2)

        Returns:
            {
                'status': 'success' | 'skipped' | 'failed',
                'decision': 'sell' | 'hold',
                'positions_checked': int,
                'actions': List[Dict],
                'cycle_type': 'position_management',
                'error': str (optional)
            }
        """
        try:
            Logger.print_header("🔄 포지션 관리 사이클 (15분)")

            # 포지션 관리 전용 파이프라인 생성
            pipeline = create_position_management_pipeline(
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct,
                max_positions=max_positions
            )

            # Container에서 레거시 서비스 추출
            upbit_client = self._get_legacy_client('upbit')
            data_collector = self._get_legacy_client('data_collector')
            trading_service = self._get_legacy_client('trading_service')

            # 컨텍스트 생성 (ticker는 동적으로 결정됨)
            context = PipelineContext(
                ticker="KRW-BTC",  # placeholder
                trading_type='spot',
                container=self._container,
                upbit_client=upbit_client,
                data_collector=data_collector,
                trading_service=trading_service,
                ai_service=None  # 포지션 관리는 AI 불필요
            )

            # 파이프라인 실행
            result = await pipeline.execute(context)

            # 결과에 포지션 관리 정보 추가
            result['cycle_type'] = 'position_management'

            return result

        except Exception as e:
            Logger.print_error(f"포지션 관리 사이클 오류: {str(e)}")
            import traceback
            traceback.print_exc()

            return {
                'status': 'failed',
                'decision': 'hold',
                'cycle_type': 'position_management',
                'error': str(e),
                'pipeline_status': 'failed'
            }

    def _get_legacy_client(self, service_name: str) -> Any:
        """
        Container에서 레거시 클라이언트 추출

        점진적 마이그레이션 동안 사용됩니다.

        Args:
            service_name: 서비스 이름 ('upbit', 'data_collector', 'trading_service', 'ai_service')

        Returns:
            해당 레거시 서비스 인스턴스 또는 None
        """
        try:
            if service_name == 'upbit':
                exchange_port = self._container.get_exchange_port()
                return getattr(exchange_port, '_client', None)
            elif service_name == 'data_collector':
                market_data_port = self._container.get_market_data_port()
                return getattr(market_data_port, '_collector', None)
            elif service_name == 'trading_service':
                # TradingService는 Container에서 직접 제공하지 않음
                # Exchange Port를 사용하거나 별도 생성 필요
                exchange_port = self._container.get_exchange_port()
                return getattr(exchange_port, '_trading_service', None)
            elif service_name == 'ai_service':
                ai_port = self._container.get_ai_port()
                return getattr(ai_port, '_service', None)
            else:
                return None
        except AttributeError:
            return None

    def _get_current_candle_ts(self, timeframe: str = "1h") -> int:
        """
        현재 캔들의 시작 타임스탬프를 계산합니다.

        캔들 마감 정렬을 위해, 현재 시간을 기준으로
        해당 타임프레임의 캔들 시작 시간을 반환합니다.

        Args:
            timeframe: 캔들 타임프레임 (기본 "1h")

        Returns:
            캔들 시작 Unix timestamp (초 단위)

        Examples:
            >>> # 09:30 에 호출 시
            >>> ts = self._get_current_candle_ts("1h")
            >>> # ts는 09:00의 timestamp (현재 캔들의 시작)

            >>> # 09:45에 호출 시
            >>> ts = self._get_current_candle_ts("15m")
            >>> # ts는 09:45의 timestamp
        """
        now = datetime.now(timezone.utc)

        if timeframe == "1h":
            # 시간 단위로 내림
            aligned = now.replace(minute=0, second=0, microsecond=0)
        elif timeframe == "15m":
            # 15분 단위로 내림
            minute = (now.minute // 15) * 15
            aligned = now.replace(minute=minute, second=0, microsecond=0)
        elif timeframe == "4h":
            # 4시간 단위로 내림
            hour = (now.hour // 4) * 4
            aligned = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        elif timeframe == "1d":
            # 일 단위로 내림
            aligned = now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            # 기본: 시간 단위
            aligned = now.replace(minute=0, second=0, microsecond=0)

        return int(aligned.timestamp())
